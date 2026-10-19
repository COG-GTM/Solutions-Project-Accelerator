import tkinter as tk

try:
    from bin.gui_base64_icons import approval_background
except ImportError as error:
    from gui_base64_icons import approval_background


class bottom_approval_view():
    def __init__(self, canvas: tk.Canvas, x, y, vbar,redraw_callback):
        self.vbar = vbar
        self.__x = x
        self.__y = y
        self.__canvas = canvas
        self.__background_image = tk.PhotoImage(data=approval_background)
        self.__background_id = None
        self.__wait_after_scroll = None 
        self.__closed = True
        self.__y_offset = 0 
        self.__redraw_callback_func = redraw_callback
        self.__discard_button = rectangle_canvas_button('Discard',self.__canvas, callback=self.__on_click_discard)
        self.__discard_all_button = rectangle_canvas_button('Discard All',self.__canvas, callback=self.__on_click_discard_all)
        self.__accept_button = rectangle_canvas_button('Accept',self.__canvas, callback=self.__on_click_accept)
        self.__accept_all_button = rectangle_canvas_button('Accept All',self.__canvas, callback=self.__on_click_accept_all)
        #self.__accept_all_button.disable()
        
        # Progress bar related variables
        self.__show_progress_bar = False
        self.__percentage = 0.0
        self.__progress_text = ''
        self.__progress_bar = None
        self.__progress_bar_background = None
        self.__progress_info = None
        self.__percentage_info = None


    def setup_callbacks(self, on_discard_callback,on_accept_callback,on_accept_all_callback,on_discard_all_callback=None):
        self.__on_discard_callback = on_discard_callback
        self.__on_accept_callback = on_accept_callback
        self.__on_accept_all_callback = on_accept_all_callback
        self.__on_discard_all_callback = on_discard_all_callback


    def __on_click_discard(self):
        if self.__on_discard_callback:
            self.__on_discard_callback()


    def __on_click_accept(self):
        if self.__on_accept_callback:
            self.__on_accept_callback()


    def __on_click_accept_all(self):
        if self.__on_accept_all_callback:
            self.__on_accept_all_callback()


    def __on_click_discard_all(self):
        if self.__on_discard_all_callback:
            self.__on_discard_all_callback()


    def enable_reject(self):
        self.__discard_button.enable()

    
    def enable_accept(self):
        self.__accept_button.enable()

    
    def enable_accept_all(self):
        self.__accept_all_button.enable()


    def disable_reject(self):
        self.__discard_button.disable()

    
    def disable_accept(self):
        self.__accept_button.disable()

    
    def disable_accept_all(self):
        self.__accept_all_button.disable()


    def enable_discard_all(self):
        self.__discard_all_button.enable()


    def disable_discard_all(self):
        self.__discard_all_button.disable()


    def set_progress_info(self, percentage, progress_text):
        """Set progress bar information"""
        self.__percentage = percentage
        self.__progress_text = progress_text
        def func():
            if self.__show_progress_bar:
                self.__redraw_callback_func()
        self.__canvas.after(0, func)


    def show_progress_bar(self):
        """Show the progress bar"""
        def func():
            self.disable_accept_all()
            self.__show_progress_bar = True
            self.__redraw_callback_func()

        self.__canvas.after(0, func)


    def hide_progress_bar(self):
        """Hide the progress bar"""
        def func():
            self.enable_accept_all()
            self.__show_progress_bar = False
            self.__redraw_callback_func()
        
        self.__canvas.after(0, func)



    def handle_scroll(self,x0, x1):
        
        self.__delete_static_elements()
        self.__discard_button.hide()
        self.__discard_all_button.hide()
        self.__accept_button.hide()
        self.__accept_all_button.hide()
        if self.vbar:
            self.vbar.set(x0, x1)
        if self.__wait_after_scroll:
            self.__canvas.after_cancel(self.__wait_after_scroll)
        self.__wait_after_scroll = self.__canvas.after(1000, self.draw)


    def draw(self,x=0,y=None,canvas=None, vbar=None):
        if vbar:
            self.vbar = vbar
        if canvas:
            self.__canvas = canvas
        self.__delete_static_elements()

        if self.__closed: 
            return

        x = self.__x + x
        if y is not None:
            self.__y_offset = y
        x_offset = self.__canvas.canvasx(self.__canvas.winfo_x(),1)+self.__canvas.winfo_width()
        y_offset = self.__canvas.canvasy(self.__canvas.winfo_y(),1)+self.__canvas.winfo_height() 

        
        self.__background_id = self.__canvas.create_image(self.__canvas.winfo_width() + 10,
                                                            y_offset - self.__y_offset,
                                                            image=self.__background_image,
                                                            anchor=tk.SE)

        # Draw progress bar if enabled
        if self.__show_progress_bar:
            self.__draw_progress_bar(y_offset, x_offset)
            
        button_y_offset = y_offset - self.__y_offset - 50

        self.__discard_button.draw(self.__canvas.winfo_width() - 293, button_y_offset)
        self.__discard_all_button.draw(self.__canvas.winfo_width() - 227, button_y_offset)
        self.__accept_button.draw(self.__canvas.winfo_width() - 142, button_y_offset)
        self.__accept_all_button.draw(self.__canvas.winfo_width() - 79, button_y_offset)
        
        

    def __draw_progress_bar(self, y_offset, x_offset):
        """Draw the progress bar similar to primary_progress_banner"""
        
        # Progress bar background
        self.__progress_bar_background = self.__canvas.create_rectangle(x_offset - 16,
                                                                        y_offset - 85 - self.__y_offset,
                                                                        x_offset - 309,
                                                                        y_offset - 80 - self.__y_offset,
                                                                        fill='#EFEFEF',
                                                                        width=0)
        
        # Progress bar fill
        self.__progress_bar = self.__canvas.create_rectangle(x_offset - 16 - int(293 * (1 - self.__percentage)),
                                                            y_offset - 85 - self.__y_offset,
                                                            x_offset - 309,
                                                            y_offset - 80 - self.__y_offset,
                                                            fill='#00AEEF',
                                                            width=0)
        return
        # Progress text
        self.__progress_info = self.__canvas.create_text(x_offset - 325,
                                                        y_offset - 90 - self.__y_offset,
                                                        text=self.__progress_text,
                                                        anchor=tk.SW, 
                                                        fill='#777777')
        
        # Percentage text
        self.__percentage_info = self.__canvas.create_text(x_offset - 60,
                                                          y_offset - 90 - self.__y_offset,
                                                          text='{:.1f} %'.format(self.__percentage*100),
                                                          anchor=tk.SE, 
                                                          fill='#777777')


    def __delete_static_elements(self):
        if self.__background_id == None:
            return  

        self.__canvas.delete(self.__background_id)
        
        # Delete progress bar elements if they exist
        if self.__progress_bar_background:
            self.__canvas.delete(self.__progress_bar_background)
            self.__progress_bar_background = None
        if self.__progress_bar:
            self.__canvas.delete(self.__progress_bar)
            self.__progress_bar = None
        if self.__progress_info:
            self.__canvas.delete(self.__progress_info)
            self.__progress_info = None
        if self.__percentage_info:
            self.__canvas.delete(self.__percentage_info)
            self.__percentage_info = None



    def hide(self):
        self.__closed = True
        self.__discard_button.hide()
        self.__redraw_callback_func()
        

    def show(self):
        self.__closed = False
        self.__redraw_callback_func()


    def is_shown(self):
        return not self.__closed 


class rectangle_canvas_button():
    def __init__(self,text, canvas:tk.Canvas, callback=None, padding=8, width=None ) -> None:
        self.__text = text
        self.__canvas = canvas
        self.__on_click_callback = callback
        self.__enabled = True
        self.__add_text = None
        self.__x = 0
        self.__y = 0
        self.__padding = padding
        self.__width = width

    


    def draw(self, x=None, y=None):
        padding = self.__padding
        self.__delete_elements()
        
        if x:
            self.__x = x
        else:
            x = self.__x

        if y:
            self.__y = y
        else:
            y = self.__y
        
        if self.__enabled:
            self.__add_text = self.__canvas.create_text(x, y,  
                                                                text=self.__text, 
                                                                font=('Arial',10,'normal'), 
                                                                anchor=tk.SW, 
                                                                fill="#505050")
        else:
            self.__add_text = self.__canvas.create_text(x, y,  
                                                                text=self.__text, 
                                                                font=('Arial',10,'normal'), 
                                                                anchor=tk.SW, 
                                                                fill="#C0C0C0")

        bounds = self.__canvas.bbox(self.__add_text)
        if not self.__width:
            self.__add_rect = self.__canvas.create_rectangle(bounds[0]-padding ,bounds[1] -padding,bounds[2]+ padding ,bounds[3]+ padding,fill='#E0E0E0', width = 0, tags=('add_text_location'))
        else:
            self.__add_rect = self.__canvas.create_rectangle(int((bounds[0]+bounds[2] -self.__width)/2) ,bounds[1] -padding, int((bounds[0]+bounds[2] +self.__width)/2) ,bounds[3]+ padding,fill='#E0E0E0', width = 0, tags=('add_text_location'))
        self.__canvas.tag_raise(self.__add_text)
        

        self.__canvas.tag_bind(self.__add_rect,'<Enter>', self.__on_enter)
        self.__canvas.tag_bind(self.__add_rect,'<Leave>', self.__on_leave)
        self.__canvas.tag_bind(self.__add_text,'<Enter>', self.__on_enter)
        self.__canvas.tag_bind(self.__add_text,'<Leave>', self.__on_leave)
        self.__canvas.tag_bind(self.__add_rect,'<Button-1>', self.__on_click)
        self.__canvas.tag_bind(self.__add_text,'<Button-1>', self.__on_click)

    
    def change_text(self, new_text):
        self.__text = new_text
        self.__canvas.itemconfig(self.__add_text, text=new_text)


    def enable(self):
        self.__enabled = True 

        self.__canvas.itemconfig(self.__add_text,fill="#505050")


    def disable(self):
        self.__enabled = False 

        self.__canvas.itemconfig(self.__add_text,fill="#C0C0C0")
    
    
    def __delete_elements(self):
        
        if self.__add_text:
            self.__canvas.delete(self.__add_text)
            self.__canvas.delete(self.__add_rect)

        


    def hide(self):
        self.__delete_elements()
        


    def __on_enter(self,_):
        if not self.__enabled:
            return
        self.__canvas.itemconfig(self.__add_rect, fill='#C5C5C5')


    def __on_leave(self,_):
        self.__canvas.itemconfig(self.__add_rect, fill='#E0E0E0')

    def __on_click(self,_):
        if not self.__enabled:
            return 
        
        if self.__on_click_callback:
            self.__on_click_callback()
