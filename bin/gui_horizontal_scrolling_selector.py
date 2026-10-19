import tkinter as tk
from tkinter import font
from typing import List
from uuid import UUID, uuid4
from PIL import Image, ImageDraw, ImageTk


class horizontal_scrolling_selector:

    def __init__(self, canvas:tk.Canvas,options:List[str], button_width:int=None , button_height:int=30,selected:str=None, callback=None
                    ,selector_font = None) -> None:
        if selector_font:
            self.__font = selector_font
        else:
            self.__font = font.Font(family="Helvetica",size=12,weight="bold")
        self.__canvas = canvas
        no_white_space_options = []
        for option in options:
            no_white_space_options.append(option.replace(' ','_'))
        self.__options = no_white_space_options
        self.__button_width = button_width
        if not self.__button_width:
            self.__auto_determine_width(options)
        self.__button_height = button_height
        self.__selected = selected 
        self.__id = uuid4()
        self.__positon = 0 
        self.__x = 0
        self.__y = 0 
        self.__in_motion = False
        self.__callback = callback
        self.__create_enabled_move_button_icons()
        self.__create_disabled_move_button_icons()
        
    
    def __auto_determine_width(self, list):
        largest_width = 0
        for options in list:
            width = self.__font.measure(options)
            if width > largest_width:
                largest_width = width
        self.__button_width = largest_width + 24

    def __create_disabled_move_button_icons(self):
        arrow = Image.new('RGBA', (15, 15), '#00000000')
        draw = ImageDraw.Draw(arrow)
        draw.line([(0, 4), (7, 11), (14, 4) ], fill=(220,220,220,255),width=2)
        im_right= arrow.rotate(90)
        im_left= arrow.rotate(270)
        self.__disabled_image_right = ImageTk.PhotoImage(im_right)
        self.__disabled_image_left = ImageTk.PhotoImage(im_left)
        

    def __create_enabled_move_button_icons(self):
        arrow = Image.new('RGBA', (15, 15), '#00000000')
        draw = ImageDraw.Draw(arrow)
        draw.line([(0, 4), (7, 11), (14, 4) ], fill=(150,150,150,255),width=2)
        im_right= arrow.rotate(90)
        im_left= arrow.rotate(270)
        self.__image_right = ImageTk.PhotoImage(im_right)
        self.__image_left = ImageTk.PhotoImage(im_left)


    def draw(self,x=None,y=None):
        if x is not None:
            self.__x = x
        else:
            x = self.__x
        if y is not None:
            self.__y = y
        else:
            y = self.__y
        self.__canvas.delete(self.__id)
        self.__id = uuid4()
        x1 = x + int(self.__button_width/2) + self.__positon
        y1 = y + int(self.__button_height/2)
        index = 0
        
        for option in self.__options:
            self.__create_option_view(option, index, x1, y1)
            x1 = x1 + self.__button_width
            index = index + 1

        self.__create_button_views(x,y1)


    def __create_option_view(self, option, index,x,y):
        self.__canvas.create_rectangle(x - int(self.__button_width/2)
                                        ,y - int(self.__button_height/2)
                                        ,x + int(self.__button_width/2)
                                        ,y + int(self.__button_height/2)
                                        ,fill="#FFFFFF"
                                        ,outline="#FFFFFF"
                                        ,tags=(option,index,self.__id,"option"+str(self.__id), "option_"+str(index)+"_"+str(self.__id)))
        if option == self.__selected:
            self.__canvas.create_text(x,y,text=option,anchor=tk.CENTER
                                        ,tags=(option,index,self.__id,"option"+str(self.__id))
                                        ,font=self.__font
                                        ,fill="#505050")
        else:
            self.__canvas.create_text(x,y,text=option,anchor=tk.CENTER
                                        ,tags=(option,index,self.__id,"option"+str(self.__id))
                                        ,font=self.__font
                                        ,fill="#B4B4B4")
        self.__canvas.tag_bind((option,), '<ButtonPress-1>', self.__handle_option_selected)


    def __create_button_views(self,x,y):
        width = self.__canvas.winfo_width()
        self.__canvas.create_rectangle(x - int(20 * 2) + width
                                        ,y - int(self.__button_height/2)
                                        ,x + int(20 * 3) + width
                                        ,y + int(self.__button_height/2)
                                        ,fill="#FFFFFF"
                                        ,outline="#FFFFFF"
                                        ,tags=(self.__id,"move_button","left"))
        self.__left_button_image = self.__canvas.create_image(x - 30 + width
                                        ,y
                                        ,image=self.__image_left
                                        ,tags=(self.__id,"move_button","left")
                                        ,anchor=tk.CENTER)
        self.__canvas.create_rectangle(x - int(20) + width
                                        ,y - int(self.__button_height/2)
                                        ,x + int(20 * 2) + width
                                        ,y + int(self.__button_height/2)
                                        ,fill="#FFFFFF"
                                        ,outline="#FFFFFF"
                                        ,tags=(self.__id,"move_button","right"))
        self.__right_button_image = self.__canvas.create_image(x - 10 + width
                                        ,y
                                        ,image=self.__image_right
                                        ,tags=(self.__id,"move_button","right")
                                        ,anchor=tk.CENTER)
        self.__canvas.tag_bind(("move_button",), '<ButtonPress-1>', self.__handle_move_options)
        self.__canvas.create_rectangle(x - int(20 * 2) + width - 2
                                        ,y - int(self.__button_height/2)
                                        ,x - int(20 * 2) + width
                                        ,y + int(self.__button_height/2)
                                        ,fill="#BBBBBB"
                                        ,tags=(self.__id,)
                                        ,outline="")
        self.__enable_or_disable_move_buttons()



    def __handle_option_selected(self, event):
        x = self.__canvas.canvasx(event.x)
        y = self.__canvas.canvasy(event.y)
        id = self.__canvas.find_closest(x,y)
        tags = self.__canvas.gettags(id)
        self.__selected = tags[0]
        self.draw()
        if self.__callback:
            self.__callback((tags[0],tags[1]))


    def select(self, selection):
        self.__selected = self.__options[selection]
        self.draw()



    def __handle_move_options(self,event):
        x = self.__canvas.canvasx(event.x)
        y = self.__canvas.canvasy(event.y)
        id = self.__canvas.find_closest(x,y)
        tags = self.__canvas.gettags(id)
        if tags[2] == "left":
            self.__move_animation_left()
        else:
            self.__move_animation_right()

        self.__enable_or_disable_move_buttons()



    def __enable_or_disable_move_buttons(self):
            width = self.__canvas.winfo_width()
            y1 = self.__y + int(self.__button_height/2)
            if abs(self.__positon) >= (len(self.__options) -1)*self.__button_width:
                self.__canvas.delete(self.__left_button_image)
                self.__left_button_image = self.__canvas.create_image(self.__x - 30 + width
                                        ,y1
                                        ,image=self.__disabled_image_left
                                        ,tags=(self.__id,"move_button","left")
                                        ,anchor=tk.CENTER)
            else:
                self.__left_button_image = self.__canvas.create_image(self.__x - 30 + width
                                        ,y1
                                        ,image=self.__image_left
                                        ,tags=(self.__id,"move_button","left")
                                        ,anchor=tk.CENTER)


            if self.__positon >= 0:
                self.__canvas.delete(self.__right_button_image)
                self.__right_button_image = self.__canvas.create_image(self.__x - 10 + width
                                        ,y1
                                        ,image=self.__disabled_image_right
                                        ,tags=(self.__id,"move_button","right")
                                        ,anchor=tk.CENTER)
            else:
                self.__right_button_image = self.__canvas.create_image(self.__x - 10 + width
                                        ,y1
                                        ,image=self.__image_right
                                        ,tags=(self.__id,"move_button","right")
                                        ,anchor=tk.CENTER)



    def __move_animation_left(self):

        # return if at last button
        if abs(self.__positon) >= (len(self.__options) -1)*self.__button_width:
            return 

        self.__in_motion = True
        self.__steps = int(self.__button_width/4)
        self.__canvas.after(2,self.__move_options_left)
        self.__positon = self.__positon - self.__button_width



    def __move_options_left(self):
        x = self.__canvas.coords(("option_0_"+str(self.__id)))[0]
        if self.__positon <= x :
            self.__canvas.move("option"+str(self.__id),-4,0)
            self.__canvas.after(2,self.__move_options_left)
            self.__steps = self.__steps - 1
        else:
            self.__in_motion = False



    def __move_animation_right(self):
        self.__in_motion = True
        
        
        if self.__positon >= 0:
            return
        self.__steps = int(self.__button_width)
        self.__canvas.after(2,self.__move_options_right)
        self.__positon = self.__positon + self.__button_width



    def __move_options_right(self):
        x = self.__canvas.coords(("option_0_"+str(self.__id)))[0]
        if self.__positon - 1 >= x :
            self.__canvas.move("option"+str(self.__id),4,0)
            self.__canvas.after(2,self.__move_options_right)
            self.__steps = self.__steps - 1
        else:
            self.__in_motion = False
        


            

        


if __name__ == "__main__":

    root = tk.Tk()
    canvas = tk.Canvas(root, bg="white", height=600, width=300)

    def callback(event):
        print(event)

    b = horizontal_scrolling_selector(canvas,["Interlock","Permissive1","Permissive2","Permissive3","Permissive4","Permissive5"],callback=callback)

    def draw(_):
        b.draw()

    canvas.bind('<Configure>',draw)


    canvas.pack()
    root.mainloop()
