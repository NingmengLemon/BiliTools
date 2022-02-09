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
import danmaku2ass

import biliapis
from biliapis import bilicodes
import custom_widgets as cusw
from basic_window import Window
import imglib
import ffmpeg_driver as ffdriver

#注意：
#为了页面美观，将 Button/Radiobutton/Checkbutton/Entry 的母模块从tk换成ttk
#↑步入现代风（并不

version = '2.0.0_Dev09'
work_dir = os.getcwd()
user_name = os.getlogin()
inner_data_path = 'C:\\Users\\{}\\BiliTools\\'.format(user_name)
if not os.path.exists(inner_data_path):
    os.mkdir(inner_data_path)
biliapis.requester.inner_data_path = inner_data_path
config_path = os.path.join(inner_data_path,'config.json')
desktop_path = biliapis.get_desktop()
biliapis.requester.load_local_cookies()
development_mode = True

config = {
    'version':version,
    'topmost':False,
    'alpha':1.0,# 0.0 - 1.0
    'filter_emoji':False,
    'download':{
        'video':{
            'quality_regular':[],
            'audio_convert':'mp3',
            'subtitle':True,
            'subtitle_lang_regular':['zh-CN','zh-Hans','zh-Hant','zh-HK','zh-TW','en-US','en-GB','ja','ja-JP'],
            'danmaku':False,
            'convert_danmaku':True,
            'danmaku_filter':{
                'keyword':[],
                'regex':[],
                'user':[], #用户uid的hash, crc32
                'filter_level':0 #0-10
                }
            },
        'audio':{
            'convert':'mp3',
            'lyrics':True
            },
        'manga':{
            'save_while_viewing':False,
            'auto_save_path':os.path.join(inner_data_path,'MangaAutoSave')
            },
        'max_thread_num':2,
        'progress_backup_path':os.path.join(inner_data_path,'progress_backup.json')
        },
    }
biliapis.filter_emoji = config['filter_emoji']
#日志模块设置
logging.basicConfig(format='[%(asctime)s][%(levelname)s]%(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level={True:logging.DEBUG,False:logging.INFO}[development_mode or '-debug' in sys.argv]
                    )

tips = [
        '欢迎使用基于Bug开发的BiliTools（',
        'Bug是此程序的核心部分',
        '你知道吗，其实此程序的作者是只鸽子（认真脸',
        '有一个程序员前来修Bug',
        '我好不容易写好一次，你却崩溃得这么彻底',
        '（`Oω|',
        '点我是可以刷新Tips哒ヾ(•ω•`)o',
        '啊哈哈哈哈，我滴程序完成辣！',
        '『世界』——！',
        'Damedane~dameyo~',
        '《程序员的取悦手段》',
        '不写注释一时爽，维护程序火葬场',
        '“你的生命不是为了飘散而绽放的。”',
        '“来吧，乘风破浪，将世俗的眼光统统超越。”',
        '“你没有活着真是太好了。”',
        ]

about_info = '\n'.join([
    'BiliTools v.%s'%version,
    '一些功能需要 FFmpeg 的支持.',
    'Made by: @NingmengLemon（GitHub）',
    '引用开源程序: danmaku2ass',

    '---------------------------',
    '此程序严禁用于任何商业用途.',
    '此程序的作者不会为任何因使用此程序所造成的后果负责.',
    '感谢您的使用.'
    ])

def dump_config(fp=config_path):
    json.dump(config,open(fp,'w+',encoding='utf-8',errors='ignore'))
    logging.debug('Config File Dumped to {}'.format(config_path))

def load_config(fp=config_path):
    global config
    if os.path.exists(fp):# and not development_mode:
        tmp = json.load(open(fp,'r',encoding='utf-8',errors='ignore'))
        if 'version' in tmp:
            if tmp['version'] == version:
                config = tmp
                logging.debug('Config File Loaded from {}'.format(config_path))
            else:
                dump_config(fp)
        else:
            dump_config(fp)
        
    else:
        dump_config(fp)

def danmaku_to_ass(xmlfilename,outputfile,w=1920,h=1080,reduce_when_full=True):
    try:
        danmaku2ass.Danmaku2ASS(xmlfilename,'autodetect',outputfile,w,h,is_reduce_comments=reduce_when_full,
                                font_face='黑体',font_size=40.0,duration_marquee=5.0,duration_still=10.0,)
    except Exception as e:
        logging.error('Error while converting danmaku: '+str(e))
    else:
        logging.info('Danmaku file {} converted to {}'.format(xmlfilename,outputfile))

def start_new_thread(func,args=(),kwargs=None,name=None,daemon=True):
    threading.Thread(target=func,args=args,kwargs=kwargs,name=name,daemon=daemon).start()

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

def make_quality_regular(qtext):
    targetlist = list(bilicodes.stream_dash_video_quality.keys())
    index = list(bilicodes.stream_dash_video_quality.values()).index(qtext)
    return list(reversed(targetlist[:index+1]))

class DownloadManager(object):
    def __init__(self):
        self.window = None
        self.task_queue = queue.Queue()
        self.refresh_loop_schedule = None
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
        self.table_columns_widths = [40,200,180,100,70,80,60,60,100,150]
        
        self.table_display_list = [] #多维列表注意, 对应Treview的内容, 每项格式见table_columns
        self.data_objs = [] #对应每个下载项的数据包, 每项格式:[序号(整型),类型(字符串,video/audio/common),选项(字典,包含从task_receiver传入的除源以外的**args)]
        self.thread_counter = 0 #线程计数器
        self.failed_indexes = [] #存放失败任务在data_objs中的索引
        self.running_indexes = [] #存放运行中的任务在data_objs中的索引
        self.done_indexes = [] #存放已完成任务在data_objs中的索引
        start_new_thread(self.auto_thread_starter) #启动线程启动器
        if os.path.exists(config['download']['progress_backup_path']) and (not development_mode or '-debug' in sys.argv):
            if os.path.getsize(config['download']['progress_backup_path']) >= 50:
                self.show()
                if msgbox.askyesno('PrgRecovery','恢复下载进度？',parent=self.window):
                    self.load_progress(config['download']['progress_backup_path'])
                self.hide()

    def load_progress(self,file=config['download']['progress_backup_path']):
        if os.path.exists(file):
            pgr = json.load(open(file,'r',encoding='utf-8',errors='ignore'))
            for reindex in range(0,len(pgr['objs'])):
                obj = pgr['objs'][reindex]
                dlist = pgr['displaylist'][reindex]
                obj[2] = copy.deepcopy(obj[2])
                obj[2]['index'] = len(self.data_objs)
                obj[0] = len(self.data_objs)+1
                dlist[0] = str(len(self.data_objs)+1)
                dlist[-1] = '待处理'
                self.data_objs.append(obj)
                self.table_display_list.append(dlist)
                if obj[1] == 'video':
                    self.task_queue.put_nowait(lambda args=obj[2]:self._video_download_thread(**args))
                elif obj[1] == 'audio':
                    self.task_queue.put_nowait(lambda args=obj[2]:self._audio_download_thread(**args))
                elif obj[1] == 'common':
                    self.task_queue.put_nowait(lambda args=obj[2]:self._common_download_thread(**args))
                elif obj[1] == 'manga':
                    self.task_queue.put_nowait(lambda args=obj[2]:self._manga_download_thread(**args))
            logging.debug('{} Progress Obj Loaded from {}'.format(len(pgr['objs']),file))
        else:
            logging.debug('Progress File not Exists.')
                

    def save_progress(self,path=config['download']['progress_backup_path']):
        pgr = {
            'objs':[],
            'displaylist':[]
            }
        for index in range(0,len(self.data_objs)):
            if index in self.failed_indexes:
                pgr['objs'] += [self.data_objs[index]]
                pgr['displaylist'] += [self.table_display_list[index]]
            elif index in self.running_indexes:
                pgr['objs'] += [self.data_objs[index]]
                pgr['displaylist'] += [self.table_display_list[index]]
            elif index in self.done_indexes:
                continue
            else:
                pgr['objs'] += [self.data_objs[index]]
                pgr['displaylist'] += [self.table_display_list[index]]
        json.dump(pgr,open(path,'w+',encoding='utf-8',errors='ignore'))
        logging.debug('{} Progress Objs Saved to {}'.format(len(pgr['objs']),path))
        
    def auto_thread_starter(self):#放在子线程里运行
        while True:
            if self.thread_counter < config['download']['max_thread_num'] and not self.task_queue.empty():
                func = self.task_queue.get_nowait()
                start_new_thread(func) #线程计数器由开启的download_thread来修改
                time.sleep(0.5)
                self.save_progress()
            else:
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

    def choose_subtitle_lang(self,bccdata,regular=config['download']['video']['subtitle_lang_regular']):
        if bccdata:
            if len(bccdata) == 1:
                return bccdata[0]
            else:
                abbs = [sub['lang_abb'] for sub in bccdata]
                for reg in regular:
                    if reg in abbs:
                        return bccdata[abbs.index(reg)]
                return bccdata[0]
        else:
            return None

    def _edit_display_list(self,index,colname,var):#供download_thread调用
        self.table_display_list[index][list(self.table_columns.keys()).index(colname)] = var

    def _common_download_thread(self,index,url,filename,path,**trash):
        #跟下面辣两个函数差不多, 流程最简单
        self.thread_counter += 1
        self.running_indexes.append(index)
        try:
            self._edit_display_list(index,'status','准备下载')
            session = biliapis.requester.download_yield(url,filename,path)
            for donesize,totalsize,percent in session:
                self._edit_display_list(index,'status','下载中 - {}%'.format(percent))
            self._edit_display_list(index,'size','{} MB'.format(round(totalsize/(1024**2),2)))
        except Exception as e:
            self.failed_indexes.append(index)
            self._edit_display_list(index,'status','错误: '+str(e))
            if development_mode:
                raise e
        else:
            self.done_indexes.append(index)
            self._edit_display_list(index,'status','完成')
        finally:
            del self.running_indexes[self.running_indexes.index(index)]
            self.thread_counter -= 1
            self.save_progress()

    def _manga_download_thread(self,index,epid,path,**trash):
        #懒得解释了
        self.thread_counter += 1
        self.running_indexes.append(index)
        try:
            #收集信息
            self._edit_display_list(index,'status','收集信息')
            episode_info = biliapis.manga.get_episode_info(epid)
            comic_title = replaceChr(episode_info['comic_title'])
            ep_title = replaceChr(episode_info['eptitle'])
            ep_title_short = replaceChr(episode_info['eptitle_short'])
            mcid = episode_info['mcid']
            path = os.path.join(path,'_'.join([comic_title,ep_title_short,ep_title]).strip())
            #获取url和token
            self._edit_display_list(index,'status','获取Token')
            urls = ['{}@{}w.jpg'.format(i['path'],i['width']) for i in biliapis.manga.get_episode_image_index(epid)['images']]
            urls = [i['url']+'?token='+i['token'] for i in biliapis.manga.get_episode_image_token(*urls)]
            self._edit_display_list(index,'length',f'{len(urls)}张')
            maxb = len(str(len(urls)))
            #开始下载
            if not os.path.exists(path):
                os.mkdir(path)
            counter = 0
            self._edit_display_list(index,'status',f'下载中 0/{len(urls)}')
            for url in urls:
                counter += 1
                filename = '%d_%d_%0*d.jpg'%(mcid,epid,maxb,counter)
                if not os.path.exists(os.path.join(path,filename)):
                    biliapis.requester.download_common(url,os.path.join(path,filename))
                self._edit_display_list(index,'status',f'下载中 {counter}/{len(urls)}')
            self._edit_display_list(index,'status','检查中')
            size = 0
            for i in os.listdir(path):
                size += os.path.getsize(os.path.join(path,i))
            self._edit_display_list(index,'size',biliapis.requester.convert_size(size))
            self._edit_display_list(index,'status','完成')
        except biliapis.BiliError as e:
            self.failed_indexes.append(index)
            self._edit_display_list(index,'status','错误: '+e.msg)
        except Exception as e:
            self.failed_indexes.append(index)
            self._edit_display_list(index,'status','错误: '+str(e))
            if development_mode:
                raise e
        else:
            self.done_indexes.append(index)
        finally:
            del self.running_indexes[self.running_indexes.index(index)]
            self.thread_counter -= 1
            self.save_progress()

    def _audio_download_thread(self,index,auid,path,audio_format='mp3',lyrics=True,**trash):
        #跟下面辣个函数差不多, 流程稍微简单些
        self.thread_counter += 1
        self.running_indexes.append(index)
        try:
            #收集信息
            self._edit_display_list(index,'status','收集信息')
            audio_info = biliapis.audio.get_info(auid)
            self._edit_display_list(index,'length',biliapis.second_to_time(audio_info['length']))
            self._edit_display_list(index,'title',audio_info['title'])
            self._edit_display_list(index,'target','Auid{}'.format(auid))
            #取流
            self._edit_display_list(index,'status','正在取流')
            stream = biliapis.audio.get_stream(auid)
            self._edit_display_list(index,'quality',stream['quality'])
            self._edit_display_list(index,'size','{} MB'.format(round(stream['size']/(1024**2),2)))
            #下载
            tmp_filename = replaceChr('{}_{}.aac'.format(auid,stream['quality_id']))
            final_filename = replaceChr('{}_{}'.format(audio_info['title'],stream['quality']))#文件名格式编辑在这里, 不带后缀名
            lyrics_filename = replaceChr('{}_{}.lrc'.format(audio_info['title'],stream['quality']))
            if os.path.exists(os.path.join(path,final_filename+'.'+audio_format)):
                self._edit_display_list(index,'status','跳过 - 文件已存在: '+final_filename)
            else:
                session = biliapis.requester.download_yield(stream['url'],tmp_filename,path)
                for donesize,totalsize,percent in session:
                    self._edit_display_list(index,'status','下载中 - {}%'.format(percent))
                #进一步处理
                if audio_format and audio_format not in ['aac','copy']:
                    self._edit_display_list(index,'status','转码')
                    ffdriver.convert_audio(os.path.join(path,tmp_filename),os.path.join(path,final_filename),audio_format)
                    try:
                        os.remove(os.path.join(path,tmp_filename))
                    except:
                        pass
                else:
                    os.rename(os.path.join(path,tmp_filename),os.path.join(path,final_filename)+'.aac')
            if not os.path.exists(os.path.join(path,lyrics_filename)) and lyrics:
                self._edit_display_list(index,'status','获取歌词')
                lrcdata = biliapis.audio.get_lyrics(auid)
                if lrcdata == 'Fatal: API error':
                    pass
                else:
                    with open(os.path.join(path,lyrics_filename),'w+',encoding='utf-8',errors='ignore') as f:
                        f.write(lrcdata)
            self._edit_display_list(index,'status','完成')
        except biliapis.BiliError as e:
            self.failed_indexes.append(index)
            self._edit_display_list(index,'status','错误: '+e.msg)
        except Exception as e:
            self.failed_indexes.append(index)
            self._edit_display_list(index,'status','错误: '+str(e))
            if development_mode:
                raise e
        else:
            self.done_indexes.append(index)
        finally:
            del self.running_indexes[self.running_indexes.index(index)]
            self.thread_counter -= 1
            self.save_progress()

    def _video_download_thread(self,index,cid,bvid,title,path,audio_format='mp3',audiostream_only=False,quality_regular=[],subtitle=True,danmaku=False,
                               convert_danmaku=True,subtitle_regular=config['download']['video']['subtitle_lang_regular'],**trash):#放在子线程里运行
        #此函数被包装为lambda函数后放入task_queue中排队, 由auto_thread_starter取出并开启线程
        #此处index为task_receiver为其分配的在tabled_display_list中的索引
        self.thread_counter += 1
        self.running_indexes.append(index)
        try:
            self._edit_display_list(index,'status','正在取流')
            stream_data = biliapis.video.get_stream_dash(cid,bvid=bvid,hdr=True,_4k=True)
            vstream,astream = self.match_dash_quality(stream_data['video'],stream_data['audio'],quality_regular)
            if audiostream_only:
                self._edit_display_list(index,'quality',bilicodes.stream_dash_audio_quality[astream['quality']])
                self._edit_display_list(index,'mode','音轨抽取')
            else:
                self._edit_display_list(index,'quality',bilicodes.stream_dash_video_quality[vstream['quality']])
                self._edit_display_list(index,'mode','视频下载')
            #生成文件名
            tmpname_audio = '{}_{}_audiostream.aac'.format(bvid,cid)
            tmpname_video = '{}_{}_{}_videostream.avc'.format(bvid,cid,vstream['quality'])
            final_filename = replaceChr('{}_{}.mp4'.format(title,bilicodes.stream_dash_video_quality[vstream['quality']]))#标题由task_receiver生成
            final_filename_audio_only = replaceChr('{}_{}'.format(title,bilicodes.stream_dash_audio_quality[astream['quality']]))#音频抽取不带后缀名
            #字幕
            is_sbt_downloaded = False
            subtitle_filename = replaceChr('{}_{}.srt'.format(title,bilicodes.stream_dash_video_quality[vstream['quality']]))#字幕文件名与视频文件保持一致
            if subtitle and not audiostream_only:
                self._edit_display_list(index,'status','获取字幕')
                bccdata = self.choose_subtitle_lang(biliapis.subtitle.get_bcc(cid,bvid=bvid),subtitle_regular)
                if bccdata:
                    bccdata = json.loads(biliapis.requester.get_content_str(bccdata['url']))
                    srtdata = biliapis.subtitle.bcc_to_srt(bccdata)
                    with open(os.path.join(path,subtitle_filename),'w+',encoding='utf-8',errors='ignore') as f:
                        f.write(srtdata)
                    is_sbt_downloaded = True
            #弹幕
            danmaku_filename = replaceChr('{}_{}.xml'.format(title,bilicodes.stream_dash_video_quality[vstream['quality']]))#弹幕文件名与视频文件保持一致
            if danmaku and not audiostream_only:
                self._edit_display_list(index,'status','获取弹幕')
                xmlstr = biliapis.video.get_danmaku_xmlstr(cid)
                self._edit_display_list(index,'status','过滤弹幕')
                xmlstr = biliapis.video.filter_danmaku(xmlstr,**config['download']['video']['danmaku_filter'])
                with open(os.path.join(path,danmaku_filename),'w+',encoding='utf-8',errors='ignore') as f:
                    f.write(xmlstr)
                if convert_danmaku and os.path.exists(os.path.join(path,danmaku_filename)):
                    ass_danmaku_filename = replaceChr('{}_{}.ass'.format(title,bilicodes.stream_dash_video_quality[vstream['quality']]))
                    if os.path.exists(ass_danmaku_filename) and is_sbt_downloaded:
                        ass_danmaku_filename = replaceChr('{}_{}_danmaku.ass'.format(title,bilicodes.stream_dash_video_quality[vstream['quality']])) #弹幕与字幕同时存在时优先保留字幕
                    danmaku_to_ass(os.path.join(path,danmaku_filename),os.path.join(path,ass_danmaku_filename),w=vstream['width'],h=vstream['height'])
            #注意这里判断的是成品文件是否存在
            #断点续传和中间文件存在判断是交给requester的
            if os.path.exists(os.path.join(path,final_filename)) and not audiostream_only:
                self._edit_display_list(index,'status','跳过 - 文件已存在: '+final_filename)
            elif os.path.exists(os.path.join(path,final_filename_audio_only)+'.'+audio_format) and audiostream_only:
                self._edit_display_list(index,'status','跳过 - 文件已存在: '+final_filename_audio_only+'.'+audio_format)
            else:
                #Audio Stream
                a_session = biliapis.requester.download_yield(astream['url'],tmpname_audio,path)
                for donesize,totalsize,percent in a_session:
                    self._edit_display_list(index,'status','下载音频流 - {}%'.format(percent))
                size = totalsize
                #Video Stream
                if audiostream_only:
                    self._edit_display_list(index,'size','{} MB'.format(round(size/(1024**2),2)))
                    if audio_format and audio_format not in ['aac','copy']:
                        self._edit_display_list(index,'status','混流/转码')
                        ffdriver.convert_audio(os.path.join(path,tmpname_audio),
                                      os.path.join(path,final_filename_audio_only),audio_format)
                        try:
                            os.remove(os.path.join(path,tmpname_audio))
                        except:
                            pass
                    else:
                        os.rename(os.path.join(path,tmpname_audio),os.path.join(path,final_filename_audio_only)+'.aac')
                else:
                    v_session = biliapis.requester.download_yield(vstream['url'],tmpname_video,path)
                    for donesize,totalsize,percent in v_session:
                        self._edit_display_list(index,'status','下载视频流 - {}%'.format(percent))
                    size += totalsize
                    self._edit_display_list(index,'size','{} MB'.format(round(size/(1024**2),2)))
                    #Mix
                    self._edit_display_list(index,'status','混流/转码')
                    ffstatus = ffdriver.merge_media(os.path.join(path,tmpname_audio),
                                           os.path.join(path,tmpname_video),
                                           os.path.join(path,final_filename))
                    try:
                        os.remove(os.path.join(path,tmpname_audio))
                        os.remove(os.path.join(path,tmpname_video))
                    except:
                        pass
                self._edit_display_list(index,'status','完成')
        except biliapis.BiliError as e:
            self.failed_indexes.append(index)
            self._edit_display_list(index,'status','错误: '+e.msg)
        except Exception as e:
            self.failed_indexes.append(index)
            self._edit_display_list(index,'status','错误: '+str(e))
            if development_mode:
                raise e
        else:
            self.done_indexes.append(index)
        finally:
            del self.running_indexes[self.running_indexes.index(index)]
            self.thread_counter -= 1
            self.save_progress()

    def task_receiver(self,mode,path,data=None,**options):
        '''mode: 下载模式, 必须从video/audio/common里选一个.
path: 输出位置
若mode为video, 则必须指定[avid/bvid]或[mdid/ssid/epid],
-附加参数: audiostream_only,audio_format,quality_regular(如不指定后两者则从config中读取),subtitle,danmaku,subtitle_regular
-avid/bvid专用附加参数:pids(分P索引列表,可为空)
-mdid/ssid/epid专用附加参数:epindexes(EP索引列表.可为空),section_index(番外剧集索引)
-可选参数: data, 传入预请求的数据包(dict), 避免再次请求
--section_index不指定时, epindexes指正片内的索引; 超出索引范围操作无效
若mode为audio, 则必须指定auid,
-附加参数: audio_format(如不指定则从config中读取)
若mode为common, 则必须指定url和filename, 无附加参数.
若mode为manga, 则必须指定[epid/mcid]; epindexes参数可选, 但在指定epid时无效
'''
        self.show()
        mode = mode.lower()
        if mode == 'video':
            #普通视频
            if 'avid' in options or 'bvid' in options:
                video_data = None
                try:
                    if data:
                        #提取预处理数据包
                        if 'avid' in options:
                            assert options['avid']==data['avid'],'预请求数据包内容不匹配'
                        else:
                            assert options['bvid']==data['bvid'],'预请求数据包内容不匹配'
                        video_data = data
                    else:
                        #提取avid/bvid
                        if 'avid' in options:
                            video_data = biliapis.video.get_detail(avid=options['avid'])
                        else:
                            video_data = biliapis.video.get_detail(bvid=options['bvid'])
                except Exception as e:
                    msgbox.showerror('',str(e),parent=self.window)
                    return
                #提取分P索引列表
                if 'pids' in options: #这里的所谓pid其实是分P的索引值哒
                    pids = options['pids']
                else:
                    pids = []
                if not pids:
                    pids = list(range(0,len(video_data['parts'])))
                #选项预处理
                pre_opts = {}
                pre_opts['audio_format'] = config['download']['video']['audio_convert']
                pre_opts['quality_regular'] = config['download']['video']['quality_regular']
                pre_opts['subtitle'] = config['download']['video']['subtitle']
                pre_opts['danmaku'] = config['download']['video']['danmaku']
                pre_opts['subtitle_regular'] = config['download']['video']['subtitle_lang_regular']
                pre_opts['convert_danmaku'] = config['download']['video']['convert_danmaku']
                for key in ['audiostream_only','quality_regular','subtitle','danmaku','subtitle_regular','convert_danmaku']:#过滤download_thread不需要的, 防止出错
                    if key in options:
                        pre_opts[key] = options[key]
                pre_opts['bvid'] = video_data['bvid']
                pre_opts['path'] = path
                #分发任务
                for pid in pids:
                    if pid < len(video_data['parts']) and pid >= 0:
                        part = video_data['parts'][pid]
                        tmpdict = copy.deepcopy(pre_opts)
                        tmpdict['cid'] = part['cid']
                        tmpdict['title'] = '{}_P{}_{}'.format(video_data['title'],pid+1,part['title'])#文件名格式编辑在这里
                        tmpdict['index'] = len(self.data_objs)
                        self.data_objs.append([len(self.data_objs)+1,'video',tmpdict])
                        self.table_display_list.append([str(len(self.data_objs)),video_data['title'],'P{} {}'.format(pid+1,part['title']),'Cid{}'.format(part['cid']),'','','',biliapis.second_to_time(part['length']),path,'待处理'])
                        self.task_queue.put_nowait(lambda args=tmpdict:self._video_download_thread(**args))
            elif 'ssid' in options or 'mdid' in options or 'epid' in options:
                try:
                    if data:
                        if 'mdid' in options:
                            assert options['mdid']==data['mdid'],'预请求数据包内容不匹配'
                            bangumi_data = data
                        elif 'ssid' in options:
                            assert options['ssid']==data['ssid'],'预请求数据包内容不匹配'
                            bangumi_data = data
                        else:
                            bangumi_data = biliapis.media.get_detail(epid=options['epid'])
                    else:
                        if 'mdid' in options:
                            bangumi_data = biliapis.media.get_detail(mdid=options['mdid'])
                        elif 'ssid' in options:
                            bangumi_data = biliapis.media.get_detail(ssid=options['ssid'])
                        else:
                            bangumi_data = biliapis.media.get_detail(epid=options['epid'])
                except Exception as e:
                    msgbox.showerror('',str(e),parent=self.window)
                    return
                main_title = bangumi_data['title']
                #选择正片/番外
                if 'section_index' in options:
                    if options['section_index'] > len(bangumi_data['sections'])-1 or options['section_index'] < 0:
                        return
                    else:
                        section = bangumi_data['sections'][options['section_index']]
                        sstitle = section['title']
                        episodes = section['episodes']
                else:
                    episodes = bangumi_data['episodes']
                    sstitle = '正片'
                #提取EP
                if 'epindexes' in options:
                    epindexes = options['epindexes']
                else:
                    epindexes = []
                if not epindexes:
                    epindexes = list(range(0,len(episodes)))
                #提取参数
                pre_opts = {}
                pre_opts['audio_format'] = config['download']['video']['audio_convert']
                pre_opts['quality_regular'] = config['download']['video']['quality_regular']
                pre_opts['subtitle'] = config['download']['video']['subtitle']
                pre_opts['danmaku'] = config['download']['video']['danmaku']
                pre_opts['subtitle_regular'] = config['download']['video']['subtitle_lang_regular']
                pre_opts['convert_danmaku'] = config['download']['video']['convert_danmaku']
                for key in ['audiostream_only','audio_format','quality_regular','subtitle','danmaku','subtitle_regular','convert_danmaku']:#过滤download_thread不需要的, 防止出错
                    if key in options:
                        pre_opts[key] = options[key]
                pre_opts['path'] = path
                #分发任务
                for epindex in epindexes:
                    if epindex < len(episodes) and epindex >= 0:
                        episode = episodes[epindex]
                        tmpdict = copy.deepcopy(pre_opts)
                        tmpdict['title'] = '{}_{}_{}.{}'.format(main_title,sstitle,epindex+1,episode['title'])#文件名格式编辑在这里
                        tmpdict['cid'] = episode['cid']
                        tmpdict['bvid'] = episode['bvid']
                        tmpdict['index'] = len(self.data_objs)
                        self.data_objs.append([len(self.data_objs)+1,'video',tmpdict])
                        self.table_display_list.append([str(len(self.data_objs)),main_title,'{} {}.{}'.format(sstitle,epindex+1,episode['title']),'Cid{}'.format(episode['cid']),'','','','-',path,'待处理'])
                        self.task_queue.put_nowait(lambda args=tmpdict:self._video_download_thread(**args))
        elif mode == 'audio':
            tmpdict = {
                'index':len(self.data_objs),
                'auid':options['auid'],
                'path':path,
                'audio_format':config['download']['audio']['convert'],
                'lyrics':config['download']['audio']['lyrics']
                }
            if 'audio_format' in options:
                tmpdict['audio_format'] = options['audio_format']
            tmpdict = tmpdict.copy()
            self.data_objs.append([len(self.data_objs)+1,'audio',tmpdict])
            self.table_display_list.append([str(len(self.data_objs)),'','','','音频下载','','','',path,'待处理'])
            self.task_queue.put_nowait(lambda args=tmpdict:self._audio_download_thread(**args))
        elif mode == 'common':
            tmpdict = {
                'index':len(self.data_objs),
                'url':options['url'],
                'filename':options['filename'],
                'path':path
                }
            self.data_objs.append([len(self.data_objs)+1,'common',tmpdict])
            self.table_display_list.append([str(len(self.data_objs)),options['filename'],'',options['url'],'普通下载','','','-',path,'待处理'])
            self.task_queue.put_nowait(lambda args=tmpdict:self._common_download_thread(**args))
        elif mode == 'manga':
            if 'mcid' in options:
                #提取预处理数据
                try:
                    if data:
                        assert data['mcid']==options['mcid'],'预请求数据包内容不匹配'
                    else:
                        data = biliapis.manga.get_detail(options['mcid'])
                except Exception as e:
                    msgbox.showerror('',str(e),parent=self.window)
                    return
                #提取epindexes
                if 'epindexes' in options:
                    indexes = options['epindexes']
                    if not indexes:
                        list(range(0,len(data['ep_list'])))
                #分发任务
                else:
                    indexes = list(range(0,len(data['ep_list'])))
                #分发任务
                for index in indexes:
                    tmpdict = {
                        'index':len(self.data_objs),
                        'epid':data['ep_list'][index]['epid'],
                        'path':path
                        }
                    self.data_objs.append([len(self.data_objs)+1,'manga',tmpdict])
                    self.table_display_list.append([str(len(self.data_objs)),data['comic_title'],data['ep_list'][index]['eptitle'],'EP'+str(data['ep_list'][index]['epid']),'漫画下载','','-','',path,'待处理'])
                    self.task_queue.put_nowait(lambda args=tmpdict:self._manga_download_thread(**args))
            elif 'epid' in options:
                #提取预处理数据
                try:
                    if data:
                        assert data['epid']==options['epid'],'预请求数据包内容不匹配'
                    else:
                        data = biliapis.manga.get_episode_info(options['epid'])
                except Exception as e:
                    msgbox.showerror('',str(e),parent=self.window)
                    return
                tmpdict = {
                    'index':len(self.data_objs),
                    'epid':options['epid'],
                    'path':path
                    }
                self.data_objs.append([len(self.data_objs)+1,'manga',tmpdict])
                self.table_display_list.append([str(len(self.data_objs)),data['comic_title'],data['eptitle'],'EP'+str(data['epid']),'漫画下载','','-','',path,'待处理'])
                self.task_queue.put_nowait(lambda args=tmpdict:self._manga_download_thread(**args))
            
        self.save_progress()

    def retry_all_failed(self):
        if self.failed_indexes:
            while self.failed_indexes:
                self._restart_task(self.failed_indexes[0])
        elif self.window:
            msgbox.showinfo('','没有失败的任务呢.',parent=self.window)

    def _restart_task(self,index):
        if index in self.failed_indexes:
            del self.failed_indexes[self.failed_indexes.index(index)]
        elif index in self.done_indexes:
            del self.done_indexes[self.done_indexes.index(index)]
        else:
            raise RuntimeError('Task index {} not allowed being restarted.'.format(index))
        data = self.data_objs[index]
        for name in ['size','quality']:
            self._edit_display_list(index,name,'')
        self._edit_display_list(index,'status','待处理')
        if data[1] == 'video':
            self.task_queue.put_nowait(lambda args=data[2]:self._video_download_thread(**args))
        elif data[1] == 'audio':
            self.task_queue.put_nowait(lambda args=data[2]:self._audio_download_thread(**args))
        elif data[1] == 'common':
            self.task_queue.put_nowait(lambda args=data[2]:self._common_download_thread(**args))
        elif data[1] == 'manga':
            self.task_queue.put_nowait(lambda args=data[2]:self._manga_download_thread(**args))
        
    def show(self):
        if self.window:#构建GUI
            if self.window.state() == 'iconic':
                self.window.deiconify()
        else:
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
                self.table.column(column,width=self.table_columns_widths[i],minwidth=self.table_columns_widths[i],anchor='w')
                self.table.heading(column,text=self.table_columns[column],anchor='w')
                i += 1
            #数据统计
            self.frame_stat = tk.Frame(self.window)
            self.frame_stat.grid(column=0,row=1,sticky='nw',padx=10)
            tk.Label(self.frame_stat,text='总任务数:')  .grid(column=0,row=0,sticky='e')
            tk.Label(self.frame_stat,text='已完成:')    .grid(column=0,row=1,sticky='e')
            tk.Label(self.frame_stat,text='运行中:')    .grid(column=0,row=2,sticky='e')
            tk.Label(self.frame_stat,text='失败:')      .grid(column=0,row=3,sticky='e')
            tk.Label(self.frame_stat,text='线程数:')    .grid(column=0,row=4,sticky='e')
            tk.Label(self.frame_stat,text='队列长度:')  .grid(column=0,row=5,sticky='e')
            self.label_stat_totaltask = tk.Label(self.frame_stat,text='0')
            self.label_stat_totaltask.grid(column=1,row=0,sticky='w')
            self.label_stat_donetask = tk.Label(self.frame_stat,text='0')
            self.label_stat_donetask.grid(column=1,row=1,sticky='w')
            self.label_stat_runningtask = tk.Label(self.frame_stat,text='0')
            self.label_stat_runningtask.grid(column=1,row=2,sticky='w')
            self.label_stat_failedtask = tk.Label(self.frame_stat,text='0')
            self.label_stat_failedtask.grid(column=1,row=3,sticky='w')
            self.label_stat_threadnum = tk.Label(self.frame_stat,text='0 / 0')
            self.label_stat_threadnum.grid(column=1,row=4,sticky='w')
            self.label_stat_queuelen = tk.Label(self.frame_stat,text='0')
            self.label_stat_queuelen.grid(column=1,row=5,sticky='w')
            #操作面板
            self.frame_console = tk.LabelFrame(self.window,text='操作')
            self.frame_console.grid(column=1,row=1,sticky='nw')
            ttk.Button(self.frame_console,text='重试所有失败任务',command=self.retry_all_failed).grid(column=0,row=0,sticky='w')
        
            self.auto_refresh_table()
            
    def auto_refresh_table(self):#更新依据: self.table_display_list
        if self.window:
            obj = self.table.get_children()
            fast_refresh = False
            if len(obj) == len(self.table_display_list):
                #不涉及项数增减的修改
                for i in range(len(obj)):
                    if self.table.item(obj[i])['values'] != self.table_display_list[i]:
                        self.table.item(obj[i],values=self.table_display_list[i])
                        fast_refresh = True
            else:
                fast_refresh = True
                #涉及到项数增减的修改
                #记录选中项
                indexes = []
                for item in self.table.selection():
                    indexes.append(obj.index(item))
                #删除旧项
                for o in obj:
                    self.table.delete(o)
                #填充新内容
                i = 0
                for line in self.table_display_list:
                    i += 1
                    self.table.insert('','end',values=tuple(line))
                #复现选中项
                obj = self.table.get_children()
                for index in indexes:
                    self.table.selection_set(obj[index])
            #更新统计信息
            self.label_stat_totaltask['text'] = str(len(self.data_objs))
            self.label_stat_donetask['text'] = str(len(self.done_indexes))
            self.label_stat_failedtask['text'] = str(len(self.failed_indexes))
            self.label_stat_runningtask['text'] = str(len(self.running_indexes))
            self.label_stat_threadnum['text'] = '{} / {}'.format(self.thread_counter,config['download']['max_thread_num'])
            self.label_stat_queuelen['text'] = str(self.task_queue.qsize())
            #准备下一次循环
            if fast_refresh:
                self.refresh_loop_schedule = self.window.after(200+len(self.table_display_list)*2,self.auto_refresh_table)
            else:
                self.refresh_loop_schedule = self.window.after(2000,self.auto_refresh_table)
        else:
            pass

    def hide(self):
        if self.window:
            if self.refresh_loop_schedule:
                self.window.after_cancel(self.refresh_loop_schedule)
                self.refresh_loop_schedule = None
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
        self.entry_source.bind('<Return>',lambda x=0:self.start())
        ttk.Button(self.frame_entry,text='粘贴',command=lambda:self.set_entry(self.entry_source,text=self.entry_source.clipboard_get()),width=5).grid(column=1,row=1)
        ttk.Button(self.frame_entry,text='清空',command=lambda:self.entry_source.delete(0,'end'),width=5).grid(column=2,row=1)
        #Login Area
        self.frame_login = tk.LabelFrame(self.window,text='用户信息')
        self.frame_login.grid(column=0,row=1,sticky='wns',rowspan=2)
        self.label_face = cusw.ImageLabel(self.frame_login,width=120,height=120)
        self.label_face.grid(column=0,row=0,sticky='nwe')
        self.label_face_text = tk.Label(self.frame_login,text='未登录',bg='#ffffff',font=('Microsoft YaHei UI',8))#图片上的提示文本
        self.label_face_text.grid(column=0,row=0)
        self.frame_login_button = tk.Frame(self.frame_login)
        self.frame_login_button.grid(column=0,row=1,sticky='nwe')
        self.button_login = ttk.Button(self.frame_login_button,text='登录',width=13,command=self.login)
        self.button_login.grid(column=0,row=0,sticky='w')
        self.button_refresh = cusw.ImageButton(self.frame_login_button,width=17,height=17,image_bytesio=imglib.refresh_sign,command=self.refresh_data,state='disabled')
        self.button_refresh.grid(column=1,row=0)
        #Entry Mode Selecting
        self.frame_entrymode = tk.LabelFrame(self.window,text='输入模式',width=50)
        self.frame_entrymode.grid(column=1,row=1,sticky='enw',rowspan=2)
        self.intvar_entrymode = tk.IntVar(self.window,0)#跳转0, 搜索1, 快速下载2
        self.radiobutton_entrymode_jump = ttk.Radiobutton(self.frame_entrymode,value=0,variable=self.intvar_entrymode,text='跳转')
        self.radiobutton_entrymode_jump.grid(column=0,row=0,sticky='w')
        self.radiobutton_entrymode_search = ttk.Radiobutton(self.frame_entrymode,value=1,variable=self.intvar_entrymode,text='搜索')
        self.radiobutton_entrymode_search.grid(column=0,row=1,sticky='w')
        self.radiobutton_entrymode_fdown = ttk.Radiobutton(self.frame_entrymode,value=2,variable=self.intvar_entrymode,text='快速下载')
        self.radiobutton_entrymode_fdown.grid(column=0,row=2,sticky='w')

        self.frame_sysfuncs = tk.Frame(self.window)
        self.frame_sysfuncs.grid(column=1,row=2,sticky='s')
        ttk.Button(self.frame_sysfuncs,text='下载姬',width=15,command=download_manager.show).grid(column=0,row=0)
        ttk.Button(self.frame_sysfuncs,text='批处理',width=15,command=self.goto_batch).grid(column=0,row=1)
        
        ttk.Button(self.window,text='开始',width=11,command=self.start).grid(column=2,row=1,sticky='ne')
        #Basic Funcs
        self.frame_basicfuncs = tk.Frame(self.window)
        self.frame_basicfuncs.grid(column=2,row=2,sticky='se')
        self.button_config = ttk.Button(self.frame_basicfuncs,text='设置',width=11,command=self.goto_config)
        self.button_config.grid(column=0,row=1)
        ttk.Button(self.frame_basicfuncs,text='关于',width=11,command=lambda:msgbox.showinfo('',about_info,parent=self.window)).grid(column=0,row=2)
        #Funcs Area
        self.frame_funcarea = tk.LabelFrame(self.window,text='功能区')
        self.frame_funcarea.grid(column=0,row=3,sticky='wnse',columnspan=3)
        self.button_blackroom = ttk.Button(self.frame_funcarea,text='小黑屋',command=self.goto_blackroom)
        self.button_blackroom.grid(column=0,row=0,sticky='w')
        ttk.Button(self.frame_funcarea,text='转换弹幕',command=self.convert_danmaku).grid(column=1,row=0)
        self.button_search = ttk.Button(self.frame_funcarea,text='搜索',command=self.goto_search)
        self.button_search.grid(column=2,row=0)
        #Tips
        self.label_tips = tk.Label(self.window,text='Tips: -')
        self.label_tips.grid(column=0,row=4,sticky='w',columnspan=3)
        self.label_tips.bind('<Button-1>',lambda x=0:self.changeTips())

        self.changeTips()
        self.login(True)
        self.entry_source.focus()
        self.entry_source.bind('<Tab>',lambda x=0:(self.intvar_entrymode.set((self.intvar_entrymode.get()+1)%3),
                                                   self.window.after(10,lambda:self.entry_source.focus())))

        self.mainloop()

    def _clear_face(self):
        self.label_face.clear()
        self.label_face_text.grid()
        self.label_face.unbind('<Button-1>')

    def _new_login(self):
        self.window.wm_attributes('-topmost',False)
        w = LoginWindow()
        if w.status:
            biliapis.requester.load_local_cookies()
            self.refresh_data()
        else:
            msgbox.showwarning('','登录未完成.',parent=self.window)
            self.task_queue.put_nowait(lambda:self.button_login.configure(state='normal'))
        self.window.wm_attributes('-topmost',config['topmost'])

    def refresh_data(self):
        def tmp():
            self.task_queue.put_nowait(lambda:self.button_login.configure(state='disabled'))
            self.task_queue.put_nowait(lambda:self.button_refresh.configure(state='disabled'))
            try:
                data = biliapis.login.get_login_info()
            except biliapis.BiliError as e:
                if e.code == -101:
                    self.task_queue.put_nowait(lambda:msgbox.showwarning('','未登录.',parent=self.window))
                else:
                    self.task_queue.put_nowait(lambda ei=str(e):msgbox.showerror('',ei,parent=self.window))
                self.task_queue.put_nowait(lambda:self.button_login.configure(state='normal'))
                self.task_queue.put_nowait(self._clear_face)
                self.task_queue.put_nowait(lambda:self.button_login.configure(text='登录',command=self.login))
            except Exception as e:
                self.task_queue.put_nowait(lambda ei=str(e):msgbox.showerror('',ei,parent=self.window))
                self.task_queue.put_nowait(lambda:self.button_login.configure(state='normal'))
                self.task_queue.put_nowait(self._clear_face)
                self.task_queue.put_nowait(lambda:self.button_login.configure(text='登录',command=self.login))
            else:
                def load_user_info(user_data):
                    self.label_face.set(BytesIO(biliapis.requester.get_content_bytes(biliapis.format_img(user_data['face'],w=120,h=120))))
                    self.label_face_text.grid_remove()
                    self.label_face.bind('<Button-1>',
                                         lambda event=None,text='{name}\nUID{uid}\nLv.{level}\n{vip_type}\nCoin: {coin}\nMoral: {moral}'.format(**user_data):msgbox.showinfo('User Info',text,parent=self.window))
                self.task_queue.put_nowait(lambda:load_user_info(data))
                self.task_queue.put_nowait(lambda:self.button_login.configure(state='normal'))
                self.task_queue.put_nowait(lambda:self.button_refresh.configure(state='normal'))
                self.task_queue.put_nowait(lambda:self.button_login.configure(text='退出登录',command=self.logout))
        start_new_thread(tmp,())

    def login(self,init=False):
        def tmp():
            self.task_queue.put_nowait(lambda:self.button_login.configure(state='disabled'))
            if biliapis.login.check_login():
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
            biliapis.login.exit_login()
            biliapis.requester.cookies.save()
        except biliapis.BiliError:
            msgbox.showwarning('','未登录.',parent=self.window)
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

    def goto_batch(self):
        w = BatchWindow()

    def goto_search(self):
        w = SearchWindow()

    def convert_danmaku(self):
        xmlfiles = list(filedialog.askopenfilenames(defaultextension='xml',filetypes=[('XML弹幕文件','.xml')],title='选择弹幕文件',parent=self.window))
        if xmlfiles:
            for f in xmlfiles:
                danmaku_to_ass(f,os.path.splitext(f)[0]+'.ass')
        msgbox.showinfo('',f'已尝试转换 {len(xmlfiles)} 个文件.')

    def goto_config(self):
        self.button_config['state'] = 'disabled'
        w = ConfigWindow()
        if self.is_alive():
            self.button_config['state'] = 'normal'
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
            msgbox.showinfo('','你似乎没有输入任何内容......',parent=self.window)
            return
        mode = self.intvar_entrymode.get()
        if mode == 0:#跳转模式
            source,flag = biliapis.parse_url(source)
            if flag == 'unknown':
                msgbox.showinfo('','无法解析......',parent=self.window)
            elif flag == 'auid':
                w = AudioWindow(source)
            elif flag == 'avid' or flag == 'bvid':
                w = CommonVideoWindow(source)
            elif flag == 'ssid' or flag == 'mdid' or flag == 'epid':
                w = BangumiWindow(**{flag:source})
            elif flag == 'cvid':
                pass
            elif flag == 'uid':
                pass
            else:
                msgbox.showinfo('','暂不支持%s的跳转'%flag,parent=self.window)
            return
        elif mode == 1:#搜索模式
            if source:
                kws = source.split()
                w = SearchWindow(*kws)
        elif mode == 2:#快速下载模式
            source,flag = biliapis.parse_url(source)
            if flag == 'unknown':
                msgbox.showinfo('','无法解析......',parent=self.window)
            elif flag == 'avid' or flag == 'bvid':#普通视频
                path = filedialog.askdirectory(title='选择保存位置',parent=self.window)
                if not path:
                    return
                video_data = biliapis.video.get_detail(**{flag:source})
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
                download_manager.task_receiver('video',path,bvid=video_data['bvid'],data=video_data,pids=indexes)
            elif flag == 'auid':#音频
                path = filedialog.askdirectory(title='选择保存位置',parent=self.window)
                if not path:
                    return
                download_manager.task_receiver('audio',path,auid=source)
            elif flag == 'ssid' or flag == 'mdid' or flag == 'epid':#番
                path = filedialog.askdirectory(title='选择保存位置',parent=self.window)
                if not path:
                    return
                bangumi_data = biliapis.media.get_detail(**{flag:source})
                episodes = bangumi_data['episodes']
                title = bangumi_data['title']
                if len(episodes) > 0:
                    tmp = []
                    for episode in episodes:
                        tmp += [[episode['title'],'-','-']]
                    indexes = PartsChooser(tmp).return_values
                    if not indexes:
                        return
                else:
                    msgbox.showinfo('','没有正片',parent=self.window)
                    return
                download_manager.task_receiver('video',path,ssid=bangumi_data['ssid'],data=bangumi_data,epindexes=indexes)
            elif flag == 'mcid':#漫画
                path = filedialog.askdirectory(title='选择保存位置',parent=self.window)
                if not path:
                    return
                manga_data = biliapis.manga.get_detail(mcid=source)
                if len(manga_data['ep_list']) > 0:
                    indexes = PartsChooser([[i['eptitle'],str(i['epid']),{True:'Yes',False:'No'}[i['pay_gold']==0],{True:'Yes',False:'No'}[i['is_locked']]] for i in manga_data['ep_list']],
                                           title='EpisodesChooser',columns=['章节标题','EpID','是否免费','是否锁定'],columns_widths=[200,70,60,60]).return_values
                    if not indexes:
                        return
                else:
                    msgbox.showinfo('','没有章节',parent=self.window)
                    return
                download_manager.task_receiver('manga',path,data=manga_data,mcid=source,epindexes=indexes)
            elif flag == 'collection':#合集
                path = filedialog.askdirectory(title='选择保存位置',parent=self.window)
                if path:
                    collection = biliapis.video.get_archive_list(*source,page_size=100)
                    if len(collection['archives']):
                        indexes = PartsChooser([[i['title'],biliapis.second_to_time(i['duration']),i['bvid'],{True:'Yes',False:'No'}[i['is_interact_video']]] for i in collection['archives']],
                                               columns=['标题','长度','BvID','互动视频'],title='Collection').return_values
                        if indexes:
                            for index in indexes:
                                download_manager.task_receiver('video',path,bvid=collection['archives'][index]['bvid'])
                    else:
                        msgbox.showinfo('合集没有内容',parent=self.window)
            elif flag == 'favlist':#收藏夹
                pass
            else:
                msgbox.showinfo('','暂不支持%s的快速下载'%flag,parent=self.window)

class BatchWindow(Window):
    def __init__(self):
        super().__init__('BiliTools - Batch',True,config['topmost'],config['alpha'])

        #Main Entry
        tk.Label(self.window,text='每行一个网址, 仅支持批量下载普通视频.\n所有分P均会被下载.\n可能会出现未响应的情况, 请耐心等待.',justify='left').grid(column=0,row=0,sticky='w')
        self.scrollbar_x = ttk.Scrollbar(self.window,orient=tk.HORIZONTAL)
        self.entry_main = scrolledtext.ScrolledText(self.window,width=70,height=20,wrap='none',xscrollcommand=self.scrollbar_x.set)
        self.entry_main.grid(column=0,row=1)
        self.scrollbar_x.grid(column=0,row=2,sticky='we')
        self.scrollbar_x['command'] = self.entry_main.xview

        self.boolvar_audiomode = tk.BooleanVar(self.window,False)
        self.checkbutton_audiomode = ttk.Checkbutton(self.window,text='仅抽取音轨',variable=self.boolvar_audiomode,onvalue=True,offvalue=False)
        self.checkbutton_audiomode.grid(column=0,row=3,sticky='w')

        self.button_start = ttk.Button(self.window,text='走你',command=self.start)
        self.button_start.grid(column=0,row=3,sticky='e')

        self.mainloop()

    def start(self,text=None):
        if not text:
            text = self.entry_main.get(1.0,'end')
        path = filedialog.askdirectory(title='输出至',parent=self.window)
        if text and path:
            audiomode = self.boolvar_audiomode.get()
            self.close()
            lines = text.split('\n')
            for line in lines:
                if line:
                    source,flag = biliapis.parse_url(line)
                    if flag in ['avid','bvid']:
                        download_manager.task_receiver('video',path,audiostream_only=audiomode,**{flag:source})

class InputWindow(Window):
    def __init__(self,master,label=None,text=None):
        super().__init__('BiliTools - Inputer',True,config['topmost'],config['alpha'],master=master)
        self.return_value = None
        tk.Label(self.window,text=label).grid(column=0,row=0,sticky='w')
        self.sctext = scrolledtext.ScrolledText(self.window,width=40,height=20)
        self.sctext.grid(column=0,row=1)
        if text:
            self.sctext.insert('end',text)
        ttk.Button(self.window,text='完成',command=self.finish).grid(column=0,row=2,sticky='e')
        ttk.Button(self.window,text='取消',command=self.close).grid(column=0,row=2,sticky='w')
        self.mainloop()

    def finish(self):
        var = self.sctext.get(1.0,'end').strip()
        if var:
            self.return_value = var
            self.close()
        else:
            pass
            
class ConfigWindow(Window):
    def __init__(self):
        super().__init__('BiliTools - Config',True,config['topmost'],config['alpha'])
        
        #Basic
        self.frame_basic = tk.LabelFrame(self.window,text='基础')
        self.frame_basic.grid(column=0,row=0,sticky='nw')
        #Topmost
        self.boolvar_topmost = tk.BooleanVar(self.window,config['topmost'])
        self.checkbutton_topmost = ttk.Checkbutton(self.frame_basic,text='置顶',onvalue=True,offvalue=False,variable=self.boolvar_topmost)
        self.checkbutton_topmost.grid(column=0,row=0,sticky='w')
        #Alpha
        self.frame_winalpha = tk.LabelFrame(self.frame_basic,text='窗体不透明度')
        self.frame_winalpha.grid(column=0,row=1,sticky='we')
        self.doublevar_winalpha = tk.DoubleVar(self.window,value=config['alpha'])
        self.label_winalpha_shower = tk.Label(self.frame_winalpha,text='%3d%%'%(config['alpha']*100),width=5)
        self.label_winalpha_shower.grid(column=0,row=0,sticky='w')
        self.scale_winalpha = ttk.Scale(self.frame_winalpha,from_=0.3,to=1.0,orient=tk.HORIZONTAL,variable=self.doublevar_winalpha,command=lambda coor:self.label_winalpha_shower.configure(text='% 3d%%'%(round(float(coor),2)*100)))
        self.scale_winalpha.grid(column=1,row=0,sticky='w')
        self.tooltip_winalpha = cusw.ToolTip(self.frame_winalpha,text='注意，不透明度调得过低会影响操作体验')
        #Emoji Filter
        self.frame_filteremoji = tk.Frame(self.frame_basic)
        self.frame_filteremoji.grid(column=0,row=2,sticky='w')
        self.boolvar_filteremoji = tk.BooleanVar(self.window,config['filter_emoji'])
        self.checkbutton_filteremoji = ttk.Checkbutton(self.frame_filteremoji,text='过滤Emoji',onvalue=True,offvalue=False,variable=self.boolvar_filteremoji)
        self.checkbutton_filteremoji.grid(column=0,row=0)
        ttk.Separator(self.frame_basic,orient='horizontal').grid(column=0,row=3,sticky='s',ipadx=80)

        #Download
        self.frame_download = tk.LabelFrame(self.window,text='下载')
        self.frame_download.grid(column=1,row=0,sticky='nswe')
        #Thread Number
        self.intvar_threadnum = tk.IntVar(self.window,config['download']['max_thread_num'])
        tk.Label(self.frame_download,text='最大线程数: ').grid(column=0,row=0,sticky='e')
        ttk.OptionMenu(self.frame_download,self.intvar_threadnum,config['download']['max_thread_num'],*range(1,17)).grid(column=1,row=0,sticky='w')
        #Video Quality
        if config['download']['video']['quality_regular']:
            default_vq = bilicodes.stream_dash_video_quality[config['download']['video']['quality_regular'][0]]
        else:
            default_vq = bilicodes.stream_dash_video_quality[max(list(bilicodes.stream_dash_video_quality.keys()))]
        self.strvar_video_quality = tk.StringVar(self.window,default_vq)
        tk.Label(self.frame_download,text='优先画质: ').grid(column=0,row=1,sticky='e')
        ttk.OptionMenu(self.frame_download,self.strvar_video_quality,default_vq,*list(bilicodes.stream_dash_video_quality.values())).grid(column=1,row=1,sticky='w')

        #Subtitle
        self.frame_subtitle = tk.LabelFrame(self.window,text='字幕与歌词')
        self.frame_subtitle.grid(column=0,row=1,sticky='we',columnspan=2)
        self.subtitle_preset = {
            '中文优先':['zh-CN','zh-Hans','zh-Hant','zh-HK','zh-TW','en-US','en-GB','ja','ja-JP'],
            '英文优先':['en-US','en-GB','zh-CN','zh-Hans','zh-Hant','zh-HK','zh-TW','ja','ja-JP'],
            '日文优先':['ja','ja-JP','zh-CN','zh-Hans','zh-Hant','zh-HK','zh-TW','en-US','en-GB']
            }
        self.boolvar_subtitle = tk.BooleanVar(self.window,config['download']['video']['subtitle'])
        self.checkbutton_subtitle = ttk.Checkbutton(self.frame_subtitle,text='下载字幕',onvalue=True,offvalue=False,variable=self.boolvar_subtitle)
        self.checkbutton_subtitle.grid(column=0,row=0,columnspan=2,sticky='w')
        init_subtitle_om_text = self._get_subtitle_preset_text()
        self.strvar_subtitle_preset = tk.StringVar(self.window,init_subtitle_om_text)
        tk.Label(self.frame_subtitle,text='多字幕视频的字幕方案:').grid(column=0,row=1,sticky='e')
        self.om_subtitle_preset = ttk.OptionMenu(self.frame_subtitle,self.strvar_subtitle_preset,init_subtitle_om_text,*list(self.subtitle_preset.keys()),'自定义',command=self._subtitle_preset_command)
        self.om_subtitle_preset.grid(column=1,row=1,sticky='w')
        self.subtitle_regular = config['download']['video']['subtitle_lang_regular']
        #Lyrics
        self.boolvar_lyrics = tk.BooleanVar(self.window,config['download']['audio']['lyrics'])
        self.checkbutton_lyrics = ttk.Checkbutton(self.frame_subtitle,text='下载歌词',onvalue=True,offvalue=False,variable=self.boolvar_lyrics)
        self.checkbutton_lyrics.grid(column=0,row=2,columnspan=2,sticky='w')
        
        #Danmaku
        self.frame_danmaku = tk.LabelFrame(self.window,text='弹幕')
        self.frame_danmaku.grid(column=2,row=0,sticky='wnse')
        self.boolvar_danmaku = tk.BooleanVar(self.window,config['download']['video']['danmaku'])
        self.checkbutton_danmaku = ttk.Checkbutton(self.frame_danmaku,text='下载弹幕',onvalue=True,offvalue=False,variable=self.boolvar_danmaku)
        self.checkbutton_danmaku.grid(column=0,row=0,sticky='w')
        #filter
        self.frame_dmfilter = tk.LabelFrame(self.frame_danmaku,text='弹幕过滤')
        self.frame_dmfilter.grid(column=0,row=1,sticky='we')
        tk.Label(self.frame_dmfilter,text='过滤等级:').grid(column=0,row=0,sticky='e')
        self.strvar_dmflevel = tk.StringVar(self.window,str(config['download']['video']['danmaku_filter']['filter_level']))
        self.om_dmflevel = ttk.OptionMenu(self.frame_dmfilter,self.strvar_dmflevel,self.strvar_dmflevel.get(),*[str(i) for i in list(range(0,11))])
        self.om_dmflevel.grid(column=1,row=0,sticky='w')
        #过滤规则计数
        tk.Label(self.frame_dmfilter,text='关键词:').grid(column=0,row=1,sticky='e')
        self.label_dmfkwcount = tk.Label(self.frame_dmfilter,text='{} 个'.format(len(config['download']['video']['danmaku_filter']['keyword'])))
        self.label_dmfkwcount.grid(column=1,row=1,sticky='w')
        tk.Label(self.frame_dmfilter,text='正则:').grid(column=0,row=2,sticky='e')
        self.label_dmfrecount = tk.Label(self.frame_dmfilter,text='{} 个'.format(len(config['download']['video']['danmaku_filter']['regex'])))
        self.label_dmfrecount.grid(column=1,row=2,sticky='w')
        tk.Label(self.frame_dmfilter,text='用户:').grid(column=0,row=3,sticky='e')
        self.label_dmfusercount = tk.Label(self.frame_dmfilter,text='{} 个'.format(len(config['download']['video']['danmaku_filter']['user'])))
        self.label_dmfusercount.grid(column=1,row=3,sticky='w')
        self.frame_dmfrule_opt = tk.Frame(self.frame_dmfilter)
        self.frame_dmfrule_opt.grid(column=0,row=4,columnspan=2,sticky='w')
        ttk.Button(self.frame_dmfrule_opt,text='清空',command=self._clear_dmfrule).grid(column=0,row=0)
        ttk.Button(self.frame_dmfrule_opt,text='同步',command=self._sync_dmfrule).grid(column=1,row=0)
        self.dmfrule = copy.deepcopy(config['download']['video']['danmaku_filter'])
        
        #convert
        self.boolvar_convert_danmaku = tk.BooleanVar(self.window,config['download']['video']['convert_danmaku'])
        self.checkbutton_convert_danmaku = ttk.Checkbutton(self.frame_danmaku,text='转换弹幕',onvalue=True,offvalue=False,variable=self.boolvar_convert_danmaku)
        self.checkbutton_convert_danmaku.grid(column=0,row=2,sticky='w')
        if not config['download']['video']['danmaku']:
            self.checkbutton_convert_danmaku['state'] = 'disabled'
        self.checkbutton_danmaku['command'] = lambda:self.checkbutton_convert_danmaku.configure(state={True:'normal',False:'disabled'}[self.boolvar_danmaku.get()])
        
        # Save or Cancel
        self.frame_soc = tk.Frame(self.window)
        self.frame_soc.grid(column=2,row=1,sticky='se')
        ttk.Button(self.frame_soc,text='取消',width=5,command=self.close).grid(column=0,row=0)
        ttk.Button(self.frame_soc,text='保存',width=5,command=self.save_config).grid(column=1,row=0)

        self.mainloop()

    def _clear_dmfrule(self):
        self.dmfrule = {
            'keyword':[],
            'regex':[],
            'user':[],
            'filter_level':int(self.strvar_dmflevel.get())
            }
        self.label_dmfkwcount['text'] = '{} 个'.format(len(self.dmfrule['keyword']))
        self.label_dmfrecount['text'] = '{} 个'.format(len(self.dmfrule['regex']))
        self.label_dmfusercount['text'] = '{} 个'.format(len(self.dmfrule['user']))

    def _sync_dmfrule(self):
        try:
            rule = biliapis.user.get_danmaku_filter()
        except biliapis.BiliError as e:
            if e.code == '-101':
                msgbox.showwarning('','未登录.',parent=self.window)
            else:
                msgbox.showerror('',str(e),parent=self.window)
        except Exception as e:
            msgbox.showerror('',str(e),parent=self.window)
        else:
            self.dmfrule = rule
            self.label_dmfkwcount['text'] = '{} 个'.format(len(rule['keyword']))
            self.label_dmfrecount['text'] = '{} 个'.format(len(rule['regex']))
            self.label_dmfusercount['text'] = '{} 个'.format(len(rule['user']))

    def _get_subtitle_preset_text(self,method_list=None):
        if not method_list:
            method_list = config['download']['video']['subtitle_lang_regular']
        if method_list in list(self.subtitle_preset.values()):
            init_subtitle_om_text = list(self.subtitle_preset.keys())[list(self.subtitle_preset.values()).index(method_list)]
        else:
            init_subtitle_om_text = '...'
        return init_subtitle_om_text

    def _subtitle_preset_command(self,selectvar):
        if selectvar == '自定义':
            self.om_subtitle_preset['state'] = 'disabled'
            w = InputWindow(
                master=self.window,
                label='输入一个新的方案.\n每行一种语言, 程序会按照顺序进行匹配.',
                text='\n'.join(self.subtitle_regular)
                )
            if self.is_alive():
                self.om_subtitle_preset['state'] = 'normal'
            if w.return_value:
                self.subtitle_regular = w.return_value.split('\n')
        else:
            self.subtitle_regular = self.subtitle_preset[selectvar]
        if self.is_alive():
            self.strvar_subtitle_preset.set(self._get_subtitle_preset_text(self.subtitle_regular))

    def apply_config(self):#
        global config
        config['topmost'] = self.boolvar_topmost.get()
        config['alpha'] = round(self.doublevar_winalpha.get(),2)
        config['filter_emoji'] = self.boolvar_filteremoji.get()
        config['download']['max_thread_num'] = self.intvar_threadnum.get()
        config['download']['video']['quality_regular'] = make_quality_regular(self.strvar_video_quality.get())
        biliapis.requester.filter_emoji = config['filter_emoji']
        config['download']['video']['subtitle_lang_regular'] = self.subtitle_regular
        config['download']['video']['subtitle'] = self.boolvar_subtitle.get()
        config['download']['audio']['lyrics'] = self.boolvar_lyrics.get()
        config['download']['video']['danmaku'] = self.boolvar_danmaku.get()
        config['download']['video']['convert_danmaku'] = self.boolvar_convert_danmaku.get()
        config['download']['video']['danmaku_filter'] = self.dmfrule
        config['download']['video']['danmaku_filter']['filter_level'] = int(self.strvar_dmflevel.get())
        dump_config()

    def save_config(self):
        self.apply_config()
        self.close()

class AudioWindow(Window):
    def __init__(self,auid):
        self.auid = int(auid)
        self.audio_data = None
        
        super().__init__('BiliTools - Audio',True,config['topmost'],config['alpha'])

        #cover
        self.label_cover_shower = cusw.ImageLabel(self.window,width=300,height=300)
        self.label_cover_shower.grid(column=0,row=0,rowspan=4,sticky='w')
        self.label_cover_text = tk.Label(self.window,text='加载中',font=('Microsoft YaHei UI',8),bg='#ffffff')
        self.label_cover_text.grid(column=0,row=0,rowspan=4)
        #audio name
        self.text_name = tk.Text(self.window,font=('Microsoft YaHei UI',10,'bold'),width=37,height=2,state='disabled',bg='#f0f0f0',bd=0)
        self.text_name.grid(column=0,row=4)
        self.tooltip_name = cusw.ToolTip(self.text_name)
        #id
        self.label_auid = tk.Label(self.window,text='auID0')
        self.label_auid.grid(column=0,row=5,sticky='e')
        #description
        tk.Label(self.window,text='简介↓').grid(column=0,row=6,sticky='w')
        self.sctext_desc = scrolledtext.ScrolledText(self.window,state='disabled',width=41,height=12)
        self.sctext_desc.grid(column=0,row=7,sticky='w')
        #uploader
        self.frame_uploader = tk.LabelFrame(self.window,text='UP主')
        self.label_uploader_face = cusw.ImageLabel(self.frame_uploader,width=50,height=50)#up头像
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
        self.mainloop()

    def download_audio(self):
        self.button_download_cover['state'] = 'disabled'
        path = filedialog.askdirectory(title='保存至',parent=self.window)
        if path:
            download_manager.task_receiver('audio',path,auid=self.auid)
        self.button_download_cover['state'] = 'normal'

    def download_cover(self):
        self.button_download_lyrics['state'] = 'disabled'
        if self.audio_data:
            filename = replaceChr(self.title)+'.jpg'
            path = filedialog.askdirectory(title='保存至',parent=self.window)
            if path:
                url = biliapis.audio.get_info(self.auid)['cover']
                with open(os.path.join(path,filename),'wb+') as f:
                    f.write(biliapis.requester.get_content_bytes(url))
                msgbox.showinfo('','完成',parent=self.window)
        else:
            msgbox.showwarning('','加载未完成')
        if self.is_alive():
            self.button_download_lyrics['state'] = 'normal'
        return

    def download_lyrics(self):
        self.button_download_lyrics['state'] = 'disabled'
        if self.audio_data:
            filename = replaceChr(self.title)+'.lrc'
            path = filedialog.askdirectory(title='保存至',parent=self.window)
            if path:
                data = biliapis.audio.get_lyrics(self.auid)
                if data == 'Fatal: API error':
                    msgbox.showinfo('','没有歌词',parent=self.window)
                else:
                    with open(os.path.join(path,filename),'w+',encoding='utf-8') as f:
                        f.write(data)
                    msgbox.showinfo('','完成',parent=self.window)
        else:
            msgbox.showwarning('','加载未完成')
        if self.is_alive():
            self.button_download_lyrics['state'] = 'normal'
        return
        
    def refresh_data(self):
        def tmp():
            if not self.check_usable():
                self.task_queue.put_nowait(lambda:msgbox.showerror('','音频不存在',parent=self.window))
                self.task_queue.put_nowait(self.close)
                return
            data = biliapis.audio.get_info(self.auid)
            self.audio_data = data
            self.title = data['title']
            self.task_queue.put_nowait(lambda:self.set_text(self.text_name,text=data['title'],lock=True))
            self.task_queue.put_nowait(lambda:self.tooltip_name.change_text(data['title']))
            self.task_queue.put_nowait(lambda:self.label_auid.configure(text='auID%s'%data['auid']))
            if data['description'].strip():
                self.task_queue.put_nowait(lambda:self.set_text(self.sctext_desc,text=data['description'],lock=True))
            else:
                self.task_queue.put_nowait(lambda:self.set_text(self.sctext_desc,text='没有简介',lock=True))
            updata = biliapis.user.get_info(data['uploader']['uid'])
            self.task_queue.put_nowait(lambda:self.label_uploader_name.configure(text=updata['name']))
            self.task_queue.put_nowait(lambda:self.label_uploader_id.configure(text='UID%s'%updata['uid']))
            if data['lyrics_url']:
                lrcdata = biliapis.audio.get_lyrics(self.auid)
                self.task_queue.put_nowait(lambda:self.set_text(self.sctext_lyrics,text=lrcdata,lock=True))
            else:
                self.task_queue.put_nowait(lambda:self.set_text(self.sctext_lyrics,text='没有歌词',lock=True))            
            tagdata = biliapis.audio.get_tags(self.auid)
            if tagdata:
                self.task_queue.put_nowait(lambda:self.set_text(self.text_tags,text='#'+'# #'.join(tagdata)+'#',lock=True))
            else:
                self.task_queue.put_nowait(lambda:self.set_text(self.text_tags,text='没有标签',lock=True))
            #image
            cover = BytesIO(biliapis.requester.get_content_bytes(biliapis.format_img(data['cover'],w=300,h=300)))
            face = BytesIO(biliapis.requester.get_content_bytes(biliapis.format_img(updata['face'],w=50,h=50)))
            self.task_queue.put_nowait(lambda:self.label_cover_shower.set(cover))
            self.task_queue.put_nowait(lambda:self.label_cover_text.grid_remove())
            self.task_queue.put_nowait(lambda:self.label_uploader_face.set(face))
            self.task_queue.put_nowait(lambda:self.label_uploader_face_text.grid_remove())
        start_new_thread(tmp,())

    def check_usable(self):
        try:
            biliapis.audio.get_info(self.auid)
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
        self.label_cover = cusw.ImageLabel(self.frame_left_1,width=380,height=232)
        self.label_cover.grid(column=0,row=0)
        self.label_cover_text = tk.Label(self.frame_left_1,text='加载中',bg='#ffffff')
        self.label_cover_text.grid(column=0,row=0)
        #标题
        self.text_title = tk.Text(self.frame_left_1,bg='#f0f0f0',bd=0,height=2,width=46,state='disabled',font=('Microsoft YaHei UI',10,'bold'))
        self.text_title.grid(column=0,row=1,sticky='w')
        #warning info
        self.label_warning = cusw.ImageLabel(self.frame_left_1,width=22,height=18)
        self.label_warning.set(imglib.warning_sign)
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
        self.label_uploader_face = cusw.ImageLabel(self.frame_uploader,width=50,height=50)#up头像
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
        self.button_show_comments = ttk.Button(self.frame_extraopt,text='查看评论',command=lambda:msgbox.showinfo('','建设中',parent=self.window))#
        self.button_show_comments.grid(column=0,row=0,sticky='se')
        self.button_show_pbp = ttk.Button(self.frame_extraopt,text='查看PBP',command=self.show_pbp)
        self.button_show_pbp.grid(column=0,row=1)
        #desc
        tk.Label(self.frame_left_2,text='简介↑').grid(column=0,row=2,sticky='nw')
        self.frame_desc = tk.Frame(self.frame_left_2)
        self.frame_desc.grid(column=0,row=1)
        self.scrollbar_desc_x = ttk.Scrollbar(self.frame_desc,orient=tk.HORIZONTAL)
        self.scrollbar_desc_x.grid(column=0,row=1,sticky='we')
        self.sctext_desc = scrolledtext.ScrolledText(self.frame_desc,width=40,height=15,state='disabled',wrap='none',xscrollcommand=self.scrollbar_desc_x.set)
        self.scrollbar_desc_x['command'] = self.sctext_desc.xview
        self.sctext_desc.grid(column=0,row=0)
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
        if development_mode:
            self.update_debug_info()
        else:
            self.frame_debug.grid_remove()
        self.refresh_data()

        self.mainloop()

    def show_pbp(self):
        if not self.video_data:
            msgbox.showwarning('','加载尚未完成',parent=self.window)
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
            msgbox.showwarning('','加载尚未完成',parent=self.window)
            return
        self.button_download_audio['state'] = 'disabled'
        path = filedialog.askdirectory(title='选择保存位置',parent=self.window)
        if path:
            parts = self.video_data['parts']
            bvid = self.video_data['bvid']
            title = self.video_data['title']
            if len(parts) > 1:
                tmp = []
                for part in parts:
                    tmp += [[part['title'],biliapis.second_to_time(part['length']),part['cid']]]
                indexes = PartsChooser(tmp).return_values
            else:
                indexes = [0]
            if indexes:
                download_manager.task_receiver('video',path,bvid=self.video_data['bvid'],pids=indexes,audiostream_only=True)
        if self.is_alive():
            self.button_download_audio['state'] = 'normal'

    def download_video(self):
        if not self.video_data:
            msgbox.showwarning('','加载尚未完成',parent=self.window)
            return
        self.button_download_video['state'] = 'disabled'
        path = filedialog.askdirectory(title='选择保存位置',parent=self.window)
        if path:
            parts = self.video_data['parts']
            bvid = self.video_data['bvid']
            title = self.video_data['title']
            if len(parts) > 1:
                tmp = []
                for part in parts:
                    tmp += [[part['title'],biliapis.second_to_time(part['length']),part['cid']]]
                indexes = PartsChooser(tmp).return_values
            else:
                indexes = [0]
            if indexes:
                download_manager.task_receiver('video',path,bvid=self.video_data['bvid'],pids=indexes)
        if self.is_alive():
            self.button_download_video['state'] = 'normal'

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
                self.obj_rec[i][o].append(cusw.ImageLabel(self.obj_rec[i][o][0],width=114,height=69))#cover
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
                self.task_queue.put_nowait(lambda:msgbox.showerror('','视频不存在',parent=self.window))
                self.task_queue.put_nowait(self.close)
                return
            if self.abtype == 'av':
                data = biliapis.video.get_detail(avid=self.abvid)
                tags = biliapis.video.get_tags(avid=self.abvid)
                self.recommend = biliapis.video.get_recommend(avid=self.abvid)
                opener_lambda = lambda:webbrowser.open(f'https://www.bilibili.com/video/av%s'%self.abvid)
            else:
                data = biliapis.video.get_detail(bvid=self.abvid)
                tags = biliapis.video.get_tags(bvid=self.abvid)
                self.recommend = biliapis.video.get_recommend(bvid=self.abvid)
                opener_lambda = lambda:webbrowser.open(f'https://www.bilibili.com/video/'+self.abvid)
            self.video_data = data
            self.task_queue.put_nowait(lambda:self._prepare_recommend(len(self.recommend)))#准备相关视频的存放空间
            #explorer_opener
            self.task_queue.put_nowait(lambda:self.button_open_in_ex.configure(command=opener_lambda))
            #common_info
            self.task_queue.put_nowait(lambda:self.label_avid.configure(text='AV%s'%data['avid']))
            self.task_queue.put_nowait(lambda:self.label_bvid.configure(text=data['bvid']))
            self.task_queue.put_nowait(lambda:self.set_text(self.text_title,lock=True,text=data['title']))
            #warning
            def fill_warning_info(warning_info):
                if warning_info.strip():
                    self.label_warning.grid()
                    self.label_warning_tooltip = cusw.ToolTip(self.label_warning,text=warning_info)
                    self.label_warning.bind('<Button-1>',lambda e=None,t=warning_info:msgbox.showinfo('',t,parent=self.window))
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
            self.task_queue.put_nowait(lambda:self.label_uploader_name.configure(text=up['name']))
            self.task_queue.put_nowait(lambda:self.label_uploader_id.configure(text='UID%s'%up['uid']))
            #desc
            if data['description'].strip():
                desc = data['description']
            else:
                desc = '没有简介'
            self.task_queue.put_nowait(lambda:self.set_text(self.sctext_desc,lock=True,text=desc))
            #img
            def load_img():
                self.task_queue.put_nowait(lambda img=BytesIO(biliapis.requester.get_content_bytes(biliapis.format_img(data['picture'],w=380))):
                                           self.label_cover.set(img))
                self.task_queue.put_nowait(lambda:self.label_cover_text.grid_remove())
                self.task_queue.put_nowait(lambda img=BytesIO(biliapis.requester.get_content_bytes(biliapis.format_img(up['face'],w=50,h=50))):
                                           self.label_uploader_face.set(img))
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
                self.task_queue.put_nowait(lambda w=o_[1],img=BytesIO(biliapis.requester.get_content_bytes(biliapis.format_img(self.recommend[c_]['picture'],w=114,h=69))):
                                           w.set(img))
                self.task_queue.put_nowait(lambda w=o_[2],t=self.recommend[c_]['title']:self.set_text(w,text=t,lock=True))
                self.task_queue.put_nowait(lambda w=o_[3],t=self.recommend[c_]['uploader']['name']:w.configure(text=t))
                self.task_queue.put_nowait(lambda w=o_[4],t=self.recommend[c_]['bvid']:w.configure(text=t))
                #绑定tooltip
                self.task_queue.put_nowait(lambda w=o_[1]:o_.append(cusw.ToolTip(w,text='点击跳转到此视频')))
                self.task_queue.put_nowait(lambda w=o_[2],t=self.recommend[c_]['title']:o_.append(cusw.ToolTip(w,text=t)))
                self.task_queue.put_nowait(lambda w=o_[3],t='%s\nUID%s'%(self.recommend[c_]['uploader']['name'],self.recommend[c_]['uploader']['uid']):
                                           o_.append(cusw.ToolTip(w,text=t)))
                self.task_queue.put_nowait(lambda w=o_[4],t='%s\nav%s\n播放: %s\n弹幕: %s\n评论: %s'%(self.recommend[c_]['bvid'],
                                                                                                self.recommend[c_]['avid'],
                                                                                                self.recommend[c_]['stat']['view'],
                                                                                                self.recommend[c_]['stat']['danmaku'],
                                                                                                self.recommend[c_]['stat']['reply']):o_.append(cusw.ToolTip(w,text=t)))
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
                biliapis.video.get_detail(avid=self.abvid)
            else:
                biliapis.video.get_detail(bvid=self.abvid)
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
        self.status = False
        self.condition = None
        self.final_url = None
        
        self.label_imgshower = cusw.ImageLabel(self.window,width=300,height=300)
        self.label_imgshower.pack()
        self.label_text = tk.Label(self.window,text='未获取',font=('Microsoft YaHei UI',15))
        self.label_text.pack(pady=10)
        self.button_refresh = ttk.Button(self.window,text='刷新',state='disabled',command=self.fresh)
        self.button_refresh.pack()
        
        self.fresh()
        logging.info('LoginWindow Initialization Completed')
        self.window.wait_window(self.window)

    def fresh(self):
        self.button_refresh['state'] = 'disabled'
        self.label_text['text'] = '正在刷新'
        self.login_url,self.oauthkey = biliapis.login.get_login_url()
        self.label_imgshower.set(makeQrcode(self.login_url))
        self.start_autocheck()

    def start_autocheck(self):
        if not self.oauthkey:
            return
        res = biliapis.login.check_scan(self.oauthkey)
        self.status,self.final_url,self.condition = res
        self.label_text['text'] = {0:'登录成功',-1:'密钥错误',-2:'二维码已超时',-4:'使用B站手机客户端扫描此二维码',-5:'在手机上确认登录'}[self.condition]
        if self.condition == 0:
            cookiejar = biliapis.login.make_cookiejar(self.final_url)
            cookiejar.save(biliapis.requester.local_cookiejar_path)
            logging.debug('Cookie File saved to '+biliapis.requester.local_cookiejar_path)
            self.window.after(1000,self.close)
            return
        elif self.condition == -2:
            self.button_refresh['state'] = 'normal'
            self.label_imgshower.clear()
            return
        elif self.condition == -4 or self.condition == -5:
            self.window.after(2000,self.start_autocheck)
            return
            
    def close(self):
        self.window.destroy()

class PbpShower(Window):
    def __init__(self,cid):
        super().__init__('BiliTools - PBP Shower of cid{}'.format(cid),True,config['topmost'],config['alpha'])

        try:
            self.pbp_data = biliapis.video.get_pbp(cid)
        except biliapis.BiliError as e:
            msgbox.showerror('','BiliError Code {}: {}'.format(e.code,e.msg),parent=self.window)
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

        self.mainloop()

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
    def __init__(self,part_list,title='PartsChooser',columns=['分P名','长度','Cid','编码'],columns_widths=[200,70,90,100],master=None):
        self.return_values = [] #Selected Indexes
        super().__init__('BiliTools - '+title,True,config['topmost'],config['alpha'],master)
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
            self.tview_parts.column(column,width=columns_widths[i],minwidth=columns_widths[i]-20,anchor='w')
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
        self.mainloop()

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
        self.label_target_face = cusw.ImageLabel(self.frame_target,width=50,height=50)#用户头像
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

        self.mainloop()

    def load_data(self):
        self.loaded_page += 1
        self.data_pool += biliapis.other.get_blackroom(self.loaded_page)
        self.label_page_shower['text'] = '{}/{}'.format(self.page,len(self.data_pool))

    def load_img(self,page):
        if type(self.data_pool[page-1]['user']['face']) == str:#检查是否加载过, 加载过的则不再加载
            self.data_pool[page-1]['user']['face'] = BytesIO(biliapis.requester.get_content_bytes(biliapis.format_img(self.data_pool[page-1]['user']['face'],50,50)))
        self.task_queue.put_nowait(lambda:self.label_target_face.set(self.data_pool[page-1]['user']['face']))
        
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

class BangumiWindow(Window):
    def __init__(self,ssid=None,mdid=None,epid=None):
        super().__init__('BiliTools - Media',True,config['topmost'],config['alpha'])
        self.ids = {'ssid':ssid,'mdid':mdid,'epid':epid}
        if not ssid and not mdid and not epid:
            raise RuntimeError('You must choose one parameter between ssid, mdid and epid.')
        self.media_data = None

        #左侧
        self.frame_left = tk.Frame(self.window)
        self.frame_left.grid(column=0,row=0)
        #封面
        self.label_cover = cusw.ImageLabel(self.frame_left,width=285,height=380)
        self.label_cover.grid(column=0,row=0)
        #标题
        self.text_title = tk.Text(self.frame_left,bg='#f0f0f0',bd=0,height=1,width=46,state='disabled',font=('Microsoft YaHei UI',12,'bold'))
        self.text_title.grid(column=0,row=1,sticky='w')
        #IDs
        self.label_ssid = tk.Label(self.frame_left,text='SS-')
        self.label_ssid.grid(column=0,row=2,sticky='w')
        self.label_mdid = tk.Label(self.frame_left,text='MD-')
        self.label_mdid.grid(column=0,row=2,sticky='e',padx=10)
        #统计
        self.frame_stat = tk.LabelFrame(self.frame_left,text='统计')
        self.frame_stat.grid(column=0,row=3)
        tk.Label(self.frame_stat,text='播放:').grid(column=0,row=0,sticky='w')
        self.label_view = tk.Label(self.frame_stat,text='-')
        self.label_view.grid(column=1,row=0,sticky='w')
        tk.Label(self.frame_stat,text='投币:').grid(column=2,row=0,sticky='w')
        self.label_coin = tk.Label(self.frame_stat,text='-')
        self.label_coin.grid(column=3,row=0,sticky='w')
        tk.Label(self.frame_stat,text='收藏:').grid(column=0,row=1,sticky='w')
        self.label_collect = tk.Label(self.frame_stat,text='-')
        self.label_collect.grid(column=1,row=1,sticky='w')
        tk.Label(self.frame_stat,text='弹幕:').grid(column=2,row=1,sticky='w')
        self.label_danmaku = tk.Label(self.frame_stat,text='-')
        self.label_danmaku.grid(column=3,row=1,sticky='w')
        tk.Label(self.frame_stat,text='分享:').grid(column=0,row=2,sticky='w')
        self.label_share = tk.Label(self.frame_stat,text='-')
        self.label_share.grid(column=1,row=2,sticky='w')
        tk.Label(self.frame_stat,text='评论:').grid(column=2,row=2,sticky='w')
        self.label_reply = tk.Label(self.frame_stat,text='-')
        self.label_reply.grid(column=3,row=2,sticky='w')
        #操作区
        self.frame_optarea = tk.Frame(self.frame_left)
        self.frame_optarea.grid(column=0,row=4)
        self.button_view_on_browser = ttk.Button(self.frame_optarea,text='在浏览器中打开')
        self.button_view_on_browser.grid(column=0,row=0)
        #右侧
        self.frame_right = tk.Frame(self.window)
        self.frame_right.grid(column=1,row=0)
        #正片/番外展示器
        self.notebook_secshower = ttk.Notebook(self.frame_right)
        self.notebook_secshower.grid(column=0,row=0)
        self.section_tabs = [] #采用列表套列表的形式
        #简介
        tk.Label(self.frame_right,text='简介↓').grid(column=0,row=1,sticky='w')
        self.text_desc = scrolledtext.ScrolledText(self.frame_right,state='disabled',bg='#f0f0f0',bd=0,height=10,width=63)
        self.text_desc.grid(column=0,row=2,sticky='w')

        self.load_data()
        self.mainloop()

    def _add_section_tab(self,tabname,section_data,section_index=-1):
        #传入的section_data是个列表, 来源biliapis.media.get_info获得的剧集列表
        #section_index是整型, 为-1时是正片
        #索引值说明(缩进表示tk隶属关系):
        #0:Section数据
        #1:框架
        #   2:表格
        #   3:y滚动条
        #   4:x滚动条
        #   5:框架-操作
        #       6:按钮-下载选中项
        #       7:按钮-下载全部
        #       8:按钮-查看PBP
        #       9:下面那个复选框的boolvar
        #       10:复选框-是否只抽取音轨
        
        #框架
        self.section_tabs += [[section_data]]
        tab_index = len(self.section_tabs)-1
        self.section_tabs[-1] += [tk.Frame(self.notebook_secshower)]
        self.notebook_secshower.add(self.section_tabs[-1][1],text=tabname)
        #表格
        headings = ['标题','BvID','EpID']
        head_widths = [200,120,80]
        self.section_tabs[-1] += [ttk.Treeview(self.section_tabs[-1][1],show="headings",columns=tuple(['序号']+headings),height=15)]
        self.section_tabs[-1][2].grid(column=0,row=0)
        #初始化表头
        self.section_tabs[-1][2].column("序号", width=40,anchor='e') #序号一栏是固有的, 参见PartsChooser
        self.section_tabs[-1][2].heading("序号", text="序号",anchor='w')
        i = 0
        for h in headings:
            self.section_tabs[-1][2].column(h,width=head_widths[i],minwidth=head_widths[i]-50,anchor='w')
            self.section_tabs[-1][2].heading(h,text=h,anchor='w')
            i += 1
        #填充数据
        i = 0
        for item in section_data:
            i += 1
            self.section_tabs[-1][2].insert("","end",values=(str(i),item['title'],item['bvid'],str(item['epid'])))
        #滚动条
        self.section_tabs[-1] += [ttk.Scrollbar(self.section_tabs[-1][1],command=self.section_tabs[-1][2].yview,orient='vertical')]
        self.section_tabs[-1][3].grid(column=1,row=0,sticky='nsw')
        self.section_tabs[-1] += [ttk.Scrollbar(self.section_tabs[-1][1],command=self.section_tabs[-1][2].xview,orient='horizontal')]
        self.section_tabs[-1][4].grid(column=0,row=1,sticky='wen')
        self.section_tabs[-1][2].configure(yscrollcommand=self.section_tabs[-1][3].set,xscrollcommand=self.section_tabs[-1][4].set)
        #操作区
        self.section_tabs[-1] += [tk.Frame(self.section_tabs[-1][1])]
        self.section_tabs[-1][5].grid(column=0,row=2,sticky='w')
        self.section_tabs[-1] += [ttk.Button(self.section_tabs[-1][5],text='下载选中项',command=lambda tbi=tab_index,sei=section_index:self._download_func(tbi,sei,False))]
        self.section_tabs[-1][6].grid(column=0,row=1)
        self.section_tabs[-1] += [ttk.Button(self.section_tabs[-1][5],text='下载全部',command=lambda tbi=tab_index,sei=section_index:self._download_func(tbi,sei,True))]
        self.section_tabs[-1][7].grid(column=1,row=1)
        self.section_tabs[-1] += [ttk.Button(self.section_tabs[-1][5],text='查看选中项的PBP',command=lambda tbi=tab_index,sei=section_index:self._see_pbp(tbi,sei))] #
        self.section_tabs[-1][8].grid(column=2,row=1)
        self.section_tabs[-1] += [tk.BooleanVar(self.section_tabs[-1][5],False)]
        self.section_tabs[-1] += [ttk.Checkbutton(self.section_tabs[-1][5],text='仅抽取音轨',onvalue=True,offvalue=False,variable=self.section_tabs[-1][9])]
        self.section_tabs[-1][10].grid(column=0,row=0)

    def _see_pbp(self,tab_index,section_index=-1):
        if not self.media_data:
            raise RuntimeError('Not loaded yet.')
        #此函数供section_tabs内的按钮调用
        ep_indexes = []
        for item in self.section_tabs[tab_index][2].selection():
            ep_indexes.append(int(self.section_tabs[tab_index][2].item(item,"values")[0])-1)
        if not ep_indexes:
            msgbox.showwarning('','你什么都没选中',parent=self.window)
            return
        if len(ep_indexes) > 1:
            msgbox.showwarning('','你选中了多项, 但程序只会为你展示选中的第一项的弹幕增量趋势.',parent=self.window)
        cids = [[o['cid'] for o in i['episodes']] for i in self.media_data['sections']]+[[i['cid'] for i in self.media_data['episodes']]]
        PbpShower(cids[section_index][ep_indexes[0]])

    def _download_func(self,tab_index,section_index=-1,download_all=False):
        if not self.media_data:
            raise RuntimeError('Not loaded yet.')
        #此函数供section_tabs内的按钮调用
        ep_indexes = []
        if download_all:
            pass
        else:
            for item in self.section_tabs[tab_index][2].selection():
                ep_indexes.append(int(self.section_tabs[tab_index][2].item(item,"values")[0])-1)
            if not ep_indexes:
                msgbox.showwarning('','你什么都没选中',parent=self.window)
                return
        path = filedialog.askdirectory(title='设定输出目录',parent=self.window)
        if path:
            if section_index == -1:
                download_manager.task_receiver('video',path=path,data=self.media_data,ssid=self.media_data['ssid'],
                                               audiostream_only=self.section_tabs[tab_index][9].get(),epindexes=ep_indexes)
            else:
                download_manager.task_receiver('video',path=path,data=self.media_data,ssid=self.media_data['ssid'],
                                               audiostream_only=self.section_tabs[tab_index][9].get(),epindexes=ep_indexes,section_index=section_index)

    def load_data(self):
        def tmp():
            try:
                self.media_data = biliapis.media.get_detail(**self.ids)
            except biliapis.BiliError as e:
                if e.code == -404:
                    self.task_queue.put_nowait(lambda:msgbox.showerror('','番剧/影视 不存在',parent=self.window))
                    self.task_queue.put_nowait(self.close)
                    return
            del self.ids
            #统计数据
            stat = self.media_data['stat']
            def fill_stat(stat_data):
                self.label_view['text'] = str(stat_data['view'])
                self.label_coin['text'] = str(stat_data['coin'])
                self.label_collect['text'] = str(stat_data['collect'])
                self.label_danmaku['text'] = str(stat_data['danmaku'])
                self.label_share['text'] = str(stat_data['share'])
                self.label_reply['text'] = str(stat_data['reply'])
            self.task_queue.put_nowait(lambda s=stat:fill_stat(s))
            #图像
            def load_img():
                self.task_queue.put_nowait(lambda img=BytesIO(biliapis.requester.get_content_bytes(biliapis.format_img(self.media_data['cover'],h=380))):
                                           self.label_cover.set(img))
            start_new_thread(load_img)
            #Section data
            if self.media_data['episodes']:
                self.task_queue.put_nowait(lambda eps=self.media_data['episodes']:self._add_section_tab('正片',eps,-1))
            i = 0
            for section in self.media_data['sections']:
                self.task_queue.put_nowait(lambda name=section['title'],eps=section['episodes'],index=i:self._add_section_tab(name,eps,index))
                i += 1
            #简介
            self.task_queue.put_nowait(lambda desc=self.media_data['description']:self.set_text(self.text_desc,text=desc,lock=True))
            #标题
            self.task_queue.put_nowait(lambda title=self.media_data['title']:self.set_text(self.text_title,lock=True,text=title))
            #IDs
            self.task_queue.put_nowait(lambda ssid=self.media_data['ssid']:self.label_ssid.configure(text='SS{}'.format(ssid)))
            self.task_queue.put_nowait(lambda mdid=self.media_data['mdid']:self.label_mdid.configure(text='MD{}'.format(mdid)))
            #打开浏览器的按钮
            self.task_queue.put_nowait(lambda mdid=self.media_data['mdid']:self.button_view_on_browser.configure(command=lambda mdid=mdid:webbrowser.open('https://www.bilibili.com/bangumi/media/md{}/'.format(mdid))))
        start_new_thread(tmp)

class MangaViewer_Rolling(Window): #技术上遇到问题, 搁置
    def __init__(self,epid):
        super().__init__('BiliTools - MangaViewer',True,config['topmost'],config['alpha'])

        self.epid = epid
        self.episode_info = None #用来存放请求数据(章节的)
        self.image_index = None
        self.image_urls = [] #用来存放拼接Token之后的Url, 一下就加载好了所以不用占位
        self.image_pool = [] #用来存放BytesIO, 没加载好的用None占位
        self.widget_list = [] #用来存放ImageLabel, 不用占位

        #控制台占300px宽,500px高
        self.console_width = 300
        self.window_width = 800
        self.window_height = 600
        
        self.window.geometry('%sx%s'%(self.window_width,self.window_height))
        self.window.minsize(self.console_width+100,self.window_height-100)
        self.window.resizable(height=True,width=True)

        self.shower_width = self.window_width-self.console_width

        self.shower = cusw.VerticalScrolledFrame(self.window,height=self.window_height)
        self.shower.grid(column=0,row=0)
        self.frame_shower = self.shower.inner_frame
        
        self.frame_console = tk.Frame(self.window)
        self.frame_console.grid(column=1,row=0)

        self._init_data()

    def _init_data(self):
        def tmp():
            self.episode_info = biliapis.manga.get_episode_info(self.epid)
            self.image_index = biliapis.manga.get_episode_image_index(self.epid)
            self.image_urls = [
                i['url']+'?token='+i['token'] for i in biliapis.manga.get_episode_image_token(
                    *['{}@{}w.jpg'.format(i['path'],i['width']) for i in self.image_index['images']]
                    )
                ]
            self.image_pool = [None]*len(self.image_urls)
            self.task_queue.put_nowait(lambda ii=self.image_index:self._prepare_shower_widget(ii))
            self.task_queue.put_nowait(lambda:self.window.bind('<Configure>',self._resize))
            self.task_queue.put_nowait(self._load_image)
        start_new_thread(tmp)

    def _load_image(self):
        def tmp():
            for i in range(len(self.image_pool)):
                if not self.image_pool[i]:
                    self.image_pool[i] = BytesIO(biliapis.requester.get_content_bytes(self.image_urls[i]))
                    self.task_queue.put_nowait(lambda index=i:self.widget_list[index].set(self.image_pool[index]))
        start_new_thread(tmp)
            
    def _prepare_shower_widget(self,image_index): #要在_resize第一次调用前调用, 并且要由_init_data调用
        for i in range(len(image_index['images'])):
            scale = self.shower_width/image_index['images'][i]['width']
            self.widget_list.append(cusw.ImageLabel(self.frame_shower,width=int(image_index['images'][i]['width']*scale),
                                                    height=int(image_index['images'][i]['height']*scale),bd=0))
            self.widget_list[-1].grid(column=0,row=i)
            
    def _resize(self,event=None):
        h = self.window.winfo_height()
        w = self.window.winfo_width()
        self.shower.set_height(h)
        self.shower_width = w-self.console_width
        if w != self.window_width:
            self.shower.scroll_to_top()
            for i in range(len(self.widget_list)):
                tw = self.shower_width
                scale = tw/self.image_index['images'][i]['width']
                th = int(self.image_index['images'][i]['height']*scale)
                self.widget_list[i].set(width=tw,height=th)
        self.window_height = h
        self.window_width = w
        
class MangaViewer_PageTurning(Window):
    def __init__(self,epid):
        super().__init__('BiliTools - MangaViewer',True,config['topmost'],config['alpha'])

        self.episode_info = None
        self.image_urls = []
        self.image_pool = [] #放BytesIO对象

        self.current_page = 1 #没有下标, 转换成索引时要-1
        self.total_pages = 0 #总页数, 由_init_data加载
        self.frame_shower = tk.Frame(self.window)
        self.frame_shower.grid(column=0,row=0)

        #暂时搁置

#供SearchWindow使用
#相当于一个当成组件用的窗口吧
class _CommonVideoSearchShower(cusw.VerticalScrolledFrame):
    def __init__(self,master,task_queue,height=400):
        #需要传入父组件的task_queue以执行多线程任务
        super().__init__(master=master,height=height)
        self.kws = None
        self.page = 1
        self.total_page = 1
        self.task_queue = task_queue
        columnnum = 5
        rownum = 4
        self.page_size = columnnum*rownum #此值必须为20
        self.sort_methods = {
            '综合排序':'totalrank',
            '最多点击':'click',
            '最新发布':'pubdate',
            '最多弹幕':'dm',
            '最多收藏':'stow',
            '最多评论':'scores'
            }
        self.sort_methods_ = {v: k for k, v in self.sort_methods.items()}
        self.duration_methods = {
            'All':0,
            '0-10':1,
            '10-30':2,
            '30-60':3,
            '60+':4
            }
        self.duration_methods_ = {v: k for k, v in self.duration_methods.items()}
        
        #过滤姬
        #排序方式
        self.frame_filter = tk.Frame(self.inner_frame)
        self.frame_filter.grid(column=0,row=0,sticky='w')
        tk.Label(self.frame_filter,text='排序方式:').grid(column=0,row=0,sticky='w')
        self.strvar_sort = tk.StringVar(value='totalrank')
        self.om_sort = ttk.OptionMenu(self.frame_filter,self.strvar_sort,'综合排序',*list(self.sort_methods.keys()))
        self.om_sort.grid(column=1,row=0,sticky='w')
        #时长筛选
        tk.Label(self.frame_filter,text='\t时长(分钟):').grid(column=2,row=0,sticky='w')
        self.strvar_duration = tk.StringVar(value='All')
        self.om_duration = ttk.OptionMenu(self.frame_filter,self.strvar_duration,'All',*list(self.duration_methods.keys()))
        self.om_duration.grid(column=3,row=0,sticky='w')
        #刷新按钮
        self.button_refresh = ttk.Button(self.frame_filter,text='刷新',command=self.refresh)
        self.button_refresh.grid(column=0,row=1,columnspan=2,sticky='w')
        #分区筛选
        tk.Label(self.frame_filter,text='\t分区:').grid(column=4,row=0)
        self.strvar_main_zone = tk.StringVar(value='All')
        self.om_main_zone = ttk.OptionMenu(self.frame_filter,self.strvar_main_zone,'All','All',*list(biliapis.bilicodes.video_zone_main.values()),command=self._update_zone_om)
        self.om_main_zone.grid(column=5,row=0)
        self.strvar_child_zone = tk.StringVar(value='All')
        self.om_child_zone = ttk.OptionMenu(self.frame_filter,self.strvar_child_zone,'All','All',*list(biliapis.bilicodes.video_zone_child.values()))
        self.om_child_zone.grid(column=6,row=0)
        self.om_child_zone.grid_remove()
        self.zone = {v:k for k,v in biliapis.bilicodes.video_zone_main.items()}
        self.zone.update({v:k for k,v in biliapis.bilicodes.video_zone_child.items()})
        
        #统计姬
        self.frame_stat = tk.Frame(self.inner_frame)
        self.frame_stat.grid(column=1,row=0,sticky='e',padx=10)
        self.label_searchtime = tk.Label(self.frame_stat,text='搜索用时: -s')
        self.label_searchtime.grid(column=0,row=0,sticky='w')
        self.label_searchcount = tk.Label(self.frame_stat,text='共有 - 个结果')
        self.label_searchcount.grid(column=0,row=1,sticky='w')

        #分鸽线 用来撑开框架w
        ttk.Separator(self.inner_frame,orient='horizontal').grid(ipadx=550,sticky='we',column=0,row=1,columnspan=2)
        
        self.frame_result = tk.Frame(self.inner_frame)
        self.frame_result.grid(column=0,row=2,columnspan=2)
        self._bind_scroll_event(self.frame_result)
        self.tk_objs = []
        for y in range(rownum):
            for x in range(columnnum):
                l = []
                #索引说明
                #0:框架
                #1:封面展示器
                #2:时长标签
                #3:标题文本
                #4:详细信息框架
                #5:播放数标签
                #6:发布时间标签
                #7:up主标签
                #8:tooltip
                l += [tk.Frame(self.frame_result)]
                l[0].grid(column=x,row=y,padx=5,pady=5)
                l[0].grid_remove()
                l += [cusw.ImageLabel(l[0],width=200,height=122)]
                l[1].grid(column=0,row=0)
                l += [tk.Label(l[0],text='--:--',bg='#000000',fg='#ffffff')]
                l[2].grid(column=0,row=0,sticky='se')
                #
                l += [tk.Text(l[0],bg='#f0f0f0',bd=0,height=2,width=28,state='disabled')]
                l[3].grid(column=0,row=1)
                l += [tk.Frame(l[0])]
                l[4].grid(column=0,row=2,sticky='we')
                l += [tk.Label(l[4],text='播放数: -')]
                l[5].grid(column=0,row=0,sticky='w')
                l += [tk.Label(l[4],text='发布时间: ----------')]
                l[6].grid(column=0,row=1,sticky='w')
                l += [tk.Label(l[4],text='UP: -')]
                l[7].grid(column=0,row=2,sticky='w')
                for w in l:
                    self._bind_scroll_event(w)
                l += [cusw.ToolTip(l[0])]
                self.tk_objs.append(l)
        #翻页姬
        self.frame_pgturner = tk.Frame(self.inner_frame)
        self.frame_pgturner.grid(column=0,row=3,columnspan=2)
        self.frame_pgturner.grid_remove()
        self.button_last = ttk.Button(self.frame_pgturner,text='上一页',command=lambda:self.turn_page(self.page-1))
        self.button_last.grid(column=0,row=0)
        self.label_page = tk.Label(self.frame_pgturner,text='-/- 页')
        self.label_page.grid(column=1,row=0)
        self.button_next = ttk.Button(self.frame_pgturner,text='下一页',command=lambda:self.turn_page(self.page+1))
        self.button_next.grid(column=2,row=0)
        self.entry_page = ttk.Entry(self.frame_pgturner,exportselection=0,width=10)
        self.entry_page.grid(column=0,row=1,columnspan=2,sticky='e')
        self.button_tp = ttk.Button(self.frame_pgturner,text='跳页',command=lambda:self.turn_page(int(self.entry_page.get())))
        self.button_tp.grid(column=2,row=1)

    def _fast_download(self,bvid,audiostream_only=False):
        path = filedialog.askdirectory(title='下载到',parent=self.master)
        if path:
            download_manager.task_receiver('video',path,bvid=bvid,audiostream_only=audiostream_only)
        
    def _right_click(self,event,bvid):
        x = event.x_root
        y = event.y_root
        menu = tk.Menu(self.inner_frame,tearoff=False)
        menu.add_command(label='跳转到该视频',command=lambda bvid=bvid:self.jump_by_bvid(bvid))
        menu.add_command(label='下载该视频的所有分P',command=lambda bvid=bvid:self._fast_download(bvid=bvid))
        menu.add_command(label='抽取该视频的所有分P的音轨',command=lambda bvid=bvid:self._fast_download(bvid=bvid,audiostream_only=True))
        menu.post(x,y)

    def _update_zone_om(self,main_var=None):
        if not main_var:
            main_var = self.strvar_main_zone.get()
        if main_var == 'All':
            self.om_child_zone.set_menu('All','All')
            self.om_child_zone.grid_remove()
        else:
            self.om_child_zone.set_menu('All','All',*[biliapis.bilicodes.video_zone_child[tid] for tid in biliapis.bilicodes.video_zone_relation[self.zone[main_var]]])
            self.om_child_zone.grid()
        self.strvar_child_zone.set('All')

    def _get_zone(self,main_var=None):
        if not main_var:
            main_var = self.strvar_main_zone.get()
        child_var = self.strvar_child_zone.get()
        if main_var == 'All':
            return 0
        else:
            if child_var == 'All':
                return self.zone[main_var]
            else:
                return self.zone[child_var]

    def jump_by_bvid(self,bvid):
        w = CommonVideoWindow(bvid)

    def search(self,*kws,page=1):
        if not kws:
            return
        def tmp(duration,sort,zone,page,kws):
            try:
                data = biliapis.video.search(*kws,page=page,order=self.sort_methods[sort],zone=zone,duration=self.duration_methods[duration])
            except biliapis.BiliError as e:
                self.task_queue.put_nowait(lambda e=e:msgbox.showerror('','BiliError code {}:\n{}'.format(e.code,e.msg),parent=self.master))
                return
            except Exception as e:
                self.task_queue.put_nowait(lambda e=e:msgbox.showerror('',str(e),parent=self.master))
                if development_mode:
                    raise e
                return
            else:
                self.task_queue.put_nowait(lambda s=sort:self.om_sort.set_menu(s,*list(self.sort_methods.keys())))
                self.task_queue.put_nowait(lambda d=duration:self.om_duration.set_menu(d,*list(self.duration_methods.keys())))
                self.task_queue.put_nowait(lambda p=page,tp=data['total_pages']:self.label_page.configure(text='{}/{}'.format(p,tp)))
                self.task_queue.put_nowait(lambda t=data['time_cost']:self.label_searchtime.configure(text=f'搜索用时: {t}s'))
                self.task_queue.put_nowait(lambda c=data['result_count']:self.label_searchcount.configure(text=f'共有 {c} 个结果'))
                self.total_page = data['total_pages']
                self.page = page
                self.kws = kws
                def fill_data(widgetlist,dataobj):
                    #封面加载交给imgloader
                    widgetlist[1].bind('<Button-1>',lambda event,bvid=dataobj['bvid']:self.jump_by_bvid(bvid=bvid))
                    widgetlist[1].bind('<Button-3>',lambda event,bvid=dataobj['bvid']:self._right_click(event=event,bvid=bvid))
                    #时长
                    widgetlist[2]['text'] = dataobj['duration']
                    #标题
                    widgetlist[3]['state'] = 'normal'
                    widgetlist[3].delete(1.0,'end')
                    widgetlist[3].insert('end',dataobj['title'])
                    widgetlist[3]['state'] = 'disabled'
                    #播放数
                    widgetlist[5]['text'] = '播放数: '+biliapis.convert_number(dataobj['stat']['view'])
                    #发布时间
                    widgetlist[6]['text'] = '发布时间: '+time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(dataobj['date_publish']))
                    #up主
                    widgetlist[7]['text'] = 'UP: '+dataobj['uploader']['name']
                    #tooltip
                    widgetlist[8].change_text('{title}\n{bvid}\nUP主: {uploader[name]}\n'\
                                              '播放: {stat[view]}\n弹幕: {stat[danmaku]}\n点击封面跳转详情页.'.format(**dataobj))
                    
                def clear_data(widgetlist):
                    widgetlist[1].clear()
                    widgetlist[1].unbind('<Button-1>')
                    widgetlist[3]['state'] = 'normal'
                    widgetlist[3].delete(1.0,'end')
                    widgetlist[3]['state'] = 'disabled'
                    widgetlist[5]['text'] = '播放数: -'
                    widgetlist[6]['text'] = '发布时间: ----------'
                    widgetlist[7]['text'] = 'UP: -'
                    widgetlist[8].change_text(None)
                
                if data['result']:
                    self.task_queue.put_nowait(lambda:self.frame_pgturner.grid())
                    for i in range(len(self.tk_objs)):
                        w = self.tk_objs[i]
                        self.task_queue.put_nowait(lambda wl=w:clear_data(wl))
                        if i <= len(data['result'])-1:
                            d = data['result'][i]
                            self.task_queue.put_nowait(lambda wl=w:wl[0].grid())
                            start_new_thread(lambda url=d['cover'],widget=w[1]:
                                             (self.task_queue.put_nowait(lambda widget=widget,img=BytesIO(biliapis.requester.get_content_bytes(biliapis.format_img(url,w=200))):
                                                                         widget.set(img))))
                            self.task_queue.put_nowait(lambda wl=w,do=d:fill_data(wl,do))
                        else:
                            self.task_queue.put_nowait(lambda wl=w:wl[0].grid_remove())
                else:
                    self.task_queue.put_nowait(lambda:self.frame_pgturner.grid_remove())
                    self.task_queue.put_nowait(lambda:msgbox.showwarning('','没有搜索结果',parent=self.master))
                    
        kwargs = {
            'duration':self.strvar_duration.get(),
            'sort':self.strvar_sort.get(),
            'zone':self._get_zone(),
            'page':page,
            'kws':kws
            }
        start_new_thread(tmp,kwargs=kwargs)

    def refresh(self):
        if self.kws:
            self.search(*self.kws,page=1)

    def turn_page(self,page):
        if self.kws:
            if page > self.total_page or page < 1:
                pass
            else:
                self.search(*self.kws,page=page)
            self.scroll_to_top()
#好麻烦的说...
class _BangumiSearchShower(cusw.VerticalScrolledFrame):
    def __init__(self,master,task_queue,height=400):
        #需要传入父组件的task_queue以执行多线程任务
        super().__init__(master=master,height=height)
        self.kws = None
        self.page = 1
        self.total_page = 1
        self.task_queue = task_queue
        columnnum = 5
        rownum = 4
        self.page_size = columnnum*rownum #此值必须为20

class SearchWindow(Window):
    def __init__(self,*init_kws):
        #Notebook.children[Notebook.select().split('.')[-1]] #可以用这个来返回被选中的tab的框架的tk对象
        #亦可以通过 tab_frame_signs.index(Notebook.select()) 来确定选中了哪个tab, 这个索引值同时还是tab_id

        #搜索类型:
        #0 - 普通视频
        #1 - 番
        #2 - 用户
        #(待扩充)

        super().__init__('BiliTools - Search',True,config['topmost'],config['alpha'])
        #输入区
        self.frame_input = tk.Frame(self.window)
        self.frame_input.grid(column=0,row=0)
        self.entry = ttk.Entry(self.frame_input,width=40)
        self.entry.grid(column=0,row=0,pady=10)
        self.entry.bind('<Return>',lambda event=None:self.search())
        self.button_start = ttk.Button(self.frame_input,text='搜索',width=5)
        self.button_start.grid(column=1,row=0)
        ttk.Button(self.frame_input,text='粘贴',command=lambda:self.set_entry(self.entry,text=self.entry.clipboard_get()),width=5).grid(column=2,row=0)
        ttk.Button(self.frame_input,text='清空',command=lambda:self.entry.delete(0,'end'),width=5).grid(column=3,row=0)
        #输出区
        self.nb = ttk.Notebook(self.window)
        self.nb.grid(column=0,row=1)
        self.button_start['command'] = self.search
        #普通视频
        self.frame_common_video = _CommonVideoSearchShower(self.nb,self.task_queue,height=500)
        self.nb.add(self.frame_common_video,text='普通视频')

        if init_kws:
            self.search(*init_kws)
            self.entry.insert('end',' '.join(init_kws))
        self.mainloop()

    def search(self,*kws):
        if not kws:
            kws = self.entry.get().strip().split()
        if kws: 
            target = self.nb.children[self.nb.select().split('.')[-1]]
            target.search(*kws)
        else:
            msgbox.showwarning('','关键字列表为空.',parent=self.window)

    def set_nb_state(self,nb,state='normal'):
        for i in range(len(nb.tabs())):
            nb.tab(i,state=state)


if (__name__ == '__main__' and not development_mode) or '-debug' in sys.argv:
    load_config()
    logging.info('Program Running.')
    w = MainWindow()    
else:
    dump_config()
