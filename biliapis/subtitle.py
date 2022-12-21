from .error import error_raiser,BiliError
from . import requester
from . import bilicodes
import json
import math

__all__ = ['get_bcc','bcc_to_srt']

def get_bcc(cid,avid=None,bvid=None,allow_ai=False):
    '''Choose one parameter between avid and bvid'''
    if avid != None:
        api = 'https://api.bilibili.com/x/player/v2?cid=%s&aid=%s'%(cid,avid)
    elif bvid != None:
        api = 'https://api.bilibili.com/x/player/v2?cid=%s&bvid=%s'%(cid,bvid)
    else:
        raise RuntimeError('You must choose one parameter between avid and bvid.')
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    data = data['data']['subtitle']['subtitles']
    res = []
    for item in data:
        if '/ai_subtitle/' in item['subtitle_url'] and not allow_ai:
            continue
        res.append({
            'id':item['id'],
            'lang':item['lan_doc'],#语言
            'lang_abb':item['lan'],#语言简写
            #'author_uid':item['author_mid'],
            'url':'https:'+item['subtitle_url']#将请求此url获得的json数据交给下面那个函数即可
            })
    return res

def bcc_to_srt(jsondata):
     srt_file = ''
     bccdata = jsondata['body']
     i = 1
     for data in bccdata:
         start = data['from']  # 获取开始时间
         stop = data['to']  # 获取结束时间
         content = data['content']  # 获取字幕内容
         srt_file += '{}\n'.format(i)  # 加入序号(没有下标)
         hour = math.floor(start) // 3600
         minute = (math.floor(start) - hour * 3600) // 60
         sec = math.floor(start) - hour * 3600 - minute * 60
         minisec = int(math.modf(start)[0] * 100)  # 处理开始时间
         srt_file += str(hour).zfill(2) + ':' + str(minute).zfill(2) + ':' + str(sec).zfill(2) + ',' + str(minisec).zfill(2)  # 将数字填充0并按照格式写入
         srt_file += ' --> '
         hour = math.floor(stop) // 3600
         minute = (math.floor(stop) - hour * 3600) // 60
         sec = math.floor(stop) - hour * 3600 - minute * 60
         minisec = abs(int(math.modf(stop)[0] * 100 - 1))  # 此处减1是为了防止两个字幕同时出现
         srt_file += str(hour).zfill(2) + ':' + str(minute).zfill(2) + ':' + str(sec).zfill(2) + ',' + str(minisec).zfill(2)
         srt_file += '\n' + content + '\n\n'  # 加入字幕文字
         i += 1
     return srt_file
