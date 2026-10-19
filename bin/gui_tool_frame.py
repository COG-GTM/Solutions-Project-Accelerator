
import uuid
import pandas as pd
from re import search
from bin.gui_approval_cells import expandable_approval_list_canvas_cell, expandable_list_approval_canvas
from bin.logic_acm_libraries_retrieval import acm_libraries_retrieval
from bin.logic_background_tasks_handler import background_tasks_handler
from bin.logic_profile import profile
import tkinter as tk               
from tkinter import font  as tkfont
import numpy as np
import logging

from pandas.core.frame import DataFrame
try:
    from .gui_elements import *
    from .gui_base64_icons import *
    from .gui_tool_cells import *
    from .logic_acm_data_handler import ACM_Data_Handler
except ImportError as error:
    from gui_elements import *
    from gui_base64_icons import *
    from gui_tool_cells import *
    from logic_acm_data_handler import ACM_Data_Handler



class tool_frame(tk.Frame):

    SORT_OPTIONS = {
        'tags_page' : ['Catalog'],
        'graphics_page' : ['Page'],
        'displays_page' : ['Page'],
        'approvals_page' : ['Catalog', 'Page']
    }

    def __init__(self,master, canvas_callback=None, show_sort_filter_callback=None,sort_by_options_callback=None
                 ,page_changed_callback=None, **kwargs):
        tk.Frame.__init__(self,master, **kwargs)
        

        self.title_font = tkfont.Font(family='Helvetica', size=18, weight="bold", slant="italic")
        
        # the container is where we'll stack a bunch of frames
        # on top of each other, then the one we want visible
        # will be raised above the others
        self.pack(side="top", fill="both", expand=True)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.canvas = None
        self.canvas_callback = canvas_callback
        self.sort_by_options_callback = sort_by_options_callback 
        self.show_sort_filter_callback = show_sort_filter_callback
        self.page_changed_callback = page_changed_callback
        self.remove_highlight_linked_text = None
        self.background_tasks = background_tasks_handler()

        self.frames = {}
        self.canvases = {}
        for F in (tags_page, graphics_page,
                  displays_page, approvals_page, configure_page):
            page_name = F.__name__
            frame = F(parent=self, controller=self)
            self.frames[page_name] = frame
            self.canvases[page_name] = frame.canvas

            # put all of the pages in the same location;
            # the one on the top of the stacking order
            # will be the one that is visible.
            frame.grid(row=0, column=0, sticky="nsew")
        self.__pass_down_configure_frame()
        self.shown_page = ""
        self.show_frame("tags_page")


    def set_roi_refresher(self, func):
        for page, frame in self.frames.items():
            if page != configure_page.__name__:
                frame.set_roi_refresher(func)


    def document_selected_func(self, func):
        for page, canvas in self.canvases.items():
            if page != configure_page.__name__:
                canvas.document_selected_func(func)

    def sheet_selected_func(self, func):
        for page, canvas in self.canvases.items():
            if page != configure_page.__name__:
                canvas.document_selected_func(func)

    def sort_by(self, index):
        if type(self.frame) == configure_page:
            return

        sort_type = self.SORT_OPTIONS[type(self.frame).__name__][int(index)]
        self.frame.set_sort_by(sort_type)
    

    def __pass_down_configure_frame(self):
        for page, canvas in self.canvases.items():
            if page != configure_page.__name__:
                canvas.setup_configure_canvas(self.canvases[configure_page.__name__])

    def pass_documnent_selection_subscription(self, subscription):
        subscription(self.document_selection_subscription_callback,None,None,None,None,self.refresh_tool_frames,self.show_cell_link
                     ,pending_linked_text_action_callback=self.approval_view_accept_cells)
        for page, canvas in self.canvases.items():
            if page != configure_page.__name__:
                canvas.pass_document_selection_subscription(subscription)


    def document_selection_subscription_callback(self,_,**kwargs):
        self.remove_highlight_linked_text = kwargs.get('remove_highlight_linked_text',None)


    def refresh_tool_frames(self):
        for page, frame in self.frames.items():
            if page != configure_page.__name__:
                frame.refresh()


    def show_cell_link(self, cell_object, linked_text_type=None, prediction='', callback=None):
        if type(cell_object)==expandable_list_canvas_control_module_cell:
            self.show_frame("tags_page")
            self.frames["tags_page"].show_cell(cell_object)
            
        elif type(cell_object)==expandable_list_canvas_static_graphic_cell:
            self.show_frame("graphics_page")
            self.frames["graphics_page"].show_cell(cell_object)
            
        elif type(cell_object)==expandable_list_canvas_hmi_display_cell:
            self.show_frame("displays_page")
            self.frames["displays_page"].show_cell(cell_object)

        elif type(cell_object)==list and cell_object and linked_text_type == 'unapproved_linked_text':
            self.show_frame("approvals_page")
            self.frames["approvals_page"].show_cell(cell_object)

        elif type(cell_object)==list and cell_object and linked_text_type == 'approved_linked_text':
            self.show_frame("tags_page")
            self.frames["tags_page"].show_linked_text(cell_object)

        elif linked_text_type == 'tagname' and cell_object:
            self.show_frame("tags_page")
            self.frames["tags_page"].show_control_module(cell_object)

        elif linked_text_type == 'new_parameter':
            self.show_frame("tags_page")
            self.frames["tags_page"].show_add_parameter_view_with_prediction(cell_object, prediction, callback)

        elif linked_text_type == 'new_subobject':
            self.show_frame("tags_page")
            self.frames["tags_page"].show_add_subobject_view_with_prediction(cell_object, prediction, callback)


    def approval_view_accept_cells(self, cell_ids, accept=True):
        if self.shown_page == 'approvals_page':
            self.canvases["approvals_page"].accept_cells(cell_ids, accept)
        else:
            self.frames["approvals_page"].refresh()
            self.canvases["approvals_page"].accept_cells(cell_ids, accept)

            


    def set_data_handler(self, data_handler):
        self.__acm_data_handler = data_handler
        self.frames["tags_page"].set_data_handler(self.__acm_data_handler)
        self.frames["displays_page"].set_data_handler(self.__acm_data_handler)
        self.frames["approvals_page"].set_data_handler(self.__acm_data_handler)
        

    def run_search(self, string):
        self.frames["tags_page"].run_search(string)
        self.frames["displays_page"].run_search(string)
        self.frames["graphics_page"].run_search(string)


    def define_project(self, project_name, database, config):
        self.__project_name = project_name
        self.__db = database
        self.__config = config
        self.frames["tags_page"].set_project_data(self.__db, self.__project_name)
        self.frames["graphics_page"].set_db(self.__db)
        self.frames["displays_page"].set_db(self.__db)
        self.frames["approvals_page"].set_db(self.__db)
        for page, canvas in self.canvases.items():
            if page != configure_page.__name__:
                canvas.setup_project(self.__project_name,self.__db,self.__config)

    

    def show_frame(self, page_name):
        '''Show a frame for the given page name'''

        if self.shown_page == 'configure_page':
            self.canvases['configure_page'].delete(tk.ALL)
            self.canvases['configure_page'].unbind('<Configure>')

            if self.remove_highlight_linked_text:
                self.remove_highlight_linked_text()

        self.frame = self.frames[page_name]
        if not page_name == 'configure_page':
            self.previously_shown_frame = page_name
            # Keep the tool side buttons in sync when a page is raised programmatically
            if self.page_changed_callback:
                self.page_changed_callback(page_name)
            self.show_sort_filter_callback(True)
        else:
            self.show_sort_filter_callback(False)
        self.frame.tkraise()
        self.hide_shown_canvas_entry_widgets()
        self.canvas = self.canvases[page_name]
        self.show_shown_canvas_entry_widgets()
        if self.canvas_callback:
            self.canvas_callback(self.canvas)
        self.shown_page = page_name
        if page_name == 'configure_page':
            return 
        
        if page_name == 'approvals_page':
            self.frame.refresh()
        
        if self.sort_by_options_callback:
            self.sort_by_options_callback(self.SORT_OPTIONS[page_name])


    def get_shown_canvas(self):
        return self.canvas, self.shown_page

            
    def hide_shown_canvas_entry_widgets(self):
        if self.canvas and type(self.canvas) is not tk.Canvas:
            self.canvas.hide_entry_widget_for_expanded_cell()
        elif self.canvas and type(self.canvas) is tk.Canvas:
            self.canvas.delete(tk.ALL)
    
    def show_shown_canvas_entry_widgets(self):
        if self.canvas and type(self.canvas) is not tk.Canvas:
            self.canvas.show_entry_widget_for_expanded_cell()
        
    
        
    def show_configure_frame(self):
        self.show_frame("configure_page")

    def get_configure_canvas(self):
        return self.canvases[configure_page.__name__]

    def show_custom_message(self, title, message, image):
        self.frames['configure_page'].show_message(title, message, image)

    def show_underconstruction(self):
        self.frames['configure_page'].show_message('Under Construction','Coming soon in later version',under_construction_image)
        
        
    def back_to_main_tools(self, _=None, __=None):
        if self.remove_highlight_linked_text:
            try:
                self.remove_highlight_linked_text()
            except Exception as e:
                logging.error(f"Error removing highlight: {str(e)}")
        self.canvases['configure_page'].delete(tk.ALL)
        self.canvases['configure_page'].unbind('<Configure>')
        self.show_frame(self.previously_shown_frame)


    def reset(self):
        self.back_to_main_tools()
        self.background_tasks = background_tasks_handler()
        self.frames["tags_page"].reset()
        self.frames["displays_page"].reset_data_frames()
        self.frames["graphics_page"].reset_data_frames()
        for page, canvas in self.canvases.items():
            if page != configure_page.__name__:
                canvas.reset()
                canvas.redraw()


class tags_page(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.canvas = expandable_list_canvas(self, self.refresh)
        self.canvas.set_canvas_name('Control Modules')
        self.canvas.pack(side="top", fill="both", pady=0, expand=True)
        self.search_string = ''
        self.__db_to_db_mapping = None
        self.__acm_data_handler = None
        self.__acm_objects_df_filtered = DataFrame()
        self.canvas.show_message('Not connected to ACM',
                                        'Go to File > Connect Database to connect an ACM database.',
                                        error_image)
        self.canvas.popup_menu(self.popup_menu)
        
        self.__db:Database = None
        self.__project_name = None
        self.__sort_by_selection = 'Catalog'
        self.__initialize_dataframe()
        self.__selected_cell_object = None 
        self.__multi_select = False
        self.__new_undefined_object_name = "" 
        self.__refresh_roi_func = None



    def __initialize_dataframe(self):
        d = {'id':[],'Name': [],'Type': [],'Page': [], 'ChangeUser': [], 'Description': [], 'IsLinked': []}
        self.__df = pd.DataFrame(data=d)
        self.__searched_df = self.__df
        self.__count = 0

    def popup_menu(self, event):
        """ Popup menu """
        _, selected_cell_id, self.__selected_cell_object, self.__multi_select = self.canvas.get_highlighted_cell()
        if selected_cell_id:
            state = tk.ACTIVE
        else:
            state = tk.DISABLED
        self.menu = tk.Menu(self.canvas.canvas, tearoff=0)
        self.menu.add_command(label='Add New', command=self.__add_new)
        self.menu.add_command(label='Refresh', command=self.__refresh_all_data)
        self.menu.add_separator()
        self.menu.add_command(label='Delete', command=self.__delete_element, accelerator=u'Delete',state=state)
        self.menu.post(event.x_root, event.y_root)  # show popup menu

    def show_cell(self, cell:expandable_list_canvas_control_module_cell):
        group_id = cell.group_id
        cell_id = cell.cell_id
        self.canvas.show_canvas_tag(group_id, cell_id)


    def show_linked_text(self, linked_text_id):
        self.canvas.show_linked_text(linked_text_id)

    
    def show_control_module(self, tagname):
        self.canvas.show_control_module(tagname)

    
    def show_add_parameter_view_with_prediction(self, text, prediction='', callback=None):
        self.canvas.show_add_parameter_view_with_prediction(text, prediction, callback)

    
    def show_add_subobject_view_with_prediction(self, text, prediction='', callback=None):
        self.canvas.show_add_subobject_view_with_prediction(text, prediction, callback)


    def set_project_data(self, db, project_name):
        self.__db = db
        self.__project_name = project_name
        self.__refresh_data()


    def __refresh_all_data(self):
        if self.__acm_data_handler is None:
            self.__refresh_data()
            return
        acm_project_name = self.__acm_data_handler.get_project_name()
        if acm_project_name:
            acm_libraries_retrieval(self.__project_name, acm_project_name)
        self.__acm_data_handler.refresh_all_data()
        self.__refresh_data()


    def refresh(self):
        self.__refresh_data()

    def __refresh_data(self):
        
        self.__get_data()
        self.__run_search()
        self.__draw_elements()


    def __get_data(self):
        self.__initialize_dataframe()

        self.__build_df_from_acm_db()
        self.__build_df_from_internal_db()
        

    def __build_df_from_acm_db(self):

        if self.__acm_objects_df_filtered.empty:
            return

        start = time.time()
        
        frame = {
                    'id':self.__acm_objects_df_filtered.index,
                    'Name':self.__acm_objects_df_filtered['Name'],
                    'Type':self.__acm_objects_df_filtered['CatalogNumber'],
                    'Page':self.__acm_objects_df_filtered['Name'],
                    'ChangeUser':self.__acm_objects_df_filtered['ChangeUser'],
                    'Description':self.__acm_objects_df_filtered['Description'],
                    'IsLinked':self.__acm_objects_df_filtered['IsLinked'],
                    'AssignmentID':'', 
                    'Catalog':self.__acm_objects_df_filtered['CatalogNumber']
        }
        df = pd.DataFrame(frame)
        self.__df = pd.concat([self.__df, df],ignore_index=True,sort=True)

        print('acm db building :'+str(time.time() - start))


    def __is_linked(self, df1, df2):
        # Merge the DataFrames based on the specified columns
        df1['IsLinked'] = np.where(df1['Name'].isin(df2['Name']), True, False)
        
        return df1
    

    def create_index_mapping(self, df1, df2, name_field):
        """
        Creates a dictionary mapping indexes from df1 to df2 based on a shared name field.
        
        Parameters:
        df1 (pandas.DataFrame): Source dataframe
        df2 (pandas.DataFrame): Target dataframe
        name_field (str): Name of the column containing shared names
        
        Returns:
        dict: Dictionary mapping df1 indexes to df2 indexes
        """
        # Create name to index mappings
        df1_name_to_idx = dict(zip(df1[name_field], df1['id']))
        df2_name_to_idx = dict(zip(df2[name_field], df2['id']))
        
        # Create mapping for common names
        mapping = {
            df1_name_to_idx[name]: df2_name_to_idx[name]
            for name in set(df1[name_field]).intersection(set(df2[name_field]))
        }
        
        return mapping


    def __build_df_from_internal_db(self):

        if self.__db is None:
            return 

        self.__control_modules = self.__db.get_all_control_modules()

        start = time.time()
        list = []
        for control_module in self.__control_modules:
            if 'id' not in  control_module:
                control_module['id'] = str(uuid.uuid4())
            d = {
                'id':control_module['id'],
                'Name':control_module['name'],
                'Type':'Unassigned',
                'Page':control_module['pno'],
                'ChangeUser':os.getlogin(),
                'Description':control_module['description'],
                'IsLinked': False,
                'AssignmentID': '',
                'Catalog': 'Unassigned'
            }
            list.append(d)

        internal_db_df = pd.DataFrame(list)

        if internal_db_df.empty:
            return
        self.__df = self.__is_linked(self.__df, internal_db_df)

        self.__db_to_db_mapping = self.create_index_mapping(internal_db_df, self.__df, 'Name')
        
        internal_db_only_df = internal_db_df.loc[~internal_db_df['Name'].isin(self.__df['Name'])].copy()

        internal_db_only_df = self.__assign_object_types(internal_db_only_df)
        
        self.__df = pd.concat([self.__df, internal_db_only_df],ignore_index=True,sort=True)
        
        print('internal db building :'+str(time.time() - start))



    def __assign_object_types(self, df):
        regexs = self.__db.get_all_object_assignment_regexs()

        def remove_brackets(text):
            # Initialize result string
            result = ""
            # Flag to track if we're inside brackets
            inside_brackets = False
            
            for char in text:
                if char == '(':
                    inside_brackets = True
                elif char == ')':
                    inside_brackets = False
                elif not inside_brackets:
                    result += char
                    
            return result

        sorted_regexs = sorted(regexs, key=lambda x: len(remove_brackets(x['regex'])), reverse=True)

        # Uses the processed_objects list to keep track of which objects have already been assigned a type
        # and writes the assigned type to the 'AssignmentID' column in the DataFrame
        processed_objects = []
        
        # Resulted dataframe
        result_df = df.copy()

        for regex in sorted_regexs:
            matching_objects = self.search_objects(regex['regex'], df)
            matching_objects = matching_objects.loc[~matching_objects['Name'].isin(processed_objects)].copy()
            result_df.loc[result_df['Name'].isin(matching_objects['Name']), 'AssignmentID'] = regex['id']
            result_df.loc[result_df['Name'].isin(matching_objects['Name']), 'Catalog'] = regex['library'][2]
            processed_objects.extend(matching_objects['Name'].tolist())

        return result_df
    

            

    def search_objects(self, regex_string, internal_db_only_df):
        return internal_db_only_df[internal_db_only_df['Name'].str.match(regex_string)]



    def __add_new(self):
        unassigned_countrol_modules = (sum(control_module["type"] == 'Unassigned' for control_module in self.__db.get_all_control_modules()))
        unassigned_df_rows = (len(self.__df[self.__df['Type']=='Unassigned']))
        if unassigned_countrol_modules < unassigned_df_rows:
            messagebox.showwarning("New undefined object already created", 
            'Please define the new undefined object named "' + self.__new_undefined_object_name + 
            '" before creating another object.')
            return 
        self.__get_data()
        uid = str(uuid.uuid4())
        self.__new_undefined_object_name = 'untitled 1'
        d = {'id':[uid],'Name': [self.__new_undefined_object_name]
             ,'Type': ['Unassigned'],'Page': ['Unassigned']
             , 'ChangeUser': [os.getlogin()], 'Description': ['undescribed']
             , 'IsLinked': False, 'Catalog': 'Unassigned'
             , 'AssignmentID': ''}
        
        if len(self.__df):
            self.__df['Name'].str.startswith('untitled ')
            untitled_df = self.__df[self.__df['Name'].str.startswith('untitled ')]
        
            if len(untitled_df):
                
                count = int(untitled_df['Name'].max().replace('untitled ',''))
                self.__new_undefined_object_name = 'untitled ' + str(count + 1)
                d['Name'] = [self.__new_undefined_object_name] 
        
        df = pd.DataFrame(data=d)
        self.__df = pd.concat([self.__df, df],ignore_index=True)
        untitled_df = self.__df['Name'].str.startswith('untitled ')

        
        self.__run_search()
        self.__draw_elements()
        self.__count = self.__count +1


    def __delete_element(self):
        if self.__multi_select:
            for cell in self.__selected_cell_object:
                cell.delete_from_database() 
        else:
            self.__selected_cell_object.delete_from_database()
        self.__refresh_data()
        if self.__refresh_roi_func:
            self.__refresh_roi_func()


    def set_roi_refresher(self, func):
        self.__refresh_roi_func = func
        

    def set_data_handler(self, data_handler):
        self.__acm_data_handler: ACM_Data_Handler = data_handler
        self.canvas.setup_data_handler(self.__acm_data_handler)
        self.__acm_data_handler.subscribe_to_filtered_objects_df(self.objects_callback)

        self.run_search()
        


    def objects_callback(self, data_frame, project_id):
        if project_id:
            self.canvas.hide_message()
        else: 
            self.canvas.show_message('No ACM project linked',
                                        'Go to Tools > Create ACM Project or go to File > Link ACM Project',
                                        error_image)
        data_frame['IsLinked'] = False
        self.__acm_objects_df_filtered = data_frame
        
        self.__refresh_data()



        
    def run_search(self, string=None):
        self.__run_search(string)
        self.__draw_elements()

    def __run_search(self, string=None):

        if string != None:
            self.search_string = string

        if self.__df.empty:
            return

        self.__searched_df = self.__df[self.__df['Name'].str.contains(
                                                            self.search_string, 
                                                            case=False,
                                                            regex=False)
                                                        ]

        
    def set_sort_by(self, selection):
        self.__sort_by_selection = selection 
        self.__draw_elements()


    def get_sort_by(self):
        return self.__sort_by_selection


    def __draw_elements(self):
        self.canvas.reset()

        if self.__searched_df.empty:
            return
            
        self.__searched_df.set_index('id',inplace=True)
        self.__groups_df = self.__searched_df.groupby(self.__sort_by_selection)

        self.canvas.set_db_to_db_mapping(self.__db_to_db_mapping)
        for index, _ in self.__groups_df.first().iterrows():
            if self.__sort_by_selection == 'Page':
                heading = 'Page '+str(int(index) + 1)
            else:
                heading = self.__sort_by_selection +': '+ str(index)
            self.canvas.insert_header(str(index)
                                      , heading
                                      , self.__groups_df.get_group(index)
                                      , expandable_list_canvas_control_module_cell)

        
        self.canvas.redraw()

    def __get_objects_project(self):
        pass


    def reset(self):
        self.__acm_objects_df_filtered = DataFrame()
        self.__searched_df = DataFrame()
        self.__groups_df = DataFrame()
        self.__initialize_dataframe()

        if self.__acm_data_handler:
            self.canvas.show_message('No ACM project linked',
                                        'Go to Tools > Create ACM Project or go to File > Link ACM Project',
                                        error_image)
        else:
            self.canvas.show_message('Not connected to ACM',
                                            'Go to File > Connect Database to connect an ACM database.',
                                            error_image)
        
        

class graphics_page(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.canvas = expandable_list_canvas(self, self.refresh)
        self.canvas.set_canvas_name('Static Graphics')
        self.canvas.pack(side="top", fill="both", pady=0, expand=True)
        #self.canvas.show_message('Under Construction','Coming soon in later version',under_construction_image)
        self.search_string = ''
        self.canvas.popup_menu(self.popup_menu)
        self.__initialize_dataframe()
        self.__sort_by_selection = 'Page'
        self.__selected_cell_name = None 
        self.__selected_cell_id = None 
        self.__selected_cell_object = None 
        self.__multi_select = False
        self.__new_undefined_object_name = ''
        self.__refresh_roi_func = None


    def __initialize_dataframe(self):
        d = {'id':[],'Name': [],'Page': [], 'ChangeUser': [], 'Description': []}
        self.__df = pd.DataFrame(data=d)
        self.__searched_df = self.__df
        self.__count = 0

    def popup_menu(self, event):
        """ Popup menu """
        self.__selected_cell_name, self.__selected_cell_id, self.__selected_cell_object, self.__multi_select = self.canvas.get_highlighted_cell()
        if self.__selected_cell_name:
            state = tk.ACTIVE
        else:
            state = tk.DISABLED
        self.menu = tk.Menu(self.canvas.canvas, tearoff=0)
        self.menu.add_command(label='Add New', command=self.__add_new)
        self.menu.add_command(label='Refresh', command=self.__refresh_data)
        self.menu.add_separator()
        self.menu.add_command(label='Delete', command=self.__delete_element, accelerator=u'Delete',state=state)
        self.menu.post(event.x_root, event.y_root)  # show popup menu


    def show_cell(self, cell:expandable_list_canvas_control_module_cell):
        group_id = cell.group_id
        cell_id = cell.cell_id
        self.canvas.show_canvas_tag(group_id, cell_id)

    def set_db(self, db):
        self.__db: Database = db
        self.__refresh_data()


    def set_sort_by(self, selection):
        self.__sort_by_selection = selection 
        #self.__draw_elements()


    def get_sort_by(self):
        return self.__sort_by_selection

    def refresh(self):
        self.__refresh_data()

    def __refresh_data(self):
        self.__get_data()
        self.__run_search()
        self.__draw_elements()

    def set_roi_refresher(self, func):
        self.__refresh_roi_func = func

    def __get_data(self):
        self.__initialize_dataframe()

        self.__all_graphics = self.__db.get_all_static_graphics()

        for graphic in self.__all_graphics:
            d = {
                'id':[graphic['id']],
                'Name':[graphic['name']],
                'Page':[graphic['pno']],
                'ChangeUser':[graphic['change_user']],
                'Description':[graphic['description']]
            }
            df = pd.DataFrame(data=d)
            self.__df = pd.concat([self.__df, df],ignore_index=True)

    

    def __add_new(self):
        self.__all_graphics = self.__db.get_all_static_graphics()
        if len(self.__all_graphics) < len(self.__df):
            messagebox.showwarning("New undefined object already created", 
            'Please define the new undefined object named "' + self.__new_undefined_object_name + 
            '" before creating another object.')
            return
        self.__get_data()
        self.__new_undefined_object_name = 'untitled 1'
        d = {'id':[str(uuid.uuid4())],'Name': [self.__new_undefined_object_name],'Page': ['Unassigned'], 'ChangeUser': [os.getlogin()], 'Description': ['undescribed']}
        
        if len(self.__df):
            untitled_df = self.__df[self.__df['Name'].str.startswith('untitled ')]
        
            if len(untitled_df):
                
                count = int(untitled_df['Name'].max().replace('untitled ',''))
                self.__new_undefined_object_name = 'untitled ' + str(count + 1)
                d['Name'] = [self.__new_undefined_object_name]
        
        df = pd.DataFrame(data=d)
        self.__df = pd.concat([self.__df, df],ignore_index=True)
        untitled_df = self.__df['Name'].str.startswith('untitled ')
        
        self.__run_search()
        self.__draw_elements()
        self.__count = self.__count +1


    def __delete_element(self):
        if self.__multi_select:
            for cell in self.__selected_cell_object:
               cell.delete_from_database() 
        else:
            self.__selected_cell_object.delete_from_database()
        self.__refresh_data()
        if self.__refresh_roi_func:
            self.__refresh_roi_func()


    def run_search(self, string=None):
        self.__run_search(string)
        self.__draw_elements()

    def __run_search(self, string=None):

        if string != None:
            self.search_string = string

        if self.__df.empty:
            return

        self.__searched_df = self.__df[self.__df['Name'].str.contains(
                                                self.search_string, 
                                                case=False,
                                                regex=False)
                                            ]
        



    def __draw_elements(self):
        self.canvas.reset()

        if self.__searched_df.empty:
            return

        self.__searched_df.set_index('id',inplace=True)
        self.__groups_df = self.__searched_df.groupby('Page')
        
        for index, _ in self.__groups_df.first().iterrows():
            if index == 'Unassigned':
                self.canvas.insert_header(index, 'Unassigned',self.__groups_df.get_group(index),expandable_list_canvas_static_graphic_cell)
            else:
                self.canvas.insert_header(str(index), "Page: "+str(int(index) + 1),self.__groups_df.get_group(index),expandable_list_canvas_static_graphic_cell)

        
        self.canvas.redraw()

    def reset_data_frames(self):
        self.__searched_df = DataFrame()
        self.__groups_df = DataFrame()
        self.__groups_df = DataFrame()
        self.__initialize_dataframe()


class displays_page(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.canvas = expandable_list_canvas(self, self.refresh)
        self.canvas.set_canvas_name('HMI Displays')
        self.canvas.pack(side="top", fill="both", pady=0, expand=True)
        #self.canvas.show_message('Under Construction','Coming soon in later version',under_construction_image)
        self.search_string = ''
        self.canvas.popup_menu(self.popup_menu)
        self.__initialize_dataframe()
        self.__sort_by_selection = 'Page'
        self.__selected_cell_name = None 
        self.__selected_cell_id = None 
        self.__selected_cell_object = None 
        self.__multi_select = False
        self.__new_undefined_object_name = ''
        self.__refresh_roi_func = None

    def __initialize_dataframe(self):
        d = {'id':[],'Name': [],'Page': [], 'ChangeUser': [], 'Description': []}
        self.__df = pd.DataFrame(data=d)
        self.__searched_df = self.__df
        self.__count = 0

    def popup_menu(self, event):
        """ Popup menu """
        self.__selected_cell_name, self.__selected_cell_id, self.__selected_cell_object, self.__multi_select = self.canvas.get_highlighted_cell()
        if self.__selected_cell_name:
            state = tk.ACTIVE
        else:
            state = tk.DISABLED
        self.menu = tk.Menu(self.canvas.canvas, tearoff=0)
        self.menu.add_command(label='Add New', command=self.__add_new)
        self.menu.add_command(label='Refresh', command=self.__refresh_data)
        self.menu.add_separator()
        self.menu.add_command(label='Delete', command=self.__delete_element, accelerator=u'Delete',state=state)
        self.menu.post(event.x_root, event.y_root)  # show popup menu


    def set_data_handler(self, data_handler):
        self.__acm_data_handler: ACM_Data_Handler = data_handler
        self.canvas.setup_data_handler(self.__acm_data_handler)
        

    def set_db(self, db):
        self.__db: Database = db
        self.__refresh_data()

    
    def set_sort_by(self, selection):
        self.__sort_by_selection = selection 
        #self.__draw_elements()


    def get_sort_by(self):
        return self.__sort_by_selection

    def refresh(self):
        self.__refresh_data()

    def __refresh_data(self):
        self.__get_data()
        self.__run_search()
        self.__draw_elements()

    
    def set_roi_refresher(self, func):
        self.__refresh_roi_func = func



    def __get_data(self):
        self.__initialize_dataframe()

        self.__all_pages = self.__db.get_all_hmi_displays()
        
        for graphic in self.__all_pages:
            d = {
                'id':[graphic['id']],
                'Name':[graphic['name']],
                'Page':[graphic['pno']],
                'ChangeUser':[graphic['change_user']],
                'Description':[graphic['description']]
            }
            df = pd.DataFrame(data=d)
            self.__df = pd.concat([self.__df, df],ignore_index=True)

        

    def __add_new(self):
        self.__all_pages = self.__db.get_all_hmi_displays()
        if len(self.__all_pages) < len(self.__df):
            messagebox.showwarning("New undefined object already created", 
            'Please define the new undefined object named "' + self.__new_undefined_object_name + 
            '" before creating another object.')
            return
        self.__get_data()
        self.__new_undefined_object_name = 'untitled 1'
        d = {'id':[str(uuid.uuid4())],'Name': [self.__new_undefined_object_name],'Page': ['Unassigned'], 'ChangeUser': [os.getlogin()], 'Description': ['undescribed']}
        
        if len(self.__df):
            untitled_df = self.__df[self.__df['Name'].str.startswith('untitled ')]
        
            if len(untitled_df):
                
                count = int(untitled_df['Name'].max().replace('untitled ',''))
                self.__new_undefined_object_name = 'untitled ' + str(count + 1)
                d['Name'] = [self.__new_undefined_object_name]
        
        df = pd.DataFrame(data=d)
        self.__df = pd.concat([self.__df, df],ignore_index=True)
        untitled_df = self.__df['Name'].str.startswith('untitled ')
        
        self.__run_search()
        self.__draw_elements()
        self.__count = self.__count + 1

    def __delete_element(self):
        if self.__multi_select:
            for cell in self.__selected_cell_object:
               cell.delete_from_database() 
        else:
            self.__selected_cell_object.delete_from_database()
        self.__refresh_data()
        if self.__refresh_roi_func:
            self.__refresh_roi_func()

    def run_search(self, string=None):
        self.__run_search(string)
        self.__draw_elements()

    def __run_search(self, string=None):

        if string != None:
            self.search_string = string

        if self.__df.empty:
            return

        self.__searched_df = self.__df[self.__df['Name'].str.contains(
                                                self.search_string, 
                                                case=False,
                                                regex=False)
                                            ]
        
        
        


    def __draw_elements(self):
        self.canvas.reset()

        if self.__searched_df.empty:
            return

        self.__searched_df.set_index('id',inplace=True)
        self.__groups_df = self.__searched_df.groupby('Page')
        
        for index, _ in self.__groups_df.first().iterrows():
            if index == 'Unassigned':
                self.canvas.insert_header(index, 'Unassigned',self.__groups_df.get_group(index),expandable_list_canvas_hmi_display_cell)
            else:
                self.canvas.insert_header(str(index), "Page: "+str(int(index) + 1),self.__groups_df.get_group(index),expandable_list_canvas_hmi_display_cell)

        
        self.canvas.redraw()


    def reset_data_frames(self):
        self.__searched_df = DataFrame()
        self.__groups_df = DataFrame()
        self.__groups_df = DataFrame()
        self.__initialize_dataframe()


class approvals_page(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.canvas = expandable_list_approval_canvas(self, self.refresh)
        self.canvas.pack(side="top", fill="both", pady=0, expand=True)
        self.canvas.popup_menu(self.popup_menu)
        self.menu = tk.Menu(self.canvas.canvas, tearoff=0)
        self.menu.add_command(label='Add New', command=self.__add_new, state=tk.DISABLED)
        self.menu.add_command(label='Delete', command=self.__delete_element, accelerator=u'Delete', state=tk.DISABLED)
        self.__sort_by_selection = 'Catalog'
        self.search_string = ''
        self.canvas.after(1000, lambda: self.__show_bottom_approval_view()) 
    
    def __show_bottom_approval_view(self):
        self.canvas.show_bottom_approval_view()

    def __initialize_dataframe(self):
        d = {'id':[],'Name': [],'Page': [], 'ChangeUser': [], 'Description': []}
        self.__df = pd.DataFrame(data=d)
        self.__searched_df = self.__df
        self.__count = 0


    def show_cell(self, cell):
        if not cell:
            return

        # Find which group in self.__groups_df holds the item with the value cell[0]
        for group_id, group in self.__groups_df:
            if cell[0] in group.index:
                self.canvas.show_canvas_tag(group_id, cell[0])
                return

        logging.warning(f"Unapproved linked text {cell[0]} was not found in the approvals list")

    def popup_menu(self, event):
        """ Popup menu """
        self.__selected_cell_name, self.__selected_cell_id, self.__selected_cell_object, self.__multi_select = self.canvas.get_highlighted_cell()
        if self.__selected_cell_name:
            state = tk.ACTIVE
        else:
            state = tk.DISABLED
        self.menu = tk.Menu(self.canvas.canvas, tearoff=0)
        self.menu.add_command(label='Add New', command=self.__add_new, state=tk.DISABLED)
        self.menu.add_command(label='Refresh', command=self.__refresh_data)
        self.menu.add_separator()
        self.menu.add_command(label='Delete', command=self.__delete_element, accelerator=u'Delete',state=state)
        self.menu.post(event.x_root, event.y_root)  # show popup menu


    def set_data_handler(self, data_handler):
        self.__acm_data_handler: ACM_Data_Handler = data_handler
        self.canvas.setup_data_handler(self.__acm_data_handler)
        

    def set_db(self, db):
        self.__db: Database = db
        self.__refresh_data()

    
    def set_sort_by(self, selection):
        self.__sort_by_selection = selection 
        self.__refresh_data()


    def get_sort_by(self):
        return self.__sort_by_selection


    def refresh(self):
        self.__refresh_data()

    def __refresh_data(self):
        self.__get_data()
        self.__run_search()
        self.__draw_elements()
        

    def __get_data(self):
        self.__initialize_dataframe()

        self.__all_unapproved_text_links = self.__db.get_all_unapproved_text_links()
        
    
        for text_link in self.__all_unapproved_text_links:
            if 'subobject' not in text_link:
                description = ''
                parameter = list(text_link['parameters'].keys())[0]
                
                description = f"{parameter} = {text_link['parameters'][parameter]['text']}"

                
                d = {
                    'id':[text_link['id']],
                    'Name':[text_link['tagname']['text']],
                    'Page':[text_link['pno']],
                    'ChangeUser':'',
                    'Catalog':[text_link['tagname']['object_type']],
                    'Description':description,
                    'Parameter':parameter,
                    'Subparameter':''
                }
                df = pd.DataFrame(data=d)
            else:

                description = ''
                for parameter, data in text_link['parameters'].items():
                    description = f"{parameter} = {data['text']}\n"

                
                d = {
                    'id':[text_link['id']],
                    'Name':[text_link['tagname']['text']],
                    'Page':[text_link['pno']],
                    'ChangeUser':'',
                    'Catalog':[text_link['tagname']['object_type']],
                    'Description':description,
                    'Parameter':text_link['subobject']['text'],
                    'Subparameter':parameter
                }
                df = pd.DataFrame(data=d)
            self.__df = pd.concat([self.__df, df],ignore_index=True)

     
                

        

    def __add_new(self):
        self.__all_unapproved_text_links = self.__db.get_all_hmi_displays()
        if len(self.__all_unapproved_text_links) < len(self.__df):
            messagebox.showwarning("New undefined object already created", 
            'Please define the new undefined object named "' + self.__new_undefined_object_name + 
            '" before creating another object.')
            return
        self.__get_data()
        self.__new_undefined_object_name = 'untitled 1'
        d = {'id':[str(uuid.uuid4())],'Name': [self.__new_undefined_object_name],'Page': ['Unassigned'], 'ChangeUser': [os.getlogin()], 'Description': ['undescribed']}
        
        if len(self.__df):
            untitled_df = self.__df[self.__df['Name'].str.startswith('untitled ')]
        
            if len(untitled_df):
                
                count = int(untitled_df['Name'].max().replace('untitled ',''))
                self.__new_undefined_object_name = 'untitled ' + str(count + 1)
                d['Name'] = [self.__new_undefined_object_name]
        
        df = pd.DataFrame(data=d)
        self.__df = pd.concat([self.__df, df],ignore_index=True)
        untitled_df = self.__df['Name'].str.startswith('untitled ')
        
        self.__run_search()
        self.__draw_elements()
        self.__count = self.__count + 1


    def __delete_element(self):
        if self.__multi_select:
            for cell in self.__selected_cell_object:
               cell.delete_from_database() 
        else:
            self.__selected_cell_object.delete_from_database()
        self.__refresh_data()
        if self.__refresh_roi_func:
            self.__refresh_roi_func()


    def run_search(self, string=None):
        self.__run_search(string)
        self.__draw_elements()

    def __run_search(self, string=None):

        if string != None:
            self.search_string = string

        if self.__df.empty:
            return

        self.__searched_df = self.__df[self.__df['Name'].str.contains(
                                                self.search_string, 
                                                case=False,
                                                regex=False)
                                            ]
        
        

    def __draw_elements(self):
        self.canvas.reset()

        if self.__searched_df.empty:
            return

        self.__searched_df.set_index('id',inplace=True)
        self.__groups_df = self.__searched_df.groupby(self.__sort_by_selection)
        
        for index, _ in self.__groups_df.first().iterrows():

            if index == 'Unassigned':
                self.canvas.insert_header(index, 'Unassigned',self.__groups_df.get_group(index),expandable_approval_list_canvas_cell)
            else:
                if self.__sort_by_selection == 'Page':
                    heading = 'Page '+str(int(index) + 1)
                else:
                    heading = self.__sort_by_selection +': '+ str(index)
                self.canvas.insert_header(str(index), heading,self.__groups_df.get_group(index),expandable_approval_list_canvas_cell)

        
        self.canvas.redraw()


    def set_roi_refresher(self, func):
        self.__refresh_roi_func = func
        
class configure_page(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.rowconfigure(0, weight=1)  # make canvas expandable
        self.columnconfigure(0, weight=1)
        vbar = AutoScrollbar(self, orient='vertical')
        vbar.grid(row=0, column=1, sticky='ns')
        self.canvas = tk.Canvas(self, highlightthickness=0,bd=0, yscrollcommand=vbar.set)
        self.canvas.grid(row=0, column=0, sticky='nswe')
        self.canvas.update()  # wait till canvas is created
        vbar.configure(command=self.__scroll_y)
        self.canvas.bind('<Configure>',  self.__redraw)  # canvas is resized
        self.canvas.bind('<MouseWheel>', self.__wheel)
        self.canvas.bind('<Button-1>',self.__click)
        self.canvas.config(scrollregion=(0,0,0,0),background='yellow')
        self.canvas_changed_callback = None
        self.message_visible = False
        self.message_image = None
        self.message_image_id = None
        self.message_title_id = None 
        self.message_text_id = None
        
    # noinspection PyUnusedLocal
    def __scroll_y(self, *args, **kwargs):
        """ Scroll canvas vertically and redraw the image """
        self.canvas.yview(*args)  # scroll vertically
        
    def __wheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), tk.UNITS)
        
    def __click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

    def show_message(self, title, message, image):
        self.message_visible = True 
        self.message_title = title 
        self.message_text = message
        self.message_image = tk.PhotoImage(data=image)
        self.__redraw(None)
         


    def hide_message(self):
        if self.message_visible:
            self.message_visible = False 
            self.__remove_message()
        
        self.__redraw(None)

    
    def __remove_message(self):
        if self.message_image_id:
            self.canvas.delete(self.message_image_id)
            self.canvas.delete(self.message_title_id)
            self.canvas.delete(self.message_text_id)
        

    def __redraw(self, _):
        y = 0
        x = 0

        self.__draw_message_with_icon()


    def __draw_message_with_icon(self):
        if self.message_visible and self.message_image:
            self.__remove_message()
            self.message_image_id = self.canvas.create_image(int(self.canvas.winfo_width()/2), 
                                        int(self.canvas.winfo_height()/3), 
                                        image = self.message_image, 
                                        anchor = tk.CENTER)
            title_font = font.Font(family="arial.ttf",size=11,weight="bold")
            self.message_title_id = self.canvas.create_text(int(self.canvas.winfo_width()/2),
                                        int(self.canvas.winfo_height()/3 + self.message_image.height()/2 + 8),
                                        text=self.message_title, anchor=tk.CENTER, fill="#A0A0A0",font=title_font,
                                        justify=tk.CENTER)
            message_font = font.Font(family="arial.ttf",size=9,weight="normal")
            self.message_text_id = self.canvas.create_text(int(self.canvas.winfo_width()/2),
                                        int(self.canvas.winfo_height()/3 + self.message_image.height()/2 + 24),
                                        text=self.message_text, anchor=tk.CENTER, fill="#A0A0A0",font=message_font,
                                        justify=tk.CENTER)


        



if __name__ == "__main__":
    root = tk.Tk()

    app = tool_frame(root)
    button0 = tk.Button(root, text="Go to Page Zero",
                            command=lambda: app.show_frame("tags_page"))
    button1 = tk.Button(root, text="Go to Page One",
                            command=lambda: app.show_frame("graphics_page"))
    button2 = tk.Button(root, text="Go to Page Two",
                        command=lambda: app.show_frame("displays_page"))
    button0.pack()
    button1.pack()
    button2.pack()
    app.mainloop()