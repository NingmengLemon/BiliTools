from http import cookiejar
from urllib import request, parse, error
import os
import re
import sys
import time
import json
import zlib,gzip
import requests
import _thread
import hashlib
#GUI
import tkinter as tk
import tkinter.messagebox as msgbox
import tkinter.ttk as ttk

import bilicodes
#av号统称为avid, bv号统称为bvid.
#音频id统称为auid

#abvid offline converter's pre-data
_table = 'fZodR9XQDSUm21yCkr6zBqiveYah8bt4xsWpHnJE7jL5VG3guMTKNPAwcF'
_tr = {}
for _ in range(58):
    _tr[_table[_]] = _
_s = [11,10,3,8,4,6]
_xor = 177451812
_add = 8728348608

#requester's pre-data
cookies = None
fake_headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',  # noqa
    'Accept-Charset': 'UTF-8,*;q=0.5',
    'Accept-Encoding': 'gzip,deflate,sdch',
    'Accept-Language': 'en-US,en;q=0.8',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.74 Safari/537.36 Edg/79.0.309.43',  # noqa
    'Referer':'https://www.bilibili.com/'
}

#requester
def _ungzip(data):
    """Decompresses data for Content-Encoding: gzip.
    """
    from io import BytesIO
    buffer = BytesIO(data)
    f = gzip.GzipFile(fileobj=buffer)
    return f.read()

def _undeflate(data):
    """Decompresses data for Content-Encoding: deflate.
    (the zlib compression is used.)
    """
    decompressobj = zlib.decompressobj(-zlib.MAX_WBITS)
    return decompressobj.decompress(data)+decompressobj.flush()

def _dict_to_headers(dict_to_conv):
    keys = list(dict_to_conv.keys())
    values = list(dict_to_conv.values())
    res = []
    for i in range(len(keys)):
        res.append((keys[i],values[i]))
    return res

def _get_response(url, headers=fake_headers):
    # install cookies
    if cookies:
        opener = request.build_opener(request.HTTPCookieProcessor(cookies))
    else:
        opener = request.build_opener()

    if headers:
        response = opener.open(
            request.Request(url, headers=headers), None
        )
    else:
        response = opener.open(url)

    data = response.read()
    if response.info().get('Content-Encoding') == 'gzip':
        data = _ungzip(data)
    elif response.info().get('Content-Encoding') == 'deflate':
        data = _undeflate(data)
    response.data = data
    return response

def get_content_str(url, encoding='utf-8', headers=fake_headers):
    content = _get_response(url, headers=headers).data
    return str(content, encoding, 'ignore')

def get_content_bytes(url, headers=fake_headers):
    content = _get_response(url, headers=headers).data
    return content

def clear_cookies():
    global cookies
    cookies = None

def load_cookies(cookiefile):
    global cookies
    if not cookiefile:
        return 1
    if cookiefile.endswith('.txt'):
        # MozillaCookieJar treats prefix '#HttpOnly_' as comments incorrectly!
        # do not use its load()
        # see also:
        #   - https://docs.python.org/3/library/http.cookiejar.html#http.cookiejar.MozillaCookieJar
        #   - https://github.com/python/cpython/blob/4b219ce/Lib/http/cookiejar.py#L2014
        #   - https://curl.haxx.se/libcurl/c/CURLOPT_COOKIELIST.html#EXAMPLE
        #cookies = cookiejar.MozillaCookieJar(cookiefile)
        #cookies.load()
        from http.cookiejar import Cookie
        cookies = cookiejar.MozillaCookieJar()
        now = time.time()
        ignore_discard, ignore_expires = False, False
        with open(cookiefile, 'r', encoding='utf-8') as f:
            for line in f:
                # last field may be absent, so keep any trailing tab
                if line.endswith("\n"): line = line[:-1]

                # skip comments and blank lines XXX what is $ for?
                if (line.strip().startswith(("#", "$")) or
                    line.strip() == ""):
                    if not line.strip().startswith('#HttpOnly_'):  # skip for #HttpOnly_
                        continue

                domain, domain_specified, path, secure, expires, name, value = \
                        line.split("\t")
                secure = (secure == "TRUE")
                domain_specified = (domain_specified == "TRUE")
                if name == "":
                    # cookies.txt regards 'Set-Cookie: foo' as a cookie
                    # with no name, whereas http.cookiejar regards it as a
                    # cookie with no value.
                    name = value
                    value = None

                initial_dot = domain.startswith(".")
                if not line.strip().startswith('#HttpOnly_'):  # skip for #HttpOnly_
                    assert domain_specified == initial_dot

                discard = False
                if expires == "":
                    expires = None
                    discard = True

                # assume path_specified is false
                c = Cookie(0, name, value,
                           None, False,
                           domain, domain_specified, initial_dot,
                           path, False,
                           secure,
                           expires,
                           discard,
                           None,
                           None,
                           {})
                if not ignore_discard and c.discard:
                    continue
                if not ignore_expires and c.is_expired(now):
                    continue
                cookies.set_cookie(c)
        return 0

    elif cookiefile.endswith(('.sqlite', '.sqlite3')):
        import sqlite3, shutil, tempfile
        temp_dir = tempfile.gettempdir()
        temp_cookiefile = os.path.join(temp_dir, 'temp_cookiefile.sqlite')
        shutil.copy2(cookiefile, temp_cookiefile)

        cookies = cookiejar.MozillaCookieJar()
        con = sqlite3.connect(temp_cookiefile)
        cur = con.cursor()
        cur.execute("""SELECT host, path, isSecure, expiry, name, value
        FROM moz_cookies""")
        for item in cur.fetchall():
            c = cookiejar.Cookie(
                0, item[4], item[5], None, False, item[0],
                item[0].startswith('.'), item[0].startswith('.'),
                item[1], False, item[2], item[3], item[3] == '', None,
                None, {},
            )
            cookies.set_cookie(c)
        return 0

    else:
        # TODO: Chromium Cookies
        # SELECT host_key, path, secure, expires_utc, name, encrypted_value
        # FROM cookies
        # http://n8henrie.com/2013/11/use-chromes-cookies-for-easier-downloading-with-python-requests/
        return 1

def find_cookies():
    #find cookies
    username = os.getlogin()
    chromeCookie = os.getenv('LOCALAPPDATA')+"\\Google\\Chrome\\User Data\\Default\\Cookies"#Chrome的Cookie加密了，暂不支持
    firefoxCookie = os.getenv('APPDATA')+"\\Mozilla\\Firefox\\Profiles\\"
    #if os.path.exists(chromeCookie):
    #    cookie = chromeCookie
    #    print('Chrome Cookies Loaded.')
    cookie = None
    if os.path.exists(firefoxCookie):
        for f in os.listdir(firefoxCookie):
            if f.endswith('.default-release'):
                firefoxCookie += f+'\\cookies.sqlite'
                break
        cookie = firefoxCookie
        return cookie
    else:
        return None

def download(url,tofile,progressfunc=None,headers=fake_headers):
    opener = request.build_opener()
    opener.addheaders = _dict_to_headers(headers)
    request.install_opener(opener)
    request.urlretrieve(url,tofile,progressfunc)

def get_redirect_url(url,headers=fake_headers):
    return request.urlopen(request.Request(url,headers=headers),None).geturl()

def download_with_requests(url,tofile,callbackfunc=None,use_cookies=True,headers=fake_headers):
    if os.path.exists(tofile):
        raise RuntimeError('File already exists.')
    tmp_file = tofile+'.download'
    #Load Header
    #headers = fake_headers
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
    
    
#Download GUI
class DownloadWindow(object):
    def __init__(self,url,topath='./',filename='Unknown',askopen=True,use_fakeheaders=True,use_cookies=True,topmost=True):
        self.data = {
            'url':url,
            'topath':os.path.abspath(topath)+'\\',
            'filename':filename,
            'totalsize':0,
            'donesize':0,
            'percent':0,
            'condition':-1,#-1:未开始,0:进行中,1:成功,2:失败,3:用户中止
            'condition_str':'Waiting...',
            'user_stop':False,
            'error_info':''
            }

        self.options = {
            'askopen':askopen,
            'fake_headers':use_fakeheaders,
            'cookies':use_cookies
            }
        
        #定义窗口
        self.window = tk.Tk()
        self.window.title('Downloader')
        self.window.resizable(height=False,width=False)
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.window.wm_attributes('-topmost',topmost)

        #定义组件
        self.widgets = {
            'text1':tk.Label(self.window,text='文件名:'),
            'label_filename':tk.Label(self.window,text='Unknown'),
            'text2':tk.Label(self.window,text='源:'),
            'label_url':tk.Label(self.window,text='-'),
            'text3':tk.Label(self.window,text='保存至:'),
            'label_topath':tk.Label(self.window,text='-'),
            'text5':tk.Label(self.window,text='文件大小:'),
            'label_size':tk.Label(self.window,text='0 B'),
            'text6':tk.Label(self.window,text='已下载大小:'),
            'label_donesize':tk.Label(self.window,text='0 B'),
            'text7':tk.Label(self.window,text='状态:'),
            'label_condition':tk.Label(self.window,text='Waiting...'),
            'progressbar':ttk.Progressbar(self.window,orient='horizontal',length=400,mode='determinate',maximum=10000,value=0),
            'label_percent':tk.Label(self.window,text='0.00%'),

            '_grid_table':[#(name,column,row,columnspan,sticky)
                ('text1',0,0,1,'w'),('label_filename',1,0,3,'w'),
                ('text2',0,1,1,'w'),('label_url',1,1,3,'w'),
                ('text3',0,2,1,'w'),('label_topath',1,2,3,'w'),
                ('text5',0,3,1,'w'),('label_size',1,3,3,'w'),
                ('text6',0,4,1,'w'),('label_donesize',1,4,3,'w'),
                ('text7',0,5,1,'w'),('label_condition',1,5,3,'w'),
                ('progressbar',0,6,3,'w'),('label_percent',3,6,1,'e')
                ]
            }
        
        #放置组件
        for coor in self.widgets['_grid_table']:
            self.widgets[coor[0]].grid(column=coor[1],row=coor[2],columnspan=coor[3],sticky=coor[4])
        
        self.widgets['label_filename']['text'] = self.data['filename']
        self.widgets['label_url']['text'] = self._cut(self.data['url'])
        self.widgets['label_topath']['text'] = self._cut(self.data['topath'])
        self._autofresh()
        _thread.start_new(self._download_thread,())
        self.window.mainloop()

    def _cut(self,string,max_length=75):
        if len(string) > max_length:
            return string[:max_length]+'...'
        else:
            return string

    def _autofresh(self):
        self.widgets['label_condition']['text'] = self.data['condition_str']
        if self.data['condition'] == -1:
            self.window.after(50,self._autofresh)
        elif self.data['condition'] == 0:
            if self.data['totalsize'] != 0:
                self.data['percent'] = self.data['donesize']/self.data['totalsize']*100
            else:
                self.data['percent'] = 0
            self.widgets['label_size']['text'] = self._convert_size(self.data['totalsize'])
            self.widgets['label_donesize']['text'] = self._convert_size(self.data['donesize'])
            self.widgets['label_percent']['text'] = '%.2f%%'%self.data['percent']
            self.widgets['progressbar']['value'] = int(self.data['percent']*100)
            #print('%.2f%%'%self.data['percent'])
            self.window.after(50,self._autofresh)
        else:
            self._over(self.data['condition'])

    def _over(self,reason=1):#reason = 1,2,3
        if reason == 1:
            self.widgets['label_donesize']['text'] = self._convert_size(self.data['totalsize'])
            self.widgets['label_percent']['text'] = '100.00%'
            self.widgets['progressbar']['value'] = 10000
            self.data['condition'] = 1
            if self.options['askopen']:
                if msgbox.askyesno('','任务完成！\n打开输出目录？'):
                    os.system('explorer "%s"'%self.data['topath'])
            self.close(True)
        elif reason == 2:
            self.data['condition'] = 2
            self.data['condition_str'] = 'Error'
            error = self.data['error_info']
            msgbox.showerror('','发生错误：\n'+str(error))
            self.close(True)
        elif reason == 3:
            self.data['condition'] = 3
            self.data['user_stop'] = True
            msgbox.showinfo('','用户终止了操作。\n当前已下载字节数：'+str(self.data['donesize']))
            self.close(True)

    def _download_thread(self):
        tofile = self.data['topath'] + self.data['filename']
        url = self.data['url']
        if os.path.exists(tofile):
            self.data['error_info'] = 'File already Exists.'
            self.data['condition'] = 2
            return
        tmp_file = tofile+'.download'
        try:
            self.data['condition'] = -1
            #Load Header
            self.data['condition_str'] = 'Loading Headers & Cookies...'
            if self.options['fake_headers']:
                headers = fake_headers
            if cookies and self.options['cookies']:
                cookies_dict = requests.utils.dict_from_cookiejar(cookies)
            else:
                cookies_dict = {}
            #Get Response
            self.data['condition_str'] = 'Checking File Size...'
            response = requests.get(url,stream=True,headers=headers,cookies=cookies_dict)
            #Check Existed File
            self.data['condition_str'] = 'Checking Existed File...'
            file_size = int(response.headers['content-length'])
            self.data['totalsize'] = file_size
            if os.path.exists(tmp_file):
                start_byte = os.path.getsize(tmp_file)
            else:
                start_byte = 0
            if start_byte >= file_size:
                os.rename(tmp_file,tofile)
            else:
                #Download
                headers['Range'] = f'bytes={start_byte}-{file_size}'
                self.data['condition'] = 0
                self.data['condition_str'] = 'Fetching Data...'
                req = requests.get(url,headers=headers,stream=True,cookies=cookies_dict)
                counter = 0
                writemode = 'ab+'
                with open(tmp_file,writemode) as f:
                    for chunk in req.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
                            f.flush()
                            counter += 1
                            self.data['donesize'] = start_byte+(counter*1024)
                            if self.data['user_stop']:
                                break
                if not self.data['user_stop']:
                    os.rename(tmp_file,tofile)
            
        except Exception as e:
            self.data['error_info'] = str(e)
            self.data['condition'] = 2
            self.data['condition_str'] = 'Error'
            return
        else:
            if self.data['user_stop']:
                self.data['condition'] = 3
                self.data['condition_str'] = 'User Stopped.'
                return
            else:
                self.data['condition'] = 1
                self.data['condition_str'] = 'Done.'
                return

    def _convert_size(self,size):#单位:Byte
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

    def close(self,force=False):
        if not force:
            cond = self.data['condition']
            if cond == -1 or cond == 0:
                if msgbox.askyesno('','任务未完成，真的要退出吗？'):
                    self._over(3)
                    return
                else:
                    return
        try:
            self.window.quit()
            self.window.destroy()
        except:
            pass

#APIs
    
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

def bvid_to_avid_online(bvid):
    data = get_content_str('https://api.bilibili.com/x/web-interface/archive/stat?bvid='+bvid)
    data = json.loads(data)['data']
    return data['aid']

def bvid_to_avid_offline(bvid):
    r = 0
    for i in range(6):
        r += _tr[bvid[_s[i]]]*58**i
    return (r-_add)^_xor

def avid_to_bvid_offline(avid):
    avid = (avid^_xor)+_add
    r = list('BV1  4 1 7  ')
    for i in range(6):
        r[_s[i]] = _table[avid//58**i%58]
    return ''.join(r)

def bvid_to_cid_online(bvid):
    data = get_content_str(f'https://api.bilibili.com/x/player/pagelist?bvid={bvid}&jsonp=jsonp')
    data = json.loads(data)['data']
    res = []
    for i in data:
        res.append(i['cid'])
    return res

def avid_to_cid_online(avid):
    data = get_content_str(f'https://api.bilibili.com/x/player/pagelist?aid={avid}&jsonp=jsonp')
    data = json.loads(data)['data']
    res = []
    for i in data:
        res.append(i['cid'])
    return res

def get_danmaku_xmlstr(cid):
    data = get_content_str(f'https://comment.bilibili.com/{cid}.xml')
    return data

def search_video(keyword,page=1,order='totalrank',zone=0,duration=0):
    '''order = totalrank 综合排序/click 最多点击/pubdate 最新发布/dm 最多弹幕/stow 最多收藏/scores 最多评论
    zone = 0/tid
    duration = 0(All)/1(0-10)/2(10-30)/3(30-60)/4(60+)
    '''
    api = f'http://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword={parse.quote(keyword)}&tid={zone}&duration={duration}&page={page}'
    data = json.loads(get_content_str(api))
    _error_raiser(data['code'],data['message'])
    data = data['data']
    tmp = []
    for res in data['result']:
        tmp.append({
            'avid':res['aid'],
            'bvid':res['bvid'],
            'uploader':{
                'name':res['author'],
                'uid':res['mid']
                },
            'title':res['title'].replace('<em class="keyword">','').replace('</em>',''),
            'description':res['description'],
            'tname_main':bilicodes.video_zone[int(res['typeid'])],
            'tname_child':res['typename'],
            'url':res['arcurl'],
            'cover':res['pic'],
            'num_view':res['play'],
            'num_danmaku':res['video_review'],
            'num_collect':res['favorites'],
            'tags':res['tag'].split(','),
            'num_comment':res['review'],
            'date_publish':res['pubdate'],
            'duration':res['duration'],
            'is_union_video':bool(res['is_union_video']),
            'hit_type':res['hit_columns']
            })
    result = {
        'seid':data['seid'],
        'page':data['page'],
        'pagesize':data['pagesize'],
        'num_result':data['numResults'],#max=1000
        'num_pages':data['numPages'],#max=50
        'time_cost':data['cost_time']['total'],
        'result':tmp
        }
    return result

def search_user(keyword,page=1,order='0',order_sort=0,user_type=0):
    '''order = 0(default) / fans / level
    order_sort = 0(high->low) / 1(low->high)
    user_type = 0(All) / 1(Uploader) / 2(CommonUser) / 3(CertifiedUser)
    '''
    api = f'http://api.bilibili.com/x/web-interface/search/type?search_type=bili_user&keyword={parse.quote(keyword)}&page={page}&order={order}&order_sort={order_sort}'
    data = json.loads(get_content_str(api))
    _error_raiser(data['code'],data['message'])
    data = data['data']
    tmp = []
    for res in data['result']:
        tmp.append({
            'uid':res['mid'],
            'name':res['uname'],
            'sign':res['usign'],
            'face':res['upic'],
            'fans':res['fans'],
            'videos':res['videos'],
            'level':res['level'],
            'gender':{1:'Male',2:'Female',3:'Unknown'}[res['gender']],
            'is_uploader':bool(res['is_upuser']),
            'is_live':bool(res['is_live']),
            'room_id':res['room_id'],
            'official_verify':{
                'type':{127:None,0:'Personal',1:'Organization'}[res['official_verify']['type']],
                'desc':res['official_verify']['desc'],
                },
            'hit_type':res['hit_columns']
            })
    result = {
        'seid':data['seid'],
        'page':data['page'],
        'pagesize':data['pagesize'],
        'num_result':data['numResults'],#max=1000
        'num_pages':data['numPages'],#max=50
        'time_cost':data['cost_time']['total'],
        'result':tmp
        }
    return result

def search_bangumi(keyword,page=1):
    api = f'http://api.bilibili.com/x/web-interface/search/type?search_type=media_bangumi&keyword={parse.quote(keyword)}&page={page}'
    data = json.loads(get_content_str(api))
    _error_raiser(data['code'],data['message'])
    data = data['data']
    tmp = []
    for res in data['result']:
        tmp.append({
            'mdid':res['media_id'],
            'ssid':res['season_id'],
            'title':res['title'].replace('<em class="keyword">','').replace('</em>',''),
            'title_org':res['org_title'].replace('<em class="keyword">','').replace('</em>',''),
            'cover':'https:'+res['cover'],
            'media_type':bilicodes.media_type[res['media_type']],
            'season_type':bilicodes.media_type[res['season_type']],
            'is_follow':bool(res['is_follow']),#Login
            'area':res['areas'],
            'style':res['styles'],
            'cv':res['cv'],
            'staff':res['staff'],
            'url':res['goto_url'],
            'time_publish':res['pubtime'],
            'hit_type':res['hit_columns']
            })
    result = {
        'seid':data['seid'],
        'page':data['page'],
        'pagesize':data['pagesize'],
        'num_result':data['numResults'],#max=1000
        'num_pages':data['numPages'],#max=50
        'time_cost':data['cost_time']['total'],
        'result':tmp
        }
    return result
    
def get_video_detail(avid=None,bvid=None):
    '''Choose one parameter between avid and bvid'''
    if avid != None:
        api = 'http://api.bilibili.com/x/web-interface/view?aid=%s'%avid
    elif bvid != None:
        api = 'http://api.bilibili.com/x/web-interface/view?bvid='+bvid
    else:
        raise RuntimeError('You must choose one between avid and bvid.')
    data = get_content_str(api)
    data = json.loads(data)
    _error_raiser(data['code'],data['message'])
    data = data['data']
    return _video_detail_handler(data,True)

def _video_detail_handler(data,detailmode=True):
    res = {
        'bvid':data['bvid'],
        'avid':data['aid'],
        'main_zone':bilicodes.video_zone[int(data['tid'])],
        'child_zone':data['tname'],
        'part_number':data['videos'],
        'picture':data['pic'],
        'title':data['title'],
        'date_publish':data['pubdate'],
        'description':data['desc'],
        'uploader':{
            'uid':data['owner']['mid'],
            'name':data['owner']['name'],
            'face':data['owner']['face']
            },
        'stat':{
            'view':data['stat']['view'],
            'danmaku':data['stat']['danmaku'],
            'reply':data['stat']['reply'],
            'collect':data['stat']['favorite'],
            'coin':data['stat']['coin'],
            'share':data['stat']['share'],
            'like':data['stat']['like'],
            'rank_now':data['stat']['now_rank'],
            'rank_his':data['stat']['his_rank']
            },
        }
    if detailmode:
        parts = []
        for i in data['pages']:
            parts.append({'cid':i['cid'],
                          'title':i['part']
                          })
        res['parts'] = parts
    return res

def get_blackroom(page):
    data = get_content_str(f'https://api.bilibili.com/x/credit/blocked/list?jsonp=jsonp&otype=0&pn={page}')
    data = json.loads(data)['data']
    return data

def get_emotions(business='reply'):
    '''business = reply / dynamic'''
    data = get_content_str(f'http://api.bilibili.com/x/emote/user/panel/web?business={business}')
    data = json.loads(data)
    _error_raiser(data['code'],data['message'])
    data = data['data']['packages']
    res = []
    for package in data:
        tmp = []
        for i in package['emote']:
            tmp.append({
                'id':i['id'],
                'text':i['text'],
                'url':i['url']
                })
        res.append({
            'id':package['id'],
            'text':package['text'],
            'url':package['url'],
            'emote':tmp
            })
    return res

def download_emotions(path='./emotions/',pause_time=1,show_process=False):
    def print_(text,end='\n'):
        if show_process:
            print(text,end=end)
        else:
            pass
    if not os.path.exists(path):
        os.mkdir(path)
    emotions = get_emotions()
    for pkg in emotions:
        path_ = path+pkg['text']+'/'
        print_('表情包 %s id%s'%(pkg['text'],pkg['id']))
        if not os.path.exists(path_):
            os.mkdir(path_)
        for i in pkg['emote']:
            if _is_url(i['url']):
                _thread.start_new(download,(i['url'],path_+i['text']+'.png'))
            else:
                with open(path_+'data.txt','a+',encoding='utf-8') as f:
                    f.write('%s\t%s\n'%(i['id'],i['text']))
            print_('表情 %s id%s'%(i['text'],i['id']))
            time.sleep(pause_time)

def _is_url(url):
    if re.match(r'^https?:/{2}\w.+$', url):
        return True
    else:
        return False

def _error_raiser(code,message=None):
    if code != 0:
        if message:
            raise RuntimeError('Code %s: %s'%(code,message))
        else:
            raise RuntimeError('Code %s: %s'%(code,bilicodes.error_code[code]))

def get_media_detail(ssid=None,epid=None,mdid=None):
    '''Choose one parameter from ssid, epid and mdid'''
    if ssid != None:
        api = 'http://api.bilibili.com/pgc/view/web/season?season_id=%s'%ssid
    elif epid != None:
        api = 'http://api.bilibili.com/pgc/view/web/season?ep_id=%s'%epid
    elif mdid != None:
        api = 'http://api.bilibili.com/pgc/review/user?media_id=%s'%mdid
        data = get_content_str(api)
        data = json.loads(data)
        _error_raiser(data['code'],data['message'])
        data = data['result']['media']
        api = 'http://api.bilibili.com/pgc/view/web/season?season_id=%s'%data['season_id']
    else:
        raise RuntimeError('You must choose one parameter from ssid, epid and mdid.')
    data = get_content_str(api)
    data = json.loads(data)
    _error_raiser(data['code'],data['message'])
    data = data['result']
    episodes = []
    for ep in data['episodes']:
        episodes.append({
            'avid':ep['aid'],
            'bvid':ep['bvid'],
            'cid':ep['cid'],
            'epid':ep['id'],
            'cover':ep['cover'],
            'title':ep['title'],
            'title_completed':ep['long_title'],
            'time_publish':ep['pub_time'],
            'url':ep['link']
            })
    sections = []
    for sec in data['section']:
        sections_ = []
        for sec_ in sec['episodes']:
            sections_.append({
                'avid':sec_['aid'],
                'bvid':sec_['bvid'],
                'cid':sec_['cid'],
                'epid':sec_['id'],
                'cover':sec_['cover'],
                'title':sec_['title'],
                'url':sec_['share_url']
                })
        sections.append({
            'title':sec['title'],
            'episodes':sections_
            })
    result = {
        'bgpic':data['bkg_cover'],
        'cover':data['cover'],
        'episodes':episodes,
        'description':data['evaluate'],
        'mdid':data['media_id'],
        'record':data['record'],
        'title':data['title'],
        'sections':sections,
        'stat':{
            'coin':data['stat']['coins'],
            'danmaku':data['stat']['danmakus'],
            'collect':data['stat']['favorites'],
            'like':data['stat']['likes'],
            'reply':data['stat']['reply'],
            'share':data['stat']['share'],
            'view':data['stat']['views']
            },
        'uploader':{
            'uid':data['up_info']['mid'],
            'face':data['up_info']['avatar'],
            'follower':data['up_info']['follower'],
            'name':data['up_info']['uname']
        }
    }
    return result

def get_video_recommend(avid=None,bvid=None):
    '''Choose one parameter between avid and bvid'''
    if avid != None:
        api = 'http://api.bilibili.com/x/web-interface/archive/related?aid=%s'%avid
    elif bvid != None:
        api = 'http://api.bilibili.com/x/web-interface/archive/related?bvid='+bvid
    else:
        raise RuntimeError('You must choose one parameter between avid and bvid.')
    data = get_content_str(api)
    data = json.loads(data)
    _error_raiser(data['code'],data['message'])
    data = data['data']
    res = []
    for data_ in data:
        res.append(_video_detail_handler(data_,False))
    return res

def get_video_stream_dash(cid,avid=None,bvid=None):
    '''Choose one parameter between avid and bvid'''
    if avid != None:
        api = 'http://api.bilibili.com/x/player/playurl?avid=%s&cid=%s&fnval=16&fourk=1'%(avid,cid)
    elif bvid != None:
        api = 'http://api.bilibili.com/x/player/playurl?bvid=%s&cid=%s&fnval=16&fourk=1'%(bvid,cid)
    else:
        raise RuntimeError('You must choose one parameter between avid and bvid.')
    data = get_content_str(api)
    data = json.loads(data)
    _error_raiser(data['code'],data['message'])
    data = data['data']['dash']
    audio = []
    for au in data['audio']:
        audio.append({
            'quality':bilicodes.stream_dash_audio_quality[au['id']],
            'url':au['baseUrl'],
            'type':au['codecs'],
            })
    video = []
    for vi in data['video']:
        video.append({
            'quality':bilicodes.stream_dash_video_quality[vi['id']],
            'url':vi['baseUrl'],
            'type':vi['codecs'],
            'width':vi['width'],
            'height':vi['height'],
            'frame_rate':vi['frameRate'],
            
            })
    stream = {
        'audio':audio,
        'video':video
        }
    return stream

def get_login_info(): #Cookies is Required.
    api = 'http://api.bilibili.com/x/web-interface/nav'
    data = get_content_str(api)
    data = json.loads(data)
    _error_raiser(data['code'],data['message'])
    data = data['data']
    res = {
        'uid':data['mid'],
        'name':data['uname'],
        'vip_type':{0:'非大会员',1:'月度大会员',2:'年度及以上大会员'}[data['vipType']],
        'coin':data['money'],
        'level':data['level_info']['current_level'],
        'exp':data['level_info']['current_exp'],
        'moral':data['moral'],#max=70
        'face':data['face']
        }
    return res

def get_user_info(uid):
    api = 'http://api.bilibili.com/x/space/acc/info?mid=%s'%uid
    data = get_content_str(api)
    data = json.loads(data)
    _error_raiser(data['code'],data['message'])
    data = data['data']
    res = {
        'uid':data['mid'],
        'name':data['name'],
        'coin':data['coins'],
        'level':data['level'],
        'face':data['face'],
        'sign':data['sign'],
        'birthday':data['birthday'],
        'head_img':data['top_photo'],
        'sex':data['sex'],
        'vip_type':{0:'非大会员',1:'月度大会员',2:'年度及以上大会员'}[data['vip']['type']]
        }
    return res

def get_audio_stream(auid,quality=3,platform='web',uid=0):
    '''quality = 0(128K)/1(192K)/2(320K)/3(FLAC)'''
    api = 'http://api.bilibili.com/audio/music-service-c/url?songid=%s&quality=%s&privilege=2&mid=%s&platform=%s'%(auid,quality,uid,platform)
    data = get_content_str(api)
    data = json.loads(data)
    _error_raiser(data['code'],data['msg'])
    data = data['data']
    res = {
        'auid':data['sid'],
        'quality':{-1:'192K试听',0:'128K',1:'192K',2:'320K',3:'FLAC'}[data['type']],
        'size':data['size'],#(Byte)
        'url':data['cdns'][0],
        'title':data['title'],
        'cover':data['cover']
        }
    return res

def get_audio_info(auid):
    api = 'http://www.bilibili.com/audio/music-service-c/web/song/info?sid=%s'%auid
    data = get_content_str(api)
    data = json.loads(data)
    _error_raiser(data['code'],data['msg'])
    data = data['data']
    res = {
        'auid':data['id'],
        'title':data['title'],
        'cover':data['cover'],
        'description':data['intro'],
        'lyrics_url':data['lyric'],
        'uploader':{
            'uid':data['uid'],
            'name':data['uname']
            },
        'author':data['author'],
        'length':data['duration'],
        'publish_time':data['passtime'],
        'connect_video':{
            'avid':data['aid'],
            'bvid':data['bvid'],
            'cid':data['cid']
            },
        'stat':{
            'coin':data['coin_num'],
            'play':data['statistic']['play'],
            'collect':data['statistic']['collect'],
            'share':data['statistic']['share']
            }
        }
    return res

def get_audio_tags(auid):
    api = 'http://www.bilibili.com/audio/music-service-c/web/tag/song?sid=%s'%auid
    data = get_content_str(api)
    data = json.loads(data)
    _error_raiser(data['code'],data['msg'])
    data = data['data']
    tags = []
    for item in data:
        tags += [item['info']]
    return tags

def get_audio_lyrics(auid):
    api = 'http://www.bilibili.com/audio/music-service-c/web/song/lyric?sid=%s'%auid
    data = get_content_str(api)
    data = json.loads(data)
    _error_raiser(data['code'],data['msg'])
    data = data['data']
    return data

def get_redirect_url(url):
    return requester.get_redirect_url(url)

def parse_url(url):
    if 'b23.tv' in url:#短链接重定向
        url = requester.get_redirect_url(url)
        
    res = re.findall(r'au[0-9]+',url,re.I)#音频id
    if res:
        return int(res[0][2:]),'auid'
    
    res = re.findall(r'av[0-9]+',url,re.I)#av号
    if res:
        return int(res[0][2:]),'avid'
    
    res = re.findall(r'BV[a-zA-Z0-9]{10}',url,re.I)#bv号
    if res:
        return res[0],'bvid'
    
    res = re.findall(r'cv[0-9]+',url,re.I)#专栏号
    if res:
        return int(res[0][2:]),'cvid'
    
    res = re.findall(r'md[0-9]+',url,re.I)#单剧集id
    if res:
        return res[0][2:],'mdid'
    
    res = re.findall(r'ss[0-9]+',url,re.I)#整个剧集的id
    if res:
        return res[0][2:],'ssid'
    
    res = re.findall(r'ep[0-9]+',url,re.I)#整个剧集的id
    if res:
        return res[0][2:],'epid'
    
    return None,'unknown'

def filter_danmaku_xml(xmlstr,regulars=None,keywords=None,users=None):
    xmlstr = xmlstr.replace('><','>\n<')
    res = []
    for item in xmlstr.split('\n'):
        tmp = item
        if item.startswith('<d'):
            flag = False
            parameters = re.findall(r'\<d p=\"[a-f0-9\.\,]+\"\>',item)[0]
            text = item.replace(parameters,'')[:-4]
            parameters = parameters[6:-2].split(',')
            if regulars:
                for regular in regulars:
                    if re.match(regular,text):
                        flag = True
                        break
            if keywords and not flag:
                for keyword in keywords:
                    if keyword in text:
                        flag = True
                        break
            if users and not flag:
                for user in users:
                    if parameters[-2] == user:
                        flag = True
                        break
            if not flag:
                res += [tmp]
        else:
            res += [tmp]
        
    return '\n'.join(res)

def load_danmaku_filter(file):
    with open(file,'r',encoding='utf-8') as f:
        content = f.read()
    regulars = re.findall(r'\<item enabled=\"true\"\>r\=.+\</item\>',content)
    keywords = re.findall(r'\<item enabled=\"true\"\>t\=.+\</item\>',content)
    users = re.findall(r'\<item enabled=\"true\"\>u\=.+\</item\>',content)
    for i in range(0,len(regulars)):
        regulars[i] = regulars[i][23:-7]
    for i in range(0,len(keywords)):
        keywords[i] = keywords[i][23:-7]
    for i in range(0,len(users)):
        users[i] = users[i][23:-7]
    return regulars,keywords,users
