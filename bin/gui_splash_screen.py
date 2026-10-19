from tkinter import *
import time

class SplashScreen(Frame):
    def __init__(self, master=None, width=0.5, height=0.6, useFactor=True):
        Frame.__init__(self, master)
        self.pack(side=TOP, fill=BOTH, expand=YES)

        self.splashScreenWindow = Toplevel(self.master)
        # get screen width and height
        ws = self.splashScreenWindow.winfo_screenwidth()
        hs = self.splashScreenWindow.winfo_screenheight()
        w = (useFactor and ws*width) or width
        h = (useFactor and hs*height) or height
        # calculate position x, y
        x = (ws/2) - (w/2) 
        y = (hs/2) - (h/2)
        self.splashScreenWindow.geometry('%dx%d+%d+%d' % (w, h, x, y))
        
        self.splashScreenWindow.overrideredirect(True)
        self.splashScreenWindow.lift()
        
    def kill(self):
        self.splashScreenWindow.destroy()
        self.splashScreenWindow.update()

if __name__ == '__main__':
    root = Tk()

    sp = SplashScreen(root)
    sp.config(bg="#3366ff")
    
    time.sleep(3)

    m = Label(root, text="This is a test of the splash screen\n\n\nThis is only a test.")
    m.pack(side=TOP, expand=YES)
    m.config(bg="#3366ff", justify=CENTER, font=("calibri", 29))
    
    Button(root, text="Press this button to kill the program", bg='red', command=sp.kill).pack(side=BOTTOM, fill=X)
    root.mainloop()