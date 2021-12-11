import tkinter as tk
import tkinter.messagebox as msgbox
import tkinter.filedialog as filedialog
import tkinter.scrolledtext as scrolledtext
import tkinter.ttk as ttk
import queue
import logging

class Window(object):#程序中所有常规窗口的父类
    def __init__(self,title='BiliTools',toplevel=False,topmost=False,alpha=1.0):
        self.task_queue = queue.Queue() #此队列用于储存来自子线程的无参函数对象
        self.is_alive = True
        load_status = False

        if toplevel:
            self.window = tk.Toplevel()
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
        if self.task_queue.empty():
            self.window.after(10,self.listen_task)
        else:
            self.window.after(1,self.listen_task)

    def config_widget(self,widget,option,value):#不要往这里面传image参数
        if option == 'image':
            return
        widget[option] = value

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

    def explore_folder(self,returnEntry,title='浏览'):
        path = filedialog.askdirectory(title=title)
        if path:
            self.set_entry(returnEntry,True,path)
        else:
            pass

    def close(self):
        self.window.quit()
        self.window.destroy()
        self.is_aive = False

    def start_window(self,winobj,args=()):
        w = winobj(args)
