

from bin.logic_acm_console import ACM_Console
import logging
import re
import shutil
import time
from typing import Dict
import uuid

import cv2
import numpy as np
import pyastar2d
from shapely.geometry import LineString, LinearRing, Point
from shapely import affinity
from shapely.ops import snap, unary_union
from shapely.geometry.polygon import Polygon
from bin.gui_config_elements import direction_buttons
from bin.gui_hmi_graphic_view import hmi_graphic_view
from bin.gui_linked_graphics_grid_view import linked_graphics_grid_view
from bin.gui_linked_text_entry_view import linked_text_entry
from bin.gui_elements import cell_line, custom_label, hover_toggle_button, set_active_canvas_screen
import tkinter as tk
import os
from bin.gui_page_link_list_view import page_links_list_view
from bin.logic_config import Config
from bin.logic_control_module import Control_Module
from bin.logic_extract_hmi_graphic import extract_hmi_graphic
from bin.logic_acm_data_handler import ACM_Data_Handler
from bin.gui_base64_icons import start_scan, test_on_page, flip_blue, flip_gray
from bin.logic_linked_graphic_scanner import Template_Flip, Template_Rotate
from bin.logic_pdf_render import render_page
from bin.logic_validators import Validators


try:
    from bin.logic_internal_database import Database
    from bin.gui_linked_graphic_view import linked_graphic_view
except:
    from logic_internal_database import Database
    from gui_linked_graphic_view import linked_graphic_view


def acm_safe_token(text):
    """ Turn free text into a fragment that keeps a generated ACM object name valid.

    :param text: The text to sanitise, typically OCR'd drawing text.
    :type text: str
    :return: A fragment of only letters, digits and single separating underscores.
    :rtype: str
    """
    token = re.sub(r'[^A-Za-z0-9_]', '_', text or '')
    token = re.sub(r'_+', '_', token).strip('_')

    if not token:
        return 'Unlinked'

    if not re.match(r'^[a-zA-Z_]', token):
        # ACM names may not start with a digit.
        token = 'D_' + token

    return token


class HMI_Display():
    """
    The HMI_Display class is used to create and manage HMI displays.
    """


    PRIMARY_GRAPHIC = 'Primary Graphic'
    SECONDARY_GRAPHIC = 'Secondary Graphic'

    PRIMARY_GRAPHIC_TYPE = 'hmi_display_page'
    SECONDARY_GRAPHIC_TYPE = 'hmi_page_link'

    def __init__(self, id, name, description, page_number, go_to_document_callback ) -> None:
        """
        Initializes the HMI_Display class.

        :param id: The ID of the HMI display.
        :type id: str
        :param name: The name of the HMI display.
        :type name: str
        :param description: The description of the HMI display.
        :type description: str
        :param page_number: The page number of the HMI display.
        :type page_number: int
        :param go_to_document_callback: The callback function to go to the document.
        :type go_to_document_callback: function

        :return: None
        :rtype: None
        """
        self.id = id
        self.name = name
        self.description = description
        self.page_number = page_number # Associated with the CatalogNumber column in the ACM SQL database
        self.__db : Database = None
        self.__primary_linked_graphic_view = linked_graphic_view( self.PRIMARY_GRAPHIC,redraw_callback=self.__redraw_config_canvas, 
                                                                    change_callback=self.__linked_graphic_change,
                                                                    goto_callback=self.__go_to_callback,
                                                                    is_primary_linked_graphic=True,
                                                                    scanning_done_callback=self.__scanning_done_callback,
                                                                    object_type=self.PRIMARY_GRAPHIC_TYPE
                                                                    )
        self.__secondary_linked_graphic_view = linked_graphic_view( self.SECONDARY_GRAPHIC,redraw_callback=self.__redraw_config_canvas, 
                                                                    change_callback=self.__linked_graphic_change,
                                                                    goto_callback=self.__go_to_callback,
                                                                    is_primary_linked_graphic=True,
                                                                    scanning_done_callback=self.__scanning_done_callback,
                                                                    object_type=self.SECONDARY_GRAPHIC_TYPE,
                                                                    template_flip=[Template_Flip.NONE,Template_Flip.HORIZONTALLY])   
        self.__connector_graphics = linked_graphics_grid_view('Connector Graphics','Used to connect pipelines '+
                                                'separated by unsed intruments.',add_linked_graphics_cell_callback=self.__redraw_config_canvas)
        self.__ignored_graphics = linked_graphics_grid_view('Ignored Graphics','Used to disconnect pipelines '+
                                                'separated by unsed intruments', add_linked_graphics_cell_callback=self.__redraw_config_canvas)
        self.__move_to_roi_func = None
        self.__clear_shown_text_roi_list_func = None
        self.__refresh_rois_func = None
        self.__draw_connecting_lines_func = None
        self.__go_to_roi_uid = None 
        self.__go_to_pno = None
        self.__document_selected_text = None
        self.__document_selected_func = None
        self.__go_to_document_callback = go_to_document_callback
        self.__linked_text = {}
        self.__busy_loading_data = False
        self.__primary_linked_graphic_data = None
        self.__secondary_linked_graphic_data = None
        self.__scan_results = {}
        self.__path = ''
        self.__pno = -1
        self.__primary_scan_results = {}
        self.__secondary_scan_results = {}
        self.__page_links = []
        self.__unlinked_page_links = []
        self.__connecting_lines = []
        self.__already_tested_pairs = {}
        self.__flow_direction = direction_buttons.NONE
        self.__flow_direction_description = None
        self.__secondary_linked_graphic_flip:list[Template_Flip]=[Template_Flip.NONE
                                                                ,Template_Flip.HORIZONTALLY]
        self.__secondary_linked_graphic_view.set_template_flip(self.__secondary_linked_graphic_flip)
        self.__secondary_scan_started = False
        self.__scanning_started = False

        self.__primary_graphic_scan_done = False
        self.__secondary_graphic_scan_done = False

        self.__primary_scanning_count = 0
        self.__secondary_scanning_count = 0
        self.__primary_done_saving = False
        self.__secondary_done_saving = False
        self.__build_display = None



    def set_name(self, name):
        """
        Sets the name of the control module.

        Parameters:
            name (str): The new name for the control module.

        Returns:
            None
        """
        self.name = name
        self.__save_to_database()
        
    def set_description(self, description):
        """
        Sets the description of the control module.

        Parameters:
            description (str): The new description for the control module.

        Returns:
            None
        """
        self.description = description
        self.__save_to_database()


    def get_document(self):
        """
        Returns the name of the document associated with the logic control module.

        If the path is not set, returns None.

        Returns:
            str or None: The name of the document or None if the path is not set.
        """
        if not self.__path:
            return None
        
        return self.__path.split('/')[-1]


    def get_page(self):
        """
        Returns the page number for the object based on the primary linked graphic.

        Returns:
            int: The current page number incremented by 1.
                If the page number is None or less than 0, returns None.
        """
        if self.__pno is None and self.__pno >= 0:
            return None
        
        return self.__pno + 1


    def get_coordinates(self):
        """
        Retrieves the coordinates of the linked graphic.

        Returns:
            tuple: A tuple containing the X and Y coordinates of the linked graphic, 
                   normalized by the page width and height respectively. 
                   The third element of the tuple is always True.
                   Returns None if no linked graphic is found.
        """
        primary_linked_graphic = self.__primary_linked_graphic_view.get_linked_graphic_data()
        
        if primary_linked_graphic:
            linked_graphic = primary_linked_graphic
        else:
            return None 
            
        return (linked_graphic['minX']/linked_graphic['page_width'],
                    linked_graphic['minY']/linked_graphic['page_height'],True)
        
        



    def document_selected_func(self, func):
        self.__document_selected_func = func


    def __scanning_done_callback(self,linked_graphic_name, results):
        """
        Callback function called when scanning is done for a linked graphic.

        Args:
            linked_graphic_name (str): The name of the linked graphic.
            results (list): The results of the scanning process.

        Returns:
            None
        """
        
        self.__scan_results[linked_graphic_name] = results

        if linked_graphic_name == self.PRIMARY_GRAPHIC:
        
            self.__build_from_primary_linked_graphic(results)
            self.__primary_graphic_scan_done = True
        
        if not self.__secondary_scan_started:
            self.__remove_background_task_callback_func(self.name)

        elif linked_graphic_name == self.SECONDARY_GRAPHIC:

            self.__build_from_secondary_linked_graphic(results)
            self.__secondary_graphic_scan_done = True

        if self.__primary_graphic_scan_done and self.__secondary_graphic_scan_done:
            self.__attach_page_links_to_pages()
            self.__scanning_started = False
            self.__remove_background_task_callback_func(self.name)

        if results is None:
            self.__scanning_started = False

        


    def __build_from_primary_linked_graphic(self, results):
        """
        Builds control modules from the primary linked graphic.

        :param results: List of results containing ROI information.
        :type results: list

        :return: None
        :rtype: None

        Builds control modules from the primary linked graphic by iterating through the results and extracting relevant information. It then calls the __build_new_control_module method to create new control modules based on the extracted information. Finally, it saves the page ROI data and logs the average scan time.

        Example:
            >>> __build_from_primary_linked_graphic(results)
        """

        path = ""
        roi_list = None

        self.__primary_scan_results = {}

        scan_times = []

        self.__primary_scanning_count = 0
        self.__primary_done_saving = False
        for result_roi_list, page_index, scan_time, template_to_match_ratio in results:

            scan_times.append(scan_time)

            for roi in result_roi_list:

                if roi_list is None:
                    path = roi['path']
                    roi_list = self.__db.get_project_document_roi(path)

                text_locations = roi['text_locations']
                list = []
                linked_text_to_search ={}
                character_differences = [] 
                for text_location in text_locations:
                    list.append(self.__get_substring_of_text_location(text_location,linked_text_to_search,self.PRIMARY_GRAPHIC,character_differences))
            
                for linked_text_name, text_to_search in linked_text_to_search.items():
                    if (linked_text_name == 'Name'  
                            and text_to_search != self.name):
                        

                        self.__build_new_hmi_display(path, roi_list, page_index, roi, text_to_search, text_locations, template_to_match_ratio)
                        self.__primary_scanning_count = self.__primary_scanning_count + 1
        self.__save_page_roi(path,roi_list)
        self.__primary_done_saving = True

        average_scan_time = sum(scan_times)/len(scan_times)
        logging.info('Average time to scan for Primary Linked Graphic: {}s per page'.format(str(average_scan_time)))
        logging.info('Done building HMI Displays from Primary Linked Graphic')
        
        if self.__refresh_rois_func:
            self.__refresh_rois_func()

    def __build_from_secondary_linked_graphic(self, results):
        """
        Builds control modules from a secondary linked graphic.

        Args:
            results (list): A list of pages containing result ROI information.

        Returns:
            None

        Raises:
            None

        """

        path = ""
        roi_list = None

        self.__secondary_scan_results = {}

        scan_times = []
        self.__secondary_scanning_count = 0
        self.__secondary_done_saving = False
        for result_roi_list, page_index, scan_time, template_to_match_ratio in results:

            scan_times.append(scan_time)

            for roi in result_roi_list:

                if roi_list is None:
                    path = roi['path']
                    roi_list = self.__db.get_project_document_roi(path)

                text_locations = roi['text_locations']
                list = []
                linked_text_to_search ={}
                character_differences = [] 
                for text_location in text_locations:
                    list.append(self.__get_substring_of_text_location(text_location,linked_text_to_search,self.SECONDARY_GRAPHIC,character_differences))
            
                for linked_text_name, text_to_search in linked_text_to_search.items():
                    if (linked_text_name == 'Name'):
                        print(text_to_search)
                        confidence = roi['confidence']

                        self.__build_new_page_link(path, roi_list, page_index, roi, text_to_search, text_locations, confidence,template_to_match_ratio)
                        self.__secondary_scanning_count = self.__secondary_scanning_count + 1
        self.__save_page_roi(path,roi_list)
        self.__secondary_done_saving = True

        average_scan_time = sum(scan_times)/len(scan_times)
        logging.info('Average time to scan for Secondary Linked Graphic: {}s per page'.format(str(average_scan_time)))
        logging.info('Done building Page Links from Secondary Linked Graphic')

        if self.__refresh_rois_func:
            self.__refresh_rois_func()


    def remove_background_task_callback(self, func):
        """
        Sets the callback function for removing a background task.

        Parameters:
        - func: The callback function to be set.

        Returns:
        None
        """
        self.__remove_background_task_callback_func = func


    def export_graphics(self, location):
        """
        Exports the static graphics associated with the hmi display to the specified location.

        Parameters:
        - location (str): The location to export the static graphics to.

        Returns:
        None
        """

        if location == '': return

        static_graphics = self.__db.get_all_static_graphic_on_page(self.__path,self.__pno)

        for graphic in static_graphics:
            method = graphic['hmi_graphic']['method']

            path = ''
            if hmi_graphic_view.EXTRACT_GRAPHIC == method:
                path = graphic['hmi_graphic']['extract_graphic']['svg_image_path']
            elif hmi_graphic_view.CUSTOM_GRAPHIC == method:
                path = graphic['hmi_graphic']['custom_graphic']['path']
            else:
                continue
            
            _, extension = os.path.splitext(path)
            shutil.copy(path, location+'/'+graphic['name']+extension)



    def __save_page_roi(self,path,roi_list):
        """
        Saves the page ROI for a specified document path and updates the database.

        Args:
            path (str): The document path the ROI will be saved for.
            roi_list (list): The list of ROIs to be saved.

        Returns:
            None
        """
        self.__db.insert_project_document_roi(path,roi_list)
        if self.__refresh_rois_func:
            self.__refresh_rois_func()

      
    def __attach_page_links_to_pages(self):
        """
        Attaches the page links to the pages in the database.

        Returns:
            None
        """

        path = ""
        roi_list = None
        hmi_pages_found = []


        for hmi_page_name, display_id in self.__primary_scan_results.items():
            if hmi_page_name in self.__secondary_scan_results:
                hmi_pages_found.append(hmi_page_name)
                hmi_display = self.__db.get_hmi_display(display_id)
                hmi_display['page_links'] = self.__secondary_scan_results[hmi_page_name]

                if roi_list is None:
                    path = hmi_display['path']
                    roi_list = self.__db.get_project_document_roi(path)

                for i in range(len(hmi_display['page_links'])):
                    old_roi_uid = hmi_display['page_links'][i]['roi_uid']
                    if display_id in old_roi_uid:
                        continue
                    
                    new_roi_uid = old_roi_uid +'-'+ display_id
                    hmi_display['page_links'][i]['roi_uid'] = new_roi_uid

                    pno = old_roi_uid.split('-')[0]
                    roi_list[int(pno)][new_roi_uid]=roi_list[int(pno)][old_roi_uid]
                    del roi_list[int(pno)][old_roi_uid]

                    self.__db.save_page_link_roi_to_hmi_display({
                        'hmi_display_id': display_id,
                        'roi_uid': new_roi_uid,
                        'path': hmi_display['path']
                    })
                hmi_display['secondary_linked_graphic'] = self.__secondary_scan_results[hmi_page_name][0]
                self.__db.save_hmi_display(hmi_display)

        if self.name in self.__secondary_scan_results:
            self.__page_links = self.__secondary_scan_results[self.name]
            hmi_pages_found.append(self.name)
            self.__save_to_database()

        # Remove already processed page links
        unlinked_page_links = []
        for page_name in self.__secondary_scan_results:
            if page_name in hmi_pages_found:
                continue
            for page_link in self.__secondary_scan_results[page_name]:
                page_link['page_name'] = page_name
                unlinked_page_links.append(page_link)

        unlinked_page_links_in_page = {}

        # Group the unlinked page links by page number
        for page_link in unlinked_page_links:
            page_number = str(page_link['pno'])
            if page_number not in unlinked_page_links_in_page:
                unlinked_page_links_in_page[page_number] = []
            unlinked_page_links_in_page[page_number].append(page_link)

        # Save the unlinked page links to the database
        for page_number, page_links in unlinked_page_links_in_page.items():
            hmi_display = self.__db.get_hmi_display_in_page(page_links[0]['path'], page_links[0]['pno'])
            
            hmi_display['unlinked_page_links'] = page_links

            for page_link in page_links:
                self.__db.save_page_link_roi_to_hmi_display({
                    'hmi_display_id': hmi_display['id'],
                    'roi_uid': page_link['roi_uid'],
                    'path': hmi_display['path']
                })

            self.__db.save_hmi_display(hmi_display)

            if self.__path == page_links[0]['path'] and self.__pno == page_links[0]['pno']:
                self.__unlinked_page_links = page_links
                self.__save_to_database()

        self.__save_page_roi(path,roi_list)
        if self.__refresh_rois_func:
            self.__refresh_rois_func()
                

                

                

    def __build_new_hmi_display(self, path, roi_list, page_index, roi, text_to_search, text_locations, template_to_match_ratio):
        """
        Builds a new HMI display based on the given parameters.
        
        :param roi_list: The list of ROIs to be saved.
        :type roi_list: list
        :param page_index: The index of the page.
        :type page_index: int
        :param roi: The region of interest (ROI) to be saved.
        :type roi: dict
        :param text_to_search: The text to search for.
        :type text_to_search: str
        :param text_locations: The locations of the text.
        :type text_locations: list
        :param template_to_match_ratio: The ratio of the template to match.
        :type template_to_match_ratio: float
        
        :return: None
        :rtype: None
        
        This function builds a new HMI display based on the given parameters. It creates a copy of the primary linked graphic 
        and linked text, and saves the new HMI display to the database. It then sets up the ROI in the ROI list.
        """
        
        primary_linked_graphic, text_old_to_new_roi_names, _ = self.__primary_linked_graphic_view.create_copy(path,page_index,roi['points'],text_locations,template_to_match_ratio)
        
        self.__primary_scan_results[text_to_search]=primary_linked_graphic['roi_uid']
                        
        new_linked_text = self.__copy_linked_text(page_index, text_to_search, text_old_to_new_roi_names)
            

        dict_data = {
                            'id': primary_linked_graphic['roi_uid'],
                            'name': text_to_search,
                            'description': '',
                            'change_user': os.getlogin(),
                            'path': path,
                            'pno': page_index,
                            'primary_linked_graphic': primary_linked_graphic,
                            'secondary_linked_graphic': {},
                            'linked_text':new_linked_text,
                            'flow_direction':self.__flow_direction,
                            'template_flip':[item.value for item in self.__secondary_linked_graphic_flip]
                        }

        self.__db.save_hmi_display(dict_data)

                        
        self.__setup_roi_in_roi_list(roi_list, page_index, primary_linked_graphic)



    def __copy_linked_text(self, page_index, text_to_search, text_old_to_new_roi_names):
        """
        Copies the linked text and updates the necessary fields based on the provided parameters.

        Args:
            page_index (int): The index of the page.
            text_to_search (str): The text to search for.
            text_old_to_new_roi_names (dict): A dictionary mapping old ROI names to new ROI names.
            character_differences (list): A list of character differences.

        Returns:
            dict: The copied and updated linked text.
        """
        new_linked_text = self.__linked_text.copy()

        if not new_linked_text or not 'Name' in new_linked_text:
            return new_linked_text
        
        new_linked_text['Name']['string'] = text_to_search
        
        for _, linked_text in new_linked_text['Name']['links'].items():
            linked_text['document_selected_text_roi_name'] = text_old_to_new_roi_names[linked_text['document_selected_text_roi_name']]
            linked_text['document_selected_text_pno'] = page_index
    
        return new_linked_text


    def __build_new_page_link(self, path, roi_list, page_index, roi, text_to_search, text_locations, confidence, template_to_match_ratio):
        """
        Builds a new page link based on the given parameters.

        Args:
            roi_list (list): The list of ROIs to be saved.
            page_index (int): The index of the page.
            roi (dict): The region of interest (ROI) to be saved.
            text_to_search (str): The text to search for.
            text_locations (list): The locations of the text.
            confidence (float): The confidence of the linked graphic.
            template_to_match_ratio (float): The ratio of the template to match.

        Returns:
            None
        """

        secondary_linked_graphic, text_old_to_new_roi_names, _ = self.__secondary_linked_graphic_view.create_copy(path,page_index,roi['points'],text_locations,template_to_match_ratio,
                                                                                                                None,roi['flip'])
        secondary_linked_graphic['confidence'] = confidence.item()
        secondary_linked_graphic['flip'] = roi['flip']
        secondary_linked_graphic['rotation'] = roi['rotation']

        
        
        if text_to_search not in self.__secondary_scan_results:
            self.__secondary_scan_results[text_to_search] = []

        self.__secondary_scan_results[text_to_search].append(secondary_linked_graphic)
        
                        
        self.__setup_roi_in_roi_list(roi_list, page_index, secondary_linked_graphic)


    def __is_highest_confidence_overlap(self, roi_list, page_index, new_roi_uid, confidence, object_type):
        '''Check to see if the new linked grapic has the highest confidence.'''
        for old_roi_uid, _ in roi_list[page_index].items():
            
            roi_details = old_roi_uid.split('-')
            if len(roi_details) < 5:
                continue
            test_rect = roi_details[1:5]
            rect = new_roi_uid.split('-')[1:5]
            if self.__is_rectangle_overlap(rect,test_rect) and object_type == roi_details[5]:
                hmi_display_id = '-'.join(roi_details[6:12])
                if hmi_display_id == '':
                    continue
                hmi_display = self.__db.get_hmi_display(hmi_display_id)
                for page_link in hmi_display['page_links']:
                    if page_link['roi_uid'] == old_roi_uid and page_link['confidence'] < confidence:
                        self.__remove_attached_page_link(old_roi_uid,hmi_display)
                        return True
                    return False
        return True

                


    def __remove_attached_page_link(self, roi_uid,hmi_display):
        print(roi_uid)


    def __is_rectangle_overlap(self, R1, R2):
        if (int(R1[0])>=int(R2[2])) or (int(R1[2])<=int(R2[0])) or (int(R1[3])<=int(R2[1])) or (int(R1[1])>=int(R2[3])):
            return False
        else:
            return True

    def __setup_roi_in_roi_list(self, roi_list, page_index, linked_graphic):
        """
        Sets up the region of interest (ROI) in the ROI list.

        Args:
            roi_list (list): The list of ROIs.
            page_index (int): The index of the page.
            linked_graphic (dict): The linked graphic containing ROI information.

        Returns:
            None
        """
        while len(roi_list) - 1  < page_index:
            roi_list.append(None)

        if roi_list[page_index] == None:
            roi_list[page_index] = {}

        roi_list[page_index][linked_graphic['roi_uid']]=linked_graphic['roi']

        for roi_id, text_location in linked_graphic['text_location_dict'].items():
            roi_list[page_index][roi_id]=text_location['text_roi']



    def __get_substring_of_text_location(self, text_locations,linked_text_to_search,linked_graphic,character_differences):
        """
        Retrieves a list of substrings from the given text location based on the linked text to search and character differences.

        Parameters:
        - text_location (str): The text location to search for substrings.
        - linked_text_to_search (dict): A dictionary containing linked text names as keys and their corresponding strings as values.
        - character_differences (list): The list to store character differences.

        Returns:
        - substring_list (list): A list of substrings found in the text location.

        """
        substring_list = []
        
        for linked_text_name, linked_texts in self.__linked_text[linked_graphic].items():
            
            if linked_text_name not in linked_text_to_search.keys():
                linked_text_to_search[linked_text_name]=linked_texts['string']
           
            self.__build_substring_list(text_locations, linked_text_to_search, substring_list, linked_text_name, linked_texts, character_differences)
                       
        return substring_list



    def __build_substring_list(self, text_location, linked_text_to_search, substring_list, linked_text_name, linked_texts, character_differences):
        """
        Builds a list of substrings based on the given text location and linked texts.

        Args:
            text_location (dict): The dictionary containing information about the text location.
            linked_text_to_search (dict): The dictionary containing linked text to search.
            substring_list (list): The list to store the generated substrings.
            linked_text_name (str): The name of the linked text.
            linked_texts (dict): The dictionary containing linked texts.
            character_differences (list): The list to store character differences.

        Returns:
            None
        """
        for substring_name, linked_text in linked_texts['links'].items():
            if text_location['roi_name'] == linked_text['document_selected_text_roi_name']:
                string=''


                for char in text_location['text_dict']:
                    string = string + char['c']

                indexes = linked_text['document_selected_text_indexes']

                if indexes[1] == -1:
                    sub_string = string
                else:
                    sub_string = string[indexes[0]:indexes[1]]
                    sub_string = self.__correct_if_ocr_used(sub_string
                                                        ,linked_text_to_search
                                                        ,linked_text_name
                                                        ,linked_text
                                                        ,character_differences=character_differences)
                
                try:
                    linked_text_to_search[linked_text_name] = self.__replacer(linked_text_to_search[linked_text_name]
                                                                                ,sub_string
                                                                                ,list(linked_text['indexes'])
                                                                                ,character_differences=character_differences)

                    data = {
                        'index':linked_text['indexes'][1],
                        'difference':len(sub_string)-(linked_text['indexes'][1] - linked_text['indexes'][0])
                    }
                    character_differences.append(data)
                except Exception as error:
                    continue
                substring_list.append(( text_location['roi_name'] , linked_text_name, substring_name, sub_string[indexes[0]:indexes[1]]))



    def __correct_if_ocr_used(self,string, linked_text_to_search, linked_text_name, linked_text, character_differences):
        """
        Corrects the given string if OCR (Optical Character Recognition) is used.

        Args:
            string (str): The original string to be corrected.
            linked_text_to_search (dict): A dictionary containing linked text to search.
            linked_text_name (str): The name of the linked text.
            linked_text (dict): A dictionary containing linked text information.
            character_differences (list): A list of character differences.

        Returns:
            str: The corrected string.
        """
        if self.__primary_linked_graphic_view.ocr_used():
            indexes = list(linked_text['indexes'])
            for character_difference in character_differences:
                if indexes[1] >= character_difference['index']:
                    indexes[0] = indexes[0] + character_difference['difference']
                    indexes[1] = indexes[1] + character_difference['difference']
            string = self.__correct_document_text(linked_text_to_search[linked_text_name][indexes[0]:indexes[1]]
                                                                    ,string)
                                                        
        return string


    def __replacer(self, s, newstring, indexes, nofail=False, character_differences=None):
        """
        Replaces a substring in a given string with a new string at specified indexes.

        Args:
            s (str): The original string.
            newstring (str): The new string to be inserted.
            indexes (list[int]): A list containing the start and end indexes of the substring to be replaced.
            nofail (bool, optional): If True, no error will be raised if the index is outside the string. Defaults to False.
            character_differences (list[dict], optional): A list of dictionaries containing information about character differences. Defaults to None.

        Returns:
            str: The modified string with the substring replaced.

        Raises:
            ValueError: If the index is outside the given string and nofail is False.

        """
        

        for character_difference in character_differences:
            if indexes[1] >= character_difference['index']:
                indexes[0] = indexes[0] + character_difference['difference']
                indexes[1] = indexes[1] + character_difference['difference']

        # raise an error if index is outside of the string
        if not nofail and indexes[0] not in range(len(s)):
            raise ValueError("index outside given string")

        # if not erroring, but the index is still not in the correct range..
        if indexes[0] < 0:  # add it to the beginning
            return newstring + s
        if indexes[0] > len(s):  # add it to the end
            return s + newstring
        if len(s[:indexes[0]]) + len(newstring) >= len(s):
            return s[:indexes[0]] + newstring

        # insert the new string between "slices" of the original
        return s[:indexes[0]] + newstring + s[indexes[1]:]
                   

         
    def __correct_document_text(self, actual_text:str, document_text:str):
        """
        Corrects the document text based on the actual text. Checks for common OCR errors.

        :param actual_text: The actual text.
        :type actual_text: str
        :param document_text: The text from the document.
        :type document_text: str

        :returns: The corrected document text.
        :rtype: str

        This function corrects the document text based on the actual text. It checks for common OCR errors
        such as replacing letters with numbers and vice versa. The function returns the corrected document text.
        """
        correction = ''

        if len(actual_text) != len(document_text):
            return ''

        document_text = document_text.upper()

        for i in range(len(actual_text)):
            if (actual_text[i].isdigit() and document_text[i].isalpha() 
                and document_text[i] in self.letter_to_number_correction):
                char = self.letter_to_number_correction[document_text[i]]

                correction = correction + char

            elif (actual_text[i].isalpha() and document_text[i].isdigit()
                and document_text[i] in self.number_to_letter_correction):
                char = self.number_to_letter_correction[document_text[i]]

                correction = correction + char

            else:
                correction = correction + document_text[i]
        return correction


    letter_to_number_correction = {
        'I':'1',
        'Z':'2',
        'S':'5',
        'G':'6',
        'O':'0',
        'o':'0'
    }

    number_to_letter_correction = {
        '1':'I',
        '2':'Z',
        '5':'S',
        '6':'G',
        '0':'O'
    }


    def setup_data_handler(self, data_handler: ACM_Data_Handler):
        """
        Sets up the Application Code Manager data handler for the logic control module.

        :param data_handler: The data handler object.
        :type data_handler: ACM_Data_Handler

        :returns: None
        :rtype: None

        This function sets the data handler for the control module.
        """
        self.__acm_data_handler = data_handler


    def setup_project(self,project_name, database, config:Config):
        """
        Sets up the project with the given project name, database, and configuration.

        :param project_name: The name of the project.
        :type project_name: str
        :param database: The database object.
        :type database: Database
        :param config: The configuration object.
        :type config: Config

        :returns: None
        :rtype: None

        This function sets the project name, database, and configuration for the control module.
        It also sets the project name for the primary and secondary linked graphics.
        It then calls the get_data_from_database method to retrieve data from the database.
        """
        self.__project_name = project_name
        self.__db = database
        self.__config = config
        self.__primary_linked_graphic_view.set_project_name(self.__project_name)
        self.__primary_linked_graphic_view.set_config(self.__config)
        self.__secondary_linked_graphic_view.set_project_name(self.__project_name)
        self.__secondary_linked_graphic_view.set_config(self.__config)
        self.__connector_graphics.set_project_name(self.__project_name)
        self.__ignored_graphics.set_project_name(self.__project_name)
        self.__get_data_from_database()

    def go_to(self,_=None):
        """
        Go to the object location based on the primary linked graphic.

        :returns: None
        :rtype: None

        This function is called when the user clicks on the linked graphic to go to the specified location.
        """
        primary_linked_graphic_location = self.__primary_linked_graphic_view.get_document_location()
        if (primary_linked_graphic_location['roi_uid'] == None
                or primary_linked_graphic_location['pno'] == None
                or primary_linked_graphic_location['path'] == None): 
                raise ValueError('Linked graphics are not defined.')
        
        self.__go_to_roi_uid = primary_linked_graphic_location['roi_uid']
        self.__go_to_pno = primary_linked_graphic_location['pno']

        self.__go_to_document_callback(primary_linked_graphic_location['path'])
        self.__move_to_roi()

    def __move_to_roi(self):    
        """
        Moves to the region of interest (ROI) on the document viewer panel based on the given parameters.
        
        :return: None
        :rtype: None

        This method checks if the move_to_roi_func, go_to_roi_uid, and go_to_pno are not None.
        If all conditions are met, it calls the move_to_roi_func with the go_to_roi_uid and go_to_pno as arguments.
        After the function call, it sets go_to_roi_uid and go_to_pno to None.
        """
        if self.__move_to_roi_func and self.__go_to_roi_uid and self.__go_to_pno is not None:
            self.__move_to_roi_func(self.__go_to_roi_uid,self.__go_to_pno)
            self.__go_to_roi_uid = None 
            self.__go_to_pno = None 

    def __go_to_roi_for_linked_text(self,name,tag_id):
        """
        Go to the region of interest (ROI) for the linked text.

        :param name: The name of the linked text entry.
        :type name: str
        :param indexes_id: The indexes of the linked text entry.
        :type indexes_id: str

        :returns: None
        :rtype: None

        This function goes to the region of interest (ROI) for the linked text. It retrieves the path, ROI name, and page number
        of the linked text entry based on the given name and indexes. The function then calls the go_to_document_callback method
        with the path as an argument. It moves to the region of interest using the move_to_roi method.
        """
        if tag_id[2] == linked_text_entry.TOP_SIDE:
            linked_graphic_name = self.PRIMARY_GRAPHIC
        else:
            linked_graphic_name = self.SECONDARY_GRAPHIC

        indexes = (tag_id[0],tag_id[1])
        path = self.__linked_text[linked_graphic_name][name]['links'][indexes]['document_selected_text_path']
        self.__go_to_roi_uid = self.__linked_text[linked_graphic_name][name]['links'][indexes]['document_selected_text_roi_name']
        self.__go_to_pno = self.__linked_text[linked_graphic_name][name]['links'][indexes]['document_selected_text_pno']
        
        self.__go_to_document_callback(path)
        self.__move_to_roi()


    def __get_data_from_database(self):
        """
        Retrieves data from the database and updates the hmi displays's attributes accordingly.

        :return: None
        :rtype: None

        This method retrieves the hmi display data from the database and updates UI associated with the hmi display.
        """
        self.__busy_loading_data = True

        if self.__db:
            data = self.__db.get_hmi_display(self.id)

            

            if data:
                self.__primary_linked_graphic_view.set_link_graphic_data(data['primary_linked_graphic'])
                self.__secondary_linked_graphic_view.set_link_graphic_data(data['secondary_linked_graphic'])
                if 'linked_text' in data.keys():
                    self.__linked_text = data['linked_text']
                if 'page_links' in data.keys():
                    self.__page_links = data['page_links']
                if 'unlinked_page_links' in data.keys():
                    self.__unlinked_page_links = data['unlinked_page_links']
                if 'flow_direction' in data.keys():
                    self.__flow_direction = data['flow_direction']
                if 'template_flip' in data.keys():
                    self.__secondary_linked_graphic_flip = [Template_Flip(item) for item in data['template_flip']]
                    self.__secondary_linked_graphic_view.set_template_flip(self.__secondary_linked_graphic_flip)
                self.__setup_text_roi_doc_viewer()

        self.__busy_loading_data = False



    def create_linked_graphics_screen(self, canvas: tk.Canvas ):
        """
        Creates the linked graphics screen on the config canvas that is responsible for presenting the linked graphics views.

        :param canvas: The canvas to draw the linked graphics screen on.
        :type canvas: tk.Canvas

        :return: None
        :rtype: None

        This method is responsible for creating the linked graphics screen on the config canvas. It creates the 
        screen label, name label, primary linked graphic view, divider lines, flow direction label, flow direction 
        description, flow direction buttons, scan rotation label, scan rotation description, connector graphics view, 
        ignored graphics view, and the divider lines. It also sets up the image text locations list view for the 
        primary and secondary linked graphics views, and sets the flow direction buttons to the current flow direction.
        """
        self.start_scan = tk.PhotoImage(data=start_scan)
        self.test_on_page = tk.PhotoImage(data=test_on_page)

        self.canvas = canvas
        self.screen_label = custom_label(self.canvas, 8, 0, text="Linked Graphics", fill= '#505050',size=16,weight="bold")
        self.name_label = custom_label(self.canvas, 8, 24, text=self.name, fill= '#505050',size=12,weight="bold")
        self.__primary_linked_graphic_view.setup_view( self.canvas,0,48, 
                                                description='Used for the display name and description.' 
                                            )
        self.__divider_line_A = cell_line(self.canvas, 24, 16, 506, fill= '#E5E5E5', width=1)
        self.__secondary_linked_graphic_view.setup_view( self.canvas,0,524,  
                                                description='Used for page links.' 
                                            )
        set_active_canvas_screen(self.canvas, self)
        self.canvas.bind('<Configure>',  self.__redraw_config_canvas)  # canvas is resized
        self.__redraw_config_canvas()
        self.__primary_linked_graphic_view.setup_image_text_locations_list_view()
        self.__secondary_linked_graphic_view.setup_image_text_locations_list_view()
        

    def __set_flip_buttons(self):
        """
        Sets the flip buttons based on the secondary linked graphic flip.

        :return: None
        :rtype: None

        This method sets the flip buttons based on the secondary linked graphic flip. If the secondary linked graphic flip contains
        Template_Flip.HORIZONTALLY, the horizontally flip button is set. Otherwise, the horizontally flip button is reset.
        """
        if Template_Flip.HORIZONTALLY in self.__secondary_linked_graphic_flip:
            self.__horizontally_flip_button.set()
        else:
            self.__horizontally_flip_button.reset()
        
    def __secondary_linked_graphic_flip_scan(self,_, is_on):
        """
        Flips the secondary linked graphic scan horizontally and saves the flip to the database.

        :param _: Placeholder parameter. Ignored.
        :type _: optional
        :param is_on: Indicates if the horizontally flip button is on.
        :type is_on: bool

        :return: None
        :rtype: None

        This method flips the secondary linked graphic scan horizontally based on the given is_on parameter. If the horizontally flip
        button is on, the horizontally flip is added to the secondary linked graphic flip. Otherwise, the horizontally flip is removed
        from the secondary linked graphic flip. The secondary linked graphic view is then updated with the new flip. Finally, the flip
        is saved to the database.
        """
        if not is_on:
            if Template_Flip.HORIZONTALLY in self.__secondary_linked_graphic_flip:
                self.__secondary_linked_graphic_flip.remove(Template_Flip.HORIZONTALLY)
        else:
            if Template_Flip.HORIZONTALLY not in self.__secondary_linked_graphic_flip:
                self.__secondary_linked_graphic_flip.append(Template_Flip.HORIZONTALLY)
        self.__secondary_linked_graphic_view.set_template_flip(self.__secondary_linked_graphic_flip)
        self.__save_to_database()

        
    def __select_flow_direction(self, selection):
        """
        Sets the flow direction to the given selection and saves it to the database.

        :param selection: The selection representing the flow direction.
        :type selection: list

        :return: None
        :rtype: None
        """
        self.__flow_direction = selection
        self.__save_to_database()


    def __redraw_config_canvas(self,_=None):
        """
        Redraws the configuration canvas.

        :param _ : Placeholder parameter. Ignored.
        :type _: optional

        :return: None
        :rtype: None

        This method is responsible for redrawing the configuration canvas. It deletes any existing static elements and then redraws the screen label, name label, primary linked graphic view, divider lines, flow direction label, flow direction description, flow direction buttons, scan rotation label, and scan rotation description. It also resizes the scroll region of the canvas.
        """
        self.__delete_static_elements()
        self.screen_label.draw(0,0)
        self.name_label.draw(0,0)
        primary_height = self.__primary_linked_graphic_view.draw(0,0)
        self.__divider_line_A.draw(primary_height)
        self.__secondary_linked_graphic_view.draw(0,primary_height)
        self.__resize_scroll_region()


    def __delete_static_elements(self):
        """
        Deletes the static elements on the configuration canvas.

        :return: None
        :rtype: None
        """
        if self.__flow_direction_description:
            self.canvas.delete(self.__flow_direction_description)
            self.canvas.delete(self.__scan_horizontal_flip_description)


    def __resize_scroll_region(self):
        """
        Resizes the scroll region of the canvas based on the bounding box of all items on the canvas.

        :return: None
        :rtype: None

        If the canvas exists and there are items on the canvas, the scroll region is resized to include all items plus an additional 100 units in the y-direction.
        """
        if self.canvas and self.canvas.bbox(tk.ALL):  
            self.canvas.config(scrollregion=(0,0,self.canvas.bbox(tk.ALL)[2],self.canvas.bbox(tk.ALL)[3]+100))


    def document_selection_subscription(self, subscription):
        """
        Subscribe to the selection event and register the callback functions to document viewer events.

        :param subscription: The subscription object for the selection event.
        :type subscription: Subscription

        :return: None
        :rtype: None

        This method is used to subscribe to the selection event and register the callback functions. The subscription object is passed as a parameter, which represents the subscription to the selection event. The callback functions are used to handle different events related to the selection, such as document selection, page number selection, selected text, full page image, and text mark.

        Example:
            >>> document_selection_subscription(subscription)
        """
        subscription(self.__document_selection_subscription_callback, 
                        self.__document_or_page_number_callback,
                        self.__selected_text_callback,
                        self.__full_page_image)
        
    def __document_selection_subscription_callback(self, selected , **kwargs): 
        """
        Callback function for document selection subscription from document viewer panel.

        :param selected: Indicates if a document is selected or not.
        :type selected: bool
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict

        :return: None
        :rtype: None

        This function is called when a document is selected or deselected. It handles the logic for moving the document viewer to the requested location, clearing text regions of interest (ROI) in the document, getting the selected ROI, and refreshing the ROIs. It also calls the document_selection_subscription function for the primary linked graphic view, secondary linked graphic view, object parameter screen, and subobject parameter screen.

        Example:
            >>> __document_selection_subscription_callback(True, move_to_roi_func=move_func, clear_shown_text_roi_list=clear_func, roi_select_func=roi_func, refresh_roi=refresh_func)
        """
        if kwargs:  
            # Get the function callback from the document viewer panel 
            # responsible for moving the document viewer to the requested location
            self.__move_to_roi_func = kwargs.get('move_to_roi_func',None)
            if self.__build_display:
                self.__build_display.set_move_to_document_roi_func(self.__move_to_roi_func)

            # Get the function callback from the document viewer panel 
            # responsible for clearing text roi in the document
            self.__clear_shown_text_roi_list_func = kwargs.get('clear_shown_text_roi_list',None)

            # Get the function callback from the document viewer panel 
            # responsible for geting the selected region of interest
            self.__get_selected_roi_func = kwargs.get('roi_select_func',None)

            # Send document selected for text regions back to the docuemnt viewr to allow copying text
            self.__send_document_selected_text_func = kwargs.get('send_document_selected_text_func',None)


            self.__refresh_rois_func = kwargs.get('refresh_roi',None)
            self.__primary_linked_graphic_view.setup_text_roi_callback_func(self.__setup_text_roi_doc_viewer)
            self.__secondary_linked_graphic_view.setup_text_roi_callback_func(self.__setup_text_roi_doc_viewer)


            self.__draw_connecting_lines_func = kwargs.get('draw_connecting_lines',None)

        self.__primary_linked_graphic_view.document_selection_subscription(selected, **kwargs)
        self.__secondary_linked_graphic_view.document_selection_subscription(selected, **kwargs)
        self.__connector_graphics.document_selection_subscription(selected, **kwargs)
        self.__ignored_graphics.document_selection_subscription(selected, **kwargs)

        if selected:
            self.__get_selected_roi()

    def __get_selected_roi(self):
        if not self.__get_selected_roi_func:
            if self.__send_document_selected_text_func: 
                self.__send_document_selected_text_func()
            return 
        
        roi_uid, _, pno, path, _, _, _ = self.__get_selected_roi_func()

        if (self.__primary_linked_graphic_data is not None and 
            'text_location_dict' in self.__primary_linked_graphic_data):

            primary_text_dict = self.__primary_linked_graphic_data['text_location_dict']
        
            if (roi_uid in primary_text_dict and primary_text_dict[roi_uid]['pno']==pno and
            primary_text_dict[roi_uid]['path']==path):

                self.__document_selected_text_roi_name = roi_uid
                self.__document_selected_text_linked_graphic_name = self.PRIMARY_GRAPHIC
                self.__document_selected_text_indexes = [0,-1]
                
                text = ''
                for char in primary_text_dict[roi_uid]['text_dict']:
                    text = text + char['c'] 
                self.__document_selected_text = text

                if self.__send_document_selected_text_func: 
                    self.__send_document_selected_text_func(self.__document_selected_text)

                return
        

        if (self.__secondary_linked_graphic_data is not None and 
            'text_location_dict' in self.__secondary_linked_graphic_data):       

            secondary_text_dict = self.__secondary_linked_graphic_data['text_location_dict']    
            
            if (roi_uid in secondary_text_dict and secondary_text_dict[roi_uid]['pno']==pno and
                secondary_text_dict[roi_uid]['path']==path):

                self.__document_selected_text_roi_name = roi_uid
                self.__document_selected_text_linked_graphic_name = self.SECONDARY_GRAPHIC
                self.__document_selected_text_indexes = [0,-1]

                text = ''
                for char in secondary_text_dict[roi_uid]['text_dict']:
                    text = text + char['c'] 
                self.__document_selected_text = text

                if self.__send_document_selected_text_func: 
                    self.__send_document_selected_text_func(self.__document_selected_text)


    def __setup_text_roi_doc_viewer(self):
        self.__primary_linked_graphic_view.set_document_viewer_text_locations()
        self.__secondary_linked_graphic_view.set_document_viewer_text_locations()


    def clear_text_in_document_viewer_panel(self):
        if self.__clear_shown_text_roi_list_func:
            self.__clear_shown_text_roi_list_func()

    def __document_or_page_number_callback(self,path,pno):
        """
        Callback function sent by document viewer panel that sets the document viewer path and page number for the primary and secondary linked graphic views.

        :param path: The path of the document viewer.
        :type path: str
        :param pno: The page number of the document viewer.
        :type pno: int

        :return: None
        :rtype: None

        This function sets the document viewer path and page number for both the primary and secondary linked graphic views.
        """
        self.__primary_linked_graphic_view.set_document_viewer_path_and_page(path,pno)
        self.__secondary_linked_graphic_view.set_document_viewer_path_and_page(path,pno)

    def __full_page_image(self,path,pno,image, pdf_zoom,svg_page):
        """
        Callback function that sets the full page image for the primary, secondary and other linked graphic views sent by document viewer panel.

        :param path: The path of the image.
        :type path: str
        :param pno: The page number.
        :type pno: int
        :param image: The image to be set.
        :type image: Image object
        :param pdf_zoom: The zoom level for the PDF.
        :type pdf_zoom: float
        :param svg_page: The SVG page.
        :type svg_page: SVG object

        :return: None
        :rtype: None

        Sets the full page image for the primary, secondary and other linked graphic views using the provided image, PDF zoom level, and SVG page.

        Example:
            >>> __full_page_image('/path/to/image', 1, image_obj, 1.5, svg_obj)
        """
        self.__primary_linked_graphic_view.set_full_page_image(image, pdf_zoom)
        self.__secondary_linked_graphic_view.set_full_page_image(image, pdf_zoom)
        self.__connector_graphics.set_full_page_image(image, pdf_zoom)
        self.__ignored_graphics.set_full_page_image(image, pdf_zoom)
    

    def __selected_text_callback(self, selected_text,path,pno,_):
        """
        Callback function for handling selected text.

        :param selected_text: The selected text.
        :type selected_text: str
        :param path: The file path.
        :type path: str
        :param pno: The page number.
        :type pno: int
        :param type: The type of the selected text (Database.DRAWING, Database.TEXT, Database.TABLE).
        :type type: int

        :return: None
        :rtype: None

        This function handles the selected text based on its type.
        If the type is Database.DRAWING, it calls __drawing_text_selection.
        If the type is Database.TEXT, it calls __text_document_text_selection.
        If the type is Database.TABLE, it calls __table_text_selection.
        """
        self.__document_selected_text = ''
        self.__document_selected_text_path = path
        self.__document_selected_text_pno = pno

        if not selected_text:
            if self.__send_document_selected_text_func:
                self.__send_document_selected_text_func()
            return

        self.__document_selected_text_linked_graphic_name = selected_text[0][4]
        self.__document_selected_text_roi_name = selected_text[0][0][:-9]

        self.__document_selected_text_indexes = [10000,-1]

        for text in selected_text:
            if self.__document_selected_text_indexes[0] > int(text[3]): 
                self.__document_selected_text_indexes[0] = int(text[3])

            if self.__document_selected_text_indexes[1] < (int(text[3]) + 1): 
                self.__document_selected_text_indexes[1] = int(text[3]) + 1

            self.__document_selected_text = self.__document_selected_text + text[2]

        if self.__send_document_selected_text_func:
            self.__send_document_selected_text_func(self.__document_selected_text)



    def draw_linked_text(self):
        """
        Draws linked text on the screen.

        :return: None
        :rtype: None

        This method iterates over the linked text dictionary and draws each linked text on the screen.
        It retrieves the start and end indexes of each linked text and calls the `primary_link_text` 
        and `secondary_link_text` method of the `name_entry` object to draw the linked text as 
        retangles above the linked text entry.
        """
        for linked_graphic_name, linked_texts in self.__linked_text.items():
            for _, linked_texts in self.__linked_text[linked_graphic_name].items():
                for _, linked_text in linked_texts['links'].items():


                    if (linked_graphic_name == self.PRIMARY_GRAPHIC):
                        start = linked_text['indexes'][0]
                        end = linked_text['indexes'][1]
                        self.__name_entry.primary_link_text(start,end)
                    elif (linked_graphic_name == self.SECONDARY_GRAPHIC):
                        start = linked_text['indexes'][0]
                        end = linked_text['indexes'][1]
                        self.__name_entry.secondary_link_text(start,end)

                        

    def add_linked_name_text_entry(self, entry: linked_text_entry):
        """ 
        Adds linked text entry to the hmi display. Done to link the object to the User Interface and populate values on the UI.
        
        :param entry: The linked text entry to add.
        :type entry: linked_text_entry
        
        :returns: None
        :rtype: None
        
        This function adds a linked text entry to the hmi display. This function is run to 
        link the object to the User Interface and populate values on the UI. The linked text 
        entry is added to the hmi display using the set_text_link_callback method of 
        the linked text entry. The set_text_link_callback method takes the linked_text_callback 
        function as an argument. The linked text entry is also added to the hmi display using 
        the set_go_to_callback method of the linked text entry. The set_go_to_callback method takes 
        the go_to_roi_for_linked_text function as an argument. The linked text entry is then drawn 
        using the draw_linked_text method of the hmi display.
        """
        self.__name_entry = entry
        self.__name_entry.set_text_link_callback(self.__linked_text_callback)
        self.__name_entry.set_go_to_callback(self.__go_to_roi_for_linked_text)
        self.draw_linked_text()

    

    def __linked_text_callback(self, is_linked, indexes, string, name):
        """
        Links or unlinks text in the document to the hmi display.
        
        :param is_linked: True if the text is to be linked, False if the text is to be unlinked.
        :type is_linked: bool
        :param indexes: The indexes of the selected text in the document.
        :type indexes: tuple(int, int)
        :param string: The selected text in the document.
        :type string: str
        :param name: The name of the linked text entry.
        :type name: str
        
        :returns: None
        :rtype: None
        
        This function links or unlinks text in the document to the hmi display. If the text is to be linked, 
        the function checks if the selected text in the document matches the selected text in the linked text 
        entry. If the text matches, the function checks if the selected characters have already been linked. If 
        the selected characters have not been linked, the function creates a dictionary with the indexes of the 
        selected text, the path to the document, the page number of the document, the region-of-interest (ROI) 
        name, and the ROI indexes. The dictionary is then added to the linked text entry. If the text is to be 
        unlinked, the function removes the dictionary from the linked text entry.
        """
        indexes_id = '{start}-{end}'.format(start=indexes[0],end=indexes[1])

        linked_graphic_name = self.__document_selected_text_linked_graphic_name

        if not is_linked:
            self.__linked_text[linked_graphic_name][name]['links'].pop(indexes_id, None)
            return
        
        if self.__document_selected_text != string[indexes[0]:indexes[1]]:
            raise ValueError('The selected text in "'+name
                                + '" is not the same as the selected text in the document. Please make sure the text matches.')
            
        if self.__is_char_in_any(name,linked_graphic_name,indexes):
            raise ValueError('The selected characters in "'+name
                                + '" have already been linked.')
            
            
        dict = {
            'indexes':indexes,
            'document_selected_text_path':self.__document_selected_text_path,
            'document_selected_text_pno':self.__document_selected_text_pno,
            'document_selected_text_roi_name' :self.__document_selected_text_roi_name,
            'document_selected_text_indexes' :self.__document_selected_text_indexes
        }

        if linked_graphic_name not in self.__linked_text.keys():
            self.__linked_text[linked_graphic_name] = {}
        
        if name not in self.__linked_text[linked_graphic_name].keys():
            self.__linked_text[linked_graphic_name][name] = {
                'string':string,
                'links':{}
                }
        self.__linked_text[linked_graphic_name][name]['links'][indexes_id] = dict

        self.__save_to_database()
        if linked_graphic_name == self.PRIMARY_GRAPHIC:
            side_to_show_link = linked_text_entry.TOP_SIDE
        else:
            side_to_show_link = linked_text_entry.BOTTOM_SIDE

        return side_to_show_link


    def __is_char_in_any(self, name, linked_graphic_name, indexes):

        if linked_graphic_name not in self.__linked_text:
            return False 

        if name not in self.__linked_text[linked_graphic_name]:
            return False 

        
        for _, linked_text in self.__linked_text[linked_graphic_name][name]['links'].items():
            if self.__index_overlap(linked_text['indexes'],indexes):
                return True

        return False


    def __index_overlap(self,index1, index2):
        """Whether index1 is overlapping index2."""
        
        range1 = range(index1[0],index1[1])
        range2 = range(index2[0],index2[1])

        if not range1:
            return True  # empty range is subset of anything
        if not range2:
            return False  # non-empty range can't be subset of empty range
        if len(range1) > 1 and range1.step % range2.step:
            return False  # must have a single value or integer multiple step
        return range1.start in range2 or range1[-1] in range2


    def __go_to_callback(self, roi_uid,pno,path,doc_type=Database.DRAWING):
        self.__go_to_roi_uid = roi_uid
        self.__go_to_pno = pno

        self.__go_to_document_callback(path,doc_type)
        self.__move_to_roi()


    def __linked_graphic_change(self):
        self.__primary_linked_graphic_data = self.__primary_linked_graphic_view.get_linked_graphic_data()
        self.__secondary_linked_graphic_data = self.__secondary_linked_graphic_view.get_linked_graphic_data()
        
        if 'path' not in self.__primary_linked_graphic_data:
            return 
        
        self.__path = self.__primary_linked_graphic_data['path']
        self.__pno = self.__primary_linked_graphic_data['pno']
        self.__save_to_database()
        self.__setup_text_roi_doc_viewer()


    
    def start_document_scan(self):
        """ Start scanning document using defined linked graphics"""

        if self.__scanning_started:
            raise OSError('Please wait. Busy scanning already.')

        if not self.__linked_text:
            raise ValueError('No linked text. Please link text first before scanning.')
        
        # Only the primary linked graphic should raise exceptions
        try:
            self.__primary_linked_graphic_view.start_scan()
            self.__primary_graphic_scan_done = False
        except Exception as error:
            raise ValueError(error)

        self.__scanning_started = True 
        self.__primary_done_saving = False
        self.__secondary_done_saving = False

        # Start scanning for in and out page links
        try:
            self.__secondary_scan_started = self.__secondary_linked_graphic_view.start_scan(self.__secondary_linked_graphic_flip)
            self.__secondary_graphic_scan_done = False
        except Exception as error:
            pass


    def check_scanner_progress(self):
        """
        Check the progress of the scanner.
        
        :return: A tuple containing the following information:
                - total_number_of_tasks (int): The total number of tasks.
                - total_number_done (int): The total number of tasks done.
                - percentage (float): The percentage of tasks completed.
                - done (bool): Indicates if the scanning is done.
                - error (str): Error message, if any.
        :rtype: tuple
        """
        total_number_of_tasks,total_number_done, _ , done_1, error, cancel_scan_1 = self.__primary_linked_graphic_view.check_scanner_progress()
        
        cancel_scan_funcs = [cancel_scan_1]

        if self.__secondary_scan_started:
            number_of_tasks_2,number_done_2, _ , done_2, error_2, cancel_scan_2 = self.__secondary_linked_graphic_view.check_scanner_progress()

            cancel_scan_funcs.append(cancel_scan_2)

            total_number_of_tasks = total_number_of_tasks + number_of_tasks_2
            total_number_done = total_number_done + number_done_2

            done_scanning = done_1 and done_2
            if error :
                error = 'HMI Display named "'+self.name+'" Primary Graphic '+error
            elif error_2 :
                error = 'HMI Display  named "'+self.name+'Secondary Graphic '+error_2
        else:
            done_scanning = done_1
            error = 'HMI Display named "'+self.name+'" Primary Graphic '+error

        if done_scanning and not self.__secondary_scan_started:
            self.__scanning_started = False

        done_saving = self.__primary_done_saving and (self.__secondary_done_saving or not self.__secondary_scan_started)

        if self.__secondary_scan_started:
            count = [self.__primary_scanning_count,self.__secondary_scanning_count]
        else:
            count = [self.__primary_scanning_count]

        if total_number_of_tasks: 
            percentage = total_number_done/total_number_of_tasks
        else:
            percentage = 1.0

        return (total_number_of_tasks, total_number_done, percentage
                ,done_scanning,count,done_saving,['HMI Displays', 'Page Links'], error, cancel_scan_funcs)

     
        
    def create_page_links_list_view(self, canvas):
        self.__page_links_list_view = page_links_list_view(canvas, self.__path, internal_db=self.__db)
        set_active_canvas_screen(canvas, self.__page_links_list_view)
        canvas.bind('<Configure>',  self.__page_links_list_view.redraw)  # canvas is resized
        self.__page_links_list_view.draw()
        self.__page_links_list_view.subscribe_to_goto(self.__go_to_callback)

        for page_link in self.__page_links:
            pno = page_link['pno']
            roi_name = page_link['roi_uid']
            self.__page_links_list_view.add_page_link(pno,roi_name)

        for unlinked_page_link in self.__unlinked_page_links:
            pno = unlinked_page_link['pno']
            roi_name = unlinked_page_link['roi_uid']
            self.__page_links_list_view.add_unlinked_page_link(pno,roi_name,unlinked_page_link['page_name'])



    def build_display(self, canvas, output_path):
        if not self.__acm_data_handler.get_factory_talk_view_se_id():
            
            acm_console = ACM_Console(self.__project_name, self.__acm_data_handler, self.__db, self.__config)
            acm_console.create_hmi_object()
        
        self.build_display_to_acm()

        from bin.gui_build_displays import BuildDisplay
        
        self.__build_display = BuildDisplay(canvas, self.__db, self.__acm_data_handler, self.__project_name, self.__config, output_path
                     ,go_to_document_page_func=self.go_to,set_document_to_open_func=self.__go_to_document_callback
                     ,move_to_document_roi_func=self.__move_to_roi_func, single_display_name=self.name)
    
    
    
    def __save_to_database(self):

        # prevents writing to database if busy loading data form database
        if self.__busy_loading_data:
            return 

        if self.__primary_linked_graphic_data is None:
            return 

        if self.__primary_linked_graphic_data['roi_uid'] is None:
            return

        if ('roi_uid' in self.__primary_linked_graphic_data and 
            (self.PRIMARY_GRAPHIC_TYPE not in self.__primary_linked_graphic_data['roi_uid'])):
            roi_list, self.__primary_linked_graphic_data = self.__update_roi_uid(
                                                                self.__primary_linked_graphic_data
                                                                ,self.PRIMARY_GRAPHIC_TYPE)
            self.__primary_linked_graphic_view.set_link_graphic_data(self.__primary_linked_graphic_data)
            self.__save_page_roi(self.__path,roi_list)

        if ('roi_uid' in self.__secondary_linked_graphic_data and 
            (self.SECONDARY_GRAPHIC_TYPE not in self.__secondary_linked_graphic_data['roi_uid'])):
            roi_list, self.__secondary_linked_graphic_data = self.__update_roi_uid(
                                                                self.__secondary_linked_graphic_data
                                                                ,self.SECONDARY_GRAPHIC_TYPE
                                                                ,self.__primary_linked_graphic_data['roi_uid'])
            # Push the renamed uid back into the view; otherwise the linked graphic keeps
            # the pre-rename uid and can no longer find its own roi once the roi list is
            # refreshed (breaks the zoom rescale that carves the text masks).
            self.__secondary_linked_graphic_view.set_link_graphic_data(self.__secondary_linked_graphic_data)
            self.__save_page_roi(self.__path,roi_list)

            self.__secondary_linked_graphic_data['confidence'] = 1.0


        dict_data = {
            'id': self.__primary_linked_graphic_data['roi_uid'],
            'name': self.name,
            'description': self.description,
            'change_user': os.getlogin(),
            'path': self.__path,
            'pno': self.__pno,
            'primary_linked_graphic': self.__primary_linked_graphic_data,
            'secondary_linked_graphic': self.__secondary_linked_graphic_data,
            'linked_text':self.__linked_text,
            'page_links':self.__page_links,
            'unlinked_page_links':self.__unlinked_page_links,
            'flow_direction':self.__flow_direction,
            'template_flip':[item.value for item in self.__secondary_linked_graphic_flip]
            }
            
        

        self.__db.save_hmi_display(dict_data)
        self.__db.save_hmi_display_graphic_template(dict_data)


    def __update_roi_uid(self, linked_graphic_data,object_type,object_id=''):
        """
        Updates the region-of-interest (ROI) UID based on the linked graphic data.

        :param linked_graphic_data: The linked graphic data.
        :type linked_graphic_data: dict
        :param object_type: The type of the object.
        :type object_type: str
        :param object_id: The ID of the object (optional).
        :type object_id: str, optional
        
        :return: The updated region-of-interest (ROI) list and linked graphic data.
        :rtype: tuple
        """
        roi_list = self.__db.get_project_document_roi(self.__path)

        roi = linked_graphic_data['roi']
        pno = linked_graphic_data['pno']

        minX = int(min(l[0] for l in roi))
        minY = int(min(l[1] for l in roi))
        maxX = int(max(l[0] for l in roi))
        maxY = int(max(l[1] for l in roi))

        roi_uid = (str(pno) +'-'+ str(minX) +'-'+ str(minY) 
                    +'-'+ str(maxX) +'-'+ str(maxY) +'-'+object_type)

        if object_id != '':
            roi_uid = roi_uid +'-'+ object_id
        roi_list[pno].pop(linked_graphic_data['roi_uid'], None)

        roi_list[pno][roi_uid]=roi
        linked_graphic_data['roi_uid']=roi_uid

        return roi_list, linked_graphic_data


    __non_connecting_object_names = [
        'hmi_display_page',
        'text'
    ]


    __connecting_object_names = [
        'hmi_page_link'
    ]


    def __is_connecting_object(self, object_name):
        for name in self.__connecting_object_names:
            if name in object_name:
                return True
        return False



    def __is_non_connecting_object(self, object_name):
        for name in self.__non_connecting_object_names:
            if name in object_name and not self.__is_connecting_object(object_name):
                return True
        return False


    def extract_lines(self):
        print('Getting image to search')
        img = np.array(render_page(self.__path, int(self.__pno), zoom=1, annots=False))
        self.__line_page_height = img.shape[0]
        self.__line_page_width = img.shape[1]
        _, image = cv2.threshold(cv2.cvtColor(img.copy(),cv2.COLOR_RGB2GRAY), 250, 255, cv2.THRESH_BINARY)

        page_regions_of_interest = self.__db.get_project_document_roi(self.__path)[self.__pno]
        
        if page_regions_of_interest == None:
            raise ValueError('No regions of interest found on page. Please first define objects.')


        
        self.__already_tested_pairs = {}

        for _, region_of_interest in page_regions_of_interest.items():
            image= cv2.fillPoly(image, np.int32([np.array(region_of_interest)]), (255,255,255))

        
        for first_object_name, first_region_of_interest in page_regions_of_interest.items():
            
            if self.__is_non_connecting_object(first_object_name): 
                continue
            
            first_filled_image = cv2.fillPoly(image.copy(), np.int32([np.array(first_region_of_interest)]), (0,0,0))
            
            
            for second_object_name, second_region_of_interest in page_regions_of_interest.items():
                
                if self.__is_non_connecting_object(second_object_name): 
                    continue
                
                second_filled_image = cv2.fillPoly(first_filled_image.copy(), np.int32([np.array(second_region_of_interest)]), (0,0,0))
                
                if first_object_name == second_object_name:
                    continue

                if (first_object_name in self.__already_tested_pairs 
                    and second_object_name in self.__already_tested_pairs[first_object_name]):
                    continue

                if (second_object_name in self.__already_tested_pairs 
                    and first_object_name in self.__already_tested_pairs[second_object_name]):
                    continue

                if first_object_name not in self.__already_tested_pairs:
                    self.__already_tested_pairs[first_object_name] = []

                self.__already_tested_pairs[first_object_name].append(second_object_name)

                first_polygon = Polygon(first_region_of_interest)
                second_polygon = Polygon(second_region_of_interest)
                
                result = self.__find_connection_between_linked_graphics( [first_polygon.representative_point()], [second_polygon.representative_point()], second_filled_image)
                
                if result.size < 2:
                    continue
                
                pre_straightened_path = self.__remove_points_in_rois(first_region_of_interest, second_region_of_interest, result)

                if pre_straightened_path.shape[0] < 2:
                    continue
                
                #pts = np.flip(path, 1)
                #pts = pts.reshape((-1, 1, 2))
                #maze = cv2.polylines(img.copy(), [pts], 
                #        False, (0,0,255), 5)

                #cv2.imshow('test',cv2.resize(maze,(1300,int(maze.shape[0]*1300/maze.shape[1]))))
                #cv2.waitKey(0)

                xs, ys = self.__straighten_lines(pre_straightened_path)

                path = []
                for i in range(len(xs)):
                    path.append((int(xs[i]),int(ys[i])))

                pts = np.flip(path, 1)
                pts = pts.reshape((-1, 1, 2))
                maze = cv2.polylines(img, [pts], 
                        False, (0,0,255), 5)

                line_string = LineString(path)

                if line_string.distance(Point(pre_straightened_path[0])) > 5:
                    path.insert(0,pre_straightened_path[0])
                    #pass

                if line_string.distance(Point(pre_straightened_path[-1])) > 5:
                    path.append(pre_straightened_path[-1])
                    #pass

                line_string = LineString(path)
                

                #cv2.imshow('test',cv2.resize(maze,(1300,int(maze.shape[0]*1300/maze.shape[1]))))
                #cv2.waitKey(0)

                self.__connecting_lines.append([path,first_object_name,second_object_name,line_string])
        #self.__write_new_display_to_acm('hello_fun')
        if self.__draw_connecting_lines_func:
            for i in range(len(self.__connecting_lines)):
                for j in range(len(self.__connecting_lines)):
                    if self.__connecting_lines[i][3].length>self.__connecting_lines[j][3].length:
                        self.__connecting_lines[j][3] = snap(self.__connecting_lines[j][3],self.__connecting_lines[i][3],5)
                        self.__connecting_lines[j][0] = np.array(self.__connecting_lines[j][3],dtype=int)
            merged_lines = unary_union([i[3] for i in self.__connecting_lines]) 
            #print(merged_lines.coords)
            merged_lines = merged_lines.simplify(5, preserve_topology=False) 
            #print(merged_lines.coords)       
            print(merged_lines.wkt)            
            self.__draw_connecting_lines_func(merged_lines)


    def __cut_line_string(self, line, distance):
        num_vert = int(round(line.length / distance))
        if num_vert == 0:
            num_vert = 1
        return LineString(
            [line.interpolate(float(n) / num_vert, normalized=True)
             for n in range(num_vert + 1)])
      
    # Must match the LibraryIDs of the SPA libraries shipped under acm_libraries\.
    ACM_LIBRARY_IDs = {
        'Process Line':'1E5825D5-62B1-4DF7-BA33-5BA0DDC2DCF3',
        'Image':'F9366DE1-305F-4DCC-BB9E-58C28C019F23',
        'Page Link':'C1A52D94-07A2-4309-80DC-ADB8BB971573'
    }

    def setup_for_build(self, config, db,path,pno, flow_direction ):
        self.__config = config
        self.__db = db
        self.__path = path
        self.__pno = pno
        self.__flow_direction = flow_direction

        
    def build_display_to_acm(self):   

        if not Validators.check_object_name_acm_valid(self.name):
            raise ValueError('"'+self.name+'" not ACM compliant name')

        try:
            self.__check_registered_libraries()
        except Exception as error:
            raise ValueError(error)


        ft_view_se_id = self.__acm_data_handler.get_factory_talk_view_se_id()
        
        if ft_view_se_id == '':
            raise ValueError('No FTViewSE Server created. Please create the sever in ACM.') 

        width, height, _, page_links, control_modules = self.__config.get_hmi_display_settings()
        hmi_display_template = self.__config.get_hmi_display_template()

        self.__acm_data_handler.write_parameter_value(hmi_display_template,ft_view_se_id,'DisplayTemplate')
         
        self.__acm_data_handler.create_new_hmi_display_in_acm(self.name,ft_view_se_id,width,height)
        self.__create_static_graphics_in_acm(ft_view_se_id,width,height)
        if page_links:
            self.__create_page_links_in_acm(ft_view_se_id,width,height)
        if control_modules:
            self.__position_control_modules_in_acm(ft_view_se_id,width,height)
       

    def __check_registered_libraries(self):
        missing_libraries = []
        for key, id in self.ACM_LIBRARY_IDs.items(): 
            if not self.__acm_data_handler.registered_library_exists(id):
                missing_libraries.append(key)
        
        if missing_libraries:
            error = 'The following Solutions Project Accelerator required libraries are missing:\n'
            for library in missing_libraries:
                error = error + library + '\n'
            error = error + 'Please ensure they have been imported into ACM.'
            raise ValueError(error)

    def __create_static_graphics_in_acm(self, ft_view_se_id, width, height):
        static_graphics = self.__db.get_all_static_graphic_on_page(self.__path,self.__pno)

        for static_graphic in static_graphics:
            image_id = static_graphic['id']
            page_width = static_graphic['primary_linked_graphic']['page_width']
            page_height = static_graphic['primary_linked_graphic']['page_height']

            image_width = abs(static_graphic['primary_linked_graphic']['maxX'] - static_graphic['primary_linked_graphic']['minX'])
            image_height = abs(static_graphic['primary_linked_graphic']['maxY'] - static_graphic['primary_linked_graphic']['minY'])

            aspect_ratio = image_width/image_height

            scaling = 1.5

            hmi_image_minX = static_graphic['primary_linked_graphic']['minX'] * width / page_width
            hmi_image_maxX = (static_graphic['primary_linked_graphic']['minX'] + (image_width * scaling)) * width / page_width
            hmi_image_width = abs(hmi_image_maxX - hmi_image_minX)
            hmi_image_maxY = static_graphic['primary_linked_graphic']['minY'] * height / page_height + (hmi_image_width / aspect_ratio)

            rect = (int(hmi_image_minX)
                    ,int(static_graphic['primary_linked_graphic']['minY'] * height / page_height)
                    ,int(hmi_image_maxX)
                    ,int(hmi_image_maxY))

            filename = static_graphic['name']
            

            self.__acm_data_handler.create_new_hmi_image_in_acm(image_id,self.name,ft_view_se_id,filename,rect)


    def __position_control_modules_in_acm(self, ft_view_se_id, width, height):

        control_modules = self.__db.get_all_control_module_on_page(self.__path,self.__pno)

        for control_module in control_modules:

            displays = self.__db.get_all_hmi_displays_on_page(self.__path,control_module['pno'])
            if not displays or not (len(displays)>0) or not( 'name' in displays[0]):
                continue

            objects_df = self.__acm_data_handler.get_all_objects_in_project()
            row = objects_df.loc[objects_df['Name'] == control_module['name']]
            if row.size == 0:
                continue
            control_module_id= str(row.index[0])

            if control_module['secondary_linked_graphic']:
                linked_graphic = control_module['secondary_linked_graphic']
            else:
                linked_graphic = control_module['primary_linked_graphic']

            page_width = linked_graphic['page_width']
            page_height = linked_graphic['page_height']
            

            self.__acm_data_handler.position_control_module_in_acm(
                                                                    displays[0]['name'],
                                                                    ft_view_se_id,
                                                                    control_module_id,
                                                                    (int(linked_graphic['minX'] * width / page_width)
                                                                    ,int(linked_graphic['minY'] * height / page_height))
                                                                    ,self.__get_final_template_rotation(control_module['flow_direction'],linked_graphic['rotation'])
                                                                    )

    def __create_lines_in_acm(self, ft_view_se_id, width, height):
        
        for line,_,__ in self.__connecting_lines:
            for i in range(len(line) - 1):
                rect = (int(line[i][1] * width / self.__line_page_width)
                    ,int(line[i][0] * height / self.__line_page_height)
                    ,int(line[i+1][1] * width / self.__line_page_width)
                    ,int(line[i+1][0] * height / self.__line_page_height))
                self.__acm_data_handler.create_new_hmi_line_in_acm(self.name,ft_view_se_id,rect)


    def __create_page_links_in_acm(self, ft_view_se_id, width, height):

        hmi_displays = self.__db.get_all_hmi_displays()

        for hmi_display in hmi_displays:
            for page_link in hmi_display.get('page_links', []):

                if page_link['pno'] == self.__pno:
                    self.__create_page_link_in_acm(ft_view_se_id, width, height, page_link
                                                   ,hmi_display['name'])

            # Unlinked page links are stored on the display of the page they sit on, and their
            # 'page_name' is drawing text that matched no display, so there is nothing to navigate to.
            for page_link in hmi_display.get('unlinked_page_links', []):

                if page_link['pno'] == self.__pno and page_link['path'] == self.__path:
                    page_name = page_link.get('page_name', '')
                    self.__create_page_link_in_acm(ft_view_se_id, width, height, page_link
                                                   ,''
                                                   ,label=f"{page_name.replace('_',' ')} (?)"
                                                   ,name_token=acm_safe_token(page_name))


    def __create_page_link_in_acm(self, ft_view_se_id, width, height, page_link, navigate_to_display_name
                                  , label=None, name_token=None):
        center_x = int((page_link['minX'] + page_link['maxX'])/2 * width / page_link['page_width'])
        center_y = int((page_link['minY'] + page_link['maxY'])/2 * height / page_link['page_height'])

        self.__acm_data_handler.create_new_hmi_page_link_in_acm(self.name
                                                                ,page_link['roi_uid']
                                                                ,ft_view_se_id
                                                                ,navigate_to_display_name
                                                                ,(center_x,center_y)
                                                                ,self.__get_final_template_flip(self.__flow_direction,page_link['flip'])
                                                                ,label=label
                                                                ,name_token=name_token)


    def __get_final_template_rotation(self, template_rotation, linked_graphic_rotation):
        if template_rotation == 4:
            final_rotation = 0
        else:
            final_rotation = template_rotation

        if linked_graphic_rotation != Template_Rotate.NONE.value:
            final_rotation = final_rotation + 1 + linked_graphic_rotation

        if final_rotation > 3:
                final_rotation = final_rotation - 4
                
        return final_rotation


    def __get_final_template_flip(self, template_orientation, linked_graphic_flip):
        if linked_graphic_flip == Template_Flip.NONE.value and template_orientation == 0:
            final_orientation = 0

        elif linked_graphic_flip == Template_Flip.HORIZONTALLY.value and template_orientation == 0:
            final_orientation = 2

        elif linked_graphic_flip == Template_Flip.NONE.value and template_orientation == 2:
            final_orientation = 2

        elif linked_graphic_flip == Template_Flip.HORIZONTALLY.value and template_orientation == 2:
            final_orientation = 0

        else:
            final_orientation = 0

        return final_orientation


    def __remove_points_in_rois(self, first_region_of_interest, second_region_of_interest, result):
        path = result
        first_polygon = Polygon(first_region_of_interest)
        second_polygon = Polygon(second_region_of_interest)

        if first_polygon.contains(second_polygon) or second_polygon.contains(first_polygon):
            return np.array([])

        t0 = time.time()
        done_with_first = False
        done_with_second = False

        for _ in path:
            if path.shape[0] < 2:
                break

            if done_with_first and done_with_second: 
                break

            points = np.flip(path, 1)


            try:
                line = LineString(points)
            except Exception:
                print('hello')
                    
            if not done_with_first and (first_polygon.intersects(line) or (Point(points[1]).distance(first_polygon)<1)):
                path = np.delete(path,0,axis=0)
            else:
                done_with_first = True

            if not done_with_second and (second_polygon.intersects(line) or (Point(points[-2]).distance(second_polygon)<1)):
                path = np.delete(path,-1,axis=0)
            else:
                done_with_second = True

                    
        dur = time.time() - t0
        print(dur)
        return path

                



    def __mask_to_compile_hmi_display(self, linked_graphic, page_image):

        cv2.fillPoly(page_image, np.int32([np.array(linked_graphic['roi'])]), (255,255,255))

        image = np.stack((page_image, page_image, page_image), axis=2)
        for point in linked_graphic['points_of_interests']:
            
            cv2.circle(image, point, radius=3, color=(0, 0, 255), thickness=-1)

        cv2.imshow('test.png',cv2.resize(image,(1300,int(image.shape[0]*1300/image.shape[1]))))
        cv2.waitKey(0)

        return page_image, [linked_graphic['roi'][0]]

    def __find_connection_between_linked_graphics(self, primary_poi, secondary_poi, image_to_search):
        grid = image_to_search.astype(np.float32)
        grid[grid == 0] = 1
        grid[grid == 255] = np.inf

        maze = np.stack((image_to_search, image_to_search, image_to_search), axis=2)
        

        #cv2.circle(maze,primary_poi[0],3,(255,0,0),2)
        #cv2.circle(maze,secondary_poi[0],3,(0,255,0),2)
        #cv2.imshow('test',cv2.resize(maze,(1300,int(maze.shape[0]*1300/maze.shape[1]))))
        #cv2.waitKey(0)

        for i in range(len(primary_poi)):
            start = np.array(primary_poi[i],dtype=int)
            start = start

            for j in range(len(secondary_poi)):
                end = np.array(secondary_poi[j],dtype=int)

                t0 = time.time()
                
                end = end
                path = pyastar2d.astar_path(grid, [start[1],start[0]], [end[1],end[0]], allow_diagonal=False)
                dur = time.time() - t0
                print(dur)

                if path is None:
                    continue

                if path.shape[0] > 0:
                    path = path
                    #xs, ys = self.__straighten_lines(path)  
                    
                    #cost = np.array([grid[point[0],point[1]] for point in path],dtype=int)
                    maze = np.stack((image_to_search, image_to_search, image_to_search), axis=2)
                    pts = np.flip(path, 1)
                    pts = pts.reshape((-1, 1, 2))
                    maze = cv2.polylines(maze, [pts], 
                            False, (0,0,255), 5)

                    cv2.circle(maze,start,3,(255,0,0),2)
                    cv2.circle(maze,end,3,(0,255,0),2)
                    cv2.imshow('test',cv2.resize(maze,(1300,int(maze.shape[0]*1300/maze.shape[1]))))
                    cv2.waitKey(0)
                    return path
                else:
                    return np.array([]) 

        return np.array([])


    def __straighten_lines(self, path):
        line = LineString(path)  
                                     
        line = line.simplify(20) 
        return self.straighten_line_string(path, line)

    def straighten_line_string(self, path, line):
        xs = [x[0] for x in line.coords ]
        ys = [x[1] for x in line.coords ]

        
        for i in range(1, len(xs)-1):
            if abs(xs[i] - xs[i-1]) < (20):
                xs[i] = xs[i-1]
                            
            if abs(ys[i] - ys[i-1]) < (20):
                ys[i] = ys[i-1]   
                            
        length = len(xs)-1   
        for i in range(1, len(xs)-1):
            if abs(xs[length - i] - xs[length - (i-1)]) < (20):
                xs[length - i] = xs[length - (i-1)]
                            
            if abs(ys[length - i] - ys[length - (i-1)]) < (20):
                ys[length - i] = ys[length - (i-1)]

        if len(xs) == 2:
            float_average = np.mean(path, axis=0)
            int_average = np.rint(float_average).astype(int)
            if abs(xs[0]-xs[1])<20:
                xs[0]=xs[1]= int_average[0]
            if abs(ys[0]-ys[1])<20:
                ys[0]=ys[1]= int_average[1]

        return xs,ys



    def delete_from_database(self):
        """
        Deletes the current object from the database.

        :return: None
        :rtype: None

        This method calls the private method __delete_all_from_database() to delete all related records from the database.
        """

        self.__delete_all_from_database()
    

    def __delete_all_from_database(self):
        """
        Deletes all data for the current hmi display from the database.

        :returns: None
        :rtype: None
        
        This function deletes all data for the hmi display from the database. This 
        includes the hmi display itself and the linked text. Lastly if the hmi display
        was a not template then the regions-of-interests (ROIs) are deleted from the document.
        """
        is_template = self.__delete_hmi_display_from_database()  

        if is_template :
            return 

        roi_to_delete = []
        roi_to_delete = roi_to_delete + self.__primary_linked_graphic_view.get_all_roi_ids()
        roi_to_delete = roi_to_delete + self.__secondary_linked_graphic_view.get_all_roi_ids()
        roi_to_delete = roi_to_delete + self.__get_all_page_link_roi_ids()


        roi_list = self.__db.get_project_document_roi(self.__path)
        for pno, roi in roi_to_delete:
            del(roi_list[pno][roi])

        self.__save_page_roi(self.__path,roi_list)
        if self.__refresh_rois_func:
            self.__refresh_rois_func()

        logging.info('Deleted {} HMI Display with ID: {} with ROIs '.format(self.name, self.id))

    


    def __delete_hmi_display_from_database(self):
        ''' Removes the hmi display from the database and 
            returns if hmi display is a template'''
        logging.info('Deleting '+self.name+' HMI Display with ID: '+self.id)

        #self.__db.delete_control_module_by_id(self.id)
        self.__db.delete_hmi_display(self.id)

        if self.__db.get_hmi_display_graphic_template(self.id):
            self.__db.delete_hmi_display_template(self.id)
            logging.info('Deleted {} HMI Display with ID: {} without ROIs '.format(self.name, self.id))
            return True 

        return False 


    def __get_all_page_link_roi_ids(self):
        ''' Returns all the roi linked to the object '''
        roi_ids = []
        for page_link in self.__page_links:
            if page_link['roi_uid']:
                roi_ids.append((page_link['pno'],page_link['roi_uid']))
            for roi_name,text_location in page_link['text_location_dict'].items():
                roi_ids.append((text_location['pno'],roi_name))

        return roi_ids


