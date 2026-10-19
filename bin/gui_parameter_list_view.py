from os import link
from re import X
import re
import threading
import tkinter as tk
from difflib import SequenceMatcher
from tkinter import font
from tkinter import messagebox
from typing import Dict
from uuid import uuid4
from PIL import Image, ImageDraw, ImageTk
from rapidfuzz import process
from bin.gui_approval_view import rectangle_canvas_button
from bin.gui_link_ignore_text_view import link_ignore_text_view, linked_text_boolean_selector, linked_text_ignore_entry, linked_text_interger_selector, linked_text_string_selector
from bin.gui_link_view import link_ignore_view


from bin.gui_parameter_selection import boolean_selector, drop_down_selector, interger_selector, string_selector
from bin.logic_acm_data_handler import ACM_Data_Handler
from bin.logic_acm_parameter import acm_paramter
from bin.logic_internal_database import Database
from bin.logic_linked_text import Linked_Text
from bin.logic_linked_texts import Linked_Texts
from bin.logic_profile import profile


try:
    from bin.gui_link_view import link_view
    from bin.gui_linked_text_entry_view import linked_text_entry
    from bin.gui_elements import custom_entry
    from bin.gui_ghost_text_widget import custom_ghost_entry
except:
    from gui_link_view import link_view
    from gui_linked_text_entry_view import linked_text_entry
    from gui_elements import custom_entry

class parameter_list_view():
    def __init__(self, canvas:tk.Canvas,acm_data_handler: ACM_Data_Handler,object_id,project_name,x=0,y=0, selected_parameter_dict={}, full_paramater_dict={}
                        , tagname='', library_id='', redraw_callback=None, go_to_callback=None, db:Database=None,config=None
                        , is_active_callback=None) -> None:
        self.__canvas = canvas 
        self.__object_id = object_id
        self.__acm_data_handler = acm_data_handler
        self.__library_id = library_id
        self.__config = config
        self.__is_active_callback = is_active_callback
        if self.__library_id:
            self.__library_type = self.__acm_data_handler.get_registered_library(self.__library_id)['CatalogNumber'].iloc[0]
        self.__db = db
        self.__project_name = project_name
        self.__redraw_callback = redraw_callback
        self.__go_to_callback = go_to_callback
        self.__tagname = tagname
        self.__selected_parameter_dict = selected_parameter_dict
        self.__id = uuid4()
        down_arrow = Image.new('RGBA', (15, 15), '#00000000')
        draw = ImageDraw.Draw(down_arrow)
        draw.line([(0, 4), (7, 11), (14, 4) ], fill=(220,220,220,255),width=2)
        up_arrow = down_arrow.rotate(180)
        self.__down_arrow = ImageTk.PhotoImage(down_arrow)
        self.__up_arrow = ImageTk.PhotoImage(up_arrow)
        self.__opened_parameter = ''
        self.__parameter_cells:Dict[str:parameter_cell] = {}
        self.__create_parameter_cells()
        self.__x = x
        self.__y = y
        self.__width = None
        self.__header_font = font.Font(family="Helvetica",size=11,weight="normal")
        self.__allow_adding_locations = True
        self.__show_add_parameter = True
        self.__add_text = None
        self.__full_parameter_dict = full_paramater_dict
        self.__add_parameter_view = add_parameter_view(self.__canvas, cancel_callback=self.__cancel_add_parameter,add_callback=self.__add_parameter)
        self.__update_autocomplete_entry()
        self.__document_selection_subscription_selected = None
        self.__document_selection_subscription_kwargs = None
        self.__document_type = None
        self.__text_in_table = True
        self.__data_loaded = False
        self.__predicted_parameter_callback = None
        self.__pending_parameters = set()
        self.__drawing = False
        self.__redraw_queued = False
        self.__reload_scheduled = False
        if self.__db is not None and self.__object_id is not None and self.__tagname:
            # subobject_type None keys this object level subscription apart from the subobject views
            self.__db.unsubscribe_unapproved_text_link_detailed_update(self.__object_id, None)
            self.__db.subscribe_unapproved_text_link_detailed_update(self.__object_id, None
                                                        , self.internal_db_linked_text_change_callback)


    def internal_db_linked_text_change_callback(self, _linked_text_id=None):
        if not self.__pending_parameters and self.__data_loaded is False:
            return
        # A batch of pending links fires one callback each, so only one reload is queued
        if self.__reload_scheduled:
            return
        self.__reload_scheduled = True
        # Deferred so an in-flight approve/reject is not torn down mid call
        self.__canvas.after(0, self.__reload_linked_text_parameters)


    def __reload_linked_text_parameters(self):
        self.__reload_scheduled = False
        if not self.__canvas.winfo_exists():
            return
        for parameter in self.__pending_parameters:
            cell = self.__parameter_cells.pop(parameter, None)
            if cell:
                cell.hide()
            self.__selected_parameter_dict.pop(parameter, None)
            if self.__opened_parameter == parameter:
                self.__opened_parameter = ''
        self.__pending_parameters = set()
        self.__data_loaded = False
        if self.__redraw_callback:
            self.__redraw_callback()
        else:
            self.draw()
        


    def __update_autocomplete_entry(self):
        autocomplete_list = []
        for parameter, data in self.__full_parameter_dict.items():


            if data['ROnly'] == 'true':
                continue 
            
            if data['RType'] != 'Immediate' and data['RType'] != 'Reference': 
                continue 

            if parameter not in self.__parameter_cells:
                autocomplete_list.append(parameter + ' | ' + data['ParH'])

        self.__add_parameter_view.update_autocomplete(autocomplete_list)


    def __create_parameter_cells(self):
        if self.__object_id is None:
            return
        for parameter, data in self.__selected_parameter_dict.items():
            self.__parameter_cells[parameter] = parameter_cell(self.__canvas,self.__acm_data_handler,self.__object_id
                                                ,data,self.__project_name,tagname=self.__tagname
                                                , library_id=self.__library_id, library_type=self.__library_type
                                                , goto_callback=self.__go_to_callback
                                                ,redraw_callback=self.__redraw_callback
                                                ,config=self.__config)
            if self.__document_selection_subscription_kwargs is None:
                continue
            self.__parameter_cells[parameter].document_selection_subscription(self.__document_selection_subscription_selected
                                                                            ,**self.__document_selection_subscription_kwargs)

        
    def document_selection_subscription(self, selected , **kwargs):
        self.__document_selection_subscription_selected = selected
        self.__document_selection_subscription_kwargs = kwargs
        self.__document_type = kwargs.get('document_type',Database.TEXT)
        for _, parameter_cell in self.__parameter_cells.items():
            parameter_cell.document_selection_subscription(selected , **kwargs)


    def __cell_size(self):
        return 250
        

    def show_linked_text(self, linked_text):
        parameters = linked_text['parameters'].keys()

        if parameters:
            self.__opened_parameter = list(parameters)[0]
            self.draw()


    def draw(self,x=0,y=0,width=None):
        # A deferred redraw can arrive after the user moved to another screen on the shared canvas
        if self.__is_active_callback and not self.__is_active_callback():
            return
        # Building cells can trigger the redraw callback mid draw, which would leave
        # half drawn canvas elements behind, so nested draws are coalesced into one
        if self.__drawing:
            self.__redraw_queued = True
            return
        self.__drawing = True
        try:
            self.__draw(x,y,width)
        finally:
            self.__drawing = False

        if self.__redraw_queued:
            self.__redraw_queued = False
            self.__canvas.after_idle(self.__deferred_redraw)


    def __deferred_redraw(self):
        if not self.__canvas.winfo_exists():
            return
        if self.__redraw_callback:
            self.__redraw_callback()
        else:
            self.draw()


    def __draw(self,x=0,y=0,width=None):
        if width:
            self.__width = width
        else:
            width = self.__width
        if width is None and self.__width is None:
            width = 200
        self.__delete_list()
        count = 0
        x = self.__x + x 
        y = self.__y + y

        if not self.__data_loaded:
            self.__data_loaded = True
            self.__get_all_linked_text_parameters()
            

        
        for parameter, _ in self.__selected_parameter_dict.items():
            if parameter in self.__parameter_cells:
                self.__parameter_cells[parameter].hide()

            if parameter != self.__opened_parameter:
                image = self.__down_arrow
                increase = 55
                func = self.__open_parameter
                draw_parameter = False 
            else:
                image = self.__up_arrow
                increase = self.__cell_size()
                func = self.__close_parameter
                draw_parameter = True

            tags=(self.__id,parameter,count)
            rect = self.__canvas.create_rectangle(x,y,x+width,y+increase,fill='',outline='',tags=tags)
            name = parameter.split(' | ')[0]
            is_pending = parameter in self.__pending_parameters
            name_fill = '#A3A3A3' if is_pending else '#606060'
            description_fill = '#A3A3A3' if is_pending else '#6F6F6F'
            if is_pending:
                name = 'Pending ' + name

            text = self.__canvas.create_text(x+16,y+21,anchor=tk.NW,text=name,tags=tags,fill=name_fill,font=self.__header_font)
            
            divider = self.__canvas.create_line(int(self.__canvas.winfo_width()/2), y + 14, int(self.__canvas.winfo_width()/2), y + 38, fill='#D5D5D5', width=2, tags=tags)
            description = parameter.split(' | ')[-1]
            description_label = self.__canvas.create_text(int(self.__canvas.winfo_width()/2)+4,y + 18, text=description, anchor=tk.NW, tags=tags, fill=description_fill)
            description_label = self.fit_description_in_mutiline(description_label,description,tags,y,fill=description_fill)
            rect_to_hide_text = self.__canvas.create_rectangle(x + width-23,y,x + width, y+increase,fill='white',outline='',tags=tags)
            icon = self.__canvas.create_image(x + width-16,y+28,image=image,tags=tags)
            if draw_parameter:
                cell_height = self.__parameter_cells[parameter].draw(x,y + 50)
                increase = increase + cell_height + 30
            self.__canvas.create_line(x+8,y+increase,x+width-8,y+increase,width=1,fill='#D5D5D5',tags=tags)
            self.__canvas.tag_bind(rect,'<Button-1>',func)
            self.__canvas.tag_bind(text,'<Button-1>',func)
            self.__canvas.tag_bind(icon,'<Button-1>',func)
            self.__canvas.tag_bind(divider,'<Button-1>',func)
            self.__canvas.tag_bind(description_label,'<Button-1>',func)
            self.__canvas.tag_bind(rect_to_hide_text,'<Button-1>',func)

            y = increase + y 

        if self.__opened_parameter in self.__parameter_cells:
            self.__parameter_cells[self.__opened_parameter].setup_regex_on_viewer()

        if not self.__show_add_parameter:
            self.__draw_add_button(x + 16, y + 24)
        else:
            self.__delete_add_parameter()
            self.show_add_parameter_interface(x + 4, y + 24)

        self.__canvas.config(scrollregion=(0,0,self.__canvas.bbox(tk.ALL)[2],self.__canvas.bbox(tk.ALL)[3]+100))



    def __get_all_linked_text_parameters(self):
        pending_linked_text_parameters = []
        if self.__tagname:
            linked_text_parameters = self.__db.get_all_approved_object_parameters_text_link(self.__tagname)
            pending_linked_text_parameters = self.__db.get_all_unapproved_object_parameters_text_link(self.__tagname)
        elif self.__library_id and self.__library_type:
            linked_text_parameters = self.__db.get_all_linked_text_regexes_by_object_type(self.__library_type)

        for linked_text_parameter in linked_text_parameters:
            self.__build_linked_text_parameter_cell(linked_text_parameter, True)

        for linked_text_parameter in pending_linked_text_parameters:
            self.__build_linked_text_parameter_cell(linked_text_parameter, False)

        if self.__selected_parameter_dict:
            self.__show_add_parameter = False
            if self.__opened_parameter not in self.__parameter_cells:
                self.__opened_parameter = ''


    def __build_linked_text_parameter_cell(self, linked_text_parameter, is_approved):
        parameter = list(linked_text_parameter['parameters'].keys())[0]
        if not is_approved and (parameter in self.__parameter_cells or parameter not in self.__full_parameter_dict):
            return
        data = {
        'properties': self.__full_parameter_dict[parameter],
        'value': linked_text_parameter['parameters'][parameter]['text']
        }
        self.__selected_parameter_dict[parameter] = data
        replaced_cell = self.__parameter_cells.get(parameter)
        if replaced_cell:
            replaced_cell.hide()
        self.__parameter_cells[parameter] = parameter_cell(self.__canvas,self.__acm_data_handler,self.__object_id,data,self.__project_name
                        ,tagname=self.__tagname,library_id=self.__library_id,library_type=self.__library_type
                        ,redraw_callback=self.__redraw_callback,goto_callback=self.__go_to_callback,db=self.__db
                        ,config=self.__config)

        self.__parameter_cells[parameter].setup_linked_text(linked_text_parameter, is_approved=is_approved)

        if not is_approved:
            self.__pending_parameters.add(parameter)

        if self.__document_selection_subscription_kwargs is not None:
            self.__parameter_cells[parameter].document_selection_subscription(self.__document_selection_subscription_selected
                                                                        ,**self.__document_selection_subscription_kwargs)



    def __draw_add_button(self, x, y):
        padding = 8
        self.__delete_elements()
        
        x = self.__x + x # For static elements
        y = self.__y + y + padding # For static elements
        
        if self.__allow_adding_locations:
            self.__add_text = self.__canvas.create_text(x, y,  
                                                                text='+ Add parameter ', 
                                                                font=('Arial',10,'normal'), 
                                                                anchor=tk.NW, 
                                                                fill="#505050")
        else:
            self.__add_text = self.__canvas.create_text(x, y,  
                                                                text='+ Add parameter ', 
                                                                font=('Arial',10,'normal'), 
                                                                anchor=tk.NW, 
                                                                fill="#C0C0C0")
        bounds = self.__canvas.bbox(self.__add_text)
        self.__add_rect = self.__canvas.create_rectangle(bounds[0]-padding ,bounds[1] -padding,bounds[2]+ padding ,bounds[3]+ padding,fill='#FFFFFF', width = 0, tags=('add_text_location'))
        self.__canvas.tag_raise(self.__add_text)
        

        self.__canvas.tag_bind(self.__add_rect,'<Enter>', self.__on_add_enter)
        self.__canvas.tag_bind(self.__add_rect,'<Leave>', self.__on_add_leave)
        self.__canvas.tag_bind(self.__add_text,'<Enter>', self.__on_add_enter)
        self.__canvas.tag_bind(self.__add_text,'<Leave>', self.__on_add_leave)
        self.__canvas.tag_bind(self.__add_rect,'<Button-1>', self.__on_add_click)
        self.__canvas.tag_bind(self.__add_text,'<Button-1>', self.__on_add_click)


    def __delete_elements(self):
        if self.__add_text:
            self.__canvas.delete(self.__add_text)
            self.__canvas.delete(self.__add_rect)
        if self.__add_parameter_view:
            self.__add_parameter_view.hide()


    def __delete_add_parameter(self):
        if self.__add_text:
            self.__canvas.delete(self.__add_text)
            self.__canvas.delete(self.__add_rect)


    def __on_add_enter(self,_):
        self.__canvas.itemconfig(self.__add_rect, fill='#E5E5E5')


    def __on_add_leave(self,_):
        self.__canvas.itemconfig(self.__add_rect, fill='#FFFFFF')


    def __on_add_click(self,_):
        if not self.__allow_adding_locations:
            return 
        
        self.__show_add_parameter = True 
        self.__add_parameter_view.clear_entry()
        self.draw()


    def show_add_parameter_view_with_prediction(self, text, callback=None):
        if not self.__allow_adding_locations:
            return 
        
        self.__show_add_parameter = True 
        self.__add_parameter_view.clear_entry()
        self.draw()
        self.__predicted_parameter_callback = callback
        self.__canvas.after(100, self.__add_parameter_view.set_first_prediction, text)
        

    
    def show_add_parameter_interface(self, x, y):
        
        self.__add_parameter_view.draw(x,y)


    def __cancel_add_parameter(self):
        if self.__add_parameter_view:
            self.__add_parameter_view.hide()
        self.__show_add_parameter = False
        self.draw()


    def __add_parameter(self, parameter):
        parameter_name = parameter.split(' | ')[0]

        data = {
            'properties': self.__full_parameter_dict[parameter_name],
            'value': ''
        }

        if ("properties" in data and 'Filter' in data['properties'] 
            and data['properties']['Filter'] == "Library.LibraryType='HMI' And Library.Category='Display'"):
            messagebox.showwarning("Display paramter linking not allowed", "Cannot link to a display parameter. Display parameters are linked through visual type documents.")
            return

        
        self.__selected_parameter_dict[parameter_name] = data
        self.__parameter_cells[parameter_name] = parameter_cell(self.__canvas,self.__acm_data_handler,self.__object_id,data,self.__project_name
                            ,tagname=self.__tagname,library_id=self.__library_id,redraw_callback=self.__redraw_callback,goto_callback=self.__go_to_callback
                            ,db=self.__db,config=self.__config)
        if self.__document_selection_subscription_kwargs is not None:
            self.__parameter_cells[parameter_name].document_selection_subscription(self.__document_selection_subscription_selected
                                                                            ,**self.__document_selection_subscription_kwargs)
        self.__update_autocomplete_entry()
        if self.__add_parameter_view:
            self.__add_parameter_view.hide()
        self.__show_add_parameter = False
        self.__opened_parameter = parameter_name
        if self.__predicted_parameter_callback:
            
            self.__parameter_cells[parameter_name].show_thinking()
            self.__predicted_parameter_callback(self.__full_parameter_dict[parameter_name], self.__predicted_linked_text_callback)
            self.__predicted_parameter_callback = None
        self.draw()


    
    def __predicted_linked_text_callback(self, parameter_properties, tagname_linked_text_data, parameter_linked_text_data):


        if self.__opened_parameter in self.__parameter_cells:
            self.__parameter_cells[self.__opened_parameter].hide_thinking()
            self.__parameter_cells[self.__opened_parameter].predicted_linked_text(parameter_properties,tagname_linked_text_data, parameter_linked_text_data)
            

    def __open_parameter(self, event):
        curX, curY = ( self.__canvas.canvasx(event.x),  self.__canvas.canvasy(event.y))
        id = self.__canvas.find_closest(curX,curY)
        tags = self.__canvas.gettags(id)
        self.__opened_parameter = tags[1]
        self.draw()

    def __close_parameter(self, event):
        curX, curY = ( self.__canvas.canvasx(event.x),  self.__canvas.canvasy(event.y))
        id = self.__canvas.find_closest(curX,curY)
        tags = self.__canvas.gettags(id)
        if tags[1] == self.__opened_parameter:
            self.__opened_parameter = ''
        
        self.draw()


    def ignore_text(self, regex_string, ignore_indexes):
        for _, parameter_cell in self.__parameter_cells.items():
            parameter_cell.ignore_text( regex_string, ignore_indexes)


    def hide(self):
        self.__delete_list()
        self.__delete_elements()


    def __delete_list(self):
        self.__canvas.delete(self.__id)

        for _, parameter_cell in self.__parameter_cells.items():
            parameter_cell.hide()


    def fit_description_in_mutiline(self, description_label, description, tags,y,fill="#6F6F6F"):

        description_bounds = self.__canvas.bbox(description_label) 

        if description_bounds is None:
            return description_label

        if (description_bounds[2] - description_bounds[0]) < (self.__canvas.winfo_width()/2 - 8) or self.__canvas.winfo_width() <= 0:
            return description_label
        
        second_line_substring = 0 
        split = description.split(" ")
        while True :
            second_line_substring = second_line_substring + 1
            multiline_description = ' '.join(split[:second_line_substring])
            self.__canvas.delete(description_label)
            description_label = self.__canvas.create_text(int(self.__canvas.winfo_width()/2)+4,y + 11, text=multiline_description, anchor=tk.NW, tags=tags, fill="#6F6F6F")
            description_bounds = self.__canvas.bbox(description_label)
            if (description_bounds[2] - description_bounds[0]) > (self.__canvas.winfo_width()/2 - 16):
                break
        second_line_substring = second_line_substring - 1
        self.__canvas.delete(description_label)
        multiline_description = ' '.join(split[:second_line_substring])+'\n'+' '.join(split[second_line_substring:])
        return self.__canvas.create_text(int(self.__canvas.winfo_width()/2)+4,y + 11, text=multiline_description, anchor=tk.NW, tags=tags, fill="#6F6F6F")
        


class parameter_cell():

    
    
    def __init__(self,  canvas:tk.Canvas,acm_data_handler: ACM_Data_Handler,object_id,parameter,project_name,x=0,y=0, tagname=''
                    , library_id='', library_type='',redraw_callback=None,goto_callback=None, db:Database=None, config=None) -> None:
        self.__canvas = canvas
        self.__object_id = object_id
        self.__acm_data_handler = acm_data_handler
        self.__config = config
        self.__db = db
        self.__x = x
        self.__y = y 
        self.__width = None 
        self.__options = None
        self.__selected_option = None
        self.__cell_height = 0
        self.__predicted_output = False
        self.__parameter_properties = parameter['properties']
        self.__id = uuid4()
        self.__tagname = tagname
        self.__library_id = library_id
        self.__library_type = library_type
        self.__parameter = self.__parameter_properties['Name']
        self.__heading_font = font.Font(family="Helvetica",size=11,weight="bold")
        self.__selection_in_document_selected = False
        self.__redraw_callback = redraw_callback
        self.__goto_callback_func = goto_callback
        self.__acm_parameter = acm_paramter(self.__object_id,self.__acm_data_handler,self.__parameter_properties,project_name)
        if self.__tagname:
            self.__object_type = self.__acm_data_handler.get_object_with_name(self.__tagname)['CatalogNumber'].iloc[0]
        elif self.__library_id:
            self.__object_type = self.__library_type
        """ self.__linked_text = Linked_Text(acm_data_handler,
                                        linked_callback=self.__text_unlinked_callback,
                                        goto_callback=self.__goto_roi,
                                        object_type=self.__object_type,
                                        tagname=tagname,
                                        db=db) """
        self.__linked_text = Linked_Texts(acm_data_handler
                                          ,change_callback=self.__redraw_callback
                                          ,goto_callback=self.__goto_roi
                                          ,object_type=self.__object_type
                                          ,tagname=tagname
                                          ,db=db)
        self.__linked_text.add_parameter(self.__parameter, self.__parameter_properties['DType'])
        self.__parameter_type = None 
        self.__parameter_entry = None
        self.__tagname_entry = None
        self.__document_type = None 
        self.__text_in_table = False
        self.__draw_done_button = True
        self.__regex_refresh_parameter = False
        self.__regex_refresh_entry_name = ''
        self.__setup_views()



    def __redraw_tagname_callback(self, _=None):
        self.__regex_refresh_parameter = False 
        self.__regex_refresh_entry_name = 'tagname'
        self.__redraw_callback()





    def __redraw_parameter_callback(self, parameter):
        self.__regex_refresh_parameter = True 
        self.__regex_refresh_entry_name = parameter
        self.__redraw_callback()


    def setup_linked_text(self, data, is_approved=False):
        self.__draw_done_button = False
        self.__linked_text.set_data(data)

        parameter = list(data['parameters'].keys())[0]

        if self.__library_id:
            self.__tagname_entry.entry.insert(0,data['tagname']['text'])
            self.__tagname_entry.entry.config(state='readonly')

        if self.__object_id:
            acm_value = self.__acm_parameter.get_value()
        else:
            acm_value = data['parameters'][parameter]['text']

        if (is_approved and acm_value != data['parameters'][parameter]['text']):
            self.__parameter_entry.error('ACM value does not match approved value'
                                         ,True)
        self.__parameter_entry.set_text(data['parameters'][parameter]['text'])

        if self.__library_id:
            self.__parameter_entry.entry.config(state='readonly')
        


    def document_selection_subscription(self, selected , **kwargs):
        self.__selection_in_document_selected = selected

        self.__check_if_selection_in_document_made()
        if not kwargs:
            return 

        document_type = kwargs.get('document_type',Database.TEXT)

        if document_type != self.__document_type:
            self.__document_type = document_type
            self.__set_linked_entry_table_text_selection()
            self.__redraw_callback()

        text_in_table =  kwargs.get('text_in_table',True)

        if self.__text_in_table != text_in_table:
            self.__text_in_table= text_in_table
            self.__set_linked_entry_table_text_selection()
            self.__redraw_callback()

        
        self.__linked_text.setup_linking_callback_func(kwargs.get('roi_select_func',None), self.__document_type)
        self.__linked_text.setup_get_sheet_dataframe_func(kwargs.get('get_sheet_dataframe',None))
        self.__linked_text.setup_text_document_linking_funcs(
                                                    kwargs.get('given_text',None),
                                                    kwargs.get('ignore_text',None),
                                                    kwargs.get('remove_given_text',None)
                                                    )
        
        self.__linked_text.setup_regex_show_funcs (
            kwargs.get('setup_regex_template',None),
            kwargs.get('remove_highlight_regex_template',None)
        )

        self.__linked_text.setup_linked_text_highlight_funcs(
            kwargs.get('setup_highlighted_linked_text',None),
            kwargs.get('remove_highlight_linked_text',None),
        )

        if self.__parameter_type == 'selector':
            if selected:
                self.__parameter_entry.enable_linking()
            else:
                self.__parameter_entry.disable_linking()

        

    
    def __check_if_selection_in_document_made(self):
        if self.__selection_in_document_selected:
            self.__tagname_entry.enable_linking()
            self.__parameter_entry.enable_linking()
        else:
            self.__tagname_entry.disable_linking()
            self.__parameter_entry.disable_linking()



    def __goto_roi(self, roi, page_number, path, doc_type):    
        if self.__goto_callback_func:
            self.__goto_callback_func(roi,page_number,path,doc_type)
            


    def __linked_text_entry(self, value=None, **kwargs) -> linked_text_entry:
        
        linked_entry_types = {
            'String': string_linked_text_entry,
            'Real': real_linked_text_entry,
            'Int': integer_linked_text_entry 
        }


        linked_entry:linked_text_entry = linked_entry_types[self.__parameter_properties['DType']](self.__canvas
                                                                        , self.__parameter_properties
                                                                        , value=value
                                                                        , placeholder=self.__parameter
                                                                        , is_parameter=True
                                                                        , **kwargs)
        linked_entry.set_go_to_callback(self.__go_to_roi_parameter_linked_text)
        self.__parameter_type = 'linked_entry'
        return linked_entry


    def __linked_selector(self, value=None, **kwargs):

        selector_types = {
            'String': linked_text_string_selector,
            'Int':linked_text_interger_selector,
            'Bool':linked_text_boolean_selector
        }

        selector:drop_down_selector = selector_types[self.__parameter_properties['DType']](self.__canvas
                                                                    , self.__parameter_properties
                                                                    , value=value
                                                                    , is_parameter=True
                                                                    ,  **kwargs)
        #selector.set_link_callback(self.__parameter_text_linked_callback)
        #selector.set_go_to_callback(self.__go_to_roi_parameter_linked_text)
        self.__parameter_type = 'selector'
        return selector


    def __get_tagname_linked_text(self):
        return self.__linked_text.get_tagname_linked_text()
    

    def __tagname_given_text_linked_callback(self, _, option=None):
        return self.__linked_text.set_tagname_given_text(option=option)
    

    def __unlink_tagname_text(self):
        self.__linked_text.unlink_tagname()

    
    def __key_tagname_text(self, linked, indexes, string, name, use_selection=True, text_view_indexes=None):
        if text_view_indexes:
            start, end, id = text_view_indexes
        elif use_selection:
            start, end, id = self.__tagname_entry.get_text_view_selection()
        else:
            start, end, id = self.__tagname_entry.get_full_text_view_selection()
        self.__tagname_entry.remove_text_view_selection()
        text,key_indexes,ignore_indexes, given_text_id  = self.__linked_text.set_key_tagname_text(linked
                                                                                  , indexes
                                                                                  , string
                                                                                  , name
                                                                                  ,[start,end,id])
        self.__tagname_entry.set_given_text(text, given_text_id )
        self.__tagname_entry.set_ignore_indexes(ignore_indexes)
        self.__tagname_entry.set_key_indexes(key_indexes)
        return linked_text_entry.TOP_SIDE
    

    def __ignore_tagname_text(self,_, ignore_text_view=False):
        if not ignore_text_view:
            start, end, id = self.__tagname_entry.get_text_view_selection()
            self.__tagname_entry.remove_text_view_selection()
        else:
            start, end, id = None, None, None
        text,key_indexes,ignore_indexes, given_text_id = self.__linked_text.set_tagname_ignore_text([start,end,id])

        self.__tagname_entry.set_given_text(text, given_text_id)
        self.__tagname_entry.set_ignore_indexes(ignore_indexes)
        self.__tagname_entry.set_key_indexes(key_indexes)
        self.__redraw_tagname_callback()

    def __unignore_tagname_text(self,_, ignore_text_view=False):
        if not ignore_text_view:
            start, end, id = self.__tagname_entry.get_text_view_selection()
            self.__tagname_entry.remove_text_view_selection()
        else:
            start, end, id = None, None, None
        text,key_indexes,ignore_indexes, given_text_id = self.__linked_text.unset_tagname_ignore_text([start,end,id])

        self.__tagname_entry.set_given_text(text, given_text_id)
        self.__tagname_entry.set_ignore_indexes(ignore_indexes)
        self.__tagname_entry.set_key_indexes(key_indexes)
        self.__redraw_tagname_callback()

    def show_thinking(self):
        self.__predicted_output = True
        self.__tagname_entry.start_thinking()
        if self.__parameter_type == 'linked_entry':
            self.__parameter_entry.start_thinking()


    def hide_thinking(self):
        self.__tagname_entry.stop_thinking()
        if self.__parameter_type == 'linked_entry':
            self.__parameter_entry.stop_thinking()


    @staticmethod
    def __predicted_given_text(linked_text_data):
        # Manual linking stores the whole table cell as the given text, which is what the regex is later matched
        # against row by row. Reshape the prediction the same way so the key indexes line up with the cell.
        given_text = list(linked_text_data['given_text'])
        cell_full_text = given_text[0][0]
        cell_full_indexes = given_text[3][5]
        given_text[0] = [cell_full_text, cell_full_text]
        given_text[1] = cell_full_indexes[0]
        given_text[2] = cell_full_indexes[1]
        return given_text


    @staticmethod
    def __predicted_link_segments(entry_text, predicted_text, predicted_indexes):
        # The entry can hold a normalised tagname (TI2007) while the document reads TI-2007, so link the matching
        # runs individually and leave the separators out, exactly as a user would when linking by hand.
        entry_text = str(entry_text)
        predicted_text = str(predicted_text)
        offset = predicted_indexes[0] if predicted_indexes else 0
        matcher = SequenceMatcher(None, entry_text.lower(), predicted_text.lower(), autojunk=False)
        segments = [([start, start + size], [offset + predicted_start, offset + predicted_start + size])
                    for start, predicted_start, size in matcher.get_matching_blocks() if size]

        if not segments:
            segments = [([0, len(entry_text)]
                         ,list(predicted_indexes) if predicted_indexes else [0, len(predicted_text)])]

        return segments


    def predicted_linked_text(self,parameter_properties, tagname_linked_text_data, parameter_linked_text_data):
        if not tagname_linked_text_data or not parameter_linked_text_data:
            return

        parameter = parameter_properties['Name']
        _, tagname_given_text_id = self.__linked_text.set_tagname_given_text(self.__predicted_given_text(tagname_linked_text_data))

        tagname_text = self.__tagname_entry.entry.get()
        for target_indexes, given_indexes in self.__predicted_link_segments(tagname_text
                                                                           ,tagname_linked_text_data['key_text'][0]
                                                                           ,tagname_linked_text_data['key_text'][2]):
            self.__linked_text.set_key_tagname_text(True
                                                    ,target_indexes
                                                    ,tagname_text
                                                    ,self.__tagname
                                                    ,None
                                                    ,[tagname_text[target_indexes[0]:target_indexes[1]]
                                                      ,tagname_given_text_id
                                                      ,given_indexes])
        
        _, parameter_given_text_id = self.__linked_text.set_parameter_given_text(parameter
                                                                                ,self.__predicted_given_text(parameter_linked_text_data))
        self.__parameter_entry.set_text(parameter_linked_text_data['key_text'][0])

        parameter_text = self.__parameter_entry.entry.get()
        for target_indexes, given_indexes in self.__predicted_link_segments(parameter_text
                                                                           ,parameter_linked_text_data['key_text'][0]
                                                                           ,parameter_linked_text_data['key_text'][2]):
            self.__linked_text.set_key_parameter_text(True
                                                      ,target_indexes
                                                      ,parameter_text
                                                      ,parameter
                                                      ,None
                                                      ,[parameter_text[target_indexes[0]:target_indexes[1]]
                                                        ,parameter_given_text_id
                                                        ,given_indexes])


        self.__canvas.after(0, self.__redraw_tagname_callback)
        self.__canvas.after(0, self.__redraw_parameter_callback, parameter)

    def __get_parameter_linked_text(self, parameter):
        return self.__linked_text.get_parameter_linked_text(parameter)
    

    def __parameter_given_text_linked_callback(self, parameter, _):
        return self.__linked_text.set_parameter_given_text(parameter)
    

    def __unlink_parameter_text(self, parameter):
        self.__linked_text.unlink_parameter(parameter)


    def __key_parameter_text(self, linked, indexes, string, parameter, use_selection=True, text_view_indexes=None):
        if text_view_indexes:
            start, end, id = text_view_indexes
        elif use_selection:
            start, end, id = self.__parameter_entry.get_text_view_selection()
        else:
            start, end, id = self.__parameter_entry.get_full_text_view_selection()
        self.__parameter_entry.remove_text_view_selection()
        text,key_indexes,ignore_indexes, given_text_id  = self.__linked_text.set_key_parameter_text(linked
                                                                                    , indexes
                                                                                    , string
                                                                                    , parameter
                                                                                    , [start,end,id])

        self.__parameter_entry.set_given_text(text, given_text_id )
        self.__parameter_entry.set_ignore_indexes(ignore_indexes)
        self.__parameter_entry.set_key_indexes(key_indexes)
        self.__linked_text.setup_parameter_regex_on_viewer(parameter)
        return linked_text_entry.TOP_SIDE
    

    def __ignore_parameter_text(self, parameter,  ignore_text_view=False):
        if not ignore_text_view:
            start, end, id = self.__parameter_entry.get_text_view_selection()
            self.__parameter_entry.remove_text_view_selection()
        else:
            start, end, id = None, None, None
        text,key_indexes,ignore_indexes, given_text_id = self.__linked_text.set_parameter_ignore_text(parameter,[start,end,id])

        self.__parameter_entry.set_given_text(text, given_text_id)
        self.__parameter_entry.set_ignore_indexes(ignore_indexes)
        self.__parameter_entry.set_key_indexes(key_indexes)
        self.__redraw_parameter_callback(parameter)


    def __unignore_parameter_text(self, parameter,  ignore_text_view=False):
        if not ignore_text_view:
            start, end, id = self.__parameter_entry.get_text_view_selection()
            self.__parameter_entry.remove_text_view_selection()
        else:
            start, end, id = None, None, None
        text,key_indexes,ignore_indexes, given_text_id = self.__linked_text.unset_parameter_ignore_text(parameter,[start,end,id])

        self.__parameter_entry.set_given_text(text, given_text_id)
        self.__parameter_entry.set_ignore_indexes(ignore_indexes)
        self.__parameter_entry.set_key_indexes(key_indexes)
        self.__redraw_parameter_callback(parameter)

    
    def __setup_views(self):

        self.__tagname_entry = string_linked_text_entry(self.__canvas
                                                        ,get_text_link_callback=self.__get_tagname_linked_text
                                                        ,given_text_link_callback=self.__tagname_given_text_linked_callback
                                                        ,key_text_link_callback=self.__key_tagname_text
                                                        ,given_text_unlink_callback=self.__unlink_tagname_given_text
                                                        ,ignore_text_callback=self.__ignore_tagname_text
                                                        ,unignore_text_callback=self.__unignore_tagname_text
                                                        ,redraw_callback=self.__redraw_tagname_callback
                                                        ,goto_callback=self.__go_to_roi_tagname_linked_text
                                                        ,given_text_goto_callback=self.__go_to_roi_tagname_given_text
                                                        ,placeholder='Tagname Link'
                                                        )
        if self.__tagname:
            self.__tagname_entry.entry.insert(0,self.__tagname)
            self.__tagname_entry.entry.config(state='readonly')

        if self.__library_id and self.__object_id is None:
            value = ''
        else:
            parameter_data = self.__acm_data_handler.get_all_parameters_in_object(self.__object_id, self.__parameter).iloc[0].to_dict()

        if self.__parameter_properties['CType'] == 'DropDownList' or self.__parameter_properties['CType'] == 'Bool':
            self.__parameter_entry = self.__linked_selector(value=parameter_data['Value']
                                                            ,selection_callback=self.__get_selector_text
                                                            ,get_text_link_callback=self.__get_parameter_linked_text
                                                            ,given_text_link_callback=self.__parameter_given_text_linked_callback
                                                            ,given_text_unlink_callback=self.__unlink_parameter_given_text
                                                            ,key_text_link_callback=self.__key_parameter_text
                                                            ,goto_callback=self.__go_to_roi_parameter_linked_text
                                                            ,given_text_goto_callback=self.__go_to_roi_parameter_given_text
                                                            ,ignore_text_callback=self.__ignore_parameter_text
                                                            ,unignore_text_callback=self.__unignore_parameter_text
                                                            ,redraw_callback=self.__redraw_parameter_callback)
        elif self.__parameter_properties['RType'] == 'Reference':
            self.__options = self.__acm_parameter.get_all_reference_options()
            if self.__library_id and self.__object_id is None:
                value = ''
            else:
                value = self.__acm_parameter.get_referenced_options(parameter_data['RefType']
                                                    ,parameter_data['Value']
                                                    ,parameter_data['RefValue'])
            self.__autocomplete_list = [x[0] for x in self.__options]
            self.__parameter_entry = self.__linked_text_entry(autocompleteList=self.__autocomplete_list
                                                            ,focus_out_callback=self.__get_referenced_linked_text
                                                            ,edit_callback=self.__edit_entry_callback
                                                            ,value=value
                                                            ,get_text_link_callback=self.__get_parameter_linked_text
                                                            ,given_text_link_callback=self.__parameter_given_text_linked_callback
                                                            ,given_text_unlink_callback=self.__unlink_parameter_given_text
                                                            ,key_text_link_callback=self.__key_parameter_text
                                                            ,goto_callback=self.__go_to_roi_parameter_linked_text
                                                            ,given_text_goto_callback=self.__go_to_roi_parameter_given_text
                                                            ,ignore_text_callback=self.__ignore_parameter_text
                                                            ,unignore_text_callback=self.__unignore_parameter_text
                                                            ,redraw_callback=self.__redraw_parameter_callback)
        else:
            if self.__library_id and self.__object_id is None:
                value = ''
            else:
                value = parameter_data['Value']
            self.__parameter_entry = self.__linked_text_entry(focus_out_callback=self.__get_linked_text
                                                                ,edit_callback=self.__edit_entry_callback
                                                                ,value=value
                                                                ,get_text_link_callback=self.__get_parameter_linked_text
                                                                ,given_text_link_callback=self.__parameter_given_text_linked_callback
                                                                ,given_text_unlink_callback=self.__unlink_parameter_given_text
                                                                ,key_text_link_callback=self.__key_parameter_text
                                                                ,goto_callback=self.__go_to_roi_parameter_linked_text
                                                                ,given_text_goto_callback=self.__go_to_roi_parameter_given_text
                                                                ,ignore_text_callback=self.__ignore_parameter_text
                                                                ,unignore_text_callback=self.__unignore_parameter_text
                                                                ,redraw_callback=self.__redraw_parameter_callback)
        
        
        self.__done_or_accept_button = rectangle_canvas_button('Done',self.__canvas,self.__on_done_click)
        self.__text_link_button = rectangle_canvas_button('Link Text',self.__canvas,self.__on_text_link)

    def __unlink_tagname_given_text(self, _, given_text_id):
        self.__linked_text.remove_highlights_on_viewer()
        self.__linked_text.unlink_tagname_given_text(given_text_id)
        self.__tagname_entry.reset()

    def __unlink_parameter_given_text(self, pararmeter, given_text_id):
        self.__linked_text.remove_highlights_on_viewer()
        self.__linked_text.unlink_parameter_given_text(pararmeter,given_text_id)
        self.__parameter_entry.reset()

    def __on_text_link(self):
        self.__tagname_entry.on_given_text_link(self.__tagname_entry.get())
        self.__parameter_entry.on_given_text_link()
        
        self.__redraw_callback()
    
    def hide_entry_widgets(self):

        if self.__tagname_entry:
            self.__tagname_entry.hide()

        if self.__parameter_entry:
            self.__parameter_entry.hide()

        self.__linked_text.remove_highlight_linked_text()




    def ignore_text(self, linked_text, parameter):
        if linked_text == 'tagname':
            self.__ignore_tagname_text(None, ignore_text_view=True)
        if linked_text == 'parameters':
            self.__ignore_parameter_text(parameter, ignore_text_view=True)


    def show_entry_widgets(self):
        y = self.y
        if self.__config.get_show_advanced_linking():
            self.__tagname_entry.draw(0,y+4)
            self.__parameter_entry.draw(0,y+76)
        else: 
            self.__parameter_entry.draw(0,y+4)


    def __on_done_click(self):
        try:
            self.__linked_text.fully_linked_check()
        except Exception as e:
            messagebox.showwarning("Not fully linked",str(e))
            return
        self.__draw_done_button = False
        ref_type = self.__acm_parameter.write_unknown_referenced_values(self.__parameter
                                                                ,self.__parameter_entry.get())
        self.__linked_text.parameters[self.__parameter].text = self.__parameter_entry.get()
        self.__linked_text.set_parameter_ref_type(self.__parameter,ref_type)
        data = self.__linked_text.get_data()
        self.__db.save_approved_text_link(data)
        self.__thread = threading.Thread(target=self.__create_other_linked_text)
        self.__thread.start()
        if self.__redraw_callback:
            self.__redraw_callback()


    def accept(self):
        self.__acm_parameter.write_referenced_values(self.__linked_text.get_parameter_ref_type(self.__parameter)
                                                     ,self.__parameter
                                                     ,self.__parameter_entry.get())
        data = self.__linked_text.get_data()
        self.__db.save_approved_text_link(data)


    def __create_other_linked_text(self):
        doc_type = self.__linked_text.get_document_type()

        if doc_type == Database.TABLE:
            self.__linked_text.process_2D_referencing()
            self.__linked_text.process_1D_referencing()

        
        if doc_type == Database.TEXT:
            self.__linked_text.save_regex_linked_text()


    def __text_unlinked_callback(self, _):
        self.__linked_text.reset()
        self.__redraw_callback()




    def __tagname_text_linked_callback(self, linked, indexes, string, name):
        
        link_side, text_indexes = self.__linked_text.tagname_link(linked,indexes,string,name)

        if self.__linked_text.is_template_text_linked():
            self.__link_ignore_text_view.highlight_linked(text_indexes[0],text_indexes[-1]+1)

        return link_side


    def __parameter_text_linked_callback(self, linked, indexes, string, name):
        
        link_side, text_indexes = self.__linked_text.parameter_link(linked,indexes,string,name)

        if self.__linked_text.is_template_text_linked():
            self.__link_ignore_text_view.highlight_linked(text_indexes[0],text_indexes[-1]+1)
        
        return link_side


    def __edit_entry_callback(self, text):
        self.__update_reference_autocomplete(text)

        if text and self.__linked_text.parameters[self.__parameter].text != text:
            self.__draw_done_button = True
            if self.__redraw_callback:
                self.__redraw_callback()


    def __update_reference_autocomplete(self, text:str):

        if self.__parameter_entry is None:
            return

        new_options = self.__acm_parameter.get_all_reference_options(text)
        
        if new_options == self.__options:
            return

        self.__options = new_options
        self.__autocomplete_list = [x[0] for x in self.__options]
        if self.__parameter_entry:
            self.__parameter_entry.update_autocomplete_list(self.__autocomplete_list,True)



    def __go_to_linked_text(self,_,indexes_id,__):
        self.__linked_text.goto_tagname(indexes_id)


    def __ignore_linked_text(self):
        self.__linked_text.ignore_text_trigger()


    def __go_to_roi_tagname_linked_text(self,_,indexes_id,__):
        self.__linked_text.goto_tagname(indexes_id)


    def __go_to_roi_parameter_linked_text(self,_=None,indexes_id=None,parameter=None):
        self.__linked_text.goto_parameter(parameter,indexes_id)


    def __go_to_roi_tagname_given_text(self,_=None,given_text_id=None):
        self.__linked_text.goto_tagname_given_text(given_text_id)


    def __go_to_roi_parameter_given_text(self,parameter=None,given_text_id=None):
        self.__linked_text.goto_parameter_given_text(parameter,given_text_id)
        


    def __get_referenced_linked_text(self):
        selection = self.__parameter_entry.get()
        selection = selection.lower()
        self.__save_refType(selection)


    def __save_refType(self, selection):
        options = [ option.lower() for option in self.__autocomplete_list]
        parameter = self.__parameter
        if selection == '' or (selection not in options):
            self.__selected_option = None
            self.__linked_text.set_parameter_ref_type(parameter,None)
        else:
            self.__selected_option = self.__options[options.index(selection)]
            self.__linked_text.set_parameter_ref_type(parameter,self.__selected_option[1])
            
        




    def __get_linked_text(self):
        selection = self.__parameter_entry.get()
        print(selection)


    def __get_selector_text(self, selection):
        print(selection)


    def draw(self, x=0, y=0 ,width=None):
        self.__delete_elements()
        if width:
            self.__width = width
        else:
            width = self.__width
        if width is None and self.__width is None:
            width = 200

        x = self.__x + x 
        y = self.__y + y

        self.y = y

        tags=(self.__id)

        if (self.__linked_text.get_document_type() == Database.TABLE 
            or self.__document_type == Database.TABLE):
            height = self.__draw_table_linking_view(x, y)
        else:
            height = self.__draw_text_document_linking_view(x, y)
        self.__cell_height = height
        return height
    

    def cell_size(self):
        return self.__cell_height + 270
    

    def __set_linked_entry_table_text_selection(self):
        is_table_text = False
        if self.__document_type == Database.TABLE or self.__text_in_table:
            is_table_text = True

        self.__tagname_entry.seletection_is_table_text(is_table_text)
        self.__parameter_entry.seletection_is_table_text(is_table_text)
    
    
    def __draw_table_linking_view(self, x, y):
        if self.__config.get_show_advanced_linking():
            tagname_entry_height = self.__tagname_entry.draw(8, y+4)
            parameter_entry_height = self.__parameter_entry.draw(8, y+76 + tagname_entry_height)
        else:
            tagname_entry_height = 0
            parameter_entry_height = self.__parameter_entry.draw(8, y+4)
        self.__draw_linked_text()
        if self.__draw_done_button:
            self.__done_or_accept_button.draw(self.__canvas.winfo_width() - (30*3)
                                              ,y + 172 + tagname_entry_height + parameter_entry_height)
            
        return tagname_entry_height + parameter_entry_height
    

    def __draw_text_document_linking_view(self, x, y):
        
        if not self.__linked_text.has_given_text() and not self.__predicted_output:
            self.__text_link_button.draw(self.__canvas.winfo_width()/2 - 24,y + 100)
            return 0

        if self.__config.get_show_advanced_linking():
            tagname_entry_height = self.__tagname_entry.draw(8, y + 4)
            parameter_entry_height = self.__parameter_entry.draw(8, y + 76 + tagname_entry_height)
            spacing = 214
        else:
            tagname_entry_height = 0
            parameter_entry_height = self.__parameter_entry.draw(8, y + 4)
            spacing = 134
        self.__draw_linked_text()
        if self.__draw_done_button:
            self.__done_or_accept_button.draw(self.__canvas.winfo_width() - (30*3)
                                              ,y + spacing + tagname_entry_height + parameter_entry_height)
            
        return tagname_entry_height + parameter_entry_height
    
        
    def setup_regex_on_viewer(self):
        # Only show linked text regex matches for linked text that is being edited
        if self.__linked_text.get_id() is not None:
            self.__linked_text.highlight_linked_text_on_doc_viewer()
            
            
        else:
            if not self.__regex_refresh_parameter:
                    self.__linked_text.setup_tagname_regex_on_viewer()
            else:
                self.__linked_text.setup_parameter_regex_on_viewer(self.__regex_refresh_entry_name)


    def __draw_linked_text(self):
        tagname_linked_text = self.__linked_text.get_tagname_linked_text()
        if tagname_linked_text.links:
            for _, linked_text in tagname_linked_text.links.items():
                start = linked_text.target_text_indexes[0]
                end = linked_text.target_text_indexes[1]
                self.__tagname_entry.primary_link_text(start,end)


        parameter_linked_text = self.__linked_text.get_parameter_linked_text()
        if parameter_linked_text.links:
            for _, linked_text in parameter_linked_text.links.items():
                start = linked_text.target_text_indexes[0]
                end = linked_text.target_text_indexes[1]
                self.__parameter_entry.primary_link_text(start,end)
    

    def __delete_elements(self):
        self.__canvas.delete(self.__id)
        self.__tagname_entry.hide()
        self.__parameter_entry.hide()
        self.__done_or_accept_button.hide()
        self.__text_link_button.hide()
        self.__linked_text.remove_highlights_on_viewer()


    def hide(self):
        self.__delete_elements()




class string_linked_text_entry(linked_text_ignore_entry):
    def __init__(self, canvas: tk.Canvas, parameter=None, value=None, **kwargs) -> None:

        if 'autocompleteList' in kwargs:
            self._options = kwargs['autocompleteList']
        else:
            self._options = []

        super().__init__(canvas, 0, 0, **kwargs)

        default = ''
        if value:
            default = value 
        elif parameter is not None:
            default = parameter['DVal']
        
        self.entry.insert(0,default)


    def on_given_text_link(self, option=None):
        if option is None:
            given_text_str, text_view_id = super().on_given_text_link()
        else:
            given_text_str, text_view_id = super().on_given_text_link(option)
            self._options = [option]


        # 1. If no options, return
        if not self._options:
            return

        # 2. If exact match, use it
        if given_text_str in self._options:
            self.set_text(given_text_str)
            indexes = [0, len(given_text_str)]
            self.key_text_link_callback(True, indexes, self.entry.get(),self.name,False)
            return 
            
        # 3. Use Fuzzy matching to find the closest matching name
        tagname_regex_pattern = r'\b([A-Z0-9]{2,}[-_][A-Z0-9]{2,}[-_][A-Z0-9]{2,})\b|\b([A-Z0-9]{2,}[-_][A-Z0-9]{2,})\b'

        list_of_matches = re.finditer(tagname_regex_pattern, given_text_str, re.IGNORECASE)

        try:
            given_text_match = next(list_of_matches).group(0)
        except StopIteration:
            return
        
        given_text_match = re.sub(r'[^a-zA-Z0-9]', '', given_text_match)
        options_dict = {re.sub(r'[^a-zA-Z0-9]', '', option): option for option in self._options}

   
        target_option = process.extractOne(given_text_match, list(options_dict.keys()))
        
        if not target_option:
            return
        
        target_text = options_dict[target_option[0]]
        
        self.set_text(target_text)

        # Split given text by whitespace to find best matching part
        given_text_parts_dict = {i: part for i, part in enumerate(given_text_str.split())}

        # Find the best matching part in the given text
        matched_given_text_part = process.extractOne(target_text, given_text_parts_dict.values())
        if matched_given_text_part:
            start = given_text_str.index(matched_given_text_part[0])
            # For each alphanumeric sub-part in the matched given text part, find its position in the target text
            for sub_match in re.finditer(r'[a-zA-Z0-9]+', matched_given_text_part[0]):
                if sub_match.group(0).lower() not in target_text.lower():
                    continue
                sub_start, sub_end = sub_match.span()
                target_start = target_text.index(sub_match.group(0))
                target_indexes = (target_start, target_start + len(sub_match.group(0)))
                indexes = (start + sub_start, start + sub_end)
                self.key_text_link_callback(True, target_indexes, target_text,self.name,False
                                            ,text_view_indexes=(start + sub_start, start + sub_end, text_view_id))
    

        

class integer_linked_text_entry(linked_text_ignore_entry):
    def __init__(self, canvas: tk.Canvas, parameter, value, **kwargs) -> None:
        vcmd = (canvas.master.register(self.validate))
        super().__init__(canvas, 0, 0,validatecommand=(vcmd, '%P'), **kwargs)
        if value:
            default = value 
        else:
            default = parameter['DVal']
        self.entry.insert(0,default)


    def validate(self, P):
        if str.isdigit(P) or P == "":
            return True
        else:
            return False
        
    
    def on_given_text_link(self):
        given_text_str, _= super().on_given_text_link()
        if given_text_str and self.validate(given_text_str):
            self.set_text(given_text_str)
            indexes = [0, len(given_text_str)]
            self.key_text_link_callback(True, indexes, self.entry.get(),self.name,False)


class real_linked_text_entry(linked_text_ignore_entry):
    def __init__(self, canvas: tk.Canvas, parameter,value=None, **kwargs) -> None:
        vcmd = (canvas.master.register(self.validate))
        self.__min = float(parameter['Min'])
        self.__max = float(parameter['Max'])
        super().__init__(canvas, 0, 0,validatecommand=(vcmd, '%P'), **kwargs)
        if value:
            default = value 
        else:
            default = parameter['DVal']
        self.entry.insert(0,default)



    def validate(self, string):
        self.__min 
        regex = re.compile(r"[+-]?(\d+([.]\d*)?([eE][+-]?\d+)?|[.]\d+([eE][+-]?\d+)?)")
        try:
            result = regex.match(string)
            return (string == ""
                    or (string.count('+') <= 1
                        and string.count('-') <= 1
                        and string.count('.') <= 1
                        and result is not None
                        and result.group(0) != ""
                        and float(string) >= self.__min
                        and float(string) <= self.__max))
        except ValueError:
            return False
        

    def on_given_text_link(self):
        given_text_str, _ = super().on_given_text_link()
        if given_text_str and self.validate(given_text_str):
            self.set_text(given_text_str)
            indexes = [0, len(given_text_str)]
            self.key_text_link_callback(True, indexes, self.entry.get(),self.name,False)



class add_parameter_view():
    def __init__(self, canvas: tk.Canvas, x_offset=0, y_offset=0, cancel_callback=None
            , add_callback=None, options_list=["test1","test2","test3"],placeholder="Parameter Name" ) -> None:
        self.__canvas = canvas
        self.__x = x_offset
        self.__y = y_offset
        self.__cancel_callback = cancel_callback
        self.__add_callback = add_callback
        self.__custom_entry = custom_entry(self.__canvas, self.__x, self.__y
                                            , placeholder=placeholder
                                            , autocompleteList=options_list
                                            , edit_callback=self.__edit_callback
                                            , focus_out_callback=self.__entry_focus_out_callback)
        self.__options_list = options_list
        self.__add_text = None 
        self.__allow_adding_parameters = False

    def set_first_prediction(self, text):
        self.__custom_entry.set_text(text)
        self.__edit_callback(text)

    def __edit_callback(self, value):
        options_without_description = [option.split(' | ')[0] for option in self.__options_list]
        if value in self.__options_list or value in options_without_description:
            self.__allow_adding_parameters = True 
            self.__canvas.itemconfig(self.__add_text,fill="#505050")
        else:
            self.__allow_adding_parameters = False
            self.__canvas.itemconfig(self.__add_text,fill="#C0C0C0")


    def update_autocomplete(self,autocomplete_list):
        self.__options_list = autocomplete_list
        self.__custom_entry.update_autocomplete_list(autocomplete_list)


    def __entry_focus_out_callback(self):
        self.__custom_entry.entry.key_selection()

    
    def draw(self, x=0, y=0):
        self.hide()
        x = self.__x + x 
        y = self.__y + y

        self.__custom_entry.draw(x,y)
        self.__draw_cancel_button(self.__canvas.winfo_width() - 20,y + 56)
        self.__draw_add_button(self.__canvas.winfo_width() - 96, y + 56)

    
    def hide(self):
        if self.__add_text:
            self.__canvas.delete(self.__add_text)
            self.__canvas.delete(self.__add_rect)
            self.__canvas.delete(self.__cancel_text)
            self.__canvas.delete(self.__cancel_rect)
            self.__custom_entry.hide()


    def __draw_cancel_button(self, x, y):
        padding = 8
        x = self.__x + x # For static elements
        y = self.__y + y # For static elements
        
        self.__cancel_text = self.__canvas.create_text(x, y,  
                                                        text=' Cancel ', 
                                                        font=('Arial',10,'normal'), 
                                                        anchor=tk.NE, 
                                                        fill="#505050",
                                                        tags=('add_parameter_cancel'))
        
        bounds = self.__canvas.bbox(self.__cancel_text)
        self.__cancel_rect = self.__canvas.create_rectangle(bounds[0]-padding ,bounds[1] -padding,bounds[2]+ padding ,bounds[3]+ padding,fill='#F2F2F2', width = 0, tags=('add_parameter_cancel'))
        self.__canvas.tag_raise(self.__cancel_text)
        

        self.__canvas.tag_bind(self.__cancel_rect,'<Enter>', self.__on_cancel_enter)
        self.__canvas.tag_bind(self.__cancel_rect,'<Leave>', self.__on_cancel_leave)
        self.__canvas.tag_bind(self.__cancel_text,'<Enter>', self.__on_cancel_enter)
        self.__canvas.tag_bind(self.__cancel_text,'<Leave>', self.__on_cancel_leave)
        self.__canvas.tag_bind(self.__cancel_rect,'<Button-1>', self.__on_cancel_click)
        self.__canvas.tag_bind(self.__cancel_text,'<Button-1>', self.__on_cancel_click)


    def __draw_add_button(self, x, y):
        padding = 8
        x = self.__x + x # For static elements
        y = self.__y + y # For static elements
        
        if self.__allow_adding_parameters:
            self.__add_text = self.__canvas.create_text(x, y,  
                                                        text=' Add ', 
                                                        font=('Arial',10,'normal'), 
                                                        anchor=tk.NE, 
                                                        fill="#505050",
                                                        tags=('add_parameter'))
        else:
            self.__add_text = self.__canvas.create_text(x, y,  
                                                        text=' Add ', 
                                                        font=('Arial',10,'normal'), 
                                                        anchor=tk.NE, 
                                                        fill="#C0C0C0",
                                                        tags=('add_parameter'))
        
        bounds = self.__canvas.bbox(self.__add_text)
        self.__add_rect = self.__canvas.create_rectangle(bounds[0]-padding ,bounds[1] -padding,bounds[2]+ padding ,bounds[3]+ padding,fill='#F2F2F2', width = 0, tags=('add_parameter'))
        self.__canvas.tag_raise(self.__add_text)
        

        self.__canvas.tag_bind(self.__add_rect,'<Enter>', self.__on_add_enter)
        self.__canvas.tag_bind(self.__add_rect,'<Leave>', self.__on_add_leave)
        self.__canvas.tag_bind(self.__add_text,'<Enter>', self.__on_add_enter)
        self.__canvas.tag_bind(self.__add_text,'<Leave>', self.__on_add_leave)
        self.__canvas.tag_bind(self.__add_rect,'<Button-1>', self.__on_add_click)
        self.__canvas.tag_bind(self.__add_text,'<Button-1>', self.__on_add_click)


    def __on_add_enter(self,_):
        if self.__allow_adding_parameters:
            self.__canvas.itemconfig(self.__add_rect, fill='#E5E5E5')


    def __on_add_leave(self,_):
        self.__canvas.itemconfig(self.__add_rect, fill='#F3F3F3')


    def __on_add_click(self,_):
        if not self.__allow_adding_parameters:
            return 

        if self.__add_callback:
            self.__add_callback(self.__custom_entry.entry.get())


    def __on_cancel_enter(self,_):
        self.__canvas.itemconfig(self.__cancel_rect, fill='#E5E5E5')


    def __on_cancel_leave(self,_):
        self.__canvas.itemconfig(self.__cancel_rect, fill='#F3F3F3')

    def __on_cancel_click(self,_):
        if self.__cancel_callback:
            self.__cancel_callback()

    def clear_entry(self):
        self.__custom_entry.entry.delete(0, 'end')




if __name__ == "__main__":

    root = tk.Tk()
    canvas = tk.Canvas(root, bg="white", height=800, width=300)

    b = parameter_list_view(canvas,selected_parameter_dict={"Cfg_Hi":True,"Cfg_HiHi":True,"Cfg_LoLo":True},
                                full_paramater_dict=["Cfg_Hi","Cfg_HiHi","test_1","test_2","test_3","test_4","test_5","test_6"])

    def draw(_):
        b.draw(width=canvas.winfo_width())

    canvas.bind('<Configure>',draw)


    canvas.pack()
    root.mainloop()
