from .error import error_raiser,BiliError
from . import requester
import json
from http import cookiejar
import copy
import time

__all__ = ['get_csrf','dict_from_cookiejar','get_login_info','get_login_url','check_scan','check_login','make_cookiejar','exit_login']

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

def get_login_url():
    api = 'https://passport.bilibili.com/qrcode/getLoginUrl'
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'])
    data = data['data']
    loginurl = data['url']
    oauthkey = data['oauthKey']
    return loginurl,oauthkey

def check_scan(oauthkey):
    headers = copy.deepcopy(requester.fake_headers_post)
    headers['Host'] = 'passport.bilibili.com'
    headers['Referer'] = "https://passport.bilibili.com/login"
    data = json.loads(requester.post_data_str('https://passport.bilibili.com/qrcode/getLoginInfo',{'oauthKey':oauthkey},headers))
    #-1：密钥错误 -2：密钥超时 -4：未扫描 -5：未确认
    #error_raiser(data['code'],data['message'])
    status = data['status']
    if status:
        return True,data['data']['url'],0 #成功与否,URL,状态码
    else:
        return False,None,data['data']

def make_cookiejar(url):#URL来自 check_scan() 成功后的传参
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
            0,i[0],i[1],
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
    if not requester.cookies:
        raise RuntimeError('CookiesJar not Loaded.')
    csrf = get_csrf(requester.cookies)
    if csrf:
        data = requester.post_data_str('https://passport.bilibili.com/login/exit/v2',{'biliCSRF':csrf})
        if '请先登录' in data:
            raise BiliError('NaN','Haven\'t Logined Yet.')
        else:
            data = json.loads(data)
            return data
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
