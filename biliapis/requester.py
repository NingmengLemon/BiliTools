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

import emoji
import brotli

filter_emoji = False
user_name = os.getlogin()
inner_data_path = 'C:\\Users\\{}\\BiliTools\\'.format(user_name)

cookies = None
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

def _get_response(url, headers=fake_headers_get):
    # install cookies
    if cookies:
        opener = request.build_opener(request.HTTPCookieProcessor(cookies))
    else:
        opener = request.build_opener()

    if headers:
        response = opener.open(
            request.Request(url, headers=headers), None, timeout=timeout
        )
    else:
        response = opener.open(url, timeout=timeout)

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

def _post_request(url,data,headers=fake_headers_post):
    if cookies:
        opener = request.build_opener(request.HTTPCookieProcessor(cookies))
    else:
        opener = request.build_opener()
    params = parse.urlencode(data).encode()
    if headers:
        response = opener.open(request.Request(url,data=params,headers=headers), timeout=timeout)
    else:
        response = opener.open(request.Request(url,data=params), timeout=timeout)
    data = response.read()
    if response.info().get('Content-Encoding') == 'gzip':
        data = _ungzip(data)
    elif response.info().get('Content-Encoding') == 'deflate':
        data = _undeflate(data)
    elif response.info().get('Content-Encoding') == 'br':
        data = _unbrotli(data)
    response.data = data
    logging.debug('Post Data to {} with Params {}'.format(url,str(params)))
    return response

def post_data_str(url,data,headers=fake_headers_post,encoding='utf-8'):
    response = _post_request(url,data,headers)
    return response.data.decode(encoding, 'ignore')

def post_data_bytes(url,data,headers=fake_headers_post,encoding='utf-8'):
    response = _post_request(url,data,headers)
    return response.data

def get_cookies(url):
    tmpcookiejar = cookiejar.MozillaCookieJar()
    handler = request.HTTPCookieProcessor(tmpcookiejar)
    opener = request.build_opener(handler)
    opener.open(url)
    return tmpcookiejar

def get_content_str(url, encoding='utf-8', headers=fake_headers_get):
    content = _get_response(url, headers=headers).data
    data = content.decode(encoding, 'ignore')
    if filter_emoji:
        data = emoji.demojize(data)
    return data

def get_content_bytes(url, headers=fake_headers_get):
    content = _get_response(url, headers=headers).data
    return content

def get_redirect_url(url,headers=fake_headers_get):
    return request.urlopen(request.Request(url,headers=headers),None).geturl()

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
        f.write('# Netscape HTTP Cookie File\n# https://curl.haxx.se/rfc/cookie_spec.html\n# This is a generated file!  Do not edit.')
        f.close()
    cookies = cookiejar.MozillaCookieJar(local_cookiejar_path)
    cookies.load()

@atexit.register
def refresh_local_cookies():
    global cookies
    if cookies:
        cookies.save(local_cookiejar_path)

#Download Operation
def download_common(url,tofile,progressfunc=None,headers=fake_headers_get):
    opener = request.build_opener()
    opener.addheaders = _dict_to_headers(headers)
    request.install_opener(opener)
    request.urlretrieve(url,tofile,progressfunc)

def convert_size(self,size):#单位:Byte
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

def download_yield(url,filename,path='./',use_cookies=True,headers=fake_headers_get,check=True):
    file = os.path.join(os.path.abspath(path),_replaceChr(filename))
    if os.path.exists(file):
        yield 0,0,100.00
    else:
        tmpfile = file+'.download'
        if cookies and use_cookies:
            opener = request.build_opener(request.HTTPCookieProcessor(cookies))
        else:
            opener = request.build_opener()
        if os.path.exists(tmpfile):
            size = os.path.getsize(tmpfile)
        else:
            size = 0
        headers = copy.deepcopy(headers)
        headers['Range'] = 'bytes={}-'.format(size)
        chunk_size = 1*1024
        done_size = size
        try:
            with opener.open(request.Request(url,headers=headers)) as fp_web:
                total_size = int(fp_web.getheader('content-length'))
                with open(tmpfile,'ab+') as fp_local:
                    logging.debug('Fetching data from {}, start_byte={}'.format(url,size))
                    while True:
                        data = fp_web.read(chunk_size)
                        if not data:
                            break
                        fp_local.write(data)
                        done_size += chunk_size
                        yield done_size,total_size,round(done_size/total_size*100,2)
            if check:
                if os.path.getsize(tmpfile) != total_size:
                    error_size = os.path.getsize(tmpfile)
                    os.remove(tmpfile)
                    raise RuntimeError('File Size not Match. The size given by server is {} Bytes, '\
                        'howerver the received file\'s size is {} Bytes.'.format(total_size,error_size))
            os.rename(tmpfile,file)
            yield total_size,total_size,100.00
        except error.HTTPError as e:
            if e.code == 416:
                yield size,size,100.00
            else:
                raise e
