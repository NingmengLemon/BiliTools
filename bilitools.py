import tkinter as tk
import tkinter.messagebox as msgbox
import tkinter.filedialog as filedialog
import tkinter.ttk as ttk
import os
import sys
import re
import time
import random
import _thread
import queue
from io import BytesIO
import traceback
#第三方库
from PIL import Image,ImageTk
import qrcode
import tooltip
#自制库
import clipboard
import biliapis
import bilicodes

#注意：
#为了页面美观，将Button/Radiobutton/Checkbutton/Entry的母模块从tk换成ttk
#↑步入现代风（并不

version = '2.0.0_Dev02'
work_dir = os.getcwd()
user_name = os.getlogin()
config_path = f'C:\\Users\\{user_name}\\bilitools_config.json'
devmode = True
config = {
    'topmost':True,
    'login_method':'qrcode',# qrcode / cookies / no
    'autologin':True,
    'alpha':1.0 # 0.0-1.0
    }

tips = [
        '欢迎使用基于Bug开发的BiliTools（',
        '最简单的方法就是直接在这里粘贴网址',
        '不管怎样，你得先告诉我你要去哪儿啊',
        'Bug是此程序的核心部分',
        '鸽子是此程序的作者的本体（咕',
        '想要反馈Bug？那你得先找到作者再说',
        ]

about_info = '\n'.join([
    'BiliTools v.%s'%version,
    '一些功能需要 FFmpeg 的支持.',
    '感谢 @m13253 的弹幕转换程序的支持',
    '如你所见, 此程序还没有完工.',
    'Made by: @NingmengLemon（GitHub）',
    '---------------------------',
    '此程序严禁用于任何商业用途.',
    '此程序的作者不会为任何因使用此程序所造成的后果负责.',
    '感谢您的使用.'
    ])

def print(*text,end='\n',sep=' '):
    tmp = []
    for part in text:
        tmp += [str(part)]
    sys.stdout.write(sep.join(tmp)+end)    
    sys.stdout.flush()

def replaceChr(text):
    repChr = {'/':'／','*':'＊',':':'：','\\':'＼','>':'＞',
              '<':'＜','|':'｜','?':'？','"':'＂'}
    for t in list(repChr.keys()):
        text = text.replace(t,repChr[t])
    return text

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

def makeQrcode(data):
    qr = qrcode.QRCode()
    qr.add_data(data)
    img = qr.make_image()
    a = BytesIO()
    img.save(a,'png')
    return a #返回一个BytesIO对象

class Timer(object):
    def __init__(self,start=False):
        self.init_time = time.time()
        self.start_time = 0
        self._status = 0
        if start:
            self.start()

    def start(self):
        if self._status == 0:
            self._status = 1
            self.start_time = time.time()

    def get(self):
        if self._status == 0:
            return 0
        else:
            return time.time() - self.start_time

class MainWindow(object):
    def __init__(self):
        self.task_queue = queue.Queue() #此队列用于储存来自子线程的lambda函数
        self.image_library = [] #将tkimage存在这里
        
        self.window = tk.Tk()
        self.window.title('BiliTools - Main')
        self.window.resizable(height=False,width=False)
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.window.wm_attributes('-alpha',config['alpha'])
        self.setTopmost()

        self.frame_main = tk.Frame(self.window)
        tk.Label(self.frame_main,text='随便输入点什么吧~').grid(column=0,row=0,sticky='w')
        #主输入框
        self.entry_source = ttk.Entry(self.frame_main,width=50,exportselection=0)
        self.entry_source.grid(column=0,row=1)
        self.entry_source.bind('<Return>',lambda x=0:self.start())
        ttk.Button(self.frame_main,text='粘贴',command=lambda x=0:self.setEntry(self.entry_source,text=clipboard.getText()),width=5).grid(column=1,row=1)
        ttk.Button(self.frame_main,text='清空',command=lambda x=0:self.entry_source.delete(0,'end'),width=5).grid(column=2,row=1)
        ttk.Button(self.frame_main,text='开始',command=self.start,width=10).grid(column=1,row=2,columnspan=2)
        #Tips Shower
        self.label_tips = tk.Label(self.frame_main,text='Tips: -')
        self.label_tips.grid(column=0,row=2,sticky='w')
        self.label_tips.bind('<Button-1>',lambda x=0:self.changeTips())
        self.frame_main.grid(column=0,row=0,columnspan=2)

        self.frame_userinfo = tk.LabelFrame(self.window,text='用户信息')
        #用户头像
        self.img_user_face_empty = tkImg(size=(100,100))
        self.label_face = tk.Label(self.frame_userinfo,text='',image=self.img_user_face_empty)
        self.label_face.grid(column=0,row=0,rowspan=4)
        self.label_face_text = tk.Label(self.frame_userinfo,text='未加载',bg='#ffffff',font=('',8))#图片上的提示文本
        self.label_face_text.grid(column=0,row=0,rowspan=4)
        #用户名
        self.label_username = tk.Label(self.frame_userinfo,text='-')
        self.label_username.grid(column=1,row=0,sticky='w',columnspan=2)
        #UID
        self.label_uid = tk.Label(self.frame_userinfo,text='UID0')
        self.label_uid.grid(column=1,row=1,sticky='w')
        #Level
        self.label_level = tk.Label(self.frame_userinfo,text='Lv.0')
        self.label_level.grid(column=1,row=2,sticky='w')
        #VIP
        self.label_vip = tk.Label(self.frame_userinfo,text='非大会员')
        self.label_vip.grid(column=1,row=3,sticky='w')
        #Login Operation
        self.button_login = ttk.Button(self.frame_userinfo,text='登录',command=self.login)
        self.button_login.grid(column=0,row=4,sticky='w')
        ttk.Button(self.frame_userinfo,text='刷新',command=self.refreshUserinfo).grid(column=1,row=4,sticky='w')
        ttk.Button(self.frame_userinfo,text='清除登录痕迹',command=self.clearLoginData).grid(column=0,row=5,columnspan=2)
        self.frame_userinfo.grid(column=0,row=1,sticky='w',columnspan=2)

        self.frame_console = tk.LabelFrame(self.window,text='操作')
        self.frame_console.grid(column=1,row=1,sticky='e')

        self.frame_config = tk.LabelFrame(self.window,text='全局设置')
        #置顶
        self.boolvar_topmost = tk.BooleanVar(value=config['topmost'])
        ttk.Checkbutton(self.frame_config,variable=self.boolvar_topmost,onvalue=True,offvalue=False,text='置顶',command=self.applyConfig).grid(column=0,row=0,sticky='w')
        #登录方式
        self.frame_config_login_method = tk.LabelFrame(self.frame_config,text='登录方式')
        self.strvar_login_method = tk.StringVar(value=config['login_method'])
        ttk.Radiobutton(self.frame_config_login_method,variable=self.strvar_login_method,value='qrcode',text='扫描二维码',command=self.applyConfig).grid(column=0,row=0,sticky='w')
        ttk.Radiobutton(self.frame_config_login_method,variable=self.strvar_login_method,value='cookies',text='加载现有的Cookies',command=self.applyConfig).grid(column=0,row=1,sticky='w')
        ttk.Radiobutton(self.frame_config_login_method,variable=self.strvar_login_method,value='no',text='不登录',command=self.applyConfig).grid(column=0,row=2,sticky='w')
        self.frame_config_login_method.grid(column=0,row=1,sticky='w',rowspan=2)
        #启动时自动尝试登录
        self.boolvar_autologin = tk.BooleanVar(value=config['autologin'])
        ttk.Checkbutton(self.frame_config,variable=self.boolvar_autologin,onvalue=True,offvalue=False,text='启动时自动尝试登录',command=self.applyConfig).grid(column=1,row=0,sticky='w')
        #窗体透明度
        self.frame_winalpha = tk.LabelFrame(self.frame_config,text='窗体透明度')
        self.doublevar_winalpha = tk.DoubleVar(value=config['alpha'])
        self.label_winalpha_shower = tk.Label(self.frame_winalpha,text='% 3d%%'%(config['alpha']*100))
        self.label_winalpha_shower.grid(column=0,row=0,sticky='w')
        self.scale_winalpha = ttk.Scale(self.frame_winalpha,from_=0.0,to=1.0,orient=tk.HORIZONTAL,variable=self.doublevar_winalpha,command=lambda x=0:self.applyConfig())
        self.scale_winalpha.grid(column=1,row=0,sticky='w')
        self.frame_winalpha.grid(column=1,row=1,sticky='w')
        self.tooltip_winalpha = tooltip.ToolTip(self.frame_winalpha,text='注意，透明度调得过低会影响操作体验')
        self.frame_config.grid(column=0,row=2,columnspan=2)

        self.changeTips()
        if config['autologin']:
            self.window.after(20,self.login)
        self.listen_task()
        self.entry_source.focus()
        #self.window.mainloop()

    def listen_task(self):
        if not self.task_queue.empty():
            func = self.task_queue.get_nowait()
            func()
        self.window.after(10,self.listen_task)

    def setTopmost(self,mode=None):
        if mode == False:
            self.window.wm_attributes('-topmost',False)
        elif mode == True:
            self.window.wm_attributes('-topmost',True)
        else:
            self.window.wm_attributes('-topmost',config['topmost'])
            
    def quitLogin(self):
        biliapis.quit_login()
        self.label_face.configure(image=self.img_user_face_empty)
        self.label_face.image = self.img_user_face_empty
        self.label_face_text.grid()
        self.label_username['text'] = '-'
        self.label_uid['text'] = 'UID0'
        self.label_level['text'] = 'Lv.0'
        self.label_vip['text'] = '非大会员'
        print('已退出登录')
        self.button_login['text'] = '登录'
        self.button_login['command'] = self.login

    def clearLoginData(self):
        if msgbox.askyesno('','这将会删除保存在程序中的登录数据.\n确认？'):
            biliapis.clear_cookies()
            self.quitLogin()
            print('已清除登录数据')

    def login(self):
        flag = 0
        if config['login_method'] == 'qrcode':
            print('正在通过QRCODE方式登录')
            biliapis.load_local_cookies()
            if biliapis.is_cookiejar_usable():
                self.refreshUserinfo()
                print('登录成功')
                flag = 1
            else:
                self.setTopmost(False)
                w = LoginWindow(True)
                if w.status:
                    biliapis.load_local_cookies()
                    self.refreshUserinfo()
                    print('登录成功')
                    flag = 1
                else:
                    msgbox.showwarning('','登录未完成.')
                    print('登录取消')
                self.setTopmost()
        elif config['login_method'] == 'cookies':
            print('正在通过COOKIES方式登录')
            biliapis.load_explorer_cookies()
            if biliapis.is_cookiejar_usable():
                self.refreshUserinfo()
                print('登录成功')
                flag = 1
            else:
                msgbox.showwarning('','无法从浏览器中加载现成的Cookies.')
                print('登录失败')
        else:
            msgbox.showwarning('','你已将登录方式设为不登录.')
        if flag != 0:
            self.button_login['text'] = '退出登录'
            self.button_login['command'] = self.quitLogin
        return

    def config_widget(self,widget,option,value):#不要往这里面传image参数
        if option == 'image':
            return
        widget[option] = value

    def set_image(self,widget,image_bytesio,size=()):
        self.image_library.append(tkImg(image_bytesio,size=size))
        index = len(self.image_library)-1
        widget.configure(image=self.image_library[index])
        widget.image = self.image_library[index]
             
    def refreshUserinfo(self):
        def tmp():
            tmp = biliapis.get_login_info()
            #Face
            face = biliapis.get_content_bytes(biliapis.format_img(tmp['face'],w=100,h=100))
            face = BytesIO(face)
            self.task_queue.put_nowait(lambda x=0:self.set_image(self.label_face,face,(100,100)))
            self.task_queue.put_nowait(lambda x=0:self.label_face_text.grid_remove())
            #Info
            self.task_queue.put_nowait(lambda x=0:self.config_widget(self.label_username,'text',tmp['name']))
            self.task_queue.put_nowait(lambda x=0:self.config_widget(self.label_uid,'text','UID%s'%tmp['uid']))
            self.task_queue.put_nowait(lambda x=0:self.config_widget(self.label_level,'text','Lv.%s'%tmp['level']))
            self.task_queue.put_nowait(lambda x=0:self.config_widget(self.label_vip,'text',tmp['vip_type']))
        _thread.start_new(tmp,())

    def applyConfig(self):
        global config
        config['topmost'] = self.boolvar_topmost.get()
        config['login_method'] = self.strvar_login_method.get()
        config['autologin'] = self.boolvar_autologin.get()
        config['alpha'] = round(self.doublevar_winalpha.get(),2)
        self.label_winalpha_shower['text'] = '% 3d%%'%(config['alpha']*100)
        self.setTopmost()
        self.window.wm_attributes('-alpha',config['alpha'])

    def changeTips(self,index=None):
        if index == None:
            self.label_tips['text'] = 'Tips: '+random.choice(tips)
        else:
            self.label_tips['text'] = 'Tips: '+tips[index]

    def setEntry(self,entry,lock=False,text=''):
        entry['state'] = 'normal'
        entry.delete(0,'end')
        entry.insert('end',text)
        if lock:
            entry['state'] = 'disabled'

    def explore_folder(self,returnEntry,title='浏览'):
        path = filedialog.askdirectory(title=title)
        if path:
            self.setEntry(returnEntry,True,path)
        else:
            pass

    def start(self,source=None):
        if source == None:
            source = self.entry_source.get().strip()
        if not source:
            msgbox.showinfo('','你似乎没有输入任何内容......')
            return
        source,flag = biliapis.parse_url(source)
        if flag == 'unknown':
            msgbox.showinfo('','无法解析......')
            return
        elif flag == 'auid':
            pass
        elif flag == 'avid' or flag == 'bvid':
            pass
        elif flag == 'ssid' or flag == 'mdid' or flag == 'epid':
            pass
        elif flag == 'cvid':
            pass
        elif flag == 'uid':
            pass
        else:
            msgbox.showinfo('','暂不支持%s的解析'%flag)
            return
        
    def close(self):
        self.window.quit()
        self.window.destroy()

class AudioWindow(object):
    def __init__(self):
        self.task_queue = queue.Queue() #此队列用于储存来自子线程的lambda函数
        self.image_library = [] #将tkimage存在这里
        
        self.window = tk.Toplevel()
        self.window.title('BiliTools - Audio')
        self.window.resizable(height=False,width=False)
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.window.attributes('-alpha',config['alpha'])

        self.listen_task()
        #self.window.mainloop()

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

    def close(self):
        self.window.quit()
        self.window.destroy()

class LoginWindow(object):
    def __init__(self):
        self.window = tk.Toplevel()
        self.window.title('BiliTools - Login')
        self.window.resizable(height=False,width=False)
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.window.wm_attributes('-topmost',config['topmost'])
        #窗口居中
        ww,wh = (310,390)
        sw,sh = (self.window.winfo_screenwidth(),self.window.winfo_screenheight())
        self.window.geometry('%dx%d+%d+%d'%(ww,wh,(sw-ww)/2,(sh-wh)/2))

        self.login_url = None
        self.oauthkey = None
        self.qrcode_img = tkImg(size=(300,300))
        self.status = False
        self.condition = None
        self.final_url = None
        
        self.label_imgshower = tk.Label(self.window,text='',image=self.qrcode_img)
        self.label_imgshower.pack()
        self.label_text = tk.Label(self.window,text='未获取',font=(15))
        self.label_text.pack(pady=10)
        self.button_refresh = ttk.Button(self.window,text='刷新',state='disabled',command=self.fresh)
        self.button_refresh.pack()

        self.fresh()
        print('LoginWindow初始化完成')
        self.window.mainloop()

    def fresh(self):
        self.button_refresh['state'] = 'disabled'
        self.label_text['text'] = '正在刷新'
        self.login_url,self.oauthkey = biliapis.get_login_url()
        tmp = makeQrcode(self.login_url)
        self.qrcode_img = tkImg(tmp,size=(300,300))
        self.label_imgshower.configure(image=self.qrcode_img)
        self.label_imgshower.image = self.qrcode_img
        self.start_autocheck()

    def start_autocheck(self):
        if not self.oauthkey:
            return
        res = biliapis.check_scan(self.oauthkey)
        self.status,self.final_url,self.condition = res
        self.label_text['text'] = {0:'登录成功',-1:'密钥错误',-2:'二维码已超时',-4:'使用B站手机客户端扫描此二维码',-5:'在手机上确认登录'}[self.condition]
        if self.condition == 0:
            print('已确认登录')
            cookiejar = biliapis.make_cookiejar(self.final_url)
            if os.path.exists(os.path.abspath('./cookies.txt')):
                os.remove(os.path.abspath('./cookies.txt'))
            cookiejar.save(os.path.abspath('./cookies.txt'))
            print('COOKIEJAR已生成')
            self.window.after(1000,self.close)
            return
        elif self.condition == -2:
            self.button_refresh['state'] = 'normal'
            self.qrcode_img = tkImg(size=(300,300))
            self.label_imgshower.configure(image=self.qrcode_img)
            self.label_imgshower.image = self.qrcode_img
            print('二维码已失效')
            return
        elif self.condition == -4 or self.condition == -5:
            self.window.after(2000,self.start_autocheck)
            print('已检查')
            return
            
    def close(self):
        self.window.quit()
        self.window.destroy()
        print('LOGINWINDOW已关闭')

class Inputer(object):
    def __init__(self,text,title='Inputer',topmost=True,accept_type=str):
        self.return_value = None
        self.accept_type = accept_type
        
        self.window = tk.Tk()
        self.window.title(title)
        self.window.resizable(height=False,width=False)
        self.window.protocol('WM_DELETE_WINDOW',self.cancel)
        self.window.wm_attributes('-topmost',topmost)

        tk.Label(self.window,text=text).grid(column=0,row=0,columnspan=2,sticky='w')
        self.entry = ttk.Entry(self.window,width=40,exportselection=0)
        self.entry.grid(column=0,row=1,columnspan=2)
        self.entry.bind('<Return>',self.ensure)
        ttk.Button(self.window,text='确认',command=self.ensure).grid(column=0,row=2)
        ttk.Button(self.window,text='取消',command=self.cancel).grid(column=1,row=2)

    def ensure(self,event=None):
        try:
            self.accept_type(self.entry.get())
        except:
            msgbox.showwarning('（；´д｀）ゞ','你所输入的内容无法转换为程序要求的类型.\n需要: '+type(self.accept_type))
            return
        self.return_value = self.entry.get()
        self.close()

    def cancel(self):
        self.close()

    def close(self):
        self.window.quit()
        self.window.destroy()

if __name__ == '__main__' and not devmode:
    print('Program Running.')
    w = MainWindow()
