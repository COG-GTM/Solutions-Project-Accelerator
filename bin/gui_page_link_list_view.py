import tkinter as tk
from typing import List


try:
    from .gui_base64_icons import goto_dark_gray_20, delete_mini_icon
    from bin.gui_elements import custom_label
except ImportError as error:
    from gui_base64_icons import goto_dark_gray_20, delete_mini_icon
    from gui_elements import custom_label



class page_link_view():
    def __init__(self, canvas: tk.Canvas, x_offset, y_offset,index, page_link_name, pno, roi_name,
            select_callback=None, goto_callback=None, delete_callback=None) -> None:
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.__index = index
        self.__canvas = canvas
        self.__pno = pno
        self.__roi_name = roi_name
        self.__page_link_name = page_link_name
        self.__text_location_label = None 
        self.__select_callback = select_callback
        self.__selected = False
        self.__goto_callback_func = goto_callback
        self.__delete_callback_func = delete_callback
        self.__unhighlighted_color = '#FFFFFF'
        self.__goto_image = tk.PhotoImage(data=goto_dark_gray_20)
        self.__delete_image = tk.PhotoImage(data=delete_mini_icon)

    def get_roi_uid(self):
        return self.__roi_name

    def goto_callback(self):
        if self.__goto_callback_func:
            self.__goto_callback_func(self.__page_link_name)

    def draw(self, x=0, y=0):
        self.__delete_static_elements()
        

        self.x = self.x_offset + x # For static elements
        self.y = self.y_offset + y # For static elements
        self.__rect = self.__canvas.create_rectangle(self.x ,self.y - 2 ,self.__canvas.winfo_width() ,self.y + 28 ,fill='#FFFFFF', width = 0, tags=('add_text_location'))
        self.__text_location_label = self.__canvas.create_text(self.x + 8, self.y + 4,  
                                                                text=self.__page_link_name, 
                                                                font=('Arial',10,'normal'), 
                                                                anchor=tk.NW, 
                                                                fill="#707070")
       
        self.__canvas.tag_bind(self.__rect,'<Enter>', self.__on_enter)
        self.__canvas.tag_bind(self.__rect,'<Leave>', self.__on_leave)
        self.__canvas.tag_bind(self.__text_location_label,'<Enter>', self.__on_enter)
        self.__canvas.tag_bind(self.__text_location_label,'<Leave>', self.__on_leave)
        self.__canvas.tag_bind(self.__rect,'<Button-1>', self.__on_click)
        self.__canvas.tag_bind(self.__text_location_label,'<Button-1>', self.__on_click)
        self.__draw_delete_button()
        self.__draw_goto_button()
    
    def __on_enter(self,_):
        self.__canvas.itemconfig(self.__rect, fill='#E5E5E5')


    def __on_leave(self,_):
        if not self.__selected:
            self.__canvas.itemconfig(self.__rect, fill='#FFFFFF')

    def __on_click(self,_):
        if self.__select_callback:
            self.__select_callback(self.__index,self.__page_link_name,self.__pno,self.__roi_name)

    def hide(self):
        self.__delete_static_elements()

    def __delete_static_elements(self):
        if self.__text_location_label:
            self.__canvas.delete(self.__text_location_label)
            self.__canvas.delete(self.__goto_rect)
            self.__canvas.delete(self.__goto_icon)
            self.__canvas.delete(self.__delete_rect)
            self.__canvas.delete(self.__delete_icon)
            self.__canvas.delete(self.__rect)

    def select(self):
        self.__selected = True
        self.__canvas.itemconfig(self.__rect, fill='#E5E5E5')

    def unselect(self):
        self.__selected = False
        self.__canvas.itemconfig(self.__rect, fill='#FFFFFF')

    
    def __draw_delete_button(self):
        self.__delete_rect = self.__canvas.create_rectangle(self.__canvas.winfo_width() - 64 ,self.y ,self.__canvas.winfo_width() - 40,self.y+24,fill=self.__unhighlighted_color, width = 0, tags=('delete_button'))


        self.__delete_icon = self.__canvas.create_image( self.__canvas.winfo_width() - 62,self.y  + 2 , image=self.__delete_image, anchor=tk.NW, tags=('delete_button'))

        self.__canvas.tag_bind(self.__delete_rect,'<Enter>', self.__on_delete_enter)
        self.__canvas.tag_bind(self.__delete_rect,'<Leave>', self.__on_delete_leave)
        self.__canvas.tag_bind(self.__delete_icon,'<Enter>', self.__on_delete_enter)
        self.__canvas.tag_bind(self.__delete_icon,'<Leave>', self.__on_delete_leave)
        self.__canvas.tag_bind(self.__delete_rect,'<Button-1>', self.__on_delete_click)
        self.__canvas.tag_bind(self.__delete_icon,'<Button-1>', self.__on_delete_click)


    def __on_delete_enter(self,_):
        self.__canvas.itemconfig(self.__delete_rect, fill='#E5E5E5')


    def __on_delete_leave(self,_):
        self.__canvas.itemconfig(self.__delete_rect, fill=self.__unhighlighted_color)


    def __on_delete_click(self,_):
        if self.__delete_callback_func:
            self.__delete_callback_func(self.__pno, self.__roi_name)

    def __draw_goto_button(self):
        self.__goto_rect = self.__canvas.create_rectangle(self.__canvas.winfo_width() - 32 ,self.y ,self.__canvas.winfo_width() - 8,self.y+24,fill=self.__unhighlighted_color, width = 0, tags=('goto_button'))
        
        
        self.__goto_icon = self.__canvas.create_image( self.__canvas.winfo_width() - 30,self.y  + 2 , image=self.__goto_image, anchor=tk.NW, tags=('goto_button'))
        
        self.__canvas.tag_bind(self.__goto_rect,'<Enter>', self.__on_goto_enter)
        self.__canvas.tag_bind(self.__goto_rect,'<Leave>', self.__on_goto_leave)
        self.__canvas.tag_bind(self.__goto_icon,'<Enter>', self.__on_goto_enter)
        self.__canvas.tag_bind(self.__goto_icon,'<Leave>', self.__on_goto_leave)
        self.__canvas.tag_bind(self.__goto_rect,'<Button-1>', self.__on_goto_click)
        self.__canvas.tag_bind(self.__goto_icon,'<Button-1>', self.__on_goto_click)

    def __on_goto_enter(self,_):
        self.__canvas.itemconfig(self.__goto_rect, fill='#E5E5E5')


    def __on_goto_leave(self,_):
        self.__canvas.itemconfig(self.__goto_rect, fill=self.__unhighlighted_color)


    def __on_goto_click(self,_):
        if self.__goto_callback_func:
            self.__goto_callback_func(self.__pno, self.__roi_name)


class page_links_list_view():

    
    def __init__(self, canvas: tk.Canvas, path,  x_offset=0, y_offset=0, internal_db=None) -> None:
        self.__path = path
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.__canvas = canvas
        self.__page_links: List[page_link_view] = []
        self.__unlinked_page_links: List[page_link_view] = []
        self.__page_link_label = None
        self.__goto_callback_func = None
        self.__db = internal_db
        self.__db.subscribe_to_changes_for_tool_viewer(self.__internal_database_page_link_deleted)
        self.__page_link_label = custom_label(self.__canvas, 0, 0, text="Page Links", fill= '#505050',size=16,weight="bold")
        self.__unlinked_page_link_label = custom_label(self.__canvas, 0, 0, text="Unlinked Page Links", fill= '#505050',size=16,weight="bold")
        self.__description_label =None
        self.__unlinked_description_label = None
        self.__empty_label = None


    def subscribe_to_goto(self, callback):
        self.__goto_callback_func = callback

    def redraw(self, _):
        self.draw()

    def draw(self, x=12, y=0):
        self.__delete_static_elements()


        self.x = self.x_offset + x # For static elements
        self.y = self.y_offset + y # For static elements
        self.__page_link_label.draw()
        self.__description_label = self.__canvas.create_text(self.x +4,self.y + 26, text='Page links found in other pages.', anchor=tk.NW, fill="#6F6F6F")
        page_links_y_offset = 48 + y
        for page_link in self.__page_links:
            page_link.draw(x,page_links_y_offset)
            page_links_y_offset = page_links_y_offset + 30 

        self.__unlinked_page_link_label.draw(0, page_links_y_offset + 16)
        self.__unlinked_description_label = self.__canvas.create_text(self.x +4,page_links_y_offset + 42, text='Page links not linked to any page.', anchor=tk.NW, fill="#6F6F6F")
        page_links_y_offset = page_links_y_offset + 64

        for page_link in self.__unlinked_page_links:
            page_link.draw(x,page_links_y_offset)
            page_links_y_offset = page_links_y_offset + 30

        if len(self.__page_links) == 0 and len(self.__unlinked_page_links) == 0:
            self.__empty_label = self.__canvas.create_text(self.__canvas.winfo_width()/2 - self.x - 4,self.y + 56, text='No page links found.', anchor=tk.CENTER, fill="#6F6F6F")

        self.__canvas.config(scrollregion=(0,0,self.__canvas.bbox(tk.ALL)[2],self.__canvas.bbox(tk.ALL)[3]))
        return page_links_y_offset - y



    def add_page_link(self, page_number: int, roi_name: str):

        name = 'Page '+str(page_number + 1)
        view = page_link_view(self.__canvas, 
                                self.x_offset, 
                                self.y_offset, 
                                len(self.__page_links),
                                name,
                                page_number,
                                roi_name,
                                self.__select_callback,
                                goto_callback=self.__goto_callback,
                                delete_callback=self.__delete_callback)
        self.__page_links.append(view)
        self.__redraw()


    def add_unlinked_page_link(self, page_number: int, roi_name: str, page_name:str=None):
        if page_name:
            name = page_name
        else:
            name = 'Page '+str(page_number + 1)
        view = page_link_view(self.__canvas, 
                                self.x_offset, 
                                self.y_offset, 
                                len(self.__unlinked_page_links),
                                name,
                                page_number,
                                roi_name,
                                self.__select_callback,
                                goto_callback=self.__goto_callback,
                                delete_callback=self.__delete_callback)
        self.__unlinked_page_links.append(view)
        self.__redraw()

    

    def __redraw(self): # TODO: Make more elegent, function has code smell
        for page_link in self.__page_links:
            page_link.hide()
        for page_link in self.__unlinked_page_links:
            page_link.hide()
        self.draw(self.x - self.x_offset, self.y - self.y_offset)


    
    def clear_text_locations(self):
        self.__text_locations = {}


    def __delete_static_elements(self):
        if self.__page_link_label:
            self.__canvas.delete(self.__description_label)
            self.__canvas.delete(self.__unlinked_description_label)
            self.__page_link_label.hide()
            for page_link in self.__page_links:
                page_link.hide()

            for page_link in self.__unlinked_page_links:
                page_link.hide()
            
            if self.__empty_label:
                self.__canvas.delete(self.__empty_label)


    
    def __select_callback(self,index,name,pno,roi_name):
        self.__selected_page_link = index
        


    def __goto_callback(self, pno, roi_name):
        if self.__goto_callback_func:
            self.__goto_callback_func(roi_name,pno,self.__path)


    def __delete_callback(self, pno, roi_name):
        if self.__db:
            self.__db.delete_page_link(self.__path, pno, roi_name)


    def __internal_database_page_link_deleted(self, path, roi_name):
        """ Callback function when the internal database has changed """
        if path != self.__path:
            return

        def remove_page_link_by_roi(page_link_list):
            to_remove = None
            for index, page_link in enumerate(page_link_list):
                if page_link.get_roi_uid() == roi_name:
                    to_remove = index
                    break
            
            if to_remove is not None:
                page_link_list[to_remove].hide()
                del page_link_list[to_remove]
                return True
            return False
        
        changed = remove_page_link_by_roi(self.__page_links)
        changed = remove_page_link_by_roi(self.__unlinked_page_links) or changed
        
        if changed:
            self.__redraw()


if __name__ == '__main__':

    root = tk.Tk()

    canvas = tk.Canvas(root, bg="white", height=600, width=300)
    
    lv = page_links_list_view(canvas,0,0)



    def draw(_):
        lv.draw()
        lv.add_page_link(0,'hello')
        lv.add_page_link(2,'hello')

    canvas.bind("<Configure>", draw)
    canvas.update()

    canvas.pack()
    root.mainloop()