import zipfile
import os
import re
from configparser import ConfigParser
from io import StringIO

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


def import_project(zip_file_path, extract_to_path='./projects/'):
    """
    Import a project by extracting the files from the zip archive to the specified destination folder.

    :param zip_file_path: The path to the (aip) zip file containing the project files.
    :type zip_file_path: str
    :param extract_to_path: The path to the destination folder where the project files will be extracted. Default is './projects/'.
    :type extract_to_path: str
    :return: True if the import was successful.
    :rtype: bool

    :raises FileNotFoundError: If the (aip) zip file does not exist.
    :raises zipfile.BadZipFile: If the file is not a valid (aip) zip file.
    :raises PermissionError: If there are issues with write permissions.
    :raises OSError: If a file system error occurs.

    This function imports a project by extracting the files from the (aip) zip archive to the specified destination folder.
    The folder structure within the (aip) zip file is preserved.

    Example:
        >>> import_project('my_project.aip', './projects/')
    """
    abs_extract_to_path = os.path.abspath(extract_to_path)
    try:
        # Create the destination folder if it doesn't exist
        if not os.path.exists(abs_extract_to_path):
            os.makedirs(abs_extract_to_path)

        # Open the ZIP archive file
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            # Extract all contents to the destination folder
            zip_ref.extractall(abs_extract_to_path)
        
        return True
    except FileNotFoundError:
        raise FileNotFoundError(f"The AIP file '{zip_file_path}' does not exist.")
    except zipfile.BadZipFile:
        raise zipfile.BadZipFile(f"The file '{zip_file_path}' is not a valid AIP archive or is corrupt.")
    except PermissionError:
        raise PermissionError(f"Permission denied while accessing '{extract_to_path}'.")
    except OSError as e:
        raise OSError(f"A file system error occurred: {e}")
    

def read_project_name_from_zip(zip_path):
    """
    Reads the project name from a (aip) zip file.

    :param zip_path: The path to the (aip) zip file.
    :type zip_path: str
    :return: The name of the project.
    :rtype: str

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

    project_name = config_parser['DEFAULT']['Name']

    # Same rule as Validators.project_name_validator. The name becomes a folder under
    # ./projects/ and is later passed to the ACM console, so refuse anything else.
    if not re.fullmatch(r'[\w. ]+', project_name) or not project_name.strip(' .'):
        raise ValueError(f"Invalid project name {project_name!r} in project archive")

    return project_name
