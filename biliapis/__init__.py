from . import audio,comment,manga,media,subtitle,user,video,danmaku
from . import bilicodes 
from . import login,other
from . import requester
from .error import BiliError

import winreg
import re

__all__ = ['audio','comment','login','manga','media','subtitle','user','video','danmaku',
           'bilicodes','other','requester','BiliError',
           'get_desktop','second_to_time','format_img','parse_url','convert_number']

def get_desktop():
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Shell Folders')
    return winreg.QueryValueEx(key,"Desktop")[0]

def convert_number(a):
    try:
        a = int(a)
    except:
        return '-'
    else:        
        y = a/(10000**2)
        if y >= 1:
            return f'{round(y,2)}亿'
        w = a/10000
        if w >= 1:
            return f'{round(w,2)}万'
        return str(a)

def second_to_time(sec):
    h = sec // 3600
    sec = sec % 3600
    m = sec // 60
    s = sec % 60
    return '%d:%02d:%02d'%(h,m,s)

def format_img(url,w=None,h=None,f='jpg'):
    '''For *.hdslb.com/bfs/* only.'''
    if '.hdslb.com/bfs' not in url:
        raise RuntimeError('Not-supported URL Type:%s'%url)
    tmp = []
    if w:
        tmp += [str(w)+'w']
    if h:
        tmp += [str(h)+'h']
    tmp = '_'.join(tmp)
    if f and f in ['png','jpg','webp']:
        tmp += '.'+f
    if tmp:
        return url+'@'+tmp
    else:
        return url

def parse_url(url):
    if 'b23.tv' in url:#短链接重定向
        url = requester.get_redirect_url(url)
    #音频id
    res = re.findall(r'au([0-9]+)',url,re.I)
    if res:
        return int(res[0]),'auid'
    #bv号
    res = re.findall(r'BV[a-zA-Z0-9]{10}',url,re.I)
    if res:
        return res[0],'bvid'
    #av号
    res = re.findall(r'av([0-9]+)',url,re.I)
    if res:
        return int(res[0]),'avid'
    #专栏号
    res = re.findall(r'cv([0-9]+)',url,re.I)
    if res:
        return int(res[0]),'cvid'
    #整个剧集的id
    res = re.findall(r'md([0-9]+)',url,re.I)
    if res:
        return int(res[0]),'mdid'
    #整个季度的id
    res = re.findall(r'ss([0-9]+)',url,re.I)
    if res:
        return int(res[0]),'ssid'
    #单集的id
    res = re.findall(r'ep([0-9]+)',url,re.I)
    if res:
        return int(res[0]),'epid'
    #手动输入的uid
    res = re.findall(r'uid([0-9]+)',url,re.I)
    if res:
        return int(res[0]),'uid'
    #漫画id
    res = re.findall(r'mc([0-9]+)',url,re.I)
    if res:
        return int(res[0]),'mcid'
    #歌单
    res = re.findall(r'am([0-9]+)',url,re.I)
    if res:
        return int(res[0]),'amid'
    #用户空间相关
    uid = re.findall(r'space\.bilibili\.com\/([0-9]+)',url,re.I)
    if uid:
        uid = int(uid[0])
        #合集
        if 'collectiondetail' in url.lower():
            sid = re.findall(r'sid\=([0-9]+)',url,re.I)
            if sid:
                return (uid,int(sid[0])),'collection'
        #收藏夹
        elif 'favlist' in url.lower():
            fid = re.findall(r'fid\=([0-9]+)',url,re.I)
            if fid:
                return (uid,int(fid[0])),'favlist'
        #系列
        elif 'seriesdetail' in url.lower():
            sid = re.findall(r'sid\=([0-9]+)',url,re.I)
            if sid:
                return (uid,int(sid[0])),'series'
        return uid,'uid'
    return None,'unknown'
