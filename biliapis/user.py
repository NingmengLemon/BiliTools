from .error import error_raiser,BiliError
from . import requester
from . import bilicodes
from . import wbi
from urllib import parse
import json
from .video import _video_detail_handler
from .article import _article_stat_handler

__all__ = ['search','get_info','get_favlist','get_all_favlists',
           'get_liveroom','get_toview','get_article_list',
           'get_readlist_list']

def get_liveroom(uid):
    api = 'http://api.live.bilibili.com/room/v1/Room/getRoomInfoOld?'\
          'mid='+str(uid)
    data = json.loads(requester.get_content_str(api))
    error_raiser(data['code'],data['message'])
    data = data['data']
    res = {
        'has_room':bool(data['roomStatus']),
        'is_rounding':bool(data['roundStatus']),#是否正在轮播
        'is_living':bool(data['liveStatus']),
        'url':data['url'],
        'title':data['title'],
        'cover':data['cover'],
        'short_id':data['roomid']
        }
    return res

def search(*keywords,page=1,order='0',order_sort=0,user_type=0):
    '''order = 0(default) / fans / level
    order_sort = 0(high->low) / 1(low->high)
    user_type = 0(All) / 1(Uploader) / 2(CommonUser) / 3(CertifiedUser)
    '''
    api = 'https://api.bilibili.com/x/web-interface/search/type?search_type=bili_user&' \
        'keyword={}&page={}&order={}&order_sort={}'.format(
            '+'.join([parse.quote(keyword) for keyword in keywords]),page,order,order_sort)
    data = json.loads(requester.get_content_str(api))
    error_raiser(data['code'],data['message'])
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

def get_info(uid):
    api = 'https://api.bilibili.com/x/space/wbi/acc/info'
    params = {
        'mid':uid
        }
    api += '?'+parse.urlencode(wbi.sign(params))
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
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

def get_favlist(mlid,tid=0,order='mtime',page_size=20,page=1):
    '''
    mlid:       fid + uid[-2:]
    tid:        分区 ID
    order:      排序方式 {pubtime, view, mtime}
    page_size:  每页视频数 [1,20]
    page:       页数
    '''
    api = 'https://api.bilibili.com/x/v3/fav/resource/list?'\
          'media_id={}&tid={}&order={}&ps={}&pn={}&platform=pc'.format(mlid,tid,order,page_size,page)
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    data = data['data']
    if data:
        info = data['info']
        res = {
            'mlid':info['id'], #mlid = fid + uid后两位
            'fid':info['fid'], #原始id
            'uploader':{
                'uid':info['mid'],
                'name':info['upper']['name'],
                'face':info['upper']['face'],
                'is_followed':info['upper']['followed'],
                },
            'title':info['title'],
            'cover':info['cover'],
            'description':info['intro'],
            'is_collected':bool(info['fav_state']), # 是否收藏, 需要登录
            'is_liked':bool(info['like_state']),    # 是否点赞, 同上
            'content_count':info['media_count'],    # 内容物计数
            'content':[{
                'bvid':i['bvid'],
                'title':i['title'],
                'fav_time':i['fav_time'],
                'pub_time':i['pubtime'],
                'description':i['intro'],
                'duration':i['duration'],
                'uploader':{
                    'uid':i['upper']['mid'],
                    'name':i['upper']['name'],
                    'face':i['upper']['face']
                    },
                'stat':{
                    'collect':i['cnt_info']['collect'],
                    'view':i['cnt_info']['play'],
                    'danmaku':i['cnt_info']['danmaku']
                    }
                } for i in data['medias']]
            }
        return res
    else:
        error_raiser('NaN','收藏夹无效')

def get_all_favlists(uid,avid=None):
    '''
    获取指定用户的所有收藏夹的id,
    同时可指示指定视频是否存在于某个收藏夹中
    '''
    api = 'https://api.bilibili.com/x/v3/fav/folder/created/list-all'
    api += f'?up_mid={uid}'
    if avid:
        api += f'&rid={avid}'
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    data = data['data']
    if not data:
        error_raiser('NaN','收藏夹无效')
    res = {
        'count':data['count'], # 收藏夹计数
        'list':[]
        }
    for fav in data['list']:
        res['list'].append({
            'mlid':fav['id'], # 完整id, =fid+uid后两位
            'fid':fav['fid'], # 原始id
            'uid':fav['mid'], # 创建者uid
            'title':fav['title'],
            'fav_state':bool(fav['fav_state']), # 指定的avid是否在收藏夹里
            'count':fav['media_count'] # 内容计数
            })
    return res

def get_toview():
    api = 'https://api.bilibili.com/x/v2/history/toview'
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    data = data['data']
    res = {
        'count':data['count'], # 计数
        'list':[]
        }
    for v in data['list']:
        res['list'].append({
            'bvid':v['bvid'],
            'avid':v['aid'],
            'cid':v['cid'],
            'zone':v['tname'],
            'zone_id':int(v['tid']),
            'part_number':v['videos'],
            'picture':v['pic'],
            'title':v['title'],
            'date_publish':v['pubdate'], # timestamp, s
            'date_upload':v['ctime'], # timestamp, s
            'description':v['desc'],
            'state':v['state'], # see .bilicodes.video_states
            'length':v['duration'], # 总时长, second
            'uploader':{
                'uid':v['owner']['mid'],
                'name':v['owner']['name'],
                'face':v['owner']['face']
                },
            'stat':{
                'view':v['stat']['view'],
                'danmaku':v['stat']['danmaku'],
                'reply':v['stat']['reply'],
                'collect':v['stat']['favorite'],
                'coin':v['stat']['coin'],
                'share':v['stat']['share'],
                'like':v['stat']['like'],
                'rank_now':v['stat']['now_rank'],
                'rank_his':v['stat']['his_rank']
                },
            'add_time':v['add_at'], # timestamp, s
            'watch_prg':v['progress'] # 观看进度, s
            })
    return res

def get_article_list(uid:int,page:int=1,page_size:int=30,sort:str='publish_time'):
    '''
    page_size 的上限为 30

    sort = publish_time / view / fav
    '''
    api = 'https://api.bilibili.com/x/space/article'
    api += '?mid=%s&pn=%s&ps=%s&sort=%s'%(uid,page,page_size,sort)
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    data = data['data']
    articles = data['articles']

    res = {
        'page':data['pn'],
        'page_size':data['ps'],
        'count':data['count'], # 总数
        'articles':[{
            'cvid':a['id'],
            'categories':[t['name'] for t in a['categories']],
            #'tags':[t['name'] for t in a['tags']],
            'title':a['title'],
            'desc':a['summary'],
            'banner':a['banner_url'],
            'cover':a['origin_image_urls'][0],
            'stat':_article_stat_handler(a['stats']),
            'time':{
                'publish':a['publish_time'],
                'create':a['ctime']
                },
            #'dynamic':a['dynamic'],
            'is_liked':a['is_like'],
            'author':{
                'uid':a['author']['mid'],
                'name':a['author']['name'],
                'avatar':a['author']['face']
            },
            'words':a['words'], # 事字数
        } for a in articles]
    }
    return res


def get_readlist_list(uid:int,sort:int=0): # 文集
    '''
    sort = 0 / 1

    0: 按时间; 1: 按访问量
    '''
    api = 'https://api.bilibili.com/x/article/up/lists'
    api += '?mid=%s&sort=%d'%(uid,sort)
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    data = data['data']
    lists = data['lists']

    res = {
        'total':data['total'],
        'lists':[{
            'rlid':d['id'],
            'uid':d['mid'],
            'title':d['name'],
            'cover':d['image_url'],
            'time':{
                'update':d['update_time'],
                'create':d['ctime'],
                'publish':d['publish_time']
            },
            'words':d['words'],
            'view':d['read'], # 浏览量
            'count':d['articles_count'], # 内容物计数
        } for d in lists]
    }
    return res