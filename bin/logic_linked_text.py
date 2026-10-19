import copy
import logging
import re
from typing import Dict
from uuid import uuid4

from pandas import DataFrame
from bin.gui_elements import button_array
from bin.gui_linked_text_entry_view import linked_text_entry
from bin.gui_parameter_list_view import link_ignore_view
from bin.logic_acm_data_handler import ACM_Data_Handler
from bin.logic_internal_database import Database


class Linked_Text():


    def __init__(self, acm_data_handler: ACM_Data_Handler, linked_callback=None, goto_callback=None,change_callback=None
                    ,scanning_done_callback=None, object_type='',tagname='',subobject='', db: Database = None ) -> None:

        self.__template_text_linked = False
        self.__tagname_linked = False
        self.__tagname_text = tagname
        self.__tagname_axis = 0 
        self.__subobject_linked = False
        self.__subobject_text = subobject 
        self.__linking_enabled = False
        self.__text_link_ignore_view = None
        self.__tagname_links = {}
        self.__tagname_link_view = None
        self.__subobject_links = {}
        self.__subobject_link_view = None
        self.__parameter_link_views:Dict[str:link_ignore_view] = {}
        self.__parameter_data = {}
        self.__linked_text_data = {}
        self.__linked_callback_func = linked_callback
        self.__goto_callback_func = goto_callback
        self.__change_callback = change_callback
        self.__linking_callback_func = None
        self.__get_sheet_dataframe_func = None 
        self.__create_text_template_func = None
        self.__ignore_text_func = None
        self.__key_text_func = None
        self.__setup_regex_template = None 
        self.__remove_highlight_regex_template = None
        self.__acm_data_handler = acm_data_handler
        self.__db = db
        self.__id = None
        self.__found_tagname_links = {}
        self.__found_subobject_links = {}
        self.__found_parameter_links = {}
        self.__object_type = object_type
        self.__subobject = subobject
        self.__parameters = []
        self.__document_type = None

    def get_all_parameters(self):
        return self.__parameters

    def add_parameter(self, parameter):
        self.__parameters.append(parameter)

    def setup_text_link(self,data):
        self.__tagname_links = data['tagname_data']['links']
        self.__tagname_text = data['tagname_data']['text']
        self.__tagname_linked = True
        self.__id = data['id']
        self.__parameter_data = data['parameter_data']

        if 'object_type' in data:
            self.__object_type = data['object_type']


        if 'linked_text_data' in data:
            self.__linked_text_data = data['linked_text_data']
            self.__template_text_linked = True


        if 'template_text' in data:
            self.__template_text = data['template_text']
            self.__original_text = data['original_text']
            self.__regex_string = data['regex_string']
            

        for parameter, parameter_data in data['parameter_data'].items():
            self.__parameters.append(parameter)


    def fully_linked_check(self):
        if not self.__tagname_linked:
            raise ValueError("Tagname not linked. Please link tagname first")
        
        if not self.__parameter_data:
            raise ValueError("No parameters linked. Please link parameters first")
        
    def get_id(self):
        return self.__id

    def get_data(self):

        if self.__id is None:
            self.__id = str(uuid4())

        tagname_data = {
            'links':self.__tagname_links,
            'text':self.__tagname_text
        }

        if self.__subobject_text: 
            data = {  
                    'id': self.__id,
                    'tagname': self.__tagname_text,
                    'type': 'subobject',
                    'object_type': self.__object_type,
                    'tagname_data': tagname_data,
                    'subobject_data':{'text': self.__subobject_text},
                    'parameter_data': self.__parameter_data,
                    'linked_text_data': self.__linked_text_data,
                    'template_id': self.__id
                    }
                
        else:
            data = {  
                    'id': self.__id,
                    'tagname': self.__tagname_text,
                    'type': 'parameter',
                    'object_type': self.__object_type,
                    'tagname_data': tagname_data,
                    'parameter_data': self.__parameter_data,
                    'linked_text_data': self.__linked_text_data,
                    'template_id': self.__id
                    }

        return data

    
    def set_parameter_ref_type(self, parameter, ref_type):
        if parameter in self.__parameter_data:
            self.__parameter_data[parameter]['refType'] = ref_type


    def get_parameter_ref_type(self, parameter):
        if parameter in self.__parameter_data:
            return self.__parameter_data[parameter]['refType']
        else:
            return 'immediate'



    def save_regex_linked_text(self):

        tagname_data = {
            'links':self.__tagname_links,
            'text':self.__tagname_text
        }

        if self.__subobject_text: 
            data = {  
                    'id': str(uuid4()),
                    'tagname': self.__tagname_text,
                    'tagname_data': tagname_data,
                    'subobject_data':{'text': self.__subobject_text},
                    'type': 'subobject',
                    'parameter_data': self.__parameter_data,
                    'linked_text_data': self.__linked_text_data,
                    'object_type': self.__object_type
                    }
                
        else:
            data = {  
                    'id': str(uuid4()),
                    'tagname': self.__tagname_text,
                    'tagname_data': tagname_data,
                    'parameter_data': self.__parameter_data,
                    'type': 'parameter',
                    'linked_text_data': self.__linked_text_data,
                    'object_type': self.__object_type
                    }

        self.__db.save_linked_text_regex(data)
            

    def set_project_name(self, project_name):
        self.__project_name = project_name 


    def __add_ignore_text(self, start_char, end_char, full_string):
        pass

    def __add_key_text(self, start_char, end_char, full_string):
        pass

    def __start_background_search_for_text(self):
        pass

    def setup_linking_callback_func(self, callback, document_type):
        """ Callback used to get data of the selected roi from document viewer """
        self.__linking_callback_func = callback
        is_table_or_drawing = (document_type == Database.TABLE or document_type == Database.DRAWING)
        #self.__tagname_link_view.document_type(is_table_or_drawing)
        #for _, view in self.__parameter_link_views.items():
        #    view.document_type(is_table_or_drawing)

    
    def setup_get_sheet_dataframe_func(self, callback):
        self.__get_sheet_dataframe_func = callback


    def setup_text_template_linking_funcs(self, create_text_template, ignore_text, key_text):
        self.__create_text_template_func = create_text_template
        self.__ignore_text_func = ignore_text
        self.__key_text_func = key_text


    def setup_regex_show_funcs(self,setup_regex_template, remove_highlight_regex_template):
        self.__setup_regex_template = setup_regex_template
        self.__remove_highlight_regex_template = remove_highlight_regex_template


    def setup_regex_on_viewer(self):
        if self.__template_text_linked and self.__setup_regex_template:
                self.__setup_regex_template(
                                        self.__linked_text_data['indexes'],
                                        self.__linked_text_data['key_indexes'],
                                        self.__linked_text_data['ignore_indexes']
                                        )


    def remove_regex_on_viewer(self):
        if self.__remove_highlight_regex_template:
            self.__remove_highlight_regex_template()


    def ignore_text_trigger(self):
        self.__ignore_text_func()


    def __goto_callback(self):
        if self.__goto_callback_func and self.__tagname_links:
            tagname_links = list(self.__tagname_links.values())[0]
            self.__goto_callback_func(tagname_links['roi'],tagname_links['pno'],tagname_links['path'])


    def goto_tagname(self, index_id):
        self.__goto_tagname_callback(index_id)

    def goto_subobject(self, index_id, parameter):
        self.__goto_subobject_callback(index_id, parameter)

    def goto_parameter(self, index_id, parameter):
        self.__goto_parameter_callback(index_id, parameter)

    def __goto_tagname_callback(self,index_id):
        if not self.__tagname_links:
            return
        roi = self.__tagname_links[index_id]['roi']
        pno = self.__tagname_links[index_id]['pno']
        path = self.__tagname_links[index_id]['path']
        doc_type = self.__tagname_links[index_id]['doc_type']

        if self.__goto_callback_func:
            self.__goto_callback_func(roi,pno,path,doc_type)


    def __goto_subobject_callback(self,index_id):
        if not self.__subobject_links:
            return
        roi = self.__subobject_links[index_id]['roi']
        pno = self.__subobject_links[index_id]['pno']
        path = self.__subobject_links[index_id]['path']
        doc_type = self.__subobject_links[index_id]['doc_type']

        if self.__goto_callback_func:
            self.__goto_callback_func(roi,pno,path,doc_type)


    def get_document_type(self):
        if self.__document_type:
            return self.__document_type
        
        if self.__tagname_links:
            return list(self.__tagname_links.values())[0]['doc_type']
        


    def horizontally_aligned(self, cells):
        # Check if all cells are in the same row (horizontally aligned)
        if len(set(cell[0] for cell in cells)) == 1:
            return  1 # Horizontally Aligned
        # Check if all cells are in the same column (vertically aligned)
        elif len(set(cell[1] for cell in cells)) == 1:
            return 0 # Vertically Aligned
        # If neither condition is met, the cells are not aligned
        else:
            return -1 # Not Aligned



        
    def __tagname_direction_horizontal(self, crossover_cell):
        tagname_link = next(iter(self.__tagname_links.values()))

        if crossover_cell[1] == tagname_link['roi'][1]:
            return True 
        else:
            return False

    

    def __value_at_2D_crossover(self, tagname_link, parameter_link):

        
        row = max(tagname_link[0],parameter_link[0])
        column = max(tagname_link[1],parameter_link[1])

        
        if self.__get_sheet_dataframe_func is None:
            return None
        
        sheet_df:DataFrame = self.__get_sheet_dataframe_func()
        return sheet_df.iat[row,column], [row,column]
        


    def __find_others_in_table(self, data, parameter=None, axis=0):
        linked_text_rows = {}
        if self.__get_sheet_dataframe_func is None:
            return linked_text_rows
        
        sheet_df:DataFrame = self.__get_sheet_dataframe_func()
        
        for indexes_id, link in data.items():
            
            if axis == 0:  # Iterate over rows
                for index, _ in sheet_df.iterrows():
                    if index not in linked_text_rows:
                        linked_text_rows[index] = {}

                    if parameter:
                        if parameter not in linked_text_rows[index]:
                            linked_text_rows[index][parameter] = {}

                        linked_text_rows[index][parameter][indexes_id] = sheet_df.iat[index,link['roi'][1]]
                    else:
                        linked_text_rows[index][indexes_id] = sheet_df.iat[index,link['roi'][1]]
            else:  # Iterate over columns
                for index in range(sheet_df.shape[1]):
                    if index not in linked_text_rows:
                        linked_text_rows[index] = {}

                    if parameter:
                        if parameter not in linked_text_rows[index]:
                            linked_text_rows[index][parameter] = {}

                        linked_text_rows[index][parameter][indexes_id] = sheet_df.iat[link['roi'][0], index]
                    else:
                        linked_text_rows[index][indexes_id] = sheet_df.iat[link['roi'][0], index]
    
        return linked_text_rows
    

    def __find_other_tagnames_in_table(self):
        axis = self.__tagname_axis
        return self.__find_others_in_table(self.__tagname_links, axis=axis)
    

    def __find_other_subobject_in_table(self, axis=0):
        return self.__find_others_in_table(self.__subobject_links, axis=axis)
        

    def __find_other_parameters_in_table(self, parameter):
        axis = self.__parameter_data[parameter]['axis']
        return self.__find_others_in_table(self.__parameter_data[parameter]['links'], parameter, axis=axis)
    

    def __find_others_in_text(self):
        pass

    def __build_other_tagnames(self, linked_text_rows):
        
        for index, linked_text_row in linked_text_rows.items():
            new_tagname = self.__tagname_text
            character_differences = []

            new_tagname = self.__build_linked_text_string(linked_text_row,new_tagname,self.__tagname_links,character_differences)

            new_linked_text = self.__copy_linked_text(self.__tagname_links,
                                                      index,
                                                      self.__tagname_axis,
                                                      linked_text_row,
                                                      character_differences)
            if str(index) not in self.__found_tagname_links:
                self.__found_tagname_links[str(index)] = {}

            data = {
                'text': new_tagname,
                'links':new_linked_text

            }
            self.__found_tagname_links[str(index)]["tagname"] = data

    
    def __build_other_subobjects(self, linked_text_rows):
        
        for row, linked_text_row in linked_text_rows.items():
            new_subobject = self.__subobject_text
            character_differences = []

            new_subobject = self.__build_linked_text_string(linked_text_row,new_subobject,self.__tagname_links,character_differences)

            new_linked_text = self.__copy_linked_text(self.__subobject_links,
                                                      row,
                                                      linked_text_row,
                                                      character_differences)
            if str(row) not in self.__found_subobject_links:
                self.__found_subobject_links[str(row)] = {}

            data = {
                'text': self.__subobject_text,
                'links':new_linked_text

            }
            self.__found_subobject_links[str(row)]["subobject"] = data


    def __build_other_parameters(self, linked_text_rows, parameter):
        
        for index, linked_text_row in linked_text_rows.items():
            new_parameter_value = self.__parameter_data[parameter]['text']
            character_differences = []

            axis=self.__parameter_data[parameter]['axis']

            new_parameter_value = self.__build_linked_text_string(linked_text_row[parameter],
                                                                  new_parameter_value,
                                                                  self.__parameter_data[parameter]['links'],
                                                                  character_differences)
            
            new_parameter_value = self.__subobject_reftype_parameter_value_correction(new_parameter_value,parameter)
            new_linked_text = self.__copy_linked_text(self.__parameter_data[parameter]['links'],
                                                      index,
                                                      axis,
                                                      linked_text_row[parameter],
                                                      character_differences)
            
            if str(index) not in self.__found_parameter_links:
                self.__found_parameter_links[str(index)] = {}

            data = {
                'text': new_parameter_value,
                'link_type': self.__parameter_data[parameter]['link_type'],
                'links':new_linked_text,
                'axis': self.__parameter_data[parameter]['axis'],
                'refType': self.__parameter_data[parameter]['refType']
            }

            if 'parameter_data' not in self.__found_parameter_links[str(index)]:
                self.__found_parameter_links[str(index)]["parameter_data"] = {}

            self.__found_parameter_links[str(index)]["parameter_data"][parameter] = data


    def __subobject_reftype_parameter_value_correction(self, new_parameter_value, parameter):
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
        if (self.__parameter_data[parameter]['refType'] != 'subobject' 
            and self.__parameter_data[parameter]['refType'] != 'subobjectNIB'):
            return new_parameter_value
        
         # Split compenents of the parameter value
        parts = self.__parameter_data[parameter]['text'].split('.')
        new_parts = new_parameter_value.split('.')

        # join the parts outside the object name 
        parts_value = '.'.join(parts[1:])
        new_parts_value = '.'.join(new_parts[1:])

        numbers_parts = ''.join(c if c.isdigit() else ' ' for c in parts_value).split()
        new_numbers_parts = ''.join(c if c.isdigit() else ' ' for c in new_parts_value).split()

        # Calculate length for each number string
        lengths = [len(part) for part in numbers_parts]

        if len(numbers_parts) != len(new_numbers_parts):
            return new_parameter_value

        # Use the length of the number string to ensure that the new value is the same length
        for i,length in enumerate(lengths):
            new_number = str(int(new_numbers_parts[i]))
            new_parts_value = new_parts_value.replace(new_numbers_parts[i], new_number.zfill(length),1)

        return new_parts[0] + '.' + new_parts_value


    
    def __copy_linked_text(self, links,index,axis,doc_text, character_differences):
        new_links = copy.deepcopy(links)


        new_links = self.__correct_link_text_indexes(
                                                        character_differences, 
                                                        new_links,
                                                        doc_text
                                                        )
        
        
        for indexes_id , _ in new_links.items():
            if axis:
                new_links[indexes_id]['roi'][1] = index
            else:
                new_links[indexes_id]['roi'][0] = index

    
        return new_links


    def __correct_link_text_indexes(self, character_differences, links, doc_text):
        corrected_indexes_links = {}
        for indexes_id, link in links.items():
            indexes = list(link['indexes'])
            for character_difference in character_differences:
                if indexes[1] >= character_difference['index']:
                    indexes[0] = indexes[0] + character_difference['difference']
                    if indexes[0] <= 0:
                        indexes[0] = 0
                    indexes[1] = indexes[1] + character_difference['difference']

            key = "{start}-{end}".format(start=indexes[0],end=indexes[1])
            link['indexes'] = (indexes[0],indexes[1])
            link['text'] = doc_text[indexes_id]
            corrected_indexes_links[key] = link
        return corrected_indexes_links


    def __build_linked_text_string(self, linked_text_row, new_text, text_links, character_differences):
        for indexes_id, linked_text in text_links.items():
                
            indexes = linked_text['document_selected_text_indexes']
            if indexes:
                sub_string = str(linked_text_row[indexes_id])[indexes[0]:indexes[1]]
            else:
                sub_string = str(linked_text_row[indexes_id])

            try:
                new_text = self.__replacer(new_text
                                            ,sub_string
                                            ,list(linked_text['indexes'])
                                            ,character_differences=character_differences)

                data = {
                    'index':linked_text['indexes'][1],
                    'difference':len(sub_string)-(linked_text['indexes'][1] - linked_text['indexes'][0])
                }
                character_differences.append(data)
            except Exception as error:
                continue

        return new_text


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

    def __goto_parameter_callback(self,index_id, parameter):
        if parameter not in self.__parameter_data:
            return

        
        roi = self.__parameter_data[parameter]['links'][index_id]['roi']
        pno = self.__parameter_data[parameter]['links'][index_id]['pno']
        path = self.__parameter_data[parameter]['links'][index_id]['path']
        doc_type = self.__parameter_data[parameter]['links'][index_id]['doc_type']

        if self.__goto_callback_func:
            self.__goto_callback_func(roi,pno,path,doc_type)


    def setup_text_link_ignore_view(self, canvas, x=0, y=0):
        if self.__text_link_ignore_view is None:
            self.__text_link_ignore_view = link_ignore_view(canvas, x,y,self.__tagname_linking_callback, self.__goto_callback,self.__tagname_ignore_callback)

        if self.__linking_enabled:
            self.__text_link_ignore_view.enable_linking()
        else:
            self.__text_link_ignore_view.disable_linking()

        if self.__template_text_linked:
            self.__text_link_ignore_view.enable_goto()
            self.__linked_callback_func()
            self.__text_link_ignore_view.link_formed()


    def setup_tagname_link_view(self, canvas, x=0, y=0):
        if self.__tagname_link_view is None:
            self.__tagname_link_view = link_ignore_view(canvas, x,y,self.__tagname_linking_callback, self.__goto_callback,self.__tagname_ignore_callback)

        if self.__linking_enabled:
            self.__tagname_link_view.enable_linking()
        else:
            self.__tagname_link_view.disable_linking()

        if self.__tagname_linked:
            self.__tagname_link_view.enable_goto()
            self.__linked_callback_func()
            self.__tagname_link_view.link_formed()


    def setup_subobject_link_view(self, canvas, x=0, y=0):
        if self.__subobject_link_view is None:
            self.__subobject_link_view = link_ignore_view(canvas, x,y,self.__subobject_linking_callback, self.__goto_callback,self.__subobject_ignore_callback)

        if self.__linking_enabled:
            self.__subobject_link_view.enable_linking()
        else:
            self.__subobject_link_view.disable_linking()

        if self.__subobject_linked:
            self.__subobject_link_view.enable_goto()
            self.__linked_callback_func()
            self.__subobject_link_view.link_formed()


    def setup_parameter_link_view(self, canvas, parameter, x=0, y=0 ):
        return
       
        if parameter not in self.__parameter_link_views:
            self.__parameter_link_views[parameter] = link_ignore_view(canvas, x,y
                                                                    ,self.__parameter_linking_callback
                                                                    ,self.__goto_parameter_callback
                                                                    ,self.__parameter_ignore_callback)
        if parameter not in self.__parameter_data:
            data = {
                'linked':False
            }
            self.__parameter_data[parameter] = data
        if self.__linking_enabled:
            self.__parameter_link_views[parameter].enable_linking()
        else:
            self.__parameter_link_views[parameter].disable_linking()

          


    def __tagname_ignore_callback(self, ignored):
        print(ignored)


    def __subobject_ignore_callback(self, ignored):
        print(ignored)

    def __parameter_ignore_callback(self, ignored):
        print(ignored)


    def get_tagname_links(self):
        return self.__tagname_links
    
    def get_subobject_links(self):
        return self.__subobject_links

    def get_parameter_links(self, parameter=None):
        if not self.__parameter_data:
            return {}
        
        if parameter is None:
            parameter = list(self.__parameter_data.keys())[0]

        if (parameter not in self.__parameter_data 
            or 'link_type' not in self.__parameter_data[parameter]):
            return {}

        if self.__parameter_data[parameter]['link_type'] == 'selector':
            return {'_':self.__parameter_data[parameter]['link']}
        else:
            return self.__parameter_data[parameter]['links']


    def draw_text_link_view(self, x=0, y=0):
        """ Function called by the linked_graphic_view"""
        if self.__template_text_linked:
            self.__text_link_ignore_view.link_formed()
            self.__text_link_ignore_view.enable_goto()
        self.__text_link_ignore_view.document_type(False)  
        self.__text_link_ignore_view.draw( x, y)


    def draw_tagname_link_view(self, x=0, y=0):
        """ Function called by the linked_graphic_view"""
        if self.__tagname_linked:
            self.__tagname_link_view.link_formed()
            self.__tagname_link_view.enable_goto()
            
        self.__tagname_link_view.draw( x, y)

    
    def draw_subobject_link_view(self, x=0, y=0):
        """ Function called by the linked_graphic_view"""
        if self.__subobject_linked:
            self.__subobject_link_view.link_formed()
            self.__subobject_link_view.enable_goto()
            
        self.__subobject_link_view.draw( x, y)

    
    def draw_paramater_link_view(self, x=0, y=0,parameter=None):
        """ Function called by the linked_graphic_view"""

        if parameter is None:
            parameter = list(self.__parameter_data.keys())[0]

        if self.__parameter_data[parameter]['linked']:
            self.__parameter_link_views[parameter].link_formed()
            self.__parameter_link_views[parameter].enable_goto()
            
        self.__parameter_link_views[parameter].draw( x, y)


    def hide_tagname_link_view(self):
        if self.__tagname_link_view:
            self.__tagname_link_view.hide()


    def hide_subobject_link_view(self):
        if self.__subobject_link_view:
            self.__subobject_link_view.hide()


    def hide_parameter_link_view(self):
        for _, parameter_link_view in  self.__parameter_link_views.items():
            parameter_link_view.hide()


    def disable_link_view(self):

        self.__linking_enabled = False
            
        
        if self.__tagname_link_view:
            self.__tagname_link_view.disable_linking()

        for _, view in self.__parameter_link_views.items():
            view.disable_linking()

            

    def enable_linking(self):
        self.__linking_enabled = True
        if self.__tagname_link_view:
            self.__tagname_link_view.enable_linking()

        for _, view in self.__parameter_link_views.items():
            view.enable_linking()

    
    def disable_linking(self):
        self.__linking_enabled = False
        if self.__tagname_link_view:
            self.__tagname_link_view.disable_linking()

        for _, view in self.__parameter_link_views.items():
            view.disable_linking()

    
    def __tagname_linking_callback(self, linked):
        pass


    def __subobject_linking_callback(self, linked):
        pass


    def get_linked_text(self):
        return self.__linked_text_data['text']
    
    def get_template_text(self):
        return self.__template_text
    
    def get_regex_string(self):
        return self.__regex_string


    def template_text_link(self):
        self.__template_text_linked = True

        linked_text, regex_string, indexes, path, pno = self.__create_text_template_func()

       
        self.__linked_text_data = {}
        self.__linked_text_data['text'] = linked_text
        self.__linked_text_data['indexes'] = indexes
        self.__linked_text_data['path'] = path
        self.__linked_text_data['pno'] = pno
        self.__linked_text_data['regex_string'] = regex_string
        self.__linked_text_data['key_indexes'] = []
        self.__linked_text_data['ignore_indexes'] = []


        return linked_text
    
    
    def ignore_text(self, regex_string, indexes):
        self.__linked_text_data['regex_string'] = regex_string
        self.__linked_text_data['ignore_indexes'].append(indexes)


    def is_template_text_linked(self):
        return self.__template_text_linked



    def tagname_link(self, linked, indexes, string, name):
        if not linked:
            self.__reset_tagname_link()
            return None, None
            
        if not self.__linking_callback_func:
            return None, None

        text, _, _, _, _, _,doc_type = self.__linking_callback_func()

        if not string[indexes[0]:indexes[1]].lower() == str(text).lower():
            raise ValueError('The selected text in "'+name
                                + '" is not the same as the selected text in the document. Please make sure the text matches.')

        if self.__is_char_in_tagname_any(indexes):
            raise ValueError('The selected characters in "'+name
                                + '" have already been linked.')

        
        if self.__template_text_linked:
            data, key_indexes = self.__process_text_doc_link(indexes, doc_type)
        else:
            data, key_indexes = self.__process_table_doc_link(indexes, doc_type, self.__tagname_links)
            

        indexes_id = '{start}-{end}'.format(start=indexes[0],end=indexes[1])

        self.__tagname_links[indexes_id] = data
        self.__tagname_linked = True 
        self.__tagname_text = string
        return linked_text_entry.TOP_SIDE, key_indexes
        

    def __process_text_doc_link(self, indexes, doc_type):

        if self.__document_type is None:
            self.__document_type = doc_type

        text, text_indexes, table_data, pno, path, page_data,_ = self.__linking_callback_func()
        regex_string, key_indexes = self.__key_text_func()

        self.__linked_text_data['key_indexes'].append(key_indexes)
        self.__linked_text_data['regex_string'] = regex_string
       
        data = {
            'roi': None,
            'pno': pno,
            'path': path,
            'doc_type': doc_type,
            'regex_indexes': key_indexes,
            'text': text,
            'indexes': indexes
        }

        return data, key_indexes
        

    IGNORE_INDICATOR = '<IGNORE_CHAR>'
    KEY_ANY_WITHOUT_PERIOD = '([^.]*)'

    def __process_table_doc_link(self, indexes, doc_type, links = None):

        if self.__document_type is None:
            self.__document_type = doc_type
        
        text, indexes, table_selection, pno, path, (text_in_page, pdf_page), _ = self.__linking_callback_func()
        
        cell_bbox, table = table_selection

        for r, row in enumerate(table.rows):
            for c, cell in enumerate(row.cells):
                if cell_bbox == list(cell):
                    selected_cell = [r,c]
                    break

        def is_char_in_bbox(char, bbox):
            return (char['bbox'][0] > bbox[0] and char['bbox'][2] < bbox[2] 
                    and char['bbox'][1] > bbox[1] and char['bbox'][3] < bbox[3])
        
        regex_text_char = []

        # Use the bbox in text_in_page to get the indexes of full text of the cell
        full_text_char =[]
        for i, char in enumerate(text_in_page):
            if is_char_in_bbox(char, cell_bbox):
                char['index'] = i
                full_text_char.append(char)
                if i >= indexes[0] and i <= indexes[1]:
                    char['c'] = self.IGNORE_INDICATOR
                    regex_text_char.append(char)
                else:
                    regex_text_char.append(char)

        text_regex_string = ''

        for i in range(len(regex_text_char)):
            char = regex_text_char[i]
            
            if char['c'] == self.IGNORE_INDICATOR:
                if len(regex_text_char) != i + 1:
                    if regex_text_char[i+1]['c'] != self.IGNORE_INDICATOR:
                        text_regex_string+=self.KEY_ANY_WITHOUT_PERIOD
                else:
                    text_regex_string+=self.KEY_ANY_WITHOUT_PERIOD

            else:
                text_regex_string+= re.escape(char['c'])

                          


        cell_full_text = table.extract()[selected_cell[0]][selected_cell[1]]

        a = pdf_page.search_for(cell_full_text)

        if indexes:
            document_selected_text_indexes = [int(start_char.split('.')[1]),int(end_char.split('.')[1])]
        else: 
            document_selected_text_indexes = None


        data = {
            'roi': selected_cell,
            'pno': pno,
            'path': path,
            'doc_type': doc_type ,
            'document_selected_text_indexes':document_selected_text_indexes,
            'text': text,
            'full_text': cell_full_text,
            'full_text_char': full_text_char,
            'text_regex_string': text_regex_string,
            'regex_text_char': regex_text_char,
            'indexes': indexes
        }

        return data, None
    

    def subobject_link(self, linked, indexes, string, name):
        if not linked:
            self.__reset_subobject_link()
            return
            
        if not self.__linking_callback_func:
            return 

        text, start_char, end_char, selected_cell, pno, path, doc_type = self.__linking_callback_func()
        
        if not string[indexes[0]:indexes[1]].lower() == text.lower():
            raise ValueError('The selected text in "'+name
                                + '" is not the same as the selected text in the document. Please make sure the text matches.')

        if self.__is_char_in_subobject_any(indexes):
            raise ValueError('The selected characters in "'+name
                                + '" have already been linked.')


        if start_char and end_char:
            document_selected_text_indexes = [int(start_char.split('.')[1]),int(end_char.split('.')[1])]
        else: 
            document_selected_text_indexes = None


        data = {
            'roi': selected_cell,
            'pno': pno,
            'path': path,
            'doc_type': doc_type ,
            'document_selected_text_indexes':document_selected_text_indexes,
            'text': text,
            'indexes': indexes
        }

        indexes_id = '{start}-{end}'.format(start=indexes[0],end=indexes[1])

        self.__subobject_links[indexes_id] = data
        self.__subobject_linked = True 
        self.__subobject_text = string 
        rows = self.__find_other_subobject_in_table()
        self.__build_other_subobjects(rows)
        return linked_text_entry.TOP_SIDE



    def process_1D_referencing(self):

        found_tagnames = self.__find_other_tagnames_in_table()
        self.__build_other_tagnames(found_tagnames)

        for parameter in self.__parameter_data.keys():
            rows = self.__find_other_parameters_in_table(parameter)
            self.__build_other_parameters(rows, parameter)

        linked_tagnames_parameters = {}

        for key, item in self.__found_tagname_links.items():

            if 'parameter_data' not in self.__found_parameter_links[key]:
                continue

            if item['tagname'] == self.__tagname_text:
                continue

            parameter_data = self.__found_parameter_links[key]['parameter_data']

            if self.__subobject_text:

                
                linked_tagnames_parameters[str(uuid4())] = {  
                                                    'tagname_data': item['tagname'],
                                                    'subobject_data':{'text': self.__subobject_text},
                                                    'parameter_data': parameter_data
                                                    }
                
            else:
                linked_tagnames_parameters[str(uuid4())] = {  
                                                    'tagname_data': item['tagname'],
                                                    'parameter_data': parameter_data
                                                    }

        self.__save_new_text_links(linked_tagnames_parameters)


    
    def process_2D_referencing(self):

        tagname_link = next(iter(self.__tagname_links.values()))

        linked_tagnames_parameters = {}

        parameters_processed = []

        for parameter,_ in self.__parameter_data.items():
            parameter_link = next(iter(self.__parameter_data[parameter]['links'].values()))

            alignment = self.horizontally_aligned([tagname_link['roi'],parameter_link['roi']])

            if alignment != -1:
                continue
            
            crossover_value, crossover_cell = self.__value_at_2D_crossover(tagname_link['roi'],parameter_link['roi'])

            if crossover_value == "":
                continue

            if self.__tagname_direction_horizontal(crossover_cell):
                self.__tagname_axis = 1
                self.__parameter_data[parameter]['axis'] = 0
                found_tagnames = self.__find_other_tagnames_in_table()
                self.__build_other_tagnames(found_tagnames)
                found_parameters = self.__find_other_parameters_in_table(parameter)
                self.__build_other_parameters(found_parameters, parameter)
                
            else:
                self.__tagname_axis = 0
                self.__parameter_data[parameter]['axis'] = 1
                found_tagnames = self.__find_other_tagnames_in_table()
                self.__build_other_tagnames(found_tagnames)
                found_parameters = self.__find_other_parameters_in_table(parameter)
                self.__build_other_parameters(found_parameters, parameter)
                


            if self.__get_sheet_dataframe_func is None:
                continue
        
            sheet_df:DataFrame = self.__get_sheet_dataframe_func()

            self.__link_tagnanme_to_2D_parameter(linked_tagnames_parameters, parameter, crossover_value, sheet_df)
            parameters_processed.append(parameter)
        

        self.__save_new_text_links(linked_tagnames_parameters)

        for parameter in parameters_processed:
            self.__parameter_data.pop(parameter)



    def __link_tagnanme_to_2D_parameter(self,linked_tagnames_parameters, parameter, crossover_value, sheet_df):
        for tagname_index , tagname_item in self.__found_tagname_links.items():
            if 'tagname' not in tagname_item:
                continue

            for parameter_index, parameter_item in self.__found_parameter_links.items():
                if ('parameter_data' not in parameter_item 
                        and parameter not in parameter_item['parameter_data']):
                    continue

                    
                if self.__tagname_axis:
                    value = sheet_df.iat[int(parameter_index),int(tagname_index)]
                else:
                    value = sheet_df.iat[int(tagname_index),int(parameter_index)]


                if (crossover_value != value):
                    continue


                if self.__subobject_text:
                    linked_tagnames_parameters[str(uuid4())] = {  
                                                        'tagname_data': tagname_item['tagname'],
                                                        'subobject_data':{'text': self.__subobject_text},
                                                        'parameter_data': parameter_item['parameter_data']
                                                        }
                    
                else:
                    linked_tagnames_parameters[str(uuid4())] = {  
                                                        'tagname_data': tagname_item['tagname'],
                                                        'parameter_data': parameter_item['parameter_data']
                                                        }

       

    def create_other_subparameter_linked_texts(self):
        
        linked_tagnames_parameters = {}

        subobject_default = {
            'text':self.__subobject_text
        }

        for key, item in self.__found_tagname_links.items():

            parameter_data = self.__found_parameter_links[key]['parameter_data']
            subobject_data = self.__found_subobject_links[key]['subobject']

            linked_tagnames_parameters[item['tagname']['text']] = {  
                                                            'tagname_data': item['tagname'],
                                                            'subobject_data': item.get('subobject',subobject_default),
                                                            'parameter_data': parameter_data
                                                        }

        self.__save_new_text_links(linked_tagnames_parameters)



    def __save_new_text_links(self, linked_tagnames_parameters):
        """
        Save unapproved text links based on linked tag names and parameters.
        """
        objects_df = self.__acm_data_handler.get_all_objects_in_project()
        filtered_objects_df = objects_df.loc[objects_df['CatalogNumber'] == self.__object_type]

        for _, filtered_object in filtered_objects_df.iterrows():
            filtered_tagname = filtered_object.Name

            for key, data in linked_tagnames_parameters.items():
                if (filtered_tagname == data['tagname_data']['text'] 
                    and not self.__is_defined_subobject(data)):
                    
                    data['id'] = key
                    self.__db.save_unapproved_text_link(data)

        logging.info('Finished creating unapproved text links')


    def __is_defined_subobject(self, data):
        
        parameter=list(data['parameter_data'].keys())[0]
        new_parameter_links = copy.deepcopy(data['parameter_data'][parameter]['links'])
        current_parameter_links = copy.deepcopy(self.__parameter_data[parameter]['links'])

        new_tagname_links = copy.deepcopy(data['tagname_data']['links'])
        current_tagname_links = copy.deepcopy(self.__tagname_links)

        def remove_text_from_nested_dict(input_dict):
            for key, value in input_dict.items():
                if isinstance(value, dict):
                    value.pop('text', None)
            return input_dict

        remove_text_from_nested_dict(new_parameter_links)
        remove_text_from_nested_dict(current_parameter_links)
        remove_text_from_nested_dict(new_tagname_links)
        remove_text_from_nested_dict(current_tagname_links)

        is_parameter_data_equal = (new_parameter_links == current_parameter_links)
        is_tagname_data_equal = (new_tagname_links == current_tagname_links)
        return is_tagname_data_equal and is_parameter_data_equal
    
    
    def __parameter_linking_callback(self, linked):
        pass


    def parameter_link(self, linked, indexes, string, name):
        if not linked:
            
            self.__reset_parameter_link(name)
            return None, None
            
        if not self.__linking_callback_func:
            return None, None
        

        text, _, _, _, _, _,doc_type = self.__linking_callback_func()

        
        
        if string is not None and indexes is not None:
            if not string[indexes[0]:indexes[1]].lower() == str(text).lower():
                raise ValueError('The selected text in "'+name
                                    + '" is not the same as the selected text in the document. Please make sure the text matches.')

            if self.__is_char_in_parameter_any(indexes, name):
                raise ValueError('The selected characters in "'+name
                                    + '" have already been linked.')

            key_indexes = self.__package_entry_parameter_data(indexes, doc_type, name)
        else:
            key_indexes = self.__package_selector_parameter_data(indexes, doc_type, name)

        
        self.__parameter_data[name]['linked'] = True
        self.__parameter_data[name]['text'] = string
        self.__parameter_data[name]['refType'] = 'immediate'
        return linked_text_entry.TOP_SIDE, key_indexes




    def __package_selector_parameter_data(self, indexes, doc_type, parameter):
        

        if self.__template_text_linked:
            data, key_indexes = self.__process_text_doc_link(indexes, doc_type)
        else:
            data, key_indexes = self.__process_table_doc_link(indexes, doc_type)

            
        
        if parameter not in self.__parameter_data:
            self.__parameter_data[parameter] = {
                                                'linked':False,
                                                'axis': 0
                                                }
        
        self.__parameter_data[parameter]['link_type'] = 'selector'

        if 'links' not in self.__parameter_data[parameter]:
            self.__parameter_data[parameter]['links'] = {}
        self.__parameter_data[parameter]['links']['-'] = data
        return key_indexes



    def __package_entry_parameter_data(self, indexes, doc_type, parameter):
        
        
            
        if self.__template_text_linked:
            data, key_indexes = self.__process_text_doc_link(indexes, doc_type)
        else:
            data, key_indexes = self.__process_table_doc_link(indexes, doc_type)
        
        indexes_id = '{start}-{end}'.format(start=indexes[0],end=indexes[1])

        if parameter not in self.__parameter_data:
            self.__parameter_data[parameter] = {
                                                'linked':True,
                                                'axis': 0
                                                }

        if 'links' not in self.__parameter_data[parameter]:
            self.__parameter_data[parameter]['links'] = {}


        self.__parameter_data[parameter]['link_type'] = 'entry'
        self.__parameter_data[parameter]['links'][indexes_id] = data
        return key_indexes



    def __is_char_in_tagname_any(self, indexes):


        for _, linked_text in self.__tagname_links.items():
            if self.__index_overlap(linked_text['indexes'],indexes):
                return True

        return False
    

    def __is_char_in_subobject_any(self, indexes):


        for _, linked_text in self.__subobject_links.items():
            if self.__index_overlap(linked_text['indexes'],indexes):
                return True

        return False


    def __is_char_in_parameter_any(self, indexes, parameter):

        if parameter not in self.__parameter_data:
            return False

        if 'links' not in self.__parameter_data[parameter]:
            return False

        for _, linked_text in self.__parameter_data[parameter]['links'].items():
            if self.__index_overlap(linked_text['indexes'],indexes):
                return True

        return False


    def __index_overlap(self,index1, index2):
        """Whether index1 is overlapping index2."""
        
        range1 = range(index1[0],index1[1])
        range2 = range(index2[0],index2[1])

        if not range1:
            return True  # empty range is subset of anything
        if not range2:
            return False  # non-empty range can't be subset of empty range
        if len(range1) > 1 and range1.step % range2.step:
            return False  # must have a single value or integer multiple step
        return range1.start in range2 or range1[-1] in range2


    def __reset_tagname_link(self):
        self.__tagname_links = {}
        self.__tagname_text = None
        self.__tagname_linked = False


    def __reset_subobject_link(self):
        self.__subobject_links = {}
        self.__subobject_text = None
        self.__subobject_linked = False


    def __reset_parameter_link(self, parameter):
        self.__parameter_data[parameter]['links'] = {}
        self.__parameter_data[parameter]['linked'] = False


    def __reset_all_parameter_links(self):
        for parameter, _ in self.__parameter_data.items():
            self.__parameter_data[parameter]['links'] = {}
            self.__parameter_data[parameter]['linked'] = False

    
    def reset(self):
        self.__template_text_linked = False
        self.__reset_tagname_link()
        self.__reset_subobject_link()
        self.__reset_all_parameter_links()



if __name__ == "__main__":


    def create_other_linked_texts(acm_data_handler, object_type):
        objects_df = acm_data_handler.get_all_objects_in_project()

        filtered_objects_df = objects_df.loc[objects_df['CatalogNumber'] == object_type]

        for index, _ in filtered_objects_df.first().iterrows(): 
            print(index)

    acm_db = ACM_Data_Handler(r'DRIVER={ODBC Driver 18 for SQL Server};SERVER=1TV0VV3\SQLACM;DATABASE=ACM;Trusted_Connection=yes;TrustServerCertificate=yes;')
    acm_db.set_project_id("9")

    create_other_linked_texts(acm_db,"PAI")