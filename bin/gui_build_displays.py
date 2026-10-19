import logging
import os
import re
import subprocess
import tempfile
import time
from threading import Thread
import tkinter as tk
from tkinter import messagebox
from tkinter.filedialog import askdirectory
import xml.etree.ElementTree as ET

from sqlalchemy import func

from bin.logic_gfx_file_editor import GfxFileEditor

try: 
    from bin.logic_internal_database import Database
    from bin.logic_acm_data_handler import ACM_Data_Handler
    from bin.gui_elements import loading_animation, hover_toggle_button, button_array, rounded_image_button
    from bin.gui_elements import custom_entry
    from bin.gui_ftview_app_picker import FTViewAppPicker
    from bin.gui_base64_icons import page_up_blue, page_up_dark_gray, page_up_light_gray
    from bin.gui_base64_icons import page_down_blue, page_down_dark_gray, page_down_light_gray
    from bin.gui_base64_icons import (left_align_blue, left_align_dark_gray, left_align_light_gray,
                                    horizontal_center_align_blue, horizontal_center_align_dark_gray, horizontal_center_align_light_gray,
                                    right_align_blue, right_align_dark_gray, right_align_light_gray,
                                    top_align_blue, top_align_dark_gray, top_align_light_gray,
                                    vertical_center_align_blue, vertical_center_align_dark_gray, vertical_center_align_light_gray,
                                    bottom_align_blue, bottom_align_dark_gray, bottom_align_light_gray,
                                    select_tool_blue, select_tool_dark_gray, select_tool_light_gray,
                                    hand_tool_blue, hand_tool_dark_gray, hand_tool_light_gray,
                                    zoom_in_blue, zoom_in_dark_gray, zoom_in_light_gray,
                                    zoom_out_blue, zoom_out_dark_gray, zoom_out_light_gray,
                                    add_anchor_blue, add_anchor_dark_gray, add_anchor_light_gray,
                                    horizontal_distribute_blue, horizontal_distribute_dark_gray, horizontal_distribute_light_gray,
                                    vertical_distribute_blue, vertical_distribute_dark_gray, vertical_distribute_light_gray)
    from bin.gui_base64_icons import generate_displays_dark_gray, generate_display_dark_gray
    from bin.gui_process_diagrams import ProcessDisplayCanvas
except ImportError as e:
    from logic_internal_database import Database
    from logic_acm_data_handler import ACM_Data_Handler
    from gui_elements import loading_animation, hover_toggle_button, button_array, rounded_image_button
    from gui_elements import custom_entry
    from gui_ftview_app_picker import FTViewAppPicker
    from gui_base64_icons import page_up_blue, page_up_dark_gray, page_up_light_gray
    from gui_base64_icons import page_down_blue, page_down_dark_gray, page_down_light_gray
    from gui_base64_icons import (left_align_blue, left_align_dark_gray, left_align_light_gray,
                                    horizontal_center_align_blue, horizontal_center_align_dark_gray, horizontal_center_align_light_gray,
                                    right_align_blue, right_align_dark_gray, right_align_light_gray,
                                    top_align_blue, top_align_dark_gray, top_align_light_gray,
                                    vertical_center_align_blue, vertical_center_align_dark_gray, vertical_center_align_light_gray,
                                    bottom_align_blue, bottom_align_dark_gray, bottom_align_light_gray,
                                    select_tool_blue, select_tool_dark_gray, select_tool_light_gray,
                                    hand_tool_blue, hand_tool_dark_gray, hand_tool_light_gray,
                                    zoom_in_blue, zoom_in_dark_gray, zoom_in_light_gray,
                                    zoom_out_blue, zoom_out_dark_gray, zoom_out_light_gray,
                                    add_anchor_blue, add_anchor_dark_gray, add_anchor_light_gray,
                                    horizontal_distribute_blue, horizontal_distribute_dark_gray, horizontal_distribute_light_gray,
                                    vertical_distribute_blue, vertical_distribute_dark_gray, vertical_distribute_light_gray)
    from gui_base64_icons import generate_displays_dark_gray, generate_display_dark_gray
    from gui_process_diagrams import ProcessDisplayCanvas



class BuildDisplay:
    """Main GUI for building HMI displays
    
    This class now supports multiple ProcessDisplayCanvas instances, one for each display.
    Instead of changing pages within a single canvas, it creates separate canvases and 
    uses pack/pack_forget to switch between them based on self.__current_page.
    """

    CURSOR_TOOL = 0
    HAND_TOOL = 1
    ADD_ANCHOR_TOOL = 2
    
    def __init__(self, parent, internal_db: Database, acm_data_handler, project_name, config, export_path
                 , go_to_document_page_func=None, set_document_to_open_func=None, move_to_document_roi_func=None
                 , single_display_name=None, run_seadd_component=False):
        """Initialize the Build Display window"""
        self.__win = tk.Toplevel(parent)
        self.__display_canvases = []  # List of multiple canvas instances
        self.__display_names = []     # List of display names corresponding to canvases
        self.__current_loading_index = 0  # Index for sequential canvas loading
        self.__busy_canvas = None
        self.__placeholder = None
        self.__page_number = None
        self.__total_pages = 0
        self.__current_page = 1
        self.__export_path = export_path
        self.__internal_db = internal_db
        self.__acm_data_handler = acm_data_handler
        self.__project_name = project_name
        self.__config = config
        self.__go_to_document_page_func = go_to_document_page_func
        self.__set_document_to_open_func = set_document_to_open_func
        self.__move_to_document_roi_func = move_to_document_roi_func
        self.__single_display_name = single_display_name  # If set, only load this display
        # When True, Export All Displays invokes SEAddComponent.exe after
        # writing the XML/images ("Build HMI → View Designer" flow).
        # When False (default), the export writes files only ("Build HMI
        # → XML and Images" flow and single-display rebuilds).
        self.__run_seadd_component = bool(run_seadd_component)
        # Populated by the FTView SE application picker shown right
        # before the export kicks off (see __generate_all_displays).
        # When the user cancels the picker these stay None and
        # __maybe_run_seadd_component_tool silently skips the push.
        self.__seadd_selected_app_name = None
        self.__seadd_selected_app_type = None
        # SEAddComponent lifecycle tracking. Set to True right before
        # the subprocess is spawned and back to False on completion,
        # timeout, or launch failure. __check_generation_complete uses
        # this to keep the busy canvas up until the push is finished.
        # __seadd_result holds the outcome dict consumed by the same
        # poller to show the final success/failure messagebox.
        self.__seadd_in_progress = False
        self.__seadd_result = None
        # Last stdout/stderr line streamed from SEAddComponent.exe;
        # rendered into the busy canvas by _update_seadd_progress.
        self.__seadd_last_line = ""
        
        self.__setup_window()
        self.__setup_keyboard_bindings()
        
        self.__win.protocol("WM_DELETE_WINDOW", self.close)
        
    def set_move_to_document_roi_func(self, func):
        self.__move_to_document_roi_func = func

    def __setup_window(self):
        """Set up the main window"""
        self.__win.title("Build HMI Display")
        self.__win.geometry('1289x779+256+89')
        self.__win.minsize(1289, 779)
        this_dir = os.path.dirname(os.path.realpath(__file__))
        self.__win.iconbitmap(os.path.join(this_dir, 'logo.ico'))

        # Create menu bar
        self.__setup_menu_bar()

        self.__win.rowconfigure(0, weight=1)
        self.__win.columnconfigure(0, weight=1)

        frame = tk.Frame(self.__win, bg='white')
        frame.grid(row=0, column=0, sticky='nsew')
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=0)
        frame.rowconfigure(1, weight=1)

        upper_frame = tk.Frame(frame, height=50, width=770, bg='white')
        upper_frame.grid(row=0, column=0, sticky='nsew')
        upper_frame.columnconfigure(0, weight=1)
        upper_frame.rowconfigure(0, weight=0)
        self.__setup_upper_frame(upper_frame)

        self.__placeholder = tk.Frame(frame, height=410, width=770)
        self.__placeholder.grid(row=1, column=0, sticky='nsew')
        self.__placeholder.columnconfigure(0, weight=1)
        self.__placeholder.rowconfigure(0, weight=1)
        self.__placeholder.config(background="#F5F5F5")
        
        self.__setup_display_canvas()
        self.__win.update()

    def __setup_menu_bar(self):
        """Set up the menu bar"""
        menu_bar = tk.Menu(self.__win)
        self.__win.config(menu=menu_bar)
        
        # File menu
        file_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Export Display", command=self.__menu_build_display)
        file_menu.add_command(label="Export All Displays", command=self.__menu_build_all_displays)
        file_menu.add_separator()
        file_menu.add_command(label="Remove All Material Lines", command=self.__menu_remove_all_material_lines)
        file_menu.add_command(label="Remove All Signal Lines", command=self.__menu_remove_all_signal_lines)
        file_menu.add_command(label="Remove All Lines", command=self.__menu_remove_all_lines)
        file_menu.add_separator()
        file_menu.add_command(label="Reset Display", command=self.__menu_reset_display)
        file_menu.add_command(label="Reset All Displays", command=self.__menu_reset_all_displays)
        file_menu.add_separator()
        file_menu.add_command(label="Show Drawing", command=self.__menu_show_drawing)
        file_menu.add_command(label="Toggle Show Object Names", accelerator="Ctrl+T", command=self.__menu_toggle_show_object_names)
        
        
        # Edit menu
        edit_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", accelerator="Ctrl+Z", command=self.__menu_undo)
        edit_menu.add_command(label="Redo", accelerator="Ctrl+Shift+Z", command=self.__menu_redo)
        


    def __setup_upper_frame(self, parent):
        """Set up the upper frame with navigation and buttons"""
        self.canvas = tk.Canvas(parent, height=60, width=770, background="white", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=1)
        
        # Bind canvas configuration for dynamic layout
        self.canvas.bind("<Configure>", self.__configure_buttons_canvas)
        
        # Create the page number entry
        self.__page_number = custom_entry(self.canvas, 0, 0, enbale_rect=False, width=40, 
                                          size=9, enable_line=False, 
                                          focus_out_callback=self.__page_number_edit_callback)
        self.__page_number.entry.configure(validate="key", justify=tk.RIGHT)
        self.__page_number.entry['validatecommand'] = (self.__page_number.entry.register(self.__check_page_number), '%P', '%d')

        self.zoom_percentage = custom_entry(self.canvas,0,0,enbale_rect=False,width=40,size=9,enable_line=False,
                                            focus_out_callback=self.__zoom_percentage_edit_callback)
        self.zoom_percentage.entry.configure(validate="key", justify=tk.RIGHT)
        self.zoom_percentage.entry['validatecommand'] = (self.zoom_percentage.entry.register(self.__check_zoom_percentage),'%P','%d')

    def __configure_buttons_canvas(self, event):
        """Configure the buttons on the canvas when resized"""
        self.canvas.delete("all")
        w, _ = event.width, event.height
        
        # Page navigation buttons
        self.__page_up_button = hover_toggle_button(self.canvas, page_up_blue, page_up_dark_gray, page_down_light_gray, 
                                                 anchor='w', is_toggle=False, callback=self.__page_down)
        self.canvas.create_window(10, 16, anchor='nw', window=self.__page_up_button)
        
        self.__page_down_button = hover_toggle_button(self.canvas, page_down_blue, page_down_dark_gray, page_down_light_gray, 
                                                   anchor='w', is_toggle=False, callback=self.__page_up)
        self.canvas.create_window(50, 16, anchor='nw', window=self.__page_down_button)
        
        # Page number entry
        self.__page_number.draw(x=70, y=1)
        
        # Total pages text
        self.__total_page_text = self.canvas.create_text(130, 20, fill="#2F2F2F", font="Arial 9",
                                                      text=f"/ {self.__total_pages}", anchor='nw')
        
        # Divider line
        self.canvas.create_line(170, 12, 170, 50, fill="#D5D5D5", width=2)

        self.select_tool_button = hover_toggle_button(self.canvas, select_tool_blue, select_tool_dark_gray, select_tool_light_gray
                                        , anchor = 'w', is_toggle=False, tool_tip_text='Select tool')
        self.canvas.create_window(190, 16, anchor='nw', window=self.select_tool_button)
        self.hand_tool_button = hover_toggle_button(self.canvas, hand_tool_blue, hand_tool_dark_gray, hand_tool_light_gray
                                        , anchor = 'w', is_toggle=False, tool_tip_text='Move tool')
        self.canvas.create_window(230, 16, anchor='nw', window=self.hand_tool_button)
        self.add_anchor_button = hover_toggle_button(self.canvas, add_anchor_blue, add_anchor_dark_gray, add_anchor_light_gray
                                        , anchor = 'w', is_toggle=False, tool_tip_text='Add anchor',)
        self.canvas.create_window(270, 16, anchor='nw', window=self.add_anchor_button)
        self.selector_tool_buttons = button_array([self.select_tool_button,
                                                    self.hand_tool_button,
                                                    self.add_anchor_button],
                                                    self.__selector_tool_chosen)
        self.zoom_in_button = hover_toggle_button(self.canvas, zoom_in_blue, zoom_in_dark_gray, zoom_in_light_gray, anchor = 'w',
                                        is_toggle=False, callback=self.zoom_in, tool_tip_text='Zoom in')
        self.canvas.create_window(310, 16, anchor='nw', window=self.zoom_in_button)
        
        self.zoom_out_button = hover_toggle_button(self.canvas, zoom_out_blue, zoom_out_dark_gray, zoom_out_light_gray, anchor = 'w',
                                        is_toggle=False, callback=self.zoom_out, tool_tip_text='Zoom out')
        self.canvas.create_window(350, 16, anchor='nw', window=self.zoom_out_button)
        
        self.zoom_percentage.draw(x = 380, y = 1)

        self.canvas.create_text(440,20,fill="#2F2F2F",font="Arial 9",
                        text=" %", anchor='nw')

        # Divider line
        self.canvas.create_line(470, 12, 470, 50, fill="#D5D5D5", width=2)

        
        self.__left_align_button = hover_toggle_button(self.canvas, left_align_blue, left_align_dark_gray, left_align_light_gray,
                                                      anchor='w', is_toggle=False, callback=self.__left_align, 
                                                      tool_tip_text='Align left')
        self.canvas.create_window(490, 16, anchor='nw', window=self.__left_align_button)
        self.__horizontal_center_align_button = hover_toggle_button(self.canvas, horizontal_center_align_blue, horizontal_center_align_dark_gray, horizontal_center_align_light_gray,
                                                        anchor='w', is_toggle=False, callback=self.__horizontal_center_align,
                                                        tool_tip_text='Align center')
        self.canvas.create_window(530, 16, anchor='nw', window=self.__horizontal_center_align_button)
        self.__right_align_button = hover_toggle_button(self.canvas, right_align_blue, right_align_dark_gray, right_align_light_gray,
                                                        anchor='w', is_toggle=False, callback=self.__right_align,
                                                        tool_tip_text='Align right')
        self.canvas.create_window(570, 16, anchor='nw', window=self.__right_align_button)
        self.__top_align_button = hover_toggle_button(self.canvas, top_align_blue, top_align_dark_gray, top_align_light_gray,
                                                        anchor='w', is_toggle=False, callback=self.__top_align,
                                                        tool_tip_text='Align top')
        self.canvas.create_window(610, 16, anchor='nw', window=self.__top_align_button)
        self.__vertical_center_align_button = hover_toggle_button(self.canvas, vertical_center_align_blue, vertical_center_align_dark_gray, vertical_center_align_light_gray,
                                                        anchor='w', is_toggle=False, callback=self.__vertical_center_align,
                                                        tool_tip_text='Align center')
        self.canvas.create_window(650, 16, anchor='nw', window=self.__vertical_center_align_button)
        self.__bottom_align_button = hover_toggle_button(self.canvas, bottom_align_blue, bottom_align_dark_gray, bottom_align_light_gray,
                                                        anchor='w', is_toggle=False, callback=self.__bottom_align,
                                                        tool_tip_text='Align bottom')
        self.canvas.create_window(690, 16, anchor='nw', window=self.__bottom_align_button)
        self.__horizontal_distribute_button = hover_toggle_button(self.canvas, horizontal_distribute_blue, horizontal_distribute_dark_gray, horizontal_distribute_light_gray,
                                                        anchor='w', is_toggle=False, callback=self.__horizontal_distribute,
                                                        tool_tip_text='Distribute horizontally')
        self.canvas.create_window(730, 16, anchor='nw', window=self.__horizontal_distribute_button)
        self.__vertical_distribute_button = hover_toggle_button(self.canvas, vertical_distribute_blue, vertical_distribute_dark_gray, vertical_distribute_light_gray,
                                                        anchor='w', is_toggle=False, callback=self.__vertical_distribute,
                                                        tool_tip_text='Distribute vertically')
        self.canvas.create_window(770, 16, anchor='nw', window=self.__vertical_distribute_button)


        # Divider line
        self.canvas.create_line(810, 12, 810, 50, fill="#D5D5D5", width=2)

        
        # Generate buttons
        self.generate_display_dark_gray = tk.PhotoImage(data=generate_display_dark_gray)
        self.__generate_display_button = rounded_image_button(self.canvas, w - 455, 4, 10, text="EXPORT DISPLAY", icon_image=self.generate_display_dark_gray, borderwidth=1, 
                    width=200, tags= ('upload',), callback=self.__generate_current_display, fixed_width_offset=-26)
        self.__generate_display_button.draw()
        

        self.generate_displays_dark_gray = tk.PhotoImage(data=generate_displays_dark_gray)
        self.__generate_all_button = rounded_image_button(self.canvas, w - 255, 4, 10, text="EXPORT ALL DISPLAYS", icon_image=self.generate_displays_dark_gray, borderwidth=1, 
                    width=240, tags= ('upload',), callback=self.__generate_all_displays, fixed_width_offset=-45)
        self.__generate_all_button.draw()


    def __go_to_drawing_roi(self, roi_uid,pno,path,doc_type=Database.DRAWING):

        self.__go_to_document_path(path,doc_type)
        self.__move_to_roi(roi_uid, pno)


    def __go_to_drawing_page(self, pno, path, doc_type=Database.DRAWING):
        self.__go_to_document_path(path,doc_type)
        self.__go_to_document_page_func(pno)


    def __move_to_roi(self, roi_uid, pno):    
        if self.__move_to_document_roi_func and roi_uid and pno is not None:
            self.__move_to_document_roi_func(roi_uid, pno)


    def __go_to_document_path(self, path, doc_type=Database.DRAWING):
        if self.__set_document_to_open_func:
            self.__set_document_to_open_func(path,doc_type)


    def __selector_tool_chosen(self, tool):
        """Handle the selection of a tool"""
        print(f"Tool chosen: {tool}")
        
        # Inform all display canvases about the selected tool
        tool_mode = None
        if tool == self.CURSOR_TOOL:
            tool_mode = "select"
        elif tool == self.HAND_TOOL:
            tool_mode = "pan"
        elif tool == self.ADD_ANCHOR_TOOL:
            tool_mode = "free_anchor"
            
        if tool_mode:
            # Apply to all canvases so the tool mode persists when switching
            for canvas in self.__display_canvases:
                canvas.set_tool_mode(tool_mode)
            


    def __setup_display_canvas(self):
        """Set up multiple display canvases based on display names"""
        # Destroy existing canvases
        for canvas in self.__display_canvases:
            canvas.destroy()
        self.__display_canvases.clear()
        self.__display_names.clear()
        
        if self.__single_display_name:
            display_names = [self.__single_display_name]
            self.__total_pages = 1
        else:
            factory_talk_view_se_id = self.__acm_data_handler.get_factory_talk_view_se_id()
            # Get display names - removing the problematic factory_talk_view_se_id for now
            # This should be fixed based on your actual data structure
            displays_df = self.__acm_data_handler.get_all_displays(factory_talk_view_se_id)
            display_names = displays_df['DisplayName'].tolist()
                
            self.__total_pages = len(display_names)

        self.__display_names = display_names
        self.library_parsers = {}
        
        # Create multiple ProcessDisplayCanvas instances, each with its own GFX file
        for i, display_name in enumerate(display_names):
            gfx_file = f"{display_name}.xml"  # Assume GFX file matches display name
            canvas = ProcessDisplayCanvas(self.__placeholder, 
                                        self.__internal_db, 
                                        self.__acm_data_handler, self.__project_name, self.__config,
                                        self.selection_callback, 
                                        self.zoom_percentage_callback,
                                        gfx_file,  # Pass the specific GFX file
                                        self.library_parsers,
                                        go_to_roi_callback=self.__go_to_drawing_roi)
            canvas.pack(fill=tk.BOTH, expand=True)
            self.__display_canvases.append(canvas)

            # Hide all canvases except the first one
            if i > 0:
                canvas.pack_forget()

        self.__current_page = 1
        
        # Load canvases sequentially, waiting for each to complete
        self.__current_loading_index = 0
        self.__load_next_canvas()
            
            
        

    def __load_next_canvas(self):
        """Load canvases sequentially, waiting for each to complete before loading the next"""

        # Set shared progress for all canvases
        percentage = (self.__current_loading_index / self.__total_pages) if self.__total_pages else 1.0
        task = f"Loaded display {self.__current_loading_index} of {self.__total_pages}"


        def close_all_progress_banners():
            for canvas in self.__display_canvases:
                canvas.hide_shared_progress()


        for canvas in self.__display_canvases:
            canvas.set_shared_progress(percentage, task, close_func=close_all_progress_banners)

        if self.__current_loading_index >= len(self.__display_canvases):
            # All canvases loaded
            print("All canvases loaded successfully")
            return
            
        current_canvas = self.__display_canvases[self.__current_loading_index]
        current_display_name = self.__display_names[self.__current_loading_index]

        

        def on_gfx_load_done():
            print(f"GFX file loaded for canvas: {current_display_name}")
            # Move to next canvas
            self.__current_loading_index += 1
            self.__load_next_canvas()
        
        current_canvas.load_gfx_file(done_callback=on_gfx_load_done)
        
    
    def selection_callback(self, number_of_selected_elements=0):
        if number_of_selected_elements < 2:
            self.__top_align_button.disable()
            self.__horizontal_center_align_button.disable()
            self.__bottom_align_button.disable()
            self.__left_align_button.disable()
            self.__vertical_center_align_button.disable()
            self.__right_align_button.disable()
        else:
            self.__top_align_button.enable()
            self.__horizontal_center_align_button.enable()
            self.__bottom_align_button.enable()
            self.__left_align_button.enable()
            self.__vertical_center_align_button.enable()
            self.__right_align_button.enable()
        
        if number_of_selected_elements < 3:
            self.__horizontal_distribute_button.disable()
            self.__vertical_distribute_button.disable()
        else:
            self.__horizontal_distribute_button.enable()
            self.__vertical_distribute_button.enable()

            


    def __update_page_display(self):
        """Update the page number display and switch to current display canvas"""
        
        # Update page number
        self.__page_number.entry.delete(0, tk.END)
        self.__page_number.entry.insert(0, str(self.__current_page))
        
        # Update total pages
        if hasattr(self, '__total_page_text'):
            self.canvas.itemconfig(self.__total_page_text, text=f"/ {self.__total_pages}")
        
        # Switch to the current canvas using pack/pack_forget instead of tkraise
        # since ProcessDisplayCanvas instances are packed, not using grid or place
        if self.__display_canvases and 0 < self.__current_page <= len(self.__display_canvases):
            # Hide all canvases
            for canvas in self.__display_canvases:
                canvas.pack_forget()
            
            # Show the current canvas
            current_canvas = self.__display_canvases[self.__current_page - 1]
            current_canvas.pack(fill=tk.BOTH, expand=True)


 

    def __page_up(self, _,__):
        """Go to the next page"""
        if self.__current_page < self.__total_pages:
            self.__current_page += 1
            self.__update_page_display()

    def __page_down(self,_,__):
        """Go to the previous page"""
        if self.__current_page > 1:
            self.__current_page -= 1
            self.__update_page_display()

    def get_current_display_canvas(self):
        """Get the currently active display canvas"""
        if self.__display_canvases and 0 < self.__current_page <= len(self.__display_canvases):
            return self.__display_canvases[self.__current_page - 1]
        return None
    
    def get_current_display_name(self):
        """Get the name of the currently active display"""
        if self.__display_names and 0 < self.__current_page <= len(self.__display_names):
            return self.__display_names[self.__current_page - 1]
        return f"Display {self.__current_page}"

    def __left_align(self, _, __):
        """Align to the left"""
        current_canvas = self.get_current_display_canvas()
        if current_canvas:
            current_canvas.align_left()

    def __horizontal_center_align(self, _, __):
        """Align to the horizontal center"""
        current_canvas = self.get_current_display_canvas()
        if current_canvas:
            current_canvas.align_horizontal_center()

    def __right_align(self, _, __):
        """Align to the right"""
        current_canvas = self.get_current_display_canvas()
        if current_canvas:
            current_canvas.align_right()

    def __top_align(self, _, __):
        """Align to the top"""
        current_canvas = self.get_current_display_canvas()
        if current_canvas:
            current_canvas.align_top()

    def __vertical_center_align(self, _, __):
        """Align to the vertical center"""
        current_canvas = self.get_current_display_canvas()
        if current_canvas:
            current_canvas.align_vertical_center()

    def __bottom_align(self, _, __):
        """Align to the bottom"""
        current_canvas = self.get_current_display_canvas()
        if current_canvas:
            current_canvas.align_bottom()

    def __horizontal_distribute(self, _, __):
        """Distribute horizontally"""
        current_canvas = self.get_current_display_canvas()
        if current_canvas:
            current_canvas.distribute_horizontal()

    def __vertical_distribute(self, _, __):
        """Distribute vertically"""
        current_canvas = self.get_current_display_canvas()
        if current_canvas:
            current_canvas.distribute_vertical()

    def zoom_in(self,_,__):
        current_canvas = self.get_current_display_canvas()
        if not current_canvas:
            return

        if (current_canvas.imscale * 100 * 1.3) > 50000:
            return

        current_canvas.zoom(current_canvas.imscale * 100 * 1.3)


    def zoom_out(self,_,__):
        current_canvas = self.get_current_display_canvas()
        if not current_canvas:
            return

        if (current_canvas.imscale * 100 / 1.3) < 2:
            return


        current_canvas.zoom(current_canvas.imscale * 100 / 1.3)


    def __zoom_percentage_edit_callback(self):
        """Handle zoom percentage edit"""
        current_canvas = self.get_current_display_canvas()
        if not current_canvas:
            return

        if int(self.zoom_percentage.entry.get()) != (int(current_canvas.imscale *100)):
            current_canvas.zoom(self.zoom_percentage.entry.get())


    def __check_zoom_percentage(self, zoom_percentage, action_type):
        if action_type == '1': #insert
            current_canvas = self.get_current_display_canvas()
            if not current_canvas:
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
            self.zoom_percentage.entry.delete(0, tk.END)
            self.zoom_percentage.entry.insert(0, percentage_string)


    def __check_page_number(self, page_number, action_type):
        """Validate page number entry"""
        if action_type == '1':  # insert
            if not page_number.isnumeric():
                return False
                
            if not 1 <= int(page_number) <= self.__total_pages:
                return False
            
        return True

    def __page_number_edit_callback(self):
        """Handle page number edit"""
        try:
            new_page = int(self.__page_number.entry.get())
            if 1 <= new_page <= self.__total_pages:
                self.__current_page = new_page
                self.__update_page_display()
        except ValueError:
            # Reset to current page if invalid
            self.__page_number.entry.delete(0, tk.END)
            self.__page_number.entry.insert(0, str(self.__current_page))

    def page_number_callback(self, page_number, _):
        self.__page_number.entry.delete(0, tk.END)
        self.__page_number.entry.insert(0, str(page_number))


    def __generate_current_display(self, _=None):
        """Generate the current display"""
        current_canvas = self.get_current_display_canvas()
        if not current_canvas:
            messagebox.showinfo("No Canvas", "No display canvas available.")
            return
            
        gfx_file_editor = current_canvas.get_gfx_file_editor()

        if not gfx_file_editor:
            messagebox.showinfo("No Displays", "No displays available to generate.")
            return
        
        self.__export_path = askdirectory(title="Select Export Directory")
        if not self.__export_path: return

        display_name = gfx_file_editor.display_name
        self.show_busy_canvas(f"Generating {display_name}...")

        self.list_of_gfx_indexes = [self.__current_page - 1]
        self.list_of_displays_done = []

        # Start generation for all displays
        Thread(target=self.__generate_all_displays_process).start()
        
        # Simulate processing time
        self.__win.after(1000, lambda: self.__check_generation_complete())

    def __generate_all_displays(self, _=None):
        """Generate all displays"""


        if not self.__display_canvases:
            messagebox.showinfo("No Displays", "No displays available to generate.")
            return
        
        for canvas in self.__display_canvases:
            if not canvas.done_loading:
                messagebox.showinfo("Displays Still Loading", "Please wait until all displays are fully loaded before generating.")
                return
        
        # "Build HMI → View Designer" pushes the exported files straight
        # into FactoryTalk View SE via SEAddComponent.exe, so the on-disk
        # location is transient — silently drop it into %TEMP% instead
        # of pestering the user with a folder-picker dialog. The
        # "XML and Images" flow still prompts because the user wants to
        # keep those artefacts.
        if self.__run_seadd_component:
            safe_project_name = re.sub(r"[^A-Za-z0-9_-]", "_",
                                       (self.__project_name or "project")).strip("_") or "project"
            try:
                self.__export_path = tempfile.mkdtemp(prefix=f"spa_hmi_{safe_project_name}_")
            except OSError as exc:
                logging.exception(f"Cannot create temp export folder: {exc}")
                messagebox.showerror(
                    "Build HMI → View Designer",
                    f"Could not create a temporary export folder:\n{exc}",
                    parent=self.__win)
                return
            logging.info(f"Build HMI → View Designer exporting to temp folder: {self.__export_path}")
        else:
            self.__export_path = askdirectory(title="Select Export Directory")
            if not self.__export_path: return

        # When the caller opted into the "Build HMI → View Designer" push,
        # let the user pick the FactoryTalk View SE application right
        # here on the Tk main thread — much cleaner than trying to
        # marshal a modal dialog out of the export worker later. If the
        # user cancels, we still perform the file-only export and just
        # skip the SEAddComponent.exe launch.
        if self.__run_seadd_component:
            self.__prompt_for_seadd_target()
            # Mark the SEAdd push as pending up-front (on the main
            # thread) so __check_generation_complete keeps the busy
            # canvas alive until the subprocess finishes. If the user
            # cancelled the picker we do NOT set this — the export
            # runs as a plain file drop with no SEAdd stage.
            if self.__seadd_selected_app_name:
                self.__seadd_in_progress = True
                self.__seadd_result = None
                self.__seadd_last_line = ""

        self.list_of_gfx_indexes: list[int] = [i for i,_ in enumerate(self.__display_canvases)]
        self.list_of_displays_done = []
        

        # Start generation for all displays
        Thread(target=self.__generate_all_displays_process).start()

        self.show_busy_canvas("Generating all displays...")

        # Check for completion every second
        self.__win.after(1000, lambda: self.__check_generation_complete())


    def __generate_all_displays_process(self):
        """Process to generate all displays"""

        hmi_displays_exported = []
        
        for gfx_index in self.list_of_gfx_indexes:
            # Use the appropriate canvas for this display
            if gfx_index < len(self.__display_canvases):
                canvas = self.__display_canvases[gfx_index]
            else:
                canvas = self.get_current_display_canvas()
                
            if not canvas:
                continue
                
            # Simulate generation process
            display_name = canvas.get_display_name()
            logging.info(f"Generating display: {display_name}")
            # Here you would add the actual logic to generate the display
            # For now, we just simulate a delay
            hmi_display = canvas.generate_display(self.__export_path)
            hmi_displays_exported.append(hmi_display)

            self.list_of_displays_done.append(gfx_index)

        # create a batch import file 
        self.__create_batch_import_file(hmi_displays_exported)

        # create the FactoryTalk View SE Add Component Tool component-list
        # XML alongside the legacy BatchImport file, then (optionally) run
        # SEAddComponent.exe against it. Both steps are best-effort — the
        # export itself has already succeeded by this point, so we never
        # re-raise from these helpers.
        component_list_path = self.__create_seadd_component_list_file(hmi_displays_exported)
        if component_list_path is not None:
            self.__maybe_run_seadd_component_tool(component_list_path)

        # Notify the user about the completion
        logging.info(f"All displays generated successfully. {len(hmi_displays_exported)} displays exported.")


    def __create_batch_import_file(self, hmi_displays_exported):
        """Create a batch import file for the generated displays"""
        root = ET.Element("gfxImport")

        for display in hmi_displays_exported:
            import_element = ET.SubElement(root, "import")
            import_element.set("importFile", display)

        # Create the tree and write to file
        tree = ET.ElementTree(root)
        tree.write(os.path.join(self.__export_path, f"BatchImport_{self.__project_name}HMI.xml"))


    def __create_seadd_component_list_file(self, hmi_displays_exported):
        """Write a Rockwell SEAddComponent component-list XML for the exported
        displays and any accompanying image files.

        Schema (per FTView SE 16 docs, "Component list file" page):

            <hmi>
              <category type="Graphics;Displays" folder="<export_path>">
                <component file="<display>.xml"/>
                ...
              </category>
              <category type="Graphics;Images" folder="<export_path>\\images">
                <component file="<image>.svg"/>
                ...
              </category>
            </hmi>

        The ``Graphics;Images`` block is only emitted when the export
        actually produced image files under ``<export_path>/images``;
        without that second category SEAddComponent silently ignores
        every static-graphic SVG the display XML references. FTView SE
        13+ accepts ``.svg`` alongside the classic ``.bmp / .png / .jpg
        / .gif / .tif / .tiff / .wmf`` set.

        Returns the absolute path of the file that was written, or ``None``
        when no displays were exported (nothing to write). Never raises —
        any I/O error is logged so the surrounding export flow keeps going.
        """
        if not hmi_displays_exported:
            return None
        try:
            root = ET.Element("hmi")

            # --- displays -------------------------------------------------
            displays_category = ET.SubElement(root, "category")
            displays_category.set("type", "Graphics;Displays")
            # Use an absolute folder path so the tool works regardless of
            # its own CWD. The docs allow this alongside relative folders.
            displays_category.set("folder", os.path.abspath(self.__export_path))
            for display in hmi_displays_exported:
                component = ET.SubElement(displays_category, "component")
                component.set("file", display)

            # --- images ---------------------------------------------------
            # generate_display() writes static-graphic SVGs into
            # <export_path>/images/ (see ProcessDisplayCanvas.generate_display).
            # SEAddComponent needs a dedicated Graphics;Images category to
            # push them into the application's Images folder — otherwise
            # the displays land in Studio with broken image references.
            image_files = self.__collect_seadd_image_files()
            if image_files:
                images_dir = os.path.abspath(
                    os.path.join(self.__export_path, 'images')
                )
                images_category = ET.SubElement(root, "category")
                images_category.set("type", "Graphics;Images")
                images_category.set("folder", images_dir)
                for image_name in image_files:
                    image_component = ET.SubElement(images_category, "component")
                    image_component.set("file", image_name)

            output_path = os.path.join(
                self.__export_path,
                f"SEAddComponent_{self.__project_name}HMI.xml",
            )
            tree = ET.ElementTree(root)
            tree.write(output_path, encoding="utf-8", xml_declaration=True)
            logging.info(
                f"Wrote SEAddComponent component list: {output_path} "
                f"(displays={len(hmi_displays_exported)}, "
                f"images={len(image_files) if image_files else 0})"
            )
            return output_path
        except Exception as exc:
            logging.exception(f"Failed to write SEAddComponent component list: {exc}")
            return None


    # File extensions FactoryTalk View SE accepts as image components.
    # Verified against real FTView SE 13 installs on 2026-07-27:
    # 4702 .bmp + 34 .svg + 1 .png in Public Documents HMI Projects.
    _SEADD_IMAGE_EXTENSIONS = ('.svg', '.png', '.bmp', '.jpg', '.jpeg',
                               '.gif', '.tif', '.tiff', '.wmf')

    def __collect_seadd_image_files(self):
        """Return the flat list of image filenames (basenames only) sitting
        in ``<export_path>/images`` that SEAddComponent should push into
        the application's Images folder. Returns ``[]`` when the images
        subfolder does not exist or is empty."""
        images_dir = os.path.join(self.__export_path, 'images')
        if not os.path.isdir(images_dir):
            return []
        try:
            entries = os.listdir(images_dir)
        except OSError as exc:
            logging.warning(f"Cannot list SEAddComponent images dir '{images_dir}': {exc}")
            return []
        image_files = []
        for name in entries:
            full = os.path.join(images_dir, name)
            if not os.path.isfile(full):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext in self._SEADD_IMAGE_EXTENSIONS:
                image_files.append(name)
        image_files.sort()
        return image_files


    def __prompt_for_seadd_target(self):
        """Show the FTView SE application picker on the Tk main thread and
        remember the choice for the export worker to consume later. Called
        from ``__generate_all_displays`` right after the user picks the
        export directory, so we can fail fast if they cancel.

        Pre-selects the app the user picked last time (persisted via
        ``Config.set_seadd_last_app_name``); on first run falls back to
        the current SPA project name if that happens to match one of the
        discovered applications, and to a plain ``''`` otherwise.

        Never raises — any failure to build the picker is logged and
        treated as "user cancelled", so the file export still succeeds
        with SEAddComponent silently skipped.
        """
        try:
            settings = self.__config.get_seadd_component_settings()
            default_type = (settings.get('application_type')
                            or 'Distributed').strip()
        except Exception as exc:
            logging.debug(f"FTView picker: cannot load settings ({exc}); using defaults.")
            default_type = 'Distributed'

        try:
            default_name = (self.__config.get_seadd_last_app_name() or '').strip()
        except Exception:
            default_name = ''
        if not default_name:
            default_name = (self.__project_name or '').strip()

        try:
            picker = FTViewAppPicker(
                self.__win,
                default_name=default_name,
                default_app_type=default_type,
            )
            result = picker.get_result()
        except Exception as exc:
            logging.exception(f"FTView picker: failed to open ({exc}); "
                              f"SEAddComponent will be skipped.")
            self.__seadd_selected_app_name = None
            self.__seadd_selected_app_type = None
            return

        if result is None:
            self.__seadd_selected_app_name = None
            self.__seadd_selected_app_type = None
            return

        self.__seadd_selected_app_name = result['name']
        self.__seadd_selected_app_type = result['app_type']

        # Remember for next time — best-effort, persistence failure must
        # not abort the export.
        try:
            self.__config.set_seadd_last_app_name(result['name'])
        except Exception as exc:
            logging.warning(f"FTView picker: cannot persist last app name ({exc}).")


    def __maybe_run_seadd_component_tool(self, component_list_path):
        """Invoke SEAddComponent.exe against the freshly-written component
        list when the caller opted into the push ("Build HMI → View
        Designer" menu entry) and the config is minimally valid.

        The application name and type come from the FTView SE picker
        shown before the export started (see
        ``__prompt_for_seadd_target``); the ``area_name``, ``overwrite``
        and ``exe_path`` inputs still come from the SE Add Component
        Tool section in Settings. SEAddComponent inherits the invoking
        Windows session's FactoryTalk identity, so no ``/U`` / ``/P``
        credentials are sent on the command line.

        Silently skips (with a WARN log) when:
        - the caller did not request the push (default for "XML and Images"),
        - the user cancelled the picker (no application selected),
        - the exe path is blank or the file does not exist.

        Runs the subprocess on a background thread so the Tk UI stays
        responsive; stdout/stderr are streamed line-by-line into the
        busy canvas via ``_update_seadd_progress`` so the user can see
        the tool making progress. The final success/failure messagebox
        is deferred to ``__check_generation_complete`` — the outcome is
        stashed on ``self.__seadd_result`` and the completion poller
        renders one consolidated dialog once both the file export and
        the push have finished.
        """
        # Guard: every early-return path here must clear
        # __seadd_in_progress so the completion poller does not wait
        # forever for a push that will never fire.
        if not self.__run_seadd_component:
            self.__seadd_in_progress = False
            return

        try:
            settings = self.__config.get_seadd_component_settings()
        except Exception as exc:
            logging.warning(f"SEAddComponent: cannot load settings ({exc}); skipping.")
            self.__seadd_in_progress = False
            return

        exe_path = (settings.get('exe_path') or '').strip()
        # Application name/type come from the FTView SE application
        # picker shown in __prompt_for_seadd_target() before the export
        # started. If the user cancelled that dialog these are None and
        # we quietly skip the push — the file-only export has already
        # succeeded by this point.
        app_name = (self.__seadd_selected_app_name or '').strip()
        app_type = (self.__seadd_selected_app_type
                    or settings.get('application_type')
                    or 'Distributed').strip()
        area = (settings.get('area_name') or '/').strip() or '/'
        overwrite = bool(settings.get('overwrite'))

        if not exe_path or not os.path.isfile(exe_path):
            logging.warning(
                f"SEAddComponent: exe path is missing or does not exist "
                f"('{exe_path}'); skipping."
            )
            self.__seadd_in_progress = False
            return
        if not app_name:
            logging.warning(
                "SEAddComponent: no application selected (picker was cancelled "
                "or returned an empty name); skipping."
            )
            self.__seadd_in_progress = False
            return

        # Positional args, in the exact order documented by Rockwell:
        #   SEAddComponent applicationName applicationType areaName componentListFile
        # optional switches follow.
        argv = [exe_path, app_name, app_type, area, component_list_path]
        if overwrite:
            argv.append('overwrite')

        logging.info(f"SEAddComponent: launching {argv}")
        log_hint = os.path.join(
            os.path.dirname(component_list_path), '$AddComponent.txt'
        )
        timeout_seconds = 600

        def _run():
            output_tail: list[str] = []
            proc = None
            try:
                # Merge stderr into stdout so we get one ordered stream
                # to display; keep it text-mode + line-buffered so lines
                # arrive incrementally rather than after the tool exits.
                proc = subprocess.Popen(
                    argv,
                    shell=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                start = time.monotonic()
                assert proc.stdout is not None
                for raw_line in proc.stdout:
                    if time.monotonic() - start > timeout_seconds:
                        proc.kill()
                        raise subprocess.TimeoutExpired(argv, timeout_seconds)
                    line = raw_line.rstrip()
                    if not line:
                        continue
                    output_tail.append(line)
                    if len(output_tail) > 20:
                        del output_tail[0]
                    # Marshal the progress line to the Tk main thread —
                    # updating widgets from a worker thread is unsafe.
                    self.__win.after(0, self._update_seadd_progress, line)
                exit_code = proc.wait(timeout=max(
                    1, timeout_seconds - int(time.monotonic() - start)))
                logging.info(
                    f"SEAddComponent: exit={exit_code} "
                    f"stdout_tail={output_tail[-20:]}"
                )
                if exit_code == 0:
                    self.__seadd_result = {
                        "status": "success",
                        "exit_code": exit_code,
                        "log_hint": log_hint,
                        "component_list_path": component_list_path,
                    }
                else:
                    detail = '\n'.join(output_tail) or '(no output)'
                    self.__seadd_result = {
                        "status": "failed",
                        "exit_code": exit_code,
                        "detail": detail,
                        "log_hint": log_hint,
                    }
            except subprocess.TimeoutExpired:
                logging.exception(
                    f"SEAddComponent: timed out after {timeout_seconds}s")
                if proc is not None:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                self.__seadd_result = {
                    "status": "timeout",
                    "timeout_seconds": timeout_seconds,
                    "log_hint": log_hint,
                }
            except Exception as exc:
                logging.exception(f"SEAddComponent: launch failed ({exc})")
                self.__seadd_result = {
                    "status": "launch_failed",
                    "error": str(exc),
                }
            finally:
                # Always clear the in-progress flag so the completion
                # poller can tear down the busy canvas and surface the
                # outcome messagebox.
                self.__seadd_in_progress = False

        Thread(target=_run, daemon=True).start()


    def _update_seadd_progress(self, line):
        """Render the latest SEAddComponent stdout line into the busy
        canvas overlay. Called on the Tk main thread via ``after`` so
        the widget update is safe. Truncates over-long lines so the
        canvas caption stays readable."""
        try:
            text = (line or '').strip()
            if not text:
                return
            if len(text) > 70:
                text = text[:67] + '...'
            self.__seadd_last_line = text
            self.show_busy_canvas(f"SEAddComponent: {text}")
        except tk.TclError:
            # Busy canvas / window already torn down — nothing to do.
            pass
        except Exception as exc:
            logging.debug(f"SEAddComponent progress render failed: {exc}")


    def __check_generation_complete(self):
        """Handle completion of display generation.

        The file-export worker populates ``list_of_displays_done`` and
        then (optionally) fires ``__maybe_run_seadd_component_tool``
        which flips ``__seadd_in_progress`` while the push is live.
        This poller therefore has three states:

        1. Exports still running — update busy canvas with %-complete.
        2. Exports done, SEAdd running — leave the busy canvas alone
           (``_update_seadd_progress`` keeps it repainted with the
           latest stdout line) and keep polling.
        3. Exports done, SEAdd finished (or never started) — tear down
           the busy canvas and surface the appropriate messagebox(es).
        """

        if len(self.list_of_displays_done) != len(self.list_of_gfx_indexes):
            percentage = int((len(self.list_of_displays_done) / len(self.list_of_gfx_indexes)) * 100)
            self.show_busy_canvas(f"Generating displays {percentage}% complete")
            # Continue checking until all displays are done
            self.__win.after(1000, lambda: self.__check_generation_complete())
            return

        if self.__seadd_in_progress:
            # SEAddComponent.exe is still working. Do NOT redraw the
            # busy canvas here — _update_seadd_progress owns that job
            # and repainting from the poller would just clobber the
            # streaming line with a stale caption. Fall through and
            # keep polling.
            self.__win.after(500, lambda: self.__check_generation_complete())
            return

        self.__delete_busy_canvas()

        # Surface the SEAdd outcome first (when applicable) so the
        # user sees the push result before the generic completion
        # message. Result is None when SEAdd was skipped or never
        # requested — in that case we just fall through to the
        # existing "Generation Complete" dialog.
        seadd_result = self.__seadd_result
        self.__seadd_result = None
        if seadd_result is not None:
            self.__show_seadd_result_messagebox(seadd_result)

        if len(self.list_of_gfx_indexes) == 1:
            current_canvas = self.get_current_display_canvas()
            if current_canvas:
                display_name = current_canvas.get_display_name()
                messagebox.showinfo("Generation Complete", f"Display '{display_name}' has been generated successfully.{self.__export_path_hint()}")
            else:
                messagebox.showinfo("Generation Complete", f"Display has been generated successfully.{self.__export_path_hint()}")
        else:
            messagebox.showinfo("Generation Complete", f"All {len(self.list_of_gfx_indexes)} displays have been generated successfully.{self.__export_path_hint()}")


    def __export_path_hint(self):
        """Return a trailing ``\\n\\nFiles exported to: <path>`` fragment
        when the export dropped files into a temp folder (View Designer
        flow). Empty string for the user-picked "XML and Images" path
        so the classic messagebox wording is preserved verbatim."""
        if self.__run_seadd_component and self.__export_path:
            return f"\n\nFiles exported to:\n{self.__export_path}"
        return ""


    def __show_seadd_result_messagebox(self, result):
        """Render the collected SEAddComponent outcome as a single
        messagebox. Called from ``__check_generation_complete`` on the
        Tk main thread once ``__seadd_in_progress`` clears."""
        status = result.get("status")
        if status == "success":
            component_list = result.get("component_list_path", "")
            log_hint = result.get("log_hint", "")
            msg = (
                "SEAddComponent.exe completed successfully (exit code 0)."
                f"\n\nComponent list:\n{component_list}"
                f"\n\nTool log (see for details):\n{log_hint}"
            )
            messagebox.showinfo("SEAddComponent complete", msg, parent=self.__win)
        elif status == "failed":
            exit_code = result.get("exit_code", "?")
            detail = result.get("detail", "(no output)")
            log_hint = result.get("log_hint", "")
            msg = (
                f"SEAddComponent.exe returned exit code {exit_code}."
                f"\n\nLast output:\n{detail}"
                f"\n\nTool log:\n{log_hint}"
            )
            messagebox.showerror("SEAddComponent failed", msg, parent=self.__win)
        elif status == "timeout":
            seconds = result.get("timeout_seconds", 600)
            log_hint = result.get("log_hint", "")
            msg = (
                f"SEAddComponent.exe did not finish within {seconds} seconds."
                f"\n\nTool log:\n{log_hint}"
            )
            messagebox.showerror("SEAddComponent timed out", msg, parent=self.__win)
        elif status == "launch_failed":
            err = result.get("error", "unknown error")
            messagebox.showerror(
                "SEAddComponent launch failed",
                f"Could not launch SEAddComponent.exe:\n{err}",
                parent=self.__win)


    def show_busy_canvas(self, text=""):
        """Show a busy indicator with text"""
        self.__delete_busy_canvas()
        self.__busy_canvas = tk.Canvas(self.__placeholder)
        self.__busy_canvas.config(background='#F5F5F5')
        loading = loading_animation(self.__busy_canvas)

        def center_loading(_):
            x = int(self.__busy_canvas.winfo_width()/2)
            y = int(self.__busy_canvas.winfo_height()/2)
            
            loading.draw(x, y)                
            text_id = self.__busy_canvas.create_text(x, y + 24,
                                            text=text,
                                            fill="#6F6F6F",
                                            anchor=tk.CENTER,
                                            justify=tk.CENTER)
            _, y1, _, y2 = self.__busy_canvas.bbox(text_id)
            self.__busy_canvas.move(text_id, 0, int(abs(y1 - y2)/2))

        self.__busy_canvas.bind("<Configure>", center_loading)
        self.__busy_canvas.update()

    def __delete_busy_canvas(self):
        """Remove the busy indicator"""
        if self.__busy_canvas:
            self.__busy_canvas.grid_forget()
            self.__busy_canvas.destroy()
            self.__busy_canvas = None

    # Menu callback methods
    def __menu_build_display(self):
        """Menu callback for Build Display"""
        self.__generate_current_display()

    def __menu_build_all_displays(self):
        """Menu callback for Build All Displays"""
        self.__generate_all_displays()

    def __menu_reset_display(self):
        """Menu callback for Reset Display"""
        current_canvas = self.get_current_display_canvas()
        if current_canvas: 
            current_canvas.reset_gfx_file_editor()
        

    def __menu_reset_all_displays(self):
        """Menu callback for Reset All Displays"""
        for canvas in self.__display_canvases:
            if canvas: 
                canvas.reset_gfx_file_editor()

    def __menu_show_drawing(self):
        """Menu callback for Show Drawing"""
        current_canvas = self.get_current_display_canvas()
        hmi_display = current_canvas.get_hmi_display()
        if not hmi_display:
            messagebox.showinfo("No SPA HMI Display Available", "The current display does not have a linked Solutions Project Accelerator display.")
            return
            
        path = hmi_display['path']
        page_number = hmi_display['pno'] + 1 # Convert to 1-based index
        self.__go_to_drawing_page(page_number, path)

    def __menu_toggle_show_object_names(self):
        """Menu callback for Hide Object Names (Ctrl+T)"""
        current_canvas = self.get_current_display_canvas()
        if current_canvas:
            current_canvas.show_or_hide_object_names()

    def __menu_undo(self):
        """Menu callback for Undo (Ctrl+Z)"""
        current_canvas = self.get_current_display_canvas()
        if current_canvas:
            current_canvas.undo()

    def __menu_redo(self):
        """Menu callback for Redo (Ctrl+Shift+Z)"""
        current_canvas = self.get_current_display_canvas()
        if current_canvas:
            current_canvas.redo()
            
    def __menu_remove_all_material_lines(self):
        """Remove all material lines from the current display"""
        current_canvas = self.get_current_display_canvas()
        if current_canvas:
            current_canvas.remove_all_material_lines()
            
    def __menu_remove_all_signal_lines(self):
        """Remove all signal lines from the current display"""
        current_canvas = self.get_current_display_canvas()
        if current_canvas:
            current_canvas.remove_all_signal_lines()
            
    def __menu_remove_all_lines(self):
        """Remove all lines from the current display"""
        current_canvas = self.get_current_display_canvas()
        if current_canvas:
            current_canvas.remove_all_lines()

    def __setup_keyboard_bindings(self):
        """Set up keyboard bindings for menu shortcuts"""
        self.__win.bind_all("<Control-t>", lambda e: self.__menu_toggle_show_object_names())
        self.__win.bind_all("<Control-z>", lambda e: self.__menu_undo())
        self.__win.bind_all("<Control-Shift-Z>", lambda e: self.__menu_redo())

    def close(self):
        """Close the Build Display window"""
        # Destroy all display canvases
        for canvas in self.__display_canvases:
            canvas.destroy()
        self.__display_canvases.clear()
        
        self.__win.destroy()

# For testing the module
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # Hide the main window

    acm_data_handler = ACM_Data_Handler(r'DRIVER={ODBC Driver 18 for SQL Server};SERVER=1TV0VV3\SQLACM;DATABASE=ACM;Trusted_Connection=yes;TrustServerCertificate=yes;')
    acm_data_handler.set_project_id("6044")
    project_name = "Video_Demo_1"
    internal_db = Database(project_name)
    
    from logic_config import Config
    config = Config()
    
    app = BuildDisplay(root, internal_db, acm_data_handler, project_name, config)
    root.mainloop()