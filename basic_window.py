import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as filedialog
import queue
import logging
import ctypes

__all__ = ['Window']

try:
    #ctypes.windll.shcore.SetProcessDpiAwareness(2)
    #ScaleFactor = ctypes.windll.shcore.GetScaleFactorForDevice(0)
    pass
except:
    pass

class Window(object):#程序中所有常规窗口的父类
    def __init__(self,title='BiliTools',toplevel=False,topmost=False,alpha=1.0,master=None):
        self.task_queue = queue.Queue() #此队列用于储存来自子线程的无参函数对象

        if toplevel or master:
            self.window = tk.Toplevel(master=master)
        else:
            self.window = tk.Tk()
        self.window.title(title)
        self.window.resizable(height=False,width=False)
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.window.wm_attributes('-alpha',alpha)
        self.window.wm_attributes('-topmost',topmost)
        self.listen_task()

    def listen_task(self):
        if not self.task_queue.empty():
            func = self.task_queue.get_nowait()
            try:
                func()
            except Exception as e:
                logging.error('Task Listener Caught an Error: '+str(e))
                #raise
        if self.task_queue.empty():
            self.window.after(10,self.listen_task)
        else:
            self.window.after(1,self.listen_task)

    def set_entry(self,entry,lock=False,text=''):
        entry['state'] = 'normal'
        entry.delete(0,'end')
        entry.insert('end',text)
        if lock:
            entry['state'] = 'disabled'

    def set_text(self,sctext,lock=False,add=False,text=''):
        sctext['state'] = 'normal'
        if not add:
            sctext.delete(1.0,'end')
        sctext.insert('end',text)
        if lock:
            sctext['state'] = 'disabled'

    def close(self):
        self.window.destroy()

    def start_window(self,winobj,args=(),kwargs={}):
        w = winobj(*args,**kwargs)

    def is_alive(self):
        try:
            self.window.state()
        except tk.TclError:
            return False
        else:
            return True

    def mainloop(self):
        self.window.wait_window(self.window)
