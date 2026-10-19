import os
import re
from tkinter import ttk
import tkinter as tk
from tkinterdnd2 import DND_FILES, TkinterDnD




class Tableview(ttk.Treeview):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bind("<Double-1>", lambda event: self.on_double_click(event))

        # Enable drag and drop
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', lambda e: self.on_files_dragged(e.data))

        # Bind motion event to show valid drop targets
        self.bind('<Motion>', self.on_motion)

        # Track current drop target
        self.current_drop_target = None

    def on_drag_enter(self, event):
        """Handle drag enter event to get dragged files."""
        self.current_drag_files = self.extract_paths(event.data)

    def on_motion(self, event):
        """Handle mouse motion to highlight valid drop targets."""
        item = self.identify_row(event.y)
        
        # Remove previous drop target highlight
        if self.current_drop_target:
            tags = list(self.item(self.current_drop_target, 'tags'))
            for tag in ['drop_target', 'invalid_drop']:
                if tag in tags:
                    tags.remove(tag)
            self.item(self.current_drop_target, tags=tags)
        
        # If we have a potential drop target
        if item and 'accepts_drops' in self.item(item, 'tags'):
            self.current_drop_target = item
            tags = list(self.item(item, 'tags'))
            
            # Check if the dragged files are valid for this target
            if self.current_drag_files and self.get_valid_files_for_target(self.current_drag_files, item):
                if 'drop_target' not in tags:
                    tags.append('drop_target')
            else:
                if 'invalid_drop' not in tags:
                    tags.append('invalid_drop')
            
            self.item(item, tags=tags)
        else:
            self.current_drop_target = None


    def extract_paths(self, text):
        """Extract file paths from drag and drop text."""
        paths = []

        # Pattern to match both normal paths and paths in curly braces
        pattern = r'(?:\{([^}]+)\}|(?<!\{)[^\s{]+)'
        for match in re.finditer(pattern, text):
            path = match.group(1) if match.group(1) else match.group(0)
            path = path.strip('"\'')
            paths.append(path)
        return paths


    def on_files_dragged(self, path_text):
        # Pattern to match both normal paths and paths in curly braces
        pattern = r'(?:\{([^}]+)\}|(?<!\{)[^\s{]+)'
        
        # Find all matches and process them
        paths = []
        for match in re.finditer(pattern, path_text):
            # If group(1) exists, it's a path from curly braces, otherwise use group(0)
            path = match.group(1) if match.group(1) else match.group(0)
            paths.append(path)

        print(paths)
        

    def on_drop(self, event):
        """Handle file drop events."""
        target_item = self.identify_row(event.y)
        files = self.extract_paths(event.data)
        
        # Only process drop if target is valid and files match accepted types
        if not target_item or not self.get_valid_files_for_target(files, target_item):
            return
        
        for file_path in files:
            if os.path.exists(file_path):
                file_name = os.path.basename(file_path)
                directory = os.path.dirname(file_path)
      


    def on_double_click(self, event):
        ''' Executed, when a row is double-clicked. Opens 
        read-only EntryPopup above the item's column, so it is possible
        to select text '''

        # close previous popups
        try:  # in case there was no previous popup
            self.entryPopup.destroy()
        except AttributeError:
            pass

        # what row and column was clicked on
        rowid = self.identify_row(event.y)
        column = self.identify_column(event.x)

        # handle exception when header is double click
        if not rowid:
            return

        # get column position info
        x,y,width,height = self.bbox(rowid, column)

        # y-axis offset
        pady = height // 2

        # place Entry popup properly
        text = self.item(rowid, 'values')[int(column[1:])-1]
        self.entryPopup = EntryPopup(self, rowid, int(column[1:])-1, text)
        self.entryPopup.place(x=x, y=y+pady, width=width, height=height, anchor='w')


class EntryPopup(ttk.Entry):
    def __init__(self, parent, iid, column, text, **kw):
        ttk.Style().configure('pad.TEntry', padding='1 1 1 1')
        super().__init__(parent, style='pad.TEntry', **kw)
        self.tv = parent
        self.iid = iid
        self.column = column

        self.insert(0, text) 
        # self['state'] = 'readonly'
        # self['readonlybackground'] = 'white'
        # self['selectbackground'] = '#1BA1E2'
        self['exportselection'] = False

        self.focus_force()
        self.select_all()
        self.bind("<Return>", self.on_return)
        self.bind("<Control-a>", self.select_all)
        self.bind("<Escape>", lambda *ignore: self.destroy())


    def on_return(self, event):
        rowid = self.tv.focus()
        vals = self.tv.item(rowid, 'values')
        vals = list(vals)
        vals[self.column] = self.get()
        self.tv.item(rowid, values=vals)
        self.destroy()


    def select_all(self, *ignore):
        ''' Set selection on the whole text '''
        self.selection_range(0, 'end')

        # returns 'break' to interrupt default key-bindings
        return 'break'
    

if __name__ == "__main__":
    root = TkinterDnD.Tk()

    tree = Tableview(root,padding = ( 0 , 20 , 0 , 0 ),column=("c1", "c2"))
    tree.grid()
    tree.column("# 1", anchor=tk.CENTER)
    tree.heading("# 1", text="ID")
    tree.column("# 2", anchor=tk.CENTER)
    tree.heading("# 2", text="Company")

    # Insert the data in Treeview widget
    tree.insert('', 'end', text="1", values=('1', 'Honda'))
    tree.insert('', 'end', text="2", values=('2', 'Hyundai'))
    tree.insert('', 'end', text="3", values=('3', 'Tesla'))
    tree.insert('', 'end', text="4", values=('4', 'Wolkswagon'))
    tree.insert('', 'end', text="5", values=('5', 'Tata Motors'))
    tree.insert('', 'end', text="6", values=('6', 'Renault'))
    
    
    root.mainloop()