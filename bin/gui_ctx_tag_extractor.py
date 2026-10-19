"""
CTX Tag Position Extractor
Tkinter application to extract GmmiPoint tags and their positions from CIMPLICITY .ctx files.
Supports folder selection, canvas preview with zoom/pan, and Excel export.
"""

import os
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class TagPosition:
    """Data class for storing tag position information."""
    filename: str
    tag_name: str
    left: int
    top: int
    right: int
    bottom: int
    
    @property
    def width(self) -> int:
        return abs(self.right - self.left)
    
    @property
    def height(self) -> int:
        return abs(self.top - self.bottom)
    
    @property
    def center_x(self) -> int:
        return (self.left + self.right) // 2
    
    @property
    def center_y(self) -> int:
        return (self.top + self.bottom) // 2


class CTXParser:
    """Parser for CIMPLICITY .ctx files to extract tags and positions."""
    
    # Regex patterns
    GMMI_POINT_PATTERN = re.compile(r'\(GmmiPoint\s+"([^"]+)"\s+\d+\s+\d+\s+\d+\)')
    GMMI_EXPR_PATTERN = re.compile(r'\(GmmiExpr\s+"([^"]+)"\s+\d+\)')
    RECT_PATTERN = re.compile(r'\(Rect\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\)')
    
    # Object types that contain visual elements with positions
    VISUAL_OBJECT_TYPES = [
        'GmmiRectShapeObject',
        'GmmiTextObject',
        'GmmiTextButtonObject',
        'GmmiLineObject',
        'GmmiEllipseObject',
        'GmmiArcObject',
        'GmmiPolylineObject',
        'GmmiPolygonObject',
        'GmmiGroupObject',
        'GmmiContainerObject',
    ]
    
    def __init__(self):
        self.valid_tags: set = set()
        self.tag_positions: List[TagPosition] = []
    
    def parse_file(self, filepath: str) -> List[TagPosition]:
        """Parse a single .ctx file and return list of tag positions."""
        try:
            # Try UTF-16 first (common for CIMPLICITY .ctx files), fallback to UTF-8
            try:
                with open(filepath, 'r', encoding='utf-16') as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
        except Exception as e:
            print(f"Error reading file {filepath}: {e}")
            return []
        
        filename = os.path.basename(filepath)
        
        # First pass: Extract valid GmmiPoint tags (exclude arrays and system vars)
        valid_tags = self._extract_valid_tags(content)
        
        # Second pass: Find visual objects and map tags to positions
        tag_positions = self._extract_tag_positions(content, filename, valid_tags)
        
        return tag_positions
    
    def _extract_valid_tags(self, content: str) -> set:
        """Extract GmmiPoint tags, excluding arrays and system variables."""
        valid_tags = set()
        
        for match in self.GMMI_POINT_PATTERN.finditer(content):
            tag_name = match.group(1).strip()
            
            # Skip array tags (contain '[')
            if '[' in tag_name:
                continue
            
            # Skip system variables (start with '$')
            if tag_name.startswith('$'):
                continue
            
            valid_tags.add(tag_name)
        
        return valid_tags
    
    def _extract_tag_positions(self, content: str, filename: str, valid_tags: set) -> List[TagPosition]:
        """Extract positions for tags from visual objects."""
        tag_positions = []
        found_tag_rects: Dict[str, List[Tuple[int, int, int, int]]] = {}
        
        # Strategy: Find all GmmiExpr occurrences and look for nearest Extents/Rect after them
        # This is more robust than trying to match complex nested S-expressions
        
        # Find all positions of GmmiExpr and Extents in the file
        expr_positions = []  # (position, expression_string)
        for match in self.GMMI_EXPR_PATTERN.finditer(content):
            expr_positions.append((match.start(), match.group(1)))
        
        rect_positions = []  # (position, left, top, right, bottom)
        for match in self.RECT_PATTERN.finditer(content):
            rect_positions.append((
                match.start(),
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
                int(match.group(4))
            ))
        
        # For each expression, find the nearest Rect that comes AFTER it (within reasonable distance)
        # The Extents block typically follows shortly after the GmmiExpr in the same object
        MAX_DISTANCE = 5000  # Characters - Rect should be within this distance after GmmiExpr
        
        for expr_pos, expression in expr_positions:
            # Extract tags from the expression
            tags_in_expr = self._extract_tags_from_expression(expression, valid_tags)
            
            if not tags_in_expr:
                continue
            
            # Find the nearest Rect after this expression
            nearest_rect = None
            for rect_pos, left, top, right, bottom in rect_positions:
                if rect_pos > expr_pos and rect_pos - expr_pos < MAX_DISTANCE:
                    nearest_rect = (left, top, right, bottom)
                    break
            
            if nearest_rect:
                left, top, right, bottom = nearest_rect
                for tag_name in tags_in_expr:
                    if tag_name not in found_tag_rects:
                        found_tag_rects[tag_name] = []
                    
                    # Avoid duplicate rects for the same tag
                    if nearest_rect not in found_tag_rects[tag_name]:
                        found_tag_rects[tag_name].append(nearest_rect)
        
        # Create TagPosition objects
        for tag_name, rects in found_tag_rects.items():
            for left, top, right, bottom in rects:
                tag_positions.append(TagPosition(
                    filename=filename,
                    tag_name=tag_name,
                    left=left,
                    top=top,
                    right=right,
                    bottom=bottom
                ))
        
        return tag_positions
    
    def _extract_tags_from_expression(self, expression: str, valid_tags: set) -> List[str]:
        """Extract individual tag names from a GmmiExpr expression string."""
        found_tags = []
        
        # Split expression by common operators and whitespace
        # Operators: AND, OR, NOT, EQ, NE, LT, GT, LE, GE, +, -, *, /, (, )
        tokens = re.split(r'\s+|(?:AND|OR|NOT|EQ|NE|LT|GT|LE|GE|[+\-*/(),])+', expression)
        
        for token in tokens:
            token = token.strip()
            if token and token in valid_tags:
                found_tags.append(token)
        
        return found_tags


class CanvasPreview(tk.Canvas):
    """Canvas widget for displaying tag positions with zoom and pan."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg='#2d2d2d', highlightthickness=0, **kwargs)
        
        self.tag_positions: List[TagPosition] = []
        self.rect_ids: Dict[int, TagPosition] = {}  # canvas rect id -> TagPosition
        self.selected_rect_id: Optional[int] = None
        
        # View transformation
        self.scale = 0.1  # Initial scale factor
        self.offset_x = 50
        self.offset_y = 50
        
        # Pan state
        self._pan_start_x = 0
        self._pan_start_y = 0
        
        # Bind events
        self.bind('<Configure>', self._on_configure)
        self.bind('<Control-MouseWheel>', self._on_zoom)
        self.bind('<MouseWheel>', self._on_scroll_vertical)
        self.bind('<Shift-MouseWheel>', self._on_scroll_horizontal)
        self.bind('<ButtonPress-1>', self._on_pan_start)
        self.bind('<B1-Motion>', self._on_pan_move)
        self.bind('<ButtonRelease-1>', self._on_click)
        
        # Callback for selection
        self.on_select_callback = None
    
    def set_data(self, tag_positions: List[TagPosition]):
        """Set the tag positions to display."""
        self.tag_positions = tag_positions
        self._fit_to_view()
        self._redraw()
    
    def _fit_to_view(self):
        """Adjust scale and offset to fit all rectangles in view."""
        if not self.tag_positions:
            return
        
        # Find bounds (negate Y to flip from math coords to screen coords)
        min_x = min(tp.left for tp in self.tag_positions)
        max_x = max(tp.right for tp in self.tag_positions)
        min_y = min(-tp.top for tp in self.tag_positions)
        max_y = max(-tp.bottom for tp in self.tag_positions)
        
        data_width = max_x - min_x
        data_height = max_y - min_y
        
        if data_width == 0 or data_height == 0:
            return
        
        canvas_width = self.winfo_width() or 400
        canvas_height = self.winfo_height() or 400
        
        # Calculate scale to fit with padding
        padding = 40
        scale_x = (canvas_width - 2 * padding) / data_width
        scale_y = (canvas_height - 2 * padding) / data_height
        self.scale = min(scale_x, scale_y)
        
        # Center the view
        self.offset_x = padding - min_x * self.scale
        self.offset_y = padding - min_y * self.scale
    
    def _redraw(self):
        """Redraw all rectangles on the canvas."""
        self.delete('all')
        self.rect_ids.clear()
        
        for tp in self.tag_positions:
            # Transform coordinates (negate Y to convert from math to screen coords)
            x1 = tp.left * self.scale + self.offset_x
            y1 = (-tp.top) * self.scale + self.offset_y
            x2 = tp.right * self.scale + self.offset_x
            y2 = (-tp.bottom) * self.scale + self.offset_y
            
            # Draw rectangle
            rect_id = self.create_rectangle(
                x1, y1, x2, y2,
                outline='#4a9eff',
                fill='',
                width=1,
                tags=('rect',)
            )
            self.rect_ids[rect_id] = tp
        
        # Redraw selection if any
        if self.selected_rect_id and self.selected_rect_id in self.rect_ids:
            self._highlight_rect(self.selected_rect_id)
    
    def _highlight_rect(self, rect_id: int):
        """Highlight a rectangle."""
        # Reset previous selection
        for rid in self.rect_ids:
            self.itemconfig(rid, outline='#4a9eff', fill='', width=1)
        
        # Highlight selected
        if rect_id:
            self.itemconfig(rect_id, outline='#ff6b6b', fill='#ffcccc', width=2)
            self.tag_raise(rect_id)
    
    def select_by_tag_position(self, tp: TagPosition):
        """Select a rectangle by TagPosition object."""
        for rect_id, tag_pos in self.rect_ids.items():
            if (tag_pos.tag_name == tp.tag_name and 
                tag_pos.left == tp.left and 
                tag_pos.top == tp.top and
                tag_pos.filename == tp.filename):
                self.selected_rect_id = rect_id
                self._highlight_rect(rect_id)
                
                # Scroll to make visible
                x1 = tp.left * self.scale + self.offset_x
                y1 = (-tp.top) * self.scale + self.offset_y
                self.scan_mark(0, 0)
                break
    
    def _on_configure(self, event):
        """Handle canvas resize."""
        if self.tag_positions:
            self._fit_to_view()
            self._redraw()
    
    def _on_zoom(self, event):
        """Handle zoom with Ctrl+MouseWheel."""
        # Get mouse position for zoom center
        mouse_x = self.canvasx(event.x)
        mouse_y = self.canvasy(event.y)
        
        # Calculate zoom factor
        if event.delta > 0:
            factor = 1.2
        else:
            factor = 0.8
        
        # Limit zoom
        new_scale = self.scale * factor
        if 0.01 <= new_scale <= 10:
            # Adjust offset to zoom toward mouse position
            self.offset_x = mouse_x - (mouse_x - self.offset_x) * factor
            self.offset_y = mouse_y - (mouse_y - self.offset_y) * factor
            self.scale = new_scale
            self._redraw()
    
    def _on_scroll_vertical(self, event):
        """Handle vertical scroll."""
        delta = -event.delta // 4
        self.offset_y -= delta
        self._redraw()
    
    def _on_scroll_horizontal(self, event):
        """Handle horizontal scroll with Shift+MouseWheel."""
        delta = -event.delta // 4
        self.offset_x -= delta
        self._redraw()
    
    def _on_pan_start(self, event):
        """Start panning."""
        self._pan_start_x = event.x
        self._pan_start_y = event.y
    
    def _on_pan_move(self, event):
        """Handle pan movement."""
        dx = event.x - self._pan_start_x
        dy = event.y - self._pan_start_y
        self._pan_start_x = event.x
        self._pan_start_y = event.y
        
        self.offset_x += dx
        self.offset_y += dy
        self._redraw()
    
    def _on_click(self, event):
        """Handle click to select rectangle."""
        # Find clicked item
        x = event.x
        y = event.y
        items = self.find_overlapping(x-2, y-2, x+2, y+2)
        
        for item in items:
            if item in self.rect_ids:
                self.selected_rect_id = item
                self._highlight_rect(item)
                
                # Trigger callback
                if self.on_select_callback:
                    self.on_select_callback(self.rect_ids[item])
                break


class CTXTagExtractorApp:
    """Main application class for CTX Tag Position Extractor."""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("CTX Tag Position Extractor")
        self.root.geometry("1200x700")
        self.root.minsize(800, 500)
        
        # Configure style
        self._configure_style()
        
        # Data storage
        self.tag_positions: List[TagPosition] = []
        self.parser = CTXParser()
        
        # Build UI
        self._create_toolbar()
        self._create_main_content()
        self._create_status_bar()
        
        # Bind window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _configure_style(self):
        """Configure ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure Treeview
        style.configure('Treeview',
                        background='#ffffff',
                        foreground='#333333',
                        fieldbackground='#ffffff',
                        rowheight=25)
        style.configure('Treeview.Heading',
                        font=('Segoe UI', 9, 'bold'))
        style.map('Treeview',
                  background=[('selected', '#0078d4')],
                  foreground=[('selected', '#ffffff')])
    
    def _create_toolbar(self):
        """Create the toolbar with buttons."""
        toolbar = ttk.Frame(self.root, padding=(10, 5))
        toolbar.pack(fill='x', side='top')
        
        # Select Folder button
        self.btn_select_folder = ttk.Button(
            toolbar,
            text="📁 Select Folder",
            command=self._on_select_folder
        )
        self.btn_select_folder.pack(side='left', padx=(0, 10))
        
        # Export to Excel button
        self.btn_export = ttk.Button(
            toolbar,
            text="📊 Export to Excel",
            command=self._on_export,
            state='disabled'
        )
        self.btn_export.pack(side='left', padx=(0, 10))
        
        # Clear button
        self.btn_clear = ttk.Button(
            toolbar,
            text="🗑 Clear",
            command=self._on_clear,
            state='disabled'
        )
        self.btn_clear.pack(side='left', padx=(0, 10))
        
        # Folder path label
        self.lbl_folder = ttk.Label(toolbar, text="No folder selected", foreground='#666666')
        self.lbl_folder.pack(side='left', padx=(20, 0))
        
        # File count label
        self.lbl_count = ttk.Label(toolbar, text="", foreground='#666666')
        self.lbl_count.pack(side='right')
        
        # --- Search bar ---
        search_bar = ttk.Frame(self.root, padding=(10, 3))
        search_bar.pack(fill='x', side='top')
        
        ttk.Label(search_bar, text="🔍 Filename:").pack(side='left')
        self.search_filename_var = tk.StringVar()
        self.search_filename_var.trace_add('write', lambda *_: self._apply_search_filter())
        self.search_filename_entry = ttk.Entry(
            search_bar, textvariable=self.search_filename_var, width=25
        )
        self.search_filename_entry.pack(side='left', padx=(5, 15))
        
        ttk.Label(search_bar, text="🔍 Tag Name:").pack(side='left')
        self.search_tagname_var = tk.StringVar()
        self.search_tagname_var.trace_add('write', lambda *_: self._apply_search_filter())
        self.search_tagname_entry = ttk.Entry(
            search_bar, textvariable=self.search_tagname_var, width=25
        )
        self.search_tagname_entry.pack(side='left', padx=(5, 15))
        
        # Clear search button
        self.btn_clear_search = ttk.Button(
            search_bar,
            text="✕ Clear Search",
            command=self._clear_search
        )
        self.btn_clear_search.pack(side='left', padx=(0, 10))
        
        # Match count label
        self.lbl_match_count = ttk.Label(search_bar, text="", foreground='#666666')
        self.lbl_match_count.pack(side='right')
    
    def _create_main_content(self):
        """Create the main content area with paned window."""
        # Main paned window
        self.paned = ttk.PanedWindow(self.root, orient='horizontal')
        self.paned.pack(fill='both', expand=True, padx=10, pady=(5, 0))
        
        # Left frame - Treeview
        left_frame = ttk.Frame(self.paned)
        self.paned.add(left_frame, weight=2)
        
        self._create_treeview(left_frame)
        
        # Right frame - Canvas preview
        right_frame = ttk.Frame(self.paned)
        self.paned.add(right_frame, weight=3)
        
        self._create_canvas_preview(right_frame)
    
    def _create_treeview(self, parent):
        """Create the treeview for displaying tag positions."""
        # Treeview with scrollbars
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill='both', expand=True)
        
        # Columns
        columns = ('filename', 'tag_name', 'size', 'width', 'height', 'left', 'top', 'right', 'bottom')
        
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', selectmode='browse')
        
        # Define headings
        self.tree.heading('filename', text='Filename', anchor='w', command=lambda: self._sort_column('filename'))
        self.tree.heading('tag_name', text='Tag Name', anchor='w', command=lambda: self._sort_column('tag_name'))
        self.tree.heading('size', text='Size', anchor='center', command=lambda: self._sort_column('size'))
        self.tree.heading('width', text='Width', anchor='center', command=lambda: self._sort_column('width'))
        self.tree.heading('height', text='Height', anchor='center', command=lambda: self._sort_column('height'))
        self.tree.heading('left', text='Left', anchor='center', command=lambda: self._sort_column('left'))
        self.tree.heading('top', text='Top', anchor='center', command=lambda: self._sort_column('top'))
        self.tree.heading('right', text='Right', anchor='center', command=lambda: self._sort_column('right'))
        self.tree.heading('bottom', text='Bottom', anchor='center', command=lambda: self._sort_column('bottom'))
        
        # Define column widths
        self.tree.column('filename', width=150, minwidth=100)
        self.tree.column('tag_name', width=150, minwidth=100)
        self.tree.column('size', width=100, minwidth=80, anchor='center')
        self.tree.column('width', width=60, minwidth=50, anchor='center')
        self.tree.column('height', width=60, minwidth=50, anchor='center')
        self.tree.column('left', width=70, minwidth=50, anchor='center')
        self.tree.column('top', width=70, minwidth=50, anchor='center')
        self.tree.column('right', width=70, minwidth=50, anchor='center')
        self.tree.column('bottom', width=70, minwidth=50, anchor='center')
        
        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid layout
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Bind selection
        self.tree.bind('<<TreeviewSelect>>', self._on_tree_select)
        
        # Sort state
        self._sort_reverse = {}
    
    def _create_canvas_preview(self, parent):
        """Create the canvas preview area."""
        # Top bar with file selector
        top_bar = ttk.Frame(parent)
        top_bar.pack(fill='x', pady=(0, 5))
        
        # Label
        lbl = ttk.Label(top_bar, text="Preview (Ctrl+Scroll to zoom, Drag to pan)", font=('Segoe UI', 9))
        lbl.pack(side='left')
        
        # File selector dropdown
        ttk.Label(top_bar, text="  File:").pack(side='left', padx=(20, 5))
        self.file_selector_var = tk.StringVar(value="All Files")
        self.file_selector = ttk.Combobox(
            top_bar, 
            textvariable=self.file_selector_var,
            state='readonly',
            width=30
        )
        self.file_selector.pack(side='left')
        self.file_selector.bind('<<ComboboxSelected>>', self._on_file_selected)
        
        # Canvas
        canvas_frame = ttk.Frame(parent, relief='sunken', borderwidth=1)
        canvas_frame.pack(fill='both', expand=True)
        
        self.canvas = CanvasPreview(canvas_frame)
        self.canvas.pack(fill='both', expand=True)
        
        # Set callback for canvas selection
        self.canvas.on_select_callback = self._on_canvas_select
    
    def _create_status_bar(self):
        """Create the status bar showing max dimensions."""
        status_frame = ttk.Frame(self.root, padding=(10, 5))
        status_frame.pack(fill='x', side='bottom')
        
        # Max dimensions label
        self.lbl_max_dims = ttk.Label(
            status_frame,
            text="Max Dimensions: -- x --",
            font=('Segoe UI', 9, 'bold')
        )
        self.lbl_max_dims.pack(side='left')
        
        # Total tags label
        self.lbl_total_tags = ttk.Label(
            status_frame,
            text="Total Tags: 0",
            font=('Segoe UI', 9)
        )
        self.lbl_total_tags.pack(side='right')
    
    def _on_select_folder(self):
        """Handle folder selection."""
        folder = filedialog.askdirectory(
            title="Select folder containing .ctx files",
            mustexist=True
        )
        
        if not folder:
            return
        
        self._process_folder(folder)
    
    def _process_folder(self, folder: str):
        """Process all .ctx files in the selected folder."""
        self.root.config(cursor='wait')
        self.root.update()
        
        try:
            # Find all .ctx files
            ctx_files = []
            for root_dir, dirs, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith('.ctx'):
                        ctx_files.append(os.path.join(root_dir, file))
            
            if not ctx_files:
                messagebox.showwarning(
                    "No Files Found",
                    "No .ctx files were found in the selected folder."
                )
                return
            
            # Parse files
            self.tag_positions.clear()
            
            for filepath in ctx_files:
                positions = self.parser.parse_file(filepath)
                self.tag_positions.extend(positions)
            
            # Update UI
            self._populate_treeview()
            self._update_file_selector()
            self._update_canvas()
            self._update_status()
            
            # Update labels
            self.lbl_folder.config(text=folder)
            self.lbl_count.config(text=f"{len(ctx_files)} file(s) processed")
            
            # Enable buttons
            self.btn_export.config(state='normal')
            self.btn_clear.config(state='normal')
            
        except Exception as e:
            messagebox.showerror("Error", f"Error processing files:\n{str(e)}")
        finally:
            self.root.config(cursor='')
    
    def _populate_treeview(self):
        """Populate the treeview with tag positions, respecting active search filters."""
        self._apply_search_filter()
    
    def _update_file_selector(self):
        """Update the file selector dropdown with available files."""
        if not self.tag_positions:
            self.file_selector['values'] = ['All Files']
            self.file_selector_var.set('All Files')
            return
        
        # Get unique filenames
        filenames = sorted(set(tp.filename for tp in self.tag_positions))
        self.file_selector['values'] = ['All Files'] + filenames
        
        # Select first file by default (not "All Files")
        if filenames:
            self.file_selector_var.set(filenames[0])
    
    def _on_file_selected(self, event=None):
        """Handle file selection from dropdown."""
        self._update_canvas()
        self._update_status()
    
    def _get_filtered_positions(self) -> List[TagPosition]:
        """Get tag positions filtered by selected file."""
        selected_file = self.file_selector_var.get()
        if selected_file == 'All Files':
            return self.tag_positions
        return [tp for tp in self.tag_positions if tp.filename == selected_file]
    
    def _update_canvas(self):
        """Update the canvas preview."""
        filtered = self._get_filtered_positions()
        self.canvas.set_data(filtered)
    
    def _update_status(self):
        """Update the status bar with max dimensions."""
        filtered = self._get_filtered_positions()
        
        if not filtered:
            self.lbl_max_dims.config(text="Max Dimensions: -- x --")
            self.lbl_total_tags.config(text="Total Tags: 0")
            return
        
        max_right = max(tp.right for tp in filtered)
        max_top = max(tp.top for tp in filtered)
        
        self.lbl_max_dims.config(text=f"Max Dimensions: {max_right} x {max_top}")
        self.lbl_total_tags.config(text=f"Total Tags: {len(filtered)} (of {len(self.tag_positions)} total)")
    
    def _sort_column(self, col: str):
        """Sort treeview by column."""
        # Toggle sort direction
        reverse = self._sort_reverse.get(col, False)
        self._sort_reverse[col] = not reverse
        
        # Get all items
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        
        # Sort - numeric for position and size columns
        if col in ('left', 'top', 'right', 'bottom', 'width', 'height'):
            items.sort(key=lambda t: int(t[0]), reverse=reverse)
        elif col == 'size':
            # Sort by area (width * height) for size column
            def get_area(val):
                try:
                    w, h = val.split('x')
                    return int(w) * int(h)
                except:
                    return 0
            items.sort(key=lambda t: get_area(t[0]), reverse=reverse)
        else:
            items.sort(key=lambda t: t[0].lower(), reverse=reverse)
        
        # Rearrange items
        for index, (val, k) in enumerate(items):
            self.tree.move(k, '', index)
    
    def _on_tree_select(self, event):
        """Handle treeview selection - highlight on canvas and auto-select file."""
        selection = self.tree.selection()
        if selection:
            index = int(selection[0])
            if 0 <= index < len(self.tag_positions):
                tp = self.tag_positions[index]
                
                # Auto-select the file in dropdown if different
                if self.file_selector_var.get() != tp.filename:
                    self.file_selector_var.set(tp.filename)
                    self._update_canvas()
                    self._update_status()
                
                # Highlight on canvas
                self.canvas.select_by_tag_position(tp)
    
    def _on_canvas_select(self, tp: TagPosition):
        """Handle canvas selection - select in treeview."""
        for i, tag_pos in enumerate(self.tag_positions):
            if (tag_pos.tag_name == tp.tag_name and 
                tag_pos.left == tp.left and 
                tag_pos.top == tp.top and
                tag_pos.filename == tp.filename):
                item_id = str(i)
                self.tree.selection_set(item_id)
                self.tree.see(item_id)
                break
    
    def _on_export(self):
        """Export data to Excel."""
        if not self.tag_positions:
            messagebox.showwarning("No Data", "No data to export.")
            return
        
        # Ask for save location
        filepath = filedialog.asksaveasfilename(
            title="Export to Excel",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        
        if not filepath:
            return
        
        try:
            self._export_to_excel(filepath)
            messagebox.showinfo("Export Complete", f"Data exported to:\n{filepath}")
        except ImportError:
            messagebox.showerror(
                "Missing Package",
                "The 'openpyxl' package is required for Excel export.\n"
                "Install it with: pip install openpyxl"
            )
        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting data:\n{str(e)}")
    
    def _export_to_excel(self, filepath: str):
        """Export tag positions to Excel file."""
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Tag Positions"
        
        # Header style
        header_font = Font(bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='0078D4', end_color='0078D4', fill_type='solid')
        header_alignment = Alignment(horizontal='center', vertical='center')
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Headers
        headers = ['Filename', 'Tag Name', 'Size', 'Width', 'Height', 'Left', 'Top', 'Right', 'Bottom']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
        
        # Data rows
        for row, tp in enumerate(self.tag_positions, 2):
            ws.cell(row=row, column=1, value=tp.filename).border = thin_border
            ws.cell(row=row, column=2, value=tp.tag_name).border = thin_border
            ws.cell(row=row, column=3, value=f"{tp.width}x{tp.height}").border = thin_border
            ws.cell(row=row, column=4, value=tp.width).border = thin_border
            ws.cell(row=row, column=5, value=tp.height).border = thin_border
            ws.cell(row=row, column=6, value=tp.left).border = thin_border
            ws.cell(row=row, column=7, value=tp.top).border = thin_border
            ws.cell(row=row, column=8, value=tp.right).border = thin_border
            ws.cell(row=row, column=9, value=tp.bottom).border = thin_border
        
        # Auto-adjust column widths
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2)
            ws.column_dimensions[column].width = adjusted_width
        
        # Add summary row
        summary_row = len(self.tag_positions) + 3
        ws.cell(row=summary_row, column=1, value="Max Dimensions:").font = Font(bold=True)
        
        if self.tag_positions:
            max_right = max(tp.right for tp in self.tag_positions)
            max_top = max(tp.top for tp in self.tag_positions)
            ws.cell(row=summary_row, column=2, value=f"{max_right} x {max_top}")
        
        ws.cell(row=summary_row + 1, column=1, value="Total Tags:").font = Font(bold=True)
        ws.cell(row=summary_row + 1, column=2, value=len(self.tag_positions))
        
        # Freeze header row
        ws.freeze_panes = 'A2'
        
        wb.save(filepath)
    
    def _apply_search_filter(self):
        """Filter the treeview based on filename and tag name search terms."""
        filename_query = self.search_filename_var.get().strip().lower()
        tagname_query = self.search_tagname_var.get().strip().lower()
        
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Build filtered list with original indices
        self._filtered_indices = []
        for i, tp in enumerate(self.tag_positions):
            if filename_query and filename_query not in tp.filename.lower():
                continue
            if tagname_query and tagname_query not in tp.tag_name.lower():
                continue
            self._filtered_indices.append(i)
            self.tree.insert('', 'end', iid=str(i), values=(
                tp.filename,
                tp.tag_name,
                f"{tp.width}x{tp.height}",
                tp.width,
                tp.height,
                tp.left,
                tp.top,
                tp.right,
                tp.bottom
            ))
        
        # Update match count label
        total = len(self.tag_positions)
        shown = len(self._filtered_indices)
        if filename_query or tagname_query:
            self.lbl_match_count.config(text=f"Showing {shown} of {total}")
        else:
            self.lbl_match_count.config(text="")
        
        # Update canvas with filtered positions
        filtered_positions = [self.tag_positions[i] for i in self._filtered_indices]
        self.canvas.set_data(filtered_positions)
    
    def _clear_search(self):
        """Clear both search fields."""
        self.search_filename_var.set('')
        self.search_tagname_var.set('')
    
    def _on_clear(self):
        """Clear all data."""
        self.tag_positions.clear()
        
        # Clear treeview
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Clear canvas
        self.canvas.delete('all')
        self.canvas.tag_positions = []
        self.canvas.rect_ids.clear()
        
        # Clear search fields
        self._clear_search()
        
        # Reset labels
        self.lbl_folder.config(text="No folder selected")
        self.lbl_count.config(text="")
        self._update_status()
        
        # Disable buttons
        self.btn_export.config(state='disabled')
        self.btn_clear.config(state='disabled')
    
    def _on_close(self):
        """Handle window close."""
        self.root.destroy()


def main():
    """Main entry point."""
    root = tk.Tk()
    app = CTXTagExtractorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
