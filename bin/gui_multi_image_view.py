
import base64
from io import BytesIO
import math
from tkinter import font
from uuid import uuid4
from PIL import Image, ImageTk, ImageDraw
import cv2
import numpy as np
import tkinter as tk

try:
    from bin.gui_base64_icons import background
except:
    from gui_base64_icons import background


class multi_image_view():
    def __init__(self, canvas, x_offset, y_offset, button_width:int=30 , button_height:int=30) -> None:
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.x = None
        self.y = None
        self.width = None 
        self.height = None
        self.__image_shown = None
        self.__background_shown = None 
        self.__image = None
        self.__im = None
        self.__canvas = canvas
        self.__imgs = []
        self.__show_image_index = 0
        self.__button_width = button_width
        self.__button_height = button_height
        self.__id = uuid4()
        self.__background_image = np.array(Image.open(BytesIO(base64.b64decode(background))))
        self.__font = font.Font(family="Helvetica",size=12,weight="bold")
        self.__create_disabled_move_button_icons()
        self.__create_enabled_move_button_icons()


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


    def draw(self, x=0,y=0,width=200,height=200):
        self.__delete()
        self.x = self.x_offset + x
        self.y = self.y_offset + y
        self.width = width
        self.height = height
        number_of_tile_x = int(math.ceil(width/20))
        number_of_tile_y = int(math.ceil(height/20))
        img = np.tile(self.__background_image, (number_of_tile_y, number_of_tile_x, 1))
        img = img[0:height,0:width]
        im = Image.fromarray(img)
        self.__img_tile = ImageTk.PhotoImage(image=im) 

        self.__background_shown = self.__canvas.create_image( self.x,self.y, image=self.__img_tile, anchor=tk.NW)
        self.__show_image()

        
        for i, _ in enumerate(self.__imgs):
            option = str(i + 1)
            x = self.x + (width/2) - len(self.__imgs)*20/2 + (i+1)*20 - 10
            self.__create_option_view(option, i,x , self.y + self.height - 40)
        
        self.__create_button_views(self.x , self.y + height/2)

        return (width, height)
        
    

    
    def __create_button_views(self,x,y):
        self.__canvas.create_rectangle(x 
                                        ,y - int(self.__button_height/2)
                                        ,x + 20
                                        ,y + int(self.__button_height/2)
                                        ,fill="#FFFFFF"
                                        ,outline="#FFFFFF"
                                        ,tags=(self.__id,"move_button","move_button"+str(self.__id),"left"))
        self.__left_button_image = self.__canvas.create_image(x
                                        ,y - 7
                                        ,image=self.__image_left
                                        ,tags=(self.__id,"move_button","move_button"+str(self.__id),"left")
                                        ,anchor=tk.NW)
        self.__canvas.create_rectangle(x - int(20) + self.width
                                        ,y - int(self.__button_height/2)
                                        ,x + self.width
                                        ,y + int(self.__button_height/2)
                                        ,fill="#FFFFFF"
                                        ,outline="#FFFFFF"
                                        ,tags=(self.__id,"move_button","move_button"+str(self.__id),"right"))
        self.__right_button_image = self.__canvas.create_image(x - int(15) + self.width
                                        ,y - 7
                                        ,image=self.__image_right
                                        ,tags=(self.__id,"move_button","move_button"+str(self.__id),"right")
                                        ,anchor=tk.NW)
        self.__canvas.tag_bind(("move_button",), '<ButtonPress-1>', self.__handle_move_options)
        self.__enable_or_disable_move_buttons()

    def __enable_or_disable_move_buttons(self):
            

            if self.__show_image_index == 0:
                self.__canvas.itemconfig(self.__left_button_image, image=self.__disabled_image_left)
            else:
                self.__canvas.itemconfig(self.__left_button_image, image=self.__image_left)


            if self.__show_image_index == len(self.__imgs) - 1:
                self.__canvas.itemconfig(self.__right_button_image, image=self.__disabled_image_right)
            else:
                self.__canvas.itemconfig(self.__right_button_image, image=self.__image_right)


    def get_shown_image_index(self):
        return self.__show_image_index
                

    def __handle_move_options(self,event):
        x = self.__canvas.canvasx(event.x)
        y = self.__canvas.canvasy(event.y)
        id = self.__canvas.find_closest(x,y)
        tags = self.__canvas.gettags(id)
        if tags[3] == "left":
            if self.__show_image_index > 0:
                self.__show_image_index -= 1
        else:
            if self.__show_image_index < len(self.__imgs) - 1:
                self.__show_image_index += 1
                
        self.__show_image()
        self.__recreate_option_views()
        self.__enable_or_disable_move_buttons()


    
    def set_images(self, images: list):
        self.__imgs = images
        self.__show_image_index = 0

        if self.__image_shown is None:
            return 
        
        self.__canvas.delete(self.__image_shown)
        self.__canvas.delete("option"+str(self.__id))
        self.__show_image()
        self.__recreate_option_views()
        self.__enable_or_disable_move_buttons()

    
    def select_image(self, index):
        if index < 0 or index >= len(self.__imgs):
            return
        self.__show_image_index = index
        self.__show_image()
        self.__recreate_option_views()
        self.__enable_or_disable_move_buttons()


    def __recreate_option_views(self):
        self.__canvas.delete("option"+str(self.__id))
        for i, _ in enumerate(self.__imgs):
            option = str(i + 1)
            x = self.x + (self.width/2) - len(self.__imgs)*20/2 + (i+1)*20 - 10
            self.__create_option_view(option, i,x , self.y + self.height - 40)


    def __create_option_view(self, option, index,x,y):
        
        rect_id = self.__canvas.create_rectangle(x - int(self.__button_width/2)
                                        ,y - int(self.__button_height/2)
                                        ,x + int(self.__button_width/2)
                                        ,y + int(self.__button_height/2)
                                        ,fill=""
                                        ,outline=""
                                        ,tags=(option,index,self.__id,"option"+str(self.__id), "option_"+str(index)+"_"+str(self.__id)))
        self.__canvas.tag_bind(rect_id, '<ButtonPress-1>', self.__handle_option_selected)
        if option == str(self.__show_image_index + 1):
            text_id = self.__canvas.create_text(x,y,text=option,anchor=tk.CENTER
                                        ,tags=(option,index,self.__id,"option"+str(self.__id))
                                        ,font=self.__font
                                        ,fill="#00AEEF")
        else:
            text_id = self.__canvas.create_text(x,y,text=option,anchor=tk.CENTER
                                        ,tags=(option,index,self.__id,"option"+str(self.__id))
                                        ,font=self.__font
                                        ,fill="#606060")
        self.__canvas.tag_bind(text_id, '<ButtonPress-1>', self.__handle_option_selected)

    def __handle_option_selected(self, event):
        x = self.__canvas.canvasx(event.x)
        y = self.__canvas.canvasy(event.y)
        id = self.__canvas.find_closest(x,y)
        tags = self.__canvas.gettags(id)
        if self.__show_image_index == int(tags[1]): return
        self.__show_image_index = int(tags[1])
        self.__show_image()
        self.__recreate_option_views()
        self.__enable_or_disable_move_buttons()


    def __show_image(self):
        if not self.__imgs or self.x is None:
            return

        
        self.__im = Image.fromarray(cv2.cvtColor(self.__imgs[self.__show_image_index], cv2.COLOR_BGRA2RGBA))
        image = self.__im.copy()
        # Resize if bigger than image view
        if image.height > self.height:
            size = (int(self.height/image.height*image.width), self.height)
            image = image.resize(size)
                
            
        if image.width > self.width:
            size = (self.width, int(self.width/image.width*image.height))
            image = image.resize(size)
        
        
        self.__image = ImageTk.PhotoImage(image=image) 
        if self.__image_shown:
            self.__canvas.delete(self.__image_shown)
        
        self.__image_shown = self.__canvas.create_image( self.x + int((self.width - self.__image.width())/2)
                                                        ,self.y + int((self.height - self.__image.height())/2)
                                                        ,image=self.__image, anchor=tk.NW)



    def get_background_id(self):
        return self.__background_shown


    def reset_image(self):
        if self.__image_shown:
            self.__canvas.delete(self.__image_shown)

    def __delete(self):
        self.__canvas.delete(self.__background_shown)
        self.__canvas.delete("move_button"+str(self.__id))
        if self.__image_shown:
            self.__canvas.delete(self.__image_shown)
            self.__canvas.delete("option"+str(self.__id))
            

    def hide(self):
        self.__delete()


if __name__ == "__main__":

    create_image = lambda x: Image.new('RGB', (100, 100), color = (x, x, x))
    images = [create_image(x) for x in range(0, 255, 80)]

    # Convert to numpy array
    images = [np.array(image) for image in images]

    root = tk.Tk()
    canvas = tk.Canvas(root, width=800, height=800)
    canvas.pack()
    image_view = multi_image_view(canvas, 30, 0)
    image_view.set_images(images)
    image_view.draw(width=200, height=200)
    root.mainloop()