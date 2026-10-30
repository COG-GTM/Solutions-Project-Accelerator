import io
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw
import os
import math

try:
    from bin.gui_autoscrollbar import AutoScrollbar
    from bin.logic_gfx_to_svg import gfx_to_svg, render_svg_to_png
except ImportError as e:
    from gui_autoscrollbar import AutoScrollbar
    from logic_gfx_to_svg import gfx_to_svg, render_svg_to_png

class HMISymbolSelector:
    def __init__(self,parent, library_parser, pre_selection, callback=None):
        self.root = tk.Toplevel(parent)
        self.root.title("Symbol Selector")
        self.root.geometry("800x600")
        this_dir = os.path.dirname(os.path.realpath(__file__))
        self.root.iconbitmap(os.path.join(this_dir, 'logo.ico'))

        # Stay above the window that opened us; without this the process
        # diagram canvas re-focuses itself on <Enter> and covers this dialog.
        self.root.transient(parent.winfo_toplevel())
        try:
            self.root.grab_set()
        except tk.TclError:
            pass
        self.root.protocol("WM_DELETE_WINDOW", self.close_interface)

        # Configuration
        self.grid_cols = 4
        self.image_size = 150
        self.padding = 20
        self.extra_padding = 0  # Extra padding between images
        self.selected_images = []
        self.callback = callback
        self.pre_selection = pre_selection  # Pre-selected image names


        self.acm_library_parser = library_parser
        self.load_hmi_symbols()
            
        # Setup UI
        self.setup_ui()
        self.load_images()



    def load_hmi_symbols(self):
        self.hmi_symbols = self.acm_library_parser.extract_all_ft_view_se_symbols()
        self.hmi_symbol_xml = {}
        self.hmi_symbol_images = {}

        for symbol in self.hmi_symbols:
            svg, viewbox, _, _ = gfx_to_svg(symbol['Value'])

            if not svg:
                print(f"Failed to convert symbol {symbol['Name']} to SVG")
                continue

            # Fit the SVG to a 150x150 box by scaling it
            scale = min(self.image_size/viewbox[2],self.image_size/viewbox[3])
            img = Image.open(io.BytesIO(render_svg_to_png(svg, scale=scale)))
            photo = ImageTk.PhotoImage(img)
            
            self.hmi_symbol_images[symbol['Name']] = photo
            self.hmi_symbol_xml[symbol['Name']] = symbol['Value']


    def setup_ui(self):
        """Setup the user interface"""
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=0, column=0, sticky='nsew', padx=0, pady=0)
        
        # Configure root grid
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # Canvas frame with scrollbars
        canvas_frame = ttk.Frame(main_frame, relief='flat')
        canvas_frame.grid(row=0, column=0, sticky='nsew')
        
        # Configure main_frame grid
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Scollbar
        v_scrollbar = AutoScrollbar(canvas_frame, orient='vertical')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        v_scrollbar.configure(command=self.scroll_y)
        
        # Canvas
        self.canvas = tk.Canvas(canvas_frame, bg="white", yscrollcommand=v_scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky='nswe')
        
        # Configure canvas_frame grid
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)

        # Bind window resize event
        self.canvas.bind("<Configure>", self.on_window_resize)
        self.resize_timer = None
        
        # Control panel
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=1, column=0, sticky='ew', pady=(5, 10))
        
        
        # Buttons
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(side=tk.RIGHT)
        
        
        ttk.Button(button_frame, text="OK", 
                  command=self.send_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Cancel", 
                  command=self.close_interface).pack(side=tk.LEFT, padx=(0, 10))
        
        # Bind canvas events
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)


    def send_selected(self):
        """Send selected images to callback if available"""
        if self.callback and self.selected_images:
            name = self.hmi_symbol_info[self.selected_images[0]]['name']
            self.callback(name, self.hmi_symbol_xml[name])
            self.close_interface()
        else:
            print("No callback function provided")


    def close_interface(self):
        """Close the symbol selector interface"""
        try:
            self.root.grab_release()
        except tk.TclError:
            pass
        self.root.destroy()
    
    
    def load_images(self):
        """Load and display images in grid"""
        
        self.hmi_symbol_info = []
        
        for i, name in enumerate(self.hmi_symbol_images):
            try:

                photo = self.hmi_symbol_images[name]
                
                # Calculate position
                row = i // self.grid_cols
                col = i % self.grid_cols
                
                x = self.extra_padding + col * (self.image_size + self.padding + self.extra_padding)
                
                y = self.padding + row * (self.image_size + self.padding + 40)


                # Create image on canvas
                image_id = self.canvas.create_image(x+self.image_size/2, y+self.image_size/2, anchor=tk.CENTER, image=photo)

                # Create selection border (initially hidden)
                border_id = self.canvas.create_rectangle(
                    x-3, y-3, x+self.image_size+3, y+self.image_size+3,
                    outline="gray90", width=1
                )

                # Create a name label
                name_label = self.canvas.create_text(x + self.image_size / 2, y + self.image_size+15, text=name, anchor=tk.CENTER,
                                                     font=("Arial", 10), fill="gray", justify=tk.CENTER)
                
                # Store image info
                self.hmi_symbol_info.append({
                    'name_id': name_label,
                    'id': image_id,
                    'border_id': border_id,
                    'name': name,
                    'index': i,
                    'x': x,
                    'y': y
                })
                
            except Exception as e:
                print(f"Error loading image {name}: {e}")

        # Handle pre-selection
        for img_obj in self.hmi_symbol_info:
            if img_obj['name'] == self.pre_selection:
                self.select(img_obj)
                break
        
        bbox = self.canvas.bbox("all")  # Update bounding box for all items
        # Update canvas scroll region
        self.canvas.configure(scrollregion=(0, 0, bbox[2], bbox[3]+50))
        
    def on_canvas_click(self, event):
        """Handle canvas click for image selection"""
        # Get canvas coordinates
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        # Find clicked image
        for img_obj in self.hmi_symbol_info:
            x, y = img_obj['x'], img_obj['y']
            if (x <= canvas_x <= x + self.image_size and 
                y <= canvas_y <= y + self.image_size):
                self.select(img_obj)
                break
    
    def select(self, img_obj):
        """Toggle selection state of an image"""
        index = img_obj['index']

        # Deselect all
        self.clear_selection()
        
        # Select
        self.selected_images.append(index)
        self.canvas.itemconfig(img_obj['border_id'], width=2, outline="#0078D7")

    def clear_selection(self):
        """Clear all selections"""
        self.selected_images.clear()
        for img_obj in self.hmi_symbol_info:
            self.canvas.itemconfig(img_obj['border_id'], width=1, outline="lightgray")

    def get_selected(self):
        """Print selected image paths"""
        if self.selected_images:
            print("Selected images:")
            for index in sorted(self.selected_images):
                print(f"  {self.hmi_symbol_info[index]}")
        else:
            print("No images selected")
    
    def on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def scroll_y(self, *args, **kwargs):
        """ Scroll canvas vertically and redraw the image """
        self.canvas.yview(*args)  # scroll vertically
    
    # Add window resize handler
    def on_window_resize(self, event):
        """Handle window resize event with debouncing"""
        # Skip if this is not the root window being resized
        if event.widget != self.canvas:
            return
            
        # Cancel previous timer if it exists
        if self.resize_timer is not None:
            self.canvas.after_cancel(self.resize_timer)
            
        # Start a new timer (300ms debounce)
        self.resize_timer = self.canvas.after(100, self.update_grid_layout)
    
    def update_grid_layout(self):
        """Update grid layout based on current window size"""
        current_width = self.canvas.winfo_width()
        
        # Calculate new number of columns based on window width
        available_width = current_width - 40  # Account for padding and scrollbar

        # Minimum 1 column, maximum based on available width
        new_cols = max(1, available_width // (self.image_size + self.padding))

        # Calculate the extra padding in between images
        width = current_width - (new_cols * (self.image_size + self.padding))
        self.extra_padding = width // (new_cols + 1)

        self.grid_cols = new_cols
        
        # Reload images with new grid layout
        self.move_images_to_grid(new_cols=new_cols, animate=False)
        
        # Restore selections
        for img_obj in self.hmi_symbol_info:
            if img_obj['index'] in self.selected_images:
                self.canvas.itemconfig(img_obj['border_id'], state="normal")


    def move_images_to_grid(self, new_cols=None, animate=False):
        """Move existing images to new grid positions without reloading"""
        if new_cols:
            self.grid_cols = new_cols

        
        for i, img_obj in enumerate(self.hmi_symbol_info):
            # Calculate new position
            row = i // self.grid_cols
            col = i % self.grid_cols
            new_x = self.extra_padding + col * (self.image_size + self.padding + self.extra_padding)  
            new_y = self.padding + row * (self.image_size + self.padding + 40)
            
            if animate:
                # Smooth animation to new position
                self.animate_image_move(img_obj, new_x, new_y)
            else:
                # Instant move
                self.canvas.coords(img_obj['name_id'], new_x+self.image_size/2, new_y+self.image_size+15)
                self.canvas.coords(img_obj['id'], new_x+self.image_size/2, new_y+self.image_size/2)
                self.canvas.coords(img_obj['border_id'], 
                                 new_x-3, new_y-3, 
                                 new_x+self.image_size+3, new_y+self.image_size+3)
            
            # Update stored position
            img_obj['x'] = new_x
            img_obj['y'] = new_y
        
        bbox = self.canvas.bbox("all")  # Update bounding box for all items
        # Update canvas scroll region
        self.canvas.configure(scrollregion=(0, 0, bbox[2], bbox[3]+50))
    
    def animate_image_move(self, img_obj, target_x, target_y, steps=10):
        """Animate image movement to new position"""
        current_coords = self.canvas.coords(img_obj['id'])
        current_x, current_y = current_coords[0], current_coords[1]
        
        step_x = (target_x - current_x) / steps
        step_y = (target_y - current_y) / steps
        
        def move_step(step_count):
            if step_count <= steps:
                new_x = current_x + (step_x * step_count)
                new_y = current_y + (step_y * step_count)
                
                # Move image and border
                self.canvas.coords(img_obj['name_id'], new_x+self.image_size/2, new_y+self.image_size+15)
                self.canvas.coords(img_obj['id'], new_x+self.image_size/2, new_y+self.image_size/2)
                self.canvas.coords(img_obj['border_id'], 
                                 new_x-3, new_y-3, 
                                 new_x+self.image_size+3, new_y+self.image_size+3)
                
                # Schedule next step
                self.root.after(20, lambda: move_step(step_count + 1))
        
        move_step(1)
