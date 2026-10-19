try:
    from bin.gui_elements import hover_toggle_button
    from bin.gui_link_view import image_view
    from bin.gui_base64_icons import radio_button_blue,radio_button_dark_gray,radio_button_light_gray,small_user_icon
    from bin.gui_elements import cell_line
except:
    from gui_elements import hover_toggle_button
    from gui_link_view import image_view
    from gui_base64_icons import radio_button_blue,radio_button_dark_gray,radio_button_light_gray,small_user_icon
    from gui_elements import cell_line
import tkinter as tk

class similar_graphics_cell:
    def __init__(self, canvas: tk.Canvas, x,y, name, username) -> None:
        self.__canvas = canvas
        self.__x_offset = x
        self.__y_offset = y
        self.__given_image_view = image_view(self.__canvas, 0, 0)
        self.__hmi_image_view = image_view(self.__canvas, 0, 0 )
        self.__radio_button = hover_toggle_button(self.__canvas, radio_button_blue,radio_button_dark_gray,radio_button_light_gray)
        self.__divider = cell_line(self.__canvas,self.__x_offset + 36,28,0,fill='#E5E5E5')
        self.__user_icon_image = tk.PhotoImage(data=small_user_icon)
        self.__radio_button_window = None
        self.__username = username
        self.__name = name
        self.__user_icon = None
        self.__username_label = None
        self.__name_label = None

    
    def draw(self, x=0,y=0):
        self.__delete()
        y = self.__y_offset + y
        image_square_length = int(self.__canvas.winfo_width()/2) - 48
        self.__user_icon = self.__canvas.create_image(self.__x_offset + 30, y, image=self.__user_icon_image, anchor = tk.NW)
        self.__username_label = self.__canvas.create_text(self.__x_offset + 46,y, text=self.__username, anchor=tk.NW, fill="#6F6F6F")
        self.__name_label = self.__canvas.create_text(self.__x_offset + 30,y + 16, text=self.__name, font=('Arial',13,'bold'), anchor=tk.NW, fill="#555555")
        self.__radio_button_window = self.__canvas.create_window(self.__x_offset +0,10 + y + int(image_square_length/2),anchor=tk.NW,window=self.__radio_button)
        self.__given_image_view.draw(self.__x_offset + 30,y + 40,image_square_length,image_square_length)
        self.__hmi_image_view.draw(self.__x_offset + 40 + image_square_length,y + 40,image_square_length,image_square_length)
        self.__divider.draw(y + image_square_length + 52)


    def __delete(self):
        self.__canvas.delete(self.__radio_button_window)
        self.__given_image_view.hide()
        self.__hmi_image_view.hide()
        self.__canvas.delete(self.__user_icon)
        self.__canvas.delete(self.__username_label)
        self.__canvas.delete(self.__name_label)
        self.__divider.hide()


    def get_radio_button(self):
        return self.__radio_button


    def hide(self):
        self.__delete()
