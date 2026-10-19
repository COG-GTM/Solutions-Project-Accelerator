
import tkinter as tk
import customtkinter as ctk

# Setup customtkinter appearance
ctk.set_appearance_mode("Light")  # Options: "System", "Dark", "Light"
ctk.set_default_color_theme("blue")

_PADDING = 10
_MIN_WIDTH = 150
_MIN_HEIGHT = 30
_REPOSITION_DELAY_MS = 16
_FOCUS_CHECK_DELAY_MS = 120


class FloatingDropdown:
    """Separate class for managing a floating dropdown window"""
    
    def __init__(self, parent_window, canvas, options=None, callback=None):
        self.parent_window = parent_window
        self.canvas = canvas
        # parent_window is usually an inner Frame, which never sees the window being moved.
        self.toplevel = canvas.winfo_toplevel()
        self.options = options or ["Option 1", "Option 2"]
        self.callback = callback
        self.dropdown_window = None
        self.dropdown = None
        self.is_visible = True
        self._app_active = True
        self._fits = False
        self._shown = False
        self._last_geometry = None
        self._reposition_after_id = None
        
        self.create_dropdown()
        self.bind_events()
    
    def create_dropdown(self):
        """Create the floating dropdown window"""
        # Create Toplevel window
        self.dropdown_window = tk.Toplevel(self.toplevel)
        self.dropdown_window.withdraw()  # Hide initially
        self.dropdown_window.overrideredirect(True)  # Remove window decorations
        # Tie it to the main window so the window manager hides/lowers it along with the app.
        try:
            self.dropdown_window.transient(self.toplevel)
        except tk.TclError:
            pass
        
        # Make window transparent background (optional)
        try:
            self.dropdown_window.wm_attributes('-transparentcolor', 'gray')
        except:
            pass  # Not supported on all platforms
        
        # Create customtkinter dropdown in the Toplevel window
        self.dropdown = ctk.CTkOptionMenu(
            self.dropdown_window, 
            values=self.options, 
            command=self._on_dropdown_change,
            bg_color="gray"
        )
        self.dropdown.pack(padx=0, pady=0)
        
        # Disable the dropdown
        self.dropdown.configure(state='disabled')
        
        # Stays hidden until the canvas is mapped and has room for it
        self.position_dropdown()

    def update_options(self, options, selected_index=0):
        """Update the dropdown options"""
        self.options = options
        if self.dropdown:
            self.dropdown.configure(state='normal')  # Enable to update
            self.dropdown.configure(values=self.options)
            self.dropdown.set(self.options[selected_index])
            # The new model name may change the widget width
            self._last_geometry = None
            self.position_dropdown()
    
    def _on_dropdown_change(self, choice):
        """Internal callback wrapper"""
        if self.callback:
            self.callback(choice)
    
    def position_dropdown(self):
        """Pin the dropdown to the canvas top right, clamped inside the canvas rectangle"""
        self._reposition_after_id = None
        if not self.dropdown_window:
            return
        try:
            if not self.canvas.winfo_ismapped():
                self._fits = False
                self._apply_visibility()
                return
            
            # Get canvas position and size
            canvas_x = self.canvas.winfo_rootx()
            canvas_y = self.canvas.winfo_rooty()
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            # Fall back to nominal size while the window has not been laid out yet
            width = self.dropdown_window.winfo_reqwidth()
            height = self.dropdown_window.winfo_reqheight()
            width = width if width > 1 else _MIN_WIDTH
            height = height if height > 1 else _MIN_HEIGHT
            
            # Not enough room inside the canvas: hide instead of spilling outside the app
            self._fits = (canvas_width >= width + 2 * _PADDING and
                          canvas_height >= height + 2 * _PADDING)
            if not self._fits:
                self._apply_visibility()
                return
            
            # Top right corner with padding, clamped so it can never leave the canvas
            dropdown_x = canvas_x + canvas_width - width - _PADDING
            dropdown_y = canvas_y + _PADDING
            dropdown_x = max(canvas_x, min(dropdown_x, canvas_x + canvas_width - width))
            dropdown_y = max(canvas_y, min(dropdown_y, canvas_y + canvas_height - height))
            
            geometry = f"+{int(dropdown_x)}+{int(dropdown_y)}"
            if geometry != self._last_geometry:
                self._last_geometry = geometry
                self.dropdown_window.geometry(geometry)
            self._apply_visibility()
        except tk.TclError:
            # Handle case where window is not ready yet
            pass
    
    def _schedule_reposition(self):
        """Coalesce the burst of events a window drag or resize produces"""
        if not self.dropdown_window:
            return
        try:
            if self._reposition_after_id is not None:
                self.canvas.after_cancel(self._reposition_after_id)
            self._reposition_after_id = self.canvas.after(_REPOSITION_DELAY_MS, self.position_dropdown)
        except tk.TclError:
            self._reposition_after_id = None
    
    def _apply_visibility(self):
        """Visible only when wanted, the app is active, and it fits inside the canvas"""
        if not self.dropdown_window:
            return
        should_show = bool(self.is_visible and self._app_active and self._fits)
        if should_show == self._shown:
            return
        self._shown = should_show
        try:
            if should_show:
                self.dropdown_window.deiconify()
                self.dropdown_window.wm_attributes('-topmost', True)
            else:
                self.dropdown_window.wm_attributes('-topmost', False)
                self.dropdown_window.withdraw()
        except tk.TclError:
            pass
    
    def bind_events(self):
        """Bind events for window state management"""
        # parent_window and canvas may be the toplevel itself, so bind each widget once
        widgets = []
        for widget in (self.toplevel, self.parent_window, self.canvas):
            if widget is not None and not any(widget is known for known in widgets):
                widgets.append(widget)
        
        for widget in widgets:
            self._bind(widget, '<Configure>', self._on_geometry_change)
            self._bind(widget, '<Map>', self._on_map)
            self._bind(widget, '<Unmap>', self._on_unmap)
        
        self._bind(self.toplevel, '<FocusIn>', self._on_focus_in)
        self._bind(self.toplevel, '<FocusOut>', self._on_focus_out)
    
    def _bind(self, widget, sequence, handler):
        """Bind additively so handlers other code put on these widgets survive"""
        try:
            widget.bind(sequence, handler, add='+')
        except tk.TclError:
            pass
    
    def _on_geometry_change(self, event):
        """Handle window move, window resize and pane resize"""
        self._schedule_reposition()
    
    def _on_map(self, event):
        """Handle the window or canvas being restored/shown"""
        self._schedule_reposition()
    
    def _on_unmap(self, event):
        """Handle the window being minimized/hidden"""
        # Hide immediately so no stray window is left behind on screen
        self._fits = False
        self._apply_visibility()
    
    def _on_focus_in(self, event):
        """Handle the application window gaining focus"""
        self._app_active = True
        self._schedule_reposition()
    
    def _on_focus_out(self, event):
        """Handle the application window losing focus"""
        try:
            self.toplevel.after(_FOCUS_CHECK_DELAY_MS, self._check_application_focus)
        except tk.TclError:
            pass
    
    def _check_application_focus(self):
        """Check if the entire application has lost focus to another program"""
        try:
            # Returns None when focus left this application entirely
            focused_widget = self.toplevel.focus_displayof()
        except (tk.TclError, KeyError):
            focused_widget = None
        
        active = False
        if focused_widget is not None:
            try:
                owner = focused_widget.winfo_toplevel()
                active = owner is self.toplevel or owner is self.dropdown_window
            except tk.TclError:
                active = False
        
        self._app_active = active
        if active:
            self.position_dropdown()
        else:
            self._apply_visibility()
    
    def show(self):
        """Show the dropdown window"""
        self._app_active = True
        self.position_dropdown()
    
    def hide(self):
        """Hide the dropdown window"""
        self._app_active = False
        self._apply_visibility()
    
    def toggle_visibility(self):
        """Toggle dropdown visibility"""
        self.set_always_visible(not self.is_visible)
    
    def set_always_visible(self, always_visible=True):
        """Set whether dropdown should always be visible when parent is active"""
        self.is_visible = always_visible
        if always_visible:
            self.position_dropdown()
        else:
            self._apply_visibility()
    
    def destroy(self):
        """Clean up the dropdown window"""
        if self._reposition_after_id is not None:
            try:
                self.canvas.after_cancel(self._reposition_after_id)
            except tk.TclError:
                pass
            self._reposition_after_id = None
        
        if self.dropdown_window:
            try:
                self.dropdown_window.destroy()
            except tk.TclError:
                pass
            # Handlers stay bound but become no-ops once this is None
            self.dropdown_window = None


if __name__ == "__main__":
    

    class ZoomableScrollableCanvas:
        def __init__(self, root):
            self.root = root
            self.zoom_factor = 1.0
            self.pan_start_x = 0
            self.pan_start_y = 0
            self.floating_dropdown = None
            
            # Create frame for canvas and scrollbars
            self.frame = tk.Frame(root)
            self.frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=20)
            
            # Create canvas with scrollbars
            self.canvas = tk.Canvas(self.frame, bg="lightgray", 
                                scrollregion=(0, 0, 1000, 1000))
            
            # Create scrollbars
            self.v_scrollbar = tk.Scrollbar(self.frame, orient=tk.VERTICAL, command=self.canvas.yview)
            self.h_scrollbar = tk.Scrollbar(self.frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
            
            # Configure canvas scrolling
            self.canvas.configure(yscrollcommand=self.v_scrollbar.set, 
                                xscrollcommand=self.h_scrollbar.set)
            
            # Pack scrollbars and canvas
            self.v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
            self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            # Bind events for zooming and panning
            self.canvas.bind("<MouseWheel>", self.on_mousewheel)
            self.canvas.bind("<Button-1>", self.on_button_press)
            self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
            self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
            
            # Bind keyboard shortcuts
            self.canvas.bind("<Control-Key-plus>", lambda e: self.zoom(1.1))
            self.canvas.bind("<Control-Key-equal>", lambda e: self.zoom(1.1))  # For + without shift
            self.canvas.bind("<Control-Key-minus>", lambda e: self.zoom(0.9))
            self.canvas.bind("<Control-Key-0>", lambda e: self.reset_zoom())
            
            # Make canvas focusable for keyboard events
            self.canvas.focus_set()
            
            self.setup_canvas_content()
        
        def setup_canvas_content(self):
            # Draw something on the canvas
            self.canvas.create_rectangle(50, 50, 200, 150, fill="skyblue", outline="black", tags="content")
            self.canvas.create_text(125, 100, text="Canvas Area", font=("Arial", 12), tags="content")
            
            # Add more content to demonstrate scrolling
            for i in range(5):
                for j in range(5):
                    x = 300 + i * 120
                    y = 50 + j * 80
                    self.canvas.create_rectangle(x, y, x+80, y+60, 
                                            fill=f"#{(i*j*40)%256:02x}{(i*50)%256:02x}{(j*50)%256:02x}", 
                                            outline="black", tags="content")
                    self.canvas.create_text(x+40, y+30, text=f"Box {i},{j}", 
                                        font=("Arial", 10), tags="content")
            
            # Create floating dropdown using the separate class
            options = ["4b Reasoning (local)", "GPT-5 mini   (online)"]
            self.floating_dropdown = FloatingDropdown(
                parent_window=self.root,
                canvas=self.canvas,
                options=options,
                callback=self.on_dropdown_change
            )
        
        def on_dropdown_change(self, choice):
            """Callback function for dropdown selection"""
            print(f"Dropdown selected: {choice}")
        
        def on_mousewheel(self, event):
            if event.state & 0x4:  # Control key is pressed
                # Zoom
                if event.delta > 0:
                    self.zoom(1.1)
                else:
                    self.zoom(0.9)
            else:
                # Scroll
                if event.state & 0x1:  # Shift key is pressed - horizontal scroll
                    self.canvas.xview_scroll(int(-1 * event.delta / 120), "units")
                else:  # Vertical scroll
                    self.canvas.yview_scroll(int(-1 * event.delta / 120), "units")
        
        def zoom(self, factor):
            self.zoom_factor *= factor
            
            # Scale all content items
            self.canvas.scale("content", 0, 0, factor, factor)
            
            # Update scroll region to match new size
            bbox = self.canvas.bbox("content")
            if bbox:
                self.canvas.configure(scrollregion=bbox)
        
        def reset_zoom(self):
            # Reset zoom to 1.0
            factor = 1.0 / self.zoom_factor
            self.zoom_factor = 1.0
            self.canvas.scale("content", 0, 0, factor, factor)
            
            # Reset scroll region
            bbox = self.canvas.bbox("content")
            if bbox:
                self.canvas.configure(scrollregion=bbox)
        
        def on_button_press(self, event):
            # Record the starting position for panning
            self.canvas.scan_mark(event.x, event.y)
            self.pan_start_x = event.x
            self.pan_start_y = event.y
        
        def on_mouse_drag(self, event):
            # Pan the canvas
            self.canvas.scan_dragto(event.x, event.y, gain=1)
        
        def on_button_release(self, event):
            # End panning
            pass
        
        def destroy(self):
            """Clean up resources when canvas is destroyed"""
            if self.floating_dropdown:
                self.floating_dropdown.destroy()

    # Create main window
    root = ctk.CTk()
    root.title("Zoomable Scrollable Canvas with Dropdown")
    root.geometry("800x600")

    # Create the zoomable scrollable canvas
    zoomable_canvas = ZoomableScrollableCanvas(root)

    # Handle proper cleanup when window is closed
    def on_closing():
        zoomable_canvas.destroy()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # Add instructions
    instructions = ctk.CTkLabel(root, text="Controls: Mouse wheel to scroll, Ctrl+Mouse wheel to zoom, Click and drag to pan, Ctrl+0 to reset zoom")
    instructions.pack(pady=5)

    # Run the application
    root.mainloop()
