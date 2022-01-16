from .error import error_raiser,BiliError
from . import requester
from . import bilicodes
import json

def _single_comment_handler(data):
    res = {
        'rpid':data['rpid'],
        'oid':data['oid'],
        'type_id':data['type'],
        'sender':{
            'uid':data['member']['mid'],
            'name':data['member']['uname'],
            'sex':data['member']['sex'],
            'desc':data['member']['sign'],
            'face':data['member']['avatar'],
            'level':data['member']['level']['current_level'],
            'vip':{0:'非大会员',1:'月度大会员',2:'年度及以上大会员'}[data['member']['vip']['vipType']],
            'is_vip':bool(data['member']['vip']['vipStatus']),
            'verify':data['member']['official_verify'],
            'fanslabel_id':data['member']['fans_detail']['medal_id'],
            'fanslabel_name':data['member']['fans_detail']['medal_name'],
            },
        'content':{
            'message':data['content']['message'],
            'plat':{1:'Web端',2:'Android客户端',3:'iOS客户端',4:'WindowsPhone客户端'}[data['content']['plat']],
            'device':data['content']['device']
            }
        }
    return res

def get_comment():
    pass #wait for building
