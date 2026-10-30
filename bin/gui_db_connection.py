
import logging
import os
import socket
from threading import *
try:
 
    from bin.logic_sql_database import *
    from bin.logic_logger import handle_exception_with_messagebox
except ImportError as error:

    from logic_sql_database import *
    from logic_logger import handle_exception_with_messagebox

import tkinter as tk
from tkinter import *
from tkinter import ttk 
from tkinter.ttk import Combobox
from tkinter import messagebox 

 
  
class db_conntection_form:

    icon = '''
    iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAQAAAC1+jfqAAABMUlEQVQoz23RMUtbARTF8d9Lo7RqlDR5IRSkYheXliKhJUND46iST9BV3B37Cdyjg3R2EVw6dOruEhzaoS6WVKGE95KGQqqiJHF4EVPas13uPfcP5wQSPVD0zBMz6PnpVEsfAvBcTVFHrIcZoZyWj74m7oq6FXOj48Q2Z0VdJRm2lf1PZduClEBoTe6fdc6aUJAW6Oh7r+lEyxUeKlqyoKcjSGPSge+WLXllAjd++2bfonekDU3bsufI5zHAtJJNfwzTUiLHymp+iVzikYLHYoeWpZIPPxwKPZWXQduxM7GSN4Z3iA8aGmOIjKqNccRr67oiF5hSkL1H9A1GiHmhWcQazsVKXiZ9VO14K/NXTBlVu6pJWYEXVmW1tV1jUl5e1ydfDO8KSilYUJRFV0tTZAC3bBpXteC2l9cAAAAASUVORK5CYII=+AAAAAAAAAAAAAAAAAAAALQAAAHsAAACTAAAAgAAAAGsAAABfAAAAXwAAAGsAAACAAAAAkwAAAHsAAAAtAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAAAAGwAAAD4AAABYAAAAZAAAAGQAAABYAAAAPgAAABsAAAADAAAAAAAAAAAAAAAA4AcAAIABAACH4QAAEAgAAAAAAAADwAAAEAgAAAAAAAAH4AAAAAAAAAAAAAAP8AAAH/gAAIPBAACAAQAA4AcAAA==
    '''

    WINDOW_AUTHENTICATION = 1
    SQL_SERVER_AUTHENTICATION = 0

    def __init__(self, callback=None):
        self.__form = tk.Toplevel()
        self.__callback = callback
        self.__setup_form()
        self.get_db_servers('localhost')
        self.__form.wait_visibility()
        self.__form.grab_set()
        self.__form.wait_window()


    def __setup_form(self):

        
        self.__form.geometry('375x474')
        self.__form.resizable(False, False)
        this_dir = os.path.dirname(os.path.realpath(__file__))  # directory of this file
        self.__form.iconbitmap(os.path.join(this_dir, 'logo.ico'))  # set logo icon
        self.__form.title("Connection Properties")
        self.__setup_server_selection_section()
        self.__setup_authenticaton_details_section()
        self.__setup_database_selection_section()
        self.__setup_end_of_form()


    def __setup_server_selection_section(self):


        dataSourceLabel = tk.Label(self.__form, text="Data source:",justify=LEFT)
        dataSourceEntry = ttk.Entry(self.__form, width=44)
        dataSourceEntry.insert(END, 'Microsoft SQL Server (SqlClient)')
        dataSourceEntry.config(state='disabled')

        dataSourceLabel.place(x = 10, y = 10, anchor=NW)
        dataSourceEntry.place(x = 10, y = 30)

        change = ttk.Button(self.__form, text = 'Change', command = None, state='disabled')
        change.place(x = 286 , y = 28) 

        dataServerLabel = tk.Label(self.__form, text="Server name:",justify=LEFT)

        dataServerLabel.place(x = 10 , y = 54)

        self.__server_sv = tk.StringVar() 
        self.__server_sv.trace("w", lambda name, index, mode, sv=self.__server_sv: self.__server_chosen())
        self.__serverChoosen = ttk.Combobox(self.__form, width = 41, textvariable = self.__server_sv) 
        self.__serverChoosen.place(x = 10 , y = 74) 
        self.__serverChoosen.current()


        refresh = ttk.Button(self.__form, text = 'Refresh', command = self.get_db_servers('localhost'))
        refresh.place(x = 286 , y = 72)  


    def __setup_authenticaton_details_section(self):


        logOnDetails = ttk.LabelFrame(self.__form, text="Log on to the server")
        logOnDetails.place(x = 10 , y = 102, width= 355, height= 150)
        
        self.__windowAuthentication_var = IntVar(None,self.WINDOW_AUTHENTICATION)

        self.__windowAuthentication = ttk.Radiobutton(logOnDetails, 
                                                        text="Use Windows Authentication", 
                                                        variable=self.__windowAuthentication_var, 
                                                        value=self.WINDOW_AUTHENTICATION,
                                                        command=self.__non_window_authentication_options_enable)
        self.__windowAuthentication.place(x = 6 , y = 8)

        self.__serverAuthentication = ttk.Radiobutton(logOnDetails, 
                                                        text="Use SQL Sever Authentication", 
                                                        variable=self.__windowAuthentication_var, 
                                                        value=self.SQL_SERVER_AUTHENTICATION,
                                                        command=self.__non_window_authentication_options_enable)
        self.__serverAuthentication.place(x = 6 , y = 28)

        '''========================================== Username =============================================='''

        nameLabel = tk.Label(logOnDetails, text="User name:",justify=LEFT)
        nameLabel.place(x = 22 , y = 50)

        self.__username_sv = StringVar()
        self.__username_sv.trace("w", lambda name, index, mode, sv=self.__username_sv: self.__username_typed())
        self.__usernameEntry = ttk.Entry(logOnDetails, 
                                            width=40,  
                                            textvariable=self.__username_sv,
                                            state=tk.DISABLED)
        self.__usernameEntry.place(x = 95 , y = 50)

        '''========================================== Password =============================================='''

        passwordLabel = tk.Label(logOnDetails, text="Password:",justify=LEFT)
        passwordLabel.place(x = 22 , y = 77)

        self.__password_sv = StringVar()
        self.__password_sv.trace("w", lambda name, index, mode, sv=self.__password_sv: self.__password_typed())
        self.__passwordEntry = ttk.Entry(logOnDetails, 
                                            width=40, 
                                            show="•", 
                                            textvariable=self.__password_sv,
                                            state=tk.DISABLED)
        self.__passwordEntry.place(x = 95 , y = 77)

        

        self.__saveMyPassword = IntVar(None, 0)
        self.__saveMyPasswordCheckButton = ttk.Checkbutton(logOnDetails, 
                                                            text = "Save my password", 
                                                            variable = self.__saveMyPassword, 
                                                            onvalue = 1, 
                                                            offvalue = 0,
                                                            state=tk.DISABLED)
        self.__saveMyPasswordCheckButton.place(x = 93 , y = 99)




    def __setup_database_selection_section(self):

        connectdatabaseDetails = ttk.LabelFrame(self.__form, text="Connect to a database")
        connectdatabaseDetails.place(x = 10 , y = 253, width= 355, height= 164)

        self.___selectDatabase = IntVar(None, 0)
        selectDatabase = ttk.Radiobutton(connectdatabaseDetails, 
                                            text="Select or enter a database name:", 
                                            variable=self.___selectDatabase, 
                                            value=0, 
                                            command=None)
        selectDatabase.place(x = 6 , y = 8)

        self.__databaseChosen_sv = tk.StringVar() 
        self.__databaseChoosen = ttk.Combobox(connectdatabaseDetails, 
                                                width = 49, 
                                                textvariable = self.__databaseChosen_sv) 
        self.__databaseChoosen.place(x = 25 , y = 28) 
        self.__databaseChoosen.current()

        attachDatabase = ttk.Radiobutton(connectdatabaseDetails, 
                                            text="Attach a database file:", 
                                            variable=self.___selectDatabase, 
                                            value=1, 
                                            command=None, 
                                            state=tk.DISABLED)
        attachDatabase.place(x = 6 , y = 50)


        databaseFilename = ttk.Entry(connectdatabaseDetails, width=38, state=tk.DISABLED)
        databaseFilename.place(x = 25 , y = 70)

        browse = ttk.Button(connectdatabaseDetails, text = 'Browse', command = None, state=tk.DISABLED)
        browse.place(x = 266 , y = 68) 

        logicalNameLabel = tk.Label(connectdatabaseDetails, text="Logical name:",justify=LEFT, state=tk.DISABLED)
        logicalNameLabel.place(x = 25 , y = 92)

        logicalNameEntry = ttk.Entry(connectdatabaseDetails, width=52, state=tk.DISABLED)
        logicalNameEntry.place(x = 25 , y = 112)


    def __setup_end_of_form(self):

        ttk.Separator(self.__form,orient=HORIZONTAL).place(x = 10 , y = 430, width= 355)

        testConnectionButton = ttk.Button(self.__form, 
                                            text = 'Test Connection', 
                                            command = self.__test_connection)
        testConnectionButton.place(x = 10 , y = 440)

        browse = ttk.Button(self.__form, text = 'Cancel', command = self.__form.destroy)
        browse.place(x = 290 , y = 440)

        browse = ttk.Button(self.__form, text = 'OK', command = self.__ok)
        browse.place(x = 208 , y = 440)

    
    def __server_chosen(self):
        self.__start_get_all_database_thread()


    def __username_typed(self):
        self.__start_get_all_database_thread()


    def __password_typed(self):
        self.__start_get_all_database_thread()


    def __start_get_all_database_thread(self):
        db_thread=Thread(target=self.__get_all_databases,args=(self.__server_sv.get(), 
                                                                self.__username_sv.get(),
                                                                self.__password_sv.get(),
                                                                self.__windowAuthentication_var.get()))
        self.__get_all_database_done = False 
        
        db_thread.start()
        self.__form.after(500,self.__check_get_all_database_done)

    def __ok(self):
        connection_string = build_connection_string(self.__server_sv.get(),
                                            database=self.__databaseChosen_sv.get(),
                                            user=self.__username_sv.get(),
                                            password=self.__password_sv.get(),
                                            use_windows_authentication = self.__windowAuthentication_var.get())
        connection_string = connection_string + "TrustServerCertificate=yes;"
        self.__callback(connection_string, self.__windowAuthentication_var.get(), self.__saveMyPassword.get())
        self.__form.destroy()
        


    def __get_all_databases(self, server,username,password,use_windows_authentication):
        try:
            self.__all_databases = get_all_databases(server,
                                            user=username,
                                            password=password,
                                            use_windows_authentication = use_windows_authentication)
            self.__get_all_database_done = True
        except Exception as error:
            logging.error('Get all database error: ' + str(error))


    def __check_get_all_database_done(self):
        if self.__get_all_database_done:
            self.__databaseChoosen['values'] = self.__all_databases
        else:
            self.__form.after(500,self.__check_get_all_database_done)
        



    def __non_window_authentication_options_enable(self):
        auth_method = self.__windowAuthentication_var.get()

        if auth_method == self.WINDOW_AUTHENTICATION:
            self.__usernameEntry["state"] = tk.DISABLED
            self.__passwordEntry["state"] = tk.DISABLED
            self.__saveMyPasswordCheckButton["state"] = tk.DISABLED
            self.__start_get_all_database_thread()
            
        else:
            self.__usernameEntry["state"] = tk.NORMAL
            self.__passwordEntry["state"] = tk.NORMAL
            self.__saveMyPasswordCheckButton["state"] = tk.NORMAL
            self.__start_get_all_database_thread()


    def get_db_servers(self, host):
        instance_info = []
        try:
            instance_info = get_instance_info(host, 
                                                instance=None,
                                                sql_browser_port=SQL_BROWSER_DEFAULT_PORT)
        except socket.error as error:
            logging.error('Connection to %s failed: %s' % (host, error))
        except Exception as error:
            logging.error('Connection to %s failed: %s' % (host, error))
            messagebox.showerror('Connection to host', str(error))

        servers = []
        for i in instance_info:

            server_name = ''
            instance_name = ''

            for key, value in i.items():

                if 'ServerName' == key :
                    server_name = value

                if 'InstanceName' == key :
                    instance_name = value

            servers.append(server_name+'\\'+instance_name)
        self.__serverChoosen['values'] = servers

    def __test_connection(self):

        @handle_exception_with_messagebox(parent=self.__form)
        def db_connection_test():
            connection_string = build_connection_string(self.__server_sv.get(),
                                            database=self.__databaseChosen_sv.get(),
                                            user=self.__username_sv.get(),
                                            password=self.__password_sv.get(),
                                            use_windows_authentication = self.__windowAuthentication_var.get())
            connection_string = connection_string + "TrustServerCertificate=yes;"

            test_connection(connection_string)
            messagebox.showinfo('Connected', 
                                'Connected to '+self.__databaseChosen_sv.get()+' database.',
                                parent = self.__form)

        db_connection_test()
    

""" """

if __name__ == "__main__":

    def open_Toplevel():
        db = db_conntection_form()
        


    root = tk.Tk()
    
    button = Button(root, text = "open toplevel1",
                command = open_Toplevel)
    button.place(x = 75, y = 50)
    root.mainloop()

