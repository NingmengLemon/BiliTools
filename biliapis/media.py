from .error import error_raiser,BiliError
from . import requester
from . import bilicodes
import json
from urllib import parse

__all__ = ['search_bangumi','search_ft','get_detail']

def _search_result_handler(data):
    tmp = []
    if 'result' in data:
        for res in data['result']:
            tmp.append({
                'mdid':res['media_id'],
                'ssid':res['season_id'],
                'title':res['title'].replace('<em class="keyword">','').replace('</em>',''),
                'title_org':res['org_title'].replace('<em class="keyword">','').replace('</em>',''),
                'cover':'https:'+res['cover'],
                'media_type':bilicodes.media_type[res['media_type']],
                'season_type':bilicodes.media_type[res['season_type']],
                'is_followed':bool(res['is_follow']),#Login required
                'area':res['areas'],
                'style':res['styles'],
                'cv':res['cv'],
                'staff':res['staff'],
                'url':res['goto_url'],
                'time_publish':res['pubtime'],
                'hit_type':res['hit_columns'],
                'score':res['media_score'] #包含user_count, score 两个键
                })
    result = {
        'seid':data['seid'],
        'page':data['page'],
        'pagesize':data['pagesize'],
        'result_count':data['numResults'],#max=1000
        'total_pages':data['numPages'],#max=50
        'time_cost':data['cost_time']['total'],
        'result':tmp
        }
    return result

def search_bangumi(*keywords,page=1):
    api = 'https://api.bilibili.com/x/web-interface/search/type'\
          '?search_type=media_bangumi&keyword={}&page={}'.format(
              '+'.join([parse.quote(keyword) for keyword in keywords]),page)
    data = json.loads(requester.get_content_str(api))
    error_raiser(data['code'],data['message'])
    data = data['data']
    return _search_result_handler(data)

def search_ft(*keywords,page):
    api = 'https://api.bilibili.com/x/web-interface/search/type'\
          '?search_type=media_ft&keyword={}&page={}'.format(
              '+'.join([parse.quote(keyword) for keyword in keywords]),page)
    data = json.loads(requester.get_content_str(api))
    error_raiser(data['code'],data['message'])
    data = data['data']
    return _search_result_handler(data)

def get_detail(ssid=None,epid=None,mdid=None):
    '''Choose one parameter from ssid, epid and mdid'''
    if ssid != None:
        api = 'https://api.bilibili.com/pgc/view/web/season?season_id=%s'%(ssid)
    elif epid != None:
        api = 'https://api.bilibili.com/pgc/view/web/season?ep_id=%s'%(epid)
    elif mdid != None:
        api = 'https://api.bilibili.com/pgc/review/user?media_id=%s'%(mdid)
        data = requester.get_content_str(api)
        data = json.loads(data)
        error_raiser(data['code'],data['message'])
        data = data['result']['media']
        api = 'https://api.bilibili.com/pgc/view/web/season?season_id=%s'%(data['season_id'])
    else:
        raise RuntimeError('You must choose one parameter from ssid, epid and mdid.')
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    data = data['result']

    episodes = []
    for ep in data['episodes']:
        episodes.append({
            'avid':ep['aid'],
            'bvid':ep['bvid'],
            'cid':ep['cid'],
            'epid':ep['id'],
            'cover':ep['cover'],
            'title_short':ep['title'],
            'title':ep['long_title'],
            'time_publish':ep['pub_time'],
            'url':ep['link'],
            'media_title':data['title'],
            'section_title':'正片',
            'tag':ep['badge'],
            'url':ep['link'],
            'vid':ep['vid'], # Unknown
            })
        
    sections = []
    if 'section' in data:
        for sec in data['section']:
            sections_ = []
            for ep in sec['episodes']:
                try:
                    sections_.append({
                        'avid':ep['aid'],
                        'bvid':ep['bvid'],
                        'cid':ep['cid'],
                        'epid':ep['id'],
                        'cover':ep['cover'],
                        'title':ep['title'],
                        'title_short':'',
                        'url':ep['share_url'],
                        'media_title':data['title'],
                        'section_title':sec['title'],
                        'tag':ep['badge']
                        })
                except:
                    continue
            sections.append({
                'title':sec['title'],
                'episodes':sections_
                })
            
    upinfo = None
    if 'up_info' in data:
        upinfo = {
            'uid':data['up_info']['mid'],
            'face':data['up_info']['avatar'],
            'follower':data['up_info']['follower'],
            'name':data['up_info']['uname']
            }
    
    seasons = []
    if 'seasons' in data:
        for ss in data['seasons']:
            seasons.append({
                'ssid':ss['season_id'],
                'mdid':ss['media_id'],
                'cover':ss['cover'],
                'title':ss['season_title']
            })
        
    result = {
        'bgpic':data['bkg_cover'],
        'cover':data['cover'],
        'episodes':episodes, # 正片内容
        'description':data['evaluate'],
        'mdid':data['media_id'],
        'ssid':data['season_id'],
        'record':data['record'],
        'title':data['title'],
        'sections':sections, # 非正片内容, 可能没有
        'is_finished':bool(data['publish']['is_finish']),
        'is_published':bool(data['publish']['is_started']),
        'publish_time':data['publish']['pub_time'], # str, YYYY-MM-DDD hh:mm:ss
        'rating':data['rating'], # count 评分人数, score 分数
        'seasons':seasons, # 同系列其他季度
        'stat':{
            'coin':data['stat']['coins'],
            'danmaku':data['stat']['danmakus'],
            'collect':data['stat']['favorites'],
            'like':data['stat']['likes'],
            'reply':data['stat']['reply'],
            'share':data['stat']['share'],
            'view':data['stat']['views']
            },
        'uploader':upinfo, # 可能没有
        'series_info':data['series'] # series_id, series_title
    }
    return result


