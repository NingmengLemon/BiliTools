import os,time,random,atexit

tmpfile_path = 'C:\\Users\\{}\\BiliTools\\tmpfiles\\'.format(os.getlogin())

def merge_media(audio_file,video_file,output_file): #传入时要带后缀
    assert not bool(os.popen('ffmpeg.exe -nostdin -hide_banner -i "{}" -i "{}" -vcodec copy -acodec copy "{}"'.format(audio_file,video_file,output_file)).close()),\
           '混流失败: "{}"&"{}"->"{}"'.format(video_file,audio_file,output_file,video_encoding)

def convert_audio(inputfile,outfile=None,audio_format='mp3',quality='320k'):#outfile的后缀名由audio_format决定
    if outfile:
        outfile = '{}.{}'.format(outfile,audio_format)
    else:
        path,filename = os.path.split(inputfile)
        outfile = os.path.join(path,os.path.splitext(filename)[0]+'.'+audio_format)
    assert not bool(os.popen('ffmpeg.exe -nostdin -hide_banner -i "{}" -ab {} "{}"'.format(inputfile,quality,outfile)).close()),\
           '转码失败: "{}"->"{}" with bitrate {}bit/s'.format(inputfile,outfile,quality)

def call_ffplay(*urls,referer='https://www.bilibili.com'):
    if len(urls) > 1:
        m3u8 = '\n'.join(urls)
        tmpfile = os.path.join(tmpfile_path,f'{time.time()}_{random.randint(100,999)}.m3u8')
        if not os.path.exists(tmpfile_path):
            os.makedirs(tmpfile_path)
        with open(tmpfile,'w+',encoding='utf-8') as f:
            f.write(m3u8)
        source = tmpfile
    else:
        source = urls[0]
    ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.74 Safari/537.36 Edg/79.0.309.43'
    command = 'ffplay.exe -hide_banner -user_agent "{}" -referer "{}" "{}"'.format(ua,referer,source)
    return os.popen(command).close()

@atexit.register
def clear_tmpfiles():
    if os.path.exists(tmpfile_path):
        for f in os.listdir(tmpfile_path):
            os.remove(os.path.join(tmpfile_path,f))

def check_ffmpeg():
    return not bool(os.popen('ffmpeg.exe -h').close())

