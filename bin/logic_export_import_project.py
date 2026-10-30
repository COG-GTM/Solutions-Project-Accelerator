import zipfile
import os
import shutil
from configparser import ConfigParser
from io import StringIO
try:
    from bin.logic_project_paths import InvalidProjectName, is_inside, project_dir, validate_project_name
except ImportError:
    from logic_project_paths import InvalidProjectName, is_inside, project_dir, validate_project_name

MAX_ARCHIVE_ENTRIES = 50000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 4 * 1024 ** 3


class InvalidProjectArchive(ValueError):
    pass

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


def import_project(zip_file_path, project_name):
    """
    Import a project by extracting the (aip) zip archive into ./projects/<project_name>.

    :param zip_file_path: The path to the (aip) zip file containing the project files.
    :type zip_file_path: str
    :param project_name: The project name; must be a plain folder name (see logic_project_paths).
    :type project_name: str
    :return: True if the import was successful.
    :rtype: bool

    :raises InvalidProjectName: If the project name is not a plain folder name.
    :raises InvalidProjectArchive: If the archive is too large or has unsafe entry names.
    :raises FileNotFoundError: If the (aip) zip file does not exist.
    :raises zipfile.BadZipFile: If the file is not a valid (aip) zip file.
    :raises PermissionError: If there are issues with write permissions.
    :raises OSError: If a file system error occurs.

    The folder structure within the (aip) zip file is preserved. Nothing is written
    unless the destination is a direct child of ./projects and every entry stays inside it.

    Example:
        >>> import_project('my_project.aip', 'my_project')
    """
    abs_extract_to_path = project_dir(project_name)
    created = False
    try:
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            check_archive_members(zip_ref, abs_extract_to_path)

            if not os.path.exists(abs_extract_to_path):
                os.makedirs(abs_extract_to_path)
                created = True

            try:
                zip_ref.extractall(abs_extract_to_path)
            except Exception:
                if created:
                    shutil.rmtree(abs_extract_to_path, ignore_errors=True)
                raise

        return True
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

        # Read the config file content
        with zip.open(config_file_name) as config_file:
            config_content = StringIO(config_file.read().decode())

    # Parse the config file
    config_parser = ConfigParser()
    config_parser.read_file(config_content)

    return validate_project_name(config_parser['DEFAULT']['Name'])
