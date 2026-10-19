import json
import os
import shutil
import tempfile
import threading
import subprocess
from time import sleep
from os import listdir
from os.path import isfile, join

from matplotlib.font_manager import json_load

try:
    from bin.logic_acm_library_parser import acm_library_parser
except:
    from logic_acm_library_parser import acm_library_parser

class acm_libraries_retrieval():
    '''
    A class that retrieves ACM libraries by project and moves the library files to the project folder. The class
    also creates quick reference files for the libraries.
    '''

    GET_LIBRARY_CMD = 'ACMConsole.exe'
    ACM_LIBRARY_FOLDER = 'acm_libraries'
    ACM_LIBRARY_ID_TO_FILES_PATH = "/acm_libraries"
    DEFAULT_ACM_LOCATION = r"C:\Program Files\Rockwell Automation\Application Code Manager\ACMConsole"

    def __init__(self, project_name, acm_project_name, acm_location=DEFAULT_ACM_LOCATION, threaded=True) -> None:
        """
        Initializes the acm_libraries_retrieval with the given parameters.

        :param project_name: The name of the project.
        :type project_name: str
        :param acm_project_name: The name of the ACM project.
        :type acm_project_name: str
        :param acm_location: The location of the ACM project, defaults to DEFAULT_ACM_LOCATION.
        :type acm_location: str, optional
        
        :return: None
        :rtype: None
        
        This method starts the retrieval process in a separate thread.
        """
        self.__project_name = project_name
        self.__acm_project_name = acm_project_name
        self.__acm_location = acm_location
        if threaded:
            threading.Thread(target=self.__start_retrival_process).start()
        else:
            self.__start_retrival_process()

    def __start_retrival_process(self):
        """
        Starts the retrieval process to export libraries by project and move the library files to the project folder.
        :return: None
        :rtype: None

        This method is called by the __init__ method. It is used to start the retrieval process in a separate thread.
        """
        fd, script = tempfile.mkstemp(suffix = '.tp')
        os.close(fd)
        temp_directory = tempfile.TemporaryDirectory()
        with open(script, "w") as text_file:
            text_file.write('exportlibrariesbyproject '
                                    +'"'+self.__acm_project_name+'" '
                                    +'"'+temp_directory.name+'"')
        subprocess.check_call([self.__acm_location +'\\'+self.GET_LIBRARY_CMD
                                    , '-p'
                                    , script])
        
        files = [join(temp_directory.name,f) for f in listdir(temp_directory.name) if isfile(join(temp_directory.name, f))]

        self.__move_library_files_to_project_folder(files)
        self.__create_library_quick_reference_files(files)


    @staticmethod
    def quick_library_retrevial(catalog_number:str, major_revision:str, minor_revision:str):
        """
        Retrieves ACM libraries by query and returns the output path.

        :param catalog_number: The catalog number of the library.
        :type catalog_number: str
        :param major_revision: The major revision of the library.
        :type major_revision: str
        :param minor_revision: The minor revision of the library.
        :type minor_revision: str
        :return: The output path of the libraries.
        :rtype: str

        """
        export_libraries_by_query_acm_command = '''
            exportlibrariesbyquery "CatalogNumber = '{catalog_number}' AND MajorRev = {major_revision} AND MinorRev = {minor_revision}" "{output_path}"
        '''

        fd, script = tempfile.mkstemp(suffix = '.tp')
        os.close(fd)
        # Create a temporary directory to store the library files
        temp_directory = tempfile.TemporaryDirectory()
        output_path = temp_directory.name

        with open(script, "w") as text_file:
            text_file.write(export_libraries_by_query_acm_command.format(catalog_number=catalog_number, major_revision=major_revision, minor_revision=minor_revision, output_path=output_path))
        subprocess.check_call([acm_libraries_retrieval.DEFAULT_ACM_LOCATION +'\\'+acm_libraries_retrieval.GET_LIBRARY_CMD
                                    , '-p'
                                    , script])
        
        # Get newly ceated file in folder
        filename = os.listdir(output_path)[0]
        new_file_path = os.path.join(output_path, filename)

        destination_folder = './temp/acm_libraries/'
        
        os.makedirs(os.path.dirname(destination_folder), exist_ok=True)
        shutil.copy(new_file_path, destination_folder )


        return os.path.join(destination_folder, filename)



    def __move_library_files_to_project_folder(self, files):
        """
        Moves the given files to the project folder for ACM libraries.

        :param files: List of file paths to be moved.
        :type files: list[str]
        :return: None
        :rtype: None
        
        This function creates the destination folder if it does not exist and copies each file from the given list to the destination folder.
        
        Example:
            >>> __move_library_files_to_project_folder(['file1.txt', 'file2.txt'])
        """
        destination_folder = './projects/' + self.__project_name + '/acm_libraries/'
        
        os.makedirs(os.path.dirname(destination_folder), exist_ok=True)
        for f in files:
            shutil.copy(f, destination_folder )


    def __create_library_quick_reference_files(self, files):
        """
        Creates quick reference files for libraries.

        :param files: List of file paths.
        :type files: list[str]
        :return: Dictionary mapping library IDs to file names.
        :rtype: dict[str, str]

        This function creates a dictionary mapping library IDs to file names and writes it to a file named 'library' in the destination folder.
        """
        library_id_file_reference = {}
        destination = './projects/' + self.__project_name + self.ACM_LIBRARY_ID_TO_FILES_PATH
        for f in files:
            parser = acm_library_parser(f)
            parser.extract_object_NIBS(destination)
            parser.extract_subobjects(destination)
            library_id = parser.get_library_ID()

            library_id_file_reference[library_id] = os.path.basename(f)

        
        with open(destination+'/library', 'w') as outfile:
            json.dump(library_id_file_reference, outfile)


def get_library_file_path(library_id:str, project_name):
        """
        Retrieves the file path of a library based on its ID and project name.

        :param library_id: The ID of the library.
        :type library_id: str
        :param project_name: The name of the project.
        :type project_name: str
        :return: The file path of the library.
        :rtype: str

        Retrieves the file path of a library based on its ID and project name. 
        If the library ID is not found in the library file reference, None is returned.
        
        Example:
            >>> get_library_file_path('123', 'my_project')
            './projects/my_project/acm_libraries/library_file.py'
        """
        library_id_file_reference = {}
        location = './projects/' + project_name + acm_libraries_retrieval.ACM_LIBRARY_ID_TO_FILES_PATH
        library_id_file_reference = json_load(location+'/library')

        if not library_id in library_id_file_reference:
            return 

        return ('./projects/' 
                    + project_name 
                    + '/' + acm_libraries_retrieval.ACM_LIBRARY_FOLDER 
                    + '/' + library_id_file_reference[library_id])




if __name__ == '__main__':
    acm_libraries_retrieval('A_project',"Example_ACM_Plant",r"C:\Program Files\Rockwell Automation\Application Code Manager\ACMConsole")
    print(get_library_file_path('9F72B21D-8949-49B0-A0AF-8C9995C116C2','A_project'))