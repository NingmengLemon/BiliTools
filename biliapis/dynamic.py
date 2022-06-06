from .error import error_raiser,BiliError
from . import requester
from . import bilicodes
import json

__all__ = ['get_dynamic_history','use_proxy']

use_proxy = True

def get_dynamic_history(uid,offset_dynamic_id=None,need_top=False):
    api = 'https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/space_history?'\
          'host_uid=%s&need_top=1&platform=web'%(uid,int(need_top))
    api += '&offset_dynamic_id='+str(offset_dynamic_id)
