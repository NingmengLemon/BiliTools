from tkinter import ttk
from tkinter import Toplevel

class TipWindow(Toplevel):
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
        self.attributes("-alpha", 0.92857142857)    # 设置透明度为 13/14

    def _label_params(self, text, textvariable):
        '''创建用来显示的标签'''
        params = {
            'textvariable': textvariable,
            'text': text,
            'justify': 'left',
            'background': 'lightyellow',
            'relief': 'solid',
            'borderwidth': 1
        }
        return params


class ToolTip:
    '''针对指定的 widget 创建一个 tooltip
    参考：https://stackoverflow.com/a/36221216 
        以及 https://pysimplegui.readthedocs.io/en/latest/
    '''

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
            self.tip_window = TipWindow(self.widget)
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
