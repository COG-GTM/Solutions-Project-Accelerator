


import cv2
from bin.logic_config import Config
import tkinter as tk
from tkinter import messagebox
from tkinter.colorchooser import askcolor
from tkinter.constants import ANCHOR

from PIL import Image, ImageTk
import numpy as np

from bin.gui_elements import loading_animation, rounded_image_button
from bin.logic_validators import Validators
#try:
from bin.gui_link_view import image_view
from bin.gui_elements import custom_entry
from bin.gui_base64_icons import width_selection 
from bin.gui_base64_icons import goto_dark_gray
""" except:
    from gui_link_view import image_view
    from gui_elements import custom_entry
    from gui_base64_icons import width_selection
    from gui_base64_icons import goto_dark_gray """


class extract_hmi_graphic_view:

    

    def __init__(self, canvas: tk.Canvas, x, y,config:Config, start_graphic_extraction_callback=None, fill_color_callback=None
                    ,stroke_color_callback=None,stroke_width_callback=None, extract_hmi_graphic_data=None, initial_values_callback=None ) -> None:
        self.__canvas = canvas
        self.__start_graphic_extraction_callback_func = start_graphic_extraction_callback
        self.__fill_color_callback_func = fill_color_callback
        self.__stroke_color_callback_func = stroke_color_callback
        self.__stroke_width_callback_func = stroke_width_callback 
        self.__config = config
        self.__x = x
        self.__y = y 
        self.goto_image = tk.PhotoImage(data=goto_dark_gray)
        self.__extract_button = rounded_image_button(self.__canvas, 16, 250, 10, text="EXTRACT", icon_image=self.goto_image, borderwidth=1, 
                    tags= ('extract',), callback=self.__start_creating_graphic)
        self.__image_view = image_view(self.__canvas,self.__x,self.__y + 60)
        self.__image_fill = ImageTk.PhotoImage(Image.new('RGBA', (12, 12), '#FF0000FF'))
        self.__image_stroke = ImageTk.PhotoImage(Image.new('RGBA', (12, 12), '#00FF00FF'))
        self.__image_width_selection = tk.PhotoImage(data=width_selection)
        self.__fill_button = tk.Button(relief=tk.FLAT,image=self.__image_fill,bd=0,command=self.__fill_color_ask_color)
        self.__fill_color_entry = custom_entry(self.__canvas,0,0 + self.__y + 60,enbale_rect=False,width=60,size=9,enable_line=False,
                                        focus_out_callback=self.__fill_color_callback)
        self.__stroke_button = tk.Button(relief=tk.FLAT,image=self.__image_stroke,bd=0,command=self.__stroke_color_ask_color)
        self.__stroke_color_entry = custom_entry(self.__canvas,0,48 + self.__y + 60,enbale_rect=False,width=60,size=9,enable_line=False,
                                        focus_out_callback=self.__stroke_color_callback)
        self.__stroke_width_entry = custom_entry(self.__canvas,0,74 + self.__y + 60,enbale_rect=False,width=60,size=9,enable_line=False,
                                        focus_out_callback=self.__stroke_width_callback)
        self.loading_animation = loading_animation(self.__canvas)
        self.__canvas.bind('<Button-1>',self.__remove_entry_focus)
        self.__loading_values = True
        if extract_hmi_graphic_data:
            self.__set_fill_color(extract_hmi_graphic_data['fill_color'])
            self.__set_stroke_color(extract_hmi_graphic_data['stroke_color'])
            self.__set_stroke_width(extract_hmi_graphic_data['stroke_width']) 
            if initial_values_callback:
                initial_values_callback(extract_hmi_graphic_data['fill_color'],
                                        extract_hmi_graphic_data['stroke_color'],
                                        extract_hmi_graphic_data['stroke_width'])
        else:
            fill,stroke,width = config.get_extracted_hmi_graphic_settings()
            self.__set_fill_color(fill)
            self.__set_stroke_color(stroke)
            self.__set_stroke_width(width)
            if initial_values_callback:
                initial_values_callback(fill,stroke,width)
        
            
        self.__loading_values = False
        self.__image_positioning_offset = 136
        self.__fill_label = None
        self.loading_animation_visible = False
        self.__error_message_string = ''


    def __start_creating_graphic(self,_= None):
        self.__start_graphic_extraction_callback_func()
        


    def start_loading_animation(self):
        self.loading_animation_visible = True
        self.__start_loading_animation()

    def stop_loading_animation(self):
        self.loading_animation_visible = False
        self.loading_animation.stop()

    def __start_loading_animation(self):
        self.loading_animation.draw(self.__x + (self.__canvas.winfo_width() - self.__image_positioning_offset)/2,
                                    self.__y + 60 + (self.__canvas.winfo_width() - self.__image_positioning_offset)/2)
        

    def __remove_entry_focus(self,_=None):
        self.__canvas.focus_set()
        

    def draw(self):
        self.__delete()
        self.__extract_button.draw()
        _, image_view_height = self.__image_view.draw(width=self.__canvas.winfo_width() - self.__image_positioning_offset, 
                                    height=self.__canvas.winfo_width() - self.__image_positioning_offset)
        self.__fill_label = self.__canvas.create_text(self.__canvas.winfo_width()- 96,self.__y + 60, text='Fill', anchor=tk.NW, fill="#6F6F6F")
        self.__fill_button_window = self.__canvas.create_window(self.__canvas.winfo_width()- 96
                                                                ,self.__y + 80, window=self.__fill_button, anchor=tk.NW)
        self.__fill_color_entry.draw(self.__canvas.winfo_width()- 88)
        self.__stroke_label = self.__canvas.create_text(self.__canvas.winfo_width()- 96,self.__y + 108
                                                                , text='Stroke', anchor=tk.NW, fill="#6F6F6F")
        self.__stroke_button_window = self.__canvas.create_window(self.__canvas.winfo_width()- 96,self.__y + 128  
                                                                ,anchor= tk.NW,window=self.__stroke_button)
        self.__stroke_color_entry.draw(self.__canvas.winfo_width()- 88)
        self.__stroke_width_entry.draw(self.__canvas.winfo_width()- 88)
        self.__image_width_selection_id = self.__canvas.create_image(self.__canvas.winfo_width()- 96,self.__y + 156,image=self.__image_width_selection,anchor=tk.NW)
        self.__error_message_id = self.__canvas.create_text(self.__x + 10,self.__y + image_view_height + 70, text=self.__error_message_string, fill="#FF0000", anchor=tk.NW)
        
        self.__canvas.after(100,self.__remove_entry_focus)
        if self.loading_animation_visible:
            self.start_loading_animation()
        else:
            self.stop_loading_animation()


    def __fill_color_ask_color(self):
        color = askcolor(parent=self.__canvas,
                         title='Choose a fill color')
        
        if color[1] is None:
            return

        self.__set_fill_color(color[1].upper()[1:])
        self.__fill_color_callback_func(color[1].upper()[1:])

    def __set_fill_color(self, color_string):
        self.__image_fill = ImageTk.PhotoImage(Image.new('RGBA', (12, 12), '#'+color_string+'FF'))
        self.__fill_button.configure(image=self.__image_fill)
        self.__fill_color_entry.entry.delete(0,tk.END)
        self.__fill_color_entry.entry.insert(0,color_string)

    def __stroke_color_ask_color(self):
        color = askcolor(parent=self.__canvas,
                         title='Choose a stroke color')

        if color[1] is None:
            return

        self.__set_stroke_color(color[1].upper()[1:])
        
        self.__stroke_color_callback_func(color[1].upper()[1:])
        
    def __set_stroke_color(self, color_string):
        self.__image_stroke = ImageTk.PhotoImage(Image.new('RGBA', (12, 12), '#'+color_string+'FF'))
        self.__stroke_button.configure(image=self.__image_stroke)
        self.__stroke_color_entry.entry.delete(0,tk.END)
        self.__stroke_color_entry.entry.insert(0,color_string)


    def __set_stroke_width(self, width_string):
       
        self.__stroke_width_entry.entry.delete(0,tk.END)
        self.__stroke_width_entry.entry.insert(0,width_string)


    def __fill_color_callback(self):
        val = self.__fill_color_entry.entry.get()

        if self.__loading_values:
            return 

        if Validators.check_hex_rgb_color(val):
            self.__fill_color_callback_func(val)
            self.__image_fill = ImageTk.PhotoImage(Image.new('RGBA', (12, 12), '#'+val+'FF'))
            self.__fill_button.configure(image=self.__image_fill)
        else:
            messagebox.showerror('Invalid hex color code', 'The fill color hex code entered is invalid. '
                                                            + 'Please enter a valid hex color code.')


    def __stroke_color_callback(self):
        val = self.__stroke_color_entry.entry.get()

        if self.__loading_values:
            return 

        if Validators.check_hex_rgb_color(val):
            self.__stroke_color_callback_func(val)
            self.__image_stroke = ImageTk.PhotoImage(Image.new('RGBA', (12, 12), '#'+val+'FF'))
            self.__stroke_button.configure(image=self.__image_stroke)
        else:
            messagebox.showerror('Invalid hex color code', 'The stroke color hex code entered is invalid. '
                                                            + 'Please enter a valid hex color code.')

    def set_hmi_graphic_image(self, image, error_message):
        np_image = np.array(image)
        self.__hmi_graphic_image = cv2.cvtColor(np_image,cv2.COLOR_RGBA2BGRA)
        self.__canvas.itemconfig(self.__error_message_id,text=error_message)
        self.__image_view.set_image(self.__hmi_graphic_image)
        self.stop_loading_animation()


    def __stroke_width_callback(self):
        val = self.__stroke_width_entry.entry.get()

        if self.__loading_values:
            return  

        self.__stroke_width_callback_func(val)



    def __delete(self):
        if self.__fill_label is None:
            return 

        self.__extract_button.hide()
        self.__image_view.hide()
        self.__canvas.delete(self.__fill_label)
        self.__canvas.delete(self.__fill_button_window)
        self.__fill_color_entry.hide()
        self.__canvas.delete(self.__stroke_label)
        self.__canvas.delete(self.__stroke_button_window)
        self.__stroke_color_entry.hide()
        self.__stroke_width_entry.hide()
        self.__canvas.delete(self.__image_width_selection_id)
        self.__canvas.delete(self.__error_message_id)


    def hide(self):
        self.__delete()
    
if __name__ == '__main__':

    root = tk.Tk()

    svg = '''
    <svg width="100" height="100" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="50" cy="50" r="47" fill="#C4C4C4" stroke="black" stroke-width="6"/>
    </svg>
    '''

    canvas = tk.Canvas(root)
    canvas.grid()
    canvas.config(background='white', highlightthickness = 0,width=500,height=1000)
    v = extract_hmi_graphic_view(canvas,0,0)

    def draw(event):

        v.draw()

    canvas.bind('<Configure>', draw)

    root.mainloop()

    

