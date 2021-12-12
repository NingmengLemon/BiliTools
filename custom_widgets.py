from tkinter import ttk
import tkinter as tk
from PIL import Image,ImageTk

def tkImg(file=None,scale=1,size=()):
    if file:
        with Image.open(file) as f:
            width = f.size[0]
            height = f.size[1]
            if size == ():
                tmp = f.resize((int(width*scale),int(height*scale)),Image.ANTIALIAS)
            else:
                tmp = f.resize((int(size[0]),int(size[1])),Image.ANTIALIAS)
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

    def set(self,image_bytesio,width=None,height=None):
        if width:
            self._params['width'] = width
        if height:
            self._params['height'] = height
        self._params['image_bytesio'] = image_bytesio
        self._update()

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
        if self.tip_window:
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
