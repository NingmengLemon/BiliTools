import tkinter as tk
import tkinter.messagebox as msgbox
import tkinter.filedialog as filedialog
import tkinter.scrolledtext as scrolledtext
import tkinter.ttk as ttk
import os
import sys
import re
import time
import random
from io import BytesIO
import traceback
import math
import logging
import threading
import queue
import webbrowser
import json
import base64
import subprocess

import qrcode

import clipboard
import biliapis
import bilicodes
import tooltip
from basic_window import tkImg,Window
import imglib

#注意：
#为了页面美观，将 Button/Radiobutton/Checkbutton/Entry 的母模块从tk换成ttk
#↑步入现代风（并不

version = '2.0.0_Dev05'
work_dir = os.getcwd()
user_name = os.getlogin()
config_path = f'C:\\Users\\{user_name}\\bilitools_config.json'

config = {
    'topmost':True,
    'alpha':1.0,# 0.0 - 1.0
    'explorer':'chrome',# chrome / firefox
    'filter_emoji':False,
    'devmode':True, #开发模式开关
    'video_download':{
        'mode':'dash', # dash / mp4 / flv
        'dash':{
            'quality':'highest',# highest / lowest / regular
            'regular':[]# qid01, qid02, qid03 ...
            },
        'flv':{
            'quality':'highest',# highest / lowest / regular
            'regular':[]# qid01, qid02, qid03 ...
            },
        'mp4':{
            'quality':'highest',# highest / lowest
            'regular':[]# 摆设, 目的是规避错误
            }
        },
    }
#TODO: 设置保存与读取
biliapis.filter_emoji = config['filter_emoji']
#日志模块设置
logging.basicConfig(format='[%(asctime)s][%(levelname)s]%(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level={True:logging.DEBUG,False:logging.INFO}[config['devmode']]
                    )

tips = [
        '欢迎使用基于Bug开发的BiliTools（',
        '不管怎样，你得先告诉我你要去哪儿啊',
        'Bug是此程序的核心部分',
        '鸽子是此程序的作者的本体（咕',
        '想要反馈Bug？那你得先找到作者再说',
        'No one knows CREATING BUGs better than me！',
        '有一个程序员前来修Bug',
        '给我来一份烫烫烫的锟斤拷',
        '我好不容易写好一次, 你却崩溃得这么彻底',
        '（`Oω|',
        '钢板和锉刀你更喜欢哪一个？',
        '点我是可以刷新Tips哒ヾ(•ω•`)o'
        ]

about_info = '\n'.join([
    'BiliTools v.%s'%version,
    '一些功能需要 FFmpeg 的支持.',
    '感谢 @m13253（GitHub） 的弹幕转换程序的支持',
    '如你所见, 此程序还没有完工.',
    'Made by: @NingmengLemon（GitHub）',
    '---------------------------',
    '此程序严禁用于任何商业用途.',
    '此程序的作者不会为任何因使用此程序所造成的后果负责.',
    '感谢您的使用.'
    ])

def start_new_thread(func,args=(),kwargs=None,name=None):
    threading.Thread(target=func,args=args,kwargs=kwargs,name=name).start()

def replaceChr(text):
    repChr = {'/':'／','*':'＊',':':'：','\\':'＼','>':'＞',
              '<':'＜','|':'｜','?':'？','"':'＂'}
    for t in list(repChr.keys()):
        text = text.replace(t,repChr[t])
    return text

def check_ffmpeg():
    return not bool(os.popen('ffmpeg.exe -h').close())

def makeQrcode(data):
    qr = qrcode.QRCode()
    qr.add_data(data)
    img = qr.make_image()
    a = BytesIO()
    img.save(a,'png')
    return a #返回一个BytesIO对象

def merge_media(audio_file,video_file,output_file): #传入时要带后缀
    return bool(os.popen('ffmpeg.exe -i "{}" -i "{}" -vcodec copy -acodec copy "{}"'.format(audio_file,video_file,output_file)).close())

def convert_audio(from_file,to_file):
    return bool(os.popen('ffmpeg.exe -i "{}" -acodec libmp3lame "{}"'.format(from_file,to_file)).close())

class MainWindow(Window):
    def __init__(self):
        super().__init__('BiliTools - Main',False,config['topmost'],config['alpha'])

        #Entry Area
        self.frame_entry = tk.Frame(self.window)
        self.frame_entry.grid(column=0,row=0,columnspan=3)
        tk.Label(self.frame_entry,text='随便输入点什么吧~').grid(column=0,row=0,sticky='w')
        self.entry_source = ttk.Entry(self.frame_entry,width=40)
        self.entry_source.grid(column=0,row=1)
        #self.entry_source.bind('<Return>',lambda x=0:self.start())
        ttk.Button(self.frame_entry,text='粘贴',command=lambda:self.set_entry(self.entry_source,text=clipboard.getText()),width=5).grid(column=1,row=1)
        ttk.Button(self.frame_entry,text='清空',command=lambda:self.entry_source.delete(0,'end'),width=5).grid(column=2,row=1)
        #Login Area
        self.frame_login = tk.LabelFrame(self.window,text='用户信息')
        self.frame_login.grid(column=0,row=1,sticky='wns',rowspan=2)
        self.img_user_face_empty = tkImg(size=(120,120))
        self.label_face = tk.Label(self.frame_login,text='',image=self.img_user_face_empty)
        self.label_face.grid(column=0,row=0,sticky='nwe')
        self.label_face_text = tk.Label(self.frame_login,text='未登录',bg='#ffffff',font=('Microsoft YaHei UI',8))#图片上的提示文本
        self.label_face_text.grid(column=0,row=0)
        self.frame_login_button = tk.Frame(self.frame_login)
        self.frame_login_button.grid(column=0,row=1,sticky='nwe')
        self.button_login = ttk.Button(self.frame_login_button,text='登录',width=13,command=self.login)
        self.button_login.grid(column=0,row=0,sticky='w')
        self.button_refresh = ttk.Button(self.frame_login_button,command=self.refresh_data,state='disabled')
        self.set_image(self.button_refresh,imglib.refresh_sign,size=(17,17))
        self.button_refresh.grid(column=1,row=0)
        #Entry Mode Selecting
        self.frame_entrymode = tk.LabelFrame(self.window,text='输入模式',width=50)
        self.frame_entrymode.grid(column=1,row=1,sticky='enw',rowspan=2)
        self.intvar_entrymode = tk.IntVar(self.window,0)#跳转0, 搜索1, 快速下载2
        self.radiobutton_entrymode_jump = ttk.Radiobutton(self.frame_entrymode,value=0,variable=self.intvar_entrymode,text='跳转')
        self.radiobutton_entrymode_jump.grid(column=0,row=0,sticky='w')
        self.radiobutton_entrymode_search = ttk.Radiobutton(self.frame_entrymode,value=1,variable=self.intvar_entrymode,text='搜索',state='disabled')
        self.radiobutton_entrymode_search.grid(column=0,row=1,sticky='w')
        self.radiobutton_entrymode_fdown = ttk.Radiobutton(self.frame_entrymode,value=2,variable=self.intvar_entrymode,text='快速下载')
        self.radiobutton_entrymode_fdown.grid(column=0,row=2,sticky='w')
        
        ttk.Button(self.window,text='开始',width=11,command=self.start).grid(column=2,row=1,sticky='ne')
        #Basic Funcs
        self.frame_basicfuncs = tk.Frame(self.window)
        self.frame_basicfuncs.grid(column=2,row=2,sticky='se')
        ttk.Button(self.frame_basicfuncs,text='设置',width=11,command=self.goto_config).grid(column=0,row=1)#等待建设
        ttk.Button(self.frame_basicfuncs,text='关于',width=11,command=lambda:msgbox.showinfo('',about_info)).grid(column=0,row=2)
        #Funcs Area
        self.frame_funcarea = tk.LabelFrame(self.window,text='功能区')
        self.frame_funcarea.grid(column=0,row=3,sticky='wnse',columnspan=3)
        self.button_blackroom = ttk.Button(self.frame_funcarea,text='小黑屋',command=self.goto_blackroom)
        self.button_blackroom.grid(column=0,row=0,sticky='w')
        #Tips
        self.label_tips = tk.Label(self.window,text='Tips: -')
        self.label_tips.grid(column=0,row=4,sticky='w',columnspan=3)
        self.label_tips.bind('<Button-1>',lambda x=0:self.changeTips())

        self.changeTips()
        self.login(True)
        self.entry_source.focus()

        self.window.mainloop()

    def _clear_face(self):
        self.label_face.configure(image=self.img_user_face_empty)
        self.label_face.image = self.img_user_face_empty
        self.label_face_text.grid()
        self.label_face.unbind('<Button-1>')

    def _new_login(self):
        self.window.wm_attributes('-topmost',False)
        w = LoginWindow()
        if w.status:
            biliapis.load_local_cookies()
            self.refresh_data()
        else:
            msgbox.showwarning('','登录未完成.')
            self.task_queue.put_nowait(lambda:self.button_login.configure(state='normal'))
        self.window.wm_attributes('-topmost',config['topmost'])

    def refresh_data(self):
        def tmp():
            self.task_queue.put_nowait(lambda:self.button_login.configure(state='disabled'))
            self.task_queue.put_nowait(lambda:self.button_refresh.configure(state='disabled'))
            try:
                data = biliapis.get_login_info()
            except biliapis.BiliError as e:
                if e.code == -101:
                    self.task_queue.put_nowait(lambda:msgbox.showwarning('','未登录.'))
                    self.task_queue.put_nowait(lambda:self.button_login.configure(state='normal'))
                    self.task_queue.put_nowait(self._clear_face)
                    self.task_queue.put_nowait(lambda:self.button_login.configure(text='登录',command=self.login))
                    return
                else:
                    raise e
            def load_user_info(user_data):
                self.set_image(self.label_face,BytesIO(biliapis.get_content_bytes(biliapis.format_img(user_data['face'],w=120,h=120))))
                self.label_face_text.grid_remove()
                self.label_face.bind('<Button-1>',
                                     lambda event=None,text='{name}\nUID{uid}\nLv.{level}\n{vip_type}\nCoin: {coin}\nMoral: {moral}'.format(**user_data):msgbox.showinfo('User Info',text))
            self.task_queue.put_nowait(lambda:load_user_info(data))
            self.task_queue.put_nowait(lambda:self.button_login.configure(state='normal'))
            self.task_queue.put_nowait(lambda:self.button_refresh.configure(state='normal'))
            self.task_queue.put_nowait(lambda:self.button_login.configure(text='退出登录',command=self.logout))
        start_new_thread(tmp,())

    def login(self,init=False):
        def tmp():
            self.task_queue.put_nowait(lambda:self.button_login.configure(state='disabled'))
            if biliapis.is_cookiejar_usable():
                self.refresh_data()
                self.task_queue.put_nowait(lambda:self.button_login.configure(state='normal'))
                self.task_queue.put_nowait(lambda:self.button_refresh.configure(state='normal'))
                self.task_queue.put_nowait(lambda:self.button_login.configure(text='退出登录',command=self.logout))
            else:
                if not init:
                    self.task_queue.put_nowait(self._new_login)
                else:
                    self.task_queue.put_nowait(lambda:self.button_login.configure(state='normal'))
                    self.task_queue.put_nowait(self._clear_face)
                    self.task_queue.put_nowait(lambda:self.button_login.configure(text='登录',command=self.login))
        start_new_thread(tmp,())
            
    def logout(self):
        self.button_login.configure(state='disabled')
        try:
            biliapis.exit_login()
            biliapis.cookies.save()
        except biliapis.BiliError:
            msgbox.showwarning('','未登录.')
            self.button_login.configure(text='退出登录',command=self.logout)
            self.button_refresh.configure(state='normal')
        else:
            self.button_login.configure(text='登录',command=self.login)
            self.task_queue.put_nowait(self._clear_face)
            self.button_refresh.configure(state='disabled')
        finally:
            self.button_login.configure(state='normal')

    def goto_blackroom(self):
        w = BlackroomWindow()

    def goto_config(self):
        w = ConfigWindow()
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
        mode = self.intvar_entrymode.get()
        source,flag = biliapis.parse_url(source)
        if mode == 0:#跳转模式
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
        elif mode == 1:#搜索模式
            pass
        elif mode == 2:#快速下载模式
            if flag == 'unknown':
                msgbox.showinfo('','无法解析......')
            elif flag == 'avid' or flag == 'bvid':
                if flag == 'avid':
                    video_data = biliapis.get_video_detail(avid=source)
                else:
                    video_data = biliapis.get_video_detail(bvid=source)
                path = filedialog.askdirectory(title='选择保存位置')
                if not path:
                    return
                parts = video_data['parts']
                bvid = video_data['bvid']
                title = video_data['title']
                if len(parts) > 1:
                    tmp = []
                    for part in parts:
                        tmp += [[part['title'],biliapis.second_to_time(part['length']),part['cid']]]
                    indexes = PartsChooser(tmp).return_values
                    if not indexes:
                        return
                else:
                    indexes = [0]
                mode = config['video_download']['mode']
                quality = config['video_download'][mode]['quality']
                try:
                    SingleVideoDownloader(bvid,path,quality,indexes,mode)
                except Exception as e:
                    raise e #
                finally:
                    return
            else:
                msgbox.showinfo('','暂不支持%s的快速下载'%flag)

class ConfigWindow(Window):
    def __init__(self):
        super().__init__('BiliToools - Config',True,config['topmost'],config['alpha'])
        
        #Basic
        self.frame_basic = tk.LabelFrame(self.window,text='基础设置')
        self.frame_basic.grid(column=0,row=0,sticky='nw')
        #Topmost
        self.boolvar_topmost = tk.BooleanVar(self.window,config['topmost'])
        self.checkbutton_topmost = ttk.Checkbutton(self.frame_basic,text='置顶',onvalue=True,offvalue=False,variable=self.boolvar_topmost)
        self.checkbutton_topmost.grid(column=0,row=0,sticky='w')
        #Alpha
        self.frame_winalpha = tk.LabelFrame(self.frame_basic,text='窗体不透明度')
        self.frame_winalpha.grid(column=0,row=1,sticky='w')
        self.doublevar_winalpha = tk.DoubleVar(self.window,value=config['alpha'])
        self.label_winalpha_shower = tk.Label(self.frame_winalpha,text='% 3d%%'%(config['alpha']*100))
        self.label_winalpha_shower.grid(column=0,row=0,sticky='w')
        self.scale_winalpha = ttk.Scale(self.frame_winalpha,from_=0.3,to=1.0,orient=tk.HORIZONTAL,variable=self.doublevar_winalpha,command=lambda coor:self.label_winalpha_shower.configure(text='% 3d%%'%(round(float(coor),2)*100)))
        self.scale_winalpha.grid(column=1,row=0,sticky='w')
        self.tooltip_winalpha = tooltip.ToolTip(self.frame_winalpha,text='注意，不透明度调得过低会影响操作体验')
        #Emoji Filter
        self.frame_filteremoji = tk.Frame(self.frame_basic)
        self.frame_filteremoji.grid(column=0,row=2,sticky='w')
        self.boolvar_filteremoji = tk.BooleanVar(self.window,config['filter_emoji'])
        self.checkbutton_filteremoji = ttk.Checkbutton(self.frame_filteremoji,text='过滤Emoji',onvalue=True,offvalue=False,variable=self.boolvar_filteremoji)
        self.checkbutton_filteremoji.grid(column=0,row=0)
        self.label_filteremoji_help = tk.Label(self.frame_filteremoji,text='')
        self.set_image(self.label_filteremoji_help,imglib.help_sign,size=(16,16))
        self.label_filteremoji_help.grid(column=1,row=0)
        self.tooltip_filteremoji = tooltip.ToolTip(self.label_filteremoji_help,text='此功能专为某些不支持Emoji显示的设备添加 :)')

        #Video Download
        self.frame_video = tk.LabelFrame(self.window,text='视频下载设置')
        self.frame_video.grid(column=1,row=0,sticky='nw')
        #Mode
        self.stringvar_videomode = tk.StringVar(self.window,config['video_download']['mode'])
        self.frame_videomode_dash = tk.Frame(self.frame_video)
        self.frame_videomode_dash.grid(column=0,row=0,sticky='w')
        self.radiobutton_videomode_dash = ttk.Radiobutton(self.frame_videomode_dash,text='DASH流',value='dash',variable=self.stringvar_videomode,command=self.change_videomode)
        self.radiobutton_videomode_dash.grid(column=0,row=0)
        self.label_videomode_dash_info = tk.Label(self.frame_videomode_dash,text='')
        self.set_image(self.label_videomode_dash_info,imglib.info_sign,size=(18,18))
        self.label_videomode_dash_info.grid(column=1,row=0)
        self.tooltip_videomode_dash = tooltip.ToolTip(self.label_videomode_dash_info,text='需要FFmpeg的支持.')
        self.radiobutton_videomode_flv = ttk.Radiobutton(self.frame_video,text='Flv',value='flv',variable=self.stringvar_videomode,command=self.change_videomode,state='disabled')
        self.radiobutton_videomode_flv.grid(column=0,row=1,sticky='w')
        self.frame_videomode_mp4 = tk.Frame(self.frame_video)
        self.frame_videomode_mp4.grid(column=0,row=2,sticky='w')
        self.radiobutton_videomode_mp4 = ttk.Radiobutton(self.frame_videomode_mp4,text='低清MP4',value='mp4',variable=self.stringvar_videomode,command=self.change_videomode,state='disabled')
        self.radiobutton_videomode_mp4.grid(column=0,row=0)
        self.label_videomode_mp4_info = tk.Label(self.frame_videomode_mp4,text='')
        self.set_image(self.label_videomode_mp4_info,imglib.info_sign,size=(18,18))
        self.label_videomode_mp4_info.grid(column=1,row=0)
        self.tooltip_videomode_mp4 = tooltip.ToolTip(self.label_videomode_mp4_info,text='仅支持240P与360P, 且限速65KB/s')
        #Strategy
        self.frame_strategy = tk.LabelFrame(self.frame_video,text='下载策略')
        self.frame_strategy.grid(column=0,row=3)
        self.stringvar_strategy = tk.StringVar(self.window,config['video_download'][config['video_download']['mode']]['quality'])
        self.radiobutton_highest = ttk.Radiobutton(self.frame_strategy,text='最高画质',value='highest',variable=self.stringvar_strategy,command=self.change_strategy)
        self.radiobutton_highest.grid(column=0,row=0,sticky='w')
        self.radiobutton_lowest = ttk.Radiobutton(self.frame_strategy,text='最低画质',value='lowest',variable=self.stringvar_strategy,command=self.change_strategy)
        self.radiobutton_lowest.grid(column=0,row=1,sticky='w')
        self.radiobutton_regular = ttk.Radiobutton(self.frame_strategy,text='自定义规则',value='regular',variable=self.stringvar_strategy,command=self.change_strategy)
        self.radiobutton_regular.grid(column=0,row=2,sticky='w')
        self.frame_regular = tk.Frame(self.frame_strategy)
        self.frame_regular.grid(column=0,row=3)
        self.listbox_regular = tk.Listbox(self.frame_regular,width=10,height=8,selectmode='extended')
        self.listbox_regular.grid(column=0,row=0,rowspan=5)
        for item in config['video_download'][config['video_download']['mode']]['regular']:
            self.listbox_regular.insert('end',bilicodes.stream_dash_video_quality[item])
        self.stringvar_quality = {'dash':tk.StringVar(self.window,'360P'),
                                  'flv':tk.StringVar(self.window,'360P'),
                                  'mp4':tk.StringVar(self.window,'360P')}
        self.optmenu_quality = {'dash':ttk.OptionMenu(self.frame_regular,self.stringvar_quality['dash'],'360P',*list(bilicodes.stream_dash_video_quality.values())),
                                'flv':ttk.OptionMenu(self.frame_regular,self.stringvar_quality['flv'],'360P',*list(bilicodes.stream_flv_video_quality.values())),
                                'mp4':ttk.OptionMenu(self.frame_regular,self.stringvar_quality['mp4'],'360P',*list(bilicodes.stream_mp4_video_quality.values()))}
        self.quality_codes = {'dash':bilicodes.stream_dash_video_quality,
                            'flv':bilicodes.stream_flv_video_quality,
                            'mp4':bilicodes.stream_mp4_video_quality,
                            'dash_':bilicodes.stream_dash_video_quality_,
                            'flv_':bilicodes.stream_flv_video_quality_,
                            'mp4_':bilicodes.stream_mp4_video_quality_}
        for widget_name in self.optmenu_quality.keys():
            self.optmenu_quality[widget_name].grid(column=1,row=0)
            if widget_name != config['video_download']['mode']:
                self.optmenu_quality[widget_name].grid_remove()
        ttk.Button(self.frame_regular,text='从上方插入',command=lambda:self.listbox_regular.insert(0,self.stringvar_quality[self.stringvar_videomode.get()].get())).grid(column=1,row=1,sticky='sw')
        ttk.Button(self.frame_regular,text='从下方插入',command=lambda:self.listbox_regular.insert('end',self.stringvar_quality[self.stringvar_videomode.get()].get())).grid(column=1,row=2,sticky='nw')
        ttk.Button(self.frame_regular,text='删除选中',command=lambda:self.listbox_regular.delete('active')).grid(column=1,row=3,sticky='sw')
        ttk.Button(self.frame_regular,text='删除全部',command=lambda:self.listbox_regular.delete(0,'end')).grid(column=1,row=4,sticky='nw')
        ttk.Button(self.frame_regular,text='保存策略设置',command=self.save_strategy).grid(column=0,row=5,columnspan=2,sticky='w')
        self.text_regular_help = tk.Label(self.frame_regular,text='如何使用？',font=('Microsoft YaHei UI',8),fg='#2080f0')
        self.text_regular_help.grid(column=0,row=6,sticky='w')
        self.text_regular_help.bind('<Button-1>',self.show_regular_help)
        if self.stringvar_videomode.get() == 'mp4':
            self.radiobutton_regular.grid_remove()
            self.frame_regular.grid_remove()
        if self.stringvar_strategy.get() != 'regular':
            self.frame_regular.grid_remove()

        # Save or Cancel
        self.frame_soc = tk.Frame(self.window)
        self.frame_soc.grid(column=1,row=1,sticky='se')
        ttk.Button(self.frame_soc,text='取消',width=5,command=self.close).grid(column=0,row=0)
        ttk.Button(self.frame_soc,text='保存',width=5,command=self.save_config).grid(column=1,row=0)

        self.window.mainloop()

    def save_strategy(self):
        global config
        mode = self.stringvar_videomode.get()
        config['video_download'][mode]['quality'] = self.stringvar_strategy.get()
        for item in list(self.listbox_regular.get(0,'end')):
            config['video_download'][mode]['regular'].append(self.quality_codes[mode+'_'][item])

    def change_videomode(self):
        var_mode = self.stringvar_videomode.get()
        var_strategy = self.stringvar_strategy.get()
        if var_mode == 'mp4':
            self.radiobutton_regular.grid_remove()
        else:
            self.radiobutton_regular.grid()
            self.listbox_regular.delete(0,'end')
            for item in config['video_download'][var_mode]['regular']:
                self.listbox_regular.insert('end',self.quality_codes[var_mode][item])
        self.stringvar_strategy.set(config['video_download'][var_mode]['quality'])
        self.change_strategy()
        for widget_name in self.optmenu_quality.keys():
            if widget_name == var_mode:
                self.optmenu_quality[widget_name].grid()
            else:
                self.optmenu_quality[widget_name].grid_remove()

    def change_strategy(self):
        if self.stringvar_strategy.get() == 'regular' and self.stringvar_videomode.get() != 'mp4':
            self.frame_regular.grid()
        else:
            self.frame_regular.grid_remove()

    def show_regular_help(self,event=None):
        text = '待填充 (`Ov|'
        msgbox.showinfo('',text)

    def apply_config(self):#
        global config
        config['topmost'] = self.boolvar_topmost.get()
        config['alpha'] = round(self.doublevar_winalpha.get(),2)
        config['filter_emoji'] = self.boolvar_filteremoji.get()
        biliapis.filter_emoji = config['filter_emoji']
        self.save_strategy()

    def save_config(self):
        self.apply_config()
        self.close()

class AudioWindow(Window):
    def __init__(self,auid):
        self.auid = int(auid)
        
        super().__init__('BiliToools - Audio',True,config['topmost'],config['alpha'])

        #cover
        self.img_cover_empty = tkImg(size=(300,300))
        self.label_cover_shower = tk.Label(self.window,image=self.img_cover_empty)
        self.label_cover_shower.grid(column=0,row=0,rowspan=4,sticky='w')
        self.label_cover_text = tk.Label(self.window,text='加载中',font=('Microsoft YaHei UI',8),bg='#ffffff')
        self.label_cover_text.grid(column=0,row=0,rowspan=4)
        #audio name
        self.text_name = tk.Text(self.window,font=('Microsoft YaHei UI',10,'bold'),width=37,height=2,state='disabled',bg='#f0f0f0',bd=0)
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
        self.label_uploader_face_text = tk.Label(self.frame_uploader,text='加载中',font=('Microsoft YaHei UI',8),bg='#ffffff')
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
        self.button_open_in_ex = ttk.Button(self.frame_operation,text='在浏览器中打开',command=lambda:webbrowser.open(f'https://www.bilibili.com/audio/au{self.auid}'))
        self.button_open_in_ex.grid(column=3,row=0)
        self.frame_operation.grid(column=0,row=8,columnspan=2)

        self.refresh_data()
        self.window.mainloop()

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
        start_new_thread(tmp,())

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

        self.video_data = None
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
        self.set_image(self.label_warning,imglib.warning_sign)
        self.label_warning.grid(column=0,row=2,sticky='e')
        self.label_warning.grid_remove()
        self.label_warning_tooltip = None
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
        self.button_download_video = ttk.Button(self.frame_operation,text='下载视频',command=self.download_video)
        self.button_download_video.grid(column=2,row=0)
        #左起第2列
        self.frame_left_2 = tk.Frame(self.window)
        self.frame_left_2.grid(column=1,row=0)
        #uploader
        self.frame_uploader = tk.LabelFrame(self.frame_left_2,text='UP主')
        self.img_upface_empty = tkImg(size=(50,50))
        self.label_uploader_face = tk.Label(self.frame_uploader,image=self.img_upface_empty)#up头像
        self.label_uploader_face.grid(column=0,row=0,rowspan=2)
        self.label_uploader_face_text = tk.Label(self.frame_uploader,text='加载中',font=('Microsoft YaHei UI',8),bg='#ffffff')
        self.label_uploader_face_text.grid(column=0,row=0,rowspan=2)
        self.label_uploader_name = tk.Label(self.frame_uploader,text='-')#up名字
        self.label_uploader_name.grid(column=1,row=0,sticky='w')
        self.label_uploader_id = tk.Label(self.frame_uploader,text='UID0')#uid
        self.label_uploader_id.grid(column=1,row=1,sticky='w')
        self.frame_uploader.grid(column=0,row=0,sticky='nw')
        #extra operation
        self.frame_extraopt = tk.Frame(self.frame_left_2)
        self.frame_extraopt.grid(column=0,row=0,sticky='se')
        self.button_show_comments = ttk.Button(self.frame_extraopt,text='查看评论',command=lambda:msgbox.showinfo('','建设中'))#
        self.button_show_comments.grid(column=0,row=0,sticky='se')
        self.button_show_pbp = ttk.Button(self.frame_extraopt,text='查看PBP',command=self.show_pbp)
        self.button_show_pbp.grid(column=0,row=1)
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
        self.rec_page = 1
        self.rec_spage_objnum = 5 #每页项数
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
        #调试信息
        self.frame_debug = tk.Frame(self.window)
        self.frame_debug.grid(column=0,row=1,columnspan=3,sticky='w')
        tk.Label(self.frame_debug,text='Thread:').grid(column=0,row=0)
        self.label_thread_count = tk.Label(self.frame_debug,text='0')
        self.label_thread_count.grid(column=1,row=0)
        tk.Label(self.frame_debug,text='|').grid(column=2,row=0)
        tk.Label(self.frame_debug,text='Queue:').grid(column=3,row=0)
        self.label_queue_count = tk.Label(self.frame_debug,text='0')
        self.label_queue_count.grid(column=4,row=0)

        self.update_debug_info()
        self.refresh_data()

        self.window.mainloop()

    def show_pbp(self):
        if not self.video_data:
            msgbox.showwarning('','加载尚未完成')
            return
        tmplist = []
        parts = self.video_data['parts']
        if len(parts) > 1:
            for part in parts:
                tmplist.append([
                    part['title'],
                    biliapis.second_to_time(part['length']),
                    str(part['cid'])
                    ])
            w = PartsChooser(tmplist)
            target = w.return_values
        else:
            target = [0]
        for index in target:
            PbpShower(parts[index]['cid'])

    def update_debug_info(self):#自动循环
        self.label_thread_count['text'] = str(threading.active_count())
        self.label_queue_count['text'] = str(self.task_queue.qsize())
        self.window.after(10,self.update_debug_info)

    def download_audio(self):
        if not self.video_data:
            msgbox.showwarning('','加载尚未完成')
            return
        self.button_download_audio['state'] = 'disabled'
        path = filedialog.askdirectory(title='选择保存位置')
        if not path:
            return
        parts = self.video_data['parts']
        bvid = self.video_data['bvid']
        title = self.video_data['title']
        if len(parts) > 1:
            tmp = []
            for part in parts:
                tmp += [[part['title'],biliapis.second_to_time(part['length']),part['cid']]]
            indexes = PartsChooser(tmp).return_values
            if not indexes:
                return
        else:
            indexes = [0]
        try:
            for index in indexes:
                cid = parts[index]['cid']
                stream = biliapis.get_video_stream_dash(cid,bvid=bvid)
                stream = stream['audio']
                qs = []
                for item in stream:
                    qs += [item['quality']]
                stream = stream[qs.index(max(qs))]
                w = biliapis.DownloadWindow(stream['url'],
                                            path,
                                            '{}_P{}_{}_cid{}_{}.aac'.format(
                                                title,
                                                index+1,
                                                bvid,cid,
                                                bilicodes.stream_dash_audio_quality[max(qs)]),
                                            False,topmost=config['topmost']
                                            )
            msgbox.showinfo('','Done.')
        except biliapis.BiliError as e:
            msgbox.showerror('','BiliError Occurred with Code %s:\n%s'%(e.code,e.msg))
        except Exception as e:
            msgbox.showerror('','Error Occurred:\n'+str(e))
        finally:
            if self.is_alive:
                self.button_download_audio['state'] = 'normal'
            return

    def download_video(self):
        if not self.video_data:
            msgbox.showwarning('','加载尚未完成')
            return
        self.button_download_video['state'] = 'disabled'
        path = filedialog.askdirectory(title='选择保存位置')
        if not path:
            return
        parts = self.video_data['parts']
        bvid = self.video_data['bvid']
        title = self.video_data['title']
        if len(parts) > 1:
            tmp = []
            for part in parts:
                tmp += [[part['title'],biliapis.second_to_time(part['length']),part['cid']]]
            indexes = PartsChooser(tmp).return_values
            if not indexes:
                return
        else:
            indexes = [0]
        mode = config['video_download']['mode']
        quality = config['video_download'][mode]['quality']
        try:
            SingleVideoDownloader(bvid,path,quality,indexes,mode)
        except Exception as e:
            raise e #
        finally:
            if self.is_alive:
                self.button_download_video['state'] = 'normal'
            return

    def jump_by_recommend(self,abvid):
        if abvid != '-' and abvid.strip():
            w = CommonVideoWindow(abvid)

    def _prepare_recommend(self,rec_length=40):
        '''
        需要在第一次调用 fill_recommend() 之前调用.
        因为推荐视频数量不能确定, 所以没有放在 __init__() 中.(标准的是40, 但有时会抽风, 并且在处理番剧ID时为0)
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
                self.obj_rec[i][o][1].bind('<Button-1>',lambda x=0,i_=i,o_=o:self.jump_by_recommend(self.obj_rec[i_][o_][4]['text']))#绑定跳转操作
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
                opener_lambda = lambda:webbrowser.open(f'https://www.bilibili.com/video/av%s'%self.abvid)
            else:
                data = biliapis.get_video_detail(bvid=self.abvid)
                tags = biliapis.get_video_tags(bvid=self.abvid)
                self.recommend = biliapis.get_video_recommend(bvid=self.abvid)
                opener_lambda = lambda:webbrowser.open(f'https://www.bilibili.com/video/'+self.abvid)
            self.video_data = data
            self.task_queue.put_nowait(lambda:self._prepare_recommend(len(self.recommend)))#准备相关视频的存放空间
            #explorer_opener
            self.task_queue.put_nowait(lambda:self.config_widget(self.button_open_in_ex,'command',opener_lambda))
            #common_info
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_avid,'text','AV%s'%data['avid']))
            self.task_queue.put_nowait(lambda:self.config_widget(self.label_bvid,'text',data['bvid']))
            self.task_queue.put_nowait(lambda:self.set_text(self.text_title,lock=True,text=data['title']))
            #warning
            def fill_warning_info(warning_info):
                if warning_info.strip():
                    self.label_warning.grid()
                    self.label_warning_tooltip = tooltip.ToolTip(self.label_warning,text=warning_info)
                    self.label_warning.bind('<Button-1>',lambda e=None,t=warning_info:msgbox.showinfo('',t))
            self.task_queue.put_nowait(lambda wi=data['warning_info']:fill_warning_info(wi))
            #stat
            stat = data['stat']
            def fill_stat(statdata):
                self.label_view['text'] = statdata['view']
                self.label_like['text'] = statdata['like']
                self.label_coin['text'] = statdata['coin']
                self.label_collect['text'] = statdata['collect']
                self.label_share['text'] = statdata['share']
                self.label_dmkcount['text'] = statdata['danmaku']
                self.label_cmtcount['text'] = statdata['reply']
            self.task_queue.put_nowait(lambda sd=stat:fill_stat(sd))
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
            def load_img():
                self.task_queue.put_nowait(lambda img=BytesIO(biliapis.get_content_bytes(biliapis.format_img(data['picture'],w=380))):
                                           self.set_image(self.label_cover,img,size=(380,232)))
                self.task_queue.put_nowait(lambda:self.label_cover_text.grid_remove())
                self.task_queue.put_nowait(lambda img=BytesIO(biliapis.get_content_bytes(biliapis.format_img(up['face'],w=50,h=50))):
                                           self.set_image(self.label_uploader_face,img,size=(50,50)))
                self.task_queue.put_nowait(lambda:self.label_uploader_face_text.grid_remove())
            start_new_thread(load_img)
            #parts
            parts = data['parts']
            def fill_partlist(plist):
                counter = 0
                for line in parts:
                    counter += 1
                    self.tview_parts.insert("","end",values=(str(counter),line['title'],biliapis.second_to_time(line['length'])))
                self.label_parts_counter['text'] = '共 %d 个分P'%counter
            self.task_queue.put_nowait(lambda:fill_partlist(parts))
            #tags
            if tags:
                tagtext = '#'+'# #'.join(tags)+'#'
            else:
                tagtext = '没有标签'
            self.task_queue.put_nowait(lambda:self.set_text(self.text_tags,lock=True,text=tagtext))
            #rec_img & rec_controller_unlock
            self.task_queue.put_nowait(lambda:self.fill_recommends(-1))
        start_new_thread(tmp,())

    def fill_recommends(self,page=1):#在加载完成后第一次调用时传入-1
        if not self.obj_rec:
            #防止特殊情况下推荐视频数为0
            self.button_rec_next.grid_remove()
            self.button_rec_back.grid_remove()
            self.text_tags['height'] = 20
            return
        self.button_rec_next['state'] = 'disabled'
        self.button_rec_back['state'] = 'disabled'
        if page != -1:
            for item in self.obj_rec[self.rec_page-1]:
                item[0].grid_remove()
        ttpage = math.ceil(len(self.recommend)/self.rec_spage_objnum)
        if page > ttpage:
            page = ttpage
        elif page < 1:
            page = 1
        if page in self.rec_page_his:#检查翻页历史, 如果翻过了就不再重新加载
            pass
        else:
            def tmp_(o_,c_):
                self.task_queue.put_nowait(lambda w=o_[1],img=BytesIO(biliapis.get_content_bytes(biliapis.format_img(self.recommend[c_]['picture'],w=114,h=69))):
                                           self.set_image(w,img,size=(114,69)))
                self.task_queue.put_nowait(lambda w=o_[2],t=self.recommend[c_]['title']:self.set_text(w,text=t,lock=True))
                self.task_queue.put_nowait(lambda w=o_[3],t=self.recommend[c_]['uploader']['name']:self.config_widget(w,'text',t))
                self.task_queue.put_nowait(lambda w=o_[4],t=self.recommend[c_]['bvid']:self.config_widget(w,'text',t))
                #绑定tooltip
                self.task_queue.put_nowait(lambda w=o_[1]:o_.append(tooltip.ToolTip(w,text='点击跳转到此视频')))
                self.task_queue.put_nowait(lambda w=o_[2],t=self.recommend[c_]['title']:o_.append(tooltip.ToolTip(w,text=t)))
                self.task_queue.put_nowait(lambda w=o_[3],t='%s\nUID%s'%(self.recommend[c_]['uploader']['name'],self.recommend[c_]['uploader']['uid']):
                                           o_.append(tooltip.ToolTip(w,text=t)))
                self.task_queue.put_nowait(lambda w=o_[4],t='%s\nav%s\n播放: %s\n弹幕: %s\n评论: %s'%(self.recommend[c_]['bvid'],
                                                                                                self.recommend[c_]['avid'],
                                                                                                self.recommend[c_]['stat']['view'],
                                                                                                self.recommend[c_]['stat']['danmaku'],
                                                                                                self.recommend[c_]['stat']['reply']):o_.append(tooltip.ToolTip(w,text=t)))
            c = (page-1)*self.rec_spage_objnum
            for o in self.obj_rec[page-1]:
                if c >= len(self.recommend):
                    break
                else:
                    start_new_thread(tmp_,(o,c))
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
        self.label_text = tk.Label(self.window,text='未获取',font=('Microsoft YaHei UI',15))
        self.label_text.pack(pady=10)
        self.button_refresh = ttk.Button(self.window,text='刷新',state='disabled',command=self.fresh)
        self.button_refresh.pack()
        
        self.fresh()
        logging.info('LoginWindow Initialization Completed')
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
            cookiejar = biliapis.make_cookiejar(self.final_url)
            cookiejar.save(os.path.abspath('./cookies.txt'))
            logging.debug('Cookie File saved to '+os.path.abspath('./cookies.txt'))
            self.window.after(1000,self.close)
            return
        elif self.condition == -2:
            self.button_refresh['state'] = 'normal'
            self.qrcode_img = tkImg(size=(300,300))
            self.label_imgshower.configure(image=self.qrcode_img)
            self.label_imgshower.image = self.qrcode_img
            return
        elif self.condition == -4 or self.condition == -5:
            self.window.after(2000,self.start_autocheck)
            return
            
    def close(self):
        self.window.quit()
        self.window.destroy()

class PbpShower(Window):
    def __init__(self,cid):
        super().__init__('BiliTools - PBP Shower of cid{}'.format(cid),True,config['topmost'],config['alpha'])

        try:
            self.pbp_data = biliapis.get_pbp(cid)
        except biliapis.BiliError as e:
            msgbox.showerror('','BiliError Code {}: {}'.format(e.code,e.msg))
            self.close()
            return
        self.length = len(self.pbp_data['data'])*self.pbp_data['step_sec']

        self.chart = tk.Canvas(self.window,height=400,width=800,bg='#ffffff')
        self.chart.grid(column=0,row=0,columnspan=2)
        w = int(self.chart['width'])
        h = int(self.chart['height'])

        step = w / len(self.pbp_data['data'])
        scale = h / max(self.pbp_data['data'])
        x = 1
        chart_data = []
        for p in self.pbp_data['data']:
            chart_data += [x,h-p*scale+1]
            x += step
        self.chart.create_line(chart_data)

        self.x_scanline = self.chart.create_line(0,0,w,0)
        self.y_scanline = self.chart.create_line(0,0,0,h)

        self.chart.bind('<B1-Motion>',self.track_scanline)
        self.chart.bind('<ButtonRelease-1>',self.move_away)
        
        self.frame_coorshower = tk.Frame(self.window)
        self.frame_coorshower.grid(column=0,row=1,sticky='w')
        tk.Label(self.frame_coorshower,text='Mouse x:').grid(column=0,row=0,sticky='w')
        self.x_shower = tk.Label(self.frame_coorshower,text='-')
        self.x_shower.grid(column=1,row=0,sticky='w')
        tk.Label(self.frame_coorshower,text='Mouse y:').grid(column=0,row=1,sticky='w')
        self.y_shower = tk.Label(self.frame_coorshower,text='-')
        self.y_shower.grid(column=1,row=1,sticky='w')

        self.frame_datashower = tk.Frame(self.window)
        self.frame_datashower.grid(column=1,row=1,sticky='e')
        tk.Label(self.frame_datashower,text='Total Length:').grid(column=0,row=0,sticky='w')
        tk.Label(self.frame_datashower,text=biliapis.second_to_time(self.length)).grid(column=1,row=0,sticky='w')
        tk.Label(self.frame_datashower,text='Realtime Position:').grid(column=0,row=1,sticky='w')
        self.label_rtlength = tk.Label(self.frame_datashower,text='--------')
        self.label_rtlength.grid(column=1,row=1,sticky='w')

        self.window.mainloop()

    def move_away(self,event):
        self.chart.itemconfig(self.x_scanline,state='hidden')
        self.chart.itemconfig(self.y_scanline,state='hidden')
        self.x_shower['text'] = '-'
        self.y_shower['text'] = '-'
        self.label_rtlength['text'] = '--------'

    def track_scanline(self,event):
        self.chart.itemconfig(self.x_scanline,state='normal')
        self.chart.itemconfig(self.y_scanline,state='normal')
        w = int(self.chart['width'])
        h = int(self.chart['height'])
        x = self.chart.canvasx(event.x)
        y = self.chart.canvasy(event.y)
        self.chart.coords(self.x_scanline,x,0,x,h)
        self.chart.coords(self.y_scanline,0,y,w,y)
        self.x_shower['text'] = '{}'.format(x)
        self.y_shower['text'] = '{}'.format(y)
        if x >= 0 and x <= w:
            self.label_rtlength['text'] = biliapis.second_to_time(self.length/w*x)
        else:
            self.label_rtlength['text'] = '--------'

class PartsChooser(Window):
    def __init__(self,part_list,title='PartsChooser',columns=['分P名','长度','Cid','编码'],columns_widths=[200,70,90,100]):
        self.return_values = [] #Selected Indexes
        super().__init__('BiliTools - PartsChooser',True,config['topmost'],config['alpha'])
        #part_list: 逐行多维数组
        #例如:
        #[
        # ['Wdnmd',99999,233333,'H.265'],
        # ['nyanyanyanyanya',88888,55555555,'Flash Video']
        #]
        self.columns = columns
        self.part_list = part_list
        tk.Label(self.window,text=title).grid(column=0,row=0)
        self.frame_parts = tk.Frame(self.window)
        self.frame_parts.grid(column=0,row=1)
        self.scbar_parts_y = tk.Scrollbar(self.frame_parts,orient='vertical')
        self.scbar_parts_x = tk.Scrollbar(self.frame_parts,orient='horizontal')
        self.tview_parts = ttk.Treeview(self.frame_parts,show="headings",columns=tuple(['序号']+self.columns),yscrollcommand=self.scbar_parts_y.set,xscrollcommand=self.scbar_parts_x.set,height=15)
        self.scbar_parts_y['command'] = self.tview_parts.yview
        self.scbar_parts_x['command'] = self.tview_parts.xview
        self.tview_parts.column("序号", width=40,anchor='e')
        self.tview_parts.heading("序号", text="序号",anchor='w')
        self.tview_parts.grid(column=0,row=0)
        self.scbar_parts_y.grid(column=1,row=0,sticky='nw',ipady=140)
        self.scbar_parts_x.grid(column=0,row=1,sticky='nw',ipadx=210)
        #初始化表头
        i = 0
        for column in columns:
            self.tview_parts.column(column,width=columns_widths[i],anchor='w')
            self.tview_parts.heading(column,text=column,anchor='w')
            i += 1
        #填充数据
        i = 0
        for line in part_list:
            i += 1        
            self.tview_parts.insert("","end",values=tuple([str(i)]+line))
        #操作区
        self.frame_opt = tk.Frame(self.window)
        self.frame_opt.grid(column=0,row=2,sticky='e')
        ttk.Button(self.frame_opt,text='取消',command=self.close).grid(column=0,row=0,sticky='e')
        ttk.Button(self.frame_opt,text='返回全部项',command=self.return_all).grid(column=1,row=0,sticky='e')
        ttk.Button(self.frame_opt,text='返回选中项',command=self.return_selected).grid(column=2,row=0,sticky='e')
        self.window.mainloop()

    def return_selected(self):
        sel = []
        for item in self.tview_parts.selection():
            sel.append(int(self.tview_parts.item(item,"values")[0])-1)
        if not sel:
            return
        self.return_values = sel
        self.close()

    def return_all(self):
        tmp = []
        for i in self.tview_parts.get_children():
            tmp.append(int(self.tview_parts.item(i,'values')[0])-1)
        if not tmp:
            return
        self.return_values = tmp
        self.close()

class BlackroomWindow(Window):
    def __init__(self):
        self.data_pool = []
        self.loaded_page = 0
        self.page = 1
        super().__init__('BiliTools - Blackroom',True,config['topmost'],config['alpha'])

        #内容框架
        self.frame_content = tk.Frame(self.window)
        self.frame_content.grid(column=0,row=0)
        #Target
        self.frame_target = tk.Frame(self.frame_content)
        self.frame_target.grid(column=0,row=0)
        self.img_targetface_empty = tkImg(size=(50,50))
        self.label_target_face = tk.Label(self.frame_target,image=self.img_targetface_empty)#用户头像
        self.label_target_face.grid(column=0,row=0,rowspan=2)
        self.label_target_face_text = tk.Label(self.frame_target,text='加载中',font=('Microsoft YaHei UI',8),bg='#ffffff')
        self.label_target_face_text.grid(column=0,row=0,rowspan=2)
        self.label_target_name = tk.Label(self.frame_target,text='-')#用户昵称
        self.label_target_name.grid(column=1,row=0,sticky='w')
        self.label_target_id = tk.Label(self.frame_target,text='UID0')#uid
        self.label_target_id.grid(column=1,row=1,sticky='w')
        #Behavior
        self.frame_behavior = tk.Frame(self.frame_content)
        self.frame_behavior.grid(column=0,row=1)
        tk.Label(self.frame_behavior,text='违规行为: ').grid(column=0,row=0,sticky='sw')
        tk.Label(self.frame_behavior,text='处理手段: ').grid(column=0,row=1,sticky='sw')
        self.label_behavior = tk.Label(self.frame_behavior,text='-',font=('Microsoft YaHei UI',14))
        self.label_behavior.grid(column=1,row=0,sticky='w')
        self.label_treatment = tk.Label(self.frame_behavior,text='-',font=('Microsoft YaHei UI',14))
        self.label_treatment.grid(column=1,row=1,sticky='w')
        #Content
        self.sctext_content = scrolledtext.ScrolledText(self.frame_content,width=50,height=20,state='disabled')
        self.sctext_content.grid(column=0,row=2)
        #Controller
        self.frame_controller = tk.Frame(self.window)
        self.frame_controller.grid(column=0,row=1)
        self.button_back = ttk.Button(self.frame_controller,text='上一页',command=lambda:self.turn_page(self.page-1))
        self.button_back.grid(column=0,row=0)
        self.label_page_shower = tk.Label(self.frame_controller,text='0/0')
        self.label_page_shower.grid(column=1,row=0)
        self.button_next = ttk.Button(self.frame_controller,text='下一页',command=lambda:self.turn_page(self.page+1))
        self.button_next.grid(column=2,row=0)
        self.button_more = ttk.Button(self.frame_controller,text='加载更多',command=self.load_data)
        self.button_more.grid(column=1,row=1)
        self.load_data()
        self.turn_page(self.page)

        self.window.mainloop()

    def load_data(self):
        self.loaded_page += 1
        self.data_pool += biliapis.get_blackroom(self.loaded_page)
        self.label_page_shower['text'] = '{}/{}'.format(self.page,len(self.data_pool))

    def load_img(self,page):
        if type(self.data_pool[page-1]['user']['face']) == str:#检查是否加载过, 加载过的则不再加载
            self.data_pool[page-1]['user']['face'] = BytesIO(biliapis.get_content_bytes(biliapis.format_img(self.data_pool[page-1]['user']['face'],50,50)))
        self.task_queue.put_nowait(lambda:self.set_image(self.label_target_face,self.data_pool[page-1]['user']['face'],size=(50,50)))
        
    def turn_page(self,page):
        if page > len(self.data_pool):
            page = len(self.data_pool)
        elif page < 1:
            page = 1
        self.page = page
        #pdata = self.data_pool[page-1]
        start_new_thread(self.load_img,(page,))
        self.label_target_face_text.grid_remove()
        self.label_target_name['text'] = self.data_pool[page-1]['user']['name']
        self.label_target_id['text'] = 'UID{}'.format(self.data_pool[page-1]['user']['uid'])
        self.label_behavior['text'] = self.data_pool[page-1]['punish']['title']
        if self.data_pool[page-1]['punish']['days'] == 0:
            self.label_treatment['text'] = '永久封禁'
        else:
            self.label_treatment['text'] = '封禁 {} 天'.format(self.data_pool[page-1]['punish']['days'])
        self.set_text(self.sctext_content,True,text=self.data_pool[page-1]['punish']['content'])
        self.label_page_shower['text'] = '{}/{}'.format(self.page,len(self.data_pool))

class SingleVideoDownloader(Window):
    def __init__(self,bvid,path=os.path.abspath('./'),quality='highest',pnumbers=[],mode='dash'):
        '''
        quality = 'highest' / 'lowest' / 'regular'
            如果传入 highest 则为最高画质;
            如果传入 lowest 则为最低画质;
            如果传入 regular 则从config中读取优先级列表
        pnumbers 为空列表时下载全部分P, 不为空时下载所指定的分P.
        '''
        self.video_data = biliapis.get_video_detail(bvid=bvid)
        self.topath = path
        self.pnumbers = pnumbers
        #self.mode = mode.lower()
        self.mode = 'dash'#其他模式没摸好
        self.quality = quality

        super().__init__('BiliTools - VideoDownloader',True,config['topmost'],config['alpha'])

        #BasicInfo
        self.frame_basic = tk.Frame(self.window)
        self.frame_basic.grid(column=0,row=0,sticky='w')
        tk.Label(self.frame_basic,text='目标:').grid(column=0,row=0,sticky='e')
        tk.Label(self.frame_basic,text=bvid).grid(column=1,row=0,sticky='w')
        tk.Label(self.frame_basic,text='标题:').grid(column=0,row=1,sticky='e')
        self.entry_title = ttk.Entry(self.frame_basic,width=60)
        self.entry_title.insert('end',self.video_data['title'])
        self.entry_title['state'] = 'disabled'
        self.entry_title.grid(column=1,row=1,sticky='w')
        tk.Label(self.frame_basic,text='画质:').grid(column=0,row=2,sticky='e')
        tk.Label(self.frame_basic,text=config['video_download'][mode]['quality'].upper()).grid(column=1,row=2,sticky='w')
        tk.Label(self.frame_basic,text='方式:').grid(column=0,row=3,sticky='e')
        tk.Label(self.frame_basic,text=config['video_download']['mode'].upper()).grid(column=1,row=3,sticky='w')
        if not check_ffmpeg() and self.mode == 'dash':
            msbox.showerror('','FFmpeg不可用.')
            self.close()
            return
        #Table
        self.table_data = []
        columns = {'number':'序号',
                   'title':'标题',
                   'cid':'Cid',
                   'quality':'画质',
                   'encoding':'编码',
                   'status:':'状态'}
        columns_widths = [40,180,80,60,100,70]
        self.frame_table = tk.Frame(self.window)
        self.frame_table.grid(column=0,row=1,sticky='w')
        self.scbar_y = tk.Scrollbar(self.frame_table,orient='vertical')
        self.scbar_x = tk.Scrollbar(self.frame_table,orient='horizontal')
        self.table = ttk.Treeview(self.frame_table,show="headings",columns=tuple(columns.keys()),yscrollcommand=self.scbar_y.set,xscrollcommand=self.scbar_x.set,height=10)
        self.table.grid(column=0,row=0)
        self.scbar_y['command'] = self.table.yview
        self.scbar_x['command'] = self.table.xview
        self.scbar_y.grid(column=1,row=0,sticky='wns')
        self.scbar_x.grid(column=0,row=1,sticky='nwe')
        i = 0
        for column in columns.keys():
            self.table.column(column,width=columns_widths[i],anchor='w')
            self.table.heading(column,text=columns[column],anchor='w')
            i += 1
        #Tip
        tk.Label(self.window,text='请耐心等待, 不要关闭本窗口/下载窗口/本窗口的父窗口.\n详细的下载进度可以在弹出的下载窗口中查看.',justify='left').grid(column=0,row=2,sticky='w')
        #Fill Data
        parts = self.video_data['parts']
        self.prepared_data = []
        if pnumbers:
            indexes = pnumbers
        else:
            indexes = range(0,len(parts))
        i = 0
        for index in indexes:
            i += 1
            p = parts[index]
            self.table_data.append([str(i),p['title'],p['cid'],'','','待处理'])
            self.table.insert("","end",values=tuple(self.table_data[-1]))
            self.prepared_data += [p]
        #Here we go
        self.auto_refresh_table()
        index = 0
        for pdata in self.prepared_data:
            if self.mode == 'dash':
                hdr = False
                _4k = False
                if config['video_download']['dash']['quality'] == 'highest':
                    hdr = True
                    _4k = True
                elif config['video_download']['dash']['quality'] == 'regular':
                    if bilicodes.stream_dash_video_quality_['HDR'] in config['video_download']['dash']['regular']:
                        hdr = True
                    if bilicodes.stream_dash_video_quality_['4K'] in config['video_download']['dash']['regular']:
                        _4k = True
                streams = biliapis.get_video_stream_dash(pdata['cid'],bvid=self.video_data['bvid'],hdr=hdr,_4k=_4k)
                #print('取流完毕')
                vstream = self.match_dash_quality(streams['video'])
                aqs = []
                for stream in streams['audio']:
                    aqs.append(stream['quality'])
                astream = streams['audio'][aqs.index(max(aqs))]
                #print('画质匹配完毕: '+bilicodes.stream_dash_video_quality[vstream['quality']])
                #更新数据
                #3画质 4编码 5状态
                self.table_data[index][3] = bilicodes.stream_dash_video_quality[vstream['quality']]
                self.table_data[index][4] = vstream['encoding']
                #生成文件名
                tmpname_audio = '{}_{}_audiostream.aac'.format(self.video_data['bvid'],
                                                       pdata['cid'])
                tmpname_video = '{}_{}_{}_videostream.mp4'.format(self.video_data['bvid'],
                                                       pdata['cid'],vstream['quality'])
                final_filename = replaceChr('{}_{}_P{}_{}_{}.mp4'.format(self.video_data['title'],self.video_data['bvid'],
                                                                         self.video_data['parts'].index(pdata)+1,pdata['title'],
                                                                         bilicodes.stream_dash_video_quality[vstream['quality']]))
                if os.path.exists(os.path.join(self.topath,final_filename)):
                    self.table_data[index][5] = '跳过'
                    continue
                #print('文件名生成完毕')
                #音频流
                self.table_data[index][5] = '下载音频流'
                aw = biliapis.DownloadWindow(astream['url'],self.topath,tmpname_audio,showwarning=False,iconic=True)
                astatus = aw.data['condition']
                aeinfo = aw.data['error_info']
                if astatus == 3:
                    logging.warning('AudioStream Downloading Task was Stopped by User.')
                elif astatus == 2:
                    logging.error('An Error Occurred while AudioStream Downloading Task Running: '+aeinfo)
                else:
                    astatus = 1
                #print('音频流下载完毕')
                #视频流
                self.table_data[index][5] = '下载视频流'
                vw = biliapis.DownloadWindow(vstream['url'],self.topath,tmpname_video,showwarning=False,iconic=True)
                vstatus = vw.data['condition']
                veinfo = vw.data['error_info']
                if vstatus == 3:
                    logging.warning('VideoStream Downloading Task was Stopped by User.')
                elif vstatus == 2:
                    logging.error('An Error Occurred while VideoStream Downloading Task Running: '+aeinfo)
                else:
                    vstatus = 1
                #print('视频流下载完毕')
                #混流
                if astatus == 1 and vstatus == 1:
                    self.table_data[index][5] = '混流'
                    mstatus = merge_media(os.path.join(self.topath,tmpname_audio),
                                          os.path.join(self.topath,tmpname_video),
                                          os.path.join(self.topath,final_filename))
                    if mstatus:
                        try:
                            os.remove(os.path.join(self.topath,tmpname_audio))
                            os.remove(os.path.join(self.topath,tmpname_video))
                        except:
                            pass
                else:
                    logging.warning('A/V Merging Canceled because of the Reason above.')
                #print('混流完毕')
                self.table_data[index][5] = '完成'
                
            index += 1
        msgbox.showinfo('','完成')
        self.close()

    def auto_refresh_table(self):#更新依据: self.table_data
        #先删掉所有旧项
        obj = self.table.get_children()
        for o in obj:
            self.table.delete(o)
        #再填充新的数据
        for line in self.table_data:
            self.table.insert("","end",values=tuple(line))

        self.window.after(100,self.auto_refresh_table)

    def match_dash_quality(self,streams):#传入的是videostreams
        quality = self.quality.lower()
        mode = self.mode.lower()
        qs = []
        for stream in streams:
            qs.append(stream['quality'])
        if quality == 'highest':
            return streams[qs.index(max(qs))]
        elif quality == 'lowest':
            return streams[qs.index(min(qs))]
        elif config['video_download'][mode]['regular']:
            res = None
            for q in config['video_download'][mode]['regular']:
                if q in qs:
                    res = q
                    break
            if res == None:
                return streams[qs.index(max(qs))]
            else:
                return streams[qs.index(res)]
        else:
            return streams[qs.index(max(qs))]

if (__name__ == '__main__' and not config['devmode']) or '-run_window' in sys.argv:
    logging.info('Program Running.')
    w = MainWindow()
