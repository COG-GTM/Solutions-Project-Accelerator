try:
    from bin.logic_file_manager import Project_File_Manager
except:
    from logic_file_manager import Project_File_Manager
import os
import re
import openpyxl
import xlrd
import warnings
from PIL import Image

from bin.logic_pdf_render import page_count
from bin.logic_svg_safety import is_safe_svg


class Validators:

    @staticmethod
    def check_image(path):
        """ Check if it is an image. Static method """
        # noinspection PyBroadException
        try:  # try to open and close image with PIL
            Image.MAX_IMAGE_PIXELS = 1000000000  # suppress DecompressionBombError for big image
            with warnings.catch_warnings():  # suppress DecompressionBombWarning for big image
                warnings.simplefilter(u'ignore')
                img = Image.open(path)
            img.close()
        except:
            return False  # not image
        return True  # image


    @staticmethod
    def check_pdf(path):
        """ Check if it is a pdf. Static method """
        # noinspection PyBroadException
        try:  # validate with the same engine that renders the pages
            page_count(path)
        except:
            return False  # not pdf
        return True  # pdf
        
        

    @staticmethod
    def check_sheet(path):

        """ 
        Check if it is a Excel. Static method

        :param path: The path to the file.
        :type path: str

        :returns: True if the file is a valid Excel file, False otherwise.
        :rtype: bool

        This function checks if the given file at the specified path is a valid Excel file by attempting to open the file with the appropriate library.
        If the file can be opened successfully, the function returns True; otherwise, it returns False.
        """
        
        # noinspection PyBroadException
        try:  # try to open and close Excel
            wb = openpyxl.load_workbook(path)
            wb.close()
        except Exception as e:
            return False  # not Excel
        return True  # Excel
        
        
    @staticmethod
    def project_name_validator(name):
        """
        Check if the project name is valid. Static method.

        :param name: The project name to be checked.
        :type name: str

        :returns: True if the project name is valid, False otherwise.
        :rtype: bool

        This function checks if the given project name is valid by checking if the name is not empty.
        """
        
        if name == "":
            return True

        pattern = re.compile(r"^[\w. ]+$")
        if re.fullmatch(pattern, name):
            return True 
            
        return False


    @staticmethod
    def check_object_name_acm_valid(name: str):
        """
        Check if the object name is a valid ACM name. Static method.

        :param name: The object name to be checked.
        :type name: str
        :returns: True if the object name is valid, False otherwise.
        :rtype: bool

        This function checks if the given object name is valid by matching it against a regular expression pattern.
        A valid ACM name consists of only alphanumeric characters and underscores, and it must start with an alphabetic character.
        The name must not contain two consecutive underscores or end with an underscore. If the name matches the pattern, the function returns True; otherwise, it returns False.

        Example:
            >>> check_object_name_acm_valid('Object1')
            True
        """
        
        # Regex specialCharPattern = new Regex(@"^[a-zA-Z_]+[a-zA-Z0-9_]*$");
        # bool valid = specialCharPattern.IsMatch(value) && !value.Contains("__") && !value.EndsWith("_"); // Only one '_' allowed for separation

        pattern = re.compile(r"^[a-zA-Z_]+[a-zA-Z0-9_]*$")

        if re.fullmatch(pattern, name) and (not name.endswith('_')) and (not '__' in name):
            return True 
        return False


    @staticmethod
    def check_project_name_valid(name):
        """
        Check if project name is valid. Static method.

        :param name: The project name to be checked.
        :type name: str
        :returns: True if the project name is valid, False otherwise.
        :rtype: bool
        
        This function checks if the given project name is valid by checking if the name is not empty.
        """
        
        # noinspection PyBroadException
        if not name:
            return False
        return True


    @staticmethod
    def check_if_project_name_exists(name):
        """
        Check if a project name exists.
        :param name: The name of the project to check.
        :type name: str
        :returns: True if the project name exists, False otherwise.
        :rtype: bool

        This function checks if a project with the given name exists by checking if the name is in the list of all project names.

        Example:
            >>> check_if_project_name_exists('Project1')
            True
        """
        all_projects = Project_File_Manager.get_all_projects()
        all_project_names = [project.lower() for project in all_projects]
        if name.lower() in all_project_names:
            return True 
        return False

    @staticmethod
    def check_svg_or_png(path):
        """
        Checks if the given file at the specified path is a valid SVG or PNG file.
        :param path: The path to the file.
        :type path: str
        :returns: True if the file is a valid SVG or PNG file, False otherwise.
        :rtype: bool

        PNG files are opened with Pillow. SVG files must be well-formed, self-contained (no external
        references) and small enough to render; see ``bin.logic_svg_safety``.

        Example:
            >>> check_svg_or_png('image.svg')
            True
        """
        # noinspection PyBroadException
        _,extension = os.path.splitext(path)
        if extension.lower() == '.svg':
            # parsed and rendered offline with size limits; external references are rejected
            return is_safe_svg(path)
        else:
            try:  # try to open the image
                Image.open(path)
            except:
                return False  # not an image
        
        return True


    @staticmethod
    def check_image_or_pdf(path):
        """
        Checks if the given file at the specified path is a valid image or PDF file.

        :param path: The path to the file.
        :type path: str
        :returns: True if the file is a valid image or PDF file, False otherwise.
        :rtype: bool

        Example:
            >>> check_image_or_pdf('drawing.pdf')
            True
        """
        _,extension = os.path.splitext(path)
        if extension.lower() == '.pdf':
            return Validators.check_pdf(path)
        return Validators.check_image(path)


    @staticmethod
    def check_hex_rgb_color(string):
        """
        Check if a string represents a valid hexadecimal RGB color.
        :param string: The string to be checked.
        :type string: str
        :returns: True if the string represents a valid hexadecimal RGB color, False otherwise.
        :rtype: bool

        This function checks if the given string matches the pattern of a valid hexadecimal RGB color.
        A valid hexadecimal RGB color consists of either 3 or 6 characters, where each character is a digit (0-9)
        or a letter (a-f or A-F). If the string matches the pattern, the function returns True; otherwise, it returns False.
        """
        # noinspection PyBroadException
        match = re.findall(r'^(?:[0-9a-fA-F]{3}){1,2}$', string)
        
        return  len(match) > 0 


 
    @staticmethod
    def check_email(email):
        """
        Check if the given email address is valid.
        :param email: The email address to be checked.
        :type email: str
        :returns: True if the email is valid, False otherwise.
        :rtype: bool

        This function checks if the given email address is valid by matching it against a regular expression pattern.

        Example:
            >>> check_email('joe@example.com')
            True
        """
        regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        # pass the regular expression
        # and the string into the fullmatch() method
        if(re.fullmatch(regex, email)):
            return True
    
        else:
            return False


    