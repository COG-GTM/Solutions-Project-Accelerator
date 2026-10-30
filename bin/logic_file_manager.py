import io
import logging
import shutil
from contextlib import ExitStack
from PIL import Image
import cv2
import numpy as np
try:
    from bin.logic_logger import handle_exception_with_messagebox
    from bin.logic_pdf_render import page_count, render_page
    from bin.logic_svg_safety import render_svg_to_png
except:
    from logic_logger import handle_exception_with_messagebox
    from logic_pdf_render import page_count, render_page
    from logic_svg_safety import render_svg_to_png
import uuid
import os
from shutil import copy
import configparser
import pikepdf
import datetime

class Project_File_Manager():
    '''
    A class that manages project files and directories.
    '''

    @handle_exception_with_messagebox()
    def create_project(project_name, project_description,version):
        """
        Creates a new project with the given name, description, and version.
        
        :param project_name: The name of the project.
        :type project_name: str
        :param project_description: The description of the project.
        :type project_description: str
        :param version: The version of the project.
        :type version: str
        :return: The name of the created project.
        :rtype: str
        
        This function creates a new project directory with the given name in the './projects/' directory.
        It also creates a 'project.ini' file inside the project directory, which contains the project's name,
        description, and version. If the project directory already exists, it does nothing and returns the
        project name.
        
        Example:
            >>> create_project('my_project', 'This is my project', '1.0')
            'my_project'
        """
        
        destination = './projects/'+project_name 
       
        if not os.path.exists(destination):
            os.makedirs(destination,  exist_ok=True)

        config = configparser.ConfigParser()
        config['DEFAULT']['Name'] = project_name
        config['DEFAULT']['Description'] = project_description
        config['DEFAULT']['Version'] = version

        with open('./projects/'+project_name+'/project.ini', 'w') as configfile:
            config.write(configfile)

        return project_name


    @handle_exception_with_messagebox()
    def import_drawing_file(path, project_name):
        """
        Imports a drawing document file to a specified project directory.

        :param path: The path of the drawing document file to import.
        :type path: str
        :param project_name: The name of the project.
        :type project_name: str
        :return: The destination path of the imported file.
        :rtype: str

        This function creates a destination directory for the imported file based on the project name and a unique identifier.
        It then copies the file from the given path to the destination directory and returns the destination path.
        
        Example:
            >>> import_text_document_file('/path/to/file.txt', 'my_project')
            './projects/my_project/drawings/12345678-1234-1234-1234-1234567890ab'
        """
        file_extension = os.path.splitext(path)[1]
        
        # for pdf 
        if file_extension.lower() == '.pdf':
            destination = './projects/'+project_name+'/drawings/'+str(uuid.uuid4())
        
            if not os.path.exists(destination):
                os.makedirs(destination,  exist_ok=True)
            
            copy(path, destination)
            return destination
        
        elif file_extension.lower() in ['.png','.jpg','.jpeg']:
            destination = './projects/'+project_name+'/drawings/'+str(uuid.uuid4())+'/images'
        
            if not os.path.exists(destination):
                os.makedirs(destination,  exist_ok=True)

            copy(path, destination + '/0' + file_extension)
            return destination

        


    @handle_exception_with_messagebox()
    def combine_drawing_files(files, project_name):
        """
        Combines multiple drawing files into a single PDF file or for images a single image folder.

        :param files: A list of paths to the files to be combined.
        :type files: list[str]
        :param project_name: The name of the project.
        :type project_name: str
        :return: A tuple containing the destination path and the combined file name (if applicable).
        :rtype: tuple[str, str or None]

        This function combines multiple PDF files into a single PDF file with a filename based on the current date and time,
        e.g., Combined_2021-09-30_14-30.pdf. For image files, it copies them into a single image folder.
        
        Example:
            >>> combine_drawing_files(['/path/to/file1.pdf', '/path/to/file2.pdf'], 'my_project')
            ('./projects/my_project/drawings/12345678-1234-1234-1234-1234567890ab', 'Combined_2021-09-30_14-30.pdf')
        """
        # Combine multiple PDF files into a single PDF file with a filename based on the current date and time e.g Combined_2021-09-30_14-30.pdf
        
        file_extension = os.path.splitext(files[0])[1]
        datetime_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
        if file_extension.lower() in ['.png','.jpg','.jpeg']:
            destination = './projects/'+project_name+'/drawings/'+str(uuid.uuid4())+'/images'

            filename = 'Combined_Images_'+datetime_str
            if not os.path.exists(destination):
                os.makedirs(destination,  exist_ok=True)

            # Change the filename to a number starting from 0
            for i, file in enumerate(files):
                copy(file, destination + '/' + str(i) + file_extension)
            return destination, filename
        else:
            destination = './projects/'+project_name+'/drawings/'+str(uuid.uuid4())
            
            filename = 'Combined_PDF_'+datetime_str+'.pdf'

            if not os.path.exists(destination):
                os.makedirs(destination,  exist_ok=True)

            # pikepdf copies page data lazily, so every source has to stay open until the save
            with ExitStack() as sources:
                pdf_writer = pikepdf.Pdf.new()
                for pdf_file in files:
                    pdf = sources.enter_context(pikepdf.open(pdf_file))
                    pdf_writer.pages.extend(pdf.pages)
                pdf_writer.save(destination + '/' + filename)
                pdf_writer.close()
            return destination, filename
    


    @handle_exception_with_messagebox()
    def import_pdf_as_images(files, project_name, zoom=2.0, page_callback=None):
        """
        Rasterises one or more PDFs into a folder of full colour PNG pages.

        :param files: A list of paths to the PDF files to rasterise.
        :type files: list[str]
        :param project_name: The name of the project.
        :type project_name: str
        :param zoom: The render scale, where 1.0 is 72 DPI. Defaults to 2.0 (~144 DPI).
        :type zoom: float
        :param page_callback: Optional callable invoked as ``page_callback(done, total)`` after each page.
            Returning True cancels the import and removes the partially written folder.
        :type page_callback: callable or None
        :return: A tuple containing the destination path and the document name, or None if cancelled.
        :rtype: tuple[str, str] or None

        The pages are written in colour with no grayscale or threshold step, so a document
        imported this way keeps its colours when scanned as a ``Database.IMAGE`` document.
        The folder layout matches :func:`combine_drawing_files` so the rest of the app can
        read the pages through :func:`get_drawing_image_files`.

        Example:
            >>> import_pdf_as_images(['/path/to/file.pdf'], 'my_project')
            ('./projects/my_project/drawings/12345678-1234-1234-1234-1234567890ab/images', 'file.pdf')
        """
        page_counts = [page_count(pdf_file) for pdf_file in files]
        total = sum(page_counts)

        destination = './projects/'+project_name+'/drawings/'+str(uuid.uuid4())+'/images'

        if len(files) == 1:
            filename = os.path.basename(files[0])
        else:
            filename = 'Combined_Images_'+datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")

        if not os.path.exists(destination):
            os.makedirs(destination,  exist_ok=True)

        page_index = 0
        for pdf_file, pages in zip(files, page_counts):
            for pno in range(pages):
                image = render_page(pdf_file, pno, zoom=zoom)
                # Zero padded because get_drawing_image_files orders pages with a plain string sort.
                image.save(destination + '/' + str(page_index).zfill(4) + '.png')
                page_index += 1
                if page_callback and page_callback(page_index, total):
                    shutil.rmtree(os.path.dirname(destination), ignore_errors=True)
                    return None

        return destination, filename


    @handle_exception_with_messagebox()
    def combine_with_existing_drawing(existing_drawing, files):
        """
        Combines multiple drawing files with an existing drawing file.

        :param existing_drawing: The path of the existing drawing file.
        :type existing_drawing: str
        :param files: A list of paths to the files to be combined with the existing drawing file.
        :type files: list[str]
        :return: The path of the combined drawing file.
        :rtype: str

        This function combines multiple drawing files (PDF or images) with an existing drawing file. 
        For PDF files, it appends the contents of each input PDF file to the existing PDF file.
        For image files, it copies them into the same directory as the existing image files.
        
        Example:
            >>> combine_with_existing_drawing('/path/to/existing_file.pdf', ['/path/to/file1.pdf', '/path/to/file2.pdf'])
            '/path/to/existing_file.pdf'
        """

        file_extension = os.path.splitext(files[0])[1]
        
        if file_extension.lower() in ['.png','.jpg','.jpeg']:
            destination = os.path.dirname(existing_drawing) 
            if not os.path.exists(destination):
                os.makedirs(destination,  exist_ok=True)

            # Get number of files in the existing directory and start from there
            existing_files_num = len(Project_File_Manager.get_drawing_image_files(destination))
            for i, file in enumerate(files):
                copy(file, destination + '/' + str(existing_files_num + i) + file_extension)
            return destination
        else:
            # pikepdf copies page data lazily, so every source has to stay open until the save
            with ExitStack() as sources:
                pdf_writer = sources.enter_context(
                    pikepdf.open(existing_drawing, allow_overwriting_input=True))

                for file in files:
                    pages = sources.enter_context(pikepdf.open(file))
                    pdf_writer.pages.extend(pages.pages)

                pdf_writer.save(existing_drawing)
            return existing_drawing

    @staticmethod
    def get_drawing_image_files(partial_path):
        """
        Retrieves a list of drawing files in a specified directory.

        :param partial_path: The partial path of the directory containing the drawing files.
        :type partial_path: str
        :return: A list of drawing file names.
        :rtype: list[str]
        """
        drawing_files = []
        for _, __, files in os.walk(partial_path):
            for file in files:
                drawing_files.append(os.path.join(partial_path, file))
        # Sort the list of files alphabetically
        drawing_files.sort()
        return drawing_files
    

    @handle_exception_with_messagebox()
    def delete_document_file(partial_path):
        """
        Deletes a document file.

        :param partial_path: The partial path of the file to be deleted.
        :type partial_path: str
        :return: None
        :rtype: None
        """
        
        shutil.rmtree(partial_path)



    @handle_exception_with_messagebox()
    def import_text_document_file(path, project_name):
        """
        Imports a text document file to a specified project directory.

        :param path: The path of the text document file to import.
        :type path: str
        :param project_name: The name of the project.
        :type project_name: str
        :return: The destination path of the imported file.
        :rtype: str

        This function creates a destination directory for the imported file based on the project name and a unique identifier.
        It then copies the file from the given path to the destination directory and returns the destination path.
        
        Example:
            >>> import_text_document_file('/path/to/file.txt', 'my_project')
            './projects/my_project/text_documents/12345678-1234-1234-1234-1234567890ab'
        """
        
        destination = './projects/'+project_name+'/text_documents/'+str(uuid.uuid4())
        
        if not os.path.exists(destination):
            os.makedirs(destination,  exist_ok=True)

        copy(path, destination)
        return destination
        

    @handle_exception_with_messagebox()
    def import_Sheets_file(path, project_name):
        """
        Imports a Sheets file (table document type) to a specified project directory.

        :param path: The path of the Sheets file (table document type) to import.
        :type path: str
        :param project_name: The name of the project.
        :type project_name: str
        :return: The destination path where the file was copied.
        :rtype: str

        This function creates a destination directory for the project and copies the Sheets file to that directory.
        It returns the destination path where the file was copied.
        
        Example:
            >>> import_Sheets_file('/path/to/file', 'my_project')
            './projects/my_project/sheets/12345678-1234-1234-1234-1234567890ab'
        """
        
        destination = './projects/'+project_name+'/sheets/'+str(uuid.uuid4())
        
        if not os.path.exists(destination):
            os.makedirs(destination,  exist_ok=True)

        copy(path, destination)
        return destination
    

    @handle_exception_with_messagebox()
    def get_all_projects():
        """
        Retrieves a list of all projects in the 'projects' directory.

        :return: A list of project names.
        :rtype: list[str]
        """
        projects = []
        
        directory = './projects'
        
        folders = [x[1] for x in os.walk(directory)]
        if len(folders)<=0:
            return[]

        for project in folders[0]: 
            projects.append(project)

        return projects
    


    def get_project_details(project_name):
        """
        Retrieves the name and description of a project from its configuration file.

        :param project_name: The name of the project.
        :type project_name: str
        :return: A tuple containing the name and description of the project.
        :rtype: tuple[str, str]
        """
        config = configparser.ConfigParser()
        config.read('./projects/'+project_name+'/project.ini')

        name = config['DEFAULT']['Name']
        description = config['DEFAULT']['Description']

        return name, description


    def open_pillow_image(path):
        """
        Opens an image file using the Pillow library.
        
        :param path: The path to the image file.
        :type path: str
        :return: The opened image.
        :rtype: PIL.Image.Image
        
        This function checks the file extension of the given path. If the extension is '.svg', it rasterises the SVG offline with a capped size (see ``bin.logic_svg_safety``) and then opens the converted image using the Pillow library. If the extension is not '.svg', it directly opens the image using the Pillow library.
        
        Example:
            >>> open_pillow_image('/path/to/image.png')
            <PIL.PngImagePlugin.PngImageFile image mode=RGB size=400x300 at 0x7F9B2C9D7F60>
        """
        _,extension = os.path.splitext(path)
        if extension.lower() == '.svg':
            image_data = render_svg_to_png(path)
            image = Image.open(io.BytesIO(image_data))
            return image
        else:
            return Image.open(path)


    @handle_exception_with_messagebox()
    def import_image_file(path, project_name):
        """
        Imports an image file to the specified project directory.

        :param path: The path of the image file to import.
        :type path: str
        :param project_name: The name of the project.
        :type project_name: str
        :return: The destination path where the image file is copied.
        :rtype: str
        
        This function creates a destination directory for the project if it does not exist,
        and then copies the image file from the given path to the destination directory.
        The destination path where the image file is copied is returned.
        
        Example:
            >>> import_image_file('/path/to/image.jpg', 'my_project')
            './projects/my_project/images/12345678-1234-1234-1234-1234567890ab'
        """
        destination = './projects/'+project_name+'/images/'+str(uuid.uuid4())
        
        if not os.path.exists(destination):
            os.makedirs(destination,  exist_ok=True)

        copy(path, destination)
        return destination


    @handle_exception_with_messagebox()
    def save_opencv_image(project_name, image: np.array, subfolder=None, prefix=''):
        """
        Saves an OpenCV image to a specified project directory.

        :param project_name: The name of the project.
        :type project_name: str
        :param image: The image to be saved.
        :type image: np.array
        :return: The path where the image is saved.
        :rtype: str

        This function saves the given OpenCV image to the specified project directory. It creates the necessary directories if they do not exist.
        Example:
            >>> save_opencv_image('project1', image)
            './projects/project1/images/1234.png'
        """
        if subfolder:
            image_dir = './projects/'+project_name+'/images/'+subfolder+'/'
        else:
            image_dir = './projects/'+project_name+'/images/'

        path = image_dir + prefix + str(uuid.uuid4())+'.png'
        
        if not os.path.exists(image_dir):
            os.makedirs(image_dir,  exist_ok=True)
        
        cv2.imwrite(path,image)

        return path


    @handle_exception_with_messagebox()
    def save_svg_image(project_name, svg_string: str):
        """
        Saves an SVG image to a file.

        :param project_name: The name of the project.
        :type project_name: str
        :param svg_string: The SVG string to be saved.
        :type svg_string: str
        :return: The path of the saved file.
        :rtype: str
        
        This function saves the given SVG string to a file in the specified project's images directory.
        If the directory does not exist, it will be created.
        The file name is generated using a UUID to ensure uniqueness.
        The function returns the path of the saved file.
        
        Example:
            >>> save_svg_image('project1', '<svg>...</svg>')
            './projects/project1/images/12345678-1234-5678-1234-567812345678.svg'
        """
        path = './projects/'+project_name+'/images/'+str(uuid.uuid4())+'.svg'
        
        if not os.path.exists('./projects/'+project_name+'/images/'):
            os.makedirs('./projects/'+project_name+'/images/',  exist_ok=True)
        
        f = open(path, "w")
        f.write(svg_string)
        f.close()

        return path

    @handle_exception_with_messagebox()
    def open_opencv_image(path, cv_image_type):
        """
        Opens an image file using the OpenCV library. If the path is a directory, it reads all the images in the directory and returns a list of images.

        :param path: The path to the image file.
        :type path: str
        :return: The opened image or a list of opened images.
        :rtype: np.array or list[np.array]

        This function opens an image file using the OpenCV library. If the path is a directory, it reads all the images in the directory and returns a list of images.

        Example:
            >>> open_opencv_image('/path
            /to/image.jpg', cv2.IMREAD_COLOR)
            array([[[255, 255, 255], [255, 255, 255], ...], ...], dtype=uint8)
        """

        # If the path is also a directory, it reads all the images 
        # in the directory and returns a list of images.
        # If a list is returned, the list is sorted by last modified time
        filename = os.path.splitext(path)[0]
        if not os.path.isdir(filename):
            return cv2.imread(path,cv_image_type)
        
        list_of_files = [path]
        
        for file in os.listdir(filename):
            list_of_files.append(os.path.join(filename, file))
        # Sort the list of files by last modified time
        list_of_files.sort(key=lambda x: os.path.getmtime(x))
        # Sort the image list by the same order
        image_list = [cv2.imread(file, cv_image_type) for file in list_of_files]
        return image_list
    

    def delete(path):
        """
        Deletes a file at the specified path.

        :param path: The path of the file to be deleted.
        :type path: str
        :return: None
        :rtype: None
        """
        if path is None:
            return 
        try:
            os.remove(path)
        except Exception as e:
            logging.warning(f"Error deleting file {path}: {e}")

    @handle_exception_with_messagebox()
    def delete_directory(path):
        """
        Deletes a directory and all its contents.

        :param path: The path of the directory to be deleted.
        :type path: str
        :return: None
        :rtype: None

        This function deletes the directory specified by the given path. If the path is None, the function does nothing.
        """
        if path is None:
            return 
        shutil.rmtree(path)