# -*- coding: utf-8 -*-
import hashlib

import math
from tkinter import messagebox
import warnings
import tkinter as tk
import io

from tkinter import ttk
from PIL import Image, ImageColor, ImageDraw, ImageTk

from bin.logic_file_manager import Project_File_Manager
from bin.logic_internal_database import Database
from bin.logic_pdf_render import page_count, page_size, render_page_png
from bin.logic_pdf_text import open_text
from bin.logic_profile import profile
from .logic_logger import logging
from .gui_autoscrollbar import AutoScrollbar

MAX_IMAGE_PIXELS = 1500000000  # maximum pixels in the image, use it carefully

class CanvasImage:
    """ Display and zoom image """

    HIGHLIGHT_TAG = 'canvas_page_highlight'
    HIGHLIGHT_COLOUR = '#ffff00'
    UNDERLINE_COLOUR = '#00ff00'
    STRIKEOUT_COLOUR = '#ff0000'
    EDITING_COLOUR = '#acd6fa'
    HIGHLIGHT_ALPHA = 90  # 0-255; low enough that the text underneath stays readable

    def __init__(self, placeholder, path, page_number_callback=None, file_type=Database.DRAWING, zoom_percentage_callback=None):
        """ Initialize the ImageFrame """
        self.imscale = 1.0  # scale for the canvas image zoom, public for outer classes
        self.__delta = 1.3  # zoom magnitude
        self.__filter = Image.LANCZOS  # could be: NEAREST, BILINEAR, BICUBIC and ANTIALIAS
        self.image = None
        self.__refresh_timer = None  # debounce timer for refresh_image

        # Decide if this image huge or not
        self.__huge = False  # huge or not
        self.__huge_size = 14000  # define size of the huge image
        self.__previous_state = 0  # previous state of the keyboard
        # Create ImageFrame in placeholder widget
        self.__imframe = tk.Frame(placeholder)  # placeholder of the ImageFrame object
        # Vertical and horizontal scrollbars for canvas
        hbar = AutoScrollbar(self.__imframe, orient='horizontal')
        vbar = AutoScrollbar(self.__imframe, orient='vertical')
        hbar.grid(row=1, column=0, sticky='we')
        vbar.grid(row=0, column=1, sticky='ns')

        # Create canvas and bind it with scrollbars. Public for outer classes
        self.canvas = tk.Canvas(self.__imframe, highlightthickness=0,
                                xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        self.canvas_up = True
        
        self.canvas.grid(row=0, column=0, sticky='nswe')
        self.canvas.update()  # wait till canvas is created
        hbar.configure(command=self.__scroll_x)  # bind scrollbars to the canvas
        vbar.configure(command=self.__scroll_y)
        # Bind events to the Canvas
        self.canvas.bind('<Configure>', lambda event: self.__show_image())  # canvas is resized
        self.canvas.bind('<ButtonPress-3>', self.__move_from)  # remember canvas position
        self.canvas.bind('<B3-Motion>',     self.__move_to)  # move canvas to the new position
        self.canvas.bind('<Control-MouseWheel>', self.__wheel)  # zoom for Windows and MacOS, but not Linux
        self.canvas.bind('<MouseWheel>', self.__vertical_scroll)  # zoom for Windows and MacOS, but not Linux
        self.canvas.bind('<Shift-MouseWheel>', self.__horizontal_scroll)
        self.canvas.bind('<Button-5>',   self.__wheel)  # zoom for Linux, wheel scroll down
        self.canvas.bind('<Button-4>',   self.__wheel)  # zoom for Linux, wheel scroll up

        # Handle keystrokes in idle mode, because program slows down on a weak computers,
        # when too many key stroke events in the same time
        self.canvas.bind('<Key>', lambda event: self.canvas.after_idle(self.__keystroke, event))
        

        self.page_number_callback = page_number_callback
        self.zoom_percentage_callback = zoom_percentage_callback
        self.document_or_page_number_change_callback = None
        self.image_changed_callback = None

        self.previous_pno = -1
        self.previous_path = ''

        self.styled_highlights = {}
        self.__highlight_version = 0  # bumped on every add/remove so the overlay redraws
        self.__highlight_signature = None
        self.__highlight_overlay_image = None  # PhotoImage ref, dropped by tk if not held

        self.file_type = file_type
        self.canvas_image = None
        self.canvas_image_id = None  # Track canvas image item for cleanup
        self.previous_imagetk = None  # Track previous PhotoImage for cleanup
        self.open_doc(path)
        
        self.moving_canvas = False
        
    @staticmethod
    def __to_hex(colour, default):
        """Accept a tkinter colour name/hex or an (r, g, b) triple in 0-1 or 0-255."""
        if colour is None:
            return default
        if isinstance(colour, str):
            return colour
        try:
            r, g, b = tuple(colour)[:3]
        except (TypeError, ValueError):
            logging.warning('Invalid highlight colour {}'.format(colour))
            return default
        scale = 1 if max(r, g, b) > 1 else 255
        return '#{:02x}{:02x}{:02x}'.format(
            *(max(0, min(255, int(round(c * scale)))) for c in (r, g, b)))

    def __add_highlight(self, name, rect, style, colour):
        if not self.canvas_up:
            return
        try:
            x0, y0, x1, y1 = (float(v) for v in tuple(rect)[:4])
        except (TypeError, ValueError):
            logging.error('Invalid highlight rect {}'.format(rect))
            return
        self.styled_highlights.setdefault(name, []).append({
            'pno': self.pno,
            'rect': (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)),
            'style': style,
            'colour': colour,
        })
        self.__highlight_version += 1

    def __clear_highlight_group(self, name, refresh_image):
        if not self.canvas_up:
            return
        group = self.styled_highlights.get(name)
        if not group:
            return
        group.clear()
        self.__highlight_version += 1
        if refresh_image: self.refresh_image()

    def _reset_highlights(self):
        """Drop every highlight, e.g. when a different document is opened."""
        self.styled_highlights = {}
        self.__highlight_version += 1
        self.__highlight_signature = None
        self.__highlight_overlay_image = None
        self.canvas.delete(self.HIGHLIGHT_TAG)

    def __to_rgba(self, colour, alpha):
        """Turn a tkinter colour name/hex into an (r, g, b, alpha) tuple for PIL."""
        try:
            r, g, b = ImageColor.getrgb(colour)[:3]
        except (ValueError, AttributeError):
            logging.warning('Invalid highlight colour {}'.format(colour))
            r, g, b = ImageColor.getrgb(self.HIGHLIGHT_COLOUR)[:3]
        return (r, g, b, alpha)

    def __draw_highlights(self):
        """Rebuild the highlight overlay for the current page in canvas coordinates."""
        if not self.canvas_up:
            return
        box_image = self.canvas.coords(self.container)
        if not box_image:
            return
        box_canvas = (self.canvas.canvasx(0), self.canvas.canvasy(0),
                      self.canvas.canvasx(self.canvas.winfo_width()),
                      self.canvas.canvasy(self.canvas.winfo_height()))
        signature = (self.pno, self.imscale, box_image[0], box_image[1],
                     tuple(round(v) for v in box_canvas), self.__highlight_version)
        if signature == self.__highlight_signature:
            return
        self.__highlight_signature = signature
        self.canvas.delete(self.HIGHLIGHT_TAG)
        self.__highlight_overlay_image = None
        # One RGBA image over the visible area gives a real alpha blend (like the
        # selection rectangle) instead of the stipple checkerboard, which made the
        # text underneath unreadable.
        overlay_width = int(box_canvas[2] - box_canvas[0])
        overlay_height = int(box_canvas[3] - box_canvas[1])
        overlay = None
        drawing = None
        drawn = False
        for group in self.styled_highlights.values():
            for mark in group:
                if mark['pno'] != self.pno:
                    continue
                rect = mark['rect']
                x0 = rect[0] * self.imscale + box_image[0]
                y0 = rect[1] * self.imscale + box_image[1]
                x1 = rect[2] * self.imscale + box_image[0]
                y1 = rect[3] * self.imscale + box_image[1]
                if mark['style'] == 'underline':
                    self.canvas.create_line(x0, y1, x1, y1, fill=mark['colour'],
                                            tags=self.HIGHLIGHT_TAG)
                    drawn = True
                elif mark['style'] == 'strikeout':
                    y = (y0 + y1) / 2
                    self.canvas.create_line(x0, y, x1, y, fill=mark['colour'],
                                            tags=self.HIGHLIGHT_TAG)
                    drawn = True
                else:
                    if overlay_width <= 0 or overlay_height <= 0:
                        continue
                    rx0 = max(int(x0 - box_canvas[0]), 0)
                    ry0 = max(int(y0 - box_canvas[1]), 0)
                    rx1 = min(int(x1 - box_canvas[0]), overlay_width - 1)
                    ry1 = min(int(y1 - box_canvas[1]), overlay_height - 1)
                    if rx1 < rx0 or ry1 < ry0:
                        continue  # scrolled out of the visible area
                    if overlay is None:
                        overlay = Image.new('RGBA', (overlay_width, overlay_height),
                                            (0, 0, 0, 0))
                        drawing = ImageDraw.Draw(overlay)
                    drawing.rectangle([rx0, ry0, rx1, ry1],
                                      fill=self.__to_rgba(mark['colour'], self.HIGHLIGHT_ALPHA))
        if overlay is not None:
            self.__highlight_overlay_image = ImageTk.PhotoImage(overlay)
            self.canvas.create_image(box_canvas[0], box_canvas[1], anchor='nw',
                                     image=self.__highlight_overlay_image,
                                     tags=self.HIGHLIGHT_TAG)
            drawn = True
        if drawn:
            self.canvas.lower(self.HIGHLIGHT_TAG)  # keep the overlay under the tools...
            if self.canvas_image_id is not None:
                self.canvas.lower(self.canvas_image_id)  # ...but over the page image

    def mark_with_style(self, name, rect, stroke, underline=False):
        self.__add_highlight(name, rect, 'underline' if underline else 'highlight',
                             self.__to_hex(stroke, self.HIGHLIGHT_COLOUR))

    def remove_all_styled_highlights(self):
        if not self.canvas_up:
            return
        # snapshot keys — remove_styled_highlight mutates self.styled_highlights
        for name in list(self.styled_highlights.keys()):
            self.remove_styled_highlight(name)

    def remove_styled_highlight(self, name):
        if not self.canvas_up:
            return
        # Drop the tracking entry so pending-approval highlighters
        # (which gate on `id in self.styled_highlights`) will redraw it next pass.
        if self.styled_highlights.pop(name, None) is None:
            return
        self.__highlight_version += 1

    def mark_with_highlight(self, rect, refresh_image=True):
        self.__add_highlight('highlight', rect, 'highlight', self.HIGHLIGHT_COLOUR)
        if refresh_image: self.refresh_image()

    def mark_with_editing(self, rect, refresh_image=True):
        self.__add_highlight('editing', rect, 'highlight', self.EDITING_COLOUR)
        if refresh_image: self.refresh_image()

    def mark_with_strikeout(self, rect, refresh_image=True):
        self.__add_highlight('strikeout', rect, 'strikeout', self.STRIKEOUT_COLOUR)
        if refresh_image: self.refresh_image()

    def mark_with_underline(self, rect, refresh_image=True):
        self.__add_highlight('underline', rect, 'underline', self.UNDERLINE_COLOUR)
        if refresh_image: self.refresh_image()

    def remove_mark_with_highlight(self, refresh_image=True):
        self.__clear_highlight_group('highlight', refresh_image)

    def remove_mark_with_strikeout(self, refresh_image=True):
        self.__clear_highlight_group('strikeout', refresh_image)

    def remove_mark_with_underline(self, refresh_image=True):
        self.__clear_highlight_group('underline', refresh_image)

    def remove_mark_with_editing(self, refresh_image=True):
        self.__clear_highlight_group('editing', refresh_image)

    def move_to_coordinate_fractions(self, x_fraction, y_fraction):
        """ Scroll to horizontal and vertical fraction coordinates and show image """
        self.canvas.xview_moveto(x_fraction)
        self.canvas.yview_moveto(y_fraction)
        self.__show_image()


    def refresh_image(self):
        """Refresh image with 200ms debounce"""
        if self.__refresh_timer is not None:
            self.canvas.after_cancel(self.__refresh_timer)
        self.__refresh_timer = self.canvas.after(200, self.__show_image)


    def open_doc(self, path):
        if self.file_type == Database.IMAGE:
            self.open_image_doc(path)
        else:
            self.open_pdf_doc(path)


    def open_pdf_doc(self, path):

        self.path = path  # path to the image, should be public for outer classes
        self.imscale = 1.0  # scale for the canvas image zoom, public for outer classes

        logging.info('Open image: {}'.format(self.path))
        self.doc = None  # only the IMAGE file type keeps a document here
        self.open_text_doc(path)

        self.page_count = page_count(path)
        self.pages = [None] * self.page_count
        self._reset_highlights()
        
        self.pno = 0
        image, r = self.get_page(0 ,0 ,0 ,0 ,1 ,full_page=True)
        _,_,self.imwidth, self.imheight = r  # public for outer classes
        
        self.__min_side = min(self.imwidth, self.imheight)  # get the smaller image side
        # Create image pyramid
        # Set ratio coefficient for image pyramid
        
        #print('\rCreating image pyramid: {j} from {n}'.format(j=j, n=n), end='')
        #print('\r' + (40 * ' ') + '\r', end='')  # hide printed string
        # Put image into container rectangle and use it to set proper coordinates to the image
        self.container = self.canvas.create_rectangle((0, 0, self.imwidth, self.imheight), width=0)
        # Create MD5 hash sum from the image. Public for outer classes
        self.md5 = hashlib.md5(image).hexdigest()
        self.__showing_vertical_scroll = False
        self.__show_image()  # show image on the canvas
        self.canvas.focus_set()  # set focus on the canvas


    def open_text_doc(self, path):
        """(Re)open the pypdfium2 handle used for character extraction and search."""
        self.close_text_doc()
        self.text_doc = open_text(path)

    def close_text_doc(self):
        text_doc = getattr(self, 'text_doc', None)
        if text_doc is not None:
            text_doc.close()
        self.text_doc = None

    def close_pdf_doc(self):
        """Release every handle on the PDF so it can be rewritten in place."""
        doc = getattr(self, 'doc', None)
        if hasattr(doc, 'close'):
            doc.close()
        self.doc = None
        self.close_text_doc()

    def reload_pdf_doc(self):
        """Re-open the PDF after it was rewritten on disk, e.g. by a page rotation."""
        self.close_pdf_doc()
        self.open_text_doc(self.path)
        self.page_count = page_count(self.path)

    def open_image_doc(self, path):
        # Opens images files within the specified path. All the images are named as 0.png, 1.png, 2.png, etc.
        self.path = path  # path to the image, should be public for outer classes
        self.imscale = 1.0  # scale for the canvas image zoom, public for outer classes

        logging.info('Open image: {}'.format(self.path))
        self.doc = Project_File_Manager.get_drawing_image_files(path)
        self.close_text_doc()

        self.page_count = len(self.doc)
        self.pages = [None] * self.page_count
        self.pno = 0
        self._reset_highlights()

        if self.page_number_callback:
                page_number = self.pno + 1
                self.page_number_callback(page_number, self.page_count)

        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS  # suppress DecompressionBombError for big image
        with warnings.catch_warnings():  # suppress DecompressionBombWarning for big image
            warnings.simplefilter('ignore')
            if self.pages[self.pno] is not None:
                page = self.pages[self.pno]
            else:
                self.pages[self.pno] = self.doc[self.pno]
                page = self.pages[self.pno]
            temp_image = Image.open(page)  # open image, but down't load it into RAM
            self.imwidth, self.imheight = temp_image.size  # public for outer classes
            if hasattr(self, 'image') and self.image is not None:
                try:
                    self.image.close()
                except:
                    pass
            self.image = temp_image
        if self.imwidth * self.imheight > self.__huge_size * self.__huge_size and \
                        self.image.tile[0][0] == 'raw':  # only raw images could be tiled
            self.__huge = True  # image is huge
            self.__offset = self.image.tile[0][2]  # initial tile offset
            self.__tile = [self.image.tile[0][0],  # it have to be 'raw'
                           [0, 0, self.imwidth, 0],  # tile extent (a rectangle)
                           self.__offset,
                           self.image.tile[0][3]]  # list of arguments to the decoder

        self.__min_side = min(self.imwidth, self.imheight)  # get the smaller image side
        # Create image pyramid
        if self.pages[self.pno] is not None:
            page = self.pages[self.pno]
        else:
            self.pages[self.pno] = self.doc[self.pno]
            page = self.pages[self.pno]
        self.__pyramid = [self.smaller()] if self.__huge else [Image.open(page)]
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
        # Put image into container rectangle and use it to set proper coordinates to the image
        self.container = self.canvas.create_rectangle((0, 0, self.imwidth, self.imheight), width=0)
        self.__show_image()  # show image on the canvas
        self.canvas.focus_set()  # set focus on the canvas


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
            if self.pages[self.pno] is not None:
                page = self.pages[self.pno]
            else:
                self.pages[self.pno] = self.doc[self.pno]
                page = self.pages[self.pno]
            self.image = Image.open(page)  # reopen / reset image
            self.image.size = (self.imwidth, band)  # set size of the tile band
            self.image.tile = [self.__tile]  # set tile
            cropped = self.image.crop((0, 0, self.imwidth, band))  # crop tile band
            image.paste(cropped.resize((w, int(band * k)+1), self.__filter), (0, int(i * k)))
            i += band
        print('\r' + (40 * ' ') + '\r', end='')  # hide printed string
        return image



    def subscribe_to_document_or_page_number_change(self, callback):
        self.document_or_page_number_change_callback = callback
        self.document_or_page_number_change_callback()


    def post_document_or_page_number_change(self):
        if (self.previous_pno == self.pno and
            self.previous_path == self.path ):
            return 
        #image_bytes, _ = self.get_page(0,0,0,0,2,True)
        #self.full_page = Image.open(io.BytesIO(image_bytes))
        self.previous_pno = self.pno
        self.previous_path = self.path


        if self.document_or_page_number_change_callback:
            self.document_or_page_number_change_callback()


    def redraw_figures(self):
        """ Dummy function to redraw figures in the children classes """
        pass

    def refresh_rois(self):
        pass

    def grid(self, **kw):
        """ Put CanvasImage widget on the parent widget """
        self.__imframe.grid(**kw)  # place CanvasImage widget on the grid
        self.__imframe.grid(sticky='nswe')  # make frame container sticky
        self.__imframe.rowconfigure(0, weight=1)  # make canvas expandable
        self.__imframe.columnconfigure(0, weight=1)

    def pack(self, **kw):
        """ Exception: cannot use pack with this widget """
        raise Exception('Cannot use pack with the widget ' + self.__class__.__name__)

    def place(self, **kw):
        """ Exception: cannot use place with this widget """
        raise Exception('Cannot use place with the widget ' + self.__class__.__name__)

    def __vertical_scroll(self, event):
        page_changed = False
        if self.__showing_vertical_scroll:
            self.canvas.yview_scroll(int(-1*(event.delta/120)), tk.UNITS)
        else:
            page_changed = self.__change_page(event)
        if page_changed: self.__refresh_container_size()
        self.__show_image()  # redraw the image
        if page_changed: self.refresh_rois()


    def __horizontal_scroll(self, event):
        self.canvas.xview_scroll(int(-1*(event.delta/120)), tk.UNITS)
        self.__show_image()  # redraw the image
        

    def __change_page(self, event):
        if self.file_type == Database.IMAGE:
            lastPageIndex = len(self.doc) - 1
        else:
            lastPageIndex = self.page_count - 1
        firstPageIndex = 0
        if event.num == 4 or event.delta == 120:  # scroll up to change page
            if (self.pno <= firstPageIndex):
                self.pno = firstPageIndex
                return False

            self.pno = self.pno - 1
            return True 
            

        if event.num == 5 or event.delta == -120:  # scroll down to change page
            if (self.pno >= lastPageIndex):
                self.pno = lastPageIndex
                return False

            self.pno = self.pno + 1
            return True 

        return False


    def go_to_page(self, page_numnber):
        self.pno = page_numnber - 1

        self.__refresh_container_size()
        
        # Clear cache of other pages to prevent memory buildup
        self.clear_page_cache(keep_current=True)
        
        self.__show_image()  # redraw the image
        self.refresh_rois()
        if self.document_or_page_number_change_callback:
            self.document_or_page_number_change_callback()


    def __refresh_container_size(self):
        """ Refresh the container rectangle for the canvas image if the page size is changed """
        if self.file_type != Database.IMAGE:
            _, r = self.get_page(0 ,0 ,0 ,0 ,1 ,full_page=True)
            width, height = r[2], r[3]    
        else:
            Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS  # suppress DecompressionBombError for big image
            with warnings.catch_warnings():  # suppress DecompressionBombWarning for big image
                warnings.simplefilter('ignore')
                if self.pages[self.pno] is not None:
                    page = self.pages[self.pno]
                else:
                    self.pages[self.pno] = self.doc[self.pno]
                    page = self.pages[self.pno]
                image = Image.open(page)  # open image, but down't load it into RAM
            width, height = image.size  
        if self.imwidth == width and self.imheight == height:
            return
        
        self.imscale = 1.0
        self.imwidth, self.imheight = width, height  # public for outer classes
        self.__ratio = max(self.imwidth, self.imheight) / self.__huge_size if self.__huge else 1.0
        self.__curr_img = 0  # current image from the pyramid
        self.zoom_scale = self.imscale * self.__ratio  # image pyramide scale
        
        self.__min_side = min(self.imwidth, self.imheight)  # get the smaller image side
        # Create image pyramid
        # Set ratio coefficient for image pyramid
        
        #print('\rCreating image pyramid: {j} from {n}'.format(j=j, n=n), end='')
        #print('\r' + (40 * ' ') + '\r', end='')  # hide printed string
        # Put image into container rectangle and use it to set proper coordinates to the image
        self.container = self.canvas.create_rectangle((0, 0, self.imwidth, self.imheight), width=0)


    # noinspection PyUnusedLocal
    def __scroll_x(self, *args, **kwargs):
        """ Scroll canvas horizontally and redraw the image """
        self.canvas.xview(*args)  # scroll horizontally
        self.__show_image()  # redraw the image

    # noinspection PyUnusedLocal
    def __scroll_y(self, *args, **kwargs):
        """ Scroll canvas vertically and redraw the image """
        self.canvas.yview(*args)  # scroll vertically
        self.__show_image()  # redraw the image


    def set_image_changed_callback(self, func):
        self.image_changed_callback = func
    

    def __show_image(self):
        """ Show image on the Canvas. Implements correct image zoom almost like in Google Maps """
        if not self.canvas_up:
            return
        box_image = self.canvas.coords(self.container)  # get image area
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
            if self.file_type == Database.IMAGE:
                if self.__huge and self.__curr_img < 0:  # show huge image, which does not fit in RAM
                    h = int((y2 - y1) / self.imscale)  # height of the tile band
                    self.__tile[1][3] = h  # set the tile band height
                    self.__tile[2] = self.__offset + self.imwidth * int(y1 / self.imscale) * 3
                    self.image.close()
                    if self.pages[self.pno] is not None:
                        page = self.pages[self.pno]
                    else:
                        self.pages[self.pno] = self.doc[self.pno]
                        page = self.pages[self.pno]
                    self.image = Image.open(page)  # reopen / reset image
                    self.image.size = (self.imwidth, h)  # set size of the tile band
                    self.image.tile = [self.__tile]
                    image = self.image.crop((int(x1 / self.imscale), 0, int(x2 / self.imscale), h))
                    if self.zoom_percentage_callback:
                        self.zoom_scale = self.imscale * self.__ratio  # image pyramide scale
                        self.zoom_percentage_callback(self.zoom_scale*100)
                    if self.page_number_callback:
                        page_number = self.pno + 1
                        self.page_number_callback(page_number, self.page_count)
                else:  # show normal image
                    if self.pages[self.pno] is not None:
                        page = self.pages[self.pno]
                    else:
                        self.pages[self.pno] = self.doc[self.pno]
                        page = self.pages[self.pno]
                    self.__pyramid = [self.smaller()] if self.__huge else [Image.open(page)]
                    self.image = self.__pyramid[max(0, self.__curr_img)]
                    image = self.image.crop(  # crop current img from pyramid
                                    (int(x1 / self.zoom_scale), int(y1 / self.zoom_scale),
                                    int(x2 / self.zoom_scale), int(y2 / self.zoom_scale)))
                    if self.zoom_percentage_callback:
                        self.zoom_percentage_callback(self.zoom_scale*100)
                    if self.page_number_callback:
                        page_number = self.pno + 1
                        self.page_number_callback(page_number, self.page_count)
                self.canvas_image = image.resize((int(x2 - x1), int(y2 - y1)), self.__filter)
            else:
                img, _ = self.get_page(x1,y1,x2,y2,self.imscale)
                self.canvas_image = Image.open(io.BytesIO(img))
            
            # Clean up old canvas image item
            if self.canvas_image_id is not None:
                try:
                    self.canvas.delete(self.canvas_image_id)
                except:
                    pass
            
            # Clean up old PhotoImage reference
            if self.previous_imagetk is not None:
                try:
                    del self.previous_imagetk
                except:
                    pass
            
            imagetk = ImageTk.PhotoImage(self.canvas_image)
            self.canvas_image_id = self.canvas.create_image(max(box_canvas[0], box_img_int[0]),
                                               max(box_canvas[1], box_img_int[1]),
                                               anchor='nw', image=imagetk)
            self.canvas.lower(self.canvas_image_id)  # set image into background
            self.canvas.imagetk = imagetk  # keep an extra reference to prevent garbage-collection
            self.previous_imagetk = imagetk
            if self.image_changed_callback:
                self.image_changed_callback()

        self.__draw_highlights()


    def __move_from(self, event):
        """ Remember previous coordinates for scrolling with the mouse """
        self.canvas.scan_mark(event.x, event.y)

    def __move_to(self, event):
        """ Drag (move) canvas to the new position """
        self.moving_canvas = True
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        self.__show_image()  # zoom tile and show it on the canvas

    def move_from(self, event):
        """ Function for children class in use """
        self.__move_from(event)

    def move_to(self, event):
        """ Function for children class in use """
        self.__move_to(event)


    def clear_page_cache(self, keep_current=True):
        """Clear page cache to free memory, optionally keeping current page"""
        if not self.canvas_up:
            return
        for i in range(len(self.pages)):
            if keep_current and i == self.pno:
                continue
            if self.pages[i] is not None:
                self.pages[i] = None
    
    def refresh_pages(self):
        """Refreshes all the page"""
        self.__highlight_signature = None
        self.__refresh_container_size()
        self.__show_image()


    # ------------------------------------------------------------------------------
    # read the page data
    # ------------------------------------------------------------------------------
    def get_page(self,x0 ,y0 ,x1 ,y1 ,zoom_level ,full_page=False):
        """Return a tkinter.PhotoImage or a PNG image for a document page number.
        :arg int pno: 0-based page number
        :arg zoom: top-left of old clip rect, and one of -1, 0, +1 for dim. x or y
                to indicate the arrow key pressed
        :arg max_size: (width, height) of available image area
        :arg bool first: if True, we cannot use tkinter
        """

        source = self.path
        width, height = page_size(source, self.pno)

        if not full_page:
            # callback for document navigation interface
            if self.page_number_callback:
                page_number = self.pno + 1
                self.page_number_callback(page_number, self.page_count)

            self.post_document_or_page_number_change() # used to save roi 
                
            if self.zoom_percentage_callback:
                self.zoom_percentage_callback(zoom_level*100)

        if full_page:
            clip = None
        else:
            clip = (x0/zoom_level ,y0/zoom_level ,x1/zoom_level ,y1/zoom_level )
        print('Getting page at zoom level: {}'.format(zoom_level))
        img = render_page_png(source, self.pno, zoom=zoom_level, clip=clip,
                              annots=False)
        return img, (0, 0, width, height)  # return image, clip position
    

    # ------------------------------------------------------------------------------
    # read the page data
    # ------------------------------------------------------------------------------
    def get_ocr_page(self,x0 ,y0 ,x1 ,y1 ,zoom_level ,full_page=False):
        """Return a tkinter.PhotoImage or a PNG image for a document page number.
        :arg int pno: 0-based page number
        :arg zoom: top-left of old clip rect, and one of -1, 0, +1 for dim. x or y
                to indicate the arrow key pressed
        :arg max_size: (width, height) of available image area
        :arg bool first: if True, we cannot use tkinter
        """
        width, height = page_size(self.path, self.pno)

        if full_page:
            clip = None
        else:
            clip = (x0/zoom_level ,y0/zoom_level ,x1/zoom_level ,y1/zoom_level )
        print('Getting page at zoom level: {}'.format(zoom_level))
        img = render_page_png(self.path, self.pno, zoom=zoom_level, clip=clip,
                              thin_lines=True, annots=False)
        return img, (0, 0, width, height)  # return image, clip position
        

    def outside(self, x, y):
        """ Checks if the point (x,y) is outside the image area """
        bbox = self.canvas.coords(self.container)  # get image area
        if bbox[0] < x < bbox[2] and bbox[1] < y < bbox[3]:
            return False  # point (x,y) is inside the image area
        else:
            return True  # point (x,y) is outside the image area

    def __wheel(self, event):
        """ Zoom with mouse wheel """
        x = self.canvas.canvasx(event.x)  # get coordinates of the event on the canvas
        y = self.canvas.canvasy(event.y)
        if self.outside(x, y): return  # zoom only inside image area
        scale = 1.0
        # Respond to Linux (event.num) or Windows (event.delta) wheel event
        if event.num == 5 or event.delta == -120:  # scroll down, zoom out, smaller
            if round(self.__min_side * self.imscale) < 30: return  # image is less than 30 pixels
            self.imscale /= self.__delta
            scale        /= self.__delta
        if event.num == 4 or event.delta == 120:  # scroll up, zoom in, bigger
            i = float(min(self.canvas.winfo_width(), self.canvas.winfo_height()) >> 1)
            if i < self.imscale: return  # 1 pixel is bigger than the visible area
            self.imscale *= self.__delta
            scale        *= self.__delta

        if self.file_type == Database.IMAGE:
            k = self.imscale * self.__ratio  # temporary coefficient
            self.__curr_img = min((-1) * int(math.log(k, self.__reduction)), len(self.__pyramid) - 1)
            self.zoom_scale = k * math.pow(self.__reduction, max(0, self.__curr_img))
        
        self.canvas.scale('all', x, y, scale, scale)  # rescale all objects
        # Redraw some figures before showing image on the screen
        self.redraw_figures()  # method for child classes
        self.__show_image()

    def zoom(self, percentage):
        self.__zoom(percentage)
        self.__show_image()


    def __zoom(self, percentage):
        if self.canvas_up == False:
            return

        box_canvas = (self.canvas.canvasx(0),  # get visible area of the canvas
                      self.canvas.canvasy(0),
                      self.canvas.canvasx(self.canvas.winfo_width()),
                      self.canvas.canvasy(self.canvas.winfo_height()))
        x =  int((box_canvas[0] + box_canvas[2])/2)    
        y =  int((box_canvas[1] + box_canvas[3])/2)   

        scale =  float(percentage) / 100

        canvas_scale = scale / self.imscale

        self.canvas.scale('all', x, y, canvas_scale, canvas_scale)  # rescale all objects
        
        # Redraw some figures before showing image on the screen
        self.redraw_figures()  # method for child classes

        self.imscale = scale

        if self.file_type == Database.IMAGE:
            k = self.imscale * self.__ratio  # temporary coefficient
            self.__curr_img = min((-1) * int(math.log(k, self.__reduction)), len(self.__pyramid) - 1)
            self.zoom_scale = k * math.pow(self.__reduction, max(0, self.__curr_img))


    def __keystroke(self, event):
        """ Scrolling with the keyboard.
            Independent from the language of the keyboard, CapsLock, <Ctrl>+<key>, etc. """
        if event.state - self.__previous_state == 4:  # means that the Control key is pressed
            pass  # do nothing if Control key is pressed
        else:
            self.__previous_state = event.state  # remember the last keystroke state
            # Up, Down, Left, Right keystrokes
            self.keycodes = {}  # init key codes
            self.keycodes = {
                'd': [68, 39, 102],
                'a': [65, 37, 100],
                'w': [87, 38, 104],
                's': [83, 40,  98],
            }
            if event.keycode in self.keycodes['d']:  # scroll right, keys 'd' or 'Right'
                self.__scroll_x('scroll',  1, 'unit', event=event)
            elif event.keycode in self.keycodes['a']:  # scroll left, keys 'a' or 'Left'
                self.__scroll_x('scroll', -1, 'unit', event=event)
            elif event.keycode in self.keycodes['w']:  # scroll up, keys 'w' or 'Up'
                self.__scroll_y('scroll', -1, 'unit', event=event)
            elif event.keycode in self.keycodes['s']:  # scroll down, keys 's' or 'Down'
                self.__scroll_y('scroll',  1, 'unit', event=event)


    def destroy(self):
        """ ImageFrame destructor """
        logging.info('Close image: {}'.format(self.path))
        
        # Clean up canvas image items
        if self.canvas_image_id is not None:
            try:
                self.canvas.delete(self.canvas_image_id)
            except:
                pass
        
        # Clean up PhotoImage references
        if hasattr(self, 'previous_imagetk') and self.previous_imagetk is not None:
            try:
                del self.previous_imagetk
            except:
                pass
        
        if hasattr(self.canvas, 'imagetk'):
            try:
                del self.canvas.imagetk
            except:
                pass
        
        # Clean up canvas_image
        if self.canvas_image is not None:
            try:
                self.canvas_image.close()
            except:
                pass
        
        # Clean up all cached pages
        if hasattr(self, 'pages'):
            for page in self.pages:
                if page is not None:
                    try:
                        del page
                    except:
                        pass
        
        # Clean up image if it exists
        if hasattr(self, 'image') and self.image is not None:
            try:
                self.image.close()
            except:
                pass
        
        # Close document
        if self.file_type != Database.IMAGE:
            self.close_pdf_doc()
        
        self.canvas_up = False
        self.canvas.destroy()
        self.__imframe.destroy()
