import tkinter as tk
from tkinter import *
from tkinter import font
import re

class GhostTextEntry(Entry):
    def __init__(self, autocompleteList, canvas: tk.Canvas, edit_callback=None, validatecommand=None, id=None, debug=False, placeholder="", *args, **kwargs):
        self.canvas = canvas
        self.disable_ghost = False
        self.disable_listbox = False
        self.edit_callback = edit_callback
        self.__id = id
        self.debug = debug
        self.autocompleteList = autocompleteList
        self.matchesFunction = None
        self.placeholder = placeholder  # Placeholder text to show when empty
        
        # Ghost text variables
        self.current_ghost = ""
        self.ghost_label = None
        self.is_processing = False
        self.ghost_font = None
        self.current_prediction = ""  # Store the full prediction
        self.first_prediction = ""  # First prediction for placeholder use
        self.font = kwargs.get('font', None)
        
        # Listbox variables (like AutocompleteEntry)
        self.listbox = None
        self.listboxUp = False
        
        # Listbox length
        if 'listboxLength' in kwargs:
            self.listboxLength = kwargs['listboxLength']
            del kwargs['listboxLength']
        else:
            self.listboxLength = 8

        # Custom matches function
        if autocompleteList != []:
            if 'matchesFunction' in kwargs:
                self.matchesFunction = kwargs['matchesFunction']
                del kwargs['matchesFunction']
            else:
                def matches(fieldValue, acListEntry):
                    # For listbox: match anywhere in string (like original AutocompleteEntry)
                    pattern = re.compile('.*' + re.escape(fieldValue) + '.*', re.IGNORECASE)
                    return re.match(pattern, acListEntry)
                self.matchesFunction = matches

        if validatecommand:
            Entry.__init__(self, self.canvas, validate='key', validatecommand=validatecommand, *args, **kwargs)
        else:
            Entry.__init__(self, self.canvas, *args, **kwargs)

        self.var = self["textvariable"]
        if self.var == '':
            self.var = self["textvariable"] = StringVar()
        
        # Set up ghost text font (lighter version of entry font)
        try:
            entry_font = self.cget('font')
            if isinstance(entry_font, str):
                # Parse font string
                font_parts = entry_font.split()
                family = font_parts[0] if font_parts else "TkDefaultFont"
                size = int(font_parts[1]) if len(font_parts) > 1 else 10
            else:
                family = "TkDefaultFont"
                size = 10
            self.ghost_font = font.Font(family=family, size=size, slant="italic")
        except:
            self.ghost_font = font.Font(family="TkDefaultFont", size=10, slant="italic")
        
        # Create ghost text label
        self.ghost_label = Label(
            self.canvas, 
            text="", 
            fg="#888888", 
            font=self.ghost_font, 
            bg=self.cget('bg'),
            anchor='w'
        )
        
        # Bind events
        if autocompleteList != []:
            self.var.trace('w', self.changed)
        else:
            self.var.trace('w', self.__edit_callback)
            
        self.bind("<KeyPress>", self.on_key_press)
        self.bind("<Right>", self.key_selection)
        self.bind("<Up>", self.moveUp)
        self.bind("<Down>", self.moveDown)
        self.bind("<FocusOut>", self.on_focus_out)
        self.bind("<FocusIn>", self.on_focus_in)
        self.bind("<Button-1>", self.on_click)
        
        if self.debug:
            print("GhostTextEntry initialized")

    def __edit_callback(self, name, index, mode):
        if self.__id:
            if self.edit_callback:
                self.edit_callback(self.__id, self.var.get())
        else:
            if self.edit_callback:
                self.edit_callback(self.var.get())

    def find_ghost_prediction(self, current_text):
        """Find prediction for ghost text (must start with current text)."""
        if len(current_text) == 0:
            return None
            
        # Find first matching prediction that starts with current text
        for item in self.autocompleteList:
            if item.lower().startswith(current_text.lower()) and len(item) > len(current_text):
                if self.debug:
                    print(f"Found ghost prediction: '{item}' for input: '{current_text}'")
                return item
        
        if self.debug:
            print(f"No ghost prediction found for: '{current_text}'")
        return None

    def comparison(self):
        """Get list of matches for listbox (uses the original matching function)."""
        if self.matchesFunction is None:
            return []
        
        return [w for w in self.autocompleteList if self.matchesFunction(self.var.get(), w)]

    def clear_ghost_text(self):
        """Clear the ghost text display."""
        if self.current_ghost:
            if self.debug:
                print(f"Clearing ghost text: '{self.current_ghost}' or placeholder")
            self.ghost_label.place_forget()
            self.current_ghost = ""
            self.current_prediction = ""

    def set_first_prediction(self, prediction):
        """Set the first prediction (for placeholder use)."""
        self.first_prediction = prediction
        self.show_ghost_prediction(prediction, "")

    def show_first_prediction(self):
        """Show placeholder text when entry is empty."""
        self.show_ghost_prediction(self.first_prediction, "")  # Dummy call to position ghost label
        

    def show_ghost_prediction(self, prediction, current_text):
        """Display ghost text prediction (remaining part of the prediction)."""
        if self.is_processing or self.disable_ghost :
            return
            
        self.is_processing = True
        
        try:
            self.clear_ghost_text()
            
            if prediction and not self.listboxUp:
                # Calculate remaining text to show as ghost
                remaining_text = prediction[len(current_text):]
                
                if remaining_text:
                    if self.debug:
                        print(f"Showing ghost prediction: '{remaining_text}' from '{prediction}' for input: '{current_text}'")
                    
                    # Position ghost text overlay
                    self.update_ghost_position(remaining_text, current_text)
                    self.current_ghost = remaining_text
                    self.current_prediction = prediction
                    
        except Exception as e:
            if self.debug:
                print(f"Error in show_ghost_prediction: {e}")
        finally:
            self.is_processing = False

    def update_ghost_position(self, ghost_text, typed_text):
        """Update the position of the ghost text overlay."""
        try:
            # Get entry position and dimensions
            entry_x = self.winfo_x()
            entry_y = self.winfo_y()
            entry_width = self.winfo_width()
            entry_height = self.winfo_height()
            
            # Calculate text width to position ghost text
            if self.font:
                typed_width = self.font.measure(typed_text)
            else:
                typed_width = len(typed_text) * 8  # Fallback estimation
            
            # Account for entry padding and border
            padding_x = 1
            padding_y = 2
            
            # Position ghost label
            ghost_x = entry_x + padding_x + typed_width
            ghost_y = entry_y + padding_y
            
            self.ghost_label.config(text=ghost_text)
            self.ghost_label.place(x=ghost_x, y=ghost_y, height=entry_height-2)
            
            if self.debug:
                print(f"Ghost text positioned at x={ghost_x}, y={ghost_y}")
                
        except Exception as e:
            if self.debug:
                print(f"Error positioning ghost text: {e}")

    def accept_ghost_text(self):
        """Accept the ghost text and insert it."""
        if self.current_ghost:
            try:
                if self.debug:
                    print(f"Accepting ghost prediction: '{self.current_prediction}'")
                
                # Set the full prediction, not just append ghost text
                self.disable_ghost = True
                self.disable_listbox = True
                self.var.set(self.current_prediction)
                self.icursor(END)
                self.disable_ghost = False
                self.disable_listbox = False
                
                self.clear_ghost_text()
                
                # Close listbox if open
                if self.listboxUp:
                    self.destroy_listbox()
                    self.listboxUp = False
                
                return True
            except Exception as e:
                if self.debug:
                    print(f"Error accepting ghost text: {e}")
                self.disable_ghost = False
                self.disable_listbox = False
                self.clear_ghost_text()
        return False

    def key_selection(self, _=None):
        """Handle listbox selection with Right arrow or Tab."""
        if self.listboxUp:
            self.var.set(self.listbox.get(ACTIVE))
            self.destroy_listbox()
            self.listboxUp = False
            self.icursor(END)
        elif self.current_ghost:
            # If no listbox but ghost text exists, accept ghost text
            if self.accept_ghost_text():
                return "break"

    def destroy_listbox(self):
        """Destroy the listbox."""
        self.canvas.master.unbind("<Return>")
        if self.listbox:
            self.listbox.destroy()
        
    def mouse_selection(self, event):
        """Handle mouse selection in listbox."""
        if not self.listboxUp:
            return 
        
        self.var.set(self.listbox.get(ANCHOR))
        self.destroy_listbox()
        self.listboxUp = False
        self.icursor(END)

    def moveUp(self, event):
        """Move selection up in listbox."""
        if self.listboxUp:
            if self.listbox.curselection() == ():
                index = '0'
            else:
                index = self.listbox.curselection()[0]
            self.listbox.selection_clear(first=index)            
            if str(index) != '0':
                index = str(int(index) - 1)
            else:
                index = str(self.listboxLength - 1)
                
            self.listbox.see(index) # Scroll!
            self.listbox.selection_set(first=index)
            self.listbox.activate(index)

    def moveDown(self, event):
        """Move selection down in listbox."""
        if self.listboxUp:
            if self.listbox.curselection() == ():
                index = '0'
            else:
                index = self.listbox.curselection()[0]
            self.listbox.selection_clear(first=index)
            if index != (self.listboxLength - 1):
                index = str(int(index) + 1)
            else:
                index = '0'
                
            self.listbox.see(index) # Scroll!
            self.listbox.selection_set(first=index)
            self.listbox.activate(index)

    def on_key_press(self, event):
        """Handle key press events."""
        if self.debug:
            print(f"Key press: {event.keysym}")

        
        # Accept ghost text with Tab (if no listbox)
        # If showing placeholder and user types, clear it
        if self.current_ghost and event.char and event.char.isprintable():
            self.clear_ghost_text()

        elif event.keysym in ["Tab", "Right", "Return"] and self.current_ghost and not self.listboxUp:
            if self.accept_ghost_text():
                return "break"  # Prevent default behavior
            
        elif event.keysym in ["Tab", "Right", "Return"] and self.listboxUp:
            self.var.set(self.listbox.get(ACTIVE))
            self.destroy_listbox()
            self.listboxUp = False
            self.icursor(END)
            return "break"
        
        # Clear ghost text on certain keys
        elif event.keysym in ["Left", "Home", "End", "BackSpace", "Delete", "Escape"]:
            self.clear_ghost_text()


    def changed(self, name=None, index=0, mode=None):
        """Handle text changes - show ghost prediction when typing, listbox for alternatives."""
        if self.disable_listbox and self.disable_ghost:
            # Still call edit callback
            if self.__id:
                if self.edit_callback:
                    self.edit_callback(self.__id, self.var.get())
            else:
                if self.edit_callback:
                    self.edit_callback(self.var.get())
            return
            
        current_text = self.var.get()
        
        if self.debug:
            print(f"Text changed to: '{current_text}'")
        
        if current_text == '':
            # Clear both ghost and listbox, show placeholder
            self.clear_ghost_text()
            if self.listboxUp:
                self.destroy_listbox()
                self.listboxUp = False
            
            # Show placeholder when empty
            if not self.disable_ghost:
                self.after(5, self.show_first_prediction)
        else:
            pass
            
            
            
            # Second priority: Show listbox for broader matches (only if no ghost or user wants alternatives)
            if not self.disable_listbox:
                words = self.comparison()
                if words and len(words) > 1:  # Show listbox only if multiple matches
                    if not self.listboxUp:
                        listbox_font = font.Font(family="arial.ttf", size=13, weight="normal")
                        m_len = listbox_font.measure("n")
                        width = int(self.winfo_width()/m_len)
                        self.listbox = Listbox(master=self.canvas, width=width, height=self.listboxLength, relief='flat',
                                        font=listbox_font, background='#F0F0F0', selectbackground="#D3D3D3",
                                        selectforeground="black")
                        self.listbox.bind("<<ListboxSelect>>", self.mouse_selection)
                        self.listbox.bind("<Right>", self.key_selection)
                        self.listbox.bind("<Tab>", self.key_selection)
                        self.canvas.master.bind("<Return>", self.key_selection)
                        self.listbox.place(x=self.winfo_x(), y=self.winfo_y() + 24)
                        self.listboxUp = True
                        
                    self.listbox.delete(0, END)
                    for w in words:
                        self.listbox.insert(END, w)
                    index = '0'
                    self.listbox.see(index)
                    self.listbox.selection_set(first=index)
                    self.listbox.activate(index)
                else:
                    if self.listboxUp:
                        self.destroy_listbox()
                        self.listboxUp = False

            # Show ghost prediction for direct matches
            if not self.disable_ghost:
                ghost_prediction = self.find_ghost_prediction(current_text)
                if ghost_prediction:
                    self.show_ghost_prediction(ghost_prediction, current_text)
                else:
                    pass
        
        # Call edit callback
        if self.__id:
            if self.edit_callback:
                self.edit_callback(self.__id, self.var.get())
        else:
            if self.edit_callback:
                self.edit_callback(self.var.get())

    def on_focus_out(self, event):
        """Handle focus out events."""
        # Keep placeholder visible when losing focus if entry is empty
        pass

    def on_focus_in(self, event):
        """Handle focus in events."""
        # Show placeholder if entry is empty
        if self.var.get() == '' and self.placeholder:
            self.show_first_prediction()

    def on_click(self, event):
        """Handle mouse clicks."""
        pass

    def update_autocomplete_list(self, autocompleteList, change_instant=False):
        """Update the autocomplete list."""
        self.autocompleteList = autocompleteList
        
        if change_instant:
            self.changed()

    def set_placeholder(self, placeholder_text):
        """Set or update the placeholder text."""
        self.placeholder = placeholder_text
        if self.var.get() == '':
            self.show_first_prediction()

    def destroy(self):
        """Clean up when destroying the widget."""
        self.clear_ghost_text()
        if self.ghost_label:
            self.ghost_label.destroy()
        if self.listbox:
            self.listbox.destroy()
        super().destroy()

class custom_ghost_entry:
    def __init__(self, canvas, x_offset, y_offset,enable_line=True,enbale_rect=True,state=NORMAL, width=None, autocompleteList=[], placeholder="", percentage_length=1, height=18, size=11,
                    focus_out_callback=None, edit_callback=None, placeholder_spacing=0,validatecommand=None,id=None, bottom_error=False):
        self.canvas = canvas
        self.__id = id 
        self.x = 0
        self.y = 0
        self.x_offset = x_offset
        self.width = width
        self.y_offset = y_offset
        self.enable_line = enable_line
        self.enbale_rect = enbale_rect
        self.focused = False
        self.name = placeholder
        self.placeholder = placeholder
        self.placeholder_color = '#505050'
        self.placeholder_spacing = placeholder_spacing
        self.size = size
        self.focus_out_callback = focus_out_callback
        self.height = height
        self.percentage_length = percentage_length
        self.autocompleteList = autocompleteList
        self.error_found = False
        self.error_color = "#B91F3B"
        self.font = font.Font(family="arial.ttf",size=size,weight="normal")
        self.entry = GhostTextEntry(autocompleteList, self.canvas
                        ,id=self.__id
                        ,borderwidth=0
                        ,background='white'
                        ,foreground='#6F6F6F',
                        font=self.font,edit_callback=edit_callback,
                        listboxLength=5,insertwidth=1,state=state,validatecommand=validatecommand)
        self.entry_window = None 
        self.rect = None
        self.line = None 
        self.placeholder_text = None 
        self.error_text = None 
        self.error_message = ''
        self.show_as_warning = False
        self.bottom_error = bottom_error
        
        self.entry.bind("<FocusIn>", self.entry_callbackIn)
        self.entry.bind("<FocusOut>", self.entry_callbackOut)
        self.entry.bind("<Enter>", self.on_enter)
        self.entry.bind("<Leave>", self.on_leave)
        self.entry.bind("<Return>", self.remove_focus)

    
        self.menu = tk.Menu(self.canvas, tearoff=0)
        self.menu.add_command(label="Cut")
        self.menu.add_command(label="Copy")
        self.menu.add_command(label="Paste")
        self.menu.add_separator()
        self.menu.add_command(label="Select all")

        self.entry.bind("<Button-3><ButtonRelease-3>", self.show_textmenu)
        self.entry.bind("<Control-a>", self.callback_select_all)
        self.entry.bind('<Control-c>', self.copy)
        self.entry.bind('<Control-x>', self.cut)
        self.entry.bind('<Control-v>', self.paste)


    def get(self):
        return self.entry.get()
    

    def set_text(self, text):
        self.entry.disable_listbox = True
        self.entry.delete(0,tk.END)
        self.entry.insert(0,text)
        self.entry.disable_listbox = False

    
    def disable(self):
        self.entry.config(state=DISABLED)

    def enable(self):
        self.entry.config(state=NORMAL)
    

    def copy(self, event=None):
        self.entry.clipboard_clear()
        text = self.entry.get("sel.first", "sel.last")
        self.entry.clipboard_append(text)

    def cut(self, event):
        self.entry.copy()
        self.entry.delete("sel.first", "sel.last")

    def paste(self, event):
        text = self.entry.selection_get(selection='CLIPBOARD')
        #self.entry.insert('insert', text)


    def callback_select_all(self, event):
        # select text after 50ms
        root.after(50, lambda:event.widget.select_range(0, 'end'))

    def show_textmenu(self, event):
        e_widget = event.widget
        self.menu.entryconfigure("Cut",command=lambda: e_widget.event_generate("<<Cut>>"))
        self.menu.entryconfigure("Copy",command=lambda: e_widget.event_generate("<<Copy>>"))
        self.menu.entryconfigure("Paste",command=lambda: e_widget.event_generate("<<Paste>>"))
        self.menu.entryconfigure("Select all",command=lambda: e_widget.select_range(0, 'end'))
        self.menu.tk.call("tk_popup", self.menu, event.x_root, event.y_root)

                                
    def draw(self,x=0, y=0, max_x=None):
        self.__delete_static_elements()
        self.x = self.x_offset + x
        self.y = self.y_offset + y

        if max_x:
            self.canvas.itemconfig(self.entry_window, width=max_x)

        else:
            max_x = self.canvas.winfo_width()*self.percentage_length
            self.canvas.itemconfig(self.entry_window, width=max_x - 32)


        line_max_x = 0
        if self.width:
            max_x = self.x + self.width
            m_len = self.font.measure("n")
            width = int((self.width)/m_len)
            self.entry.config(width=width)
            self.canvas.itemconfig(self.entry_window, width=width)
            line_max_x = max_x + 16
        
        else:
            m_len = self.font.measure("n")
            width = int((max_x - 32)/m_len)
            self.entry.config(width=width)
            line_max_x = max_x - 8
            
        
        
        self.entry_window = self.canvas.create_window(self.x + 16,self.y + 18 + self.placeholder_spacing  ,window=self.entry,anchor=NW)
        if self.enbale_rect: #rect used to hide previous elements in expandable list 
            self.rect = self.canvas.create_rectangle( + 8 ,self.y + 1 ,max_x,
                                self.y + self.height + self.size + 14 + self.placeholder_spacing , fill="white",width=0)
        self.line = self.canvas.create_line(self.x + 16 ,self.y + self.height + self.size + 11  + self.placeholder_spacing,line_max_x,
                                self.y + self.height + self.size + 11  + self.placeholder_spacing, fill="#E5E5E5",width=1)
        self.placeholder_text = self.canvas.create_text(self.x + 16, self.y + 2, fill = '#505050', text=self.placeholder,
                                anchor=tk.NW, font=font.Font(family="arial.ttf",size=11,weight="bold"))
        error_text_y = 18 + self.placeholder_spacing + 24 if self.bottom_error else 2
        self.error_text = self.canvas.create_text(line_max_x , self.y + error_text_y, fill = 'white', text='',
                                anchor=tk.NE, font=font.Font(family="arial.ttf",size=9,weight="normal"))
        self.default_fg_color = self.entry['fg']
        self.entry.changed()
        
        if self.error_found:
            self.error()
        
    def hide(self):
        self.__delete_static_elements()


    def __delete_static_elements(self):
        if self.placeholder_text:
            self.canvas.delete(self.entry_window)
            self.canvas.delete(self.rect)
            self.canvas.delete(self.line)
            self.canvas.delete(self.placeholder_text) 
            self.canvas.delete(self.error_text)
        
                
    def entry_callbackIn(self,_):   
        if self.enable_line:
            self.canvas.itemconfig(self.line, fill="#00AEEF",width=2)
        self.focused = True
        
        
    def entry_callbackOut(self,_):   
        if self.error_found:
            self.canvas.itemconfig(self.line, fill=self.error_color,width=1)
        else:
            self.canvas.itemconfig(self.line, fill="#D5D5D5",width=1)
        self.focused = False
        
        self.entry.key_selection()
        if self.__id:
          if self.focus_out_callback:
            self.focus_out_callback(self.__id)  
        else:
            if self.focus_out_callback:
                self.focus_out_callback()


    def update_autocomplete_list(self, autocompleteList,change_instant=False):
        self.autocompleteList = autocompleteList
        self.entry.update_autocomplete_list(autocompleteList,change_instant)
        
        
    def on_enter(self,event): 
        pass  
        
    def on_leave(self,event):   
        pass

    def remove_focus(self,event):
        self.canvas.focus_set()
        
    def error(self,error_message=None, show_as_warning=None):
        if error_message is None:
            error_message = self.error_message
        if show_as_warning is None:
            show_as_warning = self.show_as_warning
        self.error_color = '#ed9401' if show_as_warning else '#B91F3B'
        self.canvas.itemconfig(self.line, fill=self.error_color)
        self.canvas.itemconfig(self.placeholder_text, fill=self.error_color)
        self.canvas.itemconfig(self.error_text, fill=self.error_color)
        self.canvas.itemconfig(self.error_text, text=error_message)
        self.error_message = error_message
        self.show_as_warning = show_as_warning
        self.error_found = True
        
    def reset_error(self):
        if not self.error_found:
            return 

        self.error_found = False
        
        self.canvas.itemconfig(self.error_text, fill='white')
        self.canvas.itemconfig(self.error_text, text='')

        if self.focused:
            self.canvas.itemconfig(self.line, fill="#00AEEF")
            if self.entry['fg'] == self.placeholder_color:
                self.entry.delete('0', 'end')
                self.entry['fg'] = self.default_fg_color
            self.canvas.itemconfig(self.placeholder_text, fill='#505050')
        else:
            self.canvas.itemconfig(self.line, fill="#D5D5D5")
            if not self.entry.get():
                self.put_placeholder()
            else:
                self.canvas.itemconfig(self.placeholder_text, fill='#505050')




# Demo/Test application
if __name__ == "__main__":

    root = tk.Tk()
    canvas1 = tk.Canvas(root)
    canvas1.grid(row=0, column=1)
    canvas1.config(background='white')
    autocompleteList = [ 'Dora Lyons (7714)', 'Hannah Golden (6010)', 'Walker Burns (9390)', 'Dieter Pearson (6347)', 'Allen Sullivan (9781)', 'Warren Sullivan (3094)', 'Genevieve Mayo (8427)', 'Igor Conner (4740)', 'Ulysses Shepherd (8116)', 'Imogene Bullock (6736)', 'Dominique Sanchez (949)', 'Sean Robinson (3784)', 'Diana Greer (2385)', 'Arsenio Conrad (2891)', 'Sophia Rowland (5713)', 'Garrett Lindsay (5760)', 'Lacy Henry (4350)', 'Tanek Conley (9054)', 'Octavia Michael (5040)', 'Kimberly Chan (1989)', 'Melodie Wooten (7753)', 'Winter Beard (3896)', 'Callum Schultz (7762)', 'Prescott Silva (3736)', 'Adena Crane (6684)', 'Ocean Schroeder (2354)', 'Aspen Blevins (8588)', 'Allegra Gould (7323)', 'Penelope Aguirre (7639)', 'Deanna Norman (1963)', 'Herman Mcintosh (1776)', 'August Hansen (547)', 'Oscar Sanford (2333)', 'Guy Vincent (1656)', 'Indigo Frye (3236)', 'Angelica Vargas (1697)', 'Bevis Blair (4354)', 'Trevor Wilkinson (7067)', 'Kameko Lloyd (2660)', 'Giselle Gaines (9103)', 'Phyllis Bowers (6661)', 'Patrick Rowe (2615)', 'Cheyenne Manning (1743)', 'Jolie Carney (6741)', 'Joel Faulkner (6224)', 'Anika Bennett (9298)', 'Clayton Cherry (3687)', 'Shellie Stevenson (6100)', 'Marah Odonnell (3115)', 'Quintessa Wallace (5241)', 'Jayme Ramsey (8337)', 'Kyle Collier (8284)', 'Jameson Doyle (9258)', 'Rigel Blake (2124)', 'Joan Smith (3633)', 'Autumn Osborne (5180)', 'Renee Randolph (3100)', 'Fallon England (6976)', 'Fallon Jefferson (6807)', 'Kevyn Koch (9429)', 'Paki Mckay (504)', 'Connor Pitts (1966)', 'Rebecca Coffey (4975)', 'Jordan Morrow (1772)', 'Teegan Snider (5808)', 'Tatyana Cunningham (7691)', 'Owen Holloway (6814)', 'Desiree Delaney (272)', 'Armand Snider (8511)', 'Wallace Molina (4302)', 'Amela Walker (1637)', 'Denton Tillman (201)', 'Bruno Acevedo (7684)', 'Slade Hebert (5945)', 'Elmo Watkins (9282)', 'Oleg Copeland (8013)', 'Vladimir Taylor (3846)', 'Sierra Coffey (7052)', 'Holmes Scott (8907)', 'Evelyn Charles (8528)', 'Steel Cooke (5173)', 'Roth Barrett (7977)', 'Justina Slater (3865)', 'Mara Andrews (3113)', 'Ulla Skinner (9342)', 'Reece Lawrence (6074)', 'Violet Clay (6516)', 'Ainsley Mcintyre (6610)', 'Chanda Pugh (9853)', 'Brody Rosales (2662)', 'Serena Rivas (7156)', 'Henry Lang (4439)', 'Clark Olson (636)', 'Tashya Cotton (5795)', 'Kim Matthews (2774)', 'Leilani Good (5360)', 'Deirdre Lindsey (5829)', 'Macy Fields (268)', 'Daniel Parrish (1166)', 'Talon Winters (8469)' ]
    
    c = custom_ghost_entry(canvas1, 0,0,autocompleteList=autocompleteList,placeholder='Name')
    c.entry.show_thinking()
    #c.entry.set_first_prediction("Type a name...")


    def redraw(event):
        global c
        print ('doing')
        c.draw(0)
        c.error('Error')
    
    canvas1.bind('<Configure>', redraw)  # canvas is resized
    canvas1.update()
    root.mainloop()
    
    '''

    def test_callback(value):
        print(f"Text changed: {value}")

    root = tk.Tk()
    root.title("Ghost Text Entry with Real Predictions Demo")
    root.geometry("800x500")
    root.configure(background='white')

    # Create a canvas like in the AutocompleteEntry example
    canvas = tk.Canvas(root, bg='white')
    canvas.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    # Sample autocomplete list
    autocompleteList = [
        'Hello world', 'Hello there', 'How are you', 'How to', 'Python programming',
        'Tkinter widget', 'Text prediction', 'Machine learning', 'Data science',
        'Artificial intelligence', 'Programming language', 'Software development',
        'I am working on', 'This is a test of', 'Multiple word prediction',
        'The quick brown fox jumps over', 'Python is a great programming language',
        'Apple', 'Application', 'Apply', 'Appreciate', 'Approach'
    ]

    # Instructions
    instructions = tk.Label(
        canvas, 
        text="Features:\n• Shows placeholder when empty\n• Type to see gray ghost text prediction (e.g., 'Hel' shows 'lo world')\n• Tab accepts ghost prediction\n• Dropdown shows multiple matches\n• Arrow keys navigate dropdown",
        font=("TkDefaultFont", 10),
        bg='white',
        justify=tk.LEFT
    )
    canvas.create_window(400, 80, window=instructions)

    # Create the ghost text entry with real predictions
    ghost_entry = GhostTextEntry(
        autocompleteList, 
        canvas, 
        edit_callback=test_callback,
        debug=True,
        font=("TkDefaultFont", 12),
        width=50,
        placeholder="Start typing for predictions..."
    )
    canvas.create_window(400, 180, window=ghost_entry)
    ghost_entry.set_first_prediction("Type something...")

    # Sample with custom matches function for listbox
    def custom_matches(fieldValue, acListEntry):
        """Custom matching function that matches anywhere in the string."""
        if len(fieldValue) < 2:
            return False
        return fieldValue.lower() in acListEntry.lower()

    ghost_entry2 = GhostTextEntry(
        autocompleteList,
        canvas,
        matchesFunction=custom_matches,
        debug=True,
        font=("TkDefaultFont", 12),
        width=50,
        placeholder="Custom search (matches anywhere)..."
    )
    canvas.create_window(400, 250, window=ghost_entry2)

    # Label for second entry
    label2 = tk.Label(canvas, text="Custom matching (matches anywhere in dropdown):", bg='white')
    canvas.create_window(400, 230, window=label2)

    # Buttons
    def clear_entries():
        ghost_entry.delete(0, tk.END)
        ghost_entry2.delete(0, tk.END)
        # Trigger placeholder display
        ghost_entry.changed()
        ghost_entry2.changed()

    def update_predictions():
        new_list = ['JavaScript', 'Java programming', 'JSON data', 'jQuery library', 'Just testing']
        ghost_entry.update_autocomplete_list(new_list, change_instant=True)
        ghost_entry2.update_autocomplete_list(new_list, change_instant=True)
        print("Updated predictions!")

    def update_placeholder():
        ghost_entry.set_placeholder("New placeholder text...")
        ghost_entry2.set_placeholder("Another new placeholder...")

    clear_btn = tk.Button(canvas, text="Clear", command=clear_entries)
    canvas.create_window(250, 320, window=clear_btn)

    update_btn = tk.Button(canvas, text="Update Predictions", command=update_predictions)
    canvas.create_window(400, 320, window=update_btn)

    placeholder_btn = tk.Button(canvas, text="Update Placeholder", command=update_placeholder)
    canvas.create_window(550, 320, window=placeholder_btn)

    print("Starting Ghost Text Entry with Real Predictions Demo - check console for debug output")
    print("Try typing 'Hel', 'Py', 'Mac', 'App' to see ghost predictions!")
    root.mainloop()'''