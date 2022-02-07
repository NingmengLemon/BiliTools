from .error import error_raiser,BiliError
from . import requester
from . import bilicodes
import json
import hashlib
from urllib import parse
import logging
from bs4 import BeautifulSoup

__all__ = ['get_recommend','get_stream_dash',
           'get_tags','get_detail','search','bvid_to_avid_online',
           'bvid_to_avid_offline','avid_to_bvid_offline',
           'bvid_to_cid_online','avid_to_cid_online',
           'get_danmaku_xmlstr','get_online_nop',
           'get_shortlink','get_pbp','get_archive_list']

def get_recommend(avid=None,bvid=None):
    '''
    Choose one parameter between avid and bvid.
    普通视频下的相关视频
    '''
    if avid != None:
        api = 'https://api.bilibili.com/x/web-interface/archive/related?aid=%s'%avid
    elif bvid != None:
        api = 'https://api.bilibili.com/x/web-interface/archive/related?bvid='+bvid
    else:
        raise RuntimeError('You must choose one parameter between avid and bvid.')
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    data = data['data']
    res = []
    for data_ in data:
        res.append(_video_detail_handler(data_,False))
    return res

def get_stream_dash(cid,avid=None,bvid=None,dolby=False,hdr=False,_4k=False):
    '''Choose one parameter between avid and bvid'''
    fnval = 16
    if dolby:
        fnval = fnval|256
    if hdr:
        fnval = fnval|64
    if _4k:
        fnval = fnval|128
        
    if avid != None:
        api = 'https://api.bilibili.com/x/player/playurl?avid=%s&cid=%s&fnval=%s&fourk=1'%(avid,cid,fnval)
    elif bvid != None:
        api = 'https://api.bilibili.com/x/player/playurl?bvid=%s&cid=%s&fnval=%s&fourk=1'%(bvid,cid,fnval)
    else:
        raise RuntimeError('You must choose one parameter between avid and bvid.')
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    data = data['data']['dash']
    audio = []
    for au in data['audio']:
        audio.append({
            'quality':au['id'],#对照表 .bilicodes.stream_dash_audio_quality
            'url':au['baseUrl'],
            'encoding':au['codecs'],
            })
    video = []
    for vi in data['video']:
        video.append({
            'quality':vi['id'],#对照表 .bilicodes.stream_dash_video_quality
            'url':vi['baseUrl'],
            'encoding':vi['codecs'],
            'width':vi['width'],
            'height':vi['height'],
            'frame_rate':vi['frameRate'],#帧率
            
            })
    stream = {
        'audio':audio,
        'video':video
        }
    return stream

def get_tags(avid=None,bvid=None):
    '''Choose one parameter between avid and bvid'''
    if avid != None:
        api = 'https://api.bilibili.com/x/tag/archive/tags?aid=%s'%avid
    elif bvid != None:
        api = 'https://api.bilibili.com/x/tag/archive/tags?bvid='+bvid
    else:
        raise RuntimeError('You must choose one between avid and bvid.')
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    data = data['data']
    tags = []
    for tag in data:
        tags.append(tag['tag_name'])
    return tags

def get_detail(avid=None,bvid=None):
    '''Choose one parameter between avid and bvid'''
    if avid != None:
        api = 'https://api.bilibili.com/x/web-interface/view?aid=%s'%avid
    elif bvid != None:
        api = 'https://api.bilibili.com/x/web-interface/view?bvid='+bvid
    else:
        raise RuntimeError('You must choose one between avid and bvid.')
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    data = data['data']
    return _video_detail_handler(data,True)

def _video_detail_handler(data,detailmode=True):
    res = {
        'bvid':data['bvid'],
        'avid':data['aid'],
        'zone':data['tname'],
        'zone_id':int(data['tid']),
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
            parts.append({
                'cid':i['cid'],
                'title':i['part'],
                'length':i['duration'],#Second
                          })
        res['parts'] = parts
        res['warning_info'] = data['stat']['argue_msg']
        res['is_interact_video'] = bool(data['rights']['is_stein_gate'])
    return res

def search(*keywords,page=1,order='totalrank',zone=0,duration=0):
    '''order = totalrank 综合排序/click 最多点击/pubdate 最新发布/dm 最多弹幕/stow 最多收藏/scores 最多评论
    zone = 0/tid
    duration = 0(All)/1(0-10)/2(10-30)/3(30-60)/4(60+)
    '''
    api = 'https://api.bilibili.com/x/web-interface/search/type?'\
        'search_type=video&keyword={}&tids={}&duration={}&page={}&order={}'.format(
            '+'.join([parse.quote(keyword) for keyword in keywords]),zone,duration,page,order)
    data = json.loads(requester.get_content_str(api))
    error_raiser(data['code'],data['message'])
    data = data['data']
    tmp = []
    if 'result' in data:
        for res in data['result']:
            tmp.append({
                'avid':res['aid'],
                'bvid':res['bvid'],
                'uploader':{
                    'name':res['author'],
                    'uid':res['mid']
                    },
                'title':BeautifulSoup(res['title'],"html.parser").get_text(),
                'description':res['description'],
                'zone_id':int(res['typeid']),
                'zone':res['typename'],
                'url':res['arcurl'],
                'cover':'https:'+res['pic'],
                'stat':{
                    'view':res['play'],
                    'danmaku':res['video_review'],
                    'collect':res['favorites'],
                    'comment':res['review']
                    },
                'tags':res['tag'].split(','),
                'date_publish':res['pubdate'], #timestamp
                'duration':res['duration'], #str
                'is_union_video':bool(res['is_union_video']), #联合投稿
                'hit_type':res['hit_columns'] #匹配类型
                })
    else:
        pass
    result = {
        'seid':data['seid'], #search id
        'page':data['page'],
        'pagesize':data['pagesize'],
        'result_count':data['numResults'],#max=1000
        'total_pages':data['numPages'],#max=50
        'time_cost':data['cost_time']['total'],#搜索花费时间
        'result':tmp
        }
    return result

def bvid_to_avid_online(bvid):
    data = requester.get_content_str('https://api.bilibili.com/x/web-interface/archive/stat?bvid='+bvid)
    data = json.loads(data)['data']
    return data['aid']

def bvid_to_avid_offline(bvid):
    _table = 'fZodR9XQDSUm21yCkr6zBqiveYah8bt4xsWpHnJE7jL5VG3guMTKNPAwcF'
    _s = [11,10,3,8,4,6]
    _tr = {}
    _xor = 177451812
    _add = 8728348608
    for _ in range(58):
        _tr[_table[_]] = _
        
    r = 0
    for i in range(6):
        r += _tr[bvid[_s[i]]]*58**i
    return (r-_add)^_xor

def avid_to_bvid_offline(avid):
    _table = 'fZodR9XQDSUm21yCkr6zBqiveYah8bt4xsWpHnJE7jL5VG3guMTKNPAwcF'
    _xor = 177451812
    _add = 8728348608
    _s = [11,10,3,8,4,6]
    
    avid = (avid^_xor)+_add
    r = list('BV1  4 1 7  ')
    for i in range(6):
        r[_s[i]] = _table[avid//58**i%58]
    return ''.join(r)

def bvid_to_cid_online(bvid):
    data = requester.get_content_str(f'https://api.bilibili.com/x/player/pagelist?bvid={bvid}&jsonp=jsonp')
    data = json.loads(data)['data']
    res = []
    for i in data:
        res.append(i['cid'])
    return res

def avid_to_cid_online(avid):
    data = requester.get_content_str(f'https://api.bilibili.com/x/player/pagelist?aid={avid}&jsonp=jsonp')
    data = json.loads(data)['data']
    res = []
    for i in data:
        res.append(i['cid'])
    return res

def get_danmaku_xmlstr(cid):
    data = requester.get_content_str(f'https://comment.bilibili.com/{cid}.xml')
    return data

def get_online_nop(cid,avid=None,bvid=None):
    '''Choose one parameter between avid and bvid'''
    if avid != None:
        api = 'http://api.bilibili.com/x/player/online/total?cid=%s&aid=%s'%(cid,avid)
    elif bvid != None:
        api = 'http://api.bilibili.com/x/player/online/total?cid=%s&bvid=%s'%(cid,bvid)
    else:
        raise RuntimeError('You must choose one between avid and bvid.')
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    data = data['data']
    return {'total':data['total'],
            'web':data['count']}

def get_shortlink(avid):
    data = requester.post_data_str('https://api.bilibili.com/x/share/click',data={
	'build':9300,
	'buvid':hashlib.md5(bytes(random.randint(1000,9999))).hexdigest(),
	'oid':int(avid),
	'platform':'web',
	'share_channel':'COPY',
	'share_id':"main.ugc-video-detail.0.0.pv",
	'share_mode':1
        })
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    data = data['data']
    url = re.findall(r'(https?\://b23\.tv/[0-9A-Za-z]+)',data['content'])[0]
    return url

def get_pbp(cid):
    api = 'https://bvc.bilivideo.com/pbp/data?cid='+str(cid)
    data = requester.get_content_str(api)
    data = json.loads(data)
    if not data['events']:
        error_raiser('NaN','PBP获取失败')
    res = {
        'step_sec':data['step_sec'],
        'data':data['events']['default'],
        'debug':json.loads(data['debug'])
        }
    return res

def get_archive_list(uid,sid,reverse=False,page=1,page_size=30):
    #获取合集
    #uid是用户id; sid不知道是什么id, 应该是合集id
    api = 'https://api.bilibili.com/x/polymer/space/seasons_archives_list?'\
          'mid={}&season_id={}&sort_reverse={}&page_num={}&page_size={}'.format(uid,sid,str(reverse).lower(),page,page_size)
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    data = data['data']
    res = {
        'cover':data['meta']['cover'],
        'description':data['meta']['description'],
        'uid':data['meta']['mid'],
        'title':data['meta']['name'],
        'pub_time':data['meta']['ptime'], #timestamp
        'sid':data['meta']['season_id'],
        'total':data['meta']['total'],
        'archives':[{
            'avid':i['aid'],
            'bvid':i['bvid'],
            'duration':i['duration'],
            'is_interact_video':i['interactive_video'],
            'cover':i['pic'],
            'title':i['title'],
            'stat':i['stat'], #是个字典, 里面只有view一个键
            } for i in data['archives']]
        }
    return res
