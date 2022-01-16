from . import audio,comment,login,manga,media,subtitle,user,video 
from . import bilicodes 
from . import login,other
from . import requester
from .error import BiliError

import winreg
import re

def get_desktop():
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Shell Folders')
    return winreg.QueryValueEx(key,"Desktop")[0]

def second_to_time(sec):
    h = sec // 3600
    sec = sec % 3600
    m = sec // 60
    s = sec % 60
    return '%d:%02d:%02d'%(h,m,s)

def format_img(url,w=None,h=None,f=None):
    '''For *.hdslb.com/bfs/* only.'''
    if '.hdslb.com/bfs' not in url:
        raise RuntimeError('Not-supported URL Type:%s'%url)
    tmp = []
    if w:
        tmp += [str(w)+'w']
    if h:
        tmp += [str(w)+'h']
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
    #用户uid
    res = re.findall(r'space\.bilibili\.com\/([0-9]+)',url,re.I)
    if res:
        return int(res[0]),'uid'
    #同上
    res = re.findall(r'uid([0-9]+)',url,re.I)
    if res:
        return int(res[0]),'uid'
    #漫画id
    res = re.findall(r'mc([0-9]+)',url,re.I)
    if res:
        return int(res[0]),'mcid'
    return None,'unknown'