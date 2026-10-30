from __future__ import print_function
import logging
from bin.logic_config import Config
from bin.logic_file_manager import Project_File_Manager
import os

try: 
    from bin.gui_elements import tree_view
    from bin.logic_validators import Validators
    from bin.logic_acm_data_handler import ACM_Data_Handler
    from bin.logic_internal_database import Database
except:
    from gui_elements import tree_view
    from logic_validators import Validators
    from logic_acm_data_handler import ACM_Data_Handler
    from logic_internal_database import Database

from sys import version_info


from tkinter import *  # noqa
import tkinter.ttk as ttk


class Wizard(Toplevel):
    def __init__(
            self,
            width=640,
            height=480,
            cancelcommand=None,
            finishcommand=None,
            default_button="finish",
            **kwargs):
        self.selected_pane = None
        self.pane_entry_cmds = {}
        self.pane_prev_cmds = {}
        self.pane_next_cmds = {}
        self.pane_names = []
        self.panes = {}
        self.font = kwargs.get('font', ('Helvetica', '10'))
        self.cancel_command = cancelcommand
        self.finish_command = finishcommand
        self.prev_enabled = True
        self.next_enabled = True
        self.finish_enabled = True
        self.cancel_enabled = True
        self.default_button = default_button
        Toplevel.__init__(
            self,
            borderwidth=0,
            highlightthickness=0,
            takefocus=0,
            relief=FLAT,
        )
        this_dir = os.path.dirname(os.path.realpath(__file__))  # directory of this file
        self.iconbitmap(os.path.join(this_dir, 'logo.ico'))  # set logo icon
        self.holder = Frame(
            self,
            borderwidth=0,
            relief=FLAT,
        )
        self.btnsfr = Frame(
            self,
            borderwidth=0,
            highlightthickness=0,
            takefocus=0,
        )
        self.prevbtn = ttk.Button(
            self.btnsfr,
            text="< Prev",
            width=12,
            command=self._prevpane,
        )
        self.nextbtn = ttk.Button(
            self.btnsfr,
            text="Next >",
            width=12,
            command=self._nextpane,
        )
        self.fnshbtn = ttk.Button(
            self.btnsfr,
            text="Finish",
            width=12,
            command=self._finish,
        )
        self.cnclbtn = ttk.Button(
            self.btnsfr,
            text="Cancel",
            width=12,
            command=self._cancel,
        )
        self.cnclbtn.pack(side=RIGHT, fill=Y, expand=0, padx=10, pady=10)
        self.fnshbtn.pack(side=RIGHT, fill=Y, expand=0, padx=10, pady=10)
        self.nextbtn.pack(side=RIGHT, fill=Y, expand=0, padx=10, pady=10)
        self.prevbtn.pack(side=RIGHT, fill=Y, expand=0, padx=0, pady=10)

        self.holder.pack(side=TOP, fill=BOTH, expand=1)
        self.btnsfr.pack(side=TOP, fill=X, expand=0)

        self.wm_geometry("{width:d}x{height:d}".format(width=width, height=height))
        self.protocol('WM_DELETE_WINDOW', self._cancel)
        self.wait_visibility()
        self.grab_set()

    def add_pane(
            self, name, label,
            entrycommand=None,
            prevcommand=None,
            nextcommand=None):
        newpane = Frame(
            self.holder,
            borderwidth=0,
            highlightthickness=0,
            takefocus=0,
        )
        if not self.panes:
            self.selected_pane = name
            if entrycommand:
                self.after(0, entrycommand)
        self.pane_names.append(name)
        self.panes[name] = newpane
        self.pane_entry_cmds[name] = entrycommand
        self.pane_prev_cmds[name] = prevcommand
        self.pane_next_cmds[name] = nextcommand
        self._update()
        return newpane

    def del_pane(self, name):
        if name == self.selected_pane:
            idx = self.pane_names.index(name)
            panecnt = len(self.pane_names)
            if panecnt == 1:
                self.selected_pane = None
            elif idx == panecnt - 1:
                self._prevpane()
            else:
                self._nextpane()
        del self.pane_entry_cmds[name]
        del self.pane_prev_cmds[name]
        del self.pane_next_cmds[name]
        del self.panes[name]
        self.pane_names.remove(name)

    def show_pane(self, newpane):
        if newpane not in self.pane_names:
            raise ValueError("No pane with the name '{}' exists.".format(newpane))
        self.selected_pane = newpane
        entrycmd = self.pane_entry_cmds[newpane]
        if entrycmd:
            entrycmd()
        self._update()

    def set_prev_enabled(self, enable=True):
        self.prev_enabled = enable
        self._update()

    def set_next_enabled(self, enable=True):
        self.next_enabled = enable
        self._update()

    def set_finish_enabled(self, enable=True):
        self.finish_enabled = enable
        self._update()

    def set_cancel_enabled(self, enable=True):
        self.cancel_enabled = enable
        self._update()

    def set_prev_text(self, text="< Prev"):
        self.prevbtn.config(text=text)
        self._update()

    def set_next_text(self, text="Next >"):
        self.nextbtn.config(text=text)
        self._update()

    def set_finish_text(self, text="Finish"):
        self.fnshbtn.config(text=text)
        self._update()

    def set_cancel_text(self, text="Cancel"):
        self.cnclbtn.config(text=text)
        self._update()

    def set_default_button(self, btn="finish"):
        self.default_button = btn
        self._update()

    def _update(self):
        selpane = self.selected_pane
        prev_state = 'normal'
        next_state = 'normal'
        finish_state = 'normal'
        cancel_state = 'normal'
        if not self.pane_names or selpane == self.pane_names[0]:
            prev_state = 'disabled'
        if not self.prev_enabled:
            prev_state = 'disabled'
        if not self.pane_names or selpane == self.pane_names[-1]:
            next_state = 'disabled'
        if not self.next_enabled:
            next_state = 'disabled'
        if not self.finish_command or not self.finish_enabled:
            finish_state = 'disabled'
        if not self.cancel_command or not self.cancel_enabled:
            cancel_state = 'disabled'
        self.prevbtn.config(state=prev_state)
        self.nextbtn.config(state=next_state)
        self.fnshbtn.config(state=finish_state)
        self.cnclbtn.config(state=cancel_state)
        for child in self.holder.winfo_children():
            child.forget()
        if self.pane_names:
            newpane = self.panes[selpane]
            newpane.pack(side=TOP, fill=BOTH, expand=1)
        prev_def = "active" if self.default_button == "prev" else "normal"
        next_def = "active" if self.default_button == "next" else "normal"
        finish_def = "active" if self.default_button == "finish" else "normal"
        cancel_def = "active" if self.default_button == "cancel" else "normal"
        self.prevbtn.config(default=prev_def)
        self.nextbtn.config(default=next_def)
        self.fnshbtn.config(default=finish_def)
        self.cnclbtn.config(default=cancel_def)
        self.bind('<Return>', self._invoke_default)
        self.update_idletasks()
        self.update_idletasks()

    def _invoke_default(self, event=None):
        if self.default_button == "prev":
            self.prevbtn.invoke()
        elif self.default_button == "next":
            self.nextbtn.invoke()
        elif self.default_button == "finish":
            self.fnshbtn.invoke()
        elif self.default_button == "cancel":
            self.cnclbtn.invoke()
        return "break"

    def _prevpane(self, event=None):
        oldpane = self.selected_pane
        prevcmd = self.pane_prev_cmds[oldpane]
        if prevcmd:
            prevcmd()
        if oldpane != self.selected_pane:
            return
        pos = self.pane_names.index(oldpane)
        if pos > 0:
            pos -= 1
        self.show_pane(self.pane_names[pos])

    def _nextpane(self, event=None):
        oldpane = self.selected_pane
        nextcmd = self.pane_next_cmds[oldpane]
        if nextcmd:
            nextcmd()
        if oldpane != self.selected_pane:
            return
        pos = self.pane_names.index(oldpane)
        if pos < len(self.pane_names) - 1:
            pos += 1
        self.show_pane(self.pane_names[pos])

    def _finish(self, event=None):
        if self.finish_command:
            self.finish_command()
        

    def _cancel(self, event=None):
        if self.cancel_command:
            self.cancel_command()
        self.destroy()
        


class New_Project_Wizard(Wizard):
    def __init__(self, width=640, height=480, callback_cancel=lambda: print("Cancel"), callback_finish=lambda: print("Finish")
                    , config = None, data_handler: ACM_Data_Handler = None):
        super().__init__(width=width, height=height)
        self.title('Create new project')
        self.set_default_button('next')
        self.__setup_pane_1()
        self.__setup_pane_2()
        self.__callback_cancel = callback_cancel
        self.cancel_command = self.cancel_callback
        self.finish_command = self.finish_callback
        self.__callback_finish = callback_finish
        self.__selected_project_values = None
        self.__selected_project_name = None
        

    def cancel_callback(self):
        self.__callback_cancel()

    def finish_callback(self):
        project_name = self.project_name_entry.get()
        project_description = self.project_description_entry.get()
        project_id = self.project_id_entry.get()
        self.__callback_finish(project_name, project_description,project_id,self.__selected_project_name, self.__selected_project_values)
        try:
            self.destroy()
        except:
            pass



    def check_project_name(self, sv: StringVar):

        # replace all spaces
        sv.set(sv.get().replace(' ','_'))

        if not Validators.check_project_name_valid(sv.get()):
            self.disable_next()
            self.project_name_entry_error.config(text='Invalid name.' if sv.get() else '')
            return


        if Validators.check_if_project_name_exists(sv.get()):
            self.disable_next()
            self.project_name_entry_error.config(text='Name already exists.')
            return
        else:
            self.project_name_entry_error.config(text='')


        self.enable_next()
        


    def __setup_pane_1(self):
        self.__pane_one = self.add_pane('one', 'First', entrycommand=self.disable_finish)
        self.disable_next()
        self.__pane_one_description_label = ttk.Label(self.__pane_one, text="Project Details",font=("Arial Bold", 9))
        self.__pane_one_description_label.place(anchor=NW, width=200, x = 20, y=45)
        self.__pane_one_description_label = ttk.Label(self.__pane_one, text="ACM Configuration")
        self.__pane_one_description_label.place(anchor=NW, width=200, x = 20, y=65)

        s = ttk.Separator(self.__pane_one, orient=VERTICAL)
        s.place(anchor=NW, height = 360, x = 160, y=27)

        self.__pane_one_label = ttk.Label(self.__pane_one, text="1. Project Details", font=("Arial Bold", 12))
        self.__pane_one_label.place(anchor=NW, width=200, x = 170, y=20)

        self.__pane_one_description_label = ttk.Label(self.__pane_one, text="Please fill in the project details below.")
        self.__pane_one_description_label.place(anchor=NW, width=200, x = 170, y=45)

        project_name_label = ttk.Label(self.__pane_one, text="Project name:")
        project_name_label.place(anchor=NW, width=110, x = 180, y=70)

        self.project_name_entry_sv = StringVar()
        self.project_name_entry_sv.trace("w", lambda name, index, mode, sv=self.project_name_entry_sv: self.check_project_name(self.project_name_entry_sv))

        reg = self.__pane_one.register(Validators.project_name_validator)
        self.project_name_entry = ttk.Entry(self.__pane_one, textvariable=self.project_name_entry_sv)
        self.project_name_entry.place(anchor=NW, width=300, x = 300, y=70)
        self.project_name_entry.config(validate ="key", 
            validatecommand =(reg, '%P'))

        self.project_name_entry_error = ttk.Label(self.__pane_one, anchor='e', text="",font=("Arial Bold", 8),foreground='red',justify=RIGHT)
        self.project_name_entry_error.place(anchor=NW, width=200, x = 400, y=91)

        project_description_label = ttk.Label(self.__pane_one, text="Project description:")
        project_description_label.place(anchor=NW, width=110, x = 180, y=115)

        self.project_description_entry = ttk.Entry(self.__pane_one)
        self.project_description_entry.place(anchor=NW, width=300, x = 300, y=115)

        project_id_label = ttk.Label(self.__pane_one, text="Project ID:")
        project_id_label.place(anchor=NW, width=110, x = 180, y=160)

        self.project_id_entry = ttk.Entry(self.__pane_one)
        self.project_id_entry.place(anchor=NW, width=300, x = 300, y=160)

        self.project_id_entry_error = ttk.Label(self.__pane_one, anchor='e', text="",font=("Arial Bold", 8),foreground='red',justify=RIGHT)
        self.project_id_entry_error.place(anchor=NW, width=200, x = 400, y=181)


    
    def __setup_pane_2(self):
        self.__pane_two = self.add_pane(
            'two', 'Second',
            entrycommand=self.enable_finish,
            prevcommand=self.disable_finish,
        )
        pane2_description_label = ttk.Label(self.__pane_two, text="Project Details")
        pane2_description_label.place(anchor=NW, width=200, x = 20, y=45)
        pane2_description_label = ttk.Label(self.__pane_two, text="ACM Configuration", font=("Arial Bold", 9))
        pane2_description_label.place(anchor=NW, width=200, x = 20, y=65)

        s = ttk.Separator(self.__pane_two, orient=VERTICAL)
        s.place(anchor=NW, height = 360, x = 160, y=27)


        pane2_label = ttk.Label(self.__pane_two, text="2. ACM Configuration", font=("Arial Bold", 12))
        pane2_label.place(anchor=NW, width=200, x = 170, y=20)

        #pane2_description_label = ttk.Label(self.__pane_two, text="Please configure the ACM project settings.")
        #pane2_description_label.place(anchor=NW, width=400, x = 170, y=45)

        #
        if self.__get_acm_projects():
            self.__setup_pane_2_if_connected()
        else:
            self.__setup_pane_2_if_not_connected()

    def __get_acm_projects(self):
        try:
            config = Config()  # open config file of the main window
            connection_string = config.get_connection_string()
            config.destroy()
            data_handler = ACM_Data_Handler(connection_string)
            self.__projects_df = data_handler.get_all_projects()
            return True
        except:
            return False


    def __setup_pane_2_if_connected(self):
        label = Message(self.__pane_two, text='Once any link is made between the refrence documents'+
                                                ' and the ACM objects. The linked ACM project for an '+
                                                'Solutions Project Accelerator project cannot be changed.', width=440)
        label.place(anchor=NW,x=170,y=45)
        self.tree = tree_view(self.__pane_two)
        self.tree.place(anchor=NW,width=440,height=300,x = 170, y=90)
        self.tree['columns'] = ('one')
        self.tree.heading("#0",text="Name",anchor=W)
        self.tree.heading("one", text="Description",anchor=W)
        for id, row in self.__projects_df.iterrows():
            self.tree.insert('','end', text=row['Name'],values=(row['Description'],str(id)))

        def click(_, name, values):
            
            self.__selected_project_values = values
            self.__selected_project_name = name
            

        self.tree.single_click_func(click)
        self.tree.double_click_func(click)


    def __setup_pane_2_if_not_connected(self):
        pane2_label = ttk.Label(self.__pane_two, text="Not connected to ACM", font=("Arial Bold", 11))
        pane2_label.place(anchor=NW, width=200, x = 170, y=45)
        label = Message(self.__pane_two, text='Please go to "File > Connect Database" to connect an ACM database'+
                                                ' once the project is open.', width=440)
        label.place(anchor=NW,x=170,y=65)


    def disable_finish(self):
        self.set_finish_enabled(False)

    def enable_finish(self):
        self.set_finish_enabled(True)

    def disable_next(self):
        self.set_next_enabled(False)

    def enable_next(self):
        self.set_next_enabled(True)


class Link_ACM_Project_Wizard(Wizard):
    def __init__(self, data_handler : ACM_Data_Handler, width=640, height=480, callback_cancel=lambda: print("Cancel"), callback_finish=lambda: print("Finish")):
        super().__init__(width=width, height=height)
        self.title('Select ACM Project to link')
        self.data_handler = data_handler
        self.set_default_button('next')
        self.__setup_pane_1()
        self.__pass_double_click_func()
        self.__callback_cancel = callback_cancel
        self.cancel_command = self.cancel_callback
        self.finish_command = self.finish_callback
        self.__callback_finish = callback_finish
        self.__selected_project_name = ''
        self.__selected_project_values = []

    def cancel_callback(self):
        self.__callback_cancel()

    def finish_callback(self):
        self.__callback_finish(self.__selected_project_name, self.__selected_project_values)
        self.destroy()



    def check_project_name(self, sv):
            if Validators.check_project_name_valid(sv.get()):
                self.enable_next()
            else:
                self.disable_next()

    def __setup_pane_1(self):
        self.__pane_one = self.add_pane('one', 'First', entrycommand=self.disable_finish)
        self.disable_finish()
        label = Message(self.__pane_one, text='Once any link is made between the refrence documents'+
                                                ' and the ACM objects. The linked ACM project for an '+
                                                'Solutions Project Accelerator project cannot be changed.', width=592)
        label.pack(side="top", fill=X, padx=24, pady=0, expand=True)
        self.tree = tree_view(self.__pane_one)
        self.tree.pack(side="top", fill="both", padx=24, pady=0, expand=True)
        self.tree['columns'] = ('one')
        self.tree.heading("#0",text="Name",anchor=W)
        self.tree.heading("one", text="Description",anchor=W)
        self.nextbtn.pack_forget()
        self.prevbtn.pack_forget()
        self.__insert_projects()

    def __insert_projects(self):
        projects_df = self.data_handler.get_all_projects()
        for id, row in projects_df.iterrows():
            self.tree.insert('','end', text=row['Name'],values=(row['Description'],str(id)))


    def __pass_double_click_func(self):
        def click(_, name, values):
            
            self.__selected_project_values = values
            self.__selected_project_name = name
            self.enable_finish()

        self.tree.single_click_func(click)
        self.tree.double_click_func(click)
        
    
       
    def disable_finish(self):
        self.set_finish_enabled(False)

    def enable_finish(self):
        self.set_finish_enabled(True)

    def disable_next(self):
        self.set_next_enabled(False)

    def enable_next(self):
        self.set_next_enabled(True)



class Open_Project_Wizard(Wizard):
    def __init__(self, width=640, height=480, callback_cancel=lambda: print("Cancel"), callback_finish=lambda: print("Finish")):
        super().__init__(width=width, height=height)
        self.title('Select Project to open')
        self.set_default_button('next')
        self.__setup_pane_1()
        self.__pass_double_click_func()
        self.__callback_cancel = callback_cancel
        self.cancel_command = self.cancel_callback
        self.finish_command = self.finish_callback
        self.__callback_finish = callback_finish
        self.__selected_project_name = ''
        self.__selected_project_values = []

    def cancel_callback(self):
        self.__callback_cancel()

    def finish_callback(self):
        self.__callback_finish(self.__selected_project_name, self.__selected_project_values)
        self.destroy()



    def check_project_name(self, sv):
            if Validators.check_project_name_valid(sv.get()):
                self.enable_next()
            else:
                self.disable_next()

    def __setup_pane_1(self):
        self.__pane_one = self.add_pane('one', 'First', entrycommand=self.disable_finish)
        self.disable_finish()
        label = Message(self.__pane_one, text='Select a project to open. '+
                                                'Projects list are on your local machine.', width=592, anchor='w')
        label.pack(side="top", fill=X, padx=24, pady=0, expand=True)
        self.tree = tree_view(self.__pane_one)
        self.tree.pack(side="top", fill="both", padx=24, pady=0, expand=True)
        self.tree['columns'] = ('one')
        self.tree.heading("#0",text="Name",anchor=W)
        self.tree.heading("one", text="Description",anchor=W)
        self.nextbtn.pack_forget()
        self.prevbtn.pack_forget()
        self.__insert_projects()

    def __insert_projects(self):
        projects = Project_File_Manager.get_all_projects()
        for project in projects:
            try:
                description = Project_File_Manager.get_project_details(project)[1]
                self.tree.insert('','end', text=project,values=(description,str(id)))
            except Exception as error:
                logging.error('Open Project interface error: '+str(error))


    def __pass_double_click_func(self):
        def click(_, name, values):
            
            self.__selected_project_values = values
            self.__selected_project_name = name
            self.enable_finish()

        self.tree.single_click_func(click)
        self.tree.double_click_func(click)
        
    
       
    def disable_finish(self):
        self.set_finish_enabled(False)

    def enable_finish(self):
        self.set_finish_enabled(True)

    def disable_next(self):
        self.set_next_enabled(False)

    def enable_next(self):
        self.set_next_enabled(True)  


if __name__ == "__main__":
    def main():
        root = Tk()

        def finish_callback(_, __):
            pass

        def cancel_callback():
            pass

        wiz = Link_ACM_Project_Wizard(None, callback_finish=finish_callback, callback_cancel=cancel_callback)

        
        root.wm_withdraw()
        root.wait_window(wiz)

    main()