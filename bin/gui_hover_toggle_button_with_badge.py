
import base64
from io import BytesIO
import threading
from PIL import Image, ImageDraw, ImageFont, ImageTk
try:
    from bin.gui_base64_icons import approval_dark_gray, level_1_badge, level_2_badge, level_3_badge, level_4_badge
    from bin.gui_elements import hover_toggle_button
except:
    from gui_base64_icons import approval_dark_gray, level_1_badge, level_2_badge, level_3_badge, level_4_badge
    from gui_elements import hover_toggle_button

class hover_toggle_button_with_badge(hover_toggle_button):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.base_on_image = self.on_image.copy()
        self.base_off_image = self.off_image.copy()
        self.__font = ImageFont.truetype("arial.ttf", 13)
        self.trigger_delay_timer = None


    def set_delayed_update_function(self, func):
        self.func = func

    def trigger_delayed_update(self):
        if self.timer:
            self.timer.cancel()

        self.timer = threading.Timer(1.0, self.func)
        self.timer.start()


    def update_badge(self, number=0):
        if number == 0:
            self.__remove_badge()
        elif number < 10:
            self.__create_level_1_badge(number)
        elif number < 100:
            self.__create_level_2_badge(number)
        elif number < 1000:
            self.__create_level_3_badge(number)
        else:
            self.__create_level_4_badge(number)
        self.update_images()



    def __remove_badge(self):
        buff = BytesIO(base64.b64decode(self.on_image_data))
        img_on = Image.open(buff)
        buff = BytesIO(base64.b64decode(self.off_image_data))
        img_off = Image.open(buff)
        self.on_image = ImageTk.PhotoImage(img_on)
        self.off_image = ImageTk.PhotoImage(img_off)
        


    def __create_level_1_badge(self, number):
        buff = BytesIO(base64.b64decode(self.on_image_data))
        img_on = Image.open(buff)
        buff = BytesIO(base64.b64decode(self.off_image_data))
        img_off = Image.open(buff)
        buff = BytesIO(base64.b64decode(level_1_badge))
        img_b = Image.open(buff)
        draw = ImageDraw.Draw(img_b)
        
        draw.text((16, 5),str(number),(255,255,255),font=self.__font)
        img_on.paste(img_b, (0, 0), img_b)
        img_off.paste(img_b, (0, 0), img_b)
        self.on_image = ImageTk.PhotoImage(img_on)
        self.off_image = ImageTk.PhotoImage(img_off)


    def __create_level_2_badge(self, number):
        buff = BytesIO(base64.b64decode(self.on_image_data))
        img_on = Image.open(buff)
        buff = BytesIO(base64.b64decode(self.off_image_data))
        img_off = Image.open(buff)
        buff = BytesIO(base64.b64decode(level_2_badge))
        img_b = Image.open(buff)
        draw = ImageDraw.Draw(img_b)
        draw.text((13, 5),str(number),(255,255,255),font=self.__font)
        img_on.paste(img_b, (0, 0), img_b)
        img_off.paste(img_b, (0, 0), img_b)
        self.on_image = ImageTk.PhotoImage(img_on)
        self.off_image = ImageTk.PhotoImage(img_off)

    
    def __create_level_3_badge(self, number):
        buff = BytesIO(base64.b64decode(self.on_image_data))
        img_on = Image.open(buff)
        buff = BytesIO(base64.b64decode(self.off_image_data))
        img_off = Image.open(buff)
        buff = BytesIO(base64.b64decode(level_3_badge))
        img_b = Image.open(buff)
        draw = ImageDraw.Draw(img_b)
        draw.text((8, 5),str(number),(255,255,255),font=self.__font)
        img_on.paste(img_b, (0, 0), img_b)
        img_off.paste(img_b, (0, 0), img_b)
        self.on_image = ImageTk.PhotoImage(img_on)
        self.off_image = ImageTk.PhotoImage(img_off)


    def __create_level_4_badge(self, number):
        buff = BytesIO(base64.b64decode(self.on_image_data))
        img_on = Image.open(buff)
        buff = BytesIO(base64.b64decode(self.off_image_data))
        img_off = Image.open(buff)
        buff = BytesIO(base64.b64decode(level_4_badge))
        img_b = Image.open(buff)
        draw = ImageDraw.Draw(img_b)
        
        draw.text((2, 5),str(number),(255,255,255),font=self.__font)
        img_on.paste(img_b, (0, 0), img_b)
        img_off.paste(img_b, (0, 0), img_b)
        self.on_image = ImageTk.PhotoImage(img_on)
        self.off_image = ImageTk.PhotoImage(img_off)
        


if __name__ == '__main__':
    buff = BytesIO(base64.b64decode(approval_dark_gray))
    img_a = Image.open(buff)

    #buff = BytesIO(base64.b64decode(level_1_badge))
    #buff = BytesIO(base64.b64decode(level_2_badge))
    #buff = BytesIO(base64.b64decode(level_3_badge))
    buff = BytesIO(base64.b64decode(level_4_badge))
    img_b = Image.open(buff)
    draw = ImageDraw.Draw(img_b)
    font = ImageFont.truetype("arial.ttf", 14)
    #draw.text((15, 4),"5",(255,255,255),font=font)
    #draw.text((12, 4),"99",(255,255,255),font=font)
    #draw.text((7, 4),"000",(255,255,255),font=font)
    draw.text((1, 4),"10k+",(255,255,255),font=font)
    img_a.paste(img_b, (0, 0), img_b)
    
    img_a.show()
    print()
