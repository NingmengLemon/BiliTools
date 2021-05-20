import tkinter as tk
import tkinter.messagebox as msgbox
import tkinter.filedialog as filedialog
import tkinter.ttk as ttk
import os
import sys
import re
import time
import _thread
#自制库
import clipboard
import biliapis
import bilicodes

version = '2.0.0_Dev01'
work_dir = os.getcwd()
user_name = os.getlogin()
config_path = f'C:\\Users\\{user_name}\\bilitools_config.json'
devmode = True
config = {
    'topmost':True,
    'audio':{
        'dash_quality':30280,
        'common_quality':3
        }
    }

def print(*text,end='\n',sep=' '):
    tmp = []
    for part in text:
        tmp += [str(part)]
    sys.stdout.write(sep.join(tmp)+end)    
    sys.stdout.flush()

def replaceChr(text):
    repChr = {'/':'／',
              '*':'＊',
              ':':'：',
              '\\':'＼',
              '>':'＞',
              '<':'＜',
              '|':'｜',
              '?':'？',
              '"':'＂'}
    for t in list(repChr.keys()):
        text = text.replace(t,repChr[t])
    return text

class MainWindow(object):
    def __init__(self):
        self.window = tk.Tk()
        self.window.title('BiliTools - Main')
        self.window.resizable(height=False,width=False)
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.window.wm_attributes('-topmost',config['topmost'])
        
        self.frames = {
            'login_info':tk.LabelFrame(self.window,text='登录信息')
            }

        #定义组件
        self.widgets = {
            'user_name':tk.Label(self.frames['login_info'],text='--'),
            'uid':tk.Label(self.frames['login_info'],text='UID --'),
            'viptype':tk.Label(self.frames['login_info'],text='--'),
            'level':tk.Label(self.frames['login_info'],text='Lv --'),
            'exp':tk.Label(self.frames['login_info'],text='Exp --/--'),
            'button_refresh':tk.Button(self.frames['login_info'],text='刷新',command=self.fresh_login_info),
            'button_load_cookies':tk.Button(self.frames['login_info'],text='加载Cookies',command=self.load_cookies),
            'button_clear_cookies':tk.Button(self.frames['login_info'],text='清除Cookies',command=self.clear_cookies),

            'button_audio_window':tk.Button(self.window,text='音频抽取',command=lambda x=0:self.goto(AudioWindow)),

            '_grid_table':[
                ('user_name',0,0),('uid',1,0),
                ('viptype',0,1),
                ('level',0,2),('exp',1,2),
                ('button_refresh',0,3),('button_load_cookies',1,3),('button_clear_cookies',2,3),
                ('button_audio_window',0,4)
                ]
            }

        #放置框架
        self.frames['login_info'].grid(column=0,row=0)
        
        #放置组件
        
        for coor in self.widgets['_grid_table']:
            self.widgets[coor[0]].grid(column=coor[1],row=coor[2],sticky='w')

        self.window.mainloop()

    def goto(self,windowobj):
        self.close()
        w = windowobj(back_window=MainWindow)

    def fresh_login_info(self):
        try:
            data = biliapis.get_login_info()
        except Exception as e:
            msgbox.showerror('(っ °Д °;)っ','Error '+str(e))
            self.widgets['user_name']['text'] = '--'
            self.widgets['uid']['text'] = 'UID --'
            self.widgets['viptype']['text'] = '--'
            self.widgets['level']['text'] = 'Lv --'
            self.widgets['exp']['text'] = 'Exp --/--'
        else:
            self.widgets['user_name']['text'] = data['name']
            self.widgets['uid']['text'] = 'UID %s'%data['uid']
            self.widgets['viptype']['text'] = data['vip_type']
            self.widgets['level']['text'] = 'Lv %s'%data['level']
            self.widgets['exp']['text'] = 'Exp %s'%data['exp']

    def clear_cookies(self):
        biliapis.clear_cookies()
        msgbox.showinfo('φ(゜▽゜*)♪','Cookies已清除')
        self.widgets['user_name']['text'] = '--'
        self.widgets['uid']['text'] = 'UID --'
        self.widgets['viptype']['text'] = '--'
        self.widgets['level']['text'] = 'Lv --'
        self.widgets['exp']['text'] = 'Exp --/--'

    def load_cookies(self):
        r = biliapis.load_cookies()
        if r == 0:
            msgbox.showinfo('φ(゜▽゜*)♪','加载成功')
        else:
            msgbox.showerror('（；´д｀）ゞ','加载失败')

    def close(self):
        self.window.quit()
        self.window.destroy()

class AudioWindow(object):
    def __init__(self,back_window=None):
        self.back_window = back_window
        self.window = tk.Tk()
        self.window.title('BiliTools - Audio')
        self.window.resizable(height=False,width=False)
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.window.wm_attributes('-topmost',config['topmost'])
        
        self.frame_config_quality = tk.LabelFrame(self.window,text='首选音频质量设定')
        self.frame_config_quality.grid(column=0,row=3,columnspan=4,sticky='w')
        self.var_dash_audio_quality = tk.IntVar(value=config['audio']['dash_quality'])
        self.var_audio_quality = tk.IntVar(value=config['audio']['common_quality'])
        
        self.lock = False

        self.widgets = {
            'text1':tk.Label(self.window,text='源:'),
            'entry_url':tk.Entry(self.window,width=40,exportselection=0,selectbackground='#66CCFF'),
            'button_paste':tk.Button(self.window,text='粘贴',command=lambda x=0:self.setEntry(self.widgets['entry_url'],text=clipboard.getText())),
            'button_clear_url':tk.Button(self.window,text='清空',command=lambda x=0:self.widgets['entry_url'].delete(0,'end')),
            'text2':tk.Label(self.window,text='保存至:'),
            'entry_path':tk.Entry(self.window,width=40,exportselection=0,selectbackground='#66CCFF',state='disabled'),
            'button_explore_path':tk.Button(self.window,text='浏览',command=lambda x=0:self.explore_folder(self.widgets['entry_path'])),
            'button_clear_path':tk.Button(self.window,text='清空',command=lambda x=0:self.setEntry(self.widgets['entry_path'],True)),
            'button_start':tk.Button(self.window,text='走你',command=self.handle_process),
            'button_help':tk.Button(self.window,text=' ？ ',command=self.show_help),

            'text3':tk.Label(self.frame_config_quality,text='若来源为音频区  - '),
            'radiobtn_128k':tk.Radiobutton(self.frame_config_quality,text='128K',variable=self.var_audio_quality,value=0,command=self.apply_config),
            'radiobtn_192k':tk.Radiobutton(self.frame_config_quality,text='192K',variable=self.var_audio_quality,value=1,command=self.apply_config),
            'radiobtn_320k':tk.Radiobutton(self.frame_config_quality,text='320K',variable=self.var_audio_quality,value=2,command=self.apply_config),
            'radiobtn_flac':tk.Radiobutton(self.frame_config_quality,text='FLAC',variable=self.var_audio_quality,value=3,command=self.apply_config),

            'text4':tk.Label(self.frame_config_quality,text='若来源为视频区'),
            'radiobtn_dash_64k':tk.Radiobutton(self.frame_config_quality,text='64K',variable=self.var_dash_audio_quality,value=30216,command=self.apply_config),
            'radiobtn_dash_132k':tk.Radiobutton(self.frame_config_quality,text='132K',variable=self.var_dash_audio_quality,value=30232,command=self.apply_config),
            'radiobtn_dash_192k':tk.Radiobutton(self.frame_config_quality,text='192K',variable=self.var_dash_audio_quality,value=30280,command=self.apply_config),
            
            '_grid_table':[#(name,column,row)
                ('text1',0,0),('entry_url',1,0),('button_paste',2,0),('button_clear_url',3,0),
                ('text2',0,1),('entry_path',1,1),('button_explore_path',2,1),('button_clear_path',3,1),
                ('button_help',0,2),#('button_start',2,2),

                ('text3',0,0),('radiobtn_128k',0,1),('radiobtn_192k',0,2),('radiobtn_320k',0,3),('radiobtn_flac',0,4),
                ('text4',1,0),('radiobtn_dash_64k',1,1),('radiobtn_dash_132k',1,2),('radiobtn_dash_192k',1,3)
                ]
            }

        for coor in self.widgets['_grid_table']:
            self.widgets[coor[0]].grid(column=coor[1],row=coor[2],sticky='w')
        #有特殊需要的组件放在这里
        self.widgets['button_start'].grid(column=2,row=2,columnspan=2)

        self.window.mainloop()
        
    def show_help(self):
        help_text = '\n'.join([
            '音频抽取',
            '抽取视频的音轨或者下载音频区的音频.',
            '将网址复制到“源”输入框内, 选择输出地址, 再点击“走你”即可.',
            '首选音频质量在下方选取, 若没有匹配的质量则默认下载最高音质.'
            ])
        msgbox.showinfo('φ(゜▽゜*)♪',help_text)
        

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

    def apply_config(self):
        global config
        config['audio']['dash_quality'] = self.var_dash_audio_quality.get()
        config['audio']['common_quality'] = self.var_audio_quality.get()
        #print('Applied Audio Quality Config.')
        
    def handle_process(self,source=None,topath=None):
        #Get
        if source == None:
            source = self.widgets['entry_url'].get()
        if topath == None:
            topath = self.widgets['entry_path'].get()
        source = source.strip()
        topath = topath.strip()
        #Check
        if not source:
            msgbox.showwarning('(っ °Д °;)っ','你没有输入来源.')
            return
        if not topath:
            msgbox.showwarning('(っ °Д °;)っ','你没有输入保存地址.')
            return
        try:
            #Parse & Lock
            self.lock = True
            self.widgets['button_start']['state'] = 'disabled'
            source,flag = biliapis.parse_url(source)
            if flag == 'unknown':
                msgbox.showerror('(。﹏。*)','未知的来源...')
            #auID
            elif flag == 'auid':
                stream = biliapis.get_audio_stream(int(source),config['audio']['common_quality'])
                if stream:
                    if stream['quality'] == 'FLAC':
                        filetype = 'flac'
                    else:
                        filetype = 'aac'
                    filename = replaceChr('%s(id%s)(%s).%s'%(stream['title'],stream['auid'],stream['quality'],filetype))
                    w = biliapis.DownloadWindow(stream['url'],topath,filename)
            #avID / bvID
            elif flag == 'avid' or flag == 'bvid':
                abvid = source
                if flag == 'avid':
                    source = biliapis.get_video_detail(avid=source)
                else:
                    source = biliapis.get_video_detail(bvid=source)
                if source:
                    title = source['title']
                    source = source['parts']
                    multi_part = bool(len(source)-1)
                    if multi_part:
                        pnamelist = []
                        for item in source:
                            pnamelist.append(item['title'])
                        w = PartsChooser(pnamelist)
                        if w.return_indexs:
                            callback = w.return_indexs
                            for index in callback:
                                item = source[index]
                                if flag == 'avid':
                                    stream = biliapis.get_video_stream_dash(item['cid'],avid=abvid)
                                else:
                                    stream = biliapis.get_video_stream_dash(item['cid'],bvid=abvid)
                                stream = stream['audio']
                                qualities = []
                                for i in stream:
                                    qualities.append(i['quality'])
                                if bilicodes.stream_dash_audio_quality[config['audio']['dash_quality']] in qualities:
                                    quality_index = qualities.index(bilicodes.stream_dash_audio_quality[config['audio']['dash_quality']])
                                else:
                                    quality_index = -1
                                stream = stream[quality_index]
                                filename = replaceChr('%s(P%s.%s)(%s)(%s)'%(title,index+1,item['title'],abvid,stream['quality']))+'.aac'
                                w = biliapis.DownloadWindow(stream['url'],topath,filename,False)
                            msgbox.showinfo('(⑅˃◡˂⑅)','任务完成！\nTips：因为是批处理所以请手动打开......')
                        else:
                            return
                        
                    else:
                        index = 0
                        item = source[index]
                        if flag == 'avid':
                            stream = biliapis.get_video_stream_dash(item['cid'],avid=abvid)
                        else:
                            stream = biliapis.get_video_stream_dash(item['cid'],bvid=abvid)
                        stream = stream['audio']
                        qualities = []
                        for i in stream:
                            qualities.append(i['quality'])
                        if bilicodes.stream_dash_audio_quality[config['audio']['dash_quality']] in qualities:
                            quality_index = qualities.index(bilicodes.stream_dash_audio_quality[config['audio']['dash_quality']])
                        else:
                            quality_index = -1
                        stream = stream[quality_index]
                        filename = replaceChr('%s(P%s.%s)(%s)(%s)'%(title,index+1,item['title'],abvid,stream['quality']))+'.aac'
                        w = biliapis.DownloadWindow(stream['url'],topath,filename)
            #ssID & mdID & epID
            elif flag == 'ssid' or flag == 'mdid' or flag == 'epid':
                if flag == 'ssid':
                    data = biliapis.get_media_detail(ssid=source)
                elif flag == 'mdid':
                    data = biliapis.get_media_detail(mdid=source)
                else:#flag == 'epid'
                    data = biliapis.get_media_detail(epid=source)
                title = data['title']
                cids = []
                bvids = []
                pnames = []
                for ep in data['episodes']:
                    cids.append(ep['cid'])
                    pnames.append(ep['title_completed'])
                    bvids.append(ep['bvid'])
                for sec in data['sections']:
                    for ep in sec['episodes']:
                        cids.append(ep['cid'])
                        pnames.append(ep['title'])
                        bvids.append(ep['bvid'])
                w = PartsChooser(pnames)
                callback = w.return_indexs
                if callback:
                    for index in callback:
                        cid = cids[index]
                        pname = pnames[index]
                        bvid = bvids[index]
                        #Get Stream
                        stream = biliapis.get_video_stream_dash(cid,bvid=bvid)
                        stream = stream['audio']
                        qualities = []
                        for i in stream:
                            qualities.append(i['quality'])
                        if bilicodes.stream_dash_audio_quality[config['audio']['dash_quality']] in qualities:
                            quality_index = qualities.index(bilicodes.stream_dash_audio_quality[config['audio']['dash_quality']])
                        else:
                            quality_index = -1
                        stream = stream[quality_index]
                        #Make Filename
                        filename = replaceChr('%s(P%s.%s)(%s)(%s)'%(title,index+1,pname,bvid,stream['quality']))+'.aac'
                        w = biliapis.DownloadWindow(stream['url'],topath,filename,False)
                    msgbox.showinfo('(⑅˃◡˂⑅)','任务完成！\nTips：因为是批处理所以请手动打开......')
                else:
                    return
                
            else:
                msgbox.showwarning('(。﹏。*)','暂不支持%s的解析.'%flag)
            
        except Exception as e:
            msgbox.showerror('ERROR发生',str(e))
            #raise e
        finally:
            #Unlock
            self.lock = False
            self.widgets['button_start']['state'] = 'normal'
        
        
    def close(self):
        if self.lock:
            msgbox.showwarning('(⑅˃◡˂⑅)','请先关闭所有弹出的子窗口再退出.')
            return
        self.window.quit()
        self.window.destroy()
        if self.back_window:
            w = self.back_window()

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
        self.entry = tk.Entry(self.window,width=40,exportselection=0,selectbackground='#66CCFF')
        self.entry.grid(column=0,row=1,columnspan=2)
        self.entry.bind('<Return>',self.ensure)
        tk.Button(self.window,text='确认',command=self.ensure).grid(column=0,row=2)
        tk.Button(self.window,text='取消',command=self.cancel).grid(column=1,row=2)

    def ensure(self,event=None):
        try:
            self.accept_type(self.entry.get())
        except:
            msgbox.showwarning('（；´д｀）ゞ','你所输入的内容无法转换为程序要求的类型.\n需要: '+str(self.accept_type))
            return
        self.return_value = self.entry.get()
        self.close()

    def cancel(self):
        self.close()

    def close(self):
        self.window.quit()
        self.window.destroy()

class PartsChooser(object):
    def __init__(self,parts_list,title='PartsChooser',text='选择分P',topmost=True):
        self.return_indexs = []
        self.return_pnames = []
        if not parts_list:
            raise RuntimeError('No Parts to Choose.')
        self.window = tk.Tk()
        self.window.title(title)
        self.window.resizable(height=False,width=False)
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.window.wm_attributes('-topmost',topmost)

        tk.Label(self.window,text=text).grid(column=0,row=0,sticky='w',columnspan=2)
        
        self.bar_tvbar = tk.Scrollbar(self.window,orient='vertical')
        self.table = ttk.Treeview(self.window,show="headings",columns=("number","title"),yscrollcommand=self.bar_tvbar.set,height=15)
        self.bar_tvbar['command'] = self.table.yview
        self.table.column("number", width=40)
        self.table.column("title", width=300)
        self.table.heading("number", text="序号")
        self.table.heading("title", text="标题")

        self.table.grid(column=0,row=1,sticky='e')
        self.bar_tvbar.grid(column=1,row=1,sticky='nw',ipady=135)

        tk.Label(self.window,text='Tips：按住Ctrl可多选，按住Shift可批量勾选').grid(column=0,row=2,sticky='w')

        tk.Button(self.window,text='获取全部',command=self.return_all).grid(column=0,row=3,sticky='e')
        tk.Button(self.window,text='获取选中',command=self.return_selected).grid(column=0,row=3,sticky='w')

        for i in range(0,len(parts_list)):
            self.table.insert("","end",values=(str(i+1),parts_list[i]))

        self.window.mainloop()

    def return_selected(self):
        tmp = []
        for i in self.table.get_children():
            tmp.append(self.table.item(i,'values')[1])
        if self.table.selection() == ():
            return
        sel = []
        for item in self.table.selection():
            sel.append(self.table.item(item,"values")[1])
        self.return_pnames = sel
        self.return_indexs = []
        for pname in sel:
            self.return_indexs.append(tmp.index(pname))
        self.close()

    def return_all(self):
        tmp = []
        for i in self.table.get_children():
            tmp.append(self.table.item(i,'values')[1])
        if tmp == []:
            return
        self.return_pnames = tmp
        self.return_indexs = []
        for pname in tmp:
            self.return_indexs.append(tmp.index(pname))
        self.close()

    def close(self):
        self.window.quit()
        self.window.destroy()

class VideoWindow(object):
    def __init__(self,back_window=None):
        pass

if __name__ == '__main__' and not devmode:
    print('Program Running.')
    w = MainWindow()
