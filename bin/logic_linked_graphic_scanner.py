import logging
from math import ceil, floor
import multiprocessing
from os import error
import os
import threading
import time
import traceback
from turtle import right
from typing import Counter, List
import warnings
import cv2
import numpy as np
from imutils.object_detection import non_max_suppression
import concurrent.futures
import imutils
from shapely.geometry import box
import copy
from PIL import Image
from paddleocr import PaddleOCR

from bin.logic_color_ocr_text_boundry_detection import analyze_character_spacing, detect_character_boundaries
from bin.logic_file_manager import Project_File_Manager
from bin.logic_internal_database import Database
from bin.logic_pdf_render import page_count, page_size, render_page
from bin.logic_pdf_text import open_text
logging.getLogger().setLevel('INFO') # PaddleOCR Changes level
import enum
from bin.logic_config import Config

import bin.logic_globals 
from skimage.draw import line
from bin.logic_logger import get_logger
from bin.logic_scale_invariant_template_matching import scale_invariant_template_matching

BOTTOM_TO_TOP = 'bottom_to_top'
TOP_TO_BOTTOM = 'top_to_bottom'

class Template_Flip(enum.Enum):
    NONE = None
    VERTICALLY = 0
    HORIZONTALLY = 1
    VERTICALLY_HORIZONTALLY = -1

    def __str__(self):

        if self==self.NONE:
            return 'No Flip'
        elif self==self.VERTICALLY:
            return 'Vertical Flip'
        elif self==self.HORIZONTALLY:
            return 'Horizontal Flip'
        elif self==self.VERTICALLY_HORIZONTALLY:
            return 'Vertical and Horizontal Flip'

class Template_Rotate(enum.Enum):
    NONE = None
    CW_90 = cv2.ROTATE_90_CLOCKWISE
    CW_180 = cv2.ROTATE_180
    CW_270 = cv2.ROTATE_90_COUNTERCLOCKWISE

    
    def __str__(self):

        if self==self.NONE:
            return 'No Rotation'
        elif self==self.CW_90:
            return 'Clockwise 90 Rotation'
        elif self==self.CW_180:
            return 'Clockwise 180 Rotation'
        elif self==self.CW_270:
            return 'Clockwise 270 Rotation'


def do_something(seconds):
    print(f'Sleeping {seconds} second(s)...')
    time.sleep(seconds)
    return f'Done Sleeping...{seconds}'


def search_page_process(path, index, template,template_and_text_mask, text_locations,ocr_used,pdf_zoom_scale,template_flip,template_rotate, queue
                        , threshold=0.7,scale_factor=1,document_type=Database.DRAWING,use_scale_invariant_config=False):
    retries = 3

    process_logger = get_logger(__name__, queue=queue)
    process_error = None

    for attempt in range(retries):
        try:
            if document_type == Database.IMAGE:
                text_in_page = {}
                files = Project_File_Manager.get_drawing_image_files(path)
                image_to_search = cv2.imread(files[index])

            else:
                
                with open_text(path) as text_doc:
                    text_page = text_doc[index]
                    text_in_page = text_page.chars(text_page.derotation_matrix,
                                                   text_page.rotation_matrix)
                image_to_search = np.array(get_page_image(path,index,pdf_zoom_scale))

            process_logger.info('Searching in page: '+str(index + 1))
            result = search_image(image_to_search,template,template_and_text_mask,path, index, text_locations,text_in_page,ocr_used,pdf_zoom_scale,
                        template_flip=template_flip, template_rotate=template_rotate,threshold=threshold,scale_factor=scale_factor,
                        document_type=document_type,use_scale_invariant_config=use_scale_invariant_config)
            process_logger.info('Done searching in page: '+str(index + 1))
        except Exception as error:
            process_error = error
            process_logger.warning('Exception found while Searching for Template in page {} of path {}. Error: {}'.format(index + 1,path,error))
            process_logger.warning('Stacktrace:'  +traceback.format_exc())
            process_logger.info('Retry {}/{} page {} of path {}.'.format(attempt+1,retries,index + 1,path))
            time.sleep(retries*(index * 10 +  10)) # reduce chance of retires happening at same time
        else:
            return result
    process_logger.error('Failed after retrying {} times. page {} of path {}.'.format(retries,index + 1,path)) 
    raise process_error
        
def is_text_vertical(image):
    inverted = (255 - image)
    cnts,_ = cv2.findContours(inverted, cv2.RETR_EXTERNAL,
	cv2.CHAIN_APPROX_SIMPLE)
    previous_bottom = None
    cnts_indexes = np.argsort([cv2.boundingRect(i)[1] for i in cnts])
    

    for index in cnts_indexes:
        cnt = cnts[index]
        x, y, w, h = cv2.boundingRect(cnt)
        if previous_bottom and previous_bottom < y:
            return True
        elif previous_bottom:
            return False
        previous_bottom = y + h
    return False
    



def _render_page_image(pdf_path, pno, zoom_level, crop_border, target_dimensions, thin_lines):
    """Render a page, optionally clipping to a detected drawing border first."""
    clip = None
    if crop_border:
        from bin.logic_border_detection_cropper import (
            detect_and_crop_border,
            calculate_zoom_for_target_dimensions,
            clip_rect_for_border
        )

        # Step 1: Render at detection zoom to find border
        detection_zoom = 2.0
        img_detect = render_page(pdf_path, pno, zoom=detection_zoom, thin_lines=thin_lines)

        # Step 2: Detect border
        _, border_bbox = detect_and_crop_border(img_detect, debug=False)

        if border_bbox:
            page_rect = page_size(pdf_path, pno)

            # Step 3: Calculate optimal zoom if target dimensions provided
            if target_dimensions:
                zoom_level = calculate_zoom_for_target_dimensions(
                    page_rect, border_bbox, target_dimensions, detection_zoom
                )

            # Step 4: Get clip rectangle
            clip = clip_rect_for_border(page_rect[0], page_rect[1], border_bbox, detection_zoom)

    Image.MAX_IMAGE_PIXELS = None
    return render_page(pdf_path, pno, zoom=zoom_level, clip=clip, thin_lines=thin_lines)


def get_page_image(pdf_path, pno, zoom_level=2, full_page=False, crop_border=False, target_dimensions=None):
    """
    Return an image for a document page with optional border cropping.
    
    :param pdf_path: Path to the PDF to render
    :type pdf_path: str
    :param pno: Zero based page number
    :type pno: int
    :param zoom_level: Zoom level for rendering (ignored if target_dimensions provided with crop_border)
    :type zoom_level: float
    :param full_page: Legacy parameter (unused)
    :type full_page: bool
    :param crop_border: Enable automatic border detection and cropping
    :type crop_border: bool
    :param target_dimensions: Target (width, height) for automatic zoom calculation, requires crop_border=True
    :type target_dimensions: tuple or None
    
    :returns: PIL Image of the page
    :rtype: PIL.Image
    """
    return _render_page_image(pdf_path, pno, zoom_level, crop_border, target_dimensions, thin_lines=False)


def get_ocr_page_image(pdf_path, pno, zoom_level=2, full_page=False, crop_border=False, target_dimensions=None):
    """
    Return an image with line weights disabled for a document page with optional border cropping.
    
    :param pdf_path: Path to the PDF to render
    :type pdf_path: str
    :param pno: Zero based page number
    :type pno: int
    :param zoom_level: Zoom level for rendering (ignored if target_dimensions provided with crop_border)
    :type zoom_level: float
    :param full_page: Legacy parameter (unused)
    :type full_page: bool
    :param crop_border: Enable automatic border detection and cropping
    :type crop_border: bool
    :param target_dimensions: Target (width, height) for automatic zoom calculation, requires crop_border=True
    :type target_dimensions: tuple or None
    
    :returns: PIL Image of the page
    :rtype: PIL.Image
    """
    return _render_page_image(pdf_path, pno, zoom_level, crop_border, target_dimensions, thin_lines=True)


def search_image(image_to_search, template_image, template_and_text_mask, path, index, text_locations, text_in_page, ocr_used, pdf_zoom_scale,
                    template_flip:List[Template_Flip]=[Template_Flip.NONE], template_rotate:List[Template_Rotate]=[Template_Rotate.NONE]
                    ,threshold=0.7,scale_factor=1, document_type=Database.DRAWING,use_scale_invariant_config=False):
    THRESHOLD = 0.70
    DEBUGGING = False

    if document_type == Database.IMAGE:
        files = Project_File_Manager.get_drawing_image_files(path)
        image_to_search = cv2.imread(files[index])

        _image_to_search = image_to_search
        _ocr_image_to_search = cv2.cvtColor(image_to_search,cv2.COLOR_RGB2GRAY)
        _template_image = template_image
        _template_and_text_mask = template_and_text_mask
    else:
        ocr_image_to_search = np.array(get_ocr_page_image(path,index,pdf_zoom_scale))


        _, _image_to_search = cv2.threshold(cv2.cvtColor(image_to_search,cv2.COLOR_RGB2GRAY), 250, 255, cv2.THRESH_BINARY)
        _ocr_image_to_search = cv2.cvtColor(ocr_image_to_search,cv2.COLOR_RGB2GRAY)
        _, _template_image = cv2.threshold(cv2.cvtColor(template_image,cv2.COLOR_RGB2GRAY), 250, 255, cv2.THRESH_BINARY)
        _, _template_and_text_mask = cv2.threshold(template_and_text_mask, 250, 255, cv2.THRESH_BINARY)
    

    
   # initialize our list of rectangles and probabilties
    rects = []
    probs = []
    flips = []
    rotations = []
    template_to_match_ratios = []

    scan_run_times = []    

    for flip in template_flip:
        if flip is not Template_Flip.NONE:
            _template = cv2.flip(_template_image, flip.value)
            _mask = cv2.flip(_template_and_text_mask, flip.value)
        else:
            _template = _template_image
            _mask = _template_and_text_mask
        for rotation in template_rotate:
            if rotation is not Template_Rotate.NONE:
                __template = cv2.rotate(_template, rotation.value)
                __mask = cv2.rotate(_mask, rotation.value)
            else:
                __template = _template
                __mask = _mask


            start = time.time()
            
            # scale factor is used what the size of the template has been determined
            # therefore there is no need to scale the search image
            # Also check config setting for use_scale_invariant
            if scale_factor != 1 or document_type == Database.IMAGE or not use_scale_invariant_config:
                use_scale_invariant = False
            else:
                use_scale_invariant = True

            result = scale_invariant_template_matching(_image_to_search,__template,__mask,page=index
                                                       , threshold=threshold, use_invariant=use_scale_invariant)
            template_to_match_ratio, scan_result, locations = result
            #cv2.imwrite("result.jpg", res.astype(np.uint8))
            #print(str(time.time()-start))
            scan_run_times.append(time.time()-start)
            
            
            _rects = []
            _probs = []
            # loop over the starting (x, y)-coordinates again
            for pt in zip(*locations[::-1]):
                    # get the probablity for the point
                    probs.append(scan_result[pt[1]][pt[0]])
                    _probs.append(scan_result[pt[1]][pt[0]])
                    # update our list of rectangles
                    rect = (int(pt[0] * template_to_match_ratio), int(pt[1] * template_to_match_ratio)
                                , int((pt[0] + __template.shape[1]) * template_to_match_ratio)
                                , int((pt[1] + __template.shape[0]) * template_to_match_ratio))
                    rects.append(rect)
                    _rects.append(rect)
                    flips.append(flip)
                    rotations.append(rotation)
                    template_to_match_ratios.append(template_to_match_ratio)

            _pick = non_max_suppression(np.array(_rects),_probs)

            if DEBUGGING:
                
                drawn_img = cv2.cvtColor(_image_to_search,cv2.COLOR_GRAY2RGB)

                # loop over the final bounding boxes
                for (startX, startY, endX, endY) in _pick:
                    # draw the bounding box on the image
                    cv2.rectangle(drawn_img, (startX, startY), (endX, endY), (0,0,255), 10)
                cv2.imshow('first', cv2.resize(drawn_img,(1500,int(drawn_img.shape[0]*1500/drawn_img.shape[1]))))
                cv2.waitKey(0)

    pick = non_max_suppression(np.array(rects),probs)
    pick_indexes = [rects.index(tuple(i)) for i in pick]
    pick_flips = [flips[i] for i in pick_indexes]
    pick_rotations = [rotations[i] for i in pick_indexes]
    pick_match_ratios = [template_to_match_ratios[i] for i in pick_indexes]
    #print(len(pick))

    if len(_image_to_search.shape) != 3:
        drawn_img = cv2.cvtColor(_image_to_search,cv2.COLOR_GRAY2RGB)
    else:
        drawn_img = _image_to_search

    # loop over the final bounding boxes
    if DEBUGGING:
        pass
        for (startX, startY, endX, endY) in pick:
            # draw the bounding box on the image
            cv2.rectangle(drawn_img, (startX, startY), (endX, endY), (0,0,255), 10)
        cv2.imshow('first', cv2.resize(drawn_img,(1500,int(drawn_img.shape[0]*1500/drawn_img.shape[1]))))
        cv2.waitKey(0)

    #drawn_img = cv2.cvtColor(image_to_search_black_and_white,cv2.COLOR_GRAY2RGB)

    result = []

    previous_template_to_match_ratio = 1
    previous_scale_factor = 1
    # loop over the final bounding boxes
    for i in range(len(pick)):
        # draw the bounding box on the image
        startX, startY, endX, endY = pick[i]
        flip:Template_Flip = pick_flips[i]
        rotation = pick_rotations[i]
        template_to_match_ratio = pick_match_ratios[i]

        if (template_to_match_ratio != previous_template_to_match_ratio 
            or scale_factor != previous_scale_factor ):
            if document_type == Database.IMAGE:
                files = Project_File_Manager.get_drawing_image_files(path)
                image_to_search = cv2.imread(files[index])
                _ocr_image_to_search = image_to_search.copy()
                _image_to_search = cv2.cvtColor(image_to_search,cv2.COLOR_RGB2GRAY)
                
            else:
                with warnings.catch_warnings():  # suppress DecompressionBombWarning for big image
                    warnings.simplefilter('ignore')
                    image_to_search=np.array(get_page_image(path,index,pdf_zoom_scale / template_to_match_ratio / scale_factor))
                    _ocr_image_to_search = image_to_search.copy()
                    _, _image_to_search= cv2.threshold(cv2.cvtColor(image_to_search,cv2.COLOR_RGB2GRAY), 250, 255, cv2.THRESH_BINARY)
                    
            previous_template_to_match_ratio = template_to_match_ratio
            previous_scale_factor = scale_factor


        found_text_locations = []
        #cv2.rectangle(drawn_img, (startX, startY), (endX, endY), (0,0,255), 10)
        for roi_name, dict in text_locations.items():
            mask_shape = dict['mask_shape']
            vertical_direction = BOTTOM_TO_TOP
            if 'vertical_direction' in dict:
                vertical_direction = dict['vertical_direction']

            # Handles horizontal flips only TODO add vertical flips and rotations if requested
            if flip == Template_Flip.HORIZONTALLY:
                minX = int(min(l[0] for l in mask_shape))
                maxX = int(max(l[0] for l in mask_shape))
                template_length = abs(endX - startX)
                offset = template_length - maxX
                mask_shape = list(map((lambda i: (i[0] - minX + offset,
                                        i[1])), mask_shape))

            # Translates the shape to the reference point
            
            vertices = list(map((lambda i: (int(i[0] * scale_factor + startX / template_to_match_ratio),
                                        int(i[1] * scale_factor + startY / template_to_match_ratio))), mask_shape))
            
            
            if not ocr_used:

                text = find_text_dict_within_roi(vertices,text_in_page,pdf_zoom_scale,scale=template_to_match_ratio)

            elif document_type == Database.DRAWING:
                text, _ = find_text_dict_within_roi_with_ocr(_ocr_image_to_search,vertices,pdf_zoom_scale, mask_shape,vertical_direction=vertical_direction)
            else:
                
                text, _ = find_text_dict_within_image_roi_with_ocr(_ocr_image_to_search,vertices,1,mask_shape,vertical_direction=vertical_direction)
        
            
            points = list(map((lambda i: (int((i[0] * scale_factor + startX / template_to_match_ratio) / scale_factor),
                                        int((i[1] * scale_factor + startY / template_to_match_ratio) / scale_factor))), mask_shape))

            while text and text[0]['c'] == ' ':
                text.pop(0)

            while text and text[-1]['c'] == ' ':
                text.pop()

            if document_type == Database.DRAWING:
                zoom_scale = pdf_zoom_scale
            else:
                zoom_scale = 1

            data = {
                'roi_name':roi_name,
                'points':points,
                'text_dict':text,
                'mask_shape':mask_shape,
                'text_roi':get_text_roi(vertices,zoom_scale),
                'pno':index,
                'path':path,
                'color':dict['color'],
                'vertical_direction':vertical_direction
            }

            found_text_locations.append(data)

            if index == 3:
                ()
            #cv2.fillPoly(drawn_img, np.int32([np.array(vertices)]),(255,0,0))
        if document_type == Database.DRAWING:
            points = (startX/pdf_zoom_scale, startY/pdf_zoom_scale, endX/pdf_zoom_scale * scale_factor, endY/pdf_zoom_scale * scale_factor)
        else:
            points = (int(startX), int(startY), int(endX) * scale_factor, int(endY) * scale_factor)

        data = {
            'points': points,
            'confidence':scan_result[int(startY/template_to_match_ratio)][int(startX/template_to_match_ratio)],
            'flip': flip.value,
            'rotation': rotation.value,
            'text_locations': found_text_locations,
            'path': path,
        }

        result.append(data)
    #cv2.imshow('first', cv2.resize(drawn_img,(1500,int(drawn_img.shape[0]*1500/drawn_img.shape[1]))))
    #cv2.waitKey(0)
    #cv2.imwrite('test '+str(index)+'.png', drawn_img)
    average_scan_time_per_page = sum(scan_run_times) / len(scan_run_times)

    return result, index, average_scan_time_per_page, template_to_match_ratio*scale_factor



def create_mask_for_text_location( image, mask):

    stencil = np.zeros(image.shape[:2]).astype(image.dtype)

    minX = int(min(l[0] for l in mask))
    minY = int(min(l[1] for l in mask))

    mask = list(map((lambda i: (i[0] - minX,
                                        i[1] - minY)), mask))
    
    stencil = cv2.fillPoly(stencil, np.int32([np.array(mask)]), 255)
    sel = stencil != 255

    # Determine of gray or color image
    if len(image.shape) == 3:
        # Remove alpha channel if present
        if image.shape[2] == 4: image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
        
        image[sel] = (255, 255, 255)
    else:
        image[sel] = 255

    return image

paddle_ocr = None

def find_text_dict_within_roi_with_ocr(image,text_roi,pdf_zoom, mask, extract_image=True, vertical_direction=BOTTOM_TO_TOP):
    
    minX = min(l[0] for l in text_roi)
    minY = min(l[1] for l in text_roi)
    maxX = max(l[0] for l in text_roi)
    maxY = max(l[1] for l in text_roi)

    

    if extract_image:
        text_image = image[minY:maxY, minX:maxX]
        minX_unscaled = minX / pdf_zoom 
        minY_unscaled = minY / pdf_zoom
    else:
        text_image = image
        minX_unscaled = minX 
        minY_unscaled = minY 

    ocr_padding = 5 # creates a white border to improve ocr results

    text_image = create_mask_for_text_location(text_image,mask)
    text_image = small_top_or_bottom_contour_remover(text_image)

    text_image = add_padding(text_image, ocr_padding)

    original = text_image.copy()
    
    text_image, line_thickness = thicken_lines(text_image)
    text_image, t_added = add_trailing_t_if_two_contours(text_image, line_thickness) 
    text_horizontal = not is_text_vertical(original.copy())
    ocr_result = run_ocr(text_image,original, text_horizontal=text_horizontal, vertical_direction=vertical_direction)
    ocr_result = remove_extra_trailing_t(ocr_result, t_added)
    ocr_result = letter_i_corrective_detector(original,ocr_result)
    ocr_result = remove_padding(ocr_result,ocr_padding)

    char_found_list = []

    if not ocr_result:
        return char_found_list, text_horizontal

    for i in range(len(ocr_result['left'])-1):
        if ocr_result['left'][i+1]< ocr_result['right'][i]:
            new_x = int((ocr_result['right'][i+1] + ocr_result['left'][i]) / 2)
            ocr_result['left'][i+1] = new_x + 1
            ocr_result['right'][i] = new_x - 1
    

    for i in range(len(ocr_result['char'])):
        
        x_1 = ocr_result['left'][i]/pdf_zoom
        y_1 = (text_image.shape[0] - ocr_result['bottom'][i])/pdf_zoom
        x_2 = ocr_result['right'][i]/pdf_zoom
        y_2 = (text_image.shape[0] - ocr_result['top'][i])/pdf_zoom
        data = {
            'origin':(minX_unscaled + x_1,minY_unscaled + y_1),
            'bbox': (minX_unscaled + x_1
                        ,minY_unscaled + y_1
                        ,minX_unscaled + x_2
                        ,minY_unscaled + y_2
                    ),
            'c':ocr_result['char'][i]
        }
        char_found_list.append(data)

    return char_found_list, text_horizontal

def remove_extra_trailing_t(ocr_result, t_added):
    """
    Removes the last character if it is 'T' and t_added is True.

    :param ocr_result: The OCR result dictionary containing character information.
    :type ocr_result: dict
    :param t_added: Boolean indicating if 'T' was added to the image.
    :type t_added: bool

    :returns: The modified OCR result dictionary.
    :rtype: dict
    """
    if not t_added or not ocr_result:
        return ocr_result

    # Remove the last character if it is 'T'
    if ocr_result['char'][-1] == 'T':
        ocr_result['char'].pop()
        ocr_result['left'].pop()
        ocr_result['right'].pop()
        ocr_result['top'].pop()
        ocr_result['bottom'].pop()

    return ocr_result


def add_trailing_t_if_two_contours(text_image, line_thickness):
    """
    Checks if the text image has only two contours and adds a 'T' character at the end if true 
    to improve OCR results for 2 letter images.
    
    :param text_image: The text image to check
    :type text_image: numpy.ndarray
    :param line_thickness: The thickness of the lines in the text image.
    :type line_thickness: int
    
    :returns: Modified image with a 'T' added if needed
    :rtype: numpy.ndarray
    :returns: Boolean indicating if 'T' was added
    :rtype: bool
    """
    # Convert to correct format for contour detection
    if len(text_image.shape) == 3:
        gray_image = cv2.cvtColor(text_image, cv2.COLOR_BGR2GRAY)
    else:
        gray_image = text_image.copy()
    
    # Create inverted image for contour detection
    inverted = cv2.bitwise_not(gray_image)
    
    # Find contours
    cnts, _ = cv2.findContours(inverted, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # If only two contours are found, add a 'T' at the end
    if len(cnts) != 2:
        return text_image, False
        
    # Sort contours left to right
    cnts = sorted(cnts, key=lambda x: cv2.boundingRect(x)[0])
    
    # Get the rightmost contour's properties
    x, y, w, h = cv2.boundingRect(cnts[1])

    # Get the spacing between the last two contours
    spacing = cv2.boundingRect(cnts[1])[0] - (cv2.boundingRect(cnts[0])[0] + cv2.boundingRect(cnts[0])[2])
    
    # Calculate where to add the 'T'
    t_start_x = x + w + spacing  # Add more padding between last character and T
    
    # Create a 'T' with the same height as the existing contours
    t_height = h
    t_width = int(t_height * 0.7)  # T width proportional to height

    # Add an extra buffer of white space after the T
    buffer_size = 10
    if text_image.shape[1] < t_start_x + t_width + buffer_size:
        # Expand the image horizontally if needed
        padding = np.ones((text_image.shape[0], buffer_size), dtype=text_image.dtype) * 255
        text_image = np.hstack((text_image, padding))
    
    # Draw the horizontal part of the T (with more thickness)
    cv2.rectangle(text_image, 
                (t_start_x, y), 
                (t_start_x + t_width, y + line_thickness), 
                0, 
                -1)
    
    # Draw the vertical part of the T (with more thickness)
    vertical_width = line_thickness * 2
    vertical_center = t_start_x + t_width // 2
    cv2.rectangle(text_image, 
                (vertical_center - vertical_width//2, y), 
                (vertical_center + vertical_width//2, y + t_height), 
                0, 
                -1)
        
    return text_image, True

def find_text_dict_within_image_roi_with_ocr(image,text_roi,zoom_scale, mask, extract_image=True, vertical_direction=BOTTOM_TO_TOP):
    
    debug = False

    minX = min(l[0] for l in text_roi)
    minY = min(l[1] for l in text_roi)
    maxX = max(l[0] for l in text_roi)
    maxY = max(l[1] for l in text_roi)

    if debug:
        cv2.rectangle(image, (minX, minY), (maxX, maxY), (0,255,0), 2)
        cv2.imshow("Debug", image)
        cv2.waitKey(0)

    if extract_image:
        minY = max(0, min(image.shape[0], minY))
        minX = max(0, min(image.shape[1], minX))
        maxY = max(0, min(image.shape[0], maxY))
        maxX = max(0, min(image.shape[1], maxX))
        text_image = image[minY:maxY, minX:maxX]
        minX_unscaled = minX / zoom_scale
        minY_unscaled = minY / zoom_scale
    else:
        text_image = image
        minX_unscaled = minX 
        minY_unscaled = minY 

    ocr_padding = 5 # creates a white border to improve ocr results

    # Scale the mask with the zoom scale
    mask = list(map((lambda i: (i[0] * zoom_scale,
                                        i[1] * zoom_scale)), mask))
    
    char_found_list = []
    
    # If text image size is 0 return 
    if text_image.size == 0:
        return char_found_list, False

    text_image = create_mask_for_text_location(text_image,mask)
    
    original = text_image.copy()
    
    ocr_result = run_ocr(text_image,original, vertical_direction=vertical_direction)

    

    if not ocr_result:
        return char_found_list, True

    for i in range(len(ocr_result['left'])-1):
        if ocr_result['left'][i+1]< ocr_result['right'][i]:
            new_x = int((ocr_result['right'][i+1] + ocr_result['left'][i]) / 2)
            ocr_result['left'][i+1] = new_x + 1
            ocr_result['right'][i] = new_x - 1
    

    for i in range(len(ocr_result['char'])):
        
        x_1 = ocr_result['left'][i]/zoom_scale
        y_1 = (text_image.shape[0] - ocr_result['bottom'][i])/zoom_scale
        x_2 = ocr_result['right'][i]/zoom_scale
        y_2 = (text_image.shape[0] - ocr_result['top'][i])/zoom_scale
        data = {
            'origin':(minX_unscaled + x_1,minY_unscaled + y_1),
            'bbox': (minX_unscaled + x_1
                        ,minY_unscaled + y_1
                        ,minX_unscaled + x_2
                        ,minY_unscaled + y_2
                    ),
            'c':ocr_result['char'][i]
        }
        char_found_list.append(data)

    return char_found_list, True


def run_ocr(text_image,original, run_region_correction=True, text_horizontal=True, vertical_direction=BOTTOM_TO_TOP):

    paddle_ocr_result = run_paddle_ocr(text_image, text_horizontal,vertical_direction==BOTTOM_TO_TOP)
    ocr_result = process_paddle_ocr(paddle_ocr_result,text_image)
    if run_region_correction:
        # Convert to gray if not already
        if len(original.shape) == 3:
            original = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)

        ocr_result = paddle_ocr_check_if_start_with_i(original,ocr_result)
        ocr_result = correct_character_regions(ocr_result, original, text_image, paddle_ocr_result, text_horizontal=text_horizontal, vertical_direction=vertical_direction)

    return ocr_result


def paddle_ocr_check_if_start_with_i(image, ocr_result):
    ''' Used to correct issue with paddle ocr detecting character sequences starting with "I"'''
    _, img_w = image.shape[:2]
    inverted = cv2.bitwise_not(image.copy())
    cnts = cv2.findContours(inverted, cv2.RETR_EXTERNAL,
	cv2.CHAIN_APPROX_SIMPLE)
    cnts = imutils.grab_contours(list(cnts))
    cnts = list(cnts)
    cnts.sort(key=lambda x:get_contour_precedence(x, img_w))
    if not cnts or not ocr_result:
        return ocr_result

    cnt = cnts[0]
    # compute the bounding box of the contour and use the
    # bounding box to compute the aspect ratio
    _, _, w, h = cv2.boundingRect(cnt)
    ar = w / float(h)
    # an "I" will have an aspect ratio of less the 0.5 
    if (ar <= 0.3 and ocr_result['char'][0].upper()!= 'I'
            and ocr_result['char'][0].upper()!= 'L'
            and ocr_result['char'][0]!= '1'):
        ocr_result['char'].insert(0,'I')
        ocr_result['left'].insert(0,0)
        ocr_result['right'].insert(0,0)
        ocr_result['top'].insert(0,ocr_result['top'][0])
        ocr_result['bottom'].insert(0,ocr_result['bottom'][0])

    return ocr_result


def run_paddle_ocr(text_image, text_horizontal=True, vertical_text_rotated_up=True):
    global paddle_ocr
    if paddle_ocr is None:
        cwd = os.getcwd()
        # text detection inference model folder
        det_model_dir = r'\Paddle-OCR\det'
        # text recognition inference model
        rec_model_dir = r'\Paddle-OCR\rec'
        # classification inference model
        cls_model_dir = r'\Paddle-OCR\cls'
        paddle_ocr = PaddleOCR(use_angle_cls=True, lang='en',show_log=False, 
                                cls=False, # no text is rotated by 180 degrees, use cls=False to get better performance
                                det_model_dir=cwd + det_model_dir,
                                rec_model_dir=cwd + rec_model_dir,
                                cls_model_dir=cwd + cls_model_dir)
    if not text_horizontal and vertical_text_rotated_up: 
        img = cv2.rotate(text_image.copy(),cv2.ROTATE_90_CLOCKWISE)
    elif not text_horizontal:
        img = cv2.rotate(text_image.copy(),cv2.ROTATE_90_COUNTERCLOCKWISE)
    else: 
        img = text_image.copy()
    
    ocr_result = paddle_ocr.ocr(img, cls=True)
    return ocr_result



def process_paddle_ocr(ocr_results, text_image):
    text_dict = {}
    h, w = text_image.shape[:2]
    if ocr_results and ocr_results[0]:
        try:
            text:str = ocr_results[0][0][1][0]
            start_x = ocr_results[0][0][0][0][0]
            end_x = ocr_results[0][0][0][1][0]
            top_y = ocr_results[0][0][0][0][1]
            bottom_y = ocr_results[0][0][0][2][1]
        
        except IndexError:
            text:str = ocr_results[0][1][0]
            start_x = ocr_results[0][0][0][0]
            end_x = ocr_results[0][0][1][0]
            top_y = ocr_results[0][0][0][1]
            bottom_y = ocr_results[0][0][2][1]
        except IndexError:
            logging.debug(ocr_results)

        # Correction for cases where paddle OCR detects "II" as "="
        if text == "=":
            text = "II"
        
        char_width = int(abs(start_x - end_x)/len(text))

        
        for i in range(len(text)):
            char = text[i].capitalize()
            
            if char == ' ':
                continue


            if not text_dict:
                text_dict['char'] = []
                text_dict['left'] = []
                text_dict['right'] = []
                text_dict['top'] = []
                text_dict['bottom'] = []

            
            text_dict['char'].append(char)
            text_dict['top'].append(h - top_y)
            text_dict['bottom'].append(h - bottom_y)
            text_dict['left'].append(start_x + char_width * i)
            text_dict['right'].append(start_x + char_width * (i+1))
    
    return text_dict 




def correct_character_regions(text_dict, image, text_image
                                , paddle_ocr_result
                                , text_horizontal=True
                                , vertical_direction=BOTTOM_TO_TOP): 
    if not text_dict:
        return text_dict
    
    # Show the cropped image of the text
    minX = int(min(l[0] for l in paddle_ocr_result[0][0][0])) 
    maxX = int(max(l[0] for l in paddle_ocr_result[0][0][0]))
    minY = int(min(l[1] for l in paddle_ocr_result[0][0][0]))
    maxY = int(max(l[1] for l in paddle_ocr_result[0][0][0]))

    image = text_image[minY:maxY, minX:maxX]
    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Determine background color by sampling the image border
    border_pixels = []
    h, w = image.shape[:2]
    
    # Sample top, bottom, left, and right borders
    border_pixels.extend(image[0, :])  # Top row
    border_pixels.extend(image[h-1, :])  # Bottom row
    border_pixels.extend(image[:, 0])  # Left column
    border_pixels.extend(image[:, w-1])  # Right column
    
    # Find the most common value (mode) as the background color
    border_pixels = np.array(border_pixels)
    background_value = int(np.bincount(border_pixels).argmax())

    if background_value > 127:
        _, inverted = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        _, inverted = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cnts,_ = cv2.findContours(inverted, cv2.RETR_EXTERNAL,
	                    cv2.CHAIN_APPROX_SIMPLE)
    
    if cnts:
        # Change the coordinates of the contours to the original image
        for i in range(len(cnts)):
            cnts[i][:, :, 0] += minX
            cnts[i][:, :, 1] += minY

    total_splits_found = {}
    if len(text_dict['char']) != len(cnts):
        total_splits_found, found_all = split_conjoint_characters(cnts, 
                                    text_image, 
                                    len(text_dict['char'])-len(cnts),
                                    text_horizontal)
        if not found_all:
            return text_dict
        

    if text_horizontal:
        cnts_sorted_index = np.argsort([cv2.boundingRect(i)[0] for i in cnts])
    else:
        cnts_sorted_index = np.argsort([-(cv2.boundingRect(i)[1]) for i in cnts])
    max_bounds = get_grand_bounding_box(cnts)
    text_index = 0
    for i in range(len(cnts_sorted_index)):
        
        contour_index = cnts_sorted_index[i]
        
        cnt = cnts[cnts_sorted_index[i]]
        if text_horizontal:
            text_index = build_horizontal_text(text_dict, total_splits_found, text_index, contour_index, cnt)
        else:
            text_index = build_vertical_text(text_dict, total_splits_found, text_index, contour_index, cnt, max_bounds,
                                    text_image.shape[0], vertical_direction)
        
        

    return text_dict



def build_horizontal_text(text_dict, total_splits_found, text_index, contour_index, cnt):
    x,_,w,_ = cv2.boundingRect(cnt)
    if contour_index in total_splits_found:
        for split in total_splits_found[contour_index]:
            if split[0] < split[1]:
                text_dict['left'][text_index] = split[0]
                text_dict['right'][text_index] = split[1]
            else:
                text_dict['left'][text_index] = split[1]
                text_dict['right'][text_index] = split[0]
            text_index = text_index + 1 
    else:
        text_dict['left'][text_index] = x
        text_dict['right'][text_index] = x + w
        text_index = text_index + 1
    
    return text_index


def build_vertical_text(text_dict, total_splits_found, text_index, contour_index, cnt, max_bounds, image_height, vertical_direction):
    # TODO: Write function to handle vertical text
    
    _,y,_,h = cv2.boundingRect(cnt)

    if vertical_direction == TOP_TO_BOTTOM:
        text_dict['char'].reverse()

    if contour_index in total_splits_found:
        total_splits_found[contour_index].reverse()
        for split in total_splits_found[contour_index]:

            if split[0] < split[1]:
                text_dict['top'][text_index] = image_height - split[0]
                text_dict['bottom'][text_index] = image_height - split[1]
                text_dict['left'][text_index] = max_bounds[0]
                text_dict['right'][text_index] = max_bounds[2]
            else:
                text_dict['top'][text_index] = image_height - split[1]
                text_dict['bottom'][text_index] = image_height - split[0]
                text_dict['left'][text_index] = max_bounds[0]
                text_dict['right'][text_index] = max_bounds[2]
            text_index = text_index + 1 
    else:
        
        text_dict['top'][text_index] = image_height - y
        text_dict['bottom'][text_index] = image_height - (y + h)
        text_dict['left'][text_index] = max_bounds[0]
        text_dict['right'][text_index] = max_bounds[2]
        text_index = text_index + 1

    return text_index


def get_grand_bounding_box(contours):
    minX = float('inf')
    minY = float('inf')
    maxX = 0
    maxY = 0
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if minY > y: minY = y 
        if minX > x: minX = x 
        if maxX < (x + w): maxX = x + w
        if maxY < (y + h): maxY = y + h

    return [minX,minY,maxX,maxY]


def split_conjoint_characters(contours, text_image, missing_number, text_horizontal=True):
    total_number_splits_found = 0
    total_splits_found = {}
    if text_horizontal:
        cnts_width_sorted_index = np.argsort([cv2.boundingRect(i)[2] for i in contours])
    else:
        cnts_width_sorted_index = np.argsort([cv2.boundingRect(i)[3] for i in contours])
    cnts_width_sorted_index = cnts_width_sorted_index[::-1]
    for i in range(len(cnts_width_sorted_index)):
        contour_index = cnts_width_sorted_index[i]
        contour = contours[contour_index]
        
        if text_horizontal:
            x,_,w,_ = cv2.boundingRect(contour)
            if x != 0:
                start = x-1
            else:
                start = x


            if x + w != text_image.shape[1]:
                end = x + w + 1
            else:
                end = x + w
        else:
            _,y,_,h = cv2.boundingRect(contour)
            if y != 0:
                start = y-1
            else:
                start = y


            if y + h != text_image.shape[0]:
                end = y + h + 1
            else:
                end = y + h

        

        mask = np.zeros(text_image.shape[:2], dtype="uint8")
        mask = cv2.drawContours(mask,[contour],-1,(255),-1)
        mask = cv2.drawContours(mask,[contour],-1,(255),2)
        
        text_image = cv2.bitwise_not(text_image)
        text_image = cv2.bitwise_and(text_image, text_image, mask=mask)
        
        if text_horizontal:
            extracted_text_image = text_image[0:text_image.shape[0], start:end]
        else:
            extracted_text_image = text_image[start:end, 0:text_image.shape[1]]
        extracted_text_image = cv2.bitwise_not(extracted_text_image)
        extracted_text_image = add_padding(extracted_text_image, 20)
        
        ocr_result = run_ocr(extracted_text_image,None,False,text_horizontal)
        if not ocr_result:
            return total_splits_found, False
        
        splits_found = len(ocr_result['char']) - 1
        
        if splits_found == 0:
            continue

        total_number_splits_found = build_conjoint_character_splits(total_number_splits_found,
                                        total_splits_found, 
                                        start, 
                                        end, 
                                        splits_found,
                                        contour_index) 

        if total_number_splits_found == missing_number:
            break

    if total_number_splits_found != missing_number:
        return total_splits_found, False
    
    return total_splits_found, True



def build_conjoint_character_splits(total_number_splits_found, total_splits_found, start, end, splits_found, contour_index):
    total_number_splits_found = total_number_splits_found + splits_found
        
    splits_width = floor((end - start)/(splits_found + 1))

        
    for i in range(splits_found + 1):  

        if contour_index not in  total_splits_found:
            total_splits_found[contour_index] = []

        total_splits_found[contour_index].append([start + splits_width*i,
                                    start + splits_width*(i + 1)]) 

    return total_number_splits_found
        


def sort_contours(contours):
    # Calculate maximum rectangle height
    c = np.array(contours)
    max_height = np.max(c[::, 3])

    # Sort the contours by y-value
    by_y = sorted(contours, key=lambda x: x[1])  # y values

    line_y = by_y[0][1]       # first y
    line = 1
    by_line = []

    # Assign a line number to each contour
    for x, y, w, h in by_y:
        if y > line_y + max_height:
            line_y = y
            line += 1
            
        by_line.append((line, x, y, w, h))

    # This will now sort automatically by line then by x
    return [(x, y, w, h) for line, x, y, w, h in sorted(by_line)]



        



# Optimum character height for Optical Character Recognition 
PADDLE_OPTIMUM_CHARACTER_HEIGHT = 30 # pixels


def is_optimum_zoom_scale_for_ocr(image):
    img = image.copy()
    # Determine background color by sampling the image border
    border_pixels = []
    h, w = image.shape[:2]
    
    # Sample top, bottom, left, and right borders
    border_pixels.extend(image[0, :])  # Top row
    border_pixels.extend(image[h-1, :])  # Bottom row
    border_pixels.extend(image[:, 0])  # Left column
    border_pixels.extend(image[:, w-1])  # Right column
    
    # Find the most common value (mode) as the background color
    border_pixels = np.array(border_pixels)
    background_value = int(np.bincount(border_pixels).argmax())

    if background_value > 127:
        if image.max() > 1 : inverted = 255 - image 
        else: inverted = cv2.bitwise_not(image.copy())
    else:
        inverted = image.copy()
    cnts = cv2.findContours(inverted, cv2.RETR_EXTERNAL,
	cv2.CHAIN_APPROX_SIMPLE)
    cnts = imutils.grab_contours(list(cnts))
    
    largest_height = 0 
    for cnt in cnts:

        _,_,_,h = cv2.boundingRect(cnt)
        if h > largest_height:
            largest_height = h 

    optimum_character_height = PADDLE_OPTIMUM_CHARACTER_HEIGHT

    if largest_height == 0:
        return True, 1

    optimum_zoom_scale =  optimum_character_height/largest_height

    # return if zoom scale is ok
    if (1.5) > optimum_zoom_scale :
        return True, 1

    return False, optimum_zoom_scale

    



def determine_average_line_thickness(img):
    _, image = cv2.threshold(img, 250, 255, cv2.THRESH_BINARY)
    inverted = cv2.bitwise_not(image)
    _img = cv2.bitwise_not(image.copy())
    img = cv2.distanceTransform(inverted,cv2.DIST_L2,3)
    skel = np.zeros(_img.shape, np.uint8)

    # Get a Cross Shaped Kernel
    element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3,3))

    # Repeat steps 2-4
    while True:
        #Step 2: Open the image
        open = cv2.morphologyEx(_img, cv2.MORPH_OPEN, element)
        #Step 3: Substract open from the original image
        temp = cv2.subtract(_img, open)
        #Step 4: Erode the original image and refine the skeleton
        eroded = cv2.erode(_img, element)
        skel = cv2.bitwise_or(skel,temp)
        _img = eroded.copy()
        # Step 5: If there are no white pixels left ie.. the image has been completely eroded, quit the loop
        if cv2.countNonZero(_img)==0:
            break
    bitwiseAnd = cv2.bitwise_and(img, img, mask=skel)
    
    return bitwiseAnd[np.nonzero(bitwiseAnd)].mean()
    


def thicken_lines(template_image):
    thickness = determine_average_line_thickness(template_image)
    if thickness >= 1.5 or np.isnan(thickness):
        thickness = 1 if np.isnan(thickness) else thickness
        return template_image, int(thickness)
    thickening_runs = int(ceil(1.5 - thickness))
    print(thickness)
    print(thickening_runs)
    template_image = cv2.threshold(template_image, 250, 255, cv2.THRESH_BINARY)[1]
    kernel = np.ones((3, 3), np.uint8)
    template_image = cv2.erode(template_image, kernel, iterations=thickening_runs)
    thickness = determine_average_line_thickness(template_image)
    return template_image, int(thickness)
    

def remove_padding(text_dict, padding):
    if not text_dict:
        return text_dict
    for index in range(len(text_dict['char'])):
        text_dict['left'][index] = text_dict['left'][index] - padding
        text_dict['right'][index] = text_dict['right'][index] - padding
        text_dict['top'][index] = text_dict['top'][index] + padding
        text_dict['bottom'][index] = text_dict['bottom'][index] + padding
    return text_dict


            
def get_text_roi(vertices, zoom=2):
    """
    Get the text region of interest.

    :param vertices: The vertices.
    :type vertices: list
    :param zoom: The zoom.
    :type zoom: int

    :returns: The text region of interest.
    :rtype: list

    This method gets the text region of interest.
    """
    minX = min(l[0] for l in vertices)
    minY = min(l[1] for l in vertices)
    maxX = max(l[0] for l in vertices)
    maxY = max(l[1] for l in vertices)

    minX_scaled = minX / zoom
    minY_scaled = minY / zoom
    maxX_scaled = maxX / zoom
    maxY_scaled = maxY / zoom

    return [[minX_scaled,minY_scaled],[maxX_scaled,minY_scaled],
            [maxX_scaled,maxY_scaled],[minX_scaled,maxY_scaled]]


def small_top_or_bottom_contour_remover(image):
    """ 
    Removes small contours that touches the boundary of the image. 
    
    :param image: The image.
    :type image: numpy.ndarray

    :returns: The image with small contours removed.
    :rtype: numpy.ndarray

    This method removes small contours that touches the boundary of the image.
    """
    cut_off = 2/3 # cut off ratio based on image height
    img_h, _ = image.shape[:2]
    inverted = (255 - image)
    cnts,_ = cv2.findContours(inverted, cv2.RETR_EXTERNAL,
	cv2.CHAIN_APPROX_SIMPLE)

    
    for cnt in cnts:

        _,y,_,h = cv2.boundingRect(cnt)
        if y == 0 and h < cut_off * img_h:
            cv2.drawContours(inverted,[cnt],-1,(0), -1)
        elif y+h == img_h and h < cut_off * img_h:
            cv2.drawContours(inverted,[cnt],-1,(0), -1)


    return cv2.bitwise_not(inverted.copy())
        

def add_padding(image, ocr_padding):
    """
    Add padding to the image.

    :param image: The image.
    :type image: numpy.ndarray
    :param ocr_padding: The padding.
    :type ocr_padding: int

    :returns: The image with padding.
    :rtype: numpy.ndarray

    This method adds padding to the image for OCR.
    """
    return cv2.copyMakeBorder(image
                                , ocr_padding
                                , ocr_padding
                                , ocr_padding
                                , ocr_padding
                                , cv2.BORDER_CONSTANT
                                , value=[255, 255, 255])

def letter_i_corrective_detector(image, ocr_result, check_contour_count = True):
    """
    OCR has an issue detecting P&ID letter "I". This function detects "I" in the text image when OCR is used

    :param image: The image.
    :type image: numpy.ndarray
    :param ocr_result: The OCR result.
    :type ocr_result: dict
    :param check_contour_count: Check if the number of contours is equal to the number of characters.
    :type check_contour_count: bool

    :returns: The OCR result with the letter "I" replaced.
    :rtype: dict

    This method detects the letter "I" in the text image when OCR is used by checking using the aspect ratio of the contour.
    """
    old_ocr_result = copy.deepcopy(ocr_result)
    img_h, img_w = image.shape
    inverted = cv2.bitwise_not(image.copy())
    cnts = cv2.findContours(inverted, cv2.RETR_EXTERNAL,
	cv2.CHAIN_APPROX_SIMPLE)
    cnts = imutils.grab_contours(list(cnts))
    cnts = list(cnts)
    cnts.sort(key=lambda x:get_contour_precedence(x, img_w))
    for c in cnts:
        # compute the bounding box of the contour and use the
        # bounding box to compute the aspect ratio
        (x, y, w, h) = cv2.boundingRect(c)
        ar = w / float(h)
        # an "I" will have an aspect ratio of less the 0.5 
        if ar <= 0.3 :
            ocr_result = replace_with_letter_i(ocr_result,(x, y, w, h),img_h)
    
    if not ocr_result:
        return old_ocr_result

    if len(ocr_result['char']) > len(cnts) and check_contour_count:
        return old_ocr_result

    return ocr_result

def get_single_line_contour_precedence(contour, cols):
    """
    Get the precedence of the contour.

    :param contour: The contour.
    :type contour: numpy.ndarray
    :param cols: The number of columns.
    :type cols: int

    :returns: The precedence of the contour.
    :rtype: int

    This method gets the precedence of the contour by calculating the origin of the contour.
    """
    origin = cv2.boundingRect(contour)
    return origin[0]

def get_contour_precedence(contour, cols):
    """
    Get the precedence of the contour.

    :param contour: The contour.
    :type contour: numpy.ndarray
    :param cols: The number of columns.
    :type cols: int

    :returns: The precedence of the contour.
    :rtype: int

    This method gets the precedence of the contour by calculating the origin of the contour.
    """
    origin = cv2.boundingRect(contour)
    return origin[1] * cols + origin[0]


def replace_with_letter_i( text_dict, location, image_h):
    """
    Replace the detected character with the letter "I".

    :param text_dict: The text dictionary.
    :type text_dict: dict
    :param location: The location of the character.
    :type location: tuple
    :param image_h: The height of the image.
    :type image_h: int

    :returns: The text dictionary with the character replaced.
    :rtype: dict

    This method replaces the detected character with the letter "I" by checking if the character intersects with the letter "I".
    """

    width_I = location[2]

    left = location[0]
    bottom = location[1] + location[3]
    right = location[0] + width_I
    top =  location[1]
    
    if len(text_dict) == 0:
        text_dict['char'] = ['I']
        text_dict['left'] = [left]
        text_dict['bottom'] = [image_h - bottom]
        text_dict['right'] = [right]
        text_dict['top'] = [image_h - top]
        return text_dict

    replaced = False 
    for index in range(len(text_dict['char'])):
        

        ocr_left = text_dict['left'][index]
        ocr_bottom = image_h - text_dict['bottom'][index]
        ocr_right = text_dict['right'][index]
        ocr_top = image_h - text_dict['top'][index] 
        if rect_intersects([left,top,right,bottom],[ocr_left,ocr_top,ocr_right,ocr_bottom]):
            replaced = True 
            if text_dict['char'][index] == 'I' or text_dict['char'][index] == 'J':
                text_dict['char'][index] = 'I'
                text_dict['left'][index] = left
                text_dict['bottom'][index] = image_h - bottom
                text_dict['right'][index] = right
                text_dict['top'][index] = image_h - top
                continue

            if ((text_dict['char'][index] == 'L' and letter_L_starts_at_letter_i(text_dict['left'][index], left, width_I)) 
                or text_dict['char'][index] == 'i'):
                text_dict['char'][index] = 'I'
                text_dict['left'][index] = left
                text_dict['bottom'][index] = image_h - bottom
                text_dict['right'][index] = right
                text_dict['top'][index] = image_h - top
            elif (text_dict['char'][index] == 'L'):
                text_dict['right'][index] = left
                text_dict['char'].append('I')
                text_dict['left'].append(left)
                text_dict['bottom'].append(image_h - bottom)
                text_dict['right'].append(right)
                text_dict['top'].append(image_h - top)
            else: 
                mid = int((text_dict['left'][index] + text_dict['right'][index])/2)
                if left < mid: 
                    text_dict['left'][index] = right
                    text_dict['char'].insert(index,'I')
                    text_dict['left'].insert(index,left)
                    text_dict['bottom'].insert(index,image_h - bottom)
                    text_dict['right'].insert(index,right)
                    text_dict['top'].insert(index,image_h - top)
                    
                else:
                    text_dict['right'][index] = left
                    text_dict['char'].append('I')
                    text_dict['left'].append(left)
                    text_dict['bottom'].append(image_h - bottom)
                    text_dict['right'].append(right)
                    text_dict['top'].append(image_h - top)

    if not replaced and text_dict['right'][index] < right:
        text_dict['char'].append('I')
        text_dict['left'].append(left)
        text_dict['bottom'].append(image_h - bottom)
        text_dict['right'].append(right)
        text_dict['top'].append(image_h - top)

    return text_dict
        
            
def letter_L_starts_at_letter_i(left_L, left_I, width_I):
    ''' Check to see if the letter "L" 
    starts at the same location as the new "I"'''
    return (left_I - width_I) < left_L


def rect_intersects(rect_1, rect_2):
    try:
        a = Rectangle(rect_1[0],rect_1[1],rect_1[2],rect_1[3])
        b = Rectangle(rect_2[0],rect_2[1],rect_2[2],rect_2[3])
    except Exception:
        return False

    if a&b is not None:
        return True 
    return False



def find_text_dict_within_roi(vertices, text_in_page ,zoom=2, scale=1):
    """
    Find the text dictionary within a region of interest.

    :param vertices: The vertices of the region of interest.
    :type vertices: list
    :param text_in_page: The text in the page.
    :type text_in_page: list
    :param zoom: The zoom scale of the PDF.
    :type zoom: float
    :param scale: The scale of the PDF.
    :type scale: float

    :returns: The text dictionary within the region of interest.
    :rtype: list

    This method finds the text dictionary within a region of interest by extracting the text within the bounding box of the region of interest.
    """

    minX = int(min(l[0] for l in vertices))
    minY = int(min(l[1] for l in vertices))
    maxX = int(max(l[0] for l in vertices))
    maxY = int(max(l[1] for l in vertices))

    minX_scaled = int(minX / zoom * scale)
    minY_scaled = int(minY / zoom * scale)
    maxX_scaled = int(maxX / zoom * scale)
    maxY_scaled = int(maxY / zoom * scale)

    derotation_matrix = text_in_page[0]['derotation_matrix']
    rotation_matrix = text_in_page[0]['rotation_matrix']

    # Use the derotation matrix to transform the minX, minY, maxX, maxY coordinates
    minX_scaled, minY_scaled, maxX_scaled, maxY_scaled = transform_bbox((minX_scaled, 
                                                                         minY_scaled, 
                                                                         maxX_scaled, 
                                                                         maxY_scaled), derotation_matrix)

    np_array_of_text = np.array([i['bbox'] for i in text_in_page])

    center_x = (np_array_of_text[:,:1].ravel()+np_array_of_text[:,2:3].ravel())/2
    center_y = (np_array_of_text[:,1:2].ravel()+np_array_of_text[:,3:].ravel())/2

    inidx = np.where(np.logical_and(np.logical_and(minX_scaled <= center_x, center_x <= maxX_scaled),
                                        np.logical_and(minY_scaled <= center_y, center_y <= maxY_scaled)))[0]



    text_in_region = [copy.deepcopy(text_in_page[i]) for i in inidx]

    for text in text_in_region:
        text['bbox'] = transform_bbox(text['bbox'], rotation_matrix)
    
    return text_in_region


def transform_bbox(bbox, matrix):
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

def find_points_of_interest(full_page_image, roi, document_type):
    """
    Finds points of interest along the region of interest (ROI) line segments.

    :returns: A list of points of interest.
    :rtype: list

    :raises: None

    This function finds points of interest along the region of interest (ROI) line segments. It 
    iterates over the ROI line segments and searches for points of interest along each line segment. 
    The points of interest are determined by changes in pixel values along the line segments.
    """
    points_of_interests = []
    
    if document_type != Database.DRAWING:
        return
    
    _, image_to_search_black_and_white = cv2.threshold(cv2.cvtColor(full_page_image,cv2.COLOR_RGB2GRAY), 240, 255, cv2.THRESH_BINARY)
    
    for i in range(len(roi)):
        #if i == 0:
        #    continue
        start = [int(roi[i-1][0]),int(roi[i-1][1])]
        end = [int(roi[i][0]),int(roi[i][1])]

        discrete_line = list(zip(*line(*start, *end)))
        points_of_interests.extend(search_poi_along_line(discrete_line, image_to_search_black_and_white))
    
    return points_of_interests


def search_poi_along_line(line, image):
    """
    Search for points of interest (POI) along a given line.

    :param line: The line to search for POI along.
    :type line: list of tuples

    :return: The points of interest found along the line.
    :rtype: list of tuples

    This function searches for points of interest (POI) along a given line. It converts the full page image to black and white, and then iterates over the line to find the POI. The POI are determined by changes in pixel values along the line.

    Example:
        >>> __search_poi_along_line([(0, 0), (1, 1), (2, 2)])
        [(0, 0), (2, 2)]
    """
    
    
    start = None
    points = []
    for i in range(len(line)):
        point = line[i]
        pixel = image[point[1]*2,point[0]*2]


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


class linked_graphic_scanner():
    """
    Memory-aware multiprocess scanner for graphic documents.
    
    This scanner implements intelligent task scheduling to prevent memory exhaustion
    by limiting concurrent processes based on available system memory and CPU count.
    
    Key improvements:
    - Dynamic worker limit calculation based on available memory
    - Task queue with controlled concurrent execution
    - Memory monitoring with automatic adjustment
    - Conservative memory estimates to prevent OOM errors
    """
    def __init__(self, result_callback, done_callback, config:Config) -> None:
        """
        Initialize the linked graphic scanner.

        :param done_callback: The callback function to be called when the search is done.
        :type done_callback: function
        :param config: The configuration object.
        :type config: Config
        """
        self.__results = []
        self.__results_sent = False
        self.__error_description = ''
        self.__error_found = False
        self.__done_callback = done_callback
        self.__result_callback = result_callback
        self.__config = config
        self.__executor = None
        self.__processed_results = set()  # Track which results have been processed
        self.__completed_results = []     # Store completed results
        # Memory-aware scheduling variables
        self.__task_queue = []
        self.__active_futures = {}
        self.__max_concurrent_tasks = 2  # Conservative default
        self.__task_index = 0

    def _calculate_max_workers(self):
        """Calculate maximum workers based on available memory and CPU count"""
        try:
            import psutil
            # Get available memory in GB
            available_memory_gb = psutil.virtual_memory().available / (1024**3)
            
            # Estimate memory per process (adjust based on your observations)
            # This is conservative - you may need to adjust based on your actual usage
            estimated_memory_per_process_gb = 1.5
            
            # Calculate max processes based on memory
            memory_based_limit = max(1, int(available_memory_gb / estimated_memory_per_process_gb))
            
            # Calculate based on CPU count
            cpu_count = multiprocessing.cpu_count()
            if cpu_count > 4:
                cpu_based_limit = max(2, int(cpu_count / 3))  # More conservative than /2
            else:
                cpu_based_limit = 1
            
            # Take the minimum to be safe
            max_workers = min(memory_based_limit, cpu_based_limit, 4)  # Cap at 4 max
            
            logging.info(f"Available memory: {available_memory_gb:.1f}GB, CPU count: {cpu_count}, Max workers: {max_workers}")
            return max_workers
            
        except ImportError:
            # Fallback if psutil not available
            cpu_count = multiprocessing.cpu_count()
            return max(1, min(2, cpu_count // 2))

    def __submit_next_batch(self):
        """Submit next batch of tasks up to the concurrent limit"""
        while (len(self.__active_futures) < self.__max_concurrent_tasks and 
               self.__task_index < len(self.__task_queue)):
            
            task_args = self.__task_queue[self.__task_index]
            future = self.__executor.submit(search_page_process, *task_args)
            self.__active_futures[future] = self.__task_index
            self.__results[self.__task_index] = future
            self.__task_index += 1

    def __process_completed_tasks(self):
        """Process completed tasks and submit new ones"""
        completed_futures = []
        
        for future in list(self.__active_futures.keys()):
            if future.done():
                completed_futures.append(future)
        
        # Remove completed futures from active list
        for future in completed_futures:
            del self.__active_futures[future]
        
        # Submit next batch of tasks
        self.__submit_next_batch()

    def _monitor_memory_usage(self):
        """Monitor memory usage and adjust concurrent tasks if needed"""
        try:
            import psutil
            memory_percent = psutil.virtual_memory().percent
            
            if memory_percent > 85:  # If memory usage > 85%
                # Reduce concurrent processes
                new_limit = max(1, self.__max_concurrent_tasks - 1)
                if new_limit != self.__max_concurrent_tasks:
                    self.__max_concurrent_tasks = new_limit
                    logging.warning(f"High memory usage ({memory_percent:.1f}%), reducing concurrent tasks to {new_limit}")
                
            elif memory_percent < 60 and self.__max_concurrent_tasks < 4:
                # Increase concurrent processes if memory usage is low
                new_limit = min(4, self.__max_concurrent_tasks + 1)
                if new_limit != self.__max_concurrent_tasks:
                    self.__max_concurrent_tasks = new_limit
                    logging.info(f"Memory usage normal ({memory_percent:.1f}%), increasing concurrent tasks to {new_limit}")
                    
        except ImportError:
            pass  # psutil not available

    #def multiprocess_search_document(self, path, template,template_and_text_mask):
    #    threading.Thread(target=self.__multiprocess_search_document, args=(path, template,template_and_text_mask)).start()

    def multiprocess_search_document(self, path, template,template_and_text_mask, text_locations, ocr_used
                                     , pdf_zoom_scale,template_flip,template_rotate,page_index=None,scale_factor=1,document_type=Database.DRAWING):
        """
        Perform a multiprocess search for a document with memory-aware scheduling.
        
        :param path: The path of the document to be searched.
        :type path: str
        :param template: The template used for searching.
        :type template: str
        :param template_and_text_mask: The template and text mask used for searching.
        :type template_and_text_mask: str
        :param text_locations: The locations of the text to be searched.
        :type text_locations: list
        :param ocr_used: Flag indicating whether OCR is used.
        :type ocr_used: bool
        :param pdf_zoom_scale: The zoom scale of the PDF.
        :type pdf_zoom_scale: float
        :param template_flip: Flag indicating whether the template should be flipped.
        :type template_flip: bool
        :param template_rotate: The rotation angle of the template.
        :type template_rotate: int
        :param page_index: The index of the page to be searched.
        :type page_index: int
        :param scale_factor: The scale factor used to scale the template image before searching. Obtained from a sift match.
        :type scale_factor: float
        :returns: A dictionary containing the control modules matching the given type and path.
        :rtype: dict
        
        Perform a multiprocess search for a document using the given parameters. The function initializes a process pool executor and opens the document. It then submits a search task for each page in the document to the executor. The search task is performed by the search_page_process function.
        
        Example:
        >>> multiprocess_search_document('/path/to/document.pdf', 'template', 'template_and_text_mask', [(10, 20)], True, 1.5, False, 90)
        {'key': 'value'}
        """
        # Calculate memory-aware worker limits
        max_worker = self._calculate_max_workers()
        self.__executor = concurrent.futures.ProcessPoolExecutor(max_workers=max_worker)
        
        # Initialize task scheduling variables
        self.__task_queue = []
        self.__active_futures = {}
        self.__max_concurrent_tasks = min(max_worker, 3)  # Conservative limit
        
        logging.info('Initializing memory-aware scan in document path: {}'.format(path))
        
        # Build task list instead of immediately submitting all tasks
        if page_index is not None and not isinstance(template, list):
            self.__task_queue = [(path, page_index, template, template_and_text_mask, text_locations, ocr_used, 
                                pdf_zoom_scale, template_flip, template_rotate, bin.logic_globals.logger_queue, 
                                self.__config.get_scanning_match_score(), 
                                scale_factor, document_type, self.__config.get_scanning_use_scale_invariant())]
        else:
            if document_type == Database.IMAGE:
                page_total = len(Project_File_Manager.get_drawing_image_files(path))
            else:
                page_total = page_count(path)
                
            if isinstance(template, list):
                self.__task_queue = [(path, index, template[i], template_and_text_mask[i], text_locations, ocr_used,
                                    pdf_zoom_scale, template_flip, template_rotate, bin.logic_globals.logger_queue,
                                    self.__config.get_scanning_match_score(),
                                    scale_factor, document_type, self.__config.get_scanning_use_scale_invariant()) 
                                   for index in range(page_total) for i in range(len(template))]
            else:
                self.__task_queue = [(path, index, template, template_and_text_mask, text_locations, ocr_used,
                                    pdf_zoom_scale, template_flip, template_rotate, bin.logic_globals.logger_queue,
                                    self.__config.get_scanning_match_score(),
                                    scale_factor, document_type, self.__config.get_scanning_use_scale_invariant()) 
                                   for index in range(page_total)]
        
        # Start initial batch of tasks
        self.__results = [None] * len(self.__task_queue)  # Pre-allocate results list
        self.__submit_next_batch()
        
        logging.info('Done initializing memory-aware scan in document path: {} with {} tasks'.format(path, len(self.__task_queue)))
       
    def cancel_search_and_shutdown(self):
        """
        Cancel all tasks and shutdown the executor.
        """
        if self.__results:
            for result in self.__results:
                if result:  # Check if result is not None
                    result.cancel()
        
        if self.__executor:
            self.__executor.shutdown(wait=False)  # Don't wait for completion
            self.__executor = None
        
        self.__results.clear()
        self.__processed_results.clear()
        self.__completed_results.clear()
        self.__task_queue.clear()
        self.__active_futures.clear()
        self.__task_index = 0
        self.__results_sent = False
        self.__error_found = False
        self.__error_description = ''


    def check_multiprocess_search_progress(self):
        """
        Check the progress of a multiprocess search and process completed results.
        :returns: A tuple containing the number of total tasks, number of completed tasks, percentage of completion, 
                  a boolean indicating if the search is done, the error description (if any), and new completed results.
        :rtype: tuple

        This method checks the progress of a multiprocess search and returns a tuple containing the number of total tasks,
        number of completed tasks, percentage of completion, a boolean indicating if the search is done, the error description (if any),
        and any newly completed results since the last check.
        """

        if not self.__results:
            return 0, 0, 0, False, '', []

        # Process completed tasks and submit new ones
        self.__process_completed_tasks()
        
        # Monitor memory usage and adjust concurrency if needed
        self._monitor_memory_usage()

        tasks_done = 0 
        new_results = []
        
        for i, result in enumerate(self.__results):
            if result and result.done():
                tasks_done += 1

                self.__check_for_exceptions(result)
                
                # Process new completed results
                if i not in self.__processed_results:
                    self.__processed_results.add(i)
                    try:
                        completed_result = result.result()
                        self.__completed_results.append(completed_result)
                        new_results.append(completed_result)

                        done = (tasks_done == len(self.__task_queue) and not self.__error_found)
                        
                        # Call individual result callback if provided
                        if self.__result_callback:
                            self.__result_callback(completed_result, done)
                            
                    except Exception as e:
                        logging.error(f"Error retrieving result: {e}")
                        
            

        # Check if all tasks are done
        if tasks_done == len(self.__task_queue) and not self.__error_found:
            done = True
            if self.__done_callback and not self.__results_sent:
                self.__done_callback(self.__completed_results)
                self.__results_sent = True
        else:
            done = False
            
        if len(self.__task_queue) > 0:
            percentage = tasks_done / len(self.__task_queue) * 100
        else:
            percentage = 0

        return len(self.__task_queue), tasks_done, percentage, done, self.__error_description, self.__cancel_search

    def get_completed_results(self):
        """
        Get all completed results so far.
        
        :returns: List of completed results
        :rtype: list
        """
        return self.__completed_results.copy()

    def get_result_by_index(self, index):
        """
        Get a specific result by its index if it's completed.
        
        :param index: The index of the result to retrieve
        :type index: int
        :returns: The result if completed, None otherwise
        :rtype: object or None
        """
        if index < len(self.__results) and self.__results[index].done():
            try:
                return self.__results[index].result()
            except Exception:
                return None
        return None

    def __cancel_search(self):
        """
        Cancels the search operation for each result in the results list.

        :returns: None
        :rtype: None

        This method cancels the search operation for each result in the results list.
        """
        if self.__results:
            for result in self.__results:
                if result:  # Check if result is not None
                    result.cancel()
            # Optionally clear the results list
            self.__results.clear()
            self.__processed_results.clear()
            self.__completed_results.clear()
            self.__task_queue.clear()
            self.__active_futures.clear()
            self.__task_index = 0
            self.__results_sent = False
            self.__error_found = False
            self.__error_description = ''
        if self.__done_callback:
            self.__done_callback()


    def __check_for_exceptions(self, result: concurrent.futures.Future):
        """
        Check for exceptions in the result of a concurrent future.

        :param result: The result of a concurrent future.
        :type result: concurrent.futures.Future

        :returns: None
        :rtype: None

        This method checks for exceptions in the result of a concurrent future and sets the error description if an exception is found.
        """
        if self.__error_found:
            return 
        try:
            error = result.exception(0.01)
            if error:
                self.__cancel_search()
                self.__error_found = True 
                if ((isinstance(error, cv2.error) and error.code == -4) 
                    or str(error) == 'Overly large image' 
                    or str(error) == 'cannot pickle \'SwigPyObject\' object'
                    or 'cv::OutOfMemoryError' in str(error)):
                    self.__error_description = "Failed because of Insufficient Memory. Your system does not have enough RAM to process the current template.\n\nTry creating a larger template."
                else:
                    self.__error_description = "Failed to run scan. Please contact support.\n\nError: "+str(error)
        except concurrent.futures.TimeoutError:
            pass

        



import itertools

class Rectangle:
    def intersection(self, other):
        a, b = self, other
        x1 = max(min(a.x1, a.x2), min(b.x1, b.x2))
        y1 = max(min(a.y1, a.y2), min(b.y1, b.y2))
        x2 = min(max(a.x1, a.x2), max(b.x1, b.x2))
        y2 = min(max(a.y1, a.y2), max(b.y1, b.y2))
        if x1<x2 and y1<y2:
            return type(self)(x1, y1, x2, y2)
    __and__ = intersection

    def difference(self, other):
        inter = self&other
        if not inter:
            yield self
            return
        xs = {self.x1, self.x2}
        ys = {self.y1, self.y2}
        if self.x1<other.x1<self.x2: xs.add(other.x1)
        if self.x1<other.x2<self.x2: xs.add(other.x2)
        if self.y1<other.y1<self.y2: ys.add(other.y1)
        if self.y1<other.y2<self.y2: ys.add(other.y2)
        for (x1, x2), (y1, y2) in itertools.product(
            pairwise(sorted(xs)), pairwise(sorted(ys))
        ):
            rect = type(self)(x1, y1, x2, y2)
            if rect!=inter:
                yield rect
    __sub__ = difference

    def __init__(self, x1, y1, x2, y2):
        if x1>x2 or y1>y2:
            raise ValueError("Coordinates are invalid")
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2

    def __iter__(self):
        yield self.x1
        yield self.y1
        yield self.x2
        yield self.y2

    def __eq__(self, other):
        return isinstance(other, Rectangle) and tuple(self)==tuple(other)
    def __ne__(self, other):
        return not (self==other)

    def __repr__(self):
        return type(self).__name__+repr(tuple(self))


def pairwise(iterable):
    # https://docs.python.org/dev/library/itertools.html#recipes
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)

def main():
    pass

if __name__ == "__main__":
    main()