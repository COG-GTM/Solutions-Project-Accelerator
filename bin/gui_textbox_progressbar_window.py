import logging
import os
import time
from threading import Thread
import tkinter as tk
from tkinter import ttk, font
from tkinter import messagebox
import tkinter.scrolledtext as scrolledtext
import traceback


class ProcessCancelled(Exception):
    """Raised by long-running workers to signal a user-initiated cancel."""
    pass


class function_control():
        def __init__(self) -> None:
            self.__stopped = False
            self.__stop = False

        def stop(self):
            self.__stop = True

        def should_stop(self):
            return self.__stop

        def stopped(self):
            self.__stop = False
            self.__stopped = True

        def is_stopped(self):
            return self.__stopped

class texbox_progressbar_window():
        
    def __init__(self, process, title,*args, **kwargs):
        self.__win = tk.Toplevel()
        self.__title = title
        self.__function_control = function_control()
        self.__done = False
        self.__error_found = False
        self.__args = args
        self.__done_function = kwargs.pop('done_function', None)
        self.__auto_close = kwargs.pop('auto_close', False)
        self.__kwargs = kwargs
        self.__setup_window()
        self.__process = process
        self.__start_process()
        self.__win.wait_visibility()
        self.__win.grab_set()
        self.__win.wait_window()
        
        

    def __setup_window(self):

        self.__win.geometry('460x240')
        self.__win.resizable(False, False)
        this_dir = os.path.dirname(os.path.realpath(__file__))  # directory of this file
        self.__win.iconbitmap(os.path.join(this_dir, 'logo.ico'))  # set logo icon
        self.__win.title(self.__title)
        #self.__win.attributes('-toolwindow',True)
        self.__win.protocol('WM_DELETE_WINDOW', self.__destroy)
        self.__textbox = scrolledtext.ScrolledText(self.__win, width=69,height=8,
                                                relief=tk.FLAT,highlightbackground='#7A7A7A',
                                                highlightcolor='#7A7A7A',highlightthickness=1)
        self.__textbox.bind("<Key>", lambda e: "break")
        self.__textbox['font'] = font.nametofont("TkDefaultFont")
        self.__textbox.place(x = 10 , y = 20)
        self.__textbox.insert('end','Starting...')
        self.__create_text_right_click_menu()

        self.__label = tk.Label(self.__win, text="Starting...",justify=tk.LEFT)
        self.__label.place(x = 10 , y = 150)


        self.__progressbar = ttk.Progressbar(self.__win, orient = tk.HORIZONTAL,
              length = 440, mode = 'determinate')
        
        self.__progressbar.place(x=10, y=175)

        self.__button = ttk.Button(self.__win,text='Cancel',command=self.__destroy)
        self.__button.place(x = 375, y = 205)

    
    def __destroy(self):

        if self.__done:
            self.__win.destroy()
            return


        answer = messagebox.askyesno('Cancel', 'Are you sure you want to cancel?'
                            ,parent=self.__win, default='no')
        if answer:
            self.__function_control.stop()

    def __create_text_right_click_menu(self):
        self.menu = tk.Menu(self.__textbox, tearoff=0)
        self.menu.add_command(label="Copy")

        self.__textbox.bind("<Button-3><ButtonRelease-3>", self.show_textmenu)
        self.__textbox.bind('<Control-c>', self.copy)

    def copy(self, event=None):
        self.__textbox.clipboard_clear()
        text = self.__textbox.get("sel.first", "sel.last")
        self.__textbox.clipboard_append(text)

    def show_textmenu(self, event):
        e_widget = event.widget
        self.menu.entryconfigure("Copy",command=lambda: e_widget.event_generate("<<Copy>>"))
        self.menu.tk.call("tk_popup", self.menu, event.x_root, event.y_root)

    def __start_process(self):
        self.__thread = Thread(target=self.__run_process)
        self.__thread.start()
        self.__win.after(500, self.__check_progress)
        


    def __run_process(self):
        try:
            self.__process(self.__update_progress_and_check_if_should_stop, *self.__args, **self.__kwargs)
        except ProcessCancelled:
            # User cancelled; __check_progress will destroy the window once is_stopped() is True.
            self.__function_control.stopped()
        except Exception as error:
            self.__update_progress_and_check_if_should_stop('Error: '+str(error),'Error',error_found=True)
            logging.error('Failed: "{}" with error: {}'.format(self.__title,str(traceback.print_exc())))
        else:
            self.__progressbar['value'] = 100



    def __check_progress(self):
        if self.__progressbar['value'] < 100 and not self.__error_found:
            self.__win.after(500,self.__check_progress)
            if self.__function_control.is_stopped():
                self.__win.destroy()
        elif self.__error_found:
            self.__button.config(text='Close')
            self.__label.config(text='Error')
            self.__textbox.insert('end','\nStopped')
            self.__textbox.see('end')
            self.__done = True
        else: 
            self.__button.config(text='Close')
            self.__label.config(text='Done')
            self.__textbox.insert('end','\nDone')
            self.__textbox.see('end')
            self.__done = True
            if self.__done_function is not None:
                self.__done_function()
            if self.__auto_close:
                self.__win.after(100, self.__win.destroy)


        if self.__function_control.should_stop():
            self.__label.config(text='Stopping...')
            

    def __update_progress_and_check_if_should_stop(self, textbox_insert, label_text, percentage_done=None,error_found=False ):
        if percentage_done is not None:
            self.__progressbar['value'] = percentage_done
        self.__error_found = error_found
        if textbox_insert is not None and textbox_insert != '':
            self.__textbox.insert('end','\n'+textbox_insert)
            self.__textbox.see('end')
        if label_text is not None and label_text != '':
            self.__label.config(text=label_text)
        if self.__function_control.should_stop():
            self.__function_control.stopped()
            return True



if __name__ == "__main__":

    def process(progress_update_and_check_if_should_stop):
        for i in range(0,101):
            time.sleep(0.1)
            if progress_update_and_check_if_should_stop(str(i),str(i),i):
                break

    def bad_process(progress_update_and_check_if_should_stop):
        raise ValueError('error')
            
        




    def open_Toplevel():
        texbox_progressbar_window(process,'run')
        texbox_progressbar_window(bad_process,'run')

        
    

    root = tk.Tk()
    
    button = tk.Button(root, text = "open toplevel1",
                command = open_Toplevel)
    button.place(x = 75, y = 50)

    root.mainloop()
