from .error import error_raiser,BiliError
from . import requester
from . import bilicodes
from urllib import parse
import json

__all__ = ['search','get_info']

def search(keyword,page=1,order='0',order_sort=0,user_type=0):
    '''order = 0(default) / fans / level
    order_sort = 0(high->low) / 1(low->high)
    user_type = 0(All) / 1(Uploader) / 2(CommonUser) / 3(CertifiedUser)
    '''
    api = 'https://api.bilibili.com/x/web-interface/search/type?search_type=bili_user&' \
        'keyword={}&page={}&order={}&order_sort={}'.format(parse.quote(keyword),page,order,order_sort)
    data = json.loads(get_content_str(api))
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
