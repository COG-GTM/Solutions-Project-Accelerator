import logging
from os import link
from re import X
import re
import threading
import tkinter as tk
from tkinter import font
from tkinter import messagebox
from typing import Dict
from uuid import uuid4
from PIL import Image, ImageDraw, ImageTk
from bin.gui_elements import custom_label
from bin.gui_horizontal_scrolling_selector import horizontal_scrolling_selector

from bin.gui_base64_icons import empty_image
from bin.logic_acm_data_handler import ACM_Data_Handler
from bin.logic_acm_libraries_retrieval import get_library_file_path
from bin.logic_acm_library_parser import acm_library_parser, get_object_NIBS
from bin.logic_internal_database import Database
from bin.gui_libary_rules_view import acm_libraries_retrieval


try:
    from bin.gui_elements import custom_entry
except:
    from gui_elements import custom_entry


class libary_prompt_context_view:
    def __init__(self, name, library_id, description='Library Prompt Context', go_to_callback=None):
        self.__name = name
        self.__library_id = library_id
        self.__description = description
        self.__go_to_callback = go_to_callback
        self.__prompt_context_views = {}
        self.__prompt_context_dict = {}
        self.core_type = ''
        self.catalog_number = ''

    def setup_view(self, canvas:tk.Canvas, x,y, project_name,acm_data_handler:ACM_Data_Handler,db:Database):
        """ Setup the view of the library rules """
        self.__canvas = canvas
        self.__x = x
        self.__y = y
        self.__project_name = project_name
        
        self.__screen_label = custom_label(self.__canvas, 8, 0, text=self.__name,fill= '#505050',size=16,weight="bold")
        self.__description_label = custom_label(self.__canvas,8, 24, text=self.__description, fill= '#505050',size=11,weight="bold")
        self.__parse_library_file(project_name,acm_data_handler)
        self.__acm_data_handler = acm_data_handler
        self.__db = db
        self.__prompt_context_list = ['Parameters','References']
        self.__selected_list_view = 0 
        if len(self.__prompt_context_list) == 0:
            return
        
        self.__horizontal_scrolling_selector  = horizontal_scrolling_selector(self.__canvas
                                                    ,self.__prompt_context_list
                                                    ,callback=self.__horizontal_selector_callback
                                                    ,selected=self.__prompt_context_list[self.__selected_list_view])
        
        if not self.core_type and not self.catalog_number:
            library_df = self.__acm_data_handler.get_registered_library(self.__library_id)
            self.core_type = library_df['CoreType'].values[0]
            self.catalog_number = library_df['CatalogNumber'].values[0]

        self.__prompt_context_dict = self.__db.get_llm_library_prompts(self.__library_id, self.core_type, self.catalog_number)

        self.__create_prompt_list_views(self.__prompt_context_list)


    def __create_prompt_list_views(self, prompt_context_types):
        self.__prompt_context_views={}

        self.__parse_library_file(self.__project_name,self.__acm_data_handler)
        

        for prompt_context_type in prompt_context_types:

            if prompt_context_type == 'Parameters':
                full_interfaces_dict = self.__library_parser.get_parameters()
            
            if prompt_context_type == 'References':
                full_interfaces_dict = get_object_NIBS(self.__library_file_path)
            list_view = prompt_context_list_view(self.__canvas
                                                        ,self.__acm_data_handler
                                                        ,self.__library_id
                                                        ,self.__project_name
                                                        ,self.__x + 8, self.__y + 96
                                                        ,selected_interface_dict=self.__prompt_context_dict.get(prompt_context_type, {})
                                                        ,full_references_dict=full_interfaces_dict
                                                        ,save_callback=self.save)

            self.__prompt_context_views[prompt_context_type] = list_view 

        


    def draw(self, x=0, y=0):
        if '<Configure>' not in self.__canvas.bind():
            return
        self.__delete_static_elements()
        self.__screen_label.draw(0,0)
        self.__description_label.draw(0,0)
        
        '''self.__description_label = self.__canvas.create_text(self.__x + 24,self.__y + y + 48, text=self.__description, anchor=tk.NW, fill="#6F6F6F")
        description_bounds = self.__canvas.bbox(self.__description_label) 
        if (description_bounds[2] - description_bounds[0]) > (self.__canvas.winfo_width() - 48) and self.__canvas.winfo_width() > 0:
            self.__description_label = self.fit_text_in_mutiline(self.__description_label, self.__x + 24, self.__y + y + 22, self.__description)
        '''
        if len(self.__prompt_context_list) == 0:
            self.__draw_empty_indicator()
            return

        self.__horizontal_scrolling_selector.draw(0,64)
        view = self.__prompt_context_list[self.__selected_list_view]
        self.__prompt_context_views[view].draw(width=self.__canvas.winfo_width()-16)
        self.__canvas.config(scrollregion=(0,0,self.__canvas.bbox(tk.ALL)[2],self.__canvas.bbox(tk.ALL)[3]+100))

    
    def __delete_static_elements(self):
        if self.__description_label:
            self.__canvas.delete(self.__description_label)


    def __parse_library_file(self, project_name,acm_data_handler:ACM_Data_Handler):
        self.__library_file_path = get_library_file_path(self.__library_id,project_name)
        if not self.__library_file_path:
            projects_df = acm_data_handler.get_all_projects()
            acm_project_name = projects_df.loc[int(acm_data_handler.get_project_id())]['Name']
            acm_libraries_retrieval(project_name, acm_project_name,threaded=False)
            self.__library_file_path = get_library_file_path(self.__library_id,project_name)
            if not self.__library_file_path:
                raise Exception(f"Unable to access interfaces of {self.__name}.")
        self.__library_parser = acm_library_parser(self.__library_file_path)


    def __horizontal_selector_callback(self, event):
        view = self.__prompt_context_list[self.__selected_list_view]
        self.__prompt_context_views[view].hide()
        
        self.__selected_list_view= int(event[1])
        self.draw()


    def __draw_empty_indicator(self):
        if self.__empty_image_id:
            self.__canvas.delete(self.__empty_image_id)
            self.__canvas.delete(self.empty_title_id)
            self.__canvas.delete(self.empty_text_id)
        
        self.empty_image = tk.PhotoImage(data=empty_image)
        self.__empty_image_id = self.__canvas.create_image(int(self.__canvas.winfo_width()/2), 
                                        int(self.__canvas.winfo_height()/3), 
                                        image = self.empty_image, 
                                        anchor = tk.CENTER
                                    )
        title_font = font.Font(family="arial.ttf",size=11,weight="bold")
        self.empty_title_id = self.__canvas.create_text(int(self.__canvas.winfo_width()/2),
                                    int(self.__canvas.winfo_height()/3 + self.empty_image.height()/2 + 8),
                                    text='No Subobjects', anchor=tk.CENTER, fill="#A0A0A0",font=title_font,
                                    justify=tk.CENTER)
        message_font = font.Font(family="arial.ttf",size=9,weight="normal")
        self.empty_text_id = self.__canvas.create_text(int(self.__canvas.winfo_width()/2),
                                    int(self.__canvas.winfo_height()/3 + self.empty_image.height()/2 + 24),
                                    text='ACM Library has no subobjects.', anchor=tk.CENTER, fill="#A0A0A0",font=message_font,
                                    justify=tk.CENTER)
        
    
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
    
    def save(self):
        logging.info(f"Saving library prompt context view for {self.__name}")
        data = {}

        for prompt_context_type, list_view in self.__prompt_context_views.items():
            data[prompt_context_type] = list_view.get_data()

        
        self.__db.save_llm_library_prompts(self.__library_id, self.core_type, self.catalog_number, data)



class prompt_context_list_view():
    def __init__(self, canvas:tk.Canvas,acm_data_handler: ACM_Data_Handler,library_id,project_name,x=0,y=0, selected_interface_dict={}, full_references_dict=None
                        , tagname='', redraw_callback=None, go_to_callback=None, db:Database=None, save_callback=None) -> None:
        self.__canvas = canvas 
        self.__object_id = None
        self.__library_id = library_id
        self.__acm_data_handler = acm_data_handler
        self.__db = db
        self.__project_name = project_name
        self.__redraw_callback = redraw_callback
        self.__go_to_callback = go_to_callback
        self.__save_callback = save_callback
        self.__tagname = tagname
        self.__selected_interface_dict = selected_interface_dict
        self.__id = uuid4()
        down_arrow = Image.new('RGBA', (15, 15), '#00000000')
        draw = ImageDraw.Draw(down_arrow)
        draw.line([(0, 4), (7, 11), (14, 4) ], fill=(220,220,220,255),width=2)
        up_arrow = down_arrow.rotate(180)
        self.__down_arrow = ImageTk.PhotoImage(down_arrow)
        self.__up_arrow = ImageTk.PhotoImage(up_arrow)
        self.__opened_interface = ''
        self.__interface_cells:Dict[str:interface_cell] = {}
        self.__create_interface_cells()
        self.__x = x
        self.__y = y
        self.__width = None
        self.__header_font = font.Font(family="Helvetica",size=11,weight="normal")
        self.__allow_adding_locations = True
        self.__show_add_interface = True
        self.__add_text = None
        if full_references_dict is not None:
            self.__full_references_dict = full_references_dict
        else:
            self.__full_references_dict = {}
        self.__add_interface_view = add_interface_view(self.__canvas, cancel_callback=self.__cancel_add_interface,add_callback=self.__add_interface)
        self.__update_autocomplete_entry()
   
        self.__data_loaded = False


    def __parse_library_file(self, project_name,acm_data_handler:ACM_Data_Handler):
        library_file_path = get_library_file_path(self.__library_id,project_name)
        if not library_file_path:
            projects_df = acm_data_handler.get_all_projects()
            acm_project_name = projects_df.loc[int(acm_data_handler.get_project_id())]['Name']
            acm_libraries_retrieval(project_name, acm_project_name,threaded=False)
            library_file_path = get_library_file_path(self.__library_id,project_name)
            if not library_file_path:
                raise Exception(f"Unable to access interfaces of {self.__name}.")
        self.__library_parser = acm_library_parser(library_file_path)
        


    def __update_autocomplete_entry(self):
        autocomplete_list = []
        for interface, data in self.__full_references_dict.items():


            if 'ROnly' in data and data['ROnly'] == 'true':
                continue 
            
            if 'RType' in data and data['RType'] != 'Immediate' and data['RType'] != 'Reference': 
                continue 

            if interface not in self.__interface_cells:
                description = data['ParH'] if 'ParH' in data else data['Description']
                autocomplete_list.append(interface + ' | ' + description)

        self.__add_interface_view.update_autocomplete(autocomplete_list)


    def __create_interface_cells(self):
        
        for interface, data in self.__selected_interface_dict.items():
            self.__interface_cells[interface] = interface_cell(self.__canvas,self.__acm_data_handler,self.__object_id
                                                ,data['value'],self.__project_name,tagname=self.__tagname
                                                , goto_callback=self.__go_to_callback
                                                ,redraw_callback=self.__redraw_callback
                                                ,save_callback=self.__save_callback)
            



    def __cell_size(self):
        return 100
        

    def show_linked_text(self, linked_text):
        interfaces = linked_text['interfaces'].keys()

        if interfaces:
            self.__opened_interface = list(interfaces)[0]
            self.draw()


    def draw(self,x=0,y=0,width=None):
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
            #self.__get_all_linked_text_interfaces()
            

        
        for interface, _ in self.__selected_interface_dict.items():

            self.__interface_cells[interface].hide()

            if interface != self.__opened_interface:
                image = self.__down_arrow
                increase = 55
                func = self.__open_interface
                draw_interface = False 
            else:
                image = self.__up_arrow
                increase = self.__cell_size()
                func = self.__close_interface
                draw_interface = True

            tags=(self.__id,interface,count)
            rect = self.__canvas.create_rectangle(x,y,x+width,y+55,fill='',outline='',tags=tags)
            name = interface.split(' | ')[0]

            text = self.__canvas.create_text(x+16,y+21,anchor=tk.NW,text=name,tags=tags,fill='#606060',font=self.__header_font)
            
            divider = self.__canvas.create_line(int(self.__canvas.winfo_width()/2), y + 14, int(self.__canvas.winfo_width()/2), y + 38, fill='#D5D5D5', width=2, tags=tags)
            description = interface.split(' | ')[-1]
            description_label = self.__canvas.create_text(int(self.__canvas.winfo_width()/2)+4,y + 18, text=description, anchor=tk.NW, tags=tags, fill="#6F6F6F")
            description_label = self.fit_description_in_mutiline(description_label,description,tags,y)
            icon = self.__canvas.create_image(x + width-16,y+28,image=image,tags=tags)
            if draw_interface:
                cell_height = self.__interface_cells[interface].draw(x,y + 50, self.__canvas.winfo_width())
                increase = increase + cell_height + 30
            self.__canvas.create_line(x+8,y+increase,x+width-8,y+increase,width=1,fill='#D5D5D5',tags=tags)
            self.__canvas.tag_bind(rect,'<Button-1>',func)
            self.__canvas.tag_bind(text,'<Button-1>',func)
            self.__canvas.tag_bind(icon,'<Button-1>',func)
            self.__canvas.tag_bind(divider,'<Button-1>',func)
            self.__canvas.tag_bind(description_label,'<Button-1>',func)

            y = increase + y 

        if not self.__show_add_interface:
            self.__draw_add_button(x + 16, y + 24)
        else:
            self.__delete_add_interface()
            self.show_add_interface_interface(x + 4, y + 24)

        self.__canvas.config(scrollregion=(0,0,self.__canvas.bbox(tk.ALL)[2],self.__canvas.bbox(tk.ALL)[3]+100))



    def __draw_add_button(self, x, y):
        padding = 8
        self.__delete_elements()
        
        x = self.__x + x # For static elements
        y = self.__y + y + padding # For static elements
        
        if self.__allow_adding_locations:
            self.__add_text = self.__canvas.create_text(x, y,  
                                                                text='+ Add interface ', 
                                                                font=('Arial',10,'normal'), 
                                                                anchor=tk.NW, 
                                                                fill="#505050")
        else:
            self.__add_text = self.__canvas.create_text(x, y,  
                                                                text='+ Add interface ', 
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
        if self.__add_interface_view:
            self.__add_interface_view.hide()


    def __delete_add_interface(self):
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
        
        self.__show_add_interface = True 
        self.__add_interface_view.clear_entry()
        self.draw()

    
    def show_add_interface_interface(self, x, y):
        
        self.__add_interface_view.draw(x,y)


    def __cancel_add_interface(self):
        if self.__add_interface_view:
            self.__add_interface_view.hide()
        self.__show_add_interface = False
        self.draw()


    def __add_interface(self, interface):
        interface_name = interface.split(' | ')[0]

        data = {
            'properties': self.__full_references_dict[interface_name],
            'value': ''
        }

        if ("properties" in data and 'Filter' in data['properties'] 
            and data['properties']['Filter'] == "Library.LibraryType='HMI' And Library.Category='Display'"):
            messagebox.showwarning("Display paramter linking not allowed", "Cannot link to a display interface. Display interfaces are linked through visual type documents.")
            return

        
        self.__selected_interface_dict[interface_name] = data
        self.__interface_cells[interface_name] = interface_cell(self.__canvas,self.__acm_data_handler,self.__object_id,data['value'],self.__project_name
                            ,tagname=self.__tagname,redraw_callback=self.__redraw_callback,goto_callback=self.__go_to_callback,db=self.__db,save_callback=self.__save_callback)
        
        self.__update_autocomplete_entry()
        if self.__add_interface_view:
            self.__add_interface_view.hide()
        self.__show_add_interface = False
        self.__opened_interface = ''
        self.draw()


    def __open_interface(self, event):
        curX, curY = ( self.__canvas.canvasx(event.x),  self.__canvas.canvasy(event.y))
        id = self.__canvas.find_closest(curX,curY)
        tags = self.__canvas.gettags(id)
        self.__opened_interface = tags[1]
        self.draw()

    def __close_interface(self, event):
        curX, curY = ( self.__canvas.canvasx(event.x),  self.__canvas.canvasy(event.y))
        id = self.__canvas.find_closest(curX,curY)
        tags = self.__canvas.gettags(id)
        if tags[1] == self.__opened_interface:
            self.__opened_interface = ''
        
        self.draw()


    def ignore_text(self, regex_string, ignore_indexes):
        for _, interface_cell in self.__interface_cells.items():
            interface_cell.ignore_text( regex_string, ignore_indexes)


    def hide(self):
        self.__delete_list()
        self.__delete_elements()


    def __delete_list(self):
        self.__canvas.delete(self.__id)

        for _, interface_cell in self.__interface_cells.items():
            interface_cell.hide()


    def fit_description_in_mutiline(self, description_label, description, tags,y):

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
        
    def get_data(self):
        data = {}

        
        for interface, interface_cell in self.__interface_cells.items():
            interface_name = interface.split(' | ')[0]
            data[interface_name] = {
                'properties': self.__full_references_dict[interface_name],
                'value': interface_cell.get_text_content()
                }

        return data

class interface_cell():

    
    
    def __init__(self,  canvas:tk.Canvas,acm_data_handler: ACM_Data_Handler,object_id,prompt,project_name,x=0,y=0, tagname=''
                    ,redraw_callback=None,goto_callback=None, db:Database=None, save_callback=None) -> None:
        self.__canvas = canvas

        self.__x = x
        self.__y = y 
        self.__width = None 
        self.__save_callback = save_callback
        self.__cell_height = 0
        self.__interface_prompt = prompt
        self.__id = uuid4()
        self.__text_widget = None
        self.__text_widget_window = None
        self.__setup_views()




    def __goto_roi(self, roi, page_number, path, doc_type):    
        if self.__goto_callback_func:
            self.__goto_callback_func(roi,page_number,path,doc_type)
            


    
    def __setup_views(self):

        pass



    def setup_viewer(self):

        pass

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

        text_font = font.Font(family="Arial", size=10, weight="normal")

        text_width = int((width-32)/text_font.measure("0"))

        if not self.__text_widget:
            # Create a Text widget inside the interface cell
            self.__text_widget = tk.Text(self.__canvas, height=4, width=text_width, wrap=tk.WORD, 
                                font=text_font, bg='white', fg='#6F6F6F',
                                relief=tk.FLAT, highlightthickness=1,highlightbackground="lightgray",
                                highlightcolor="lightgray")
            self.__text_widget.insert(tk.END, self.__interface_prompt)
            self.__text_widget.bind('<FocusOut>', self.__on_text_focus_out)
        else:
            self.__text_widget.config(width=text_width)

        # Create a window on the canvas to hold the Text widget
        self.__text_widget_window = self.__canvas.create_window(x + 10, y + 10, anchor=tk.NW, 
                                                 window=self.__text_widget, tags=tags)
        
        # Set the cell height to accommodate the text widget
        self.__cell_height = self.__text_widget.winfo_reqheight()
        return self.__cell_height
    

    def __on_text_focus_out(self, _):
        if self.__save_callback:
            self.__save_callback()
    

    def cell_size(self):
        return self.__text_widget.winfo_reqheight()
    





    def __delete_elements(self):
        # Clean up the text widget if it exists
        if self.__text_widget_window:
            self.__canvas.delete(self.__text_widget_window)
            # Remove focus
            self.__canvas.focus_set()
        self.__canvas.delete(self.__id)


    def hide(self):
        self.__delete_elements()
    
    def get_text_content(self):
        """Get the content of the text widget"""
        if self.__text_widget:
            return self.__text_widget.get('1.0', tk.END).strip()
        return ""
    
    def set_text_content(self, text):
        """Set the content of the text widget"""
        if self.__text_widget:
            self.__text_widget.delete('1.0', tk.END)
            self.__text_widget.insert('1.0', text)





class add_interface_view():
    def __init__(self, canvas: tk.Canvas, x_offset=0, y_offset=0, cancel_callback=None
            , add_callback=None, options_list=["test1","test2","test3"],placeholder="Interface Name" ) -> None:
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
        self.__allow_adding_interfaces = False

    def __edit_callback(self, value):
        if value in self.__options_list:
            self.__allow_adding_interfaces = True 
            self.__canvas.itemconfig(self.__add_text,fill="#505050")
        else:
            self.__allow_adding_interfaces = False
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
                                                        tags=('add_interface_cancel'))
        
        bounds = self.__canvas.bbox(self.__cancel_text)
        self.__cancel_rect = self.__canvas.create_rectangle(bounds[0]-padding ,bounds[1] -padding,bounds[2]+ padding ,bounds[3]+ padding,fill='#F2F2F2', width = 0, tags=('add_interface_cancel'))
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
        
        if self.__allow_adding_interfaces:
            self.__add_text = self.__canvas.create_text(x, y,  
                                                        text=' Add ', 
                                                        font=('Arial',10,'normal'), 
                                                        anchor=tk.NE, 
                                                        fill="#505050",
                                                        tags=('add_interface'))
        else:
            self.__add_text = self.__canvas.create_text(x, y,  
                                                        text=' Add ', 
                                                        font=('Arial',10,'normal'), 
                                                        anchor=tk.NE, 
                                                        fill="#C0C0C0",
                                                        tags=('add_interface'))
        
        bounds = self.__canvas.bbox(self.__add_text)
        self.__add_rect = self.__canvas.create_rectangle(bounds[0]-padding ,bounds[1] -padding,bounds[2]+ padding ,bounds[3]+ padding,fill='#F2F2F2', width = 0, tags=('add_interface'))
        self.__canvas.tag_raise(self.__add_text)
        

        self.__canvas.tag_bind(self.__add_rect,'<Enter>', self.__on_add_enter)
        self.__canvas.tag_bind(self.__add_rect,'<Leave>', self.__on_add_leave)
        self.__canvas.tag_bind(self.__add_text,'<Enter>', self.__on_add_enter)
        self.__canvas.tag_bind(self.__add_text,'<Leave>', self.__on_add_leave)
        self.__canvas.tag_bind(self.__add_rect,'<Button-1>', self.__on_add_click)
        self.__canvas.tag_bind(self.__add_text,'<Button-1>', self.__on_add_click)


    def __on_add_enter(self,_):
        if self.__allow_adding_interfaces:
            self.__canvas.itemconfig(self.__add_rect, fill='#E5E5E5')


    def __on_add_leave(self,_):
        self.__canvas.itemconfig(self.__add_rect, fill='#F3F3F3')


    def __on_add_click(self,_):
        if not self.__allow_adding_interfaces:
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

    acm_data_handler = ACM_Data_Handler(r'DRIVER={ODBC Driver 18 for SQL Server};SERVER=1TV0VV3\SQLACM;DATABASE=ACM;Trusted_Connection=yes;TrustServerCertificate=yes;')
    acm_data_handler.set_project_id("6044")
    project_name = "Video_Demo_1"
    internal_db = Database(project_name)


    b = prompt_context_list_view(canvas,acm_data_handler,"47529A66-10E1-4F53-89E3-9E307C489D13",project_name,selected_interface_dict={},
                                full_paramater_dict={"Cfg_Hi":'',"Cfg_HiHi":'',"Cfg_LoLo":'',"test_1":'',"test_2":'',"test_3":'',"test_4":'',"test_5":'',"test_6":''})

    def draw(_):
        b.draw(width=canvas.winfo_width())

    canvas.bind('<Configure>',draw)


    canvas.pack()
    root.mainloop()
