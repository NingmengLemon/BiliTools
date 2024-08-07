# BiliTools

## 大概是一个Bilibili工具箱

**由于早年遗留的各种问题，此仓库停止更新，未来会尝试重写**  
> 到时大概会新开一个仓库罢

请注意，此程序有很多功能不完善，甚至可以说是简陋。而网上其实有很多已经成熟的同类工具，建议优先考虑他们。

此程序旨在满足自己的日常使用需求，嗯大概就是，早年的时候自嗨用的  

此程序仅能用于学习交流用途，不允许用于任何非法用途

### 功能喵

功能 | 备注
------------ | -------------
扫二维码登录 | /
查询并下载音频区的音频 | /
下载普通视频/番剧的音轨 | /
查看小黑屋 | /
查看普通视频的弹幕增量趋势 | /
查询并下载普通视频 | 仅DASH方式
查询并下载番剧 | 仅DASH方式
批量下载普通视频 | 仅DASH方式
下载漫画 | /
搜索普通视频 | /
解析合集 | /
解析频道 | 或者说是系列？
解析歌单 | /
调用ffplay进行播放 | /
给普通视频点赞投币收藏 | /
将普通视频添加到稍后再看 | /
查看互动视频的剧情图 | 但是展示器做得一团糟
下载互动视频的分P | /
查看普通视频的快照 | /
下载普通视频的封面 | /
解析自己的收藏夹 | 仍不稳定

值得注意的是，由于GUI未完工，部分功能（漫画/频道/合集/歌单/收藏夹 下载）不应当使用跳转模式，而应使用快速下载模式  
~~↑ 有相当一部分功能的未实现是懒得写GUI导致的~~

媒体处理依赖 ffmpeg.exe / 媒体播放依赖 ffplay.exe

我真的太逊了（逃）

### 感谢喵

感谢 [bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect) 的 API 文档

感谢 [danmaku2ass](https://github.com/m13253/danmaku2ass) 的弹幕转换程序

感谢 [FFmpeg](https://github.com/FFmpeg/FFmpeg) 的~~十分甚至九分~~好用的媒体处理程序

### 问题喵

目前存在的问题：

- 早年遗留的问题，比如线程不安全、默认参数不重复评估引起的问题
- 对于部分视频（比如[这个视频](https://www.bilibili.com/video/BV1ZW41147ER/)的某些分P）只能获取到MP4流，而不是DASH流 | [详细信息](https://github.com/SocialSisterYi/bilibili-API-collect/issues/888)
- 启动时疑似 Cookie 丢失导致的登录失效问题
- 还有各种各样的由于编写不规范导致的问题

<details><summary>我要笑死了</summary>
  
  ![主程序里BeLike](./images/indescribable_code_xd.png)

  Mypy & Pylint：蒸乌鱼😅
</details><br />

~~啊啊尽管如此，但是它居然能跑，太神奇了jrm~~

### 预览喵

<details><summary>一些界面的截图</summary>
  
  ![主窗口](./images/main_window.png)
  ![视频窗口](./images/video_window.png)
  ![音频窗口](./images/audio_window.png)
  ![番剧&影视窗口](./images/media_window.png)
  ![下载窗口](./images/download_window.png)
  ![小黑屋窗口](./images/blackroom_window.png)
</details>
