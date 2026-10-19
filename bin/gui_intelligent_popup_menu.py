import tkinter as tk
import time

class IntelligenceEnabledPopupMenu:
    """
    A flicker-free, borderless popup menu implemented with Toplevel.
    Supports dynamic info rows (updated via callables) and command rows.
    Includes thinking animation before showing menu options.
    """
    def __init__(self, master, bg="#f0f0f0", fg="#000", border="#c0c0c0"):
        self.master = master
        self.bg = bg
        self.fg = fg
        self.border = border

        self.popup = tk.Toplevel(master)
        self.popup.withdraw()
        self.popup.overrideredirect(True)  # no window chrome
        self.popup.configure(bg=self.border)
        self.popup.attributes("-topmost", True)  # stay above

        # Container frame (1px border effect via outer bg)
        self.frame = tk.Frame(self.popup, bg=self.bg, bd=0)
        self.frame.pack(padx=1, pady=1)

        # Rows will be a list of dicts: {'type': 'info'|'command'|'separator', ...}
        self.rows = []
        self.update_job = None
        self.is_open = False
        
        # Thinking animation variables
        self.thinking_mode = False
        self.thinking_label = None
        self.thinking_animation_job = None
        self.thinking_dots = 0
        self.thinking_callback = None

        # Close on escape
        self.popup.bind("<Escape>", lambda e: self.close())

        # Close when focus leaves (common for menus)
        #self.popup.bind("<FocusOut>", lambda e: self.close())

        # Global click handling to dismiss when clicking outside
        self.popup.bind("<ButtonPress-1>", self._on_mouse_press_anywhere, add="+")
        self.popup.bind("<ButtonPress-3>", self._on_mouse_press_anywhere, add="+")
        # Prevent clicks inside content from propagating
        self.frame.bind("<ButtonPress-1>", lambda e: "break")
        self.frame.bind("<ButtonPress-3>", lambda e: "break")

    # ---------- Public API ----------

    def add_info(self, provider, font=("Segoe UI", 9), pad=(14, 6)):
        """
        Add a non-interactive info row whose text comes from provider() -> str.
        """
        var = tk.StringVar(value="")
        lbl = tk.Label(self.frame, textvariable=var, bg=self.bg, fg=self.fg,
                       anchor="w", font=font)
        lbl.pack(fill="x", padx=(pad[0], 8), pady=(pad[1]//2, pad[1]//2))
        self.rows.append({
            "type": "info",
            "var": var,
            "provider": provider,
            "widget": lbl,
            "last_text": None
        })

    def add_separator(self):
        sep = tk.Frame(self.frame, bg=self.border, height=1)
        sep.pack(fill="x", padx=6, pady=4)
        self.rows.append({"type": "separator", "widget": sep})

    def add_command(self, label, command, font=("Segoe UI", 9), pad=(10, 6),
                    hover_bg="#0078d7"):
        """
        Add a clickable command row.
        """
        container = tk.Frame(self.frame, bg=self.bg)
        container.pack(fill="x")

        lbl = tk.Label(container, text=label, bg=self.bg, fg=self.fg,
                       anchor="w", font=font)
        lbl.pack(fill="x", padx=(pad[0], 8), pady=(pad[1]//2, pad[1]//2))

        def on_enter(_):
            container.configure(bg=hover_bg)
            lbl.configure(bg=hover_bg)

        def on_leave(_):
            container.configure(bg=self.bg)
            lbl.configure(bg=self.bg)

        def on_click(_):
            self.close()
            command()

        container.bind("<Enter>", on_enter)
        container.bind("<Leave>", on_leave)
        container.bind("<ButtonRelease-1>", on_click)
        lbl.bind("<ButtonRelease-1>", on_click)

        self.rows.append({
            "type": "command",
            "widget": container,
            "label_widget": lbl
        })

    def clear_rows(self):
        """Clear all existing rows from the menu"""
        for row in self.rows:
            if row.get("widget") and row["widget"].winfo_exists():
                row["widget"].destroy()
        self.rows.clear()

    def show_thinking_at(self, x, y, thinking_text="Thinking"):
        """
        Show thinking animation at screen coords (x, y), then call callback to populate menu.
        
        Args:
            x, y: Screen coordinates
            thinking_text: Base text to show (dots will be animated)
        """
        if self.is_open:
            self.close()

        self.is_open = True
        self.thinking_mode = True
        self.thinking_dots = 0

        # Create thinking label
        self.thinking_label = tk.Label(
            self.frame, 
            text=thinking_text + "   ", 
            bg=self.bg, 
            fg=self.fg,
            anchor="w", 
            font=("Segoe UI", 9),
            padx=14,
            pady=8
        )
        self.thinking_label.pack(fill="x")

        # Show popup
        self.popup.geometry(f"+{int(x)}+{int(y)}")
        self.popup.deiconify()
        self.popup.lift()
        try:
            self.popup.focus_set()
        except Exception:
            pass

        # Grab ensures clicks go through us
        try:
            pass
            #self.popup.grab_set()
        except Exception:
            pass

        # Start thinking animation
        self._start_thinking_animation()
        
    

    def _start_thinking_animation(self):
        """Start the animated dots for thinking"""
        def animate():
            if not self.thinking_mode or not self.is_open:
                return
                
            self.thinking_dots = (self.thinking_dots + 1) % 4
            dots = "." * self.thinking_dots + " " * (3 - self.thinking_dots)
            
            if self.thinking_label and self.thinking_label.winfo_exists():
                current_text = self.thinking_label.cget("text")
                base_text = current_text.split("   ")[0] if "   " in current_text else "Thinking"
                self.thinking_label.config(text=f"{base_text}{dots}")
            
            self.thinking_animation_job = self.master.after(300, animate)
        
        animate()

    def finished_thinking(self):
        """Finish thinking animation and populate menu"""
        self.thinking_mode = False
        
        # Stop thinking animation
        if self.thinking_animation_job:
            try:
                self.master.after_cancel(self.thinking_animation_job)
            except Exception:
                pass
            self.thinking_animation_job = None
        
        # Remove thinking label
        if self.thinking_label and self.thinking_label.winfo_exists():
            self.thinking_label.destroy()
            self.thinking_label = None
        
            
        # Start normal updater if we have dynamic rows
        self._start_updater(100)

    def show_at(self, x, y, update_interval_ms=100):
        """
        Show the popup at screen coords (x, y) and start the dynamic updater.
        """
        if self.is_open:
            self.close()

        self.is_open = True
        self.popup.geometry(f"+{int(x)}+{int(y)}")
        self.popup.deiconify()
        self.popup.lift()
        try:
            self.popup.focus_set()
        except Exception:
            pass

        # Grab ensures clicks go through us so we can detect outside clicks reliably
        try:
            self.popup.grab_set()
        except Exception:
            pass

        self._start_updater(update_interval_ms)

    def close(self):
        if not self.is_open:
            return
        self.is_open = False
        self.thinking_mode = False
        
        # Stop all animations and updaters
        self._stop_updater()
        if self.thinking_animation_job:
            try:
                self.master.after_cancel(self.thinking_animation_job)
            except Exception:
                pass
            self.thinking_animation_job = None
            
        # Clean up thinking label
        if self.thinking_label and self.thinking_label.winfo_exists():
            self.thinking_label.destroy()
            self.thinking_label = None
            
        # Clear all menu rows
        self.clear_rows()
            
        try:
            self.popup.grab_release()
        except Exception:
            pass
        self.popup.withdraw()

    # ---------- Internals ----------

    def _start_updater(self, interval):
        # Update only when text actually changes (prevents any micro-flicker)
        def tick():
            if not self.is_open:
                return

            for row in self.rows:
                if row["type"] == "info":
                    try:
                        text = row["provider"]()
                    except Exception as ex:
                        text = f"(error: {ex})"
                    if text != row["last_text"]:
                        row["var"].set(text)
                        row["last_text"] = text

            self.update_job = self.master.after(interval, tick)

        tick()

    def _stop_updater(self):
        if self.update_job is not None:
            try:
                self.master.after_cancel(self.update_job)
            except Exception:
                pass
            self.update_job = None

    def _on_mouse_press_anywhere(self, event):
        """
        If click lands outside our content, close. Because we took a grab,
        clicks outside will still arrive; we can check pointer containment.
        """
        # Where is the pointer?
        x_root = self.popup.winfo_pointerx()
        y_root = self.popup.winfo_pointery()
        widget_under = self.popup.winfo_containing(x_root, y_root)
        inside = False
        if widget_under is not None:
            # Check if widget_under is the popup or one of its descendants
            w = widget_under
            while w is not None:
                if w is self.popup:
                    inside = True
                    break
                w = w.master
        if not inside:
            self.close()

class DemoApp:
    def __init__(self, root):
        root.title("Right-click for thinking animation popup")
        self.root = root

        self.canvas = tk.Canvas(root, width=460, height=220, bg="#20232a", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_text(
            230, 110,
            text="Right-click here to see thinking animation then menu options",
            fill="#61dafb",
            font=("Segoe UI", 12)
        )

        # Prepare popup
        self.menu = IntelligenceEnabledPopupMenu(root)
        self.opened_at = None

        # Bind right-click (Windows/Linux <Button-3>, macOS may send <Button-2>)
        self.canvas.bind("<Button-3>", self._show)
        self.canvas.bind("<Button-2>", self._show)

    def _show(self, event):
        self.opened_at = time.perf_counter()
        
        # Add static options first
        self._add_static_options()
        
        # Show thinking animation, then populate additional menu
        self.menu.show_thinking_at(
            event.x_root + 2, 
            event.y_root + 2, 
            thinking_text="Thinking",
            callback=self._populate_menu,
            thinking_duration=2500  # 2.5 seconds of thinking
        )
        
    def _add_static_options(self):
        """Add static menu options that appear immediately"""
        # Clear any existing rows first
        self.menu.clear_rows()
        
        # Add static options
        self.menu.add_command("📋Copy", lambda: self._execute_action("Text copied to clipboard!"))
        self.menu.add_command("📋Highlight", lambda: self._execute_action("Text highlighted!"))
        self.menu.add_separator()

    def _populate_menu(self):
        """Called after thinking animation to populate the menu with additional options"""
        # Add dynamic info rows (static options are already there)
        self.menu.add_info(lambda: f"Uptime: {self._uptime():.1f} s")
        self.menu.add_separator()
        
        # Add additional command options
        self.menu.add_command("📝 Create Document", lambda: self._execute_action("Document created!"))
        self.menu.add_command("🔧 Settings", lambda: self._execute_action("Settings opened!"))
        self.menu.add_command(" Deploy", lambda: self._execute_action("Deployment started!"))

    def _uptime(self):
        if self.opened_at is None:
            return 0.0
        return time.perf_counter() - self.opened_at

    def _execute_action(self, message):
        self.canvas.delete("all")
        self.canvas.create_text(
            230, 110,
            text=message,
            fill="#98c379",
            font=("Segoe UI", 14, "bold")
        )
        # Reset after 2 seconds
        self.root.after(2000, self._reset_canvas)
    
    def _reset_canvas(self):
        self.canvas.delete("all")
        self.canvas.create_text(
            230, 110,
            text="Right-click here to see thinking animation then menu options",
            fill="#61dafb",
            font=("Segoe UI", 12)
        )

if __name__ == "__main__":
    root = tk.Tk()
    app = DemoApp(root)
    root.mainloop()
