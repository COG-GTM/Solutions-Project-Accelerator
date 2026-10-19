from bin.gui_tool_frame import tags_page, tool_frame
from bin.logic_acm_data_handler import ACM_Data_Handler
from tkinter import *
from tkinter import ttk
import tkinter as tk
from tkinter import *
from tkinter import ttk
from tkinter import font
from PIL import ImageTk, ImageSequence, ImageDraw
from PIL import Image
from io import BytesIO
import base64
import time 
import os
from threading import Timer
import sys
from PIL import ImageFont
try:
    from .gui_elements import *
    from .gui_base64_icons import *
except ImportError as error:
    from gui_elements import *
    from gui_base64_icons import *




class sort_option_button(hover_toggle_button):
    
    
    def __init__(self, button_canvas, tool_frame, default_index='0', callback=None, **kw):
        self.tool_frame = tool_frame
        self.menu_canvas = tool_frame.get_shown_canvas()[0]
        self.button_canvas = button_canvas
        self.menu_callback = callback
        self.menu_canvas.config(highlightthickness = 0)
        self.selected_index = default_index
        hover_toggle_button.__init__(self,self.button_canvas, sort_blue, sort_dark_gray, sort_light_gray, anchor = 'w',is_toggle=False,callback=self.__show_options)
        
        # custom indicator images
        im_empty = Image.new('RGBA', (15, 15), '#00000000')
        

        self.img_empty = ImageTk.PhotoImage(im_empty, name='img_empty', master=self.menu_canvas)
        self.img_tick = tk.PhotoImage(data=tick_dark_gray)
        self.menu_up = False
        self.options_treeview = None 
        self.options = []

    def set_options(self,options, selected_option):
        self.options = options
        self.selected_index = selected_option
        
    def insert_with_icon(self, parent, index, text='', **kw):

        self.options_treeview.insert(parent,index,image=self.img_empty, text='  '+text,**kw)
            
    def selection(self, event):
        selected_item = self.options_treeview.focus()
        for item in self.options_treeview.get_children():
            self.options_treeview.item(item,image=self.img_empty)
        self.options_treeview.item(selected_item,image=self.img_tick)
        self.selected_index = selected_item
        self.options_treeview.destroy()
        self.menu_up = False
        if self.menu_callback:
            self.menu_callback(selected_item)
        
    def __show_options(self, _, __):
        if not self.menu_up:

            self.menu_canvas = self.tool_frame.get_shown_canvas()[0]
            style = ttk.Style(self.menu_canvas)
            
            if 'Treeitem.myindicator' not in str(style.layout("Treeview.Item")):
                # custom indicator
                style.element_create('Treeitem.myindicator',
                                     'image', 'img_empty', ('user1', '!user2', 'img_empty'), ('user2', 'img_empty'),
                                     sticky='w', width=1, padding=1)
            # replace Treeitem.indicator by custom one
            style.layout('Treeview.Item',
            [('Treeitem.padding',
              {'sticky': 'nswe',
               'children': [('Treeitem.myindicator', {'side': 'left', 'sticky': ''}),
                ('Treeitem.image', {'side': 'left', 'sticky': ''}),
                #('Treeitem.focus', {'side': 'left', 'sticky': '','children':[
                  ('Treeitem.text', {'side': 'left', 'sticky': ''})
                  #]})
                ]
              })]
            )
            style.layout("Treeview", [
                ('Treeview.treearea', {'sticky': 'nswe'})
            ])
            style.map('Treeview', background=[("selected","#E3E3E3")], foreground=[("selected","#101010")])
            style.configure("Treeview", font=(None, 10))
            style.configure("Treeview.Heading", font=(None, 10))
            style.configure('Treeview', rowheight=30) 
            style.configure('Treeview', background='#F5F5F5')


      

            #self.bind("<Button-3>", self.popup)
            
            self.options_treeview = ttk.Treeview(self.menu_canvas,show="tree")
            """ self.insert_with_icon('', 'end', iid='0', text='Page')
            self.insert_with_icon('', 'end', iid='1', text='User')
            self.insert_with_icon('', 'end', iid='2', text='Date')
            self.insert_with_icon('', 'end', iid='3', text='Type') """
            for i in range(len(self.options)):
                self.insert_with_icon('', 'end', iid=str(i), text=self.options[i])
            num = len(self.options_treeview.get_children())
            self.options_treeview.place(x=self.winfo_x()+self.winfo_width(), y=2,height=30*num, width=110, anchor='ne')
            self.options_treeview.item(self.selected_index,image=self.img_tick)
            self.options_treeview.focus_force()
            self.options_treeview.bind("<ButtonRelease-1>", self.selection)
            self.options_treeview.bind("<FocusIn>", self.focus_in)
            self.options_treeview.bind("<FocusOut>", self.focus_out)
            self.options_treeview.bind('<Escape>', self.close)
            self.menu_canvas.bind("<Button-1>", self.outside)
            self.menu_canvas._nametowidget(self.menu_canvas.winfo_parent()).bind("<Button-1>", self.outside)
            #self.menu_canvas._nametowidget(self.menu_canvas.winfo_parent().winfo_parent()).bind("<Button-1>", self.outside)
            self.menu_up = True 
        else:
            self.close(None)
        
    def focus_in(self, event):
        pass
        
    def focus_out(self, event):
        print('event1')
        print(event)
        self.close(None)
        
    def close(self, event):
        if self.options_treeview:
            self.options_treeview.destroy()
            #del self.options_treeview
            self.menu_up = False
        
    def outside(self, event):
        print('event2')
        print(event)
        widget = event.widget
        x = widget.winfo_rootx() + event.x
        y = widget.winfo_rooty() + event.y
        
        if not self.menu_up:
            return
        
        if not (x >= self.options_treeview.winfo_rootx() 
            and x <= self.options_treeview.winfo_rootx() +  self.options_treeview.winfo_width()
            and y >= self.options_treeview.winfo_rooty() 
            and y <= self.options_treeview.winfo_rooty() +  self.options_treeview.winfo_height()):
      
            self.options_treeview.destroy()
            self.menu_up = False
            


class filter_option_button(hover_toggle_button):

    USERS = 'USERS'
    TYPES = 'TYPES'
    PAGES = 'PAGES'
    
    
    def __init__(self, button_canvas, tool_frame: tool_frame, default_index='0', callback=None, apply_filter_callback=None, **kw):
        

        self.tool_frame = tool_frame
        self.button_canvas = button_canvas
        self.menu_canvas = self.tool_frame.get_shown_canvas()[0]
        self.menu_callback = callback
        self.apply_filter_callback = apply_filter_callback
        self.menu_canvas.config(highlightthickness = 0)
        self.selected_index = default_index
        hover_toggle_button.__init__(self,self.button_canvas, filter_blue, filter_dark_gray, filter_light_gray, anchor = 'w',is_toggle=False,callback=self.__show_options)
        
        # custom indicator images
        im_empty = Image.new('RGBA', (15, 15), '#00000000')
        

        self.img_empty = ImageTk.PhotoImage(im_empty, name='img_empty', master=self.menu_canvas)
        self.img_tick = tk.PhotoImage(data=tick_dark_gray)
        self.menu_up = False
        self.elements = []
        self.__acm_data_handler = None


    def __indicate_filter_state(self, filtered):

        if not filtered:
            self.off_image = tk.PhotoImage(data=filter_dark_gray)
            self.on_image = tk.PhotoImage(data=filter_blue)
            self.inactive_image = tk.PhotoImage(data=filter_light_gray)
        else:
            self.off_image = tk.PhotoImage(data=filtered_dark_gray)
            self.on_image = tk.PhotoImage(data=filtered_blue)
            self.inactive_image = tk.PhotoImage(data=filtered_light_gray)

        self.update_images()

        
    
    def set_data_handler(self, data_handler: ACM_Data_Handler):
        self.__acm_data_handler = data_handler
        self.__acm_data_handler.subscribe_to_is_filtered(self.__indicate_filter_state)


    def __get_filter_options(self):
        if not self.__acm_data_handler:
            return
        filters = self.__acm_data_handler.get_object_filter()

        try:
            self.selected_users = filters['users']['values']
        except:
            pass

        try:
            self.selected_types = filters['types']['values']
        except:
            pass
        

    def __get_data(self):

        self.elements = {}
        self.elements[self.USERS] = []
        self.elements[self.TYPES] = []

        if not self.__acm_data_handler:
            return

        self.__objects_df = self.__acm_data_handler.get_all_objects_in_project()
        
        
        self.__groups_df = self.__objects_df.groupby('CatalogNumber')

        for index, _ in self.__groups_df.first().iterrows():
            self.insert_type_element(str(index))


        self.__groups_df = self.__objects_df.groupby('ChangeUser')

        for index, _ in self.__groups_df.first().iterrows():
            self.insert_user_element(str(index))

        
    
        
    def __show_options(self, _, __):
        if not self.menu_up:
            
            self.menu_canvas, self.page_shown = self.tool_frame.get_shown_canvas()
            self.frame = tk.Frame(self.menu_canvas)
            self.frame.place(x=self.winfo_x()+self.winfo_width(), y=2,height=0, width=300, anchor='ne')
            self.__get_filter_options()
            self.frame.rowconfigure(0, weight=1)  # make canvas expandable
            self.frame.columnconfigure(0, weight=1)
            vbar = AutoScrollbar(self.frame, orient='vertical')
            vbar.grid(row=0, column=1, sticky='ns')
            self.inner_options_canvas = Canvas(self.frame,highlightthickness=0,background='#F5F5F5', yscrollcommand=vbar.set)
            self.inner_options_canvas.grid(row=0, column=0, sticky='nswe')
            self.inner_options_canvas.update()
            vbar.configure(command=self.__scroll_y)
            self.inner_options_canvas.rowconfigure(0, weight=1)
            self.inner_options_canvas.bind('<Configure>',self.__redraw)
            self.inner_options_canvas.bind("<FocusIn>", self.focus_in)
            self.inner_options_canvas.bind("<FocusOut>", self.focus_out)
            self.inner_options_canvas.bind('<MouseWheel>', self.__wheel)
            self.inner_options_canvas.bind('<Escape>', self.close)
            
            self.inner_options_canvas.config(scrollregion=(0,0,0,0),background='#F5F5F5')
            self.users_label = None
            self.types_label = None 
            self.__get_data()
            self.__redraw(None)
            self.inner_options_canvas.update()
            self.inner_options_canvas.focus_force()
            self.menu_up = True 
        else:

            self.close(None)

     # noinspection PyUnusedLocal
    def __scroll_y(self, *args, **kwargs):
        """ Scroll canvas vertically and redraw the image """
        self.inner_options_canvas.yview(*args)  # scroll vertically
        print(self.inner_options_canvas.yview())


    def __wheel(self, event):
        self.inner_options_canvas.yview_scroll(int(-1*(event.delta/120)), tk.UNITS)


    def __check_start_page(self,_,__):
        return True 

    def __check_end_page(self,_,__):
        return True 

    def __change_page_filter(self):
        pass
        


    def __redraw(self, _):

        
        self.inner_options_canvas.delete(tk.ALL)
        

        self.pages_label = self.inner_options_canvas.create_text(16,16,text='PAGES', anchor=tk.NW, font=font.Font(family="arial.ttf",size=10,weight="bold"))


        self.start_page_number = custom_entry(self.inner_options_canvas,8,22,enbale_rect=False,width=40,size=9,state=DISABLED,enable_line=False,
                                        focus_out_callback=self.__change_page_filter)
        
        self.start_page_number.draw()
        
        self.start_page_number.entry.configure(validate="key", justify=tk.RIGHT)
        self.start_page_number.entry['validatecommand'] = (self.start_page_number.entry.register(self.__check_start_page),'%P','%d')
    
        
        
        self.inner_options_canvas.create_text(68,44,fill="#2F2F2F",font="Arial 9",
                        text="to", anchor='nw')

        self.end_page_number = custom_entry(self.inner_options_canvas,70,22,enbale_rect=False,width=40,size=9,state=DISABLED,enable_line=False,
                                        focus_out_callback=self.__change_page_filter)
        
        self.end_page_number.draw()
        
        self.end_page_number.entry.configure(validate="key", justify=tk.RIGHT)
        self.end_page_number.entry['validatecommand'] = (self.end_page_number.entry.register(self.__check_end_page),'%P','%d')

        
        canvas_width = self.inner_options_canvas.winfo_width()
        canvas_height = self.inner_options_canvas.winfo_height()

        self.users_label = self.inner_options_canvas.create_text(16,80,text=self.USERS, anchor=tk.NW, font=font.Font(family="arial.ttf",size=10,weight="bold"))
        y_end = self.build_filter_options(16, 114, canvas_width, self.elements[self.USERS],selected_array=self.selected_users)
        
        if self.page_shown == tags_page.__name__:
            self.types_label = self.inner_options_canvas.create_text(16,y_end + 16,text=self.TYPES, anchor=tk.NW, font=font.Font(family="arial.ttf",size=10,weight="bold"))    
            y_end = self.build_filter_options(16, y_end + 40, canvas_width, self.elements[self.TYPES],selected_array=self.selected_types)

        self.apply_button = rounded_text_button(self.inner_options_canvas,
                                                text='APPLY',
                                                padding=8,
                                                font_used=font.Font(family="arial.ttf",size=10,weight="bold"),
                                                callback=self.__apply_filter_settings)
        self.apply_button.draw(canvas_width - self.apply_button.get_size()[0] - 16,y_end + 32)
        
        self.inner_options_canvas.config(scrollregion=(0,0,self.inner_options_canvas.bbox(tk.ALL)[2],self.inner_options_canvas.bbox(tk.ALL)[3]+16))
        self.frame.place_forget()

        if self.inner_options_canvas.bbox(tk.ALL)[3] <= 600:
            self.frame.place(x=self.winfo_x()+self.winfo_width(), y=2,width=300, height=self.inner_options_canvas.bbox(tk.ALL)[3]+16, anchor='ne')
        else:
            self.frame.place(x=self.winfo_x()+self.winfo_width(), y=2,width=300, height=600+16, anchor='ne')

    def __apply_filter_settings(self, _, apply):

        filter = {
            'users': {
                'filtered': apply and len(self.selected_users) > 0,
                'values': self.selected_users
            },
            'types': {
                'filtered': apply and len(self.selected_types) > 0,
                'values': self.selected_types
            },
            'pages': {
                'filtered': (apply and self.selected_start_page != self.start_page 
                                and self.selected_end_page != self.end_page),
                'values':[self.start_page, self.end_page]
            }
        }
        if self.apply_filter_callback:
            self.apply_filter_callback(filter)

        self.frame.destroy()
        self.inner_options_canvas.destroy()
        self.menu_up = False


    def build_filter_options(self, x, y, canvas_width, sub_elements, selected_array):
        x_initial = x 
        y_end = y 
        row_height = 0
        row_cells = []
        spacing = 8
        for i in range(len(sub_elements)):
            sub_elements[i].draw(x,y)
            selected = sub_elements[i].text in selected_array
            sub_elements[i].set_is_on(selected)
            row_cells.append(sub_elements[i])
            w, h = sub_elements[i].get_size()
            x = x + w + 8



            # record the largest image height          
            if (32 + h) >= row_height:
                row_height = spacing + h

            if i < len(sub_elements) - 1:
                w, _ = sub_elements[i+1].get_size()


                # If image wont fit move to next row                     
                if (x + w + spacing) >= canvas_width:
                    y = y + row_height
                    x = x_initial
                    row_height = 0
            y_end = y + row_height


        return y_end
        
        
    def focus_in(self, event):
        print("focus in")
        
    def focus_out(self, event):
        self.frame.destroy()
        self.inner_options_canvas.destroy()
        self.menu_up = False
        
    def close(self, event):
        self.frame.destroy()
        self.inner_options_canvas.destroy()
        self.menu_up = False

    selected_users = []
    selected_types = []

    start_page = 0
    end_page = 0

    selected_start_page = 0
    selected_end_page = 0 


    def insert_user_element(self,id):

        def button_pressed(tags, is_on):
            
            if is_on:
                # Add selected user to selected users
                self.selected_users.append(tags[1])
            else:
                # Remove unselected user from selected users
                self.selected_users = [i for i in self.selected_users if i != tags[1]]

            print(self.selected_users)


        self.elements[self.USERS].append(rounded_text_button(self.inner_options_canvas,
                                                                text= id,
                                                                callback=button_pressed,
                                                                tags=('user',id),
                                                                is_on=id in self.selected_users))
        
    def insert_type_element(self,id):

        def button_pressed(tags, is_on):
            
            if is_on:
                # Add selected user to selected users
                self.selected_types.append(tags[1])
            else:
                # Remove unselected user from selected users
                self.selected_types = [i for i in self.selected_types if i != tags[1]]

            print(self.selected_types)

        self.elements[self.TYPES].append(rounded_text_button(self.inner_options_canvas,
                                                                text= id,
                                                                callback=button_pressed,
                                                                tags=('type',id),
                                                                is_on=id in self.selected_types ))
        
            
class search_button(hover_toggle_button):

    def __init__(self, canvas, default_index='0', callback=None, edit_callback=None, **kw):
        self.canvas = canvas
        self.callback = callback
        self.canvas.config(highlightthickness = 0)
        hover_toggle_button.__init__(self,self.canvas, search_blue, search_dark_gray, search_light_gray, anchor = 'w',is_toggle=False,callback=self.__toggle_search)
        self.searching = False
        self.search_entry = custom_entry(self.canvas, 8,0,placeholder='',edit_callback=edit_callback)
        self.__search_entry_shown = False 
        
    
    def __toggle_search(self, _, __):
        if self.searching:
            self.__hide_search_entry()
            self.searching = False
            
        else:
            self.__show_search_entry()
            self.searching = True
            
            
    def __show_search_entry(self):
        self.search_entry.draw(0, max_x=(self.winfo_x()))
        self.off_image = tk.PhotoImage(data=close_dark_gray)
        self.on_image = tk.PhotoImage(data=close_blue)
        self.__search_entry_shown = True
        self.update_images()
        
    def __hide_search_entry(self):
        self.search_entry.hide()
        self.off_image = tk.PhotoImage(data=search_dark_gray)
        self.on_image = tk.PhotoImage(data=search_blue)
        self.search_entry.entry.var.set('')
        self.canvas.focus_set()
        self.canvas.focus("")
        self.__search_entry_shown = False
        self.update_images()


    def hide_search_entry(self):
        if self.__search_entry_shown:
            self.search_entry.hide()

    def show_search_entry(self):
        if self.__search_entry_shown:
            self.search_entry.draw(0, max_x=(self.winfo_x()))

            
    
        
if __name__ == "__main__":

    root = Tk()

    def callback_A(item):
        print(item)
        
    sort_filter_canvas = tk.Canvas(root, height=50, width=200,background="white")
    canvas = tk.Canvas(root, height=500, width=200,background="white")
    button7 = sort_option_button(sort_filter_canvas, canvas, callback=callback_A)
    search_button_window = sort_filter_canvas.create_window(180, 16, anchor='ne', window=button7)
    button8 = search_button(sort_filter_canvas, callback=callback_A)
    search_window = sort_filter_canvas.create_window(150, 16, anchor='ne', window=button8)
    
    sort_filter_canvas.grid()
    canvas.grid()


    root.mainloop()