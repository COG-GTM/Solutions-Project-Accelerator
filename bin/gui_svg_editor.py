import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.colorchooser import askcolor
import traceback
import xml.etree.ElementTree as ET
import re
import cv2
import numpy as np
import cairosvg
from PIL import Image, ImageTk
import io
import os
from svgpathtools import parse_path
import math
import copy

try:
    from bin.gui_elements import button_array, custom_entry, hover_toggle_button, rounded_image_button
    from bin.gui_autoscrollbar import AutoScrollbar
    from bin.logic_validators import Validators
    from bin.gui_base64_icons import (select_tool_blue, select_tool_dark_gray, select_tool_light_gray,
                                    hand_tool_blue, hand_tool_dark_gray, hand_tool_light_gray,
                                    pen_tool_blue, pen_tool_dark_gray, pen_tool_light_gray,
                                    zoom_in_blue, zoom_in_dark_gray, zoom_in_light_gray,
                                    zoom_out_blue, zoom_out_dark_gray, zoom_out_light_gray,
                                    save_icon, width_selection)
except ImportError as e:
    from gui_elements import button_array, custom_entry, hover_toggle_button, rounded_image_button
    from gui_autoscrollbar import AutoScrollbar
    from logic_validators import Validators
    from gui_base64_icons import (select_tool_blue, select_tool_dark_gray, select_tool_light_gray,
                                    hand_tool_blue, hand_tool_dark_gray, hand_tool_light_gray,
                                    pen_tool_blue, pen_tool_dark_gray, pen_tool_light_gray,
                                    zoom_in_blue, zoom_in_dark_gray, zoom_in_light_gray,
                                    zoom_out_blue, zoom_out_dark_gray, zoom_out_light_gray,
                                    save_icon, width_selection)

class SVGEditor:
    def __init__(self, parent, build_hmi_element=None, svg_path=None, config=None):
        self.root = tk.Toplevel(parent)
        self.root.title("SVG Editor")
        self.root.geometry("800x600")
        this_dir = os.path.dirname(os.path.realpath(__file__))
        self.root.iconbitmap(os.path.join(this_dir, 'logo.ico'))

        # Stay above the window that opened us; without this the process
        # diagram canvas re-focuses itself on <Enter> and covers this dialog.
        self.root.transient(parent.winfo_toplevel())
        try:
            self.root.grab_set()
        except tk.TclError:
            pass

        self.parent = parent
        self.__config = config
        self.__delta = 1.3  # zoom magnitude
        
        # Initialize variables
        self.svg_path = svg_path
        self.build_hmi_element = build_hmi_element
        self.svg_string = build_hmi_element.svg_string
        self.svg_root = None
        self.svg_namespaces = {}
        self.canvas_elements = {}  # Map SVG elements to canvas objects
        self.path_data = {}  # Store original path data
        self.mode = "select"  # Default mode
        self.selected_element = None
        self.drawing_line = False
        self.line_start = None
        self.temp_line = None
        self.line_width = 2
        self.line_color = "#000000"
        self.scale_factor = 1.0
        self.snap_radius = 10  # Radius in pixels for snap-to-point
        self.snap_indicator = None  # Visual indicator for snap points
        self.all_points = []  # Store all endpoints for snapping
        self.snap_enabled = True  # Default snap to enabled
        
        # Add viewBox properties
        self.viewbox = {"min_x": 0, "min_y": 0, "width": 0, "height": 0}
        self.svg_width = 0
        self.svg_height = 0
        self.has_viewbox = False
        
        # Undo history
        self.undo_stack = []
        self.max_undo_steps = 20  # Maximum number of undo steps to store

        self.original_img_width = None  # Original width of the SVG image
        self.original_img_height = None

        self.__fill_color = "#00FF00"  # Default fill color for drawing
        self.__loading_style_values = False
        # While False the style defaults track the styling of the imported SVG
        self.__style_user_modified = False

        if self.__config:
            fill, stroke, width = self.__config.get_extracted_hmi_graphic_settings()
            self.__fill_color = self.__normalize_color(fill, self.__fill_color)
            self.line_color = self.__normalize_color(stroke, self.line_color)
            self.line_width = self.__normalize_width(width, self.line_width)
        
        # Setup UI components
        self._setup_ui()

        
        self.import_svg()

        self.__update_style_widgets()


        
    def _setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, relief='flat')
        main_frame.grid(row=0, column=0, sticky='nsew', padx=0, pady=0)

        # Configure root grid
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Configure main_frame grid
        main_frame.grid_rowconfigure(0, weight=0)  # Toolbar row
        main_frame.grid_rowconfigure(1, weight=1)  # Canvas row
        main_frame.grid_columnconfigure(0, weight=1)


        # Create toolbar canvas
        self.toolbar_canvas = tk.Canvas(main_frame, height=60, background="white", highlightthickness=0)
        self.toolbar_canvas.grid(row=0, column=0, sticky='ew')
        self.toolbar_canvas.bind("<Configure>", self._configure_toolbar)

        self.zoom_percentage = custom_entry(self.toolbar_canvas,0,0,enbale_rect=False,width=40,size=9,enable_line=False,
                                            focus_out_callback=self.__zoom_percentage_edit_callback)
        self.zoom_percentage.entry.insert(0, "100")
        self.zoom_percentage.entry.configure(validate="key", justify=tk.RIGHT)
        self.zoom_percentage.entry['validatecommand'] = (self.zoom_percentage.entry.register(self.__check_zoom_percentage),'%P','%d')
        self.generate_display_dark_gray = tk.PhotoImage(data=save_icon)

        # Default drawing style controls (stroke colour, fill colour and line width)
        self.__stroke_swatch_image = None
        self.__fill_swatch_image = None
        self.width_selection_image = tk.PhotoImage(data=width_selection)
        self.stroke_color_button = tk.Button(self.toolbar_canvas, relief=tk.FLAT, bd=0, highlightthickness=0,
                                             background="white", activebackground="white",
                                             command=self.__ask_stroke_color)
        self.fill_color_button = tk.Button(self.toolbar_canvas, relief=tk.FLAT, bd=0, highlightthickness=0,
                                           background="white", activebackground="white",
                                           command=self.__ask_fill_color)
        self.stroke_color_entry = custom_entry(self.toolbar_canvas, 0, 0, enbale_rect=False, width=56, size=9,
                                               enable_line=False,
                                               focus_out_callback=self.__stroke_color_edit_callback)
        self.fill_color_entry = custom_entry(self.toolbar_canvas, 0, 0, enbale_rect=False, width=56, size=9,
                                             enable_line=False,
                                             focus_out_callback=self.__fill_color_edit_callback)
        self.line_width_entry = custom_entry(self.toolbar_canvas, 0, 0, enbale_rect=False, width=30, size=9,
                                             enable_line=False,
                                             focus_out_callback=self.__line_width_edit_callback)
        self.line_width_entry.entry.configure(validate="key", justify=tk.RIGHT)
        self.line_width_entry.entry['validatecommand'] = (self.line_width_entry.entry.register(self.__check_line_width),'%P','%d')
        
        canvas_frame = ttk.Frame(main_frame, relief='flat')
        canvas_frame.grid(row=1, column=0, sticky='nsew')
        canvas_frame.grid_rowconfigure(0, weight=1)  # Canvas row
        canvas_frame.grid_columnconfigure(0, weight=1)

        # Create canvas with scrollbars
        hbar = AutoScrollbar(canvas_frame, orient='horizontal')
        vbar = AutoScrollbar(canvas_frame, orient='vertical')

        # Bind scrollbars to the canvas
        hbar.configure(command=self.__scroll_x)  # bind scrollbars to the canvas
        vbar.configure(command=self.__scroll_y)
        hbar.grid(row=1, column=0, sticky='we')
        vbar.grid(row=0, column=1, sticky='ns')
        self.canvas = tk.Canvas(canvas_frame, bg="white", scrollregion=(0, 0, 3000, 3000), highlightthickness=0,
                                xscrollcommand=hbar.set, yscrollcommand=vbar.set, background="#F0F0F0")
        
        self.canvas.grid(row=0, column=0, sticky='nswe')      
        
        # Create a reference point at (0,0) to align SVG
        self.reference_point = self.canvas.create_rectangle(0, 0, 1, 1, fill="", outline="", width=2, tags=("reference_point",))
        
        # Create context menu
        self.context_menu = tk.Menu(self.canvas, tearoff=0)
        self.context_menu.add_command(label="Delete path", command=self.delete_selected_element, accelerator="Delete")
        self.context_menu.add_command(label="Undo", command=self.undo_action, accelerator="Ctrl+Z")
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Reload SVG", command=self.reload_svg)
        self.context_menu.add_command(label="Export SVG", command=self.export_svg)
        self.context_menu.add_command(label="Save", command=self.save_svg, accelerator="Ctrl+S")

        # Bind canvas events
        self.canvas.bind("<Button-1>", self.canvas_click)
        self.canvas.bind("<B1-Motion>", self.canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.canvas_release)
        self.canvas.bind("<Motion>", self.canvas_motion)  # Mouse motion tracking

        # Bind canvas events for panning
        self.canvas.bind("<Button-3>", self.pan_click)  # Right click for panning
        self.canvas.bind("<B3-Motion>", self.pan_drag)  # Right click drag for panning
        self.canvas.bind("<ButtonRelease-3>", self.pan_release)  # Right click release

        # Bind canvas events for zooming
        self.canvas.bind("<Shift-MouseWheel>", self._zoom)  # Shift + Mouse wheel for zooming out
        self.canvas.bind("<Control-MouseWheel>", self._zoom)  # Ctrl + Mouse wheel for zooming in

        # Enable delete by pressing Delete key
        self.root.bind_all("<Delete>", self.delete_selected_element)

        # Enable undo by pressing Ctrl+Z
        self.canvas.bind_all("<Control-z>",self.undo_action)
        self.canvas.bind_all("<Control-Z>",self.undo_action)

        self.canvas.bind("<Enter>", lambda _: self.canvas.focus_set())

        # Initialize SVGPathParser
        self.svg_path_parser = SVGPathParser()


    # noinspection PyUnusedLocal
    def __scroll_x(self, *args, **kwargs):
        """ Scroll canvas horizontally and redraw the image """
        self.canvas.xview(*args)  # scroll horizontally

    # noinspection PyUnusedLocal
    def __scroll_y(self, *args, **kwargs):
        """ Scroll canvas vertically and redraw the image """
        self.canvas.yview(*args)  # scroll vertically
        
  
    def _configure_toolbar(self, event):
        """Configure the toolbar buttons when resized"""
        self.toolbar_canvas.delete("all")
        w, _ = event.width, event.height
        
        # Mode selection buttons (select, hand, draw)
        x_pos = 10
        
        # Select tool button
        self.select_tool_button = hover_toggle_button(self.toolbar_canvas, select_tool_blue, select_tool_dark_gray, select_tool_light_gray
                                        , anchor = 'w', is_toggle=False, tool_tip_text='Select tool')
        self.toolbar_canvas.create_window(x_pos, 16, anchor='nw', window=self.select_tool_button)
        x_pos += 40

        # Hand tool button (for panning)
        self.hand_tool_button = hover_toggle_button(self.toolbar_canvas, hand_tool_blue, hand_tool_dark_gray, hand_tool_light_gray
                                        , anchor = 'w', is_toggle=False, tool_tip_text='Move tool')
        self.toolbar_canvas.create_window(x_pos, 16, anchor='nw', window=self.hand_tool_button)
        x_pos += 40
        
        # Draw tool button
        self.draw_tool_button = hover_toggle_button(self.toolbar_canvas, pen_tool_blue, pen_tool_dark_gray, pen_tool_light_gray
                                        , anchor = 'w', is_toggle=False, tool_tip_text='Pen tool')
        self.toolbar_canvas.create_window(x_pos, 16, anchor='nw', window=self.draw_tool_button)
        x_pos += 40
        self.selector_tool_buttons = button_array([self.select_tool_button,
                                                    self.hand_tool_button,
                                                    self.draw_tool_button],
                                                    self.__selector_tool_chosen)
        self.selector_tool_buttons.select(0)  # Default to select tool
        
        # Divider line
        self.toolbar_canvas.create_line(x_pos, 12, x_pos, 50, fill="#D5D5D5", width=2)
        x_pos += 20
        
        # Zoom controls
        self.zoom_in_button = hover_toggle_button(self.toolbar_canvas, zoom_in_blue, zoom_in_dark_gray, zoom_in_light_gray, anchor = 'w',
                                        is_toggle=False, callback=self.zoom_in, tool_tip_text='Zoom in')
        self.toolbar_canvas.create_window(x_pos, 16, anchor='nw', window=self.zoom_in_button)
        x_pos += 40

        self.zoom_out_button = hover_toggle_button(self.toolbar_canvas, zoom_out_blue, zoom_out_dark_gray, zoom_out_light_gray, anchor = 'w',
                                        is_toggle=False, callback=self.zoom_out, tool_tip_text='Zoom out')
        self.toolbar_canvas.create_window(x_pos, 16, anchor='nw', window=self.zoom_out_button)
        x_pos += 30
        
        # Zoom percentage display
        self.zoom_percentage.draw(x_pos, 1)
        x_pos += 80
        
        # Divider line
        self.toolbar_canvas.create_line(x_pos, 12, x_pos, 50, fill="#D5D5D5", width=2)
        x_pos += 20

        # Default drawing style controls
        self.toolbar_canvas.create_text(x_pos, 29, text='Stroke', anchor=tk.W, fill="#6F6F6F")
        x_pos += 42
        self.toolbar_canvas.create_window(x_pos, 23, anchor='nw', window=self.stroke_color_button)
        self.stroke_color_entry.draw(x_pos + 2, 1)
        x_pos += 82
        self.toolbar_canvas.create_text(x_pos, 29, text='Fill', anchor=tk.W, fill="#6F6F6F")
        x_pos += 26
        self.toolbar_canvas.create_window(x_pos, 23, anchor='nw', window=self.fill_color_button)
        self.fill_color_entry.draw(x_pos + 2, 1)
        x_pos += 82
        self.toolbar_canvas.create_image(x_pos, 23, image=self.width_selection_image, anchor=tk.NW)
        self.line_width_entry.draw(x_pos + 2, 1)
        
        # Save button (right aligned)
        self.save_button = rounded_image_button(self.toolbar_canvas, w - 130, 4, 10, text="SAVE", icon_image=self.generate_display_dark_gray, borderwidth=1, 
                    width=120, tags= ('upload',), callback=self.save_svg, fixed_width_offset=10)
        self.save_button.draw()

    @staticmethod
    def __normalize_color(value, fallback):
        """Return value as an '#RRGGBB' string, or fallback when it is not a valid hex colour"""
        value = str(value).strip().lstrip('#') if value else ''
        if len(value) == 3:
            value = ''.join(character * 2 for character in value)
        if not re.fullmatch(r'[0-9a-fA-F]{6}', value):
            return fallback
        return '#' + value.upper()

    @staticmethod
    def __normalize_width(value, fallback):
        """Return value as a positive float, or fallback when it is not a valid width"""
        try:
            width = float(value)
        except (TypeError, ValueError):
            return fallback
        return width if width > 0 else fallback

    @staticmethod
    def __format_width(value):
        """Format a width for display and for the SVG stroke-width attribute"""
        width = float(value)
        return str(int(width)) if width.is_integer() else str(width)

    def __update_style_widgets(self):
        """Sync the toolbar swatches and entries with the current default style"""
        self.__loading_style_values = True
        try:
            self.__stroke_swatch_image = ImageTk.PhotoImage(Image.new('RGBA', (12, 12), self.line_color + 'FF'))
            self.stroke_color_button.configure(image=self.__stroke_swatch_image)
            self.stroke_color_entry.set_text(self.line_color[1:])
            self.__fill_swatch_image = ImageTk.PhotoImage(Image.new('RGBA', (12, 12), self.__fill_color + 'FF'))
            self.fill_color_button.configure(image=self.__fill_swatch_image)
            self.fill_color_entry.set_text(self.__fill_color[1:])
            self.line_width_entry.set_text(self.__format_width(self.line_width))
        finally:
            self.__loading_style_values = False

    def __save_style_defaults(self, stroke=False, fill=False, width=False):
        """Store the current style so it becomes the default for new graphics and restyle the drawing"""
        self.__style_user_modified = True
        self.__update_style_widgets()
        self.__apply_style_to_drawing(stroke=stroke, fill=fill, width=width)
        if not self.__config:
            return
        self.__config.set_extracted_hmi_graphic_settings(self.__fill_color[1:],
                                                         self.line_color[1:],
                                                         self.__format_width(self.line_width))

    def __apply_style_to_drawing(self, stroke=False, fill=False, width=False):
        """Restyle the loaded SVG with the current defaults and redraw the canvas"""
        if self.svg_root is None:
            return

        self.deselect_element()
        self._save_state_for_undo("change default style")

        stroke_width = self.__format_width(self.line_width)
        for element in self.svg_root.iter():
            if element is self.svg_root:
                continue
            if stroke and element.get('stroke', 'none') != 'none':
                element.set('stroke', self.line_color)
            if width and element.get('stroke-width', 'none') != 'none':
                element.set('stroke-width', stroke_width)
            if fill and element.get('fill', 'none') != 'none':
                element.set('fill', self.__fill_color)

        self._redraw_from_svg(True)

    def __ask_stroke_color(self):
        color = askcolor(parent=self.root, color=self.line_color, title='Choose a default stroke color')
        if color[1] is None:
            return
        self.line_color = self.__normalize_color(color[1], self.line_color)
        self.__save_style_defaults(stroke=True)

    def __ask_fill_color(self):
        color = askcolor(parent=self.root, color=self.__fill_color, title='Choose a default fill color')
        if color[1] is None:
            return
        self.__fill_color = self.__normalize_color(color[1], self.__fill_color)
        self.__save_style_defaults(fill=True)

    def __stroke_color_edit_callback(self):
        if self.__loading_style_values:
            return
        value = self.stroke_color_entry.get().strip().lstrip('#')
        if not Validators.check_hex_rgb_color(value):
            self.__update_style_widgets()
            messagebox.showerror('Invalid hex color code', 'The stroke color hex code entered is invalid. '
                                                           + 'Please enter a valid hex color code.')
            return
        if self.__normalize_color(value, self.line_color) == self.line_color:
            return
        self.line_color = self.__normalize_color(value, self.line_color)
        self.__save_style_defaults(stroke=True)

    def __fill_color_edit_callback(self):
        if self.__loading_style_values:
            return
        value = self.fill_color_entry.get().strip().lstrip('#')
        if not Validators.check_hex_rgb_color(value):
            self.__update_style_widgets()
            messagebox.showerror('Invalid hex color code', 'The fill color hex code entered is invalid. '
                                                           + 'Please enter a valid hex color code.')
            return
        if self.__normalize_color(value, self.__fill_color) == self.__fill_color:
            return
        self.__fill_color = self.__normalize_color(value, self.__fill_color)
        self.__save_style_defaults(fill=True)

    def __check_line_width(self, line_width, action_type):
        if action_type == '1':  # insert
            if not self.toolbar_canvas:
                return False
            if not re.fullmatch(r'\d*\.?\d*', line_width):
                return False
            if line_width not in ('', '.') and float(line_width) > 100:
                return False
        return True

    def __line_width_edit_callback(self):
        if self.__loading_style_values:
            return
        width = self.__normalize_width(self.line_width_entry.get().strip(), None)
        if width is None:
            self.__update_style_widgets()
            messagebox.showerror('Invalid line width', 'The line width entered is invalid. '
                                                       + 'Please enter a number greater than zero.')
            return
        if width == self.line_width:
            return
        self.line_width = width
        self.__save_style_defaults(width=True)

    
    def show_context_menu(self, event):
        """Show the context menu at the current mouse position"""
        # If we're in select mode and clicked on an element, select it first
        if self.mode == "select":
            x = self.canvas.canvasx(event.x)
            y = self.canvas.canvasy(event.y)
            clicked_item = self.canvas.find_closest(x, y, halo=5)
            if clicked_item and any(tag in self.canvas.gettags(clicked_item[0]) for tag in ["selectable", "path_segment"]):
                self.select_element(clicked_item[0])
        
        # Enable/disable menu items based on current state
        self.context_menu.entryconfigure("Delete path", 
                                        state=tk.NORMAL if self.selected_element else tk.DISABLED)
        self.context_menu.entryconfigure("Undo", 
                                        state=tk.NORMAL if self.undo_stack else tk.DISABLED)
        
        # Show the menu
        self.context_menu.post(event.x_root, event.y_root)

    def reload_svg(self):
        """Reload the original SVG file"""
        if self.svg_path:
            # Save state for undo before reloading
            self._save_state_for_undo("reload SVG")
            
            # Reset state
            self.canvas_elements = {}
            self.path_data = {}
            self.all_points = []
            self.deselect_element()
            
            # Re-import the SVG
            self._parse_svg_file()
            self._display_svg_on_canvas()
            messagebox.showinfo("Reload", "SVG has been reloaded from the original file")
        else:
            messagebox.showwarning("Warning", "No SVG file has been loaded")

    def export_svg(self):
        """Export the current SVG to a new file"""
        if self.svg_root is None:
            messagebox.showwarning("Warning", "No SVG loaded to export")
            return
        
        # Open file dialog to select export location
        file_path = filedialog.asksaveasfilename(
            title="Export SVG File",
            defaultextension=".svg",
            filetypes=[("SVG files", "*.svg"), ("All files", "*.*")],
            initialfile="exported.svg"
        )
        
        if not file_path:
            return
        
        if not file_path.endswith('.svg'):
            file_path += '.svg'
        
        try:
            # Create a new ElementTree and save
            tree = ET.ElementTree(self.svg_root)
            tree.write(file_path, encoding="utf-8", xml_declaration=True)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export SVG: {str(e)}")


    def __selector_tool_chosen(self, tool):
        """Handle tool selection changes"""
        if tool == 0:
            self.mode = "select"
        elif tool == 1:
            self.deselect_element()
            self.mode = "pan"
        elif tool == 2:
            self.deselect_element()
            self.mode = "draw"

    def __check_zoom_percentage(self, zoom_percentage, action_type):
        if action_type == '1': #insert
            if not self.toolbar_canvas:
                return False
                
            if not zoom_percentage.isnumeric():
                return False

            if not 50000 >= int(zoom_percentage):
                return False

            if not 1 <= int(zoom_percentage):
                return False
            
        return True
    
    def __zoom_percentage_edit_callback(self):
        """Handle zoom percentage edit"""
        if not self.canvas:
            return

        if int(self.zoom_percentage.entry.get()) != (int(self.scale_factor *100)):
            self._zoom_to_percentage(self.zoom_percentage.entry.get())


    def _zoom_to_percentage(self, percentage):

        box_canvas = (self.canvas.canvasx(0),  # get visible area of the canvas
                      self.canvas.canvasy(0),
                      self.canvas.canvasx(self.canvas.winfo_width()),
                      self.canvas.canvasy(self.canvas.winfo_height()))
        x =  int((box_canvas[0] + box_canvas[2])/2)    
        y =  int((box_canvas[1] + box_canvas[3])/2)  

        scale =  float(percentage) / 100

        canvas_scale = scale / self.scale_factor  # calculate scale factor for canvas
        self.scale_factor = scale  # update image pyramide scale

        self.canvas.scale("all", x, y, canvas_scale, canvas_scale)  # Scale all canvas elements
        
        # Update line widths based on the new scale factor
        for canvas_id, element_info in self.canvas_elements.items():
            element = element_info.get('element')
            if element is not None and hasattr(element, 'get'):
                stroke_width = float(element.get('stroke-width', 1))
                # Update line width proportionally to the change in scale
                new_width = stroke_width * self.scale_factor
                try:
                    self.canvas.itemconfig(canvas_id, width=new_width)
                except:
                    pass

        self.update_image_postion()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))  # Update scroll region


        

    def _zoom(self, event):
        """ Zoom with mouse wheel """
        x = self.canvas.canvasx(event.x)  # get coordinates of the event on the canvas
        y = self.canvas.canvasy(event.y)
        scale = 1.0
        # Respond to Linux (event.num) or Windows (event.delta) wheel event
        if event.num == 5 or event.delta == -120:  # scroll down, zoom out, smaller
            scale        /= self.__delta
        elif event.num == 4 or event.delta == 120:  # scroll up, zoom in, larger
            scale        *= self.__delta

        self.scale_factor *= scale
        self.canvas.scale("all", x, y, scale, scale)  # Scale all canvas elements
        
        # Update line widths based on the new scale factor
        for canvas_id, element_info in self.canvas_elements.items():
            element = element_info.get('element')
            if element is not None and hasattr(element, 'get'):
                stroke_width = float(element.get('stroke-width', 1))
                # Update line width proportionally to the change in scale
                new_width = stroke_width * self.scale_factor
                try:
                    self.canvas.itemconfig(canvas_id, width=new_width)
                except:
                    pass

        self.update_image_postion()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))  # Update scroll region

        self.zoom_percentage.entry.delete(0, 'end')
        self.zoom_percentage.entry.insert(0, f"{int(self.scale_factor * 100)}")


    def update_image_postion(self):
        """Update the position of the background image based on the reference point"""
        if self.svg_root is not None:
            if hasattr(self, 'refresh_svg_handle_id'):
                self.canvas.after_cancel(self.refresh_svg_handle_id)
            
            # Ensure reference point is at (0,0)
            x,y,_,_ = self.canvas.coords(self.reference_point)

            # Raster resize the image based on the new scale factor
            svg_image = self.svg_image.resize((int(self.original_img_width * self.scale_factor), int(self.original_img_height * self.scale_factor)), Image.Resampling.LANCZOS)
    
            self.tk_image = ImageTk.PhotoImage(svg_image)
            if self.selected_element:
                selection_image = self.selected_element_image_img.resize((int(self.original_img_width * self.scale_factor), int(self.original_img_height * self.scale_factor)), Image.Resampling.LANCZOS)
                self.selected_element_image = ImageTk.PhotoImage(selection_image)
                self.canvas.coords("selected_overlay", x, y)  # Move selection image to top-left (0,0)
                self.canvas.itemconfig("selected_overlay", image=self.selected_element_image)

            self.canvas.coords("background", x, y)  # Move background image to top-left (0,0)
            self.canvas.itemconfig("background", image=self.tk_image)
            
            self.refresh_svg_handle_id = self.canvas.after(500, self._refresh_svg_image)

            
    def _refresh_svg_image(self):
        
        png_data = cairosvg.svg2png(bytestring=self.svg_string, scale=self.scale_factor)
        
        self.svg_image = Image.open(io.BytesIO(png_data))

        self.tk_image = ImageTk.PhotoImage(self.svg_image)
        
        # Always use (0,0) as the reference point
        self.canvas.itemconfig("background", image=self.tk_image)
        self.canvas.tag_raise("selectable", "background")  # Ensure it appears above the background
        if self.selected_element:
            self.canvas.delete("selected_overlay")
            png_data = cairosvg.svg2png(bytestring=self.selection_svg_string, scale=self.scale_factor)
            self.selected_element_image_img = Image.open(io.BytesIO(png_data))
            self.selected_element_image = ImageTk.PhotoImage(self.selected_element_image_img)
            x, y, _, _ = self.canvas.coords(self.reference_point)  # Get the reference point coordinates
            self.canvas.create_image(x, y, anchor="nw", image=self.selected_element_image, tags=("selected_overlay",))
            self.canvas.tag_raise("selectable", "selected_overlay")  # Ensure it appears below the selectable elements
        
        

    def pan_click(self, event):
        """Start panning on right click"""
        self.canvas.scan_mark(event.x, event.y)
        self.moving_canvas = False

    def pan_drag(self, event):
        """Handle panning while dragging right click"""
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        self.moving_canvas = True

    def pan_release(self, event):
        """End panning on right click release"""
        self.canvas.scan_mark(0, 0)

        if self.moving_canvas:
            self.moving_canvas = False 
            return
        
        self.show_context_menu(event)  # Show context menu on right click release if not panning



    def update_snap_radius(self, event=None):
        self.snap_radius = self.snap_radius_var.get()
    
    def _save_state_for_undo(self, action_name=""):
        """Save current state for undo"""
        state = {
            'canvas_elements': copy.deepcopy(self.canvas_elements),
            'all_points': copy.deepcopy(self.all_points),
            'svg_root': copy.deepcopy(self.svg_root) if self.svg_root is not None else None,
            'path_data': copy.deepcopy(self.path_data),
            'action': action_name
        }
        
        self.undo_stack.append(state)
        
        # Limit the undo stack size
        if len(self.undo_stack) > self.max_undo_steps:
            self.undo_stack.pop(0)
    
    def undo_action(self, _=None):
        """Undo the last action"""
        if not self.undo_stack:
            return
        
        # Get the previous state
        previous_state = self.undo_stack.pop()
        
        # Restore state
        self.canvas_elements = previous_state['canvas_elements']
        self.all_points = previous_state['all_points']
        self.svg_root = previous_state['svg_root']
        self.path_data = previous_state['path_data']
        
        # Redraw everything
        self._redraw_from_svg(True)
        
    
    
    def _clean_duplicate_canvas_elements(self):
        """Remove duplicate elements from canvas after redrawing"""
        # Group elements by their coordinates
        element_by_coords = {}
        
        # Find duplicates based on coordinates
        for canvas_id, element_info in list(self.canvas_elements.items()):
            if not self.canvas.winfo_exists():
                continue  # Canvas has been destroyed
                
            # Skip if element doesn't exist on canvas anymore
            try:
                if not self.canvas.type(canvas_id):
                    del self.canvas_elements[canvas_id]
                    continue
            except:
                del self.canvas_elements[canvas_id]
                continue
                
            coords_key = None
            if 'coords' in element_info:
                # Create a hash of the coordinates for comparison
                coords_key = tuple(element_info['coords'])
                
            if coords_key:
                if coords_key in element_by_coords:
                    # We found a duplicate, delete the older one
                    old_id = element_by_coords[coords_key]
                    try:
                        self.canvas.delete(old_id)
                    except:
                        pass
                    if old_id in self.canvas_elements:
                        del self.canvas_elements[old_id]
                
                # Store this element
                element_by_coords[coords_key] = canvas_id
                
    def import_svg(self):
        try:
            # Parse SVG file
            self._parse_svg_file()
            
            # Display SVG on canvas
            self._display_svg_on_canvas()

            # Save current state for undo
            self._save_state_for_undo("import SVG")


        except Exception as e:
            messagebox.showerror("Error", f"Failed to import SVG: {str(e)}")
    
    def _parse_svg_file(self):
        ET.register_namespace('', 'http://www.w3.org/2000/svg')

        if self.svg_path is not None:
            tree = ET.parse(self.svg_path)
            self.svg_root = tree.getroot()
            self.svg_string = ET.tostring(self.svg_root, encoding='unicode')
        elif self.svg_string is not None:
            try:
                self.svg_root = ET.fromstring(self.svg_string)
            except ET.ParseError as e:
                messagebox.showerror("Error", f"Failed to parse SVG string: {str(e)}")
                return
            
        
        # Extract namespaces
        xmlns_pattern = re.compile(r'\{([^}]+)\}')
        matches = xmlns_pattern.findall(self.svg_root.tag)
        if matches:
            self.svg_namespaces = {'svg': matches[0]}
        
        # Parse viewBox if present
        self.has_viewbox = False
        viewbox_attr = self.svg_root.get('viewBox', None)
        
        if viewbox_attr:
            try:
                viewbox_values = list(map(float, re.findall(r'[-+]?(?:\d*\.\d+|\d+)', viewbox_attr)))
                if len(viewbox_values) == 4:
                    self.viewbox["min_x"] = viewbox_values[0]
                    self.viewbox["min_y"] = viewbox_values[1]
                    self.viewbox["width"] = viewbox_values[2]
                    self.viewbox["height"] = viewbox_values[3]
                    self.has_viewbox = True
            except Exception as e:
                print(f"Error parsing viewBox: {e}")
        
        # Get SVG dimensions
        try:
            width_attr = self.svg_root.get('width', '100%')
            height_attr = self.svg_root.get('height', '100%')
            
            # Convert to numbers if possible (ignore percentage values)
            if width_attr.endswith('px'):
                width_attr = width_attr[:-2]
            if height_attr.endswith('px'):
                height_attr = height_attr[:-2]
                
            if not width_attr.endswith('%') and not height_attr.endswith('%'):
                self.svg_width = float(width_attr)
                self.svg_height = float(height_attr)
            elif self.has_viewbox:
                # If dimensions are percentages but we have a viewBox, use viewBox dimensions
                self.svg_width = self.viewbox["width"]
                self.svg_height = self.viewbox["height"]
        except Exception as e:
            print(f"Error parsing SVG dimensions: {e}")
            # Use viewBox dimensions as fallback if available
            if self.has_viewbox:
                self.svg_width = self.viewbox["width"]
                self.svg_height = self.viewbox["height"]
                

    def _display_svg_on_canvas(self, preserve_state=False, recreate_interactive_elements=True):
        
        
        # Preserve state if requested
        if not preserve_state:
            self.canvas_elements = {}
            self.path_data = {}
            self.all_points = []  # Reset endpoint list
        
        # Convert SVG to PNG image using CairoSVG
        try:
            png_data = cairosvg.svg2png(bytestring=self.svg_string, scale=self.scale_factor)
            self.svg_image = Image.open(io.BytesIO(png_data))
            self.tk_image = ImageTk.PhotoImage(self.svg_image)
            
            # Set canvas size based on image
            if self.original_img_width is None or self.original_img_height is None:
                self.original_img_width, self.original_img_height = self.svg_image.size
                self.canvas.config(scrollregion=(0, 0, self.original_img_width, self.original_img_height))
            
            # Create image on canvas
            x, y, _, _ = self.canvas.coords(self.reference_point)
            if recreate_interactive_elements:
                self.canvas.delete("background")
                background = self.canvas.create_image(x, y, anchor="nw", image=self.tk_image, tags=("background","element"))
            else:
                background = self.canvas.find_withtag("background")
                if background:
                    self.canvas.itemconfig(background, image=self.tk_image)
                else:
                    background = self.canvas.create_image(x, y, anchor="nw", image=self.tk_image, tags=("background","element"))
            self.canvas.lower(background)

            
            # Add visual representation of lines for interaction
            if recreate_interactive_elements:
                # Remove existing interactive elements
                self.canvas.delete("selectable")
                self._create_interactive_elements()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to display SVG: {str(e)}")
    
    def _create_interactive_elements(self):
        # Process the SVG structure to extract lines and other elements
        if self.svg_root is None:
            return
        
        # Find all line elements
        lines = self.svg_root.findall(".//svg:line", namespaces=self.svg_namespaces) or \
                self.svg_root.findall(".//line")
        
        # Find all path elements
        paths = self.svg_root.findall(".//svg:path", namespaces=self.svg_namespaces) or \
                self.svg_root.findall(".//path")
        
        x0, y0, _, _ = self.canvas.coords(self.reference_point)
        
        # Process line elements
        for i, line in enumerate(lines):
            x1 = float(line.get('x1', 0))
            y1 = float(line.get('y1', 0))
            x2 = float(line.get('x2', 0))
            y2 = float(line.get('y2', 0))
            stroke = line.get('stroke', '#000000')
            stroke_width = float(line.get('stroke-width', 1)) * self.scale_factor

            if not self.__style_user_modified:
                self.line_width = self.__normalize_width(line.get('stroke-width'), self.line_width)
                self.line_color = self.__normalize_color(line.get('stroke'), self.line_color)
            
            # Transform coordinates to canvas space
            x1, y1 = self.svg_to_canvas(x1, y1)
            x2, y2 = self.svg_to_canvas(x2, y2)

            x1 += x0 
            y1 += y0 
            x2 += x0 
            y2 += y0 

            # Add the endpoints to our list for snapping
            self.all_points.append((x1, y1))
            self.all_points.append((x2, y2))
            
            # Create visible line on canvas
            canvas_line = self.canvas.create_line(
                x1, y1, x2, y2, 
                fill="", 
                width=stroke_width,
                tags=(f"line_{i}", "selectable","element")
            )
            
            # Store mapping between SVG element and canvas object
            self.canvas_elements[canvas_line] = {
                'element': line,
                'type': 'line',
                'coords': [x1, y1, x2, y2]
            }
            
        # Process path elements
        for i, path in enumerate(paths):
            d = path.get('d', '')
            if d:
                
                try:
                    stroke = path.get('stroke', None)
                    stroke_width_str = path.get('stroke-width', None)
                    if not self.__style_user_modified:
                        self.line_width = self.__normalize_width(stroke_width_str, self.line_width)
                        self.line_color = self.__normalize_color(stroke, self.line_color)

                    # Save reference of paths with no stroke/stroke-width or none stroke/stroke-width
                    if not stroke or not stroke_width_str or stroke == 'none' or stroke_width_str == 'none':
                        continue

                    if stroke_width_str != 'none':
                        stroke_width = float(stroke_width_str) * self.scale_factor
                    else:
                        stroke_width = 1 * self.scale_factor


                    # Store original path data
                    self.path_data[i] = d

                    def draw_path(points):
                        """Draw path segments on canvas"""
                        if not points:
                            return

                        converted_points = []
                        for i in range(0, len(points), 2):
                            x, y = points[i], points[i+1]
                            new_x, new_y = self.svg_to_canvas(x, y)
                            new_x, new_y = new_x + x0, new_y + y0  # Adjust for reference point
                            converted_points.extend([new_x, new_y])
                            self.all_points.append((new_x, new_y))  # Add to all points for snapping

                        # Create path segments as lines on canvas
                        for j in range(0, len(converted_points) - 2, 2):
                            x1, y1 = converted_points[j], converted_points[j+1]
                            x2, y2 = converted_points[j+2], converted_points[j+3] 

                            # Draw the segment with the proper width
                            canvas_line = self.canvas.create_line(
                                    converted_points, 
                                    fill="", 
                                    width=stroke_width * 0.5,
                                    tags=(f"path_{i}_{j}", "path_segment", "selectable","element")
                                )
                                
                            self.canvas_elements[canvas_line] = {
                                'element': path,
                                'type': 'path_segment',
                                'coords': [x1, y1, x2, y2],
                                'segment_index': j,
                                'path_index': i
                            }

                    # Extract path points and control points for snapping
                    self.svg_path_parser.parse_path(d, draw_path)
                    
                            
                except Exception as e:
                    # Print stacktrace for debugging
                    print(f"Error parsing path data '{d}': {e}")
                    print(traceback.format_exc())
                    continue
    
    
    def update_mode(self):
        mode = self.mode
        
        # Reset any in-progress drawing
        if self.temp_line:
            self.canvas.delete(self.temp_line)
            self.temp_line = None
        
        # Remove snap indicator if it exists
        if self.snap_indicator:
            self.canvas.delete(self.snap_indicator)
            self.snap_indicator = None
            
        self.drawing_line = False
        self.line_start = None
    
    def find_nearest_point(self, x, y):
        """Find the nearest point within snap radius"""
        if not self.snap_enabled:
            return None
            
        min_dist = float('inf')
        nearest_point = None
        
        for px, py in self.all_points:
            dist = math.sqrt((px - x) ** 2 + (py - y) ** 2)
            if dist < min_dist and dist <= self.snap_radius:
                min_dist = dist
                nearest_point = (px, py)
                
        return nearest_point
    
    def show_snap_indicator(self, x, y):
        """Show visual indicator for a snap point"""
        if not self.snap_enabled:
            return
            
        # Remove existing indicator if there is one
        if self.snap_indicator:
            self.canvas.delete(self.snap_indicator)
        
        # Create a new indicator (small circle)
        self.snap_indicator = self.canvas.create_oval(
            x - 5, y - 5, x + 5, y + 5,
            fill="#0C8CE9", outline="white", width=2,
            tags=("snap_indicator", "element")
        )
    
    def hide_snap_indicator(self):
        """Hide the snap point indicator"""
        if self.snap_indicator:
            self.canvas.delete(self.snap_indicator)
            self.snap_indicator = None
    

    def canvas_click(self, event):
        # Get canvas coordinates accounting for scrolling
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        item_id = self.selected_element['id'] if self.selected_element else None
        element_info = self.canvas_elements.get(item_id, {})
        element = element_info.get('element')
        mode = self.mode
        
        if mode == "select":
            # Find if we clicked on a line
            clicked_item = self.canvas.find_closest(x, y, halo=5)
            if clicked_item and any(tag in self.canvas.gettags(clicked_item[0]) for tag in ["selectable", "path_segment"]):
                self.select_element(clicked_item[0])
            else:
                self.deselect_element()
                
        elif mode == "draw":
            # Check if we should snap to a nearby point
            snap_point = self.find_nearest_point(x, y)
            
            if snap_point:
                x, y = snap_point
                self.show_snap_indicator(x, y)
            
            self.drawing_line = True
            self.line_start = (x, y)
            
            # Create temporary line
            self.temp_line = self.canvas.create_line(
                x, y, x, y,
                fill=self.line_color,
                width=float(self.line_width),
                tags=("temp_line","element")
            )
        elif mode == "pan":
            # Start panning on right click
            self.canvas.scan_mark(event.x, event.y)
        
    
    def canvas_drag(self, event):
        # Get canvas coordinates accounting for scrolling
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        mode = self.mode
        
        if mode == "draw" and self.drawing_line and self.temp_line:
            # Check if we should snap to a nearby point
            snap_point = self.find_nearest_point(x, y)
            
            if snap_point:
                x, y = snap_point
                self.show_snap_indicator(x, y)
            else:
                self.hide_snap_indicator()
                
            # Update temporary line
            x1, y1 = self.line_start
            self.canvas.coords(self.temp_line, x1, y1, x, y)
        elif mode == "pan":
            # Handle panning with right click
            self.canvas.scan_dragto(event.x, event.y, gain=1)
    
    def canvas_release(self, event):
        # Get canvas coordinates accounting for scrolling
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        mode = self.mode
        
        if mode == "draw" and self.drawing_line and self.line_start:
            # Check for snap on release
            snap_point = self.find_nearest_point(x, y)
            if snap_point:
                x, y = snap_point
            
            x1, y1 = self.line_start

            
            # Minimum line length check (to avoid accidental clicks)
            if ((x - x1) ** 2 + (y - y1) ** 2) > 25:  # Minimum 5px distance
                # Save state for undo before making changes
                self._save_state_for_undo("create line")
                
                # Delete temporary line
                if self.temp_line:
                    self.canvas.delete(self.temp_line)
                
                # Create final line
                stroke = self.line_color
                stroke_width = float(self.line_width)
                
                canvas_line = self.canvas.create_line(
                    x1, y1, x, y, 
                    fill=stroke, 
                    width=stroke_width,
                    tags=(f"new_line", "selectable", "element")
                )
                
                # Add the endpoints to our list for future snapping
                self.all_points.append((x1, y1))
                self.all_points.append((x, y))
                
                # Create SVG line element
                if self.svg_root is not None:
                    # Adjust coordinates for SVG scale
                    x0, y0, _,_ =self.canvas.coords(self.reference_point)
                    svg_x1, svg_y1 = self.canvas_to_svg(x1-x0, y1-y0)
                    svg_x2, svg_y2 = self.canvas_to_svg(x-x0, y-y0)

                    # Create new line element
                    line_element = ET.Element("line")
                    line_element.set("x1", str(svg_x1))
                    line_element.set("y1", str(svg_y1))
                    line_element.set("x2", str(svg_x2))
                    line_element.set("y2", str(svg_y2))
                    line_element.set("stroke", stroke)
                    line_element.set("stroke-width", self.__format_width(stroke_width))
                    line_element.set("stroke-linecap", "round")
                    line_element.set("stroke-linejoin", "round")
                    
                    # Add to SVG document
                    self.svg_root.append(line_element)
                      # Store mapping
                    self.canvas_elements[canvas_line] = {
                        'element': line_element,
                        'type': 'line',
                        'coords': [x1, y1, x, y]
                    }
                    
                    # Redraw canvas from temporary SVG to ensure proper coordinate mapping
                    self._redraw_from_svg(True)
                    
            else:
                # Delete too short line
                if self.temp_line:
                    self.canvas.delete(self.temp_line)
            
            self.temp_line = None
            self.drawing_line = False
            self.line_start = None
            self.hide_snap_indicator()
        elif mode == "pan":
            # End panning on right click release
            self.canvas.scan_mark(0, 0)
            
            
    
    def canvas_motion(self, event):
        # Update coordinates display
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # Show snap indicator if in draw mode and near a snap point
        if self.mode == "draw" and not self.drawing_line and self.snap_enabled:
            snap_point = self.find_nearest_point(x, y)
            if snap_point:
                self.show_snap_indicator(snap_point[0], snap_point[1])
            else:
                self.hide_snap_indicator()
    
    def select_element(self, item_id):
        # Deselect previously selected item
        start = time.time()
        self.deselect_element()
        
        # Get element info
        element_info = self.canvas_elements.get(item_id, {})
        element = element_info.get('element')
        element_type = element_info.get('type', 'unknown')

        
        # Get original color from the element
        original_color = element.get('stroke', '#000000') if element is not None and hasattr(element, 'get') else '#000000'

        
        # Store the selected element ID and original color
        self.selected_element = {
            'id': item_id,
            'original_color': original_color,
            'type': element_type
        }
        
        # For path segments, get additional info
        if element_type == 'path_segment':
            path_index = element_info.get('path_index', -1)
            self.selected_element['path_index'] = path_index
        
        # Change color in SVG element for highlighting
        selection_color = "#0C8CE9"
        
        # Create a lightweight temporary SVG with just the selected element
        if element is not None and self.svg_root is not None:
            # Create a new SVG root with only viewport/dimension attributes
            temp_root = ET.Element('svg')
            for attr in ['width', 'height', 'viewBox', 'xmlns']:
                if attr in self.svg_root.attrib:
                    temp_root.set(attr, self.svg_root.get(attr))
            
            # Add only the selected element
            if element_type == 'path_segment':
                # For path segments, copy the entire path that contains this segment
                path_index = element_info.get('path_index', -1)
                temp_element = copy.deepcopy(element)
                temp_element.set('stroke', selection_color)
                temp_element.set('stroke-width', self.__format_width(self.line_width))
                temp_root.append(temp_element)
            else:
                # For other elements, just copy the single element
                temp_element = copy.deepcopy(element)
                temp_element.set('stroke', selection_color)
                temp_element.set('stroke-width', self.__format_width(self.line_width))
                temp_root.append(temp_element)
            
            # Save temp SVG and render it
            try:
                
                # Write the temporary SVG
                self.selection_svg_string = ET.tostring(temp_root, encoding="utf-8", xml_declaration=True)

                
                # Render the lightweight SVG quickly
                try:
                    png_data = cairosvg.svg2png(bytestring=self.selection_svg_string, scale=self.scale_factor)
                    self.selected_element_image_img = Image.open(io.BytesIO(png_data))
                    self.selected_element_image = ImageTk.PhotoImage(self.selected_element_image_img)
                    
                    # Create an overlay image on top of the existing background
                    x, y, _, _ = self.canvas.coords(self.reference_point)
                    self.selected_element_canvas_id = self.canvas.create_image(x, y, anchor="nw", image=self.selected_element_image
                                                                               , tags=("selected_overlay", "element"))
                    self.canvas.tag_raise("selectable", "background")  # Ensure it appears above the background
                    self.canvas.tag_raise("selectable", "selected_overlay")  # Ensure it appears below the selectable elements
                    self.selected_element['overlay_id'] = self.selected_element_canvas_id
                    
                    # Store the temp path for cleanup
                    self.selected_element['temp_svg'] = self.selection_svg_string
                    end = time.time()
                    print(f"Rendered selected element in {end - start:.4f} seconds")
                    
                    return  # Skip the full redraw
                except Exception as e:
                    print(f"Error rendering selected element: {e}")
            except Exception as e:
                print(f"Error creating temp SVG: {e}")
            
        
        # Fallback to traditional highlighting if the optimized method fails
        if self._change_element_color_in_svg(element, selection_color):
            # Redraw canvas using temporary SVG to show selection
            self._redraw_from_svg(recreate_interactive_elements=False)
        else:
            # Fallback to canvas-level highlighting if SVG update fails
            current_width = float(self.canvas.itemcget(item_id, 'width'))
            self.canvas.itemconfig(item_id, fill=selection_color, width=current_width*1.5)
        
        
    
    def deselect_element(self):
        if self.selected_element:
            # Get the item id from the selected_element dictionary
            item_id = self.selected_element.get('id')
            
            # Remove the overlay if it exists
            if 'overlay_id' in self.selected_element:
                self.canvas.delete(self.selected_element['overlay_id'])
            
            # Get element info
            element_info = self.canvas_elements.get(item_id, {})
            element = element_info.get('element')
            
            # Restore original color in SVG if we used the traditional method
            if 'overlay_id' not in self.selected_element:
                if self._restore_element_color_in_svg(element):
                    # Redraw canvas using temporary SVG to show restored colors
                    self._redraw_from_svg(recreate_interactive_elements=False)
                else:
                    # Fallback to canvas-level reset if SVG update fails
                    if element_info and hasattr(element, 'get'):
                        orig_width = float(element.get('stroke-width', 1))
                        self.canvas.itemconfig(item_id, width=orig_width * self.scale_factor, fill="")
            
            self.selected_element = None
    
    def delete_selected_element(self, event=None):
        if self.selected_element and self.selected_element['id'] in self.canvas_elements:
            # Save state for undo before deleting
            self._save_state_for_undo("delete element")
            
            item_id = self.selected_element['id']
            element_info = self.canvas_elements[item_id]
            element = element_info.get('element')
            element_type = element_info.get('type', '')
            
            # Restore original color before deleting (to avoid saving the element with modified color)
            self._restore_element_color_in_svg(element)
            
            # Handle path segments differently
            if element_type == 'path_segment':
                # For path segments, we should remove the whole path
                # In a real app, you might want to just modify the path data to remove the segment
                path_index = element_info.get('path_index', -1)
                
                # Find all canvas elements for this path
                path_elements = []
                for canvas_id, info in self.canvas_elements.items():
                    if info.get('type') == 'path_segment' and info.get('path_index') == path_index:
                        path_elements.append(canvas_id)
                
                # Remove all segments from canvas
                for canvas_id in path_elements:
                    # Get the segment points to remove from snap points
                    segment_info = self.canvas_elements.get(canvas_id, {})
                    coords = segment_info.get('coords', [])
                    if len(coords) >= 4:
                        x1, y1, x2, y2 = coords
                        # Remove points from snap points
                        if (x1, y1) in self.all_points:
                            self.all_points.remove((x1, y1))
                        if (x2, y2) in self.all_points:
                            self.all_points.remove((x2, y2))
                    
                    # Remove from canvas
                    self.canvas.delete(canvas_id)
                    # Remove from mapping
                    if canvas_id in self.canvas_elements:
                        del self.canvas_elements[canvas_id]
                
                # Remove from SVG document
                if element is not None and self.svg_root is not None:
                    self.svg_root.remove(element)
                
            else:
                # Regular line element deletion
                # Get the line coordinates to remove from snap points
                coords = element_info.get('coords', [])
                if len(coords) >= 4:
                    # Remove the endpoints from our snap points list
                    x1, y1, x2, y2 = coords
                    if (x1, y1) in self.all_points:
                        self.all_points.remove((x1, y1))
                    if (x2, y2) in self.all_points:
                        self.all_points.remove((x2, y2))
                
                # Remove from SVG document
                if element is not None and self.svg_root is not None:
                    self.svg_root.remove(element)
                
                # Remove from canvas
                self.canvas.delete(item_id)
                
                # Remove from mapping
                del self.canvas_elements[item_id]
                

            # Redraw canvas from temporary SVG to ensure proper coordinate mapping
            self._redraw_from_svg(recreate_interactive_elements=True)
            
            # Clear selection
            self.deselect_element()
            
    
    def save_svg(self, _=None):
        if self.svg_root is None:
            messagebox.showwarning("Warning", "No SVG loaded to save")
            return
        
        try:
            if self.svg_path is not None:
                # Create a new ElementTree and save
                tree = ET.ElementTree(self.svg_root)
                tree.write(self.svg_path, encoding="utf-8", xml_declaration=True)

            elif self.build_hmi_element is not None:
                self.svg_string = ET.tostring(self.svg_root, encoding="unicode")
                self.build_hmi_element.set_svg_string(self.svg_string)
                self.build_hmi_element.update_image()
                self.__offer_style_to_other_graphics()

            self.root.destroy()  # Close the editor window

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save SVG: {str(e)}")

    def __offer_style_to_other_graphics(self):
        """Offer to restyle the static graphics on every display with the style chosen in this editor"""
        if not self.__style_user_modified or not hasattr(self.parent, 'apply_style_to_all_displays'):
            return

        if not messagebox.askyesno("Apply Style",
                                   "Apply the stroke color, fill color and line width to the static "
                                   "graphics on all HMI displays?",
                                   parent=self.root):
            return

        self.parent.apply_style_to_all_displays(self.line_color, self.__fill_color,
                                                self.__format_width(self.line_width),
                                                exclude=self.build_hmi_element)
    
    def zoom_in(self, _=None, __=None):
        self.scale_factor *= 1.2
        self.zoom_percentage.entry.delete(0, 'end')
        self.zoom_percentage.entry.insert(0, f"{int(self.scale_factor * 100)}")
        self._display_svg_on_canvas()

    def zoom_out(self, _=None, __=None):
        self.scale_factor /= 1.2
        self.zoom_percentage.entry.delete(0, 'end')
        self.zoom_percentage.entry.insert(0, f"{int(self.scale_factor * 100)}")
        self._display_svg_on_canvas()

    def svg_to_canvas(self, svg_x, svg_y):
        """Transform SVG coordinates to canvas coordinates, applying viewBox transform if present"""
        if not self.has_viewbox:
            # Simple scaling if no viewBox is defined
            return svg_x * self.scale_factor, svg_y * self.scale_factor
        
        # Apply viewBox transformation
        canvas_x = (svg_x - self.viewbox["min_x"]) * (self.svg_width / self.viewbox["width"]) * self.scale_factor
        canvas_y = (svg_y - self.viewbox["min_y"]) * (self.svg_height / self.viewbox["height"]) * self.scale_factor
        
        return canvas_x, canvas_y
    
    def canvas_to_svg(self, canvas_x, canvas_y):
        """Transform canvas coordinates to SVG coordinates, applying viewBox transform if present"""
        if not self.has_viewbox:
            # Simple scaling if no viewBox is defined
            return canvas_x / self.scale_factor, canvas_y / self.scale_factor
        
        # Apply inverse viewBox transformation
        svg_x = (canvas_x / self.scale_factor) * (self.viewbox["width"] / self.svg_width) + self.viewbox["min_x"]
        svg_y = (canvas_y / self.scale_factor) * (self.viewbox["height"] / self.svg_height) + self.viewbox["min_y"]
        
        return svg_x, svg_y
    
    def _save_temporary_svg(self):
        """Generate and save a temporary SVG file from the current in-memory SVG root"""
        if self.svg_root is None:            return None
        
        try:
            # Create a temporary filename
            temp_path = os.path.join(os.path.dirname(self.svg_string) if self.svg_string else ".", 
                                   f"temp_{os.path.basename(self.svg_string) if self.svg_string else 'untitled.svg'}")
            
            # Create a new ElementTree and save
            tree = ET.ElementTree(self.svg_root)
            tree.write(temp_path, encoding="utf-8", xml_declaration=True)
            
            return temp_path
        except Exception as e:
            print(f"Error creating temporary SVG: {str(e)}")
            return None
            
    def _clean_duplicate_canvas_elements(self):
        """Remove duplicate elements from canvas after redrawing"""
        # Group elements by their coordinates
        element_by_coords = {}
        
        # Find duplicates based on coordinates
        for canvas_id, element_info in list(self.canvas_elements.items()):
            if not self.canvas.winfo_exists():
                continue  # Canvas has been destroyed
                
            # Skip if element doesn't exist on canvas anymore
            try:
                if not self.canvas.type(canvas_id):
                    del self.canvas_elements[canvas_id]
                    continue
            except:
                del self.canvas_elements[canvas_id]
                continue
                
            coords_key = None
            if 'coords' in element_info:
                # Create a hash of the coordinates for comparison
                coords_key = tuple(element_info['coords'])
                
            if coords_key:
                if coords_key in element_by_coords:
                    # We found a duplicate, delete the older one
                    old_id = element_by_coords[coords_key]
                    try:
                        self.canvas.delete(old_id)
                    except:
                        pass
                    if old_id in self.canvas_elements:
                        del self.canvas_elements[old_id]
                
                # Store this element
                element_by_coords[coords_key] = canvas_id
                
    def _redraw_from_svg(self, recreate_interactive_elements=True):
        """Redraw the canvas using a temporary SVG file"""

        if recreate_interactive_elements:
            self._create_background_fill()
      
        # Set the path to the temporary file for rendering
        self.svg_string = ET.tostring(self.svg_root, encoding="utf-8")
        
        # Display the temporary SVG, preserving the element state
        self._display_svg_on_canvas(preserve_state=True, 
                                    recreate_interactive_elements=recreate_interactive_elements)
        
        # Clean up duplicate elements
        self._clean_duplicate_canvas_elements()
    
            

    def _change_element_color_in_svg(self, element, color):
        """Change the color of an SVG element"""
        if element is not None and hasattr(element, 'set'):
            # Save original color if not already saved
            if 'original_stroke' not in element.attrib:
                element.set('original_stroke', element.get('stroke', '#000000'))
            
            # Change the color
            element.set('stroke', color)
            return True
        return False
    
    def _restore_element_color_in_svg(self, element):
        """Restore the original color of an SVG element"""
        if element is not None and hasattr(element, 'set'):
            # Use the attribute stored in the element if available
            if 'original_stroke' in element.attrib:
                # Restore the original color
                original_color = element.get('original_stroke')
                element.set('stroke', original_color)
                element.attrib.pop('original_stroke')
                return True
            # Use the color stored in selected_element if available
            elif self.selected_element and 'original_color' in self.selected_element:
                element.set('stroke', self.selected_element['original_color'])
                return True
        return False
    

    def _create_background_fill(self):
        """
        Creates a background fill for the given region of interest (ROI).
        
        :return: None
        :rtype: None

        This function creates a background fill for the given region of interest (ROI). It uses the strokes_in_roi list to determine the boundary of the ROI and creates a fill for the area enclosed by the boundary. The fill is added to the fills_in_roi list.
        """

        # Remove elements from svg_root that have stroke='none' 
        for element in self.svg_root.findall(".//*[@stroke='none']"):
            # Get the fill color from the element
            if 'fill' in element.attrib and not self.__style_user_modified:
                self.__fill_color = self.__normalize_color(element.get('fill'), self.__fill_color)
            self.svg_root.remove(element)
        
        self.svg_string = ET.tostring(self.svg_root, encoding="utf-8")
        
        xmin, ymin, viewbox_width, viewbox_height = self.svg_root.attrib['viewBox'].split(' ')

        image_data = cairosvg.svg2png(bytestring=self.svg_string)
        
        image = Image.open(io.BytesIO(image_data))
        
        
        img = np.array(image)

        bbox_height = image.height
        bbox_width = image.width
        img= cv2.cvtColor(img,cv2.COLOR_RGBA2RGB)
        mask = np.zeros((img.shape[0] + 2,img.shape[1] + 2), np.uint8)
        cv2.floodFill(img, mask, (0, 0), (255, 255, 255))
        
        mask = mask[1:-1,1:-1]
        
        mask = mask * 255
        mask = cv2.bitwise_not(mask)
        contours, hierarchy = cv2.findContours(mask,cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)

        debug = False 

        if debug:
            cv2.drawContours(img, contours, -1, (0, 255, 0), 3)
            cv2.imshow('Contours', img)
            cv2.waitKey(0)

        if not contours:
            return
        
        # Get the contours in the highest level of hierarchy
        contours = [contour for contour, h in zip(contours, hierarchy[0]) if h[3] == -1]

        # Scale the contours to fit the bounding box and draw the background fill
        for contour in contours:
            path = self.__contour_to_svg_path(contour,float(xmin),float(ymin), bbox_width/float(viewbox_width), bbox_height/float(viewbox_height))
            path_d = path.d()
            path_element = ET.Element("path")
            path_element.set("d", path_d)
            path_element.set("fill", self.__fill_color)
            path_element.set("stroke", "none")
            # Insert the path at the beginning of the SVG root
            self.svg_root.insert(0, path_element)


    def __contour_to_svg_path(self, contour,xmin,ymin, width_ratio, height_ratio):
        """
        Converts a contour to an SVG path.

        :param contour: The contour to convert.
        :type contour: list of tuples
        :param xmin: The minimum x-coordinate value.
        :type xmin: float
        :param ymin: The minimum y-coordinate value.
        :type ymin: float
        :param width_ratio: The ratio to scale the x-coordinates.
        :type width_ratio: float
        :param height_ratio: The ratio to scale the y-coordinates.
        :type height_ratio: float
        :return: The SVG path representation of the contour.
        :rtype: svg.path.Path
        
        Converts a contour, represented as a list of tuples, to an SVG path. The x and y coordinates of each point in the contour are scaled and translated based on the provided xmin, ymin, width_ratio, and height_ratio values. The resulting SVG path is returned.
        
        Example:
            >>> __contour_to_svg_path([(0, 0), (1, 1), (2, 2)], 0, 0, 1, 1)
            <svg.path.Path object at 0x7f9d0a7c6a90>
        """
     
        path = "M"
        for i in range(len(contour)):
            x, y = contour[i][0]
            path = path + str(x / width_ratio + xmin)+ ' ' + str(y / height_ratio + ymin) +' '
            
        #Close path
        x, y = contour[0][0]
        path = path + str(x / width_ratio + xmin)+ ' ' + str(y / height_ratio + ymin)+' '
        
        return parse_path(path)
    
class SVGPathParser:
    def __init__(self):
        self.current_x = 0
        self.current_y = 0
        self.start_x = 0
        self.start_y = 0
        self.last_control_x = 0
        self.last_control_y = 0
        self._draw_points_callback = None
        
    def parse_path(self, path_data, draw_points_callback):
        """Parse SVG path data and draw on canvas"""

        self._draw_points_callback = draw_points_callback

        commands = self._tokenize_path(path_data)
        points = []
        
        i = 0
        while i < len(commands):
            cmd = commands[i]
            if cmd.upper() in 'MLHVCSQTAZ':
                if points and cmd.upper() in 'MZ':
                    # Draw accumulated points before starting new path
                    self._draw_points(points)
                    points = []
                
                i = self._process_command(commands, i, points)
            else:
                i += 1
        
        # Draw any remaining points
        if points:
            self._draw_points(points)
    
    def _tokenize_path(self, path_data):
        """Tokenize SVG path data into commands and coordinates"""
        # Replace commas with spaces and add spaces around commands
        path_data = re.sub(r'([MLHVCSQTAZmlhvcsqtaz])', r' \1 ', path_data)
        path_data = path_data.replace(',', ' ')
        
        # Split and filter empty strings
        tokens = [t for t in path_data.split() if t]
        
        # Convert numeric strings to floats
        result = []
        for token in tokens:
            try:
                result.append(float(token))
            except ValueError:
                result.append(token)
        
        return result
    
    def _process_command(self, commands, i, points):
        """Process a single SVG command"""
        cmd = commands[i]
        i += 1
        
        if cmd.upper() == 'M':  # MoveTo
            x, y = commands[i], commands[i+1]
            if cmd.islower():
                x += self.current_x
                y += self.current_y
            self.current_x, self.current_y = x, y
            self.start_x, self.start_y = x, y
            points.extend([x, y])
            return i + 2
            
        elif cmd.upper() == 'L':  # LineTo
            x, y = commands[i], commands[i+1]
            if cmd.islower():
                x += self.current_x
                y += self.current_y
            points.extend([x, y])
            self.current_x, self.current_y = x, y
            return i + 2
            
        elif cmd.upper() == 'H':  # Horizontal LineTo
            x = commands[i]
            if cmd.islower():
                x += self.current_x
            points.extend([x, self.current_y])
            self.current_x = x
            return i + 1
            
        elif cmd.upper() == 'V':  # Vertical LineTo
            y = commands[i]
            if cmd.islower():
                y += self.current_y
            points.extend([self.current_x, y])
            self.current_y = y
            return i + 1
            
        elif cmd.upper() == 'C':  # Cubic Bezier
            x1, y1 = commands[i], commands[i+1]
            x2, y2 = commands[i+2], commands[i+3]
            x, y = commands[i+4], commands[i+5]
            
            if cmd.islower():
                x1 += self.current_x
                y1 += self.current_y
                x2 += self.current_x
                y2 += self.current_y
                x += self.current_x
                y += self.current_y
            
            self._add_cubic_bezier(points, x1, y1, x2, y2, x, y)
            self.last_control_x = x2
            self.last_control_y = y2
            self.current_x, self.current_y = x, y
            return i + 6
            
        elif cmd.upper() == 'S':  # Smooth Cubic Bezier
            x2, y2 = commands[i], commands[i+1]
            x, y = commands[i+2], commands[i+3]
            
            if cmd.islower():
                x2 += self.current_x
                y2 += self.current_y
                x += self.current_x
                y += self.current_y
            
            # Calculate first control point as reflection of last control point
            x1 = 2 * self.current_x - self.last_control_x
            y1 = 2 * self.current_y - self.last_control_y
            
            self._add_cubic_bezier(points, x1, y1, x2, y2, x, y)
            self.last_control_x = x2
            self.last_control_y = y2
            self.current_x, self.current_y = x, y
            return i + 4
            
        elif cmd.upper() == 'Q':  # Quadratic Bezier
            x1, y1 = commands[i], commands[i+1]
            x, y = commands[i+2], commands[i+3]
            
            if cmd.islower():
                x1 += self.current_x
                y1 += self.current_y
                x += self.current_x
                y += self.current_y
            
            self._add_quadratic_bezier(points, x1, y1, x, y)
            self.last_control_x = x1
            self.last_control_y = y1
            self.current_x, self.current_y = x, y
            return i + 4
            
        elif cmd.upper() == 'T':  # Smooth Quadratic Bezier
            x, y = commands[i], commands[i+1]
            
            if cmd.islower():
                x += self.current_x
                y += self.current_y
            
            # Calculate control point as reflection of last control point
            x1 = 2 * self.current_x - self.last_control_x
            y1 = 2 * self.current_y - self.last_control_y
            
            self._add_quadratic_bezier(points, x1, y1, x, y)
            self.last_control_x = x1
            self.last_control_y = y1
            self.current_x, self.current_y = x, y
            return i + 2
            
        elif cmd.upper() == 'A':  # Elliptical Arc
            rx, ry = commands[i], commands[i+1]
            rotation = commands[i+2]
            large_arc = commands[i+3]
            sweep = commands[i+4]
            x, y = commands[i+5], commands[i+6]
            
            if cmd.islower():
                x += self.current_x
                y += self.current_y
            
            self._add_arc(points, rx, ry, rotation, large_arc, sweep, x, y)
            self.current_x, self.current_y = x, y
            return i + 7
            
        elif cmd.upper() == 'Z':  # Close Path
            points.extend([self.start_x, self.start_y])
            self.current_x = self.start_x
            self.current_y = self.start_y
            return i
            
        return i
    
    def _add_cubic_bezier(self, points, x1, y1, x2, y2, x3, y3, steps=10):
        """Add cubic Bezier curve approximated with line segments"""
        x0, y0 = self.current_x, self.current_y
        
        for i in range(1, steps + 1):
            t = i / steps
            
            # Cubic Bezier formula
            x = (1-t)**3 * x0 + 3*(1-t)**2*t * x1 + 3*(1-t)*t**2 * x2 + t**3 * x3
            y = (1-t)**3 * y0 + 3*(1-t)**2*t * y1 + 3*(1-t)*t**2 * y2 + t**3 * y3
            
            points.extend([x, y])
    
    def _add_quadratic_bezier(self, points, x1, y1, x2, y2, steps=10):
        """Add quadratic Bezier curve approximated with line segments"""
        x0, y0 = self.current_x, self.current_y
        
        for i in range(1, steps + 1):
            t = i / steps
            
            # Quadratic Bezier formula
            x = (1-t)**2 * x0 + 2*(1-t)*t * x1 + t**2 * x2
            y = (1-t)**2 * y0 + 2*(1-t)*t * y1 + t**2 * y2
            
            points.extend([x, y])
    
    def _add_arc(self, points, rx, ry, rotation, large_arc, sweep, x2, y2, steps=10):
        """Add elliptical arc approximated with line segments"""
        x1, y1 = self.current_x, self.current_y
        
        # Convert rotation to radians
        phi = math.radians(rotation)
        cos_phi = math.cos(phi)
        sin_phi = math.sin(phi)
        
        # Calculate center point
        dx = (x1 - x2) / 2
        dy = (y1 - y2) / 2
        
        x1_prime = cos_phi * dx + sin_phi * dy
        y1_prime = -sin_phi * dx + cos_phi * dy
        
        # Ensure radii are large enough
        lambda_sq = (x1_prime / rx)**2 + (y1_prime / ry)**2
        if lambda_sq > 1:
            rx *= math.sqrt(lambda_sq)
            ry *= math.sqrt(lambda_sq)
        
        # Calculate center
        sign = -1 if large_arc == sweep else 1
        coeff = sign * math.sqrt(max(0, (rx*ry)**2 - (rx*y1_prime)**2 - (ry*x1_prime)**2))
        coeff /= ((rx*y1_prime)**2 + (ry*x1_prime)**2)
        
        cx_prime = coeff * rx * y1_prime / ry
        cy_prime = -coeff * ry * x1_prime / rx
        
        cx = cos_phi * cx_prime - sin_phi * cy_prime + (x1 + x2) / 2
        cy = sin_phi * cx_prime + cos_phi * cy_prime + (y1 + y2) / 2
        
        # Calculate angles
        def angle_between(ux, uy, vx, vy):
            dot = ux * vx + uy * vy
            det = ux * vy - uy * vx
            angle = math.atan2(det, dot)
            return angle
        
        theta1 = angle_between(1, 0, (x1_prime - cx_prime) / rx, (y1_prime - cy_prime) / ry)
        dtheta = angle_between((x1_prime - cx_prime) / rx, (y1_prime - cy_prime) / ry,
                              (-x1_prime - cx_prime) / rx, (-y1_prime - cy_prime) / ry)
        
        if sweep and dtheta < 0:
            dtheta += 2 * math.pi
        elif not sweep and dtheta > 0:
            dtheta -= 2 * math.pi
        
        # Generate points
        for i in range(1, steps + 1):
            theta = theta1 + (i / steps) * dtheta
            
            x = cx + rx * math.cos(theta) * cos_phi - ry * math.sin(theta) * sin_phi
            y = cy + rx * math.cos(theta) * sin_phi + ry * math.sin(theta) * cos_phi
            
            points.extend([x, y])
    
    def _draw_points(self, points, **kwargs):
        """Draw accumulated points as a line"""
        if len(points) >= 4:  # Need at least 2 points (4 coordinates)
            self._draw_points_callback(points, **kwargs)

