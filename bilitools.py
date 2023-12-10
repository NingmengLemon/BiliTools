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
from typing import Any
import webbrowser
import json
import base64
import subprocess
import copy
import functools
import typing

import qrcode
import danmaku2ass
import lxml

import biliapis
from biliapis import bilicodes
import custom_widgets as cusw
from basic_window import Window
import imglib
import ffdriver
from videoshot_handler import VideoShotHandler

from configuration import version, inner_data_path
from configuration import config_path
from configuration import default_config as config
from configuration import development_mode
import textlib

#注意：
#为了页面美观，将 Button/Radiobutton/Checkbutton/Entry 的母模块从tk换成ttk
#↑步入现代风（并不


if not os.path.exists(inner_data_path):
    os.mkdir(inner_data_path)
biliapis.requester.inner_data_path = inner_data_path

biliapis.requester.filter_emoji = config['filter_emoji']
# 加载关于信息
about_info = textlib.about_info.format(version=version)
# 加载Cookies
biliapis.requester.load_local_cookies()

rgb2hex = lambda r,g,b:'#{:0>6s}'.format(str(hex((r<<16)+(g<<8)+b))[2:])

def remove_repeat(l):
    l_ = []
    for i in l:
        if i not in l_:
            l_.append(i)
    return l_

def apply_proxy_config(): # also used as refresher
    if config['proxy']['enabled']:
        if config['proxy']['port'] == None:
            biliapis.requester.proxy = config['proxy']['host']
        else:
            biliapis.requester.proxy = '%s:%s'%(config['proxy']['host'],config['proxy']['port'])
        if config['proxy']['use_system_proxy']:
            biliapis.requester.global_config(use_proxy=None)
        else:
            biliapis.requester.global_config(use_proxy=True)
    else:
        biliapis.requester.proxy = None
        biliapis.requester.global_config(use_proxy=False)

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
                                font_face='黑体',font_size=40.0,duration_marquee=7.0,duration_still=10.0,)
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

def makeQrcode(data) -> BytesIO:
    qr = qrcode.QRCode()
    qr.add_data(data)
    img = qr.make_image()
    a = BytesIO()
    img.save(a,'png')
    return a

def make_quality_regulation(qtext):
    targetlist = list(bilicodes.stream_dash_video_quality.keys())
    index = list(bilicodes.stream_dash_video_quality.values()).index(qtext)
    return list(reversed(targetlist[:index+1]))

class DownloadManager(object):
    def __init__(self):
        self.window = None
        self.task_queue = queue.Queue()
        self.refresh_loop_schedule = None
        self.task_receiving_lock = threading.Lock()
        self.table_edit_lock = threading.Lock() # 尝试添加了这个, 希望能阻止 not in mainloop 报错
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
        self.table_columns_widths = [40,200,180,100,70,70,100,60,100,150]
        
        self.table_display_list = []    # 多维列表注意, 对应Treeview的内容, 每项格式见table_columns
        self.data_objs = []             # 对应每个下载项的数据包, 每项格式:[序号(整型),类型(字符串,video/audio/common/manga),选项(字典,包含从task_receiver传入的除源以外的**args)]
        self.thread_counter = 0         # 线程计数器
        self.failed_indexes = []        # 存放失败任务在data_objs中的索引
        self.running_indexes = []       # 存放运行中的任务在data_objs中的索引
        self.done_indexes = []          # 存放已完成任务在data_objs中的索引
        start_new_thread(self.auto_thread_starter) # 启动线程启动器
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
                with self.table_edit_lock:
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
        with self.table_edit_lock:
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

    def match_dash_quality(self,videostreams,audiostreams,regulation=config['download']['video']['quality']):
        videostream = None
        audiostream = None
        #Video
        vqs = []
        for vstream in videostreams:
            vqs.append(vstream['quality'])
        if regulation:
            regulation = make_quality_regulation(bilicodes.stream_dash_video_quality[regulation])
            res = None
            for vq in regulation:
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
        if bilicodes.stream_dash_audio_quality_["Flac"] in aqs and config['download']['video']['allow_flac']: 
            # flac 不是音质代码中数值最高的那个, 所以要手动匹配
            audiostream = audiostreams[aqs.index(bilicodes.stream_dash_audio_quality_["Flac"])]
        else:
            audiostream = audiostreams[aqs.index(max(aqs))]
        return videostream,audiostream

    def choose_subtitle_lang(self,bccdata,regulation=config['download']['video']['subtitle_lang_regulation']):
        if bccdata:
            if len(bccdata) == 1:
                return bccdata[0]
            else:
                abbs = [sub['lang_abb'] for sub in bccdata]
                for reg in regulation:
                    if reg in abbs:
                        return bccdata[abbs.index(reg)]
                return bccdata[0]
        else:
            return None

    def _edit_display_list(self,index,colname,var): #供download_thread调用
        with self.table_edit_lock:
            self.table_display_list[index][list(self.table_columns.keys()).index(colname)] = var

    def _common_download_thread(self,index,url,filename,path,**trash):
        #跟下面辣两个函数差不多, 流程最简单, 然而这个函数并不能被用户使用...
        self.thread_counter += 1
        self.running_indexes.append(index)
        try:
            self._edit_display_list(index,'status','准备下载')
            session = biliapis.requester.download_yield(url,filename,path)
            for donesize,totalsize,percent in session:
                self._edit_display_list(index,'status','下载中 - {}%'.format(percent))
            self._edit_display_list(index,'size',biliapis.requester.convert_size(totalsize))
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
            if path.endswith('.'):
                path = path + '_'
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

    def _audio_download_thread(self,index,auid,path,audio_format='mp3',lyrics=True,data=None,**trash):
        #跟下面辣个函数差不多, 流程稍微简单些
        self.thread_counter += 1
        self.running_indexes.append(index)
        try:
            #收集信息
            self._edit_display_list(index,'status','收集信息')
            if data:
                audio_info = data
            else:
                audio_info = biliapis.audio.get_info(auid) #因为外面套了一层try所以不用做错误处理
            self._edit_display_list(index,'length',biliapis.second_to_time(audio_info['length']))
            self._edit_display_list(index,'title',audio_info['title'])
            self._edit_display_list(index,'target','Auid{}'.format(auid))
            #取流
            self._edit_display_list(index,'status','正在取流')
            stream = biliapis.stream.get_audio_stream(auid)
            self._edit_display_list(index,'quality',stream['quality'])
            #下载
            tmp_filename = replaceChr('{}_{}.aac'.format(auid,stream['quality_id']))
            final_filename = replaceChr('{}_{}'.format(audio_info['title'],stream['quality']))#文件名格式编辑在这里, 不带后缀名
            lyrics_filename = replaceChr('{}_{}.lrc'.format(audio_info['title'],stream['quality']))
            if not os.path.exists(os.path.join(path,lyrics_filename)) and lyrics:
                self._edit_display_list(index,'status','获取歌词')
                lrcdata = biliapis.audio.get_lyrics(auid)
                if lrcdata == 'Fatal: API error':
                    pass
                else:
                    with open(os.path.join(path,lyrics_filename),'w+',encoding='utf-8',errors='ignore') as f:
                        f.write(lrcdata)
            if os.path.exists(os.path.join(path,final_filename+'.'+audio_format)):
                self._edit_display_list(index,'status','跳过 - 文件已存在: '+final_filename)
                self._edit_display_list(index,'size',biliapis.requester.convert_size(os.path.getsize(os.path.join(path,final_filename+'.'+audio_format))))
            else:
                session = biliapis.requester.download_yield(stream['url'],tmp_filename,path)
                for donesize,totalsize,percent in session:
                    self._edit_display_list(index,'status','下载中 - {}%'.format(percent))
                self._edit_display_list(index,'size',biliapis.requester.convert_size(totalsize))
                #进一步处理
                if audio_format and audio_format not in ['aac','copy']:
                    self._edit_display_list(index,'status','转码')
                    ffdriver.convert_audio(os.path.join(path,tmp_filename),os.path.join(path,final_filename),audio_format,stream['quality'].lower())
                    self._edit_display_list(index,'size',biliapis.requester.convert_size(os.path.getsize(os.path.join(path,final_filename+'.'+audio_format))))
                    try:
                        os.remove(os.path.join(path,tmp_filename))
                    except:
                        pass
                else:
                    os.rename(os.path.join(path,tmp_filename),os.path.join(path,final_filename)+'.aac')
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

    def _video_download_thread(self,index,cid,bvid,title,path,audio_format='mp3',audiostream_only=False,quality=None,subtitle=True,danmaku=False,
                               convert_danmaku=True,subtitle_regulation=config['download']['video']['subtitle_lang_regulation'],**trash):
        # 放在子线程里运行
        # 此函数被包装为lambda函数后放入task_queue中排队, 由auto_thread_starter取出并开启线程
        # 此处index为task_receiver为其分配的在tabled_display_list中的索引
        self.thread_counter += 1
        self.running_indexes.append(index)
        try:
            audio_format = audio_format.lower()
            self._edit_display_list(index,'status','正在取流')
            stream_data = biliapis.stream.get_video_stream_dash(cid,bvid=bvid,hdr=True,_4k=True,dolby_vision=True,_8k=True)
            self._edit_display_list(index,'length',biliapis.second_to_time(stream_data['length']))
            vstream,astream = self.match_dash_quality(stream_data['video'],stream_data['audio'],quality)
            if audiostream_only:
                self._edit_display_list(index,'quality',bilicodes.stream_dash_audio_quality[astream['quality']])
                self._edit_display_list(index,'mode','音轨抽取')
            else:
                self._edit_display_list(index,'quality',bilicodes.stream_dash_video_quality[vstream['quality']]+'/'+\
                                        bilicodes.stream_dash_audio_quality[astream['quality']])
                self._edit_display_list(index,'mode','视频下载')
            #生成文件名
            tmpname_audio = '{}_{}_audiostream.aac'.format(bvid,cid)
            tmpname_video = '{}_{}_{}_videostream.avc'.format(bvid,cid,vstream['quality'])
            if astream['quality'] == 30251:
                final_filename = replaceChr('{}_{}.mkv'.format(title,bilicodes.stream_dash_video_quality[vstream['quality']]))#标题由task_receiver生成
                audio_format = bilicodes.stream_dash_audio_quality[astream['quality']].lower()
            else:
                final_filename = replaceChr('{}_{}.mp4'.format(title,bilicodes.stream_dash_video_quality[vstream['quality']]))#标题由task_receiver生成
            final_filename_audio_only = replaceChr('{}_{}'.format(title,bilicodes.stream_dash_audio_quality[astream['quality']]))#音频抽取不带后缀名
            #字幕
            is_sbt_downloaded = False
            subtitle_filename = replaceChr('{}_{}.srt'.format(title,bilicodes.stream_dash_video_quality[vstream['quality']]))#字幕文件名与视频文件保持一致
            if subtitle and not audiostream_only:
                self._edit_display_list(index,'status','获取字幕')
                bccdata = self.choose_subtitle_lang(biliapis.subtitle.get_bcc(cid,bvid=bvid,allow_ai=config['download']['video']['allow_ai_subtitle']),subtitle_regulation)
                if bccdata:
                    bccdata = json.loads(biliapis.requester.get_content_str(bccdata['url']))
                    srtdata = biliapis.subtitle.bcc_to_srt(bccdata)
                    with open(os.path.join(path,subtitle_filename),'w+',encoding='utf-8',errors='ignore') as f:
                        f.write(srtdata)
                    is_sbt_downloaded = True
            #弹幕
            danmaku_filename = replaceChr('{}_{}.xml'.format(title,bilicodes.stream_dash_video_quality[vstream['quality']]))
            if danmaku and not audiostream_only:
                self._edit_display_list(index,'status','获取弹幕')
                xmlstr = biliapis.danmaku.get_xmlstr(cid)
                self._edit_display_list(index,'status','过滤弹幕')
                xmlstr = biliapis.danmaku.filter(xmlstr,**config['download']['video']['danmaku_filter'])
                with open(os.path.join(path,danmaku_filename),'w+',encoding='utf-8',errors='ignore') as f:
                    f.write(xmlstr)
                if convert_danmaku and os.path.exists(os.path.join(path,danmaku_filename)):
                    ass_danmaku_filename = replaceChr('{}_{}.ass'.format(title,bilicodes.stream_dash_video_quality[vstream['quality']]))
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
                    self._edit_display_list(index,'size',biliapis.requester.convert_size(size))
                    if audio_format == 'copy' or astream['quality'] == 30251:
                        if astream['quality'] == 30251:
                            os.rename(os.path.join(path,tmpname_audio),os.path.join(path,final_filename_audio_only)+'.flac')
                        else:
                            os.rename(os.path.join(path,tmpname_audio),os.path.join(path,final_filename_audio_only)+'.aac')
                    else:
                        self._edit_display_list(index,'status','混流/转码')
                        ffdriver.convert_audio(os.path.join(path,tmpname_audio),
                                               os.path.join(path,final_filename_audio_only),audio_format,
                                               bilicodes.stream_dash_audio_quality[astream['quality']].lower())
                        try:
                            os.remove(os.path.join(path,tmpname_audio))
                        except:
                            pass
                else:
                    v_session = biliapis.requester.download_yield(vstream['url'],tmpname_video,path)
                    for donesize,totalsize,percent in v_session:
                        self._edit_display_list(index,'status','下载视频流 - {}%'.format(percent))
                    size += totalsize
                    self._edit_display_list(index,'size',biliapis.requester.convert_size(size))
                    #Mix
                    self._edit_display_list(index,'status','混流/转码')
                    ffstatus = ffdriver.merge_media(
                        os.path.join(path,tmpname_audio),
                        os.path.join(path,tmpname_video),
                        os.path.join(path,final_filename)
                        )
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

    def task_receiver(self, mode: str, path: str, data: typing.Union[dict, None] = None, **options) -> None:
        '''
        - `mode`: 下载模式, 必须为 `"video"` `"audio"` `"common"` `"manga"` 中的任意一个
        - `path`: 保存位置
        - `data`: (可选)传入预请求的数据(dict), 避免再次请求

        ---

        详细规则:

        - 若`mode`为`video`, 则必须通过`**options`指定[avid/bvid]或[mdid/ssid/epid]参数
            - `avid` 和 `bvid` 的专用附加参数:
                - `pids`: 分P`索引`列表, 可为空
                - `cids`: `cid`列表, 给互动视频用的, 会覆盖`pids`参数
                - 如果此视频为互动视频:
                    - 则需 提交为真值的`is_interact`参数 并 传入`cid`参数 并 [同时传入`graph_id`和`edge_id`参数 或 传入`data`参数]
                    - 此时`data`传入的是由`biliapis.video.get_interact_edge_info()`获取的数据, 并可以再传入一个包含主视频数据的`video_data`来避免大批量下载时的重复请求
                    - 若视频不是互动视频但传入了`video_data`, 在没传入`data`的情况下将其当作`data`参数处理
                    - 我实在想不到能够怎样一次性处理多个互动视频剧情节点了, 交给调用循环罢
            - `mdid` 和 `ssid` 和 `epid` 的专用附加参数:
                - `epindexes`: EP索引列表, 可为空
                - `section_index`: 番外剧集索引
                    - `section_index`指定时, `epindexes`指的是对应番外中的剧集索引
                    - 反之则`epindexes`指正片内的索引; 超出索引范围操作无效
            - 通用可选参数: 
                - `audiostream_only`: 是否仅抽取音轨
                - `audio_format`: 音频转换格式, 仅当`audiostream_only`参数被指定时生效
                - `quality`: 视频优先质量 
                - `subtitle`: 是否下载字幕 
                - `danmaku`: 是否下载弹幕
                - `subtitle_regulation`: 字幕匹配规则
                - 弹幕过滤列表因为可能太长所以直接由线程从`config`中实时读取
                - 除了`audiostream_only`外都会读取`config`中的默认值
        - 若`mode`为`audio`, 则必须指定`auid`参数
            - `auid`的附加参数: `audio_format` (从`config`中读取默认值)
        - 若`mode`为`common`, 则必须指定`url`和`filename`, 无附加参数.
        - 若`mode`为`manga`, 则必须指定`epid`或`mcid`参数
            - 若`mcid`被指定, 有 `epindexes` 参数可选
        '''     
        with self.task_receiving_lock: # 防止多线程操作资源混乱
            is_mainthread = isinstance(threading.current_thread(),threading._MainThread)
            if is_mainthread:
                self.show() #规避 main thread not in main loop 错误
            mode = mode.lower()
            if mode == 'video':
                #普通视频
                if 'avid' in options or 'bvid' in options:
                    abvid = {'avid':None,'bvid':None}
                    if 'avid' in options:
                        abvid['avid'] = options['avid']
                    else:
                        abvid['bvid'] = options['bvid']
                    # 互动视频判定
                    is_interact = False
                    if 'is_interact' in options:
                        if options['is_interact']:
                            is_interact = True
                    if is_interact:
                        edge_data = None
                        # 特殊处理互动视频
                        assert 'cid' in options,'提交的资源不够, 互动视频分P的解析需要cid'
                        cid = options['cid']
                        if 'graph_id' in options and 'edge_id' in options:
                            try:
                                edge_data = biliapis.video.get_interact_edge_info(
                                    graph_id=options['graph_id'],
                                    edge_id=options['edge_id'],
                                    **abvid
                                    )
                            except Exception as e:
                                if is_mainthread:
                                    msgbox.showerror('Error','Unable to get edge data:\n'+str(e),parent=self.window)
                                else:
                                    logging.error('Unable to get edge data: '+str(e))
                                return
                        elif data:
                            # 没有办法做验证
                            edge_data = data
                        else:
                            raise AssertionError('提交的资源不够, 互动视频分P的解析需要 [graph_id和edge_id] 或 来自biliapis.video.get_interact_edge_info()的数据')
                        if 'video_data' in options:
                            if 'avid' in options:
                                assert options['avid']==options['video_data']['avid'],'预请求数据包内容不匹配'
                            else:
                                assert options['bvid']==options['video_data']['bvid'],'预请求数据包内容不匹配'
                            video_data = options['video_data']
                        else:
                            try:
                                video_data = biliapis.video.get_detail(**abvid)
                            except Exception as e:
                                if is_mainthread:
                                    msgbox.showerror('Error','Unable to get video data:\n'+str(e),parent=self.window)
                                else:
                                    logging.error('Unable to get video data: '+str(e))
                                return

                        pre_opts = {}
                        pre_opts['audio_format'] = config['download']['video']['audio_convert']
                        pre_opts['quality'] = config['download']['video']['quality']
                        pre_opts['subtitle'] = config['download']['video']['subtitle']
                        pre_opts['danmaku'] = config['download']['video']['danmaku']
                        pre_opts['subtitle_regulation'] = config['download']['video']['subtitle_lang_regulation']
                        pre_opts['convert_danmaku'] = config['download']['video']['convert_danmaku']
                        for key in ['audiostream_only','quality','subtitle','danmaku','subtitle_regulation','convert_danmaku']:#过滤download_thread不需要的, 防止出错
                            if key in options:
                                pre_opts[key] = options[key]
                        pre_opts['bvid'] = video_data['bvid']
                        pre_opts['path'] = path
                        pre_opts['cid'] = cid
                        pre_opts['title'] = '{}_E{}_{}'.format(video_data['title'],edge_data['edge_id'],edge_data['title'])#文件名格式编辑在这里
                        pre_opts['index'] = len(self.data_objs)
                        self.data_objs.append([len(self.data_objs)+1,'video',pre_opts])
                        with self.table_edit_lock:
                            self.table_display_list.append([
                                str(len(self.data_objs)),video_data['title'],'E{} {}'.format(edge_data['edge_id'],edge_data['title']),'Cid'+str(cid),'','','','-',path,'待处理'
                                ])
                        self.task_queue.put_nowait(lambda args=pre_opts:self._video_download_thread(**args))
                    else:
                        # 正常处理普通视频
                        video_data = None
                        if not data and 'video_data' in options:
                            data = options['video_data']
                        if data:
                            #提取预处理数据包
                            if 'avid' in options:
                                assert options['avid']==data['avid'],'预请求数据包内容不匹配'
                            else:
                                assert options['bvid']==data['bvid'],'预请求数据包内容不匹配'
                            video_data = data
                        else:
                            #提取avid/bvid
                            try:
                                video_data = biliapis.video.get_detail(**abvid)
                            except Exception as e:
                                if is_mainthread:
                                    msgbox.showerror('Error','Unable to get video data:\n'+str(e),parent=self.window)
                                else:
                                    logging.error('Unable to get video data: '+str(e))
                                return
                            # if 'avid' in options:
                            #     video_data = biliapis.video.get_detail(avid=options['avid'])
                            # else:
                            #     video_data = biliapis.video.get_detail(bvid=options['bvid'])
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
                        pre_opts['quality'] = config['download']['video']['quality']
                        pre_opts['subtitle'] = config['download']['video']['subtitle']
                        pre_opts['danmaku'] = config['download']['video']['danmaku']
                        pre_opts['subtitle_regulation'] = config['download']['video']['subtitle_lang_regulation']
                        pre_opts['convert_danmaku'] = config['download']['video']['convert_danmaku']
                        for key in ['audiostream_only','quality','subtitle','danmaku','subtitle_regulation','convert_danmaku']:#过滤download_thread不需要的, 防止出错
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
                                if part['title'] == video_data['title']:
                                    tmpdict['title'] = '{}_P{}'.format(video_data['title'],pid+1)#文件名格式编辑在这里
                                else:
                                    tmpdict['title'] = '{}_P{}_{}'.format(video_data['title'],pid+1,part['title'])#文件名格式编辑在这里
                                tmpdict['index'] = len(self.data_objs)
                                self.data_objs.append([len(self.data_objs)+1,'video',tmpdict])
                                with self.table_edit_lock:
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
                        if isinstance(e, AssertionError):
                            raise
                        if is_mainthread:
                            msgbox.showerror('',str(e),parent=self.window)
                        else:
                            logging.error("Unable to get media data: "+str(e))
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
                    pre_opts['quality'] = config['download']['video']['quality']
                    pre_opts['subtitle'] = config['download']['video']['subtitle']
                    pre_opts['danmaku'] = config['download']['video']['danmaku']
                    pre_opts['subtitle_regulation'] = config['download']['video']['subtitle_lang_regulation']
                    pre_opts['convert_danmaku'] = config['download']['video']['convert_danmaku']
                    for key in ['audiostream_only','audio_format','quality','subtitle','danmaku','subtitle_regulation','convert_danmaku']:#过滤download_thread不需要的, 防止出错
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
                            with self.table_edit_lock:
                                self.table_display_list.append([str(len(self.data_objs)),main_title,'{} {}.{}'.format(sstitle,epindex+1,episode['title']),'Cid{}'.format(episode['cid']),'','','','-',path,'待处理'])
                            self.task_queue.put_nowait(lambda args=tmpdict:self._video_download_thread(**args))
                else:
                    raise AssertionError('提交的资源不足, 解析视频需要avid/bvid/mdid/ssid/epid中的任意一个')
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
                if data:
                    assert data['auid']==options['auid'],'预请求数据包内容不匹配'
                    tmpdict['data'] = data.copy()
                tmpdict = tmpdict.copy()
                self.data_objs.append([len(self.data_objs)+1,'audio',tmpdict])
                with self.table_edit_lock:
                    self.table_display_list.append([str(len(self.data_objs)),'','','Auid'+str(tmpdict['auid']),'音频下载','','','',path,'待处理'])
                self.task_queue.put_nowait(lambda args=tmpdict:self._audio_download_thread(**args))
            elif mode == 'common':
                tmpdict = {
                    'index':len(self.data_objs),
                    'url':options['url'],
                    'filename':options['filename'],
                    'path':path
                    }
                self.data_objs.append([len(self.data_objs)+1,'common',tmpdict])
                with self.table_edit_lock:
                    self.table_display_list.append([str(len(self.data_objs)),options['filename'],'',options['url'],'普通下载','','','-',path,'待处理'])
                self.task_queue.put_nowait(lambda args=tmpdict:self._common_download_thread(**args))
            elif mode == 'manga':
                if 'mcid' in options:
                    #提取预处理数据
                    if data:
                        assert data['mcid']==options['mcid'],'预请求数据包内容不匹配'
                    else:
                        try:
                            data = biliapis.manga.get_detail(options['mcid'])
                        except Exception as e:
                            if is_mainthread:
                                msgbox.showerror('',str(e),parent=self.window)
                            else:
                                logging.error("Unable to get manga data: "+str(e))
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
                        with self.table_edit_lock:
                            self.table_display_list.append([str(len(self.data_objs)),data['comic_title'],data['ep_list'][index]['eptitle'],'EP'+str(data['ep_list'][index]['epid']),'漫画下载','','-','',path,'待处理'])
                        self.task_queue.put_nowait(lambda args=tmpdict:self._manga_download_thread(**args))
                elif 'epid' in options:
                    #提取预处理数据
                    if data:
                        assert data['epid']==options['epid'],'预请求数据包内容不匹配'
                    else:
                        try:
                            data = biliapis.manga.get_episode_info(options['epid'])
                        except Exception as e:
                            if is_mainthread:
                                msgbox.showerror('',str(e),parent=self.window)
                            else:
                                logging.error('Unable to get episode data: '+str(e))
                            return
                    tmpdict = {
                        'index':len(self.data_objs),
                        'epid':options['epid'],
                        'path':path
                        }
                    self.data_objs.append([len(self.data_objs)+1,'manga',tmpdict])
                    with self.table_edit_lock:
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
        if self.window: # 构建GUI
            if self.window.state() == 'iconic':
                self.window.deiconify()
        else:
            self.window = tk.Tk()
            self.window.title('BiliTools - Download Manager')
            self.window.resizable(height=False,width=False)
            self.window.protocol('WM_DELETE_WINDOW',self.hide)
            self.window.wm_attributes('-alpha',config['alpha'])
            self.window.wm_attributes('-topmost',config['topmost'])
            # 任务列表
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
            # 初始化表头
            i = 0
            for column in self.table_columns.keys():
                self.table.column(column,width=self.table_columns_widths[i],minwidth=self.table_columns_widths[i],anchor='w')
                self.table.heading(column,text=self.table_columns[column],anchor='w')
                i += 1
            # 数据统计
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
            # 操作面板
            self.frame_console = tk.LabelFrame(self.window,text='操作')
            self.frame_console.grid(column=1,row=1,sticky='nw')
            ttk.Button(self.frame_console,text='重试所有失败任务',command=self.retry_all_failed).grid(column=0,row=0,sticky='w')
        
            self.auto_refresh_table()
            
    def auto_refresh_table(self): #更新依据: self.table_display_list
        with self.table_edit_lock:
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
        self.label_tips.bind('<Button-1>',lambda x=0:self.change_tip(by_human=True))
        if not config['show_tips']:
            self.label_tips.grid_remove()

        self.change_tip(by_human=False)
        self.login(True)
        self.entry_source.focus()
        self.entry_source.bind('<Control-Tab>',lambda x=0:(self.intvar_entrymode.set((self.intvar_entrymode.get()+1)%3),
                                                   self.window.after(10,lambda:self.entry_source.focus())))

        self.mainloop()

    def _clear_face(self):
        self.label_face.clear()
        self.label_face_text.grid()
        self.label_face.unbind('<Button-1>')

    def _new_login(self):
        self.window.wm_attributes('-topmost',False)
        try:
            w = LoginWindow()
        except Exception as e:
            msgbox.showwarning('','登录出现错误: \n'+str(e),parent=self.window)
            logging.error('Unexpected Error occurred when login: '+str(e))
            self.button_login.configure(state='normal')
        else:
            if w.status:
                #time.sleep(0.2) # 实验性(?)
                biliapis.requester.load_local_cookies()
                self.refresh_data()
            else:
                msgbox.showwarning('','登录未完成.',parent=self.window)
                self.button_login.configure(state='normal')
        self.window.wm_attributes('-topmost',config['topmost'])

    def refresh_data(self,init=False):
        def tmp():
            self.task_queue.put_nowait(lambda:self.button_login.configure(state='disabled'))
            self.task_queue.put_nowait(lambda:self.button_refresh.configure(state='disabled'))
            try:
                data = biliapis.login.get_login_info()
            except biliapis.BiliError as e:
                if e.code == -101:
                    if init:
                        pass
                    else:
                        self.task_queue.put_nowait(self._new_login)
                else:
                    self.task_queue.put_nowait(lambda ei=str(e):msgbox.showerror('',ei,parent=self.window))
                self.task_queue.put_nowait(lambda:self.button_login.configure(state='normal'))
                self.task_queue.put_nowait(self._clear_face)
                self.task_queue.put_nowait(lambda:self.button_login.configure(text='登录',command=self.login))
            except Exception as e:
                logging.error('Unexpected Error occurred when login: '+str(e))
                self.task_queue.put_nowait(lambda ei=str(e):msgbox.showerror('','登录时出现错误: \n'+ei,parent=self.window))
                self.task_queue.put_nowait(lambda:self.button_login.configure(state='normal'))
                self.task_queue.put_nowait(self._clear_face)
                self.task_queue.put_nowait(lambda:self.button_login.configure(text='登录',command=self.login))
            else:
                def load_user_info(user_data):
                    start_new_thread(lambda url=biliapis.format_img(user_data['face'],w=120,h=120):
                                     self.task_queue.put_nowait(lambda img=BytesIO(biliapis.requester.get_content_bytes(url)):self.label_face.set(img)))
                    self.label_face_text.grid_remove()
                    self.label_face.bind('<Button-1>',
                                         lambda event=None,text='{name}\nUID{uid}\nLv.{level}\n{vip_type}\nCoin: {coin}\nMoral: {moral}'.format(**user_data):msgbox.showinfo('User Info',text,parent=self.window))
                self.task_queue.put_nowait(lambda:load_user_info(data))
                self.task_queue.put_nowait(lambda:self.button_login.configure(state='normal'))
                self.task_queue.put_nowait(lambda:self.button_refresh.configure(state='normal'))
                self.task_queue.put_nowait(lambda:self.button_login.configure(text='退出登录',command=self.logout))
        start_new_thread(tmp,())

    def login(self,init=False):
        self.refresh_data(init=init)
            
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

    def change_tip(self, by_human=False):
        tip = textlib.get_tip(by_human=by_human)
        self.label_tips['text'] = 'Tip: '+tip

    def _jump_by_source(self,source):
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

    def start(self,source=None):
        if source == None:
            source = self.entry_source.get().strip()
        if not source:
            msgbox.showinfo('','你似乎没有输入任何内容......',parent=self.window)
            return
        mode = self.intvar_entrymode.get()
        if mode == 0:#跳转模式
            self._jump_by_source(source)
        elif mode == 1:#搜索模式
            if source:
                kws = source.split()
                w = SearchWindow(*kws)
        elif mode == 2:#快速下载模式
            try:
                self._fast_download(*biliapis.parse_url(source))
            except Exception:
                msgbox.showerror('','在尝试快速下载时出现了错误：\n'+traceback.format_exc(),parent=self.window)
                raise

    def __fd_commonv(self, source, flag):
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

    def __fd_audio(self, source, flag):
        path = filedialog.askdirectory(title='选择保存位置',parent=self.window)
        if not path:
            return
        download_manager.task_receiver('audio',path,auid=source)

    def __fd_media(self, source, flag):
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
            indexes = PartsChooser(tmp, title='Media %s'%title).return_values
            if not indexes:
                return
        else:
            msgbox.showinfo('','没有正片',parent=self.window)
            return
        download_manager.task_receiver('video',path,ssid=bangumi_data['ssid'],data=bangumi_data,epindexes=indexes)

    def __fd_manga(self, source, flag):
        path = filedialog.askdirectory(title='选择保存位置',parent=self.window)
        if not path:
            return
        
        manga_data = biliapis.manga.get_detail(mcid=source)
        if len(manga_data['ep_list']) > 0:
            indexes = PartsChooser(
                [[
                    i['eptitle'],
                    str(i['epid']),
                    {True:'Yes',False:'No'}[i['pay_gold']==0],
                    {True:'Yes',False:'No'}[i['is_locked']]
                    ] for i in manga_data['ep_list']],
                title='EpisodesChooser',
                columns=['章节标题','EpID','是否免费','是否锁定'],
                columns_widths=[200,70,60,60]
                ).return_values
            if not indexes:
                return
        else:
            msgbox.showinfo('','没有章节',parent=self.window)
            return
        download_manager.task_receiver('manga',path,data=manga_data,mcid=source,epindexes=indexes)

    # 下面几个函数的结构, 其实都差不多...?
    # 我想是否可以做个模板来套, 但是似乎有点...
    def __fd_collection(self, source, flag):
        path = filedialog.askdirectory(title='选择保存位置',parent=self.window)
        if not path:
            return
        
        collection = biliapis.video.get_archive_list(*source,page_size=100)
        archives = collection['archives']
        tp = collection['total_page']
        if not archives:
            msgbox.showinfo('合集没有内容',parent=self.window)
            return
        if tp > 1:
            if msgbox.askyesno('多个分页','目标合集内容量超过100(共{}), 要全部获取吗？\n这可能会花上一段时间.'.format(collection['total']),parent=self.window):
                def get_archives(source,tp,progress_hook):
                    archives = []
                    for p in range(2,tp+1):
                        progress_hook['status'] = 'Fetching page %d of %d'%(p, tp)
                        progress_hook['progress'] = (p-1, tp)
                        archives += biliapis.video.get_archive_list(*source,page_size=100,page=p)['archives']
                        time.sleep(config['download']['batch_sleep'])
                    return archives
                archives += cusw.run_with_gui(
                    get_archives,
                    master=self.window,
                    args=(source,tp),
                    is_progress_hook_available=True
                    )

        indexes = PartsChooser(
            [[
                i['title'],
                biliapis.second_to_time(i['duration']),
                i['bvid'],
                {True:'Yes',False:'No'}[i['is_interact_video']]
            ] for i in archives],
            columns=['标题','长度','BvID','互动视频'],
            title='Collection'
            ).return_values
        if not indexes:
            return
        
        def putin_tasks(indexes,archives,progress_hook):
            count = 0
            ind_total = len(indexes)
            for index in indexes:
                count += 1
                progress_hook['status'] = 'Adding task %d of %d'%(count, ind_total)
                progress_hook['progress'] = (count-1, ind_total)
                download_manager.task_receiver('video',path,bvid=archives[index]['bvid'])
                time.sleep(config['download']['batch_sleep'])
        cusw.run_with_gui(
            putin_tasks,
            args=(indexes,archives),
            master=self.window,
            is_progress_hook_available=True
            )

    def __fd_series(self, source, flag):
        path = filedialog.askdirectory(title='选择保存位置',parent=self.window)
        if not path:
            return
        
        series = biliapis.video.get_series_list(*source,page_size=100)
        archives = series['archives']
        tp = series['total_page']
        if not archives:
            msgbox.showinfo('没有内容',parent=self.window)
            return
        if tp > 1:
            if msgbox.askyesno('多个分页','目标内容量超过100(共{}), 要全部获取吗？\n这可能会花上一段时间.'.format(series['total']),parent=self.window):
                def get_archives(source, tp, progress_hook):
                    archives = []
                    for p in range(2,tp+1):
                        progress_hook['status'] = 'Fetching page %d of %d'%(p, tp)
                        progress_hook['progress'] = (p-1, tp)
                        archives += biliapis.video.get_series_list(*source,page_size=100,page=p)['archives']
                        time.sleep(config['download']['batch_sleep'])
                    return archives
                archives += cusw.run_with_gui(
                    get_archives,
                    master=self.window,
                    args=(source,tp),
                    is_progress_hook_available=True
                    )
                
        indexes = PartsChooser(
            [[
                i['title'],
                biliapis.second_to_time(i['duration']),
                i['bvid'],
                {True:'Yes',False:'No'}[i['is_interact_video']]
            ] for i in archives],
            columns=['标题','长度','BvID','互动视频'],
            title='Collection'
            ).return_values
        if not indexes:
            return
        
        def putin_tasks(indexes,archives,progress_hook):
            count = 0
            ind_total = len(indexes)
            for index in indexes:
                count += 1
                progress_hook['status'] = 'Adding task %d of %d'%(count, ind_total)
                progress_hook['progress'] = (count-1, ind_total)
                download_manager.task_receiver('video',path,bvid=archives[index]['bvid'])
                time.sleep(config['download']['batch_sleep'])
        cusw.run_with_gui(
            putin_tasks,
            args=(indexes,archives),
            master=self.window,
            is_progress_hook_available=True
            )

    def __fd_favlist(self, source, flag):
        path = filedialog.askdirectory(title='选择保存位置',parent=self.window)
        if not path:
            msgbox.showinfo('注意','操作已被取消',parent=self.window)
            return
        
        favlist = biliapis.user.get_favlist(mlid=source[1])
        total = favlist['content_count']
        page_size = 20 # 已经是最大了
        page = math.ceil(total/page_size)
        content = favlist['content']
        if total == 0:
            msgbox.showinfo('','收藏夹没有内容',parent=self.window)
            return
        elif page > 1:
            if msgbox.askyesno('多个分页','目标内容量超过{}(共{}), 要全部获取吗？\n这可能会花上一段时间.'.format(page_size, total),parent=self.window):
                def get_favlist_content(source, tp, progress_hook):
                    archives = []
                    for p in range(2,tp+1):
                        progress_hook['status'] = 'Fetching page %d of %d'%(p, tp)
                        progress_hook['progress'] = (p-1, tp)
                        archives += biliapis.user.get_favlist(source[1],page_size=page_size,page=p)['content']
                        time.sleep(config['download']['batch_sleep'])
                    return archives
                content += cusw.run_with_gui(
                    get_favlist_content,
                    master=self.window,
                    args=(source, page),
                    is_progress_hook_available=True
                    )
                
        indexes = PartsChooser(
            [[i['title'],biliapis.second_to_time(i['duration']),i['bvid'],i['uploader']['name']] for i in content],
            columns=['标题','长度','BvID','UP主'],
            title='FavList {} by {}'.format(source[1], favlist['uploader']['name'])
            ).return_values  
        if not indexes:
            return
        
        def putin_tasks(indexes, archives, progress_hook):
            count = 0
            ind_total = len(indexes)
            for index in indexes:
                count += 1
                progress_hook['status'] = 'Adding task %d of %d'%(count, ind_total)
                progress_hook['progress'] = (count-1, ind_total)
                download_manager.task_receiver('video',path,bvid=archives[index]['bvid'])
                time.sleep(config['download']['batch_sleep'])
        cusw.run_with_gui(
            putin_tasks,
            args=(indexes, content),
            master=self.window,
            is_progress_hook_available=True
            )

    def __fd_audiolist(self, source, flag):
        path = filedialog.askdirectory(title='选择保存位置',parent=self.window)
        if not path:
            return
        
        data = biliapis.audio.get_list(source)
        if not data:
            msgbox.showinfo('','歌单是空的.',parent=self.window)
            return
        tp = data['total_page']
        audio_list = data['data']

        if tp > 1:
            if msgbox.askyesno('多个分页','目标歌单内容量超过100(共{}), 要全部获取吗？\n这可能会花上一段时间.'.format(data['total_size']),parent=self.window):
                def get_audio_lists(source,tpprogress_hook):
                    audio_list = []
                    for p in range(2,tp+1):
                        audio_list += biliapis.audio.get_list(source,page=p)['data']
                        time.sleep(config['download']['batch_sleep'])
                    return audio_list
                audio_list += cusw.run_with_gui(
                    get_audio_lists,
                    args=(source,tp),
                    master=self.window,
                    is_progress_hook_available=True
                    )
        if not audio_list:
            return
        
        indexes = PartsChooser(
            [[i['title'],biliapis.second_to_time(i['length']),str(i['auid']),i['connect_video']['bvid']] for i in audio_list],
            columns=['标题','长度','AuID','关联BvID'],
            title='Audio List'
            ).return_values
        if not indexes:
            return
        def putin_tasks(indexes,audio_list,progress_hook):
            count = 0
            ind_total = len(indexes)
            for index in indexes:
                count += 1
                progress_hook['status'] = 'Adding task %d of %d'%(count, ind_total)
                progress_hook['progress'] = (count-1, ind_total)
                download_manager.task_receiver('audio',path,auid=audio_list[index]['auid'],data=audio_list[index])
        cusw.run_with_gui(
            putin_tasks,
            args=(indexes,audio_list),
            master=self.window,
            is_progress_hook_available=True
            )

    def _fast_download(self,source,flag):
        if flag == 'unknown':
            msgbox.showinfo('','无法解析......',parent=self.window)
        elif flag == 'avid' or flag == 'bvid':                      # 普通视频
            self.__fd_commonv(source=source, flag=flag)
        elif flag == 'auid':                                        # 音频
            self.__fd_audio(source=source, flag=flag)
        elif flag == 'ssid' or flag == 'mdid' or flag == 'epid':    # 番
            self.__fd_media(source=source, flag=flag)
        elif flag == 'mcid':                                        # 漫画
            self.__fd_manga(source=source, flag=flag)
        elif flag == 'collection':                                  # 合集
            self.__fd_collection(source=source, flag=flag)
        elif flag == 'favlist':                                     # 收藏夹
            self.__fd_favlist(source=source, flag=flag)
        elif flag == 'series':                                      # 系列
            self.__fd_series(source=source, flag=flag)
        elif flag == 'amid':                                        # 歌单
            self.__fd_audiolist(source=source,flag=flag)
        else:
            msgbox.showinfo('','暂不支持%s的快速下载'%flag,parent=self.window)


class BatchWindow(Window):
    def __init__(self):
        super().__init__('BiliTools - Batch',True,config['topmost'],config['alpha'])

        #Main Entry
        tk.Label(self.window,text='每行一个网址, 仅支持批量下载普通视频.\n所有分P均会被下载.\n请耐心等待.',justify='left').grid(column=0,row=0,sticky='w')
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
        if text:
            path = filedialog.askdirectory(title='输出至',parent=self.window)
            if path:
                audiomode = self.boolvar_audiomode.get()
                self.close()
                cusw.run_with_gui(self.working_thread,(text,audiomode,path))
            
    def working_thread(self,text,audiomode,path):
        lines = text.split('\n')
        for line in lines:
            if line:
                source,flag = biliapis.parse_url(line)
                if flag in ['avid','bvid']:
                    download_manager.task_receiver('video',path,audiostream_only=audiomode,**{flag:source})
                    time.sleep(config['download']['batch_sleep'])

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
        self.frame_basic.grid(column=0,row=0,sticky='nwse')
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
        #Tips
        self.boolvar_show_tips = tk.BooleanVar(self.window,config['show_tips'])
        self.checkbutton_show_tips = ttk.Checkbutton(self.frame_basic,text='显示Tips',onvalue=True,offvalue=False,variable=self.boolvar_show_tips)
        self.checkbutton_show_tips.grid(column=0,row=3,sticky='w')
        self.tooltip_show_tips = cusw.ToolTip(self.checkbutton_show_tips,text='警告：开启之后你将会看到一些不正经的语录......以及作者的碎碎念。\n重启程序生效')

        #Download
        self.frame_download = tk.LabelFrame(self.window,text='下载')
        self.frame_download.grid(column=1,row=0,sticky='nwes')
        #Thread Number
        self.intvar_threadnum = tk.IntVar(self.window,config['download']['max_thread_num'])
        tk.Label(self.frame_download,text='最大线程数: ').grid(column=0,row=0,sticky='e')
        ttk.OptionMenu(self.frame_download,self.intvar_threadnum,config['download']['max_thread_num'],*range(1,17)).grid(column=1,row=0,sticky='w')
        #Video Quality
        if config['download']['video']['quality']:
            default_vq = bilicodes.stream_dash_video_quality[config['download']['video']['quality']]
        else:
            default_vq = bilicodes.stream_dash_video_quality[max(list(bilicodes.stream_dash_video_quality.keys()))]
        self.strvar_video_quality = tk.StringVar(self.window,default_vq)
        tk.Label(self.frame_download,text='优先画质: ').grid(column=0,row=1,sticky='e')
        ttk.OptionMenu(self.frame_download,self.strvar_video_quality,default_vq,*list(bilicodes.stream_dash_video_quality.values())).grid(column=1,row=1,sticky='w')
        #Flac
        self.boolvar_allow_flac = tk.BooleanVar(self.window,config['download']['video']['allow_flac'])
        self.checkbutton_allow_flac = ttk.Checkbutton(self.frame_download,text='允许Flac音轨',onvalue=True,offvalue=False,variable=self.boolvar_allow_flac)
        self.checkbutton_allow_flac.grid(column=0,row=2,sticky='w',columnspan=2)
        self.tooltip_allow_flac = cusw.ToolTip(self.checkbutton_allow_flac,'由于mp4容器的限制，包含flac音轨的视频将被封装为mkv格式。')
        #batch sleep
        self.frame_batch_sleep = tk.Frame(self.frame_download)
        # self.frame_batch_sleep.grid(col)

        #Subtitle
        self.frame_subtitle = tk.LabelFrame(self.window,text='字幕与歌词')
        self.frame_subtitle.grid(column=0,row=2,sticky='we',columnspan=2)
        self.subtitle_preset = {
            '简体中文优先':['zh-CN','zh-Hans','zh-Hant','zh-HK','zh-TW','en-US','en-GB','ja','ja-JP'],
            '繁体中文优先':['zh-Hant','zh-HK','zh-TW','zh-CN','zh-Hans','en-US','en-GB','ja','ja-JP'],
            '英文优先':['en-US','en-GB','zh-CN','zh-Hans','zh-Hant','zh-HK','zh-TW','ja','ja-JP'],
            '日文优先':['ja','ja-JP','zh-CN','zh-Hans','zh-Hant','zh-HK','zh-TW','en-US','en-GB']
            }
        self.boolvar_subtitle = tk.BooleanVar(self.window,config['download']['video']['subtitle'])
        self.checkbutton_subtitle = ttk.Checkbutton(self.frame_subtitle,text='下载字幕',onvalue=True,offvalue=False,variable=self.boolvar_subtitle)
        self.checkbutton_subtitle.grid(column=0,row=0,sticky='w')
        self.boolvar_allow_ai_sub = tk.BooleanVar(self.window,config['download']['video']['allow_ai_subtitle'])
        self.checkbutton_allow_ai_sub = ttk.Checkbutton(self.frame_subtitle,text='允许AI生成字幕',onvalue=True,offvalue=False,variable=self.boolvar_allow_ai_sub)
        self.checkbutton_allow_ai_sub.grid(column=1,row=0,sticky='w')
        init_subtitle_om_text = self._get_subtitle_preset_text()
        self.strvar_subtitle_preset = tk.StringVar(self.window,init_subtitle_om_text)
        tk.Label(self.frame_subtitle,text='多字幕视频的字幕方案:').grid(column=0,row=1,sticky='e')
        self.om_subtitle_preset = ttk.OptionMenu(self.frame_subtitle,self.strvar_subtitle_preset,init_subtitle_om_text,*list(self.subtitle_preset.keys()),'自定义',command=self._subtitle_preset_command)
        self.om_subtitle_preset.grid(column=1,row=1,sticky='w')
        self.subtitle_regulation = config['download']['video']['subtitle_lang_regulation']
        #Lyrics
        self.boolvar_lyrics = tk.BooleanVar(self.window,config['download']['audio']['lyrics'])
        self.checkbutton_lyrics = ttk.Checkbutton(self.frame_subtitle,text='下载歌词',onvalue=True,offvalue=False,variable=self.boolvar_lyrics)
        self.checkbutton_lyrics.grid(column=0,row=2,columnspan=2,sticky='w')
        
        #Danmaku
        self.frame_danmaku = tk.LabelFrame(self.window,text='弹幕')
        self.frame_danmaku.grid(column=2,row=0,rowspan=2,sticky='wne')
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

        #Play
        self.frame_play = tk.LabelFrame(self.window,text='播放')
        self.frame_play.grid(column=1,row=1,sticky='nse')
        #audio
        self.strvar_play_aq = tk.StringVar(self.window,bilicodes.stream_audio_quality[config['play']['audio_quality']])
        self.frame_play_audio = tk.LabelFrame(self.frame_play,text='音频区')
        self.frame_play_audio.grid(column=0,row=0,columnspan=2,sticky='we')
        tk.Label(self.frame_play_audio,text='音质:').grid(column=0,row=0,sticky='e')
        self.om_play_aq = ttk.OptionMenu(self.frame_play_audio,self.strvar_play_aq,self.strvar_play_aq.get(),*list(bilicodes.stream_audio_quality.values())[1:])
        self.om_play_aq.grid(column=1,row=0,sticky='w')
        #video
        self.strvar_play_vq = tk.StringVar(self.window,bilicodes.stream_flv_video_quality[config['play']['video_quality']])
        self.frame_play_video = tk.LabelFrame(self.frame_play,text='视频区')
        self.frame_play_video.grid(column=0,row=1,columnspan=2,sticky='we')
        tk.Label(self.frame_play_video,text='画质:').grid(column=0,row=0,sticky='e')
        self.om_play_vq = ttk.OptionMenu(self.frame_play_video,self.strvar_play_vq,self.strvar_play_vq.get(),*list(bilicodes.stream_flv_video_quality.values()))
        self.om_play_vq.grid(column=1,row=0,sticky='w')
        #repeat
        self.frame_play_repeat = tk.LabelFrame(self.frame_play,text='循环播放')
        self.frame_play_repeat.grid(column=0,row=2,sticky='w')
        self.doublevar_play_repeat = tk.DoubleVar(self.window,float(config['play']['repeat']))
        self.label_play_repeat_shower = tk.Label(self.frame_play_repeat,text=str(config['play']['repeat'])+' 次',width=6)
        self.label_play_repeat_shower.grid(column=0,row=0,sticky='e')
        self.scale_play_repeat = ttk.Scale(self.frame_play_repeat,from_=0,to=999,orient=tk.HORIZONTAL,length=150,
                                           variable=self.doublevar_play_repeat,command=lambda coor:self.label_play_repeat_shower.configure(text='%s 次'%(int(float(coor)))))
        self.scale_play_repeat.grid(column=1,row=0)
        #other
        self.boolvar_play_fs = tk.BooleanVar(self.window,config['play']['fullscreen'])
        ttk.Checkbutton(self.frame_play,variable=self.boolvar_play_fs,onvalue=True,offvalue=False,text='全屏启动').grid(column=0,row=3,sticky='w')
        self.boolvar_play_ae = tk.BooleanVar(self.window,config['play']['auto_exit'])
        ttk.Checkbutton(self.frame_play,variable=self.boolvar_play_ae,onvalue=True,offvalue=False,text='播完自动退出').grid(column=0,row=4,sticky='w')

        #Proxy
        self.frame_proxy = tk.LabelFrame(self.window,text='代理')
        self.frame_proxy.grid(column=0,row=1,sticky='n')
        self.boolvar_use_pxy = tk.BooleanVar(self.window,config['proxy']['enabled'])
        self.checkbutton_use_pxy = ttk.Checkbutton(self.frame_proxy,text='使用代理',onvalue=True,offvalue=False,variable=self.boolvar_use_pxy)
        self.checkbutton_use_pxy.grid(column=0,row=0,columnspan=2,sticky='w')

        self.boolvar_use_syspxy = tk.BooleanVar(self.window,config['proxy']['use_system_proxy'])
        self.radiobutton_system_proxy = ttk.Radiobutton(self.frame_proxy,value=True,variable=self.boolvar_use_syspxy,text='使用系统代理')
        self.radiobutton_system_proxy.grid(column=0,row=1,columnspan=2,sticky='w')
        self.radiobutton_manual_proxy = ttk.Radiobutton(self.frame_proxy,value=False,variable=self.boolvar_use_syspxy,text='手动设置代理')
        self.radiobutton_manual_proxy.grid(column=0,row=2,columnspan=2,sticky='w')
        
        tk.Label(self.frame_proxy,text='服务器：').grid(column=0,row=3,sticky='e')
        self.entry_pxyhost = ttk.Entry(self.frame_proxy,width=18)
        self.entry_pxyhost.grid(column=1,row=3,sticky='w')
        self.entry_pxyhost.insert('end',config['proxy']['host'])
        tk.Label(self.frame_proxy,text='端口：').grid(column=0,row=4,sticky='e')
        self.entry_pxyport = ttk.Entry(self.frame_proxy,width=6)
        self.entry_pxyport.grid(column=1,row=4,sticky='w')
        if config['proxy']['port'] != None:
            self.entry_pxyport.insert('end',str(config['proxy']['port']))
        def update_proxy_widgets_state():
            var1 = self.boolvar_use_pxy.get()
            var2 = self.boolvar_use_syspxy.get()
            self.radiobutton_system_proxy['state'] = self.radiobutton_manual_proxy['state'] = {True:'normal',False:'disabled'}[var1]
            self.entry_pxyhost['state'] = self.entry_pxyport['state'] = {True:'normal',False:'disabled'}[var1 and not var2]
            
        self.checkbutton_use_pxy['command'] = self.radiobutton_system_proxy['command'] = self.radiobutton_manual_proxy['command'] = update_proxy_widgets_state
        update_proxy_widgets_state()
        
        # Save or Cancel
        self.frame_soc = tk.Frame(self.window)
        self.frame_soc.grid(column=2,row=2,sticky='se')
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
            rule = biliapis.danmaku.get_filter_rule()
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
            method_list = config['download']['video']['subtitle_lang_regulation']
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
                label='输入一个新的方案.\n每行一种语言, 程序会按照从上到下的顺序进行匹配.',
                text='\n'.join(self.subtitle_regulation)
                )
            if self.is_alive():
                self.om_subtitle_preset['state'] = 'normal'
            if w.return_value:
                self.subtitle_regulation = w.return_value.split('\n')
        else:
            self.subtitle_regulation = self.subtitle_preset[selectvar]
        if self.is_alive():
            self.strvar_subtitle_preset.set(self._get_subtitle_preset_text(self.subtitle_regulation))

    def apply_config(self):#
        global config
        #检查用户的设定
        pxyport = self.entry_pxyport.get().strip().split('.')[0]
        pxyhost = self.entry_pxyhost.get().strip()
        if self.boolvar_use_pxy.get():
            if not pxyhost:
                msgbox.showwarning('','代理主机名不能为空.',parent=self.window)
                return 1
            if pxyport == '':
                pxyport = None
            else:
                if not pxyport.isdigit():
                    msgbox.showwarning('','端口必须为一个整数.',parent=self.window)
                    return 1
                pxyport = int(pxyport)
                if not 0<=pxyport<=65535:
                    msgbox.showwarning('','端口不合法.',parent=self.window)
                    return 1
            config['proxy']['host'] = pxyhost
            config['proxy']['port'] = pxyport
        
        #应用用户的设定
        config['topmost'] = self.boolvar_topmost.get()
        config['alpha'] = round(self.doublevar_winalpha.get(),2)
        config['filter_emoji'] = self.boolvar_filteremoji.get()
        config['show_tips'] = self.boolvar_show_tips.get()
        
        config['download']['max_thread_num'] = self.intvar_threadnum.get()
        config['download']['video']['quality'] = bilicodes.stream_dash_video_quality_[self.strvar_video_quality.get()]
        biliapis.requester.filter_emoji = config['filter_emoji']
        config['download']['video']['subtitle_lang_regulation'] = self.subtitle_regulation
        config['download']['video']['subtitle'] = self.boolvar_subtitle.get()
        config['download']['video']['allow_ai_subtitle'] = self.boolvar_allow_ai_sub.get()
        config['download']['audio']['lyrics'] = self.boolvar_lyrics.get()
        config['download']['video']['danmaku'] = self.boolvar_danmaku.get()
        config['download']['video']['convert_danmaku'] = self.boolvar_convert_danmaku.get()
        config['download']['video']['danmaku_filter'] = self.dmfrule
        config['download']['video']['danmaku_filter']['filter_level'] = int(self.strvar_dmflevel.get())
        config['download']['video']['allow_flac'] = self.boolvar_allow_flac.get()

        config['play']['video_quality'] = bilicodes.stream_flv_video_quality_[self.strvar_play_vq.get()]
        config['play']['audio_quality'] = bilicodes.stream_audio_quality_[self.strvar_play_aq.get()]
        config['play']['repeat'] = int(self.doublevar_play_repeat.get())
        config['play']['fullscreen'] = self.boolvar_play_fs.get()
        config['play']['auto_exit'] = self.boolvar_play_ae.get()

        config['proxy']['enabled'] = self.boolvar_use_pxy.get()
        config['proxy']['use_system_proxy'] = self.boolvar_use_syspxy.get()
        #代理主机和端口的应用移到了上面
        apply_proxy_config()

    def save_config(self):
        if self.apply_config() != 1:
            dump_config()
            self.close()

class AudioWindow(Window):
    def __init__(self,auid):
        self.auid = int(auid)
        self.audio_data = None
        
        super().__init__('BiliTools - Audio',True,config['topmost'],config['alpha'])

        #cover
        self.label_cover_shower = cusw.ImageLabel(self.window,width=300,height=300)
        self.label_cover_shower.grid(column=0,row=0,rowspan=4)
        self.label_cover_text = tk.Label(self.window,text='加载中',font=('Microsoft YaHei UI',8),bg='#ffffff')
        self.label_cover_text.grid(column=0,row=0,rowspan=4)
        #title
        self.text_name = tk.Text(self.window,font=('Microsoft YaHei UI',10,'bold'),width=37,height=2,state='disabled',bg='#f0f0f0',bd=0)
        self.text_name.grid(column=0,row=4)
        self.tooltip_name = cusw.ToolTip(self.text_name)
        #id
        self.label_auid = tk.Label(self.window,text='AuID0')
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
        self.button_download_audio.grid(column=1,row=0)
        self.button_download_cover = ttk.Button(self.frame_operation,text='下载封面',command=self.download_cover)
        self.button_download_cover.grid(column=2,row=0)
        self.button_download_lyrics = ttk.Button(self.frame_operation,text='下载歌词',command=self.download_lyrics)
        self.button_download_lyrics.grid(column=3,row=0)
        self.button_open_in_ex = ttk.Button(self.frame_operation,text='在浏览器中打开',command=lambda:webbrowser.open(f'https://www.bilibili.com/audio/au{self.auid}'))
        self.button_open_in_ex.grid(column=4,row=0)
        self.button_play = ttk.Button(self.frame_operation,text='播放',command=self.play_audio)
        self.button_play.grid(column=0,row=0)
        self.frame_operation.grid(column=0,row=8,columnspan=2)

        self.refresh_data()
        self.mainloop()

    def play_audio(self):
        def process():
            try:
                stream = biliapis.stream.get_audio_stream(self.auid,quality=config['play']['audio_quality'])
                ffdriver.call_ffplay(stream['url'],title='[Au{auid}/{quality}] {title}'.format(**stream),is_audio=True,repeat=config['play']['repeat'],
                                     fullscreen=config['play']['fullscreen'],auto_exit=config['play']['auto_exit'])
            except Exception as e:
                self.task_queue.put_nowait(lambda e=e:msgbox.showerror('',str(e),parent=self.window))
        self.button_play['state'] = 'disabled'
        cusw.run_with_gui(process,no_window=True)
        if self.is_alive():
            self.button_play['state'] = 'normal'

    def download_audio(self):
        self.button_download_audio['state'] = 'disabled'
        path = filedialog.askdirectory(title='保存至',parent=self.window)
        if path:
            download_manager.task_receiver('audio',path,auid=self.auid)
        self.button_download_audio['state'] = 'normal'

    def download_cover(self):
        self.button_download_cover['state'] = 'disabled'
        if self.audio_data:
            filename = replaceChr(self.title)+'.jpg'
            path = filedialog.askdirectory(title='保存至',parent=self.window)
            if path:
                url = biliapis.audio.get_info(self.auid)['cover']
                with open(os.path.join(path,filename),'wb+') as f:
                    f.write(biliapis.requester.get_content_bytes(url))
                msgbox.showinfo('','完成',parent=self.window)
        else:
            msgbox.showwarning('','加载未完成',parent=self.window)
        if self.is_alive():
            self.button_download_cover['state'] = 'normal'
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
            msgbox.showwarning('','加载未完成',parent=self.window)
        if self.is_alive():
            self.button_download_lyrics['state'] = 'normal'
        return
        
    def refresh_data(self):
        def tmp():
            try:
                data = biliapis.audio.get_info(self.auid)
            except biliapis.BiliError as e:
                if e.code == -404 or e.code == 7201006:
                    self.task_queue.put_nowait(lambda:msgbox.showerror('','音频不存在',parent=self.window))
                    self.task_queue.put_nowait(self.close)
                    return
            self.audio_data = data
            self.title = data['title']
            self.task_queue.put_nowait(lambda:self.set_text(self.text_name,text=data['title'],lock=True))
            self.task_queue.put_nowait(lambda:self.tooltip_name.change_text(data['title']))
            self.task_queue.put_nowait(lambda:self.label_auid.configure(text='AuID%s'%data['auid']))
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
        self.link = None
        #左起第1列
        self.frame_left_1 = tk.Frame(self.window)
        self.frame_left_1.grid(column=0,row=0)
        #封面
        self.label_cover = cusw.ImageLabel(self.frame_left_1,width=380,height=232)
        self.label_cover.grid(column=0,row=0)
        self.label_cover_text = tk.Label(self.frame_left_1,text='加载中',bg='#ffffff')
        self.label_cover_text.grid(column=0,row=0)
        #title
        self.text_title = tk.Text(self.frame_left_1,bg='#f0f0f0',bd=0,height=2,width=46,state='disabled',font=('Microsoft YaHei UI',10,'bold'))
        self.text_title.grid(column=0,row=1,sticky='w')
        #warning info
        self.label_warning = cusw.ImageLabel(self.frame_left_1,width=22,height=18,cursor='hand2')
        self.label_warning.set(imglib.warning_sign)
        self.label_warning.grid(column=0,row=2,sticky='e')
        self.label_warning.grid_remove()
        self.label_warning_tooltip = None
        #第1列第4行的合并框架
        self.frame_c0r3 = tk.Frame(self.frame_left_1)
        self.frame_c0r3.grid(column=0,row=3,sticky='we')
        #av
        self.label_avid = tk.Label(self.frame_c0r3,text='AV0')
        self.label_avid.grid(column=0,row=0,sticky='w',padx=4)
        #bv
        self.label_bvid = tk.Label(self.frame_c0r3,text='BV-')
        self.label_bvid.grid(column=1,row=0,sticky='w',padx=4)
        #publish time
        self.label_pubtime = tk.Label(self.frame_c0r3,text='-')
        self.label_pubtime.grid(column=2,row=0,sticky='w',padx=4)
        #statistics
        self.frame_status = tk.LabelFrame(self.frame_left_1,text='统计')
        self.frame_status.grid(column=0,row=4)
        
        tk.Label(self.frame_status,text='播放:').grid(column=0,row=0,sticky='w')
        self.label_view = tk.Label(self.frame_status,text='-')
        self.label_view.grid(column=1,row=0,sticky='w',columnspan=5)
        
        tk.Label(self.frame_status,text='点赞:').grid(column=0,row=1,sticky='w')
        self.label_like = tk.Label(self.frame_status,text='-')
        self.label_like.grid(column=1,row=1,sticky='w')
        
        tk.Label(self.frame_status,text='投币:').grid(column=0,row=2,sticky='w')
        self.label_coin = tk.Label(self.frame_status,text='-')
        self.label_coin.grid(column=1,row=2,sticky='w')
        
        tk.Label(self.frame_status,text='收藏:').grid(column=2,row=1,sticky='w')
        self.label_collect = tk.Label(self.frame_status,text='-')
        self.label_collect.grid(column=3,row=1,sticky='w')
        
        tk.Label(self.frame_status,text='分享:').grid(column=2,row=2,sticky='w')
        self.label_share = tk.Label(self.frame_status,text='-')
        self.label_share.grid(column=3,row=2,sticky='w')
        
        tk.Label(self.frame_status,text='弹幕:').grid(column=4,row=1,sticky='w')
        self.label_dmkcount = tk.Label(self.frame_status,text='-')
        self.label_dmkcount.grid(column=5,row=1,sticky='w')
        
        tk.Label(self.frame_status,text='评论:').grid(column=4,row=2,sticky='w')
        self.label_cmtcount = tk.Label(self.frame_status,text='-')
        self.label_cmtcount.grid(column=5,row=2,sticky='w')
        #operation area 1
        self.frame_lcfs = tk.Frame(self.frame_left_1) # LCFS = Like, Coin, Fav, SeeLater (草
        self.frame_lcfs.grid(column=0,row=5)
        self.button_like = cusw.ImageButton(self.frame_lcfs,30,30,imglib.like_sign_grey,command=self.like,state='disabled')
        self.button_like.grid(column=0,row=0,padx=10)
        self.is_liked = False
        self.button_coin = cusw.ImageButton(self.frame_lcfs,30,30,imglib.coin_sign_grey,command=self.coin,state='disabled')
        self.button_coin.grid(column=1,row=0,padx=10)
        self.coined_number = -1
        self.button_collect = cusw.ImageButton(self.frame_lcfs,30,30,imglib.collect_sign_grey,command=self.collect,state='disabled')
        self.button_collect.grid(column=2,row=0,padx=10)
        self.button_toview = cusw.ImageButton(self.frame_lcfs,30,30,imglib.addtoview_sign,command=self.toview,state='disabled')
        self.button_toview.grid(column=3,row=0,padx=10)
        #operation area 2
        self.frame_operation = tk.Frame(self.frame_left_1)
        self.frame_operation.grid(column=0,row=6)
        self.button_play = ttk.Button(self.frame_operation,text='播放视频',command=lambda:self.play_video(False))
        self.button_play.grid(column=0,row=0)
        self.button_play_audio = ttk.Button(self.frame_operation,text='播放音轨',command=lambda:self.play_video(True))
        self.button_play_audio.grid(column=0,row=1)
        self.button_open_in_ex = ttk.Button(self.frame_operation,text='在浏览器中打开') # command在加载数据时加上
        self.button_open_in_ex.grid(column=1,row=0)
        self.button_download_audio = ttk.Button(self.frame_operation,text='下载音轨',command=self.download_audio)
        self.button_download_audio.grid(column=2,row=0)
        self.button_download_video = ttk.Button(self.frame_operation,text='下载视频',command=self.download_video)
        self.button_download_video.grid(column=2,row=1)
        self.button_copy_link = ttk.Button(self.frame_operation,text='复制链接',command=self.copy_link)
        self.button_copy_link.grid(column=1,row=1)
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
        self.button_show_pbp = ttk.Button(self.frame_extraopt,text='弹幕增量趋势',command=self.show_pbp)
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
        self.button_view_interact = ttk.Button(self.frame_parts,text='查看剧情图',command=self.jump_to_interact)
        self.button_view_interact.grid(column=0,row=0)
        self.button_view_interact.grid_remove()
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
        
        self.refresh_data()

        self.mainloop()

    def jump_to_interact(self):
        # 触发此函数的按钮只会在视频为互动视频时出现 故不用(懒得)做校验
        data = self.video_data
        cid = data['parts'][0]['cid']
        bvid = data['bvid']
        self.button_view_interact['state'] = 'disabled'
        self.window.after(5000,lambda:self.button_view_interact.configure(state='normal'))
        w = PlotShower(self.window,cid,bvid)
        w.init()
        w.mainloop()

    def like(self):
        def like_process(token,cancel=False):
            self.task_queue.put_nowait(lambda:self.button_like.configure(state='disabled'))
            try:
                if cancel:
                    biliapis.video.like(token,self.video_data['avid'],opt=2)
                else:
                    biliapis.video.like(token,self.video_data['avid'],opt=1)
            except Exception as e:
                if cancel:
                    self.task_queue.put_nowait(lambda e_=e:msgbox.showerror('','无法取消点赞：\n'+str(e_),parent=self.window))
                else:
                    self.task_queue.put_nowait(lambda e_=e:msgbox.showerror('','无法完成点赞：\n'+str(e_),parent=self.window))
            else:
                if cancel:
                    self.is_liked = False
                    self.task_queue.put_nowait(lambda:self.button_like.set(imglib.like_sign_grey))
                    self.task_queue.put_nowait(lambda:self.window.after(1,lambda:cusw.bubble(
                        self.button_like,'取消点赞成功'
                        )))
                else:
                    self.is_liked = True
                    self.task_queue.put_nowait(lambda:self.button_like.set(imglib.like_sign))
                    self.task_queue.put_nowait(lambda:self.window.after(1,lambda:cusw.bubble(
                        self.button_like,'点赞成功'
                        )))
            finally:
                self.task_queue.put_nowait(lambda:self.button_like.configure(state='normal'))
                
        csrf = biliapis.login.get_csrf(biliapis.requester.cookies)
        if csrf: # cookies中有csrf是点赞操作的前提之一
            if self.is_liked:
                if msgbox.askokcancel('注意','你已经点过赞了，你要取消点赞吗',parent=self.window):
                    start_new_thread(like_process,(csrf,True))
                else:
                    return
            else:
                start_new_thread(like_process,(csrf,False))
        else:
            msgbox.showerror('','点赞失败.\n未成功获取到 CSRF Token',parent=self.window)

    def coin(self):
        def coin_process(token,cn): # cn 指 coin_num
            if cn <= 0:
                return
            self.task_queue.put_nowait(lambda:self.button_coin.configure(state='disabled'))
            try:
                biliapis.video.coin(token,self.video_data['avid'],num=cn)
            except Exception as e:
                self.task_queue.put_nowait(lambda e_=e:msgbox.showerror('','无法完成投币：\n'+str(e_),parent=self.window))
            else:
                self.task_queue.put_nowait(lambda:self.button_coin.set(imglib.coin_sign))
                self.task_queue.put_nowait(lambda:self.window.after(1,lambda n=cn:cusw.bubble(
                    self.button_coin,f'成功投出了 {n} 个币'
                    )))
            finally:
                self.coined_number = coin = biliapis.video.is_coined(self.video_data['avid'])
                if coin == 2 or (coin==1 and not self.video_data['is_original']):
                    pass
                else:
                    self.task_queue.put_nowait(lambda:self.button_coin.configure(state='normal'))
                
        csrf = biliapis.login.get_csrf(biliapis.requester.cookies)
        if csrf: # cookies中有csrf是投币操作的前提之一
            is_orig = self.video_data['is_original']
            coin_num = self.coined_number
            if (coin_num == 1 and  not is_orig) or self.coined_number == 2: # 硬币已投满 (转载视频已投1颗, 自制视频已投2颗)
                msgbox.showwarning('','这个视频的币已经投满了，不能再投了',parent=self.window)
            elif coin_num == 1 and is_orig: # 自制视频投了且未投满
                if msgbox.askokcancel('','为这个视频再投 1 个币吗？',parent=self.window):
                    start_new_thread(coin_process,(csrf,1)) # 投 1 个币
                else:
                    return
            elif coin_num == 0 and is_orig: # 自制视频未投
                c = cusw.msgbox_askchoice(self.window,'','你要投几个币？',
                                          {'1 个币':1,'2 个币':2,'还是不投了':None}
                                          )
                if c == None:
                    return
                else:
                    start_new_thread(coin_process,(csrf,c)) # 投 c 个币
            elif coin_num == 0 and not is_orig: # 转载视频未投
                if msgbox.askokcancel('','为这个视频投 1 个币吗？',parent=self.window):
                    start_new_thread(coin_process,(csrf,1)) # 投 1 个币
                else:
                    return
        else:
            msgbox.showerror('','无法投币.\n未成功获取到 CSRF Token',parent=self.window)
            
    def collect(self):
        w = CollectWindow(self.window,self.video_data['avid'])
        if w.del_mlids or w.add_mlids:
            msgbox.showinfo('','在本次收藏操作中，\n这个视频在 %s 个收藏夹中被新添加，从 %s 个收藏夹中被删除'%(
                len(w.add_mlids),len(w.del_mlids)
                ),parent=self.window)
        if w.is_collected:
            self.button_collect.set(imglib.collect_sign)
        else:
            self.button_collect.set(imglib.collect_sign_grey)

    def _like_button_right_click(self,event):
        x = event.x_root
        y = event.y_root
        menu = tk.Menu(self.button_like,tearoff=False)
        menu.add_command(label='三连',command=self.triple)
        menu.post(x,y)

    def _cover_right_click(self,event):
        x = event.x_root
        y = event.y_root
        menu = tk.Menu(self.label_cover,tearoff=False)
        menu.add_command(label='保存封面',command=self.save_cover)
        menu.add_command(label='查看视频快照',command=self.view_videoshot)
        menu.post(x,y)

    def view_videoshot(self):
        if len(self.video_data['parts'])==1:
            w = VideoShotViewer(self.window,bvid=self.video_data['bvid'])   
            w.load()
            w.mainloop()
        else:
            ws = []
            tmp = []
            for part in self.video_data['parts']:
                tmp += [[part['title'],biliapis.second_to_time(part['length']),part['cid']]]
            indexes = PartsChooser(tmp).return_values
            cids = [self.video_data['parts'][i]['cid'] for i in indexes]
            for c in cids:
                ws += [VideoShotViewer(self.window,bvid=self.video_data['bvid'],cid=c)]
                ws[-1].load()
            ws[-1].mainloop()

    def save_cover(self):
        cover_url = self.video_data['picture']
        filename = cover_url.split('/')[-1]
        ext = os.path.splitext(filename)[-1]
        file = filedialog.asksaveasfilename(
            parent=self.window,
            initialfile=filename,
            filetypes=[("图像文件",ext)]
            )
        if file:
            try:
                biliapis.requester.download_common(cover_url,file)
            except Exception:
                msgbox.showerror('','尝试下载封面时出现错误:\n'+str(e),parent=self.window)
            else:
                msgbox.showinfo('','已成功下载封面',parent=self.window)

    def triple(self):
        def triple_process(token,coin_orig_state):
            self.task_queue.put_nowait(lambda:(
                self.button_like.configure(state='disabled'),
                self.button_coin.configure(state='disabled'),
                self.button_collect.configure(state='disabled')
                ))
            try:
                biliapis.video.triple(token,avid=self.video_data['avid'])
            except Exception as e:
                self.task_queue.put_nowait(lambda cos_=coin_orig_state:self.button_coin.configure(state=cos_))
                self.task_queue.put_nowait(lambda e_=e:msgbox.showerror('','三连失败：\n'+str(e_),parent=self.window))
            else:
                self.task_queue.put_nowait(lambda:self.button_coin.configure(state='disabled'))
                self.task_queue.put_nowait(lambda:(
                    self.button_like.set(imglib.like_sign),
                    self.button_coin.set(imglib.coin_sign),
                    self.button_collect.set(imglib.collect_sign)
                    ))
                self.task_queue.put_nowait(lambda:(
                    self.window.after(1,lambda:cusw.bubble(self.button_like,text='三连成功')),
                    self.window.after(1,lambda:cusw.bubble(self.button_coin,text='三连成功')),
                    self.window.after(1,lambda:cusw.bubble(self.button_collect,text='三连成功'))
                    ))
            finally:
                self.task_queue.put_nowait(lambda cos_=coin_orig_state:(
                    self.button_like.configure(state='normal'),
                    self.button_collect.configure(state='normal')
                    ))
            
        csrf = biliapis.login.get_csrf(biliapis.requester.cookies)
        if csrf:
            if msgbox.askokcancel('','你确定要给这个视频三连吗？\n视频将被收藏至默认收藏夹.',parent=self.window):
                cos = self.button_coin['state']
                start_new_thread(triple_process,(csrf,cos))
        else:
            msgbox.showerror('','无法三连.\n未成功获取到 CSRF Token',parent=self.window)

    def toview(self):
        def toview_process(token):
            self.task_queue.put_nowait(lambda:self.button_toview.configure(state='disabled'))
            try:
                biliapis.video.add_to_toview(token,avid=self.video_data['avid'])
            except Exception as e:
                self.task_queue.put_nowait(lambda:msgbox.showerror('','无法添加到稍后再看：\n'+str(e),parent=self.window))
            else:
                self.task_queue.put_nowait(lambda:self.window.after(1,lambda:cusw.bubble(
                    self.button_toview,f'已添加到稍后再看'
                    )))
            finally:
                self.task_queue.put_nowait(lambda:self.button_toview.configure(state='normal'))
        csrf = biliapis.login.get_csrf(biliapis.requester.cookies)
        if csrf:
            start_new_thread(toview_process,(csrf,))
        else:
            msgbox.showerror('','无法添加到稍后再看.\n未成功获取到 CSRF Token',parent=self.window)

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

    def play_video(self,audio_only=False):
        if not self.video_data:
            msgbox.showwarning('','加载尚未完成',parent=self.window)
            return
        self.button_play['state'] = 'disabled'
        self.button_play_audio['state'] = 'disabled'
        parts = self.video_data['parts']
        if len(parts) > 1:
            tmp = []
            for part in parts:
                tmp += [[part['title'],biliapis.second_to_time(part['length']),part['cid']]]
            indexes = PartsChooser(tmp).return_values
        else:
            indexes = [0]
        if indexes:
            if len(indexes) > 1:
                msgbox.showwarning('','你选择了多个分P，但一次只能播放一个啊awa',parent=self.window)
            index = indexes[0]
            part = parts[index]
            self._call_ffplay(part,index,audio_only)
        if self.is_alive():
            self.button_play['state'] = 'normal'
            self.button_play_audio['state'] = 'normal'

    def _call_ffplay(self,part,index,audio_only=False):
        def process():
            bvid = self.video_data['bvid']
            title = self.video_data['title']
            quality = config['play']['video_quality']
            try:
                if audio_only:
                    stream = biliapis.stream.get_video_stream_dash(part['cid'],bvid=bvid)['audio']
                    qs = [i['quality'] for i in stream]
                    stream = stream[qs.index(max(qs))]
                    urls = [stream['url']]
                    real_quality = bilicodes.stream_dash_audio_quality[stream['quality']]
                else:
                    stream = biliapis.stream.get_video_stream_flv(part['cid'],bvid=bvid,quality_id=quality)
                    urls = [i['url'] for i in stream['parts']]
                    real_quality = bilicodes.stream_flv_video_quality[stream['quality']]
                window_title = '[{}/P{}/{}] {} - {}'.format(bvid,index+1,real_quality,title,part['title'])
                ffdriver.call_ffplay(*urls,title=window_title,repeat=config['play']['repeat'],is_audio=audio_only,
                                     fullscreen=config['play']['fullscreen'],auto_exit=config['play']['auto_exit'])
            except Exception as e:
                self.task_queue.put_nowait(lambda e=e:msgbox.showerror('','Error:\n'+str(e),parent=self.window))
        cusw.run_with_gui(process,no_window=True)

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

    def copy_link(self):
        if not self.link:
            msgbox.showwarning('','加载尚未完成',parent=self.window)
            return
        self.button_copy_link.clipboard_clear()
        self.button_copy_link.clipboard_append(self.link)
        self.button_copy_link.configure(text='复制成功',state='disabled')
        self.window.after(800,lambda:self.button_copy_link.configure(state='normal',text='复制链接'))

    def refresh_data(self):
        def load():
            try:
                if self.abtype == 'av':
                    data = biliapis.video.get_detail(avid=self.abvid)
                    tags = biliapis.video.get_tags(avid=self.abvid)
                    self.recommend = biliapis.video.get_recommend(avid=self.abvid)
                    self.link = 'https://www.bilibili.com/video/av%s'%self.abvid
                    
                else:
                    data = biliapis.video.get_detail(bvid=self.abvid)
                    tags = biliapis.video.get_tags(bvid=self.abvid)
                    self.recommend = biliapis.video.get_recommend(bvid=self.abvid)
                    self.link = 'https://www.bilibili.com/video/'+self.abvid
            except biliapis.BiliError as e:
                if e.code in [-404,62002]:
                    self.task_queue.put_nowait(lambda:msgbox.showerror('','视频不存在',parent=self.window))
                    self.task_queue.put_nowait(self.close)
                    return
                else:
                    self.task_queue.put_nowait(lambda e=e:msgbox.showerror('意料之外的错误',str(e),parent=self.window))
                    self.task_queue.put_nowait(self.close)
                    raise e
            opener_lambda = lambda:webbrowser.open(self.link)
            self.video_data = data
            self.task_queue.put_nowait(lambda:self._prepare_recommend(len(self.recommend)))#准备相关视频的组件的存放空间
            #explorer_opener
            self.task_queue.put_nowait(lambda:self.button_open_in_ex.configure(command=opener_lambda))
            #common_info
            self.task_queue.put_nowait(lambda:self.label_avid.configure(text='AV%s'%data['avid']))
            self.task_queue.put_nowait(lambda:self.label_bvid.configure(text=data['bvid']))
            self.task_queue.put_nowait(lambda:self.label_pubtime.configure(text=time.strftime("%Y-%m-%d %a %H:%M:%S",time.localtime(data['date_publish']))))
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
            if data['is_interact_video']:
                self.task_queue.put_nowait(lambda:self.label_parts_counter.configure(text='互动视频 非传统分P'))
                self.task_queue.put_nowait(lambda:self.button_view_interact.grid())
            else:
                self.task_queue.put_nowait(lambda:fill_partlist(parts))
            #tags
            if tags:
                tagtext = '#'+'# #'.join(tags)+'#'
            else:
                tagtext = '没有标签'
            self.task_queue.put_nowait(lambda:self.set_text(self.text_tags,lock=True,text=tagtext))
            #rec_img & rec_controller_unlock
            self.task_queue.put_nowait(lambda:self.fill_recommends(-1))
            #lcfs buttons
            def check_like(avid):
                # 查询点赞状态
                try:
                    is_liked = self.is_liked = biliapis.video.is_liked(avid=avid)
                except biliapis.BiliError as e:
                    if e.code != -101:
                        raise
                self.task_queue.put_nowait(lambda:self.button_like.configure(state='normal'))
                if is_liked:
                    self.task_queue.put_nowait(lambda:self.button_like.set(imglib.like_sign))
            def check_coin(avid,is_orig):
                # 查询投币状态
                try:
                    coin = self.coined_number = biliapis.video.is_coined(avid=avid)
                except biliapis.BiliError as e:
                    if e.code != -101:
                        raise
                if coin == 0: # 没投硬币
                    self.task_queue.put_nowait(lambda:self.button_coin.configure(state='normal'))
                elif coin == 1 and is_orig: # 硬币投了但没投满
                    self.task_queue.put_nowait(lambda:self.button_coin.configure(state='normal'))
                    self.task_queue.put_nowait(lambda:self.button_coin.set(imglib.coin_sign))
                elif coin == 2 or (coin==1 and not is_orig): # 硬币投满
                    self.task_queue.put_nowait(lambda:self.button_coin.set(imglib.coin_sign))
            def check_collect(avid):
                try:
                    is_collected = self.is_collected = biliapis.video.is_collected(avid=avid)
                except biliapis.BiliError as e:
                    if e.code != -101:
                        raise
                if is_collected:
                    self.task_queue.put_nowait(lambda:self.button_collect.set(imglib.collect_sign))
                self.task_queue.put_nowait(lambda:self.button_collect.configure(state='normal'))
            start_new_thread(check_like,(data['avid'],))
            start_new_thread(check_coin,(data['avid'],data['is_original']))
            start_new_thread(check_collect(data['avid'],))
            self.task_queue.put_nowait(lambda:self.button_like.bind('<Button-3>',self._like_button_right_click))
            self.task_queue.put_nowait(lambda:self.label_cover.bind('<Button-3>',self._cover_right_click))
            self.task_queue.put_nowait(lambda:self.button_toview.configure(state='normal'))
                
        start_new_thread(load,())

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
                self.task_queue.put_nowait(lambda w=o_[4],t='%s\nav%s\n播放: %s\n弹幕: %s\n评论: %s'%(
                    self.recommend[c_]['bvid'],
                    self.recommend[c_]['avid'],
                    self.recommend[c_]['stat']['view'],
                    self.recommend[c_]['stat']['danmaku'],
                    self.recommend[c_]['stat']['reply']
                    ):o_.append(cusw.ToolTip(w,text=t)))
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

class CollectWindow(Window):
    def __init__(self,master,avid,lock_master=True):
        # 需要使用到的api:
        # biliapis.video.collect         收藏请求
        # biliapis.login.get_login_info  获取获取当前用户uid
        # biliapis.user.get_all_favlists 获取收藏夹列表
        self.avid = avid

        super().__init__('Collect av%s'%avid,True,True,config['alpha'],master=master)
        w = self.window
        w.attributes('-toolwindow',1)
        self.add_mlids = []
        self.del_mlids = []
        self.is_collected = None
        self.all_favlists = None # 存放获取到的数据
        # 滚动框架(竖直)
        self._frame_main = cusw.VerticalScrolledFrame(self.window,height=300)
        self._frame_main.grid(column=0,row=0)
        self.frame_main = self._frame_main.inner_frame
        ttk.Separator(self.frame_main,orient='horizontal').grid(ipadx=200,sticky='we',column=0,row=0)
        self.widgets_list = [] # 列表套列表套组件, 组件填充由另一个函数完成
        # overlayer: "加载中"
        self.label_overlayer = tk.Label(self.window,text='加载中',font=50)
        self.label_overlayer.grid(column=0,row=0) # 与 main frame 同处一个grid单元中, 目的是覆盖于其上
        # 确认/取消按钮
        fc = self.frame_controller = tk.Frame(self.window)
        fc.grid(column=0,row=1)
        be = self.button_ensure = ttk.Button(fc,text='确定',command=self.ensure,state='disabled')
        be.grid(column=0,row=0,padx=20)
        bc = self.button_cancel = ttk.Button(fc,text='取消',command=self.close)
        bc.grid(column=1,row=0,padx=20)
        
        ww,wh = (400,300)
        sw,sh = (w.winfo_screenwidth(),w.winfo_screenheight())
        self.window.geometry('+%d+%d'%((sw-ww)/2,(sh-wh)/2))

        self.check_schedule = None
        start_new_thread(self.load_data)

        mst_orig_state = master.attributes('-disabled')
        mst_orig_tpmst = master.attributes('-topmost')
        if lock_master:
            master.attributes('-disabled',1)
        self.mainloop()
        master.attributes('-disabled',mst_orig_state)
        master.attributes('-topmost',0)
        master.attributes('-topmost',1)
        master.attributes('-topmost',mst_orig_tpmst)

    # 丢子线程里跑
    def load_data(self):
        try:
            if not biliapis.login.get_csrf(biliapis.requester.cookies):
                raise biliapis.BiliError(-101,'账号未登录')
            uid = biliapis.login.get_login_info()['uid']
            afl = self.all_favlists = biliapis.user.get_all_favlists(uid,avid=self.avid)['list']
        except Exception as e:
            self.task_queue.put_nowait(lambda e=e:msgbox.showerror('','加载数据失败：\n'+str(e),parent=self.window))
            self.task_queue.put_nowait(self.close)
            return
        else:
            self.task_queue.put_nowait(lambda data=afl:self.fill_main_frame(data))
        
    def ensure(self):
        orig_states = [i['fav_state'] for i in self.all_favlists]
        new_states = [i[1].get() for i in self.widgets_list]
        for i in range(len(orig_states)):
            mlid = self.all_favlists[i]['mlid']
            if orig_states[i] and not new_states[i]:
                self.del_mlids.append(mlid)
            elif not orig_states[i] and new_states[i]:
                self.add_mlids.append(mlid)
        start_new_thread(self.collect_process)

    # 丢子线程里跑
    def collect_process(self):
        if not self.add_mlids and not self.del_mlids:
            self.task_queue.put_nowait(lambda:msgbox.showerror('','没有对收藏夹做任何更改',parent=self.window))
            return
        self.task_queue.put_nowait(lambda:(
            self.button_ensure.configure(state='disabled'),
            self.button_cancel.configure(state='disabled'),
            self.label_overlayer.configure(text='正在执行操作'),
            self.label_overlayer.grid()
            ))
        csrf = biliapis.login.get_csrf(biliapis.requester.cookies)
        try:
            if not csrf:
                raise biliapis.BiliError(-101,'账号未登录')
            biliapis.video.collect(csrf,self.avid,self.add_mlids,self.del_mlids)
            self.is_collected = biliapis.video.is_collected(avid=self.avid)
        except Exception as e:
            self.task_queue.put_nowait(lambda e=e:msgbox.showerror('','无法执行收藏操作：\n'+str(e),parent=self.window))
        finally:
            self.task_queue.put_nowait(self.close)

    def check(self):
        orig_states = [i['fav_state'] for i in self.all_favlists]
        new_states = [i[1].get() for i in self.widgets_list]
        if orig_states == new_states:
            self.button_ensure['state'] = 'disabled'
        else:
            self.button_ensure['state'] = 'normal'
        self.check_schedule = self.window.after(50,self.check)
        
    def fill_main_frame(self,favlists):
        wl = self.widgets_list
        fm = self.frame_main
        row = 1 # 分割线占了r0, 于是从1始计
        for fav in favlists:
            f = tk.Frame(fm,relief='groove',bd=1)
            f.grid(column=0,row=row,sticky='we')
            self._frame_main._bind_scroll_event(f)
            # index 索引说明
            # 0 每行的框架
            # 1 每行的 checkbutton 的 boolvar
            # 2 每行的 checkbutton
            # 3 每行的标题 label
            # 4 每行的内容数指示 label
            # 5 每行的 mlid 指示 label
            wl.append([f])
            wl[-1].append(tk.BooleanVar(self.window,value=fav['fav_state']))
            wl[-1].append(ttk.Checkbutton(f,onvalue=True,offvalue=False,text='',variable=wl[-1][1],state=(
                                          {False:'normal',True:'disabled'}[fav['count']>=1000 and not fav['fav_state']]
                                          )))
            wl[-1][-1].grid(column=0,row=0,rowspan=2,padx=10,pady=10)
            wl[-1].append(tk.Label(f,text=fav['title'],justify='left',font=20))
            wl[-1][-1].grid(column=1,row=0,columnspan=2,sticky='w')
            wl[-1].append(tk.Label(f,text='%s 个内容'%fav['count'],justify='left'))
            wl[-1][-1].grid(column=1,row=1,sticky='w')
            #wl[-1].append(tk.Label(f,text='mlid%s'%fav['mlid'],justify='right'))
            #wl[-1][-1].grid(column=2,row=1,sticky='e')
            for w in wl[-1][2:]:
                self._frame_main._bind_scroll_event(w)
            row += 1

        self.label_overlayer.grid_remove()
        self.check_schedule = self.window.after(10,self.check)

class LoginWindow(Window):
    # 会直接对requester里的cookies做修改
    def __init__(self):
        super().__init__('BiliTools - Login',True,True)
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
        self.label_text['text'] = {0:'登录成功',-1:'密钥错误',-2:'二维码已超时',-4:'使用B站客户端扫描二维码以登录',-5:'在手机上确认登录'}[self.condition]
        if self.condition == 0:
            cookiejar = biliapis.login.make_cookiejar(self.final_url)
            cookiejar.save(biliapis.requester.local_cookiejar_path)
            biliapis.requester.cookies = cookiejar
            apply_proxy_config()
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
        self.section_tabs[-1] += [ttk.Button(self.section_tabs[-1][5],text='查看选中项的弹幕增量趋势',command=lambda tbi=tab_index,sei=section_index:self._see_pbp(tbi,sei))] #
        self.section_tabs[-1][8].grid(column=2,row=1)
        self.section_tabs[-1] += [tk.BooleanVar(self.section_tabs[-1][5],False)]
        self.section_tabs[-1] += [ttk.Checkbutton(self.section_tabs[-1][5],text='仅音轨',onvalue=True,offvalue=False,variable=self.section_tabs[-1][9])]
        self.section_tabs[-1][10].grid(column=0,row=0,sticky='w')
        self.section_tabs[-1] += [ttk.Button(self.section_tabs[-1][5],text='播放选中项',command=lambda tbi=tab_index,sei=section_index:self._play_video(tbi,sei))]
        self.section_tabs[-1][11].grid(column=1,row=0)

    def _play_video(self,tab_index,section_index=-1):
        if not self.media_data:
            raise RuntimeError('Not loaded yet.')
        button = self.section_tabs[tab_index][11]
        button['state'] = 'disabled'
        #此函数供section_tabs内的按钮调用
        ep_indexes = []
        for item in self.section_tabs[tab_index][2].selection():
            ep_indexes.append(int(self.section_tabs[tab_index][2].item(item,"values")[0])-1)
        if ep_indexes:
            if len(ep_indexes) > 1:
                msgbox.showwarning('','若选中多项则只播放第一项',parent=self.window)
            index = ep_indexes[0]
            if section_index == -1:
                ep = self.media_data['episodes'][index]
            else:
                ep = self.media_data['sections'][section_index]['episodes'][index]
            self._call_ffplay(ep,self.section_tabs[tab_index][9].get())
        else:
            msgbox.showwarning('','你什么都没选中',parent=self.window)
        button['state'] = 'normal'

    def _call_ffplay(self,ep,audio_only=False):
        #供self._play_video调用
        def process():
            try:
                if audio_only:
                    stream = biliapis.stream.get_video_stream_dash(ep['cid'],bvid=ep['bvid'])
                    qs = [i['quality'] for i in stream['audio']]
                    astream = stream['audio'][qs.index(max(qs))]
                    urls = [astream['url']]
                    title = '[Ep{}/AudioOnly/{}] {} - {}: {}'.format(ep['epid'],bilicodes.stream_dash_audio_quality[astream['quality']],ep['media_title'],ep['section_title'],ep['title'])
                else:
                    stream = biliapis.stream.get_video_stream_flv(ep['cid'],bvid=ep['bvid'],quality_id=config['play']['video_quality'])
                    urls = [i['url'] for i in stream['parts']]
                    title = '[Ep{}/{}] {} - {}: {}'.format(ep['epid'],bilicodes.stream_flv_video_quality[stream['quality']],ep['media_title'],ep['section_title'],ep['title'])
                ffdriver.call_ffplay(*urls,title=title,is_audio=audio_only,repeat=config['play']['repeat'],
                                     fullscreen=config['play']['fullscreen'],auto_exit=config['play']['auto_exit'])
            except Exception as e:
                self.task_queue.put_nowait(lambda e=e:msgbox.showerror('','Error:\n'+str(e),parent=self.window))
        cusw.run_with_gui(process,no_window=True)

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
            self.task_queue.put_nowait(lambda mdid=self.media_data['mdid']:self.button_view_on_browser.configure(
                command=lambda mdid=mdid:webbrowser.open('https://www.bilibili.com/bangumi/media/md{}/'.format(mdid))
                ))
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
        self.om_main_zone = ttk.OptionMenu(self.frame_filter,self.strvar_main_zone,'All','All',*list(bilicodes.video_zone_main.values()),command=self._update_zone_om)
        self.om_main_zone.grid(column=5,row=0)
        self.strvar_child_zone = tk.StringVar(value='All')
        self.om_child_zone = ttk.OptionMenu(self.frame_filter,self.strvar_child_zone,'All','All',*list(bilicodes.video_zone_child.values()))
        self.om_child_zone.grid(column=6,row=0)
        self.om_child_zone.grid_remove()
        self.zone = {v:k for k,v in bilicodes.video_zone_main.items()}
        self.zone.update({v:k for k,v in bilicodes.video_zone_child.items()})
        
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
                l += [cusw.ImageLabel(l[0],width=200,height=122,cursor='hand2')]
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
        

    def _fast_download(self,bvid,audiostream_only=False):
        path = filedialog.askdirectory(title='下载到',parent=self.master)
        if path:
            download_manager.task_receiver('video',path,bvid=bvid,audiostream_only=audiostream_only)
        
    def _right_click(self,event,bvid):
        x = event.x_root
        y = event.y_root
        menu = tk.Menu(self.inner_frame,tearoff=False)
        menu.add_command(label='跳转',command=lambda bvid=bvid:self.jump_by_bvid(bvid))
        menu.add_command(label='下载所有分P',command=lambda bvid=bvid:self._fast_download(bvid=bvid))
        menu.add_command(label='抽取所有分P的音轨',command=lambda bvid=bvid:self._fast_download(bvid=bvid,audiostream_only=True))
        menu.post(x,y)

    def _update_zone_om(self,main_var=None):
        if not main_var:
            main_var = self.strvar_main_zone.get()
        if main_var == 'All':
            self.om_child_zone.set_menu('All','All')
            self.om_child_zone.grid_remove()
        else:
            self.om_child_zone.set_menu('All','All',*[bilicodes.video_zone_child[tid] for tid in bilicodes.video_zone_relation[self.zone[main_var]]])
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
                    self.task_queue.put_nowait(lambda:msgbox.showwarning('','没有搜索结果',parent=self.master))
                    
        kwargs = {
            'duration':self.strvar_duration.get(),
            'sort':self.strvar_sort.get(),
            'zone':self._get_zone(),
            'page':page,
            'kws':kws
            }
        cusw.run_with_gui(tmp,kwargs=kwargs,master=self.master,no_window=True)
        return self.page,self.total_page

    def refresh(self):
        if self.kws:
            self.search(*self.kws,page=1)

    def turn_page(self,page):
        if self.kws:
            if page > self.total_page or page < 1:
                msgbox.showerror('','超出页数范围.',parent=self.master)
            else:
                self.search(*self.kws,page=page)
                self.scroll_to_top()
        return self.page,self.total_page
    
#yeeeeee 套用模板的屑
#没写完
class _MediaSearchShower(cusw.VerticalScrolledFrame):
    def __init__(self,master,task_queue,media_type=0,height=400): #media_type: 0:番剧; 1:影视
        #需要传入父组件的task_queue以执行多线程任务
        super().__init__(master=master,height=height)
        self.kws = None
        self.page = 1
        self.total_page = 1
        self.media_type = media_type
        self.task_queue = task_queue
        columnnum = 1
        rownum = 20
        self.page_size = columnnum*rownum #此值必须为20
        
        #刷新按钮
        self.button_refresh = ttk.Button(self.inner_frame,text='刷新',command=self.refresh)
        self.button_refresh.grid(column=0,row=0,sticky='w')
        
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
                #1:封面(imagelabel)
                #2:标题(entry)
                #3:评分(label)
                #4-7:风格地区时间参演(entry)
                #8:简介
                #wwwwww
                l += [tk.Frame(self.frame_result)]
                l[0].grid(column=x,row=y,pady=5)
                l[0].grid_remove()
                l += [cusw.ImageLabel(l[0],width=285,height=380)]
                l[1].grid(column=0,row=0,rowspan=3)
                tf = tk.Frame(l[0])
                tf.grid(column=1,row=0)
                l += [tk.Entry(tf,bg='#f0f0f0',bd=0,width=30,state='disabled',font=('Microsoft YaHei UI',30))]
                l[2].grid(column=0,row=0)
                l += [tk.Label(tf,text='-')]
                l[3].grid(column=1,row=0)
                sf = tk.Frame(l[0])
                sf.grid(column=1,row=1,sticky='nwe')
                tk.Label(sf,text='风格:').grid(column=0,row=0,sticky='w')
                l += [tk.Entry(sf,bg='#f0f0f0',bd=0,width=35,state='disabled')]
                l[4].grid(column=1,row=0)
                tk.Label(sf,text='地区:').grid(column=2,row=0,sticky='w')
                l += [tk.Entry(sf,bg='#f0f0f0',bd=0,width=35,state='disabled')]
                l[5].grid(column=3,row=0)
                tk.Label(sf,text='时间:').grid(column=0,row=1,sticky='w')
                l += [tk.Entry(sf,bg='#f0f0f0',bd=0,width=35,state='disabled')]
                l[6].grid(column=1,row=1)
                tk.Label(sf,text='参演:').grid(column=2,row=1,sticky='w')
                l += [tk.Entry(sf,bg='#f0f0f0',bd=0,width=35,state='disabled')]
                l[7].grid(column=3,row=1)
                l += [tk.Text(l[0],bg='#f0f0f0',bd=0,width=70,height=10,state='disabled')]
                l[8].grid(column=1,row=2)
                
                
                
                self.tk_objs.append(l)

    def search(self,*kws,page=1):
        if not kws:
            return
        def tmp(duration,sort,zone,page,kws):
            try:
                data = {0:biliapis.media.search_bangumi,1:biliapis.media.search_ft}[int(self.media_type)](*kws,page=page)
            except biliapis.BiliError as e:
                self.task_queue.put_nowait(lambda e=e:msgbox.showerror('','BiliError code {}:\n{}'.format(e.code,e.msg),parent=self.master))
                return
            except Exception as e:
                self.task_queue.put_nowait(lambda e=e:msgbox.showerror('',str(e),parent=self.master))
                if development_mode:
                    raise e
                return
            else:
                self.task_queue.put_nowait(lambda t=data['time_cost']:self.label_searchtime.configure(text=f'搜索用时: {t}s'))
                self.task_queue.put_nowait(lambda c=data['result_count']:self.label_searchcount.configure(text=f'共有 {c} 个结果'))
                self.total_page = data['total_pages']
                self.page = page
                self.kws = kws
                def fill_data(widgetlist,dataobj):
                    pass
                    
                def clear_data(widgetlist):
                    pass
                
                if data['result']:
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
                    self.task_queue.put_nowait(lambda:msgbox.showwarning('','没有搜索结果',parent=self.master))
                    
        kwargs = {
            'page':page,
            'kws':kws
            }
        cusw.run_with_gui(tmp,kwargs=kwargs,master=self.master,no_window=True)
        return self.page,self.total_page

    def refresh(self):
        if self.kws:
            self.search(*self.kws,page=1)

    def turn_page(self,page):
        if self.kws:
            if page > self.total_page or page < 1:
                msgbox.showerror('','超出页数范围.',parent=self.master)
            else:
                self.search(*self.kws,page=page)
                self.scroll_to_top()
        return self.page,self.total_page

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
        ww,wh = (1125,650)
        sw,sh = (self.window.winfo_screenwidth(),self.window.winfo_screenheight())
        self.window.geometry('%dx%d+%d+%d'%(ww,wh,(sw-ww)/2,(sh-wh)/2-40))
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
        #翻页姬
        self.frame_pgturner = tk.Frame(self.window)
        self.frame_pgturner.grid(column=0,row=2)
        self.frame_pgturner.grid_remove()
        self.button_last = ttk.Button(self.frame_pgturner,text='上一页',command=lambda:self.turn_page(offset=-1))
        self.button_last.grid(column=0,row=0)
        self.label_page = tk.Label(self.frame_pgturner,text='-/- 页')
        self.label_page.grid(column=1,row=0)
        self.button_next = ttk.Button(self.frame_pgturner,text='下一页',command=lambda:self.turn_page(offset=1))
        self.button_next.grid(column=2,row=0)
        self.entry_page = ttk.Entry(self.frame_pgturner,exportselection=0,width=10)
        self.entry_page.grid(column=0,row=1,columnspan=2,sticky='e')
        self.entry_page.bind('<Return>',self._jump_page)
        self.button_tp = ttk.Button(self.frame_pgturner,text='跳页',command=lambda:self._jump_page)
        self.button_tp.grid(column=2,row=1)

        if init_kws:
            self.search(*init_kws)
            self.entry.insert('end',' '.join(init_kws))
        #self.mainloop()

    def _jump_page(self,event=None):
        try:
            self.turn_page(page=int(self.entry_page.get().strip()))
        except ValueError:
            msgbox.showwarning('','输入的不是数字.',parent=self.window)

    def search(self,*kws):
        self.button_start['state'] = 'disabled'
        if not kws:
            kws = self.entry.get().strip().split()
        if kws: 
            target = self.nb.children[self.nb.select().split('.')[-1]]
            p,tp = target.search(*kws)
            self.label_page.configure(text='{}/{}'.format(p,tp))
            self.frame_pgturner.grid()
        else:
            msgbox.showwarning('','关键字列表为空.',parent=self.window)
        self.button_start['state'] = 'normal'

    def turn_page(self,offset=None,page=None):
        target = self.nb.children[self.nb.select().split('.')[-1]]
        self.button_next['state'] = 'disabled'
        self.button_last['state'] = 'disabled'
        self.button_tp['state'] = 'disabled'
        if page:
            p,tp = target.turn_page(page)
            self.label_page.configure(text='{}/{}'.format(p,tp))
        if offset:
            p,tp = target.turn_page(target.page+offset)
            self.label_page.configure(text='{}/{}'.format(p,tp))
        self.button_next['state'] = 'normal'
        self.button_last['state'] = 'normal'
        self.button_tp['state'] = 'normal'
        
    def set_nb_state(self,nb,state='normal'):
        for i in range(len(nb.tabs())):
            nb.tab(i,state=state)

# 互动视频剧情图展示器, 虽然写得依托答辩但还是放上来吧
# 还在plot_drawer.py里做完善
# 原本还打算做另一个生成模式, 但越写越乱所以还是算了罢
# 正在做交互
# 测试用↓
# (957032264,'BV1zY411177B')
# (245682070,'BV1UE411y7Wy')
# (512487448,'BV1Du411Q7jf')
class PlotShower(Window):
    def __init__(self,master,cid,bvid):
        self.cid = cid
        self.bvid = bvid
        self.graph_id = None
        self.cfg = { # 画图参数
            'plot_w':150, #plot块的宽
            'plot_h':75, #plot块的高
            'empty_w':150, #横向间距
            'min_empty_h':100, #最小的纵向间距
            'top_reserve':75, #顶部保留区域
            'bot_reserve':75, #底部保留区域
            'toptrace_y':5, #顶部plot跳转线的起始y坐标
            'bottrace_y':-5, #底部plot跳转线的相对画布底部的起始y坐标
            'bezcurve_kp_offset':25, 
            'jump_stretchout':20, #plot跳转线从plot块向前伸出的距离
            'jump_x_offset':5, #plot跳转线之间的横向间距
            'jump_y_offset':5  #plot跳转线之间的纵向间距
            }
        self.plots = []
        self.explored_plot_ids = {} # plot_id:(layer_index, in-layer_index) # e.g.第5层第1个:(4,0)
        # plot_id 在B站API中被描述为 edge_id
        # self.plots 注解
        # 类似于树的结构?
        # layer 0 [ {Root Plot} ]
        # layer 1 [ {Plot 1}, {Plot 2} ]
        # layer 2 [ {Plot 3}, {Plot 4}, {Plot 5}, {Plot 6} ]
        # ...
        # ↑大概就像这样
        self.is_explored = False
        self.is_drawn = False
        self.plot_coors = {} # plot_id:(x,y,w,h) # 便于draw函数连接各个plot块
        self.selected_plot = (None,None) # (plot_id, canvasItemId)
        self.sidebar_state = 'hide' # show / hide
        self.sidebar_width = 300
        self.sidebar_min_height = 500
        self.last_cfg_event = None
        self.explore_callback_dict = {}

        self.cid_map = {} # pid: cid
        self.avid_map = {} # cid: avid

        super().__init__('BiliTools - PlotShower of %s'%bvid,True,config['topmost'],config['alpha'],master=master)
        w = self.window
        w.resizable(True,True)
        w.geometry('700x400')
        w.minsize(300,250)
        
        # 画布区域
        cv = self.canvas = tk.Canvas(w,height=w.winfo_height()-50,width=w.winfo_width()-25)
        cv.grid(column=0,row=0)
        sx = self.scbar_x = ttk.Scrollbar(w,orient=tk.HORIZONTAL,command=cv.xview)
        sx.grid(column=0,row=1,sticky='we')
        sy = self.scbar_y = ttk.Scrollbar(w,orient=tk.VERTICAL,command=cv.yview)
        sy.grid(column=1,row=0,sticky='sn')
        cv.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
        w.bind('<Configure>',self._config_event)
        
        # 底部功能按键区域
        fc = self.frame_console = tk.Frame(w)
        fc.grid(column=0,row=2,columnspan=2,sticky='we')
        bdl = self.button_download_bottom = ttk.Button(
            fc,text='下载全部剧情',
            command=lambda:self.download_all_plots(audio_only=False,button_to_lock=self.button_download_bottom),
            state='disabled'
            )
        bdl.grid(column=0,row=0)
        #bsv = self.button_save_plots = ttk.Button(fc,text='保存剧情图数据')
        
        # 拖动相关参数和变量
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_speed_reduce = -50
        
        # 侧边栏区域
        self.detail_text_width = 39
        #fd = self.frame_detail = tk.Frame(w)
            # 进行一个偷梁换柱
        fd = self.frame_detail = cusw.VerticalScrolledFrame(w, height=w.winfo_height())
        #ttk.Separator(fd.inner_frame).grid(ipadx=self.sidebar_width)
        fd.grid(column=2,row=0,rowspan=2) #
        fd.grid_remove() #
        fd = fd.inner_frame
        # 框架内布置
            # 剧情图封面
    #    self.imglabel_cover = cusw.ImageLabel(
    #        fd, width=self.sidebar_width-25, height=int((self.sidebar_width-25)*(9/16)))
    #    self.imglabel_cover.grid(column=0, row=0, columnspan=2)
            # 剧情图EdgeID
        le = self.label_edgeid = tk.Label(fd, text='EdgeID -')
        le.grid(column=0,row=1,columnspan=2,sticky='w')
            # 剧情图标题
        lt = self.label_title = tk.Label(fd, text='TITLE')
        lt.grid(column=0,row=2,columnspan=2,sticky='w')
            # 剧情图cID
        lc = self.label_cid = tk.Label(fd, text='cID -')
        lc.grid(column=0,row=3,columnspan=2,sticky='w')
            # 剧情图问题区
        fq = self.frame_question = tk.LabelFrame(fd, text='Question')
        fq.grid(column=0,row=4,columnspan=2)
                # 问题参数
    #    tqt = self.label_quescontent = tk.Text(fd)
    #    tqt.grid()
        tl = self.label_timelimit = tk.Label(fq, text='限时 -s')
        tl.grid(column=0,row=0,sticky='w')
        ps = self.label_pause_or_not = tk.Label(fq, text='回答时视频会暂停')
        ps.grid(column=0,row=1,sticky='w')
                # 4个选项的参数(最多4个选项)
        fos = self.frames_option = [
            [tk.LabelFrame(fq, text='选项1')],
            [tk.LabelFrame(fq, text='选项2')],
            [tk.LabelFrame(fq, text='选项3')],
            [tk.LabelFrame(fq, text='选项4')]
            ]
        bdpv = self.button_downpv = ttk.Button(fd, text='下载视频')
        bdpv.grid(column=0,row=5,sticky='w')
        bdpa = self.button_downpa = ttk.Button(fd, text='抽取音频')
        bdpa.grid(column=0,row=6,sticky='w')
        bvv = self.button_view_vars = ttk.Button(fd, text='查看变量')
        bvv.grid(column=0,row=7,sticky='w')
        sprt = self.bar_separator = ttk.Separator(fd)
        sprt.grid(column=0,row=10,ipadx=142,sticky='s')
        for i in range(len(fos)):
            fos[i][0].grid(column=0,row=2+i)
            # 可变文本 存入列表 后续会根据选中的块进行修改
            fos[i] += [
                tk.Text(fos[i][0],width=self.detail_text_width, # 1
                        bg='#f0f0f0',bd=0,height=2,state='disabled'), # 选项内容
                tk.Label(fos[i][0], text='EdgeID -'), # 点击后跳转到的edgeID # 2
                tk.Frame(fos[i][0]) # 3 !
                ]
            fos[i] += [
                tk.Text(fos[i][3],width=self.detail_text_width, # 4
                        bg='#f0f0f0',bd=0,height=5,state='disabled'), # 点击后执行的运算语句们 用\n分割
                tk.Frame(fos[i][0]) # 5 !
                ]
            fos[i] += [
                tk.Text(fos[i][5],width=self.detail_text_width, # 6
                        bg='#f0f0f0',bd=0,height=2,state='disabled'), # 选项出现的条件
                ]
            # index 0 是容纳以上组件的框架
            fos[i][1].grid(column=0,row=0,sticky='w',columnspan=2)
            fos[i][2].grid(column=1,row=1,sticky='w')
            fos[i][3].grid(column=0,row=3,sticky='w',columnspan=2)
            fos[i][4].grid(column=0,row=1)
            fos[i][5].grid(column=0,row=5,sticky='w',columnspan=2)
            fos[i][6].grid(column=0,row=1)
            # 固定的提示性文本
            tk.Label(fos[i][0], text='跳转至:').grid(column=0,row=1,sticky='w')
            tk.Label(fos[i][3], text='进行以下变量运算:').grid(column=0,row=0,sticky='w')
            tk.Label(fos[i][5], text='满足以下条件时出现:').grid(column=0,row=0,sticky='w')
        
        # Overlayer区域
        fo = self.frame_overlayer = tk.Frame(w)
        fo.grid(column=0,row=0,columnspan=3,rowspan=3,ipadx=w.winfo_width(),ipady=w.winfo_height())
        les = self.label_explore_status = tk.Label(fo,text='剧情图未探索')
        les.grid(column=0,row=0,sticky='s')
        lep = self.label_explore_progress = tk.Label(fo,text='第 - 层\nEdgeID - \nTITLE')
        lep.grid(column=0,row=1,sticky='n',pady=10)
        
        
        self.canvas.bind('<B1-Motion>',self._drag_moving)
        self.canvas.bind('<Button-1>',self._drag_start)

    def init(self):
        self.explore_callback_dict = {
            'layer':0,
            'edge_id':1,
            'title':''
            }
        self.label_explore_status['text'] = '正在探索剧情图...'
        t = threading.Thread(target=self.explore,kwargs={'callback_dict':self.explore_callback_dict},daemon=True)
        t.start()
        self.window.after(10,self._init_check)

    def _init_check(self):
        if self.is_explored:
            self.draw()
            self.label_explore_status['text'] = '完成'
            self.window.after(800,lambda:self.frame_overlayer.grid_remove())
            self.button_download_bottom['state'] = 'normal'
        else:
            self.label_explore_progress['text'] = '第 {layer} 层\nEdgeID {edge_id}\n{title}'.format(
                **self.explore_callback_dict
                )
            self.window.after(50,self._init_check)
        
    def _drag_start(self,event):
        #print('啊？')
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def _drag_moving(self,event):
        #print('正在被撅')
        self.canvas.xview_scroll(int((event.x-self.drag_start_x)/self.drag_speed_reduce),'units')
        self.canvas.yview_scroll(int((event.y-self.drag_start_y)/self.drag_speed_reduce),'units')
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def fill_detail_area(self,pid):
        i1,i2 = self.explored_plot_ids[pid]
        data = self.plots[i1][i2]
        #cover_url = data[]
        self.label_edgeid['text'] = 'EdgeID %s'%data['edge_id']
        self.label_title['text'] = data['title']
        if pid in self.cid_map:
            self.label_cid['text'] = 'cID %s'%self.cid_map[pid]
        self.button_downpv['command'] = lambda pid_=pid:self.download_single_plot(pid=pid_,audio_only=False,button_to_lock=self.button_downpv)
        self.button_downpa['command'] = lambda pid_=pid:self.download_single_plot(pid=pid_,audio_only=True,button_to_lock=self.button_downpa)
        self.button_view_vars['command'] = lambda pid_=pid:self.show_vars(pid=pid_)
        q = data['question']
        if q:
            self.frame_question.grid()
        else:
            self.frame_question.grid_remove()
            return
        if q['time_limit'] == -1:
            self.label_timelimit['text'] = '不限时'
        else:
            self.label_timelimit['text'] = '限时 %ds'%q['time_limit']
        self.label_pause_or_not['text'] = {
            True:'回答时视频会暂停',
            False:'直接进入默认选项'
            }[q['pause']]
        # 填充选项
        fos = self.frames_option
        for i in range(len(fos)):
            if i<=len(q['choices'])-1:
                fos[i][0].grid()
                c = q['choices'][i]
                l = '选项%d'%(i+1)
                if c['is_default']:
                    l += ' [默认]'
                if c['is_hidden']:
                    l += ' [隐藏]'
                fos[i][0]['text'] = l
                self.set_text(fos[i][1],lock=True,text=c['text'])
                fos[i][2]['text'] = 'EdgeID %d'%c['jump_edge_id']
                if c['var_operations']:
                    self.set_text(fos[i][4],lock=True,text='\n'.join(c['var_operations']))
                    fos[i][3].grid()
                else:
                    fos[i][3].grid_remove()
                if c['appear_condition']:
                    self.set_text(fos[i][6],lock=True,text=c['appear_condition'])
                    fos[i][5].grid()
                else:
                    fos[i][5].grid_remove()
                
            else:
                fos[i][0].grid_remove()

    def show_vars(self,pid):
        i1,i2 = self.explored_plot_ids[pid]
        plot = self.plots[i1][i2]
        if plot['vars']:
            head = ['变量名称','ID_v1','ID_v2','是否随机','是否展示']
            tables = [[d['name'],d['id_v1'],d['id_v2'],str(d['is_random']),str(d['display'])] for d in plot['vars']]
            # msgbox.showinfo(
            #     'Vars of Edge ID %s'%plot['edge_id'],
            #     head+'\n'+tables,
            #     parent=self.window
            #     )
            w = tk.Toplevel(self.window)
            w.resizable(False,False)
            w.title('Vars of EdgeID %s'%plot['edge_id'])
            f = tk.Frame(w)
            f.grid(column=0,row=0,padx=10,pady=10)
            for i in range(len(head)):
                tk.Label(f,text=head[i]).grid(sticky='w',column=i,row=0,padx=5)
            for i in range(len(tables)):
                for o in range(len(tables[i])):
                    tk.Label(f,text=tables[i][o]).grid(sticky='w',column=o,row=i+1,padx=5)
            w.wait_window(w)
        else:
            msgbox.showinfo('','此节点没有变量',parent=self.window)

    def play_plot(self,pid):
        i1,i2 = self.explored_plot_ids[pid]
        data = self.plots[i1][i2]

    def download_specific_plot(self, button_to_lock=None):
        if button_to_lock:
            button_to_lock['state'] = 'disabled'
        path = filedialog.askdirectory(title='选择保存位置',parent=self.window)
        if path:
            bvid = self.bvid
            main_video_data = biliapis.video.get_detail(bvid=bvid)
            plot_table = []

    def download_single_plot(self,pid,audio_only=False,button_to_lock=None):
        i1,i2 = self.explored_plot_ids[pid]
        data = self.plots[i1][i2]
        cid = self.cid_map[pid]
        if button_to_lock:
            button_to_lock['state'] = 'disabled'
        path = filedialog.askdirectory(title='选择保存位置',parent=self.window)
        if path:
            download_manager.task_receiver('video',path,bvid=self.bvid,is_interact=True,data=data.copy(),audiostream_only=audio_only,cid=cid)
        if self.is_alive() and button_to_lock:
            button_to_lock['state'] = 'normal'

    def download_all_plots(self, audio_only=False, button_to_lock=None):
        if button_to_lock:
            button_to_lock['state'] = 'disabled'
        path = filedialog.askdirectory(title='选择保存位置',parent=self.window)
        if path:
            bvid = self.bvid
            main_video_data = biliapis.video.get_detail(bvid=bvid)
            for layer in self.plots:
                for plot in layer:
                    pid = plot['edge_id']
                    cid = self.cid_map[pid]
                    download_manager.task_receiver(
                        'video',
                        path,
                        bvid=bvid,
                        is_interact=True,
                        data=plot.copy(),
                        audiostream_only=audio_only,
                        cid=cid,
                        video_data=main_video_data.copy()
                        )
        if self.is_alive() and button_to_lock:
            button_to_lock['state'] = 'normal'

    def _config_event(self,event=None):
        if self.sidebar_state == 'show':
            self.canvas.configure(
                width=self.window.winfo_width()-25-self.sidebar_width,
                height=self.window.winfo_height()-50
                )
            self.window.minsize(300+self.sidebar_min_height,250+self.sidebar_width)
        else:
            self.canvas.configure(
                width=self.window.winfo_width()-25,
                height=self.window.winfo_height()-50
                )
            self.window.minsize(300,250)
        self.last_cfg_event = event
        self.frame_detail.set_height(self.window.winfo_height()-25)

    def set_sidebar_state(self,state):
        if state == 'show':
            if self.sidebar_state != 'show':
                self.sidebar_state = 'show'
                self.frame_detail.set_height(self.window.winfo_height()-25) #
                self.frame_detail.grid()
        else:
            if self.sidebar_state != 'hide':
                self.sidebar_state = 'hide'
                self.frame_detail.grid_remove()
        self._config_event()

    def explore(self, callback_func=None, callback_dict=None): # 耗时, 丢子线程里, 仅需调用一次
        # callback_func接受3个参数
        # - 当前剧情图所在的layer(int)
        # - 当前剧情图的 Edge ID
        # - 当前剧情图的标题
        # 每探索到一个剧情图就回调一次
        # ..._dict同理 只是把调用变成了修改
        bvid = self.bvid
        gid = self.graph_id = biliapis.video.get_interact_graph_id(self.cid,bvid=bvid)
        root_plot = biliapis.video.get_interact_edge_info(gid,bvid=bvid)
        self.plots += [[root_plot]]
        self.explored_plot_ids[root_plot['edge_id']] = (0,0)
        plots = [root_plot]
        next_layer = []
        layer_num = 1
        while True: # 大循环: plots的深度
            for plot in plots:
                #breakpoint()
                if plot['question']:
                    next_layer += [i['jump_edge_id'] for i in plot['question']['choices']]
            next_layer = remove_repeat(next_layer)
            if next_layer:
                #print('Next:',next_layer)
                pass
            else:
                #breakpoint()
                #print('MISSION ACCOMPLISHED!')
                break
            #print('Layer',layer_num)
            plots = []
            self.plots.append([])
            i = 0
            for pid in next_layer: # 小循环: plots每层中的plot
                if pid in self.explored_plot_ids:
                    continue
                plot = biliapis.video.get_interact_edge_info(gid,bvid=bvid,edge_id=pid)
                #print('Fetched:',pid)
                if callback_func:
                    callback_func(layer_num, pid, plot['title'])
                if callback_dict:
                    callback_dict['layer'] = layer_num
                    callback_dict['edge_id'] = pid
                    callback_dict['title'] = plot['title']
                if plot['question']:
                    plots.append(plot)
                    for choice in plot['question']['choices']:
                        self.cid_map[choice['jump_edge_id']] = choice['jump_cid']
                self.plots[-1].append(plot)
                # 试图录入cid信息
                for story in plot['story_list']:
                    self.cid_map[story['edge_id']] = story['cid']
                for part in plot['preload_parts']:
                    #self.cid_map[]
                    self.avid_map[part['cid']] = part['avid']
                    
                self.explored_plot_ids[plot['edge_id']] = (layer_num,i)
                i += 1
                time.sleep(0.2)
            next_layer = []
            layer_num += 1
        self.is_explored = True
        #self.frame_overlayer.grid_remove()

    def draw(self): # 需要预先调用 self.explore()
        if not self.is_explored:
            return
        cfg = self.cfg
        # 相关参数
        plot_w = cfg['plot_w']
        plot_h = cfg['plot_h']
        empty_w = cfg['empty_w']
        min_empty_h = cfg['min_empty_h']
        top_reserve = cfg['top_reserve']
        bot_reserve = cfg['bot_reserve']
        max_plotnum = max([len(i) for i in self.plots])
        tth = max_plotnum*plot_h+(max_plotnum-1)*min_empty_h # total height
        ttw = len(self.plots)*plot_w+(len(self.plots)-1)*empty_w # total width
        toptrace_y = cfg['toptrace_y']
        bottrace_y = tth+top_reserve+bot_reserve+cfg['bottrace_y']
        bezcurve_kp_offset = cfg['bezcurve_kp_offset']
        jump_stretchout = cfg['jump_stretchout']
        jump_x_offset = cfg['jump_x_offset']
        jump_y_offset = cfg['jump_y_offset']
        # 开始
        # 放置Plot块
        pcs = self.plot_coors
        x = 20
        for li in range(len(self.plots)):
            layer = self.plots[li]
            pn = len(layer)
            y = top_reserve-plot_h/2
            step_y = tth/(len(layer)+1)
            for pi in range(len(layer)):
                plot = layer[pi]
                y += step_y
                coor = (x,y,plot_w,plot_h) # x,y,w,h
                self.plot_coors[plot['edge_id']] = coor
                #边框
                color = 'white'
                # 起始剧情和结尾剧情特殊标注
                if plot['edge_id'] == 1: 
                    color = '#ffb6c1'
                if plot['is_end_edge']:
                    color = '#00fa9a'
                self.canvas.create_rectangle(x,y,x+plot_w,y+plot_h,fill=color)
                #Text
                self.canvas.create_text(x+plot_w/2,y+0.2*plot_h,text=plot['title'])
                #Plot id
                self.canvas.create_text(x+plot_w/2,y+0.5*plot_h,text='EdgeID %s'%plot['edge_id'])
                #使用bind事件返回的event判断点击了哪个plot块
            x += plot_w+empty_w
        # 连接Plot块 #arrow='last'
        terminate_offset_x = {} # layer_index: offset
        for layer in self.plots:
            x_offset = 0
            for plot in layer:
                if not plot['question']:
                    continue
                on = len(plot['question']['choices']) # option num
                step = plot_h/(on+1)
                y_offset = 0
                for choice in plot['question']['choices']:
                    y_offset += step
                    # 获取要连接的两个plot的信息
                    p1 = plot['edge_id']
                    p2 = choice['jump_edge_id']
                    li1,pi1 = self.explored_plot_ids[p1]
                    li2,pi2 = self.explored_plot_ids[p2]
                    x1,y1,w1,h1 = self.plot_coors[p1]
                    x2,y2,w2,h2 = self.plot_coors[p2]
                    # 分情况进行连接
                    if li1+1 == li2: # 正常的连接
                        #self._draw_bezcurve(
                        #    (x1+w1,y1+y_offset),(x1+w1+bezcurve_kp_offset,y1+y_offset),(x2-bezcurve_kp_offset,y2+h2/2),(x2,y2+h2/2),
                        #    arrow='last'
                        #    )
                        self.canvas.create_line(
                            x1+w1,y1+y_offset, x2,y2+h2/2,
                            arrow='last')
                    elif li+1 > li2 or li < li2: # 跳连
                        if li2 in terminate_offset_x:
                            tox = terminate_offset_x[li2]
                            terminate_offset_x[li2] += jump_x_offset
                        else:
                            terminate_offset_x[li2] = jump_x_offset
                            tox = 0
                        if pi1 <= len(layer)/2: # 从上面绕
                            self.canvas.create_line(
                                x1+w1,y1+y_offset, x1+w1+jump_stretchout+x_offset,y1+y_offset, x1+w1+jump_stretchout+x_offset,toptrace_y,
                                x2-jump_stretchout-tox,toptrace_y, x2-jump_stretchout-tox,y2+h2/2,  x2,y2+h2/2,  
                                fill='red',arrow='last')
                            toptrace_y += jump_y_offset
                        else: # 从下面绕
                            self.canvas.create_line(
                                x1+w1,y1+y_offset, x1+w1+jump_stretchout+x_offset,y1+y_offset, x1+w1+jump_stretchout+x_offset,bottrace_y,
                                x2-jump_stretchout-tox,bottrace_y, x2-jump_stretchout-tox,y2+h2/2,  x2,y2+h2/2,  
                                fill='red',arrow='last')
                            bottrace_y -= jump_y_offset
                        x_offset += jump_x_offset
        # 完成
        self.canvas.config(scrollregion=(0,0,ttw+50,tth+top_reserve+bot_reserve))
        self._bind_scroll_event(self.canvas)
        self.canvas.bind('<Button-1>',self.click,add='+')
        self.is_drawn = True

    def click(self,event):
        #获得点击点在canvas中的位置
        _,_,cw,ch = self.canvas.config('scrollregion')[-1].split()
        xic = event.x+self.scbar_x.get()[0]*int(cw)
        yic = event.y+self.scbar_y.get()[0]*int(ch)
        #self.canvas.create_line(xic-100,yic-100,xic,yic,arrow='last')
        selected = None
        for pid,indexs in self.explored_plot_ids.items():
           x,y,w,h = self.plot_coors[pid]
           if x<=xic<=x+w and y<=yic<=y+h:
               selected = pid
               break
        if selected:
            self.fill_detail_area(selected)
        last_spi,last_cii = self.selected_plot # last_plot_id,last_canvasItemId
        if selected:
            if last_cii == selected:
                return
            if last_cii:
                self.canvas.delete(last_cii)
            now_cii = self.canvas.create_rectangle(
                x-3,y-3,x+w+3,y+h+3,
                outline='#0078d7',width=2
                )
            self.selected_plot = (selected,now_cii)
            #self.show_plot_info(*indexs)
            self.set_sidebar_state('show')
        else:
            if last_cii:
                self.canvas.delete(last_cii)
            self.set_sidebar_state('hide')
            self.selected_plot = (None,None)
        
    def _draw_bezcurve(self,*coors,kpnum=20,**kwargs):
        import bezier_curve as bc
        p = []
        for i in bc.all_points(*coors,kpnum=kpnum):
            p += [*i]
        return self.canvas.create_line(*p,**kwargs)
    
    def _scroll_event(self,event):
        self.canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def _bind_scroll_event(self,widget):
        widget.bind('<MouseWheel>',self._scroll_event)
        widget.bind('<Button-4>',self._scroll_event)
        widget.bind('<Button-5>',self._scroll_event)
        widget.bind('<Up>',lambda event:self.canvas.yview_scroll(-1,"units"))
        widget.bind('<Down>',lambda event:self.canvas.yview_scroll(1,"units"))
    
class VideoShotViewer(Window):
    def __init__(self, master, bvid, cid=None):
        self.bvid = bvid
        self.cid = cid
        super().__init__('VideoshotViewer of %s -> cID%s'%(bvid,cid), master=master)#,True,config['topmost'],config['alpha'],master=master)
        self.vshandler = None
        self._init_thread = None
        self._last_index = 1
        self.window.wm_attributes('-toolwindow',1)
        
        fm = self.frame_main = tk.Frame(self.window)
        fm.grid(column=0,row=0,padx=10,pady=10)
        self.intvar = tk.IntVar(self.window,0)
        self.scale = ttk.Scale(fm,orient=tk.HORIZONTAL,from_=0,to=1,length=150,variable=self.intvar)#,resolution=1)
        self.scale.grid(column=0,row=0)
        self.imglabel = cusw.ImageLabel(fm, width=160,height=90)
        self.imglabel.grid(column=0,row=1)
        self.label_time = tk.Label(fm,text='--:--:--')
        self.label_time.grid(column=0,row=2,sticky='e')
        self.label_size = tk.Label(fm,text='-x-')
        self.label_size.grid(column=0,row=2,sticky='w')
        ln = self.label_notice = tk.Label(self.window,text='加载中')
        ln.grid(column=0,row=0)

    def load(self):
        self._init_thread = t = threading.Thread(target=self._load_thread,name='VideoShotHandler_Initialization',daemon=True)
        t.start()
        self.window.after(10,self._load_check)

    def _load_thread(self):
        self.data = biliapis.video.get_videoshot(bvid=self.bvid,cid=self.cid)
        self.vshandler = VideoShotHandler(self.data)
        self.vshandler.init()

    def _load_check(self):
        if self._init_thread.is_alive():
            self.window.after(50, self._load_check)
        else:
            if self.vshandler:
                if self.vshandler.is_ready:
                    self.label_notice.grid_remove()
                    self.scale['to'] = len(self.data['index'])-1
                    self.scale['command'] = self._scale_callback
                    self.scale['length'] = self.data['img_w']
                    self.imglabel.set(height=self.data['img_h'],width=self.data['img_w'])
                    self.label_size['text'] = "{img_w}x{img_h}".format(**self.data)
                    self._scale_callback(None)
                    return
            msgbox.showerror('','加载视频快照失败',parent=self.window)
            self.close()

    def _scale_callback(self, event):
        index = self.intvar.get()
        if self._last_index != index:
            bio,dura = self.vshandler.get_frame(index)
            self.imglabel.set(bio)
            self.label_time['text'] = biliapis.second_to_time(dura)
            self._last_index = index

class ArticleWindow(Window):
    def __init__(self, cvid):
        pass

class ToviewWindow(Window):
    def __init__(self, master):
        super().__init__('Toview', True,config['topmost'],config['alpha'],master=master)



def main():
    load_config()
    apply_proxy_config()
    threading.Thread(target=biliapis.wbi.init,name='WBI_Initialization').start()
    logging.info('Program Running.')
    w = MainWindow()   

if (__name__ == '__main__' and not development_mode) or '-debug' in sys.argv:
    try:
        main()
    except Exception as e:
        traceback_info = traceback.format_exc()
        with open('./crash_report.txt','w+',encoding='utf-8') as f:
            f.write(traceback_info)
        raise e
    else:
        sys.exit(0)
else:
    #dump_config()
    pass
