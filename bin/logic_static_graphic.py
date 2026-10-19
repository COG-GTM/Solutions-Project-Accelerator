


import logging
from bin.gui_hmi_graphic_view import hmi_graphic_view
from bin.gui_linked_text_entry_view import linked_text_entry
from bin.gui_elements import custom_label, set_active_canvas_screen
import tkinter as tk
import os
from bin.logic_extract_hmi_graphic import extract_hmi_graphic
from bin.logic_acm_data_handler import ACM_Data_Handler
from bin.gui_base64_icons import start_scan, test_on_page
from bin.logic_internal_database import Database
from bin.gui_linked_graphic_view import linked_graphic_view


class Static_Graphic():
    """
    The Static_Graphic class is used to create and manage static graphics in the application.
    """

    PRIMARY_GRAPHIC_TYPE = 'static_graphic'

    def __init__(self, id, name, description, group_id, go_to_document_callback, hmi_graphic_changed_callback, update_roi_name_callback=None,
                 auto_save=True ) -> None:
        """
        Initializes the Static_Graphic class.

        :param id: The ID of the static graphic.
        :type id: int
        :param name: The name of the static graphic.
        :type name: str
        :param description: The description of the static graphic.
        :type description: str
        :param group_id: The group ID of the static graphic.
        :type group_id: int
        :param go_to_document_callback: The callback function for going to the document.
        :type go_to_document_callback: function
        :param hmi_graphic_changed_callback: The callback function for when the HMI graphic changes.
        :type hmi_graphic_changed_callback: function

        :return: None
        :rtype: None
        """
        self.__auto_save = auto_save
        self.id = id
        self.name = name
        self.description = description
        self.group_id = group_id # Associated with the CatalogNumber column in the ACM SQL database
        self.__db : Database = None
        self.__display_image = None
        self.__update_roi_name_func = update_roi_name_callback
        self.__primary_linked_graphic_view = linked_graphic_view( 'Primary Graphic',redraw_callback=self.__redraw_config_canvas, 
                                                                    change_callback=self.__linked_graphic_change,
                                                                    goto_callback=self.__go_to_callback,
                                                                    is_primary_linked_graphic=True,
                                                                    scanning_done_callback=self.__scanning_done_callback,
                                                                    object_type= self.PRIMARY_GRAPHIC_TYPE
                                                                    )
        self.__move_to_roi_func = None
        self.__clear_shown_text_roi_list_func = None
        self.__refresh_rois_func = None
        self.__go_to_roi_uid = None 
        self.__go_to_pno = None
        self.__document_selected_text = None
        self.__document_selected_func = None
        self.__go_to_document_callback = go_to_document_callback
        self.__linked_text = {}
        self.__hmi_graphic_view = None
        self.__busy_loading_data = False
        self.__hmi_graphic_changed_callback = hmi_graphic_changed_callback
        self.__primary_linked_graphic_data = None
        self.__path = ''
        self.__pno = -1
        self.__scanning_started = False
        self.__scanning_count = 0
        self.__done_saving = False
        

    
    def hide_hmi_graphic(self):
        if self.__hmi_graphic_view:
            self.__hmi_graphic_view.hide()


    def set_name(self, name):
        """
        Sets the name of the control module.

        Parameters:
            name (str): The new name for the control module.

        Returns:
            None
        """
        self.name = name
        self.save_to_database()
        
    def set_description(self, description):
        """
        Sets the description of the control module.

        Parameters:
            description (str): The new description for the control module.

        Returns:
            None
        """
        self.description = description
        self.save_to_database()

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
    

    def create_quick_graphic_link(self,linking_callback_func):
        """
        Creates a quick graphic link for the static graphic.

        :param linking_callback_func: The callback function to be called when the quick graphic link is created.
        :type linking_callback_func: function

        :return: None
        :rtype: None

        This function creates a quick graphic link for the static graphic by calling the create_quick_graphic_link method of the primary linked graphic view.
        The linking_callback_func is passed as an argument to the create_quick_graphic_link method.
        """
        self.__primary_linked_graphic_view.create_quick_graphic_link(linking_callback_func)
        self.__hmi_graphic_view.quiet_graphic_extraction()
    


    def get_hmi_graphic(self):
        """
        Returns the HMI graphic data.

        :return: The HMI graphic data.
        :rtype: dict

        This function retrieves the HMI graphic data from the HMI graphic view.
        """
        return self.__hmi_graphic_view.get_hmi_graphic()
    


    def get_error_message(self):
        """
        Returns the error message from the HMI graphic view.

        :return: The error message.
        :rtype: str

        This function retrieves the error message from the HMI graphic view.
        """
        return self.__hmi_graphic_view.get_error_message()


        

    def document_selected_func(self, func):
        self.__document_selected_func = func


    def __scanning_done_callback(self,_, results):
        """
        Callback function called when scanning is done for a linked graphic.

        Args:
            linked_graphic_name (str): The name of the linked graphic.
            results (list): The results of the scanning process.

        Returns:
            None
        """
        self.__build_from_primary_linked_graphic(results)


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

        scan_times = []

        self.__scanning_count = 0

        for result_roi_list, page_index, scan_time, template_to_match_ratio in results:

            scan_times.append(scan_time)

            for roi in result_roi_list:

                if roi_list is None:
                    path = roi['path']
                    roi_list = self.__db.get_project_document_roi(path)

                text_locations = roi['text_locations']


                self.__build_new_static_graphic(path, roi_list, page_index, roi, text_locations, template_to_match_ratio)

                self.__scanning_count = self.__scanning_count + 1

        self.__save_page_roi(path,roi_list)


        average_scan_time = sum(scan_times)/len(scan_times)
        logging.info('Average time to scan for Primary Linked Graphic: {}s per page'.format(str(average_scan_time)))
        logging.info('Done building Static Graphic from Primary Linked Graphic')

        if self.__refresh_rois_func:
            self.__refresh_rois_func()

        self.__done_saving = True

        self.__remove_background_task_callback_func(self.name)


    def __build_new_static_graphic(self, path, roi_list, page_index, roi, text_locations, template_to_match_ratio):
        """ Builds a new static graphic from the primary linked graphic.
         
        :param roi_list: The list of region-of-interests (ROIs) in the document.
        :type roi_list: dict
        :param page_index: The index of the page.
        :type page_index: int
        :param roi: The region-of-interest (ROI) data.
        :type roi: dict
        :param text_locations: The text locations.
        :type text_locations: list
        
        :return: None
        :rtype: None
        
        This function builds a new static graphic from the primary linked graphic. It creates a copy of the 
        primary linked graphic and linked text on the specified page. The function then saves the region-of-interests 
        in the document and refreshes the region-of-interests.
        """



        primary_linked_graphic, text_old_to_new_roi_names, overlaps = self.__primary_linked_graphic_view.create_copy(path,page_index,roi['points'],text_locations, template_to_match_ratio)
        
        if overlaps:
            return

        if not self.__primary_linked_graphic_data:
            self.__primary_linked_graphic_data = self.__primary_linked_graphic_view.get_linked_graphic_data()
        parent_id = self.__primary_linked_graphic_data['roi_uid']
        
        dict_data = {
            'id': primary_linked_graphic['roi_uid'],
            'name': self.name,
            'description': self.description,
            'change_user': os.getlogin(),
            'path': path,
            'pno': page_index,
            'primary_linked_graphic': primary_linked_graphic,
            'linked_text':self.__linked_text,
            'hmi_graphic':self.__hmi_graphic_view.get_data(),
            'parent_id':parent_id
            }
            

        self.__db.save_static_graphic(dict_data)

        while len(roi_list) - 1  < page_index:
            roi_list.append(None)

        if roi_list[page_index] == None:
            roi_list[page_index] = {}

        roi_list[page_index][primary_linked_graphic['roi_uid']]=primary_linked_graphic['roi']



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


    def setup_project(self,project_name, database, config):
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
        It also sets the project name for the primary linked graphics.
        It then calls the get_data_from_database method to retrieve data from the database.
        """
        self.__project_name = project_name
        self.__db = database
        self.__config = config
        self.__primary_linked_graphic_view.set_project_name(self.__project_name)
        self.__primary_linked_graphic_view.set_config(self.__config)
        self.__hmi_graphic_view = hmi_graphic_view( self.__project_name, self.__config
                                                    ,self.__hmi_graphic_changed
                                                    ,self.__set_roi_for_extracting_hmi_graphic)
        self.__get_data_from_database()

    def go_to(self):
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

    def __go_to_roi_for_linked_text(self,name,indexes_id):
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
        path = self.__linked_text[name]['links'][indexes_id]['document_selected_text_path']
        self.__go_to_roi_uid = self.__linked_text[name]['links'][indexes_id]['document_selected_text_roi_name']
        self.__go_to_pno = self.__linked_text[name]['links'][indexes_id]['document_selected_text_pno']
        
        self.__go_to_document_callback(path)
        self.__move_to_roi()


    def __get_data_from_database(self):
        """
        Retrieves data from the database and updates the static graphic's attributes accordingly.

        :return: None
        :rtype: None

        This method retrieves the static graphic data from the database and updates UI associated with the static graphic.
        """
        
        self.__busy_loading_data = True

        if self.__db:
            data = self.__db.get_static_graphic_by_id(self.id)
            
            if data:
                self.__primary_linked_graphic_view.set_link_graphic_data(data['primary_linked_graphic'])
                self.__hmi_graphic_view.set_data(data['hmi_graphic'])
                if 'linked_text' in data.keys():
                    self.__linked_text = data['linked_text']

                self.__hmi_graphic_changed_callback()

        self.__busy_loading_data = False


    def create_edit_graphic_screen(self, canvas):
        """
        Creates the edit graphic screen on the canvas.

        :param canvas: The canvas to draw the edit graphic screen on.
        :type canvas: tk.Canvas

        :return: None
        :rtype: None

        Draw the hmi graphic view on the canvas and bind the canvas to the redraw configuration canvas method.
        The HMI graphic view is allows users to choose how which method they want to use to create the HMI graphic.
        """
        self.__hmi_graphic_view.setup_view(canvas)
        set_active_canvas_screen(canvas, self.__hmi_graphic_view)
        canvas.bind('<Configure>',  self.__hmi_graphic_view.draw)  # canvas is resized
        self.__hmi_graphic_view.draw()


    def __hmi_graphic_changed(self):
        """
        Callback function for when the HMI graphic changes.

        :return: None
        :rtype: None

        This function is called when the HMI graphic changes. It saves the HMI graphic to 
        the database and calls the HMI graphic changed callback function to update the UI.
        """
        self.save_to_database()
        self.__hmi_graphic_changed_callback()


    def export_graphic(self, filename):
        """
        Exports the graphic to a file.
        
        :param filename: The name of the file to export the graphic to.
        :type filename: str

        :return: None
        :rtype: None

        This function exports the graphic to a file by calling the export_graphic method of the HMI_Graphic_View class.
        The export_graphic method takes the filename as an argument.
        """
        self.__hmi_graphic_view.export_graphic(filename)

    def create_linked_graphics_screen(self, canvas: tk.Canvas ):
        """
        Creates the linked graphics screen on the config canvas that is responsible for presenting the linked graphics views.

        :param canvas: The canvas to draw the linked graphics screen on.
        :type canvas: tk.Canvas

        :return: None
        :rtype: None

        This method creates the linked graphics screen by drawing the screen label, name label, 
        primary linked graphic view, divider lines, flow direction label, flow direction 
        description, flow direction buttons, scan rotation label, and scan rotation description. 
        It also sets up the image text locations list view for the primary linked graphic view 
        and binds the canvas to the redraw configuration canvas method.
        """
        self.start_scan = tk.PhotoImage(data=start_scan)
        self.test_on_page = tk.PhotoImage(data=test_on_page)

        self.canvas = canvas
        self.screen_label = custom_label(self.canvas, 8, 0, text="Linked Graphics", fill= '#505050',size=16,weight="bold")
        self.name_label = custom_label(self.canvas, 8, 24, text=self.name, fill= '#505050',size=12,weight="bold")
        self.__primary_linked_graphic_view.setup_view( self.canvas,0,48, 
                                                description='Used for linking texted and positioning if secondary graphic is not defined.' 
                                            )
        
        set_active_canvas_screen(self.canvas, self)
        self.canvas.bind('<Configure>',  self.__redraw_config_canvas)  # canvas is resized
        self.__redraw_config_canvas()
        self.__primary_linked_graphic_view.setup_image_text_locations_list_view()

    def __redraw_config_canvas(self,_=None):
        """
        Redraws the configuration canvas.

        :param _ : Placeholder parameter. Ignored.
        :type _: optional

        :return: None
        :rtype: None

        This method is responsible for redrawing the configuration canvas. It deletes any existing static elements and then redraws the screen label, name label, primary linked graphic view, divider lines, flow direction label, flow direction description, flow direction buttons, scan rotation label, and scan rotation description. It also resizes the scroll region of the canvas.
        """

        self.screen_label.draw(0,0)
        self.name_label.draw(0,0)
        self.__primary_linked_graphic_view.draw(0,0)
        
        self.__resize_scroll_region()

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
            # responsible for moving the docuemnt viewer to the requested location
            self.__move_to_roi_func = kwargs.get('move_to_roi_func',None)

            # Get the function callback from the document viewer panel 
            # responsible for clearing text roi in the docuemnt
            self.__clear_shown_text_roi_list_func = kwargs.get('clear_shown_text_roi_list',None)


            self.__refresh_rois_func = kwargs.get('refresh_roi',None)

        self.__primary_linked_graphic_view.document_selection_subscription(selected, **kwargs)
       

    def clear_text_in_document_viewer_panel(self):
        if self.__clear_shown_text_roi_list_func:
            self.__clear_shown_text_roi_list_func()

    def __document_or_page_number_callback(self,path,pno):
        """
        Callback function sent by document viewer panel that sets the document viewer path and page number for the primary linked graphic views.

        :param path: The path of the document viewer.
        :type path: str
        :param pno: The page number of the document viewer.
        :type pno: int

        :return: None
        :rtype: None

        This function sets the document viewer path and page number for both the primary linked graphic views.
        """
        self.__primary_linked_graphic_view.set_document_viewer_path_and_page(path,pno)
    

    def __full_page_image(self,path,pno,image,pdf_zoom,svg_page):
        """
        Callback function that sets the full page image for the primary linked graphic view sent by document viewer panel.

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

        Sets the full page image for the primary linked graphic view using the provided image, PDF zoom level, and SVG page.

        Example:
            >>> __full_page_image('/path/to/image', 1, image_obj, 1.5, svg_obj)
        """
        self.__current_full_page = image
        self.__current_full_svg_page = svg_page
        self.__primary_linked_graphic_view.set_full_page_image(image,pdf_zoom)
    

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
            return

        self.__document_selected_text_roi_name = selected_text[0][0][:-9]

        self.__document_selected_text_indexes = [10000,-1]

        for text in selected_text:
            if self.__document_selected_text_indexes[0] > int(text[3]): 
                self.__document_selected_text_indexes[0] = int(text[3])

            if self.__document_selected_text_indexes[1] < (int(text[3]) + 1): 
                self.__document_selected_text_indexes[1] = int(text[3]) + 1

            self.__document_selected_text = self.__document_selected_text + text[2]


    def draw_linked_text(self):
        """
        Draws linked text on the screen.

        :return: None
        :rtype: None

        This method iterates over the linked text dictionary and draws each linked text on the screen.
        It retrieves the start and end indexes of each linked text and calls the `primary_link_text` method
        of the `name_entry` object to draw the linked text as retangles above the linked text entry.
        """
        for _, linked_texts in self.__linked_text.items():
            for _, linked_text in linked_texts['links'].items():
                    start = linked_text['indexes'][0]
                    end = linked_text['indexes'][1]
                    self.__name_entry.primary_link_text(start,end)


    def add_linked_name_text_entry(self, entry: linked_text_entry):
        """ 
        Adds linked text entry to the static graphic. Done to link the object to the User Interface and populate values on the UI.
        
        :param entry: The linked text entry to add.
        :type entry: linked_text_entry
        
        :returns: None
        :rtype: None
        
        This function adds a linked text entry to the static graphic. This function is run to 
        link the object to the User Interface and populate values on the UI. The linked text 
        entry is added to the static graphic using the set_text_link_callback method of 
        the linked text entry. The set_text_link_callback method takes the linked_text_callback 
        function as an argument. The linked text entry is also added to the static graphic using 
        the set_go_to_callback method of the linked text entry. The set_go_to_callback method takes 
        the go_to_roi_for_linked_text function as an argument. The linked text entry is then drawn 
        using the draw_linked_text method of the static graphic.
        """
        self.__name_entry = entry
        self.__name_entry.set_text_link_callback(self.__linked_text_callback)
        self.__name_entry.set_go_to_callback(self.__go_to_roi_for_linked_text)
        self.draw_linked_text()


    def __linked_text_callback(self, is_linked, indexes, string, name):
        """
        Links or unlinks text in the document to the static graphic.
        
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
        
        This function links or unlinks text in the document to the static graphic. If the text is to be linked, 
        the function checks if the selected text in the document matches the selected text in the linked text 
        entry. If the text matches, the function checks if the selected characters have already been linked. If 
        the selected characters have not been linked, the function creates a dictionary with the indexes of the 
        selected text, the path to the document, the page number of the document, the region-of-interest (ROI) 
        name, and the ROI indexes. The dictionary is then added to the linked text entry. If the text is to be 
        unlinked, the function removes the dictionary from the linked text entry.
        """
        indexes_id = '{start}-{end}'.format(start=indexes[0],end=indexes[1])

        if not is_linked:
            self.__linked_text[name]['links'].pop(indexes_id, None)
            return
        
        if self.__document_selected_text != string[indexes[0]:indexes[1]]:
            raise ValueError('The selected text in "'+name
                                + '" is not the same as the selected text in the document. Please make sure the text matches.')
            
        if self.__is_char_in_any(name,indexes):
            raise ValueError('The selected characters in "'+name
                                + '" have already been linked.')
            
            
        dict = {
            'indexes':indexes,
            'document_selected_text_path':self.__document_selected_text_path,
            'document_selected_text_pno':self.__document_selected_text_pno,
            'document_selected_text_roi_name' :self.__document_selected_text_roi_name,
            'document_selected_text_indexes' :self.__document_selected_text_indexes
        }
        
        if name not in self.__linked_text.keys():
            self.__linked_text[name] = {
                'string':string,
                'links':{}
                }
        self.__linked_text[name]['links'][indexes_id] = dict

        #self.__save_to_database()
        return linked_text_entry.TOP_SIDE

    def __go_to_callback(self, roi_uid,pno,path,doc_type=Database.DRAWING):
        """
        Moves the document viewer to the specified region-of-interest (ROI).
        
        :param roi_uid: The unique identifier of the region-of-interest (ROI).
        :type roi_uid: str
        :param pno: The page number of the document.
        :type pno: int
        :param path: The path to the document.
        
        This function moves the document viewer to the specified region-of-interest (ROI) by calling the 
        move_to_roi function of the Document_Viewer class. The move_to_roi function takes the ROI unique 
        identifier, page number, and path to the document viewer panel as arguments."""
        self.__go_to_roi_uid = roi_uid
        self.__go_to_pno = pno

        self.__go_to_document_callback(path, doc_type)
        self.__move_to_roi()


    def __linked_graphic_change(self):
        """
        Updates the linked graphic data for the static graphic.

        :returns: None
        :rtype: None

        This function updates the linked graphic data for the static graphic. The linked graphic data is retrieved
        from the primary linked graphic view using the get_linked_graphic_data method. The linked graphic data is then
        saved to the database using the save_static_graphic method of the Database class.
        """
        self.__primary_linked_graphic_data = self.__primary_linked_graphic_view.get_linked_graphic_data()
        
        if 'path' not in self.__primary_linked_graphic_data:
            return 
        
        self.__path = self.__primary_linked_graphic_data['path']
        self.__pno = self.__primary_linked_graphic_data['pno']
        self.__set_roi_for_extracting_hmi_graphic()
        self.save_to_database()


    def start_document_scan(self):
        """ 
        Start scanning document using defined linked graphics.

        :returns: None
        :rtype: None

        This function starts scanning the document using the defined linked graphics. The document 
        is scanned using the start_scan method of the Linked_Graphic_View class. The scanning process 
        is started only if the scanning has not already been started. If the scanning has already been 
        started, an exception is raised.
        """
        # Only the primary linked graphic should raise exceptions
        if self.__scanning_started:
            raise OSError('Please wait. Busy scanning already.')

        try:
            self.__primary_linked_graphic_view.start_scan()
        except Exception as error:
            raise ValueError(error)

        self.__scanning_started = True 
        self.__done_saving = False


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

        number_of_tasks,number_done, percentage , done_scanning, error, cancel_scan = self.__primary_linked_graphic_view.check_scanner_progress()

        if done_scanning:
            self.__scanning_started = False 


        if error:
            error = 'Static Graphic named "'+self.name+'" Primary Graphic '+error

        
        return (number_of_tasks, number_done,percentage
                ,done_scanning,[self.__scanning_count],self.__done_saving,['Static Graphics'], error, [cancel_scan])
         

    
    def __set_roi_for_extracting_hmi_graphic(self):
        """ 
        Sets the roi used to create an HMI graphic using the primary linked graphic.

        :returns: None
        :rtype: None

        This function sets the region-of-interest (ROI) used to create an HMI graphic using the primary linked 
        graphic. The ROI is set using the linked graphic data for the primary linked graphic. The ROI is passed 
        to the extract_hmi_graphic function of the Extract_HMI_Graphic class to create the HMI graphic. The HMI 
        graphic is then set using the set_hmi_graphic method of the HMI_Graphic_View class.
        """
        if self.__primary_linked_graphic_data and self.__primary_linked_graphic_data['roi']:
            self.__hmi_graphic_view.set_roi(self.__primary_linked_graphic_data['roi'],
                                            self.__primary_linked_graphic_data['points_of_interests'],
                                            self.__primary_linked_graphic_data['path'],
                                            self.__primary_linked_graphic_data['pno'],
                                            self.__primary_linked_graphic_data['text_location_dict'])
            
           
    def remove_background_task_callback(self, func):
        self.__remove_background_task_callback_func = func


    
    def save_to_database(self, force_save=False):
        if self.__auto_save or force_save:
            self.__save_to_database()



    def __save_to_database(self):
        """ 
        Saves the static graphic to the database.

        :returns: None
        :rtype: None

        This function saves the static graphic to the database. The static graphic is saved as a dictionary 
        with the following keys: 'id', 'name', 'description', 'change_user', 'path', 'pno', 'primary_linked_graphic', 
        'linked_text', and 'hmi_graphic'. The 'id' key is the unique identifier for the static graphic. The 'name' key 
        is the name of the static graphic. The 'description' key is the description of the static graphic. 
        The 'change_user' key is the user who last changed the static graphic. The 'path' key is the path to 
        the document that the static graphic is linked to. The 'pno' key is the page number of the document that 
        the static graphic is linked to. The 'primary_linked_graphic' key is the linked graphic data for the static 
        graphic. The 'linked_text' key is the linked text for the static graphic. The 'hmi_graphic' key is the 
        human-machine interface (HMI) graphic data for the static graphic. The static graphic is saved to the 
        database using the save_static_graphic method of the Database class.
        """
        if self.__busy_loading_data:
            return 

        if self.__primary_linked_graphic_data is None:
            return 

        if self.__primary_linked_graphic_data['roi_uid'] is None:
            return

        if (self.__primary_linked_graphic_data['roi_uid'] and 
            (self.PRIMARY_GRAPHIC_TYPE not in self.__primary_linked_graphic_data['roi_uid'])):
            roi_list, self.__primary_linked_graphic_data = self.__update_roi_uid(
                                                                self.__primary_linked_graphic_data
                                                                ,self.PRIMARY_GRAPHIC_TYPE)
            self.__primary_linked_graphic_view.set_link_graphic_data(self.__primary_linked_graphic_data)
            self.__update_roi_name_func(primary_roi_name=self.__primary_linked_graphic_data['roi_uid'])
            self.__save_page_roi(self.__path,roi_list)


        dict_data = {
            'id': self.__primary_linked_graphic_data['roi_uid'],
            'name': self.name,
            'description': self.description,
            'change_user': os.getlogin(),
            'path': self.__path,
            'pno': self.__pno,
            'primary_linked_graphic': self.__primary_linked_graphic_data,
            'linked_text':self.__linked_text,
            'hmi_graphic':self.__hmi_graphic_view.get_data()
            }
            
        

        self.__db.save_static_graphic(dict_data)
        self.__db.save_static_graphic_graphic_template(dict_data)


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
        Deletes all data for the current static graphic from the database.

        :returns: None
        :rtype: None
        
        This function deletes all data for the static graphic from the database. This 
        includes the static graphic itself and the linked text. Lastly if the static graphic
        was a not template then the regions-of-interests (ROIs) are deleted from the document.
        """
        
        is_template = self.__delete_static_graphic_from_database()  

        if is_template :
            return 

        roi_to_delete = []
        roi_to_delete = roi_to_delete + self.__primary_linked_graphic_view.get_all_roi_ids()
       

        roi_list = self.__db.get_project_document_roi(self.__path)
        for pno, roi in roi_to_delete:
            del(roi_list[pno][roi])

        self.__save_page_roi(self.__path,roi_list)
        if self.__refresh_rois_func:
            self.__refresh_rois_func()

        logging.info('Deleted {} Static Graphic with ID: {} with ROIs '.format(self.name, self.id))

    


    def __delete_static_graphic_from_database(self):
        """ 
        Removes the static graphic from the database and returns true if static graphic is a template.

        :return: True if static graphic is a template, False otherwise
        :rtype: bool
        """
        logging.info('Deleting '+self.name+' Static Graphic with ID: '+self.id)

        #self.__db.delete_control_module_by_id(self.id)
        self.__db.delete_static_graphic(self.id)

        if self.__db.get_static_graphic_graphic_template(self.id):
            self.__db.delete_static_graphic_template(self.id)
            logging.info('Deleted {} Static Graphic with ID: {} without ROIs '.format(self.name, self.id))
            return True 

        return False 



