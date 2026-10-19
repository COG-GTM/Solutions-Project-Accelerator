import tkinter as tk
from tkinter import ttk, messagebox

import cv2
import pandas as pd
from bin.logic_static_graphic import Static_Graphic
from bin.gui_link_view import image_view
from bin.gui_elements import custom_entry, loading_animation, rounded_image_button
from bin.logic_internal_database import Database
import uuid

try:
    from .gui_base64_icons import save_icon, start_scan
except ImportError:
    from gui_base64_icons import save_icon, start_scan

class QuickCreateStaticGraphic(tk.Toplevel):
    def __init__(self, parent=None, project_name=None, database=None, config=None, get_selected_roi=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.title("Quick Create Static Graphic")
        self.geometry("500x550")
        # Non-resizable window
        self.resizable(False, False)
        # Without minimize and maximize buttons
        self.attributes('-toolwindow', True)
        
        # Store project information
        self.__project_name = project_name
        self.__db = database
        self.__config = config
        self.__get_selected_roi = get_selected_roi

        # Generate a unique ID for this static graphic
        self.cell_id = str(uuid.uuid4())
        
        # Configure the window to expand the canvas when resized
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        
        # Create a frame to hold all widgets
        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.columnconfigure(0, weight=1)

        # Add widgets
        self.name_entry = None
        self.name = None
        self.__error_message_id = None
        self.canvas.after(1000, self.__create_widgets)
        
        self.name = self.get_default_name()

        def dummy_callback(*args, **kwargs):
            pass
        
        # Create the static graphic with default group_id of 0 (can be updated later)
        self.static_graphic = Static_Graphic(
            id=str(uuid.uuid4()),
            name=self.name,
            description='',
            group_id='Unassigned',
            go_to_document_callback=None,
            hmi_graphic_changed_callback=None,
            update_roi_name_callback=dummy_callback,
            auto_save=False
        )
        
        # Setup the project data
        self.static_graphic.setup_project(self.__project_name,self.__db, self.__config)
        self.static_graphic.create_quick_graphic_link(self.__get_selected_roi)
        self.canvas.after(2000, self.__wait_for_extracted_graphic)


    def __wait_for_extracted_graphic(self):
        image = self.static_graphic.get_hmi_graphic()
        image = cv2.cvtColor(image,cv2.COLOR_RGBA2BGRA)
        error_message = self.static_graphic.get_error_message()
        if image is not None and self.__error_message_id:
            image = cv2.cvtColor(image,cv2.COLOR_RGBA2BGRA)
            self.canvas.itemconfig(self.__error_message_id,text=error_message)
            self.image_view.set_image(image)
            self.__stop_loading_animation()
            
        else:
            self.canvas.after(1000, self.__wait_for_extracted_graphic)

        

    def get_default_name(self):
        self.__all_graphics = self.__db.get_all_static_graphics()
        new_undefined_object_name = 'untitled 1'

        for graphic in self.__all_graphics:
            d = {
                'id':[graphic['id']],
                'Name':[graphic['name']],
                'Page':[graphic['pno']],
                'ChangeUser':[graphic['change_user']],
                'Description':[graphic['description']]
            }
            df = pd.DataFrame(data=d)

            if len(df):
                untitled_df = df[df['Name'].str.startswith('untitled ')]

                if len(untitled_df):
                    count = int(untitled_df['Name'].max().replace('untitled ',''))
                    new_undefined_object_name = 'untitled ' + str(count + 1)
        
        if self.name_entry:
            self.name_entry.set_text(new_undefined_object_name)

        return new_undefined_object_name
    
    def __create_widgets(self):
        # Create name entry field
        self.canvas.update()
        self.name_entry = custom_entry(self.canvas, 8, 18, placeholder="Name", focus_out_callback=self.__name_entry_focusout)
        self.name_entry.draw(max_x=self.canvas.winfo_width() - 16)
        if self.name:
            self.name_entry.set_text(self.name)
        
        # Create image view (canvas for displaying the graphic)
        self.image_view_height = 400
        self.image_view = image_view(self.canvas, 20, 80)
        self.image_view.draw(width=self.canvas.winfo_width() - 40, height=self.image_view_height)
        self.__error_message_id = self.canvas.create_text(10, self.image_view_height + 80, text='', fill="#FF0000", anchor=tk.NW)
        self.loading_animation = loading_animation(self.canvas)

        # Load icons
        self.save_icon = tk.PhotoImage(data=save_icon) 
        
        # Create action buttons
        
        self.save_button = rounded_image_button(
            self.canvas, 0, 96, 10, 
            text="SAVE", 
            icon_image=self.save_icon, 
            borderwidth=1,
            tags=('save',), 
            callback=self.__save_graphic
        )
        self.save_button.draw(0,self.image_view_height)
        
        

        self.__start_loading_animation()

    def __stop_loading_animation(self):
        self.loading_animation_visible = False
        self.loading_animation.stop()

    def __start_loading_animation(self):
        self.loading_animation.draw(self.canvas.winfo_width()/2,
                                    80 + self.image_view_height/2)
        

    
    def __name_entry_focusout(self):
        text = self.name_entry.entry.get()
        if text:
            self.static_graphic.set_name(text)
    
    
    def __save_graphic(self, tags):
        try:
            text = self.name_entry.entry.get()
            if not text:
                messagebox.showwarning("Missing Name", "Please enter a name for the static graphic.")
                return
            self.static_graphic.set_name(text)    
            # Save the static graphic
            self.static_graphic.save_to_database(force_save=True)
            
            # Close the window after saving
            self.destroy()
        except Exception as error:
            messagebox.showerror("Error Saving", str(error))
    
    def __save_and_scan(self, tags):
        try:
            if not self.name_entry.entry.get():
                messagebox.showwarning("Missing Name", "Please enter a name for the static graphic.")
                return
                
            # Save the static graphic
            self.static_graphic.save_to_database()
            
            # Start the scan
            self.static_graphic.start_document_scan()
            messagebox.showinfo("Scan Started", f"Static graphic '{self.name_entry.entry.get()}' saved and scan started.")
        except OSError as error:
            messagebox.showwarning("Already Started", str(error))
        except Exception as error:
            messagebox.showerror("Error", str(error))
    
    def setup_project(self, project_name, database, config):
        self.__project_name = project_name
        self.__db = database
        self.__config = config
        self.static_graphic.setup_project(project_name, database, config)
    
    def setup_data_handler(self, data_handler):
        self.static_graphic.setup_data_handler(data_handler)
    
    def on_resize(self, event):
        # Update image view size when window is resized
        if hasattr(self, 'image_view'):
            width = max(self.winfo_width() - 40, 400)  # Minimum width of 400
            self.image_view.resize(width, self.image_view_height)

if __name__ == "__main__":
    # Test the class
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    app = QuickCreateStaticGraphic()
    app.mainloop()