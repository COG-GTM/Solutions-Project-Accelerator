from io import BytesIO
import logging
import os
from threading import Thread
import time
from tkinter import font, messagebox, ttk
import tkinter as tk
import math
import uuid
import warnings
import cairosvg
from PIL import Image, ImageDraw, ImageFilter
import re
from xml.etree import ElementTree as ET
from PIL import ImageTk, Image

from bin.gui_scan_progress_banner import banner_handler
try:
    from bin.logic_internal_database import Database
    from bin.logic_acm_data_handler import ACM_Data_Handler
    from bin.gui_elements import loading_animation
    from bin.logic_gfx_file_editor import GfxFileEditor
    from bin.logic_gfx_to_svg import AnchorDirection, render_svg_to_png
    from bin.gui_hmi_symbol_selector import HMISymbolSelector
    from bin.gui_autoscrollbar import AutoScrollbar
    from bin.logic_process_line_extraction import ProcessLinesExtractor
    from bin.logic_tools import quick_build_hmi_page
    from bin.gui_svg_editor import SVGEditor
    from bin.gui_library_anchor_editor import LibraryAnchorEditor
    from bin.logic_library_anchor_overrides import get_default_store as _get_anchor_override_store
    from bin.gui_base64_icons import build_hmi_anchor_canvas
except Exception as e:
    from logic_internal_database import Database
    from logic_acm_data_handler import ACM_Data_Handler
    from gui_elements import loading_animation
    from logic_gfx_file_editor import GfxFileEditor
    from logic_gfx_to_svg import AnchorDirection, render_svg_to_png
    from gui_hmi_symbol_selector import HMISymbolSelector
    from gui_autoscrollbar import AutoScrollbar
    from logic_process_line_extraction import ProcessLinesExtractor
    from logic_tools import quick_build_hmi_page
    from gui_svg_editor import SVGEditor
    from gui_library_anchor_editor import LibraryAnchorEditor
    from logic_library_anchor_overrides import get_default_store as _get_anchor_override_store
    from gui_base64_icons import build_hmi_anchor_canvas


# Constants for anchor types
TOP_ANCHOR = 'top'
BOTTOM_ANCHOR = 'bottom'
LEFT_ANCHOR = 'left'
RIGHT_ANCHOR = 'right'

# Default colors
HIGHLIGHTING_COLOR = '#00AEEF'
DRAWING_DEFAULT_COLOR = '#6E6E6E'

MAX_IMAGE_PIXELS = 1500000000  # maximum pixels in the image, use it carefully

from enum import Enum

class AnchorType(str, Enum):
    """Enum defining different anchor types"""
    MATERIAL = "material"
    SIGNAL = "signal"
    MECHANICAL = "mechanical"
    POWER = "power"

class ProcessControlElement:
    """ Process control element with multiple configurable anchors """
    def __init__(self, x, y, width, height, default_image, name, font, 
                 top_anchors=None, bottom_anchors=None, left_anchors=None, right_anchors=None,
                 spa_name=None, spa_id=None, gfx_reference=None, image_tag=None, 
                 path=None, pno=None, roi_uid=None):
        self._x = x
        self._y = y
        self.width = width
        self.height = height
        self.default_image = default_image
        self.selection_rectangle_id = None
        self.reference_point_id = None
        self.image_id = None  # Canvas item ID for the image
        self.image_tag = image_tag
        self.text_id = None
        self.last_x = 0  # Last recorded x position
        self.last_y = 0  # Last recorded y position
        self.original_x = 0
        self.original_y = 0
        self.canvas: tk.Canvas = None
        self.selected = False # Name of the symbol in the library
        self.spa_name = spa_name  # Name of the SPA (if applicable)
        self.spa_id = spa_id  # ID of the SPA (if applicable)
        self.path = path  # Path to the SPA file (if applicable)
        self.pno = pno  # Page number in the SPA (if applicable)
        self.roi_uid = roi_uid  # Region of interest in the SPA (if applicable)
        self.gfx_reference = gfx_reference  # Reference to the GFX file editor (if applicable)
        self.name = name
        self.font = font
        
        # Initialize anchor collections
        self.top_anchors = top_anchors or []
        self.bottom_anchors = bottom_anchors or []
        self.left_anchors = left_anchors or []
        self.right_anchors = right_anchors or []
        
        # Dictionaries to store canvas IDs for each anchor
        self.top_anchor_ids = {}
        self.bottom_anchor_ids = {}
        self.left_anchor_ids = {}
        self.right_anchor_ids = {}
        
        # Dictionary to map anchor IDs to their types and positions
        self.anchor_info = {}

        self.create_anchor_ids(self.top_anchors, 'top_anchors')
        self.create_anchor_ids(self.bottom_anchors, 'bottom_anchors')
        self.create_anchor_ids(self.left_anchors, 'left_anchors')
        self.create_anchor_ids(self.right_anchors, 'right_anchors')


    def create_anchor_ids(self, anchors, prefix):
        """Create unique IDs for each anchor"""
        for i, anchor in enumerate(anchors):
            anchor_id = f'{self.spa_id}_{prefix}_{i}'
            anchor.append(anchor_id)


    def set_anchors(self, top_anchors=None, bottom_anchors=None, left_anchors=None, right_anchors=None, lines=None, scale=1.0):


        lines_to_change = []

        for line_id, (start_anchor, end_anchor), start_element, end_element in lines:
            # A None direction means the old anchor id no longer resolves (a 'border'
            # fallback, a free anchor, or a symbol that ships without anchors). The
            # line is still re-resolved below so it never keeps a dead anchor id.
            if start_element == self:
                anchor_pos = self.get_anchor_position(start_anchor)
                anchor_direction = anchor_pos[2] if anchor_pos else None
                lines_to_change.append((line_id,(start_anchor, end_anchor), start_element, end_element, 'start_anchor', anchor_direction))
            elif end_element == self:
                anchor_pos = self.get_anchor_position(end_anchor)
                anchor_direction = anchor_pos[2] if anchor_pos else None
                lines_to_change.append((line_id, (start_anchor, end_anchor), start_element, end_element, 'end_anchor', anchor_direction))

        # Delete all custom anchors
        for anchor_id in self.top_anchor_ids:
            self.canvas.delete(anchor_id)
        
        for anchor_id in self.bottom_anchor_ids:
            self.canvas.delete(anchor_id)
        
        for anchor_id in self.left_anchor_ids:
            self.canvas.delete(anchor_id)
        
        for anchor_id in self.right_anchor_ids:
            self.canvas.delete(anchor_id)


        """Set new anchors for the element"""
        self.top_anchors = top_anchors or []
        self.bottom_anchors = bottom_anchors or []
        self.left_anchors = left_anchors or []
        self.right_anchors = right_anchors or []

        self.anchor_info = {}

        # Dictionaries to store canvas IDs for each anchor
        self.top_anchor_ids = {}
        self.bottom_anchor_ids = {}
        self.left_anchor_ids = {}
        self.right_anchor_ids = {}

        # Recreate anchor IDs
        self.create_anchor_ids(self.top_anchors, 'top_anchors')
        self.create_anchor_ids(self.bottom_anchors, 'bottom_anchors')
        self.create_anchor_ids(self.left_anchors, 'left_anchors')
        self.create_anchor_ids(self.right_anchors, 'right_anchors')

        # Create custom anchors for each side
        self.create_top_anchors(scale)
        self.create_bottom_anchors(scale)
        self.create_left_anchors(scale)
        self.create_right_anchors(scale)

        new_lines = []

        for line_id, (start_anchor, end_anchor), start_element, end_element, anchor_type, anchor_direction in lines_to_change:
            if anchor_type == 'start_anchor':
                start_anchor = self.resolve_anchor_for_direction(anchor_direction)
            elif anchor_type == 'end_anchor':
                end_anchor = self.resolve_anchor_for_direction(anchor_direction)

            new_lines.append((line_id, (start_anchor, end_anchor), start_element, end_element))

        return new_lines

    def update_width_height(self, width, height, scale):
        """ Update the width and height of the element """
        self.width = width
        self.height = height
        
        if self.selection_rectangle_id:
            self.canvas.coords(
                self.selection_rectangle_id,
                self.x, self.y,
                self.x + int(self.width * scale),
                self.y + int(self.height * scale)
            )
        
        if self.image_id:
            self.canvas.coords(
                self.image_id,
                self.x + self.width / 2 * scale,
                self.y + self.height / 2 * scale
            )
        
        if self.text_id:
            self.canvas.coords(
                self.text_id,
                self.x + self.width / 2 * scale,
                self.y + (self.height + 15) * scale
            )

    
    def hide_text(self):
        """ Hide the text label of the element """
        if self.text_id:
            self.canvas.itemconfigure(self.text_id, state='hidden')


    def show_text(self):
        """ Show the text label of the element """
        if self.text_id:
            self.canvas.itemconfigure(self.text_id, state='normal')


    def draw(self, canvas, scale):
        """ Draw the element and its anchors on the canvas """
        self.canvas = canvas
        
        # Draw the base element
        self.reference_point_id = canvas.create_oval(
            self._x, self._y, self._x + 1, self._y + 1, 
            fill='', outline='', tags=('not_grid',)
        )

        self.original_x = self._x
        self.original_y = self._y

        padding = 5
        self.selection_rectangle_id = canvas.create_rectangle(
            self.x - padding, self.y - padding,
            self.x + int((self.width + padding) * scale) ,
            self.y + int((self.height + padding) * scale),
            outline='', fill='',width=2,
            tags=('element_selection', 'not_grid')
        )

        if self.image_tag:
            image_tags = ('element', 'not_grid', self.image_tag)
        else:
            image_tags = ('element', 'not_grid')
        
        # Float math (no int truncation) keeps the image aligned with the
        # anchor ovals - truncation errors get multiplied by canvas.scale on zoom.
        self.image_id = canvas.create_image(
            self.x + self.width / 2 * scale,
            self.y + self.height / 2 * scale,
            image=self.default_image, 
            anchor='center', 
            tags=image_tags
        )

        
        
        # Create text label
        self.text_id = canvas.create_text(
            self.x + self.width / 2 * scale,
            self.y + (self.height + 15) * scale,
            text=self.name, 
            tags=('element_text', 'not_grid', 'object_name'), 
            anchor='center',
            font=self.font, 
            fill='#6E6E6E'
        )
        
        # Create custom anchors for each side
        self.create_top_anchors(scale)
        self.create_bottom_anchors(scale)
        self.create_left_anchors(scale)
        self.create_right_anchors(scale)


    def create_anchor_oval(self, scale, rel_x, rel_y, anchor_type, anchor_id):
        # Calculate absolute position
        abs_x = self.x + rel_x * scale
        abs_y = self.y + rel_y * scale
            
            # Create the anchor
        self.canvas.create_oval(
                abs_x - int(5*scale), abs_y - int(5*scale),
                abs_x + int(5*scale), abs_y + int(5*scale),
                fill='', outline='', 
                tags=(f'anchor_{str(anchor_type.value)}', 'anchor', 'not_grid', anchor_id)
            )
        
        return abs_x,abs_y

    def create_top_anchors(self, scale):
        """Create anchors along the top edge of the element"""
        for anchor_info in self.top_anchors:
            rel_x, rel_y, anchor_type, index, anchor_id = anchor_info


            
            abs_x, abs_y = self.create_anchor_oval(scale, rel_x, rel_y, anchor_type, anchor_id)

            # Store the anchor ID
            self.top_anchor_ids[anchor_id] = (rel_x, rel_y, anchor_type)
            
            # Add to anchor info dictionary
            self.anchor_info[anchor_id] = {
                'position': (abs_x, abs_y),
                'type': anchor_type,
                'direction': AnchorDirection.TOP,
                'index': index
            }


    def create_bottom_anchors(self, scale):
        """Create anchors along the bottom edge of the element"""
        for anchor_info in self.bottom_anchors:
            rel_x, rel_y, anchor_type, index, anchor_id = anchor_info
            
            
            abs_x, abs_y = self.create_anchor_oval(scale, rel_x, rel_y, anchor_type, anchor_id)
            
            # Store the anchor ID
            self.bottom_anchor_ids[anchor_id] = (rel_x, rel_y, anchor_type)
            
            # Add to anchor info dictionary
            self.anchor_info[anchor_id] = {
                'position': (abs_x, abs_y),
                'type': anchor_type,
                'direction': AnchorDirection.BOTTOM,
                'index': index
            }

    def create_left_anchors(self, scale):
        """Create anchors along the left edge of the element"""
        for anchor_info in self.left_anchors:
            rel_x, rel_y, anchor_type, index, anchor_id = anchor_info
            
            
            abs_x, abs_y = self.create_anchor_oval(scale, rel_x, rel_y, anchor_type, anchor_id)
            
            # Store the anchor ID
            self.left_anchor_ids[anchor_id] = (rel_x, rel_y, anchor_type)
            
            # Add to anchor info dictionary
            self.anchor_info[anchor_id] = {
                'position': (abs_x, abs_y),
                'type': anchor_type,
                'direction': AnchorDirection.LEFT,
                'index': index
            }

    def create_right_anchors(self, scale):
        """Create anchors along the right edge of the element"""
        for anchor_info in self.right_anchors:
            rel_x, rel_y, anchor_type, index, anchor_id = anchor_info

            
            abs_x, abs_y = self.create_anchor_oval(scale, rel_x, rel_y, anchor_type, anchor_id)
           
            # Store the anchor ID
            self.right_anchor_ids[anchor_id] = (rel_x, rel_y, anchor_type)
            
            # Add to anchor info dictionary
            self.anchor_info[anchor_id] = {

                'position': (abs_x, abs_y),
                'type': anchor_type,
                'direction': AnchorDirection.RIGHT,
                'index': index
            }

    def move(self, dx, dy):
        """Move the element and all its anchors"""
        # Move the base element
        self.canvas.move(self.reference_point_id, dx, dy)
        self.canvas.move(self.image_id, dx, dy)
        self.canvas.move(self.text_id, dx, dy)
        
        # Move all custom anchors
        for anchor_id in self.top_anchor_ids:
            self.canvas.move(anchor_id, dx, dy)
        
        for anchor_id in self.bottom_anchor_ids:
            self.canvas.move(anchor_id, dx, dy)
        
        for anchor_id in self.left_anchor_ids:
            self.canvas.move(anchor_id, dx, dy)
        
        for anchor_id in self.right_anchor_ids:
            self.canvas.move(anchor_id, dx, dy)
        
        # Update anchor info positions
        for anchor_id, info in self.anchor_info.items():
            pos_x, pos_y = info['position']
            info['position'] = (pos_x + dx, pos_y + dy)

        if self.selection_rectangle_id:
            self.canvas.move(self.selection_rectangle_id, dx, dy)

    def move_to(self, x, y):
        """Move the element to a specific position"""
        dx = x - self.x
        dy = y - self.y
        self.move(dx, dy)


        
    @property
    def x(self):
        return self.canvas.coords(self.reference_point_id)[0]
    
    @property
    def y(self):
        return self.canvas.coords(self.reference_point_id)[1]
    
    @property
    def id(self):
        return self.image_id


    def delete(self):
        """Delete the element and all its anchors from the canvas"""
        if self.canvas:
            self.canvas.delete(self.image_id)
            self.canvas.delete(self.text_id)
            self.canvas.delete(self.reference_point_id)
            self.canvas.delete(self.selection_rectangle_id)
            
            # Delete all custom anchors
            for anchor_id in self.top_anchor_ids:
                self.canvas.delete(anchor_id)
            
            for anchor_id in self.bottom_anchor_ids:
                self.canvas.delete(anchor_id)
            
            for anchor_id in self.left_anchor_ids:
                self.canvas.delete(anchor_id)
            
            for anchor_id in self.right_anchor_ids:
                self.canvas.delete(anchor_id)

    def get_anchor_position_by_connection(self, connection):
        """Return the position of the anchor based on a connection"""
        if not connection or len(connection) < 7:
            return None
        direction = connection[6]

        return self.get_anchor_position_by_direction(direction)
    


    def get_anchor_position_by_direction(self, direction):

        if direction == AnchorDirection.TOP and self.top_anchor_ids:
            return list(self.top_anchor_ids.keys())[0]
        elif direction == AnchorDirection.BOTTOM and self.bottom_anchor_ids:
            return list(self.bottom_anchor_ids.keys())[0]
        elif direction == AnchorDirection.LEFT and self.left_anchor_ids:
            return list(self.left_anchor_ids.keys())[0]
        elif direction == AnchorDirection.RIGHT and self.right_anchor_ids:
            return list(self.right_anchor_ids.keys())[0]

        # If the specified direction is not found, return the first anchor of the alternative direction
        if direction == AnchorDirection.TOP and self.left_anchor_ids:
            return list(self.left_anchor_ids.keys())[0]
        elif direction == AnchorDirection.BOTTOM and self.right_anchor_ids:
            return list(self.right_anchor_ids.keys())[0]
        elif direction == AnchorDirection.LEFT and self.top_anchor_ids:
            return list(self.top_anchor_ids.keys())[0]
        elif direction == AnchorDirection.RIGHT and self.bottom_anchor_ids:
            return list(self.bottom_anchor_ids.keys())[0]
        else:
            return 'border'

    def resolve_anchor_for_direction(self, direction):
        """Pick an anchor id for a direction value, or any anchor when the direction is unknown"""
        if direction is not None:
            return self.get_anchor_position_by_direction(AnchorDirection(direction))

        for anchor_ids in (self.top_anchor_ids, self.bottom_anchor_ids,
                           self.left_anchor_ids, self.right_anchor_ids):
            if anchor_ids:
                return list(anchor_ids.keys())[0]

        return 'border'

    def get_anchor_position(self, anchor):
        """Return the position of the specified anchor"""
        
        # Check if this is one of our custom anchors
        if anchor in self.anchor_info:
            info = self.anchor_info[anchor]
            coords = self.canvas.coords(anchor)
            direction = info['direction']
            
            # Return the anchor position and its type
            return (coords[0] + coords[2]) / 2, (coords[1] + coords[3]) / 2, direction.value
        
        # Not found
        return None
    
    def show_anchors(self, show=True):
        """Show or hide all anchors of the element"""
        if show:
            for anc_id in self.top_anchor_ids.keys():
                self.canvas.itemconfig(anc_id, fill=DRAWING_DEFAULT_COLOR)
            for anc_id in self.bottom_anchor_ids.keys():
                self.canvas.itemconfig(anc_id, fill=DRAWING_DEFAULT_COLOR)
            for anc_id in self.left_anchor_ids.keys():
                self.canvas.itemconfig(anc_id, fill=DRAWING_DEFAULT_COLOR)
            for anc_id in self.right_anchor_ids.keys():
                self.canvas.itemconfig(anc_id, fill=DRAWING_DEFAULT_COLOR)
        else:
            for anc_id in self.get_all_anchors():
                self.canvas.itemconfig(anc_id, fill='')

    def on_hover(self, part, is_enter, anchor_id=None):
        """Handle hover events for different parts of the element"""
        
        # If we're hovering over the element itself, highlight all anchors

        
        if part == 'image':
            fill = DRAWING_DEFAULT_COLOR if is_enter else ""
            self.update_anchor_highlight(fill)

            # Change the selection rectangle width based on hover state
            if self.selection_rectangle_id:
                if is_enter:
                    self.canvas.itemconfig(self.selection_rectangle_id, width=2)
                else:
                    self.canvas.itemconfig(self.selection_rectangle_id, width=1)
        
        # Otherwise, check if we're hovering over a specific custom anchor
        elif part in [anchor_type.value for anchor_type in AnchorDirection] and anchor_id in self.anchor_info.keys():
            # Highlight the specific anchor

            # Check if the anchor is highlighted. If so, do not change the color
            highlighted_anchor = self.canvas.master.highlighted_anchor
            highlighted_anchor_id = highlighted_anchor[0] if highlighted_anchor else None
            if anchor_id == highlighted_anchor_id:
                return
            
            self.canvas.itemconfig(anchor_id, fill=HIGHLIGHTING_COLOR if is_enter else "")

    def update_anchor_highlight(self, fill):

        highlighted_anchor = self.canvas.master.highlighted_anchor
        highlighted_anchor_id = highlighted_anchor[0] if highlighted_anchor else None
        
        for anc_id in self.top_anchor_ids.keys():
            if anc_id != highlighted_anchor_id: self.canvas.itemconfig(anc_id, fill=fill)
            
        for anc_id in self.bottom_anchor_ids.keys():
            if anc_id != highlighted_anchor_id: self.canvas.itemconfig(anc_id, fill=fill)
            
        for anc_id in self.left_anchor_ids.keys():
            if anc_id != highlighted_anchor_id: self.canvas.itemconfig(anc_id, fill=fill)
            
        for anc_id in self.right_anchor_ids.keys():
            if anc_id != highlighted_anchor_id: self.canvas.itemconfig(anc_id, fill=fill)

    def get_all_anchors(self):
        """Return a list of all anchor IDs"""
        return ( 
            list(self.top_anchor_ids.keys()) + 
            list(self.bottom_anchor_ids.keys()) + 
            list(self.left_anchor_ids.keys()) + 
            list(self.right_anchor_ids.keys())
        )

    def set_image(self, default_image, redraw=False):
        """Update the element's images and repositions anchors"""
        # Update the base images
        self.default_image = default_image

        if not self.canvas:
            return
        
        # If we're resizing with an SVG string, regenerate the image
        if hasattr(self, 'resizing') and self.resizing and self.svg_string:
            # Skip during active resize - will be handled in redraw_with_new_dimensions
            return
        
        scale = self.canvas.master.imscale if hasattr(self.canvas.master, 'imscale') else 1.0
        
        if redraw:
            self._x, self._y, _, _ = self.canvas.coords(self.reference_point_id)
            self.delete()  # Remove old image and anchors
            self.draw(self.canvas, scale)  # Redraw with new image
        
        # Get base position
        x, y, _, _ = self.canvas.coords(self.reference_point_id)

        self.canvas.itemconfigure(self.image_id, image=self.default_image)

        self.canvas.coords(self.image_id, x + self.width / 2 * scale, y + self.height / 2 * scale)
        
        # Update all custom anchors
        self.update_anchors_position(x, y, scale)

    def update_anchor_oval(self, scale, x, y, rel_x, rel_y, anchor_id):
        # Must match create_anchor_oval exactly (no int truncation), otherwise
        # anchors shift away from their connected lines on every zoom step.
        abs_x = x + rel_x * scale
        abs_y = y + rel_y * scale
            
            # Create the anchor
        anchor_id = self.canvas.coords(
                anchor_id,
                abs_x - int(5*scale), abs_y - int(5*scale),
                abs_x + int(5*scale), abs_y + int(5*scale),
            )
        
        return abs_x, abs_y

    def update_anchors_position(self, x, y, scale):
        """Update positions of all custom anchors"""
        # Update top anchors
        for anchor_id, (rel_x, rel_y, _) in self.top_anchor_ids.items():
            abs_x, abs_y = self.update_anchor_oval(scale, x , y, rel_x, rel_y, anchor_id)
            self.anchor_info[anchor_id]['position'] = (abs_x, abs_y)
        
        # Update bottom anchors
        for anchor_id, (rel_x, rel_y, _) in self.bottom_anchor_ids.items():
            abs_x, abs_y = self.update_anchor_oval(scale, x , y, rel_x, rel_y, anchor_id)
            self.anchor_info[anchor_id]['position'] = (abs_x, abs_y)
        
        # Update left anchors
        for anchor_id, (rel_x, rel_y, _) in self.left_anchor_ids.items():
            abs_x, abs_y = self.update_anchor_oval(scale, x , y, rel_x, rel_y, anchor_id)
            self.anchor_info[anchor_id]['position'] = (abs_x, abs_y)
        
        # Update right anchors
        for anchor_id, (rel_x, rel_y, _) in self.right_anchor_ids.items():
            abs_x, abs_y = self.update_anchor_oval(scale, x , y, rel_x, rel_y, anchor_id)
            self.anchor_info[anchor_id]['position'] = (abs_x, abs_y)

    def select_element(self, selected):
        self.canvas.itemconfig(self.selection_rectangle_id, outline=HIGHLIGHTING_COLOR if selected else '', width=2 if selected else 1)
        self.selected = selected

        if (not selected and self.canvas.master.highlighted_anchor != None 
            and self.canvas.master.highlighted_anchor[0] in self.get_all_anchors()):
            # If the highlighted anchor is part of this element, select it
            self.select_anchor(self.canvas.master.highlighted_anchor[0], False)


    def select_anchor(self, anchor_id, selected):
        """Select or deselect a specific anchor"""
        if anchor_id in self.anchor_info:
            fill_color = HIGHLIGHTING_COLOR if selected else ''
            self.canvas.itemconfig(anchor_id, fill=fill_color)

            anchor_direction = self.anchor_info[anchor_id]['direction']

            self.canvas.master.highlighted_anchor = (anchor_id, self, anchor_direction)
            if (not selected and self.canvas.master.highlighted_anchor and 
                self.canvas.master.highlighted_anchor[0] == anchor_id):
                self.canvas.master.highlighted_anchor = None
        else:
            logging.warning(f"Anchor {anchor_id} not found in element {self.name}")


        


def restyle_svg_string(svg_string, stroke_color, fill_color, stroke_width):
    """Return the SVG restyled with the given stroke/fill colours and stroke width, or None if nothing changed"""
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    root = ET.fromstring(svg_string)
    changed = False
    for elem in root.iter():
        if elem is root:
            continue
        if elem.get('stroke', 'none') != 'none':
            elem.set('stroke', stroke_color)
            changed = True
        if elem.get('stroke-width', 'none') != 'none':
            elem.set('stroke-width', stroke_width)
            changed = True
        if elem.get('fill', 'none') != 'none':
            elem.set('fill', fill_color)
            changed = True

    return ET.tostring(root, encoding='unicode') if changed else None


class ProcessControlStaticGraphicElement(ProcessControlElement):
    """Process control element with multiple configurable anchors that can be resized"""
    def __init__(self, x, y, width, height, name, font, internal_db, 
                 top_anchors=None, bottom_anchors=None, left_anchors=None, right_anchors=None,
                 min_width=50, min_height=50, svg_string=None, spa_name=None, spa_id=None, gfx_reference=None,
                 path=None, pno=None, roi_uid=None, filename_suffix=None):

        self.__internal_db: Database = internal_db
        self.svg_string = svg_string
        if filename_suffix:
            self.filename_suffix = filename_suffix
        else:
            self.generate_new_filename_suffix()

        # Parse the SVG string
        try:
            # Add namespace to prevent ElementTree from adding ns0 prefixes
            ET.register_namespace('', 'http://www.w3.org/2000/svg')
            self.svg_string_root = ET.fromstring(self.svg_string)
            # Get original dimensions
            root_width = float(self.svg_string_root.get('width', '100').replace('px', ''))
            root_height = float(self.svg_string_root.get('height', '100').replace('px', ''))

            self.width_hmi_to_svg = width / root_width
            self.height_hmi_to_svg = height / root_height

            # run thorugh the elements to get the first stroke width that is not 'none'
            self.__read_svg_stroke_width()
            

            self.has_viewbox = False

            viewbox_attr = self.svg_string_root.get('viewBox', None)
            self.viewbox = {"min_x": 0, "min_y": 0, "width": 0, "height": 0}
            
            if viewbox_attr:
                try:
                    viewbox_values = list(map(float, re.findall(r'[-+]?(?:\d*\.\d+|\d+)', viewbox_attr)))
                    if len(viewbox_values) == 4:
                        self.viewbox["min_x"] = viewbox_values[0]
                        self.viewbox["min_y"] = viewbox_values[1]
                        self.viewbox["width"] = viewbox_values[2]
                        self.viewbox["height"] = viewbox_values[3]
                        self.has_viewbox = True
                except Exception as e:
                    logging.error(f"Error parsing viewBox: {e}")
            
            # Get SVG dimensions
            try:
                width_attr = self.svg_string_root.get('width', '100%')
                height_attr = self.svg_string_root.get('height', '100%')
                
                # Convert to numbers if possible (ignore percentage values)
                if width_attr.endswith('px'):
                    width_attr = width_attr[:-2]
                if height_attr.endswith('px'):
                    height_attr = height_attr[:-2]
                    
                if not width_attr.endswith('%') and not height_attr.endswith('%'):
                    self.svg_width = float(width_attr)
                    self.svg_height = float(height_attr)
                elif self.has_viewbox:
                    # If dimensions are percentages but we have a viewBox, use viewBox dimensions
                    self.svg_width = self.viewbox["width"]
                    self.svg_height = self.viewbox["height"]
            except Exception as e:
                logging.error(f"Error parsing SVG dimensions: {e}")
                # Use viewBox dimensions as fallback if available
                if self.has_viewbox:
                    self.svg_width = self.viewbox["width"]
                    self.svg_height = self.viewbox["height"]
                

            # shift the anchor positions to the new dimensions using the viewBox[0] and viewBox[1]
            top_anchors = [[(x - self.viewbox["min_x"]) * (self.svg_width / self.viewbox["width"]) * self.width_hmi_to_svg
                            , (y - self.viewbox["min_y"]) * (self.svg_height / self.viewbox["height"]) * self.height_hmi_to_svg, anc_type, index] for (x, y, anc_type, index) in top_anchors]
            bottom_anchors = [[(x - self.viewbox["min_x"]) * (self.svg_width / self.viewbox["width"]) * self.width_hmi_to_svg
                              , (y - self.viewbox["min_y"]) * (self.svg_height / self.viewbox["height"]) * self.height_hmi_to_svg, anc_type, index] for (x, y, anc_type, index) in bottom_anchors]
            left_anchors = [[(x - self.viewbox["min_x"]) * (self.svg_width / self.viewbox["width"]) * self.width_hmi_to_svg
                             , (y - self.viewbox["min_y"]) * (self.svg_height / self.viewbox["height"]) * self.height_hmi_to_svg, anc_type, index] for (x, y, anc_type, index) in left_anchors]
            right_anchors = [[(x - self.viewbox["min_x"]) * (self.svg_width / self.viewbox["width"]) * self.width_hmi_to_svg
                              , (y - self.viewbox["min_y"]) * (self.svg_height / self.viewbox["height"]) * self.height_hmi_to_svg, anc_type, index] for (x, y, anc_type, index) in right_anchors]

        except Exception as e:
            logging.error(f"Error parsing SVG: {e} using default dimensions")
            
        super().__init__(x, y, width, height, None, name, font,
                         top_anchors, bottom_anchors, left_anchors, right_anchors,
                         spa_name, spa_id, gfx_reference, path=path, pno=pno, roi_uid=roi_uid)
        
        # Resizing properties
        self.update_image_schedule_id = None
        self.min_width = min_width
        self.min_height = min_height
        self.resize_handles = {}
        self.resizing = False
        self.resize_direction = None
        self.resize_start_x = 0
        self.resize_start_y = 0
        self.original_width = width
        self.original_height = height
        self.current_width = width
        self.current_height = height
        self.aspect_ratio = width / height  # For maintaining aspect ratio if needed
        self.unscaled_top_anchors = top_anchors or []
        self.unscaled_bottom_anchors = bottom_anchors or []
        self.unscaled_left_anchors = left_anchors or []
        self.unscaled_right_anchors = right_anchors or []

        # Remember the width/height that the current filename_suffix corresponds to,
        # so we only mint a new suffix when the element is actually resized.
        self._suffix_width = width
        self._suffix_height = height


    def generate_new_filename_suffix(self):
        # Display-only 8-char suffix (not a lookup key); collisions are cosmetic.
        self.filename_suffix = str(uuid.uuid4())[:8]
        # Refresh the size the new suffix corresponds to. Guarded because this
        # method is also called from __init__ before super().__init__ has set
        # self.width/self.height (that path re-seeds _suffix_width/_suffix_height
        # explicitly at the end of __init__).
        if hasattr(self, 'width') and hasattr(self, 'height'):
            self._suffix_width = self.width
            self._suffix_height = self.height


    def regenerate_filename_suffix_if_size_changed(self):
        """Mint a new filename_suffix only if the element's size differs from
        the size the current suffix was minted for. Prevents export from
        churning suffixes on no-op resizes / SVG-only edits."""
        if (getattr(self, '_suffix_width', None) != self.width
                or getattr(self, '_suffix_height', None) != self.height):
            self.generate_new_filename_suffix()
        
        
    def draw(self, canvas, scale):
        """Draw the element, its anchors, and resize handles on the canvas"""

        self.canvas = canvas

        if self.svg_string:
            # Get width and height from the SVG string
            self.pil_default_image = self.__create_resized_svg_image(self.svg_string, DRAWING_DEFAULT_COLOR)
            self.default_image = ImageTk.PhotoImage(self.pil_default_image)

        super().draw(canvas, scale)
        
        # Create resize handles after drawing the base element
        self.create_resize_handles(scale)

    def set_svg_string(self, svg_string):
        self.svg_string = svg_string
        self.svg_string_root = ET.fromstring(self.svg_string)
        # resize_svg re-applies svg_stroke_width to every element, so it has to
        # track the edited SVG or stroke width changes are rendered with the old value.
        self.__read_svg_stroke_width()
        # NOTE: intentionally do NOT regenerate filename_suffix here. Suffix
        # regeneration is now gated on actual size changes (see
        # regenerate_filename_suffix_if_size_changed); a pure SVG-content edit
        # keeps the same suffix so exports overwrite the previous file instead
        # of accumulating orphans.


    def __read_svg_stroke_width(self):
        """Take the first usable stroke width found in the SVG as the element stroke width"""
        self.svg_stroke_width = getattr(self, 'svg_stroke_width', 1.0)
        for elem in self.svg_string_root.iter():
            stroke_width = elem.get('stroke-width', 'none')
            if stroke_width != 'none':
                try:
                    self.svg_stroke_width = float(stroke_width.replace('px', ''))
                except ValueError:
                    continue
                return


    def restyle(self, stroke_color, fill_color, stroke_width):
        """Apply a stroke colour, fill colour and stroke width to the whole graphic"""
        restyled = restyle_svg_string(self.svg_string, stroke_color, fill_color, stroke_width)
        if restyled is None:
            return False

        self.set_svg_string(restyled)
        self.update_image()
        return True


    def export_svg_string(self, export_path):

        tree = ET.ElementTree(self.svg_string_root)
        tree.write(export_path, encoding='utf-8', xml_declaration=True)
        
    
    def create_resize_handles(self, scale):
        """Create handles for resizing the element"""
        handle_size = 6 * scale
        
        # Define positions for resize handles (corners and middle of each side)
        handle_positions = {
            'top_left': (self.x, self.y, 'nw'),
            'top_right': (self.x + self.width * scale, self.y, 'ne'),
            'bottom_right': (self.x + self.width * scale, self.y + self.height * scale, 'se'),
            'bottom_left': (self.x, self.y + self.height * scale, 'sw')
        }
        
        # Create a handle for each position
        for position_name, (x, y, direction) in handle_positions.items():
            handle_id = self.canvas.create_rectangle(
                x - handle_size, y - handle_size,
                x + handle_size, y + handle_size,
                fill='', outline='',
                tags=(f'resize_handle_{position_name}', 'resize_handle', 'not_grid')
            )
            
            self.resize_handles[position_name] = {
                'id': handle_id,
                'direction': direction
            }
            
            # Bind events to handle
            self.canvas.tag_bind(handle_id, '<Enter>', 
                lambda e, h=handle_id: self.highlight_resize_handle(True, h))
            self.canvas.tag_bind(handle_id, '<Leave>', 
                lambda e, h=handle_id: self.highlight_resize_handle(False, h))
            self.canvas.tag_bind(handle_id, '<ButtonPress-1>', 
                lambda e, pos=position_name: self.start_resize(e, pos))
            self.canvas.tag_bind(handle_id, '<B1-Motion>', self.resize)
            self.canvas.tag_bind(handle_id, '<ButtonRelease-1>', self.end_resize)

    
    def highlight_resize_handle(self, highlight, handle_id):
        """Highlight or unhighlight the resize handle"""
        
        if highlight and self.selected:
            self.canvas.itemconfig(handle_id, fill=HIGHLIGHTING_COLOR, outline=HIGHLIGHTING_COLOR)
        else:
            outline_color = HIGHLIGHTING_COLOR if self.selected else ''
            fill_color = 'white' if self.selected else ''
            self.canvas.itemconfig(handle_id, fill=fill_color, outline=outline_color)

    
    def start_resize(self, event, position):
        """Start the resizing operation"""
        if not self.selected:
            return
        self.resizing = True
        self.resize_direction = self.resize_handles[position]['direction']
        self.resize_start_x = self.canvas.canvasx(event.x)
        self.resize_start_y = self.canvas.canvasy(event.y)
        scale = self.canvas.master.imscale if hasattr(self.canvas.master, 'imscale') else 1.0
        self.current_width = self.width
        self.current_height = self.height
        self.aspect_ratio = self.width / self.height if self.height > 0 else 1.0
        
        # Store original position
        self.resize_original_x = self.x
        self.resize_original_y = self.y
        self.resize_original_width = self.width
        self.resize_original_height = self.height

        self.resize_original_x_right_edge = self.x + self.width
        self.resize_original_y_bottom_edge = self.y + self.height
    
    def resize(self, event):
        """Update the element size during resize"""
        if not self.resizing:
            return
        
        scale = self.canvas.master.imscale if hasattr(self.canvas.master, 'imscale') else 1.0
        
        # Get current mouse position
        current_x = self.canvas.canvasx(event.x)
        current_y = self.canvas.canvasy(event.y)
        
        # Calculate movement
        dx = (current_x - self.resize_start_x) / scale
        dy = (current_y - self.resize_start_y) / scale
        
        # Calculate new width and height based on the resize direction
        new_width = self.width 
        new_height = self.height
        new_x = self.x
        new_y = self.y

        # Handle corner resizing
        if self.resize_direction == 'nw':  # Top-left
            # For height, only change if dy is valid
            if self.current_height - dy >= self.min_height * scale:
                new_height = self.current_height - dy
                new_y = self.resize_original_y + dy * scale
                if new_height != self.current_height:
                    dx_aspect_ratio = dy * self.aspect_ratio
                    new_width = max(self.min_width * scale, (self.current_width + dx_aspect_ratio)/ scale)
                    new_x = self.resize_original_x + dx_aspect_ratio * scale
            
        elif self.resize_direction == 'ne':  # Top-right
            # For width, simple addition (bounded by min)
            new_width = max(self.min_width * scale, self.current_width + dx)
            
            # For height, only change if dy is valid
            if self.current_height - dy >= self.min_height * scale:
                new_height = self.current_height - dy
                new_y = (self.resize_original_y + dy) * scale
            
        elif self.resize_direction == 'se':  # Bottom-right
            new_width = max(self.min_width * scale, self.current_width + dx)
            new_height = max(self.min_height * scale, self.current_height + dy)
            
        elif self.resize_direction == 'sw':  # Bottom-left
            # For height, simple addition (bounded by min)
            new_height = max(self.min_height * scale, self.current_height + dy)

            if new_height != self.current_height:
                    dx_aspect_ratio = dy * self.aspect_ratio
                    new_width = max(self.min_width * scale, self.current_width + dx_aspect_ratio)
                    new_x = (self.resize_original_x - dx_aspect_ratio * scale ) 
        
        # Apply the changes
        self.resize_to(new_x, new_y, new_width, new_height)

        # Update any connected lines
        if hasattr(self.canvas.master, 'update_lines'):
            self.canvas.master.update_lines(self)
        
    
    def resize_to(self, new_x, new_y, new_width, new_height):
        """Apply resize changes to the element"""
        # Calculate the amount to move and resize
        dx = new_x - self.x
        dy = new_y - self.y
        
        # Move element if needed
        if (dx != 0 or dy != 0):
            #print(f"Moving element by ({dx}, {dy}) to new position ({new_x}, {new_y})")

            self.move(dx, dy)
        
        # Update dimensions with a fixed aspect ratio
        new_width = max(self.min_width,new_width)
        new_height = max(self.min_height, new_height)
        new_width = new_height * self.aspect_ratio

        self.width = new_width
        self.height = new_height
        
        # Redraw the element with new dimensions
        self.redraw_with_new_dimensions()
    
    
    def redraw_with_new_dimensions(self):
        """Redraw the element with new dimensions"""
        scale = self.canvas.master.imscale if hasattr(self.canvas.master, 'imscale') else 1.0

        # If we have an SVG string, regenerate the image at the new dimensions
        self.raster_update_image()
        
        # Update the image position and size
        self.canvas.coords(self.image_id, 
                          self.x + self.width / 2 * scale,
                          self.y + self.height / 2 * scale)
        

        # Update the selection rectangle
        self.canvas.coords(self.selection_rectangle_id,
                            self.x, self.y,
                            self.x + self.width * scale,
                            self.y + self.height * scale)
        

        # Update text position
        self.canvas.coords(self.text_id,
                          self.x + self.width / 2 * scale,
                          self.y + (self.height + 15) * scale)
        
        # Recalculate anchor positions based on the new dimensions
        self.recalculate_anchor_positions(scale)
        
        # Update resize handles
        self.update_resize_handles(scale)

    def zoom_update_image(self):
        
        if hasattr(self, 'pil_default_image'):
            # If we have PIL images, update them
            self.raster_update_image()

            coords = self.canvas.coords(self.reference_point_id)
            if coords is None or len(coords) < 4:
                return
            
            x, y, _, _ = self.canvas.coords(self.reference_point_id)

            scale = self.canvas.master.imscale if hasattr(self.canvas.master, 'imscale') else 1.0

            # Update all custom anchors
            self.update_anchors_position(x, y, scale)
            if self.update_image_schedule_id: self.canvas.after_cancel(self.update_image_schedule_id)
            self.update_image_schedule_id = self.canvas.after_idle(self.update_image)
        
        else:
            # If we have an SVG string, update the images
            self.update_image()
        

    def raster_update_image(self):

        scale = self.canvas.master.imscale if hasattr(self.canvas.master, 'imscale') else 1.0

        scale_x = self.width * scale / self.original_width
        scale_y = self.height * scale / self.original_height

        
        # Calculate new dimensions
        new_width = int(self.original_width * scale_x)
        new_height = int(self.original_height * scale_y)
        
        # Resize the images using LANCZOS resampling
        resized_default_image = self.pil_default_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Update the images
        self.default_image = ImageTk.PhotoImage(resized_default_image)
        
        self.canvas.itemconfigure(self.image_id, image=self.default_image)


    def set_filename_suffix(self, filename_suffix):
        self.filename_suffix = filename_suffix
        # Snapshot the current size as the size this externally-set suffix
        # corresponds to. Used by project deserialization (resize_to +
        # update_image + set_filename_suffix) so a load-then-export round-trip
        # keeps the persisted suffix instead of minting a new one.
        self._suffix_width = self.width
        self._suffix_height = self.height

    
    def update_image(self):
        if self.svg_string:
            # Create new images based on the resized dimensions
            self.pil_default_image = self.__create_resized_svg_image(self.svg_string, DRAWING_DEFAULT_COLOR)
          
            # Update the images
            self.default_image = ImageTk.PhotoImage(self.pil_default_image)
            
            # Update the canvas image
            self.canvas.itemconfigure(self.image_id, image=self.default_image)

    def get_anchor_position_by_connection(self, connection):
        """Get anchor position by its point of interest list index"""

        poi_index = connection[4]

        for anc in self.top_anchors:
            if anc[3] == poi_index:
                return anc[4]
        for anc in self.bottom_anchors:
            if anc[3] == poi_index:
                return anc[4]
        for anc in self.left_anchors:
            if anc[3] == poi_index:
                return anc[4]
        for anc in self.right_anchors:
            if anc[3] == poi_index:
                return anc[4]

    
    def recalculate_anchor_positions(self, scale):
        """Recalculate anchor positions based on new dimensions"""
        # Clear existing anchor collections
        for anchor_id in list(self.top_anchor_ids.keys()):
            self.canvas.delete(anchor_id)
        for anchor_id in list(self.bottom_anchor_ids.keys()):
            self.canvas.delete(anchor_id)
        for anchor_id in list(self.left_anchor_ids.keys()):
            self.canvas.delete(anchor_id)
        for anchor_id in list(self.right_anchor_ids.keys()):
            self.canvas.delete(anchor_id)
        
        # Clear dictionaries
        self.top_anchor_ids = {}
        self.bottom_anchor_ids = {}
        self.left_anchor_ids = {}
        self.right_anchor_ids = {}

        width_scale = self.width / self.original_width
        height_scale = self.height / self.original_height 
        
        # Scale anchor positions based on new dimensions
        scaled_top_anchors = []
        for rel_x, rel_y, anchor_type, anchor_id, index in self.unscaled_top_anchors:
            scaled_rel_x = rel_x * width_scale
            scaled_rel_y = rel_y * height_scale
            scaled_top_anchors.append((scaled_rel_x, scaled_rel_y, anchor_type, anchor_id, index))
        self.top_anchors = scaled_top_anchors
        
        scaled_bottom_anchors = []
        for rel_x, rel_y, anchor_type, anchor_id, index in self.unscaled_bottom_anchors:
            scaled_rel_x = rel_x * width_scale
            scaled_rel_y = rel_y * height_scale
            scaled_bottom_anchors.append((scaled_rel_x, scaled_rel_y, anchor_type, anchor_id, index))
        self.bottom_anchors = scaled_bottom_anchors
        
        scaled_left_anchors = []
        for rel_x, rel_y, anchor_type, anchor_id, index in self.unscaled_left_anchors:
            scaled_rel_x = rel_x * width_scale
            scaled_rel_y = rel_y * height_scale
            scaled_left_anchors.append((scaled_rel_x, scaled_rel_y, anchor_type, anchor_id, index))
        self.left_anchors = scaled_left_anchors
        
        scaled_right_anchors = []
        for rel_x, rel_y, anchor_type, anchor_id, index in self.unscaled_right_anchors:
            scaled_rel_x = rel_x * width_scale
            scaled_rel_y = rel_y * height_scale
            scaled_right_anchors.append((scaled_rel_x, scaled_rel_y, anchor_type, anchor_id, index))
        self.right_anchors = scaled_right_anchors
        
        # Recreate all anchors
        self.create_top_anchors(scale)
        self.create_bottom_anchors(scale)
        self.create_left_anchors(scale)
        self.create_right_anchors(scale)


    def reverse_anchor_scaling(self):
        """Reverse the anchor scaling to get back to original unscaled positions"""
        
        # Calculate reverse scale factors
        width_scale = self.width / self.original_width
        height_scale = self.height / self.original_height
        
        # Reverse scale top anchors
        unscaled_top_anchors = []
        for scaled_rel_x, scaled_rel_y, anchor_type, anchor_id, index in self.top_anchors:
            original_rel_x = scaled_rel_x / width_scale
            original_rel_y = scaled_rel_y / height_scale
            unscaled_top_anchors.append((original_rel_x, original_rel_y, anchor_type, anchor_id, index))
        self.unscaled_top_anchors = unscaled_top_anchors
        
        # Reverse scale bottom anchors
        unscaled_bottom_anchors = []
        for scaled_rel_x, scaled_rel_y, anchor_type, anchor_id, index in self.bottom_anchors:
            original_rel_x = scaled_rel_x / width_scale
            original_rel_y = scaled_rel_y / height_scale
            unscaled_bottom_anchors.append((original_rel_x, original_rel_y, anchor_type, anchor_id, index))
        self.unscaled_bottom_anchors = unscaled_bottom_anchors
        
        # Reverse scale left anchors
        unscaled_left_anchors = []
        for scaled_rel_x, scaled_rel_y, anchor_type, anchor_id, index in self.left_anchors:
            original_rel_x = scaled_rel_x / width_scale
            original_rel_y = scaled_rel_y / height_scale
            unscaled_left_anchors.append((original_rel_x, original_rel_y, anchor_type, anchor_id, index))
        self.unscaled_left_anchors = unscaled_left_anchors
        
        # Reverse scale right anchors
        unscaled_right_anchors = []
        for scaled_rel_x, scaled_rel_y, anchor_type, anchor_id, index in self.right_anchors:
            original_rel_x = scaled_rel_x / width_scale
            original_rel_y = scaled_rel_y / height_scale
            unscaled_right_anchors.append((original_rel_x, original_rel_y, anchor_type, anchor_id, index))
        self.unscaled_right_anchors = unscaled_right_anchors


    def reverse_anchor_transformation(self):
        """
        Reverse the anchor position transformation to get back original coordinates. Unscaled HMI anchors to SVG coordinates.

        Args:
            top_anchors, bottom_anchors, left_anchors, right_anchors: Lists of transformed anchor data
        
        Returns:
            Tuple of (original_top_anchors, original_bottom_anchors, original_left_anchors, original_right_anchors)
        """

        # Reverse the anchor scaling to get back to original unscaled positions
        self.reverse_anchor_scaling()


        # Reverse the transformation for top anchors
        top_anchors = [{'x': (x / (self.svg_width / self.viewbox["width"]) / self.width_hmi_to_svg) + self.viewbox["min_x"],
                         'y': (y / (self.svg_height / self.viewbox["height"]) / self.height_hmi_to_svg) + self.viewbox["min_y"],
                         'index': index, 'direction': 'top'} for (x, y, _, index) in self.unscaled_top_anchors]

        # Reverse the transformation for bottom anchors
        bottom_anchors = [{'x': (x / (self.svg_width / self.viewbox["width"]) / self.width_hmi_to_svg) + self.viewbox["min_x"],
                         'y': (y / (self.svg_height / self.viewbox["height"]) / self.height_hmi_to_svg) + self.viewbox["min_y"],
                         'index': index, 'direction': 'bottom'} for (x, y, _, index) in self.unscaled_bottom_anchors]
        
        # Reverse the transformation for left anchors
        left_anchors = [{'x': (x / (self.svg_width / self.viewbox["width"]) / self.width_hmi_to_svg) + self.viewbox["min_x"],
                         'y': (y / (self.svg_height / self.viewbox["height"]) / self.height_hmi_to_svg) + self.viewbox["min_y"],
                         'index': index, 'direction': 'left'} for (x, y, _, index) in self.unscaled_left_anchors]
        
        # Reverse the transformation for right anchors
        right_anchors = [{'x': (x / (self.svg_width / self.viewbox["width"]) / self.width_hmi_to_svg) + self.viewbox["min_x"],
                          'y': (y / (self.svg_height / self.viewbox["height"]) / self.height_hmi_to_svg) + self.viewbox["min_y"],
                          'index': index, 'direction': 'right'} for (x, y, _, index) in self.unscaled_right_anchors]
        
        return (top_anchors, bottom_anchors, left_anchors, right_anchors)
        

    def save_changes_to_static_graphic(self):

        
        top_anchors, bottom_anchors, left_anchors, right_anchors = self.reverse_anchor_transformation()

        self.__internal_db.save_static_graphic_anchors(
            self.spa_id, top_anchors, bottom_anchors, left_anchors, right_anchors)
        

    def change_anchor_direction(self, anchor_id, new_direction):
        """Change the direction of a specific anchor"""
        if anchor_id not in self.anchor_info:
            logging.warning(f"Anchor {anchor_id} not found in element {self.name}")
            return
        
        # Get current position and type
        current_direction = self.anchor_info[anchor_id]['direction']

        self.__change_scaled_anchors(anchor_id, new_direction, current_direction)
        self.__change_unscaled_anchors(anchor_id, new_direction, current_direction)

        return current_direction
    

    def __change_unscaled_anchors(self, anchor_id, new_direction, current_direction):
        """Change the direction of an anchor in the unscaled anchor lists"""
        
        # Get the anchor info
        index = self.anchor_info[anchor_id]['index']
        
        # Remove the anchor from its current collection
        if current_direction == AnchorDirection.TOP:
            rel_x, rel_y, anc_type, index, anc_id = self.__pop_unscaled_anchor(self.unscaled_top_anchors, index)
        elif current_direction == AnchorDirection.BOTTOM:
            rel_x, rel_y, anc_type, index, anc_id = self.__pop_unscaled_anchor(self.unscaled_bottom_anchors, index)
        elif current_direction == AnchorDirection.LEFT:
            rel_x, rel_y, anc_type, index, anc_id = self.__pop_unscaled_anchor(self.unscaled_left_anchors, index)
        elif current_direction == AnchorDirection.RIGHT:
            rel_x, rel_y, anc_type, index, anc_id = self.__pop_unscaled_anchor(self.unscaled_right_anchors, index)

        # Add the anchor to the new collection
        if new_direction == AnchorDirection.TOP:
            self.unscaled_top_anchors.append((rel_x, rel_y, anc_type, index, anc_id))
        elif new_direction == AnchorDirection.BOTTOM:
            self.unscaled_bottom_anchors.append((rel_x, rel_y, anc_type, index, anc_id))
        elif new_direction == AnchorDirection.LEFT:
            self.unscaled_left_anchors.append((rel_x, rel_y, anc_type, index, anc_id))
        elif new_direction == AnchorDirection.RIGHT:
            self.unscaled_right_anchors.append((rel_x, rel_y, anc_type, index, anc_id))


    def __pop_unscaled_anchor(self, anchors, index):
        """Remove an anchor from the specified collection"""
        for i, (rel_x, rel_y, anc_type, idx, anc_id) in enumerate(anchors):
            if idx == index:
                del anchors[i]
                return rel_x, rel_y, anc_type, idx, anc_id

    def __change_scaled_anchors(self, anchor_id, new_direction, current_direction):
        
        
        # Remove the anchor from its current collection
        if current_direction == AnchorDirection.TOP:
            x, y, anc_type  = self.top_anchor_ids.pop(anchor_id)
        elif current_direction == AnchorDirection.BOTTOM:
            x, y, anc_type  = self.bottom_anchor_ids.pop(anchor_id)
        elif current_direction == AnchorDirection.LEFT:
            x, y, anc_type  = self.left_anchor_ids.pop(anchor_id)
        elif current_direction == AnchorDirection.RIGHT:
            x, y, anc_type  = self.right_anchor_ids.pop(anchor_id)

        # Update the anchor info with the new direction
        self.anchor_info[anchor_id]['direction'] = new_direction
        
        # Add the anchor to the new collection
        if new_direction == AnchorDirection.TOP:
            self.top_anchor_ids[anchor_id] = (x, y, anc_type)
        elif new_direction == AnchorDirection.BOTTOM:
            self.bottom_anchor_ids[anchor_id] = (x, y, anc_type)
        elif new_direction == AnchorDirection.LEFT:
            self.left_anchor_ids[anchor_id] = (x, y, anc_type)
        elif new_direction == AnchorDirection.RIGHT:
            self.right_anchor_ids[anchor_id] = (x, y, anc_type)
        return current_direction
        


    def __create_resized_svg_image(self, svg_string, color):
        """Create a new image from SVG at the current element size"""
        # First, replace the color placeholder in the SVG
        svg_with_color = svg_string.format(hex_color=color)
        
        # Resize the SVG to match the element dimensions
        scale = self.canvas.master.imscale if hasattr(self.canvas.master, 'imscale') else 1.0
        resized_svg = self.resize_svg(
            svg_with_color, 
            scale=scale,
        )
        
        # Convert string to bytes
        byte_image = str.encode(resized_svg)
        
        # Render the SVG to PNG
        png_data = cairosvg.svg2png(byte_image)

        image = Image.open(BytesIO(png_data))
        
        # Create a PhotoImage from the PNG data
        return image
    
    
    def resize_svg(self, svg_string, scale, width=None, height=None, preserve_aspect_ratio=True):
        """
        Resize SVG while maintaining stroke width by using vector-effect="non-scaling-stroke".
        
        Args:
            svg_string: The original SVG content as a string
            width: Target width in pixels
            height: Target height in pixels
            preserve_aspect_ratio: Whether to maintain aspect ratio when only one dimension is specified
            
        Returns:
            Resized SVG as a string with non-scaling strokes
        """

        scale_x = self.width * scale / self.original_width
        scale_y = self.height * scale / self.original_height
        
        # Calculate new dimensions
        new_width = self.original_width * scale_x
        new_height = self.original_height * scale_y
        
        # Update root SVG element dimensions
        self.svg_string_root.set('width', str(new_width))
        self.svg_string_root.set('height', str(new_height))
      
        
        # Add a wrapper group that applies the scaling transform
        # This ensures all child elements are scaled but strokes don't scale
        wrapper = ET.Element('{http://www.w3.org/2000/svg}g')
        
        
        # Move all direct children to the wrapper group
        children = list(self.svg_string_root)
        for child in children:
            self.svg_string_root.remove(child)
            wrapper.append(child)
        
        # Add the wrapper to the root
        self.svg_string_root.append(wrapper)
        
        # Process all path, rect, circle, line elements to set vector-effect
        def process_element(element):
            tag = element.tag.split('}')[-1]  # Remove namespace if present
            if tag in ('path', 'rect', 'circle', 'line', 'ellipse', 'polyline', 'polygon'):
                #element.set('transform', f'scale({scale_x}, {scale_y})')
                # get the stroke width and set it to the new value
                element.set('stroke-width', str(self.svg_stroke_width / scale_x * scale))
                
            
            # Process children recursively
            for child in element:
                process_element(child)
        
        process_element(wrapper)
        
        # Convert back to string
        svg_string = ET.tostring(self.svg_string_root, encoding='utf-8').decode('utf-8')

        return svg_string
    
    
    def update_resize_handles(self, scale):
        """Update the position of resize handles"""
        handle_size = 6 * scale
        
        handle_positions = {
            'top_left': (self.x, self.y),
            'top_right': (self.x + self.width * scale, self.y),
            'bottom_right': (self.x + self.width * scale, self.y + self.height * scale),
            'bottom_left': (self.x, self.y + self.height * scale)
        }
        
        # Update handle positions
        for position_name, (x, y) in handle_positions.items():
            handle_id = self.resize_handles[position_name]['id']
            self.canvas.coords(
                handle_id,
                x - handle_size, y - handle_size,
                x + handle_size, y + handle_size
            )
    
    def end_resize(self, _):
        """Finalize the resize operation"""
        if not self.resizing:
            return
        
        self.resizing = False

         # Record resize action for undo
        if hasattr(self.canvas.master, 'undo_manager'):
            self.canvas.master.undo_manager.add_action('resize_element', {
                'element': self,
                'original_x': self.resize_original_x,
                'original_y': self.resize_original_y,
                'original_width': self.resize_original_width,
                'original_height': self.resize_original_height
            })

        self.update_image()
        self.regenerate_filename_suffix_if_size_changed()
        
        # Update any connected lines
        if hasattr(self.canvas.master, 'update_lines'):
            self.canvas.master.update_lines(self)
            
        # Detect and handle line crossings if applicable
        if hasattr(self.canvas.master, 'detect_and_break_line_crossings'):
            self.canvas.master.detect_and_break_line_crossings()
    
    def move(self, dx, dy):
        """Move the element and all its components"""
        super().move(dx, dy)
        
        # Additionally move resize handles
        for handle_info in self.resize_handles.values():
            self.canvas.move(handle_info['id'], dx, dy)
    
    def select_element(self, selected):
        """Select/deselect the element and show/hide resize handles"""
        super().select_element(selected)
        
        # Show or hide resize handles
        for handle_info in self.resize_handles.values():
            if selected:
                self.canvas.itemconfigure(handle_info['id'], outline=HIGHLIGHTING_COLOR, fill='white')
            else:
                self.canvas.itemconfigure(handle_info['id'], outline='', fill='')
    
    def delete(self):
        """Delete the element and all its components"""
        super().delete()
        
        # Additionally delete resize handles
        for handle_info in self.resize_handles.values():
            self.canvas.delete(handle_info['id'])

class ProcessControlLibraryElement(ProcessControlElement):
    """A process control element that is part of a ACM library, with an HMI symbol"""
    def __init__(self, x, y, width, height, default_image, name, font, 
                 top_anchors=None, bottom_anchors=None, left_anchors=None, right_anchors=None,
                 catalog_number=None, library_id=None, hmi_symbol=None, spa_name=None, spa_id=None, 
                 gfx_reference=None, path=None, pno=None, roi_uid=None):
        

        self.library_id = library_id
        self.catalog_number = catalog_number
        self.hmi_symbol = hmi_symbol 

        
        super().__init__(x, y, width, height, default_image, name, font,
                         top_anchors, bottom_anchors, left_anchors, right_anchors,
                         spa_name, spa_id, gfx_reference, path=path, pno=pno, roi_uid=roi_uid)
        

class ProcessControlAnchorElement(ProcessControlElement):
    """A process control element that has anchors for connections"""
    
    def __init__(self, x, y, scale, default_image, font):
        """Initialize a new process control anchor element"""

        width = 20
        height = 20


        top_anchors = [[width/2, 0, AnchorType.MATERIAL, None]]
        bottom_anchors = [[width/2, height, AnchorType.MATERIAL, None]]
        left_anchors = [[0, height/2, AnchorType.MATERIAL, None]]
        right_anchors = [[width, height/2, AnchorType.MATERIAL, None]]


        spa_id = str(uuid.uuid4())

        super().__init__(x - int(width/2 * scale), y - int(height/2 * scale), width, height, default_image, "", font,
                         top_anchors, bottom_anchors, left_anchors, right_anchors, spa_id=spa_id, image_tag='anchor_image')

    def get_anchor_position(self, anchor):
        """Return the position of the specified anchor"""
        
        # Check if this is one of our custom anchors
        if anchor in self.anchor_info:
            direction = self.anchor_info[anchor]['direction']
            coords = self.canvas.coords(self.image_id)

            
            # Return the anchor position and its type
            return coords[0], coords[1], direction.value

        # Not found
        return None
    
    def get_anchor_position_for_drag_line(self, anchor):
        """Get the position of an anchor for a drag line"""
        return super().get_anchor_position(anchor)
    




class AnchorElement:
    """Class representing a connection anchor point in the process diagram"""
    
    def __init__(self, canvas, x, y, anchor_type=None, parent_element=None):
        """Initialize a new anchor
        
        Args:
            canvas: The canvas to draw on
            x: X coordinate
            y: Y coordinate
            anchor_type: Type of anchor (e.g., TOP_ANCHOR, BOTTOM_ANCHOR, etc.)
            parent_element: The element this anchor belongs to (or None for free-standing anchors)
        """
        self.canvas = canvas
        self.x = x
        self.y = y
        self.type = anchor_type
        self.parent_element = parent_element
        self.connections = []  # List of lines connected to this anchor
        self.id = None  # Canvas ID of the anchor visual
        self.selected = False
        self.highlighted = False
        self.height = 0
        self.width = 0
        
        # Create the visual representation
        self.draw()
    
    def draw(self, scale=1.0):
        """Draw the anchor on the canvas"""
        if self.id:
            self.canvas.delete(self.id)
            
        self.id = self.canvas.create_oval(
            self.x - 5 * scale, 
            self.y - 5 * scale,
            self.x + 5 * scale, 
            self.y + 5 * scale,
            fill='', 
            outline='', 
            tags=('anchor', 'not_grid')
        )
    
    def move(self, dx, dy):
        """Move the anchor by the specified amount"""
        self.x += dx
        self.y += dy
        if self.id:
            self.canvas.move(self.id, dx, dy)
    
    def update_position(self, x, y, scale=1.0):
        """Update the anchor's position to new coordinates"""
        self.x = x
        self.y = y
        if self.id:
            self.canvas.coords(
                self.id,
                x - 5 * scale, 
                y - 5 * scale,
                x + 5 * scale, 
                y + 5 * scale
            )
    
    def highlight(self, highlight=True, color=HIGHLIGHTING_COLOR):
        """Highlight or unhighlight the anchor"""
        self.highlighted = highlight
        if highlight:
            self.canvas.itemconfig(self.id, fill=color)
        else:
            fill_color = color if self.selected else DRAWING_DEFAULT_COLOR
            self.canvas.itemconfig(self.id, fill=fill_color)
    
    def select(self, select=True, color=HIGHLIGHTING_COLOR):
        """Select or deselect the anchor"""
        self.selected = select
        if select:
            self.canvas.itemconfig(self.id, fill=color)
        else:
            self.canvas.itemconfig(self.id, fill=DRAWING_DEFAULT_COLOR if not self.highlighted else color)
    
    def add_connection(self, line_id):
        """Add a line connection to this anchor"""
        if line_id not in self.connections:
            self.connections.append(line_id)
    
    def remove_connection(self, line_id):
        """Remove a line connection from this anchor"""
        if line_id in self.connections:
            self.connections.remove(line_id)
    
    def get_anchor_position(self,_):
        """Get the position and type of this anchor"""
        return self.x, self.y, self.type
    
    def delete(self):
        """Delete the anchor from the canvas"""
        if self.id:
            self.canvas.delete(self.id)
            self.id = None


    def show_anchors(self, _=None):
        """Show the anchor on the canvas"""
        pass




class ProcessToolsMenu:
    """ Menu widget for the process diagram canvas GUI window """
    def __init__(self, master, functions, undo_manager):
        """ Initialize the Menu """
        self.__functs = functions  # obtain link on dictionary of functions
        self.__undo_manager = undo_manager  # obtain link on undo manager
        # Create menu icons from base64 (should be provided)
        # For now, using placeholders
        self.__edit_menu_up = False

        self.__label_show_object_names = "Show Object Names"
        self.__label_hide_object_names = "Hide Object Names"

        self.__create_basic_menu(master)
        self.__create_edit_menu(master)
        
        

    def __create_basic_menu(self, master):
        self.basic_menu = tk.Menu(master, tearoff=0)  # create main menu bar, public for the main GUI


        # Add undo/redo menu items
        self.basic_menu.add_command(label="Undo", command=self.__functs["undo"]
                                  , state='disabled',accelerator='Ctrl+Z')
        self.basic_menu.add_command(label="Redo", command=self.__functs["redo"]
                                  , state='disabled',accelerator='Ctrl+Shift+Z')
        self.basic_menu.add_separator()

    def __create_edit_menu(self, master):
        self.edit_menu = tk.Menu(master, tearoff=0)  # create main menu bar, public for the main GUI

        self.__label_edit_static_graphic = "Edit Static Graphic"
        self.__label_connect_element = 'Connect Element'
        self.__label_select_alternate_symbol = 'Change Symbol'
        self.__label_configure_symbol_anchors = 'Configure Symbol Anchors\u2026'
        self.__label_show_on_drawing = 'Show Link'
        self.__label_edit_delete = 'Delete'
        self.__label_change_anchor_position = 'Change Anchor Position'

        # Create alignment submenu
        self.align_menu = tk.Menu(self.edit_menu, tearoff=0)
        self.align_menu.add_command(label="Align Left", command=self.__functs["align_left"])
        self.align_menu.add_command(label="Align Horizontal Center", command=self.__functs["align_horizontal_center"])
        self.align_menu.add_command(label="Align Right", command=self.__functs["align_right"])
        self.align_menu.add_separator()
        self.align_menu.add_command(label="Align Top", command=self.__functs["align_top"])
        self.align_menu.add_command(label="Align Vertical Center", command=self.__functs["align_vertical_center"])
        self.align_menu.add_command(label="Align Bottom", command=self.__functs["align_bottom"])
        self.align_menu.add_separator()
        self.align_menu.add_command(label="Distribute Horizontal", command=self.__functs["distribute_horizontal"])
        self.align_menu.add_command(label="Distribute Vertical", command=self.__functs["distribute_vertical"])

        # Create anchor direction submenu
        self.anchor_direction_menu = tk.Menu(self.edit_menu, tearoff=0)
        self.anchor_direction_menu.add_command(label="Left", command=self.__functs["change_anchor_direction_left"])
        self.anchor_direction_menu.add_command(label="Right", command=self.__functs["change_anchor_direction_right"])
        self.anchor_direction_menu.add_command(label="Top", command=self.__functs["change_anchor_direction_top"])
        self.anchor_direction_menu.add_command(label="Bottom", command=self.__functs["change_anchor_direction_bottom"])

        # Create menu 
        self.edit_menu.add_command(label=self.__label_edit_static_graphic,
                                command=self.__functs["edit_static_graphic"],
                                state='disabled')
        self.edit_menu.add_cascade(label="Change Anchor Direction", menu=self.anchor_direction_menu, state='disabled')
        self.edit_menu.add_command(label=self.__label_change_anchor_position,
                                command=self.__functs["change_anchor_position"],
                                state='disabled')
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label=self.__label_select_alternate_symbol,
                                command=self.__functs["select_alternate_symbol"],
                                state='disabled')
        self.edit_menu.add_command(label=self.__label_configure_symbol_anchors,
                                command=self.__functs["configure_symbol_anchors"],
                                state='disabled')
        self.edit_menu.add_command(label=self.__label_show_on_drawing,
                                command=self.__functs["go_to_roi"],
                                state='disabled')
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label=self.__label_connect_element,
                                command=self.__functs["connect_element"],
                                state='disabled')
        self.edit_menu.add_command(label="Connect Signal Line",
                                command=self.__functs["create_signal_line"],
                                state='normal')
        
        # Create lines management submenu
        self.lines_menu = tk.Menu(self.edit_menu, tearoff=0)
        self.lines_menu.add_command(label="Remove All Material Lines", command=self.__functs["remove_all_material_lines"])
        self.lines_menu.add_command(label="Remove All Signal Lines", command=self.__functs["remove_all_signal_lines"])
        self.lines_menu.add_command(label="Remove All Lines", command=self.__functs["remove_all_lines"])
        
        self.edit_menu.add_cascade(label="Lines", menu=self.lines_menu, state='normal')
        self.edit_menu.add_cascade(label="Align", menu=self.align_menu, state='disabled')
        
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label=self.__label_edit_delete,
                                command=self.__functs["delete"],
                                state='normal')
        
    def enable_edit_static_graphic(self, enable=True):
        if enable:
            
            self.edit_menu.entryconfigure(self.__label_edit_static_graphic, state='normal')
        else:
            self.edit_menu.entryconfigure(self.__label_edit_static_graphic, state='disabled')

    def enable_select_alternate_symbol(self, enable=True):
        if enable:
            self.edit_menu.entryconfigure(self.__label_select_alternate_symbol, state='normal')
        else:
            self.edit_menu.entryconfigure(self.__label_select_alternate_symbol, state='disabled')

    def enable_configure_symbol_anchors(self, enable=True):
        if enable:
            self.edit_menu.entryconfigure(self.__label_configure_symbol_anchors, state='normal')
        else:
            self.edit_menu.entryconfigure(self.__label_configure_symbol_anchors, state='disabled')

    def enable_show_on_drawing(self, enable=True):
        if enable:
            self.edit_menu.entryconfigure(self.__label_show_on_drawing, state='normal')
        else:
            self.edit_menu.entryconfigure(self.__label_show_on_drawing, state='disabled')
            
    def enable_connect_element(self, enable=True):
        if enable:
            self.edit_menu.entryconfigure(self.__label_connect_element, state='normal') 
        else: 
            self.edit_menu.entryconfigure(self.__label_connect_element, state='disabled')

    def enable_align_menu(self, enable=True):
        if enable:
            self.edit_menu.entryconfigure("Align", state='normal')
        else:
            self.edit_menu.entryconfigure("Align", state='disabled')

    def enable_anchor_direction_menu(self, enable=True, current_direction=None):
        if enable:
            self.edit_menu.entryconfigure("Change Anchor Direction", state='normal')
            
            self.anchor_direction_menu.entryconfigure("Left", state='normal')
            self.anchor_direction_menu.entryconfigure("Right", state='normal')
            self.anchor_direction_menu.entryconfigure("Top", state='normal')
            self.anchor_direction_menu.entryconfigure("Bottom", state='normal')
            if current_direction is not None:
                # Enable only the relevant direction based on current direction
                if current_direction == AnchorDirection.LEFT:
                    self.anchor_direction_menu.entryconfigure("Left", state='disabled')
                elif current_direction == AnchorDirection.RIGHT:
                    self.anchor_direction_menu.entryconfigure("Right", state='disabled')
                elif current_direction == AnchorDirection.TOP:
                    self.anchor_direction_menu.entryconfigure("Top", state='disabled')
                elif current_direction == AnchorDirection.BOTTOM:
                    self.anchor_direction_menu.entryconfigure("Bottom", state='disabled')
        else:
            self.edit_menu.entryconfigure("Change Anchor Direction", state='disabled')

    def enable_change_anchor_position(self, enable=True):
        if enable:
            self.edit_menu.entryconfigure(self.__label_change_anchor_position, state='normal')
        else:
            self.edit_menu.entryconfigure(self.__label_change_anchor_position, state='disabled')

    def enable_undo(self, enable=True):
        if enable:
            self.basic_menu.entryconfigure("Undo", state='normal')
        else:
            self.basic_menu.entryconfigure("Undo", state='disabled')

    def enable_redo(self, enable=True):
        if enable:
            self.basic_menu.entryconfigure("Redo", state='normal')
        else:
            self.basic_menu.entryconfigure("Redo", state='disabled')

    def post_basic_menu(self, x, y, object_text_shown):
        if self.__edit_menu_up:
            self.__edit_menu_up = False 
            return
        
        self.enable_undo(self.__undo_manager.can_undo())
        self.enable_redo(self.__undo_manager.can_redo())

        self.add_show_object_names(self.basic_menu, object_text_shown)

        self.basic_menu.post(x, y)  # show popup menu


    def post_edit_menu(self, x, y):


        self.edit_menu.post(x, y)  # show popup menu
        self.__edit_menu_up = True


    def add_show_object_names(self, menu, object_text_shown=True):
        """ Add or remove the show object names menu item """

        try:
            menu.delete(self.__label_show_object_names)
        except tk.TclError:
            pass

        try:
            menu.delete(self.__label_hide_object_names)
        except tk.TclError:
            pass

        if object_text_shown:
            label = self.__label_hide_object_names
        else:
            label = self.__label_show_object_names
        menu.add_command(label=label, command=self.__functs["show_or_hide_object_names"], accelerator='Ctrl+T')


class PropertiesBar(tk.Frame):
    """Properties bar widget for displaying and editing element properties"""
    
    def __init__(self, parent, canvas_manager):
        super().__init__(parent)
        self.canvas_manager: ProcessDisplayCanvas = canvas_manager
        self.current_element = None
        
        # Configure the frame
        self.configure(relief='flat', bd=1, bg="#ffffff")
        
        # Create the UI elements
        self._create_widgets()

    def set_element(self, element):
        self.update_element_properties(element)


    def update_element_properties(self, element):
        self.current_element = element
        x, y, width, height = self.transform_coord_to_gfx(element)

        self.x_var.set(str(x))
        self.y_var.set(str(y))
        self.width_var.set(str(width))
        self.height_var.set(str(height))

        self.name_label.config(text=element.name)
        
        self.x_entry.config(state='normal')
        self.y_entry.config(state='normal')

        if isinstance(element, ProcessControlStaticGraphicElement):
            self.width_entry.config(state='normal')
            self.height_entry.config(state='normal')
            self.type_label.config(text=' | Static Graphic')
        elif isinstance(element, ProcessControlLibraryElement):
            self.width_entry.config(state='readonly')
            self.height_entry.config(state='readonly')
            if element.hmi_symbol and element.catalog_number:
                self.type_label.config(text=f" |  {element.catalog_number}  |  {element.hmi_symbol}")
            else:
                self.type_label.config(text=' | Process Control Element')
        elif isinstance(element, ProcessControlAnchorElement):
            self.width_entry.config(state='readonly')
            self.height_entry.config(state='readonly')
            self.type_label.config(text=' | Anchor Element')


    def transform_coord_to_gfx(self,element: ProcessControlElement):

        scale = self.canvas_manager.imscale
        bbox = self.canvas_manager.canvas.coords(self.canvas_manager.container)

        x = int((element.x - bbox[0]) / scale)
        y = int((element.y - bbox[1]) / scale)
        width = int(element.width)
        height = int(element.height)
        return x, y, width, height
    

    def _create_widgets(self):
        """Create all the widgets for the properties bar"""
        # Main container with padding
        main_frame = tk.Frame(self, bg="#ffffff")
        main_frame.pack(fill='x', padx=10, pady=5)
        
        # Position section
        pos_frame = tk.Frame(main_frame, bg="#ffffff")
        pos_frame.pack(side='left', padx=(0, 20))

        def validate_numeric_input(new_text):
            if new_text.isdigit() or new_text == "":
                return True
            else:
                return False
            
        vcmd = main_frame.register(validate_numeric_input)
        
        #tk.Label(pos_frame, text="Position:", font=('Arial', 8), bg="#ffffff", fg='#666666').pack(side='left')
        
        # X position
        tk.Label(pos_frame, text="X:", font=('Arial', 8), bg="#ffffff", fg='#666666').pack(side='left', padx=(10, 2))
        self.x_var = tk.StringVar()
        self.x_entry = ttk.Entry(pos_frame, width=8, font=('Arial', 8)
                                 , textvariable=self.x_var, state='readonly'
                                 , validate="key", validatecommand=(vcmd, '%P'), foreground="#5F5F5F")
        self.x_entry.pack(side='left', padx=(0, 5))
        
        # Y position
        tk.Label(pos_frame, text="Y:", font=('Arial', 8), bg="#ffffff", fg='#666666').pack(side='left', padx=(5, 2))

        self.y_var = tk.StringVar()
        self.y_entry = ttk.Entry(pos_frame, width=8, font=('Arial', 8)
                                 , textvariable=self.y_var, state='readonly'
                                 , validate="key", validatecommand=(vcmd, '%P'), foreground="#5F5F5F")
        self.y_entry.pack(side='left')

        # Separator
        separator = ttk.Separator(main_frame, orient='vertical', )
        separator.pack(side='left', fill='y', padx=(0, 10))
        
        # Size section
        self.size_frame = tk.Frame(main_frame, bg="#ffffff")
        self.size_frame.pack(side='left', padx=(0, 20))
        
        #tk.Label(self.size_frame, text="Size:", font=('Arial', 8), bg="#ffffff", fg='#666666').pack(side='left')
        
        # Width
        tk.Label(self.size_frame, text="Width:", font=('Arial', 8), bg="#ffffff", fg='#666666').pack(side='left', padx=(10, 2))
        self.width_var = tk.StringVar()
        self.width_entry = ttk.Entry(self.size_frame, width=8, font=('Arial', 8)
                                     , textvariable=self.width_var, state='readonly'
                                     , validate="key", validatecommand=(vcmd, '%P'), foreground="#5F5F5F")
        self.width_entry.pack(side='left', padx=(0, 5))
        
        # Height
        tk.Label(self.size_frame, text="Height:", font=('Arial', 8), bg="#ffffff", fg='#666666').pack(side='left', padx=(5, 2))
        self.height_var = tk.StringVar()
        self.height_entry = ttk.Entry(self.size_frame, width=8, font=('Arial', 8)
                                      , textvariable=self.height_var, state='readonly'
                                      , validate="key", validatecommand=(vcmd, '%P'), foreground="#5F5F5F")
        self.height_entry.pack(side='left')

        # Separator
        separator = ttk.Separator(main_frame, orient='vertical')
        separator.pack(side='left', fill='y', padx=(0, 10))

        # Element name label
        self.name_label = tk.Label(main_frame, text="No Selection", justify='right',
                                  font=('Arial', 8, 'bold'), bg="#ffffff", fg='#666666')
        self.name_label.pack(side='left', padx=(20, 0))
        
        # Element type label
        self.type_label = tk.Label(main_frame, text="", font=('Arial', 8), 
                                  fg='#666666', bg='#ffffff')
        self.type_label.pack(side='left')
        
        
        # Bind Enter key to apply changes
        self.x_entry.bind('<Return>', self._apply_position_changes)
        self.y_entry.bind('<Return>', self._apply_position_changes)
        self.width_entry.bind('<Return>', self._apply_width_changes)
        self.height_entry.bind('<Return>', self._apply_height_changes)
        
        # Bind focus out events to apply changes
        self.x_entry.bind('<FocusOut>', self._apply_position_changes)
        self.y_entry.bind('<FocusOut>', self._apply_position_changes)
        self.width_entry.bind('<FocusOut>', self._apply_width_changes)
        self.height_entry.bind('<FocusOut>', self._apply_height_changes)


    def _apply_position_changes(self, _=None):
        """Apply changes to the position of the current element"""
        if self.current_element:
            scale = self.canvas_manager.imscale
            new_x = int(float(self.x_entry.get()) * scale)
            new_y = int(float(self.y_entry.get()) * scale)

           

            self.canvas_manager.undo_manager.add_action('move_element', {
                'element': self.current_element,
                'original_x': self.current_element.original_x,
                'original_y': self.current_element.original_y,
                'new_x': self.current_element.x,  # Store current position for redo
                'new_y': self.current_element.y    # Store current position for redo
            })

            self.current_element.move(new_x - self.current_element.x, new_y - self.current_element.y)
            self.canvas_manager.update_lines(self.current_element)
            self.update_element_properties(self.current_element)
            
    def _apply_width_changes(self, _=None):
        """Apply changes to the width of the current element"""
        if self.current_element and isinstance(self.current_element, ProcessControlStaticGraphicElement):
            new_x = self.current_element.x
            new_y = self.current_element.y
            new_width = int(self.width_entry.get())
            new_height = new_width / self.current_element.aspect_ratio

            self.canvas_manager.undo_manager.add_action('resize_element', {
                'element': self.current_element,
                'original_x': self.current_element.x,
                'original_y': self.current_element.y,
                'original_width': self.current_element.width,
                'original_height': self.current_element.height
            })

            self.current_element.resize_to(new_x, new_y, new_width, new_height)
            self.current_element.update_image()
            self.current_element.regenerate_filename_suffix_if_size_changed()
            self.canvas_manager.update_lines(self.current_element)
            self.update_element_properties(self.current_element)

    def _apply_height_changes(self, _=None):
        """Apply changes to the height of the current element"""
        if self.current_element and isinstance(self.current_element, ProcessControlStaticGraphicElement):
            new_x = self.current_element.x
            new_y = self.current_element.y
            new_height = int(self.height_entry.get())
            new_width = new_height * self.current_element.aspect_ratio

            self.canvas_manager.undo_manager.add_action('resize_element', {
                'element': self.current_element,
                'original_x': self.current_element.x,
                'original_y': self.current_element.y,
                'original_width': self.current_element.width,
                'original_height': self.current_element.height
            })

            self.current_element.resize_to(new_x, new_y, new_width, new_height)
            self.current_element.update_image()
            self.current_element.regenerate_filename_suffix_if_size_changed()
            self.canvas_manager.update_lines(self.current_element)
            self.update_element_properties(self.current_element)



class ProcessDisplayCanvas(tk.Frame):
    """ Display and interact with process diagrams """
    def __init__(self, master, internal_db: Database, acm_data_handler, project_name, config,
                 selection_callback, zoom_percentage_callback, gfx_file, library_parsers,
                 use_express=True, go_to_roi_callback=None):
        """ Initialize the ProcessDisplayCanvas 
        
        Args:
            master: Parent widget
            internal_db: Database instance
            acm_data_handler: ACM data handler
            project_name: Name of the project
            config: Configuration object
            selection_callback: Callback for element selection
            zoom_percentage_callback: Callback for zoom changes
            gfx_file: Specific GFX file to load (required)
            use_express: Flag for express mode
            go_to_roi_callback: Callback for ROI navigation
        """
        super().__init__(master)
        self.imscale = 1.0  # scale for the canvas image zoom, public for outer classes
        self.__delta = 1.3  # zoom magnitude
        self.__huge = False
        self.__huge_size = 14000  # define size of the huge image
        self.__filter = Image.LANCZOS  # could be: NEAREST, BILINEAR, BICUBIC and ANTIALIAS
        self.point_spacing = 5
        self.canvas_elements: dict[str, ProcessControlElement] = {}
        self.moving_canvas = False
        self.dragging = False  # Flag to check if we are dragging (moving) an element
        self.dragged = False
        self.start_of_drag = False
        self.drag_line_id = None  # Track the current line being drawn
        self.drag_line_start_anchor = None  # Track the current anchor from which a line is being drawn
        self.drag_line_connection_valid = False
        self.drag_line_near_anchor = None
        self.drag_line_near_element = None
        self.dragging_segment = False
        self.drag_segment_handle = None
        self.drag_segment_line = None
        self.drag_segment_index = None
        self.drag_segment_start_x = 0
        self.drag_segment_start_y = 0
        self.drag_segment_original_coords = None
        self.lines = {}  # Store lines with references to their anchors
        self.lines_to_remove = []  # Lines that need to be removed
        self.drag_line_element = None
        self.material_lines = {}  # Store material lines separately
        self.signal_lines = {}  # Store signal lines separately
        # Signal lines that only exist because a material line had no usable anchor
        self.material_fallback_lines = set()
        self.lines_breaks = []
        self.pan_x = 0
        self.pan_y = 0
        self.menu_pop_x = 0
        self.menu_pop_y = 0
        self.selection_image = None
        self.selected_element = None
        self.select_element_id = None
        self.selected_line_id = None
        self.selected_elements = []  # New - track multiple selected elements
        self.last_selected_element = None  # New - track the last selected element
        self.highlighted_anchor = None  # Anchor currently highlighted
        self.grid_image = None
        self.offset_x = 0
        self.offset_y = 0
        self.font = font.Font(self, "Arial 10")  # create font object
        self.fontsize = 9
        self.previous_font_scale = 9
        self.grid_image_tkimage = None
        self.__zoom_percentage_callback = zoom_percentage_callback
        self.__selection_callback = selection_callback
        self.__go_to_roi_callback = go_to_roi_callback
        self.__showing_vertical_scroll = False
        self.__internal_db: Database = internal_db
        self.__acm_data_handler: ACM_Data_Handler = acm_data_handler
        self.__project_name = project_name
        self.__config = config
        self.__busy_canvas = None
        self.canvas = None
        self.temp_anchor = None
        self.anchors = []
        self.library_parsers = library_parsers
        self.show_object_names = True
        self.current_tool_mode = "select"
        self.editing_anchor_id = None
        self.use_express = use_express  # Flag to indicate if express mode is used

        self.material_line_width, self.material_line_color, _ = self.__config.get_hmi_material_line_properties()
        self.signal_line_width, self.signal_line_color, hasDot = self.__config.get_hmi_signal_line_properties()
        self.material_line_width = float(self.material_line_width)
        self.signal_line_width = float(self.signal_line_width)
        self.material_line_color = "#"+ self.material_line_color
        self.signal_line_color = "#"+ self.signal_line_color

        if hasDot:
            self.signal_line_dash = (7, 1, 1, 1)
        else:
            self.signal_line_dash = None

        self.__cached_anchor_image = tk.PhotoImage(data=build_hmi_anchor_canvas)

        self.factory_talk_view_se_id = self.__acm_data_handler.get_factory_talk_view_se_id()
        
        # Store the single GFX file
        self.gfx_file = gfx_file
        self.gfx_file_editor = None

        # Add undo manager
        self.undo_manager = UndoManager(self)

        

        self.show_busy_canvas(f"Loading {self.gfx_file}")

        self.banner_handler = banner_handler(self.__busy_canvas, 0,0, None, None)
        self.banner_handler.secondary_progress_banner.show()
        self.banner_handler.draw()
        self.done_loading = False

        # Async pipe extraction state (see __connect_elements / __run_pipe_extraction_worker)
        self.__pipe_extraction_done = False
        self.__pipe_extraction_result = None
        self.__pipe_extraction_error = None


    def set_tool_mode(self, mode):
        """Set the current tool mode
        
        Args:
            mode (str): The tool mode to set ('select', 'pan', 'scale', 'free_anchor')
        """
        self.current_tool_mode = mode
        
        # Update cursor based on mode
        if mode == "free_anchor":
            self.canvas.configure(cursor="crosshair")
        elif mode == "pan":
            self.canvas.configure(cursor="")
        else:  # select
            self.canvas.configure(cursor="")
        
        # If switching away from free_anchor mode, cancel any in-progress anchor creation
        if hasattr(self, "temp_anchor") and self.temp_anchor and mode != "free_anchor":
            self.delete(self.temp_anchor)
            self.temp_anchor = None
        


    def show_busy_canvas(self, text=""):
        self.__delete_busy_canvas()
        self.__busy_canvas = tk.Canvas(self)
        self.__busy_canvas.grid(row=0, column=0, sticky='nsew')

        # Configure grid row/column weights (important for proper resizing)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.__busy_canvas.config(background='#F5F5F5')
        loading = loading_animation(self.__busy_canvas)

        def center_loading(_):
            x = int(self.__busy_canvas.winfo_width()/2)
            y = int(self.__busy_canvas.winfo_height()/2)
            
            loading.draw(x ,y)                
            text_id = self.__busy_canvas.create_text(x, y + 24
                                            , text=text
                                            , fill="#6F6F6F"
                                            , anchor=tk.CENTER
                                            , justify=tk.CENTER )
            _,y1,_,y2 = self.__busy_canvas.bbox(text_id)
            self.__busy_canvas.move(text_id,0,int(abs(y1 - y2)/2))
            

        self.__busy_canvas.bind("<Configure>", center_loading)
        self.__busy_canvas.update()

    def __delete_busy_canvas(self):
        if self.__busy_canvas:
            self.__busy_canvas.grid_forget()
            try:
                self.__busy_canvas.destroy()
            except Exception as e:
                pass
            self.__busy_canvas = None


    def create_hmi_display_canvas(self, reset_state=False, done_callback=None):
        # Reset zoom
        self.imscale = 1.0

        self.__create_canvas()
        self.__create_elements()

        def _finalize():
            self.__create_pop_menu()
            # Clear undo history when changing pages
            self.undo_manager.clear()
            self.done_loading = True
            self.__delete_busy_canvas()
            if done_callback:
                try:
                    done_callback()
                except Exception as cb_err:
                    logging.exception(f"done_callback failed after canvas load: {cb_err}")

        if reset_state or not self.load_canvas_state():
            if reset_state:
                self.lines.clear()
                self.material_lines.clear()
                self.signal_lines.clear()
                self.material_fallback_lines.clear()
                self.lines_to_remove = []  # Lines that need to be removed
                self.drag_line_element = None
                self.lines_breaks = []
            # Pipe extraction is heavy (CV2 + Shapely + A*). Run it on a background
            # thread and finalize on the UI thread when it completes; otherwise the
            # Tk event loop is blocked and the whole app freezes during Build HMI.
            self.__connect_elements(done_callback=_finalize)
        else:
            _finalize()


    def __connect_elements(self, done_callback=None):
        if not self.__pdf_path:
            if done_callback:
                done_callback()
            return

        # Reset async state and spawn the CPU-heavy extractor on a worker thread.
        self.__pipe_extraction_done = False
        self.__pipe_extraction_result = None
        self.__pipe_extraction_error = None

        worker = Thread(target=self.__run_pipe_extraction_worker, daemon=True)
        worker.start()
        self.after(200, self.__check_pipe_extraction_done, done_callback)


    def __run_pipe_extraction_worker(self):
        """Background-thread worker: runs ProcessLinesExtractor. Must not touch Tk."""
        try:
            self.__pipe_extraction_result = ProcessLinesExtractor(
                self.__pdf_path, self.__pdf_pno, self.__internal_db)
        except Exception as e:
            logging.exception(f"Pipe extraction failed for {self.gfx_file}: {e}")
            self.__pipe_extraction_error = e
            self.__pipe_extraction_result = []
        finally:
            self.__pipe_extraction_done = True


    def __check_pipe_extraction_done(self, done_callback=None):
        """UI-thread poll for extraction completion. Applies data and fires callback."""
        if not self.__pipe_extraction_done:
            self.after(200, self.__check_pipe_extraction_done, done_callback)
            return

        connection_data = self.__pipe_extraction_result or []
        # Clear worker-shared state before touching the canvas.
        self.__pipe_extraction_result = None
        self.__pipe_extraction_error = None

        try:
            self.__apply_connection_data(connection_data)
        except Exception as apply_err:
            logging.exception(
                f"Error applying pipe extraction results for {self.gfx_file}: {apply_err}")

        if done_callback:
            done_callback()


    def __apply_connection_data(self, connection_data):
        """UI-thread canvas work: draw signal/material lines and prune stale ones."""
        dict_spa_ids = { ele.spa_id: canvas_id for canvas_id, ele in self.canvas_elements.items() if ele.spa_id is not None }

        self.lines_to_remove = self.lines.copy()

        for connection in connection_data:
            spa_id = connection['point'][2]
            elem_1: ProcessControlElement = self.canvas_elements.get(dict_spa_ids.get(spa_id))
            if not elem_1:
                logging.warning(f"Element with SPA ID {spa_id} not found in canvas elements.")
                continue

            anchor_1 = elem_1.get_anchor_position_by_connection(connection['point'])

            if connection['cleaned_points_of_int']:
                for conn in connection['cleaned_points_of_int']:
                    elem_2: ProcessControlElement = self.canvas_elements.get(dict_spa_ids.get(conn[2]))
                    if not elem_2:
                        logging.warning(f"Element with SPA ID {conn[2]} not found in canvas elements.")
                        continue
                    anchor_2 = elem_2.get_anchor_position_by_connection(conn)
                    # Use image-based line type if available, otherwise fall back to anchor heuristic
                    detected_type = connection.get('line_type')
                    if detected_type == 'signal':
                        self.__create_signal_line(anchor_1, anchor_2, elem_1, elem_2)
                    elif detected_type == 'material' and anchor_1 and anchor_2 and 'border' not in [anchor_1, anchor_2]:
                        self.__create_material_line(anchor_1, anchor_2, elem_1, elem_2, True)
                    elif anchor_1 and anchor_2 and 'border' not in [anchor_1, anchor_2]:
                        self.__create_material_line(anchor_1, anchor_2, elem_1, elem_2, True)
                    else:
                        # Downgraded only because an end has no usable anchor, so flag it:
                        # giving that symbol anchors later must restore the material line.
                        self.__create_signal_line(anchor_1, anchor_2, elem_1, elem_2, material_fallback=True)


        if self.lines_to_remove:
            for line_id in self.lines_to_remove:
                # Delete the selected line
                self.canvas.delete(line_id)
                self.canvas.delete('handle_' + str(line_id))
                # Remove the line from the lines dictionary
                del self.lines[line_id]
                if line_id in self.material_lines:
                    del self.material_lines[line_id]
                elif line_id in self.signal_lines:
                    del self.signal_lines[line_id]
                self.material_fallback_lines.discard(line_id)
                self.selected_line_id = None
            self.lines_to_remove.clear()

        self.send_lines_back()



    # Old multi-file loading methods removed - now using single file mode only


    def __map_gfx_file_to_hmi_display(self):
        """ Map the single GFX file to HMI display """
        try:
            hmi_displays = self.__internal_db.get_all_hmi_displays()
            self.__gfx_file_to_display = {}
            
            # Find the matching HMI display for our GFX file
            for display in hmi_displays:
                display_name = display['name'] + '.xml'
                if display_name == self.gfx_file:
                    self.__gfx_file_to_display[self.gfx_file] = display
                    break
        except Exception as e:
            logging.error(f"Error mapping GFX file to HMI display: {e}")
            self.__gfx_file_to_display = {}

    def load_gfx_file(self, done_callback=None):
        """Start loading the single GFX file in a separate thread"""
        self.show_busy_canvas(f"Loading {self.gfx_file}")
        
        # Map the GFX file to HMI display
        self.__map_gfx_file_to_hmi_display()
        
        db_thread = Thread(target=self.__load_gfx_file)
        db_thread.start()
        self.after(500, self.__check_gfx_loading_done, done_callback)

    def __load_gfx_file(self):
        """Load the GFX file editor"""
        #try:
            
        gfx_file_path = None  # Adjust this if you need a specific path
        
        self.gfx_file_editor = GfxFileEditor(self.factory_talk_view_se_id, self.gfx_file,
                                                gfx_file_path, self.__acm_data_handler,
                                                self.__project_name, self.__config,
                                                self.library_parsers, self.use_express)
        logging.info(f"Loaded GfxFileEditor for {self.gfx_file}")
        #except Exception as e:
        #    print(f"Error loading GFX file {self.__gfx_file}: {e}")
        #self.__gfx_file_editor = None

    def __check_gfx_loading_done(self, done_callback=None):
        """Check if GFX file loading is complete and create the display"""
        if self.gfx_file_editor is not None:
            # Note: __delete_busy_canvas() is invoked by create_hmi_display_canvas's
            # _finalize helper, which now fires only after pipe extraction actually
            # completes on the background thread. done_callback is threaded through
            # so BuildDisplay's sequential canvas loader advances at true completion.
            self.create_hmi_display_canvas(done_callback=done_callback)
        else:
            # Continue checking if not loaded yet
            self.after(500, self.__check_gfx_loading_done, done_callback)

    def show_gfx_file_editor(self, gfx_file_editor_index):
        """ Show the GfxFileEditor (no-op in single file mode) """
        pass


    def reset_gfx_file_editor(self):
        """ Reset the GfxFileEditor """
        self.show_busy_canvas(f"Loading {self.gfx_file}")
        # create_hmi_display_canvas now runs pipe extraction on a background thread
        # and clears the busy canvas from its _finalize helper when extraction ends.
        self.create_hmi_display_canvas(reset_state=True)


    def get_gfx_file_editor(self):
        """ Get the GfxFileEditor """
        return self.gfx_file_editor

    def get_hmi_display(self):
        """ Get the HMI display for the GfxFileEditor """
        if hasattr(self, '_ProcessDisplayCanvas__gfx_file_to_display') and self.gfx_file in self.__gfx_file_to_display:
            return self.__gfx_file_to_display[self.gfx_file]
        return None
    
    def get_canvas_elements(self):
        """ Get the canvas elements """
        return self.canvas_elements
    

    def get_static_graphic_elements(self, exclude=None):
        """ Get the static graphic elements currently on the display """
        return [element for element in self.canvas_elements.values()
                if isinstance(element, ProcessControlStaticGraphicElement) and element is not exclude]
    

    def apply_style_to_all_displays(self, stroke_color, fill_color, stroke_width, exclude=None):
        """ Restyle the static graphics on every open display and in every saved display """
        for canvas in self.__open_display_canvases():
            for element in canvas.get_static_graphic_elements(exclude=exclude):
                element.restyle(stroke_color, fill_color, stroke_width)

        if not self.__internal_db:
            return

        for record in self.__internal_db.get_all_build_hmi_displays():
            state = record.get('state') or {}
            changed = False
            for element_data in state.get('elements', []):
                svg_string = element_data.get('svg_string')
                if not svg_string:
                    continue
                try:
                    restyled = restyle_svg_string(svg_string, stroke_color, fill_color, stroke_width)
                except ET.ParseError:
                    logging.exception(f"Could not restyle a graphic in {record.get('gfx_file_name')}")
                    continue
                if restyled:
                    element_data['svg_string'] = restyled
                    changed = True

            if changed:
                self.__internal_db.save_build_hmi_display(record.get('gfx_file_name'), state)
    

    def __open_display_canvases(self):
        """ Every display canvas loaded alongside this one, since they all hold live elements """
        parent = self.master
        siblings = parent.winfo_children() if parent is not None else []
        canvases = [child for child in siblings if isinstance(child, ProcessDisplayCanvas)]
        return canvases or [self]
    

    def generate_display(self, export_path):
        """ Generate the display """
        gfx_file_editor = self.gfx_file_editor
        canvas_elements = self.canvas_elements
        for element in canvas_elements.values():
            bbox = self.canvas.coords(self.container)

            x = (element.x - bbox[0]) / self.imscale
            y = (element.y - bbox[1]) / self.imscale

            if isinstance(element, ProcessControlStaticGraphicElement):
                new_image_name = gfx_file_editor.change_element_size(element.gfx_reference
                                                                     ,element.width
                                                                     ,element.height
                                                                     ,element.filename_suffix)
                
                # If path "export_path/images" does not exist, create it

                if not os.path.exists(os.path.join(export_path, 'images')):
                    os.makedirs(os.path.join(export_path, 'images'))

                file_path = os.path.join(export_path,'images', f"{new_image_name}.svg")
                element.export_svg_string(file_path)


            gfx_file_editor.change_element_position(element.gfx_reference, x, y)
            

        material_lines = self.get_lines_data(self.material_lines)
        signal_lines = self.get_lines_data(self.signal_lines)
        line_breaks = [{'x':line_break[2][0], 'y':line_break[2][1]} for line_break in self.lines_breaks]

        return gfx_file_editor.export_display(material_lines, signal_lines, line_breaks, export_path)


    def get_lines_data(self, lines_dict):
        """
        Get the coordinates of all lines in the given lines_dict the follow format for each segment of the line:
        { x0=x0, y0=y0, x1=x1, y1=y1}

        Args:
            lines_dict: Dictionary of line IDs and their corresponding canvas elements
        Returns:
            A list of dictionaries containing the coordinates of each line segment
        """
        result = []
        bbox = self.canvas.coords(self.container)
        for line_id, _ in lines_dict.items():
            segments = self.canvas.coords(line_id)
            for i in range(0, len(segments) - 2, 2):
                x0, y0, x1, y1 = segments[i:i+4]
                result.append({
                    'x0': (x0 - bbox[0]) / self.imscale,
                    'y0': (y0 - bbox[1]) / self.imscale,
                    'x1': (x1 - bbox[0]) / self.imscale,
                    'y1': (y1 - bbox[1]) / self.imscale
                })

        return result



    def get_display_name(self):
        """ Get the display name """
        return self.gfx_file_editor.display_name if self.gfx_file_editor else self.gfx_file
    

    def get_number_of_gfx_file_editors(self):
        """ Get the number of GfxFileEditors (always 1 in single file mode) """
        return 1


    def __create_pop_menu(self):
        functs = {
            "edit_static_graphic": self.edit_static_graphic,
            "select_alternate_symbol": self.select_alternate_symbol,
            "configure_symbol_anchors": self.configure_symbol_anchors,
            "go_to_roi": self.go_to_roi,
            "connect_element": self.connect_element,
            "create_signal_line": self.create_signal_line,
            "delete": self.delete_item,
            "align_left": self.align_left,
            "align_horizontal_center": self.align_horizontal_center,
            "align_right": self.align_right,
            "align_top": self.align_top,
            "align_vertical_center": self.align_vertical_center,
            "align_bottom": self.align_bottom,
            "distribute_horizontal": self.distribute_horizontal,
            "distribute_vertical": self.distribute_vertical,
            "undo": self.undo,
            "redo": self.redo,
            "show_text": self.show_text,
            "hide_text": self.hide_text,
            "show_or_hide_object_names": self.show_or_hide_object_names,
            "change_anchor_direction_left": self.change_anchor_direction_left,
            "change_anchor_direction_right": self.change_anchor_direction_right,
            "change_anchor_direction_top": self.change_anchor_direction_top,
            "change_anchor_direction_bottom": self.change_anchor_direction_bottom,
            "change_anchor_position": self.change_anchor_position,
            "remove_all_material_lines": self.remove_all_material_lines,
            "remove_all_signal_lines": self.remove_all_signal_lines,
            "remove_all_lines": self.remove_all_lines,
        }
        self.menu = ProcessToolsMenu(self.canvas, functs, self.undo_manager)


    def remove_all_material_lines(self):
        self.canvas.delete("material_line")
        for line in self.material_lines.keys():
            if line in self.lines:
                del self.lines[line]
        self.material_lines.clear()


    def remove_all_signal_lines(self):
        self.canvas.delete("signal_line")
        for line in self.signal_lines.keys():
            if line in self.lines:
                del self.lines[line]
        self.signal_lines.clear()
        self.material_fallback_lines.clear()

    
    def remove_all_lines(self):
        self.canvas.delete("material_line")
        self.canvas.delete("signal_line")
        self.lines.clear()
        self.material_lines.clear()
        self.signal_lines.clear()
        self.material_fallback_lines.clear()


    def go_to_roi(self):
        """ Go to the ROI of the selected element """
        if self.selected_elements and len(self.selected_elements) == 1:
            element:ProcessControlElement = self.selected_elements[0]
            path = element.path
            pno = element.pno
            roi_uid = element.roi_uid
            if not path or pno is None or not roi_uid:
                messagebox.showinfo("Not Found", "The selected element does not have an associated Solutions Project Accelerator link.")
                return
            if self.__go_to_roi_callback:
                self.__go_to_roi_callback(roi_uid, pno, path)


    def show_text(self):
        """ Show text for all canvas elements """
        for element in self.canvas_elements.values():
            if hasattr(element, 'show_text'):
                element.show_text()


    def hide_text(self):
        """ Hide text for all canvas elements """
        for element in self.canvas_elements.values():
            if hasattr(element, 'hide_text'):
                element.hide_text()


    def edit_static_graphic(self):

        """ Edit the static graphic of the selected element """

        if self.selected_elements and len(self.selected_elements) == 1:
            # Get the current element's static graphic
            SVGEditor(self, build_hmi_element=self.selected_elements[0], config=self.__config)

    def change_anchor_position(self):
        """ Change the anchor position for the selected elements """
        if self.highlighted_anchor:
            element = self.highlighted_anchor[1]
            anchor_id = self.highlighted_anchor[0]
            
            # Start anchor position editing mode
            self._start_anchor_position_editing(anchor_id, element)

    
    def _start_anchor_position_editing(self, anchor_id, element):
        """Start the anchor position editing mode"""
        # Store the editing state
        self.editing_anchor_id = anchor_id
        self.editing_anchor_element = element
        self.editing_anchor_original_coords = self.canvas.coords(anchor_id)
        
        # Change anchor appearance to white outline
        self.canvas.itemconfig(anchor_id, outline='white', width=2)
        
        # Bind events for anchor editing
        self.canvas.tag_bind(anchor_id, '<B1-Motion>', self._drag_anchor_position, '+')
        self.canvas.tag_bind(anchor_id, '<ButtonPress-1>', self._start_drag_anchor_position, '+')
        self.canvas.tag_bind(anchor_id, '<ButtonRelease-1>', self._end_drag_anchor_position, '+')

        # Bind canvas click to end editing
        self.canvas.bind('<Button-1>', self._end_anchor_editing_on_canvas_click)
        
        # Bind arrow keys for precise movement
        self.canvas.bind('<KeyPress-Left>', self._move_anchor_left)
        self.canvas.bind('<KeyPress-Right>', self._move_anchor_right)
        self.canvas.bind('<KeyPress-Up>', self._move_anchor_up)
        self.canvas.bind('<KeyPress-Down>', self._move_anchor_down)
        
        # Make sure canvas has focus for key events
        self.canvas.focus_set()

    def _start_drag_anchor_position(self, event):
        """Start dragging the anchor position"""
        if self.editing_anchor_id is None:
            return
        
        self.anchor_drag_start_x = self.canvas.canvasx(event.x)
        self.anchor_drag_start_y = self.canvas.canvasy(event.y)

    def _end_drag_anchor_position(self, event):
        """End dragging the anchor position"""
        # This is handled by the canvas click or key events
        pass

    def _drag_anchor_position(self, event):
        """Update anchor position during drag"""
        if self.editing_anchor_id is None:
            return
        
        # Calculate movement
        current_x = self.canvas.canvasx(event.x)
        current_y = self.canvas.canvasy(event.y)
        dx = current_x - self.anchor_drag_start_x
        dy = current_y - self.anchor_drag_start_y
        
        # Move the anchor
        self.canvas.move(self.editing_anchor_id, dx, dy)
        
        # Update the anchor info in the element
        self._update_anchor_info_position(dx, dy)
        
        # Update connected lines
        self.update_lines(self.editing_anchor_element)
        
        # Update start position for next movement
        self.anchor_drag_start_x = current_x
        self.anchor_drag_start_y = current_y


    def _move_anchor_left(self, event):
        """Move anchor left by 1 pixel"""
        if hasattr(self, 'editing_anchor_id'):
            self.canvas.move(self.editing_anchor_id, -1, 0)
            self._update_anchor_info_position(-1, 0)
            self.update_lines(self.editing_anchor_element)

    def _move_anchor_right(self, event):
        """Move anchor right by 1 pixel"""
        if hasattr(self, 'editing_anchor_id'):
            self.canvas.move(self.editing_anchor_id, 1, 0)
            self._update_anchor_info_position(1, 0)
            self.update_lines(self.editing_anchor_element)

    def _move_anchor_up(self, event):
        """Move anchor up by 1 pixel"""
        if hasattr(self, 'editing_anchor_id'):
            self.canvas.move(self.editing_anchor_id, 0, -1)
            self._update_anchor_info_position(0, -1)
            self.update_lines(self.editing_anchor_element)

    def _move_anchor_down(self, event):
        """Move anchor down by 1 pixel"""
        if hasattr(self, 'editing_anchor_id'):
            self.canvas.move(self.editing_anchor_id, 0, 1)
            self._update_anchor_info_position(0, 1)
            self.update_lines(self.editing_anchor_element)

    def _update_anchor_info_position(self, dx, dy):
        """Update the anchor info position in the element"""
        if not hasattr(self, 'editing_anchor_id'):
            return
        
        anchor_id = self.editing_anchor_id
        element = self.editing_anchor_element
        
        if anchor_id in element.anchor_info:
            pos_x, pos_y = element.anchor_info[anchor_id]['position']
            element.anchor_info[anchor_id]['position'] = (pos_x + dx, pos_y + dy)

    def _end_anchor_editing_on_canvas_click(self, event):
        """End anchor editing when clicking outside the anchor"""
        if self.editing_anchor_id is None:
            return
        
        # Check if the click was on the anchor being edited
        current = self.canvas.find_withtag("current")  # Finds the item that is currently under the cursor
        tags = self.canvas.gettags(current)
        
        if self.editing_anchor_id in tags:
            return  # Don't end editing if clicking on the anchor itself
        
        # End anchor editing
        self._end_anchor_position_editing()

    def _end_anchor_position_editing(self):
        """End the anchor position editing mode"""
        if self.editing_anchor_id is None:
            return
        
        anchor_id = self.editing_anchor_id
        element = self.editing_anchor_element
        
        # Record the position change for undo
        new_coords = self.canvas.coords(anchor_id)
        if hasattr(self, 'editing_anchor_original_coords'):
            self.undo_manager.add_action('change_anchor_position', {
                'anchor_id': anchor_id,
                'element': element,
                'original_coords': self.editing_anchor_original_coords,
                'new_coords': new_coords
            })
        
        # Restore normal anchor appearance
        self.canvas.itemconfig(anchor_id, outline='', width=1)
        
        # Remove the editing event bindings
        self.canvas.tag_unbind(anchor_id, '<B1-Motion>')
        self.canvas.tag_unbind(anchor_id, '<ButtonPress-1>')
        self.canvas.tag_unbind(anchor_id, '<ButtonRelease-1>')
        
        # Remove canvas bindings
        self.canvas.unbind('<Button-1>')
        self.canvas.unbind('<KeyPress-Left>')
        self.canvas.unbind('<KeyPress-Right>')
        self.canvas.unbind('<KeyPress-Up>')
        self.canvas.unbind('<KeyPress-Down>')
        
        # Restore original canvas bindings
        self.canvas.bind('<ButtonPress-1>', self.__on_click)
        self.canvas.bind('<Up>', self.move_selection_up)
        self.canvas.bind('<Down>', self.move_selection_down)
        self.canvas.bind('<Left>', self.move_selection_left)
        self.canvas.bind('<Right>', self.move_selection_right)
        
        # Clean up editing state
        self.editing_anchor_id = None
        self.editing_anchor_element = None
        if hasattr(self, 'editing_anchor_original_coords'):
            delattr(self, 'editing_anchor_original_coords')
        if hasattr(self, 'anchor_drag_start_x'):
            delattr(self, 'anchor_drag_start_x')
        if hasattr(self, 'anchor_drag_start_y'):
            delattr(self, 'anchor_drag_start_y')
        
        # Update anchor position in the element's anchor collections
        self._update_element_anchor_collections(anchor_id, element)

    def _update_element_anchor_collections(self, anchor_id, element):
        """Update the anchor's relative position in the element's anchor collections"""
        if anchor_id not in element.anchor_info:
            return
        
        # Get the current absolute position of the anchor
        coords = self.canvas.coords(anchor_id)
        anchor_center_x = (coords[0] + coords[2]) / 2
        anchor_center_y = (coords[1] + coords[3]) / 2
        
        # Calculate relative position to the element
        rel_x = (anchor_center_x - element.x) / self.imscale
        rel_y = (anchor_center_y - element.y) / self.imscale
        
        # Update the anchor in the appropriate collection
        anchor_type = element.anchor_info[anchor_id]['type']
        direction = element.anchor_info[anchor_id]['direction']
        
        # Find and update the anchor in the appropriate collection
        if direction == AnchorDirection.TOP:
            for i, anchor_data in enumerate(element.top_anchors):
                if len(anchor_data) > 4 and anchor_data[4] == anchor_id:
                    element.top_anchors[i] = [rel_x, rel_y, anchor_type, anchor_data[3], anchor_id]
                    break
            if anchor_id in element.top_anchor_ids:
                element.top_anchor_ids[anchor_id] = (rel_x, rel_y, anchor_type)
        elif direction == AnchorDirection.BOTTOM:
            for i, anchor_data in enumerate(element.bottom_anchors):
                if len(anchor_data) > 4 and anchor_data[4] == anchor_id:
                    element.bottom_anchors[i] = [rel_x, rel_y, anchor_type, anchor_data[3], anchor_id]
                    break
            if anchor_id in element.bottom_anchor_ids:
                element.bottom_anchor_ids[anchor_id] = (rel_x, rel_y, anchor_type)
        elif direction == AnchorDirection.LEFT:
            for i, anchor_data in enumerate(element.left_anchors):
                if len(anchor_data) > 4 and anchor_data[4] == anchor_id:
                    element.left_anchors[i] = [rel_x, rel_y, anchor_type, anchor_data[3], anchor_id]
                    break
            if anchor_id in element.left_anchor_ids:
                element.left_anchor_ids[anchor_id] = (rel_x, rel_y, anchor_type)
        elif direction == AnchorDirection.RIGHT:
            for i, anchor_data in enumerate(element.right_anchors):
                if len(anchor_data) > 4 and anchor_data[4] == anchor_id:
                    element.right_anchors[i] = [rel_x, rel_y, anchor_type, anchor_data[3], anchor_id]
                    break
            if anchor_id in element.right_anchor_ids:
                element.right_anchor_ids[anchor_id] = (rel_x, rel_y, anchor_type)
        
        # Update the anchor info position
        element.anchor_info[anchor_id]['position'] = (anchor_center_x, anchor_center_y)

        self.canvas.itemconfig(anchor_id, outline='', width=2)
        element.select_anchor(anchor_id, False)


    def change_anchor_direction_left(self):
        """ Change the anchor direction to left for the selected elements """
        if self.highlighted_anchor:
            element = self.highlighted_anchor[1]
            anchor_id = self.highlighted_anchor[0]
            previous_direction = element.change_anchor_direction(anchor_id, AnchorDirection.LEFT)
            self.update_lines(element)
            self.undo_manager.add_action('change_anchor_direction', 
                                         {'element': element
                                          , 'anchor_id': anchor_id
                                          , 'previous_direction': previous_direction
                                          , 'new_direction': AnchorDirection.LEFT
                                          })

    def change_anchor_direction_right(self):
        """ Change the anchor direction to right for the selected elements """
        if self.highlighted_anchor:
            element = self.highlighted_anchor[1]
            anchor_id = self.highlighted_anchor[0]
            previous_direction = element.change_anchor_direction(anchor_id, AnchorDirection.RIGHT)
            self.update_lines(element)
            self.undo_manager.add_action('change_anchor_direction', 
                                         {'element': element
                                          , 'anchor_id': anchor_id
                                          , 'previous_direction': previous_direction
                                          , 'new_direction': AnchorDirection.RIGHT
                                          })

    def change_anchor_direction_top(self):
        """ Change the anchor direction to top for the selected elements """
        if self.highlighted_anchor:
            element = self.highlighted_anchor[1]
            anchor_id = self.highlighted_anchor[0]
            previous_direction = element.change_anchor_direction(anchor_id, AnchorDirection.TOP)
            self.update_lines(element)
            self.undo_manager.add_action('change_anchor_direction', 
                                         {'element': element
                                          , 'anchor_id': anchor_id
                                          , 'previous_direction': previous_direction
                                          , 'new_direction': AnchorDirection.TOP
                                          })

    def change_anchor_direction_bottom(self):
        """ Change the anchor direction to bottom for the selected elements """
        if self.highlighted_anchor:
            element = self.highlighted_anchor[1]
            anchor_id = self.highlighted_anchor[0]
            previous_direction = element.change_anchor_direction(anchor_id, AnchorDirection.BOTTOM)
            self.update_lines(element)
            self.undo_manager.add_action('change_anchor_direction', 
                                         {'element': element
                                          , 'anchor_id': anchor_id
                                          , 'previous_direction': previous_direction
                                          , 'new_direction': AnchorDirection.BOTTOM
                                          })

    def select_alternate_symbol(self):
        """ Select an alternate symbol for the selected element """

        gfx_file_editor = self.gfx_file_editor

        if self.selected_elements and len(self.selected_elements) == 1:
            # Get the current element's symbol
            current_symbol = self.selected_elements[0].hmi_symbol
            # Open the symbol selector dialog
            library_parsers = gfx_file_editor.get_library_parsers()
            library_parser = library_parsers[self.selected_elements[0].library_id]
            HMISymbolSelector(self, library_parser, current_symbol, 
                              callback=self.on_symbol_selected)
        else:
            logging.warning("No element selected to change symbol.")


    def configure_symbol_anchors(self):
        """Open the anchor-configuration dialog for the selected library symbol.

        PlantPAx / ACM library symbols ship without ``_Anchor_*`` marker
        ellipses, so no anchors are extracted at parse time. This entry
        point lets the user place, drag, redirect, and delete anchors on
        the symbol's SVG; on save the override is persisted globally
        (``logic_library_anchor_overrides``) and every instance of that
        symbol on the current display refreshes its anchors so connected
        lines re-attach through the existing ``set_anchors`` path.
        """
        if not self.selected_elements or len(self.selected_elements) != 1:
            logging.warning("configure_symbol_anchors: exactly one element must be selected.")
            return

        element = self.selected_elements[0]
        if not isinstance(element, ProcessControlLibraryElement):
            logging.warning("configure_symbol_anchors: selected element is not a library symbol.")
            return

        library_id = element.library_id
        symbol_name = element.hmi_symbol
        if not library_id or not symbol_name:
            logging.warning("configure_symbol_anchors: element is missing library_id or hmi_symbol.")
            return

        gfx_file_editor = self.gfx_file_editor
        # Locate the raw symbol XML - needed by the editor to render the SVG.
        library_parsers = gfx_file_editor.get_library_parsers() or {}
        parser = library_parsers.get(library_id)
        if parser is None:
            messagebox.showerror(
                "Configure Symbol Anchors",
                f"Could not locate library parser for library '{library_id}'.",
            )
            return
        symbol_xml = None
        try:
            for entry in parser.extract_all_ft_view_se_symbols():
                if entry.get('Name') == symbol_name:
                    symbol_xml = entry.get('Value')
                    break
        except Exception as exc:  # noqa: BLE001 - keep UI responsive
            logging.exception("configure_symbol_anchors: failed to enumerate symbols: %s", exc)
            messagebox.showerror(
                "Configure Symbol Anchors",
                f"Could not read symbol XML from library:\n{exc}",
            )
            return
        if not symbol_xml:
            messagebox.showerror(
                "Configure Symbol Anchors",
                f"Symbol '{symbol_name}' was not found in library '{library_id}'.",
            )
            return

        # Convert the current in-memory anchor dict (keyed by AnchorDirection
        # enum members with tuple values) into the flat dict the editor expects.
        current_anchors = {'top': [], 'bottom': [], 'left': [], 'right': []}
        try:
            svg_entry = gfx_file_editor.library_svg_images.get(library_id, {}).get(symbol_name)
            if svg_entry and len(svg_entry) >= 3 and svg_entry[2]:
                anchors_dict = svg_entry[2]
                current_anchors['top']    = [(float(x), float(y)) for x, y in anchors_dict.get(AnchorDirection.TOP, [])]
                current_anchors['bottom'] = [(float(x), float(y)) for x, y in anchors_dict.get(AnchorDirection.BOTTOM, [])]
                current_anchors['left']   = [(float(x), float(y)) for x, y in anchors_dict.get(AnchorDirection.LEFT, [])]
                current_anchors['right']  = [(float(x), float(y)) for x, y in anchors_dict.get(AnchorDirection.RIGHT, [])]
        except Exception:  # noqa: BLE001 - defensive
            logging.exception("configure_symbol_anchors: failed to read current anchors; starting empty.")

        def _on_save(payload):
            self._apply_library_anchor_override(library_id, symbol_name, payload)

        LibraryAnchorEditor(
            self,
            library_id=library_id,
            symbol_name=symbol_name,
            symbol_xml=symbol_xml,
            initial_anchors=current_anchors,
            on_save=_on_save,
        )


    def _apply_library_anchor_override(self, library_id, symbol_name, anchors_payload):
        """Persist an anchor override and refresh every instance on this display.

        ``anchors_payload`` is the ``{'top': [...], 'bottom': [...], ...}`` dict
        emitted by :class:`LibraryAnchorEditor` in SVG viewBox coordinates.
        """
        # 1. Persist globally so future GfxFileEditor loads pick it up.
        try:
            store = _get_anchor_override_store()
            store.set(library_id, symbol_name, anchors_payload)
            store.save()
        except Exception as exc:  # noqa: BLE001 - refresh should still run
            logging.exception("Failed to persist anchor override: %s", exc)
            messagebox.showwarning(
                "Configure Symbol Anchors",
                f"Anchors could not be saved to disk:\n{exc}\n\n"
                "The change is applied to the current session only.",
            )

        # 2. Update the in-memory library_svg_images cache so subsequent
        # element creations / symbol swaps see the new anchor set.
        try:
            svg_entry = self.gfx_file_editor.library_svg_images.get(library_id, {}).get(symbol_name)
            if svg_entry and len(svg_entry) >= 3:
                svg_entry[2] = {
                    AnchorDirection.TOP:    [tuple(pt) for pt in anchors_payload.get('top', [])],
                    AnchorDirection.BOTTOM: [tuple(pt) for pt in anchors_payload.get('bottom', [])],
                    AnchorDirection.LEFT:   [tuple(pt) for pt in anchors_payload.get('left', [])],
                    AnchorDirection.RIGHT:  [tuple(pt) for pt in anchors_payload.get('right', [])],
                    AnchorDirection.ANY:    [],
                }
        except Exception:  # noqa: BLE001
            logging.exception("Failed to update in-memory library_svg_images cache.")

        # 3. Refresh every existing instance of this symbol on the current display.
        refreshed = 0
        for elem in list(self.canvas_elements.values()):
            if (isinstance(elem, ProcessControlLibraryElement)
                    and getattr(elem, 'library_id', None) == library_id
                    and getattr(elem, 'hmi_symbol', None) == symbol_name):
                try:
                    self.__update_element_anchors(elem, symbol_name, library_id)
                    refreshed += 1
                except Exception:  # noqa: BLE001
                    logging.exception(
                        "Failed to refresh anchors on element '%s'.",
                        getattr(elem, 'name', '?'),
                    )
        logging.info(
            "Anchor override applied for %s::%s (%d instance(s) refreshed on '%s').",
            library_id, symbol_name, refreshed,
            self.get_display_name() if hasattr(self, 'get_display_name') else '?',
        )


    def on_symbol_selected(self, symbol_name, symbol_xml):

        gfx_file_editor = self.gfx_file_editor

        self.update_hmi_symbol(self.selected_elements[0], symbol_name, symbol_xml, gfx_file_editor)

    def update_hmi_symbol(self, element, symbol_name, symbol_xml, gfx_file_editor):
        element.hmi_symbol = symbol_name
        library_id = element.library_id
        if symbol_name in self.__cached_images[library_id]:
            image = self.__cached_images[library_id][symbol_name]['Image']
            width = self.__cached_images[library_id][symbol_name]['Width']
            height = self.__cached_images[library_id][symbol_name]['Height']
        else:
            svg = gfx_file_editor.library_svg_images[library_id][symbol_name][0]
            width = gfx_file_editor.library_svg_images[library_id][symbol_name][1][0] 
            height = gfx_file_editor.library_svg_images[library_id][symbol_name][1][1]

            image = self.__create_canvas_image_from_svg(svg)
            if symbol_name not in self.__cached_images[library_id]:
                data = {'Image': image, 'Width': width, 'Height': height}
                self.__cached_images[library_id][symbol_name] = data

        self.__update_element_anchors(element, symbol_name, library_id)
            
        element.set_image(image)
        element.update_width_height(width, height, self.imscale)
        gfx_file_editor.get_object_xml_symbol(element.name, symbol_xml)

        self.update_lines(element)



    def __update_element_anchors(self, element, symbol_name, library_id):

        anchors = self.gfx_file_editor.library_svg_images[library_id][symbol_name][2]

        top_anchors = [[anc[0],anc[1],AnchorType.MATERIAL,None] for anc in anchors[AnchorDirection.TOP]]
        bottom_anchors = [[anc[0],anc[1],AnchorType.MATERIAL,None] for anc in anchors[AnchorDirection.BOTTOM]]
        left_anchors = [[anc[0],anc[1],AnchorType.MATERIAL,None] for anc in anchors[AnchorDirection.LEFT]]
        right_anchors = [[anc[0],anc[1],AnchorType.MATERIAL,None] for anc in anchors[AnchorDirection.RIGHT]]

        lines = [[line_id, (start_anchor, end_anchor), start_element, end_element] 
                 for line_id, (start_anchor, end_anchor), start_element, end_element in self.lines.values() 
                 if element in [start_element, end_element]]
        
        # Lines whose anchor on this element is already dead carry no direction, so
        # set_anchors can only pick an arbitrary replacement; re-resolve them below.
        undirected = {line_id for line_id, (start_anchor, end_anchor), start_element, _ in lines
                      if not self.__anchor_resolves(start_anchor if start_element == element else end_anchor, element)}

        new_connections = element.set_anchors(top_anchors, bottom_anchors, left_anchors, right_anchors, lines, self.imscale)

        self.setup_anchor_bindings(element)

        for line_id, (start_anchor, end_anchor), start_element, end_element in new_connections:
            self.canvas.delete(line_id)
            self.canvas.delete('handle_' + str(line_id))
            
            if line_id in undirected:
                if start_element == element:
                    start_anchor, _ = self._find_best_anchor(element, end_element)
                else:
                    end_anchor, _ = self._find_best_anchor(element, start_element)
            
            # Remove the line from the lines dictionary and create a new line
            del self.lines[line_id]
            was_material_fallback = line_id in self.material_fallback_lines
            self.material_fallback_lines.discard(line_id)
            if line_id in self.material_lines:
                del self.material_lines[line_id]
                self.__create_material_line(start_anchor, end_anchor, start_element, end_element, True)
            elif line_id in self.signal_lines:
                del self.signal_lines[line_id]
                if was_material_fallback:
                    # The new anchors may make a real material line possible now.
                    self.__create_material_line(start_anchor, end_anchor, start_element, end_element, True)
                else:
                    self.__create_signal_line(start_anchor, end_anchor, start_element, end_element)
            




    def connect_element(self):
        print("connect_element")

    def create_signal_line(self):
        """Create a signal line between two selected elements"""
        if len(self.selected_elements) == 2:
            # Get the two selected elements
            element1 = self.selected_elements[0]
            element2 = self.selected_elements[1]
            
            # Find the best anchor points to connect from each element
            self.__create_signal_line(None, None, element1, element2)

    def __create_signal_line(self, anchor1=None, anchor2=None, element1=None, element2=None, material_fallback=False):
        
        if self.__connection_already_exists(anchor1, anchor2, element1, element2):
            logging.warning("Signal line already exists between these elements.")
            return
        
        if not anchor1 or anchor1 == 'border':
            anchor1, anchor_pos1 = self._find_best_anchor(element1, element2)
        else: 
            anchor_pos1 = element1.get_anchor_position(anchor1)
            if anchor_pos1 is None:
                anchor1, anchor_pos1 = self._find_best_anchor(element1, element2)
        
        if not anchor2 or anchor2 == 'border':
            anchor2, anchor_pos2 = self._find_best_anchor(element2, element1)
        else:
            anchor_pos2 = element2.get_anchor_position(anchor2)
            if anchor_pos2 is None:
                anchor2, anchor_pos2 = self._find_best_anchor(element2, element1)

        if anchor_pos1 is None or anchor_pos2 is None:
            logging.warning(f"Cannot draw signal line between "
                            f"'{getattr(element1, 'name', element1)}' and "
                            f"'{getattr(element2, 'name', element2)}': no anchor position available.")
            return

            # Create the signal line with appropriate style
        line_id = self.canvas.create_line(
                anchor_pos1[0], anchor_pos1[1], 
                anchor_pos2[0], anchor_pos2[1],
                fill=self.signal_line_color,
                width=int(self.signal_line_width * self.imscale),
                dash=self.signal_line_dash,
                tags=('signal_line', 'line', 'not_grid')
            )
            
            # Calculate proper path
        start_type = anchor_pos1[2]
        end_type = anchor_pos2[2]
        coords = self.calculate_elbow(
                [anchor_pos1[0], anchor_pos1[1]], start_type,
                [anchor_pos2[0], anchor_pos2[1]], end_type,
                element1, element2
            )
            
            # Update line with correct path
        self.canvas.coords(line_id, coords)
            
            # Store line information
        self.lines[line_id] = (line_id, (anchor1, anchor2), element1, element2)
        self.signal_lines[line_id] = (line_id, (anchor1, anchor2), element1, element2)
        if material_fallback:
            self.material_fallback_lines.add(line_id)
            
            # Add event bindings
        self.canvas.tag_bind(line_id, '<Enter>', self.__highlight_line)
        self.canvas.tag_bind(line_id, '<Leave>', self.__unhighlight_line)
        self.canvas.tag_bind(line_id, '<ButtonRelease-1>', self.__select_line)
        self.canvas.tag_bind(line_id, '<ButtonRelease-3>', lambda e, elem=line_id: self.element_right_click(e, elem))
            
            # Set up draggable segments
        self.setup_line_segment_dragging(line_id)
            
            # Record action for undo
        self.undo_manager.add_action('add_signal_line', {
                'line_id': line_id,
                'start_anchor': anchor1,
                'end_anchor': anchor2,
                'start_element': element1,
                'end_element': element2
            })
            
            # Check for line crossings and break lines if necessary
        self.detect_and_break_line_crossings()

    def _find_best_anchor(self, from_element, to_element):
        """Find the best anchor point on from_element to connect to to_element"""
        # Get all anchors from the element
        anchors = []
        if isinstance(from_element, ProcessControlElement):
            for anchor in from_element.get_all_anchors():
                if anchor:
                    pos = from_element.get_anchor_position(anchor)
                    if pos:
                        anchors.append((anchor, pos))
        
        # Get the center point of the target element
        target_x = to_element.x + to_element.width / 2 * self.imscale
        target_y = to_element.y + to_element.height / 2 * self.imscale

        # Find the anchor that is closest to the target element
        best_anchor = None
        best_pos = None
        min_distance = float('inf')
        
        for anchor, pos in anchors:
            x, y, _ = pos
            distance = ((x - target_x) ** 2 + (y - target_y) ** 2) ** 0.5
            if distance < min_distance:
                min_distance = distance
                best_anchor = anchor
                best_pos = pos


        # if no anchor is found, use the border of the element
        if not best_anchor:
            # Library symbols carry a tighter art bounding box than the element itself.
            bbox = None
            library_id = getattr(from_element, 'library_id', None)
            hmi_symbol = getattr(from_element, 'hmi_symbol', None)
            if library_id is not None and hmi_symbol is not None:
                hmi_symbols = self.gfx_file_editor.library_svg_images.get(library_id, {})
                if hmi_symbol in hmi_symbols:
                    bbox = hmi_symbols[hmi_symbol][3]

            if bbox is None:
                bbox = (0, 0, from_element.width, from_element.height)

            x, y, width, height = bbox
            x0 = from_element.x + x
            y0 = from_element.y + y
            x1 = x0 + width * self.imscale
            y1 = y0 + height * self.imscale

            near_x = max(x0, min(target_x, x1))
            near_y = max(y0, min(target_y, y1)) 

            # Determine the anchor direction based on the closest border
            if near_x == x0 and near_y != y0 and near_y != y1:
                anchor_direction = LEFT_ANCHOR
            elif near_x == x1 and near_y != y0 and near_y != y1:
                anchor_direction = RIGHT_ANCHOR
            elif near_y == y0:
                anchor_direction = TOP_ANCHOR
            else:
                anchor_direction = BOTTOM_ANCHOR
                

            best_anchor = 'border'
            best_pos = (near_x, near_y, anchor_direction)

        
        return best_anchor, best_pos


    def delete_item(self):
        if self.selected_elements:
            # Remove all selected elements
            for element in self.selected_elements:
                # Collect line data for undo
                connected_lines = []
                for line_id, (line, (start_anchor, end_anchor), start_element, end_element) in list(self.lines.items()):
                    if start_element == element or end_element == element:
                        connected_lines.append({
                            'id': line_id,
                            'start_anchor': start_anchor,
                            'end_anchor': end_anchor,
                            'start_element': start_element,
                            'end_element': end_element
                        })

                # Remove the element from the gfx file editor's element_map so it
                # doesn't get re-created on the next display reload / save. Capture
                # the removed entry so undo can restore it.
                gfx_reference = getattr(element, 'gfx_reference', None)
                gfx_map_item = None
                if gfx_reference and self.gfx_file_editor is not None \
                        and gfx_reference in self.gfx_file_editor.element_map:
                    gfx_map_item = self.gfx_file_editor.element_map.pop(gfx_reference)

                # Record action for undo
                self.undo_manager.add_action('delete_element', {
                    'element': element,
                    'x': element.x,
                    'y': element.y,
                    'lines': connected_lines,
                    'gfx_reference': gfx_reference,
                    'gfx_map_item': gfx_map_item
                })
                # Remove all connected lines
                for line_id, (line, (start_anchor, end_anchor), start_element, end_element) in list(self.lines.items()):
                    if start_element == element or end_element == element:
                        self.canvas.delete(line_id)
                        del self.lines[line_id]
                
                # Remove the element from the elements list
                if element in self.canvas_elements.values():
                    element_id = element.id
                    self.canvas_elements.pop(element_id, None)

                # Delete the element's canvas items
                element.delete()
            
            self.selected_elements = []
            self.__selection_callback()
            self.selected_element = None
            self.select_element_id = None
        
        elif self.selected_line_id:
            # Get line data for undo
            line_id = self.selected_line_id[0]
            if line_id in self.lines:
                line, anchors, start_element, end_element = self.lines[line_id]
                
                # Record action for undo
                self.undo_manager.add_action('delete_line', {
                    'line_id': line_id,
                    'start_anchor': anchors[0],
                    'end_anchor': anchors[1],
                    'start_element': start_element,
                    'end_element': end_element
                })

                # Delete the selected line
                self.canvas.delete(line_id)
                self.canvas.delete('handle_' + str(line_id))
                # Remove the line from the lines dictionary
                del self.lines[line_id]
                if line_id in self.material_lines:
                    del self.material_lines[line_id]
                elif line_id in self.signal_lines:
                    del self.signal_lines[line_id]
                self.material_fallback_lines.discard(line_id)
                self.selected_line_id = None

        self.detect_and_break_line_crossings()

    def __delete_canvas(self):
        """Remove the busy indicator"""
        if self.canvas:
            self.__clear_element_selection()
            self.canvas.delete('all')  # Clear all items from the canvas
            self.canvas.grid_forget()
            try:
                self.canvas.destroy()
            except Exception as e:
                pass
            self.canvas = None

    def __create_canvas(self):
        """ Set up the canvas and scrollbars """
        self.__delete_canvas()  # remove previous canvas if exists
        
        # Create the properties bar
        self.properties_bar = PropertiesBar(self, self)

        # Vertical and horizontal scrollbars for canvas
        self.hbar = AutoScrollbar(self, orient='horizontal')
        self.vbar = AutoScrollbar(self, orient='vertical')
        self.hbar.grid(row=1, column=0, sticky='we')
        self.vbar.grid(row=0, column=1, sticky='ns')

        # Create canvas and bind it with scrollbars. Public for outer classes
        self.canvas: tk.Canvas = tk.Canvas(self, highlightthickness=0, yscrollcommand=self.vbar.set,
                                xscrollcommand=self.hbar.set, bg='#E0E0E0')
        self.canvas.grid(row=0, column=0, sticky='nswe')

        # Configure grid row/column weights (important for proper resizing)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)  
        self.grid_rowconfigure(2, weight=0)  # Properties bar
        self.grid_columnconfigure(0, weight=1)
        

        # Bind scrollbars to the canvas
        self.hbar.configure(command=self.__scroll_x)  # bind scrollbars to the canvas
        self.vbar.configure(command=self.__scroll_y)
        # Pack properties bar at the bottom
        self.properties_bar.grid(row=2, column=0, columnspan=2, sticky='ew')
        self.properties_bar.grid_remove()

        # Bind events to the Canvas
        self.canvas.bind('<Configure>', self.__redraw)  # Canvas is resized
        self.canvas.bind('<MouseWheel>', self.__vertical_scroll)
        self.canvas.bind('<Shift-MouseWheel>', self.__horizontal_scroll)
        self.canvas.bind('<ButtonPress-3>', self.__move_from)  # Remember canvas position
        self.canvas.bind('<B3-Motion>', self.__move_to)  # Move canvas to the new position
        self.canvas.bind('<B1-Motion>', self.__on_motion)  # Drag element
        self.canvas.bind('<Control-MouseWheel>', self.__zoom)  # zoom for Windows and MacOS, but not Linux
        self.canvas.bind('<ButtonPress-1>', self.__on_click)
        self.canvas.bind('<ButtonRelease-1>', self.__on_release)  # release mouse button
        self.canvas.bind('<ButtonRelease-3>', self.popup)  # call popup menu

        # Add Ctrl+Z binding for undo
        self.canvas.bind('<Control-z>', self.undo)
        self.canvas.bind('<Control-Z>', self.undo)
        
        # Add Ctrl+Y and Ctrl+Shift+Z bindings for redo
        self.canvas.bind('<Control-y>', self.redo)
        self.canvas.bind('<Control-Y>', self.redo)
        self.canvas.bind('<Control-Shift-z>', self.redo)
        self.canvas.bind('<Control-Shift-Z>', self.redo)

        # Add Ctrl+T binding for showing/hiding object names
        self.canvas.bind('<Control-t>', self.show_or_hide_object_names)
        self.canvas.bind('<Control-T>', self.show_or_hide_object_names)


        # Bind arrow keys for navigation
        self.canvas.bind('<Up>', self.move_selection_up)
        self.canvas.bind('<Down>', self.move_selection_down)
        self.canvas.bind('<Left>', self.move_selection_left)
        self.canvas.bind('<Right>', self.move_selection_right)

        def focus_on_canvas(event):
            # Never pull focus away from a dialog opened on top of us - on
            # Windows that also raises this window over the dialog.
            focused = self.canvas.focus_displayof()
            if focused is not None and focused.winfo_toplevel() is not self.canvas.winfo_toplevel():
                return
            self.canvas.focus_set()

        self.canvas.bind("<Enter>", focus_on_canvas)

        # Set the scrollregion (initially no scroll region)
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

        # Put image into container rectangle and use it to set proper coordinates to the image
        self.grid_reference = self.canvas.create_rectangle((0, 0, 1, 1), width=0, tags='not_grid')

        self.create_rectangle_with_shadow(1920, 1080)

        self.container = self.canvas.create_rectangle((0,0, 1920, 1080), width=0, fill='#C0C0C0', tags=('not_grid','background'))
        
        self.__redraw_drop_shadow()  # show image on the canvas

        self.banner_handler.draw(self.canvas, self.vbar)
        

    def move_selection_up(self, _):
        """ Move selected elements up by 1 pixel """
        self.__recode_moves_for_undo()
        if self.selected_elements:
            for element in self.selected_elements:
                element.move(0, -1)
                element.original_x = element.x
                element.original_y = element.y
                self.update_lines(element)
            self.__selection_callback(len(self.selected_elements))


    def move_selection_down(self, _):
        """ Move selected elements down by 1 pixel """
        self.__recode_moves_for_undo()
        if self.selected_elements:
            for element in self.selected_elements:
                element.move(0, 1)
                element.original_x = element.x
                element.original_y = element.y
                self.update_lines(element)
            self.__selection_callback(len(self.selected_elements))


    def move_selection_left(self, _):
        """ Move selected elements left by 1 pixel """
        self.__recode_moves_for_undo()
        if self.selected_elements:
            for element in self.selected_elements:
                element.move(-1 , 0)
                element.original_x = element.x
                element.original_y = element.y
                self.update_lines(element)
            self.__selection_callback(len(self.selected_elements))
    

    def move_selection_right(self, _):
        """ Move selected elements right by 1 pixel """
        self.__recode_moves_for_undo()
        if self.selected_elements:
            for element in self.selected_elements:
                element.move(1, 0)
                element.original_x = element.x
                element.original_y = element.y
                self.update_lines(element)
            self.__selection_callback(len(self.selected_elements))


    def __on_motion(self, event):
        if self.selection_image:
            curX, curY = ( self.canvas.canvasx(event.x),  self.canvas.canvasy(event.y))
            self.draw_selection_rectangle(self.start_rect_selection_x,self.start_rect_selection_y,curX,curY)

    
    def __on_release(self, event):

        if not self.selection_image or self.selection_image.height() == 1 or self.selection_image.width() == 1:
            self.selection_image = None 
            self.start_rect_selection_x = None
            self.start_rect_selection_y = None
            return 
        
        self.canvas.delete('selection_rectangle') 
        
        
        if hasattr(self, 'start_rect_selection_x'):
            curX, curY = (self.canvas.canvasx(event.x),  self.canvas.canvasy(event.y))
            if abs(curX - self.start_rect_selection_x) <= 5 and abs(curY - self.start_rect_selection_y) <= 5:
                return
            enclosed_ids  = self.canvas.find_enclosed(self.start_rect_selection_x, self.start_rect_selection_y,
                                                curX, curY)
        

            for id in enclosed_ids:
                if id not in self.canvas_elements:
                    continue
                element = self.canvas_elements[id]
                if element not in self.selected_elements:
                    self.selected_elements.append(element)
                    element.select_element(True)
                else:
                    self.selected_elements.remove(element)
                    element.select_element(False)

        self.selection_image = None 
        self.start_rect_selection_x = None
        self.start_rect_selection_y = None
        self.show_or_hide_properties_bar()
        self.__selection_callback(len(self.selected_elements))

    
    def show_or_hide_object_names(self, _=None):
        """ Toggle visibility of object names on the canvas """
        self.show_object_names = not self.show_object_names
        self.canvas.itemconfig('object_name', state='normal' if self.show_object_names else 'hidden')
        self.canvas.itemconfig('anchor_image', state='normal' if self.show_object_names else 'hidden')


    def redo(self, _=None):
        """Redo the previously undone action"""
        if self.undo_manager.can_redo():
            self.undo_manager.redo()
            # Update the display
            self.detect_and_break_line_crossings()

    def undo(self, _=None):
        """Undo the last action"""
        if self.undo_manager.can_undo():
            self.undo_manager.undo()
            # Update the display
            self.detect_and_break_line_crossings()


    def draw_selection_rectangle(self, x1, y1, x2, y2):
        """ Draw selection rectangle """
        image = Image.new('RGBA', (int(abs(x2-x1)), int(abs(y2-y1))), (0,120,215,128))
        drawing = ImageDraw.Draw(image)
        x = abs(x1-x2) - 1 if abs(x1-x2) >= 1 else 0 # Prevent negative width
        y = abs(y1-y2) - 1 if abs(y1-y2) >= 1 else 0 # Prevent negative height
        drawing.rectangle([0, 0, x, y], fill=None, outline=(0,120,215,255), width=1)
        self.selection_image = ImageTk.PhotoImage(image)
        if hasattr(self, 'selection_rect') and self.selection_rect:
            self.canvas.delete(self.selection_rect)
        self.selection_rect = self.canvas.create_image(x1 if x1 < x2 else x2, y1 if y1 < y2 else y2
                                                       , image=self.selection_image, anchor='nw'
                                                       , tags='selection_rectangle')
        

    def create_rectangle_with_shadow(self, width, height, 
                                        shadow_color=(132, 132, 132, 128), 
                                        shadow_offset=(0, 0), 
                                        shadow_blur=5):
        """
        Create an image of a rectangle with a drop shadow.
        
        Parameters:
        - width: Width of the rectangle
        - height: Height of the rectangle
        - rectangle_color: Color of the rectangle (RGB tuple)
        - shadow_color: Color of the shadow (RGBA tuple)
        - shadow_offset: Offset of the shadow (x, y) from the rectangle
        - shadow_blur: Blur radius for the shadow
        
        Returns:
        - PIL.ImageTk.PhotoImage: The generated image
        """
        # Create a transparent image with extra space for the shadow
        padding = max(shadow_offset[0] + shadow_blur * 2, shadow_offset[1] + shadow_blur * 2)
        total_width = width + padding * 2
        total_height = height + padding * 2
        
        # Create a transparent image
        image = Image.new('RGBA', (total_width, total_height), (0, 0, 0, 0))
        
        # Draw the shadow (a rectangle offset from the main rectangle)
        shadow_pos = (
            padding + shadow_offset[0],
            padding + shadow_offset[1],
            padding + width + shadow_offset[0],
            padding + height + shadow_offset[1]
        )
        shadow = Image.new('RGBA', image.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rectangle(shadow_pos, fill=shadow_color)
        
        # Apply blur to the shadow
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=shadow_blur))
        
        # Composite the shadow onto the main image
        image = Image.alpha_composite(image, shadow)

        self.background_image = image
        self.background_offset = (padding, padding)

        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS  # suppress DecompressionBombError for big image
        with warnings.catch_warnings():  # suppress DecompressionBombWarning for big image
            warnings.simplefilter('ignore')
        self.imwidth, self.imheight = self.background_image.size  # public for outer classes
        
        self.__min_side = min(self.imwidth, self.imheight)  # get the smaller image side
        # Create image pyramid
        self.__pyramid = [self.smaller()] if self.__huge else [self.background_image]
        # Set ratio coefficient for image pyramid
        self.__ratio = max(self.imwidth, self.imheight) / self.__huge_size if self.__huge else 1.0
        self.__curr_img = 0  # current image from the pyramid
        self.zoom_scale = self.imscale * self.__ratio  # image pyramide scale
        self.__reduction = 2  # reduction degree of image pyramid
        (w, h), m, j = self.__pyramid[-1].size, 512, 0
        n = math.ceil(math.log(min(w, h) / m, self.__reduction)) + 1  # image pyramid length
        while w > m and h > m:  # top pyramid image is around 512 pixels in size
            j += 1
            print('\rCreating image pyramid: {j} from {n}'.format(j=j, n=n), end='')
            w /= self.__reduction  # divide on reduction degree
            h /= self.__reduction  # divide on reduction degree
            self.__pyramid.append(self.__pyramid[-1].resize((int(w), int(h)), self.__filter))
        print('\r' + (40 * ' ') + '\r', end='')  # hide printed string

    def smaller(self):
        """ Resize image proportionally and return smaller image """
        w1, h1 = float(self.imwidth), float(self.imheight)
        w2, h2 = float(self.__huge_size), float(self.__huge_size)
        aspect_ratio1 = w1 / h1
        aspect_ratio2 = w2 / h2  # it equals to 1.0
        if aspect_ratio1 == aspect_ratio2:
            image = Image.new('RGB', (int(w2), int(h2)))
            k = h2 / h1  # compression ratio
            w = int(w2)  # band length
        elif aspect_ratio1 > aspect_ratio2:
            image = Image.new('RGB', (int(w2), int(w2 / aspect_ratio1)))
            k = h2 / w1  # compression ratio
            w = int(w2)  # band length
        else:  # aspect_ratio1 < aspect_ration2
            image = Image.new('RGB', (int(h2 * aspect_ratio1), int(h2)))
            k = h2 / h1  # compression ratio
            w = int(h2 * aspect_ratio1)  # band length
        i, j, n = 0, 0, math.ceil(self.imheight / self.__band_width)
        while i < self.imheight:
            j += 1
            print('\rOpening image: {j} from {n}'.format(j=j, n=n), end='')
            band = min(self.__band_width, self.imheight - i)  # width of the tile band
            self.__tile[1][3] = band  # set band width
            self.__tile[2] = self.__offset + self.imwidth * i * 3  # tile offset (3 bytes per pixel)
            self.image.close()
            self.image = Image.open(self.doc[self.pno])  # reopen / reset image
            self.image.size = (self.imwidth, band)  # set size of the tile band
            self.image.tile = [self.__tile]  # set tile
            cropped = self.image.crop((0, 0, self.imwidth, band))  # crop tile band
            image.paste(cropped.resize((w, int(band * k)+1), self.__filter), (0, int(i * k)))
            i += band
        print('\r' + (40 * ' ') + '\r', end='')  # hide printed string
        return image


    def __redraw_drop_shadow(self):
        """ Show image on the Canvas. Implements correct image zoom almost like in Google Maps """
        box_image = self.canvas.coords(self.container)  # get image area
        box_image = (box_image[0] - self.background_offset[0] * self.imscale,  # get image area
                    box_image[1] - self.background_offset[1] * self.imscale,
                    box_image[2] + self.background_offset[0] * self.imscale,
                    box_image[3] + self.background_offset[1] * self.imscale)
        box_canvas = (self.canvas.canvasx(0),  # get visible area of the canvas
                      self.canvas.canvasy(0),
                      self.canvas.canvasx(self.canvas.winfo_width()),
                      self.canvas.canvasy(self.canvas.winfo_height()))
        box_img_int = tuple(map(int, box_image))  # convert to integer or it will not work properly
        # Get scroll region box
        box_scroll = [min(box_img_int[0], box_canvas[0]), min(box_img_int[1], box_canvas[1]),
                      max(box_img_int[2], box_canvas[2]), max(box_img_int[3], box_canvas[3])]
        # Horizontal part of the image is in the visible area
        if  box_scroll[0] == box_canvas[0] and box_scroll[2] == box_canvas[2]:
            box_scroll[0]  = box_img_int[0]
            box_scroll[2]  = box_img_int[2]
        # Vertical part of the image is in the visible area
        if  box_scroll[1] == box_canvas[1] and box_scroll[3] == box_canvas[3]:
            box_scroll[1]  = box_img_int[1]
            box_scroll[3]  = box_img_int[3]
            self.__showing_vertical_scroll = False
        else:
            self.__showing_vertical_scroll = True
        # Convert scroll region to tuple and to integer
        self.canvas.configure(scrollregion=tuple(map(int, box_scroll)))  # set scroll region
        x1 = max(box_canvas[0] - box_image[0], 0)  # get coordinates (x1,y1,x2,y2) of the image tile
        y1 = max(box_canvas[1] - box_image[1], 0)
        x2 = min(box_canvas[2], box_image[2]) - box_image[0]
        y2 = min(box_canvas[3], box_image[3]) - box_image[1]
        if int(x2 - x1) > 0 and int(y2 - y1) > 0:  # show image if it in the visible area
            if self.__huge and self.__curr_img < 0:  # show huge image, which does not fit in RAM
                h = int((y2 - y1) / self.imscale)  # height of the tile band
                self.__tile[1][3] = h  # set the tile band height
                self.__tile[2] = self.__offset + self.imwidth * int(y1 / self.imscale) * 3
                self.background_image.size = (self.imwidth, h)  # set size of the tile band
                self.background_image.tile = [self.__tile]
                image = self.background_image.crop((int(x1 / self.imscale), 0, int(x2 / self.imscale), h))
            else:  # show normal image
                self.__pyramid = [self.smaller()] if self.__huge else [self.background_image]
                image = self.__pyramid[max(0, self.__curr_img)].crop(  # crop current img from pyramid
                                    (int(x1 / self.zoom_scale), int(y1 / self.zoom_scale),
                                    int(x2 / self.zoom_scale), int(y2 / self.zoom_scale)))
            self.canvas_image = image.resize((int(x2 - x1), int(y2 - y1)), self.__filter)
            
            imagetk = ImageTk.PhotoImage(self.canvas_image)
            imageid = self.canvas.create_image(max(box_canvas[0], box_img_int[0]),
                                               max(box_canvas[1], box_img_int[1]),
                                               anchor='nw', image=imagetk)
            self.canvas.lower(imageid)  # set image into background
            self.canvas.imagetk = imagetk  # keep an extra reference to prevent garbage-collection
    
    def __on_click(self, event):
        current = self.canvas.find_withtag("current")  # Finds the item that is currently under the cursor
        tags = self.canvas.gettags(current)
        is_shift_pressed = event.state & 0x0001  # Check if Shift is pressed

        
        if self.current_tool_mode == 'select':
            # If we're not clicking on an element and shift is not pressed, clear selection
            if (not current or 'background' in tags) and not is_shift_pressed:
                self.__clear_element_selection()

                # Create a selection rectangle
                x = self.canvas.canvasx(event.x)
                y = self.canvas.canvasy(event.y)
                
                self.start_rect_selection_x =  x
                self.start_rect_selection_y =  y
                self.draw_selection_rectangle(x, y, x+1, y+1)

            self.__line_selection(current, tags)


        if self.current_tool_mode != "select":
            self.__clear_element_selection()
            self.__clear_line_selection()

        if self.current_tool_mode == "free_anchor" and 'background' in tags:
            # Get canvas coordinates (accounting for zoom and pan)
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)

            # Create a new anchor at this position
            self._create_free_anchor(canvas_x, canvas_y)
            return

    def __clear_element_selection(self):
        for elem in self.selected_elements:
            elem.select_element(False)
        self.selected_elements = []
        self.__selection_callback()
        self.selected_element = None
        self.select_element_id = None
        if self.highlighted_anchor is not None:
            self.highlighted_anchor = None
            self.canvas.itemconfig('anchor', fill='')
        self.show_or_hide_properties_bar()


    def __line_selection(self, current, tags):

        self.__clear_line_selection(current)

        if 'line' in tags:
            self.selected_line_id = current
            self.canvas.itemconfig(self.selected_line_id, fill=HIGHLIGHTING_COLOR)


    def __clear_line_selection(self, current=None):
        if current != self.selected_line_id and self.selected_line_id:
            line_tags = self.canvas.gettags(self.selected_line_id)
            if 'signal_line' in line_tags:
                self.canvas.itemconfig(self.selected_line_id, fill=self.signal_line_color)
            else:
                self.canvas.itemconfig(self.selected_line_id, fill=DRAWING_DEFAULT_COLOR)
            self.canvas.itemconfig(f'handle_{self.selected_line_id}', fill='')
            self.selected_line_id = None
        

        
     
    def antialias_args(self, args, winc=0.5, cw=2):
        nargs = {}
        
        # Set defaults
        nargs['width'] = 1
        nargs['fill'] = "#000"

        # Get original args
        for arg in args:
            nargs[arg] = args[arg]
        if nargs['width'] == 0:
            nargs['width'] = 1

        # Calculate width
        nargs['width'] += winc

        cbg = self.winfo_rgb(self.canvas.cget("bg"))   
        cfg = list(self.winfo_rgb(nargs['fill']))
        cfg[0] = (cfg[0] + cbg[0]*cw)/(cw+1)
        cfg[1] = (cfg[1] + cbg[1]*cw)/(cw+1)
        cfg[2] = (cfg[2] + cbg[2]*cw)/(cw+1)
        nargs['fill'] = '#%02x%02x%02x' % (cfg[0]/256, cfg[1]/256, cfg[2]/256)

        return nargs

    def add_element(self, element):
        """ Add a new element to the canvas and set up event bindings """
        element.draw(self.canvas, self.imscale)
        self.canvas_elements[element.id] = element
        self.setup_element_bindings(element)

        # Record action for undo
        self.undo_manager.add_action('add_element', {'element': element})

    def __create_elements(self):
        # Create images for each element type
        self.__cached_images = {}
        self.canvas_elements = {}

        self.__pdf_path = ""
        self.__pdf_pno = -1
        gfx_file_editor = self.gfx_file_editor
        # Iterate over a snapshot: entries whose canvas element cannot be
        # created are pruned from element_map below so their placeholder XML
        # never leaks into the exported display.
        # Static graphics ('Image') are drawn first so control modules stack on top of them.
        ordered_elements = sorted(gfx_file_editor.element_map.items(),
                                  key=lambda item: 0 if item[1].catalog_number == 'Image' else 1)
        for element_name, element in ordered_elements:
            library_id = element.library_id
            hmi_symbol = element.hmi_symbol
            _control_module = self.__internal_db.get_control_module(element_name)
            _hmi_display = self.__internal_db.get_hmi_display(element.spa_id)
            if _control_module:
                self.__pdf_path = _control_module['path']
                self.__pdf_pno = _control_module['pno']
                element.spa_id = _control_module['id']
            elif _hmi_display:
                self.__pdf_path = _hmi_display['path']
                self.__pdf_pno = _hmi_display['pno']
                element.spa_id = _hmi_display['id']
            if _control_module and 'primary_linked_graphic' in _control_module:
                roi_uid = _control_module['primary_linked_graphic']['roi_uid']
            else:
                roi_uid =  None
            if element.catalog_number == 'Image':
                canvas_element = self.create_static_graphic_canvas_element(element_name, element)
                if canvas_element is None:
                    # Drop this entry so export_display doesn't emit XML that
                    # still contains unresolved {WidthFinal}/{HeightFinal}/
                    # {LeftFinal}/{TopFinal} placeholders (FTView SE would
                    # reject the display on import).
                    gfx_file_editor.element_map.pop(element_name, None)
                    logging.warning(
                        f"Dropping static graphic '{element_name}' from display "
                        f"'{gfx_file_editor.display_name}' — its canvas element "
                        f"could not be built, so its XML would contain unresolved "
                        f"template placeholders."
                    )
                    continue
            elif hmi_symbol is not None:
                svg = gfx_file_editor.library_svg_images[library_id][hmi_symbol][0]
                width = gfx_file_editor.library_svg_images[library_id][hmi_symbol][1][0] 
                height = gfx_file_editor.library_svg_images[library_id][hmi_symbol][1][1]
                anchors = gfx_file_editor.library_svg_images[library_id][hmi_symbol][2]
                if library_id not in self.__cached_images:
                    self.__cached_images[library_id] = {}
                if hmi_symbol not in self.__cached_images[library_id]:
                    data = {'Image': self.__create_canvas_image_from_svg(svg),
                            'Width': width, 'Height': height}

                    self.__cached_images[library_id][hmi_symbol] = data
                
                image = self.__cached_images[element.library_id][element.hmi_symbol]['Image']

                bbox = self.canvas.coords(self.container)
                x = element.Cfg_PositionX * self.imscale + bbox[0] # get real (x,y) on the image without zoom
                y = element.Cfg_PositionY * self.imscale + bbox[1]

                top_anchors = [[anc[0],anc[1],AnchorType.MATERIAL,None] for anc in anchors[AnchorDirection.TOP]]
                bottom_anchors = [[anc[0],anc[1],AnchorType.MATERIAL,None] for anc in anchors[AnchorDirection.BOTTOM]]
                left_anchors = [[anc[0],anc[1],AnchorType.MATERIAL,None] for anc in anchors[AnchorDirection.LEFT]]
                right_anchors = [[anc[0],anc[1],AnchorType.MATERIAL,None] for anc in anchors[AnchorDirection.RIGHT]]

                canvas_element = ProcessControlLibraryElement(x, y
                                                    ,width,height,image,element_name,self.font, catalog_number=element.catalog_number
                                                    ,library_id=element.library_id,hmi_symbol=element.hmi_symbol
                                                    ,top_anchors=top_anchors, bottom_anchors=bottom_anchors
                                                    ,left_anchors=left_anchors, right_anchors=right_anchors
                                                    ,spa_id=element.spa_id, spa_name=element_name, gfx_reference=element_name
                                                    ,path=self.__pdf_path, pno=self.__pdf_pno, roi_uid=roi_uid)
                
            self.add_element(canvas_element)


        self.__internal_db.subscribe_to_element_updates_on_hmi_display(self.element_updated, self.__pdf_path, self.__pdf_pno)



    def create_static_graphic_canvas_element(self, element_name, element):
        static_graphic = self.__internal_db.get_static_graphic_by_id(element.spa_id)
        if not static_graphic:
            logging.warning(f"Static graphic with SPA ID {element.spa_id} not found in the database.")
            return None
        name = static_graphic['name']
        svg_path = static_graphic['hmi_graphic']['extract_graphic']['svg_image_path']
        if svg_path is None or not os.path.isfile(svg_path):
            logging.warning(f"SVG file for static graphic '{name}' not found at path: {svg_path}")
            return None
        svg_string = open(svg_path, 'r').read()

        top_anchors = static_graphic['hmi_graphic']['extract_graphic']['top_anchors']
        bottom_anchors = static_graphic['hmi_graphic']['extract_graphic']['bottom_anchors']
        left_anchors = static_graphic['hmi_graphic']['extract_graphic']['left_anchors']
        right_anchors = static_graphic['hmi_graphic']['extract_graphic']['right_anchors']

        if not self.__pdf_path:
            self.__pdf_path = static_graphic['path']
            self.__pdf_pno = static_graphic['pno']

        if static_graphic and 'primary_linked_graphic' in static_graphic:
            roi_uid = static_graphic['primary_linked_graphic']['roi_uid']
        else:
            roi_uid =  None

        top_anchors = [[int(anc['x']),anc['y'],AnchorType.MATERIAL,anc.get('index', i)] for i, anc in enumerate(top_anchors)]
        bottom_anchors = [[int(anc['x']),anc['y'],AnchorType.MATERIAL,anc.get('index', i)] for i, anc in enumerate(bottom_anchors)]
        left_anchors = [[int(anc['x']),anc['y'],AnchorType.MATERIAL,anc.get('index', i)] for i, anc in enumerate(left_anchors)]
        right_anchors = [[int(anc['x']),anc['y'],AnchorType.MATERIAL,anc.get('index', i)] for i, anc in enumerate(right_anchors)]

        bbox = self.canvas.coords(self.container)
        x = element.Cfg_PositionX * self.imscale + bbox[0] # get real (x,y) on the image without zoom
        y = element.Cfg_PositionY * self.imscale + bbox[1]

        canvas_element = ProcessControlStaticGraphicElement(x=x,
                                                    y=y,
                                                    width=element.image_width, height=element.image_height,name=name,
                                                    font=self.font,internal_db=self.__internal_db,svg_string=svg_string,
                                                    top_anchors=top_anchors, bottom_anchors=bottom_anchors,
                                                    left_anchors=left_anchors, right_anchors=right_anchors,
                                                    spa_id=element.spa_id, spa_name=name, gfx_reference=element_name,
                                                    path=self.__pdf_path, pno=self.__pdf_pno, roi_uid=roi_uid)

        return canvas_element


    def destroy(self):
        # Without this the database keeps calling element_updated on a dead widget.
        try:
            self.__internal_db.unsubscribe_to_new_element_on_hmi_display(self.element_updated)
        except Exception:
            logging.exception("Failed to unsubscribe ProcessDisplayCanvas from HMI display updates")
        super().destroy()


    def element_updated(self, elem, spa_type):
        if not self.winfo_exists():
            self.__internal_db.unsubscribe_to_new_element_on_hmi_display(self.element_updated)
            return
        if spa_type == 'static_graphic_deleted':
            self.__remove_canvas_element_from_deletion(elem, ProcessControlStaticGraphicElement)
            return
        if spa_type == 'control_module_deleted':
            self.__remove_canvas_element_from_deletion(elem, ProcessControlLibraryElement)
            return

        quick_build_hmi_page(self.__pdf_path, self.__pdf_pno, self.__acm_data_handler,
                             self.__config, self.__internal_db, self.__project_name)
        logging.info(f"Element {elem['name']} updated in ACM HMI display {self.__pdf_pno}. Rebuilding page.")

        spa_ids_to_elements = {element.spa_id: element for element in self.canvas_elements.values()}

        if elem['id'] in spa_ids_to_elements:
            logging.info(f"SPA ID {elem['id']} corresponds to element {spa_ids_to_elements[elem['id']].name}.")
        else:
            logging.info(f"SPA ID {elem['id']} does not correspond to any element on the canvas.")
            gfx_file_editor = self.gfx_file_editor

            
            objects_df = self.__acm_data_handler.get_all_objects_in_project(force_update=True)

            if spa_type == 'control_module':
                object_row = objects_df.loc[objects_df['Name'] == elem['name']]
                if object_row.empty:
                    return
                
                acm_id = str(object_row.index[0])

            elif spa_type == 'static_graphic':
                parameter_row = self.__acm_data_handler.get_object_id_by_spa_id(elem['id'])
                if parameter_row.size == 0:
                    return
                acm_id = str(parameter_row.index[0])

            else:
                return
            
            row = self.__acm_data_handler.get_display_object(acm_id)
            element = gfx_file_editor.add_acm_element(gfx_file_editor.element_map, acm_id, row)
            canvas_element = self.create_static_graphic_canvas_element(row['Name'], element)

            self.add_element(canvas_element)
            self.__connect_elements()


    def __remove_canvas_element_from_deletion(self, elem, expected_class):
        """Remove a canvas element that was deleted elsewhere (e.g. via its
        tool cell or by deleting its ROI in the document viewer) so the change
        is reflected on this open canvas without requiring a reload.

        Matches by ``spa_id`` first; falls back to ``spa_name`` if no ID
        matches. Cleans up connected lines, the ``gfx_file_editor.element_map``
        entry, and the current selection.
        """
        if not isinstance(elem, dict):
            return
        deleted_spa_id = elem.get('id')
        deleted_spa_name = elem.get('name')

        target_elements = []
        for element in list(self.canvas_elements.values()):
            if not isinstance(element, expected_class):
                continue
            if deleted_spa_id is not None and element.spa_id == deleted_spa_id:
                target_elements.append(element)
            elif deleted_spa_id is None and deleted_spa_name is not None \
                    and getattr(element, 'spa_name', None) == deleted_spa_name:
                target_elements.append(element)

        if not target_elements:
            return

        for element in target_elements:
            # Remove any connected lines
            for line_id, (line, (start_anchor, end_anchor), start_element, end_element) in list(self.lines.items()):
                if start_element == element or end_element == element:
                    self.canvas.delete(line_id)
                    del self.lines[line_id]

            # Remove from gfx_file_editor.element_map so it doesn't come back on
            # save / reload.
            gfx_reference = getattr(element, 'gfx_reference', None)
            if gfx_reference and self.gfx_file_editor is not None \
                    and gfx_reference in self.gfx_file_editor.element_map:
                self.gfx_file_editor.element_map.pop(gfx_reference, None)

            # Remove from canvas_elements dict
            self.canvas_elements.pop(element.id, None)

            # Remove from current selection if present
            if element in self.selected_elements:
                self.selected_elements.remove(element)
            if getattr(self, 'selected_element', None) is element:
                self.selected_element = None

            # Delete the element's canvas items
            element.delete()

        self.__selection_callback()
        logging.info(
            f"Removed {expected_class.__name__} "
            f"(spa_id={deleted_spa_id!r}, name={deleted_spa_name!r}) from canvas "
            f"(deleted from database)."
        )


    def __resize_elements(self):
        """ Resize all elements on the canvas based on the current zoom level """

        gfx_file_editor = self.gfx_file_editor
        resized_images = []

        for canvas_element in self.canvas_elements.values():
            if isinstance(canvas_element, ProcessControlLibraryElement):
                
                library_id = canvas_element.library_id
                symbol_name = canvas_element.hmi_symbol

                if f"{library_id}.{symbol_name}" not in resized_images:
                    svg = gfx_file_editor.library_svg_images[library_id][symbol_name][0]
                    image = self.__create_canvas_image_from_svg(svg)
                    resized_images.append(f"{library_id}.{symbol_name}")
                    self.__cached_images[library_id][symbol_name]['Image'] = image
                else:
                    image = self.__cached_images[library_id][symbol_name]['Image']
                
                canvas_element.set_image(image)

            elif isinstance(canvas_element, ProcessControlStaticGraphicElement):
                canvas_element.zoom_update_image()



    def __create_canvas_image_from_svg(self, svg: str, color=None, return_image=True):
        out = BytesIO()
        byte_image = str.encode(svg.format(hex_color=color))
        render_svg_to_png(byte_image, write_to=out, scale=self.imscale)
        if return_image:
            return ImageTk.PhotoImage(Image.open(out))
        else:
            return Image.open(out)

    def create_smooth_line(self, *args, **kwargs):
        # Add anti-aliasing
        nkwargs = self.antialias_args(kwargs)
        self.canvas.create_line(*args, **nkwargs)
        return self.canvas.create_line(*args, **kwargs)

    def setup_element_bindings(self, element):
        """ Setup mouse event bindings for an element """
        # Binding for the element image
        self.canvas.tag_bind(element.image_id, '<Enter>', lambda e, elem=element: elem.on_hover('image', True))
        self.canvas.tag_bind(element.image_id, '<Leave>', lambda e, elem=element: elem.on_hover('image', False))

        self.setup_anchor_bindings(element)

        # Bind moving elements
        self.canvas.tag_bind(element.image_id, '<Button1-Motion>', lambda e, elem=element: self.move_element(e, elem))
        self.canvas.tag_bind(element.image_id, '<ButtonPress-1>', lambda e, elem=element: self.select_element(e, elem, moving=True))
        self.canvas.tag_bind(element.image_id, '<ButtonRelease-1>', lambda e, elem=element: self.release_element(e, elem))
        self.canvas.tag_bind(element.image_id, '<ButtonRelease-3>', lambda e, elem=element: self.element_right_click(e, elem))
        self.canvas.tag_bind(element.text_id, '<Button1-Motion>', lambda e, elem=element: self.move_element(e, elem))
        self.canvas.tag_bind(element.text_id, '<ButtonPress-1>', lambda e, elem=element: self.select_element(e, elem, moving=True))
        self.canvas.tag_bind(element.text_id, '<ButtonRelease-1>', lambda e, elem=element: self.release_element(e, elem))
        self.canvas.tag_bind(element.text_id, '<ButtonRelease-3>', lambda e, elem=element: self.element_right_click(e, elem))

    def setup_anchor_bindings(self, element):
        """ (Re)bind mouse events on an element's anchors.

        Anchor ids are canvas tags, so this must run again whenever the anchor
        ovals are recreated - newly added ids have no bindings otherwise.
        """
        # Check if this is a ProcessControlElement with custom anchors
        if isinstance(element, ProcessControlElement):
            # Get all anchors
            for anchor_id in element.get_all_anchors():
                if anchor_id:  # Safety check
                    anchor_info = element.get_anchor_position(anchor_id)
                    if anchor_info:
                        _, _, anchor_type = anchor_info
                        self.canvas.tag_bind(anchor_id, '<ButtonPress-1>', 
                                            lambda e, elem=element, anc=anchor_id: self.start_line(e, elem, anc))
                        self.canvas.tag_bind(anchor_id, '<B1-Motion>', self.drag_line)
                        self.canvas.tag_bind(anchor_id, '<ButtonRelease-1>', 
                                            lambda e, anc=anchor_id: self.end_line(e, anc))
                        self.canvas.tag_bind(anchor_id, '<Enter>', 
                                            lambda e, elem=element, anc_type=anchor_type, anc_id=anchor_id: elem.on_hover(anc_type, True, anc_id))
                        self.canvas.tag_bind(anchor_id, '<Leave>', 
                                            lambda e, elem=element, anc_type=anchor_type, anc_id=anchor_id: elem.on_hover(anc_type, False, anc_id))
                        self.canvas.tag_bind(anchor_id, '<ButtonRelease-3>',
                                             lambda e, elem=element, anc=anchor_id: self.element_right_click(e, elem, anc))
        else:
            # Bindings for all four anchors
            anchors = [
                (element.top_anchor, TOP_ANCHOR),
                (element.bottom_anchor, BOTTOM_ANCHOR),
                (element.left_anchor, LEFT_ANCHOR),
                (element.right_anchor, RIGHT_ANCHOR)
            ]

            for anchor in anchors:
                self.canvas.tag_bind(anchor[0], '<ButtonPress-1>', lambda e, elem=element, anc=anchor[0]: self.start_line(e, elem, anc))
                self.canvas.tag_bind(anchor[0], '<B1-Motion>', self.drag_line)
                self.canvas.tag_bind(anchor[0], '<ButtonRelease-1>', lambda e, anc=anchor[0]: self.end_line(e, anc))
                self.canvas.tag_bind(anchor[0], '<Enter>', lambda e, elem=element, anc_type=anchor[1]: elem.on_hover(anc_type, True))
                self.canvas.tag_bind(anchor[0], '<Leave>', lambda e, elem=element, anc_type=anchor[1]: elem.on_hover(anc_type, False))
                self.canvas.tag_bind(anchor[0], '<ButtonRelease-3>', lambda e, elem=element, anc=anchor[0]: self.element_right_click(e, elem, anc))

    def move_element(self, event, element):
        """Move an element to a new position."""
        if self.dragging:
            self.dragged = True
            if self.start_of_drag:
                self.canvas.delete("crossing_marker")
                self.start_of_drag = False
            dx = event.x - element.last_x
            dy = event.y - element.last_y
            for elem in self.selected_elements:
                elem.move(dx, dy)
                self.update_lines(elem)
                elem.last_x = event.x
                elem.last_y = event.y

    
    def align_left(self):
        """Align selected elements to the leftmost element"""
        if len(self.selected_elements) < 2:
            return
        
        # Find the leftmost element
        leftmost = min(self.selected_elements, key=lambda elem: elem.x)
        target_x = leftmost.x
        
        # Move all other elements to align with the leftmost
        for elem in self.selected_elements:
            if elem != leftmost:
                dx = target_x - elem.x
                elem.move(dx, 0)
                elem.last_x = target_x
                self.update_lines(elem)
        
        self.detect_and_break_line_crossings()
    
    def align_horizontal_center(self):
        """Align selected elements to the horizontal center"""
        if len(self.selected_elements) < 2:
            return
        
        # Calculate the average horizontal center
        center_x = sum(elem.x + elem.width/2 for elem in self.selected_elements) / len(self.selected_elements)
        
        # Move all elements to align with the center
        for elem in self.selected_elements:
            target_x = center_x - elem.width/2
            dx = target_x - elem.x
            elem.move(dx, 0)
            elem.last_x = target_x
            self.update_lines(elem)
        
        self.detect_and_break_line_crossings()
    
    def align_right(self):
        """Align selected elements to the rightmost element"""
        if len(self.selected_elements) < 2:
            return
        
        # Find the rightmost element (based on right edge)
        rightmost = max(self.selected_elements, key=lambda elem: elem.x + elem.width)
        target_right = rightmost.x + rightmost.width
        
        # Move all other elements to align with the rightmost
        for elem in self.selected_elements:
            if elem != rightmost:
                target_x = target_right - elem.width
                dx = target_x - elem.x
                elem.move(dx, 0)
                elem.last_x = target_x
                self.update_lines(elem)
        
        self.detect_and_break_line_crossings()
    
    def align_top(self):
        """Align selected elements to the topmost element"""
        if len(self.selected_elements) < 2:
            return
        
        # Find the topmost element
        topmost = min(self.selected_elements, key=lambda elem: elem.y)
        target_y = topmost.y
        
        # Move all other elements to align with the topmost
        for elem in self.selected_elements:
            if elem != topmost:
                dy = target_y - elem.y
                elem.move(0, dy)
                elem.last_y = target_y
                self.update_lines(elem)
        
        self.detect_and_break_line_crossings()
    
    def align_vertical_center(self):
        """Align selected elements to the vertical center"""
        if len(self.selected_elements) < 2:
            return
        
        # Calculate the average vertical center
        center_y = sum(elem.y + elem.height/2 for elem in self.selected_elements) / len(self.selected_elements)
        
        # Move all elements to align with the center
        for elem in self.selected_elements:
            target_y = center_y - elem.height/2
            dy = target_y - elem.y
            elem.move(0, dy)
            elem.last_y = target_y
            self.update_lines(elem)
        
        self.detect_and_break_line_crossings()
    
    def align_bottom(self):
        """Align selected elements to the bottommost element"""
        if len(self.selected_elements) < 2:
            return
        
        # Find the bottommost element (based on bottom edge)
        bottommost = max(self.selected_elements, key=lambda elem: elem.y + elem.height)
        target_bottom = bottommost.y + bottommost.height
        
        # Move all other elements to align with the bottommost
        for elem in self.selected_elements:
            if elem != bottommost:
                target_y = target_bottom - elem.height
                dy = target_y - elem.y
                elem.move(0, dy)
                elem.last_y = target_y
                self.update_lines(elem)
        
        self.detect_and_break_line_crossings()


    def distribute_horizontal(self):
        """Distribute selected elements evenly along the horizontal axis"""
        if len(self.selected_elements) < 3:
            return
        
        # Sort elements by x position
        sorted_elements = sorted(self.selected_elements, key=lambda elem: elem.x)
        
        # Calculate the total available space
        leftmost = sorted_elements[0]
        rightmost = sorted_elements[-1]
        total_width = (rightmost.x + rightmost.width) - leftmost.x
        
        # Calculate the space we need to distribute
        element_widths = sum(elem.width for elem in sorted_elements)
        
        # Calculate the equal spacing between elements
        spacing = (total_width - element_widths) / (len(sorted_elements) - 1)
        
        # Position each element except the first and last
        current_x = leftmost.x + leftmost.width + spacing
        for i in range(1, len(sorted_elements) - 1):
            elem = sorted_elements[i]
            target_x = current_x
            dx = target_x - elem.x
            elem.move(dx, 0)
            elem.last_x = target_x
            self.update_lines(elem)
            current_x += elem.width + spacing
        
        self.detect_and_break_line_crossings()
    
    def distribute_vertical(self):
        """Distribute selected elements evenly along the vertical axis"""
        if len(self.selected_elements) < 3:
            return
        
        # Sort elements by y position
        sorted_elements = sorted(self.selected_elements, key=lambda elem: elem.y)
        
        # Calculate the total available space
        topmost = sorted_elements[0]
        bottommost = sorted_elements[-1]
        total_height = (bottommost.y + bottommost.height) - topmost.y
        
        # Calculate the space we need to distribute
        element_heights = sum(elem.height for elem in sorted_elements)
        
        # Calculate the equal spacing between elements
        spacing = (total_height - element_heights) / (len(sorted_elements) - 1)
        
        # Position each element except the first and last
        current_y = topmost.y + topmost.height + spacing
        for i in range(1, len(sorted_elements) - 1):
            elem = sorted_elements[i]
            target_y = current_y
            dy = target_y - elem.y
            elem.move(0, dy)
            elem.last_y = target_y
            self.update_lines(elem)
            current_y += elem.height + spacing
        
        self.detect_and_break_line_crossings()

    def _create_free_anchor(self, x, y):
        """Create a free anchor at the specified position"""
        anchor = ProcessControlAnchorElement(x, y, self.imscale, self.__cached_anchor_image, self.font)
        
        # Store the anchor in our list
        self.add_element(anchor)
    

    def _highlight_free_anchor(self, anchor_id):
        """Highlight the anchor"""
        self.canvas.itemconfig(anchor_id, fill=HIGHLIGHTING_COLOR)
        
    def _unhighlight_free_anchor(self, anchor_id):
        """Unhighlight the anchor"""
        self.canvas.itemconfig(anchor_id, fill=DRAWING_DEFAULT_COLOR)

        
    def _anchor_drag(self, event, anchor):
        if self.current_tool_mode != 'free_anchor':
            return
        """Handle dragging an anchor"""
        # Get canvas coordinates
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        # Calculate the movement
        dx = canvas_x - anchor.x
        dy = canvas_y - anchor.y
        
        # Move the anchor
        anchor.move(dx, dy)

        self.update_lines(anchor)

    

    def update_lines(self, element):
        """Update lines connected to the moved element's anchors."""
        for line_id, (start_anchor, end_anchor), start_element, end_element in self.lines.values():
            if element not in [start_element, end_element]: continue
            line_tags = self.canvas.gettags(line_id)

            # Remove existing handles for this line
            self.canvas.delete('handle_' + str(line_id))

            if start_anchor == 'border':
                start_coords = self._find_best_anchor(start_element, end_element)[1]
            else:
                start_coords = start_element.get_anchor_position(start_anchor)
                if start_coords is None:
                    start_coords = self._find_best_anchor(start_element, end_element)[1]

            if end_anchor == 'border':
                end_coords = self._find_best_anchor(end_element, start_element)[1]
            else:
                end_coords = end_element.get_anchor_position(end_anchor)
                if end_coords is None:
                    end_coords = self._find_best_anchor(end_element, start_element)[1]

            if start_coords is None or end_coords is None:
                logging.warning(f"Skipping update of line {line_id}: no anchor position available.")
                continue

            new_coords = self.calculate_elbow([start_coords[0], start_coords[1]], start_coords[2], 
                                              [end_coords[0], end_coords[1]], end_coords[2],
                                              start_element, end_element)
            
            self.canvas.coords(line_id, new_coords)
            if 'signal_line' in line_tags:
                self.canvas.itemconfigure(line_id, fill=self.signal_line_color)
            else:
                self.canvas.itemconfigure(line_id, fill=DRAWING_DEFAULT_COLOR)

            # Create new handles for the updated line
            self.setup_line_segment_dragging(line_id)

        # Send the lines to the back before the background so they don't cover the elements
        self.send_lines_back()





    def send_lines_back(self):
        """Send lines to the back of the canvas, behind the background."""
        if self.canvas.find_withtag('line'):
            self.canvas.tag_lower('line', 'not_grid')
            self.canvas.tag_lower('background', 'line')

        



    def calculate_elbow(self, start, start_type, end, end_type, start_element, end_element):
        """
        Calculate the elbow points for right-angled connections.
        This enhanced version supports all four directions: top, bottom, left, right.
        """
        def scale(number):
            return int(number * self.imscale)

        # Determine offset direction based on anchor type
        if start_type == TOP_ANCHOR:
            start_offset_y = scale(-10)
            start_offset_x = 0
        elif start_type == BOTTOM_ANCHOR:
            start_offset_y = scale(10)
            start_offset_x = 0
        elif start_type == LEFT_ANCHOR:
            start_offset_y = 0
            start_offset_x = scale(-10)
        elif start_type == RIGHT_ANCHOR:
            start_offset_y = 0
            start_offset_x = scale(10)

        if end_type == TOP_ANCHOR:
            end_offset_y = scale(-10)
            end_offset_x = 0
        elif end_type == BOTTOM_ANCHOR:
            end_offset_y = scale(10)
            end_offset_x = 0
        elif end_type == LEFT_ANCHOR:
            end_offset_y = 0
            end_offset_x = scale(-10)
        elif end_type == RIGHT_ANCHOR:
            end_offset_y = 0
            end_offset_x = scale(10)

        # Start and end points
        sx, sy = start
        ex, ey = end
        
        # Connection cases based on anchor types

        max_element_height = max(start_element.height, end_element.height)
        max_element_width = max(start_element.width, end_element.width)
        
        # Case 1: Same direction anchors that need to go around
        if start_type == end_type:
            if start_type in [TOP_ANCHOR, BOTTOM_ANCHOR]:
                # Top-to-top or bottom-to-bottom
                if start_type == TOP_ANCHOR:
                    mid_init = sy if sy < ey else ey
                else:
                    mid_init = sy if sy > ey else ey
                mid_y = mid_init + start_offset_x + scale(20) * (1 if start_type == BOTTOM_ANCHOR else -1)
                return [sx, sy, 
                        sx, mid_y, 
                        ex, mid_y, 
                        ex, ey]
            else:
                # Left-to-left or right-to-right
                if start_type == LEFT_ANCHOR:
                    mid_init = sx if sx < ex else ex
                else:
                    mid_init = sx if sx > ex else ex
                mid_x = mid_init + start_offset_x + scale(20) * (1 if start_type == RIGHT_ANCHOR else -1)
                return [sx, sy, 
                        mid_x, sy, 
                        mid_x, ey, 
                        ex, ey]
        # Case 2: Opposite direction anchors (vertical connections)
        # Vertical connections (top to bottom or bottom to top)
        if (start_type in [TOP_ANCHOR, BOTTOM_ANCHOR] and end_type in [TOP_ANCHOR, BOTTOM_ANCHOR]):
            if (abs(ex - sx) < scale(max_element_width)/2 and 
                ((start_type == TOP_ANCHOR and end_type == BOTTOM_ANCHOR and sy < ey) or 
                (start_type == BOTTOM_ANCHOR and end_type == TOP_ANCHOR and sy > ey))):
                edge = min([sx, ex])
                return [sx, sy, sx, sy + start_offset_y, edge - scale(max_element_width), sy + start_offset_y,
                        edge - scale(max_element_width), ey + end_offset_y, ex, ey + end_offset_y, ex, ey]

            if sy < ey - scale(20) and start_type == BOTTOM_ANCHOR:
                mid_y = (sy + ey) / 2
                return [sx, sy, 
                        sx, mid_y, 
                        ex, mid_y, 
                        ex, ey]
            
            if ey < sy - scale(20) and start_type == TOP_ANCHOR:
                mid_y = (sy + ey) / 2
                return [sx, sy, sx, mid_y, 
                        ex, mid_y, ex, ey]
            
            # Default vertical connection
            mid_x = (sx + ex) / 2
            return [sx, sy, sx, sy + start_offset_y, mid_x, sy + start_offset_y,
                    mid_x, ey + end_offset_y, ex, ey + end_offset_y, ex, ey]
        # Case 3: Opposite direction anchors (horizontal connections)
        # Horizontal connections (left to right or right to left)
        elif (start_type in [LEFT_ANCHOR, RIGHT_ANCHOR] and end_type in [LEFT_ANCHOR, RIGHT_ANCHOR]):
            if (abs(ey - sy) < scale(max_element_height)/2 and 
                ((start_type == LEFT_ANCHOR and end_type == RIGHT_ANCHOR and sx < ex) or 
                (start_type == RIGHT_ANCHOR and end_type == LEFT_ANCHOR and sx > ex))):
                edge = min([sy, ey])
                return [sx, sy, sx + start_offset_x, sy, sx + start_offset_x, edge - scale(max_element_height),
                        ex + end_offset_x, edge - scale(max_element_height), ex + end_offset_x, ey, ex, ey]

            if sx < ex - scale(20) and start_type == RIGHT_ANCHOR:
                mid_x = (sx + ex) / 2
                return [sx, sy, mid_x, sy, 
                        mid_x, ey, ex, ey]
            
            if ex < sx - scale(20) and start_type == LEFT_ANCHOR:
                mid_x = (sx + ex) / 2
                return [sx, sy, mid_x, sy, 
                        mid_x, ey, ex, ey]
            
            # Default horizontal connection
            mid_y = (sy + ey) / 2
            return [sx, sy, sx + start_offset_x, sy, sx + start_offset_x, mid_y,
                    ex + end_offset_x, mid_y, ex + end_offset_x, ey, ex, ey]
        
        # Case 4: Mixed direction anchors (vertical to horizontal or horizontal to vertical)
        else:
            max_element_height = max(start_element.height, end_element.height)
            max_element_width = max(start_element.width, end_element.width)
            if start_type in [TOP_ANCHOR, BOTTOM_ANCHOR]:
                vx, vy = start
                hx, hy = end
                v_type = start_type
                h_type = end_type
            else:
                vx, vy = end
                hx, hy = start
                v_type = end_type
                h_type = start_type

            # Try simple L-shape first (just 2 lines)
            simple_path = [(vx, vy), (vx, hy), (hx, hy)]
            
            # Check if simple L-shape intersects with shapes
            shapes = [start_element, end_element]
            
            if (h_type == LEFT_ANCHOR and vx < hx and v_type == TOP_ANCHOR and vy > hy) or \
                (h_type == LEFT_ANCHOR and vx < hx and v_type == BOTTOM_ANCHOR and vy < hy) or \
                (h_type == RIGHT_ANCHOR and vx > hx and v_type == TOP_ANCHOR and vy > hy) or \
                (h_type == RIGHT_ANCHOR and vx > hx and v_type == BOTTOM_ANCHOR and vy < hy):

                return simple_path
            
            # If simple L-shape would intersect, use complex routing with clearance
            clearance = 0
            
            # Calculate safe intermediate points
            mid_y = int((start_element.y + scale(start_element.height) / 2 + 
                    (end_element.y + scale(end_element.height) / 2)) / 2)
            if v_type == TOP_ANCHOR:
                # Check if we need to go around shapes
                if self.shapes_between(vx, mid_y, hx, mid_y, shapes) or vy < hy:
                    mid_y = min(start_element.y, end_element.y) - clearance
            elif v_type == BOTTOM_ANCHOR:
                # Check if we need to go around shapes
                if self.shapes_between(vx, mid_y, hx, mid_y, shapes) or vy > hy:
                    mid_y = max(start_element.y + scale(start_element.height), 
                            end_element.y + scale(end_element.height)) + clearance
            
            mid_x = int((start_element.x + scale(start_element.width) / 2 +
                    (end_element.x + scale(end_element.width) / 2)) / 2)
            # Check horizontal clearance
            if h_type == LEFT_ANCHOR:
                # Check if we need to go around shapes
                if self.shapes_between(mid_x, mid_y, mid_x, hy, shapes) or hx < vx:
                    mid_x = min(start_element.x, end_element.x) - clearance
            elif h_type == RIGHT_ANCHOR:
                # Check if we need to go around shapes
                if self.shapes_between(mid_x, mid_y, mid_x, hy, shapes) or hx > vx:
                    mid_x = max(start_element.x + scale(start_element.width),
                            end_element.x + scale(end_element.width)) + clearance
            
            # Create complex path with clearance
            complex_path = [(vx, vy), (vx, mid_y), (mid_x, mid_y), (mid_x, hy), (hx, hy)]
            return complex_path


    def shapes_between(self, x1, y1, x2, y2, shapes):
        """Simple check if line segment intersects with shapes."""
        for shape in shapes:
            if self.line_intersects_rect(x1, y1, x2, y2, 
                                shape.x, shape.y, 
                                shape.x + shape.width * self.imscale, 
                                shape.y + shape.height * self.imscale):
                return True
        return False


    def line_intersects_rect(self, x1, y1, x2, y2, rx, ry, rx2, ry2):
        """Check if line segment intersects with rectangle."""
        return not (max(x1, x2) < rx or min(x1, x2) > rx2 or 
                    max(y1, y2) < ry or min(y1, y2) > ry2)


            

    def detect_and_break_line_crossings(self):
        """Detect and breaks lines that cross each other without sharing any elements."""

        # First remove any existing crossing markers
        self.canvas.delete("crossing_marker")

        self.lines_breaks = []

        # Extract all lines and their coordinates for checking
        line_data = []
        for line_id, (_, anchors, start_element, end_element) in self.lines.items():
            # Signal lines cross without a break marker; only material lines get broken.
            if line_id in self.signal_lines:
                continue
            coords = self.canvas.coords(line_id)
            # We need to check each segment of the polyline
            segments = []
            for i in range(0, len(coords) - 3, 2):
                segments.append((coords[i], coords[i+1], coords[i+2], coords[i+3]))
            line_data.append((line_id, segments, start_element, end_element))
        
        # Check each pair of lines for intersections
        for i in range(len(line_data)):
            line1_id, segments1, start_elem1, end_elem1 = line_data[i]
            
            for j in range(i + 1, len(line_data)):
                line2_id, segments2, start_elem2, end_elem2 = line_data[j]
                
                # Skip if lines share any elements
                if (start_elem1 is start_elem2 or 
                    start_elem1 is end_elem2 or 
                    end_elem1 is start_elem2 or 
                    end_elem1 is end_elem2):
                    continue

                # Find all intersection points between the line segments
                intersection_points = []

                # Check each segment pair for intersection
                for seg1 in segments1:
                    for seg2 in segments2:
                        intersection , intersection_point, line1_horizontal = self.__segments_intersect(seg1, seg2)
                        if intersection:
                            self.lines_breaks.append((line1_id, line2_id, intersection_point, line1_horizontal))
                            x, y = intersection_point
                            line_id = line1_id if line1_horizontal else line2_id
                            self.__create_crossing_marker(x, y, line_id)
        

    

    def __create_crossing_marker(self, x, y, line_id):
        """Create a visual marker at the intersection point of two lines."""
        # Size of the marker (adjusted by scale)
        size = 5 * self.imscale
        

        self.canvas.create_line(x - size, y, x + size, y, fill="#C0C0C0", 
                                                    width=int(3*self.material_line_width*self.imscale), tags=(f'{str(line_id)}_crossing_line_break','line_break'
                                                                                                           ,'crossing_marker','not_grid'))

        self.canvas.create_line(x - size, y, x + size, y, fill=DRAWING_DEFAULT_COLOR, 
                                                    width=int(self.material_line_width*self.imscale), tags=(f'{str(line_id)}_crossing_line','line'
                                                                                                         ,'crossing_marker','not_grid'))
    


    def create_break_image(self, size=12):
        """Create an image that looks like a line break.
        
        This creates a white oval that can be placed at line crossings
        to create the appearance of one line passing over another.
        """
        from PIL import Image, ImageDraw
        
        # Create a transparent image
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Draw a white oval (slightly smaller than the image bounds)
        padding = size // 6
        draw.ellipse(
            (padding, padding, size - padding, size - padding),
            fill='white'
        )
        
        # Store the base image
        self.break_base_image = img
        
        # Return initial PhotoImage
        return ImageTk.PhotoImage(img)

    def __segments_intersect(self, seg1, seg2):
        """Check if two line segments intersect.
        
        Each segment is defined as (x1, y1, x2, y2).
        """
        x1, y1, x2, y2 = seg1
        x3, y3, x4, y4 = seg2
        
        # Convert to line representation Ax + By = C
        A1 = y2 - y1
        B1 = x1 - x2
        C1 = A1 * x1 + B1 * y1
        
        A2 = y4 - y3
        B2 = x3 - x4
        C2 = A2 * x3 + B2 * y3
        
        # Determinant
        det = A1 * B2 - A2 * B1
        
        # Lines are parallel or coincident
        if abs(det) < 1e-8:
            return False, None, None
        
        # Compute intersection point
        x = (B2 * C1 - B1 * C2) / det
        y = (A1 * C2 - A2 * C1) / det
        
        # Floating point correction for intersection point
        x = round(x, 3)
        y = round(y, 3)
        x1 = round(x1, 3)
        y1 = round(y1, 3)
        x2 = round(x2, 3)
        y2 = round(y2, 3)
        x3 = round(x3, 3)
        y3 = round(y3, 3)
        x4 = round(x4, 3)        
        y4 = round(y4, 3)

        # Check if intersection point is on both segments
        on_segment1 = (min(x1, x2) <= x <= max(x1, x2) and 
                    min(y1, y2) <= y <= max(y1, y2))
        on_segment2 = (min(x3, x4) <= x <= max(x3, x4) and 
                    min(y3, y4) <= y <= max(y3, y4))
        
        # Determine which line is horizontal
        seg1_horizontal = abs(y2 - y1) < 1e-8

        
        return on_segment1 and on_segment2 , (x, y), seg1_horizontal

    
    def show_or_hide_properties_bar(self):
        """Show the properties bar for the selected element."""
        if len(self.selected_elements) == 1:
            self.properties_bar.grid()
            self.properties_bar.set_element(self.selected_elements[0])
        else:
            self.properties_bar.grid_remove()

    def element_right_click(self, event, element, anchor=None):
        """ Popup menu """
        if self.moving_canvas:
            self.moving_canvas = False 
            return
        
        # If shift is pressed, add to selection, otherwise make this the only selection
        is_shift_pressed = event.state & 0x0001
        if not is_shift_pressed and not element in self.selected_elements:
            for elem in self.selected_elements:
                elem.select_element(False)
            self.selected_elements = []
            self.__selection_callback()

        self.menu.enable_align_menu(False)
        self.menu.enable_anchor_direction_menu(False)
        self.menu.enable_edit_static_graphic(False)
        self.menu.enable_select_alternate_symbol(False)
        self.menu.enable_configure_symbol_anchors(False)
        self.menu.enable_show_on_drawing(False)
        self.menu.enable_change_anchor_position(False)

        if isinstance(element, int):
            self.selected_line_id = self.canvas.find_withtag("current")
        elif anchor is not None and isinstance(element, (ProcessControlStaticGraphicElement)):
            element.select_anchor(anchor, True)
            self.menu.enable_anchor_direction_menu(True, self.highlighted_anchor[2])
            self.menu.enable_change_anchor_position(True)
        else:
            self.select_element_id = self.canvas.find_withtag("current")
            
            # Add element to selection if not already selected
            if element not in self.selected_elements:
                self.selected_elements.append(element)
                self.__selection_callback(len(self.selected_elements))
                element.select_element(True)
                
            
            self.selected_element = element
            
            # Enable/disable align menu based on selection count
            self.menu.enable_align_menu(len(self.selected_elements) > 1)
            self.menu.enable_edit_static_graphic(len(self.selected_elements) == 1 and isinstance(element, ProcessControlStaticGraphicElement))
            self.menu.enable_select_alternate_symbol(len(self.selected_elements) == 1 and isinstance(element, ProcessControlLibraryElement))
            self.menu.enable_configure_symbol_anchors(len(self.selected_elements) == 1 and isinstance(element, ProcessControlLibraryElement))
            self.menu.enable_show_on_drawing(len(self.selected_elements) == 1 and isinstance(element, (ProcessControlLibraryElement, ProcessControlStaticGraphicElement)))
            self.menu.enable_anchor_direction_menu(self.highlighted_anchor is not None)
        
        self.show_or_hide_properties_bar()
        self.menu_pop_x = self.canvas.canvasx(event.x)
        self.menu_pop_y = self.canvas.canvasy(event.y)
        self.menu.post_edit_menu(event.x_root, event.y_root)  # show popup menu
        

    def select_element(self, event, element, moving=False):
        """ Record the last coordinates for a moving element """
        self.select_element_id = self.canvas.find_withtag("current")
        element.last_x = event.x
        element.last_y = event.y
        self.dragging = moving

        # If starting to move, record original position
        if moving:
            # Store the original position for undo
            for elem in self.selected_elements:
                elem.original_x = elem.x
                elem.original_y = elem.y

        # Check if Shift key is pressed for multi-selection
        is_shift_pressed = event.state & 0x0001  # Check if Shift is pressed
        
        if not is_shift_pressed and not element in self.selected_elements:
            # Deselect all currently selected elements if Shift is not pressed
            for elem in self.selected_elements:
                elem.select_element(False)
            self.selected_elements = []
            self.__selection_callback()

    
        # If element not already selected, add it to selection
        if element not in self.selected_elements:
            self.selected_elements.append(element)
            self.__selection_callback(len(self.selected_elements))
            element.select_element(True)

        self.start_of_drag = True
        element.select_element(True)
        self.show_or_hide_properties_bar()
        self.selected_element = element


    def release_element(self, _, element):
        """ Finalize the position of an element after moving it """
        

        x1, _, x2, _ = self.canvas.coords(self.grid_reference)

        adjusted_grid_width = abs(x1 - x2)

         # If element was dragged, record the move action for undo
        if self.dragged:
            # Start a batch for multiple elements
            self.__recode_moves_for_undo()


        # If multiple elements are selected and we're moving one, move them all
        if self.dragged and len(self.selected_elements) > 1 and element in self.selected_elements:
            # Calculate the difference to move
            dx = round(element.x / adjusted_grid_width) * adjusted_grid_width - element.x
            dy = round(element.y / adjusted_grid_width) * adjusted_grid_width - element.y

            
            
            # Move all selected elements
            for elem in self.selected_elements:
                elem.move(dx, dy)
                self.update_lines(elem)
                
                # Reset last positions to the current snapped position
                elem.last_x = elem.x
                elem.last_y = elem.y
        elif self.dragged:
            # Snap element's final position to the nearest 10 pixels
            snapped_x = round(element.x / adjusted_grid_width) * adjusted_grid_width
            snapped_y = round(element.y / adjusted_grid_width) * adjusted_grid_width

            # Calculate the difference to move
            dx = snapped_x - element.x
            dy = snapped_y - element.y

            # Move element to snapped position
            element.move(dx, dy)
            self.update_lines(element)


            # Reset last positions to the current snapped position
            element.last_x = element.x
            element.last_y = element.y

        self.dragging = False  # Reset the dragging flag
        self.dragged = False  # Reset the dragged flag

        # Check for line crossings and break lines if necessary
        self.detect_and_break_line_crossings()

    def __recode_moves_for_undo(self):
        if len(self.selected_elements) > 1:
            self.undo_manager.start_batch()
            
        for elem in self.selected_elements:
                # Record move action for each element
            if hasattr(elem, 'original_x') and hasattr(elem, 'original_y'):
                self.undo_manager.add_action('move_element', {
                        'element': elem,
                        'original_x': elem.original_x,
                        'original_y': elem.original_y,
                        'new_x': elem.x,  # Store current position for redo
                        'new_y': elem.y    # Store current position for redo
                    }, batch=(len(self.selected_elements) > 1))
            
            # End batch if multiple elements
        if len(self.selected_elements) > 1:
            self.undo_manager.end_batch()


    def start_line(self, event, element, anchor):
        """ Start drawing a line from the anchor point """
        if self.current_tool_mode != 'select' or self.editing_anchor_id is not None:
            return
        anchor_pos = element.get_anchor_position(anchor)
        if anchor_pos is None:
            logging.warning(f"Cannot start a line: anchor '{anchor}' no longer exists.")
            return
        anchor_x, anchor_y, _ = anchor_pos
        
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        self.drag_line_id = self.canvas.create_line(anchor_x, anchor_y, x, y, fill=DRAWING_DEFAULT_COLOR, 
                                                    capstyle=tk.ROUND, joinstyle=tk.ROUND,
                                                    width=int(self.material_line_width*self.imscale), tags=('material_line','line','not_grid'))
        self.drag_line_start_anchor = anchor
        self.drag_line_element = element
        self.dragging = False  # Reset the dragging flag

        # Show all the anchors of the all the elements
        for _ , elem in self.canvas_elements.items():
            if elem == self.drag_line_element:
                continue
            elem.show_anchors()

    def drag_line(self, event):
        """ Update the current line with new endpoint during drag """
        if self.current_tool_mode != 'select':
            return
        if self.drag_line_id is None: return

        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        self.drag_line_near_anchor, self.drag_line_near_element, min_dist = None, None, 10  # Snap threshold (e.g., 10 pixels)
        
        for _, elem in self.canvas_elements.items():
            # Skip the element we started from
            if elem == self.drag_line_element:
                continue
                
            if isinstance(elem, (ProcessControlLibraryElement, ProcessControlStaticGraphicElement)):
                # Check if the element has custom anchors
                for anc in elem.get_all_anchors():
                    if anc is None: continue
                    anc_pos = elem.get_anchor_position(anc)
                    if anc_pos is None: continue
                    anc_x, anc_y, _ = anc_pos
                    dist = ((anc_x - x) ** 2 + (anc_y - y) ** 2) ** 0.5
                    if dist < min_dist * self.imscale:
                        self.drag_line_near_anchor, min_dist, self.drag_line_near_element = anc, dist, elem
            
            if isinstance(elem, ProcessControlAnchorElement):
                # Check if the element has custom anchors
                for anc in elem.get_all_anchors():
                    if anc is None: continue
                    anc_pos = elem.get_anchor_position_for_drag_line(anc)
                    if anc_pos is None: continue
                    anc_x, anc_y, _ = anc_pos
                    dist = ((anc_x - x) ** 2 + (anc_y - y) ** 2) ** 0.5
                    if dist < min_dist * self.imscale:
                        self.drag_line_near_anchor, min_dist, self.drag_line_near_element = anc, dist, elem

        if not None in [self.drag_line_near_anchor , self.drag_line_element, self.drag_line_near_element]:
            line_color = HIGHLIGHTING_COLOR
            self.drag_line_connection_valid = True
        else:
            line_color = DRAWING_DEFAULT_COLOR
            self.drag_line_connection_valid = False
            
        self.canvas.coords(self.drag_line_id, self.canvas.coords(self.drag_line_id)[:2] + [x, y])
        self.canvas.itemconfigure(self.drag_line_id, fill=line_color)


    def end_line(self, _, __):
        """Finalize the line position and snap to nearest anchor if close enough."""
        if self.current_tool_mode != 'select':
            return
        
        for _, elem in self.canvas_elements.items():
            elem.show_anchors(False)

        if self.drag_line_id is None:
            return

        if not self.drag_line_connection_valid or None in [self.drag_line_near_anchor, self.drag_line_near_element]:
            self.canvas.delete(self.drag_line_id)
            return
        
        self.__create_material_line(self.drag_line_start_anchor, self.drag_line_near_anchor,
                              self.drag_line_element, self.drag_line_near_element)
        
        # Record action for undo
        self.undo_manager.add_action('add_line', {
            'line_id': self.drag_line_id,
            'start_anchor': self.drag_line_start_anchor,
            'end_anchor': self.drag_line_near_anchor,
            'start_element': self.drag_line_element,
            'end_element': self.drag_line_near_element
        })
        
        self.drag_line_id = None
        self.drag_line_start_anchor = None
        self.drag_line_near_element = None
        self.drag_line_element = None

        # Check for line crossings and break lines if necessary
        self.detect_and_break_line_crossings()

        self.canvas.tag_lower('line', 'not_grid')
        self.canvas.tag_lower('background', 'line')


    def __discard_drag_line(self):
        """Remove the in-progress drag line, if any"""
        if self.drag_line_id:
            self.canvas.delete(self.drag_line_id)
            self.drag_line_id = None

    @staticmethod
    def __anchor_resolves(anchor, element):
        """True when the anchor id still maps to a real anchor on the element"""
        if not anchor or anchor == 'border' or element is None:
            return False
        return element.get_anchor_position(anchor) is not None

    def __reresolve_anchor(self, anchor, element, other_element):
        """Keep a still-valid anchor id, otherwise pick the one nearest the other element"""
        if self.__anchor_resolves(anchor, element):
            return anchor
        if element is None or other_element is None:
            return anchor
        best_anchor, _ = self._find_best_anchor(element, other_element)
        return best_anchor

    def __create_material_line(self, anchor_1, anchor_2, element_1, element_2, new_line=False):
        if element_1 is None or element_2 is None or element_1 == element_2:
            self.__discard_drag_line()
            return

        # A material line needs a real anchor on both ends. Symbols that ship without
        # anchors (or stale ids left by a symbol swap) resolve to 'border' instead, and
        # the codebase represents those connections as signal lines.
        if not self.__anchor_resolves(anchor_1, element_1) or not self.__anchor_resolves(anchor_2, element_2):
            logging.info(f"No usable anchor for a material line between "
                         f"'{getattr(element_1, 'name', element_1)}' and "
                         f"'{getattr(element_2, 'name', element_2)}'; creating a signal line instead.")
            self.__discard_drag_line()
            self.__create_signal_line(anchor_1, anchor_2, element_1, element_2, material_fallback=True)
            return

        if anchor_1 == anchor_2:
            self.__discard_drag_line()
            return

        self.__draw_line_connection(anchor_1, anchor_2, element_1, element_2, new_line)

    def __draw_line_connection(self, anchor_1, anchor_2
                               , element_1: ProcessControlElement, element_2: ProcessControlElement, new_line=False):


        if self.__connection_already_exists(anchor_1, anchor_2, element_1, element_2):
            logging.info(f"Connection already exists between {element_1.name} and {element_2.name}")
            if self.drag_line_id:
                self.canvas.delete(self.drag_line_id)
            return  # Exit without creating a new line

        start_pos = element_1.get_anchor_position(anchor_1)
        end_pos = element_2.get_anchor_position(anchor_2)

        if start_pos is None or end_pos is None:
            logging.warning(f"Cannot draw material line: anchor "
                            f"'{anchor_1 if start_pos is None else anchor_2}' no longer exists.")
            self.__discard_drag_line()
            return

        start_x, start_y, start_type = start_pos
        end_x, end_y, end_type = end_pos

        if new_line:
            line_id = self.canvas.create_line(start_x, start_y, end_x, end_y, fill=DRAWING_DEFAULT_COLOR, 
                                                        capstyle=tk.ROUND, joinstyle=tk.ROUND,
                                                        width=int(self.material_line_width*self.imscale), tags=('material_line','line','not_grid'))
        else:
            line_id = self.drag_line_id

        anchors = (anchor_1, anchor_2)
        coords = self.calculate_elbow([start_x, start_y], start_type, [end_x, end_y], end_type, element_1, element_2)
        self.canvas.coords(line_id, coords)
        self.canvas.itemconfigure(line_id, fill=DRAWING_DEFAULT_COLOR)
        
        self.lines[line_id] = (line_id, anchors, element_1, element_2)  # Store the line with anchors
        self.material_lines[line_id] = (line_id, anchors, element_1, element_2)  # Store the material line

        self.canvas.tag_bind(line_id, '<Enter>', self.__highlight_line)
        self.canvas.tag_bind(line_id, '<Leave>', self.__unhighlight_line)
        self.canvas.tag_bind(line_id, '<ButtonRelease-1>', self.__select_line)
        self.canvas.tag_bind(line_id, '<ButtonRelease-3>', lambda e, elem=line_id: self.element_right_click(e, elem))

        # Set up draggable segments
        self.setup_line_segment_dragging(line_id)


    def __connection_already_exists(self, anchor_1, anchor_2, element_1, element_2):
        """Check if a connection already exists between the specified elements and anchors.
        
        Args:
            anchor_1: First anchor point
            anchor_2: Second anchor point
            element_1: First element
            element_2: Second element
            
        Returns:
            bool: True if connection already exists, False otherwise
        """
        for line_id, (_, existing_anchors, existing_start_element, existing_end_element) in self.lines.items():
            # Check if the same connection already exists (in either direction)
            if ((existing_start_element == element_1 and existing_end_element == element_2 and
                existing_anchors[0] == anchor_1 and existing_anchors[1] == anchor_2) or
                (existing_start_element == element_2 and existing_end_element == element_1 and
                existing_anchors[0] == anchor_2 and existing_anchors[1] == anchor_1)):

                # Remove the line_id from the self.lines_to_remove
                if line_id in self.lines_to_remove:
                    del self.lines_to_remove[line_id]

                return True
        return False

    def __highlight_line(self, event):
        """Highlight the line and its crossing line when hovered."""
        self.canvas.itemconfig(tk.CURRENT, fill=HIGHLIGHTING_COLOR)
        line_id = self.canvas.find_withtag('current')[0]  # id of the current object
        self.canvas.itemconfig(f'{str(line_id)}_crossing_line', fill=HIGHLIGHTING_COLOR)
        self.canvas.itemconfig(f'handle_{line_id}', fill=HIGHLIGHTING_COLOR)  

    def __unhighlight_line(self, event):
        current = self.canvas.find_withtag('current')  # id of the current object
       
        if self.selected_line_id == current:
            return
        
        line_tags = self.canvas.gettags('current')

        if 'signal_line' in line_tags:
            self.canvas.itemconfig(current, fill=self.signal_line_color)
        else:
            self.canvas.itemconfig(current, fill=DRAWING_DEFAULT_COLOR)
        line_id = self.canvas.find_withtag('current')[0]  # id of the current object
        self.canvas.itemconfig(f'{str(line_id)}_crossing_line', fill=DRAWING_DEFAULT_COLOR)
        self.canvas.itemconfig(f'handle_{line_id}', fill='')  # Reset handle color

    def __select_line(self, _):
        item = self.canvas.find_withtag('current')  # id of the current object
        for line in self.lines.values():
            if item[0] == line[0]:
                break
        else:
            return
    
        self.selected_line_id = item[0]
        self.canvas.itemconfig(f'{str(self.selected_line_id)}_crossing_line', fill=HIGHLIGHTING_COLOR)



    def setup_line_segment_dragging(self, line_id):
        """Set up dragging functionality for line segments."""
        coords = self.canvas.coords(line_id)

        if len(coords) == 6:
            return
        
        # Create control points at each vertex of the polyline (except start and end points)
        
        
        for i in range(4, len(coords) - 2, 2):
            x, y = (coords[i] + coords[i - 2])/2, (coords[i+1] + coords[i - 1])/2
            handle_id = self.canvas.create_oval(
                x - 4, y - 4, 
                x + 4, y + 4,
                fill='', outline='', 
                tags=(f'handle_{line_id}_{i}',f'handle_{line_id}', 'line_handle', 'not_grid')
            )
            
            # Bind events to the handle
            self.canvas.tag_bind(handle_id, '<Enter>', lambda e, h=handle_id: self.canvas.itemconfig(h, fill=HIGHLIGHTING_COLOR))
            self.canvas.tag_bind(handle_id, '<Leave>', lambda e, h=handle_id: self.canvas.itemconfig(h, fill=''))
            self.canvas.tag_bind(handle_id, '<ButtonPress-1>', lambda e, h=handle_id, l=line_id: self.start_segment_drag(e, h, l))
            self.canvas.tag_bind(handle_id, '<B1-Motion>', self.drag_segment)
            self.canvas.tag_bind(handle_id, '<ButtonRelease-1>', lambda e, l=line_id:  self.end_segment_drag(e, l))

    def start_segment_drag(self, event, handle_id, line_id):
        """Start dragging a line segment."""
        self.dragging_segment = True
        self.drag_segment_handle = handle_id
        self.drag_segment_line = line_id
        self.drag_segment_start_x = self.canvas.canvasx(event.x)
        self.drag_segment_start_y = self.canvas.canvasy(event.y)
        
        # Get the segment index from the handle tag
        tag = self.canvas.gettags(handle_id)[0]
        self.drag_segment_index = int(tag.split('_')[2])
        
        # Remember original coords for cancel operation
        self.drag_segment_original_coords = self.canvas.coords(line_id)

        self.canvas.delete(f'{line_id}_crossing_line_break')
        self.canvas.delete(f'{line_id}_crossing_line')
        other_line_ids = [line_break[0] for line_break in self.lines_breaks if line_break[1] == line_id]
        for line_break_id in other_line_ids:
            self.canvas.delete(f'{line_break_id}_crossing_line_break')
            self.canvas.delete(f'{line_break_id}_crossing_line')
        

    def drag_segment(self, event):
        """Update the line segment position during drag."""
        if not hasattr(self, 'dragging_segment') or not self.dragging_segment:
            return
        
        if self.editing_anchor_id is not None:
            return
            
        # Calculate the movement
        current_x = self.canvas.canvasx(event.x)
        current_y = self.canvas.canvasy(event.y)
        dx = current_x - self.drag_segment_start_x
        dy = current_y - self.drag_segment_start_y
        
        # Update the line vertex position
        coords = self.canvas.coords(self.drag_segment_line)
        
        # Determine which points to move based on segment type
        i = self.drag_segment_index
        
        # Get the line's elements
        line_info = self.lines.get(self.drag_segment_line)
        if not line_info:
            return
        
        
        # Only allow movement in the appropriate direction based on segment orientation
        is_horizontal = abs(coords[i] - coords[i-2]) > abs(coords[i+1] - coords[i-1])
        
        # For horizontal segments, only allow vertical movement
        # For vertical segments, only allow horizontal movement
        if is_horizontal:
            # This is a horizontal segment - only move vertically
            coords[i+1] += dy
            # Find the connected vertical segments and update them
            if i > 2:  # There's a segment before
                coords[i-1] += dy
        else:
            # This is a vertical segment - only move horizontally
            coords[i] += dx
            # Find the connected horizontal segments and update them
            if i > 2:  # There's a segment before
                coords[i-2] += dx

        
        # Update the line
        self.canvas.coords(self.drag_segment_line, *coords)
        
        # Update the handle position
        x, y = (coords[i] + coords[i - 2])/2, (coords[i+1] + coords[i - 1])/2
        self.canvas.coords(
            self.drag_segment_handle,
            x - 4, y - 4,
            x + 4, y + 4
        )
        
        # Update the start position for the next movement
        self.drag_segment_start_x = current_x
        self.drag_segment_start_y = current_y


    def is_running_along_element_border(self, element, x1, y1, x2, y2):
        """Check if the line segment is running along the border of an element.
        Args:
            element: The element to check against
            x1, y1: Start point of the line segment
            x2, y2: End point of the line segment
            
        Returns:
            bool: True if the line runs along the element border, False otherwise
        """
        # Get element boundaries
        elem_x1 = element.x
        elem_y1 = element.y
        elem_x2 = element.x + element.width * self.imscale
        elem_y2 = element.y + element.height * self.imscale
        
        # Define the tolerance (how close to the border the line needs to be)
        tolerance = 1 * self.imscale
        
        # Check if both endpoints are near the same border
        
        # Top border
        if (abs(y1 - elem_y1) <= tolerance and abs(y2 - elem_y1) <= tolerance and
            min(x1, x2) >= elem_x1 - tolerance and max(x1, x2) <= elem_x2 + tolerance):
            return True
            
        # Bottom border
        if (abs(y1 - elem_y2) <= tolerance and abs(y2 - elem_y2) <= tolerance and
            min(x1, x2) >= elem_x1 - tolerance and max(x1, x2) <= elem_x2 + tolerance):
            return True
            
        # Left border
        if (abs(x1 - elem_x1) <= tolerance and abs(x2 - elem_x1) <= tolerance and
            min(y1, y2) >= elem_y1 - tolerance and max(y1, y2) <= elem_y2 + tolerance):
            return True
            
        # Right border
        if (abs(x1 - elem_x2) <= tolerance and abs(x2 - elem_x2) <= tolerance and
            min(y1, y2) >= elem_y1 - tolerance and max(y1, y2) <= elem_y2 + tolerance):
            return True
            
        
                
        return False
        


    def end_segment_drag(self, _, line_id):
        """Finalize the line segment position after dragging."""
        if not hasattr(self, 'dragging_segment') or not self.dragging_segment:
            return
        
        # Record action for undo
        if hasattr(self, 'drag_segment_original_coords'):
            self.undo_manager.add_action('modify_line', {
                'line_id': line_id,
                'original_coords': self.drag_segment_original_coords
            })
        
        # Check for line crossings and update breaks
        self.detect_and_break_line_crossings()

        # Remove existing handles for this line
        self.canvas.delete('handle_' + str(line_id))

        # Create new handles for the updated line
        self.setup_line_segment_dragging(line_id)

        line_tags = self.canvas.gettags(line_id)

        coords = self.canvas.coords(line_id)

        line_info = self.lines.get(line_id)

        # Remove the segment if it runs along an element border
       
        
        if self.is_running_along_element_border(line_info[2], coords[0], coords[1],
                                                    coords[2], coords[3]):
            # Remove the segment
            coords = coords[2:]  # Keep only the second segment


        if self.is_running_along_element_border(line_info[3], coords[-4], coords[-3],
                                                    coords[-2], coords[-1]):
            coords = coords[:-2]  # Remove the last segment
     

        self.canvas.coords(line_id, *coords)
        
        # Reset dragging state
        self.dragging_segment = False
        self.drag_segment_handle = None
        self.drag_segment_line = None

    def __redraw(self, _=None):
        """ Redraw the canvas when it is resized """
        # If canvas is not ready, skip redraw
        if not self.canvas.winfo_ismapped():
            return
        self.__resize_elements()
        bbox = self.canvas.bbox('not_grid')
        if bbox:
            self.canvas.config(scrollregion=(bbox[0] - 50, bbox[1] - 50, bbox[2] + 50, bbox[3] + 50))
        if self.__zoom_percentage_callback:
            self.zoom_scale = self.imscale  # image pyramide scale
            self.__zoom_percentage_callback(self.zoom_scale*100)
        self.banner_handler.draw(self.canvas, self.vbar)
        


    def set_shared_progress(self, percentage,task, close_func=None):
        self.banner_handler.secondary_progress_banner.show()
        self.banner_handler.secondary_progress_banner.set_info(percentage,task)
        self.banner_handler.secondary_progress_banner.set_close_func(close_func)

        if percentage >= 1:
            self.banner_handler.secondary_progress_banner.enable_close_pop_up()


    def hide_shared_progress(self):
        self.banner_handler.secondary_progress_banner.hide()


    def __vertical_scroll(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), tk.UNITS)
        


    def __horizontal_scroll(self, event):
        self.canvas.xview_scroll(int(-1*(event.delta/120)), tk.UNITS)
        self.__redraw_drop_shadow()  # redraw the image


    # noinspection PyUnusedLocal
    def __scroll_x(self, *args, **kwargs):
        """ Scroll canvas horizontally and redraw the image """
        self.canvas.xview(*args)  # scroll horizontally
        self.__redraw_drop_shadow()  # redraw the image

    # noinspection PyUnusedLocal
    def __scroll_y(self, *args, **kwargs):
        """ Scroll canvas vertically and redraw the image """
        self.canvas.yview(*args)  # scroll vertically
        self.__redraw_drop_shadow()  # redraw the image


    def __move_from(self, event):
        """ Remember previous coordinates for drag move with the mouse """
        self.canvas.scan_mark(event.x, event.y)

    def __move_to(self, event):
        """ Drag (move) canvas to the new position """
        self.moving_canvas = True
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        self.offset_x += event.x - self.canvas.canvasx(0)
        self.offset_y += event.y - self.canvas.canvasy(0)
        self.__redraw_drop_shadow()  # zoom tile and show it on the canvas

    def popup(self, event):
        """ Popup menu """

        if self.moving_canvas:
            self.moving_canvas = False 
            return

        current = self.canvas.find_withtag("current")  # Finds the item that is currently under the cursor

        if current != self.select_element_id and self.selected_element is not None:
            self.selected_element.select_element(False)
            self.selected_element = None

        if current != self.selected_line_id:
            self.canvas.itemconfig(self.selected_line_id, fill=DRAWING_DEFAULT_COLOR)
            self.canvas.itemconfig(f'handle_{self.selected_line_id}', fill='')
            self.selected_line_id = None

        
        self.menu_pop_x = self.canvas.canvasx(event.x)
        self.menu_pop_y = self.canvas.canvasy(event.y)

        self.menu.post_basic_menu(event.x_root, event.y_root, self.show_object_names)  # show popup menu

    def __zoom(self, event):
        """ Zoom with mouse wheel """
        x = self.canvas.canvasx(event.x)  # get coordinates of the event on the canvas
        y = self.canvas.canvasy(event.y)
        scale = 1.0
        # Respond to Linux (event.num) or Windows (event.delta) wheel event
        if event.num == 5 or event.delta == -120:  # scroll down, zoom out, smaller
            self.imscale /= self.__delta
            scale        /= self.__delta
        if event.num == 4 or event.delta == 120:  # scroll up, zoom in, bigger
            i = float(min(self.canvas.winfo_width(), self.canvas.winfo_height()) >> 1)
            if i < self.imscale: return  # 1 pixel is bigger than the visible area
            self.imscale *= self.__delta
            scale        *= self.__delta

        self.__scale_canvas(x, y, scale)
        self.__redraw_drop_shadow()


    def __scale_canvas(self, x, y, scale):
        self.canvas.scale('not_grid', x, y, scale, scale)  # rescale all objects
        self.canvas.itemconfigure('material_line', width=int(self.material_line_width*self.imscale))
        self.canvas.itemconfigure('line_break', width=int(3*self.material_line_width*self.imscale))
        self.canvas.itemconfigure('signal_line', width=int(self.signal_line_width*self.imscale))
        
        if self.imscale >= 1:
            scaled_dash = [max(1,int(d * self.imscale)) for d in self.signal_line_dash]
        else:
            scaled_dash = (1,1)
        self.canvas.itemconfigure('signal_line', dash=scaled_dash)

        # Update handle sizes
        for handle_id in self.canvas.find_withtag('line_handle'):
            coords = self.canvas.coords(handle_id)
            center_x = (coords[0] + coords[2]) / 2
            center_y = (coords[1] + coords[3]) / 2
            size = 4 * self.imscale
            self.canvas.coords(
                handle_id,
                center_x - size, center_y - size,
                center_x + size, center_y + size
            )

        self.__redraw()


    def __zoom_to(self, percentage):
        box_canvas = (self.canvas.canvasx(0),  # get visible area of the canvas
                      self.canvas.canvasy(0),
                      self.canvas.canvasx(self.canvas.winfo_width()),
                      self.canvas.canvasy(self.canvas.winfo_height()))
        x =  int((box_canvas[0] + box_canvas[2])/2)    
        y =  int((box_canvas[1] + box_canvas[3])/2)   

        scale =  float(percentage) / 100

        canvas_scale = scale / self.imscale  # calculate scale factor for canvas
        self.imscale = scale  # update image pyramide scale

        self.__scale_canvas(x, y, canvas_scale)
        self.__redraw_drop_shadow()



    def zoom(self, percentage):
        self.__zoom_to(percentage)


    # Canvas item coordinates carry the current zoom and container origin, so state
    # is persisted in unscaled display coordinates. Version 1 states were written in
    # raw canvas coordinates and are restored as-is.
    STATE_COORDINATE_VERSION = 2

    def to_display_coords(self, x, y):
        """Convert canvas coordinates to unscaled display coordinates"""
        bbox = self.canvas.coords(self.container)
        return (x - bbox[0]) / self.imscale, (y - bbox[1]) / self.imscale

    def to_canvas_coords(self, x, y):
        """Convert unscaled display coordinates to canvas coordinates"""
        bbox = self.canvas.coords(self.container)
        return x * self.imscale + bbox[0], y * self.imscale + bbox[1]

    def save_canvas_state(self):
        """Save the current canvas state to the database"""
        # Create a dictionary to store the canvas state
        if not self.done_loading:
            return
        
        canvas_state = {
            'elements': self.__serialize_elements(),
            'material_lines': self.__serialize_lines(self.material_lines),
            'signal_lines': self.__serialize_lines(self.signal_lines),
            'line_breaks': self.__serialize_line_breaks(),
            'timestamp': int(time.time()),
            'gfx_file': self.gfx_file,
            'coordinate_version': self.STATE_COORDINATE_VERSION
        }
        
        # Save to database
        if hasattr(self, '_ProcessDisplayCanvas__internal_db') and self.__internal_db:
            self.__internal_db.save_build_hmi_display(self.gfx_file, canvas_state)
            logging.info(f"Canvas state saved for {self.gfx_file}")

    def load_canvas_state(self):
        """Load the canvas state from the database"""
        # Get state from database
        if not self.__internal_db:
            return False
            
        canvas_state = self.__internal_db.get_build_hmi_display(self.gfx_file)
        if not canvas_state:
            return False

        logging.info(f"Loading canvas state for {self.gfx_file}")

        display_coords = canvas_state.get('coordinate_version', 1) >= self.STATE_COORDINATE_VERSION

        # Load elements
        self.__deserialize_elements(canvas_state.get('elements', []), display_coords)
        
        # Load lines
        self.__deserialize_lines(canvas_state.get('material_lines', []), is_material=True, display_coords=display_coords)
        self.__deserialize_lines(canvas_state.get('signal_lines', []), is_material=False, display_coords=display_coords)
        
        # Load line breaks
        self.__deserialize_line_breaks(canvas_state.get('line_breaks', []), display_coords)
        
        # Check for line crossings and update display
        self.detect_and_break_line_crossings()
        return True    

    def __clear_current_canvas(self):
        """Clear all elements and lines from the canvas"""
        # Delete all elements
        for element_id in list(self.canvas_elements.keys()):
            element = self.canvas_elements[element_id]
            element.delete()
            
        # Clear dictionaries
        self.canvas_elements = {}
        self.lines = {}
        self.material_lines = {}
        self.signal_lines = {}
        self.lines_breaks = []
	    # Clear canvas items with specific tags
        self.canvas.delete('line')
        self.canvas.delete('crossing_marker')
        self.canvas.delete('line_handle')

    def __serialize_elements(self):
        """Serialize all canvas elements to a list of dictionaries"""
        elements_data = []
        
        for element_id, element in self.canvas_elements.items():
            x, y = self.to_display_coords(element.x, element.y)
            # Get basic element properties
            element_data = {
                'id': element_id,
                'x': x,
                'y': y,
                'width': element.width,
                'height': element.height,
                'name': element.name,
                'spa_id': element.spa_id,
                'spa_name': element.spa_name,
                'gfx_reference': element.gfx_reference,
                'type': element.__class__.__name__,
            }
            
            # Add class-specific properties
            if isinstance(element, ProcessControlLibraryElement):
                element_data.update({
                    'library_id': element.library_id,
                    'catalog_number': element.catalog_number,
                    'hmi_symbol': element.hmi_symbol,
                })
            elif isinstance(element, ProcessControlStaticGraphicElement):
                element_data['filename_suffix']= element.filename_suffix
                if hasattr(element, 'svg_string'):
                    element_data['svg_string'] = element.svg_string
                    
            # Serialize anchor data
            element_data['anchors'] = self.__serialize_anchors(element)
            
            elements_data.append(element_data)
            
        return elements_data
    
    def __serialize_anchors(self, element):
        """Serialize an element's anchors"""
        anchors = {
            'top': [],
            'bottom': [],
            'left': [],
            'right': []
        }
        
        # For ProcessControlElements, get all custom anchors
        if isinstance(element, ProcessControlElement):
            if hasattr(element, 'top_anchors') and element.top_anchors:
                anchors['top'] = element.top_anchors
            if hasattr(element, 'bottom_anchors') and element.bottom_anchors:
                anchors['bottom'] = element.bottom_anchors
            if hasattr(element, 'left_anchors') and element.left_anchors:
                anchors['left'] = element.left_anchors
            if hasattr(element, 'right_anchors') and element.right_anchors:
                anchors['right'] = element.right_anchors
                
        return anchors
    
    def __serialize_lines(self, lines_dict):
        """Serialize lines to a list of dictionaries"""
        lines_data = []
        
        for line_id, (_, anchors, start_element, end_element) in lines_dict.items():
            # Get the coordinates of the line
            coords = self.convert_flat_coords(self.canvas.coords(line_id), self.to_display_coords)
            
            # Create line data
            line_data = {
                'coords': coords,
                'start_element_spa_id': start_element.spa_id,
                'end_element_spa_id': end_element.spa_id,
                'start_anchor': anchors[0],
                'end_anchor': anchors[1],
                'material_fallback': line_id in self.material_fallback_lines
            }
            
            lines_data.append(line_data)
            
        return lines_data
    
    def __get_element_id(self, element):
        """Get the ID of an element in the canvas_elements dictionary"""
        for elem_id, elem in self.canvas_elements.items():
            if elem == element:
                return elem_id
        return None
    
    def get_selected_gfx(self):
        """ Get the selected GFX index (always 0 in single file mode) """
        return 0
    
    def __serialize_line_breaks(self):
        """Serialize line breaks"""
        breaks_data = []
        
        for line_break in self.lines_breaks:
            point = line_break[2]
            break_data = {
                'line1_id': line_break[0],
                'line2_id': line_break[1],
                'point': list(self.to_display_coords(point[0], point[1])),
                'line1_horizontal': line_break[3]
            }
            breaks_data.append(break_data)
            
        return breaks_data

    def convert_flat_coords(self, coords, convert):
        """Apply a coordinate conversion to a flat [x0, y0, x1, y1, ...] list"""
        converted = []
        for i in range(0, len(coords) - 1, 2):
            converted.extend(convert(coords[i], coords[i + 1]))
        return converted
    
    def __deserialize_elements(self, elements_data, display_coords=True):
        """Update existing elements from serialized data instead of creating new ones"""

        # Create a dictionary mapping spa_id to existing elements
        spa_ids_to_elements = {element.spa_id: element for element in self.canvas_elements.values() if element.spa_id is not None}
        gfx_file_editor = self.gfx_file_editor

        # Update existing elements based on serialized data
        for element_data in elements_data:
            element_type = element_data.get('type')
            spa_id = element_data.get('spa_id')
            
            # Skip if no spa_id or element doesn't exist
            if spa_id is None or spa_id not in spa_ids_to_elements:
                continue
                
            existing_element = spa_ids_to_elements[spa_id]
            saved_x, saved_y = self.__saved_element_position(element_data, existing_element, display_coords)
            
            if element_type == 'ProcessControlLibraryElement' and isinstance(existing_element, ProcessControlLibraryElement):
                # Update position and size
                dx = saved_x - existing_element.x
                dy = saved_y - existing_element.y
                
                if dx != 0 or dy != 0:
                    existing_element.move(dx, dy)
                
                # Update size
                new_width = element_data.get('width', existing_element.width)
                new_height = element_data.get('height', existing_element.height)
                existing_element.update_width_height(new_width, new_height, self.imscale)
                
                # Update HMI symbol if it's different
                new_hmi_symbol = element_data.get('hmi_symbol')
                if new_hmi_symbol and new_hmi_symbol != existing_element.hmi_symbol:
                    # Get the symbol XML from the GfxFileEditor
                    library_id = existing_element.library_id
                    symbol_xml = gfx_file_editor.get_symbol_xml(library_id, new_hmi_symbol)
                    if symbol_xml:
                        self.update_hmi_symbol(existing_element, new_hmi_symbol, symbol_xml, gfx_file_editor)
                
            elif element_type == 'ProcessControlStaticGraphicElement' and isinstance(existing_element, ProcessControlStaticGraphicElement):
                # Update position and size
                dx = saved_x - existing_element.x
                dy = saved_y - existing_element.y
                
                if dx != 0 or dy != 0:
                    existing_element.move(dx, dy)
                
                # Update size
                new_width = element_data.get('width', existing_element.width)
                new_height = element_data.get('height', existing_element.height)
                existing_element.resize_to(existing_element.x, existing_element.y, new_width, new_height)
                existing_element.update_image()
                existing_element.set_filename_suffix(element_data.get('filename_suffix', existing_element.filename_suffix))
                
                
            elif element_type == 'Anchor':
                # For free anchors, update position
                if isinstance(existing_element, AnchorElement):
                    existing_element.update_position(saved_x, saved_y, self.imscale)
            
            # Update lines connected to this element
            self.update_lines(existing_element)
    
    def __saved_element_position(self, element_data, element, display_coords):
        """Canvas position an element should be restored to from its serialized data"""
        x = element_data.get('x')
        y = element_data.get('y')
        if x is None or y is None:
            return element.x, element.y
        if not display_coords:
            return x, y
        return self.to_canvas_coords(x, y)

    def __deserialize_lines(self, lines_data, is_material=True, display_coords=True):
        """Recreate lines from serialized data"""

        spa_ids_to_elements = {element.spa_id: element for element in self.canvas_elements.values() if element.spa_id is not None}
        for line_data in lines_data:
            # Get the start and end elements
            start_element_spa_id = line_data.get('start_element_spa_id')
            end_element_spa_id = line_data.get('end_element_spa_id')

            start_element_id = spa_ids_to_elements.get(start_element_spa_id).id
            end_element_id = spa_ids_to_elements.get(end_element_spa_id).id

            if start_element_id in self.canvas_elements and end_element_id in self.canvas_elements:
                start_element = self.canvas_elements[start_element_id]
                end_element = self.canvas_elements[end_element_id]
                
                # Get anchors
                start_anchor = line_data.get('start_anchor')
                end_anchor = line_data.get('end_anchor')
                
                # Create the line
                if is_material:
                    self.__create_material_line(start_anchor, end_anchor, start_element, end_element, True)
                elif line_data.get('material_fallback'):
                    # Saved as a signal line only because the symbol had no anchors; the
                    # stale ids must be re-resolved before re-testing for a material line.
                    start_anchor = self.__reresolve_anchor(start_anchor, start_element, end_element)
                    end_anchor = self.__reresolve_anchor(end_anchor, end_element, start_element)
                    self.__create_material_line(start_anchor, end_anchor, start_element, end_element, True)
                else:
                    self.__create_signal_line(start_anchor, end_anchor, start_element, end_element)
                    
                # Update the line's coordinates if provided
                coords = line_data.get('coords')
                if coords and self.drag_line_id:
                    if display_coords:
                        coords = self.convert_flat_coords(coords, self.to_canvas_coords)
                    self.canvas.coords(self.drag_line_id, coords)
    
    def __deserialize_line_breaks(self, breaks_data, display_coords=True):
        """Recreate line breaks from serialized data"""
        for break_data in breaks_data:
            line1_id = break_data.get('line1_id')
            line2_id = break_data.get('line2_id')
            point = tuple(break_data.get('point'))
            if display_coords:
                point = self.to_canvas_coords(point[0], point[1])
            line1_horizontal = break_data.get('line1_horizontal')
            
            # Add to lines_breaks list
            self.lines_breaks.append((line1_id, line2_id, point, line1_horizontal))

    def destroy(self):
        """Override destroy method to save canvas state before destruction"""
        try:
            # Save the current canvas state before destroying the widget
            self.save_canvas_state()
        except Exception as e:
            # Log the error but don't prevent destruction
            logging.error(f"Error saving canvas state during destruction: {e}")
        finally:
            # Call the parent's destroy method
            super().destroy()



class UndoManager:
    """Manages the undo/redo history for the process diagram editor"""
    
    def __init__(self, canvas_manager):
        """Initialize the undo manager
        
        Args:
            canvas_manager: The ProcessDisplayCanvas instance
        """
        self.canvas_manager = canvas_manager
        self.history = []  # Stack of actions that can be undone/redone
        self.current_position = -1  # Current position in history
        self.max_history = 50  # Maximum number of actions to remember
        self.batch_mode = False  # When True, actions are grouped together
        self.batch_actions = []  # Actions in the current batch
        
    def clear(self):
        """Clear the undo/redo history"""
        self.history = []
        self.current_position = -1
        
    def add_action(self, action_type, data, batch=False):
        """Add an action to the history
        
        Args:
            action_type: Type of action (e.g., 'add_element', 'move_element', etc.)
            data: Dictionary with relevant data for the action
            batch: Whether this action is part of a batch operation
        """
        if self.batch_mode and not batch:
            # End current batch if a non-batch action is added
            self.end_batch()
            
        if batch and not self.batch_mode:
            # Start a new batch
            self.start_batch()
            
        action = {
            'type': action_type,
            'data': data
        }
        self.__store_display_coordinates(action)
        
        if self.batch_mode:
            self.batch_actions.append(action)
        else:
            # If we've gone back in history and are adding a new action,
            # remove all actions after the current position
            if self.current_position < len(self.history) - 1:
                self.history = self.history[:self.current_position + 1]
                
            self.history.append(action)
            self.current_position = len(self.history) - 1
            
            # Limit history size
            if len(self.history) > self.max_history:
                self.history.pop(0)
                self.current_position -= 1
    
    def start_batch(self):
        """Start a batch of actions that will be undone/redone together"""
        self.batch_mode = True
        self.batch_actions = []
        
    def end_batch(self):
        """End the current batch and add it to history"""
        if not self.batch_mode:
            return
            
        if self.batch_actions:
            batch_action = {
                'type': 'batch',
                'data': {'actions': self.batch_actions}
            }
            
            # If we've gone back in history and are adding a new action,
            # remove all actions after the current position
            if self.current_position < len(self.history) - 1:
                self.history = self.history[:self.current_position + 1]
                
            self.history.append(batch_action)
            self.current_position = len(self.history) - 1
            
            # Limit history size
            if len(self.history) > self.max_history:
                self.history.pop(0)
                self.current_position -= 1
                
        self.batch_mode = False
        self.batch_actions = []
    
    def can_undo(self):
        """Check if undo is available"""
        return self.current_position >= 0
        
    def can_redo(self):
        """Check if redo is available"""
        return self.current_position < len(self.history) - 1
        
    def undo(self):
        """Undo the last action"""
        if not self.can_undo():
            return
            
        action = self.history[self.current_position]
        self.current_position -= 1
        
        self._execute_undo(action)
        
    def redo(self):
        """Redo the previously undone action"""
        if not self.can_redo():
            return
            
        self.current_position += 1
        action = self.history[self.current_position]
        
        self._execute_redo(action)
        
    # Canvas item coordinates bake in the current zoom level and the container
    # origin, so recorded coordinates are stored unscaled and converted back when
    # the action is replayed. Zooming between an action and its undo/redo would
    # otherwise displace the element, line or anchor being restored.
    _POINT_FIELDS = {
        'move_element': (('original_x', 'original_y'), ('new_x', 'new_y')),
        'resize_element': (('original_x', 'original_y'), ('current_x', 'current_y')),
        'delete_element': (('x', 'y'),),
    }

    _FLAT_COORD_FIELDS = {
        'modify_line': ('original_coords', 'current_coords'),
        'change_anchor_position': ('original_coords', 'new_coords', 'current_coords'),
    }

    def __convert_coordinates(self, action, convert):
        """Apply a coordinate conversion to every coordinate field of an action"""
        data = action['data']
        for x_key, y_key in self._POINT_FIELDS.get(action['type'], ()):
            if data.get(x_key) is None or data.get(y_key) is None:
                continue
            data[x_key], data[y_key] = convert(data[x_key], data[y_key])

        for key in self._FLAT_COORD_FIELDS.get(action['type'], ()):
            coords = data.get(key)
            if coords:
                data[key] = self.canvas_manager.convert_flat_coords(coords, convert)

    def __store_display_coordinates(self, action):
        """Normalize an action's canvas coordinates to unscaled display coordinates"""
        self.__convert_coordinates(action, self.canvas_manager.to_display_coords)

    def __restore_canvas_coordinates(self, action):
        """Convert an action's stored coordinates back to current canvas coordinates"""
        self.__convert_coordinates(action, self.canvas_manager.to_canvas_coords)

    def _execute_undo(self, action):
        """Execute the undo operation for a specific action"""
        self.__restore_canvas_coordinates(action)
        try:
            self.__apply_undo(action)
        finally:
            self.__store_display_coordinates(action)

    def __apply_undo(self, action):
        action_type = action['type']
        data = action['data']
        
        if action_type == 'batch':
            # Undo all actions in the batch in reverse order
            for batch_action in reversed(data['actions']):
                self._execute_undo(batch_action)
            return
            
        # Handle different action types
        if action_type == 'add_element':
            # Remove the element that was added
            element = data['element']
            if element in self.canvas_manager.canvas_elements.values():
                # Remove all connected lines
                for line_id, (line, (start_anchor, end_anchor), start_element, end_element) in list(self.canvas_manager.lines.items()):
                    if start_element == element or end_element == element:
                        self.canvas_manager.canvas.delete(line_id)
                        del self.canvas_manager.lines[line_id]

                self.canvas_manager.canvas_elements.pop(element.id, None)
                element.delete()
                
        elif action_type == 'delete_element':
            # Restore the deleted element
            element = data['element']
            # The element's canvas items are gone, so draw() falls back to _x/_y.
            if data.get('x') is not None and data.get('y') is not None:
                element._x, element._y = data['x'], data['y']
            self.canvas_manager.canvas_elements[element.id] = element
            element.draw(self.canvas_manager.canvas, self.canvas_manager.imscale)
            self.canvas_manager.setup_element_bindings(element)

            # Restore the entry in gfx_file_editor.element_map so the element
            # persists on save / reload.
            gfx_reference = data.get('gfx_reference')
            gfx_map_item = data.get('gfx_map_item')
            gfx_file_editor = getattr(self.canvas_manager, 'gfx_file_editor', None)
            if gfx_reference and gfx_map_item is not None and gfx_file_editor is not None:
                gfx_file_editor.element_map[gfx_reference] = gfx_map_item

            # Restore connected lines
            for line_data in data['lines']:
                line_id = line_data['id']
                start_anchor = line_data['start_anchor']
                end_anchor = line_data['end_anchor']
                start_element = line_data['start_element']
                end_element = line_data['end_element']
                
                # Recreate the line
                if start_anchor != 'border' and end_anchor != 'border':
                    self.canvas_manager._ProcessDisplayCanvas__create_material_line(
                        start_anchor, end_anchor, start_element, end_element, True)
                else:
                    self.canvas_manager._ProcessDisplayCanvas__create_signal_line(
                        start_anchor, end_anchor, start_element, end_element)
                
        elif action_type == 'move_element':
            # Move the element back to its original position
            element = data['element']
            original_x = data['original_x']
            original_y = data['original_y']
            
            current_x = element.x
            current_y = element.y
            
            dx = original_x - current_x
            dy = original_y - current_y
            
            element.move(dx, dy)
            self.canvas_manager.update_lines(element)
            element.last_x = original_x
            element.last_y = original_y
            
        elif action_type == 'resize_element':
            # Restore the element to its original size
            element = data['element']
            original_x = data['original_x']
            original_y = data['original_y']
            original_width = data['original_width']
            original_height = data['original_height']
            
            # Store the current dimensions for redo
            data['current_x'] = element.x
            data['current_y'] = element.y
            data['current_width'] = element.width
            data['current_height'] = element.height
            
            # Move back to original position
            current_x = element.x
            current_y = element.y
            
            dx = original_x - current_x
            dy = original_y - current_y
            
            if dx != 0 or dy != 0:
                element.move(dx, dy)
                
            # Restore original dimensions
            element.width = original_width
            element.height = original_height
            
            # Redraw with original dimensions
            element.redraw_with_new_dimensions()
            self.canvas_manager.update_lines(element)
            
        elif action_type == 'add_line':
            # Remove the line that was added
            line_id = data['line_id']
            if line_id in self.canvas_manager.lines:
                self.canvas_manager.canvas.delete(line_id)
                self.canvas_manager.canvas.delete('handle_' + str(line_id))
                del self.canvas_manager.lines[line_id]
                
        elif action_type == 'delete_line':
            # Restore the deleted line
            line_id = data['line_id']
            start_anchor = data['start_anchor']
            end_anchor = data['end_anchor']
            start_element = data['start_element']
            end_element = data['end_element']
            
            # Recreate the line
            if start_anchor != 'border' and end_anchor != 'border':
                self.canvas_manager._ProcessDisplayCanvas__create_material_line(
                    start_anchor, end_anchor, start_element, end_element, True)
            else:
                self.canvas_manager._ProcessDisplayCanvas__create_signal_line(
                    start_anchor, end_anchor, start_element, end_element)
            
                
        elif action_type == 'modify_line':
            # Restore the line to its original state
            line_id = data['line_id']
            original_coords = data['original_coords']
            
            # Store current coords for redo
            if line_id in self.canvas_manager.lines:
                data['current_coords'] = self.canvas_manager.canvas.coords(line_id)
                
                self.canvas_manager.canvas.coords(line_id, original_coords)
                self.canvas_manager.canvas.delete('handle_' + str(line_id))
                self.canvas_manager.setup_line_segment_dragging(line_id)

        elif action_type == 'change_anchor_position':
            # Restore the anchor to its original position
            anchor_id = data['anchor_id']
            element = data['element']
            original_coords = data['original_coords']
            
            # Store current coords for redo
            data['current_coords'] = self.canvas_manager.canvas.coords(anchor_id)
            
            # Restore original position
            self.canvas_manager.canvas.coords(anchor_id, original_coords)
            
            # Update anchor info
            anchor_center_x = (original_coords[0] + original_coords[2]) / 2
            anchor_center_y = (original_coords[1] + original_coords[3]) / 2
            
            if anchor_id in element.anchor_info:
                element.anchor_info[anchor_id]['position'] = (anchor_center_x, anchor_center_y)
            
            # Update element's anchor collections
            self.canvas_manager._update_element_anchor_collections(anchor_id, element)
            
            # Update connected lines
            self.canvas_manager.update_lines(element)

        elif action_type == 'change_anchor_direction':
            # Restore the anchor to its previous direction
            element = data['element']
            anchor_id = data['anchor_id']
            previous_direction = data['previous_direction']
            
            element.change_anchor_direction(anchor_id, previous_direction)
            self.canvas_manager.update_lines(element)
    
    def _execute_redo(self, action):
        """Execute the redo operation for a specific action"""
        self.__restore_canvas_coordinates(action)
        try:
            self.__apply_redo(action)
        finally:
            self.__store_display_coordinates(action)

    def __apply_redo(self, action):
        action_type = action['type']
        data = action['data']
        
        if action_type == 'batch':
            # Redo all actions in the batch in forward order
            for batch_action in data['actions']:
                self._execute_redo(batch_action)
            return
            
        # Handle different action types
        if action_type == 'add_element':
            # Re-add the element that was removed
            element = data['element']
            self.canvas_manager.canvas_elements.append(element)
            element.draw(self.canvas_manager.canvas, self.canvas_manager.imscale)
            self.canvas_manager.setup_element_bindings(element)
                
        elif action_type == 'delete_element':
            # Re-delete the restored element
            element = data['element']
            if element in self.canvas_manager.canvas_elements.values():
                # Remove all connected lines
                for line_id, (line, (start_anchor, end_anchor), start_element, end_element) in list(self.canvas_manager.lines.items()):
                    if start_element == element or end_element == element:
                        self.canvas_manager.canvas.delete(line_id)
                        del self.canvas_manager.lines[line_id]

                self.canvas_manager.canvas_elements.pop(element.id, None)
                element.delete()

            # Re-remove the entry from gfx_file_editor.element_map so the
            # element stays gone on save / reload.
            gfx_reference = data.get('gfx_reference')
            gfx_file_editor = getattr(self.canvas_manager, 'gfx_file_editor', None)
            if gfx_reference and gfx_file_editor is not None \
                    and gfx_reference in gfx_file_editor.element_map:
                data['gfx_map_item'] = gfx_file_editor.element_map.pop(gfx_reference)
                
        elif action_type == 'move_element':
            # Move the element back to its post-move position
            element = data['element']
            new_x = data['new_x']
            new_y = data['new_y']
            
            current_x = element.x
            current_y = element.y
            
            dx = new_x - current_x
            dy = new_y - current_y
            
            element.move(dx, dy)
            self.canvas_manager.update_lines(element)
            element.last_x = new_x
            element.last_y = new_y
            
        elif action_type == 'resize_element':
            # Restore the element to its post-resize dimensions
            element = data['element']
            current_x = data.get('current_x')
            current_y = data.get('current_y')
            current_width = data.get('current_width')
            current_height = data.get('current_height')
            
            if current_x is None or current_width is None:
                # If we don't have the post-resize dimensions, we can't redo
                return
                
            # Move back to resized position
            dx = current_x - element.x
            dy = current_y - element.y
            
            if dx != 0 or dy != 0:
                element.move(dx, dy)
                
            # Restore resized dimensions
            element.width = current_width
            element.height = current_height
            
            # Redraw with resized dimensions
            element.redraw_with_new_dimensions()
            self.canvas_manager.update_lines(element)
            
        elif action_type == 'add_line':
            # Re-add the line that was removed
            start_anchor = data['start_anchor']
            end_anchor = data['end_anchor']
            start_element = data['start_element']
            end_element = data['end_element']
            
            # Recreate the line
            self.canvas_manager._ProcessDisplayCanvas__create_material_line(
                start_anchor, end_anchor, start_element, end_element)
                
        elif action_type == 'delete_line':
            # Re-delete the restored line
            line_id = data['line_id']
            if line_id in self.canvas_manager.lines:
                self.canvas_manager.canvas.delete(line_id)
                self.canvas_manager.canvas.delete('handle_' + str(line_id))
                del self.canvas_manager.lines[line_id]
                
        elif action_type == 'modify_line':
            # Restore the line to its modified state
            line_id = data['line_id']
            current_coords = data.get('current_coords')
            
            if current_coords is None or line_id not in self.canvas_manager.lines:
                # If we don't have the modified coords, we can't redo
                return
                
            self.canvas_manager.canvas.coords(line_id, current_coords)
            self.canvas_manager.canvas.delete('handle_' + str(line_id))
            self.canvas_manager.setup_line_segment_dragging(line_id)

        elif action_type == 'change_anchor_direction':
            # Restore the anchor to its new direction
            element = data['element']
            anchor_id = data['anchor_id']
            new_direction = data['previous_direction']
            
            if anchor_id in element.anchor_info:
                element.anchor_info[anchor_id]['direction'] = new_direction
                self.canvas_manager.update_lines(element)


        elif action_type == 'change_anchor_position':
            # Restore the anchor to its moved position
            anchor_id = data['anchor_id']
            element = data['element']
            new_coords = data.get('new_coords')
            
            if new_coords is None:
                return
            
            # Restore moved position
            self.canvas_manager.canvas.coords(anchor_id, new_coords)
            
            # Update anchor info
            anchor_center_x = (new_coords[0] + new_coords[2]) / 2
            anchor_center_y = (new_coords[1] + new_coords[3]) / 2
            
            if anchor_id in element.anchor_info:
                element.anchor_info[anchor_id]['position'] = (anchor_center_x, anchor_center_y)
            
            # Update element's anchor collections
            self.canvas_manager._update_element_anchor_collections(anchor_id, element)
            
            # Update connected lines
            self.canvas_manager.update_lines(element)

        elif action_type == 'change_anchor_direction':
            # Restore the anchor to its new direction
            element = data['element']
            anchor_id = data['anchor_id']
            new_direction = data['new_direction']
            
            element.change_anchor_direction(anchor_id, new_direction)
            self.canvas_manager.update_lines(element)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Process Diagram Editor")
    canvas = ProcessDisplayCanvas(root)
    canvas.pack(fill='both', expand=True)
    root.geometry("1200x800")
    root.mainloop()