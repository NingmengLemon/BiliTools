from .error import error_raiser,BiliError
from . import requester
from . import bilicodes
import json

__all__ = ['get_audio_stream','get_live_stream',
           'get_video_stream_dash','get_video_stream_flv']

def get_video_stream_flv(cid,avid=None,bvid=None,quality_id=64):
    fnval = 0
    fourk = 0
    if int(quality_id) == 120:
        fnval = fnval|128
        fourk = 1
    if avid != None:
        api = 'https://api.bilibili.com/x/player/playurl?avid=%s&cid=%s&fnval=%s&fourk=%s&qn=%s'%(avid,cid,fnval,fourk,quality_id)
    elif bvid != None:
        api = 'https://api.bilibili.com/x/player/playurl?bvid=%s&cid=%s&fnval=%s&fourk=%s&qn=%s'%(bvid,cid,fnval,fourk,quality_id)
    else:
        raise RuntimeError('You must choose one parameter between avid and bvid.')
    data = requester.get_content_str(api)
    data = json.loads(data)
    if data['code'] == -404:
        api = api.replace('/x/player/playurl','/pgc/player/web/playurl')
        data = requester.get_content_str(api)
        data = json.loads(data)
        error_raiser(data['code'],data['message'])
        data = data['result']
    else:
        error_raiser(data['code'],data['message'])
        data = data['data']
    parts = []
    for p in data['durl']:
        parts.append({
            'order':p['order'],#分段序号
            'length':p['length']/1000,#sec,
            'size':p['size'],
            'url':p['url'],
            'urls_backup':p['backup_url']
            })
    res = {
        'parts':parts,
        'quality':data['quality'],
        'length':data['timelength']/1000
        }
    return res

def get_video_stream_dash(cid,avid=None,bvid=None,dolby_vision=False,hdr=False,
                    _4k=False,_8k=False):
    '''Choose one parameter between avid and bvid'''
    fnval = 16
    fourk = 0
    if hdr:
        fnval = fnval|64
    if _4k:
        fourk = 1
        fnval = fnval|128
    #if dolby_audio:
    #    fnval = fnval|256
    if dolby_vision:
        fnval = fnval|512
    if _8k:
        fnval = fnval|1024
        
    if avid != None:
        api = 'https://api.bilibili.com/x/player/playurl?avid=%s&cid=%s&fnval=%s&fourk=%s'%(avid,cid,fnval,fourk)
    elif bvid != None:
        api = 'https://api.bilibili.com/x/player/playurl?bvid=%s&cid=%s&fnval=%s&fourk=%s'%(bvid,cid,fnval,fourk)
    else:
        raise RuntimeError('You must choose one parameter between avid and bvid.')
    data = requester.get_content_str(api)
    data = json.loads(data)
    if data['code'] == -404:
        api = api.replace('/x/player/playurl','/pgc/player/web/playurl')
        data = requester.get_content_str(api)
        data = json.loads(data)
        error_raiser(data['code'],data['message'])
        data = data['result']
    else:
        error_raiser(data['code'],data['message'])
        data = data['data']
    audio = []
    for au in data['dash']['audio']:
        audio.append({
            'quality':au['id'],#对照表 .bilicodes.stream_dash_audio_quality
            'url':au['baseUrl'],
            'url_backup':au['backupUrl'],
            'codec':au['codecs'],
            })
    if 'flac' in data['dash']:
        flac = data['dash']['flac']
        if flac:
            if flac['audio']:
                audio.append({
                    'quality':flac['audio']['id'],
                    'url':flac['audio']['base_url'],
                    'url_backup':flac['audio']['backup_url'], #list
                    'codec':flac['audio']['codecs']
                    })
    video = []
    for vi in data['dash']['video']:
        video.append({
            'quality':vi['id'],#对照表 .bilicodes.stream_dash_video_quality
            'url':vi['baseUrl'],
            'codec':vi['codecs'],
            'width':vi['width'],
            'height':vi['height'],
            'frame_rate':vi['frameRate'],#帧率
            
            })
    stream = {
        'audio':audio,
        'video':video,
        'length':data['timelength']/1000 #sec
        }
    return stream

def get_audio_stream(auid,quality=3,platform='web',uid=0):
    '''quality = 0(128K)/1(192K)/2(320K)/3(FLAC)'''
    api = 'https://api.bilibili.com/audio/music-service-c/url?songid=%s&quality=%s&privilege=2&mid=%s&platform=%s'%(auid,quality,uid,platform)
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['msg'])
    data = data['data']
    res = {
        'auid':data['sid'],
        'quality':{-1:'192K试听',0:'128K',1:'192K',2:'320K',3:'FLAC'}[data['type']],
        'quality_id':data['type'],
        'size':data['size'],#(Byte)
        'url':data['cdns'][0],
        'urls_backup':data['cdns'][1:],
        'title':data['title'],
        'cover':data['cover']
        }
    return res

def get_live_stream(room_id,quality=4,method=1):
    '''
    quality参见bilicodes
    method: 1(http-flv)/2(hls)
    '''
    method = {1:'web',2:'h5'}[int(method)]
    api = 'https://api.live.bilibili.com/room/v1/Room/playUrl?'\
          'cid={}&platform={}&quality={}'.format(room_id,method,quality)
    data = requester.get_content_str(api)
    data = json.loads(data)
    error_raiser(data['code'],data['message'])
    data = data['data']
    res = {
        'qn':data['current_qn'],
        'quality':data['current_quality'],
        'usable_quality':data['accept_quality'],
        'url':data['durl'][0]['url'],
        'urls_backup':[i['url'] for i in data['durl'][1:]],
        }
    return res
