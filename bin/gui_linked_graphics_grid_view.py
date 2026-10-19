import tkinter as tk
from math import floor
from tkinter import messagebox
from tkinter import font
from typing import Dict

from bin.gui_elements import rounded_text_button
try:
    from bin.gui_elements import custom_label
    from bin.gui_link_view import image_view
    from bin.logic_linked_graphic import Linked_Graphic
except:
    from gui_elements import custom_label
    from gui_link_view import image_view
    from logic_linked_graphic import Linked_Graphic

class mini_linked_graphic_view():
    def __init__(self, id, redraw_callback=None, goto_callback=None,change_callback=None
                    ,scanning_done_callback=None, config=None) -> None:
        self.__id = id 
        self.__linked_graphic = Linked_Graphic(linked_callback=self.__graphic_linked_callback,
                                                change_callback=change_callback,
                                                goto_callback=goto_callback,
                                                is_primary_linked_graphic=True,
                                                scanning_done_callback=self.__scanning_done_callback,
                                                config=config
                                                )
        self.__redraw_callback = redraw_callback
        self.__selection_in_document_selected = False
        self.__scanning_done_callback_func= scanning_done_callback
        self.__label = None


    def set_config(self, config):
        self.__config = config
        self.__linked_graphic.set_config(self.__config)

    def setup_view(self, canvas: tk.Canvas, x , y):
        
        self.__canvas = canvas 
        self.__x = x
        self.__y = y
        self.__image_view = image_view(self.__canvas, x + 0, y + 0)
        self.__label = custom_label(self.__canvas, x - 8, y + 152, text=self.__id, fill= '#505050',size=11,weight="bold")
        self.__linked_graphic.setup_link_view(self.__canvas, x + 100, y + 150)
        self.__test_button = rounded_text_button(self.__canvas,x + 30, 150,5,1,text='TEST'
                                                    ,no_animation=True
                                                    ,callback=self.__test_linked_graphic
                                                    ,font_used=font.Font(family='arial.ttf',size=8,weight='normal'))

    def draw(self, x=0, y=0):
        self.__delete_static_elements()
        self.__image_view.draw(y=y,width=150, height=150)
        self.__label.draw(y=y)
        self.__linked_graphic.draw_link_view(y=y)
        self.__test_button.draw(self.__x + 64,self.__y +154 + y )

    def hide(self):
        self.__delete_static_elements()

    def __delete_static_elements(self):
        if self.__label:
            self.__label.hide()
            self.__test_button.hide()
            self.__image_view.hide()
            self.__linked_graphic.hide_link_view()


    def __test_linked_graphic(self,_,__):
        self.__canvas.config(cursor='wait')
        try:
            self.__linked_graphic.search_current_page()
        except ValueError as error:
            messagebox.showerror('Error starting scan',error)
        self.__canvas.config(cursor='')

    def __scanning_done_callback(self, results):
        self.__scanning_done_callback_func(self.__id, results)


    def set_project_name(self, name):
        self.__linked_graphic.set_project_name(name)

    def __graphic_linked_callback(self, display_image):
        self.__image_view.set_image(display_image)

    def set_document_viewer_path_and_page(self,path,page):
        if page is not None and path is not None:
            self.__linked_graphic.set_document_viewer_path_and_page(path,page)

    def setup_linking_callback_func(self,func):
        self.__linked_graphic.setup_linking_callback_func(func)


    def setup_get_page_text_callback_func(self, func):
        self.__linked_graphic.setup_get_page_text_callback_func(func)


    def setup_text_roi_callback_func(self,func):
        self.__linked_graphic.setup_text_roi_callback_func(func)

    def enable_linking(self):
        self.__linked_graphic.enable_link_view()


    def disable_linking(self):
        self.__linked_graphic.disable_link_view()

    def set_full_page_image(self, image, pdf_zoom):
        self.__linked_graphic.set_full_page_image(image, pdf_zoom)

    def start_scan(self):
        try:
            self.__linked_graphic.start_scan()
        except Exception as error:
            raise ValueError(error)

    def check_scanner_progress(self):
        return  self.__linked_graphic.check_scanner_progress()
        





class linked_graphics_grid_view():
    def __init__(self,name, description, add_linked_graphics_cell_callback=None) -> None:
        self.__name = name 
        self.__description = description
        self.__config = None
        self.__linked_graphics: Dict[str,mini_linked_graphic_view] = {}
        self.__name_label = None
        self.__allow_adding_locations = False
        self.__add_linked_graphic_cell_callback = add_linked_graphics_cell_callback
        self.__new_linked_graphic_callback = None
        self.__add_text = None 
        self.__selected_text_location = ''
        self.__allow_linking = False
        self.__goto_callback_func = None
        self.__full_page_image = None
        self.__pno = 0
        self.__path = None
        self.__page = None
        self.__project_name = None


    def setup_view(self, canvas: tk.Canvas, x_offset, y_offset, ):
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.__canvas = canvas


    def set_config(self, config):
        self.__config = config
        for _, linked_graphic in self.__linked_graphics.items():
            linked_graphic.set_config(self.__config)


    def set_project_name(self, name):
        self.__project_name = name
        for _, linked_graphic in self.__linked_graphics.items():
            linked_graphic.set_project_name(name)


    def __new_linked_graphic(self, linked, id):
        if self.__new_linked_graphic_callback:
            self.__new_linked_graphic_callback(linked, id)

    def document_selection_subscription(self, selected , **kwargs):
        self.__selection_in_document_selected = selected
        self.__check_if_selection_in_document_made() 
        for _, linked_graphic in self.__linked_graphics.items():
            linked_graphic.setup_linking_callback_func(kwargs.get('roi_select_func',None))
            linked_graphic.setup_text_roi_callback_func(kwargs.get('text_roi_selected_func',None))
            linked_graphic.setup_get_page_text_callback_func(kwargs.get('get_text_on_page_func',None))
    

    def __check_if_selection_in_document_made(self):
        if self.__selection_in_document_selected:
            self.__enable_linking()
        else:
            self.__disable_linking()


    def __enable_linking(self):
        for _, linked_graphic in self.__linked_graphics.items():
            linked_graphic.enable_linking()

    
    def __disable_linking(self):
        for _, linked_graphic in self.__linked_graphics.items():
            linked_graphic.disable_linking()


    def __linked_graphic_change(self):
        pass


    def subscribe_to_new_linked_graphic(self, callback):
        self.__new_linked_graphic_callback = callback

    def subscribe_to_goto_link_text_location(self, callback):
        self.__goto_callback_func = callback

    def draw(self, x=0, y=0):
        self.__delete_static_elements()


        self.x = self.x_offset + x # For static elements
        self.y = self.y_offset + y # For static elements
        self.__name_label = self.__canvas.create_text(self.x + 2, self.y,  
                                                                text=self.__name, 
                                                                font=('Arial',11,'bold'), 
                                                                anchor=tk.NW, 
                                                                fill="#505050")
        self.__description_label = self.__canvas.create_text(self.x + 2, self.y + 24,  
                                                                text=self.__description, 
                                                                anchor=tk.NW, 
                                                                fill="#6F6F6F")

        row_offset = 48 + self.y
        cell_x_spacing = 24 
        cell_width = 150
        number_of_cells_in_row = floor(self.__canvas.winfo_width() / (cell_width + cell_x_spacing))
        count_cells_in_row = 0
        
        for _, linked_graphic in self.__linked_graphics.items():
            if count_cells_in_row > (number_of_cells_in_row - 1):
               row_offset = row_offset + 150 + 50
               count_cells_in_row = 0
            
            linked_graphic.setup_view(self.__canvas,self.x + 2 + count_cells_in_row * (cell_width + cell_x_spacing),
                                        row_offset )
            linked_graphic.draw()
            count_cells_in_row = count_cells_in_row + 1

            
        if len(self.__linked_graphics) >0: row_offset = row_offset + 150 + 30
        self.__draw_add_button(self.x_offset + 8, row_offset)

        return row_offset - self.y

    def __delete_static_elements(self):
        if self.__name_label:
            self.__canvas.delete(self.__name_label)
            self.__canvas.delete(self.__description_label)
            self.__canvas.delete(self.__add_text)
            self.__canvas.delete(self.__add_rect)
            for _, linked_graphic in self.__linked_graphics.items():
                linked_graphic.hide()


    def __draw_add_button(self, x, y):
        padding = 8
        y = y + padding # For static elements
        
        if self.__allow_adding_locations:
            self.__add_text = self.__canvas.create_text(x, y,  
                                                                text='+ Add new linked graphic ', 
                                                                font=('Arial',10,'normal'), 
                                                                anchor=tk.NW, 
                                                                fill="#505050")
        else:
            self.__add_text = self.__canvas.create_text(x, y,  
                                                                text='+ Add new linked graphic ', 
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
        
        self.add_linked_graphic()
        self.__redraw()


    def add_linked_graphic(self):
        num = len(self.__linked_graphics)
        if num < 10 : id = '0'+str(num)
        else: id = str(num)
        self.__linked_graphics[id] = mini_linked_graphic_view(id,change_callback=self.__linked_graphic_change,config=self.__config)
        self.__linked_graphics[id].set_document_viewer_path_and_page(self.__path,self.__page)
        self.__linked_graphics[id].set_full_page_image(self.__full_page_image, self.__pdf_zoom)

        if self.__project_name:
            self.__linked_graphics[id].set_project_name(self.__project_name)
            
        if self.__add_linked_graphic_cell_callback:
            self.__add_linked_graphic_cell_callback(id)
            '''
        if self.__allow_linking:
            self.enable_linking()
        else:
            self.disable_linking()'''

    
    def set_document_viewer_path_and_page(self,path,page):
        self.__path = path
        self.__page = page
        for _, linked_graphic in self.__linked_graphics.items():
            linked_graphic.set_document_viewer_path_and_page(self.__path,self.__page)

    def set_full_page_image(self, image, pdf_zoom):
        self.__full_page_image = image
        self.__pdf_zoom = pdf_zoom
        for _, linked_graphic in self.__linked_graphics.items():
            linked_graphic.set_full_page_image(self.__full_page_image, self.__pdf_zoom)


    def allow_addition(self):
        self.__allow_adding_locations = True
        if self.__add_text:
            self.__canvas.itemconfig(self.__add_text, fill= "#505050")

    def disallow_addition(self):
        self.__allow_adding_locations = False
        if self.__add_text:
            self.__canvas.itemconfig(self.__add_text, fill= "#C0C0C0")




if __name__ == '__main__':
    root = tk.Tk()
    canvas = tk.Canvas(root, bg="white", height=1000, width=400)

    v = linked_graphics_grid_view(canvas,0,0)
    v.allow_addition()

    def draw(_):
        v.draw()

    canvas.bind("<Configure>", draw)
    canvas.pack()
    root.mainloop()

    