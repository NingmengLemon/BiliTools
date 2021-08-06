import tkinter as tk
import tkinter.messagebox as msgbox
import tkinter.filedialog as filedialog
import tkinter.ttk as ttk
from PIL import Image,ImageTk
import _thread
import queue

def print(*text,end='\n',sep=' '):
    tmp = []
    for part in text:
        tmp += [str(part)]
    sys.stdout.write(sep.join(tmp)+end)    
    sys.stdout.flush()

def tkImg(file=None,scale=1,size=()):
    try:
        with Image.open(file) as f:
            width = f.size[0]
            height = f.size[1]
            if size == ():
                tmp = f.resize((int(width*scale),int(height*scale)),Image.ANTIALIAS)
            else:
                tmp = f.resize((int(size[0]),int(size[1])),Image.ANTIALIAS)
        img = ImageTk.PhotoImage(tmp)
    except Exception as e:
        if size == ():
            f = Image.new('RGB',(300,300),(255,255,255))
        else:
            f = Image.new('RGB',size,(255,255,255))
        return ImageTk.PhotoImage(f)
    return img

class Window(object):#程序中所有常规窗口的父类
    def __init__(self,title='BiliTools',toplevel=False,topmost=False,alpha=1.0):
        self.task_queue = queue.Queue() #此队列用于储存来自子线程的无参函数对象
        self.image_library = [] #将tkimage存在这里
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
            func()
        self.window.after(10,self.listen_task)

    def config_widget(self,widget,option,value):#不要往这里面传image参数
        if option == 'image':
            return
        widget[option] = value

    def set_image(self,widget,image_bytesio,size=()):
        self.image_library.append(tkImg(image_bytesio,size=size))
        index = len(self.image_library)-1
        widget.configure(image=self.image_library[index])
        widget.image = self.image_library[index]

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
        w=winobj(args)
