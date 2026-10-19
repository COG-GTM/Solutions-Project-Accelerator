

import time
import shutil
import numpy as np
from bin.gui_extract_hmi_graphic_view import extract_hmi_graphic_view
from bin.gui_similar_graphics_list_view import similar_graphics_list_view
from bin.logic_extract_hmi_graphic import extract_hmi_graphic
from bin.logic_file_manager import Project_File_Manager
import io
import os
from tkinter import messagebox
from PIL import Image, ImageTk

import cairosvg
from bin.logic_validators import Validators
from tkinter.filedialog import askopenfilename
from bin.gui_elements import rounded_image_button
from tkinter.constants import NONE
from bin.gui_link_view import image_view
import tkinter as tk


try:
    from bin.gui_config_elements import radio_buttons
    from bin.gui_elements import custom_label
    from bin.gui_elements import cell_line
    from bin.gui_base64_icons import goto_dark_gray
except:
    from gui_config_elements import radio_buttons
    from gui_elements import custom_label
    from gui_elements import cell_line

class hmi_graphic_view():

    NONE = '-1'
    EXTRACT_GRAPHIC = '0'
    CUSTOM_GRAPHIC = '1'
    SIMILAR_GRAPHIC = '2'

    def __init__(self, project_name, config, change_callback, request_roi_callback) -> None:
        self.__last_config_time_stamp = None
        self.__project_name = project_name
        self.__config = config
        self.__change_callback = change_callback
        self.__request_roi_callback = request_roi_callback
        self.__extract_hmi_graphic = extract_hmi_graphic(self.__project_name, config)
        self.description = 'Select one of the three methods to create a graphic that will be placed on the HMI.'
        self.hmi_graphic_source_selection_array = [['Extract Graphic','Create a graphic based on the linked graphic.',self.EXTRACT_GRAPHIC]
                                                ,['Custom Graphic','Upload a custom graphic .svg or .png to use.',self.CUSTOM_GRAPHIC]
                                                ,['Similar Graphics','Link to similar to similar graphic found in the repository.',self.SIMILAR_GRAPHIC]]
        self.description_label = None
        self.__remove_view = {
            self.EXTRACT_GRAPHIC: self.__remove_extract_hmi_graphic_view,
            self.CUSTOM_GRAPHIC: self.__remove_custom_graphic_view,
            self.SIMILAR_GRAPHIC: self.__remove_similar_graphic_view,
            self.NONE: lambda: None
        }
        self.__draw_view = {
            self.EXTRACT_GRAPHIC: self.__draw_extract_graphic_view,
            self.CUSTOM_GRAPHIC: self.__draw_custom_graphic_view,
            self.SIMILAR_GRAPHIC: self.__draw_similar_graphics_view,
            self.NONE: lambda: None
        }

        self.__get_graphic = {
            self.EXTRACT_GRAPHIC: self.__get_extracted_graphic,
            self.CUSTOM_GRAPHIC: self.__get_custom_graphic,
            self.SIMILAR_GRAPHIC: self.__get_similar_graphic,
            self.NONE: lambda: None
        }

        self.__export_graphic = {
            self.EXTRACT_GRAPHIC: self.__export_extracted_graphic,
            self.CUSTOM_GRAPHIC: self.__export_custom_graphic,
            self.SIMILAR_GRAPHIC: self.__export_similar_graphic,
            self.NONE: lambda: None
        }

        self.__method = self.NONE
        self.__custom_graphic_path = None
        self.__newly_extracted = False
        self.__hmi_graphic_source_selection = None
        self.__extract_hmi_graphic_view = None 
        self.__custom_graphic_image_view = None 
        self.__similar_graphic_list_view = None
        self.__extract_hmi_graphic_data = {}



    def setup_view(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.__label = custom_label(self.canvas,8, 0, text='HMI Graphic', fill= '#505050',size=14,weight="bold")
        
        self.__hmi_graphic_source_selection = radio_buttons(self.canvas,24,64,
                                                        options_array=self.hmi_graphic_source_selection_array,
                                                        callback=self.__selection_callback)
        self.__hmi_graphic_source_selection.select(self.__method)
        self.__divider = cell_line(self.canvas, 24, 28, 224, fill= '#E5E5E5', width=1)
        
        if self.__similar_graphic_list_view is None:
            self.__similar_graphic_list_view = similar_graphics_list_view(self.canvas,32,246)

        if self.__extract_hmi_graphic_view is None:
            self.__extract_hmi_graphic_view = extract_hmi_graphic_view(self.canvas,32,250,self.__config
                                                            ,self.__start_graphic_extraction
                                                            ,self.__fill_color
                                                            ,self.__stroke_color
                                                            ,self.__stroke_width
                                                            ,self.__extract_hmi_graphic_data,
                                                            initial_values_callback=self.__initial_values)

    def quiet_graphic_extraction(self):
        """ Start the graphic extraction without user interaction. """
        self.__method = self.EXTRACT_GRAPHIC

        try:
            self.__extract_hmi_graphic.start_extraction()
        except OSError as error:
            messagebox.showwarning('Already started',error)
            return
        except ValueError as error:
            messagebox.showerror('Error starting extraction',error)
            return
        
           


    def __start_graphic_extraction(self):
        
        self.__request_roi_callback()

        try:
            self.__extract_hmi_graphic.start_extraction()
        except OSError as error:
            messagebox.showwarning('Already started',error)
            return
        except ValueError as error:
            messagebox.showerror('Error starting extraction',error)
            return

        self.canvas.after(1000, self.__wait_for_extracted_graphic)
        self.__extract_hmi_graphic_view.start_loading_animation()
        self.__newly_extracted = True 

    def set_roi(self, roi, poi, path, pno, text_locations):
        self.__extract_hmi_graphic.set_roi(roi, poi, path, pno, text_locations)

    def get_hmi_graphic(self):
        image =  self.__get_graphic[self.__method]()
        if image is None:
            return None
        
        return np.array(image)


    def __get_custom_graphic(self):
        if self.__custom_graphic_path is None:
            return None
        return Project_File_Manager.open_pillow_image(self.__custom_graphic_path)

    def __get_similar_graphic(self):
        return None 

    def __get_extracted_graphic(self):
        return self.__extract_hmi_graphic.get_hmi_graphic()
    
    def get_error_message(self):
        return self.__extract_hmi_graphic.get_error_message()

    def __wait_for_extracted_graphic(self):
        image = self.__extract_hmi_graphic.get_hmi_graphic()
        error_message = self.__extract_hmi_graphic.get_error_message()
        if image:
            self.__extract_hmi_graphic_view.set_hmi_graphic_image(image, error_message)
            
            if self.__newly_extracted: self.__change_callback()
        else:
            self.canvas.after(1000, self.__wait_for_extracted_graphic)

    def __fill_color(self, color):
        self.__extract_hmi_graphic.set_fill_color(color)
        self.__extract_hmi_graphic_data['fill_color'] = color
        self.__wait_for_extracted_graphic()
        self.__change_callback()

    def __stroke_color(self, color):
        self.__extract_hmi_graphic.set_stroke_color(color)
        self.__extract_hmi_graphic_data['stroke_color'] = color
        self.__wait_for_extracted_graphic()
        self.__change_callback()

    def __stroke_width(self, width):
        self.__extract_hmi_graphic.set_stroke_width(width)
        self.__extract_hmi_graphic_data['stroke_width'] = width
        self.__wait_for_extracted_graphic()
        self.__change_callback()

    def __initial_values(self, fill_color, stroke_color, stroke_width):
        self.__extract_hmi_graphic.initial_values(fill_color,stroke_color,stroke_width)

    def draw(self, event=None):
        if event is not None and event.type == '22':
            # Wierd bug where the canvas keeps getting resized
            if self.__last_config_time_stamp is not None and time.time() - self.__last_config_time_stamp < 500:
                return
            self.__last_config_time_stamp = time.time()
        if '<Configure>' not in self.canvas.bind():
            return
        self.__delete()
        self.__label.draw()
        self.description_label = self.canvas.create_text(24,24, text=self.description, anchor=tk.NW, fill="#6F6F6F")
        description_bounds = self.canvas.bbox(self.description_label) 
        if (description_bounds[2] - description_bounds[0]) > (self.canvas.winfo_width() - 48) and self.canvas.winfo_width() > 0:
            self.fit_description_in_mutiline()
        self.__hmi_graphic_source_selection.draw()
        self.__divider.draw()
        self.__draw_view[self.__method]()
        self.canvas.config(scrollregion=(0,0,self.canvas.bbox(tk.ALL)[2],self.canvas.bbox(tk.ALL)[3]+100))
        

    def __delete(self):
        if self.description_label:
            self.canvas.delete(self.description_label)
            self.__hmi_graphic_source_selection.hide()
            self.__divider.hide()
            self.__remove_items()



    def __selection_callback(self, value):
        self.__draw_view[value[2]]()
        self.__change_callback()


    def __set_method(self, method):
        if self.__hmi_graphic_source_selection:
            self.__hmi_graphic_source_selection.select(method)

    def __draw_extract_graphic_view(self):
        self.__remove_items()
        if self.__extract_hmi_graphic_view is None:
            return

        self.__extract_hmi_graphic_view.draw()
        self.__show_extracted_image()
        self.__method = self.EXTRACT_GRAPHIC

    def __remove_extract_hmi_graphic_view(self):
        if self.__extract_hmi_graphic_view:
            self.__extract_hmi_graphic_view.hide()

    def __draw_custom_graphic_view(self):
        self.__remove_items()
        self.goto_image = tk.PhotoImage(data=goto_dark_gray)
        self.buttonA = rounded_image_button(self.canvas, 16, 250, 10, text="UPLOAD", icon_image=self.goto_image, borderwidth=1, 
                    tags= ('upload',), callback=self.__upload_images)
        self.buttonA.draw()
        self.__custom_graphic_image_view = image_view(self.canvas,32,310)
        self.__custom_graphic_image_view.draw(width=self.canvas.winfo_width()-32,height=self.canvas.winfo_width()-50)
        self.__method = self.CUSTOM_GRAPHIC
        self.__show_custom_image()

    def __remove_custom_graphic_view(self):
        if self.__custom_graphic_image_view:
            self.__custom_graphic_image_view.hide()
            self.buttonA.hide()

    def __draw_similar_graphics_view(self):
        self.__remove_items()
        self.__similar_graphic_list_view.draw()
        self.__method = self.SIMILAR_GRAPHIC
    
    def __remove_similar_graphic_view(self):
        if self.__similar_graphic_list_view:
            self.__similar_graphic_list_view.hide()

    def __remove_items(self):
        self.__remove_extract_hmi_graphic_view()
        self.__remove_custom_graphic_view()
        self.__remove_similar_graphic_view()


    def __upload_images(self,_=None):
        """ Open image in the GUI """
        path = askopenfilename(title='Select a image file',
                               initialdir=os.path.dirname(self.__config.get_recent_path()),filetypes = [("SVG or PNG file", "*.svg *.png")])
        if path == '': return

        self.__config.set_opened_path(path)  # remember path
        # Check if it is a supported image file
        if not Validators.check_svg_or_png(path):
            messagebox.showinfo('Not a valid image file',
                                'This is not a valid svg or png: "{}"\nPlease, select another image file.'.format(path))
            self.__upload_images()  # try to open new image again
            return
        #

        self.__custom_graphic_path = Project_File_Manager.import_image_file(path, self.__project_name) +os.path.sep+ os.path.basename(path)
        self.__show_custom_image()
        self.__change_callback()

    def __show_extracted_image(self):
        self.__wait_for_extracted_graphic()
        
    def __show_custom_image(self):
        if self.__custom_graphic_path is not None:
            image = Project_File_Manager.open_pillow_image(self.__custom_graphic_path)
            self.__custom_graphic_image_view.set_image(np.array(image))


    def hide(self):
        self.__delete()

    def fit_description_in_mutiline(self):
        description_bounds = self.canvas.bbox(self.description_label) 
        second_line_substring = 0 
        split = self.description.split(" ")
        while True :
            second_line_substring = second_line_substring + 1
            multiline_description = ' '.join(split[:second_line_substring])
            self.canvas.delete(self.description_label)
            self.description_label = self.canvas.create_text(24,24, text=multiline_description, anchor=tk.NW, fill="#6F6F6F")
            description_bounds = self.canvas.bbox(self.description_label)
            if (description_bounds[2] - description_bounds[0]) > (self.canvas.winfo_width() - 48):
                break
        second_line_substring = second_line_substring - 1
        self.canvas.delete(self.description_label)
        multiline_description = ' '.join(split[:second_line_substring])+'\n'+' '.join(split[second_line_substring:])
        self.description_label = self.canvas.create_text(24,24, text=multiline_description, anchor=tk.NW, fill="#6F6F6F")
        
    def get_data(self):

        dict_data = {
            'method':self.__method,
            'custom_graphic': {
                'path':self.__custom_graphic_path
            },
            'extract_graphic': self.__extract_hmi_graphic.get_data(),
            'similar_graphic': {}
        }

        return dict_data


    def set_data(self, data):

        if not data:
            return 
    
        self.__method = data['method']
        self.__custom_graphic_path = data['custom_graphic']['path']
        self.__extract_hmi_graphic.set_data(data['extract_graphic'])

        self.__set_method(self.__method)

        self.__extract_hmi_graphic_data = data['extract_graphic']
        



    def export_graphic(self,filename):
        self.__export_graphic[self.__method](filename)
        

    def __export_custom_graphic(self,filename):
        if self.__custom_graphic_path:
            _, extension = os.path.splitext(self.__custom_graphic_path)
            shutil.copy(self.__custom_graphic_path, filename + extension)


    def __export_extracted_graphic(self,filename):
        self.__extract_hmi_graphic.export_graphic(filename)
        

    def __export_similar_graphic(self):
        messagebox.showwarning('Future feature','Coming soon in later versions.')
    
    
    


if __name__ == '__main__':

    root = tk.Tk()

    canvas = tk.Canvas(root)
    canvas.grid(row=0, column=1)
    canvas.config(background='white')
    a = hmi_graphic_view(canvas)

    def redraw(event):
        a.draw()


    canvas.bind('<Configure>', redraw)  # canvas is resized
    
    canvas.update()

    root.mainloop()

