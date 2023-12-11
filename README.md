# BiliTools

## Bilibili工具箱

此项目仍在**开发中**，并且很多功能仍不完善，甚至简陋

↑ 所以到目前为止发的 release 的类型都是 pre-release

此项目使用 Python 和 Tkinter 进行开发，旨在满足自己的日常使用需求（所以这就是你不注重美观的原因吗（恼））

此项目仅能用于学习交流用途，不允许用于任何非法用途

### 现有以下功能：

功能 | 备注
------------ | -------------
扫二维码登录 | 
查询并下载音频区的音频 | 
下载普通视频/番剧的音轨 | 
查看小黑屋 | 
查看普通视频的弹幕增量趋势 | 
查询并下载普通视频 | 仅DASH方式
查询并下载番剧 | 仅DASH方式 
批量下载普通视频 | 仅DASH方式 
下载漫画 |  
搜索普通视频 |
解析合集 |
解析频道 | 或者说是系列？
解析歌单 | 
调用ffplay进行播放 | 
给普通视频点赞投币收藏 | 
将普通视频添加到稍后再看 | 
查看互动视频的剧情图 | 但是展示器做得一团糟 
下载互动视频的分P | 
查看普通视频的快照 |
下载普通视频的封面 | 
解析自己的收藏夹 | 仍不稳定

值得注意的是，由于GUI未完工，部分功能（漫画/频道/合集/歌单/收藏夹 下载）不应当使用跳转模式，而应使用快速下载模式

媒体处理依赖 ffmpeg.exe / 媒体播放依赖 ffplay.exe

我真的太逊了（逃）

感谢 [bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect) 的 API 文档

感谢 [danmaku2ass](https://github.com/m13253/danmaku2ass) 的弹幕转换程序

感谢 [FFmpeg](https://github.com/FFmpeg/FFmpeg) 的~~十分甚至九分~~好用的媒体处理程序

<details><summary>P.S. </summary>这个项目其实也有一段时间的历史了，算是我的练习作罢。但也正因为如此，一些代码已经堆成了shit山，再加上现在我进了大学的计算机系，得突破舒适区去细学别的语言了，这个项目可能不会更新得很频繁。但会保持在能用的程度，也就是说不会失效，因为这个程序我平时也在用ww</details>


<details><summary>一些界面的截图</summary>
  
  ![主窗口](https://raw.githubusercontent.com/NingmengLemon/BiliTools/main/images/main_window.png)
  ![视频窗口](https://raw.githubusercontent.com/NingmengLemon/BiliTools/main/images/video_window.png)
  ![音频窗口](https://raw.githubusercontent.com/NingmengLemon/BiliTools/main/images/audio_window.png)
  ![番剧&影视窗口](https://raw.githubusercontent.com/NingmengLemon/BiliTools/main/images/media_window.png)
  ![下载窗口](https://raw.githubusercontent.com/NingmengLemon/BiliTools/main/images/download_window.png)
  ![小黑屋窗口](https://raw.githubusercontent.com/NingmengLemon/BiliTools/main/images/blackroom_window.png)
</details>

既然都看到这里了，不如点个star叭 (。・∀・)ノ

我会继续努力更新这个项目的~
