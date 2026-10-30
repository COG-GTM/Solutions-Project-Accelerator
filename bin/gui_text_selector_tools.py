# -*- coding: utf-8 -*-
import ast
from collections import OrderedDict
import copy
import json
import os

from bs4 import BeautifulSoup
import markdown
from rapidfuzz import process
import requests
from bin.logic_config import Config
from bin.logic_profile import profile
import re
import sys
import threading
from tkinter import font, messagebox, ttk
from typing import List
import cv2
import numpy as np
from bin.gui_floating_dropdown import FloatingDropdown
from bin.logic_internal_database import Database
from bin.logic_pdf_markdown import page_to_markdown
from bin.logic_pdf_tables import Table, find_tables
from bin.logic_pdf_to_svg import page_to_svg
import io
import logging
from threading import Thread

from PIL import Image, ImageTk, ImageFilter
from bin.logic_linked_graphic import Linked_Graphic
import tkinter as tk
import uuid
import cv2
from paddleocr import PPStructure

from bin import logic_safe_regex as safe_regex
from bin.logic_linked_texts import GivenTextLink, LinkedText, TagnameParameterRelationship, TargetTextLink, contains_item_separator
from bin.logic_llm_inference import UnifiedInference
from bin.logic_text_document_llm_processors import TextDocumentLLMPreprocessor, TextDocumentLLMPostProcessor, TextDocumentLLMProcessor
logging.getLogger().setLevel('INFO') # PaddleOCR Changes level

from .gui_canvas import CanvasImage
from .logic_acm_data_handler import ACM_Data_Handler
from PIL import ImageDraw
import ttwidgets

from .gui_base64_icons import rotate_gray
from .gui_intelligent_popup_menu import IntelligenceEnabledPopupMenu

class TextSelectorToolsMenu:
    """ Menu widget for the selector canvas GUI window """
    def __init__(self, master, functions):
        """ Initialize the Menu """
        self.__functs = functions  # obtain link on dictionary of functions
        self.menu = tk.Menu(master, tearoff=0)  # create main menu bar, public for the main GUI
        # Enable / disable these menu labels
        self.__label_copy_text = 'Copy'
        self.__label_view_link = 'View Link'
        self.__label_accept = 'Accept'
        self.__label_discard = 'Discard'
        self.__label_ignore_text = 'Ignore Text'
        self.__label_next_unapproved = 'Show Next Unapproved'
        self.__label_previous_text = 'Show Previous Unapproved'
        self.__label_rotate = 'Rotate'
        self.__label_rotate_all = 'Rotate All'
        self.__label_delete = 'Delete'
        self.__label_rerun_rule = 'Re-run Rule'
        
        self.__rotate_meun_icon = tk.PhotoImage(data=rotate_gray)
        # Create menu 
        self.menu.add_command(label=self.__label_copy_text
                              , command=self.__functs["copy_text"]
                              , accelerator="Ctrl+C"
                              , state='disabled')
        self.menu.add_separator()
        self.menu.add_command(label=self.__label_view_link,
                                command=self.__functs["view_link"],
                                accelerator="Alt+V",
                                state='disabled')
        self.menu.add_command(label=self.__label_accept,
                                command=self.__functs["accept"],
                                accelerator="Alt+A",
                                state='disabled')
        self.menu.add_command(label=self.__label_discard,
                                command=self.__functs["reject"],
                                accelerator="Alt+D",
                                state='disabled')
        self.menu.add_separator()
        self.menu.add_command(label=self.__label_previous_text,
                                command=self.__functs["previous_unapproved"],
                                accelerator='Up',
                                state='disabled')
        self.menu.add_command(label=self.__label_next_unapproved,
                                command=self.__functs["next_unapproved"],
                                accelerator='Down',
                                state='disabled')
        self.menu.add_separator()
        self.menu.add_command(label=self.__label_ignore_text,
                                command=self.__functs["ignore_text"],
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
                                state='disabled')
        self.menu.add_separator()
        self.menu.add_command(label=self.__label_rerun_rule,
                                command=self.__functs["rerun_regex"],
                                state='disabled')
        
    def enable_copy_text(self, enable=True):
        if enable:
            self.menu.entryconfigure(self.__label_copy_text, state='normal') 
        else: 
            self.menu.entryconfigure(self.__label_copy_text, state='disabled')

    def enable_view_link(self, enable=True):
        if enable:
            self.menu.entryconfigure(self.__label_view_link, state='normal') 
        else: 
            self.menu.entryconfigure(self.__label_view_link, state='disabled')

    def enable_accept(self, enable=True):
        if enable:
            self.menu.entryconfigure(self.__label_accept, state='normal') 
        else: 
            self.menu.entryconfigure(self.__label_accept, state='disabled')

    def enable_reject(self, enable=True):
        if enable:
            self.menu.entryconfigure(self.__label_discard, state='normal') 
        else: 
            self.menu.entryconfigure(self.__label_discard, state='disabled')

    def enable_next_unapproved(self, enable=True):
        if enable:
            self.menu.entryconfigure(self.__label_next_unapproved, state='normal') 
        else: 
            self.menu.entryconfigure(self.__label_next_unapproved, state='disabled')
    
    def enable_previous_unapproved(self, enable=True):
        if enable:
            self.menu.entryconfigure(self.__label_previous_text, state='normal') 
        else: 
            self.menu.entryconfigure(self.__label_previous_text, state='disabled')

    def enable_ignore_text(self, enable=True):
        if enable:
            self.menu.entryconfigure(self.__label_ignore_text, state='normal') 
        else: 
            self.menu.entryconfigure(self.__label_ignore_text, state='disabled')

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

    def enable_rerun_regex(self, enable=True):
        if enable:
            self.menu.entryconfigure(self.__label_rerun_rule, state='normal') 
        else: 
            self.menu.entryconfigure(self.__label_rerun_rule, state='disabled')

    def post(self, x, y):
        self.menu.post(x, y)  # show popup menu


class AutoAdjustingText(tk.Text):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master
        self.font = font.Font(font=('Arial',9))

         # Set the text color to green
        self.config(font=self.font)

        # Create a tag for bold text
        self.tag_configure("bold", font='arial 9 bold')

        # Create a tag for approved text
        self.tag_configure("approved", font='arial 9 bold', foreground='green')

        # Create a tag for approved text
        self.tag_configure("pending", font='arial 9 bold', foreground='orange')
        
        # Bind to the <Configure> event to update size when window changes
        self.bind("<Configure>", self.update_size)

    def set_text(self, text, bold_ranges=None, approved=False,is_tagname=False):
        self.config(state=tk.NORMAL)
        self.delete(1.0, tk.END)
        self.insert(tk.END, text)

        # Apply bold formatting
        if bold_ranges:
            for start, end in bold_ranges:
                self.tag_add("bold", f"1.{start}", f"1.{end}")

        if approved and not is_tagname:
            self.insert(tk.END, "\n✓ APPROVED",'approved')
        elif not is_tagname:
            self.insert(tk.END, "\n○ PENDING",'pending')

        self.config(state=tk.DISABLED)
        self.update_size()



    def update_size(self, event=None):
    
        # Calculate the number of lines needed
        contents = self.get(1.0, tk.END)
        if contents.endswith('\n'):
            num_lines = len(contents.split('\n')) - 1
        else:
            num_lines = len(contents.split('\n'))

        # Calculate the number of characters that can fit in this width
        longest_line = max(contents.split('\n'), key=len)
        
        # Set the widget's width in characters
        self.config(width=len(longest_line))
        
        # Set the widget's height in lines
        self.config(height=num_lines)


class CanvasTooltip:
    '''
    It creates a tooltip for a given canvas tag or id as the mouse is
    above it.

    This class has been derived from the original Tooltip class I updated
    and posted back to StackOverflow at the following link:

    https://stackoverflow.com/questions/3221956/
           what-is-the-simplest-way-to-make-tooltips-in-tkinter/
           41079350#41079350

    Alberto Vassena on 2016.12.10.
    '''
    
    # Class variable to track the currently active tooltip
    _active_tooltip = None

    def __init__(self, canvas, tag_or_id,
                 *,
                 bg='#FFFFEA',
                 pad=(5, 3, 5, 3),
                 text='canvas info',
                 waittime=400,
                 wraplength=250,
                 bold_ranges=None,
                 approved=False,
                 is_tagname=False):
        self.waittime = waittime  # in miliseconds, originally 500
        self.wraplength = wraplength  # in pixels, originally 180
        self.canvas = canvas
        self.text = text
        self.bold_ranges = bold_ranges 
        self.approved = approved
        self.is_tagname = is_tagname
        self.bg = bg
        self.pad = pad
        self.id = None
        self.tw = None
        if not self.canvas.winfo_exists():
            return
        if not self.canvas.find_withtag(tag_or_id):
            return
        self.canvas.after(0, self.canvas.tag_bind, tag_or_id, "<Enter>", self.onEnter)
        self.canvas.after(0, self.canvas.tag_bind, tag_or_id, "<Leave>", self.onLeave)
        self.canvas.after(0, self.canvas.tag_bind, tag_or_id, "<ButtonPress>", self.onLeave)
        

    def onEnter(self, event=None):
        self.schedule()

    def onLeave(self, event=None):
        self.unschedule()
        self.hide()

    def schedule(self):
        self.unschedule()
        self.id = self.canvas.after(self.waittime, self.show)

    def unschedule(self):
        id_ = self.id
        self.id = None
        if id_:
            self.canvas.after_cancel(id_)


    def show_on_position(self, x,y):
        # Hide any currently active tooltip before showing this one
        if CanvasTooltip._active_tooltip is not None and CanvasTooltip._active_tooltip is not self:
            CanvasTooltip._active_tooltip.hide()
        
        self.tw = tk.Toplevel(self.canvas.master)
        self.tw.wm_overrideredirect(True)
        win = tk.Frame(self.tw,
                       background=self.bg,
                       borderwidth=0)
        label = AutoAdjustingText(win, background=self.bg,borderwidth=0)
        
        # Insert the text into the Text widget
        label.set_text(self.text, bold_ranges=self.bold_ranges
                       , approved=self.approved, is_tagname=self.is_tagname)

        # Make the Text widget read-only
        label.config(state=tk.DISABLED)

        label.grid(padx=(self.pad[0], self.pad[2]),
                   pady=(self.pad[1], self.pad[3]),
                   sticky=tk.NSEW)
        win.grid()

        self.tw.wm_geometry("+%d+%d" % (x, y))
        
        # Set this tooltip as the currently active one
        CanvasTooltip._active_tooltip = self



    def show(self, event=None):
        # Hide any currently active tooltip before showing this one
        if CanvasTooltip._active_tooltip is not None and CanvasTooltip._active_tooltip is not self:
            CanvasTooltip._active_tooltip.hide()
        
        def tip_pos_calculator(canvas, label,
                               *,
                               tip_delta=(10, 5), pad=(5, 3, 5, 3)):

            c = canvas

            s_width, s_height = c.winfo_screenwidth(), c.winfo_screenheight()

            width, height = (pad[0] + label.winfo_reqwidth() + pad[2],
                             pad[1] + label.winfo_reqheight() + pad[3])

            mouse_x, mouse_y = c.winfo_pointerxy()

            x1, y1 = mouse_x + tip_delta[0], mouse_y + tip_delta[1]
            x2, y2 = x1 + width, y1 + height

            x_delta = x2 - s_width
            if x_delta < 0:
                x_delta = 0
            y_delta = y2 - s_height
            if y_delta < 0:
                y_delta = 0

            offscreen = (x_delta, y_delta) != (0, 0)

            if offscreen:

                if x_delta:
                    x1 = mouse_x - tip_delta[0] - width

                if y_delta:
                    y1 = mouse_y - tip_delta[1] - height

            offscreen_again = y1 < 0  # out on the top

            if offscreen_again:
                # No further checks will be done.

                # TIP:
                # A further mod might automagically augment the
                # wraplength when the tooltip is too high to be
                # kept inside the screen.
                y1 = 0

            return x1, y1

        bg = self.bg
        pad = self.pad
        canvas = self.canvas

        # creates a toplevel window
        self.tw = tk.Toplevel(canvas.master)

        # Leaves only the label and removes the app window
        self.tw.wm_overrideredirect(True)

        win = tk.Frame(self.tw,
                       background=bg,
                       borderwidth=0)
        label = AutoAdjustingText(win, background=bg,borderwidth=0)
        
        # Insert the text into the Text widget
        label.set_text(self.text, bold_ranges=self.bold_ranges
                       , approved=self.approved, is_tagname=self.is_tagname)

        # Make the Text widget read-only
        label.config(state=tk.DISABLED)

        label.grid(padx=(pad[0], pad[2]),
                   pady=(pad[1], pad[3]),
                   sticky=tk.NSEW)
        win.grid()

        x, y = tip_pos_calculator(canvas, label)

        self.tw.wm_geometry("+%d+%d" % (x, y))
        
        # Set this tooltip as the currently active one
        CanvasTooltip._active_tooltip = self

    def hide(self):
        if self.tw:
            self.tw.destroy()
        self.tw = None
        # Clear the active tooltip reference if this tooltip was active
        if CanvasTooltip._active_tooltip is self:
            CanvasTooltip._active_tooltip = None

class TextSelectorTools(CanvasImage):

    CURSOR_TOOL = 0
    HAND_TOOL = 1
    RECTANGULAR_TOOL = 2
    POLYGON_TOOL = 3
    AUTO_SELECT_TOOL = 4
    DRAW_ROI_TOOL = 5

    REGEX_STROKE = (0.8, 0.8, 0.8)
    REGEX_FILL = (0,0,0)

    APPROVED_STROKE = (0.5529 , 0.8, 0.5608)
    APPROVED_FILL = (0,0,0)

    UNAPPROVED_STROKE = (1 , 1, 0)
    UNAPPROVED_FILL = (0,0,0)

    LLM_GENERATED_STROKE = (0/255, 174/255, 239/255)  # Blue for LLM-generated text
    LLM_GENERATED_FILL = (0,0,0)

    TAGNAME_SUBOBJECT_STROKE = (0.9411, 0.9725, 1)

    TAGNAME_LINE = (0/255, 174/255, 239/255)

    """ Class of SelectorTools. Inherit CanvasImage class """
    def __init__(self, placeholder, path, project_name, db: Database,  rect_size, roll_size, acm_data_handler:ACM_Data_Handler=None, 
                 llm_manager:UnifiedInference=None, type=Database.TEXT, page_number_callback=None, zoom_percentage_callback=None, config:Config=None):
        """ Initialize the SelectorTools """

        
        self.x = self.y = 0
        self.start_text_select_x = None
        self.start_text_select_y = None
        self.__config = config
        
        self.__lines_to_highlight = None
        self.__lines_to_glow = None
        self.__selecting_text = False
        self.__selecting_text_rect = None
        self.__selecting_text_rect_id = None
        self.__selected_given_text = None
        self.__selected_given_texts = {}
        self.__highlighted_given_text = None 
        self.__highlighted_parameter = None

        self.__ordered_unapproved_linked_texts = OrderedDict()
        self.__unapproved_toolips = {}
        self.__shown_tooltip = None
        self.__tagname_control_modules = {}

        self.selected_cell = None
        self.selected_table_shape = None 
        self.selected_table_bbox = None
        self.selected_table: Table = None
        self.selected_cell_full_text = None
        self.selected_cell_full_indexes = None
        self.__cell_cooordinates = None

        self.__type = type
        self.__go_to_roi = None 
        self.__go_to_pno = None
        

        self.__db = db # Internal project database
        self.__subscribed_to_db = False
        
        self.__acm_data_handler = acm_data_handler
        self.__project_name = project_name
        self.__llm_manager = llm_manager

        self.__linked_text_templates = None

        self.__zoom_percentage_callback = zoom_percentage_callback
        CanvasImage.__init__(self, placeholder, path,page_number_callback=page_number_callback, zoom_percentage_callback=self.__zoom_percentage_callback_func)  # call __init__ of the CanvasImage class

        self.text_in_page = []
        
        
        # Create a popup menu for Rectangles
        self.hold_menu1 = False  # popup menu is closed
        self.hold_menu2 = False
        self.intelligent_menu = IntelligenceEnabledPopupMenu(self.canvas)
        
        llm_option = []
        llm_selected = ''
        if llm_selected in llm_option:
            llm_option.remove(llm_selected)
        llm_option.insert(0, llm_selected)
        self.floating_dropdown = FloatingDropdown(
            parent_window=self.canvas.master,
            canvas=self.canvas,
            options=llm_option,
            callback=self.on_switch_llm_model
        )
        self.__llm_manager.init_done_subscribe(self.__llm_init_complete)
        
        
        self.menu = tk.Menu(self.canvas, tearoff=0)
        #self.menu.add_command(label='Delete', command=self.delete_rect, accelerator=u'Delete')
        #self.menu.add_command(label='Delete', command=self.delete_selected, accelerator=u'Delete')
        self.menu.add_command(label='Mark Yellow', command=self.__given_text)
        self.menu.add_command(label='Mark Green', command=self.__key_text)
        self.menu.add_command(label='Mark Red', command=self.__ignore_text)
        # Rectangle parameters
        self.rect_size = rect_size  # size of the rolling window
        # Polygon parameters
        self.roi = True  # is it a ROI or hole
        self.roll_size = roll_size  # size of the rolling window
        self.width_line = 2  # lines width

        self.color_back_roi = 'red'  # draw roi color
        self.dash = (1, 1)  # dash pattern
        self.color_roi = {'draw'   : 'red',     # draw roi color
                          'point'  : 'blue',    # point roi color
                          'back'   : self.color_back_roi,  # background roi color
                          'stipple': 'gray12'}  # stipple value for roi
        self.rect = self.canvas.create_rectangle((0, 0, 0, 0), width=self.width_line,
                                                 dash=self.dash, outline=self.color_roi['draw'])
        
        self.canvas.bind('<Motion>', self.motion)  # handle mouse motion
        self.canvas.bind("<ButtonPress-1>", self.on_select_press)
        self.canvas.bind("<ButtonRelease-3>", self.on_right_click)
        self.tag_roi = 'roi'  # roi tag
        self.tag_rect_const = 'rect'  # constant tag for rectangle
        self.tag_poly_line = 'poly_line'  # edge of the rectangle
        self.highlighted_rect = []  # selected rectangles
        self.selected_rect = []
        self.roi_list = self.__db.get_project_document_roi(self.path)  # list of all page roi rectangles and theirself.color_back_hole = 'cyan'  # draw hole color
        self.color_back_hole = 'cyan'  # draw hole color
        
        self.color_hole = {'draw'   : 'magenta',  # draw hole color
                           'point'  : '#8B0000',  # point hole color
                           'back'   : self.color_back_hole,  # background hole color
                           'stipple': 'gray50'}   # stipple value for hole
        self.color_roi =  {'draw'   : 'red',      # draw roi color
                           'point'  : 'blue',     # point roi color
                           'back'   : self.color_back_roi,  # background roi color
                           'stipple': 'gray12'}   # stipple value for roi
        self.tag_curr_edge_start = '1st_edge'  # starting edge of the current polygon
        self.tag_curr_edge = 'edge'  # edges of the polygon
        self.tag_curr_edge_id = 'edge_id'  # part of unique ID of the current edge
        self.tag_roi = 'roi'  # roi tag
        self.tag_hole = 'hole'  # hole tag
        self.tag_poly_const = 'poly'  # constant tag for polygon
        self.tag_poly_line = 'poly_line'  # edge of the polygon
        self.tag_highlighted_text = 'highlighted_text'
        self.tag_glow_text = 'tag_glow_text'
        self.tag_curr_circle = 'circle'  # sticking circle tag for the current polyline
        self.radius_stick = 10  # distance where line sticks to the polygon's staring point
        self.radius_circle = 3  # radius of the sticking circle
        self.edge = None  # current edge of the new polygon
        self.polygon = []  # vertices of the current (drawing, red) polygon
        self.highlighted_poly = []  # selected polygons top left coords on the canvas
        self.selected_poly = []
        self.hole_dict = {}  # dictionary of all holes and their coordinates on the canvas image
        self.drawn_connecting_lines = []
        self.imscale = 1.0
        self.__layers = []

        self.__show_cell_link_callback = None
        self.__pending_linked_text_action_callback = None
        



        self.__selected_text_regex_string = ''

        self.start_rect_highlight_x = None
        self.start_rect_highlight_y = None

        self.__selection_callback = None
        self.__tool_panel_text_mark_callback = None
        self.__tool_panel_document_or_page_number_change_callback = None
        self.__tool_panel_selected_text_callback = None
        self.__full_page_image_callback = None 
        
        self.__layout_engine = None
        self.__md_text = None

        # Threading variables for LLM processing
        self.__llm_processing_thread = None
        self.__llm_processing_cancelled = False

        self.subscribe_to_document_or_page_number_change(self.__document_or_page_number_change)
        self.__pending_approvals_update_timer = None
        self.__shown_text_roi_rect_lists = {}
        self.__selected_text_regex_rect_dict = {}
        self.__selected_shown_text_roi_list = []
        self.__previous_selected_text_roi = ''
        self.start_text_highlight = None
        self.__highlight_rect_images = {} 
        self.__highlighted_chars = []
        
        
        self.__menu_functions = {
                                    'copy_text': self.__copy_text,
                                    'view_link': self.__view_link,
                                    'accept': self.__accept,
                                    'reject': self.__reject,
                                    'ignore_text': self.__ignore_text,
                                    'rotate': self.__rotate,
                                    'rotate_all': self.__rotate_all,
                                    'delete': self.__delete,
                                    'next_unapproved': lambda : self.__move_to_next_unapproved_linked_texts(self.selected_poly),
                                    'previous_unapproved': lambda : self.__move_to_previous_unapproved_linked_texts(self.selected_poly),
                                    'rerun_regex': self.__rerun_regex
                                    }
        self.text_processor = TextDocumentLLMProcessor(self.__llm_manager,self.__project_name, self.__acm_data_handler, self.__db, self.__config)


    def __llm_init_complete(self):
        llm_option = self.__llm_manager.get_all_models()
        llm_selected = self.__llm_manager.get_model_name()
        if llm_selected in llm_option:
            llm_option.remove(llm_selected)
        llm_option.insert(0, llm_selected)
        if self.floating_dropdown:
            self.floating_dropdown.update_options(llm_option)

    def on_switch_llm_model(self, model_name):
        self.__llm_manager.switch_model(model_name)


    def on_right_click(self, event):
        i = self.canvas.find_withtag('current')  # id of the current object
        tags = self.canvas.gettags(i)  # get tags of the current object

        for selected_poly in self.selected_poly:
            self.canvas.itemconfigure(selected_poly, outline='', width=0)
            
        if self.tag_poly_line in tags and 'poly' in tags:
            self.canvas.itemconfigure(tags[1], outline=self.color_roi['point'], width=2)  # select lines
            self.selected_poly.clear()
            self.selected_poly.append(tags[1])

        menu = TextSelectorToolsMenu(self.canvas, self.__menu_functions)

        if len(tags) > 4 and tags[3]== 'unapproved_linked_text':
            menu.enable_accept()
            menu.enable_reject()
            menu.enable_view_link()
            menu.enable_next_unapproved()
            menu.enable_previous_unapproved()
            menu.enable_delete()
            menu.enable_rerun_regex()
        
        elif len(tags) > 4 and tags[3]== 'approved_linked_text':  
            menu.enable_view_link()
            menu.enable_delete()
            menu.enable_rerun_regex()

        elif self.selected_poly and self.selected_poly[0] in self.__tagname_control_modules:
            menu.enable_view_link()

        in_given_text, self.__highlighted_given_text, self.__highlighted_parameter = self.__get_highlighted_given_text()

        if in_given_text:
            menu.enable_ignore_text()
        else:
            menu.enable_ignore_text(False)


        if self.__highlighted_chars:
            menu.enable_copy_text()
            # Enable delete for highlighted text as well
            if not (len(tags) > 4 and (tags[3]== 'unapproved_linked_text' or tags[3]== 'approved_linked_text')):
                menu.enable_delete()
        else:
            menu.enable_copy_text(False)
        
        menu.post(event.x_root, event.y_root)


    def __copy_text(self, _=None):
        
        text_to_copy = ''

        if self.__highlighted_chars:
            for char in self.__highlighted_chars:
                text_to_copy += char['c']

        self.canvas.clipboard_clear()
        self.canvas.clipboard_append(text_to_copy)


    def __get_highlighted_given_text(self):
        '''Check if highlighted text is within the selected given text'''
        if not self.__highlighted_chars or not self.__selected_given_texts:
            return False, '', None
        if 'tagname' in self.__selected_given_texts:
            index_list = [char['index'] for char in self.__selected_given_texts['tagname']['chars']]
            all_in = True
            for char in self.__highlighted_chars:
                if char['index'] not in index_list:
                    all_in = False
            if all_in:
                return True, 'tagname', None

        if 'subobject' in self.__selected_given_texts:
            index_list += [char['index'] for char in self.__selected_given_texts['subobject']['chars']] 
            all_in = True
            for char in self.__highlighted_chars:
                if char['index'] not in index_list:
                    all_in = False
            if all_in:
                return True, 'subobject', None

        if 'parameters' in self.__selected_given_texts:
            for parameter in self.__selected_given_texts['parameters']['chars']:
                index_list += [char['index'] for char in parameter]

                all_in = True
                for char in self.__highlighted_chars:
                    if char['index'] not in index_list:
                        all_in = False
                if all_in:
                    return True, 'parameters', parameter
        
        
        return False, None, None


    def __view_link(self,_=None):
        if self.__show_cell_link_callback and self.selected_poly:
            control_module_name = self.__tagname_control_modules.get(self.selected_poly[0])
            if control_module_name:
                self.__show_cell_link_callback(control_module_name, 'tagname')
                return
            tags = self.canvas.gettags(self.selected_poly)
            linked_text_type = tags[3]
            self.__show_cell_link_callback(self.selected_poly,linked_text_type)

    def __add_new_parameter_linked_text(self, tagname, prediction, context, highlighted_text, pre_result):

        def callback(parameter_properties, callback=None):
            self.pass_parameter_back_text_selection(pre_result, context, highlighted_text, parameter_properties, callback)


        if self.__show_cell_link_callback and tagname:
            self.__show_cell_link_callback(tagname, 'new_parameter', prediction, callback)

    def __add_new_subobject_linked_text(self, tagname, subobject, context, highlighted_text, pre_result):

        def callback(callback=None):
            self.pass_subobject_back_text_selection(subobject, pre_result, context, highlighted_text, callback)


        if self.__show_cell_link_callback and tagname:
            self.__show_cell_link_callback(tagname, 'new_subobject', subobject, callback)


    def __accept(self, move_to_next=False):
        if self.__pending_linked_text_action_callback and self.selected_poly:
            selected_poly = self.selected_poly[0]

            next_id = None 
            keyList = list(self.__ordered_unapproved_linked_texts.keys())
            for i,v in enumerate(keyList):
                if v==selected_poly and i+1 < len(keyList):
                    next_id = keyList[i+1]

            self.__pending_linked_text_action_callback(self.selected_poly, True)
            try:
                self.__ordered_unapproved_linked_texts.pop(selected_poly)
            except KeyError:
                pass

            if move_to_next:

                if next_id is None:
                    return
                self.__move_to_unapproved_linked_texts(next_id)

    def __reject(self, move_to_next=False):
        for selected_poly in self.selected_poly:
            index = self.__processed_unapproved_linked_text.index(selected_poly)
            self.__processed_unapproved_linked_text.pop(index)
            
            
        if self.__pending_linked_text_action_callback and self.selected_poly:
            selected_poly = self.selected_poly[0]

            next_id = None 
            keyList = list(self.__ordered_unapproved_linked_texts.keys())
            for i,v in enumerate(keyList):
                if v==selected_poly and i+1 < len(keyList):
                    next_id = keyList[i+1]

            self.__pending_linked_text_action_callback(self.selected_poly, False)
            self.__ordered_unapproved_linked_texts.pop(selected_poly)

            if move_to_next:

                if next_id is None:
                    return
                self.__move_to_unapproved_linked_texts(next_id)

    def __move_to_previous_unapproved_linked_texts(self, current_id):
        if not self.__ordered_unapproved_linked_texts:
                return
        
        if isinstance(current_id, list):
            current_id = current_id[0]

        previous_id = None 
        keyList = list(self.__ordered_unapproved_linked_texts.keys())
        for i,v in enumerate(keyList):
            if v==current_id and i-1 >= 0:
                previous_id = keyList[i-1]
        if previous_id is None:
            return 
        
        for selected_poly in self.selected_poly:
            self.canvas.itemconfigure(selected_poly, outline='', width=0)

        self.canvas.itemconfigure(previous_id, outline=self.color_roi['point'], width=2)
        self.selected_poly.clear()
        self.selected_poly.append(previous_id)

        if self.__shown_tooltip:
            self.__unapproved_toolips[self.__shown_tooltip].hide()
            self.__shown_tooltip = None

        if previous_id in self.__unapproved_toolips:
            # Get the postion reletive to the screen of the polygon
            bbox = self.canvas.bbox(previous_id)
            x = self.canvas.canvasx(bbox[2])
            y = self.canvas.canvasy(bbox[3])

            # Get the postion of the canvas on the screen
            x = self.canvas.winfo_rootx() + x
            y = self.canvas.winfo_rooty() + y

            self.__unapproved_toolips[previous_id].show_on_position(x,y)
            self.__shown_tooltip = previous_id



    def __move_to_next_unapproved_linked_texts(self, current_id):
        if not self.__ordered_unapproved_linked_texts:
            return

        if isinstance(current_id, list):
            current_id = current_id[0]

        next_id = None 
        keyList = list(self.__ordered_unapproved_linked_texts.keys())
        for i,v in enumerate(keyList):
            if v==current_id and i+1 < len(keyList):
                next_id = keyList[i+1]
        if next_id is None:
            return 
        
        for selected_poly in self.selected_poly:
            self.canvas.itemconfigure(selected_poly, outline='', width=0)
        
        self.canvas.itemconfigure(next_id, outline=self.color_roi['point'], width=2)  # select lines
        self.selected_poly.clear()
        self.selected_poly.append(next_id)

        if self.__shown_tooltip:
            self.__unapproved_toolips[self.__shown_tooltip].hide()
            self.__shown_tooltip = None

        if next_id in self.__unapproved_toolips:
            # Get the postion reletive to the screen of the polygon
            bbox = self.canvas.bbox(next_id)
            x = self.canvas.canvasx(bbox[2])
            y = self.canvas.canvasy(bbox[3])

            # Get the postion of the canvas on the screen
            x = self.canvas.winfo_rootx() + x
            y = self.canvas.winfo_rooty() + y

            self.__unapproved_toolips[next_id].show_on_position(x,y)
            self.__shown_tooltip = next_id


    def __move_to_unapproved_linked_texts(self, linked_text_id):
        if not self.__ordered_unapproved_linked_texts:
            return

        
        for selected_poly in self.selected_poly:
            self.canvas.itemconfigure(selected_poly, outline='', width=0)
        
        self.canvas.itemconfigure(linked_text_id, outline=self.color_roi['point'], width=2)  # select lines
        self.selected_poly.clear()
        self.selected_poly.append(linked_text_id)

        if self.__shown_tooltip:
            self.__unapproved_toolips[self.__shown_tooltip].hide()
            self.__shown_tooltip = None

        if linked_text_id in self.__unapproved_toolips:
            # Get the postion reletive to the screen of the polygon
            bbox = self.canvas.bbox(linked_text_id)
            x = self.canvas.canvasx(bbox[2])
            y = self.canvas.canvasy(bbox[3])

            # Get the postion of the canvas on the screen
            x = self.canvas.winfo_rootx() + x
            y = self.canvas.winfo_rooty() + y

            self.__unapproved_toolips[linked_text_id].show_on_position(x,y)
            self.__shown_tooltip = linked_text_id



    def __rotate(self):
        print('Rotate')

    def __rotate_all(self):
        print('Rotate All')

    def __delete(self):
        """Delete selected linked text or clear highlighted text. If it's an approved subobject text link, also delete the subobject from ACM database."""
        # Check if we have a linked text polygon selected
        if self.selected_poly:
            selected_poly_id = self.selected_poly[0] if isinstance(self.selected_poly, list) else self.selected_poly
            self.delete_linked_text(selected_poly_id)

        
        # If no linked text polygon selected, try to find linked text from highlighted text
        if self.__highlighted_chars and self.__lines_to_highlight:
            # Get the bounding box of the first highlighted line
            for _, line_bbox in self.__lines_to_highlight.items():
                
                # Convert to canvas coordinates
                bbox = self.canvas.coords(self.container)
                x1 = line_bbox[0] * self.imscale + bbox[0]
                y1 = line_bbox[1] * self.imscale + bbox[1]
                x2 = line_bbox[2] * self.imscale + bbox[0]
                y2 = line_bbox[3] * self.imscale + bbox[1]
                
                # Find overlapping items on canvas
                overlapping = self.canvas.find_overlapping(x1, y1, x2, y2)
                
                # Look for linked text polygons in the overlapping items
                for item in overlapping:
                    tags = self.canvas.gettags(item)
                    if ('approved_linked_text' in tags or 'unapproved_linked_text' in tags) and len(tags) > 1:
                        linked_text_id = tags[1]  # Second tag is the unique ID
                        self.delete_linked_text(linked_text_id)
                        
        
        # If no linked text found, just clear highlighted text
        if self.__highlighted_chars:
            self.__clear_highlighted_text()
            self.refresh_image()

    def __rerun_regex(self, _=None):
        """Re-run the regex template for the selected linked text, regardless of whether it's been processed."""
        if not self.selected_poly:
            return
        
        selected_poly_id = self.selected_poly[0] if isinstance(self.selected_poly, list) else self.selected_poly
        
        # Try to get the linked text from both approved and unapproved tables
        linked_text_data = self.__db.get_approved_text_link_by_id(selected_poly_id)
        
        if not linked_text_data:
            linked_text_data = self.__db.get_unapproved_text_link_by_id(selected_poly_id)
        
        if not linked_text_data:
            return
        
        # Get the template ID
        template_id = linked_text_data.get('template_id')
        if not template_id:
            return
        
        # Find the template in the linked text templates
        template_dict = None
        for template in self.__linked_text_templates:
            if template['id'] == template_id:
                template_dict = template
                break
        
        if not template_dict:
            return
        
        # Remove the current page from processed pages for this template
        if 'processed_pages' in template_dict:
            if self.path in template_dict['processed_pages']:
                if self.pno in template_dict['processed_pages'][self.path]:
                    template_dict['processed_pages'][self.path].remove(self.pno)
                    # If no more pages for this path, remove the path entry
                    if not template_dict['processed_pages'][self.path]:
                        del template_dict['processed_pages'][self.path]
        
        # Remove from processed regex list if present
        if template_id in self.__processed_linked_text_regexes:
            self.__processed_linked_text_regexes.remove(template_id)
        
        # Extract and re-run the template
        try:
            linked_texts = self.__extract_linked_texts_data(template_dict)
            
            if linked_texts['text_relationship'] == TagnameParameterRelationship.IN_TABLE:
                self.__table_linked_text(linked_texts)
            else:
                self.__non_table_linked_text(linked_texts)
            
            # Mark as processed again
            if 'processed_pages' not in template_dict:
                template_dict['processed_pages'] = {}
            
            if self.path not in template_dict['processed_pages']:
                template_dict['processed_pages'][self.path] = []
            
            template_dict['processed_pages'][self.path].append(self.pno)
            
            # Save the updated template
            self.__db.save_linked_text_regex(template_dict)
            
            # Refresh the display
            self.delayed_update_pending_approvals()
            
        except Exception as error:
            logging.error(f"Error re-running regex: {str(error)}")

    def delete_linked_text(self, linked_text_id):
        """Delete a linked text by its ID. If it's an approved subobject text link, also delete the subobject from ACM database."""
        # Try to get the linked text from both approved and unapproved tables
        linked_text_data = self.__db.get_approved_text_link_by_id(linked_text_id)
        is_approved = True
        
        if not linked_text_data:
            linked_text_data = self.__db.get_unapproved_text_link_by_id(linked_text_id)
            is_approved = False
        
        if not linked_text_data:
            return
        
        # Check if it's a subobject link and if it's approved
        is_subobject = 'subobject' in linked_text_data
        
        if is_approved and is_subobject:
            # Delete subobject from ACM database
            try:
                # Extract tagname and subobject text
                tagname_text = linked_text_data['tagname']['text']
                subobject_name = linked_text_data['subobject_name']
                
                # Get the object ID from the tagname
                object_id = self.__acm_data_handler.get_object_id(tagname_text)
                
                if object_id:
                    # Get the subobject from ACM database
                    subobject_df = self.__acm_data_handler.get_subobject_in_object_with_name(object_id, subobject_name)
                    if subobject_df is not None and not subobject_df.empty:
                        subobject_id = subobject_df.index[0]  # SubObjectID is the index
                        self.__acm_data_handler.delete_subobject(subobject_id)
            except Exception as error:
                logging.error(f"Error deleting subobject from ACM database: {str(error)}")
        
        # Delete the text link from the database
        self.__db.delete_text_link(linked_text_id)
        
        # Remove the highlighting and canvas elements
        self.__remove_highlight_linked_text(linked_text_id)
        self.delete_polygon(linked_text_id)
        
        # Remove from tooltip dictionary if present
        if linked_text_id in self.__unapproved_toolips:
            del self.__unapproved_toolips[linked_text_id]
        
        # Remove from ordered list if present
        if linked_text_id in self.__ordered_unapproved_linked_texts:
            del self.__ordered_unapproved_linked_texts[linked_text_id]
        
        # Clear selection if this was the selected item
        if linked_text_id in self.selected_poly:
            for poly in self.selected_poly:
                self.canvas.itemconfigure(poly, outline='', width=0)
            self.selected_poly.clear()

    def motion(self, _):
        """ Track mouse position over the canvas """
        i = self.canvas.find_withtag('current')  # id of the current object
        tags = self.canvas.gettags(i)  # get tags of the current object

        if self.__shown_tooltip:
            self.__unapproved_toolips[self.__shown_tooltip].hide()
            self.__shown_tooltip = None

        self.unhighlight_poly()
        if self.tag_poly_line in tags and 'poly' in tags:  # If it's a polyline. 2nd tag is ALWAYS a unique tag ID
            #j = tags[1] + self.tag_poly_const  # unique tag of the polygon
            #color = self.color_roi if self.is_roi(j) else self.color_hole  # get color palette
            #self.canvas.itemconfigure(tags[1], fill=color['point'])  # select lines through 2nd tag
            #self.canvas.itemconfigure(j, state='normal')  # show polygon
            self.highlighted_poly.append(tags[1])  # remember 2nd unique tag_id
            

    def unhighlight_poly(self):
        """ Deselect current roi object """
        if not self.highlighted_poly: return  # selected polygons list is empty
        #for i in self.highlighted_poly:
            #j = i + self.tag_poly_const  # unique tag of the polygon
            #color = self.color_roi if self.is_roi(j) else self.color_hole  # get color palette
            #self.canvas.itemconfigure(i, fill=color['back'])  # deselect lines
            #self.canvas.itemconfigure(j, state='hidden')  # hide figure
        self.highlighted_poly.clear()  # clear the list
        

    def __zoom_percentage_callback_func(self, zoom_percentage):
        
        # Remove text selection because tkinter canvas images dont scale 
        if self.__selecting_text_rect_id != None:
            self.__clear_selected_shown_text()

        self.__create_highlight_rect_images()
        #self.__create_glow_rect_images()
        # Pass up to the document navigation tools ui
        self.__zoom_percentage_callback(zoom_percentage)

    def get_selection_subscription(self, selection_callback):
        '''Sets callback that notifies another object of selection'''
        #self.__selection_callback = callback
        selection_callback(self.__subscribe_to_selections)


    def __subscribe_to_selections(self, selection_callback, page_change_callback, selected_text_callback, full_page_image_callback
                                  , multi_selection_callback=None, refresh_tool_canvas_callback=None,show_cell_link_callback=None
                                  , text_mark_callback=None, pending_linked_text_action_callback=None):
        
        if selection_callback:
            self.__selection_callback = selection_callback

        if (self.selected_poly or self.selected_rect):
            self.__send_selection_callback(True)
        elif self.__selection_callback:
            self.__send_selection_callback(False)


        if page_change_callback:
            self.__tool_panel_document_or_page_number_change_callback = page_change_callback
            self.__tool_panel_document_or_page_number_change_callback(self.path,self.pno)

        if selected_text_callback:
            self.__tool_panel_selected_text_callback = selected_text_callback
            self.__tool_panel_selected_text_callback(self.__highlighted_chars,self.path,self.pno,self.__type)

        if text_mark_callback:
            self.__tool_panel_text_mark_callback = text_mark_callback

        
        if show_cell_link_callback:
            self.__show_cell_link_callback = show_cell_link_callback
            self.__show_cell_link_callback(self.selected_poly)

        if pending_linked_text_action_callback:
            self.__pending_linked_text_action_callback = pending_linked_text_action_callback



        self.__full_page_image_callback = full_page_image_callback
        if not self.__get_pages_thread_done:
            return
        if self.__full_page_image_callback:
            self.__full_page_image_callback(self.path,self.pno,self.full_page,self.pdf_zoom, self.full_svg_page)

       





    def __send_selection_callback(self, selection_detected):
        if not self.__selection_callback:
            return
        text_in_table = self.selected_cell is not None
        self.__selection_callback(selection_detected, 
                                    roi_select_func = self.get_selected_roi,
                                    setup_regex_template = self.setup_regex_template,
                                    setup_highlighted_linked_text = self.setup_highlighted_linked_text,
                                    remove_highlight_linked_text = self.remove_highlight_linked_text,
                                    move_to_roi_func = self.move_to_roi,
                                    remove_highlight_regex_template = self.__remove_highlight_regex_template,
                                    refresh_roi = self.__refresh_rois,
                                    given_text = self.__given_text,
                                    ignore_text = self.__ignore_text,
                                    remove_given_text = self.__remove_given_text,
                                    text_in_table = text_in_table,
                                    select_poly = self.__select_poly,
                                    document_type=Database.TEXT)
        

    def __remove_given_text(self, given_text_id):
        self.remove_styled_highlight(given_text_id)
        

    def __select_poly(self, poly_id):
        if not self.canvas_up: 
            return 
        
        for selected_poly in self.selected_poly:
            self.canvas.itemconfigure(selected_poly, outline='', width=0)

        
        self.canvas.itemconfigure(poly_id, outline=self.color_roi['point'], width=2)  # select lines
        self.selected_poly.clear()
        self.selected_poly.append(poly_id)
        

    def __draw_connecting_lines(self, lines_on_page):
        self.__remove_all_drawn_connecting_lines()

        bbox = self.canvas.coords(self.container)  # get image area
        for lineString in lines_on_page:
            line = np.array(lineString,dtype=np.int)
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
        image_bytes, _ = self.get_page(0,0,0,0,pdf_zoom,True)
        return Image.open(io.BytesIO(image_bytes))


    def __start_get_full_page_thread(self, pdf_zoom=2):
        self.__get_pages_thread_done = False
        self.__get_pages_thread=Thread(target=self.__get_page, args=(pdf_zoom,))
        self.__get_pages_thread.start()
        self.canvas.after(500,self.__check_if_get_roi_done)


    def __get_page(self, pdf_zoom):
        if CanvasTooltip._active_tooltip is not None and CanvasTooltip._active_tooltip is not self:
            CanvasTooltip._active_tooltip.hide()
        image_bytes, _ = self.get_page(0,0,0,0,pdf_zoom,True)
        self.full_page = Image.open(io.BytesIO(image_bytes))
        self.full_svg_page = page_to_svg(self.path, self.pno)
        self.pdf_zoom = pdf_zoom

        text_page = self.text_doc[self.pno]

        blocks = text_page.blocks()
        self.text_in_page = []
        self.text_in_page_string = ''
        self.lines_in_page = []

        # Order the blocks by their y0 coordinate (top to bottom)
        blocks.sort(key=lambda b: b['bbox'][1])

        #for inst in text_instances:
        #highlight = page.addHighlightAnnot((147.25030517578125, 126.52999877929688, 154.1880340576172, 140.5699920654297))
        #highlight.set_colors(stroke=[1, 0.8, 0.8]) # light red color (r, g, b)
        #highlight.update()
        #self.doc.save(self.path,incremental = True, encryption=0)


        # get chars with bbox in text 
        for block in blocks:
            for char in block['chars']:
                self.text_in_page.append(char)
                self.text_in_page_string += char['c']
            self.text_in_page_string += '\n'

        self.tables_in_page = find_tables(self.path, self.pno)


        if self.__layout_engine is None:
            cwd = os.getcwd()
            # text detection inference model folder
            det_model_dir = r'\Paddle-OCR\det'
            # text recognition inference model
            rec_model_dir = r'\Paddle-OCR\rec'
            # classification inference model
            cls_model_dir = r'\Paddle-OCR\cls'
            # layout analysis model inference model
            layout_model_dir = r'\Paddle-OCR\layout'
            # table structure model inference model
            table_model_dir = r'\Paddle-OCR\table'
            self.__layout_engine = PPStructure(table=False, ocr=False, show_log=True,lang='en',
                            det_model_dir=cwd + det_model_dir,
                            rec_model_dir=cwd + rec_model_dir,
                            cls_model_dir=cwd + cls_model_dir,
                            layout_model_dir=cwd + layout_model_dir,
                            table_model_dir=cwd + table_model_dir)
            
        img = cv2.cvtColor(np.array(self.full_page), cv2.COLOR_RGB2BGR)
        self.__page_layout = self.__layout_engine(img)

        self.__md_text = page_to_markdown(self.path, self.pno)

        # Sort layout by y1 coordinate
        self.__page_layout.sort(key=lambda x: x['bbox'][1])
        
        # Check for missed text and insert in correct order
        self.__page_layout = self.__check_and_insert_missed_text()

        # Use cv2 to draw the layout on the image
        #for item in self.__page_layout:
        #    cv2.imshow(item['type'], item['img'])
        #    cv2.waitKey(0)

        self.__processed_linked_text_regexes = []
        self.__processed_approved_linked_text = []
        self.__processed_unapproved_linked_text = []
        self.__ordered_unapproved_linked_texts = OrderedDict()
        self.__unapproved_toolips = {}

        self.__annotations_selection_rects = {}
        self.__underlined_tagname_rects = {}
        self.__tagname_control_modules = {}

        self.__highlight_approved_linked_texts()
        self.__highlight_unapproved_linked_texts()

        if not self.__subscribed_to_db:
            self.__db.subscribe_linked_text_regex_table(self.__get_linked_text_regexes)
            self.__db.subscribe_unapproved_text_link_update(self.delayed_update_pending_approvals)
            self.__db.subscribe_rejected_text_link_update(self.__remove_rejected_linked_text)
            self.__subscribed_to_db = True 

        self.__find_template_text_regexes_text()

        self.__get_pages_thread_done = True
        self.refresh_image()


    def __check_and_insert_missed_text(self):
        """
        Check if any extracted text blocks have been missed by the layout detector.
        If missed text is found, insert it in the correct order based on y-coordinate.
        
        Returns:
            list: Updated page_layout list with missed text blocks inserted
        """
        if not self.text_in_page or not self.__page_layout:
            return self.__page_layout
        
        # Group text_in_page characters into blocks based on bbox proximity
        text_blocks = self.__group_text_into_blocks()
        
        # Track which text blocks are covered by layout regions
        covered_blocks = []
        missed_blocks = []
        
        for block in text_blocks:
            is_covered = False
            block_bbox = block['bbox']
            
            # Check if this text block overlaps with any layout region
            for layout_item in self.__page_layout:
                layout_bbox = layout_item['bbox']
                # Divide by 2 for bbox
                layout_bbox = [layout_bbox[0]//2, layout_bbox[1]//2, layout_bbox[2]//2, layout_bbox[3]//2]
                
                # Check for overlap using IoU or containment
                if self.__is_rectangle_overlap(block_bbox, layout_bbox):
                    is_covered = True
                    covered_blocks.append(block)
                    break
            
            if not is_covered:
                # Check if block contains non-whitespace text
                block_text = ''.join(char['c'] for char in block['chars'])
                if block_text.strip():  # Only add if not empty or whitespace-only
                    missed_blocks.append(block)
        
        # If no missed blocks, return original layout
        if not missed_blocks:
            return self.__page_layout
        
        # Create new layout items for missed text blocks
        updated_layout = list(self.__page_layout)
        
        for missed_block in missed_blocks:
            # Extract the image region for this text block
            x0, y0, x1, y1 = missed_block['bbox']
            
            # Convert to integer coordinates
            x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
            
            # Ensure coordinates are within image bounds
            img_height, img_width = self.full_page.height, self.full_page.width
            x0 = max(0, min(x0, img_width)) * 2
            x1 = max(0, min(x1, img_width)) * 2
            y0 = max(0, min(y0, img_height)) * 2
            y1 = max(0, min(y1, img_height)) * 2
            
            # Skip if invalid bbox
            if x1 <= x0 or y1 <= y0:
                continue
            
            # Create a layout item for the missed text
            img_array = np.array(self.full_page)
            text_img = img_array[y0:y1, x0:x1]
            
            new_layout_item = {
                'type': 'text',
                'bbox': [x0, y0, x1, y1],
                'img': text_img,
                'score': 0.5,  # Lower confidence since it was missed
                'source': 'text_recovery'  # Mark as recovered from the extracted text
            }
            
            updated_layout.append(new_layout_item)
        
        # Re-sort by y-coordinate to maintain reading order
        updated_layout.sort(key=lambda x: x['bbox'][1])
        
        return updated_layout


    def __group_text_into_blocks(self):
        """
        Group individual characters from text_in_page into text blocks based on proximity.
        
        Returns:
            list: List of text blocks with bbox and character information
        """
        if not self.text_in_page:
            return []
        
        blocks = []
        current_block = None
        line_threshold = 5  # Vertical distance to consider same line
        word_threshold = 20  # Horizontal distance to consider same block
        
        for char in self.text_in_page:
            char_bbox = char['bbox']
            
            if current_block is None:
                # Start new block
                current_block = {
                    'bbox': list(char_bbox),
                    'chars': [char]
                }
            else:
                # Check if char belongs to current block
                block_bbox = current_block['bbox']
                
                # Check vertical alignment (same line or close)
                vertical_close = abs(char_bbox[1] - block_bbox[1]) < line_threshold
                
                # Check horizontal proximity
                horizontal_close = char_bbox[0] - block_bbox[2] < word_threshold
                
                if vertical_close and horizontal_close:
                    # Extend current block
                    current_block['bbox'][2] = max(current_block['bbox'][2], char_bbox[2])
                    current_block['bbox'][3] = max(current_block['bbox'][3], char_bbox[3])
                    current_block['bbox'][0] = min(current_block['bbox'][0], char_bbox[0])
                    current_block['bbox'][1] = min(current_block['bbox'][1], char_bbox[1])
                    current_block['chars'].append(char)
                else:
                    # Save current block and start new one
                    blocks.append(current_block)
                    current_block = {
                        'bbox': list(char_bbox),
                        'chars': [char]
                    }
        
        # Don't forget the last block
        if current_block is not None:
            blocks.append(current_block)
        
        # Filter out blocks that only contain whitespace
        blocks = [block for block in blocks 
                  if ''.join(char['c'] for char in block['chars']).strip()]
        
        return blocks




    def delayed_update_pending_approvals(self):
        if not self.canvas.winfo_exists():
            return

        if self.__pending_approvals_update_timer:
            self.canvas.after_cancel(self.__pending_approvals_update_timer)

        self.__pending_approvals_update_timer = self.canvas.after(200, self.update_pending_approvals)


    def update_pending_approvals(self):
        self.__pending_approvals_update_timer = None

        if not self.canvas.winfo_exists():
            return

        self.__highlight_approved_linked_texts()
        self.__highlight_unapproved_linked_texts()
        self.refresh_image()
        


    def __remove_rejected_linked_text(self, rejected_linked_text_id):
        self.delete_polygon(rejected_linked_text_id)
        self.__remove_highlight_linked_text(rejected_linked_text_id)


    def __highlight_approved_linked_texts(self):
        approved_linked_texts = self.__db.get_all_approved_text_links_by_page_no(self.path,self.pno)

        # Filter out duplicate approved linked texts
        approved_linked_texts = self.__filter_approved_overlapping_with_approved(approved_linked_texts)

        for approved_linked_text in approved_linked_texts:
            approved_linked_text = self.__extract_linked_texts_data(approved_linked_text)
            lines_to_highlight = {}

            is_higlighted = False
            linked_text_id = approved_linked_text['id']

            if linked_text_id in self.__processed_approved_linked_text:
                is_higlighted = True

            if linked_text_id in self.styled_highlights and linked_text_id not in self.__processed_unapproved_linked_text:
                is_higlighted = True
            
            if approved_linked_text['template_id'] not in self.__processed_linked_text_regexes:
                self.__processed_linked_text_regexes.append(approved_linked_text['template_id'])

            self.__processed_approved_linked_text.append(linked_text_id)

            for _, parameter in approved_linked_text['parameters'].items():
                for _, given_text in parameter.given_text.items():
                    chars = self.text_in_page[given_text.indexes[0]:given_text.indexes[1]]
                    for char in chars:
                        if given_text.table_bbox and not self.__is_bbox_within_row_column(char['bbox'], given_text.table_bbox, given_text.roi[0], given_text.roi[1]):
                            continue
                        self.__build_highlight_lines(lines_to_highlight,char)
            
            if not is_higlighted:   
                self.__highlight_linked_text(self.APPROVED_STROKE
                                            ,linked_text_id
                                            ,lines_to_highlight
                                            ,refresh_image=False)
            
            for _,line in lines_to_highlight.items():
                line = [[ line[0], line[1]],    # Top-left
                        [ line[2], line[1]],    # Top-right
                        [ line[2], line[3]],    # Bottom-right
                        [ line[0], line[3]]]    # Bottom-left
                
                if 'subobject' not in approved_linked_text:
                    parameter_type = 'Parameter'
                else:
                    parameter_type = 'Subobject'
                 
                self.draw_polygon(line
                                  , self.color_roi
                                  , "approved_linked_text"
                                  , self.__annotations_selection_rects
                                  , linked_text_id
                                  , parameter_type)
                
                self.__formated_tooltip(approved_linked_text,True)

    def __filter_approved_overlapping_with_approved(self, approved_linked_texts):
        """
        Filter out approved linked texts that overlap with other approved ones
        when they have the same parameter, parameter_type, and parameter text value.
        This helps remove duplicate approved entries.
        """
        if not approved_linked_texts or len(approved_linked_texts) < 2:
            return approved_linked_texts
        
        # Extract data for all linked texts
        extracted_approved = [self.__extract_linked_texts_data(lt) for lt in approved_linked_texts]
        
        # Track indices to remove (keep the first occurrence)
        indices_to_remove = set()
        ids_to_remove = []
        
        # Check each approved text against other approved texts
        for i, app_text_1 in enumerate(extracted_approved):
            if i in indices_to_remove:
                continue
                
            app_param_type_1 = 'Subobject' if 'subobject' in app_text_1 else 'Parameter'
            
            for j, app_text_2 in enumerate(extracted_approved):
                if i >= j or j in indices_to_remove:  # Skip self and already marked for removal
                    continue
                    
                app_param_type_2 = 'Subobject' if 'subobject' in app_text_2 else 'Parameter'
                
                # Check if parameter types match
                if app_param_type_1 != app_param_type_2:
                    continue
                
                # Check if they have the same parameters
                app_params_1 = set(app_text_1['parameters'].keys())
                app_params_2 = set(app_text_2['parameters'].keys())
                
                if app_params_1 != app_params_2:
                    continue
                
                # Check if parameter text values match
                params_match = True
                for param in app_params_1:
                    if app_text_1['parameters'][param].text != app_text_2['parameters'][param].text:
                        params_match = False
                        break
                
                if not params_match:
                    continue
                
                # Check for text overlap by comparing character index ranges
                has_overlap = False
                
                for app_param_1 in app_text_1['parameters'].values():
                    if not app_param_1.given_text:
                        continue
                    for app_given_1 in app_param_1.given_text.values():
                        app_range_1 = (app_given_1.indexes[0], app_given_1.indexes[1])
                        
                        # Check against second approved text parameters
                        for app_param_2 in app_text_2['parameters'].values():
                            if not app_param_2.given_text:
                                continue
                            for app_given_2 in app_param_2.given_text.values():
                                app_range_2 = (app_given_2.indexes[0], app_given_2.indexes[1])
                                
                                # Check if ranges overlap
                                if self.__ranges_overlap(app_range_1, app_range_2):
                                    has_overlap = True
                                    break
                            
                            if has_overlap:
                                break
                    
                    if has_overlap:
                        break
                
                # If overlap found, mark second approved text for removal (keep first)
                if has_overlap:
                    indices_to_remove.add(j)
                    ids_to_remove.append(app_text_2['id'])
        
        # Remove highlighting and canvas elements for duplicate approved texts
        for text_id in ids_to_remove:
            # Remove highlight
            self.__remove_highlight_linked_text(text_id, refresh_image=False)
            # Delete canvas polygon
            self.delete_polygon(text_id)
            # Delete from internal database
            self.__db.delete_text_link(text_id)
            # Remove from tooltip dictionary if present
            if text_id in self.__unapproved_toolips:
                del self.__unapproved_toolips[text_id]
            # Remove from ordered list if present
            if text_id in self.__ordered_unapproved_linked_texts:
                del self.__ordered_unapproved_linked_texts[text_id]
        
        # Return filtered list
        return [approved_linked_texts[i] for i in range(len(approved_linked_texts)) 
                if i not in indices_to_remove]


    def __filter_overlapping_llm_texts(self, unapproved_linked_texts):
        """
        Filter out LLM-generated linked texts that overlap with non-LLM generated ones
        when they have the same parameter, parameter_type, and parameter text value.
        Removes highlighting and canvas elements for filtered texts.
        """
        # Extract data for all linked texts
        extracted_texts = [self.__extract_linked_texts_data(lt) for lt in unapproved_linked_texts]
        
        # Separate LLM and non-LLM generated texts
        llm_texts = []
        non_llm_texts = []
        
        for i, extracted in enumerate(extracted_texts):
            if extracted.get('is_llm_generated', False):
                llm_texts.append((i, extracted))
            else:
                non_llm_texts.append((i, extracted))
        
        # Track indices to remove
        indices_to_remove = set()
        ids_to_remove = []
        
        # Check each LLM text against non-LLM texts
        for llm_idx, llm_text in llm_texts:
            llm_param_type = 'Subobject' if 'subobject' in llm_text else 'Parameter'
            
            for non_llm_idx, non_llm_text in non_llm_texts:
                non_llm_param_type = 'Subobject' if 'subobject' in non_llm_text else 'Parameter'
                
                # Check if parameter types match
                if llm_param_type != non_llm_param_type:
                    continue
                
                # Check if they have the same parameters
                llm_params = set(llm_text['parameters'].keys())
                non_llm_params = set(non_llm_text['parameters'].keys())
                
                if llm_params != non_llm_params:
                    continue
                
                # Check if parameter text values match
                params_match = True
                for param in llm_params:
                    if llm_text['parameters'][param].text != non_llm_text['parameters'][param].text:
                        params_match = False
                        break
                
                if not params_match:
                    continue
                
                # Check for text overlap by comparing character index ranges
                llm_has_overlap = False
                
                for llm_param in llm_text['parameters'].values():
                    if not llm_param.given_text:
                        continue
                    for llm_given in llm_param.given_text.values():
                        llm_range = llm_given.indexes
                        
                        for non_llm_param in non_llm_text['parameters'].values():
                            if not non_llm_param.given_text:
                                continue
                            for non_llm_given in non_llm_param.given_text.values():
                                non_llm_range = non_llm_given.indexes
                                
                                # Check if ranges overlap
                                if self.__ranges_overlap(llm_range, non_llm_range):
                                    llm_has_overlap = True
                                    break
                            
                            if llm_has_overlap:
                                break
                    
                    if llm_has_overlap:
                        break
                
                # If overlap found, mark LLM text for removal
                if llm_has_overlap:
                    indices_to_remove.add(llm_idx)
                    ids_to_remove.append(llm_text['id'])
                    break
        
        # Remove highlighting and canvas elements for filtered LLM texts
        for text_id in ids_to_remove:
            # Remove highlight
            self.__remove_highlight_linked_text(text_id, refresh_image=False)
            # Delete canvas polygon
            self.delete_polygon(text_id)
            # Delete from internal database
            self.__db.delete_text_link(text_id)
            # Remove from tooltip dictionary if present
            if text_id in self.__unapproved_toolips:
                del self.__unapproved_toolips[text_id]
            # Remove from ordered list if present
            if text_id in self.__ordered_unapproved_linked_texts:
                del self.__ordered_unapproved_linked_texts[text_id]

            
        
        # Return filtered list
        return [unapproved_linked_texts[i] for i in range(len(unapproved_linked_texts)) 
                if i not in indices_to_remove]


    def __get_given_text_ranges(self, extracted_linked_text):
        ranges = []
        for parameter in extracted_linked_text['parameters'].values():
            if not parameter.given_text:
                continue
            for given_text in parameter.given_text.values():
                if not given_text.indexes:
                    continue
                ranges.append((given_text.indexes[0], given_text.indexes[1]))
        return ranges


    def __linked_texts_share_a_range(self, extracted_linked_text, other_extracted_linked_text):
        other_ranges = self.__get_given_text_ranges(other_extracted_linked_text)
        for text_range in self.__get_given_text_ranges(extracted_linked_text):
            for other_range in other_ranges:
                if self.__ranges_overlap(text_range, other_range):
                    return True
        return False


    def __discard_linked_texts(self, ids_to_remove):
        for text_id in ids_to_remove:
            # Remove highlight
            self.__remove_highlight_linked_text(text_id, refresh_image=False)
            # Delete canvas polygon
            self.delete_polygon(text_id)
            # Delete from internal database
            self.__db.delete_text_link(text_id)
            # Remove from tooltip dictionary if present
            if text_id in self.__unapproved_toolips:
                del self.__unapproved_toolips[text_id]
            # Remove from ordered list if present
            if text_id in self.__ordered_unapproved_linked_texts:
                del self.__ordered_unapproved_linked_texts[text_id]


    def __filter_unapproved_overlapping_with_approved(self, unapproved_linked_texts):
        """
        Filter out unapproved linked texts covering a text range that is already
        covered by an approved one, so a pending link is never drawn on top of an
        accepted link.
        """
        # Get all approved linked texts for this page
        approved_linked_texts = self.__db.get_all_approved_text_links_by_page_no(self.path, self.pno)
        
        if not approved_linked_texts:
            return unapproved_linked_texts
        
        # Extract data for all linked texts
        extracted_unapproved = [self.__extract_linked_texts_data(lt) for lt in unapproved_linked_texts]
        extracted_approved = [self.__extract_linked_texts_data(lt) for lt in approved_linked_texts]
        
        # Track indices to remove
        indices_to_remove = set()
        ids_to_remove = []
        
        # Check each unapproved text against approved texts
        for unapp_idx, unapp_text in enumerate(extracted_unapproved):
            for app_text in extracted_approved:
                if self.__linked_texts_share_a_range(unapp_text, app_text):
                    indices_to_remove.add(unapp_idx)
                    ids_to_remove.append(unapp_text['id'])
                    break
        
        # Remove highlighting and canvas elements for filtered unapproved texts
        self.__discard_linked_texts(ids_to_remove)
        
        # Return filtered list
        return [unapproved_linked_texts[i] for i in range(len(unapproved_linked_texts)) 
                if i not in indices_to_remove]


    def __filter_overlapping_unapproved_linked_texts(self, unapproved_linked_texts):
        """
        Keep a single pending linked text per text range so two pending links are
        never drawn on top of each other.
        """
        if len(unapproved_linked_texts) < 2:
            return unapproved_linked_texts
        
        extracted_unapproved = [self.__extract_linked_texts_data(lt) for lt in unapproved_linked_texts]
        
        # An LLM suggestion is only kept when no other pending link covers the range
        evaluation_order = sorted(range(len(extracted_unapproved))
                                  , key=lambda idx: bool(extracted_unapproved[idx].get('is_llm_generated')))
        
        indices_to_remove = set()
        ids_to_remove = []
        kept_indices = []
        
        for idx in evaluation_order:
            unapp_text = extracted_unapproved[idx]
            if any(self.__linked_texts_share_a_range(unapp_text, extracted_unapproved[kept_idx])
                   for kept_idx in kept_indices):
                indices_to_remove.add(idx)
                ids_to_remove.append(unapp_text['id'])
            else:
                kept_indices.append(idx)
        
        # Remove highlighting and canvas elements for filtered unapproved texts
        self.__discard_linked_texts(ids_to_remove)
        
        # Return filtered list
        return [unapproved_linked_texts[i] for i in range(len(unapproved_linked_texts)) 
                if i not in indices_to_remove]


    def __highlight_unapproved_linked_texts(self):
        unapproved_linked_texts = self.__db.get_all_unapproved_text_links_by_page_no(self.path,self.pno)


        # Filter out LLM-generated texts that overlap with non-LLM ones having same parameter details
        unapproved_linked_texts = self.__filter_overlapping_llm_texts(unapproved_linked_texts)

        # Filter out unapproved linked texts that overlap with approved ones
        unapproved_linked_texts = self.__filter_unapproved_overlapping_with_approved(unapproved_linked_texts)

        # Filter out unapproved linked texts that overlap with each other
        unapproved_linked_texts = self.__filter_overlapping_unapproved_linked_texts(unapproved_linked_texts)

        for unapproved_linked_text in unapproved_linked_texts:
            unapproved_linked_text = self.__extract_linked_texts_data(unapproved_linked_text)
            lines_to_highlight = {}

            is_higlighted = False
            linked_text_id = unapproved_linked_text['id']

            if linked_text_id in self.__processed_approved_linked_text:
                is_higlighted = True
            
            if linked_text_id in self.__processed_unapproved_linked_text:
                is_higlighted = True

            if linked_text_id in self.styled_highlights:
                is_higlighted = True

            self.__processed_unapproved_linked_text.append(linked_text_id)

            if unapproved_linked_text['template_id'] not in self.__processed_linked_text_regexes and unapproved_linked_text['is_llm_generated'] == False:
                self.__processed_linked_text_regexes.append(unapproved_linked_text['template_id'])

   

            for _, parameter in unapproved_linked_text['parameters'].items():
                for _, given_text in parameter.given_text.items():
                    chars = self.text_in_page[given_text.indexes[0]:given_text.indexes[1]]
                    for char in chars:
                        if given_text.table_bbox and not self.__is_bbox_within_row_column(char['bbox'], given_text.table_bbox, given_text.roi[0], given_text.roi[1]):
                            continue
                        self.__build_highlight_lines(lines_to_highlight,char)


            # Sort the unapproved linked texts by the order they appear in the text
            for line_bbox in lines_to_highlight.values():
                self.__ordered_unapproved_linked_texts[linked_text_id] = [line_bbox[0]
                                                                                        ,line_bbox[1]
                                                                                        ,line_bbox[2]
                                                                                        ,line_bbox[3]]

           
            # Use blue for LLM-generated text, yellow for regular unapproved text
            stroke_color = self.LLM_GENERATED_STROKE if unapproved_linked_text.get('is_llm_generated', False) else self.UNAPPROVED_STROKE
            if not is_higlighted:    
                self.__highlight_linked_text(stroke_color
                                            ,linked_text_id
                                            ,lines_to_highlight
                                            ,refresh_image=False)
            
            for _,line in lines_to_highlight.items():
                line = [[ line[0], line[1]],    # Top-left
                        [ line[2], line[1]],    # Top-right
                        [ line[2], line[3]],    # Bottom-right
                        [ line[0], line[3]]]    # Bottom-left
                
                 
                if 'subobject' not in unapproved_linked_text:
                    parameter_type = 'Parameter'
                else:
                    parameter_type = 'Subobject'

                        
                self.draw_polygon(line
                                  , self.color_roi
                                  , "unapproved_linked_text"
                                  , self.__annotations_selection_rects
                                  , linked_text_id
                                  , parameter_type)
                
                tooltip = self.__formated_tooltip(unapproved_linked_text)
                self.__unapproved_toolips[linked_text_id] = tooltip

        # Sort the order dictionary of unapproved linked texts by the order they appear in the text
        self.__ordered_unapproved_linked_texts = dict(sorted(self.__ordered_unapproved_linked_texts.items(), key=lambda item: [item[1],item[0]]))




    def __formated_tooltip(self, linked_text,approved=False, object_type=None, tagname="",id="",description=""):

        bold_ranges = []
        text = ''
        is_tagname = False

        if object_type is not None:
            text = tagname
            bold_ranges.append([0,len(text)])
            text += f' {object_type}\n\n'
            text += description 
            is_tagname = True

        elif 'subobject' not in linked_text:
            id = linked_text['id']
            text = linked_text['tagname'].text
            bold_ranges.append([0,len(text)])
            text += ' Parameter\n\n'
            parameter = list(linked_text['parameters'].keys())[0]
            description = f"{parameter} = {linked_text['parameters'][parameter].text}"
            
            text += description 
                
        else:
            id = linked_text['id']
            text = linked_text['tagname'].text
            bold_ranges.append([0,len(text)])
            text += ' Subobject\n\n'
            description = ''
            for parameter, data in linked_text['parameters'].items():
                description = f"{parameter} = {data.text}\n"

            text += description
            
        return CanvasTooltip(self.canvas,id,text=text,bold_ranges=bold_ranges
                             , approved=approved, is_tagname=is_tagname)
            


    def __highlight_linked_text(self,stroke, id, linked_text_lines_to_highlight, underline=False, refresh_image=True):
        self.__remove_highlight_linked_text(id, False)
        if linked_text_lines_to_highlight is None:
            return

        for _,line in linked_text_lines_to_highlight.items():
            self.mark_with_style(id, line, stroke, underline)

        if refresh_image:
            self.refresh_image()


    def __remove_highlight_linked_text(self,id, refresh_image=True):
        self.remove_styled_highlight(id)
        if refresh_image:
            self.refresh_image()




    def __get_linked_text_regexes(self):
        self.__linked_text_templates:list[LinkedText] = self.__db.get_all_linked_text_regexes()
        self.__find_template_text_regexes_text()
        self.__find_other_templates_using_llm()
        self.__underline_tagnames_text()


    def __find_other_templates_using_llm(self):
        if not self.__linked_text_templates:
            return
        linked_texts = [self.__extract_linked_texts_data(data) for data in self.__linked_text_templates]
        self.text_processor.set_example_linked_texts(linked_texts)
        self.__start_llm_table_processing_thread()

    def __start_llm_table_processing_thread(self):
        """Start LLM table processing in a separate thread"""
        # Cancel any existing LLM processing
        self.__cancel_llm_processing()
        
        # Start new thread
        self.__llm_processing_cancelled = False
        self.__llm_processing_thread = Thread(target=self.__find_other_table_templates_using_llm_thread)
        self.__llm_processing_thread.start()


    def __start_llm_list_processing_thread(self):
        """Start LLM list processing in a separate thread"""
        # Cancel any existing LLM processing
        self.__cancel_llm_processing()
        
        # Start new thread
        self.__llm_processing_cancelled = False
        self.__llm_processing_thread = Thread(target=self.__find_other_list_templates_using_llm_thread)
        self.__llm_processing_thread.start()

    def __cancel_llm_processing(self):
        """Cancel ongoing LLM processing"""
        if self.__llm_processing_thread and self.__llm_processing_thread.is_alive():
            self.__llm_processing_cancelled = True
            # Wait briefly for thread to finish
            try:
                self.__llm_processing_thread.join(timeout=0.5)
            except:
                pass

    def __find_other_list_templates_using_llm_thread(self):
        """LLM list processing that runs in a separate thread"""
        
        # If there still llm generated unapproved linked texts, skip processing
        unapproved_linked_texts = self.__db.get_all_unapproved_text_links_by_page_no(self.path,self.pno)
        for unapproved_linked_text in unapproved_linked_texts:
            unapproved_linked_text = self.__extract_linked_texts_data(unapproved_linked_text)
            if unapproved_linked_text.get('is_llm_generated', False):
                return
            
        # Use the LLM and the linked text with in the list item to figure out if all the dependency conditions are captured
        


    def __find_other_table_templates_using_llm_thread(self):
        """LLM table processing that runs in a separate thread"""
        try:
            tables = find_tables(self.path, self.pno)

            for table in tables:
                # Check if processing has been cancelled
                if self.__llm_processing_cancelled:
                    return
                
                table_md = table.to_markdown()

                # Remove header separator line from markdown table
                table_md = table_md.replace('|---','')
                table_md = table_md.replace('\n|\n','\n')
                
                # Add row and column numbers
                table_md = self.__add_row_col_numbers_to_table(table_md)

                table_context = {
                    'full_table': table_md,
                    'table_shape': (table.col_count, table.row_count),
                    'table_bbox': table.bbox,
                    'text_on_page': self.text_in_page,
                    'table_object': table,
                    'pno': self.pno,
                    'path': self.path,
                    'doc_type': self.__type
                }

                try:
                    # Check cancellation before expensive LLM call
                    if self.__llm_processing_cancelled:
                        return
                        
                    results = self.text_processor.process_parameter_tables_with_examples(table_context)
                except requests.exceptions.ConnectionError as e:
                    # Bind the message now; `e` is unbound once the except block exits
                    error_message = str(e)
                    self.canvas.after(0, lambda msg=error_message: messagebox.showerror("Connection Error", msg))
                    continue
                except Exception:
                    # Use canvas.after to show error dialog on main thread
                    logging.exception("LLM processing error")
                    continue

                # Check cancellation after LLM call
                if self.__llm_processing_cancelled:
                    return

                if 'rebuilt_linked_texts' not in results:
                    continue

                new_text_links = results['rebuilt_linked_texts']

                for new_text_link in new_text_links:
                    # Check cancellation before processing each link
                    if self.__llm_processing_cancelled:
                        return
                    self.__save_new_text_links(new_text_link, self.text_processor.linked_texts, False)
                    
        except Exception:
            # Handle any unexpected errors
            if not self.__llm_processing_cancelled:
                logging.exception("LLM Processing Error")
        finally:
            self.__llm_processing_thread = None

    
    def __ranges_overlap(self,range1, range2):
        # Ranges are [start, end): adjacent table cells share a boundary but do not overlap.
        return range1[0] < range2[1] and range2[0] < range1[1]
    
    def __extract_linked_texts_data(self, data) -> dict[str,LinkedText]:
        id = data['id']
        tagname = self.__extract_linked_text(data['tagname'])
        parameters = {k: self.__extract_linked_text(v) for k, v in data['parameters'].items()}
        
        if 'subobject' in data:
            subobject = self.__extract_linked_text(data['subobject'])
        else:
            subobject = None

        output_data = {
            'id': id,
            'tagname': tagname,
            'parameters': parameters
        }

        if subobject is not None:
            output_data['subobject'] = subobject

        output_data['text_relationship'] = data['text_relationship']
        output_data['template_id'] = data['template_id']
        # Stored as NULL for links created before the flag existed
        output_data['is_llm_generated'] = bool(data.get('is_llm_generated') or False)
        output_data['timestamp'] = data.get('timestamp', None)

        return output_data


    def __extract_linked_text(self, data):
        linked_text = LinkedText(**data)

        if data['links'] == 'None':
            linked_text.links = None
        else:
            # Replace inf with float('inf') for safe parsing
            links_str = data['links'].replace('(inf,', '(float("inf"),').replace(', inf)', ', float("inf"))')
            linked_text.links = {k: TargetTextLink(**v) for k, v in eval(links_str).items()}


        if data['given_text'] == 'None':
            linked_text.given_text = None
        else:
            # Replace inf with float('inf') for safe parsing
            given_text_str = data['given_text'].replace('(inf,', '(float("inf"),').replace(', inf)', ', float("inf"))')
            linked_text.given_text = {k: GivenTextLink(**v) for k, v in eval(given_text_str).items()}

        return linked_text
    
    def __underline_tagnames_text(self):
        
        if self.__linked_text_templates is None:
            return
        
        for linked_texts_dict in self.__linked_text_templates:
            linked_texts = self.__extract_linked_texts_data(linked_texts_dict)
            if linked_texts['text_relationship'] == TagnameParameterRelationship.IN_TABLE:
                for table in self.tables_in_page:
                    found_tagname_cell_texts = self.__get_cell_text_for_linking_table(table,linked_texts['tagname']) 
                    new_tagname_linked_texts_list = self.__build_new_table_links(linked_texts['tagname'],found_tagname_cell_texts)
                    self.canvas.after(0, self.__highlight_tagnames, new_tagname_linked_texts_list)

            else :
                found_tagname_matches = [m for m in self.__find_all_matches(linked_texts['tagname'])]
                new_tagname_linked_texts_list = []
                for tagname_match in found_tagname_matches:
                    new_linked_texts = copy.deepcopy(linked_texts)
                    new_linked_texts['tagname'] = self.__build_new_links(linked_texts['tagname'],tagname_match)
                    new_tagname_linked_texts_list.append(new_linked_texts['tagname'])
                self.canvas.after(0, self.__highlight_tagnames, new_tagname_linked_texts_list)


    def __find_template_text_regexes_text(self):

        if self.__linked_text_templates is None:
            return

        for linked_texts_dict in self.__linked_text_templates:

            if ('processed_pages' in linked_texts_dict 
                and self.path in linked_texts_dict['processed_pages']
                and self.pno in linked_texts_dict['processed_pages'][self.path]):
                continue
            
            try:
                linked_texts = self.__extract_linked_texts_data(linked_texts_dict)
            except Exception as error:
                logging.error(f"Error extracting linked texts data: {str(error)}")
                continue


            if linked_texts['text_relationship'] == TagnameParameterRelationship.IN_TABLE:
                self.__table_linked_text(linked_texts)
            else:
                self.__non_table_linked_text(linked_texts)

            if 'processed_pages' not in linked_texts_dict:
                linked_texts_dict['processed_pages'] = {}

            if self.path not in linked_texts_dict['processed_pages']:
                linked_texts_dict['processed_pages'][self.path] = []
            
            linked_texts_dict['processed_pages'][self.path].append(self.pno)

            self.__db.save_linked_text_regex(linked_texts_dict)




    def __table_linked_text(self, linked_texts):
        for table in self.tables_in_page:
            found_tagname_cell_texts = self.__get_cell_text_for_linking_table(table,linked_texts['tagname']) 
            new_tagname_linked_texts = self.__build_new_table_links(linked_texts['tagname'],found_tagname_cell_texts)
            
            new_parameter_linked_texts = {}
            for parameter, parameter_data in linked_texts['parameters'].items():
                found_parameter_cell_texts = self.__get_cell_text_for_linking_table(table,parameter_data)
                new_parameter_linked_texts[parameter] = self.__build_new_table_links(
                                                                                    linked_texts['parameters'][parameter]
                                                                                    ,found_parameter_cell_texts
                                                                                    ,parameter
                                                                                    )
                

            if new_tagname_linked_texts:
                for i, new_tagname_linked_text in enumerate(new_tagname_linked_texts):
                    new_linked_texts = copy.deepcopy(linked_texts)
                    new_linked_texts['tagname'] = new_tagname_linked_text

                    new_linked_texts['parameters'] = {}
                    for parameter, new_parameter_linked_text in new_parameter_linked_texts.items():
                        if len(new_parameter_linked_text) > i and new_parameter_linked_text[i]:
                            new_linked_texts['parameters'][parameter] = new_parameter_linked_text[i]

                    new_linked_texts['pno'] = self.pno
                    
                    if new_linked_texts['parameters']:
                        self.__save_new_text_links(new_linked_texts, linked_texts)
                
        
    def __highlight_tagnames(self, new_tagname_linked_texts: list[LinkedText]):
        for i, new_tagname_linked_text in enumerate(new_tagname_linked_texts):
            if not new_tagname_linked_text:
                continue
            control_module = self.__db.get_control_module(new_tagname_linked_text.text)
            if not control_module:
                continue
            acm_object_df = self.__acm_data_handler.get_object_with_name(control_module['name'])

            if acm_object_df is None or acm_object_df.empty:
                continue

            object_type = acm_object_df.iloc[0]['CatalogNumber']
            description = acm_object_df.iloc[0]['Description']
            name = control_module['name']
            path = control_module['primary_linked_graphic']['path']
            pno = control_module['primary_linked_graphic']['pno']
            roi = control_module['primary_linked_graphic']['roi']

            lines_to_highlight = {}

            for _, given_text in new_tagname_linked_text.given_text.items():
                chars = self.text_in_page[given_text.indexes[0]:given_text.indexes[1]]
                for char in chars:
                    self.__build_highlight_lines(lines_to_highlight,char)

            first_index, last_index = new_tagname_linked_text.first_and_last_index()

            tagname_id = f"tagname_{first_index}_{last_index}"

            if tagname_id in self.__underlined_tagname_rects:
                continue

            self.__highlight_linked_text(self.TAGNAME_LINE
                                            ,tagname_id
                                            ,lines_to_highlight
                                            ,True
                                            ,False)
            
            for _,line in lines_to_highlight.items():
                line = [[ line[0], line[1]],    # Top-left
                        [ line[2], line[1]],    # Top-right
                        [ line[2], line[3]],    # Bottom-right
                        [ line[0], line[3]]]    # Bottom-left
                
                 

                        
                self.draw_polygon(line
                                  , self.color_roi
                                  , ("tagname", name, path, pno, roi)
                                  , self.__underlined_tagname_rects
                                  , tagname_id
                                  , 'Tagname')

                self.__tagname_control_modules[tagname_id] = name
                
                tooltip = self.__formated_tooltip(new_tagname_linked_text
                                                  , object_type=object_type
                                                  , tagname=name
                                                  , id=tagname_id
                                                  , description=description)
                self.__unapproved_toolips[tagname_id] = tooltip




    def __build_new_table_links(self, linked_text:LinkedText, found_cell_texts, parameter=None):


        new_linked_texts = []

        for index, found_cell_text in found_cell_texts.items():

            character_differences = []

            try:
                new_linked_text = self.__build_linked_table_text_string(found_cell_text
                                                                , linked_text
                                                                , index
                                                                , character_differences)
            except Exception as error:
                new_linked_texts.append(None)
                continue
            if parameter:
                new_linked_text = self.__subobject_reftype_parameter_value_correction(new_linked_text,parameter)


            new_linked_text = self.__correct_link_text_indexes(
                                                            character_differences, 
                                                            new_linked_text
                                                            )
            new_linked_texts.append(new_linked_text)
            

        return new_linked_texts
    


    def __subobject_reftype_parameter_value_correction(self, linked_text:LinkedText, parameter):
        """
        Correct the new parameter value to match the length of the original parameter value
        by using the length of the number string in the original parameter value
        to correct the length of the number string in the new parameter value
        
        e.g. original parameter value = Local.DI.001_003
             new parameter value = Local.DI.1_4 -> Local.DI.001_004
             
        :param new_parameter_value: The new parameter value
        :type new_parameter_value: str
        :param parameter: The parameter name
        :type parameter: str
        :return: The corrected new parameter value
        :rtype: str
        
        """
        if (linked_text.reftype != 'subobject' 
            and linked_text.reftype != 'subobjectNIB'):
            return linked_text
        
         # Split compenents of the parameter value
        parts = self.parameters[parameter].text.split('.')
        new_parts = linked_text.split('.')

        # join the parts outside the object name 
        parts_value = '.'.join(parts[1:])
        new_parts_value = '.'.join(new_parts[1:])

        numbers_parts = ''.join(c if c.isdigit() else ' ' for c in parts_value).split()
        new_numbers_parts = ''.join(c if c.isdigit() else ' ' for c in new_parts_value).split()

        # Calculate length for each number string
        lengths = [len(part) for part in numbers_parts]

        if len(numbers_parts) != len(new_numbers_parts):
            return linked_text

        # Use the length of the number string to ensure that the new value is the same length
        for i,length in enumerate(lengths):
            new_number = str(int(new_numbers_parts[i]))
            new_parts_value = new_parts_value.replace(new_numbers_parts[i], new_number.zfill(length),1)

        linked_text.text = new_parts[0] + '.' + new_parts_value



    def __build_linked_table_text_string(self, found_cell_texts, linked_text:LinkedText,index , character_differences):

        new_linked_text = copy.deepcopy(linked_text)
        
        for indexes_id, link in new_linked_text.links.items():
                
            given_text = linked_text.given_text[link.given_text_id]
            group = self.__get_regex_group(given_text.text,given_text.regex_string, link.given_text_indexes)
            if group is None:
                raise ValueError('Group not found in regex string')
            
            match = safe_regex.search(given_text.regex_string,found_cell_texts[indexes_id]['text'])
            if match is None:
                raise ValueError('No match found in cell text')
            sub_string = str(match.group(group))
            new_linked_text.given_text[link.given_text_id].key_and_ignore_indexes.remove(link.given_text_indexes)
            match_start = match.span(group)[0] - match.span(0)[0]
            new_linked_text.links[indexes_id].given_text_indexes = [match_start,match_start+len(sub_string)]
            new_linked_text.given_text[link.given_text_id].key_and_ignore_indexes.append(link.given_text_indexes)



            try:
                target_text_indexes = linked_text.links[indexes_id].target_text_indexes
                new_linked_text.text = self.__replacer(new_linked_text.text
                                            ,sub_string
                                            ,list(target_text_indexes)
                                            ,character_differences=character_differences)

                data = {
                    'index':target_text_indexes[1],
                    'difference':len(sub_string)-(target_text_indexes[1] - target_text_indexes[0])
                }
                character_differences.append(data)

                new_linked_text.given_text[link.given_text_id].text = found_cell_texts[indexes_id]['text']
                new_linked_text.given_text[link.given_text_id].indexes = found_cell_texts[indexes_id]['indexes']
                new_linked_text.given_text[link.given_text_id].table_bbox = found_cell_texts[indexes_id]['table_bbox']
                new_linked_text.given_text[link.given_text_id].pno = found_cell_texts[indexes_id]['pno']
                # Template may come from another document; re-point it at this one.
                new_linked_text.given_text[link.given_text_id].path = self.path
                new_linked_text.given_text[link.given_text_id].doc_type = self.__type
                if linked_text.axis:
                    new_linked_text.given_text[link.given_text_id].roi[1] = index
                else:
                    new_linked_text.given_text[link.given_text_id].roi[0] = index
                
            except Exception as error:
                continue


        return new_linked_text


        
    def __get_cell_text_for_linking_table(self,table, linked_text:LinkedText, parameter=None):
        
        found_cell_texts = {}
        
        if not linked_text.links:
            return found_cell_texts
        
        for indexes_id, target_text_link in linked_text.links.items():
            link = linked_text.given_text[target_text_link.given_text_id]

            if table.col_count != link.table_shape[0]:
                break
            
            if linked_text.axis == 0:  # Iterate over rows
                for index in range(table.row_count):
                    if index not in found_cell_texts:
                        found_cell_texts[index] = {}

                    if parameter:
                        if parameter not in found_cell_texts[index]:
                            found_cell_texts[index][parameter] = {}

                        found_cell_texts[index][parameter][indexes_id] = self.__get_text_in_cell(table,index,link.roi[1])
                        found_cell_texts[index][parameter][indexes_id]['table_bbox'] = table.bbox
                        found_cell_texts[index][parameter][indexes_id]['pno'] = self.pno
                    else:
                        found_cell_texts[index][indexes_id] = self.__get_text_in_cell(table, index,link.roi[1])
                        found_cell_texts[index][indexes_id]['table_bbox'] = table.bbox
                        found_cell_texts[index][indexes_id]['pno'] = self.pno

                        if found_cell_texts[index][indexes_id]['text'].replace(" ", "") == '' and index > 0:
                            # Use the previous value if the current value is empty
                            found_cell_texts[index][indexes_id] = found_cell_texts[index-1][indexes_id]

            else:  # Iterate over columns
                for index in range(table.col_count):
                    if index not in found_cell_texts:
                        found_cell_texts[index] = {}

                    if parameter:
                        if parameter not in found_cell_texts[index]:
                            found_cell_texts[index][parameter] = {}

                        found_cell_texts[index][parameter][indexes_id] = self.__get_text_in_cell(table,link.roi[0], index)
                        found_cell_texts[index][parameter][indexes_id]['table_bbox'] = table.bbox
                        found_cell_texts[index][parameter][indexes_id]['pno'] = self.pno
                    else:
                        found_cell_texts[index][indexes_id] = self.__get_text_in_cell(table, link.roi[0], index)
                        found_cell_texts[index][indexes_id]['table_bbox'] = table.bbox
                        found_cell_texts[index][indexes_id]['pno'] = self.pno

                        if found_cell_texts[index][indexes_id]['text'].replace(" ", "") == '' and index > 0:
                            # Use the previous value if the current value is empty
                            found_cell_texts[index][indexes_id] = found_cell_texts[index-1][indexes_id]
    
        return found_cell_texts
    


    def __non_table_linked_text(self, linked_texts):
        
        if linked_texts['id'] in self.__processed_linked_text_regexes:
            return

        tagname_matches = [m for m in self.__find_all_matches(linked_texts['tagname'])]

    
        parameter_matches = {}
        for parameter in linked_texts['parameters']:
            parameter_matches[parameter] = [m for m in self.__find_all_matches(linked_texts['parameters'][parameter])]

        all_new_linked_texts =  self.__build_listed_linked_texts(parameter_matches, tagname_matches, linked_texts)


    def __build_listed_linked_texts(self, parameter_matches, tagname_matches, linked_texts):

        text_relationship = linked_texts['text_relationship']
        
        if text_relationship == TagnameParameterRelationship.IN_LINE:
            return self.__build_inline_tagname_parameters(parameter_matches, tagname_matches, linked_texts)
        elif text_relationship == TagnameParameterRelationship.LIST_HEADER:
            return self.__build_list_header_tagname_parameters(parameter_matches, tagname_matches, linked_texts)


    def __build_inline_tagname_parameters(self, parameter_matches, tagname_matches, linked_texts:dict[str,LinkedText]):
        
        

        tagname_parameter_matches = self.__match_inline_tagnames_to_parameters(parameter_matches, tagname_matches)

        for tagname_match, parameter_matches in tagname_parameter_matches:
            
                new_linked_texts = copy.deepcopy(linked_texts)
                new_linked_texts['tagname'] = self.__build_new_links(linked_texts['tagname'],tagname_match)
                
                for parameter, parameter_match in parameter_matches.items():
                    try:
                        new_linked_texts['parameters'][parameter] = self.__build_new_links(linked_texts['parameters'][parameter]
                                                                                        ,parameter_match
                                                                                        ,TagnameParameterRelationship.IN_LINE)
                        new_linked_texts['pno'] = self.pno
                    except Exception:
                        continue
                if new_linked_texts['parameters']:
                    self.__save_new_text_links(new_linked_texts, linked_texts)
            

       
    

    def __get_text_in_cell(self, table, row, column):
        # ``end_index`` is exclusive so callers can slice ``text_in_page[start:end]``.
        chars = ''
        cell_bbox = table.rows[row].cells[column]


        start_index = np.inf
        end_index = 0

        if cell_bbox is None:
            return {'text': chars, 'indexes':(start_index,end_index)}
        
        for i, char in enumerate(self.text_in_page):
            if self.__is_bbox_within_bbox(char['bbox'],cell_bbox):
                chars += char['c']
                if i < start_index:
                    start_index = i
                if i >= end_index:
                    end_index = i + 1

        return {'text': chars, 'indexes':(start_index,end_index)}
    

    def __match_inline_tagnames_to_parameters(self, parameter_matches, tagname_matches):
        tagname_paramter_matches = []
        for tagname_match in tagname_matches:
            found_parameter_matches = {}
            for parameter, specific_parameter_matches in parameter_matches.items():
                for parameter_match in specific_parameter_matches:
                    if self.__ranges_overlap(tagname_match.span(),parameter_match.span()):
                        found_parameter_matches[parameter] = parameter_match
            if found_parameter_matches:
                tagname_paramter_matches.append((tagname_match,found_parameter_matches))
        return tagname_paramter_matches
    
                    
    def __is_bbox_within_bbox(self,bbox1, bbox2):
        return bbox1[0] >= bbox2[0] and bbox1[1] >= bbox2[1] and bbox1[2] <= bbox2[2] and bbox1[3] <= bbox2[3]
    

    def __build_list_header_tagname_parameters(self, parameter_matches, tagname_matches, linked_texts:dict[str,LinkedText]):
        tagname_parameter_matches = self.__match_list_header_tagnames_to_parameters(parameter_matches, tagname_matches)
        

        for tagname_match, parameter_matches in tagname_parameter_matches:
            
                new_linked_texts = copy.deepcopy(linked_texts)
                new_linked_texts['tagname'] = self.__build_new_links(linked_texts['tagname'],tagname_match)

                for parameter, subparameter_matches in parameter_matches.items():
                    
                        for subparameter_match in subparameter_matches:
                            try:
                                new_linked_texts['parameters'][parameter] = self.__build_new_links(linked_texts['parameters'][parameter]
                                                                                                ,subparameter_match
                                                                                                ,TagnameParameterRelationship.LIST_HEADER)
                                new_linked_texts['pno'] = self.pno
                            except Exception:
                                continue
                            if new_linked_texts['parameters']:
                                self.__save_new_text_links(new_linked_texts, linked_texts)

                
            
    

    def __match_list_header_tagnames_to_parameters(self, parameter_matches, tagname_matches):
        tagname_paramter_matches = []
        sorted_hearders_and_lists = self.__sorted_hearders_and_lists_page_layout(tagname_matches)
        for tagname_match in tagname_matches:
            found_parameter_matches = {}
            for parameter, specific_parameter_matches in parameter_matches.items():
                for parameter_match in specific_parameter_matches:
                    if self.__is_within_list_of_tagname_match(tagname_match,parameter_match,sorted_hearders_and_lists):
                        if parameter not in found_parameter_matches:
                            found_parameter_matches[parameter] = []
                        found_parameter_matches[parameter].append(parameter_match)
            if found_parameter_matches:
                tagname_paramter_matches.append((tagname_match,found_parameter_matches))
        return tagname_paramter_matches
    

    def __is_within_list_of_tagname_match(self, tagname_match, parameter_match, sorted_page_layout):
        ''' This function checks if a parameter match is within a tagname match'''

        tagname_bbox = self.__match_to_bbox(tagname_match)
        parameter_bbox = self.__match_to_bbox(parameter_match)

        
        for i in range(len(sorted_page_layout) - 1):
            # If the tagname match comes just before the parameter match 
            # or the tagname match is the same as the bbox as parameter match
            if ((self.__is_rectangle_overlap([x//2 for x in sorted_page_layout[i]['bbox']],tagname_bbox) 
                and self.__is_rectangle_overlap([x//2 for x in sorted_page_layout[i + 1]['bbox']],parameter_bbox))
                or (self.__is_rectangle_overlap([x//2 for x in sorted_page_layout[i]['bbox']],tagname_bbox) 
                and self.__is_rectangle_overlap([x//2 for x in sorted_page_layout[i]['bbox']],parameter_bbox))):
                return True
        return False 
    

    def __sorted_hearders_and_lists_page_layout(self, tagname_matches):
        hearders_and_lists_page_layout = []
        for item in self.__page_layout:
            if item['type'] == 'list':
                hearders_and_lists_page_layout.append(item)

        for tagname_match in tagname_matches:
            bbox = self.__match_to_bbox(tagname_match)
            # multiply by 2 to get the pixel value
            bbox = [x*2 for x in bbox]
            hearders_and_lists_page_layout.append({'type': 'header',
                                                   'bbox': bbox})

        return sorted(hearders_and_lists_page_layout, key=lambda y: y['bbox'][1])



    def __match_to_bbox(self, match):
        indexes = match.span()
        minx = np.inf
        miny = np.inf
        maxx = 0
        maxy = 0
        for i, char in enumerate(self.text_in_page[indexes[0]:indexes[1]]):
            minx = min(minx,char['bbox'][0])
            miny = min(miny,char['bbox'][1])
            maxx = max(maxx,char['bbox'][2])
            maxy = max(maxy,char['bbox'][3])

        bbox = [minx,miny,maxx,maxy]
        return bbox
         

    def __find_all_matches(self, linked_text:LinkedText):
        if linked_text.links is None:
            return
        
        given_text = list(linked_text.given_text.values())[0]
        text_in_page_string_without_newlines = self.text_in_page_string.replace('\n','')
        matches = safe_regex.finditer(given_text.regex_string,text_in_page_string_without_newlines)

        # Templates saved before the wildcards excluded list separators can still
        # run past the end of an item and swallow the next one.
        if contains_item_separator(given_text.text):
            return matches

        return (match for match in matches if not contains_item_separator(match.group(0)))


    def __save_new_text_links(self, linked_texts:dict[str,LinkedText],oringinal_linked_texts,template_used=True):
        """
        Save unapproved text links based on linked tag names and parameters.
        """
        if self.__has_overrun_parameter_value(linked_texts['parameters'],oringinal_linked_texts):
            return

        objects_df = self.__acm_data_handler.get_all_objects_in_project()
        filtered_objects_df = objects_df.loc[objects_df['CatalogNumber'] == linked_texts['tagname'].object_type]

        saved = False
        for _, filtered_object in filtered_objects_df.iterrows():
            filtered_tagname = filtered_object.Name

            if ((filtered_tagname == linked_texts['tagname'].text)
                and not self.__is_defined_parameter(linked_texts['parameters'],oringinal_linked_texts)):
                
                if template_used:
                    linked_texts['template_id'] = linked_texts['id']
                    linked_texts['id'] = str(uuid.uuid4())
                else:
                    linked_texts['id'] = str(uuid.uuid4())
                    linked_texts['template_id'] = linked_texts['id']
                    

                # The template's own locator points at the document it was authored on.
                linked_texts['path']= self.path
                linked_texts['pno'] = self.pno
                self.__db.save_unapproved_text_link(self.__linked_texts_to_dict(linked_texts))
                saved = True

                logging.info('Finished creating unapproved text link for tagname: {0}'.format(linked_texts['tagname'].text))

        if not saved:
            logging.info('No text link created for tagname "{0}" ({1}): no ACM object of that name, or the parameter is already defined'
                         .format(linked_texts['tagname'].text, linked_texts['tagname'].object_type))




    def __has_overrun_parameter_value(self, linked_texts:dict[str,LinkedText], oringinal_linked_texts_list):
        """
        A value that picked up a list separator or extra words that the template value
        never had means the template match ran past the end of its list item.
        """
        if isinstance(oringinal_linked_texts_list, dict):
            oringinal_linked_texts_list = [oringinal_linked_texts_list]

        for oringinal_linked_texts in oringinal_linked_texts_list:
            for parameter, new_parameter in linked_texts.items():

                if 'parameters' not in oringinal_linked_texts or parameter not in oringinal_linked_texts['parameters']:
                    continue

                original_parameter = oringinal_linked_texts['parameters'][parameter]

                if original_parameter is None or new_parameter is None:
                    continue

                if contains_item_separator(new_parameter.text):
                    logging.info('Discarding text link for "{0}": value "{1}" crosses a list item boundary'
                                 .format(parameter, new_parameter.text))
                    return True

                if not re.search(r'\s', str(original_parameter.text)) and re.search(r'\s', str(new_parameter.text)):
                    logging.info('Discarding text link for "{0}": value "{1}" does not match the shape of "{2}"'
                                 .format(parameter, new_parameter.text, original_parameter.text))
                    return True

        return False


    def __is_defined_parameter(self, linked_texts:dict[str,LinkedText], oringinal_linked_texts_list:list[dict[str,LinkedText]]):
        if isinstance(oringinal_linked_texts_list, dict):
            oringinal_linked_texts_list = [oringinal_linked_texts_list]
        for oringinal_linked_texts in oringinal_linked_texts_list:
            for parameter, new_parameter in linked_texts.items():

                if 'parameters' not in oringinal_linked_texts or parameter not in oringinal_linked_texts['parameters']:
                    continue

                if oringinal_linked_texts['parameters'][parameter] is None:
                    continue

                current_given_text = oringinal_linked_texts['parameters'][parameter].given_text
                new_given_text = new_parameter.given_text
                
                # Check if given text is exactly the same
                shared = 0
                for new_key in new_given_text:
                    for current_key in current_given_text:
                        if new_given_text[new_key] == current_given_text[current_key]:
                            shared += 1
                
                if shared == len(new_given_text):
                    return True
                    
                

                # Check if given text is almost the same and the target text is the same
                same_target_text = linked_texts[parameter].text == oringinal_linked_texts['parameters'][parameter].text

                almost_shared = len({k: new_given_text[k] for k in new_given_text 
                    if k in current_given_text and new_given_text[k].is_close_match(current_given_text[k])})
                
                if same_target_text and almost_shared == len(new_given_text):
                    return True

        return False




    def __linked_texts_to_dict(self, linked_texts:dict[str,LinkedText]):
        linked_texts_dict = {}
        for key, object in linked_texts.items():
            if isinstance(object, LinkedText):
                linked_texts_dict[key] = object.dict()
            elif isinstance(object, dict) and isinstance(list(object.values())[0], LinkedText):
                linked_texts_dict[key] = self.__linked_texts_to_dict(object)
            else:
                linked_texts_dict[key] = object
        return linked_texts_dict

    


    def __build_new_links(self, linked_text:LinkedText, match, relationship:TagnameParameterRelationship=None):

        character_differences = []


        new_linked_text = self.__build_linked_text_string(match
                                                            , linked_text
                                                            , character_differences
                                                            , relationship)


        new_linked_text = self.__correct_link_text_indexes(
                                                        character_differences, 
                                                        new_linked_text
                                                        )
        return new_linked_text
        

    

    def __correct_link_text_indexes(self, character_differences, linked_text:LinkedText):
        corrected_indexes_links = {}
        if linked_text.links is None:
            return linked_text
        
        for indexes_id, link in linked_text.links.items():
    
            indexes = list(link.target_text_indexes)
            for character_difference in character_differences:
                if indexes[1] >= character_difference['index']:
                    indexes[0] = indexes[0] + character_difference['difference']
                    if indexes[0] <= 0:
                        indexes[0] = 0
                    indexes[1] = indexes[1] + character_difference['difference']

            key = "{start}-{end}".format(start=indexes[0],end=indexes[1])
            link.target_text_indexes = (indexes[0],indexes[1])
            corrected_indexes_links[indexes_id] = key

        for indexes_id, key in corrected_indexes_links.items():
            linked_text.links[key] = linked_text.links.pop(indexes_id)

        return linked_text
    


    def __build_linked_text_string(self, match, linked_text:LinkedText, character_differences, relationship:TagnameParameterRelationship):
        
        group_indexes = {}

        new_linked_text = copy.deepcopy(linked_text)

        if linked_text.links is None:
            return new_linked_text
        
        # Remove all key_and_ignore_indexes within the given text
        for indexes_id, link in new_linked_text.links.items():
            new_linked_text.given_text[link.given_text_id].key_and_ignore_indexes = []
        
        for index_id, link in linked_text.links.items():
            
            given_text = linked_text.given_text[link.given_text_id]
            group = self.__get_regex_group(given_text.text,given_text.regex_string, link.given_text_indexes)
            if group is None:
                continue

            sub_string = str(match.group(group))
            match_start = match.span(group)[0] - match.span(0)[0]
            new_linked_text.links[index_id].given_text_indexes = [match_start,match_start+len(sub_string)]
            new_linked_text.given_text[link.given_text_id].text = str(match.group(0))
            new_linked_text.given_text[link.given_text_id].indexes = [match.span()[0],match.span()[1]]
            new_linked_text.given_text[link.given_text_id].key_and_ignore_indexes.append([match_start,match_start+len(sub_string)])
            new_linked_text.given_text[link.given_text_id].pno = self.pno
            # Template may come from another document; re-point it at this one.
            new_linked_text.given_text[link.given_text_id].path = self.path
            new_linked_text.given_text[link.given_text_id].doc_type = self.__type

            if relationship is not None:
                for char in self.text_in_page[match.span()[0]:match.span()[1]]:
                    char_bbox = char['bbox']
                    for table in self.tables_in_page:
                        if self.__is_bbox_within_bbox(char_bbox,table.bbox):
                            raise

                    if relationship == TagnameParameterRelationship.IN_LINE:
                        if self.__is_within_list(char_bbox):
                            raise

                    if relationship == TagnameParameterRelationship.LIST_HEADER:
                        if not self.__is_within_list(char_bbox):
                            raise


            try:
                new_linked_text.text = self.__replacer(new_linked_text.text
                                            ,sub_string
                                            ,link.target_text_indexes
                                            ,character_differences=character_differences)



                data = {
                    'index':linked_text['indexes'][1],
                    'difference':len(sub_string)-(linked_text['indexes'][1] - linked_text['indexes'][0])
                }
                character_differences.append(data)
                
                start_index = match.start(group) - match.start(0)
                end_index = match.end(group) - match.start(0)

                group_indexes[index_id] = [start_index,end_index]

                new_linked_text.given_text[link.given_text_id].text = match.group(0)
            except Exception as error:
                continue

        return new_linked_text
        
    


    

    def __replacer(self, s, newstring, indexes, nofail=False, character_differences=None):

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
    
    def __add_row_col_numbers_to_table(self, table_md):
        """
        Add row and column numbers to a markdown table.
        Columns are numbered as Col1, Col2, etc.
        Rows are numbered as Row1, Row2, etc.
        
        :param table_md: Markdown table string
        :return: Modified markdown table with row and column numbers
        """
        if not table_md or not table_md.strip():
            return table_md
        
        lines = table_md.split('\n')
        if len(lines) < 1:
            return table_md
        
        # Find the first non-empty line to determine column count
        first_line = None
        for line in lines:
            if line.strip():
                first_line = line
                break
        
        if not first_line:
            return table_md
        
        # Count columns by counting pipe characters
        col_count = first_line.count('|') - 1
        
        modified_lines = []
        row_num = 0
        
        for i, line in enumerate(lines):
            if not line.strip():
                modified_lines.append(line)
                continue
            
            # Add column numbers to the first row
            if i == 0:
                # Create column header with Col0, Col1, etc.
                col_headers = [''] + [f'Col{j}' for j in range(col_count)]
                modified_lines.append('|' + '|'.join(col_headers) + '|')
            
            # Add row number at the beginning, then append original line content
            parts = line.split('|')
            if len(parts) > 1:
                # Insert row number after the first pipe, keeping original content
                parts.insert(1, f'Row{row_num}')
                modified_lines.append('|'.join(parts))
                row_num += 1
            else:
                modified_lines.append(line)
        
        return '\n'.join(modified_lines)
    


    
    def __get_regex_group(self, original_string, regex_pattern, char_indexes):
        match = safe_regex.search(regex_pattern, original_string)
        
        if not match:
            return None
        
        if char_indexes[0] < 0 or char_indexes[0] >= len(original_string):
            return None
        
        # Check each group (including group 0, which is the entire match)
        for group_num in range(1, len(match.groups()) + 1):
            if char_indexes[0] in range(match.start(group_num), match.end(group_num)):
                return group_num
        
        return None
    
    
    def draw_bounding_boxes(self, img, bounding_boxes):
        # Open the image
        # Create a drawing object
        draw = ImageDraw.Draw(img)
        
        # Define colors for different types
        colors = {
            'text': (255, 0, 0),    # Red
            'title': (0, 255, 0),   # Green
            'list': (0, 0, 255),    # Blue
            'figure': (255, 255, 0) # Yellow
        }
        
        # Draw bounding boxes
        for item in bounding_boxes:
            bbox = item['bbox']
            box_type = item['type']
            color = colors.get(box_type, (128, 128, 128))  # Default to gray if type not found
            
            # Draw rectangle
            draw.rectangle(bbox, outline=color, width=2)
            
            # Draw label
            label_position = (bbox[0], bbox[1] - 20)
            draw.text(label_position, box_type, fill=color)
        
        # Show the image
        img.show()



    def __check_if_get_roi_done(self):
        if not self.__get_pages_thread_done:
            self.canvas.after(500,self.__check_if_get_roi_done)
            return
        if self.__full_page_image_callback:
            self.__full_page_image_callback(self.path,self.pno,self.full_page,self.pdf_zoom,self.full_svg_page)
        logging.info("Got Full page image of page {pno} of {doc}".format(pno=self.pno,doc=self.path))
        


    def __document_or_page_number_change(self):
        
        # Cancel any ongoing LLM processing when page changes
        self.__cancel_llm_processing()
        self.__find_other_templates_using_llm()
        
        self.__get_rois()
        self.__remove_all_drawn_connecting_lines()
        if self.__tool_panel_document_or_page_number_change_callback:
            self.__tool_panel_document_or_page_number_change_callback(self.path,self.pno)
        self.__clear_highlighted_text()
        self.__start_get_full_page_thread()
        

    def __refresh_rois(self,page_index=None):
        self.roi_list = self.__db.get_project_document_roi(self.path)
        self.__get_rois()


    def __get_rois(self):
        
        logging.info("Getting page number {pno} of {doc} region-of-interests".format(pno=self.pno,doc=self.path))
        if len(self.roi_list) != self.page_count:
            self.roi_list = [None] * self.page_count
            logging.info("Created new region-of-interests list for document {doc} ".format(doc=self.path))

        if self.roi_list[self.pno] == None:
            self.roi_list[self.pno] = {}
            logging.info("Created new region-of-interests list for page number {pno} of {doc} ".format(pno=self.pno,doc=self.path))

        logging.info("Redrawing region-of-interests for page number {pno} of {doc} ".format(pno=self.pno,doc=self.path))
        self.reset(self.roi_list[self.pno])
        


    def selector_tool_chosen(self, chosen_tool):
        self.__selector_tool_chosen = chosen_tool
        self.__set_chosen_tool()

    def __set_chosen_tool(self):
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
            pass


    def __finished_text_select(self, _):
        # To remove a text selection
        self.start_text_highlight = None
        if self.__selector_tool_chosen == self.AUTO_SELECT_TOOL:
            self.__start_intelligent_analysis()
        self.__send_selection_callback(len(self.__highlighted_chars)>0)


    def __start_intelligent_analysis(self):
        if not self.__highlighted_chars:
            return 
        
        Thread(target=self.__intelligent_analysis_thread).start()

        self.__show_intelligent_popup_menu(self.bottom_x, self.bottom_y)

    

    def __intelligent_analysis_thread(self):

        if self.selected_table and self.selected_cell:
            self.__intelligent_analysis_table()
        elif self.__is_within_list(self.__get_encapsed_bbox(self.__highlighted_chars)):
            self.__intelligent_analysis_list()
        else:
            self.__intelligent_analysis_text()


    def __intelligent_analysis_text(self):
        text_data = self.__given_text()

        highlighted_text = text_data[0][1]

        text_blocks_string, text_blocks_bbox = self.__get_text_blocks_from_chars(self.__highlighted_chars)

        context = {
                    'text_on_page': self.text_in_page,
                    'pno': self.pno,
                    'path': self.path,
                    'text_blocks_string': text_blocks_string,
                    'text_blocks_bbox': text_blocks_bbox,
                    'type': 'text'
        }

        llm_preprocessor = TextDocumentLLMPreprocessor(self.__llm_manager, self.__project_name, self.__acm_data_handler, self.__config)

        
        try:
            result = llm_preprocessor.classify_and_extract(
                    highlighted_text, 
                    context, 
                    'text'
                )
        except Exception as e:
            self.canvas.after(0, self.intelligent_menu.close)
            def show_error(error):
                messagebox.showerror("AI Analysis Error", f"{str(error)}")
            self.canvas.after(0, show_error, e)
            return
                
        
        self.canvas.after(0, self.intelligent_menu.finished_thinking)

        self.__process_result(result, context, highlighted_text)

    
    def __get_text_blocks_from_chars(self, chars, get_block_before=True):
        '''
        Get text blocks from highlighted characters. 

        returns a string of text blocks.
        '''
        if not chars:
            return ''
        
        # Get the bounding box of the highlighted characters
        highlighted_bbox = self.__get_encapsed_bbox(chars)
        
        # Get the raw text data with blocks
        blocks = self.text_doc[self.pno].blocks()
        
        # Sort blocks by y0 coordinate (top to bottom)
        blocks.sort(key=lambda b: b['bbox'][1])
        
        result_blocks = []
        found_block_index = -1
        
        # Find blocks that overlap with the highlighted bbox
        for i, block in enumerate(blocks):
            if 'bbox' in block:
                block_bbox = block['bbox']
                # Check if the block overlaps with highlighted area
                if self.__is_rectangle_overlap(highlighted_bbox, block_bbox):
                    found_block_index = i
                    result_blocks.append(block)
                    break
        
        # If get_block_before is True and we found a block, also include the previous block
        if get_block_before and found_block_index > 0:
            result_blocks.insert(0, blocks[found_block_index - 1])
        
        # Extract text from the blocks
        text_result = ''
        for block in result_blocks:
            for char in block['chars']:
                text_result += char.get('c', '')
            text_result += '\n'

        # Return the combined bbox from the blocks
        combined_bbox = [float('inf'), float('inf'), float('-inf'), float('-inf')]
        for block in result_blocks:
            block_bbox = block['bbox']
            combined_bbox[0] = min(combined_bbox[0], block_bbox[0])
            combined_bbox[1] = min(combined_bbox[1], block_bbox[1])
            combined_bbox[2] = max(combined_bbox[2], block_bbox[2])
            combined_bbox[3] = max(combined_bbox[3], block_bbox[3])
        
        return text_result.strip(), combined_bbox


    def __intelligent_analysis_list(self):

        text_data = self.__given_text()

        highlighted_text = text_data[0][1]

        context = self.extract_lists_with_headers(self.__md_text, highlighted_text, self.__highlighted_chars[0]['bbox'])[0]

        context.update({
                    'text_on_page': self.text_in_page,
                    'pno': self.pno,
                    'path': self.path,
                    'type': 'list'
        })

        llm_preprocessor = TextDocumentLLMPreprocessor(self.__llm_manager, self.__project_name, self.__acm_data_handler, self.__config)

        
        try:
            result = llm_preprocessor.classify_and_extract(
                    highlighted_text, 
                    context, 
                    'list'
                )
        except Exception as e:
            self.canvas.after(0, self.intelligent_menu.close)
            def show_error(error):
                messagebox.showerror("AI Analysis Error", f"{str(error)}")
            self.canvas.after(0, show_error, e)
            return
                
        
        self.canvas.after(0, self.intelligent_menu.finished_thinking)

        self.__process_result(result, context, highlighted_text)



    def __intelligent_analysis_table(self):
        text_data = self.__given_text()
        
        llm_preprocessor = TextDocumentLLMPreprocessor(self.__llm_manager, self.__project_name, self.__acm_data_handler, self.__config)

        full_table = self.selected_table.to_markdown(clean=False)
        

        # Remove header indicator '---'
        full_table = full_table.replace('|---','')
        full_table = full_table.replace('\n|\n','\n')
        

        # Remove the placeholder column names (Col)
        full_table = re.sub(r'Col\d+', '', full_table)

        # Add row and column numbers
        full_table = self.__add_row_col_numbers_to_table(full_table)

        context = {
                    "full_table": full_table,
                    "row_and_column": self.selected_cell,
                    'table_shape': (self.selected_table.col_count, self.selected_table.row_count),
                    'table_bbox': self.selected_table.bbox,
                    'text_on_page': self.text_in_page,
                    'table_object': self.selected_table,
                    'pno': self.pno,
                    'path': self.path,
                    'type': 'table'
                }
        
        highlighted_text = text_data[0][1]
        
        try:
            result = llm_preprocessor.classify_and_extract(
                    highlighted_text, 
                    context, 
                    'table'
                )
        except Exception as e:
            self.canvas.after(0, self.intelligent_menu.close)
            def show_error(error):
                messagebox.showerror("AI Analysis Error", f"{str(error)}")
            self.canvas.after(0, show_error, e)
            return
                
        
        self.canvas.after(0, self.intelligent_menu.finished_thinking)

        self.__process_result(result, context, highlighted_text)


    def extract_lists_with_headers(self, md_text, contained_text, contained_text_bbox=None):

        results = []
        # First Approach: Using page layout analysis
        #=============================================

        # 1. Extract the layout information
        layout = copy.deepcopy(self.__page_layout)
        for item in layout:
            item['bbox'] = [coord // 2 for coord in item['bbox']]  # Convert to pixel values

        # 2. Use the contained_text_bbox to find the list
        index_of_list = -1
        for i, item in enumerate(layout):
            if item['type'] == 'list' and contained_text_bbox:
                if self.__is_rectangle_overlap(item['bbox'], contained_text_bbox):
                    index_of_list = i
                    break

        # 3. Find the nearest preceding header
        if index_of_list != -1:
            for i in range(index_of_list - 1, -1, -1):
                if layout[i]['type'] in ['text', 'title']:
                    results.append({
                        'list_heading': self.__get_text_within_bbox(layout[i]['bbox'])[0],
                        'full_list': self.__get_text_within_bbox(layout[index_of_list]['bbox'])[0],
                        'list_bbox': layout[index_of_list]['bbox'],
                        'header_bbox': layout[i]['bbox']
                    })
                    break

        if results:
            return results

        # Second Approach: Using markdown and BeautifulSoup
        #======================================================

        # 1. Convert Markdown to HTML
        html_text = markdown.markdown(md_text)
        
        # 2. Parse the HTML with BeautifulSoup
        soup = BeautifulSoup(html_text, 'html.parser')
        
        # 3. Iterate through elements and extract headers and lists
        current_header = None
        
        for element in soup.contents:
            if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                current_header = element.get_text(strip=True)
            elif element.name in ['ul', 'ol']:
                if current_header:
                    list_items = [item.get_text(strip=True) for item in element.find_all('li')]
                    results.append({
                        'list_heading': current_header,
                        'full_list': list_items,
                        'list_bbox': self.__get_text_bbox(list_items),
                        'header_bbox': self.__get_text_bbox(current_header)
                    })
                # Reset current_header if you only want the *immediately* preceding header
                # and not for subsequent lists
                # current_header = None

        # filter results to only include those with the contained_text
        results = [res for res in results if any(contained_text in item for item in res['full_list'])]

        return results
    
    def __get_text_bbox(self, text):
        
        if isinstance(text, list):
            bboxes = []
            for t in text:
                bbox = self.__get_text_bbox(t)
                # Create a bounding box that encompasses all bboxes
                if bbox:
                    bboxes.append(bbox)

            if bboxes:
                min_x = min(b[0] for b in bboxes)
                min_y = min(b[1] for b in bboxes)
                max_x = max(b[2] for b in bboxes)
                max_y = max(b[3] for b in bboxes)
                return [min_x, min_y, max_x, max_y]

        text_page = self.text_doc[self.pno]
        r1 = text_page.search_for(text)
        return text_page.get_textbox(r1[0]) if r1 else None


    def __process_result(self, result, context, highlighted_text):

        if result["classification"].get("category") == TextDocumentLLMPreprocessor.PARAMETER:
            tagname_objects = result["tagname_extraction"].get("objects")

            if not tagname_objects:
                return
            
            # Add additional command options
            for _, tagname_object in tagname_objects.items():
                object_name = tagname_object["name"]
                if not object_name:
                    continue
                predicted_parameters = tagname_object["parameters"]["matched_parameters"]
                predicted_parameter = predicted_parameters[0]['parameter_name'] if predicted_parameters else ""
                
                def func():
                    self.__add_new_parameter_linked_text(object_name, 
                                                         predicted_parameter, 
                                                         context, 
                                                         highlighted_text,
                                                         result)

                self.intelligent_menu.add_command(f"Add Parameter for {object_name}", func)
        elif result["classification"].get("category") == TextDocumentLLMPreprocessor.INTERLOCK:
            tagname_objects = result["interlock_extraction"].get("interlock_objects")

            if not tagname_objects:
                return
            
            # Add additional command options
            for _, tagname_object in tagname_objects.items():
                
                object_name = tagname_object["name"]
                if not object_name:
                    continue
                def func(subobject):
                    self.__add_new_subobject_linked_text(object_name, 
                                                         subobject, 
                                                         context, 
                                                         highlighted_text,
                                                         result)
                for subobject in tagname_object.get("subobjects", []):
                    self.intelligent_menu.add_command(f"Add {subobject} for {object_name}", lambda subobject=subobject: func(subobject))


    def get_table_cell_overlapping_bbox(self, bbox):
        if not self.tables_in_page:
            return None

        selected_table = None
        for table in self.tables_in_page:
            if self.__is_rectangle_overlap(bbox, table.bbox):
                selected_table = table
                break

        if not selected_table:
            return None

        

        # Find the cell within the selected table that overlaps with the bbox
        for row_index, row in enumerate(selected_table.rows):
            for col_index, cell in enumerate(row.cells):
                if cell and self.__is_rectangle_overlap(bbox, cell):
                    selected_cell = [row_index, col_index]
                    selected_cell_full_text, selected_cell_full_indexes = self.__get_text_within_bbox(selected_table.rows[row_index].cells[col_index])
                    selected_table_shape = [selected_table.col_count,selected_table.row_count]
                    return selected_cell, selected_cell_full_text, selected_cell_full_indexes, selected_table_shape, selected_table.bbox

        return None


    def pass_parameter_back_text_selection(self, pre_result, context, highlighted_text, parameter_properties, callback):
        processor = TextDocumentLLMPostProcessor(self.__llm_manager, self.__project_name, self.__acm_data_handler, self.__db, self.__config)

        def process_post_thread():
            try:
                post_result = processor.post_process_paramter_extraction(pre_result, context, highlighted_text, parameter_properties, self.selected_table, self.text_doc[self.pno])
            except Exception as e:
                self.canvas.after(0, self.intelligent_menu.close)
                def show_error(error):
                    messagebox.showerror("AI Analysis Error", f"{str(error)}")
                self.canvas.after(0, show_error, e)
                return

            # Post-processor returns ``None`` when the extracted annotation
            # duplicates one already persisted on this page; skip the callback
            # so no duplicate LinkedText is created.
            if post_result is None:
                self.canvas.after(0, self.intelligent_menu.close)
                return

            tagname_linked_text_data = self.process_post_result(post_result['tagname'])
            parameter_linked_text_data = self.process_post_result(post_result['parameter'])

            callback(parameter_properties, tagname_linked_text_data, parameter_linked_text_data)

        Thread(target=process_post_thread).start()


    def pass_subobject_back_text_selection(self, subobject, pre_result, context, highlighted_text, callback):
        processor = TextDocumentLLMPostProcessor(self.__llm_manager, self.__project_name, self.__acm_data_handler, self.__db, self.__config)

        def process_post_thread():
            processor.post_process_dependency_extraction(subobject
                                                            ,pre_result
                                                            , context
                                                            , highlighted_text
                                                            , self.selected_table
                                                            , self.text_doc[self.pno]
                                                            , self.text_in_page
                                                            , callback)


        Thread(target=process_post_thread).start()
        

    def process_post_result(self, post_result):
        get_table_cell_overlapping_bbox = self.get_table_cell_overlapping_bbox(post_result['bbox'])
        if not get_table_cell_overlapping_bbox:
            return
        cell = get_table_cell_overlapping_bbox[0]
        cell_full_text = get_table_cell_overlapping_bbox[1]
        cell_full_indexes = get_table_cell_overlapping_bbox[2]
        table_shape = get_table_cell_overlapping_bbox[3]
        table_bbox = get_table_cell_overlapping_bbox[4]
        text_data = self.__get_text_within_bbox(post_result['bbox'],True)
        if not text_data: 
            return 
        indexes = text_data[1]
        font = text_data[2]
        given_linked_text = [[cell_full_text, post_result['raw_text']]
                            ,indexes[0]
                            ,indexes[1]
                            ,(cell, table_shape, False, font, table_bbox, cell_full_indexes)
                            ,self.pno
                            ,self.path
                            ,Database.TEXT]
        
        # Get the indexes of post_result['raw_text'] in cell_full_text
        key_indexes = self.__find_substring_indexes(cell_full_text, post_result['raw_text'])

        key_linked_text = [post_result['raw_text'], cell_full_text, key_indexes]

        return {
            'given_text': given_linked_text,
            'key_text': key_linked_text
        }
    


    def __find_substring_indexes(self, string:str, substring:str):
        start_index = string.find(substring)
        if start_index == -1:
            return []
        end_index = start_index + len(substring)
        return [start_index, end_index]




    def __show_intelligent_popup_menu(self, x, y):
        # Convert canvas coordinates to screen coordinates accounting for scrolling
        
        # Convert canvas coordinates back to widget coordinates
        widget_x = x - self.canvas.canvasx(0)
        widget_y = y - self.canvas.canvasy(0)
        
        # Convert widget coordinates to screen coordinates
        screen_x = self.canvas.winfo_rootx() + widget_x + 2
        screen_y = self.canvas.winfo_rooty() + widget_y + 2
        
        self.intelligent_menu.add_command("Copy", self.__copy_text)
        self.intelligent_menu.add_command("Highlight", self.__copy_text)
        self.intelligent_menu.add_separator()
        self.intelligent_menu.show_thinking_at(screen_x, screen_y)


    def __cursor_tool(self):
        self.canvas.unbind('<ButtonPress-1>')
        self.canvas.unbind('<ButtonRelease-3>') 
        self.canvas.unbind('<Motion>') 
        self.canvas.unbind('<Delete>')
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.unbind('<Control-c>')
        self.canvas.unbind('<Alt-v>')
        self.canvas.unbind('<Alt-a>')
        self.canvas.unbind('<Alt-d>')
        self.canvas.unbind('<Up>')
        self.canvas.unbind('<Down>')
        # Reset the cursor to the default
        self.canvas.config(cursor="")

        self.canvas.bind('<ButtonRelease-3>', self.on_right_click)  # call popup menu
        self.canvas.bind('<Motion>', self.motion)  # handle mouse motion
        self.canvas.bind("<ButtonPress-1>", self.on_select_press)
        self.canvas.bind("<ButtonRelease-1>",self.__finished_text_select)
        self.canvas.bind('<B1-Motion>',self.__on_text_move_press)
        self.canvas.bind('<Double-Button-1>', self.__highlight_selected_regex_text_matches)
        self.canvas.bind('<Control-c>', self.__copy_text)
        self.canvas.bind('<Alt-v>', self.__view_link)
        self.canvas.bind('<Alt-a>', lambda e: self.__accept(True))
        self.canvas.bind('<Alt-d>', lambda e: self.__reject(True))
        self.canvas.bind('<Up>', lambda e: self.__move_to_previous_unapproved_linked_texts(self.selected_poly))
        self.canvas.bind('<Down>', lambda e: self.__move_to_next_unapproved_linked_texts(self.selected_poly))
        self.canvas.config(cursor="xterm")

    def __auto_select_tool(self):
        self.canvas.unbind('<ButtonPress-1>')
        self.canvas.unbind('<ButtonRelease-3>') 
        self.canvas.unbind('<Motion>') 
        self.canvas.unbind('<Delete>')
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.unbind('<Control-c>')
        self.canvas.unbind('<Alt-v>')
        self.canvas.unbind('<Alt-a>')
        self.canvas.unbind('<Alt-d>')
        self.canvas.unbind('<Up>')
        self.canvas.unbind('<Down>')
        # Reset the cursor to the default
        self.canvas.config(cursor="")

        self.canvas.bind('<ButtonRelease-3>', self.on_right_click)  # call popup menu
        self.canvas.bind('<Motion>', self.motion)  # handle mouse motion
        self.canvas.bind("<ButtonPress-1>", self.on_select_press)
        self.canvas.bind("<ButtonRelease-1>",self.__finished_text_select)
        self.canvas.bind('<B1-Motion>',self.__on_text_move_press)
        self.canvas.bind('<Double-Button-1>', self.__highlight_selected_regex_text_matches)
        self.canvas.bind('<Control-c>', self.__copy_text)
        self.canvas.bind('<Alt-v>', self.__view_link)
        self.canvas.bind('<Alt-a>', lambda e: self.__accept(True))
        self.canvas.bind('<Alt-d>', lambda e: self.__reject(True))
        self.canvas.bind('<Up>', lambda e: self.__move_to_previous_unapproved_linked_texts(self.selected_poly))
        self.canvas.bind('<Down>', lambda e: self.__move_to_next_unapproved_linked_texts(self.selected_poly))
        self.canvas.config(cursor="xterm")

    def __hand_tool(self):
        self.canvas.unbind('<ButtonPress-1>')
        self.canvas.unbind('<ButtonRelease-3>') 
        self.canvas.unbind('<Motion>') 
        self.canvas.unbind('<Delete>')
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.unbind('<Double-Button-1>')
        self.canvas.unbind('<Control-c>')
        self.canvas.unbind('<Alt-v>')
        self.canvas.unbind('<Alt-a>')
        self.canvas.unbind('<Alt-d>')
        self.canvas.unbind('<Up>')
        self.canvas.unbind('<Down>')
        self.canvas.config(cursor="")

        self.canvas.bind('<ButtonPress-1>', self.move_from)  # remember canvas position
        self.canvas.bind('<B1-Motion>', self.move_to)  # move canvas to the new position
        self.canvas.bind("<ButtonRelease-1>",self.__finished_text_select)


    def __rectangular_tool(self):
        pass

    def __polygon_tool(self):
        pass

    def __highlight_selected_regex_text_matches(self, event):
        pass
        

    def __add_to_layer(self, layer, command, *args, **kwargs):
        layer_tag = "layer %s" % layer
        if layer_tag not in self.__layers: self.__layers.append(layer_tag)
        tags = kwargs.get("tags", ())
        tags = tags + (layer_tag,)
        kwargs['tags'] = tags
        item_id = command(*args, **kwargs)
        self.__adjust_layers()
        return item_id

    def __adjust_layers(self):
        for layer in sorted(self.__layers):
            self.canvas.lift(layer)    


    def ___create_text_select_rectangle(self, X1, Y1, X2, Y2, **kwargs):
        
        x1 = int(X1)
        y1 = int(Y1)
        x2 = int(X2)
        y2 = int(Y2)
        image = Image.new('RGBA', (x2-x1, y2-y1), (0,102,204,127))
        scan_image = ImageTk.PhotoImage(image)
        tags = (self.tag_highlighted_text,)
        return scan_image, self.__add_to_layer(1, self.canvas.create_image, x1, y1, image=scan_image, anchor='nw',tags=tags,**kwargs)
    

    

    def get_selected_roi(self, _=None,__=None,pno=0):
        """ Passes the selected region to the linked Graphic object """
        
        text = ''
        indexes = []
        for char in self.__highlighted_chars:
            text = text + char['c']
            indexes.append(char['index'])

        # Remove trailing or leading spaces from text and indexes
        while text and text[0].isspace():
            text = text[1:]
            indexes.pop(0)

        while text and text[-1].isspace():
            text = text[:-1]
            indexes.pop(-1)


        is_within_list = self.__is_within_list(self.__get_encapsed_bbox(self.__highlighted_chars))

        return text, indexes, (self.__cell_cooordinates, self.selected_table, is_within_list), self.pno, self.path, (self.text_in_page, self.text_doc[pno]),Database.TEXT
        

        
    
    def __get_encapsed_bbox(self, chars):
        """
        Calculate the bounding box that encapsulates a list of characters.

        Args:
            chars (list of dict): A list of dictionaries where each dictionary 
                                  represents a character and contains a 'bbox' key 
                                  with a tuple of four values (x0, y0, x1, y1).

        Returns:
            tuple: A tuple containing four values (minX, minY, maxX, maxY) 
                   representing the coordinates of the encapsulated bounding box.
        """
        if not chars:
            # Return coordinates that will not overlap with any other bounding box
            return [-1, -1, -1, -1]
        minX = min(l['bbox'][0] for l in chars)
        minY = min(l['bbox'][1] for l in chars)
        maxX = max(l['bbox'][2] for l in chars)
        maxY = max(l['bbox'][3] for l in chars)
        return minX, minY, maxX, maxY
    

    def __is_within_list(self, bbox):
        for i in range(len(self.__page_layout)):
            if self.__page_layout[i]['type'] != 'list':
                continue

            table_bbox = [x//2 for x in self.__page_layout[i]['bbox']] # 2 is default page zoom
            if self.__is_rectangle_overlap(table_bbox,bbox):
                    return True
            
        # Extract text content from the bbox to find in markdown
        bbox_text = ""
        for char in self.text_in_page:
            if self.__is_bbox_within_bbox(char['bbox'], bbox):
                bbox_text += char['c']
        
        if not bbox_text.strip():
            return False
        
        # Parse markdown to find lists
        lines = self.__md_text.split('\n')
        in_list = False
        
        for line in lines:
            # Check for unordered list items (-, *, +)
            if re.match(r'^\s*[-*+]\s+', line):
                in_list = True
                # Check if our bbox text is in this list item
                if bbox_text.strip() in line:
                    return True
            # Check for ordered list items (1., 2., etc.)
            elif re.match(r'^\s*\d+\.\s+', line):
                in_list = True
                # Check if our bbox text is in this list item
                if bbox_text.strip() in line:
                    return True
            # Check for continuation of list (indented text)
            elif in_list and re.match(r'^\s{2,}', line) and line.strip():
                # Check if our bbox text is in this continued list content
                if bbox_text.strip() in line:
                    return True
            # Empty line or non-list content breaks the list context
            elif not line.strip() or not re.match(r'^\s', line):
                in_list = False
        
            
        return False


    def setup_highlighted_linked_text(self, linked_text_id , tagname_indexes, subobject_indexes):

        self.remove_mark_with_editing()

        if tagname_indexes is None:
            return
        
        tagname_lines = {}
        for _, char in enumerate(self.text_in_page[tagname_indexes[0]:tagname_indexes[1]]):
            self.__build_highlight_lines(tagname_lines,char)

        for tagname_line in tagname_lines.values():
            self.mark_with_editing(tagname_line,False)
        
        
        if subobject_indexes:
            subobject_lines = {}
            for _, char in enumerate(self.text_in_page[subobject_indexes[0]:subobject_indexes[1]]):
                self.__build_highlight_lines(subobject_lines,char)

            for subobject_line in subobject_lines.values():
                self.mark_with_editing(subobject_line,False)

        self.refresh_image()

        
    def remove_highlight_linked_text(self):
        self.__remove_highlight_regex_template(remove_key_ignore_marks=True)
        self.remove_mark_with_editing()

    

    def setup_regex_template(self, indexes, key_indexes, ignore_indexes, regex_string, given_text_id, type
                             , parameter=None, is_table=False, roi=None, table_shape=None, table_bbox=None, show_regex_matches=True):
        """ Sets up a given as a text based text highlightable roi"""
        
        self.__remove_highlight_regex_template(refresh_image=False)
        self.remove_mark_with_strikeout(refresh_image=False)
        self.remove_mark_with_underline(refresh_image=False)
        self.remove_mark_with_highlight(refresh_image=False)

        
                

        self.__selected_given_text = []
        self.__selected_text = []
        lines_to_highlight = {}
        for i, char in enumerate(self.text_in_page[indexes[0]:indexes[1]]):
            char['index'] = indexes[0]+i
            if is_table:
                if table_bbox and not self.__is_bbox_within_row_column(char['bbox'], table_bbox, roi[0], roi[1]):
                    continue
                self.__selected_given_text.append(char)
                self.__selected_text.append(char)
                self.__build_highlight_lines(lines_to_highlight,char)
            else:
                self.__selected_given_text.append(char)
                self.__selected_text.append(char)
                self.__build_highlight_lines(lines_to_highlight,char)

        if show_regex_matches:
            for line in lines_to_highlight.values():
                self.mark_with_highlight(line,False)

        if type != 'parameter':
            self.__selected_given_texts[type] = {
                'chars': self.__selected_given_text
            }
        else:
            if type not in self.__selected_given_texts:
                self.__selected_given_texts[type] = {}
            self.__selected_given_texts[type][parameter] = {
                'chars': self.__selected_given_text
            }

        
        processed_indexes = []
        if key_indexes:
            for key_index in key_indexes:
                for char in self.text_in_page[indexes[0]+key_index[0]:indexes[0]+key_index[-1]]:
                    if char['bbox'] in processed_indexes:
                        continue
                    processed_indexes.append(char['bbox'])
                    self.mark_with_underline(char['bbox'],False)
        
        processed_indexes = []
        if ignore_indexes:
            for ignore_index in ignore_indexes:

                for char in self.text_in_page[indexes[0]+ignore_index[0]:indexes[0]+ignore_index[-1]]:
                    if char['bbox'] in processed_indexes:
                        continue
                    processed_indexes.append(char['bbox'])
                    self.mark_with_strikeout(char['bbox'],False)
        
        if regex_string and show_regex_matches:
            self.__run_regex_matching(regex_string , is_table, roi, table_shape)
        
        self.refresh_image()

    
    def __is_bbox_within_row_column(self, char_bbox, table_bbox, row_index, col_index):
        
        for table in self.tables_in_page:
            if self.__is_rectangle_overlap(table_bbox, table.bbox):
                if row_index < len(table.rows):
                    if col_index < len(table.rows[row_index].cells):
                        cell_bbox = table.rows[row_index].cells[col_index]
                        return self.__is_rectangle_overlap(char_bbox, cell_bbox)


    def move_to_roi(self, roi, pno):
        self.__go_to_roi = roi
        self.__go_to_pno = pno
        self.canvas.after(1000,self.__move_to_roi)

    def __move_to_roi(self):
        """ Move the canvas to the a region of interest """

        if self.pno != self.__go_to_pno:
            self.zoom(100)
            self.go_to_page(self.__go_to_pno + 1)

        self.__lines_to_highlight = {}

        self.__highlighted_chars = []

        char_indexes = self.__go_to_roi[1]
        for i in range(len(self.text_in_page)):
            char = self.text_in_page[i]
            char['index'] = i
            if i >= char_indexes[0] and i < char_indexes[1]:
                self.__highlighted_chars.append(char)
                self.__build_highlight_lines(self.__lines_to_highlight,char)

        self.__create_highlight_rect_images()
            

    def __clear_highlighted_text(self):
        self.intelligent_menu.close()
        self.__lines_to_highlight = {}
        self.__highlight_rect_images = {}
        self.__highlighted_chars = []
        self.selected_cell = None 
        self.selected_table_shape = None 
        self.selected_table_bbox = None
        self.selected_table = None
        self.selected_cell_full_text = None
        self.selected_cell_full_indexes = None
        self.__first_char_bbox = None
        self.canvas.delete(self.tag_highlighted_text)



    def __highlight_line(self, x, y):

        if (self.start_text_highlight is None):
            self.__selected_table_text([x,y])
            self.start_text_highlight = [x,y]
            self.__first_char_bbox = None

        self.__lines_to_highlight = {}

        self.__highlighted_chars = []
        

        # Handle forward and reverse direction 
        if self.__first_char_bbox and self.__first_char_bbox[1] <= y:
            start = self.start_text_highlight
            end = (x,y)
        else:
            start = (x,y)
            end = self.start_text_highlight

        bbox2 = self.canvas.coords(self.container)  # get image area

        self.bottom_x = 0
        self.bottom_y = 0
        for i in range(len(self.text_in_page)):
            char = self.text_in_page[i]
            char['index'] = i
            char_bbox = (char['bbox'][0] * self.imscale + bbox2[0]
                        ,char['bbox'][1] * self.imscale + bbox2[1]
                        ,char['bbox'][2] * self.imscale + bbox2[0]
                        ,char['bbox'][3] * self.imscale + bbox2[1])
            
            if self.__cell_cooordinates and not self.__is_within_table(char_bbox):
                continue

            if self.__is_within_same_line_as_start(char_bbox, start, end):
                self.__highlighted_chars.append(char)
                self.__build_highlight_lines(self.__lines_to_highlight,char)
                if self.__first_char_bbox is None:
                    self.__first_char_bbox = char_bbox

            elif self.__is_middle_line(char_bbox, start, end):
                self.__highlighted_chars.append(char)
                self.__build_highlight_lines(self.__lines_to_highlight,char)
                if self.__first_char_bbox is None:
                    self.__first_char_bbox = char_bbox

            elif self.__is_within_same_line_as_end(char_bbox, start, end):
                self.__highlighted_chars.append(char)
                self.__build_highlight_lines(self.__lines_to_highlight,char)
                if self.__first_char_bbox is None:
                    self.__first_char_bbox = char_bbox

            


        self.__create_highlight_rect_images()

        if self.__tool_panel_selected_text_callback:
            self.__tool_panel_selected_text_callback(self.__highlighted_chars,self.path,self.pno,self.__type)



    def __is_within_table(self, char_bbox):
        cell_x1, cell_y1, cell_x2, cell_y2 = self.__cell_cooordinates
        return (char_bbox[0] >= cell_x1 and 
                char_bbox[2] <= cell_x2 and 
                char_bbox[1] >= cell_y1 and 
                char_bbox[3] <= cell_y2)


        
    def __selected_table_text(self, start):

        
        self.selected_cell = None
        self.selected_table_row = None
        self.selected_table_header = None
        self.selected_table_bbox = None
        self.selected_table_shape = None 
        self.selected_cell_full_text = None
        self.selected_cell_full_indexes = None
        self.__cell_cooordinates = None
    
        bbox2 = self.canvas.coords(self.container)  # get image area

        for table in self.tables_in_page:
            if (start[0] >= table.bbox[0] * self.imscale + bbox2[0] 
                and start[0] <= table.bbox[2] * self.imscale + bbox2[0] 
                and start[1] >= table.bbox[1] * self.imscale + bbox2[1]
                and start[1] <= table.bbox[3] * self.imscale + bbox2[1]):
                for i in range(len(table.rows)):
                    for j in range(len(table.rows[i].cells)):

                        if table.rows[i].cells[j] is None:
                            continue

                        cell_x1 = table.rows[i].cells[j][0] * self.imscale + bbox2[0]
                        cell_y1 = table.rows[i].cells[j][1] * self.imscale + bbox2[1]
                        cell_x2 = table.rows[i].cells[j][2] * self.imscale + bbox2[0]
                        cell_y2 = table.rows[i].cells[j][3] * self.imscale + bbox2[1]
                        if (start[0] >= cell_x1 and 
                            start[0] <= cell_x2 and 
                            start[1] >= cell_y1 and 
                            start[1] <= cell_y2):
                            cell_bbox = [cell_x1, cell_y1, cell_x2, cell_y2]
                            self.__cell_cooordinates = cell_bbox
                            self.selected_cell = (i,j)
                            self.selected_cell_full_text, self.selected_cell_full_indexes = self.__get_text_within_bbox(table.rows[i].cells[j])
                            self.selected_table = table
                            self.selected_table_row = i
                            self.selected_table_header = table.header
                            self.selected_table_bbox = table.bbox
                            self.selected_table_shape = [table.col_count,table.row_count]
        
    
    def __get_text_within_bbox(self, bbox, get_font=False):
        # ``end`` is exclusive so callers can slice ``text_in_page[start:end]``.
        text = ''
        start = np.inf
        end = 0
        for i in range(len(self.text_in_page)):
            char = self.text_in_page[i]
            char_bbox = char['bbox']
            if (char_bbox[0] >= bbox[0] and 
                char_bbox[2] <= bbox[2] and 
                char_bbox[1] >= bbox[1] and 
                char_bbox[3] <= bbox[3]):
                text += char['c']
                if i < start:
                    start = i
                if i >= end:
                    end = i + 1
            if get_font:
                font = char.get('font', None)
        if text and get_font:
            return text, [start,end], font
        elif text:
            return text, [start,end]


    def __create_highlight_rect_images(self):


        self.__highlight_rect_images = {}
        if self.__lines_to_highlight is None:
            return

        self.bottom_x = -np.inf
        self.bottom_y = -np.inf
        for line_key,line in self.__lines_to_highlight.items():
            bbox2 = self.canvas.coords(self.container)  # get image area
            line_bbox = (line[0] * self.imscale + bbox2[0]
                            ,line[1] * self.imscale + bbox2[1]
                            ,line[2] * self.imscale + bbox2[0]
                            ,line[3] * self.imscale + bbox2[1])
            image, id = self.___create_text_select_rectangle(line_bbox[0],
                                                    line_bbox[1],
                                                    line_bbox[2],
                                                    line_bbox[3])
            self.__highlight_rect_images[line_key] = image

            if line_bbox[2] > self.bottom_x:
                self.bottom_x = line_bbox[2]

            if line_bbox[3] > self.bottom_y:
                self.bottom_y = line_bbox[3]



    def __is_rectangle_vertical_overlap(self, R1, R2):
        if  (int(R1[3])<int(R2[1])) or (int(R1[1])>int(R2[3])):
            return False
        else:
            return True


    def __build_highlight_lines(self, lines_to_highlight, char):

        line_key = "{:.2f} {:.2f}".format(char['bbox'][1],char['bbox'][3])

        for existing_line_key, bbox in lines_to_highlight.items():
            
            if self.__is_rectangle_vertical_overlap(bbox,char['bbox']):
            
                lines_to_highlight[existing_line_key][1] = min(bbox[1],char['bbox'][1])
                lines_to_highlight[existing_line_key][3] = max(bbox[3],char['bbox'][3])

                line_key = existing_line_key 


        if line_key not in lines_to_highlight:
  
            lines_to_highlight[line_key] = [char['bbox'][0]
                                            ,char['bbox'][1]
                                            ,char['bbox'][2]
                                            ,char['bbox'][3]]
        
        line = lines_to_highlight[line_key]

        # If the current character is to the left of the line 
        # then extend the line to the left
        if line[2]< char['bbox'][2]:
            line[2] = char['bbox'][2]

        lines_to_highlight[line_key] = line


            
    def __is_within_same_line_as_start(self, char, start, end):
        a = char[0] >= start[0]
        b = char[3] > end[1]
        c = char[1] < start[1]
        d = char[2] < end[0]
        return (((char[0] >= start[0]
                 and char[1] < start[1]
                 and char[2] < end[0]
                 and char[3] > end[1]) or 
                 (char[0]<start[0] 
                 and char[2]>start[0] 
                 and char[1]<start[1] 
                 and char[3]>start[1]) or 
                 (char[0]<end[0] 
                 and char[2]>end[0] 
                 and char[1]<end[1] 
                 and char[3]>end[1])) or
                 (char[0] >= start[0]
                 and char[1] < start[1]
                 and char[3] > start[1]
                 and char[3] < end[1]))

    
    def __is_middle_line(self, char, start, end):
        return ((char[1] > start[1]
                 and char[3] < end[1])) 

    def __is_within_same_line_as_end(self, char, start, end):
        return ((char[1] < end[1] 
                and char[3] > end[1]
                 and char[1] > start[1])
                 and char[0] < end[0]) 


    def highlight_text(self):
        i = self.canvas.find_withtag('current')  # id of the current object
        tags = self.canvas.gettags(i)  # get tags of the current object
        
        #self.__selecting_text = True
        if 'text_roi' in tags:  
            self.__selecting_text = True
            
            self.canvas.config(cursor="xterm")
            
        else:
            self.canvas.config(cursor="")
            #self.__selecting_text = False
            
        self.__selecting_text = True
            
        self.canvas.config(cursor="xterm")

   
    def on_select_press(self, event):
        self.canvas.focus_set() 
        # create rectangle if not yet exist
        #if not self.rect:

        if self.__shown_tooltip:
            self.__unapproved_toolips[self.__shown_tooltip].hide()
            self.__shown_tooltip = None

        for selected_poly in self.selected_poly:
            self.canvas.itemconfigure(selected_poly, outline='', width=0)
        i = self.canvas.find_withtag('current')  # id of the current object
        tags = self.canvas.gettags(i)  # get tags of the current object
        if self.tag_poly_line in tags and 'poly' in tags:
            self.canvas.itemconfigure(tags[1], outline=self.color_roi['point'], width=2)  # select lines
            self.selected_poly.clear()
            self.selected_poly.append(tags[1])

        self.__clear_highlighted_text()


    def __on_text_move_press(self, event):
        
        curX, curY = ( self.canvas.canvasx(event.x),  self.canvas.canvasy(event.y))

        #if self.__selecting_text:
        #self.__select_text(curX, curY) 
        self.__highlight_line(curX, curY)
            #return 
        '''else: 
            if self.__clear_selected_shown_text:
                self.__clear_selected_shown_text()'''
        

    def highlight_rect(self):
        """ Select and change color of the current roi object """
        i = self.canvas.find_withtag('current')  # id of the current object
        tags = self.canvas.gettags(i)  # get tags of the current object
        if self.tag_poly_line in tags and 'rect' in tags:  # if it's a polyline. 2nd tag is ALWAYS a unique tag ID
            j = tags[1] + self.tag_rect_const  # unique tag of the rectangle
            self.canvas.itemconfigure(tags[1], fill=self.color_roi['point'])  # select lines
            self.canvas.itemconfigure(j, state='normal')  # show rectangle
            self.highlighted_rect.append(tags[1])  # remember 2nd unique tag_id

  

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
            


   
    
    def draw_polygon(self, polygon, color, tag, dictionary, tag_uid=None, parameter_type=''):
        """ Draw polygon on the canvas """

        if not self.canvas_up:
            return
        
        # Calculate coordinates of vertices on the zoomed image
        bbox = self.canvas.coords(self.container)  # get image area
        vertices = list(map((lambda i: (i[0] * self.imscale + bbox[0],
                                        i[1] * self.imscale + bbox[1])), polygon))
        if not tag_uid:
            # Create identification tag
            tag_uid = str(uuid.uuid4())  # unique ID
        # Create polygon. 2nd tag is ALWAYS a unique tag ID + constant string.
        self.canvas.create_polygon(vertices, fill='', width=0, outline='',
                                   tags=(self.tag_poly_line, tag_uid, 'poly',tag, parameter_type))
        
        dictionary[tag_uid] = polygon.copy()


    def delete_polygon(self, id):
        """ Delete polygon """
        self.canvas.delete(id)  # delete polygon


    def popup(self, event):
        """ Popup menu """
        self.motion(event)  # select polygon with popup menu explicitly to be sure it is selected
        i = self.canvas.find_withtag('current')  # id of the current object
        tags = self.canvas.gettags(i)  # get tags of the current object

        if self.tag_highlighted_text in tags:
            self.hold_menu1 = True  # popup menu is opened
            self.hold_menu2 = True
            
            self.menu.post(event.x_root, event.y_root)  # show popup menu
            self.hold_menu1 = False  # popup menu is closed


        
    def __given_text(self, option=None):
        if option is None:
            return self.__given_text_no_option()
        else:
            return self.__given_text_with_option(option)
        

    def __given_text_no_option(self):
        
        self.__selected_given_text = []
        self.__selected_text = []
        text = ''
        for char in self.__highlighted_chars:
            self.__selected_given_text.append({'index':char['index'],
                                               'c':char['c'],
                                               'bbox':char['bbox']})
            self.__selected_text.append(char)
            text = text + char['c']

        # Remove trailing or leading spaces from text and indexes
        while text and text[0].isspace():
            text = text[1:]
            self.__selected_text.pop(0)

        while text and text[-1].isspace():
            text = text[:-1]
            self.__selected_text.pop(-1)


        font = self.__get_selected_text_font()

        def get_index(char):
            return char['index']

        self.__selected_given_text.sort(key=get_index)

        if not self.__selected_given_text:
            return None

        is_within_list = self.__is_within_list(self.__get_encapsed_bbox(self.__highlighted_chars))

        return ([self.selected_cell_full_text,text]
                ,self.__selected_given_text[0]['index']
                ,self.__selected_given_text[-1]['index']+1
                ,(self.selected_cell, self.selected_table_shape, is_within_list, font, self.selected_table_bbox, self.selected_cell_full_indexes)
                ,self.pno
                ,self.path
                ,Database.TEXT)
    

    def __given_text_with_option(self, option):
        text_in_page_list = self.text_in_page_string.split()

        # Only alphanumeric comparison
        option = re.sub(r'[^a-zA-Z0-9]', '', option)

        text_in_page_dict = {re.sub(r'[^a-zA-Z0-9]', '', t): t for t in text_in_page_list}

        option_in_page = text_in_page_dict[process.extractOne(option, list(text_in_page_dict.keys()))[0]]
        
        option_rects = self.text_doc[self.pno].search_for(option_in_page)
        # Get the closest rectangle to the selected text that comes before it on the page
        
        if not self.__highlighted_chars:
            return None
        
        selected_bbox = self.__get_encapsed_bbox(self.__highlighted_chars)
        
        closest_rect = None
        min_distance = float('inf')
        
        for rect in option_rects:
            # Check if this option comes before the selected text on the page
            # (either above it, or on the same line but to the left)
            if rect.y1 < selected_bbox[1] or (rect.y0 < selected_bbox[3] and rect.x1 < selected_bbox[0]):
                # Calculate distance (vertical distance is more important than horizontal)
                vertical_distance = abs(selected_bbox[1] - rect.y1)
                horizontal_distance = abs(selected_bbox[0] - rect.x0)
                distance = vertical_distance * 2 + horizontal_distance  # Weight vertical more
                
                if distance < min_distance:
                    min_distance = distance
                    closest_rect = rect
        
        if not closest_rect:
            return None
        
        # Get the text and indexes for the option
        option_text_data = self.__get_text_within_bbox(closest_rect, get_font=True)
        if not option_text_data:
            return None
        
        option_text = option_text_data[0]
        option_indexes = option_text_data[1]
        option_font = option_text_data[2]
        
        # Build the selected_given_text for the option
        option_given_text = []
        for i in range(option_indexes[0], option_indexes[1]):
            char = self.text_in_page[i]
            option_given_text.append({'index': char['index'],
                                     'c': char['c'],
                                     'bbox': char['bbox']})
        
        # Get cell information if within a table
        cell_info = self.get_table_cell_overlapping_bbox(closest_rect)
        if cell_info:
            cell = cell_info[0]
            cell_full_text = cell_info[1]
            cell_full_indexes = cell_info[2]
            table_shape = cell_info[3]
            table_bbox = cell_info[4]
        else:
            cell = None
            cell_full_text = option_text
            cell_full_indexes = option_indexes
            table_shape = None
            table_bbox = None
        
        is_within_list = self.__is_within_list(closest_rect)
        
        return ([cell_full_text, option_text]
                , option_indexes[0]
                , option_indexes[1]
                , (cell, table_shape, is_within_list, option_font, table_bbox, cell_full_indexes)
                , self.pno
                , self.path
                , Database.TEXT)
            

    def __get_selected_text_font(self):
        font = ''

        for char in self.__selected_text:
            if font == '':
                font = char['font']
            elif font == char['font']:
                continue
            elif font != char['font']:
                return None
        
        return font
    


    KEY_INDICATOR = '<KEY_CHAR>'
    IGNORE_INDICATOR = '<IGNORE_CHAR>'
    IGNORE_ANY_WITHOUT_PERIOD = '[^.]*'
    KEY_ANY_WITHOUT_PERIOD = '([^.]*)'

    def __run_regex_matching(self, regex_string, is_table=False, roi=None, table_shape=None):

        if is_table:
            self.__run_regex_matching_for_tables(regex_string, roi, table_shape)
        else:
            self.__run_regex_matching_for_text(regex_string)



    def __run_regex_matching_for_text(self, regex_string):
        
        matches = self.__find_text_regex_in_page(regex_string)

        regex_match_lines_to_highlight = []

        for match in matches:
            self.__mark_found_regex_match(match, regex_match_lines_to_highlight)

        self.__limit_to_list(regex_match_lines_to_highlight)
        
        self.__highlight_regex_matches(regex_match_lines_to_highlight)
    

    def __run_regex_matching_for_tables(self, regex_string, roi, table_shape):

        # Filter tables with same number of column 

        lines_to_highlight = {}

        if not safe_regex.is_safe_pattern(regex_string):
            self.__highlight_regex_matches([lines_to_highlight])
            return

        for table in self.tables_in_page:
            if table.col_count != table_shape[0]:
                continue

            column = roi[1]

            for j in range(len(table.rows)):
                text_in_cell  = self.__get_text_in_cell(table,j,column)
                text = text_in_cell['text']
                indexes = text_in_cell['indexes']

                if text == '':
                    continue

                if safe_regex.search(regex_string,text) is None:
                    continue

                if indexes[0] == np.inf:
                    continue

                for char in self.text_in_page[indexes[0]:indexes[1]]:
                    if table.bbox and not self.__is_bbox_within_row_column(char['bbox'], table.bbox, j, column):
                        continue
                    self.__build_highlight_lines(lines_to_highlight,char)

        self.__highlight_regex_matches([lines_to_highlight])





    def __limit_to_list(self, regex_match_lines_to_highlight):
        if self.__page_layout is None:
            return
        
        index =  self.__find_list_index_in_layout()

        if index is None:
            return
                    
        lines_to_remove = []
        for match_line in regex_match_lines_to_highlight:
            for bbox in match_line.values():
                scaled_bbox = [x//2 for x in self.__page_layout[index]['bbox']] # 2 is default page zoom
                
                if not match_line:
                    continue
                
                if not self.__is_rectangle_overlap(bbox, scaled_bbox):
                    lines_to_remove.append(match_line)


        for line in lines_to_remove:
            if line in regex_match_lines_to_highlight:
                regex_match_lines_to_highlight.remove(line)




    def __find_list_index_in_layout(self):

        for i in range(len(self.__page_layout)):
            if self.__page_layout[i]['type'] != 'list':
                continue

            bbox = [x//2 for x in self.__page_layout[i]['bbox']] # 2 is default page zoom
            if (self.__selected_given_text 
                and self.__is_rectangle_overlap(bbox,self.__selected_given_text[0]['bbox'])):
                    return i


    def __is_rectangle_overlap(self, R1, R2):
        if (int(R1[0])>=int(R2[2])) or (int(R1[2])<=int(R2[0])) or (int(R1[3])<=int(R2[1])) or (int(R1[1])>=int(R2[3])):
            return False
        else:
            return True
        


    def __highlight_regex_matches(self, regex_match_lines_to_highlight):
        
        self.__remove_highlight_regex_template()
        if regex_match_lines_to_highlight is None:
            return

        for match_lines_to_highlight in regex_match_lines_to_highlight:
            for line_key,line in match_lines_to_highlight.items():
                self.mark_with_style('REGEX', line, self.REGEX_STROKE)
                
        self.refresh_image()


    def __remove_highlight_regex_template(self, refresh_image=True,remove_key_ignore_marks=False):
        self.remove_styled_highlight('REGEX')
        if remove_key_ignore_marks:
            self.remove_mark_with_highlight(refresh_image=refresh_image)
            self.remove_mark_with_strikeout(refresh_image=refresh_image)
            self.remove_mark_with_underline(refresh_image=refresh_image)
        if refresh_image:
            self.refresh_image()




    
    def __find_text_regex_in_page(self, regex_string=None):
        
        if regex_string is None:
            regex_string = self.__selected_text_regex_string

        return [match.group(0) for match in safe_regex.finditer(regex_string,self.text_in_page_string)]
        

      
    def __mark_found_regex_match(self, match, regex_match_lines_to_highlight:List):
        # Check if match object is a string
        if isinstance(match, tuple):
            regex_string = match[0]
        else:
            regex_string = match

        r = re.compile(re.escape(regex_string)) 
        text_in_page_string_without_newlines = self.text_in_page_string.replace('\n','')
        match_indexes_list = [[m.start(),m.end()] for m in r.finditer(text_in_page_string_without_newlines)]

        lines_to_highlight = {}
        
        for match_indexes in match_indexes_list:
            chars = self.text_in_page[match_indexes[0]:match_indexes[1]]
            for char in chars:
                if char in self.__selected_text:
                    continue
                self.__build_highlight_lines(lines_to_highlight,char)

        regex_match_lines_to_highlight.append(lines_to_highlight)

        


    def __ignore_text(self):
        
        ignore_indexes = []
        for char in self.__highlighted_chars:
            index = char['index']
            ignore_indexes.append(index)
        self.__tool_panel_text_mark_callback(self.__highlighted_given_text, self.__highlighted_parameter)
        

    def __key_text(self):
        for char in self.__highlighted_chars:
            if (self.__first_highlight_char_index > char['index'] 
                or self.__last_highlight_char_index < char['index']):
                messagebox.showwarning('Select Linked Text','Please select text within a linked text')
                return 

        for _,line in self.__lines_to_highlight.items():
            self.mark_with_underline(line)

        key_indexes = []
        for char in self.__highlighted_chars:
            _char = copy.deepcopy(char)
            _char['c']=self.IGNORE_INDICATOR

            index = char['index']-self.__first_highlight_char_index
            self.__selected_given_text[index] = _char
            key_indexes.append(index)

        #regex_string = self.__run_regex_matching()
        #return regex_string, key_indexes
    




    def focus_on_roi(self, roi_name):
        self.unselect_poly()
        j = roi_name + self.tag_poly_const  # unique tag of the polygon
        color = self.color_roi if self.is_roi(j) else self.color_hole  # get color palette
        self.canvas.itemconfigure(roi_name, fill=color['point'])  # select lines through 2nd tag
        self.canvas.itemconfigure(j, state='normal')  # show polygon
        self.selected_poly.append(roi_name)

    def unselect_poly(self):
        if not self.selected_poly: return  # selected polygons list is empty
        for i in self.selected_poly:
            j = i + self.tag_poly_const  # unique tag of the polygon
            color = self.color_roi if self.is_roi(j) else self.color_hole  # get color palette
            self.canvas.itemconfigure(i, fill=color['back'])  # deselect lines
            self.canvas.itemconfigure(j, state='hidden')  # hide figure
        self.selected_poly.clear()  # clear the list

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

    def delete_edges(self):
        """ Delete edges of drawn polygon """
        if self.edge:  # if polygon is being drawing, delete it
            self.edge = None  # delete all edges and set current edge to None
            self.canvas.delete(self.tag_curr_edge)  # delete all edges
            self.polygon.clear()  # remove all items from vertices list

    def delete_selected(self):
        self.delete_rect()
        self.delete_poly()

    def delete_poly(self):
        """ Delete selected polygon """
        self.delete_edges()  # delete edges of drawn polygon
        if self.highlighted_poly:  # delete selected polygon
            for i in self.highlighted_poly:
                j = i + self.tag_poly_const  # unique tag of the polygon
                if self.is_roi(j):
                    del(self.roi_list[self.pno][i])  # delete ROI from the dictionary of all ROIs
                else:
                    del(self.hole_dict[i])  # delete hole from the dictionary of all holes
                self.canvas.delete(i)  # delete lines
                self.canvas.delete(j)  # delete polygon
            self.highlighted_poly.clear()  # clear selection list
            self.hold_menu2 = False  # popup menu is closed
            self.save_page_roi()
            

    def delete_all(self):
        """ Delete all polygons and rects from the canvas and clear variables """
        self.delete_edges()  # delete edges of drawn polygon
        self.canvas.delete(self.tag_roi)  # delete all ROI
        self.canvas.delete(self.tag_hole)  # delete all holes
        self.canvas.delete(self.tag_poly_line)  # delete all polygon lines
        self.highlighted_poly.clear()  # clear selection list
        self.hold_menu2 = False  # popup menu is closed
        # self.roi_list[self.pno].clear()  # clear dictionary of ROI
        self.hole_dict.clear()  # clear dictionary of holes

    def reset(self, roi):
        """ Reset ROI and holes on the image """
        self.delete_all()  # delete old rectangles and poly
            
        for tag_uid ,polygon in roi.items():  # draw roi polygons
            self.draw_polygon(polygon, self.color_roi, self.tag_roi, self.roi_list[self.pno], tag_uid)

        

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
        logging.info("Saving region-of-interests list for document {doc} ".format(doc=self.path))
        
        self.__db.insert_project_document_roi(self.path,self.roi_list)

    
    def destroy(self):
        """Clean up resources when canvas is destroyed"""
        if self.__pending_approvals_update_timer:
            self.canvas.after_cancel(self.__pending_approvals_update_timer)
            self.__pending_approvals_update_timer = None
        if self.floating_dropdown:
            self.floating_dropdown.destroy()
        return super().destroy()

def main():
    pass

if __name__ == "__main__":
    main()