import requests #
import os
import re
import sys
import time
import json
import zlib,gzip
import _thread
import hashlib
import math
from io import BytesIO
from http import cookiejar
from urllib import request, parse, error
import tkinter as tk
import tkinter.messagebox as msgbox
import tkinter.ttk as ttk
from basic_window import Window

cookies = None

def download_with_requests(url,tofile,callbackfunc=None,use_cookies=True,headers={}):
    if os.path.exists(tofile):
        raise RuntimeError('File already exists.')
    tmp_file = tofile+'.download'
    #Load Header
    #headers = fake_headers_get
    if cookies and use_cookies:
        cookies_dict = requests.utils.dict_from_cookiejar(cookies)
    else:
        cookies_dict = {}
    #Get Response
    response = requests.get(url,stream=True,headers=headers,cookies=cookies_dict)
    #Check Existed File
    file_size = int(response.headers['content-length'])
    if os.path.exists(tmp_file):
        start_byte = os.path.getsize(tmp_file)
    else:
        start_byte = 0
    if start_byte >= file_size:
        callbackfunc(int(file_size/1024),1024,file_size)
        os.rename(tmp_file,tofile)
        return 0
    #Download
    headers['Range'] = f'bytes={start_byte}-{file_size}'
    req = requests.get(url,headers=headers,stream=True,cookies=cookies_dict)
    counter = 0
    writemode = 'ab+'
    with open(tmp_file,writemode) as f:
        for chunk in req.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
                f.flush()
                counter += 1024
                if callbackfunc:
                    callbackfunc(int((start_byte+counter)/1024),1024,file_size)#与 urllib.request.urlretrieve() 的回传方法保持一致
    os.rename(tmp_file,tofile)
    return 0

class DownloadWindow(Window):
    def __init__(self,url,topath='./',filename='Unknown'):
        super().__init__('Downloader',True,True,1.0)
        self.window.protocol('WM_DELETE_WINDOW',self.close_)
        
        self.status = -1 #-1:Not Start yet, 0:Done, 1:Running, 2:Error, 3:User Stopped
        self.url = url
        self.topath = os.path.abspath(topath)
        self.filename = filename
        #GUI
        tk.Label(self.window,text='文件名:').grid(column=0,row=0,sticky='w')
        self.text_filename = tk.Text(self.window,bg='#f0f0f0',bd=0,height=1,width=46,state='disabled')
        self.text_filename.grid(column=1,row=0,sticky='w')
        tk.Label(self.window,text='源:').grid(column=0,row=1,sticky='w')
        self.text_source = tk.Text(self.window,bg='#f0f0f0',bd=0,height=1,width=46,state='disabled')
        self.text_source.grid(column=1,row=1,sticky='w')
        tk.Label(self.window,text='保存至:').grid(column=0,row=2,sticky='w')
        self.text_topath = tk.Text(self.window,bg='#f0f0f0',bd=0,height=1,width=46,state='disabled')
        self.text_topath.grid(column=1,row=2,sticky='w')
        tk.Label(self.window,text='文件大小:').grid(column=0,row=3,sticky='w')
        self.label_filesize = tk.Label(self.window,text='- B')
        self.label_filesize.grid(column=1,row=3,sticky='w')
        tk.Label(self.window,text='已完成大小:').grid(column=0,row=4,sticky='w')
        self.label_donesize = tk.Label(self.window,text='- B')
        self.label_donesize.grid(column=1,row=4,sticky='w')
        tk.Label(self.window,text='完成度:').grid(column=0,row=5,sticky='w')
        self.label_percent = tk.Label(self.window,text='0.000%')
        self.label_percent.grid(column=1,row=5,sticky='w')
        tk.Label(self.window,text='状态:').grid(column=0,row=6,sticky='w')
        self.label_status = tk.Label(self.window,text='Not started yet.')
        self.label_status.grid(column=1,row=6,sticky='w')
        self.prgbar = ttk.Progressbar(self.window,orient='horizontal',length=380,mode='determinate',maximum=1000,value=0)
        self.prgbar.grid(column=0,row=7,columnspan=2)

        self.set_text(self.text_filename,text=self.filename,lock=True)
        self.set_text(self.text_source,text=self.url,lock=True)
        self.set_text(self.text_topath,text=self.topath,lock=True)
        
        _thread.start_new(self._download_thread,(self.url,os.path.join(self.topath,self.filename)))
        self.window.mainloop()

    def close_(self,force=False):
        if not force:
            if self.status == 0:
                if msgbox.askyesno('','任务还在进行，要中止后再关闭窗口吗？'):
                    _end_process(3)
                else:
                    pass
                return
        self.close()

    def _convert_unit(self,byte):
        if byte <= 1024:
            return '%d B'%byte
        else:
            K = byte / 1024
        if K <= 1024:
            return '%.3f KB'%K
        else:
            M = K / 1024
        return '%.3f MB'%M

    def _end_process(self,code=0,error_msg=None):
        if error_msg or code == 2:
            self.status = 2
            msgbox.showerror('','发生错误\n%s'%error_msg)
            self.close(True)
        elif code = 0:
            self.status = 0
            if msgbox.askyesno('','完成！打开输出目录？'):
                os.popen('explorer "%s"'%self.topath)
            self.close(True)
        elif code = 3:
            self.status = 3
            msgbox.showinfo('','用户手动结束了进程。')
            self.close(True)
        return
        
    def _update_info(self,file_size=None,done_size=None,status_text=None,status_code=1):
        if file_size != None and done_size != None:
            percent = done_size / file_size * 100
            self.label_percent['text'] = '%.3f%%'%percent
            self.prgbar['value'] = int(percent*10)
        if file_size != None:
            self.label_filesize['text'] = self._convert_unit(file_size)
        if done_size != None:
            self.label_donesize['text'] = self._convert_unit(done_size)
        if status_text:
            self.label_status['text'] = status_text
        if status_code == 1:
            self.label_status['text'] = 'Done'
            self.label_donesize['text'] = self.label_filesize['text']
            self.prgbar['value'] = 1000
            self.label_percent['text'] = '100.000%'

    def _download_thread(self,url,tofile):
        #self.task_queue.put_nowait(lambda fs=None,ds=None,st=None:self._update_info(fs,ds,st))
        if os.path.exists(tofile):
            pass
        tmp_file = tofile+'.download'
        #Load Header
        headers = fake_headers_get
        if cookies:
            cookies_dict = requests.utils.dict_from_cookiejar(cookies)
        else:
            cookies_dict = {}
        #Get Pre-data
        response = requests.get(url,stream=True,headers=headers,cookies=cookies_dict)
        #Check Existed File
        file_size = int(response.headers['content-length'])
        if os.path.exists(tmp_file):
            start_byte = os.path.getsize(tmp_file)
        else:
            start_byte = 0
        if start_byte >= file_size:
            os.rename(tmp_file,tofile)
            return 0
        #Download
        headers['Range'] = f'bytes={start_byte}-{file_size}'
        req = requests.get(url,headers=headers,stream=True,cookies=cookies_dict)
        counter = start_byte
        writemode = 'ab+'
        with open(tmp_file,writemode) as f:
            for chunk in req.iter_content(chunk_size=512):
                if chunk:
                    f.write(chunk)
                    f.flush()
                    counter += 512
                    #Callback
        os.rename(tmp_file,tofile)
        return 0
