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
    def __init__(self,url,file,data_range=None,headers=fake_headers_get,buffer_size=1024*8):
        self.url = url
        self.file = file
        self.range = data_range
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
            logging.debug('[{}]Start fetching data, host={}, range={}, code={}'.format(
                self.name,host,str(self.range),fp_web.getcode()))
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
        
def download_yield_new(url,filename,path='./',headers=fake_headers_get):
    thread = _DownloadThread(
        url=url,
        file=os.path.normpath(os.path.abspath(os.path.join(path,filename))),
        headers=headers,
        )
    thread.start()
    while thread.is_alive():
        yield (
            thread.downloaded_size, thread.expected_size,
            round(thread.downloaded_size/thread.expected_size*100,2)
        )
        time.sleep(0.05)
    if thread.exception:
        raise thread.exception
    yield (
        thread.downloaded_size, thread.expected_size,
        round(thread.downloaded_size/thread.expected_size*100,2)
        )

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
                    response_headers = fp_web.info()
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
                    raise error.ContentTooShortError(
                        "retrieval incomplete: got only %i out of %i bytes"
                        %(error_size,total_size),(filename,response_headers)
                        )
        os.rename(tmpfile,file)
        yield total_size,total_size,100.00



global_config()
