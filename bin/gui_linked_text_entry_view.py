

from logging import error
import tkinter as tk
from tkinter import messagebox
try:
    from bin.gui_elements import custom_entry
    from bin.gui_link_view import link_view
    from bin.gui_elements import button_array
except:
    from gui_elements import custom_entry
    from gui_link_view import link_view
    from gui_elements import button_array

class linked_text_entry_button():
    def __init__(self, canvas:tk.Canvas, width, height=8,tags=()) -> None:
        self.__canvas = canvas
        self.__tags = tags
        self.callback = None
        self.button_id = None
        self.is_on = False
        self.__window = None
        self.pixel = tk.PhotoImage(width=1, height=1)
        self.__button = tk.Button(self.__canvas,relief='flat',bd=0,width=width,background='#D0D0D0',
                                height=height, image=self.pixel,compound="c", command=self.__callback)
        

    def get_tag_id(self):
        return self.__tags

    def draw(self, x=0, y=0):
        self.__window = self.__canvas.create_window(x,y,anchor='nw',window= self.__button)


    def delete(self):
        if self.__window:
            self.__canvas.delete(self.__window)
            self.__window = None

    
    
    def set(self):
        self.__button.config(background='#00AEEF')
        self.is_on = True


    def reset(self):
        self.__button.config(background='#D0D0D0')
        self.is_on = False

    def __callback(self):
        if self.callback:
            self.callback(self.button_id,self.__tags)


class linked_text_entry(custom_entry):

    TOP_SIDE = 'top'
    BOTTOM_SIDE = 'bottom'

    def __init__(self, canvas: tk.Canvas, x_offset=0, y_offset=0,validatecommand=None, **kwargs) -> None:
        self.__canvas = canvas
        self.__x_offset = x_offset
        self.__y_offset = y_offset
        self.__placeholder_spacing = 14
        self.__is_drawn = False
        custom_entry.__init__(self,self.__canvas,
                                self.__x_offset,
                                self.__y_offset, 
                                placeholder_spacing= self.__placeholder_spacing,
                                validatecommand=validatecommand,
                                **kwargs)
        self.__link_view = link_view(self.__canvas,
                                        self.__x_offset,
                                        self.__y_offset + 16 + self.__placeholder_spacing,
                                        self.__linked_callback,
                                        self.__goto_link_callback)
        self.menu.add_separator()
        self.menu.add_command(label="Link")
        self.entry.bind('<ButtonRelease-1>',self.__selection)

        self.__selected_text = {}
        self.__selected_text_button = []
        self.__selected_text_button_array = []
        self.__button_array = None
        self.__text_link_callback = None 
        self.__go_to_callback = None
        self.__selected_tag_id = None
        self.debugging = False
        self.__switch_test = False

    def entry_callbackOut(self, _):
        
        super().entry_callbackOut(_)
        self.__link_view.disable_linking()
        self.__link_view.disable_goto()
        if self.__button_array:
            self.__button_array.remove_selection()
        
    def __selection(self, event):

        if not self.entry.select_present():
            self.__link_view.force_disable_linking()
            return

        start = self.entry.index("sel.first")
        end = self.entry.index("sel.last")     

        start_ = -1
        end_ = -1

        if self.__button_array:
            index = self.__button_array.get_selected_button()
            if index is not None:
                tag_id = self.__selected_text_button_array[index].get_tag_id()

                start_ = self.__selected_text[tag_id][0]
                end_ = self.__selected_text[tag_id][1] 

        if start == start_ and end == end_:
            pass
        else:
            self.__link_view.link_removed()
            self.__link_view.disable_goto()
            if self.__button_array:
                self.__button_array.remove_selection()


    def draw(self,x=0,y=0):
        super().draw(x,y, max_x = self.__canvas.winfo_width() - 50)
        self.__link_view.draw(self.__canvas.winfo_width() - 60,y)
        self.__is_drawn = True


    def hide(self):
        super().hide()
        self.__is_drawn = False
        self.__link_view.hide()
        for button in self.__selected_text_button_array:
            button.delete()


    def set_text(self, text):
        self.entry.delete(0,tk.END)
        self.entry.insert(0,text)   
        self.entry.destroy_listbox()
        self.entry.listboxUp = False


    def show_textmenu(self, event):
        e_widget = event.widget
        self.menu.entryconfigure("Cut",command=lambda: e_widget.event_generate("<<Cut>>"))
        self.menu.entryconfigure("Copy",command=lambda: e_widget.event_generate("<<Copy>>"))
        self.menu.entryconfigure("Paste",command=lambda: e_widget.event_generate("<<Paste>>"))
        self.menu.entryconfigure("Select all",command=lambda: e_widget.select_range(0, 'end'))
        self.menu.entryconfigure("Link",command=lambda: self.__linked_callback(True))
        self.menu.tk.call("tk_popup", self.menu, event.x_root, event.y_root)

    
    def set_text_link_callback(self,callback):
        self.__text_link_callback = callback


    def set_go_to_callback(self,callback):
        self.__go_to_callback = callback


    def __linked_callback(self, linked):
        """ Links or Unlinks depending on whether the selected text is choosen by the button """
        start = self.entry.index("sel.first")
        end = self.entry.index("sel.last")


         
        start_ = -1
        end_ = -1
        # Determine if a button and its text has been selected
        if self.__button_array:
            index = self.__button_array.get_selected_button()
            if index is not None:
                tag_id = self.__selected_text_button_array[index].get_tag_id()

                start_ = self.__selected_text[tag_id][0]
                end_ = self.__selected_text[tag_id][1]

        
        # If a button and its text has been selected 
        if start == start_ and end == end_:
            if self.debugging:
                self.unlink_text(index)
                return

            # Unlink text
            self.__text_link_callback(False, (start, end), self.entry.get(),self.name)
            self.unlink_text(index)

        else:
            
            # Link text
            if self.debugging:
                if self.__switch_test:
                    self.primary_link_text(start, end)
                    self.__switch_test = not self.__switch_test
                else:
                    self.secondary_link_text(start, end)
                    self.__switch_test = not self.__switch_test
                return

            try:
                side_to_show_link = self.__text_link_callback(True, (start, end), self.entry.get(),self.name)
                if side_to_show_link == self.TOP_SIDE:
                    self.primary_link_text(start, end)
                else:
                    self.secondary_link_text(start, end)
            except ValueError as error:
                messagebox.showerror('Error linking text',error)
                return

            

    def unlink_text(self, index):
        button = self.__selected_text_button_array.pop(index)
        button.delete()
        self.__button_array = button_array(self.__selected_text_button_array,
                                            self.__substring_selected_callback)
        self.__link_view.disable_goto()
        self.__link_view.link_removed()
        
        
    def primary_link_text(self, start, end):
        start_x = self.x + 17 + self.font.measure(self.entry.get()[:start]) 
        width = self.font.measure(self.entry.get()[start:end])

        tag_id = '{start}-{end}'.format(start=start,end=end)
        self.__selected_text[tag_id] = (start,end,self.TOP_SIDE)
        
        button = linked_text_entry_button(self.__canvas,width,tags=tag_id)
        if self.__is_drawn:
            button.draw(start_x - 1,self.y + 8 + self.__placeholder_spacing)
        self.__link_view.link_formed()
        self.__selected_text_button_array.append(button)
        self.__button_array = button_array(self.__selected_text_button_array,
                                            self.__substring_selected_callback)

        
        
    def secondary_link_text(self, start, end):
        start_x = self.x + 17 + self.font.measure(self.entry.get()[:start]) 
        width = self.font.measure(self.entry.get()[start:end])

        tag_id = '{start}-{end}'.format(start=start,end=end)
        self.__selected_text[tag_id] = (start,end,self.BOTTOM_SIDE)
        
        button = linked_text_entry_button(self.__canvas,width,tags=tag_id)
        if self.__is_drawn:
            button.draw(start_x - 1,self.y + 8 + self.__placeholder_spacing + 34)
        self.__link_view.link_formed()
        self.__selected_text_button_array.append(button)
        self.__button_array = button_array(self.__selected_text_button_array,
                                            self.__substring_selected_callback)
            
       
        
    def __substring_selected_callback(self, id):
        tag_id = self.__selected_text_button_array[id].get_tag_id()
        self.__selected_tag_id = tag_id

        start = self.__selected_text[tag_id][0]
        end = self.__selected_text[tag_id][1]
        
        
        self.entry.select_range(start,end)

        self.entry.focus()

        self.__link_view.enable_goto()
        self.__link_view.link_formed()

    def __goto_link_callback(self):
        if self.__selected_tag_id:
            self.__go_to_callback(self.name,self.__selected_tag_id,self.name)

    def enable_linking(self):
        self.__link_view.enable_linking()

    def disable_linking(self):
        self.__link_view.disable_linking()


if __name__ == "__main__":

    root = tk.Tk()

    canvas = tk.Canvas(root)
    canvas.grid(row=0, column=1)
    canvas.config(background='white')
    a = linked_text_entry(canvas, 0,0,placeholder='Name')
    a.debugging = True
    b = linked_text_entry(canvas, 0,70,placeholder='Name')
    b.debugging = True

    def redraw(event):
        global a
        a.draw()
        b.draw()


    canvas.bind('<Configure>', redraw)  # canvas is resized
    
    canvas.update()

    root.mainloop()
    
    