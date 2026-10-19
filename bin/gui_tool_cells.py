
from pydoc import doc

import cv2
from bin.logic_acm_data_handler import ACM_Data_Handler
from bin.logic_hmi_display import HMI_Display
from bin.logic_internal_database import Database
from bin.logic_profile import profile
from bin.logic_static_graphic import Static_Graphic
from bin.gui_link_view import image_view
from tkinter import messagebox
from bin.gui_linked_text_entry_view import linked_text_entry
from bin.logic_control_module import Control_Module
from tkinter.filedialog import asksaveasfilename, askdirectory
import time
import tkinter as tk
from tkinter import *
from tkinter import ttk
from tkinter import font

from bin.logic_validators import Validators

try:
    from .gui_base64_icons import small_user_icon, parameters, goto_dark_gray, error_image, linked_graphic, subobjects, start_scan, locations, edit_graphic, export, build, page_links, connect_lines, assign_object_dark_gray, magic_copy_select_dark_gray_thin
    from .gui_elements import custom_entry, rounded_image_button, expandable_list_canvas, custom_label, cell_line
except ImportError as error:
    from gui_base64_icons import small_user_icon, parameters, goto_dark_gray, error_image, linked_graphic, subobjects, start_scan, locations, edit_graphic, export, build, page_links, connect_lines, assign_object_dark_gray, magic_copy_select_dark_gray_thin
    from gui_elements import custom_entry, rounded_image_button, expandable_list_canvas, custom_label, cell_line

class expandable_list_canvas_cell:

    def __init__(self, canvas: expandable_list_canvas, group_id, cell_id, tool_frame=None, name='',username='',description='',is_linked=True
                    ,cell_highlighted_callback=None, cell_unhighlighted_callback=None,delete_from_database_callback=None, assignment_id=''
                    ,assigned_type=''):

        self.canvas = canvas
        self._configure_canvas = None
        self.y = 0
        self.group_id = group_id
        self.cell_id = cell_id
        self.user_icon_image = tk.PhotoImage(data=small_user_icon)
        self.name = name
        self.description = description
        self.username = username
        self.is_linked = is_linked
        self.assignment_id = assignment_id
        self.assigned_type = assigned_type
        self.primary_linked_graphic_roi_name = ''
        self.secondary_linked_graphic_roi_name = ''

        self.selection_rect_image = None
        self.user_icon = None 
        self.username_label = None 
        self.name_label = None 
        self.description_label = None 
        self.divider = None 
        self.rect = None
        self.tool_frame = tool_frame
        self.expanded = False
        if self.assignment_id != '' and self.group_id == 'Unassigned':
            self.tags = ('cell',self.assigned_type, self.cell_id )
        else:
            self.tags = ('cell',self.group_id, self.cell_id )
        self.entry_widgets_hidden = False # Used ti handle redarw cases 
        self.pass_document_selection_subscription_func = None
        self.__db = None 
        self.__document_selected_func = None 
        self.add_primary_running_task = None
        self.add_secondary_running_task = None
        self.add_background_task_callback = None 
        self.remove_background_task_callback = None 
        self.acm_data_handler = None
        self.__multi_selected = False
        self.__cell_highlighted_callback_func = cell_highlighted_callback
        self.__cell_unhighlighted_callback_func = cell_unhighlighted_callback
        self.__delete_from_database_func = delete_from_database_callback


    def add_background_task_callback_func(self, func):
        self.add_background_task_callback = func

    def remove_background_task_callback_func(self, func):
        self.remove_background_task_callback = func
        
    def document_selected_func(self, func):
        self.__document_selected_func = func 

    def get_document_selected_func(self):
        return self.__document_selected_func

    def setup_data_handler( self, data_handler: ACM_Data_Handler):
        self.acm_data_handler = data_handler

    def setup_project(self, project_name, database, config):
        self.__project_name = project_name
        self.__db = database
        self.__config = config

    def get_project(self):
        return self.__project_name,self.__db,self.__config

    def get_data_handler(self):
        return self.acm_data_handler
        
    def setup_configure_canvas(self, canvas):
        '''Passes configuration canvas to children'''
        self._configure_canvas = canvas


    @property
    def configure_canvas(self):
        '''Falls back to the tool frame when no canvas was passed down (e.g. cells built from a document selection).'''
        if self._configure_canvas is None:
            tool_frame = self.__find_tool_frame()
            if tool_frame:
                self._configure_canvas = tool_frame.get_configure_canvas()
        return self._configure_canvas


    @configure_canvas.setter
    def configure_canvas(self, canvas):
        self._configure_canvas = canvas


    def __find_tool_frame(self):
        widget = self.canvas
        while widget is not None:
            if hasattr(widget, 'get_configure_canvas'):
                return widget
            parent_name = widget.winfo_parent()
            if not parent_name:
                return None
            widget = widget._nametowidget(parent_name)
        return None

        
    def draw(self, y):
        self.y = y 
        self.rect = self.canvas.create_rectangle(16, y, self.canvas.winfo_width(), y + 50,tags=self.tags, fill='#FFFFFF',width=0)
        self.user_icon = self.canvas.create_image(20, y + 8, image=self.user_icon_image, anchor = tk.NW, tags=self.tags)
        self.username_label = self.canvas.create_text(36,y + 8, text=self.username, anchor=tk.NW, tags=self.tags, fill="#6F6F6F")


        if self.is_linked or self.group_id == 'Unassigned' and self.assignment_id == '':
            name_label_color = "#555555" 
        elif self.assignment_id != '' and self.group_id == 'Unassigned':
            name_label_color = "#00AEEF"
        else:
            name_label_color = "#A3A3A3"
        self.name_label = self.canvas.create_text(20,y + 24, text=self.name, font=('Arial',13,'bold'), anchor=tk.NW, tags=self.tags, fill=name_label_color)

        self.divider = self.canvas.create_line(int(self.canvas.winfo_width()/2), y + 14, int(self.canvas.winfo_width()/2), y + 38, fill='#D5D5D5', width=2)
        self.description = self.description
        self.description_label = self.canvas.create_text(int(self.canvas.winfo_width()/2)+4,y + 18, text=self.description, anchor=tk.NW, tags=self.tags, fill="#6F6F6F")
        self.fit_description_in_mutiline()
        self.selection_rect_image = self.canvas.create_rectangle(16, y, self.canvas.winfo_width(), y + 50,tags=self.tags, fill='',width=0)
        self.canvas.tag_bind(self.selection_rect_image , '<Enter>', lambda event:self.highlight_element(event))
        self.canvas.tag_bind(self.selection_rect_image , '<Leave>', lambda event:self.unhighlight_element(event))
        
    
    def update_name_label_indicate_linked(self, is_linked=True):

        self.is_linked = is_linked

        if self.is_linked:
            name_label_color = "#555555" 
        else:
            name_label_color = "#A3A3A3"
        
        self.canvas.itemconfig(self.name_label,fill=name_label_color)


    def primary_progress_callback_func(self, func):
        self.add_primary_running_task = func   


    def secondary_progress_callback_func(self, func):
        self.add_secondary_running_task = func


    def find_similar_primary_from_image(self, image):
        print('find_similar_primary_in_image not defined')


    def find_similar_secondary_from_image(self, image):
        print('find_similar_secondary_in_image not defined')
        

    def delete_from_database(self):
        if self.__delete_from_database_func:
            self.__delete_from_database_func()
        
        
    def highlight_element(self, event):

        if self.__multi_selected:
            return  

        if not self.expanded:
            self.canvas.itemconfig(self.rect,fill='#F0F0F0')

        if self.__cell_highlighted_callback_func:
            self.__cell_highlighted_callback_func(self.name,self.cell_id,self.group_id,self)
        
    def unhighlight_element(self, event):

        if self.__multi_selected:
            return  

        if not self.expanded:
            self.canvas.itemconfig(self.rect,fill='white')   

        if self.__cell_unhighlighted_callback_func:
            self.__cell_unhighlighted_callback_func(self.name,self.cell_id,self.group_id,self)


    def multi_select_highlight(self):
        self.canvas.itemconfig(self.rect,fill='#E7E7E7')
        self.__multi_selected = True 

    
    def clear_multi_select_highlight(self):
        self.canvas.itemconfig(self.rect,fill='white')  
        self.__multi_selected = False 

            
    def template_delete(self):
        if self.description_label:
            self.canvas.delete(self.rect)
            self.canvas.delete(self.user_icon)
            self.canvas.delete(self.username_label)
            self.canvas.delete(self.name_label)
            self.canvas.delete(self.description_label)
            self.canvas.delete(self.divider)
            self.canvas.delete(self.selection_rect_image)
        
   
    def fit_description_in_mutiline(self):

        description_bounds = self.canvas.bbox(self.description_label) 

        if description_bounds is None:
            return

        if (description_bounds[2] - description_bounds[0]) < (self.canvas.winfo_width()/2 - 8) or self.canvas.winfo_width() <= 0:
            return

        y = self.y
        
        second_line_substring = 0 
        split = self.description.split(" ")
        while True :
            second_line_substring = second_line_substring + 1
            multiline_description = ' '.join(split[:second_line_substring])
            self.canvas.delete(self.description_label)
            self.description_label = self.canvas.create_text(int(self.canvas.winfo_width()/2)+4,y + 11, text=multiline_description, anchor=tk.NW, tags=self.tags, fill="#6F6F6F")
            description_bounds = self.canvas.bbox(self.description_label)
            if (description_bounds[2] - description_bounds[0]) > (self.canvas.winfo_width()/2 - 8):
                break
        second_line_substring = second_line_substring - 1
        self.canvas.delete(self.description_label)
        multiline_description = ' '.join(split[:second_line_substring])+'\n'+' '.join(split[second_line_substring:])
        self.description_label = self.canvas.create_text(int(self.canvas.winfo_width()/2)+4,y + 11, text=multiline_description, anchor=tk.NW, tags=self.tags, fill="#6F6F6F")
        

    def show_config_canvas(self):
        parentName = self.canvas.winfo_parent()
        parent     = self.canvas._nametowidget(parentName) #event.widget is your widget

        frameParentName = parent.winfo_parent()
        frameParent     = parent._nametowidget(frameParentName)
        frameGrandParentName = frameParent.winfo_parent()
        frameGrandParent     = frameParent._nametowidget(frameGrandParentName)
        frameGrandParent.show_configure_frame()

    def show_underconstruction_config_canvas(self):
        parentName = self.canvas.winfo_parent()
        parent     = self.canvas._nametowidget(parentName) #event.widget is your widget

        frameParentName = parent.winfo_parent()
        frameParent     = parent._nametowidget(frameParentName)
        frameGrandParentName = frameParent.winfo_parent()
        frameGrandParent     = frameParent._nametowidget(frameGrandParentName)
        frameGrandParent.show_underconstruction()


    def show_message_on_config_canvas(self,title, message, image):
        parentName = self.canvas.winfo_parent()
        parent     = self.canvas._nametowidget(parentName) #event.widget is your widget

        frameParentName = parent.winfo_parent()
        frameParent     = parent._nametowidget(frameParentName)
        frameGrandParentName = frameParent.winfo_parent()
        frameGrandParent     = frameParent._nametowidget(frameGrandParentName)
        frameGrandParent.show_custom_message(title, message, image)


    def update_roi_names(self, primary_roi_name=None, secondary_roi_name=None):
        if primary_roi_name:
            self.primary_linked_graphic_roi_name = primary_roi_name
        
        if secondary_roi_name:
            self.secondary_linked_graphic_roi_name = secondary_roi_name
            

class expandable_list_canvas_control_module_cell(expandable_list_canvas_cell):
    def __init__(self, canvas: expandable_list_canvas, group_id, cell_id,name='',description='',username=''
                 ,is_linked=False,assignment_id='',cell_highlighted_callback=None, cell_unhighlighted_callback=None,assigned_type=''):  
        expandable_list_canvas_cell.__init__(self, canvas,group_id,cell_id, name=name,description=description,username=username,is_linked=is_linked,assignment_id=assignment_id
                                            ,cell_highlighted_callback=cell_highlighted_callback, cell_unhighlighted_callback=cell_unhighlighted_callback, assigned_type=assigned_type

                                            ,delete_from_database_callback=self.__delete_from_database)
        self.group_id = group_id
        self.cell_id = cell_id
        self.widgets_created = False
        self.description_entry = None
        self.name = name 
        self.description = description
        self.control_module = Control_Module(self.cell_id, name,description, self.__go_to_document_path
                                             ,self.update_name_label_indicate_linked, self.group_id,self.update_roi_names)
        self.control_module.document_selected_func(self.get_document_selected_func())
        self.pass_document_selection_subscription_func = self.__pass_document_selection_subscription
        

    def __go_to_document_path(self, path, doc_type=Database.DRAWING):
        func = self.get_document_selected_func()
        func(path,doc_type)

    def __pass_document_selection_subscription(self, subscription):
        self.control_module.document_selection_subscription(subscription)
        
        
    def create_widgets(self):
        self.name_entry = linked_text_entry(self.canvas, 8,56,placeholder='Name')
        
        self.name_entry.entry.insert(0, self.name)
        if self.group_id != 'Unassigned':
            self.name_entry = linked_text_entry(self.canvas, 8,56,placeholder='Name')
            self.name_entry.entry.insert(0, self.name) 
            self.name_entry.entry.config(state='readonly')
        else:
            self.name_entry = linked_text_entry(self.canvas, 8,56,placeholder='Name',focus_out_callback=self.__name_entry_focusout)
            self.name_entry.entry.insert(0, self.name) 
        self.parameters = tk.PhotoImage(data=parameters)
        self.goto_image = tk.PhotoImage(data=goto_dark_gray)
        self.linked_graphic = tk.PhotoImage(data=linked_graphic)
        self.subobjects = tk.PhotoImage(data=subobjects)
        self.assign_object_image = tk.PhotoImage(data=assign_object_dark_gray)
        self.highlight_sismilar = tk.PhotoImage(data=magic_copy_select_dark_gray_thin)
        self.start_scan = tk.PhotoImage(data=start_scan)
        
        
        if self.group_id != 'Unassigned':
            self.description_entry = custom_entry(self.canvas, 8,126,placeholder='Description')
            self.description_entry.entry.insert(0, self.description)
            self.description_entry.entry.config(state='readonly')
        else:
            self.description_entry = custom_entry(self.canvas, 8,126,placeholder='Description',focus_out_callback=self.__description_entry_focusout)
            self.description_entry.entry.insert(0, self.description)
        self.reference_document = custom_label(self.canvas, 8, 176, text="Reference Document", fill= '#505050',size=11,weight="bold")
        self.reference_document_value = custom_label(self.canvas, 8, 194, text="XXXX-XXXX-XXXX-XXXX", fill= '#505050' ,size=11,weight="normal")
        self.reference_page = custom_label(self.canvas, 8, 216, text="Page", fill= '#505050',size=11,weight="bold")
        self.reference_page_value = custom_label(self.canvas, 8, 234, text="0000", fill= '#505050' ,size=11,weight="normal")
        self.position = custom_label(self.canvas, 8, 256, text="Position", fill= '#505050',size=11,weight="bold")
        self.position_x_label = custom_label(self.canvas, 8, 274, text="X", fill= '#D7D7D7',size=11,weight="bold")
        self.position_x_value = custom_label(self.canvas, 24, 274, text="000000", fill= '#505050' ,size=11,weight="normal")
        self.position_y_label = custom_label(self.canvas, 90, 274, text="Y", fill= '#D7D7D7',size=11,weight="bold")
        self.position_y_value = custom_label(self.canvas, 106, 274, text="000000", fill= '#505050' ,size=11,weight="normal")
        tags = (self.group_id, self.cell_id, "configure_frame")
        self.buttonA = rounded_image_button(self.canvas, 16, 294, 10, text="SHOW LINK", icon_image=self.goto_image, borderwidth=1, 
                    tags= tags + ('show link',), callback=self.__show_link)
        self.buttonC = rounded_image_button(self.canvas, 16, 338, 10, text="LINKED GRAPHICS", icon_image=self.linked_graphic, borderwidth=1, 
                    tags= tags + ('linked graphics',), callback=self.__linked_graphic)
        self.buttonD = rounded_image_button(self.canvas, 16, 382, 10, text="ASSIGN OBJECT", icon_image=self.assign_object_image, borderwidth=1, 
                    tags= tags + ('assign object',), callback=self.__assign_object)
        self.buttonE = rounded_image_button(self.canvas, 16, 426, 10, text="PARAMETERS", icon_image=self.parameters, borderwidth=1, 
                    tags= tags + ('parameters',), callback=self.__parameters)
        self.buttonF = rounded_image_button(self.canvas, 16, 470, 10, text="SUBOBJECTS", icon_image=self.subobjects, borderwidth=1, 
                    tags= tags + ('subobjects',), callback=self.__subobjects)
        self.cell_divider = cell_line(self.canvas, 48, 28, 530, fill= '#E5E5E5', width=1)
        self.position_in_display = custom_label(self.canvas, 8, 542, text="Position In Display", fill= '#505050',size=11,weight="bold")
        self.position_in_display_x_label = custom_label(self.canvas, 8, 560, text="X", fill= '#D7D7D7',size=11,weight="bold")
        self.position_in_display_x_value = custom_label(self.canvas, 24, 560, text="000000", fill= '#505050' ,size=11,weight="normal")
        self.position_in_display_y_label = custom_label(self.canvas, 90, 560, text="Y", fill= '#D7D7D7',size=11,weight="bold")
        self.position_in_display_y_value = custom_label(self.canvas, 106, 560, text="000000", fill= '#505050' ,size=11,weight="normal")
        self.buttonG = rounded_image_button(self.canvas, 16, 580, 10, text="DRAW ROI", icon_image=self.highlight_sismilar, borderwidth=1,
                    tags= tags + ('draw roi',), callback=self.__draw_roi_trigger)
        self.buttonH = rounded_image_button(self.canvas, 16, 624, 10, text="SCAN PAGE", icon_image=self.start_scan, borderwidth=1, 
                    tags= tags, callback=self.__start_single_page_scan)
        self.buttonI = rounded_image_button(self.canvas, 16, 668, 10, 
                                            text="SCAN ALL PAGES", 
                                            borderwidth=1, 
                                            tags=('button','B'),
                                            icon_image=self.start_scan,
                                            callback=self.__start_document_scan)

    def get_primary_pdf_zoom_scale(self):
        project_name,database,config = self.get_project()
        self.control_module.setup_project(project_name,database,config)
        self.control_module.setup_data_handler(self.get_data_handler())
        return self.control_module.get_primary_pdf_zoom_scale()
    

    def get_secondary_pdf_zoom_scale(self):
        project_name,database,config = self.get_project()
        self.control_module.setup_project(project_name,database,config)
        self.control_module.setup_data_handler(self.get_data_handler())
        return self.control_module.get_secondary_pdf_zoom_scale()


    def get_primary_linked_graphic_data(self):
        """ Returns the primary linked graphic dict for this cell (or None). """
        project_name, database, config = self.get_project()
        self.control_module.setup_project(project_name, database, config)
        self.control_module.setup_data_handler(self.get_data_handler())
        return self.control_module.get_primary_linked_graphic_data()


    def instantiate_manual_placement(self, dest_path, dest_pno, roi_bbox,
                                     rotation=None, flip=None, scale=1.0,
                                     text_roi_polygons=None, wire_kwargs=None):
        """ Persist a manually-placed copy of this cell's primary linked graphic. """
        project_name, database, config = self.get_project()
        self.control_module.setup_project(project_name, database, config)
        self.control_module.setup_data_handler(self.get_data_handler())
        self.control_module.setup_canvas(self.canvas)
        return self.control_module.instantiate_manual_placement(
            dest_path, dest_pno, roi_bbox,
            rotation=rotation, flip=flip, scale=scale,
            text_roi_polygons=text_roi_polygons,
            wire_kwargs=wire_kwargs,
        )


    def scan_from_manual_placement(self, roi_uid, pno, template_mask,
                                   scale_factor=1.0, page_index=None,
                                   document_type=None, wire_kwargs=None):
        """ Kick off the document scan after a manual placement. """
        project_name, database, config = self.get_project()
        self.control_module.setup_project(project_name, database, config)
        self.control_module.setup_data_handler(self.get_data_handler())
        self.control_module.setup_canvas(self.canvas)
        try:
            self.control_module.scan_from_manual_placement(
                roi_uid, pno, template_mask,
                scale_factor=scale_factor,
                page_index=page_index,
                document_type=document_type,
                wire_kwargs=wire_kwargs,
            )
        except OSError as error:
            messagebox.showwarning('Already started', error)
        except Exception as error:
            messagebox.showerror('Error starting scan', error)
        else:
            self.add_background_task_callback(self.cell_id, self)
            self.add_primary_running_task(self.__check_scanner_progress)
            self.control_module.add_secondary_progress_callback(self.__add_secondary_progress)
            self.control_module.remove_background_task_callback(self.remove_background_task_callback)


    def test_from_manual_placement(self, roi_uid, pno, template_mask,
                                   document_type=None, wire_kwargs=None,
                                   polygon=None):
        """ Run a page-level test scan after a manual placement. """
        project_name, database, config = self.get_project()
        self.control_module.setup_project(project_name, database, config)
        self.control_module.setup_data_handler(self.get_data_handler())
        self.control_module.setup_canvas(self.canvas)
        try:
            self.control_module.test_from_manual_placement(
                roi_uid, pno, template_mask,
                document_type=document_type,
                wire_kwargs=wire_kwargs,
                polygon=polygon,
            )
        except Exception as error:
            messagebox.showerror('Error running test scan', error)

    
    def expand(self):
        self.canvas.config(cursor="wait")
        project_name,database,config = self.get_project()
        self.control_module.setup_project(project_name,database,config)
        self.control_module.setup_data_handler(self.get_data_handler())
        self.control_module.setup_canvas(self.canvas)
        if not self.widgets_created:
            self.create_widgets()
            self.widgets_created = True

        y = self.y
        #self.description_entry_label = self.canvas.create_text(20,y + 56, text='Description',font=('Arial',11,'bold'), anchor=tk.NW, tags=self.tags, fill="#505050")
        if not self.entry_widgets_hidden:
            self.name_entry.draw(0,y)
            self.description_entry.draw(0,y)
        self.reference_document.draw(0,y)
        self.reference_document_value.draw(0,y)
        
        self.reference_page.draw(0,y)
        self.reference_page_value.draw(0,y)
        
        self.position.draw(0,y)
        self.position_x_label.draw(0,y)
        self.position_x_value.draw(0,y)
        self.position_y_label.draw(0,y)
        self.position_y_value.draw(0,y)
        self.buttonA.draw(0,y)
        self.buttonC.draw(0,y)
        self.buttonD.draw(0,y)
        self.buttonE.draw(0,y)
        self.buttonF.draw(0,y)
        self.cell_divider.draw(y)
        self.position_in_display.draw(0,y)
        self.position_in_display_x_label.draw(0,y)
        self.position_in_display_x_value.draw(0,y)
        self.position_in_display_y_label.draw(0,y)
        self.position_in_display_y_value.draw(0,y)
        self.buttonG.draw(0,y)
        self.buttonH.draw(0,y)
        self.buttonI.draw(0,y)
        self.control_module.add_linked_name_text_entry(self.name_entry)
        self.expanded = True
        self.__populate_details()
        self.canvas.config(cursor="")

    def __populate_details(self):

        # set document name
        document = self.control_module.get_document()
        if not document:
            document = 'Not defined' 
        self.reference_document_value.set_text(document)

        # set page number
        page = self.control_module.get_page()
        if not page:
            page = 'Not defined'
        self.reference_page_value.set_text(page)

        # set coordinates
        coordinates = self.control_module.get_coordinates()
        if not coordinates:
            x_coordinate = 'N/A'
            y_coodintate = 'N/A'
        else:
            x_coordinate = "{:0.2f}%".format(coordinates[0]*100)
            y_coodintate = "{:0.2f}%".format(coordinates[1]*100)

        self.position_x_value.set_text(x_coordinate)
        self.position_y_value.set_text(y_coodintate)
        self.position_in_display_x_value.set_text(x_coordinate)
        self.position_in_display_y_value.set_text(y_coodintate)

        
    
    def delete(self):
        if self.description_entry:
            if not self.entry_widgets_hidden:
                self.name_entry.hide()
                self.description_entry.hide()
            self.reference_document.hide()
            self.reference_document_value.hide()
            self.reference_page.hide()
            self.reference_page_value.hide()
            self.position.hide()
            self.position_x_label.hide()
            self.position_x_value.hide()
            self.position_y_label.hide()
            self.position_y_value.hide()
            self.buttonA.hide()
            self.buttonC.hide()
            self.buttonD.hide()
            self.buttonE.hide()
            self.buttonF.hide()
            self.cell_divider.hide()
            self.position_in_display.hide()
            self.position_in_display_x_label.hide()
            self.position_in_display_x_value.hide()
            self.position_in_display_y_label.hide()
            self.position_in_display_y_value.hide()
            self.buttonG.hide()
            self.buttonH.hide()
            self.buttonI.hide()
            self.control_module.clear_text_in_document_viewer_panel()
        self.template_delete()
        self.expanded = False

    def __delete_from_database(self):
        project_name,database,config = self.get_project()
        self.control_module.setup_project(project_name,database,config)
        self.control_module.setup_data_handler(self.get_data_handler())
        self.control_module.delete_from_database()

        
    def __name_entry_focusout(self):
        text = self.name_entry.entry.get()
        self.control_module.set_name(text)
        self.canvas.itemconfig(self.name_label,text=text)
        self.name = text

    def __description_entry_focusout(self):
        text = self.description_entry.entry.get()
        self.control_module.set_description(text)
        self.canvas.itemconfig(self.description_label,text=text)


    def hide_entry_widgets(self):
        self.name_entry.hide()
        self.description_entry.hide()
        self.entry_widgets_hidden = True # Used ti handle redarw cases 
        
        
    def show_entry_widgets(self):
        y = self.y
        self.name_entry.draw(0,y)
        self.description_entry.draw(0,y)
        self.control_module.draw_linked_text()
        self.entry_widgets_hidden = False # Used ti handle redarw cases 


    def __start_document_scan(self, tags):
        try:
            self.control_module.start_document_scan()
        except OSError as error:
            messagebox.showwarning('Already started',error)
        except Exception as error:
            messagebox.showerror('Error starting scan',error)
        else:
            self.add_background_task_callback(self.cell_id,self)
            self.add_primary_running_task(self.__check_scanner_progress)
            self.control_module.add_secondary_progress_callback(self.__add_secondary_progress)
            self.control_module.remove_background_task_callback(self.remove_background_task_callback)


    def __start_single_page_scan(self, tags):
        try:
            self.control_module.start_page_scan()
        except OSError as error:
            messagebox.showwarning('Already started',error)
        except Exception as error:
            messagebox.showerror('Error starting scan',error)
        else:
            self.add_background_task_callback(self.cell_id,self)
            self.add_primary_running_task(self.__check_scanner_progress)
            self.control_module.add_secondary_progress_callback(self.__add_secondary_progress)
            self.control_module.remove_background_task_callback(self.remove_background_task_callback)

    
    def find_similar_primary_from_image(self,matcher,image,page_index=None,callback=None,document_type=Database.DRAWING):
        try:
            self.control_module.setup_canvas(self.canvas)
            result = self.control_module.find_similar_primary_from_image(matcher,image,page_index,callback,document_type)
            result.append(self.__start_find_similar_scan)
            return result
        except OSError as error:
            messagebox.showwarning('Already started',error)
        except Exception as error:
            messagebox.showerror('Error starting scan',error)
        


    def __start_find_similar_scan(self,roi_uid,pno,new_template_mask,template_flip,template_rotate
                         ,page_index,scale_factor,document_type,add_template_image):
        try:
            self.control_module.add_graphic_link(roi_uid,pno,new_template_mask,template_flip
                                                 ,template_rotate,page_index,scale_factor,document_type,add_template_image)
        except OSError as error:
            messagebox.showwarning('Already started',error)
        except Exception as error:
            messagebox.showerror('Error starting scan',error)
        else:
            self.add_background_task_callback(self.cell_id,self)
            self.add_primary_running_task(self.__check_scanner_progress)
            self.control_module.add_secondary_progress_callback(self.__add_secondary_progress)
            self.control_module.remove_background_task_callback(self.remove_background_task_callback)

    

    def __draw_roi_trigger(self,_):
        try:
            self.control_module.draw_roi_trigger(self)
        except Exception as error:
            messagebox.showerror('Error starting draw ROI',error)

    

    def find_similar_secondary_from_image(self,matcher,image,page_index=None,callback=None,document_type=Database.DRAWING):
        try:
            self.control_module.setup_canvas(self.canvas)
            self.control_module.find_similar_secondary_from_image(matcher,image,page_index,callback,document_type)
        except OSError as error:
            messagebox.showwarning('Already started',error)
        except Exception as error:
            messagebox.showerror('Error starting scan',error)
        else:
            self.add_background_task_callback(self.cell_id,self)
            self.add_primary_running_task(self.__check_scanner_progress)
            self.control_module.add_secondary_progress_callback(self.__add_secondary_progress)
            self.control_module.remove_background_task_callback(self.remove_background_task_callback)
            


    def __check_scanner_progress(self):
        return self.control_module.check_scanner_progress()

    def __add_secondary_progress(self):
        self.add_secondary_running_task(self.__check_secondary_progress)

    def __check_secondary_progress(self):
        return self.control_module.check_pairing_progress()
        

    def __show_link(self, tags):
        try:
            self.control_module.go_to()
        except Exception as error:
            messagebox.showerror('Error showing link',error)

    def __linked_graphic(self, tags):
        self.configure_canvas.delete(tk.ALL)
        self.configure_canvas.config(background='white')
        self.control_module.create_linked_graphics_screen(self.configure_canvas)
        self.show_config_canvas()

    def __assign_object(self, tags):
        self.configure_canvas.delete(tk.ALL)
        self.configure_canvas.config(background='white')
        if self.group_id != 'Unassigned':
            self.show_message_on_config_canvas('ACM Object','This object is already created in ACM. '
                                               +' Delete the object in ACM to reassign.',error_image)
        else:
            self.control_module.create_assign_object_screen(self.configure_canvas,self.assignment_id)
        self.show_config_canvas()


    def show_parameter_linked_text(self, linked_text):
        self.__parameters()
        self.control_module.show_parameter_linked_text(linked_text)

    def show_add_parameter_view_with_prediction(self, prediction, callback=None):
        self.__parameters()
        self.control_module.show_add_parameter_view_with_prediction(prediction, callback)

    def show_subobject_linked_text(self, linked_text):
        self.__subobjects()
        self.control_module.show_subobject_linked_text(linked_text)

    def show_add_subobject_view_with_prediction(self, prediction, callback=None):
        self.__subobjects()
        self.control_module.show_add_subobject_view_with_prediction(prediction, callback)


    def __parameters(self, _=None):
        self.configure_canvas.delete(tk.ALL)
        self.configure_canvas.config(background='white')

        if self.group_id == 'Unassigned':
            messagebox.showwarning('Not an ACM Object','This object is not created in ACM.\n\n' \
            'Assign the object to a ACM library and create the object in ACM by going to Tools > Create Assigned Object.') 
            return

        if self.acm_data_handler is None:
            messagebox.showwarning("Not connected to ACM","Please connect to the ACM database.")
            return
        
        if not self.acm_data_handler.is_control_module_in_project(self.name):
            messagebox.showwarning("Not found in ACM","Please ensure that the object exists in Application Code Manager.")
            return
        self.canvas.config(cursor='wait')
        try:
            self.control_module.create_object_parameter_view(self.configure_canvas)
        except Exception as error:
            messagebox.showwarning('Unable to show parameters',error)
            self.canvas.config(cursor='')
            return
        self.canvas.config(cursor='')
        self.show_config_canvas()


    def __subobjects(self, _=None):
        self.configure_canvas.delete(tk.ALL)
        self.configure_canvas.config(background='white')

        if self.group_id == 'Unassigned':
            messagebox.showwarning('Not an ACM Object','This object is not created in ACM.\n\n' \
            'Assign the object to a ACM library and create the object in ACM by going to Tools > Create Assigned Object.') 
            return
        
        if self.acm_data_handler is None:
            messagebox.showwarning("Not connected to ACM","Please connect to the ACM database.")
            return
        
        if not self.acm_data_handler.is_control_module_in_project(self.name):
            messagebox.showwarning("Not found in ACM","Please ensure that the object exists in Application Code Manager.")
            return
        self.canvas.config(cursor='wait')
        try:
            self.control_module.create_subobject_parameter_view(self.configure_canvas
                                                                ,self.__add_background_task
                                                                ,self.__remove_background_task)
        except Exception as error:
            messagebox.showwarning('Unable to show parameters',error)
            self.canvas.config(cursor='')
            return
        self.canvas.config(cursor='')
        self.show_config_canvas()


    def __add_background_task(self):
        self.add_background_task_callback(self.cell_id,self)


    def __remove_background_task(self):
        self.remove_background_task_callback(self.cell_id)

    


        
    def cell_size(self):
        return 742


class expandable_list_canvas_static_graphic_cell(expandable_list_canvas_cell):
    def __init__(self, canvas: expandable_list_canvas, group_id, cell_id,name='',description='',username='',is_linked=True,assignment_id=''
                 ,cell_highlighted_callback=None, cell_unhighlighted_callback=None,assigned_type=''):
        expandable_list_canvas_cell.__init__(self, canvas,group_id,cell_id, name=name,description=description,username=username,assignment_id=assignment_id

                                            ,cell_highlighted_callback=cell_highlighted_callback, cell_unhighlighted_callback=cell_unhighlighted_callback
                                            ,delete_from_database_callback=self.__delete_from_database)
        self.group_id = group_id
        self.cell_id = cell_id
        self.widgets_created = False
        self.description_entry = None
        self.name = name 
        self.description = description
        self.static_graphic = Static_Graphic(self.cell_id, name,description, self.group_id, self.__go_to_document_path, self.__hmi_graphic_changed
                                             ,self.update_roi_names)
        self.static_graphic.document_selected_func(self.get_document_selected_func())
        self.pass_document_selection_subscription_func = self.__pass_document_selection_subscription
        self.__image_view_height = 300
        self.image_view = None


    def __hmi_graphic_changed(self):
        if self.image_view:
            image = self.static_graphic.get_hmi_graphic()
            if image is not None:
                image = cv2.cvtColor(image,cv2.COLOR_RGBA2BGRA)
            self.image_view.set_image(image)


    def __go_to_document_path(self, path, doc_type=Database.DRAWING):
        func = self.get_document_selected_func()
        func(path,doc_type)

    def __pass_document_selection_subscription(self, subscription):
        self.static_graphic.document_selection_subscription(subscription)
        
        
    def create_widgets(self):
        self.name_entry = linked_text_entry(self.canvas, 8,56,placeholder='Name',focus_out_callback=self.__name_entry_focusout)
        
        self.name_entry.entry.insert(0, self.name)
        self.locations = tk.PhotoImage(data=locations)
        self.goto_image = tk.PhotoImage(data=goto_dark_gray)
        self.linked_graphic = tk.PhotoImage(data=linked_graphic)
        self.edit_graphic = tk.PhotoImage(data=edit_graphic)
        self.export = tk.PhotoImage(data=export)
        self.start_scan = tk.PhotoImage(data=start_scan)
        
        self.description_entry = custom_entry(self.canvas, 8,126,placeholder='Description',focus_out_callback=self.__description_entry_focusout)
        self.description_entry.entry.insert(0, self.description)
        self.reference_document = custom_label(self.canvas, 8, 176, text="Reference Document", fill= '#505050',size=11,weight="bold")
        self.reference_document_value = custom_label(self.canvas, 8, 194, text="XXXX-XXXX-XXXX-XXXX", fill= '#505050' ,size=11,weight="normal")
        self.reference_page = custom_label(self.canvas, 8, 216, text="Page", fill= '#505050',size=11,weight="bold")
        self.reference_page_value = custom_label(self.canvas, 8, 234, text="0000", fill= '#505050' ,size=11,weight="normal")
        self.position = custom_label(self.canvas, 8, 256, text="Position", fill= '#505050',size=11,weight="bold")
        self.position_x_label = custom_label(self.canvas, 8, 274, text="X", fill= '#D7D7D7',size=11,weight="bold")
        self.position_x_value = custom_label(self.canvas, 24, 274, text="000000", fill= '#505050' ,size=11,weight="normal")
        self.position_y_label = custom_label(self.canvas, 90, 274, text="Y", fill= '#D7D7D7',size=11,weight="bold")
        self.position_y_value = custom_label(self.canvas, 106, 274, text="000000", fill= '#505050' ,size=11,weight="normal")
        self.image_view = image_view(self.canvas, 24, 294)
        tags = (self.group_id, self.cell_id, "configure_frame")
        self.buttonA = rounded_image_button(self.canvas, 16, 294, 10, text="SHOW LINK", icon_image=self.goto_image, borderwidth=1, 
                    tags= tags + ('show link',), callback=self.__show_link)
        self.buttonC = rounded_image_button(self.canvas, 16, 338, 10, text="LINKED GRAPHICS", icon_image=self.linked_graphic, borderwidth=1, 
                    tags= tags + ('linked graphics',), callback=self.__linked_graphic)
        self.buttonD = rounded_image_button(self.canvas, 16, 382, 10, text="HMI GRAPHIC", icon_image=self.edit_graphic, borderwidth=1, 
                    tags= tags + ('hmi graphic',), callback=self.__hmi_graphic)
        self.buttonE = rounded_image_button(self.canvas, 16, 426, 10, text="EXPORT GRAPHIC", icon_image=self.export, borderwidth=1, 
                    tags= tags + ('export graphic',), callback=self.__export_graphic)
        self.buttonF = rounded_image_button(self.canvas, 16, 470, 10, text="LOCATIONS", icon_image=self.locations, borderwidth=1, 
                    tags= tags + ('locations',), callback=self.__locations)
        self.cell_divider = cell_line(self.canvas, 48, 28, 530, fill= '#E5E5E5', width=1)
        self.position_in_display = custom_label(self.canvas, 8, 542, text="Position In Display", fill= '#505050',size=11,weight="bold")
        self.position_in_display_x_label = custom_label(self.canvas, 8, 560, text="X", fill= '#D7D7D7',size=11,weight="bold")
        self.position_in_display_x_value = custom_label(self.canvas, 24, 560, text="000000", fill= '#505050' ,size=11,weight="normal")
        self.position_in_display_y_label = custom_label(self.canvas, 90, 560, text="Y", fill= '#D7D7D7',size=11,weight="bold")
        self.position_in_display_y_value = custom_label(self.canvas, 106, 560, text="000000", fill= '#505050' ,size=11,weight="normal")
        self.buttonG = rounded_image_button(self.canvas, 16, 580, 10, 
                                            text="RUN SCAN", 
                                            borderwidth=1, 
                                            tags=('button','B'),
                                            icon_image=self.start_scan,
                                            callback=self.__start_document_scan)
    

    def expand(self):
        self.canvas.config(cursor="wait")
        project_name,database,config = self.get_project()
        self.static_graphic.setup_project(project_name,database,config)
        #self.control_module.setup_data_handler(self.get_data_handler())
        if not self.widgets_created:
            self.create_widgets()
            self.widgets_created = True

        y = self.y
        #self.description_entry_label = self.canvas.create_text(20,y + 56, text='Description',font=('Arial',11,'bold'), anchor=tk.NW, tags=self.tags, fill="#505050")
        if not self.entry_widgets_hidden:
            self.name_entry.draw(0,y)
            self.description_entry.draw(0,y)
        self.reference_document.draw(0,y)
        self.reference_document_value.draw(0,y)
        self.reference_page.draw(0,y)
        self.reference_page_value.draw(0,y)
        self.position.draw(0,y)
        self.position_x_label.draw(0,y)
        self.position_x_value.draw(0,y)
        self.position_y_label.draw(0,y)
        self.position_y_value.draw(0,y)
        self.image_view.draw(y=y, width=self.canvas.winfo_width() - 48, height=self.__image_view_height)
        self.buttonA.draw(0,y + self.__image_view_height)
        self.buttonC.draw(0,y + self.__image_view_height)
        self.buttonD.draw(0,y + self.__image_view_height)
        self.buttonE.draw(0,y + self.__image_view_height)
        self.buttonF.draw(0,y + self.__image_view_height)
        self.cell_divider.draw(y + self.__image_view_height)
        self.position_in_display.draw(0,y + self.__image_view_height)
        self.position_in_display_x_label.draw(0,y + self.__image_view_height)
        self.position_in_display_x_value.draw(0,y + self.__image_view_height)
        self.position_in_display_y_label.draw(0,y + self.__image_view_height)
        self.position_in_display_y_value.draw(0,y + self.__image_view_height)
        self.buttonG.draw(0,y + self.__image_view_height)
        self.static_graphic.add_linked_name_text_entry(self.name_entry)
        self.expanded = True
        self.__populate_details()
        self.canvas.config(cursor="")
    

    def __populate_details(self):

        # set document name
        document = self.static_graphic.get_document()
        if not document:
            document = 'Not defined' 
        self.reference_document_value.set_text(document)

        # set page number
        page = self.static_graphic.get_page()
        if not page:
            page = 'Not defined'
        self.reference_page_value.set_text(page)

        # set coordinates
        coordinates = self.static_graphic.get_coordinates()
        if not coordinates:
            x_coordinate = 'N/A'
            y_coodintate = 'N/A'
        else:
            x_coordinate = "{:0.2f}%".format(coordinates[0]*100)
            y_coodintate = "{:0.2f}%".format(coordinates[1]*100)

        self.position_x_value.set_text(x_coordinate)
        self.position_y_value.set_text(y_coodintate)
        self.position_in_display_x_value.set_text(x_coordinate)
        self.position_in_display_y_value.set_text(y_coodintate)
    
    
    def delete(self):
        if self.description_entry:
            if not self.entry_widgets_hidden:
                self.name_entry.hide()
                self.description_entry.hide()
            self.reference_document.hide()
            self.reference_document_value.hide()
            self.reference_page.hide()
            self.reference_page_value.hide()
            self.position.hide()
            self.position_x_label.hide()
            self.position_x_value.hide()
            self.position_y_label.hide()
            self.position_y_value.hide()
            self.image_view.hide()
            self.buttonA.hide()
            self.buttonC.hide()
            self.buttonD.hide()
            self.buttonE.hide()
            self.buttonF.hide()
            self.cell_divider.hide()
            self.position_in_display.hide()
            self.position_in_display_x_label.hide()
            self.position_in_display_x_value.hide()
            self.position_in_display_y_label.hide()
            self.position_in_display_y_value.hide()
            self.buttonG.hide()
            self.static_graphic.clear_text_in_document_viewer_panel()
        self.template_delete()
        self.expanded = False

        
    def __delete_from_database(self):
        project_name,database,config = self.get_project()
        self.static_graphic.setup_project(project_name,database,config)
        self.static_graphic.setup_data_handler(self.get_data_handler())
        self.static_graphic.delete_from_database()

    
    def hide_entry_widgets(self):
        self.name_entry.hide()
        self.description_entry.hide()
        self.entry_widgets_hidden = True # Used ti handle redarw cases 
        
        
    def show_entry_widgets(self):
        y = self.y
        self.name_entry.draw(0,y)
        self.description_entry.draw(0,y)
        self.entry_widgets_hidden = False # Used ti handle redarw cases 
        self.static_graphic.draw_linked_text()
        # To remove the edit graphic entry widgets
        self.static_graphic.hide_hmi_graphic()
    
    
    def __name_entry_focusout(self):
        text = self.name_entry.entry.get()
        self.static_graphic.set_name(text)
        self.canvas.itemconfig(self.name_label,text=text)
        self.name = text


    def __description_entry_focusout(self):
        text = self.description_entry.entry.get()
        self.static_graphic.set_description(text)
        self.canvas.itemconfig(self.description_label,text=text)
    

    def __start_document_scan(self, tags):
        try:
            self.static_graphic.start_document_scan()
        except OSError as error:
            messagebox.showwarning('Already started',error)
        except Exception as error:
            messagebox.showerror('Error starting scan',error)
        else:
            self.add_background_task_callback(self.cell_id,self)
            self.add_primary_running_task(self.__check_scanner_progress)
            self.static_graphic.remove_background_task_callback(self.remove_background_task_callback)


    def __check_scanner_progress(self):
        return self.static_graphic.check_scanner_progress()
        

    def __show_link(self, tags):
        try:
            self.static_graphic.go_to()
        except Exception as error:
            messagebox.showerror('Error showing link',error)

    def __linked_graphic(self, tags):
        self.configure_canvas.delete(tk.ALL)
        self.configure_canvas.config(background='white')
        self.static_graphic.create_linked_graphics_screen(self.configure_canvas)
        self.show_config_canvas()

    def __hmi_graphic(self, tags):
        self.configure_canvas.delete(tk.ALL)
        self.configure_canvas.config(background='white')
        self.static_graphic.create_edit_graphic_screen(self.configure_canvas)
        self.show_config_canvas()

    def __export_graphic(self, tags):
        filename = asksaveasfilename(filetypes = [("SVG or PNG file", "*.svg *.png")])
        self.static_graphic.export_graphic(filename)

    def __locations(self, tags):
        self.configure_canvas.delete(tk.ALL)
        self.configure_canvas.config(background='indigo')
        self.show_underconstruction_config_canvas()
        self.show_config_canvas()

    def __show_display(self, tags):
        self.configure_canvas.delete(tk.ALL)
        self.configure_canvas.config(background='violet')
        self.show_underconstruction_config_canvas()
        self.show_config_canvas()

        
    def cell_size(self):
        
        return 654 + self.__image_view_height



class expandable_list_canvas_hmi_display_cell(expandable_list_canvas_cell):
    def __init__(self, canvas: expandable_list_canvas, group_id, cell_id ,name='',description='',username='',is_linked=True,assignment_id=''
                 ,cell_highlighted_callback=None, cell_unhighlighted_callback=None,assigned_type=''):
        expandable_list_canvas_cell.__init__(self, canvas,group_id,cell_id, name=name,description=description,username=username,assignment_id=assignment_id

                                            ,cell_highlighted_callback=cell_highlighted_callback, cell_unhighlighted_callback=cell_unhighlighted_callback
                                            ,delete_from_database_callback=self.__delete_from_database)
        self.group_id = group_id
        self.cell_id = cell_id
        self.widgets_created = False
        self.description_entry = None
        self.name = name 
        self.description = description
        self.hmi_display = HMI_Display(self.cell_id, name,description, self.group_id, self.__go_to_document_path)
        self.hmi_display.document_selected_func(self.get_document_selected_func())
        self.pass_document_selection_subscription_func = self.__pass_document_selection_subscription

        
        

    def __go_to_document_path(self, path, doc_type=Database.DRAWING):
        func = self.get_document_selected_func()
        func(path,doc_type)

    def __pass_document_selection_subscription(self, subscription):
        self.hmi_display.document_selection_subscription(subscription)
        
        
    def create_widgets(self):
        self.name_entry = linked_text_entry(self.canvas, 8,56,placeholder='Name',focus_out_callback=self.__name_entry_focusout)
        
        self.name_entry.entry.insert(0, self.name)
        self.page_links = tk.PhotoImage(data=page_links)
        self.goto_image = tk.PhotoImage(data=goto_dark_gray)
        self.linked_graphic = tk.PhotoImage(data=linked_graphic)
        self.build = tk.PhotoImage(data=build)
        self.export = tk.PhotoImage(data=export)
        self.start_scan = tk.PhotoImage(data=start_scan)
        self.connect_lines = tk.PhotoImage(data=connect_lines)
        
        self.description_entry = custom_entry(self.canvas, 8,126,placeholder='Description',focus_out_callback=self.__description_entry_focusout)
        self.description_entry.entry.insert(0, self.description)
        self.reference_document = custom_label(self.canvas, 8, 176, text="Reference Document", fill= '#505050',size=11,weight="bold")
        self.reference_document_value = custom_label(self.canvas, 8, 194, text="XXXX-XXXX-XXXX-XXXX", fill= '#505050' ,size=11,weight="normal")
        self.reference_page = custom_label(self.canvas, 8, 216, text="Page", fill= '#505050',size=11,weight="bold")
        self.reference_page_value = custom_label(self.canvas, 8, 234, text="0000", fill= '#505050' ,size=11,weight="normal")
        self.position = custom_label(self.canvas, 8, 256, text="Position", fill= '#505050',size=11,weight="bold")
        self.position_x_label = custom_label(self.canvas, 8, 274, text="X", fill= '#D7D7D7',size=11,weight="bold")
        self.position_x_value = custom_label(self.canvas, 24, 274, text="000000", fill= '#505050' ,size=11,weight="normal")
        self.position_y_label = custom_label(self.canvas, 90, 274, text="Y", fill= '#D7D7D7',size=11,weight="bold")
        self.position_y_value = custom_label(self.canvas, 106, 274, text="000000", fill= '#505050' ,size=11,weight="normal")
        tags = (self.group_id, self.cell_id, "configure_frame")
        self.buttonA = rounded_image_button(self.canvas, 16, 294, 10, text="SHOW LINK", icon_image=self.goto_image, borderwidth=1, 
                    tags= tags + ('show link',), callback=self.__show_link)
        self.buttonC = rounded_image_button(self.canvas, 16, 338, 10, text="LINKED GRAPHICS", icon_image=self.linked_graphic, borderwidth=1, 
                    tags= tags + ('linked graphics',), callback=self.__linked_graphic)
        self.buttonD = rounded_image_button(self.canvas, 16, 382, 10, text="EXPORT STATIC GRAPHICS", icon_image=self.export, borderwidth=1, 
                    tags= tags + ('export graphics',), callback=self.__export_graphics)
        self.buttonE = rounded_image_button(self.canvas, 16, 426, 10, text="PAGE LINKS", icon_image=self.page_links, borderwidth=1, 
                    tags= tags + ('page links',), callback=self.__page_links)
        self.cell_divider = cell_line(self.canvas, 48, 28, 486, fill= '#E5E5E5', width=1)
        
        self.buttonF = rounded_image_button(self.canvas, 16, 496, 10, text="BUILD DISPLAY", icon_image=self.build, borderwidth=1, 
                    tags= tags + ('build display',), callback=self.__build_display)
        self.buttonG = rounded_image_button(self.canvas, 16, 540, 10, 
                                            text="RUN SCAN", 
                                            borderwidth=1, 
                                            tags=('button','B'),
                                            icon_image=self.start_scan,
                                            callback=self.__start_document_scan)
    

    def expand(self):
        self.canvas.config(cursor="wait")
        project_name,database,config = self.get_project()
        self.hmi_display.setup_project(project_name,database,config)
        self.hmi_display.setup_data_handler(self.get_data_handler())
        if not self.widgets_created:
            self.create_widgets()
            self.widgets_created = True

        y = self.y
        #self.description_entry_label = self.canvas.create_text(20,y + 56, text='Description',font=('Arial',11,'bold'), anchor=tk.NW, tags=self.tags, fill="#505050")
        if not self.entry_widgets_hidden:
            self.name_entry.draw(0,y)
            self.description_entry.draw(0,y)
        self.reference_document.draw(0,y)
        self.reference_document_value.draw(0,y)
        self.reference_page.draw(0,y)
        self.reference_page_value.draw(0,y)
        self.position.draw(0,y)
        self.position_x_label.draw(0,y)
        self.position_x_value.draw(0,y)
        self.position_y_label.draw(0,y)
        self.position_y_value.draw(0,y)
        self.buttonA.draw(0,y )
        self.buttonC.draw(0,y )
        self.buttonD.draw(0,y )
        self.buttonE.draw(0,y )
        self.cell_divider.draw(y )
        self.buttonF.draw(0,y )
        self.buttonG.draw(0,y )
        self.hmi_display.add_linked_name_text_entry(self.name_entry)
        self.expanded = True
        self.__populate_details()
        self.canvas.config(cursor="")


    def __populate_details(self):

        # set document name
        document = self.hmi_display.get_document()
        if not document:
            document = 'Not defined' 
        self.reference_document_value.set_text(document)

        # set page number
        page = self.hmi_display.get_page()
        if not page:
            page = 'Not defined'
        self.reference_page_value.set_text(page)

        # set coordinates
        coordinates = self.hmi_display.get_coordinates()
        if not coordinates:
            x_coordinate = 'N/A'
            y_coodintate = 'N/A'
        else:
            x_coordinate = "{:0.2f}%".format(coordinates[0]*100)
            y_coodintate = "{:0.2f}%".format(coordinates[1]*100)

        self.position_x_value.set_text(x_coordinate)
        self.position_y_value.set_text(y_coodintate)
    
        
    
    def delete(self):
        if self.description_entry:
            if not self.entry_widgets_hidden:
                self.name_entry.hide()
                self.description_entry.hide()
            self.reference_document.hide()
            self.reference_document_value.hide()
            self.reference_page.hide()
            self.reference_page_value.hide()
            self.position.hide()
            self.position_x_label.hide()
            self.position_x_value.hide()
            self.position_y_label.hide()
            self.position_y_value.hide()
            self.buttonA.hide()
            self.buttonC.hide()
            self.buttonD.hide()
            self.buttonE.hide()
            self.cell_divider.hide()
            self.buttonF.hide()
            self.buttonG.hide()
            self.hmi_display.clear_text_in_document_viewer_panel()
        self.template_delete()
        self.expanded = False


    def __delete_from_database(self):
        project_name,database,config = self.get_project()
        self.hmi_display.setup_project(project_name,database,config)
        self.hmi_display.setup_data_handler(self.get_data_handler())
        self.hmi_display.delete_from_database()
        
    
    def hide_entry_widgets(self):
        self.name_entry.hide()
        self.description_entry.hide()
        self.entry_widgets_hidden = True # Used ti handle redarw cases 
        
        
    def show_entry_widgets(self):
        y = self.y
        self.name_entry.draw(0,y)
        self.description_entry.draw(0,y)
        self.hmi_display.draw_linked_text()
        self.entry_widgets_hidden = False # Used to handle redarw cases 
        
        
    
    
    def __name_entry_focusout(self):
        text = self.name_entry.entry.get()
        if not Validators.check_object_name_acm_valid(text):
            self.name_entry.error('Name not ACM compliant')
        else:
            self.name_entry.reset_error()
        self.hmi_display.set_name(text)
        self.canvas.itemconfig(self.name_label,text=text)
        self.name = text


    def __description_entry_focusout(self):
        text = self.description_entry.entry.get()
        self.hmi_display.set_description(text)
        self.description = text
        self.canvas.itemconfig(self.description_label,text=text)
        self.fit_description_in_mutiline()
    

    def __start_document_scan(self, tags):
        try:
            self.hmi_display.start_document_scan()
        except OSError as error:
            messagebox.showwarning('Already started',error)
        except Exception as error:
            messagebox.showerror('Error starting scan',error)
        else:
            self.add_background_task_callback(self.cell_id,self)
            self.add_primary_running_task(self.__check_scanner_progress)
            self.hmi_display.remove_background_task_callback(self.remove_background_task_callback)


    def __check_scanner_progress(self):
        return self.hmi_display.check_scanner_progress()
        

    def __show_link(self, tags):
        try:
            self.hmi_display.go_to()
        except Exception as error:
            messagebox.showerror('Error showing link',error)

    def __linked_graphic(self, tags):
        self.configure_canvas.delete(tk.ALL)
        self.configure_canvas.config(background='white')
        self.hmi_display.create_linked_graphics_screen(self.configure_canvas)
        self.show_config_canvas()

    def __build_display(self, tags):
        try: 
            output_path = askdirectory(title='Build PLC')

            if output_path == '': return
            self.hmi_display.build_display(self.canvas, output_path)
        except Exception as error:
            messagebox.showerror('Error building display',error)

    def __export_graphics(self, tags):
        folder = askdirectory()

        if folder == "": return
        
        self.hmi_display.export_graphics(folder)

    def __page_links(self, tags):
        self.configure_canvas.delete(tk.ALL)
        self.configure_canvas.config(background='white')
        self.hmi_display.create_page_links_list_view(self.configure_canvas)
        self.show_config_canvas()

    def __show_display(self, tags):
        self.configure_canvas.delete(tk.ALL)
        self.configure_canvas.config(background='violet')
        self.show_underconstruction_config_canvas()
        self.show_config_canvas()

    def __extract_lines(self, tags):
        self.configure_canvas.delete(tk.ALL)
        self.configure_canvas.config(background='violet')
        self.show_underconstruction_config_canvas()
        self.show_config_canvas()

        
    def cell_size(self):
        return 614 
    
if __name__ == "__main__":
    root = tk.Tk()
    canvas = tk.Canvas(root)
    canvas.grid()
    canvas.config(background='white', highlightthickness = 0)
    a = expandable_list_canvas_control_module_cell(canvas,"0","0")
    expanded = False
    
    def redraw(event):
        global a 
        a.delete()
        a.draw(0)
        a.expand()
        
    def click(event):
        global a, expanded, canvas
        canvas.focus_set()
        canvas.focus("") # just to be sure
        
        x = canvas.canvasx(event.x)
        y = canvas.canvasy(event.y)
        print(canvas.find_closest(x,y))
        tags = canvas.gettags(canvas.find_closest(x,y))
        if 'current' in tags:
            print("Current Widget")
        print(tags)
        
        if expanded:
            #a.delete()
            #a.draw(0)
            expanded = False
        else:
            #a.delete()
            #a.draw(0)
            #a.expand()
            expanded = True
            
        

    
    canvas.bind('<Configure>', redraw)  # canvas is resized
    
    canvas.bind('<Button-1>',click)
    
    canvas1 = expandable_list_canvas(root)
    canvas1.insert_header("1", "Page 1", 0)
    canvas1.insert_element("1",'id1', 'name', 'user',expandable_list_canvas_control_module_cell)
    canvas1.insert_element("1",'id2', 'name', 'user',expandable_list_canvas_control_module_cell)
    canvas1.insert_header("2", "Page 12", 0)
    canvas1.insert_element("2",'id1', 'name', 'user',expandable_list_canvas_control_module_cell)
    canvas1.insert_element("2",'id2', 'name', 'user',expandable_list_canvas_control_module_cell)
    canvas1.insert_header("3", "Page 13", 0)
    canvas1.insert_element("3",'id1', 'name', 'user',expandable_list_canvas_control_module_cell)
    canvas1.insert_element("3",'id2', 'name', 'user',expandable_list_canvas_control_module_cell)
    canvas1.grid()
    
    
   