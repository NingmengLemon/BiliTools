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
import copy

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

version = '2.0.0_Dev06'
work_dir = os.getcwd()
user_name = os.getlogin()
config_path = f'C:\\Users\\{user_name}\\bilitools_config.json'
desktop_path = biliapis.get_desktop()

config = {
    'topmost':True,
    'alpha':1.0,# 0.0 - 1.0
    'filter_emoji':False,
    'devmode':True, #开发模式开关
    'download':{
        'video':{
            'quality_regular':[]
            },
        'max_thread_num':4
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
        '点我是可以刷新Tips哒ヾ(•ω•`)o',
        
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
    return not bool(os.popen('ffmpeg.exe -hide_banner -i "{}" -i "{}" -vcodec {} -acodec {} "{}"'.format(audio_file,video_file,vcodec,acodec,output_file)).close())

def convert_audio(inputfile,audio_format='mp3'):
    path,filename = os.path.split(file)
    outfile = os.path.join(path,os.path.splitext(filename)[0]+'.'+audio_format)
    return not bool(os.popen('ffmpeg.exe -hide_banner -i "{}" "{}"'.format(inputfile,outfile)).close())

class DownloadManager(object):
    def __init__(self):
        self.window = None
        self.task_queue = queue.Queue()
        self.table_columns = {
            'number':'序号',
            'title':'标题',
            'subtitle':'副标题',
            'target':'目标',
            'mode':'模式',
            'size':'大小',
            'quality':'质量',
            'length':'长度',
            'saveto':'保存至',
            'status':'状态'
            }
        self.table_columns_widths = [40,180,180,100,70,60,60,60,100,150]
        
        self.table_display_list = [] #多维列表注意, 对应Treview的内容, 每项格式见table_columns
        self.data_objs = [] #对应每个下载项的数据包, 每项格式:[序号(整型),类型(字符串,video/audio/common),选项(字典,包含从task_receiver传入的除源以外的**args)]
        self.thread_counter = 0 #线程计数器
        self.failed_indexes = [] #存放失败任务在data_objs中的索引
        self.running_indexes = [] #存放运行中的任务在data_objs中的索引
        self.done_indexes = [] #存放已完成任务在data_objs中的索引
        #以上对象的读写权限注意:
        #只有task_receiver有添加新项的权限
        #各个download_thread只有写入/读取权限
        #auto_refresh_table只有读取权限
        start_new_thread(self.auto_thread_starter)
        
    def auto_thread_starter(self):#放在子线程里运行
        while True:
            if self.thread_counter < config['download']['max_thread_num'] and not self.task_queue.empty():
                func = self.task_queue.get_nowait()
                start_new_thread(func) #线程计数器由开启的download_thread来修改
            time.sleep(0.5)

    def match_dash_quality(self,videostreams,audiostreams,regular=config['download']['video']['quality_regular']):
        videostream = None
        audiostream = None
        #Video
        vqs = []
        for vstream in videostreams:
            vqs.append(vstream['quality'])
        if regular:
            res = None
            for vq in regular:
                if vq in vqs:
                    res = vq
                    break
            if res == None:
                videostream = videostreams[vqs.index(min(vqs))]
            else:
                videostream = videostreams[vqs.index(res)]
        else:
            videostream = videostreams[vqs.index(max(vqs))]
        #Audio
        aqs = []
        for astream in audiostreams:
            aqs.append(astream['quality'])
        audiostream = audiostreams[aqs.index(max(aqs))]
        return videostream,audiostream

    def _edit_display_list(self,index,colname,var):#供download_thread调用
        self.table_display_list[index][list(self.table_columns.keys()).index(colname)] = var

    def _common_download_thread(self,index,url,filename,path,**trash):
        #跟下面辣两个函数差不多, 流程最简单
        self.thread_counter += 1
        self.running_indexes.append(index)
        try:
            self._edit_display_list(index,'status','准备下载')
            session = biliapis.download_yield(url,filename,path)
            for donesize,totalsize,percent in session:
                self._edit_display_list(index,'status','下载中 - {}%'.format(percent))
            self._edit_display_list(index,'size','{} MB'.format(round(totalsize/(1024**2),2)))
        except Exception as e:
            self.failed_indexes.append(index)
            self._edit_display_list(index,'status','出现问题')
            if config['devmode']:
                raise e
        else:
            self.done_indexes.append(index)
            self._edit_display_list(index,'status','完成')
        finally:
            del self.running_indexes[self.running_indexes.index(index)]
            self.thread_counter -= 1

    def _audio_download_thread(self,index,auid,path,audio_format='mp3',**trash):
        #跟下面辣个函数差不多, 流程稍微简单些
        #TODO: Format Converting
        self.thread_counter += 1
        self.running_indexes.append(index)
        try:
            #收集信息
            self._edit_display_list(index,'status','收集信息')
            audio_info = biliapis.get_audio_info(auid)
            self._edit_display_list(index,'length',biliapis.second_to_time(audio_info['length']))
            self._edit_display_list(index,'title',audio_info['title'])
            self._edit_display_list(index,'target','Auid{}'.format(auid))
            #取流
            self._edit_display_list(index,'status','正在取流')
            stream = biliapis.get_audio_stream(auid)
            self._edit_display_list(index,'quality',stream['quality'])
            self._edit_display_list(index,'size','{} MB'.format(round(stream['size']/(1024**2),2)))
            #下载
            tmp_filename = replaceChr('{}_{}.aac'.format(auid,stream['quality_id']))
            final_filename = replaceChr('{}_{}.aac'.format(audio_info['title'],stream['quality']))
            session = biliapis.download_yield(stream['url'],tmp_filename,path,)
            for donesize,totalsize,percent in session:
                self._edit_display_list(index,'status','下载中 - {}%'.format(percent))
            #进一步处理
            os.rename(os.path.join(path,tmp_filename),
                      os.path.join(path,final_filename))
        except biliapis.BiliError as e:
            self.failed_indexes.append(index)
            self._edit_display_list(index,'status',e.msg)
        except Exception as e:
            self.failed_indexes.append(index)
            self._edit_display_list(index,'status','出现问题')
            if config['devmode']:
                raise e
        else:
            self.done_indexes.append(index)
            self._edit_display_list(index,'status','完成')
        finally:
            del self.running_indexes[self.running_indexes.index(index)]
            self.thread_counter -= 1

    def _video_download_thread(self,index,cid,bvid,title,path,video_encoding='copy',audio_format='mp3',audiostream_only=False,quality_regular=[],**trash):#放在子线程里运行
        #此函数被包装为lambda函数后放入task_queue中排队, 由auto_thread_starter取出并开启线程
        #此处index为task_receiver为其分配的在tabled_display_list中的索引
        #TODO: Format Converting
        self.thread_counter += 1
        self.running_indexes.append(index)
        try:
            self._edit_display_list(index,'status','正在取流')
            stream_data = biliapis.get_video_stream_dash(cid,bvid=bvid,hdr=True,_4k=True)
            vstream,astream = self.match_dash_quality(stream_data['video'],stream_data['audio'],quality_regular)
            if audiostream_only:
                self._edit_display_list(index,'quality',bilicodes.stream_dash_audio_quality[astream['quality']])
                self._edit_display_list(index,'mode','音轨抽取')
            else:
                self._edit_display_list(index,'quality',bilicodes.stream_dash_video_quality[vstream['quality']])
                self._edit_display_list(index,'mode','视频下载')
            #生成文件名
            tmpname_audio = '{}_{}_audiostream.aac'.format(bvid,cid)
            tmpname_video = '{}_{}_{}_videostream.mp4'.format(bvid,cid,vstream['quality'])
            final_filename = replaceChr('{}_{}.mp4'.format(title,bilicodes.stream_dash_video_quality[vstream['quality']]))#标题由task_receiver生成
            final_filename_audio_only = replaceChr('{}_{}.aac'.format(title,bilicodes.stream_dash_audio_quality[astream['quality']]))
            #Audio Stream
            size = 0
            a_session = biliapis.download_yield(astream['url'],tmpname_audio,path)
            for donesize,totalsize,percent in a_session:
                self._edit_display_list(index,'status','下载音频流 - {}%'.format(percent))
            size += totalsize
            self._edit_display_list(index,'size','{} MB'.format(round(totalsize/(1024**2),2)))
            #Video Stream
            if audiostream_only:
                self._edit_display_list(index,'status','混流/转码')
                os.rename(os.path.join(path,tmpname_audio),os.path.join(path,final_filename_audio_only))
            else:
                v_session = biliapis.download_yield(vstream['url'],tmpname_video,path)
                for donesize,totalsize,percent in v_session:
                    self._edit_display_list(index,'status','下载视频流 - {}%'.format(percent))
                size += totalsize
                self._edit_display_list(index,'size','{} MB'.format(round(totalsize/(1024**2),2)))
                #Mix
                self._edit_display_list(index,'status','混流/转码')
                ffstatus = merge_media(os.path.join(path,tmpname_audio),
                            os.path.join(path,tmpname_video),
                            os.path.join(path,final_filename))
                try:
                    os.remove(os.path.join(path,tmpname_audio))
                    os.remove(os.path.join(path,tmpname_video))
                except:
                    pass
        except biliapis.BiliError as e:
            self.failed_indexes.append(index)
            self._edit_display_list(index,'status',e.msg)
        except Exception as e:
            self.failed_indexes.append(index)
            self._edit_display_list(index,'status',str(e))
            if config['devmode']:
                raise e
        else:
            self.done_indexes.append(index)
            self._edit_display_list(index,'status','完成')
        finally:
            del self.running_indexes[self.running_indexes.index(index)]
            self.thread_counter -= 1
            

    def task_receiver(self,mode,path,**options):
        '''mode: 下载模式, 必须从video/audio/common里选一个.
path: 输出位置
若mode为video, 则必须指定[avid/bvid,pids(分P索引列表)]或[mdid/ssid/epid],
-附加参数: audiostream_only,video_encoding,audio_format,quality_regular
若mode为audio, 则必须指定auid,
-附加参数: audio_format
若mode为common, 则必须指定url, 无附加参数.
'''#格式转换还在摸
        self.show()
        mode = mode.lower()
        if mode == 'video':
            #普通视频
            if 'avid' in options or 'bvid' in options:
                video_data = None
                #提取avid/bvid
                if 'avid' in options:
                    video_data = biliapis.get_video_detail(avid=options['avid'])
                else:
                    video_data = biliapis.get_video_detail(bvid=options['bvid'])
                #提取分P索引列表
                if 'pids' in options:
                    pids = options['pids']
                else:
                    pids = []
                if not pids:
                    pids = list(range(0,len(video_data['parts'])))
                #选项预处理
                pre_opts = {}
                for key in ['audiostream_only','video_encoding','audio_format','quality_regular']:#过滤download_thread不需要的, 防止出错
                    if key in options:
                        pre_opts[key] = options[key]
                pre_opts['bvid'] = video_data['bvid']
                pre_opts['path'] = path
                #分发任务
                for pid in pids:
                    if pid < len(video_data['parts']):
                        part = video_data['parts'][pid]
                        tmpdict = copy.deepcopy(pre_opts)
                        tmpdict['cid'] = part['cid']
                        tmpdict['title'] = '{}_P{}_{}'.format(video_data['title'],pid+1,part['title'])
                        tmpdict['index'] = len(self.data_objs)
                        self.data_objs.append([len(self.data_objs)+1,'video',tmpdict])
                        self.table_display_list.append([str(len(self.data_objs)),video_data['title'],part['title'],'Cid{}'.format(part['cid']),'','','',biliapis.second_to_time(part['length']),path,''])
                        self.task_queue.put_nowait(lambda args=tmpdict:self._video_download_thread(**args))
            elif 'ssid' in options or 'mdid' in options or 'epid' in options:
                pass
        elif mode == 'audio':
            tmpdict = {
                'index':len(self.data_objs),
                'auid':options['auid'],
                'path':path
                }
            if 'audio_format' in options:
                tmpdict['audio_format'] = options['audio_format']
            self.data_objs.append([len(self.data_objs)+1,'audio',tmpdict])
            self.table_display_list.append([str(len(self.data_objs)),'','','','音频下载','','','',path,''])
            self.task_queue.put_nowait(lambda args=tmpdict:self._audio_download_thread(**args))
        elif mode == 'common':
            tmpdict = {
                'index':len(self.data_objs),
                'url':options['url'],
                'filename':options['filename'],
                'path':path
                }
            self.data_objs.append([len(self.data_objs)+1,'common',tmpdict])
            self.table_display_list.append([str(len(self.data_objs)),options['filename'],'',options['url'],'普通下载','','','',path,''])
            self.task_queue.put_nowait(lambda args=tmpdict:self._common_download_thread(**args))
        
    def show(self):
        if not self.window:#构建GUI
            self.window = tk.Tk()
            self.window.title('BiliTools - Download Manager')
            self.window.resizable(height=False,width=False)
            self.window.protocol('WM_DELETE_WINDOW',self.hide)
            self.window.wm_attributes('-alpha',config['alpha'])
            self.window.wm_attributes('-topmost',config['topmost'])
            #任务列表
            self.frame_table = tk.Frame(self.window)
            self.frame_table.grid(column=0,row=0,sticky='w',columnspan=2)
            self.scbar_y = tk.Scrollbar(self.frame_table,orient='vertical')
            self.scbar_x = tk.Scrollbar(self.frame_table,orient='horizontal')
            self.table = ttk.Treeview(self.frame_table,show="headings",columns=tuple(self.table_columns.keys()),yscrollcommand=self.scbar_y.set,xscrollcommand=self.scbar_x.set,height=20)
            self.table.grid(column=0,row=0)
            self.scbar_y['command'] = self.table.yview
            self.scbar_x['command'] = self.table.xview
            self.scbar_y.grid(column=1,row=0,sticky='wns')
            self.scbar_x.grid(column=0,row=1,sticky='nwe')
            #初始化表头
            i = 0
            for column in self.table_columns.keys():
                self.table.column(column,width=self.table_columns_widths[i],anchor='w')
                self.table.heading(column,text=self.table_columns[column],anchor='w')
                i += 1
            #数据统计
            self.frame_stat = tk.Frame(self.window)
            self.frame_stat.grid(column=0,row=1,sticky='nw')
            tk.Label(self.frame_stat,text='总任务数:')  .grid(column=0,row=0,sticky='e')
            tk.Label(self.frame_stat,text='已完成:')    .grid(column=0,row=1,sticky='e')
            tk.Label(self.frame_stat,text='运行中:')    .grid(column=0,row=2,sticky='e')
            tk.Label(self.frame_stat,text='失败:')      .grid(column=0,row=3,sticky='e')
            tk.Label(self.frame_stat,text='当前线程数:').grid(column=0,row=4,sticky='e')
            self.label_stat_totaltask = tk.Label(self.frame_stat,text='0')
            self.label_stat_totaltask.grid(column=1,row=0,sticky='w')
            self.label_stat_donetask = tk.Label(self.frame_stat,text='0')
            self.label_stat_donetask.grid(column=1,row=1,sticky='w')
            self.label_stat_runningtask = tk.Label(self.frame_stat,text='0')
            self.label_stat_runningtask.grid(column=1,row=2,sticky='w')
            self.label_stat_failedtask = tk.Label(self.frame_stat,text='0')
            self.label_stat_failedtask.grid(column=1,row=3,sticky='w')
            self.label_stat_threadnum = tk.Label(self.frame_stat,text='0')
            self.label_stat_threadnum.grid(column=1,row=4,sticky='w')
            #操作面板
            #等会儿再搞
        
            self.auto_refresh_table()
            
    def auto_refresh_table(self):#更新依据: self.table_display_list
        if self.window:
            #删掉旧内容
            obj = self.table.get_children()
            for o in obj:
                self.table.delete(o)
            #填充新内容
            i = 0
            for line in self.table_display_list:
                i += 1
                self.table.insert('','end',values=tuple(line))
            #更新统计信息
            self.label_stat_totaltask['text'] = str(len(self.data_objs))
            self.label_stat_donetask['text'] = str(len(self.done_indexes))
            self.label_stat_failedtask['text'] = str(len(self.failed_indexes))
            self.label_stat_runningtask['text'] = str(len(self.running_indexes))
            self.label_stat_threadnum['text'] = str(self.thread_counter)
            #准备下一次循环
            self.window.after(100,self.auto_refresh_table)
        else:
            pass

    def hide(self):
        if self.window:
            self.window.destroy()
            self.window = None

download_manager = DownloadManager()

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
        ttk.Button(self.frame_basicfuncs,text='下载姬',width=11,command=download_manager.show).grid(column=0,row=3)
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
                pass
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

        #Download
        self.frame_download = tk.LabelFrame(self.window,text='下载设置')
        self.frame_download.grid(column=1,row=0,sticky='nw')
        #Video Quality
        #######
        
        # Save or Cancel
        self.frame_soc = tk.Frame(self.window)
        self.frame_soc.grid(column=1,row=1,sticky='se')
        ttk.Button(self.frame_soc,text='取消',width=5,command=self.close).grid(column=0,row=0)
        ttk.Button(self.frame_soc,text='保存',width=5,command=self.save_config).grid(column=1,row=0)

        self.window.mainloop()

    def apply_config(self):#
        global config
        config['topmost'] = self.boolvar_topmost.get()
        config['alpha'] = round(self.doublevar_winalpha.get(),2)
        config['filter_emoji'] = self.boolvar_filteremoji.get()
        biliapis.filter_emoji = config['filter_emoji']

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
        self.button_download_cover['state'] = 'disabled'
        path = filedialog.askdirectory(title='保存至')
        if path:
            download_manager.task_receiver('audio',path,auid=self.auid)
        if self.is_alive:
            self.button_download_cover['state'] = 'normal'

    def download_cover(self):
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
        download_manager.task_receiver('video',path,pids=indexes,audiostream_only=True)
        if self.is_alive:
            self.button_download_audio['state'] = 'normal'

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
        download_manager.task_receiver('video',path,pids=indexes)
        if self.is_alive:
            self.button_download_audio['state'] = 'normal'

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



if (__name__ == '__main__' and not config['devmode']) or '-run_window' in sys.argv:
    logging.info('Program Running.')
    #w = MainWindow()
    download_manager.task_receiver('video','D:/',avid=99999999,pids=[3],audiostream_only=True,audio_convert='mp3')
