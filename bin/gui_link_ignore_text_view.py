import re
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox

from bin.gui_elements import button_array, hover_toggle_button
from bin.gui_parameter_selection import drop_down_selector
from bin.logic_linked_texts import LinkedText

try:
    from bin.gui_approval_view import rectangle_canvas_button
    from bin.gui_link_view import link_view
    from bin.gui_linked_text_entry_view import linked_text_entry
    from bin.gui_base64_icons import cell_reference_blue, cell_reference_dark_gray, cell_reference_light_gray
except:
    from gui_approval_view import rectangle_canvas_button
    from gui_link_view import link_view
    from gui_linked_text_entry_view import linked_text_entry
    from gui_base64_icons import cell_reference_blue, cell_reference_dark_gray, cell_reference_light_gray

#from bin.gui_link_view import link_ignore_view

class link_ignore_text_view(tk.Text):

    REMOVE_TAG = "remove"
    LINKED_TAG = "highlight"

    def __init__(self, canvas:tk.Canvas,name="Linked Text",placeholder_spacing=0
                 ,selection_callback=None,ignore_text_callback=None,unignore_text_callback=None, *args, **kwargs):
        super().__init__(canvas, *args, **kwargs)
        self.configure(state=tk.DISABLED)
        self.canvas = canvas
        self.name = name
        self.placeholder = name
        self.placeholder_color = '#505050'
        self.placeholder_spacing = placeholder_spacing
        self.text_window = None
        self.selection_callback = selection_callback
        self.text_font = tkfont.Font(family="Arial", size=11)
        self.config(font=self.text_font, foreground='#404040', pady=10
                    , background='#ECECEC',bd=0, wrap=tk.WORD)
        
        linked_font = tkfont.Font(family='Arial',size=11,weight='bold')
        remove_font = tkfont.Font(family='Arial',size=10,overstrike=1)
        
        # sample tag
        self.tag_config(self.REMOVE_TAG, background="#F6C8C8", font=remove_font)
        self.tag_config(self.LINKED_TAG, background="#C5FFB7", font=linked_font)
        self.tag_configure('highlight_blue', foreground="white", background="#0078d7")
        self.tag_config("center", justify='center')
        self.start_index = None
        self.end_index = None
        self.bind('<ButtonRelease-1>',self.__selection)
        self.bind('<ButtonRelease-3>',self.__show_menu)
        self.menu = tk.Menu(self, tearoff=0)
        self.ignore_text_callback = ignore_text_callback
        self.unignore_text_callback = unignore_text_callback
        self.ignore_text_menu_item = "Ignore text"
        self.unignore_text_menu_item = "Unignore text"
        self.menu.add_command(label=self.ignore_text_menu_item, command=self.__on_ignore_text)
        self.menu.add_command(label=self.unignore_text_menu_item, command=self.__on_unignore_text)
        
    def __width(self):
        return self.canvas.winfo_width()-32
    
    def __selection(self, _):
        self.remove_mark_blue()
        if not self.tag_ranges(tk.SEL):
            self.start_index = None
            self.end_index = None
            return 
        
        self.start_index = self.index("sel.first")
        self.end_index = self.index("sel.last") 
        self.__mark_blue()


    def __mark_blue(self):
        
        if self.start_index and self.end_index:
            #self.remove_mark_blue()
            self.tag_add('highlight_blue',self.start_index, self.end_index)
            


    def remove_mark_blue(self):
        if self.start_index and self.end_index:
            self.tag_remove('highlight_blue',self.start_index,self.end_index)
        self.start_index = None
        self.end_index = None
        


    def get_text_selection(self):
        return self.start_index, self.end_index
    

    def __is_selection_ignored(self):
        """Check if the current selection has the REMOVE_TAG (is ignored)"""
        if not self.start_index or not self.end_index:
            return False
        
        # Get all tags in the selection range
        tags_in_selection = self.tag_names(self.start_index)
        
        # Check if any character in the selection has the REMOVE_TAG
        current_index = self.start_index
        while self.compare(current_index, '<', self.end_index):
            tags_at_index = self.tag_names(current_index)
            if self.REMOVE_TAG in tags_at_index:
                return True
            current_index = self.index(f"{current_index}+1c")
        
        return False
    

            
    def get_text(self):
        return self.get('1.1',tk.END)
    

    def get_text_indexes(self):
        return '1.1', self.index('end-1c')


    def __show_menu(self, event):
        if self.start_index and self.end_index:
            is_ignored = self.__is_selection_ignored()
            
            if is_ignored:
                # Selection is ignored, show "Unignore text" option
                self.menu.entryconfigure(self.ignore_text_menu_item, state='disabled')
                self.menu.entryconfigure(self.unignore_text_menu_item, state='normal')
            else:
                # Selection is not ignored, show "Ignore text" option
                self.menu.entryconfigure(self.ignore_text_menu_item, state='normal')
                self.menu.entryconfigure(self.unignore_text_menu_item, state='disabled')
        else:
            # No selection, disable both options
            self.menu.entryconfigure(self.ignore_text_menu_item, state='disabled')
            self.menu.entryconfigure(self.unignore_text_menu_item, state='disabled')
        
        self.menu.post(event.x_root, event.y_root)


    def __on_ignore_text(self):
        if self.ignore_text_callback:
            self.ignore_text_callback(self.name)


    def __on_unignore_text(self):
        """Remove ignore highlighting from the selected text"""
        if self.start_index and self.end_index:
            self.tag_remove(self.REMOVE_TAG, self.start_index, self.end_index)
            
        # Call the unignore callback if available, otherwise fall back to ignore callback
        if self.unignore_text_callback:
            self.unignore_text_callback(self.name)


    def draw(self, x, y):

        self.__delete_elements()

        self.text_window = self.canvas.create_window(x + 16,y + 24 + self.placeholder_spacing, anchor='nw', window=self
                                  , width=self.__width())
        self.config(height=self.calculate_text_lines() + 1) 
        
        self.tag_add("center", "1.0", "end")
        return self.winfo_height()


    def __delete_elements(self):
        if self.text_window:
            self.canvas.delete(self.text_window)


    def hide(self):
        self.__delete_elements()


    def insert(self, string):
        self.configure(state=tk.NORMAL)
        self.delete('1.0',tk.END)
        super().insert('1.0', ' '+string+'')
        self.tag_add("center", "1.0", "end")
        self.configure(state=tk.DISABLED)


    def highlight_remove(self,start,end):
        start_index = f'1.0+{start+1}c'
        end_index = f'1.0+{end+1}c'
        self.tag_add(self.REMOVE_TAG, start_index, end_index)


    def unignore_remove(self,start,end):
        """Remove ignore highlighting from a specific range"""
        start_index = f'1.0+{start+1}c'
        end_index = f'1.0+{end+1}c'
        self.tag_remove(self.REMOVE_TAG, start_index, end_index)


    def highlight_linked(self,start,end):
        start_index = f'1.0+{start+1}c'
        end_index = f'1.0+{end+1}c'
        self.tag_add(self.LINKED_TAG, start_index, end_index)
    

    def clean_highlights(self, _=None):
        self.tag_remove(self.REMOVE_TAG, "1.0", tk.END)
        self.tag_remove(self.LINKED_TAG, "1.0", tk.END)

    
    def calculate_text_lines(self):
        
    
        text = self.get('1.0',tk.END)
        # Count explicit newlines
        newline_count = text.count('\n')
    
        # Calculate wrapped lines
        wrapped_lines = 0
        for line in text.split('\n'):
            line_width = self.text_font.measure(line)
            wrapped_lines += -(-line_width // self.__width())  # Ceiling division
        
        return max(newline_count, wrapped_lines)
    


class linked_text_ignore_entry(linked_text_entry):
    
    
    def __init__(self, canvas: tk.Canvas, x_offset=0, y_offset=0,validatecommand=None,get_text_link_callback=None,given_text_link_callback=None
                 ,key_text_link_callback=None,given_text_unlink_callback=None,ignore_text_callback=None,unignore_text_callback=None,redraw_callback=None
                 ,goto_callback=None,given_text_goto_callback=None,is_parameter=False,**kwargs):
        self.__canvas = canvas
        self.__cell_reference_1_button = hover_toggle_button(self.__canvas, cell_reference_blue,cell_reference_dark_gray,cell_reference_light_gray)
        self.__cell_reference_2_button = hover_toggle_button(self.__canvas, cell_reference_blue,cell_reference_dark_gray,cell_reference_light_gray)
        self.__cell_reference_3_button = hover_toggle_button(self.__canvas, cell_reference_blue,cell_reference_dark_gray,cell_reference_light_gray)
        self.__cell_reference_4_button = hover_toggle_button(self.__canvas, cell_reference_blue,cell_reference_dark_gray,cell_reference_light_gray)
        self.__cell_references_button_array = button_array([self.__cell_reference_1_button
                                               ,self.__cell_reference_2_button
                                               ,self.__cell_reference_3_button
                                               ,self.__cell_reference_4_button], callback=self.__cell_reference_callback)
        self.__button_windows = []
        self.__selected_cell_reference = 0
        self.__text_link_button = rectangle_canvas_button('Link Text',canvas,self.on_given_text_link)
        self.__linked_text_name = kwargs.get('placeholder','Linked Text')
        self.__link_ignore_text_view = link_ignore_text_view(canvas
                                                             ,name=self.__linked_text_name
                                                             ,ignore_text_callback=ignore_text_callback
                                                             ,unignore_text_callback=unignore_text_callback)
        self.__text_link_view = link_view(canvas
                                                ,goto_callback=self.__on_goto_linked_text
                                                ,link_callback=self.__on_given_text_unlink
                                                )
        
        
        kwargs['placeholder'] = ''
        self.__heading_text = None
        self.__get_text_link_callback = get_text_link_callback
        self.__given_text_link_callback = given_text_link_callback
        self.key_text_link_callback = key_text_link_callback
        self.__given_text_unlink_callback = given_text_unlink_callback
        self.__goto_text_link_callback = goto_callback
        self.__given_text_goto_callback = given_text_goto_callback
        self.__redraw_callback = redraw_callback
        self.__x_offset = x_offset
        self.__y_offset = y_offset
        self.__is_parameter = is_parameter
        self.__is_table_text = False
        self.__given_text_id = None
        super().__init__(canvas, x_offset, y_offset,validatecommand, **kwargs, bottom_error=True)
        self.set_text_link_callback(self.__on_text_link)
        self.set_go_to_callback(goto_callback)
        self.name = self.__linked_text_name


    def __on_text_link(self,link, indexes, string, name):
        result = self.key_text_link_callback(link, indexes, string, name)
        self.__redraw_callback(self.__linked_text_name)
        return result
        

    def __cell_reference_callback(self, value):
        if self.__selected_cell_reference != value:
            self.__selected_cell_reference = value
            self.__redraw_callback(self.__linked_text_name)

        
    def on_given_text_link(self, option=None):
        given_text_data = self.__given_text_link_callback(self.__linked_text_name, option)
        if given_text_data:
            given_text, id = given_text_data
            self.__given_text_id = id
            given_text = re.sub(r'\\(.)', r'\1',str(given_text))
            self.__link_ignore_text_view.insert(given_text)
        else:
            messagebox.showinfo("No text selected", f"Please select text on the document.")
            return None
        self.__redraw_callback(self.__linked_text_name)
        return given_text, id

    
    def get_text_view_selection(self):
        start , end = self.__link_ignore_text_view.get_text_selection()
        return start , end , self.__given_text_id
    

    def get_full_text_view_selection(self):
        start, end =  self.__link_ignore_text_view.get_text_indexes()
        return start, end, self.__given_text_id
    

    def remove_text_view_selection(self):
        self.__link_ignore_text_view.remove_mark_blue()

    
    def __on_given_text_unlink(self, _):
        
        self.__given_text_unlink_callback(self.__linked_text_name, self.__given_text_id)
        self.__redraw_callback(self.__linked_text_name)


    def __on_goto_linked_text(self):
        if self.__given_text_goto_callback:
            self.__given_text_goto_callback(self.__linked_text_name, self.__given_text_id)


    def set_given_text(self, text, id ):
        self.__link_ignore_text_view.insert(re.sub(r'\\(.)', r'\1',str(text)))
        self.__given_text_id = id


    def set_key_indexes(self, indexes):
        if not indexes:
            return
        
        for index in indexes:
            self.__link_ignore_text_view.highlight_linked(index[0],index[1])

    def set_ignore_indexes(self, indexes):
        if not indexes:
            return
        
        for index in indexes:
            self.__link_ignore_text_view.highlight_remove(index[0],index[1])

    
    def reset(self):
        self.__link_ignore_text_view.insert('')
        self.__link_ignore_text_view.clean_highlights()
        self.__text_link_view.link_removed()
        self.__text_link_view.disable_goto()
        self.__given_text_id = None
        self.__redraw_callback(self.__linked_text_name)


    def seletection_is_table_text(self, is_table_text):
        self.__is_table_text = is_table_text




    def draw(self,x=0,y=0):
        x = x + self.__x_offset
        y = y + self.__y_offset
        link_ignore_text_height = 0


        
        
        if self.__is_parameter:
            linked_text:LinkedText = self.__get_text_link_callback(self.__linked_text_name)
        else:
            linked_text:LinkedText = self.__get_text_link_callback()
        
        if self.__is_table_text or (linked_text and linked_text.given_text) or self.thinking:
            if linked_text and linked_text.given_text:
                for i in range(4):
                    if i < len(linked_text.given_text):
                        button = self.__cell_references_button_array.array_buttons[i]
                        button_window = self.__canvas.create_window(self.__canvas.winfo_width() - 30*(3+i), y+4, anchor='nw', window=button)
                        self.__button_windows.append(button_window)
                        
                self.__cell_references_button_array.select(self.__selected_cell_reference)

                self.__given_text_id = list(linked_text.given_text.keys())[self.__selected_cell_reference]
                given_text = str(linked_text.given_text[self.__given_text_id].text)

                self.__link_ignore_text_view.insert(re.sub(r'\\(.)', r'\1',given_text))
                self.__text_link_view.link_formed()
                if self.__given_text_goto_callback:
                    self.__text_link_view.enable_goto()

                key_indexes = []
                if linked_text.links:
                    for _, link in linked_text.links.items():
                        if link.given_text_id == self.__given_text_id and link.given_text_indexes:
                            key_indexes.append(link.given_text_indexes)
                ignore_indexes = linked_text.given_text[self.__given_text_id].key_and_ignore_indexes
                # Filter out key indexes out of ignore indexes
                if ignore_indexes:
                    ignore_indexes = [index for index in ignore_indexes if index not in key_indexes]

                self.set_key_indexes(key_indexes)

                self.set_ignore_indexes(ignore_indexes)

            link_ignore_text_height = self.__link_ignore_text_view.draw(x, y+4)
            self.__text_link_view.draw(self.__canvas.winfo_width() - (30*2),y+4)
            super().draw(x,y + link_ignore_text_height + 8)
        else:
            self.__text_link_button.draw(int(self.__canvas.winfo_width()/2) - 16, y + 50)

        self.__heading_text = self.canvas.create_text(x + 16, y + 2, fill = '#505050', text=self.__linked_text_name,
                                anchor=tk.NW, font=tkfont.Font(family="arial.ttf",size=11,weight="bold"))

        return link_ignore_text_height


    def hide(self):
        self.__text_link_button.hide()
        self.__text_link_view.hide()
        self.__link_ignore_text_view.hide()
        
        for button_window in self.__button_windows:
            self.canvas.delete(button_window)

        self.__button_windows = []
        super().hide()
        if self.__heading_text:
            self.canvas.delete(self.__heading_text)



class linked_text_ignore_selector(drop_down_selector):
    def __init__(self, canvas:tk.Canvas,name, default,options, x_offset=0, y_offset=0,validatecommand=None,get_text_link_callback=None,given_text_link_callback=None
                ,key_text_link_callback=None,given_text_unlink_callback=None,ignore_text_callback=None,unignore_text_callback=None,redraw_callback=None
                ,goto_callback=None,given_text_goto_callback=None,is_parameter=False,**kwargs):
        self.__canvas = canvas
        self.__cell_reference_1_button = hover_toggle_button(self.__canvas, cell_reference_blue,cell_reference_dark_gray,cell_reference_light_gray)
        self.__cell_reference_2_button = hover_toggle_button(self.__canvas, cell_reference_blue,cell_reference_dark_gray,cell_reference_light_gray)
        self.__cell_reference_3_button = hover_toggle_button(self.__canvas, cell_reference_blue,cell_reference_dark_gray,cell_reference_light_gray)
        self.__cell_reference_4_button = hover_toggle_button(self.__canvas, cell_reference_blue,cell_reference_dark_gray,cell_reference_light_gray)
        self.__cell_references_button_array = button_array([self.__cell_reference_1_button
                                            ,self.__cell_reference_2_button
                                            ,self.__cell_reference_3_button
                                            ,self.__cell_reference_4_button], callback=self.__cell_reference_callback)
        self.__button_windows = []
        self.__selected_cell_reference = 0
        self.__text_link_button = rectangle_canvas_button('Link Text',canvas,self.__on_given_text_link)
        self.__linked_text_name = name
        self.__link_ignore_text_view = link_ignore_text_view(canvas
                                                            ,name=self.__linked_text_name
                                                            ,ignore_text_callback=ignore_text_callback
                                                            ,unignore_text_callback=unignore_text_callback)
        self.__text_link_view = link_view(canvas
                                                ,goto_callback=self.__on_goto_linked_text
                                                ,link_callback=self.__on_given_text_unlink
                                                )
        
        
        
        self.__placeholder_text = None
        self.__get_text_link_callback = get_text_link_callback
        self.__given_text_link_callback = given_text_link_callback
        self.key_text_link_callback = key_text_link_callback
        self.__given_text_unlink_callback = given_text_unlink_callback
        self.__goto_text_link_callback = goto_callback
        self.__given_text_goto_callback = given_text_goto_callback
        self.__redraw_callback = redraw_callback
        self.__x_offset = x_offset
        self.__y_offset = y_offset
        self.__is_parameter = is_parameter
        self.__is_table_text = False
        self.__given_text_id = None
        self.error_found = False
        self.error_text = None
        super().__init__(canvas, name,  default,options, **kwargs)
        self.set_link_callback(self.__on_text_link)
        self.set_go_to_callback(goto_callback)
        self.name = self.__linked_text_name

    def __on_text_link(self,link, indexes, string, name):
        result = self.key_text_link_callback(link, indexes, string, name)
        self.__redraw_callback(self.__linked_text_name)
        return result
        

    def __cell_reference_callback(self, value):
        if self.__selected_cell_reference != value:
            self.__selected_cell_reference = value
            self.__redraw_callback(self.__linked_text_name)

        
    def __on_given_text_link(self):
        given_text_data = self.__given_text_link_callback(self.__linked_text_name)
        if given_text_data:
            given_text, id = given_text_data
            self.__given_text_id = id
            self.__link_ignore_text_view.insert(re.sub(r'\\(.)', r'\1',str(given_text)))

        self.__redraw_callback(self.__linked_text_name)

    
    def get_text_view_selection(self):
        start , end = self.__link_ignore_text_view.get_text_selection()
        return start , end , self.__given_text_id
    

    def primary_link_text(self, start, end):
        pass

    

    def remove_text_view_selection(self):
        self.__link_ignore_text_view.remove_mark_blue()

    
    def __on_given_text_unlink(self, _):
        
        self.__given_text_unlink_callback(self.__linked_text_name, self.__given_text_id)
        self.__redraw_callback(self.__linked_text_name)


    def __on_goto_linked_text(self):
        if self.__given_text_goto_callback:
            self.__given_text_goto_callback(self.__linked_text_name, self.__given_text_id)


    def set_given_text(self, text, id ):
        self.__link_ignore_text_view.insert(re.sub(r'\\(.)', r'\1',str(text)))
        self.__given_text_id = id


    def set_key_indexes(self, indexes):
        if not indexes:
            return
        
        for index in indexes:
            self.__link_ignore_text_view.highlight_linked(index[0],index[1])

    def set_ignore_indexes(self, indexes):
        if not indexes:
            return
        
        for index in indexes:
            self.__link_ignore_text_view.highlight_remove(index[0],index[1])


    def reset(self):
        self.__link_ignore_text_view.insert('')
        self.__link_ignore_text_view.clean_highlights()
        self.__text_link_view.link_removed()
        self.__text_link_view.disable_goto()
        self.__given_text_id = None
        self.__redraw_callback(self.__linked_text_name)

    def seletection_is_table_text(self, is_table_text):
        self.__is_table_text = is_table_text


    def error(self,error_message=None, show_as_warning=None):
        if error_message is None:
            error_message = self.error_message
        if show_as_warning is None:
            show_as_warning = self.show_as_warning
        self.error_color = '#ed9401' if show_as_warning else '#B91F3B'
        self.__canvas.itemconfig(self.error_text, fill=self.error_color)
        self.__canvas.itemconfig(self.error_text, text=error_message)
        self.error_message = error_message
        self.show_as_warning = show_as_warning
        self.error_found = True


    def reset_error(self):
        if not self.error_found:
            return 

        self.error_found = False
        
        self.__canvas.itemconfig(self.error_text, fill='white')
        self.__canvas.itemconfig(self.error_text, text='')


    def draw(self,x=0,y=0):
        x = x + self.__x_offset
        y = y + self.__y_offset
        link_ignore_text_height = 0


        if self.__is_parameter:
            linked_text:LinkedText = self.__get_text_link_callback(self.__linked_text_name)
        else:
            linked_text:LinkedText = self.__get_text_link_callback()
        
        if self.__is_table_text or (linked_text and linked_text.given_text):
            if linked_text and linked_text.given_text:
                for i in range(4):
                    if i < len(linked_text.given_text):
                        button = self.__cell_references_button_array.array_buttons[i]
                        button_window = self.__canvas.create_window(self.__canvas.winfo_width() - 30*(3+i), y+4, anchor='nw', window=button)
                        self.__button_windows.append(button_window)
                        
                self.__cell_references_button_array.select(self.__selected_cell_reference)

                self.__given_text_id = list(linked_text.given_text.keys())[self.__selected_cell_reference]
                given_text = str(linked_text.given_text[self.__given_text_id].text)

                self.__link_ignore_text_view.insert(re.sub(r'\\(.)', r'\1',given_text))
                self.__text_link_view.link_formed()
                if self.__given_text_goto_callback:
                    self.__text_link_view.enable_goto()
                
                ignore_indexes = linked_text.given_text[self.__given_text_id].key_and_ignore_indexes
                
            
                self.set_ignore_indexes(ignore_indexes)

            link_ignore_text_height = self.__link_ignore_text_view.draw(x, y+4)
            self.__text_link_view.draw(self.__canvas.winfo_width() - (30*2),y+4)
            super().draw(x+16,y + 32 + link_ignore_text_height + 8)
            self.error_text = self.__canvas.create_text(self.__canvas.winfo_width() - 64 , y + link_ignore_text_height + 72, fill = 'white', text='',
                                anchor=tk.NE, font=tkfont.Font(family="arial.ttf",size=9,weight="normal"))
            if self.error_found:
                self.error()
        else:
            self.__text_link_button.draw(int(self.__canvas.winfo_width()/2) - 16, y + 50)

        
        return link_ignore_text_height + 32


    def hide(self):
        self.__text_link_button.hide()
        self.__text_link_view.hide()
        self.__link_ignore_text_view.hide()
        
        for button_window in self.__button_windows:
            self.__canvas.delete(button_window)
            self.__canvas.delete(self.error_text)

        self.__button_windows = []
        super().hide()


class linked_text_boolean_selector(linked_text_ignore_selector):
    def __init__(self, canvas: tk.Canvas, parameter, value=None,**kwargs) -> None:

        self.__canvas = canvas
        self.__placeholder = parameter['Name']

        if parameter['DVal'] == '1':
            default = 'True'
        else:
            default = 'False'

        if value:
            if value == '1':
                default = 'True'
            else:
                default = 'False'

        super().__init__(canvas,self.__placeholder, default, ['False','True'],**kwargs)
        self.__label = None 

    def draw(self,x=0,y=0):
        self.__delete_label()
        self.__label = self.__canvas.create_text(x+16,y, fill = '#505050', text=self.__placeholder,
                                anchor=tk.NW, font=tkfont.Font(family="arial.ttf",size=11,weight="bold"))
        return super().draw(x=x,y=y) + 8

    
    def __delete_label(self):
        if self.__label:
            self.__canvas.delete(self.__label)

    def hide(self):
        self.__delete_label()
        super().hide()





class linked_text_interger_selector(linked_text_ignore_selector):
    def __init__(self, canvas: tk.Canvas, parameter, value=None,**kwargs) -> None:

        self.__canvas = canvas
        self.__label = None
        self.__placeholder = parameter['Name']
        
        if value:
            default = value
        else:
            default = parameter['DVal']
        options = []
        for num in range(int(parameter['Min']), int(parameter['Max'])+1):
            options.append(str(num))
        super().__init__(canvas,self.__placeholder, default,options,**kwargs)

    def draw(self,x=0,y=0):
        self.__delete_label()
        self.__label = self.__canvas.create_text(x+16,y, fill = '#505050', text=self.__placeholder,
                                anchor=tk.NW, font=tkfont.Font(family="arial.ttf",size=11,weight="bold"))
        return super().draw(x=x,y=y) + 8

    def __delete_label(self):
        if self.__label:
            self.__canvas.delete(self.__label)

    def hide(self):
        self.__delete_label()
        super().hide()


class linked_text_string_selector(linked_text_ignore_selector):
    def __init__(self, canvas: tk.Canvas, parameter, value=None,options=None,**kwargs) -> None:
        
        self.__canvas = canvas
        self.__label = None
        if isinstance(parameter, str):
            self.__placeholder = parameter
        else:
            self.__placeholder = parameter['Name']
        
        if value:
            default = value
        else:
            default = parameter['DVal']

        if not options:
            options = parameter['CVals'].split(',')
   
        super().__init__(canvas,self.__placeholder, default,options,**kwargs)

    def draw(self,x=0,y=0):
        self.__delete_label()
        self.__label = self.__canvas.create_text(x+16,y, fill = '#505050', text=self.__placeholder,
                                anchor=tk.NW, font=tkfont.Font(family="arial.ttf",size=11,weight="bold"))
        return super().draw(x=x,y=y) + 8


    def __delete_label(self):
        if self.__label:
            self.__canvas.delete(self.__label)

    def hide(self):
        self.__delete_label()
        super().hide()
    


if __name__ == "__main__":

    root = tk.Tk()

    canvas = tk.Canvas(root)
    #canvas.pack(fill=tk.BOTH, expand=1)
    def ignore_text_callback(start_index, end_index):
        print(start_index, end_index)
              
    def redraw_callback():
        canvas.update()


    def goto_callback():
        print("Goto callback")


    def text_link_callback():
        return "Hello World"
    

    def text_unlink_callback():
        print("Unlink text")

    def get_text_link_callback1():
        return "Hello World"
    
    def get_text_link_callback2():
        return ""

    
    def redraw(event):
        global text
        text.draw(0,0)
        text.highlight_remove(4, 16)
        text.highlight_linked(23, 29)
        text.highlight_linked(40, 44)
        text.configure(state=tk.DISABLED)


    canvas.grid(row=0, column=1)
    canvas.config(background='white')
    a = linked_text_ignore_entry(canvas
                                 ,get_text_link_callback2
                                 ,text_link_callback
                                 ,text_unlink_callback
                                 ,ignore_text_callback
                                 ,redraw_callback
                                 ,goto_callback
                                 ,placeholder='Name'
                                , x_offset=0,y_offset=0)
    a.debugging = True
    b = linked_text_ignore_entry(canvas
                                 ,get_text_link_callback1
                                 ,text_link_callback
                                 ,text_unlink_callback
                                 ,ignore_text_callback
                                 ,redraw_callback
                                 ,goto_callback
                                 ,placeholder='Name'
                                , x_offset=0,y_offset=0)
    b.debugging = True

    def redraw(event):
        global a
        height = a.draw()
        b.draw(y=height+70)


    canvas.bind('<Configure>', redraw)  # canvas is resized
    
    canvas.update()

    root.mainloop()