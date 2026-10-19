

import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageTk
import PyTaskbar
import cython



try:
    from .gui_approval_view import bottom_approval_view
    from .gui_base64_icons import (small_progress_banner_background, medium_progress_banner_background
                                   ,large_progress_banner_background, scanning_refresh_button
                                   ,scanning_cancel_button)
    from .gui_warning_banner import warning_banner
except ImportError as error:
    from gui_base64_icons import (small_progress_banner_background, medium_progress_banner_background
                                    ,large_progress_banner_background, scanning_refresh_button
                                    ,scanning_cancel_button)
    from gui_warning_banner import warning_banner
    from gui_approval_view import bottom_approval_view


class banner_handler():
    def __init__(self, canvas, x,y,vbar,refresh_list_callback,both_direction_scroll=False) -> None:
        self.vbar = vbar
        self.both_direction_scroll = both_direction_scroll
        self.primary_progress_banner = primary_progress_banner(canvas,0,0,vbar,self.draw,refresh_list_callback)
        self.warning_banner = warning_banner(canvas,0,0,vbar,self.draw)
        self.bottom_approval_view = bottom_approval_view(canvas,0,0,vbar,self.draw)
        self.secondary_progress_banner = secondary_progress_banner(canvas,0,0,vbar,self.draw)
        canvas.config(yscrollcommand=self.__handle_scroll)
        if both_direction_scroll:
            canvas.config(xscrollcommand=self.__handle_scroll)

    def draw(self,canvas=None, vbar=None):
        scan_progress_height = self.primary_progress_banner.draw(canvas=canvas, vbar=vbar)
        other_task_progress_height = self.secondary_progress_banner.draw(y=scan_progress_height, canvas=canvas, vbar=vbar)
        self.warning_banner.draw(y=other_task_progress_height+scan_progress_height, canvas=canvas, vbar=vbar)
        self.bottom_approval_view.draw(canvas=canvas, vbar=vbar)

        if canvas:
            canvas.config(yscrollcommand=self.__handle_scroll)
            
        if canvas and self.both_direction_scroll:
            canvas.config(xscrollcommand=self.__handle_scroll)


    def __handle_scroll(self,x0, x1):
        
        self.primary_progress_banner.handle_scroll(x0, x1)
        self.warning_banner.handle_scroll(x0, x1)
        self.secondary_progress_banner.handle_scroll(x0, x1)
        self.bottom_approval_view.handle_scroll(x0, x1)
        if self.vbar:
            self.vbar.set(x0, x1)



class primary_progress_banner():
    def __init__(self, canvas: tk.Canvas, x, y, vbar,redraw_callback,refresh_list_callback=None):
        self.vbar = vbar
        self.__x = x
        self.__y = y
        self.__canvas = canvas
        self.__cancel_scan_funcs = []
        self.__small_background_image = tk.PhotoImage(data=small_progress_banner_background)
        self.__medium_background_image = tk.PhotoImage(data=medium_progress_banner_background)
        self.__large_background_image = tk.PhotoImage(data=large_progress_banner_background)
        self.__refresh_button_image = tk.PhotoImage(data=scanning_refresh_button)
        self.__cancel_button_image = tk.PhotoImage(data=scanning_cancel_button)
        self.__background_image = self.__small_background_image
        
        im_close = Image.new('RGBA', (15, 15), '#00000000')
        im_open = Image.new('RGBA', (15, 15), '#00000000')
        draw_close = ImageDraw.Draw(im_close)
        draw_close.line([(0, 4), (7, 11), (14, 4) ], fill=(150,150,150,255),width=2)
        im_open= im_close.rotate(180)
        im_close_pop_up = Image.new('RGBA', (15, 15), '#00000000')
        draw_close_pop_up = ImageDraw.Draw(im_close_pop_up)
        draw_close_pop_up.line([(2, 2), (11, 11)], fill=(150,150,150,255),width=2)
        draw_close_pop_up.line([(11, 3), (2, 12)], fill=(150,150,150,255),width=2)

        im_close_pop_up_disabled = Image.new('RGBA', (15, 15), '#00000000')
        draw_close_pop_up_disabled = ImageDraw.Draw(im_close_pop_up_disabled)
        draw_close_pop_up_disabled.line([(2, 2), (11, 11)], fill=(220,220,220,255),width=2)
        draw_close_pop_up_disabled.line([(11, 3), (2, 12)], fill=(220,220,220,255),width=2)
        
        
        self.__img_open = ImageTk.PhotoImage(im_open)
        self.__img_close = ImageTk.PhotoImage(im_close) 
        self.__im_close_pop_up = ImageTk.PhotoImage(im_close_pop_up)
        self.__im_close_pop_up_disabled = ImageTk.PhotoImage(im_close_pop_up_disabled)
        self.__background = None
        self.__open_close_button = tk.Button(self.__canvas,relief='flat',bd=0,image=self.__img_open,command=self.__handle_open_close,background="white")
        self.__close_pop_up_button = tk.Button(self.__canvas,relief='flat',bd=0,image=self.__im_close_pop_up_disabled,command=None,background="white")
        
        self.__offset = -15
        self.__opened = False
        self.__first_progress_set = False
        self.__has_secondary_scan = False
        self.__has_error = False
        self.__error_shown = False
        self.__error_title = ''
        self.__error_description = ''
        self.__wait_after_scroll = None 
        self.__percentage = 0.0
        self.__pno = '-'
        self.__page_count = '-' 
        self.__primary_scan_count = '-'
        self.__secondary_scan_count = '-'
        self.__primary_scan_name = ''
        self.__secondary_scan_name = ''
        self.__found_label = None
        self.__closed = True
        self.__redraw_callback_func = redraw_callback
        self.__refresh_list_callback = refresh_list_callback
        self.__refresh_button_id = None
        self.__cancel_button_id = None
        self.__secondary_scan_name_label = None
        root = self.__canvas.winfo_toplevel()
        self.__prog = PyTaskbar.TaskbarProgress(int(root.wm_frame(), 16))





    def handle_scroll(self,x0, x1):
        self.__delete_static_elements()
        if self.__wait_after_scroll:
            self.__canvas.after_cancel(self.__wait_after_scroll)
        self.__wait_after_scroll = self.__canvas.after(1000, self.draw)
        


        
    def set_info(self, percentage,pno,page_count,names_of_scans,count_of_scans, error_description, cancel_scan_funcs):
        self.__percentage = percentage
        self.__pno = pno
        self.__page_count = page_count
        self.__primary_scan_name = names_of_scans[0]
        self.__primary_scan_count = count_of_scans[0]
        self.__cancel_scan_funcs = cancel_scan_funcs
        if not self.__first_progress_set and self.__percentage != 0:
            self.__prog.set_progress_type(PyTaskbar.ProgressType.NORMAL)
            self.__first_progress_set = True
        self.__prog.set_progress(int(percentage*100))
        if self.__percentage == 1 and not self.__opened:
            self.__prog.flash_done()
            self.__handle_open_close()
        if len(count_of_scans) > 1:
            self.__has_secondary_scan = True
            self.__secondary_scan_name = names_of_scans[1]
            self.__secondary_scan_count = count_of_scans[1]
        if error_description:
            self.__has_error = True
            self.__prog.set_progress_type(PyTaskbar.ProgressType.ERROR)
            self.show_error('Failed to Run Scan',error_description)
        else:
            self.__has_error = False
            self.__error_shown = False 
            self.__redraw_callback_func()


    def __cancel_scan_callback(self):
        for func in self.__cancel_scan_funcs:
            func()
        


    def show_error(self, title, description):
        self.__error_title = title
        self.__error_description = description
        self.__has_error = True 
        self.enable_close_pop_up()
        self.__redraw_callback_func()



    def draw(self,x=0,y=0,canvas=None, vbar=None):
        if vbar:
            self.vbar = vbar

        if canvas:
            self.__canvas = canvas

        self.__delete_static_elements()

        if self.__closed: 
            return 0
        
        

        x = self.__x + x
        y = self.__y + y
        x_offset = self.__canvas.canvasx(self.__canvas.winfo_x(),1)+self.__canvas.winfo_width()
        y_offset = self.__canvas.canvasy(self.__canvas.winfo_y(),1)+self.__canvas.winfo_height() 
        self.__background = self.__canvas.create_image(x_offset + 10,y_offset,image=self.__background_image,anchor=tk.SE)
        self.__open_close_window = self.__canvas.create_window(x_offset - 34,y_offset - 50 - self.__offset,window=self.__open_close_button,anchor=tk.SE)
        self.__close_pop_up_window = self.__canvas.create_window(x_offset - 15,y_offset - 50 - self.__offset,window=self.__close_pop_up_button,anchor=tk.SE)
        self.__progress_bar_background = self.__canvas.create_rectangle(x_offset - 15,
                                                                            y_offset - 45 - self.__offset,
                                                                            x_offset - 325,
                                                                            y_offset - 40 - self.__offset,
                                                                            fill='#EFEFEF',
                                                                            width=0)

        
        self.__show_progress(y_offset, x_offset)
        self.__show_error(y_offset, x_offset)

        


        
        if not self.__opened:
            return 50
        
        offset = 30 if self.__has_secondary_scan else 13
        if self.__percentage == 1:

            
            self.__refresh_button_id = self.__canvas.create_image(x_offset - 16,
                                                                            y_offset + offset - self.__offset,
                                                                            image=self.__refresh_button_image,
                                                                            anchor=tk.SE,
                                                                            tags='refresh_button')
        
            self.__canvas.tag_bind('refresh_button', '<Button-1>', 
                                   lambda event: self.__refresh_list_callback() if self.__refresh_list_callback else None)
        elif float(self.__percentage) < 1 and not self.__has_error and self.__page_count != '-' and float(self.__page_count) > 0:
            self.__cancel_button_id = self.__canvas.create_image(x_offset - 16,
                                                                            y_offset + offset - self.__offset,
                                                                            image=self.__cancel_button_image,
                                                                            anchor=tk.SE,
                                                                            tags='cancel_button')
            self.__canvas.tag_bind('cancel_button', '<Button-1>', 
                                   lambda event: self.__cancel_scan_callback() if self.__cancel_scan_callback else None)

        self.__found_label = self.__canvas.create_text(x_offset - 325,
                                                                            y_offset - 20 - self.__offset,
                                                                            text='Found', font=('Arial', 10, 'bold'),
                                                                            anchor=tk.SW,
                                                                            fill='#777777')
        self.__primary_scan_name_label = self.__canvas.create_text(x_offset - 320,
                                                                            y_offset + 5 - self.__offset,
                                                                            text=self.__primary_scan_name,
                                                                            anchor=tk.SW,
                                                                            fill='#777777')
        self.__primary_scan_count_label = self.__canvas.create_text(x_offset - 150,
                                                                            y_offset + 5 - self.__offset,
                                                                            text=self.__primary_scan_count,
                                                                            anchor=tk.SE,
                                                                            fill='#777777')
        
        
        
        if not self.__has_secondary_scan:
            return 105
        
        self.__secondary_scan_name_label = self.__canvas.create_text(x_offset - 320,
                                                                            y_offset + 30 - self.__offset,
                                                                            text=self.__secondary_scan_name,
                                                                            anchor=tk.SW,
                                                                            fill='#777777')
        self.__secondary_scan_count_label = self.__canvas.create_text(x_offset - 150,
                                                                            y_offset + 30 - self.__offset,
                                                                            text=self.__secondary_scan_count,
                                                                            anchor=tk.SE,
                                                                            fill='#777777')
        
        
        return 122

    def __show_progress(self, y_offset, x_offset):
        if not self.__has_error:
            self.__progress_bar = self.__canvas.create_rectangle(x_offset - 15 - int(310 * (1 - self.__percentage)),
                                                                y_offset - 45 - self.__offset,
                                                                x_offset - 325,
                                                                y_offset - 40 - self.__offset,
                                                                fill='#00AEEF',
                                                                width=0)
            self.__page_info = self.__canvas.create_text(x_offset - 325,
                                                                y_offset - 50 - self.__offset,
                                                                text='Page {page}/{page_count}'.format(page=self.__pno,
                                                                page_count=self.__page_count),
                                                                anchor=tk.SW, 
                                                                fill='#777777')
            self.__percentage_info = self.__canvas.create_text(x_offset - 60,
                                                                y_offset - 50 - self.__offset,
                                                                text='{:.1f} %'.format(self.__percentage*100),
                                                                anchor=tk.SE, 
                                                                fill='#777777')

    def __show_error(self, y_offset, x_offset):
        if self.__has_error:
            self.__progress_bar = self.__canvas.create_rectangle(x_offset - 15,
                                                                y_offset - 45 - self.__offset,
                                                                x_offset - 325,
                                                                y_offset - 40 - self.__offset,
                                                                fill='#FF0000',
                                                                width=0)

            self.__page_info = self.__canvas.create_text(x_offset - 325,
                                                                y_offset - 50 - self.__offset,
                                                                text='Error scanning pages',
                                                                anchor=tk.SW, 
                                                                fill='#777777')
            self.__percentage_info = self.__canvas.create_text(x_offset - 60,
                                                                y_offset - 50 - self.__offset,
                                                                text='-.-- %',
                                                                anchor=tk.SE, 
                                                                fill='#777777')
            if not self.__error_shown:
                self.__error_shown = True
                messagebox.showerror(self.__error_title, self.__error_description)
                
        


    def __delete_static_elements(self):
        if self.__background == None:
            return  

        self.__canvas.delete(self.__background)
        self.__canvas.delete(self.__open_close_window)
        self.__canvas.delete(self.__close_pop_up_window)
        self.__canvas.delete(self.__progress_bar_background)
        self.__canvas.delete(self.__progress_bar)
        self.__canvas.delete(self.__page_info)
        self.__canvas.delete(self.__percentage_info)

        if self.__found_label == None:
            return

        self.__canvas.delete(self.__found_label)
        self.__canvas.delete(self.__primary_scan_name_label)
        self.__canvas.delete(self.__primary_scan_count_label)

        if self.__refresh_button_id:
            self.__canvas.delete(self.__refresh_button_id)
            self.__refresh_button_id = None

        if self.__cancel_button_id:
            self.__canvas.delete(self.__cancel_button_id)
            self.__cancel_button_id = None

        if self.__secondary_scan_name_label == None:
            return
        
        self.__canvas.delete(self.__secondary_scan_name_label)
        self.__canvas.delete(self.__secondary_scan_count_label)

    def __handle_open_close(self):
        #self.__delete_static_elements()
        if not self.__opened and not self.__has_secondary_scan:
            self.__background_image = self.__medium_background_image
            self.__open_close_button.config(image=self.__img_close)
            self.__offset = 42
            self.__opened = True
            self.__redraw_callback_func()
        elif not self.__opened and self.__has_secondary_scan:
            self.__background_image = self.__large_background_image
            self.__open_close_button.config(image=self.__img_close)
            self.__offset = 59
            self.__opened = True
            self.__redraw_callback_func()
        else:
            self.__background_image = self.__small_background_image
            self.__open_close_button.config(image=self.__img_open)
            self.__offset = -15
            self.__opened = False
            self.__redraw_callback_func()


    def enable_close_pop_up(self):
        self.__close_pop_up_button.config(image=self.__im_close_pop_up)
        self.__close_pop_up_button.configure(command=self.__handle_close)
        self.__canvas.delete(self.__cancel_button_id)


    def disable_close_pop_up(self):
        self.__close_pop_up_button.config(image=self.__im_close_pop_up_disabled)
        self.__close_pop_up_button.configure(command=self.__empty)

    def __empty(self):
        pass


    def __handle_close(self):
        self.__closed = True
        self.disable_close_pop_up()
        self.__redraw_callback_func()
        self.__percentage = 0.0
        self.__pno = '-'
        self.__page_count = '-' 
        
        

    def show(self):
        self.__prog.reset()
        self.__prog.set_progress_type(PyTaskbar.ProgressType.INDETERMINATE)
        self.__first_progress_set = False
        self.__closed = False
        self.__redraw_callback_func()

    def is_shown(self):
        return not self.__closed 
            

class secondary_progress_banner():
    def __init__(self, canvas: tk.Canvas, x, y, vbar, redraw_callback):
        self.vbar = vbar
        self.__x = x
        self.__y = y
        self.__canvas = canvas
        self.__background_image = tk.PhotoImage(data=small_progress_banner_background)
        
        
        im_close_pop_up = Image.new('RGBA', (15, 15), '#00000000')
        draw_close_pop_up = ImageDraw.Draw(im_close_pop_up)
        draw_close_pop_up.line([(2, 2), (11, 11)], fill=(150,150,150,255),width=2)
        draw_close_pop_up.line([(11, 3), (2, 12)], fill=(150,150,150,255),width=2)

        im_close_pop_up_disabled = Image.new('RGBA', (15, 15), '#00000000')
        draw_close_pop_up_disabled = ImageDraw.Draw(im_close_pop_up_disabled)
        draw_close_pop_up_disabled.line([(2, 2), (11, 11)], fill=(220,220,220,255),width=2)
        draw_close_pop_up_disabled.line([(11, 3), (2, 12)], fill=(220,220,220,255),width=2)
        
        self.__has_error = False
        self.__error_shown = False
        self.__error_title = ''
        self.__error_description = ''
        
        self.__im_close_pop_up = ImageTk.PhotoImage(im_close_pop_up)
        self.__im_close_pop_up_disabled = ImageTk.PhotoImage(im_close_pop_up_disabled)
        self.__background = None
        self.__close_pop_up_button = tk.Button(self.__canvas,relief='flat',bd=0,image=self.__im_close_pop_up_disabled,command=None,background="white")
        self.__offset = -15
        self.__wait_after_scroll = None 
        self.__percentage = 0.0
        self.__task = '-'
        self.__object_name = '-' 
        self.__closed = True
        self.__redraw_callback_func = redraw_callback
        self.__y_offset = 0
        self.__close_allowed = False
        self.__close_func = None 


    def handle_scroll(self,x0, x1):
        
        self.__delete_static_elements()
        if self.vbar:
            self.vbar.set(x0, x1)
        if self.__wait_after_scroll:
            self.__canvas.after_cancel(self.__wait_after_scroll)
        self.__wait_after_scroll = self.__canvas.after(1000, self.draw)
        
        

        
    def set_info(self, percentage,task,object_name='', error_description=''):
        self.__percentage = percentage
        self.__task = task
        self.__object_name = object_name
        if error_description:
            self.__has_error = True 
            self.show_error('Failed to Run Task',error_description)
        else:
            self.__has_error = False
            self.__error_shown = False 
            self.__redraw_callback_func()


    def show_error(self, title, description):
        self.__error_title = title
        self.__error_description = description
        self.__has_error = True 
        self.enable_close_pop_up()
        self.__redraw_callback_func()


    def draw(self,x=0,y=None,canvas=None, vbar=None):
        if vbar:
            self.vbar = vbar
        if canvas:
            self.__canvas = canvas
        self.__delete_static_elements()

        if self.__closed: 
            return 0

        x = self.__x + x
        if y is not None:
            self.__y_offset = y
        x_offset = self.__canvas.canvasx(self.__canvas.winfo_x(),1)+self.__canvas.winfo_width()
        y_offset = self.__canvas.canvasy(self.__canvas.winfo_y(),1)+self.__canvas.winfo_height() 
        self.__background = self.__canvas.create_image(x_offset + 10,y_offset - self.__y_offset,image=self.__background_image,anchor=tk.SE)
        self.__close_pop_up_button = tk.Button(self.__canvas,relief='flat',bd=0,image=self.__im_close_pop_up_disabled,command=None,background="white")
        if self.__close_allowed: self.enable_close_pop_up()
        self.__close_pop_up_window = self.__canvas.create_window(x_offset - 15,y_offset - 50 - self.__y_offset - self.__offset,window=self.__close_pop_up_button,anchor=tk.SE)
        self.__progress_bar_background = self.__canvas.create_rectangle(x_offset - 15,
                                                                            y_offset - 45 - self.__y_offset - self.__offset,
                                                                            x_offset - 325,
                                                                            y_offset - 40 - self.__y_offset - self.__offset,
                                                                            fill='#EFEFEF',
                                                                            width=0)
        self.__show_progress(y_offset, x_offset)
        self.__show_error(y_offset, x_offset)
        
        
        return 50


    def __show_progress(self, y_offset, x_offset):
        if not self.__has_error:
            self.__progress_bar = self.__canvas.create_rectangle(x_offset - 15 - int(310 * (1 - self.__percentage)),
                                                                    y_offset - 45 - self.__y_offset - self.__offset,
                                                                    x_offset - 325,
                                                                    y_offset - 40 - self.__y_offset - self.__offset,
                                                                    fill='#00AEEF',
                                                                    width=0)
            if self.__object_name:
                text_to_show = '{task} for {object_name}'.format(task=self.__task,
                                                                    object_name=self.__object_name)
            else:
                text_to_show = self.__task
            self.__page_info = self.__canvas.create_text(x_offset - 325,
                                                                    y_offset - 50 - self.__y_offset - self.__offset,
                                                                    text=text_to_show,
                                                                    anchor=tk.SW, 
                                                                    fill='#777777')
            self.__percentage_info = self.__canvas.create_text(x_offset - 40,
                                                                    y_offset - 50 - self.__y_offset - self.__offset,
                                                                    text='{:.1f} %'.format(self.__percentage*100),
                                                                    anchor=tk.SE, 
                                                                    fill='#777777')
      
    
    def __show_error(self, y_offset, x_offset):
        if self.__has_error:
            self.__progress_bar = self.__canvas.create_rectangle(x_offset - 15,
                                                                    y_offset - 45 - self.__y_offset - self.__offset,
                                                                    x_offset - 325,
                                                                    y_offset - 40 - self.__y_offset - self.__offset,
                                                                    fill='#FF0000',
                                                                    width=0)
            self.__page_info = self.__canvas.create_text(x_offset - 325,
                                                                    y_offset - 50 - self.__y_offset - self.__offset,
                                                                    text='Error running secondary task',
                                                                    anchor=tk.SW, 
                                                                    fill='#777777')
            self.__percentage_info = self.__canvas.create_text(x_offset - 40,
                                                                    y_offset - 50 - self.__y_offset - self.__offset,
                                                                    text='-.-- %',
                                                                    anchor=tk.SE, 
                                                                    fill='#777777')
            if not self.__error_shown:
                self.__error_shown = True
                messagebox.showerror(self.__error_title, self.__error_description)


    def __delete_static_elements(self):
        if self.__background == None:
            return  

        self.__canvas.delete(self.__background)
        self.__canvas.delete(self.__close_pop_up_window)
        self.__canvas.delete(self.__progress_bar_background)
        self.__canvas.delete(self.__progress_bar)
        self.__canvas.delete(self.__page_info)
        self.__canvas.delete(self.__percentage_info)



    def enable_close_pop_up(self):
        self.__close_pop_up_button.config(image=self.__im_close_pop_up)
        self.__close_pop_up_button.configure(command=self.__handle_close)
        self.__close_allowed = True
        

    
    def set_close_func(self, func):
        self.__close_func = func

    
    def hide(self):
        self.__closed = True
        self.disable_close_pop_up()
        self.__redraw_callback_func()
        self.__percentage = 0.0
        self.__task = '-'
        self.__object_name = '-' 


    def disable_close_pop_up(self):
        self.__close_pop_up_button.config(image=self.__im_close_pop_up_disabled)
        self.__close_pop_up_button.configure(command=self.__empty)
        self.__close_allowed = False
        

    def __empty(self):
        pass


    def __handle_close(self):
        self.__closed = True
        self.disable_close_pop_up()
        self.__redraw_callback_func()
        self.__percentage = 0.0
        self.__task = '-'
        self.__object_name = '-' 
        if self.__close_func:
            self.__close_func()
        
        

    def show(self):
        self.__closed = False
        self.__redraw_callback_func()

    def is_shown(self):
        return not self.__closed 


if __name__ == '__main__':

    root = tk.Tk()

    frame=tk.Frame(root,width=400,height=400)
    frame.grid(row=0,column=0)
    canvas = tk.Canvas(frame, bg="white", height=400, width=400, background='white',scrollregion=(0,0,400,1500))
    canvas.pack(side=tk.LEFT,expand=True,fill=tk.BOTH)
    vbar=tk.Scrollbar(frame,orient=tk.VERTICAL)
    vbar.pack(side=tk.RIGHT,fill=tk.Y)
    vbar.config(command=canvas.yview)

    def wheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), tk.UNITS)

    canvas.bind('<MouseWheel>', wheel)

    canvas.create_rectangle(100,0,200,1500,fill='red')
    
    a = banner_handler(canvas,0,0,vbar)
    
    a.primary_progress_banner.show()
    a.warning_banner.show("Hello",'World!')
    a.secondary_progress_banner.show()
    a.primary_progress_banner.enable_close_pop_up()
    a.primary_progress_banner.show_error('Error', 'Description')
    a.secondary_progress_banner.show_error('Error', 'Description')
    a.secondary_progress_banner.enable_close_pop_up()
    

    def draw(_):
        a.draw()

    canvas.bind("<Configure>", draw)
    canvas.update()
    

    
    root.mainloop()



