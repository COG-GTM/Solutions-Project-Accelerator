from doctest import master
import threading
from tkinter import messagebox
from tkinter import filedialog

import os
import tkinter as tk                    
from tkinter import ttk

from bin.logic_acm_libraries_retrieval import acm_libraries_retrieval
from bin.logic_acm_library_parser import acm_library_parser




try:
    from bin.logic_config import Config
    from bin.logic_validators import Validators
    from bin.logic_acm_data_handler import ACM_Data_Handler
    from bin.logic_secret_store import save_openai_key, load_openai_key, has_openai_key
except Exception as error:
    from logic_config import Config
    from logic_validators import Validators
    from logic_acm_data_handler import ACM_Data_Handler
    from logic_secret_store import save_openai_key, load_openai_key, has_openai_key

  
class settings():
    def __init__(self, config:Config=None, acm_data_handler: ACM_Data_Handler = None):
        self.__config = config
        self.__acm_data_handler = acm_data_handler
        self.__form = tk.Toplevel()
        
        # Change detection variables
        self.__has_changes = False
        self.__initial_values = {}
        self.__ignore_change_events = True  # Flag to prevent change events during initialization
        
        # Thread lock for library loading operations
        self.__library_load_lock = threading.Lock()
        
        self.__setup_form()
        self.__form.wait_visibility()
        self.__form.grab_set()
        self.__form.wait_window()
        


    def __setup_form(self):
        
        self.__form.geometry('430x645')
        self.__form.resizable(False, False)
        this_dir = os.path.dirname(os.path.realpath(__file__))  # directory of this file
        self.__form.iconbitmap(os.path.join(this_dir, 'logo.ico'))  # set logo icon
        self.__form.title("Settings")
        
        # Handle window close button (X)
        self.__form.protocol("WM_DELETE_WINDOW", self.__on_closing)

        
        tabControl = ttk.Notebook(self.__form)
        tabControl.place(x=5,y=5,width=420,height=595)

        self.__setup_hmi_display_tab(tabControl)
        self.__setup_plc_code_tab(tabControl)
        self.__setup_export_graphics_tab(tabControl)
        self.__setup_scanning_accuracy(tabControl)
        self.__setup_llm_inference_tab(tabControl)

        self.__apply_button = ttk.Button(self.__form,text='Apply',command=self.__apply)
        self.__apply_button.place(x = 335, y = 610)

        self.__cancel_button = ttk.Button(self.__form,text='Cancel',command=self.__cancel)
        self.__cancel_button.place(x = 255, y = 610)

        self.__ok_button = ttk.Button(self.__form,text='OK',command=self.__ok)
        self.__ok_button.place(x = 175, y = 610)
        
        # Initialize change detection
        self.__capture_initial_values()
        self.__update_button_states()
        
        # Enable change detection now that initialization is complete
        self.__ignore_change_events = False


    
    def __int_validation(self, S:str):
        if S.isdigit():
            return True
        self.__form.bell() # .bell() plays that ding sound telling you there was invalid input
        return False
    
    def __capture_initial_values(self):
        """Capture the initial values of all form controls for change detection"""
        self.__initial_values = {
            'display_width': self.__display_width_entry.get(),
            'display_height': self.__display_height_entry.get(),
            'display_color': self.__display_color_entry.get(),
            'material_line_width': self.__material_line_width_entry.get(),
            'material_line_color': self.__material_line_color_entry.get(),
            'signal_line_width': self.__signal_line_width_entry.get(),
            'signal_line_color': self.__signal_line_color_entry.get(),
            'signal_line_dash_dot': self.__signal_line_dash_dot_v.get(),
            'hmi_library': self.__hmi_library.get(),
            'display_template': self.__display_template.get(),
            'alarm_library': self.__alarm_library.get(),
            'project_library': self.__project_library.get(),
            'controller_library': self.__controller_library.get(),
            'program': self.__program.get(),
            'task': self.__task.get(),
            'fill_color': self.__fill_color_entry.get(),
            'stroke_color': self.__stroke_color_entry.get(),
            'stroke_width': self.__stroke_width_entry.get(),
            'scanning_accuracy': self.__scanning_accuracy.get(),
            'use_scale_invariant': self.__use_scale_invariant_v.get(),
            'show_advanced_linking': self.__show_advanced_linking_v.get(),
            'llm_provider': self.__llm_provider_v.get(),
            'llm_openai_base_url': self.__llm_openai_base_url_entry.get(),
            'llm_openai_model': self.__llm_openai_model_entry.get(),
            'llm_openai_organization': self.__llm_openai_org_entry.get(),
            'llm_ollama_mode': self.__llm_ollama_mode_v.get(),
            'llm_ollama_remote_url': self.__llm_ollama_url_entry.get(),
            'llm_ollama_model': self.__llm_ollama_model_entry.get(),
            'seadd_exe_path': self.__seadd_exe_path_entry.get(),
            'seadd_application_type': self.__seadd_application_type_v.get(),
            'seadd_area_name': self.__seadd_area_name_entry.get(),
            'seadd_overwrite': self.__seadd_overwrite_v.get(),
            'logix_designer_sdk_wheel_dir': self.__logix_designer_sdk_dir_entry.get(),
            'logix_echo_sdk_wheel_dir': self.__logix_echo_sdk_dir_entry.get(),
        }
    
    def __detect_changes(self):
        """Check if any form values have changed from their initial values"""
        if self.__ignore_change_events:
            return False
            
        current_values = {
            'display_width': self.__display_width_entry.get(),
            'display_height': self.__display_height_entry.get(),
            'display_color': self.__display_color_entry.get(),
            'material_line_width': self.__material_line_width_entry.get(),
            'material_line_color': self.__material_line_color_entry.get(),
            'signal_line_width': self.__signal_line_width_entry.get(),
            'signal_line_color': self.__signal_line_color_entry.get(),
            'signal_line_dash_dot': self.__signal_line_dash_dot_v.get(),
            'hmi_library': self.__hmi_library.get(),
            'display_template': self.__display_template.get(),
            'alarm_library': self.__alarm_library.get(),
            'project_library': self.__project_library.get(),
            'controller_library': self.__controller_library.get(),
            'program': self.__program.get(),
            'task': self.__task.get(),
            'fill_color': self.__fill_color_entry.get(),
            'stroke_color': self.__stroke_color_entry.get(),
            'stroke_width': self.__stroke_width_entry.get(),
            'scanning_accuracy': self.__scanning_accuracy.get(),
            'use_scale_invariant': self.__use_scale_invariant_v.get(),
            'show_advanced_linking': self.__show_advanced_linking_v.get(),
            'llm_provider': self.__llm_provider_v.get(),
            'llm_openai_base_url': self.__llm_openai_base_url_entry.get(),
            'llm_openai_model': self.__llm_openai_model_entry.get(),
            'llm_openai_organization': self.__llm_openai_org_entry.get(),
            'llm_ollama_mode': self.__llm_ollama_mode_v.get(),
            'llm_ollama_remote_url': self.__llm_ollama_url_entry.get(),
            'llm_ollama_model': self.__llm_ollama_model_entry.get(),
            'seadd_exe_path': self.__seadd_exe_path_entry.get(),
            'seadd_application_type': self.__seadd_application_type_v.get(),
            'seadd_area_name': self.__seadd_area_name_entry.get(),
            'seadd_overwrite': self.__seadd_overwrite_v.get(),
            'logix_designer_sdk_wheel_dir': self.__logix_designer_sdk_dir_entry.get(),
            'logix_echo_sdk_wheel_dir': self.__logix_echo_sdk_dir_entry.get(),
        }
        
        return current_values != self.__initial_values
    
    def __on_change(self, *args):
        """Called when any form control value changes"""
        if self.__ignore_change_events:
            return
            
        self.__has_changes = self.__detect_changes()
        self.__update_button_states()
        self.__update_form_title()
    
    def __update_button_states(self):
        """Enable/disable Apply and OK buttons based on whether changes exist"""
        if self.__has_changes:
            self.__apply_button.config(state='normal')
            self.__ok_button.config(state='normal')
        else:
            self.__apply_button.config(state='disabled')
            self.__ok_button.config(state='normal')  # OK should always be enabled to close dialog
    
    def __update_form_title(self):
        """Update form title to indicate unsaved changes"""
        base_title = "Settings"
        if self.__has_changes:
            self.__form.title(f"{base_title} *")
        else:
            self.__form.title(base_title)
    
    def __on_closing(self):
        """Handle window close event"""
        self.__cancel()


    def __setup_hmi_display_tab(self, tabControl):
        
        try:
            width, height, color, page_link, control_modules = self.__config.get_hmi_display_settings()
            material_line_width, material_line_fore_color, material_line_style = self.__config.get_hmi_material_line_properties()
            signal_line_width, signal_line_fore_color, signal_line_has_dash_dot = self.__config.get_hmi_signal_line_properties()
        except:
            width, height, color, page_link, control_modules = (100, 100, "#E0E0E0", True, True)
            material_line_width, material_line_fore_color, material_line_style = ("2", "#AAAAAA", "solid")
            signal_line_width, signal_line_fore_color, signal_line_has_dash_dot = ("2", "#0B84FD", True)

        self.__selected_hmi_display_template = None 
        self.__selected_hmi_library = None
        self.__selected_alarm_library = None
        
        # core_type, catalog_number, major_version, minor_version
        hmi_library_option_array = self.__config.get_hmi_library()

        if hmi_library_option_array is None:
            hmi_library_option = ''
        else:
            hmi_library_option = f'{hmi_library_option_array[0]} Version {hmi_library_option_array[2]}.{hmi_library_option_array[3]}'


        alarm_library_option_array = self.__config.get_alarm_library()

        if alarm_library_option_array is None:
            alarm_library_option = ''
        else:
            alarm_library_option = f'{alarm_library_option_array[0]} Version {alarm_library_option_array[2]}.{alarm_library_option_array[3]}'


        hmi_display_tab = ttk.Frame(tabControl)
        
        tabControl.add(hmi_display_tab, text ='HMI Displays')

        # Get df of all the registered libraries
        libraries = self.__acm_data_handler.get_all_registered_libraries()

        # Create Server section frame
        server_section = ttk.LabelFrame(hmi_display_tab, text="HMI Server")
        server_section.place(x=5, y=5, width=405, height=80)
     
        # All the hmi libraries that have a LibraryType of Project
        hmi_libraries = libraries[(libraries['LibraryType'] == 'HMI') & (libraries['Category'] == 'Display')]

        # Option should consist of the CoreType column, MajorRev and MinorRev
        hmi_options = [[f'{hmi_libraries.iloc[i]["CoreType"]}  Version {hmi_libraries.iloc[i]["MajorRev"]}.{hmi_libraries.iloc[i]["MinorRev"]}',
                            hmi_libraries.iloc[i]["CoreType"],hmi_libraries.iloc[i]["CatalogNumber"],hmi_libraries.iloc[i]["MajorRev"],hmi_libraries.iloc[i]["MinorRev"]] 
                            for i in range(len(hmi_libraries))]
        

        hmi_library_label = tk.Label(server_section, text="Library used when creating a HMI Server:",justify=tk.RIGHT)
        hmi_library_label.place(x = 5 , y = 2)

        def hmi_library_option_callback(*_):
            self.__selected_hmi_library = hmi_options[self.__hmi_library_dropdown.current()]

            self.__display_template_dropdown.set(Config.DEFAULT_ACM_HMI_TEMPLATE)
            
            library_catalog_number = self.__selected_hmi_library[2]
            library_major_revision = self.__selected_hmi_library[3]
            library_minor_revision = self.__selected_hmi_library[4]
            
            
            library_file_path = acm_libraries_retrieval.quick_library_retrevial(library_catalog_number
                                                                                , library_major_revision
                                                                                , library_minor_revision)
            library_parser = acm_library_parser(library_file_path)
            display_template_options = library_parser.extract_all_display_templates()
            
       
            self.display_template_options = display_template_options
            self.__display_template_dropdown['values'] = self.display_template_options
            
            # Cleanup 
            os.remove(library_file_path)

            # Trigger change detection
            self.__on_change()

        # Create a Tkinter variable
        self.__hmi_library = tk.StringVar(hmi_display_tab)
        self.__hmi_library.set(hmi_library_option) # set the default option
        self.__hmi_library.trace_add('write', hmi_library_option_callback)

        # Create a dropdown menu
        self.__hmi_library_dropdown = ttk.Combobox(server_section, state="readonly", textvariable=self.__hmi_library, width=60
                                                       , values=[option[0] for option in hmi_options])

        self.__hmi_library_dropdown.place(x = 5 , y = 22)

        # Create Display section frame
        display_section = ttk.LabelFrame(hmi_display_tab, text="HMI Display Settings")
        display_section.place(x=5, y=90, width=405, height=250)

        self.display_template_options = []
        display_template_option = self.__config.get_hmi_display_template()

        display_template_label = tk.Label(display_section, text="Display template used when creating HMI displays:",justify=tk.RIGHT)
        display_template_label.place(x = 5 , y = 2)

        def display_template_option_callback(*_):
            if not self.display_template_options:
                return
            
            self.__selected_hmi_display_template = self.display_template_options[self.__display_template_dropdown.current()]
            self.__on_change()

        # Create a Tkinter variable
        self.__display_template = tk.StringVar(hmi_display_tab)
        self.__display_template.set(display_template_option)
        self.__display_template.trace_add('write', display_template_option_callback)

        # Create a dropdown menu
        self.__display_template_dropdown = ttk.Combobox(display_section, state="disabled", textvariable=self.__display_template, width=60
                                                          , values=[option[0] for option in self.display_template_options])

        self.__display_template_dropdown.place(x = 5 , y = 22)

        if hmi_library_option_array is None:
            self.__display_template_dropdown['values'] = []
            self.__display_template_dropdown.config(state="readonly")
        else:
            # core_type, catalog_number, major_version, minor_version
            library_catalog_number = hmi_library_option_array[1]
            library_major_revision = hmi_library_option_array[2]
            library_minor_revision = hmi_library_option_array[3]


            def load_library_templates():
                with self.__library_load_lock:
                    try:
                        library_file_path = acm_libraries_retrieval.quick_library_retrevial(library_catalog_number
                                                                                        , library_major_revision
                                                                                        , library_minor_revision)
                        library_parser = acm_library_parser(library_file_path)
                        display_template_options = library_parser.extract_all_display_templates()

                        def update_display_templates(display_template_options):
                            """Update display template dropdown on main thread"""
                            if self.__form.winfo_exists():
                                self.display_template_options = display_template_options
                                self.__display_template_dropdown['values'] = self.display_template_options
                                self.__display_template_dropdown.config(state="readonly")
                        
                        # Update UI on main thread
                        self.__form.after(0, lambda: update_display_templates(display_template_options))
                        
                        # Cleanup 
                        os.remove(library_file_path)
                    except Exception as e:
                        # Handle errors on main thread
                        pass

            # Start the operation on a background thread
            threading.Thread(target=load_library_templates, daemon=True).start()

        
        display_width_label = tk.Label(display_section, text="Display Width Pixels: ",justify=tk.RIGHT)
        display_width_label.place(x = 5 , y = 50)

        vcmd = (self.__form.register(self.__int_validation), '%S')

        self.__display_width_entry = ttk.Entry(display_section, validate='key', validatecommand=vcmd,
                                            width=10, justify=tk.LEFT)
        self.__display_width_entry.insert(tk.END, str(width))
        self.__display_width_entry.bind('<KeyRelease>', self.__on_change)
        self.__display_width_entry.bind('<FocusOut>', self.__on_change)
        self.__display_width_entry.place(x = 125 , y = 50)

        display_height_label = tk.Label(display_section, text="Display Height Pixels: ",justify=tk.RIGHT)
        display_height_label.place(x = 5 , y = 75)

        self.__display_height_entry = ttk.Entry(display_section, validate='key', validatecommand=vcmd,
                                            width=10, justify=tk.LEFT)
        self.__display_height_entry.insert(tk.END, str(height))
        self.__display_height_entry.bind('<KeyRelease>', self.__on_change)
        self.__display_height_entry.bind('<FocusOut>', self.__on_change)
        self.__display_height_entry.place(x = 125 , y = 75)
        

        display_color_label = tk.Label(display_section, text="Display Color: ",justify=tk.RIGHT)
        display_color_label.place(x = 5 , y = 100)

        def display_color_callback(*_):
            val = self.__display_color_entry.get()

            if not Validators.check_hex_rgb_color(val):
                messagebox.showerror('Invalid hex color code', 'The display background color hex code entered is invalid. '
                                                            + 'Please enter a valid hex color code.',master=self.__form)
                self.__display_color_entry.delete(0,tk.END)
                self.__display_color_entry.insert(tk.END, "#E0E0E0")

        
        self.__display_color_entry = ttk.Entry(display_section, width=10, justify=tk.LEFT)
        self.__display_color_entry.insert(tk.END, str(color))
        self.__display_color_entry.bind("<FocusOut>", display_color_callback)
        self.__display_color_entry.bind('<KeyRelease>', self.__on_change)
        self.__display_color_entry.place(x = 125 , y = 100)

        # Material Line Properties
        material_line_label = tk.Label(display_section, text="Material Line Width: ", justify=tk.RIGHT)
        material_line_label.place(x = 5, y = 125)  # Adjusted from y = 2 to y = 10
        
        self.__material_line_width_entry = ttk.Entry(display_section, validate='key', validatecommand=vcmd,
                                            width=10, justify=tk.LEFT)
        self.__material_line_width_entry.insert(tk.END, str(material_line_width))
        self.__material_line_width_entry.bind('<KeyRelease>', self.__on_change)
        self.__material_line_width_entry.bind('<FocusOut>', self.__on_change)
        self.__material_line_width_entry.place(x = 125, y = 125)  # Adjusted from y = 2 to y = 10

        material_color_label = tk.Label(display_section, text="Material Line Color: ", justify=tk.RIGHT)
        material_color_label.place(x = 5, y = 150)  # Adjusted from y = 27 to y = 40
        
        self.__material_line_color_entry = ttk.Entry(display_section, width=10, justify=tk.LEFT)
        self.__material_line_color_entry.insert(tk.END, str(material_line_fore_color))
        self.__material_line_color_entry.bind('<KeyRelease>', self.__on_change)
        self.__material_line_color_entry.bind('<FocusOut>', self.__on_change)
        self.__material_line_color_entry.place(x = 125, y = 150)  # Adjusted from y = 27 to y = 40
        
        # Signal Line Properties
        signal_line_label = tk.Label(display_section, text="Signal Line Width: ", justify=tk.RIGHT)
        signal_line_label.place(x = 5, y = 175)  # Adjusted from y = 52 to y = 70
        
        self.__signal_line_width_entry = ttk.Entry(display_section, validate='key', validatecommand=vcmd,
                                            width=10, justify=tk.LEFT)
        self.__signal_line_width_entry.insert(tk.END, str(signal_line_width))
        self.__signal_line_width_entry.bind('<KeyRelease>', self.__on_change)
        self.__signal_line_width_entry.bind('<FocusOut>', self.__on_change)
        self.__signal_line_width_entry.place(x = 125, y = 175)  # Adjusted from y = 52 to y = 70

        self.__signal_line_dash_dot_v = tk.BooleanVar()
        self.__signal_line_dash_dot = ttk.Checkbutton(display_section, text='Use dash-dot ',
                   takefocus=0, variable=self.__signal_line_dash_dot_v, command=self.__on_change)
        self.__signal_line_dash_dot_v.set(signal_line_has_dash_dot)
        self.__signal_line_dash_dot.place(x = 200, y = 175)  # Adjusted from y = 52 to y = 70

        signal_color_label = tk.Label(display_section, text="Signal Line Color: ", justify=tk.RIGHT)
        signal_color_label.place(x = 5, y = 200)  # Adjusted from y = 27 to y = 40
        
        self.__signal_line_color_entry = ttk.Entry(display_section, width=10, justify=tk.LEFT)
        self.__signal_line_color_entry.insert(tk.END, str(signal_line_fore_color))
        self.__signal_line_color_entry.bind('<KeyRelease>', self.__on_change)
        self.__signal_line_color_entry.bind('<FocusOut>', self.__on_change)
        self.__signal_line_color_entry.place(x = 125, y = 200)  # Adjusted from y = 27 to y = 40

        # Create Alarm section frame
        alarm_section = ttk.LabelFrame(hmi_display_tab, text="Alarm Server")
        alarm_section.place(x=5, y=350, width=405, height=70)  # Adjusted y from 370 to 390 and increased height from 45 to 70

        # All the alarm libraries that have a LibraryType of Project
        alarm_libraries = libraries[(libraries['LibraryType'] == 'HMI') & (libraries['Category'] == 'FTAE')]

        # Option should consist of the CoreType column, MajorRev and MinorRev
        alarm_options = [[f'{alarm_libraries.iloc[i]["CoreType"]}  Version {alarm_libraries.iloc[i]["MajorRev"]}.{alarm_libraries.iloc[i]["MinorRev"]}',
                            alarm_libraries.iloc[i]["CoreType"],alarm_libraries.iloc[i]["CatalogNumber"],alarm_libraries.iloc[i]["MajorRev"],alarm_libraries.iloc[i]["MinorRev"]] 
                            for i in range(len(alarm_libraries))]
        

        alarm_library_label = tk.Label(alarm_section, text="Library used when creating a Alarm Server:",justify=tk.RIGHT)
        alarm_library_label.place(x = 5 , y = 2)

        def alarm_library_option_callback(*_):
            self.__selected_alarm_library = alarm_options[self.__alarm_library_dropdown.current()]
            self.__on_change()


        # Create a Tkinter variable
        self.__alarm_library = tk.StringVar(hmi_display_tab)
        self.__alarm_library.set(alarm_library_option) # set the default option
        self.__alarm_library.trace_add('write', alarm_library_option_callback)

        # Create a dropdown menu
        self.__alarm_library_dropdown = ttk.Combobox(alarm_section, state="readonly", textvariable=self.__alarm_library, width=60
                                                       , values=[option[0] for option in alarm_options])

        self.__alarm_library_dropdown.place(x = 5 , y = 25)  # Adjusted y from 18 to 25

        # ── FactoryTalk View SE Add Component Tool ─────────────────────────
        # Rockwell's SEAddComponent.exe imports components into an existing
        # HMI project. Fields persist to [HMIDisplays] via
        # Config.set_seadd_component_settings. The application name is not
        # collected here — it is derived from the currently-open project
        # name at export time. SEAddComponent inherits the invoking Windows
        # session's FactoryTalk identity, so no /U or /P are collected.
        seadd_settings = self.__config.get_seadd_component_settings()

        seadd_section = ttk.LabelFrame(hmi_display_tab, text="FactoryTalk View SE Add Component Tool")
        seadd_section.place(x=5, y=425, width=405, height=145)

        # Row 1 — exe path + Browse
        seadd_exe_label = tk.Label(seadd_section, text="SEAddComponent.exe path:", justify=tk.RIGHT)
        seadd_exe_label.place(x=5, y=2)

        self.__seadd_exe_path_entry = ttk.Entry(seadd_section, width=48, justify=tk.LEFT)
        self.__seadd_exe_path_entry.insert(tk.END, str(seadd_settings['exe_path']))
        self.__seadd_exe_path_entry.bind('<KeyRelease>', self.__on_change)
        self.__seadd_exe_path_entry.bind('<FocusOut>', self.__on_change)
        self.__seadd_exe_path_entry.place(x=5, y=22)

        def _browse_seadd_exe():
            initial = self.__seadd_exe_path_entry.get().strip()
            initial_dir = os.path.dirname(initial) if initial and os.path.isdir(os.path.dirname(initial)) else ''
            path = filedialog.askopenfilename(
                parent=self.__form,
                title='Select SEAddComponent.exe',
                initialdir=initial_dir or None,
                filetypes=[('Executable', '*.exe'), ('All files', '*.*')],
            )
            if path:
                self.__seadd_exe_path_entry.delete(0, tk.END)
                self.__seadd_exe_path_entry.insert(tk.END, path)
                self.__on_change()

        self.__seadd_browse_btn = ttk.Button(seadd_section, text='Browse…', command=_browse_seadd_exe, width=8)
        self.__seadd_browse_btn.place(x=333, y=20)

        # Row 2 — Application type
        seadd_type_label = tk.Label(seadd_section, text="Application type:", justify=tk.RIGHT)
        seadd_type_label.place(x=5, y=50)

        self.__seadd_application_type_v = tk.StringVar(seadd_section)
        self.__seadd_application_type_v.set(str(seadd_settings['application_type']))
        self.__seadd_application_type_v.trace_add('write', lambda *_: self.__on_change())
        self.__seadd_application_type_dropdown = ttk.Combobox(
            seadd_section, state='readonly',
            textvariable=self.__seadd_application_type_v,
            values=['Distributed', 'Stand-alone'], width=28,
        )
        self.__seadd_application_type_dropdown.place(x=155, y=50)

        # Row 3 — Area name
        seadd_area_label = tk.Label(seadd_section, text="Area name:", justify=tk.RIGHT)
        seadd_area_label.place(x=5, y=75)

        self.__seadd_area_name_entry = ttk.Entry(seadd_section, width=30, justify=tk.LEFT)
        self.__seadd_area_name_entry.insert(tk.END, str(seadd_settings['area_name']))
        self.__seadd_area_name_entry.bind('<KeyRelease>', self.__on_change)
        self.__seadd_area_name_entry.bind('<FocusOut>', self.__on_change)
        self.__seadd_area_name_entry.place(x=155, y=75)

        # Row 4 — Overwrite checkbox
        self.__seadd_overwrite_v = tk.BooleanVar()
        self.__seadd_overwrite_v.set(bool(seadd_settings['overwrite']))
        self.__seadd_overwrite_chk = ttk.Checkbutton(
            seadd_section, text='Overwrite existing components',
            takefocus=0, variable=self.__seadd_overwrite_v,
            command=self.__on_change,
        )
        self.__seadd_overwrite_chk.place(x=5, y=100)


    def __setup_plc_code_tab(self, tabControl):


        self.__selected_project_library = None
        self.__selected_controller_library = None
        self.__selected_controller_program = None
        self.__selected_controller_task = None
        self.__selected_controller_software_revision = None

    
        project_option_array = self.__config.get_acm_project()

        if project_option_array is None:
            project_option = ''
        else:
            project_option = f'{project_option_array[0]} Version {project_option_array[2]}.{project_option_array[3]}'

        controller_option_array = self.__config.get_acm_controller()

        if controller_option_array is None:
            controller_option = ''
        else:
            controller_option = f'{controller_option_array[0]} {controller_option_array[1]} Version {controller_option_array[2]}.{controller_option_array[3]}'

        # Get df of all the registered libraries
        libraries = self.__acm_data_handler.get_all_registered_libraries()

     
        # All the project libraries that have a LibraryType of Project
        project_libraries = libraries[libraries['LibraryType'] == 'Project']

        # Option should consist of the CoreType column, MajorRev and MinorRev
        project_options = [[f'{project_libraries.iloc[i]["CoreType"]}  Version {project_libraries.iloc[i]["MajorRev"]}.{project_libraries.iloc[i]["MinorRev"]}',
                            project_libraries.iloc[i]["CoreType"],project_libraries.iloc[i]["CatalogNumber"],project_libraries.iloc[i]["MajorRev"],project_libraries.iloc[i]["MinorRev"]] 
                            for i in range(len(project_libraries))]

        # All the controller libaries that have a LibraryType of Controller
        controller_libraries = libraries[libraries['LibraryType'] == 'Controller']

        # Option should consist of the CoreType column, MajorRev and MinorRev
        controller_options = [[f'{controller_libraries.iloc[i]["CoreType"]} {controller_libraries.iloc[i]["CatalogNumber"]} Version {controller_libraries.iloc[i]["MajorRev"]}.{controller_libraries.iloc[i]["MinorRev"]}',
                            controller_libraries.iloc[i]["CoreType"],controller_libraries.iloc[i]["CatalogNumber"],controller_libraries.iloc[i]["MajorRev"],controller_libraries.iloc[i]["MinorRev"]] 
                            for i in range(len(controller_libraries))]
    
        


        plc_code_tab = ttk.Frame(tabControl)
        
        tabControl.add(plc_code_tab, text ='PLC Code')
        
        project_library_label = tk.Label(plc_code_tab, text="Library used when creating a Project:",justify=tk.RIGHT)
        project_library_label.place(x = 10 , y = 20)

        def project_library_option_callback(*_):
            self.__selected_project_library = project_options[self.__project_library_dropdown.current()]
            self.__on_change()

        # Create a Tkinter variable
        self.__project_library = tk.StringVar(plc_code_tab)
        self.__project_library.set(project_option) # set the default option
        self.__project_library.trace_add('write', project_library_option_callback)

        # Create a dropdown menu
        self.__project_library_dropdown = ttk.Combobox(plc_code_tab, state="readonly", textvariable=self.__project_library, width=60
                                                       , values=[option[0] for option in project_options])

        self.__project_library_dropdown.place(x = 10 , y = 40)


        
        controller_settings = ttk.LabelFrame(plc_code_tab, text="Controller Settings")
        controller_settings.place(x = 10 , y = 80, width= 400, height= 190)

        controller_library_label = tk.Label(controller_settings, text="Library used when creating a Controller:",justify=tk.RIGHT)
        controller_library_label.place(x = 10 , y = 2)

        def controller_library_option_callback(*_):
            self.__selected_controller_library = controller_options[self.__controller_library_dropdown.current()]

            self.__program_dropdown.set(Config.DEFAULT_ACM_CONTROLLER_PROGRAM)
            self.__task_dropdown.set(Config.DEFAULT_ACM_CONTROLLER_TASK)
            
            library_catalog_number = self.__selected_controller_library[2]
            library_major_revision = self.__selected_controller_library[3]
            library_minor_revision = self.__selected_controller_library[4]
            
            
            library_file_path = acm_libraries_retrieval.quick_library_retrevial(library_catalog_number
                                                                                , library_major_revision
                                                                                , library_minor_revision)
            library_parser = acm_library_parser(library_file_path)
            program_options = library_parser.extract_all_controller_programs()
            task_options = library_parser.extract_all_controller_tasks()
            
            self.program_options = program_options
            self.__program_dropdown['values'] = self.program_options
            self.task_options = task_options
            self.__task_dropdown['values'] = self.task_options
            
            # Cleanup 
            os.remove(library_file_path)
            
            # Trigger change detection
            self.__on_change()


        # Create a Tkinter variable
        self.__controller_library = tk.StringVar(controller_settings)
        self.__controller_library.set(controller_option)
        self.__controller_library.trace_add('write', controller_library_option_callback)

        # Create a dropdown menu
        self.__controller_library_dropdown = ttk.Combobox(controller_settings, state="readonly", textvariable=self.__controller_library, width=58
                                                          , values=[option[0] for option in controller_options])

        self.__controller_library_dropdown.place(x = 10 , y = 22)


        self.program_options = []
        program_option = self.__config.get_acm_controller_program()

        program_label = tk.Label(controller_settings, text="Program used when creating Objects:",justify=tk.RIGHT)
        program_label.place(x = 15 , y = 50)

        def program_option_callback(*_):
            if self.program_options:
                self.__selected_controller_program = self.program_options[self.__program_dropdown.current()]
            self.__on_change()

        # Create a Tkinter variable
        self.__program = tk.StringVar(controller_settings)
        self.__program.set(program_option)
        self.__program.trace_add('write', program_option_callback)

        # Create a dropdown menu
        self.__program_dropdown = ttk.Combobox(controller_settings, state="disabled", textvariable=self.__program, width=57
                                                          , values=[option[0] for option in self.program_options])

        self.__program_dropdown.place(x = 15 , y = 70)

        self.task_options = []
        task_option = self.__config.get_acm_controller_task()

        task_label = tk.Label(controller_settings, text="Task used when creating Objects:",justify=tk.RIGHT)
        task_label.place(x = 15 , y = 92)

        def task_option_callback(*_):
            if self.task_options:
                self.__selected_controller_task = self.task_options[self.__task_dropdown.current()]
            self.__on_change()

        # Create a Tkinter variable
        self.__task = tk.StringVar(controller_settings)
        self.__task.set(task_option)
        self.__task.trace_add('write', task_option_callback)

        # Create a dropdown menu
        self.__task_dropdown = ttk.Combobox(controller_settings, state="disabled", textvariable=self.__task, width=57
                                                            , values=[option[0] for option in self.task_options])
        
        self.__task_dropdown.place(x = 15 , y = 112)

        # PLC firmware / software revision entry (free text, 2 digits, >= 20)
        software_revision_option = self.__config.get_acm_controller_software_revision()

        software_revision_label = tk.Label(controller_settings,
                                           text="PLC firmware revision (20-99):",
                                           justify=tk.RIGHT)
        software_revision_label.place(x = 15 , y = 140)

        def _validate_software_revision_keystroke(proposed_value):
            # Allow empty (in-progress typing) or 1-2 digits
            if proposed_value == '':
                return True
            if len(proposed_value) > 2:
                return False
            return proposed_value.isdigit()

        vcmd = (self.__form.register(_validate_software_revision_keystroke), '%P')

        def software_revision_option_callback(*_):
            self.__selected_controller_software_revision = self.__software_revision.get()
            self.__on_change()

        self.__software_revision = tk.StringVar(controller_settings)
        self.__software_revision.set(software_revision_option)
        self.__software_revision.trace_add('write', software_revision_option_callback)

        self.__software_revision_entry = ttk.Entry(controller_settings,
                                                   textvariable=self.__software_revision,
                                                   width=5,
                                                   validate='key',
                                                   validatecommand=vcmd)
        self.__software_revision_entry.place(x = 200 , y = 140)

        if controller_option_array is None:
            self.__program_dropdown['values'] = []
            self.__program_dropdown.config(state="readonly")
            self.__task_dropdown['values'] = []
            self.__task_dropdown.config(state="readonly")
        else:
            # core_type, catalog_number, major_version, minor_version
            library_catalog_number = controller_option_array[1]
            library_major_revision = controller_option_array[2]
            library_minor_revision = controller_option_array[3]

            def load_library_templates():
                with self.__library_load_lock:
                    try:
                        library_file_path = acm_libraries_retrieval.quick_library_retrevial(library_catalog_number
                                                                                        , library_major_revision
                                                                                        , library_minor_revision)
                        library_parser = acm_library_parser(library_file_path)
                        program_options = library_parser.extract_all_controller_programs()
                        task_options = library_parser.extract_all_controller_tasks()

                        def update_controller_templates(program_options, task_options):
                            """Update display template dropdown on main thread"""
                            # if the form is up
                            if self.__form.winfo_exists():
                                self.program_options = program_options
                                self.__program_dropdown['values'] = self.program_options
                                self.__program_dropdown.config(state="readonly")

                                self.task_options = task_options
                                self.__task_dropdown['values'] = self.task_options
                                self.__task_dropdown.config(state="readonly")

                        # Update UI on main thread
                        self.__form.after(0, lambda: update_controller_templates(program_options, task_options))
                        
                        # Cleanup 
                        os.remove(library_file_path)
                    except Exception as e:
                        # Handle errors on main thread
                        pass

            # Start the operation on a background thread
            threading.Thread(target=load_library_templates, daemon=True).start()

        plc_code_link_settings = ttk.LabelFrame(plc_code_tab, text="Text Link Settings")
        plc_code_link_settings.place(x = 10 , y = 285, width= 400, height= 50)

        # Get the current setting value
        try:
            show_advanced_linking = self.__config.get_show_advanced_linking()
        except:
            show_advanced_linking = False

        # Create the checkbox variable and control
        self.__show_advanced_linking_v = tk.BooleanVar()
        self.__show_advanced_linking = ttk.Checkbutton(plc_code_link_settings, text='Show advanced linking',
                   takefocus=0, variable=self.__show_advanced_linking_v, command=self.__on_change)
        self.__show_advanced_linking_v.set(show_advanced_linking)
        self.__show_advanced_linking.place(x = 10, y = 5)

        # ── Rockwell SDK Locations ─────────────────────────────────────────
        # File paths to the Rockwell Logix Designer and FactoryTalk Logix
        # Echo Python SDK wheel files (``*.whl``) distributed by their
        # respective installers. Only consulted when composing the
        # install-hint error message shown if ``import logix_designer_sdk``
        # or ``import ftecho_sdk`` fails. Leaving a field empty reverts to
        # the installer default wheel location. A directory path is also
        # accepted for backward compatibility with older configs.
        rockwell_sdk_settings = ttk.LabelFrame(plc_code_tab, text="Rockwell SDK Locations")
        rockwell_sdk_settings.place(x=10, y=345, width=400, height=120)

        # Row 1 — Logix Designer SDK wheel file
        logix_designer_sdk_label = tk.Label(
            rockwell_sdk_settings,
            text="Logix Designer SDK wheel file:",
            justify=tk.RIGHT,
        )
        logix_designer_sdk_label.place(x=5, y=2)

        self.__logix_designer_sdk_dir_entry = ttk.Entry(rockwell_sdk_settings, width=48, justify=tk.LEFT)
        self.__logix_designer_sdk_dir_entry.insert(
            tk.END, str(self.__config.get_logix_designer_sdk_wheel_dir() or '')
        )
        self.__logix_designer_sdk_dir_entry.bind('<KeyRelease>', self.__on_change)
        self.__logix_designer_sdk_dir_entry.bind('<FocusOut>', self.__on_change)
        self.__logix_designer_sdk_dir_entry.place(x=5, y=22)

        def _browse_logix_designer_sdk_dir():
            initial = self.__logix_designer_sdk_dir_entry.get().strip()
            if initial and os.path.isfile(initial):
                initial_dir = os.path.dirname(initial)
            elif initial and os.path.isdir(initial):
                initial_dir = initial
            elif initial and os.path.isdir(os.path.dirname(initial)):
                initial_dir = os.path.dirname(initial)
            else:
                initial_dir = ''
            path = filedialog.askopenfilename(
                parent=self.__form,
                title='Select Logix Designer SDK wheel file',
                initialdir=initial_dir or None,
                filetypes=[('Python wheel', '*.whl'), ('All files', '*.*')],
            )
            if path:
                self.__logix_designer_sdk_dir_entry.delete(0, tk.END)
                self.__logix_designer_sdk_dir_entry.insert(tk.END, path)
                self.__on_change()

        self.__logix_designer_sdk_browse_btn = ttk.Button(
            rockwell_sdk_settings, text='Browse…',
            command=_browse_logix_designer_sdk_dir, width=8,
        )
        self.__logix_designer_sdk_browse_btn.place(x=333, y=20)

        # Row 2 — Logix Echo SDK wheel file
        logix_echo_sdk_label = tk.Label(
            rockwell_sdk_settings,
            text="Logix Echo SDK wheel file:",
            justify=tk.RIGHT,
        )
        logix_echo_sdk_label.place(x=5, y=48)

        self.__logix_echo_sdk_dir_entry = ttk.Entry(rockwell_sdk_settings, width=48, justify=tk.LEFT)
        self.__logix_echo_sdk_dir_entry.insert(
            tk.END, str(self.__config.get_logix_echo_sdk_wheel_dir() or '')
        )
        self.__logix_echo_sdk_dir_entry.bind('<KeyRelease>', self.__on_change)
        self.__logix_echo_sdk_dir_entry.bind('<FocusOut>', self.__on_change)
        self.__logix_echo_sdk_dir_entry.place(x=5, y=68)

        def _browse_logix_echo_sdk_dir():
            initial = self.__logix_echo_sdk_dir_entry.get().strip()
            if initial and os.path.isfile(initial):
                initial_dir = os.path.dirname(initial)
            elif initial and os.path.isdir(initial):
                initial_dir = initial
            elif initial and os.path.isdir(os.path.dirname(initial)):
                initial_dir = os.path.dirname(initial)
            else:
                initial_dir = ''
            path = filedialog.askopenfilename(
                parent=self.__form,
                title='Select Logix Echo SDK wheel file',
                initialdir=initial_dir or None,
                filetypes=[('Python wheel', '*.whl'), ('All files', '*.*')],
            )
            if path:
                self.__logix_echo_sdk_dir_entry.delete(0, tk.END)
                self.__logix_echo_sdk_dir_entry.insert(tk.END, path)
                self.__on_change()

        self.__logix_echo_sdk_browse_btn = ttk.Button(
            rockwell_sdk_settings, text='Browse…',
            command=_browse_logix_echo_sdk_dir, width=8,
        )
        self.__logix_echo_sdk_browse_btn.place(x=333, y=66)




    def __setup_export_graphics_tab(self, tabControl):

        try:
            self.__fill_color, self.__stroke_color, width = self.__config.get_extracted_hmi_graphic_settings()
        except:
            self.__fill_color, self.__stroke_color, width = ('000000','000000', '2')

        

        hmi_display_tab = ttk.Frame(tabControl)
        
        tabControl.add(hmi_display_tab, text ='Static Graphics')

        fill_color_label = tk.Label(hmi_display_tab, text="Default Extract Fill Color: ",justify=tk.RIGHT)
        fill_color_label.place(x = 10 , y = 20)

        
        self.__fill_color_entry = ttk.Entry(hmi_display_tab, validate='key',
                                            width=10, justify=tk.LEFT)
        self.__fill_color_entry.bind("<FocusOut>", self.__fill_color_callback)
        self.__fill_color_entry.bind('<KeyRelease>', self.__on_change)
        self.__fill_color_entry.insert(tk.END, str(self.__fill_color))
        self.__fill_color_entry.place(x = 168 , y = 20)


        stroke_color_label = tk.Label(hmi_display_tab, text="Default Extract Stroke Color: ",justify=tk.RIGHT)
        stroke_color_label.place(x = 10 , y = 45)

        
        self.__stroke_color_entry = ttk.Entry(hmi_display_tab, validate='key',
                                            width=10, justify=tk.LEFT)
        self.__stroke_color_entry.bind("<FocusOut>", self.__stroke_color_callback)
        self.__stroke_color_entry.bind('<KeyRelease>', self.__on_change)
        self.__stroke_color_entry.insert(tk.END, str(self.__stroke_color))
        self.__stroke_color_entry.place(x = 168 , y = 45)

        stroke_width_label = tk.Label(hmi_display_tab, text="Default Extract Stroke Width: ",justify=tk.RIGHT)
        stroke_width_label.place(x = 10 , y = 70)

        vcmd = (self.__form.register(self.__int_validation), '%S')

        self.__stroke_width_entry = ttk.Entry(hmi_display_tab, validate='key', validatecommand=vcmd,
                                            width=10, justify=tk.LEFT)
        self.__stroke_width_entry.insert(tk.END, str(width))
        self.__stroke_width_entry.bind('<KeyRelease>', self.__on_change)
        self.__stroke_width_entry.bind('<FocusOut>', self.__on_change)
        self.__stroke_width_entry.place(x = 168 , y = 70)


    def __setup_scanning_accuracy(self, tabControl):
        
        
        selection = self.__config.get_scanning_match_score()
        use_scale_invariant = self.__config.get_scanning_use_scale_invariant()
        scanning_accuracy_tab = ttk.Frame(tabControl)

        self.__selected_match_score = None
        
        tabControl.add(scanning_accuracy_tab, text ='Scanning Options')

        scanning_accuracy_options = {'0.7':'High Accuracy'
                                     ,'0.6':'Medium Accuracy'
                                     ,'0.5':'Low Accuracy'}


        def scanning_accuracy_option_callback(*_):
            selection = self.__scanning_accuracy_dropdown.get()
            for key, value in scanning_accuracy_options.items():
                if value == selection:
                    self.__selected_match_score = key
            self.__on_change()

        scanning_accuracy_label = tk.Label(scanning_accuracy_tab, text="Scanning Accuracy:",justify=tk.RIGHT)
        scanning_accuracy_label.place(x = 10 , y = 20)


        # Create a Tkinter variable
        self.__scanning_accuracy = tk.StringVar(scanning_accuracy_tab)
        self.__scanning_accuracy.set(scanning_accuracy_options[str(selection)]) 
        self.__scanning_accuracy.trace_add('write', scanning_accuracy_option_callback)

        # Create a dropdown menu
        self.__scanning_accuracy_dropdown = ttk.Combobox(scanning_accuracy_tab, state="readonly", textvariable=self.__scanning_accuracy, width=58
                                                          , values=list(scanning_accuracy_options.values()))

        self.__scanning_accuracy_dropdown.place(x = 10 , y = 40)

        # Use Scale Invariant Template Matching checkbox
        self.__use_scale_invariant_v = tk.BooleanVar()
        self.__use_scale_invariant = ttk.Checkbutton(scanning_accuracy_tab, text='Use multi-scale scanning',
                   takefocus=0, variable=self.__use_scale_invariant_v, command=self.__on_change)
        self.__use_scale_invariant_v.set(use_scale_invariant)
        self.__use_scale_invariant.place(x = 10, y = 70)

        

    

    def __setup_llm_inference_tab(self, tabControl):
        """
        Build the LLM Inference settings tab.

        Provider dropdown values map to the ``Provider`` field written by
        ``Config.set_llm_inference_settings``:

            display label        → stored value
            ─────────────────────────────────────
            "Auto (detect)"      → ""      (enterprise gateway plugin, else Ollama)
            "OpenAI (public)"    → "openai"
            "Ollama"             → "ollama"

        The OpenAI API key never touches Config; it goes through the DPAPI
        store (``bin/logic_secret_store.py``). The Save Key button is the
        only surface that writes the plaintext; the entry field is cleared
        right after the encrypted blob lands on disk.
        """
        try:
            settings = self.__config.get_llm_inference_settings()
        except Exception:
            settings = {
                'provider': '',
                'openai_base_url': '',
                'openai_model': 'gpt-4.1-mini',
                'openai_organization': '',
                'ollama_mode': 'bundled',
                'ollama_remote_url': '',
                'ollama_model': 'reasoning:4b',
            }

        # Display label mapping ↔ stored provider value.
        provider_options = {
            '': 'Auto (detect)',
            'openai': 'OpenAI (public)',
            'ollama': 'Ollama',
        }
        stored_provider = (settings.get('provider') or '').lower()
        if stored_provider not in provider_options:
            stored_provider = ''
        self.__llm_provider_map = provider_options

        llm_tab = ttk.Frame(tabControl)
        tabControl.add(llm_tab, text='LLM Models')

        # ── Provider selector ────────────────────────────────────────────
        provider_label = tk.Label(llm_tab, text='Provider:', justify=tk.LEFT)
        provider_label.place(x=10, y=8)

        self.__llm_provider_v = tk.StringVar(llm_tab)
        self.__llm_provider_v.set(provider_options[stored_provider])
        self.__llm_provider_v.trace_add('write', lambda *_: self._on_llm_provider_changed())

        self.__llm_provider_dropdown = ttk.Combobox(
            llm_tab, state='readonly', textvariable=self.__llm_provider_v,
            width=60, values=list(provider_options.values()),
        )
        self.__llm_provider_dropdown.place(x=10, y=28)

        # ── OpenAI (public) section ──────────────────────────────────────
        self.__llm_openai_section = ttk.LabelFrame(llm_tab, text='OpenAI (public)')
        self.__llm_openai_section.place(x=5, y=60, width=405, height=165)

        api_key_label = tk.Label(self.__llm_openai_section, text='API key:', justify=tk.LEFT)
        api_key_label.place(x=8, y=2)

        self.__llm_openai_key_entry = ttk.Entry(self.__llm_openai_section, width=38, show='*')
        self.__llm_openai_key_entry.place(x=8, y=22)

        # Visual "key present" indicator: instead of a separate status label,
        # we pre-fill the (masked) entry with a placeholder when a key is
        # already stored in DPAPI. The placeholder is cleared the moment the
        # user focuses/edits, and Save-key ignores writes while the field
        # still holds the placeholder.
        self.__llm_openai_key_placeholder = '\u2022' * 12
        self.__llm_openai_key_is_placeholder = False
        if has_openai_key():
            self.__llm_openai_key_entry.insert(0, self.__llm_openai_key_placeholder)
            self.__llm_openai_key_is_placeholder = True
        self.__llm_openai_key_entry.bind('<FocusIn>', self.__on_llm_openai_key_focus_in)
        self.__llm_openai_key_entry.bind('<Key>', self.__on_llm_openai_key_key_press)

        self.__llm_openai_key_show_v = tk.BooleanVar(value=False)
        self.__llm_openai_key_show_btn = ttk.Checkbutton(
            self.__llm_openai_section, text='Show', takefocus=0,
            variable=self.__llm_openai_key_show_v,
            command=self._toggle_llm_openai_key_visibility,
        )
        self.__llm_openai_key_show_btn.place(x=278, y=20)

        self.__llm_openai_key_save_btn = ttk.Button(
            self.__llm_openai_section, text='Save key',
            command=self._save_llm_openai_key,
        )
        self.__llm_openai_key_save_btn.place(x=335, y=19, width=65)

        base_url_label = tk.Label(self.__llm_openai_section, text='Base URL (optional, defaults to api.openai.com):',
                                  justify=tk.LEFT)
        base_url_label.place(x=8, y=48)
        self.__llm_openai_base_url_entry = ttk.Entry(self.__llm_openai_section, width=56)
        self.__llm_openai_base_url_entry.insert(tk.END, settings.get('openai_base_url', '') or '')
        self.__llm_openai_base_url_entry.bind('<KeyRelease>', self.__on_change)
        self.__llm_openai_base_url_entry.place(x=8, y=68)

        # Model row: label + narrower selector + refresh, aligned inline
        # with the Organization label + entry on the same y.
        model_label = tk.Label(self.__llm_openai_section, text='Model:', justify=tk.LEFT)
        model_label.place(x=8, y=95)
        # Editable Combobox so users can still type custom / experimental
        # model IDs. Values are seeded with the curated fallback list from
        # PublicOpenAIInference and refreshed from the OpenAI /v1/models
        # endpoint once the user authenticates (see _refresh_openai_models).
        initial_model = settings.get('openai_model', '') or 'gpt-4.1-mini'
        self.__llm_openai_model_entry = ttk.Combobox(
            self.__llm_openai_section, width=16, state='normal',
            values=self._initial_openai_model_values(initial_model),
        )
        self.__llm_openai_model_entry.set(initial_model)
        self.__llm_openai_model_entry.bind('<KeyRelease>', self.__on_change)
        self.__llm_openai_model_entry.bind('<<ComboboxSelected>>', self.__on_change)
        self.__llm_openai_model_entry.place(x=48, y=95)

        self.__llm_openai_model_refresh_btn = ttk.Button(
            self.__llm_openai_section, text='\u21bb',
            command=lambda: self._refresh_openai_models(silent=False),
        )
        self.__llm_openai_model_refresh_btn.place(x=165, y=94, width=25)

        org_label = tk.Label(self.__llm_openai_section, text='Organization:', justify=tk.LEFT)
        org_label.place(x=195, y=95)
        self.__llm_openai_org_entry = ttk.Entry(self.__llm_openai_section, width=18)
        self.__llm_openai_org_entry.insert(tk.END, settings.get('openai_organization', '') or '')
        self.__llm_openai_org_entry.bind('<KeyRelease>', self.__on_change)
        self.__llm_openai_org_entry.place(x=275, y=95)

        self.__llm_openai_test_btn = ttk.Button(
            self.__llm_openai_section, text='Test',
            command=lambda: self._test_llm_connection('openai'),
        )
        self.__llm_openai_test_btn.place(x=8, y=122, width=60)

        # ── Ollama section ───────────────────────────────────────────────
        self.__llm_ollama_section = ttk.LabelFrame(llm_tab, text='Ollama')
        self.__llm_ollama_section.place(x=5, y=230, width=405, height=190)

        self.__llm_ollama_mode_v = tk.StringVar(
            self.__llm_ollama_section,
            value=(settings.get('ollama_mode') or 'bundled').lower(),
        )
        self.__llm_ollama_mode_v.trace_add('write', lambda *_: self._on_llm_ollama_mode_changed())

        bundled_radio = ttk.Radiobutton(
            self.__llm_ollama_section, text='Bundled (start local server)',
            takefocus=0, variable=self.__llm_ollama_mode_v, value='bundled',
        )
        bundled_radio.place(x=8, y=5)

        remote_radio = ttk.Radiobutton(
            self.__llm_ollama_section, text='Remote (connect to existing server)',
            takefocus=0, variable=self.__llm_ollama_mode_v, value='remote',
        )
        remote_radio.place(x=8, y=27)

        url_label = tk.Label(self.__llm_ollama_section, text='Server URL (e.g. http://localhost:11434):',
                             justify=tk.LEFT)
        url_label.place(x=8, y=52)
        self.__llm_ollama_url_entry = ttk.Entry(self.__llm_ollama_section, width=56)
        self.__llm_ollama_url_entry.insert(tk.END, settings.get('ollama_remote_url', '') or '')
        self.__llm_ollama_url_entry.bind('<KeyRelease>', self.__on_change)
        self.__llm_ollama_url_entry.place(x=8, y=72)

        ollama_model_label = tk.Label(self.__llm_ollama_section, text='Model:', justify=tk.LEFT)
        ollama_model_label.place(x=8, y=97)
        self.__llm_ollama_model_entry = ttk.Entry(self.__llm_ollama_section, width=16)
        self.__llm_ollama_model_entry.insert(tk.END, settings.get('ollama_model', '') or 'reasoning:4b')
        self.__llm_ollama_model_entry.bind('<KeyRelease>', self.__on_change)
        self.__llm_ollama_model_entry.place(x=48, y=97)

        self.__llm_ollama_download_btn = ttk.Button(
            self.__llm_ollama_section, text='Download',
            command=self._download_ollama_model,
        )
        self.__llm_ollama_download_btn.place(x=170, y=95, width=80)

        self.__llm_ollama_test_btn = ttk.Button(
            self.__llm_ollama_section, text='Test',
            command=lambda: self._test_llm_connection('ollama'),
        )
        self.__llm_ollama_test_btn.place(x=260, y=95, width=60)

        # Download progress row (initially blank; populated by
        # ``_download_ollama_model`` while a pull is in flight).
        self.__llm_ollama_progress_v = tk.DoubleVar(self.__llm_ollama_section, value=0.0)
        self.__llm_ollama_progress = ttk.Progressbar(
            self.__llm_ollama_section, orient='horizontal', mode='determinate',
            variable=self.__llm_ollama_progress_v, maximum=100,
        )
        self.__llm_ollama_progress.place(x=8, y=125, width=389, height=14)
        self.__llm_ollama_progress_status_v = tk.StringVar(
            self.__llm_ollama_section, value='',
        )
        self.__llm_ollama_progress_status = tk.Label(
            self.__llm_ollama_section, textvariable=self.__llm_ollama_progress_status_v,
            justify=tk.LEFT, fg='#555555', anchor='w',
        )
        self.__llm_ollama_progress_status.place(x=8, y=143, width=389)

        # Apply initial enable/disable state based on provider + Ollama mode.
        self._on_llm_provider_changed()
        self._on_llm_ollama_mode_changed()

    def _selected_llm_provider_value(self):
        """Return the canonical stored value ('', 'openai', or 'ollama') for
        the current dropdown selection."""
        label = self.__llm_provider_v.get()
        for value, disp in self.__llm_provider_map.items():
            if disp == label:
                return value
        return ''

    def _on_llm_provider_changed(self, *_):
        """Enable only the section matching the selected provider."""
        provider = self._selected_llm_provider_value()
        openai_state = 'normal' if provider == 'openai' else 'disabled'
        ollama_state = 'normal' if provider == 'ollama' else 'disabled'

        openai_widgets = [
            self.__llm_openai_key_entry,
            self.__llm_openai_key_show_btn,
            self.__llm_openai_key_save_btn,
            self.__llm_openai_base_url_entry,
            self.__llm_openai_model_entry,
            self.__llm_openai_model_refresh_btn,
            self.__llm_openai_org_entry,
            self.__llm_openai_test_btn,
        ]
        for w in openai_widgets:
            try:
                w.configure(state=openai_state)
            except tk.TclError:
                # Combobox uses "readonly" not "normal"; not applicable here
                # but guard anyway.
                pass

        ollama_widgets = [
            self.__llm_ollama_model_entry,
            self.__llm_ollama_download_btn,
            self.__llm_ollama_test_btn,
        ]
        for w in ollama_widgets:
            try:
                w.configure(state=ollama_state)
            except tk.TclError:
                pass

        # URL entry only usable in Ollama-remote mode.
        self._on_llm_ollama_mode_changed()
        self.__on_change()

    def _on_llm_ollama_mode_changed(self, *_):
        """Toggle the Ollama URL entry based on Bundled vs. Remote."""
        provider = self._selected_llm_provider_value()
        mode = self.__llm_ollama_mode_v.get()
        if provider == 'ollama' and mode == 'remote':
            self.__llm_ollama_url_entry.configure(state='normal')
        else:
            self.__llm_ollama_url_entry.configure(state='disabled')
        self.__on_change()

    def __on_llm_openai_key_focus_in(self, _event=None):
        """Clear the masked placeholder when the user focuses the entry."""
        if self.__llm_openai_key_is_placeholder:
            self.__llm_openai_key_entry.delete(0, tk.END)
            self.__llm_openai_key_is_placeholder = False

    def __on_llm_openai_key_key_press(self, _event=None):
        """Same as focus-in, but for the case where the entry already had
        focus (e.g. user tabbed in and immediately started typing)."""
        if self.__llm_openai_key_is_placeholder:
            self.__llm_openai_key_entry.delete(0, tk.END)
            self.__llm_openai_key_is_placeholder = False

    def _refresh_llm_openai_key_placeholder(self):
        """After a successful save, re-show the masked placeholder so the
        entry visually indicates a key is on file."""
        self.__llm_openai_key_entry.delete(0, tk.END)
        if has_openai_key():
            self.__llm_openai_key_entry.insert(0, self.__llm_openai_key_placeholder)
            self.__llm_openai_key_is_placeholder = True
        else:
            self.__llm_openai_key_is_placeholder = False

    # ── OpenAI model list helpers ────────────────────────────────────────
    # Substrings that mark an ID as NOT a chat-completions model. Applied
    # after the ``gpt-`` / ``o`` prefix filter so we don't advertise
    # embeddings, audio, image, or moderation endpoints in the chat dropdown.
    _OPENAI_NON_CHAT_SUBSTRINGS = (
        'embedding', 'whisper', 'tts', 'dall', 'moderation',
        'audio', 'image', 'realtime', 'transcribe',
    )

    def _curated_openai_fallback_models(self):
        """Return the curated fallback list from PublicOpenAIInference.

        Kept behind a helper so the import stays lazy (openai is a heavy
        module and this settings dialog is opened before the LLM pipeline
        would otherwise trigger it)."""
        try:
            try:
                from bin.logic_llm_inference import PublicOpenAIInference
            except ImportError:
                from logic_llm_inference import PublicOpenAIInference  # type: ignore[no-redef]
            # PublicOpenAIInference.__init__ enforces a non-empty api_key,
            # but list_models is really a static curated list — grab it
            # from the class-level attribute if present, else instantiate
            # with a dummy key.
            try:
                return list(PublicOpenAIInference(api_key='dummy').list_models())
            except Exception:
                return []
        except Exception:
            return []

    def _initial_openai_model_values(self, current_model):
        """Combobox values shown before any API refresh.

        Union of the curated fallback list and ``current_model`` (so the
        user's saved choice always appears), preserving curated-first order.
        """
        values = self._curated_openai_fallback_models()
        if current_model and current_model not in values:
            values = [current_model] + values
        return values

    @classmethod
    def _filter_openai_chat_models(cls, model_ids):
        """Keep only IDs that look like chat-completions models.

        Rule: prefix must be ``gpt-`` or start with a single ``o`` followed
        by a digit (o1, o3-mini, o4-mini, …). Then reject anything whose ID
        contains one of ``_OPENAI_NON_CHAT_SUBSTRINGS``.
        """
        chat = []
        for mid in model_ids:
            if not isinstance(mid, str) or not mid:
                continue
            lower = mid.lower()
            is_gpt = lower.startswith('gpt-')
            is_o_series = (
                len(lower) >= 2 and lower[0] == 'o' and lower[1].isdigit()
            )
            if not (is_gpt or is_o_series):
                continue
            if any(sub in lower for sub in cls._OPENAI_NON_CHAT_SUBSTRINGS):
                continue
            chat.append(mid)
        return sorted(set(chat))

    def _refresh_openai_models(self, *, silent=False):
        """Fetch chat models from the OpenAI API and populate the dropdown.

        Runs the network call on a background thread. On success the
        Combobox's ``values`` are replaced with the filtered, sorted list;
        the currently-selected model is preserved even if the API omits it.
        On failure the dropdown falls back to the curated list.

        :param silent: When True, suppress info/error dialogs (used by the
            Save-key and Test-connection paths so they don't stack modals
            on top of their own).
        """
        api_key = load_openai_key()
        if not api_key:
            if not silent:
                messagebox.showinfo(
                    'No key stored',
                    'Save an OpenAI API key first — the model list is fetched\n'
                    'from the API using that key.',
                    master=self.__form,
                )
            return

        base_url = self.__llm_openai_base_url_entry.get().strip() or None
        organization = self.__llm_openai_org_entry.get().strip() or None
        current_model = self.__llm_openai_model_entry.get().strip()

        try:
            self.__llm_openai_model_refresh_btn.configure(state='disabled')
        except tk.TclError:
            pass

        def _apply_values(values, error=None):
            # Preserve the user's current selection even if the API list
            # doesn't include it (custom / private model IDs).
            if current_model and current_model not in values:
                values = [current_model] + list(values)
            try:
                self.__llm_openai_model_entry.configure(values=list(values))
                # configure(values=...) does not touch the currently displayed
                # text, but be defensive: re-set if it was cleared somehow.
                if current_model and self.__llm_openai_model_entry.get() != current_model:
                    self.__llm_openai_model_entry.set(current_model)
            except tk.TclError:
                pass
            try:
                # Re-enable only if the OpenAI section is still active.
                if self._selected_llm_provider_value() == 'openai':
                    self.__llm_openai_model_refresh_btn.configure(state='normal')
            except tk.TclError:
                pass
            if silent:
                return
            if error is None:
                messagebox.showinfo(
                    'Model list refreshed',
                    f'Loaded {len(values)} chat model(s) from the OpenAI API.',
                    master=self.__form,
                )
            else:
                messagebox.showerror(
                    'Model list refresh failed',
                    f'Could not fetch models from the OpenAI API:\n{error}\n\n'
                    'Falling back to the built-in curated list.',
                    master=self.__form,
                )

        def _run():
            try:
                try:
                    import openai as _openai
                except ImportError as exc:
                    raise RuntimeError('openai package is not installed') from exc
                client_kwargs = {'api_key': api_key}
                if base_url:
                    client_kwargs['base_url'] = base_url
                if organization:
                    client_kwargs['organization'] = organization
                client = _openai.OpenAI(**client_kwargs)
                raw = client.models.list()
                # openai>=1.x returns a paginated object; iterate for all.
                ids = [getattr(m, 'id', None) for m in raw]
                filtered = self._filter_openai_chat_models(ids)
                if not filtered:
                    # API returned nothing useful — fall back rather than
                    # emptying the dropdown.
                    filtered = self._curated_openai_fallback_models()
                self.__form.after(0, lambda v=filtered: _apply_values(v))
            except Exception as exc:
                fallback = self._curated_openai_fallback_models()
                err_text = str(exc)
                self.__form.after(0, lambda v=fallback, e=err_text: _apply_values(v, error=e))

        threading.Thread(target=_run, daemon=True).start()

    def _toggle_llm_openai_key_visibility(self):
        self.__llm_openai_key_entry.configure(
            show='' if self.__llm_openai_key_show_v.get() else '*'
        )

    def _save_llm_openai_key(self):
        """Encrypt-and-write the entered key, then clear the entry field.

        Failures degrade to a modal error without ever logging the key.
        """
        key = self.__llm_openai_key_entry.get()
        # If the field still holds our masked "key is stored" placeholder
        # we treat that as no-op instead of saving the dot characters.
        if self.__llm_openai_key_is_placeholder or key == self.__llm_openai_key_placeholder:
            messagebox.showinfo(
                'No changes',
                'A key is already stored. Type a new key to replace it.',
                master=self.__form,
            )
            return
        if not key:
            messagebox.showerror(
                'Missing key',
                'Enter an OpenAI API key first.',
                master=self.__form,
            )
            return
        try:
            save_openai_key(key)
        except Exception as exc:
            messagebox.showerror(
                'Save failed',
                f'Could not store the API key securely:\n{exc}',
                master=self.__form,
            )
            return
        # Clear plaintext from the UI immediately and re-show the masked
        # placeholder so the entry visually indicates a key is on file.
        self.__llm_openai_key_show_v.set(False)
        self.__llm_openai_key_entry.configure(show='*')
        self._refresh_llm_openai_key_placeholder()
        # Fire-and-forget: pull the model list now that a key is available.
        # silent=True keeps the "Key stored" dialog as the only feedback.
        self._refresh_openai_models(silent=True)
        messagebox.showinfo('Key stored', 'The API key has been encrypted and saved.',
                            master=self.__form)

    def _test_llm_connection(self, provider):
        """Probe the selected provider in a background thread.

        Kept intentionally small: we import the inference classes lazily
        (they pull in openai/ollama) and use only the minimum call needed to
        validate credentials + URL.
        """
        if provider == 'openai':
            api_key = load_openai_key()
            if not api_key:
                messagebox.showerror(
                    'No key stored',
                    'Save an OpenAI API key first, then retry.',
                    master=self.__form,
                )
                return
            base_url = self.__llm_openai_base_url_entry.get().strip() or None
            model = self.__llm_openai_model_entry.get().strip() or 'gpt-4.1-mini'
            organization = self.__llm_openai_org_entry.get().strip() or None
            self.__llm_openai_test_btn.configure(state='disabled')

            def _run():
                try:
                    try:
                        from bin.logic_llm_inference import PublicOpenAIInference
                    except ImportError:
                        from logic_llm_inference import PublicOpenAIInference  # type: ignore[no-redef]
                    client = PublicOpenAIInference(
                        api_key=api_key, base_url=base_url,
                        organization=organization, model_name=model,
                    )
                    _ = client.chat([{'role': 'user', 'content': 'ping'}],
                                     max_tokens=1)
                    self.__form.after(0, lambda: messagebox.showinfo(
                        'Test connection', 'OpenAI: reachable.', master=self.__form))
                    # Successful auth → refresh the model dropdown quietly.
                    self.__form.after(0, lambda: self._refresh_openai_models(silent=True))
                except Exception as exc:
                    err = str(exc)
                    self.__form.after(0, lambda: messagebox.showerror(
                        'Test connection failed', f'OpenAI: {err}',
                        master=self.__form))
                finally:
                    self.__form.after(0, lambda: self.__llm_openai_test_btn.configure(state='normal'))

            threading.Thread(target=_run, daemon=True).start()
            return

        if provider == 'ollama':
            mode = self.__llm_ollama_mode_v.get()
            remote_url = self.__llm_ollama_url_entry.get().strip()
            if mode == 'remote' and not remote_url:
                messagebox.showerror(
                    'Missing URL',
                    'Enter the Ollama server URL first.',
                    master=self.__form,
                )
                return
            self.__llm_ollama_test_btn.configure(state='disabled')

            def _run():
                # For a quick liveness check we hit /api/tags directly; this
                # avoids spinning up the bundled server just for a probe.
                import requests as _requests
                try:
                    if mode == 'remote':
                        url = remote_url.rstrip('/') + '/api/tags'
                    else:
                        # Bundled server lives on the module-global URL once
                        # OllamaInference has run. If it hasn't been started
                        # yet, tell the user rather than launching it here.
                        try:
                            from bin.logic_llm_inference import ollama_llm_base_url as _base
                        except ImportError:
                            from logic_llm_inference import ollama_llm_base_url as _base  # type: ignore[no-redef]
                        if not _base:
                            raise RuntimeError(
                                'Bundled Ollama server is not running yet. '
                                'Launch the app once with provider = Ollama, '
                                'or use Remote mode.'
                            )
                        url = _base.rstrip('/') + '/api/tags'
                    r = _requests.get(url, timeout=5)
                    r.raise_for_status()
                    self.__form.after(0, lambda: messagebox.showinfo(
                        'Test connection', f'Ollama: reachable at {url}.',
                        master=self.__form))
                except Exception as exc:
                    err = str(exc)
                    self.__form.after(0, lambda: messagebox.showerror(
                        'Test connection failed', f'Ollama: {err}',
                        master=self.__form))
                finally:
                    self.__form.after(0, lambda: self.__llm_ollama_test_btn.configure(state='normal'))

            threading.Thread(target=_run, daemon=True).start()

    # ── Ollama model download (pull) ─────────────────────────────────────
    def _resolve_ollama_base_url(self):
        """Return the Ollama HTTP base URL for the currently-selected mode,
        or raise RuntimeError with a user-facing message when unresolved."""
        mode = self.__llm_ollama_mode_v.get()
        if mode == 'remote':
            url = self.__llm_ollama_url_entry.get().strip()
            if not url:
                raise RuntimeError('Enter the Ollama server URL first.')
            return url.rstrip('/')
        try:
            from bin.logic_llm_inference import ollama_llm_base_url as _base
        except ImportError:
            from logic_llm_inference import ollama_llm_base_url as _base  # type: ignore[no-redef]
        if not _base:
            raise RuntimeError(
                'Bundled Ollama server is not running yet. Launch the app '
                'once with provider = Ollama, or switch to Remote mode.'
            )
        return _base.rstrip('/')

    def _download_ollama_model(self):
        """Pull the model named in the Ollama Model entry from the server.

        Uses the Ollama HTTP API ``POST /api/pull`` with ``stream=True`` and
        parses the JSONL progress events. The determinate progress bar and
        status label above the buttons are updated on the Tk thread via
        ``self.__form.after``. If the model already exists locally the pull
        endpoint still succeeds quickly and simply reports "success".
        """
        model = self.__llm_ollama_model_entry.get().strip()
        if not model:
            messagebox.showerror(
                'Missing model',
                'Enter an Ollama model name first (e.g. reasoning:4b).',
                master=self.__form,
            )
            return

        try:
            base_url = self._resolve_ollama_base_url()
        except RuntimeError as exc:
            messagebox.showerror('Download failed', str(exc), master=self.__form)
            return

        # Freeze the controls that would race with an in-flight pull.
        try:
            self.__llm_ollama_download_btn.configure(state='disabled')
            self.__llm_ollama_test_btn.configure(state='disabled')
            self.__llm_ollama_model_entry.configure(state='disabled')
        except tk.TclError:
            pass
        self.__llm_ollama_progress_v.set(0)
        self.__llm_ollama_progress_status_v.set(f'Preparing to download {model}\u2026')

        def _apply_progress(percent, status_text):
            try:
                self.__llm_ollama_progress_v.set(percent)
                self.__llm_ollama_progress_status_v.set(status_text)
            except tk.TclError:
                pass

        def _finish(success, message):
            try:
                self.__llm_ollama_download_btn.configure(state='normal')
                self.__llm_ollama_test_btn.configure(state='normal')
                self.__llm_ollama_model_entry.configure(state='normal')
            except tk.TclError:
                pass
            if success:
                self.__llm_ollama_progress_v.set(100)
                self.__llm_ollama_progress_status_v.set(message)
                messagebox.showinfo('Download complete', message, master=self.__form)
            else:
                self.__llm_ollama_progress_v.set(0)
                self.__llm_ollama_progress_status_v.set('')
                messagebox.showerror('Download failed', message, master=self.__form)

        def _run():
            import json as _json
            import requests as _requests
            url = base_url + '/api/pull'
            try:
                resp = _requests.post(
                    url, json={'model': model, 'stream': True},
                    stream=True, timeout=(10, None),
                )
                resp.raise_for_status()
                current_status = ''
                for raw in resp.iter_lines(decode_unicode=True):
                    if not raw:
                        continue
                    try:
                        evt = _json.loads(raw)
                    except ValueError:
                        continue
                    if 'error' in evt:
                        raise RuntimeError(str(evt['error']))
                    status = evt.get('status', current_status) or current_status
                    current_status = status
                    total = evt.get('total') or 0
                    completed = evt.get('completed') or 0
                    if total > 0 and completed >= 0:
                        percent = max(0.0, min(100.0, (completed / total) * 100.0))
                        # Human-readable byte counts.
                        def _fmt(n):
                            for unit in ('B', 'KB', 'MB', 'GB'):
                                if n < 1024 or unit == 'GB':
                                    return f'{n:.1f} {unit}'
                                n /= 1024.0
                            return f'{n:.1f} GB'
                        text = f'{status}  {_fmt(completed)} / {_fmt(total)}  ({percent:.1f}%)'
                    else:
                        percent = 0.0
                        text = status
                    self.__form.after(0, lambda p=percent, t=text: _apply_progress(p, t))
                self.__form.after(
                    0, lambda: _finish(True, f'Model "{model}" is ready.')
                )
            except Exception as exc:
                err = str(exc)
                self.__form.after(0, lambda: _finish(False, f'Ollama pull failed:\n{err}'))

        threading.Thread(target=_run, daemon=True).start()

    def __fill_color_callback(self,_):
        val = self.__fill_color_entry.get()


        if not Validators.check_hex_rgb_color(val):
            messagebox.showerror('Invalid hex color code', 'The fill color hex code entered is invalid. '
                                                            + 'Please enter a valid hex color code.',master=self.__form)
            self.__fill_color_entry.delete(0,tk.END)
            self.__fill_color_entry.insert(tk.END, str(self.__fill_color))

            

    def __stroke_color_callback(self,_):
        val = self.__stroke_color_entry.get()


        if not Validators.check_hex_rgb_color(val):
            messagebox.showerror('Invalid hex color code', 'The fill color hex code entered is invalid. '
                                                            + 'Please enter a valid hex color code.',master=self.__form)
            self.__stroke_color_entry.insert(tk.END, str(self.__stroke_color))


    def __cancel(self):
        if self.__has_changes:
            result = messagebox.askyesnocancel(
                "Unsaved Changes", 
                "You have unsaved changes. Do you want to save them before closing?",
                master=self.__form
            )
            if result is True:  # Yes - save and close
                self.__apply()
                self.__form.destroy()
            elif result is False:  # No - close without saving
                self.__form.destroy()
            # Cancel - do nothing, keep dialog open
        else:
            self.__form.destroy()


    def __ok(self):
        self.__apply()
        self.__form.destroy()


    def __apply(self):
        self.__config.set_hmi_display_settings(int(self.__display_width_entry.get()),
                                                int(self.__display_height_entry.get()),
                                                self.__display_color_entry.get(),
                                                True,
                                                True)


        self.__config.set_extracted_hmi_graphic_settings(self.__fill_color_entry.get(),
                                                self.__stroke_color_entry.get(),
                                                self.__stroke_width_entry.get())
        
        self.__config.set_hmi_material_line_properties(self.__material_line_width_entry.get(),
                                                self.__material_line_color_entry.get(),
                                                "solid")
                                                
        self.__config.set_hmi_signal_line_properties(self.__signal_line_width_entry.get(),
                                                self.__signal_line_color_entry.get(),
                                                self.__signal_line_dash_dot_v.get())
     
        if self.__selected_hmi_library:
            self.__config.set_hmi_library(self.__selected_hmi_library[1]
                                        ,self.__selected_hmi_library[2]
                                        ,str(self.__selected_hmi_library[3])
                                        ,str(self.__selected_hmi_library[4]))
            
            
        if self.__selected_hmi_display_template:
            self.__config.set_hmi_display_template(self.__selected_hmi_display_template)

        if self.__selected_alarm_library:
            self.__config.set_alarm_library(self.__selected_alarm_library[1]
                                        ,self.__selected_alarm_library[2]
                                        ,str(self.__selected_alarm_library[3])
                                        ,str(self.__selected_alarm_library[4]))

        
        if self.__selected_project_library:
            self.__config.set_acm_project(self.__selected_project_library[1]
                                          ,self.__selected_project_library[2]
                                          ,str(self.__selected_project_library[3])
                                          ,str(self.__selected_project_library[4]))
            
        if self.__selected_controller_library:
            self.__config.set_acm_controller(self.__selected_controller_library[1]
                                                ,self.__selected_controller_library[2]
                                                ,str(self.__selected_controller_library[3])
                                                ,str(self.__selected_controller_library[4]))
            
        if self.__selected_controller_program:
            self.__config.set_acm_controller_program(self.__selected_controller_program)

        if self.__selected_controller_task:
            self.__config.set_acm_controller_task(self.__selected_controller_task)

        # Save PLC firmware / software revision (validated: 2 digits, >= 20).
        # Falls back to the previously saved value if the entry is invalid.
        software_revision_value = self.__software_revision.get().strip()
        try:
            software_revision_int = int(software_revision_value)
        except ValueError:
            software_revision_int = None

        if software_revision_int is None or software_revision_int < 20:
            messagebox.showwarning(
                "Invalid PLC firmware revision",
                "PLC firmware revision must be a number between 20 and 99. "
                "Reverting to the previously saved value."
            )
            previous_value = self.__config.get_acm_controller_software_revision()
            self.__software_revision.set(previous_value)
        else:
            self.__config.set_acm_controller_software_revision(str(software_revision_int))

        if self.__selected_match_score:
            self.__config.set_scanning_match_score(self.__selected_match_score)

        # Save use scale invariant setting
        self.__config.set_scanning_use_scale_invariant(self.__use_scale_invariant_v.get())

        # Save show advanced linking setting
        self.__config.set_show_advanced_linking(self.__show_advanced_linking_v.get())

        # Save LLM inference settings. Only values that require normalisation
        # (provider label → stored value) get preprocessed; the rest go
        # through as trimmed strings. The API key itself is NOT persisted
        # here — it lives in the DPAPI store (see _save_llm_openai_key).
        self.__config.set_llm_inference_settings(
            provider=self._selected_llm_provider_value(),
            openai_base_url=self.__llm_openai_base_url_entry.get().strip(),
            openai_model=self.__llm_openai_model_entry.get().strip() or 'gpt-4.1-mini',
            openai_organization=self.__llm_openai_org_entry.get().strip(),
            ollama_mode=(self.__llm_ollama_mode_v.get() or 'bundled').strip().lower(),
            ollama_remote_url=self.__llm_ollama_url_entry.get().strip(),
            ollama_model=self.__llm_ollama_model_entry.get().strip() or 'reasoning:4b',
        )

        # Save FactoryTalk View SE Add Component Tool settings. Text fields
        # are trimmed to avoid stray whitespace ending up on the command
        # line. The application name is not collected — it is passed at
        # export time from the currently-open project name.
        self.__config.set_seadd_component_settings(
            exe_path=self.__seadd_exe_path_entry.get().strip(),
            application_type=(self.__seadd_application_type_v.get() or 'Distributed').strip(),
            area_name=self.__seadd_area_name_entry.get().strip() or '/',
            overwrite=self.__seadd_overwrite_v.get(),
        )

        # Save Rockwell SDK wheel-directory overrides. Empty string clears
        # the override so the getter falls back to the installer default
        # exposed by ``DEFAULT_LOGIX_SDK_WHEEL_DIR`` /
        # ``DEFAULT_LOGIX_ECHO_SDK_WHEEL_DIR``.
        self.__config.set_logix_designer_sdk_wheel_dir(
            self.__logix_designer_sdk_dir_entry.get().strip()
        )
        self.__config.set_logix_echo_sdk_wheel_dir(
            self.__logix_echo_sdk_dir_entry.get().strip()
        )

        # Reset change detection after successful save
        self.__ignore_change_events = True
        self.__capture_initial_values()
        self.__ignore_change_events = False
        self.__has_changes = False
        self.__update_button_states()
        self.__update_form_title()

                                                

  
if __name__ == "__main__":

    def open_Toplevel():
        db = settings()
        


    root = tk.Tk()
    
    button = tk.Button(root, text = "open toplevel1",
                command = open_Toplevel)
    button.place(x = 75, y = 50)

    root.mainloop()
