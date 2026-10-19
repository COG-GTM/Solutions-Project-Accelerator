import tkinter as tk
from tkinter import font
from PIL import Image, ImageDraw, ImageTk

try:
    from .gui_base64_icons import medium_banner_background, medium_warning
except ImportError as error:
    from gui_base64_icons import medium_banner_background, medium_warning



class warning_banner():
    def __init__(self, canvas: tk.Canvas, x, y, vbar,redraw_callback):
        self.vbar = vbar
        self.__x = x
        self.__y = y
        self.__canvas = canvas
        self.__background_image = tk.PhotoImage(data=medium_banner_background)
        self.__warning_icon = tk.PhotoImage(data=medium_warning)
        self.__background_id = None
        self.__warning_icon_id = None 
        self.__title_id = None
        self.__message_id = None 
        self.__wait_after_scroll = None 
        self.__closed = True
        self.__y_offset = 0 
        self.__title = ''
        self.__message = ''
        self.__redraw_callback_func = redraw_callback


    def handle_scroll(self,x0, x1):
        
        self.__delete_static_elements()
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
        self.__background_id = self.__canvas.create_image(x_offset + 10,
                                                            y_offset - self.__y_offset,
                                                            image=self.__background_image,
                                                            anchor=tk.SE)
        self.__warning_icon_id = self.__canvas.create_image(x_offset - 240,
                                                            y_offset - 35 - self.__y_offset,
                                                            image=self.__warning_icon,
                                                            anchor=tk.SE)
        self.__title_id = self.__canvas.create_text(x_offset - 230,
                                                        y_offset - 60 - self.__y_offset,
                                                        text=self.__title,
                                                        font=('Arial Bold',11),
                                                        anchor=tk.SW, 
                                                        fill='#777777')
        
        self.__fit_message(y_offset, x_offset)
        '''self.__message_id = self.__canvas.create_text(self.__canvas.winfo_width() - 230,
                                                                            y_offset - 30 - self.__y_offset,
                                                                            text=self.__message,
                                                                            font=('Arial',9),
                                                                            anchor=tk.SW, 
                                                                            fill='#777777')'''
        

    def __delete_static_elements(self):
        if self.__background_id == None:
            return  

        self.__canvas.delete(self.__background_id)
        self.__canvas.delete(self.__warning_icon_id)
        self.__canvas.delete(self.__title_id)
        self.__canvas.delete(self.__message_id)


    def hide(self):
        self.__closed = True
        self.__redraw_callback_func()
        

    def show(self, title, message):
        self.__title = title
        self.__message = message
        self.__closed = False
        self.__redraw_callback_func()


    def __fit_message(self , y_offset, x_offset):
        second_line_substring = 0 
        split = self.__message.split(" ")
        while True :
            second_line_substring = second_line_substring + 1
            multiline_description = ' '.join(split[:second_line_substring])
            self.__canvas.delete(self.__message_id)
            self.__message_id = self.__canvas.create_text(x_offset - 230,
                                                            y_offset - 30 - self.__y_offset,
                                                            text=multiline_description,
                                                            font=('Arial',9),
                                                            anchor=tk.SW, 
                                                            fill='#777777')
            description_bounds = self.__canvas.bbox(self.__message_id)
            if (description_bounds[2] - description_bounds[0]) > (200 - 8):
                break
            if second_line_substring > len(split):
                break
        second_line_substring = second_line_substring - 1
        self.__canvas.delete(self.__message_id)
        multiline_description = ' '.join(split[:second_line_substring])+'\n'+' '.join(split[second_line_substring:])
        self.__message_id = self.__canvas.create_text(x_offset - 230,
                                                        y_offset - 30 - self.__y_offset,
                                                        text=multiline_description,
                                                        font=('Arial',9),
                                                        anchor=tk.SW, 
                                                        fill='#777777')
        

    def is_shown(self):
        return not self.__closed 


            



if __name__ == '__main__':

    root = tk.Tk()

    frame=tk.Frame(root,width=400,height=400)
    frame.grid(row=0,column=0)
    canvas = tk.Canvas(frame, bg="white", height=400, width=400, background='white',scrollregion=(0,0,400,1500))
    vbar=tk.Scrollbar(frame,orient=tk.VERTICAL)
    vbar.pack(side=tk.RIGHT,fill=tk.Y)
    vbar.config(command=canvas.yview)

    def wheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), tk.UNITS)

    canvas.bind('<MouseWheel>', wheel)

    canvas.create_rectangle(100,0,200,1500,fill='red')
    
    a = warning_banner(canvas,0,0,vbar)
    a.show()
    a.offset_vertical_position(100)
    

    def draw(_):
        a.draw()
        print('Doing stuff')

    canvas.bind("<Configure>", draw)
    canvas.update()
    

    canvas.pack(side=tk.LEFT,expand=True,fill=tk.BOTH)
    root.mainloop()
