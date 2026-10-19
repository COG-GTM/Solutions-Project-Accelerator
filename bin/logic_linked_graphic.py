

from concurrent.futures import thread
from copy import deepcopy
import logging
from math import ceil
import math
import os
from re import template
from threading import Thread
import traceback
import warnings
from typing import List
from tkinter import messagebox
from bin.gui_test_on_page import test_on_page
from shapely.geometry import Polygon
from bin.logic_config import Config

from bin.logic_file_manager import Project_File_Manager
from bin.logic_internal_database import Database
from bin.logic_linked_graphic_scanner import BOTTOM_TO_TOP, Template_Flip, Template_Rotate, find_text_dict_within_image_roi_with_ocr, get_ocr_page_image
from bin.logic_pdf_render import render_page
from bin.logic_scale_invariant_template_matching import scale_invariant_template_matching
try:
    from bin.logic_linked_graphic_scanner import linked_graphic_scanner, find_text_dict_within_roi_with_ocr, find_text_dict_within_roi, is_optimum_zoom_scale_for_ocr
    from bin.logic_linked_graphic_scanner import find_points_of_interest, search_poi_along_line
    from bin.gui_link_view import link_view
except:
    from logic_linked_graphic_scanner import linked_graphic_scanner, find_text_dict_within_roi_with_ocr, find_text_dict_within_roi, is_optimum_zoom_scale_for_ocr
    from bin.logic_linked_graphic_scanner import find_points_of_interest, search_poi_along_line
    from gui_link_view import link_view
    
from imutils.object_detection import non_max_suppression
import cv2
import numpy as np
import time
import uuid
from skimage.draw import line


class Linked_Graphic():
    """ 
    The Linked Graphic class used to link graphics in a document and run test on the page.
    """

    THRESHOLD = 0.70
    

    def __init__(self, name='', linked_callback=None, goto_callback=None,change_callback=None,
                    is_primary_linked_graphic:bool=False, result_callback=None, 
                    scanning_done_callback=None, object_type='', change_pdf_zoom_image_scale_callback=None, 
                    get_multi_graphic_func=None) -> None:
        """
        Initializes the linked graphic.

        :param name: The name of the linked graphic.
        :type name: str
        :param linked_callback: The linked callback function.
        :type linked_callback: function
        :param goto_callback: The goto callback function.
        :type goto_callback: function
        :param change_callback: The change callback function.
        :type change_callback: function
        :param is_primary_linked_graphic: Flag indicating whether the linked graphic is primary. Default is False.
        :type is_primary_linked_graphic: bool
        :param scanning_done_callback: The scanning done callback function.
        :type scanning_done_callback: function
        :param object_type: The object type.
        :type object_type: str
        :param change_pdf_zoom_image_scale_callback: The change PDF zoom image scale callback function.
        :type change_pdf_zoom_image_scale_callback: function

        Initializes the linked graphic. The function initializes the linked graphic by setting the name, linked callback
        function, goto callback function, change callback function, primary linked graphic flag, scanning done callback
        function, object type, and change PDF zoom image scale callback function.
        """
        self.__name = name
        self.__ocr_reader = None
        self.__uid = str(uuid.uuid4())
        self.__full_page_image = None
        self.__document_viewer_panel_pno = None
        self.__document_viewer_panel_path = None 
        self.__path = None 
        self.__pno = None 
        self.__roi = None 
        self.__roi_uid = None
        self.__minX = -1 # min x value based on the image
        self.__minY = -1 # min y value based on the image
        self.__maxX = -1
        self.__maxY = -1
        self.__text_location_dict = {}
        self.__text_location_name_to_roi_name_map = {}
        self.__target_image = None
        self.__display_image = None
        self.__display_image_path = None
        self.__template_image = None
        self.__template_image_path = None
        self.__template_mask = ...
        self.__template_mask_path = None
        self.__template_and_text_mask = ...
        self.__template_and_text_mask_path = None
        self.__template_image_width = 0 
        self.__template_image_height = 0
        self.__linking_callback_func = None
        self.__text_roi_doc_viewer_callback_func = None
        self.__linked_callback_func = linked_callback
        self.__goto_callback_func = goto_callback
        self.__change_callback = change_callback
        self.__text_locations_list_view = None
        self.__linking_enabled = False
        self.__linked = False
        self.__link_view = None
        self.__is_primary_linked_graphic = is_primary_linked_graphic
        self.__result_callback = result_callback
        self.__scanning_done_callback_funcs = [scanning_done_callback]
        self.__change_pdf_zoom_image_scale_callback = change_pdf_zoom_image_scale_callback
        self.__get_multi_graphic_func = get_multi_graphic_func
        self.__ocr_used = False
        self.__document_type = Database.DRAWING
        self.__current_doc_type = Database.DRAWING
        self.__points_of_interests = []
        self.__object_type = object_type
        self.__page_width = 0
        self.__page_height = 0 
        self.__pdf_zoom_scale = 2
        self.__default_zoom_scale = 2
        self.__get_full_page_image_callback_func = None
        self.__config: Config = None 

    def set_config(self,config):
        """
        Sets the configuration.

        :param config: The configuration.
        :type config: Config

        :returns: None
        :rtype: None
        """
        self.__config = config

    def ocr_used(self):
        """
        Returns whether OCR was used.

        :returns: True if OCR was used, False otherwise.
        :rtype: bool
        """
        return self.__ocr_used

    
    def set_project_name(self,project_name):
        """
        Sets the project name.

        :param project_name: The project name.
        :type project_name: str

        :returns: None
        :rtype: None

        Sets the project name. The function sets the project name.
        """
        self.__project_name = project_name


    def attach_location_text_list_view(self, list_view):
        """
        Attaches a text locations list view.

        :param list_view: The text locations list view to attach.
        :type list_view: link_view

        :returns: None
        :rtype: None

        Attaches a text locations list view. The function attaches a text locations list view by subscribing to the new link
        text location, goto link text location, and vertical direction toggle callbacks.
        """
        self.__text_locations_list_view = list_view
        self.__text_locations_list_view.subscribe_to_new_link_text_location(self.__text_location_link_callback)
        self.__text_locations_list_view.subscribe_to_goto_link_text_location(self.__text_location_goto_callback)
        self.__text_locations_list_view.subscribe_to_vertical_direction_toggle(self.__text_location_vertical_direction_toggle_callback)

    def __text_location_link_callback(self, linked, name_of_text_location, color):
        """
        Callback function for the text location link button.

        :param linked: Flag indicating whether the text location is linked.
        :type linked: bool
        :param name_of_text_location: The name of the text location.
        :type name_of_text_location: str
        :param color: The color.
        :type color: str

        :returns: None
        :rtype: None

        Callback function for the text location link button. The function links or unlinks the text location by calling the
        linking callback function with the PDF zoom scale. The function then creates a text reference and links or unlinks the
        text location to the text locations list view. The function also updates the text location name to ROI name map and sets
        the document viewer text locations.
        """
        if linked:
            # Remove text location 
            self.__remove_text_location(name_of_text_location)
        else:
            # Create a new text location
            self.__new_text_location( name_of_text_location, color)

        self.__change_callback()


    def __text_location_vertical_direction_toggle_callback(self, name_of_text_location, vertical_direction, color ):
        """
        Callback function for the vertical direction toggle button.

        :param name_of_text_location: The name of the text location.
        :type name_of_text_location: str
        :param vertical_direction: The vertical direction.
        :type vertical_direction: str
        :param color: The color.
        :type color: str

        :returns: None
        :rtype: None

        Callback function for the vertical direction toggle button. The function toggles the vertical direction of the text
        location by removing the text location and creating a new text location with the specified vertical direction and color.
        The function also updates the text locations list view and sets the document viewer text locations.
        """
        self.__recreate_text_location( name_of_text_location, vertical_direction, color)
        self.__change_callback()



    def __remove_all_text_locations(self):
        """
        Removes all text locations.

        :returns: None
        :rtype: None

        This function removes all text links from the text locations list view.
        """
        self.__text_locations_list_view.remove_all_links()


    def __new_text_location(self, name_of_text_location, color, vertical_direction=BOTTOM_TO_TOP):
        """
        Creates a new text location.

        :param name_of_text_location: The name of the text location.
        :type name_of_text_location: str
        :param color: The color.
        :type color: str
        :param vertical_direction: The vertical direction. Default is BOTTOM_TO_TOP.
        :type vertical_direction: str

        :returns: None
        :rtype: None

        Creates a new text location. The function creates a new text location by calling the linking callback function with the
        PDF zoom scale. The function then creates a text reference and links the text location to the text locations list view.
        The function also updates the text location name to ROI name map and sets the document viewer text locations.
        """
        
        roi_name, roi, pno, path, page_image, image, text_in_page = self.__linking_callback_func(self.__pdf_zoom_scale
                                                                                                 ,ocr_image=True
                                                                                                 )

        if roi_name is None:
            logging.warning(f"No region-of-interest selected for text location {name_of_text_location}")
            return

        vertical_direction = self.__create_text_reference(roi_name,roi,pno, path, image,text_in_page,color,vertical_direction)

        
        self.__text_locations_list_view.link_formed_for_text_location(name_of_text_location, vertical_direction)

        self.__text_location_name_to_roi_name_map[name_of_text_location]=roi_name

        self.set_document_viewer_text_locations()

    
    def __recreate_text_location(self, name_of_text_location, vertical_direction, color):
        """
        Recreates a text location.

        :param name_of_text_location: The name of the text location.
        :type name_of_text_location: str
        :param vertical_direction: The vertical direction.
        :type vertical_direction: str
        :param color: The color.
        :type color: str

        :returns: None
        :rtype: None

        Recreates a text location. The function recreates a text location by removing the text location and creating a new text
        location with the specified vertical direction and color. The function also updates the text locations list view and
        sets the document viewer text locations.
        """
        roi_name = self.__text_location_name_to_roi_name_map[name_of_text_location]
        roi = self.__text_location_dict[roi_name]['text_roi']
        pno = self.__text_location_dict[roi_name]['pno']
        _,_,_,_,_, image, text_in_page = self.__linking_callback_func(
                                                                    self.__pdf_zoom_scale,
                                                                    roi_name,
                                                                    pno,
                                                                    ocr_image=True
        )

        vertical_direction = self.__create_text_reference(roi_name,roi,pno, self.__path, image,text_in_page,color,vertical_direction)

        self.__text_locations_list_view.link_formed_for_text_location(name_of_text_location, vertical_direction)


        self.set_document_viewer_text_locations()



        
    def __text_location_goto_callback(self, text_location_name):
        """
        Callback function for the text location goto button.

        :param text_location_name: The name of the text location.
        :type text_location_name: str

        :returns: None
        :rtype: None

        Callback function for the text location goto button. The function calls the goto callback function with the region
        of interest (ROI) name, page number, and path.
        """
        roi_name =self.__text_location_name_to_roi_name_map[text_location_name]
        if self.__goto_callback_func:
            self.__goto_callback_func(roi_name,self.__pno,self.__path)


    def __find_text_dict_within_roi(self, minX, minY, maxX, maxY, text_in_page):
        """
        Finds the text dictionary within a region of interest (ROI).

        :param minX: The minimum x value.
        :type minX: int
        :param minY: The minimum y value.
        :type minY: int
        :param maxX: The maximum x value.
        :type maxX: int
        :param maxY: The maximum y value.
        :type maxY: int
        :param text_in_page: The text in the page.
        :type text_in_page: list

        :returns: The text dictionary within the region of interest.
        :rtype: list

        Finds the text dictionary within a region of interest (ROI). The function finds the text dictionary within a region of
        interest by checking if the text is within the region of interest. The function returns the text dictionary within the
        region of interest.
        """
        
        if not text_in_page:
            return []
        
        derotation_matrix = text_in_page[0]['derotation_matrix']
        rotation_matrix = text_in_page[0]['rotation_matrix']

        # Use the derotation matrix to transform the minX, minY, maxX, maxY coordinates
        minX, minY, maxX, maxY = self.transform_bbox((minX, minY, maxX, maxY), derotation_matrix)
        

        np_array_of_text = np.array([i['bbox'] for i in text_in_page])
        
        center_x = (np_array_of_text[:,:1].ravel()+np_array_of_text[:,2:3].ravel())/2
        center_y = (np_array_of_text[:,1:2].ravel()+np_array_of_text[:,3:].ravel())/2

        inidx = np.where(np.logical_and(np.logical_and(minX <= center_x, center_x <= maxX),np.logical_and(minY <= center_y, center_y <= maxY)))[0]

        text_in_region = [deepcopy(text_in_page[i]) for i in inidx]

        for text in text_in_region:
            text['bbox'] = self.transform_bbox(text['bbox'], rotation_matrix)

        return text_in_region
    

    def transform_bbox(self, bbox, matrix):
        """
        Transform a bounding box using a 2D transformation matrix.
        
        Args:
            bbox: Tuple of (x0, y0, x1, y1) representing the bounding box
            matrix: List [a, b, c, d, e, f] representing the transformation matrix
                [a, c, e]
                [b, d, f]
                [0, 0, 1]
        
        Returns:
            Transformed bounding box as (x0', y0', x1', y1')
        """
        # Extract parameters
        x0, y0, x1, y1 = bbox
        a, b, c, d, e, f = matrix
        
        # Create the full transformation matrix
        transform = np.array([
            [a, c, e],
            [b, d, f],
            [0, 0, 1]
        ])
        
        # Transform each corner of the bbox
        corners = [
            (x0, y0, 1),  # top-left
            (x1, y0, 1),  # top-right
            (x0, y1, 1),  # bottom-left
            (x1, y1, 1)   # bottom-right
        ]
        
        # Apply transformation to each corner
        transformed_corners = []
        for corner in corners:
            # Convert to column vector and multiply
            corner_vector = np.array(corner).reshape(3, 1)
            transformed = np.dot(transform, corner_vector)
            transformed_corners.append((transformed[0, 0], transformed[1, 0]))
        
        # Find the new bounding box that contains all transformed corners
        x_coords = [p[0] for p in transformed_corners]

        y_coords = [p[1] for p in transformed_corners]
        
        # The new bbox is the min/max of the transformed corners
        new_bbox = (
            min(x_coords),
            min(y_coords),
            max(x_coords),
            max(y_coords)
        )
        
        return new_bbox


    def __create_text_reference(self,roi_name, text_roi,pno, path, image, text_in_page,color='red',vertical_direction=BOTTOM_TO_TOP):
        """
        Creates a text reference.

        :param roi_name: The region of interest (ROI) name.
        :type roi_name: str
        :param text_roi: The text region of interest (ROI).
        :type text_roi: list
        :param pno: The page number.
        :type pno: int
        :param path: The path.
        :type path: str
        :param image: The image.
        :type image: numpy.ndarray
        :param text_in_page: The text in the page.
        :type text_in_page: list
        :param color: The color. Default is 'red'.
        :type color: str
        :param vertical_direction: The vertical direction. Default is BOTTOM_TO_TOP.
        :type vertical_direction: str

        :returns: None
        :rtype: None

        Creates a text reference. The function creates a text reference by creating a mask shape and mask for the text region
        of interest (ROI) and finding the text dictionary within the region of interest. The function then creates a text
        location dictionary and creates a template and text mask. The function also creates a display image.
        """
        minX = min(l[0] for l in text_roi)
        minY = min(l[1] for l in text_roi)

        minX_int = int(minX)
        minY_int = int(minY)
        maxX_int = int(max(l[0] for l in text_roi))
        maxY_int = int(max(l[1] for l in text_roi))

        is_horizontal = True

        raw_text_dict = self.__find_text_dict_within_roi(minX_int,minY_int,maxX_int,maxY_int, text_in_page)


        roi_image = np.array(image)
        
        mask_shape, mask = self.__create_mask(text_roi)

        
        if self.__document_type == Database.IMAGE:
        
            roi_image = cv2.cvtColor(roi_image, cv2.COLOR_RGB2BGR)

            ocr_text_dict, is_horizontal = find_text_dict_within_image_roi_with_ocr(roi_image
                                                                    ,text_roi
                                                                    ,1
                                                                    ,mask_shape
                                                                    ,extract_image = False
                                                                    ,vertical_direction=vertical_direction)
        else:
            _, black_and_white = cv2.threshold(cv2.cvtColor(roi_image,cv2.COLOR_RGB2GRAY)
                                                                    , 250
                                                                    , 255
                                                                    , cv2.THRESH_BINARY)
            if self.__is_optimum_pdf_zoom_scale_for_ocr(black_and_white):
                    
                roi_image = cv2.cvtColor(roi_image, cv2.COLOR_RGB2GRAY)

                ocr_text_dict, is_horizontal = find_text_dict_within_roi_with_ocr(roi_image
                                                                    ,text_roi
                                                                    ,self.__pdf_zoom_scale
                                                                    ,mask_shape
                                                                    ,extract_image = False
                                                                    ,vertical_direction=vertical_direction)
                

            else:
                return self.__change_pdf_zoom_scale_for_text(roi_name, 
                                                    text_roi,
                                                    pno, 
                                                    path, 
                                                    image, 
                                                    text_in_page,
                                                    color,
                                                    vertical_direction)

        
        if not ocr_text_dict or self.__have_common_chars(ocr_text_dict,raw_text_dict):
            text_dict = raw_text_dict
            self.__ocr_used = False
        else:
            text_dict = ocr_text_dict
            self.__ocr_used = True



        while text_dict and text_dict[0]['c'] == ' ':
            text_dict.pop(0)


        self.__text_location_dict[roi_name] = {
            'text_roi':text_roi,
            'text_dict': text_dict,
            'mask_shape': mask_shape,
            'pno': pno,
            'path': path,
            'color': color
        }

        
        if not is_horizontal:
            self.__text_location_dict[roi_name]['vertical_direction'] = vertical_direction
        else:
            vertical_direction = None

        self.__create_template_and_text_mask()
        self.__create_display_image()
        return vertical_direction
    

    def __have_common_chars(self, str1, str2):
        # Remove whitespace and convert to sets
        set1 = set(char['c'].lower() for char in str1 if not char['c'].isspace())
        set2 = set(char['c'].lower() for char in str2 if not char['c'].isspace())
        
        # Check if there's any intersection between the sets
        return bool(set1 & set2)
        


    def __is_optimum_pdf_zoom_scale_for_ocr(self, image):
        """
        Checks if the PDF zoom scale is optimum for OCR.

        :param image: The image to check.
        :type image: numpy.ndarray

        :returns: True if the PDF zoom scale is optimum for OCR, False otherwise.
        :rtype: bool

        Checks if the PDF zoom scale is optimum for OCR. The function checks if the PDF zoom scale is optimum for OCR by
        checking if the image is of minimum size. The function returns True if the PDF zoom scale is optimum for OCR, False
        otherwise.
        """
        is_optimim, zoom_scale = is_optimum_zoom_scale_for_ocr(image)
        self.__pdf_zoom_scale = self.__pdf_zoom_scale * zoom_scale
        return is_optimim
    

    def __optimum_image_scale_for_ocr(self, image):
        

        is_optimim, zoom_scale = is_optimum_zoom_scale_for_ocr(image)
        
        if not is_optimim:
            image = cv2.resize(image, (0,0), fx=zoom_scale, fy=zoom_scale)
        
        return image, zoom_scale

    
    __min_template_width_height = 50


    def __is_minimum_template_size(self, image):
        """
        Checks if the image is of minimum size.

        :param image: The image to check.
        :type image: numpy.ndarray

        :returns: True if the image is of minimum size, False otherwise.
        :rtype: bool

        Checks if the image is of minimum size. The function checks if the image is of minimum size by checking if the width
        or height of the image is less than the minimum template width and height. The function returns True if the image is of
        minimum size, False otherwise.
        """
        width = image.shape[1]
        height = image.shape[0]

        if width < height:
            optimum_zoom_scale = self.__pdf_zoom_scale * self.__min_template_width_height/width
        else:
            optimum_zoom_scale = self.__pdf_zoom_scale * self.__min_template_width_height/height

        # return if zoom scale is ok
        if self.__pdf_zoom_scale > optimum_zoom_scale:
            return True

        self.__pdf_zoom_scale = ceil(1.5 * optimum_zoom_scale)
        return False 
        

    def __change_pdf_zoom_scale_for_text(self, roi_name,roi,pno, path, image,text_in_page,color,vertical_direction=BOTTOM_TO_TOP):
        """
        Changes the PDF zoom scale for text.

        :param roi_name: The region of interest (ROI) name.
        :type roi_name: str
        :param roi: The region of interest (ROI).
        :type roi: list
        :param pno: The page number.
        :type pno: int
        :param path: The path.
        :type path: str
        :param image: The image.
        :type image: numpy.ndarray
        :param text_in_page: The text in the page.
        :type text_in_page: list
        :param color: The color.
        :type color: str

        :returns: None
        :rtype: None

        Changes the PDF zoom scale for text. The function changes the PDF zoom scale for text by creating a new template image
        and text mask and creating a display image.
        """
        self.__change_pdf_zoom_scale()


        _, _, _, _, _, image, _ = self.__linking_callback_func(self.__pdf_zoom_scale,ocr_image=True)

        if image is None:
            logging.warning(f"No image available for text location {roi_name} at zoom scale {self.__pdf_zoom_scale}")
            return vertical_direction

        return self.__create_text_reference(roi_name,roi,pno, path, image,text_in_page,color,vertical_direction)
        

    def __change_pdf_zoom_scale(self):
        """
        Changes the PDF zoom scale.

        :returns: None
        :rtype: None

        Changes the PDF zoom scale. The function changes the PDF zoom scale by creating a new template image and text mask
        and creating a display image.
        """
        if self.__linking_callback_func is None:
            return 

        _,_,_,_, full_image, image, _ = self.__linking_callback_func(self.__pdf_zoom_scale,
                                                                    self.__roi_uid,
                                                                    self.__pno)

        # The roi is unavailable when the viewer is showing a different document or page than the link was made on.
        if image is None or full_image is None:
            logging.warning(f"Cannot rescale graphic link: roi {self.__roi_uid} not available on page {self.__pno} of {self.__path}")
            return

        self.create_graphic_link(self.__roi,self.__pno,self.__path,full_image,image)



    def get_text_location_dict(self):
        return self.__text_location_dict


    def __create_mask(self, roi_points, is_text_mask=True):
        """
        Creates a mask.

        :param roi_points: The region of interest (ROI) points.
        :type roi_points: list
        :param is_text_mask: Flag indicating whether to create a text mask. Default is True.
        :type is_text_mask: bool

        :returns: The mask shape and the mask.
        :rtype: tuple

        The function creates a mask. The function creates a mask by creating a mask shape and then creating a mask from the
        mask shape. The function returns the mask shape and the mask.
        """
        mask_shape = []

        if self.__document_type == Database.DRAWING:
            zoom_scale = self.__pdf_zoom_scale
        elif self.__document_type == Database.IMAGE:
            zoom_scale = 1

        for point in roi_points:
            mask_shape.append((int(point[0]*zoom_scale) - self.__minX, 
                                int(point[1]*zoom_scale) - self.__minY))


        mask = self.__create_mask_from_mask_shape(is_text_mask, mask_shape)
        return mask_shape, mask



    def __create_mask_from_mask_shape(self, is_text_mask, mask_shape):
        """
        Creates a mask from a mask shape.

        :param is_text_mask: Flag indicating whether to create a text mask. Default is True.
        :type is_text_mask: bool
        :param mask_shape: The mask shape.
        :type mask_shape: list

        :returns: The mask.
        :rtype: numpy.ndarray

        The function creates a mask from a mask shape. The function returns the mask.
        """
        mask = np.zeros(self.__template_image.shape[:2], np.uint8)
        mask = cv2.fillPoly(mask, np.int32([np.array(mask_shape)]), (255))
        if is_text_mask: 
            mask = cv2.bitwise_not(mask)
        return mask



    def __remove_text_location(self, name_of_text_location):
        """
        Removes a text location.

        :param name_of_text_location: The name of the text location to remove.
        :type name_of_text_location: str

        :returns: None
        :rtype: None

        Removes a text location. The function removes a text location by removing the text location from the text location
        dictionary and the text location name to ROI name map. The function also creates a template and text mask and
        creates a display image.
        """
        self.__text_locations_list_view.link_removed_for_text_location(name_of_text_location)
        roi_name = self.__text_location_name_to_roi_name_map[name_of_text_location]
        self.__text_location_dict.pop(roi_name,None)
        self.__text_location_name_to_roi_name_map.pop(name_of_text_location,None)
        self.__create_template_and_text_mask()
        self.__create_display_image() 


    def get_text_references(self):
        return self.__text_location_dict, self.__text_location_name_to_roi_name_map

    
    def convert_hex_color_to_rgba_array(self, color):
        """
        Converts a hexadecimal color code to an RGBA array.

        :param color: The hexadecimal color code to convert.
        :type color: str

        :returns: The RGBA array representing the color.
        :rtype: tuple

        The function converts a hexadecimal color code to an RGBA array. The function returns the RGBA array.
        """

        return tuple(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + (100,)


    def __translate_points(self, old_start, new_start, points):
        """
        Translates points from one coordinate system to another.

        :param old_start: The starting point of the old coordinate system.
        :type old_start: tuple
        :param new_start: The starting point of the new coordinate system.
        :type new_start: tuple
        :param points: The points to be translated.
        :type points: list

        :returns: The translated points.
        :rtype: list

        The function translates points from one coordinate system to another. The function returns the translated points.
        """
        return [[point[0] - old_start[0] + new_start[0],point[1] - old_start[1] + new_start[1]] for point in points]


    def __rotate_point(self,point, angle, center_point=(0, 0)):
        """
        Rotates a point by a given angle around a center point.

        :param point: The point to be rotated.
        :type point: tuple
        :param angle: The angle of rotation in degrees.
        :type angle: float
        :param center_point: The center point of rotation. Defaults to (0, 0).
        :type center_point: tuple, optional

        :returns: The rotated point.
        :rtype: tuple

        The function rotates a point by a given angle around a center point. The function returns the rotated point.
        """
        angle_rad = math.radians(angle % 360)
        # Shift the point so that center_point becomes the origin
        new_point = (point[0] - center_point[0], point[1] - center_point[1])
        new_point = (new_point[0] * math.cos(angle_rad) - new_point[1] * math.sin(angle_rad),
                    new_point[0] * math.sin(angle_rad) + new_point[1] * math.cos(angle_rad))
        # Reverse the shifting we have done
        new_point = (new_point[0] + center_point[0], new_point[1] + center_point[1])
        return new_point


    def __rotate_polygon(self, polygon, angle, center_point=(0, 0)):
        """
        Rotates a polygon by a given angle around a center point.

        :param polygon: The polygon to be rotated.
        :type polygon: list of tuples
        :param angle: The angle of rotation in degrees.
        :type angle: float
        :param center_point: The center point of rotation. Defaults to (0, 0).
        :type center_point: tuple, optional

        :returns: The rotated polygon and the minimum x and y coordinates of the rotated polygon.
        :rtype: tuple

        The function rotates a polygon by a given angle around a center point. The function returns the rotated polygon 
        and the minimum x and y coordinates of the rotated polygon.
        """
        
        rotated_polygon = []
        for corner in polygon:
            rotated_corner = self.__rotate_point(corner, angle, center_point)
            rotated_polygon.append(rotated_corner)

        minX = min(l[0] for l in rotated_polygon) 
        minY = min(l[1] for l in rotated_polygon) 
        return rotated_polygon, [minX, minY]


    def __flip_polygon(self, polygon, horizontal_flip=True):
        """
        Flips a polygon horizontally or vertically.

        :param polygon: The polygon to be flipped.
        :type polygon: list of tuples
        :param horizontal_flip: Flag indicating whether to perform a horizontal flip. Default is True.
        :type horizontal_flip: bool

        :returns: The flipped polygon and the minimum x and y coordinates.
        :rtype: tuple

        The function flips a polygon horizontally or vertically. The function returns the flipped polygon and the minimum
        """
        np_polygon = np.array(polygon)
        

        if horizontal_flip:
            flipped_polygon = list(np_polygon.dot([[-1,0],[0,1]]))
        else:
            flipped_polygon = list(np_polygon.dot([[1,0],[0,-1]]))

        minX = min(l[0] for l in flipped_polygon) 
        minY = min(l[1] for l in flipped_polygon) 
        return flipped_polygon, [minX, minY]

        

    def set_full_page_image(self, image, pdf_zoom):
        """
        Set the full page image and the default zoom scale.

        :param image: The image to set as the full page image.
        :type image: numpy.ndarray
        :param pdf_zoom: The default zoom scale for the PDF.
        :type pdf_zoom: float

        :returns: None
        :rtype: None

        Set the full page image and the default zoom scale. The function sets the full page image and the default zoom scale
        for the PDF.
        """
        self.__default_zoom_scale = pdf_zoom
        

        self.__full_page_image = np.array(image)


    def create_graphic_link(self, roi, pno, path, full_page_image, image, mask=...,page_width=None,page_height=None):
        """
        Creates a graphic link.

        :param roi: The region of interest (ROI).
        :type roi: list
        :param pno: The page number.
        :type pno: int
        :param path: The path.
        :type path: str
        :param full_page_image: The full page image.
        :type full_page_image: numpy.ndarray
        :param image: The image.
        :type image: numpy.ndarray
        :param mask: The mask.
        :type mask: numpy.ndarray
        :param page_width: The page width.
        :type page_width: int
        :param page_height: The page height.
        :type page_height: int

        :returns: None
        :rtype: None

        Creates a graphic link. The function creates a graphic link by adding a border to the image. The function
        also creates a mask for the image.
        """
        img = np.array(image)
        full_page_image = np.array(full_page_image)

        # Convert BGR to RGB for 3 and 4 channel
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self.__full_page_image = cv2.cvtColor(full_page_image, cv2.COLOR_BGR2RGB)
        
        
        self.__roi = roi
        self.__pno = pno
        self.__path = path
        self.__document_type = self.__current_doc_type
        if not self.__is_minimum_template_size(img) and self.__document_type == Database.DRAWING:
            self.__change_pdf_zoom_scale()
            return 
        self.__page_width = int(self.__full_page_image.shape[1] * self.__pdf_zoom_scale/self.__default_zoom_scale)
        self.__page_height = int(self.__full_page_image.shape[0] * self.__pdf_zoom_scale/self.__default_zoom_scale)
        self.__create_template_image(img,self.__roi)
        self.__create_template_and_text_mask()
        self.__create_display_image()
        self.__points_of_interests = find_points_of_interest(self.__full_page_image, self.__roi, self.__document_type)


        self.__linked = True
        if self.__link_view:
            self.__link_view.link_formed()
            self.__link_view.enable_goto()
        self.__change_callback()


    
    

    def __search_poi_along_line(self, line):
        """
        Searches for points of interest along a line.

        :param line: The line.
        :type line: list

        :returns: The points of interest.
        :rtype: list

        Searches for points of interest along a line. The function searches for points of interest along a line by
        iterating through the line and checking for a change in pixel value. The function returns the points of interest.
        """
        _, image_to_search_black_and_white = cv2.threshold(cv2.cvtColor(self.__full_page_image,cv2.COLOR_RGB2GRAY), 240, 255, cv2.THRESH_BINARY)
        
        start = None
        points = []
        for i in range(len(line)):
            point = line[i]
            pixel = image_to_search_black_and_white[point[1]*2,point[0]*2]


            if i == 0:
                if pixel==0: start = line[i]
                previous_pixel = pixel
                continue

            
            if (pixel==0 and previous_pixel==255):
                start = line[i]

            elif (pixel==255 and previous_pixel==0):
                end = line[i - 1]
                points.append([int((start[0] + end[0])/2),int((start[1] + end[1])/2)])

            previous_pixel = pixel

        return points
            


    def __create_template_image(self, image, roi):
        """
        Creates a template image.

        :param image: The image.
        :type image: numpy.ndarray
        :param roi: The region of interest (ROI).
        :type roi: list

        :returns: None
        :rtype: None

        Creates a template image. The function creates a template image by adding a border to the image. The function
        also creates a mask for the template image.
        """
        if self.__document_type == Database.IMAGE:
            zoom_scale = 1
        else:
            zoom_scale = self.__pdf_zoom_scale


        self.__minX = int(min(l[0] for l in roi) * zoom_scale)
        self.__minY = int(min(l[1] for l in roi) * zoom_scale)
        self.__maxX = int(max(l[0] for l in roi) * zoom_scale)
        self.__maxY = int(max(l[1] for l in roi) * zoom_scale)

        

        self.__template_image_height = image.shape[0]
        self.__template_image_width = image.shape[1]


        self.__template_image = image

        
        Project_File_Manager.delete(self.__template_image_path)
                                         
        self.__template_image_path = Project_File_Manager.save_opencv_image(self.__project_name,
                                                                        self.__template_image)
        _, self.__template_mask = self.__create_mask(roi,is_text_mask=False)
        
        Project_File_Manager.delete(self.__template_mask_path)
        self.__template_mask_path = Project_File_Manager.save_opencv_image(self.__project_name,
                                                                self.__template_mask)


    def __create_template_and_text_mask(self):
        """
        Creates a template and text mask.

        :returns: None
        :rtype: None

        Creates a template and text mask. The function creates a mask by performing a bitwise AND operation on the template
        mask and text mask.
        """
        self.__template_and_text_mask = self.__template_mask
        
        for _, text_location in self.__text_location_dict.items():
            mask = self.__create_mask_from_mask_shape(True,text_location['mask_shape'])
            self.__template_and_text_mask = cv2.bitwise_and(mask ,self.__template_and_text_mask)
        
        Project_File_Manager.delete(self.__template_and_text_mask_path)
        self.__template_and_text_mask_path = Project_File_Manager.save_opencv_image(self.__project_name,
                                                                        self.__template_and_text_mask)


    def __create_display_image(self):
        """
        Creates a display image.

        :returns: None
        :rtype: None

        Creates a display image. The function creates a display image by adding a border to the template image.
        """
        r_channel, g_channel, b_channel = cv2.split(self.__template_image)[0:3]
        self.__display_image = cv2.merge((b_channel, g_channel, r_channel, self.__template_and_text_mask))
        
        
        for _, text_location in self.__text_location_dict.items():
            cv_color = self.convert_hex_color_to_rgba_array(text_location['color'])
            self.__display_image = cv2.fillPoly(self.__display_image, np.int32([np.array(text_location['mask_shape'])]), cv_color)

        self.__display_image = cv2.cvtColor(self.__display_image, cv2.COLOR_BGRA2RGBA)
        
        Project_File_Manager.delete(self.__display_image_path)
        self.__display_image_path = Project_File_Manager.save_opencv_image(self.__project_name,
                                                    self.__display_image)
        
        self.__linked_callback_func(self.__display_image)


    def __create_test_image(self, template_image):
        """
        Creates a test image.

        :param template_image: The template image.
        :type template_image: numpy.ndarray

        :returns: The test image.
        :rtype: numpy.ndarray

        Creates a test image. The function creates a test image by adding a border to the template image.
        """


        if isinstance(self.__template_and_text_mask, list): 
            selected_template_index = self.__get_multi_graphic_func()
            template_and_text_mask = self.__template_and_text_mask[selected_template_index]*255
        else: template_and_text_mask = self.__template_and_text_mask

        if self.__document_type == Database.DRAWING:
            b_channel, g_channel, r_channel = cv2.split(cv2.cvtColor(template_image,cv2.COLOR_GRAY2RGB))
        else:
            r_channel, g_channel, b_channel = cv2.split(template_image)
        # If template_and_text_mask is not the same size as the image, resize it
        if template_and_text_mask.shape[:2] != template_image.shape[:2]:
            template_and_text_mask = cv2.resize(template_and_text_mask, (template_image.shape[1], template_image.shape[0]), interpolation=cv2.INTER_NEAREST)
        
        # Merge the channels and the mask
        img = cv2.merge((b_channel, g_channel, r_channel, template_and_text_mask))


        for _, text_location in self.__text_location_dict.items():
            cv_color = self.convert_hex_color_to_rgba_array(text_location['color'])
            img = cv2.fillPoly(img, np.int32([np.array(text_location['mask_shape'])]), cv_color)
        
        return img


    def delete_images(self):
        """
        Deletes the images associated with the object.

        :returns: None
        :rtype: None

        Deletes the images associated with the object. The function deletes the template image, display image,
        template and text mask, and template mask.
        """
        Project_File_Manager.delete(self.__template_image_path)
        Project_File_Manager.delete(self.__display_image_path)
        Project_File_Manager.delete(self.__template_and_text_mask_path)
        Project_File_Manager.delete(self.__template_mask_path)


    def get_document_location(self):
        """
        Retrieves the document location.

        :returns: The document location.
        :rtype: tuple

        Retrieves the document location. The function returns a tuple containing the path and page number.
        """
        dict_data = {
            'path': self.__path,
            'pno': self.__pno,
            'roi': self.__roi,
            'roi_uid': self.__roi_uid,
        }

        if self.__document_type == Database.DRAWING:
            dict_data['document_type'] = Database.DRAWING
        elif self.__document_type == Database.IMAGE:
            dict_data['document_type'] = Database.IMAGE
        return dict_data


    def get_data(self):
        """
        Retrieves the data associated with the object.

        :returns: A dictionary containing the data.
        :rtype: dict

        Retrieves the data associated with the object. The function returns a dictionary containing 
        the path, page number, region of interest (ROI), ROI UID, minimum X-coordinate, minimum 
        Y-coordinate, maximum X-coordinate, and maximum Y-coordinate.
        """

        dict_data = {}

        if self.__template_image is None:
            return dict_data

        dict_data = {
                'path': self.__path,
                'pno': self.__pno,
                'roi': self.__roi,
                'roi_uid': self.__roi_uid,
                'minX': self.__minX,
                'minY': self.__minY,
                'maxX': self.__maxX,
                'maxY': self.__maxY,
                'text_location_dict': self.__text_location_dict,
                'text_location_name_to_roi_name_map': self.__text_location_name_to_roi_name_map,
                'display_image': self.__display_image_path,
                'template_image': self.__template_image_path,
                'template_mask': self.__template_mask_path,
                'template_and_text_mask': self.__template_and_text_mask_path,
                'template_image_width': self.__template_image_width,
                'template_image_height': self.__template_image_height,
                'ocr_used':self.__ocr_used,
                'points_of_interests':self.__points_of_interests,
                'page_width':self.__page_width,
                'page_height':self.__page_height,
                'pdf_zoom_scale': self.__pdf_zoom_scale,
                'flip':None,
                'rotation':None,
                'document_type':self.__document_type,
            }
     


        return dict_data



    def create_copy(self,path,pno:int,roi_bbox,text_locations,template_to_match_ratio,rotation=None,flip=None, create_new_points_of_interest=True):

        """
        Creates a copy of the object with updated parameters.

        :param pno: The page number.
        :type pno: int
        :param roi_bbox: The bounding box coordinates of the region of interest.
        :type roi_bbox: tuple
        :param text_locations: The text locations.
        :type text_locations: list
        :param template_to_match_ratio: The ratio of the template to match.
        :type template_to_match_ratio: float
        :param rotation: The rotation angle (optional).
        :type rotation: float, optional
        :param flip: The flip option (optional).
        :type flip: str, optional

        :returns: A dictionary containing the copied object's data and the mapping of old to new ROI names.
        :rtype: tuple(dict, dict)

        Creates a copy of the object with updated parameters. The function calculates the new ROI coordinates 
        based on the given bounding box, template ratio, rotation, and flip options. It also creates a new ROI 
        UID and updates the text location dictionary. The function returns a dictionary containing the copied 
        object's data and the mapping of old to new ROI names.
        """
        pass

        if self.__document_type == Database.DRAWING:
            old_start = ((self.__minX / self.__pdf_zoom_scale, self.__minY / self.__pdf_zoom_scale ))
        else:
            old_start = ((self.__minX, self.__minY))
        new_start = ((roi_bbox[0],roi_bbox[1]))

        roi = self.__scale_points(self.__roi, old_start,template_to_match_ratio)
        roi, old_start = self.__rotate_points(rotation,roi, old_start)
        roi, old_start = self.__flip_points(flip,roi, old_start)
        roi = self.__translate_points(old_start,new_start,roi)

        
            

        roi_uid = (str(pno) +'-'+ str(int(roi_bbox[0])) +'-'+ str(int(roi_bbox[1])) 
                    +'-'+ str(int(roi_bbox[2])) +'-'+ str(int(roi_bbox[3])) +'-'+ self.__object_type)

        (text_location_dict, text_location_name_to_roi_name_map, old_to_new_roi_names) = self.__create_text_location_dict_copy(pno
                                                                        ,roi_bbox
                                                                        ,text_locations
                                                                        ,template_to_match_ratio)

        if create_new_points_of_interest and self.__document_type == Database.DRAWING:

            if getattr(self, 'create_new_points_of_interest_key', None) != (path, pno):
                self.create_new_points_of_interest_key = (path, pno)
                self.create_new_points_of_interest_image = np.array(render_page(path, pno, zoom=2))
            
            points_of_interests = find_points_of_interest(self.create_new_points_of_interest_image, roi, self.__document_type)

        elif self.__points_of_interests:
            points_of_interests = self.__scale_points(self.__points_of_interests, old_start,template_to_match_ratio)
            points_of_interests, old_start = self.__rotate_points(rotation,points_of_interests, old_start)
            points_of_interests, old_start = self.__flip_points(flip,points_of_interests, old_start)
            points_of_interests = self.__translate_points(old_start,new_start,points_of_interests)
        else:
            points_of_interests = self.__points_of_interests

        if self.__document_type == Database.DRAWING:
            zoom_scale = self.__pdf_zoom_scale
        else:
            zoom_scale = 1


        dict_data = {
            'path': path,
            'pno':pno,
            'roi':roi,
            'roi_uid': roi_uid,
            'minX': roi_bbox[0] * zoom_scale,
            'minY': roi_bbox[1] * zoom_scale,
            'maxX': roi_bbox[2] * zoom_scale,
            'maxY': roi_bbox[3] * zoom_scale,
            'text_location_dict':text_location_dict,
            'text_location_name_to_roi_name_map':text_location_name_to_roi_name_map,
            'display_image': self.__display_image_path,
            'template_image': self.__template_image_path,
            'template_mask': self.__template_mask_path,
            'template_and_text_mask': self.__template_and_text_mask_path,
            'template_image_width': self.__template_image_width,
            'template_image_height': self.__template_image_height,
            'ocr_used':self.__ocr_used,
            'points_of_interests':points_of_interests,
            'page_width':self.__page_width,
            'page_height':self.__page_height,
            'pdf_zoom_scale': self.__pdf_zoom_scale,
            'flip':None,
            'rotation':None,
            'document_type':self.__document_type,
        }


        # Check if new linked graphic overlaps with existing linked graphic using the minx, miny, maxx, maxy
        new_roi = (dict_data['minX'], dict_data['minY'], dict_data['maxX'], dict_data['maxY'])
        existing_roi = (self.__minX, self.__minY, self.__maxX, self.__maxY)
        overlap = False
        if pno == self.__pno and self.__calculate_rectangle_overlap_percentage(existing_roi,new_roi ) > 0.8:
            overlap = True

        return dict_data, old_to_new_roi_names, overlap
    

    def __calculate_rectangle_overlap_percentage(self, rect1, rect2):
        """
        Calculate the percentage of area overlap between two rectangles.
        The percentage is calculated as (overlap area / area of rect1) * 100.
        
        Parameters:
        rect1 (tuple): First rectangle coordinates (minx, miny, maxx, maxy)
        rect2 (tuple): Second rectangle coordinates (minx, miny, maxx, maxy)
        
        Returns:
        float: Percentage of rect1's area that overlaps with rect2
        """
        # Extract coordinates from rectangles
        minx1, miny1, maxx1, maxy1 = rect1
        minx2, miny2, maxx2, maxy2 = rect2
        
        # Calculate the area of the first rectangle
        area1 = (maxx1 - minx1) * (maxy1 - miny1)
        
        # Find the overlapping rectangle coordinates
        overlap_minx = max(minx1, minx2)
        overlap_miny = max(miny1, miny2)
        overlap_maxx = min(maxx1, maxx2)
        overlap_maxy = min(maxy1, maxy2)
        
        # Check if there is an overlap
        if overlap_minx >= overlap_maxx or overlap_miny >= overlap_maxy:
            return 0.0  # No overlap
        
        # Calculate the area of overlap
        overlap_area = (overlap_maxx - overlap_minx) * (overlap_maxy - overlap_miny)
        
        # Calculate the percentage of the first rectangle that is overlapped
        overlap_percentage = (overlap_area / area1) * 100
        
        return overlap_percentage
    

    def __scale_points(self, polygon, point, scale_factor):
        """
        Scales the points of a polygon around a given point by a specified scale factor.

        :param polygon: The polygon to be scaled.
        :type polygon: list of tuples
        :param point: The point around which the polygon will be scaled.
        :type point: tuple
        :param scale_factor: The factor by which the polygon will be scaled.
        :type scale_factor: float

        :returns: The scaled polygon.
        :rtype: list of tuples

        This function scales the points of a polygon around a given point by a specified scale factor.
        """
        

        # Create the new vertices of the enlarged polygon
        enlarged_polygon = [(np.array(point) + (np.array(vertex) - np.array(point)) * scale_factor).tolist() for vertex in polygon]

        return enlarged_polygon


    def __rotate_points(self, rotation, roi, start):
        """
        Rotates the polygon based on the rotation type.

        :param rotation: The rotation type.
        :type rotation: int
        :param roi: The region of interest.
        :type roi: list
        :param start: The start point.
        :type start: list

        :returns: The rotated polygon and start point.
        :rtype: tuple

        This function rotates the polygon based on the rotation type.
        """
        if rotation is None:
            return roi, start

        rotation_options = {
            Template_Rotate.CW_90.value: 90,
            Template_Rotate.CW_180.value: 180,
            Template_Rotate.CW_270.value: 270,
        }

        rotation_degrees = rotation_options[rotation]

        center = list(Polygon(roi).centroid.coords)[0]

        return self.__rotate_polygon(roi,rotation_degrees,center)


    def __flip_points(self, flip, roi, start):
        """
        Flips the polygon based on the flip type.

        :param flip: The flip type.
        :type flip: int
        :param roi: The region of interest.
        :type roi: list
        :param start: The start point.
        :type start: list

        :returns: The flipped polygon and start point.
        :rtype: tuple

        This function flips the polygon based on the flip type.
        """
        if flip is None:
            return roi, start

        return self.__flip_polygon(roi,flip==Template_Flip.HORIZONTALLY.value)


    def __create_text_location_dict_copy(self,pno,roi_bbox, text_locations, template_to_match_ratio):
        """
        Creates a copy of the text location dictionary.

        :param pno: The page number.
        :type pno: int
        :param roi_bbox: The region of interest bounding box.
        :type roi_bbox: list
        :param text_locations: The list of text locations.
        :type text_locations: list
        :param template_to_match_ratio: The ratio to match the template.
        :type template_to_match_ratio: float

        :returns: A dictionary containing the new text location dictionary, the name to ROI name map, and the old to new ROI names map.
        :rtype: tuple

        This function creates a copy of the text location dictionary.
        """
        new_text_location_dict = {}
        new_text_location_name_to_roi_name_map = {}

        old_to_new_roi_names = {}

        for text_location in text_locations:

            if self.__document_type == Database.DRAWING:  zoom_scale = self.__pdf_zoom_scale  
            else: zoom_scale = 1

            text_roi = list(map((lambda i: (i[0]/zoom_scale * template_to_match_ratio,
                                        i[1]/zoom_scale * template_to_match_ratio)), text_location['points']))


            minX = int(min(l[0] for l in text_roi))
            minY = int(min(l[1] for l in text_roi))
            maxX = int(max(l[0] for l in text_roi))
            maxY = int(max(l[1] for l in text_roi))

            roi_name = (str(pno) +'-'+ str(minX) +'-'+ str(minY) 
                    +'-'+ str(maxX) +'-'+ str(maxY) +'-'+'text')

            mask_shape = self.__text_location_dict[text_location['roi_name']]['mask_shape']
            
            
            new_text_location_dict[roi_name] = {
                'text_roi':text_roi,
                'text_dict': text_location['text_dict'],
                'mask_shape': mask_shape,
                'pno': pno,
                'path': self.__path,
                'color': self.__text_location_dict[text_location['roi_name']]['color']
            }

            for text_location_name, old_roi_name in self.__text_location_name_to_roi_name_map.items():
                if old_roi_name == text_location['roi_name']:
                    new_text_location_name_to_roi_name_map[text_location_name] = roi_name
                    old_to_new_roi_names[old_roi_name]=roi_name

        return new_text_location_dict, new_text_location_name_to_roi_name_map, old_to_new_roi_names

        

            

        

    def set_data(self, data):
        """
        Sets the data for the object.

        :param data: A dictionary containing the data to be set.
        :type data: dict

        :returns: None
        :rtype: None

        This function sets the data for the object.
        """
        
        if not data:
            return 

        self.__path = data['path']
        self.__pno = data['pno']
        self.__roi = data['roi']
        self.__roi_uid = data['roi_uid']
        self.__minX = data['minX']
        self.__minY = data['minY']
        self.__maxX = data['maxX']
        self.__maxY = data['maxY']
        self.__text_location_dict = data['text_location_dict']
        self.__text_location_name_to_roi_name_map = data['text_location_name_to_roi_name_map']
        
        if data['display_image'] != None:
            self.__display_image_path = data['display_image']
            self.__display_image = Project_File_Manager.open_opencv_image(data['display_image'],
                                                                            cv2.IMREAD_UNCHANGED)
        
        if data['template_image'] != None:
            self.__template_image_path = data['template_image']
            self.__template_image = Project_File_Manager.open_opencv_image(data['template_image'],
                                                                            cv2.IMREAD_UNCHANGED)
        
        if data['template_mask'] != None:
            self.__template_mask_path = data['template_mask']
            self.__template_mask = Project_File_Manager.open_opencv_image(data['template_mask'],
                                                                            cv2.IMREAD_GRAYSCALE)
        
        if data['template_and_text_mask'] != None:
            self.__template_and_text_mask_path = data['template_and_text_mask']
            self.__template_and_text_mask = Project_File_Manager.open_opencv_image(data['template_and_text_mask'],
                                                                            cv2.IMREAD_GRAYSCALE)
        
        self.__template_image_width = data['template_image_width']
        self.__template_image_height = data['template_image_height']
        self.__ocr_used = data['ocr_used']
        self.__points_of_interests = data['points_of_interests']

        self.__page_width = data['page_width']
        self.__page_height = data['page_height']
        self.__pdf_zoom_scale = data['pdf_zoom_scale'] 

        if 'document_type' in data and data['document_type'] != None:
            self.__document_type = data['document_type']

        self.__linked = True
        self.__change_callback()


    def get_pdf_zoom_scale(self):
        """
        Retrieves the PDF zoom scale.

        :returns: The PDF zoom scale.
        :rtype: float

        Retrieves the PDF zoom scale. The function returns the PDF zoom scale.
        """
        return self.__pdf_zoom_scale


    def set_document_viewer_path_and_page(self, path, page):
        """
        Sets the path and page number of the document viewer.

        :param path: The path of the document.
        :type path: str

        :param page: The page number of the document.
        :type page: int

        :returns: None
        :rtype: None

        This function sets the path and page number of the document viewer.
        """
        self.__document_viewer_panel_path = path
        self.__document_viewer_panel_pno = page

        self.set_document_viewer_text_locations()


    def set_document_viewer_text_locations(self):
        """
        Sets the text locations for the document viewer.

        :returns: None
        :rtype: None

        This function sets the text locations for the document viewer.
        """

        if self.__document_viewer_panel_path != self.__path:
            return 

        if self.__document_viewer_panel_pno != self.__pno:
            return

        if not self.__text_location_dict:
            return 

       
        if self.__text_roi_doc_viewer_callback_func:
            self.__text_roi_doc_viewer_callback_func(self.__text_location_dict, self.__name)


    def get_all_roi_ids(self):
        """
        Retrieves all ROI IDs associated with the current instance.

        :returns: A list of tuples representing the ROI IDs.
        :rtype: list

        This function retrieves all ROI IDs associated with the current instance.

        Example:
        >>> get_all_roi_ids()
        [('pno1', 'uid1'), ('pno2', 'roi1'), ('pno2', 'roi2')]
        """
        roi_ids = []
        if self.__roi_uid:
            roi_ids.append((self.__pno,self.__roi_uid))
        for roi_name,text_location in self.__text_location_dict.items():
            roi_ids.append((text_location['pno'],roi_name))

        return roi_ids

        

    def get_display_image(self):
        """
        Returns the display image.

        :returns: The display image.
        :rtype: object

        This function returns the display image.
        """
        return self.__display_image


    def get_template_image(self):
        """
        Returns the template image.

        :returns: The template image.
        :rtype: object

        This function returns the template image.
        """
        return self.__template_image


    def enable_link_view(self):
        """
        Enables the linking view.

        :returns: None
        :rtype: None

        This function enables the linking view.
        """

        self.__linking_enabled = True

    

        if self.__linked and self.__text_locations_list_view is not None:
            self.__text_locations_list_view.enable_linking() 
            

        if self.__link_view:
            self.__link_view.enable_linking()



    def disable_link_view(self):
        """
        Disables the link view functionality.

        :returns: None
        :rtype: None

        This function disables the link view functionality.
        """

        self.__linking_enabled = False

        if self.__linked and self.__text_locations_list_view is not None:
            self.__text_locations_list_view.disable_linking() 
                    
        if self.__link_view:
            self.__link_view.disable_linking()

 
    def setup_link_view(self, canvas, x, y):
        """
        Sets up the link view.

        :param canvas: The canvas to draw the link view on.
        :type canvas: tkinter.Canvas
        :param x: The x-coordinate of the link view.
        :type x: int
        :param y: The y-coordinate of the link view.
        :type y: int

        :returns: None
        :rtype: None

        This function sets up the link view.
        """
        self.__link_view = link_view(canvas, x,y,self.__linking_callback, self.__goto_callback)
        
        if self.__linking_enabled:
            self.__link_view.enable_linking()
        else:
            self.__link_view.disable_linking()

        if self.__linked:
            self.__link_view.enable_goto()
            self.__linked_callback_func(self.__display_image)
            self.__link_view.link_formed()

         
    def setup_linking_callback_func(self, callback):
        """
        Sets up the linking callback function.

        :param callback: The callback function to be set.
        :type callback: function

        :returns: None
        :rtype: None

        This function sets up the linking callback function.
        """
        self.__linking_callback_func = callback


    def document_type(self, type):
        """
        Sets the document type.

        :param type: The document type.
        :type type: str

        :returns: None
        :rtype: None

        This function sets the document type.
        """
        self.__current_doc_type = type


    def setup_text_roi_callback_func(self, callback):
        """
        Sets up the callback function for the text ROI document viewer.

        :param callback: The callback function to be set up.
        :type callback: function

        :returns: None
        :rtype: None

        This function sets up the callback function for the text ROI document viewer.
        """
        
        self.__text_roi_doc_viewer_callback_func = callback


    def setup_get_page_text_callback_func(self, callback):
        """
        Sets up the callback function for retrieving text on a page.

        :param callback: The callback function to be set.
        :type callback: function

        :returns: None
        :rtype: None

        Th
        """
        self.__get_text_on_page_callback_func = callback


    def setup_get_full_page_image_func(self, callback):
        """
        Sets up the callback function for getting the full page image.

        :param callback: The callback function to be set.
        :type callback: function

        :returns: None

        This function sets up the callback function for getting the full page image.
        """

        self.__get_full_page_image_callback_func = callback


    def redetect_text_dicts_at_polygons(self, text_roi_polygons_unscaled, dest_path, dest_pno):
        """ Run text detection at the caller-supplied polygons on the currently-visible
        destination page and return a parallel list of `text_dict` results (one per
        polygon). Used by manual Draw ROI so freshly-placed control modules pick up
        the text that is actually under the drawn ROI instead of inheriting the
        source template's characters.

        Polygons are in *unscaled destination-doc coords* (same coord system as
        `text_location_dict[...]['text_roi']`). Returns an empty list on any wiring
        failure; individual polygons return `[]` when detection fails.
        """
        if not text_roi_polygons_unscaled:
            return []
        if self.__get_full_page_image_callback_func is None:
            return [[] for _ in text_roi_polygons_unscaled]

        try:
            full_page_pil = self.__get_full_page_image_callback_func(self.__pdf_zoom_scale)
            full_page = np.array(full_page_pil)
        except Exception:
            logging.exception("redetect_text_dicts_at_polygons: failed to fetch page image")
            return [[] for _ in text_roi_polygons_unscaled]

        text_in_page = None
        if self.__get_text_on_page_callback_func is not None:
            try:
                text_in_page = self.__get_text_on_page_callback_func()
            except Exception:
                text_in_page = None

        is_drawing = self.__document_type == Database.DRAWING
        zoom = self.__pdf_zoom_scale if is_drawing else 1

        results = []
        for poly in text_roi_polygons_unscaled:
            if not poly or len(poly) < 3:
                results.append([])
                continue
            vertices = [(int(round(p[0] * zoom)), int(round(p[1] * zoom))) for p in poly]
            mask_shape = vertices

            raw_text_dict = []
            if is_drawing and text_in_page:
                # `__find_text_dict_within_roi` matches against char bboxes in
                # unscaled PDF-point coords, so pass the polygon in its native
                # unscaled coords (not the scaled `vertices` used for OCR).
                xs_raw = [p[0] for p in poly]
                ys_raw = [p[1] for p in poly]
                raw_text_dict = self.__find_text_dict_within_roi(
                    int(min(xs_raw)), int(min(ys_raw)),
                    int(max(xs_raw)), int(max(ys_raw)),
                    text_in_page,
                )

            ocr_text_dict = []
            # Mirror the scanner path: when the source link was created without
            # OCR, trust the raw PDF text and skip the OCR pass entirely.
            skip_ocr = is_drawing and not self.__ocr_used
            try:
                if skip_ocr:
                    ocr_text_dict = []
                elif not is_drawing:
                    ocr_img = full_page
                    if ocr_img.ndim == 3 and ocr_img.shape[2] == 4:
                        ocr_img = cv2.cvtColor(ocr_img, cv2.COLOR_RGBA2BGR)
                    elif ocr_img.ndim == 3:
                        ocr_img = cv2.cvtColor(ocr_img, cv2.COLOR_RGB2BGR)
                    ocr_text_dict, _ = find_text_dict_within_image_roi_with_ocr(
                        ocr_img, vertices, 1, mask_shape,
                        extract_image=True,
                    )
                else:
                    if full_page.ndim == 3:
                        ocr_img = cv2.cvtColor(full_page, cv2.COLOR_RGB2GRAY)
                    else:
                        ocr_img = full_page
                    ocr_text_dict, _ = find_text_dict_within_roi_with_ocr(
                        ocr_img, vertices, self.__pdf_zoom_scale, mask_shape,
                        extract_image=True,
                    )
            except Exception:
                logging.exception("redetect_text_dicts_at_polygons: OCR failed for polygon %s", poly)
                ocr_text_dict = []

            if ocr_text_dict and not self.__have_common_chars(ocr_text_dict, raw_text_dict):
                text_dict = ocr_text_dict
            else:
                text_dict = raw_text_dict or ocr_text_dict

            while text_dict and text_dict[0].get('c') == ' ':
                text_dict.pop(0)
            while text_dict and text_dict[-1].get('c') == ' ':
                text_dict.pop()

            results.append(text_dict)

        return results


    def create_placement_template_images(self, placement_dict):
        """ Build and persist a standalone template / mask / display image set for a
        manually-placed copy, cropped from the currently-visible destination page.

        `create_copy` only copies this instance's template paths onto the new
        dict, so a manual placement would otherwise share (and display) the
        source symbol's artwork. Returns the new path + size values to merge
        into `placement_dict`, or None when they cannot be produced. This must
        never mutate this instance's own `__*_path` fields — the source graphic
        keeps its own files.
        """
        if not isinstance(placement_dict, dict):
            return None
        if self.__get_full_page_image_callback_func is None:
            return None
        roi = placement_dict.get('roi') or []
        if len(roi) < 3:
            return None

        try:
            full_page = np.array(self.__get_full_page_image_callback_func(self.__pdf_zoom_scale))
        except Exception:
            logging.exception("create_placement_template_images: failed to fetch page image")
            return None
        if full_page.ndim == 2:
            full_page = cv2.cvtColor(full_page, cv2.COLOR_GRAY2BGR)
        elif full_page.shape[2] == 4:
            full_page = cv2.cvtColor(full_page, cv2.COLOR_RGBA2BGR)

        page_h, page_w = full_page.shape[:2]
        min_x = max(int(placement_dict.get('minX', 0)), 0)
        min_y = max(int(placement_dict.get('minY', 0)), 0)
        max_x = min(int(placement_dict.get('maxX', 0)), page_w)
        max_y = min(int(placement_dict.get('maxY', 0)), page_h)
        if max_x - min_x < 1 or max_y - min_y < 1:
            return None

        # Same channel handling as `__create_graphic_link` so the saved PNGs
        # match the ones the scanner/linking path produces.
        template_image = cv2.cvtColor(full_page[min_y:max_y, min_x:max_x].copy(),
                                      cv2.COLOR_BGR2RGB)
        shape = template_image.shape[:2]
        zoom_scale = 1 if self.__document_type == Database.IMAGE else self.__pdf_zoom_scale

        outline = [(int(p[0] * zoom_scale) - min_x, int(p[1] * zoom_scale) - min_y) for p in roi]
        template_mask = cv2.fillPoly(np.zeros(shape, np.uint8), np.int32([np.array(outline)]), (255))

        text_locations = list((placement_dict.get('text_location_dict') or {}).values())
        template_and_text_mask = template_mask
        for text_location in text_locations:
            mask_shape = text_location.get('mask_shape')
            if not mask_shape or len(mask_shape) < 3:
                continue
            text_mask = cv2.fillPoly(np.zeros(shape, np.uint8), np.int32([np.array(mask_shape)]), (255))
            template_and_text_mask = cv2.bitwise_and(cv2.bitwise_not(text_mask),
                                                     template_and_text_mask)

        r_channel, g_channel, b_channel = cv2.split(template_image)[0:3]
        display_image = cv2.merge((b_channel, g_channel, r_channel, template_and_text_mask))
        for text_location in text_locations:
            mask_shape = text_location.get('mask_shape')
            color = text_location.get('color')
            if not mask_shape or len(mask_shape) < 3 or not color:
                continue
            cv_color = self.convert_hex_color_to_rgba_array(color)
            display_image = cv2.fillPoly(display_image, np.int32([np.array(mask_shape)]), cv_color)
        display_image = cv2.cvtColor(display_image, cv2.COLOR_BGRA2RGBA)

        return {
            'template_image': Project_File_Manager.save_opencv_image(self.__project_name, template_image),
            'template_mask': Project_File_Manager.save_opencv_image(self.__project_name, template_mask),
            'template_and_text_mask': Project_File_Manager.save_opencv_image(self.__project_name, template_and_text_mask),
            'display_image': Project_File_Manager.save_opencv_image(self.__project_name, display_image),
            'template_image_width': shape[1],
            'template_image_height': shape[0],
        }


    def draw_link_view(self, x=0, y=0):
        """
        Draws a link view at the specified coordinates.

        :param x: The x-coordinate of the link view. Default is 0.
        :type x: int
        :param y: The y-coordinate of the link view. Default is 0.
        :type y: int

        :returns: None
        :rtype: None

        This function draws a link view at the specified coordinates.
        """
        if self.__linked:
            self.__link_view.link_formed()
            self.__link_view.enable_goto()
            
        self.__link_view.draw( x, y)


    def hide_link_view(self):
        """
        Hides the link view if it is currently visible.

        :returns: None
        :rtype: None

        :raises: None
        """
        if self.__link_view:
            self.__link_view.hide()


    def __linking_callback(self, linked):
        """
        Callback function for handling linked status.

        :param linked: Indicates if the link is active or not.
        :type linked: bool

        :returns: None
        :rtype: None

        This function is a callback function for handling linked status. It resets the link if the link is active,
        """
        if linked:
            self.__reset_link()
           
        else: 
            if self.__linking_callback_func:
                self.__roi_uid, roi, pno, path, full_image, image, _ = self.__linking_callback_func()
                self.create_graphic_link(roi,pno,path,full_image,image)


    def create_quick_graphic_link(self, linking_callback_func):    
        """
        Creates a quick graphic link.

        :param linking_callback_func: The callback function for linking.
        :type linking_callback_func: function

        :returns: None
        :rtype: None

        This function creates a quick graphic link by resetting the link and setting the linking callback function.
        """
        self.__linking_callback_func = linking_callback_func
        self.__roi_uid, roi, pno, path, full_image, image, _ = self.__linking_callback_func()
        self.create_graphic_link(roi,pno,path,full_image,image)



    def __reset_link(self):
        """
        Resets the link by clearing all the attributes and variables related to the link.

        :returns: None
        :rtype: None

        This function resets the link by clearing all the attributes and variables related to the link.
        """
        self.__full_page_image = None
        self.__path = None 
        self.__pno = None 
        self.__roi = None 
        self.__roi_uid = None
        self.__minX = -1
        self.__minY = -1
        self.__maxX = -1
        self.__maxY = -1
        self.__text_location_dict = {}
        self.__text_location_name_to_roi_name_map = {}
        self.__target_image = None
        self.__display_image = None
        self.__template_image = None
        self.__template_mask = ...
        self.__template_image_width = 0 
        self.__template_image_height = 0
        self.__linking_enabled = False
        self.__linked = False
        if self.__link_view:
            self.__link_view.link_removed()
            self.__link_view.disable_goto()
        self.__ocr_used = False
        self.__points_of_interests = []
        if self.__link_view:
            if self.__linking_enabled:
                self.__link_view.enable_linking()
            else:
                self.__link_view.disable_linking()
        self.__remove_all_text_locations()
        self.__linked_callback_func(None)
        self.__change_callback()
        self.__pdf_zoom_scale = 2


    def __goto_callback(self):
        if self.__goto_callback_func:
            self.__goto_callback_func(self.__roi_uid,self.__pno,self.__path, self.__document_type)
        


    def remove_external_rogue_lines(self, img):
        """
        Remove external rogue lines from an image.

        :param img: The input image.
        :type img: numpy.ndarray

        :returns: The modified image with external rogue lines removed.
        :rtype: numpy.ndarray

        This function removes external rogue lines from an image. It first removes closed 
        contour content from the image, then removes boundary touching lines.
        """
        image = img.copy()
        orig = image.copy()

        start = time.time()

        '''=========== Remove closed contour content =========== '''

        height_mini, width_mini = image.shape[:2]

        for x in range(width_mini - 1):
            cv2.floodFill(image, None, (x, 0), (0, 0, 0))
            cv2.floodFill(image, None, (x, height_mini - 1), (0, 0, 0))
            
        for y in range(height_mini - 1):
            cv2.floodFill(image, None, (0, y), (0, 0, 0))
            cv2.floodFill(image, None, (width_mini - 1 , y), (0, 0, 0))

        cv2.imshow('done', image)
        cv2.waitKey(0)
    
        difference = cv2.subtract(orig, image)
        cv2.imshow('done', difference)
        cv2.waitKey(0)

        '''=========== Remove boundary touching lines =========== '''

        kernel = np.ones((3,3), np.uint8)
        
        difference = cv2.bitwise_not(difference)
        contours, _ = cv2.findContours(difference, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea)
        number_of_time_eroded = 0
        while (self.is_contour_touching_border(contours[-1], difference) and 
                number_of_time_eroded < 15):
            difference = cv2.erode(difference, kernel, iterations=1)
            number_of_time_eroded = number_of_time_eroded + 1
            contours, _ = cv2.findContours(difference, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
            contours = sorted(contours, key=cv2.contourArea)
            cv2.imshow('done', difference)
            cv2.waitKey(0)
            

        for i in range(number_of_time_eroded):
            difference = cv2.dilate(difference, kernel, iterations=1)

        contours, _ = cv2.findContours(difference, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea)

        x,y,w,h = cv2.boundingRect(contours[-1])
        
        template_image = orig[y:y+h, x:x+w]

        mask = np.zeros(orig.shape, np.uint8)
        cv2.drawContours(mask, [contours[-1]], -1 ,(255),-1)
        
      
        print(time.time() - start)

        cv2.imshow('done', template_image)
        cv2.waitKey(0)

        cv2.imshow('done', mask)
        cv2.waitKey(0)

        return image 


    def is_contour_touching_border(self, contour, image):
        """
        Check if a contour is touching the border of an image.

        :param contour: The contour to check.
        :type contour: numpy.ndarray
        :param image: The image to check against.
        :type image: numpy.ndarray

        :returns: True if the contour is touching the border, False otherwise.
        :rtype: bool

        :raises ValueError: If the contour is invalid.
        :raises TypeError: If the image is not a valid numpy array.

        This function checks if the bounding rectangle of the given contour is touching the border of the image.
        The contour is considered to be touching the border if any part of its bounding rectangle lies outside the image boundaries.
        The function returns True if the contour is touching the border, and False otherwise.
        It raises a ValueError if the contour is invalid or a TypeError if the image is not a valid numpy array.

        Example:
        >>> contour = np.array([[0, 0], [0, 1], [1, 1], [1, 0]])
        >>> image = np.zeros((3, 3), dtype=np.uint8)
        >>> is_contour_touching_border(contour, image)
        True
        """
        x_o,y_o,w_o,h_o = cv2.boundingRect(contour)
        image_height = image.shape[0] - 1
        image_width = image.shape[1] - 1


        if ( x_o <= 0 or y_o <= 0 or
            (x_o + w_o) >= image_width or (y_o + h_o) >= image_height):
            return True

        return False


    def get_points_of_interests(self):
        return self.__points_of_interests

        

    
    def find_center_countour(self, image):
        cv2.imshow('first', image)
        cv2.waitKey(0)
        dilate_contours, dilate_hierarchy = cv2.findContours(image, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        mask = np.zeros(image.shape, np.uint8)
        cv2.imshow('first', mask)
        cv2.waitKey(0)
        cnt = sorted(dilate_contours, key=cv2.contourArea)

        for i in range(len(cnt)):
            cv2.drawContours(mask, cnt, i ,(255),-1)
            cv2.imshow('first', mask)
            cv2.waitKey(0)


        
    def search_current_page(self,  template_flip:List[Template_Flip]=[Template_Flip.NONE], template_rotate:List[Template_Rotate]=[Template_Rotate.NONE]):
        """
        Searches for the current page using the specified template flip and template rotate.

        :param template_flip: List of template flip options (default: [Template_Flip.NONE])
        :type template_flip: List[Template_Flip]
        :param template_rotate: List of template rotate options (default: [Template_Rotate.NONE])
        :type template_rotate: List[Template_Rotate]

        :return: None
        :rtype: None

        This function searches for the current page using the specified template flip and template rotate options. It raises a ValueError if no template image has been defined or if no page is open. It starts a new thread to perform the search and updates the test search progress string. The search is performed using the full page image and the specified template flip and template rotate options.

        Example:
            >>> search_current_page([Template_Flip.NONE, Template_Flip.HORIZONTAL], [Template_Rotate.NONE, Template_Rotate.CLOCKWISE])
        """
        if self.__template_image is None:
            raise ValueError('No template image has been defined. Please define the linked graphic before testing.')


        
        if self.__get_full_page_image_callback_func is None:
            raise ValueError('No page open. Please open a document page first before testing.')
        img = np.array(self.__get_full_page_image_callback_func(self.__pdf_zoom_scale))
        self.__full_page_image = cv2.cvtColor(img,cv2.COLOR_BGR2RGB)

        if self.__linking_callback_func is None:
            raise ValueError('No document open. Please open a document first before testing or reopen the document.')
        
        _, __, pno, path, ___, ____, ______ = self.__linking_callback_func()
        
        if self.__full_page_image is None:
            raise ValueError('No page open. Please open a document page first before testing.')


        def start_test_on_page_search():
        
            thread = Thread(target=self.search_image,args=(path,pno,self.__full_page_image,template_flip,template_rotate))
            thread.start()

            self.__test_search_done = False
            self.__test_progress_string = "Starting"
            self.__test_on_page_interface.run_after_delay(self.__check_if_test_search_done)



        self.__test_on_page_interface = test_on_page(self.__config, start_test_on_page_search)
        start_test_on_page_search()


    


    def __check_if_test_search_done(self):
        """
        Check if the test search is done and perform the necessary actions accordingly.

        :return: None
        :rtype: None

        This function checks if the test search is done and performs the necessary actions accordingly. 
        If the test search is done, the function displays the test results on the page interface. If the 
        test search is not done, the function shows the busy canvas on the page interface.
        """
        if self.__test_search_done:
            self.__test_on_page_interface.images(self.__test_result_image
                                                ,self.__test_default_image
                                                ,self.__test_cw_90_image
                                                ,self.__test_cw_180_image
                                                ,self.__test_cw_270_image
                                                ,self.__test_flipped_image
                                                ,self.__test_text_result_image
                                                ,self.__create_test_image(self.__test_template_image_black_and_white))
        else:
            self.__test_on_page_interface.run_after_delay(self.__check_if_test_search_done)
            self.__test_on_page_interface.show_busy_canvas(self.__test_progress_string)


    def __scanning_done_callback(self, results=None):
        for func in self.__scanning_done_callback_funcs:
            if func is not None:
                func(results)

    def start_scan(self,template_flip,template_rotate,page_index=None):
        """
        Starts the scanning process.

        :param template_flip: Indicates whether to flip the template image.
        :type template_flip: bool
        :param template_rotate: Indicates the rotation angle of the template image.
        :type template_rotate: int

        :return: True if the scanning process started successfully, False otherwise.
        :rtype: bool
        """

        if self.__template_image is None:
            if not self.__is_primary_linked_graphic:
                return False
            raise ValueError('No template image has been defined. Please define the primary linked graphic before scanning.')
        
        if self.__linking_callback_func is None:
            raise ValueError('No document open. Please open a document first before scanning or reopen the document.')
        
        path = self.__linking_callback_func()[3]

        if self.__current_doc_type != self.__document_type:
            raise ValueError('Document type mismatch. Please scan the same type of document.')

        self.__scanner = linked_graphic_scanner(self.__result_callback, self.__scanning_done_callback, self.__config)

        
        self.__scanner.multiprocess_search_document(path,
                                                        self.__template_image,
                                                        self.__template_and_text_mask,
                                                        self.__text_location_dict,
                                                        self.__ocr_used,
                                                        self.__pdf_zoom_scale,
                                                        template_flip,
                                                        template_rotate,
                                                        page_index,
                                                        document_type=self.__document_type)
        return True
        
        '''
        if self.__full_page_image is None:
            if self.__is_primary_linked_graphic:
                return
            raise ValueError('No page open')'''


    def check_scanner_progress(self):
        return self.__scanner.check_multiprocess_search_progress()
         
    
    def update_scanner_string(self, string):
        self.__test_progress_string = string


    def find_similar_from_image(self,matcher,image,template_flip:List[Template_Flip]=[Template_Flip.NONE]
                                ,template_rotate:List[Template_Rotate]=[Template_Rotate.NONE]
                                ,page_index=None,document_type=Database.DRAWING):

        """
        Uses a Image Matcher to find a similar image in the current document and gets a histogram of the image that is used 
        to redraw the polygon and text location.
        :param matcher: The image matcher to use.
        :type matcher: object
        :param image: The image to match.
        :type image: numpy.ndarray
        :param template_flip: List of template flip options (default: [Template_Flip.NONE])
        :type template_flip: List[Template_Flip]
        :param template_rotate: List of template rotate options (default: [Template_Rotate.NONE])
        :type template_rotate: List[Template_Rotate]
        :param page_index: The page index to search on (default: None)
        :type page_index: int
        :param document_type: The type of document to search in (default: Database.DRAWING)
        :type document_type: str
        :return: True if the image was found, False otherwise.
        :rtype: bool
        :raises ValueError: If no template image is defined, no document is open, or if the document type does not match.
        """
        

        if self.__linking_callback_func is None:
            raise ValueError('No document open. Please open a document first before scanning or reopen the document.')
                

        if self.__current_doc_type != self.__document_type:
            raise ValueError('Document type mismatch. Please scan the same type of document.')




        
        if self.__template_image is None:
            if not self.__is_primary_linked_graphic:
                return False
            raise ValueError('No template image has been defined. Please define the primary linked graphic before scanning.')
        
        try:
            if isinstance(self.__template_image, list): template_image = self.__template_image[0]
            else: template_image = self.__template_image

            if isinstance(self.__template_and_text_mask, list): template_and_text_mask = self.__template_and_text_mask[0]
            else: template_and_text_mask = self.__template_and_text_mask
            
            if self.__document_type == Database.DRAWING:
                old_start = ((self.__minX / self.__pdf_zoom_scale, self.__minY / self.__pdf_zoom_scale ))
                pdf_zoom = self.__pdf_zoom_scale
            else:
                old_start = ((self.__minX, self.__minY))
                pdf_zoom = 1

            roi = self.__translate_points(old_start,[0, 0],self.__roi)

            result =  matcher.match(template_image
                                                                                    ,image
                                                                                    ,template_and_text_mask
                                                                                    ,template_flip
                                                                                    ,template_rotate
                                                                                    ,document_type
                                                                                    ,polygon=roi
                                                                                    ,pdf_zoom=pdf_zoom)

            new_template_image = result[0]
            new_template_mask = result[1]
            scale_factor = result[2]
            template_flip = [Template_Flip.NONE]
            template_rotate = [Template_Rotate.NONE]
            new_roi = result[5]

        except Exception as e:
            logging.warning('Unable to find similar in selected region. Error: '+str(e))
            raise ValueError('Unable to find similar in selected region. Error: '+str(e))
        
        
        
        # Determine color difference between the new template image and the original template image
        hist1 = cv2.calcHist([template_image], [0, 1, 2], template_and_text_mask
                             , [8, 8, 8], [0, 256, 0, 256, 0, 256])
        # Normalize the histogram to protect against scaling differences
        hist1 = cv2.normalize(hist1, hist1).flatten()

        hist2 = cv2.calcHist([new_template_image], [0, 1, 2], new_template_mask
                                , [8, 8, 8], [0, 256, 0, 256, 0, 256])
        # Normalize the histogram to protect against scaling differences
        hist2 = cv2.normalize(hist2, hist2).flatten()
        diff = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)

        # If the difference is less than 0.9 and the scale factor is between 0.9 and 1.1, add the new template image
        add_template_image = diff < 0.9 and 0.9 <= scale_factor <= 1.1

        return [new_template_mask, scale_factor, new_roi, template_flip,
                template_rotate, page_index, document_type, add_template_image]
        

        
    def add_graphic_link(self,roi_uid,pno,new_template_mask,template_flip,template_rotate
                         ,page_index,scale_factor,document_type,add_template_image=False):
        _, _, _, path, _, image, _ = self.__linking_callback_func(self.__pdf_zoom_scale,
                                                                    roi_uid,
                                                                    pno)
        
        # Convert the image to numpy array
        new_template_image = np.array(image)
        
        # Convert BGR to RGB for 3 and 4 channel
        new_template_image = cv2.cvtColor(new_template_image, cv2.COLOR_BGR2RGB)

        # resize the mask to the new image size
        h, w = new_template_image.shape[:2]
        new_template_mask = cv2.resize(new_template_mask, (w, h))

        if add_template_image:
            self.__add_template_image(new_template_image, new_template_mask)

        
        
        self.__scanner = linked_graphic_scanner(self.__result_callback, self.__scanning_done_callback, self.__config)
        self.__scanner.multiprocess_search_document(path,
                                                    new_template_image,
                                                    new_template_mask,
                                                    self.__text_location_dict,
                                                    self.__ocr_used,
                                                    self.__pdf_zoom_scale,
                                                    template_flip,
                                                    template_rotate,
                                                    page_index,
                                                    scale_factor,
                                                    document_type)
        


    def search_current_page_with_polygon_template(self, polygon_unscaled, template_mask,
                                                   template_flip=None, template_rotate=None):
        """ Page-level test where the template image is freshly cropped from the
        currently-visible destination page at ``polygon_unscaled`` and the mask
        is caller-supplied. Used by Draw ROI's Test button so the preview
        reflects the transformed (flipped/rotated/scaled/moved) placement
        instead of the pristine source template used by ``search_current_page``.
        ``polygon_unscaled`` is in destination-doc unscaled coords, matching
        ``text_location_dict[...]['text_roi']`` conventions. """
        if template_flip is None:
            template_flip = [Template_Flip.NONE]
        if template_rotate is None:
            template_rotate = [Template_Rotate.NONE]
        if self.__get_full_page_image_callback_func is None:
            raise ValueError('No page open. Please open a document page first before testing.')
        if self.__linking_callback_func is None:
            raise ValueError('No document open. Please open a document first before testing.')
        if not polygon_unscaled or len(polygon_unscaled) < 3:
            raise ValueError('Draw ROI polygon is empty; nothing to test.')

        _, _, pno, path, _, _, _ = self.__linking_callback_func()

        is_drawing = self.__document_type == Database.DRAWING
        zoom = self.__pdf_zoom_scale if is_drawing else 1

        full_page_pil = self.__get_full_page_image_callback_func(self.__pdf_zoom_scale)
        image_to_search = np.array(full_page_pil)
        if image_to_search.ndim == 3 and image_to_search.shape[2] == 4:
            image_to_search = cv2.cvtColor(image_to_search, cv2.COLOR_RGBA2BGR)

        xs_scaled = [p[0] * zoom for p in polygon_unscaled]
        ys_scaled = [p[1] * zoom for p in polygon_unscaled]
        page_h, page_w = image_to_search.shape[:2]
        min_x = max(0, int(math.floor(min(xs_scaled))))
        min_y = max(0, int(math.floor(min(ys_scaled))))
        max_x = min(page_w, int(math.ceil(max(xs_scaled))))
        max_y = min(page_h, int(math.ceil(max(ys_scaled))))
        if max_x <= min_x or max_y <= min_y:
            raise ValueError('Draw ROI polygon lies outside the destination page.')

        new_template_image = image_to_search[min_y:max_y, min_x:max_x].copy()
        # Mirror new_graphic_search: crop is stored in RGB so search_image's
        # DRAWING branch can threshold it via cvtColor(RGB2GRAY).
        new_template_image = cv2.cvtColor(new_template_image, cv2.COLOR_BGR2RGB)

        h, w = new_template_image.shape[:2]
        resized_mask = cv2.resize(template_mask, (w, h), interpolation=cv2.INTER_NEAREST)

        def start_test_on_page_search():
            thread = Thread(target=self.search_image,
                            args=(path, pno, image_to_search, template_flip, template_rotate,
                                  new_template_image, resized_mask))
            thread.start()
            self.__test_search_done = False
            self.__test_progress_string = "Starting"
            self.__test_on_page_interface.run_after_delay(self.__check_if_test_search_done)

        self.__test_on_page_interface = test_on_page(self.__config, start_test_on_page_search)
        start_test_on_page_search()


    def new_graphic_search(self,roi_uid,pno,new_template_mask,template_flip,template_rotate
                            ,document_type=Database.DRAWING):
        

        _, _, _, path, image_to_search, image, _ = self.__linking_callback_func(self.__pdf_zoom_scale,
                                                                    roi_uid,
                                                                    pno)
        

        # If image_to_search is not np.ndarray, convert it to np.ndarray
        if not isinstance(image_to_search, np.ndarray):
            image_to_search = np.array(image_to_search)

        # If image_to_search is 4 channel, convert it to 3 channel
        if len(image_to_search.shape) == 3 and image_to_search.shape[2] == 4:
            image_to_search = cv2.cvtColor(image_to_search, cv2.COLOR_RGBA2BGR)

        # Convert the image to numpy array
        new_template_image = np.array(image)
        
        # Convert BGR to RGB for 3 and 4 channel
        new_template_image = cv2.cvtColor(new_template_image, cv2.COLOR_BGR2RGB)

        # resize the mask to the new image size
        h, w = new_template_image.shape[:2]
        new_template_mask = cv2.resize(new_template_mask, (w, h))

        def start_test_on_page_search():
        
            thread = Thread(target=self.search_image,args=(path, pno, image_to_search, template_flip, template_rotate,
                                                            new_template_image, new_template_mask))
            thread.start()

            self.__test_search_done = False
            self.__test_progress_string = "Starting"
            self.__test_on_page_interface.run_after_delay(self.__check_if_test_search_done)



        self.__test_on_page_interface = test_on_page(self.__config, start_test_on_page_search)
        start_test_on_page_search()



    

    def __add_template_image(self, template_image, template_and_text_mask):
        """
        Adds a template image to the linked graphic.

        :param template_image: The template image to add.
        :type template_image: numpy.ndarray
        :param template_mask: The mask for the template image.
        :type template_mask: numpy.ndarray
        :param template_and_text_mask: The mask for the template and text.
        :type template_and_text_mask: numpy.ndarray
        :param template_image_width: The width of the template image.
        :type template_image_width: int
        :param template_image_height: The height of the template image.
        :type template_image_height: int

        :returns: None
        :rtype: None

        This function adds a template image to the linked graphic. It sets the template image, mask, and the width and height of the template image.
        """
        # Save the new template image and mask
        template_filename = os.path.split(self.__template_image_path)[1]
        template_subfolder = os.path.splitext(template_filename)[0]
        Project_File_Manager.save_opencv_image(self.__project_name,template_image,template_subfolder)


        mask_filename = os.path.split(self.__template_and_text_mask_path)[1]
        mask_subfolder = os.path.splitext(mask_filename)[0]
        Project_File_Manager.save_opencv_image(self.__project_name,template_and_text_mask,mask_subfolder)

        b_channel, g_channel, r_channel = cv2.split(template_image)[0:3]
        display_image = cv2.merge((b_channel, g_channel, r_channel, template_and_text_mask))

        display_image_filename = os.path.split(self.__display_image_path)[1]
        display_image_subfolder = os.path.splitext(display_image_filename)[0]
        Project_File_Manager.save_opencv_image(self.__project_name,display_image,display_image_subfolder)

        if not isinstance(self.__template_image, list):
            self.__template_image = [self.__template_image, template_image]
            self.__template_and_text_mask = [self.__template_and_text_mask, template_and_text_mask]
            self.__display_image = [self.__display_image, display_image]
        else:
            self.__template_image.append(template_image)
            self.__template_and_text_mask.append(template_and_text_mask)
            self.__display_image.append(display_image)


    def __remove_template_image(self, index):
        """
        Removes a template image from the linked graphic.

        :param index: The index of the template image to remove.
        :type index: int

        :returns: None
        :rtype: None

        This function removes a template image from the linked graphic. It removes the template image, mask, and the width and height of the template image at the specified index.
        """
        if isinstance(self.__template_image, list) and len(self.__template_image) == 2:
            self.__template_image = self.__template_image[0]
            self.__template_and_text_mask = self.__template_and_text_mask[0]
            self.__display_image = self.__display_image[0]
        else:
            del self.__template_image[index]
            del self.__template_and_text_mask[index]
            del self.__display_image[index]




    def search_image(self,path,pno, image_to_search, template_flip:List[Template_Flip]=[Template_Flip.NONE]
                     , template_rotate:List[Template_Rotate]=[Template_Rotate.NONE], raw_template_image=None,
                     raw_template_and_text_mask=None):

        """
        Search for an image within another image using template matching.

        :param image_to_search: The image in which to search for the template image.
        :type image_to_search: numpy.ndarray

        :param template_flip: List of template flip options, defaults to [Template_Flip.NONE]
        :type template_flip: List[Template_Flip], optional

        :param template_rotate: List of template rotation options, defaults to [Template_Rotate.NONE]
        :type template_rotate: List[Template_Rotate], optional

        :return: None
        :rtype: None

        This function performs template matching to search for an image within another image. It takes an image to search and a list of template flip and rotation options. The function applies the specified flips and rotations to the template image and performs template matching with the image to search. The function then returns the result of the template matching.

        Example:
            >>> search_image(image_to_search, [Template_Flip.NONE, Template_Flip.HORIZONTALLY], [Template_Rotate.NONE, Template_Rotate.CW_90])
        """
        try:
            if raw_template_image is None and isinstance(self.__template_image, list): 
                selected_template_index = self.__get_multi_graphic_func()
                raw_template_image = self.__template_image[selected_template_index]
            elif raw_template_image is None: raw_template_image = self.__template_image

            if raw_template_and_text_mask is None and isinstance(self.__template_and_text_mask, list): 
                selected_template_index = self.__get_multi_graphic_func()
                raw_template_and_text_mask = self.__template_and_text_mask[selected_template_index]
            elif raw_template_and_text_mask is None: raw_template_and_text_mask = self.__template_and_text_mask

            # self.remove_external_rogue_lines(self.__template_image)
            if self.__default_zoom_scale != self.__pdf_zoom_scale and self.__document_type == Database.DRAWING:
                with warnings.catch_warnings():  # suppress DecompressionBombWarning for big image
                    warnings.simplefilter('ignore')
                    image_to_search = np.array(self.__get_full_page_image_callback_func(self.__pdf_zoom_scale))
                    image_to_search = cv2.cvtColor(image_to_search,cv2.COLOR_RGB2BGR)
            
            if self.__document_type == Database.DRAWING:
                ocr_image_to_search = np.array(get_ocr_page_image(path,pno,self.__pdf_zoom_scale))


                _, image_to_search = cv2.threshold(cv2.cvtColor(image_to_search,cv2.COLOR_RGB2GRAY), 250, 255, cv2.THRESH_BINARY)
                ocr_image_to_search = cv2.cvtColor(ocr_image_to_search,cv2.COLOR_RGB2GRAY)
                _, template_image = cv2.threshold(cv2.cvtColor(raw_template_image,cv2.COLOR_RGB2GRAY), 250, 255, cv2.THRESH_BINARY)
                _, combined_final_mask = cv2.threshold(raw_template_and_text_mask, 250, 255, cv2.THRESH_BINARY)
            
            if self.__document_type == Database.IMAGE:
                self.doc = Project_File_Manager.get_drawing_image_files(path)
                ocr_image_to_search = cv2.imread(self.doc[pno], cv2.IMREAD_UNCHANGED)
                template_image = raw_template_image
                combined_final_mask = raw_template_and_text_mask


        
            self.__test_template_image_black_and_white = template_image
            
            
            # initialize our list of rectangles and probabilties
            rects = []
            probs = []
            flips = []
            rotations = []

            self.__test_default_image = None
            self.__test_cw_90_image = None 
            self.__test_cw_180_image = None 
            self.__test_cw_270_image = None 
            self.__test_flipped_image = None

            for flip in template_flip:
                if flip is not Template_Flip.NONE:
                    _template = cv2.flip(template_image, flip.value)
                    _mask = cv2.flip(combined_final_mask, flip.value)
                else:
                    _template = template_image
                    _mask = combined_final_mask
                for rotation in template_rotate:
                    if rotation is not Template_Rotate.NONE:
                        __template = cv2.rotate(_template, rotation.value)
                        __mask = cv2.rotate(_mask, rotation.value)
                    else:
                        __template = _template
                        __mask = _mask

                    
                    self.__test_progress_string = "Finding linked graphic template for "+str(flip) + " and "+str(rotation)


                    start = time.time()
                    result = scale_invariant_template_matching(image_to_search,__template,__mask
                                                               ,progress=self.update_scanner_string
                                                               ,threshold=self.__config.get_scanning_match_score())
                    scale, scan_result, locations = result
            
                    #cv2.imwrite("result.jpg", res.astype(np.uint8))
                    print(str(time.time()-start))
                    
                    _rects = []
                    _probs = []
                    # loop over the starting (x, y)-coordinates again
                    for pt in zip(*locations[::-1]):
                        # get the probablity for the point
                        probs.append(scan_result[pt[1]][pt[0]])
                        _probs.append(scan_result[pt[1]][pt[0]])
                        # update our list of rectangles
                        rect = (int(pt[0] * scale), int(pt[1] * scale)
                                , int((pt[0] + __template.shape[1]) * scale), int((pt[1] + __template.shape[0]) * scale))
                        rects.append(rect)
                        _rects.append(rect)
                        flips.append(flip)
                        rotations.append(rotation)

                    _pick = non_max_suppression(np.array(_rects),_probs)

                    if self.__document_type == Database.DRAWING:
                        drawn_img = cv2.cvtColor(image_to_search,cv2.COLOR_GRAY2RGB)
                    if self.__document_type == Database.IMAGE:
                        drawn_img = image_to_search.copy()

                    # loop over the final bounding boxes
                    for (startX, startY, endX, endY) in _pick:
                        # draw the bounding box on the image
                        cv2.rectangle(drawn_img, (startX, startY), (endX, endY), (0,0,255), 10)
                    if rotation == rotation.NONE and flip == flip.NONE:
                        self.__test_default_image = drawn_img
                    elif rotation == rotation.CW_90 and flip == flip.NONE:
                        self.__test_cw_90_image = drawn_img
                    elif rotation == rotation.CW_180 and flip == flip.NONE:
                        self.__test_cw_180_image = drawn_img
                    elif rotation == rotation.CW_270 and flip == flip.NONE:
                        self.__test_cw_270_image = drawn_img
                    elif rotation == rotation.NONE and flip == flip.HORIZONTALLY:
                        self.__test_flipped_image = drawn_img


                    #cv2.imshow(str(flip) + " | "+str(rotation), cv2.resize(drawn_img,(1500,int(drawn_img.shape[0]*1500/drawn_img.shape[1]))))
                    #cv2.waitKey(0)
            
            
            # apply non-maxima suppression to the rectangles
            pick = non_max_suppression(np.array(rects),probs)
            pick_indexes = [rects.index(tuple(i)) for i in pick]
            pick_flips = [flips[i] for i in pick_indexes]
            pick_rotations = [rotations[i] for i in pick_indexes]

            print(len(pick))

            if self.__document_type == Database.DRAWING:
                self.__test_result_image = cv2.cvtColor(image_to_search,cv2.COLOR_GRAY2RGB)
            if self.__document_type == Database.IMAGE:
                self.__test_result_image = image_to_search.copy()

            # loop over the final bounding boxes
            for i in range(len(pick)):
                startX, startY, endX, endY = pick[i]
                flip = pick_flips[i]
                rotation = pick_rotations[i]
                # draw the bounding box on the image
                cv2.rectangle(self.__test_result_image, (startX, startY), (endX, endY), (0,0,255), 10)
                cv2.putText(self.__test_result_image,str(flip) + " | "+str(rotation),(startX, startY),cv2.FONT_HERSHEY_SIMPLEX,1,(255,0,0),1,2)
            # cv2.imshow('first', cv2.resize(self.__test_result_image,(1500,int(self.__test_result_image.shape[0]*1500/self.__test_result_image.shape[1]))))
            # cv2.waitKey(0)



            self.__test_text_result_image = None
            if self.__ocr_used:
                self.__test_progress_string = "Starting text extraction via OCR"
            else:
                self.__test_progress_string = "Extracting native text"
            self.__test_text_result_image = self.__get_test_image_text(path,pno,ocr_image_to_search,
                                                pick,pick_flips,pick_rotations,scale)

            self.__test_search_done = True
        except cv2.error as e:
            if e.code == -4:
                self.__test_progress_string = "Failed because of Insufficient Memory. Your system does not have enough RAM to process the current template.\n\nTry creating a larger template."
            else:
                self.__test_progress_string = "Failed to run Test on Page. "+str(e)
            logging.error('Failed to run Test on Page: '+str(e))
            logging.error('Stacktrace: '+traceback.format_exc())
        except Exception as e:
            if str(e) == 'Overly large image':
                self.__test_progress_string = "Failed because of Insufficient Memory. Your system does not have enough RAM to process the current template.\n\nTry creating a larger template."
            else:
                self.__test_progress_string = "Failed to run Test on Page. "+str(e)
            logging.error('Failed to run Test on Page: '+str(e))
            logging.error('Stacktrace: '+traceback.format_exc())


        
       


    
    def __get_test_image_text(self,path,pno,image_to_search, pick, pick_flips, pick_rotations,scale,vertical_direction=BOTTOM_TO_TOP):
        """
        Extracts text from an image and overlays it on the image.

        :param path: The path to the document.
        :type path: str
        :param pno: The page number of the document.
        :type pno: int
        :param image_to_search: The image to search for text.
        :type image_to_search: numpy.ndarray
        :param pick: List of bounding box coordinates for text regions.
        :type pick: List[Tuple[int, int, int, int]]
        :param pick_flips: List of flip directions for each bounding box.
        :type pick_flips: List[Template_Flip]
        :param pick_rotations: List of rotation angles for each bounding box.
        :type pick_rotations: List[float]
        :param scale: The scale factor for resizing the image.
        :type scale: float
        :param vertical_direction: The direction of text extraction (default: BOTTOM_TO_TOP).
        :type vertical_direction: str

        :return: The image with overlaid text.
        :rtype: numpy.ndarray

        Extracts text from the given image using OCR or text extraction from a dictionary.
        The text is then overlaid on the image using bounding box coordinates and other parameters.
        The resulting image with overlaid text is returned.
        """
        text = []

        if scale != 1 and self.__document_type == Database.DRAWING:
            with warnings.catch_warnings():  # suppress DecompressionBombWarning for big image
                warnings.simplefilter('ignore')
                image_to_search=np.array(self.__get_full_page_image_callback_func(self.__pdf_zoom_scale / scale))
                

        if self.__document_type == Database.DRAWING:
            drawn_img = cv2.cvtColor(image_to_search.copy(),cv2.COLOR_GRAY2RGB)
        if self.__document_type == Database.IMAGE:
            drawn_img = image_to_search.copy()
            

        total_number_of_text = len(pick) * len(self.__text_location_dict)
        count = 0 

        for i in range(len(pick)):
            # draw the bounding box on the image
            startX, startY, endX, endY = pick[i]
            flip:Template_Flip = pick_flips[i]
            rotation = pick_rotations[i]

            

            #cv2.rectangle(drawn_img, (startX, startY), (endX, endY), (0,0,255), 10)
            for _, dict in self.__text_location_dict.items():
                count = count + 1
                self.__test_progress_string = "Text extraction using OCR " + str(int(count/total_number_of_text*100)) + "% complete"

                mask_shape = dict['mask_shape']


                
                minY = int(min(l[1] for l in mask_shape))

                # Handles horizontal flips only TODO add vertical flips and rotations if requested
                if flip == Template_Flip.HORIZONTALLY:
                    minX = int(min(l[0] for l in mask_shape))
                    maxX = int(max(l[0] for l in mask_shape))
                    template_length = abs(endX - startX)
                    offset = template_length - maxX
                    mask_shape = list(map((lambda i: (i[0] - minX + offset,
                                            i[1])), mask_shape))

                orginal_width = abs(self.__maxX - self.__minX)
                template_width = abs(endX - startX)

                shape_scale = template_width/orginal_width


                # Translates the shape to the reference point
                vertices = list(map((lambda i: (int(i[0] * shape_scale + startX / scale),
                                        int(i[1] * shape_scale + startY / scale))), mask_shape))


                if not self.__ocr_used:
                    if self.__get_text_on_page_callback_func:
                        text_in_page = self.__get_text_on_page_callback_func()
                    text = find_text_dict_within_roi(vertices,text_in_page,self.__pdf_zoom_scale,scale=scale)
                elif self.__document_type == Database.DRAWING:
                    text, _ = find_text_dict_within_roi_with_ocr(image_to_search,vertices,self.__pdf_zoom_scale,mask_shape,vertical_direction=vertical_direction)
                else:
                    text, _ = find_text_dict_within_image_roi_with_ocr(image_to_search,vertices,1,mask_shape,vertical_direction=vertical_direction)
                    
                while text and text[0]['c'] == ' ':
                    text.pop(0)

                while text and text[-1]['c'] == ' ':
                    text.pop()

                full_text = ""

                for char in text:
                    full_text = full_text + char['c']

                overlay = drawn_img.copy()


                cv_color = self.convert_hex_color_to_rgba_array(dict['color'])
                
                cv2.fillPoly(overlay, np.int32([np.array(vertices)]),cv_color)
                
                alpha = 0.4  # Transparency factor.

                # Following line overlays transparent rectangle over the image
                drawn_img = cv2.addWeighted(overlay, alpha, drawn_img, 1 - alpha, 0)

                minX = int(min(l[0] for l in vertices))
                minY = int(min(l[1] for l in vertices))

                
                cv2.putText(drawn_img,full_text,(minX, minY),cv2.FONT_HERSHEY_SIMPLEX,1,(255,0,0),1,2)
        
        #cv2.imshow('image',cv2.resize(drawn_img,(1500,int(drawn_img.shape[0]*1500/drawn_img.shape[1]))))
        #cv2.waitKey(0)

        return drawn_img
    


if __name__ == '__main__':

    # Override with SPA_SAMPLE_DATA_DIR to point at a different sample image folder.
    sample_data_dir = os.environ.get(
        'SPA_SAMPLE_DATA_DIR',
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data'),
    )

    image = cv2.imread(os.path.join(sample_data_dir, 'tag_template.png'), 0)
    image_to_search = cv2.imread(os.path.join(sample_data_dir, 'search_image.png'), 0)
    mask = cv2.imread(os.path.join(sample_data_dir, 'tag_mask.png'), 0)

    roi = None 
    pno = None
    path = None
    print('Pictures loaded')
    print(cv2.resize(image_to_search, (0,0), fx=0.3, fy=0.3).shape)
    cv2.imwrite("result0.3.jpg", cv2.resize(image_to_search, (0,0), fx=0.3, fy=0.3))
    
    image = cv2.imread(os.path.join(sample_data_dir, 'image_test3.png'), 0)
    linked_graphic_B = Linked_Graphic()
    linked_graphic_B.create_template_image(image)

    roi = None 
    pno = None
    path = None
    image = cv2.imread(os.path.join(sample_data_dir, 'tag_template1.png'), 0)
    image_to_search = cv2.imread(os.path.join(sample_data_dir, 'search_image1.png'), 0)
    mask = cv2.imread(os.path.join(sample_data_dir, 'tag_mask1.png'), 0)
    print('Pictures loaded')
    print(image_to_search.shape)
    

  