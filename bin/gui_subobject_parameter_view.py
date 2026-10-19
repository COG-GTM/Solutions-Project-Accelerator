import tkinter as tk
from tkinter import font
from tkinter import messagebox
from turtle import width


from bin.gui_base64_icons import empty_image
from bin.gui_elements import custom_label, is_active_canvas_screen
from bin.gui_horizontal_scrolling_selector import horizontal_scrolling_selector
from bin.gui_subobject_parameter_list_view import subobject_parameter_list_view
from bin.logic_acm_data_handler import ACM_Data_Handler
from bin.logic_acm_function_handler import acm_parameter_handler
from bin.logic_acm_libraries_retrieval import acm_libraries_retrieval, get_library_file_path
from bin.logic_acm_library_parser import acm_library_parser
from bin.logic_acm_db_commands import subobject_subparameter_value_template, create_subobject
from bin.logic_internal_database import Database

class subobject_parameter_view:
    def __init__(self, name, object_id, description, go_to_callback=None,save_reference_id_callback=None) -> None:

        self.__object_id = object_id
        self.__name = name 
        self.__description_label = None
        self.__empty_image_id = None 
        self.__description = description
        
        self.__go_to_callback = go_to_callback
        self.__save_reference_id_callback = save_reference_id_callback
        self.__document_selection_subscription_selected = None 
        self.__document_selection_subscription_kwargs = None
        self.__subobject_list_views = []
        self.__pending_transactions = {}
        
    
    def setup_subobject_parameter_view(self,canvas:tk.Canvas, x, y, project_name,acm_data_handler:ACM_Data_Handler,db:Database,config
                                       ,add_to_background_func = None, remove_from_background_func = None):
        self.__x = x
        self.__y = y
        self.__canvas = canvas 
        self.__project_name = project_name
        self.__config = config
        self.__add_to_background_func = add_to_background_func
        self.__remove_from_background_func = remove_from_background_func    
        self.__screen_label = custom_label(self.__canvas, 8, 0, text="Subobjects", fill= '#505050',size=16,weight="bold")
        self.__object_label = custom_label(self.__canvas,8, 24, text=self.__name, fill= '#505050',size=11,weight="bold")
        self.__parse_library_file(project_name,acm_data_handler)
        self.__acm_data_handler = acm_data_handler
        self.__db = db
        self.__subobjects = self.__library_parser.get_all_subobjects()
        self.__subobject_list = list(self.__subobjects.keys())
        self.__selected_subobject = 0 
        if len(self.__subobject_list) == 0:
            return
        self.__horizontal_scrolling_selector  = horizontal_scrolling_selector(self.__canvas
                                                    ,self.__subobject_list
                                                    ,callback=self.__horizontal_selector_callback
                                                    ,selected=self.__subobject_list[self.__selected_subobject])
        
        self.__create_subobject_list_views(self.__subobject_list)


    def show_add_subobject_view_with_prediction(self, subobject, callback=None):
        self.__subobject_list_views[self.__selected_subobject].hide()
        index = self.__subobject_list.index(subobject)
        self.__selected_subobject = index
        self.draw()
        self.__canvas.after(100, self.__subobject_list_views[self.__selected_subobject].add_non_commit_subobject,callback)
        
        

    def show_linked_text(self, linked_text):
        subobject = linked_text['subobject']['text']
        self.__selected_subobject = self.__subobject_list.index(subobject)
        self.__subobject_list_views[self.__selected_subobject].hide()
        self.draw()
        self.__subobject_list_views[self.__selected_subobject].show_linked_text(linked_text)

    def document_selection_subscription(self, selected , **kwargs):
        self.__document_selection_subscription_selected = selected
        self.__document_selection_subscription_kwargs = kwargs
        if not self.__subobject_list_views:
            return
        for subobject_list_view in self.__subobject_list_views:
            subobject_list_view.document_selection_subscription(selected , **kwargs)


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


    def __create_subobject_list_views(self, subobject_list):
        self.__subobject_list_views=[]
        for subobject_type in subobject_list:

            subobject_parameters = self.__library_parser.get_subobject_parameters(subobject_type)

            if subobject_type not in self.__pending_transactions:
                self.__pending_transactions[subobject_type] = {}

            list_view = subobject_parameter_list_view(self.__canvas
                                                        ,self.__object_id
                                                        ,self.__acm_data_handler
                                                        ,self.__db
                                                        ,self.__project_name
                                                        ,16,96
                                                        ,selected_subobject_dict={}
                                                        ,subobject=self.__subobjects[subobject_type]
                                                        ,subobject_parameters=subobject_parameters
                                                        ,tagname=self.__name
                                                        ,subobject_type=subobject_type
                                                        ,create_subobject_callback=self.__create_subobject
                                                        ,go_to_callback=self.__go_to_callback
                                                        ,redraw_callback=self.draw
                                                        ,save_reference_id_callback=self.__save_reference_id_callback
                                                        ,library_parser=self.__library_parser
                                                        ,config=self.__config
                                                        ,add_to_background_func=self.__add_to_background_func
                                                        ,remove_from_background_func=self.__remove_from_background_func
                                                        ,is_active_callback=self.is_active)

            self.__subobject_list_views.append(list_view)

            if self.__document_selection_subscription_kwargs:
                list_view.document_selection_subscription(
                                        self.__document_selection_subscription_selected 
                                        , **self.__document_selection_subscription_kwargs
                                        )


    def __parse_library_file(self, project_name,acm_data_handler:ACM_Data_Handler):
        library_id = acm_data_handler.get_object_library_id(self.__name)
        library_file_path = get_library_file_path(library_id,project_name)
        if not library_file_path:
            projects_df = acm_data_handler.get_all_projects()
            acm_project_name = projects_df.loc[int(acm_data_handler.get_project_id())]['Name']
            acm_libraries_retrieval(project_name, acm_project_name,threaded=False)
            library_file_path = get_library_file_path(library_id,project_name)
            if not library_file_path:
                raise Exception(f"Unable to access parameters of {self.__name}.")
        self.__library_parser = acm_library_parser(library_file_path)



    def __create_subobject(self, subobject):
        subobject_parameters = self.__library_parser.get_subobject_parameters(self.__subobject_list[self.__selected_subobject])
        try:
            subobject_parameters['Index']['Max'] = acm_parameter_handler(subobject_parameters['Index']['Max']
                              ,self.__object_id
                              ,self.__acm_data_handler
                              ,self.__project_name)
            self.__acm_data_handler.create_subobject(self.__object_id,self.__subobjects[subobject], subobject_parameters)
        except Exception as error:
            messagebox.showwarning("Unable to create new subobject",error)


    
    def ignore_text(self, linked_text, parameter):
        for subobject_list_view in self.__subobject_list_views:
            subobject_list_view.ignore_text(linked_text, parameter)

    
    
    def is_active(self):
        return is_active_canvas_screen(self.__canvas, self)


    def draw(self, x=0, y=0,refresh_data=False):
        if '<Configure>' not in self.__canvas.bind():
                return
        # A deferred redraw can arrive after the user moved to another screen on the shared canvas
        if not self.is_active():
                return
        self.__delete_static_elements()
        self.__screen_label.draw(0,0)
        self.__object_label.draw(0,0)
        
        self.__description_label = self.__canvas.create_text(self.__x + 24,self.__y + y + 48, text=self.__description, anchor=tk.NW, fill="#6F6F6F")
        description_bounds = self.__canvas.bbox(self.__description_label) 
        if (description_bounds[2] - description_bounds[0]) > (self.__canvas.winfo_width() - 48) and self.__canvas.winfo_width() > 0:
            self.__description_label = self.fit_text_in_mutiline(self.__description_label, self.__x + 24, self.__y + y + 22, self.__description)

        if len(self.__subobject_list) == 0:
            self.__draw_empty_indicator()
            return

        self.__horizontal_scrolling_selector.draw(0,64)
        self.__subobject_list_views[self.__selected_subobject].draw(width=self.__canvas.winfo_width()-16)
        self.__canvas.config(scrollregion=(0,0,self.__canvas.bbox(tk.ALL)[2],self.__canvas.bbox(tk.ALL)[3]+100))


    def __horizontal_selector_callback(self, event):
        self.__subobject_list_views[self.__selected_subobject].hide()
        
        self.__selected_subobject= int(event[1])
        self.draw()


    def __delete_static_elements(self):
        if self.__description_label:
            self.__canvas.delete(self.__description_label)


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