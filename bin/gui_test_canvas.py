import os
import math
import hashlib
from threading import Thread
import warnings
import cv2
import numpy as np
import tkinter as tk
from bin.logic_profile import profile
from tkinter import ttk
from PIL import Image, ImageTk
try:
    from .logic_logger import logging
    from .gui_autoscrollbar import AutoScrollbar
except:
    from logic_logger import logging
    from gui_autoscrollbar import AutoScrollbar

MAX_IMAGE_PIXELS =  2500000000  # maximum pixels in the image, use it carefully
                    
class TestCanvasImage:
    """ Display and zoom image """
    def __init__(self, placeholder, image_array, template_image:Image, image_processed_callback):
        """ Initialize the ImageFrame """
        self.imscale = 1.0  # scale for the canvas image zoom, public for outer classes
        self.__delta = 1.3  # zoom magnitude
        self.__template_curX = 0 
        self.__template_curY = 0
        self.__filter = Image.LANCZOS  # could be: NEAREST, BILINEAR, BICUBIC and ANTIALIAS
        self.__previous_state = 0  # previous state of the keyboard
        img = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
        self.__image_array = img  # path to the image, should be public for outer classes
        self.__template_image_shown = False
        self.__template_image = Image.fromarray(template_image)
        self.__placed_template_images = []
        self.__shown_template_image = None 
        self.__template_image_id = None
        self.__running_template_test = False
        # Decide if this image huge or not
        self.__huge = False  # huge or not
        self.__huge_size = 20000  # define size of the huge image
        self.__band_width = 1024  # width of the tile band
        self.__image = None
        self.__imframe = None 
        self.__placeholder = placeholder
        self.__image_processed_callback = image_processed_callback
        self.__start_open_image_thread()
        

    def __start_open_image_thread(self):
        db_thread=Thread(target=self.__open_image,args=(self.__image_array,))
        self.__open_image_done = False 
        
        db_thread.start()
        self.__placeholder.after(500,self.__check_open_image_done)


    def __check_open_image_done(self):
        if self.__open_image_done:
            if self.__image_processed_callback:
                self.__image_processed_callback()
            self.__create_image_canvas()
        else:
            self.__placeholder.after(500,self.__check_open_image_done)


    def __create_image_canvas(self):
        
        # Create ImageFrame in placeholder widget
        self.__imframe = ttk.Frame(self.__placeholder)  # placeholder of the ImageFrame object
        self.grid()
        # Vertical and horizontal scrollbars for canvas
        hbar = AutoScrollbar(self.__imframe, orient='horizontal')
        vbar = AutoScrollbar(self.__imframe, orient='vertical')
        hbar.grid(row=1, column=0, sticky='we')
        vbar.grid(row=0, column=1, sticky='ns')
        # Create canvas and bind it with scrollbars. Public for outer classes
        self.canvas = tk.Canvas(self.__imframe, highlightthickness=0,
                                xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        self.canvas.grid(row=0, column=0, sticky='nswe')
        self.canvas.update()  # wait till canvas is created
        hbar.configure(command=self.__scroll_x)  # bind scrollbars to the canvas
        vbar.configure(command=self.__scroll_y)
        # Bind events to the Canvas
        self.canvas.bind('<Configure>', lambda _: self.__show_image())  # canvas is resized
        self.canvas.bind('<ButtonPress-3>', self.__move_from)  # remember canvas position
        self.canvas.bind('<B3-Motion>',     self.__move_to)  # move canvas to the new position
        self.canvas.bind('<MouseWheel>', self.__wheel)  # zoom for Windows and MacOS, but not Linux
        self.canvas.bind('<Button-5>',   self.__wheel)  # zoom for Linux, wheel scroll down
        self.canvas.bind('<Button-4>',   self.__wheel)  # zoom for Linux, wheel scroll up
        self.canvas.bind('<Enter>' , self.__enter)
        self.canvas.bind('<Leave>' , self.__leave)
        # Handle keystrokes in idle mode, because program slows down on a weak computers,
        # when too many key stroke events in the same time
        self.canvas.bind('<Key>', lambda event: self.canvas.after_idle(self.__keystroke, event))

        
        # Put image into container rectangle and use it to set proper coordinates to the image
        self.container = self.canvas.create_rectangle((0, 0, self.imwidth, self.imheight), width=0)
        self.__show_image()  # show image on the canvas
        self.canvas.focus_set()  # set focus on the canvas
        self.__placeholder.update()

    def __open_image(self, array_image):
        if self.__image:
            self.__image.close()
            map(lambda i: i.close, self.__pyramid)  # close all pyramid images
            del self.__pyramid[:]  # delete pyramid list
            del self.__pyramid  # delete pyramid variable
        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS  # suppress DecompressionBombError for big image
        with warnings.catch_warnings():  # suppress DecompressionBombWarning for big image
            warnings.simplefilter('ignore')
            self.__image = Image.fromarray(array_image)  # open image, but down't load it into RAM
        self.imwidth, self.imheight = self.__image.size  # public for outer classes
        if self.imwidth * self.imheight > self.__huge_size * self.__huge_size and \
                        hasattr(self.__image, 'tile') and self.__image.tile[0][0] == 'raw':  # only raw images could be tiled
            self.__huge = True  # image is huge
            self.__offset = self.__image.tile[0][2]  # initial tile offset
            self.__tile = [self.__image.tile[0][0],  # it have to be 'raw'
                           [0, 0, self.imwidth, 0],  # tile extent (a rectangle)
                           self.__offset,
                           self.__image.tile[0][3]]  # list of arguments to the decoder
        self.__min_side = min(self.imwidth, self.imheight)  # get the smaller image side
        # Create image pyramid
        self.__pyramid = [self.smaller()] if self.__huge else [Image.fromarray(self.__image_array)]
        # Set ratio coefficient for image pyramid
        self.__ratio = max(self.imwidth, self.imheight) / self.__huge_size if self.__huge else 1.0
        self.__curr_img = 0  # current image from the pyramid
        self.__scale = self.imscale * self.__ratio  # image pyramide scale
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
        self.__open_image_done = True
        


    def __enter(self, event):
        if self.__running_template_test:
            self.__create_template_image()


    def __leave(self, _):
        if self.__template_image_id:
            self.canvas.delete(self.__template_image_id)


    def __reset_canvas_tool_selection(self):
        self.canvas.unbind('<ButtonPress-1>')
        self.canvas.unbind('<B1-Motion>')
        self.canvas.unbind('<Motion>')
        self.canvas.unbind('<Button-1>')
        self.__running_template_test = False
        if self.__template_image_id:
            self.__template_image_shown = False 
            self.canvas.delete(self.__template_image_id) 



    def start_move_tool(self):
        self.__reset_canvas_tool_selection()
        self.canvas.bind('<ButtonPress-1>', self.__move_from)  # remember canvas position
        self.canvas.bind('<B1-Motion>',     self.__move_to)  # move canvas to the new position
        


    def start_template_test_tool(self):
        self.__reset_canvas_tool_selection()
        self.canvas.bind('<Motion>', self.__move_template_to)
        self.canvas.bind('<Button-1>', self.__place_template_image)
        self.__running_template_test = True

    def __create_template_image(self):
        
        width = int(self.__template_image.width * self.imscale)
        height = int(self.__template_image.height * self.imscale)
        img = self.__template_image.resize((width, height), Image.LANCZOS)
        img = self.__change_image_color_to_color(img,[255,255,255],[255,255,255,0])
        self.__shown_template_image = ImageTk.PhotoImage(self.__change_image_color_to_color(img,[0,0,0],[0,0,0,255],0.65,True))
        self.__faded_shown_template_image = ImageTk.PhotoImage(self.__change_image_color_to_color(img,[0,0,0],[200,200,200,255],0.5))

        if not self.__running_template_test:
            return
        if self.template_outside(self.__template_curX, self.__template_curY):
            self.__template_image_id = self.canvas.create_image(self.__template_curX,self.__template_curY,image=self.__faded_shown_template_image) 
            self.__template_image_shown = False 
        else:
            self.__template_image_id = self.canvas.create_image(self.__template_curX,self.__template_curY,image=self.__shown_template_image)
            self.__template_image_shown = True 
        
        self.__reposition_placed_images()
        
        


    def __change_image_color_to_color(self, image, color_to_change, color, transparency=1, add_border=False):
        data = np.array(image)   # "data" is a height x width x 4 numpy array
        red, green, blue, _  = data.T # Temporarily unpack the bands for readability

        # Replace white with red... (leaves alpha values alone...)
        white_areas = (red == color_to_change[0]) & (blue == color_to_change[1]) & (green == color_to_change[2])
        data[..., 0:4][white_areas.T] = (color[0], color[1], color[2], color[3]) # Transpose back needed

        data[...,3] = (data[...,3] * transparency)
     
        if add_border:
            data = cv2.copyMakeBorder(data, 2, 2, 2, 2, cv2.BORDER_CONSTANT, None,(255,0,0,255))
        
        return Image.fromarray(data)


    def __move_template_to(self, event:tk.Event):
        
        self.__template_curX, self.__template_curY = ( self.canvas.canvasx(event.x),  self.canvas.canvasy(event.y))

        if not self.template_outside(self.__template_curX, self.__template_curY) and self.__template_image_shown:
            self.canvas.coords(self.__template_image_id,self.__template_curX,self.__template_curY)
        elif not self.template_outside(self.__template_curX, self.__template_curY):
            self.__create_template_image()
        elif self.template_outside(self.__template_curX, self.__template_curY) and self.__template_image_shown:
            
            #self.canvas.delete(self.__template_image_id) 
            self.__create_template_image()
        elif self.template_outside(self.__template_curX, self.__template_curY):
            self.canvas.coords(self.__template_image_id,self.__template_curX,self.__template_curY)



    def __place_template_image(self, event:tk.Event):
        if self.template_outside(self.__template_curX, self.__template_curY):
            return
        self.canvas.create_image(self.__template_curX,self.__template_curY,image=self.__shown_template_image,tags=('placed_template',))
        positioning_rect_id = self.canvas.create_rectangle(self.__template_curX,self.__template_curY,self.__template_curX+1,self.__template_curY+1,fill="",outline="")
        self.__placed_template_images.append(positioning_rect_id)
        

    def __reposition_placed_images(self):
        self.canvas.delete('placed_template')
        for coordinate in self.__placed_template_images:
            coords = self.canvas.coords(coordinate)
            self.canvas.create_image(coords[0],coords[1],image=self.__shown_template_image,tags=('placed_template',))
       



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
            self.__image.close()
            self.__image = Image.fromarray(self.__image_array)  # reopen / reset image
            self.__image.size = (self.imwidth, band)  # set size of the tile band
            self.__image.tile = [self.__tile]  # set tile
            cropped = self.__image.crop((0, 0, self.imwidth, band))  # crop tile band
            image.paste(cropped.resize((w, int(band * k)+1), self.__filter), (0, int(i * k)))
            i += band
        print('\r' + (40 * ' ') + '\r', end='')  # hide printed string
        return image

    @staticmethod
    def check_image(path):
        """ Check if it is an image. Static method """
        # noinspection PyBroadException
        try:  # try to open and close image with PIL
            Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS  # suppress DecompressionBombError for big image
            with warnings.catch_warnings():  # suppress DecompressionBombWarning for big image
                warnings.simplefilter(u'ignore')
                img = Image.open(path)
            img.close()
        except:
            return False  # not image
        return True  # image

    def redraw_figures(self):
        """ Dummy function to redraw figures in the children classes """
        pass

    def grid(self, **kw):
        """ Put CanvasImage widget on the parent widget """
        if self.__imframe is None:
            return
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

    def __show_image(self):
        """ Show image on the Canvas. Implements correct image zoom almost like in Google Maps """
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
                self.__image.close()
                self.__image = Image.fromarray(self.__image_array)  # reopen / reset image
                self.__image.size = (self.imwidth, h)  # set size of the tile band
                self.__image.tile = [self.__tile]
                image = self.__image.crop((int(x1 / self.imscale), 0, int(x2 / self.imscale), h))
            else:  # show normal image
                image = self.__pyramid[max(0, self.__curr_img)].crop(  # crop current img from pyramid
                                    (int(x1 / self.__scale), int(y1 / self.__scale),
                                     int(x2 / self.__scale), int(y2 / self.__scale)))
            #
            imagetk = ImageTk.PhotoImage(image.resize((int(x2 - x1), int(y2 - y1)), self.__filter))
            imageid = self.canvas.create_image(max(box_canvas[0], box_img_int[0]),
                                               max(box_canvas[1], box_img_int[1]),
                                               anchor='nw', image=imagetk)
            self.canvas.lower(imageid)  # set image into background
            self.canvas.imagetk = imagetk  # keep an extra reference to prevent garbage-collection

    def __move_from(self, event):
        """ Remember previous coordinates for scrolling with the mouse """
        self.canvas.scan_mark(event.x, event.y)

    def __move_to(self, event):
        """ Drag (move) canvas to the new position """
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        self.__show_image()  # zoom tile and show it on the canvas

    def outside(self, x, y):
        """ Checks if the point (x,y) is outside the image area """
        bbox = self.canvas.coords(self.container)  # get image area
        if bbox[0] < x < bbox[2] and bbox[1] < y < bbox[3]:
            return False  # point (x,y) is inside the image area
        else:
            return True  # point (x,y) is outside the image area


    def template_outside(self, x, y):
        """ Checks if the point (x,y) is outside the image area """
        bbox = self.canvas.coords(self.container)  # get image area
        width = self.__template_image.width * self.imscale / 2
        height = self.__template_image.height * self.imscale / 2
        if (bbox[0] + width) < x < (bbox[2] - width) and (bbox[1] + height) < y < (bbox[3] - height):
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
        # Take appropriate image from the pyramid
        k = self.imscale * self.__ratio  # temporary coefficient
        self.__curr_img = min((-1) * int(math.log(k, self.__reduction)), len(self.__pyramid) - 1)
        self.__scale = k * math.pow(self.__reduction, max(0, self.__curr_img))
        #
        self.canvas.scale('all', x, y, scale, scale)  # rescale all objects
        # Redraw some figures before showing image on the screen
        self.redraw_figures()  # method for child classes
        self.__show_image()
        self.__create_template_image()
        self.__reposition_placed_images()


    def __keystroke(self, event):
        """ Scrolling with the keyboard.
            Independent from the language of the keyboard, CapsLock, <Ctrl>+<key>, etc. """
        if event.state - self.__previous_state == 4:  # means that the Control key is pressed
            pass  # do nothing if Control key is pressed
        else:
            self.__previous_state = event.state  # remember the last keystroke state
            # Up, Down, Left, Right keystrokes
            self.keycodes = {}  # init key codes
            if os.name == 'nt':  # Windows OS
                self.keycodes = {
                    'd': [68, 39, 102],
                    'a': [65, 37, 100],
                    'w': [87, 38, 104],
                    's': [83, 40,  98],
                }
            else:  # Linux OS
                self.keycodes = {
                    'd': [40, 114, 85],
                    'a': [38, 113, 83],
                    'w': [25, 111, 80],
                    's': [39, 116, 88],
                }
            if event.keycode in self.keycodes['d']:  # scroll right, keys 'd' or 'Right'
                self.__scroll_x('scroll',  1, 'unit', event=event)
            elif event.keycode in self.keycodes['a']:  # scroll left, keys 'a' or 'Left'
                self.__scroll_x('scroll', -1, 'unit', event=event)
            elif event.keycode in self.keycodes['w']:  # scroll up, keys 'w' or 'Up'
                self.__scroll_y('scroll', -1, 'unit', event=event)
            elif event.keycode in self.keycodes['s']:  # scroll down, keys 's' or 'Down'
                self.__scroll_y('scroll',  1, 'unit', event=event)

    def crop(self, bbox):
        """ Crop rectangle from the image and return it """
        if self.__huge:  # image is huge and not totally in RAM
            band = bbox[3] - bbox[1]  # width of the tile band
            self.__tile[1][3] = band  # set the tile height
            self.__tile[2] = self.__offset + self.imwidth * bbox[1] * 3  # set offset of the band
            self.__image.close()
            self.__image = Image.fromarray(self.__image_array)  # reopen / reset image
            self.__image.size = (self.imwidth, band)  # set size of the tile band
            self.__image.tile = [self.__tile]
            return self.__image.crop((bbox[0], 0, bbox[2], band))
        else:  # image is totally in RAM
            return self.__pyramid[0].crop(bbox)

    def destroy(self):
        """ ImageFrame destructor """
        self.__image.close()
        map(lambda i: i.close, self.__pyramid)  # close all pyramid images
        del self.__pyramid[:]  # delete pyramid list
        del self.__pyramid  # delete pyramid variable
        self.canvas.destroy()
        self.__imframe.destroy()