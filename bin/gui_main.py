# -*- coding: utf-8 -*-
import json
import subprocess
import threading
import webbrowser
import shutil
from logging import Logger

from bin.gui_db_connection import db_conntection_form
import os
import win32api
import PIL
from bin.gui_hmi_graphic_view import hmi_graphic_view
from bin.gui_hover_toggle_button_with_badge import hover_toggle_button_with_badge
from bin.gui_selector_tools import SelectorTools
from bin.gui_settings import settings
from bin.gui_textbox_progressbar_window import texbox_progressbar_window
from bin.logic_acm_libraries_retrieval import acm_libraries_retrieval
from bin.logic_acm_console import ACM_Console
from bin.logic_export_import_project import import_project, export_project, read_project_name_from_zip
from bin.logic_project_paths import InvalidProjectName, project_dir
from bin.logic_internal_database import Database

import tkinter as tk

from tkinter import ttk
from tkinter import messagebox
from tkinter.filedialog import askopenfilename

from bin.logic_llm_inference import UnifiedInference
from bin.logic_secret_store import has_openai_key
from .gui_menu import Custom_Menu
from .logic_config import Config
from .logic_logger import logging, handle_exception
from .logic_tools import  start_build_hmi, build_pages, create_alarms, export_images, export_reduced_images, find_pages_needing_hmi_displays, get_version_number, open_figures, start_build_plc
from .logic_logix_designer import push_build_output_to_logix_designer, is_sdk_available, sdk_install_hint, LogixDesignerSdkNotFoundError
from .logic_logix_echo import (
    push_build_output_to_logix_echo,
    is_sdk_available as is_logix_echo_sdk_available,
    sdk_install_hint as logix_echo_sdk_install_hint,
    LogixEchoSdkNotFoundError,
    LogixEchoControllerExistsError,
)
from .gui_elements import hover_toggle_button, animated_hover_button, button_array
from .gui_base64_icons import *
from .gui_navigation_frame import *
from .gui_tool_frame import *
from .gui_wizard import *
from .gui_sort_filter_elements import filter_option_button, sort_option_button, search_button

from bin.gui_sheet import SheetGUI
from tksheet import Sheet

from bin.gui_sheet_selector import SheetSelectorTools
from bin.gui_text_selector_tools import TextSelectorTools
from bin.gui_build_displays import BuildDisplay



# Support/community links are deployment-specific and are therefore not
# hard-coded. Set them in the environment (or a .env consumed by the
# launcher) to enable the corresponding Help menu entries.
GET_HELP_URL = os.environ.get("SPA_GET_HELP_URL", "")
DOCUMENTATION_URL = os.environ.get("SPA_DOCUMENTATION_URL", "")
JOIN_TEAM_URL = os.environ.get("SPA_JOIN_TEAM_URL", "")
REGISTER_ACM_SCRIPT_PATH = r".\acm_libraries\acm_library_register.cmd"


def _resolve_bundled_docs_index() -> str | None:
    """Return the absolute path to the bundled MkDocs ``index.html``, or None.

    The docs site is copied into ``_internal/docs/site/`` at build time by
    ``runme.spec`` (see the ``datas`` entry for ``build/docs_site``).  When
    running from source we look at the same relative location under the
    repository root so developers get the same experience.
    """
    import sys as _sys

    candidate_bases: list[str] = []
    # 1. Frozen (PyInstaller onefile / onedir) — data files live under _MEIPASS.
    meipass = getattr(_sys, "_MEIPASS", None)
    if meipass:
        candidate_bases.append(meipass)
    # 2. Installed layout — runme.exe sits next to the _internal folder.
    if getattr(_sys, "frozen", False):
        candidate_bases.append(os.path.dirname(_sys.executable))
    # 3. Running from source — repository root (two levels up from this file).
    candidate_bases.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

    for base in candidate_bases:
        for rel in ("docs/site/index.html", "_internal/docs/site/index.html", "build/docs_site/index.html"):
            path = os.path.join(base, rel)
            if os.path.isfile(path):
                return path
    return None

class MainGUI(ttk.Frame):
    """ Main GUI Window """
    def __init__(self, mainframe):
        """ Initialize the Frame """
        logging.info('Open GUI')
        ttk.Frame.__init__(self, master=mainframe)
        self.__project_name = None
        self.__project_description = None
        self.__set_up_theme()
        self.__create_instances()
        self.__create_main_window()
        self.__create_widgets()
        self.__connect_sql_db()
        self.type = None
        mainframe.bind("<FocusIn>", self.__on_focus_in)
        mainframe.bind("<FocusOut>", self.__on_focus_out) 
        if len(sys.argv) > 1:
            file_path = sys.argv[1]
            self.import_project(file_path,True)


    def __create_instances(self):
        """ Instances for GUI are created here """
        self.__config = Config()  # open config file of the main window
        # Pass the Config so UnifiedInference can honour any user-configured
        # provider override (external OpenAI key or remote Ollama). When
        # nothing is overridden the resolver tries the optional
        # ``genai_bridge`` enterprise gateway, then falls back to Ollama.
        self.__llm_manager = UnifiedInference(
            config=self.__config,
            model_name="gpt-4.1-mini",
        )
        self.__connection_string = self.__config.get_connection_string()
        self.__imframe = None  # empty instance of image frame (canvas)
        self.__navigation_panel_hidden = None
        self.__acm_data_handler = None
        self.__tools_page_shown = 0

        # First-run hint for installs with no reachable LLM backend. The
        # check is purely informational; the app still runs regardless.
        self.__maybe_prompt_llm_first_run()

  


    def __connect_sql_db(self):
        if self.__connection_string:
            self.__set_connection_string()


    def __create_main_window(self):
        """ Create main window GUI"""
        self.__default_title = 'Solutions Project Accelerator'
        self.master.title(self.__default_title)
        self.master.geometry(self.__config.get_win_geometry())  # get window size/position from config
        self.master.wm_state(self.__config.get_win_state())  # get window state
        # self.destructor gets fired when the window is destroyed
        self.master.protocol('WM_DELETE_WINDOW', self.destroy)
        #
        self.__fullscreen = False  # enable / disable fullscreen mode
        self.__bugfix = False  # BUG! when change: fullscreen --> zoomed --> normal
        self.__previous_state = 0  # previous state of the event
        # List of shortcuts in the following format: [name, keycode, function]
        self.keycode = {}  # init key codes
        self.keycode = {
            'n': 78,
            'o': 79,
            'i': 73,
            'k': 75,
            'l': 76,
            's': 83,
        }
        
        self.__shortcuts = [['Ctrl+N', self.keycode['n'], self.__new_project],          # 0 
                            ['Ctrl+O', self.keycode['o'], self.__open_project],         # 1
                            ['Ctrl+I', self.keycode['i'], self.__import_project],       # 2
                            ['Ctrl+K', self.keycode['k'], self.__connect_to_db],        # 3
                            ['Ctrl+L', self.keycode['l'], self.__link_acm_project],     # 4
                            ['', None, self.__start_export_images],                     # 5
                            ['', None, self.__extract_lines],                           
                            ['', None, self.__create_displays],
                            ['', None, None],                                          # 8 (removed: report issue)
                            ['', None, self.__about],
                            ['', None, self.__settings],
                            ['', None, self.__documentation],
                            ['', None, self.__get_help],
                            ['', None, self.__join_team],
                            ['', None, self.__register_acm_libraries],
                            ['', None, None],                                          # 15 (removed: check for update)
                            ['', None, self.__export_project],
                            ['', None, self.__create_acm_project],
                            ['', None, self.__create_acm_objects],
                            ['', None, self.__build_hmi_xml_and_images],                     # 19 Build HMI → XML and Images
                            ['', None, self.__build_plc],
                            ['', None, self.__start_export_reduced_images],
                            ['', None, self.__create_alarms],
                            ['', None, None],                                          # 23 (removed: extraction template manager)
                            ['', None, self.__build_plc_logix_designer], # 24 Build PLC → Logix Designer (.ACD via SDK)
                            ['', None, self.__build_plc_logix_echo], # 25 Build PLC → Logix Echo (push .ACD via ftecho_sdk)
                            ['', None, self.__build_hmi_view_designer]] # 26 Build HMI → View Designer (push to FTView SE via SEAddComponent.exe)
        # Bind events to the main window
        self.master.bind('<Motion>', lambda event: self.__motion())  # track and handle mouse pointer position
        self.master.bind('<F11>', lambda event: self.__toggle_fullscreen())  # toggle fullscreen mode
        self.master.bind('<Escape>', lambda event, s=False: self.__toggle_fullscreen(s))
        self.master.bind('<F5>', lambda event: self.__refresh_roi())  # reset default window geometry
        # Handle main window resizing in the idle mode, because consecutive keystrokes <F11> - <F5>
        # don't set default geometry from full screen if resizing is not postponed.
        self.master.bind('<Configure>', lambda event: self.master.after_idle(self.__resize_master))
        # Handle keystrokes in the idle mode, because program slows down on a weak computers,
        # when too many key stroke events in the same time.
        self.master.bind('<Key>', lambda event: self.master.after_idle(self.__keystroke, event))


    def __toggle_fullscreen(self, state=None):
        """ Enable/disable the full screen mode """
        if state is not None:
            self.__fullscreen = state  # set state to fullscreen
        else:
            self.__fullscreen = not self.__fullscreen  # toggling the boolean
        # Hide menubar in fullscreen mode or show it otherwise
        if self.__fullscreen:
            self.__menubar_hide()
        else:  # show menubar
            self.__menubar_show()
        self.master.wm_attributes('-fullscreen', self.__fullscreen)  # fullscreen mode on/off


    def __menubar_show(self):
        """ Show menu bar """
        self.master.configure(menu=self.__menu.menubar)

    def __menubar_hide(self):
        """ Hide menu bar """
        self.master.configure(menu=self.__menu.empty_menu)

    def __motion(self):
        """ Track mouse pointer and handle its position """
        if self.__fullscreen:
            y = self.master.winfo_pointery()
            if 0 <= y < 20:  # if close to the upper side of the main window
                self.__menubar_show()
            else:
                self.__menubar_hide()

    def __keystroke(self, event):
        """ Language independent handle events from the keyboard
            Link1: http://infohost.nmt.edu/tcc/help/pubs/tkinter/web/key-names.html
            Link2: http://infohost.nmt.edu/tcc/help/pubs/tkinter/web/event-handlers.html """
        #print(event.keycode, event.keysym, event.state)  # uncomment it for debug purposes
        if event.state - self.__previous_state == 4:  # check if <Control> key is pressed
            for shortcut in self.__shortcuts:
                if event.keycode == shortcut[1]:
                    shortcut[2]()
        else:  # remember previous state of the event
            self.__previous_state = event.state

    def __default_geometry(self):
        """ Reset default geometry for the main GUI window """
        self.__toggle_fullscreen(state=False)  # exit from fullscreen
        self.master.wm_state(self.__config.default_state)  # exit from zoomed
        self.__config.set_win_geometry(self.__config.default_geometry)  # save default to config
        self.master.geometry(self.__config.default_geometry)  # set default geometry

    def __resize_master(self):
        """ Save main window size and position into config file.
            BUG! There is a BUG when changing window from fullscreen to zoomed and then to normal mode.
            Main window somehow remembers zoomed mode as normal, so I have to explicitly set
            previous geometry from config INI file to the main window. """
        if self.master.wm_attributes('-fullscreen'):  # don't remember fullscreen geometry
            self.__bugfix = True  # fixing bug
            return
        if self.master.state() == 'normal':
            if self.__bugfix is True:  # fixing bug for: fullscreen --> zoomed --> normal
                self.__bugfix = False
                # Explicitly set previous geometry to fix the bug
                self.master.geometry(self.__config.get_win_geometry())
                return
            self.__config.set_win_geometry(self.master.winfo_geometry())
        self.__config.set_win_state(self.master.wm_state())

    def __create_widgets(self):
        """ Widgets for GUI are created here """

        
        # Create menu widget
        self.functions = {  # dictionary of functions for menu widget
            "destroy": self.destroy,
            "toggle_fullscreen": self.__toggle_fullscreen,
            "default_geometry": self.__default_geometry,
            "open_project": self.open_project,
            "check_roi": self.__check_roi,
            "refresh_roi": self.__refresh_roi}
        self.__menu = Custom_Menu(self.master, self.__config, self.__shortcuts, self.functions)
        self.master.configure(menu=self.__menu.menubar)  # menu should be BEFORE iconbitmap, it's a bug
        # BUG! Add menu bar to the main window BEFORE iconbitmap command. Otherwise it will
        # shrink in height by 20 pixels after each open-close of the main window.
        this_dir = os.path.dirname(os.path.realpath(__file__))  # directory of this file
        self.master.iconbitmap(os.path.join(this_dir, 'logo.ico'))  # set logo icon
        
        # Create placeholder frame for the image
        
        self.master.rowconfigure(0, weight=1)  # make grid cell expandable
        self.master.columnconfigure(0, weight=1)
        
        frame2 = tk.Frame(self.master, bg='white')
        frame2.grid(row=0, column=0, sticky='nsew')
        frame2.columnconfigure(0, weight=1)
        frame2.rowconfigure(0, weight=0)
        frame2.rowconfigure(1, weight=1)  
        
        frame2a = tk.Frame(frame2, height=70, width=770, bg='white') 
        frame2a.grid(row=0, column=0, sticky='nsew')
        frame2a.columnconfigure(0, weight=1)
        frame2a.rowconfigure(0, weight=0)   
        x0 = frame2a.winfo_screenwidth()/2
        y0 = frame2a.winfo_screenheight()/2
        
        self.__setup_main_menu_canvas(frame2a)

        
        frame2b = tk.Frame(frame2, height=410, width=770) 
        frame2b.grid(row=1, column= 0, sticky='nsew')
        frame2b.columnconfigure(0, weight=1)
        frame2b.rowconfigure(1, weight=1)  
        
        self.pw = tk.PanedWindow(frame2b,orient ='horizontal',borderwidth=2,
                                 opaqueresize=False,proxybackground='#00AEEF')
        self.pw.grid(row=1, column=0, sticky ="nsew")
        self.left = ttk.Frame(self.pw)
        
        self.pw.add(self.left, stretch="always")
        self.pw.paneconfigure(self.left, minsize=15)


        self.left_arrow = tk.PhotoImage(data=left_arrow)
        self.right_arrow = tk.PhotoImage(data=right_arrow)
        self.left_button = tk.Button(self.left,width=15,relief='flat',background='#E0E0E0',bd=0,image=self.left_arrow,command=self.__handle_left_panel_hide_button)
        self.left_button.pack(fill='y',side='right', padx=0, pady=0)
        
        self.__setup_navigation_canvas()
        
        #self.__placeholder = ttk.Frame(self.master)
        self.__placeholder = ttk.Frame(self.pw)
        self.pw.add(self.__placeholder, stretch="always")
        #self.__placeholder.grid(row=0, column=0, sticky='nswe')
        self.__placeholder.rowconfigure(0, weight=1)  # make grid cell expandable
        self.__placeholder.columnconfigure(0, weight=1)
        # If image wasn't closed previously, open this image once again
        self.right = ttk.Frame(self.pw)
        self.pw.add(self.right, stretch="always",minsize=420)
        self.__setup_tool_canvas()
        self.__pass_document_selected_func()
        #self.__pass_sheet_selected_func()


        self.__show_sort_filter_buttons = True

        
        def click(_):
            """ To remove focus on other elements"""
            self.__placeholder.focus_set()

        self.__placeholder.bind("<Button-1>", click)
        
        self.pw.update()
        
        self.navigation_sash_position = self.__config.get_navigation_sash()
        self.pw.sash_place(0,self.navigation_sash_position[0],self.navigation_sash_position[1])
        
        sash_position = self.__config.get_tool_sash()
        self.pw.sash_place(1,sash_position[0],sash_position[1])
        
        self.__navigation_panel_hidden = self.__config.get_is_navigation_panel_hidden()
        if not self.__navigation_panel_hidden:
            self.left_button.config(image=self.left_arrow)
            self.pw.update()
            self.pw.sash_place(0,self.navigation_sash_position[0],self.navigation_sash_position[1])
        else: 
            self.left_button.config(image=self.right_arrow)
            self.navigation_sash_position = self.pw.sash_coord(0)
            self.pw.sash_place(0,0,self.navigation_sash_position[1])
        
        self.master.update()
        
    

    def __check_page_number(self, page_number, action_type):
        if action_type == '1': #insert
            if not self.__imframe:
                return False
                
            if not page_number.isnumeric():
                return False

            if not self.__imframe.page_count >= int(page_number):
                return False
            
        return True

    def page_number_callback(self, page_number, total_pages):
        self.page_number.entry.delete(0, END)
        self.page_number.entry.insert(0, str(page_number))

        total_page_number_string = '/ '+str(total_pages)
        self.canvas.itemconfig(self.__total_page_number, text= total_page_number_string)
        self.navigation_frame.set_page(int(page_number) - 1)


    def page_number_edit_callback(self):
        if not self.__imframe:
            return

        if int(self.page_number.entry.get()) != (int(self.__imframe.pno + 1)):
            self.update_page(int(self.page_number.entry.get()))


    def page_up(self, _, __):
        if not self.__imframe:
            return

        if self.__imframe.page_count > (self.__imframe.pno + 1):
            self.update_page(self.__imframe.pno + 2)


    def page_down(self, _, __):
        if not self.__imframe:
            return

        if 0 < self.__imframe.pno:
            self.update_page(self.__imframe.pno)

    def go_to_page_callback(self, page):
        self.__imframe.go_to_page(page)


    def update_page(self, page):
        self.__imframe.go_to_page(page)
        self.navigation_frame.set_page(page - 1)


    def __register_acm_libraries(self):

        # Check if the application is frozen
        if not getattr(sys, 'frozen', False):
            messagebox.showinfo("Not Supported", "This function only works for frozen versions.")
            return
        
        try:
            # Run the CMD script and wait for it to complete
            subprocess.run(["cmd.exe", "/c", REGISTER_ACM_SCRIPT_PATH], text=True, capture_output=True, check=True
                                    , creationflags=subprocess.CREATE_NO_WINDOW)
            messagebox.showinfo("ACM Libraries Registered", "Libraries have successfully been registered in ACM.")
        except subprocess.CalledProcessError as e:
            # If an error occurs during script execution, show an error message
            messagebox.showerror("Error Registering ACM Libraries", "Script execution failed.\n\nError:\n" + e.stderr)


    def __check_zoom_percentage(self, zoom_percentage, action_type):
        if action_type == '1': #insert
            if not self.__imframe:
                return False
                
            if not zoom_percentage.isnumeric():
                return False

            if not 50000 >= int(zoom_percentage):
                return False

            if not 1 <= int(zoom_percentage):
                return False
            
        return True

    def zoom_percentage_callback(self, percentage):
        percentage_string = str(int(percentage))
        if self.zoom_percentage.entry.get() != percentage_string:
            self.zoom_percentage.entry.delete(0, END)
            self.zoom_percentage.entry.insert(0, percentage_string)


    def read_only_zoom_percentage_callback(self, percentage):
        percentage_string = str(int(percentage))
        if self.zoom_percentage.entry.get() != percentage_string:
            self.zoom_percentage.entry.config(state=NORMAL)
            self.zoom_percentage.entry.delete(0, END)
            self.zoom_percentage.entry.insert(0, percentage_string)
            self.zoom_percentage.entry.config(state='readonly')

    def zoom_percentage_edit_callback(self):
        if not self.__imframe:
            return

        if int(self.zoom_percentage.entry.get()) != (int(self.__imframe.imscale *100)):
            self.__imframe.zoom(self.zoom_percentage.entry.get())


    def zoom_in(self,_,__):
        if not self.__imframe:
            return

        if (self.__imframe.imscale * 100 * 1.3) > 50000:
            return

        self.__imframe.zoom(self.__imframe.imscale * 100 * 1.3)


    def zoom_out(self,_,__):
        if not self.__imframe:
            return

        if (self.__imframe.imscale * 100 / 1.3) < 2:
            return


        self.__imframe.zoom(self.__imframe.imscale * 100 / 1.3)


    def __setup_main_menu_canvas(self, parent):
        self.canvas = tk.Canvas(parent, height=50, width=770,background="white", highlightthickness=0)
        
        def click(_):
            """ To remove focus on other elements"""
            self.canvas.focus_set()

        self.canvas.bind('<Button-1>',click)
        self.canvas.pack(fill=tk.BOTH, expand=1)

        self.canvas.create_line(0, 0, 70, 50)
        self.canvas.create_line(0, 20, 70, 0, fill="red", dash=(4, 4))

        self.page_number = custom_entry(self.canvas,0,0,enbale_rect=False,width=40,size=9,state=DISABLED,enable_line=False,
                                        focus_out_callback=self.page_number_edit_callback)
        self.page_number.entry.configure(validate="key", justify=tk.RIGHT)
        self.page_number.entry['validatecommand'] = (self.page_number.entry.register(self.__check_page_number),'%P','%d')

        self.zoom_percentage = custom_entry(self.canvas,0,0,enbale_rect=False,width=40,size=9,state=DISABLED,enable_line=False,
                                            focus_out_callback=self.zoom_percentage_edit_callback)
        self.zoom_percentage.entry.configure(validate="key", justify=tk.RIGHT)
        self.zoom_percentage.entry['validatecommand'] = (self.zoom_percentage.entry.register(self.__check_zoom_percentage),'%P','%d')
        
        self.canvas.bind("<Configure>", self.__configure_main_menu_canvas)
        
            
    def __configure_main_menu_canvas(self, event):
        self.canvas.delete("all")
        w, h = event.width, 50
                
        button8 = hover_toggle_button(self.canvas, page_up_blue, page_up_dark_gray, page_down_light_gray, anchor = 'w',
                                        is_toggle=False, callback=self.page_down)
        self.page_up_button = button8
        self.canvas.create_window(w/2-330, 20, anchor='nw', window=button8)
        self.page_down_button = hover_toggle_button(self.canvas, page_down_blue, page_down_dark_gray, page_down_light_gray, anchor = 'w',
                                        is_toggle=False, callback=self.page_up)
        self.canvas.create_window(w/2-300, 20, anchor='nw', window=self.page_down_button)
       
        self.page_number.draw(x = w/2-270,y = 5)
        
        self.__total_page_number = self.canvas.create_text(w/2-210,24,fill="#2F2F2F",font="Arial 9",
                        text="/ -", anchor='nw')
        self.canvas.create_line(w/2-170,20,w/2-170,44, fill="#D5D5D5",width=2)
        
        self.select_tool_button = hover_toggle_button(self.canvas, select_tool_blue, select_tool_dark_gray, select_tool_light_gray
                                        , anchor = 'w', is_toggle=False, tool_tip_text='Select tool')
        self.canvas.create_window(w/2-160, 20, anchor='nw', window=self.select_tool_button)
        self.hand_tool_button = hover_toggle_button(self.canvas, hand_tool_blue, hand_tool_dark_gray, hand_tool_light_gray
                                        , anchor = 'w', is_toggle=False, tool_tip_text='Move tool')
        self.canvas.create_window(w/2-120, 20, anchor='nw', window=self.hand_tool_button)
        self.zoom_in_button = hover_toggle_button(self.canvas, zoom_in_blue, zoom_in_dark_gray, zoom_in_light_gray, anchor = 'w',
                                        is_toggle=False, callback=self.zoom_in, tool_tip_text='Zoom in')
        self.canvas.create_window(w/2-80, 20, anchor='nw', window=self.zoom_in_button)
        
        self.zoom_out_button = hover_toggle_button(self.canvas, zoom_out_blue, zoom_out_dark_gray, zoom_out_light_gray, anchor = 'w',
                                        is_toggle=False, callback=self.zoom_out, tool_tip_text='Zoom out')
        self.canvas.create_window(w/2-40, 20, anchor='nw', window=self.zoom_out_button)
        
        self.zoom_percentage.draw(x = w/2-10,y = 5)
        
        self.canvas.create_text(w/2+50,24,fill="#2F2F2F",font="Arial 9",
                        text=" %", anchor='nw')
        self.canvas.create_line(w/2+80,20,w/2+80,44, fill="#D5D5D5",width=2)
        self.rectangular_selection_tool_button = hover_toggle_button(self.canvas, rectangular_selection_tool_blue, rectangular_selection_tool_dark_gray, rectangular_selection_tool_light_gray
                                        , anchor = 'w', is_toggle=False, tool_tip_text='Draw a rectangle')
        self.canvas.create_window(w/2 + 98, 20, anchor='nw', window=self.rectangular_selection_tool_button)
        self.polygon_selection_tool_button = hover_toggle_button(self.canvas, polygon_selection_tool_blue, polygon_selection_tool_dark_gray, polygon_selection_tool_light_gray
                                        , anchor = 'w', is_toggle=False, tool_tip_text='Draw a polygon')
        self.canvas.create_window(w/2+138, 20, anchor='nw', window=self.polygon_selection_tool_button)
        self.auto_selection_tool_button = hover_toggle_button(self.canvas, magic_select_blue, magic_select_dark_gray, magic_select_light_gray
                                        , anchor = 'w', is_toggle=False, tool_tip_text='AI Select tool')
        self.canvas.create_window(w/2+178, 20, anchor='nw', window=self.auto_selection_tool_button)
        self.draw_roi_button = hover_toggle_button(self.canvas, magic_copy_select_blue, magic_copy_select_dark_gray, magic_copy_select_light_gray
                                        , anchor = 'w', is_toggle=False, tool_tip_text='Draw ROI tool')
        self.canvas.create_window(w/2+218, 20, anchor='nw', window=self.draw_roi_button)
        self.draw_roi_button.disable()
        self.selector_tool_buttons = button_array([self.select_tool_button
                                                    ,self.hand_tool_button
                                                    ,self.rectangular_selection_tool_button
                                                    ,self.polygon_selection_tool_button
                                                    ,self.auto_selection_tool_button
                                                    ,self.draw_roi_button]
                                                    ,self.__selector_tool_chosen)

           
    def __draw_roi_loaded(self, loaded=False):
        if loaded:
            if self.selector_tool_buttons.get_selected_button() != 5: self.selector_tool_buttons.select(5, True)
            self.draw_roi_button.update_on_image(magic_copy_selected_blue)
        else:
            self.draw_roi_button.update_on_image(magic_copy_select_blue)
            # No session is running, so don't leave Draw ROI showing as the active
            # tool in the toolbar - fall back to the select tool.
            if self.selector_tool_buttons.get_selected_button() == 5:
                self.selector_tool_buttons.select(0)


    def __draw_roi_availability_changed(self, available=False):
        """ Enable / disable the toolbar Draw ROI button based on whether the
        currently selected object can seed the tool (a linked-graphic cell). """
        if not hasattr(self, 'draw_roi_button') or self.draw_roi_button is None:
            return
        try:
            if available:
                self.draw_roi_button.enable()
            else:
                self.draw_roi_button.disable()
                # If the tool was active with the disabled button, drop the highlight.
                self.draw_roi_button.update_on_image(magic_copy_select_blue)
        except Exception:
            pass


    def __selector_tool_chosen(self, val):
        if self.__imframe:
            # Draw ROI reports its own state once the tool has tried to seed itself.
            if val != 5:
                self.__draw_roi_loaded()
            self.__imframe.selector_tool_chosen(val)

        
    def __setup_navigation_canvas(self):
        self.navigation_canvas = tk.Canvas(self.left, height=600, width=50,background="white",highlightthickness=0)

        def click(_):
            """ To remove focus on other elements"""
            self.navigation_canvas.focus_set()

        self.navigation_canvas.bind('<Button-1>',click)

        self.navigation_canvas.pack(fill='y',side='left', padx=0, pady=0)
        files_navigation_button = hover_toggle_button(self.navigation_canvas, folders_blue, folders_dark_gray, folders_light_gray, anchor = 'w',
                                        tool_tip_text='Project Documents', is_toggle=False)
        self.navigation_canvas.create_window(8, 8, anchor='nw', window=files_navigation_button)
        self.pages_navigation_button = hover_toggle_button(self.navigation_canvas, pages_blue, pages_dark_gray, pages_light_gray, anchor = 'w',
                                        tool_tip_text='Pages', is_toggle=False)
        self.pages_navigation_button.disable()
        self.navigation_canvas.create_window(8, 58, anchor='nw', window=self.pages_navigation_button)
        self.bookmarks_navigation_button = hover_toggle_button(self.navigation_canvas, bookmark_blue, bookmark_dark_gray, bookmark_light_gray, anchor = 'w',
                                        tool_tip_text='Bookmarks', is_toggle=False)
        self.bookmarks_navigation_button.disable()
        self.navigation_canvas.create_window(8, 108, anchor='nw', window=self.bookmarks_navigation_button)
        
        self.navigation_frame = navigation_frame(self.left, self.__config)
        self.navigation_frame.set_opened_document_func(self.__get_open_document_path)
        self.navigation_frame.set_close_doc_func(self.__close_doc)
        self.pw.bind("<ButtonRelease-1>", self.navigation_frame_release)
        self.navigation_frame.pack(fill='both',expand=1)
        self.navigation_frame.set_page_selected_callback(self.go_to_page_callback)
        
        
        self.navigation_buttons = button_array([files_navigation_button,self.pages_navigation_button,self.bookmarks_navigation_button],self.__navigation_canvas_callback)
        self.navigation_buttons.select(0)

    MIN_ALLOWABLE_NAVIGATION_FRAME = 200 # Min size before hidding the nvigation frame

    TOOLS_PAGES = {
        0 : 'tags_page',
        1 : 'graphics_page',
        2 : 'displays_page',
        3 : 'approvals_page'
    }

    def navigation_frame_release(self, _):
        if self.pw.sash_coord(0)[0] < self.MIN_ALLOWABLE_NAVIGATION_FRAME:
            self.left_button.config(image=self.right_arrow)
            self.navigation_sash_position = self.pw.sash_coord(0)
            self.pw.sash_place(0,0,self.navigation_sash_position[1])
            self.__navigation_panel_hidden = True
        else:
            self.left_button.config(image=self.left_arrow)
            self.__navigation_panel_hidden = False
    
        
    def __navigation_canvas_callback(self, id):
        options = {
            0 : 'project_folder_page',
            1 : 'page_navigation_page',
            2 : 'bookmark_navigation_page'
        }
        self.navigation_frame.show_frame(options[id])
        
    def __setup_tool_canvas(self):
        self.tool_canvas = tk.Canvas(self.right, height=600, width=50,background="white",highlightthickness=0)
        
        def click(_):
            self.tool_canvas.focus_set()

        self.tool_canvas.bind('<Button-1>',click)
        
        self.tool_canvas.pack(fill='y',side='right', padx=0, pady=0)
        button1 = hover_toggle_button(self.tool_canvas, tag_blue, tag_dark_gray, tag_light_gray, anchor = 'w',
                                        tool_tip_text='Control Modules', tool_tip_anchor=tk.NW, is_toggle=False)
        self.tool_canvas.create_window(8, 8, anchor='nw', window=button1)
        button2 = hover_toggle_button(self.tool_canvas, graphic_blue, graphic_dark_gray, graphic_light_gray, anchor = 'w',
                                        tool_tip_text='Static Graphics', tool_tip_anchor=tk.NW, is_toggle=False)
        self.tool_canvas.create_window(8, 58, anchor='nw', window=button2)
        button3 = hover_toggle_button(self.tool_canvas, displays_blue, displays_dark_gray, displays_light_gray, anchor = 'w',
                                        tool_tip_text='HMI Displays', tool_tip_anchor=tk.NW, is_toggle=False)
        self.tool_canvas.create_window(8, 108, anchor='nw', window=button3)
        self.tool_canvas.create_line(8,158,42,158, fill="#D5D5D5",width=2)
        self.__pending_approvals_with_badge = hover_toggle_button_with_badge(self.tool_canvas, approval_blue, approval_dark_gray, approval_light_gray, anchor = 'w',
                                        tool_tip_text='Pending Approvals', tool_tip_anchor=tk.NW, is_toggle=False)
        self.__pending_approvals_with_badge_timer = None
        self.tool_canvas.create_window(8, 166, anchor='nw', window=self.__pending_approvals_with_badge)  
        self.tools_buttons = button_array([button1,button2,button3,self.__pending_approvals_with_badge],self.__tools_canvas_callback)
        # Virtual event lets us marshal pending-approval notifications from worker
        # threads back onto the Tk main thread safely (event_generate with
        # when='tail' is thread-safe; Widget.after is not).
        self.bind('<<PendingApprovalsChanged>>', self.__on_pending_approvals_changed)
        
        
        def callback_A(item):
            print(item)

        def callback_B(string):
            self.tool_frame.run_search(string)
            
        self.filter_button_window = None
        self.sort_button_window = None
        self.search_button_window = None
        self.back_button_window = None
        self.sort_option_button = None
        self.sort_filter_canvas = tk.Canvas(self.right, height=50, width=200,background="white",highlightthickness=0)
        

        def click(_):
            """ To remove focus on other elements"""
            self.sort_filter_canvas.focus_set()

        self.sort_filter_canvas.bind('<Button-1>',click)
        self.sort_filter_canvas.pack(fill='x', expand=0)
        self.tool_frame = tool_frame(self.right, canvas_callback=self.__update_canvas, show_sort_filter_callback=self.show_sort_filter_buttons, sort_by_options_callback=self.__sort_by_options, page_changed_callback=self.__tool_page_changed)
        self.tool_frame.set_roi_refresher(self.__refresh_roi)
        self.tool_frame.pack(fill='both',expand=1)
        self.search_button = search_button(self.sort_filter_canvas, callback=callback_A, edit_callback=callback_B)
        self.search_button_window = self.sort_filter_canvas.create_window(self.sort_filter_canvas.winfo_width() - 0, 16, anchor='ne', window=self.search_button)
        self.sort_option_button = sort_option_button(self.sort_filter_canvas, self.tool_frame, callback=self.__set_sort_by)
        self.sort_button_window = self.sort_filter_canvas.create_window(self.sort_filter_canvas.winfo_width() - 0, 16, anchor='ne', window=self.sort_option_button)
        self.filter_button = filter_option_button(self.sort_filter_canvas, self.tool_frame, callback=callback_A, apply_filter_callback=self.__filter_data)
        self.filter_button_window = self.sort_filter_canvas.create_window(self.sort_filter_canvas.winfo_width() - 0, 16, anchor='ne', window=self.filter_button)
        self.sort_filter_canvas.bind("<Configure>", self.__setup_tool_sort_filter_canvas)
        self.back_button = hover_toggle_button(self.sort_filter_canvas, back_blue, back_dark_gray, back_light_gray, anchor = 'w', callback=self.tool_frame.back_to_main_tools, is_toggle=False)
        self.tools_buttons.select(0)

    def __update_pending_approval_button_count(self, count):
        self.__pending_approvals_with_badge.update_badge(count)

    def __set_sort_by(self, selection):
        self.tool_frame.sort_by(selection)

    def __sort_by_options(self, options , selection=0):
        if self.sort_option_button:
            self.sort_option_button.set_options(options, selection)


    def __filter_data(self, filters):
        self.__db.set_project_setting(self.__db.PROJECT_SETTINGS_FILTER,json.dumps(filters))
        self.__acm_data_handler.set_objects_filter(filters)
        
    def __update_canvas(self, canvas):
        if self.sort_filter_buttons_up():
            self.sort_option_button.close(None)
            self.sort_option_button.menu_canvas = canvas
            
    def sort_filter_buttons_up(self):
        if self.sort_option_button:
            return True
        else:
            return False
        
        
    def __setup_tool_sort_filter_canvas(self, event):
        if self.__show_sort_filter_buttons:
            self.sort_filter_canvas.coords(self.search_button_window,self.sort_filter_canvas.winfo_width() - 88, 16)
            self.sort_filter_canvas.coords(self.sort_button_window,self.sort_filter_canvas.winfo_width() - 48, 16)
            self.sort_filter_canvas.coords(self.filter_button_window,self.sort_filter_canvas.winfo_width() - 8, 16)
            
        else:
            self.sort_filter_canvas.coords(self.back_button_window,8, 16)
            

     
    def show_sort_filter_buttons(self, show):
        if not self.sort_filter_buttons_up():
            return
        if show:
            self.__show_sort_filter_buttons = True
            if self.back_button_window:
                self.sort_filter_canvas.delete(self.back_button_window)
                self.tools_buttons.restore_selection(self.__tools_page_shown)
            self.filter_button_window = self.sort_filter_canvas.create_window(self.sort_filter_canvas.winfo_width() - 8, 16, anchor='ne', window=self.filter_button)
            self.sort_button_window = self.sort_filter_canvas.create_window(self.sort_filter_canvas.winfo_width() - 48, 16, anchor='ne', window=self.sort_option_button)
            self.search_button_window = self.sort_filter_canvas.create_window(self.sort_filter_canvas.winfo_width() - 88, 16, anchor='ne', window=self.search_button)
            self.search_button.show_search_entry()

        else:
            self.__show_sort_filter_buttons = False
            self.sort_filter_canvas.delete(self.search_button_window)
            self.sort_filter_canvas.delete(self.sort_button_window)
            self.sort_filter_canvas.delete(self.filter_button_window)
            self.tools_buttons.remove_selection()
            self.back_button_window = self.sort_filter_canvas.create_window(8, 16, anchor='nw', window=self.back_button)
            self.search_button.hide_search_entry()

    def __tools_canvas_callback(self, id):
        self.__tools_page_shown = id
        self.tool_frame.show_frame(self.TOOLS_PAGES[id])    


    def __tool_page_changed(self, page_name):
        """Keeps the tool side buttons matching the page raised by the tool frame."""
        for id, name in self.TOOLS_PAGES.items():
            if name != page_name:
                continue
            if self.__tools_page_shown != id or self.tools_buttons.get_selected_button() != id:
                self.__tools_page_shown = id
                self.tools_buttons.select(id, silent=True)
            return
        
        
    def __handle_left_panel_hide_button(self):

        if self.navigation_sash_position[0] < self.MIN_ALLOWABLE_NAVIGATION_FRAME: 
            self.navigation_sash_position = (self.MIN_ALLOWABLE_NAVIGATION_FRAME,self.navigation_sash_position[1])
        
        if not self.__navigation_panel_hidden :
            self.left_button.config(image=self.right_arrow)
            self.navigation_sash_position = self.pw.sash_coord(0)
            
            self.pw.sash_place(0,0,self.navigation_sash_position[1])
        else: 
            
            self.left_button.config(image=self.left_arrow)
            self.pw.update()
            self.pw.sash_place(0,self.navigation_sash_position[0],self.navigation_sash_position[1])
        self.__navigation_panel_hidden = not self.__navigation_panel_hidden
        
    def set_document_to_open(self, path,file_type=Database.DRAWING):
           if not self.__imframe or self.__imframe.path != path:
                self.__close_doc()
                self.type = file_type
                if file_type == self.__db.DRAWING or  file_type == self.__db.IMAGE : 
                    self.__setup_document_viewer(path, file_type)
                if file_type == self.__db.TEXT : 
                    self.__setup_text_viewer(path)        
                if file_type == self.__db.TABLE : 
                    self.__setup_sheet_viewer(path)
                self.navigation_frame.open_doc(path,file_type)


    def move_to_roi(self, roi_uid, pno):
        if self.__imframe:
            self.__imframe.move_to_roi(roi_uid, pno)


    def __get_open_document_path(self):
        if self.__imframe is None:
            return None
        return self.__imframe.path

    

        

    def __refresh_roi(self):
        if self.__imframe:
            self.__imframe.refresh_rois()



    def __setup_document_viewer(self, path, file_type):
        self.__imframe = SelectorTools(placeholder=self.__placeholder, path=path, db= self.__db, file_type=file_type,
                                        rect_size=self.__config.get_rect_size(),
                                        roll_size=self.__config.get_roll_size(),
                                        page_number_callback = self.page_number_callback,
                                        zoom_percentage_callback = self.zoom_percentage_callback)  # create image frame
        
        self.__imframe.setup_project(self.__project_name, self.__config)   
        self.__imframe.grid()  # show it
        self.selector_tool_buttons.select(self.__imframe.RECTANGULAR_TOOL)
        self.__imframe.get_selection_subscription(self.__pass_document_selection_subscription)
        self.__imframe.get_draw_roi_func(self.__draw_roi_loaded)
        self.__imframe.get_draw_roi_availability_func(self.__draw_roi_availability_changed)
        self.pages_navigation_button.enable()
        if file_type == self.__db.IMAGE:
            self.bookmarks_navigation_button.disable()
        else:
            self.bookmarks_navigation_button.enable()
        self.zoom_percentage.entry.configure(state=NORMAL)
        self.page_number.entry.configure(state=NORMAL)
        self.master.title(self.__default_title + ': {}'.format(self.__project_name))  # change window title
        self.page_up_button.enable()
        self.page_down_button.enable()
        self.select_tool_button.enable()
        self.hand_tool_button.enable()
        self.zoom_in_button.enable()
        self.zoom_out_button.enable()
        self.rectangular_selection_tool_button.enable()
        self.polygon_selection_tool_button.enable()
        self.selector_tool_buttons.select(2)
        
        # Enable some menus
        self.__menu.set_state(state='normal')



        self.__menu.enable_refresh_roi()


    def __setup_text_viewer(self, path):
        self.__imframe = TextSelectorTools(placeholder=self.__placeholder, path=path,
                                        project_name=self.__project_name, db= self.__db,
                                        acm_data_handler = self.__acm_data_handler,
                                        llm_manager=self.__llm_manager,
                                        rect_size=self.__config.get_rect_size(),
                                        roll_size=self.__config.get_roll_size(),
                                        page_number_callback = self.page_number_callback,
                                        zoom_percentage_callback = self.zoom_percentage_callback,
                                        config=self.__config)  # create image frame
        
                                    
        self.__imframe.grid()  # show it
        self.selector_tool_buttons.select(self.__imframe.RECTANGULAR_TOOL)
        self.__imframe.get_selection_subscription(self.__pass_document_selection_subscription)
        self.pages_navigation_button.enable()
        self.bookmarks_navigation_button.enable()
        self.zoom_percentage.entry.configure(state=NORMAL)
        self.page_number.entry.configure(state=NORMAL)
        self.master.title(self.__default_title + ': {}'.format(self.__project_name))  # change window title
        self.page_up_button.enable()
        self.page_down_button.enable()
        self.select_tool_button.enable()
        self.hand_tool_button.enable()
        self.zoom_in_button.enable()
        self.zoom_out_button.enable()
        self.rectangular_selection_tool_button.disable()
        self.polygon_selection_tool_button.disable()
        self.draw_roi_button.disable()
        self.selector_tool_buttons.select(0)
        
        # Enable some menus
        self.__menu.set_state(state='normal')

    def __setup_sheet_viewer(self, path):
             #app = SheetGUI()  # start the application  
        self.__imframe = SheetSelectorTools(placeholder=self.__placeholder
                                            ,path=path
                                            ,db= self.__db
                                            ,page_number_callback = self.page_number_callback
                                            ,zoom_percentage_callback = self.read_only_zoom_percentage_callback)  # call __init__ of the CanvasImage class
        self.__imframe.grid(row = 0, column = 0, sticky = "nswe")
        self.__imframe.get_selection_subscription(self.__pass_document_selection_subscription)
        self.pages_navigation_button.disable()
        self.bookmarks_navigation_button.enable()
        self.zoom_percentage.entry.configure(state='readonly')
        self.page_number.entry.configure(state=NORMAL)
        self.master.title(self.__default_title + ': {}'.format(self.__project_name))  # change window title
        self.select_tool_button.disable()
        self.hand_tool_button.disable()
        self.zoom_in_button.disable()
        self.zoom_out_button.disable()
        self.rectangular_selection_tool_button.disable()
        self.polygon_selection_tool_button.disable()
              
        # Enable some menus
        self.__menu.set_state(state='normal')


    def sheet_select_event(self, event = None):
        try:
            len(event)
        except:
            return
        try:
            if event[0] == "select_cell":
                self.show_selections.config(text = f"Cells: ({event[1] + 1},{event[2] + 1}) : ({event[1] + 1},{event[2] + 1})")
            elif "cells" in event[0]:
                self.show_selections.config(text = f"Cells: ({event[1] + 1},{event[2] + 1}) : ({event[3] + 1},{event[4]})")
            elif event[0] == "select_column":
                self.show_selections.config(text = f"Columns: {event[1] + 1} : {event[1] + 1}")
            elif "columns" in event[0]:
                self.show_selections.config(text = f"Columns: {event[1][0] + 1} : {event[1][-1] + 1}")
            elif event[0] == "select_row":
                self.show_selections.config(text = f"Rows: {event[1] + 1} : {event[1] + 1}")
            elif "rows" in event[0]:
                self.show_selections.config(text = f"Rows: {event[1][0] + 1} : {event[1][-1] + 1}")
            else:
                self.show_selections.config(text = "")
        except:
            self.show_selections.config(text = "")

        
    def __begin_edit_cell(self, event):
        print(event)
        
        self.frame.after(2000,self.__get_text)

    def __disable_cell_edit(self,event):
        self.sheet.get_text_editor_widget().configure(state='disabled')


    def __get_text(self):
        print(self.sheet.get_text_editor_widget().get(tk.SEL_FIRST, tk.SEL_LAST))

    def __pass_document_selection_subscription(self, subscription):
        self.tool_frame.pass_documnent_selection_subscription( subscription)    

    def __pass_document_selected_func(self):
        
        self.navigation_frame.document_selected_func(self.set_document_to_open)
        self.tool_frame.document_selected_func(self.set_document_to_open)
  
    def __new_project(self):
        """ Create a new project """

        def callback(project_name, project_description,project_id,acm_project_name, acm_project_details):
            self.new_project(project_name, project_description,project_id,acm_project_name, acm_project_details)
                
        New_Project_Wizard(callback_finish= callback)
        


    def __open_project(self):
        """ Open a project """

        def callback(project_name, project_description):
            self.open_project(project_name)

        Open_Project_Wizard(callback_finish= callback)


    def __import_project(self):
        """ Import a project """
        path = askopenfilename(title='Import project',
                                filetypes=[("Project Archive", ".aip")],
                                defaultextension=".aip",
                                   initialdir=self.__config.config_dir)
        if path == '': return

        self.import_project(path)
        
        
    
    def import_project(self, path, double_click_file_open=False):
        try:
            importing_project_name = read_project_name_from_zip(path)
        except InvalidProjectName as e:
            logging.warning('Rejected project archive %s: %s', path, e)
            messagebox.showwarning('Invalid project name', str(e))
            if double_click_file_open: self.__import_project()  # try to open figures again
            return
        except:
            messagebox.showwarning('Wrong file',
                                'Not a valid project file.')
            if double_click_file_open: self.__import_project()  # try to open figures again
            return
        
        projects = Project_File_Manager.get_all_projects()
        if importing_project_name in projects:
            if messagebox.askokcancel("Project already exists", "Do you want to replace the existing project?"):
                Project_File_Manager.delete_directory(project_dir(importing_project_name))
            else:
                return

        # noinspection PyBroadException
        try:  # check if it is a right file with figures
            import_project(path, importing_project_name)
        except Exception as e:
            messagebox.showerror('Error importing project', e)
            if double_click_file_open: self.__import_project()  # try to open figures again
            return



    def __export_project(self):
        """ Import a project """
        path = asksaveasfilename(title='Export project',
                                filetypes=[("Project Archive", ".aip")],
                                defaultextension=".aip",
                                   initialdir=self.__config.config_dir)
        if path == '': return
        # noinspection PyBroadException
        try:  # check if it is a right file with figures
            export_project(self.__project_name,path)
        except:
            messagebox.showwarning('Wrong file',
                                'Wrong figures for image: "{}"\n'.format(self.__imframe.path) +
                                'Please, select ROI figures for the current image.')
            self.__export_project()  # try to open figures again
            return
        

    def __connect_to_db(self):
        """ Connected to sql database """
        
        def callback(connection_string, use_windows_authentication, save_password):

            self.__connection_string = connection_string
            self.__set_connection_string()
            if use_windows_authentication or save_password:
                self.__config.set_connection_string(connection_string)
               

        db_conntection_form(callback=callback)

    
    def __link_to_acm_project(self,acm_project_name, acm_project_details):
        acm_project_description = acm_project_details[0]
        acm_project_id = acm_project_details[1]
        logging.info('Linking ACM Project: {} - {} with Project ID {}'.format(acm_project_name, acm_project_description,acm_project_id))
        self.__db.set_project_setting(self.__db.PROJECT_SETTINGS_ACM_PROJECT,acm_project_id)
        self.__acm_data_handler.set_project_id(acm_project_details[1])
        acm_libraries_retrieval(self.__project_name, acm_project_name)
        self.tool_frame.set_data_handler(self.__acm_data_handler)
        self.filter_button.set_data_handler(self.__acm_data_handler)
        self.__menu.enable_create_acm_project(False)


    def __link_acm_project(self):
        """ Link to ACM Project """
        

        def cancel_callback():
            pass

        Link_ACM_Project_Wizard(self.__acm_data_handler, callback_finish=self.__link_to_acm_project, callback_cancel=cancel_callback)


    def __set_connection_string(self):
        logging.info('Setting Sql Connection String: {}'.format(self.__connection_string))
        self.__acm_data_handler = ACM_Data_Handler(self.__connection_string, self.__project_missing)
        if self.tool_frame:
            self.tool_frame.set_data_handler(self.__acm_data_handler)
            self.filter_button.set_data_handler(self.__acm_data_handler)


    def __project_missing(self):
        logging.warning('ACM Project is missing: {}'.format(self.__project_name))
        self.__db.remove_project_setting(self.__db.PROJECT_SETTINGS_ACM_PROJECT)
        self.__menu.enable_create_acm_project(True)
        

    def open_project(self, project_name):
        self.__close_doc()
        self.tool_frame.reset()

        logging.info('Opening project: {}'.format(project_name))
        self.__project_name = project_name
        self.__db = Database(self.__project_name)
        self.__db.subscribe_unapproved_text_link_update(self.delayed_update_pending_approvals_with_badge)
        self.navigation_frame.define_project(self.__project_name, self.__db, self.__acm_data_handler)
        self.tool_frame.define_project(self.__project_name, self.__db, self.__config)
        logging.info('Getting project setting from internal project database')
        project_id = self.__db.get_project_setting(self.__db.PROJECT_SETTINGS_ACM_PROJECT)
        filters = self.__db.get_project_setting(self.__db.PROJECT_SETTINGS_FILTER)
        if self.__acm_data_handler:
            self.__acm_data_handler.initialize()
            self.__acm_data_handler.set_objects_filter(filters)
            if project_id:
                self.__menu.enable_create_acm_project(False)
            else:
                self.__menu.enable_create_acm_project(True)
            self.__acm_data_handler.set_project_id(project_id)
            acm_project_name = self.__acm_data_handler.get_project_name()
            if acm_project_name:
                acm_libraries_retrieval(self.__project_name, acm_project_name)
            self.tool_frame.set_data_handler(self.__acm_data_handler)
            self.filter_button.set_data_handler(self.__acm_data_handler)
            
        else:
            self.__menu.enable_create_acm_project(True)
        self.__config.set_recent_project(self.__project_name)  # save project into config
        logging.info('Opened project: {}'.format(project_name))
        self.update_pending_approvals_button()


    def update_pending_approvals_button(self):
        count = self.__db.get_unapproved_text_link_count()
        if self.__pending_approvals_with_badge:
            self.after(0, self.__update_pending_approval_button_count, count)
            


    def delayed_update_pending_approvals_with_badge(self):
        # Called from DB notifier fan-out which may execute on worker threads
        # (e.g. save_bulk_unapproved_text_links, __setup_regex_template_threaded,
        # LLM ThreadPoolExecutor). Widget.after is not thread-safe, so we hop
        # back to the Tk main thread via a virtual event with when='tail'.
        try:
            self.event_generate('<<PendingApprovalsChanged>>', when='tail')
        except tk.TclError:
            # Widget was destroyed while a worker thread was still writing.
            pass

    def __on_pending_approvals_changed(self, _event=None):
        # Runs on the Tk main thread. Debounce rapid bursts of DB writes so we
        # only issue one DB read and one badge redraw per quiet 200 ms window.
        if self.__pending_approvals_with_badge_timer:
            self.after_cancel(self.__pending_approvals_with_badge_timer)
        self.__pending_approvals_with_badge_timer = self.after(200, self.update_pending_approvals_button)


    def new_project(self, project_name, project_description, project_id ,acm_project_name, acm_project_details):

        self.__close_doc()
        self.tool_frame.reset()
        self.pages_navigation_button.disable()
        self.bookmarks_navigation_button.disable()

        if project_name:
            self.__project_name = Project_File_Manager.create_project(project_name, project_description,get_version_number())
            self.__db = Database(self.__project_name)
            self.__db.subscribe_unapproved_text_link_update(self.delayed_update_pending_approvals_with_badge)
            self.__project_description = project_description
            self.__db.set_project_setting(self.__db.PROJECT_SETTINGS_DESCRIPTION, self.__project_description)
            self.navigation_frame.define_project(self.__project_name, self.__db, self.__acm_data_handler)
            self.tool_frame.define_project(self.__project_name, self.__db,self.__config)
            logging.info('New project: {}'.format(project_name))
            self.__config.set_recent_project(self.__project_name)  # save project into config

            if self.__acm_data_handler:
                self.__acm_data_handler.initialize()

            if acm_project_name and self.__acm_data_handler:
                filters = self.__db.get_project_setting(self.__db.PROJECT_SETTINGS_FILTER)
                self.__acm_data_handler.set_objects_filter(filters)
                self.__link_to_acm_project(acm_project_name, acm_project_details)
                self.__menu.enable_create_acm_project(False)
            else:
                self.__menu.enable_create_acm_project(True)

            self.update_pending_approvals_button()

        else: messagebox.showerror('Error', 'Invalid project name')



    def __close_doc(self):
        """ Close image """
        if self.__imframe:
            # if len(self.__imframe.roi_dict):
            self.__imframe.destroy()
            self.__imframe = None
            self.master.title(self.__default_title)  # set default window title
            # self.__menu.set_state(state='disabled')  # disable some menus

    def __check_roi(self):
        """ Check if there are ROI on the image """
        #if self.__imframe and len(self.__imframe.roi_dict):  # there are ROI on the image
        #    return True
        #return False  # if there are no figures
        messagebox.showwarning("Future feature",'Coming soon in later versions.')

    
    def __open_figures(self):
        """ Open figures for the current image from file """
        if self.__imframe:
            path = askopenfilename(title='Open rectangles for the current image',
                                   initialdir=self.__config.config_dir)
            if path == '': return
            # noinspection PyBroadException
            try:  # check if it is a right file with figures
                open_figures(self.__imframe, path)
            except:
                messagebox.showwarning('Wrong file',
                                    'Wrong figures for image: "{}"\n'.format(self.__imframe.path) +
                                    'Please, select ROI figures for the current image.')
                self.__open_figures()  # try to open figures again
                return

    def __start_export_images(self):
        """ Exports the images from Static Graphic templates """
        path = askdirectory(title='Export images')

        if path == '': return
        texbox_progressbar_window(export_images, 'Export All Images', self.__db, path)



    def __start_export_reduced_images(self):
        """ Exports the images from Static Graphic templates """
        output_path = askdirectory(title='Export images')

        if output_path == '': return
        texbox_progressbar_window(export_reduced_images, 'Export Reduced Images', self.__db,self.__config, output_path)
    
        

    def __extract_lines(self):
        messagebox.showwarning("Extract Lines feature",'Coming soon in later versions.')

    def __create_displays(self):

        texbox_progressbar_window(build_pages, 'Build Pages', self.__acm_data_handler, self.__config, self.__db
                                  , self.__project_name)
        

    def __create_alarms(self):

        if not messagebox.askokcancel("Build Alarms", "This will create new Alarm Groups. Do you want to continue?"):
            return

        texbox_progressbar_window(create_alarms, 'Build Alarms',self.__acm_data_handler, self.__config, self.__db
                                  , self.__project_name)
        
        

    def __confirm_build_without_displays(self, title):
        """ Warn when the project has no HMI Displays, since the build will invent one
            per scanned page instead of using displays the user laid out. """
        if self.__db.get_all_hmi_displays():
            return True

        if not find_pages_needing_hmi_displays(self.__db):
            messagebox.showwarning(
                title,
                'No HMI Displays have been defined and no scanned drawing page contains '
                'control modules or static graphics to build one from.\n\n'
                'Scan a drawing or define an HMI Display first.')
            return False

        return messagebox.askyesno(
            title,
            'No HMI Displays have been defined for this project.\n\n'
            'A display will be created automatically for each scanned drawing page that '
            'contains control modules or static graphics.\n\n'
            'Generate displays anyway?',
            icon='warning')

    def __build_hmi_xml_and_images(self):
        """ Build HMI → XML and Images: run the HMI build and open the
            BuildDisplay window in file-only mode. Export All Displays writes
            the XML files and images to the export path but does **not**
            invoke SEAddComponent.exe (that is the "View Designer" flow). """
        if not self.__confirm_build_without_displays('Build HMI → XML and Images'):
            return
        output_path = None
        texbox_progressbar_window(start_build_hmi, 'Build HMI → XML and Images',
                                  self.__acm_data_handler, self.__config, self.__db,
                                  self.__project_name, output_path, auto_close=True)
        BuildDisplay(self.master, self.__db, self.__acm_data_handler, self.__project_name, self.__config, output_path
                     ,go_to_document_page_func=self.go_to_page_callback,set_document_to_open_func=self.set_document_to_open
                     ,move_to_document_roi_func=self.move_to_roi
                     ,run_seadd_component=False)

    def __build_hmi_view_designer(self):
        """ Build HMI → View Designer: run the HMI build and open the
            BuildDisplay window in push mode. Export All Displays writes
            the XML files and images, prompts the user to pick the target
            FactoryTalk View SE application (see ``FTViewAppPicker``),
            and then invokes SEAddComponent.exe to push the components
            into that application. Other SEAddComponent args come from
            the SE Add Component Tool section in Settings. """
        if not self.__confirm_build_without_displays('Build HMI → View Designer'):
            return
        output_path = None
        texbox_progressbar_window(start_build_hmi, 'Build HMI → View Designer',
                                  self.__acm_data_handler, self.__config, self.__db,
                                  self.__project_name, output_path, auto_close=True)
        BuildDisplay(self.master, self.__db, self.__acm_data_handler, self.__project_name, self.__config, output_path
                     ,go_to_document_page_func=self.go_to_page_callback,set_document_to_open_func=self.set_document_to_open
                     ,move_to_document_roi_func=self.move_to_roi
                     ,run_seadd_component=True)

    def __build_plc(self):
        output_path = askdirectory(title='Build PLC')

        if output_path == '': return
        texbox_progressbar_window(start_build_plc, 'Build PLC',self.__acm_data_handler, self.__config, self.__db
                                  , self.__project_name, output_path)

    def __build_plc_logix_designer(self):
        """ Build PLC → Logix Designer: run the ACM build to produce the
            L5X, then convert it to an .ACD in the same folder using the
            Rockwell Logix Designer Python SDK. The .ACD lands next to
            the L5X as ``<controller_name>.ACD``. """
        if not is_sdk_available():
            messagebox.showerror(
                'Logix Designer SDK not installed',
                sdk_install_hint(self.__config.get_logix_designer_sdk_wheel_dir()))
            return
        output_path = askdirectory(title='Build PLC → Logix Designer')
        if output_path == '': return
        texbox_progressbar_window(push_build_output_to_logix_designer,
                                  'Build PLC → Logix Designer',
                                  self.__acm_data_handler, self.__config, self.__db,
                                  self.__project_name, output_path)

    def __build_plc_logix_echo(self):
        """ Build PLC → Logix Echo: run the ACM build to produce the
            L5X, convert it to an .ACD via the Logix Designer SDK, then
            create/download the ACD into a controller on the local
            FactoryTalk Logix Echo service via ``ftecho_sdk``.

            Both SDKs must be pip-installed; missing wheels are surfaced
            through their respective install-hint error dialogs. """
        if not is_sdk_available():
            messagebox.showerror(
                'Logix Designer SDK not installed',
                sdk_install_hint(self.__config.get_logix_designer_sdk_wheel_dir()))
            return
        if not is_logix_echo_sdk_available():
            messagebox.showerror(
                'FactoryTalk Logix Echo SDK not installed',
                logix_echo_sdk_install_hint(self.__config.get_logix_echo_sdk_wheel_dir()))
            return
        output_path = askdirectory(title='Build PLC → Logix Echo')
        if output_path == '': return
        texbox_progressbar_window(push_build_output_to_logix_echo,
                                  'Build PLC → Logix Echo',
                                  self.__acm_data_handler, self.__config, self.__db,
                                  self.__project_name, output_path)
        
    def __create_acm_project(self):

        if not self.__acm_data_handler:
            messagebox.showwarning('Not connected to ACM',
                                    'Go to File > Connect Database to connect an ACM database.')
            return

        project_library_array = self.__config.get_acm_project()

        if project_library_array is None:
            raise ValueError('Project Library not set in Settings. Please go Tools > Setting to set the project library.')

        acm_console = ACM_Console(self.__project_name,self.__acm_data_handler,self.__db, self.__config)
        
        texbox_progressbar_window(acm_console.create_acm_project,'Create ACM Project'
                                    , project_library_array[0]
                                    , project_library_array[1]
                                    , project_library_array[2]
                                    , project_library_array[3], self.__link_to_acm_project)
                                        
        

    def __create_acm_objects(self):
        acm_console = ACM_Console(self.__project_name,self.__acm_data_handler,self.__db, self.__config)

        def done_function():
            self.__acm_data_handler.refresh_all_data()
        
        texbox_progressbar_window(acm_console.create_assigned_acm_objects, 'Create ACM Objects',
                                  done_function=done_function)
        
        




    def __about(self):
        messagebox.showinfo('About',' Solutions Project Accelerator Version: '+ get_version_number())

    def __settings(self):
        settings(self.__config, self.__acm_data_handler)

    def __maybe_prompt_llm_first_run(self):
        """
        Show a one-off hint if the app has no reachable LLM backend.

        Rather than guessing "internal vs external" from filesystem
        markers, we wait up to ~60 s for the resolved backend to actually
        finish its handshake:

            * Enterprise gateway (optional ``genai_bridge`` plugin) —
              background token/cert fetch succeeded.
            * Public OpenAI path — user-supplied key means construction
              succeeded.
            * Ollama path — bundled or remote client instantiated.

        If ``UnifiedInference.is_backend_ready()`` becomes True during the
        grace period, no modal appears. If not, we surface the hint so an
        external (or misconfigured) install knows where to configure.

        The modal itself is only relevant when the user has NOT already
        picked a provider and has NO stored OpenAI key — both of those
        short-circuit the check up-front.
        """
        try:
            settings_dict = self.__config.get_llm_inference_settings()
        except Exception:
            settings_dict = {}
        if (settings_dict.get('provider') or '').strip():
            return  # user already picked a provider
        if has_openai_key():
            return  # a key is available even if provider is Auto

        # Grace-period polling. Total budget ~60 s at 2 s intervals so a
        # slow VPN / Zscaler startup doesn't false-fire.
        state = {'attempts_left': 30}

        def _poll():
            try:
                if self.__llm_manager.is_backend_ready():
                    return  # backend came online in time — silent success

                state['attempts_left'] -= 1
                if state['attempts_left'] > 0:
                    self.master.after(2000, _poll)
                    return

                # Grace period elapsed without a working backend. Show the
                # hint. If the backend check hasn't even *finished* yet
                # (e.g. MSAL still hanging), soften the wording so it's a
                # heads-up rather than a definitive failure.
                check_done = self.__llm_manager.has_backend_check_completed()
                if check_done:
                    body = (
                        'No LLM backend is available for this install.\n\n'
                        'Open Tools → Settings → LLM Inference to enter an '
                        'OpenAI API key or point at an Ollama server.'
                    )
                else:
                    body = (
                        'LLM backend is still initializing after 60s.\n\n'
                        'Open Tools → Settings → LLM Inference to configure a '
                        'public OpenAI key or an Ollama server.'
                    )
                messagebox.showinfo(
                    'LLM inference not configured',
                    body,
                    master=self.master,
                )
            except Exception:
                # Never let a UI hint break app startup.
                pass

        try:
            # First poll after 2 s so the main window is drawn and the
            # background auth thread has had a chance to run at least once.
            self.master.after(2000, _poll)
        except Exception:
            pass

    def __open_configured_url(self, url, env_var):
        """Open ``url``, or explain which variable to set when it is blank."""
        if url:
            webbrowser.open(url)
            return
        messagebox.showinfo(
            'Link not configured',
            f'No URL is configured for this action.\n\nSet the {env_var} '
            'environment variable to enable it.',
            master=self.master,
        )

    def __documentation(self):
        """Open the offline documentation site if bundled, else the online URL."""
        local_index = _resolve_bundled_docs_index()
        if local_index:
            uri = "file:///" + local_index.replace("\\", "/")
            logging.info(f"Opening bundled documentation: {uri}")
            webbrowser.open(uri)
            return
        logging.info("Bundled documentation not found; falling back to online URL.")
        self.__open_configured_url(DOCUMENTATION_URL, 'SPA_DOCUMENTATION_URL')

    def __get_help(self):
        self.__open_configured_url(GET_HELP_URL, 'SPA_GET_HELP_URL')

    def __join_team(self):
        self.__open_configured_url(JOIN_TEAM_URL, 'SPA_JOIN_TEAM_URL')

    def destroy(self):
        """ Destroy the main frame object and release all resources """
        if not self.__navigation_panel_hidden:
            self.__config.set_navigation_sash(self.pw.sash_coord(0))
        else:
            self.__config.set_navigation_sash(self.navigation_sash_position)
        self.__config.set_is_navigation_panel_hidden(self.__navigation_panel_hidden)
        self.__config.set_opened_project(self.__project_name)
        self.__config.set_tool_sash(self.pw.sash_coord(1))
        self.__close_doc()
        self.__config.destroy()
        self.__db.close_db()
        logging.info('Close GUI')
        self.quit()


    def __set_up_theme(self):
        style = ttk.Style(self.master)
        # custom indicator images
        im_open = PIL.Image.new('RGBA', (15, 15), '#00000000')
        im_empty = PIL.Image.new('RGBA', (15, 15), '#00000000')
        draw = PIL.ImageDraw.Draw(im_open)
        draw.line([(0, 4), (7, 11), (14, 4) ], fill=(150,150,150,255),width=2)
        im_close= im_open.rotate(90)
        
        self.img_open = PIL.ImageTk.PhotoImage(im_open, name='tree_img_open', master=self.master)
        self.img_close = PIL.ImageTk.PhotoImage(im_close, name='tree_img_close', master=self.master)
        self.img_empty = PIL.ImageTk.PhotoImage(im_empty, name='tree_img_empty', master=self.master)
        self.image_dict = {}
        
        if 'Treeitem.myindicator' not in str(style.layout("Treeview.Item")):
            # custom indicator
            style.element_create('Treeitem.myindicator',
                                 'image', 'tree_img_close', ('user1', '!user2', 'tree_img_open'), ('user2', 'tree_img_empty'),
                                 sticky='w', width=15, padding=12)
        # replace Treeitem.indicator by custom one
        style.layout('Treeview.Item',
        [('Treeitem.padding',
          {'sticky': 'nswe',
           'children': [('Treeitem.myindicator', {'side': 'left', 'sticky': ''}),
            ('Treeitem.image', {'side': 'left', 'sticky': ''}),
            #('Treeitem.focus', {'side': 'left', 'sticky': '','children':[
              ('Treeitem.text', {'side': 'left', 'sticky': ''})
              #]})
            ]
          })]
        )
        style.layout("Treeview", [
            ('Treeview.treearea', {'sticky': 'nswe'})
        ])
        style.map('Treeview', background=[("selected","#E3E3E3")], foreground=[("selected","#101010")])
        style.configure("Treeview", font=(None, 10))
        style.configure("Treeview.Heading", font=(None, 10))
        style.configure('Treeview', rowheight=30) 
        style.configure('Treeview', background='#F5F5F5')

    def __on_focus_in(self, _):
        pass

    def __on_focus_out(self, _):
        pass

