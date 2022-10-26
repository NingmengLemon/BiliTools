from .error import error_raiser,BiliError
from . import requester
from . import bilicodes
import json

__all__ = ['get_init_info']

#直播间号有长号和短号之分, 长号才是真实的房间号

def get_init_info(short_id):
    api = 'https://api.live.bilibili.com/room/v1/Room/room_init?id='+str(short_id)
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['msg'])
    data = data['data']
    res = {
        'room_id':data['room_id'],
        'short_id':data['short_id'],
        'uid':data['uid'],
        'need_p2p':data['need_p2p'],
        'is_hidden':data['is_hidden'],
        'is_locked':data['is_locked'],
        'status':data['live_status'],#0:未开播;1:直播中;2:轮播中
        'type':data['special_type'],#0:普通;1:付费,2:拜年祭
        'is_encrypted':data['encrypted'],
        'is_verified':data['pwd_verified'],#是否通过了加密验证, 仅当上面那条为true时有效
        }
