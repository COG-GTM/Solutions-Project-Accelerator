import logging
import tkinter as tk
from tkinter import font
import tkinter as tk
from typing import List



from bin.gui_base64_icons import goto_dark_gray_20
from bin.gui_elements import custom_label
from bin.gui_base64_icons import empty_image
from bin.gui_elements import custom_label
from bin.gui_horizontal_scrolling_selector import horizontal_scrolling_selector
from bin.gui_parameter_list_view import parameter_list_view
from bin.gui_subobject_parameter_list_view import subobject_parameter_list_view
from bin.logic_acm_data_handler import ACM_Data_Handler
from bin.logic_acm_libraries_retrieval import acm_libraries_retrieval, get_library_file_path
from bin.logic_acm_library_parser import acm_library_parser
from bin.logic_internal_database import Database

class libary_rules_view:
    def __init__(self, name, library_id, description='Library Rules', go_to_callback=None):
        self.__name = name
        self.__library_id = library_id
        self.__description = description
        self.__go_to_callback_func = go_to_callback
        self.__parameter_list_view = None 
        self.__rules_list_views = []

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
        self.__subobjects = self.__library_parser.get_all_subobjects()
        self.__rules_list = ['Parameters'] + list(self.__subobjects.keys())
        self.__selected_subobject = 0 
        if len(self.__rules_list) == 0:
            return
        
        self.__horizontal_scrolling_selector  = horizontal_scrolling_selector(self.__canvas
                                                    ,self.__rules_list
                                                    ,callback=self.__horizontal_selector_callback
                                                    ,selected=self.__rules_list[self.__selected_subobject])
        
        self.__create_rules_list_views(self.__rules_list)


    def __create_rules_list_views(self, subobject_list):
        self.__rules_list_views=[]

        self.__parameter_list_view = parameter_list_view(self.__canvas
                                ,self.__acm_data_handler
                                ,None
                                ,self.__project_name
                                ,8,96
                                ,selected_parameter_dict={}
                                ,full_paramater_dict=self.__library_parser.get_parameters()
                                ,tagname=""
                                ,library_id=self.__library_id
                                ,redraw_callback=self.draw
                                ,go_to_callback=self.__go_to_callback
                                ,db=self.__db)
        
        self.__rules_list_views.append(self.__parameter_list_view)

        for subobject_type in subobject_list[1:]:

            subobject_parameters = self.__library_parser.get_subobject_parameters(subobject_type)

            list_view = subobject_parameter_list_view(self.__canvas
                                                        ,None
                                                        ,self.__acm_data_handler
                                                        ,self.__db
                                                        ,self.__project_name
                                                        ,16,96
                                                        ,selected_subobject_dict={}
                                                        ,subobject=self.__subobjects[subobject_type]
                                                        ,subobject_parameters=subobject_parameters
                                                        ,tagname=self.__name
                                                        ,subobject_type=subobject_type
                                                        ,create_subobject_callback=None
                                                        ,go_to_callback=self.__go_to_callback
                                                        ,redraw_callback=self.draw
                                                        ,save_reference_id_callback=None)

            self.__rules_list_views.append(list_view)

        


    def draw(self, x=0, y=0):
        #if '<Configure>' not in self.__canvas.bind():
        #        return
        self.__delete_static_elements()
        self.__screen_label.draw(0,0)
        self.__description_label.draw(0,0)
        
        '''self.__description_label = self.__canvas.create_text(self.__x + 24,self.__y + y + 48, text=self.__description, anchor=tk.NW, fill="#6F6F6F")
        description_bounds = self.__canvas.bbox(self.__description_label) 
        if (description_bounds[2] - description_bounds[0]) > (self.__canvas.winfo_width() - 48) and self.__canvas.winfo_width() > 0:
            self.__description_label = self.fit_text_in_mutiline(self.__description_label, self.__x + 24, self.__y + y + 22, self.__description)
        '''
        if len(self.__rules_list) == 0:
            self.__draw_empty_indicator()
            return

        self.__horizontal_scrolling_selector.draw(0,64)
        self.__rules_list_views[self.__selected_subobject].draw(width=self.__canvas.winfo_width()-16)
        self.__canvas.config(scrollregion=(0,0,self.__canvas.bbox(tk.ALL)[2],self.__canvas.bbox(tk.ALL)[3]+100))

    
    def __go_to_callback(self, *args, **kwargs):


        # TODO: show detailed view of all the parameters and subobjects 
        # that have been set using this rule


        if self.__go_to_callback_func:
            self.__go_to_callback_func(*args, **kwargs)

    
    def __delete_static_elements(self):
        if self.__description_label:
            self.__canvas.delete(self.__description_label)


    def __parse_library_file(self, project_name,acm_data_handler:ACM_Data_Handler):
        library_file_path = get_library_file_path(self.__library_id,project_name)
        if not library_file_path:
            projects_df = acm_data_handler.get_all_projects()
            acm_project_name = projects_df.loc[int(acm_data_handler.get_project_id())]['Name']
            acm_libraries_retrieval(project_name, acm_project_name,threaded=False)
            library_file_path = get_library_file_path(self.__library_id,project_name)
            if not library_file_path:
                raise Exception(f"Unable to access parameters of {self.__name}.")
        self.__library_parser = acm_library_parser(library_file_path)


    def __horizontal_selector_callback(self, event):
        self.__rules_list_views[self.__selected_subobject].hide()
        
        self.__selected_subobject= int(event[1])
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
        logging.info(f"Saving library rules view for {self.__name}")
    

class match_view():
    def __init__(self, canvas: tk.Canvas, x_offset, y_offset,index, match_name, pno, roi_name,
            select_callback=None, goto_callback=None) -> None:
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.__index = index
        self.__canvas = canvas
        self.__pno = pno
        self.__roi_name = roi_name
        self.__match_name = match_name
        self.__text_location_label = None 
        self.__select_callback = select_callback
        self.__selected = False
        self.__goto_callback_func = goto_callback
        self.__unhighlighted_color = '#FFFFFF'
        self.__goto_image = tk.PhotoImage(data=goto_dark_gray_20)

   
    def goto_callback(self):
        if self.__goto_callback_func:
            self.__goto_callback_func(self.__match_name)

    def draw(self, x=0, y=0):
        self.__delete_static_elements()
        

        self.x = self.x_offset + x # For static elements
        self.y = self.y_offset + y # For static elements
        self.__rect = self.__canvas.create_rectangle(self.x ,self.y - 2 ,self.__canvas.winfo_width() ,self.y + 28 ,fill='#FFFFFF', width = 0, tags=('add_text_location'))
        self.__text_location_label = self.__canvas.create_text(self.x + 8, self.y + 4,  
                                                                text=self.__match_name, 
                                                                font=('Arial',10,'normal'), 
                                                                anchor=tk.NW, 
                                                                fill="#707070")
       
        self.__canvas.tag_bind(self.__rect,'<Enter>', self.__on_enter)
        self.__canvas.tag_bind(self.__rect,'<Leave>', self.__on_leave)
        self.__canvas.tag_bind(self.__text_location_label,'<Enter>', self.__on_enter)
        self.__canvas.tag_bind(self.__text_location_label,'<Leave>', self.__on_leave)
        self.__canvas.tag_bind(self.__rect,'<Button-1>', self.__on_click)
        self.__canvas.tag_bind(self.__text_location_label,'<Button-1>', self.__on_click)
        self.__draw_goto_button()
    
    def __on_enter(self,_):
        self.__canvas.itemconfig(self.__rect, fill='#E5E5E5')


    def __on_leave(self,_):
        if not self.__selected:
            self.__canvas.itemconfig(self.__rect, fill='#FFFFFF')

    def __on_click(self,_):
        if self.__select_callback:
            self.__select_callback(self.__index,self.__match_name,self.__pno,self.__roi_name)

    def hide(self):
        self.__delete_static_elements()

    def __delete_static_elements(self):
        if self.__text_location_label:
            self.__canvas.delete(self.__text_location_label)
            self.__canvas.delete(self.__goto_rect)
            self.__canvas.delete(self.__goto_icon)
            self.__canvas.delete(self.__rect)

    def select(self):
        self.__selected = True
        self.__canvas.itemconfig(self.__rect, fill='#E5E5E5')

    def unselect(self):
        self.__selected = False
        self.__canvas.itemconfig(self.__rect, fill='#FFFFFF')


    def __draw_goto_button(self):
        self.__goto_rect = self.__canvas.create_rectangle(self.__canvas.winfo_width() - 32 ,self.y ,self.__canvas.winfo_width() - 8,self.y+24,fill=self.__unhighlighted_color, width = 0, tags=('goto_button'))
        
        
        self.__goto_icon = self.__canvas.create_image( self.__canvas.winfo_width() - 30,self.y  + 2 , image=self.__goto_image, anchor=tk.NW, tags=('goto_button'))
        
        self.__canvas.tag_bind(self.__goto_rect,'<Enter>', self.__on_goto_enter)
        self.__canvas.tag_bind(self.__goto_rect,'<Leave>', self.__on_goto_leave)
        self.__canvas.tag_bind(self.__goto_icon,'<Enter>', self.__on_goto_enter)
        self.__canvas.tag_bind(self.__goto_icon,'<Leave>', self.__on_goto_leave)
        self.__canvas.tag_bind(self.__goto_rect,'<Button-1>', self.__on_goto_click)
        self.__canvas.tag_bind(self.__goto_icon,'<Button-1>', self.__on_goto_click)

    def __on_goto_enter(self,_):
        self.__canvas.itemconfig(self.__goto_rect, fill='#E5E5E5')


    def __on_goto_leave(self,_):
        self.__canvas.itemconfig(self.__goto_rect, fill=self.__unhighlighted_color)


    def __on_goto_click(self,_):
        if self.__goto_callback_func:
            self.__goto_callback_func(self.__pno, self.__roi_name)


class matches_list_view():

    
    def __init__(self, canvas: tk.Canvas, path,  x_offset=0, y_offset=0) -> None:
        self.__path = path
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.__canvas = canvas
        self.__matches_links: List[match_view] = []
        self.__matches_label = None
        self.__goto_callback_func = None
        self.__matches_label = custom_label(self.__canvas, 0, 0, text="Rule Matches", fill= '#505050',size=16,weight="bold")
        self.__description_label = None
        self.__empty_label = None


    def subscribe_to_goto(self, callback):
        self.__goto_callback_func = callback

    def redraw(self, _):
        self.draw()

    def draw(self, x=12, y=0):
        self.__delete_static_elements()


        self.x = self.x_offset + x # For static elements
        self.y = self.y_offset + y # For static elements
        self.__matches_label.draw()
        self.__description_label = self.__canvas.create_text(self.x +4,self.y + 26, text='Page links found in other pages.', anchor=tk.NW, fill="#6F6F6F")
        match_y_offset = 48 + y
        for match in self.__matches_links:
            match.draw(x,match_y_offset)
            match_y_offset = match_y_offset + 30 


        if len(self.__matches_links) == 0:
            self.__empty_label = self.__canvas.create_text(self.__canvas.winfo_width()/2 - self.x - 4,self.y + 56, text='No matches found.', anchor=tk.CENTER, fill="#6F6F6F")

        self.__canvas.config(scrollregion=(0,0,self.__canvas.bbox(tk.ALL)[2],self.__canvas.bbox(tk.ALL)[3]))
        return match_y_offset - y



    def add_match_link(self, page_number: int, roi_name: str):

        name = 'Page '+str(page_number + 1)
        view = match_view(self.__canvas, 
                                self.x_offset, 
                                self.y_offset, 
                                len(self.__matches_links),
                                name,
                                page_number,
                                roi_name,
                                self.__select_callback,
                                goto_callback=self.__goto_callback)
        self.__matches_links.append(view)
        self.__redraw()

    

    def __redraw(self): # TODO: Make more elegent, function has code smell
        self.draw(self.x - self.x_offset, self.y - self.y_offset)



    def __delete_static_elements(self):
        if self.__matches_label:
            self.__canvas.delete(self.__description_label)
            self.__matches_label.hide()
            for match_link in self.__matches_links:
                match_link.hide()

            
            if self.__empty_label:
                self.__canvas.delete(self.__empty_label)




    
    def __select_callback(self,index,name,pno,roi_name):
        self.__selected_page_link = index
        


    def __goto_callback(self, pno, roi_name):
        if self.__goto_callback_func:
            self.__goto_callback_func(roi_name,pno,self.__path)
