from concurrent.futures import thread
from io import BytesIO
from msilib import CAB
import os
from threading import Thread
import tkinter as tk
import customtkinter as ctk
from PIL import ImageTk, Image

from bin.gui_elements import loading_animation
from bin.gui_parameter_selection import string_selector


try:
    from bin.gui_test_canvas import TestCanvasImage
    from bin.logic_config import Config
    from bin.gui_elements import hover_toggle_button
    from bin.gui_elements import rounded_image_button
    from bin.gui_elements import button_array
    from bin.gui_base64_icons import*
except:
    from gui_test_canvas import TestCanvasImage
    from logic_config import Config
    from gui_elements import hover_toggle_button, rounded_image_button
    from gui_elements import button_array
    from gui_base64_icons import*



class test_on_page:
    def __init__(self, config, rerun_search_func) -> None:
        self.__win = tk.Toplevel()
        self.__test_image_canvas = None 
        self.__busy_canvas = None 
        self.__images_generated = False
        self.__config = config
        self.__rerun_search_func = rerun_search_func
        self.__setup_window()


    def run_after_delay(self, func, delay=500):
        self.__win.after(delay,func)
        

    def images(self, result_image, default_image = None, cw_90_image= None, cw_180_image=None, cw_270_image=None, flipped_image = None
                    , text_result_image = None, template_image:tk.Image = None):
        self.__result_image = result_image
        self.__default_image = default_image
        self.__cw_90_image = cw_90_image 
        self.__cw_180_image = cw_180_image 
        self.__cw_270_image = cw_270_image 
        self.__flipped_image = flipped_image 
        self.__text_result_image= text_result_image 
        self.__template_image = template_image
        self.__images_generated = True
        self.__enable_buttons()


    def __enable_buttons(self):
        self.__hand_button.enable()
        self.__test_template_button.enable()
        self.__result_button.enable()
        self.__default_button.enable()
        if self.__cw_90_image is not None :
            self.__cw_90_button.enable()
        if self.__cw_180_image is not None:
            self.__cw_180_button.enable()
        if self.__cw_270_image is not None:
            self.__cw_270_button.enable()
        if self.__flipped_image is not None:
            self.__flipped_button.enable()
        if self.__text_result_image is not None:
            self.__show_text_button.enable()
        
        self.__template_type_buttons.select(6)
        

    def __setup_window(self):
        self.__win.title("Test on Page")
        self.__win.geometry('1269x779+256+89')
        #self.__win.wm_state(self.__config.get_win_state())
        this_dir = os.path.dirname(os.path.realpath(__file__))
        self.__win.iconbitmap(os.path.join(this_dir, 'logo.ico'))

        self.__win.rowconfigure(0, weight=1)  # make grid cell expandable
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
        self.__placeholder.grid(row=1, column= 0, sticky='nsew')
        self.__placeholder.columnconfigure(0, weight=1)
        self.__placeholder.rowconfigure(0, weight=1)  
        self.__placeholder.config(background="#F5F5F5")
        self.__win.update()


    def show_busy_canvas(self, text=""):
        self.__delete_busy_canvas()
        self.__busy_canvas = tk.Canvas(self.__placeholder)
        self.__busy_canvas.grid(row=0, column=0, sticky='nsew')
        self.__busy_canvas.config(background='#F5F5F5')
        loading = loading_animation(self.__busy_canvas)

        def center_loading(_):
            x = int(self.__busy_canvas.winfo_width()/2)
            y = int(self.__busy_canvas.winfo_height()/2)
            
            loading.draw(x ,y)                
            text_id = self.__busy_canvas.create_text(x, y + 24
                                            , text=text
                                            , fill="#6F6F6F"
                                            , anchor=tk.CENTER
                                            , justify=tk.CENTER )
            _,y1,_,y2 = self.__busy_canvas.bbox(text_id)
            self.__busy_canvas.move(text_id,0,int(abs(y1 - y2)/2))

        self.__busy_canvas.bind("<Configure>", center_loading)
        self.__busy_canvas.update()

    
    def __setup_upper_frame(self, parent):
        self.canvas = tk.Canvas(parent, height=50, width=770,background="white", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=1)
        self.canvas.create_line(0, 0, 70, 50)
        self.canvas.create_line(0, 20, 70, 0, fill="red", dash=(4, 4))
        self.canvas.bind("<Configure>", self.__configure_buttons_canvas)


    def __configure_buttons_canvas(self, _):
        self.canvas.delete("all")

        
        self.__hand_button = hover_toggle_button(self.canvas, hand_tool_mid_blue, hand_tool_mid_dark_gray, hand_tool_mid_light_gray
                                        , anchor = 'w', is_toggle=True)
        self.__hand_button.disable()
        self.canvas.create_window(10, 10, anchor='nw', window=self.__hand_button)
        self.__test_template_button = hover_toggle_button(self.canvas, test_template_blue, test_template_dark_gray, test_template_light_gray
                                        , anchor = 'w', is_toggle=True)
        self.__test_template_button.disable()
        self.canvas.create_window(50, 10, anchor='nw', window=self.__test_template_button)
        self.__selector_tool_buttons = button_array([self.__hand_button, self.__test_template_button ],self.__selector_type)
        self.__selector_tool_buttons.select(0)
        self.canvas.create_line(84,12,84,34, fill="#D5D5D5",width=2)
        self.__default_button = hover_toggle_button(self.canvas, test_default_blue, test_default_gray, test_default_light_gray
                                        , anchor = 'w', is_toggle=True)
        self.__default_button.disable()
        self.canvas.create_window(100, 6, anchor='nw', window=self.__default_button)
        
        self.__cw_90_button = hover_toggle_button(self.canvas, cw_90_mid_blue, cw_90_mid_gray, cw_90_mid_light_gray
                                        , anchor = 'w')
        self.__cw_90_button.disable()
        self.canvas.create_window(200, 10, anchor='nw', window=self.__cw_90_button)
        self.__cw_180_button = hover_toggle_button(self.canvas, cw_180_mid_blue, cw_180_mid_gray, cw_180_mid_light_gray
                                        , anchor = 'w')
        self.__cw_180_button.disable()
        self.canvas.create_window(240, 10, anchor='nw', window=self.__cw_180_button)
        self.__cw_270_button = hover_toggle_button(self.canvas, cw_270_mid_blue, cw_270_mid_gray, cw_270_mid_light_gray
                                        , anchor = 'w')
        self.__cw_270_button.disable()
        self.canvas.create_window(280, 10, anchor='nw', window=self.__cw_270_button)
        self.__flipped_button = hover_toggle_button(self.canvas, flip_mid_blue, flip_mid_gray, flip_mid_light_gray
                                        , anchor = 'w')
        self.__flipped_button.disable()
        self.canvas.create_window(320, 10, anchor='nw', window=self.__flipped_button)
                                   
        
        self.__show_text_button = hover_toggle_button(self.canvas, show_text_blue, show_text_dark_gray, show_text_light_gray
                                        , anchor = 'w', is_toggle=True)
        self.__show_text_button.disable()
        self.canvas.create_window(360, 10, anchor='nw', window=self.__show_text_button)
        self.canvas.create_line(404,12,404,34, fill="#D5D5D5",width=2)
        self.__result_button = hover_toggle_button(self.canvas, test_result_blue, test_result_gray, test_result_light_gray
                                        , anchor = 'w')
        self.__result_button.disable()
        self.canvas.create_window(420, 6, anchor='nw', window=self.__result_button)
        
        self.__template_type_buttons = button_array([self.__default_button
                                                        ,self.__cw_90_button
                                                        ,self.__cw_180_button
                                                        ,self.__cw_270_button
                                                        ,self.__flipped_button
                                                        ,self.__show_text_button
                                                        ,self.__result_button
                                                    ],self.__template_type)
        
        self.canvas.create_line(545,12,545,34, fill="#D5D5D5",width=2)

        selected_accuracy = self.__config.get_scanning_match_score()
        accuracy_options = {'0.7':'High Accuracy'
                                     ,'0.6':'Medium Accuracy'
                                     ,'0.5':'Low Accuracy'}

        # Create a StringVar to store the selected value
        self.selected_option = tk.StringVar()
        self.selected_option.set(accuracy_options[str(selected_accuracy)])  # Set default value
        
        def option_selected(_):
            selected = self.selected_option.get()
            for key, value in accuracy_options.items():
                if value == selected:
                    self.__config.set_scanning_match_score(float(key))
            self.__rerun_search_func()

        # Create the dropdown (Combobox)
        ctk.set_appearance_mode("light")
        self.dropdown = ctk.CTkComboBox(
            self.canvas,
            values=list(accuracy_options.values()),
            variable=self.selected_option,
            state="readonly",
            command=option_selected,
            width=140,
            border_color="#DFDFDF",
            button_color="#DFDFDF",
            text_color="#6F6F6F",
            
        )

        self.dropdown_window = self.canvas.create_window(
            630, 23, window=self.dropdown)


        

        if self.__images_generated:
            self.__enable_buttons()
        


    def __template_type(self, val):

        if val == 0:
            self.__setup_image_canvas(self.__default_image)
        elif val == 1:
            self.__setup_image_canvas(self.__cw_90_image)
        elif val == 2:
            self.__setup_image_canvas(self.__cw_180_image)
        elif val == 3:
            self.__setup_image_canvas(self.__cw_270_image)
        elif val == 4:
            self.__setup_image_canvas(self.__flipped_image)
        elif val == 5:
            self.__setup_image_canvas(self.__text_result_image)
        elif val == 6 and self.__result_image is not None:
            self.__setup_image_canvas(self.__result_image)

      


    def __selector_type(self, selection):

        if self.__test_image_canvas is None:
            return 

        if selection == 0:
            self.__test_image_canvas.start_move_tool()
        elif selection == 1:
            self.__test_image_canvas.start_template_test_tool()
        



    def __setup_image_canvas(self, image):
        if self.__test_image_canvas:
            self.__test_image_canvas.destroy()

        self.show_busy_canvas()

        self.__placeholder.update()
        self.__test_image_canvas = TestCanvasImage(self.__placeholder,image
                                                        ,image_processed_callback=self.__delete_busy_canvas
                                                        ,template_image=self.__template_image)
        self.__test_image_canvas.grid() 
        
        

    def __delete_busy_canvas(self):
        if self.__busy_canvas:
            self.__busy_canvas.grid_forget()
            self.__busy_canvas.destroy()
            self.__busy_canvas = None
