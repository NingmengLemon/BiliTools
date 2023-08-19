import tkinter as tk
import random

def _scale_point(coor1,coor2,scale):
    x1,y1 = coor1
    x2,y2 = coor2
    return x1+scale*(x2-x1),y1+scale*(y2-y1)

def key_point(*coors,scale):
    if coors:
        if len(coors) == 1:
            return coors[0]
        else:
            pre = []
            for i in range(0,len(coors)-1):
                pre += [_scale_point(coors[i],coors[i+1],scale)]
            return key_point(*pre,scale=scale)
    else:
        return None

def all_points(*coors,kpnum=100):
    scale = 0
    while scale <= 1:
        yield key_point(*coors,scale=scale)
        scale += 1/kpnum

class SampleWindow(object):
    def __init__(self):
        self.window = tk.Tk()
        self.window.resizable(False,False)
        self.canvas = tk.Canvas(self.window,width=400,height=400,bg='white')
        self.canvas.grid(column=0,row=0)
        self.label = tk.Label(self.window,text='-')
        self.label.grid(column=1,row=0)
        self.button = tk.Button(self.window,text='Refresh',command=self.show)
        self.button.grid(column=0,row=1)
        self.show()
        self.window.mainloop()
        
    def show(self):
        self.label['text'] = '-'
        text = ''
        self.canvas.delete('all')
        self.points = []
        kp = []
        for i in range(random.randint(2,20)):
            p = (random.randint(0,400),random.randint(0,400))
            self.points += [p]
            kp += [*p]
            text += str(p)+'\n'
        points = []
        for p in all_points(*self.points,kpnum=1000):
            points += [*p]
        self.canvas.create_line(*points)
        self.canvas.create_line(*kp,dash=(2,2),fill='red')
        self.label['text'] = text

if __name__ == '__main__':
    w = SampleWindow()
