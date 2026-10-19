# -*- coding: utf-8 -*-
import math
import os
import re
import sys
import time
from tkinter import messagebox, simpledialog
from typing import Any, Dict, List
import cv2
import numpy as np
from shapely import BufferJoinStyle, Polygon
from bin.gui_elements import loading_animation
from bin.gui_quick_create_static_graphic import QuickCreateStaticGraphic
from bin.gui_tool_tip_canvas import CanvasTooltip
from bin.logic_hmi_display import HMI_Display
from bin.logic_internal_database import Database
from bin.logic_linked_graphic_scanner import Template_Rotate, Template_Flip
import io
import logging
from threading import Thread
from PIL import Image, ImageTk, ImageDraw
from bin.logic_linked_graphic import Linked_Graphic
import tkinter as tk
import uuid
import json

from bin.logic_llm_inference import UnifiedInference
from bin.logic_pdf_render import rotate_pages
from bin.logic_pdf_to_svg import page_to_svg
from bin.logic_profile import profile
from bin.logic_sam2_segmentation import SAM2Image

from .gui_canvas import CanvasImage
from .gui_base64_icons import (rotate_gray, magic_select_done_button, magic_select_cancel_button, magic_select_reset_button,
                               magic_select_down_button, magic_select_left_button, magic_select_up_button, magic_select_right_button,
                               magic_select_flip_horizontal_button, magic_select_flip_vertical_button,
                               magic_select_test_button, magic_select_scan_page, magic_select_scan_all)

class SelectorToolsMenu:
    """ Menu widget for the selector canvas GUI window """
    def __init__(self, master, functions):
        """ Initialize the Menu """
        self.__functs = functions  # obtain link on dictionary of functions
        self.menu = tk.Menu(master, tearoff=0)  # create main menu bar, public for the main GUI
        # Enable / disable these menu labels
        self.__label_view_link = 'View Link'
        self.__label_copy_text = 'Copy Text'
        self.__label_rotate = 'Rotate'
        self.__label_rotate_all = 'Rotate All'
        self.__label_delete = 'Delete'
        self.__label_edit_polygon = 'Edit Polygon'
        self.__label_create_static_graphic = 'Create Static Graphic'
        self.__label_delete_vertex = 'Delete Vertex'
        self.__label_add_vertex = 'Add Vertex'
        self.__label_draw_roi = 'Draw ROI'
        self.__label_flip_horizontal = 'Flip Horizontal'
        self.__label_flip_vertical = 'Flip Vertical'
        self.__is_polygon_menu_added = False

        
        self.__rotate_meun_icon = tk.PhotoImage(data=rotate_gray)
        # Create menu 
        self.menu.add_command(label=self.__label_view_link,
                                command=self.__functs["view_link"],
                                accelerator='Alt+V',
                                state='disabled')
        self.menu.add_command(label=self.__label_copy_text,
                                command=self.__functs["copy_text"],
                                accelerator='Ctrl+C',
                                state='disabled')
        self.menu.add_separator()
        self.menu.add_command(label=self.__label_rotate,
                                image=self.__rotate_meun_icon,
                                compound="left",
                                command=self.__functs["rotate"],
                                state='disabled')
        self.menu.add_command(label=self.__label_rotate_all,
                                image=self.__rotate_meun_icon,
                                compound="left",
                                command=self.__functs["rotate_all"],
                                state='disabled')
        self.menu.add_separator()
        self.menu.add_command(label=self.__label_delete,
                                command=self.__functs["delete"],
                                accelerator='Delete',
                                state='disabled')
        self.menu.add_separator()
        self.menu.add_command(label=self.__label_draw_roi,
                                command=self.__functs["draw_roi"],
                                state='disabled')
        self.menu.add_command(label=self.__label_flip_horizontal,
                                command=self.__functs["flip_horizontal"],
                                state='disabled')
        self.menu.add_command(label=self.__label_flip_vertical,
                                command=self.__functs["flip_vertical"],
                                state='disabled')
        self.menu.add_separator()
        self.menu.add_command(label=self.__label_edit_polygon,
                                command=self.__functs["edit_polygon"],
                                state='disabled')
        self.menu.add_command(label=self.__label_create_static_graphic,
                                command=self.__functs["create_static_graphic"],
                                state='disabled')
        

    def enable_view_link(self, enable=True):
        if enable:
            self.menu.entryconfigure(self.__label_view_link, state='normal') 
        else: 
            self.menu.entryconfigure(self.__label_view_link, state='disabled')

    def enable_copy_text(self, enable=True):
        if enable:
            self.menu.entryconfigure(self.__label_copy_text, state='normal') 
        else: 
            self.menu.entryconfigure(self.__label_copy_text, state='disabled')

    def enable_rotate(self, enable=True):
        if enable:
            self.menu.entryconfigure(self.__label_rotate, state='normal') 
        else: 
            self.menu.entryconfigure(self.__label_rotate, state='disabled')

    def enable_rotate_all(self, enable=True):
        if enable:
            self.menu.entryconfigure(self.__label_rotate_all, state='normal') 
        else: 
            self.menu.entryconfigure(self.__label_rotate_all, state='disabled')

    def enable_delete(self, enable=True):
        if enable:
            self.menu.entryconfigure(self.__label_delete, state='normal') 
        else: 
            self.menu.entryconfigure(self.__label_delete, state='disabled')

    def enable_edit_polygon(self, enable=True):
        if self.__is_polygon_menu_added:
            return
        if enable:
            self.menu.entryconfigure(self.__label_edit_polygon, state='normal') 
        else: 
            self.menu.entryconfigure(self.__label_edit_polygon, state='disabled')

    def enable_create_static_graphic(self, enable=True):
        if self.__is_polygon_menu_added:
            return
        if enable:
            self.menu.entryconfigure(self.__label_create_static_graphic, state='normal') 
        else: 
            self.menu.entryconfigure(self.__label_create_static_graphic, state='disabled')

    def enable_delete_vertex(self, enable=True):
        if not self.__is_polygon_menu_added:
            return
        if enable:
            self.menu.entryconfigure(self.__label_delete_vertex, state='normal') 
        else: 
            self.menu.entryconfigure(self.__label_delete_vertex, state='disabled')

    def enable_add_vertex(self, enable=True):
        if not self.__is_polygon_menu_added:
            return
        
        if enable:
            self.menu.entryconfigure(self.__label_add_vertex, state='normal') 
        else: 
            self.menu.entryconfigure(self.__label_add_vertex, state='disabled')


    def enable_draw_roi(self, enable=True):
        if enable:
            self.menu.entryconfigure(self.__label_draw_roi, state='normal') 
        else: 
            self.menu.entryconfigure(self.__label_draw_roi, state='disabled')

    def enable_flip_horizontal(self, enable=True):
        if enable:
            self.menu.entryconfigure(self.__label_flip_horizontal, state='normal') 
        else: 
            self.menu.entryconfigure(self.__label_flip_horizontal, state='disabled')

    def enable_flip_vertical(self, enable=True):
        if enable:
            self.menu.entryconfigure(self.__label_flip_vertical, state='normal') 
        else: 
            self.menu.entryconfigure(self.__label_flip_vertical, state='disabled')


    def add_polygon_menu(self):
        if self.__is_polygon_menu_added:
            return
        self.menu.delete(self.__label_edit_polygon)
        self.menu.add_command(label=self.__label_delete_vertex,
                                command=self.__functs["delete_vertex"],
                                state='disabled')
        self.menu.add_command(label=self.__label_add_vertex,
                                command=self.__functs["add_vertex"],
                                state='disabled')
        self.__is_polygon_menu_added = True
        
    
    def remove_polygon_menu(self):
        if not self.__is_polygon_menu_added:
            return
        self.menu.delete(self.__label_delete_vertex)
        self.menu.delete(self.__label_add_vertex)
        self.menu.add_command(label=self.__label_edit_polygon,
                                command=self.__functs["edit_polygon"],
                                state='disabled')
        self.__is_polygon_menu_added = False


    def post(self, x, y):
        self.menu.post(x, y)  # show popup menu
    

class SelectorTools(CanvasImage):

    CURSOR_TOOL = 0
    HAND_TOOL = 1
    RECTANGULAR_TOOL = 2
    POLYGON_TOOL = 3
    AUTO_SELECT_TOOL = 4
    DRAW_ROI_TOOL = 5

    """ Class of SelectorTools. Inherit CanvasImage class """
    def __init__(self, placeholder, path, db: Database,  rect_size, roll_size, file_type=Database.DRAWING, page_number_callback=None, zoom_percentage_callback=None):
        """ Initialize the SelectorTools """

        
        self.x = self.y = 0
        self.start_text_select_x = None
        self.start_text_select_y = None
        self.end_text_select_x = None
        self.end_text_select_y = None
        self.__selecting_text = False
        self.__selecting_text_rect = None
        self.__selecting_text_rect_id = None
        self.__finished_selecting_text = True

        self.__go_to_roi = None 
        self.__go_to_pno = None

        self.__db = db # Internal project database
        self.__db.subscribe_to_changes_for_document_viewer(self.internal_database_changed)

        self.file_type = file_type

        self.highlighted_poly = []  # selected polygons top left coords on the canvas
        self.selected_poly = []

        self.__zoom_percentage_callback = zoom_percentage_callback
        CanvasImage.__init__(self, placeholder, path
                             , page_number_callback=page_number_callback
                             , file_type=file_type
                             , zoom_percentage_callback=self.__zoom_percentage_callback_func)  # call __init__ of the CanvasImage class
        self.set_image_changed_callback(self.__image_changed_callback)
        funcs = {
                    'view_link':self.view_link,
                    'copy_text':self.copy_text,
                    'rotate': self.__rotate_pdf,
                    'rotate_all': self.__rotate_all_pdf,
                    'delete':self.delete_selected,
                    'edit_polygon':self.edit_poly_mode,
                    'create_static_graphic':self.create_static_graphic,
                    'delete_vertex':self.delete_vertex,
                    'add_vertex':self.add_vertex_to_line,
                    'draw_roi':self.__activate_draw_roi_tool,
                    'flip_horizontal':self.flip_draw_roi_horizontal,
                    'flip_vertical':self.flip_draw_roi_vertical
                    }
        self.menu = SelectorToolsMenu(self.canvas, funcs)
        self.text_in_page = []
        self.__selector_tool_chosen = self.CURSOR_TOOL
        self.__draw_roi_button_indication_func = None
        self.__draw_roi_availability_func = None
        self._init_draw_roi_state()
        self.__set_chosen_tool()
        
        
        # Create a popup menu for Rectangles
        self.hold_menu1 = False  # popup menu is closed
        self.hold_menu2 = False
        # Rectangle parameters
        self.rect_size = rect_size  # size of the rolling window
        # Polygon parameters
        self.roi = True  # is it a ROI or hole
        self.roll_size = roll_size  # size of the rolling window
        self.width_line = 2  # lines width
        self.color_back_roi = 'red'  # draw roi color
        self.color_back_hole = 'cyan'  # draw hole color
        self.dash = (1, 1)  # dash pattern
        self.color_hole = {'draw'   : 'magenta',  # draw hole color
                           'point'  : '#8B0000',  # point hole color
                           'back'   : self.color_back_hole,  # background hole color
                           'stipple': 'gray50'}   # stipple value for hole
        self.color_roi = {'draw'   : 'red',     # draw roi color
                          'point'  : 'blue',    # point roi color
                          'back'   : self.color_back_roi,  # background roi color
                          'stipple': 'gray12'}  # stipple value for roi
        self.rect = self.canvas.create_rectangle((0, 0, 0, 0), width=0,
                                                 dash=self.dash, outline=self.color_roi['draw'])
        self.tag_roi = 'roi'  # roi tag
        self.tag_rect_const = 'rect'  # constant tag for rectangle
        self.tag_auto_select_polygon = 'auto_select_polygon'
        self.auto_selection_polygon_tag_id = ''
        self.highlighted_rect = []  # selected rectangles
        self.selected_rect = []
        self.last_current_item = None
        
        self.roi_list = self.__db.get_project_document_roi(self.path)  # list of all page roi rectangles and polygons
        
        
        
        self.tag_curr_edge_start = '1st_edge'  # starting edge of the current polygon
        self.tag_curr_edge = 'edge'  # edges of the polygon
        self.tag_curr_edge_id = 'edge_id'  # part of unique ID of the current edge
        
        self.tag_hole = 'hole'  # hole tag
        self.tag_poly_const = 'poly'  # constant tag for polygon
        self.tag_poly_line = 'poly_line'  # edge of the polygon
        self.tag_vertex_circle = 'vertex_circle' # Tag for vertex circles
        self.tag_curr_circle = 'circle'  # sticking circle tag for the current polyline
        self.radius_stick = 10  # distance where line sticks to the polygon's staring point
        self.radius_circle = 3  # radius of the sticking circle
        self.edge = None  # current edge of the new polygon
        self.auto_selection_points = [] # points for auto selection
        self.auto_selection_rectangle_id = None # rectangle for auto selection
        self.auto_selection_press_pos = None # press position for auto selection
        self.auto_selection_polygons = []
        self.auto_selection_polygon_ids = []
        self.auto_selection_overlay_id = None
        self.is_showing_auto_selection_overlay = False
        self.polygon = []  # vertices of the current (drawing, red) polygon

        self.hole_dict = {}  # dictionary of all holes and their coordinates on the canvas image
        self.drawn_connecting_lines = []
        self.imscale = 1.0

        # Editing variables
        self.edit_mode = False # Flag to indicate if edit mode is active
        self.vertex_circles = {} # Dictionary to store vertex circles and their indices, keyed by polygon tag
        self.selected_vertex_index = None # Index of the selected vertex in polygon vertices list
        self.current_polygon_editing_tag = None # Tag of the polygon being edited
        self.previous_dragged_polygon_tag = None # Polygon that is being repositioned
        self.radius_vertex_circle = 5 # Radius for vertex circles

        # Crosshairs
        self.crosshair_vertical = self.canvas.create_line(0, 0, 0, 0, fill='gray', dash=(2, 2), state='hidden') # Vertical crosshair
        self.crosshair_horizontal = self.canvas.create_line(0, 0, 0, 0, fill='gray', dash=(2, 2), state='hidden') # Horizontal crosshair
        self.canvas.bind('<Enter>', self.show_crosshairs)
        self.canvas.bind('<Leave>', self.hide_crosshairs)
        
        self.__tool_canvas_list_to_refresh = [] # List of tool canvases to refresh

        self.__rect = None

        self.start_rect_highlight_x = None
        self.start_rect_highlight_y = None

        self.__selection_callback = None
        self.__tool_panel_document_or_page_number_change_callback = None
        self.__tool_panel_selected_text_callback = None
        self.__full_page_image_callback = None 
        # Subscribers may attach before the first full-page render thread starts
        self.__get_pages_thread_done = False
        self.__get_pages_thread = None
        self.full_page = None
        self.full_svg_page = None
        self.pdf_zoom = 2
        self.__selection_callbacks = []
        self.__refresh_tool_canvas_callback = None
        self.__show_cell_link_callback = None

        self.__selected_objects = []
        self.__previously_selected_poly = None

        self.__selected_text = None

        
        self.__shown_text_roi_rect_lists = {}
        self.__shown_ocr_text_lists = {}
        self.__text_location_dicts = {}
        self.__selected_shown_text_roi_list = []
        self.__previous_selected_text_roi = ''

        self.__text_tooltips_lists = {}
        self.subscribe_to_document_or_page_number_change(self.__document_or_page_number_change)

        # Start thread to load the AI models
        Thread(target=self.__load_ai_models).start()   
        #self.show_busy_canvas()
        self.__project_name = None 
        self.__config = None


    def internal_database_changed(self, path):
        """ Callback function when the internal database has changed """
        if path != self.path:
            return
        self.canvas.after(0, self.__refresh_rois)


    def setup_project(self, project_name, config):
        """ Setup the project data """
        self.__project_name = project_name
        self.__config = config


    def set_llm_inference(self, llm_inference: UnifiedInference):
        """ Set the LLM inference object """
        self.llm_inference = llm_inference
        if not self.llm_inference.check_model() and self.llm_inference.get_provider() == "ollama":
            message = f"The model '{self.llm_inference.model_name}' is not found locally. \
                        Do you want to download it now? (This may take some time and \
                        requires internet connection)"
            if messagebox.askyesno("Download the model", message):
                self.S3FileDownloader()



    def create_static_graphic(self):
        """ Create a static graphic from the selected polygons and rectangles """

        if not self.highlighted_poly and not self.highlighted_rect:
            messagebox.showwarning("No Selection", "Please select at least one polygon or rectangle to create a static graphic.")
            return
        
        
        self.__set_selected_roi()

        QuickCreateStaticGraphic(
            parent=self.canvas,
            project_name=self.__project_name,
            database=self.__db,
            config=self.__config,
            get_selected_roi=self.get_selected_roi
        )
        

    def __activate_draw_roi_tool(self):
        """ Activate the Draw ROI tool from the context menu / tool cell button.
        Auto-detects the source linked-graphic cell from the current selection. """
        self.__selector_tool_chosen = self.DRAW_ROI_TOOL
        self.__set_chosen_tool(False)
        # __set_chosen_tool -> __draw_roi_tool already tries to seed from current selection.
        self._notify_draw_roi_button(self._draw_roi_state != 'idle')


    def show_busy_canvas(self, text="Please Wait"):
        self.__delete_busy_canvas()
        self.loading_animation = loading_animation(self.canvas)
        self.loading_animation_text = None

        def center_loading(_):
            x = int(self.canvas.winfo_width()/2)
            y = int(self.canvas.winfo_height()/2)
            
            self.loading_animation.draw(x ,y)                
            self.loading_animation_text = self.canvas.create_text(x, y + 24
                                            , text=text
                                            , fill="#4F4F4F"
                                            , anchor=tk.CENTER
                                            , justify=tk.CENTER )
            _,y1,_,y2 = self.canvas.bbox(self.loading_animation_text)
            self.canvas.move(self.loading_animation_text,0,int(abs(y1 - y2)/2))

        self.loading_animation_funcid=self.canvas.bind("<Configure>", center_loading, '+')
        self.canvas.update()


    def __delete_busy_canvas(self):
        if not hasattr(self, 'loading_animation'):
            return
        self.loading_animation.stop()
        self.canvas.delete(self.loading_animation_text)
        self.canvas.unbind("<Configure>", self.loading_animation_funcid)


    def __load_ai_models(self):
        if self.file_type == Database.IMAGE:
            self.segmentation_model = SAM2Image()


    def __rotate_pdf(self):
        self.close_pdf_doc()  # the file is about to be rewritten in place
        rotate_pages(self.path, 90, pnos=[self.pno])
        self.reload_pdf_doc()

        self.refresh_pages()

    def __rotate_all_pdf(self):
        self.close_pdf_doc()  # the file is about to be rewritten in place
        rotate_pages(self.path, 90)
        self.reload_pdf_doc()

        self.refresh_pages()

    def __zoom_percentage_callback_func(self, zoom_percentage):
        
        # Remove text selection because tkinter canvas images dont scale 
        if self.__selecting_text_rect_id != None:
            self.__clear_selected_shown_text()

        # Pass up to the document navigation tools ui
        self.__zoom_percentage_callback(zoom_percentage)

    def get_selection_subscription(self, selection_callback):
        '''Sets callback that notifies another object of selection'''
        #self.__selection_callback = callback
        selection_callback(self.__subscribe_to_selections)


    def __subscribe_to_selections(self, selection_callback, page_change_callback, selected_text_callback, full_page_image_callback
                                  , multi_selection_callback=None, refresh_tool_canvas_callback=None,show_cell_link_callback=None,
                                  text_mark_callback=None,pending_linked_text_action_callback=None):
        if selection_callback:
            self.__selection_callback = selection_callback
            
            if self.selected_poly or self.selected_rect:
                self.__send_selection_callback(True)
            else:
                self.__send_selection_callback(False)


        if page_change_callback:
            self.__tool_panel_document_or_page_number_change_callback = page_change_callback
            self.__tool_panel_document_or_page_number_change_callback(self.path,self.pno)

        if selected_text_callback:
            self.__tool_panel_selected_text_callback = selected_text_callback
            self.__tool_panel_selected_text_callback(self.__selected_shown_text_roi_list,self.path,self.pno,self.file_type)

        if full_page_image_callback:
            self.__full_page_image_callback = full_page_image_callback
            if self.__get_pages_thread_done:
                self.__full_page_image_callback(self.path,self.pno,self.full_page,self.pdf_zoom, self.full_svg_page)
        
        if multi_selection_callback:
            self.__selection_callbacks.append(multi_selection_callback)
            
            self.__get_object_selection()

        if refresh_tool_canvas_callback:
            self.__refresh_tool_canvas_callback = refresh_tool_canvas_callback

        if show_cell_link_callback:
            self.__show_cell_link_callback = show_cell_link_callback


    def __send_selection_callback(self, selection_detected):
        if not self.__selection_callback:
            return
        self.__selection_callback(selection_detected, 
                                    roi_select_func = self.get_selected_roi,
                                    text_roi_selected_func = self.setup_text_roi,
                                    move_to_roi_func = self.move_to_roi,
                                    clear_shown_text_roi_list = self.__clear_shown_text_roi_list,
                                    refresh_roi = self.__refresh_rois,
                                    draw_connecting_lines = self.__draw_connecting_lines,
                                    get_full_page_image = self.__get_full_page_image,
                                    get_text_on_page_func = self.__get_text_on_page,
                                    draw_roi_trigger_func = self.__draw_roi_trigger,
                                    document_type=self.file_type,
                                    send_document_selected_text_func=self.__document_selected_text
                                    )
        
    def __document_selected_text(self, text=None):
        self.__selected_text = text


    def __get_object_selection(self):
        self.__selected_objects = []
        self.__tool_canvas_list_to_refresh = []
        for callback in self.__selection_callbacks:
            if callback:
                objects, refresh_pending, canvas_name = callback(self.multi_highlighted_poly + 
                                   self.multi_highlighted_rect + 
                                   self.selected_poly + 
                                   self.selected_rect + 
                                   self.highlighted_poly + 
                                   self.highlighted_rect)
                if refresh_pending:
                    self.__tool_canvas_list_to_refresh.append(canvas_name)
                self.__selected_objects = self.__selected_objects + objects

        # Notify the toolbar whether the current selection can seed Draw ROI.
        if self.__draw_roi_availability_func:
            try:
                self.__draw_roi_availability_func(
                    self._find_selected_control_module_cell() is not None)
            except Exception:
                pass


                


    def __draw_connecting_lines(self, lines_on_page):
        self.__remove_all_drawn_connecting_lines()

        bbox = self.canvas.coords(self.container)  # get image area
        for lineString in lines_on_page:
            line = np.array(lineString,dtype=int)
            for i in range(len(line) - 1):
                line_id = self.canvas.create_line(line[i][1] * self.imscale + bbox[0]
                                                    ,line[i][0] * self.imscale + bbox[1]
                                                    ,line[i+1][1] * self.imscale + bbox[0]
                                                    ,line[i+1][0] * self.imscale + bbox[1]
                                                    ,fill='blue'
                                                    ,width=self.width_line)
                self.drawn_connecting_lines.append(line_id)


    def __remove_all_drawn_connecting_lines(self):
        for line_id in self.drawn_connecting_lines:
            self.canvas.delete(line_id)

    def __get_text_on_page(self):
        return self.text_in_page


    def __get_full_page_image(self,pdf_zoom=2):
        if self.file_type == Database.IMAGE:
            return self.image
        
        image_bytes, _ = self.get_page(0,0,0,0,pdf_zoom,True)
        Image.MAX_IMAGE_PIXELS = 1500000000
        return Image.open(io.BytesIO(image_bytes))


    def __start_get_full_page_thread(self, pdf_zoom=2):
        self.__get_pages_thread_done = False
        self.__get_pages_thread=Thread(target=self.__get_page, args=(pdf_zoom,))
        self.__get_pages_thread.start()
        self.canvas.after(500,self.__check_if_get_roi_done)


    def __get_page(self, pdf_zoom):
        image_bytes, _ = self.get_page(0,0,0,0,pdf_zoom,True)
        self.full_page = Image.open(io.BytesIO(image_bytes))
        self.full_svg_page = page_to_svg(self.path, self.pno)
        self.pdf_zoom = pdf_zoom
        text_page = self.text_doc[self.pno]
        self.text_in_page = text_page.chars(text_page.derotation_matrix,
                                            text_page.rotation_matrix)

        self.__get_pages_thread_done = True

    def __check_if_get_roi_done(self):
        if not self.__get_pages_thread_done:
            self.canvas.after(500,self.__check_if_get_roi_done)
            return
        if self.__full_page_image_callback:
            self.__full_page_image_callback(self.path,self.pno,self.full_page,self.pdf_zoom,self.full_svg_page)
        logging.info("Got Full page image of page {pno} of {doc}".format(pno=self.pno,doc=self.path))
        


    def __document_or_page_number_change(self):

        self.__get_rois()
        self.__remove_all_drawn_connecting_lines()
        if self.__tool_panel_document_or_page_number_change_callback:
            self.__tool_panel_document_or_page_number_change_callback(self.path,self.pno)

        if self.file_type != Database.IMAGE:
            self.__start_get_full_page_thread()

        
        

    def __refresh_rois(self, with_text=True, page_index=None):
        if page_index is not None and self.pno != page_index:
            return 
        self.roi_list = self.__db.get_project_document_roi(self.path)
        self.__get_rois(with_text)
        if with_text:
            self.__redraw_text_rois()


    def __redraw_text_rois(self):
        """ Redraws the char boxes that the roi refresh just wiped off the canvas """
        for linked_graphic_name, text_location_dict in list(self.__text_location_dicts.items()):
            if text_location_dict:
                self.setup_text_roi(text_location_dict, linked_graphic_name)


    def __get_rois(self, with_text=True):
        
        logging.info("Getting page number {pno} of {doc} region-of-interests".format(pno=self.pno,doc=self.path))
        if len(self.roi_list) != self.page_count:
            while len(self.roi_list) < self.page_count:
                self.roi_list.append(None)
            logging.info("Created new region-of-interests list for document {doc} ".format(doc=self.path))

        if self.roi_list[self.pno] == None:
            self.roi_list[self.pno] = {}
            logging.info("Created new region-of-interests list for page number {pno} of {doc} ".format(pno=self.pno,doc=self.path))

        logging.info("Redrawing region-of-interests for page number {pno} of {doc} ".format(pno=self.pno,doc=self.path))
        self.reset(self.roi_list[self.pno],with_text)
        
    def get_draw_roi_func(self, func):
        self.__draw_roi_button_indication_func = func

    def get_draw_roi_availability_func(self, func):
        """ Register a callback invoked with True/False whenever the currently
        selected object can seed the Draw ROI tool (i.e. it exposes
        `instantiate_manual_placement`). Used by the toolbar to enable/disable
        the Draw ROI button. """
        self.__draw_roi_availability_func = func
        # Fire once so the caller can set the initial state.
        try:
            func(self._find_selected_control_module_cell() is not None)
        except Exception:
            pass

    def selector_tool_chosen(self, chosen_tool):
        self.__selector_tool_chosen = chosen_tool
        self.__set_chosen_tool()

    def __set_chosen_tool(self, clear_selection=True):
        # The Draw ROI tool must not lose the currently-selected linked-graphic
        # cell that seeds it, so we always preserve the selection for that mode.
        if clear_selection and self.__selector_tool_chosen != self.DRAW_ROI_TOOL:
            self.unhighlight_poly()
            self.unselect_poly()
        # Ensure any in-progress Draw ROI session is torn down when switching tools
        self.__cancel_draw_roi_session()
        
        if self.__selector_tool_chosen == self.CURSOR_TOOL:
            self.__cursor_tool()
        elif self.__selector_tool_chosen == self.HAND_TOOL:
            self.__hand_tool()
        elif self.__selector_tool_chosen == self.RECTANGULAR_TOOL:
            self.__rectangular_tool()
        elif self.__selector_tool_chosen == self.POLYGON_TOOL:
            self.__polygon_tool()
        elif self.__selector_tool_chosen == self.AUTO_SELECT_TOOL:
            self.__auto_select_tool()
        elif self.__selector_tool_chosen == self.DRAW_ROI_TOOL:
            self.__draw_roi_tool()


    def __finished_text_select(self, _):
        # To remove a text selection
        self.__finished_selecting_text = True


    def __cursor_tool(self):
        self.canvas.unbind('<ButtonPress-1>')
        self.canvas.unbind('<ButtonRelease-3>') 
        self.canvas.unbind('<Motion>') 
        self.canvas.unbind('<Delete>')
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.unbind("<Control-1>")
        self.canvas.unbind('<Alt-v>')
        self.canvas.unbind('<Control-c>')

        #self.canvas.bind('<ButtonRelease-3>', self.popup)  # call popup menu
        self.canvas.bind('<Motion>', self.motion)  # handle mouse motion
        self.canvas.bind("<ButtonRelease-1>",self.on_selection_button_release)
        self.canvas.bind("<ButtonPress-1>", self.on_button_press_selection)
        self.canvas.bind("<B1-Motion>", self.on_rect_move_press)
        self.canvas.bind("<Control-1>", self.on_control_shift_press)
        self.canvas.bind('<ButtonRelease-3>', self.popup)  # call popup menu
        self.canvas.bind('<Alt-v>', self.view_link)
        self.canvas.bind('<Control-c>', self.copy_text)

        # Editing functionality bindings
        self.canvas.bind('<ButtonPress-1>', self.start_vertex_drag, add='+') # Add binding for vertex drag start
        self.canvas.bind('<B1-Motion>', self.drag_vertex, add='+') # Binding for vertex dragging
        self.canvas.bind('<ButtonRelease-1>', self.stop_vertex_drag, add='+') # Binding for vertex drag stop
        self.show_crosshair = False


    def __hand_tool(self):
        self.canvas.unbind('<ButtonPress-1>')
        self.canvas.unbind('<ButtonRelease-3>') 
        self.canvas.unbind('<Motion>') 
        self.canvas.unbind('<Delete>')
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.unbind("<Control-1>")
        self.canvas.unbind('<Alt-v>')
        self.canvas.unbind('<Control-c>')

        self.canvas.bind('<ButtonPress-1>', self.move_from)  # remember canvas position
        self.canvas.bind('<B1-Motion>', self.move_to)  # move canvas to the new position
        self.canvas.bind("<ButtonRelease-1>",self.__finished_text_select)
        self.canvas.bind('<Delete>', lambda _: self.delete_selected())  # delete selected rectangle

        # Editing functionality bindings
        self.canvas.bind('<ButtonPress-1>', self.start_vertex_drag, add='+') # Add binding for vertex drag start
        self.canvas.bind('<B1-Motion>', self.drag_vertex, add='+') # Binding for vertex dragging
        self.canvas.bind('<ButtonRelease-1>', self.stop_vertex_drag, add='+') # Binding for vertex drag stop

        self.show_crosshair = False


    def __rectangular_tool(self):
        self.canvas.unbind('<ButtonPress-1>')
        self.canvas.unbind('<ButtonRelease-3>') 
        self.canvas.unbind('<Motion>') 
        self.canvas.unbind('<Delete>')
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.unbind("<Control-1>")
        self.canvas.unbind('<Alt-v>')
        self.canvas.unbind('<Control-c>')

        self.canvas.bind('<ButtonRelease-3>', self.popup)  # call popup menu
        self.canvas.bind('<Motion>', self.motion)  # handle mouse motion
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_rect_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.canvas.bind('<Delete>', lambda _: self.delete_selected())  # delete selected rectangle
        self.canvas.bind('<Alt-v>', self.view_link)
        self.canvas.bind('<Control-c>', self.copy_text)

        # Editing functionality bindings
        self.canvas.bind('<ButtonPress-1>', self.start_vertex_drag, add='+') # Add binding for vertex drag start
        self.canvas.bind('<B1-Motion>', self.drag_vertex, add='+') # Binding for vertex dragging
        self.canvas.bind('<ButtonRelease-1>', self.stop_vertex_drag, add='+') # Binding for vertex drag stop

        self.show_crosshair = True


    def __polygon_tool(self):
        self.canvas.unbind('<ButtonPress-1>')
        self.canvas.unbind('<ButtonRelease-3>') 
        self.canvas.unbind('<Motion>') 
        self.canvas.unbind('<Delete>')
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.unbind("<Control-1>")
        self.canvas.unbind('<Alt-v>')
        self.canvas.unbind('<Control-c>')

        self.canvas.bind('<ButtonPress-1>', self.set_edge)  # set new edge
        self.canvas.bind('<ButtonRelease-3>', self.popup)  # call popup menu
        self.canvas.bind('<Motion>', self.motion)  # handle mouse motion
        self.canvas.bind('<Delete>', lambda _: self.delete_selected())
        self.canvas.bind('<B1-Motion>',self.__on_text_move_press)
        self.canvas.bind("<ButtonRelease-1>",self.__finished_text_select)
        self.canvas.bind('<Alt-v>', self.view_link)
        self.canvas.bind('<Control-c>', self.copy_text)

        # Editing functionality bindings
        self.canvas.bind('<ButtonPress-1>', self.start_vertex_drag, add='+') # Add binding for vertex drag start
        self.canvas.bind('<B1-Motion>', self.drag_vertex, add='+') # Binding for vertex dragging
        self.canvas.bind('<ButtonRelease-1>', self.stop_vertex_drag, add='+') # Binding for vertex drag stop

        self.show_crosshair = False


    def __auto_select_tool(self):
        self.canvas.unbind('<ButtonPress-1>')
        self.canvas.unbind('<ButtonRelease-3>') 
        self.canvas.unbind('<Motion>') 
        self.canvas.unbind('<Delete>')
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.unbind("<Control-1>")
        self.canvas.unbind('<Alt-v>')
        self.canvas.unbind('<Control-c>')

        self.canvas.bind('<ButtonPress-1>', self.set_auto_select_point_box)
        self.canvas.bind('<Motion>', self.motion)  # handle mouse motion
        self.canvas.bind('<B1-Motion>', self.auto_selection_motion)
        self.canvas.bind('<ButtonRelease-1>', self.auto_selection_release)
        self.canvas.bind('<ButtonRelease-3>', self.popup)  # call popup menu
        self.canvas.bind('<Delete>', lambda _: self.delete_selected())
        self.canvas.bind('ButtonRelease-1>', self.__finished_text_select)
        self.canvas.bind('<Alt-v>', self.view_link)
        self.canvas.bind('<Control-c>', self.copy_text)

        # Editing functionality bindings
        self.canvas.bind('<ButtonPress-1>', self.start_vertex_drag, add='+') # Add binding for vertex drag start
        self.canvas.bind('<B1-Motion>', self.drag_vertex, add='+') # Binding for vertex dragging
        self.canvas.bind('<ButtonRelease-1>', self.stop_vertex_drag, add='+') # Binding for vertex drag stop

        self.show_crosshair = False


    def __draw_roi_tool(self):
        self.canvas.unbind('<ButtonPress-1>')
        self.canvas.unbind('<ButtonRelease-3>') 
        self.canvas.unbind('<Motion>') 
        self.canvas.unbind('<Delete>')
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.unbind("<Control-1>")
        self.canvas.unbind('<Alt-v>')
        self.canvas.unbind('<Control-c>')
        self.canvas.unbind('<Escape>')
        self.canvas.unbind('<Return>')

        self.canvas.bind('<ButtonRelease-3>', self.popup)
        self.canvas.bind('<Motion>', self.draw_roi_motion)
        self.canvas.bind('<ButtonPress-1>', self.draw_roi_press)
        self.canvas.bind('<B1-Motion>', self.draw_roi_drag)
        self.canvas.bind('<ButtonRelease-1>', self.draw_roi_release)
        self.canvas.bind('<Delete>', lambda _: self.cancel_draw_roi())
        self.canvas.bind('<Escape>', lambda _: self.cancel_draw_roi())
        self.canvas.bind('<Return>', lambda _: self.commit_draw_roi())
        self.canvas.bind('<Alt-v>', self.view_link)
        self.canvas.bind('<Control-c>', self.copy_text)

        # Try to seed from the currently selected control-module cell.
        source_cell = self._find_selected_control_module_cell()
        if source_cell is not None and self._seed_draw_roi_from_cell(source_cell):
            self._notify_draw_roi_button(True)
        self.show_crosshair = True
        

    def add_vertex_to_line(self):
        """ Add a new vertex to the polygon at the clicked line """
        if not self.edit_mode or not self.current_polygon_editing_tag or not self.last_current_item:
            return

        polygon_tag = self.current_polygon_editing_tag
        polygon_const_tag = polygon_tag + self.tag_poly_const

        polygon_vertices = self.roi_list[self.pno][polygon_tag]
        polygon_dict = self.roi_list[self.pno]
        tag = self.tag_roi
        

        line_tags = self.canvas.gettags(self.last_current_item)

        if self.tag_poly_line in line_tags and line_tags[1] == polygon_tag:
            index = int(line_tags[3]) # Get the index of the line segment in the polygon vertices list
            
            p1 = polygon_vertices[index]
            p2 = polygon_vertices[index+1]

            new_vertex = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
            polygon_vertices.insert(index+1, new_vertex)

            self.canvas.delete(polygon_const_tag) 
            self.canvas.delete(polygon_tag)
            self._hide_vertex_circles() # Delete old vertex circles


            color = self.color_roi 
            self.draw_polygon(polygon_vertices, color, tag, polygon_dict, polygon_tag) # Redraw polygon
            self.save_page_roi()
            self._draw_vertex_circles(polygon_tag) # Redraw vertex circles

    
    def edit_poly_mode(self):
        """ Enter polygon edit mode for the selected polygon """
        if not self.highlighted_poly:
            return
        if self.current_polygon_editing_tag:
            self.exit_edit_poly_mode()
        self.edit_mode = True
        polygon_tag = self.highlighted_poly[0] # Assuming only one polygon is selected for edit
        self.current_polygon_editing_tag = polygon_tag
        self.previous_dragged_polygon_tag = None
        self._draw_vertex_circles(polygon_tag)
        self.canvas.config(cursor="hand2") # Change cursor to indicate edit mode


    def exit_edit_poly_mode(self):
        """ Exit polygon edit mode """
        self.edit_mode = False
        self._hide_vertex_circles()
        self.current_polygon_editing_tag = None
        self.selected_vertex_index = None
        self.previous_dragged_polygon_tag = None
        self.menu.remove_polygon_menu()
        self.canvas.config(cursor="") # Restore default cursor


    
    def _draw_vertex_circles(self, polygon_tag):
        """ Draw circles around vertices of the polygon to indicate editable vertices """
        polygon_const_tag = polygon_tag + self.tag_poly_const
        a = self.canvas.find_withtag(polygon_const_tag)
        if not a:
            return
        polygon_item_id = self.canvas.find_withtag(polygon_const_tag)[0] # Get the polygon item id
        vertices_canvas_coords = self.canvas.coords(polygon_item_id)

        polygon_vertices = []
        if self.is_roi(polygon_const_tag):
            polygon_vertices = self.roi_list[self.pno][polygon_tag]
        else:
            polygon_vertices = self.hole_dict[polygon_tag]

        vertex_circles = {}
        for i in range(len(polygon_vertices)):
            x_canvas, y_canvas = vertices_canvas_coords[2*i], vertices_canvas_coords[2*i+1]
            circle_item = self.canvas.create_oval(x_canvas - self.radius_vertex_circle,
                                                 y_canvas - self.radius_vertex_circle,
                                                 x_canvas + self.radius_vertex_circle,
                                                 y_canvas + self.radius_vertex_circle,
                                                 fill='red', outline='black',
                                                 tags=(self.tag_vertex_circle, polygon_tag)) # Tag vertex circles with vertex_circle and polygon tag
            self.canvas.tag_bind(circle_item, '<Enter>', lambda event, item=circle_item: self.canvas.itemconfig(item, fill='lightgray'))
            self.canvas.tag_bind(circle_item, '<Leave>', lambda event, item=circle_item: self.canvas.itemconfig(item, fill='red'))
            vertex_circles[i] = circle_item # Store item id with vertex index
        self.vertex_circles[polygon_tag] = vertex_circles


    def _hide_vertex_circles(self):
        """ Hide vertex circles for the currently edited polygon """
        if self.current_polygon_editing_tag and self.current_polygon_editing_tag in self.vertex_circles:
            for circle_item in self.vertex_circles[self.current_polygon_editing_tag].values():
                self.canvas.delete(circle_item)
            del self.vertex_circles[self.current_polygon_editing_tag]


    def start_vertex_drag(self, event):
        """ Start dragging a vertex if clicked on a vertex circle """
        if not self.edit_mode:
            return

        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        closest_vertex_circle = self.canvas.find_closest(x, y, halo=5) # Find closest item within halo

        if closest_vertex_circle and self.tag_vertex_circle in self.canvas.gettags(closest_vertex_circle):
            vertex_circle_item = closest_vertex_circle[0]
            tags = self.canvas.gettags(vertex_circle_item)
            polygon_tag = next((tag for tag in tags if tag not in [self.tag_vertex_circle, 'current']), None) # Get polygon tag

            if polygon_tag and polygon_tag == self.current_polygon_editing_tag and polygon_tag in self.vertex_circles:
                for index, item_id in self.vertex_circles[polygon_tag].items():
                    if item_id == vertex_circle_item:
                        self.selected_vertex_index = index
                        return # Exit after finding and setting the selected vertex
        else:
            self.exit_edit_poly_mode()


    def is_currently_dragging_vertex(self):
        return  self.edit_mode and self.selected_vertex_index and self.current_polygon_editing_tag


    def drag_vertex(self, event):
        """ Drag the selected vertex to the new mouse position """
        if not self.edit_mode or self.selected_vertex_index is None or not self.current_polygon_editing_tag:
            return
        x_canvas = self.canvas.canvasx(event.x)
        y_canvas = self.canvas.canvasy(event.y)


        polygon_tag = self.current_polygon_editing_tag
        polygon_const_tag = polygon_tag + self.tag_poly_const


        polygon_vertices = self.roi_list[self.pno][polygon_tag]
        polygon_dict = self.roi_list[self.pno]
        tag = self.tag_roi
        

        #Update vertex coordinates in polygon vertices list (in image coordinates)
        bbox = self.canvas.coords(self.container)  # get image area
        x_image = round((x_canvas - bbox[0]) / self.imscale)  # get real (x,y) on the image without zoom
        y_image = round((y_canvas - bbox[1]) / self.imscale)
        polygon_vertices[self.selected_vertex_index] = (x_image, y_image)

        # Check for self-intersections and outside vertices
        if self.polygon_selfintersection_edit(polygon_vertices) or self.outside_polygon_vertex(polygon_vertices):
            return

        polygon_dict[polygon_tag] = polygon_vertices # Update the dictionary

        # Update canvas polygon and vertex circles
        self.canvas.delete(polygon_const_tag) # Delete old polygon
        self.canvas.delete(polygon_tag) # Delete old poly lines
        self._hide_vertex_circles() # Delete old vertex circles

        color = self.color_roi 
        self.draw_polygon(polygon_vertices, color, tag, polygon_dict, polygon_tag) # Redraw polygon with updated vertices
        #self.save_page_roi()
        
        self._draw_vertex_circles(polygon_tag) # Redraw vertex circles for the updated polygon


    def stop_vertex_drag(self, event):
        """ Stop vertex dragging and reset selected vertex index """
        if self.current_polygon_editing_tag:
            self.save_page_roi()
        
        
        
    def outside_polygon_vertex(self, polygon_vertices):
        """ Check if any vertex of the given polygon is outside the image bounds """
        bbox = self.canvas.coords(self.container)  # get image area
        for vertex in polygon_vertices:
            x_canvas = vertex[0] * self.imscale + bbox[0]
            y_canvas = vertex[1] * self.imscale + bbox[1]
            if self.outside(x_canvas, y_canvas):
                return True
        return False
    

    def polygon_selfintersection_edit(self, polygon_vertices):
        """ Check if a given polygon (list of vertices) has self-intersections during edit """
        for i in range(len(polygon_vertices)):
            p1 = polygon_vertices[i]
            p2 = polygon_vertices[(i + 1) % len(polygon_vertices)]
            for j in range(len(polygon_vertices)):
                if i == j: continue # Don't compare same segment
                p3 = polygon_vertices[j]
                p4 = polygon_vertices[(j + 1) % len(polygon_vertices)]
                if j == (i + 1) % len(polygon_vertices) or i == (j + 1) % len(polygon_vertices): continue # Don't compare adjacent segments
                if self.intersect(p1, p2, p3, p4):
                    return True

        return False


    def delete_vertex(self):
        """ Delete the selected vertex from the polygon """
        if not self.edit_mode or self.selected_vertex_index is None or not self.current_polygon_editing_tag:
            return

        polygon_tag = self.current_polygon_editing_tag
        polygon_const_tag = polygon_tag + self.tag_poly_const

        if self.is_roi(polygon_const_tag):
            polygon_vertices = self.roi_list[self.pno][polygon_tag]
            polygon_dict = self.roi_list[self.pno]
        else:
            polygon_vertices = self.hole_dict[polygon_tag]
            polygon_dict = self.hole_dict

        if len(polygon_vertices) <= 3: # Polygons need at least 3 vertices
            return # Do nothing if trying to delete vertex from triangle or less

        del polygon_vertices[self.selected_vertex_index] # Remove vertex from list
        polygon_dict[polygon_tag] = polygon_vertices # Update dictionary

        # Update canvas polygon and vertex circles
        self.canvas.delete(polygon_const_tag) # Delete old polygon
        self.canvas.delete(polygon_tag) # Delete old poly lines
        self._hide_vertex_circles() # Delete old vertex circles


        color = self.color_roi 
        tag = self.tag_roi 
        self.draw_polygon(polygon_vertices, color, tag, polygon_dict) # Redraw polygon
        self.save_page_roi()
        self._draw_vertex_circles(polygon_tag) # Redraw vertex circles


        self.selected_vertex_index = None # Reset selected vertex index

    def valid_selection_rectangle_size(self, x0, y0, x1, y1):
        """ Check if the selection rectangle has a valid size """
        return abs(x1 - x0) > 10 and abs(y1 - y0) > 10

    def auto_selection_release(self, event):
        
        
        self.__finished_selecting_text = True

        curX, curY = ( self.canvas.canvasx(event.x),  self.canvas.canvasy(event.y))

        if not self.is_valid_auto_selection_click(curX, curY):
            return
        
        if self.auto_selection_press_pos is None:
            return

        valid_size = self.valid_selection_rectangle_size(self.auto_selection_press_pos[0]
                                                         , self.auto_selection_press_pos[1]
                                                         , curX, curY)
        
        if not self.is_showing_auto_selection_overlay and self.auto_selection_rectangle_id and valid_size:
            return self.start_auto_selection()
        elif self.auto_selection_rectangle_id and not valid_size:
            self.canvas.delete(self.auto_selection_rectangle_id)
            return
    
        if self.is_showing_auto_selection_overlay:
            is_close, closest_point = self.is_close_to_point(curX, curY)
            if is_close:
                self.delete_auto_selection_point(closest_point)
            elif self.is_inside_polygon(curX, curY):
                self.add_auto_select_point(curX, curY, is_positive=False)
            else:
                self.add_auto_select_point(curX, curY, is_positive=True)


    def __image_changed_callback(self):
        self.__refresh_auto_select_overlay_image()
        self.__refresh_draw_roi_overlay()


    def __refresh_auto_select_overlay_image(self):
        if self.is_showing_auto_selection_overlay:

            x0, y0, x1, y1 = self.canvas.coords(self.auto_selection_rectangle_id)
            bbox = self.canvas.coords(self.container)  # get image area
            x0 = (x0 - bbox[0])  # get real (x,y) on the image without zoom
            y0 = (y0 - bbox[1]) 
            x1 = (x1 - bbox[0]) 
            y1 = (y1 - bbox[1]) 

            self.draw_auto_selection_overlay(x0, y0, x1, y1, bbox)

    # =====================================================================
    #  Draw ROI tool  ---  seeded from an existing linked graphic (primary
    #  polygon + text-region outlines); user transforms and commits as a
    #  full linked-graphic copy.
    # =====================================================================

    # Handle roles for the transform-mode oriented bounding box.
    _DRAW_ROI_HANDLE_ROLES = ('nw', 'ne', 'se', 'sw', 'rotate')
    _DRAW_ROI_HANDLE_SIZE = 5           # half side (in canvas px) of a resize handle
    _DRAW_ROI_ROTATE_OFFSET = 26        # gap in canvas px above OBB top for rotate handle
    _DRAW_ROI_HIT_HALO = 6              # px halo for handle hit-testing
    _DRAW_ROI_SNAP_STEP_DEG = 15        # rotation snap when Shift held during drag

    def _init_draw_roi_state(self):
        """ Initialise/reset per-session Draw ROI state (safe to call repeatedly). """
        self._draw_roi_state = 'idle'            # 'idle' | 'placement' | 'transform'
        self._draw_roi_source_cell = None        # cell that seeded the tool
        # Template geometry in OBB-local coords (destination image-space):
        self._draw_roi_base_local = []           # outer polygon [(lx, ly), ...]
        self._draw_roi_base_text_rois = []       # [ [(lx, ly), ...], ...]
        self._draw_roi_obb_center = (0.0, 0.0)   # image coords (dest doc)
        self._draw_roi_obb_size = (0.0, 0.0)     # (w, h) at time of seed
        # User-controlled transforms:
        self._draw_roi_angle = 0.0               # degrees
        self._draw_roi_scale = 1.0               # uniform scale factor
        self._draw_roi_flip_h = False
        self._draw_roi_flip_v = False
        # Canvas item ids for transient visuals:
        self._draw_roi_polyline_ids = []
        self._draw_roi_text_indicator_ids = []
        self._draw_roi_handle_ids = {}
        self._draw_roi_rotate_line_id = None
        self._draw_roi_overlay_button_ids = {}
        self._draw_roi_overlay_photos = {}
        # Interaction snapshot:
        self._draw_roi_active_handle = None
        self._draw_roi_drag_snapshot = None

    def __cancel_draw_roi_session(self):
        """ Tear down any in-progress Draw ROI visuals (used when switching tools/pages). """
        if not hasattr(self, '_draw_roi_state'):
            self._init_draw_roi_state()
            return
        self._clear_draw_roi_visuals()
        self._init_draw_roi_state()

    def _clear_draw_roi_visuals(self):
        """ Delete all transient canvas items for the Draw ROI session. """
        for pid in self._draw_roi_polyline_ids:
            self.canvas.delete(pid)
        self._draw_roi_polyline_ids = []
        for tid in self._draw_roi_text_indicator_ids:
            self.canvas.delete(tid)
        self._draw_roi_text_indicator_ids = []
        for hid in self._draw_roi_handle_ids.values():
            self.canvas.delete(hid)
        self._draw_roi_handle_ids = {}
        if self._draw_roi_rotate_line_id is not None:
            self.canvas.delete(self._draw_roi_rotate_line_id)
            self._draw_roi_rotate_line_id = None
        for ids in self._draw_roi_overlay_button_ids.values():
            id_list = ids if isinstance(ids, (list, tuple)) else (ids,)
            for bid in id_list:
                self.canvas.tag_unbind(bid, "<ButtonRelease-1>")
                self.canvas.delete(bid)
        self._draw_roi_overlay_button_ids = {}
        self._draw_roi_overlay_photos = {}

    def __draw_roi_trigger(self, trigger_object=None):
        """ Callback invoked from the tool-cell button. `trigger_object` is the
        cell whose primary linked graphic seeds the tool. """
        self.__selector_tool_chosen = self.DRAW_ROI_TOOL
        self.__set_chosen_tool(False)
        if trigger_object is not None and self._seed_draw_roi_from_cell(trigger_object):
            self._notify_draw_roi_button(True)

    def _notify_draw_roi_button(self, active):
        """ Tell the toolbar whether a Draw ROI session is actually running, so the
        button does not stay highlighted / selected once the session has ended. """
        if not self.__draw_roi_button_indication_func:
            return
        try:
            self.__draw_roi_button_indication_func(bool(active))
        except Exception:
            logging.exception("Draw ROI: failed to update the toolbar button state")

    def _image_to_canvas(self, x_img, y_img):
        bbox = self.canvas.coords(self.container)
        return (x_img * self.imscale + bbox[0], y_img * self.imscale + bbox[1])

    def _canvas_to_image(self, x_c, y_c):
        bbox = self.canvas.coords(self.container)
        return ((x_c - bbox[0]) / self.imscale, (y_c - bbox[1]) / self.imscale)

    # ---- Event handlers ------------------------------------------------

    def draw_roi_motion(self, event):
        self.motion(event)
        state = getattr(self, '_draw_roi_state', 'idle')
        if state != 'placement':
            return
        curX = self.canvas.canvasx(event.x)
        curY = self.canvas.canvasy(event.y)
        img_x, img_y = self._canvas_to_image(curX, curY)
        self._draw_roi_obb_center = (img_x, img_y)
        self._render_draw_roi_transform()

    def draw_roi_press(self, event):
        if self.edit_mode:
            return
        self.canvas.focus_set()
        curX = self.canvas.canvasx(event.x)
        curY = self.canvas.canvasy(event.y)
        bbox = self.canvas.coords(self.container)
        if not (bbox[0] <= curX < bbox[2] and bbox[1] <= curY < bbox[3]):
            return
        state = getattr(self, '_draw_roi_state', 'idle')
        if state == 'placement':
            self._land_placement(curX, curY)
        elif state == 'transform':
            self._begin_draw_roi_transform_drag(event, curX, curY)

    def draw_roi_drag(self, event):
        if getattr(self, '_draw_roi_state', 'idle') != 'transform':
            return
        if not self._draw_roi_active_handle:
            return
        curX = self.canvas.canvasx(event.x)
        curY = self.canvas.canvasy(event.y)
        role = self._draw_roi_active_handle
        if role == 'move':
            self._apply_draw_roi_move(curX, curY)
        elif role == 'rotate':
            shift_down = bool(event.state & 0x0001)
            self._apply_draw_roi_rotate(curX, curY, snap=shift_down)
        else:
            self._apply_draw_roi_resize(role, curX, curY)
        self._render_draw_roi_transform()

    def draw_roi_release(self, _):
        if getattr(self, '_draw_roi_state', 'idle') != 'transform':
            return
        # Snap rotation to the nearest 90 degrees on release of the rotate handle
        # so the final template rotation is representable in Template_Rotate.
        if self._draw_roi_active_handle == 'rotate':
            snapped = round(self._draw_roi_angle / 90.0) * 90.0
            self._draw_roi_angle = ((snapped + 180) % 360) - 180
            self._render_draw_roi_transform()
        self._draw_roi_active_handle = None
        self._draw_roi_drag_snapshot = None

    # ---- Source seeding -------------------------------------------------

    def _find_selected_control_module_cell(self):
        """ Return the currently selected object if it looks like a
        control-module cell that carries a primary linked graphic, else None. """
        selected = getattr(self, '_SelectorTools__selected_objects', None)
        if not selected:
            return None
        for obj in selected:
            if hasattr(obj, 'get_primary_linked_graphic_data') and \
                    hasattr(obj, 'instantiate_manual_placement'):
                return obj
        return None

    def _seed_draw_roi_from_cell(self, cell):
        """ Fetch the primary linked-graphic polygon + text_rois from `cell`, normalise
        them to destination image coords, and enter placement mode. Returns True on
        success. """
        try:
            source = cell.get_primary_linked_graphic_data()
        except Exception:
            source = None
        if not source:
            return False
        template_polygon = source.get('roi')
        if not template_polygon or len(template_polygon) < 3:
            return False

        # Prefer the currently-highlighted placed polygon on this page so the
        # ghost matches the visible source shape (`get_data()` returns the
        # underlying TEMPLATE polygon, which can be much smaller than any
        # scanner-placed instance).
        placed_polygon = None
        selected_uids = list(self.selected_poly) + list(self.highlighted_poly)
        page_roi = None
        if 0 <= self.pno < len(self.roi_list):
            page_roi = self.roi_list[self.pno]
        if page_roi:
            for uid in selected_uids:
                if uid in page_roi:
                    candidate = page_roi[uid]
                    if candidate and len(candidate) >= 3:
                        placed_polygon = candidate
                        break

        outer_polygon = placed_polygon if placed_polygon else template_polygon

        xs = [p[0] for p in outer_polygon]
        ys = [p[1] for p in outer_polygon]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0
        w = max(max_x - min_x, 1e-6)
        h = max(max_y - min_y, 1e-6)
        self._draw_roi_base_local = [(p[0] - cx, p[1] - cy) for p in outer_polygon]

        # Derive a template->placed scale ratio so the text-region indicators
        # sit at the correct positions on top of the (possibly larger) placed
        # polygon. Both bboxes are compared in their own native coord systems,
        # so any pdf_zoom_scale difference cancels out.
        txs = [p[0] for p in template_polygon]
        tys = [p[1] for p in template_polygon]
        tw = max(max(txs) - min(txs), 1e-6)
        th = max(max(tys) - min(tys), 1e-6)
        template_cx = (min(txs) + max(txs)) / 2.0
        template_cy = (min(tys) + max(tys)) / 2.0
        scale_ratio = ((w / tw) + (h / th)) / 2.0

        text_dict = source.get('text_location_dict') or {}
        text_rois_local = []
        for _, entry in text_dict.items():
            text_roi = entry.get('text_roi') if isinstance(entry, dict) else None
            if not text_roi or len(text_roi) < 3:
                continue
            local_pts = [
                ((p[0] - template_cx) * scale_ratio,
                 (p[1] - template_cy) * scale_ratio)
                for p in text_roi
            ]
            text_rois_local.append(local_pts)
        self._draw_roi_base_text_rois = text_rois_local

        # `create_copy` scales the source *template* polygon by
        # `template_to_match_ratio`. Our base_local was seeded from the placed
        # polygon (already `scale_ratio` × template). Capture that seed ratio
        # so `_persist_manual_placement` can pass the *effective* ratio =
        # user_scale × seed_ratio, otherwise create_copy produces a
        # template-sized polygon at the corner of the user-drawn bbox and the
        # placement appears mis-sized / mis-positioned.
        self._draw_roi_template_scale_at_seed = scale_ratio

        self._draw_roi_obb_size = (w, h)
        self._draw_roi_angle = 0.0
        self._draw_roi_scale = 1.0
        self._draw_roi_flip_h = False
        self._draw_roi_flip_v = False
        self._draw_roi_source_cell = cell
        # Anchor at the current cursor / canvas centre initially; motion moves it.
        try:
            centre_canvas_x = self.canvas.canvasx(self.canvas.winfo_width() / 2)
            centre_canvas_y = self.canvas.canvasy(self.canvas.winfo_height() / 2)
            self._draw_roi_obb_center = self._canvas_to_image(centre_canvas_x, centre_canvas_y)
        except Exception:
            self._draw_roi_obb_center = (0.0, 0.0)
        self._draw_roi_state = 'placement'
        self._render_draw_roi_transform()
        self.menu.enable_flip_horizontal(True)
        self.menu.enable_flip_vertical(True)
        return True

    def _land_placement(self, curX, curY):
        """ Confirm the placement at the cursor location and enter transform mode. """
        img_x, img_y = self._canvas_to_image(curX, curY)
        self._draw_roi_obb_center = (img_x, img_y)
        self._draw_roi_state = 'transform'
        self._render_draw_roi_transform()

    def _transform_local_point(self, lx, ly):
        """ Apply flip -> uniform scale -> rotate -> translate to a local point. """
        if self._draw_roi_flip_h:
            lx = -lx
        if self._draw_roi_flip_v:
            ly = -ly
        s = self._draw_roi_scale
        lx *= s
        ly *= s
        theta = math.radians(self._draw_roi_angle)
        cs = math.cos(theta)
        sn = math.sin(theta)
        rx = lx * cs - ly * sn
        ry = lx * sn + ly * cs
        cx, cy = self._draw_roi_obb_center
        return (cx + rx, cy + ry)

    def _current_transformed_polygon(self):
        return [self._transform_local_point(x, y) for x, y in self._draw_roi_base_local]

    def _current_transformed_text_rois(self):
        """ Return list of transformed text-region polygons in image coords. """
        out = []
        for poly in self._draw_roi_base_text_rois:
            out.append([self._transform_local_point(x, y) for x, y in poly])
        return out

    def _obb_corners_image(self):
        """ Return current OBB corners (nw, ne, se, sw) + rotate handle in image coords. """
        s = self._draw_roi_scale
        w = self._draw_roi_obb_size[0] * s
        h = self._draw_roi_obb_size[1] * s
        hx = w / 2.0
        hy = h / 2.0
        locals_ = {
            'nw': (-hx, -hy),
            'ne': ( hx, -hy),
            'se': ( hx,  hy),
            'sw': (-hx,  hy),
        }
        theta = math.radians(self._draw_roi_angle)
        cs = math.cos(theta)
        sn = math.sin(theta)
        cx, cy = self._draw_roi_obb_center
        out = {}
        for role, (lx, ly) in locals_.items():
            rx = lx * cs - ly * sn
            ry = lx * sn + ly * cs
            out[role] = (cx + rx, cy + ry)
        # 'n' is used only to anchor the rotate-handle connector line.
        rlx_n, rly_n = 0.0, -hy
        rx_n = rlx_n * cs - rly_n * sn
        ry_n = rlx_n * sn + rly_n * cs
        out['n'] = (cx + rx_n, cy + ry_n)
        # Rotate handle sits above the top-center along the local -y axis (canvas px offset).
        offset_img = self._DRAW_ROI_ROTATE_OFFSET / max(self.imscale, 1e-6)
        rlx, rly = 0.0, -hy - offset_img
        rrx = rlx * cs - rly * sn
        rry = rlx * sn + rly * cs
        out['rotate'] = (cx + rrx, cy + rry)
        return out

    def _render_draw_roi_transform(self):
        # Redraw outer polyline
        for pid in self._draw_roi_polyline_ids:
            self.canvas.delete(pid)
        self._draw_roi_polyline_ids = []
        color = self.color_roi
        poly_img = self._current_transformed_polygon()
        poly_canvas = [self._image_to_canvas(x, y) for x, y in poly_img]
        for i in range(len(poly_canvas)):
            x1, y1 = poly_canvas[i]
            x2, y2 = poly_canvas[(i + 1) % len(poly_canvas)]
            lid = self.canvas.create_line(x1, y1, x2, y2, fill=color['draw'],
                                          width=self.width_line, dash=self.dash)
            self._draw_roi_polyline_ids.append(lid)
        # Redraw text-region indicators (per-region 4-point outlines)
        for tid in self._draw_roi_text_indicator_ids:
            self.canvas.delete(tid)
        self._draw_roi_text_indicator_ids = []
        for text_poly_img in self._current_transformed_text_rois():
            text_canvas = [self._image_to_canvas(x, y) for x, y in text_poly_img]
            for i in range(len(text_canvas)):
                x1, y1 = text_canvas[i]
                x2, y2 = text_canvas[(i + 1) % len(text_canvas)]
                tid = self.canvas.create_line(x1, y1, x2, y2, fill='red',
                                              width=1, dash=(2, 2))
                self._draw_roi_text_indicator_ids.append(tid)
        # Handles + overlay buttons only visible in transform mode
        for hid in self._draw_roi_handle_ids.values():
            self.canvas.delete(hid)
        self._draw_roi_handle_ids = {}
        if self._draw_roi_rotate_line_id is not None:
            self.canvas.delete(self._draw_roi_rotate_line_id)
            self._draw_roi_rotate_line_id = None
        for ids in self._draw_roi_overlay_button_ids.values():
            id_list = ids if isinstance(ids, (list, tuple)) else (ids,)
            for bid in id_list:
                self.canvas.tag_unbind(bid, "<ButtonRelease-1>")
                self.canvas.delete(bid)
        self._draw_roi_overlay_button_ids = {}
        self._draw_roi_overlay_photos = {}
        if self._draw_roi_state != 'transform':
            return
        corners = self._obb_corners_image()
        top_cx, top_cy = self._image_to_canvas(*corners['n'])
        rot_cx, rot_cy = self._image_to_canvas(*corners['rotate'])
        self._draw_roi_rotate_line_id = self.canvas.create_line(
            top_cx, top_cy, rot_cx, rot_cy, fill='#4F4F4F', width=1)
        for role in self._DRAW_ROI_HANDLE_ROLES:
            ix, iy = corners[role]
            cx, cy = self._image_to_canvas(ix, iy)
            s = self._DRAW_ROI_HANDLE_SIZE
            if role == 'rotate':
                hid = self.canvas.create_oval(cx - s, cy - s, cx + s, cy + s,
                                              fill='#3F8FDF', outline='black')
            else:
                hid = self.canvas.create_rectangle(cx - s, cy - s, cx + s, cy + s,
                                                   fill='white', outline='black')
            self._draw_roi_handle_ids[role] = hid
        self._render_draw_roi_overlay_buttons(rot_cx, rot_cy)

    _DRAW_ROI_TEXT_BUTTON_HEIGHT = 32

    def _render_draw_roi_overlay_buttons(self, anchor_cx, anchor_cy):
        # Row of buttons above the rotate handle. Widths vary per item,
        # so compute cumulative x positions instead of a uniform stride.
        # Order: Done, Scan Page, Scan All, ←, ↑, ↓, →, Flip H, Flip V, Test, Cancel
        # 'kind' is either 'icon' (base64 png) or 'text' (canvas-drawn label).
        items = [
            ('done',      'icon', magic_select_done_button,             self._on_draw_roi_done,       86),
            ('scan_page', 'icon', magic_select_scan_page,               self._on_draw_roi_scan_page, 123),
            ('scan_all',  'icon', magic_select_scan_all,                self._on_draw_roi_scan_all,  113),
            ('nudge_l',   'icon', magic_select_left_button,             self._on_draw_roi_nudge_left,  34),
            ('nudge_u',   'icon', magic_select_up_button,               self._on_draw_roi_nudge_up,    34),
            ('nudge_d',   'icon', magic_select_down_button,             self._on_draw_roi_nudge_down,  34),
            ('nudge_r',   'icon', magic_select_right_button,            self._on_draw_roi_nudge_right, 34),
            ('flip_h',    'icon', magic_select_flip_horizontal_button,  self._on_draw_roi_flip_h,     67),
            ('flip_v',    'icon', magic_select_flip_vertical_button,    self._on_draw_roi_flip_v,     67),
            ('test',      'icon', magic_select_test_button,             self._on_draw_roi_test,       72),
            ('cancel',    'icon', magic_select_cancel_button,           self._on_draw_roi_cancel,     71),
        ]
        gap = 6
        total_w = sum(w for _, _, _, _, w in items) + gap * (len(items) - 1)
        start_x = int(anchor_cx - total_w / 2)
        y = int(anchor_cy - 44)
        x = start_x
        h = self._DRAW_ROI_TEXT_BUTTON_HEIGHT
        for name, kind, payload, cb, w in items:
            if kind == 'icon':
                photo = tk.PhotoImage(data=payload)
                self._draw_roi_overlay_photos[name] = photo  # keep ref
                bid = self.canvas.create_image(x, y, image=photo, anchor='nw')
                self.canvas.tag_bind(bid, "<ButtonRelease-1>", cb)
                self._draw_roi_overlay_button_ids[name] = [bid]
            else:
                rect_id = self.canvas.create_rectangle(
                    x, y, x + w, y + h,
                    fill='white', outline='#666666', width=1,
                )
                text_id = self.canvas.create_text(
                    x + w / 2, y + h / 2,
                    text=payload, fill='black',
                    font=('Segoe UI', 9, 'bold'),
                )
                self.canvas.tag_bind(rect_id, "<ButtonRelease-1>", cb)
                self.canvas.tag_bind(text_id, "<ButtonRelease-1>", cb)
                self._draw_roi_overlay_button_ids[name] = [rect_id, text_id]
            x += w + gap

    def _on_draw_roi_done(self, _):
        self.commit_draw_roi()

    def _on_draw_roi_scan_page(self, _):
        self.commit_draw_roi_scan_page()

    def _on_draw_roi_scan_all(self, _):
        self.commit_draw_roi_scan_all()

    def _on_draw_roi_cancel(self, _):
        self.cancel_draw_roi()

    def _on_draw_roi_flip_h(self, _):
        self.flip_draw_roi_horizontal()

    def _on_draw_roi_flip_v(self, _):
        self.flip_draw_roi_vertical()

    _DRAW_ROI_NUDGE_CANVAS_PX = 5

    def _nudge_draw_roi_center(self, dx_c, dy_c):
        # Zoom-independent nudge: fixed canvas-pixel step, converted to image coords.
        if getattr(self, '_draw_roi_state', 'idle') != 'transform':
            return
        scale = max(self.imscale, 1e-6)
        cx, cy = self._draw_roi_obb_center
        self._draw_roi_obb_center = (cx + dx_c / scale, cy + dy_c / scale)
        self._render_draw_roi_transform()

    def _on_draw_roi_nudge_left(self, _):
        self._nudge_draw_roi_center(-self._DRAW_ROI_NUDGE_CANVAS_PX, 0)

    def _on_draw_roi_nudge_right(self, _):
        self._nudge_draw_roi_center(self._DRAW_ROI_NUDGE_CANVAS_PX, 0)

    def _on_draw_roi_nudge_up(self, _):
        self._nudge_draw_roi_center(0, -self._DRAW_ROI_NUDGE_CANVAS_PX)

    def _on_draw_roi_nudge_down(self, _):
        self._nudge_draw_roi_center(0, self._DRAW_ROI_NUDGE_CANVAS_PX)

    def _on_draw_roi_test(self, _):
        self.test_draw_roi()

    # ---- Transform actions ---------------------------------------------

    def _begin_draw_roi_transform_drag(self, event, curX, curY):
        # Hit-test handles first
        role = self._hit_test_draw_roi_handle(curX, curY)
        if role is None:
            # Inside polygon -> move
            if self._point_inside_transformed_polygon(curX, curY):
                role = 'move'
            else:
                return
        self._draw_roi_active_handle = role
        self._draw_roi_drag_snapshot = {
            'cursor': (curX, curY),
            'center': self._draw_roi_obb_center,
            'angle': self._draw_roi_angle,
            'scale': self._draw_roi_scale,
            'size': self._draw_roi_obb_size,
        }
    def _hit_test_draw_roi_handle(self, curX, curY):
        halo = self._DRAW_ROI_HIT_HALO
        for role, hid in self._draw_roi_handle_ids.items():
            hx0, hy0, hx1, hy1 = self.canvas.coords(hid)
            if (hx0 - halo) <= curX <= (hx1 + halo) and (hy0 - halo) <= curY <= (hy1 + halo):
                return role
        return None

    def _point_inside_transformed_polygon(self, curX, curY):
        img_x, img_y = self._canvas_to_image(curX, curY)
        poly = self._current_transformed_polygon()
        # Ray casting
        inside = False
        n = len(poly)
        j = n - 1
        for i in range(n):
            xi, yi = poly[i]
            xj, yj = poly[j]
            if ((yi > img_y) != (yj > img_y)):
                x_intersect = (xj - xi) * (img_y - yi) / (yj - yi + 1e-12) + xi
                if img_x < x_intersect:
                    inside = not inside
            j = i
        return inside

    def _apply_draw_roi_move(self, curX, curY):
        snap = self._draw_roi_drag_snapshot
        if not snap:
            return
        start_x, start_y = snap['cursor']
        dx_c = curX - start_x
        dy_c = curY - start_y
        dx_img = dx_c / max(self.imscale, 1e-6)
        dy_img = dy_c / max(self.imscale, 1e-6)
        base_cx, base_cy = snap['center']
        self._draw_roi_obb_center = (base_cx + dx_img, base_cy + dy_img)

    def _apply_draw_roi_rotate(self, curX, curY, snap=False):
        snap_state = self._draw_roi_drag_snapshot
        if not snap_state:
            return
        cx, cy = self._image_to_canvas(*snap_state['center'])
        start_x, start_y = snap_state['cursor']
        base_angle = snap_state['angle']
        a0 = math.degrees(math.atan2(start_y - cy, start_x - cx))
        a1 = math.degrees(math.atan2(curY - cy, curX - cx))
        new_angle = base_angle + (a1 - a0)
        if snap:
            step = self._DRAW_ROI_SNAP_STEP_DEG
            new_angle = round(new_angle / step) * step
        # Normalise to [-180, 180]
        new_angle = ((new_angle + 180) % 360) - 180
        self._draw_roi_angle = new_angle

    def _apply_draw_roi_resize(self, role, curX, curY):
        """ Uniform scale from a corner handle. `role` is nw/ne/se/sw. """
        snap = self._draw_roi_drag_snapshot
        if not snap:
            return
        base_cx, base_cy = snap['center']
        base_scale = snap['scale']
        base_w, base_h = snap['size']
        # Convert cursor position to OBB-local coords using the current angle.
        theta = math.radians(self._draw_roi_angle)
        cs = math.cos(-theta)
        sn = math.sin(-theta)
        img_x, img_y = self._canvas_to_image(curX, curY)
        dx = img_x - base_cx
        dy = img_y - base_cy
        lx = dx * cs - dy * sn
        ly = dx * sn + dy * cs
        # Base corner distance from centre gives the reference length; the new
        # distance sets the uniform scale factor.
        sign_x = {'nw': -1, 'ne': 1, 'se': 1, 'sw': -1}[role]
        sign_y = {'nw': -1, 'ne': -1, 'se': 1, 'sw': 1}[role]
        base_half_w = base_w * base_scale / 2.0
        base_half_h = base_h * base_scale / 2.0
        base_diag = math.hypot(base_half_w, base_half_h)
        cur_diag = math.hypot(sign_x * lx, sign_y * ly)
        if base_diag < 1e-6:
            return
        min_scale = 0.05
        max_scale = 20.0
        new_scale = max(min_scale, min(max_scale, base_scale * (cur_diag / base_diag)))
        self._draw_roi_scale = new_scale

    # ---- Public transform commands (menu + overlay button hooks) --------

    def flip_draw_roi_horizontal(self):
        if getattr(self, '_draw_roi_state', 'idle') != 'transform':
            return
        self._draw_roi_flip_h = not self._draw_roi_flip_h
        self._render_draw_roi_transform()

    def flip_draw_roi_vertical(self):
        if getattr(self, '_draw_roi_state', 'idle') != 'transform':
            return
        self._draw_roi_flip_v = not self._draw_roi_flip_v
        self._render_draw_roi_transform()

    def commit_draw_roi(self):
        """ Persist the drawn ROI as a single control module at the transformed
        location. This is the "Done" action: it creates one linked-graphic
        instance and stops — no additional scanning is triggered. Use
        `commit_draw_roi_scan_page` or `commit_draw_roi_scan_all` to also
        register a template variant and scan for similar instances. """
        final_text_rois = self._current_transformed_text_rois()
        wire_kwargs = self._collect_selection_wire_kwargs()
        persisted = self._persist_manual_placement(
            text_roi_polygons=final_text_rois,
            wire_kwargs=wire_kwargs,
        )
        if persisted is None:
            return
        result, _roi_uid, _final_polygon = persisted
        self._finalise_draw_roi_after_commit()
        if result is None:
            messagebox.showwarning('Draw ROI',
                                   'Placement overlaps an existing linked graphic and was skipped.')

    def _commit_draw_roi_and_scan(self, scan_scope):
        """ Persist the drawn ROI and then run a scan.

        `scan_scope`:
          - 'all'  : register a new template variant and run a document-wide
                     scan (`scan_from_manual_placement` with page_index=None).
          - 'page' : same pipeline as 'all' but restricted to the current
                     page (page_index=self.pno). This intentionally does NOT
                     use `test_from_manual_placement`, which would swap the
                     view over to the Test-On-Page interface.
        """
        final_text_rois = self._current_transformed_text_rois()
        wire_kwargs = self._collect_selection_wire_kwargs()
        persisted = self._persist_manual_placement(
            text_roi_polygons=final_text_rois,
            wire_kwargs=wire_kwargs,
        )
        if persisted is None:
            return
        result, roi_uid, final_polygon = persisted
        try:
            template_mask = self._build_template_mask_from_polygon(
                final_polygon, text_polygons=final_text_rois)
            page_index = None if scan_scope == 'all' else self.pno
            self._draw_roi_source_cell_ref.scan_from_manual_placement(
                roi_uid=roi_uid,
                pno=self.pno,
                template_mask=template_mask,
                scale_factor=float(self._committed_scale),
                page_index=page_index,
                document_type=self.file_type,
                wire_kwargs=wire_kwargs,
            )
        except Exception as error:
            logging.exception("Draw ROI: %s scan failed: %s", scan_scope, error)
            messagebox.showerror('Draw ROI',
                                 'Placement was saved but the scan could not start: {}'.format(error))
        self._finalise_draw_roi_after_commit()
        if result is None:
            messagebox.showwarning('Draw ROI',
                                   'Placement overlaps an existing linked graphic and was skipped.')

    def commit_draw_roi_scan_all(self):
        """ Persist + register as template variant + run a document-wide scan
        (equivalent to the historical "Done" behaviour before Done became
        persist-only). """
        self._commit_draw_roi_and_scan('all')

    def commit_draw_roi_scan_page(self):
        """ Persist + run a current-page scan for the source template. """
        self._commit_draw_roi_and_scan('page')

    def test_draw_roi(self):
        """ Run a page-level test scan for the source template while keeping the
        Draw ROI overlay alive.

        Test is a preview: it must NOT persist the placement and must NOT tear
        down the transform interface, so the user can keep adjusting the
        placement (or click Done / Cancel) after previewing the scan. Only
        Done commits the placement to the DB.

        The underlying `test_from_manual_placement` receives the transformed
        polygon + text-carved template mask so the preview uses a template
        freshly cropped from the destination page at the drawn placement
        (matching what `commit_draw_roi_scan_page` / `..._scan_all` do),
        instead of the pristine source template.
        """
        if getattr(self, '_draw_roi_state', 'idle') != 'transform':
            return
        source_cell = self._draw_roi_source_cell
        if source_cell is None:
            return
        final_polygon = self._current_transformed_polygon()
        if len(final_polygon) < 3:
            return
        final_text_rois = self._current_transformed_text_rois()
        try:
            template_mask = self._build_template_mask_from_polygon(
                final_polygon, text_polygons=final_text_rois)
        except Exception as error:
            logging.exception("Draw ROI: failed to build test template mask: %s", error)
            template_mask = None
        try:
            source_cell.test_from_manual_placement(
                roi_uid=None,
                pno=self.pno,
                template_mask=template_mask,
                document_type=self.file_type,
                wire_kwargs=self._collect_selection_wire_kwargs(),
                polygon=final_polygon,
            )
        except Exception as error:
            logging.exception("Draw ROI: test_from_manual_placement failed: %s", error)
            messagebox.showerror('Draw ROI',
                                 'Failed to run the test: {}'.format(error))

    def _collect_selection_wire_kwargs(self):
        """ Return the same kwargs the singleton selection subscription would
        propagate to a cell. Used so scan / test can wire the source cell's
        linked-graphic view even when the last-subscribed cell was a different
        one. Mirrors `__send_selection_callback`. """
        return dict(
            roi_select_func=self.get_selected_roi,
            text_roi_selected_func=self.setup_text_roi,
            move_to_roi_func=self.move_to_roi,
            clear_shown_text_roi_list=self.__clear_shown_text_roi_list,
            refresh_roi=self.__refresh_rois,
            draw_connecting_lines=self.__draw_connecting_lines,
            get_full_page_image=self.__get_full_page_image,
            get_text_on_page_func=self.__get_text_on_page,
            draw_roi_trigger_func=self.__draw_roi_trigger,
            document_type=self.file_type,
            send_document_selected_text_func=self.__document_selected_text,
        )

    def _persist_manual_placement(self, text_roi_polygons=None, wire_kwargs=None):
        """ Shared body used by both Done and Test. Instantiates the linked-graphic
        copy at the transformed location and returns ``(result, roi_uid, polygon)``,
        or ``None`` if the tool is not currently in transform mode. """
        if getattr(self, '_draw_roi_state', 'idle') != 'transform':
            return None
        source_cell = self._draw_roi_source_cell
        if source_cell is None:
            self.cancel_draw_roi()
            return None
        final_polygon = self._current_transformed_polygon()
        if len(final_polygon) < 3:
            self.cancel_draw_roi()
            return None
        xs = [p[0] for p in final_polygon]
        ys = [p[1] for p in final_polygon]
        roi_bbox = (min(xs), min(ys), max(xs), max(ys))
        # Snap the visual angle to the nearest 90 for Template_Rotate.
        angle = ((round(self._draw_roi_angle / 90.0) * 90) % 360 + 360) % 360
        rotation_map = {
            0:   Template_Rotate.NONE,
            90:  Template_Rotate.CW_90,
            180: Template_Rotate.CW_180,
            270: Template_Rotate.CW_270,
        }
        rotation = rotation_map.get(angle, Template_Rotate.NONE)
        if self._draw_roi_flip_h and self._draw_roi_flip_v:
            flip = Template_Flip.VERTICALLY_HORIZONTALLY
        elif self._draw_roi_flip_h:
            flip = Template_Flip.HORIZONTALLY
        elif self._draw_roi_flip_v:
            flip = Template_Flip.VERTICALLY
        else:
            flip = Template_Flip.NONE
        user_scale = float(self._draw_roi_scale)
        # `create_copy` interprets `template_to_match_ratio` as a multiplier on
        # the source *template* polygon. Our seed polygon was the placed
        # instance (template x seed_ratio), so we compose them here so the
        # persisted polygon matches the drawn ghost.
        seed_ratio = float(getattr(self, '_draw_roi_template_scale_at_seed', 1.0) or 1.0)
        effective_scale = user_scale * seed_ratio
        try:
            result = source_cell.instantiate_manual_placement(
                dest_path=self.path,
                dest_pno=self.pno,
                roi_bbox=roi_bbox,
                rotation=rotation,
                flip=flip,
                scale=effective_scale,
                text_roi_polygons=text_roi_polygons,
                wire_kwargs=wire_kwargs,
            )
        except Exception as error:
            logging.exception("Draw ROI: instantiate_manual_placement failed: %s", error)
            messagebox.showerror('Draw ROI', 'Failed to place the linked graphic: {}'.format(error))
            return None
        # Extract the persisted roi_uid so scan / test can reference it.
        roi_uid = None
        if isinstance(result, dict):
            primary = result.get('primary_linked_graphic') or {}
            roi_uid = primary.get('roi_uid') or result.get('id')
        # Preserve the source cell + committed scale for the follow-up scan / test
        # (self._draw_roi_source_cell is cleared by _finalise_draw_roi_after_commit).
        self._draw_roi_source_cell_ref = source_cell
        self._committed_scale = effective_scale
        return result, roi_uid, final_polygon

    def _finalise_draw_roi_after_commit(self):
        """ Clear transient visuals + state and refresh ROIs. Called from Done / Test. """
        self._clear_draw_roi_visuals()
        self._init_draw_roi_state()
        self.menu.enable_flip_horizontal(False)
        self.menu.enable_flip_vertical(False)
        # Refresh the ROI display so the newly placed graphic appears.
        try:
            self.__refresh_rois()
        except Exception:
            try:
                self.refresh_rois()
            except Exception:
                pass
        self._refresh_tool_list_after_placement()
        self._notify_draw_roi_button(False)

    _DRAW_ROI_LIST_REFRESH_POLL_MS = 250
    _DRAW_ROI_LIST_REFRESH_MAX_POLLS = 20

    def _refresh_tool_list_after_placement(self, attempt=0):
        """ Rebuild the Control Modules list once the threaded control-module write
        has landed, so a manual placement shows up without the user pressing the
        list's Refresh button. `save_bulk_control_modules` writes on a background
        thread, hence the poll rather than a straight call. """
        if self.__refresh_tool_canvas_callback is None:
            return
        try:
            written = self.__db.check_if_save_bulk_control_modules_threads_finished()
        except Exception:
            written = True
        if not written and attempt < self._DRAW_ROI_LIST_REFRESH_MAX_POLLS:
            self.canvas.after(self._DRAW_ROI_LIST_REFRESH_POLL_MS,
                              lambda: self._refresh_tool_list_after_placement(attempt + 1))
            return
        try:
            self.__refresh_tool_canvas_callback()
        except Exception:
            logging.exception("Draw ROI: failed to refresh the control module list")

    def _build_template_mask_from_polygon(self, polygon, text_polygons=None):
        """ Rasterise the placed polygon into a binary mask (uint8, 0/255) sized to
        the polygon's bounding box in destination image coords. `add_graphic_link`
        will resize it to match the actual image crop.

        When `text_polygons` is provided (list of polygons in the same image
        coord space as `polygon`), the interiors of those polygons are carved
        out of the mask (set to 0) so the scanner ignores text regions when
        matching this variant — mirroring how the source template's
        `template_and_text_mask` is built via `__create_template_and_text_mask`.
        Without this carving, a new variant added by Draw ROI would include
        text pixels in template matching, degrading scan quality.
        """
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        min_x = int(math.floor(min(xs)))
        min_y = int(math.floor(min(ys)))
        max_x = int(math.ceil(max(xs)))
        max_y = int(math.ceil(max(ys)))
        w = max(1, max_x - min_x)
        h = max(1, max_y - min_y)
        mask = np.zeros((h, w), dtype=np.uint8)
        rel_pts = np.array(
            [[int(round(x - min_x)), int(round(y - min_y))] for x, y in polygon],
            dtype=np.int32,
        )
        cv2.fillPoly(mask, [rel_pts], 255)
        # Carve out text ROI regions so template matching ignores text pixels
        # (parity with the source template's text-carved mask).
        if text_polygons:
            for text_poly in text_polygons:
                if not text_poly or len(text_poly) < 3:
                    continue
                text_pts = np.array(
                    [[int(round(x - min_x)), int(round(y - min_y))] for x, y in text_poly],
                    dtype=np.int32,
                )
                cv2.fillPoly(mask, [text_pts], 0)
        return mask

    def cancel_draw_roi(self):
        state = getattr(self, '_draw_roi_state', 'idle')
        if state == 'idle':
            return
        self._clear_draw_roi_visuals()
        self._init_draw_roi_state()
        self.menu.enable_flip_horizontal(False)
        self.menu.enable_flip_vertical(False)
        self._notify_draw_roi_button(False)

    def __refresh_draw_roi_overlay(self):
        """ Re-render the Draw ROI transform overlay when the image zoom / position changes. """
        if getattr(self, '_draw_roi_state', 'idle') != 'transform':
            return
        self._render_draw_roi_transform()

    def start_auto_selection(self):
        try:
            x0, y0, x1, y1 = self.canvas.coords(self.auto_selection_rectangle_id)
        except:
            return
        
        bbox = self.canvas.coords(self.container)  # get image area
        x0 = (x0 - bbox[0])  # get real (x,y) on the image without zoom
        y0 = (y0 - bbox[1]) 
        x1 = (x1 - bbox[0]) 
        y1 = (y1 - bbox[1]) 

        segmentation_region = (int(x0 / self.imscale) , int(y0 / self.imscale), int(x1 / self.imscale) , int(y1 / self.imscale))
        image = self.image.crop(segmentation_region)
        self.segmentation_model.set_image_asynch(np.array(image), segmentation_region)

        self.draw_auto_selection_overlay(x0, y0, x1, y1, bbox)


    def draw_auto_selection_overlay(self, x0r, y0r, x1r, y1r, bbox):

        self.canvas.itemconfig(self.auto_selection_rectangle_id, dash=(4, 4))

        box_canvas = (self.canvas.canvasx(0),  # get visible area of the canvas
                      self.canvas.canvasy(0),
                      self.canvas.canvasx(self.canvas.winfo_width()),
                      self.canvas.canvasy(self.canvas.winfo_height()))
        x1 = max(box_canvas[0] - bbox[0], 0)  # get coordinates (x1,y1,x2,y2) of the image tile
        y1 = max(box_canvas[1] - bbox[1], 0)
        x2 = min(box_canvas[2], bbox[2]) - bbox[0]
        y2 = min(box_canvas[3], bbox[3]) - bbox[1]

        # Draw the overlay image
        overlay_image = Image.new('RGBA', (int(x2-x1), int(y2-y1)), (0,0,0,128))
        drawing = ImageDraw.Draw(overlay_image)
        drawing.rectangle((x0r-x1,y0r-y1,x1r-x1,y1r-y1), fill=(0, 0, 0, 0))
        
        # Resize the image to fit the canvas
        overlay_image = overlay_image.resize((int(x2 - x1), int(y2 - y1)), Image.LANCZOS)

        self.auto_selection_overlay_image = ImageTk.PhotoImage(overlay_image)
        if self.auto_selection_overlay_id:
            self.canvas.delete(self.auto_selection_overlay_id)

        box_img_int = tuple(map(int, bbox))  # convert to integer or it will not work properly
        self.auto_selection_overlay_id = self.canvas.create_image(max(box_canvas[0], box_img_int[0]),
                                               max(box_canvas[1], box_img_int[1]), image=self.auto_selection_overlay_image, anchor='nw')

        # Draw the done button
        self.magic_select_done_button = tk.PhotoImage(data=magic_select_done_button)
        self.auto_selection_done_button_id = self.canvas.create_image(bbox[0] + x0r, bbox[1] + y0r - 40, image=self.magic_select_done_button, anchor='nw')
        self.canvas.tag_bind(self.auto_selection_done_button_id, "<ButtonRelease-1>", self.done_auto_selection)


        # Draw the reset button
        self.magic_select_reset_button = tk.PhotoImage(data=magic_select_reset_button)
        self.auto_selection_reset_button_id = self.canvas.create_image(bbox[0] + x0r + 90, bbox[1] + y0r - 40, image=self.magic_select_reset_button, anchor='nw')
        self.canvas.tag_bind(self.auto_selection_reset_button_id, "<ButtonRelease-1>", self.reset_auto_selection)


        # Draw the cancel button
        self.magic_select_cancel_button = tk.PhotoImage(data=magic_select_cancel_button)
        self.auto_selection_cancel_button_id = self.canvas.create_image(bbox[0] + x0r + 180 , bbox[1] + y0r - 40, image=self.magic_select_cancel_button, anchor='nw')
        self.canvas.tag_bind(self.auto_selection_cancel_button_id, "<ButtonRelease-1>", self.cancel_auto_selection)
        
        self.is_showing_auto_selection_overlay = True


    def reset_auto_selection(self, _):
        """ Reset the auto selection """
        for id in self.auto_selection_polygon_ids:
            self.canvas.delete(id)
        self.segmentation_model.reset_points()
        for point in self.auto_selection_points:
            self.canvas.delete(point[0])
        self.auto_selection_points = []
        self.auto_selection_polygons = []
        

    def done_auto_selection(self, _):
        """ Finish the auto selection and save the polygon """
        for id in self.auto_selection_polygon_ids:
            self.canvas.delete(id)
        for point in self.auto_selection_points:
            self.canvas.delete(point[0])
        self.is_showing_auto_selection_overlay = False
        
        self.draw_polygon(self.auto_selection_polygons[0], self.color_roi , self.tag_roi, self.roi_list[self.pno])
        self.save_page_roi()
        self.close_auto_selection()
        
        
    def cancel_auto_selection(self, _):
        """ Cancel the auto selection """
        self.close_auto_selection()


    def close_auto_selection(self):
        self.canvas.delete(self.auto_selection_rectangle_id)
        self.canvas.delete(self.auto_selection_overlay_id)
        self.canvas.delete(self.auto_selection_done_button_id)
        self.canvas.delete(self.auto_selection_reset_button_id)
        self.canvas.delete(self.auto_selection_cancel_button_id)
        for id in self.auto_selection_polygon_ids:
            self.canvas.delete(id)
        for point in self.auto_selection_points:
            self.canvas.delete(point[0])
        self.auto_selection_points = []
        self.auto_selection_polygons = []
        self.is_showing_auto_selection_overlay = False
        self.segmentation_model.reset()


    
    def is_valid_auto_selection_click(self, x, y):
        """ Check if the click is with the auto selection rectangle, 
        but return True if the overlay is not showing """
        if not self.is_showing_auto_selection_overlay:
            return True
        x0, y0, x1, y1 = self.canvas.coords(self.auto_selection_rectangle_id)
        return x0 <= x <= x1 and y0 <= y <= y1


    
    def draw_auto_selection_polygon(self):
        self.auto_selection_polygons = self.segmentation_model.get_polygons()
        self.canvas.delete(self.tag_auto_select_polygon)
        self.canvas.delete(self.auto_selection_polygon_tag_id)
        self.canvas.update_idletasks()
        for id in self.auto_selection_polygon_ids:
            self.canvas.delete(id)
        bbox = self.canvas.coords(self.container)  # get image area
        for polygon in self.auto_selection_polygons:
            vertices = list(map((lambda i: (i[0] * self.imscale + bbox[0],
                                        i[1] * self.imscale + bbox[1])), polygon))
            id = self.canvas.create_polygon(vertices, fill=self.color_hole['point'], stipple=self.color_hole['stipple']
                                            , outline='red', width=2
                                            , tags=(self.tag_auto_select_polygon
                                            , self.auto_selection_polygon_tag_id))
            # Move points to the front
            for point in self.auto_selection_points:
                self.canvas.tag_raise(point[0])

            self.auto_selection_polygon_ids.append(id)
            
            


    def add_auto_select_point(self, x, y, is_positive=True):
        self.canvas.config(cursor="wait")
        color = f'#{0:02x}{255:02x}{0:02x}' if is_positive else f'#{255:02x}{0:02x}{0:02x}'
        radius = 4 * self.imscale
        point = self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=color, outline=color)
        bbox = self.canvas.coords(self.container)  # get image area
        x = (x - bbox[0]) / self.imscale # get real (x,y) on the image without zoom
        y = (y - bbox[1]) / self.imscale
        self.auto_selection_points.append((point, x, y, is_positive))
        try:
            self.segmentation_model.add_point((int(x),int(y)), is_positive)
        except Exception as e:
            messagebox.showerror("Error adding point", e)

        def check_auto_selection_polygon():
            if self.segmentation_model.is_done_processing():
                self.draw_auto_selection_polygon()
                self.canvas.config(cursor="")
            else:
                self.canvas.after(100, check_auto_selection_polygon)

        self.canvas.after(100, check_auto_selection_polygon)
        

        print(f"Added point at ({x}, {y}) that is {'positive' if is_positive else 'negative'}")



    def delete_auto_selection_point(self, point):
        self.canvas.delete(point[0])
        self.auto_selection_points.remove(point)
        self.segmentation_model.remove_point((point[1], point[2]), 1)
        print(f"Deleted point at ({point[1]}, {point[2]}) that is {'positive' if point[3] else 'negative'}")


    def add_auto_select_rectangle(self, x1, y1, x2, y2):

        # Convert to top-left and bottom-right coordinates if not already
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        # self.sam2.set_box(((x0, y0), (x1, y1)), label_id)
        print(f"Added box at ({x0}, {y0}) to ({x1}, {y1}) with label '{self.selected_label}'")



    def is_inside_polygon(self, x, y):
        if not self.auto_selection_polygons:
            return False
        
        bbox = self.canvas.coords(self.container)  # get image area
        
        x = (x - bbox[0]) / self.imscale # get real (x,y) on the image without zoom
        y = (y - bbox[1]) / self.imscale
        
        for polygon in self.auto_selection_polygons:
        
            n = len(polygon)
            inside = False
            
            # Store the first point as the last point to close the polygon
            p1x, p1y = polygon[0]
            
            for i in range(n + 1):
                p2x, p2y = polygon[i % n]
                
                # Check if point is on horizontal edge
                if y == p1y and y == p2y:
                    if min(p1x, p2x) <= x <= max(p1x, p2x):
                        return True
                        
                # Check if point is on vertical edge
                if x == p1x and x == p2x:
                    if min(p1y, p2y) <= y <= max(p1y, p2y):
                        return True
                
                # Ray casting algorithm
                if (y > min(p1y, p2y) and y <= max(p1y, p2y) and x <= max(p1x, p2x)):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        
                        # Check if point is on non-horizontal edge
                        if p1x == p2x or x <= xinters:
                            inside = not inside
                
                p1x, p1y = p2x, p2y
            
            if inside:
                return True
            
        return False
    


    
    def is_close_to_point(self, x, y, distance_thres = 10):
        # Check if the point is close to an existing point for deletion
        closest_point = None
        closest_distance = float('inf')

        for point in self.auto_selection_points:
            _, px, py, _ = point
            distance = (x - px) ** 2 + (y - py) ** 2
            if distance < closest_distance:
                closest_distance = distance
                closest_point = point

        is_close = closest_distance < distance_thres ** 2

        return is_close, closest_point


    def auto_selection_motion(self, event):
        
        self.__on_text_move_press(event)

        curX, curY = ( self.canvas.canvasx(event.x),  self.canvas.canvasy(event.y))

        if not self.is_valid_auto_selection_click(curX, curY):
            return

        if self.auto_selection_rectangle_id and not self.is_showing_auto_selection_overlay:

            # expand rectangle as you drag the mouse

            bbox = self.canvas.coords(self.container)  # get image area
            if (bbox[0] <= curX < bbox[2] and bbox[1] <= curY < bbox[3]):
                self.canvas.coords(self.auto_selection_rectangle_id, self.auto_selection_press_pos[0], self.auto_selection_press_pos[1], curX, curY)
                self.canvas.itemconfigure(self.auto_selection_rectangle_id, dash='')  # set solid line
            else:
                self.canvas.coords(self.auto_selection_rectangle_id, self.auto_selection_press_pos[0], self.start_rect_highlight_y, curX, curY)
                self.canvas.itemconfigure(self.auto_selection_rectangle_id, dash=self.dash)  # set dashed line

        


    def set_auto_select_point_box(self,event):
        '''Sets the point to auto select'''
        
        # To remove focus on other elements
        self.canvas.focus_set() 

        curX, curY = ( self.canvas.canvasx(event.x),  self.canvas.canvasy(event.y))
        if not self.is_valid_auto_selection_click(curX, curY):
            return

        #self.__selecting_text_rect = None

        if self.__selecting_text:
            self.__select_text(curX, curY) 
            return 
        else: 
            if self.__clear_selected_shown_text:
                self.__clear_selected_shown_text()
        
        if self.hold_menu2:  # popup menu was opened
            self.hold_menu2 = False
            self.motion(event)  # motion event for popup menu
            return

        self.unselect_poly()
        self.unselect_rect()
        self.__send_selection_callback(False)
        self.__get_object_selection()

        if self.highlighted_poly or self.highlighted_rect:
            self.__set_selected_roi()
            return
            

        self.motion(event)  # generate motion event. It's needed for menu bar, bug otherwise!
 
        bbox = self.canvas.coords(self.container)  # get image area
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        if (bbox[0] <= x < bbox[2] and bbox[1] <= y < bbox[3]) and not self.is_showing_auto_selection_overlay:

            # save mouse drag start position
            self.auto_selection_press_pos = (x,y)

            self.auto_selection_rectangle_id = self.canvas.create_rectangle(x, y, x, y, fill="",width=self.width_line,
                                                dash=(2, 2), outline='cyan')



    def ___create_text_select_rectangle(self, X1, Y1, X2, Y2, **kwargs):
        x1 = int(X1)
        y1 = int(Y1)
        x2 = int(X2)
        y2 = int(Y2)
        image = Image.new('RGBA', (abs(x2-x1), abs(y2-y1)), (0,102,204,127))
        scan_image = ImageTk.PhotoImage(image)
        return scan_image, self.canvas.create_image(min([x1,x2]), min([y1,y2]), image=scan_image, anchor='nw')
    

    def refresh_rois(self, _ = None):
        self.__refresh_rois()


    def get_selected_roi(self, pdf_zoom_scale = 2,selected_roi=None,pno=0,ocr_image=False):
        """ Passes the selected region to the linked Graphic object """
        
        if selected_roi is None:
            pno = self.pno
            selected_roi = ''

            if self.selected_poly:
                selected_roi = self.selected_poly[0]

            if self.selected_rect:
                selected_roi = self.selected_rect[0]
        
        self.__refresh_rois(with_text=False)
        
        if pno >= len(self.roi_list) or selected_roi not in self.roi_list[pno]:
            return None, None, pno, self.path, None, None, None

        roi = self.roi_list[pno][selected_roi]

        image = self.__get_sub_full_page_image(roi,pdf_zoom_scale,ocr_image)

        return selected_roi, roi, pno, self.path, self.full_page, image, self.text_in_page
        
    def __get_sub_full_page_image(self,roi, pdf_zoom_scale,ocr_image=False):

        if self.file_type == Database.IMAGE:
            zoom_scale = 1
        else:
            zoom_scale = pdf_zoom_scale

        minX = int(min(l[0] for l in roi) * zoom_scale)
        minY = int(min(l[1] for l in roi) * zoom_scale)
        maxX = int(max(l[0] for l in roi) * zoom_scale)
        maxY = int(max(l[1] for l in roi) * zoom_scale)

        if self.file_type == Database.IMAGE:
            self.full_page = self.image
            return self.image.crop((minX,minY,maxX,maxY))
            

        if ocr_image:
            image_bytes, _= self.get_ocr_page(minX,minY,maxX,maxY,pdf_zoom_scale)
        else:
            image_bytes, _= self.get_page(minX,minY,maxX,maxY,pdf_zoom_scale)
        return Image.open(io.BytesIO(image_bytes))
        


    def setup_text_roi(self, text_location_dict, linked_graphic_name):
        """ Sets up a given as a text based text highlightable roi"""

        # Clear current text roi rects
        self.__clear_shown_text_roi_list(linked_graphic_name)

        rect_list = []
        ocr_text_list = []
        text_tooltip_list = []

        # Refreshed once up front so a just-linked text roi is picked up and the roi
        # redraw cannot restack itself over char boxes drawn in an earlier iteration.
        self.__refresh_rois(with_text=False)
        page_rois = self.roi_list[self.pno] if self.pno < len(self.roi_list) else None

        try:
            for roi_id, text_location in text_location_dict.items():
                if (text_location.get('pno', self.pno) != self.pno
                        or text_location.get('path', self.path) != self.path):
                    continue

                if not page_rois or roi_id not in page_rois:
                    logging.warning(f"Skipping text roi {roi_id} in text_location_dict: not on page {self.pno} of {self.path}")
                    continue

                roi = page_rois[roi_id]

                if not 'vertical_direction' in text_location:
                    text_horizontal = True
                    text = self.__create_horizontal_text_roi(linked_graphic_name, rect_list, text_tooltip_list, roi_id, text_location)
                else:
                    text_horizontal = False
                    text = self.__create_vertical_text_roi(linked_graphic_name, rect_list, text_tooltip_list, roi_id, text_location)

                minX = min(l[0] for l in roi)
                maxX = max(l[0] for l in roi)
                minY = min(l[1] for l in roi)
                maxY = max(l[1] for l in roi)


                if text_horizontal:
                    text_height = maxY-minY
                else:
                    text_height = maxX-minX

                bbox = self.canvas.coords(self.container)  # get image area

                text_id = self.canvas.create_text(minX * self.imscale + bbox[0], minY * self.imscale + bbox[1], text=text,anchor=tk.SW,fill='red')

                self.canvas.itemconfigure(text_id, font=("Arial", int(text_height/3 * self.imscale)))

                ocr_text_list.append((text_id,text_height,text_horizontal))
        finally:
            # Always tracked, otherwise a partial draw leaves canvas items that can never be cleared.
            self.__shown_text_roi_rect_lists[linked_graphic_name] = rect_list
            self.__shown_ocr_text_lists[linked_graphic_name] = ocr_text_list
            self.__text_tooltips_lists[linked_graphic_name] = text_tooltip_list
            self.__text_location_dicts[linked_graphic_name] = text_location_dict


    def __create_horizontal_text_roi(self, linked_graphic_name, rect_list, text_tooltip_list, roi_id, text_location):
        i = 0
        top, bottom = self.__get_top_and_bottom_of_text_line( text_location['text_dict'])
        text = ""

        for char in text_location['text_dict']:
            bbox1 = char['bbox']
            vertices_unscaled = [(bbox1[0], top), (bbox1[2], top), (bbox1[2], bottom), (bbox1[0], bottom)]
                
            bbox2 = self.canvas.coords(self.container)  # get image area
            vertices = list(map((lambda i: (i[0] * self.imscale + bbox2[0],
                                            i[1] * self.imscale + bbox2[1])), vertices_unscaled))
                
            
            rect = self.canvas.create_polygon(vertices, fill='', width=1,outline="red", tags=(roi_id + '_text_roi' , 'text_roi', char['c'], str(i),linked_graphic_name, True))
            rect_list.append(rect)
            tooltip = CanvasTooltip(self.canvas, rect, text=char['c'])
            text_tooltip_list.append(tooltip)
            i = i + 1
            text = text + char['c']
        return text


    def __create_vertical_text_roi(self, linked_graphic_name, rect_list, text_tooltip_list, roi_id, text_location):
        i = 0
        left, right = self.__get_left_and_right_of_text_line( text_location['text_dict'])
        text = ""

        for char in text_location['text_dict']:
            bbox1 = char['bbox']
            vertices_unscaled = [(left, bbox1[1]), (left, bbox1[3]), (right, bbox1[3]), (right , bbox1[1])]
                
            bbox2 = self.canvas.coords(self.container)  # get image area
            vertices = list(map((lambda i: (i[0] * self.imscale + bbox2[0],
                                            i[1] * self.imscale + bbox2[1])), vertices_unscaled))
                
            tags=(roi_id + '_text_roi' , 'text_roi', char['c'], str(i),linked_graphic_name, False, bbox1[0], bbox1[1])
            rect = self.canvas.create_polygon(vertices, fill='', width=1,outline="red", tags=tags)
            rect_list.append(rect)
            tooltip = CanvasTooltip(self.canvas, rect, text=char['c'])
            text_tooltip_list.append(tooltip)
            i = i + 1
            text = text + char['c']
        return text


    
    def __is_horizontal_text(self, text_location):
            vertical_center = None
            for char in text_location['text_dict']:
                bbox = char['bbox']
                if vertical_center is not None:
                    if bbox[1]< vertical_center < bbox[3] or bbox[3]< vertical_center < bbox[1]:
                        return True
                    else:
                        return False
                vertical_center = (bbox[1] + bbox[3])/2



    def __get_top_and_bottom_of_text_line(self, text):

        top = sys.maxsize
        bottom = -1

        for char in text:

            bbox1 = char['bbox']

            if bbox1[3] > bbox1[1]:
                mBottom = bbox1[3]
                mTop = bbox1[1]
            else:
                mBottom = bbox1[1]
                mTop = bbox1[3]

            if mTop<top:
                top=mTop

            if mBottom>bottom:
                bottom = mBottom
            
        return top, bottom

    
    def __get_left_and_right_of_text_line(self, text):

        left = sys.maxsize
        right = -1

        for char in text:

            bbox1 = char['bbox']

            if bbox1[2] > bbox1[0]:
                mRight = bbox1[2]
                mLeft = bbox1[0]
            else:
                mRight = bbox1[0]
                mLeft = bbox1[2]

            if mLeft<left:
                left=mLeft

            if mRight>right:
                right = mRight
            
        return left, right


    def __clear_shown_text_roi_list(self, linked_graphic_name=None, forget=True):

        # forget=False keeps the cached text locations so __refresh_rois can redraw them.
        if forget:
            if linked_graphic_name:
                self.__text_location_dicts.pop(linked_graphic_name, None)
            else:
                self.__text_location_dicts.clear()

        if not self.canvas.winfo_exists() or not self.__shown_text_roi_rect_lists :
            return

        if linked_graphic_name and linked_graphic_name in self.__shown_text_roi_rect_lists :
            for id in self.__shown_text_roi_rect_lists[linked_graphic_name]:
                self.canvas.delete(id)
            
            self.__shown_text_roi_rect_lists[linked_graphic_name].clear()

            for text in self.__shown_ocr_text_lists[linked_graphic_name]:
                self.canvas.delete(text[0])

            self.__shown_ocr_text_lists[linked_graphic_name].clear()
            self.__text_tooltips_lists[linked_graphic_name].clear()

        elif linked_graphic_name is None:
            for linked_graphic_name, rect_list in self.__shown_text_roi_rect_lists.items():
                for id in rect_list:
                    self.canvas.delete(id)
                
                for text in self.__shown_ocr_text_lists[linked_graphic_name]:
                    self.canvas.delete(text[0])

            self.canvas.delete('text_roi')

            self.__shown_text_roi_rect_lists.clear()
            self.__shown_ocr_text_lists.clear()
            self.__text_tooltips_lists.clear()
        



    def move_to_roi(self, roi, pno):
        self.__go_to_roi = roi
        self.__go_to_pno = pno
        self.canvas.after(1000,self.__move_to_roi)

    def __move_to_roi(self):
        """ Move the canvas to the a region of interest """

        self.zoom(100)
        self.go_to_page(self.__go_to_pno + 1)

        bbox1 = self.canvas.bbox(self.__go_to_roi)
        bbox2 = self.canvas.bbox(tk.ALL)

        box_image = self.canvas.coords(self.container)  # get image area
        box_canvas = (self.canvas.canvasx(0),  # get visible area of the canvas
                      self.canvas.canvasy(0),
                      self.canvas.canvasx(self.canvas.winfo_width()),
                      self.canvas.canvasy(self.canvas.winfo_height()))
        
        x1 = max(box_canvas[0] - box_image[0], 0)  # get coordinates (x1,y1,x2,y2) of the image tile
        y1 = max(box_canvas[1] - box_image[1], 0)
        x2 = min(box_canvas[2], box_image[2]) - box_image[0]
        y2 = min(box_canvas[3], box_image[3]) - box_image[1]

        

        # calculate coordinates to center region of interest

        x = ((bbox1[0] - box_image[0])+(bbox1[2] - box_image[0]))/2 - (x2-x1)/2*self.imscale
        y = ((bbox1[1] - box_image[1])+(bbox1[3] - box_image[1]))/2 - (y2-y1)/2*self.imscale


        x_percentage = x/(bbox2[2]-bbox2[0])
        y_percentage = y/(bbox2[3]-bbox2[1])


        self.move_to_coordinate_fractions(x_percentage,y_percentage)
        self.focus_on_roi(self.__go_to_roi)
        self.canvas.after(500,self.unselect_poly)
        self.canvas.after(1000,self.focus_on_roi,self.__go_to_roi)
        self.canvas.after(1500,self.unselect_poly)
        self.canvas.after(2000,self.focus_on_roi,self.__go_to_roi)


    def __select_text(self, x, y):
        """ Selects text when cursor is with text location """
        text_tag = self.canvas.find_closest(x, y)
        tags = self.canvas.gettags(text_tag)  # get tags of the current object
        
        if 'text_roi' in tags:  

            if self.__previous_selected_text_roi != tags[0] or self.__finished_selecting_text:
                if self.__clear_selected_shown_text:
                    self.__clear_selected_shown_text()
                self.__finished_selecting_text = False
                self.__previous_selected_text_roi = tags[0]


            is_horizontal = (tags[5] == 'True')
            if is_horizontal:
                rect, rect_id = self.__create_horizontal_selection_rectangle(text_tag)
            else:
                rect, rect_id = self.__create_vertical_selection_rectangle(text_tag)
            self.__selecting_text_rect = rect 
            self.__selecting_text_rect_id = rect_id   

            self.__selected_shown_text_roi_list.append(tags)

            # Sort vertical selection 
            if not is_horizontal:
                def vertical_text_order(e):
                    return e[7]
                self.__selected_shown_text_roi_list.sort(key=vertical_text_order,reverse=True)

            self.__tool_panel_selected_text_callback(self.__selected_shown_text_roi_list,self.path,self.pno,self.file_type) 



    def __create_horizontal_selection_rectangle(self, text_tag):
        bbox = self.canvas.bbox(text_tag)
        if ((not self.__selecting_text_rect)
                or self.start_text_select_x > bbox[0] 
                or self.start_text_select_y > bbox[1]):
            self.start_text_select_x = bbox[0]
            self.start_text_select_y = bbox[1]
           
        self.canvas.delete(self.__selecting_text_rect_id)

        rect , rect_id = self.___create_text_select_rectangle(self.start_text_select_x,
                                                                                    self.start_text_select_y,
                                                                                    bbox[2],
                                                                                    bbox[3])
                                                                            
        return rect,rect_id  


    def __create_vertical_selection_rectangle(self, text_tag):
        bbox = self.canvas.bbox(text_tag)
        if ((not self.__selecting_text_rect)
                or self.start_text_select_x > bbox[0]):
            self.start_text_select_x = bbox[0]
            self.start_text_select_y = bbox[1]
            self.end_text_select_y = bbox[3]
           
        self.canvas.delete(self.__selecting_text_rect_id)

        if self.start_text_select_y > bbox[1]:
            start_y =  self.end_text_select_y
            end_y = bbox[1]
        else:
            start_y = self.start_text_select_y
            end_y = bbox[3]

        rect , rect_id = self.___create_text_select_rectangle(self.start_text_select_x,
                                                                                    start_y,
                                                                                    bbox[2],
                                                                                    end_y)
                                                                                
        return rect,rect_id  



    
    def highlight_text(self):
        i = self.canvas.find_withtag('current')  # id of the current object
        tags = self.canvas.gettags(i)  # get tags of the current object
        if 'text_roi' in tags:  
            self.__selecting_text = True
            
            self.canvas.config(cursor="xterm")
        else:
            self.canvas.config(cursor="")
            self.__selecting_text = False

        

    def on_select_press(self, event):
        self.canvas.focus_set() 
        # create rectangle if not yet exist
        #if not self.rect:

        self.unselect_poly()
        self.unselect_rect()
        self.__get_object_selection()

        curX, curY = ( self.canvas.canvasx(event.x),  self.canvas.canvasy(event.y))

        #self.__selecting_text_rect = None

        if self.__selecting_text:
            self.__select_text(curX, curY) 
            return 
        else: 
            if self.__clear_selected_shown_text:
                self.__clear_selected_shown_text()
            

        if self.highlighted_poly or self.highlighted_rect:
            self.__set_selected_roi()
            return

    def __clear_selected_shown_text(self):
        self.canvas.delete(self.__selecting_text_rect_id)
        self.__selecting_text_rect = None
        self.__selected_shown_text_roi_list.clear()
        if self.__tool_panel_selected_text_callback:
            self.__tool_panel_selected_text_callback(self.__selected_shown_text_roi_list,self.path,self.pno,self.file_type)

    
    selection_rect = None
    start_rect_selection_x =  0
    start_rect_selection_y =  0


    def on_button_press_selection(self, event):
        self.canvas.focus_set() 

        curX, curY = ( self.canvas.canvasx(event.x),  self.canvas.canvasy(event.y))
        
        if self.__selecting_text:
            self.__select_text(curX, curY) 
            return 
        else: 
            if self.__clear_selected_shown_text:
                self.__clear_selected_shown_text()

        self.unselect_poly()
        self.unselect_rect()

        self.unhighlight_rect()  # change color and zeroize selected rectangle
        self.highlight_rect()  # change color and select rectangle

       
        self.unhighlight_poly()  # change color and zeroize selected polygon
        self.highlight_poly()  # change color and select polygon
        
        self.__get_object_selection()

        self.__send_selection_callback(False)

        if self.highlighted_poly or self.highlighted_rect:
            self.__set_selected_roi()
            return
        
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        self.start_rect_selection_x =  x
        self.start_rect_selection_y =  y
        
        self.selection_rect = self.draw_selection_rectangle(x, y, x+1, y+1)


    def on_control_shift_press(self, _):
        i = self.canvas.find_withtag('current')  # id of the current object
        tags = self.canvas.gettags(i)  # get tags of the current object
        
        if self.tag_poly_line in tags and 'rect' in tags:  # if it's a polyline. 2nd tag is ALWAYS a unique tag ID
            j = tags[1] + self.tag_rect_const  # unique tag of the rectangle
            self.canvas.itemconfigure(tags[1], fill=self.color_roi['point'])  # select lines
            self.canvas.itemconfigure(j, state='normal')  # show rectangle
            self.multi_highlighted_rect.append(tags[1])  # remember 2nd unique tag_id
        
        if self.tag_poly_line in tags and 'poly' in tags:
            j = tags[1] + self.tag_poly_const  # unique tag of the polygon
            color = self.color_roi 
            self.canvas.itemconfigure(tags[1], fill=color['point'])  # select lines through 2nd tag
            self.canvas.itemconfigure(j, state='normal')  # show polygon
            self.multi_highlighted_poly.append(tags[1])  # remember 2nd unique tag_id
        
        self.__get_object_selection()


    def on_button_press(self, event):
        if self.edit_mode:
            return
        # To remove focus on other elements
        self.canvas.focus_set() 

        curX, curY = ( self.canvas.canvasx(event.x),  self.canvas.canvasy(event.y))

        #self.__selecting_text_rect = None

        if self.__selecting_text:
            self.__select_text(curX, curY) 
            return 
        else: 
            if self.__clear_selected_shown_text:
                self.__clear_selected_shown_text()

        self.unselect_poly()
        self.unselect_rect()

        self.unhighlight_rect()  # change color and zeroize selected rectangle
        self.highlight_rect()  # change color and select rectangle

       
        self.unhighlight_poly()  # change color and zeroize selected polygon
        self.highlight_poly()  # change color and select polygon

        self.__get_object_selection()

        self.__send_selection_callback(False)

        if self.highlighted_poly or self.highlighted_rect:
            self.__set_selected_roi()
            return
        

        bbox = self.canvas.coords(self.container)  # get image area
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        if (bbox[0] <= x < bbox[2] and bbox[1] <= y < bbox[3]):

            # save mouse drag start position
            self.start_rect_highlight_x =  x
            self.start_rect_highlight_y =  y

            self.__rect = self.canvas.create_rectangle(self.x, self.y, 1, 1, fill="",width=self.width_line,
                                                dash=self.dash, outline=self.color_roi['draw'])

    def on_rect_move_press(self, event):

        if self.edit_mode:
            return
        
        self.__on_text_move_press(event)

        curX, curY = ( self.canvas.canvasx(event.x),  self.canvas.canvasy(event.y))

        if self.__rect:

            # expand rectangle as you drag the mouse

            bbox = self.canvas.coords(self.container)  # get image area
            if (bbox[0] <= curX < bbox[2] and bbox[1] <= curY < bbox[3]):
                self.canvas.coords(self.__rect, self.start_rect_highlight_x, self.start_rect_highlight_y, curX, curY)
                self.canvas.itemconfigure(self.__rect, dash='')  # set solid line
            else:
                self.canvas.coords(self.__rect, self.start_rect_highlight_x, self.start_rect_highlight_y, curX, curY)
                self.canvas.itemconfigure(self.__rect, dash=self.dash)  # set dashed line

        if self.selection_image:
            self.draw_selection_rectangle(self.start_rect_selection_x,self.start_rect_selection_y,curX,curY)

        self.repostion_crosshair(event, curX, curY)



    def __on_text_move_press(self, event):
        
        curX, curY = ( self.canvas.canvasx(event.x),  self.canvas.canvasy(event.y))

        if self.__selecting_text:
            self.__select_text(curX, curY) 
            return 
        else: 
            if self.__clear_selected_shown_text:
                self.__clear_selected_shown_text()
        


    def on_button_release(self, event):
        self.__finished_selecting_text = True
        if self.__rect:
            self.rect = self.__rect
            self.set_rect(event)
            self.canvas.delete(self.__rect)
            self.__rect = None 


    multi_highlighted_rect = []
    multi_highlighted_poly = []

    def on_selection_button_release(self, event):
        self.__finished_selecting_text = True

        if event.state & 0x0004:  # 0x0004 corresponds to Control
            return 
        
        self.multi_unhighlight()

        if self.__rect:
            self.rect = self.__rect
            self.set_rect(event)
            self.canvas.delete(self.__rect)
            self.__rect = None 

        if self.selection_image and self.selection_image.height == 1 and self.selection_image.width == 1:
            self.selection_image = None
            return 
        
        self.selection_image = None 
        curX, curY = ( self.canvas.canvasx(event.x),  self.canvas.canvasy(event.y))
        enclosed_ids  = self.canvas.find_enclosed(self.start_rect_selection_x, self.start_rect_selection_y,
                                                curX, curY)


        for id in enclosed_ids:
            tags = self.canvas.gettags(id)
            if self.tag_poly_line in tags and 'rect' in tags:  # if it's a polyline. 2nd tag is ALWAYS a unique tag ID
                j = tags[1] + self.tag_rect_const  # unique tag of the rectangle
                self.canvas.itemconfigure(tags[1], fill=self.color_roi['point'])  # select lines
                self.canvas.itemconfigure(j, state='normal')  # show rectangle
                self.multi_highlighted_rect.append(tags[1])  # remember 2nd unique tag_id
            if self.tag_poly_line in tags and 'poly' in tags:
                j = tags[1] + self.tag_poly_const  # unique tag of the polygon
                color = self.color_roi 
                self.canvas.itemconfigure(tags[1], fill=color['point'])  # select lines through 2nd tag
                self.canvas.itemconfigure(j, state='normal')  # show polygon
                self.multi_highlighted_poly.append(tags[1])  # remember 2nd unique tag_id
        
        self.__get_object_selection()

        if self.selection_rect:
            self.canvas.delete(self.selection_rect)
            self.selection_rect = None

    
    def multi_unhighlight(self):

        for id in self.multi_highlighted_rect:
            j = id + self.tag_rect_const  # unique tag of the rectangle
            self.canvas.itemconfigure(id, fill=self.color_roi['back'])  # deselect lines
            self.canvas.itemconfigure(j, state='hidden')  # hide rectangle
        self.multi_highlighted_rect.clear()  # clear the list

        for id in self.multi_highlighted_poly:
            j = id + self.tag_poly_const  # unique tag of the polygon
            color = self.color_roi 
            self.canvas.itemconfigure(id, fill=color['back'])  # deselect lines
            self.canvas.itemconfigure(j, state='hidden')  # hide figure
        self.multi_highlighted_poly.clear()  # clear the list


    def set_rect(self, event):
        """ Set rectangle """
        #if self.hold_menu2:  # popup menu was opened
        #    self.hold_menu2 = False
        #    self.motion(event)  # motion event for popup menu
        #    return
        #self.motion(event)  # generate motion event. It's needed for menu bar, bug otherwise!
        if self.__selector_tool_chosen is not self.RECTANGULAR_TOOL:
            return
        if ' '.join(map(str, self.dash)) == self.canvas.itemcget(self.rect, 'dash'):
            return  # rectangle is out of scope
        # Calculate coordinates of rectangle top left corner on the zoomed image
        bbox1 = self.canvas.coords(self.container)  # get image area
        bbox2 = self.canvas.coords(self.rect)  # get rectangle area
        x0 = (bbox2[0] - bbox1[0])/ self.imscale  # get (x,y) of top left corner on the image
        y0 = (bbox2[1] - bbox1[1])/ self.imscale
        x1 = (bbox2[2] - bbox1[0])/ self.imscale
        y1 = (bbox2[3] - bbox1[1])/ self.imscale
        poly = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        tag_uid = "{x0}-{y0}-{x1}-{y1}".format(x0=int(x0), y0=int(y0), x1=int(x1), y1=int(y1))  # unique ID
        self.draw_polygon(poly, self.color_roi, self.tag_roi, self.roi_list[self.pno],  tag_uid)  # draw rectangle
        self.save_page_roi()



    def unhighlight_rect(self):
        """ Deselect current roi object """
        if not self.highlighted_rect: return  # selected rectangles list is empty
        for i in self.highlighted_rect:
            if i not in self.selected_rect and i not in self.multi_highlighted_rect:
                j = i + self.tag_rect_const  # unique tag of the rectangle
                self.canvas.itemconfigure(i, fill=self.color_roi['back'])  # deselect lines
                self.canvas.itemconfigure(j, state='hidden')  # hide rectangle
        self.highlighted_rect.clear()  # clear the list


    def highlight_rect(self):
        """ Select and change color of the current roi object """
        i = self.canvas.find_withtag('current')  # id of the current object
        tags = self.canvas.gettags(i)  # get tags of the current object
        if self.tag_poly_line in tags and 'rect' in tags:  # if it's a polyline. 2nd tag is ALWAYS a unique tag ID
            j = tags[1] + self.tag_rect_const  # unique tag of the rectangle
            self.canvas.itemconfigure(tags[1], fill=self.color_roi['point'])  # select lines
            self.canvas.itemconfigure(j, state='normal')  # show rectangle
            self.highlighted_rect.append(tags[1])  # remember 2nd unique tag_id

    def unselect_rect(self):
        if not self.selected_rect: return  # selected rectangles list is empty
        
        current_object_id = self.canvas.find_withtag('current')  # id of the current object
        tags = self.canvas.gettags(current_object_id)  # get tags of the current object
        if len(tags) > 1 and tags[1] in self.selected_rect:
            return
        
        for i in self.selected_rect:
            j = i + self.tag_rect_const  # unique tag of the rectangle
            self.canvas.itemconfigure(i, fill=self.color_roi['back'])  # deselect lines
            self.canvas.itemconfigure(j, state='hidden')  # hide rectangle
        self.selected_rect.clear()  # clear the list


    def multi_delete_rect(self):
        """ Delete multiple selected rectangles """
        for i in self.multi_highlighted_rect:
            j = i + self.tag_rect_const  # unique tag of the rectangle
            if i in self.roi_list[self.pno]: del(self.roi_list[self.pno][i])  # delete ROI from the dictionary of all rectangles
            self.canvas.delete(i)  # delete lines
            self.canvas.delete(j)  # delete rectangle
        self.save_page_roi()


    def delete_rect(self):
        """ Delete selected rectangle """
        if self.highlighted_rect:  # delete selected rectangle
            for i in self.highlighted_rect:
                j = i + self.tag_rect_const  # unique tag of the rectangle
                del(self.roi_list[self.pno][i])  # delete ROI from the dictionary of all rectangles
                self.canvas.delete(i)  # delete lines
                self.canvas.delete(j)  # delete rectangle
            self.highlighted_rect.clear()  # clear selection list
            self.hold_menu2 = False  # popup menu is closed
            self.save_page_roi()


    def set_edge(self, event):
        """ Set edge of the polygon """
        if self.edit_mode:
            return

        # To remove focus on other elements
        self.canvas.focus_set() 

        curX, curY = ( self.canvas.canvasx(event.x),  self.canvas.canvasy(event.y))

        #self.__selecting_text_rect = None

        if self.__selecting_text:
            self.__select_text(curX, curY) 
            return 
        else: 
            if self.__clear_selected_shown_text:
                self.__clear_selected_shown_text()
        
        if self.hold_menu2:  # popup menu was opened
            self.hold_menu2 = False
            self.motion(event)  # motion event for popup menu
            return

        self.unselect_poly()
        self.unselect_rect()
        self.__send_selection_callback(False)
        self.__get_object_selection()

        if self.highlighted_poly or self.highlighted_rect:
            self.__set_selected_roi()
            return
            

        self.motion(event)  # generate motion event. It's needed for menu bar, bug otherwise!
        x = self.canvas.canvasx(event.x)  # get coordinates of the event on the canvas
        y = self.canvas.canvasy(event.y)
        if self.edge and ' '.join(map(str, self.dash)) == self.canvas.itemcget(self.edge, 'dash'):
            return  # the edge is out of scope or self-crossing with other edges
        elif not self.edge and self.outside(x, y):
            return  # starting point is out of scope
        color = self.color_roi 
        if not self.edge:  # start drawing polygon
            self.draw_edge(color, x, y, self.tag_curr_edge_start)
            # Draw sticking circle
            self.canvas.create_oval(x - self.radius_circle, y - self.radius_circle,
                                    x + self.radius_circle, y + self.radius_circle,
                                    width=0, fill=color['draw'],
                                    tags=(self.tag_curr_edge, self.tag_curr_circle))
        else:  # continue drawing polygon
            x1, y1, x2, y2 = self.canvas.coords(self.tag_curr_edge_start)  # get coords of the 1st edge
            x3, y3, x4, y4 = self.canvas.coords(self.edge)  # get coordinates of the current edge
            if x4 == x1 and y4 == y1:  # finish drawing polygon
                if len(self.polygon) > 2:  # draw polygon on the zoomed image canvas
                    if self.roi:  # it's a ROI polygon
                        d = self.roi_list[self.pno]
                        tag = self.tag_roi
                    else:  # it's a hole polygon
                        d = self.hole_dict
                        tag = self.tag_hole
                    self.draw_polygon(self.polygon, color, tag, d)
                    self.save_page_roi()
                self.delete_edges()  # delete edges of drawn polygon
            else:
                self.draw_edge(color, x, y)  # continue drawing polygon, set new edge
    
  



    def __set_selected_roi(self):
        self.selected_poly = self.highlighted_poly.copy()
        self.selected_rect = self.highlighted_rect.copy()

        self.__send_selection_callback(True)
        self.__get_object_selection()

        # Rehighlight the selected poly or rect
        for i in self.selected_poly:
            j = i + self.tag_poly_const  # unique tag of the polygon
            color = self.color_roi 
            self.canvas.itemconfigure(i, fill=color['point'])  # select lines
            self.canvas.itemconfigure(j, state='normal')
        
        for i in self.selected_rect:
            j = i + self.tag_rect_const  # unique tag of the rectangle
            self.canvas.itemconfigure(i, fill=self.color_roi['point'])  # deselect lines
            self.canvas.itemconfigure(j, state='normal')  # hide rectangle

    
    def draw_polygon(self, polygon, color, tag, dictionary=None, tag_uid=None):
        """ Draw polygon on the canvas """
        # Calculate coordinates of vertices on the zoomed image
        bbox = self.canvas.coords(self.container)  # get image area
        vertices = list(map((lambda i: (i[0] * self.imscale + bbox[0],
                                        i[1] * self.imscale + bbox[1])), polygon))
        if not tag_uid:
            # Create identification tag
            tag_uid = str(uuid.uuid4())  # unique ID
        # Create polygon. 2nd tag is ALWAYS a unique tag ID + constant string.
        self.canvas.create_polygon(vertices, fill=color['point'],
                                   stipple=color['stipple'], width=1, state='hidden',
                                   tags=(tag, tag_uid + self.tag_poly_const))
        # Create polyline. 2nd tag is ALWAYS a unique tag ID.
        for j in range(-1, len(vertices) - 1):
            self.canvas.create_line(vertices[j], vertices[j + 1], width=self.width_line,
                                    fill=color['back'], tags=(self.tag_poly_line, tag_uid, 'poly', j))
        # Remember ROI / hole in the dictionary of all ROIs / holes
        if dictionary is not None:
            dictionary[tag_uid] = polygon.copy()
            
        return tag_uid

    def draw_edge(self, color, x, y, tags=None):
        """ Draw edge of the polygon """
        if len(self.polygon) > 1:
            x1, y1, x2, y2 = self.canvas.coords(self.edge)
            if x1 == x2 and y1 == y2:
                return  # don't draw edge in the same point, otherwise it'll be self-intersection
        curr_edge_id = self.tag_curr_edge_id + str(len(self.polygon))  # ID of the edge in the polygon
        self.edge = self.canvas.create_line(x, y, x, y, fill=color['draw'], width=self.width_line,
                                            tags=(tags, self.tag_curr_edge, curr_edge_id,))
        bbox = self.canvas.coords(self.container)  # get image area
        x1 = (x - bbox[0]) / self.imscale # get real (x,y) on the image without zoom
        y1 = (y - bbox[1]) / self.imscale
        self.polygon.append((x1, y1))  # add new vertex to the list of polygon vertices

    def popup(self, event):
        """ Popup menu """
        current_item = self.canvas.find_withtag('current')
        self.last_current_item = current_item
        
        self.motion(event)  # select polygon with popup menu explicitly to be sure it is selected
        if self.moving_canvas:
            self.moving_canvas = False 
            return
        self.__get_object_selection()
        self.hold_menu1 = True  # popup menu is opened
        self.hold_menu2 = True
        self.enable_or_disable_menu_buttons()
        self.menu.post(event.x_root, event.y_root)  # show popup menu
        self.hold_menu1 = False  # popup menu is closed

    def show_refresh_tool_canvas_warining(self):
        
        # Warning message if only one canvas needs to be refreshed
        if len(self.__tool_canvas_list_to_refresh) == 1:
            messagebox.showwarning("Refresh Lists", f"Please refresh the {self.__tool_canvas_list_to_refresh[0]} list.")
        else:
            canvas = ', '.join(self.__tool_canvas_list_to_refresh[:-1]) + ' and ' + self.__tool_canvas_list_to_refresh[-1]
            messagebox.showwarning("Refresh Lists", f"Please refresh the {canvas} lists.")
        return
        

    def enable_or_disable_menu_buttons(self):
        """ Enable or disable menu button depending on the what selected"""
        if (len(self.__selected_objects) == 1 or 
            ((len(self.selected_poly) == 1 or len(self.highlighted_poly) == 1)
             and len(self.__tool_canvas_list_to_refresh) > 0)):
            self.menu.enable_view_link()
        else:
            self.menu.enable_view_link(False)

        self.__selected_text = self.get_highlighted_text()
        if self.__selected_text:
            self.menu.enable_copy_text()
        else:
            self.menu.enable_copy_text(False)

        if len(self.roi_list)==0 or len(self.roi_list[self.pno]) ==0:
            self.menu.enable_rotate()
        else:
            self.menu.enable_rotate(False)

        if self.__is_empty_roi_list():
            self.menu.enable_rotate_all()
        else:
            self.menu.enable_rotate_all(False)

        if (self.selected_poly or self.selected_rect 
            or self.highlighted_poly or self.highlighted_rect
            or self.__selected_objects or self.multi_highlighted_poly):
            self.menu.enable_delete()
        else:
            self.menu.enable_delete(False)

        if self.edit_mode:
            self.menu.add_polygon_menu()
        else:
            self.menu.remove_polygon_menu()

        if (self.selected_poly or self.selected_rect 
            or self.highlighted_poly or self.highlighted_rect) and len(self.__selected_objects) == 0:
            self.menu.enable_edit_polygon()
            self.menu.enable_create_static_graphic()
        else:
            self.menu.enable_edit_polygon(False)
            self.menu.enable_create_static_graphic(False)

        if self.edit_mode and self.selected_vertex_index and self.current_polygon_editing_tag:
            self.menu.enable_delete_vertex()
        else:
            self.menu.enable_delete_vertex(False)

        item_tags = self.canvas.gettags(self.last_current_item)
        if self.tag_poly_line in item_tags and item_tags[1] == self.current_polygon_editing_tag: # Check if clicked on polyline of the editing polygon
            self.menu.enable_add_vertex()
        else:
            self.menu.enable_add_vertex(False)

        # Draw ROI context-menu entry is available only when the current selection
        # is a linked-graphic cell that can seed the tool.
        if self._find_selected_control_module_cell() is not None:
            self.menu.enable_draw_roi(True)
        else:
            self.menu.enable_draw_roi(False)




    def __is_empty_roi_list(self):
        if len(self.roi_list)==0:
            return True
        
        for page in self.roi_list:
            if page is not None and len(page)>0:
                return False
        
        return True 
            

    def view_link(self, _=None):
        
        if len(self.__tool_canvas_list_to_refresh) > 0:
            self.show_refresh_tool_canvas_warining()
            return
        
        if len(self.__selected_objects) != 1:
            return ("break")
        
        self.__show_cell_link_callback(self.__selected_objects[0])
       


    def copy_text(self, _=None):
        """Copy the selected_text to the clip board"""
        self.canvas.clipboard_clear()
        self.__selected_text = self.get_highlighted_text()
        if self.__selected_text:
            self.canvas.clipboard_append(self.__selected_text)

    def get_highlighted_text(self):
        """Get the highlighted text from selected text ROIs or current text selection"""
        highlighted_text = ""

        # Then check if there are selected text ROIs
        if self.__selected_shown_text_roi_list:
            # Extract characters from each selected text ROI
            # Each tag in the list has structure: (roi_id + '_text_roi', 'text_roi', char, index, linked_graphic_name, is_horizontal, ...)
            for tag_info in self.__selected_shown_text_roi_list:
                if len(tag_info) >= 3:
                    char = tag_info[2]  # The character is stored in index 2 of the tags
                    highlighted_text += char
        
            return highlighted_text

        # Use highlighted polygons to get the text rois 
        if self.highlighted_poly:
            bbox = self.canvas.bbox(self.highlighted_poly[0])
            text_rois = self.canvas.find_overlapping(bbox[0], bbox[1], bbox[2], bbox[3])
            text_roi_list = []
            for text_roi in text_rois:
                text_tags = self.canvas.gettags(text_roi)

                if 'text_roi' not in text_tags:
                    continue

                is_horizontal = (text_tags[5] == 'True') 
                text_roi_list.append(text_tags)

                # Sort vertical selection 
                if not is_horizontal:
                    def vertical_text_order(e):
                        return e[7]
                    text_roi_list.sort(key=vertical_text_order,reverse=True)

                if len(text_tags) >= 3:
                    char = text_tags[2]  # The character is stored in index 2 of the tags
                    highlighted_text += char

        return highlighted_text

        

    def motion(self, event):
        """ Track mouse position over the canvas """
        if self.hold_menu1: return  # popup menu is opened
        x = self.canvas.canvasx(event.x)  # get coordinates of the event on the canvas
        y = self.canvas.canvasy(event.y)

        self.unhighlight_rect()  # change color and zeroize selected rectangle
        self.highlight_rect()  # change color and select rectangle

       
        self.unhighlight_poly()  # change color and zeroize selected polygon
        self.highlight_poly()  # change color and select polygon

        self.highlight_text()

        if self.edge:  # relocate edge of the drawn polygon
            x1, y1, x2, y2 = self.canvas.coords(self.tag_curr_edge_start)  # get coordinates of the 1st edge
            x3, y3, x4, y4 = self.canvas.coords(self.edge)  # get coordinates of the current edge
            dx = x - x1
            dy = y - y1
            # Set new coordinates of the edge
            if self.radius_stick * self.radius_stick > dx * dx + dy * dy:  # sticking radius
                self.canvas.coords(self.edge, x3, y3, x1, y1)  # stick to the beginning
                self.set_dash(x1, y1)  # set dash for edge segment
            else:  # follow the mouse
                self.canvas.coords(self.edge, x3, y3, x, y)  # follow the mouse movements
                self.set_dash(x, y)  # set dash for edge segment


        self.repostion_crosshair(event, x, y)



    def repostion_crosshair(self, event, x, y):
        bbox = self.canvas.coords(self.container) # Image bbox
        if self.show_crosshair and bbox and bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]: # Mouse inside image
            self.canvas.coords(self.crosshair_vertical, x, self.canvas.canvasy(0), x, self.canvas.canvasy(self.canvas.winfo_height()))
            self.canvas.coords(self.crosshair_horizontal, self.canvas.canvasx(0), y, self.canvas.canvasx(self.canvas.winfo_width()), y)
            self.canvas.itemconfigure(self.crosshair_vertical, state='normal')
            self.canvas.itemconfigure(self.crosshair_horizontal, state='normal')
            pixel_color = self.get_pixel_color(event) # Get pixel color under mouse
            if pixel_color:
                luminance = self.calculate_luminance(pixel_color)
                if luminance > 180: # Threshold for light background
                    crosshair_color = 'gray30'
                else:
                    crosshair_color = 'gray70'
                self.canvas.itemconfigure(self.crosshair_vertical, fill=crosshair_color) # Set crosshair color
                self.canvas.itemconfigure(self.crosshair_horizontal, fill=crosshair_color) # Set crosshair color
                
        else:
            self.canvas.itemconfigure(self.crosshair_vertical, state='hidden')
            self.canvas.itemconfigure(self.crosshair_horizontal, state='hidden')


    
    def calculate_luminance(self, color):
        """ Calculate luminance of a color tuple """
        if isinstance(color, tuple): # RGB color
            r, g, b = color[0], color[1], color[2]
            return 0.299 * r + 0.587 * g + 0.114 * b
        elif isinstance(color, int): # Grayscale color
            return color # Luminance is just the grayscale value
        return 0 # Default luminance if color is not recognized


    def get_pixel_color(self, event):
        """ Get the color of the image pixel under the mouse pointer """
        x_canvas = self.canvas.canvasx(event.x)
        y_canvas = self.canvas.canvasy(event.y)

        bbox = self.canvas.coords(self.container) # Image bbox
        if not bbox or not self.canvas_image: # Check if image is loaded and bbox exists
            return None # No image loaded or bbox not available

        if not (bbox[0] <= x_canvas <= bbox[2] and bbox[1] <= y_canvas <= bbox[3]): # Mouse is outside image bounds
            return None

        x_image = int((x_canvas - bbox[0]) / self.imscale) # Get image coordinates
        y_image = int((y_canvas - bbox[1]) / self.imscale)

        # Check if the pixel is within the image bounds
        if not (0 <= x_image <= self.canvas_image.width) or not (0 <= y_image <= self.canvas_image.height):
            return None
        
        try:
            
            pixel_color = self.canvas_image.getpixel((x_image, y_image)) # Get pixel color from PIL Image
            return pixel_color # Returns RGB tuple (or grayscale value)
        except IndexError:
            return None # Handle cases where coordinates are still slightly out of bounds
        

    def set_dash(self, x, y):
        """ Set dash for edge segment """
        # If outside of the image or polygon self-intersection is occurred
        if self.outside(x, y) or self.polygon_selfintersection():
            self.canvas.itemconfigure(self.edge, dash=self.dash)  # set dashed line
        else:
            self.canvas.itemconfigure(self.edge, dash='')  # set solid line

    


    def unhighlight_poly(self):
        """ Deselect current roi object """
        if not self.highlighted_poly: return  # selected polygons list is empty
        for i in self.highlighted_poly:
            if i not in self.selected_poly and i not in self.multi_highlighted_poly:
                j = i + self.tag_poly_const  # unique tag of the polygon
                color = self.color_roi 
                self.canvas.itemconfigure(i, fill=color['back'])  # deselect lines
                self.canvas.itemconfigure(j, state='hidden')  # hide figure
        self.highlighted_poly.clear()  # clear the list
        

    def highlight_poly(self):
        """ Select and change color of the current roi object """
        if self.edge: return  # new polygon is being created (drawn) right now
        id = self.canvas.find_withtag('current')  # id of the current object
        tags = self.canvas.gettags(id)  # get tags of the current object
        if self.tag_poly_line in tags and 'poly' in tags:  # If it's a polyline. 2nd tag is ALWAYS a unique tag ID
            j = tags[1] + self.tag_poly_const  # unique tag of the polygon
            color = self.color_roi 
            self.canvas.itemconfigure(tags[1], fill=color['point'])  # select lines through 2nd tag
            self.canvas.itemconfigure(j, state='normal')  # show polygon
            self.highlighted_poly.append(tags[1])  # remember 2nd unique tag_id
        
        self.selected_vertex_index = None

        if self.tag_vertex_circle in tags:
            vertex_circle_item = id[0]
            tags = self.canvas.gettags(vertex_circle_item)
            polygon_tag = next((tag for tag in tags if tag not in [self.tag_vertex_circle, 'current']), None) # Get polygon tag

            if polygon_tag and polygon_tag == self.current_polygon_editing_tag and polygon_tag in self.vertex_circles:
                
                for index, item_id in self.vertex_circles[polygon_tag].items():
                    if item_id == vertex_circle_item:
                        self.selected_vertex_index = index


    def focus_on_roi(self, roi_name):
        self.unselect_poly()
        j = roi_name + self.tag_poly_const  # unique tag of the polygon
        color = self.color_roi 
        self.canvas.itemconfigure(roi_name, fill=color['point'])  # select lines through 2nd tag
        self.canvas.itemconfigure(j, state='normal')  # show polygon
        self.selected_poly.append(roi_name)

    def unselect_poly(self):
        if not self.selected_poly: return  # selected polygons list is empty
        
        current_object_id = self.canvas.find_withtag('current')  # id of the current object
        tags = self.canvas.gettags(current_object_id)  # get tags of the current object
        if len(tags) > 1 and tags[1] in self.selected_poly:
            return

        for i in self.selected_poly:
            j = i + self.tag_poly_const  # unique tag of the polygon
            color = self.color_roi 
            self.canvas.itemconfigure(i, fill=color['back'])  # deselect lines
            self.canvas.itemconfigure(j, state='hidden')  # hide figure
        self.selected_poly.clear()  # clear the list


    def unselect_poly_except_current(self):
        if not self.selected_poly: return  # selected polygons list is empty
        
        current_object_id = self.canvas.find_withtag('current')  # id of the current object
        tags = self.canvas.gettags(current_object_id)  # get tags of the current object
        
        to_keep = []
        for i in self.selected_poly:
            if len(tags) > 1 and tags[1] in self.selected_poly and len(to_keep) == 0:
                to_keep = [tags[1]]
                continue
            j = i + self.tag_poly_const  # unique tag of the polygon
            color = self.color_roi 
            self.canvas.itemconfigure(i, fill=color['back'])  # deselect lines
            self.canvas.itemconfigure(j, state='hidden')  # hide figure
        
        self.selected_poly = to_keep


    def is_roi(self, tag):
        """ Return True if polygon is ROI. Return False if polygon is hole """
        tags = self.canvas.gettags(tag)
        if self.tag_roi in tags:
            return True
        return False

    def redraw_figures(self):
        """ Overwritten method. Redraw sticking circle for the wheel event """
        bbox = self.canvas.coords(self.tag_curr_circle)
        if bbox:  # radius of sticky circle is unchanged during zoom
            cx = (bbox[0] + bbox[2]) / 2  # center of the circle
            cy = (bbox[1] + bbox[3]) / 2
            self.canvas.coords(self.tag_curr_circle,
                               cx - self.radius_circle, cy - self.radius_circle,
                               cx + self.radius_circle, cy + self.radius_circle)
            
        # Rescale all tag_vertex_circle circles in the canvas 
        vertex_circles_ids = self.canvas.find_withtag(self.tag_vertex_circle)
        for vertex_circle_id in vertex_circles_ids:
            bbox = self.canvas.coords(vertex_circle_id)
            cx = (bbox[0] + bbox[2]) / 2  # center of the circle
            cy = (bbox[1] + bbox[3]) / 2
            self.canvas.coords(vertex_circle_id,
                                 cx - self.radius_vertex_circle, cy - self.radius_vertex_circle,
                                 cx + self.radius_vertex_circle, cy + self.radius_vertex_circle)


        for _, text_in_linked_graphic in self.__shown_ocr_text_lists.items():
            for text in text_in_linked_graphic:
                text_id = text[0]
                roi_height = text[1]
                self.canvas.itemconfigure(text_id, font=("Arial", int(roi_height/3 * self.imscale)))


    selection_image = None
    selection_rect = None


    def draw_selection_rectangle(self, x1, y1, x2, y2):
        """ Draw selection rectangle """
        image = Image.new('RGBA', (int(abs(x2-x1)), int(abs(y2-y1))), (0,120,215,128))
        drawing = ImageDraw.Draw(image)
        x = abs(x1-x2) - 1 if abs(x1-x2) >= 1 else 0 # Prevent negative width
        y = abs(y1-y2) - 1 if abs(y1-y2) >= 1 else 0 # Prevent negative height
        drawing.rectangle([0, 0, x, y], fill=None, outline=(0,120,215,255), width=1)
        self.selection_image = ImageTk.PhotoImage(image)
        if self.selection_rect:
            self.canvas.delete(self.selection_rect)
        self.selection_rect = self.canvas.create_image(x1 if x1 < x2 else x2, y1 if y1 < y2 else y2, image=self.selection_image, anchor='nw')
        

    def delete_edges(self):
        """ Delete edges of drawn polygon """
        if self.edge:  # if polygon is being drawing, delete it
            self.edge = None  # delete all edges and set current edge to None
            self.canvas.delete(self.tag_curr_edge)  # delete all edges
            self.polygon.clear()  # remove all items from vertices list

    
    def delete_selected_objects(self):
        for object in self.__selected_objects:
            object.delete_from_database()
        self.__refresh_tool_canvas_callback()
        


    def delete_selected(self):
        if len(self.__tool_canvas_list_to_refresh) > 0:
            self.show_refresh_tool_canvas_warining()
            return

        if self.__check_if_any_linked():
            message = 'Object(s) selected are linked. Do you want to delete the links also?'
            if not messagebox.askokcancel('Delete Links',message):
                return
            
        self.delete_page_links()
        self.delete_selected_objects()
        self.delete_rect()
        self.delete_poly()
        self.multi_delete_poly()
        self.multi_delete_rect()
        self.__refresh_rois()


    def __check_if_any_linked(self):
        list_to_check :List[str] = self.selected_poly + self.selected_rect + self.multi_highlighted_poly + self.multi_highlighted_rect
    
        
        for roi_id in list_to_check:
            if re.search('[a-zA-Z]', roi_id):
                return True
            
        return False
    

    def delete_page_links(self):
        list_to_check :List[str] = self.highlighted_poly + self.highlighted_rect + self.selected_poly + self.selected_rect \
                                    + self.multi_highlighted_poly + self.multi_highlighted_rect


        for roi_id in list_to_check:
            if HMI_Display.SECONDARY_GRAPHIC_TYPE in roi_id:
                self.__db.delete_page_link(self.path, self.pno, roi_id)

        

    def multi_delete_poly(self):
        """ Delete multiple selected polygons """
        for i in self.multi_highlighted_poly:
            j = i + self.tag_poly_const  # unique tag of the polygon
            if self.is_roi(j):
                if i in self.roi_list[self.pno]: del(self.roi_list[self.pno][i])  # delete ROI from the dictionary of all ROIs
            else:
                if i in self.hole_dict: del(self.hole_dict[i])  # delete hole from the dictionary of all holes
            self.canvas.delete(i)  # delete lines
            self.canvas.delete(j)  # delete polygon
        self.save_page_roi()
                

    def delete_poly(self):
        """ Delete selected polygon """
        self.delete_edges()  # delete edges of drawn polygon
        if self.highlighted_poly:  # delete selected polygon
            for i in self.highlighted_poly:
                j = i + self.tag_poly_const  # unique tag of the polygon
                if self.is_roi(j):
                    if i in self.roi_list[self.pno]: del(self.roi_list[self.pno][i])  # delete ROI from the dictionary of all ROIs
                else:
                    if i in self.hole_dict: del(self.hole_dict[i])  # delete hole from the dictionary of all holes
                self.canvas.delete(i)  # delete lines
                self.canvas.delete(j)  # delete polygon
            self.highlighted_poly.clear()  # clear selection list
            self.hold_menu2 = False  # popup menu is closed
            self.save_page_roi()

    def delete_all(self, with_text=True):
        """ Delete all polygons and rects from the canvas and clear variables """
        self.delete_edges()  # delete edges of drawn polygon
        self.canvas.delete(self.tag_roi)  # delete all ROI
        self.canvas.delete(self.tag_hole)  # delete all holes
        self.canvas.delete(self.tag_poly_line)  # delete all polygon lines
        self.highlighted_poly.clear()  # clear selection list
        self.hold_menu2 = False  # popup menu is closed
        # self.roi_list[self.pno].clear()  # clear dictionary of ROI
        self.hole_dict.clear()  # clear dictionary of holes
        if not with_text:
            return
        self.__clear_shown_text_roi_list(forget=False)

    def reset(self, roi, with_text=True):
        """ Reset ROI and holes on the image """
        self.delete_all(with_text)  # delete old rectangles and poly
        
        # In try block to handle RuntimeError: dictionary changed size during iteration
        try:
            for tag_uid ,polygon in roi.items():  # draw roi polygons
                self.draw_polygon(polygon, self.color_roi, self.tag_roi, self.roi_list[self.pno], tag_uid)
        except RuntimeError:
            pass
        

        

    @staticmethod
    def orientation(p1, p2, p3):
        """ Find orientation of ordered triplet (p1, p2, p3). Returns following values:
             0 --> p1, p2 and p3 are collinear
            -1 --> clockwise
             1 --> counterclockwise """
        val = (p2[0] - p1[0]) * (p3[1] - p2[1]) - (p2[1] - p1[1]) * (p3[0] - p2[0])
        if   val < 0: return -1  # clockwise
        elif val > 0: return  1  # counterclockwise
        else:         return  0  # collinear

    @staticmethod
    def on_segment(p1, p2, p3):
        """ Given three collinear points p1, p2, p3, the function checks
            if point p2 lies on line segment p1-p3 """
        # noinspection PyChainedComparisons
        if p2[0] <= max(p1[0], p3[0]) and p2[0] >= min(p1[0], p3[0]) and \
           p2[1] <= max(p1[1], p3[1]) and p2[1] >= min(p1[1], p3[1]):
            return True
        return False

    def intersect(self, p1, p2, p3, p4):
        """ Return True if line segments p1-p2 and p3-p4 intersect, otherwise return False """
        # Find 4 orientations
        o1 = self.orientation(p1, p2, p3)
        o2 = self.orientation(p1, p2, p4)
        o3 = self.orientation(p3, p4, p1)
        o4 = self.orientation(p3, p4, p2)
        # General case
        if o1 != o2 and o3 != o4: return True  # segments intersect
        # Segments p1-p2 and p3-p4 are collinear
        if o1 == o2 == 0:
            # p3 lies on segment p1-p2
            if self.on_segment(p1, p3, p2): return True
            # p4 lies on segment p1-p2
            if self.on_segment(p1, p4, p2): return True
            # p1 lies on segment p3-p4
            if self.on_segment(p3, p1, p4): return True
        return False  # doesn't intersect

    def penultimate_intersect(self, p1, p2, p3):
        """ Check penultimate (last but one) edge,
            where p1 and p4 coincide with the current edge """
        if self.orientation(p1, p2, p3) == 0 and not self.on_segment(p3, p1, p2):
            return True
        else:
            return False

    def first_intersect(self, p1, p2, p3, p4):
        """ Check the 1st edge, where points p2 and p3 CAN coincide """
        if p2[0] == p3[0] and p2[1] == p3[1]: return False  # p2 and p3 coincide -- this is OK
        if p1[0] == p3[0] and p1[1] == p3[1]: return False  # there is only 1 edge
        # There is only 2 edges
        if p1[0] == p4[0] and p1[1] == p4[1]: return self.penultimate_intersect(p1, p2, p3)
        return self.intersect(p1, p2, p3, p4)  # General case

    def polygon_selfintersection(self):
        """ Check if polygon has self-intersections """
        x1, y1, x2, y2 = self.canvas.coords(self.edge)  # get coords of the current edge
        for i in range(1, len(self.polygon)-2):  # don't include the 1st ant the last 2 edges
            x3, y3, x4, y4 = self.canvas.coords(self.tag_curr_edge_id + str(i))
            if self.intersect((x1, y1), (x2, y2), (x3, y3), (x4, y4)): return True
        # Check penultimate (last but one) edge, where points p1 and p4 coincide
        j = len(self.polygon) - 2
        if j > 0:  # 2 or more edges
            x3, y3, x4, y4 = self.canvas.coords(self.tag_curr_edge_id + str(j))
            if self.penultimate_intersect((x1, y1), (x2, y2), (x3, y3)): return True
        # Check the 1st edge, where points p2 and p3 CAN coincide
        x3, y3, x4, y4 = self.canvas.coords(self.tag_curr_edge_start)
        if self.first_intersect((x1, y1), (x2, y2), (x3, y3), (x4, y4)): return True
        return False  # there is no self-intersections in the polygon


    def save_page_roi(self):
        """ Saves region-of-interests in document """
        logging.info("PDF Saving region-of-interests list for document {doc} ".format(doc=self.path))
        self.__db.insert_project_document_roi(self.path,self.roi_list)

    def show_crosshairs(self, _):
        self.canvas.itemconfigure(self.crosshair_vertical, state='normal')
        self.canvas.itemconfigure(self.crosshair_horizontal, state='normal')

    def hide_crosshairs(self, _):
        self.canvas.itemconfigure(self.crosshair_vertical, state='hidden')
        self.canvas.itemconfigure(self.crosshair_horizontal, state='hidden')



