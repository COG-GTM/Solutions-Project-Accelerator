import logging
import re
import threading
from tkinter import font, messagebox
import tkinter as tk
from typing import Dict
from uuid import uuid4
from PIL import Image, ImageDraw, ImageTk
import pandas as pd
from pandas import DataFrame

from bin.gui_approval_view import rectangle_canvas_button
from bin.gui_elements import loading_animation
from bin.gui_link_ignore_text_view import link_ignore_text_view, linked_text_boolean_selector, linked_text_ignore_entry, linked_text_interger_selector, linked_text_string_selector
from bin.gui_link_view import link_view
from bin.gui_parameter_list_view import integer_linked_text_entry, string_linked_text_entry
from bin.gui_parameter_selection import boolean_selector, interger_selector, string_selector
from bin.logic_acm_data_handler import ACM_Data_Handler
from bin.logic_acm_function_handler import acm_parameter_handler
from bin.logic_acm_libraries_retrieval import acm_libraries_retrieval, get_library_file_path
from bin.logic_acm_parameter import acm_paramter
from bin.logic_acm_library_parser import acm_library_parser, get_object_NIBS
from bin.logic_internal_database import Database
from bin.logic_linked_text import Linked_Text
from bin.logic_linked_texts import Linked_Texts


try:
    from bin.gui_base64_icons import error_image
    from bin.gui_parameter_list_view import add_parameter_view
    from bin.gui_linked_text_entry_view import linked_text_entry
    from bin.gui_parameter_list_view import link_ignore_view, real_linked_text_entry
except:
    from gui_base64_icons import error_image
    from gui_parameter_list_view import add_parameter_view
    from gui_linked_text_entry_view import linked_text_entry
    from gui_parameter_list_view import link_ignore_view, real_linked_text_entry
    
class subobject_parameter_list_view():
    def __init__(self, canvas:tk.Canvas,object_id,acm_data_handler:ACM_Data_Handler,db:Database, project_name=None,x=0,y=0, selected_subobject_dict={}, subobject=None, subobject_parameters=None, tagname=''
                                ,subobject_type='',create_subobject_callback=None,go_to_callback=None,save_reference_id_callback=None,library_parser=None
                                ,redraw_callback=None, config=None,add_to_background_func=None, remove_from_background_func=None
                                ,is_active_callback=None) -> None:
        self.__canvas = canvas 
        self.__object_id = object_id
        self.__acm_data_handler = acm_data_handler
        self.__config = config
        self.__is_active_callback = is_active_callback
        self.__db = db
        self.__thinking = False
        self.__db.subscribe_unapproved_text_link_detailed_update(
                            object_id, subobject_type, self.internal_db_linked_text_change_callback
                            )
        self.__add_to_background_func = add_to_background_func
        self.__remove_from_background_func = remove_from_background_func
        self.__create_subobject_callback = create_subobject_callback
        self.__library_parser = library_parser
        self.__subobject_type=subobject_type
        self.__project_name = project_name
        self.__go_to_callback = go_to_callback
        self.__redraw_callback = redraw_callback
        self.__pending_transactions = {}
        self.__pending_subobject_names = []
        self.__pending_subobject_link_names = []
        self.__save_reference_id_callback = save_reference_id_callback
        self.__selected_subobject_df = DataFrame()
        self.__id = uuid4()
        down_arrow = Image.new('RGBA', (15, 15), '#00000000')
        draw = ImageDraw.Draw(down_arrow)
        draw.line([(0, 4), (7, 11), (14, 4) ], fill=(220,220,220,255),width=2)
        up_arrow = down_arrow.rotate(180)
        self.__tagname = tagname
        self.__subobject = subobject
        self.__subobject_parameters = subobject_parameters
        self.__down_arrow = ImageTk.PhotoImage(down_arrow)
        self.__up_arrow = ImageTk.PhotoImage(up_arrow)
        self.__opened_subobject = ''
        self.__subobject_cells:Dict[str:subobject_cell] = {}
        self.__document_selection_subscription_selected = None
        self.__document_selection_subscription_kwargs = None
        self.__document_type = None
        self.__text_in_table = True
        self.__create_subobject_cells()
        self.__x = x
        self.__y = y
        self.__width = None
        self.__header_font = font.Font(family="Helvetica",size=11,weight="normal")
        self.__allow_adding_locations = True
        self.__show_add_subobject = True
        self.__add_text = None
        self.__full_subobject_list = []
        self.__subobject_last_selected_index = 0
        self.__unable_process_subobject = False
        self.message_title_id = None
        self.processed_dependencies = {}
        self.auto_increment_previous_values = {}
        self.__context_menu = None
        self.__current_subobject_id = None
        self.__current_subobject_name = None
        self.__setup_context_menu()
        try:

            self.__build_subparameters()
        except Exception as e:
            self.__unable_process_subobject = True

    def internal_db_linked_text_change_callback(self, linked_text_id):
        print('Linked text changed callback received for linked text id:', linked_text_id)
        list_changed = False
        for _, subobject_cell in self.__subobject_cells.items():
            if subobject_cell.internal_db_linked_text_change_callback(linked_text_id):
                list_changed = True

        if list_changed and not self.__thinking:
            self.reset_subobjects()

        

    def ignore_text(self, linked_text, parameter):
        for _, subobject_cell in self.__subobject_cells.items():
            subobject_cell.ignore_text(linked_text, parameter)

    
    def __setup_context_menu(self):
        """Setup the right-click context menu for subobjects"""
        self.__context_menu = tk.Menu(self.__canvas, tearoff=0)
        self.__context_menu.add_command(label='Delete Subobject', command=self.__delete_subobject)


    def __delete_subobject(self):
        """Delete the currently selected subobject"""
        if self.__current_subobject_id is None:
            return
        
        # Check if this is a pending subobject or a committed one
        is_pending = False
        subobject_name = self.__current_subobject_name
        
        # First check if it's in pending transactions
        if subobject_name in self.__pending_transactions:
            is_pending = True
        
        if not subobject_name:
            return
        
        # Confirm deletion
        if is_pending:
            message = f"Are you sure you want to remove the pending subobject '{subobject_name}'?\n\nThis will discard unsaved changes."
        else:
            message = f"Are you sure you want to delete the subobject '{subobject_name}'?\n\nThis action cannot be undone and will remove it from the ACM database."
        
        response = messagebox.askyesno(
            "Delete Subobject",
            message,
            icon='warning'
        )
        
        if not response:
            return
        

        if is_pending:
            # Remove from local tracking
            del self.__pending_transactions[subobject_name]
            message = f"Pending subobject '{subobject_name}' removed successfully"
            
        else:
            # Delete from database
            self.__acm_data_handler.delete_subobject(self.__current_subobject_id)
            message = f"Subobject '{subobject_name}' deleted successfully"
        

        self.__subobject_cells[subobject_name].delete_linked_text()

        # Redraw the view
        messagebox.showinfo("Success", message)
        self.reset_subobjects()
                
   
    

    
    def reset_subobjects(self):
        self.__delete_list()
        self.__create_subobject_cells()
        self.__opened_subobject = ''
        self.__current_subobject_id = None
        self.draw()
        


    def __show_context_menu(self, event, subobject_id, subobject_name=None):
        """Show the context menu at the cursor position"""
        self.__current_subobject_id = subobject_id
        self.__current_subobject_name = subobject_name
        try:
            self.__context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.__context_menu.grab_release()

    
    def __create_subobject_cells(self, show_thinking=False):
        if self.__object_id is None:
            return
        acm_subobjects_df = self.__acm_data_handler.get_all_subobjects_in_object(self.__object_id,self.__subobject_type)
        approved_text_links = self.__db.get_all_approved_subobject_parameters_text_link(self.__tagname, self.__subobject_type)

        list_of_approved_subobject_names = [link['subobject_name'] for link in approved_text_links]

        unapproved_text_links = self.__db.get_all_unapproved_subobject_parameters_text_link(self.__tagname, self.__subobject_type)
        
        list_of_unapproved_subobject_names = [link['subobject_name'] for link in unapproved_text_links if 'subobject_name' in link]
        self.__pending_subobject_link_names = list_of_unapproved_subobject_names

        pending_transactions_df = self.convert_pending_transactions_to_df(unapproved_text_links)
        
        self.__selected_subobject_df = pd.DataFrame()
        self.__selected_subobject_df = pd.concat([acm_subobjects_df, pending_transactions_df])



        for subobject_id, subobject in self.__selected_subobject_df.iterrows():
            if subobject['Name'] in self.__subobject_cells:
                continue
            self.__subobject_cells[subobject['Name']] = subobject_cell(self.__canvas
                                                                       ,self.__object_id
                                                                       ,subobject_id
                                                                       ,self.__acm_data_handler
                                                                       ,self.__db
                                                                       ,self.__subobject_parameters
                                                                       ,self.__project_name
                                                                       ,redraw_callback=self.__redraw_callback
                                                                       ,tagname=self.__tagname
                                                                       ,library_parser=self.__library_parser
                                                                       ,subobject_name=subobject['Name']
                                                                       ,subobject_type=self.__subobject_type
                                                                       ,go_to_callback=self.__go_to_callback
                                                                       ,pending_transaction=True if subobject['Name'] in list_of_unapproved_subobject_names else False
                                                                       ,delete_pending_transaction_callback=self.delete_non_commited_subobject
                                                                       ,config=self.__config)

            if show_thinking and subobject['Name'] in pending_transactions_df['Name'].values:
                self.__subobject_cells[subobject['Name']].show_thinking()
                
            if subobject['Name'] in list_of_approved_subobject_names:
                index = list_of_approved_subobject_names.index(subobject['Name'])
                self.__subobject_cells[subobject['Name']].setup_linked_text(approved_text_links[index], is_approved=True)
            
            elif subobject['Name'] in list_of_unapproved_subobject_names:
                index = list_of_unapproved_subobject_names.index(subobject['Name'])
                self.__subobject_cells[subobject['Name']].setup_linked_text(unapproved_text_links[index], is_approved=False)
            
            else:
                logging.info('Unable find subobject link for {} in '.format(subobject['Name'],self.__tagname))

            if self.__document_selection_subscription_kwargs is None:
                continue

            # Add not_redraw to self.__document_selection_subscription_kwargs
            if show_thinking:
                dont_redraw = True
                self.__document_selection_subscription_kwargs['not_redraw'] = dont_redraw
            self.__subobject_cells[subobject['Name']].document_selection_subscription(self.__document_selection_subscription_selected
                                                                            ,**self.__document_selection_subscription_kwargs)
        

    def convert_pending_transactions_to_df(self, unapproved_subobjects):
        pending_transactions_df = DataFrame()
        for subobject_name in unapproved_subobjects:
            temp_df = pd.DataFrame([{
                'Name': subobject_name['subobject_name']
            }])
            pending_transactions_df = pd.concat([pending_transactions_df, temp_df])
        for subobject_name in self.__pending_subobject_names:
            if subobject_name in unapproved_subobjects:
                continue
            temp_df = pd.DataFrame([{
                'Name': subobject_name
            }])
            pending_transactions_df = pd.concat([pending_transactions_df, temp_df])
        return pending_transactions_df
    

    def delete_non_commited_subobject(self, subobject_name):
        self.reset_subobjects()
        
        



    def __create_non_commit_subobject(self):
        subobject_parameters = self.__library_parser.get_subobject_parameters(self.__subobject_type)
        subobjects_library_data = self.__library_parser.get_all_subobjects()

        try:
            subobject_name = str(uuid4())[:8]
            
            subobject_name = subobject_name + "*"
            self.__pending_subobject_names.append(subobject_name)
            self.__pending_transactions[subobject_name] = {
                'subobject_type': self.__subobject_type,
                'subobject_data': subobjects_library_data[self.__subobject_type],
                'subobject_name': subobject_name,
                'subobject_parameters': subobject_parameters
            }
            return subobject_name
        except Exception as error:
            messagebox.showwarning("Unable to create new subobject",error)
            
    

    def document_selection_subscription(self, selected , **kwargs):
        self.__document_selection_subscription_selected = selected
        self.__document_selection_subscription_kwargs = kwargs
        for _, subobject_cell in self.__subobject_cells.items():
            subobject_cell.document_selection_subscription(selected , **kwargs)

    def show_linked_text(self, linked_text):
        self.__opened_subobject=linked_text['subobject_name']
        self.draw()

    def draw(self,x=0,y=0,width=None):
        # A deferred redraw can arrive after the user moved to another screen on the shared canvas
        if self.__is_active_callback and not self.__is_active_callback():
            return
        if width:
            self.__width = width
        else:
            width = self.__width
        if width is None and self.__width is None:
            width = 200
        self.__delete_list()
        count = 0
        x = self.__x + x 
        y = self.__y + y

        if self.__unable_process_subobject:
            self.__draw_error_message()
            return 
        else:
            self.__hide_error_message()

        
        for subobject_id, subobject_data in self.__selected_subobject_df.iterrows():
            subobject = subobject_data['Name']
            if subobject != self.__opened_subobject:
                image = self.__down_arrow
                increase = 55
                func = self.__open_parameter
                draw_subobject = False 
            else:
                image = self.__up_arrow
                increase = 210
                func = self.__close_parameter
                draw_subobject = True

            tags=(self.__id,subobject,count,subobject_id)
            rect = self.__canvas.create_rectangle(x,y,x+width,y+increase,fill='',outline='',tags=tags)
            is_pending = subobject.endswith('*') or subobject in self.__pending_subobject_link_names
            if subobject.endswith('*'):
                # name is a generated uuid, so show the type instead
                subobject_text = "Pending " + self.__subobject_type
            elif is_pending:
                subobject_text = "Pending " + subobject
            else:
                subobject_text = subobject
            text = self.__canvas.create_text(x+16,y+21,anchor=tk.NW,text=subobject_text,tags=tags,fill='#A3A3A3' if is_pending else '#606060',font=self.__header_font)
            rect_to_hide_text = self.__canvas.create_rectangle(x + width-23,y,x + width, y+increase,fill='white',outline='',tags=tags)
            icon = self.__canvas.create_image(x + width-16,y+28,image=image,tags=tags)
            
            self.__canvas.tag_bind(rect,'<Button-1>',func)
            self.__canvas.tag_bind(text,'<Button-1>',func)
            self.__canvas.tag_bind(icon,'<Button-1>',func)
            self.__canvas.tag_bind(rect_to_hide_text,'<Button-1>',func)
            
            # Bind right-click for context menu
            self.__canvas.tag_bind(rect,'<Button-3>',lambda e, sid=subobject_id, name=subobject: self.__show_context_menu(e, sid, name))
            self.__canvas.tag_bind(text,'<Button-3>',lambda e, sid=subobject_id, name=subobject: self.__show_context_menu(e, sid, name))
            self.__canvas.tag_bind(icon,'<Button-3>',lambda e, sid=subobject_id, name=subobject: self.__show_context_menu(e, sid, name))
            self.__canvas.tag_bind(rect_to_hide_text,'<Button-3>',lambda e, sid=subobject_id, name=subobject: self.__show_context_menu(e, sid, name))
            
            if not draw_subobject:
                y = increase + y 
                self.__canvas.create_line(x+8,y,x+width-8,y,width=1,fill='#D5D5D5',tags=tags)
                continue 

            y = increase + y + self.__subobject_cells[subobject].draw(x,y + 50)
            self.__canvas.create_line(x+8,y,x+width-8,y,width=1,fill='#D5D5D5',tags=tags)
            
        if self.__opened_subobject in self.__subobject_cells:
            self.__subobject_cells[self.__opened_subobject].setup_regex_on_viewer()

        self.__draw_add_button(x + 16, y + 24)
        self.__canvas.config(scrollregion=(0,0,self.__canvas.bbox(tk.ALL)[2],self.__canvas.bbox(tk.ALL)[3]+100))
       

    def __draw_error_message(self):
        self.message_image = tk.PhotoImage(data=error_image)
        error_message = 'Unable to show subobjects. Subobjects contain complex references.'
        self.message_image_id = self.__canvas.create_image(int(self.__canvas.winfo_width()/2), 
                                    int(self.__canvas.winfo_height()/3), 
                                    image = self.message_image, 
                                    anchor = tk.CENTER)
        title_font = font.Font(family="arial.ttf",size=11,weight="bold")
        self.message_title_id = self.__canvas.create_text(int(self.__canvas.winfo_width()/2),
                                    int(self.__canvas.winfo_height()/3 + self.message_image.height()/2 + 8),
                                    text="Unable to display Subobjects", anchor=tk.CENTER, fill="#A0A0A0",font=title_font,
                                    justify=tk.CENTER)
        message_font = font.Font(family="arial.ttf",size=9,weight="normal")
        self.message_text_id = self.__canvas.create_text(int(self.__canvas.winfo_width()/2),
                                    int(self.__canvas.winfo_height()/3 + self.message_image.height()/2 + 24),
                                    text=error_message, anchor=tk.CENTER, fill="#A0A0A0",font=message_font,
                                    justify=tk.CENTER)
        

    def __hide_error_message(self):
        if self.message_title_id:
            self.__canvas.delete(self.message_title_id)
            self.__canvas.delete(self.message_text_id)
            self.__canvas.delete(self.message_image_id)


    


    def __draw_add_button(self, x, y):
        padding = 8
        self.__delete_elements()
        
        tags=(self.__id,)
        x = self.__x + x # For static elements
        y = self.__y + y + padding # For static elements
        
        if self.__allow_adding_locations:
            fill = "#505050"
        else:
            fill="#C0C0C0"

        self.__add_text = self.__canvas.create_text(x, y, tags=tags,
                                                                text='+ Add subobject ', 
                                                                font=('Arial',10,'normal'), 
                                                                anchor=tk.NW, 
                                                                fill=fill)
        bounds = self.__canvas.bbox(self.__add_text)
        self.__add_rect = self.__canvas.create_rectangle(bounds[0]-padding ,bounds[1] -padding,bounds[2]+ padding ,bounds[3]+ padding,fill='#FFFFFF', width = 0, tags=tags)
        self.__canvas.tag_raise(self.__add_text)
        

        self.__canvas.tag_bind(self.__add_rect,'<Enter>', self.__on_add_enter)
        self.__canvas.tag_bind(self.__add_rect,'<Leave>', self.__on_add_leave)
        self.__canvas.tag_bind(self.__add_text,'<Enter>', self.__on_add_enter)
        self.__canvas.tag_bind(self.__add_text,'<Leave>', self.__on_add_leave)
        self.__canvas.tag_bind(self.__add_rect,'<Button-1>', self.__add_subobject)
        self.__canvas.tag_bind(self.__add_text,'<Button-1>', self.__add_subobject)


    def __delete_elements(self):
        if self.__add_text:
            self.__canvas.delete(self.__add_text)
            self.__canvas.delete(self.__add_rect)

        if self.message_title_id:
            self.__canvas.delete(self.message_title_id)
            self.__canvas.delete(self.message_text_id)
            self.__canvas.delete(self.message_image_id)
       


    def __on_add_enter(self,_):
        self.__canvas.itemconfig(self.__add_rect, fill='#E5E5E5')


    def __on_add_leave(self,_):
        self.__canvas.itemconfig(self.__add_rect, fill='#FFFFFF')


    def add_non_commit_subobject(self, callback):

        self.__thinking = True
        subobject = self.__create_non_commit_subobject()
        
        self.__selected_subobject_df[subobject] = True
        self.__create_subobject_cells(show_thinking=True)
        self.__opened_subobject = subobject
        self.draw()
        self.__add_to_background_func()
        callback(self.__prediction_streaming_callback)

    
    def __prediction_streaming_callback(self, results, message):

        if not results:
            return
        
        def update_view():
            
            if 'dependency_groups' in results:
                self.__pending_subobject_names = []
                self.__pending_transactions = {}
                self.__dependency_groups = results['dependency_groups']
                

                self.draw()

            self.__process_prediction_post_result(results)

        self.__canvas.after(0, update_view)

    
    def __process_prediction_post_result(self, post_result):

        processed_dependencies = post_result.get('processed_dependencies', [])

        if not processed_dependencies:
            return
        
        self.__pending_subobject_names = []
        self.__pending_transactions = {}
                
        first_subobject = ''
        for _ in self.__dependency_groups:
            subobject_name = self.__create_non_commit_subobject()

            if first_subobject == '':
                first_subobject = subobject_name
    
        self.__opened_subobject = first_subobject
        self.__create_subobject_cells()

        for i, subobject_names in enumerate(self.__pending_transactions.keys()):
            self.__subobject_cells[subobject_names].show_thinking()

        self.draw()

        for i, subobject_names in enumerate(self.__pending_subobject_names):
            if len(processed_dependencies) <= i:
                break
            self.__pending_subobject_names = []
            self.__subobject_cells[subobject_names].predicted_linked_text(processed_dependencies[i])


        for i, subobject_names in enumerate(self.__pending_transactions.keys()):
            self.__subobject_cells[subobject_names].hide_thinking()
        self.__remove_from_background_func()
        
        self.draw()
        self.__thinking = False


    def __add_subobject(self, _=None):


        subobject = self.__full_subobject_list[self.__subobject_last_selected_index]

        self.__subobject_last_selected_index = self.__subobject_last_selected_index + 1

        
        self.__create_subobject_callback(self.__subobject_type)
        
        self.__selected_subobject_df[subobject] = True
        self.__create_subobject_cells()
        self.__show_add_subobject = False
        self.__opened_subobject = ''
        self.draw()


    def __build_subparameters(self):
        min_index = int(acm_parameter_handler(self.__subobject_parameters['Index']['Min']
                              ,self.__object_id
                              ,self.__acm_data_handler
                              ,self.__project_name))
        
        max_index = int(acm_parameter_handler(self.__subobject_parameters['Index']['Max']
                              ,self.__object_id
                              ,self.__acm_data_handler
                              ,self.__project_name))
        

        subobject_name_template =self.__subobject['Name']

        

        for i in range(min_index,max_index+1):
            index = "{:02d}".format(i)
            subobject_name=subobject_name_template.format(Index=index)

            self.__full_subobject_list.append(subobject_name)
            

    def ignore_text(self, linked_text, parameter):
        if self.__opened_subobject in self.__subobject_cells:
            self.__subobject_cells[self.__opened_subobject].ignore_text(linked_text, parameter)


    def __open_parameter(self, event):
        curX, curY = ( self.__canvas.canvasx(event.x),  self.__canvas.canvasy(event.y))
        id = self.__canvas.find_closest(curX,curY)
        tags = self.__canvas.gettags(id)
        self.__opened_subobject = tags[1]
        self.draw()

    def __close_parameter(self, event):
        curX, curY = ( self.__canvas.canvasx(event.x),  self.__canvas.canvasy(event.y))
        id = self.__canvas.find_closest(curX,curY)
        tags = self.__canvas.gettags(id)
        if tags[1] == self.__opened_subobject:
            self.__opened_subobject = ''
        
        
        self.draw()


    def __delete_list(self):
        self.__canvas.delete(self.__id)

        for _, subobject_cell in self.__subobject_cells.items():
            subobject_cell.hide()

    def hide(self):
        self.__delete_list()
        self.__delete_elements()


    def fit_description_in_mutiline(self, description_label, description, tags,y):

        description_bounds = self.__canvas.bbox(description_label) 

        if description_bounds is None:
            return description_label

        if (description_bounds[2] - description_bounds[0]) < (self.__canvas.winfo_width()/2 - 8) or self.__canvas.winfo_width() <= 0:
            return description_label
        
        second_line_substring = 0 
        split = description.split(" ")
        while True :
            second_line_substring = second_line_substring + 1
            multiline_description = ' '.join(split[:second_line_substring])
            self.__canvas.delete(description_label)
            description_label = self.__canvas.create_text(int(self.__canvas.winfo_width()/2)+4,y + 11, text=multiline_description, anchor=tk.NW, tags=tags, fill="#6F6F6F")
            description_bounds = self.__canvas.bbox(description_label)
            if (description_bounds[2] - description_bounds[0]) > (self.__canvas.winfo_width()/2 - 16):
                break
        second_line_substring = second_line_substring - 1
        self.__canvas.delete(description_label)
        multiline_description = ' '.join(split[:second_line_substring])+'\n'+' '.join(split[second_line_substring:])
        return self.__canvas.create_text(int(self.__canvas.winfo_width()/2)+4,y + 11, text=multiline_description, anchor=tk.NW, tags=tags, fill="#6F6F6F")
        
    

class subobject_cell():
    def __init__(self,  canvas:tk.Canvas, object_id,subobject_id,acm_data_handler:ACM_Data_Handler, db:Database
                 , parameters,project_name=None, x=0,y=0, redraw_callback=None,tagname='',subobject_name='',subobject_type='',go_to_callback=None
                 , pending_transaction=None, delete_pending_transaction_callback=None, config=None, library_parser=None) -> None:
        self.__canvas = canvas
        self.__object_id = object_id
        self.__subobject_id = subobject_id
        self.__subobject_type = subobject_type
        self.__acm_data_handler = acm_data_handler
        self.__config = config
        self.__db = db
        self.__library_parser = library_parser
        self.__project_name = project_name
        self.__go_to_callback = go_to_callback
        self.__delete_pending_transaction_callback = delete_pending_transaction_callback
        self.__x = x
        self.__y = y 
        self.__width = None 
        self.__tagname = tagname
        self.__subobject_name = subobject_name
        self.__subobject = subobject_type
        self.__parameters = parameters
        self.__id = uuid4()
        self.__redraw_callback = redraw_callback
        self.__heading_font = font.Font(family="Helvetica",size=11,weight="bold")
        self.__subparameter_cell_list_view = None 
        self.__document_selection_subscription_selected = None
        self.__document_selection_subscription_kwargs = None
        self.__pending_transaction = pending_transaction
        self.__setup_views()


    def document_selection_subscription(self, selected , **kwargs):
        self.__document_selection_subscription_selected = selected
        self.__document_selection_subscription_kwargs = kwargs
        if self.__subparameter_cell_list_view:
            self.__subparameter_cell_list_view.document_selection_subscription(selected , **kwargs)

    
    def __setup_views(self):
        self.__subparameter_cell_list_view = subparameter_cell_list_view(self.__canvas, self.__object_id, self.__subobject_id
                                                                                ,self.__acm_data_handler
                                                                                ,self.__db
                                                                                ,self.__project_name
                                                                                , 0
                                                                                , 0
                                                                                ,subobject_type=self.__subobject_type
                                                                                ,library_parser=self.__library_parser
                                                                                ,parameters=self.__parameters
                                                                                ,redraw_callback=self.__redraw_callback
                                                                                ,tagname=self.__tagname
                                                                                ,subobject_name=self.__subobject_name
                                                                                ,subobject=self.__subobject
                                                                                ,goto_callback=self.__go_to_callback
                                                                                ,pending_transaction=self.__pending_transaction
                                                                                ,delete_pending_transaction_callback=self.__delete_pending_transaction_callback
                                                                                ,config=self.__config)
        
        if self.__document_selection_subscription_kwargs:
            self.__subparameter_cell_list_view.document_selection_subscription(self.__document_selection_subscription_selected
                                                                            ,**self.__document_selection_subscription_kwargs)


    def show_thinking(self):
        self.__subparameter_cell_list_view.show_thinking()


    def hide_thinking(self):
        self.__subparameter_cell_list_view.hide_thinking()
    

    def draw(self, x=0, y=0 ,width=None):
        self.__delete_elements()
        if width:
            self.__width = width
        else:
            width = self.__width
        if width is None and self.__width is None:
            width = 200

        x = self.__x + x 
        y = self.__y + y

        return self.__subparameter_cell_list_view.draw(8, y+4)
    

    def ignore_text(self, linked_text, parameter):
        if self.__subparameter_cell_list_view:
            self.__subparameter_cell_list_view.ignore_text(linked_text, parameter)

        
    

    def __delete_elements(self):
        self.__canvas.delete(self.__id)
        if self.__subparameter_cell_list_view is None:
            return 
        self.__subparameter_cell_list_view.hide()


    def hide(self):
        self.__delete_elements()

    
    def setup_linked_text(self,data,is_approved=False):
        self.__subparameter_cell_list_view.setup_linked_text(data,False,is_approved)


    def setup_regex_on_viewer(self):
        self.__subparameter_cell_list_view.setup_regex_on_viewer()


    def show_selection_on_viewer(self):
        self.__subparameter_cell_list_view.show_selection_on_viewer()


    def predicted_linked_text(self,processed_result):
        self.__subparameter_cell_list_view.predicted_linked_text(processed_result)

    def update_thinking_message_text(self, text):
        self.__subparameter_cell_list_view.update_thinking_message_text(text)

    def delete_linked_text(self):
        self.__subparameter_cell_list_view.delete_linked_text()

    def internal_db_linked_text_change_callback(self, linked_text_id):
        return self.__subparameter_cell_list_view.internal_db_linked_text_change_callback(linked_text_id)







class subparameter_cell_list_view:
    def __init__(self, canvas: tk.Canvas, object_id, subobject_id, acm_data_handler:ACM_Data_Handler, db:Database
                 , project_name=None, x=0, y=0,parameters=None , redraw_callback=None, tagname='',subobject_name='', subobject='',goto_callback=None
                 ,allow_adding_subparameters=True,draw_add_subparameters=True,pending_transaction=None,delete_pending_transaction_callback=None
                 ,config=None, subobject_type=None, library_parser=None) -> None:
        self.__canvas = canvas
        self.__object_id = object_id
        self.__subobject_id = subobject_id
        self.__subobject_type = subobject_type
        self.__library_parser = library_parser
        self.__acm_data_handler = acm_data_handler
        self.__config = config
        self.__thinking_animation = None
        self.__thinking_animation_text_id = None
        self.__thinking_animation_text = ''
        self.__thinking = False
        self.__opened = False
        self.__change_detected = False
        self.__thinking_animation = loading_animation(self.__canvas)
        self.__goto_callback_func = goto_callback
        self.__delete_pending_transaction_callback = delete_pending_transaction_callback
        self.__db = db
        self.__project_name = project_name
        self.__x = x
        self.__y = y
        self.y = 0
        self.__cell_size = 140
        self.__add_text = None 
        self.__predicted_output = False
        self.__allow_adding_locations = allow_adding_subparameters
        self.__allow_add_subparameters = draw_add_subparameters
        self.__draw_add_subparameters = True
        self.__show_add_parameter = True
        self.__subparameter_cells = {}
        self.__full_parameter_list = []
        self.__redraw_callback = redraw_callback
        self.__select_poly_callback = None
        self.__pending_transaction = pending_transaction
        self.__add_parameter_view = add_parameter_view(self.__canvas 
                                                        ,cancel_callback=self.__cancel_add_parameter
                                                        ,add_callback=self.__add_parameter
                                                        ,placeholder='Subparameter Name')
        self.__subparameters = parameters
        self.__build_parameters(self.__subparameters)
        self.__tagname = tagname
        self.__subobject_name = subobject_name
        self.__subobject = subobject
        self.__text_in_table = False
        self.__document_type = None 

        self.__tagname_entry = string_linked_text_entry(self.__canvas
                                                        ,get_text_link_callback=self.__get_tagname_linked_text
                                                        ,given_text_link_callback=self.__tagname_given_text_linked_callback
                                                        ,key_text_link_callback=self.__key_tagname_text
                                                        ,given_text_unlink_callback=self.__unlink_tagname_given_text
                                                        ,ignore_text_callback=self.__ignore_tagname_text
                                                        ,unignore_text_callback=self.__unignore_tagname_text
                                                        ,redraw_callback=self.__redraw_tagname_callback
                                                        ,goto_callback=self.__go_to_roi_tagname_linked_text
                                                        ,given_text_goto_callback=self.__go_to_roi_tagname_given_text
                                                        ,placeholder='Tagname Link'
                                                        )
        self.__tagname_entry.entry.insert(0,tagname)
        self.__tagname_entry.entry.config(state='readonly')
        
        
        self.__subobject_entry = string_linked_text_entry(self.__canvas
                                                        ,get_text_link_callback=self.__get_subobject_linked_text
                                                        ,given_text_link_callback=self.__subobject_given_text_linked_callback
                                                        ,key_text_link_callback=self.__key_subobject_text
                                                        ,given_text_unlink_callback=self.__unlink_subobject_given_text
                                                        ,ignore_text_callback=self.__ignore_subobject_text
                                                        ,unignore_text_callback=self.__unignore_subobject_text
                                                        ,redraw_callback=self.__redraw_subobject_callback
                                                        ,goto_callback=self.__go_to_roi_subobject_linked_text
                                                        ,given_text_goto_callback=self.__go_to_roi_subobject_given_text
                                                        ,placeholder='Subobject Link')
        
        self.__subobject_entry.entry.insert(0,subobject)
        self.__subobject_entry.entry.config(state='readonly')

        self.__done_or_accept_button = rectangle_canvas_button('Done',self.__canvas,self.__on_done_click)
        self.__reject_button = rectangle_canvas_button('Discard',self.__canvas,self.__on_reject_click)
        self.__single_reference_link_button = rectangle_canvas_button('Object Reference',self.__canvas
                                                                    ,self.__on_text_link_object_reference, width=120)
        self.__multiple_reference_link_button = rectangle_canvas_button('Custom Logic',self.__canvas
                                                                    ,self.__on_text_link_custom_logic, width=120)
        self.__object_type = self.__acm_data_handler.get_object_with_name(self.__tagname)['CatalogNumber'].iloc[0]
        self.__linked_text = Linked_Texts(acm_data_handler
                                          ,change_callback=self.__redraw_callback
                                          ,goto_callback=self.__goto_roi
                                          ,object_type=self.__object_type
                                          ,tagname=tagname
                                          ,subobject=self.__subobject
                                          ,db=db)
        
        
        self.__loading = False 
        self.__draw_done_button = True
        self.__regex_refresh_parameter = False
        self.__regex_refresh_entry_name = ''


    def __on_text_link_object_reference(self):
        self.__tagname_entry.on_given_text_link(self.__tagname_entry.get())
        parameter = 'ReferencedTag'
        self.__add_parameter(parameter, False, copy_tagname=False)
        parameter_entry = self.__subparameter_cells[parameter]['parameter_entry']
        parameter_entry.on_given_text_link()
        if self.__redraw_callback:
            self.__redraw_callback()


    def internal_db_linked_text_change_callback(self, linked_text_id):
        if self.__linked_text.get_id() == linked_text_id:
            linked_text = self.__db.get_approved_text_link_by_id(linked_text_id)
            if not linked_text:
                return True
            self.__loading = True
            self.__draw_done_button = False
            self.__linked_text.set_data(linked_text)
            self.__loading = False
            return True
        return False

    
    def __on_text_link_custom_logic(self):
        self.__tagname_entry.on_given_text_link(self.__tagname_entry.get())
        parameter = 'Custom_Referenced_Tag'
        self.__add_parameter(parameter, False, copy_tagname=False)
        parameter_entry = self.__subparameter_cells[parameter]['parameter_entry']
        parameter_entry.on_given_text_link()
        if self.__redraw_callback:
            self.__redraw_callback()

    def update_thinking_message_text(self, text):
        if self.__thinking_animation_text_id:
            self.__canvas.itemconfig(self.__thinking_animation_text_id, text=text)
            self.__thinking_animation_text = text


    def show_thinking(self):
        self.__thinking = True
        self.__thinking_animation_text = 'Thinking...'
        self.__canvas.bind("<Configure>", self.__center_thinking_animation, add='+')
        self.__center_thinking_animation()

        '''
        self.__tagname_entry.start_thinking()
        self.__subobject_entry.start_thinking()
        for _, parameter_cell in self.__subparameter_cells.items():
            parameter_cell['parameter_entry'].start_thinking()'''

    def __center_thinking_animation(self,_=None):
            if not self.__thinking:
                return
            if not self.__opened:
                return
            x = int(self.__canvas.winfo_width()/2)
            y = self.y
            
            self.__thinking_animation.hide()
            self.__thinking_animation.draw(x, y + 12)
            self.__canvas.delete(self.__thinking_animation_text_id)                
            self.__thinking_animation_text_id = self.__canvas.create_text(x, y + 36,
                                            text=self.__thinking_animation_text,
                                            fill="#6F6F6F",
                                            anchor=tk.CENTER,
                                            justify=tk.CENTER)
            _, y1, _, y2 = self.__canvas.bbox(self.__thinking_animation_text_id)
            self.__canvas.move(self.__thinking_animation_text_id, 0, int(abs(y1 - y2)/2))

    def hide_thinking(self):
        self.__thinking = False 
        self.__stop_thinking()

    def __stop_thinking(self):
        if self.__thinking_animation:
            self.__thinking_animation.hide()
            self.__canvas.delete(self.__thinking_animation_text_id)
            
        '''self.__tagname_entry.stop_thinking()
        self.__subobject_entry.stop_thinking()
        for _, parameter_cell in self.__subparameter_cells.items():
            parameter_cell['parameter_entry'].stop_thinking()'''


    def predicted_linked_text(self,processed_result):
        self.__pending_transaction = True
        if not processed_result:
            return
        parameter_result = processed_result['parameter_reference']
        tagname_result = processed_result['dependent_reference']

        if parameter_result['reference_type'] == 'object':
            parameter = 'ReferencedTag'
        else:
            parameter = 'Custom_Referenced_Tag'
        self.__add_parameter(parameter, False)

        
        _, tagname_given_text_id = self.__linked_text.set_tagname_given_text(tagname_result['given_text'])
        
        for key_text in tagname_result['key_texts']:
            self.__linked_text.set_key_tagname_text(True
                                                    ,[key_text[1][0],key_text[1][1]+1]
                                                    ,self.__tagname_entry.entry.get()
                                                    ,self.__tagname
                                                    ,None
                                                    ,[key_text[0][0],tagname_given_text_id,key_text[0][2]])
            
        for key_text in tagname_result['ignore_texts']:
            self.__linked_text.set_tagname_ignore_text(None,[tagname_given_text_id,key_text['indexes']])

        _, parameter_given_text_id = self.__linked_text.set_parameter_given_text(parameter, parameter_result['given_text'])
        
        parameter_entry = self.__subparameter_cells[parameter]['parameter_entry']
        parameter_entry.set_text(parameter_result['subparameter_text'])

        for key_text in parameter_result['key_texts']:
            self.__linked_text.set_key_parameter_text(True
                                                      ,[key_text[1][0],key_text[1][1]+1]
                                                      ,parameter_entry.entry.get()
                                                      ,parameter
                                                      ,None
                                                      ,[key_text[0][0],parameter_given_text_id,key_text[0][2]])
            
        for key_text in parameter_result['ignore_texts']:
            self.__linked_text.set_parameter_ignore_text(parameter,None,[parameter_given_text_id,key_text['indexes']])

        self.__regex_refresh_parameter = True
        self.__regex_refresh_entry_name = parameter 

        data = self.__linked_text.get_data()
        data['subobject_name'] = self.__subobject_name
        data['is_llm_generated'] = True
        self.__db.save_unapproved_text_link(data)
        self.__done_or_accept_button.change_text('Accept')




    def __redraw_tagname_callback(self, _=None):
        self.__regex_refresh_parameter = False 
        self.__regex_refresh_entry_name = 'tagname'
        self.__redraw_callback()


    def __redraw_subobject_callback(self, _=None):
        self.__regex_refresh_parameter = False 
        self.__regex_refresh_entry_name = 'subobject'
        self.__redraw_callback()


    def __redraw_parameter_callback(self, parameter):
        self.__regex_refresh_parameter = True 
        self.__regex_refresh_entry_name = parameter
        self.__redraw_callback()
    

    def __get_tagname_linked_text(self):
        return self.__linked_text.get_tagname_linked_text()
    

    def __tagname_given_text_linked_callback(self, _, option=None):
        return self.__linked_text.set_tagname_given_text(option=option)
    

    def __unlink_tagname_given_text(self, _, given_text_id):
        self.__linked_text.remove_highlights_on_viewer()
        self.__linked_text.unlink_tagname_given_text(given_text_id)

    
    def __key_tagname_text(self, linked, indexes, string, name, use_selection=True, text_view_indexes=None):
        if text_view_indexes:
            start, end, id = text_view_indexes
        elif use_selection:
            start, end, id = self.__tagname_entry.get_text_view_selection()
        else:
            start, end, id = self.__tagname_entry.get_full_text_view_selection()
        self.__tagname_entry.remove_text_view_selection()
        text,key_indexes,ignore_indexes, given_text_id = self.__linked_text.set_key_tagname_text(linked
                                                                                  , indexes
                                                                                  , string
                                                                                  , name
                                                                                  , [start,end,id])
        self.__tagname_entry.set_given_text(text, given_text_id)
        self.__tagname_entry.set_ignore_indexes(ignore_indexes)
        self.__tagname_entry.set_key_indexes(key_indexes)
        return linked_text_entry.TOP_SIDE
    

    def __ignore_tagname_text(self, _, ignore_text_view=False):
        if not ignore_text_view:
            start, end, id = self.__tagname_entry.get_text_view_selection()
            self.__tagname_entry.remove_text_view_selection()
        else:
            start, end, id = None, None, None
        text,key_indexes,ignore_indexes, given_text_id = self.__linked_text.set_tagname_ignore_text([start,end,id])

        self.__tagname_entry.set_given_text(text, given_text_id)
        self.__tagname_entry.set_ignore_indexes(ignore_indexes)
        self.__tagname_entry.set_key_indexes(key_indexes)
        self.__redraw_tagname_callback()


    def __unignore_tagname_text(self, _, ignore_text_view=False):
        if not ignore_text_view:
            start, end, id = self.__tagname_entry.get_text_view_selection()
            self.__tagname_entry.remove_text_view_selection()
        else:
            start, end, id = None, None, None
        text,key_indexes,ignore_indexes, given_text_id = self.__linked_text.unset_tagname_ignore_text([start,end,id])

        self.__tagname_entry.set_given_text(text, given_text_id)
        self.__tagname_entry.set_ignore_indexes(ignore_indexes)
        self.__tagname_entry.set_key_indexes(key_indexes)
        self.__redraw_tagname_callback()


    def __get_subobject_linked_text(self):
        return self.__linked_text.get_subobject_linked_text()
    

    def __subobject_given_text_linked_callback(self, _, __):
        return self.__linked_text.set_subobject_given_text()
    

    def __unlink_subobject_given_text(self,_,  given_text_id):
        self.__linked_text.unlink_subobject_given_text(given_text_id)

    
    def __key_subobject_text(self, linked, indexes, string, name, use_selection=True, text_view_indexes=None):
        if text_view_indexes:
            start, end, id = text_view_indexes
        elif use_selection:
            start, end, id = self.__subobject_entry.get_text_view_selection()
        else:
            start, end, id = self.__subobject_entry.get_full_text_view_selection()
        self.__subobject_entry.remove_text_view_selection()
        text,key_indexes,ignore_indexes, given_text_id = self.__linked_text.set_key_subobject_text(linked
                                                                                  , indexes
                                                                                  , string
                                                                                  , name
                                                                                  , [start,end,id])
        self.__subobject_entry.set_given_text(text, given_text_id)
        self.__subobject_entry.set_ignore_indexes(ignore_indexes)
        self.__subobject_entry.set_key_indexes(key_indexes)
        return linked_text_entry.TOP_SIDE
    

    def __ignore_subobject_text(self, _, ignore_text_view=False):
        if not ignore_text_view:
            start, end, id = self.__subobject_entry.get_text_view_selection()
            self.__subobject_entry.remove_text_view_selection()
        else:
            start, end, id = None, None, None
        text,key_indexes,ignore_indexes, given_text_id = self.__linked_text.set_subobject_ignore_text([start,end,id])

        self.__subobject_entry.set_given_text(text, given_text_id)
        self.__subobject_entry.set_ignore_indexes(ignore_indexes)
        self.__subobject_entry.set_key_indexes(key_indexes)
        self.__redraw_subobject_callback()

    def __unignore_subobject_text(self, _, ignore_text_view=False):
        if not ignore_text_view:
            start, end, id = self.__subobject_entry.get_text_view_selection()
            self.__subobject_entry.remove_text_view_selection()
        else:
            start, end, id = None, None, None
        text,key_indexes,ignore_indexes, given_text_id = self.__linked_text.unset_subobject_ignore_text([start,end,id])

        self.__subobject_entry.set_given_text(text, given_text_id)
        self.__subobject_entry.set_ignore_indexes(ignore_indexes)
        self.__subobject_entry.set_key_indexes(key_indexes)
        self.__redraw_subobject_callback()
    
    def ignore_text(self, linked_text, parameter):
        if linked_text == 'tagname':
            self.__ignore_tagname_text(None, ignore_text_view=True)
        if linked_text == 'subobject':
            self.__ignore_subobject_text(None, ignore_text_view=True)
        if linked_text == 'parameters':
            self.__ignore_parameter_text(parameter, ignore_text_view=True)

    
    def __go_to_linked_text(self,_,indexes_id,__):
        self.__linked_text.goto_tagname(indexes_id)

    
    def __go_to_roi_tagname_linked_text(self,_,indexes_id,__):
        self.__linked_text.goto_tagname(indexes_id)

    
    def __go_to_roi_subobject_linked_text(self,_,indexes_id,__):
        self.__linked_text.goto_subobject(indexes_id)


    def __go_to_roi_parameter_linked_text(self,_=None,indexes_id=None,parameter=None):
        self.__linked_text.goto_parameter(parameter,indexes_id)


    def __go_to_roi_tagname_given_text(self,_=None,given_text_id=None):
        self.__linked_text.goto_tagname_given_text(given_text_id)


    def __go_to_roi_subobject_given_text(self,_=None,given_text_id=None):
        self.__linked_text.goto_subobject_given_text(given_text_id)


    def __go_to_roi_parameter_given_text(self,parameter=None,given_text_id=None):
        self.__linked_text.goto_parameter_given_text(parameter,given_text_id)
  

    def __build_parameters(self, subparameters):
        for subparameter, data in subparameters.items():

            if data['ROnly'] == 'true':
                continue 
            
            if data['RType'] != 'Immediate' and data['RType'] != 'Reference': 
                continue 

            if subparameter not in self.__subparameter_cells:
                self.__full_parameter_list.append(subparameter)
        
        self.__update_autocomplete_add_parameter_entry()

    def __cancel_add_parameter(self):
        if self.__add_parameter_view:
            self.__add_parameter_view.hide()
        self.__show_add_parameter = False
        if self.__redraw_callback:
            self.__redraw_callback()


    def draw(self,x=0,y=0):
        x = self.__x + x 
        y = self.__y + y
        self.y = y

        increase = 0 

        self.__opened = True

        if self.__thinking:
            self.show_thinking()
            
        
        if (self.__linked_text.get_document_type() == Database.TABLE 
            or self.__document_type == Database.TABLE):
            text_view_height = self.__draw_table_linking_view(x, y)
            increase = increase + text_view_height
        else:
            text_view_height = self.__draw_text_document_linking_view(x, y)
            increase = increase + text_view_height
       
        if self.__config.get_show_advanced_linking():
            increase = increase + 140

        for _, views in self.__subparameter_cells.items():

            text_view_hieght = views['parameter_entry'].draw(8, increase + y+2)
            #self.__linked_text.draw_paramater_link_view(self.__canvas.winfo_width() - (30*3)
            #                                            ,increase + y
            #                                            ,parameter)
            increase = increase + text_view_hieght + 70

        ready_to_save = len(self.__subparameter_cells)>0 and self.__draw_done_button and self.__object_id is not None

        if ready_to_save:
            self.__done_or_accept_button.draw(self.__canvas.winfo_width() - 90, y + increase + 32)

        if ready_to_save and self.__pending_transaction is not False:
            self.__reject_button.draw(self.__canvas.winfo_width() - 155, y + increase + 32)


        if self.__allow_add_subparameters and self.__draw_add_subparameters:
            if not self.__show_add_parameter:
                self.__draw_add_button(x + 16, y + increase + 54)
            else:
                self.__delete_add_parameter()
                self.show_add_parameter_interface(x + 4, y + increase + 54)

        self.__draw_linked_text()
        if self.__select_poly_callback:
            self.__select_poly_callback(self.__linked_text.get_id())

        self.__cell_size = increase + 140

        
        return increase
    

    def __parse_library_file(self, project_name,acm_data_handler:ACM_Data_Handler):
        library_id = acm_data_handler.get_object_library_id(self.__tagname)
        library_file_path = get_library_file_path(library_id,project_name)
        if not library_file_path:
            projects_df = acm_data_handler.get_all_projects()
            acm_project_name = projects_df.loc[int(acm_data_handler.get_project_id())]['Name']
            acm_libraries_retrieval(project_name, acm_project_name,threaded=False)
            library_file_path = get_library_file_path(library_id,project_name)
        self.__library_parser = acm_library_parser(library_file_path)

    

    def accept(self):
        try:
            self.__parse_library_file(self.__project_name,self.__acm_data_handler)
            subobjects = self.__library_parser.get_all_subobjects()
            subobject_parameters = self.__library_parser.get_subobject_parameters(self.__subobject)
            object_id = self.__acm_data_handler.get_object_id(self.__tagname)
            subobject_parameters['Index']['Max'] = acm_parameter_handler(subobject_parameters['Index']['Max']
                              ,object_id
                              ,self.__acm_data_handler
                              ,self.__project_name)
            subobject_name = self.__acm_data_handler.create_subobject(object_id,subobjects[self.__subobject], subobject_parameters)
            subobject_id = self.__acm_data_handler.get_subobject_id(subobject_name,object_id)
        
            for subparameter, subparameter_cell in self.__subparameter_cells.items():
                subparameter_cell['acm_subparameter'].write_unknown_referenced_values(subparameter
                                                                                    ,subparameter_cell['parameter_entry'].get()
                                                                                    ,subobject_id)
            data = self.__linked_text.get_data()
            data['subobject_name'] = subobject_name
            self.__db.save_approved_text_link(data)
        except Exception as error:
            messagebox.showwarning("Unable to create new subobject",error)

    
    def __draw_table_linking_view(self, x, y):
        if self.__config.get_show_advanced_linking():
            tagname_entry_height = self.__tagname_entry.draw(8, y+4)
            subobject_entry_height = self.__subobject_entry.draw(8, y + 74 + tagname_entry_height)
            return tagname_entry_height + subobject_entry_height
        else:
            return 0

    def delete_linked_text(self):
        self.__db.delete_text_link(self.__linked_text.get_id())
    

    def __draw_text_document_linking_view(self, x, y):
        
        self.__draw_add_subparameters = True

        if not self.__linked_text.has_given_text() and not self.__subparameter_cells and not self.__thinking:
            self.__single_reference_link_button.draw(self.__canvas.winfo_width()/2 - 144,y + 100)
            self.__multiple_reference_link_button.draw(self.__canvas.winfo_width()/2 + 4,y + 100)
            return 140

        if self.__config.get_show_advanced_linking():
            tagname_entry_height = self.__tagname_entry.draw(8, y + 42)
            subobject_entry_height = self.__subobject_entry.draw(8, y + 118 + tagname_entry_height)
            return tagname_entry_height + subobject_entry_height + 50
        else:
            return 0

    def cell_size(self):
        return self.__cell_size


    def __draw_linked_text(self):
        tagname_linked_text = self.__linked_text.get_tagname_linked_text()
        if tagname_linked_text.links:
            for _, linked_text in tagname_linked_text.links.items():
                start = linked_text.target_text_indexes[0]
                end = linked_text.target_text_indexes[1]
                self.__tagname_entry.primary_link_text(start,end)


        subobject_linked_text = self.__linked_text.get_subobject_linked_text()
        if subobject_linked_text and subobject_linked_text.links:
            for _, linked_text in subobject_linked_text.links.items():
                start = linked_text.target_text_indexes[0]
                end = linked_text.target_text_indexes[1]
                self.__subobject_entry.primary_link_text(start,end)


        parameters = self.__linked_text.get_all_parameter_names()
        for parameter in parameters:
            parameter_linked_text = self.__linked_text.get_parameter_linked_text(parameter)
            if parameter_linked_text and parameter_linked_text.links:
                parameter_entry = self.__subparameter_cells[parameter]['parameter_entry']
                for _, linked_text in parameter_linked_text.links.items():
                    start = linked_text.target_text_indexes[0]
                    end = linked_text.target_text_indexes[1]
                    parameter_entry.primary_link_text(start,end)




    def __draw_add_button(self, x, y):
        padding = 8
        self.__delete_elements()
        
        x = self.__x + x # For static elements
        y = self.__y + y + padding # For static elements
        
        if self.__allow_adding_locations:
            self.__add_text = self.__canvas.create_text(x, y,  
                                                                text='+ Add subparameter ', 
                                                                font=('Arial',10,'normal'), 
                                                                anchor=tk.NW, 
                                                                fill="#505050")
        else:
            self.__add_text = self.__canvas.create_text(x, y,  
                                                                text='+ Add subparameter ', 
                                                                font=('Arial',10,'normal'), 
                                                                anchor=tk.NW, 
                                                                fill="#C0C0C0")
        bounds = self.__canvas.bbox(self.__add_text)
        self.__add_rect = self.__canvas.create_rectangle(bounds[0]-padding ,bounds[1] -padding,bounds[2]+ padding ,bounds[3]+ padding,fill='#FFFFFF', width = 0, tags=('add_text_location'))
        self.__canvas.tag_raise(self.__add_text)
        

        self.__canvas.tag_bind(self.__add_rect,'<Enter>', self.__on_add_enter)
        self.__canvas.tag_bind(self.__add_rect,'<Leave>', self.__on_add_leave)
        self.__canvas.tag_bind(self.__add_text,'<Enter>', self.__on_add_enter)
        self.__canvas.tag_bind(self.__add_text,'<Leave>', self.__on_add_leave)
        self.__canvas.tag_bind(self.__add_rect,'<Button-1>', self.__on_add_click)
        self.__canvas.tag_bind(self.__add_text,'<Button-1>', self.__on_add_click)

    def __delete_elements(self):
        
        if self.__add_text:
            self.__canvas.delete(self.__add_text)
            self.__canvas.delete(self.__add_rect)
        if self.__add_parameter_view:
            self.__add_parameter_view.hide()
            
        


    def hide_entry_widgets(self):

        if self.__tagname_entry:
            self.__tagname_entry.hide()

        if self.__subobject_entry:
            self.__subobject_entry.hide()

        for _, views in self.__subparameter_cells.items():
            views['parameter_entry'].hide()

        self.__linked_text.remove_highlight_linked_text()

        


    def show_entry_widgets(self):
        self.draw()


    def hide(self):
        self.__delete_elements()
        self.__linked_text.remove_highlights_on_viewer()
        self.__tagname_entry.hide()
        self.__subobject_entry.hide()
        self.__done_or_accept_button.hide()
        self.__single_reference_link_button.hide()
        self.__multiple_reference_link_button.hide()
        self.__reject_button.hide()
        self.__stop_thinking()
        for _, views in self.__subparameter_cells.items():
            views['parameter_entry'].hide()

        self.__opened = False
        



    def __delete_add_parameter(self):
        if self.__add_text:
            self.__canvas.delete(self.__add_text)
            self.__canvas.delete(self.__add_rect)


    def __on_add_enter(self,_):
        self.__canvas.itemconfig(self.__add_rect, fill='#E5E5E5')


    def __on_add_leave(self,_):
        self.__canvas.itemconfig(self.__add_rect, fill='#FFFFFF')

    def __on_add_click(self,_):
        if not self.__allow_adding_locations:
            return 
        
        self.__show_add_parameter = True 
        self.__add_parameter_view.clear_entry()
        if self.__redraw_callback:
            self.__redraw_callback()

    
    def show_add_parameter_interface(self, x, y):
        
        self.__add_parameter_view.draw(x,y)

    def __cancel_add_parameter(self):
        if self.__add_parameter_view:
            self.__add_parameter_view.hide()
        self.__show_add_parameter = False
        if self.__redraw_callback:
            self.__redraw_callback()


    def __update_autocomplete_add_parameter_entry(self):
        autocomplete_list = [ACM_Data_Handler.SUBOBJECT_DESCRIPTION]
        for parameter in self.__full_parameter_list:
            if parameter not in self.__subparameter_cells:
                autocomplete_list.append(parameter)

        self.__add_parameter_view.update_autocomplete(autocomplete_list)


    def __linked_text_entry(self, parameter_properties , parameter_name,value=None ,**kwargs):
        
        linked_entry_types = {
            'String': string_linked_text_entry,
            'Real': real_linked_text_entry,
            'Int': integer_linked_text_entry 
        }

        return linked_entry_types[parameter_properties['DType']](self.__canvas
                                                                        , parameter_properties
                                                                        , value=value
                                                                        , placeholder=parameter_name
                                                                        , is_parameter=True
                                                                        , **kwargs)

    def __linked_selector(self, parameter_properties, value=None, **kwargs):

        selector_types = {
            'String': linked_text_string_selector,
            'Int':linked_text_interger_selector,
            'Bool':linked_text_boolean_selector
        }

        return selector_types[parameter_properties['DType']](self.__canvas
                                                                    , parameter_properties
                                                                    , value=value
                                                                    , is_parameter=True
                                                                    , **kwargs)

    def __get_parameter_linked_text(self, parameter):
        return self.__linked_text.get_parameter_linked_text(parameter)
    

    def __parameter_given_text_linked_callback(self, parameter, _):
        return self.__linked_text.set_parameter_given_text(parameter)
    

    def __unlink_parameter_text(self, parameter):
        self.__linked_text.unlink_parameter(parameter)


    def __key_parameter_text(self, linked, indexes, string, subparameter, use_selection=True, text_view_indexes=None):
        if text_view_indexes:
            start, end, id = text_view_indexes
        elif use_selection:
            start, end, id = self.__subparameter_cells[subparameter]['parameter_entry'].get_text_view_selection()
        else:
            start, end, id = self.__subparameter_cells[subparameter]['parameter_entry'].get_full_text_view_selection()
        self.__subparameter_cells[subparameter]['parameter_entry'].remove_text_view_selection()
        text,key_indexes,ignore_indexes, given_text_id = self.__linked_text.set_key_parameter_text(linked
                                                                                    , indexes
                                                                                    , string
                                                                                    , subparameter
                                                                                    , [start,end,id])

        self.__subparameter_cells[subparameter]['parameter_entry'].set_given_text(text, given_text_id)
        self.__subparameter_cells[subparameter]['parameter_entry'].set_ignore_indexes(ignore_indexes)
        self.__subparameter_cells[subparameter]['parameter_entry'].set_key_indexes(key_indexes)
        return linked_text_entry.TOP_SIDE
    

    def __ignore_parameter_text(self, parameter,  ignore_text_view=False):
        if not ignore_text_view:
            start, end, id = self.__subparameter_cells[parameter]['parameter_entry'].get_text_view_selection()
            self.__subparameter_cells[parameter]['parameter_entry'].remove_text_view_selection()
        else:
            start, end, id = None, None, None
        text,key_indexes,ignore_indexes, given_text_id = self.__linked_text.set_parameter_ignore_text(parameter,[start,end,id])

        self.__subparameter_cells[parameter]['parameter_entry'].set_given_text(text, given_text_id)
        self.__subparameter_cells[parameter]['parameter_entry'].set_ignore_indexes(ignore_indexes)
        self.__subparameter_cells[parameter]['parameter_entry'].set_key_indexes(key_indexes)
        self.__redraw_parameter_callback(parameter)


    def __unignore_parameter_text(self, parameter,  ignore_text_view=False):
        if not ignore_text_view:
            start, end, id = self.__subparameter_cells[parameter]['parameter_entry'].get_text_view_selection()
            self.__subparameter_cells[parameter]['parameter_entry'].remove_text_view_selection()
        else:
            start, end, id = None, None, None
        text,key_indexes,ignore_indexes, given_text_id = self.__linked_text.unset_parameter_ignore_text(parameter,[start,end,id])

        self.__subparameter_cells[parameter]['parameter_entry'].set_given_text(text, given_text_id)
        self.__subparameter_cells[parameter]['parameter_entry'].set_ignore_indexes(ignore_indexes)
        self.__subparameter_cells[parameter]['parameter_entry'].set_key_indexes(key_indexes)
        self.__redraw_parameter_callback(parameter)
    

    def __unlink_parameter_given_text(self, pararmeter, given_text_id):
        self.__linked_text.unlink_parameter_given_text(pararmeter,given_text_id)


    def __add_parameter(self, subparameter, redraw=True, create_subparameter=True,copy_tagname=True):
        self.__loading = True 
        if subparameter == ACM_Data_Handler.SUBOBJECT_DESCRIPTION:
            subparameter_properties = {
                'Name': self.__acm_data_handler.SUBOBJECT_DESCRIPTION,
                'DType': 'String',
                'RType': 'Immediate',
                'CType': 'Text',
                'ROnly': 'false',
                'DVal': ''
            }

            subparameter_data = {'Value': self.__acm_data_handler.get_subobject_description(self.__subobject_id)}
        else:
            subparameter_properties = self.__subparameters[subparameter]
            subparameter_data = self.__get_subparameter_data(subparameter, subparameter_properties)

        acm_subparameter = acm_paramter(self.__object_id,self.__acm_data_handler,subparameter_properties,self.__project_name)
        
        options = []
        if subparameter_properties['CType'] == 'DropDownList' or subparameter_properties['CType'] == 'Bool':
            entry_view = self.__linked_selector(subparameter_properties
                                                , value=subparameter_data['Value']
                                                , id=subparameter
                                                ,selection_callback=self.__get_selector_text
                                                ,get_text_link_callback=self.__get_parameter_linked_text
                                                ,given_text_link_callback=self.__parameter_given_text_linked_callback
                                                ,given_text_unlink_callback=self.__unlink_parameter_given_text
                                                ,key_text_link_callback=self.__key_parameter_text
                                                ,goto_callback=self.__go_to_roi_parameter_linked_text
                                                ,given_text_goto_callback=self.__go_to_roi_parameter_given_text
                                                ,ignore_text_callback=self.__ignore_parameter_text
                                                ,unignore_text_callback=self.__unignore_parameter_text
                                                ,redraw_callback=self.__redraw_parameter_callback)
            parameter_type = 'selector'
        elif subparameter_properties['RType'] == 'Reference':
            options = acm_subparameter.get_all_reference_options()
            value = acm_subparameter.get_referenced_options(subparameter_data['RefType']
                                                    ,subparameter_data['Value']
                                                    ,subparameter_data['RefValue'])
            autocomplete_list = [x[0] for x in options]
            entry_view = self.__linked_text_entry(subparameter_properties,subparameter
                                                    ,autocompleteList=autocomplete_list
                                                    ,focus_out_callback=self.__get_referenced_linked_text
                                                    ,edit_callback=self.__edit_entry_callback
                                                    ,id=subparameter
                                                    ,value=value
                                                    ,get_text_link_callback=self.__get_parameter_linked_text
                                                    ,given_text_link_callback=self.__parameter_given_text_linked_callback
                                                    ,given_text_unlink_callback = self.__unlink_parameter_given_text
                                                    ,key_text_link_callback=self.__key_parameter_text
                                                    ,goto_callback=self.__go_to_roi_parameter_linked_text
                                                    ,given_text_goto_callback=self.__go_to_roi_parameter_given_text
                                                    ,ignore_text_callback = self.__ignore_parameter_text
                                                    ,unignore_text_callback=self.__unignore_parameter_text
                                                    ,redraw_callback=self.__redraw_parameter_callback)
            parameter_type = 'linked_entry'
            
        else:
            entry_view = self.__linked_text_entry(subparameter_properties,subparameter
                                                    ,focus_out_callback=self.__get_linked_text
                                                    ,edit_callback=self.__edit_entry_callback
                                                    ,id=subparameter
                                                    ,value=subparameter_data['Value']
                                                    ,get_text_link_callback=self.__get_parameter_linked_text
                                                    ,given_text_link_callback=self.__parameter_given_text_linked_callback
                                                    ,given_text_unlink_callback = self.__unlink_parameter_given_text
                                                    ,key_text_link_callback=self.__key_parameter_text
                                                    ,goto_callback=self.__go_to_roi_parameter_linked_text
                                                    ,given_text_goto_callback=self.__go_to_roi_parameter_given_text
                                                    ,ignore_text_callback = self.__ignore_parameter_text
                                                    ,unignore_text_callback=self.__unignore_parameter_text
                                                    ,redraw_callback=self.__redraw_parameter_callback)
        
            parameter_type = 'linked_entry'
            
        
        if create_subparameter:
            self.__linked_text.add_parameter(subparameter, subparameter_properties['DType'],copy_tagname)

        cell_views = {
            'parameter_entry' : entry_view,
            'parameter_type' : parameter_type,
            'acm_subparameter': acm_subparameter,
            'options': options
        }
        self.__subparameter_cells[subparameter] = cell_views 
        self.__update_autocomplete_add_parameter_entry()
        if self.__add_parameter_view:
            self.__add_parameter_view.hide()
        self.__show_add_parameter = False
        is_table_text = False
        if self.__document_type == Database.TABLE or self.__text_in_table:
            is_table_text = True
        self.__subparameter_cells[subparameter]['parameter_entry'].seletection_is_table_text(is_table_text)
        if self.__redraw_callback and redraw:
            self.__redraw_callback()

        self.__loading = False 



    def __get_subparameter_data(self, subparameter, subparameter_properties):
        
        if self.__subobject_id is None or self.__pending_transaction is True:
            
            subparameter_data = {
            'RefType': self.__acm_data_handler.get_reference_type_number(subparameter_properties['RType']),
            'Value': subparameter_properties['DVal'],
            'RefValue': ''
            }
        else:
            subparameter_data = self.__acm_data_handler.get_all_subparameters_in_subobject(self.__subobject_id,subparameter).iloc[0].to_dict()
        return subparameter_data
        

    def setup_linked_text(self, data, redraw=True, is_approved=False):
        
        self.__linked_text.set_data(data)
        self.__loading = True
        self.__draw_done_button = True if not is_approved else False
        self.__done_or_accept_button.change_text('Accept' if self.__linked_text.is_llm_generated() else 'Done')
        for parameter, parameter_data in data['parameters'].items():
            self.__add_parameter(parameter, redraw, create_subparameter=False)
            if (is_approved and 
                parameter_data['text'] != self.__subparameter_cells[parameter]['parameter_entry'].get()):
                self.__subparameter_cells[parameter]['parameter_entry'].error('ACM value does not match approved value'
                                                                              ,True)
            self.__subparameter_cells[parameter]['parameter_entry'].set_text(parameter_data['text'])
        self.__loading = False


    def __subobject_text_linked_callback(self, linked, indexes, string, name):
        return self.__linked_text.subobject_link(linked,indexes,string,name)

    
    def __tagname_text_linked_callback(self, linked, indexes, string, name):
        
        link_side, text_indexes = self.__linked_text.tagname_link(linked,indexes,string,name)

        if self.__linked_text.is_template_text_linked():
            self.__link_ignore_text_view.highlight_linked(text_indexes[0],text_indexes[-1]+1)

        return link_side


    def __parameter_text_linked_callback(self, linked, indexes, string, name):
        
        link_side, text_indexes = self.__linked_text.parameter_link(linked,indexes,string,name)

        if self.__linked_text.is_template_text_linked():
            self.__link_ignore_text_view.highlight_linked(text_indexes[0],text_indexes[-1]+1)
        
        return link_side


    def document_selection_subscription(self, selected , **kwargs):
        self.__selection_in_document_selected = selected

        self.__check_if_selection_in_document_made()
        if not kwargs:
            return 

        document_type = kwargs.get('document_type',Database.TEXT)

        if document_type != self.__document_type:
            self.__document_type = document_type
            self.__set_linked_entry_table_text_selection()
            dont_redraw = 'not_redraw' in kwargs and kwargs['not_redraw']
            if self.__redraw_callback and not dont_redraw:
                self.__redraw_callback()

        text_in_table =  kwargs.get('text_in_table',True)

        if self.__text_in_table != text_in_table:
            self.__text_in_table= text_in_table
            self.__set_linked_entry_table_text_selection()
            dont_redraw = 'not_redraw' in kwargs and kwargs['not_redraw']
            if self.__redraw_callback and not dont_redraw:
                self.__redraw_callback()

        self.__linked_text.setup_linking_callback_func(kwargs.get('roi_select_func',None), self.__document_type)
        self.__linked_text.setup_get_sheet_dataframe_func(kwargs.get('get_sheet_dataframe',None))
        self.__linked_text.setup_text_document_linking_funcs(
                                                    kwargs.get('given_text',None),
                                                    kwargs.get('ignore_text',None),
                                                    kwargs.get('remove_given_text',None)
                                                    )
        self.__select_poly_callback = kwargs.get('select_poly',None)
        self.__linked_text.setup_regex_show_funcs (
            kwargs.get('setup_regex_template',None),
            kwargs.get('remove_highlight_regex_template',None)
        )

        self.__linked_text.setup_linked_text_highlight_funcs (
            kwargs.get('setup_highlighted_linked_text',None),
            kwargs.get('remove_highlight_linked_text',None)
        )

        for _, subparameter_cell in self.__subparameter_cells.items():
            
            if selected:
                subparameter_cell['parameter_entry'].enable_linking()
            else:
                subparameter_cell['parameter_entry'].disable_linking()


    def __set_linked_entry_table_text_selection(self):
        is_table_text = False
        if self.__document_type == Database.TABLE or self.__text_in_table:
            is_table_text = True

        self.__tagname_entry.seletection_is_table_text(is_table_text)
        self.__subobject_entry.seletection_is_table_text(is_table_text)
        for _, subparameter_cell in self.__subparameter_cells.items():
            subparameter_cell['parameter_entry'].seletection_is_table_text(is_table_text)



    def __check_if_selection_in_document_made(self):
        if self.__selection_in_document_selected:
            #self.__linked_text.enable_linking()
            pass
        else:
            #self.__linked_text.disable_linking()
            pass


    def __ignore_linked_text(self):
        self.__linked_text.ignore_text_trigger()


    def __on_done_click(self):
        try:
            self.__linked_text.fully_linked_check()
        except Exception as e:
            messagebox.showwarning("Not fully linked",str(e))
            return
        self.__draw_done_button = False
        
        
        for subparameter,subparameter_cell in self.__subparameter_cells.items():
            self.__linked_text.parameters[subparameter].text = subparameter_cell['parameter_entry'].get()
            self.__get_referenced_linked_text(subparameter)

        # Handle pending transaction
        if self.__pending_transaction:
            self.__pending_transaction_write()
        else:
            self.__write_subparameter_values()
            
        self.__thread = threading.Thread(target=self.__create_other_linked_text)
        self.__thread.start()

        if self.__redraw_callback:
            self.__redraw_callback()


    def __on_reject_click(self):
        data = self.__linked_text.get_data()
        self.__db.save_rejected_text_link(data)


    def __pending_transaction_write(self):
        linked_text_data = self.__linked_text.get_data()
        
        subobjects = self.__library_parser.get_all_subobjects()
        subobject_parameters = self.__library_parser.get_subobject_parameters(self.__subobject_type)
        subobject_parameters['Index']['Max'] = acm_parameter_handler(subobject_parameters['Index']['Max']
                            ,self.__object_id
                            ,self.__acm_data_handler
                            ,self.__project_name)
        subobject_name = self.__acm_data_handler.create_subobject(self.__object_id,subobjects[self.__subobject_type], subobject_parameters)
        subobject_id = self.__acm_data_handler.get_subobject_id(subobject_name,self.__object_id)
        
        
        subparameters = list(linked_text_data['parameters'].keys())

        for subparameter in subparameters:
            
            subparameter_data = subobject_parameters[subparameter]
            acm_parameter = acm_paramter(self.__object_id,self.__acm_data_handler,subparameter_data,self.__project_name)
        
            acm_parameter.write_unknown_referenced_values(subparameter
                                                        ,linked_text_data['parameters'][subparameter]['text']
                                                        ,subobject_id)
        
        linked_text_data['subobject_name'] = subobject_name

        if linked_text_data['is_llm_generated']:
            linked_text_data['is_llm_generated'] = None
        self.__db.save_linked_text_regex(linked_text_data)
        self.__db.save_approved_text_link(linked_text_data)


    def __write_subparameter_values(self):
        for subparameter, subparameter_cell in self.__subparameter_cells.items():
            
            if 'selected_option' in  subparameter_cell and subparameter_cell['selected_option'] is not None:
                subparameter_cell['acm_subparameter'].write_reference_option(subparameter_cell['selected_option']
                                                                             ,subparameter,self.__subobject_id)
            else:
                parameter_text = subparameter_cell['parameter_entry'].get()
                subparameter_cell['acm_subparameter'].write_unknown_referenced_values(subparameter
                                                                                      ,parameter_text
                                                                                      ,self.__subobject_id)
                
        data = self.__linked_text.get_data()
        data['subobject_name'] = self.__subobject_name
        self.__db.save_approved_text_link(data)
        


    def __create_other_linked_text(self):
        doc_type = self.__linked_text.get_document_type()

        if doc_type == Database.TABLE:
            self.__linked_text.process_2D_referencing()
            self.__linked_text.process_1D_referencing()

        
        if doc_type == Database.TEXT:
            self.__linked_text.save_regex_linked_text()


    def __text_unlinked_callback(self, _):
        self.__linked_text.reset()
        self.__redraw_callback()

    def setup_regex_on_viewer(self):
        if self.__linked_text.get_id() is not None:
            self.__linked_text.highlight_linked_text_on_doc_viewer()
        else:
            if not self.__regex_refresh_parameter:
                if self.__regex_refresh_entry_name == 'tagname':
                    self.__linked_text.setup_tagname_regex_on_viewer()
                if self.__regex_refresh_entry_name == 'subobject':
                    self.__linked_text.setup_subobject_regex_on_viewer()
            elif self.__regex_refresh_entry_name in self.__subparameter_cells:
                self.__linked_text.setup_parameter_regex_on_viewer(self.__regex_refresh_entry_name)
            


    def __goto_roi(self, roi, page_number, path, doc_type):    
        if self.__goto_callback_func:
            self.__goto_callback_func(roi,page_number,path,doc_type)

    
    def __text_linked_callback(self):
        pass


    def __edit_entry_callback(self, subparameter, text):
        if self.__loading:
            return 
        self.__update_reference_autocomplete(subparameter , text)

        if text and self.__linked_text.parameters[subparameter].text != text:
            self.__draw_done_button = True
            if self.__redraw_callback:
                self.__redraw_callback()
            


    def __update_reference_autocomplete(self,subparameter, text:str):

        options = self.__subparameter_cells[subparameter]['acm_subparameter'].get_all_reference_options(text)
        previous_options = self.__subparameter_cells[subparameter]['options']

        if options == previous_options:
            return

        self.__subparameter_cells[subparameter]['options'] = options
        autocomplete_list = [x[0] for x in options]
        self.__subparameter_cells[subparameter]['parameter_entry'].update_autocomplete_list(autocomplete_list,True)



    def __get_referenced_linked_text(self, subparameter):
        selection = self.__subparameter_cells[subparameter]['parameter_entry'].entry.get()
        selection = selection.lower()
        self.__save_refType(selection, subparameter)
        

    def __save_refType(self, selection, subparameter):
        options = self.__subparameter_cells[subparameter]['options']
        list_options = [i[0].lower() for i in options]
        if selection == '' or (selection not in list_options):
            self.__subparameter_cells[subparameter]['selected_option'] = None
            self.__linked_text.set_parameter_ref_type(subparameter,None)
        else:
            option = options[list_options.index(selection)]
            self.__subparameter_cells[subparameter]['selected_option'] = option
            self.__linked_text.set_parameter_ref_type(subparameter,option[1])



    def __get_linked_text(self, subparameter):
        selection = self.__subparameter_cells[subparameter]['parameter_entry'].entry.get()
        


    def __get_selector_text(self, selection, id):
        print(selection)
        if selection and self.__linked_text.parameters[subparameter].text != selection:
            self.__draw_done_button = True
            if self.__redraw_callback:
                self.__redraw_callback()
    



if __name__ == "__main__":

    root = tk.Tk()
    canvas = tk.Canvas(root, bg="white", height=800, width=300)


    b = subobject_parameter_list_view(canvas,selected_subobject_dict={"Cfg_Hi":True, "Cfg_HiHi":True},
                                full_subobject_dict={"Cfg_Hi":True,"Cfg_HiHi":True,"test_1":True})

    def draw(_):
        b.draw(width=canvas.winfo_width())

    canvas.bind('<Configure>',draw)


    canvas.pack()
    root.mainloop()
