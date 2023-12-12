from .error import error_raiser,BiliError
from . import requester
import json
from http import cookiejar
import copy
import time
import os
import threading
import typing
import logging

import binascii
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from lxml import etree

__all__ = ['get_csrf','dict_from_cookiejar','get_login_info','get_login_url','check_scan','check_login','make_cookiejar','exit_login']
ref_token_path = './'
ref_token_filename = 'refresh_token'
_reftoken_access_lock = threading.Lock()

def _save_reftoken(token):
    with _reftoken_access_lock:
        file = os.path.join(ref_token_path,ref_token_filename)
        with open(file,'w+',encoding='utf-8') as f:
            f.write(token)
    logging.info("Refresh Token saved")

def _get_reftoken():
    with _reftoken_access_lock:
        file = os.path.join(ref_token_path,ref_token_filename)
        if os.path.exists(file):
            with open(file, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return None
        
def _del_reftoken():
    with _reftoken_access_lock:
        file = os.path.join(ref_token_path,ref_token_filename)
        if os.path.exists(file):
            os.remove(file)

def get_spi():
    api = 'https://api.bilibili.com/x/frontend/finger/spi'
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'])
    return data['data']

def dict_from_cookiejar(cj):
    cookie_dict = {}

    for cookie in cj:
        cookie_dict[cookie.name] = cookie.value

    return cookie_dict

def get_csrf(cj): # 因为csrf比较常用, 所以单独抠出来做一个函数
    if cj:
        cjdict = dict_from_cookiejar(cj)
        if 'bili_jct' in cjdict:
            return cjdict['bili_jct']
    return None

def get_login_url_legacy():
    api = 'https://passport.bilibili.com/qrcode/getLoginUrl'
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'])
    data = data['data']
    loginurl = data['url']
    oauthkey = data['oauthKey']
    return loginurl,oauthkey

def check_scan_legacy(oauthkey):
    headers = copy.deepcopy(requester.fake_headers_post)
    headers['Host'] = 'passport.bilibili.com'
    headers['Referer'] = "https://passport.bilibili.com/login"
    data = json.loads(requester.post_data_str(
        'https://passport.bilibili.com/qrcode/getLoginInfo',
        {'oauthKey':oauthkey},headers
        ))
    #-1：密钥错误 -2：密钥超时 -4：未扫描 -5：未确认
    #error_raiser(data['code'],data['message'])
    status = data['status']
    if status:
        return True,data['data']['url'],0 #成功与否,URL,状态码
    else:
        return False,None,data['data']

def get_login_url():
    api = 'https://passport.bilibili.com/x/passport-login/web/qrcode/generate'
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'], data['message'])
    data = data['data']
    loginurl = data['url']
    oauthkey = data['qrcode_key']
    return loginurl,oauthkey

def check_scan(oauthkey):
    api = 'https://passport.bilibili.com/x/passport-login/web/qrcode/poll'
    api += '?qrcode_key=%s'%oauthkey
    # 涉及到 cookies 的操作需要更底层地进行操纵
    logging.debug("Checking scanning status...")
    with requester.get(api) as response:
        data = requester.read_and_decode_data(response).decode('utf-8','ignore')
        data = json.loads(data)
        error_raiser(data['code'],data['message'])
        data = data['data']
        #
        #-1：密钥错误 -2：密钥超时 -4：未扫描 -5：未确认
        status = data['code']
        if status==0:
            _save_reftoken(data['refresh_token'])
            if requester.cookies:
                # 返回的 response 被做过特殊处理, 拥有了 request 属性
                requester.cookies.make_cookies(response, response.request)
            logging.info("QR login succeeded")
            return True,data['url'],0 #成功与否,URL,状态码
        else:
            # 将返回的状态码转换为以前的
            logging.debug("Login server msg: "+data['message'])
            return False,None,{
                0:0,
                86038:-2,
                86090:-5,
                86101:-4
                }[status]

def make_cookiejar_from_url(url):#URL来自 check_scan() 成功后的传参
    tmpjar = cookiejar.MozillaCookieJar()
    data = url.split('?')[-1].split('&')[:-1]
    for domain in ['.bilibili.com','.bigfun.cn','.bigfunapp.cn','.biligame.com']:
        for item in data:
            i = item.split('=',1)
            tmpjar.set_cookie(cookiejar.Cookie(
                0,i[0],i[1],
                None,False,
                domain,True,domain.startswith('.'),
                '/',False,
                False,int(time.time())+(6*30*24*60*60),
                False,
                None,
                None,
                {}
                ))
    return tmpjar

def copy_cookies(cj,from_domain,to_domain):
    cookie_dict = {}
    for cookie in cj:
        if cookie.domain == from_domain:
            cookie_dict[cookie.name] = cookie.value
    for name,value in cookie_dict.items():
        cj.set_cookie(cookiejar.Cookie(
            0,name,value,
            None,False,
            to_domain,True,to_domain.startswith('.'),
            '/',False,
            False,int(time.time())+(6*30*24*60*60),
            False,
            None,
            None,
            {}
            ))

def check_login():
    try:
        get_login_info()
    except BiliError:#操作得当不会出现BiliError以外的错误(网络问题除外
        return False
    else:
        return True

def exit_login():
    assert requester.cookies, 'CookiesJar not Loaded'
    csrf = get_csrf(requester.cookies)
    if csrf:
        data = requester.post_data_str('https://passport.bilibili.com/login/exit/v2',{'biliCSRF':csrf})
        if '请先登录' in data:
            raise BiliError('NaN','Haven\'t Logined Yet.')
        else:
            data = json.loads(data)
            error_raiser(data['code'],data.get('message'))
            _del_reftoken()
            logging.info("Logout succeeded")
    else:
        raise BiliError('NaN','Haven\'t Logined Yet.')

def get_login_info(): #Cookies is Required.
    '''
    获取当前登录的用户的信息, 注意与user.get_info()的区分
    '''
    api = 'https://api.bilibili.com/x/web-interface/nav'
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
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

def check_if_refresh_required():
    # 需要登录
    api = 'https://passport.bilibili.com/x/passport-login/web/cookie/info'
    if not requester.cookies:
        raise RuntimeError('CookiesJar not Loaded.')
    csrf = get_csrf(requester.cookies)
    if csrf:
        data = json.loads(requester.get_content_str(
            api + '?csrf=%s'%csrf
        ))
        error_raiser(data['code'], data['message'])
        data = data['data']
        if data['refresh']:
            logging.info("Cookie Refreshment required")
        else:
            logging.info("No need to Refresh Cookie")
        return data['refresh']#, data['timestamp']
    else:
        raise BiliError('NaN','Haven\'t Logined Yet.')

_co_key = RSA.importKey('''\
-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDLgd2OAkcGVtoE3ThUREbio0Eg
Uc/prcajMKXvkCKFCWhJYJcLkcM2DKKcSeFpD/j6Boy538YXnR6VhcuUJOhH2x71
nzPjfdTcqMz7djHum0qSZA0AyCBDABUqCrfNgCiJ00Ra7GmRj+YCK1NJEuewlb40
JNrRuoEUXpabUzGB8QIDAQAB
-----END PUBLIC KEY-----''')

def _get_correspondpath(ts):
    cipher = PKCS1_OAEP.new(_co_key, SHA256)
    encrypted = cipher.encrypt(f'refresh_{ts}'.encode())
    return binascii.b2a_hex(encrypted).decode()
    
def get_refresh_csrf():
    api = "https://www.bilibili.com/correspond/1/"
    cp = _get_correspondpath(time.time()*1000)
    api += cp
    webpage = requester.get_content_str(api)
    csrf = etree.HTML(webpage, etree.HTMLParser()).xpath(
        "//div[id='1-name']/text()"
    )
    _save_reftoken(csrf)
    return csrf

def confirm_refresh_cookies(refresh_token_old, csrf):
    api = 'https://passport.bilibili.com/x/passport-login/web/confirm/refresh'
    data = json.loads(requester.post_data_str(
        api,
        {
            'csrf': csrf,
            'refresh_token': refresh_token_old
        }
    ))
    error_raiser(data['code'], data['message'])
    logging.info("Cookie Refreshment confirmed")

def refresh_cookies(cj=None):
    logging.info("Attempting to refresh cookies")
    # 准备工作
    assert cj or requester.cookies, 'No cookiejar available'
    refresh_token = _get_reftoken()
    assert refresh_token, 'No Refresh Token found'
    csrf = get_csrf(requester.cookies)
    assert csrf, 'No CSRF found'
    refresh_csrf = get_refresh_csrf()
    assert refresh_csrf, 'Refresh CSRF generating failure'

    api = 'https://passport.bilibili.com/x/passport-login/web/cookie/refresh'
    with requester.post(
        api,
        {
            'csrf': csrf,
            'refresh_csrf': refresh_csrf,
            'source': 'main_web',
            'refresh_token': refresh_token,
        }
        ) as response:
        data = requester.read_and_decode_data(response).decode('utf-8','ignore')
        data = json.loads(data)
        error_raiser(data['code'],data['message'])
        data = data['data']
        old_reftoken = _get_reftoken()
        _save_reftoken(data['refresh_token'])
        if cj:
            pass
        else:
            cj = requester.cookies
        cj.make_cookies(response, response.request)

    csrf = get_csrf(cj)
    assert csrf, 'CSRF missed while processing'
    confirm_refresh_cookies(old_reftoken, csrf)
    logging.info("Cookies refreshed")

    return cj
        


