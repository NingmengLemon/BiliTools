from .error import error_raiser, BiliError
from . import requester
from . import bilicodes
import json

from typing import Literal, Union, Optional

__all__ = ["get_dynamic_list"]


_dynamic_types = [
    "DYNAMIC_TYPE_NONE",  # 无效动态
    "DYNAMIC_TYPE_FORWARD",  # 动态转发
    "DYNAMIC_TYPE_AV",  # 投稿视频
    "DYNAMIC_TYPE_PGC",  # 剧集
    "DYNAMIC_TYPE_COURSES",  #
    "DYNAMIC_TYPE_WORD",  # 纯文字动态
    "DYNAMIC_TYPE_DRAW",  # 带图动态
    "DYNAMIC_TYPE_ARTICLE",  # 投稿专栏
    "DYNAMIC_TYPE_MUSIC",  # 音乐
    "DYNAMIC_TYPE_COMMON_SQUARE",  # 装扮 / 剧集点评 / 普通分享
    "DYNAMIC_TYPE_COMMON_VERTICAL",  #
    "DYNAMIC_TYPE_LIVE",  # 直播间分享
    "DYNAMIC_TYPE_MEDIALIST",  # 收藏夹
    "DYNAMIC_TYPE_COURSES_SEASON",  # 课程
    "DYNAMIC_TYPE_COURSES_BATCH",  #
    "DYNAMIC_TYPE_AD",  #
    "DYNAMIC_TYPE_APPLET",  #
    "DYNAMIC_TYPE_SUBSCRIPTION",  #
    "DYNAMIC_TYPE_LIVE_RCMD",  # 直播开播
    "DYNAMIC_TYPE_BANNER",  #
    "DYNAMIC_TYPE_UGC_SEASON",  # 合集更新
    "DYNAMIC_TYPE_SUBSCRIPTION_NEW",  #
]

_author_types = [
    "AUTHOR_TYPE_NONE",
    "AUTHOR_TYPE_NORMAL",  # 普通
    "AUTHOR_TYPE_PGC",  # 剧集
    "AUTHOR_TYPE_UGC_SEASON",  # 合集
]

_additional_types = [
    "ADDITIONAL_TYPE_NONE",
    "ADDITIONAL_TYPE_PGC",
    "ADDITIONAL_TYPE_GOODS",  # 商品
    "ADDITIONAL_TYPE_VOTE",  # 投票
    "ADDITIONAL_TYPE_COMMON",  # 普通
    "ADDITIONAL_TYPE_MATCH",
    "ADDITIONAL_TYPE_UP_RCMD",
    "ADDITIONAL_TYPE_UGC",  # 视频跳转
    "ADDITIONAL_TYPE_RESERVE",
]

_major_types = {
"MAJOR_TYPE_NONE",
"MAJOR_TYPE_NONE",
"MAJOR_TYPE_OPUS",
"MAJOR_TYPE_ARCHIVE",
"MAJOR_TYPE_PGC",
"MAJOR_TYPE_COURSES",
"MAJOR_TYPE_DRAW",
"MAJOR_TYPE_ARTICLE",
"MAJOR_TYPE_MUSIC",
"MAJOR_TYPE_COMMON",
"MAJOR_TYPE_LIVE",
"MAJOR_TYPE_MEDIALIST",
"MAJOR_TYPE_APPLET",
"MAJOR_TYPE_SUBSCRIPTION",
"MAJOR_TYPE_LIVE_RCMD",
"MAJOR_TYPE_UGC_SEASON",
"MAJOR_TYPE_SUBSCRIPTION_NEW",
}

def get_dynamic_list(
    type_: Literal["all", "video", "pgc", "article"] = "all",
    offset: Optional[Union[str, int]] = None,
    update_baseline: Optional[Union[str, int]] = None,
):
    """
    需要登录

    results:
    [
    dy 1 <- id: {update_baseline} (在请求中传入时仅作统计用)
    dy 2
    dy 3
    ...
    dy n <- id: {offset} (在下一次请求中作为传入来实现翻页)
    ]
    """
    api = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/all"
    api += "?timezone_offset=-480&type=%s" % type_
    if offset:
        api += "&offset=%s" % offset
    if update_baseline:
        api += "&update_baseline=%s" % update_baseline

    data = requester.get_content_str(api)
    data: dict = json.loads(data)
    error_raiser(data["code"], data.get("message"))
    data: dict = data["data"]

    result = {
        "has_more": data.get("has_more"),
        "offset": data.get("offset", ""),
        "update_baseline": data.get("update_baseline", ""),
        "update_num": data.get("update_num", 0),  # 在 update_baseline 以上的动态个数
        "items": [_item_handler(i) for i in data.get("items", [])],
    }

    return result


def _item_handler(item: dict):
    basic: dict = item.get("basic", {})
    modules: dict = item.get("modules", {})
    uploader: dict = modules["module_author"]
    dynamic: dict = modules["module_dynamic"]

    info = {
        "author": {
            "face": uploader.get("face"),
            "name": uploader.get("name"),
            "following": uploader.get("following", False),
            "id": uploader.get("mid", 0),
        },
        "publish_action": uploader.get("pub_action", ""),  # 更新描述, e.g. 投稿了视频
        "time": uploader.get("pub_ts", 0),  # timestamp (sec)
        "type": item.get("type", "DYNAMIC_TYPE_NONE"),  # see _dynamic_types
        "id": item.get("id_str", "0"),
        "visible": item.get("visible", True),
    }
    content = _dynamic_handler(item["modules"]["module_dynamic"], item.get("type"))
    result = {
        "info": info,
        "content": content,
    }

    origin = item.get("orig")
    result["origin"] = _item_handler(origin) if origin else None

    return result


def _dynamic_handler(dyn: dict, type_: str):
    result = {
        "text": dyn.get("desc", {}).get("text", "")  # 惹啊啊啊啊啊
        # 111不许折叠
    }
    result.update(_additional_handler(dyn["additional"]))

    major = {}
    match dyn.get("major",{}).get("type"):
        case _:
            pass
    result.update(major)

    return result

def _ugc_handler(major: dict):
    pass


def _additional_handler(additional: dict):
    type_ = additional["type"]
    result = {}
    match type_:
        case "ADDITIONALTYPE_VOTE":
            vt = additional["vote"]
            result["text"] = vt["desc"]
            result["time_left"] = vt["end_time"]  # sec
            result["join_num"] = vt["join_num"]
            result["vid"] = vt["vote_id"]
        case "ADDITIONAL_TYPE_UGC":
            vd = additional["ugc"]
            result["cover"] = vd["cover"]
            result["duration"] = vd["duration"]
            result["avid"] = int(vd["id_str"])
            result["title"] = vd["title"]
        case _:
            pass
    return result
