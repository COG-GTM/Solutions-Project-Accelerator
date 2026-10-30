import datetime
import json
import logging
import os
import re
from string import Formatter
from tkinter import Label
from typing import Dict
from sqlalchemy import create_engine, engine
from sqlalchemy.engine import URL
import pandas as pd
from rapidfuzz import fuzz, process

try:
    from bin.logic_sql_database import db_connector, non_commit_db_connector
    from bin.logic_acm_db_commands import create_display_sql_command, position_control_module_sql_command, write_parameter_value_sql_command, write_subparameter_value_sql_command
    from bin.logic_acm_db_commands import create_line_sql_command, create_image_sql_command, create_page_link_sql_command, create_subobject, write_parameter_value_and_reftype_sql_command
    from bin.logic_acm_db_commands import get_all_objects_with_acm_filter, get_all_subobjects_with_acm_filter, subobject_subparameter_value_template, write_subparameter_value_and_reftype_sql_command
    from bin.logic_acm_db_commands import get_display_objects_sql_command, get_displays_sql_command, get_display_sql_command, get_display_object_sql_command, delete_subobject_sql_command
    from bin.logic_acm_db_commands import bind_params, parameterize_acm_filter, render_name_template, to_db_id
    from bin.logic_acm_db_commands import (create_display_sql_command_params, create_image_sql_command_params, create_line_sql_command_params, create_page_link_sql_command_params, create_subobject_params, delete_subobject_sql_command_params, get_all_objects_with_acm_filter_params, get_all_subobjects_with_acm_filter_params, get_display_object_sql_command_params, get_display_objects_sql_command_params, get_display_sql_command_params, get_displays_sql_command_params, position_control_module_sql_command_params, subobject_subparameter_value_template_params, write_parameter_value_and_reftype_sql_command_params, write_subparameter_value_and_reftype_sql_command_params)
except:
    from logic_sql_database import db_connector, non_commit_db_connector
    from logic_acm_db_commands import create_display_sql_command, position_control_module_sql_command, write_parameter_value_sql_command, write_subparameter_value_sql_command
    from logic_acm_db_commands import create_line_sql_command, create_image_sql_command, create_page_link_sql_command, create_subobject, write_parameter_value_and_reftype_sql_command
    from logic_acm_db_commands import get_all_objects_with_acm_filter, get_all_subobjects_with_acm_filter, subobject_subparameter_value_template, write_subparameter_value_and_reftype_sql_command
    from logic_acm_db_commands import get_display_objects_sql_command, get_displays_sql_command, get_display_sql_command, get_display_object_sql_command, delete_subobject_sql_command
    from logic_acm_db_commands import bind_params, parameterize_acm_filter, render_name_template, to_db_id
    from logic_acm_db_commands import (create_display_sql_command_params, create_image_sql_command_params, create_line_sql_command_params, create_page_link_sql_command_params, create_subobject_params, delete_subobject_sql_command_params, get_all_objects_with_acm_filter_params, get_all_subobjects_with_acm_filter_params, get_display_object_sql_command_params, get_display_objects_sql_command_params, get_display_sql_command_params, get_displays_sql_command_params, position_control_module_sql_command_params, subobject_subparameter_value_template_params, write_parameter_value_and_reftype_sql_command_params, write_subparameter_value_and_reftype_sql_command_params)


# SPA-generated object names differ by a single character (UX00201 vs UX00202),
# so a fuzzy tagname lookup only counts when it scores high and beats the runner-up.
_TAGNAME_FUZZY_SCORE_CUTOFF = 90
_TAGNAME_FUZZY_AMBIGUITY_MARGIN = 5


def _normalize_tagname(value) -> str:
    return re.sub(r'[^a-zA-Z0-9]', '', str(value)).upper()


class ACM_Data_Handler():
    """
    A class that handles the ACM data and provides methods to interact with the ACM database. The class connects 
    to the SQL ACM database and provides methods to retrieve, create, and update ACM data.
    """
    REF_IMMEDIATE_TYPE = 1
    REF_OBJECT_TYPE = 2
    REF_OBJECT_NIB_TYPE = 5
    REF_SUBOBJECT_TYPE = 3
    REF_SUBOBJECT_NIB_TYPE = 9

    SUBOBJECT_DESCRIPTION = 'SubObject Description'

    def __init__(self, connection_string, project_missing_callback=None) -> None:
        """
        Initializes the logic_acm_data_handler object.

        :param connection_string: The connection string for the database.
        :type connection_string: str

        :return: None
        :rtype: None
        """
        connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
        self.__engine = create_engine(connection_url)
        self.__connection_string = connection_string
        self.__project_missing_callback = project_missing_callback
        self.initialize()

    def initialize(self):
        self.__project_id = None
        self.__is_linked = False
        self.__previous_project_id = ''
        self.__filter = {}
        self.__filtered = False # Used to indicate to the use if filter is used
        self.__df_filtered = pd.DataFrame()
        self.__projects_df = pd.DataFrame()
        self.__objects_df = pd.DataFrame()
        self.__all_objects_df = pd.DataFrame()
        self.__subobjects_df = pd.DataFrame()
        self.__parameters_df = pd.DataFrame()
        self.__subparameters_df = pd.DataFrame()
        self.__get_objects_in_project_callbacks = []
        self.__get_is_filtered_callbacks = []


    def refresh_all_data(self):
        """
        Refreshes all data in the data handler.

        :return: None
        :rtype: None
        """
        self.__objects_df = pd.DataFrame()
        self.set_objects_filter()
        
        

    def set_project_id(self, project_id):
        """
        Sets the project ID and updates the objects filter.

        :param project_id: The project ID to set.
        :type project_id: Any

        :return: None
        :rtype: None

        This function sets the project ID and updates the objects filter. It also sets the __is_linked attribute to True.
        """
        if project_id:
            try:
                project_id = to_db_id(project_id, 'project_id')
            except ValueError:
                logging.error('Ignoring invalid ACM project id: %r', project_id)
                if self.__project_missing_callback:
                    self.__project_missing_callback()
                return
            self.__project_id = project_id
            self.set_objects_filter()
            self.__is_linked = True 

    
    def get_project_id(self):
        """
        Returns the project ID.

        :return: The project ID.
        :rtype: str
        """
        return self.__project_id
    
    def get_project_name(self):
        """
        Returns the project name.

        :return: The project name.
        :rtype: str
        """
        if self.__project_id is None:
            return ''

        if self.__projects_df.empty:
            self.get_all_projects()

        project_id = int(self.__project_id)

        if project_id in self.__projects_df.index:
            return self.__projects_df.loc[project_id]['Name']
        return ''

    
    def is_linked(self):
        """
        Check if the object is linked to an ACM project.

        :return: True if the object is linked, False otherwise.
        :rtype: bool
        """
        return self.__is_linked

    
    def get_all_projects(self):
        """
        Retrieves all projects from the database.
        
        :return: A DataFrame containing all projects.
        :rtype: pandas.DataFrame

        Retrieves all projects from the database by executing a SQL query to retrieve all projects from the 'Projects' table. Returns a DataFrame containing all projects.
        """

        query = 'SELECT * FROM Projects'
        self.__projects_df =  pd.read_sql_query(query,self.__engine,index_col='ProjectID')
        
        return self.__projects_df 
    

    def check_if_project_exists(self):
        """
        Checks if a project exists in the database.

        :return: True if the project exists, False otherwise.
        :rtype: bool
        """
        query = 'SELECT COUNT(*) FROM Projects WHERE ProjectID=?'
        count = pd.read_sql_query(query, self.__engine, params=(to_db_id(self.__project_id, 'project_id'),)).iloc[0, 0]
        return count > 0
    

    def get_all_registered_libraries(self):
        """
        Retrieves all registered libraries from the database.

        :return: A DataFrame containing all registered libraries.
        :rtype: pandas.DataFrame

        Retrieves all registered libraries from the database by executing a SQL query to retrieve all libraries from the 'RegisteredLibraries' table. Returns a DataFrame containing all registered libraries.
        """

        query = 'SELECT * FROM RegisteredLibraries'
        return pd.read_sql_query(query,self.__engine,index_col='LibraryID')
    

    def get_registered_library(self, library_id):
        """
        Retrieves all registered libraries from the database.

        :return: A DataFrame containing all registered libraries.
        :rtype: pandas.DataFrame

        Retrieves all registered libraries from the database by executing a SQL query to retrieve all libraries from the 'RegisteredLibraries' table. Returns a DataFrame containing all registered libraries.
        """

        query = 'SELECT * FROM RegisteredLibraries where LibraryID=?'
        return pd.read_sql_query(query,self.__engine,params=(str(library_id),),index_col='LibraryID')
    

    def get_all_project_libraries(self):
        """
        Retrieves all libraries associated with a specific project.

        Uses DISTINCT to get unique library entries.

        :param project_id: The ID of the project to retrieve libraries for.
        :type project_id: Any

        :return: A DataFrame containing all libraries associated with the project.
        :rtype: pandas.DataFrame

        Retrieves all libraries associated with a specific project by executing a SQL query to retrieve all libraries from the 'ProjectLibraries' table where the ProjectID matches the given project_id. Returns a DataFrame containing all libraries associated with the project.
        """

        query = 'SELECT DISTINCT LibraryID,CatalogNumber,LibraryType FROM Objects WHERE ProjectID=?'
        return pd.read_sql_query(query,self.__engine,params=(to_db_id(self.__project_id, 'project_id'),),index_col='LibraryID')
    

    def get_all_objects_in_project(self, force_update=False) -> pd.DataFrame:
        """
        Retrieves all objects in an ACM project.

        :return: DataFrame containing all objects in the project
        :rtype: pandas.DataFrame

        Retrieves all objects in an ACM project by executing a SQL query to retrieve all objects from the 'Objects' table. Returns a DataFrame containing all objects in the project.
        """

        if self.__project_id and (force_update or self.__objects_df.empty 
                or self.__previous_project_id != self.__project_id):
            query = 'SELECT * FROM Objects WHERE ProjectID=?'
            self.__all_objects_df = pd.read_sql_query(query,self.__engine,params=(to_db_id(self.__project_id, 'project_id'),),index_col='ObjectID')
            if self.__all_objects_df['ControllerID'].first_valid_index() is None:
                return self.__objects_df
                
            self.__controller_id = self.__all_objects_df.loc[self.__all_objects_df['ControllerID'].first_valid_index()]['ControllerID']
            self.__controller_object_id = self.__all_objects_df['ControllerID'].sort_index().first_valid_index()
            none_controllers_df = self.__all_objects_df[self.__all_objects_df['LibraryType'] != 'Controller']
            self.__parent_object_id = none_controllers_df.loc[none_controllers_df['ControllerID'].first_valid_index()]['ParentObjectID']
            self.__previous_project_id = self.__project_id

            query = ("SELECT DISTINCT Objects.ObjectID,Objects.ProjectID,Objects.ControllerID,Objects.ParentObjectID"+
                    ",Objects.ParentObjectImport,Objects.Name,Objects.CatalogNumber,Objects.Description,Objects.LibraryID"+
                    ",Objects.LibraryType,Objects.ChangeDate,Objects.ChangeUser,Objects.MajorRev,Objects.MinorRev"+
                    ",Objects.Lock,Objects.MarkForDeletion FROM Objects inner join Parameters "+
                    "on Objects.ObjectID  = Parameters.ObjectID "+
                    "where Objects.CatalogNumber != 'Image' and Objects.CatalogNumber != 'PageLink' "+
                    "and Objects.ProjectID=? "+
                    "and Objects.ParentObjectID > 0 and Objects.ControllerID IS NOT NULL")
            self.__objects_df = pd.read_sql_query(query,self.__engine,params=(to_db_id(self.__project_id, 'project_id'),),index_col='ObjectID')
        return self.__objects_df
    

    def get_controller_name(self):
        """
        Retrieves the name of the controller object.

        :return: The name of the controller object.
        :rtype: str

        Retrieves the name of the controller object from the 'Objects' DataFrame. Returns the name as a string.
        """
        if self.__all_objects_df.empty:
            return ''
        
        controller_name = self.__all_objects_df[self.__all_objects_df['LibraryType'] == 'Controller']['Name'].iloc[0]

        return controller_name


    def get_controller_object_id(self):
        """
        Retrieves the ObjectID of the controller object for the current project.

        Forces a refresh of the objects cache so the controller is picked up
        immediately after an ACM CREATECONTROLLER script has run.

        :return: The ObjectID of the controller, or ``None`` if no controller exists.
        :rtype: int or None
        """
        # Force refresh so a freshly-created controller is picked up
        self.get_all_objects_in_project(force_update=True)
        return getattr(self, '_ACM_Data_Handler__controller_object_id', None)


    def is_control_module_in_project(self, name,type=None):
        """
        Check if a control module is present in the project.

        :param name: The name of the control module.
        :type name: str
        :param type: The type of the control module (optional).
        :type type: str, default=None

        :return: True if the control module is present, False otherwise.
        :rtype: bool

        This function checks if a control module with the given name is present in the project.
        If the type parameter is provided, it also checks if the control module has the specified type.

        Example:
            >>> is_control_module_in_project('module1')
            True
            >>> is_control_module_in_project('module2', 'type1')
            False
        """
        if type==None:
            return len(self.__objects_df[self.__objects_df['Name'].str.contains(r'\b'+name+r'\b')]) > 0
        else:
            return len(self.__objects_df[(self.__objects_df['Name'].str.contains(r'\b'+name+r'\b')) &
                                           (self.__objects_df['CatalogNumber'].str.contains(r'\b'+type+r'\b'))]) > 0

    
    def is_object_in_project(self, name,type=None):
        """
        Check if an object is present in the project.

        :param name: The name of the object to search for.
        :type name: str
        :param type: The type of the object to search for. (optional)
        :type type: str
        :return: True if the object is found, False otherwise.
        :rtype: bool

        This function checks if an object with the given name and type (optional) is present in the project.
        If type is not provided, it only checks for the object name.
        Returns True if the object is found, False otherwise.

        Example:
            >>> is_object_in_project('example_object')
            True
            >>> is_object_in_project('example_object', 'example_type')
            False
        """
        if type==None:
            return len(self.__all_objects_df[self.__all_objects_df['Name'].str.contains(r'\b'+name+r'\b',case=False)]) > 0
        else:
            return len(self.__all_objects_df[(self.__all_objects_df['Name'].str.contains(r'\b'+name+r'\b',case=False)) &
                                           (self.__all_objects_df['CatalogNumber'].str.contains(r'\b'+type+r'\b',case=False))]) > 0


    def __ensure_object_cached(self, object_id):
        """
        Refresh the cached ``__all_objects_df`` from the database if ``object_id``
        is not already present.

        The in-memory ``__all_objects_df`` cache is populated once by
        :meth:`get_all_objects_in_project`. Methods that create new objects
        directly in the ACM database (e.g. :meth:`create_new_hmi_display_in_acm`)
        do not invalidate this cache, so subsequent lookups for newly created
        ObjectIDs would raise ``KeyError`` until the app was restarted. This
        helper re-queries the Objects table on demand to pick up any objects
        added since the cache was last populated.
        """
        if not self.__project_id:
            return
        try:
            if object_id in self.__all_objects_df.index:
                return
        except Exception:
            pass
        query = 'SELECT * FROM Objects WHERE ProjectID=?'
        self.__all_objects_df = pd.read_sql_query(query, self.__engine, params=(to_db_id(self.__project_id, 'project_id'),), index_col='ObjectID')

    def get_object_name(self, object_id:int):
        """
        Retrieves the name of an object based on its ID.
        :param object_id: The ID of the object.
        :type object_id: int
        :return: The name of the object.
        :rtype: str

        Retrieves the name of an object from the __all_objects_df DataFrame based on its ID. 
        Returns the name as a string.

        Example:
            >>> get_object_name(1)
            'Object Name'
        """
        logging.info(f"Retrieving object name for ID: {object_id}")
        self.__ensure_object_cached(object_id)
        if object_id not in self.__all_objects_df.index:
            logging.info(f"Object ID {object_id} not found.")
        return self.__all_objects_df.loc[[object_id]]['Name'].iloc[0]
    

    def get_object_with_tagname_like(self, tagname:str):
        """
        Retrieves objects from the DataFrame based on a tagname given.
        :param tagname: The tagname to search for.
        :type tagname: str
        :return: A DataFrame containing the objects that match the given tagname.
        :rtype: pandas.DataFrame

        Both the tagname and the object names are stripped of special characters and upper-cased before
        comparison, so 'UX-00201', 'ux00201' and 'UX00201' all resolve to the same object. An exact match
        wins, then a substring match, then a fuzzy match that must clear a score cutoff and beat the
        runner-up; an ambiguous fuzzy result returns nothing rather than a guess.

        Example:
            >>> get_object_with_tagname_like('example_tagname')
            Returns a DataFrame with objects that have 'example_tagname' in their name.
        """
        if self.__all_objects_df.empty:
            return pd.DataFrame()

        normalized_tagname = _normalize_tagname(tagname)
        if not normalized_tagname:
            return pd.DataFrame()

        normalized_names = self.__all_objects_df['Name'].fillna('').map(_normalize_tagname)

        exact_df = self.__all_objects_df[normalized_names == normalized_tagname]
        if not exact_df.empty:
            return exact_df

        df = self.__all_objects_df[normalized_names.str.contains(normalized_tagname, regex=False)]
        if not df.empty:
            return df

        # WRatio's partial-ratio branch scores a truncated tag equally against every sibling, so
        # compare with a plain ratio over distinct names.
        candidates = [name for name in dict.fromkeys(normalized_names.tolist()) if name]
        matches = process.extract(normalized_tagname, candidates, scorer=fuzz.ratio, limit=2,
                                  score_cutoff=_TAGNAME_FUZZY_SCORE_CUTOFF)
        if not matches:
            logging.info(f"No object matched tagname '{tagname}'.")
            return pd.DataFrame()

        if len(matches) > 1 and matches[0][1] - matches[1][1] < _TAGNAME_FUZZY_AMBIGUITY_MARGIN:
            logging.info(f"Ambiguous tagname '{tagname}': '{matches[0][0]}' ({matches[0][1]:.1f}) and "
                         f"'{matches[1][0]}' ({matches[1][1]:.1f}) are too close to call.")
            return pd.DataFrame()

        return self.__all_objects_df[normalized_names == matches[0][0]]

    def get_object(self, object_id:int):
        """
        Retrieves an object from the data handler based on the provided object ID.

        :param object_id: The ID of the object to retrieve.
        :type object_id: int
        :return: The retrieved object.
        :rtype: pandas.DataFrame

        Retrieves the object with the specified object ID from the data handler's dataframe and returns it.
        
        Example:
            >>> get_object(1)
            DataFrame with the object data
        """
        self.__ensure_object_cached(object_id)
        return self.__all_objects_df.loc[[object_id]]
    

    def get_object_with_name(self, object_name:str,case=True):
        """
        Retrieves objects from the DataFrame based on the given object name.

        :param object_name: The name of the object to search for.
        :type object_name: str
        :param case: Determines whether the search is case-sensitive or not. Defaults to True.
        :type case: bool
        :return: A DataFrame containing the objects that match the given object name.
        :rtype: pandas.DataFrame

        Retrieves objects from the DataFrame based on the given object name. The search can be case-sensitive or case-insensitive, depending on the value of the 'case' parameter.
        
        Example:
            >>> get_object_with_name('example_object')
            Returns a DataFrame with objects that have 'example_object' in their name.
        """
        
        return self.__all_objects_df[self.__all_objects_df['Name'].str.contains(r'\b'+object_name+r'\b',case=case)]


    def get_object_id(self, object_name:str,case=True):
        """
        Returns the ACM object id of the first occurrence of an object name in the __all_objects_df DataFrame.
        
        :param object_name: The name of the object to search for.
        :type object_name: str
        :param case: Whether to perform a case-sensitive search. Defaults to True.
        :type case: bool
        :return: The index of the first occurrence of the object name in the DataFrame.
        :rtype: int
        
        Returns the ACM object id of the first occurrence of the object name in the __all_objects_df DataFrame.
        """
        
        return self.__all_objects_df[self.__all_objects_df['Name'].str.contains(r'\b'+object_name+r'\b',case=case)].first_valid_index()


    def get_object_library_id(self, name=None, object_id:int=None, case=True ):
        """
        Retrieves the LibraryID of an object based on its name or object_id.

        :param name: The name of the object. (default: None)
        :type name: str
        :param object_id: The ID of the object. (default: None)
        :type object_id: int
        :param case: Determines whether the search is case-sensitive or not. (default: True)
        :type case: bool
        
        :return: The LibraryID of the object.
        :rtype: int

        Retrieves the LibraryID of an object based on its name or object_id. If the name parameter is provided, it searches for the object with a matching name in the __all_objects_df DataFrame and returns its LibraryID. If the object_id parameter is provided, it directly retrieves the LibraryID of the object with the specified ID from the __all_objects_df DataFrame.

        Example:
            >>> get_object_library_id(name='example_object')
            12345
        """
        if name:
            return self.__all_objects_df[self.__all_objects_df['Name'].str.contains(r'\b'+name+r'\b',case=case)]['LibraryID'].iloc[0]
        if object_id:
            self.__ensure_object_cached(object_id)
            return self.__all_objects_df.loc[[object_id]]['LibraryID'].iloc[0]
        
        
    def get_subobject(self, subobject_id):
        """
        Retrieves a subobject from the database based on the given subobject ID.

        :param subobject_id: The ID of the subobject to retrieve.
        :type subobject_id: int

        :return: A pandas DataFrame containing the subobject data.
        :rtype: pandas.DataFrame

        Retrieves a subobject from the database based on the given subobject ID. The function executes a SQL query to fetch the subobject data and returns it as a pandas DataFrame.

        Example:
            >>> get_subobject(123)
            DataFrame with subobject data
        """
        query = 'SELECT * FROM SubObjects WHERE SubObjectID=?'
        return pd.read_sql_query(query,self.__engine,params=(to_db_id(subobject_id, 'subobject_id'),),index_col='SubObjectID')
    

    def get_object_id_by_spa_id(self, spa_id):
        """
        Retrieves the object ID based on the given SPA ID.

        :param spa_id: The SPA ID of the object.
        :type spa_id: str
        :return: The ID of the object. Returns an empty string if no object is found.
        :rtype: str

        Retrieves the object ID from the 'Parameters' table in the database based on the provided SPA ID. If no object is found, an empty string is returned.
        
        Example:
            >>> get_object_id_by_spa_id('spa123')
            'object_id'
        """
        query = "SELECT * FROM Parameters WHERE Name='SolutionsProjectAcceleratorID' and Value=?"
        return pd.read_sql_query(query,self.__engine,params=(str(spa_id),),index_col='ObjectID')
    

    def get_raw_object(self, object_id):
        """
        Retrieves the raw object data from the database based on the given object ID.

        :param object_id: The ID of the object to retrieve.
        :type object_id: int
        :return: A DataFrame containing the raw object data.
        :rtype: pandas.DataFrame
        Retrieves the raw object data from the 'Objects' table in the database based on the provided object ID. Returns a DataFrame containing the raw object data.
        Example:
            >>> get_raw_object(123)
            DataFrame with raw object data
        """
        query = 'SELECT * FROM Objects WHERE ObjectID=?'
        return pd.read_sql_query(query,self.__engine,params=(to_db_id(object_id, 'object_id'),),index_col='ObjectID')
 
    

    def get_subobject_id(self, subobject_name, object_id):
        """
        Retrieves the ID of a subobject based on its name and parent object ID.

        :param subobject_name: The name of the subobject.
        :type subobject_name: str
        :param object_id: The ID of the parent object.
        :type object_id: int
        :return: The ID of the subobject. Returns an empty string if no subobject is found.
        :rtype: str

        Retrieves the ID of a subobject from the 'SubObjects' table in the database based on the provided subobject name and parent object ID.
        If no subobject is found, an empty string is returned.
        
        Example:
            >>> get_subobject_id('subobject_name', 123)
            'subobject_id'
        """
        query = 'SELECT * FROM SubObjects WHERE Name=? and ParentObjectID=?'
        subobjects_df = pd.read_sql_query(query,self.__engine,params=(str(subobject_name), to_db_id(object_id, 'object_id')),index_col='SubObjectID')
    
        if subobjects_df.empty:
            return ''
        return subobjects_df.index.array[0]
    

    def subscribe_to_filtered_objects_df(self, callback):
        """
        Subscribe to filtered objects DataFrame.

        :param callback: The callback function to be called when the filtered objects DataFrame is updated.
        :type callback: function
        :return: None
        :rtype: None

        This function adds the given callback function to the list of callbacks to be called when the filtered objects DataFrame is updated. The callback function will be called with the filtered objects DataFrame and the project ID as arguments.
        """
        if callback not in self.__get_objects_in_project_callbacks:
            self.__get_objects_in_project_callbacks.append(callback)

        callback(self.__df_filtered, self.__project_id)


    def subscribe_to_is_filtered(self, callback):
        """
        Subscribes a callback function to be called when the 'is_filtered' value changes.
        
        :param callback: The callback function to be called when the 'is_filtered' value changes.
        :type callback: function
        :return: None
        :rtype: None
        
        This function adds the given callback function to the list of callbacks to be called when the 'is_filtered' value changes. The callback function will be called with the current value of 'is_filtered' as an argument.
        
        Example:
            >>> subscribe_to_is_filtered(callback_function)
        """
        if callback not in self.__get_is_filtered_callbacks:
            self.__get_is_filtered_callbacks.append(callback)

        callback(self.__filtered)


    def set_objects_filter(self, filter=None):
        """
        Sets the filter for objects in the project.

        :param filter: The filter to be applied. Defaults to None.
        :type filter: dict
        :return: None
        :rtype: None
        
        This function sets the filter for objects in the project. It takes an optional filter parameter, which is a dictionary containing filter criteria. The function applies the filter to the data and updates the filtered data frame.
        
        Example:
            >>> set_objects_filter(filter={'types': {'filtered': True, 'values': ['type1', 'type2']}})
        """
        if self.__project_id and not self.check_if_project_exists() and self.__project_missing_callback:
            self.__project_missing_callback()

        self.__sanitize_filter(filter)
        self.__df_filtered = self.get_all_objects_in_project()

        self.__filtered = False

        try:
            if self.__filter['types']['filtered']:
                self.__filtered = True
                self.__df_filtered = self.__df_filtered[self.__df_filtered['CatalogNumber'].isin(self.__filter['types']['values'])]
        except:
            pass

        try:
            if self.__filter['users']['filtered']:
                self.__filtered = True
                self.__df_filtered = self.__df_filtered[self.__df_filtered['ChangeUser'].isin(self.__filter['users']['values'])]
        except:
            pass


        self.__post_changes()


    def __post_changes(self):
        """
        Updates all function that have subscribed to the filtered data and is_filtered value.

        :return: None
        :rtype: None

        This function updates all functions that have subscribed to the filtered data and is_filtered value. It calls the subscribed functions with the filtered data and is_filtered value as arguments.
        """

        for callback in self.__get_objects_in_project_callbacks:
            callback(self.__df_filtered, self.__project_id)

        for callback in self.__get_is_filtered_callbacks:
            callback(self.__filtered)


    def __sanitize_filter(self, filter):
        """
        Sanitizes the filter object.

        :param filter: The filter object to be sanitized. It can be a string or a dictionary.
        :type filter: str or dict
        :return: None
        
        This method sanitizes the filter object by converting it to a dictionary if it is a string.
        If the filter object is None, it does nothing.
        
        Example:
            >>> __sanitize_filter('{"name": "John"}')
            None
        """
        # Checks if filter object is String object, from the project settings
        if filter == '':
            filter == {}
        elif isinstance(filter, str):
            filter = json.loads(filter)

        # Checks if filter object is not None
        if filter != None:
            self.__filter = filter


    def get_object_filter(self):
        """
        Returns the object filter.

        :return: The object filter.
        :rtype: Any

        More detailed description of the function (if needed).

        Example:
            >>> example_function(1, 'test')
            'Result'
        """
        return self.__filter



    def get_all_subobjects_in_object(self, object_id, name_type=None, connection=None) -> pd.DataFrame:
        """
        Retrieves all subobjects in an object.

        :param object_id: The ID of the parent object.
        :type object_id: int
        :param name_type: The type of subobjects to retrieve (optional).
        :type name_type: str
        :return: A DataFrame containing all the subobjects.
        :rtype: pd.DataFrame

        Retrieves all subobjects in an object based on the given parent object ID. 
        If a name type is specified, only subobjects of that type will be retrieved.
        
        Example:
            >>> get_all_subobjects_in_object(1, 'test')
            pd.DataFrame(...)
        """
        if connection is None:
            connection = self.__engine
        
        query = 'SELECT * FROM SubObjects WHERE ParentObjectID=?'
        params = [to_db_id(object_id, 'object_id')]
        if name_type:
            query = query + ' and Type=?'
            params.append(str(name_type))
        return pd.read_sql_query(query, connection, params=tuple(params), index_col='SubObjectID')


    def get_subobject_in_object_with_name(self, object_id, subobject_name, name_type=None, connection=None) -> pd.DataFrame:
        """
        Retrieves all subobjects in an object.

        :param object_id: The ID of the parent object.
        :type object_id: int
        :param name_type: The type of subobjects to retrieve (optional).
        :type name_type: str
        :return: A DataFrame containing all the subobjects.
        :rtype: pd.DataFrame

        Retrieves all subobjects in an object based on the given parent object ID. 
        If a name type is specified, only subobjects of that type will be retrieved.
        
        Example:
            >>> get_all_subobjects_in_object(1, 'test')
            pd.DataFrame(...)
        """
        if connection is None:
            connection = self.__engine
        
        query = 'SELECT * FROM SubObjects WHERE ParentObjectID=? and Name=?'
        params = [to_db_id(object_id, 'object_id'), str(subobject_name)]
        if name_type:
            query = query + ' and Type=?'
            params.append(str(name_type))
        return pd.read_sql_query(query, connection, params=tuple(params), index_col='SubObjectID')

    
    def get_all_parameters_in_object(self, object_id, name_type=None):
        """
        Retrieves all parameters in an object.

        :param object_id: The ID of the object.
        :type object_id: int
        :param name_type: The type of the parameter name (optional).
        :type name_type: str
        :return: A DataFrame containing all parameters.
        :rtype: pandas.DataFrame

        Retrieves all parameters in an object based on the given object ID. If a name type is specified, only parameters with that name type will be returned. Returns a DataFrame containing all parameters.
        
        Example:
            >>> get_all_parameters_in_object(1, 'test')
            DataFrame(...)
        """

        query = 'SELECT * FROM Parameters WHERE ObjectID=?'
        params = [to_db_id(object_id, 'object_id')]
        if name_type:
            query = query + ' and Name=?'
            params.append(str(name_type))
        return pd.read_sql_query(query,self.__engine,params=tuple(params),index_col='ParameterID')



    def get_parameter_in_object(self, object_id,parameter_name) -> Dict:
        """
        Retrieves parameters in an object based on the object ID and parameter name.
        
        :param object_id: The ID of the object.
        :type object_id: int
        :param parameter_name: The name of the parameter.
        :type parameter_name: str
        :return: A dictionary containing the parameters.
        :rtype: dict
        
        Retrieves parameters from the database table 'Parameters' based on the provided object ID and parameter name.
        The parameters are returned as a dictionary where the keys are the parameter IDs and the values are the parameter details.
        
        Example:
            >>> get_parameters_in_object(1, 'test')
            {'param1': 'value1', 'param2': 'value2'}
        """
           
        query = 'SELECT * FROM Parameters WHERE ObjectID=? and Name=?'
        parameters_dict = pd.read_sql_query(query,self.__engine,params=(to_db_id(object_id, 'object_id'), str(parameter_name)),index_col='ParameterID').to_dict()

        return list(parameters_dict['Value'].values())[0] if 'Value' in parameters_dict else None
    

    
    def get_all_subparameters_in_subobject(self, subobject_id, name_type=None,connection=None):
        """
        Retrieves all subparameters in a subobject based on the given subobject ID and optional name type.
        
        :param subobject_id: The ID of the subobject.
        :type subobject_id: int
        :param name_type: The optional name type to filter the subparameters by.
        :type name_type: str, optional
        :return: A pandas DataFrame containing the retrieved subparameters.
        :rtype: pandas.DataFrame
        
        Retrieves all subparameters in a subobject based on the given subobject ID and optional name type. If a name type is provided, only subparameters with that name type will be returned. The subparameters are retrieved from the 'SubParameters' table in the database.
        
        Example:
            >>> get_all_subparameters_in_subobject(1, 'test')
            <pandas DataFrame>
        """
        if connection is None:
            connection = self.__engine

        query = 'SELECT * FROM SubParameters WHERE SubObjectID=?'
        params = [to_db_id(subobject_id, 'subobject_id')]
        if name_type:
            query = query + ' and Name=?'
            params.append(str(name_type))
        return pd.read_sql_query(query, connection, params=tuple(params), index_col='SubParameterID')


    def get_all_objects_with_acm_filter(self, filter=''):
        """
        Retrieves all objects with ACM filter applied.
        
        :param filter: Additional filter to apply (optional)
        :type filter: str
        :return: DataFrame containing filtered objects
        :rtype: pandas.DataFrame
        
        This function retrieves all objects with ACM filter applied. It takes an optional filter parameter to further refine the results. The function returns a pandas DataFrame containing the filtered objects.
        
        Example:
            >>> get_all_objects_with_acm_filter(filter='status = "active"')
            <pandas DataFrame object>
        """

        try:
            filter_sql, filter_params = parameterize_acm_filter(filter)
        except ValueError as error:
            logging.error('Rejected ACM library filter: %s', error)
            return pd.DataFrame()

        query = get_all_objects_with_acm_filter.format(filter=filter_sql)
        params = bind_params(get_all_objects_with_acm_filter_params, project_id=self.__project_id) + filter_params
        filtered_objects_df = pd.read_sql_query(query,self.__engine,params=params,index_col='ObjectID')

        return filtered_objects_df


    def get_all_subobjects_with_acm_filter(self, filter=''):
        """
        Retrieves all subobjects with ACM filter applied.

        :param filter: Additional filter to apply (optional)
        :type filter: str
        :return: DataFrame containing filtered subobjects
        :rtype: pandas.DataFrame

        This function retrieves all subobjects with an ACM filter applied. The filter parameter allows for additional filtering to be applied to the query. The function returns a pandas DataFrame containing the filtered subobjects.
        
        Example:
            >>> get_all_subobjects_with_acm_filter(filter='SubObjectStatus = "Active"')
            DataFrame with filtered subobjects
        """

        try:
            filter_sql, filter_params = parameterize_acm_filter(filter)
        except ValueError as error:
            logging.error('Rejected ACM library filter: %s', error)
            return pd.DataFrame()

        query = get_all_subobjects_with_acm_filter.format(filter=filter_sql)
        params = bind_params(get_all_subobjects_with_acm_filter_params, project_id=self.__project_id) + filter_params
        filtered_subobjects_df = pd.read_sql_query(query,self.__engine,params=params,index_col='SubObjectID')

        return filtered_subobjects_df


    def get_factory_talk_view_se_id(self):
        """
        Retrieves the FactoryTalk View SE ID from the database.

        :return: The FactoryTalk View SE ID.
        :rtype: str

        Retrieves the FactoryTalk View SE ID from the database by executing a SQL query to retrieve the object with the CatalogNumber 'FTViewSE'.
        """
        if self.__project_id:
            query = "SELECT * FROM Objects WHERE CatalogNumber='FTViewSE' and ProjectID=?"
            ftv_objects_df = pd.read_sql_query(query,self.__engine,params=(to_db_id(self.__project_id, 'project_id'),),index_col='ObjectID')

        if ftv_objects_df.empty:
            return ''
        return ftv_objects_df.index.array[0]
    

    def get_factory_talk_view_alarm_id(self):
        """
        Retrieves the FactoryTalk View Alarms ID from the database.

        :return: The FactoryTalk View Alarms ID.
        :rtype: str

        Retrieves the FactoryTalk View SE Alarms from the database by executing a SQL query to retrieve the object with the CatalogNumber 'FTViewSE'.
        """
        if self.__project_id:
            query = '''SELECT 
                o.ObjectID,
                o.ProjectID,
                o.Name,
                o.CatalogNumber,
                o.Description,
                o.LibraryID,
                o.LibraryType,
                l.Family,
                l.CoreType,
                l.Category,
                l.Status,
                l.ContentType,
                l.Class
            FROM 
                [ACM].[dbo].[Objects] o
            INNER JOIN 
                [ACM].[dbo].[RegisteredLibraries] l
                ON o.LibraryID = l.LibraryID WHERE l.Category='FTAE' and o.LibraryType='HMI' and o.ProjectID=?'''
            ftv_objects_df = pd.read_sql_query(query,self.__engine,params=(to_db_id(self.__project_id, 'project_id'),),index_col='ObjectID')

        if ftv_objects_df.empty:
            return ''
        return ftv_objects_df.index.array[0]


    def registered_library_exists(self, library_id):
        """
        Check if a registered library exists in the database.

        :param library_id: The ID of the library to check.
        :type library_id: str
        :return: True if the library exists, False otherwise.
        :rtype: bool

        Check if a registered library exists in the database by executing a SQL query to retrieve the library with the given ID.
        """
        query = 'SELECT * FROM RegisteredLibraries WHERE LibraryID=?'
        df = pd.read_sql_query(query,self.__engine,params=(str(library_id),),index_col='LibraryID')

        if df.empty:
            return False
        return True

    def get_reference_type_number(self, type):
        """
        Retrieves the ACM reference type number for a given type.

        :param type: The type of the reference.
        :type type: str

        :return: The reference type number.
        :rtype: int

        Retrieves the reference type number for a given type from the ReferenceTypesEnum table in the database.

        Example:
            >>> get_reference_type_number('example')
            1
        """
        query = 'SELECT * FROM ReferenceTypesEnum WHERE Name=?'
        return pd.read_sql_query(query,self.__engine,params=(str(type),),index_col='RefType').first_valid_index()


    SQL_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S.000'

    def create_subobject(self, object_id,  subobject_data, subobject_parameters):
        """
        Creates a subobject with the given object ID, subobject data, and subobject parameters.
        :param object_id: The ID of the parent object.
        :type object_id: int
        :param subobject_data: The data of the subobject.
        :type subobject_data: dict
        :param subobject_parameters: The parameters of the subobject.
        :type subobject_parameters: dict
        :return: The name of the created subobject.
        :rtype: str

        This function creates a subobject using the provided object ID, subobject data, and subobject parameters. It generates the subobject name based on the template specified in the subobject data and the values of the subobject parameters. The subobject parameters are inserted into the database using the provided SQL command.
        
        Example:
            >>> create_subobject(1, {'Name': 'Subobject_{name}'}, {'name': {'DType': 'str', 'DVal': 'Test'}})
            'Subobject_001'
        """
        subobject_parameters_sql_values = []
        values = {}
        for subparameter_name, data in subobject_parameters.items():

            ref_type = self.get_reference_type_number(data['RType'])
            if ref_type is None:
                ref_type = 1
            if data['AInc'] == 'true':
                value = self.__autoincrement_parameter_value(object_id,subobject_data['Type'],subparameter_name,data['DVal'],data['Max'])
                value ="{:02d}".format(int(value))
            else:
                value = data['DVal']

            values[subparameter_name] = value

            subparameter_entry = bind_params(
                subobject_subparameter_value_template_params
                ,name=subparameter_name
                ,data_type=data['DType']
                ,value=value
                ,ref_type=ref_type
                ,change_date=datetime.datetime.now(datetime.timezone.utc).strftime(self.SQL_DATETIME_FORMAT)
                ,user=os.getlogin()
                ,parameter_help=data['ParH']
                ,ref_value=''
            )
            subobject_parameters_sql_values.append(subparameter_entry)

        subobject_name_template: str = subobject_data['Name']
        subobject_name = render_name_template(subobject_name_template, values)

        create_subobject_sql_cmd = create_subobject.format(
            subparameter_values=','.join([subobject_subparameter_value_template] * len(subobject_parameters_sql_values)))
        create_subobject_sql_params = bind_params(
            create_subobject_params,
            subobject_name=subobject_name,
            parent_object_id=object_id,
            subobject_display_name=subobject_data['Type'],
            subobject_type=subobject_data['Type'],
            date_time=datetime.datetime.now(datetime.timezone.utc).strftime(self.SQL_DATETIME_FORMAT),
            user=os.getlogin(),
            subobject_description='',
            description_override=0,
        ) + tuple(param for entry in subobject_parameters_sql_values for param in entry)

        @db_connector(self.__connection_string)
        def query(cnn):
            try:
                cur = cnn.cursor()
                cur.execute(create_subobject_sql_cmd, create_subobject_sql_params)
                return subobject_name
            except Exception as error:
                raise ValueError(error)


        try:
            return query()
        except Exception as error:
            raise ValueError(error)
        

    def non_commit_create_subobject(self, object_id,  subobject_data, subobject_parameters, previous_values=None):
        """
        Creates a subobject with the given object ID, subobject data, and subobject parameters.
        :param object_id: The ID of the parent object.
        :type object_id: int
        :param subobject_data: The data of the subobject.
        :type subobject_data: dict
        :param subobject_parameters: The parameters of the subobject.
        :type subobject_parameters: dict
        :return: The name of the created subobject.
        :rtype: str

        This function creates a subobject using the provided object ID, subobject data, and subobject parameters. It generates the subobject name based on the template specified in the subobject data and the values of the subobject parameters. The subobject parameters are inserted into the database using the provided SQL command.
        
        Example:
            >>> create_subobject(1, {'Name': 'Subobject_{name}'}, {'name': {'DType': 'str', 'DVal': 'Test'}})
            'Subobject_001'
        """
        subobject_parameters_sql_values = []
        values = {}
        for subparameter_name, data in subobject_parameters.items():

            ref_type = self.get_reference_type_number(data['RType'])
            if ref_type is None:
                ref_type = 1
            if data['AInc'] == 'true':
                previous_value = previous_values[subparameter_name] if previous_values and subparameter_name in previous_values else None
                value = self.__autoincrement_parameter_value(object_id,subobject_data['Type'],subparameter_name,data['DVal'],data['Max']
                                                             ,previous_value=previous_value)
                value ="{:02d}".format(int(value))
            else:
                value = data['DVal']

            values[subparameter_name] = value

            subparameter_entry = bind_params(
                subobject_subparameter_value_template_params
                ,name=subparameter_name
                ,data_type=data['DType']
                ,value=value
                ,ref_type=ref_type
                ,change_date=datetime.datetime.now(datetime.timezone.utc).strftime(self.SQL_DATETIME_FORMAT)
                ,user=os.getlogin()
                ,parameter_help=data['ParH']
                ,ref_value=''
            )
            subobject_parameters_sql_values.append(subparameter_entry)

        subobject_name_template: str = subobject_data['Name']
        subobject_name = render_name_template(subobject_name_template, values)

        return subobject_name, values

    
    def get_subobject_description(self, subobject_id):
        """
        Retrieves the description of a subobject based on the subobject ID.

        :param subobject_id: The ID of the subobject.
        :type subobject_id: int
        :return: The description of the subobject.
        :rtype: str

        Retrieves the description of a subobject from the database based on the provided subobject ID.
        """
        query = 'SELECT * FROM SubObjects WHERE SubObjectID=?'
        subobject_df = pd.read_sql_query(query,self.__engine,params=(to_db_id(subobject_id, 'subobject_id'),),index_col='SubObjectID')

        if subobject_df.empty:
            return ''
        return subobject_df['Description'].iloc[0]
    

    def set_subobject_description(self, subobject_id, description):
        """
        Sets the description of a subobject based on the subobject ID.

        :param subobject_id: The ID of the subobject.
        :type subobject_id: int
        :param description: The description to set.
        :type description: str
        :return: None
        :rtype: None

        Sets the description of a subobject in the database based on the provided subobject ID.
        """
        sql = 'UPDATE SubObjects SET Description=? WHERE SubObjectID=?'
        params = ('' if description is None else str(description), to_db_id(subobject_id, 'subobject_id'))

        @db_connector(self.__connection_string)
        def query(cnn):
            try:
                cur = cnn.cursor()
                cur.execute(sql, params)
            except Exception as error:
                raise ValueError(error)

        try:
            query()
        except Exception as error:
            raise ValueError(error)


    def __autoincrement_parameter_value(self,object_id,subobject_type, subparameter_name,default, max_value, connection=None,previous_value=None):
        """
        Autoincrements the parameter index value for a subobject based on the given object_id, subobject_type, subparameter_name, default, and max.
        
        :param object_id: The ID of the object.
        :type object_id: int
        :param subobject_type: The type of the subobject.
        :type subobject_type: str
        :param subparameter_name: The name of the subparameter.
        :type subparameter_name: str
        :param default: The default value.
        :type default: int
        :param max: The maximum value.
        :type max: int
        :return: The autoincremented value.
        :rtype: int

        :raises ValueError: If there is an error executing the query.

        This function autoincrements the parameter value based on the given object_id, subobject_type, subparameter_name, default, and max.
        It executes a SQL query to get all subobjects in the object and all subparameters in the subobject. It then increments the value.
        """
        subobjects_df = self.get_all_subobjects_in_object(object_id, subobject_type, connection=connection)
        value = int(default)
        for subobject_id, _ in subobjects_df.iterrows():
            subparameter_df = self.get_all_subparameters_in_subobject(subobject_id, subparameter_name, connection=connection)
            for _, sub_data in subparameter_df.iterrows():
                value = max(int(sub_data['Value']) + 1, value)
        if previous_value:
            value = int(previous_value) + 1
            
        if value > int(max_value):
            
            raise ValueError("Max amount number of subobjected created")
        return value
            



    def create_new_hmi_display_in_acm(self, display_name,factory_talk_view_se_id,width,height):
        """
        Creates a new HMI display in the ACM project.

        :param display_name: The name of the display.
        :type display_name: str
        :param factory_talk_view_se_id: The ID of the FactoryTalk View SE.
        :type factory_talk_view_se_id: int
        :param width: The width of the display.
        :type width: int
        :param height: The height of the display.
        :type height: int
        :return: The result of the query.
        :rtype: Any

        :raises ValueError: If there is an error executing the query.
        
        This function creates a new HMI display in the ACM project. It executes a SQL query to insert the display details into the database.
        If an error occurs during the query execution, a ValueError is raised.
        
        Example:
            >>> create_new_hmi_display_in_acm('Display1', 1234, 800, 600)
            'Result'
        """
        logging.info('Creating display with display name: '+display_name+' in project: '+str(self.__project_id)+'.')

        @db_connector(self.__connection_string)
        def query(cnn):
            try:
                cur = cnn.cursor()
                cur.execute(create_display_sql_command, bind_params(create_display_sql_command_params, display_name=display_name,
                            width=width,
                            height=height,
                            factory_talk_view_se_id=factory_talk_view_se_id,
                            date_time=datetime.datetime.now(datetime.timezone.utc).strftime(self.SQL_DATETIME_FORMAT),
                            user=os.getlogin())) # or something else 
            except Exception as error:
                raise ValueError(error)

        try:
            return query()
        except Exception as error:
            raise ValueError(error)


    def create_new_hmi_line_in_acm(self, display_name,factory_talk_view_se_id,rect):
        """
        Creates a new HMI line in the ACM project.

        :param display_name: The display name of the new line.
        :type display_name: str
        :param factory_talk_view_se_id: The ID of the FactoryTalk View SE.
        :type factory_talk_view_se_id: int
        :param rect: The coordinates of the line's rectangle (x1, y1, x2, y2).
        :type rect: tuple
        :return: The result of the query execution.
        :rtype: Any
        :raises ValueError: If there is an error executing the query.
        
        This function creates a new HMI line in the ACM project. It generates a line name based on the display name and rectangle coordinates. The line is created using the provided parameters and the current date and time. The function returns the result of the query execution.
        
        Example:
            >>> create_new_hmi_line_in_acm('Line1', 123, (10, 20, 30, 40))
            'Result'
        """

        logging.info('Creating display with display name: '+display_name+' in project: '+str(self.__project_id)+'.')

        x1,y1,x2,y2 = rect

        line_name = display_name+'_'+str(x1)+'_'+str(y1)+'_'+str(x2)+'_'+str(y2)

        @db_connector(self.__connection_string)
        def query(cnn):
            try:
                cur = cnn.cursor()
                cur.execute(create_line_sql_command, bind_params(create_line_sql_command_params, display_name=display_name,
                            factory_talk_view_se_id=factory_talk_view_se_id,
                            project_id=self.__project_id,
                            controller_id=self.__controller_id,
                            parent_object_id=self.__controller_object_id,
                            line_name=line_name,
                            X1=x1,
                            Y1=y1,
                            X2=x2,
                            Y2=y2,
                            width=3,
                            color='A0A0A0',
                            date_time=datetime.datetime.now(datetime.timezone.utc).strftime(self.SQL_DATETIME_FORMAT),
                            user=os.getlogin())) # or something else 
            except Exception as error:
                raise ValueError(error)

        try:
            return query()
        except Exception as error:
            raise ValueError(error)


    def create_new_hmi_image_in_acm(self,image_id,display_name,factory_talk_view_se_id,image_filename,rect):
        """
        Creates a new HMI image in ACM.
        :param display_name: The display name of the HMI image.
        :type display_name: str
        :param factory_talk_view_se_id: The ID of the FactoryTalk View SE.
        :type factory_talk_view_se_id: int
        :param image_filename: The filename of the image.
        :type image_filename: str
        :param rect: The coordinates of the image rectangle in the format (x1, y1, x2, y2).
        :type rect: tuple
        :return: The result of the query.
        :rtype: Any
        :raises ValueError: If an error occurs during the query execution.

        Creates a new HMI image in ACM by executing a SQL command with the provided parameters. The SQL command is executed using a database connector decorator.

        Example:
            >>> create_new_hmi_image_in_acm('Display 1', 123, 'image.png', (10, 20, 30, 40))
            'Result'
        """
        
        x1,y1,x2,y2 = rect

        image_name = display_name+'_'+image_filename+'_'+str(x1)+'_'+str(y1)

        @db_connector(self.__connection_string)
        def query(cnn):
            try:
                cur = cnn.cursor()
                cur.execute(create_image_sql_command, bind_params(create_image_sql_command_params, display_name=display_name,
                            factory_talk_view_se_id=factory_talk_view_se_id,
                            project_id=self.__project_id,
                            controller_id=self.__controller_id,
                            parent_object_id=self.__controller_object_id,
                            image_name=image_name.replace(' ','_'),
                            X1=x1,
                            Y1=y1,
                            X2=x2,
                            Y2=y2,
                            filename=image_filename,
                            image_id=image_id,
                            date_time=datetime.datetime.now(datetime.timezone.utc).strftime(self.SQL_DATETIME_FORMAT),
                            user=os.getlogin())) # or something else 
            except Exception as error:
                raise ValueError(error)

        try:
            return query()
        except Exception as error:
            raise ValueError(error)


    def create_new_hmi_page_link_in_acm(self, display_name,page_link_id,factory_talk_view_se_id,navigate_to_display_name,center_point,orientation
                                        ,label=None,name_token=None):
        """
        Creates a new HMI page link in ACM.
        
        :param display_name: The display name.
        :type display_name: str
        :param page_link_id: The ID of the page link.
        :type page_link_id: string
        :param factory_talk_view_se_id: The FactoryTalk View SE ID.
        :type factory_talk_view_se_id: int
        :param navigate_to_display_name: The display name to navigate to. Empty for an unlinked page link.
        :type navigate_to_display_name: str
        :param center_point: The center point coordinates (x, y).
        :type center_point: tuple
        :param orientation: The orientation of the page link.
        :type orientation: str
        :param label: The caption shown on the page link. Defaults to the navigation target.
        :type label: Optional[str]
        :param name_token: The middle part of the generated ACM object name. Defaults to the navigation target.
        :type name_token: Optional[str]
        :return: The result of the query.
        :rtype: Any
        
        Creates a new HMI page link in ACM by executing a SQL command with the provided parameters.
        The SQL command is executed using a database connector decorator.
        
        Example:
            >>> create_new_hmi_page_link_in_acm('Page1', 123, 'Page2', (100, 200), 'landscape')
            'Result'
        """
        
        center_x,center_y = center_point

        if not name_token:
            name_token = navigate_to_display_name

        if label is None:
            label = navigate_to_display_name.replace('_',' ')


        page_link_name = display_name+'_to_'+name_token+'_'+str(center_x)+'_'+str(center_y)


        @db_connector(self.__connection_string)
        def query(cnn):
            try:
                cur = cnn.cursor()
                cur.execute(create_page_link_sql_command, bind_params(create_page_link_sql_command_params, display_name=display_name,
                            page_link_id=page_link_id,
                            factory_talk_view_se_id=factory_talk_view_se_id,
                            project_id=self.__project_id,
                            controller_id=self.__controller_id,
                            parent_object_id=self.__controller_object_id,
                            page_link_name=page_link_name,
                            center_x=center_x,
                            center_y=center_y,
                            orientation=orientation,
                            label=label,
                            navigate_to_display_name=navigate_to_display_name,
                            date_time=datetime.datetime.now(datetime.timezone.utc).strftime(self.SQL_DATETIME_FORMAT),
                            user=os.getlogin())) # or something else 
            except Exception as error:
                raise ValueError(error)

        try:
            return query()
        except Exception as error:
            raise ValueError(error)


    def position_control_module_in_acm(self, display_name,factory_talk_view_se_id,control_module_id,position,orientation):
        """
        Positions the control module in the ACM.

        :param display_name: The display name of the control module.
        :type display_name: str
        :param factory_talk_view_se_id: The ID of the FactoryTalk View SE.
        :type factory_talk_view_se_id: int
        :param control_module_id: The ID of the control module.
        :type control_module_id: int
        :param position: The position of the control module.
        :type position: tuple
        :param orientation: The orientation of the control module.
        :type orientation: str
        :return: The result of the query.
        :rtype: Any

        :raises ValueError: If an error occurs during the write operation

        Positions the control module in the ACM by executing a SQL command with the given parameters.
        
        Example:
            >>> position_control_module_in_acm('Module1', 1234, 5678, (10, 20), 'up')
            'Result of the query'
        """
        position_x,position_y = position

        
        @db_connector(self.__connection_string)
        def query(cnn):
            try:
                cur = cnn.cursor()
                cur.execute(position_control_module_sql_command, bind_params(position_control_module_sql_command_params, display_name=display_name,
                            factory_talk_view_se_id=factory_talk_view_se_id,
                            control_module_id=control_module_id,
                            position_x=position_x,
                            position_y=position_y,
                            orientation=orientation,
                            date_time=datetime.datetime.now(datetime.timezone.utc).strftime(self.SQL_DATETIME_FORMAT),
                            user=os.getlogin())) # or something else 
            except Exception as error:
                raise ValueError(error)

        try:
            return query()
        except Exception as error:
            raise ValueError(error)
        


    def get_display_objects(self, display_name, factory_talk_view_se_id):
        """
        Retrieves display objects from the ACM database.

        :param display_name: The name of the display.
        :type display_name: str
        :param factory_talk_view_se_id: The ID of the FactoryTalk View SE.
        :type factory_talk_view_se_id: int
        :return: A DataFrame containing the display objects.
        :rtype: pandas.DataFrame

        Retrieves display objects from the ACM database based on the provided display name and FactoryTalk View SE ID.
        
        Example:
            >>> get_display_objects('Display1', 1234)
            DataFrame with display objects
        """
        query, params = get_display_objects_sql_command, bind_params(get_display_objects_sql_command_params, 
            display_name=display_name,
            factory_talk_view_se_id=factory_talk_view_se_id
        )
        objects_in_display_df = pd.read_sql_query(query, self.__engine, params=params, index_col='ObjectID')
        
        return objects_in_display_df
    
    def get_display_object(self,object_id):
        """
        Retrieves a specific display object from the ACM database.

        :param display_name: The name of the display.
        :type display_name: str
        :param factory_talk_view_se_id: The ID of the FactoryTalk View SE.
        :type factory_talk_view_se_id: int
        :param object_id: The ID of the object to retrieve.
        :type object_id: int
        :return: A DataFrame containing the display object information.
        :rtype: pandas.DataFrame

        Retrieves a specific display object from the ACM database based on the provided display name, FactoryTalk View SE ID, and object ID.
        
        Example:
            >>> get_display_object('Display1', 1234, 5678)
            DataFrame with display object information
        """
        query, params = get_display_object_sql_command, bind_params(get_display_object_sql_command_params, 
            object_id=object_id
        )
        return pd.read_sql_query(query, self.__engine, params=params, index_col='ObjectID').iloc[0]
    
    def get_display(self, display_name, factory_talk_view_se_id):
        """
        Retrieves a specific display from the ACM database.

        :param display_name: The name of the display.
        :type display_name: str
        :param factory_talk_view_se_id: The ID of the FactoryTalk View SE.
        :type factory_talk_view_se_id: int
        :return: A DataFrame containing the display information.
        :rtype: pandas.DataFrame

        Retrieves a specific display from the ACM database based on the provided display name and FactoryTalk View SE ID.
        
        Example:
            >>> get_display('Display1', 1234)
            DataFrame with display information
        """
        query, params = get_display_sql_command, bind_params(get_display_sql_command_params, 
            display_name=display_name,
            factory_talk_view_se_id=factory_talk_view_se_id
        )
        return pd.read_sql_query(query, self.__engine, params=params, index_col='SubObjectID')

    def get_all_displays(self, factory_talk_view_se_id):
        """
        Retrieves all displays from the ACM database.

        :param factory_talk_view_se_id: The ID of the FactoryTalk View SE.
        :type factory_talk_view_se_id: int
        :return: A DataFrame containing all displays.
        :rtype: pandas.DataFrame

        Retrieves all displays from the ACM database based on the provided FactoryTalk View SE ID.
        
        Example:
            >>> get_all_displays(1234)
            DataFrame with all displays
        """
        query, params = get_displays_sql_command, bind_params(get_displays_sql_command_params, factory_talk_view_se_id=factory_talk_view_se_id) # or something else 
        return pd.read_sql_query(query, self.__engine, params=params, index_col='SubObjectID')


    def write_parameter_value(self, value, object_id, parameter, ref_type='1', ref_value=''):
        """
        Writes a parameter value to the database for a given ACM object.

        :param value: The value to be written.
        :type value: Any
        :param object_id: The ID of the object.
        :type object_id: int
        :param parameter: The parameter name.
        :type parameter: str
        :param ref_type: The reference type (default is '1').
        :type ref_type: str
        :param ref_value: The reference value (default is '').
        :type ref_value: str
        :return: None
        :rtype: None

        :raises ValueError: If an error occurs during the write operation
        
        This function writes the given parameter value to the database for the specified object. It uses a database connector
        to establish a connection and execute the SQL command to write the value. If an error occurs during the execution,
        a ValueError is raised.
        
        Example:
            >>> write_parameter_value(10, 1, 'param1')
        """
    
        @db_connector(self.__connection_string)
        def query(cnn):
            try:
                cur = cnn.cursor()
                cur.execute(write_parameter_value_and_reftype_sql_command, bind_params(write_parameter_value_and_reftype_sql_command_params, parameter=parameter,
                            object_id=object_id,
                            ref_type=ref_type,
                            ref_value=ref_value,
                            value=value)) # or something else 
            except Exception as error:
                raise ValueError(error)

        try:
            return query()
        except Exception as error:
            raise ValueError(error)



    def write_subparameter_value(self, value, subobject_id, subparameter, ref_type='1', ref_value=''):
        """
        Writes the value of a subparameter for a given subobject ID.
        
        :param value: The value to be written.
        :type value: Any
        :param subobject_id: The ID of the subobject.
        :type subobject_id: int
        :param subparameter: The subparameter to be written.
        :type subparameter: str
        :param ref_type: The reference type (default is '1').
        :type ref_type: str
        :param ref_value: The reference value (default is '').
        :type ref_value: str
        :return: The result of the write operation.
        :rtype: Any
        
        :raises ValueError: If an error occurs during the write operation

        Example:
            >>> write_subparameter_value(10, 1, 'subparam', '2', 'ref')
            'Result'
        """
    
        @db_connector(self.__connection_string)
        def query(cnn):
            try:
                cur = cnn.cursor()
                cur.execute(write_subparameter_value_and_reftype_sql_command, bind_params(write_subparameter_value_and_reftype_sql_command_params, subparameter=subparameter,
                            subobject_id=subobject_id,
                            ref_type=ref_type,
                            ref_value=ref_value,
                            value=value)) # or something else 
            except Exception as error:
                raise ValueError(error)

        try:
            return query()
        except Exception as error:
            raise ValueError(error)


    def delete_subobject(self, subobject_id):
        """
        Deletes a subobject from the database.

        :param subobject_id: The ID of the subobject to delete.
        :type subobject_id: int

        :return: None
        :rtype: None

        This function deletes a subobject and its associated subparameters from the database.
        
        Example:
            >>> delete_subobject(123)
        """
        @db_connector(self.__connection_string)
        def query(cnn):
            try:
                cur = cnn.cursor()
                cur.execute(delete_subobject_sql_command, bind_params(delete_subobject_sql_command_params, subobject_id=subobject_id))
                cnn.commit()
            except Exception as error:
                raise ValueError(error)

        try:
            return query()
        except Exception as error:
            raise ValueError(error)



        

    


        

    