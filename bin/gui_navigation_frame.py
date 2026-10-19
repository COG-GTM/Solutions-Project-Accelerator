from math import inf
import shutil
from bin.gui_textbox_progressbar_window import texbox_progressbar_window
from bin.logic_profile import profile
from bin.logic_logger import logging
from threading import Thread
from queue import Queue
import os
import sys
import re

import xlrd
import numpy
import pandas as pd
from pypdf import PdfReader
from bin.logic_internal_database import Database
from bin.logic_file_manager import Project_File_Manager
from bin.logic_tools import export_excel_with_data, export_pdf_with_data, export_text_excel_with_data, export_text_pdf_with_data
from bin.logic_validators import Validators
from bin.logic_logger import handle_exception, handle_exception_with_messagebox
import tkinter as tk 
from tkinterdnd2 import DND_FILES
from tkinter import messagebox  
from datetime import datetime, timezone 
from tkinter.filedialog import askopenfilename, askopenfilenames, asksaveasfilename
from PIL import ImageTk, Image, ImageDraw           
from tkinter import font  as tkfont


from bin.logic_border_detection_cropper import detect_and_crop_border, create_pdf_from_cropped_pages
from bin.logic_pdf_render import page_count as pdf_page_count, page_size, render_page



try:
    from .gui_elements import *
    from .gui_base64_icons import *
except ImportError as error:
    from gui_elements import *
    from gui_base64_icons import *


def pdf_outline(path):
    """Flatten a PDF's bookmarks into [level, title, 1-based page] rows."""
    reader = PdfReader(path)
    toc = []

    def walk(items, level):
        for item in items:
            if isinstance(item, list):
                walk(item, level + 1)
                continue
            try:
                page = reader.get_destination_page_number(item) + 1
            except Exception:
                page = -1
            toc.append([level, item.title, page])

    walk(reader.outline, 1)
    return toc


class navigation_frame(tk.Frame):

    def __init__(self,master,config, **kwargs):
        tk.Frame.__init__(self,master, **kwargs)

        self.title_font = tkfont.Font(family='Helvetica', size=18, weight="bold", slant="italic")
        
        # the container is where we'll stack a bunch of frames
        # on top of each other, then the one we want visible
        # will be raised above the others
        self.pack(side="top", fill="both", expand=True)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.__config = config
        self.__close_document_func = None
        self.__project_name = None
        self.__iid = None
        self.type = None

        self.__parent_iid = None

        self.frames = {}
        for F in (project_folder_page, page_navigation_page, bookmark_navigation_page):
            page_name = F.__name__
            frame = F(parent=self, controller=self, config=self.__config)
            self.frames[page_name] = frame

            # put all of the pages in the same location;
            # the one on the top of the stacking order
            # will be the one that is visible.
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("project_folder_page")

    def show_frame(self, page_name):
        '''Show a frame for the given page name'''
        frame = self.frames[page_name]
        frame.tkraise()
        frame.show()
        

    def define_project(self, project_name, db, acm_data_handler):
        for _ ,frame in self.frames.items():
            frame.set_project(project_name, db, acm_data_handler)
        


    def set_opened_document_func(self, callback):
        self.frames[project_folder_page.__name__].set_opened_document_func(callback)


    def set_page_selected_callback(self, callback):
        self.frames[page_navigation_page.__name__].set_page_selected_callback(callback)
        self.frames[bookmark_navigation_page.__name__].set_page_selected_callback(callback)
    
 
    def open_doc(self, path,type):
        self.type = type
        self.doc = None
        if self.type in [Database.DRAWING, Database.IMAGE]:
            if self.type == Database.DRAWING:
                self.doc = path
            if self.type == Database.IMAGE:
                self.doc = Project_File_Manager.get_drawing_image_files(path)
            self.frames[page_navigation_page.__name__].open_doc(self.doc, type)

        if self.type == Database.TABLE :
            self.doc = pd.ExcelFile(path)

        if self.type != Database.IMAGE:
            self.frames[bookmark_navigation_page.__name__].open_doc(self.doc,type)


    def set_close_doc_func(self, func):
        self.__close_document_func = func 
        self.frames[project_folder_page.__name__].set_close_doc_func(self.__close_document)


    def __close_document(self):
        self.__close_document_func()
        self.doc = None
        self.frames[page_navigation_page.__name__].close_doc()
        self.frames[bookmark_navigation_page.__name__].close_doc()



    def set_page(self, page):
        self.frames[page_navigation_page.__name__].canvas.highlight_page(page)
        


    def document_selected_func(self, func):
        self.frames[project_folder_page.__name__].document_selected_func(func)

    def sheet_selected_func(self, func):
        self.frames[project_folder_page.__name__].sheet_selected_func(func)
            


class project_folder_page(tk.Frame):
    
    LEVEL_1_IDS = []
    LEVEL_2_IDS = []
    LEVEL_3_IDS = []

    PROJECT_TREE_INDEX = ''
    DRAWING_TREE_INDEX = ''
    TEXTS_TREE_INDEX = ''
    TABLES_TREE_INDEX = ''

    FOLDERS_AND_FILES_COL = "#0"


    def __init__(self, parent, controller, config=None):
        tk.Frame.__init__(self, parent)
        self.parent = parent
        self.__config = config
        self.__project_name = None
        self.__document_selected_func = None
        self.__opened_document_func = None 
        self.__close_document_func = None
        self.__db : Database = None
        self.__acm_data_handler = None
        self.__iid = None
        self.__import_image_menu_label = 'Import as Images'
        self.__export_with_data_menu_label = 'Export With Data'
        self.__export_original_menu_label = 'Export Original'
        self.__export_excel_menu_label = 'Export data in Excel'
        
        # Border checking thread variables
        self.border_check_thread = None
        self.border_check_result = None
        self.border_check_queue = Queue()
        self.tree_view: tree_view = tree_view(self)

        # Enable drag and drop
        self.tree_view.drop_target_register(DND_FILES)
        self.tree_view.dnd_bind('<<Drop>>', self.on_files_dragged)

        # Bind motion event to show valid drop targets
        self.tree_view.dnd_bind('<<DropPosition>>', self.on_motion)
        self.tree_view.dnd_bind('<<DropEnter>>', self.on_drag_enter)
        
        # Pattern for extracting paths
        self.path_pattern = r'(?:\{([^}]+)\}|(?<!\{)[^\s{]+)'
        
        # Track current drop target and dragged files
        self.current_drop_target = None
        self.current_drag_files = []

        self.tree_view.pack(side="top", fill="both", pady=0, expand=True)
        self.tree_view['columns'] = ('one')
        self.tree_view.heading(self.FOLDERS_AND_FILES_COL,text="",anchor=tk.W)
        self.tree_view.heading("one", text="Added",anchor=tk.W)

    def show(self):
        pass
    
    def __check_pdf_border_consistency_thread(self, pdf_path):
        """Thread function to check border consistency of a PDF."""
        
        
        try:
            detection_zoom = 2.0
            
            borders = []
            page_count = pdf_page_count(pdf_path)

            width = inf
            height = inf
            
            # Detect borders for all pages
            for page_num in range(page_count):
                # Render page for border detection
                img_detect = render_page(pdf_path, page_num, zoom=detection_zoom)
                
                _, border_bbox = detect_and_crop_border(img_detect, debug=False)
                
                if border_bbox:
                    _, _, w, h = border_bbox
                    if w < width:
                        width = w
                    if h < height:
                        height = h
                
                borders.append(border_bbox)
            
            # Analyze consistency
            pages_with_borders = [i for i, b in enumerate(borders) if b is not None]
            
            if len(pages_with_borders) < 2:
                self.border_check_queue.put({'consistent': True, 'pages': page_count})
                return
            
            # Compare all borders against the first one
            tolerance = 10
            reference = borders[pages_with_borders[0]]
            consistent = True
            
            for i in pages_with_borders[1:]:
                border = borders[i]
                if (abs(border[0] - reference[0]) > tolerance or
                    abs(border[1] - reference[1]) > tolerance or
                    abs(border[2] - reference[2]) > tolerance or
                    abs(border[3] - reference[3]) > tolerance):
                    consistent = False
                    break
            
            self.border_check_queue.put({
                'consistent': consistent,
                'pages': page_count,
                'pages_with_borders': len(pages_with_borders),
                'pdf_path': pdf_path,
                'largest_width': width,
                'largest_height': height
            })
            
        except Exception as e:
            logging.error(f"Error checking border consistency: {e}")
            self.border_check_queue.put({'error': str(e)})
    
    def __start_border_consistency_check(self, pdf_path):
        """Start a threaded border consistency check."""
        if self.border_check_thread and self.border_check_thread.is_alive():
            return  # Already checking
        
        self.border_check_thread = Thread(target=self.__check_pdf_border_consistency_thread, args=(pdf_path,))
        self.border_check_thread.daemon = True
        self.border_check_thread.start()
        
        # Start checking for results
        self.after(100, self.__check_border_consistency_result)
    
    def __check_border_consistency_result(self):
        """Check if border consistency check is complete and show dialog."""
        try:
            result = self.border_check_queue.get_nowait()
            
            if 'error' in result:
                logging.warning(f"Border check error: {result['error']}")
                return
            
            if not result.get('consistent', True):
                # Borders are different - ask user
                pages = result.get('pages', 0)
                pages_with_borders = result.get('pages_with_borders', 0)
                pdf_path = result.get('pdf_path', '')
                width = result.get('largest_width', 0)
                height = result.get('largest_height', 0)
                
                response = messagebox.askyesno(
                    "Different Borders Detected",
                    f"The combined PDF has {pages} pages with inconsistent borders detected on {pages_with_borders} pages.\n\n"
                    f"Would you like to standardize all pages to use consistent borders?\n\n"
                    f"This improves scanning accuracy.\n\n",
                    icon='question'
                )
                
                if response:
                    if self.__opened_document_func() == pdf_path:
                        self.__close_document_func()
                    self.__standardize_pdf_borders(pdf_path, (width, height))
            
        except Exception:
            # Queue is empty, check again
            if self.border_check_thread and self.border_check_thread.is_alive():
                self.after(100, self.__check_border_consistency_result)
    
    def __standardize_pdf_borders(self, pdf_path, target_dimensions):
        """Standardize borders in the PDF"""
        try:
            # This would call your border cropping function
            create_pdf_from_cropped_pages(pdf_path, pdf_path, target_dimensions)
            logging.info(f"Standardizing borders for: {pdf_path}")
        except Exception as e:
            logging.error(f"Error standardizing borders: {e}")
            messagebox.showerror("Error", f"Failed to standardize borders: {str(e)}")
       
    def get_valid_files_for_target(self, files, target):
        """Check if files match the target's accepted types."""
        if not target:
            return False
        
        if target == self.DRAWING_TREE_INDEX:
            valid_extensions = {'.png', '.jpg', '.jpeg', '.pdf'}
            return all(any(f.lower().endswith(ext) for ext in valid_extensions) for f in files)
        elif target == self.TEXTS_TREE_INDEX:
            valid_extensions = {'.pdf'}
            return all(any(f.lower().endswith(ext) for ext in valid_extensions) for f in files)
        elif target == self.TABLES_TREE_INDEX:
            valid_extensions = {'.xlsx','.xlsm'}
            return all(any(f.lower().endswith(ext) for ext in valid_extensions) for f in files)
        elif self.__has_file_extension(target, files):
            return True
        return
    

    def __has_file_extension(self, item, files):
        """Check if all of the files have the same extension as the item. 
        For images, any image extension is valid."""
        values = self.tree_view.item(item,"values")
        _, extension = os.path.splitext(values[2])
        if extension.lower() in ['.jpg', '.jpeg', '.png']:
            return all(f.lower().endswith(('.jpg', '.jpeg', '.png')) for f in files)
        return all(f.lower().endswith(extension) for f in files)

    
    
    def on_drag_enter(self, event):
        """Handle drag enter event to get dragged files."""
        self.current_drag_files = self.extract_paths(event.data)


    def extract_paths(self, text):
        """Extract file paths from drag and drop text."""
        paths = []
        for match in re.finditer(self.path_pattern, text):
            path = match.group(1) if match.group(1) else match.group(0)
            path = path.strip('"\'')
            paths.append(path)
        return paths
    

    def on_motion(self, _):
        """Handle mouse motion to highlight valid drop targets."""
        # Get the item under the cursor
        y = self.tree_view.winfo_pointery() - self.tree_view.winfo_rooty()
        item = self.tree_view.identify_row(y)
        
        # If we have a potential drop target
        if item != self.PROJECT_TREE_INDEX:
            self.current_drop_target = item
            
            # Check if the dragged files are valid for this target
            if self.current_drag_files and self.get_valid_files_for_target(self.current_drag_files, item):
                self.tree_view.selection_set(item)
            else:
                self.tree_view.selection_set('')
        else:
            self.current_drop_target = None
        

    def on_files_dragged(self, event):
        """Handle file drop events."""
         
        # target_item = self.tree.identify_row(event.y)
        files = self.extract_paths(event.data)

        # Get the item under the cursor
        y = self.tree_view.winfo_pointery() - self.tree_view.winfo_rooty()
        target_item = self.tree_view.identify_row(y)

        # Only process drop if target is valid and files match accepted types
        if not target_item or not self.get_valid_files_for_target(files, target_item):
            return
        
        if target_item == self.DRAWING_TREE_INDEX:

            if os.path.splitext(files[0])[1].lower() in ['.png', '.jpg', '.jpeg']:
                type = self.__db.IMAGE
            else:
                type = self.__db.DRAWING

            if len(files) == 1:
                
                destination = Project_File_Manager.import_drawing_file(files[0], self.__project_name)
                self.__db.insert_project_document(os.path.basename(files[0]),destination,type)
            else:
                destination, filename = Project_File_Manager.combine_drawing_files(files, self.__project_name)
                self.__db.insert_project_document(filename,destination,type)
                
                # Start threaded check if borders are consistent
                self.__start_border_consistency_check(destination + '/' + filename)

            self.__setup_level_3()
            return

        if target_item in self.LEVEL_3_IDS and self.__has_file_extension(target_item, files):
            type = self.__db.DRAWING
            values = self.tree_view.item(target_item,"values")
            path = values[1] +'/'+ values[2]
            if type in values:
                if self.__opened_document_func() == path:
                    self.__close_document_func()
                destination = Project_File_Manager.combine_with_existing_drawing(path, files)
                
                # Start threaded check if borders are consistent
                self.__start_border_consistency_check(destination + '/' + filename)
                
                self.__setup_level_3()
                return
                

        if target_item == self.TEXTS_TREE_INDEX:
            type = self.__db.TEXT
            for file in files:
                destination = Project_File_Manager.import_text_document_file(file, self.__project_name)
                self.__db.insert_project_document(os.path.basename(file),destination,type)
            self.__setup_level_3()
            return

        if target_item == self.TABLES_TREE_INDEX:
            type = self.__db.TABLE
            for file in files:
                destination = Project_File_Manager.import_Sheets_file(file, self.__project_name)
                self.__db.insert_project_document(os.path.basename(file),destination,type)
            self.__setup_level_3()
            return



    def set_project(self, project_name, db, acm_data_handler=None):
        self.__db = db
        self.__acm_data_handler = acm_data_handler
        self.__project_name = project_name
        self.tree_view.delete(*self.tree_view.get_children())
        self.__setup_level_1()
        self.__setup_level_2()
        self.__setup_level_3()
        self.__pass_show_popup_func()
        self.__pass_double_click_func()
        self.__setup_menus()
        

    def __setup_menus(self):
        self.__setup_level_1_menu()
        self.__setup_level_2_menu()
        self.__setup_level_3_menu()

    def __setup_level_1(self):
        id = self.tree_view.insert_with_icon('', 'end', project_folder, text=self.__project_name, open=True)
        self.LEVEL_1_IDS.append(id)
        self.PROJECT_TREE_INDEX = id
        self.tree_view.after_idle(self.tree_view.selection_set,self.PROJECT_TREE_INDEX )
        


    def __setup_level_2(self):
        id = self.tree_view.insert_with_icon(self.PROJECT_TREE_INDEX, 'end', visual_references_folder, text='Visuals')
        self.LEVEL_2_IDS.append(id)
        self.DRAWING_TREE_INDEX = id
        id = self.tree_view.insert_with_icon(self.PROJECT_TREE_INDEX, 'end', text_references_folder, text='Text')
        self.LEVEL_2_IDS.append(id)
        self.TEXTS_TREE_INDEX = id
        id = self.tree_view.insert_with_icon(self.PROJECT_TREE_INDEX, 'end', table_references_folder, text='Sheets')
        self.LEVEL_2_IDS.append(id)
        self.TABLES_TREE_INDEX = id


    def __setup_level_3(self):
        self.LEVEL_3_IDS.clear()
        drawings = self.__db.get_project_drawings()
        for item in self.tree_view.get_children(item=self.DRAWING_TREE_INDEX):
            self.tree_view.delete(item)

        for drawing in drawings:
            type = self.__db.DRAWING
            ts = int(int(drawing['timestamp'])/1000)
            date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%m/%d/%Y %H:%M')
            path = drawing['path']
            id = self.tree_view.insert_with_icon(self.DRAWING_TREE_INDEX, 'end', drawing_reference_file, text=drawing['name'], values=(date,path,drawing['name'],type), open=False)
            self.LEVEL_3_IDS.append(id)

        image_drawings = self.__db.get_project_drawing_images()

        for image_drawing in image_drawings:
            type = self.__db.IMAGE
            ts = int(int(image_drawing['timestamp'])/1000)
            date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%m/%d/%Y %H:%M')
            path = image_drawing['path']
            id = self.tree_view.insert_with_icon(self.DRAWING_TREE_INDEX, 'end', hmi_reference_file, text=image_drawing['name'], values=(date,path,image_drawing['name'],type), open=False)
            self.LEVEL_3_IDS.append(id)
        

        texts = self.__db.get_project_texts()
        for item in self.tree_view.get_children(item=self.TEXTS_TREE_INDEX):
            self.tree_view.delete(item)

        for text in texts:
            type = self.__db.TEXT
            ts = int(int(text['timestamp'])/1000)
            date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%m/%d/%Y %H:%M')
            path = text['path']
            id = self.tree_view.insert_with_icon(self.TEXTS_TREE_INDEX, 'end', text_reference_file, text=text['name'], values=(date,path,text['name'],type), open=False)
            self.LEVEL_3_IDS.append(id)

        tables = self.__db.get_project_tables()
        for item in self.tree_view.get_children(item=self.TABLES_TREE_INDEX):
            self.tree_view.delete(item)

        for table in tables:
            ts = int(int(table['timestamp'])/1000)
            date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%m/%d/%Y %H:%M')
            path = table['path']
            type = self.__db.TABLE            
            id = self.tree_view.insert_with_icon(self.TABLES_TREE_INDEX, 'end', table_reference_file, text=table['name'], values=(date,path,table['name'],type), open=False)
            self.LEVEL_3_IDS.append(id)


    def __setup_level_1_menu(self):
        self.menuA = tk.Menu(self.parent, tearoff=0)
        self.menuA.add_command(label='Export All With Data')
        self.menuA.add_command(label='Export All Originals')

    def __setup_level_2_menu(self):
        self.menuB = tk.Menu(self.parent, tearoff=0)
        self.menuB.add_command(label='Import',command=lambda: self.__import_document())
        self.menuB.add_command(label=self.__import_image_menu_label
                               ,command=lambda: self.__import_images()
                               ,state='disabled')
        self.menuB.add_separator()
        self.menuB.add_command(label='Export All With Data')
        self.menuB.add_command(label='Export All Originals')


    def __setup_level_3_menu(self):
        self.menuC = tk.Menu(self.parent, tearoff=0)
        self.menuC.add_command(label=self.__export_with_data_menu_label,command=lambda: self.__export_document_with_data())
        self.menuC.add_command(label=self.__export_original_menu_label,command=lambda: self.__export_document())
        self.menuC.add_command(label=self.__export_excel_menu_label,command=lambda: self.__export_excel_with_data())
        self.menuC.add_separator()
        self.menuC.add_command(label='Delete',command=lambda: self.__delete_document())

    def __pass_show_popup_func(self):
        def show_popup(iid, event):
            self.__iid = iid
            if iid in self.LEVEL_1_IDS:
                self.menuA.post(event.x_root, event.y_root)
            if iid in self.LEVEL_2_IDS:
                if iid == self.DRAWING_TREE_INDEX:
                    self.menuB.entryconfigure(self.__import_image_menu_label, state='normal') 
                else:
                    self.menuB.entryconfigure(self.__import_image_menu_label, state='disabled')
                self.menuB.post(event.x_root, event.y_root)
            if iid in self.LEVEL_3_IDS:
                # The exporters all read a single source file, which a folder backed image document does not have.
                values = self.tree_view.item(iid,"values")
                export_state = 'disabled' if len(values) > 3 and values[3] == self.__db.IMAGE else 'normal'
                for label in [self.__export_with_data_menu_label
                              ,self.__export_original_menu_label
                              ,self.__export_excel_menu_label]:
                    self.menuC.entryconfigure(label, state=export_state)
                self.menuC.post(event.x_root, event.y_root)


        self.tree_view.show_popup_func(show_popup)
    

    def __pass_double_click_func(self):
        def double_click(item, text, value):
            if len(value)< 4:
                return
            
            type = value[3]
            if item in self.LEVEL_1_IDS:
                    pass
            if item in self.LEVEL_2_IDS:
                    pass
            if item in self.LEVEL_3_IDS:
                if type == self.__db.IMAGE:
                    path = value[1]
                else:
                    path = value[1] +'/'+ value[2]
                logging.info('Opening document: '+text+' path: '+path)
                self.__document_selected_func(path,type)
              
          
        self.tree_view.double_click_func(double_click)

    def document_selected_func(self, func):
        
        self.__document_selected_func = func

    

    def set_opened_document_func(self, func):
        self.__opened_document_func = func 

    
    def set_close_doc_func(self, func):
        self.__close_document_func = func


    def toggle_open_close_children(self, item):
        if self.tree_view.item(item, 'open'):
            self.tree_view.item(item, open=False)  # close parent
        else:
            self.tree_view.item(item, open=True)  # close parent


    @handle_exception(0)
    def __import_document(self):
     

        if self.__iid == self.DRAWING_TREE_INDEX:

            """ Open image in the GUI """
            paths = askopenfilenames(title='Select a pdf files',
                                initialdir=os.path.dirname(self.__config.get_recent_path()),filetypes = [("PDF file (*.pdf)", "*.pdf")])
            if not paths: return

            self.__config.set_opened_path(paths[0])  # remember path

            # Check if they are valid pdf
            for path in paths:
                if not Validators.check_pdf(path):
                    messagebox.showinfo('Not a valid pdf',
                                        'This is not a valid pdf: "{}"\nPlease, select another pdf file.'.format(path))
                    self.__import_document()
                    return
                        
            type = self.__db.DRAWING
            if len(paths) == 1:
                destination = Project_File_Manager.import_drawing_file(paths[0], self.__project_name)
                self.__db.insert_project_document(os.path.basename(paths[0]),destination,type)
            else:
                destination, filename = Project_File_Manager.combine_drawing_files(paths, self.__project_name)
                self.__db.insert_project_document(filename,destination,type)
                
                # Start threaded check if borders are consistent
                self.__start_border_consistency_check(destination + '/' + filename)
        
        if self.__iid == self.TEXTS_TREE_INDEX:
            type = self.__db.TEXT
            """ Open image in the GUI """
            paths = askopenfilenames(title='Select a sheet file',
                                initialdir=os.path.dirname(self.__config.get_recent_path()),filetypes = [("PDF file (*.pdf)", "*.pdf")])
            if not paths: return

            self.__config.set_opened_path(paths[0])  # remember path
            
            # Check if they are valid pdf
            for path in paths:
                if not Validators.check_pdf(path):
                    messagebox.showinfo('Not a valid pdf',
                                        'This is not a valid pdf: "{}"\nPlease, select another pdf file.'.format(path))
                    self.__import_document()
                    return
            
            for path in paths:
                destination = Project_File_Manager.import_text_document_file(path, self.__project_name)
                self.__db.insert_project_document(os.path.basename(path),destination,type)

        if self.__iid == self.TABLES_TREE_INDEX:
            type = self.__db.TABLE
            """ Open image in the GUI """
            paths = askopenfilenames(title='Select a sheet file',
                                initialdir=os.path.dirname(self.__config.get_recent_path()),filetypes = [("Excel file (*.xlsx, *.xlsm)", "*.xlsx *.xlsm"), ("All files", "*.*")])
            if not paths: return

            self.__config.set_opened_path(paths[0])  # remember path
            
            # Check if they are valid excel
            for path in paths:
                if not Validators.check_sheet(path):
                    messagebox.showinfo('Not a valid Excel',
                                        'This is not a valid Excel: "{}"\nPlease, select another Excel file.'.format(path))
                    self.__import_document()
                    return 
     
            for path in paths:
                destination = Project_File_Manager.import_Sheets_file(path, self.__project_name)
                self.__db.insert_project_document(os.path.basename(path),destination,type)

        self.__setup_level_3()


    @handle_exception(0)
    def __import_images(self):
        paths = askopenfilenames(title='Select image or pdf files',
                                initialdir=os.path.dirname(self.__config.get_recent_path()),filetypes = [("Image or PDF files", "*.png *.jpg *.jpeg *.pdf")])
        if not paths: return

        self.__config.set_opened_path(paths[0])  # remember path

        # Check if they are valid images or pdfs
        for path in paths:
            if not Validators.check_image_or_pdf(path):
                messagebox.showinfo('Not a valid image or pdf',
                                    'This is not a valid image or pdf: "{}"\nPlease, select another file.'.format(path))
                self.__import_images()
                return

        pdf_paths = [path for path in paths if os.path.splitext(path)[1].lower() == '.pdf']
        if pdf_paths and len(pdf_paths) != len(paths):
            messagebox.showinfo('Mixed file types',
                                'Select either pdf files or image files, not a mixture of both.')
            self.__import_images()
            return

        type = self.__db.IMAGE

        if pdf_paths:
            imported = self.__rasterise_pdfs_as_images(pdf_paths)
            if imported is None: return
            destination, image_folder_name = imported
            self.__db.insert_project_document(image_folder_name,destination,type)
        elif len(paths) == 1:
            destination = Project_File_Manager.import_image_file(paths[0], self.__project_name)
            self.__db.insert_project_document(os.path.basename(paths[0]),destination,type)
        else: 
            destination, image_folder_name = Project_File_Manager.combine_drawing_files(paths, self.__project_name)
            self.__db.insert_project_document(image_folder_name,destination,type)

        self.__setup_level_3()


    def __rasterise_pdfs_as_images(self, paths):
        """Renders pdf pages to colour images so the document is scanned as an image and keeps its colours."""
        imported = {}

        def process(progress_update_and_check_if_should_stop, *_):
            def page_rendered(done, total):
                return progress_update_and_check_if_should_stop(
                    'Rendered page {done} of {total}'.format(done=done, total=total),
                    'Rendering pages...', (done / total) * 100.0)

            imported['value'] = Project_File_Manager.import_pdf_as_images(paths, self.__project_name
                                                                         , page_callback=page_rendered)

        texbox_progressbar_window(process, 'Import PDF as Images', auto_close=True)
        return imported.get('value')


    
  
    @handle_exception_with_messagebox()
    def __export_document_with_data(self):

        values = self.tree_view.item(self.__iid,"values")
        path = values[1] +'/'+ values[2]

        pdf_name, extension = os.path.splitext(values[2])
        
        proceed = False
        while proceed == False:
            filename = asksaveasfilename(initialfile = pdf_name,filetypes = [("PDF file (*.pdf)", "*.pdf")],confirmoverwrite=False)
            if filename != '':
                try:
                    f = open(filename + extension, "r")
                    f.close()
                    messagebox.showerror("Error","File exists - Choose another file name")
                except Exception as error:
                    proceed = True
            else:
                break
        

        if self.__selected_document_type() == self.__db.TEXT:
            exporter = export_text_pdf_with_data
        else:
            exporter = export_pdf_with_data

        texbox_progressbar_window(exporter, 'Exporting PDF with Data',path,filename + extension,self.__db)


        
        

    @handle_exception_with_messagebox()
    def __export_document(self):

        values = self.tree_view.item(self.__iid,"values")
        path = values[1] +'/'+ values[2]

        pdf_name, extension = os.path.splitext(values[2])
        
        proceed = False
        while proceed == False:
            filename = asksaveasfilename(initialfile = pdf_name,filetypes = [("PDF file (*.pdf)", "*.pdf")],confirmoverwrite=False)
            if filename != '':
                try:
                    f = open(filename + extension, "r")
                    f.close()
                    messagebox.showerror("Error","File exists - Choose another file name")
                except:
                    proceed = True
            else:
                break
        

        shutil.copy(path, filename + extension)


    @handle_exception_with_messagebox()
    def __export_excel_with_data(self):

        values = self.tree_view.item(self.__iid,"values")
        path = values[1] +'/'+ values[2]

        pdf_name, _ = os.path.splitext(values[2])
        
        extension = '.xlsx'

        proceed = False
        while proceed == False:
            filename = asksaveasfilename(initialfile = pdf_name,filetypes = [("Excel file (*.xlsx)", "*.xlsx")],confirmoverwrite=False)
            if filename != '':
                try:
                    f = open(filename + extension, "r")
                    f.close()
                    messagebox.showerror("Error","File exists - Choose another file name")
                except Exception as error:
                    proceed = True
            else:
                break
        

        if self.__selected_document_type() == self.__db.TEXT:
            texbox_progressbar_window(export_text_excel_with_data, 'Exporting Excel with Data',path,filename + extension,self.__db)
        else:
            texbox_progressbar_window(export_excel_with_data, 'Exporting PDF with Data',path,filename + extension,self.__db, self.__acm_data_handler)


    def __selected_document_type(self):
        values = self.tree_view.item(self.__iid,"values")
        return values[3] if len(values) > 3 else None
        

    def __delete_document(self):
        values = self.tree_view.item(self.__iid,"values")
        partial_path = values[1]
        filename = values[2]
        type = values[3]
        # Image documents are folder backed, so the folder is their viewer and roi key.
        path = partial_path if type == self.__db.IMAGE else partial_path +'/'+ filename
        if self.__opened_document_func() == path:
            self.__close_document_func()
        logging.info('Deleting document: {} with path: {}'.format(filename,path))

        # Check if document has any region of 
        roi_list = self.__db.get_project_document_roi(path)
        found_roi = False 
        for page_roi in roi_list:
            if page_roi:
                found_roi = True

        if found_roi:
            logging.warning('Failed to deleted document: {} with path: {}'.format(filename,path))
            messagebox.showwarning('Failed to Delete','A region of interest was found in the document. '+
                                                        'Please delete all regions of interest before deleting document.')
        else:
            self.__db.delete_project_document(filename)
            self.__db.delete_project_document_roi(path)
            Project_File_Manager.delete_document_file(partial_path)

        logging.info('Deleted document: {} with path: {}'.format(filename,path))

        self.__setup_level_3()
        



class page_navigation_page(tk.Frame):

    MAX_PAGE_IMAGE_HEIGHT = 300
    MAX_PAGE_IMAGE_WIDTH = 300

    def __init__(self, parent, controller, config=None):
        tk.Frame.__init__(self, parent)
        self.__db = None
        self.config(background="white")
        self.canvas = image_gallery_canvas(self)
        self.canvas.pack(side="top", fill="both", pady=0, expand=True)

        self.get_pages_thread = None
        self.kill_get_pages_thread = False
        self.pages = []
        self.got_pages = False
        self.doc = None
        self.previous_doc = None
        self.file_type = None

    def show(self):
        if self.doc and self.doc != self.previous_doc:
            self.previous_doc = self.doc
            self.canvas.reset_image_elements()
            self.canvas.start_loading_animation()
            self.got_pages = False
            self.pages = []

            if self.get_pages_thread != None:
                if self.get_pages_thread.is_alive():
                    self.kill_get_pages_thread = True
                    self.get_pages_thread.join()
                    self.kill_get_pages_thread = False

            if self.file_type != Database.IMAGE:
                self.get_pages_thread=Thread(target=self.get_pdf_pages)
                self.get_pages_thread.start()
                self.after(500, self.check_got_pages)
            else:
                self.get_pages_thread=Thread(target=self.get_image_pages)
                self.get_pages_thread.start()
                self.after(500, self.check_got_pages)


    def set_page_selected_callback(self, callback):
        self.canvas.image_selected_callback = callback
        

    def set_project(self, project_name, db, acm_data_handler=None):
        self.__db = db
        self.__project_name = project_name


    def open_doc(self, doc,file_type):
        self.doc = doc
        self.file_type = file_type


    def close_doc(self):
        self.doc = None


    def check_got_pages(self):
        if self.got_pages:
            self.__redraw_pages()
            return

        self.after(500, self.check_got_pages)

    def __redraw_pages(self):
        index = 1
        self.canvas.stop_loading_animation()
        for page in self.pages:
            imagetk = ImageTk.PhotoImage(page)
            self.canvas.insert_image_elements(str(index),imagetk)
            index = index + 1
        self.canvas.redraw()
        
    
    def get_image_pages(self):
        for image in self.doc:
            if self.kill_get_pages_thread:
                break
            img = Image.open(image)
            width, height = img.size
            if width > height:
                zoom_level = self.MAX_PAGE_IMAGE_WIDTH / width
            else:
                zoom_level = self.MAX_PAGE_IMAGE_HEIGHT / height
            img = img.resize((int(width * zoom_level), int(height * zoom_level)))
            self.pages.append(img)
        
        self.got_pages = True


    # ------------------------------------------------------------------------------
    # read the page data
    # ------------------------------------------------------------------------------
    def get_pdf_pages(self):
        """Render every page of the document down to a thumbnail image."""

        for pno in range(pdf_page_count(self.doc)):

            if self.kill_get_pages_thread:
                break

            width, height = page_size(self.doc, pno)

            if width > height:
                zoom_level = self.MAX_PAGE_IMAGE_WIDTH / width
            else:
                zoom_level = self.MAX_PAGE_IMAGE_HEIGHT / height

            self.pages.append(render_page(self.doc, pno, zoom=zoom_level, annots=False))
        
        self.got_pages = True
            


class bookmark_navigation_page(tk.Frame):

    def __init__(self, parent, controller, config=None):
        tk.Frame.__init__(self, parent)
        self.__project_name = None
        self.__db = None
        self.tree = tree_view(self)
        self.tree.pack(side="top", fill="both", pady=0, expand=True)
        self.tree.double_click_func(self.double_click_callback)
        self.doc = None 
        self.previous_doc = None


    def show(self):
        if self.doc and self.doc != self.previous_doc:
            self.previous_doc = self.doc

            self.tree.delete(*self.tree.get_children())

            if self.type == Database.DRAWING :
                toc = pdf_outline(self.doc)
            
            if self.type == Database.TABLE :
                toc = self.doc.sheet_names
            
            

            if toc:
                self.create_toc(toc, "", toc[0][0])

    def set_project(self, project_name, db, acm_data_handler=None):
        self.__db = db
        self.__project_name = project_name

    
 
    def open_doc(self, doc,type):
        self.doc = doc
        self.type = type


    def close_doc(self):
        self.doc = None


    def set_page_selected_callback(self, callback):
        
            self.page_selected_callback = callback
        
    def double_click_callback(self, item, text, values ):
        self.page_selected_callback(int(values[0]))


    def create_toc(self, contents, parent, phead, parent_index=''):
        """
        Table of contents extracted from PDF file is in form of nested list. This function converts that nested list
        in to a parent-child data structure, so that all heading and sub-heading can be associated
        :param contents: list of child
        :param parent: Parent heading of sub-heading
        :param phead: key of the parent heading
        :return: None
        """
        
        if self.type == Database.DRAWING:
            cons = iter(contents)
            for content in cons:
                i = contents.index(content)
                head, text = content[0], content[1]
                
                if head == phead:
                    i += 1
                    k = ''.join(text.split())
                    parent_name=self.tree.insert_with_icon(parent_index, 'end', bookmark, text=text,values=(content[2],'','',self.type), open=False)
                else:
                    j = i
                    while True:
                        j += 1
                        if j < len(contents) and contents[j][0] != phead:
                            next(cons, None)
                        else:
                            break
                    self.create_toc(contents[i:j], k, head,parent_name)
        if self.type == Database.TABLE:
            sheet_no = 0
            for sheet_name in contents:
                sheet_no +=1
                parent_name=self.tree.insert_with_icon(parent_index, 'end', bookmark, text=sheet_name,values=(sheet_no,'','',self.type), open=False)
        
        
if __name__ == "__main__":
    root = tk.Tk()

    app = navigation_frame(root)
    button0 = tk.Button(root, text="Go to Page Zero",
                            command=lambda: app.show_frame("project_folder_page"))
    #button1 = tk.Button(root, text="Go to Page One",                            command=lambda: app.show_frame("page_navigation_page"))
    button1 = tk.Button(root, text="Go to Page One", command=lambda: app.show_frame("page_navigation_page"))
    
    button2 = tk.Button(root, text="Go to Page Two",
                        command=lambda: app.show_frame("bookmark_navigation_page"))
    button0.pack()
    button1.pack()
    button2.pack()
    app.mainloop()