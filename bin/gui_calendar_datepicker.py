from tkcalendar import Calendar, DateEntry

import tkinter as tk
from tkinter import ttk


def example3():
    top = tk.Toplevel(root)

    ttk.Label(top, text='Choose date').pack(padx=10, pady=10)

    style = ttk.Style()
    # style.theme_use('clam')  # -> uncomment this line if the styling does not work
    style.configure('my.DateEntry',
                    fieldbackground='light gray',
                    background='dark gray',
                    arrowcolor='white',
                    bordercolor='light gray', disabledbackground="black", 
               headersbackground="black", normalbackground="black",  
               normalforeground='white', headersforeground='white')

    cal = DateEntry(top, width=12, background='darkblue', showweeknumbers=False,
                    foreground='white', borderwidth=2, year=2010, style='my.DateEntry',
                    date_pattern='dd/mm/y')
    cal.pack(padx=10, pady=10)
    cal.config(background = "dark gray")
    


root = tk.Tk()
ttk.Button(root, text='DateEntry', command=example3).pack(padx=10, pady=10)

root.mainloop()