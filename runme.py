# -*- coding: utf-8 -*-
import sys
import os
# Zscaler fix
import pip_system_certs.wrapt_requests
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from tkinter.filedialog import askopenfilename
from tkinter import StringVar, messagebox
import tkinter as tk
from tkinter.ttk import Progressbar
from tkinterdnd2 import TkinterDnD
from bin.logic_env_file import load_env_file
from bin.logic_logger import logging, get_logger, logger_init, LoggerManager
from multiprocessing import freeze_support
from bin.gui_base64_icons import full_logo, splash_screen_close

# Must run before modules read deployment-specific settings from os.environ.
load_env_file()



class Splash_Screen:
    def __init__(self):
        
        self.w=tk.Tk()
        
        width_of_window = 427
        height_of_window = 250
        screen_width = self.w.winfo_screenwidth()
        screen_height = self.w.winfo_screenheight()
        x_coordinate = (screen_width/2)-(width_of_window/2)
        y_coordinate = (screen_height/2)-(height_of_window/2)
        self.w.geometry("%dx%d+%d+%d" %(width_of_window,height_of_window,x_coordinate,y_coordinate))
        self.w.overrideredirect(1)
        
        self.__splash_backgorund_color='#00AEEF'
        frame = tk.Frame(self.w,width=427,height=241).place(x=0,y=0)  #249794
        f1 = GradientFrame(frame, self.__splash_backgorund_color ,borderwidth=0)
        f1.pack(side="top", fill="both", expand=True)

        self.logo_img = tk.PhotoImage(data=full_logo)
        logo = tk.Label(self.w, image = self.logo_img, borderwidth=0)
        logo.place(x=20,y=80)

        self.__progress=Progressbar(self.w,orient=tk.HORIZONTAL,length=500,mode='determinate',)
        self.__progress.place(x=-10,y=235)
        
        self.__progress_string = StringVar()
        self.__progress_label =tk.Label(self.w,textvariable=self.__progress_string,
                                        fg='white',bg=self.__splash_backgorund_color)
        self.__progress_string.set("Loading...")
        lst4=('Arial (Body)',9)
        self.__progress_label.config(font=lst4)
        self.__progress_label.place(x=18,y=210)

        self.w.update()
        

    def show_options(self, open_project_callback, new_project_callback, import_project_callback):
        self.__open_project_callback = open_project_callback
        self.__new_project_callback = new_project_callback
        self.__import_project_callback = import_project_callback

        self.close_button_img = tk.PhotoImage(data=splash_screen_close)
        close_button=tk.Button(self.w,text='Close',command=self.close_splash_screen,border=0,
                               image=self.close_button_img,bg='#000507',activebackground='#000507')
        close_button.place(x=405,y=7, width= 20)
        self.__place_buttons()
        self.__progress_label.destroy()
        self.__progress.destroy()
        self.w.mainloop()


    def close_splash_screen(self):
        self.w.destroy()

    def new_project(self):
        self.__new_project_callback()

    def open_project(self):
        self.__open_project_callback(self.__project_choosen.get())

    def import_project(self):
        self.__import_project_callback()


    def project_selected(self, _):
        if not self.__project_choosen.get() == "":
            self.__b4["state"] = tk.NORMAL
        else:
            self.__b4["state"] = tk.DISABLED

    def future_versions(self):
        messagebox.showwarning("Future feature",'Coming soon in later versions.')


    def browse_projects(self):

        self.__b1.place_forget()
        self.__b2.place_forget()
        self.__b3.place_forget()

        projects = Project_File_Manager.get_all_projects()
        n = tk.StringVar()
       
        self.__project_choosen = tk.ttk.Combobox(self.w, width = 30, textvariable = n, state="readonly")
        self.__project_choosen['values'] = projects
        self.__project_choosen.place(x=90,y=200)
        self.__project_choosen.bind("<<ComboboxSelected>>", self.project_selected)

        self.__b4=tk.Button(self.w,width=10,height=1,text='Open',command=self.open_project,border=0,fg="#045F80",bg='white')
        self.__b4.place(x=300,y=200, width= 50)
        self.__b4.config(font=('Arial',9))
        self.__b4["state"] = tk.DISABLED
        self.__b5=tk.Button(self.w,width=10,height=1,text='Cancel',command=self.reset_splash_screen_options,border=0,fg="#045F80",bg='white')
        self.__b5.place(x=360,y=200, width= 50)
        self.__b5.config(font=('Arial',9))


    def reset_splash_screen_options(self):
        self.__b4.place_forget()
        self.__b5.place_forget()
        self.__project_choosen.place_forget()

        self.__place_buttons()

    def __place_buttons(self):
        self.__b1=tk.Button(self.w,width=10,height=1,text='New Project',command=self.new_project,border=0,fg="#045F80",bg='white')
        self.__b1.place(x=90,y=200, width= 100)
        self.__b1.config(font=('Arial',9))
        self.__b2=tk.Button(self.w,width=10,height=1,text='Import Project',command=self.import_project,border=0,fg="#045F80",bg='white')
        self.__b2.place(x=205,y=200, width= 100)
        self.__b2.config(font=('Arial',9))
        self.__b3=tk.Button(self.w,width=10,height=1,text='Browse Projects',command=self.browse_projects,border=0,fg="#045F80",bg='white')
        self.__b3.config(font=('Arial',9))
        self.__b3.place(x=320,y=200, width = 100)    


    def update_progress(self, percentage: int, text: str):
        self.__progress['value']=percentage
        self.__progress_string.set(text)
        self.__progress_label.update_idletasks()
        self.w.update()


    def __del__(self):
        print('Destructor called, Splash Screen deleted.')

class GradientFrame(tk.Canvas):
    '''A gradient frame which uses a canvas to draw the background'''
    def __init__(self, parent, color1="red", color2="black", **kwargs):
        tk.Canvas.__init__(self, parent, **kwargs)
        self._color1 = color1
        self._color2 = color2
        self.bind("<Configure>", self._draw_gradient)

    def _draw_gradient(self, event=None):
        '''Draw the gradient'''
        self.delete("gradient")
        width = self.winfo_width()
        height = self.winfo_height()
        self.configure(borderwidth=0, highlightthickness=0)
        limit = width
        (r1,g1,b1) = self.winfo_rgb(self._color1)
        (r2,g2,b2) = self.winfo_rgb(self._color2)
        r_ratio = float(r2-r1) / limit
        g_ratio = float(g2-g1) / limit
        b_ratio = float(b2-b1) / limit

        for i in range(limit):
            nr = int(r1 + (r_ratio * i))
            ng = int(g1 + (g_ratio * i))
            nb = int(b1 + (b_ratio * i))
            color = "#%4.4x%4.4x%4.4x" % (nr,ng,nb)
            self.create_line(i,0,i,height, tags=("gradient",), fill=color)
            
        self.create_rectangle(0,70,303,160,fill='#E5E5E5', width = 0)
        self.lower("gradient")
    

logger = get_logger(__name__)

if __name__ == '__main__':
    freeze_support()

    logger_manager:LoggerManager = logger_init() 

    logging.info('Start software')
    logging.info('Start splash screen')
    splash_screen = Splash_Screen()
    logging.info('Splash screen started')

    splash_screen.update_progress(0, "Loading config")
    from bin.logic_config import Config
    splash_screen.update_progress(20, "Loading basic UI elements")
    from bin.gui_wizard import New_Project_Wizard
    splash_screen.update_progress(40, "Loading projects elements")
    from bin.logic_export_import_project import import_project, read_project_name_from_zip, InvalidProjectArchive
    from bin.logic_project_paths import InvalidProjectName
    splash_screen.update_progress(50, "Loading files")
    from bin.logic_file_manager import Project_File_Manager
    splash_screen.update_progress(70, "Preparing UI elements")
    from bin.gui_main import MainGUI
    splash_screen.update_progress(100, "Done")
    
    
    config = Config()  # open config file of the main window

    this_dir = os.path.dirname(os.path.realpath(__file__))  # path to this directory
    os.chdir(this_dir)  # make path to this dir the current path

    def open_project(project_name):
        logger.info('Opening Project')
        this_dir = os.path.dirname(os.path.realpath(__file__))  # path to this directory
        os.chdir(this_dir)  # make path to this dir the current path
        splash_screen.w.destroy()
        logger.info('Splash screen Closed')
        app = MainGUI(TkinterDnD.Tk())  # start the application
        app.open_project(project_name)
        try:
            app.mainloop()
            app.destroy()
        except Exception as e:
            logging.error(f"Error in main loop: {str(e)}")


    def new_project():
        def finish_callback(project_name, project_description,project_id,acm_project_name, acm_project_details):
            logging.info('New Project')
            this_dir = os.path.dirname(os.path.realpath(__file__))  # path to this directory
            os.chdir(this_dir)  # make path to this dir the current path
            splash_screen.w.destroy()
            logger.info('Splash screen Closed')
            app = MainGUI(TkinterDnD.Tk())  # start the application
            app.new_project(project_name, project_description, project_id, acm_project_name, acm_project_details)
            try:
                app.mainloop()
                app.destroy()
            except Exception as e:
                logging.error(f"Error in main loop: {str(e)}")

        def cancel_callback():
            pass
                
        New_Project_Wizard(callback_finish=finish_callback, callback_cancel=cancel_callback)


    def import_project_file():
        """ Import a project """
        path = askopenfilename(title='Import project')
        if path == '': return
        try:
            importing_project_name = read_project_name_from_zip(path)
        except (InvalidProjectName, InvalidProjectArchive) as e:
            logging.warning('Rejected project archive %s: %s', path, e)
            messagebox.showwarning('Invalid project file', str(e))
            return
        except:
            messagebox.showwarning('Wrong file',
                                'Not a valid project file.')
            return
        
        projects = [project.lower() for project in Project_File_Manager.get_all_projects()]
        replace = importing_project_name.lower() in projects
        if replace and not messagebox.askokcancel("Project already exists", "Do you want to replace the existing project?"):
            return

        # noinspection PyBroadException
        try:  # check if it is a right file with figures
            logging.info('Importing Project')
            import_project(path, importing_project_name, replace=replace)
            this_dir = os.path.dirname(os.path.realpath(__file__))  # path to this directory
            os.chdir(this_dir)  # make path to this dir the current path
            splash_screen.w.destroy()
            logger.info('Splash screen Closed')
            app = MainGUI(TkinterDnD.Tk())  # start the application
            app.open_project(importing_project_name)
            try:
                app.mainloop()
                app.destroy()
            except Exception as e:
                logging.error(f"Error in main loop: {str(e)}")
            
        except Exception as e:
            messagebox.showerror('Error importing project', e)
            return


    
    last_project = config.get_opened_project()
    config.destroy()

    if last_project != Config.DEFAULT_PROJECT_OPEN :
        splash_screen.w.destroy()
        logger.info('Splash screen Closed')
        app = MainGUI(TkinterDnD.Tk())  # start the application
        app.open_project(last_project)
        try:
            app.mainloop()
            app.destroy()
        except Exception as e:
            logging.error(f"Error in main loop: {str(e)}")
    else:
        splash_screen.show_options(open_project, new_project, import_project_file)
        
  
    logging.info('Finish software')
    logger_manager.terminate_logger()
