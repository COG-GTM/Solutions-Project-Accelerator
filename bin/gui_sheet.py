from tkinter import font
from tksheet import Sheet
import tkinter as tk

from bin.gui_horizontal_scrolling_selector import horizontal_scrolling_selector
from bin.logic_internal_database import Database
from .logic_logger import logging
import openpyxl

import pandas as pd

class SheetGUI:
    def __init__(self, placeholder, path, page_number_callback=None, zoom_percentage_callback=None):
        self.__imframe = tk.Frame(placeholder)  
        self.__imframe.grid_columnconfigure(0, weight = 1)
        self.__imframe.grid_rowconfigure(0, weight = 1)
        self.path = path
        self.pno=0
        self.selected_cell = None
        self.__selection_callback_func = None
        self.__text_selection_start = None 
        self.__text_selection_end = None
        self.__text_editor_selection = False
        self.__workbook = pd.ExcelFile(self.path, engine='openpyxl')
        self.__defualt_zoom_font_size = None
        self.__zoom_percentage_callback = zoom_percentage_callback
        self.__page_number_callback = page_number_callback
        
        self.sheet = None 
        self.__create_sheet_selector()
        self.__show_spreadsheet() 

    
    def __create_sheet_selector(self):
        self.selector_canvas = tk.Canvas(self.__imframe,height=35,background="white") 
        

        def callback(event):
            self.pno = int(event[1])
            self.__show_spreadsheet()  # redraw the image

        sheets = self.__workbook.sheet_names
        self.page_count = len(sheets)
        self.__sheet_selector = horizontal_scrolling_selector(self.selector_canvas,sheets,callback=callback
                                                ,selector_font=font.Font(family="Helvetica",size=10,weight="bold"))
        self.selector_canvas.bind('<Configure>',self.__draw_selector)
        self.selector_canvas.grid(row = 1, column = 0, sticky = "nswe")


    def setup_selection_callback(self, selection_callback):
        self.__selection_callback_func = selection_callback
        self.__selection_callback_func()


    def __draw_selector(self,_):
        self.__sheet_selector.draw(0,4)


    def __show_spreadsheet(self):
        self.sheet_df = self.__workbook.parse(self.pno, header=None)
        
        self.sheet_df = self.sheet_df.fillna('')          
        cols = self.sheet_df.shape[1]
        rows = self.sheet_df.shape[0]

        self.sheet = Sheet(self.__imframe,height=500,width=700)

        #data work
        self.sheet = Sheet(self.__imframe, data = [[self.sheet_df.values[r,c] for c in range(cols)] for r in range(rows)])
        self.headers= [columnNumberToExcelColumnName(i+1) for i in range(cols)] 
        self.sheet.headers(self.headers)

        
        self.sheet.enable_bindings(("single_select",
                                    "cell_select",
                                    "row_select",
                                    "column_width_resize",
                                    "arrowkeys",
                                    "select_all",
                                    "row_select",
                                    "column_select",
                                    "shift_column_select",
                                    "rc_select",
                                    "copy",
                                    "drag_select_columns",
                                    "drag_select_cells",
                                    "drag_select_rows",
                                    "edit_cell"))
        self.sheet.extra_bindings([("all_select_events", self.sheet_select_event)])
        self.sheet.bind("<<SheetRedrawn>>", self.__sheet_modified)
        self.sheet.extra_bindings("end_edit_cell", self.__end_cell_edit)
        self.__defualt_zoom_font_size = self.sheet.ops.table_font[1]
        
        self.sheet.MT.extra_double_b1_func = self.__disable_cell_edit
        self.__sheet_selector.select(self.pno)
        logging.info('Open sheet no: {} in {}'.format(self.pno+1,self.path))
        self.grid()
        self.sheet.after(500, self.__post_page_number)


    def __post_page_number(self):
        if self.__page_number_callback:
            self.__page_number_callback(self.pno+1, self.page_count)


    def __sheet_modified(self,_):
        precentage_zoom = self.sheet.ops.table_font[1]/ self.__defualt_zoom_font_size * 100
        if self.__zoom_percentage_callback:
            self.__zoom_percentage_callback(precentage_zoom) 
        

    def grid(self, **kw):
        """ Put CanvasImage widget on the parent widget """
        self.__imframe.grid(**kw)  # place CanvasImage widget on the grid
        self.__imframe.grid(sticky='nswe')  # make frame container sticky
        self.__imframe.rowconfigure(0, weight=1)  # make canvas expandable
        self.__imframe.columnconfigure(0, weight=1)
        self.sheet.grid(row = 0, column = 0, sticky = "nswe")
        

    def pack(self, **kw):
        """ Exception: cannot use pack with this widget """
        raise Exception('Cannot use pack with the widget ' + self.__class__.__name__)

    def place(self, **kw):
        """ Exception: cannot use place with this widget """
        raise Exception('Cannot use place with the widget ' + self.__class__.__name__)

    def sheet_select_event(self, event = None):
        self.__text_editor_selection = False
        try:
            currently_selected = self.sheet.get_currently_selected()
            if currently_selected:
                self.selected_cell = [currently_selected.row,currently_selected.column]
            else:
                self.selected_cell = None
                
        except:
            self.selected_cell = None

        self.sheet.popup_menu_del_command("Cut")
        self.__text_selection_start = None 
        self.__text_selection_end = None 
        if self.__selection_callback_func:
            self.__selection_callback_func()


    def __end_cell_edit(self,event:tk.Event):
        if self.__text_selection_start is None and self.__text_selection_end is None:
            return

        if event.type!=tk.EventType.FocusOut:
            return 
        start = self.__text_selection_start
        end = self.__text_selection_end
        
        
        self.__mark_blue(start, end)

        
    def __selection(self, _):
        text_editor = self.sheet.get_text_editor_widget()
        self.__text_selection_start = text_editor.index("sel.first")
        self.__text_selection_end = text_editor.index("sel.last")  

    def __focus_in(self,_):
        self.__remove_blue_mark()
        

    def __disable_cell_edit(self,event):
        self.__text_editor = self.sheet.get_text_editor_widget()
        
        self.__text_editor.bind('<<Selection>>', self.__selection)
        self.__text_editor.bind('<FocusOut>', self.__end_cell_edit)
        self.__text_editor.bind('<FocusIn>', self.__focus_in)
        
        self.__text_editor.configure(state='disabled')
        self.__text_editor.rc_popup_menu.delete(0, "end")
        self.__text_editor.rc_popup_menu.add_command(label = "Mark Yellow",
                                       command = self.__mark_yellow)
        self.__text_editor.rc_popup_menu.add_command(label = "Mark Green",
                                       command = self.__mark_green)
        self.__text_editor.rc_popup_menu.add_command(label = "Mark Red",
                                       command = self.__mark_red)
        
        self.__text_editor.rc_popup_menu.add_command(
            label="Copy",
            accelerator="Ctrl+C",
            command=self.__text_editor.copy,
        )


    def get_selection(self):
        text_editor = self.sheet.get_text_editor_widget()
        full_text = self.sheet.get_data(self.selected_cell[0],self.selected_cell[1])
        if text_editor is None or not self.__text_editor_selection:
            text = None
            start = None
            end = None
        else:
            text = text_editor.get(self.__text_selection_start, self.__text_selection_end)
            start = self.__text_selection_start
            end = self.__text_selection_end
        return ((full_text,text), start, end, self.selected_cell, self.pno, self.path, Database.TABLE)

    

    def __mark_blue(self, index_1, index_2):
        self.__text_editor.tag_add('highlight_blue',index_1, index_2)
        self.__text_editor.tag_configure('highlight_blue', foreground="white", background="#0078d7")
        self.__text_editor_selection = True


    def __remove_blue_mark(self):
        
        self.__text_editor.tag_remove('highlight_blue'
                                                        ,self.__text_selection_start
                                                        ,self.__text_selection_end)
        print(self.__text_selection_start)
        print(self.__text_selection_end)


    def __mark_yellow(self):
        self.sheet.get_text_editor_widget().tag_add('highlight yellow',tk.SEL_FIRST, tk.SEL_LAST)
        self.sheet.get_text_editor_widget().tag_configure('highlight yellow', selectforeground ='#ffbf00',selectbackground="#0078d7", foreground="black", background="yellow")


    def __mark_green(self):
        self.sheet.get_text_editor_widget().tag_add('highlight green',tk.SEL_FIRST, tk.SEL_LAST)
        self.sheet.get_text_editor_widget().tag_configure('highlight green', underline=True, selectforeground ='#00ff00',selectbackground="#0078d7", foreground="black", background="#00ff01")


    def __mark_red(self):
        self.sheet.get_text_editor_widget().tag_add('highlight red',tk.SEL_FIRST, tk.SEL_LAST)
        self.sheet.get_text_editor_widget().tag_configure('highlight red', overstrike=True, selectforeground ='#ff0000',selectbackground="#0078d7", foreground="black", background="red")


    def __get_text(self):
        print(self.sheet.get_text_editor_widget().get(tk.SEL_FIRST, tk.SEL_LAST))
     
    def destroy(self):
        """ ImageFrame destructor """
        logging.info('Close workbook: {}'.format(self.path))
        
        self.__imframe.destroy()
    
    def go_to_page(self, page_numnber):
        self.pno = page_numnber - 1
        self.__show_spreadsheet()  # redraw the image


    def go_to_pno(self, pno):
        self.pno = pno
        self.__show_spreadsheet()  # redraw the image


# Function to print Excel column name
# for a given column number
def columnNumberToExcelColumnName(num) -> str:
    alpha = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    if num < 26:
        return alpha[num-1]
    else:
        q, r = num//26, num % 26
        if r == 0:
            if q == 1:
                return alpha[r-1]
            else:
                return columnNumberToExcelColumnName(q-1) + alpha[r-1]
        else:
            return columnNumberToExcelColumnName(q) + alpha[r-1]



    
      

