#GUI
import tkinter as tk
import tkinter.messagebox as msgbox
import tkinter.filedialog as filedialog
import tkinter.scrolledtext as scrolledtext
import tkinter.ttk as ttk
#System
import os
import sys
import re
import time
import random
from io import BytesIO
import traceback
import math
#多线程用
import _thread
import queue
#第三方库
import qrcode
#自制库
import clipboard
import biliapis
import bilicodes
import tooltip
from basic_window import tkImg,Window

#注意：
#为了页面美观，将Button/Radiobutton/Checkbutton/Entry的母模块从tk换成ttk
#↑步入现代风（并不

version = '2.0.0_Dev03'
work_dir = os.getcwd()
user_name = os.getlogin()
config_path = f'C:\\Users\\{user_name}\\bilitools_config.json'
devmode = True #开发模式开关
config = {
    'topmost':True,
    'login_method':'qrcode',# qrcode / cookies / no
    'autologin':True,
    'alpha':1.0,# 0.0 - 1.0
    'explorer':'chrome',# chrome / firefox
    }

tips = [
        '欢迎使用基于Bug开发的BiliTools（',
        '最简单的方法就是直接在这里粘贴网址',
        '不管怎样，你得先告诉我你要去哪儿啊',
        'Bug是此程序的核心部分',
        '鸽子是此程序的作者的本体（咕',
        '想要反馈Bug？那你得先找到作者再说'
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

def makeQrcode(data):
    qr = qrcode.QRCode()
    qr.add_data(data)
    img = qr.make_image()
    a = BytesIO()
    img.save(a,'png')
    return a #返回一个BytesIO对象

class MainWindow(Window):
    def __init__(self):
        super().__init__('BiliTools - Main',False,config['topmost'],config['alpha'])

        self.frame_main = tk.Frame(self.window)
        tk.Label(self.frame_main,text='随便输入点什么吧~').grid(column=0,row=0,sticky='w')
        #主输入框
        self.entry_source = ttk.Entry(self.frame_main,width=50,exportselection=0)
        self.entry_source.grid(column=0,row=1)
        self.entry_source.bind('<Return>',lambda x=0:self.start())
        ttk.Button(self.frame_main,text='粘贴',command=lambda:self.set_entry(self.entry_source,text=clipboard.getText()),width=5).grid(column=1,row=1)
        ttk.Button(self.frame_main,text='清空',command=lambda:self.entry_source.delete(0,'end'),width=5).grid(column=2,row=1)
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
        self.button_refresh = ttk.Button(self.frame_userinfo,text='刷新',command=self.refreshUserinfo,state='disabled')
        self.button_refresh.grid(column=1,row=4,sticky='w')
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
        self.rb_login_1 = ttk.Radiobutton(self.frame_config_login_method,variable=self.strvar_login_method,value='qrcode',text='扫描二维码',command=self.applyConfig)
        self.rb_login_1.grid(column=0,row=0,sticky='w')
        self.rb_login_2 = ttk.Radiobutton(self.frame_config_login_method,variable=self.strvar_login_method,value='cookies',text='加载现有的Cookies',command=self.applyConfig)
        self.rb_login_2.grid(column=0,row=1,sticky='w')
        self.rb_login_3 = ttk.Radiobutton(self.frame_config_login_method,variable=self.strvar_login_method,value='no',text='不登录',command=self.applyConfig)
        self.rb_login_3.grid(column=0,row=2,sticky='w')
        self.frame_config_login_method.grid(column=0,row=1,sticky='w',rowspan=2)
        #启动时自动尝试登录
        self.boolvar_autologin = tk.BooleanVar(value=config['autologin'])
        ttk.Checkbutton(self.frame_config,variable=self.boolvar_autologin,onvalue=True,offvalue=False,text='启动时自动尝试登录',command=self.applyConfig).grid(column=1,row=0,sticky='w')
        #窗体透明度
        self.frame_winalpha = tk.LabelFrame(self.frame_config,text='窗体不透明度')
        self.doublevar_winalpha = tk.DoubleVar(value=config['alpha'])
        self.label_winalpha_shower = tk.Label(self.frame_winalpha,text='% 3d%%'%(config['alpha']*100))
        self.label_winalpha_shower.grid(column=0,row=0,sticky='w')
        self.scale_winalpha = ttk.Scale(self.frame_winalpha,from_=0.0,to=1.0,orient=tk.HORIZONTAL,variable=self.doublevar_winalpha,command=lambda x=0:self.applyConfig())
        self.scale_winalpha.grid(column=1,row=0,sticky='w')
        self.frame_winalpha.grid(column=1,row=1,sticky='w')
        self.tooltip_winalpha = tooltip.ToolTip(self.frame_winalpha,text='注意，不透明度调得过低会影响操作体验')
        self.frame_config.grid(column=0,row=2,columnspan=2)

        self.changeTips()
        if config['autologin']:
            self.window.after(20,self.login)
        self.entry_source.focus()
        self.window.mainloop()
            
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
        self.button_refresh['state'] = 'disabled'
        self.rb_login_1['state'] = 'normal'
        self.rb_login_2['state'] = 'normal'
        self.rb_login_3['state'] = 'normal'

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
                self.window.wm_attributes('-topmost',False)
                w = LoginWindow()
                if w.status:
                    biliapis.load_local_cookies()
                    self.refreshUserinfo()
                    print('登录成功')
                    flag = 1
                else:
                    msgbox.showwarning('','登录未完成.')
                    print('登录取消')
                self.window.wm_attributes('-topmost',config['topmost'])
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
            self.button_refresh['state'] = 'normal'
            self.rb_login_1['state'] = 'disabled'
            self.rb_login_2['state'] = 'disabled'
            self.rb_login_3['state'] = 'disabled'
        return
             
    def refreshUserinfo(self):
        def tmp():
            tmp = biliapis.get_login_info()
            #Face
            face = biliapis.get_content_bytes(biliapis.format_img(tmp['face'],w=100,h=100))
            face = BytesIO(face)
            self.task_queue.put_nowait(lambda:self.set_image(self.label_face,face,(100,100)))
            self.task_queue.put_nowait(lambda:self.label_face_text.grid_remove())
            #Info
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_username,'text',tmp['name']))
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_uid,'text','UID%s'%tmp['uid']))
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_level,'text','Lv.%s'%tmp['level']))
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_vip,'text',tmp['vip_type']))
        _thread.start_new(tmp,())

    def applyConfig(self):
        global config
        config['topmost'] = self.boolvar_topmost.get()
        config['login_method'] = self.strvar_login_method.get()
        config['autologin'] = self.boolvar_autologin.get()
        config['alpha'] = round(self.doublevar_winalpha.get(),2)
        self.label_winalpha_shower['text'] = '% 3d%%'%(config['alpha']*100)
        self.window.wm_attributes('-topmost',config['topmost'])
        self.window.wm_attributes('-alpha',config['alpha'])

    def changeTips(self,index=None):
        if index == None:
            self.label_tips['text'] = 'Tips: '+random.choice(tips)
        else:
            self.label_tips['text'] = 'Tips: '+tips[index]

    def start(self,source=None):
        if source == None:
            source = self.entry_source.get().strip()
        if not source:
            msgbox.showinfo('','你似乎没有输入任何内容......')
            return
        source,flag = biliapis.parse_url(source)
        if flag == 'unknown':
            msgbox.showinfo('','无法解析......')
        elif flag == 'auid':
            w = AudioWindow(source)
        elif flag == 'avid' or flag == 'bvid':
            w = CommonVideoWindow(source)
        elif flag == 'ssid' or flag == 'mdid' or flag == 'epid':
            pass
        elif flag == 'cvid':
            pass
        elif flag == 'uid':
            pass
        else:
            msgbox.showinfo('','暂不支持%s的解析'%flag)
        return

class AudioWindow(Window):
    def __init__(self,auid):
        self.auid = int(auid)
        
        super().__init__('BiliToools - Audio',True,config['topmost'],config['alpha'])

        #cover
        self.img_cover_empty = tkImg(size=(300,300))
        self.label_cover_shower = tk.Label(self.window,image=self.img_cover_empty)
        self.label_cover_shower.grid(column=0,row=0,rowspan=4,sticky='w')
        self.label_cover_text = tk.Label(self.window,text='加载中',font=('',8),bg='#ffffff')
        self.label_cover_text.grid(column=0,row=0,rowspan=4)
        #audio name
        self.text_name = tk.Text(self.window,font=('微软雅黑',10,'bold'),width=37,height=2,state='disabled',bg='#f0f0f0',bd=0)
        self.text_name.grid(column=0,row=4)
        self.tooltip_name = tooltip.ToolTip(self.text_name)
        #id
        self.label_auid = tk.Label(self.window,text='auID0')
        self.label_auid.grid(column=0,row=5,sticky='e')
        #description
        tk.Label(self.window,text='简介↓').grid(column=0,row=6,sticky='w')
        self.sctext_desc = scrolledtext.ScrolledText(self.window,state='disabled',width=41,height=12)
        self.sctext_desc.grid(column=0,row=7,sticky='w')
        #uploader
        self.frame_uploader = tk.LabelFrame(self.window,text='UP主')
        self.img_upface_empty = tkImg(size=(50,50))
        self.label_uploader_face = tk.Label(self.frame_uploader,image=self.img_upface_empty)#up头像
        self.label_uploader_face.grid(column=0,row=0,rowspan=2)
        self.label_uploader_face_text = tk.Label(self.frame_uploader,text='加载中',font=('',8),bg='#ffffff')
        self.label_uploader_face_text.grid(column=0,row=0,rowspan=2)
        self.label_uploader_name = tk.Label(self.frame_uploader,text='-')#up名字
        self.label_uploader_name.grid(column=1,row=0,sticky='w')
        self.label_uploader_id = tk.Label(self.frame_uploader,text='UID0')#uid
        self.label_uploader_id.grid(column=1,row=1,sticky='w')
        self.frame_uploader.grid(column=1,row=0,rowspan=1,sticky='nw')
        #tags
        self.text_tags = tk.Text(self.window,width=45,height=2,state='disabled',wrap=tk.WORD,bg='#f0f0f0',bd=0)
        self.text_tags.grid(column=1,row=1)
        #lyrics
        tk.Label(self.window,text='歌词↓').grid(column=1,row=2,sticky='sw')
        self.sctext_lyrics = scrolledtext.ScrolledText(self.window,width=40,height=30)
        self.sctext_lyrics.grid(column=1,row=3,rowspan=5)
        #operations
        self.frame_operation = tk.Frame(self.window)
        self.button_download_audio = ttk.Button(self.frame_operation,text='下载音频',command=self.download_audio)
        self.button_download_audio.grid(column=0,row=0)
        self.button_download_cover = ttk.Button(self.frame_operation,text='下载封面',command=self.download_cover)
        self.button_download_cover.grid(column=1,row=0)
        self.button_download_lyrics = ttk.Button(self.frame_operation,text='下载歌词',command=self.download_lyrics)
        self.button_download_lyrics.grid(column=2,row=0)
        self.button_open_in_ex = ttk.Button(self.frame_operation,text='在浏览器中打开',command=lambda:biliapis.open_in_explorer(f'https://www.bilibili.com/audio/au{self.auid}',config['explorer']))
        self.button_open_in_ex.grid(column=3,row=0)
        self.frame_operation.grid(column=0,row=8,columnspan=2)

        self.refresh_data()
        #self.window.mainloop()

    def download_audio(self):
        self.button_download_audio['state'] = 'disabled'
        if self.load_status:
            filename = replaceChr(self.title)+'.aac'
            path = filedialog.askdirectory(title='保存至')
            if path:
                stream = biliapis.get_audio_stream(auid=self.auid,quality=2)
                w = biliapis.DownloadWindow(stream['url'],path,filename)
        else:
            msgbox.showwarning('','加载未完成')
        if self.is_alive:
            self.button_download_audio['state'] = 'normal'
        return

    def download_cover(self):
        self.button_download_cover['state'] = 'disabled'
        if self.load_status:
            filename = replaceChr(self.title)+'.jpg'
            path = filedialog.askdirectory(title='保存至')
            if path:
                url = biliapis.get_audio_info(self.auid)['cover']
                with open(os.path.join(path,filename),'wb+') as f:
                    f.write(biliapis.get_content_bytes(url))
                msgbox.showinfo('','完成')
        else:
            msgbox.showwarning('','加载未完成')
        if self.is_alive:
            self.button_download_cover['state'] = 'normal'
        return

    def download_lyrics(self):
        self.button_download_lyrics['state'] = 'disabled'
        if self.load_status:
            filename = replaceChr(self.title)+'.lrc'
            path = filedialog.askdirectory(title='保存至')
            if path:
                data = biliapis.get_audio_lyrics(self.auid)
                if data == 'Fatal: API error':
                    msgbox.showinfo('','没有歌词')
                else:
                    with open(os.path.join(path,filename),'w+',encoding='utf-8') as f:
                        f.write(data)
                    msgbox.showinfo('','完成')
        else:
            msgbox.showwarning('','加载未完成')
        if self.is_alive:
            self.button_download_lyrics['state'] = 'normal'
        return
        
    def refresh_data(self):
        def tmp():
            if not self.check_usable():
                self.task_queue.put_nowait(lambda:msgbox.showerror('','音频不存在'))
                self.task_queue.put_nowait(self.close)
                return
            data = biliapis.get_audio_info(self.auid)
            self.title = data['title']
            self.task_queue.put_nowait(lambda:self.set_text(self.text_name,text=data['title'],lock=True))
            self.task_queue.put_nowait(lambda:self.tooltip_name.change_text(data['title']))
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_auid,'text','auID%s'%data['auid']))
            if data['description'].strip():
                self.task_queue.put_nowait(lambda:self.set_text(self.sctext_desc,text=data['description'],lock=True))
            else:
                self.task_queue.put_nowait(lambda:self.set_text(self.sctext_desc,text='没有简介',lock=True))
            updata = biliapis.get_user_info(data['uploader']['uid'])
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_uploader_name,'text',updata['name']))
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_uploader_id,'text','UID%s'%updata['uid']))
            if data['lyrics_url']:
                lrcdata = biliapis.get_audio_lyrics(self.auid)
                self.task_queue.put_nowait(lambda:self.set_text(self.sctext_lyrics,text=lrcdata,lock=True))
            else:
                self.task_queue.put_nowait(lambda:self.set_text(self.sctext_lyrics,text='没有歌词',lock=True))            
            tagdata = biliapis.get_audio_tags(self.auid)
            if tagdata:
                self.task_queue.put_nowait(lambda:self.set_text(self.text_tags,text='#'+'# #'.join(tagdata)+'#',lock=True))
            else:
                self.task_queue.put_nowait(lambda:self.set_text(self.text_tags,text='没有标签',lock=True))
            #image
            cover = BytesIO(biliapis.get_content_bytes(biliapis.format_img(data['cover'],w=300,h=300)))
            face = BytesIO(biliapis.get_content_bytes(biliapis.format_img(updata['face'],w=50,h=50)))
            self.task_queue.put_nowait(lambda:self.set_image(self.label_cover_shower,cover,(300,300)))
            self.task_queue.put_nowait(lambda:self.label_cover_text.grid_remove())
            self.task_queue.put_nowait(lambda:self.set_image(self.label_uploader_face,face,(50,50)))
            self.task_queue.put_nowait(lambda:self.label_uploader_face_text.grid_remove())
            self.load_status = True
        _thread.start_new(tmp,())

    def check_usable(self):
        try:
            biliapis.get_audio_info(self.auid)
        except biliapis.BiliError as e:
            if e.code == -404 or e.code == 7201006:
                return False
            else:
                raise e
        else:
            return True

class CommonVideoWindow(Window):
    def __init__(self,abvid):
        try:
            abvid = int(abvid)
            self.abtype = 'av'
        except ValueError:
            self.abtype = 'bv'
        self.abvid = abvid

        super().__init__('BiliTools - CommonVideo',True,config['topmost'],config['alpha'])

        self.rec_page = 1
        self.rec_spage_objnum = 5 #每页项数
        #左起第1列
        self.frame_left_1 = tk.Frame(self.window)
        self.frame_left_1.grid(column=0,row=0)
        #封面
        self.img_cover_empty = tkImg(size=(380,232))#！
        self.label_cover = tk.Label(self.frame_left_1,image=self.img_cover_empty)
        self.label_cover.grid(column=0,row=0)
        self.label_cover_text = tk.Label(self.frame_left_1,text='加载中',bg='#ffffff')
        self.label_cover_text.grid(column=0,row=0)
        #标题
        self.text_title = tk.Text(self.frame_left_1,bg='#f0f0f0',bd=0,height=2,width=46,state='disabled',font=('Microsoft YaHei UI',10,'bold'))
        self.text_title.grid(column=0,row=1,sticky='w')
        #warning info
        self.label_warning = tk.Label(self.frame_left_1,text='')
        self.label_warning.grid(column=0,row=2,sticky='w')
        #av
        self.label_avid = tk.Label(self.frame_left_1,text='AV0')
        self.label_avid.grid(column=0,row=3,sticky='w')
        #bv
        self.label_bvid = tk.Label(self.frame_left_1,text='BV-')
        self.label_bvid.grid(column=0,row=3,sticky='e')
        #status
        self.frame_status = tk.LabelFrame(self.frame_left_1,text='统计')
        self.frame_status.grid(column=0,row=4)
        tk.Label(self.frame_status,text='播放:').grid(column=0,row=0,sticky='w')
        self.label_view = tk.Label(self.frame_status,text='-')
        self.label_view.grid(column=1,row=0,sticky='w',columnspan=3)
        tk.Label(self.frame_status,text='点赞:').grid(column=0,row=1,sticky='w')
        self.label_like = tk.Label(self.frame_status,text='-')
        self.label_like.grid(column=1,row=1,sticky='w')
        tk.Label(self.frame_status,text='投币:').grid(column=0,row=2,sticky='w')
        self.label_coin = tk.Label(self.frame_status,text='-')
        self.label_coin.grid(column=1,row=2,sticky='w')
        tk.Label(self.frame_status,text='收藏:').grid(column=0,row=3,sticky='w')
        self.label_collect = tk.Label(self.frame_status,text='-')
        self.label_collect.grid(column=1,row=3,sticky='w')
        tk.Label(self.frame_status,text='分享:').grid(column=2,row=1,sticky='w')
        self.label_share = tk.Label(self.frame_status,text='-')
        self.label_share.grid(column=3,row=1,sticky='w')
        tk.Label(self.frame_status,text='弹幕:').grid(column=2,row=2,sticky='w')
        self.label_dmkcount = tk.Label(self.frame_status,text='-')
        self.label_dmkcount.grid(column=3,row=2,sticky='w')
        tk.Label(self.frame_status,text='评论:').grid(column=2,row=3,sticky='w')
        self.label_cmtcount = tk.Label(self.frame_status,text='-')
        self.label_cmtcount.grid(column=3,row=3,sticky='w')
        #operation
        self.frame_operation = tk.Frame(self.frame_left_1)
        self.frame_operation.grid(column=0,row=5)
        self.button_open_in_ex = ttk.Button(self.frame_operation,text='在浏览器中打开')
        self.button_open_in_ex.grid(column=0,row=0)
        self.button_download_audio = ttk.Button(self.frame_operation,text='下载音频',command=self.download_audio)
        self.button_download_audio.grid(column=1,row=0)
        #左起第2列
        self.frame_left_2 = tk.Frame(self.window)
        self.frame_left_2.grid(column=1,row=0)
        #uploader
        self.frame_uploader = tk.LabelFrame(self.frame_left_2,text='UP主')
        self.img_upface_empty = tkImg(size=(50,50))
        self.label_uploader_face = tk.Label(self.frame_uploader,image=self.img_upface_empty)#up头像
        self.label_uploader_face.grid(column=0,row=0,rowspan=2)
        self.label_uploader_face_text = tk.Label(self.frame_uploader,text='加载中',font=('',8),bg='#ffffff')
        self.label_uploader_face_text.grid(column=0,row=0,rowspan=2)
        self.label_uploader_name = tk.Label(self.frame_uploader,text='-')#up名字
        self.label_uploader_name.grid(column=1,row=0,sticky='w')
        self.label_uploader_id = tk.Label(self.frame_uploader,text='UID0')#uid
        self.label_uploader_id.grid(column=1,row=1,sticky='w')
        self.frame_uploader.grid(column=0,row=0,sticky='nw')
        #comment
        self.button_show_comments = ttk.Button(self.frame_left_2,text='查看评论')#
        self.button_show_comments.grid(column=0,row=0,sticky='se')
        #desc
        tk.Label(self.frame_left_2,text='简介↑').grid(column=0,row=2,sticky='nw')
        self.sctext_desc = scrolledtext.ScrolledText(self.frame_left_2,width=40,height=15,state='disabled')
        self.sctext_desc.grid(column=0,row=1)
        #parts
        tk.Label(self.frame_left_2,text='↓分P').grid(column=0,row=2,sticky='se',padx=20)
        self.frame_parts = tk.Frame(self.frame_left_2)
        self.frame_parts.grid(column=0,row=3)
        self.scbar_parts = tk.Scrollbar(self.frame_parts,orient='vertical')
        self.tview_parts = ttk.Treeview(self.frame_parts,show="headings",columns=("n.","pname","length"),yscrollcommand=self.scbar_parts.set,height=8)
        self.scbar_parts['command'] = self.tview_parts.yview
        self.tview_parts.column("n.", width=40,anchor='e')
        self.tview_parts.column("pname", width=180,anchor='w')
        self.tview_parts.column("length", width=60,anchor='w')
        self.tview_parts.heading("n.", text="序号",anchor='w')
        self.tview_parts.heading("pname", text="分P标题",anchor='w')
        self.tview_parts.heading("length", text="时长",anchor='w')
        self.tview_parts.grid(column=0,row=0)
        self.scbar_parts.grid(column=1,row=0,sticky='nw',ipady=70)
        #.insert("","end",values=(n.,pname,length))
        self.label_parts_counter = tk.Label(self.frame_parts,text='共 - 个分P')
        self.label_parts_counter.grid(column=0,row=1,columnspan=2,sticky='w')
        #左起第3列
        self.frame_left_3 = tk.Frame(self.window)
        self.frame_left_3.grid(column=2,row=0)
        #tags
        self.text_tags = tk.Text(self.frame_left_3,bg='#f0f0f0',bd=0,height=5,width=48,state='disabled',wrap=tk.WORD)
        self.text_tags.grid(column=0,row=0,sticky='sw')
        #recommend
        self.frame_rec = tk.LabelFrame(self.frame_left_3,text='相关视频 -个 -/-页')
        self.frame_rec.grid(column=0,row=1)
        self.rec_page_his = [] #翻页历史
        self.obj_rec = [] #已转移到单独的函数中
        self.rec_page = 1 #初始页数(必须为1)
        self.rec_spage_objnum = 5 #每页项数
        self.recommend = None #相关视频数据
        self.img_rec_empty = tkImg(size=(114,69))
        
        self.frame_rec_control = tk.Frame(self.frame_left_3)
        self.frame_rec_control.grid(column=0,row=2)
        self.button_rec_back = ttk.Button(self.frame_rec_control,text='上一页',state='disabled',command=lambda:self.fill_recommends(self.rec_page-1))
        self.button_rec_back.grid(column=0,row=0)
        self.button_rec_next = ttk.Button(self.frame_rec_control,text='下一页',state='disabled',command=lambda:self.fill_recommends(self.rec_page+1))
        self.button_rec_next.grid(column=1,row=0)
        
        self.refresh_data()
        #self.window.mainloop()

    def download_audio(self):
        #待施工！
        self.button_download_audio['state'] = 'disabled'
        path = filedialog.askdirectory(title='选择保存位置')
        if not path:
            return
        try:
            if self.abtype == 'av':
                cids = biliapis.avid_to_cid_online(self.abvid)
            else:
                cids = biliapis.bvid_to_cid_online(self.abvid)
            for cid in cids:
                if self.abtype == 'av':
                    stream = biliapis.get_video_stream_dash(cid,avid=self.abvid)
                else:
                    stream = biliapis.get_video_stream_dash(cid,bvid=self.abvid)
                stream = stream['audio']
                qs = []
                for item in stream:
                    qs += [item['quality']]
                stream = stream[qs.index(max(qs))]
                w = biliapis.DownloadWindow(stream['url'],path,f'{self.abvid} - cid{cid}.aac',False,topmost=config['topmost'])
            msgbox.showinfo('','Done.')
        except biliapis.BiliError as e:
            msgbox.showerror('','BiliError Occurred with Code %s:\n%s'%(e.code,e.msg))
        except Exception as e:
            msgbox.showerror('','Error Occurred:\n'+str(e))
        finally:
            self.button_download_audio['state'] = 'normal'
            return

    def jump_by_recommend(self,abvid):
        if abvid != '-' and abvid.strip():
            w = CommonVideoWindow(abvid)

    def _prepare_recommend(self,rec_length=40):
        '''
        需要在第一次调用 fill_recommend() 之前调用.
        因为推荐视频数量不能确定, 所以没有放在 __init__() 中.(标准的是40, 但有时会抽风)
        又因为queue的先进先出原则, 所以放在 refresh_data() 里通过queue传递指令来执行没有问题.

        '''
        pn = math.ceil(rec_length/self.rec_spage_objnum)
        for i in range(0,pn):
            self.obj_rec.append([])
            for o in range(0,self.rec_spage_objnum):
                self.obj_rec[i].append([])
                #相关视频的单个对象的布局. 牵扯到很多代码, 不要轻易改动.
                self.obj_rec[i][o].append(tk.Frame(self.frame_rec))#frame
                self.obj_rec[i][o].append(tk.Label(self.obj_rec[i][o][0],image=self.img_rec_empty))#cover
                self.obj_rec[i][o].append(tk.Text(self.obj_rec[i][o][0],bg='#f0f0f0',bd=0,height=2,width=30,state='disabled'))#title
                self.obj_rec[i][o].append(tk.Label(self.obj_rec[i][o][0],text='-'))#uploader
                self.obj_rec[i][o].append(tk.Label(self.obj_rec[i][o][0],text='-'))#bvid
                for t in range(0,5):
                    self.obj_rec[i][o][t].bind('<Button-1>',lambda x=0,i_=i,o_=o:self.jump_by_recommend(self.obj_rec[i_][o_][4]['text']))#绑定跳转操作
                c = 0
                for coor in [(0,o,1,1,'w'),(0,0,1,3,'w'),(1,0,2,1,'w'),(1,1,1,1,'w'),(2,1,1,1,'e')]:#(col,row,rspan,cspan,sticky)
                    self.obj_rec[i][o][c].grid(column=coor[0],row=coor[1],columnspan=coor[2],rowspan=coor[3],sticky=coor[4])
                    c += 1
                self.obj_rec[i][o][0].grid_remove()

    def refresh_data(self):
        def tmp():
            if not self.check_usable():
                self.task_queue.put_nowait(lambda:msgbox.showerror('','视频不存在'))
                self.task_queue.put_nowait(self.close)
                return
            if self.abtype == 'av':
                data = biliapis.get_video_detail(avid=self.abvid)
                tags = biliapis.get_video_tags(avid=self.abvid)
                self.recommend = biliapis.get_video_recommend(avid=self.abvid)
                opener_lambda = lambda:biliapis.open_in_explorer(f'https://www.bilibili.com/video/av%s'%self.abvid,config['explorer'])
            else:
                data = biliapis.get_video_detail(bvid=self.abvid)
                tags = biliapis.get_video_tags(bvid=self.abvid)
                self.recommend = biliapis.get_video_recommend(bvid=self.abvid)
                opener_lambda = lambda:biliapis.open_in_explorer(f'https://www.bilibili.com/video/'+self.abvid,config['explorer'])
            self.task_queue.put_nowait(lambda:self._prepare_recommend(len(self.recommend)))#准备相关视频的存放空间
            #explorer_opener
            self.task_queue.put_nowait(lambda:self.config_widget(self.button_open_in_ex,'command',opener_lambda))
            #common_info
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_avid,'text','AV%s'%data['avid']))
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_bvid,'text',data['bvid']))
            self.task_queue.put_nowait(lambda:self.set_text(self.text_title,lock=True,text=data['title']))
            #warning
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_warning,'text',data['warning_info']))
            #stat
            stat = data['stat']
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_view,'text',stat['view']))
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_like,'text',stat['like']))
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_coin,'text',stat['coin']))
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_collect,'text',stat['collect']))
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_share,'text',stat['share']))
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_dmkcount,'text',stat['danmaku']))
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_cmtcount,'text',stat['reply']))
            #up
            up = data['uploader']
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_uploader_name,'text',up['name']))
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_uploader_id,'text','UID%s'%up['uid']))
            #desc
            if data['description'].strip():
                desc = data['description']
            else:
                desc = '没有简介'
            self.task_queue.put_nowait(lambda:self.set_text(self.sctext_desc,lock=True,text=desc))
            #img
            self.task_queue.put_nowait(lambda:self.set_image(self.label_cover,BytesIO(biliapis.get_content_bytes(biliapis.format_img(data['picture'],w=380))),size=(380,232)))
            self.task_queue.put_nowait(lambda:self.label_cover_text.grid_remove())
            self.task_queue.put_nowait(lambda:self.set_image(self.label_uploader_face,BytesIO(biliapis.get_content_bytes(biliapis.format_img(up['face'],w=50,h=50))),size=(50,50)))
            self.task_queue.put_nowait(lambda:self.label_uploader_face_text.grid_remove())
            #parts
            parts = data['parts']
            counter = 0
            for line in parts:
                counter += 1
                self.task_queue.put_nowait(lambda n=str(counter),t=line['title'],l=biliapis.second_to_time(line['length']):self.tview_parts.insert("","end",values=(n,t,l)))
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_parts_counter,'text','共 %d 个分P'%counter))
            #tags
            if tags:
                tagtext = '#'+'# #'.join(tags)+'#'
            else:
                tagtext = '没有标签'
            self.task_queue.put_nowait(lambda:self.set_text(self.text_tags,lock=True,text=tagtext))
            #rec_img & rec_controller_unlock
            self.task_queue.put_nowait(lambda:self.fill_recommends(-1))
        _thread.start_new(tmp,())

    def fill_recommends(self,page=1):#在加载完成后调用时传入-1
        self.button_rec_next['state'] = 'disabled'
        self.button_rec_back['state'] = 'disabled'
        if not self.obj_rec:#保险措施
            self._prepare_recommend()
            page = -1
        if page != -1:
            for item in self.obj_rec[self.rec_page-1]:
                item[0].grid_remove()
        ttpage = math.ceil(len(self.recommend)/self.rec_spage_objnum)
        if page > ttpage:
            page = ttpage
        elif page < 1:
            page = 1
        if page in self.rec_page_his:
            pass
        else:
            def tmp_(o_,c_):
                self.task_queue.put_nowait(lambda w=o_[1],u=self.recommend[c_]['picture']:self.set_image(w,BytesIO(biliapis.get_content_bytes(biliapis.format_img(u,w=114,h=69))),size=(114,69)))
                self.task_queue.put_nowait(lambda w=o_[2],t=self.recommend[c_]['title']:self.set_text(w,text=t,lock=True))
                self.task_queue.put_nowait(lambda w=o_[3],t=self.recommend[c_]['uploader']['name']:self.config_widget(w,'text',t))
                self.task_queue.put_nowait(lambda w=o_[4],t=self.recommend[c_]['bvid']:self.config_widget(w,'text',t))
                self.task_queue.put_nowait(lambda w1=o_[0]:o_.append(tooltip.ToolTip(w1,text='点击打开')))#绑定tooltip
            c = (page-1)*self.rec_spage_objnum
            for o in self.obj_rec[page-1]:
                if c >= len(self.recommend):
                    break
                else:
                    _thread.start_new(tmp_,(o,c))
                    c += 1
            self.rec_page_his.append(page)
        self.rec_page = page
        for item in self.obj_rec[page-1]:
            item[0].grid()
        self.frame_rec['text'] = f'相关视频 {len(self.recommend)}个 {page}/{ttpage}页'
        self.button_rec_next['state'] = 'normal'
        self.button_rec_back['state'] = 'normal'

    def check_usable(self):
        try:
            if self.abtype == 'av':
                biliapis.get_video_detail(avid=self.abvid)
            else:
                biliapis.get_video_detail(bvid=self.abvid)
        except biliapis.BiliError as e:
            if e.code == -404:
                return False
            else:
                raise e
        else:
            return True

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
            msgbox.showwarning('','你所输入的内容无法转换为程序要求的类型.\n需要: '+type(self.accept_type))
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
