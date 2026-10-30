import ast
import copy
from dataclasses import asdict, dataclass, field
from enum import Enum
import logging
import re
import threading
import uuid

from pandas import DataFrame

from bin.logic_acm_data_handler import ACM_Data_Handler
from bin.logic_internal_database import Database
from bin import logic_safe_regex as safe_regex

# Page text is a flat character stream with the line breaks stripped, so these
# glyphs are the only markers left of where one list item ends and the next begins.
_ITEM_SEPARATOR_GLYPHS = '\u2022\u2023\u2043\u25aa\u25ab\u25cf\u25e6\u00b7\uf071\uf0a7\uf0b7'
ITEM_SEPARATOR_CHARACTERS = '\n\r' + _ITEM_SEPARATOR_GLYPHS
ITEM_SEPARATOR_CHARACTER_CLASS = r'\n\r' + _ITEM_SEPARATOR_GLYPHS


def contains_item_separator(text):
    """Return True when the text runs across a list item or line boundary."""
    return any(char in ITEM_SEPARATOR_CHARACTERS for char in str(text))


class LinkedTextMatchError(Exception):
    def __init__(self, message="Linked text does not Match"):
        self.message = message
        super().__init__(self.message)


@dataclass
class GivenTextLink():
    linked: bool = False
    text: str = ''
    indexes: tuple = None
    path: str = None
    pno: str = None
    roi: list = None
    regex_string: str = None
    key_and_ignore_indexes: list = None
    in_table: bool = False
    table_shape: tuple = None
    table_bbox: tuple = None
    doc_type: str = None
    axis: int = 0
    text_format: str = ''
    in_list: bool = False


    def __eq__(self, value: object) -> bool:
        if not isinstance(value, GivenTextLink):
            return False
        return (self.text == value.text
                and (self.indexes == None or self.indexes[0] == value.indexes[0])
                and (self.indexes == None or self.indexes[1] == value.indexes[1])
                and self.path == value.path
                and self.pno == value.pno
                and self.roi == value.roi
                and self.doc_type == value.doc_type
                and self.axis == value.axis)
    

    def is_close_match(self, value: object) -> bool:
        if not isinstance(value, GivenTextLink):
            return False
        
        if not self.indexes or not value.indexes:
            return False
                
        return (self.indexes[0] <= value.indexes[1] and self.indexes[1] >= value.indexes[0]
                and self.path == value.path
                and self.pno == value.pno
                and self.roi == value.roi
                and self.doc_type == value.doc_type
                and self.axis == value.axis)


@dataclass
class TargetTextLink():
    target_text_indexes: tuple
    given_text_id: str
    given_text_indexes: list


class TargetTextType (str, Enum):
    OBJECT = 'object'
    REAL = 'real'
    INT = 'integer'
    STRING = 'string'

    @classmethod
    def _missing_(cls, _):
        return TargetTextType.STRING

class TagnameParameterRelationship(str, Enum):
    IN_LINE = 'in_line'                     # Tagname and parameter are in the same line of text 
    IN_TABLE = 'in_table'                   # Tagname and parameter are in a table 
    LIST_HEADER = 'list_header'             # Tagname is a header and the parameter is in a list below the header
    UNDEFINED = 'undefined'                 # Relationship is undefined

    @classmethod
    def _missing_(cls, _):
        return TagnameParameterRelationship.UNDEFINED
    

class LinkType(str, Enum):
    SELECTOR = 'selector'                   # The target text is a selector
    TEXT = 'text'                           # The target text is text

    @classmethod
    def _missing_(cls, _):
        return LinkType.TEXT

@dataclass
class LinkedText():
    text: str = ''
    text_type: TargetTextType = TargetTextType.STRING
    object_type: str = None
    linked: bool = False
    given_text: dict[str,GivenTextLink] = None
    links: dict[str,TargetTextLink] = None
    reftype: str = None
    link_type: LinkType = LinkType.TEXT
    axis: int = 0

    def dict(self):
        return {k: str(v) if k == 'links' or k == 'given_text' else v
                for k, v in asdict(self).items()}
    

    def first_and_last_index(self):
        if self.given_text:
            start_index = min([i.indexes[0] for i in self.given_text.values()])
            end_index = max([i.indexes[1] for i in self.given_text.values()])
            return (start_index, end_index)
        return None
    


    

class Linked_Texts():

    def __init__(self, acm_data_handler: ACM_Data_Handler, linked_callback=None, goto_callback=None,change_callback=None
                    ,scanning_done_callback=None, object_type='',tagname='',subobject='', db: Database = None ) -> None:
        self.tagname = LinkedText(tagname, TargetTextType.OBJECT, object_type)
        if subobject:
            self.subobject = LinkedText(subobject, TargetTextType.OBJECT, object_type)
        else:
            self.subobject = None
        self.__acm_data_handler = acm_data_handler
        self.__get_sheet_dataframe_func = None 
        self.__given_text_func = None
        self.__ignore_text_func = None
        self.__remove_given_text_func = None
        self.__setup_regex_template = None
        self.__highlight_linked_text = None
        self.__remove_highlight_linked_text = None
        self.__goto_callback_func = goto_callback
        self.__linking_callback_func = None
        self.__remove_highlight_regex_template = None
        self.__object_type = object_type
        self.__processed_parameters = []
        self.__id = None
        self.__db = db
        self.__found_tagname_links:dict[str,dict[str,LinkedText]] = {}
        self.__found_parameter_links:dict[str,LinkedText] = {}
        self.parameters: dict[str,LinkedText] = {}
        self.__highlighting_regex_template = False 
        self.__highlighting_linked_text = False
        self.__is_llm_generated = False


    def get_tagname_linked_text(self):
        return self.tagname
    

    def get_subobject_linked_text(self):
        return self.subobject
    
    

    def get_parameter_linked_text(self, parameter_name=None):

        if parameter_name and parameter_name in self.parameters:
            return self.parameters[parameter_name]
        elif not parameter_name and self.parameters:
            return self.parameters[list(self.parameters.keys())[0]]
        else:
            return None
        

    def unlink_tagname(self):
        self.tagname.linked = False
        self.tagname.links = {}


    def unlink_parameter(self, parameter_name):
        if parameter_name in self.parameters:
            self.parameters[parameter_name].linked = False
            self.parameters[parameter_name].links = {}


    def get_all_parameter_names(self):
        return list(self.parameters.keys())


    def add_parameter(self, parameter_name, data_type=None,copy_tagname=True):
        self.parameters[parameter_name] = LinkedText()
        self.parameters[parameter_name].object_type = self.__object_type

        if data_type == 'Real':
            self.parameters[parameter_name].text_type = TargetTextType.REAL
        elif data_type == 'Int':
            self.parameters[parameter_name].text_type = TargetTextType.INT

        if self.tagname.given_text and copy_tagname:
            first_given_text = list(self.tagname.given_text.values())[0]
            if first_given_text.doc_type == Database.TEXT and not first_given_text.in_table:
                given_texts = copy.deepcopy(self.tagname.given_text)
                self.parameters[parameter_name].given_text = given_texts


    def setup_get_sheet_dataframe_func(self, callback):
        self.__get_sheet_dataframe_func = callback


    def setup_text_document_linking_funcs(self, given_text_func, ignore_text_func, key_text_func):
        self.__given_text_func = given_text_func
        self.__ignore_text_func = ignore_text_func
        self.__remove_given_text_func = key_text_func


    def set_tagname_ignore_text(self, text_view_selection=None, prediction=None):
        return self.__set_ignore_text(self.tagname, text_view_selection, prediction)

    def set_subobject_ignore_text(self, text_view_selection=None, prediction=None):
        return self.__set_ignore_text(self.subobject, text_view_selection, prediction)

    def set_parameter_ignore_text(self, parameter_name, text_view_selection=None, prediction=None):
        return self.__set_ignore_text(self.parameters[parameter_name], text_view_selection, prediction)


    def __set_ignore_text(self, linked_text:LinkedText, text_view_selection, prediction):
        if prediction:
            given_text_id, text_indexes = prediction
            if not linked_text.given_text[given_text_id].key_and_ignore_indexes:
                linked_text.given_text[given_text_id].key_and_ignore_indexes = []
            linked_text.given_text[given_text_id].key_and_ignore_indexes.append(text_indexes)

        elif text_view_selection:
            _, given_text_id, text_indexes = self.__handle_text_viewer_text_index(linked_text, text_view_selection)
        elif self.__given_text_func:
            document_selection = self.__given_text_func()

            doc_type = document_selection[6]
            full_text = str(document_selection[0][0])
            doc_start = document_selection[1]
            doc_end = document_selection[2]
            if document_selection[0][1] is None and doc_type == Database.TABLE:
                text_indexes = [0,len(full_text)]
            elif doc_type == Database.TABLE:
                # convert tkinter indexes to python indexes e.g. (1.0,1.9) to (0,9)
                text_indexes = (int(doc_start.split('.')[1]),int(doc_end.split('.')[1]))
            else:
                text_indexes = (doc_start,doc_end)
            roi = document_selection[3]
            path = document_selection[5]
            pno = document_selection[4]

            if doc_type == Database.TEXT:
                given_text_id, _ = self.__handle_text_key_text(linked_text, text_indexes)
            elif doc_type == Database.TABLE:
                given_text_id = self.__handle_table_key_text(linked_text, doc_type, full_text, text_indexes, roi, path, pno)
           
        key_indexes = []
        
        # If links have been defined and the target indexes are not from a selector
        if linked_text.links and linked_text.link_type != LinkType.SELECTOR:
            for _, link in linked_text.links.items():
                if link.given_text_id == given_text_id and link.given_text_indexes:
                    key_indexes.append(link.given_text_indexes)
        
        self.__build_regex_string(linked_text, given_text_id, key_indexes)

        ignore_indexes = linked_text.given_text[given_text_id].key_and_ignore_indexes
        # FIlter out key indexes out of ignore indexes
        if ignore_indexes:
            ignore_indexes = [index for index in ignore_indexes if index not in key_indexes]

        self.__sync_given_text(linked_text, given_text_id)
        return linked_text.given_text[given_text_id].text,key_indexes,ignore_indexes, given_text_id


    def unset_tagname_ignore_text(self, text_view_selection):
        return self.__unset_ignore_text(self.tagname, text_view_selection)
    
    def unset_subobject_ignore_text(self, text_view_selection):
        return self.__unset_ignore_text(self.subobject, text_view_selection)
    
    def unset_parameter_ignore_text(self, parameter_name, text_view_selection):
        return self.__unset_ignore_text(self.parameters[parameter_name], text_view_selection)

    
    def __unset_ignore_text(self, linked_text:LinkedText, text_view_selection):
        if not text_view_selection:
            raise ValueError("No text selection provided to unset ignore text.")

        _, given_text_id, _ = self.__handle_text_viewer_text_index(linked_text, text_view_selection, True)

        key_indexes = []
        # If links have been defined and the target indexes are not from a selector
        if linked_text.links and linked_text.link_type != LinkType.SELECTOR:
            for _, link in linked_text.links.items():
                if link.given_text_id == given_text_id and link.given_text_indexes:
                    key_indexes.append(link.given_text_indexes)
        
        self.__build_regex_string(linked_text, given_text_id, key_indexes)

        ignore_indexes = linked_text.given_text[given_text_id].key_and_ignore_indexes
        # FIlter out key indexes out of ignore indexes
        if ignore_indexes:
            ignore_indexes = [index for index in ignore_indexes if index not in key_indexes]

        self.__sync_given_text(linked_text, given_text_id)
        return linked_text.given_text[given_text_id].text,key_indexes,ignore_indexes, given_text_id
        
    def remove_text_indexes_from_ranges(self, linked_text: LinkedText, given_text_id: str, text_indexes_to_remove: tuple):
        """
        Remove specific text indexes from key_and_ignore_indexes ranges.
        Instead of removing entire ranges, this function removes specific character positions
        and adjusts the ranges accordingly by splitting overlapping ranges.
        
        Args:
            linked_text: The LinkedText object containing the ranges
            given_text_id: The ID of the given text
            text_indexes_to_remove: Tuple (start, end) of indexes to remove
        """
        if (given_text_id not in linked_text.given_text or 
            not linked_text.given_text[given_text_id].key_and_ignore_indexes):
            return
            
        key_and_ignore_indexes = linked_text.given_text[given_text_id].key_and_ignore_indexes
        remove_start, remove_end = text_indexes_to_remove
        updated_ranges = []
        
        for current_range in key_and_ignore_indexes:
            range_start, range_end = current_range
            
            # Case 1: Remove range is completely before or after current range - no overlap
            if remove_end <= range_start or remove_start >= range_end:
                # Keep current range unchanged
                updated_ranges.append(current_range)
                
            # Case 2: Remove range overlaps with current range
            else:
                # Part before the removal (if any)
                if range_start < remove_start:
                    updated_ranges.append((range_start, remove_start))
                
                # Part after the removal (if any) - keep original positions
                if range_end > remove_end:
                    updated_ranges.append((remove_end, range_end))
        
        # Update the key_and_ignore_indexes with the new ranges
        linked_text.given_text[given_text_id].key_and_ignore_indexes = updated_ranges
        
    def remove_exact_range_from_indexes(self, linked_text: LinkedText, given_text_id: str, text_indexes_to_remove: tuple):
        """
        Remove an exact matching range from key_and_ignore_indexes.
        This is equivalent to the original list.remove() functionality but with error handling.
        
        Args:
            linked_text: The LinkedText object containing the ranges
            given_text_id: The ID of the given text
            text_indexes_to_remove: Tuple (start, end) of exact range to remove
        """
        if (given_text_id not in linked_text.given_text or 
            not linked_text.given_text[given_text_id].key_and_ignore_indexes):
            return
            
        key_and_ignore_indexes = linked_text.given_text[given_text_id].key_and_ignore_indexes
        
        # Try to remove the exact range
        try:
            key_and_ignore_indexes.remove(text_indexes_to_remove)
        except ValueError:
            # If exact range not found, fall back to the more sophisticated removal
            self.remove_text_indexes_from_ranges(linked_text, given_text_id, text_indexes_to_remove)


    def __build_regex_string(self, linked_text:LinkedText, given_text_id, key_indexes=None):
        """
        Uses the given text key indexes and ignore indexes to build a regex string.
        By marking the indexes to ignore with a negative lookbehind assertion.

        """
        given_text = linked_text.given_text[given_text_id]

        if not given_text.key_and_ignore_indexes:
            linked_text.given_text[given_text_id].regex_string = given_text.text
            return

        key_and_ignore_indexes = given_text.key_and_ignore_indexes

        regex_string = ''
        key_regex_group = self.get_key_text_regex_group(linked_text)
        default_regex_group = '([^.{0}]*?)'.format(ITEM_SEPARATOR_CHARACTER_CLASS)
        given_text_string = given_text.text

        # Remove trailing whitespaces to avoid matching them in the regex
        given_text_string = given_text_string.rstrip()
        for i in range(len(given_text_string)):

            if key_indexes and self.is_within_indexes(i, key_indexes):
                regex_string += key_regex_group
            elif key_and_ignore_indexes and self.is_within_indexes(i, key_and_ignore_indexes):
                regex_string += default_regex_group
            else:
                regex_string += re.escape(given_text_string[i])

        # Cleanup multiple negative lookbehind assertions
        while default_regex_group+default_regex_group in regex_string:
            regex_string = regex_string.replace(default_regex_group+default_regex_group,default_regex_group)

        while key_regex_group+key_regex_group in regex_string:
            regex_string = regex_string.replace(key_regex_group+key_regex_group,key_regex_group)

        if not given_text.in_table:

            # Remove lookbehind assertion at the beginning of the string to 
            # avoid matching the all the text before the text when not in a table
            if regex_string.startswith(default_regex_group):
                regex_string = regex_string.replace(default_regex_group,'',1)

            if (regex_string.startswith(key_regex_group) 
                and linked_text.text_type == TargetTextType.STRING):
                regex_string = regex_string.replace(key_regex_group,'',1)

            # Remove lookbehind assertion at the end of the string to 
            # avoid matching the all the text before the text when not in a table
            if regex_string.endswith(default_regex_group):
                regex_string = regex_string[:-len(default_regex_group)]

            if (regex_string.endswith(key_regex_group)
                and linked_text.text_type == TargetTextType.STRING):
                regex_string = regex_string[:-len(key_regex_group)]
        
        else:
            if regex_string == default_regex_group:
                regex_string = '([^.{0}]*)'.format(ITEM_SEPARATOR_CHARACTER_CLASS)

        linked_text.given_text[given_text_id].regex_string = regex_string

            


    def get_key_text_regex_group(self, linked_text:LinkedText):
        if linked_text.text_type == TargetTextType.INT:
            return r'(\d+)'
        elif linked_text.text_type == TargetTextType.REAL:
            # Integer or decimal number
            return r'(\d+(\.\d+)?)'
        elif linked_text.text_type == TargetTextType.OBJECT:
            # Alphabetical characters, numbers and underscores
            return r'([a-zA-Z0-9_]*)'
        else:
            return '([^.{0}]*?)'.format(ITEM_SEPARATOR_CHARACTER_CLASS)


    def is_within_indexes(self, i, indexes):
        for index in indexes:
            if i >= index[0] and i < index[1]:
                return True
        return False
    
    
    def unlink_tagname_given_text(self, given_text_id):
        self.__unlink_given_text(self.tagname, given_text_id)



    def unlink_subobject_given_text(self, given_text_id):
        self.__unlink_given_text(self.subobject, given_text_id)


    def unlink_parameter_given_text(self, parameter_name, given_text_id):
        self.__unlink_given_text(self.parameters[parameter_name], given_text_id)

    
    def __unlink_given_text(self, linked_text:LinkedText, given_text_id):
        if given_text_id in linked_text.given_text:
            del linked_text.given_text[given_text_id]
            index_ids = []
            if linked_text.links:
                for index_id, target_text_link in linked_text.links.items():
                    if target_text_link.given_text_id == given_text_id:
                        index_ids.append(index_id)
                
                for index_id in index_ids:
                    del linked_text.links[index_id]
                
                if not linked_text.links:
                    linked_text.linked = False

        # Check if the given text is used in other linked texts if not remove it from document viewer
        found_in_others = False
        if self.tagname.given_text and given_text_id in self.tagname.given_text:
            found_in_others = True
        
        if self.subobject and self.subobject.given_text and given_text_id in self.subobject.given_text:
            found_in_others = True

        for parameter in self.parameters.values():
            if parameter.given_text and given_text_id in parameter.given_text:
                found_in_others = True
                break

        if self.__remove_given_text_func and not found_in_others:
            self.__remove_given_text_func(given_text_id)


    def __sync_given_text(self, linked_text:LinkedText, given_text_id):
        
        if (linked_text!= self.tagname 
            and self.tagname.given_text 
            and given_text_id in self.tagname.given_text):
            self.tagname.given_text[given_text_id] = copy.deepcopy(linked_text.given_text[given_text_id])

        if (linked_text!= self.subobject and self.subobject   
            and self.subobject.given_text 
            and given_text_id in self.subobject.given_text):
            self.subobject.given_text[given_text_id] = copy.deepcopy(linked_text.given_text[given_text_id])

        for parameter in self.parameters.values():
            if (linked_text!= parameter and parameter.given_text 
                and given_text_id in parameter.given_text):
                parameter.given_text[given_text_id] = copy.deepcopy(linked_text.given_text[given_text_id])
        

    def set_tagname_given_text(self, document_selection=None, option=None):
        return self.__set_given_text(self.tagname, document_selection, option)


    def set_subobject_given_text(self, document_selection=None):
        return self.__set_given_text(self.subobject, document_selection)


    def set_parameter_given_text(self, parameter_name, document_selection=None):
        return self.__set_given_text(self.parameters[parameter_name], document_selection)


    def __set_given_text(self, linked_text:LinkedText, document_selection=None, option=None):
        if not document_selection and not self.__given_text_func:
            return
        
        if not document_selection:  
            document_selection = self.__given_text_func(option)

        if not document_selection:
            return

        if not linked_text.given_text:
            linked_text.given_text = {}

        new_given_text = GivenTextLink(linked=True
                                        ,text=str(document_selection[0][1])
                                        ,roi=document_selection[3][0]
                                        ,path=document_selection[5]
                                        ,pno=document_selection[4]
                                        ,doc_type=document_selection[6]
                                        ,indexes=(document_selection[1],document_selection[2]))
        
        if new_given_text.doc_type == Database.TEXT and document_selection[3][0]:
            new_given_text.in_table = True 
            new_given_text.table_shape=document_selection[3][1]
            new_given_text.table_bbox=document_selection[3][4]
        elif new_given_text.doc_type == Database.TEXT and document_selection[3][2]:
            new_given_text.in_list = True

        
        
        if new_given_text in linked_text.given_text.values():
            return

        id = str(uuid.uuid4())
        linked_text.given_text[id] = new_given_text
        
        return linked_text.given_text[id].text, id
        


    def set_key_tagname_text(self, link, indexes, string, name, text_view_selection, prediction=None):
        return self.__set_key_text(self.tagname, link, indexes, string, name, text_view_selection, prediction)

    def set_key_subobject_text(self, link, indexes, string, name, text_view_selection, prediction=None):
        return self.__set_key_text(self.subobject, link, indexes, string, name, text_view_selection, prediction)

    def set_key_parameter_text(self, link, indexes, string, parameter_name, text_view_selection, prediction=None):
        return self.__set_key_text(self.parameters[parameter_name], link, indexes, string, parameter_name, text_view_selection, prediction)


    def __set_key_text(self, linked_text:LinkedText, link, target_indexes, string, name, text_view_selection, prediction=None):
        if not link:
            return self.__remove_key_text(linked_text, target_indexes)
        
        if prediction:
            text, given_text_id, given_indexes = prediction
            if not linked_text.given_text[given_text_id].key_and_ignore_indexes:
                linked_text.given_text[given_text_id].key_and_ignore_indexes = []
            linked_text.given_text[given_text_id].key_and_ignore_indexes.append(given_indexes)
            text_source = "intelligence prediction"
        elif text_view_selection:
            text, given_text_id, given_indexes = self.__handle_text_viewer_text_index(linked_text, text_view_selection)
            text_source = "above text view"
        elif self.__given_text_func:
            document_selection = self.__given_text_func()

            doc_type = document_selection[6]
            full_text = str(document_selection[0][0])
            text = str(document_selection[0][1])
            doc_start = document_selection[1]
            doc_end = document_selection[2]
            if document_selection[0][1] is None and doc_type == Database.TABLE:
                text = full_text
                given_indexes = [0,len(full_text)]
                roi = document_selection[3]
            elif doc_type == Database.TABLE:
                # convert tkinter indexes to python indexes e.g. (1.0,1.9) to (0,9)
                given_indexes = (int(doc_start.split('.')[1]),int(doc_end.split('.')[1]))
                roi = document_selection[3]
            elif doc_type == Database.TEXT and document_selection[3][0]:
                roi = document_selection[3][0]
                given_indexes = (doc_start,doc_end)
            else:
                given_indexes = (doc_start,doc_end)
            
            path = document_selection[5]
            pno = document_selection[4]

            if doc_type == Database.TEXT and document_selection[3][0] is None:
                given_text_id, given_indexes = self.__handle_text_key_text(linked_text, given_indexes)
            elif doc_type == Database.TEXT and document_selection[3][0]:
                given_text_id, given_indexes = self.__handle_table_key_text(linked_text, doc_type
                                                                           , full_text, given_indexes
                                                                           , roi, path, pno, document_selection[3][5])
                linked_text.given_text[given_text_id].in_table = True 
                linked_text.given_text[given_text_id].table_shape=document_selection[3][1]
                linked_text.given_text[given_text_id].table_bbox=document_selection[3][4]
            elif doc_type == Database.TABLE:
                given_text_id = self.__handle_table_key_text(linked_text, doc_type
                                                             , full_text, given_indexes
                                                             , roi, path, pno
                                                             , is_selector=target_indexes == [0,-1])
                linked_text.given_text[given_text_id].in_table = True 
            text_source = "document"

        # Check if target indexes are not from a selector ([0,-1]) and that the selected characters have already been linked
        # The ([0,-1]) array can only sent by selectors
        if target_indexes != [0,-1] and not string[target_indexes[0]:target_indexes[1]].lower() == str(text).lower():
            raise ValueError('The selected text in "'+name
                            + '" is not the same as the selected text in the {}. Please make sure the text matches.'.format(text_source))

        # Check if target indexes are not from a selector ([0,-1]) and that the selected characters have already been linked
        if target_indexes != [0,-1] and self.__is_char_in_any_link(target_indexes, linked_text):
            raise ValueError('The selected characters in "'+name
                            + '" have already been linked.')

        linked_text.text = string

        if not linked_text.links:
            linked_text.links = {}

        indexes_id = '{start}-{end}'.format(start=target_indexes[0],end=target_indexes[1])

        linked_text.links[indexes_id] = TargetTextLink(target_text_indexes=target_indexes
                                                ,given_text_id=given_text_id
                                                ,given_text_indexes=given_indexes)
        linked_text.linked = True
        linked_text.link_type = LinkType.TEXT if target_indexes != [0,-1] else LinkType.SELECTOR
        key_indexes = []

        # If links have been defined and the target indexes are not from a selector
        if linked_text.links and linked_text.link_type != LinkType.SELECTOR:
            for _, link in linked_text.links.items():
                if link.given_text_id == given_text_id and link.given_text_indexes:
                    key_indexes.append(link.given_text_indexes)
        
        self.__build_regex_string(linked_text, given_text_id, key_indexes)

        ignore_indexes = linked_text.given_text[given_text_id].key_and_ignore_indexes
        # FIlter out key indexes out of ignore indexes
        if ignore_indexes:
            ignore_indexes = [index for index in ignore_indexes if index not in key_indexes]

        self.__sync_given_text(linked_text, given_text_id)
        return linked_text.given_text[given_text_id].text,key_indexes,ignore_indexes, given_text_id
    


    def __handle_text_viewer_text_index(self, linked_text:LinkedText, text_view_selection, remove=False):
        given_text_id = text_view_selection[2]
        if isinstance(text_view_selection[0], int):
            text_indexes = (int(text_view_selection[0]),int(text_view_selection[1]))
        else:
            text_indexes = (int(text_view_selection[0].split('.')[1])-1,int(text_view_selection[1].split('.')[1])-1)
        text = linked_text.given_text[given_text_id].text[text_indexes[0]:text_indexes[1]]

        if remove:
            self.remove_exact_range_from_indexes(linked_text, given_text_id, text_indexes)
            return text, given_text_id, text_indexes
        if not linked_text.given_text[given_text_id].key_and_ignore_indexes:
            linked_text.given_text[given_text_id].key_and_ignore_indexes = []
        linked_text.given_text[given_text_id].key_and_ignore_indexes.append(text_indexes)

        return text, given_text_id, text_indexes
        
        
        

    def __handle_text_key_text(self, linked_text:LinkedText, text_indexes):
        given_text_id = list(linked_text.given_text.keys())[0]
        if self.__index_within(text_indexes, linked_text.given_text[given_text_id].indexes):
            
            
                
            # key index relative to the given text
            text_indexes = [text_indexes[0]-linked_text.given_text[given_text_id].indexes[0],
                            text_indexes[1]-linked_text.given_text[given_text_id].indexes[0]]
            
          
            if not linked_text.given_text[given_text_id].key_and_ignore_indexes:
                linked_text.given_text[given_text_id].key_and_ignore_indexes = []

            linked_text.given_text[given_text_id].key_and_ignore_indexes.append(text_indexes)

            return given_text_id, text_indexes
        raise ValueError('The selected key text in is not in linked text shown above. Please make sure the text is within the text above.')



    def __handle_table_key_text(self, linked_text:LinkedText, doc_type, full_text, key_indexes, roi, path, pno
                                , full_text_indexes=None, is_selector=False):
        if not linked_text.given_text:
            linked_text.given_text = {}

        new_given_text = GivenTextLink(linked=True
                                            ,text=full_text
                                            ,roi=roi
                                            ,path=path
                                            ,pno=pno
                                            ,doc_type=doc_type)
        

        if doc_type == Database.TEXT:
            # key index relative to the given text
            new_given_text.indexes = full_text_indexes
            key_indexes = [key_indexes[0]-new_given_text.indexes[0],
                            key_indexes[1]-new_given_text.indexes[0]]
        

        if (new_given_text not in linked_text.given_text.values()):
            given_text_id = str(uuid.uuid4())
            linked_text.given_text[given_text_id] = new_given_text
                
        else:
            for given_text_id, given_text in linked_text.given_text.items():
                if given_text == new_given_text:
                    given_text_id = given_text_id
                    break
        
        
        if not linked_text.given_text[given_text_id].key_and_ignore_indexes:
            linked_text.given_text[given_text_id].key_and_ignore_indexes = []
        
        if is_selector:
            key_indexes = []
        else:
            linked_text.given_text[given_text_id].key_and_ignore_indexes.append(key_indexes)
        
        if doc_type == Database.TEXT:
            return given_text_id, key_indexes
        
        return given_text_id
    

    def __remove_key_text(self, linked_text:LinkedText, indexes):
        index_id = '{start}-{end}'.format(start=indexes[0],end=indexes[1])
        if index_id not in linked_text.links:
            return
        given_text_id = linked_text.links[index_id].given_text_id

        if given_text_id not in linked_text.given_text:
            return

        if linked_text.given_text[given_text_id].key_and_ignore_indexes is None:
            return 

        for i, key_index in enumerate(linked_text.given_text[given_text_id].key_and_ignore_indexes):
            if linked_text.links[index_id].given_text_indexes == key_index:
                del linked_text.given_text[given_text_id].key_and_ignore_indexes[i]
                break

        

        # Remove the key text if it is the only key text left then unlink the linked_text
        del linked_text.links[index_id]
        if not linked_text.links:
            linked_text.linked = False

        key_indexes = []
        if linked_text.links:
            for _, link in linked_text.links.items():
                if link.given_text_id == given_text_id and link.given_text_indexes:
                    key_indexes.append(link.given_text_indexes)
        ignore_indexes = linked_text.given_text[given_text_id].key_and_ignore_indexes
        # Filter out key indexes out of ignore indexes
        if ignore_indexes:
            ignore_indexes = [index for index in ignore_indexes if index not in key_indexes]

        self.__sync_given_text(linked_text, given_text_id)
        return linked_text.given_text[given_text_id].text,key_indexes,ignore_indexes, given_text_id


    def __reset_linked_text(self, linked_text:LinkedText):
        linked_text.linked = False
        linked_text.given_text = {}
        linked_text.links = {}
        
        

    def __is_char_in_any_link(self, indexes, linked_text:LinkedText=None):
        if not linked_text.links:
            return False
        
        for _, links in linked_text.links.items():
            if self.__index_overlap(links.target_text_indexes,indexes):
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
    
    
    def __index_within(self,index1, index2):
        """Whether index1 is within index2."""
        return index1[0] >= index2[0] and index1[1] <= index2[1]
        

    def setup_regex_show_funcs(self,setup_regex_template, remove_highlight_regex_template):
        self.__setup_regex_template = setup_regex_template
        self.__remove_highlight_regex_template = remove_highlight_regex_template


    def setup_linked_text_highlight_funcs(self, highlight_func, remove_highlight_func):
        self.__highlight_linked_text = highlight_func
        self.__remove_highlight_linked_text = remove_highlight_func


    def __setup_regex_template_threaded(self, *args, **kwargs):

        # Use thread to call self.__setup_regex_template to avoid blocking the main thread
        thread = threading.Thread(target=self.__setup_regex_template, args=args, kwargs=kwargs)
        thread.start()
        self.__highlighting_regex_template = True


    def remove_highlight_linked_text(self):
        if self.__remove_highlight_linked_text:
            self.__remove_highlight_linked_text()


    def highlight_linked_text_on_doc_viewer(self):
        if self.__remove_highlight_linked_text:
            self.__remove_highlight_linked_text()

        if self.__highlight_linked_text is None:
            return

        tagname_given_text_id = list(self.tagname.given_text.keys())[0]

        if self.subobject and self.subobject.given_text:
            
            subobject_given_text_id = list(self.subobject.given_text.keys())[0]
            self.__highlight_linked_text(self.__id,
                                         self.tagname.given_text[tagname_given_text_id].indexes
                                        ,self.subobject.given_text[subobject_given_text_id].indexes)
            
        else: 
            self.__highlight_linked_text(self.__id
                                        ,self.tagname.given_text[tagname_given_text_id].indexes
                                        ,[])
            
        self.__highlighting_linked_text = True


    def setup_tagname_regex_on_viewer(self, show_regex_matches=True):
        if self.tagname.given_text and self.__setup_regex_template:
            # Use the first given text to setup regex
            given_text_id = list(self.tagname.given_text.keys())[0]
            
            key_indexes = []
            if self.tagname.links:
                for _, link in self.tagname.links.items():
                    if link.given_text_id == given_text_id and link.given_text_indexes:
                        key_indexes.append(link.given_text_indexes)
            ignore_indexes = self.tagname.given_text[given_text_id].key_and_ignore_indexes
            in_table = self.tagname.given_text[given_text_id].in_table
            roi = self.tagname.given_text[given_text_id].roi
            table_shape = self.tagname.given_text[given_text_id].table_shape
            table_bbox = self.tagname.given_text[given_text_id].table_bbox
            
            # Filter out key indexes out of ignore indexes
            if ignore_indexes:
                ignore_indexes = [index for index in ignore_indexes if index not in key_indexes]
             
            self.__setup_regex_template_threaded(self.tagname.given_text[given_text_id].indexes
                                        ,key_indexes
                                        ,ignore_indexes
                                        ,self.tagname.given_text[given_text_id].regex_string
                                        ,given_text_id
                                        ,'tagname'
                                        ,is_table=in_table
                                        ,roi=roi
                                        ,table_shape=table_shape
                                        ,table_bbox=table_bbox
                                        ,show_regex_matches=show_regex_matches)
    

    def setup_subobject_regex_on_viewer(self, show_regex_matches=True):
        if self.subobject.given_text and self.__setup_regex_template:
            # Use the first given text to setup regex
            given_text_id = list(self.subobject.given_text.keys())[0]

            key_indexes = []
            if self.subobject.links:
                for _, link in self.subobject.links.items():
                    if link.given_text_id == given_text_id and link.given_text_indexes:
                        key_indexes.append(link.given_text_indexes)
            ignore_indexes = self.subobject.given_text[given_text_id].key_and_ignore_indexes
            in_table = self.tagname.given_text[given_text_id].in_table
            roi = self.tagname.given_text[given_text_id].roi
            table_shape = self.tagname.given_text[given_text_id].table_shape
            table_bbox = self.tagname.given_text[given_text_id].table_bbox
            
            # Filter out key indexes out of ignore indexes
            if ignore_indexes:
                ignore_indexes = [index for index in ignore_indexes if index not in key_indexes]
            
            self.__setup_regex_template_threaded(self.subobject.given_text[given_text_id].indexes
                                        ,key_indexes
                                        ,ignore_indexes
                                        ,self.subobject.given_text[given_text_id].regex_string
                                        ,given_text_id
                                        ,'subobject'
                                        ,is_table=in_table
                                        ,roi=roi
                                        ,table_shape=table_shape
                                        ,table_bbox=table_bbox
                                        ,show_regex_matches=show_regex_matches)
    


    def setup_parameter_regex_on_viewer(self, parameter, show_regex_matches=True):
        if self.parameters[parameter].given_text and self.__setup_regex_template:
            # Use the first given text to setup regex
            given_text_id = list(self.parameters[parameter].given_text.keys())[0]

            key_indexes = []
            if self.parameters[parameter].links:
                for _, link in self.parameters[parameter].links.items():
                    if link.given_text_id == given_text_id and link.given_text_indexes:
                        key_indexes.append(link.given_text_indexes)
            ignore_indexes = self.parameters[parameter].given_text[given_text_id].key_and_ignore_indexes
            in_table = self.parameters[parameter].given_text[given_text_id].in_table
            roi = self.parameters[parameter].given_text[given_text_id].roi
            table_shape = self.parameters[parameter].given_text[given_text_id].table_shape
            table_bbox = self.parameters[parameter].given_text[given_text_id].table_bbox
            # Filter out key indexes out of ignore indexes
            if ignore_indexes:
                ignore_indexes = [index for index in ignore_indexes if index not in key_indexes]
            
            self.__setup_regex_template_threaded(self.parameters[parameter].given_text[given_text_id].indexes
                                        ,key_indexes
                                        ,ignore_indexes
                                        ,self.parameters[parameter].given_text[given_text_id].regex_string
                                        ,given_text_id
                                        ,'parameter'
                                        ,parameter
                                        ,is_table=in_table
                                        ,roi=roi
                                        ,table_shape=table_shape
                                        ,table_bbox=table_bbox
                                        ,show_regex_matches=show_regex_matches)
    


    def remove_highlights_on_viewer(self):
        if self.__remove_highlight_regex_template and self.__highlighting_regex_template:
            self.__remove_highlight_regex_template(remove_key_ignore_marks=True)
            self.__highlighting_regex_template = False
        if self.__remove_highlight_linked_text and self.__highlighting_linked_text:
            self.__remove_highlight_linked_text()
            self.__highlighting_linked_text = False

    def __goto_callback(self):
        if self.__goto_callback_func and self.tagname.links:
            tagname_link = (self.tagname.links.values())[0]
            given_text = self.tagname.given_text[tagname_link.given_text_id]
            self.__goto_callback_func(given_text.roi,given_text.pno,given_text.path)


    def goto_tagname(self, index_id):
        if not self.tagname.linked:
            return
        
        given_text_id = self.tagname.links[index_id].given_text_id
        
        roi = self.tagname.given_text[given_text_id].roi

        if self.tagname.given_text[given_text_id].doc_type == Database.TEXT:
            indexes = self.tagname.given_text[given_text_id].indexes
            given_indexes = self.tagname.links[index_id].given_text_indexes

            roi = self.__id, [indexes[0]+given_indexes[0],indexes[0]+given_indexes[1]]

        pno = self.tagname.given_text[given_text_id].pno
        path = self.tagname.given_text[given_text_id].path
        doc_type = self.tagname.given_text[given_text_id].doc_type

        if self.__goto_callback_func:
            self.__goto_callback_func(roi,pno,path,doc_type)


    def goto_subobject(self, index_id):
        if not self.subobject.linked:
            return
        
        given_text_id = self.subobject.links[index_id].given_text_id
        
        roi = self.subobject.given_text[given_text_id].roi

        if self.subobject.given_text[given_text_id].doc_type == Database.TEXT:
            indexes = self.subobject.given_text[given_text_id].indexes
            given_indexes = self.subobject.links[index_id].given_text_indexes

            roi = self.__id, [indexes[0]+given_indexes[0],indexes[0]+given_indexes[1]]

        pno = self.subobject.given_text[given_text_id].pno
        path = self.subobject.given_text[given_text_id].path
        doc_type = self.subobject.given_text[given_text_id].doc_type

        if self.__goto_callback_func:
            self.__goto_callback_func(roi,pno,path,doc_type)


    def goto_parameter(self, parameter_name, index_id):
        if not self.parameters[parameter_name].linked:
            return
        
        
        given_text_id = self.parameters[parameter_name].links[index_id].given_text_id
        
        roi = self.parameters[parameter_name].given_text[given_text_id].roi

        if self.parameters[parameter_name].given_text[given_text_id].doc_type == Database.TEXT:
            indexes = self.parameters[parameter_name].given_text[given_text_id].indexes
            given_indexes = self.parameters[parameter_name].links[index_id].given_text_indexes

            roi = self.__id, [indexes[0]+given_indexes[0],indexes[0]+given_indexes[1]]

        pno = self.parameters[parameter_name].given_text[given_text_id].pno
        path = self.parameters[parameter_name].given_text[given_text_id].path
        doc_type = self.parameters[parameter_name].given_text[given_text_id].doc_type

        if self.__goto_callback_func:
            self.__goto_callback_func(roi,pno,path,doc_type)


    def __goto_given_text(self, linked_text: LinkedText, given_text_id):
        if not linked_text or not linked_text.given_text:
            return

        if given_text_id not in linked_text.given_text:
            given_text_id = list(linked_text.given_text.keys())[0]

        given_text = linked_text.given_text[given_text_id]

        roi = given_text.roi
        if given_text.doc_type == Database.TEXT:
            roi = self.__id, [given_text.indexes[0], given_text.indexes[1]]

        if self.__goto_callback_func:
            self.__goto_callback_func(roi,given_text.pno,given_text.path,given_text.doc_type)


    def goto_tagname_given_text(self, given_text_id=None):
        self.__goto_given_text(self.tagname, given_text_id)


    def goto_subobject_given_text(self, given_text_id=None):
        self.__goto_given_text(self.subobject, given_text_id)


    def goto_parameter_given_text(self, parameter_name, given_text_id=None):
        self.__goto_given_text(self.parameters.get(parameter_name), given_text_id)


    def get_document_type(self):
        if self.tagname.linked and self.tagname.links:
            given_text_id = list(self.tagname.links.values())[0].given_text_id
            return self.tagname.given_text[given_text_id].doc_type
        else:
            return None


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
        
    
    def process_1D_referencing(self):

        found_tagnames = self.__find_other_tagnames_in_table()
        self.__build_other_linked_texts(found_tagnames)

        for parameters in self.parameters.keys():
            if parameters in self.__processed_parameters:
                continue
            rows = self.__find_other_parameters_in_table(parameters)
            self.__build_other_parameters(rows, parameters)

        all_new_linked_texts = {}

        for key, linked_texts in self.__found_tagname_links.items():

            if self.__found_parameter_links[key] is None:
                continue

            if linked_texts['tagname'].text == self.tagname.text:
                continue

            parameters = self.__found_parameter_links[key]

            id = str(uuid.uuid4())

            given_text_id = list(linked_texts['tagname'].given_text.keys())[0]
            pno = linked_texts['tagname'].given_text[given_text_id].pno
            path = linked_texts['tagname'].given_text[given_text_id].path

            all_new_linked_texts[id] = {  
                                        'tagname': linked_texts['tagname'],
                                        'parameters': parameters,
                                        'pno': pno,
                                        'path': path
                                        }

            if self.subobject:
                all_new_linked_texts[id]['subobject'] = self.subobject


        self.__save_new_text_links(all_new_linked_texts)


    def save_regex_linked_text(self):

        if self.__id is None:
            self.__id = str(uuid.uuid4())

        data = {
            'id' : self.__id,
            'tagname': self.tagname.dict(),
            'parameters': {k: v.dict() for k, v in self.parameters.items()}
        }

        if self.subobject:
            data['subobject'] = self.subobject.dict()

        data['text_relationship'] = self.__determine_tagname_parameter_text_relationship()

        # Get first given_text in tagname
        first_given_text = list(self.tagname.given_text.values())[0]
        data['path']= first_given_text.path
        data['pno'] = first_given_text.pno
        data['template_id'] = self.__id

        self.__db.save_linked_text_regex(data)



    def process_2D_referencing(self):

        all_new_linked_texts = {}

        self.__processed_parameters = []

        tagname_link = self.tagname.given_text[next(iter(self.tagname.links.values())).given_text_id]

        for parameter,parameter_linked_text in self.parameters.items():
            parameter_link = parameter_linked_text.given_text[next(iter(parameter_linked_text.links.values())).given_text_id]

            alignment = self.horizontally_aligned([tagname_link.roi,parameter_link.roi])

            if alignment != -1:
                continue
            
            crossover_value, crossover_cell = self.__value_at_2D_crossover(tagname_link.roi,parameter_link.roi)

            if crossover_value == "":
                continue

            if self.__tagname_direction_horizontal(crossover_cell):
                self.tagname.axis = 1
                self.parameters[parameter].axis = 0
                found_tagnames = self.__find_other_tagnames_in_table()
                self.__build_other_linked_texts(found_tagnames)
                found_parameters = self.__find_other_parameters_in_table(parameter)
                self.__build_other_parameters(found_parameters, parameter)
                
            else:
                self.tagname.axis = 0
                self.parameters[parameter].axis = 1
                found_tagnames = self.__find_other_tagnames_in_table()
                self.__build_other_linked_texts(found_tagnames)
                found_parameters = self.__find_other_parameters_in_table(parameter)
                self.__build_other_parameters(found_parameters, parameter)
                


            if self.__get_sheet_dataframe_func is None:
                continue
        
            sheet_df:DataFrame = self.__get_sheet_dataframe_func()

            self.__link_tagname_to_2D_parameter(all_new_linked_texts, parameter, crossover_value, sheet_df)
            self.__processed_parameters.append(parameter)
        

        self.__save_new_text_links(all_new_linked_texts)

      




    def __link_tagname_to_2D_parameter(self,all_new_linked_texts, parameter, crossover_value, sheet_df):
        for tagname_index , linked_texts in self.__found_tagname_links.items():

            for parameter_index, parameters in self.__found_parameter_links.items():
                if (not parameters and parameter not in parameters):
                    continue

                    
                if self.tagname.axis:
                    value = str(sheet_df.iat[int(parameter_index),int(tagname_index)])
                else:
                    value = str(sheet_df.iat[int(tagname_index),int(parameter_index)])


                if (crossover_value != value):
                    continue

                id = str(uuid.uuid4())

                given_text_id = list(linked_texts['tagname'].given_text.keys())[0]
                pno = linked_texts['tagname'].given_text[given_text_id].pno
                path = linked_texts['tagname'].given_text[given_text_id].path

                all_new_linked_texts[id] = {  
                                        'tagname': linked_texts['tagname'],
                                        'parameters': parameters,
                                        'pno': pno,
                                        'path': path
                                        }

                if self.subobject:
                    all_new_linked_texts[id]['subobject'] = self.subobject

       


    def __save_new_text_links(self, all_new_linked_texts:dict[str,dict[str,LinkedText]]):
        """
        Save unapproved text links based on linked tag names and parameters.
        """
        objects_df = self.__acm_data_handler.get_all_objects_in_project()
        filtered_objects_df = objects_df.loc[objects_df['CatalogNumber'] == self.__object_type]

        for _, filtered_object in filtered_objects_df.iterrows():
            filtered_tagname = filtered_object.Name

            for key, linked_texts in all_new_linked_texts.items():
                if (filtered_tagname == linked_texts['tagname'].text
                    and not self.__is_defined_parameter(linked_texts['parameters'])):
                    
                    linked_texts['id'] = key
                    self.__db.save_unapproved_text_link(self.__linked_texts_to_dict(linked_texts))

        logging.info('Finished creating unapproved text links')


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
    




    def __is_defined_parameter(self, linked_texts:dict[str,LinkedText]):
        for parameter, new_parameter in linked_texts.items():
            current_given_text = self.parameters[parameter].given_text
            new_given_text = new_parameter.given_text


            shared = len({k: new_given_text[k] for k in new_given_text 
                if k in current_given_text and new_given_text[k] == current_given_text[k]})
            
            if shared == len(new_given_text):
                return True
        return False



    def __tagname_direction_horizontal(self, crossover_cell):
        
        given_text_id = list(self.tagname.links.values())[0].given_text_id

        if crossover_cell[1] == self.tagname.given_text[given_text_id].roi[1]:
            return True 
        else:
            return False
        

    def __value_at_2D_crossover(self, tagname_link, parameter_link):
        row = max(tagname_link[0],parameter_link[0])
        column = max(tagname_link[1],parameter_link[1])

        
        if self.__get_sheet_dataframe_func is None:
            return None
        
        sheet_df:DataFrame = self.__get_sheet_dataframe_func()
        return str(sheet_df.iat[row,column]), [row,column]
    

    def __find_others_in_table(self, linked_text:LinkedText, parameter=None):
        linked_text_rows = {}
        if self.__get_sheet_dataframe_func is None:
            return linked_text_rows
        
        sheet_df:DataFrame = self.__get_sheet_dataframe_func()
        
        for indexes_id, target_text_link in linked_text.links.items():
            link = linked_text.given_text[target_text_link.given_text_id]
            
            if linked_text.axis == 0:  # Iterate over rows
                for index, _ in sheet_df.iterrows():
                    if index not in linked_text_rows:
                        linked_text_rows[index] = {}

                    if parameter:
                        if parameter not in linked_text_rows[index]:
                            linked_text_rows[index][parameter] = {}

                        linked_text_rows[index][parameter][indexes_id] = str(sheet_df.iat[index,link.roi[1]])
                    else:
                        linked_text_rows[index][indexes_id] = str(sheet_df.iat[index,link.roi[1]])
            else:  # Iterate over columns
                for index in range(sheet_df.shape[1]):
                    if index not in linked_text_rows:
                        linked_text_rows[index] = {}

                    if parameter:
                        if parameter not in linked_text_rows[index]:
                            linked_text_rows[index][parameter] = {}

                        linked_text_rows[index][parameter][indexes_id] = str(sheet_df.iat[link.roi[0], index])
                    else:
                        linked_text_rows[index][indexes_id] = str(sheet_df.iat[link.roi[0], index])
    
        return linked_text_rows
    

    def __find_other_tagnames_in_table(self):
        return self.__find_others_in_table(self.tagname)
    

    def __find_other_subobjects_in_table(self):
        return self.__find_others_in_table(self.subobject)
    

    def __find_other_parameters_in_table(self, parameter_name):
        return self.__find_others_in_table(self.parameters[parameter_name], parameter_name)
    
    

    def __build_other_linked_texts(self, linked_text_rows, parameter=None):
        
        for index, linked_text_row in linked_text_rows.items():
            character_differences = []

            new_linked_text = self.__build_linked_text_string(linked_text_row
                                                              ,self.tagname
                                                              ,index
                                                              ,character_differences)

            new_linked_text = self.__correct_link_text_indexes(
                                                            character_differences, 
                                                            new_linked_text
                                                            )
            if str(index) not in self.__found_tagname_links:
                self.__found_tagname_links[str(index)] = {}

            self.__found_tagname_links[str(index)]["tagname"] = new_linked_text


    def __build_other_parameters(self, linked_text_rows, parameter):
        
        for index, linked_text_row in linked_text_rows.items():
            character_differences = []

            try:
                new_linked_text = self.__build_linked_text_string(linked_text_row[parameter],
                                                                    self.parameters[parameter],
                                                                    index,
                                                                    character_differences)
            except LinkedTextMatchError:
                self.__found_parameter_links[str(index)] = None
                continue
            
            new_linked_text = self.__subobject_reftype_parameter_value_correction(new_linked_text,parameter)
            
            new_linked_text = self.__correct_link_text_indexes(
                                                            character_differences, 
                                                            new_linked_text
                                                            )
            
            if str(index) not in self.__found_parameter_links:
                self.__found_parameter_links[str(index)] = {}



            self.__found_parameter_links[str(index)][parameter] = new_linked_text


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

    def __copy_linked_text(self, linked_text:LinkedText,index, character_differences):


        linked_text = self.__correct_link_text_indexes(
                                                        character_differences, 
                                                        linked_text
                                                        )
        
        
        for _ , link in linked_text.links.items():
            if linked_text.axis:
                linked_text.given_text[link.given_text_id].roi[1] = index
            else:
                linked_text.given_text[link.given_text_id].roi[0] = index

    
        return linked_text


    def __correct_link_text_indexesf(self, character_differences, linked_text:LinkedText):
        corrected_indexes_links = {}
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



    def __build_linked_text_string(self, found_cell_texts, linked_text:LinkedText, index, character_differences):
        
        new_linked_text = copy.deepcopy(linked_text)
        
        for indexes_id, link in new_linked_text.links.items():
                
            given_text = linked_text.given_text[link.given_text_id]
            if new_linked_text.link_type == LinkType.SELECTOR:
                group = 0
            else:
                group = self.__get_regex_group(given_text.text,given_text.regex_string, link.given_text_indexes)
                if group is None:
                    raise ValueError('Group not found in regex string')
                
                self.remove_exact_range_from_indexes(new_linked_text, link.given_text_id, link.given_text_indexes)
            
            match = safe_regex.search(given_text.regex_string,found_cell_texts[indexes_id])
            if not match:
                if new_linked_text.link_type == LinkType.SELECTOR:
                    raise LinkedTextMatchError('No match found in cell text')
                continue
            sub_string = str(match.group(group))
            
            match_start = match.span(group)[0]
            given_text_indexes = [match_start,match_start+len(sub_string)]
            new_linked_text.links[indexes_id].given_text_indexes = given_text_indexes

            
            if new_linked_text.link_type == LinkType.SELECTOR:
                new_linked_text.given_text[link.given_text_id].key_and_ignore_indexes = []
                
            else:
                new_linked_text.given_text[link.given_text_id].key_and_ignore_indexes.append(given_text_indexes)

                try:
                    target_text_indexes = linked_text.links[indexes_id].target_text_indexes
                    new_linked_text.text = self.__replacer(new_linked_text.text
                                                ,sub_string
                                                ,list(target_text_indexes)
                                                ,character_differences=character_differences)
                except Exception as error:
                    print(error)
                    continue
                data = {
                    'index':target_text_indexes[1],
                    'difference':len(sub_string)-(target_text_indexes[1] - target_text_indexes[0])
                }
                character_differences.append(data)




            new_linked_text.given_text[link.given_text_id].text = found_cell_texts[indexes_id]
            if linked_text.axis:
                new_linked_text.given_text[link.given_text_id].roi[1] = int(index)
            else:
                new_linked_text.given_text[link.given_text_id].roi[0] = int(index)
            
            


        return new_linked_text
    

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
    


    def fully_linked_check(self):
        if not self.tagname.linked:
            raise Exception('Tagname not linked. Please link tagname first')
        
        if not self.parameters:
            raise Exception('No parameters added. Please add parameters first')
        
        for parameter_name in self.parameters:
            if not self.parameters[parameter_name].linked:
                raise Exception(f'{parameter_name} not linked. Please link {parameter_name} first')
            

    def has_given_text(self):
        parameter_given_text = False
        for parameter_name in self.parameters:
            if self.parameters[parameter_name].given_text:
                parameter_given_text = True
            

        if self.tagname.given_text or parameter_given_text:
            return True
        else:
            return False

    def is_linked(self):
        parameter_linked = False
        for parameter_name in self.parameters:
            if self.parameters[parameter_name].linked:
                parameter_linked = True
            

        if self.tagname.linked or parameter_linked:
            return True
        else:
            return False
        

    def is_fully_linked(self):
        parameter_linked = False
        for parameter_name in self.parameters:
            if self.parameters[parameter_name].linked:
                parameter_linked = True
            

        if self.tagname.linked and parameter_linked:
            return True
        else:
            return False
        
            
    def get_id(self):
        return self.__id
    
    def set_parameter_ref_type(self, parameter_name, reftype):
        self.parameters[parameter_name].reftype = reftype


    def setup_linking_callback_func(self, callback, doc_type):
        self.__linking_callback_func = callback



    def get_parameter_ref_type(self, parameter_name):
        if parameter_name in self.parameters:
            return self.parameters[parameter_name].reftype
        else:
            return 'immediate'
        

    
    def get_data(self):

        if self.__id is None:
            self.__id = str(uuid.uuid4())

        data = {
            'id' : self.__id,
            'tagname': self.tagname.dict(),
            'parameters': {k: v.dict() for k, v in self.parameters.items()}
        }

        if self.subobject:
            data['subobject'] = self.subobject.dict()


        data['text_relationship'] = self.__determine_tagname_parameter_text_relationship()

        # Get first given_text in tagname
        first_given_text = list(self.tagname.given_text.values())[0]
        data['path']= first_given_text.path
        data['pno'] = first_given_text.pno
        data['template_id'] = self.__id
        data['is_llm_generated'] = self.__is_llm_generated

        return data
    
    def __determine_tagname_parameter_text_relationship(self) -> TagnameParameterRelationship:
        
        if not self.tagname.linked:
            return TagnameParameterRelationship.UNDEFINED
        
        first_given_text = list(self.tagname.given_text.values())[0]

        if first_given_text.doc_type != Database.TEXT:
            return TagnameParameterRelationship.UNDEFINED
        
        if not self.parameters:
            return TagnameParameterRelationship.UNDEFINED
        
        if not all(parameter.linked for parameter in self.parameters.values()):
            return TagnameParameterRelationship.UNDEFINED
        
        # Determine relationship using only the first paramter 
        first_parameter = list(self.parameters.values())[0]
        first_parameter_given_text = list(first_parameter.given_text.values())[0]

        if self.__ranges_overlap(first_given_text.indexes, first_parameter_given_text.indexes):
            return TagnameParameterRelationship.IN_LINE

        if first_given_text.in_table and first_parameter_given_text.in_table:
            return TagnameParameterRelationship.IN_TABLE
        
        if first_parameter_given_text.in_list:
            return TagnameParameterRelationship.LIST_HEADER



    
    def __ranges_overlap(self,range1, range2):
        return range1[0] <= range2[1] and range2[0] <= range1[1]
    

    def is_llm_generated(self):
        return self.__is_llm_generated
        

    def set_data(self, data):
        self.__id = data['id']
        self.__is_llm_generated = data.get('is_llm_generated', False)
        self.tagname = self.__extract_linked_text(data['tagname'])
        self.parameters = {k: self.__extract_linked_text(v) for k, v in data['parameters'].items()}
        
        if 'subobject' in data:
            self.subobject = self.__extract_linked_text(data['subobject'])
        else:
            self.subobject = None

    def __extract_linked_text(self, data):


        linked_text = LinkedText(**data)

        if data['links'] == 'None':
            linked_text.links = None
        else:
            links_str = data['links'].replace('(inf,', '(float("inf"),').replace(', inf)', ', float("inf"))')
            linked_text.links = {k: TargetTextLink(**v) for k, v in eval(links_str).items()}


        if data['given_text'] == 'None':
            linked_text.given_text = None
        else:
            given_text_str = data['given_text'].replace('(inf,', '(float("inf"),').replace(', inf)', ', float("inf"))')
            linked_text.given_text = {k: GivenTextLink(**v) for k, v in eval(given_text_str).items()}

        return linked_text
        

    