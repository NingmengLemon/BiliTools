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

import brotli

filter_emoji = False
user_name = os.getlogin()
inner_data_path = 'C:\\Users\\{}\\BiliTools\\'.format(user_name)

cookies = None
proxy = None
fake_headers_get = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',  # noqa
    'Accept-Charset': 'UTF-8,*;q=0.5',
    'Accept-Encoding': 'gzip,deflate,sdch',
    'Accept-Language': 'en-US,en;q=0.8',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.74 Safari/537.36 Edg/79.0.309.43',  # noqa
    'Referer':'https://www.bilibili.com/'
}

fake_headers_post = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.74 Safari/537.36 Edg/79.0.309.43'
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

def make_opener(use_cookie=True,use_proxy=True):
    if use_cookie and use_proxy:
        if cookies and proxy:
            opener = request.build_opener(request.HTTPCookieProcessor(cookies),request.ProxyHandler({'http':proxy,'https':proxy}))
        elif cookies and not proxy:
            opener = request.build_opener(request.HTTPCookieProcessor(cookies),request.ProxyHandler({}))
        elif not cookies and proxy:
            opener = request.build_opener(request.ProxyHandler({'http':proxy,'https':proxy}))
        else:
            opener = request.build_opener(request.ProxyHandler({}))
        return opener
    elif use_cookie and not use_proxy:
        if cookies:
            opener = request.build_opener(request.HTTPCookieProcessor(cookies))
        else:
            opener = request.build_opener(request.ProxyHandler({}))
    elif not use_cookie and use_proxy:
        if proxy:
            opener = request.build_opener(request.ProxyHandler({'http':proxy,'https':proxy}))
        else:
            opener = request.build_opener(request.ProxyHandler({}))
    else:
        opener = request.build_opener(request.ProxyHandler({}))
    return opener

@auto_retry(retry_time)
def _get_response(url, headers=fake_headers_get,use_cookie=True,use_proxy=True):
    # install cookies
    opener = make_opener(use_cookie,use_proxy)

    response = opener.open(
        request.Request(url, headers=headers), None, timeout=timeout
    )

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
def _post_request(url,data,headers=fake_headers_post,use_cookie=True,use_proxy=True):
    opener = make_opener(use_cookie,use_proxy)
    params = parse.urlencode(data).encode()
    response = opener.open(request.Request(url,data=params,headers=headers), timeout=timeout)
    data = response.read()
    if response.info().get('Content-Encoding') == 'gzip':
        data = _ungzip(data)
    elif response.info().get('Content-Encoding') == 'deflate':
        data = _undeflate(data)
    elif response.info().get('Content-Encoding') == 'br':
        data = _unbrotli(data)
    response.data = data
    if len(str(params)) <= 50:
        logging.debug('Post Data to {} with Params {}'.format(url,str(params)))
    else:
        logging.debug('Post Data to {} with a very long params'.format(url))
    return response

def post_data_str(url,data,headers=fake_headers_post,encoding='utf-8',use_cookie=True,use_proxy=True):
    content = _post_request(url,data,headers).data
    data = content.decode(encoding, 'ignore')
    if filter_emoji:
        data = remove_emoji(data)
    return data

def post_data_bytes(url,data,headers=fake_headers_post,encoding='utf-8',use_cookie=True,use_proxy=True):
    response = _post_request(url,data,headers)
    return response.data

def get_content_str(url, encoding='utf-8', headers=fake_headers_get,use_cookie=True,use_proxy=True):
    content = _get_response(url, headers=headers).data
    data = content.decode(encoding, 'ignore')
    if filter_emoji:
        data = remove_emoji(data)
    return data

def get_content_bytes(url, headers=fake_headers_get,use_cookie=True,use_proxy=True):
    content = _get_response(url, headers=headers).data
    return content

def get_redirect_url(url,headers=fake_headers_get,use_cookie=True,use_proxy=True):
    return _get_response(url=url, headers=headers).geturl()

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
    opener = make_opener(use_cookie,use_proxy)
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

def download_yield(url,filename,path='./',headers=fake_headers_get,check=True,use_cookie=True,use_proxy=False):
    file = os.path.join(os.path.abspath(path),_replaceChr(filename))
    if os.path.exists(file):
        size = os.path.getsize(file)
        yield size,size,100.00
    else:
        tmpfile = file+'.download'
        #安装cookies
        opener = make_opener(use_cookie,use_proxy)
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
                            done_size += chunk_size
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

def _join_files(main_file,*files,delete=False):
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
