from .error import error_raiser,BiliError
from . import requester
from . import bilicodes
import json

__all__ = ['get_stream','get_lyrics','get_tags','get_info','get_list']

def get_stream(auid,quality=3,platform='web',uid=0):
    '''quality = 0(128K)/1(192K)/2(320K)/3(FLAC)'''
    api = 'https://api.bilibili.com/audio/music-service-c/url?songid=%s&quality=%s&privilege=2&mid=%s&platform=%s'%(auid,quality,uid,platform)
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['msg'])
    data = data['data']
    res = {
        'auid':data['sid'],
        'quality':{-1:'192K试听',0:'128K',1:'192K',2:'320K',3:'FLAC'}[data['type']],
        'quality_id':data['type'],
        'size':data['size'],#(Byte)
        'url':data['cdns'][0],
        'urls_backup':data['cdns'][1:],
        'title':data['title'],
        'cover':data['cover']
        }
    return res

def get_info(auid):
    api = 'https://www.bilibili.com/audio/music-service-c/web/song/info?sid=%s'%auid
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['msg'])
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

def get_tags(auid):
    api = 'https://www.bilibili.com/audio/music-service-c/web/tag/song?sid=%s'%auid
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['msg'])
    data = data['data']
    tags = []
    for item in data:
        tags += [item['info']]
    return tags

def get_lyrics(auid):
    api = 'https://www.bilibili.com/audio/music-service-c/web/song/lyric?sid=%s'%auid
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['msg'])
    data = data['data']
    return data

def get_list(amid,page=1,page_size=100):
    api = 'https://www.bilibili.com/audio/music-service-c/web/song/of-menu?'\
          'sid={}&pn={}&ps={}'.format(amid,page,page_size)
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['msg'])
    data = data['data']
    if data:
        res = {
            'page':data['curPage'],
            'total_page':data['pageCount'],
            'page_size':data['pageSize'],
            'total_size':data['totalSize'],
            'data':[{
                'connect_video':{
                    'avid':i['aid'],
                    'bvid':i['bvid'],
                    'cid':i['cid']
                    },
                'title':i['title'],
                'description':i['intro'],
                'auid':i['id'],
                'length':i['duration'],
                'uploader':{
                    'uid':i['uid'],
                    'name':i['uname']
                    },
                'lyrics_url':i['lyric'],
                'cover':i['cover'],
                'publish_time':i['passtime'],
                'stat':{
                    'coin':i['coin_num'],
                    'comment':i['statistic']['comment'],
                    'play':i['statistic']['play'],
                    'share':i['statistic']['share']
                    },
                'author':i['author']
                } for i in data['data']]
            }
        return res
    else:
        return None
