from .error import error_raiser,BiliError
from . import requester
from . import bilicodes
import json
import logging
import re
from bs4 import BeautifulSoup

__all__ = ['filter','get_xmlstr','use_proxy','get_filter_rule']

use_proxy = True

def _parse_d(dp):
    appeartime,mode,size,color,timestamp,pool,user,dmid,level = dp.split(',')
    color = ('#'+hex(int(color))[2:]).upper()
    #mode:1-3:普通,4:底,5:顶,6:逆向,7:高级,8:代码,9:BAS
    res = {
        'appear_time':float(appeartime),
        'mode':int(mode),
        'size':int(size),
        'color':color,
        'timestamp':int(timestamp),
        'pool':int(pool),
        'userhash':user,
        'dmid':int(dmid),
        'level':int(level)
        }
    return res

def filter(xmlstr,keyword=[],regex=[],user=[],filter_level=0):
    #参数名称与.user.get_danmaku_filter返回值保持一致
    bs = BeautifulSoup(xmlstr,'lxml')
    counter = 0
    i = 0
    for d in bs.find_all('d'):
        content = d.get_text()
        dp = _parse_d(d.get('p'))
        if dp['mode'] == '7':
            content = json.loads(content)[4]
        userhash = dp['userhash']
        flag = False
        if filter_level > dp['level']:
            flag = True
        if not flag:
            for kw in keyword:
                if kw.lower() in content.lower():
                    flag = True
                    break
        if not flag:
            for uhash in user:
                if userhash == uhash:
                    flag = True
                    break
        if not flag:
            for reg in regex:
                if re.search(reg,content):
                    flag = True
                    break
        if flag:
            d.extract()
            counter += 1
        i += 1
    logging.info(f'{counter} of {i} danmaku are filtered.')
    return str(bs).replace('<html><body>','').replace('</body></html>','')

def get_xmlstr(cid):
    data = requester.get_content_str(f'https://api.bilibili.com/x/v1/dm/list.so?oid={cid}',use_proxy=use_proxy)
    return data

def get_filter_rule():
    api = 'https://api.bilibili.com/x/dm/filter/user?jsonp=jsonp'
    data = json.loads(requester.get_content_str(api,use_proxy=use_proxy))
    error_raiser(data['code'],data['message'])
    data = data['data']
    #type: 0关键字, 1正则, 2用户
    keyword = []
    regex = []
    user = []
    for r in data['rule']:
        f = r['filter']
        if r['type'] == 0:
            keyword += [f]
        elif r['type'] == 1:
            regex += [f]
        elif r['type'] == 2:
            user += [f]
    res = {
        'keyword':keyword,
        'regex':regex,
        'user':user
        }
    return res