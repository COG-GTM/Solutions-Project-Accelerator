import threading
import tkinter as tk
from tkinter import messagebox
import uuid

import pandas as pd
from bin.gui_approval_view import rectangle_canvas_button
from bin.gui_elements import custom_entry, custom_label
from bin.gui_link_ignore_text_view import link_ignore_text_view
from bin.gui_parameter_selection import string_selector
from bin.logic_acm_data_handler import ACM_Data_Handler
from bin.logic_internal_database import Database


class assign_object_type_view():
    def __init__(self):
        
        self.__description = "Used to create objects using the object name or a property found in a table."
        self.__description_label = None
        self.__assignment_id = None
        self.__error_on_apply = None
        self.__ignore_indexes = [] 

    def setup_assign_object_view(self, canvas:tk.Canvas, x, y, tagname,acm_data_handler:ACM_Data_Handler,db:Database,assignment_id=""):
        self.__x = x
        self.__y = y
        self.__tagname = tagname
        self.__canvas = canvas
        self.__acm_data_handler = acm_data_handler
        self.__db = db
        self.__assignment_id = assignment_id
        
        self.__screen_label = custom_label(self.__canvas, x + 8, y + 0, text="Assign Object Type", fill= '#505050',size=16,weight="bold")
        self.__tagname_label = custom_label(self.__canvas, x + 8, y + 0, text=self.__tagname, fill= '#505050',size=11,weight="bold")
        self.__link_ignore_text_view = link_ignore_text_view(canvas
                                                             ,name=self.__tagname
                                                             ,ignore_text_callback=self.__ignore_text)
        self.__link_ignore_text_view.insert(self.__tagname)
        

        self.registerd_libraries_options = self.__get_registerd_libraries_options()
        options_strings = [i[0] for i in self.registerd_libraries_options]
        self.__library_selector = custom_entry(self.__canvas, 0,0,autocompleteList=options_strings,placeholder='Library Selection'
                                               ,focus_out_callback=self.__library_selection_callback, edit_callback=self.__edit_callback)
        self.__apply_button = rectangle_canvas_button('Apply',canvas,self.__apply_object_assignment)
        self.__apply_button.disable()

        self.__remove_rule_button = rectangle_canvas_button('Remove Rule',canvas,self.__remove_rule)
        self.__remove_rule_button.disable()

        self.__ignore_rule_button = rectangle_canvas_button('Ignore Rule',canvas,self.__ignore_rule)
        self.__ignore_rule_button.disable()

        self.__populate_object_assignment()


    def __populate_object_assignment(self):
        if not self.__assignment_id:
            return

        object_assignment = self.__db.get_object_assignment_regex(self.__assignment_id)

        if not object_assignment:
            return
        
        self.__remove_rule_button.enable()
        self.__ignore_rule_button.enable()

        self.__library_selector.set_text(object_assignment['library'][0])
        self.__link_ignore_text_view.insert(object_assignment['tagname'])
        self.__library_selector.disable()
        self.__ignore_indexes = object_assignment['ignore_indexes']

        for index in self.__ignore_indexes:
            self.__link_ignore_text_view.highlight_remove(index[0], index[1])
        

    def __remove_rule(self):
        self.__db.delete_object_assignment_regex(self.__assignment_id)
        self.__remove_rule_button.disable()
        self.__ignore_rule_button.disable()
        

        self.__library_selector.set_text('')
        self.__library_selector.enable()
        self.__ignore_indexes = []
        self.__link_ignore_text_view.clean_highlights()
        self.__link_ignore_text_view.insert(self.__tagname)


    def __ignore_rule(self):
        self.__remove_rule_button.disable()
        self.__ignore_rule_button.disable()
        self.__apply_button.enable()


        self.__library_selector.set_text('')
        self.__library_selector.enable()
        self.__ignore_indexes = []
        self.__link_ignore_text_view.clean_highlights()
        self.__link_ignore_text_view.insert(self.__tagname)





    def __apply_object_assignment(self):

        
        if self.__error_on_apply:
            messagebox.showerror('Error', self.__error_on_apply)
            return
        

        regex_string = self.__build_regex()

        options_strings = [i[0] for i in self.registerd_libraries_options]
        option = self.__library_selector.get()

        index = options_strings.index(option)

        library = self.registerd_libraries_options[index]

        self.__assignment_id = str(uuid.uuid4())

        data = {
            'id':self.__assignment_id,
            'tagname':self.__tagname,
            'library':library,
            'regex':regex_string,
            'ignore_indexes':self.__ignore_indexes
        }

        self.__db.save_object_assignment_regex(data)
        self.__canvas.after(500, self.__ignore_rule_button.enable)
        self.__canvas.after(500, self.__remove_rule_button.enable)
        self.__canvas.after(500, self.__apply_button.disable)


    
        

    def __get_acm_objects(self):
    
        if self.__acm_data_handler is None:
            return
        
        all_object = self.__acm_data_handler.get_all_objects_in_project()

        if all_object.empty:
            # Return empty dataframe if no objects
            return pd.DataFrame() 
        
        frame = {
                    'id':all_object.index,
                    'Name':all_object['Name'],
                    'Type':all_object['CatalogNumber']
        }
        return pd.DataFrame(frame)
        


    def __get_internal_db_objects(self):
        if self.__db is None:
            return 
        
        self.__control_modules = self.__db.get_all_control_modules()

        list = []
        for control_module in self.__control_modules:
            if 'id' not in  control_module:
                control_module['id'] = str(uuid.uuid4())
            d = {
                'id':control_module['id'],
                'Name':control_module['name'],
                'Type':control_module['type'],
            }
            list.append(d)

        internal_db_df = pd.DataFrame(list)
        return internal_db_df


    def __edit_callback(self,_):
        option = self.__library_selector.get()
        self.__apply_button.enable()

        options_strings = [i[0] for i in self.registerd_libraries_options]

        if option not in options_strings:
            self.__error_on_apply = 'Not a valid library'
            self.__library_selector.error('Not a valid library')
        else:
            self.__library_selector.reset_error()
            self.__error_on_apply = None

        
    def __library_selection_callback(self):
        option = self.__library_selector.get()

        options_strings = [i[0] for i in self.registerd_libraries_options]

        if option not in options_strings:
            self.__library_selector.error('Not a valid library')
            self.__apply_button.disable()
        else:
            self.__library_selector.reset_error()
            self.__apply_button.enable()


    def __get_registerd_libraries_options(self):
        self.registerd_libraries_df = self.__acm_data_handler.get_all_registered_libraries()
        core_types = self.registerd_libraries_df['CoreType']
        catalog_numbers = self.registerd_libraries_df['CatalogNumber']
        major_revs = self.registerd_libraries_df['MajorRev']
        minor_revs = self.registerd_libraries_df['MinorRev']

        # Listed of options for the library selector based on the CatalogNumber, MajorRev and MinorRev
        return [[f'{catalog_number} {major_rev}.{minor_rev}',core_type,catalog_number,major_rev,minor_rev] 
                for core_type, catalog_number, major_rev, minor_rev in zip(core_types, catalog_numbers, major_revs, minor_revs)]

    
    def draw(self, x=0, y=0):
        self.__delete_static_elements()
        self.__screen_label.draw(0,0)
        self.__tagname_label.draw(0,24)
        self.__description_label = self.__canvas.create_text(self.__x + 24,self.__y + y + 42, text=self.__description, anchor=tk.NW, fill="#6F6F6F")
        description_bounds = self.__canvas.bbox(self.__description_label) 
        if (description_bounds[2] - description_bounds[0]) > (self.__canvas.winfo_width() - 48) and self.__canvas.winfo_width() > 0:
            self.__description_label = self.fit_text_in_mutiline(self.__description_label, self.__x + 24, self.__y + y + 42, self.__description)
        description_bounds = self.__canvas.bbox(self.__description_label) 
        link_ignore_text_view_height = self.__link_ignore_text_view.draw(0,description_bounds[3] - 4)
        self.__library_selector.draw(0,description_bounds[3] + link_ignore_text_view_height + 24)
        self.__apply_button.draw(self.__canvas.winfo_width() - 80,description_bounds[3] + link_ignore_text_view_height + 128)
        self.__remove_rule_button.draw(self.__canvas.winfo_width() - 190,description_bounds[3] + link_ignore_text_view_height + 128)
        self.__ignore_rule_button.draw(self.__canvas.winfo_width() - 290,description_bounds[3] + link_ignore_text_view_height + 128)


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
        self.__screen_label.hide()
        self.__tagname_label.hide()
        self.__link_ignore_text_view.hide()
        self.__library_selector.hide()

    def __ignore_text(self, _):
        start , end = self.__link_ignore_text_view.get_text_selection()
        self.__link_ignore_text_view.remove_mark_blue()
        # convert tkinter indexes to python indexes
        start = int(start.split('.')[1])-1
        end = int(end.split('.')[1])-1
        self.__link_ignore_text_view.highlight_remove(start , end)
        self.__ignore_indexes.append([start,end])

    def __build_regex(self):

        def is_within_indexes( i, indexes):
            for index in indexes:
                if i >= index[0] and i < index[1]:
                    return True
            return False
            

        # Use the indexes to build a regex using text from the link_ignore_text_view
        text = self.__link_ignore_text_view.get_text()
        regex_string = ''
        for i, char in enumerate(text):
            if is_within_indexes(i, self.__ignore_indexes):
                regex_string += '([^.]*?)'
            else:
                regex_string += char

        # Remove newlines
        regex_string = regex_string.replace('\n', '')

        while '([^.]*?)([^.]*?)' in regex_string:
            regex_string = regex_string.replace('([^.]*?)([^.]*?)', '([^.]*?)')

        return regex_string


        
    

    


    
        


        

    