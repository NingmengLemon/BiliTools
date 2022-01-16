from . import bilicodes

class BiliError(Exception):
    def __init__(self,code,msg):
        self.code = code
        self.msg = msg
        self._final_msg = 'Code %s: %s'%(code,msg)
        
    def __str__(self):
        return self._final_msg

def error_raiser(code,message=None):
    if code != 0:
        if message:
            raise BiliError(code,message)
        else:
            raise BiliError(code,bilicodes.error_code[code])
