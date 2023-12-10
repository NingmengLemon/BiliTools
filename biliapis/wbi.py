import logging
import json
from functools import reduce
import time
from hashlib import md5
import urllib.parse
from . import bilicodes
from .error import error_raiser,BiliError
from . import requester

img_key = None
sub_key = None
last_fetch = 0

# from bilibili-API-collect, modified

mixinKeyEncTab = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52
]

def getMixinKey(orig: str):
    '对 imgKey 和 subKey 进行字符顺序打乱编码'
    return reduce(lambda s, i: s + orig[i], mixinKeyEncTab, '')[:32]

def encWbi(params: dict, img_key: str, sub_key: str) -> dict:
    '为请求参数进行 wbi 签名'
    mixin_key = getMixinKey(img_key + sub_key)
    curr_time = round(time.time())
    params['wts'] = curr_time                                   # 添加 wts 字段
    params = dict(sorted(params.items()))                       # 按照 key 重排参数
    # 过滤 value 中的 "!'()*" 字符
    params = {
        k : ''.join(filter(lambda chr: chr not in "!'()*", str(v)))
        for k, v 
        in params.items()
    }
    query = urllib.parse.urlencode(params)                      # 序列化参数
    wbi_sign = md5((query + mixin_key).encode()).hexdigest()    # 计算 w_rid
    params['w_rid'] = wbi_sign
    return params

def getWbiKeys():# -> tuple[str, str]:
    '获取最新的 img_key 和 sub_key'
    api = 'https://api.bilibili.com/x/web-interface/nav'
    json_content = json.loads(requester.get_content_str(api))
    img_url: str = json_content['data']['wbi_img']['img_url']
    sub_url: str = json_content['data']['wbi_img']['sub_url']
    img_key = img_url.rsplit('/', 1)[1].split('.')[0]
    sub_key = sub_url.rsplit('/', 1)[1].split('.')[0]
    logging.debug('WBI KEY has been refreshed')
    return img_key, sub_key

def init():
    global img_key
    global sub_key
    global last_fetch
    img_key, sub_key = getWbiKeys()
    last_fetch = time.time()
    logging.info('WBI KEY has been initialized')

def sign(params) -> str:
    global img_key
    global sub_key
    global last_fetch
    if (not img_key or not sub_key) or (time.time()-last_fetch) > 60*60*6:
        img_key, sub_key = getWbiKeys()
    signed_params = encWbi(
        params=params,
        img_key=img_key,
        sub_key=sub_key
    )
    query = urllib.parse.urlencode(signed_params)
    logging.debug('Signed new WBI params: '+query)
    return signed_params#,query
