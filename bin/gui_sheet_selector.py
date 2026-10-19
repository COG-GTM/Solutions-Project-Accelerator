# -*- coding: utf-8 -*-
import cv2
import numpy as np
from bin.logic_internal_database import Database
import io
import logging
from threading import Thread

from PIL import Image, ImageTk
from bin.logic_linked_graphic import Linked_Graphic
import tkinter as tk
import uuid
import json

from .gui_sheet import SheetGUI

class SheetSelectorTools(SheetGUI):

    CURSOR_TOOL = 0
    HAND_TOOL = 1
    RECTANGULAR_TOOL = 2
    POLYGON_TOOL = 3

    """ Class of SelectorTools. Inherit CanvasImage class """
    def __init__(self, placeholder, path, db: Database, **kwargs):
        """ Initialize the SelectorTools """

        self.__db = db # Internal project database        
        SheetGUI.__init__(self, placeholder, path, **kwargs)  # call __init__ of the CanvasImage class
        #self.sheet.highlight_cells(cells=([1,1],[2,2]),fg='#00FF00',bg='#FF0000')
        self.roi_list = self.__db.get_project_document_roi(self.path)  # list of all page roi rectangles and theirself.color_back_hole = 'cyan'  # draw hole color
        

    def get_selection_subscription(self, selection_callback):
        '''Sets callback that notifies another object of selection'''
        #self.__selection_callback = callback
        selection_callback(self.__subscribe_to_selections)


    def __subscribe_to_selections(self, selection_callback, sheet_change_callback, selected_cell_callback, _
                                  ,multi_selection_callback=None, refresh_tool_canvas_callback=None,show_cell_link_callback=None,
                                  text_mark_callback=None,pending_linked_text_action_callback=None):
        if selection_callback:
            self.__selection_callback_func = selection_callback
            self.setup_selection_callback(self.__selection_callback)
            self.__selection_callback()

        if sheet_change_callback:
            self.__tool_panel_sheet_change_callback = sheet_change_callback
            self.__tool_panel_sheet_change_callback(self.path,self.pno)


    def __selection_callback(self):
        if self.__selection_callback_func and self.selected_cell:
            self.__selection_callback_func(True,
                                    roi_select_func = self.get_selection,
                                    move_to_roi_func = self.move_to_roi,
                                    clear_shown_text_roi_list = self.__clear_shown_text_roi_list,
                                    refresh_roi = self.__refresh_rois,
                                    get_sheet_dataframe = self.__get_sheet_dataframe,
                                    given_text = self.get_selection,
                                    document_type = Database.TABLE)
        
        elif self.__selection_callback_func:
            self.__selection_callback_func(False,
                                    roi_select_func = self.get_selection,
                                    move_to_roi_func = self.move_to_roi,
                                    clear_shown_text_roi_list = self.__clear_shown_text_roi_list,
                                    refresh_roi = self.__refresh_rois,
                                    get_sheet_dataframe = self.__get_sheet_dataframe,
                                    given_text = self.get_selection,
                                    document_type = Database.TABLE)

    def __get_sheet_dataframe(self):
        return self.sheet_df.copy()

    def __clear_shown_text_roi_list(self):
        pass

    def __refresh_rois(self,page_index=None):
        self.roi_list = self.__db.get_project_document_roi(self.path)
        self.__get_rois()


    def move_to_roi(self, cell, sheet):
        if self.pno != sheet:
            self.go_to_pno(sheet)
        self.sheet.see(cell[0],cell[1])
        cells = self.sheet.get_selected_cells()
        for selected_cell in cells:
            if cell == list(selected_cell):
                return

        self.sheet.select_cell(cell[0],cell[1])


    def __get_rois(self):
        
        logging.info("Getting page number {pno} of {doc} region-of-interests".format(pno=self.pno,doc=self.path))
        if len(self.roi_list) != self.page_count:
            self.roi_list = [None] * self.page_count
            logging.info("Created new region-of-interests list for document {doc} ".format(doc=self.path))

        if self.roi_list[self.pno] == None:
            self.roi_list[self.pno] = {}
            logging.info("Created new region-of-interests list for page number {pno} of {doc} ".format(pno=self.pno,doc=self.path))

        logging.info("Redrawing region-of-interests for page number {pno} of {doc} ".format(pno=self.pno,doc=self.path))
        self.reset(self.roi_list[self.pno])
        
        

        
