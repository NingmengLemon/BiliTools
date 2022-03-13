from .error import error_raiser,BiliError
from . import requester
from . import bilicodes
from urllib import parse
import json

__all__ = ['search','get_info','get_favlist','get_danmaku_filter']

def get_danmaku_filter():
    api = 'https://api.bilibili.com/x/dm/filter/user?jsonp=jsonp'
    data = json.loads(requester.get_content_str(api))
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
    api = 'https://api.bilibili.com/x/space/acc/info?mid=%s'%uid
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
            'is_collected':bool(info['fav_state']), #是否收藏, 需要登录
            'is_liked':bool(info['like_state']), #是否点赞, 同上
            'content_count':info['media_count'],
            'content':[{
                'bvid':i['bvid'],
                'title':i['title'],
                'fav_time':i['fav_time'],
                'pub_time':i['pubtime'],
                'description':i['intro'],
                'uploader':{
                    'uid':i['upper']['mid'],
                    'name':i['upper']['name'],
                    'face':i['upper']['fave']
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
