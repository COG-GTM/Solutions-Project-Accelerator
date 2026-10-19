from collections import deque
from dataclasses import dataclass, field
import math

import pyastar2d
from skimage.draw import line
from shapely.geometry import LineString, Point
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

try:
    from bin.logic_internal_database import Database
    from bin.logic_gfx_to_svg import AnchorDirection
    from bin.logic_pdf_render import page_size, render_page
except Exception as e:
    from logic_internal_database import Database
    from logic_gfx_to_svg import AnchorDirection
    from logic_pdf_render import page_size, render_page
import numpy as np
import cv2
try:
    from scipy.spatial import cKDTree
except ImportError:
    cKDTree = None


PROCESS_LINE_EXTRACTION_PDF_WIDTH = 1300
PROCESS_LINE_EXTRACTION_FILL_COLOR = [0, 255, 0]  # Green
SEGMENT_COLORS = [
    (255, 0, 0), (0, 200, 0), (0, 0, 255),
    (255, 165, 0), (128, 0, 128), (0, 255, 255),
    (255, 0, 255), (128, 128, 0)
]

def get_direction_from_roi(roi, pt):
    """
    Determine the direction of a point relative to a region of interest (ROI).
    
    This function calculates the distance from the point to each edge of the ROI
    and returns the direction corresponding to the closest edge.
    
    Args:
        roi (list): List of points defining the ROI, where each point is [x, y]
        pt (list): The point of interest, format [x, y, ...]
        
    Returns:
        AnchorDirection: The direction from the ROI to the point (TOP, BOTTOM, LEFT, RIGHT)
    """
    # Extract x and y coordinates from all ROI points
    roi_x = [point[0] for point in roi]
    roi_y = [point[1] for point in roi]
    
    # Get the boundaries of the ROI
    left_edge = min(roi_x)
    right_edge = max(roi_x)
    top_edge = min(roi_y)
    bottom_edge = max(roi_y)
    
    # Get the coordinates of the point of interest
    pt_x = pt[0]
    pt_y = pt[1]
    
    # Calculate distance to each edge
    dist_to_left = abs(pt_x - left_edge)
    dist_to_right = abs(pt_x - right_edge)
    dist_to_top = abs(pt_y - top_edge)
    dist_to_bottom = abs(pt_y - bottom_edge)
    
    # Find the minimum distance
    min_distance = min(dist_to_left, dist_to_right, dist_to_top, dist_to_bottom)
    
    # Return the direction corresponding to the closest edge
    if min_distance == dist_to_left:
        return AnchorDirection.LEFT
    elif min_distance == dist_to_right:
        return AnchorDirection.RIGHT
    elif min_distance == dist_to_top:
        return AnchorDirection.TOP
    else:  # min_distance == dist_to_bottom
        return AnchorDirection.BOTTOM

def dilate_erode(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Apply some edge detection or thresholding to get binary image
    _, binary_image = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)

    # Define a kernel size for dilation
    kernel_size = 5 #7
    kernel = np.ones((kernel_size, kernel_size), np.uint8)

    # Dilate the binary image to increase thickness of the lines
    #dilated_image = cv2.dilate(binary_image, kernel, iterations=20)
    eroded = cv2.erode(binary_image, kernel, iterations=1)

    # Convert the dilated image back to BGR to use with original image
    dilated_image_colored = cv2.cvtColor(eroded, cv2.COLOR_GRAY2BGR)

    # Blend the original image with the dilated image to cover gaps
    result = cv2.addWeighted(image, 0.5, dilated_image_colored, 0.5, 0)
    return result 


def read_pdf(pdf_path , pno):
    # Get the original size of the page (in points, 1 point = 1/72 inch)
    original_width, _ = page_size(pdf_path, pno)

    # Set the desired width (2500 pixels) and calculate the scale factor
    scale_factor = PROCESS_LINE_EXTRACTION_PDF_WIDTH / original_width

    # Render the page to an image with the new resolution
    image = cv2.cvtColor(np.array(render_page(pdf_path, pno, zoom=scale_factor)), cv2.COLOR_RGB2BGR)

    return image, scale_factor


def read_poi(internal_db: Database, pdf_path, pno):
    poi_list = []
    roi_list = []
    control_module_roi_dict = {}


    static_graphics = internal_db.get_all_static_graphic_on_page(pdf_path, pno)

    for static_graphic in static_graphics:
        #print(index)
        name = static_graphic['name']
        poi = static_graphic['primary_linked_graphic']['points_of_interests']
        roi = static_graphic['primary_linked_graphic']['roi']
        _pdf_path = static_graphic['primary_linked_graphic']['path']
        spa_id = static_graphic['id']
   
        if pdf_path == _pdf_path: 
            roi_list.append(roi)

        if pdf_path == _pdf_path:
            for idx, pt in enumerate(poi):
                pt.extend([spa_id, name, idx])
                poi_list.append(pt)


    control_modules = internal_db.get_all_control_module_on_page(pdf_path, pno)

    for control_module in control_modules:
        _pdf_path = control_module['primary_linked_graphic']['path']
        name = control_module['name']
        spa_id = control_module['id']
        if pdf_path == _pdf_path:
            roi = control_module['primary_linked_graphic']['roi']
            poi = control_module['primary_linked_graphic']['points_of_interests']
            roi_list.append(roi)
            

            if not control_module['secondary_linked_graphic']:
                control_module_roi_dict[spa_id] = [roi, name, None, 'primary']
                
                for idx, pt in enumerate(poi):
                    poi_direction = get_direction_from_roi(roi, pt)
                    pt.extend([spa_id, name, idx, 'primary', poi_direction])
                    poi_list.append(pt)
                


            else:
                roi = control_module['secondary_linked_graphic']['roi']
                roi_list.append(roi)
                _poi = control_module['secondary_linked_graphic']['points_of_interests']
                for idx, pt in enumerate(_poi):
                    poi_direction = get_direction_from_roi(roi, pt)
                    pt.extend([spa_id, name, idx, 'secondary', poi_direction])
                    poi_list.append(pt)

    
    displays = internal_db.get_all_page_links_on_page(pdf_path, pno)

    processed_page_links = []
    for display in displays:
        name = display['name'] 
        for page_link in display['page_links']:
            if page_link['pno'] != pno:
                continue
            spa_id = page_link['roi_uid']
            _pdf_path = page_link['path']
            if pdf_path == _pdf_path:
                poi = page_link['points_of_interests']
                roi = page_link['roi']
                roi_list.append(roi)
                for idx, pt in enumerate(poi):
                    poi_direction = get_direction_from_roi(roi, pt)
                    pt.extend([spa_id, name, idx, None, poi_direction])
                    poi_list.append(pt)
                processed_page_links.append(spa_id)


        
    displays = internal_db.get_all_hmi_displays_on_page(pdf_path, pno)
    
    if not displays:
        return poi_list, roi_list, control_module_roi_dict
    
    display = displays[0]
    name = display['name'] 

    if 'unlinked_page_links' not in display:
            return poi_list, roi_list, control_module_roi_dict

    for page_link in display['unlinked_page_links']:
        spa_id = page_link['roi_uid']
        _pdf_path = page_link['path']
        if pdf_path == _pdf_path and spa_id not in processed_page_links:
            poi = page_link['points_of_interests']
            roi = page_link['roi']
            roi_list.append(roi)
            for idx, pt in enumerate(poi):
                poi_direction = get_direction_from_roi(roi, pt)
                pt.extend([spa_id, name, idx, None, poi_direction])
                poi_list.append(pt)



    return poi_list, roi_list, control_module_roi_dict

def overlay_red_crosses(gray_image, crosses):
    # Convert grayscale to color image
    color_image = cv2.cvtColor(gray_image, cv2.COLOR_GRAY2BGR)
    # Create a red mask for the crosses
    for cross in crosses:
        red_mask = np.zeros_like(color_image)
        red_mask[cross > 0] = [0, 0, 255]  # Red color
        # Dilate the crosses for better visibility
        #points = np.argwhere(red_mask == [0, 0, 255])
        points = np.argwhere(np.all(red_mask == [0, 0, 255], axis=-1))
        kernel = np.ones((5, 5), np.uint8)
        dilated_crosses = cv2.dilate(cross, kernel, iterations=1)
        # Apply the red mask to the color image
        color_image[dilated_crosses > 0] = [0, 0, 255]  # Red color
    return points, color_image


def detect_crosses(image):
    # Define kernels for cross detection
    size_kernel_list = [5,7,9,11,21,31] #size_kernel needs to be an odd number 
    crosses = []
    for size_kernel in size_kernel_list:
        cross_kernel = np.zeros((size_kernel, size_kernel),int)
        cross_kernel[0,int((size_kernel-1)/2)] = 1
        cross_kernel[int((size_kernel-1)/2),0] = 1
        cross_kernel[int(size_kernel-1),int((size_kernel-1)/2)] = 1
        cross_kernel[int((size_kernel-1)/2),(size_kernel-1)] = 1

        # Apply hit-and-miss transform for each kernel
        crosses_1 = cv2.morphologyEx(image, cv2.MORPH_HITMISS, cross_kernel)
        crosses.append(crosses_1)
    
    return crosses

def find_cross_pts(image):
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    _, bw_img = cv2.threshold(gray_image, 240, 255, cv2.THRESH_BINARY)

    new_bw_img = np.invert(bw_img)
    image = cv2.ximgproc.thinning(new_bw_img)

    #cv2.imshow('thinned_image', image)
    #cv2.waitKey(0)

    # Detect crosses
    crosses = detect_crosses(image)
    cross_points, _ = overlay_red_crosses(image, crosses)
    
    return cross_points 


def add_cross_lines(image, cross_points, margin=5):
    # Create a copy of the image to draw on
    image_with_crosses = image.copy()
    
    # Draw crosses at the detected points
    for point in cross_points:
        y, x = point
        # Draw horizontal line
        cv2.line(image_with_crosses, (x - margin, y), (x + margin, y), (0, 0, 0), 2)
        # Draw vertical line
        cv2.line(image_with_crosses, (x, y - margin), (x, y + margin), (0, 0, 0), 2)
    
    return image_with_crosses


def erase_vertical_region(image, cross_point, erase_thickness, margin, debug=True):
    vert_image = image.copy()
    
    y, x = cross_point
    img_height, img_width = image.shape[:2]
    
    

    # Define the left and right erasing limits with margin
    left_x = max(0, x - erase_thickness)
    right_x = min(img_width, x + erase_thickness )

    vert_image[max(0, y - erase_thickness ): min(img_height, y + erase_thickness),left_x:x-margin] = (255,255,255)  # Erase left, leaving margin
    vert_image[max(0, y - erase_thickness ): min(img_height, y + erase_thickness),x-margin:x+margin] = (0,0,0) # Add this line to keep the original color
    vert_image[max(0, y - erase_thickness ): min(img_height, y + erase_thickness),x+margin:right_x] = (255,255,255)
    
    if debug:
        cv2.imshow('vert_image',vert_image)
        cv2.waitKey(0)
    
    return vert_image 

def erase_horizontal_region(image, cross_point, erase_thickness, margin, debug=True):
    horiz_image = image.copy()
    y, x = cross_point
    img_height, img_width = image.shape[:2]
    
    # Define the top and bottom erasing limits with margin
    top_y = max(0, y - erase_thickness )
    bottom_y = min(img_height, y + erase_thickness)
    
    horiz_image[top_y:y-margin, max(0,x - erase_thickness):min(img_width, x + erase_thickness )] = (255,255,255)  # Erase top, leaving margin
    horiz_image[y-margin:y+margin, max(0,x - erase_thickness):min(img_width, x + erase_thickness )] = (0,0,0) # Add this line to keep the original color
    horiz_image[y+margin:bottom_y, max(0,x - erase_thickness):min(img_width, x + erase_thickness )] = (255,255,255)  # Erase bottom, leaving margin
    
    if debug:
        cv2.imshow('horiz_image',horiz_image)
        cv2.waitKey(0)

    return horiz_image 



def check_cross_fill_connection(check_cross_image, cross_point): 
    new_color =  [0, 255, 0]
    y , x = cross_point
    #new_image = check_cross_image
    if np.array_equal(check_cross_image[y, x], new_color): # Same as fill color 
        return True 
    else:
        return False 


def remove_roi(roi_image, points):
    
    # Convert points to the required format for OpenCV polygon (int32)
    points = np.array(points, dtype=np.int32)
    
    mask = np.zeros(roi_image.shape[:2], dtype=np.uint8)
    # Fill the region defined by the po xints with white (255)
    cv2.fillPoly(mask, [points], 255)
    # Optionally, extract the background color from the region outside the mask
    background_color = (255, 255, 255)  # For example, white background
    # Apply background color to the selected region
    roi_image[mask == 255] = background_color
    
    #cv2.imshow('result',roi_image)
    return roi_image



def flood_fill_analysis(original_image, points_of_int, cross_points, closed_contours=None, debug=True):

    output_list = []
    processed_points = []

    for point in points_of_int:
        if point in processed_points:
            continue
        image = original_image.copy()
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        _, binary_image = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
        image = cv2.cvtColor(binary_image, cv2.COLOR_GRAY2RGB)

        point_data = []

        image_with_crosses = add_cross_lines(image.copy(), cross_points, 10)

        pre_erase_cross_points, pre_erase_points_of_int, pre_erase_contours = flood_fill_analyze(
            image_with_crosses.copy(), point, points_of_int, cross_points, closed_contours, debug)


        for cross_pt in pre_erase_cross_points:
            horizontally_erased_image = erase_horizontal_region(image_with_crosses.copy(), cross_pt, 10, 3, debug)
            horizontal_result = flood_fill_analyze(horizontally_erased_image, point, points_of_int, cross_points, closed_contours, debug)

            for point_of_int in horizontal_result[1]:
                if point_of_int not in pre_erase_points_of_int:
                    pre_erase_points_of_int.append(point_of_int)
            
            for contour_idx in horizontal_result[2]:
                if contour_idx not in pre_erase_contours:
                    pre_erase_contours.append(contour_idx)
            
            vertically_erased_image = erase_vertical_region(image_with_crosses.copy(), cross_pt, 10, 3, debug)
            vertical_result = flood_fill_analyze(vertically_erased_image, point, points_of_int, cross_points, closed_contours, debug)

            for point_of_int in vertical_result[1]:
                if point_of_int not in pre_erase_points_of_int:
                    pre_erase_points_of_int.append(point_of_int)
            
            for contour_idx in vertical_result[2]:
                if contour_idx not in pre_erase_contours:
                    pre_erase_contours.append(contour_idx)

            data = {'cross_point': cross_pt, 
                    'horizontal_result': {
                        'connected_cross_points':horizontal_result[0], 
                        'connected_points_of_int': horizontal_result[1],
                        'connected_contours': horizontal_result[2]
                    },
                    'vertical_result': {
                        'connected_cross_points': vertical_result[0], 
                        'connected_points_of_int': vertical_result[1],
                        'connected_contours': vertical_result[2]
                    }
            }
            point_data.append(data)

        data = {
            'point': point, 'data': point_data,
                       'pre_erase_cross_points': pre_erase_cross_points,
                       'pre_erase_points_of_int': pre_erase_points_of_int,
                       'pre_erase_contours': pre_erase_contours
                       }
        if debug:
            output = process_output(data, original_image.copy(), closed_contours)
        else:
            output = process_output(data, closed_contours=closed_contours)
        processed_points.extend(output['cleaned_points_of_int'])
        output_list.append(output)

    return output_list


def inList(array, list):
    for element in list:
        if np.array_equal(element, array):
            return True
    return False

def process_output(point_data, visaulization_image=None, closed_contours=None):
    """
    Process the output data to clean up points of interest and cross points by removing 
    cross points and points of interest that are not connected to the main point by a vertical or
    horizontal line at the cross point."""

    processed_points = []

    focus_point = point_data['point']
    data = point_data['data']
    pre_erase_cross_points = point_data['pre_erase_cross_points']
    pre_erase_points_of_int = point_data['pre_erase_points_of_int']
    pre_erase_contours = point_data.get('pre_erase_contours', [])

    cross_points_to_remove = []
    point_of_int_to_remove = []
    contours_to_remove = []
    
    for cross_data in data:
        cross_point = cross_data['cross_point']
        horizontal_result = cross_data['horizontal_result']
        vertical_result = cross_data['vertical_result']

        if inList(cross_point, horizontal_result['connected_cross_points']) and not inList(cross_point, vertical_result['connected_cross_points']):
            for pre_erase_cross_point in pre_erase_cross_points:
                if not inList(pre_erase_cross_point, horizontal_result['connected_cross_points']):
                    cross_points_to_remove.append(pre_erase_cross_point)
            for pre_erase_point in pre_erase_points_of_int:
                if pre_erase_point not in horizontal_result['connected_points_of_int']:
                    point_of_int_to_remove.append(pre_erase_point)
            for pre_erase_contour in pre_erase_contours:
                if pre_erase_contour not in horizontal_result.get('connected_contours', []):
                    contours_to_remove.append(pre_erase_contour)
                    
        elif inList(cross_point, vertical_result['connected_cross_points']) and not inList(cross_point, horizontal_result['connected_cross_points']):
            for pre_erase_cross_point in pre_erase_cross_points:
                if not inList(pre_erase_cross_point, vertical_result['connected_cross_points']):
                    cross_points_to_remove.append(pre_erase_cross_point)
            for pre_erase_point in pre_erase_points_of_int:
                if pre_erase_point not in vertical_result['connected_points_of_int']:
                    point_of_int_to_remove.append(pre_erase_point)
            for pre_erase_contour in pre_erase_contours:
                if pre_erase_contour not in vertical_result.get('connected_contours', []):
                    contours_to_remove.append(pre_erase_contour)

    cleaned_cross_points = [cross_point for cross_point in pre_erase_cross_points if not inList(cross_point, cross_points_to_remove)]
    cleaned_points_of_int = [point for point in pre_erase_points_of_int if point not in point_of_int_to_remove and point != focus_point]
    cleaned_contours = [contour for contour in pre_erase_contours if contour not in contours_to_remove]

    if len(processed_points):
        for cleaned_point in cleaned_points_of_int:
            if cleaned_point not in processed_points:
                processed_points.append(cleaned_point)

    # Save the cleaned points of interest and cross points
    data_dict = {
        'point': focus_point,
        'cleaned_cross_points': cleaned_cross_points,
        'cleaned_points_of_int': cleaned_points_of_int,
        'cleaned_contours': cleaned_contours
    }

    if visaulization_image is not None:
        for focus_point in cleaned_points_of_int:
            cv2.circle(visaulization_image, (focus_point[0], focus_point[1]), 5, (0, 255, 0), -1)  # Green circle for cleaned points of interest
        for cross_point in cleaned_cross_points:
            cv2.circle(visaulization_image, (cross_point[1], cross_point[0]), 5, (255, 0, 0), -1)  # Blue circle for cleaned cross points
        
        # Draw connected contours if available
        if closed_contours is not None:
            for i in cleaned_contours:
                cv2.drawContours(visaulization_image, closed_contours, i, (0, 165, 255), 2)  # Orange for connected contours
                
        cv2.imshow('Processed Output', visaulization_image)
        cv2.waitKey(0)

    return data_dict


def flood_fill_analyze(image, flood_fill_point, points_of_int, cross_points, closed_contours=None, debug=True):

    img_height, img_width = image.shape[:2]

    mask = np.zeros((img_height + 2, img_width + 2), np.uint8)

    point = (int(flood_fill_point[0]), int(flood_fill_point[1]))  # Ensure the point is in (x, y) format

    cv2.floodFill(image, mask, point, PROCESS_LINE_EXTRACTION_FILL_COLOR)

    connected_cross_points = []
    connected_points_of_int = []
    connected_contours = []

    count = np.sum(mask)

    if count > 0.5 * img_height * img_width:
        return connected_cross_points, connected_points_of_int, connected_contours

    for cross_pt in cross_points:
        x, y = cross_pt
        if np.array_equal(image[int(x), int(y)], PROCESS_LINE_EXTRACTION_FILL_COLOR):
            connected_cross_points.append(cross_pt)

    for point in points_of_int:
        x, y = point[0], point[1]  # Ensure the point is in (x, y) format
        if np.array_equal(image[int(y), int(x)], PROCESS_LINE_EXTRACTION_FILL_COLOR):
            connected_points_of_int.append(point)
            
    # Check which contours are touched by the flood fill
    if closed_contours is not None:
        for i, contour in enumerate(closed_contours):
            # Check if any point of the contour is filled with the fill color
            for point in contour:
                x, y = point[0][0], point[0][1]  # Contour points are in the format [[x, y]]
                # Make sure the point is within the image boundaries
                if 0 <= y < img_height and 0 <= x < img_width:
                    if np.array_equal(image[int(y), int(x)], PROCESS_LINE_EXTRACTION_FILL_COLOR):
                        connected_contours.append(i)
                        break  # Once we find one point, we know the contour is connected

    if debug:
        # Show the cross points (blue circle) and points of interest (green circle) with the point (red circle)
        
        for cross_pt in connected_cross_points:
            cv2.circle(image, (cross_pt[1],cross_pt[0]), 5, (255, 0, 0), -1)  # Blue circle for cross points
        for poi in connected_points_of_int:
            cv2.circle(image, (poi[0], poi[1]), 5, (255, 255, 0), -1)  # Green circle for points of interest
        cv2.circle(image, (flood_fill_point[0], flood_fill_point[1]), 5, (0, 0, 255), -1)  # Red circle for the point
        
        # Draw connected contours
        if closed_contours is not None:
            for i in connected_contours:
                cv2.drawContours(image, closed_contours, i, (0, 165, 255), 2)  # Orange for connected contours
                
        cv2.imshow('Flood Fill Analysis', image)
        cv2.waitKey(0)

    return connected_cross_points, connected_points_of_int, connected_contours



    

def find_points_of_interest(image, roi_list):
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
        for i in range(len(roi_list)):
            #if i == 0:
            #    continue
            start = [int(roi_list[i-1][0]),int(roi_list[i-1][1])]
            end = [int(roi_list[i][0]),int(roi_list[i][1])]
 
            discrete_line = list(zip(*line(*start, *end)))
            poi = search_poi_along_line(image, discrete_line)
            points_of_interests.append(poi)
        return points_of_interests

 
def search_poi_along_line(image, line):
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
        
        _, image_to_search_black_and_white = cv2.threshold(cv2.cvtColor(image,cv2.COLOR_RGB2GRAY), 240, 255, cv2.THRESH_BINARY)
       
        start = None
        points = []
        for i in range(len(line)):
            point = line[i]
            #print(image_to_search_black_and_white.shape,point[1],point[0] )
            pixel = image_to_search_black_and_white[point[1],point[0]]

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
        #cv2.imshow('')
        return points

def extract_two_element_lists(nested_element):
    # If it's not a list, return an empty list (since we only care about lists)
    if not isinstance(nested_element, list):
        return []
    
    # If it's a list with exactly two elements, return it
    if len(nested_element) == 2 and all(not isinstance(i, list) for i in nested_element):
        return [nested_element]

    # Recursively process each element and collect lists with exactly two elements
    result = []
    for item in nested_element:
        result.extend(extract_two_element_lists(item))
    
    return result

def color_around_pixel(image, center, thickness=5, color=(0, 0, 255)):
    x, y = center
    # Define the top-left and bottom-right corners of the rectangle based on thickness
    top_left = (int(x - thickness), int(y - thickness))
    bottom_right = (int(x + thickness), int(y + thickness))
    
    # Make sure the coordinates are within the image bounds
    height, width = image.shape[:2]
    top_left = (max(0, top_left[0]), max(0, top_left[1]))
    bottom_right = (min(width - 1, bottom_right[0]), min(height - 1, bottom_right[1]))

    # Color the region with the specified color (red in this case)
    cv2.rectangle(image, top_left, bottom_right, color, thickness=-1)  # -1 fills the region


@dataclass
class SlidingWindowNode:
    node_id: str
    kind: str
    position: list
    poi_data: list | None = None


@dataclass
class SlidingWindowEdge:
    edge_id: str
    from_node: str
    to_node: str | None
    path_pixels: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class SlidingWindowTraceState:
    trace_id: str
    source_node: str
    origin_poi_key: tuple
    position_yx: np.ndarray
    direction_yx: np.ndarray
    path_pixels: list = field(default_factory=list)
    steps: int = 0


class SlidingWindowPathGraph:
    def __init__(self, group_idx=None):
        self.group_idx = group_idx
        self.nodes = {}
        self.edges = []

    def add_node(self, node):
        self.nodes[node.node_id] = node
        return node.node_id

    def add_edge(self, edge):
        self.edges.append(edge)
        return edge.edge_id

    def get_node_near(self, position, radius=6.0, exclude_node_id=None):
        x, y = float(position[0]), float(position[1])
        for node in self.nodes.values():
            if exclude_node_id is not None and node.node_id == exclude_node_id:
                continue
            nx, ny = float(node.position[0]), float(node.position[1])
            if math.hypot(nx - x, ny - y) <= radius:
                return node
        return None

    def to_dict(self):
        return {
            'group_idx': self.group_idx,
            'nodes': {
                node_id: {
                    'kind': node.kind,
                    'position': [float(node.position[0]), float(node.position[1])],
                    'poi_data': node.poi_data,
                }
                for node_id, node in self.nodes.items()
            },
            'edges': [
                {
                    'edge_id': edge.edge_id,
                    'from_node': edge.from_node,
                    'to_node': edge.to_node,
                    'path_pixels': [
                        [int(pixel[0]), int(pixel[1])] for pixel in edge.path_pixels
                    ],
                    'metadata': edge.metadata,
                }
                for edge in self.edges
            ],
        }


class SlidingWindowPathTracer:
    def __init__(self, point_group, image, group_idx, window_size=21,
                 step_size=6, snap_radius=10, merge_radius=6,
                 min_component_area=3, max_steps=500, debug=True,
                 poi_cluster_radius=None, poi_cluster_angle_threshold=35.0):
        self.point_group = point_group
        self.group_idx = group_idx
        self.image = image
        self.window_size = max(9, int(window_size) | 1)
        self.half_window = self.window_size // 2
        self.step_size = max(2, int(step_size))
        self.snap_radius = float(snap_radius)
        self.merge_radius = float(merge_radius)
        self.min_component_area = int(min_component_area)
        self.max_steps = int(max_steps)
        self.debug = debug
        if poi_cluster_radius is None:
            poi_cluster_radius = max(self.snap_radius * 2.5, 24.0)
        self.poi_cluster_radius = float(poi_cluster_radius)
        self.poi_cluster_angle_threshold = float(poi_cluster_angle_threshold)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
        self.line_mask = binary < 240
        if hasattr(cv2, 'ximgproc') and hasattr(cv2.ximgproc, 'thinning'):
            thin = cv2.ximgproc.thinning((self.line_mask.astype(np.uint8) * 255))
            self.trace_mask = thin > 0
        else:
            self.trace_mask = self.line_mask.copy()

        self.img_height, self.img_width = self.trace_mask.shape[:2]
        self.graph = SlidingWindowPathGraph(group_idx)
        self.target_pois = [point_group['point'], *point_group.get('cleaned_points_of_int', [])]
        self.poi_nodes = {}
        self.visited_pixels = {}
        self.trace_states = {}
        self.node_counter = 0
        self.edge_counter = 0
        self.trace_counter = 0
        self.attempted_seed_keys = set()

        for poi in self.target_pois:
            self._ensure_poi_node(poi)
        self.root_node_id = self._ensure_poi_node(point_group['point'])

        self._debug_log(
            f"Initialized with {len(self.target_pois)} POIs: "
            f"{', '.join(self._format_poi(poi) for poi in self.target_pois)}")

    def trace(self):
        self._debug_log(
            f"Starting trace from root {self._format_poi(self.point_group['point'])}")
        queue = deque(self._build_seed_states(self.point_group['point']))
        self._debug_log(f"Initial seed state count: {len(queue)}")
        while queue:
            state = queue.popleft()
            for child_state in self._trace_state(state):
                queue.append(child_state)

        unvisited_pois = self._get_unvisited_pois()
        if unvisited_pois:
            self._debug_log(
                "Unconnected POIs after initial pass: "
                + ", ".join(self._format_poi(poi) for poi in unvisited_pois))
        while len(unvisited_pois) > 0:
            next_origin = self._select_next_unvisited_origin(unvisited_pois)
            if next_origin is None:
                self._debug_log(
                    "No valid reseed origin found for remaining POIs: "
                    + ", ".join(self._format_poi(poi) for poi in unvisited_pois))
                break

            self._debug_log(f"Reseeding from {self._format_poi(next_origin)}")
            queue = deque(self._build_seed_states(next_origin))
            self._debug_log(f"Reseed state count: {len(queue)}")
            while queue:
                state = queue.popleft()
                for child_state in self._trace_state(state):
                    queue.append(child_state)

            unvisited_pois = self._get_unvisited_pois()
            if unvisited_pois:
                self._debug_log(
                    "Still-unconnected POIs after reseed: "
                    + ", ".join(self._format_poi(poi) for poi in unvisited_pois))

        self._prune_dead_end_branches()
        self._debug_log(
            f"Trace complete: {len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges")
        if self.debug:
            self._visualize_graph()
        return self.graph

    def _build_seed_states(self, origin):
        seeds = []
        origin_key = self._poi_key(origin)
        self.attempted_seed_keys.add(origin_key)
        origin_node_id = self._ensure_poi_node(origin)
        origin_yx = np.array([float(origin[1]), float(origin[0])], dtype=np.float32)

        self._debug_log(f"Building seeds from {self._format_poi(origin)}")

        for candidate in self._find_seed_directions(origin_yx):
            trace_id = self._next_trace_id()
            start_position = self._advance_to_candidate(origin_yx, candidate)
            start_pixel = self._round_pixel(start_position)
            self.visited_pixels.setdefault(tuple(start_pixel), trace_id)
            self._debug_log(
                f"  Seed {trace_id}: start={self._format_position_yx(start_position)} "
                f"dir={self._format_vector(candidate['direction_yx'])}")
            state = SlidingWindowTraceState(
                trace_id=trace_id,
                source_node=origin_node_id,
                origin_poi_key=origin_key,
                position_yx=start_position,
                direction_yx=candidate['direction_yx'],
                path_pixels=[self._round_pixel(origin_yx), start_pixel],
                steps=1,
            )
            self.trace_states[trace_id] = state
            seeds.append(state)

        if not seeds:
            self._debug_log(f"  No seed directions found for {self._format_poi(origin)}")

        return seeds

    def _get_graph_connected_poi_keys(self):
        connected_keys = set()
        for edge in self.graph.edges:
            for node_id in (edge.from_node, edge.to_node):
                node = self.graph.nodes.get(node_id)
                if node is None or node.kind != 'poi' or node.poi_data is None:
                    continue
                connected_keys.add(self._poi_key(node.poi_data))
        return connected_keys

    def _get_unvisited_pois(self):
        connected_keys = self._get_graph_connected_poi_keys()
        return [
            poi for poi in self.target_pois
            if self._poi_key(poi) not in connected_keys
        ]

    def _select_next_unvisited_origin(self, unvisited_pois):
        for poi in unvisited_pois:
            poi_key = self._poi_key(poi)
            if poi_key in self.attempted_seed_keys:
                self._debug_log(
                    f"Skipping reseed from {self._format_poi(poi)}: already attempted")
                continue
            if self._poi_is_on_visited_pixels(poi):
                self._debug_log(
                    f"Skipping reseed from {self._format_poi(poi)}: overlaps visited pixels")
                continue
            self._debug_log(f"Selected reseed origin {self._format_poi(poi)}")
            return poi
        return None

    def _poi_is_on_visited_pixels(self, poi_data):
        poi_y, poi_x = self._round_pixel([poi_data[1], poi_data[0]])
        radius = max(1, int(math.ceil(self.merge_radius)))
        for check_y in range(max(0, poi_y - radius), min(self.img_height, poi_y + radius + 1)):
            for check_x in range(max(0, poi_x - radius), min(self.img_width, poi_x + radius + 1)):
                if (check_y, check_x) in self.visited_pixels:
                    return True
        return False

    def _trace_state(self, state):
        child_states = []

        self._debug_log(
            f"Trace {state.trace_id} active from {self._format_node(state.source_node)} "
            f"at {self._format_position_yx(state.position_yx)}")

        while state.steps < self.max_steps:
            clustered_pois = self._find_local_unreached_poi_cluster(state)
            if clustered_pois:
                self._debug_log(
                    f"Trace {state.trace_id} found synthetic POI cluster near "
                    f"{self._format_position_yx(state.position_yx)}: "
                    + ", ".join(self._format_poi(poi) for poi in clustered_pois))
                self._create_synthetic_poi_cluster_fork(state, clustered_pois)
                return child_states

            target_node_id = self._find_target_node(state)
            if target_node_id is not None:
                self._debug_log(
                    f"Trace {state.trace_id} hit target {self._format_node(target_node_id)} "
                    f"after {state.steps} steps")
                self._commit_edge(state.source_node, target_node_id,
                                  state.path_pixels,
                                  {'termination': 'poi'})
                return child_states

            merge_node_id = self._find_merge_node(state)
            if merge_node_id is not None:
                self._debug_log(
                    f"Trace {state.trace_id} merged into {self._format_node(merge_node_id)} "
                    f"after {state.steps} steps")
                self._commit_edge(state.source_node, merge_node_id,
                                  state.path_pixels,
                                  {'termination': 'merge'})
                return child_states

            candidates = self._sample_front_components(
                state.position_yx, state.direction_yx)
            if not candidates:
                self._debug_log(
                    f"Trace {state.trace_id} stopped at {self._format_position_yx(state.position_yx)}: "
                    "no forward candidates")
                return child_states

            if len(candidates) == 1:
                candidate = candidates[0]
                next_position = self._advance_to_candidate(
                    state.position_yx, candidate)
                next_pixel = self._round_pixel(next_position)
                if state.path_pixels and next_pixel == state.path_pixels[-1]:
                    self._debug_log(
                        f"Trace {state.trace_id} stalled at {self._format_position_yx(next_position)}")
                    return child_states
                state.position_yx = next_position
                state.direction_yx = candidate['direction_yx']
                state.path_pixels.append(next_pixel)
                self.visited_pixels.setdefault(tuple(next_pixel), state.trace_id)
                state.steps += 1
                if state.steps % 25 == 0:
                    self._debug_log(
                        f"Trace {state.trace_id} advanced to {self._format_position_yx(next_position)} "
                        f"at step {state.steps}")
                continue

            fork_xy = [float(state.position_yx[1]), float(state.position_yx[0])]
            fork_node = self.graph.get_node_near(
                fork_xy, radius=self.merge_radius,
                exclude_node_id=state.source_node)
            if fork_node is None:
                fork_node_id = self._create_node('fork', fork_xy)
            else:
                fork_node_id = fork_node.node_id

            self._debug_log(
                f"Trace {state.trace_id} forked at ({int(round(fork_xy[0]))}, {int(round(fork_xy[1]))}) "
                f"into {len(candidates)} branches")

            self._commit_edge(state.source_node, fork_node_id,
                              state.path_pixels,
                              {'termination': 'fork',
                               'branch_count': len(candidates)})

            fork_pixel = self._round_pixel(state.position_yx)
            for candidate in candidates:
                child_position = self._advance_to_candidate(
                    state.position_yx, candidate)
                child_pixel = self._round_pixel(child_position)
                if child_pixel == fork_pixel:
                    continue
                child_trace_id = self._next_trace_id()
                self.visited_pixels.setdefault(tuple(child_pixel), child_trace_id)
                self._debug_log(
                    f"  Spawned child trace {child_trace_id} from {self._format_node(fork_node_id)} "
                    f"toward {self._format_position_yx(child_position)}")
                child_state = SlidingWindowTraceState(
                    trace_id=child_trace_id,
                    source_node=fork_node_id,
                    origin_poi_key=state.origin_poi_key,
                    position_yx=child_position,
                    direction_yx=candidate['direction_yx'],
                    path_pixels=[fork_pixel, child_pixel],
                    steps=1,
                )
                self.trace_states[child_trace_id] = child_state
                child_states.append(child_state)
            return child_states

        return child_states

    def _find_seed_directions(self, origin_yx):
        patch, min_y, min_x, local_center = self._extract_patch(
            self.trace_mask, origin_yx, self.half_window)
        if patch.size == 0:
            return []

        yy, xx = np.indices(patch.shape)
        dy = yy - local_center[0]
        dx = xx - local_center[1]
        dist = np.sqrt(dy * dy + dx * dx)
        seed_mask = patch & (dist >= max(2.0, self.step_size / 2.0))

        candidates = []
        for centroid in self._component_centroids(seed_mask):
            centroid_yx = np.array([
                min_y + centroid[0],
                min_x + centroid[1],
            ], dtype=np.float32)
            direction = self._normalize(centroid_yx - origin_yx)
            if direction is None:
                continue
            candidates.append({
                'centroid_yx': centroid_yx,
                'direction_yx': direction,
                'score': float(np.linalg.norm(centroid_yx - origin_yx)),
            })

        return self._merge_direction_candidates(candidates)

    def _sample_front_components(self, position_yx, direction_yx):
        patch, min_y, min_x, local_center = self._extract_patch(
            self.trace_mask, position_yx, self.half_window)
        if patch.size == 0:
            return []

        yy, xx = np.indices(patch.shape)
        dy = yy - local_center[0]
        dx = xx - local_center[1]
        proj = dy * direction_yx[0] + dx * direction_yx[1]
        perp = np.abs(dy * direction_yx[1] - dx * direction_yx[0])

        front_mask = patch & (proj >= 1.0) & (perp <= self.half_window)
        if not np.any(front_mask):
            return []

        max_proj = float(np.max(proj[front_mask]))
        band_depth = max(2.0, float(self.step_size))
        leading_mask = front_mask & (proj >= max_proj - band_depth)
        component_mask = leading_mask if np.any(leading_mask) else front_mask

        candidates = []
        for centroid in self._component_centroids(component_mask):
            centroid_yx = np.array([
                min_y + centroid[0],
                min_x + centroid[1],
            ], dtype=np.float32)
            direction = self._normalize(centroid_yx - position_yx)
            if direction is None:
                continue
            if float(np.dot(direction, direction_yx)) <= 0.15:
                continue
            candidates.append({
                'centroid_yx': centroid_yx,
                'direction_yx': direction,
                'score': max_proj,
            })

        return self._merge_direction_candidates(candidates)

    def _find_local_unreached_poi_cluster(self, state):
        if state.steps < 2:
            return []

        current_xy = np.array([float(state.position_yx[1]), float(state.position_yx[0])], dtype=np.float32)
        connected_keys = self._get_graph_connected_poi_keys()
        nearby = []

        for poi in self.target_pois:
            poi_key = self._poi_key(poi)
            if poi_key == state.origin_poi_key or poi_key in connected_keys:
                continue

            poi_xy = np.array([float(poi[0]), float(poi[1])], dtype=np.float32)
            offset_xy = poi_xy - current_xy
            distance = float(np.linalg.norm(offset_xy))
            if distance > self.poi_cluster_radius:
                continue

            direction_yx = self._normalize(np.array([offset_xy[1], offset_xy[0]], dtype=np.float32))
            if direction_yx is None:
                continue
            if float(np.dot(direction_yx, state.direction_yx)) <= -0.15:
                continue

            nearby.append({
                'poi': poi,
                'direction_yx': direction_yx,
                'distance': distance,
            })

        if len(nearby) < 2:
            return []

        max_angle = 0.0
        for idx in range(len(nearby)):
            for jdx in range(idx + 1, len(nearby)):
                angle = self._angle_between(
                    nearby[idx]['direction_yx'],
                    nearby[jdx]['direction_yx'])
                max_angle = max(max_angle, angle)

        if max_angle < self.poi_cluster_angle_threshold:
            return []

        return [item['poi'] for item in sorted(nearby, key=lambda item: item['distance'])]

    def _create_synthetic_poi_cluster_fork(self, state, clustered_pois):
        fork_xy = [float(state.position_yx[1]), float(state.position_yx[0])]
        existing_node = self.graph.get_node_near(
            fork_xy, radius=self.merge_radius,
            exclude_node_id=state.source_node)
        if existing_node is None or existing_node.kind == 'poi':
            fork_node_id = self._create_node('fork', fork_xy)
        else:
            fork_node_id = existing_node.node_id

        self._commit_edge(
            state.source_node,
            fork_node_id,
            state.path_pixels,
            {
                'termination': 'synthetic-fork-cluster',
                'cluster_size': len(clustered_pois),
            },
        )

        fork_pixel = self._round_pixel(state.position_yx)
        for poi in clustered_pois:
            poi_key = self._poi_key(poi)
            target_node_id = self.poi_nodes.get(poi_key)
            if target_node_id is None:
                continue

            connector_pixels = self._build_connector_path(
                fork_pixel,
                [int(round(float(poi[1]))), int(round(float(poi[0])))],
            )
            self._debug_log(
                f"  Synthetic cluster connector from {self._format_node(fork_node_id)} "
                f"to {self._format_node(target_node_id)}")
            self._commit_edge(
                fork_node_id,
                target_node_id,
                connector_pixels,
                {
                    'termination': 'poi-cluster',
                    'cluster_origin': state.trace_id,
                },
            )

    def _find_target_node(self, state):
        if state.steps < 2:
            return None

        current_xy = [float(state.position_yx[1]), float(state.position_yx[0])]
        best_distance = None
        best_node_id = None

        for poi in self.target_pois:
            poi_key = self._poi_key(poi)
            if poi_key == state.origin_poi_key:
                continue
            distance = math.hypot(float(poi[0]) - current_xy[0],
                                  float(poi[1]) - current_xy[1])
            if distance <= self.snap_radius and (
                    best_distance is None or distance < best_distance):
                best_distance = distance
                best_node_id = self.poi_nodes.get(poi_key)

        return best_node_id

    def _find_merge_node(self, state):
        if state.steps < 3:
            return None

        source_node = self.graph.nodes.get(state.source_node)
        if source_node is None:
            return None

        current_xy = [float(state.position_yx[1]), float(state.position_yx[0])]
        if math.hypot(source_node.position[0] - current_xy[0],
                      source_node.position[1] - current_xy[1]) <= self.merge_radius:
            return None

        py, px = self._round_pixel(state.position_yx)
        radius = max(1, int(math.ceil(self.merge_radius / 2.0)))
        for check_y in range(max(0, py - radius), min(self.img_height, py + radius + 1)):
            for check_x in range(max(0, px - radius), min(self.img_width, px + radius + 1)):
                visited_owner = self.visited_pixels.get((check_y, check_x))
                if visited_owner is None or visited_owner == state.trace_id:
                    continue
                existing = self.graph.get_node_near(
                    [float(check_x), float(check_y)],
                    radius=self.merge_radius,
                    exclude_node_id=state.source_node)
                if existing is not None:
                    return existing.node_id

                merge_node_id = self._create_node('merge', [float(check_x), float(check_y)])
                self._debug_log(
                    f"Trace {state.trace_id} encountered visited owner {visited_owner} "
                    f"at ({check_x},{check_y})")
                if isinstance(visited_owner, str) and visited_owner.startswith('edge_'):
                    self._connect_merge_node_to_edge(
                        merge_node_id, visited_owner, [check_y, check_x])
                elif isinstance(visited_owner, str) and visited_owner.startswith('trace_'):
                    self._connect_merge_node_to_trace(
                        merge_node_id, visited_owner, [check_y, check_x])
                return merge_node_id

        return None

    def _advance_to_candidate(self, position_yx, candidate):
        centroid_yx = candidate['centroid_yx']
        direction_yx = candidate['direction_yx']
        centroid_distance = float(np.linalg.norm(centroid_yx - position_yx))
        step_distance = min(max(1.0, centroid_distance), float(self.step_size))
        proposed = position_yx + direction_yx * step_distance
        return self._snap_to_line(proposed, radius=max(2, self.step_size))

    def _extract_patch(self, mask, center_yx, half_window):
        center_pixel = self._round_pixel(center_yx)
        min_y = max(0, center_pixel[0] - half_window)
        max_y = min(self.img_height, center_pixel[0] + half_window + 1)
        min_x = max(0, center_pixel[1] - half_window)
        max_x = min(self.img_width, center_pixel[1] + half_window + 1)
        patch = mask[min_y:max_y, min_x:max_x]
        local_center = np.array([
            center_pixel[0] - min_y,
            center_pixel[1] - min_x,
        ], dtype=np.float32)
        return patch, min_y, min_x, local_center

    def _component_centroids(self, component_mask):
        label_count, _, stats, centroids = cv2.connectedComponentsWithStats(
            component_mask.astype(np.uint8), connectivity=8)
        found = []
        for label_idx in range(1, label_count):
            if stats[label_idx, cv2.CC_STAT_AREA] < self.min_component_area:
                continue
            centroid_x, centroid_y = centroids[label_idx]
            found.append(np.array([centroid_y, centroid_x], dtype=np.float32))
        return found

    def _merge_direction_candidates(self, candidates, angle_tolerance=18.0):
        unique = []
        for candidate in sorted(candidates, key=lambda item: item['score'], reverse=True):
            is_duplicate = False
            for existing in unique:
                if self._angle_between(candidate['direction_yx'],
                                       existing['direction_yx']) <= angle_tolerance:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique.append(candidate)
        return unique

    def _angle_between(self, vec_a, vec_b):
        dot = float(np.clip(np.dot(vec_a, vec_b), -1.0, 1.0))
        return math.degrees(math.acos(dot))

    def _normalize(self, vector):
        norm = float(np.linalg.norm(vector))
        if norm <= 1e-6:
            return None
        return vector / norm

    def _build_connector_path(self, start_yx, end_yx):
        rr, cc = line(
            int(start_yx[0]), int(start_yx[1]),
            int(end_yx[0]), int(end_yx[1]))
        connector = []
        for py, px in zip(rr, cc):
            if self._in_bounds(int(py), int(px)):
                connector.append([int(py), int(px)])
        return connector

    def _snap_to_line(self, position_yx, radius=4):
        patch, min_y, min_x, local_center = self._extract_patch(
            self.trace_mask, position_yx, radius)
        points = np.argwhere(patch)
        if len(points) == 0:
            return np.array([
                float(np.clip(position_yx[0], 0, self.img_height - 1)),
                float(np.clip(position_yx[1], 0, self.img_width - 1)),
            ], dtype=np.float32)

        distances = np.linalg.norm(points - local_center, axis=1)
        snapped = points[int(np.argmin(distances))]
        return np.array([
            float(min_y + snapped[0]),
            float(min_x + snapped[1]),
        ], dtype=np.float32)

    def _ensure_poi_node(self, poi_data):
        poi_key = self._poi_key(poi_data)
        if poi_key in self.poi_nodes:
            return self.poi_nodes[poi_key]

        node_id = self._create_node('poi', [float(poi_data[0]), float(poi_data[1])],
                                    poi_data=poi_data)
        self.poi_nodes[poi_key] = node_id
        return node_id

    def _create_node(self, kind, position_xy, poi_data=None):
        node_id = f"{kind}_{self.group_idx}_{self.node_counter}"
        self.node_counter += 1
        self.graph.add_node(SlidingWindowNode(
            node_id=node_id,
            kind=kind,
            position=[float(position_xy[0]), float(position_xy[1])],
            poi_data=poi_data,
        ))
        return node_id

    def _get_edge_by_id(self, edge_id):
        for edge in self.graph.edges:
            if edge.edge_id == edge_id:
                return edge
        return None

    def _connect_merge_node_to_edge(self, merge_node_id, edge_id, merge_pixel):
        edge = self._get_edge_by_id(edge_id)
        if edge is None or edge.to_node is None:
            self._debug_log(
                f"Merge node {self._format_node(merge_node_id)} could not attach to {edge_id}")
            return

        for existing_edge in self.graph.edges:
            if existing_edge.from_node == merge_node_id and existing_edge.to_node == edge.to_node:
                return

        if not edge.path_pixels:
            connector_pixels = [merge_pixel]
        else:
            merge_yx = np.array(merge_pixel, dtype=np.float32)
            edge_pixels = np.array(edge.path_pixels, dtype=np.float32)
            distances = np.linalg.norm(edge_pixels - merge_yx, axis=1)
            nearest_idx = int(np.argmin(distances))
            connector_pixels = edge.path_pixels[nearest_idx:]
            if not connector_pixels:
                connector_pixels = [merge_pixel]

        self._debug_log(
            f"Attaching {self._format_node(merge_node_id)} to downstream edge {edge_id} "
            f"toward {self._format_node(edge.to_node)}")
        self._commit_edge(
            merge_node_id,
            edge.to_node,
            connector_pixels,
            {
                'termination': 'merge-connector',
                'source_edge': edge_id,
            },
        )

    def _connect_merge_node_to_trace(self, merge_node_id, trace_id, merge_pixel):
        trace_state = self.trace_states.get(trace_id)
        if trace_state is None:
            self._debug_log(
                f"Merge node {self._format_node(merge_node_id)} could not attach to {trace_id}")
            return

        if trace_state.source_node not in self.graph.nodes:
            return

        for existing_edge in self.graph.edges:
            if (existing_edge.from_node == trace_state.source_node
                    and existing_edge.to_node == merge_node_id):
                return

        owner_pixels = self._normalize_path_pixels(trace_state.path_pixels)
        if not owner_pixels:
            owner_pixels = [merge_pixel]

        merge_yx = np.array(merge_pixel, dtype=np.float32)
        edge_pixels = np.array(owner_pixels, dtype=np.float32)
        distances = np.linalg.norm(edge_pixels - merge_yx, axis=1)
        nearest_idx = int(np.argmin(distances))
        connector_pixels = owner_pixels[:nearest_idx + 1]
        if not connector_pixels:
            connector_pixels = [merge_pixel]

        self._debug_log(
            f"Attaching {self._format_node(merge_node_id)} to downstream trace {trace_id} "
            f"from {self._format_node(trace_state.source_node)}")
        self._commit_edge(
            trace_state.source_node,
            merge_node_id,
            connector_pixels,
            {
                'termination': 'trace-connector',
                'source_trace': trace_id,
            },
        )

    def _commit_edge(self, from_node, to_node, path_pixels, metadata=None):
        if from_node == to_node:
            return None

        pixels = self._normalize_path_pixels(path_pixels)
        if from_node in self.graph.nodes:
            source_xy = self.graph.nodes[from_node].position
            source_pixel = [int(round(source_xy[1])), int(round(source_xy[0]))]
            if not pixels or pixels[0] != source_pixel:
                pixels.insert(0, source_pixel)

        if to_node in self.graph.nodes:
            target_xy = self.graph.nodes[to_node].position
            target_pixel = [int(round(target_xy[1])), int(round(target_xy[0]))]
            if not pixels or pixels[-1] != target_pixel:
                pixels.append(target_pixel)

        if len(pixels) < 2:
            return None

        edge_id = f"edge_{self.group_idx}_{self.edge_counter}"
        self.edge_counter += 1
        self.graph.add_edge(SlidingWindowEdge(
            edge_id=edge_id,
            from_node=from_node,
            to_node=to_node,
            path_pixels=pixels,
            metadata=metadata or {},
        ))

        self._debug_log(
            f"Committed edge {edge_id}: {self._format_node(from_node)} -> "
            f"{self._format_node(to_node)} ({len(pixels)} px, "
            f"termination={self.graph.edges[-1].metadata.get('termination')})")

        for py, px in pixels:
            self.visited_pixels[(py, px)] = edge_id
        return edge_id

    def _normalize_path_pixels(self, path_pixels):
        pixels = []
        for pixel in path_pixels:
            py, px = self._round_pixel(pixel)
            if not self._in_bounds(py, px):
                continue
            current = [py, px]
            if not pixels or pixels[-1] != current:
                pixels.append(current)
        return pixels

    def _prune_dead_end_branches(self):
        incoming = {}
        outgoing = {}
        for edge in self.graph.edges:
            incoming.setdefault(edge.to_node, []).append(edge)
            outgoing.setdefault(edge.from_node, []).append(edge)

        reached_targets = {
            node_id for node_id, node in self.graph.nodes.items()
            if node.kind == 'poi'
            and node_id != self.root_node_id
            and (incoming.get(node_id) or outgoing.get(node_id))
        }
        if not reached_targets:
            self._debug_log(
                f"Pruning all edges: no reached targets beyond root {self._format_node(self.root_node_id)}")
            self.graph.edges = []
            self.graph.nodes = {
                node_id: node
                for node_id, node in self.graph.nodes.items()
                if node_id == self.root_node_id
            }
            return

        self._debug_log(
            "Reached targets before pruning: "
            + ", ".join(self._format_node(node_id) for node_id in sorted(reached_targets)))

        keep_nodes = {self.root_node_id, *reached_targets}
        keep_edges = set()
        queue = deque(reached_targets)
        while queue:
            node_id = queue.popleft()
            for edge in incoming.get(node_id, []):
                if edge.edge_id in keep_edges:
                    continue
                keep_edges.add(edge.edge_id)
                if edge.from_node not in keep_nodes:
                    keep_nodes.add(edge.from_node)
                    queue.append(edge.from_node)

            node = self.graph.nodes.get(node_id)
            if node is None:
                continue
            if node.kind != 'poi' and node_id != self.root_node_id:
                continue

            for edge in outgoing.get(node_id, []):
                if edge.edge_id in keep_edges:
                    continue
                keep_edges.add(edge.edge_id)
                if edge.to_node not in keep_nodes:
                    keep_nodes.add(edge.to_node)
                    queue.append(edge.to_node)

        self.graph.edges = [
            edge for edge in self.graph.edges if edge.edge_id in keep_edges
        ]
        self.graph.nodes = {
            node_id: node
            for node_id, node in self.graph.nodes.items()
            if node_id in keep_nodes
        }

        self._debug_log(
            f"After pruning: kept {len(self.graph.nodes)} nodes and {len(self.graph.edges)} edges")

    def _visualize_graph(self):
        viz = self.image.copy()
        for edge in self.graph.edges:
            edge_pixels = np.array(edge.path_pixels, dtype=np.int32)
            if len(edge_pixels) < 2:
                continue
            pts_xy = np.flip(edge_pixels, axis=1).reshape((-1, 1, 2))
            cv2.polylines(viz, [pts_xy], False, (0, 255, 255), 2)

        for node in self.graph.nodes.values():
            x, y = int(node.position[0]), int(node.position[1])
            if node.kind == 'poi':
                color = (0, 255, 0)
            elif node.kind == 'fork':
                color = (0, 0, 255)
            else:
                color = (0, 255, 255)
            cv2.circle(viz, (x, y), 5, color, -1)
            cv2.putText(viz, node.kind[:1].upper(), (x + 4, y - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)

        cv2.imshow(
            f'Sliding Window Path Graph - Group {self.group_idx}',
            cv2.resize(viz, (1300, int(viz.shape[0] * 1300 / viz.shape[1]))))
        cv2.waitKey(0)

    def _poi_key(self, poi_data):
        spa_id = poi_data[2] if len(poi_data) > 2 else None
        poi_idx = poi_data[4] if len(poi_data) > 4 else None
        return (int(round(poi_data[0])), int(round(poi_data[1])), spa_id, poi_idx)

    def _next_trace_id(self):
        trace_id = f"trace_{self.group_idx}_{self.trace_counter}"
        self.trace_counter += 1
        return trace_id

    def _round_pixel(self, position_yx):
        return [
            int(round(float(position_yx[0]))),
            int(round(float(position_yx[1]))),
        ]

    def _in_bounds(self, py, px):
        return 0 <= py < self.img_height and 0 <= px < self.img_width

    def _debug_log(self, message):
        if self.debug:
            print(f"[SlidingWindow g{self.group_idx}] {message}")

    def _format_poi(self, poi_data):
        x = int(round(float(poi_data[0])))
        y = int(round(float(poi_data[1])))
        if len(poi_data) > 3 and poi_data[3] is not None:
            return f"{poi_data[3]}@({x},{y})"
        return f"poi@({x},{y})"

    def _format_node(self, node_id):
        node = self.graph.nodes.get(node_id)
        if node is None:
            return str(node_id)
        if node.kind == 'poi' and node.poi_data is not None:
            return f"{node_id}:{self._format_poi(node.poi_data)}"
        x = int(round(node.position[0]))
        y = int(round(node.position[1]))
        return f"{node_id}:{node.kind}@({x},{y})"

    def _format_position_yx(self, position_yx):
        y = int(round(float(position_yx[0])))
        x = int(round(float(position_yx[1])))
        return f"({x},{y})"

    def _format_vector(self, vector_yx):
        return f"({float(vector_yx[1]):.2f}, {float(vector_yx[0]):.2f})"


def trace_sliding_window_path_graphs(output_list, image, debug=True):
    graph_results = []

    for group_idx, point_group in enumerate(output_list):
        if not point_group.get('cleaned_points_of_int'):
            continue
        tracer = SlidingWindowPathTracer(point_group, image, group_idx,
                                         debug=debug)
        graph = tracer.trace()
        graph_data = graph.to_dict()
        graph_data['root_point'] = point_group['point']
        graph_data['line_type'] = point_group.get('line_type')
        graph_results.append(graph_data)

    return graph_results



def ProcessLinesExtractor(pdf_path, pno, internal_db):

    debug = False

    # Get the points of interest from the JSON file
    page_poi, roi_points, control_module_roi_dict = read_poi(internal_db, pdf_path, pno)
    
    # Get the pdf images
    image, scale_factor = read_pdf(pdf_path, pno)

    page_poi = [[int(poi[0] * scale_factor), int(poi[1] * scale_factor), *poi[2:]] for poi in page_poi]

    # Scale control module ROI coordinates
    for module_id, data in control_module_roi_dict.items():
        roi = data[0]  # Get the ROI points
        scaled_roi = []
        for point in roi:
            scaled_point = [point[0] * scale_factor, point[1] * scale_factor]
            scaled_roi.append(scaled_point)
        control_module_roi_dict[module_id][0] = scaled_roi

    for roi_pt in roi_points:
        roi_pt = [[pt[0] * scale_factor,pt[1] * scale_factor] for pt in roi_pt]
        image = remove_roi(image, roi_pt)     

    for end_point in page_poi:
        x, y = end_point[0], end_point[1]
        color_around_pixel(image, [x ,y], thickness=1)

    if debug:
        cv2.imshow('image', image)
        cv2.waitKey(0)

    # Extract closed contours that will be used to find all the secondary graphics linked to the primary graphics
    closed_contours = extract_closed_contours(page_poi, image, debug)

    pois = sorted(page_poi, key=lambda x: x[0])

    # Preserve the original image (after ROI removal / POI marking) before erosion
    original_image = image.copy()
    
    erode_image = dilate_erode(image)

    if debug:
        cv2.imshow('erode_image',erode_image)
        cv2.waitKey(0)

    cross_points = find_cross_pts(image)
    
    if debug:
        print(len(cross_points))
        img = erode_image.copy()
        for cross_pt in cross_points:
            y, x = cross_pt
            cv2.circle(img, (x, y), 5, (0, 0, 255), -1)  # Red circle for cross points
        cv2.imshow('cross points', img)
        cv2.waitKey(0)    
    
    output_list = flood_fill_analysis(erode_image, pois, cross_points, closed_contours, debug=debug)

    #output_list = find_nearest_contours_to_control_modules(control_module_roi_dict, closed_contours,
    #                                         output_list, erode_image, debug=debug)

    # Find the order of the cleaned points of interest using A* pathfinding
    output_list = order_cleaned_points_of_int(output_list, erode_image, debug=debug)

    # Analyze gaps along A* paths using the original (pre-erode) image
    gap_analysis = analyze_straight_line_gaps(output_list, original_image, erode_image, debug=debug)

    # Classify each path group as signal (dashed) or material (solid)
    output_list = identify_signal_lines(output_list, original_image, erode_image, debug=debug)

    # Build a fork-aware path graph using sliding windows and branch spawning.
    #sliding_window_graphs = trace_sliding_window_path_graphs(#
    #    output_list, erode_image, debug=debug)
    #if debug:
    #    print(f"Sliding window graphs traced: {len(sliding_window_graphs)}")

    # Keep the legacy diagnostics available for side-by-side testing.
    run_legacy_junction_debug = debug
    if run_legacy_junction_debug:
        poi_linestrings = extract_poi_contour_linestrings(
            output_list, erode_image, debug=True)

        convergence_results = detect_path_convergence_points(
            output_list, erode_image, debug=True)

        multi_segment_junctions = detect_multi_segment_junctions(
            output_list, erode_image, debug=True)

        radial_dropoffs = detect_radial_path_dropoff(
            output_list, erode_image, debug=True)

    # Split the output list when 'secondary' points of interest are found
    output_list = split_output_list_on_secondary_points(output_list, debug=debug)

    # Detect points of interest and orientation for control modules
    output_list = control_module_roi_points_and_orientation_detector(output_list, control_module_roi_dict, erode_image, debug=debug)


    return output_list


def extract_poi_contour_linestrings(output_list, image, debug=True):
    """
    Find contours in the image that are touched by points of interest,
    convert them to Shapely LineStrings, and plot them on a matplotlib graph.

    Args:
        output_list: List of point-group dicts (each has 'point' and 'cleaned_points_of_int').
        image: BGR image from which to extract contours.
        debug: If True, display the matplotlib plot.

    Returns:
        List of dicts with keys:
            'group_idx'  – index into output_list
            'poi'        – the [x, y] point of interest that touched this contour
            'linestring' – the Shapely LineString (or Point) geometry
            'contour'    – the raw OpenCV contour array
    """
    # --- threshold to binary ---
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, masked = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    masked = cv2.bitwise_not(masked)  # invert so lines are white

    img_height, img_width = masked.shape[:2]

    # --- detect line segments with LSD and draw onto a clean mask ---
    lsd = cv2.createLineSegmentDetector(0)
    lsd_lines, _, _, _ = lsd.detect(masked)

    lsd_mask = np.zeros((img_height, img_width), dtype=np.uint8)
    if lsd_lines is not None:
        for ln in lsd_lines:
            x1, y1, x2, y2 = ln[0]
            cv2.line(lsd_mask, (int(x1), int(y1)), (int(x2), int(y2)), 255, 2)

    if debug:
        # Show detected LSD lines on the original image
        lsd_viz = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        if lsd_lines is not None:
            for ln in lsd_lines:
                x1, y1, x2, y2 = ln[0]
                cv2.line(lsd_viz, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 2)
        cv2.imshow('LSD Detected Lines', cv2.resize(lsd_viz, (1300, int(lsd_viz.shape[0] * 1300 / lsd_viz.shape[1]))))
        cv2.waitKey(0)

    # --- find contours on the LSD-drawn mask ---
    line_contours, line_hierarchy = cv2.findContours(
        lsd_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )

    # --- collect all POIs from every group ---
    all_pois = []
    for idx, pg in enumerate(output_list):
        p = pg['point']
        all_pois.append((idx, p))
        for cp in pg.get('cleaned_points_of_int', []):
            all_pois.append((idx, cp))

    # --- for each contour, check which POIs touch it ---
    results = []
    used_contour_indices = set()

    for group_idx, poi in all_pois:
        px, py = int(poi[0]), int(poi[1])
        if not (0 <= py < img_height and 0 <= px < img_width):
            continue

        for ci, contour in enumerate(line_contours):
            # pointPolygonTest returns >= 0 when the point is inside or on the edge
            dist = cv2.pointPolygonTest(contour, (px, py), False)
            if dist >= 0:
                key = (group_idx, ci)
                if key in used_contour_indices:
                    continue
                used_contour_indices.add(key)

                # Convert contour to Shapely geometry
                pts = np.reshape(contour, (contour.shape[0], 2)).tolist()
                if len(pts) >= 2:
                    geom = LineString(pts)
                else:
                    geom = Point(pts[0])

                results.append({
                    'group_idx': group_idx,
                    'poi': poi,
                    'linestring': geom,
                    'contour': contour
                })

    # --- plot the LineStrings ---
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.set_title('Contour LineStrings Touched by Points of Interest')
    ax.set_xlabel('X (pixels)')
    ax.set_ylabel('Y (pixels)')

    colors = plt.cm.tab10.colors
    for i, entry in enumerate(results):
        geom = entry['linestring']
        color = colors[entry['group_idx'] % len(colors)]
        if isinstance(geom, LineString):
            xs, ys = geom.xy
            ax.plot(xs, ys, color=color, linewidth=1.5,
                    label=f"Group {entry['group_idx']}" if i == 0 or
                    results[i - 1]['group_idx'] != entry['group_idx'] else None)
        else:
            ax.plot(geom.x, geom.y, 'o', color=color, markersize=4)

    # Overlay the POIs as red markers
    plotted_pois = set()
    for entry in results:
        key = (int(entry['poi'][0]), int(entry['poi'][1]))
        if key not in plotted_pois:
            plotted_pois.add(key)
            ax.plot(key[0], key[1], 'rx', markersize=8, markeredgewidth=2)

    # Invert Y axis so the plot matches image coordinates (origin top-left)
    ax.invert_yaxis()
    ax.set_aspect('equal')
    ax.legend(loc='upper right')
    plt.tight_layout()

    if debug:
        plt.show(block=True)
    else:
        plt.savefig('poi_contour_linestrings.png', dpi=150)
        plt.close(fig)

    return results


def order_cleaned_points_of_int(output_list, image, debug=True):
    """
    Order the cleaned points of interest for each point group using A* pathfinding.
    
    Args:
        output_list: List of output dictionaries from flood_fill_analysis
        image: The binary image used for creating the A* grid
        
    Returns:
        The updated output_list with ordered cleaned_points_of_int
    """
    # Prepare grid for A* pathfinding
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    #_, binary_image = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    #cv2.imshow('Gray Image for A*', cv2.resize(gray, (1300, int(gray.shape[0]*1300/gray.shape[1]))))
    #cv2.waitKey(0)
    # Convert the image to a grid for A* pathfinding
    # Black (0) pixels are paths with low cost, white (255) pixels are high cost
    grid = gray.astype(np.float32)
    grid[grid == 0] = 1  # Black pixels (lines) have low cost
    grid[grid < 127] = 10  # White pixels have high cost

    for point_group in output_list:
        point = point_group['point']
        cleaned_points = point_group['cleaned_points_of_int']
        
        # Skip if there are no points or only one point (no need to order)
        if len(cleaned_points) <= 2:
            continue
        
        # Use the first point (which is usually the start point in the flood fill) as the start
        start_point = point
        
        # Create a map to store the path distance from start to each point
        point_distances = {}
        
        # For each point, calculate the A* path from start
        for dest_point in cleaned_points:
            # Convert the point format to what pyastar2d expects [y, x]
            start_coords = [int(start_point[1]), int(start_point[0])]
            dest_coords = [int(dest_point[1]), int(dest_point[0])]
            
            # Ensure points are within grid boundaries
            img_height, img_width = grid.shape
            if (0 <= start_coords[0] < img_height and 0 <= start_coords[1] < img_width and
                0 <= dest_coords[0] < img_height and 0 <= dest_coords[1] < img_width):
                
                # Calculate A* path
                path = pyastar2d.astar_path(
                    grid, 
                    start_coords, 
                    dest_coords, 
                    allow_diagonal=True
                )

                if debug:
                        maze = np.stack((gray, gray, gray), axis=2)
                        pts = np.flip(path, 1)
                        pts = pts.reshape((-1, 1, 2))
                        maze = cv2.polylines(maze, [pts], 
                                False, (0,0,255), 5)

                        cv2.circle(maze, [int(start_point[0]), int(start_point[1])], 3, (255,0,0), 2)
                        cv2.circle(maze, [int(dest_point[0]), int(dest_point[1])], 3, (0,255,0), 2)
                        cv2.imshow('Distance to Contour', cv2.resize(maze, (1300, int(maze.shape[0]*1300/maze.shape[1]))))
                        cv2.waitKey(0)
                
                # If a path is found, store the length of the path
                if path is not None:
                    point_distances[tuple(dest_point)] = len(path)

                else:
                    # If no path is found, use Euclidean distance as a fallback
                    euclidean_dist = np.sqrt((dest_point[0] - start_point[0])**2 + 
                                           (dest_point[1] - start_point[1])**2)
                    point_distances[tuple(dest_point)] = euclidean_dist * 100  # Penalize no-path cases
        
        # Sort the points based on the path distances
        ordered_points = sorted(cleaned_points, key=lambda p: point_distances.get(tuple(p), float('inf')))
        
        # Update the point group with the ordered points
        point_group['cleaned_points_of_int'] = ordered_points
    
    return output_list


def compute_full_path(point_group, grid, binary_image=None, debug=True, return_segments=False):
    """
    Chain A* paths between the group's starting point and each consecutive
    cleaned POI to produce a single pixel-level path array.

    Args:
        point_group: Dict with 'point' and 'cleaned_points_of_int'
        grid: A* cost grid (float32, black lines = 1, white = 64)
        binary_image: Optional grayscale image for debug visualisation
        debug: If True, show each A* segment and the final chained path
        return_segments: If True, return (full_path, segments) tuple

    Returns:
        numpy array of shape (N, 2) with [y, x] pixel coordinates,
        or None if no path could be computed.
        If return_segments is True, returns (full_path, list_of_segment_arrays).
    """
    start = point_group['point']
    waypoints = point_group['cleaned_points_of_int']
    if not waypoints:
        return None

    img_height, img_width = grid.shape
    segments = []
    current = [int(start[1]), int(start[0])]  # [y, x]

    for wp_idx, wp in enumerate(waypoints):
        dest = [int(wp[1]), int(wp[0])]  # [y, x]
        if not (0 <= current[0] < img_height and 0 <= current[1] < img_width and
                0 <= dest[0] < img_height and 0 <= dest[1] < img_width):
            if debug:
                print(f"  Segment {wp_idx}: skipped (out of bounds)")
            current = dest
            continue
        path = pyastar2d.astar_path(grid, current, dest, allow_diagonal=True)
        if path is not None and len(path) > 0:
            segments.append(path)
            if debug:
                print(f"  Segment {wp_idx}: {len(path)} pixels  "
                      f"({current[1]},{current[0]}) -> ({dest[1]},{dest[0]})")
        else:
            if debug:
                print(f"  Segment {wp_idx}: NO PATH FOUND  "
                      f"({current[1]},{current[0]}) -> ({dest[1]},{dest[0]})")
        current = dest

    if not segments:
        return None if not return_segments else (None, [])

    full_path = np.concatenate(segments, axis=0)

    if debug and binary_image is not None:
        maze = np.stack((binary_image, binary_image, binary_image), axis=2)
        # Draw each segment in a different colour
        for seg_idx, seg in enumerate(segments):
            color = SEGMENT_COLORS[seg_idx % len(SEGMENT_COLORS)]
            pts = np.flip(seg, 1).reshape((-1, 1, 2)).astype(np.int32)
            cv2.polylines(maze, [pts], False, color, 2)
        # Mark start and all waypoints
        cv2.circle(maze, (int(start[0]), int(start[1])), 6, (0, 0, 255), -1)  # red start
        for wp in waypoints:
            cv2.circle(maze, (int(wp[0]), int(wp[1])), 4, (0, 255, 0), -1)  # green waypoints
        cv2.imshow('compute_full_path - Chained Segments',
                   cv2.resize(maze, (1300, int(maze.shape[0] * 1300 / maze.shape[1]))))
        cv2.waitKey(0)

    if return_segments:
        return full_path, segments
    return full_path


def _compute_segment_angle(path_segment):
    """
    Compute the dominant direction angle of an (M, 2) array of [y, x] path pixels
    using cv2.fitLine.

    Returns:
        Angle in degrees in the range [0, 180).
    """
    # fitLine expects points as (N, 1, 2) in (x, y) order
    pts = np.flip(path_segment, axis=1).reshape((-1, 1, 2)).astype(np.float32)
    vx, vy, _, _ = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01)
    angle = np.degrees(np.arctan2(float(vy), float(vx))) % 180.0
    return angle


def _split_path_at_direction_changes(path, window=15, angle_change_threshold=30.0):
    """
    Split a single A* path into sub-segments wherever the travel direction
    changes by more than *angle_change_threshold* degrees.

    A sliding window of *window* pixels is used to compute a local direction
    angle.  When the angle jumps by more than the threshold between
    consecutive windows, the path is split at that point.

    Args:
        path:                  (N, 2) array of [y, x] pixel coords.
        window:                Number of pixels for the local direction window.
        angle_change_threshold: Degrees; a jump bigger than this triggers a split.

    Returns:
        List of (M_i, 2) sub-path arrays whose concatenation equals *path*.
    """
    n = len(path)
    if n < window * 2:
        return [path]

    # Compute local angle at each position where we have a full window
    angles = []
    positions = []
    for i in range(0, n - window + 1, max(1, window // 3)):
        seg = path[i : i + window]
        angles.append(_compute_segment_angle(seg))
        positions.append(i + window // 2)  # centre of the window

    if len(angles) < 2:
        return [path]

    # Find split points where angle changes sharply
    split_indices = []
    for k in range(1, len(angles)):
        diff = abs(angles[k] - angles[k - 1])
        diff = min(diff, 180.0 - diff)
        if diff > angle_change_threshold:
            split_indices.append(positions[k])

    if not split_indices:
        return [path]

    # Build sub-paths
    sub_paths = []
    prev = 0
    for sp in split_indices:
        if sp > prev:
            sub_paths.append(path[prev:sp])
        prev = sp
    if prev < n:
        sub_paths.append(path[prev:])

    return [s for s in sub_paths if len(s) >= 2]


def _run_length_encode(on_line):
    """Run-length encode a boolean array into (is_line, start, end) tuples."""
    if len(on_line) == 0:
        return []
    runs = []
    run_start = 0
    for i in range(1, len(on_line)):
        if on_line[i] != on_line[run_start]:
            runs.append((bool(on_line[run_start]), run_start, i - 1))
            run_start = i
    runs.append((bool(on_line[run_start]), run_start, len(on_line) - 1))
    return runs


def _check_collinearity(full_path, rs_i, re_i, angle_i, rs_j, re_j, angle_j,
                        angle_threshold, min_gap_length, max_lateral_offset=8.0):
    """Check three collinearity conditions between two reliable line runs.

    Returns:
        (is_collinear, angle_diff, lateral_dist, gap_aligned)
    """
    # 1. Angle similarity
    diff = abs(angle_i - angle_j)
    angle_diff = min(diff, 180.0 - diff)
    angles_match = angle_diff <= angle_threshold

    # 2. Lateral offset — perpendicular distance from run_j midpoint
    #    to fitted line of run_i
    seg_i = full_path[rs_i : re_i + 1]
    pts_i = np.flip(seg_i, axis=1).reshape((-1, 1, 2)).astype(np.float32)
    vx, vy, cx, cy = cv2.fitLine(pts_i, cv2.DIST_L2, 0, 0.01, 0.01)
    vx, vy, cx, cy = float(vx), float(vy), float(cx), float(cy)

    seg_j = full_path[rs_j : re_j + 1]
    mid_j = seg_j[len(seg_j) // 2]
    mx, my = float(mid_j[1]), float(mid_j[0])  # [y,x] -> x,y
    lateral_dist = abs(vx * (my - cy) - vy * (mx - cx))
    offset_ok = lateral_dist <= max_lateral_offset

    # 3. Gap alignment — gap pixels travel same direction as runs
    gap_start = re_i + 1
    gap_end = rs_j
    gap_aligned = True
    if gap_end - gap_start >= min_gap_length:
        gap_seg = full_path[gap_start : gap_end]
        if len(gap_seg) >= 2:
            gap_angle = _compute_segment_angle(gap_seg)
            gap_diff = abs(gap_angle - angle_i)
            gap_diff = min(gap_diff, 180.0 - gap_diff)
            gap_aligned = gap_diff <= angle_threshold * 3

    is_collinear = angles_match and offset_ok and gap_aligned
    return is_collinear, angle_diff, lateral_dist, gap_aligned


def _visualize_segment_angles(image, sub_segments, start_pt, waypoints, pg_idx):
    """Debug: draw each sub-segment with its angle label."""
    viz = image.copy()
    for s_idx, s_path in enumerate(sub_segments):
        if len(s_path) < 2:
            continue
        color = SEGMENT_COLORS[s_idx % len(SEGMENT_COLORS)]
        pts_xy = np.flip(s_path, axis=1).reshape((-1, 1, 2)).astype(np.int32)
        cv2.polylines(viz, [pts_xy], False, color, 2)
        angle = _compute_segment_angle(s_path)
        mid = s_path[len(s_path) // 2]
        cv2.putText(viz, f"seg{s_idx} {angle:.1f}deg",
                    (int(mid[1]) + 5, int(mid[0]) - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
    cv2.circle(viz, (int(start_pt[0]), int(start_pt[1])), 6, (0, 0, 255), -1)
    for wp in waypoints:
        cv2.circle(viz, (int(wp[0]), int(wp[1])), 4, (0, 255, 0), -1)
    display_width = 1300
    cv2.imshow(f"Segment Angles - Group {pg_idx}",
               cv2.resize(viz, (display_width,
                                int(viz.shape[0] * display_width / viz.shape[1]))))
    cv2.waitKey(0)


def _visualize_gap_analysis(original_image, results):
    """Debug: draw gap analysis overlays for each group."""
    display_width = 1300
    for pg_idx, entry in enumerate(results):
        full_path = entry['full_path']
        if full_path is None or len(full_path) == 0:
            continue

        all_group_gaps = [g for s in entry['segments'] for g in s['gaps']]
        if not all_group_gaps:
            continue

        viz = original_image.copy()
        pts_xy = np.flip(full_path, axis=1).reshape((-1, 1, 2)).astype(np.int32)
        cv2.polylines(viz, [pts_xy], False, (255, 0, 0), 1)

        for gap in all_group_gaps:
            gap_segment = full_path[gap['start_idx']:gap['end_idx'] + 1]
            gap_pts = np.flip(gap_segment, axis=1).reshape((-1, 1, 2)).astype(np.int32)

            if gap['is_collinear'] is True:
                color, label = (0, 255, 0), f"OK {gap['angle_diff']}deg"
            elif gap['is_collinear'] is False:
                color, label = (0, 0, 255), f"BAD {gap['angle_diff']}deg"
            else:
                color, label = (0, 255, 255), f"? gap={gap['gap_length']}px"

            cv2.polylines(viz, [gap_pts], False, color, 3)
            mid_idx = (gap['start_idx'] + gap['end_idx']) // 2
            mid_y, mid_x = int(full_path[mid_idx][0]), int(full_path[mid_idx][1])
            cv2.putText(viz, label, (mid_x + 5, mid_y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)

            # BEFORE slice in cyan
            if gap['before_slice_range'] is not None:
                bs, be = gap['before_slice_range']
                before_seg = full_path[bs:be]
                before_pts = np.flip(before_seg, axis=1).reshape((-1, 1, 2)).astype(np.int32)
                cv2.polylines(viz, [before_pts], False, (255, 255, 0), 3)
                lbl_y, lbl_x = int(before_seg[0][0]), int(before_seg[0][1])
                cv2.putText(viz, f"BEFORE {gap['angle_before']}deg",
                            (lbl_x + 5, lbl_y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 0), 1)

            # AFTER slice in magenta
            if gap['after_slice_range'] is not None:
                as_, ae = gap['after_slice_range']
                after_seg = full_path[as_:ae]
                after_pts = np.flip(after_seg, axis=1).reshape((-1, 1, 2)).astype(np.int32)
                cv2.polylines(viz, [after_pts], False, (255, 0, 255), 3)
                lbl_y, lbl_x = int(after_seg[-1][0]), int(after_seg[-1][1])
                cv2.putText(viz, f"AFTER {gap['angle_after']}deg",
                            (lbl_x + 5, lbl_y + 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 0, 255), 1)

        origin = entry['point']
        cv2.circle(viz, (int(origin[0]), int(origin[1])), 6, (0, 0, 255), -1)

        n_legit = sum(1 for g in all_group_gaps if g['is_collinear'] is True)
        n_bad = sum(1 for g in all_group_gaps if g['is_collinear'] is False)
        n_unk = sum(1 for g in all_group_gaps if g['is_collinear'] is None)
        title = (f"Gap Analysis - Group {pg_idx}: "
                 f"{n_legit} collinear, {n_bad} non-collinear, {n_unk} unknown")
        cv2.imshow(title,
                   cv2.resize(viz, (display_width,
                                    int(viz.shape[0] * display_width / viz.shape[1]))))
        cv2.waitKey(0)

    total_gaps = sum(len(s['gaps']) for e in results for s in e['segments'])
    total_legit = sum(1 for e in results for s in e['segments']
                      for g in s['gaps'] if g['is_collinear'] is True)
    total_bad = sum(1 for e in results for s in e['segments']
                    for g in s['gaps'] if g['is_collinear'] is False)
    print(f"\nGap Analysis Summary: {total_gaps} gaps detected "
          f"({total_legit} collinear, {total_bad} non-collinear)")


def analyze_straight_line_gaps(output_list, original_image, erode_image,
                               angle_threshold=10.0, min_gap_length=3,
                               min_segment_length=15, debug=True):
    """
    For each point group, compute individual A* segments between consecutive
    POIs and analyse each segment independently for gaps on the original
    (pre-erode) image.  For every gap flanked by line pixels on both sides,
    check whether the flanking segments are collinear (within
    *angle_threshold* degrees).

    Args:
        output_list:      List of point-group dicts (with 'point' and
                          'cleaned_points_of_int').
        original_image:   BGR image **before** dilate_erode.
        erode_image:      BGR image **after** dilate_erode (used for A* grid).
        angle_threshold:  Maximum angle difference (degrees) for two flanking
                          segments to be considered collinear (default 10).
        min_gap_length:   Ignore gaps shorter than this many path pixels
                          (default 3).
        min_segment_length: Minimum flanking segment length to attempt
                          collinearity check (default 5).
        debug:            If True, visualise each segment with gap annotations.

    Returns:
        List of dicts, one per point group:
            {
                'point':      the origin POI,
                'segments':   list of per-segment dicts (see below),
                'full_path':  np.ndarray (N, 2) of [y, x] or None
            }
        Each segment dict:
            {
                'seg_idx':    int,
                'from_point': [x, y, ...] start POI,
                'to_point':   [x, y, ...] end POI,
                'path':       np.ndarray (M, 2) of [y, x],
                'gaps':       list of gap dicts
            }
        Each gap dict:
            {
                'start_idx', 'end_idx', 'start_pixel', 'end_pixel',
                'gap_length', 'angle_diff', 'angle_before', 'angle_after',
                'before_slice_range', 'after_slice_range', 'is_collinear'
            }
    """
    # --- build A* cost grid from the eroded image ---------------------------
    gray_erode = cv2.cvtColor(erode_image, cv2.COLOR_BGR2GRAY)
    grid = gray_erode.astype(np.float32)
    grid[grid == 0] = 1    # black pixels (lines) have low cost
    grid[grid < 127] = 10  # white pixels have high cost

    # --- binary mask of the original image (dark pixels = line) -------------
    gray_orig = cv2.cvtColor(original_image, cv2.COLOR_BGR2GRAY)
    _, orig_binary = cv2.threshold(gray_orig, 240, 255, cv2.THRESH_BINARY)
    # orig_binary: 0 = line pixel, 255 = background

    img_height, img_width = orig_binary.shape[:2]

    results = []

    for pg_idx, point_group in enumerate(output_list):
        # Get individual A* segments between consecutive POIs
        result = compute_full_path(point_group, grid, return_segments=True)
        if result is None:
            results.append({'point': point_group['point'], 'segments': [], 'full_path': None})
            continue
        full_path, segments = result
        if full_path is None or len(segments) == 0:
            results.append({'point': point_group['point'], 'segments': [], 'full_path': None})
            continue

        # Build endpoint pairs for each segment
        start_pt = point_group['point']
        waypoints = point_group['cleaned_points_of_int']

        # --- split A* segments at direction changes into sub-segments ------
        sub_segments = []  # list of sub-path arrays
        for seg_path in segments:
            sub_segments.extend(_split_path_at_direction_changes(seg_path))

        if debug:
            _visualize_segment_angles(original_image, sub_segments, start_pt,
                                      waypoints, pg_idx)

        segment_results = []
        for seg_idx, seg_path in enumerate(sub_segments):
            # Derive from/to from the sub-segment path endpoints ([y,x] -> [x,y])
            from_pt = [int(seg_path[0][1]), int(seg_path[0][0])]
            to_pt = [int(seg_path[-1][1]), int(seg_path[-1][0])]
            segment_results.append({
                'seg_idx': seg_idx,
                'from_point': from_pt,
                'to_point': to_pt,
                'path': seg_path,
                'gaps': []
            })

        # --- gap detection on the FULL path (not per sub-segment) -----------
        ys = full_path[:, 0].astype(int)
        xs = full_path[:, 1].astype(int)
        in_bounds = (ys >= 0) & (ys < img_height) & (xs >= 0) & (xs < img_width)
        on_line = np.zeros(len(full_path), dtype=bool)
        on_line[in_bounds] = orig_binary[ys[in_bounds], xs[in_bounds]] < 240

        if debug:
            n_on = int(np.sum(on_line))
            n_off = len(on_line) - n_on
            print(f"\n  Group {pg_idx}: full_path={len(full_path)}px, "
                  f"on_line={n_on}, gap_pixels={n_off}")

        runs = _run_length_encode(on_line)

        if debug:
            line_runs = [(s, e, e - s + 1) for (is_l, s, e) in runs if is_l]
            gap_runs_debug = [(s, e, e - s + 1) for (is_l, s, e) in runs if not is_l]
            print(f"    Runs: {len(runs)} total, "
                  f"{len(line_runs)} line-runs, {len(gap_runs_debug)} gap-runs")
            for gs, ge, gl in gap_runs_debug:
                print(f"      gap [{gs}-{ge}] len={gl}  "
                      f"{'SKIP' if gl < min_gap_length else 'ANALYSE'}")
            for ls, le, ll in line_runs:
                print(f"      line [{ls}-{le}] len={ll}")

        # Build a mapping from full-path index to sub-segment index
        sub_seg_boundaries = []  # list of (start_idx_in_full, end_idx_in_full)
        offset = 0
        for seg_path in sub_segments:
            sub_seg_boundaries.append((offset, offset + len(seg_path) - 1))
            offset += len(seg_path)

        if debug:
            total_sub = sum(len(s) for s in sub_segments)
            print(f"    sub_segments: {len(sub_segments)}, total_px={total_sub}, "
                  f"full_path_px={len(full_path)}, "
                  f"match={'YES' if total_sub == len(full_path) else 'NO MISMATCH!'}")

        def _full_idx_to_seg(idx):
            for si, (s, e) in enumerate(sub_seg_boundaries):
                if s <= idx <= e:
                    return si
            return len(sub_seg_boundaries) - 1

        # --- collect reliable line runs and compute their angles ---------------
        reliable_runs = []  # list of (run_idx, start, end, angle)
        for r_idx, (is_line, r_start, r_end) in enumerate(runs):
            if not is_line:
                continue
            run_len = r_end - r_start + 1
            if run_len < min_segment_length:
                continue
            angle = _compute_segment_angle(full_path[r_start : r_end + 1])
            reliable_runs.append((r_idx, r_start, r_end, angle))

        if debug:
            print(f"    Reliable line runs: {len(reliable_runs)}")
            for ri, rs, re, ra in reliable_runs:
                print(f"      run[{ri}] [{rs}-{re}] len={re-rs+1} angle={ra:.1f}deg")

        # --- pairwise collinearity: mark all gaps between collinear runs ----
        # For each pair of reliable line runs, if they are collinear, every
        # gap that sits between them is legitimate.
        gap_runs = []  # (run_idx_in_runs, start, end, gap_length)
        for r_idx, (is_line, r_start, r_end) in enumerate(runs):
            if is_line:
                continue
            gap_length = r_end - r_start + 1
            if gap_length < min_gap_length:
                continue
            gap_runs.append((r_idx, r_start, r_end, gap_length))

        # Initialise gap results
        gap_results = {}  # keyed by (r_start, r_end)
        for (gr_idx, gr_start, gr_end, gr_len) in gap_runs:
            gap_results[(gr_start, gr_end)] = {
                'start_idx': gr_start,
                'end_idx': gr_end,
                'start_pixel': full_path[gr_start].tolist(),
                'end_pixel': full_path[gr_end].tolist(),
                'gap_length': gr_len,
                'angle_diff': None,
                'angle_before': None,
                'angle_after': None,
                'before_slice_range': None,
                'after_slice_range': None,
                'is_collinear': None
            }

        # Pairwise collinearity: angle + lateral offset + gap alignment
        for i in range(len(reliable_runs)):
            for j in range(i + 1, len(reliable_runs)):
                _, rs_i, re_i, angle_i = reliable_runs[i]
                _, rs_j, re_j, angle_j = reliable_runs[j]

                is_collinear, angle_diff, lateral_dist, gap_aligned = \
                    _check_collinearity(full_path, rs_i, re_i, angle_i,
                                        rs_j, re_j, angle_j,
                                        angle_threshold, min_gap_length)

                if debug:
                    print(f"    Compare run [{rs_i}-{re_i}] ({angle_i:.1f}deg) "
                          f"vs [{rs_j}-{re_j}] ({angle_j:.1f}deg): "
                          f"angle_diff={angle_diff:.1f}, lateral={lateral_dist:.1f}px, "
                          f"gap_aligned={gap_aligned}, "
                          f"collinear={is_collinear}")

                if is_collinear:
                    # Mark all gaps between these two runs as collinear
                    for (gr_start, gr_end) in gap_results:
                        if gr_start > re_i and gr_end < rs_j:
                            g = gap_results[(gr_start, gr_end)]
                            if g['is_collinear'] is not True:
                                g['angle_diff'] = round(angle_diff, 2)
                                g['angle_before'] = round(angle_i, 2)
                                g['angle_after'] = round(angle_j, 2)
                                g['before_slice_range'] = (rs_i, re_i + 1)
                                g['after_slice_range'] = (rs_j, re_j + 1)
                                g['is_collinear'] = True

        # Attribute each gap to a sub-segment
        for (gr_start, gr_end), gap_dict in gap_results.items():
            mid_idx = (gr_start + gr_end) // 2
            seg_owner = _full_idx_to_seg(mid_idx)
            segment_results[seg_owner]['gaps'].append(gap_dict)

        entry = {
            'point': point_group['point'],
            'segments': segment_results,
            'full_path': full_path
        }
        results.append(entry)

    if debug:
        _visualize_gap_analysis(original_image, results)

    return results


def _compute_path_curvature(path, stride=5, smooth_sigma=2.0):
    """
    Compute local curvature at each point along a path using the Menger
    curvature formula on triplets (p[i-stride], p[i], p[i+stride]).

    A Gaussian smooth is applied first to suppress pixel-level zigzag
    noise from A* paths traversing thick lines.

    Args:
        path:         (N, 2) array of [y, x] pixel coordinates.
        stride:       Distance (in samples) between the three points used for
                      curvature estimation.
        smooth_sigma: Standard deviation for Gaussian smoothing of coordinates.
                      Set to 0 to disable.

    Returns:
        curvature: (N,) array of signed curvature values.  Points within
                   *stride* of the ends are set to 0.
    """
    from scipy.ndimage import gaussian_filter1d

    n = len(path)
    curvature = np.zeros(n, dtype=np.float64)
    if n < stride * 2 + 1:
        return curvature

    # Smooth path coordinates to remove pixel-level zigzag from A* paths
    smoothed = path.astype(np.float64).copy()
    if smooth_sigma > 0 and n > 5:
        smoothed[:, 0] = gaussian_filter1d(smoothed[:, 0], sigma=smooth_sigma)
        smoothed[:, 1] = gaussian_filter1d(smoothed[:, 1], sigma=smooth_sigma)

    for i in range(stride, n - stride):
        p0 = smoothed[i - stride]
        p1 = smoothed[i]
        p2 = smoothed[i + stride]

        # Triangle side lengths
        a = np.linalg.norm(p1 - p0)
        b = np.linalg.norm(p2 - p1)
        c = np.linalg.norm(p2 - p0)

        # Signed area via cross product (positive = left turn)
        cross = (p1[1] - p0[1]) * (p2[0] - p0[0]) - (p1[0] - p0[0]) * (p2[1] - p0[1])
        denom = a * b * c
        if denom > 1e-9:
            curvature[i] = 2.0 * cross / denom

    return curvature


def _compute_perpendicular_displacement(path, window=30):
    """
    Compute signed perpendicular displacement of each path point from a
    local baseline direction.

    A sliding window of *window* pixels is used to fit a local line, and
    the signed distance from each point to that line is recorded.

    Args:
        path:   (N, 2) array of [y, x] pixel coordinates.
        window: Number of points for the local baseline fit.

    Returns:
        displacement: (N,) array of signed perpendicular distances.
    """
    n = len(path)
    displacement = np.zeros(n, dtype=np.float64)
    half = window // 2

    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        seg = path[lo:hi]
        if len(seg) < 3:
            continue
        pts = np.flip(seg, axis=1).reshape((-1, 1, 2)).astype(np.float32)
        vx, vy, cx, cy = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01)
        vx, vy, cx, cy = float(vx), float(vy), float(cx), float(cy)
        # Signed distance: point (x, y) from line through (cx, cy) along (vx, vy)
        px, py = float(path[i, 1]), float(path[i, 0])  # [y,x] -> x,y
        displacement[i] = vx * (py - cy) - vy * (px - cx)

    return displacement


def _classify_revision_cloud(curvature, displacement,
                             min_peaks=5,
                             max_peak_spacing_cv=0.55,
                             min_displacement_amplitude=4.0,
                             min_peak_curvature=0.03):
    """
    Determine whether curvature and displacement profiles indicate a
    revision-cloud (scalloped/wavy) line.

    Revision clouds have periodic curvature with arcs predominantly
    bulging in one direction and periodic perpendicular displacement.

    The function checks positive and negative curvature peaks independently.
    If either sign has enough regular, periodic peaks, the line is a cloud.

    Args:
        curvature:                (N,) curvature array from _compute_path_curvature.
        displacement:             (N,) displacement array from _compute_perpendicular_displacement.
        min_peaks:                Minimum number of same-sign curvature peaks required.
        max_peak_spacing_cv:      Maximum CV of inter-peak spacing for regularity.
        min_displacement_amplitude: Minimum peak-to-trough in displacement profile.
        min_peak_curvature:       Minimum absolute curvature value for a peak to
                                  qualify (filters out pixel-level noise on straight lines).

    Returns:
        (is_revision_cloud, metrics_dict)
    """
    from scipy.signal import find_peaks

    abs_curv = np.abs(curvature)
    if abs_curv.max() < min_peak_curvature:
        return False, {'reason': 'curvature_below_threshold'}

    # Displacement amplitude check
    disp_amplitude = float(displacement.max() - displacement.min())
    if disp_amplitude < min_displacement_amplitude:
        return False, {'displacement_amplitude': disp_amplitude,
                       'reason': 'low_displacement'}

    # Analyze positive and negative curvature peaks independently.
    # Revision cloud arcs all bulge one way, so one sign should dominate
    # with periodic peaks.
    best_result = None
    for sign_label, signal in [('positive', curvature), ('negative', -curvature)]:
        # Only look at peaks exceeding the minimum curvature magnitude
        peaks, _ = find_peaks(signal, height=min_peak_curvature, distance=3)
        peak_count = len(peaks)

        if peak_count < min_peaks:
            continue

        spacings = np.diff(peaks).astype(np.float64)
        mean_spacing = spacings.mean()
        spacing_cv = (spacings.std() / mean_spacing) if mean_spacing > 0 else 999.0

        if spacing_cv <= max_peak_spacing_cv:
            metrics = {
                'peak_count': int(peak_count),
                'dominant_sign': sign_label,
                'mean_peak_spacing': round(float(mean_spacing), 2),
                'peak_spacing_cv': round(float(spacing_cv), 3),
                'displacement_amplitude': round(disp_amplitude, 2),
                'is_revision_cloud': True,
            }
            # Return immediately on first qualifying sign
            return True, metrics

        # Track best non-qualifying result for diagnostics
        if best_result is None or peak_count > best_result.get('peak_count', 0):
            best_result = {
                'peak_count': int(peak_count),
                'dominant_sign': sign_label,
                'mean_peak_spacing': round(float(mean_spacing), 2),
                'peak_spacing_cv': round(float(spacing_cv), 3),
                'displacement_amplitude': round(disp_amplitude, 2),
                'is_revision_cloud': False,
            }

    if best_result:
        return False, best_result
    return False, {'peak_count': 0, 'reason': 'too_few_peaks',
                   'displacement_amplitude': round(disp_amplitude, 2)}


def _visualize_signal_line_classification(image, classification_data):
    """Debug: draw paths colored by signal/material classification."""
    display_width = 1300
    viz = image.copy()

    for entry in classification_data:
        full_path = entry.get('full_path')
        if full_path is None or len(full_path) == 0:
            continue

        line_type = entry.get('line_type', 'material')
        metrics = entry.get('dash_metrics', {})

        # Color by classification
        if line_type == 'signal':
            path_color = (255, 128, 0)  # orange for signal
        elif line_type == 'revision_cloud':
            path_color = (0, 200, 255)  # yellow for revision cloud
        else:
            path_color = (160, 160, 160)  # gray for material

        pts_xy = np.flip(full_path, axis=1).reshape((-1, 1, 2)).astype(np.int32)
        cv2.polylines(viz, [pts_xy], False, path_color, 2)

        # Label at the path start
        start_y, start_x = int(full_path[0][0]), int(full_path[0][1])
        label = f"{line_type.upper()}"
        if metrics:
            label += (f" gaps={metrics.get('gap_count', 0)}"
                      f" freq={metrics.get('gap_frequency', 0):.1f}"
                      f" dCV={metrics.get('dash_length_cv', 0):.2f}"
                      f" gCV={metrics.get('gap_length_cv', 0):.2f}")
        cv2.putText(viz, label, (start_x + 5, start_y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, path_color, 1)

        # Draw alternating dash/gap runs if available
        runs = entry.get('runs', [])
        for is_line, r_start, r_end in runs:
            seg = full_path[r_start:r_end + 1]
            if len(seg) < 2:
                continue
            seg_pts = np.flip(seg, axis=1).reshape((-1, 1, 2)).astype(np.int32)
            if is_line:
                cv2.polylines(viz, [seg_pts], False, (0, 200, 0), 3)  # green = dash
            else:
                cv2.polylines(viz, [seg_pts], False, (0, 0, 255), 3)  # red = gap

    n_signal = sum(1 for e in classification_data if e.get('line_type') == 'signal')
    n_material = sum(1 for e in classification_data if e.get('line_type') == 'material')
    n_cloud = sum(1 for e in classification_data if e.get('line_type') == 'revision_cloud')
    title = (f"Signal Line Classification: {n_signal} signal, "
             f"{n_material} material, {n_cloud} revision_cloud")
    cv2.imshow(title,
               cv2.resize(viz, (display_width,
                                int(viz.shape[0] * display_width / viz.shape[1]))))
    cv2.waitKey(0)

    print(f"\nSignal Line Classification Summary: "
          f"{n_signal} signal, {n_material} material, {n_cloud} revision_cloud "
          f"(total {len(classification_data)} groups)")
    for i, entry in enumerate(classification_data):
        m = entry.get('dash_metrics', {})
        print(f"  Group {i}: {entry.get('line_type', '?'):>8s}  "
              f"gaps={m.get('gap_count', 0):>3d}  "
              f"freq={m.get('gap_frequency', 0):>5.1f}  "
              f"dCV={m.get('dash_length_cv', 0):.2f}  "
              f"gCV={m.get('gap_length_cv', 0):.2f}  "
              f"d̄={m.get('mean_dash_length', 0):.1f}  "
              f"ḡ={m.get('mean_gap_length', 0):.1f}")


def identify_signal_lines(output_list, original_image, erode_image,
                          min_gap_count=3, min_gap_frequency=5.0,
                          max_dash_cv=0.5, max_gap_cv=0.6,
                          debug=True):
    """
    Classify each path group as 'signal' (dashed) or 'material' (solid) by
    detecting regular dash-gap patterns along the A* path on the original
    (pre-erode) image.

    Signal lines in P&ID diagrams are drawn with a repeating dash pattern.
    This function walks each full A* path, samples whether each pixel sits
    on a dark line in the original image, run-length-encodes the on/off
    pattern, and checks whether the gaps are frequent and regular enough
    to indicate a dashed line.

    Args:
        output_list:       List of point-group dicts (with 'point' and
                           'cleaned_points_of_int').
        original_image:    BGR image **before** dilate_erode.
        erode_image:       BGR image **after** dilate_erode (used for A* grid).
        min_gap_count:     Minimum number of gaps to establish a dash pattern
                           (default 3).
        min_gap_frequency: Minimum gaps per 100 path pixels to be considered
                           dashed (default 5.0).
        max_dash_cv:       Maximum coefficient of variation (std/mean) of dash
                           lengths for regularity (default 0.5).
        max_gap_cv:        Maximum coefficient of variation of gap lengths
                           (default 0.6).
        debug:             If True, visualise classification overlays.

    Returns:
        The mutated output_list with an added 'line_type' key per group:
            'signal'         – dashed line detected
            'revision_cloud' – scalloped/wavy revision cloud line detected
            'material'       – solid line (default)
    """
    # --- build A* cost grid from the eroded image ---------------------------
    gray_erode = cv2.cvtColor(erode_image, cv2.COLOR_BGR2GRAY)
    grid = gray_erode.astype(np.float32)
    grid[grid == 0] = 1
    grid[grid < 127] = 10

    # --- binary mask of the original image (dark pixels = line) -------------
    gray_orig = cv2.cvtColor(original_image, cv2.COLOR_BGR2GRAY)
    _, orig_binary = cv2.threshold(gray_orig, 240, 255, cv2.THRESH_BINARY)
    img_height, img_width = orig_binary.shape[:2]

    classification_data = []  # for debug visualisation

    for pg_idx, point_group in enumerate(output_list):
        # Compute pixel-level path
        full_path = compute_full_path(point_group, grid)
        if full_path is None or len(full_path) < 30:
            point_group['line_type'] = 'material'
            if debug:
                classification_data.append({
                    'full_path': full_path, 'line_type': 'material',
                    'dash_metrics': {}, 'runs': []
                })
            continue

        # Sample each path pixel against original binary image
        ys = full_path[:, 0].astype(int)
        xs = full_path[:, 1].astype(int)
        in_bounds = (ys >= 0) & (ys < img_height) & (xs >= 0) & (xs < img_width)
        on_line = np.zeros(len(full_path), dtype=bool)
        on_line[in_bounds] = orig_binary[ys[in_bounds], xs[in_bounds]] < 240

        # Run-length encode the on/off pattern
        runs = _run_length_encode(on_line)

        # Separate dash runs (on-line) and gap runs (off-line)
        dash_lengths = [e - s + 1 for (is_l, s, e) in runs if is_l]
        gap_lengths = [e - s + 1 for (is_l, s, e) in runs if not is_l]

        # Compute metrics
        gap_count = len(gap_lengths)
        path_length = len(full_path)
        gap_frequency = (gap_count / path_length * 100) if path_length > 0 else 0

        if len(dash_lengths) >= 2:
            mean_dash = float(np.mean(dash_lengths))
            dash_cv = float(np.std(dash_lengths) / mean_dash) if mean_dash > 0 else 999.0
        else:
            mean_dash = float(np.mean(dash_lengths)) if dash_lengths else 0.0
            dash_cv = 999.0

        if len(gap_lengths) >= 2:
            mean_gap = float(np.mean(gap_lengths))
            gap_cv = float(np.std(gap_lengths) / mean_gap) if mean_gap > 0 else 999.0
        else:
            mean_gap = float(np.mean(gap_lengths)) if gap_lengths else 0.0
            gap_cv = 999.0

        # Classification: signal if all thresholds met
        is_signal = (
            gap_count >= min_gap_count
            and gap_frequency >= min_gap_frequency
        )

        line_type = 'signal' if is_signal else 'material'

        # Second pass: check material lines for revision cloud pattern
        cloud_metrics = {}
        if line_type == 'material' and len(full_path) >= 50:
            curv = _compute_path_curvature(full_path, stride=5)
            disp = _compute_perpendicular_displacement(full_path, window=30)
            is_cloud, cloud_metrics = _classify_revision_cloud(curv, disp)
            if is_cloud:
                line_type = 'revision_cloud'

        point_group['line_type'] = line_type

        dash_metrics = {
            'gap_count': gap_count,
            'gap_frequency': round(gap_frequency, 2),
            'dash_length_cv': round(dash_cv, 3),
            'gap_length_cv': round(gap_cv, 3),
            'mean_dash_length': round(mean_dash, 1),
            'mean_gap_length': round(mean_gap, 1),
            'path_length': path_length,
            'dash_count': len(dash_lengths),
            **{f'cloud_{k}': v for k, v in cloud_metrics.items()}
        }
        point_group['dash_metrics'] = dash_metrics

        if debug:
            classification_data.append({
                'full_path': full_path,
                'line_type': line_type,
                'dash_metrics': dash_metrics,
                'runs': runs
            })

    if debug and classification_data:
        _visualize_signal_line_classification(original_image, classification_data)

    return output_list


def detect_path_convergence_points(output_list, image, proximity_threshold=15,
                                   min_poi_count=1, debug=True):
    """
    After paths have been ordered by A*, detect fork/junction points where
    separate path groups diverge from or merge into each other.

    Any path group with at least *min_poi_count* cleaned POI (default 1)
    qualifies — if a contour has two paths through it, both participate.

    A fork is the last shared pixel where two paths overlap before they
    split apart.  A merge is the first shared pixel where two previously
    separate paths meet.  Only the actual on-path pixel is reported (not
    a midpoint in empty space).  Points that land exactly on a known POI
    (within 3 px) are excluded so only geometric fork/merge locations
    are returned.

    Args:
        output_list:  List of point-group dicts from flood_fill_analysis / ordering.
        image:        BGR image used to build the A* cost grid.
        proximity_threshold: Pixel distance below which two path pixels are
                             considered to be on the same physical line
                             (default 15).
        min_poi_count: Minimum number of cleaned POIs a group must have to
                       participate in detection (default 1).
        debug:        If True, visualise paths and junction markers.

    Returns:
        convergence_results: list of dicts, one per detected junction pair:
            {
                'path_a_idx':      index into output_list,
                'path_b_idx':      index into output_list,
                'junction_points': list of [x, y] on-path fork/merge pixels,
                'min_distance':    float, smallest distance between the paths
            }
    """
    # --- build A* grid (same recipe as order_cleaned_points_of_int) ----------
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary_image = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    grid = binary_image.astype(np.float32)
    grid[grid == 0] = 1
    grid[grid == 255] = 64

    # --- collect all known POI coordinates for exclusion --------------------
    poi_exclusion_radius = 3  # only exclude points literally on a POI
    all_poi_coords = []
    for pg in output_list:
        p = pg['point']
        all_poi_coords.append([p[0], p[1]])
        for cp in pg.get('cleaned_points_of_int', []):
            all_poi_coords.append([cp[0], cp[1]])
    all_poi_coords = np.array(all_poi_coords) if all_poi_coords else np.empty((0, 2))

    # --- diagnostic ---------------------------------------------------------
    if debug:
        print(f"\n{'='*60}")
        print(f"JUNCTION DETECTION — {len(output_list)} path groups, "
              f"min_poi_count={min_poi_count}, "
              f"proximity_threshold={proximity_threshold}px, "
              f"poi_exclusion={poi_exclusion_radius}px")
        print(f"{'='*60}")
        for idx, pg in enumerate(output_list):
            n_poi = len(pg.get('cleaned_points_of_int', []))
            qualifies = "Y" if n_poi >= min_poi_count else "N"
            pt = pg['point']
            print(f"  [{qualifies}] Group {idx}: {n_poi} POIs, "
                  f"start=({pt[0]:.0f}, {pt[1]:.0f})")

    # --- compute full pixel paths for qualifying groups ---------------------
    qualifying_indices = []
    full_paths = []
    for idx, pg in enumerate(output_list):
        if len(pg.get('cleaned_points_of_int', [])) >= min_poi_count:
            if debug:
                print(f"Computing full path for group {idx} "
                      f"({len(pg['cleaned_points_of_int'])} POIs)...")
            fp = compute_full_path(pg, grid, binary_image if debug else None, debug)
            if fp is not None and len(fp) > 0:
                qualifying_indices.append(idx)
                full_paths.append(fp)
                if debug:
                    print(f"  -> {len(fp)} pixels")

    if debug:
        print(f"Qualifying: {len(full_paths)} groups "
              f"(indices: {qualifying_indices})")

    convergence_results = []
    if len(full_paths) < 2:
        if debug:
            print("Need >= 2 qualifying paths; skipping.")
        return convergence_results

    # --- debug: overview of all paths ---------------------------------------
    if debug:
        overview = image.copy()
        palette = [
            (255, 0, 0), (0, 200, 0), (0, 0, 255),
            (255, 165, 0), (128, 0, 128), (0, 255, 255),
            (255, 0, 255), (128, 128, 0)
        ]
        for idx, pg in enumerate(output_list):
            if idx in qualifying_indices:
                continue
            fp = compute_full_path(pg, grid)
            if fp is not None and len(fp) > 0:
                pts_xy = np.flip(fp, axis=1).reshape((-1, 1, 2)).astype(np.int32)
                cv2.polylines(overview, [pts_xy], False, (160, 160, 160), 1)
                start_pt = (int(fp[0][1]), int(fp[0][0]))
                cv2.putText(overview, f"g{idx}", start_pt,
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (160, 160, 160), 1)
        for k, fp in enumerate(full_paths):
            color = palette[k % len(palette)]
            pts_xy = np.flip(fp, axis=1).reshape((-1, 1, 2)).astype(np.int32)
            cv2.polylines(overview, [pts_xy], False, color, 2)
            start_pt = (int(fp[0][1]), int(fp[0][0]))
            cv2.putText(overview, f"G{qualifying_indices[k]}", start_pt,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        for poi_xy in all_poi_coords:
            cv2.circle(overview, (int(poi_xy[0]), int(poi_xy[1])),
                       3, (255, 255, 255), 1)
        cv2.imshow('All Paths (color=qualifying, gray=excluded)',
                   cv2.resize(overview, (1300, int(overview.shape[0] * 1300 / overview.shape[1]))))
        cv2.waitKey(0)

    # --- helper: find where two paths share a segment then split ------------
    def _find_junctions(path_a, path_b):
        """Find the on-path pixels where two paths diverge or converge.

        Two paths "share a segment" when their nearest-neighbour distance is
        below *proximity_threshold*.  A fork is the last shared pixel before
        they split apart; a merge is the first shared pixel where they come
        together.  The returned point is an actual pixel on path_a — not a
        midpoint in empty space.

        Returns (junction_points, min_dist) or None.
        """
        if cKDTree is not None:
            tree_b = cKDTree(path_b)
            dists_a, _ = tree_b.query(path_a)
        else:
            dists_a = np.empty(len(path_a))
            for k, pt in enumerate(path_a):
                dists_a[k] = float(np.min(np.linalg.norm(path_b - pt, axis=1)))

        min_dist = float(np.min(dists_a))
        if debug:
            shared = int(np.sum(dists_a < proximity_threshold))
            print(f"     dist: min={min_dist:.1f} mean={np.mean(dists_a):.1f} "
                  f"shared_pixels={shared}/{len(dists_a)}")
        if min_dist > proximity_threshold:
            return None  # paths never share a segment

        # Boolean: True where the two paths run on the same segment
        shared_mask = dists_a < proximity_threshold

        # Detect transitions along path_a:
        #   +1 = separate → shared  (MERGE — paths coming together)
        #   -1 = shared → separate  (FORK  — paths splitting apart)
        transitions = np.diff(shared_mask.astype(np.int8))
        transition_indices = np.where(transitions != 0)[0]

        if debug and len(transition_indices) > 0:
            for t_idx in transition_indices:
                kind = "MERGE" if transitions[t_idx] > 0 else "FORK"
                print(f"       idx {t_idx}: {kind}  "
                      f"dist {dists_a[t_idx]:.1f} -> {dists_a[t_idx+1]:.1f}")

        junction_points = []
        for t_idx in transition_indices:
            if transitions[t_idx] < 0:
                # FORK: shared→separate — the fork pixel is the last shared one
                pick_idx = t_idx
            else:
                # MERGE: separate→shared — the merge pixel is the first shared one
                pick_idx = t_idx + 1

            # Report the actual pixel on path_a at the split/merge point
            pt = path_a[pick_idx]  # [y, x]
            jx, jy = float(pt[1]), float(pt[0])  # convert to [x, y]

            # Skip if this point is right on top of a known POI
            if len(all_poi_coords) > 0:
                poi_dists = np.linalg.norm(
                    all_poi_coords - np.array([jx, jy]), axis=1)
                nearest = float(np.min(poi_dists))
                if nearest < poi_exclusion_radius:
                    if debug:
                        print(f"       SKIP ({jx:.0f},{jy:.0f}) "
                              f"— {nearest:.0f}px from POI")
                    continue

            kind = "FORK" if transitions[t_idx] < 0 else "MERGE"
            if debug:
                print(f"       KEEP {kind} at ({jx:.0f},{jy:.0f})")
            junction_points.append([jx, jy])

        if not junction_points:
            return None
        return junction_points, min_dist

    # --- pairwise comparison ------------------------------------------------
    for i in range(len(full_paths)):
        for j in range(i + 1, len(full_paths)):
            if debug:
                print(f"\nG{qualifying_indices[i]} vs G{qualifying_indices[j]}:")
            result = _find_junctions(full_paths[i], full_paths[j])
            if result is None:
                if debug:
                    print("  -> no shared segment")
                continue
            junction_points, min_dist = result
            if debug:
                print(f"  -> {len(junction_points)} junction(s), "
                      f"min_dist={min_dist:.1f}px")

            convergence_results.append({
                'path_a_idx': qualifying_indices[i],
                'path_b_idx': qualifying_indices[j],
                'junction_points': junction_points,
                'min_distance': min_dist
            })

            # --- per-pair debug view ----------------------------------------
            if debug:
                pair_viz = image.copy()
                pts_a = np.flip(full_paths[i], 1).reshape((-1, 1, 2)).astype(np.int32)
                pts_b = np.flip(full_paths[j], 1).reshape((-1, 1, 2)).astype(np.int32)
                cv2.polylines(pair_viz, [pts_a], False, (255, 0, 0), 2)
                cv2.polylines(pair_viz, [pts_b], False, (0, 200, 0), 2)
                for poi_xy in all_poi_coords:
                    cv2.circle(pair_viz, (int(poi_xy[0]), int(poi_xy[1])),
                               3, (255, 255, 255), 1)
                for jp in junction_points:
                    c = (int(jp[0]), int(jp[1]))
                    diamond = np.array([
                        [c[0], c[1] - 8], [c[0] + 8, c[1]],
                        [c[0], c[1] + 8], [c[0] - 8, c[1]],
                    ], dtype=np.int32)
                    cv2.fillPoly(pair_viz, [diamond], (255, 0, 255))
                    cv2.putText(pair_viz, "FORK", (c[0]+10, c[1]-5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 255), 1)
                cv2.imshow(
                    f'G{qualifying_indices[i]} vs G{qualifying_indices[j]}',
                    cv2.resize(pair_viz, (1300, int(pair_viz.shape[0]*1300/pair_viz.shape[1]))))
                cv2.waitKey(0)

    # --- deduplicate junction points across all pairs -----------------------
    # Multiple pairs may detect the same physical fork; merge nearby points.
    all_junctions = []
    for cr in convergence_results:
        all_junctions.extend(cr['junction_points'])

    if len(all_junctions) > 1:
        unique = [all_junctions[0]]
        for jp in all_junctions[1:]:
            if all(np.linalg.norm(np.array(jp) - np.array(u)) > proximity_threshold
                   for u in unique):
                unique.append(jp)
        if debug and len(unique) < len(all_junctions):
            print(f"Deduplicated {len(all_junctions)} -> {len(unique)} "
                  f"unique junction(s)")
        all_junctions = unique

    # --- debug: summary visualisation ---------------------------------------
    if debug:
        print(f"\nTotal junction pairs: {len(convergence_results)}, "
              f"unique junction points: {len(all_junctions)}")
        viz = image.copy()
        palette = [
            (255, 0, 0), (0, 200, 0), (0, 0, 255),
            (255, 165, 0), (128, 0, 128), (0, 255, 255),
            (255, 0, 255), (128, 128, 0)
        ]
        for k, fp in enumerate(full_paths):
            color = palette[k % len(palette)]
            pts_xy = np.flip(fp, axis=1).reshape((-1, 1, 2)).astype(np.int32)
            cv2.polylines(viz, [pts_xy], False, color, 2)
            start_pt = (int(fp[0][1]), int(fp[0][0]))
            cv2.putText(viz, f"G{qualifying_indices[k]}", start_pt,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        for poi_xy in all_poi_coords:
            cv2.circle(viz, (int(poi_xy[0]), int(poi_xy[1])),
                       3, (255, 255, 255), 1)
        for jp in all_junctions:
            c = (int(jp[0]), int(jp[1]))
            diamond = np.array([
                [c[0], c[1] - 10], [c[0] + 10, c[1]],
                [c[0], c[1] + 10], [c[0] - 10, c[1]],
            ], dtype=np.int32)
            cv2.fillPoly(viz, [diamond], (255, 0, 255))

        cv2.imshow('Fork/Junction Detection - Summary',
                   cv2.resize(viz, (1300, int(viz.shape[0]*1300/viz.shape[1]))))
        cv2.waitKey(0)

    return convergence_results


def detect_multi_segment_junctions(output_list, image, proximity_radius=10,
                                    min_segments=2, debug=True):
    """
    Detect and visualize points where multiple individual chained segments
    (from compute_full_path) pass through the same location.

    Each path group is broken into its individual A* segments (the colored
    pieces shown in 'compute_full_path - Chained Segments'). A density map
    is built from every individual segment, and regions where >= min_segments
    overlap are reported as junction points.

    Args:
        output_list: List of point-group dicts from flood_fill_analysis / ordering.
        image: BGR image used to build the A* cost grid.
        proximity_radius: Pixel radius for segment zone dilation (default 10).
        min_segments: Minimum number of overlapping segments to qualify as
                      a junction (default 2).
        debug: If True, show chained segments, junctions, and density heatmap.

    Returns:
        list of dicts with keys:
            'point': [x, y] pixel coordinates of junction center
            'segment_count': number of individual segments passing through
            'group_indices': list of output_list group indices involved
            'segment_labels': list of (group_idx, seg_idx) tuples
    """
    # Build A* grid
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary_image = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    grid = binary_image.astype(np.float32)
    grid[grid == 0] = 1
    grid[grid == 255] = 64

    img_height, img_width = image.shape[:2]

    # Compute chained segments for all qualifying groups
    all_segments = []       # list of individual segment arrays
    segment_labels = []     # (group_idx, seg_idx) for each segment
    group_full_paths = []   # full concatenated path per group (for viz)
    group_indices = []      # which output_list indices have paths

    for idx, pg in enumerate(output_list):
        if not pg.get('cleaned_points_of_int'):
            continue
        result = compute_full_path(pg, grid, return_segments=True)
        if result is None:
            continue
        full_path, segments = result
        if full_path is None or len(segments) == 0:
            continue
        group_full_paths.append(full_path)
        group_indices.append(idx)
        for seg_idx, seg in enumerate(segments):
            all_segments.append(seg)
            segment_labels.append((idx, seg_idx))

    if debug:
        print(f"Collected {len(all_segments)} individual segments "
              f"from {len(group_indices)} path groups")

    if len(all_segments) < min_segments:
        if debug:
            print(f"Only {len(all_segments)} segments, need >= {min_segments}")
        return []

    # Build per-segment zone masks and accumulate into density count map
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (proximity_radius * 2 + 1, proximity_radius * 2 + 1))
    count_map = np.zeros((img_height, img_width), dtype=np.int32)
    segment_masks = []

    for seg in all_segments:
        mask = np.zeros((img_height, img_width), dtype=np.uint8)
        pts_xy = np.flip(seg.astype(np.int32), axis=1).reshape((-1, 1, 2))
        cv2.polylines(mask, [pts_xy], isClosed=False, color=255, thickness=1)
        dilated = cv2.dilate(mask, kernel, iterations=1)
        segment_masks.append(dilated)
        count_map += (dilated > 0).astype(np.int32)

    # Threshold to find multi-segment junction areas
    junction_mask = (count_map >= min_segments).astype(np.uint8) * 255

    # Find connected junction regions
    contours, _ = cv2.findContours(junction_mask, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)

    junction_points = []
    for contour in contours:
        M = cv2.moments(contour)
        if M["m00"] == 0:
            x, y, w, h = cv2.boundingRect(contour)
            cx, cy = x + w // 2, y + h // 2
        else:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

        # Identify which individual segments contribute at this junction
        contributing_labels = []
        contributing_groups = set()
        for k, mask in enumerate(segment_masks):
            if 0 <= cy < img_height and 0 <= cx < img_width and mask[cy, cx] > 0:
                contributing_labels.append(segment_labels[k])
                contributing_groups.add(segment_labels[k][0])

        if len(contributing_labels) >= min_segments:
            junction_points.append({
                'point': [cx, cy],
                'segment_count': len(contributing_labels),
                'group_indices': sorted(contributing_groups),
                'segment_labels': contributing_labels
            })

    if debug:
        _visualize_multi_segment_junctions(
            image, all_segments, segment_labels, group_full_paths,
            group_indices, junction_points, count_map, min_segments,
            output_list)

    return junction_points


def _visualize_multi_segment_junctions(image, all_segments, segment_labels,
                                        group_full_paths, group_indices,
                                        junction_points, count_map,
                                        min_segments, output_list):
    """Visualize multi-segment junction detection using individual chained segments."""
    img_height, img_width = image.shape[:2]
    display_width = 1300
    scale = display_width / img_width
    display_height = int(img_height * scale)

    segment_palette = [
        (255, 0, 0), (0, 200, 0), (0, 0, 255),
        (255, 165, 0), (128, 0, 128), (0, 255, 255),
        (255, 0, 255), (128, 128, 0), (0, 128, 128),
        (128, 0, 0), (0, 128, 0), (0, 0, 128),
        (200, 200, 0), (0, 200, 200), (200, 0, 200)
    ]

    # --- 1. Show each individual segment one at a time ---
    for k, seg in enumerate(all_segments):
        seg_viz = image.copy()
        color = segment_palette[k % len(segment_palette)]
        grp, si = segment_labels[k]

        # Draw this segment
        pts_xy = np.flip(seg, axis=1).reshape((-1, 1, 2)).astype(np.int32)
        cv2.polylines(seg_viz, [pts_xy], False, color, 3)

        # Mark start and end of segment
        seg_start = (int(seg[0][1]), int(seg[0][0]))
        seg_end = (int(seg[-1][1]), int(seg[-1][0]))
        cv2.circle(seg_viz, seg_start, 6, (0, 0, 255), -1)   # red start
        cv2.circle(seg_viz, seg_end, 6, (0, 255, 0), -1)      # green end

        # Label
        cv2.putText(seg_viz, f"Group {grp} - Segment {si}  ({len(seg)} px)",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
        cv2.putText(seg_viz, f"Start {seg_start}  End {seg_end}",
                    (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

        # Draw any junction markers that involve this segment
        for jp in junction_points:
            if (grp, si) in jp['segment_labels']:
                pt = (jp['point'][0], jp['point'][1])
                cv2.circle(seg_viz, pt, 10, (255, 0, 255), -1)
                cv2.circle(seg_viz, pt, 12, (255, 255, 255), 2)

        cv2.imshow('Segment View',
                   cv2.resize(seg_viz, (display_width, display_height)))
        cv2.waitKey(0)

    # --- 2. Summary with all segments and junction markers ---
    viz = image.copy()
    for k, seg in enumerate(all_segments):
        color = segment_palette[k % len(segment_palette)]
        pts_xy = np.flip(seg, axis=1).reshape((-1, 1, 2)).astype(np.int32)
        cv2.polylines(viz, [pts_xy], False, color, 2)
        grp, si = segment_labels[k]
        start_pt = (int(seg[0][1]), int(seg[0][0]))
        cv2.putText(viz, f"G{grp}S{si}", start_pt,
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)

    for k, idx in enumerate(group_indices):
        pg = output_list[idx]
        pt = pg['point']
        cv2.circle(viz, (int(pt[0]), int(pt[1])), 5, (0, 0, 255), -1)
        for cp in pg.get('cleaned_points_of_int', []):
            cv2.circle(viz, (int(cp[0]), int(cp[1])), 3, (0, 255, 0), -1)

    for jp in junction_points:
        pt = (jp['point'][0], jp['point'][1])
        count = jp['segment_count']
        radius = 8 + (count - min_segments) * 4
        cv2.circle(viz, pt, radius + 2, (255, 255, 255), 2)
        cv2.circle(viz, pt, radius, (255, 0, 255), -1)
        cv2.putText(viz, str(count), (pt[0] - 4, pt[1] + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    cv2.imshow('Multi-Segment Junctions (All Segments)',
               cv2.resize(viz, (display_width, display_height)))
    cv2.waitKey(0)

    # --- 2. Density heatmap blended with original ---
    max_count = max(count_map.max(), 1)
    normalized = (count_map.astype(np.float64) / max_count * 255).astype(np.uint8)
    heatmap = cv2.applyColorMap(normalized, cv2.COLORMAP_JET)
    blended = cv2.addWeighted(image, 0.4, heatmap, 0.6, 0)

    for jp in junction_points:
        pt = (jp['point'][0], jp['point'][1])
        cv2.circle(blended, pt, 10, (255, 255, 255), 2)

    cv2.imshow('Segment Density Heatmap',
               cv2.resize(blended, (display_width, display_height)))
    cv2.waitKey(0)

    print(f"Found {len(junction_points)} multi-segment junctions "
          f"(min_segments={min_segments})")
    for i, jp in enumerate(junction_points):
        labels_str = ', '.join(f'G{g}S{s}' for g, s in jp['segment_labels'])
        print(f"  Junction {i}: ({jp['point'][0]}, {jp['point'][1]}) "
              f"- {jp['segment_count']} segments [{labels_str}] "
              f"from groups {jp['group_indices']}")


def detect_radial_path_dropoff(output_list, image, proximity_radius=8, debug=True):
    """
    For each path group, compute independent A* paths from the group's origin
    to every waypoint. Overlay all paths into a density map and detect points
    where the path count drops (i.e. where paths branch away from the shared trunk).

    Args:
        output_list: List of point-group dicts from flood_fill_analysis / ordering.
        image: BGR image used to build the A* cost grid.
        proximity_radius: Pixel radius for path dilation when building density (default 8).
        debug: If True, visualize each group's radial paths and drop-off points.

    Returns:
        list of dicts per group:
            'group_idx': index into output_list
            'origin': [x, y]
            'dropoff_points': list of {'point': [x, y], 'from_count': int, 'to_count': int}
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary_image = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    grid = binary_image.astype(np.float32)
    grid[grid == 0] = 1
    grid[grid == 255] = 64

    img_height, img_width = image.shape[:2]
    display_width = 1300
    scale = display_width / img_width
    display_height = int(img_height * scale)

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (proximity_radius * 2 + 1, proximity_radius * 2 + 1))

    segment_palette = [
        (255, 0, 0), (0, 200, 0), (0, 0, 255),
        (255, 165, 0), (128, 0, 128), (0, 255, 255),
        (255, 0, 255), (128, 128, 0), (0, 128, 128),
        (200, 200, 0), (0, 200, 200), (200, 0, 200)
    ]

    all_results = []

    for idx, pg in enumerate(output_list):
        waypoints = pg.get('cleaned_points_of_int', [])
        if len(waypoints) < 2:
            continue

        origin = pg['point']
        origin_yx = [int(origin[1]), int(origin[0])]

        # Compute independent A* paths from origin to each waypoint
        radial_paths = []
        radial_wp_indices = []  # track which waypoint each path goes to
        for wp_idx, wp in enumerate(waypoints):
            dest_yx = [int(wp[1]), int(wp[0])]
            if not (0 <= origin_yx[0] < img_height and 0 <= origin_yx[1] < img_width and
                    0 <= dest_yx[0] < img_height and 0 <= dest_yx[1] < img_width):
                continue
            path = pyastar2d.astar_path(grid, origin_yx, dest_yx, allow_diagonal=True)
            if path is not None and len(path) > 0:
                radial_paths.append(path)
                radial_wp_indices.append(wp_idx)

        if len(radial_paths) < 2:
            continue

        # Build density map: how many radial paths pass through each pixel
        count_map = np.zeros((img_height, img_width), dtype=np.int32)
        path_masks = []
        for rp in radial_paths:
            mask = np.zeros((img_height, img_width), dtype=np.uint8)
            pts_xy = np.flip(rp.astype(np.int32), axis=1).reshape((-1, 1, 2))
            cv2.polylines(mask, [pts_xy], isClosed=False, color=255, thickness=1)
            dilated = cv2.dilate(mask, kernel, iterations=1)
            path_masks.append(dilated)
            count_map += (dilated > 0).astype(np.int32)

        # Walk outward from origin along each radial path and detect where
        # count_map drops — these are branch/split points
        dropoff_points = []
        seen_locations = []
        dedup_radius = proximity_radius * 3

        for rp_idx, rp in enumerate(radial_paths):
            prev_count = None
            for pix_idx in range(0, len(rp), 3):  # sample every 3 pixels
                py, px = int(rp[pix_idx][0]), int(rp[pix_idx][1])
                if 0 <= py < img_height and 0 <= px < img_width:
                    cur_count = int(count_map[py, px])
                    if prev_count is not None and cur_count < prev_count:
                        # Check not too close to an already-found drop-off
                        too_close = False
                        for seen in seen_locations:
                            if abs(px - seen[0]) < dedup_radius and abs(py - seen[1]) < dedup_radius:
                                too_close = True
                                break
                        if not too_close:
                            dropoff_points.append({
                                'point': [px, py],
                                'from_count': prev_count,
                                'to_count': cur_count
                            })
                            seen_locations.append([px, py])
                    prev_count = cur_count

        all_results.append({
            'group_idx': idx,
            'origin': [origin[0], origin[1]],
            'dropoff_points': dropoff_points
        })

        if debug:
            # --- Show each radial path one at a time ---
            for rp_idx, rp in enumerate(radial_paths):
                path_viz = image.copy()
                color = segment_palette[rp_idx % len(segment_palette)]
                pts_xy = np.flip(rp, axis=1).reshape((-1, 1, 2)).astype(np.int32)
                cv2.polylines(path_viz, [pts_xy], False, color, 3)

                # Origin (red) and destination (green)
                cv2.circle(path_viz, (int(origin[0]), int(origin[1])), 6, (0, 0, 255), -1)
                wp_i = radial_wp_indices[rp_idx]
                wp = waypoints[wp_i]
                cv2.circle(path_viz, (int(wp[0]), int(wp[1])), 6, (0, 255, 0), -1)

                cv2.putText(path_viz,
                            f"Group {idx} - Radial path {rp_idx}/{len(radial_paths)}  ({len(rp)} px)",
                            (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

                # Show drop-off points relevant to this path
                for dp in dropoff_points:
                    pt = (dp['point'][0], dp['point'][1])
                    cv2.circle(path_viz, pt, 10, (0, 255, 255), -1)
                    cv2.circle(path_viz, pt, 12, (255, 255, 255), 2)
                    cv2.putText(path_viz, f"{dp['from_count']}->{dp['to_count']}",
                                (pt[0] + 14, pt[1] + 4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

                cv2.imshow('Radial Path View',
                           cv2.resize(path_viz, (display_width, display_height)))
                cv2.waitKey(0)

            # --- Summary: all radial paths + drop-off markers ---
            summary = image.copy()
            for rp_idx, rp in enumerate(radial_paths):
                color = segment_palette[rp_idx % len(segment_palette)]
                pts_xy = np.flip(rp, axis=1).reshape((-1, 1, 2)).astype(np.int32)
                cv2.polylines(summary, [pts_xy], False, color, 2)

            cv2.circle(summary, (int(origin[0]), int(origin[1])), 7, (0, 0, 255), -1)
            cv2.putText(summary, "ORIGIN", (int(origin[0]) + 10, int(origin[1]) - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

            for wp_idx, wp in enumerate(waypoints):
                color = segment_palette[wp_idx % len(segment_palette)]
                cv2.circle(summary, (int(wp[0]), int(wp[1])), 4, color, -1)

            for dp in dropoff_points:
                pt = (dp['point'][0], dp['point'][1])
                cv2.circle(summary, pt, 10, (0, 255, 255), -1)
                cv2.circle(summary, pt, 12, (255, 255, 255), 2)
                cv2.putText(summary, f"{dp['from_count']}->{dp['to_count']}",
                            (pt[0] + 14, pt[1] + 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

            cv2.imshow('Radial Paths Summary',
                       cv2.resize(summary, (display_width, display_height)))
            cv2.waitKey(0)

            # --- Density heatmap for this group ---
            max_count = max(count_map.max(), 1)
            normalized = (count_map.astype(np.float64) / max_count * 255).astype(np.uint8)
            heatmap = cv2.applyColorMap(normalized, cv2.COLORMAP_JET)
            blended = cv2.addWeighted(image, 0.4, heatmap, 0.6, 0)

            for dp in dropoff_points:
                pt = (dp['point'][0], dp['point'][1])
                cv2.circle(blended, pt, 10, (255, 255, 255), 2)

            cv2.imshow('Radial Density Heatmap',
                       cv2.resize(blended, (display_width, display_height)))
            cv2.waitKey(0)

            print(f"Group {idx}: origin=({origin[0]:.0f},{origin[1]:.0f}), "
                  f"{len(radial_paths)} radial paths, {len(dropoff_points)} drop-off points")
            for di, dp in enumerate(dropoff_points):
                print(f"  Drop-off {di}: ({dp['point'][0]}, {dp['point'][1]}) "
                      f"count {dp['from_count']} -> {dp['to_count']}")

    return all_results


def control_module_roi_points_and_orientation_detector(output_list, control_module_roi_dict, image, debug=True):
    """
    Performs slices vertically and horizontally arround the control module ROI to detect points of interest and their orientation.

    Args:
        output_list: List of output dictionaries from flood_fill_analysis
        control_module_roi_dict: Dictionary mapping control module IDs to their ROI points
        image: The binary image used for creating the A* grid
        debug: Boolean flag for debugging

    Returns:
        output_list: The updated output_list with control module points of interest and their orientation
        control_module_orientation_dict: Dictionary mapping control module IDs to their orientation

    """
    
    # Get all points of interest from output_list for flood fill analysis
    all_points_of_interest = []
    for output in output_list:
        all_points_of_interest.extend(output['cleaned_points_of_int'])
        all_points_of_interest.append(output['point'])
    
    # Process each control module
    for module_id, module_data in control_module_roi_dict.items():
        roi_points = module_data[0]  # Get the ROI points
        module_name = module_data[1]  # Get the module name
        
        if not roi_points:
            continue
            
        # Calculate the center of the ROI
        roi_points_array = np.array(roi_points)
        if len(roi_points_array.shape) > 2:
            roi_points_array = np.array(extract_two_element_lists(roi_points))
        
        if len(roi_points_array) == 0:
            continue
            
        roi_center = np.mean(roi_points_array, axis=0)
        center_x, center_y = int(roi_center[0]), int(roi_center[1])
        
        # Get ROI bounds for slicing
        roi_x_coords = roi_points_array[:, 0]
        roi_y_coords = roi_points_array[:, 1]
        min_x, max_x = int(np.min(roi_x_coords)), int(np.max(roi_x_coords))
        min_y, max_y = int(np.min(roi_y_coords)), int(np.max(roi_y_coords))
        
        # Extend slice area beyond ROI bounds
        slice_margin = 1
        img_height, img_width = image.shape[:2]
        
        # Prepare the base image for flood fill analysis
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, binary_image = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)

        # Paint the ROI area black
        cv2.fillPoly(binary_image, [roi_points_array.astype(np.int32)], 0)
        
        # Convert to 3-channel image for flood fill
        base_image = cv2.cvtColor(binary_image, cv2.COLOR_GRAY2RGB)
        
        if debug:
            debug_image = base_image.copy()
            cv2.rectangle(debug_image, (min_x, min_y), (max_x, max_y), (255, 0, 0), 2)
            cv2.circle(debug_image, (center_x, center_y), 5, (0, 255, 0), -1)
            cv2.imshow(f'Control Module ROI - {module_name}', debug_image)
            cv2.waitKey(0)
        
        # Perform baseline flood fill from ROI center to get initial connections
        baseline_image = base_image.copy()
        baseline_connected_points = flood_fill_from_point(baseline_image, (center_x, center_y), all_points_of_interest)

        # Remove points associated with the control module itself
        baseline_connected_points = [pt for pt in baseline_connected_points if module_id != pt[2]]

        if debug:
            baseline_debug = baseline_image.copy()
            for point in baseline_connected_points:
                cv2.circle(baseline_debug, (point[0], point[1]), 3, (0, 255, 255), -1)
            cv2.imshow(f'Baseline Connections - {module_name}', baseline_debug)
            cv2.waitKey(0)
        
        # Test vertical slices (left and right)
        orientation_results = {
            'horizontal_blocked': False,
            'vertical_blocked': False,
            'left_connections': [],
            'right_connections': [],
            'top_connections': [],
            'bottom_connections': []
        }
        
        # Vertical slice on the left side of ROI
        left_slice_x = max(0, min_x - slice_margin)
        left_sliced_image = base_image.copy()
        left_sliced_image[:, left_slice_x:min_x] = (255, 255, 255)  # White out the slice area
        
        left_connected_points = flood_fill_from_point(left_sliced_image, (center_x, center_y), baseline_connected_points)
        left_disconnected = [p for p in baseline_connected_points if p not in left_connected_points]
        orientation_results['left_connections'] = left_disconnected
        
        if debug:
            left_debug = left_sliced_image.copy()
            cv2.line(left_debug, (left_slice_x, 0), (left_slice_x, img_height), (255, 0, 0), 3)
            cv2.line(left_debug, (min_x, 0), (min_x, img_height), (255, 0, 0), 3)
            for point in left_disconnected:
                cv2.circle(left_debug, (point[0], point[1]), 5, (0, 0, 255), -1)
            cv2.imshow(f'Left Slice - {module_name} (Disconnected: {len(left_disconnected)})', left_debug)
            cv2.waitKey(0)
        
        # Vertical slice on the right side of ROI
        right_slice_x = min(img_width, max_x + slice_margin)
        right_sliced_image = base_image.copy()
        right_sliced_image[:, max_x:right_slice_x] = (255, 255, 255)  # White out the slice area
        
        right_connected_points = flood_fill_from_point(right_sliced_image, (center_x, center_y), baseline_connected_points)
        right_disconnected = [p for p in baseline_connected_points if p not in right_connected_points]
        orientation_results['right_connections'] = right_disconnected
        
        if debug:
            right_debug = right_sliced_image.copy()
            cv2.line(right_debug, (max_x, 0), (max_x, img_height), (0, 255, 0), 3)
            cv2.line(right_debug, (right_slice_x, 0), (right_slice_x, img_height), (0, 255, 0), 3)
            for point in right_disconnected:
                cv2.circle(right_debug, (point[0], point[1]), 5, (0, 0, 255), -1)
            cv2.imshow(f'Right Slice - {module_name} (Disconnected: {len(right_disconnected)})', right_debug)
            cv2.waitKey(0)
        
        # Horizontal slice on the top side of ROI
        top_slice_y = max(0, min_y - slice_margin)
        top_sliced_image = base_image.copy()
        top_sliced_image[top_slice_y:min_y, :] = (255, 255, 255)  # White out the slice area
        
        top_connected_points = flood_fill_from_point(top_sliced_image, (center_x, center_y), baseline_connected_points)
        top_disconnected = [p for p in baseline_connected_points if p not in top_connected_points]
        orientation_results['top_connections'] = top_disconnected

        if debug:
            top_debug = top_sliced_image.copy()
            cv2.line(top_debug, (0, top_slice_y), (img_width, top_slice_y), (255, 255, 0), 3)
            cv2.line(top_debug, (0, min_y), (img_width, min_y), (255, 255, 0), 3)
            for point in top_disconnected:
                cv2.circle(top_debug, (point[0], point[1]), 5, (0, 0, 255), -1)
            cv2.imshow(f'Top Slice - {module_name} (Disconnected: {len(top_disconnected)})', top_debug)
            cv2.waitKey(0)
        
        # Horizontal slice on the bottom side of ROI
        bottom_slice_y = min(img_height, max_y + slice_margin)
        bottom_sliced_image = base_image.copy()
        bottom_sliced_image[max_y:bottom_slice_y, :] = (255, 255, 255)  # White out the slice area
        
        bottom_connected_points = flood_fill_from_point(bottom_sliced_image, (center_x, center_y), baseline_connected_points)
        bottom_disconnected = [p for p in baseline_connected_points if p not in bottom_connected_points]
        orientation_results['bottom_connections'] = bottom_disconnected
        
        if debug:
            bottom_debug = bottom_sliced_image.copy()
            cv2.line(bottom_debug, (0, max_y), (img_width, max_y), (255, 0, 255), 3)
            cv2.line(bottom_debug, (0, bottom_slice_y), (img_width, bottom_slice_y), (255, 0, 255), 3)
            for point in bottom_disconnected:
                cv2.circle(bottom_debug, (point[0], point[1]), 5, (0, 0, 255), -1)
            cv2.imshow(f'Bottom Slice - {module_name} (Disconnected: {len(bottom_disconnected)})', bottom_debug)
            cv2.waitKey(0)

        # If one of the pairs disconnects all connections
        total_disconnect_top_bottom = (len(top_disconnected) == len(baseline_connected_points) 
                                       or len(bottom_disconnected) == len(baseline_connected_points))
        total_disconnect_left_right = (len(left_disconnected) == len(baseline_connected_points) 
                                       or len(right_disconnected) == len(baseline_connected_points))
        
        # If pairs have common disconnections 
        common_disconnect_top_bottom = any(p in top_disconnected for p in bottom_disconnected)  
        common_disconnect_left_right = any(p in left_disconnected for p in right_disconnected)

        # If pairs have common connections
        common_connect_top_bottom = any(p in top_connected_points for p in bottom_connected_points)
        common_connect_left_right = any(p in left_connected_points for p in right_connected_points)

        if not total_disconnect_left_right and not common_disconnect_left_right and not common_connect_left_right:
            print("Horizontal orientation detected")
            primary_orientation = 'horizontal'

            first_data = {'point': [center_x - 2, center_y, module_id, module_name, None, 'primary', AnchorDirection.RIGHT],
                    'cleaned_points_of_int': left_connected_points}

            second_data = {'point': [center_x + 2, center_y, module_id, module_name, None, 'primary', AnchorDirection.TOP],
                    'cleaned_points_of_int': right_connected_points}


        elif not total_disconnect_top_bottom and not common_disconnect_top_bottom and not common_connect_top_bottom:
            print("Vertical orientation detected")
            primary_orientation = 'vertical'

            first_data = {'point': [center_x, center_y - 2, module_id, module_name, None, 'primary', AnchorDirection.BOTTOM],
                    'cleaned_points_of_int': top_connected_points}

            second_data = {'point': [center_x, center_y + 2, module_id, module_name, None, 'primary', AnchorDirection.TOP],
                    'cleaned_points_of_int': bottom_connected_points}
            

        else:
            continue

        

        if debug:
            print(f"Module {module_name} (ID: {module_id}): {primary_orientation} orientation")
            print(f"  Left disconnected: {len(left_disconnected)}")
            print(f"  Right disconnected: {len(right_disconnected)}")
            print(f"  Top disconnected: {len(top_disconnected)}")
            print(f"  Bottom disconnected: {len(bottom_disconnected)}")

        # Now, update the output_list to include control module points and remove original points
        index = None
        for i, output in enumerate(output_list):
            if any(pt in first_data['cleaned_points_of_int'] for pt in output['cleaned_points_of_int']):
                index = i
                break

        if index is not None:
            output_list.pop(index)
            output_list.append(first_data)
            output_list.append(second_data)

        if debug:
            print(f"Updated output list with control module {module_name} points.")
            debug_image = base_image.copy()
            for point in first_data['cleaned_points_of_int']:
                cv2.circle(debug_image, (point[0], point[1]), 5, (0, 0, 255), -1)
            for point in second_data['cleaned_points_of_int']:
                cv2.circle(debug_image, (point[0], point[1]), 5, (0, 255, 0), -1)
            cv2.imshow(f'Final Connections - {module_name}', debug_image)
            cv2.waitKey(0)
    
    return output_list


def flood_fill_from_point(image, start_point, points_to_check):
    """
    Helper function to perform flood fill from a point and return connected points of interest.
    
    Args:
        image: The image to perform flood fill on
        start_point: The starting point for flood fill (x, y)
        points_to_check: List of points to check for connection
        
    Returns:
        List of connected points from points_to_check
    """
    img_height, img_width = image.shape[:2]
    mask = np.zeros((img_height + 2, img_width + 2), np.uint8)
    
    # Ensure start point is within bounds
    if (0 <= start_point[0] < img_width and 0 <= start_point[1] < img_height):
        cv2.floodFill(image, mask, start_point, PROCESS_LINE_EXTRACTION_FILL_COLOR)
    
    connected_points = []
    for point in points_to_check:
        x, y = point[0], point[1]
        if (0 <= x < img_width and 0 <= y < img_height and
            np.array_equal(image[int(y), int(x)], PROCESS_LINE_EXTRACTION_FILL_COLOR)):
            connected_points.append(point)
    
    return connected_points

def split_output_list_on_secondary_points(output_list, debug=True):
    """
    Split the output list when 'secondary' points of interest are found.
    
    If two consecutive points have the same spa_id, end the current list with the first one
    and start a new list with the second one. If there's just one secondary point, both the
    current list and the new list will include it (as an end point and start point respectively).
    
    Args:
        output_list: List of output dictionaries from order_cleaned_points_of_int
        debug: Boolean flag for debugging
        
    Returns:
        A new output_list with splits at secondary points
    """
    new_output_list = []
    
    # Process each point group in the output list
    for point_group in output_list:
        cleaned_points = point_group['cleaned_points_of_int']
        
        # Skip if there are no points or only one point (no need to split)
        if len(cleaned_points) <= 1:
            new_output_list.append(point_group)
            continue
        
        # Track split indices
        split_indices = []
        
        # Find all secondary points and consecutive points with the same spa_id
        for i in range(len(cleaned_points) - 1):
            current_point = cleaned_points[i]
            next_point = cleaned_points[i + 1]

            appended = False
            
            # Check if point is secondary type or if consecutive points have the same spa_id
            # Point structure is assumed to be [x, y, spa_id, name, idx, type]
            if (len(current_point) >= 6 and current_point[5] == 'secondary' and 
                i not in split_indices):
                split_indices.append(i)
                appended = True
            
            # Check if consecutive points have the same spa_id
            if (len(current_point) >= 6 and len(next_point) >= 6 and 
                current_point[2] is not None and next_point[2] is not None and 
                current_point[2] == next_point[2] and current_point[5] == 'secondary'):
                split_indices.append(i + 1)
            elif appended:
                split_indices.append(i)  # Ensure the next point is also included
        
        # Add the last index if it's not already in the list
        if len(cleaned_points) - 1 not in split_indices:
            split_indices.append(len(cleaned_points) - 1)
        
        # If no splits needed, add the original point group
        if not split_indices:
            new_output_list.append(point_group)
            continue
        
        # Add unique split indices in order
        split_indices = sorted(set(split_indices))
        
        if debug:
            print(f"Split indices for point group: {split_indices}")

        split_point_group(new_output_list, point_group, cleaned_points, split_indices)
            
        

    if debug:
        print(f"Original output list had {len(output_list)} groups, new output list has {len(new_output_list)} groups")
    
    return new_output_list

def split_point_group(new_output_list, point_group, cleaned_points, split_indices):
    start_idx = 0
        # Create a copy of the current point group
    new_group = {
            'point': point_group['point'],
            'cleaned_cross_points': point_group.get('cleaned_cross_points', []),
            'cleaned_points_of_int': cleaned_points[start_idx:split_indices[0] + 1],  # Include the split point
            'cleaned_contours': point_group.get('cleaned_contours', [])
        }
        
    new_output_list.append(new_group)
        
    # Update the start index for the next group
        
    # Create new point groups based on the split indices

    for i, split_idx in enumerate(split_indices[1:-1]):
        # Create a new point group with the points up to and including the split point
        split_point = cleaned_points[split_idx]  # The point to split at

        end_idx = split_indices[i + 2]

        
            
        # Create a copy of the current point group
        new_group = {
                'point': split_point,
                'cleaned_cross_points': point_group.get('cleaned_cross_points', []),
                'cleaned_points_of_int': cleaned_points[split_idx:end_idx + 1],  # Include the split point
                'cleaned_contours': point_group.get('cleaned_contours', [])
            }
            
        new_output_list.append(new_group)


def find_nearest_contours_to_control_modules(control_module_roi_dict, closed_contours, output_list, image, max_distance=200, debug=True):
    """
    Find the nearest cleaned contours to each control module based on their ROI using A* pathfinding.
    
    :param control_module_roi_dict: Dictionary mapping control module IDs to their ROI points
    :param closed_contours: List of all detected closed contours
    :param cleaned_contours_indices: List of indices of cleaned contours from flood fill analysis
    :param image: Original image to create the grid for A* pathfinding
    :param max_distance: Maximum distance to consider a contour as related to a control module
    :return: Dictionary mapping control module IDs to lists of contour indices
    """
    cleaned_contours_indices = [[output_idx, contour_idx] for output_idx, output in enumerate(output_list) for contour_idx in output['cleaned_contours']]
    cleaned_modules = [point[2] for output in output_list for point in output['cleaned_points_of_int']]
    
    # Process only if we have contours to check
    if not closed_contours or not cleaned_contours_indices:
        return output_list
    
    # Prepare grid for A* pathfinding
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary_image = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    
    # Create grid where black lines have low cost (1) and white areas have high cost (inf)
    grid = binary_image.astype(np.float32)
    grid[grid == 0] = 1  # Black pixels (lines) have low cost
    grid[grid == 255] = 64  # White pixels have high cost
    
    
    for module_id, module_data in control_module_roi_dict.items():
        # Skip if the module ID is already processed
        if module_id in cleaned_modules:
            continue

        roi_points = module_data[0]  # Get the ROI points for the control module

        # Calculate centroid of the control module's ROI
        roi_points = np.array(roi_points)
        if len(roi_points.shape) > 2:  # Handle nested lists
            # Flatten the list if needed and extract points
            roi_points = np.array(extract_two_element_lists(roi_points))
        
        if len(roi_points) == 0:
            continue
            
        module_centroid = np.mean(roi_points, axis=0)
        module_point = (int(module_centroid[0]), int(module_centroid[1]))
        
        # First, sort contours by standard Euclidean distance to filter out far ones
        contour_euclidean_distances = []
        for output_idx, contour_idx in cleaned_contours_indices:
            if contour_idx >= len(closed_contours):
                continue
                
            contour = closed_contours[contour_idx]
            contour_points = np.array([point[0] for point in contour])
            contour_centroid = np.mean(contour_points, axis=0)
            contour_point = (int(contour_centroid[0]), int(contour_centroid[1]))
            
            # Calculate Euclidean distance
            euclidean_distance = np.sqrt((module_point[0] - contour_point[0])**2 + 
                                         (module_point[1] - contour_point[1])**2)
            
            contour_euclidean_distances.append((contour_idx, euclidean_distance, contour_point, output_idx))
        
        # Sort by Euclidean distance and take only the closest ones for A* calculation
        contour_euclidean_distances.sort(key=lambda x: x[1])
        
        # Only process the closest N contours with A* to save processing time
        # Or only process contours within a certain Euclidean distance
        close_contours_to_check = [(idx, dist, point, output_idx) for idx, dist, point, output_idx in contour_euclidean_distances
                                  if dist < max_distance * 2][:10]
        
        
        nearest_distance = float('inf')
        nearest_contour = None
        
        # Find paths to contours using A* pathfinding
        for contour_idx, distance, contour_point, output_idx in close_contours_to_check:
            # Ensure points are within image boundaries
            img_height, img_width = grid.shape

            # If the euclidean distance is already greater than the nearest found distance, skip
            if nearest_distance < distance:
                continue

            if (0 <= module_point[1] < img_height and 0 <= module_point[0] < img_width and
                0 <= contour_point[1] < img_height and 0 <= contour_point[0] < img_width):
                
                # Use A* to find path from module to contour
                path = pyastar2d.astar_path(
                    grid, 
                    [module_point[1], module_point[0]], 
                    [contour_point[1], contour_point[0]], 
                    allow_diagonal=True
                )
                
                # If a path is found, calculate its cost
                if path is not None and path.shape[0] > 0:
                    # Calculate the path cost (sum of grid costs along the path)
                    path_cost = sum(grid[p[0], p[1]] for p in path)
                    nearest_distance = min(nearest_distance, path_cost)
                    
                    # Only consider paths with reasonable cost
                    if path_cost < max_distance * len(path):
                        nearest_contour = [path_cost, path, module_point, contour_point, output_idx, contour_idx]

                    if debug:
                        maze = np.stack((binary_image, binary_image, binary_image), axis=2)
                        pts = np.flip(path, 1)
                        pts = pts.reshape((-1, 1, 2))
                        maze = cv2.polylines(maze, [pts], 
                                False, (0,0,255), 5)

                        cv2.circle(maze, module_point, 3, (255,0,0), 2)
                        cv2.circle(maze, contour_point, 3, (0,255,0), 2)
                        cv2.imshow('Distance to Contour', cv2.resize(maze, (1300, int(maze.shape[0]*1300/maze.shape[1]))))
                        cv2.waitKey(0)
        
      
        
        if debug and nearest_contour:
            path = nearest_contour[1]  # Get the path for the nearest contour
            maze = np.stack((binary_image, binary_image, binary_image), axis=2)
            pts = np.flip(path, 1)
            pts = pts.reshape((-1, 1, 2))
            maze = cv2.polylines(maze, [pts], 
                    False, (0,0,255), 5)

            cv2.circle(maze, module_point, 3, (255,0,0), 2)
            cv2.drawContours(maze, [closed_contours[nearest_contour[4]]], 0, (0,255,0), 2)
            cv2.imshow('Best Path to Contour', cv2.resize(maze, (1300, int(maze.shape[0]*1300/maze.shape[1]))))
            cv2.waitKey(0)
        
        output_idx = nearest_contour[4] 
        contour_idx = nearest_contour[5]
        module_point = nearest_contour[2]  
        contour_point = nearest_contour[3]
        module_name = module_data[1]  # Get the name of the control module
        module_type = module_data[2]  # Get the type of the control module
        output_list[output_idx]['cleaned_points_of_int'].append([contour_point[0], contour_point[1], module_id, module_name, None, module_type])  # Add the control module point to the cleaned points of interest

    return output_list


def extract_closed_contours(page_poi, image, debug=True):
    """
    Extracts closed contours from the image based on the points of interest (page_poi).
    :param page_poi: List of points of interest.
    :param image: The original image.
    :param debug: Boolean flag for debugging purposes.
    :return: List of closed contours found in the image.
    """
    _img = image.copy()
    for end_point in page_poi:
        x, y = end_point[0], end_point[1]
        color_around_pixel(_img, [x ,y], thickness=2, color=(255, 255, 255)) 

    img = cv2.threshold(cv2.cvtColor(_img, cv2.COLOR_BGR2GRAY), 240, 255, cv2.THRESH_BINARY)[1]

    # Flood fill all the page_poi points 
    mask = np.zeros((img.shape[0] + 2, img.shape[1] + 2), np.uint8)
    for point in page_poi:
        pt = (int(point[0]), int(point[1]))  # Ensure the point is in (x, y) format
         # Color the point with black
        cv2.floodFill(img, mask, pt, 0)  # Fill with black (0)
    
    if debug:
        cv2.imshow('Contours', img)
        cv2.waitKey(0)

    # Invert the image to make the lines white and background black
    img = cv2.bitwise_not(img)
    # Find all the closed contours in the image
    contours = cv2.findContours(img, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)[0]

    if debug:
        print(f"Number of contours found: {len(contours)}")
        
        
        for i, contour in enumerate(contours):
                print(f"Contour {i}: {len(contour)} points")
                cv2.drawContours(_img, contours, i, (0, 255, 0), 1)
        cv2.imshow('Contours', _img)
        cv2.waitKey(0)

    return contours
