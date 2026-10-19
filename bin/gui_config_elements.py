

import tkinter as tk
from tkinter.constants import LEFT
try:
    from bin.gui_elements import hover_toggle_button
    from bin.gui_base64_icons import left_arrow_blue, left_arrow_gray, up_arrow_blue, up_arrow_gray
    from bin.gui_base64_icons import right_arrow_blue, right_arrow_gray, down_arrow_blue, down_arrow_gray
    from bin.gui_base64_icons import center_blue, center_gray, radio_button_blue,radio_button_dark_gray,radio_button_light_gray
    from bin.gui_elements import button_array
    from bin.gui_link_view import image_view, link_view
except Exception as e:
    from gui_elements import hover_toggle_button
    from gui_base64_icons import left_arrow_blue, left_arrow_gray, up_arrow_blue, up_arrow_gray
    from gui_base64_icons import right_arrow_blue, right_arrow_gray, down_arrow_blue, down_arrow_gray
    from gui_base64_icons import center_blue, center_gray, radio_button_blue,radio_button_dark_gray,radio_button_light_gray
    from gui_elements import button_array
    from gui_link_view import image_view, link_view

class direction_buttons():

    LEFT = 2
    UP = 3
    RIGHT = 0
    DOWN = 1
    NONE = 4

    def __init__(self,canvas , x, y, callback) -> None:
        self.__canvas = canvas
        self.__x = x
        self.__y = y

        self.__callback_func = callback

        self.__left_button = hover_toggle_button(self.__canvas, left_arrow_blue,left_arrow_gray)
        self.__up_button = hover_toggle_button(self.__canvas, up_arrow_blue,up_arrow_gray)
        self.__right_button = hover_toggle_button(self.__canvas, right_arrow_blue,right_arrow_gray)
        self.__down_button = hover_toggle_button(self.__canvas, down_arrow_blue,down_arrow_gray)
        self.__center_button = hover_toggle_button(self.__canvas, center_blue,center_gray)
        self.__button_array = button_array([self.__right_button, self.__down_button, self.__left_button, self.__up_button, self.__center_button],callback=self.__callback)
        self.__border = None 


    def draw(self, x, y):
        self.__delete_elements()
        x = x + self.__x
        y = y + self.__y
        button1_window = self.__canvas.create_window(x + 3, y + 25, anchor='nw', window=self.__left_button)
        button2_window = self.__canvas.create_window(x + 25, y + 3, anchor='nw', window=self.__up_button)
        button3_window = self.__canvas.create_window(x + 36, y + 25, anchor='nw', window=self.__right_button)
        button4_window = self.__canvas.create_window(x + 25, y + 36, anchor='nw', window=self.__down_button)
        button5_window = self.__canvas.create_window(x + 26, y + 26, anchor='nw', window=self.__center_button)


        self.__border = self.round_rectangle( x,y,
                                            x + 61,y + 61, 
                                            radius=10, borderwidth=1,
                                            fill="white",outline='#E5E5E5')

    def set(self, value):
        self.__button_array.remove_selection()
        
        if value == self.LEFT:
            self.__left_button.set()
        elif value == self.RIGHT:
            self.__right_button.set()
        elif value == self.DOWN:
            self.__down_button.set()
        elif value == self.UP:
            self.__up_button.set()

    def __delete_elements(self):
        if self.__border:
            self.__canvas.delete(self.__border)


    def __callback(self,value):
        
        if value == self.NONE:
            self.__button_array.remove_selection()
        self.__callback_func(value)


    def round_rectangle(self,x1, y1, x2, y2, radius=25, borderwidth=1, **kwargs):

        points = [x1+radius, y1,
                  x1+radius, y1,
                  x2-radius, y1,
                  x2-radius, y1,
                  x2, y1,
                  x2, y1+radius,
                  x2, y1+radius,
                  x2, y2-radius,
                  x2, y2-radius,
                  x2, y2,
                  x2-radius, y2,
                  x2-radius, y2,
                  x1+radius, y2,
                  x1+radius, y2,
                  x1, y2,
                  x1, y2-radius,
                  x1, y2-radius,
                  x1, y1+radius,
                  x1, y1+radius,
                  x1, y1]

        return self.__canvas.create_polygon(points, width=borderwidth, **kwargs, smooth=True)


class radio_buttons():
    def __init__(self,canvas , x, y, options_array = [['Option 1','Hello'], ['Option 2','Hi']], callback=None) -> None:
        self.__canvas = canvas
        self.__x = x
        self.__y = y
        self.__options = options_array
        self.__buttons_array = []
        self.__label_ids = []
        self.__callback_func = callback

        for option in options_array:
            button = hover_toggle_button(self.__canvas, radio_button_blue,radio_button_dark_gray,radio_button_light_gray)
            self.__buttons_array.append(button)

        self.__button_array = button_array(self.__buttons_array, callback=self.__callback)

    def draw(self, x=0, y=0):
        if '<Configure>' not in self.__canvas.bind():
            return
        self.__delete_elements()
        x_offset = x + self.__x
        y_offset = y + self.__y

        i = 0
        for button in self.__buttons_array:
            
            self.__canvas.create_window(x_offset, y_offset + 4, anchor='nw', window=button)
            text_label = self.__canvas.create_text(x_offset + 24, y_offset + 1, 
                                            fill = '#505050', text=self.__options[i][0], anchor=tk.NW, 
                                            font=('Roboto Bold',12,'bold'))
            self.__label_ids.append(text_label)
            description_label = self.__canvas.create_text(x_offset + 24, y_offset + 16, 
                                            fill="#6F6F6F", text=self.__options[i][1], anchor=tk.NW )
            self.__label_ids.append(description_label)
            y_offset = y_offset + 56
            i = i + 1

        return y_offset - y - self.__y
       
   
    def __delete_elements(self):

        for label_id in self.__label_ids:
            self.__canvas.delete(label_id)

        self.__label_ids.clear()


    def hide(self):
        self.__delete_elements()


    def select(self, selection):
        index = int(selection)
        if index >= 0:
            self.__button_array.select(int(selection))


    def __callback(self, value):
        if self.__callback_func:
            self.__callback_func(self.__options[value])


class linked_graphic_mini_view():
    def __init__(self, canvas: tk.Canvas, x, y,name='label') -> None:
        self.__canvas = canvas
        self.__x = x
        self.__y = y
        self.__name = name
        self.__image = None
        self.__image_view = image_view(self.__canvas, x, y)
        self.__link_view = link_view(self.__canvas, x, y + 100, self.__link_callback, self.__goto_callback)
        self.__label = None 

    def __link_callback(self, linked):
        pass

    def __goto_callback(self):
        pass

    def draw(self, x, y):
        self.x = x + self.__x
        self.y = y + self.__y
        self.__delete_elements()
        self.__image_view.draw(self.x,self.y,100,100)
        bbox = self.__canvas.bbox(self.__image_view.get_background_id())
        self.__label = self.__canvas.create_text(self.x + 2,self.y + 100 + 4,text=self.__name, fill = '#505050'
                                                    ,font=('Roboto Bold',10,'normal'), anchor=tk.NW)
        self.__link_view.draw(bbox[2] - 52,y)

    def __delete_elements(self):
        if self.__label:
            self.__canvas.delete(self.__label)
        
        

if __name__ == '__main__':
    root = tk.Tk()
    canvas = tk.Canvas(root, bg="white", height=600, width=300)
    b=direction_buttons(canvas,0,0)
    c = radio_buttons(canvas,8,8)
    d = linked_graphic_mini_view(canvas, 0, 0)
    b.draw(50,50)
    b.draw(100,100)
    c.draw(10,0)
    d.draw(150,300)

    def move():
        b.draw(200,200)
        

    canvas.after(5000,move)
    
    canvas.pack()
    root.mainloop()