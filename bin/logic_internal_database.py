
import logging
import uuid
import os
import atexit
import threading
import time
from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware
try:
    from bin.logic_reader_write_lock import RWLock
except ImportError:
    from logic_reader_write_lock import RWLock

class Database():
    '''
    Represents a database for managing project documents and settings.
    Attributes:
        DRAWING (str): Constant representing the drawing document type.
        TEXT (str): Constant representing the text document type.
        TABLE (str): Constant representing the table document type.
    '''

    DRAWING = 'DRAWING'
    IMAGE = 'IMAGE'
    TEXT = 'TEXT'
    TABLE = 'TABLE'


    def __init__(self, project_name):
        """
        Initializes the logic_internal_database object.
        
        :param project_name: The name of the project.
        :type project_name: str
        :return: None
        :rtype: None

        This method initializes the logic_internal_database object by creating the necessary directories and tables for storing data.
        """
        
        if project_name is None:
            return
        
        self.__dir = './projects/'+project_name+'/database'

        if not os.path.exists(self.__dir):
            os.makedirs(self.__dir,  exist_ok=True)
            
        self.__open_db()
        self.__rwlock = RWLock()

        # Flush timer mechanism
        self.__flush_timer = None
        self.__flush_lock = threading.Lock()

        # Ensure a best-effort flush on interpreter exit even if __del__ never runs.
        atexit.register(self.close_db)

        self.__unapproved_text_link_update_func = []
        self.__unapproved_text_link_detailed_update_func = []
        self.__rejected_text_link_update_func = []
        self.__linked_text_regex_update_func = None
        self.__object_assignment_regex_update_func = None
        self.__update_element_on_hmi_display_update_func = []
        self.__save_bulk_control_modules_threads = []
        self.__update_roi_on_document_viewer_func = None
        self.__update_roi_on_tool_viewer_func = None

    def __open_db(self):
        self.__db = TinyDB(self.__dir+'/database.json', storage=CachingMiddleware(JSONStorage))
        self.__db.default_table_name = "settings"
        self.__documents_table = self.__db.table('documents')
        self.__documents_roi_table = self.__db.table('rois')
        self.__control_modules_table = self.__db.table('control_modules')
        self.__control_modules_graphic_templates_table = self.__db.table('control_modules_graphic_templates')
        self.__linked_graphic_pairs = self.__db.table('linked_graphic_pairs')
        self.__static_graphics_table = self.__db.table('static_graphics')
        self.__static_graphics_graphic_templates_table = self.__db.table('static_graphics_graphic_templates')
        self.__hmi_displays_table = self.__db.table('displays')
        self.__page_link_roi_to_page_link_table = self.__db.table('displays_roi_to_page_link')
        self.__hmi_displays_graphic_templates_table = self.__db.table('hmi_displays_graphic_templates')
        self.__unapproved_text_links_table = self.__db.table('unapproved_text_links')
        self.__approved_text_links_table = self.__db.table('approved_text_links')
        self.__rejected_text_links_table = self.__db.table('rejected_text_links')
        self.__linked_text_regexes_table = self.__db.table('linked_text_regexes')
        self.__object_assignment_regexes_table = self.__db.table('object_assignment_regexes')
        self.__build_hmi_displays_table = self.__db.table('build_hmi_displays')
        self.__tables_already_processed_by_llm = self.__db.table('tables_already_processed_by_llm')
        self.__llm_library_prompts_table = self.__db.table('llm_library_prompts')
        self.__run_lazy_migrations()


    def __run_lazy_migrations(self):
        """One-shot repairs for legacy database.json files. Idempotent."""
        # Stamp missing ids on legacy documents_table rows.
        for row in self.__documents_table.all():
            if 'id' not in row:
                self.__documents_table.update({'id': str(uuid.uuid4())}, doc_ids=[row.doc_id])

        # Text-link state machine: an id must live in at most one of approved/rejected.
        approved_ids = {r['id']: r for r in self.__approved_text_links_table.all() if 'id' in r}
        rejected_ids = {r['id']: r for r in self.__rejected_text_links_table.all() if 'id' in r}
        collisions = approved_ids.keys() & rejected_ids.keys()
        if collisions:
            query = Query()
            for cid in collisions:
                a_ts = approved_ids[cid].get('timestamp', 0) or 0
                r_ts = rejected_ids[cid].get('timestamp', 0) or 0
                # Keep the newer decision, drop the older side.
                loser = self.__rejected_text_links_table if a_ts >= r_ts else self.__approved_text_links_table
                loser.remove(query.id == cid)
            logging.info("Reconciled %d text-link id(s) present in both approved and rejected tables.", len(collisions))


    def subscribe_to_changes_for_document_viewer(self, func):
        self.__update_roi_on_document_viewer_func = func

    def subscribe_to_changes_for_tool_viewer(self, func):   
        self.__update_roi_on_tool_viewer_func = func

    def __start_flush_timer(self):
        """
        Starts or resets the 5-second flush timer.
        If another write operation occurs, this method will cancel the existing timer and start a new one.
        """
        with self.__flush_lock:
            # Cancel existing timer if it exists
            if self.__flush_timer is not None:
                self.__flush_timer.cancel()
            
            # Start new timer
            self.__flush_timer = threading.Timer(5.0, self.__flush_database)
            self.__flush_timer.start()

    def __flush_database(self):
        """
        Flushes the database to ensure all writes are persisted to disk.
        This method is called automatically by the timer after 5 seconds of no write operations.
        """
        try:
            with self.__flush_lock:
                if self.__db is not None:
                    # Force the cached middleware to write to disk
                    self.__db.storage.flush()
                    logging.info("Database flushed to disk after 5 seconds of inactivity")
                self.__flush_timer = None
        except Exception as e:
            logging.error(f"Error during database flush: {e}")

    def __trigger_write_event(self):
        """
        Called after every write operation to restart the flush timer.
        """
        self.__start_flush_timer()


    def __flush_now(self):
        """Flush the caching middleware immediately (used for durability-critical writes)."""
        try:
            with self.__flush_lock:
                if getattr(self, '_Database__db', None) is not None:
                    self.__db.storage.flush()
        except Exception:
            logging.exception("Immediate database flush failed")


    def save_llm_library_prompts(self, library_id, Core_type, CatalogNumber, prompts_dict):
        """
        Saves an LLM library prompt to the internal database.

        :param library_id: The ID of the library.
        :type library_id: str
        :param prompts_dict: The dictionary containing the prompts.
        :type prompts_dict: dict
        :return: None
        :rtype: None
        """
        
        # Check if entry exists 
        query = Query()
        with self.__rwlock.w_locked():
            self.__llm_library_prompts_table.upsert({
                    'library_id': library_id,
                    'core_type': Core_type,
                    'catalog_number': CatalogNumber,
                    'prompts': prompts_dict
                    }, (query.library_id == library_id)
                    | ((query.catalog_number == CatalogNumber) & (query.core_type == Core_type)))

        self.__trigger_write_event()


    def get_llm_library_prompts(self, library_id, Core_type, CatalogNumber):
        """
        Retrieves an LLM library prompt from the internal database.

        :param library_id: The ID of the library.
        :type library_id: str
        :return: The prompts dictionary if found, otherwise None.
        :rtype: dict or None
        """
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__llm_library_prompts_table.search((query.library_id == library_id) 
                                                             | ((query.catalog_number == CatalogNumber) & (query.core_type == Core_type)))
        
        if result: 
            return result[0]['prompts']
        else:
            return {}


    def save_table_already_processed_by_llm(self, path, pno, bbox, model_name):
        """
        Saves the tables already processed by LLM to the internal database.

        :param table_data: The table data to be saved.
        :type table_data: dict
        :return: None
        :rtype: None
        """
        
        # Check if entry exists 
        query = Query()
        with self.__rwlock.w_locked():
            timestamp = int(round(time.time() * 1000))
            bbox_string = '-'.join(str(int(round(coord))) for coord in bbox)
            table_data = {
                'path': path,
                'pno': pno,
                'bbox': bbox_string,
                'model_name': model_name
            }
            table_data['timestamp'] = timestamp
            self.__tables_already_processed_by_llm.upsert(table_data, (query.bbox == table_data['bbox']) 
                                                          & (query.path == table_data['path']) 
                                                          & (query.pno == table_data['pno']))

        self.__trigger_write_event()


    def get_table_already_processed_by_llm(self, path, pno, bbox):
        """
        Retrieves a table already processed by LLM from the internal database.

        :param path: The path of the document.
        :type path: str
        :param pno: The page number of the document.
        :type pno: int
        :param bbox: The bounding box of the table.
        :type bbox: list
        :return: The table data if found, otherwise None.
        :rtype: dict or None
        """
        bbox_string = '-'.join(str(int(round(coord))) for coord in bbox)
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__tables_already_processed_by_llm.search((query.path == path) 
                                                                   & (query.pno == pno) 
                                                                   & (query.bbox == bbox_string))
        
        if result: 
            return result[0]
        else:
            return None


    def insert_project_document(self, file_name, path, type):
        """
        Inserts (or refreshes) a project document row keyed by path.

        Returns the document id (stable across refreshes for the same path).
        """
        query = Query()
        with self.__rwlock.w_locked():
            existing = self.__documents_table.get(query.path == path)
            doc_id = existing.get('id') if existing else str(uuid.uuid4())
            self.__documents_table.upsert({
                'id': doc_id,
                'timestamp': int(round(time.time() * 1000)),
                'name': file_name,
                'path': path,
                'type': type
            }, query.path == path)

        self.__trigger_write_event()
        return doc_id


    def delete_project_document(self, name):
        """
        Deletes project documents with the given name and cascades ROI removal.
        """
        query = Query()
        with self.__rwlock.w_locked():
            matches = self.__documents_table.search(query.name == name)
            self.__documents_table.remove(query.name == name)

        if len(matches) > 1:
            logging.warning("delete_project_document('%s') removed %d rows (expected 1)", name, len(matches))
        for row in matches:
            row_path = row.get('path')
            if row_path:
                self.delete_project_document_roi(row_path)

        self.__trigger_write_event()


    def delete_project_document_by_id(self, doc_id):
        """
        Deletes a project document by id and cascades ROI removal.
        """
        query = Query()
        with self.__rwlock.w_locked():
            matches = self.__documents_table.search(query.id == doc_id)
            self.__documents_table.remove(query.id == doc_id)

        for row in matches:
            row_path = row.get('path')
            if row_path:
                self.delete_project_document_roi(row_path)

        self.__trigger_write_event()


    def insert_project_document_roi(self, path, roi):
        """
        Inserts a project document ROI (Region of Interest)into the database.

        :param path: The path of the document.
        :type path: str
        :param roi: The ROI (Region of Interest) list.
        :type roi: list
        :return: None
        :rtype: None

        This function inserts a project document ROI into the database. It checks if an entry already exists for the given path and updates it if it does, otherwise it inserts a new entry with the document name and ROI list.
        
        Example:
            >>> insert_project_document_roi('/path/to/document', 0.5)
            None
        """
        
        
        # Check if entry exists 
        query = Query()
        with self.__rwlock.w_locked():
            self.__documents_roi_table.upsert({
                    'document_name': path,
                    'roi': roi
                    }, query.document_name == path)
        
        self.__trigger_write_event()

        if self.__update_roi_on_document_viewer_func:
            self.__update_roi_on_document_viewer_func(path)


    def delete_roi(self, path, pno, roi_id):
        """
        Deletes a project document ROI (Region of Interest) from the database.

        :param path: The path of the document.
        :type path: str
        :param roi: The ROI (Region of Interest) to delete.
        :type roi: dict
        :return: None
        :rtype: None
        """
        roi_list = self.get_project_document_roi(path)
        if roi_list and pno < len(roi_list) and roi_id in roi_list[pno]:
            del roi_list[pno][roi_id]
        self.insert_project_document_roi(path, roi_list)

        if self.__update_roi_on_tool_viewer_func:
            self.__update_roi_on_tool_viewer_func(path, roi_id)



    def delete_project_document_roi(self ,path):
        """
        Deletes a project document ROI (Region of Interest) from the internal database.

        :param path: The path of the document to be deleted.
        :type path: str
        :return: None
        :rtype: None

        This function removes a document ROI from the internal database based on the given path.
        Example:
            >>> delete_project_document_roi('/path/to/document')
        """
        query = Query()
        with self.__rwlock.w_locked():
            self.__documents_roi_table.remove(query.document_name == path)
        
        self.__trigger_write_event()
            



    def get_project_document_roi(self, file_name):
        """
        Retrieves the ROI (Region of Interest) for a given project document.
        
        :param file_name: The name of the project document.
        :type file_name: str
        :return: The ROI of the project document.
        :rtype: list
        """
        

        ROI = Query()
        with self.__rwlock.r_locked():
            result = self.__documents_roi_table.search(ROI.document_name == file_name)
        
        if result: 
            return result[0]['roi']
        else:
            return []


    PROJECT_SETTINGS_DESCRIPTION = 'project_description'
    PROJECT_SETTINGS_ACM_PROJECT = 'project_acm_project_id'
    PROJECT_SETTINGS_FILTER = 'project_filter'


    def subscribe_to_element_updates_on_hmi_display(self, func, path, pno):

        # Re-subscribing the same widget (e.g. on canvas reload) must not stack duplicates.
        if (func, pno, path) in self.__update_element_on_hmi_display_update_func:
            return

        self.__update_element_on_hmi_display_update_func.append((func, pno, path))


    def unsubscribe_to_new_element_on_hmi_display(self, func):
        """
        Unsubscribes a function from the new element on HMI display update.

        :param func: The function to unsubscribe.
        :type func: function
        :return: None
        :rtype: None
        
        This function removes the specified function from the list of functions that are called when a new element is added to the HMI display.
        
        Example:
            >>> unsubscribe_to_new_element_on_hmi_display(my_function)
        """
        
        self.__update_element_on_hmi_display_update_func = [f for f in self.__update_element_on_hmi_display_update_func if f[0] != func]


    def __notify_hmi_display_subscribers(self, record, record_pno, record_path, spa_type, source):
        """
        Notifies HMI-display subscribers registered for the given page/document.

        A subscriber is a GUI widget that may already have been destroyed, so a failing
        subscriber must never abort the database write that triggered the notification.
        """
        for func, pno, path in list(self.__update_element_on_hmi_display_update_func):
            if pno != record_pno or path != record_path:
                continue
            try:
                func(record, spa_type)
            except Exception:
                logging.exception(f'update_element_on_hmi_display subscriber raised ({source})')


    def set_project_setting(self, key, value):
        """
        Sets the value of a project setting.

        :param key: The key of the setting.
        :type key: str
        :param value: The value to set.
        :type value: Any
        :return: None
        :rtype: None
        
        This function sets the value of a project setting identified by the given key. If the setting already exists, its value will be updated. If the setting does not exist, a new setting will be created with the given key and value.
        
        Example:
            >>> set_project_setting('setting_key', 'setting_value')
        """
        
        query = Query()
        with self.__rwlock.w_locked():
            self.__db.upsert({ 'key': key, 'value':value }, query.key == key)

        self.__trigger_write_event()
        self.__flush_now()

    
    def remove_project_setting(self, key):
        """
        Removes a project setting from the internal database.

        :param key: The key of the setting to remove.
        :type key: str
        :return: None
        :rtype: None

        This function removes the project setting with the given key from the internal database.
        Example:
            >>> remove_project_setting('setting_key')
        """
        query = Query()
        with self.__rwlock.w_locked():
            self.__db.remove(query.key == key)

        self.__trigger_write_event()
        self.__flush_now()


    def get_project_setting(self, key, default=''):
        """
        Retrieves the value of a project setting.

        Returns ``default`` (defaults to ``''`` for backwards compatibility) when
        the key is not present. Pass ``default=None`` to distinguish a missing
        setting from a legitimately empty one.
        """
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__db.search(query.key == key)

        if result: 
            return result[0]['value']
        else:
            return default
        
    
    def get_project_drawing_images(self):
        """
        Retrieves the project documents of image type a subset of drawing type from the internal database.

        :return: The project documents of image type.
        :rtype: List[documents]
        """
        query = Query()
        with self.__rwlock.r_locked():
            return self.__documents_table.search(query.type == self.IMAGE)


    def get_project_drawings(self):
        """
        Retrieves the project documents of drawing type from the internal database.

        :return: The project documents of drawing type.
        :rtype: List[documents]
        """
        query = Query()
        with self.__rwlock.r_locked():
            return self.__documents_table.search(query.type == self.DRAWING) 

    def get_project_texts(self):
        """
        Retrieves the project documents of text type from the internal database.

        :return: The project documents of text type.
        :rtype: List[documents]
        """
        query = Query()
        with self.__rwlock.r_locked():
            return self.__documents_table.search(query.type == self.TEXT)
        

    def get_project_tables(self):
        """
        Retrieves the project documents of table type from the internal database.

        :return: The project documents of table type.
        :rtype: List[documents]
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            return self.__documents_table.search(query.type == self.TABLE)


    def save_control_module(self, control_module_dict):
        """
        Saves a control module entry in the internal database.

        :param control_module_dict: Dictionary containing the control module data.
        :type control_module_dict: dict
        :return: None
        :rtype: None
        
        This function saves the control module entry in the internal database. It checks if the entry already exists and updates it if necessary.
        
        Example:
            >>> save_control_module({'id': 1, 'name': 'Module 1'})
        """
        
        # Check if entry exists 
        query = Query()
        with self.__rwlock.w_locked():
            self.__control_modules_table.upsert(control_module_dict, query.id == control_module_dict['id'])


        for func, pno, path in self.__update_element_on_hmi_display_update_func:
            if pno == control_module_dict['pno'] and path == control_module_dict['path']:
                func(control_module_dict, 'control_module')

        self.__trigger_write_event()


    def delete_control_module(self, name):
        """
        Deletes a control module from the database.

        :param name: The name of the control module to delete.
        :type name: str
        :return: None
        :rtype: None
        
        This function removes a control module from the database based on its name.
        
        Example:
            >>> delete_control_module('module1')
        """
        
        query = Query()
        with self.__rwlock.w_locked():
            # Look up the record first so we know which HMI-display subscribers
            # to notify after removal.
            existing = self.__control_modules_table.search(query.name == name)
            self.__control_modules_table.remove(query.name == name)

        for record in existing:
            deleted_pno = record.get('pno')
            deleted_path = record.get('path')
            for func, pno, path in self.__update_element_on_hmi_display_update_func:
                if pno == deleted_pno and path == deleted_path:
                    func(record, 'control_module_deleted')

        self.__trigger_write_event()

    
    def delete_control_module_by_id(self, id):
        """
        Deletes a control module from the internal database by its ID.

        :param id: The ID of the control module to be deleted.
        :type id: str
        :return: None
        :rtype: None
        """
        
        query = Query()
        with self.__rwlock.w_locked():
            # Look up the record first so we know which HMI-display subscribers
            # to notify after removal.
            existing = self.__control_modules_table.search(query.id == id)
            self.__control_modules_table.remove(query.id == id)

        for record in existing:
            deleted_pno = record.get('pno')
            deleted_path = record.get('path')
            for func, pno, path in self.__update_element_on_hmi_display_update_func:
                if pno == deleted_pno and path == deleted_path:
                    func(record, 'control_module_deleted')

        self.__trigger_write_event()


    def save_bulk_control_modules(self, control_modules):
        """
        Saves a list of control modules in a separate thread.

        :param control_modules: The list of control modules to be saved.
        :type control_modules: list
        :return: None
        :rtype: None
        
        This function saves each control module in the given list in a separate thread using the `save_control_module` method.
        
        Example:
            >>> save_bulk_control_modules([control_module1, control_module2])
        """

        def write_modules():
            with self.__rwlock.w_locked():
                self.__control_modules_table.insert_multiple(control_modules)

            # Mirror per-item save_control_module: notify HMI subscribers so open displays refresh.
            for module in control_modules:
                module_pno = module.get('pno')
                module_path = module.get('path')
                for func, pno, path in self.__update_element_on_hmi_display_update_func:
                    if pno == module_pno and path == module_path:
                        try:
                            func(module, 'control_module')
                        except Exception:
                            logging.exception('update_element_on_hmi_display subscriber raised (save_bulk_control_modules)')

            self.__trigger_write_event()

        thread = threading.Thread(target=write_modules)
        thread.start()

        self.__save_bulk_control_modules_threads.append(thread)


    def check_if_save_bulk_control_modules_threads_finished(self)-> bool:
        """
        Checks if all save bulk control modules threads have finished and removes them from the list if they have.
        :return: bool
        :rtype: bool
        This function iterates through the list of save bulk control modules threads and checks if each thread is alive. If a thread is not alive, it is removed from the list. The function returns True if all threads have finished, otherwise it returns False.
        """
        all_finished = True
        for thread in self.__save_bulk_control_modules_threads:
            if thread.is_alive():
                all_finished = False

        self.__save_bulk_control_modules_threads = [thread for thread in self.__save_bulk_control_modules_threads if thread.is_alive()]
        
        return all_finished

    def save_control_module_graphic_template(self, control_module_dict):
        """
        Saves a control module graphic template.

        :param control_module_dict: The dictionary containing the control module information.
        :type control_module_dict: dict
        :return: None
        :rtype: None

        This function saves a control module graphic template by upserting the control_module_dict into the control_modules_graphic_templates_table.
        
        Example:
            >>> save_control_module_graphic_template({'id': 1, 'name': 'template'})
        """
        
        # Check if entry exists 
        query = Query()
        with self.__rwlock.w_locked():
            self.__control_modules_graphic_templates_table.upsert(control_module_dict, query.id == control_module_dict['id'])

        self.__trigger_write_event()


    def delete_control_module_template(self, name):
        """
        Deletes a control module template from the database.

        :param name: The name of the control module template to delete.
        :type name: str
        :return: None
        :rtype: None

        This function removes a control module template from the database based on its name.
        """
        
        query = Query()
        with self.__rwlock.w_locked():
            self.__control_modules_graphic_templates_table.remove(query.name == name)

        self.__trigger_write_event()


    def delete_control_module_template_by_id(self, id):
        """
        Deletes a control module template by its ID.

        :param id: The ID of the control module template to be deleted.
        :type id: str
        :return: None
        :rtype: None
        """
        
        query = Query()
        with self.__rwlock.w_locked():
            self.__control_modules_graphic_templates_table.remove(query.id == id)

        self.__trigger_write_event()


    def save_static_graphic(self, static_graphic_dict):
        """
        Saves a static graphic entry in the database.

        :param static_graphic_dict: Dictionary containing the static graphic data.
        :type static_graphic_dict: dict
        :return: None
        :rtype: None
        """
        
        # Check if entry exists 
        query = Query()
        with self.__rwlock.w_locked():
            self.__static_graphics_table.upsert(static_graphic_dict, query.id == static_graphic_dict['id'])

        self.__notify_hmi_display_subscribers(static_graphic_dict,
                                              static_graphic_dict['pno'],
                                              static_graphic_dict['path'],
                                              'static_graphic',
                                              'save_static_graphic')

        self.__trigger_write_event()
                


    def delete_static_graphic(self, id):
        """
        Deletes a static graphic from the internal database.

        :param id: The ID of the static graphic to delete.
        :type id: str
        :return: None
        :rtype: None
        
        This function removes a static graphic from the internal database based on its ID.
        
        Example:
            >>> delete_static_graphic(1)
        """
        
        query = Query()
        with self.__rwlock.w_locked():
            # Look up the record first so we know which HMI-display subscribers
            # to notify after removal.
            existing = self.__static_graphics_table.search(query.id == id)
            self.__static_graphics_table.remove(query.id == id)

        if existing:
            deleted_record = existing[0]
            self.__notify_hmi_display_subscribers(deleted_record,
                                                  deleted_record.get('pno'),
                                                  deleted_record.get('path'),
                                                  'static_graphic_deleted',
                                                  'delete_static_graphic')

        self.__trigger_write_event()


    def save_static_graphic_graphic_template(self, static_graphic_dict):
        """
        Saves a static graphic template in the database.

        :param static_graphic_dict: The dictionary containing the static graphic template data.
        :type static_graphic_dict: dict
        :return: None
        :rtype: None

        This function saves a static graphic template in the database by upserting the provided dictionary into the 
        'static_graphics_graphic_templates_table' table. The upsert operation checks if an entry with the same ID 
        already exists and updates it if found, or inserts a new entry if not found.
        """
        
        # Check if entry exists 
        query = Query()
        with self.__rwlock.w_locked():
            self.__static_graphics_graphic_templates_table.upsert(static_graphic_dict, query.id == static_graphic_dict['id'])

        self.__trigger_write_event()


    def delete_static_graphic_template(self, id):
        """
        Deletes a static graphic template from the database.

        :param id: The ID of the graphic template to delete.
        :type id: str
        :return: None
        :rtype: None
        This function removes a static graphic template from the database based on its ID.
        """
        
        query = Query()
        with self.__rwlock.w_locked():
            self.__static_graphics_graphic_templates_table.remove(query.id == id)

        self.__trigger_write_event()


    def save_hmi_display(self, hmi_display_dict):
        """
        Saves the HMI display information to the internal database.

        :param hmi_display_dict: Dictionary containing the HMI display information.
        :type hmi_display_dict: dict
        :return: None
        :rtype: None
        """
        
        # Check if entry exists 
        query = Query()
        with self.__rwlock.w_locked():
            self.__hmi_displays_table.upsert(hmi_display_dict, query.id == hmi_display_dict['id'])

        self.__trigger_write_event()
        self.__flush_now()


    def save_page_link_roi_to_hmi_display(self, data):
        """
        Saves the page link ROI to the page link table.

        :param data: The data to save.
        :type data: dict
        :return: None
        :rtype: None
        """
        query = Query()
        with self.__rwlock.w_locked():
            self.__page_link_roi_to_page_link_table.upsert(data, query.roi_uid == data['roi_uid'])

        self.__trigger_write_event()


    def delete_page_link(self, path, pno, roi_uid):
        """
        Deletes a page link from the page link table.

        :param hmi_display_id: The ID of the HMI display.
        :type hmi_display_id: str
        :param index: The index of the page link to delete.
        :type index: int
        :return: None
        :rtype: None
        """
        removed_page_link = None
        with self.__rwlock.w_locked():
            # Get the display object 
            query = Query()
            data = self.__page_link_roi_to_page_link_table.search((query.path == path) & (query.roi_uid == roi_uid))
            data = data[0] if data else None

            query = Query()
            display = self.__hmi_displays_table.get(query.id == data['hmi_display_id']) if data else None

            # Get the page link or unlinked page link 
            if display:
                new_page_links = []

                for link in display['page_links']:
                    if link['roi_uid'] != roi_uid:
                        new_page_links.append(link)
                    else:
                        removed_page_link = link
                display['page_links'] = new_page_links

                new_unlinked_page_links = []
                if 'unlinked_page_links' in display:
                    for link in display['unlinked_page_links']:
                        if link['roi_uid'] != roi_uid:
                            new_unlinked_page_links.append(link)
                        else:
                            removed_page_link = link
                    display['unlinked_page_links'] = new_unlinked_page_links

                # Update the display object
                query = Query()
                self.__hmi_displays_table.update(display, query.id == display['id'])

            # Remove the page link from the reference table (the display may already be deleted,
            # leaving a stale reference row behind)
            query = Query()
            self.__page_link_roi_to_page_link_table.remove(query.roi_uid == roi_uid)

        # Also remove the ROI and text ROIs from the document
        self.delete_roi(path, pno, roi_uid)
        if removed_page_link:
            for text_roi in removed_page_link.get('text_location_dict', {}).keys():
                self.delete_roi(path, pno, text_roi)

        self.__trigger_write_event()

    def save_hmi_display_graphic_template(self, hmi_display_dict):
        """
        Saves the HMI display graphic template to the internal database.

        :param hmi_display_dict: The dictionary containing the HMI display graphic template.
        :type hmi_display_dict: dict
        :return: None
        :rtype: None

        This function saves the HMI display graphic template to the internal database. It checks if the entry already exists and updates it if necessary.
        
        Example:
            >>> save_hmi_display_graphic_template({'id': 1, 'name': 'Template 1'})
        """
        
        # Check if entry exists 
        query = Query()
        with self.__rwlock.w_locked():
            self.__hmi_displays_graphic_templates_table.upsert(hmi_display_dict, query.id == hmi_display_dict['id'])

        self.__trigger_write_event()


    def delete_hmi_display(self, id):
        """
        Deletes an HMI display from the internal database.

        :param id: The ID of the HMI display to delete.
        :type id: str
        :return: None
        :rtype: None
        """
        
        query = Query()
        with self.__rwlock.w_locked():
            self.__hmi_displays_table.remove(query.id == id)
            # Drop the page link references so they do not outlive the display
            self.__page_link_roi_to_page_link_table.remove(query.hmi_display_id == id)

        self.__trigger_write_event()


    def delete_hmi_display_template(self, id):
        """
        Deletes an HMI display template from the database.

        :param id: The ID of the template to delete.
        :type id: str
        :return: None
        :rtype: None
        """
        
        query = Query()
        with self.__rwlock.w_locked():
            self.__hmi_displays_graphic_templates_table.remove(query.id == id)

        self.__trigger_write_event()


    def save_linked_graphic(self, linked_graphic_pairs_dict):
        """
        Saves a linked graphic pair to the internal database.

        :param linked_graphic_pairs_dict: Dictionary containing the linked graphic pair information.
        :type linked_graphic_pairs_dict: dict
        :return: None
        :rtype: None
        
        This function saves a linked graphic pair to the internal database. It checks if the entry already exists and updates it if it does, or inserts a new entry if it doesn't.
        
        Example:
            >>> save_linked_graphic({'path': '/path/to/graphic', 'name': 'graphic.png'})
        """
        
        # Check if entry exists 
        query = Query()
        with self.__rwlock.w_locked():
            self.__linked_graphic_pairs.upsert(linked_graphic_pairs_dict, query.name == linked_graphic_pairs_dict['path'])

        self.__trigger_write_event()


    def save_linked_text_regex(self, linked_text_regex_dict):
        """
        Saves the linked text regex dictionary to the internal database.
        
        :param linked_text_regex_dict: The dictionary containing the linked text regex information.
        :type linked_text_regex_dict: dict
        :return: None
        :rtype: None
        
        This function saves the linked text regex dictionary to the internal database using the upsert method of the linked_text_regex_table. 
        If the linked_text_regex_update_func is defined, it is called after the upsert operation.
        """
        
        query = Query()
        with self.__rwlock.w_locked():
            if 'timestamp' not in linked_text_regex_dict:
                timestamp = int(round(time.time() * 1000))
                linked_text_regex_dict['timestamp'] = timestamp
            self.__linked_text_regexes_table.upsert(linked_text_regex_dict, query.id == linked_text_regex_dict['id'])
        
        if self.__linked_text_regex_update_func:
            self.__linked_text_regex_update_func()

        self.__trigger_write_event()



    def get_unapproved_text_link_count(self):
        """
        Returns the count of unapproved text links in the database.

        :return: The count of unapproved text links.
        :rtype: int
        """
        with self.__rwlock.r_locked():
            count = len(self.__unapproved_text_links_table.all())
        return count

      

    def subscribe_unapproved_text_link_update(self, func):
        """
        Subscribe to the unapproved text link update function.

        :param func: The function to be set as the unapproved text link update function.
        :type func: function
        :return: None
        :rtype: None

        This function sets the unapproved text link update function to the given function.
        """

        self.__unapproved_text_link_update_func.append(func)
        # Fire only the newly-registered callback once so it can seed its
        # initial state. Previously this looped over every subscriber which
        # caused unrelated widgets to redraw on every new subscription.
        try:
            func()
        except Exception:
            logging.exception('subscribe_unapproved_text_link_update initial fire failed')


    def subscribe_unapproved_text_link_detailed_update(self, object_id, subobject_type, func):
        """
        Subscribe to the unapproved text link detailed update function.
        
        :param func: The function to be set as the unapproved text link detailed update function.
        :type func: function
        :return: None
        :rtype: None
        
        This function sets the unapproved text link detailed update function to the given function.
        """
        self.__unapproved_text_link_detailed_update_func.append((object_id, subobject_type, func))


    def unsubscribe_unapproved_text_link_detailed_update(self, object_id, subobject_type):
        """
        Unsubscribe from the unapproved text link detailed update function.

        :return: None
        :rtype: None
        """
        self.__unapproved_text_link_detailed_update_func = [f for f in self.__unapproved_text_link_detailed_update_func 
                                                            if not (f[0] == object_id and f[1] == subobject_type)]
    
    def unsubscribe_unapproved_text_link_update(self, func):
        """
        Unsubscribe from the unapproved text link update function.

        :param func: The function to be removed from the unapproved text link update functions.
        :type func: function
        :return: None
        :rtype: None

        This function removes the given function from the list of unapproved text link update functions.
        """
        
        self.__unapproved_text_link_update_func = [f for f in self.__unapproved_text_link_update_func if f != func]


    def subscribe_rejected_text_link_update(self, func):
        
        self.__rejected_text_link_update_func.append(func)


    def save_unapproved_text_link(self, text_link_dict):
        """
        Saves an unapproved text link to the internal database.

        :param text_link_dict: A dictionary containing the details of the text link.
        :type text_link_dict: dict
        :return: None
        :rtype: None

        This function checks if the entry already exists in the database. If it does, it updates the existing entry with the new details. If it doesn't, it inserts a new entry into the database. After saving the text link, it triggers the unapproved text link update function if it is defined.
        
        Example:
            >>> save_unapproved_text_link({'id': 1, 'url': 'https://example.com', 'text': 'Example text'})
        """
        if 'subobject' in text_link_dict and 'subobject_name' not in text_link_dict:
            # Display-only 8-char suffix (not a lookup key); collisions are cosmetic.
            text_link_dict['subobject_name'] = str(uuid.uuid4())[:8] + "*"
        # Check if entry exists 
        query = Query()
        with self.__rwlock.w_locked():
            self.__unapproved_text_links_table.upsert(text_link_dict, query.id == text_link_dict['id'])
        for func in self.__unapproved_text_link_update_func:
            try: func()
            except Exception:
                logging.exception('unapproved_text_link_update subscriber raised (save_unapproved_text_link)')

        for _, _, func in self.__unapproved_text_link_detailed_update_func:
            try: func(text_link_dict['id'])
            except Exception:
                logging.exception('unapproved_text_link_detailed_update subscriber raised (save_unapproved_text_link)')

        self.__trigger_write_event()


    def save_approved_text_link(self, text_link_dict):
        """
        Saves the approved text link to the internal database.

        :param text_link_dict: Dictionary containing the details of the text link
        :type text_link_dict: dict
        :return: None
        :rtype: None
        
        This function saves the provided text link dictionary to the approved_text_links_table in the internal database. It first checks if the entry already exists and updates it if necessary. It also removes the corresponding entry from the unapproved_text_links_table. If a callback function is provided, it is called after the update.
        
        Example:
            >>> save_approved_text_link({'id': 1, 'url': 'https://example.com'})
        """
        
        # Check if entry exists 
        query = Query()
        with self.__rwlock.w_locked():
            self.__approved_text_links_table.upsert(text_link_dict, query.id == text_link_dict['id'])
            self.__unapproved_text_links_table.remove(query.id == text_link_dict['id'])
            self.__rejected_text_links_table.remove(query.id == text_link_dict['id'])
        for func in self.__unapproved_text_link_update_func:
            try: func()
            except Exception:
                logging.exception('unapproved_text_link_update subscriber raised (save_approved_text_link)')

        for _, _, func in self.__unapproved_text_link_detailed_update_func:
            try: func(text_link_dict['id'])
            except Exception:
                logging.exception('unapproved_text_link_detailed_update subscriber raised (save_approved_text_link)')

        self.__trigger_write_event()
        self.__flush_now()

    
    def save_rejected_text_link(self, text_link_dict):
        """
        Saves the rejected text link to the internal database.

        :param text_link_dict: Dictionary containing the details of the text link
        :type text_link_dict: dict
        :return: None
        :rtype: None
        
        This function saves the provided text link dictionary to the rejected_text_links_table in the internal database. It first checks if the entry already exists and updates it if necessary. It also removes the corresponding entry from the unapproved_text_links_table. If a callback function is provided, it is called after the update.
        
        Example:
            >>> save_rejected_text_link({'id': 1, 'url': 'https://example.com'})
        """
        
        # Check if entry exists 
        query = Query()
        with self.__rwlock.w_locked():
            self.__rejected_text_links_table.upsert(text_link_dict, query.id == text_link_dict['id'])
            self.__unapproved_text_links_table.remove(query.id == text_link_dict['id'])
            self.__approved_text_links_table.remove(query.id == text_link_dict['id'])
        for func in self.__unapproved_text_link_update_func:
            try: func()
            except Exception:
                logging.exception('unapproved_text_link_update subscriber raised (save_rejected_text_link)')

        for func in self.__rejected_text_link_update_func:
            try: func(text_link_dict['id'])
            except Exception:
                logging.exception('rejected_text_link_update subscriber raised (save_rejected_text_link)')

        for _, _, func in self.__unapproved_text_link_detailed_update_func:
            try: func(text_link_dict['id'])
            except Exception:
                logging.exception('unapproved_text_link_detailed_update subscriber raised (save_rejected_text_link)')

        self.__trigger_write_event()
        self.__flush_now()


    def delete_text_link(self, id):
        """
        Deletes a text link from the internal database.

        :param id: The ID of the text link to delete.
        :type id: str
        :return: None
        :rtype: None
        
        This function deletes a text link from the internal database. It removes the text link with the specified ID from the 'unapproved_text_links_table'. If there is an update function defined, it will be called after the deletion.
        
        Example:
            >>> delete_text_link(1)
        """
        
        query = Query()
        with self.__rwlock.w_locked():
            self.__unapproved_text_links_table.remove(query.id == id)
            self.__approved_text_links_table.remove(query.id == id)
            self.__rejected_text_links_table.remove(query.id == id)
            self.__linked_text_regexes_table.remove(query.id == id)
        for func in self.__unapproved_text_link_update_func:
            try: func()
            except Exception:
                logging.exception('unapproved_text_link_update subscriber raised (delete_text_link)')

        for _, _, func in self.__unapproved_text_link_detailed_update_func:
            try: func(id)
            except Exception:
                logging.exception('unapproved_text_link_detailed_update subscriber raised (delete_text_link)')

        self.__trigger_write_event()


    def save_bulk_unapproved_text_links(self, text_links):
        """
        Saves a bulk of unapproved text links asynchronously.

        :param text_links: A list of text links to be saved.
        :type text_links: list
        :return: None
        :rtype: None
        
        This function saves a bulk of unapproved text links asynchronously using threading. Each text link in the list is passed to the save_unapproved_text_link method for saving.
        
        Example:
            >>> save_bulk_unapproved_text_links(['link1', 'link2', 'link3'])
        """
        

        def write_modules():
            for text_link in text_links:
                self.save_unapproved_text_link(text_link)

        threading.Thread(target=write_modules).start()

        self.__trigger_write_event()


    def get_unapproved_text_link_by_id(self, id):
        """
        Retrieves an unapproved text link by its ID.

        :param id: The ID of the unapproved text link.
        :type id: str
        :return: The unapproved text link with the specified ID, or an empty dictionary if not found.
        :rtype: dict
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__unapproved_text_links_table.search(query.id == id)

        if result: 
            return result[0]
        else:
            return {}
        
    def get_approved_text_link_by_id(self, id):
        """
        Retrieves the approved text link by its ID.

        :param id: The ID of the approved text link.
        :type id: str
        :return: The approved text link with the specified ID, or an empty dictionary if not found.
        :rtype: dict
        
        This function searches for the approved text link with the given ID in the approved_text_links_table.
        If found, it returns the first matching result. Otherwise, it returns an empty dictionary.
        
        Example:
            >>> get_approved_text_link_by_id(1)
            {'id': 1, 'url': 'https://example.com'}
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__approved_text_links_table.search(query.id == id)

        if result: 
            return result[0]
        else:
            return {}
        
    
    def get_all_approved_object_parameters_text_link(self, tagname):
        """
        Retrieves all approved object parameters with text links for a given tagname.

        :param tagname: The tagname to filter the results.
        :type tagname: str
        :return: A list of approved object parameters with text links.
        :rtype: list

        This function queries the approved_text_links_table to retrieve all object parameters
        that are approved and have text links associated with them for a given tagname. The
        function returns a list of the matching results. If no results are found, an empty list
        is returned.
        
        Example:
            >>> get_all_approved_object_parameters_text_link('example_tag')
            [{'param1': 'value1', 'param2': 'value2'}, {'param3': 'value3', 'param4': 'value4'}]
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__approved_text_links_table.search((query.tagname.text == tagname) & ~ (query.subobject.exists()))

        if result: 
            return result
        else:
            return []
        
        
    def get_all_unapproved_object_parameters_text_link(self, tagname):
        """
        Retrieves all unapproved (pending) object parameters with text links for a given tagname.

        :param tagname: The tagname to filter the results.
        :type tagname: str
        :return: A list of unapproved object parameters with text links.
        :rtype: list
        """

        query = Query()
        with self.__rwlock.r_locked():
            result = self.__unapproved_text_links_table.search((query.tagname.text == tagname) & ~ (query.subobject.exists()))

        if result: 
            return result
        else:
            return []
        
        
        
    
    def get_all_approved_subobject_parameters_text_link(self, tagname, subobject):
        """
        Retrieves all approved subobject parameters with text links.

        :param tagname: The tagname to search for.
        :type tagname: str
        :param subobject: The subobject to search for.
        :type subobject: str
        :return: A list of approved subobject parameters with text links.
        :rtype: list
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__approved_text_links_table.search((query.tagname.text == tagname)
                                                             & (query.subobject.text == subobject))

        if result: 
            return result
        else:
            return []
        
    
    def get_all_unapproved_subobject_parameters_text_link(self, tagname, subobject):
        """
        Retrieves all approved subobject parameters with text links.

        :param tagname: The tagname to search for.
        :type tagname: str
        :param subobject: The subobject to search for.
        :type subobject: str
        :return: A list of approved subobject parameters with text links.
        :rtype: list
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__unapproved_text_links_table.search((query.tagname.text == tagname)
                                                             & (query.subobject.text == subobject))

        if result: 
            return result
        else:
            return []
        
    
    def get_approved_text_link_by_id(self, id:str):

        query = Query()
        with self.__rwlock.r_locked():
            result = self.__approved_text_links_table.search(query.id == id)

        if result: 
            return result[0]
        else:
            return {}


    def get_control_module(self, name):
        """
        Retrieves the control module with the given name.

        :param name: The name of the control module.
        :type name: str
        :return: The control module with the given name, or an empty dictionary if not found.
        :rtype: dict
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__control_modules_table.search(query.name == name)

        if result: 
            return result[0]
        else:
            return {}


    def get_control_module_by_id(self, id):
        """
        Retrieves the control module with the given ID.

        :param id: The ID of the control module.
        :type id: str
        :return: The control module with the given ID, or an empty dictionary if not found.
        :rtype: dict
        
        This function retrieves the control module from the control_modules_table based on the provided ID.
        If the control module is found, it is returned. Otherwise, an empty dictionary is returned.
        
        Example:
            >>> get_control_module_by_id(1)
            {'id': 1, 'name': 'Module 1', 'status': 'active'}
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__control_modules_table.search(query.id == id)

        if result: 
            return result[0]
        else:
            return {}


    def get_static_graphic(self, name):
        """
        Retrieves a static graphic from the internal database.

        :param name: The name of the static graphic.
        :type name: str
        :return: The static graphic with the given name, or an empty dictionary if not found.
        :rtype: dict
        
        This function retrieves a static graphic from the internal database based on its name. If a static graphic with the given name is found, it is returned. Otherwise, an empty dictionary is returned.
        
        Example:
            >>> get_static_graphic('logo')
            {'name': 'logo', 'url': 'https://example.com/logo.png'}
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__static_graphics_table.search(query.name == name)

        if result: 
            return result[0]
        else:
            return {}


    def get_static_graphic_by_id(self, id):
        """
        Retrieves a static graphic by its ID.

        :param id: The ID of the static graphic.
        :type id: str
        :return: The static graphic with the specified ID, or an empty dictionary if not found.
        :rtype: dict
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__static_graphics_table.search(query.id == id)

        if result: 
            return result[0]
        else:
            return {}
        

    def save_static_graphic_anchors(self, id, top_anchor, bottom_anchor, left_anchors, right_anchors):
        """
        Saves the anchors for a static graphic.

        :param id: The ID of the static graphic.
        :type id: str
        :param anchors: The anchors to save.
        :type anchors: list
        """
        query = Query()
        with self.__rwlock.w_locked():
            # TinyDB Table.update signature is (fields, cond); previously the args were swapped so anchors never persisted.
            self.__static_graphics_table.update({
                "hmi_graphic": {
                    "extract_graphic": {
                        "top_anchors": top_anchor,
                        "bottom_anchors": bottom_anchor,
                        "left_anchors": left_anchors,
                        "right_anchors": right_anchors
                    }
                }
            }, query.id == id)

        self.__trigger_write_event()


    def get_hmi_display(self, id):
        """
        Retrieves the HMI display with the specified ID.

        :param id: The ID of the HMI display.
        :type id: str
        :return: The HMI display with the specified ID, or an empty dictionary if not found.
        :rtype: dict
        
        This function retrieves the HMI display from the internal database based on the provided ID.
        If the HMI display is found, it is returned. Otherwise, an empty dictionary is returned.
        
        Example:
            >>> get_hmi_display(1)
            {'id': 1, 'name': 'Display 1', 'type': 'Main'}
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__hmi_displays_table.search(query.id == id)

        if result: 
            return result[0]
        else:
            return {}
        
    
    def get_hmi_display_by_name(self, name):
        """
        Retrieves the HMI display with the specified name.

        :param name: The name of the HMI display.
        :type name: str
        :return: The HMI display with the specified name, or an empty dictionary if not found.
        :rtype: dict
        
        This function retrieves the HMI display from the internal database based on the provided name.
        If the HMI display is found, it is returned. Otherwise, an empty dictionary is returned.
        
        Example:
            >>> get_hmi_display_by_name('Main Display')
            {'id': 1, 'name': 'Main Display', 'type': 'Main'}
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__hmi_displays_table.search(query.name == name)

        if result: 
            return result[0]
        else:
            return {}
        

    def get_hmi_display_in_page(self, path, pno):
        """
        Retrieves the HMI display in a specific page.

        :param path: The path of the document.
        :type path: str
        :param pno: The page number.
        :type pno: int
        :return: The HMI display in the specified page, or an empty dictionary if not found.
        :rtype: dict
        """
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__hmi_displays_table.search((query.path == path) & (query.pno == pno))

        if result:
            return result[0]
        else:
            return {}


    def get_linked_graphic_pairs(self, path):
        """
        Retrieves the linked graphic pairs for a given path.

        :param path: The path to search for linked graphic pairs.
        :type path: str
        :return: The linked graphic pairs found for the given path.
        :rtype: dict

        This function searches for linked graphic pairs in the internal database based on the provided path. It uses a read lock to ensure thread safety during the search. If linked graphic pairs are found, the first result is returned. If no linked graphic pairs are found, an empty dictionary is returned.
        
        Example:
            >>> get_linked_graphic_pairs('/path/to/file')
            {'graphic1': 'image1', 'graphic2': 'image2'}
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__linked_graphic_pairs.search(query.path == path)

        if result: 
            return result[0]
        else:
            return {}
        
    
    def get_linked_text_regexes(self, id):
        """
        Retrieves the linked text regexes for a given ID.
        
        :param id: The ID to search for.
        :type id: str
        :return: The linked text regexes for the given ID.
        :rtype: dict

        This function retrieves the linked text regexes from the linked text regex table
        for the specified ID. 
        If the ID is found in the table, the first result is returned as a dictionary.
        If the ID is not found, an empty dictionary is returned.
        
        Example:
            >>> get_linked_text_regexes(123)
            {'regex1': 'pattern1', 'regex2': 'pattern2'}
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__linked_text_regexes_table.search(query.id == id)

        if result: 
            return result[0]
        else:
            return {}
        

    def get_all_linked_text_regexes_by_object_type(self, object_type):
        """
        Retrieves the linked text regexes for a given object type.

        :param object_type: The object type to search for.
        :type object_type: str
        :return: The linked text regexes for the given object type.
        :rtype: dict

        This function retrieves the linked text regexes from the linked text regex table
        for the specified object type. 
        If the object type is found in the table, the first result is returned as a dictionary.
        If the object type is not found, an empty dictionary is returned.
        
        Example:
            >>> get_linked_text_regexs_by_object_type('example_type')
            {'regex1': 'pattern1', 'regex2': 'pattern2'}
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__linked_text_regexes_table.search(query.tagname.object_type == object_type)

        if result: 
            return result
        else:
            return {}


    def get_all_control_modules(self):
        """
        Retrieves all control modules from the internal database.

        :return: A dictionary containing all control modules.
        :rtype: dict
        """
        
        with self.__rwlock.r_locked():
            result = self.__control_modules_table.all()

        if result: 
            return result
        else:
            return {}


    def get_all_control_module_in_document(self, path):
        """
        Retrieves all control modules in a document.

        :param path: The path of the document.
        :type path: str
        :return: A dictionary containing the control modules in the document.
        :rtype: dict
        
        This function retrieves all control modules in a document by querying the control_modules_table
        using the provided path. If control modules are found, they are returned as a dictionary. If no
        control modules are found, an empty dictionary is returned.
        
        Example:
            >>> get_all_control_module_in_document('/path/to/document')
            {'module1': {...}, 'module2': {...}, ...}
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__control_modules_table.search((query.path == path))

        if result: 
            return result
        else:
            return {}


    def get_all_control_module_on_page(self, path, pno):
        """
        Retrieves all control modules on a specific page and document path.

        :param path: The document path of the page.
        :type path: str
        :param pno: The docuemnt page number.
        :type pno: int
        :return: A dictionary containing the control modules on the page.
        :rtype: dict

        This function retrieves all control modules on a specific page by querying the control_modules_table
        using the provided document path and page number. If control modules are found, they are returned as a dictionary.
        If no control modules are found, an empty dictionary is returned.
        
        Example:
            >>> get_all_control_module_on_page('/c:/projects/example_project', 1)
            {'module1': {...}, 'module2': {...}, ...}
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__control_modules_table.search((query.path == path) & (query.pno == pno))

        if result: 
            return result
        else:
            return {}


    def get_all_control_module_of_type(self, type):
        """
        Retrieves all control modules of a specific type.

        :param type: The type of control module to retrieve.
        :type type: str
        :return: A dictionary containing the control modules of the specified type.
        :rtype: dict
        
        This function queries the control modules table to retrieve all control modules
        that match the specified type. It returns a dictionary containing the control
        modules of the specified type. If no control modules are found, an empty dictionary
        is returned.
        
        Example:
            >>> get_all_control_module_of_type('type1')
            {'module1': {...}, 'module2': {...}}
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__control_modules_table.search((query.type == type))

        if result: 
            return result
        else:
            return {}


    def get_all_control_module_of_type_in_document(self,path , type):
        """
        Retrieves all control modules of a specific type in a document.

        :param path: The path of the document.
        :type path: str
        :param type: The type of control module.
        :type type: str
        :return: A dictionary containing the control modules matching the given type and path.
        :rtype: dict

        This function searches for control modules in the control_modules_table that match the given type and path.
        If control modules are found, they are returned as a dictionary.
        If no control modules are found, an empty dictionary is returned.
        
        Example:
            >>> get_all_control_module_of_type_in_document('/c:/projects/example_project/drawings/example.pdf', 'example_type')
            {'control_module1': {...}, 'control_module2': {...}}
        """
    
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__control_modules_table.search((query.type == type) & (query.path == path))

        if result: 
            return result
        else:
            return {}



    def get_all_static_graphics(self):
        """
        Retrieves all static graphics from the internal database.

        :return: A dictionary containing all static graphics.
        :rtype: dict
        """
        
        with self.__rwlock.r_locked():
            result = self.__static_graphics_table.all()

        if result: 
            return result
        else:
            return {}
        
    
    def get_all_static_graphic_in_document(self, path):
        """
        Retrieves all static graphics in a document.

        :param path: The path of the document.
        :type path: str
        :return: A dictionary containing the static graphics in the document.
        :rtype: dict
        
        This function retrieves all static graphics in a document by querying the static_graphics_table
        using the provided path. If static graphics are found, they are returned as a dictionary. If no
        static graphics are found, an empty dictionary is returned.
        
        Example:
            >>> get_all_static_graphic_in_document('/path/to/document')
            {'graphic1': {...}, 'graphic2': {...}, ...}
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__static_graphics_table.search(query.path == path)

        if result: 
            return result
        else:
            return {}


    def get_all_static_graphic_templates(self):
        """
        Retrieves all static graphic templates.

        :return: A dictionary containing the static graphic templates.
        :rtype: dict
        """
        
        with self.__rwlock.r_locked():
            result = self.__static_graphics_graphic_templates_table.all()

        if result: 
            return result
        else:
            return {}


    def get_all_static_graphic_on_page(self, path, pno):
        """
        Retrieves all static graphics on a specific page and document path.
        
        :param path: The document path of the page.
        :type path: str
        :param pno: The document page number.
        :type pno: int
        :return: A dictionary containing the static graphics on the page.
        :rtype: dict
        
        This function searches for static graphics in the internal database based on the given path and page number.
        If any static graphics are found, it returns a dictionary containing the graphics.
        If no graphics are found, an empty dictionary is returned.
        
        Example:
            >>> get_all_static_graphic_on_page('/path/to/page', 1)
            {'graphic1': 'image1.png', 'graphic2': 'image2.png'}
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__static_graphics_table.search((query.path == path) & (query.pno == pno))

        if result: 
            return result
        else:
            return {}

    
    def get_all_hmi_displays(self):
        """
        Retrieves all HMI displays from the internal database.

        :return: A dictionary containing all HMI displays.
        :rtype: dict
        """
        
        with self.__rwlock.r_locked():
            result = self.__hmi_displays_table.all()

        if result: 
            return result
        else:
            return {}
        

    def get_all_hmi_displays_in_document(self, path):
        """
        Retrieves all HMI displays in a document.

        :param path: The path of the document.
        :type path: str
        :return: A dictionary containing the HMI displays in the document.
        :rtype: dict
        
        This function retrieves all HMI displays in a document by querying the hmi_displays_table
        using the provided path. If HMI displays are found, they are returned as a dictionary. If no
        HMI displays are found, an empty dictionary is returned.
        
        Example:
            >>> get_all_hmi_displays_in_document('/path/to/document')
            {'display1': {...}, 'display2': {...}, ...}
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__hmi_displays_table.search(query.path == path)

        if result: 
            return result
        else:
            return {}


    def get_all_hmi_displays_on_page(self, path, pno):
        """
        Retrieves all HMI displays on a specific page and document.

        :param path: The document path of the page.
        :type path: str
        :param pno: The document page number.
        :type pno: int
        :return: A dictionary containing the HMI displays on the page.
        :rtype: dict

        This function retrieves all HMI displays on a specific page by querying the internal database. It takes the path of the document and the page number as parameters. If there are HMI displays found on the page, it returns a dictionary containing the displays. Otherwise, it returns an empty dictionary.
        
        Example:
            >>> get_all_hmi_displays_on_page('/path/to/page', 1)
            {'display1': {...}, 'display2': {...}, ...}
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__hmi_displays_table.search((query.path == path) & (query.pno == pno))

        if result: 
            return result
        else:
            return {}
        
    
    def get_all_page_links_on_page(self, path, pno):
        """
        Retrieves all HMI displays on a specific page and document.

        :param path: The document path of the page.
        :type path: str
        :param pno: The document page number.
        :type pno: int
        :return: A dictionary containing the HMI displays on the page.
        :rtype: dict

        This function retrieves all HMI displays on a specific page by querying the internal database. It takes the path of the document and the page number as parameters. If there are HMI displays found on the page, it returns a dictionary containing the displays. Otherwise, it returns an empty dictionary.
        
        Example:
            >>> get_all_hmi_displays_on_page('/path/to/page', 1)
            {'display1': {...}, 'display2': {...}, ...}
        """
        PageLink = Query()
        query = Query().page_links.any((PageLink.path == path) & (PageLink.pno == pno))
        with self.__rwlock.r_locked():
            result = self.__hmi_displays_table.search(query)

        if result: 
            return result
        else:
            return {}


    def get_all_linked_graphic_pairs(self):
        """
        Retrieves all linked graphic pairs.

        :return: A dictionary containing all linked graphic pairs.
        :rtype: dict
        """
        
        with self.__rwlock.r_locked():
            result = self.__linked_graphic_pairs.all()

        if result:
            return result
        else: 
            return {}


    def remove_linked_graphic(self, path):
        """
        Removes the linked graphic pairs entry for the given source document path.

        The linked graphic pairs table stores one bundle per source document
        (keyed by ``path``). This deletes the entire bundle for that document.

        :param path: Source document path whose linked graphic bundle should be removed.
        :type path: str
        :return: None
        :rtype: None
        """
        query = Query()
        with self.__rwlock.w_locked():
            self.__linked_graphic_pairs.remove(query.path == path)

        self.__trigger_write_event()

        
    
    def get_all_unapproved_text_links(self):
        """
        Retrieves all unapproved text links from the internal database.

        :return: A dictionary containing the unapproved text links.
        :rtype: dict
        """
        
        with self.__rwlock.r_locked():
            result = self.__unapproved_text_links_table.all()

        if result:
            return result
        else: 
            return {}
        

    def get_all_unapproved_text_links_by_page_no(self, path, pno):
        """
        Retrieves all unapproved text links by page number and document path.

        :param path: The document path of the linked text data.
        :type path: str
        :param pno: The document page number of the linked text data.
        :type pno: int
        :return: A dictionary containing the unapproved text links.
        :rtype: dict

        This function retrieves all unapproved text links by page number from the internal database.
        It searches for linked text data that exists, matches the given path and page number.
        If any unapproved text links are found, they are returned as a dictionary.
        If no unapproved text links are found, an empty dictionary is returned.
        
        Example:
            >>> get_all_unapproved_text_links_by_page_no('/path/to/data', 1)
            {'link1': 'text1', 'link2': 'text2'}
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__unapproved_text_links_table.search((query.path == path) & 
                                                                (query.pno == pno))

        if result:
            return result
        else: 
            return {}
        

    def get_all_approved_text_links_by_page_no(self, path, pno):
        """
        Retrieves all approved text links by page number and document path.
        
        :param path: The document path to search for.
        :type path: str
        :param pno: The document page number to search for.
        :type pno: int
        :return: A dictionary containing the result if found, otherwise an empty dictionary.
        :rtype: dict
        
        This function searches for approved text links in the specified path and page number. If found, it returns the result as a dictionary. If not found, it returns an empty dictionary.
        
        Example:
            >>> get_all_approved_text_links_by_page_no('/path/to/file', 1)
            {'result': 'example'}
        """
       
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__approved_text_links_table.search((query.path == path) & 
                                                            (query.pno == pno))

        if result:
            return result
        else: 
            return {}
        

    def get_all_approved_text_links_by_document(self, path):
        """
        Retrieves every approved text link that belongs to a source document.

        :param path: Source document path to filter by.
        :type path: str
        :return: List of approved text link records (empty list if none).
        :rtype: list
        """

        query = Query()
        with self.__rwlock.r_locked():
            result = self.__approved_text_links_table.search(query.path == path)

        return result if result else []


    def get_all_unapproved_text_links_by_document(self, path):
        """
        Retrieves every unapproved text link that belongs to a source document.

        :param path: Source document path to filter by.
        :type path: str
        :return: List of unapproved text link records (empty list if none).
        :rtype: list
        """

        query = Query()
        with self.__rwlock.r_locked():
            result = self.__unapproved_text_links_table.search(query.path == path)

        return result if result else []


    def get_all_rejected_text_links_by_document(self, path):
        """
        Retrieves every rejected text link that belongs to a source document.

        :param path: Source document path to filter by.
        :type path: str
        :return: List of rejected text link records (empty list if none).
        :rtype: list
        """

        query = Query()
        with self.__rwlock.r_locked():
            result = self.__rejected_text_links_table.search(query.path == path)

        return result if result else []

    
    def get_all_linked_text_regexes(self):
        """
        Retrieves all linked text regexes from the database.
        
        :return: A dictionary containing all linked text regexes.
        :rtype: dict
        """
        
        with self.__rwlock.r_locked():
            result = self.__linked_text_regexes_table.all()

        if result:
            return result
        else: 
            return {}


    def get_linked_text_regexes_by_document(self, path):
        """
        Retrieves all linked text regex records that originate from a given source
        document path.

        :param path: Source document path to filter by.
        :type path: str
        :return: List of linked text regex records for that document (empty list if none).
        :rtype: list
        """
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__linked_text_regexes_table.search(query.path == path)

        return result if result else []


    def remove_linked_text_regex(self, regex_id):
        """
        Removes a linked text regex record by id.

        Fires the subscribed ``linked_text_regex_update_func`` (if any) so
        listeners like the pending-approvals badge refresh.

        :param regex_id: Identifier of the regex record (matches ``id`` field).
        :type regex_id: str
        :return: None
        :rtype: None
        """
        query = Query()
        with self.__rwlock.w_locked():
            self.__linked_text_regexes_table.remove(query.id == regex_id)

        if self.__linked_text_regex_update_func:
            self.__linked_text_regex_update_func()

        self.__trigger_write_event()
        

    def subscribe_linked_text_regex_table(self, func):
        """
        Subscribes a function to be called when the linked text regex table is updated.

        :param name: The function to be called when the linked text regex table is updated.
        :type name: func
        :return: None
        :rtype: None
        """
        self.__linked_text_regex_update_func = func
        self.__linked_text_regex_update_func()


    def get_control_module_graphic_template(self, name):
        """
        Retrieves the graphic template for a control module.

        :param name: The name of the control module.
        :type name: str
        :return: The graphic template for the control module.
        :rtype: dict
        
        Retrieves the graphic template for a control module based on its name. If a matching template is found, it is returned as a dictionary. If no template is found, an empty dictionary is returned.
        
        Example:
            >>> get_control_module_graphic_template('module1')
            {'template': 'template1'}
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__control_modules_graphic_templates_table.search(query.name == name)

        if result: 
            return result[0]
        else:
            return {}


    def get_control_module_graphic_template_by_id(self, id):
        """
        Retrieves the control module graphic template by its ID.

        :param id: The ID of the control module graphic template.
        :type id: str
        :return: The control module graphic template with the specified ID, or an empty dictionary if not found.
        :rtype: dict
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__control_modules_graphic_templates_table.search(query.id == id)

        if result: 
            return result[0]
        else:
            return {}


    def get_all_control_module_graphic_templates(self):
        """
        Retrieves all control module graphic templates.

        :return: A dictionary containing all control module graphic templates.
        :rtype: dict
        """
        
        with self.__rwlock.r_locked():
            result = self.__control_modules_graphic_templates_table.all()

        if result: 
            return result
        else:
            return {}


    def get_static_graphic_graphic_template(self, name):
        """
        Retrieves a static graphic template by name.

        :param name: The name of the graphic template.
        :type name: str
        :return: The static graphic template with the given name, or an empty dictionary if not found.
        :rtype: dict

        This function retrieves a static graphic template from the internal database by its name. It searches the
        __static_graphics_graphic_templates_table for a template with a matching name and returns the first result
        if found. If no matching template is found, an empty dictionary is returned.
        
        Example:
            >>> get_static_graphic_graphic_template('template1')
            {'name': 'template1', 'property1': 'value1', 'property2': 'value2'}
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__static_graphics_graphic_templates_table.search(query.name == name)

        if result: 
            return result[0]
        else:
            return {}

    def get_hmi_display_graphic_template(self, name):
        """
        Retrieves the HMI display graphic template with the given name.

        :param name: The name of the HMI display graphic template.
        :type name: str
        :returns: The HMI display graphic template with the given name, or an empty dictionary if not found.
        :rtype: dict
        
        This function searches for the HMI display graphic template with the specified name in the internal database.
        If found, it returns the template. Otherwise, it returns an empty dictionary.
        
        Example:
            >>> get_hmi_display_graphic_template('template1')
            {'name': 'template1', 'property1': 'value1', 'property2': 'value2'}
        """
      
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__hmi_displays_graphic_templates_table.search(query.name == name)

        if result: 
            return result[0]
        else:
            return {}
        

    def subscribe_object_assignment_regex_table(self, func):
        """
        Subscribes a function to be called when the object assignment regex table is updated.

        :param func: The function to be called when the object assignment regex table is updated.
        :type func: function
        :return: None
        :rtype: None
        """
        
        self.__object_assignment_regex_update_func = func
        self.__object_assignment_regex_update_func()
        

    def save_object_assignment_regex(self, object_assignment_regex_dict):
        """
        Saves the object assignment regex to the internal database.

        :param object_assignment_regex_dict: The dictionary containing the object assignment regex information.
        :type object_assignment_regex_dict: dict
        :return: None
        :rtype: None
        
        This function saves the object assignment regex dictionary to the internal database using the upsert method of the object_assignment_regex_table. 
        If the object_assignment_regex_update_func is defined, it is called after the upsert operation.
        """
        
        query = Query()
        with self.__rwlock.w_locked():
            self.__object_assignment_regexes_table.upsert(object_assignment_regex_dict, query.id == object_assignment_regex_dict['id'])
        
        if self.__object_assignment_regex_update_func:
            self.__object_assignment_regex_update_func()

        self.__trigger_write_event()


    def get_object_assignment_regex(self, id):
        """
        Retrieves the object assignment regex by its ID.

        :param id: The ID of the object assignment regex.
        :type id: str
        :return: The object assignment regex with the specified ID, or an empty dictionary if not found.
        :rtype: dict
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__object_assignment_regexes_table.search(query.id == id)

        if result: 
            return result[0]
        else:
            return {}
        

    def get_object_assignment_regex_by_tagname(self, tagname):
        """
        Retrieves the object assignment regex by tagname.

        :param tagname: The tagname of the object assignment regex.
        :type tagname: str
        :return: The object assignment regex with the specified tagname, or an empty dictionary if not found.
        :rtype: dict
        """
        
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__object_assignment_regexes_table.search(query.tagname == tagname)

        if result: 
            return result[0]
        else:
            return {}
        

    def get_all_object_assignment_regexs(self):
        """
        Retrieves all object assignment regexes from the database.

        :return: A dictionary containing all object assignment regexes.
        :rtype: dict
        """
        
        with self.__rwlock.r_locked():
            result = self.__object_assignment_regexes_table.all()

        if result:
            return result
        else: 
            return {}
        

    def delete_object_assignment_regex(self, id):
        """
        Deletes an object assignment regex from the internal database.

        :param id: The ID of the object assignment regex to delete.
        :type id: str
        :return: None
        :rtype: None
        
        This function deletes an object assignment regex from the internal database. It removes the object assignment regex with the specified ID from the 'object_assignment_regex_table'. If there is an update function defined, it will be called after the deletion.
        
        Example:
            >>> delete_object_assignment_regex(1)
        """
        
        query = Query()
        with self.__rwlock.w_locked():
            self.__object_assignment_regexes_table.remove(query.id == id)
            if self.__object_assignment_regex_update_func:
                self.__object_assignment_regex_update_func()

        self.__trigger_write_event()


    def save_build_hmi_display(self, gfx_file_name, hmi_display):
        """
        Saves the canvas state for a specific GFX file.
        
        :param gfx_file_name: The name of the GFX file.
        :type gfx_file_name: str
        :param canvas_state: The state of the canvas to be saved.
        :type canvas_state: dict
        :return: None
        :rtype: None
        """
            
        # Check if entry exists
        query = Query()
        with self.__rwlock.w_locked():
            self.__build_hmi_displays_table.upsert(
                {
                    'gfx_file_name': gfx_file_name,
                    'state': hmi_display,
                    'timestamp': hmi_display.get('timestamp', int(time.time()))
                }, 
                query.gfx_file_name == gfx_file_name
            )

        self.__trigger_write_event()
    
    def get_build_hmi_display(self, gfx_file_name):
        """
        Retrieves the canvas state for a specific GFX file.
        
        :param gfx_file_name: The name of the GFX file.
        :type gfx_file_name: str
        :return: The canvas state for the specified GFX file, or None if not found.
        :rtype: dict or None
        """
        query = Query()
        with self.__rwlock.r_locked():
            result = self.__build_hmi_displays_table.search(query.gfx_file_name == gfx_file_name)
            
        if result:
            return result[0]['state']
        else:
            return None
    
    def delete_build_hmi_display(self, gfx_file_name):
        """
        Deletes the canvas state for a specific GFX file.
        
        :param gfx_file_name: The name of the GFX file.
        :type gfx_file_name: str
        :return: None
        :rtype: None
        """
        
        query = Query()
        with self.__rwlock.w_locked():
            self.__build_hmi_displays_table.remove(query.gfx_file_name == gfx_file_name)

        self.__trigger_write_event()
    
    def get_all_build_hmi_displays(self):
        """
        Retrieves all saved canvas states.
        
        :return: A list of all canvas states.
        :rtype: list
        """
            
        with self.__rwlock.r_locked():
            result = self.__build_hmi_displays_table.all()
            
        return result if result else []
    



    def close_db(self):
        """
        Closes the database connection. Safe to call multiple times and safe to
        call from atexit even if __init__ failed before __open_db().
        """
        db = getattr(self, '_Database__db', None)
        if db is None:
            return
        try:
            timer = getattr(self, '_Database__flush_timer', None)
            if timer is not None:
                timer.cancel()
            db.close()
            logging.info("Database connection closed.")
        except Exception:
            logging.exception("close_db failed")
        finally:
            self.__db = None


    def __del__(self):
        """
        Destructor for the LogicInternalDatabase class.
        """
        try:
            self.close_db()
        except Exception:
            pass
        