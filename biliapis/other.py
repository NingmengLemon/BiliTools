from .error import error_raiser,BiliError
from . import requester
from . import bilicodes
import json
import os
import time
from bs4 import BeautifulSoup

__all__ = ['get_blackroom','get_emotions','download_emotions_demo']

def get_blackroom(page=1,source_filter=None,reason_filter=0):
    '''
    source_filter = None(All) / 0(SystemBanned) / 1(JudgementBanned)
    reason_filter = 0(All)/...(Look in bilicodes.ban_reason)
    '''
    if source_filter == None:
        source_filter = ''
    api = 'https://api.bilibili.com/x/credit/blocked/list?btype=%s&otype=%s&pn=%s'%(source_filter,reason_filter,page)
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    data = data['data']
    res = []
    for item in data:
        res.append({
            'id':item['id'],
            'user':{
                'name':item['uname'],
                'face':item['face'],
                'uid':item['uid']
                },
            'origin':{
                'title':item['originTitle'],
                'url':item['originUrl'],
                'type_id':item['originType'],
                'type':item['originTypeName']
                },
            'punish':{
                'content':BeautifulSoup(item['originContentModify'],"html.parser").get_text('\n'),
                'content_origin':item['originContentModify'],
                'title':item['punishTitle'],
                'time':item['punishTime'],#TimeStamp
                'type':item['punishTypeName'],
                'days':item['blockedDays'],#forever is 0
                'is_forever':bool(item['blockedForever']),
                },
            'reason':{
                'type_id':item['reasonType'],
                'type':item['reasonTypeName']
                },
            })
    return res

def get_emotions(business='reply'):
    '''business = reply / dynamic'''
    data = requester.get_content_str(f'https://api.bilibili.com/x/emote/user/panel/web?business={business}')
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
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

def download_emotions_demo(path='./emotions/',pause_time=1,show_process=False):
    path = os.path.abspath(path)+'\\'
    def print_(text,end='\n'):
        if show_process:
            print(text,end=end)
        else:
            pass
    if not os.path.exists(path):
        os.mkdir(path)
    emotions = get_emotions()
    for pkg in emotions:
        path_ = path+pkg['text']+'\\'
        print_('表情包 %s id%s'%(pkg['text'],pkg['id']))
        if not os.path.exists(path_):
            os.mkdir(path_)
        for i in pkg['emote']:
            if _is_url(i['url']):
                start_new_thread(download_common,(i['url'],path_+i['text']+'.png'))
            else:
                with open(path_+'data.txt','a+',encoding='utf-8') as f:
                    f.write('%s\t%s\n'%(i['id'],i['text']))
            print_('表情 %s id%s'%(i['text'],i['id']))
            time.sleep(pause_time)
