


import tkinter as tk
from tkinter import *
from tkinter import ttk
from tkinter import font
from PIL import Image, ImageTk, ImageDraw
from io import BytesIO
import base64
import time 
import os
from threading import Timer
import sys


try:
    from bin.gui_scan_progress_banner import banner_handler
    from bin.logic_internal_database import Database
    from bin.gui_warning_banner import warning_banner
    from bin.logic_profile import profile
except:
    from gui_scan_progress_banner import banner_handler
    from logic_internal_database import Database
    from gui_warning_banner import warning_banner


try:
    from .gui_autoscrollbar import AutoScrollbar
    from .gui_base64_icons import position_dark_gray, reposition, empty_image, loading_animation_images
except ImportError as error:
    from gui_autoscrollbar import AutoScrollbar
    from gui_base64_icons import position_dark_gray, reposition, empty_image, loading_animation_images


_ACTIVE_CANVAS_SCREEN = '_spa_active_screen'


def set_active_canvas_screen(canvas, screen):
    """Records which view currently owns a shared canvas."""
    setattr(canvas, _ACTIVE_CANVAS_SCREEN, screen)


def is_active_canvas_screen(canvas, screen):
    """False once another view has taken the canvas, so stale deferred redraws can bail out."""
    if screen is None:
        return True
    return getattr(canvas, _ACTIVE_CANVAS_SCREEN, None) is screen


class hover_toggle_button(tk.Button):
    def __init__(self, master, on_image_data, off_image_data, inactive_image_data=None, is_active=True, is_toggle=True,callback = None, tool_tip_text=None,tool_tip_anchor=tk.NE, **kw):
        tk.Button.__init__(self,master=master,relief='flat',command=self.__callback,bd=0,background='white',**kw)
        self.callback = callback
        self.is_toggle = is_toggle
        self.is_active = is_active
        self.is_on = False
        self.button_id = ""
        self.off_image_data = off_image_data
        off_image = tk.PhotoImage(data=off_image_data)
        self.off_image = off_image
        self.on_image_data = on_image_data
        on_image = tk.PhotoImage(data=on_image_data)
        self.on_image = on_image
        inactive_image = None
        if inactive_image_data is not None:
            inactive_image = tk.PhotoImage(data=inactive_image_data)
            self.inactive_image = inactive_image
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<ButtonPress>", self.on_leave)
        self.config(image=self.off_image)
        if not self.is_active:
            self.disable()
        self.tw = None
        self.id = None
        self.tool_tip_text = tool_tip_text
        self.tool_tip_anchor = tool_tip_anchor

    def update_on_image(self, on_image_data):
        self.on_image_data = on_image_data
        self.on_image = tk.PhotoImage(data=on_image_data)
        self.update_images()

    def update_off_image(self, off_image_data):
        self.off_image_data = off_image_data
        self.off_image = tk.PhotoImage(data=off_image_data)
        self.update_images()

    def update_inactive_image(self, inactive_image_data):
        self.inactive_image_data = inactive_image_data
        self.inactive_image = tk.PhotoImage(data=inactive_image_data)
        self.update_images()

    def on_enter(self, e):
        self.schedule()
        if self.is_active:
            self.config(image=self.on_image)

    def on_leave(self, e):
        self.unschedule()
        self.hidetip()
        if not self.is_on and self.is_active:
            self.config(image=self.off_image)

    def schedule(self):
        self.unschedule()
        self.id = self.after(1000, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.after_cancel(id)

    def showtip(self, event=None):
        if self.tool_tip_text:
            x = y = 0
            x, y, cx, cy = self.bbox("insert")
            x += self.winfo_rootx()
            y += self.winfo_rooty() + 20
            # creates a toplevel window
            self.tw = tk.Toplevel(self)
            # Leaves only the label and removes the app window
            f = font.nametofont('TkTextFont')
            length = f.measure(self.tool_tip_text)
            self.tw.wm_overrideredirect(True)
            if self.tool_tip_anchor == tk.NE:
                x = x + 30
                self.tw.wm_geometry("+%d+%d" % (x , y))
                
            else:
                self.tw.wm_geometry("+%d+%d" % (x - length , y))
                
            
            label = tk.Label(self.tw, text=self.tool_tip_text, justify='left',
                        background="#ffffff", relief='solid', borderwidth=1)
            label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw= None
        if tw:
            tw.destroy()
        
    def disable(self):
        self.is_active = False
        self.is_on = False
        self["state"] = "disabled"
        self.config(image=self.inactive_image)
        
    def enable(self):
        self.is_active = True
        self.is_on = False
        self["state"] = "normal"
        self.config(image=self.off_image)
        
    def set(self):
        if self.is_active:
            self.is_on = True
            self.config(image=self.on_image)
        
    def reset(self):
        if self.is_active:
            self.is_on = False 
            self.config(image=self.off_image)  
            
    def update_images(self):
        if self.is_active and self.is_on:
            self.config(image=self.on_image) 
        elif self.is_active:
            self.config(image=self.off_image) 
        else:
            self.config(image=self.inactive_image) 
        
    def __callback(self):
        if self.is_active:
            if self.is_on and self.is_toggle:
                self.is_on = False 
                self.config(image=self.off_image)
            elif self.is_toggle :
                self.is_on = True
                self.config(image=self.on_image)
        
            if self.callback:
                self.callback(self.button_id, self.is_on)
                
class option_button(hover_toggle_button):
    def __init__(self, canvas, on_image_data, off_image_data, inactive_image_data=None, callback = None,**kw):
        var = StringVar(canvas)
        self.canvas = canvas
        var.set("one") # initial value
        hover_toggle_button.__init__(self.canvas, on_image_data, off_image_data, inactive_image_data=None, is_toggle=False,callback = self.callback, **kw)
 
    def callback(self):
        self.frame = tk.Frame(width=100, height=100, relief='flat')
                    
        self.frame.place(x=self.canvas.canvasx(self.winfo_x()), y=self.canvas.canvasy(self.winfo_y() + self.winfo_height()+ 7))
 
class button_array:
    def __init__(self, array_buttons, callback=None):
        self.array_buttons = array_buttons
        self.callback = callback
        self.id = -1
        for i in range(len(self.array_buttons)):
            self.array_buttons[i].callback = self.button_callback
            self.array_buttons[i].button_id = i
            
    def select(self, index, silent=False):
        self.id = index
        for i in range(len(self.array_buttons)):
            if index != i:
                self.array_buttons[i].reset() 
        self.array_buttons[index].set()
        if silent: return
        self.callback(index)
        
        
    def button_callback(self, id, value):
        
        for i in range(len(self.array_buttons)):
            if id != i:
                self.array_buttons[i].reset() 
            else:
                self.array_buttons[i].set()
        self.callback(id) 

    def remove_selection(self):
        for i in range(len(self.array_buttons)):
            self.array_buttons[i].reset() 
            
            
    def restore_selection(self, selection):
        self.array_buttons[selection].set()

    def get_selected_button(self):
        
        for i in range(len(self.array_buttons)):
            if self.array_buttons[i].is_on:
                return i
        return None


    def get_buttons(self):
        return self.array_buttons
                
    
class tree_view(ttk.Treeview):
    
    
    def __init__(self, root, **kw):
        
        self.image_dict = {}

        self.__popup_func = None
        self.__single_click_func = None
        self.__double_click_func = None

        ttk.Treeview.__init__(self,root, **kw)
        self.menu = tk.Menu(root, tearoff=0)
        self.menu.add_command(label='Delete')
        self.menu.add_command(label='Say Hello')

        self.bind("<Button-3>", self.__popup)
        self.bind("<ButtonRelease-1>", self.__on_single_click)
        self.bind("<Double-1>", self.__on_double_click)
        
        
    def insert_with_icon(self, parent, index, image_data, text='', **kw):
        if image_data in self.image_dict:
            return self.insert(parent,index,image=self.image_dict[image_data], text='  '+text,**kw)
        else:
            self.image_dict[image_data] = tk.PhotoImage(data=image_data)
            return self.insert(parent,index,image=self.image_dict[image_data], text='  '+text,**kw)
            
        
    def __popup(self, event):
        """action in event of button 3 on tree view"""
        # select row under mouse
        iid = self.identify_row(event.y)
        if iid:
            # mouse pointer over item
            self.selection_set(iid)
            #self.menu.post(event.x_root, event.y_root)
            if self.__popup_func is not None:
                self.__popup_func(iid, event)
        else:
            # mouse pointer not over item
            # occurs when items do not fill frame
            # no action required
            pass

    def show_popup_func(self, func):
        self.__popup_func = func


    def __on_single_click(self, event):
        item = self.identify_row(event.y)
        if item:
            text =  self.item(item,"text")
            values =  self.item(item,"values")
            
            if self.__single_click_func is not None:
                self.__single_click_func(item, text, values)

            
    def __on_double_click(self, event):
        if self.selection():
            item = self.selection()[0]
            text =  self.item(item,"text")
            values =  self.item(item,"values")
            

            if self.__double_click_func is not None:
                self.__double_click_func(item, text, values)


    def single_click_func(self, func):
        self.__single_click_func = func

    def double_click_func(self, func):
        self.__double_click_func = func

    


        
        
def analyseImage(data):
    '''
    Pre-process pass over the image to determine the mode (full or additive).
    Necessary as assessing single frames isn't reliable. Need to know the mode 
    before processing all frames.
    '''
    im = Image.open(BytesIO(base64.b64decode(data)))
    results = {
        'size': im.size,
        'mode': 'full',
    }
    try:
        while True:
            if im.tile:
                tile = im.tile[0]
                update_region = tile[1]
                update_region_dimensions = update_region[2:]
                if update_region_dimensions != im.size:
                    results['mode'] = 'partial'
                    break
            im.seek(im.tell() + 1)
    except EOFError:
        pass
    return results
                
class animated_hover_button(tk.Button):
    """
    Class to show animated GIF file in a button
    Use start() method to begin animation, and set the stop flag to stop it
    """
    def __init__(self, root, png_file_data, off_image_data, inactive_image_data=None, delay=0.04, callback = None, **kw):
        """
        :param root: tk.parent
        :param gif_file: filename (and path) of animated gif
        :param delay: delay between frames in the gif animation (float)
        """
        tk.Button.__init__(self, root,relief='flat',command=self.callback,bd=0,**kw,background='white')
        self.root = root
        self.is_active = True
        self.callback = callback
        self.png_files = png_file_data
        off_image = tk.PhotoImage(data=off_image_data)
        self.off_image = off_image
        inactive_image = None
        if inactive_image_data is not None:
            inactive_image = tk.PhotoImage(data=inactive_image_data)
            self.inactive_image = inactive_image
        self.delay = delay  # Animation delay - try low floats, like 0.04 (depends on the gif in question)
        self.stop = False  # Thread exit request flag
        self.started = False
        self.config(image=self.off_image)
        self._num = 0
        
        self.frames = []

        for i in range(len(self.png_files)):
                
            
                self.frames.append(tk.PhotoImage(data=self.png_files[i]))


    def start(self):
        """ Starts non-threaded version that we need to manually update() """
        self.start_time = time.time()  # Starting timer
        if not self.started:
            self.started = True
            self.stop = False
            self._animate()

    def stop(self):
        """ This stops the after loop that runs the animation, if we are using the after() approach """
        self.stop = True
        self.started = False
        self.config(image=self.off_image)

    def _animate(self):
        if self._num < len(self.frames) and not self.stop:
            #gif = BytesIO(base64.b64decode(self.gif_file))
            #self.gif = ImageTk.PhotoImage(gif, format='gif -index {}'.format(self._num))  # Looping through the frames
            self.configure(image=self.frames[self._num])
            self._num += 1
        else:  # When we try a frame that doesn't exist, we know we have to start over from zero
            self._num = 0
        if not self.stop:    # If the stop flag is set, we don't repeat
            self.root.after(int(self.delay*1000), self._animate)

    def start_thread(self):
        """ This starts the thread that runs the animation, if we are using a threaded approach """
        from threading import Thread  # We only import the module if we need it
        self._animation_thread = Thread()
        self._animation_thread = Thread(target=self._animate_thread).start()  # Forks a thread for the animation

    def stop_thread(self):
        """ This stops the thread that runs the animation, if we are using a threaded approach """
        self.stop = True
        self.started = False
        self.config(image=self.off_image)
        

    def _animate_thread(self):
        """ Updates animation, if it is running as a separate thread """
        while self.stop is False:  # Normally this would block mainloop(), but not here, as this runs in separate thread
            try:
                time.sleep(self.delay)
                self.gif = tk.PhotoImage(file=self.gif_file, format='gif -index {}'.format(self._num))  # Looping through the frames
                self.configure(image=self.gif)
                self._num += 1
            except tk.TclError:  # When we try a frame that doesn't exist, we know we have to start over from zero
                self._num = 0
            except RuntimeError:
                sys.exit() 

    def disable(self):
        self.is_active = False
        self["state"] = "disabled"
        self.config(image=self.inactive_image)
        self.stop_thread() 
        
    def enable(self):
        self.is_active = True
        self["state"] = "normal"
        self.stop_thread()                
    
    def callback(self):
        if self.is_active:
            self.is_on = False 
            self.start()
            
        
            if self.callback:
                self.callback()

class expandable_list_canvas_header:

    DEFAULT_CELL_HEIGHT = 50

    def __init__(self, canvas, id, name, data_frame, cell_class, configure_canvas, resize_callback
                    ,cell_highlighted_callback=None, cell_unhighlighted_callback=None):
        self.canvas = canvas
        self.configure_canvas = configure_canvas
        self.y = 0
        self.id = id
        self.name = name
        self.callback = resize_callback
        self.shown = False
        self.rect = None 
        self.title = None
        self.expanded_element = None
        self.highlighted_element = None
        self.nummber_of_items = None
        self.show_or_hide_image = None
        self.elements_created = False
        self.cell_class = cell_class
        self.data_frame = data_frame
        im_open = Image.new('RGBA', (15, 15), '#00000000')
        draw = ImageDraw.Draw(im_open)
        draw.line([(0, 4), (7, 11), (14, 4) ], fill=(150,150,150,255),width=2)
        im_close= im_open.rotate(90)
        self.__cell_pass_document_selection_subscription_func = None
        self.__document_selection_subscription = None
        self.__multi_select_start = ''
        self.img_open = ImageTk.PhotoImage(im_open)
        self.img_close = ImageTk.PhotoImage(im_close)
        self.elements = {}
        self.__db = None 
        self.__acm_data_handler = None
        self.__document_selected_func = None 
        self.__add_primary_progress_callback = None 
        self.__add_secondary_progress_callback = None 
        self.__add_background_task_callback = None 
        self.__remove_background_task_callback = None 
        self.__get_object_if_running_func = None
        self.__cell_highlighted_callback_func = cell_highlighted_callback
        self.__cell_unhighlighted_callback_func = cell_unhighlighted_callback
        self.__cells_to_highlight = []



    def setup_data_handler(self, data_handler):
        self.__acm_data_handler = data_handler

    def document_selected_func(self, func):
        self.__document_selected_func = func


    def add_primary_progress_callback(self, func):
        self.__add_primary_progress_callback = func


    def add_secondary_progress_callback(self, func):
        self.__add_secondary_progress_callback = func
    

    def add_background_task_callback_func(self, func):
        self.__add_background_task_callback = func

    def remove_background_task_callback_func(self, func):
        self.__remove_background_task_callback = func

    def get_object_if_running_func(self, func):
        self.__get_object_if_running_func = func

    def setup_project(self, project_name, database, config):
        self.__project_name = project_name
        self.__db:Database = database
        self.__config = config

    def pass_document_selection_subscription(self, subscription=None):
        if subscription != None:
            self.__document_selection_subscription = subscription
            if self.__cell_pass_document_selection_subscription_func:
                self.__cell_pass_document_selection_subscription_func(subscription)
            
        else:
            if self.__document_selection_subscription and self.__cell_pass_document_selection_subscription_func:
                self.__cell_pass_document_selection_subscription_func(self.__document_selection_subscription)
        


        
    
    def draw(self, y):
        self.y = y
        self.rect = self.canvas.create_rectangle(8, self.y, self.canvas.winfo_width(), self.y + 50, tags=('header',self.id),fill="#E3E3E3",outline="#E3E3E3")
        self.title = self.canvas.create_text(16,y + 16, text=self.name, anchor=tk.NW, tags=('header',self.id))
        if 'IsLinked' in self.data_frame.columns and self.id != 'Unassigned':
            
            linked_count = len(self.data_frame[self.data_frame['IsLinked'] == True])
            linked_count_text = "Linked " +str(linked_count) + "/" + str(len(self.data_frame.index))
            self.nummber_of_items = self.canvas.create_text(self.canvas.winfo_width() - 40,y + 16, text=linked_count_text, anchor=tk.NE, tags=('header',self.id))
        else:
            self.nummber_of_items = self.canvas.create_text(self.canvas.winfo_width() - 40,y + 16, text=str(len(self.data_frame.index)), anchor=tk.NE, tags=('header',self.id))
        self.show_or_hide_image = self.canvas.create_image(self.canvas.winfo_width() - 8, y + 16, image=self.img_close, anchor = tk.NE, tags=('header',self.id))
       
        if not self.shown:
            self.canvas.itemconfigure(self.show_or_hide_image,image=self.img_close)
            self.remove_elements()
        else:
            self.canvas.itemconfigure(self.show_or_hide_image,image=self.img_open)
            self.redraw_elements()
            
    def redraw_elements(self):
        self.remove_elements()
        self.__cell_pass_document_selection_subscription_func = None
        y = self.y + 51
        for cell_id, values in self.elements.items():
            cell_height = self.DEFAULT_CELL_HEIGHT
            cell_color = 'white'
            cell_expanded = False
            if self.expanded_element:
                if self.expanded_element == cell_id:
                    if self.elements[cell_id]["cell"]:
                        cell_height = self.elements[cell_id]["cell"].cell_size()
                    else:
                        cell_height = 200
                    cell_color = '#FFFFFF'  
                    cell_expanded = True
            if self.elements[cell_id]["cell"]:
                self.elements[cell_id]["cell"].draw(y)
                if cell_expanded:
                    if self.__acm_data_handler:
                        self.elements[cell_id]["cell"].setup_data_handler(self.__acm_data_handler)
                    if self.__db:
                        self.elements[cell_id]["cell"].setup_project(self.__project_name,self.__db,self.__config)
                    self.elements[cell_id]["cell"].expand()
                    self.elements[cell_id]["cell"].document_selected_func(self.__document_selected_func)
                    self.elements[cell_id]["cell"].primary_progress_callback_func(self.__add_primary_progress_callback)
                    self.elements[cell_id]["cell"].secondary_progress_callback_func(self.__add_secondary_progress_callback)
                    self.elements[cell_id]["cell"].add_background_task_callback_func(self.__add_background_task_callback)
                    self.elements[cell_id]["cell"].remove_background_task_callback_func(self.__remove_background_task_callback)
                    self.__cell_pass_document_selection_subscription_func = self.elements[cell_id]["cell"].pass_document_selection_subscription_func
                    self.pass_document_selection_subscription()
                    if self.configure_canvas:
                        self.elements[cell_id]["cell"].setup_configure_canvas(self.configure_canvas)
           
            self.elements[cell_id]["line"] = self.canvas.create_line(16, y + cell_height,  self.canvas.winfo_width(), y + cell_height, fill="#E3E3E3",width=2)

            y = y + cell_height
        return (self.y , y)
            
    def remove_elements(self):
        for key, values in self.elements.items():
            if "line" in values:
                #self.canvas.delete(values['rect'])
                self.canvas.delete(values['line'])
                if values['cell']:
                    values['cell'].delete()
                #del self.elements[key]['rect'] 
                del self.elements[key]['line'] 
    
    def delete_on_canvas(self):
        if self.rect:
            self.canvas.delete(self.rect)
            
        if self.title:   
            self.canvas.delete(self.title)
        
        if self.show_or_hide_image:
            self.canvas.delete(self.show_or_hide_image)
            
        if self.nummber_of_items:   
            self.canvas.delete(self.nummber_of_items)
        
    
    def show_or_hide(self, hide=None):
        self.canvas.config(cursor="wait")
        if not self.elements_created:
            for sub_index, row in self.data_frame.iterrows():

                if 'IsLinked' in self.data_frame.columns:
                    self.insert_element( str(sub_index), 
                                        row['Name'], 
                                        row['Type'],
                                        row['ChangeUser'], 
                                        row['Description'],
                                        self.cell_class,
                                        row['IsLinked'],
                                        row['AssignmentID'],
                                        row['Catalog'])
                else:
                    self.insert_element( str(sub_index), 
                                        row['Name'], 
                                        None,
                                        row['ChangeUser'], 
                                        row['Description'],
                                        self.cell_class)

            self.elements_created = True
        
        if hide is None:
            hide = self.shown

        if  hide:
            self.canvas.itemconfigure(self.show_or_hide_image,image=self.img_close)
            self.shown = False
            self.expanded_element = None
            self.hide_elements()
        else:
            self.canvas.itemconfigure(self.show_or_hide_image,image=self.img_open)
            self.shown = True 
            self.show_elements()
        self.canvas.config(cursor="")
        return self.shown


    def select_cell_list(self, cell_list):

        selected_cells = []

        for data in self.elements.values():
            if (data["cell"] and 
                (data['cell'].primary_linked_graphic_roi_name in cell_list
                 or data['cell'].secondary_linked_graphic_roi_name in cell_list)):
                selected_cells.append(data["cell"])

        # Check to see if cells already exist
        in_memory_cells = list(set(cell_list).intersection(list(self.elements.keys())))

        for cell_id in list(set(in_memory_cells)):
            selected_cells.append(self.elements[cell_id]["cell"])

        # Filter the list to only include existing index labels
        not_in_memory_cells = [label for label in cell_list if label in self.data_frame.index]

        # Select rows using the filtered list of index labels
        selected_rows = self.data_frame.loc[list(set(not_in_memory_cells))]

        for sub_index, row in selected_rows.iterrows():
            if (self.cell_class and str(sub_index) not in in_memory_cells and
                self.__get_object_if_running_func(str(sub_index)) is None):
                    called_cell_class = self.cell_class(self.canvas,self.id, str(sub_index)
                                                    ,name=row['Name']
                                                    ,username=row['ChangeUser']
                                                    ,description=row['Description']
                                                    ,cell_highlighted_callback=self.__highlight_element
                                                    ,cell_unhighlighted_callback=self.__unhighlight_element)
                    
                    selected_cells.append(called_cell_class)

        return selected_cells
                    
         

    def insert_element(self, cell_id, name, acm_type, user, description, cell_class, is_linked=True, assignment_id='', assigned_type=''):

        called_cell_class = None 
    
        if cell_class:
            if self.__get_object_if_running_func(cell_id) is not None:
                called_cell_class = self.__get_object_if_running_func(cell_id)
            else:
                if acm_type is None:
                    acm_type = self.id
                called_cell_class = cell_class(self.canvas,acm_type, cell_id
                                                    ,name=name
                                                    ,username=user
                                                    ,description=description

                                                    ,is_linked=is_linked
                                                    ,assignment_id=assignment_id
                                                    ,assigned_type=assigned_type

                                                    ,cell_highlighted_callback=self.__highlight_element
                                                    ,cell_unhighlighted_callback=self.__unhighlight_element)
        
        self.elements[cell_id] = {
                                "name":name,
                                "user":user,
                                "cell":called_cell_class,
                                "type":'cell',
                                "is_linked":is_linked
                            }
        if self.shown:
            self.show_elements()
            
    def expand_element(self,element_id):
        self.expanded_element = element_id
        self.show_elements()

    def multi_select(self, cell_id):
        self.clear_multi_select(False)
        if not self.__multi_select_start: 
            self.__multi_select_start = cell_id
            self.elements[cell_id]["cell"].multi_select_highlight()
            return

        cell_key_list = list(self.elements.keys())

        start = cell_key_list.index(self.__multi_select_start)
        end = cell_key_list.index(cell_id)

        if start < end:
            self.__cells_to_highlight = cell_key_list[start: end + 1]
        else:
            self.__cells_to_highlight = cell_key_list[end: start + 1]
        
        for cell_id in self.__cells_to_highlight:
            cell = self.elements[cell_id]["cell"]
            cell.multi_select_highlight()
            if self.__acm_data_handler:
                cell.setup_data_handler(self.__acm_data_handler)
            if self.__db:
                cell.setup_project(self.__project_name,self.__db,self.__config)


    def single_multi_select(self, cell_id):
        self.__cells_to_highlight.append(cell_id)
        cell = self.elements[cell_id]["cell"]
        cell.multi_select_highlight()
        if self.__acm_data_handler:
            cell.setup_data_handler(self.__acm_data_handler)
        if self.__db:
            cell.setup_project(self.__project_name,self.__db,self.__config)


    def get_multi_highlighted_cells(self):
        
        cell_ids = []
        cells = []
        cell_names = []

        for cell_id in self.__cells_to_highlight:
            cell_ids.append(cell_id)
            cells.append(self.elements[cell_id]["cell"])
            cell_names.append(self.elements[cell_id]["name"])

        return cell_names, cell_ids, cells
    

    def get_cell_id(self, cell_name):
        return self.data_frame[(self.data_frame['Name'] == cell_name)].first_valid_index()
        

    def show_add_parameter_view_with_prediction(self, predictions, callback=None):
        if self.expanded_element:
            self.elements[self.expanded_element]["cell"].show_add_parameter_view_with_prediction(predictions, callback)

    
    def show_add_subobject_view_with_prediction(self, predictions, callback=None):
        if self.expanded_element:
            self.elements[self.expanded_element]["cell"].show_add_subobject_view_with_prediction(predictions, callback)


    def show_parameter_linked_text(self, linked_text):
        if self.expanded_element:
            self.elements[self.expanded_element]["cell"].show_parameter_linked_text(linked_text)

    def show_subobject_linked_text(self, linked_text):
        if self.expanded_element:
            self.elements[self.expanded_element]["cell"].show_subobject_linked_text(linked_text)


    def get_cells_to_highlight(self):
        return self.__cells_to_highlight


    def clear_multi_select(self, remove_start=True):
        if remove_start:
            if self.__multi_select_start in self.elements:
                self.elements[self.__multi_select_start]["cell"].clear_multi_select_highlight()

            self.__multi_select_start = ''
        for cell in self.__cells_to_highlight:
            self.elements[cell]["cell"].clear_multi_select_highlight()


        
    def __highlight_element(self,name,cell_id,group_id,cell):
        if self.__cell_highlighted_callback_func:
            self.__cell_highlighted_callback_func(name,cell_id,group_id,cell)
        if self.__acm_data_handler:
            cell.setup_data_handler(self.__acm_data_handler)
        if self.__db:
            cell.setup_project(self.__project_name,self.__db,self.__config)
    
    def __unhighlight_element(self, name,cell_id,group_id,cell):    
        if self.__cell_unhighlighted_callback_func:
            self.__cell_unhighlighted_callback_func(name,cell_id,group_id,cell)

    def shrink_elements(self):
        self.expanded_element = None
        if self.shown:
            self.show_elements()
        else:
            self.hide_elements()
     
    def show_elements(self):
        y0, y1 = self.redraw_elements()
        self.callback_size_change(y0, y1) 
                            
                            
    def hide_elements(self): 
        self.remove_elements()
        self.callback_size_change(self.y, self.y + 50)   

    def hide_entry_widgets(self):
        if self.expanded_element:
            self.elements[self.expanded_element]["cell"].hide_entry_widgets()
        
    def show_entry_widgets(self):
        if self.expanded_element:
            self.elements[self.expanded_element]["cell"].show_entry_widgets()
        
                
    def callback_size_change(self, y0 ,y1):
        if self.callback:
            self.callback(self.id, y0, y1 )
                


class expandable_list_canvas(tk.Frame):
    def __init__(self, placeholder, refresh_data_callback):
        tk.Frame.__init__(self, placeholder)
        self.rowconfigure(0, weight=1)  # make canvas expandable
        self.columnconfigure(0, weight=1)
        self.vbar = AutoScrollbar(self, orient='vertical')
        self.vbar.grid(row=0, column=1, sticky='ns')
        self.canvas = tk.Canvas(self, highlightthickness=0,bd=0, yscrollcommand=self.vbar.set)
        self.canvas.grid(row=0, column=0, sticky='nswe')
        self.canvas.update()  # wait till canvas is created
        self.vbar.configure(command=self.__scroll_y)
        self.configure_canvas = None
        self.canvas.bind('<Configure>',  self.__redraw)  # canvas is resized
        self.canvas.bind('<MouseWheel>', self.__wheel)
        self.canvas.bind('<Button-1>',self.__click)
        self.canvas.bind('<Control-1>',self.__ctrl_click)
        self.canvas.bind('<Shift-1>',self.__shift_click)
        self.canvas.bind('<ButtonRelease-3>', self.__right_click)
        self.__shift_select_tag = ''
        self.__ctrl_select_tag = ''
        self.canvas.config(scrollregion=(0,0,0,0),background='white')
        self.elements = {}
        self.expanded_subelement_parent = None
        self.highlighted_subelement_parent = None
        self.message_visible = False
        self.message_image = None
        self.message_image_id = None
        self.message_title_id = None 
        self.message_text_id = None
        self.empty_image = None
        self.canvas_list_name = None
        self.empty_image_id = None
        self.empty_title_id = None 
        self.empty_text_id = None
        self.__header_pass_document_selection_subscription = None
        self.__document_selection_subscription = None
        self.db = None 
        self.db_to_db_mapping = None
        self.acm_data_handler = None
        self.__document_selected_func = None
        self.banner_handler = banner_handler(self.canvas,0,0,self.vbar,refresh_data_callback)
        self.__primary_running_tasks = []
        self.__secondary_running_tasks = []
        self.__background_tasks_dict = {}
        self.__highlighted_cell_name = None
        self.__highlighted_cell_id = None
        self.__highlighted_cell_object = None 
        self.__popup_menu = None
        self.refresh_pending = False
        self.header_elements = []


    def set_canvas_name(self, canvas_name):
        self.canvas_list_name = canvas_name

    def popup_menu(self, func):
        self.__popup_menu = func
        


    def __right_click(self, event):
        if self.popup_menu:
            if self.__shift_select_tag and self.elements and self.__shift_select_tag in self.elements:
                cells_to_highlight = self.elements[self.__shift_select_tag]['element'].get_cells_to_highlight()
                if not self.__highlighted_cell_id in cells_to_highlight:
                    self.__clear_multi_select()
            self.__popup_menu(event)


    def get_object_if_running(self, name):
        if name not in self.__background_tasks_dict:
            return None 
        else:
            return self.__background_tasks_dict[name]

    
    def __add_background_task(self,name, object):
        self.__background_tasks_dict[name] = object


    def __remove_background_task(self, name):
        if name in self.__background_tasks_dict:
            self.__background_tasks_dict.pop(name)
        self.refresh_pending = True


    def setup_data_handler(self, data_handler):
        self.acm_data_handler = data_handler


    def document_selected_func(self, func):
        self.__document_selected_func = func

    def setup_project(self, project_name, database:Database, config):
        self.project_name = project_name
        self.db = database
        self.config = config

    def setup_configure_canvas(self, canvas):
        self.configure_canvas = canvas

    def pass_document_selection_subscription(self, subscription=None):
        if subscription != None:
            self.__document_selection_subscription = subscription
            self.__document_selection_subscription(None,None,None,None,self.__document_canvas_multi_selection)
            if self.__header_pass_document_selection_subscription:
                self.__header_pass_document_selection_subscription( subscription)
        else:
            if self.__document_selection_subscription and self.__header_pass_document_selection_subscription:
                self.__header_pass_document_selection_subscription(self.__document_selection_subscription)


    def __document_canvas_multi_selection(self, cells):

        selected_cells = []

        # Use the self.db_to_db_mapping to change any id to id used for cells
        if self.db_to_db_mapping:
            for i, cell_id in enumerate(cells):
                if cell_id in self.db_to_db_mapping:
                    cells[i] = self.db_to_db_mapping[cell_id]

        if len(cells) == 0:
            return selected_cells, self.refresh_pending, self.canvas_list_name
        for id in self.header_elements:
            if id in self.elements and 'element' in self.elements[id]:
                cell_list = self.elements[id]['element'].select_cell_list(cells)
                selected_cells.extend(cell_list)
                for cell in cell_list:
                    if self.acm_data_handler:
                        cell.setup_data_handler(self.acm_data_handler)
                    if self.db:
                        cell.setup_project(self.project_name,self.db,self.config)
                    cell.primary_progress_callback_func(self.__add_primary_running_task)
                    cell.secondary_progress_callback_func(self.__add_secondary_running_task)
                    cell.add_background_task_callback_func(self.__add_background_task)
                    cell.remove_background_task_callback_func(self.__remove_background_task)
                    if self.configure_canvas:
                        cell.setup_configure_canvas(self.configure_canvas)
                    
                    
        return selected_cells, self.refresh_pending, self.canvas_list_name


    def __empty_list_indication(self):
        if self.message_visible:
            return

        if len(self.elements) > 0:
            return 

        if self.empty_image_id:
            self.canvas.delete(self.empty_image_id)
            self.canvas.delete(self.empty_title_id)
            self.canvas.delete(self.empty_text_id)
        
        self.empty_image = tk.PhotoImage(data=empty_image)
        self.empty_image_id = self.canvas.create_image(int(self.canvas.winfo_width()/2), 
                                        int(self.canvas.winfo_height()/3), 
                                        image = self.empty_image, 
                                        anchor = tk.CENTER
                                    )
        title_font = font.Font(family="arial.ttf",size=11,weight="bold")
        self.empty_title_id = self.canvas.create_text(int(self.canvas.winfo_width()/2),
                                    int(self.canvas.winfo_height()/3 + self.empty_image.height()/2 + 8),
                                    text='Empty List', anchor=tk.CENTER, fill="#A0A0A0",font=title_font,
                                    justify=tk.CENTER)
        message_font = font.Font(family="arial.ttf",size=9,weight="normal")
        self.empty_text_id = self.canvas.create_text(int(self.canvas.winfo_width()/2),
                                    int(self.canvas.winfo_height()/3 + self.empty_image.height()/2 + 24),
                                    text='No items found.', anchor=tk.CENTER, fill="#A0A0A0",font=message_font,
                                    justify=tk.CENTER)

        
        
    def __add_primary_running_task(self, callback):

        self.__primary_running_tasks.append(callback)

        self.canvas.after(1000, self.__check_primary_running_tasks)
        self.banner_handler.primary_progress_banner.show()
        self.banner_handler.primary_progress_banner.disable_close_pop_up()


    def __add_secondary_running_task(self, callback):

        self.__secondary_running_tasks.append(callback)

        self.canvas.after(1000, self.__check_secondary_running_tasks)
        self.banner_handler.secondary_progress_banner.show()
        self.banner_handler.secondary_progress_banner.disable_close_pop_up()


    def __check_primary_running_tasks(self):
        total_page_count = 0 
        total_pages_done = 0
        scanners_to_remove = []
        pages_done_array =[]


        for i in range(len(self.__primary_running_tasks)):
            (page_count
             , pages_done
             , _
             ,done_scanning
             ,count_of_scans
             ,done_saving
             ,names_of_scans
             ,error
             ,cancel_scan_funcs) = self.__primary_running_tasks[i]()
            total_page_count = total_page_count + page_count
            total_pages_done = total_pages_done + pages_done
            pages_done_array.append(pages_done)
            if done_saving or error or total_page_count == 0:
                scanners_to_remove.append(i)

        saved = 0.2 if done_saving else 0

        if total_page_count > 0:
            percent_done = total_pages_done/total_page_count * 0.8 + saved
        else:
            percent_done = 0

        self.banner_handler.primary_progress_banner.set_info(percent_done,
                                            total_pages_done,total_page_count,
                                            names_of_scans,count_of_scans, error,
                                            cancel_scan_funcs)

        scanners_to_remove.sort(reverse=True)
        for i in scanners_to_remove:
            self.__primary_running_tasks.pop(i)

        if len(self.__primary_running_tasks) != 0:
            self.canvas.after(1000, self.__check_primary_running_tasks)
        else:
            self.banner_handler.primary_progress_banner.enable_close_pop_up()
            

    def __check_secondary_running_tasks(self):
        total_page_count = 0 
        total_pages_done = 0
        scanners_to_remove = []
        pages_done_array =[]


        for i in range(len(self.__secondary_running_tasks)):
            page_count, pages_done, _,done, error = self.__secondary_running_tasks[i]()
            total_page_count = total_page_count + page_count
            total_pages_done = total_pages_done + pages_done
            pages_done_array.append(pages_done)
            if done or error:
                scanners_to_remove.append(i)

        if total_page_count > 0:
            self.banner_handler.secondary_progress_banner.set_info(total_pages_done/total_page_count,
                                            total_pages_done,total_page_count, error)

        scanners_to_remove.sort(reverse=True)
        for i in scanners_to_remove:
            self.__secondary_running_tasks.pop(i)

        if len(self.__secondary_running_tasks) != 0:
            self.canvas.after(1000, self.__check_secondary_running_tasks)
        else:
            self.banner_handler.secondary_progress_banner.enable_close_pop_up()
            

            

    def show_message(self, title, message, image):
        self.message_visible = True 
        self.message_title = title 
        self.message_text = message
        self.message_image = tk.PhotoImage(data=image)

        # Delay required to remove bug that places the message 
        # incorrectly when the canvas is sill updating
        self.canvas.after(1000, lambda: self.__redraw(None)) 


    def hide_message(self):
        if self.message_visible:
            self.message_visible = False 
            self.__remove_message()
        
        self.__redraw(None)

    
    def __remove_message(self):
        if self.message_image_id:
            self.canvas.delete(self.message_image_id)
            self.canvas.delete(self.message_title_id)
            self.canvas.delete(self.message_text_id)
        
        self.banner_handler.warning_banner.hide()


    def __draw_message_with_icon(self):

        if not self.message_visible:
            return
            
        if not self.message_image:
            return

        self.__remove_message()

        if len(self.elements) > 0:
            self.banner_handler.warning_banner.show(self.message_title,self.message_text)
            return 

        self.message_image_id = self.canvas.create_image(int(self.canvas.winfo_width()/2), 
                                    int(self.canvas.winfo_height()/3), 
                                    image = self.message_image, 
                                    anchor = tk.CENTER)
        title_font = font.Font(family="arial.ttf",size=11,weight="bold")
        self.message_title_id = self.canvas.create_text(int(self.canvas.winfo_width()/2),
                                    int(self.canvas.winfo_height()/3 + self.message_image.height()/2 + 8),
                                    text=self.message_title, anchor=tk.CENTER, fill="#A0A0A0",font=title_font,
                                    justify=tk.CENTER)
        message_font = font.Font(family="arial.ttf",size=9,weight="normal")
        self.message_text_id = self.canvas.create_text(int(self.canvas.winfo_width()/2),
                                    int(self.canvas.winfo_height()/3 + self.message_image.height()/2 + 24),
                                    text=self.message_text, anchor=tk.CENTER, fill="#A0A0A0",font=message_font,
                                    justify=tk.CENTER)


        
        
    # noinspection PyUnusedLocal
    def __scroll_y(self, *args, **kwargs):
        """ Scroll canvas vertically and redraw the image """
        self.canvas.yview(*args)  # scroll vertically
        
    def __wheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), tk.UNITS)


    def show_canvas_tag(self, header_id, cell_id):
        header_id = str(header_id)
        cell_id = str(cell_id)

        if header_id not in self.elements or 'element' not in self.elements[header_id]:
            return

        self.__open_header(header_id,False)

        cell_bbox = self.canvas.bbox(cell_id)
        bbox2 = self.canvas.bbox(tk.ALL)

        if not cell_bbox or not bbox2:
            return

        pos = cell_bbox[1] - expandable_list_canvas_header.DEFAULT_CELL_HEIGHT - 50
        height = bbox2[3] - bbox2[1]
        if height:
            self.canvas.yview_moveto(pos / height)
        self.__open_cell(header_id, cell_id)


    def show_control_module(self, tagname):

        for id in self.elements.keys():

            if id == 'Unassigned':
                continue

            cell_id = self.elements[id]['element'].get_cell_id(tagname)

            if cell_id:
                self.show_canvas_tag(id, str(cell_id))
                break


    def show_linked_text(self, linked_text_id):
        
        linked_text = self.db.get_approved_text_link_by_id(linked_text_id[0])

        tagname = linked_text['tagname']['text']
        is_subobject = 'subobject' in linked_text

        for id in self.elements.keys():

            if id == 'Unassigned':
                continue

            cell_id = self.elements[id]['element'].get_cell_id(tagname)

            if cell_id:
                cell_id = str(cell_id)
                self.show_canvas_tag(id, cell_id)
                if is_subobject:
                    self.elements[id]['element'].show_subobject_linked_text(linked_text)
                else:
                    self.elements[id]['element'].show_parameter_linked_text(linked_text)
                break     

    
    def show_add_parameter_view_with_prediction(self, tagname, prediction, callback):
        for id in self.elements.keys():

            if id == 'Unassigned':
                continue

            cell_id = self.elements[id]['element'].get_cell_id(tagname)

            if cell_id:
                cell_id = str(cell_id)
                self.show_canvas_tag(id, cell_id)
                self.elements[id]['element'].show_add_parameter_view_with_prediction(prediction, callback)
                break


    def show_add_subobject_view_with_prediction(self, tagname, prediction, callback):
        for id in self.elements.keys():

            if id == 'Unassigned':
                continue

            cell_id = self.elements[id]['element'].get_cell_id(tagname)

            if cell_id:
                cell_id = str(cell_id)
                self.show_canvas_tag(id, cell_id)
                self.elements[id]['element'].show_add_subobject_view_with_prediction(prediction, callback)
                break



    def __shift_click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        tags = self.canvas.gettags(self.canvas.find_closest(x,y))
        if tags and tags[0] == 'cell':
            if self.__shift_select_tag != tags[1]:
                self.__clear_multi_select()
            self.__shift_select_tag = tags[1]
            self.elements[tags[1]]['element'].multi_select(tags[2])

    
    def __clear_multi_select(self):
        if self.__shift_select_tag and self.elements and self.__shift_select_tag in self.elements:
            self.elements[self.__shift_select_tag]['element'].clear_multi_select()
            self.__shift_select_tag = ''
            self.__ctrl_select_tag = ''
        
    def __normal_click_multi_select(self, event):
        self.__clear_multi_select()
        self.__shift_click(event)

    def __ctrl_click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        tags = self.canvas.gettags(self.canvas.find_closest(x,y))
        if tags and tags[0] == 'cell':
            self.elements[tags[1]]['element'].single_multi_select(tags[2])
            self.__ctrl_select_tag = tags[1]
        

    def __click(self, event):
        self.__normal_click_multi_select(event)
        self.canvas.focus_set() # To remove focus on other elements
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        tags = self.canvas.gettags(self.canvas.find_closest(x,y))
        if 'current' in tags:
            if tags[0] == 'header':
                self.__open_header(tags[1])
            elif tags[0] == 'cell':
                self.__open_cell(tags[1],tags[2])


    def __open_cell(self, header_id, cell_id):
        if self.expanded_subelement_parent:
            self.elements[self.expanded_subelement_parent]['element'].shrink_elements()
        self.elements[header_id]['element'].expand_element(cell_id)
        self.expanded_subelement_parent = header_id


    def __open_header(self, header_id, hide=None):
        if self.db:
            self.elements[header_id]['element'].setup_project(self.project_name,self.db,self.config)
        if self.acm_data_handler:
            self.elements[header_id]['element'].setup_data_handler(self.acm_data_handler)
                
        header_expanded = self.elements[header_id]['element'].show_or_hide(hide)

        self.elements[header_id]['element'].add_primary_progress_callback(self.__add_primary_running_task)
        self.elements[header_id]['element'].add_secondary_progress_callback(self.__add_secondary_running_task)
        self.elements[header_id]['element'].document_selected_func(self.__document_selected_func)
        self.elements[header_id]['element'].add_background_task_callback_func(self.__add_background_task)
        self.elements[header_id]['element'].remove_background_task_callback_func(self.__remove_background_task)
                
        self.__header_pass_document_selection_subscription = self.elements[header_id]['element'].pass_document_selection_subscription
        if header_expanded:
            self.pass_document_selection_subscription()

        
    def __redraw(self, _):
        self.__delete_elements()
        y = 0
        for id, values in self.elements.items():
            if 'element' in values:
                self.elements[id]['element'].draw(y) 
                self.elements[id]['y0'] = y
                y = y + self.elements[id]['height']
                self.elements[id]['y1'] = y
        
        bbox=self.canvas.bbox(tk.ALL)
        if bbox:
            self.canvas.config(scrollregion=(bbox[0],bbox[1],bbox[2],bbox[3] + 200))
        
        self.__draw_message_with_icon()
        self.__empty_list_indication()
        
        self.refresh_pending = False
        self.banner_handler.draw()

    
    def __delete_elements(self):
        for key, values in self.elements.items():
            if 'element' in values:
                self.elements[key]['element'].delete_on_canvas()

    
    def set_db_to_db_mapping(self, mapping=None):
        self.db_to_db_mapping = mapping

    
    def insert_header(self,id, name, data_frame, cell_class):
        self.elements[id]= {
                            'id':id,
                            'name': name,
                            'height': 50,
                            'type':'header'
                            }
        
        self.elements[id]['element'] = expandable_list_canvas_header(self.canvas, id,name, data_frame, cell_class, 
                                                                        self.configure_canvas, resize_callback = self.header_expansion
                                                                        ,cell_highlighted_callback=self.highlighted_cell
                                                                        ,cell_unhighlighted_callback=self.unhighlighted_cell)
        self.elements[id]['element'].get_object_if_running_func(self.get_object_if_running)
        self.header_elements.append(id)
        

    def highlighted_cell(self,name,cell_id,group_id,cell):
        self.__highlighted_cell_name = name
        self.__highlighted_cell_id = cell_id
        self.__highlighted_cell_object = cell

    def unhighlighted_cell(self,name,cell_id,group_id,cell):
        if self.__highlighted_cell_name == name:
            self.__highlighted_cell_name = None
            self.__highlighted_cell_object = None 

        if self.__highlighted_cell_id == cell_id:
            self.__highlighted_cell_id = None

    def get_highlighted_cell(self):
        ''' Returns tuple (name, cell_id , cell_object) of the highlighted cell '''
        if self.__shift_select_tag or self.__ctrl_select_tag:
            select_tag = self.__shift_select_tag if self.__shift_select_tag else self.__ctrl_select_tag
            if select_tag in self.elements and self.elements[select_tag]:
                cell_data = self.elements[select_tag]['element'].get_multi_highlighted_cells()
                if cell_data[0]:
                    return (cell_data[0],cell_data[1],cell_data[2], True)
        return (self.__highlighted_cell_name,self.__highlighted_cell_id, self.__highlighted_cell_object, False)
        
        
    def header_expansion(self, id, y0, y1):
        self.elements[id]['y0'] = y0
        self.elements[id]['y1'] = y1
        self.elements[id]['height'] = y1 - y0
        self.__redraw(None)
        

    def reset(self):
        self.canvas.delete(tk.ALL)
        self.elements = {}
        self.header_elements = []
        self.expanded_subelement_parent = None
        self.highlighted_subelement_parent = None


    def redraw(self):
        self.__clear_multi_select()
        self.__redraw(None)
           
        
    def hide_entry_widget_for_expanded_cell(self):
        if self.expanded_subelement_parent:
            if self.expanded_subelement_parent in self.elements:
                self.elements[self.expanded_subelement_parent]['element'].hide_entry_widgets()
            else:
                self.expanded_subelement_parent = None
        
    def show_entry_widget_for_expanded_cell(self):
        if self.expanded_subelement_parent:
            if self.expanded_subelement_parent in self.elements:
                self.elements[self.expanded_subelement_parent]['element'].show_entry_widgets()
            else:
                self.expanded_subelement_parent = None
        


def resize_to_min(image):
    w, h = image.size
    
    min_dim = 100
    
    if w <= h:
        ratio = h/min_dim
        ideal_w = int(w/ratio)
        ideal_h = min_dim
    else: 
        ratio = w/min_dim
        ideal_h = int(h/ratio)
        ideal_w = min_dim
    
    return image.resize(w,h)

class canvas_image_element:
    def __init__(self, canvas, id, image):
        self.canvas = canvas
        self.x = 0
        self.y = 0
        self.id = id
        
        self.title = None 
        self.image = None
        self.rect = None
        self.img = image
     
    
    def draw(self, x, y):
        self.delete_on_canvas()
        self.x = x
        self.y = y
        
        self.title = self.canvas.create_text( x + (self.img.width()/2), y + self.img.height() + 8, text=self.id, anchor='center', tags=(self.id))
        self.image = self.canvas.create_image( x, y, image=self.img, anchor=tk.NW, tags=(self.id))
        self.rect = self.canvas.create_rectangle(x-1, y-1, x + self.img.width(), y + self.img.height(), tags=(self.id),outline="#939393", width=1)
        
    def highlight(self):
        self.canvas.itemconfig(self.rect, width=4, outline="#00AEEF")
    
    def unhighlight(self):
        self.canvas.itemconfig(self.rect, width=1, outline="#939393" )
    
    def delete_on_canvas(self):
    
        self.x = 0
        self.y = 0
            
        if self.title:   
            self.canvas.delete(self.title)
        
        if self.image:
            self.canvas.delete(self.image)
        
        if self.rect:
            self.canvas.delete(self.rect)

    def get_image_size(self):
        return  (self.img.width(),self.img.height())
        


class image_gallery_canvas(tk.Frame):
    def __init__(self, placeholder, image_selected_callback=None):
        tk.Frame.__init__(self, placeholder)
        self.rowconfigure(0, weight=1)  # make canvas expandable
        self.columnconfigure(0, weight=1)
        vbar = AutoScrollbar(self, orient='vertical')
        vbar.grid(row=0, column=1, sticky='ns')
        self.canvas = tk.Canvas(self, highlightthickness=0,bd=0, yscrollcommand=vbar.set)
        self.canvas.grid(row=0, column=0, sticky='nswe')
        self.canvas.update()  # wait till canvas is created
        vbar.configure(command=self.__scroll_y)
        self.canvas.bind('<Configure>',  self.__redraw)  # canvas is resized
        self.canvas.bind('<MouseWheel>', self.__wheel)
        self.canvas.bind('<Button-1>',self.__click)
        self.canvas.config(scrollregion=(0,0,0,0),background='white')
        self.elements = []
        self.drawn_elements = {}
        self.highlighted_cell = None
        self.image_selected_callback = image_selected_callback
        self.loading_animation = loading_animation(self.canvas)
        self.loading_animation_visible = True
        
        
    # noinspection PyUnusedLocal
    def __scroll_y(self, *args, **kwargs):
        """ Scroll canvas vertically and redraw the image """
        self.canvas.yview(*args)  # scroll vertically
        
    def __wheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), tk.UNITS)
        
    def __click(self, event):
        self.canvas.focus_set() # To remove focus on other elements
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        page = int(self.canvas.gettags(self.canvas.find_closest(x,y))[0])
        cell = page - 1 # page number correction
        if self.highlighted_cell:
            self.highlighted_cell.unhighlight()
        self.elements[cell].highlight()
        self.highlighted_cell = self.elements[cell]
        if self.image_selected_callback:
            self.image_selected_callback(page)

    def highlight_page(self, cell):
        if self.highlighted_cell:
            self.highlighted_cell.unhighlight()
        
        if not self.elements:
            return
        
        self.elements[cell].highlight()
        self.highlighted_cell = self.elements[cell]
        
    def __redraw(self, _):
        y = 16
        x = 0
        row_height = 0
        row_cells = []
        x_adjust = 0
        canvas_width = 0
        for i in range(len(self.elements)):
            self.elements[i].draw( x, y)
            row_cells.append(self.elements[i])
            w, h1 = self.elements[i].get_image_size()
            x = x + w + 8
            
            canvas_width = self.canvas.winfo_width()
            
            
                
            # record the largest image height          
            if (32 + h1) >= row_height:
                row_height = 32 + h1
            
            if i < len(self.elements) - 1:
                w, h = self.elements[i+1].get_image_size()
                
                # center image in row
                if (x + w + 8) >= canvas_width:
                    x_adjust = int((canvas_width - x + 8)/2)
                    for cell in row_cells:
                        cell.draw( cell.x + x_adjust, cell.y)
                    row_cells = []    
                
                
                # If image wont fit move to next row                     
                if (x + w + 8) >= canvas_width:
                    y = y + row_height
                    x = 0
                    row_height = 0
                    
                    
          
        x_adjust = int((canvas_width - x + 8)/2)
        for cell in row_cells:
            cell.draw( cell.x + x_adjust, cell.y)
            
        if self.canvas and self.canvas.bbox(tk.ALL):  
            self.canvas.config(scrollregion=(0,0,self.canvas.bbox(tk.ALL)[2],self.canvas.bbox(tk.ALL)[3]))
        
    def reset_image_elements(self):
        self.canvas.delete(tk.ALL)
        self.elements = []
    
    def insert_image_elements(self,id, image):
        self.elements.append(canvas_image_element(self.canvas, id,image))
        
    def redraw(self):
        if self.loading_animation_visible:
            self.__start_loading_animation()
        self.__redraw(None)

    def start_loading_animation(self):
        self.loading_animation_visible = True
        self.redraw()

    def stop_loading_animation(self):
        self.loading_animation_visible = False
        self.loading_animation.stop()
        

    def __start_loading_animation(self):
        self.loading_animation.draw(self.canvas.winfo_width()/2,self.canvas.winfo_height()/3)
        
       


import re        
        
class AutocompleteEntry(Entry):
    def __init__(self, autocompleteList, canvas:tk.Canvas, edit_callback=None,validatecommand=None,id=None, *args, **kwargs):
        self.canvas = canvas
        self.disable_listbox = False
        self.edit_callback = edit_callback
        self.__id = id 
        self.listbox=None
        self.matchesFunction=None
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
                    pattern = re.compile('.*' + re.escape(fieldValue) + '.*', re.IGNORECASE)
                    return re.match(pattern, acListEntry)
                    
                self.matchesFunction = matches

        if validatecommand:
            Entry.__init__(self, self.canvas, validate = 'key',validatecommand=validatecommand, *args, **kwargs)
        else:
            Entry.__init__(self, self.canvas, *args, **kwargs)


        self.autocompleteList = autocompleteList
        
        self.var = self["textvariable"]
        if self.var == '':
            self.var = self["textvariable"] = StringVar()
        
        if autocompleteList != []:
            self.var.trace('w', self.changed)
        else:
            self.var.trace('w', self.__edit_callback)
        self.bind("<Right>", self.key_selection)
        self.bind("<Up>", self.moveUp)
        self.bind("<Down>", self.moveDown)
        
        
        self.listboxUp = False

    def __edit_callback(self, name, index, mode):
        if self.__id:
            if self.edit_callback:
                self.edit_callback(self.__id,self.var.get())
        else:
            if self.edit_callback:
                self.edit_callback(self.var.get())

    def changed(self, name=None, index=0, mode=None):
        if self.disable_listbox:
            return
        if self.var.get() == '':
            if self.listboxUp:
                self.destroy_listbox()
                self.listboxUp = False
        else:
            words = self.comparison()
            if words:
                if not self.listboxUp:
                    listbox_font = font.Font(family="arial.ttf",size=13,weight="normal")
                    m_len = listbox_font.measure("n")
                    if m_len == 0:
                        m_len = 10
                    width = int(self.winfo_width()/m_len)
                    self.listbox = Listbox(master=self.canvas, width=width, height=self.listboxLength, relief='flat',
                                    font=listbox_font, background='#F0F0F0',selectbackground="#D3D3D3",
                                    selectforeground="black")
                    self.listbox.bind("<<ListboxSelect>>", self.mouse_selection)
                    self.listbox.bind("<Right>", self.key_selection)
                    self.listbox.bind("<Tab>", self.key_selection)
                    self.canvas.master.bind("<Return>", self.key_selection)
                    self.listbox.place(x=self.winfo_x(), y=self.winfo_y() + 24)
                    self.listboxUp = True
                    
                
                self.listbox.delete(0, END)
                for w in words:
                    self.listbox.insert(END,w)
                index = '0'
                self.listbox.see(index) # Scroll!
                self.listbox.selection_set(first=index)
                self.listbox.activate(index)
            else:
                if self.listboxUp:
                    self.destroy_listbox()
                    self.listboxUp = False
                    
        if self.__id:
            if self.edit_callback:
                self.edit_callback(self.__id,self.var.get())
        else:
            if self.edit_callback:
                self.edit_callback(self.var.get())
    
    def key_selection(self, _=None):
        if self.listboxUp:
            self.var.set(self.listbox.get(ACTIVE))
            self.destroy_listbox()
            self.listboxUp = False
            self.icursor(END)

    def destroy_listbox(self):
        self.canvas.master.unbind("<Return>")
        if self.listbox:
            self.listbox.destroy()
        
    def mouse_selection(self, event):
        if not self.listboxUp:
            return 
        
        self.var.set(self.listbox.get(ANCHOR))
        self.destroy_listbox()
        self.listboxUp = False
        self.icursor(END)

    def update_autocomplete_list(self, autocompleteList, change_instant=False):
        self.autocompleteList = autocompleteList

        if not change_instant:
            return 

        self.changed()


    def moveUp(self, event):
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

    def comparison(self):
        if self.matchesFunction is None:
            return []
        
        return [ w for w in self.autocompleteList if self.matchesFunction(self.var.get(), w) ]
        
class custom_entry:
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
        self.entry = AutocompleteEntry(autocompleteList, self.canvas
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
        
        # Thinking animation properties
        self.thinking_active = False
        self.thinking = False
        self.thinking_text = None  # Will be a tk.Label
        self.thinking_window = None  # Canvas window for the label
        self.thinking_dots = 0
        self.thinking_animation_id = None
        self.thinking_circle_phase = 0  # 0 to 1, controls size and opacity
        self.thinking_circle_image = None  # PhotoImage for the circle
        
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
        pass


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
            
        
        if not self.thinking:
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
        
        
        if self.error_found:
            self.error()

        if self.thinking:
            self.start_thinking()
        
    def start_thinking(self):
        """Start the thinking animation"""
        self.thinking = True

        if self.thinking_active:
            return
        
        self.thinking_active = True
        self.thinking_dots = 0
        self._animate_thinking()
    
    def stop_thinking(self):
        """Stop the thinking animation"""
        self.thinking = False

        self.stop_thinking_animation()

    def stop_thinking_animation(self):
        """Stop the thinking animation immediately"""
        if not self.thinking_active:
            return
        
        self.thinking_active = False
        if self.thinking_animation_id:
            self.canvas.after_cancel(self.thinking_animation_id)
            self.thinking_animation_id = None
        
        # Hide thinking label and window
        if self.thinking_window:
            self.canvas.delete(self.thinking_window)
            self.thinking_window = None
        if self.thinking_text:
            self.thinking_text.destroy()
            self.thinking_text = None
        self.thinking_circle_image = None
        self.thinking_circle_phase = 0
        
    
    def _animate_thinking(self):
        """Internal method to handle the thinking animation"""
        if not self.thinking_active:
            return
        
        # Cycle through 0, 1, 2, 3 dots (3 resets to 0)
        self.thinking_dots = self.thinking_dots + 0.1
        thinking_dots = int(self.thinking_dots % 4)
        dots = "." * thinking_dots if thinking_dots > 0 else ""
        thinking_message = f" thinking{dots}"
        
        # Update circle animation phase (0 to 1 and back)
        self.thinking_circle_phase = (self.thinking_circle_phase + 0.1) % 2.0
        phase = self.thinking_circle_phase if self.thinking_circle_phase <= 1.0 else 2.0 - self.thinking_circle_phase
        
        # Create animated circle image with antialiasing
        circle_size = 16
        scale = 2  # Upscale factor for antialiasing
        upscaled_size = circle_size * scale
        
        min_radius = 3
        max_radius = 6
        radius = min_radius + (max_radius - min_radius) * phase
        upscaled_radius = radius * scale
        
        # Opacity varies: darker when small, lighter when large
        min_opacity = 255  # Darker
        max_opacity = 50  # Lighter
        opacity = int(min_opacity + (max_opacity - min_opacity) * phase)
        
        # Create circle image at higher resolution
        img = Image.new('RGBA', (upscaled_size, upscaled_size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        center = upscaled_size // 2
        draw.ellipse(
            [center - upscaled_radius, center - upscaled_radius, center + upscaled_radius, center + upscaled_radius],
            fill=(0, 174, 239, opacity)  # Blue with varying opacity
        )
        
        # Downsample for smooth antialiased edges
        img = img.resize((circle_size, circle_size), Image.LANCZOS)
        self.thinking_circle_image = ImageTk.PhotoImage(img)
        
        # Update or create thinking label
        if self.thinking_text:
            self.thinking_text.config(text=thinking_message, image=self.thinking_circle_image, compound=tk.LEFT)
        else:
            # Create thinking label
            thinking_font = font.Font(family="arial.ttf", size=self.size-1, slant="italic")
            self.thinking_text = tk.Label(
                self.canvas,
                text=thinking_message,
                image=self.thinking_circle_image,
                compound=tk.LEFT,
                fg='#888888',
                bg='white',
                font=thinking_font,
                borderwidth=0,
                highlightthickness=0
            )
            
            # Position thinking label in the entry area
            thinking_x = self.x + 16 + 2  # Slightly offset from entry start
            thinking_y = self.y + 18 + self.placeholder_spacing + 2
            self.thinking_window = self.canvas.create_window(
                thinking_x, thinking_y,
                window=self.thinking_text,
                anchor=tk.NW
            )
        
        # Schedule next animation frame (faster for smooth animation)
        self.thinking_animation_id = self.canvas.after(100, self._animate_thinking)
        
    def hide(self):
        self.stop_thinking_animation()  # Stop thinking animation when hiding
        self.__delete_static_elements()


    def __delete_static_elements(self):
        if self.placeholder_text:
            self.canvas.delete(self.entry_window)
            self.canvas.delete(self.rect)
            self.canvas.delete(self.line)
            self.canvas.delete(self.placeholder_text) 
            self.canvas.delete(self.error_text)
            
        # Clean up thinking label and window if they exist
        if self.thinking_window:
            self.canvas.delete(self.thinking_window)
            self.thinking_window = None
        if self.thinking_text:
            self.thinking_text.destroy()
            self.thinking_text = None
        self.thinking_circle_image = None
        
                
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

class custom_label():
    def __init__(self, canvas:tk.Canvas, x_offset, y_offset, text="", fill= '#505050', size=11, weight="normal"):
        self.fill = fill
        self.font = font.Font(family="arial.ttf",size=size,weight=weight) 
        self.canvas = canvas 
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.label = None 
        self.text = text
        
    def draw(self,x=0, y=0, max_width=None):
        self.hide()
        self.x = self.x_offset + x
        self.y = self.y_offset + y
        self.label = self.canvas.create_text(self.x + 16, self.y + 2, fill = self.fill, text=self.text,
                                anchor=tk.NW, font=self.font)
                                
    def hide(self):
        if self.label:
            self.canvas.delete(self.label) 


    def set_text(self, text):
        if self.label:
            self.canvas.itemconfig(self.label,text=text)
            
            
class cell_line():
    def __init__(self, canvas, x1, x2, y_offset, fill= '#505050', width=2):
        self.fill = fill
        self.width = width
        self.canvas = canvas 
        self.x1 = x1
        self.x2 = x2
        self.y_offset = y_offset
        self.line = None 
        
    def draw(self, y=0, max_width=None):
        self.hide()
        self.y = self.y_offset + y
        self.line = self.canvas.create_line(self.x1, self.y, self.canvas.winfo_width() - self.x2, 
                                self.y, fill=self.fill, width=self.width)
                                
    def hide(self):
        if self.line:
            self.canvas.delete(self.line) 
        
                
class rounded_image_button():
    def __init__(self, canvas, x_offset, y_offset, cornerradius, padding=8, width=None, height=50, text= None, text_image=None, icon_image=None, font_size=11, borderwidth=1, tags=None
            ,fixed_width_offset = 0,callback=None ):
        if tags:
            self.tags = tags + ('rounded_button',)
        else:
            self.tags = ('rounded_button',)
        self.canvas = canvas
        self.text_image = text_image
        self.icon_image = icon_image
        self.text_value = text
        self.padding = padding
        self.cornerradius = cornerradius
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.fixed_width = width
        self.width = 0
        self.height = height
        self.borderwidth =borderwidth
        self.border = None 
        self.icon = None 
        self.text_label = None 
        self.font_size = font_size
        self.fixed_width_offset = fixed_width_offset # This is a hack to make the button look centered when using fixed width
        self.callback = callback


        
    def draw(self, x=0, y=0):
        self.hide()
        self.x = self.x_offset + x
        self.y = self.y_offset + y
        if self.fixed_width:
            self.width = self.fixed_width
            fixed_width_offset = self.x + self.fixed_width_offset
        else:
            self.width = self.canvas.winfo_width() - self.x
            fixed_width_offset = 0
        
        self.border = self.round_rectangle( self.x+self.padding,self.y+self.padding,
                                            self.x+self.width-self.padding,self.y+self.height-self.padding, 
                                            radius=self.cornerradius, borderwidth=self.borderwidth,
                                            fill="white",outline='#E5E5E5')
        
        if self.icon_image:
            self.icon = self.canvas.create_image( int(self.width/2)-24 + fixed_width_offset, self.y+self.padding+self.cornerradius-4,
                                                tags=self.tags, image=self.icon_image, anchor=tk.NE)
            x_image_offset = 16
            y_image_offset = self.y+self.padding+self.cornerradius-2
            text_anchore = tk.NW
        else:
            x_image_offset = 0
            y_image_offset = self.y + self.height/2
            text_anchore = tk.CENTER

        if self.text_image:
            self.text_label = self.canvas.create_image(int(self.width/2)-x_image_offset + fixed_width_offset, y_image_offset,
                                             tags=self.tags, image=self.text_image, anchor=text_anchore)
        else:
            self.text_label = self.canvas.create_text(int(self.width/2) -x_image_offset + fixed_width_offset , y_image_offset + 1, 
                                            fill = '#777777', text=self.text_value, anchor=text_anchore, 
                                            tags=self.tags, font=('Roboto Bold',self.font_size,'bold'))
            
        self.canvas.tag_bind(self.border,'<Button-1>', self.on_click)
        if self.icon_image:
            self.canvas.tag_bind(self.icon,'<Button-1>', self.on_click)
        self.canvas.tag_bind(self.text_label,'<Button-1>', self.on_click)
    
    def hide(self):
        if self.text_label:
            self.canvas.delete(self.text_label)
            self.canvas.delete(self.icon)
            self.canvas.delete(self.border)
        

    def round_rectangle(self,x1, y1, x2, y2, radius=25, borderwidth=1, **kwargs):

        points = [x1+radius, y1,
                  x1+radius, y1,
                  x2-radius, y1,
                  x2-radius, y1,
                  x2, y1,
                  x2, y1+radius,
                  x2, y1+radius,
                  x2, y2-radius,
                  x2, y2-radius,
                  x2, y2,
                  x2-radius, y2,
                  x2-radius, y2,
                  x1+radius, y2,
                  x1+radius, y2,
                  x1, y2,
                  x1, y2-radius,
                  x1, y2-radius,
                  x1, y1+radius,
                  x1, y1+radius,
                  x1, y1]

        return self.canvas.create_polygon(points, width=borderwidth, **kwargs, smooth=True, tags=self.tags)
    
    def on_click(self, event): 
        self.canvas.itemconfigure(self.border, fill="#eeeeee", outline="#E5E5E5")
        self.callback(self.tags)
        def _restore_border():
            try:
                if not self.canvas.winfo_exists():
                    return
                self.canvas.itemconfigure(self.border, fill='white', outline="#E5E5E5")
            except tk.TclError:
                # Canvas or item was destroyed before the timer fired.
                pass
        try:
            if self.canvas.winfo_exists():
                self.canvas.after(200, _restore_border)
        except tk.TclError:
            pass


class rounded_text_button():
    def __init__(self, canvas, x=0, y=0, cornerradius=10, padding=4, text="Round Button", borderwidth=1, tags=('rounded_button',), callback=None,
                    font_used=None,is_on=False,no_animation=False):
        self.tags = tags
        self.canvas = canvas
        self.text = text
        self.padding = padding
        self.cornerradius = cornerradius
        self.x = x
        self.y = y
        self.width = 0
        self.height = 50
        self.borderwidth =borderwidth
        self.border = None 
        self.icon = None 
        self.text_label = None 
        self.is_on = is_on
        self.callback = callback
        self.bounds = None
        self.no_animation = no_animation
        if font_used:
            self.font = font_used
        else:
            self.font = font.Font(family="arial.ttf",size=9,weight="normal")
        self.text_label = self.canvas.create_text(self.padding,self.padding ,fill="#505050",font=self.font,
                        text=self.text,tags=self.tags, anchor = tk.NW)
        self.bounds = self.canvas.bbox(self.text_label)
        self.canvas.delete(self.text_label)
        self.text_label  = None


    def delete_on_canvas(self):
    
        self.x = 0
        self.y = 0
            
        if self.text_label:   
            self.canvas.delete(self.text_label)
        
        if self.border:
            self.canvas.delete(self.border)
        


        
    def draw(self, x, y):
        self.delete_on_canvas()
        self.x = x
        self.y = y
        
        self.text_label = self.canvas.create_text(self.padding + x,self.padding + y,fill="#505050",font=self.font,
                        text=self.text,tags=self.tags, anchor = tk.NW)
        self.bounds = self.canvas.bbox(self.text_label)
        self.canvas.delete(self.text_label)

        
        self.border = self.round_rectangle( self.bounds[0] - self.padding,self.bounds[1] - self.padding,
                                            self.bounds[2] + self.padding,self.bounds[3] + self.padding, 
                                            radius=self.cornerradius, borderwidth=self.borderwidth,
                                            fill="white",outline='#A0A0A0')
                                            
        self.text_label = self.canvas.create_text(self.padding + x,self.padding + y,fill="#505050",font=self.font,
                        text=self.text,tags=self.tags, anchor = tk.NW)
                        
            
        
        self.canvas.tag_bind(self.border,'<Button-1>', self.on_click) 
        self.canvas.tag_bind(self.text_label,'<Button-1>', self.on_click) 

        if not self.no_animation:
            self.canvas.tag_bind(self.text_label,'<Enter>', self.on_focus) 
            self.canvas.tag_bind(self.text_label,'<Leave>', self.on_not_focus) 
            self.canvas.tag_bind(self.border,'<Enter>', self.on_focus) 
            self.canvas.tag_bind(self.border,'<Leave>', self.on_not_focus) 
        return (self.bounds[0] - self.padding,self.bounds[1] - self.padding, self.bounds[2] + self.padding,self.bounds[3] + self.padding)
        
    def set_is_on(self, is_on):
        self.is_on = is_on
        if self.is_on:
            self.canvas.itemconfig(self.text_label, fill='white')
            self.canvas.itemconfig(self.border,  fill="#00AEEF",outline='#00AEEF')
        else:
            self.canvas.itemconfig(self.text_label, fill='#505050')
            self.canvas.itemconfig(self.border,  fill="white",outline='#505050')
    
    def on_focus(self, event):
        if not self.is_on:
            self.canvas.itemconfig(self.text_label, fill='white')
            self.canvas.itemconfig(self.border,  fill="#c0c0c0",outline="#c0c0c0")
        
    def on_not_focus(self, event):
        if not self.is_on:
            self.canvas.itemconfig(self.text_label, fill='#505050')
            self.canvas.itemconfig(self.border,  fill="white",outline='#505050')
        
    def on_click(self, event):
        if not self.no_animation:
            if not self.is_on:
                self.canvas.itemconfig(self.text_label, fill='white')
                self.canvas.itemconfig(self.border,  fill="#00AEEF",outline='#00AEEF')
                self.is_on = True
            else:
                self.canvas.itemconfig(self.text_label, fill='white')
                self.canvas.itemconfig(self.border,  fill="#c0c0c0",outline="#c0c0c0")
                self.is_on = False
            
        if self.callback:
            self.callback(self.tags, self.is_on)
            
    def get_size(self):
        return ( -self.bounds[0] + self.padding + self.bounds[2] + self.padding, -self.bounds[1] + self.padding + self.bounds[3] + self.padding)
    
    def hide(self):
        if self.text:
            self.canvas.delete(self.text_label)
            self.canvas.delete(self.icon)
            self.canvas.delete(self.border)
        

    def round_rectangle(self,x1, y1, x2, y2, radius=25, borderwidth=1, **kwargs):

        points = [x1+radius, y1,
                  x1+radius, y1,
                  x2-radius, y1,
                  x2-radius, y1,
                  x2, y1,
                  x2, y1+radius,
                  x2, y1+radius,
                  x2, y2-radius,
                  x2, y2-radius,
                  x2, y2,
                  x2-radius, y2,
                  x2-radius, y2,
                  x1+radius, y2,
                  x1+radius, y2,
                  x1, y2,
                  x1, y2-radius,
                  x1, y2-radius,
                  x1, y1+radius,
                  x1, y1+radius,
                  x1, y1]

        return self.canvas.create_polygon(points, width=borderwidth, **kwargs, smooth=True, tags=self.tags + ('button_rect',))



class loading_animation():
    def __init__(self, canvas):
        self.canvas = canvas
        self.delay = 0.05  # Animation delay - try low floats, like 0.04 (depends on the gif in question)
        self.stopped = False  # Thread exit request flag
        self.started = False
        # Create a Pillow Image of a square 100x100, with a transparent gray background
        background = Image.new('RGBA', (100, 100), (0, 0, 0, 0))
        # Draw a round rectangle on the background
        draw = ImageDraw.Draw(background)
        draw.rounded_rectangle((10, 10, 90, 90), radius=10, fill=(220, 220, 220, 190))
        # Save the image to a BytesIO object
        self.__background_image = ImageTk.PhotoImage(background)
        self.__background_image_id = None
        self.__image = tk.PhotoImage(data=loading_animation_images[0])
        self.__image_id = None
        self._num = 0
        self.frames = []
        self.animation_thread = None

        for i in range(len(loading_animation_images)):
                #print "saving %s (%s) frame %d, %s %s" % (path, mode, i, im.size, im.tile)
            
                self.frames.append(tk.PhotoImage(data=loading_animation_images[i]))

    def draw(self, x, y, draw_background=False):
        self.delete()
        if draw_background:
            self.__background_image_id = self.canvas.create_image( x, y, image=self.__background_image, anchor=tk.CENTER)
        self.__image_id = self.canvas.create_image( x, y, image=self.__image, anchor=tk.CENTER)
        self.start()

    def hide(self):
        self.stop()

    def delete(self):
        if self.__image_id:
            self.canvas.delete(self.__image_id)
        if self.__background_image_id:
            self.canvas.delete(self.__background_image_id)

    def start(self):
        """ Starts non-threaded version that we need to manually update() """
        self.start_time = time.time()  # Starting timer
        if not self.started:
            self.started = True
            self.stopped = False
            self._animate()

    def stop(self):
        """ This stops the after loop that runs the animation, if we are using the after() approach """
        self.stopped = True
        self.started = False
        if self.animation_thread is not None:
            self.canvas.after_cancel(self.animation_thread)
            self.animation_thread = None
        self.delete()

    def _animate(self):
        if self._num < len(self.frames) and not self.stopped:
            #gif = BytesIO(base64.b64decode(self.gif_file))
            #self.gif = ImageTk.PhotoImage(gif, format='gif -index {}'.format(self._num))  # Looping through the frames
            self.canvas.itemconfigure(self.__image_id,image=self.frames[self._num])
            self._num += 1
        else:  # When we try a frame that doesn't exist, we know we have to start over from zero
            self._num = 0
            self.canvas.itemconfigure(self.__image_id,image=self.frames[self._num])
            self._num += 1
        if not self.stopped:    # If the stop flag is set, we don't repeat
            self.animation_thread = self.canvas.after(int(self.delay*1000), self._animate)




if __name__ == "__main__":

    classButtonD = None

    def test_callback(id, is_on):
        print(is_on)
        
    def stop_button():
        print("K")
        classButtonD.stop_thread()
        
    def wait_callback():
        print("J")
        timer = Timer(5, stop_button)
        timer.start()
        

    root = tk.Tk()
    

    root.configure(background='white')
    
    base_64_gray_hand = '''
    iVBORw0KGgoAAAANSUhEUgAAACgAAAAoCAMAAAC7IEhfAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAABdUExURQAAAM/Pz8/Pz8/Pz8/Pz8/Pz8zMzM3NzczMzM3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc7Ozs3Nzc7Ozs7Ozs7Ozs3Nzc7Ozs3Nzc7Ozs7Ozs3Nzc7Ozs3Nzc3Nzc7Ozs3NzcgNLfQAAAAedFJOUwAQIDBAT1Bgb3B/gI+Qn6CvsL/AzM/Q1N/g5O/w+LmvCzwAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAE0SURBVDhPxZRRQsMgDEDL0LG21gooDpm5/zGXAKttSOufvg8W4DW0LND9DXp4VjU8ZAaA66l2DjBgn3qwtbeLxoSYLSSMDhhw1QQYeAzA7b7pGeIUgMTPHM1luGUCXO+bxC+KYirDLZ6cuDS5K5JnNs3OLjViAnihCQ4T3/MXjTTDYGLMX3SlGUYjPiIOE38azn+IanAX/MmDY3g0gviBtfLKBwXRYJ3MMHHRNmIPZ6xVMEzUOLoV1Q23X4VSs4ztwyMYTHDLNcvYijllp38XS8rOTKW3hoklpQQTa0oBLu6m5CKm7Gu0pRFVTOJ597EGCwb/QwHhFvJ06XC0cLg0uBqtcHTAOFP7Pb34PlgWbDMviQq45RThbbWSdhCEhQll8VZ2Fax6cR8KevZYbUS045Ku6+6IbxwNHjWnSAAAAABJRU5ErkJggg==
    '''
    
    base_64_blue_hand = '''
    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
    '''
    
    base_64_black_hand = '''
    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
    '''
    
    classButtonA = hover_toggle_button(root,base_64_blue_hand,base_64_black_hand,base_64_gray_hand, callback = test_callback)
    classButtonA.grid()
    
    classButtonB = hover_toggle_button(root,base_64_blue_hand,base_64_black_hand,base_64_gray_hand)
    classButtonB.disable()
    classButtonB.grid()
    
    classButtonC = hover_toggle_button(root,base_64_blue_hand,base_64_black_hand,base_64_gray_hand, is_toggle=False, callback = test_callback)
    classButtonC.grid()
    
    base_64_gray_sync = '''
    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
    '''
    
    base_64_black_sync = '''
    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
    '''
    
    base_64_blue_sync = '''
    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
    '''
    
    sync_blue_animation = [
        '''
        iVBORw0KGgoAAAANSUhEUgAAACkAAAAoCAYAAABjPNNTAAAACXBIWXMAAAR2AAAEdgG9ParHAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAQ/SURBVHgB7VjbVdtAEL275jtBFcRUEFNBlArAJPkGKoBUgKkgSQUm3znBpAJEBXEqQKlALgBLmdlZWVppJVuyOScf3HPAa1mjvTs7j7tSWIdZMkSK0IwzLDBAhHGwWGOzT/9HZDc03zXmZDNHTyi0kcswpVHosZrQpNcNdhdkN6HRfuWXmOzek12MnZCcJSOa6N4zURlznASHzpWfyZSeeIY2pBjjY3CHDtDeqxlmluCCxtc0cUCEFH0yqe/2rhGRmpQInpUIRsZrYhPQM87BnpQZpzYcNkbdkzLZ1IwHgzMcvfpeu2eWzGjiY7MIhQMTo7fJI30fGjInwYHHhnfnN8QJ1/gQTLAhtIf2qR1FXoKMJ3yzI/ZIiB9JaAmy/bnXRhInsvccoQN82y1boXTcaPUpiFbjlO5XTuw222V4cObYEBp90DGmVlDoZecjKavN0uMWMqelJ8xN7cyRNmS3PCvf5j/YiuQSeXnYN2WI66U7WWjrICMysSbFPTJXFK4o+S5rBFN8QRG3X9EB/jrJpYUnE8REak7L4c8RiuK+MCUpL85S/O9XRKQMze1ij5HHYUpJ9zG4xNYk60Sr4O4xrrW6OlEXPQi2kywmndDoLcQTsclQTdvV1r+l1p6i2N4I3ATGparQAbqFIJHSRzRBBt7aomO8Bsy2N9mFdM87lL2ZmfGRKeg9oPzkwCKBt6WtZMSmcOfe2azfMyJrF2ND7MEl6IupuU2A3CMjS2Ros18UUWZKz35pARHF4F/zTVO4SNKxfWjbY4DOJKsElaJSlF17daDE3JUlOiFbvjohUgsiFDXGHpcmRbvU1pU8KLb7NmGCoRln+EwCoL2WyaJYLUmc9ZBg3UiWlU8XhcLxK1s3hGzxoTfrJc4lFHqL3sKLfpnVBlZAAxMmrjeLBAxRV/cR6cAbnDSorBpJ8YYJqkb9uA65llT6BuPX57Z1TtFU1AtsdKRQjidYQetuQW1xYVtfDJjif1P6jUqOvsNTKqJiT1Omp5elBawlqpx43C3cOlqF23YjCrP3tAPMY0E2n+GQdIN/V3DFRxNuE64gF5bJV9tAYM5FpQQsSlBVkvUBa0n2TpcKUZyNctSSV2EXMDVz8A5qKYJ5nQflhQMtaPBINqOVBw0jm3wl7GEX4Dccajk1UoTb6CyJSDw/NL7tYFKm8yxhbcoP+1W90u+MU39K+fQnntGYrY6wVSiT/XHD06Lqhd14MqsV6xhtiSh64GD1nokXKQIk9nl+e0/KmbsszySz8782cOxyXV6SIOZkYbXvwfae1DUBzISvqrXOi1x5aTM+bHrztr0nlXPwkr7NMTkzHl5PUBBD1D+ei+TEbJNs1flqMpZx1aNtQTB0tGtGB7TWtrhr1I8RciTmFwIab5zjrRBcW/h3T1KIth9tBe29vYTnIZlDFBZ7jo/EQ0goPJjY7Xm8fcEL/gf8A/IZtvcE6ss9AAAAAElFTkSuQmCC
        ''',
        '''
        iVBORw0KGgoAAAANSUhEUgAAACkAAAAoCAYAAABjPNNTAAAACXBIWXMAAAR2AAAEdgG9ParHAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAARcSURBVHgB7VhBVtswEP1yum7xDdwTND1BzQlCKF0HTgCcgOQE0BME1n0lcALcEzQ9AeYEzuu62J3RyLFsyyZ20ve64PMAxfFIX9LMn5EUXsIiCZAi1O0MKwwQYeyvXrDZo79Dsgv0Zw9LslmiJxTayGWYUyt0WE1p0FmD3SnZTam1V/kmJrt9souxE5KLZEgDPTgGsrHEof+x9OR7Mqcej9GGFGMc+XfoAM/5NMPCEFxRe0YD+0RI0X8mdWPeGhKpqUXw2CIY6VUTG5/6OAGvpIw4N+6wMeorKYPNdXswOMbo7U3tnUWyoIEP9CQU3msfvU0e6XOgyRz67x02vDs/IYsww2d/ig3hOWhPTCtyEmT8wVfT4hUJ8S0JDUG2P3HaSOBE5p0ROsC13bIVyosbrb740bqd0vuq5LvNdhl+lMbYEB76oKNPraHQy85FUmabpQctZCZWD0utnTnShuiWvvJt/oWtSD4jl4c9LUOsl+XBQqODjEj7moh7pJ8oXFDwndUIprhE4bdX6AC3TrK08GCCmEgtaTr8f4hC3FdaknJxFvF/WBMRGVqayR4g98OUgu7IP8PWJOtEq+DsMa6lujrRMnoQbCdZDDql1gfISsQ6Qj3arrb8LVo7QbG9ETgJjC1V6ACvhSCR8kY0QAbe2iJjvAP0tjfZhfTOJ9irmen2SAt6Dyg3OXCRwNvSJhmxFu58dTbL94zI2MXYEG9QJujyqaUJgHxFhoZIYKJfKqJMS8+eNYGIfPBJf/LIXSTo2D406dFHZ5JVgkqRFGUzZx0oPndhiE7Jlp9OidSKCEWNvsfSpGiX2rKSA8V23yZMMNTtDOdUALRrmUyKqyXxsx4lWDeSduXTpUJh/5WtCyBb/LEx6vOk0LvoLVbRXWa1gSuggXaT8mqKOkx0ei1X9zwJcqHBNQ4bqqwKPBPNof40GEzRFVIRxWLvjQxBCY4svUL9+GHGe77Wi1NNuw6o0kpwBe11c2qDU5P6YlrNc5669R1Jjkermz6ZMUJIoRGY7188+7yhDgOL8lxLd38E1N+BNfiJI9LZHc6stJsf+PabOvXo5w7otXouRPokCcrRsjpR45scnKwighC3vydNrxYStIFvtCDXWO6RJ32+cRQXQRtR0O7rzFXRZoVdYJHMTcaxe76mv7MXyYrAXxqbK5OO74lw7jaVtNiP4LBGkCHPQvp1nRxFnpDyKSBax4EQ5PNVYr++PcmsFMkMHjiGfcSoIiUyKpVaVcGRpdLS7Ui/g1gO+ygrIs3IaKuO9XlcLhPqsIM1W6tBbl1zke18UtLiA+Sm4974VnFh0G4b6ENbufp3ZrzdBE4+aIZH3e6W//Pqf9J0Y7I7koxCTlZGJ5doJzc3DMZ0KzIsXTpY2M4nq5ArFt5mcYPq0bYgGBo3CU2aRBNB6XbXqB8jpOpRpUApjhgbuMbuSQLtF7AFmnJ7Df+GZA6psHjlPpjRWAWetDb2PN6+4hX/A/4C6nW9Ts+M3DQAAAAASUVORK5CYII=
        ''',
        '''
        iVBORw0KGgoAAAANSUhEUgAAACkAAAAoCAYAAABjPNNTAAAACXBIWXMAAAR2AAAEdgG9ParHAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAARVSURBVHgB7VjbVdtAEJ2V+U6sDpwK4lQQUQE4j29DBSEVYFdAUoHhOwcMFSAqwFQQpQI5+cZS5rHrXdmrtSw75+SDyzl4Le9or2Zm785IwSZM8x4UkPC4hDl0IIVBPN9g08X/fbTr8fcIZmgzg5ZQECJXwgRHicdqhIuOa+y+oN0IR92VXzK0O0S7DPZCcpr3caF7z0IuZvAhfle5cp1P8I4nEEIBA/gU38IWiLxXS5hqgnMcj3HhGAkp/CRSV3pWH0mNHIInDsGUvSY2Md7jFMiTsuJEp0NjrHtSFpvwuNM5gaNXV2tzpvkUFz7mh1DwhnP0Jv+J33tM5kP8xmND0XkEccIYPsYjaIjIQ3uoR6mXIOEZvusReSSBH3miCZL9qddGNk6q5xzBFvCFW0KhoqzW6nOcLscFzleV3K23K+GhskZDRNAGW+bUEgpa2flIytOWxXGAzNC5w4y106Co2d1yLxPmJ9iJ5AKMPHRZhkgvq4slWgcJKeeaiHvKVxSc4+Y7WyNYwAXYvP0GW8CvkyQttJggQ1IzfBz67IMV9zlLkhFnEf/7JRGRoZl+2GMweVjgpvsUn8HOJNeJroJOj8HaUbdOtIoWBMMk7aIjHL0F8UTGOzTCcIXOb9HaIdjwpkCHwMBRhS0QBQgiqegIFyiBQmtPjNcAHPY6uwTnvAfXmyWPj1jQW0D5yQEVCRSWkGRkLNzGO83Oe0Kq7TJoiAOoEvTl1ExvAOORvibS07tfKqKSpafrPECKOfiLv0WYLrLpyD7Rx2MMW5NcJagUSlE59taBknPnmugIbenqCEnNkVBam3skTQqjFDqVPLDhvsmJYMLjEr5iARDWMnkoqpYkz1qUYE0hG4c8YwmONxIkUE5ROWY31EXwuKSHanmciietF/1lVghUAXU4TareFHUY8vFare7pEKA5jSVJ8c1K4KSqrR83wdSSKrqEwetTfc9HqBN1u/ol/h9v2umq4gmqoKPtklrji1MEH+p7PerfUHKiWyiK33jvuZ7n6ujG3kdVKvH9wBDt8bh+p7vH7nq/5CDCP8qPDPaHrpayLJhz1D7QJhX04ebPsG6qlaDVkqwpFrhAxFK0irkO4yxobzdtit48hCDJNhCtpNzrVsgJuuA2anVw0406S8/cdu2DwTPnnZCxKfOgc9IlW4+ikmo935TdSFJDtkBC5C1DUkU5h5gKYvFitmZHEaCNQ58HDsmo8xavTVarpQPYFaZzvMmlmCgLKRxC2kevbxQXGkP98kGwWFzqEZFc7vbdPFmFCe/7jcdfCXd61PPKX7ns6xn7I+k2cAWEWwSqDaz8VEEHysf40r202+5ehZWTZvJjBZ2i0PURJOwz3OYVi1nwEcN+7tVfkp1rfJ9EB4nxKBUnHoJy231D2ggS955zlVqGTL+SScDK0h0K+DHbBLy+f5JC1HSZw8Asf1vswb8hacChxo4TCpIb470nridbtrcveMH/gL8UkLqLbvQCewAAAABJRU5ErkJggg==
        ''',
        '''
        iVBORw0KGgoAAAANSUhEUgAAACkAAAAoCAYAAABjPNNTAAAACXBIWXMAAAR2AAAEdgG9ParHAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAROSURBVHgB7VjbVdtAEL2S+U6sCuJUEKeCKBXwCHxjKgAqQK4AqMDwnROcVIBSAU4FiAqkk28sZWZ2Za3klSwLcfLDPcf2Stbs3t2dvTMjB5swj0dI4Us7Q4IBQux7yQabIX2PyW4k1y4WZLNARzhoIpdhRi3fYhXQoNMau1OyC6g1rPwTkd1XsovQC8l5PKaB7i0DmVjgwPtcuvMjnlGPEzQhxT4OvZ/YAq71boa5JphQe0oDe0TIoV8mdaufGhOpwCA4MQiGsmrKxqM+TsArqUacaXdojfWVVIPNpD0YTLD77nbtmXk8p4H3ZBIOPoqP3sWPdD0SMgfeR4sN784D1CJM8c0L0BKuhfaxboVWgoxnXOsWr4iP77GvCbL9idVGHZxQP7OLLWDbbrUVjhvVWh154aqd0vNOyXfr7TL8Lo3REi66YEufWsFBJzsbSTXbLN1rIHNs9LAQ7cyR1pxu1Ve+zX/wIpJL5PIwFBlivSwP5msdZITia0rcQ7nj4IIO39kawRSXKPz2ClvArpMsLTyYQkSkFjQd/h2jEPdEJCkXZyX+9ysiSoYWerJ7yP0wpUN36J3hxSTXiVbB0WN/LdStEy2jA8FmksWgAbU+Qa1EJCfUpe1qit9Ka49RbG8IDgL7hipsAbeBIJFyd2mADLy1RcR4D8i219n59MwXmKuZSXtXBL0DHDs5cJLA29IkGZEId7467eI9I9R2EVpiB2WCNp9a6AOQr8hYExnp068yokykZ2hMICQffJIrl9xFHTq293V49LA1ySpBxyEpyqbWPFD53IUmGpAt3w2IVEKEwlrfY2lyaJeaopIFxXbfxUzQl3aGc0oAmrVMTYqzJeVnHVKwtlAHh1emIDjdSJDBPsXpWHGgLhvDJU+qYzhVJIvMJ9omhRIZWq6ynhG1fU1ouCLGO3QXxzT5R/rEktLN45moQEs40iEbM+ryx03Ic0lHQupClIHFnmuj+oDAo9/Q9/mmmsmRXHAgBwaSQbvbObXGqQ59JpTUCGGXJpE+6bTOp/9MHd1Y++wQqZFBeSbS3Q98IrVH7lMNgzd69wJATnpe8H2t6yjf7gfUxduXoSgvbCjlB4MJDuyuVkhQNSVrD16JC+opMbacB1OHcVM9U0jfevWpUYh5h3pYIwL7312cy1ZCg03oGkLUdT80Wmc0IeWnY1koC49u5YMdn/SvilBMdMl+lp43WrlGVl/jcjvoG2YBd9QtNauiv5V0kLR+dh5fyOsYxnNp9ax99Ecy0xlPcwGXp3QBfa4k6uysop3KWS22/ZE0C7gUTSVChDzeZ6LL/uofFTofqkT7I6n8L5Q2a9+vv8fW56rxvjgsQ+OD1yGpyBUvppbLG+17o7XnzAmVEeoKNCl32zfs2T0PHq1it0osrnWkUwWeWYpU0D/JgmgA801HGerNW/7qcEN6+Dokc8hWU8WJlOuaoQ6dT7KSL3g9/YY3/G/8AyKQuRtIdbKWAAAAAElFTkSuQmCC
        ''',
        '''
        iVBORw0KGgoAAAANSUhEUgAAACkAAAAoCAYAAABjPNNTAAAACXBIWXMAAAR2AAAEdgG9ParHAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAARMSURBVHgB7VhRVptAFH2D+a5hBY0rKF1BcQUx1n4bV6CuIMkKrCuIfvdU6grEFUhXIF0B9F+h772ZyUAYCCR4+uP1nDghPOby5r07FwRsQpCMIAOfxzmksAchTNx0Q8wQPz2MG/F3ByKMiWBLCGgil8MSR74lao6TLmrizjFujqPh2i8xxh1iXAy9kAwSDyd6sExURATH7ufSkZ/JEq84hSZkMIET9xd0gGM9mkOgCKY4XuDELhIS+J9I3aqzPCQ1LxCcFgiGnDUZ4+I1zoAyKWdcqnJojWom5WRLHu/tTWH84bZyTpAEOPER34SAA67Ru+QZv4+YzLF7YImh1XkCmYQFfHXn0BKOhfapGoVWgoQXuFYjyogPPxJfEaT4M2uMbJxQnTOGDrAtt1wK4cS1Ud/ccDXO8HxRqt36uBweS3O0hAPboGNNrSBgqzgbSXm3eXbUQOa0cIWItVMjq+lueS29zL9hJ5KvoOVhyDJEelmezFc6SAi51qS4h3xEwAyb76JCMIMrMHX7HTrArpMkLTSZRIykIrwd+u+BEfeUJUmLsxT/hxURKUORutkj0HWYYdOduBewM8kq0XXQ7jGpbHVVomVsQbCZpJl0jqNPIDMRc4c6uFxN+7fU2lMwyxsCbQKTgip0gNNAEEk5Y5wgB1pas2PsA/Cy18X5eM4XKGYz5/GYBX0LCDs5IJNAy9IkGTELt85Ou/2eEKq4GFpiAGWCtpqKVAPojHiKyEh1v3REOUvPsHADIdbgH/7mYLnIpqN4X22PLnQmuU5QCJSifGH1gbLmZoroHGPp6BxJpUgorK09kiaBq9S0K1lglvsuIYI+j3O4RAPQrGXypsgtyTrbwoK1hWwcyowhuNhIkEA1RXbMNNRVZYcqbgTbbqWgM2myaLdZTSAHtMdlQpjiTQrubi3gZOUyHAvecQi0CVDGF22bR/Ad5sBFVesfN8F4ySqodAT/dm6Z/QY/Lzc9Mw3QG3qYCYmXV8E61x2R6nywEPFxdcishMrW+XhU6qhUBA9/O2wiKkpO/G2QIsmy3MimIx3W2Q3xnMO6Czj4R/URQ7+I1XMNYVhZHarFY97DtcP3m1bQSNC6JeuKYnNQbWev90j0GWTzkBmxy5Op59psNhuMLgjwcVbWmFGIIMEOdz7CZP+6Nk4K/JVi49pqcwB9wTSOcd2TFuJO5Zav5Ik2hrB6Sn8Y8We2U31bBb8/ktqEOOw92+OlJF1WGeqPZLZaZq9xC6R3RXfJ08pbDgoPdTXGpE+SoRoRwVnteVIfPXzgmyq9nPJx4dzUhfRHkl4YCPWkSUTWnxgNHtXMY+WiFLIFvDlJCfNiSrArWlb0NwftT+m4fpxIlYG2rkB/Oqlhd/ehmo0yrUXehurrROg/k0WfWXRTPsjHBu1T47WolB1Rzcuu/jNZBC81PnFCRgTJEt6zoQ7+zvA1jo/NgpnNHnd5Vf2Od/wP/ANJHaO3WYNmKQAAAABJRU5ErkJggg==
        ''',
        '''
        iVBORw0KGgoAAAANSUhEUgAAACkAAAAoCAYAAABjPNNTAAAACXBIWXMAAAR2AAAEdgG9ParHAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAQ9SURBVHgB7VjNedNAEH2SfYaoApQKMBWgVOAkwDmmAkgFtisAKjCc+YjpIKKCmAoiKpC5JxLzs5Ila6VoHXHh4/GRrJQd7dvZmbez6+EhrNMQGSJp59hihBhnwfYBmyP6OSG7UJ59bMhmgwPhoYtcjhW1IovVggZdtti9I7sFtY72/pKQ3QnZJRiE5Dqd0EDXloGq2OA8eFF78y1d0Rdn6EKGM7wOvsMBvvVtjrUhuKX2kgYOiJBHv5nUF9NrQqQWFYKzCsFYvKY2AX3jLdiTOuLKhENvND2pg62kPRrNMH3ypdFnna5p4FOZhIdjidGr9JaeQyFzHhxbbHh1bqBOWOJVsEBP+BbaF6YVWwky7vDJtNgjEb6mkSHI9m+tNpo4sekzhQNsy61L4flJq9WbIC7bGfX3arHbbpfjR22MnvBxCBxjqoSHg+xsJHW2eXbaQeai8oWNaGeBrCW79VvFMv/Eo0jeo5CHI5Eh1sv6YJHRQUYssabiHssbD3NKvvcNghk+YBe3H+EAu06ytPBgioRIbWg6/HuCnbhvRZIKcVbxvy6JqAxtzGRPUcRhRkn3OniPR5NsEt0H7x5nja2uSbSOAwh2k9wNuqDWc6gnEslQn5ara/9Wrb3Abnlj8CZwVlEFB/gdBImUP6UBcvDS7naMp4Ase5tdRH1eourNXNpTEfQD4NnJgYsEXpYuyUhEuAvv9NvvGbGxS9ATY9QJ2mJqYxKg8MjEEAlN9mtFlIv0HFUmEFMM/pInn8JFk47tI7M9BnAmuU/Q80iK8qW1DtSYmxuiC7LltwsitSVCcWvssTR5tEpdu5IFu+W+SplgJO0cl1QAdGuZToqrJY2zA0owN5LVyselQuH41aULUchSRh62bX8eTfzA6lxJ7rxoL7O6wBXQSMKEwSQmLSOdABKbMxPjy77J45tsjuRpNFrAFVoRJebpNxH4DJUsGyLwJJhojlsa+0OfYmVMteGEPKG4u/dE59yxMZn/jP53ydAleCIwOqoyF9GYJ12bw5h8GZZPHJc5HoOwUnwkFJ+XvFblX3V5ZyaWuR9nOofH3EzACp/+fYejJPSAngxHsCcKe+1c9nCt8NmjHSs4Nm4+bpRkrsgwKwsSju3pk0TaV2lSEt8HH41zqTF5Bdg2tn26u8Bwwe5w5qYQ1WqLT5aW2Dzs+GBDXiaLU9Vtwq1AaO8yHIoDXOpmVpMrqyoMR9IzMZdnIdzwoE4ORzIrj6tRq0Dz+/0szmp3TVY1GI6kLztNgbZjx0oqreJ6hhVFqyJG623dcCR1gKruNYkWyeX7z4ygs9CH8q7t5gPDJo7qXqGHWmfO7fqbhaZ6mpi+ncXGcDpZwF7dx1LGqeeiWv8epeGwnmSwR7Qsq152RWgv4ea0K92gA8N7soriKns8yuWGrlr918F7eeuZ5++S3MdXOe6GjfePvFP/j38KfwAXG5nOiHLVMQAAAABJRU5ErkJggg==
        ''',
        '''
        iVBORw0KGgoAAAANSUhEUgAAACkAAAAoCAYAAABjPNNTAAAACXBIWXMAAAR2AAAEdgG9ParHAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAR5SURBVHgB7VjbddQwEB1r8w3rDkwFmApwKsiD8J2lAqCCeCsAKlj45rAbKsCpAFNBTAXeAhKLecivtexYjvPH5ZCVbY11pRnNXNmDh7DLAygg4raGPSwggTN//4DNEv+GaBfwtYIUbVKYCA+GyGnYYCuyWMU46LrH7j3axdhaHjzJ0O4Y7TKYheQuD3GgX5aBmkjh3H/VuvMj3+AbVzCEAs7gwr8GByjrXQ07Q3CP7TUO7CMhD3+J1DfTK0RScYPgqkEw4VUTGx/f8Q5oJWXEjQmH0eiupAy24fZisYKTZ986fXb5Dgc+5Ul48IJjdJvf4nXAZM79FxYb8s5vkEVYwxs/hpFQFtqXppVYCRLu4Itp0YpE8D2PDEGyf2e1kY2TmD4n4ACbu8UVnsp6rd76SdUusL/Xit1+Ow03rTFGQsEUOMZUBQ8m2dlIymx1cTpA5rLxhpRzZ4miZ3fLu0o3/4FHkbyHMj0sOQ1RvmwPFpk8SEg41iS5J3zHgyvcfB86BAv4BHXcfgYH2PMkpRYaTJAhqRSnQ78h1Ml9zympTM6S/H9VRCQNpWayp1DGYYGb7sL/AI8m2SV6CKoeZ51S1yXaxgSCwyTrQWNsvQRZiYx3qEJ3DdVvybWXULs3ASoCZ42s4AA1QBBJqRMcQAO5tq4YzwHY7X12EfZ5Dc3V1Nw+4YQ+AZ6dHJBIILcMpYyME3e5OuPqPSExdhmMxBG0CdpiKjUboFyR0BAJzO4XRaQ59SwbE0gwBv/ylcJwkU1H9pEpjz44kzwk6HmYivTaqgMl5q4M0Rht6W6MpPZIKOmNPUpNHnppqCpZULt7mxPBiNsaPqIAGM5lMilSSxJnTQkmz2i19ryieoEuvr+ZoiVrkk3l46JQKH6FTADi4le860lwLNgrh0hxMutperJWPpmLhGJC95XqCbAdcYsEiGjIwzQVInmZnEP9V6ZzxFeLRQyuEEWUib2S2kxHCI/LoI1IyquvIcd+n8aQ9Vquodkrt6A2eG9KH7n8a6O20zuv8V4AErty5KgFspCWs09vcThCUkGD8oZT93QEDYJSOs8xO2xz3v4YjzdmnGPT79KQp0zxse+lCv9dA0xavSGUJ8PUqChx6cIoLNrl5/4KW6LwqXDsWN1bUaegQ0nmigLdLXEIhmBSPRPptuxsSskOtyCTSJD4MTwptvln/K9NvI0HqS2xy/u6TDs+2PHS/DqpbvRAYlrLPgEyJ0mBp3Kn/ket/WBNR3OSFDGhCzc5dtcSM9Y0NB9JDaUQCZ02oWpo056PWvORVJjE65XoHjt2+RVvkOYhjSYjqojws//Vc4Eqhq7y3qpzYtTmqKuNe6UcNk+Qcd+rh884rmirIuASKZUkqL4DURWSD2FEMDTEB5XXvCSFaFs8aya5r6SgVLeg6l/gAe2Cq08v5k9BVPKo4sgnwpTLrmp9oArM754n8ABBwhE8BUSBr6rrrbUu0/E4gxGYfyUPIXFKLqeVzRpPQhz9aswr5o/Jh8ClT+G5nJP+5A8G/zEF/wBsC73EuVU0/gAAAABJRU5ErkJggg==
        ''',
        '''
        iVBORw0KGgoAAAANSUhEUgAAACkAAAAoCAYAAABjPNNTAAAACXBIWXMAAAR2AAAEdgG9ParHAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAARySURBVHgBzVjffds2ED5Qfm7FCcpMYGWCshNITtxn2xM4mcDUBEkncPzc1lInMDtB2AnCTkD2PSZ6f0ASlECKoKVf8vlnCaRwwMfD4bsDFRzCpoiggpjbGkqYQQoXYXnAZo6fC7SL+DqADG0ymAgFQ+Q03GMrdlglOOm6x+4W7RJszXd+ydHuF7TL4SgkN8UCJ3pyTGQjgzfh686dP4t7HPEahlDBBVyGW/BA4LyrYWMIlthe48QhElL4TaQeTK8FkkosgtcWwZS9JjYhjnED5EmZ8d6Ew2jse1Imu+f2bHYNyx8e9vpsig1OvOKHUPCKY/Sx+ILXEZN5E75y2NDqfAZxwhrehgmMROCgfWVaqZMg4Sv8ZlrkkRh+L2JDkOxvnDaycVLTZwkecC23LIUK8l6rX8O0aVfYX3Vit99Ow9+dOUYigCnwjKkGCibZuUjK0+pqNUDmyhohY+2sUfXsbhmrXuZ/4EUkn6GWhznLEOlld7LY6CAh5VgTcU/5joI73Hzv9ghW8AHauP0IHnDrJEkLTSbIkVSGj0PfC2jFvWRJqsVZxP+pISIylJmHXUEdhxVuusvwHbyY5D7RXVD2uNhLdftEu5hAcJhkO2mCrXMQT+S8QwNcrqH8LVp7Be3ypkBJ4MJSBQ8EAwSRVLDECTTQ0rYZ40cAXvY+uxj7/Ay2NzW3lyzoE6Dc5ICKBFqWIcnIWbhr74zL94TU2OUwEmfQJeiKqcxsgNojC0MkMrtfKiLN0jO3HiDFGPyXrwIMF9l0ZB+b9BiCN8ldgkqhFOm1sw6UmLszRBO0pbsJkiqRUNqJvcfiCu+f4/0b/F6g3S0MZSUHlDXYE0BT3L7HAmBYy+ShqFqSOOsrwR6Lz00fBZ/wc+1bU8rGIc+0BNcHCRJoIirH2g31wZmhFKybPhQSGr5gvzuf1BqYgeo0l/uUUCxDz03VE2E7bn4jEkRGW5mmBoXIc5O1RpCUJ4r5ajZLwBdSEeViHywNwVv2mGhs5LSbodaO9OYZ1oYLNBB8fVasc/7IeOfrKjbeS6zfUrx+4DXTppiuuB5dkIswZlOTvcp+koH1pFSRa3gJIotgZibP+Uoqd0LOXqya0KBvUor3fYMG+LcFT0kYge7JUCqpiNsUUnT/bfgJqkoqf0ocAyvYStBuSeYL8szQ2UjKt3lnY1JMUuxKEvgLz0YrOCkei4/4r/G/8LKjauuA3bTjgwsKfjKtzMtON/3nfat5PJIt/vPqrcHe1ZGry/FI6obcOUxH7rp5TJL1skVep8mzJtuVfTn9eCQDLh7qpeseO0jgSSf/KFY790lXY26rYNs/9LEgGcPWvTuLSAJ1LdmFlderNZycJEExmZzbbeZpvTozR1kSbioN5RQplddA+TZ8EJuC+r2mRnGWY/DG/EJH4K2p0NuzToXevwyvh4Y8Pkkb7Zs2F8qxtesZnAriURfqqmiLabAcM9RpPUmQlwx0rrEPaa8Pvne3cIqM0wUVFN03xBEMndu/OSgEphXV3z/+B0hzxCS5l3n9AAAAAElFTkSuQmCC
        ''',
        '''
        iVBORw0KGgoAAAANSUhEUgAAACkAAAAoCAYAAABjPNNTAAAACXBIWXMAAAR2AAAEdgG9ParHAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAARASURBVHgB1VnbddNAEL2S/Q1WB6ICTAWICpxA+E5SQaCC2BUEKgj+5mDTQUQFMRUgKpDhO9Eys7N6evWM/ME9B7ySdrR3Z+epOGjDNvaRINBjhT0mCHHq7VtkZvT/nOR8fe1iRzI7DISDJnIKtzQKLFJLWnRVI3dFcksazSpPIpJ7Q3IRRiG5jee00J1loSJ2eOu9Kt35Ft/SGy/QhASnOPO+owdc612FrSG4p/GKFvaIkEO/TGptZs2J1LJA8KJAMNRaExmP3nEJ1qSseGvMoTMONSmL3erxZHKBxbP1wZxtvKWFT/QmHLzQNrqJf9G1r8m89V5YZPh07iFKWOGdt0RHuBba52YUWgkyHvDZjFgjAb7GgSHI8pdWGXGc0MxZoAdsxy1H4bhRrdR7L8zGCc13SrZbL6fwo7RGR7gYgp42lcHBIDkbSdmtSk4ayJwX3rDTsTNFUuPd8q70mH/iSSQfkYaHmQ5DHC/LiwUmDjJCbWsS3EN9x8E1Od+HA4IJbpDb7Sf0gD1OcmjhxQQRkdrRdvh3jjy473VISoOzBP+7jIiEoZ3Z7AlSO0zI6c68D3gyyUOiVXD2OD1IdYdEyxhAsJlkvuiSRi8hmoi0h7p0XE35W2LtOfLjDcFJ4LQQFXrAbSBIpNwFLaDAR5tnjOeAPvY6uYDmvEZRm0qPFzqgD4BjJwcuEvhYmkJGpAN3qp1u+Z4RGrkIHTFFmaDNpnbGAVKNzA0R33i/VERKh55ZYQMh2eBvfeWSuYjTsXxg0qOH3iSrBB2HQpFaWetAsblrQ3RJsnx3SaT2RCistb1NfG822au2dAovYIKBHit8pAKgOZbJprZI7bOtBCsXGF/o/ZfoCHEc1kxOcNVKkME2xeVY7lA3tRlK7nNclU1wSce1Z0eIJnMt2susJnAFNNFmUtamZKqriq2W0VGjrtlloK8mkyX6QiqiSOTdhSF4pY+2LUKwRrd/btCCKdWGc9KE4OHR0XGuP3ba81USkPx1IbdzfF3rtJqkG9EFtW+e073kc9vLp6RLP7viilzhKfALBA8bL9mAX3rOFdXmL5lZTYGtafFxi9f5GA82grxOXHr+SKfo6ggBMz+ElWT+Eh9PAffmbb3RJuao8TLLOEKceyO225Cc9g2OCq6aNrGif/HYcsPaBxuczFx6ZRPtVIJZ3WmOR3IoFPZtU45B0u8zudKcWQmPRzI/Nt/SF/m1cpOsOYvqCunxSLqU4jJNuNeG3EynXPbganMmz32TNrnPD+tfPRZYC8p82VCJb8JLXlnZoFAoMpJV3bTmHmcIuOCY6l6oWMatqfC4yOZUy7yWb0Pjk8w1mPcziko015iCMtV5iuoGLJhifMxQrXwc6rsPawL5rHjWXruOr0mGvVeKIIUv/bKTJOvWz9oGxyHJqBLt0pLU4HgZp9peqOFV1vE0mSL964VLztPxeP9L/APSAcUHFahC/AAAAABJRU5ErkJggg==
        ''',
        '''
        iVBORw0KGgoAAAANSUhEUgAAACkAAAAoCAYAAABjPNNTAAAACXBIWXMAAAR2AAAEdgG9ParHAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAR1SURBVHgB7Vjbdds4EL2g/L0WO2AqiFzBciuQnGS/7VTgpAJLFSipQPH3nljZCsKtYJkKzK2A3P+Y2JkB+JIAipSUc/Yj18cWRGOAi8HMxYAKh7DNI5SIpa1RYIIE12FxwGZKf2dkF8n3ACnZpDgSCn3kNDbUih1WS5p05bG7I7sltaY7/8nI7jeyy3AWktt8RhN9dUzURopX4VXnyed8QyPeog8lrvEm/IIRCJxPNbaWYEHtFU0cEiFFn0zqwfaaEalli+Bti2AiXjM2IY3xFuxJM+PGhsNg7HvSTLaR9mRyi/kvD3t9tvmWJl7IIhReSIw+5k/0PRIyr8IXDhvenb9hnLDC63CJgQgctG9sK3ESZHzHR9tij8T4I48tQbZ/67QxiZPYPnOMgGu7zVaoIPNa/R4mdbuk/qoTu347jb86cwxEgGMwMqZqKBxl5yJpVqvLRQ+Zm9YIqWhnhdKT3Wasapu/4SSSz6jkYSoyxHrZnSy2OshIJNaMuCfyROGeku/dHsESazRx+wEj4NZJlhaezCAjUikthz9naMS9EEmqxNmI/9eaiJGh1C52gSoOS0q6N+E7nExyn+gu+PS43jvq9ol2cQTBfpLNpEtqvYTxRCYZGtB29Z3fRmtv0GxvAj4ErluqMAJBD0EiFcxpAg3e2ubEuARk2312MfX5FW1vamnPRdCPgHKTAxcJvC19kpGJcFfeGXbeMxJrl2EgLtAl6Iqp1CZA5ZGZJRLZ7DcVkRbpmbYWkFAM/iPfAgoXk3RsH9vjMcRokrsElSIp0itnHWhi7t4SXZItP10SqYIIJd7YY2lStEt9p5IDzXY/5kwwlrbGeyoA+rXMLIqrJRNnY0qwbX4vixsyD6rEYc80BFdDDCWmuBxrEmrtPaF4QZxQVeJomCqJd2P3sPCSbCqfbEwJJTL0XFc9EbXjFrEp/a5ph3Ii9SShxLH4mLNavLS9qpPoAEmz+li+TSZLjIWpiDJjH8wtwTtLzKcQjRQpLMTLPbig2nBGBYLB92d1yMCDVDJfl3Edbw0+WjHPaK4puSXuCD1DSxIm8JIMWp25Itc4BVGLoPvitc1ZLS6tlxs73lHPKRbQzxeMlIQB8BGMJC4bgtUd6qrvmFWdAU7DzEpS390okliVmYNPpFvvJdlYGTSFhUdVGjE/4j7cwed8US+5fP7T2Yfn2OYsP7S1l6m1MyeRORwOkDwVqs7Y/jccu87QcuwypuJph7OOu+PASfISx0CjONTlfCQ1/rWtCGPQvZx5svtc0LXORfUzcxRuepNyUl/OMl+YnC8mX4efKAkiXEyeLKm1vdswuCxb7NmYbL+VtgoS39Dn86QZ7QNldqWFFanMeTtk8a4kS1CufMOez5MGmxY5RmpFvdghOLOvFauqaEXvjzLfoP0XsbFoi3WDwsbrN7kfda/Fg15enZck4zHnrb0b0LMYWruen6SJNfamuQIDfPpw/RjZHhSjAdUL5cPB19o/jCTD3GXWdoarU96X/1jwtrffBP/E/wD/AZqpyeYQfYQPAAAAAElFTkSuQmCC
        ''',
        '''
        iVBORw0KGgoAAAANSUhEUgAAACkAAAAoCAYAAABjPNNTAAAACXBIWXMAAAR2AAAEdgG9ParHAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAARHSURBVHgB7VjbVdtAEJ2V/J2gCiIqiFMBSgV+hHzbVACpALsCkgp8+E6CSQVeKkCpAKUCOf8gZWZnZb1WiySUPy7n4JW8o73amb0zYwHPYRv7kECgxinswQUJM2//jM0R/h+jna+uHQjRJoSeEGAjl8IGR4HBaoWLrhvsztFuhaOjyjcR2n1EuwgGIbmNx7jQzrBQESHMvQ+lOz/jDT5xCTYkMINT7xY6wDHeTWGrCe5xvMaFPSQk8JNIXetZYyS1KhBcFghKtWts4+EzzoB2klfc6HBojfpO8mIbNXbdJUzeXNfmbOMtLjxVLyHgWMXoTfyA174iM/eODTbknXvgTVjDJ28FLeEYaC/0SBoJEh7hmx7RjgTwPQ40QbI/M9rwwZF6zgQ6wORudoVwokarz548jBOcL0qx22yXwl1pjZZwoA86xtQBAnrZmUjy26bJ1EJmUXhCqLQzQ9JwuvlZmZt/w4tIPkEmD0dKhkgvy4sFWgcJUsUai7tUdwRc4uG7qBFM4AryuP0KHWDWSZIWWowRIakQX4c+x5CL+15JUibOLP67AxGWoVC/7BSyOEzw0J16F/BiknWiVVD2mNVSXZ1oGT0I2knmi65w9B54JyJ1Qh10ly1/s9YuIHevBEoCs4IqdIBjIYiknAkukAK5Ns8YbwGU25vsApxzAsXdTNV4ogS9B4SZHFCRQG6xSUakhDvbnXb5niC1XQQtMYIyQVNMhfoAZDsy1kR8ffq5IkqV9BwVXkBiDP5RVw6GCx86sg90evSgM8kqQSFQitK1sQ7kmLvURFdoS3dXSGqPhGRj7JE0CfSSLSsZkLv7JiaCgRqn8AULALuW8UtRtcRx1qME60ayWPl0qVAoftl1PrCLPxhPPScEX1+Fhzlc9V/pyn1tJ5nvornMsoEqIFeFSXk37QeQDs8a54/xkzJRXvIZ4OiHBerKdVfQFVwRRWzvcG7+EU+R3ENDGwHAh2dXKAu5J2rACGvDMe4E4/FJKJ3rjlCd/DQJdI+Tx3OKtYCjqvkQ1/Jh5OBJT2h3/RKxJ5U6penhohSPw6Kso1XU0269Z9Jw8O8WOkpCC+x1ZyiN327/nuO67yp3x02l4UgH63GtJOsK6s2LCjFvyCjkuTQxyZsEdr+EGskMPfrhyuK+Hu2tGpug19yD537hi5EnQ1vBMoKhIAo6aAOrQS5znBTuUQahSWeHI9kXdOLdwwtyr1/BkDtJLqYyjttdPgS+WtQWSuXmrEHMhwIXIkTwRGWwFGLlRs7vzXAPzVnUFJfD7WT+q0YZwhKjHI9LnufIpmnD7WRSa1Pv9EEw/6LBxclOX+EOJo0FxpAkZeUOtRATo/5yW5xVT6yrlri1N2JdcRNT9Wv6XZKrdOqPym1xq9JwaJJ5yce/hCwss/eaoL24hiHdTUgxg2SYe0tVI4KugJh4pDKMcC7Udy0I/h9Qbu7Zur7iFYh/TDWzU1BUkWAAAAAASUVORK5CYII=
        ''',
        '''
        iVBORw0KGgoAAAANSUhEUgAAACkAAAAoCAYAAABjPNNTAAAACXBIWXMAAAR2AAAEdgG9ParHAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAQ2SURBVHgB7VjRddNKEL27znmfD6sCnAqeqeCJCmIH+I5TAVABdgVABTbfQAwVRFSAqABRgVxALDGzs7KkaLWWHJsvbo7jtb3jvbszc2fWCvuwTkfIEJpxjg0GiDANNntshvR/THYj81ojJpsYB0LBRy7Hkkahw2pOiy5a7F6S3ZxGw3ufJGT3lOwSHIXkOh3TQreOhaqIcRk8qb3zOV3SN87gQ4Ypngdf0APa+W6OtSW4ofGCFg6IkKJnJvXBzhoTqXmF4KxCMDKnJjYBfcc1+CRlxaUNh85onqQstjTjwWCGi38/NOas0zUtPDGbUDg3MXqT/qTXI0PmMjh32LB3vkMOYYFnwRwdoR20r+wochJk3OG9HfGJhPiYhpYg2187bSRxIjvnAj3gcre4Qumk1epFEO3GGc1Xtdhtt8vxrbZGR2gcgp4xtYPCQXYukrLbPJt4yFxVviE22lkga8lu+a7CzT/wIJJbFPIwNDLEellfLLQ6yIhMrIm4R+YdhTeUfK8aBDO8RRm379ADbp1kaeHFBAmRimk7/DxGKe4bI0mFOIv43+6IiAzFdrMTFHGYUdI9D17hwSSbRO+Dq8e0UeqaROs4gKCfZLnonEb/QU4iMRmqyV2++i1ae4XSvRG4CEwrqtAD2kOQSOkLWiAHu7asGI8A4/Y2u5Dm/I/qaeZmfGEE/QAoNzlwk8Bu8UlGYoS7OJ1u9Z4RWbsEHXGGOkFXTMU2AYoTGVsiI5v90hHlRnqGlQ1EFIO/zCtN4SJJx/ahLY8BepO8T1ApkqJ84ewDJebeWKJzsuV350RqQ4Si1thjaVLkJV9VcqB0903KBEMzzvGaGgC/lsmmuFuSODugBetHstr59OlQOH7FdSOIi584s17ivAiFzd7O3kmyPEV3m+UDd0ADEyb10ywTcIambkbUB65w2dJlNUjKaZigau0f96HoJZVeYfro2pbOJdpEvUqWM31LIcPNsHixEWZn1BuO6SQEd1tlFuiP2GR+noVE+IrGqxqRnIScG5E7crnmzdikk0y/NSUXpuXjBsRBUld2q8xuHoIRPVZ2XNfROlaVsjvCnhPX9PcFPSWhA4qbYdQ6Q5LzPTrgzGbaeaMl64+xlSSO7TnFdtI6k6tTRp1RbjqpDiQLHHAfruFzOtktmG2/eudyUil0ruNnOBY4bHJw0nwlGfPrIM9xXSUUnHYdDrsDip9Vmkg6eYhDzTPvsIvYfUh83ToeP/dKGlc7nicF5YQkHwK9u5wN26ecBhFVkae2lkets6RJmZix0nHbtFORDPHP4LH3576yNWRQwmSLtqmnICkZut2uiIj7Iie1vexduWZ7Euc42f2JNFJbIWcXi6iP7KdyJeYfBDQe2w69VIIOreFxSDJu0ne0YGK6GN8PsCV8tb2G45F0QXrNGcorsVxvtyTmJ+ri/+Iv/gR+Aw2UqnBBnfdYAAAAAElFTkSuQmCC
        '''
    ]
    
    classButtonD =  animated_hover_button(root, sync_blue_animation, base_64_black_sync, base_64_gray_sync, anchor = 'w')
    classButtonD.grid()
    
    
    project_folder = '''
    iVBORw0KGgoAAAANSUhEUgAAABkAAAAYCAYAAAAPtVbGAAAACXBIWXMAAAKdAAACnQEbaSIpAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAHaSURBVHgB3VU7bsJAEB1DoKGxkKgxDS1uKKhiTpBEoiecwHACc4PYJwjUCIkbYGoKqGizBVC7oULCeUNsZDn+IipGGnb9dnbf7HwWomcRaTgcKq7r6pjLMTaOJElT0zS3dKdIuq5vSqWSCo00OJ/PVwXRCEQm3SFM4rZaLWo2m7FG6/WahBCUQxZwagCfHP544Z9yuZy4o91uU61Wo9PpRFlkt9u9Y1hBzRtJkiBf3fl8rsWQL+r1+iaChIdbjlNJ9vs9F4aBqQjAfIB8OBwESNKOoAJlFI6xZVkNVsw/KIek3iRJjsejKBaLDfrvEA9ObhKEbIlK9Oc3vNPpCPTaJ7B+eA/wFSpsnEpSqVS4GQfe4X3MOR+Wtyy8UYOq0GDDqpT1JtVq1ej1ekw0ms1mGog0wIa3bPDtgMlY38Lrrr8P+DIzie/R5XKRA97bIRsmlxEezQf4m7y85E48PBbweBDEcPiEQ8l5C5nbd5HEyBjkkwhcPJKEw/UaBoHZTMQkWzwDatoD6JetF3sltPZGfxXmBGClUCiw3fSFuxcP3xdUTiKBHR8goBz7n4h1O666JMopwQryxfvTU4LPDbBv7nwmzp0TbLIjiLnj1YgbXm0fWV12BC7oqeQXgPfWfvaNLkkAAAAASUVORK5CYII=
    '''
    text_references_folder = '''
    iVBORw0KGgoAAAANSUhEUgAAABkAAAAZCAYAAADE6YVjAAAACXBIWXMAAAKdAAACnQEbaSIpAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAGKSURBVHgB3ZW9cYNAEIUXjSIpsDowsSKVcA4UWx3YrgBcgVEHGlUg5wRyBSIjIBARqc8d4AACmAG/ZZAHW/wdZNoZ6e7m3u23yy0L0a2Yxn+maS4wbFp0zm63kzQUwoA8z8+Y621CaJ73+/07DYQIODgJIWg2m10J0jQlz/MoDENeOj18Sk3TttXMp5cJA+bzee2p9XpNQRBQFEWCWixJkiKYOI51LB+uIF22XC6LKMtfo7muy5A/mt4Qdm7b9ise7Rvmiw6tbhjGGdoj7nGrBMEhowQ4PfQr3I2FUQlSGA5KXOpLlw4FZSGoFc+VIaWDDRw8Nu1jz6muB0GyLLtHRqJpfzKZfGMIR0HghF/KjxYJA8xREHZQVlmTHZDp11jIkQugZZ/3xFhInfmoOv+y4HY1FrL5/7i4XzGoTsyQogq4N9U1yIqT3zkitjBY1NOmnCJS20opn9qEgHAwXe2kHqISGfrRiQaY8p3gLhbIXO+huxsE4drHYf7IffY8IpUhMBOgg4Lep5uyH79NoPWmfju1AAAAAElFTkSuQmCC
    '''
    text_reference_file = '''
    iVBORw0KGgoAAAANSUhEUgAAABkAAAAZCAYAAADE6YVjAAAACXBIWXMAAAKdAAACnQEbaSIpAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAE/SURBVHgBzZWNTcMwEIWfow7ACGGDbkDYgA2aTpBsQEaos0DSDdiAbEDZICOwQXgWRoLIPl8dEHzSyU0v9rsf2zFY0bbtnsMD0rydiOI9mPUfTdO8cCjdIsK8G2+jtfaIBLvQAsYYyyC72CRmWy/LMvBnzaCQEiqwAQp1XmjAb4kURXFm1seU0NZMBtoBH/2LCu1iC7Dun80NMdPG1XPlTS9C9ozyOeRgo92unPA9qJHv310rcvH13owk4kpVhhyMuvv6LG33lEjJ9B+ho0OOCKObELgRcpB2V+VPdRT6T33fW+SKkJmNPwt+0P8KBZKIO2ATEriMfWmzRKLnJIDYu+i14qJjOW41hgRS410mTcin+YaoRDwVfgDpnFw4JEuhYdNV/69EguVyDScHXAHnuAt1VolwS95zqJHHE/6Kd/GMdVhokkrkAAAAAElFTkSuQmCC
    '''
    visual_references_folder = '''
    iVBORw0KGgoAAAANSUhEUgAAABkAAAAZCAYAAADE6YVjAAAACXBIWXMAAAKdAAACnQEbaSIpAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAIVSURBVHgB7VW9TgJBEJ4zVNBgQUlyPoFaUNBhRye+ATwB5xMITwDHC6gtIfFsaDlogIREhVBReAkJBRSc4a8Dv4FdcprDE+kMk8zt7uzufPO3c0RH2oMU/miaFsQQ3HHGzufzNh0CAoDEarW6/wGEsJ8pFApZ+itIOp2uBAKBWCQScT0wGo2o2+3y1AB7eqQoyjM8N5wyH39CodCa3Yjlfr+fLMtKkAfNZjOaz+dJROfUGWLfrgsIkb1YLB5rtdr7dDo9XS6X42g0+hEOh++wre4CKZfLPL0Am54gsDzVarVyUiHCQI1Gg0OnxePxpFD0Kzohdy+yAoCVX+q6jkE5w9KYTCaZfr+v0x7kCtJut8fsARSnENtXlmG0eM3zZrPJlfjrsnYF6fV6H2JqOeUimTY8Pd8HxEcHEgD1er3+MBgM1jni3IFUVFiSjYRh5kEgUPhQLBbHGF927JsY/g4CD547nY4BRRUwF0IGHIT8iTb5vCIRUi8QlRx5QQhUKGFZrFQqsfyaNr1NE0dsnLnFmQovuFh4PPGw9h6XLhwAT45tSxogGux32srYE5tf6nA4dMNh91/Q3xhwbalgE28nBeUxthqcw1yXhpFI+BYEsXtEE0xUq9WtZlEh64dIm5ctrTIYVJ5jRVCehewOnJQe4t6N01L5P1Hpaz9iD3KcPBlXSdy1IX9z5EHel23GPPT/c6R/Qp84mw1O8b4PhAAAAABJRU5ErkJggg==
    '''
    drawing_reference_file = '''
    iVBORw0KGgoAAAANSUhEUgAAABkAAAAZCAYAAADE6YVjAAAACXBIWXMAAAKdAAACnQEbaSIpAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAHHSURBVHgB7VTRUcJAEN1k8k86MHQAFQgd2IHYAEkHJhWY0ABQgVqBsQLpgLMCsYL4nrPn3MSDRMUZPngzm8vtbfbtbnZP5IwfIMiybIR1JH/HrizLBy9JmqZbrIkcAU3T5IvFovCRNEEQ3CCKlVUiu1g0O+jrLuewn4FguY8obH8wn89vYbiFPFGYKZxcSQ8g2AKS08deEh7SCLKGjCFTqDcguwfRpIsEWec+oqgVyQzLCsaZo671v1FXHyJh2bAYBqZEwtJFjkGCiBMcPrY/hu4ZZ5fSAftfnO9yLEXksd1JTzAwfd1oaS0Mj0GachPJL6BZLyET33lVVZy/r2B9JLF0gF3Hla2PxWiZSJyFYfjetveRJB6nA5IjuhzvF7RheewMQT+G/g0EgTtvFqHHYerUWrR1OScxzq71nTDWBo5ZGoq3CqFHR2dbtC0H8UVLQwcGtR4igyH39qcSOhMkqH0kkScTzkMMZyPdlyjD1LYwo0Z2BfZ3CGKmAbB81b4r6BsJHL7CeO3q4NRtTxKV0NV45Z014A1x6I77vCC1KziEiUbWnpVYxUhPaDkztjMz2SGSkmWR48PwEfEixDqR/0EtZ5wkPgAX6/gDWUFnCAAAAABJRU5ErkJggg==
    '''
    


    
    tree = tree_view(root)
    tree.grid()
    tree['columns'] = ('one')
    tree.heading("#0",text="",anchor=tk.W)
    tree.heading("one", text="Added",anchor=tk.W)
    tree.insert_with_icon('', 'end', project_folder, text='item 1', open=True)
    tree.insert_with_icon('', 'end', text_references_folder, text='item 2')
    tree.insert_with_icon('', 'end', visual_references_folder, text='item 2')
    tree.insert_with_icon('I001', 'end', text_reference_file, text='item 11', open=False)
    tree.insert_with_icon('I001', 'end', drawing_reference_file, text='item 12', open=False)
    tree.insert_with_icon('I004', 'end', drawing_reference_file, text='item 121', open=False)

    
    canvas = expandable_list_canvas(root)
    canvas.grid(row=2, column=1)
    
    autocompleteList = [ 'Dora Lyons (7714)', 'Hannah Golden (6010)', 'Walker Burns (9390)', 'Dieter Pearson (6347)', 'Allen Sullivan (9781)', 'Warren Sullivan (3094)', 'Genevieve Mayo (8427)', 'Igor Conner (4740)', 'Ulysses Shepherd (8116)', 'Imogene Bullock (6736)', 'Dominique Sanchez (949)', 'Sean Robinson (3784)', 'Diana Greer (2385)', 'Arsenio Conrad (2891)', 'Sophia Rowland (5713)', 'Garrett Lindsay (5760)', 'Lacy Henry (4350)', 'Tanek Conley (9054)', 'Octavia Michael (5040)', 'Kimberly Chan (1989)', 'Melodie Wooten (7753)', 'Winter Beard (3896)', 'Callum Schultz (7762)', 'Prescott Silva (3736)', 'Adena Crane (6684)', 'Ocean Schroeder (2354)', 'Aspen Blevins (8588)', 'Allegra Gould (7323)', 'Penelope Aguirre (7639)', 'Deanna Norman (1963)', 'Herman Mcintosh (1776)', 'August Hansen (547)', 'Oscar Sanford (2333)', 'Guy Vincent (1656)', 'Indigo Frye (3236)', 'Angelica Vargas (1697)', 'Bevis Blair (4354)', 'Trevor Wilkinson (7067)', 'Kameko Lloyd (2660)', 'Giselle Gaines (9103)', 'Phyllis Bowers (6661)', 'Patrick Rowe (2615)', 'Cheyenne Manning (1743)', 'Jolie Carney (6741)', 'Joel Faulkner (6224)', 'Anika Bennett (9298)', 'Clayton Cherry (3687)', 'Shellie Stevenson (6100)', 'Marah Odonnell (3115)', 'Quintessa Wallace (5241)', 'Jayme Ramsey (8337)', 'Kyle Collier (8284)', 'Jameson Doyle (9258)', 'Rigel Blake (2124)', 'Joan Smith (3633)', 'Autumn Osborne (5180)', 'Renee Randolph (3100)', 'Fallon England (6976)', 'Fallon Jefferson (6807)', 'Kevyn Koch (9429)', 'Paki Mckay (504)', 'Connor Pitts (1966)', 'Rebecca Coffey (4975)', 'Jordan Morrow (1772)', 'Teegan Snider (5808)', 'Tatyana Cunningham (7691)', 'Owen Holloway (6814)', 'Desiree Delaney (272)', 'Armand Snider (8511)', 'Wallace Molina (4302)', 'Amela Walker (1637)', 'Denton Tillman (201)', 'Bruno Acevedo (7684)', 'Slade Hebert (5945)', 'Elmo Watkins (9282)', 'Oleg Copeland (8013)', 'Vladimir Taylor (3846)', 'Sierra Coffey (7052)', 'Holmes Scott (8907)', 'Evelyn Charles (8528)', 'Steel Cooke (5173)', 'Roth Barrett (7977)', 'Justina Slater (3865)', 'Mara Andrews (3113)', 'Ulla Skinner (9342)', 'Reece Lawrence (6074)', 'Violet Clay (6516)', 'Ainsley Mcintyre (6610)', 'Chanda Pugh (9853)', 'Brody Rosales (2662)', 'Serena Rivas (7156)', 'Henry Lang (4439)', 'Clark Olson (636)', 'Tashya Cotton (5795)', 'Kim Matthews (2774)', 'Leilani Good (5360)', 'Deirdre Lindsey (5829)', 'Macy Fields (268)', 'Daniel Parrish (1166)', 'Talon Winters (8469)' ]
    def matches(fieldValue, acListEntry):
        pattern = re.compile(re.escape(fieldValue) + '.*', re.IGNORECASE)
        return re.match(pattern, acListEntry)
    
    
    canvas1 = tk.Canvas(root)
    canvas1.grid(row=0, column=1)
    canvas1.config(background='white')
    c = custom_entry(canvas1, 0,0,autocompleteList=autocompleteList,placeholder='Name')
    
    d = custom_entry(canvas1, 0,70,autocompleteList=autocompleteList,placeholder='Surname')
    
    image1 = tk.PhotoImage(data=reposition)
    image2 = tk.PhotoImage(data=position_dark_gray)
    
    def test():
        print("Hello")
    tags=('0','0','reposition')
    button = rounded_image_button(canvas1, 0, 140, 10, text='Itumeleng Mabote', icon_image=image2, borderwidth=1, tags=tags) 
    buttonA = rounded_text_button(canvas1, 0, 180, 10, text='Itumeleng Mabote', borderwidth=1) 
 

    def redraw(event):
        global c,d,e, button, buttonA
        print ('doing')
        c.draw(0)
        d.draw(0)
        c.error('Error')
        button.draw(0)
        buttonA.draw(8,200)
    
    canvas1.bind('<Configure>', redraw)  # canvas is resized
    canvas1.update()
    #c.error('Wrong stuff')
    
    canvas2 = image_gallery_canvas(root)
    canvas2.insert_image_elements('0',ImageTk.PhotoImage(Image.new('RGBA', (300, 150), '#E3E3E3FF')))
    canvas2.insert_image_elements('1',ImageTk.PhotoImage(Image.new('RGBA', (300, 150), '#E3E3E3FF')))
    canvas2.insert_image_elements('2',ImageTk.PhotoImage(Image.new('RGBA', (100, 150), '#E3E3E3FF')))
    canvas2.insert_image_elements('3',ImageTk.PhotoImage(Image.new('RGBA', (150, 100), '#E3E3E3FF')))
    canvas2.insert_image_elements('4',ImageTk.PhotoImage(Image.new('RGBA', (100, 150), '#E3E3E3FF')))
    canvas2.insert_image_elements('5',ImageTk.PhotoImage(Image.new('RGBA', (100, 150), '#E3E3E3FF')))
    canvas2.insert_image_elements('6',ImageTk.PhotoImage(Image.new('RGBA', (150, 100), '#E3E3E3FF')))
    canvas2.insert_image_elements('7',ImageTk.PhotoImage(Image.new('RGBA', (150, 100), '#E3E3E3FF')))
    canvas2.insert_image_elements('8',ImageTk.PhotoImage(Image.new('RGBA', (150, 100), '#E3E3E3FF')))
    canvas2.grid(row=1, column=1)

    
    canvas3 = tk.Canvas(root)
    canvas3.grid(row=0, column=2)
    canvas3.config(background='white')

    loading = loading_animation(canvas3)

    def redraw(event):
        global loading
        loading.draw(50,50)


    canvas3.bind('<Configure>', redraw)  # canvas is resized
    canvas3.update()


    root.mainloop()