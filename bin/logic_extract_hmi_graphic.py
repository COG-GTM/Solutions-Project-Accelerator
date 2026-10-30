from typing import List, Optional
from bin.logic_config import Config
from threading import Thread
from uuid import uuid4
from svgpathtools import svg2paths2, Path, Line, is_path_segment, wsvg, parse_path
import cv2
import numpy as np
from svgpathtools import Document
from svgpathtools.paths2svg import disvg
from svgpathtools.svg_to_paths import svg2paths
import io
from PIL import Image
from lxml import etree
from bin.logic_file_manager import Project_File_Manager
from bin.logic_pdf_to_svg import page_to_svg
from bin.logic_svg_render import svg_bytes_to_png

from bin.logic_profile import profile

class extract_hmi_graphic:
    """
    The extract_hmi_graphic class is used to extract an HMI graphic from a PDF file.
    """

    def __init__(self, project_name, config:Config) -> None:
        """
        Initializes the extract_hmi_graphic object.

        :param project_name: The name of the project.
        :type project_name: str
        :param config: The configuration object.
        :type config: Config
        :return: None
        :rtype: None

        Initializes the extract_hmi_graphic object with the given project name and configuration object. Sets up the necessary attributes and variables for further processing.
        """
        self.__project_name = project_name
        self.__svg_page = None 
        self.__svg_paths = None
        self.__config = config
        self.__svg_attributes = None
        self.__image_papge = None
        self.__roi = None
        self.__poi = None
        self.__path = None 
        self.__pno = None 
        self.__display_image = None 
        self.__bbox_to_viewbox_ratio = [1,1] # ratio used to correct svg to dimensions 
        self.__hmi_svg_drawing = None
        self.__extract_roi_thread = None

        fill,stroke,width = config.get_extracted_hmi_graphic_settings()
        self.__stroke_color = stroke 
        self.__fill_color = fill 
        self.__stroke_width = width
        self.__strokes_in_roi = []
        self.__strokes_in_roi_attributes = []
        self.__fills_in_roi = []
        self.__svg_image_path = ''
        self.__extraction_started = False 
        self.__error_message = ''
        # Anchor points for connecting to other elements
        self.__top_anchors = []
        self.__bottom_anchors = []
        self.__left_anchors = []
        self.__right_anchors = []
        
    def initial_values(self, fill_color, stroke_color, stroke_width):
        """
        Set the initial values for fill color, stroke color, and stroke width.

        :param fill_color: The fill color to be set.
        :type fill_color: str
        :param stroke_color: The stroke color to be set.
        :type stroke_color: str
        :param stroke_width: The stroke width to be set.
        :type stroke_width: int
        
        :return: None
        :rtype: None

        This method sets the initial values for the fill color, stroke color, and stroke width
        of the object.

        Example:
            >>> initial_values('red', 'blue', 2)
            None
        """
        self.__fill_color = fill_color
        self.__stroke_color = stroke_color
        self.__stroke_width = stroke_width
        
    def set_fill_color(self, fill_color: str):
        """
        Sets the fill color of the HMI graphic.

        :param fill_color: The fill color to be set.
        :type fill_color: str
        
        :return: None
        :rtype: None

        This function sets the fill color of the HMI graphic and rebuilds the graphic.

        Example:
            >>> set_fill_color('red')
        """
        self.__fill_color = fill_color
        self.__rebuild_hmi_graphic()

    def set_stroke_color(self, stroke_color: str):
        """
        Sets the stroke color of the HMI graphic.

        :param stroke_color: The color to set as the stroke color.
        :type stroke_color: str

        :return: None
        :rtype: None

        This function sets the stroke color of the HMI graphic and rebuilds the graphic.

        Example:
            >>> set_stroke_color('red')
        """
        self.__stroke_color = stroke_color
        self.__rebuild_hmi_graphic()

    def set_stroke_width(self, stroke_width: str):
        """
        Sets the stroke width of the HMI graphic.

        :param stroke_width: The stroke width to be set.
        :type stroke_width: str

        :return: None
        :rtype: None

        This function sets the stroke width of the HMI graphic and rebuilds the graphic.
        """
        self.__stroke_width = stroke_width
        self.__rebuild_hmi_graphic()

    def get_fill_color(self):
        """
        Get the fill color of the graphic.

        :return: The fill color of the graphic.
        :rtype: str
        """
        return self.__fill_color

    def get_stroke_color(self):
        """
        Returns the stroke color of the graphic.

        :return: The stroke color.
        :rtype: str
        """
        return self.__stroke_color

    def get_stroke_width(self):
        """
        Returns the stroke width.

        :return: The stroke width.
        :rtype: int
        """
        return self.__stroke_width


    def set_roi(self, roi, poi, path, pno, text_locations):
        """
        Set the region of interest (ROI) for the graphic.

        :param roi: The region of interest.
        :type roi: <type of roi>
        :param poi: The point of interest.
        :type poi: <type of poi>
        :param path: The path of the graphic.
        :type path: <type of path>
        :param pno: The pno of the graphic.
        :type pno: <type of pno>
        :param text_locations: The locations of the text.
        :type text_locations: <type of text_locations>
        
        :return: None
        :rtype: None
        
        Set the region of interest (ROI) for the graphic. This function updates the ROI, path, pno, and text_locations attributes of the object.
        """
        self.__roi = roi
        self.__poi = poi
        self.__path = path 
        self.__pno = pno
        self.__text_locations = text_locations
        

    def get_display_image(self):
        return self.__display_image


    def get_hmi_graphic(self):
        """
        Retrieves the HMI graphic.
        :return: The HMI graphic as an Image object.
        :rtype: Image

        This function retrieves the HMI graphic by performing the following steps:
        1. Checks if there are any strokes in the region of interest (ROI). If not, returns None.
        2. Checks if there are any fills in the ROI and if there is no error message. If not, returns None.
        3. If the HMI SVG drawing is not already built, builds it.
        4. Converts the SVG drawing to PNG image data using cairosvg (external references blocked).
        5. Returns the image data as an Image object.
        
        Example:
            >>> get_hmi_graphic()
            <PIL.Image.Image image mode=RGB size=...>
        """

        if not self.__strokes_in_roi:
            return None

        if not self.__fills_in_roi and self.__error_message == '':
            return None

        if self.__hmi_svg_drawing is None :
            self.__build_hmi_graphic()

        image_data = svg_bytes_to_png(self.__hmi_svg_drawing.tostring())
        return Image.open(io.BytesIO(image_data))

       
    def get_error_message(self):
        """
        Get the error message.

        :return: The error message.
        :rtype: str
        """
        return self.__error_message


    def start_extraction(self):
        """
        Start the extraction process.

        :return: None
        :rtype: None

        This function starts the extraction process by performing pre-extraction checks and extracting the HMI graphic. It sets the `__extraction_started` flag to True to indicate that the extraction process has started.
        """
        if self.__extraction_started:
            raise OSError('Please wait. Busy extracting already.')
        try:
            self.__pre_extraction_checks()
        except ValueError as error:
            raise error
        self.__svg_page = page_to_svg(self.__path, self.__pno)
        
        svg_stringio = io.StringIO()
        # paste file content into it
        svg_stringio.write(self.__svg_page)
        # reset curser to its beginning
        svg_stringio.seek(0)
        doc = Document(svg_stringio)
        self.__svg_paths = doc.paths()
        
        xmin, ymin, xmax, ymax  = doc.root.attrib['viewBox'].split()
        viewBox_xmin = float(xmin)
        viewBox_xmax = float(xmax)
        viewBox_ymin = float(ymin)
        viewBox_ymax = float(ymax)
        bbox_xmin, bbox_xmax, bbox_ymin, bbox_ymax = self.__big_bounding_box(self.__svg_paths)
        self.__bbox_to_viewbox_ratio[0] = (bbox_xmax - bbox_xmin)/(viewBox_xmax - viewBox_xmin) 
        self.__bbox_to_viewbox_ratio[1] = (bbox_ymax - bbox_ymin)/(viewBox_ymax - viewBox_ymin) 
        self.__start_extract_roi_thread()
        self.__extraction_started = True
        
        


    def __pre_extraction_checks(self):
        """
        Perform pre-extraction checks before extracting the HMI graphic.

        :raises ValueError: If fill color, stroke color, stroke width, pno, path, or roi is not defined.
        """
        if not self.__fill_color:
            raise ValueError('Fill color not defined. Please input a valid hex color code.')

        if not self.__stroke_color:
            raise ValueError('Stroke color not defined. Please input a valid hex color code.')

        if not self.__stroke_width:
            raise ValueError('Stroke width not defined. Please input a valid width.')

        if self.__pno is None or not self.__path or not self.__roi:
            raise ValueError('Linked graphic not defined. Please define a linked graphic.')


    def __start_extract_roi_thread(self):
        """
        Starts a thread to extract ROI (Region of Interest) from an HMI (Human Machine Interface) graphic.

        :return: None
        :rtype: None

        This function starts a thread to extract the region of interest (ROI) from an HMI graphic. It creates a new thread and calls the __extract_roi function to extract the ROI from the SVG paths. The thread is started and the extraction process is initiated. The function returns None.
        """
        
        
        self.__hmi_svg_drawing = None
        self.__kill_extract_roi_thread = False

        if self.__extract_roi_thread != None:
            if self.__extract_roi_thread.is_alive():
                self.__kill_extract_roi_thread = False
                self.__extract_roi_thread.join()
                self.__kill_extract_roi_thread = True

        self.__extract_roi_thread = Thread(target=self.__extract_roi)
        self.__extract_roi_thread.start()





    def __extract_roi(self):
        """
        Extracts the region of interest (ROI) from the SVG paths and stores the strokes and fills within the ROI.
        :return: None
        :rtype: None

        This function extracts the region of interest (ROI) from the SVG paths and stores the strokes and fills within the ROI. It iterates through the SVG paths and checks if each path is contained within the ROI. If the path is contained within the ROI, it is added to the strokes_in_roi list. The attributes of the path are also extracted and stored in the strokes_in_roi_attributes list. The fills_in_roi list is populated with the fills within the ROI. The fills are added to the fills_in_roi list. The function then creates a background fill for the ROI and builds the HMI graphic by combining the fills and strokes in the ROI. The resulting SVG image is saved as a file.
        """
        self.__top_anchors = []
        self.__bottom_anchors = []
        self.__left_anchors = []
        self.__right_anchors = []
        
        roi_path = self.__points_to_svg_path(self.__roi)
        self.__strokes_in_roi = []
        self.__strokes_in_roi_attributes = []
        self.__fills_in_roi = []
        self.__fills_in_roi_attributes = []
        for path in self.__svg_paths:
            subpaths = path.continuous_subpaths()
            for subpath in subpaths:
                if self.__kill_extract_roi_thread:
                    break
                try:
                    if (subpath.start is not None and subpath.length() != 0 
                            and subpath.is_contained_by(roi_path)
                            and self.__is_not_in_text_locations(subpath)):
                        self.__strokes_in_roi.append(subpath)
                        dict_attributes = self.__extract_attributes(path)
                        self.__strokes_in_roi_attributes.append(dict_attributes)
                except Exception as error:
                    pass
        for index, point in enumerate(self.__poi):
            self.__create_anchor_points(point, index)
        self.__move_anchors_to_svg_outline()

        self.__create_background_fill()
        self.__build_hmi_graphic()


    def __is_not_in_text_locations(self,path):
        """
        Checks if the given path is not contained by any of the text locations.

        :param path: The path to check.
        :type path: Path
        :return: True if the path is not contained by any text location, False otherwise.
        :rtype: bool

        This function checks if the given path is not contained by any of the text locations. It iterates through the text locations and checks if the path is contained by any of the text regions. If the path is contained by any text region, the function returns False; otherwise, it returns True.
        """
        
        for _,text_location in self.__text_locations.items():
            roi_path = self.__points_to_svg_path(text_location['text_roi'])
            if path.is_contained_by( roi_path):
                return False
        return True
    

    def __extract_attributes(self, path):
        """
        Extracts attributes from the given path element.

        :param path: The path element to extract attributes from.
        :type path: Element
        :return: A dictionary containing the extracted attributes.
        :rtype: dict
        
        This function extracts attributes such as stroke width, stroke linecap, stroke linejoin, fill, and stroke from the given path element.
        If the stroke width is not specified, it defaults to "1.0".
        The fill color is set to "none" and the stroke color is set to "#AAAAAA".
        
        Example:
            >>> __extract_attributes(path)
            {'stroke-width': '1.0', 'stroke-linecap': 'round', 'stroke-linejoin': 'miter', 'fill': 'none', 'stroke': '#AAAAAA'}
        """
        dict_attributes = {}
        if 'stroke-width'in path.element.attrib:
            if 'transform' in path.element.attrib:
                stroke_width = self.__get_transformed_stroke_width(path.element.attrib['stroke-width'], path.element.attrib['transform'])
            else: 
                stroke_width = path.element.attrib['stroke-width']
            dict_attributes['stroke-width'] = stroke_width
        else:
            dict_attributes['stroke-width'] = "1.0"
        if 'stroke-linecap'in path.element.attrib:
            dict_attributes['stroke-linecap'] = path.element.attrib['stroke-linecap']
        if 'stroke-linejoin'in path.element.attrib:
            dict_attributes['stroke-linejoin'] = path.element.attrib['stroke-linejoin']
        
        dict_attributes['fill'] = "none" 
        dict_attributes['stroke'] = "#AAAAAA"
        
        return dict_attributes


    def __get_transformed_stroke_width(self, stroke_width, transform):
        """
        Get the transformed stroke width based on the given transform matrix.

        :param stroke_width: The original stroke width.
        :type stroke_width: float
        :param transform: The transform matrix.
        :type transform: str
        :return: The transformed stroke width.
        :rtype: str

        This function takes the original stroke width and the transform matrix as input.
        It extracts the values from the transform matrix and creates a transform matrix array.
        Then, it creates a coordinate array based on the stroke width.
        The function applies the transform matrix to the coordinate array and calculates the transformed stroke width.
        The absolute difference between the x-coordinates of the transformed stroke width is returned as a string.
        
        Example:
            >>> __get_transformed_stroke_width(2.5, 'matrix(1,0,0,1,0,0)')
            '0.0'
        """
        values = transform[transform.find("(")+1:transform.find(")")].split(",")

        transform_matrix = np.array([[float(values[0]),float(values[1])],[float(values[2]),float(values[3])]])

        coords = np.array([[0,0],[float(stroke_width),float(stroke_width)]])
        output = transform_matrix@coords
        return str(abs(output[0][0]-output[1][0]))
        

        
    def __rebuild_hmi_graphic(self):
        """
        Rebuilds the HMI graphic.

        :return: None
        :rtype: None
        """
        if self.__hmi_svg_drawing:
            self.__build_hmi_graphic()
            


    def __build_hmi_graphic(self):
        """
        Builds the HMI graphic by combining the fills and strokes in the region of interest.

        :return: None
        :rtype: None

        This function builds the HMI graphic by combining the fills and strokes in the region of interest. It creates a background fill for the ROI and adds the fills and strokes to the HMI graphic. The fills are added first, followed by the strokes. The resulting SVG image is saved as a file.
        """
        paths = []
        path_attributes = []
        for background in self.__fills_in_roi:
            paths.append(background)
            dict_attributes = {}
            dict_attributes['stroke-width'] = "none"
            dict_attributes['fill'] = "#" + self.__fill_color 
            dict_attributes['stroke'] = "none"
            path_attributes.append(dict_attributes)

        for i in range(len(self.__strokes_in_roi)):
            stroke = self.__strokes_in_roi[i]
            stroke_attributes = self.__strokes_in_roi_attributes[i]
            paths.append(stroke)
            dict_attributes = {}
            dict_attributes['stroke-width'] = self.__stroke_width
            dict_attributes['fill'] = "none"
            if 'stroke-linecap'in stroke_attributes:
                dict_attributes['stroke-linecap'] = stroke_attributes['stroke-linecap']
            if 'stroke-linejoin'in stroke_attributes:
                dict_attributes['stroke-linejoin'] = stroke_attributes['stroke-linejoin']
            dict_attributes['stroke'] = "#" + self.__stroke_color
            path_attributes.append(dict_attributes)


        self.__hmi_svg_drawing = disvg(paths, attributes = path_attributes , paths2Drawing=True)
        self.__extraction_started = False
        self.__save_graphic()
    

    def __create_background_fill(self):
        """
        Creates a background fill for the given region of interest (ROI).
        
        :return: None
        :rtype: None

        This function creates a background fill for the given region of interest (ROI). It uses the strokes_in_roi list to determine the boundary of the ROI and creates a fill for the area enclosed by the boundary. The fill is added to the fills_in_roi list.
        """
        
        self.__roi_paths_drawing = disvg(self.__strokes_in_roi, attributes = self.__strokes_in_roi_attributes , paths2Drawing=True)

        
        doc = etree.fromstring(self.__roi_paths_drawing.tostring())
        
        xmin, ymin, viewbox_width, viewbox_height = doc.attrib['viewBox'].split(' ')

        image_data = svg_bytes_to_png(self.__roi_paths_drawing.tostring())
        
        image = Image.open(io.BytesIO(image_data))
        
        
        img = np.array(image)

        bbox_height = image.height
        bbox_width = image.width
        img= cv2.cvtColor(img,cv2.COLOR_RGBA2RGB)
        mask = np.zeros((img.shape[0] + 2,img.shape[1] + 2), np.uint8)
        cv2.floodFill(img, mask, (0, 0), (255, 255, 255))
        
        mask = mask[1:-1,1:-1]
        
        mask = mask * 255
        mask = cv2.bitwise_not(mask)
        contours, hierarchy = cv2.findContours(mask,cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)

        debug = False 

        if debug:
            cv2.drawContours(img, contours, -1, (0, 255, 0), 3)
            cv2.imshow('Contours', img)
            cv2.waitKey(0)

        if not contours:
            self.__error_message = 'No closed contour found. Fill not applied'
            return
        else:
            self.__error_message = ''
        
        # Get the contours in the highest level of hierarchy
        contours = [contour for contour, h in zip(contours, hierarchy[0]) if h[3] == -1]

        
        # Scale the contours to fit the bounding box and draw the background fill
        for contour in contours:
            path = self.__contour_to_svg_path(contour,float(xmin),float(ymin), bbox_width/float(viewbox_width), bbox_height/float(viewbox_height))
            self.__fills_in_roi.insert(0,path)
            dict_attributes = {}
            dict_attributes['stroke-width'] = "1.0"
            dict_attributes['fill'] = "#CCCCCC" 
            dict_attributes['stroke'] = "none"
            self.__fills_in_roi_attributes.insert(0,dict_attributes)


    def __rect_to_pathd(ix0, iy0, ix1, iy1):
        """Converts an SVG-rect element to a Path d-string.
        
        The rectangle will start at the (x,y) coordinate specified by the 
        rectangle object and proceed counter-clockwise."""
        x0, y0 = float(ix0), float(iy0)
        w, h =  abs(float(ix1) - x0), abs(float(iy1) - y0)
        x1, y1 = x0 + w, y0
        x2, y2 = x0 + w, y0 + h
        x3, y3 = x0, y0 + h

        d = ("M{} {} L {} {} L {} {} L {} {} z"
            "".format(x0, y0, x1, y1, x2, y2, x3, y3))
        return d


    def __big_bounding_box(self,paths_n_stuff):
        """
        Calculate the bounding box of a list of paths and complex objects.

        :param paths_n_stuff: A list of paths and complex objects.
        :type paths_n_stuff: list
        :return: The minimum and maximum x and y values of the bounding box.
        :rtype: tuple

        This function calculates the bounding box of a list of paths and complex objects. It iterates through the list and checks the type of each element. If the element is a path segment or a Path object, it tries to retrieve the bounding box using the `bbox()` method. If the element is a complex number, it adds a bounding box with the real and imaginary parts as the minimum and maximum values. If the element is neither a path segment, a Path object, nor a complex number, it raises a TypeError.
        Example:
            >>> __big_bounding_box([Path(), complex(1, 2)])
            (0, 1, 2, 2)
        """
        bbs = []
        for thing in paths_n_stuff:
            if is_path_segment(thing) or isinstance(thing, Path):
                try:
                    bbs.append(thing.bbox())
                except ValueError:
                    ()
            elif isinstance(thing, complex):
                bbs.append((thing.real, thing.real, thing.imag, thing.imag))
            else:
                try:
                    complexthing = complex(thing)
                    bbs.append((complexthing.real, complexthing.real,
                                complexthing.imag, complexthing.imag))
                except ValueError:
                    raise TypeError("paths_n_stuff can only contains Path, "
                                    "CubicBezier, QuadraticBezier, Line, "
                                    "and complex objects.")
        xmins, xmaxs, ymins, ymaxs = list(zip(*bbs))
        xmin = min(xmins)
        xmax = max(xmaxs)
        ymin = min(ymins)
        ymax = max(ymaxs)
        return xmin, xmax, ymin, ymax

    
    def __points_to_svg_path(self, points):
        """
        Convert a list of points to an SVG path string.

        :param points: List of points in the format [(x1, y1), (x2, y2), ...]
        :type points: list[tuple[float, float]]
        :return: SVG path string
        :rtype: parse_path.Path

        This function takes a list of points and converts them into an SVG path string. Each point in the list should be a tuple of two floats representing the x and y coordinates. The resulting SVG path string can be used to draw a path in an SVG image.
        
        Example:
            >>> __points_to_svg_path([(0, 0), (1, 1), (2, 2)])
            <parse_path.Path object at 0x7f9e3a1e4a90>
        """
     
     
        path = "M"
        for i in range(len(points) - 1):
            x = float(points[i][0])  
            y = float(points[i][1]) 
            path = path + str(x)+ ' ' + str(y)+' L '
            
        # Close path
        x = float(points[-1][0]) 
        y = float(points[-1][1])
        path = path + str(x)+ ' ' + str(y)+' z'
        
        return parse_path(path)



    def __contour_to_svg_path(self, contour,xmin,ymin, width_ratio, height_ratio):
        """
        Converts a contour to an SVG path.

        :param contour: The contour to convert.
        :type contour: list of tuples
        :param xmin: The minimum x-coordinate value.
        :type xmin: float
        :param ymin: The minimum y-coordinate value.
        :type ymin: float
        :param width_ratio: The ratio to scale the x-coordinates.
        :type width_ratio: float
        :param height_ratio: The ratio to scale the y-coordinates.
        :type height_ratio: float
        :return: The SVG path representation of the contour.
        :rtype: svg.path.Path
        
        Converts a contour, represented as a list of tuples, to an SVG path. The x and y coordinates of each point in the contour are scaled and translated based on the provided xmin, ymin, width_ratio, and height_ratio values. The resulting SVG path is returned.
        
        Example:
            >>> __contour_to_svg_path([(0, 0), (1, 1), (2, 2)], 0, 0, 1, 1)
            <svg.path.Path object at 0x7f9d0a7c6a90>
        """
     
        path = "M"
        for i in range(len(contour)):
            x, y = contour[i][0]
            path = path + str(x / width_ratio + xmin)+ ' ' + str(y / height_ratio + ymin) +' '
            
        #Close path
        x, y = contour[0][0]
        path = path + str(x / width_ratio + xmin)+ ' ' + str(y / height_ratio + ymin)+' '
        
        return parse_path(path)


    def get_data(self):
        """
        Returns a dictionary containing the stroke color, stroke width, fill color, and SVG image path.
        :return: A dictionary with the following keys:
                 - 'stroke_color': The stroke color of the graphic.
                 - 'stroke_width': The stroke width of the graphic.
                 - 'fill_color': The fill color of the graphic.
                 - 'svg_image_path': The file path of the SVG image.
        :rtype: dict

        This function returns a dictionary containing the stroke color, stroke width, fill color, and SVG image path of the object.
        """

        dict_data = {
            'stroke_color': self.__stroke_color,
            'stroke_width': self.__stroke_width,
            'fill_color': self.__fill_color,
            'svg_image_path': self.__svg_image_path,
            'top_anchors': self.__top_anchors,
            'bottom_anchors': self.__bottom_anchors,
            'left_anchors': self.__left_anchors,
            'right_anchors': self.__right_anchors
        }

        return dict_data


    def set_data(self, data):
        """
        Set the data for the object.
        :param data: A dictionary containing the data for the object.
                     It should have the following keys:
                     - 'stroke_color': The color of the stroke.
                     - 'stroke_width': The width of the stroke.
                     - 'fill_color': The color to fill the object.
                     - 'svg_image_path': The path to the SVG image file.
        :type data: dict
        :return: None
        :rtype: None

        This function sets the data for the object using the data provided in the `data` dictionary.
        """

        if not data:
            return 

        self.__stroke_color = data['stroke_color']
        self.__stroke_width = data['stroke_width']
        self.__fill_color = data['fill_color']
        self.__svg_image_path = data['svg_image_path']

        if 'top_anchors' in data:
            self.__top_anchors = self.__normalize_anchor_indexes(data['top_anchors'], 'top')
        if 'bottom_anchors' in data:
            self.__bottom_anchors = self.__normalize_anchor_indexes(data['bottom_anchors'], 'bottom')
        if 'left_anchors' in data:
            self.__left_anchors = self.__normalize_anchor_indexes(data['left_anchors'], 'left')
        if 'right_anchors' in data:
            self.__right_anchors = self.__normalize_anchor_indexes(data['right_anchors'], 'right')

        self.__open_svg_image_path(self.__svg_image_path)


    @staticmethod
    def __normalize_anchor_indexes(anchors, direction):
        """Backfill missing 'index' / 'direction' keys on persisted anchor dicts."""
        if not anchors:
            return anchors or []
        normalized = []
        for i, anc in enumerate(anchors):
            if not isinstance(anc, dict):
                normalized.append(anc)
                continue
            if 'index' not in anc:
                anc = {**anc, 'index': i}
            if 'direction' not in anc:
                anc = {**anc, 'direction': direction}
            normalized.append(anc)
        return normalized


    def __open_svg_image_path(self, svg_image_path):
        """
        Opens an SVG image file and extracts the paths and attributes.

        :param svg_image_path: The path to the SVG image file.
        :type svg_image_path: str
        :return: None
        :rtype: None

        This function opens an SVG image file specified by `svg_image_path` and extracts the paths and attributes. It populates the `__fills_in_roi` and `__strokes_in_roi` lists with the paths, and `__strokes_in_roi_attributes` with the corresponding attributes.
        
        Example:
            >>> __open_svg_image_path('/path/to/image.svg')
        """
        if not svg_image_path:
            return 
        paths, attributes, _ = svg2paths2(svg_image_path)

        for i in range(len(paths)):
            if attributes[i]['stroke'] == 'none':
                self.__fills_in_roi.insert(0,paths[i])
            else:
                self.__strokes_in_roi.append(paths[i])
                self.__strokes_in_roi_attributes.append(attributes[i])




    def export_graphic(self,filename):
        """
        Export the HMI graphic as an SVG file.

        :param filename: The name of the file to save the SVG graphic.
        :type filename: str

        :return: None
        :rtype: None

        This function saves the HMI graphic as an SVG file with the given filename.

        Example:
            >>> export_graphic('graphic')
        """
        self.__hmi_svg_drawing.saveas(filename + '.svg')


    def __save_graphic(self):
        """
        Saves the HMI graphic as an SVG image.

        :return: The path of the saved SVG image.
        :rtype: str
        """
        svg_string = self.__hmi_svg_drawing.tostring()
        self.__svg_image_path = Project_File_Manager.save_svg_image(self.__project_name,svg_string)
        

    def __scale_contour(self,cnt, scale):
        M = cv2.moments(cnt)
        cx = int(M['m10']/M['m00'])
        cy = int(M['m01']/M['m00'])

        cnt_norm = cnt - [cx, cy]
        cnt_scaled = cnt_norm * scale
        cnt_scaled = cnt_scaled + [cx, cy]
        cnt_scaled = cnt_scaled.astype(np.int32)

        return cnt_scaled


    def __path_is_contained_in_path(self,path1:Path, path2:Path):
        """ Determine if svg path1 is in svg path2"""
        if path1.start is None:
            return False
        assert path2.isclosed()  # This question isn't well-defined otherwise
        if path2.intersect(path1,True):
            return False
        # find a point that's definitely outside path2
        xmin, xmax, ymin, ymax = path2.bbox()
        B = (xmin + 1) + 1j*(ymax + 1)
        
        
        A = path1.start  # pick an arbitrary point in path1
        
        AB_line = Path(Line(A, B))
        number_of_intersections = len(AB_line.intersect(path2))
        if number_of_intersections % 2:  # if number of intersections is odd
            return True
        else:
            return False
        

    def __move_anchors_to_svg_outline(self):
        """
        Move anchor points to the closest intersection with the SVG outline.
        
        :return: None
        :rtype: None

        This function moves the anchor points to the closest intersection with the SVG outline. It iterates through the anchor points and finds the closest intersection point along a ray from each anchor point in the specified direction. The anchor points are updated with the new coordinates.
        """

        direction_dict = {
            'top': complex(0, 1),
            'bottom': complex(0, -1),
            'left': complex(1, 0),
            'right': complex(-1, 0)
        }

        for anchors in [self.__top_anchors, self.__bottom_anchors, self.__left_anchors, self.__right_anchors]:
            for anchor in anchors:
                point = complex(anchor['x'], anchor['y'])
                direction = direction_dict.get(anchor['direction'])
                closest_intersection = self.find_closest_intersection(point, direction, self.__strokes_in_roi)
                if closest_intersection:
                    anchor['x'] = closest_intersection.real
                    anchor['y'] = closest_intersection.imag

        print("Top anchors:", self.__top_anchors)
        print("Bottom anchors:", self.__bottom_anchors)
        print("Left anchors:", self.__left_anchors)
        print("Right anchors:", self.__right_anchors)
        return


        

    def find_closest_intersection(self, point: complex, direction: complex, paths: List[Path], 
                            max_distance: float = 1000) -> Optional[complex]:
        """
        Find the closest intersection point along a ray from the given point.
        
        Args:
            point: Starting point as complex number
            direction: Direction vector as complex number (should be normalized)
            paths: List of SVG paths to check intersections with
            max_distance: Maximum distance to search for intersections
        
        Returns:
            Closest intersection point as complex number, or None if no intersection found
        """
        # Create a ray as a line segment
        ray_end = point + direction * max_distance
        ray = Line(point, ray_end)
        
        closest_intersection = None
        min_distance = float('inf')
        
        for path in paths:
            try:
                # Find intersections between the ray and each path
                intersections = path.intersect(ray)
                
                for (T1, seg1, t1), (T2, seg2, t2) in intersections:
                    
                    intersection_point = path.point(T1)
                    
                    # Calculate distance from original point
                    distance = abs(intersection_point - point)
                    
                    # Check if this intersection is in the correct direction
                    # (dot product should be positive)
                    to_intersection = intersection_point - point
                    if to_intersection != 0:  # Avoid division by zero
                        dot_product = (to_intersection * direction.conjugate()).real
                        if dot_product > 0 and distance < min_distance:
                            min_distance = distance
                            closest_intersection = intersection_point
                            
            except Exception as e:
                # Some paths might not support intersection calculation
                continue
        
        return closest_intersection
        

    def __create_anchor_points(self, point, index):
        """
        Create anchor points from intersection points between SVG paths and ROI boundary.
        
        
        :param point: The point of interest
        :type point: list[int, int]
        :param index: The index of the point in the list of points of interest
        :type index: int
        :return: None

        This function analyzes intersection points between SVG paths and the ROI boundary
        and creates anchor points at those locations. Each anchor point stores the coordinates
        and direction (top, bottom, left, right) based on which edge of the ROI it is closest to.
        The function also tracks the actual path segment data to ensure anchors connect to
        the visual outline of the graphic.
        """
         
        # Get ROI bounds
        roi_points = self.__roi
        roi_xmin = min(point[0] for point in roi_points)
        roi_xmax = max(point[0] for point in roi_points)
        roi_ymin = min(point[1] for point in roi_points)
        roi_ymax = max(point[1] for point in roi_points)
        roi_width = roi_xmax - roi_xmin
        roi_height = roi_ymax - roi_ymin
        
        
        x, y = point
        
        
        # Determine which edge of the ROI the point is closest to
        distances = {
            'top': abs(y - roi_ymin),
            'bottom': abs(y - roi_ymax),
            'left': abs(x - roi_xmin),
            'right': abs(x - roi_xmax)
        }
        
        # Find the direction with the smallest distance
        closest_direction = min(distances, key=distances.get)
        
        # Assign anchor based on the closest direction
        if closest_direction == 'top':
            self.__top_anchors.append({
                'x': x,
                'y': roi_ymin,  # Snap to exact edge
                'index': index,
                'direction': 'top'
            })
        elif closest_direction == 'bottom':
            self.__bottom_anchors.append({
                'x': x,
                'y': roi_ymax,  # Snap to exact edge
                'index': index,
                'direction': 'bottom'
            })
        elif closest_direction == 'left':
            self.__left_anchors.append({
                'x': roi_xmin,  # Snap to exact edge
                'y': y,
                'index': index,
                'direction': 'left'
            })
        elif closest_direction == 'right':
            self.__right_anchors.append({
                'x': roi_xmax,  # Snap to exact edge
                'y': y,
                'index': index,
                'direction': 'right'
            })

    def get_anchors(self):
        """
        Returns all anchors detected in the HMI graphic.
        
        :return: Dictionary containing top, bottom, left, and right anchors
        :rtype: dict
        """
        return {
            'top': self.__top_anchors,
            'bottom': self.__bottom_anchors,
            'left': self.__left_anchors,
            'right': self.__right_anchors
        }
    
    def generate_process_element_from_svg(self, x, y, width, height, id, name, font):
        """
        Generate a ProcessControlStaticGraphicElement from the extracted SVG.
        
        :param x: X-coordinate for the element
        :type x: int
        :param y: Y-coordinate for the element
        :type y: int
        :param width: Width of the element
        :type width: int
        :param height: Height of the element
        :type height: int
        :param id: Unique identifier for the element
        :type id: str
        :param name: Display name for the element
        :type name: str
        :param font: Font to use for text
        :type font: Font object
        
        :return: A new ProcessControlStaticGraphicElement with anchors
        :rtype: ProcessControlStaticGraphicElement
        """
        from gui_process_diagrams import ProcessControlStaticGraphicElement
        
        # Get all anchors that have been detected
        anchors = self.get_anchors()
        
        # Create the SVG string if not already available
        if not hasattr(self, 'svg_string') or not self.svg_string:
            self.svg_string = self.__generate_svg_string()
            
        # Create the ProcessControlStaticGraphicElement with the extracted SVG and anchors
        element = ProcessControlStaticGraphicElement(
            x=x,
            y=y,
            width=width, 
            height=height,
            id=id,
            name=name,
            font=font,
            top_anchors=anchors['top'],
            bottom_anchors=anchors['bottom'],
            left_anchors=anchors['left'],
            right_anchors=anchors['right'],
            svg_string=self.svg_string
        )
        
        return element
        
    def __generate_svg_string(self):
        """
        Generate an SVG string from the extracted paths.
        
        :return: SVG markup as a string
        :rtype: str
        """
        # Create an SVG string from the extracted strokes
        svg_width = self.__roi[2][0] - self.__roi[0][0]
        svg_height = self.__roi[2][1] - self.__roi[0][1]
        
        # Start SVG with viewBox attribute
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width} {svg_height}">\n'
        
        # Add all paths that were found in the ROI
        for i, path in enumerate(self.__strokes_in_roi):
            path_d = self.__get_path_d_attribute(path)
            attributes = self.__strokes_in_roi_attributes[i] if i < len(self.__strokes_in_roi_attributes) else {}
            
            # Get style attributes or use defaults
            stroke = attributes.get('stroke', self.__stroke_color)
            fill = attributes.get('fill', 'none')  # Default to no fill for lines
            stroke_width = attributes.get('stroke-width', self.__stroke_width)
            
            # Add the path to the SVG
            svg += f'  <path d="{path_d}" stroke="{stroke}" fill="{fill}" stroke-width="{stroke_width}" />\n'
        
        # Add fills if any
        for fill_path in self.__fills_in_roi:
            path_d = self.__get_path_d_attribute(fill_path)
            svg += f'  <path d="{path_d}" stroke="none" fill="{self.__fill_color}" />\n'
            
        # Close SVG
        svg += '</svg>'
        
        return svg
        
    def __get_path_d_attribute(self, path):
        """
        Convert a path object to SVG path d attribute string.
        
        :param path: Path object to convert
        :type path: path object
        
        :return: SVG path d attribute string
        :rtype: str
        """
        d = ""
        try:
            # Extract path segments
            segments = self.__get_path_segments(path)
            
            for i, segment in enumerate(segments):
                if i == 0:
                    # First segment starts with M (move to)
                    d += f"M{segment[0]},{segment[1]} "
                else:
                    # Subsequent segments use L (line to)
                    d += f"L{segment[0]},{segment[1]} "
            
            # Close the path if it forms a closed loop
            if path.is_closed:
                d += "Z"
                
        except Exception as e:
            print(f"Error creating path d attribute: {str(e)}")
            
        return d
        
    def __get_path_segments(self, path):
        """
        Extract line segments from a path.
        
        :param path: Path object to process
        :type path: path object
        
        :return: List of point coordinates
        :rtype: list
        """
        segments = []
        
        # Get the start point
        if path.start is not None:
            start_x, start_y = path.start.real, path.start.imag
            segments.append((start_x, start_y))
        
        # Process each segment of the path
        for segment in path:
            # Get end point of segment
            end_x, end_y = segment.end.real, segment.end.imag
            segments.append((end_x, end_y))
            
        return segments


if __name__ == '__main__':

    extract_hmi_graphic = extract_hmi_graphic()

    #extract_hmi_graphic.set_svg_page('./data/Output.svg')
    #create_graphic.set_roi(([0,0],[2383.94,0],[2383.94,1683.75],[0,1683.75]))
    #create_graphic.set_roi(([0,0],[1191.94,0],[1191.94,841.75],[0,841.75]))
    
    extract_hmi_graphic.set_roi(([848*0.74866478165252906063462142632736,240*0.74866478165252906063462142632736],
                            [1057*0.74866478165252906063462142632736,240*0.74866478165252906063462142632736],
                            [1057*0.74866478165252906063462142632736,365*0.74866478165252906063462142632736],
                            [848*0.74866478165252906063462142632736,365*0.74866478165252906063462142632736]))