import zipfile
import os
import shutil
import tempfile
import uuid
from configparser import ConfigParser
from io import StringIO
try:
    from bin.logic_project_paths import (InvalidProjectName, find_existing_project, is_inside, is_link, project_dir,
                                         validate_project_name)
except ImportError:
    from logic_project_paths import (InvalidProjectName, find_existing_project, is_inside, is_link, project_dir,
                                     validate_project_name)

MAX_ARCHIVE_ENTRIES = 50000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 4 * 1024 ** 3
MAX_PROJECT_INI_BYTES = 64 * 1024
STAGING_PREFIX = '.aip-import-'
REPLACED_PREFIX = '.aip-replaced-'


class InvalidProjectArchive(ValueError):
    pass


class ReplacedProjectNotRemoved(Exception):
    """The new project was imported, but the previous version could not be fully deleted."""

    def __init__(self, backup_path, error):
        super().__init__(
            f"The project was imported, but the previous version could not be fully removed ({error}). "
            f"Its remaining files were kept in '{backup_path}'.")
        self.backup_path = backup_path

def export_project(source_folder, output_filename):
    """
    Export a project by archiving the files in the source folder and saving them to the output filename.

    :param source_folder: The path to the source folder containing the project files.
    :type source_folder: str
    :param output_filename: The name of the output file to save the archived project.
    :type output_filename: str
    :return: None
    :rtype: None

    :raises FileNotFoundError: If the source folder does not exist.
    :raises PermissionError: If there are issues with write permissions.
    :raises Exception: For other errors that occur during archiving.

    This function exports a project by creating a (aip) zip file and adding all the files in the source folder to the (aip) zip file.
    The folder structure within the (aip) zip file is preserved.

    Example:
        >>> export_project('my_project', 'my_project.aip')
    """
    
    try:
        with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for foldername, _, filenames in os.walk('./projects/' + source_folder):
                for filename in filenames:
                    file_path = os.path.join(foldername, filename)
                    arcname = os.path.relpath(file_path,'./projects/' + source_folder)  # preserve folder structure within the zip
                    zipf.write(file_path, arcname)

    except FileNotFoundError:
        raise FileNotFoundError(f"The source folder '{source_folder}' does not exist.")
    except PermissionError:
        raise PermissionError(f"Permission denied while writing to '{output_filename}'.")
    except Exception as e:
        raise Exception(f"An error occurred during archiving: {e}")


def check_archive_members(zip_ref, destination):
    """
    Reject archives that are too large or contain entries that would land outside ``destination``.

    :raises InvalidProjectArchive: on too many entries, too much uncompressed data,
        or an absolute / drive-qualified / '..' entry name.
    """
    members = zip_ref.infolist()
    if len(members) > MAX_ARCHIVE_ENTRIES:
        raise InvalidProjectArchive(
            f"The AIP archive has {len(members)} entries (limit {MAX_ARCHIVE_ENTRIES}).")
    total_size = sum(member.file_size for member in members)
    if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
        raise InvalidProjectArchive(
            f"The AIP archive expands to {total_size} bytes (limit {MAX_ARCHIVE_UNCOMPRESSED_BYTES}).")

    for member in members:
        name = member.filename
        parts = name.replace('\\', '/').split('/')
        if (name.startswith(('/', '\\')) or any(part == '..' or ':' in part for part in parts)
                or os.path.isabs(name)):
            raise InvalidProjectArchive(f"The AIP archive contains an unsafe entry name: {name!r}")
        if not is_inside(destination, os.path.join(destination, name)):
            raise InvalidProjectArchive(f"The AIP archive entry {name!r} points outside the project folder.")


def _remove_tree(path):
    if is_link(path):
        os.unlink(path) if os.path.islink(path) else os.rmdir(path)
    else:
        shutil.rmtree(path)


def _swap_into_place(staging, destination, existing=None):
    """
    Move ``staging`` to ``destination``. ``existing`` (default: ``destination``) is moved aside first
    and only deleted once the move succeeded.

    :raises ReplacedProjectNotRemoved: if the new project is in place but the old one could not be deleted.
    """
    existing = existing or destination
    backup = None
    if os.path.lexists(existing):
        backup = os.path.join(os.path.dirname(existing), REPLACED_PREFIX + uuid.uuid4().hex)
        os.rename(existing, backup)
    try:
        os.rename(staging, destination)
    except Exception:
        if backup:
            os.rename(backup, existing)
        raise
    if backup:
        try:
            _remove_tree(backup)
        except OSError as e:
            raise ReplacedProjectNotRemoved(backup, e) from e


def import_project(zip_file_path, project_name, replace=False):
    """
    Import a project by extracting the (aip) zip archive into ./projects/<project_name>.

    :param zip_file_path: The path to the (aip) zip file containing the project files.
    :type zip_file_path: str
    :param project_name: The project name; must be a plain folder name (see logic_project_paths).
    :type project_name: str
    :param replace: Replace the existing project this name resolves to (see find_existing_project).
    :type replace: bool
    :return: True if the import was successful.
    :rtype: bool

    :raises InvalidProjectName: If the project name is not a plain folder name.
    :raises InvalidProjectArchive: If the archive is too large or has unsafe entry names.
    :raises FileExistsError: If the project folder exists and ``replace`` is False.
    :raises ReplacedProjectNotRemoved: If the import succeeded but the old project could not be fully deleted.
    :raises FileNotFoundError: If the (aip) zip file does not exist.
    :raises zipfile.BadZipFile: If the file is not a valid (aip) zip file.
    :raises PermissionError: If there are issues with write permissions.
    :raises OSError: If a file system error occurs.

    The archive is validated, then extracted into a fresh staging folder under ./projects and
    renamed into place. An existing project is only removed after the new one is in place, so a
    rejected or failed import leaves it untouched.

    Example:
        >>> import_project('my_project.aip', 'my_project')
    """
    abs_extract_to_path = project_dir(project_name)
    root = os.path.dirname(abs_extract_to_path)
    try:
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            check_archive_members(zip_ref, abs_extract_to_path)

            existing = find_existing_project(project_name)
            if existing and not replace:
                raise FileExistsError(f"The project '{existing}' already exists.")
            existing_path = project_dir(existing) if existing else None

            os.makedirs(root, exist_ok=True)
            staging = tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=root)
            try:
                zip_ref.extractall(staging)
                _swap_into_place(staging, abs_extract_to_path, existing_path)
            except ReplacedProjectNotRemoved:
                raise
            except Exception:
                shutil.rmtree(staging, ignore_errors=True)
                raise

        return True
    except (FileExistsError, ReplacedProjectNotRemoved):
        raise
    except FileNotFoundError:
        raise FileNotFoundError(f"The AIP file '{zip_file_path}' does not exist.")
    except zipfile.BadZipFile:
        raise zipfile.BadZipFile(f"The file '{zip_file_path}' is not a valid AIP archive or is corrupt.")
    except PermissionError:
        raise PermissionError(f"Permission denied while accessing '{abs_extract_to_path}'.")
    except OSError as e:
        raise OSError(f"A file system error occurred: {e}")
    

def read_project_name_from_zip(zip_path):
    """
    Reads the project name from a (aip) zip file.

    :param zip_path: The path to the (aip) zip file.
    :type zip_path: str
    :return: The name of the project.
    :rtype: str
    :raises InvalidProjectName: If the name is not a plain folder name (e.g. contains '..' or path separators).
    :raises InvalidProjectArchive: If project.ini or the archive exceeds the size limits or has unsafe entry names.

    This function reads the project name from a (aip) zip file by extracting the 'project.ini' file from the zip,
    parsing its content, and returning the value of the 'Name' key in the 'DEFAULT' section of the config file.
    
    Example:
        >>> read_project_name_from_zip('/path/to/zip_file.aip')
        'My Project'
    """
    

    config_file_name = 'project.ini'

    with zipfile.ZipFile(zip_path, 'r') as zip:
        # Ensure the config file exists in the zip
        if config_file_name not in zip.namelist():
            raise KeyError(f"Not a valid project")

        if zip.getinfo(config_file_name).file_size > MAX_PROJECT_INI_BYTES:
            raise InvalidProjectArchive(f"project.ini is larger than {MAX_PROJECT_INI_BYTES} bytes.")

        # Read the config file content
        with zip.open(config_file_name) as config_file:
            config_content = StringIO(config_file.read().decode())

        # Parse the config file
        config_parser = ConfigParser()
        config_parser.read_file(config_content)
        name = validate_project_name(config_parser['DEFAULT']['Name'])

        # Reject unsafe archives here so callers never delete or overwrite anything for them
        check_archive_members(zip, project_dir(name))

    return name
