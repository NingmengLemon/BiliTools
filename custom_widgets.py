from tkinter import ttk
import tkinter as tk
import io
from PIL import Image,ImageTk
from basic_window import Window
import threading
import time
from tkinter import messagebox as msgbox
import logging

__all__ = ['tkImg','ImageButton','ImageLabel','ToolTip','VerticalScrolledFrame',
           'run_with_gui','bubble','msgbox_askchoice']

def tkImg(file=None,scale=1,size=()):
    if file:
        with Image.open(file) as f:
            width = f.size[0]
            height = f.size[1]
            if size == ():
                tmp = f.resize((int(width*scale),int(height*scale)),Image.LANCZOS)
            else:
                tmp = f.resize((int(size[0]),int(size[1])),Image.LANCZOS)
        img = ImageTk.PhotoImage(tmp)
        return img
    else:
        if size == ():
            f = Image.new('RGB',(300,300),(255,255,255))
        else:
            f = Image.new('RGB',size,(255,255,255))
        return ImageTk.PhotoImage(f)

class ImageButton(ttk.Button):
    def __init__(self,master,width=20,height=20,image_bytesio=None,**kwargs):
        super().__init__(master,**kwargs)
        self._params = {
            'width':width,
            'height':height,
            'image_bytesio':image_bytesio
            }
        self._tkimg = None
        self._update()

    def _update(self):
        if self._params['image_bytesio']:
            self._tkimg = tkImg(self._params['image_bytesio'],size=(self._params['width'],self._params['height']))
        else:
            self._tkimg = tkImg(size=(self._params['width'],self._params['height']))
        self.configure(image=self._tkimg)
        self.image = self._tkimg

    def clear(self):
        self._params['image_bytesio'] = None
        self._update()

    def set(self,image_bytesio=None,width=None,height=None):
        if width:
            self._params['width'] = width
        if height:
            self._params['height'] = height
        if image_bytesio:
            self._params['image_bytesio'] = image_bytesio
        self._update()

class ImageLabel(tk.Label):
    def __init__(self,master,width=300,height=300,image_bytesio=None,**kwargs):
        super().__init__(master,**kwargs)
        self._params = {
            'width':width,
            'height':height,
            'image_bytesio':image_bytesio
            }
        self._tkimg = None
        self._update()

    def _update(self):
        if self._params['image_bytesio']:
            self._tkimg = tkImg(self._params['image_bytesio'],size=(self._params['width'],self._params['height']))
        else:
            self._tkimg = tkImg(size=(self._params['width'],self._params['height']))
        self.configure(image=self._tkimg)
        self.image = self._tkimg

    def clear(self):
        self._params['image_bytesio'] = None
        self._update()

    def set(self,image_bytesio=None,width=None,height=None):
        if width:
            self._params['width'] = width
        if height:
            self._params['height'] = height
        if image_bytesio:
            self._params['image_bytesio'] = image_bytesio
        self._update()

    def get_width(self):
        return self._params['width']

    def get_height(self):
        return self._params['height']

class _TipWindow(tk.Toplevel):
    def __init__(self, master, **kw):
        """创建一个带有工具提示文本的 topoltip 窗口"""
        super().__init__(master, **kw)
        self._custom(master)

    def _custom(self, widget):
        '''定制窗口属性
        
        参数
        ======
        widget: tkinter 小部件 或者 tkinter.ttk 小部件
        '''
        ## 隐藏窗体的标题、状态栏等
        self.overrideredirect(True)
        ## 保持在主窗口的上面
        self.attributes("-toolwindow", 1)  # 也可以使用 `-topmost`
        self.attributes("-alpha", 0.928)    # 设置透明度为 13/14

    def _label_params(self, text, textvariable):
        '''创建用来显示的标签'''
        params = {
            'textvariable': textvariable,
            'text': text,
            'justify': 'left',
            'background': '#ffffff',
            'relief': 'solid',
            'borderwidth': 1
        }
        return params


class ToolTip:
    '''针对指定的 widget 创建一个 tooltip'''
    def __init__(self, widget, text=None, textvariable=None, timeout=300, offset=(0, -20), **kw):
        # 设置 用户参数
        self.widget = widget
        self.text = text
        self.textvariable = textvariable
        self.timeout = timeout
        self.offset = offset
        self._init_params()
        # 绑定事件
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)

    def change_text(self,text):
        self.text = text

    def _init_params(self):
        '''内部参数的初始化'''
        self.id_after = None
        self.x, self.y = 0, 0
        self.tip_window = None

    def update_cursor(self, event):
        '''设定 鼠标光标的位置坐标 (x,y)'''
        self.x = event.x
        self.y = event.y

    def unschedule(self):
        '''取消用于鼠标悬停时间的计时器'''
        if self.id_after:
            self.widget.after_cancel(self.id_after)
        self.id_after = None

    def wm_geometry(self):
        '''转换为电脑桌面的坐标'''
        new_x = self.widget.winfo_rootx() + self.x + self.offset[0]
        new_y = self.widget.winfo_rooty() + self.y + self.offset[1]
        return new_x, new_y

    def show_tip(self):
        """
        创建一个带有工具提示文本的 topoltip 窗口
        """
        if self.tip_window or not self.text:
            return
        else:
            self.tip_window = _TipWindow(self.widget)
            self.tip_window.wm_attributes('-topmost',True)
            new_x, new_y = self.wm_geometry()
            self.tip_window.wm_geometry("+%d+%d" % (new_x, new_y))
            params = self.tip_window._label_params(
                self.text, self.textvariable)
            tip_label = ttk.Label(self.tip_window, **params)
            tip_label.grid(sticky='nsew')

    def schedule(self):
        """
        安排计时器以计时鼠标悬停的时间
        """
        self.id_after = self.widget.after(self.timeout, self.show_tip)

    def enter(self, event):
        """
        鼠标进入 widget 的回调函数
        
        参数
        =========
        :event:  来自于 tkinter，有鼠标的 x,y 坐标属性
        """
        self.unschedule()
        self.update_cursor(event)
        self.schedule()

    def hide_tip(self):
        """
        销毁 tooltip window
        """
        if self.tip_window:
            self.tip_window.destroy()
        self.tip_window = None

    def leave(self, event):
        """
        鼠标离开 widget 的销毁 tooltip window
         
        参数
        =========
        :event:  来自于 tkinter，没有被使用
        """
        self.unschedule()
        self.hide_tip()

class VerticalScrolledFrame(tk.Frame): #所以说这个B玩意为什么会在height>31000px的时候失效啊wdnmd
    #这个滚动框架采用的是frame套canvas再套frame的操作
    def __init__(self,master,height=200,**kwargs):
        '''组件宽度由内部的框架大小决定'''
        super().__init__(master,**kwargs)
        self._canvas = tk.Canvas(self,height=height,borderwidth=0,highlightthickness=0,takefocus=0,bg='#66ccff')
        self._canvas.grid(column=0,row=0,sticky='nsew')
        self._scrollbar = ttk.Scrollbar(self,orient='vertical',command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._scrollbar.grid(column=1,row=0,sticky='ns')
        self.inner_frame = tk.Frame(self._canvas)
        self._inner_frame_id = self._canvas.create_window(0,0, anchor='nw',window=self.inner_frame)

        self.inner_frame.bind('<Configure>',self._update_canvas)
        self._bind_scroll_event(self.inner_frame)

        self.bind = self.inner_frame.bind
        self.focus_set = self.inner_frame.focus_set
        self.unbind = self.inner_frame.unbind
        self.xview = self._canvas.xview
        self.xview_moveto = self._canvas.xview_moveto
        self.yview = self._canvas.yview
        self.yview_moveto = self._canvas.yview_moveto

    def set_height(self,h):
        self._canvas['height'] = h

    def _bind_scroll_event(self,widget):
        widget.bind('<MouseWheel>',self._scroll_event)
        widget.bind('<Button-4>',self._scroll_event)
        widget.bind('<Button-5>',self._scroll_event)
        widget.bind('<Up>',lambda event:self._canvas.yview_scroll(-1,"units"))
        widget.bind('<Down>',lambda event:self._canvas.yview_scroll(1,"units"))

    def _update_canvas(self,event):
        reqwidth = self._canvas.winfo_reqwidth()
        reqheight = self.inner_frame.winfo_reqheight()
        self._canvas.configure(scrollregion=(0, 0, reqwidth, reqheight),width=self.inner_frame.winfo_reqwidth())

    def scroll_to_top(self):
        self._canvas.yview_moveto(0)

    def _scroll_event(self,event):
        self._canvas.yview_scroll(-1 * (event.delta // 120), "units")

class Thread_with_gui(Window):
    def __init__(self,func,args=(),kwargs={},master=None,is_progress_hook_available=False,is_task_queue_available=False,no_window=False):
        '''
        由于涉及到GUI, 该方法只能在主线程中运行...
        is_progress_hook_available 的意思是, 传入的函数是否可以被传入progress_hook参数,
        函数通过修改该变量可以向GUI通报进度或状态.
        progress_hook是一个字典, 可以包含: status:(str),progress:(done(int),total(int))(tuple)/None
        is_task_queue_available 的意思是, 传入的函数是否可以被传入task_queue参数, 该参数是一个队列, 线程可以向它提交无参函数给主线程执行
        '''
        super().__init__('BiliTools - Working...',master=master,topmost=True)
        self.window.overrideredirect(True)
        ww,wh = (420,65)
        sw,sh = (self.window.winfo_screenwidth(),self.window.winfo_screenheight())
        self.window.geometry('%dx%d+%d+%d'%(ww,wh,(sw-ww)/2,(sh-wh)/2))

        self.func = func
        self.master = master
        self.progress_hook = {
            'status':'Working...',
            'progress':None #当此项为None时, 进度条左右游荡, 为元组时进度条显示进度
            }
        if is_progress_hook_available:
            kwargs['progress_hook'] = self.progress_hook
        if is_task_queue_available:
            kwargs['task_queue'] = self.task_queue
        self.no_window = no_window
        self.return_value = None
        self.thread = threading.Thread(target=self.thread_func,args=args,kwargs=kwargs,daemon=True)
        self.error = None
        self.loop_schedule = None

        self.prgbar = ttk.Progressbar(self.window,length=400)
        self.prgbar.grid(column=0,row=0,sticky='w',padx=10,pady=10)
        self.label = tk.Label(self.window,text='-')
        self.label.grid(column=0,row=1,sticky='w')

        self.thread.start()
        if self.master and not self.no_window:
            self.master.attributes('-disabled',1)
        if self.no_window:
            self.window.withdraw()
        self.refresh_gui()

    def thread_func(self,*args,**kwargs):
        try:
            self.return_value = self.func(*args,**kwargs)
        except Exception as e:
            self.error = e

    def refresh_gui(self):
        if self.thread.is_alive():
            if self.progress_hook['progress']:
                done,total = self.progress_hook['progress']
                if self.prgbar['mode'] != 'determinate':
                    self.prgbar['mode'] = 'determinate'
                self.prgbar['maximum'] = total
                self.prgbar['value'] = done
            else:
                if self.prgbar['mode'] != 'indeterminate':
                    self.prgbar['mode'] = 'indeterminate'
                self.prgbar.step()
            self.label['text'] = self.progress_hook['status']
            self.loop_schedule = self.window.after(50,self.refresh_gui)
        else:
            if self.loop_schedule:
                self.window.after_cancel(self.loop_schedule)
                self.loop_schedule = None
            if self.error:
                #msgbox.showerror('','出现错误: '+str(self.error))
                logging.error('Unexpected Error occurred while running function {} with gui: {}'.format(str(self.func),str(self.error)))
            self.close()
            if self.master and not self.no_window:
                self.master.attributes('-disabled',0)
            if self.error:
                raise self.error #将异常传达到主线程抛出

def run_with_gui(func,args=(),kwargs={},master=None,is_progress_hook_available=False,is_task_queue_available=False,no_window=False):
    thread = Thread_with_gui(func,args,kwargs,master,is_progress_hook_available,is_task_queue_available,no_window)
    thread.mainloop()
    return thread.return_value

def bubble(widget,text,start_alpha=1.0,pause_time=1000,fade_out_time=100,execute_time=20,offset=(0,-20)): # ms
    w = tk.Toplevel(widget)
    w.overrideredirect(1)
    w.configure(takefocus=0)
    w.resizable(False,False)
    w.attributes('-topmost',1,'-alpha',start_alpha)
    x,y = widget.winfo_rootx()+offset[0],widget.winfo_rooty()+offset[1]
    w.geometry(f'+{x}+{y}')
    l = tk.Label(w,text=text,background='#ffffff',
                 justify='left',relief='solid',
                 borderwidth=1)
    l.grid()
    def update(ext,wtt,x,y): # 执行次数, 等待时间
        alpha = w.attributes('-alpha')
        alpha -= start_alpha/ext
        if ext < 0 or w.attributes('-alpha') <= 0:
            w.destroy()
            return
        else:
            w.attributes('-alpha',alpha)
            y = y - 1
            w.geometry(f'+{x}+{y}')
            w.after(wtt,lambda t=ext-1,x=x,y=y:update(t,wtt,x,y))
    w.after(pause_time,lambda:update(execute_time,int(fade_out_time/execute_time),x,y))
    w.wait_window(w)

def coor_in_root_window(widget):
    '''
    返回组件在根窗口中的位置
    如果需要组件在屏幕中的位置只需使用 widget.winfo_rootx(或y)()
    虽然项目中没有实际使用, 但万一哪天用上了呢(
    '''
    def gc(wid,coor=(0,0)):
        try:
            wi = wid.grid_info()
        except AttributeError:
            return coor
        else:
            x,y = coor
            x += wi['in'].winfo_x()
            y += wi['in'].winfo_y()
            coor = (x,y)
            return gc(wi['in'],coor)
    x,y = gc(widget)
    return x,y

class _CustomMsgbox(object):
    def __init__(self,master,title,text,buttons={'是':True,'否':False},lock_master=True):
        self.return_value = None
        self.window = w = tk.Toplevel(master)
        w.title(title)
        w.resizable(False,False)
        w.attributes('-toolwindow',1,'-topmost',1)
        w.protocol('WM_DELETE_WINDOW',w.destroy)
        
        self.label = l = tk.Label(w,text=text,justify='left')
        l.grid(column=0,row=0,pady=10,padx=10,columnspan=len(buttons))
        col,row = 0,1
        self.buttons = []
        for bt,rv in buttons.items():
            self.buttons.append(ttk.Button(w,text=bt,command=lambda rev=rv:self.make_choice(rev)))
            self.buttons[-1].grid(column=col,row=row,padx=5,pady=5)
            col += 1

        ww,wh = (w.winfo_reqwidth(),w.winfo_reqheight())
        sw,sh = (w.winfo_screenwidth(),w.winfo_screenheight())
        self.window.geometry('+%d+%d'%((sw-ww)/2,(sh-wh)/2))

        orgstate = master.attributes('-disabled')
        if lock_master:
            master.attributes('-disabled',1)
        w.wait_window(w)
        master.attributes('-disabled',orgstate)
        org_topm = master.attributes('-topmost')
        master.attributes('-topmost',1)
        master.attributes('-topmost',0)
        master.attributes('-topmost',org_topm)

    def make_choice(self,return_value):
        self.return_value = return_value
        self.window.destroy()

def msgbox_askchoice(master,title,text,buttons={'是':True,'否':False}):
    w = _CustomMsgbox(master,title,text,buttons)
    return w.return_value

run_with_gui.__doc__ = Thread_with_gui.__init__.__doc__
