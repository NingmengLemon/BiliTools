from .error import error_raiser,BiliError
from . import requester
from . import bilicodes
import json

def get_detail(mcid):
    data = requester.post_data_str('https://manga.bilibili.com/twirp/comic.v1.Comic/ComicDetail?device=pc&platform=web',data={
        'comic_id':int(mcid)
        })
    data = json.loads(data)
    error_raiser(data['code'],data['msg'])
    data = data['data']
    res = {
        'mcid':data['id'],
        'comic_title':data['title'],
        'authors':data['author_name'],
        'is_japan_comic':data['japan_comic'],
        'last_read':{ #上一次阅读
            'time':data['last_read_time'],
            'short_title':data['last_short_title']
            },
        'renewal_time':data['renewal_time'], #更新频次
        'styles':data['styles'],
        'total_count':data['total'], #总章节数
        'introduction':data['introduction'],
        'description':data['classic_lines'],
        'cover':{ #封面
            'vertical':data['vertical_cover'], #竖版
            'square':data['square_cover'], #正方形版
            'horizontal':data['horizontal_cover'] #横版
            }
        }
    ep_list = [] #章节列表, 排序从新到旧
    for ep in data['ep_list']:
        ep_list.append({
            'epid':ep['id'],
            'eptitle':ep['title'],
            'eptitle_short':ep['short_title'],
            'cover':ep['cover'],
            'is_free':ep['is_in_free'],
            'is_locked':ep['is_locked'],
            'like_count':ep['like_count'],#点赞数
            'ord':ep['ord'],#章节标识 不一定连续, 但一定按先后顺序从小到大
            'pay_gold':ep['pay_gold'],#价格
            'pub_time':ep['pub_time'],#发布时间
            })
    res['ep_list'] = ep_list
    return res

def get_episode_info(epid):
    data = requester.post_data_str('https://manga.bilibili.com/twirp/comic.v1.Comic/GetEpisode?device=pc&platform=web',data={
        'id':int(epid)
        })
    data = json.loads(data)
    error_raiser(data['code'],data['msg'])
    data = data['data']
    res = {
        'eptitle':data['title'],
        'eptitle_short':data['short_title'],
        'mcid':data['comic_id'],
        'comic_title':data['comic_title']
        }
    return res

def get_episode_image_index(mcepid):
    data = post_data_str('https://manga.bilibili.com/twirp/comic.v1.Comic/GetImageIndex?device=pc&platform=web',data={
        'ep_id':int(mcepid)
        })
    data = json.loads(data)
    error_raiser(data['code'],data['msg'])
    data = data['data']
    res = {
        'host':data['host']
        }
    images = [] #每个章节包含的图片, 按先后顺序排列
    for image in data['images']:
        images.append({
            'path':image['path'], #与host拼接成图片url
            'width':image['x'],
            'height':image['y']
            })
    res['images'] = images
    return res

def get_episode_image_token(*paths): #参数来自get_manga_episode_image_index的path
    data = post_data_str('https://manga.bilibili.com/twirp/comic.v1.Comic/ImageToken?device=pc&platform=web',data={
        'urls':json.dumps(list(paths))
        })
    data = json.loads(data)
    error_raiser(data['code'],data['msg'])
    data = data['data'] #是列表套字典的操作, 有url和token两个键
    return data
