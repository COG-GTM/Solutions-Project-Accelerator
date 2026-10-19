
import tkinter as tk
import threading
from PIL import Image, ImageTk, ImageDraw

from bin.gui_subobject_parameter_list_view import subparameter_cell_list_view
from bin.logic_acm_function_handler import acm_parameter_handler
from bin.logic_acm_parameter import acm_paramter
from bin.logic_internal_database import Database
from bin.logic_linked_text import Linked_Text
from bin.logic_profile import profile


try:
    from bin.gui_elements import expandable_list_canvas
    from bin.logic_acm_data_handler import ACM_Data_Handler
    from bin.gui_parameter_list_view import parameter_cell
    from bin.logic_acm_libraries_retrieval import get_library_file_path, acm_libraries_retrieval
    from bin.logic_acm_library_parser import acm_library_parser
except:
    from gui_elements import expandable_list_canvas
    from logic_acm_data_handler import ACM_Data_Handler
    from gui_parameter_list_view import parameter_cell
    from logic_acm_libraries_retrieval import get_library_file_path, acm_libraries_retrieval
    from logic_acm_library_parser import acm_library_parser


class expandable_list_approval_canvas(expandable_list_canvas):

    def __init__(self, placeholder, refresh_data_callback=None):
        self.__refresh_data_callback = refresh_data_callback
        super().__init__(placeholder,self.__refresh_data_callback)
        self.project_name = ''
        self.db:Database = None
        self.config:profile = None
        self.acm_data_handler:ACM_Data_Handler = None


    def show_bottom_approval_view(self):
        self.banner_handler.bottom_approval_view.show()
        self.banner_handler.bottom_approval_view.setup_callbacks(self.__on_reject,
                                                                 self.__on_accept,
                                                                 self.__on_accept_all,
                                                                 self.__on_discard_all)

    
    def __on_reject(self):
        for header_element in self.header_elements:
            self.elements[header_element]['element'].reject_selected_cell()

            if (self.elements[header_element]['element'].data_frame.empty 
                and self.__refresh_data_callback):
                self.__refresh_data_callback()

    def __on_accept(self):
        for header_element in self.header_elements:
            self.elements[header_element]['element'].accept_selected_cell()

            if (self.elements[header_element]['element'].data_frame.empty 
                and self.__refresh_data_callback):
                self.__refresh_data_callback()


    def __on_accept_all(self):
        self.banner_handler.bottom_approval_view.show_progress_bar()
        progress_func = self.banner_handler.bottom_approval_view.set_progress_info
        progress_divisions = [len(self.elements[header_element]['element'].data_frame) 
                                for header_element in self.header_elements]
        
        # Run the acceptance process in a separate thread
        def accept_all_thread():
            total = 0
            for i, header_element in enumerate(self.header_elements):
                current_division = progress_divisions[i]
                
                self.elements[header_element]['element'].accept_all_cells(progress_func, progress_divisions, total)
                total += current_division

            def func():
                # Hide progress bar and refresh data on main thread
                self.banner_handler.bottom_approval_view.hide_progress_bar()
                if self.__refresh_data_callback:
                    self.__refresh_data_callback()

            self.canvas.after(0, func)
        
        thread = threading.Thread(target=accept_all_thread)
        thread.daemon = True
        thread.start()


    def __on_discard_all(self):
        self.banner_handler.bottom_approval_view.show_progress_bar()
        progress_func = self.banner_handler.bottom_approval_view.set_progress_info
        progress_divisions = [len(self.elements[header_element]['element'].data_frame) 
                                for header_element in self.header_elements]
        
        # Run the discard process in a separate thread
        def discard_all_thread():
            total = 0
            for i, header_element in enumerate(self.header_elements):
                current_division = progress_divisions[i]
                
                self.elements[header_element]['element'].reject_all_cells(progress_func, progress_divisions, total)
                total += current_division

            def func():
                # Hide progress bar and refresh data on main thread
                self.banner_handler.bottom_approval_view.hide_progress_bar()
                if self.__refresh_data_callback:
                    self.__refresh_data_callback()

            self.canvas.after(0, func)
        
        thread = threading.Thread(target=discard_all_thread)
        thread.daemon = True
        thread.start()


    def accept_cells(self, cell_ids, accept=True):
        for header_element in self.header_elements:
            self.elements[header_element]['element'].accept_cells(cell_ids
                                                                ,self.project_name
                                                                ,self.db
                                                                ,self.config
                                                                ,self.acm_data_handler
                                                                ,accept)
            if (self.elements[header_element]['element'].data_frame.empty 
                and self.__refresh_data_callback):
                self.__refresh_data_callback()

        


    def insert_header(self,id, name, data_frame, cell_class):
        self.elements[id]= {
                            'id':id,
                            'name': name,
                            'height': 50,
                            'type':'header'
                            }
        
        self.elements[id]['element'] = expandable_list_approval_canvas_header(self.canvas, id,name, data_frame, cell_class, 
                                                                        self.configure_canvas, resize_callback = self.header_expansion
                                                                        ,cell_highlighted_callback=self.highlighted_cell
                                                                        ,cell_unhighlighted_callback=self.unhighlighted_cell)
        self.elements[id]['element'].setup_project(self.project_name,self.db,self.config)
        self.elements[id]['element'].setup_data_handler(self.acm_data_handler)
        self.elements[id]['element'].get_object_if_running_func(self.get_object_if_running)
        self.header_elements.append(id)


class expandable_list_approval_canvas_header:

    DEFAULT_CELL_HEIGHT = 80

    def __init__(self, canvas, id, name, data_frame, cell_class, configure_canvas, resize_callback
                    ,cell_highlighted_callback=None, cell_unhighlighted_callback=None):
        self.canvas = canvas
        self.configure_canvas = configure_canvas
        self.y = 0
        self.id = id
        self.name = name
        self.callback = resize_callback
        self.shown = False
        self.rect = None 
        self.title = None
        self.expanded_element = None
        self.highlighted_element = None
        self.nummber_of_items = None
        self.show_or_hide_image = None
        self.elements_created = False
        self.cell_class = cell_class
        self.data_frame = data_frame
        im_open = Image.new('RGBA', (15, 15), '#00000000')
        draw = ImageDraw.Draw(im_open)
        draw.line([(0, 4), (7, 11), (14, 4) ], fill=(150,150,150,255),width=2)
        im_close= im_open.rotate(90)
        self.__cell_pass_document_selection_subscription_func = None
        self.__document_selection_subscription = None
        self.__multi_select_start = ''
        self.img_open = ImageTk.PhotoImage(im_open)
        self.img_close = ImageTk.PhotoImage(im_close)
        self.elements = {}
        self.__db = None 
        self.__acm_data_handler = None
        self.__document_selected_func = None 
        self.__add_primary_progress_callback = None 
        self.__add_secondary_progress_callback = None 
        self.__add_background_task_callback = None 
        self.__remove_background_task_callback = None 
        self.__get_object_if_running_func = None
        self.__cell_highlighted_callback_func = cell_highlighted_callback
        self.__cell_unhighlighted_callback_func = cell_unhighlighted_callback
        self.__cells_to_highlight = []
        self.__next_cell_to_expand = None


    def reject_selected_cell(self):
        if self.expanded_element and self.expanded_element in self.elements:
            self.elements[self.expanded_element]["cell"].reject()
            self.elements[self.expanded_element]["cell"].delete()
            self.elements.pop(self.expanded_element)
            self.data_frame.drop(self.expanded_element, inplace=True)
        self.__expand_next_cell()

    
    
    def accept_selected_cell(self):
        if self.expanded_element and self.expanded_element in self.elements:
            self.elements[self.expanded_element]["cell"].accept()
            self.elements[self.expanded_element]["cell"].delete()
            self.elements.pop(self.expanded_element)
            self.data_frame.drop(self.expanded_element, inplace=True)
        self.__expand_next_cell()


    
    def accept_all_cells(self, progress_callback=None, progress_divisions=None,total=0):
        
        if not self.elements_created:
            self.__create_elements()

        local_count = 0
        for cell_id, _ in self.elements.items():
            self.elements[cell_id]["cell"].silent_accept()
            local_count += 1
            percentage = ((total + local_count) / sum(progress_divisions)) 
            progress_callback(percentage, f'Writing {self.name}')

        

    def reject_all_cells(self, progress_callback=None, progress_divisions=None,total=0):

        if not self.elements_created:
            self.__create_elements()
        
        local_count = 0
        for cell_id, _ in self.elements.items():
            self.elements[cell_id]["cell"].reject()
            local_count += 1
            percentage = ((total + local_count) / sum(progress_divisions)) 
            progress_callback(percentage, f'Discarding {self.name}')

        


    def accept_cells(self, cell_ids, project_name, db, config, acm_data_handler, accept=True):
        if not self.elements_created:
            self.__create_elements()

        for cell_id in cell_ids:
            if cell_id in self.elements:
                cell:expandable_approval_list_canvas_cell = self.elements[cell_id]["cell"]
                cell.setup_project(project_name,db,config)
                cell.setup_data_handler(acm_data_handler)
                if accept:
                    cell.silent_accept()
                else:
                    cell.reject()
                cell.delete()
                self.elements.pop(cell_id)
                self.data_frame.drop(cell_id, inplace=True)
                if self.expanded_element == cell_id:
                    self.expanded_element = None
                if self.highlighted_element == cell_id:
                    self.highlighted_element = None
        
        self.show_elements()


    def setup_data_handler(self, data_handler):
        self.__acm_data_handler = data_handler

    def document_selected_func(self, func):
        self.__document_selected_func = func


    def add_primary_progress_callback(self, func):
        self.__add_primary_progress_callback = func


    def add_secondary_progress_callback(self, func):
        self.__add_secondary_progress_callback = func
    

    def add_background_task_callback_func(self, func):
        self.__add_background_task_callback = func

    def remove_background_task_callback_func(self, func):
        self.__remove_background_task_callback = func

    def get_object_if_running_func(self, func):
        self.__get_object_if_running_func = func

    def setup_project(self, project_name, database, config):
        self.__project_name = project_name
        self.__db = database
        self.__config = config

    def pass_document_selection_subscription(self, subscription=None):
        if subscription != None:
            self.__document_selection_subscription = subscription
            if self.__cell_pass_document_selection_subscription_func:
                self.__cell_pass_document_selection_subscription_func(subscription)
            
        else:
            if self.__document_selection_subscription and self.__cell_pass_document_selection_subscription_func:
                self.__cell_pass_document_selection_subscription_func(self.__document_selection_subscription)
        


        
    
    def draw(self, y):
        self.y = y
        self.rect = self.canvas.create_rectangle(8, self.y, self.canvas.winfo_width(), self.y + 50, tags=('header',self.id),fill="#E3E3E3",outline="#E3E3E3")
        self.title = self.canvas.create_text(16,y + 16, text=self.name, anchor=tk.NW, tags=('header',self.id))
        self.nummber_of_items = self.canvas.create_text(self.canvas.winfo_width() - 40,y + 16, text=str(len(self.data_frame.index)), anchor=tk.NE, tags=('header',self.id))
        self.show_or_hide_image = self.canvas.create_image(self.canvas.winfo_width() - 8, y + 16, image=self.img_close, anchor = tk.NE, tags=('header',self.id))
       
        if not self.shown:
            self.canvas.itemconfigure(self.show_or_hide_image,image=self.img_close)
            self.remove_elements()
        else:
            self.canvas.itemconfigure(self.show_or_hide_image,image=self.img_open)
            self.redraw_elements()
            
    def redraw_elements(self):
        self.remove_elements()
        self.__cell_pass_document_selection_subscription_func = None
        y = self.y + 51
        cell_expanded = False
        self.__next_cell_to_expand = None
        for cell_id, _ in self.elements.items():
            cell_height = self.DEFAULT_CELL_HEIGHT
            cell_color = 'white'
            if cell_expanded:
                self.__next_cell_to_expand = cell_id
            cell_expanded = False
            if self.expanded_element:
                if self.expanded_element == cell_id:
                    if self.elements[cell_id]["cell"]:
                        cell_height = self.elements[cell_id]["cell"].cell_size()
                    else:
                        cell_height = 200
                    cell_color = '#FFFFFF'  
                    cell_expanded = True
            if self.elements[cell_id]["cell"]:
                self.elements[cell_id]["cell"].draw(y)
                if cell_expanded:
                    if self.__acm_data_handler:
                        self.elements[cell_id]["cell"].setup_data_handler(self.__acm_data_handler)
                    if self.__db:
                        self.elements[cell_id]["cell"].setup_project(self.__project_name,self.__db,self.__config)
                    self.elements[cell_id]["cell"].expand()
                    cell_height = self.elements[cell_id]["cell"].cell_size()
                    self.elements[cell_id]["cell"].document_selected_func(self.__document_selected_func)
                    self.elements[cell_id]["cell"].primary_progress_callback_func(self.__add_primary_progress_callback)
                    self.elements[cell_id]["cell"].secondary_progress_callback_func(self.__add_secondary_progress_callback)
                    self.elements[cell_id]["cell"].add_background_task_callback_func(self.__add_background_task_callback)
                    self.elements[cell_id]["cell"].remove_background_task_callback_func(self.__remove_background_task_callback)
                    self.__cell_pass_document_selection_subscription_func = self.elements[cell_id]["cell"].pass_document_selection_subscription_func
                    self.pass_document_selection_subscription()
                    self.elements[cell_id]["cell"].setup_configure_canvas(self.configure_canvas)
           
            self.elements[cell_id]["line"] = self.canvas.create_line(16, y + cell_height,  self.canvas.winfo_width(), y + cell_height, fill="#E3E3E3",width=2)

            y = y + cell_height
        return (self.y , y)
            
    def remove_elements(self):
        for key, values in self.elements.items():
            if "line" in values:
                #self.canvas.delete(values['rect'])
                self.canvas.delete(values['line'])
                if values['cell']:
                    values['cell'].delete()
                #del self.elements[key]['rect'] 
                del self.elements[key]['line'] 
    
    def delete_on_canvas(self):
        if self.rect:
            self.canvas.delete(self.rect)
            
        if self.title:   
            self.canvas.delete(self.title)
        
        if self.show_or_hide_image:
            self.canvas.delete(self.show_or_hide_image)
            
        if self.nummber_of_items:   
            self.canvas.delete(self.nummber_of_items)
        
    
    def show_or_hide(self, hide=None):
        self.canvas.config(cursor="wait")
        if not self.elements_created:
            self.__create_elements()
        
        if hide is None:
            hide = self.shown

        if  hide:
            self.canvas.itemconfigure(self.show_or_hide_image,image=self.img_close)
            self.shown = False
            self.expanded_element = None
            self.hide_elements()
        else:
            self.canvas.itemconfigure(self.show_or_hide_image,image=self.img_open)
            self.shown = True 
            self.show_elements()
        self.canvas.config(cursor="")
        return self.shown

    def __create_elements(self):
        for sub_index, row in self.data_frame.iterrows():
            self.insert_element( str(sub_index)
                                    , row['Name']
                                    , row['ChangeUser']
                                    , row['Description']
                                    , row['Parameter']
                                    , row['Subparameter']
                                    ,self.cell_class)
        self.elements_created = True


    def select_cell_list(self, cell_list):

        selected_cells = []

        # Check to see if cells already exist
        in_memory_cells = list(set(cell_list).intersection(list(self.elements.keys())))

        for cell_id in list(set(in_memory_cells)):
            selected_cells.append(self.elements[cell_id]["cell"])

        # Filter the list to only include existing index labels
        not_in_memory_cells = [label for label in cell_list if label in self.data_frame.index]

        # Select rows using the filtered list of index labels
        selected_rows = self.data_frame.loc[list(set(not_in_memory_cells))]

        for sub_index, row in selected_rows.iterrows():
            if (self.cell_class and str(sub_index) not in in_memory_cells and
                self.__get_object_if_running_func(str(sub_index)) is None):
                    called_cell_class = self.cell_class(self.canvas,self.id, str(sub_index)
                                                    ,name=row['Name']
                                                    ,username=row['ChangeUser']
                                                    ,description=row['Description']
                                                    ,cell_highlighted_callback=self.__highlight_element
                                                    ,cell_unhighlighted_callback=self.__unhighlight_element)
                    
                    selected_cells.append(called_cell_class)

        return selected_cells
                    
         
    def insert_element(self, cell_id, name, user, description, parameter, subparameter, cell_class):
        called_cell_class = None 
        if cell_class:
            if self.__get_object_if_running_func(cell_id) is not None:
                called_cell_class = self.__get_object_if_running_func(cell_id)
            else:
                called_cell_class = cell_class(self.canvas,self.id, cell_id
                                                    ,name=name
                                                    ,username=user
                                                    ,description=description
                                                    ,parameter=parameter
                                                    ,subparameter=subparameter
                                                    ,cell_highlighted_callback=self.__highlight_element
                                                    ,cell_unhighlighted_callback=self.__unhighlight_element)
                if self.__acm_data_handler:
                    called_cell_class.setup_data_handler(self.__acm_data_handler)
                if self.__db:
                    called_cell_class.setup_project(self.__project_name,self.__db,self.__config)
        
        self.elements[cell_id] = {
                                "name":name,
                                "user":user,
                                "cell":called_cell_class,
                                "type":'cell'
                            }
        if self.shown:
            self.show_elements()

            
    def expand_element(self,element_id):
        self.expanded_element = element_id
        self.show_elements()

    
    def __expand_next_cell(self):
        if self.__next_cell_to_expand is None:
            self.expanded_element = None
            return 
        
        self.expanded_element = self.__next_cell_to_expand
        self.show_elements()


    def multi_select(self, cell_id):
        self.clear_multi_select(False)
        if not self.__multi_select_start: 
            self.__multi_select_start = cell_id
            self.elements[cell_id]["cell"].multi_select_highlight()
            return

        cell_key_list = list(self.elements.keys())

        start = cell_key_list.index(self.__multi_select_start)
        end = cell_key_list.index(cell_id)

        if start < end:
            self.__cells_to_highlight = cell_key_list[start: end + 1]
        else:
            self.__cells_to_highlight = cell_key_list[end: start + 1]
        
        for cell_id in self.__cells_to_highlight:
            cell = self.elements[cell_id]["cell"]
            cell.multi_select_highlight()
            if self.__acm_data_handler:
                cell.setup_data_handler(self.__acm_data_handler)
            if self.__db:
                cell.setup_project(self.__project_name,self.__db,self.__config)


    def single_multi_select(self, cell_id):
        self.__cells_to_highlight.append(cell_id)
        cell = self.elements[cell_id]["cell"]
        cell.multi_select_highlight()
        if self.__acm_data_handler:
            cell.setup_data_handler(self.__acm_data_handler)
        if self.__db:
            cell.setup_project(self.__project_name,self.__db,self.__config)


    def get_multi_highlighted_cells(self):
        
        cell_ids = []
        cells = []
        cell_names = []

        for cell_id in self.__cells_to_highlight:
            cell_ids.append(cell_id)
            cells.append(self.elements[cell_id]["cell"])
            cell_names.append(self.elements[cell_id]["name"])

        return cell_names, cell_ids, cells


    def get_cells_to_highlight(self):
        return self.__cells_to_highlight


    def clear_multi_select(self, remove_start=True):
        if remove_start:
            if self.__multi_select_start in self.elements:
                self.elements[self.__multi_select_start]["cell"].clear_multi_select_highlight()

            self.__multi_select_start = ''
        for cell in self.__cells_to_highlight:
            self.elements[cell]["cell"].clear_multi_select_highlight()


        
    def __highlight_element(self,name,cell_id,group_id,cell):
        if self.__cell_highlighted_callback_func:
            self.__cell_highlighted_callback_func(name,cell_id,group_id,cell)
        if self.__acm_data_handler:
            cell.setup_data_handler(self.__acm_data_handler)
        if self.__db:
            cell.setup_project(self.__project_name,self.__db,self.__config)
    
    def __unhighlight_element(self, name,cell_id,group_id,cell):    
        if self.__cell_unhighlighted_callback_func:
            self.__cell_unhighlighted_callback_func(name,cell_id,group_id,cell)

    def shrink_elements(self):
        self.expanded_element = None
        if self.shown:
            self.show_elements()
        else:
            self.hide_elements()
     
    def show_elements(self):
        y0, y1 = self.redraw_elements()
        self.callback_size_change(y0, y1) 
                            
                            
    def hide_elements(self): 
        self.remove_elements()
        self.callback_size_change(self.y, self.y + 50)   

    def hide_entry_widgets(self):
        if self.expanded_element:
            if self.expanded_element in self.elements:
                self.elements[self.expanded_element]["cell"].hide_entry_widgets()
            else:
                self.expanded_element = None
        self.shown = False
        
    def show_entry_widgets(self):
        if self.expanded_element:
            if self.expanded_element in self.elements:
                self.elements[self.expanded_element]["cell"].show_entry_widgets()
            else:
                self.expanded_element = None
        
                
    def callback_size_change(self, y0 ,y1):
        if self.callback:
            self.callback(self.id, y0, y1 )
                

class expandable_approval_list_canvas_cell:
    def __init__(self, canvas: expandable_list_canvas, group_id, cell_id, tool_frame=None, name='',username='',description='',parameter='',subparameter=''
                    ,db=None,cell_highlighted_callback=None, cell_unhighlighted_callback=None,delete_from_database_callback=None):
        self.canvas = canvas
        self.configure_canvas = None
        self.y = 0
        self.group_id = group_id
        self.cell_id = cell_id
        self.name = name
        self.description = description
        self.subobject_or_parameter_name = parameter
        self.subparameter_name = subparameter
        self.selection_rect_image = None
        self.name_label = None 
        self.parameter_name_label = None 
        self.divider = None 
        self.rect = None
        self.tool_frame = tool_frame
        self.expanded = False
        self.tags = ('cell',self.group_id, self.cell_id )
        self.pass_document_selection_subscription_func = self.document_selection_subscription 
        self.__document_selected_func = None
        self.acm_data_handler = None
        self.__multi_selected = False
        self.__cell_highlighted_callback_func = cell_highlighted_callback
        self.__cell_unhighlighted_callback_func = cell_unhighlighted_callback
        self.__delete_from_database_func = delete_from_database_callback
        self.__db:Database = db
        self.__parameter_cell = None
        self.__subparameter_cell_list_view = None
        self.__library_parser = None
        self.__pararmeter_data = None
        self.__move_to_roi_func = None
        self.object_id = None
        self.__document_selection_subscription_selected = None
        self.__document_selection_subscription_kwargs = None

    
    def __redraw_callback(self):
        pass


    def __go_to_callback(self, roi_uid,pno,path,doc_type=Database.DRAWING):
        self.__go_to_roi_uid = roi_uid
        self.__go_to_pno = pno

        self.__go_to_document_path(path,doc_type)
        self.__move_to_roi()


    def document_selection_subscription(self, subscription):
        subscription(self.__document_selection_subscription_callback, 
                        None,
                        None,
                        None)
        
        
    def __document_selection_subscription_callback(self, selected , **kwargs): 
        """ Sets up the communication between the object and the document viewer panel"""
        if kwargs and 'move_to_roi_func' in kwargs:  
            # Get the function callback from the document viewer panel 
            # responsible for moving the document viewer to the requested location
            self.__move_to_roi_func = kwargs.get('move_to_roi_func',None)

        self.__document_selection_subscription_selected = selected
        self.__document_selection_subscription_kwargs = kwargs


        if self.__parameter_cell:
            self.__parameter_cell.document_selection_subscription(self.__document_selection_subscription_selected
                                                                            ,**self.__document_selection_subscription_kwargs)

        if self.__subparameter_cell_list_view:
            self.__subparameter_cell_list_view.document_selection_subscription(self.__document_selection_subscription_selected
                                                                            ,**self.__document_selection_subscription_kwargs)

    def __move_to_roi(self):    
        if self.__move_to_roi_func and self.__go_to_roi_uid and self.__go_to_pno is not None:
            self.__move_to_roi_func(self.__go_to_roi_uid,self.__go_to_pno)
            self.__go_to_roi_uid = None 
            self.__go_to_pno = None 
        
    def __go_to_document_path(self, path, doc_type=Database.DRAWING):
        func = self.get_document_selected_func()
        func(path,doc_type)
   
    def expand(self):
        self.canvas.config(cursor="wait")

        if self.__library_parser is None:
            self.__parse_library_file(self.__project_name,self.acm_data_handler)

        if not self.subparameter_name:
            
            if self.__pararmeter_data is None:
                self.__pararmeter_data = self.__library_parser.get_parameters()

            if self.object_id is None:
                self.object_id = self.acm_data_handler.get_object_id(self.name)

            data = {
                'properties': self.__pararmeter_data[self.subobject_or_parameter_name],
                'value': ''
            }

            if self.__parameter_cell is None:
                self.__parameter_cell = parameter_cell(self.canvas
                                                    ,self.acm_data_handler
                                                    ,self.object_id
                                                    ,data
                                                    ,self.__project_name
                                                    ,tagname=self.name
                                                    ,goto_callback=self.__go_to_callback
                                                    ,db=self.__db
                                                    ,redraw_callback=self.__redraw_callback
                                                    ,config=self.__config)
                data = self.__db.get_unapproved_text_link_by_id(self.cell_id)
                self.__parameter_cell.setup_linked_text(data)
            self.__parameter_cell.draw(0, self.y + 78)
            if self.__document_selection_subscription_kwargs:
                self.__parameter_cell.document_selection_subscription(self.__document_selection_subscription_selected
                                                                            ,**self.__document_selection_subscription_kwargs)
                self.__parameter_cell.setup_regex_on_viewer()
        else:

            subobject_parameters = self.__library_parser.get_subobject_parameters(self.subobject_or_parameter_name)
            self.__subparameter_cell_list_view = subparameter_cell_list_view(self.canvas, self.object_id
                                                                                    ,None
                                                                                    ,self.acm_data_handler
                                                                                    ,self.__db
                                                                                    ,self.__project_name
                                                                                    , 0
                                                                                    , 0
                                                                                    ,parameters=subobject_parameters
                                                                                    ,tagname=self.name
                                                                                    ,subobject=self.subobject_or_parameter_name
                                                                                    ,goto_callback=self.__go_to_callback
                                                                                    ,allow_adding_subparameters=False
                                                                                    ,draw_add_subparameters=False
                                                                                    ,config=self.__config)
            data = self.__db.get_unapproved_text_link_by_id(self.cell_id)
            self.__subparameter_cell_list_view.setup_linked_text(data)
            self.__subparameter_cell_list_view.draw(0, self.y + 78)
            if self.__document_selection_subscription_kwargs:
                self.__subparameter_cell_list_view.document_selection_subscription(self.__document_selection_subscription_selected
                                                                            ,**self.__document_selection_subscription_kwargs)
                self.__subparameter_cell_list_view.setup_regex_on_viewer()



        self.expanded = True
        self.canvas.config(cursor="")




    def accept(self):
        if self.__parameter_cell:
            self.__parameter_cell.accept()
        
        if self.__subparameter_cell_list_view:
            self.__subparameter_cell_list_view.accept()


    def silent_accept(self):
        data = self.__db.get_unapproved_text_link_by_id(self.cell_id)

        if not data:
            return
        
        data = dict(data)

        if 'subobject' not in data:
            self.__parameter_silent_accept(data)
        else:
            self.__subobject_silent_accept(data)


    def reject(self):
        data = self.__db.get_unapproved_text_link_by_id(self.cell_id)

        if not data:
            return
        
        data = dict(data)
        
        self.__db.save_rejected_text_link(data)


    def __parameter_silent_accept(self, data):
        self.object_id = self.acm_data_handler.get_object_id(self.name)
        self.__parse_library_file(self.__project_name,self.acm_data_handler)
        parameter_data = self.__library_parser.get_parameters()[self.subobject_or_parameter_name]
        acm_parameter = acm_paramter(self.object_id,self.acm_data_handler,parameter_data,self.__project_name)
        
        
        parameter = list(data['parameters'].keys())[0]
        parameter_data = data['parameters'][parameter]
        acm_parameter.write_unknown_referenced_values(parameter
                                                     ,parameter_data['text'])
        if data['is_llm_generated']:
            data['is_llm_generated'] = None
            self.__db.save_linked_text_regex(data)
        self.__db.save_approved_text_link(data)

        


    def __subobject_silent_accept(self, data):
        self.__parse_library_file(self.__project_name,self.acm_data_handler)
        subobjects = self.__library_parser.get_all_subobjects()
        subobject_parameters = self.__library_parser.get_subobject_parameters(self.subobject_or_parameter_name)
        object_id = self.acm_data_handler.get_object_id(self.name)
        subobject_parameters['Index']['Max'] = acm_parameter_handler(subobject_parameters['Index']['Max']
                            ,object_id
                            ,self.acm_data_handler
                            ,self.__project_name)
        subobject_name = self.acm_data_handler.create_subobject(object_id,subobjects[self.subobject_or_parameter_name], subobject_parameters)
        subobject_id = self.acm_data_handler.get_subobject_id(subobject_name,object_id)
        
        
        subparameters = list(data['parameters'].keys())

        for subparameter in subparameters:
            
            subparameter_data = subobject_parameters[subparameter]
            acm_parameter = acm_paramter(self.object_id,self.acm_data_handler,subparameter_data,self.__project_name)
        
            acm_parameter.write_unknown_referenced_values(subparameter
                                                        ,data['parameters'][subparameter]['text']
                                                        ,subobject_id)
        
        data['subobject_name'] = subobject_name

        if data['is_llm_generated']:
            data['is_llm_generated'] = None
            self.__db.save_linked_text_regex(data)
        self.__db.save_approved_text_link(data)




    def __parse_library_file(self, project_name,acm_data_handler:ACM_Data_Handler):
        library_id = acm_data_handler.get_object_library_id(self.name)
        library_file_path = get_library_file_path(library_id,project_name)
        if not library_file_path:
            projects_df = acm_data_handler.get_all_projects()
            acm_project_name = projects_df.loc[int(acm_data_handler.get_project_id())]['Name']
            acm_libraries_retrieval(project_name, acm_project_name,threaded=False)
            library_file_path = get_library_file_path(library_id,project_name)
        self.__library_parser = acm_library_parser(library_file_path)


    def add_background_task_callback_func(self, func):
        self.add_background_task_callback = func

    def remove_background_task_callback_func(self, func):
        self.remove_background_task_callback = func
        
    def document_selected_func(self, func):
        self.__document_selected_func = func 

    def get_document_selected_func(self):
        return self.__document_selected_func
    
    def delete(self):
        if self.__parameter_cell:
            self.__parameter_cell.hide()
        if self.__subparameter_cell_list_view:
            self.__subparameter_cell_list_view.hide()
        self.template_delete()
        self.expanded = False

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
        self.configure_canvas = canvas

    
    def hide_entry_widgets(self):
        
        if self.__parameter_cell:
            self.__parameter_cell.hide_entry_widgets()

        if self.__subparameter_cell_list_view:
            self.__subparameter_cell_list_view.hide_entry_widgets()


    def show_entry_widgets(self):
        if self.__parameter_cell:
            self.__parameter_cell.show_entry_widgets()

        
    def draw(self, y):
        self.y = y 
        self.rect = self.canvas.create_rectangle(16, y, self.canvas.winfo_width(), y + 78,tags=('cell',self.group_id, self.cell_id ), fill='#FFFFFF',width=0)
        self.name_label = self.canvas.create_text(20,y + 12, text=self.name, font=('Arial',13,'bold'), anchor=tk.NW, tags=self.tags, fill="#555555")
        self.divider = self.canvas.create_line(108, y + 32, 108, y + 50, fill='#D5D5D5', width=2)
        if self.subparameter_name != '':
            parameter_text = 'Subobject'
        else:
            parameter_text = 'Parameter'
        self.parameter_label = self.canvas.create_text(20,y + 30, text=parameter_text, font=('Arial',12,'bold'), anchor=tk.NW, tags=self.tags, fill="#555555")
        self.parameter_name_label = self.canvas.create_text(116,y + 32, text=self.subobject_or_parameter_name, font=('Arial',10,'normal'), anchor=tk.NW, tags=self.tags, fill="#555555")
        
        self.parameter_value_label = self.canvas.create_text(20,y + 52, text=self.description, font=('Arial',10,'normal'), anchor=tk.NW, tags=self.tags, fill="#6F6F6F")
        
        self.selection_rect_image = self.canvas.create_rectangle(16, y, self.canvas.winfo_width(), y + 78,tags=('cell',self.group_id, self.cell_id ), fill='',width=0)
        self.canvas.tag_bind(self.selection_rect_image , '<Enter>', lambda event:self.highlight_element(event))
        self.canvas.tag_bind(self.selection_rect_image , '<Leave>', lambda event:self.unhighlight_element(event))
        
    
    def primary_progress_callback_func(self, func):
        self.add_primary_running_task = func   


    def secondary_progress_callback_func(self, func):
        self.add_secondary_running_task = func

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


    def cell_size(self):
        if self.__subparameter_cell_list_view:
            return self.__subparameter_cell_list_view.cell_size()
        
        if self.__parameter_cell:
            return self.__parameter_cell.cell_size()
    
    
            
    def template_delete(self):
        if self.rect:
            self.canvas.delete(self.rect)
            self.canvas.delete(self.name_label)
            self.canvas.delete(self.divider)
            self.canvas.delete(self.parameter_label)
            self.canvas.delete(self.parameter_value_label)
            self.canvas.delete(self.parameter_name_label)
            self.canvas.delete(self.selection_rect_image)
        
   
    def fit_description_in_mutiline(self):

        description_bounds = self.canvas.bbox(self.description_label) 

        if description_bounds is None:
            return

        if (description_bounds[2] - description_bounds[0]) < (self.canvas.winfo_width()/2 - 8) or self.canvas.winfo_width() <= 0:
            return

        y = self.y
        
        second_line_substring = 0 
        split = self.subobject_or_parameter_name.split(" ")
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


if __name__ == "__main__":
    root = tk.Tk()
    canvas = tk.Canvas(root)
    canvas.grid()
    canvas.config(background='white', highlightthickness = 0)
    a = expandable_approval_list_canvas_cell(canvas,"0","0", name="AI00741", parameter_name="Cfg_HiHiLim", parameter_value='4.5')
    expanded = False
    
    def redraw(event):
        global a 
        a.draw(0)
        
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

    root.mainloop()
    