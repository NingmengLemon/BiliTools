from .error import error_raiser,BiliError
from . import requester
from . import bilicodes
import json
import hashlib
from urllib import parse
from bs4 import BeautifulSoup
import logging
import re
import math
import random

__all__ = ['get_recommend',
           'get_tags','get_detail','search','bvid_to_avid_online',
           'bvid_to_avid_offline','avid_to_bvid_offline',
           'bvid_to_cid_online','avid_to_cid_online',
           'get_online_nop',
           'get_shortlink','get_pbp','get_archive_list','get_series_list',
           'get_interact_graph_id','get_interact_edge_info',
           'like','is_liked','coin','is_coined','collect','is_collected',
           'get_videoshot']

def get_recommend(avid:int=None,bvid:str=None):
    '''
    Choose one parameter between avid and bvid.
    普通视频下的相关视频
    '''
    if avid != None:
        api = f'https://api.bilibili.com/x/web-interface/archive/related?aid={avid}'
    elif bvid != None:
        api = f'https://api.bilibili.com/x/web-interface/archive/related?bvid='+bvid
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

def get_tags(avid:int=None,bvid:str=None):
    '''Choose one parameter between avid and bvid'''
    if avid != None:
        api = f'https://api.bilibili.com/x/tag/archive/tags?aid={avid}'
    elif bvid != None:
        api = f'https://api.bilibili.com/x/tag/archive/tags?bvid='+bvid
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
        api = f'https://api.bilibili.com/x/web-interface/view?aid={avid}'
    elif bvid != None:
        api = f'https://api.bilibili.com/x/web-interface/view?bvid='+bvid
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
        'is_original':(data['copyright']==1),
        'part_number':data['videos'],
        'picture':data['pic'],
        'title':data['title'],
        'date_publish':data['pubdate'],
        'date_upload':data['ctime'],
        'description':data['desc'],
        'state':data['state'], # see .bilicodes.video_states
        'length':data['duration'], # 总时长, second
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
        'redirect_url':None
        }
    if 'redirect_url' in data:
        res['redirect_url'] = data['redirect_url']
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
        res['is_cooperation'] = data['rights']['is_cooperation']
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
                #'zone_id':int(res['typeid']),
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
            if res['typeid']:
                tmp[-1]['zone_id'] = int(res['typeid'])
            else:
                tmp[-1]['zone_id'] = -1
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
    data = get_detail(bvid=bvid)
    return data['avid']

def avid_to_bvid_online(avid):
    data = get_detail(avid=avid)
    return data['bvid']

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
            } for i in data['archives']],
        'page':data['page']['page_num'],
        'page_size':data['page']['page_size'],
        'total_page':math.ceil(data['page']['total']/data['page']['page_size'])
        }
    return res

def get_series_list(uid,sid,reverse=False,page=1,page_size=30):
    #获取系列
    #sid是系列id
    api = 'https://api.bilibili.com/x/series/archives?'\
          'mid={}&series_id={}&only_normal=true&sort={}&pn={}&ps={}'.format(uid,sid,
                                                                            {False:'desc',True:'asc'}[reverse],
                                                                            page,page_size)
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    data = data['data']
    res = {
        'archives':[{
            'avid':i['aid'],
            'bvid':i['bvid'],
            'duration':i['duration'],
            'is_interact_video':i['interactive_video'],
            'cover':i['pic'],
            'title':i['title'],
            'stat':i['stat'], #是个字典, 里面只有view一个键
            } for i in data['archives']],
        'page':data['page']['num'],
        'page_size':data['page']['size'],
        'total_page':math.ceil(data['page']['total']/data['page']['size']),
        'total':data['page']['total']
        }
    return res

def get_series_detail(uid,sid):
    pass

def like(csrf,avid=None,bvid=None,opt=1): # 点赞
    '''
    opt为1时点赞，为2时取消点赞
    需要手动传入cookies中的csrf
    '''
    api = 'https://api.bilibili.com/x/web-interface/archive/like'
    data = {}
    if avid != None:
        data['aid'] = int(avid)
    elif bvid != None:
        data['bvid'] = bvid
    else:
        raise RuntimeError('You must choose one parameter between avid and bvid.')
    data['like'] = opt
    data['csrf'] = csrf
    data = json.loads(requester.post_data_str(api,data=data))
    error_raiser(data['code'],data['message'])

def is_liked(avid=None,bvid=None): # 判断是否赞过
    '''
    需要登录
    '''
    api = 'https://api.bilibili.com/x/web-interface/archive/has/like'
    if avid != None:
        api += f'?aid={avid}'
    elif bvid != None:
        api += f'?bvid={bvid}'
    else:
        raise RuntimeError('You must choose one parameter between avid and bvid.')
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    return bool(data['data'])

def coin(csrf,avid=None,bvid=None,num=1,like=False): # 投币
    '''
    num为投币个数，上限为2
    like为是否附加点赞
    需要手动传入cookies中的csrf
    '''
    api = 'https://api.bilibili.com/x/web-interface/coin/add'
    data = {}
    if avid != None:
        data['aid'] = int(avid)
    elif bvid != None:
        data['bvid'] = bvid
    else:
        raise RuntimeError('You must choose one parameter between avid and bvid.')
    data['multiply'] = num
    data['select_like'] = int(like)
    data['csrf'] = csrf
    data = json.loads(requester.post_data_str(api,data=data))
    error_raiser(data['code'],data['message'])
    return {'like_result':data['data']['like']}

def is_coined(avid=None,bvid=None): # 判断是否投过币
    '''
    需要登录
    '''
    api = 'https://api.bilibili.com/x/web-interface/archive/coins'
    if avid != None:
        api += f'?aid={avid}'
    elif bvid != None:
        api += f'?bvid={bvid}'
    else:
        raise RuntimeError('You must choose one parameter between avid and bvid.')
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    return data['data']['multiply'] # 已投的币的数目

def triple(csrf,avid=None,bvid=None): # 三连
    '''
    需要手动传入cookies中的csrf
    '''
    api = 'https://api.bilibili.com/x/web-interface/archive/like/triple'
    data = {}
    if avid != None:
        data['aid'] = int(avid)
    elif bvid != None:
        data['bvid'] = bvid
    else:
        raise RuntimeError('You must choose one parameter between avid and bvid.')
    data['csrf'] = csrf
    data = json.loads(requester.post_data_str(api,data=data))
    error_raiser(data['code'],data['message'])
    data = data['data']
    return {
        'like_result':data['like'],
        'coin_result':data['coin'],
        'collect_result':data['fav'],
        'coined_num':data['multiply']
        }

def collect(csrf,avid,add_mlids=[],del_mlids=[]):
    api = 'https://api.bilibili.com/medialist/gateway/coll/resource/deal'
    data = {}
    data['rid'] = int(avid)
    data['csrf'] = csrf
    data['type'] = 2
    if add_mlids:
        data['add_media_ids'] = ','.join([str(i) for i in add_mlids])
    if del_mlids:
        data['del_media_ids'] = ','.join([str(i) for i in del_mlids])
    data = json.loads(requester.post_data_str(api,data=data))
    error_raiser(data['code'],data['message'])

def is_collected(avid=None,bvid=None):
    api = 'https://api.bilibili.com/x/v2/fav/video/favoured'
    if avid != None:
        api += f'?aid={avid}'
    elif bvid != None:
        api += f'?aid={bvid}'
    else:
        raise RuntimeError('You must choose one parameter between avid and bvid.')
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    return data['data']['favoured']

def get_interact_graph_id(cid,avid=None,bvid=None):
    '''
    获取互动视频的剧情图ID
    avid / bvid 任选一个
    '''
    if avid != None:
        api = f'https://api.bilibili.com/x/player/v2?aid={avid}&cid={cid}'
    elif bvid != None:
        api = f'https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}'
    else:
        raise RuntimeError('You must choose one parameter between avid and bvid.')
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    data = data['data']
    if 'interaction' in data:
        return data['interaction']['graph_version']
    else:
        raise RuntimeError(f'Not a interact video: a{avid}b{bvid}c{cid}')

def get_interact_edge_info(graph_id,avid=None,bvid=None,edge_id=0):
    '''
    获取互动视频的某个模块的详细信息
    avid / bvid 任选一个
    graph_id 为剧情图ID
    edge_id 为模块编号, 填 0 时为初始
    '''
    if avid != None:
        api = f'https://api.bilibili.com/x/stein/edgeinfo_v2?aid={avid}'
    elif bvid != None:
        api = f'https://api.bilibili.com/x/stein/edgeinfo_v2?bvid={bvid}'
    else:
        raise RuntimeError('You must choose one parameter between avid and bvid.')
    api += f'&graph_version={graph_id}&edge_id={edge_id}'
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    data = d = data['data']
    res = {
        'title':d['title'],
        'edge_id':d['edge_id'],
        'story_list':[], # 进度回溯列表
        'vars':[], # 变量列表
        'preload_parts':[], # 预加载分P, 都是问题选项所对应的
        'is_end_edge':bool(d['is_leaf']), # 是否为结束模块
        }
    for p in d['preload']['video']:
        res['preload_parts'].append({
            'avid':p['aid'],
            'cid':p['cid']
            })
    if 'hidden_vars' in d:
        for v in d['hidden_vars']:
            res['vars'].append({
                'value':v['value'],
                'id_v1':v['id'],
                'id_v2':v['id_v2'], # 运算语句中更常用
                'is_random':(v['type']==2), # 是否是随机数
                'display':bool(v['is_show']), # 是否展示
                'name':v['name'],
                })
    for s in d['story_list']:
        res['story_list'].append({
            'edge_id':s['edge_id'],
            'title':s['title'],
            'cid':s['cid'],
            'cover':s['cover'],
            'prg_sn':s['cursor'], # 从0始计的进度序号
            'is_current':('is_current' in s)
            })
    if 'questions' in d['edges']:
        q = d['edges']['questions'][0]
        res['question'] = {
            'show_mode':q['type'], # 选项显示模式
            # 0:不显示; 1:底部; 2:坐标定点; 3:?; 127:?
            'time_limit':q['duration'], # 回答限时(-1时不限时), ms
            'pause':bool(q['pause_video']), # 是否暂停播放(当为否时会直接进入默认的选项)
            #'fade_in_time':q['fade_in_time'], # 选项淡入淡出时间, ms
            #'fade_out_time':q['fade_out_time'],
            'choices':[]
            }
        for c in q['choices']:
            vopt = c['native_action'].split(';') if c['native_action'] else []
            res['question']['choices'].append({
                'jump_edge_id':c['id'], # 点击后跳转到的模块ID
                'var_operations':vopt, # 变量运算语句(们)
                'appear_condition':c['condition'], # 选项出现的条件
                'jump_cid':c['cid'],
                'text':c['option'],
                'is_default':('is_default' in c),
                'is_hidden':('is_hidden' in c)
                })
    else:
        res['question'] = None # 为最后一个模块时
    return res
    
def add_to_toview(csrf,avid=None,bvid=None):
    '''
    添加视频到稍后再看
    需要手动传入cookies中的csrf
    '''
    api = 'https://api.bilibili.com/x/v2/history/toview/add'
    data = {}
    if avid != None:
        data['aid'] = int(avid)
    elif bvid != None:
        data['bvid'] = bvid
    else:
        raise RuntimeError('You must choose one parameter between avid and bvid.')
    data['csrf'] = csrf
    data = json.loads(requester.post_data_str(api,data=data))
    error_raiser(data['code'],data['message'])

def get_videoshot(avid=None,bvid=None,cid=None):
    '''
    获取视频快照
    avid 和 bvid 任选其一传入
    不指定 cid 时返回 P1 的内容
    '''
    if avid != None:
        api = f'https://api.bilibili.com/x/player/videoshot?aid={avid}&index=1'
    elif bvid != None:
        api = f'https://api.bilibili.com/x/player/videoshot?bvid={bvid}&index=1'
    else:
        raise RuntimeError('You must choose one parameter between avid and bvid.')
    if cid:
        api += f'&cid={cid}'
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    data = d = data['data']
    res = {
        "bin_ver":'https:'+data["pvdata"],
        "img_ver":['https:'+i for i in data["image"]],
        "img_x_length":data["img_x_len"],
        "img_y_length":data["img_y_len"],
        "img_w":data["img_x_size"],
        "img_h":data["img_y_size"],
        "index":data["index"]
    }
    return res
    
