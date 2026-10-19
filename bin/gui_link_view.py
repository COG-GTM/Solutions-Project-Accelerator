try:
    from .gui_base64_icons import linked, unlinked_dark_gray, unlinked_light_gray, goto_dark_gray_20, goto_light_gray_20, background, bottom_to_top_gray, top_to_bottom_gray
    from bin.gui_base64_icons import ignore_dark_gray,ignore_light_gray,allow_dark_gray,allow_light_gray
    from bin.gui_base64_icons import cell_reference_blue,cell_reference_dark_gray,cell_reference_light_gray
except ImportError as error:
    from gui_base64_icons import linked, unlinked_dark_gray, unlinked_light_gray, goto_dark_gray_20, goto_light_gray_20, background, bottom_to_top_gray, top_to_bottom_gray
    from gui_base64_icons import ignore_dark_gray,ignore_light_gray,allow_dark_gray,allow_light_gray
    from gui_base64_icons import cell_reference_blue,cell_reference_dark_gray,cell_reference_light_gray

from io import BytesIO
import math
from re import X
import tkinter as tk
from tkinter import font
from PIL import Image, ImageTk
import cv2
import numpy as np
import base64

BOTTOM_TO_TOP = 'bottom_to_top'
TOP_TO_BOTTOM = 'top_to_bottom'

class link_view():
    def __init__(self, canvas : tk.Canvas, x_offset=0, y_offset=0, link_callback=None, goto_callback=None, parameter=None, indexed=False) -> None:
        self.__canvas = canvas
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.x = self.x_offset
        self.y = self.x_offset
        self.indexed = indexed
        self.unhighlighted_color = '#FFFFFF'
        self.__linked_image = tk.PhotoImage(data=linked)
        self.__unlinked_image = tk.PhotoImage(data=unlinked_dark_gray)
        self.__linking_disabled_image = tk.PhotoImage(data=unlinked_light_gray)
        self.__goto_image = tk.PhotoImage(data=goto_dark_gray_20)
        self.__goto_disabled_image = tk.PhotoImage(data=goto_light_gray_20)
        self.__is_linked = False
        self.__linking_is_disabled = True 
        self.__goto_is_disabled = True
        self.__link_callback = link_callback
        self.__goto_callback = goto_callback
        self.__parameter = parameter
        self.__link_icon = None
        self.__goto_icon = None

    
    def draw(self, x=0, y=0):
        self.x = self.x_offset + x
        self.y = self.y_offset + y
        self.delete()
        self.__draw_link_button()
        self.__draw_goto_button()


    def delete(self):
        if self.__link_icon:
            self.__canvas.delete(self.__link_rect)
            self.__canvas.delete(self.__link_icon)
            self.__canvas.delete(self.__goto_rect)
            self.__canvas.delete(self.__goto_icon)

    
    def hide(self):
        self.delete()

    def __draw_link_button(self):
        self.__link_rect = self.__canvas.create_rectangle(self.x ,self.y ,self.x+24 ,self.y+24,fill=self.unhighlighted_color, width = 0, tags=('link_button'))
        
        if self.__is_linked:
            self.__link_icon = self.__canvas.create_image( self.x + 2 ,self.y  + 2 , image=self.__linked_image, anchor=tk.NW, tags=('link_button'))
        elif not self.__linking_is_disabled:
            self.__link_icon = self.__canvas.create_image( self.x + 2 ,self.y  + 2 , image=self.__unlinked_image, anchor=tk.NW, tags=('link_button'))
        else:
            self.__link_icon = self.__canvas.create_image( self.x + 2 ,self.y  + 2 , image=self.__linking_disabled_image, anchor=tk.NW, tags=('link_button'))

        self.__canvas.tag_bind(self.__link_rect,'<Enter>', self.__on_link_enter)
        self.__canvas.tag_bind(self.__link_rect,'<Leave>', self.__on_link_leave)
        self.__canvas.tag_bind(self.__link_icon,'<Enter>', self.__on_link_enter)
        self.__canvas.tag_bind(self.__link_icon,'<Leave>', self.__on_link_leave)
        self.__canvas.tag_bind(self.__link_rect,'<Button-1>', self.__on_link_click)
        self.__canvas.tag_bind(self.__link_icon,'<Button-1>', self.__on_link_click)


    def __draw_goto_button(self):
        self.__goto_rect = self.__canvas.create_rectangle(self.x + 28 ,self.y ,self.x+24 + 28 ,self.y+24,fill=self.unhighlighted_color, width = 0, tags=('goto_button'))
        
        if not self.__goto_is_disabled:
            self.__goto_icon = self.__canvas.create_image( self.x + 2 + 28,self.y  + 2 , image=self.__goto_image, anchor=tk.NW, tags=('goto_button'))
        else:
            self.__goto_icon = self.__canvas.create_image( self.x + 2 + 28,self.y  + 2 , image=self.__goto_disabled_image, anchor=tk.NW, tags=('goto_button'))

        self.__canvas.tag_bind(self.__goto_rect,'<Enter>', self.__on_goto_enter)
        self.__canvas.tag_bind(self.__goto_rect,'<Leave>', self.__on_goto_leave)
        self.__canvas.tag_bind(self.__goto_icon,'<Enter>', self.__on_goto_enter)
        self.__canvas.tag_bind(self.__goto_icon,'<Leave>', self.__on_goto_leave)
        self.__canvas.tag_bind(self.__goto_rect,'<Button-1>', self.__on_goto_click)
        self.__canvas.tag_bind(self.__goto_icon,'<Button-1>', self.__on_goto_click)


    def __on_link_enter(self,_):
        self.__canvas.itemconfig(self.__link_rect, fill='#E5E5E5')


    def __on_link_leave(self,_):
        self.__canvas.itemconfig(self.__link_rect, fill=self.unhighlighted_color)


    def __on_goto_enter(self,_):
        self.__canvas.itemconfig(self.__goto_rect, fill='#E5E5E5')


    def __on_goto_leave(self,_):
        self.__canvas.itemconfig(self.__goto_rect, fill=self.unhighlighted_color)

    def __on_link_click(self,_):
        if self.__linking_is_disabled:
            return 

        if self.__parameter:
            self.__link_callback(self.__is_linked, self.__parameter)
        else:
            self.__link_callback(self.__is_linked)

    def __on_goto_click(self,_):
        if self.__goto_is_disabled:
            return 
        
        if self.__parameter:
            self.__goto_callback(self.__parameter)
        else:
            self.__goto_callback()

    def enable_linking(self):
        if self.__is_linked:
            return

        self.__linking_is_disabled = False
        if self.__link_icon:
            self.__canvas.itemconfig(self.__link_icon, image=self.__unlinked_image)

    def enable_goto(self):
        self.__goto_is_disabled = False
        if self.__goto_icon:
            self.__canvas.itemconfig(self.__goto_icon, image=self.__goto_image)

    def disable_linking(self):
        if self.__is_linked:
            return

        self.__linking_is_disabled = True
        if self.__link_icon:
            self.__canvas.itemconfig(self.__link_icon, image=self.__linking_disabled_image)


    def force_disable_linking(self):
        self.__is_linked = False 
        self.disable_linking()


    def disable_goto(self):
        self.__goto_is_disabled = True
        if self.__goto_icon:
            self.__canvas.itemconfig(self.__goto_icon, image=self.__goto_disabled_image)


    def link_formed(self):
        self.__linking_is_disabled = False
        self.__is_linked = True
        if self.__link_icon:
            self.__canvas.itemconfig(self.__link_icon, image=self.__linked_image)


    def link_removed(self):
        self.__is_linked = False
        self.__linking_is_disabled = False
        if self.__link_icon:
            self.__canvas.itemconfig(self.__link_icon, image=self.__unlinked_image)


class image_view():
    def __init__(self, canvas, x_offset, y_offset) -> None:
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
        self.__background_image = np.array(Image.open(BytesIO(base64.b64decode(background))))

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
        return (width, height)

    def set_image(self, image: np.array):
        """ Set the image and fit the image on the image view"""
        if image is None:
            self.reset_image()
            return
        image = cv2.cvtColor(image,cv2.COLOR_RGBA2BGRA)
        self.__im = Image.fromarray(image)
        self.__show_image()


    def __show_image(self):
        if self.__im is None or self.x is None:
            return


        image = self.__im.copy()
        # Resize if bigger than image view
        if image.height > self.height:
            size = (int(self.height/image.height*image.width), self.height)
            image = image.resize(size)
                
            
        if image.width > self.width:
            size = (self.width, int(self.width/image.width*image.height))
            image = image.resize(size)
        
        
        self.__image = ImageTk.PhotoImage(image=image) 

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
        if self.__image_shown:
            self.__canvas.delete(self.__image_shown)


    def hide(self):
        self.__delete()


class link_ignore_view(link_view):
    def __init__(self, canvas: tk.Canvas,x=0,y=0,link_callback=None, goto_callback=None, ignore_callback=None,parameter=None,indexed=False,index_selected_callback=None) -> None:
        super().__init__(canvas,x + 29,y,link_callback=link_callback,goto_callback=goto_callback,parameter=parameter,indexed=indexed)
        self.__canvas = canvas 
        self.__x = x
        self.__y = y
        self.__ignore_callback = ignore_callback
        self.__ignore_image = tk.PhotoImage(data=ignore_dark_gray)
        self.__ignore_disabled_image = tk.PhotoImage(data=ignore_light_gray)
        self.__allowed_image = tk.PhotoImage(data=allow_dark_gray)
        self.__allowed_disabled_image = tk.PhotoImage(data=allow_light_gray)
        self.__is_ignored = False
        self.__is_ignore_disabled = True
        self.__ignore_rect = None
        self.__parameter = parameter
        
        self.__document_viewer_has_table = False




    def draw(self, x=None, y=None):
        if x:
            self.__x = x 
        else:
            x = self.__x
        
        if y:
            self.__y = y 
        else:
            y = self.__y

        if self.__document_viewer_has_table:
            self.__delete()
            return 
        
        super().draw(x, y)
        self.__draw_ignore_button(x,y)
        

    def document_type(self, is_table):
        self.__document_viewer_has_table = is_table
        self.draw()

        

    def __draw_ignore_button(self,x=0,y=0):
        self.__ignore_rect = self.__canvas.create_rectangle(x ,y ,x+24 ,y+24,fill=self.unhighlighted_color, width = 0, tags=('link_button'))
        
        if self.__is_ignored and not self.__is_ignore_disabled:
            image = self.__allowed_image
        elif self.__is_ignored and self.__is_ignore_disabled:
            image = self.__allowed_disabled_image
        elif not self.__is_ignored and not self.__is_ignore_disabled:
            image = self.__ignore_image
        else:
            image = self.__ignore_disabled_image

        self.__ignore_icon = self.__canvas.create_image( x + 2 ,y  + 2 , image=image, anchor=tk.NW, tags=('link_button'))
        self.__canvas.tag_bind(self.__ignore_rect,'<Enter>', self.__on_ignore_enter)
        self.__canvas.tag_bind(self.__ignore_rect,'<Leave>', self.__on_ignore_leave)
        self.__canvas.tag_bind(self.__ignore_icon,'<Enter>', self.__on_ignore_enter)
        self.__canvas.tag_bind(self.__ignore_icon,'<Leave>', self.__on_ignore_leave)
        self.__canvas.tag_bind(self.__ignore_rect,'<Button-1>', self.__on_ignore_click)
        self.__canvas.tag_bind(self.__ignore_icon,'<Button-1>', self.__on_ignore_click)


    def __on_ignore_enter(self,_):
        self.__canvas.itemconfig(self.__ignore_rect, fill='#E5E5E5')


    def __on_ignore_leave(self,_):
        self.__canvas.itemconfig(self.__ignore_rect, fill=self.unhighlighted_color)

    def __delete(self):
        super().delete()
        if not self.__ignore_rect:
            return
        self.__canvas.delete(self.__ignore_rect)
        self.__canvas.delete(self.__ignore_icon)


    def hide(self):
        self.__delete()


    def __on_ignore_click(self,_):
        if self.__is_ignore_disabled:
            return 
        
        if self.__parameter:
            self.__ignore_callback(self.__is_ignored, self.__parameter)
        else:
            self.__ignore_callback(self.__is_ignored)


    def ignored(self):
        self.__is_ignore_disabled = False
        self.__is_ignored = True
        if self.__ignore_icon:
            self.__canvas.itemconfig(self.__ignore_icon, image=self.__allowed_image)


    def allowed(self):
        self.__is_ignored = False
        self.__is_ignore_disabled = False
        if self.__ignore_icon:
            self.__canvas.itemconfig(self.__ignore_icon, image=self.__ignore_icon)


    def disable(self):
        if self.__is_ignored:
            image = self.__allowed_disabled_image
        else:
            image = self.__ignore_disabled_image
        if self.__ignore_icon:
            self.__canvas.itemconfig(self.__ignore_icon, image=image)


class image_text_locations_view():
    def __init__(self, canvas: tk.Canvas, x_offset, y_offset, text_loaction_name, text_indicator_color='red',
            select_callback=None, link_text_location_callback= None, goto_callback=None,
            is_horizontal = True, is_bottom_to_top = True, vertical_direction_toggle_callback=None) -> None:
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.__canvas = canvas
        self.__bottom_to_top_image = tk.PhotoImage(data=bottom_to_top_gray)
        self.__top_to_bottom_image = tk.PhotoImage(data=top_to_bottom_gray)
        self.link_view = link_view(canvas, x_offset, y_offset + 1 , self.link_callback, self.goto_callback )
        self.__link_text_location_callback = link_text_location_callback
        self.__text_location_name = text_loaction_name
        self.__text_indicator_color = text_indicator_color
        self.__text_location_label = None 
        self.__text_location_color_indicator = None
        self.__select_callback = select_callback
        self.__selected = False
        self.__unhighlighted_color = '#FFFFFF'
        self.__goto_callback_func = goto_callback
        self.__vertical_direction_toggle_func = vertical_direction_toggle_callback
        self.__is_horizontal = is_horizontal
        self.__is_bottom_to_top = is_bottom_to_top
        self.__vertical_direction_rect = None



    def link_callback(self, linked):
        if self.__link_text_location_callback:
            self.__link_text_location_callback(linked, self.__text_location_name)

    def toggle_vertical_text_direction(self,_):
        pass

    def goto_callback(self):
        if self.__goto_callback_func:
            self.__goto_callback_func(self.__text_location_name)

    def draw(self, x=0, y=0):
        self.__delete_static_elements()
        

        self.x = self.x_offset + x # For static elements
        self.y = self.y_offset + y # For static elements
        self.__rect = self.__canvas.create_rectangle(self.x ,self.y - 2 ,self.__canvas.winfo_width() ,self.y + 28 ,fill='#FFFFFF', width = 0, tags=('add_text_location'))
        self.__text_location_label = self.__canvas.create_text(self.x + 8, self.y + 4,  
                                                                text=self.__text_location_name, 
                                                                font=('Arial',10,'normal'), 
                                                                anchor=tk.NW, 
                                                                fill="#707070")
        self.__text_location_color_indicator = self.__canvas.create_oval(self.x + 100, self.y + 6, 
                                                                            self.x + 112, self.y + 18, 
                                                                            fill=self.__text_indicator_color, 
                                                                            width = 0)
        

        self.__canvas.tag_bind(self.__rect,'<Enter>', self.__on_enter)
        self.__canvas.tag_bind(self.__rect,'<Leave>', self.__on_leave)
        self.__canvas.tag_bind(self.__text_location_label,'<Enter>', self.__on_enter)
        self.__canvas.tag_bind(self.__text_location_label,'<Leave>', self.__on_leave)
        self.__canvas.tag_bind(self.__rect,'<Button-1>', self.__on_click)
        self.__canvas.tag_bind(self.__text_location_label,'<Button-1>', self.__on_click)

        self.link_view.draw(self.__canvas.winfo_width() - 100, y)

        if self.__is_horizontal:
            return

        self.draw_vertical_text_direction_button()


    def draw_vertical_text_direction_button(self):
        x = self.x + self.__canvas.winfo_width() - 130

        self.__vertical_direction_rect = self.__canvas.create_rectangle(x ,self.y ,x + 28 ,self.y+28,fill=self.__unhighlighted_color, width = 0, tags=('text_direction_button'))
        
        if self.__is_bottom_to_top:
            self.__vertical_direction_icon = self.__canvas.create_image(x + 2 ,self.y + 2, image=self.__bottom_to_top_image, anchor=tk.NW, tags=('text_direction_button'))
        else:
            self.__vertical_direction_icon = self.__canvas.create_image(x + 2 ,self.y + 2, image=self.__top_to_bottom_image, anchor=tk.NW, tags=('text_direction_button'))

        self.__canvas.tag_bind(self.__vertical_direction_rect,'<Enter>', self.__on_vertical_direction_enter)
        self.__canvas.tag_bind(self.__vertical_direction_rect,'<Leave>', self.__on_link_leave)
        self.__canvas.tag_bind(self.__vertical_direction_icon,'<Enter>', self.__on_vertical_direction_enter)
        self.__canvas.tag_bind(self.__vertical_direction_icon,'<Leave>', self.__on_link_leave)
        self.__canvas.tag_bind(self.__vertical_direction_rect,'<Button-1>', self.__on_vertical_text_direction_click)
        self.__canvas.tag_bind(self.__vertical_direction_icon,'<Button-1>', self.__on_vertical_text_direction_click)


    def remove_vertical_text_direction_button(self):
        if not self.__vertical_direction_rect:
            return  
        self.__canvas.delete(self.__vertical_direction_rect)
        self.__canvas.delete(self.__vertical_direction_icon)


    def __on_vertical_direction_enter(self,_):
        self.__canvas.itemconfig(self.__vertical_direction_rect, fill='#E5E5E5')


    def __on_link_leave(self,_):
        self.__canvas.itemconfig(self.__vertical_direction_rect, fill=self.__unhighlighted_color)


    def __on_vertical_text_direction_click(self,_):
        vertical_direction = TOP_TO_BOTTOM if self.__is_bottom_to_top else BOTTOM_TO_TOP
        self.__vertical_direction_toggle_func(self.__text_location_name, vertical_direction)


    def vertical_bottom_to_top(self):
        self.__is_bottom_to_top = True
        self.__is_horizontal = False
        if self.__vertical_direction_icon:
            self.__canvas.itemconfig(self.__vertical_direction_icon, image=self.__bottom_to_top_image)


    def vertical_top_to_bottom(self):
        self.__is_bottom_to_top = False
        self.__is_horizontal = False
        if self.__vertical_direction_icon:
            self.__canvas.itemconfig(self.__vertical_direction_icon, image=self.__top_to_bottom_image)


    def get_indication_color(self):
        return self.__text_indicator_color


    def __on_enter(self,_):
        self.__canvas.itemconfig(self.__rect, fill='#E5E5E5')


    def __on_leave(self,_):
        if not self.__selected:
            self.__canvas.itemconfig(self.__rect, fill='#FFFFFF')

    def __on_click(self,_):
        if self.__select_callback:
            self.__select_callback(self.__text_location_name)

    def __delete_static_elements(self):
        if self.__text_location_label:
            self.__canvas.delete(self.__text_location_label)
            self.__canvas.delete(self.__text_location_color_indicator)
            self.__canvas.delete(self.__rect)

    def select(self):
        self.__selected = True
        self.__canvas.itemconfig(self.__rect, fill='#E5E5E5')

    def unselect(self):
        self.__selected = False
        self.__canvas.itemconfig(self.__rect, fill='#FFFFFF')




class image_text_locations_list_view():

    __distinct_colors = [ '#0000FF', '#FF0000', '#00FF00', '#FFFF00', '#FF00FF', 
               '#FF8080', '#808080', '#800000', '#FF8000']
    

    def __init__(self, canvas: tk.Canvas, x_offset, y_offset, add_location_callback=None) -> None:
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.__canvas = canvas
        self.__text_locations = {}
        self.__text_locations_label = None
        self.__allow_adding_locations = False
        self.__add_location_callback = add_location_callback
        self.__new_link_text_locations_callback = None
        self.__add_text = None 
        self.__selected_text_location = ''
        self.__allow_linking = False
        self.__goto_callback_func = None
        self.__vertical_direction_toggle_callback_func = None


    def __new_link_text_location(self, linked, name):
        color = self.__text_locations[name].get_indication_color()
        if self.__new_link_text_locations_callback:
            self.__new_link_text_locations_callback(linked, name, color)


    def __toggle_vertical_text_direction(self, name, vertical_direction):
        color = self.__text_locations[name].get_indication_color()
        if self.__vertical_direction_toggle_callback_func:
            self.__vertical_direction_toggle_callback_func(name,vertical_direction, color)

    def subscribe_to_new_link_text_location(self, callback):
        self.__new_link_text_locations_callback = callback


    def subscribe_to_goto_link_text_location(self, callback):
        self.__goto_callback_func = callback

    
    def subscribe_to_vertical_direction_toggle(self, callback):
        self.__vertical_direction_toggle_callback_func = callback


    def draw(self, x=0, y=0):
        self.__delete_static_elements()


        self.x = self.x_offset + x # For static elements
        self.y = self.y_offset + y # For static elements
        self.__text_locations_label = self.__canvas.create_text(self.x, self.y,  
                                                                text='Linked Text Locations', 
                                                                font=('Arial',11,'bold'), 
                                                                anchor=tk.NW, 
                                                                fill="#505050")

        text_locations_y_offset = 24 + y
        for key, text_location in self.__text_locations.items():
            text_location.draw(x,text_locations_y_offset)
            text_locations_y_offset = text_locations_y_offset + 30 
            if key == self.__selected_text_location:
                text_location.select()

        self.__draw_add_button(x + 8, text_locations_y_offset)

        return text_locations_y_offset - y

    def __draw_add_button(self, x, y):
        padding = 8
        x = self.x_offset + x # For static elements
        y = self.y_offset + y + padding # For static elements
        
        if self.__allow_adding_locations:
            self.__add_text = self.__canvas.create_text(x, y,  
                                                                text='+ Add new linked text location ', 
                                                                font=('Arial',10,'normal'), 
                                                                anchor=tk.NW, 
                                                                fill="#505050")
        else:
            self.__add_text = self.__canvas.create_text(x, y,  
                                                                text='+ Add new linked text location ', 
                                                                font=('Arial',10,'normal'), 
                                                                anchor=tk.NW, 
                                                                fill="#C0C0C0")
        bounds = self.__canvas.bbox(self.__add_text)
        self.__add_rect = self.__canvas.create_rectangle(bounds[0]-padding ,bounds[1] -padding,bounds[2]+ padding ,bounds[3]+ padding,fill='#FFFFFF', width = 0, tags=('add_text_location'))
        self.__canvas.tag_raise(self.__add_text)
        

        self.__canvas.tag_bind(self.__add_rect,'<Enter>', self.__on_add_enter)
        self.__canvas.tag_bind(self.__add_rect,'<Leave>', self.__on_add_leave)
        self.__canvas.tag_bind(self.__add_text,'<Enter>', self.__on_add_enter)
        self.__canvas.tag_bind(self.__add_text,'<Leave>', self.__on_add_leave)
        self.__canvas.tag_bind(self.__add_rect,'<Button-1>', self.__on_add_click)
        self.__canvas.tag_bind(self.__add_text,'<Button-1>', self.__on_add_click)

    def __redraw(self): # TODO: Make more elegent, function has code smell
        self.draw(self.x - self.x_offset, self.y - self.y_offset)


    def __on_add_enter(self,_):
        self.__canvas.itemconfig(self.__add_rect, fill='#E5E5E5')


    def __on_add_leave(self,_):
        self.__canvas.itemconfig(self.__add_rect, fill='#FFFFFF')

    def __on_add_click(self,_):
        if not self.__allow_adding_locations:
            return 
        
        self.add_text_location()
        self.__redraw()


    def enable_linking(self):
        self.__allow_linking = True
        for _, text_location in self.__text_locations.items():
            text_location.link_view.enable_linking()

    def disable_linking(self):
        self.__allow_linking = False
        for _, text_location in self.__text_locations.items():
            text_location.link_view.disable_linking()
            

    def link_formed_for_text_location(self, text_location_name, vertical_direction):
        self.__text_locations[text_location_name].link_view.link_formed()
        self.__text_locations[text_location_name].link_view.enable_goto()
        
        if not vertical_direction:
            self.__text_locations[text_location_name].remove_vertical_text_direction_button()
            return 
        self.__text_locations[text_location_name].draw_vertical_text_direction_button()
        if vertical_direction == BOTTOM_TO_TOP:
            self.__text_locations[text_location_name].vertical_bottom_to_top()
        else:
            self.__text_locations[text_location_name].vertical_top_to_bottom()


    def link_removed_for_text_location(self, text_location_name):
        self.__text_locations[text_location_name].link_view.link_removed()
        self.__text_locations[text_location_name].link_view.disable_goto()


    def remove_all_links(self):
        for text_location_name, _ in self.__text_locations.items():
            self.__text_locations[text_location_name].link_view.link_removed()
            self.__text_locations[text_location_name].link_view.disable_goto()


    def link_formed_for_all_text_location(self):
        for text_location_name, _ in self.__text_locations.items():
            self.__text_locations[text_location_name].link_view.link_formed()
            self.__text_locations[text_location_name].link_view.enable_goto()
        
        
    def add_text_location(self, name=None,color=None,is_horizontal=True,is_bottom_to_top=True):
        if not name:
            name, color = self.__create_unique_text_location_name_and_color()

        self.__text_locations[name] = image_text_locations_view(self.__canvas, 
                                                                self.x_offset, 
                                                                self.y_offset, 
                                                                name,
                                                                color, 
                                                                self.__select_callback,
                                                                self.__new_link_text_location,
                                                                goto_callback=self.__goto_callback,
                                                                is_horizontal=is_horizontal,
                                                                is_bottom_to_top=is_bottom_to_top,
                                                                vertical_direction_toggle_callback=self.__toggle_vertical_text_direction)
      

        if self.__add_location_callback:
            self.__add_location_callback(name, color)

        if self.__allow_linking:
            self.enable_linking()
        else:
            self.disable_linking()

    def __create_unique_text_location_name_and_color(self):

        new_index_number = 0 
        for name, _ in self.__text_locations.items():
            value = int(name[14:]) # get the number in the name
            if new_index_number <= value:
                new_index_number = value + 1

        color = self.__distinct_colors[new_index_number % 8]
        
        return 'text location ' + str(new_index_number), color


    def clear_text_locations(self):
        self.__text_locations = {}


    def __delete_static_elements(self):
        if self.__text_locations_label:
            self.__canvas.delete(self.__text_locations_label)
            self.__canvas.delete(self.__add_text)
            self.__canvas.delete(self.__add_rect)


    def allow_addition(self):
        self.__allow_adding_locations = True
        if self.__add_text:
            self.__canvas.itemconfig(self.__add_text, fill= "#505050")

    def disallow_addition(self):
        self.__allow_adding_locations = False
        if self.__add_text:
            self.__canvas.itemconfig(self.__add_text, fill= "#C0C0C0")

    def __select_callback(self,key):
        self.__selected_text_location = key
        for key, text_location in self.__text_locations.items():
            if key == self.__selected_text_location:
                text_location.select() 
            else:
                text_location.unselect()


    def __goto_callback(self, text_location_name):
        self.__goto_callback_func(text_location_name)

if __name__ == "__main__":

    root = tk.Tk()

    


    canvas = tk.Canvas(root, bg="white", height=600, width=300)
    
    def callback1():
        print(1)

    def callback2():
        print(2)

    def text_loaction_added_callback(name, color):
        print(name)
        print(color)


    lv = link_view(canvas,5,5,callback1, callback2)
    img = image_view(canvas, 5,30)
    ltv = image_text_locations_view(canvas, 5, 250, 'text location 1')
    ltlv = image_text_locations_list_view(canvas,5, 280,text_loaction_added_callback)
    ltlv.add_text_location()
    ltlv.add_text_location()
    
    def draw(_):
        lv.draw()
        img.draw()
        
        #image = cv2.cvtColor(image,cv2.COLOR_RGBA2BGRA)

        #Rearrang the color channel
        #img.set_image(image)
        ltv.draw()
        ltlv.draw()


    def enable():
        lv.enable_linking()
        lv.enable_goto()
        ltlv.allow_addition()


    def link_added():
        lv.link_formed()

    def link_removed():
        lv.link_removed()


    def disable():
        lv.disable_linking()
        lv.disable_goto()
        ltlv.disallow_addition()


    canvas.bind("<Configure>", draw)
    canvas.update()
    canvas.after(5000,enable)
    canvas.after(10000,link_added)
    canvas.after(15000,link_removed)
    canvas.after(20000,disable)

    canvas.pack()
    root.mainloop()