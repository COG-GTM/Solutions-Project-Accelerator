# -*- coding: utf-8 -*-
import tkinter as tk

class Custom_Menu:
    """ Menu widget for the main GUI window """
    def __init__(self, master, config, shortcuts, functions):
        """ Initialize the Menu """
        self.__config = config  # obtain link on config file
        self.__shortcuts = shortcuts  # obtain link on keyboard shortcuts
        self.__functs = functions  # obtain link on dictionary of functions
        self.menubar = tk.Menu(master)  # create main menu bar, public for the main GUI
        self.menubar.config(bg="white")
        self.empty_menu = tk.Menu(master)  # empty menu to hide the real menubar in fullscreen mode
        # Enable / disable these menu labels
        self.__label_recent = 'Open recent'
        self.__label_tools = 'Tools'
        self.__label_export_images = 'Export Images'
        self.__label_extract_lines = 'Extract Lines'
        self.__label_create_acm_project = 'Create ACM Project'
        self.__label_create_assigned_acm_objects = 'Create Assigned ACM Objects'
        self.__label_create_displays = 'Create Displays'
        self.__label_create_alarms = 'Create Alarms'
        self.__label_build_plc = 'Build PLC'
        self.__label_build_plc_l5x = 'L5X'
        self.__label_build_plc_logix_designer = 'Logix Designer'
        self.__label_build_plc_echo = 'Logix Echo'
        self.__label_build_hmi = 'Build HMI'
        self.__label_build_hmi_xml_and_images = 'XML and Images'
        self.__label_build_hmi_view_designer = 'View Designer'
        self.__label_settings = 'Settings'
        self.__label_about = 'About'
        self.__label_refresh_rois = 'Refresh ROI'
        # Create menu for the image
        self.__file = tk.Menu(self.menubar, tearoff=False, postcommand=self.__list_recent)
        self.__file.add_command(label='New project',
                                command=self.__shortcuts[0][2],
                                accelerator=self.__shortcuts[0][0])
        self.__recent_projects = tk.Menu(self.__file, tearoff=False)
        self.__file.add_cascade(label=self.__label_recent, menu=self.__recent_projects)
        self.__file.add_command(label='Open project',
                                command=self.__shortcuts[1][2],
                                accelerator=self.__shortcuts[1][0])
        self.__file.add_separator()
        self.__file.add_command(label='Import project',
                                command=self.__shortcuts[2][2],
                                accelerator=self.__shortcuts[2][0])
        self.__file.add_command(label='Export project',
                                command=self.__shortcuts[16][2])
        self.__file.add_separator()
        self.__file.add_command(label='Connect Database',
                                command=self.__shortcuts[3][2],
                                accelerator=self.__shortcuts[3][0])
        self.__file.add_command(label='Link ACM Project',
                                command=self.__shortcuts[4][2],
                                accelerator=self.__shortcuts[4][0])
        self.__file.add_separator()
        self.__file.add_command(label='Exit',
                                command=self.__functs['destroy'],
                                accelerator=u'Alt+F4')
        self.menubar.add_cascade(label='File', menu=self.__file)
        # Create menu for the tools: cut rectangular images with the rolling window, etc.
        self.__tools = tk.Menu(self.menubar, tearoff=False)
        self.__tools.add_command(label=self.__label_export_images,
                                 command=self.__shortcuts[5][2])
        self.__tools.add_command(label='Export Reduced Images',
                                 command=self.__shortcuts[21][2])
        self.__tools.add_separator()
        self.__tools.add_command(label=self.__label_create_acm_project,
                                    command=self.__shortcuts[17][2])
        self.__tools.add_command(label=self.__label_create_assigned_acm_objects,
                                    command=self.__shortcuts[18][2])
        self.__tools.add_command(label=self.__label_create_displays,
                                 command=self.__shortcuts[7][2])
        self.__tools.add_command(label=self.__label_create_alarms,
                                 command=self.__shortcuts[22][2])
        self.__tools.add_separator()
        # Build HMI → submenu with per-target commands. XML and Images
        # writes files only; View Designer additionally invokes
        # SEAddComponent.exe to push the components into a FactoryTalk
        # View SE application (application name = current project name,
        # other args from the SE Add Component Tool section in Settings).
        self.__build_hmi_menu = tk.Menu(self.__tools, tearoff=False)
        self.__build_hmi_menu.add_command(label=self.__label_build_hmi_xml_and_images,
                                          command=self.__shortcuts[19][2])
        self.__build_hmi_menu.add_command(label=self.__label_build_hmi_view_designer,
                                          command=self.__shortcuts[26][2])
        self.__tools.add_cascade(label=self.__label_build_hmi,
                                 menu=self.__build_hmi_menu)
        # Build PLC → submenu with per-target commands. The legacy
        # single command mapped to shortcut index 20 (L5X output); new
        # targets are appended to __shortcuts and referenced by index
        # here. Logix Echo pushes the built ACD into the local
        # FactoryTalk Logix Echo emulator via the ftecho_sdk wheel.
        self.__build_plc_menu = tk.Menu(self.__tools, tearoff=False)
        self.__build_plc_menu.add_command(label=self.__label_build_plc_l5x,
                                          command=self.__shortcuts[20][2])
        self.__build_plc_menu.add_command(label=self.__label_build_plc_logix_designer,
                                          command=self.__shortcuts[24][2])
        self.__build_plc_menu.add_command(label=self.__label_build_plc_echo,
                                          command=self.__shortcuts[25][2])
        self.__tools.add_cascade(label=self.__label_build_plc,
                                 menu=self.__build_plc_menu)
        self.__tools.add_separator()
        self.__tools.add_command(label=self.__label_settings,
                                 command=self.__shortcuts[10][2])
        self.menubar.add_cascade(label=self.__label_tools, menu=self.__tools)
        # Create menu for the view: fullscreen, default size, etc.
        self.__view = tk.Menu(self.menubar, tearoff=False)
        self.__view.add_command(label='Fullscreen',
                                command=self.__functs["toggle_fullscreen"],
                                accelerator='F11')
        self.__view.add_command(label='Default size',
                                command=self.__functs["default_geometry"])
        self.__view.add_separator()
        self.__view.add_command(label=self.__label_refresh_rois,
                                command=self.__functs["refresh_roi"],
                                accelerator='F5',state='disabled')
        self.menubar.add_cascade(label='View', menu=self.__view)
        
         # Create menu for the view: fullscreen, default size, etc.
        self.__help = tk.Menu(self.menubar, tearoff=False)
        self.__help.add_command(label='Get Help',
                                command=self.__shortcuts[12][2])
        self.__help.add_command(label='Documentation',
                                command=self.__shortcuts[11][2])
        self.__help.add_separator()
        self.__help.add_command(label='Register ACM Libraries',
                                command=self.__shortcuts[14][2])
        self.__help.add_separator()
        self.__help.add_command(label=self.__label_about,
                                command=self.__shortcuts[9][2])
        self.menubar.add_cascade(label='Help', menu=self.__help)

    def __list_recent(self):
        """ List of the recent images """
        self.__recent_projects.delete(0, 'end')  # empty previous list
        lst = self.__config.get_recent_projects_list()  # get list of recently opened images
        for project in lst:  # get list of recent projects
            self.__recent_projects.add_command(label=project,
                                             command=lambda x=project: self.__functs["open_project"](x))
        # Disable recent list menu if it is empty.
        if self.__recent_projects.index('end') is None:
            self.__file.entryconfigure(self.__label_recent, state='disabled')
        else:
            self.__file.entryconfigure(self.__label_recent, state='normal')

    def __check_figures(self):
        """ Check if there are figures on the image and enable/disable menu 'Rolling Window' """
        if self.__functs["check_roi"]():  # there are regions of interest on the image
            self.__tools.entryconfigure(self.__label_export_images, state='normal')  # enable menu
        else:  # if there are no figures
            self.__tools.entryconfigure(self.__label_export_images, state='disabled')  # disable menu

    def set_state(self, state):
        """ Enable / disable some menus """
        self.__tools.entryconfigure(self.__label_export_images, state=state)


    def enable_create_acm_project(self, enable=True):
        self.__tools.entryconfigure(self.__label_create_acm_project, state='normal' if enable else 'disabled')
        self.__tools.entryconfigure(self.__label_create_assigned_acm_objects, state='disabled' if enable else 'normal')
        self.__tools.entryconfigure(self.__label_create_displays, state='disabled' if enable else 'normal')
        self.__tools.entryconfigure(self.__label_create_alarms, state='disabled' if enable else 'normal')
        self.__tools.entryconfigure(self.__label_build_hmi, state='disabled' if enable else 'normal')
        self.__tools.entryconfigure(self.__label_build_plc, state='disabled' if enable else 'normal')

    def enable_refresh_roi(self, enable=True):
        if enable:
            self.__view.entryconfigure(self.__label_refresh_rois, state='normal')
        else:
            self.__view.entryconfigure(self.__label_refresh_rois, state='disabled') 