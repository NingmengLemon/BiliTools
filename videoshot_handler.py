from PIL import Image
from biliapis import requester
from io import BytesIO

from biliapis import requester

class VideoShotHandler(object):
    def __init__(self, data):
        self.data = data
        self.is_ready = False
    
    def _load(self):
        data = self.data
        self.images = []
        for u in data["img_ver"]:
            self.images.append(BytesIO(requester.get_content_bytes(u)))
        self.index = data['index']

    def _split(self):
        data = self.data
        self.frames = []
        w = data['img_w']
        h = data['img_h']
        wl = data['img_x_length']
        hl = data['img_y_length']
        tmpbio = None
        tmpimg = None
        for image in self.images:
            with Image.open(image) as img:
                for y in range(hl):
                    for x in range(wl):
                        tmpbio = BytesIO()
                        tmpimg = img.crop((x*w+1,y*h+1,(x+1)*w+1,(y+1)*h+1))
                        tmpimg.save(tmpbio,'png')
                        self.frames.append(tmpbio)

    def init(self):
        self._load()
        self._split()
        self.is_ready = True

    def get_frame(self, index=0):
        return self.frames[index],self.index[index]