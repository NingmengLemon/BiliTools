from .error import error_raiser, BiliError
from . import requester
from . import bilicodes
import json

__all__ = ['get_info','get_readlist']


def _article_stat_handler(stat:dict):
    return {
            "view": stat["view"],
            "collect": stat["favorite"],
            "like": stat["like"],
            "dislike": stat["dislike"],
            "reply": stat["reply"],
            "share": stat["share"],
            "coin": stat["coin"],
            "forward": stat["dynamic"],
        }

def get_info(cvid: int) -> dict:
    api = f"https://api.bilibili.com/x/article/viewinfo?id={cvid}"
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data["code"], data["message"])
    data = data["data"]

    res = {
        # Cookies required
        "is_liked": bool(data["like"]),
        "is_followed": data["attention"],
        "is_collected": data["favorite"],
        "coin_num": data["coin"],
        #
        "stat": _article_stat_handler(data["stats"]),
        "title": data["title"],
        "banner": data["banner_url"],
        "author": {
            "uid": data["mid"], 
            "name": data["author_name"]
            },
        "cover": data["origin_image_urls"][0],
        "dynamic_image": data["image_urls"][0],
        "is_in_readlist": data["in_list"],
        "type": data["type"],  # 0: 文章; 1: 笔记
        "prev": data["pre"],  # 上一篇, 没有就为 0
        "next": data["next"],  # 下一篇, 同上
    }
    return res


def get_readlist(rlid: int) -> dict:
    api = f"https://api.bilibili.com/x/article/list/web/articles?id={rlid}"
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data["code"], data["message"])
    data = data["data"]

    articles = data['articles']
    author = data['author']
    is_followed = data['attention']
    data = data['list']

    res = {
        'rlid':data['id'],
        'author':{
            'uid':data['mid'],
            'name':data['name'],
            'avatar':author['face'],
            'is_followed':is_followed
        },
        'cover':data['image_url'],
        'time':{ # timestamp
            'update':data['update_time'],
            'create':data['ctime'],
            'publish':data['publish_time']
        },
        'desc':data['summary'],
        'words':data['words'], # 字数
        'view':data['read'], # 浏览量
        'count':data['articles_count'], # 内容量
        'articles':[{
            'cvid':a['id'],
            'title':a['title'],
            'publish_time':a['publish_time'],
            'words':a['words'], # 字数
            'cover':a['image_urls'][0],
            'desc':a['summary'],
            'categories':[t['name'] for t in a['categories']],
            'stat':_article_stat_handler(a['stats']),
            'is_liked':a['like_state']
        } for a in articles]
    }
    return res

