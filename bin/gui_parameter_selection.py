import tkinter as tk
from tkinter import font
from typing import List
from uuid import uuid4 
from PIL import Image, ImageDraw, ImageTk

from bin.gui_link_view import link_view

class drop_down_selector():
    def __init__(self,canvas:tk.Canvas,name:str,selection:str,options:List,id=None,listboxLength=None,selection_callback=None) -> None:
        self.__selection = selection
        self.__canvas = canvas
        self.__options = options
        self.__id = id
        self.__name = name
        self.__selection_callback = selection_callback
        self.__uuid = uuid4()
        self.__rect = None 
        self.__text = None
        self.__listbox = None
        self.__listboxUp = False
        if listboxLength:
            self.__listboxLength = 2
        else:
            self.__listboxLength = len(options)
        arrow = Image.new('RGBA', (15, 15), '#00000000')
        draw = ImageDraw.Draw(arrow)
        draw.line([(0, 4), (7, 11), (14, 4) ], fill=(220,220,220,255),width=2)
        self.__arrow = ImageTk.PhotoImage(arrow)
        self.__link_view = link_view(self.__canvas,
                                        0,
                                        0,
                                        self.__linked_callback,
                                        self.__goto_callback)


    def draw(self,x=0,y=0,length=None):
        self.__delete()
        if length is None:
            width = self.__canvas.winfo_width() - 60
        else:
            width = length
        value = str(self.__selection)
        self.__font = font.Font(family="arial.ttf",size=12,weight="normal")
        self.__rect = self.__canvas.create_rectangle(x,y,x+width-28,y+30,fill="#FFFFFF",tag=self.__uuid,outline="#D5D5D5",width=2)
        self.__text = self.__canvas.create_text(x+8,y+7,text=value,tag=self.__uuid,font=self.__font, anchor=tk.NW,fill='#6E6E6E')

        self.__icon = self.__canvas.create_image(x-46+width,y+15,image=self.__arrow,tag=self.__uuid)
        
        self.__link_view.draw(x + width - 24,
                                        y + 2)
        self.__canvas.tag_bind(self.__uuid,"<Button-1>",self.show_options)
        self.__width = width


    def __linked_callback(self, linked):
        """ Links or Unlinks depending on whether the selected text is choosen by the button """
        if linked:
            self.__link_view.disable_goto()
            self.__link_view.link_removed()
            link = False
        else:
            self.__link_view.link_formed()
            self.__link_view.enable_goto()
            link = True

        self.__link_callback(link, [0,-1], self.__selection, self.__name)
            



    def set_go_to_callback(self,callback):
        self.__go_to_callback = callback
        

    def set_link_callback(self,callback):
        self.__link_callback = callback



    def __goto_callback(self):
        self.__go_to_callback()

        
    def enable_linking(self):
        self.__link_view.enable_linking()


    def disable_linking(self):
        self.__link_view.disable_linking()


    def __delete(self):
        if not self.__rect:
            return 
        self.__canvas.delete(self.__uuid)
        self.__link_view.hide()
        self.__destroy_listbox()
        self.__listboxUp = False


    def hide(self):
        self.__delete()
        


    def show_options(self,_):
        if self.__listboxUp:
            return

        listbox_font = font.Font(family="arial.ttf",size=13,weight="normal")
        m_len = listbox_font.measure("n")
        width = int((self.__width - 28)/m_len)
        self.__listbox = tk.Listbox(master=self.__canvas, width=width, height=self.__listboxLength, relief='flat',
                        font=listbox_font, background='#F0F0F0',selectbackground="#D3D3D3",
                        selectforeground="#6E6E6E",foreground='#6E6E6E')
        self.__listbox.bind("<<ListboxSelect>>", self.__mouse_selection)
        self.__listbox.bind("<Right>", self.__key_selection)
        self.__listbox.bind("<Up>", self.moveUp)
        self.__listbox.bind("<Down>", self.moveDown)
        self.__canvas.master.bind("<Return>", self.__key_selection)
        coords = self.__canvas.coords(self.__rect)
        x= self.__canvas.canvasx(self.__canvas.winfo_x() + coords[0])
        y= self.__canvas.canvasy(self.__canvas.winfo_y() + coords[3] + 1) #+ self.__canvas.canvasy(coords[3])
        self.__listbox.place(x=x, y=y + 1)
        self.__listboxUp = True
        
    
        self.__listbox.delete(0, tk.END)
        for w in self.__options:
            self.__listbox.insert(tk.END,w)
        for i in range(len(self.__options)):
            if self.__options[i] == self.__selection:
                index = str(i)
                break

        self.__listbox.see(index) # Scroll!
        self.__listbox.selection_set(first=index)
        self.__listbox.activate(index)


    def __key_selection(self, _):
        if self.__listboxUp:
            self.__canvas.itemconfig(self.__text,text=self.__listbox.get(tk.ACTIVE))
            self.__selection = self.__listbox.get(tk.ACTIVE)
            self.__destroy_listbox()
            self.__listboxUp = False

    def __destroy_listbox(self):
        self.__canvas.master.unbind("<Return>")

        if self.__listbox:
            self.__listbox.destroy()
            if self.__id:
                if self.__selection_callback:
                    self.__selection_callback(self.__id,self.__selection)
            else: 
                if self.__selection_callback:
                    self.__selection_callback(self.__selection)

        
    def __mouse_selection(self, event):
        if not self.__listboxUp:
            return 
        self.__canvas.itemconfig(self.__text,text=self.__listbox.get(tk.ANCHOR))
        self.__selection = self.__listbox.get(tk.ANCHOR)
        self.__destroy_listbox()
        self.__listboxUp = False

    
    def get(self):
        return self.__selection
    

    def set_text(self,text):
        self.__selection = text
        self.__canvas.itemconfig(self.__text,text=text)


    def moveUp(self, event):
        if self.__listboxUp:
            if self.__listbox.curselection() == ():
                index = '0'
            else:
                index = self.__listbox.curselection()[0]
            self.__listbox.selection_clear(first=index)            
            if str(index) != '0':
                index = str(int(index) - 1)
            else:
                index = str(self.__listboxLength - 1)
                
            self.__listbox.see(index) # Scroll!
            self.__listbox.selection_set(first=index)
            self.__listbox.activate(index)

    def moveDown(self, event):
        if self.__listboxUp:
            if self.__listbox.curselection() == ():
                index = '0'
            else:
                index = self.__listbox.curselection()[0]
            self.__listbox.selection_clear(first=index)
            if index != (self.__listboxLength - 1):
                index = str(int(index) + 1)
            else:
                index = '0'
                
            self.__listbox.see(index) # Scroll!
            self.__listbox.selection_set(first=index)
            self.__listbox.activate(index) 


class boolean_selector(drop_down_selector):
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

        super().__init__(canvas, self.__placeholder, default, ['False','True'],**kwargs)
        self.__label = None 

    def draw(self,x=0,y=0):
        self.__delete_label()
        self.__label = self.__canvas.create_text(x+16,y, fill = '#505050', text=self.__placeholder,
                                anchor=tk.NW, font=font.Font(family="arial.ttf",size=11,weight="bold"))
        super().draw(x=x+16,y=y+32)

    
    def __delete_label(self):
        if self.__label:
            self.__canvas.delete(self.__label)

    def hide(self):
        self.__delete_label()
        super().hide()





class interger_selector(drop_down_selector):
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
        super().__init__(canvas, self.__placeholder, default,options,**kwargs)

    def draw(self,x=0,y=0):
        self.__delete_label()
        self.__label = self.__canvas.create_text(x+16,y, fill = '#505050', text=self.__placeholder,
                                anchor=tk.NW, font=font.Font(family="arial.ttf",size=11,weight="bold"))
        super().draw(x=x+16,y=y+32)

    def __delete_label(self):
        if self.__label:
            self.__canvas.delete(self.__label)

    def hide(self):
        self.__delete_label()
        super().hide()


class string_selector(drop_down_selector):
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
   
        super().__init__(canvas, self.__placeholder, default,options,**kwargs)

    def draw(self,x=0,y=0,length=None):
        self.__delete_label()
        self.__label = self.__canvas.create_text(x+16,y, fill = '#505050', text=self.__placeholder,
                                anchor=tk.NW, font=font.Font(family="arial.ttf",size=11,weight="bold"))
        super().draw(x=x+16,y=y+32,length=length)


    def __delete_label(self):
        if self.__label:
            self.__canvas.delete(self.__label)

    def hide(self):
        self.__delete_label()
        super().hide()






if __name__ == "__main__":
    root = tk.Tk()
    canvas = tk.Canvas(root)
    canvas.grid(row=0, column=1)
    canvas.config(background='white')
    bool_selector = boolean_selector(canvas)
    limited_selector = drop_down_selector(canvas,'one',['one','two','three'])


    def redraw(event):
        bool_selector.draw(50,50)
        limited_selector.draw(50,100)

    canvas.bind('<Configure>', redraw)  # canvas is resized
    canvas.update()


    root.mainloop()