
try:
    from bin.gui_similar_graphics_cell import similar_graphics_cell
    from bin.gui_elements import button_array
except:
   from gui_similar_graphics_cell import similar_graphics_cell 
   from gui_elements import button_array


import tkinter as tk

class similar_graphics_list_view:
    def __init__(self, canvas: tk.Canvas, x=0, y=0) -> None:
        self.__x = x
        self.__y = y
        self.__canvas = canvas
        self.__similar_graphics_list = [1,2,3]
        self.__cells = []
        self.__radio_button_array = None
        self.__radio_button_list = []
        self.__build_cells()
        

    def insert_cell(self):
        cell = similar_graphics_cell(self.__canvas, self.__x,0,'Tank A','John')
        self.__cells.append(cell)
        self.__redraw_elements()

    def __build_cells(self):
        for similar_graphics in self.__similar_graphics_list:
            cell = similar_graphics_cell(self.__canvas, self.__x,0,'Tank A','John')
            self.__cells.append(cell)

    def draw(self):
        self.__redraw_elements()


    def __redraw_elements(self):
        self.__remove_cells()
        y_offset = self.__y
    
        for cell in self.__cells:
            cell.draw(y = y_offset)
            cell_height = int(self.__canvas.winfo_width()/2)
            y_offset = y_offset + cell_height + 24
            self.__radio_button_list.append(cell.get_radio_button())
            self.__radio_button_array = button_array(self.__radio_button_list,self.__link_to_similar_graphic_callback)

        self.__canvas.config(scrollregion=self.__canvas.bbox(tk.ALL))
            
    def hide(self):
        self.__remove_cells()
        self.__canvas.config(scrollregion=self.__canvas.bbox(tk.ALL))

    def __link_to_similar_graphic_callback(self, value):
        print(value)


    def __remove_cells(self):

        for cell in self.__cells:
            cell.hide()


if __name__ == '__main__':
    root = tk.Tk()

    canvas = tk.Canvas(root)
    canvas.grid()
    canvas.config(background='white', highlightthickness = 0,width=500,height=1000)
    lv = similar_graphics_list_view(canvas)

    def draw(event):
        lv.draw()
        canvas.config(scrollregion=canvas.bbox(tk.ALL))

    canvas.bind('<Configure>', draw)

    root.mainloop()




        

