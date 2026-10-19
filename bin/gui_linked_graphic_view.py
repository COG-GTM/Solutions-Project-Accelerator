

from logging import error
from typing import List

from cv2 import randShuffle
from bin.gui_link_view import image_text_locations_list_view, image_view
from bin.gui_elements import custom_label, rounded_image_button
from bin.gui_multi_image_view import multi_image_view
from bin.logic_internal_database import Database
from bin.logic_linked_graphic import Linked_Graphic
from bin.gui_base64_icons import start_scan, test_on_page
import tkinter as tk
from tkinter import messagebox

from bin.logic_linked_graphic_scanner import BOTTOM_TO_TOP, Template_Flip, Template_Rotate


class linked_graphic_view():
    def __init__(self, name, redraw_callback=None, goto_callback=None, change_callback=None,is_primary_linked_graphic=False, result_callback=None,
                    scanning_done_callback=None,object_type='', template_flip:List[Template_Flip]=[Template_Flip.NONE], template_rotate:List[Template_Rotate]=[Template_Rotate.NONE]) -> None:
        self.__name = name
        self.__linked_graphic = Linked_Graphic(self.__name, linked_callback=self.__graphic_linked_callback,
                                                change_callback=change_callback,
                                                goto_callback=goto_callback,
                                                is_primary_linked_graphic=is_primary_linked_graphic,
                                                result_callback=self.__result_callback,
                                                scanning_done_callback=self.__scanning_done_callback,
                                                object_type=object_type,
                                                get_multi_graphic_func=self.__get_multi_graphic_index)
        self.__redraw_callback = redraw_callback
        self.__image_view = None
        self.__multi_image_view = None
        self.__description_label = None
        self.__selection_in_document_selected = False
        self.__goto_callback = goto_callback
        self.__result_callback_func = result_callback
        self.__scanning_done_callback_func= scanning_done_callback
        self.__template_flip = template_flip
        self.__template_rotate = template_rotate
        self.__config = None 

    def set_config(self, config):
        self.__config = config
        self.__linked_graphic.set_config(self.__config)

    def set_template_flip(self, template_flip:List[Template_Flip]):
        self.__template_flip = template_flip

    def set_template_rotate(self, template_rotate:List[Template_Rotate]):
        self.__template_rotate = template_rotate

    def get_name(self):
        return self.__name
    

    def __get_multi_graphic_index(self):
        try:
            return self.__multi_image_view.get_shown_image_index()
        except Exception as e:
            print(f"Error getting multi graphic index: {e}")
            return 0

    def find_similar_from_image(self,matcher,image,template_flip:List[Template_Flip]=[Template_Flip.NONE]
                                ,template_rotate:List[Template_Rotate]=[Template_Rotate.NONE]
                                , page_index=None,document_type=Database.DRAWING):
        
        return self.__linked_graphic.find_similar_from_image(matcher,image,template_flip,template_rotate,page_index,document_type)


    def add_graphic_link(self,roi_uid,pno,new_template_mask,template_flip,template_rotate
                         ,page_index,scale_factor,document_type,add_template_image=False):
        """
        Adds a graphic link to the primary linked graphic view.
        """

        self.__linked_graphic.add_graphic_link(roi_uid,pno,new_template_mask,template_flip,template_rotate
                                                            ,page_index,scale_factor,document_type,add_template_image=add_template_image)
        
    def create_quick_graphic_link(self, linking_callback_func):
        self.__linked_graphic.create_quick_graphic_link(linking_callback_func)

    def new_graphic_search(self,roi_uid,pno,new_template_mask,template_flip,template_rotate
                            ,document_type=Database.DRAWING):
        
        self.__linked_graphic.new_graphic_search(roi_uid,pno,new_template_mask,template_flip,template_rotate
                                                            ,document_type=document_type)

    def search_current_page(self, template_flip=None, template_rotate=None):
        """ Public wrapper around the underlying `search_current_page`. Used by
        the Draw ROI tool's Test button so the page-level test uses the source
        template + text-carved mask (identical behaviour to the Test On Page
        button on the linked-graphic view). """
        if template_flip is None:
            template_flip = self.__template_flip
        if template_rotate is None:
            template_rotate = self.__template_rotate
        self.__linked_graphic.search_current_page(template_flip, template_rotate)

    def search_current_page_with_polygon_template(self, polygon_unscaled, template_mask,
                                                   template_flip=None, template_rotate=None):
        """ Public wrapper for the Draw ROI Test button: runs a page-level test
        with a template cropped from the destination page at `polygon_unscaled`
        so the preview reflects the transformed placement. """
        if template_flip is None:
            template_flip = self.__template_flip
        if template_rotate is None:
            template_rotate = self.__template_rotate
        self.__linked_graphic.search_current_page_with_polygon_template(
            polygon_unscaled, template_mask, template_flip, template_rotate)


    def ocr_used(self):
        return self.__linked_graphic.ocr_used()


    def set_project_name(self, project_name):
        self.__project_name = project_name 
        self.__linked_graphic.set_project_name(project_name)

    def __result_callback(self, result, done):
        if self.__result_callback_func:
            self.__result_callback_func(result, done)


    def __scanning_done_callback(self, results):
        self.__scanning_done_callback_func(self.__name, results)

    def setup_view(self, canvas: tk.Canvas, x , y , description = 'Used for linking texted and positioning if secondary graphic is not defined.'):
        
        self.__canvas = canvas 
        self.__x = x
        self.__y = y
        self.__description = description
        self.__test_on_page = tk.PhotoImage(data=test_on_page)
        self.__label = custom_label(self.__canvas, x + 8, y + 0, text=self.__name, fill= '#505050',size=11,weight="bold")
        self.__image_view = image_view(self.__canvas, x + 24, y + 56)
        self.__multi_image_view = multi_image_view(self.__canvas, x + 24, y + 56)
        self.__linked_graphic.setup_link_view(self.__canvas, x + 8, y + 0)
        self.__image_text_locations_list_view = image_text_locations_list_view(self.__canvas, x + 24, y + 56 + 8,self.__image_text_location_added_callback)
        
        
        self.__linked_graphic.attach_location_text_list_view(self.__image_text_locations_list_view)
        self.buttonA = rounded_image_button(self.__canvas, x + 16, y + 102, 10, 
                                            text="TEST ON PAGE", 
                                            borderwidth=1, 
                                            tags=('button','A'),
                                            icon_image=self.__test_on_page, 
                                            callback=self.__start_page_scan)


    def setup_image_text_locations_list_view(self):
        self.__image_text_locations_list_view.clear_text_locations()
        self.__image_text_locations_list_view.allow_addition()
        text_references, names_to_roi_names = self.__linked_graphic.get_text_references()

        for text_location_name, roi_name in names_to_roi_names.items():
            color = text_references[roi_name]['color']
            if 'vertical_direction' in text_references[roi_name]:
                is_bottom_to_top = text_references[roi_name]['vertical_direction'] == BOTTOM_TO_TOP
                self.__image_text_locations_list_view.add_text_location(text_location_name,
                                                                        color,
                                                                        is_horizontal=False,
                                                                        is_bottom_to_top=is_bottom_to_top)
            else:
                self.__image_text_locations_list_view.add_text_location(text_location_name,color)
            self.__image_text_locations_list_view.link_formed_for_all_text_location()


    def draw(self, _, y):
        self.__delete_static_elements()

        self.__label.draw(0,y)
        self.__linked_graphic.draw_link_view(self.__canvas.winfo_width() - 64,y)
        self.__description_label = self.__canvas.create_text(self.__x + 24,self.__y + y + 22, text=self.__description, anchor=tk.NW, fill="#6F6F6F")
        description_bounds = self.__canvas.bbox(self.__description_label) 
        if (description_bounds[2] - description_bounds[0]) > (self.__canvas.winfo_width() - 48) and self.__canvas.winfo_width() > 0:
            self.__description_label = self.fit_text_in_mutiline(self.__description_label, self.__x + 24, self.__y + y + 22, self.__description)

        
        if isinstance(self.__linked_graphic.get_display_image(),list):
            _, image_view_height = self.__multi_image_view.draw(y=y, width=self.__canvas.winfo_width() - 48, height=300)
            self.__multi_image_view.set_images(self.__linked_graphic.get_display_image())
        else:
            _, image_view_height = self.__image_view.draw(y=y, width=self.__canvas.winfo_width() - 48, height=300)
            self.__image_view.set_image(self.__linked_graphic.get_display_image())
        list_view_height = self.__image_text_locations_list_view.draw(0,y + image_view_height)
        self.buttonA.draw(0, y + image_view_height + list_view_height)
        return list_view_height


    def document_selection_subscription(self, selected , **kwargs):  
        self.__selection_in_document_selected = selected
        self.__check_if_selection_in_document_made()
        self.__linked_graphic.document_type(kwargs.get('document_type',Database.DRAWING))
        self.__linked_graphic.setup_linking_callback_func(kwargs.get('roi_select_func',None))
        self.__linked_graphic.setup_text_roi_callback_func(kwargs.get('text_roi_selected_func',None))
        self.__linked_graphic.setup_get_full_page_image_func(kwargs.get('get_full_page_image',None))
        self.__linked_graphic.setup_get_page_text_callback_func(kwargs.get('get_text_on_page_func',None))


    def setup_text_roi_callback_func(self, func):
        self.__linked_graphic.setup_text_roi_callback_func(func)

    def set_document_viewer_path_and_page(self,path,page):
        self.__linked_graphic.set_document_viewer_path_and_page(path,page)


    def set_document_viewer_text_locations(self):
        self.__linked_graphic.set_document_viewer_text_locations()


    def set_full_page_image(self, image, pdf_zoom):
        self.__linked_graphic.set_full_page_image(image, pdf_zoom)


    def create_copy(self,path,pno, roi_bbox, text_locations, template_to_match_ratio, rotation=None, flip=None):
        return self.__linked_graphic.create_copy(path,pno,roi_bbox,text_locations, template_to_match_ratio, rotation,flip)


    def __check_if_selection_in_document_made(self):
        if self.__selection_in_document_selected:
            self.__enable_linking()
        else:
            self.__disable_linking()


    def get_text_location_dict(self):
        self.__linked_graphic.get_text_location_dict()


    def __enable_linking(self):
        self.__linked_graphic.enable_link_view()


    def __disable_linking(self):
        self.__linked_graphic.disable_link_view()


    def __delete_static_elements(self):
        if self.__description_label:
            self.__canvas.delete(self.__description_label)
            

    def __start_page_scan(self,_):
        self.__canvas.config(cursor="wait")
        try:
            self.__linked_graphic.search_current_page( self.__template_flip, self.__template_rotate)
        except ValueError as error:
            messagebox.showerror('Error starting scan',error)
        self.__canvas.config(cursor="")
        
    def __graphic_linked_callback(self, display_image):
        if isinstance(display_image,list):
            if self.__multi_image_view:
                self.__multi_image_view.set_images(display_image)
        else:
            if self.__image_view:
                self.__image_view.set_image(display_image)

    def __image_text_location_added_callback(self, name, color):
        self.__redraw_callback(None)
       
    def get_document_location(self):
        return self.__linked_graphic.get_document_location()

    def get_linked_graphic_data(self):
        return self.__linked_graphic.get_data() 

    def set_link_graphic_data(self, data):
        self.__linked_graphic.set_data(data)
        #self.__setup_image_text_locations_list_view()

    def get_pdf_zoom_scale(self):
        return self.__linked_graphic.get_pdf_zoom_scale()

    def redetect_text_dicts_at_polygons(self, text_roi_polygons_unscaled, dest_path, dest_pno):
        """ Delegate to `Linked_Graphic.redetect_text_dicts_at_polygons`. Used by the
        Draw ROI commit path so text-region contents come from the destination
        drawing, not the source template. """
        return self.__linked_graphic.redetect_text_dicts_at_polygons(
            text_roi_polygons_unscaled, dest_path, dest_pno
        )

    def create_placement_template_images(self, placement_dict):
        """ Delegate to `Linked_Graphic.create_placement_template_images`. """
        return self.__linked_graphic.create_placement_template_images(placement_dict)


    def fit_text_in_mutiline(self, label, x, y, text):
        description_bounds = self.__canvas.bbox(label) 
        second_line_substring = 0 
        split = text.split(" ")
        while True :
            second_line_substring = second_line_substring + 1
            multiline_description = ' '.join(split[:second_line_substring])
            self.__canvas.delete(label)
            label = self.__canvas.create_text(x,y, text=multiline_description, anchor=tk.NW, fill="#6F6F6F")
            description_bounds = self.__canvas.bbox(label)
            if (description_bounds[2] - description_bounds[0]) > (self.__canvas.winfo_width() - 48):
                break
        second_line_substring = second_line_substring - 1
        self.__canvas.delete(label)
        multiline_description = ' '.join(split[:second_line_substring])+'\n'+' '.join(split[second_line_substring:])
        label = self.__canvas.create_text(x,y, text=multiline_description, anchor=tk.NW, fill="#6F6F6F")
        return label

    
    def start_scan(self,template_flip:List[Template_Flip]=[Template_Flip.NONE],template_rotate:List[Template_Rotate]=[Template_Rotate.NONE],page_index=None):
        try:
            return self.__linked_graphic.start_scan(template_flip,template_rotate,page_index)
        except Exception as error:
            raise ValueError(error)

    def check_scanner_progress(self):
        return  self.__linked_graphic.check_scanner_progress()

    def get_all_roi_ids(self):
        return self.__linked_graphic.get_all_roi_ids()
        


