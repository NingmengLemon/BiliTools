import biliapis
import bezier_curve as bc
import tkinter as tk
from tkinter import ttk
from basic_window import Window
import time
import custom_widgets as cusw
import threading

config = None

def remove_repeat(l):
    l_ = []
    for i in l:
        if i not in l_:
            l_.append(i)
    return l_

class PlotShower(Window):
    def __init__(self,master,cid,bvid):
        self.cid = cid
        self.bvid = bvid
        self.graph_id = None
        self.cfg = { # 画图参数
            'plot_w':150, #plot块的宽
            'plot_h':75, #plot块的高
            'empty_w':150, #横向间距
            'min_empty_h':100, #最小的纵向间距
            'top_reserve':50, #顶部保留区域
            'bot_reserve':50, #底部保留区域
            'toptrace_y':5, #顶部plot跳转线的起始y坐标
            'bottrace_y':-5, #底部plot跳转线的相对画布底部的起始y坐标
            'bezcurve_kp_offset':25, 
            'jump_stretchout':20, #plot跳转线从plot块向前伸出的距离
            'jump_x_offset':5, #plot跳转线之间的横向间距
            'jump_y_offset':5  #plot跳转线之间的纵向间距
            }
        self.plots = []
        self.explored_plot_ids = {} # plot_id:(layer_index, in-layer_index) # e.g.第5层第1个:(4,0)
        # plot_id 在B站API中被描述为 edge_id
        # self.plots 注解
        # 类似于树的结构?
        # layer 0 [ {Root Plot} ]
        # layer 1 [ {Plot 1}, {Plot 2} ]
        # layer 2 [ {Plot 3}, {Plot 4}, {Plot 5}, {Plot 6} ]
        # ...
        # ↑大概就像这样
        self.is_explored = False
        self.is_drawn = False
        self.plot_coors = {} # plot_id:(x,y,w,h) # 便于draw函数连接各个plot块
        self.selected_plot = (None,None) # (plot_id, canvasItemId)
        self.sidebar_state = 'hide' # show / hide
        self.sidebar_width = 300
        self.sidebar_min_height = 500
        self.last_cfg_event = None
        self.explore_callback_dict = {}

        self.cid_map = {} # pid: cid
        #self.avid_map = {} # cid: avid

        super().__init__('BiliTools - PlotShower of %s'%bvid,True,master=master)#,config['topmost'],config['alpha'],master=master)
        w = self.window
        w.resizable(True,True)
        w.geometry('700x400')
        w.minsize(300,250)
        
        # 画布区域
        cv = self.canvas = tk.Canvas(w,height=w.winfo_height()-50,width=w.winfo_width()-25)
        cv.grid(column=0,row=0)
        sx = self.scbar_x = ttk.Scrollbar(w,orient=tk.HORIZONTAL,command=cv.xview)
        sx.grid(column=0,row=1,sticky='we')
        sy = self.scbar_y = ttk.Scrollbar(w,orient=tk.VERTICAL,command=cv.yview)
        sy.grid(column=1,row=0,sticky='sn')
        cv.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
        w.bind('<Configure>',self._config_event)
        
        # 底部功能按键区域
        fc = self.frame_console = tk.Frame(w)
        fc.grid(column=0,row=2,columnspan=2)
        #bdl = self.button_download_bottom = ttk.Button(fc,text='下载剧情')
        #bdl.grid(column=0,row=0)
        #bsv = self.button_save_plots = ttk.Button(fc,text='保存剧情图数据')
        
        # 拖动相关参数和变量
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_speed_reduce = -50
        
        # 详情区域
        self.detail_text_width = 39
        #fd = self.frame_detail = tk.Frame(w)
            # 进行一个偷梁换柱
        fd = self.frame_detail = cusw.VerticalScrolledFrame(w, height=w.winfo_height())
        #ttk.Separator(fd.inner_frame).grid(ipadx=self.sidebar_width)
        fd.grid(column=2,row=0,rowspan=2) #
        fd.grid_remove() #
        fd = fd.inner_frame
        # 框架内布置
            # 剧情图封面
##        self.imglabel_cover = cusw.ImageLabel(
##            fd, width=self.sidebar_width-25, height=int((self.sidebar_width-25)*(9/16)))
##        self.imglabel_cover.grid(column=0, row=0, columnspan=2)
            # 剧情图EdgeID
        le = self.label_edgeid = tk.Label(fd, text='EdgeID -')
        le.grid(column=0,row=1,columnspan=2,sticky='w')
            # 剧情图标题
        lt = self.label_title = tk.Label(fd, text='TITLE')
        lt.grid(column=0,row=2,columnspan=2,sticky='w')
            # 剧情图cID
        lc = self.label_cid = tk.Label(fd, text='cID -')
        lc.grid(column=0,row=3,columnspan=2,sticky='w')
            # 剧情图问题区
        fq = self.frame_question = tk.LabelFrame(fd, text='Question')
        fq.grid(column=0,row=4,columnspan=2)
                # 问题参数
##        tqt = self.label_quescontent = tk.Text(fd)
##        tqt.grid()
        tl = self.label_timelimit = tk.Label(fq, text='限时 -s')
        tl.grid(column=0,row=0)
        ps = self.label_pause_or_not = tk.Label(fq, text='回答时视频会暂停')
        ps.grid(column=0,row=1)
                # 4个选项的参数(最多4个选项)
        fos = self.frames_option = [
            [tk.LabelFrame(fq, text='选项1')],
            [tk.LabelFrame(fq, text='选项2')],
            [tk.LabelFrame(fq, text='选项3')],
            [tk.LabelFrame(fq, text='选项4')]
            ]
        for i in range(len(fos)):
            fos[i][0].grid(column=0,row=2+i)
            # 固定的提示性文本
            tk.Label(fos[i][0], text='跳转至:').grid(column=0,row=1,sticky='w')
            tk.Label(fos[i][0], text='进行以下变量运算:').grid(column=0,row=2,columnspan=2,sticky='w')
            tk.Label(fos[i][0], text='满足以下条件时出现:').grid(column=0,row=4,columnspan=2,sticky='w')
            # 可变文本 存入列表 后续会根据选中的块进行修改
            fos[i] += [
                tk.Text(fos[i][0],width=self.detail_text_width,
                        bg='#f0f0f0',bd=0,height=2,state='disabled'), # 选项内容
                tk.Label(fos[i][0], text='EdgeID -'), # 点击后跳转到的edgeID
                tk.Text(fos[i][0],width=self.detail_text_width,
                        bg='#f0f0f0',bd=0,height=5,state='disabled'), # 点击后执行的运算语句们 用\n分割
                tk.Text(fos[i][0],width=self.detail_text_width,
                        bg='#f0f0f0',bd=0,height=2,state='disabled'), # 选项出现的条件
                ]
            # index 0 是容纳以上组件的框架
            fos[i][1].grid(column=0,row=0,columnspan=2,sticky='w')
            fos[i][2].grid(column=1,row=1,sticky='w')
            fos[i][3].grid(column=0,row=3,columnspan=2,sticky='w')
            fos[i][4].grid(column=0,row=5,columnspan=2,sticky='w')
        
        # Overlayer区域
        fo = self.frame_overlayer = tk.Frame(w)
        fo.grid(column=0,row=0,columnspan=3,rowspan=3,ipadx=w.winfo_width(),ipady=w.winfo_height())
        les = self.label_explore_status = tk.Label(fo,text='剧情图未探索')
        les.grid(column=0,row=0,sticky='s')
        lep = self.label_explore_progress = tk.Label(fo,text='第 - 层\nEdgeID - \nTITLE')
        lep.grid(column=0,row=1,sticky='n',pady=10)
        
        
        self.canvas.bind('<B1-Motion>',self._drag_moving)
        self.canvas.bind('<Button-1>',self._drag_start)

    def init(self):
        self.explore_callback_dict = {
            'layer':0,
            'edge_id':1,
            'title':''
            }
        self.label_explore_status['text'] = '正在探索剧情图...'
        t = threading.Thread(target=self.explore,kwargs={'callback_dict':self.explore_callback_dict},daemon=True)
        t.start()
        self.window.after(10,self._init_check)

    def _init_check(self):
        if self.is_explored:
            self.draw()
            self.label_explore_status['text'] = '完成'
            self.window.after(1000,lambda:self.frame_overlayer.grid_remove())
            
        else:
            self.label_explore_progress['text'] = '第 {layer} 层\nEdgeID {edge_id}\n{title}'.format(
                **self.explore_callback_dict
                )
            self.window.after(50,self._init_check)
        

    def _drag_start(self,event):
        #print('啊？')
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def _drag_moving(self,event):
        #print('正在被撅')
        self.canvas.xview_scroll(int((event.x-self.drag_start_x)/self.drag_speed_reduce),'units')
        self.canvas.yview_scroll(int((event.y-self.drag_start_y)/self.drag_speed_reduce),'units')
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def fill_detail_area(self,pid):
        i1,i2 = self.explored_plot_ids[pid]
        data = self.plots[i1][i2]
        #cover_url = data[]
        self.label_edgeid['text'] = 'EdgeID %s'%data['edge_id']
        self.label_title['text'] = data['title']
        if pid in self.cid_map:
            self.label_cid['text'] = 'cID %s'%self.cid_map[pid]
        q = data['question']
        if q:
            self.frame_question.grid()
        else:
            self.frame_question.grid_remove()
            return
        if q['time_limit'] == -1:
            self.label_timelimit['text'] = '不限时'
        else:
            self.label_timelimit['text'] = '限时 %ds'%q['time_limit']
        self.label_pause_or_not['text'] = {
            True:'回答时视频会暂停',
            False:'直接进入默认选项'
            }[q['pause']]
        # 填充选项
        fos = self.frames_option
        for i in range(len(fos)):
            if i<=len(q['choices'])-1:
                fos[i][0].grid()
                c = q['choices'][i]
                l = '选项%d'%(i+1)
                if c['is_default']:
                    l += ' [默认]'
                if c['is_hidden']:
                    l += ' [隐藏]'
                fos[i][0]['text'] = l
                self.set_text(fos[i][1],lock=True,text=c['text'])
                fos[i][2]['text'] = 'EdgeID %d'%c['jump_edge_id']
                self.set_text(fos[i][3],lock=True,text='\n'.join(c['var_operations']))
                self.set_text(fos[i][4],lock=True,text=c['appear_condition'])
                
            else:
                fos[i][0].grid_remove()

    def play_plot(self,pid):
        i1,i2 = self.explored_plot_ids[pid]
        data = self.plots[i1][i2]

    def download_plot(self,pid,audio_only=False):
        i1,i2 = self.explored_plot_ids[pid]
        data = self.plots[i1][i2]

    def _config_event(self,event=None):
        if self.sidebar_state == 'show':
            self.canvas.configure(
                width=self.window.winfo_width()-25-self.sidebar_width,
                height=self.window.winfo_height()-50
                )
            self.window.minsize(300+self.sidebar_min_height,250+self.sidebar_width)
        else:
            self.canvas.configure(
                width=self.window.winfo_width()-25,
                height=self.window.winfo_height()-50
                )
            self.window.minsize(300,250)
        self.last_cfg_event = event
        self.frame_detail.set_height(self.window.winfo_height()-25)

    def set_sidebar_state(self,state):
        if state == 'show':
            if self.sidebar_state != 'show':
                self.sidebar_state = 'show'
                self.frame_detail.set_height(self.window.winfo_height()-25) #
                self.frame_detail.grid()
        else:
            if self.sidebar_state != 'hide':
                self.sidebar_state = 'hide'
                self.frame_detail.grid_remove()
        self._config_event()

    def explore(self, callback_func=None, callback_dict=None): # 耗时, 丢子线程里, 仅需调用一次
        # callback_func接受3个参数
        # - 当前剧情图所在的layer(int)
        # - 当前剧情图的 Edge ID
        # - 当前剧情图的标题
        # 每探索到一个剧情图就回调一次
        # ..._dict同理 只是把调用变成了修改
        bvid = self.bvid
        gid = self.graph_id = biliapis.video.get_interact_graph_id(self.cid,bvid=bvid)
        root_plot = biliapis.video.get_interact_edge_info(gid,bvid=bvid)
        self.plots += [[root_plot]]
        self.explored_plot_ids[root_plot['edge_id']] = (0,0)
        plots = [root_plot]
        next_layer = []
        layer_num = 1
        while True: # 大循环: plots的深度
            for plot in plots:
                #breakpoint()
                if plot['question']:
                    next_layer += [i['jump_edge_id'] for i in plot['question']['choices']]
            next_layer = remove_repeat(next_layer)
            if next_layer:
                #print('Next:',next_layer)
                pass
            else:
                #breakpoint()
                #print('MISSION ACCOMPLISHED!')
                break
            #print('Layer',layer_num)
            plots = []
            self.plots.append([])
            i = 0
            for pid in next_layer: # 小循环: plots每层中的plot
                if pid in self.explored_plot_ids:
                    continue
                plot = biliapis.video.get_interact_edge_info(gid,bvid=bvid,edge_id=pid)
                #print('Fetched:',pid)
                if callback_func:
                    callback_func(layer_num, pid, plot['title'])
                if callback_dict:
                    callback_dict['layer'] = layer_num
                    callback_dict['edge_id'] = pid
                    callback_dict['title'] = plot['title']
                if plot['question']:
                    plots.append(plot)
                    for choice in plot['question']['choices']:
                        self.cid_map[choice['jump_edge_id']] = choice['jump_cid']
                self.plots[-1].append(plot)
                # 试图录入cid信息
                for story in plot['story_list']:
                    self.cid_map[story['edge_id']] = story['cid']
                #for part in plot['preload_parts']:
                    #self.cid_map[]
                    #self.avid_map[part['cid']] = part['avid']
                    
                self.explored_plot_ids[plot['edge_id']] = (layer_num,i)
                i += 1
                time.sleep(0.2)
            next_layer = []
            layer_num += 1
        self.is_explored = True
        #self.frame_overlayer.grid_remove()

    def draw(self): # 需要预先调用 self.explore()
        if not self.is_explored:
            return
        cfg = self.cfg
        # 相关参数
        plot_w = cfg['plot_w']
        plot_h = cfg['plot_h']
        empty_w = cfg['empty_w']
        min_empty_h = cfg['min_empty_h']
        top_reserve = cfg['top_reserve']
        bot_reserve = cfg['bot_reserve']
        max_plotnum = max([len(i) for i in self.plots])
        tth = max_plotnum*plot_h+(max_plotnum-1)*min_empty_h # total height
        ttw = len(self.plots)*plot_w+(len(self.plots)-1)*empty_w # total width
        toptrace_y = cfg['toptrace_y']
        bottrace_y = tth+top_reserve+bot_reserve+cfg['bottrace_y']
        bezcurve_kp_offset = cfg['bezcurve_kp_offset']
        jump_stretchout = cfg['jump_stretchout']
        jump_x_offset = cfg['jump_x_offset']
        jump_y_offset = cfg['jump_y_offset']
        # 开始
        # 放置Plot块
        pcs = self.plot_coors
        x = 20
        for li in range(len(self.plots)):
            layer = self.plots[li]
            pn = len(layer)
            y = top_reserve-plot_h/2
            step_y = tth/(len(layer)+1)
            for pi in range(len(layer)):
                plot = layer[pi]
                y += step_y
                coor = (x,y,plot_w,plot_h) # x,y,w,h
                self.plot_coors[plot['edge_id']] = coor
                #边框
                color = 'white'
                # 起始剧情和结尾剧情特殊标注
                if plot['edge_id'] == 1: 
                    color = '#ffb6c1'
                if plot['is_end_edge']:
                    color = '#00fa9a'
                self.canvas.create_rectangle(x,y,x+plot_w,y+plot_h,fill=color)
                #Text
                self.canvas.create_text(x+plot_w/2,y+0.2*plot_h,text=plot['title'])
                #t = tk.Entry(self.canvas,bg='#ffffff',bd=0,width=20)
                #self.canvas.create_window(x+plot_w/2,y+0.2*plot_h,window=t)
                #t.insert(tk.END,plot['title'])
                #self._bind_scroll_event(t)
                #t['state'] = 'readonly'
                #Plot id
                self.canvas.create_text(x+plot_w/2,y+0.5*plot_h,text='EdgeID %s'%plot['edge_id'])
                #Viewing Button
                #b = ttk.Button(self.canvas,text='View Detail',command=lambda index=(li,pi):self.show_plot_info(*index))
                #self.canvas.create_window(x+plot_w/2,y+0.8*plot_h,window=b)
                #使用bind事件返回的event判断点击了哪个plot块
            x += plot_w+empty_w
        # 连接Plot块 #arrow='last'
        terminate_offset_x = {} # layer_index: offset
        for layer in self.plots:
            x_offset = 0
            for plot in layer:
                if not plot['question']:
                    continue
                on = len(plot['question']['choices']) # option num
                step = plot_h/(on+1)
                y_offset = 0
                for choice in plot['question']['choices']:
                    y_offset += step
                    # 获取要连接的两个plot的信息
                    p1 = plot['edge_id']
                    p2 = choice['jump_edge_id']
                    li1,pi1 = self.explored_plot_ids[p1]
                    li2,pi2 = self.explored_plot_ids[p2]
                    x1,y1,w1,h1 = self.plot_coors[p1]
                    x2,y2,w2,h2 = self.plot_coors[p2]
                    # 分情况进行连接
                    if li1+1 == li2: # 正常的连接
                        #self._draw_bezcurve(
                        #    (x1+w1,y1+y_offset),(x1+w1+bezcurve_kp_offset,y1+y_offset),(x2-bezcurve_kp_offset,y2+h2/2),(x2,y2+h2/2),
                        #    arrow='last'
                        #    )
                        self.canvas.create_line(
                            x1+w1,y1+y_offset, x2,y2+h2/2,
                            arrow='last')
                    elif li+1 > li2 or li < li2: # 跳连
                        if li2 in terminate_offset_x:
                            tox = terminate_offset_x[li2]
                            terminate_offset_x[li2] += jump_x_offset
                        else:
                            terminate_offset_x[li2] = jump_x_offset
                            tox = 0
                        if pi1 <= len(layer)/2: # 从上面绕
                            self.canvas.create_line(
                                x1+w1,y1+y_offset, x1+w1+jump_stretchout+x_offset,y1+y_offset, x1+w1+jump_stretchout+x_offset,toptrace_y,
                                x2-jump_stretchout-tox,toptrace_y, x2-jump_stretchout-tox,y2+h2/2,  x2,y2+h2/2,  
                                fill='red',arrow='last')
                            toptrace_y += jump_y_offset
                        else: # 从下面绕
                            self.canvas.create_line(
                                x1+w1,y1+y_offset, x1+w1+jump_stretchout+x_offset,y1+y_offset, x1+w1+jump_stretchout+x_offset,bottrace_y,
                                x2-jump_stretchout-tox,bottrace_y, x2-jump_stretchout-tox,y2+h2/2,  x2,y2+h2/2,  
                                fill='red',arrow='last')
                            bottrace_y -= jump_y_offset
                        x_offset += jump_x_offset
        # 完成
        self.canvas.config(scrollregion=(0,0,ttw+25,tth+top_reserve+bot_reserve))
        self._bind_scroll_event(self.canvas)
        self.canvas.bind('<Button-1>',self.click,add='+')
        self.is_drawn = True

    def click(self,event):
        #获得点击点在canvas中的位置
        _,_,cw,ch = self.canvas.config('scrollregion')[-1].split()
        xic = event.x+self.scbar_x.get()[0]*int(cw)
        yic = event.y+self.scbar_y.get()[0]*int(ch)
        #self.canvas.create_line(xic-100,yic-100,xic,yic,arrow='last')
        selected = None
        for pid,indexs in self.explored_plot_ids.items():
           x,y,w,h = self.plot_coors[pid]
           if x<=xic<=x+w and y<=yic<=y+h:
               selected = pid
               break
        if selected:
            self.fill_detail_area(selected)
        last_spi,last_cii = self.selected_plot # last_plot_id,last_canvasItemId
        if selected:
            if last_cii == selected:
                return
            if last_cii:
                self.canvas.delete(last_cii)
            now_cii = self.canvas.create_rectangle(
                x-3,y-3,x+w+3,y+h+3,
                outline='#0078d7',width=2
                )
            self.selected_plot = (selected,now_cii)
            #self.show_plot_info(*indexs)
            self.set_sidebar_state('show')
        else:
            if last_cii:
                self.canvas.delete(last_cii)
            self.set_sidebar_state('hide')
            self.selected_plot = (None,None)
        
    def _draw_bezcurve(self,*coors,kpnum=20,**kwargs):
        p = []
        for i in bc.all_points(*coors,kpnum=kpnum):
            p += [*i]
        return self.canvas.create_line(*p,**kwargs)
    
    def _scroll_event(self,event):
        self.canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def _bind_scroll_event(self,widget):
        widget.bind('<MouseWheel>',self._scroll_event)
        widget.bind('<Button-4>',self._scroll_event)
        widget.bind('<Button-5>',self._scroll_event)
        widget.bind('<Up>',lambda event:self.canvas.yview_scroll(-1,"units"))
        widget.bind('<Down>',lambda event:self.canvas.yview_scroll(1,"units"))

if __name__ == '__main__':
    biliapis.requester.global_config(use_proxy=False)
    w = tk.Tk()
    #wc = PlotShower(w,1169855952,'BV1Zh4y1u7GB')
    wc = PlotShower(w,957032264,'BV1zY411177B')
    #wc = PlotShower(w,245682070,'BV1UE411y7Wy')
    #wc = PlotShower(w,512487448,'BV1Du411Q7jf')
    #wc.explore()
    #wc.draw()
    #w.mainloop()
