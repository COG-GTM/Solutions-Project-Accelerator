
import profile
import tkinter as tk

from bin.gui_elements import custom_label, is_active_canvas_screen
from bin.gui_parameter_list_view import parameter_list_view
from bin.logic_acm_data_handler import ACM_Data_Handler
from bin.logic_acm_libraries_retrieval import acm_libraries_retrieval, get_library_file_path
from bin.logic_acm_library_parser import acm_library_parser
from bin.logic_internal_database import Database

class object_parameter_view:
    def __init__(self, name,id, description,go_to_callback=None) -> None:
        self.__name = name 
        self.__object_id = id
        self.__description_label = None
        self.__description = description
        self.__go_to_callback = go_to_callback
        self.__document_selection_subscription_selected = None
        self.__document_selection_subscription_kwargs = None
        self.__parameter_list_view = None

    def setup_object_parameter_view(self,canvas:tk.Canvas, x, y, project_name,acm_data_handler:ACM_Data_Handler,db:Database,config):
        self.__x = x
        self.__y = y
        self.__canvas = canvas 
        self.__acm_data_handler = acm_data_handler
        self.__config = config
        self.__project_name = project_name
        self.__screen_label = custom_label(self.__canvas, 8, 0, text="Parameters", fill= '#505050',size=16,weight="bold")
        self.__object_label = custom_label(self.__canvas,8, 24, text=self.__name, fill= '#505050',size=11,weight="bold")
        self.__parse_library_file(project_name,acm_data_handler)

        self.__parameter_list_view = parameter_list_view(self.__canvas
                                ,self.__acm_data_handler
                                ,self.__object_id
                                ,self.__project_name
                                ,8,64
                                ,selected_parameter_dict={}
                                ,full_paramater_dict=self.__library_parser.get_parameters()
                                ,tagname=self.__name
                                ,library_id=self.__library_id
                                ,redraw_callback=self.draw
                                ,go_to_callback=self.__go_to_callback
                                ,db=db
                                ,config=self.__config
                                ,is_active_callback=self.is_active)
        if self.__document_selection_subscription_kwargs:
            self.__parameter_list_view.document_selection_subscription(self.__document_selection_subscription_selected 
                                                                , **self.__document_selection_subscription_kwargs)


    def show_linked_text(self, linked_text):
        if self.__parameter_list_view:
            self.__parameter_list_view.show_linked_text(linked_text)

    def show_add_parameter_view_with_prediction(self, text, callback=None):
        if self.__parameter_list_view:
            self.__parameter_list_view.show_add_parameter_view_with_prediction(text, callback)

    def __parse_library_file(self, project_name,acm_data_handler:ACM_Data_Handler):
        self.__library_id = acm_data_handler.get_object_library_id(self.__name)
        library_file_path = get_library_file_path(self.__library_id,project_name)
        if not library_file_path:
            projects_df = acm_data_handler.get_all_projects()
            acm_project_name = projects_df.loc[int(acm_data_handler.get_project_id())]['Name']
            acm_libraries_retrieval(project_name, acm_project_name,threaded=False)
            library_file_path = get_library_file_path(self.__library_id,project_name)
            if not library_file_path:
                raise Exception(f"Unable to access parameters of {self.__name}.")
        self.__library_parser = acm_library_parser(library_file_path)


    def document_selection_subscription(self, selected , **kwargs):
        self.__document_selection_subscription_selected = selected
        self.__document_selection_subscription_kwargs = kwargs
        if self.__parameter_list_view is None:
            return 
        self.__parameter_list_view.document_selection_subscription(selected , **kwargs)


    def ignore_text(self):
        if self.__parameter_list_view:
            self.__parameter_list_view.ignore_text()


    def is_active(self):
        return is_active_canvas_screen(self.__canvas, self)


    def draw(self, x=0, y=0):
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
        self.__parameter_list_view.draw(width=self.__canvas.winfo_width() - 8)


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

    def __delete_static_elements(self):
        if self.__description_label:
            self.__canvas.delete(self.__description_label)