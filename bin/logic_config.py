# -*- coding: utf-8 -*-
import __main__
import uuid
try:
    from bin.logic_file_manager import Project_File_Manager
except Exception as e:
    from logic_file_manager import Project_File_Manager
try:
    from bin.logic_connection_string import add_password, split_password, uses_sql_login
    from bin.logic_secret_store import delete_sql_password, load_sql_password, save_sql_password
except ImportError:
    from logic_connection_string import add_password, split_password, uses_sql_login
    from logic_secret_store import delete_sql_password, load_sql_password, save_sql_password
import logging
import os
import json
import configparser
from tkinter import messagebox

class Config:
    """ This class is responsible for various operations with configuration INI file.
        ConfigParser module is a part of the standard Python library """

    DEFAULT_PROJECT_OPEN = 'None'
    DEFAULT_ACM_CONTROLLER_PROGRAM = 'Unscheduled'
    DEFAULT_ACM_CONTROLLER_TASK = 'Unscheduled_Routines'
    DEFAULT_ACM_HMI_TEMPLATE = '(RA-TPL)_Process_5_HMI_Display_FTViewSE_12.0_(1.0).xml'

    def __init__(self):
        """ Initialize configure parameters for INI file """
        self.config_dir = os.path.dirname(os.path.realpath(__main__.__file__))  # path to this directory
        self.__config_name = 'config.ini'  # name of config file
        self.__config_path = os.path.join(self.config_dir,'temp', self.__config_name)
        #
        # Value -- first place. Options -- second place.
        self.__window = 'Window'  # info about the main window
        self.__geometry = 'Geometry'  # size and position of the main window 'WxH±X±Y'
        self.__default_geometry = '1269x779+256+89'  # default window geometry 'WxH±X±Y'
        self.__state = 'State'  # state of the window: normal, zoomed, etc.
        self.__default_state = 'normal'  # normal state of the window
        self.__opened_path = 'OpenedPath'  # last opened path of the task or image
        self.__opened_project = 'OpenedProject'
        self.__default_opened_path = 'None'
        self.__default_opened_project = self.DEFAULT_PROJECT_OPEN
        self.__sash = 'Sash'
        self.__navigation = 'Navigation'
        self.__HMI_Displays = 'HMIDisplays'
        self.__PLC_Code = 'PLCCode'
        self.__tool = 'Tool'
        self.__panel_hidden = 'PanelHidden'
        self.__default_opened_path = 'Documents'
        self.__default_navigation_sash = [400,2]
        self.__default_tool_sash = [850,2]
        self.__default_navigation_panel_hidden = False
        
        #
        self.__sql = 'SQL'
        self.__connection_string = 'Connection string'
        self.__filter = 'filter'
        #
        self.__rectangle = 'RectangleWindow'  # info about the rolling window
        self.__rect_w = 'Width'  # width of rolling window
        self.__rect_h = 'Height'  # height of rolling window
        self.__default_rect_w, self.__default_rect_h = 320, 240  # default rolling window width/height
        #
        self.__recent = 'LastOpened'  # list of last opened paths
        self.__recent_number = 10  # number of recent paths
        #
        self.__user_activity = 'UserActivity'
        self.__user_id = 'UserId'
        #
        self.__config = configparser.ConfigParser()  # create config parser
        self.__config.optionxform = lambda option: option  # preserve case for letters
        # Create config directory if not exist
        if not os.path.isdir(self.config_dir):
            os.makedirs(self.config_dir)
        
        self.__ocr_settings = 'OCRSettings'
        self.__ocr_vertical_text_rotated_up = "VerticalTextRotatedUp"
        self.__default_ocr_vertical_text_rotated_up = True
        #
        self.__rolling = 'RollingWindow'  # info about the rolling window
        self.__roll_w = 'Width'  # width of rolling window
        self.__roll_h = 'Height'  # height of rolling window
        self.__default_roll_w, self.__default_roll_h = 320, 240  # default rolling window width/height
        self.__roll_dx = 'Horizontal step'  # horizontal step of the rolling window
        self.__roll_dy = 'Vertical step'  # vertical step of the rolling window
        

        self.__static_graphics = 'StaticGraphics'
        self.__fill_color = 'FillColor'
        self.__stroke_color = 'StrokeColor'
        self.__stroke_width = 'StrokeWidth' 

        self.__default_fill_color = 'CCCCCC'
        self.__default_stroke_color = 'AAAAAA'
        self.__default_stroke_width = '2'

        self.__display_width = 'Width'
        self.__display_height = 'Height'
        self.__display_color = 'Color'
        self.__display_with_page_links = 'PageLinks'
        self.__display_with_control_modules = 'ControlModules'

        # HMI Material Line Properties
        self.__hmi_material_line_width = 'HMI_Material_Line_Width'
        self.__hmi_material_line_fore_color = 'HMI_Material_Line_Fore_Color'
        self.__hmi_material_line_style = 'HMI_Material_Line_Style'

        self.__default_hmi_material_line_width = 2
        self.__default_hmi_material_line_fore_color = "AAAAAA"
        self.__default_hmi_material_line_style = 'solid'

        # HMI Signal Line Properties
        self.__hmi_signal_line_width = 'HMI_Signal_Line_Width'
        self.__hmi_signal_line_fore_color = 'HMI_Signal_Line_Fore_Color'
        self.__hmi_signal_line_has_dash_dot = 'HMI_Signal_Line_Has_Dash_Dot'

        self.__default_hmi_signal_line_width = 1
        self.__default_hmi_signal_line_fore_color = '0B84FD'
        self.__default_hmi_signal_line_has_dash_dot = True
        
        self.__hmi_library_core_type = 'HMICoreType'
        self.__hmi_library_catalog_number = 'HMICatalogNumber'
        self.__hmi_library_major_version = 'HMIMajorVersion'
        self.__hmi_library_minor_version = 'HMIMinorVersion'

        self.__hmi_display_template = 'HMIDisplayTemplate'

        self.__alarm_library_core_type = 'AlarmCoreType'
        self.__alarm_library_catalog_number = 'AlarmCatalogNumber'
        self.__alarm_library_major_version = 'AlarmMajorVersion'
        self.__alarm_library_minor_version = 'AlarmMinorVersion'

        self.__acm_project_core_type = 'ProjectCoreType'
        self.__acm_project_catalog_number = 'ProjectCatalogNumber'
        self.__acm_project_major_version = 'ProjectMajorVersion'
        self.__acm_project_minor_version = 'ProjectMinorVersion'

        self.__acm_controller_core_type = 'ControllerCoreType'
        self.__acm_controller_catalog_number = 'ControllerCatalogNumber'
        self.__acm_controller_major_version = 'ControllerMajorVersion'
        self.__acm_controller_minor_version = 'ControllerMinorVersion'
        self.__acm_controller_program = 'ControllerProgram'
        self.__acm_controller_task = 'ControllerTask'
        self.__acm_controller_software_revision = 'ControllerSoftwareRevision'
        self.__acm_batch_create_enabled = 'BatchCreateEnabled'
        self.__show_advanced_linking = 'ShowAdvancedLinking'

        self.__scanning_accuracy = 'ScanningAccuracy'
        self.__scanning_match_score = 'ScanningMatchScore'
        self.__scanning_match_score_default = 0.7
        self.__scanning_use_scale_invariant = 'UseScaleInvariant'
        self.__scanning_use_scale_invariant_default = False

        # Default ACM library made up of the CoreType, CatalogNumber, MajorVersion, and MinorVersion
        self.__default_hmi_library = '(RA-LIB) Process 5', 'FTViewSE', '5', '10'

        # Default ACM display template
        self.__default_hmi_display_template = self.DEFAULT_ACM_HMI_TEMPLATE

        # Defaualt ACM alarm library made up of the CoreType, CatalogNumber, MajorVersion, and MinorVersion
        self.__default_alarm_library = '(RA-LIB) ACM 2.00', 'FTAlarmEvent', '4', '0'

        # Default ACM project made up of the CoreType, CatalogNumber, MajorVersion, and MinorVersion
        self.__default_acm_project = '(RA-LIB) ACM 2.00', 'Basic_Project', '2', '0'

        # Default ACM controller made up of the CoreType, CatalogNumber, MajorVersion, and MinorVersion
        self.__default_acm_controller = '(RA-LIB) ACM 2.00', 'ControlLogix_Controller', '2', '1'

        self.__default_acm_controller_program = self.DEFAULT_ACM_CONTROLLER_PROGRAM
        self.__default_acm_controller_task = self.DEFAULT_ACM_CONTROLLER_TASK
        self.__default_acm_controller_software_revision = '35'
        self.__default_acm_batch_create_enabled = True
        self.__default_show_advanced_linking = False
        # Default horizontal step is 1/2 of the rolling window width
        self.__default_roll_dx = int(self.__default_roll_w / 2)  # should be integer
        # Default vertical step is 1/2 of the rolling window height
        self.__default_roll_dy = int(self.__default_roll_h / 2)  # should be integer
        # Create new config file if not exist or read existing one

        self.__default_display_width = 1920
        self.__default_display_height = 1080
        self.__default_display_color = 'E0E0E0'
        self.__default_display_page_links = True
        self.__default_display_control_modules = True

        # LLM Inference settings — see set_llm_inference_settings /
        # get_llm_inference_settings. Empty ``Provider`` means auto-detect
        # (optional ``genai_bridge`` enterprise gateway, else Ollama);
        # ``openai`` / ``ollama`` overrides come from the Settings dialog.
        # The OpenAI API key itself is NOT stored here — it lives in a
        # DPAPI-protected blob (see logic_secret_store).
        self.__llm_inference = 'LLMInference'
        self.__llm_provider = 'Provider'
        self.__llm_openai_base_url = 'OpenAIBaseURL'
        self.__llm_openai_model = 'OpenAIModel'
        self.__llm_openai_organization = 'OpenAIOrganization'
        self.__llm_ollama_mode = 'OllamaMode'
        self.__llm_ollama_remote_url = 'OllamaRemoteURL'
        self.__llm_ollama_model = 'OllamaModel'
        self.__default_llm_provider = ''
        self.__default_llm_openai_base_url = ''
        self.__default_llm_openai_model = 'gpt-4.1-mini'
        self.__default_llm_openai_organization = ''
        self.__default_llm_ollama_mode = 'bundled'
        self.__default_llm_ollama_remote_url = ''
        self.__default_llm_ollama_model = 'reasoning:4b'

        # FactoryTalk View SE Add Component Tool settings — stored under the
        # existing [HMIDisplays] section. The application name is not
        # persisted here; it is derived from the currently-open project
        # name at export time. SEAddComponent.exe inherits the invoking
        # Windows session's FactoryTalk identity, so no /U or /P are
        # collected either.
        self.__seadd_exe_path = 'SEAddComponentExePath'
        self.__seadd_application_type = 'SEAddComponentApplicationType'
        self.__seadd_area_name = 'SEAddComponentAreaName'
        self.__seadd_overwrite = 'SEAddComponentOverwrite'
        # Last FactoryTalk View SE application name the user picked in
        # the "Build HMI → View Designer" flow. Persisted so the picker
        # dialog can pre-select the same app next time.
        self.__seadd_last_app_name = 'SEAddComponentLastAppName'

        self.__default_seadd_exe_path = (
            r'C:\Program Files (x86)\Rockwell Software\RSView Enterprise\SEAddComponent.exe'
        )
        self.__default_seadd_application_type = 'Distributed'
        self.__default_seadd_area_name = '/'
        self.__default_seadd_overwrite = False
        self.__default_seadd_last_app_name = ''

        # Rockwell Logix Designer SDK — location of the wheel distributed
        # by the Studio 5000 Logix Designer SDK installer. Only used to
        # compose an install-guide error message when the wheel has not
        # yet been ``pip install``'d into the active Python environment.
        # Stored under the existing [PLCCode] section so PLC-related tool
        # settings live together.
        self.__logix_sdk_wheel_dir_key = 'LogixDesignerSdkWheelDir'
        from bin.logic_logix_designer import DEFAULT_LOGIX_SDK_WHEEL_DIR
        self.__default_logix_sdk_wheel_dir = DEFAULT_LOGIX_SDK_WHEEL_DIR

        # Rockwell FactoryTalk Logix Echo SDK — location of the
        # ``ftecho_sdk`` wheel distributed by the Logix Echo installer.
        # Used only to compose an install-guide error message when the
        # wheel has not yet been ``pip install``'d into the active Python
        # environment. Stored under [PLCCode] alongside the Logix
        # Designer SDK key.
        self.__logix_echo_sdk_wheel_dir_key = 'LogixEchoSdkWheelDir'
        from bin.logic_logix_echo import DEFAULT_LOGIX_ECHO_SDK_WHEEL_DIR
        self.__default_logix_echo_sdk_wheel_dir = DEFAULT_LOGIX_ECHO_SDK_WHEEL_DIR

        if not os.path.isfile(self.__config_path):
            self.__new_config()  # create new config
        else:
            self.__config.read(self.__config_path, encoding='utf-8')  # read existing config file

    def __check_section(self, section):
        """ Check if section exists and create it if not """
        if not self.__config.has_section(section):
            self.__config.add_section(section)

    def get_connection_string(self):
        """ Get connection string, with the SQL login password restored from the DPAPI store """
        try:
            stored = self.__config[self.__sql][self.__connection_string]
        except KeyError:  # if the key is not in the dictionary of config
            return ''
        stripped, legacy_password = split_password(stored)
        if legacy_password is not None:
            # Older versions wrote PWD= into config.ini; move it out and rewrite the file.
            self.set_connection_string(stored)
            self.save()
            return stored
        if uses_sql_login(stripped):
            password = load_sql_password()
            if password:
                return add_password(stripped, password)
        return stripped

    def set_objects_filter(self, filter):
        """ Set main window size """
        self.__check_section(self.__sql)
        self.__config[self.__sql][self.__filter] = json.dumps(filter)


    def set_ocr_vertical_text_rotated_up(self, selection):
        """ Set OCR vertical text rotation """
        self.__check_section(self.__ocr_settings)
        self.__config[self.__ocr_settings][self.__ocr_vertical_text_rotated_up] = str(selection)



    def get_ocr_vertical_text_rotated_up(self):
        """ Get OCR vertical text rotation """
        try:
            selection = self.__config[self.__ocr_settings][self.__ocr_vertical_text_rotated_up]
            return selection == 'True'
        except KeyError:
            return self.__default_ocr_vertical_text_rotated_up



    def get_user_id(self):
        """ Get user id for user activity
        
            returns tuple with bool to say whether just genterated"""
        try:
            user_id = self.__config[self.__user_activity][self.__user_id]
            return user_id, False
        except KeyError:
            user_id = str(uuid.uuid4())
            self.__check_section(self.__user_activity)
            self.__config[self.__user_activity][self.__user_id] = user_id
            return user_id, True
        
    def get_objects_filter(self):
        """ Get connection string """
        try:
            filter = self.__config[self.__sql][self.__filter]
            return json.loads(filter)
        except KeyError:  # if the key is not in the dictionary of config
            return {}

    def set_connection_string(self, connection_string):
        """ Set connection string; the password goes to the DPAPI store, never to config.ini """
        stripped, password = split_password(connection_string)
        self.__check_section(self.__sql)
        self.__config[self.__sql][self.__connection_string] = stripped
        if not password:
            delete_sql_password()
            return
        try:
            save_sql_password(password)
        except (RuntimeError, OSError) as error:
            delete_sql_password()
            logging.warning('SQL Server password was not saved: %s', type(error).__name__)

    def clear_connection_string(self):
        """ Forget the saved connection string and SQL login password """
        if self.__config.has_section(self.__sql):
            self.__config.remove_option(self.__sql, self.__connection_string)
        delete_sql_password()

    def get_win_geometry(self):
        """ Get main window size and position """
        try:
            return self.__config[self.__window][self.__geometry]
        except KeyError:  # if the key is not in the dictionary of config
            return self.__default_geometry

    def set_win_geometry(self, geometry):
        """ Set main window size """
        self.__check_section(self.__window)
        self.__config[self.__window][self.__geometry] = geometry

    def get_win_state(self):
        """ Get main window state: normal, zoomed, etc. """
        try:
            return self.__config[self.__window][self.__state]
        except KeyError:  # if the key is not in the dictionary of config
            return self.__default_state

    def set_win_state(self, state):
        """ Set main window state: normal, zoomed, etc. """
        self.__check_section(self.__window)
        self.__config[self.__window][self.__state] = state

    def get_opened_path(self):
        """ Get opened path if it wasn't closed previously or return an empty string """
        try:
            path = self.__config[self.__window][self.__opened_path]
            if path == self.__default_opened_path or not os.path.exists(path):
                return ''
            else:
                return path
        except KeyError:  # if the key is not in the dictionary of config
            return ''

    def get_opened_project(self):
        """ Get opened project if it wasn't closed previously or return an empty string """
        try:
            project = self.__config[self.__window][self.__opened_project]
            if project == self.__default_opened_project:
                return self.DEFAULT_PROJECT_OPEN
            else:
                return project
        except KeyError:  # if the key is not in the dictionary of config
            return self.DEFAULT_PROJECT_OPEN
            
    def set_is_navigation_panel_hidden(self, state):
        """ Set position tuple of the tool sash """
        self.__check_section(self.__navigation)
        self.__config[self.__navigation][self.__panel_hidden] = str(state)
    
    def get_is_navigation_panel_hidden(self):
        """ Set position tuple of the tool sash """
        try:
            state = self.__config[self.__navigation][self.__panel_hidden]
            return state == 'True'
        except KeyError:  # if the key is not in the dictionary of config
            return self.__default_navigation_panel_hidden


    def set_hmi_display_settings(self, width=None, height=None, color=None, page_links=None, control_modules=None):
        """ Set HMI display genereation settings """
        self.__check_section(self.__HMI_Displays)
        if width:
            self.__config[self.__HMI_Displays][self.__display_width] = str(width)
        else:
            self.__config[self.__HMI_Displays][self.__display_width] = str(self.__default_display_width)
        if height:
            self.__config[self.__HMI_Displays][self.__display_height] = str(height)
        else:
            self.__config[self.__HMI_Displays][self.__display_height] = str(self.__default_display_height)
        if color:
            self.__config[self.__HMI_Displays][self.__display_color] = color
        else:
            self.__config[self.__HMI_Displays][self.__display_color] = self.__default_display_color
        if page_links is not None:
            self.__config[self.__HMI_Displays][self.__display_with_page_links] = str(page_links)
        else:
            self.__config[self.__HMI_Displays][self.__display_with_page_links] = str(self.__default_display_page_links)
        if control_modules is not None:
            self.__config[self.__HMI_Displays][self.__display_with_control_modules] = str(control_modules)
        else:
            self.__config[self.__HMI_Displays][self.__display_with_control_modules] = str(self.__default_display_control_modules)

    def get_hmi_display_settings(self):
        """ Get tuple (width, height, include page links, include control modules) of the hmi display settings """
        try:
            w = self.__config[self.__HMI_Displays][self.__display_width]
            h = self.__config[self.__HMI_Displays][self.__display_height]
            color = self.__config[self.__HMI_Displays][self.__display_color]
            p = self.__config[self.__HMI_Displays][self.__display_with_page_links]
            c = self.__config[self.__HMI_Displays][self.__display_with_control_modules]
            return int(w), int(h), color, p == 'True', c == 'True'
        except KeyError:  # if the key is not in the dictionary of config
            return (self.__default_display_width, self.__default_display_height,
                    self.__default_display_color, self.__default_display_page_links, self.__default_display_control_modules)


    def set_llm_inference_settings(self, provider=None, openai_base_url=None,
                                    openai_model=None, openai_organization=None,
                                    ollama_mode=None, ollama_remote_url=None,
                                    ollama_model=None):
        """ Set LLM inference settings.

        ``provider`` is ``''`` (auto — optional ``genai_bridge`` enterprise
        gateway, else Ollama), ``'openai'`` (external OpenAI-compatible
        endpoint using a user key loaded from the DPAPI store), or
        ``'ollama'``. Passing ``None`` for any argument resets that field to
        its default.
        """
        self.__check_section(self.__llm_inference)
        if provider is not None:
            self.__config[self.__llm_inference][self.__llm_provider] = str(provider)
        else:
            self.__config[self.__llm_inference][self.__llm_provider] = self.__default_llm_provider
        if openai_base_url is not None:
            self.__config[self.__llm_inference][self.__llm_openai_base_url] = str(openai_base_url)
        else:
            self.__config[self.__llm_inference][self.__llm_openai_base_url] = self.__default_llm_openai_base_url
        if openai_model is not None:
            self.__config[self.__llm_inference][self.__llm_openai_model] = str(openai_model)
        else:
            self.__config[self.__llm_inference][self.__llm_openai_model] = self.__default_llm_openai_model
        if openai_organization is not None:
            self.__config[self.__llm_inference][self.__llm_openai_organization] = str(openai_organization)
        else:
            self.__config[self.__llm_inference][self.__llm_openai_organization] = self.__default_llm_openai_organization
        if ollama_mode is not None:
            self.__config[self.__llm_inference][self.__llm_ollama_mode] = str(ollama_mode)
        else:
            self.__config[self.__llm_inference][self.__llm_ollama_mode] = self.__default_llm_ollama_mode
        if ollama_remote_url is not None:
            self.__config[self.__llm_inference][self.__llm_ollama_remote_url] = str(ollama_remote_url)
        else:
            self.__config[self.__llm_inference][self.__llm_ollama_remote_url] = self.__default_llm_ollama_remote_url
        if ollama_model is not None:
            self.__config[self.__llm_inference][self.__llm_ollama_model] = str(ollama_model)
        else:
            self.__config[self.__llm_inference][self.__llm_ollama_model] = self.__default_llm_ollama_model


    def get_llm_inference_settings(self):
        """ Return LLM inference settings as a dict.

        Keys: ``provider``, ``openai_base_url``, ``openai_model``,
        ``openai_organization``, ``ollama_mode``, ``ollama_remote_url``,
        ``ollama_model``. Missing keys fall back to per-field defaults.
        """
        def _read(key, default):
            try:
                return self.__config[self.__llm_inference][key]
            except KeyError:
                return default

        return {
            'provider': _read(self.__llm_provider, self.__default_llm_provider),
            'openai_base_url': _read(self.__llm_openai_base_url, self.__default_llm_openai_base_url),
            'openai_model': _read(self.__llm_openai_model, self.__default_llm_openai_model),
            'openai_organization': _read(self.__llm_openai_organization, self.__default_llm_openai_organization),
            'ollama_mode': _read(self.__llm_ollama_mode, self.__default_llm_ollama_mode),
            'ollama_remote_url': _read(self.__llm_ollama_remote_url, self.__default_llm_ollama_remote_url),
            'ollama_model': _read(self.__llm_ollama_model, self.__default_llm_ollama_model),
        }

    def set_hmi_material_line_properties(self, width=None, fore_color=None, style=None):
        """ Set HMI material line properties """
        self.__check_section(self.__HMI_Displays)
        if width:
            self.__config[self.__HMI_Displays][self.__hmi_material_line_width] = str(width)
        else:
            self.__config[self.__HMI_Displays][self.__hmi_material_line_width] = self.__default_hmi_material_line_width
        if fore_color:
            self.__config[self.__HMI_Displays][self.__hmi_material_line_fore_color] = fore_color
        else:
            self.__config[self.__HMI_Displays][self.__hmi_material_line_fore_color] = self.__default_hmi_material_line_fore_color
        if style:
            self.__config[self.__HMI_Displays][self.__hmi_material_line_style] = style
        else:
            self.__config[self.__HMI_Displays][self.__hmi_material_line_style] = self.__default_hmi_material_line_style


    def get_hmi_material_line_properties(self):
        """ Get HMI material line properties """
        try:
            width = self.__config[self.__HMI_Displays][self.__hmi_material_line_width]
            fore_color = self.__config[self.__HMI_Displays][self.__hmi_material_line_fore_color]
            style = self.__config[self.__HMI_Displays][self.__hmi_material_line_style]
            return width, fore_color, style
        except KeyError:
            return (self.__default_hmi_material_line_width, 
                    self.__default_hmi_material_line_fore_color, 
                    self.__default_hmi_material_line_style)
        

    def set_hmi_signal_line_properties(self, width=None, fore_color=None, has_dash_dot=None):
        """ Set HMI signal line properties """
        self.__check_section(self.__HMI_Displays)
        if width:
            self.__config[self.__HMI_Displays][self.__hmi_signal_line_width] = str(width)
        else:
            self.__config[self.__HMI_Displays][self.__hmi_signal_line_width] = self.__default_hmi_signal_line_width
        if fore_color:
            self.__config[self.__HMI_Displays][self.__hmi_signal_line_fore_color] = fore_color
        else:
            self.__config[self.__HMI_Displays][self.__hmi_signal_line_fore_color] = self.__default_hmi_signal_line_fore_color
        if has_dash_dot is not None:
            self.__config[self.__HMI_Displays][self.__hmi_signal_line_has_dash_dot] = str(has_dash_dot)
        else:
            self.__config[self.__HMI_Displays][self.__hmi_signal_line_has_dash_dot] = str(self.__default_hmi_signal_line_has_dash_dot)
    
    
    def get_hmi_signal_line_properties(self):
        """ Get HMI signal line properties """
        try:
            width = self.__config[self.__HMI_Displays][self.__hmi_signal_line_width]
            fore_color = self.__config[self.__HMI_Displays][self.__hmi_signal_line_fore_color]
            has_dash_dot = self.__config[self.__HMI_Displays][self.__hmi_signal_line_has_dash_dot]
            return width, fore_color, has_dash_dot == 'True'
        except KeyError:
            return (self.__default_hmi_signal_line_width, 
                    self.__default_hmi_signal_line_fore_color, 
                    self.__default_hmi_signal_line_has_dash_dot)
        
    
    def set_hmi_library(self, CoreType, CatalogNumber, MajorVersion, MinorVersion):
        """ Set HMI library for ACM """
        self.__check_section(self.__HMI_Displays)

        self.__config[self.__HMI_Displays][self.__hmi_library_core_type] = CoreType
        self.__config[self.__HMI_Displays][self.__hmi_library_catalog_number] = CatalogNumber
        self.__config[self.__HMI_Displays][self.__hmi_library_major_version] = MajorVersion
        self.__config[self.__HMI_Displays][self.__hmi_library_minor_version] = MinorVersion


    def get_hmi_library(self):
        """ Get HMI library for ACM """
        try:
            core_type = self.__config[self.__HMI_Displays][self.__hmi_library_core_type]
            catalog_number = self.__config[self.__HMI_Displays][self.__hmi_library_catalog_number]
            major_version = self.__config[self.__HMI_Displays][self.__hmi_library_major_version]
            minor_version = self.__config[self.__HMI_Displays][self.__hmi_library_minor_version]
            return core_type, catalog_number, major_version, minor_version
        except KeyError:  # if the key is not in the dictionary of config
            return self.__default_hmi_library
        

    def set_alarm_library(self, CoreType, CatalogNumber, MajorVersion, MinorVersion):
        """ Set alarm library for ACM """
        self.__check_section(self.__HMI_Displays)

        self.__config[self.__HMI_Displays][self.__alarm_library_core_type] = CoreType
        self.__config[self.__HMI_Displays][self.__alarm_library_catalog_number] = CatalogNumber
        self.__config[self.__HMI_Displays][self.__alarm_library_major_version] = MajorVersion
        self.__config[self.__HMI_Displays][self.__alarm_library_minor_version] = MinorVersion

    
    def get_alarm_library(self):
        """ Get alarm library for ACM """
        try:
            core_type = self.__config[self.__HMI_Displays][self.__alarm_library_core_type]
            catalog_number = self.__config[self.__HMI_Displays][self.__alarm_library_catalog_number]
            major_version = self.__config[self.__HMI_Displays][self.__alarm_library_major_version]
            minor_version = self.__config[self.__HMI_Displays][self.__alarm_library_minor_version]
            return core_type, catalog_number, major_version, minor_version
        except KeyError:  # if the key is not in the dictionary of config
            return self.__default_alarm_library
        

    def set_hmi_display_template(self, display_template):
        """ Set HMI display template for ACM """
        self.__check_section(self.__HMI_Displays)
        self.__config[self.__HMI_Displays][self.__hmi_display_template] = display_template


    def get_hmi_display_template(self):
        """ Get HMI display template for ACM """
        try:
            display_template = self.__config[self.__HMI_Displays][self.__hmi_display_template]
            return display_template
        except KeyError:
            return self.__default_hmi_display_template


    def set_extracted_hmi_graphic_settings(self, fill_color, stroke_color, stroke_width):
        """ Set tuple (fill_color, stroke_color, stroke_width) for the default configuration 
        for extracting graphic"""
        self.__check_section(self.__static_graphics)
        if fill_color:
            self.__config[self.__static_graphics][self.__fill_color] = str(fill_color)
        else:
            self.__config[self.__static_graphics][self.__fill_color] = self.__default_fill_color
        if stroke_color:
            self.__config[self.__static_graphics][self.__stroke_color] = str(stroke_color)
        else:
            self.__config[self.__static_graphics][self.__stroke_color] = self.__default_stroke_color
        if stroke_width:
            self.__config[self.__static_graphics][self.__stroke_width] = str(stroke_width)
        else:
            self.__config[self.__static_graphics][self.__stroke_width] = self.__default_stroke_width


        

    def get_extracted_hmi_graphic_settings(self):
        """ Get tuple (fill_color, stroke_color, stroke_width) for the default configuration 
        for extracting graphic"""
        try:
            fill_color = self.__config[self.__static_graphics][self.__fill_color]
            stroke_color = self.__config[self.__static_graphics][self.__stroke_color]
            stroke_width = self.__config[self.__static_graphics][self.__stroke_width]
            return fill_color, stroke_color, stroke_width
        except KeyError:  # if the key is not in the dictionary of config
            return (self.__default_fill_color, self.__default_stroke_color, 
                        self.__default_stroke_width)
        

    def set_scanning_match_score(self, score):
        """ Set scanning match score """
        self.__check_section(self.__scanning_accuracy)
        self.__config[self.__scanning_accuracy][self.__scanning_match_score] = str(score)


    
    def get_scanning_match_score(self):
        """ Get scanning match score """
        try:
            score = self.__config[self.__scanning_accuracy][self.__scanning_match_score]
            return float(score)
        except KeyError:
            return self.__scanning_match_score_default


    def set_scanning_use_scale_invariant(self, use_scale_invariant):
        """ Set scanning use scale invariant """
        self.__check_section(self.__scanning_accuracy)
        self.__config[self.__scanning_accuracy][self.__scanning_use_scale_invariant] = str(use_scale_invariant)


    def get_scanning_use_scale_invariant(self):
        """ Get scanning use scale invariant """
        try:
            use_scale_invariant = self.__config[self.__scanning_accuracy][self.__scanning_use_scale_invariant]
            return use_scale_invariant == 'True'
        except KeyError:
            return self.__scanning_use_scale_invariant_default
        

    def set_acm_project(self, CoreType, CatalogNumber, MajorVersion, MinorVersion):
        """ Set project name for the ACM """
        self.__check_section(self.__PLC_Code)

        self.__config[self.__PLC_Code][self.__acm_project_core_type] = CoreType
        self.__config[self.__PLC_Code][self.__acm_project_catalog_number] = CatalogNumber
        self.__config[self.__PLC_Code][self.__acm_project_major_version] = MajorVersion
        self.__config[self.__PLC_Code][self.__acm_project_minor_version] = MinorVersion


    def get_acm_project(self):
        """ Get project name for the ACM """
        try:
            core_type = self.__config[self.__PLC_Code][self.__acm_project_core_type]
            catalog_number = self.__config[self.__PLC_Code][self.__acm_project_catalog_number]
            major_version = self.__config[self.__PLC_Code][self.__acm_project_major_version]
            minor_version = self.__config[self.__PLC_Code][self.__acm_project_minor_version]
            return core_type, catalog_number, major_version, minor_version
        except KeyError:  # if the key is not in the dictionary of config
            return self.__default_acm_project
        

    def set_acm_controller(self, CoreType, CatalogNumber, MajorVersion, MinorVersion):
        """ Set controller name for the ACM """
        self.__check_section(self.__PLC_Code)
        self.__config[self.__PLC_Code][self.__acm_controller_core_type] = CoreType
        self.__config[self.__PLC_Code][self.__acm_controller_catalog_number] = CatalogNumber
        self.__config[self.__PLC_Code][self.__acm_controller_major_version] = MajorVersion
        self.__config[self.__PLC_Code][self.__acm_controller_minor_version] = MinorVersion


    def get_acm_controller(self):
        """ Get controller name for the ACM """
        try:
            core_type = self.__config[self.__PLC_Code][self.__acm_controller_core_type]
            catalog_number = self.__config[self.__PLC_Code][self.__acm_controller_catalog_number]    
            major_version = self.__config[self.__PLC_Code][self.__acm_controller_major_version]
            minor_version = self.__config[self.__PLC_Code][self.__acm_controller_minor_version]
            return core_type, catalog_number, major_version, minor_version
        except KeyError:  # if the key is not in the dictionary of config
            return self.__default_acm_controller
        
    def set_acm_controller_program(self, program_name):
        """ Set controller program name for the ACM """
        self.__check_section(self.__PLC_Code)
        self.__config[self.__PLC_Code][self.__acm_controller_program] = program_name


    def get_acm_controller_program(self):
        """ Get controller program name for the ACM """
        try:
            program_name = self.__config[self.__PLC_Code][self.__acm_controller_program]
            return program_name
        except KeyError:
            return self.__default_acm_controller_program
        
    def set_acm_controller_task(self, task_name):
        """ Set controller task name for the ACM """
        self.__check_section(self.__PLC_Code)
        self.__config[self.__PLC_Code][self.__acm_controller_task] = task_name

    
    def get_acm_controller_task(self):
        """ Get controller task name for the ACM """
        try:
            task_name = self.__config[self.__PLC_Code][self.__acm_controller_task]
            return task_name
        except KeyError:
            return self.__default_acm_controller_task

    def set_acm_controller_software_revision(self, software_revision):
        """ Set controller PLC firmware / software revision for the ACM """
        self.__check_section(self.__PLC_Code)
        self.__config[self.__PLC_Code][self.__acm_controller_software_revision] = str(software_revision)

    def get_acm_controller_software_revision(self):
        """ Get controller PLC firmware / software revision for the ACM """
        try:
            software_revision = self.__config[self.__PLC_Code][self.__acm_controller_software_revision]
            return software_revision
        except KeyError:
            return self.__default_acm_controller_software_revision
    
    def set_acm_batch_create_enabled(self, enabled):
        """ Set ACM batch create mode enabled/disabled """
        self.__check_section(self.__PLC_Code)
        self.__config[self.__PLC_Code][self.__acm_batch_create_enabled] = str(enabled)

    def get_acm_batch_create_enabled(self):
        """ Get ACM batch create mode enabled/disabled """
        try:
            enabled = self.__config[self.__PLC_Code][self.__acm_batch_create_enabled]
            return enabled == 'True'
        except KeyError:
            return self.__default_acm_batch_create_enabled
    
    def set_show_advanced_linking(self, enabled):
        """ Set show advanced linking enabled/disabled """
        self.__check_section(self.__PLC_Code)
        self.__config[self.__PLC_Code][self.__show_advanced_linking] = str(enabled)

    def get_show_advanced_linking(self):
        """ Get show advanced linking enabled/disabled """
        try:
            enabled = self.__config[self.__PLC_Code][self.__show_advanced_linking]
            return enabled == 'True'
        except KeyError:
            return self.__default_show_advanced_linking
                        

    def set_seadd_component_settings(self,
                                     exe_path=None,
                                     application_type=None,
                                     area_name=None,
                                     overwrite=None):
        """ Persist the FactoryTalk View SE Add Component Tool settings under
            the ``[HMIDisplays]`` section. Any argument left as ``None`` is
            written as its default value. Booleans are serialised via
            ``str()`` to stay compatible with the existing round-trip idiom
            (``value == 'True'``). """
        self.__check_section(self.__HMI_Displays)
        section = self.__config[self.__HMI_Displays]
        section[self.__seadd_exe_path] = (
            exe_path if exe_path is not None else self.__default_seadd_exe_path)
        section[self.__seadd_application_type] = (
            application_type if application_type is not None
            else self.__default_seadd_application_type)
        section[self.__seadd_area_name] = (
            area_name if area_name is not None else self.__default_seadd_area_name)
        section[self.__seadd_overwrite] = str(
            bool(overwrite) if overwrite is not None else self.__default_seadd_overwrite)

    def get_seadd_component_settings(self):
        """ Return the FactoryTalk View SE Add Component Tool settings as a
            dict. Missing keys fall back to defaults. Booleans are decoded
            from the persisted ``'True'`` / ``'False'`` strings. """
        try:
            section = self.__config[self.__HMI_Displays]
        except KeyError:
            section = {}
        def _get(key, default):
            try:
                return section[key]
            except KeyError:
                return default
        return {
            'exe_path': _get(self.__seadd_exe_path, self.__default_seadd_exe_path),
            'application_type': _get(self.__seadd_application_type,
                                     self.__default_seadd_application_type),
            'area_name': _get(self.__seadd_area_name, self.__default_seadd_area_name),
            'overwrite': _get(self.__seadd_overwrite,
                              str(self.__default_seadd_overwrite)) == 'True',
        }

    def set_seadd_last_app_name(self, application_name):
        """ Remember the FactoryTalk View SE application the user picked in
            the "Build HMI → View Designer" picker so the same entry can
            be pre-selected next time. Empty / ``None`` clears it. """
        self.__check_section(self.__HMI_Displays)
        section = self.__config[self.__HMI_Displays]
        section[self.__seadd_last_app_name] = (application_name or '').strip()

    def get_seadd_last_app_name(self):
        """ Return the last FactoryTalk View SE application name picked by
            the user (or ``''`` when nothing has been persisted yet). """
        try:
            return self.__config[self.__HMI_Displays][self.__seadd_last_app_name]
        except KeyError:
            return self.__default_seadd_last_app_name


    def get_logix_designer_sdk_wheel_dir(self):
        """ Return the path to the Rockwell Logix Designer SDK wheel
            (``*.whl``) file, or a directory that contains one. Persisted
            under ``[PLCCode]`` if the user manually overrides the
            default in the INI; otherwise falls back to the Studio 5000
            installer's Public Documents path. Used only to compose an
            install-guide error message when the SDK has not been
            ``pip install``'d into the active Python environment. """
        try:
            return self.__config[self.__PLC_Code][self.__logix_sdk_wheel_dir_key]
        except KeyError:
            return self.__default_logix_sdk_wheel_dir


    def get_logix_echo_sdk_wheel_dir(self):
        """ Return the path to the Rockwell FactoryTalk Logix Echo SDK
            wheel (``ftecho_sdk-*.whl``) file, or a directory that
            contains one. Persisted under ``[PLCCode]`` if the user
            manually overrides the default in the INI; otherwise falls
            back to the FactoryTalk Logix Echo installer's Public
            Documents path. Used only to compose an install-guide error
            message when the SDK has not been ``pip install``'d into the
            active Python environment. """
        try:
            return self.__config[self.__PLC_Code][self.__logix_echo_sdk_wheel_dir_key]
        except KeyError:
            return self.__default_logix_echo_sdk_wheel_dir


    def set_logix_designer_sdk_wheel_dir(self, path):
        """ Persist the Rockwell Logix Designer SDK wheel override under
            ``[PLCCode]``. ``path`` is normally a full path to the
            ``logix_designer_sdk-*.whl`` file, but a directory containing
            that wheel is also accepted. Pass an empty string / ``None``
            to clear the override so the getter falls back to the
            installer default. """
        self.__check_section(self.__PLC_Code)
        value = (path or '').strip()
        section = self.__config[self.__PLC_Code]
        if value:
            section[self.__logix_sdk_wheel_dir_key] = value
        elif self.__logix_sdk_wheel_dir_key in section:
            del section[self.__logix_sdk_wheel_dir_key]


    def set_logix_echo_sdk_wheel_dir(self, path):
        """ Persist the Rockwell FactoryTalk Logix Echo SDK wheel
            override under ``[PLCCode]``. ``path`` is normally a full
            path to the ``ftecho_sdk-*.whl`` file, but a directory
            containing that wheel is also accepted. Pass an empty string
            / ``None`` to clear the override so the getter falls back to
            the installer default. """
        self.__check_section(self.__PLC_Code)
        value = (path or '').strip()
        section = self.__config[self.__PLC_Code]
        if value:
            section[self.__logix_echo_sdk_wheel_dir_key] = value
        elif self.__logix_echo_sdk_wheel_dir_key in section:
            del section[self.__logix_echo_sdk_wheel_dir_key]


    def set_roll_size(self, width=None, height=None):
        """ Set tuple (width, height) of the rolling window """
        self.__check_section(self.__rolling)
        if width:
            self.__config[self.__rolling][self.__roll_w] = str(width)
        else:
            self.__config[self.__rolling][self.__roll_w] = str(self.__default_roll_w)
        if height:
            self.__config[self.__rolling][self.__roll_h] = str(height)
        else:
            self.__config[self.__rolling][self.__roll_h] = str(self.__default_roll_h)


    def get_roll_size(self):
        """ Get tuple (width, height) of the rolling window """
        try:
            w = self.__config[self.__rolling][self.__roll_w]
            h = self.__config[self.__rolling][self.__roll_h]
            return int(w), int(h)
        except KeyError:  # if the key is not in the dictionary of config
            return self.__default_roll_w, self.__default_roll_h

    def get_step_size(self):
        """ Get tuple (dx, dy) of the rolling window steps """
        try:
            dx = self.__config[self.__rolling][self.__roll_dx]
            dy = self.__config[self.__rolling][self.__roll_dy]
            return int(dx), int(dy)
        except KeyError:  # if the key is not in the dictionary of config
            return self.__default_roll_dx, self.__default_roll_dy

    def set_step_size(self, dx=None, dy=None):
        """ Set tuple (dx, dy) of the rolling window steps """
        self.__check_section(self.__rolling)
        if dx:
            self.__config[self.__rolling][self.__roll_dx] = str(dx)
        else:
            self.__config[self.__rolling][self.__roll_dx] = str(self.__default_roll_dx)
        if dy:
            self.__config[self.__rolling][self.__roll_dy] = str(dy)
        else:
            self.__config[self.__rolling][self.__roll_dy] = str(self.__default_roll_dy)

            
    def set_tool_sash(self, position):
        """ Set position tuple of the tool sash """
        self.__check_section(self.__sash)
        self.__config[self.__sash][self.__tool] = json.dumps(position)

        
    def get_tool_sash(self):
        """ Get position tuple of the tool sash """
        try:
            position = json.loads(self.__config[self.__sash][self.__tool])
            return position
        except KeyError:  # if the key is not in the dictionary of config
            return self.__default_tool_sash
            
    def set_navigation_sash(self, position):
        """ Set position tuple of the navigation sash """
        self.__check_section(self.__sash)
        self.__config[self.__sash][self.__navigation] = json.dumps(position)
        
    def get_navigation_sash(self):
        """ Get position tuple of the navigation sash """
        try:
            position = json.loads(self.__config[self.__sash][self.__navigation])
            return position
        except KeyError:  # if the key is not in the dictionary of config
            return self.__default_navigation_sash

    def set_opened_path(self, path=None):
        """ Remember opened path to the config INI file """
        self.__check_section(self.__window)
        if path:
            self.__config[self.__window][self.__opened_path] = path
        else:
            self.__config[self.__window][self.__opened_path] = self.__default_opened_path


    def set_opened_project(self, project=None):
        """ Remember opened project to the config INI file """
        self.__check_section(self.__window)
        if project:
            self.__config[self.__window][self.__opened_project] = project
        else:
            self.__config[self.__window][self.__opened_project] = self.__default_opened_project


    def get_rect_size(self):
        """ Get tuple (width, height) of the rolling window """
        try:
            w = self.__config[self.__rectangle][self.__rect_w]
            h = self.__config[self.__rectangle][self.__rect_h]
            return int(w), int(h)
        except KeyError:  # if the key is not in the dictionary of config
            return self.__default_rect_w, self.__default_rect_h


    def set_rect_size(self, width=None, height=None):
        """ Set tuple (width, height) of the rolling window """
        self.__check_section(self.__rectangle)
        if width:
            self.__config[self.__rectangle][self.__rect_w] = str(width)
        else:
            self.__config[self.__rectangle][self.__rect_w] = str(self.__default_rect_w)
        if height:
            self.__config[self.__rectangle][self.__rect_h] = str(height)
        else:
            self.__config[self.__rectangle][self.__rect_h] = str(self.__default_rect_h)



    def get_recent_projects_list(self):
        """ Get list of recently opened image paths """
        try:
            lst = self.__config.items(self.__recent)  # list of (key, value) pairs
            lst = [project for _, project in lst]  # leave only path
            projects = Project_File_Manager.get_all_projects()
            for n, project in enumerate(lst):
                if project not in projects:
                    del lst[n]  # delete non-existent file path from the list
            return lst
        except configparser.NoSectionError:  # no section with the list of last opened paths
            return ''

    def get_recent_path(self):
        """ Get last opened path from config INI file """
        try:
            path = self.__config[self.__window][self.__opened_path]
            return path
        except KeyError:  # if the key is not in the dictionary of config
            return self.__default_opened_path 

    def set_recent_project(self, project_name):
        """ Set last opened path to config INI file """
        try:
            lst = self.__config.items(self.__recent)  # list of (key, value) pairs
        except configparser.NoSectionError:  # no section with the list of last opened paths
            lst = []  # there is no such section
        lst = [value for key, value in lst]  # leave only path
        if project_name in lst: lst.remove(project_name)  # delete path from list
        lst.insert(0, project_name)  # add path to the beginning of a list
        self.__config.remove_section(self.__recent)  # remove section
        self.__config.add_section(self.__recent)  # create empty section
        key = 1
        for name in lst:
            self.__config[self.__recent][str(key)] = name
            key += 1
            if key > self.__recent_number:
                break  # exit from the cycle

    def save(self):
        """ Save config file """
        with open(self.__config_path, 'w', encoding='utf-8') as configfile:
            self.__config.write(configfile)

    def __new_config(self):
        """ Create new config INI file and put default values in it """
        self.set_win_geometry(self.__default_geometry)
        self.set_win_state(self.__default_state)
        self.set_rect_size()
        self.set_roll_size()
        self.set_step_size()

    def destroy(self):
        """ Config destructor """
        self.save()
