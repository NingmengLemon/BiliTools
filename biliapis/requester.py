from http import cookiejar
from urllib import request, parse, error
import json
import zlib,gzip
import os
import re
import sys
import atexit
from io import BytesIO
import logging
import copy
import time
import functools
import threading
import traceback
import contextlib
import queue
import math

import brotli

filter_emoji = False
user_name = os.getlogin()
inner_data_path = 'C:\\Users\\{}\\BiliTools\\'.format(user_name)

cookies = None
proxy = None
opener = None
fake_headers_get = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',  # noqa
    'Accept-Charset': 'UTF-8,*;q=0.5',
    'Accept-Encoding': 'gzip,deflate,sdch',
    'Accept-Language': 'en-US,en;q=0.8',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.74 Safari/537.36 Edg/79.0.309.43',  # noqa
    'Referer':'https://www.bilibili.com/'
}

fake_headers_post = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.74 Safari/537.36 Edg/79.0.309.43',
    'Referer':'https://www.bilibili.com/'
    }


local_cookiejar_path = os.path.join(inner_data_path,'cookies.txt')

timeout = 15
retry_time = 3

def auto_retry(retry_time=3):
    def retry_decorator(func):
        @functools.wraps(func)
        def wrapped(*args,**kwargs):
            _run_counter = 0
            while True:
                _run_counter += 1
                try:
                    return func(*args,**kwargs)
                except Exception as e:
                    logging.error('Unexpected Error occurred while executing function {}: '\
                                  '{}; Retrying...'.format(str(func),str(e)))
                    if _run_counter > retry_time:
                        raise e
        return wrapped
    return retry_decorator

def remove_emoji(string):
    # 过滤表情
    try:
        co = re.compile(u'[\U00010000-\U0010ffff]')
    except re.error:
        co = re.compile(u'[\uD800-\uDBFF][\uDC00-\uDFFF]')
    return co.sub('', string)

def _replaceChr(text):
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

def _ungzip(data):
    """Decompresses data for Content-Encoding: gzip.
    """
    buffer = BytesIO(data)
    f = gzip.GzipFile(fileobj=buffer)
    return f.read()

def _undeflate(data):
    """Decompresses data for Content-Encoding: deflate.
    (the zlib compression is used.)
    """
    decompressobj = zlib.decompressobj(-zlib.MAX_WBITS)
    return decompressobj.decompress(data)+decompressobj.flush()

def _unbrotli(data):
    return brotli.decompress(data)

def _dict_to_headers(dict_to_conv):
    keys = list(dict_to_conv.keys())
    values = list(dict_to_conv.values())
    res = []
    for i in range(len(keys)):
        res.append((keys[i],values[i]))
    return res

def global_config(use_cookie=True,use_proxy=None):
    global opener
    handler_list = []
    if use_cookie and cookies:
        handler_list.append(request.HTTPCookieProcessor(cookies))
    if use_proxy == None:
        handler_list.append(request.ProxyHandler())
    elif use_proxy == True:
        handler_list.append(request.ProxyHandler({'http':proxy,'https':proxy}))
    else:
        handler_list.append(request.ProxyHandler({}))
    opener = request.build_opener(*handler_list)

@auto_retry(retry_time)
def _get_response(url, headers=fake_headers_get):
    with opener.open(request.Request(url, headers=headers), None, timeout=timeout) as response:
        data = response.read()
        if response.info().get('Content-Encoding') == 'gzip':
            data = _ungzip(data)
        elif response.info().get('Content-Encoding') == 'deflate':
            data = _undeflate(data)
        elif response.info().get('Content-Encoding') == 'br':
            data = _unbrotli(data)
        response.data = data
        logging.debug('Get Response from: '+url)
        return response

@auto_retry(retry_time)
def _post_request(url,data,headers=fake_headers_post):
    params = parse.urlencode(data).encode()
    with opener.open(request.Request(url,data=params,headers=headers), timeout=timeout) as response:
        data = response.read()
        if response.info().get('Content-Encoding') == 'gzip':
            data = _ungzip(data)
        elif response.info().get('Content-Encoding') == 'deflate':
            data = _undeflate(data)
        elif response.info().get('Content-Encoding') == 'br':
            data = _unbrotli(data)
        response.data = data
        if len(params) <= 100:
            logging.debug('Post Data to {} with Params {}'.format(url,str(params)))
        else:
            logging.debug('Post Data to {} with a very long params'.format(url))
        return response

def post_data_str(url,data,headers=fake_headers_post,encoding='utf-8'):
    content = _post_request(url,data,headers).data
    data = content.decode(encoding, 'ignore')
    if filter_emoji:
        data = remove_emoji(data)
    return data

def post_data_bytes(url,data,headers=fake_headers_post,encoding='utf-8'):
    response = _post_request(url,data,headers)
    return response.data

def get_content_str(url, encoding='utf-8', headers=fake_headers_get):
    content = _get_response(url, headers=headers).data
    data = content.decode(encoding, 'ignore')
    if filter_emoji:
        data = remove_emoji(data)
    return data

def get_content_json(**options):
    return json.loads(get_content_str(**options))

def get_content_bytes(url, headers=fake_headers_get):
    content = _get_response(url, headers=headers).data
    return content

def get_redirect_url(url,headers=fake_headers_get):
    with opener.open(request.Request(url, headers=headers), None, timeout=timeout) as rsp:
        return rsp.geturl()

#Cookie Operation
def clear_cookies():
    global cookies
    cookies = None
    if os.path.exists(local_cookiejar_path):
        os.remove(local_cookiejar_path)
    
def load_local_cookies():
    global cookies
    if not os.path.exists(local_cookiejar_path):
        f = open(local_cookiejar_path,'w+',encoding='utf-8')
        f.write('# Netscape HTTP Cookie File\n'\
                '# https://curl.haxx.se/rfc/cookie_spec.html\n'\
                '# This is a generated file!  Do not edit.')
        f.close()
    cookies = cookiejar.MozillaCookieJar(local_cookiejar_path)
    cookies.load()
    logging.debug('Cookiejar loaded from '+local_cookiejar_path)

@atexit.register
def refresh_local_cookies():
    global cookies
    if cookies:
        cookies.save(local_cookiejar_path)

def set_proxy(new_proxy):
    global proxy
    proxy = new_proxy

#Download Operation
def download_common(url,tofile,headers=fake_headers_get,use_cookie=True,use_proxy=False):
    
    chunk_size = 1024
    with opener.open(request.Request(url,headers=headers),timeout=timeout) as response:
        with open(tofile,'wb+') as f:
            while True:
                data = response.read(chunk_size)
                if data:
                    f.write(data)
                else:
                    break
    logging.debug('Download file from {} to {}.'.format(url,tofile))
           

def convert_size(size):#单位:Byte
    if size < 1024:
        return '%.2f B'%size
    size /= 1024
    if size < 1024:
        return '%.2f KB'%size
    size /= 1024
    if size < 1024:
        return '%.2f MB'%size
    size /= 1024
    return '%.2f GB'%size

class _DownloadThread(threading.Thread):
    def __init__(self,url,file,datarange=None,headers=fake_headers_get,buffer_size=1024*8):
        self.url = url
        self.file = file
        self.range = datarange
        self.buffer_size = buffer_size
        self.headers = headers.copy()
        self.downloaded_size = 0
        self.exception = None
        self.traceback_info = None
        self.expected_size = -1
        super().__init__()
        self.setDaemon(True)

    def run(self):
        try:
            self._download()
        except Exception as e:
            self.exception = e
            self.traceback_info = traceback.format_exc()
            raise e
        else:
            pass

    def _download(self):
        if self.range:
            s,e = self.range
            self.headers['Range'] = f'bytes={s}-{e}'
            self.expected_size = e-s+1
        else:
            self.expected_size = -1
        with contextlib.closing(opener.open(request.Request(self.url,headers=self.headers),timeout=timeout)) as fp_web: #网络文件
            host = fp_web.geturl().split('/')[2]
            web_headers = fp_web.info()
            if self.expected_size == -1 and 'content-length' in web_headers:
                self.expected_size = int(fp_web.getheader('content-length'))
                self.range = (0,self.expected_size-1)
            logging.debug('[{}]Start fetching data, host={}, range={}, code={}'.format(self.name,
                                                                                       host,
                                                                                       str(self.range),
                                                                                       fp_web.getcode()
                                                                                       ))
            write_mode = 'wb+'
            with open(self.file,write_mode) as fp_local: #本地文件
                while True:
                    data = fp_web.read(self.buffer_size)
                    if not data:
                        break
                    fp_local.write(data)
                    self.downloaded_size += len(data)
        if self.expected_size >= 0 and self.downloaded_size < self.expected_size:
            raise request.ContentTooShortError("retrieval incomplete: got only %i out of %i bytes"%(
                self.downloaded_size,self.expected_size),(self.file,web_headers))

# 测试用url：https://dldir1.qq.com/qqfile/qq/PCQQ9.7.1/QQ9.7.1.28934.exe
# 首先预请求，得到headers里的content-length,accept-ranges等参数
# 然后创建临时任务文件夹，位于目标目录下
# 临时文件夹里存在一个downloaded_data_info.json，里面存放已下载数据文件的索引信息
# 分配任务区间，默认每个线程50MB，同时进行线程数5
# 创建多个任务对象存待做列表里
class MultithreadDownloader(object):
    def __init__(url,file,headers=fake_headers_get,block_size=50*1024*1024,max_thread_num=5):
        self.url = url
        self.file = file
        self.headers = headers.copy()
        self.strategy = 0 # 0:未定, 1:单线程, 2:多线程
        self.expected_size = -1
        self.block_size = block_size
        self.max_thread_num = max_thread_num

        self.block_files = []
        self.not_started = queue.Queue()
        self.running = []
        self.done = []

        self.progress = {
            'done':-1,
            'total':-1,
            'bps':0, # bytes per second
            'status':0, # 0:未开始,1:进行中,2:成功,3:失败
            'msg':''
            }
        self._last_report = (0,time.time()) # bytes, second

    def distribute_ranges(self,total_size,block_size):
        block_num = math.ceil(total_size/block_size)
        ranges = []
        i = 0
        for i in range(0,block_num):
            ranges += [(i*block_size,(i+1)*block_size-1)]
        ranges[i] = (i*block_size,total_size-1)
        return ranges

    def pre_request(self,strategy=None):
        with contextlib.closing(opener.open(request.Request(self.url,headers=self.headers),timeout=timeout)) as fp:
            if fp.getheader('accept-ranges') == 'bytes':
                if strategy in [None,2]:
                    self.strategy = 2
                else:
                    self.strategy = 1
            else:
                self.strategy = 1
                logging.debug('Range operation is not supported, using single thread')
            cl = fp.getheader('content-length')
            if cl:
                self.expected_size = int(cl)
            if self.expected_size <= 1.2*self.block_size and self.strategy == 2 and self.expected_size >= 0:
                self.strategy = 1
                logging.debug('File size is close to block size, using single thread')
            if self.expected_size == -1 and self.strategy == 2:
                self.strategy = 1
                logging.debug('Unknown file size, using single thread')

    def start(self,strategy=None):
        self.pre_request(strategy)
        self._last_report = (0,time.perf_counter())
        if self.strategy == 2:
            self.main_multi()
        elif self.strategy in [0,1]:
            self.main_single()

    def main_single(self): # 丢子线程里跑
        thread = _DownloadThread(self.url,self.file)
        thread.start()
        is_alive = True
        while is_alive:
            self.report_progress()
            time.sleep(0.1)
            is_alive = thread.is_alive()

    def main_multi(self): #丢子线程里跑
        pass

    def merge_files(self,main_file,*files,delete=True):
        chunk_size = 1*1024*1024
        with open(main_file,'wb+') as f:
            for file in files:
                with open(file,'rb') as tf:
                    while True:
                        data = tf.read(chunk_size)
                        if data:
                            f.write(data)
                        else:
                            break
                if delete:
                    os.remove(file)

    def report_progress(self,done,total,status,msg=None):
        self.progress['done'] = done
        self.progress['total'] = total
        self.progress['status'] = status
        if msg:
            self.progress['msg'] = msg
        try:
            s1,t1 = self._last_report
            s2,t2 = done,time.perf_counter()
            self.progress['bps'] = round((t2-t1)/(s2-s1))
            self._last_report = (s2,t2)
        except:
            pass

def download_yield_experiment(url,filename=None,path='./',headers=fake_headers_get):
    if filename:
        pass
    else:
        filename = url.split('/')[-1]
    file = os.path.join(os.path.abspath(path),_replaceChr(filename))

def download_yield(url,filename,path='./',headers=fake_headers_get,check=True):
    file = os.path.join(os.path.abspath(path),_replaceChr(filename))
    if os.path.exists(file):
        size = os.path.getsize(file)
        yield size,size,100.00
    else:
        tmpfile = file+'.download'
        #检查上次下载遗留文件
        if os.path.exists(tmpfile):
            size = os.path.getsize(tmpfile)
        else:
            size = 0
        #拷贝请求头
        headers = copy.deepcopy(headers)
        #预请求
        #核对文件信息
        with opener.open(request.Request(url,headers=headers),timeout=timeout) as pre_response:
            total_size = int(pre_response.getheader('content-length'))
            if pre_response.getheader('accept-ranges') == 'bytes' and size <= total_size and size > 0:
                #满足这些条件时才会断点续传, 否则直接覆盖download文件
                #条件: 支持range操作, 本地文件大小小于服务端文件大小
                #生成range头
                headers['Range'] = 'bytes={}-{}'.format(size,total_size)
                write_mode = 'ab+'
                done_size = size
            else:
                done_size = size = 0
                write_mode = 'wb+'
        pre_response.close()
        chunk_size = 1*1024
        if size == total_size:
            pass
        else:
            try:
                with opener.open(request.Request(url,headers=headers),timeout=timeout) as fp_web: #网络文件
                    logging.debug('Fetching data from {}, start_byte={}, Code {}'.format(url,size,fp_web.getcode())) 
                    with open(tmpfile,write_mode) as fp_local: #本地文件
                        while True:
                            data = fp_web.read(chunk_size)
                            if not data:
                                break
                            fp_local.write(data)
                            done_size += len(data)
                            yield done_size,total_size,round(done_size/total_size*100,2)
            except Exception as e:
                raise e
            if check:
                if os.path.getsize(tmpfile) != total_size:
                    error_size = os.path.getsize(tmpfile)
                    os.remove(tmpfile)
                    raise RuntimeError('File Size not Match. The size given by server is {} Bytes, '\
                        'howerver the received file\'s size is {} Bytes.'.format(total_size,error_size))
        os.rename(tmpfile,file)
        yield total_size,total_size,100.00



global_config()
