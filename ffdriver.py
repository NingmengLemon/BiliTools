import os
import time
import random
import atexit
import subprocess
import logging
import shlex

__all__ = ['tmpfile_path','merge_media','convert_audio','call_ffplay',
           'clear_tmpfiles','check_ffmpeg']

def subprocess_check_output(cmd):
    p = subprocess.Popen(cmd,shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    msg = ''
    for line in p.stdout.readlines():
        msg += line.decode()
    status = p.wait()
    return status

tmpfile_path = 'C:\\Users\\{}\\BiliTools\\tmpfiles\\'.format(os.getlogin())

def merge_media(audio_file,video_file,output_file): #传入时要带后缀
    logging.info('Calling FFmpeg...')
    assert not bool(os.popen('ffmpeg.exe -nostdin -hide_banner -i "{}" -i "{}" -vcodec copy -acodec copy "{}"'.format(audio_file,video_file,output_file)).close()),\
           '混流失败: "{}"&"{}"->"{}"'.format(video_file,audio_file,output_file)

def convert_audio(inputfile,outfile=None,audio_format='mp3',quality='320k'):#outfile的后缀名由audio_format决定
    if quality == 'flac':
        audio_format = 'flac'
    if outfile:
        outfile = '{}.{}'.format(outfile,audio_format)
    else:
        path,filename = os.path.split(inputfile)
        outfile = os.path.join(path,os.path.splitext(filename)[0]+'.'+audio_format)
    logging.info('Calling FFmpeg...')
    if quality == 'flac':
        os.rename(inputfile,outfile)
    else:
        assert not bool(os.popen('ffmpeg.exe -nostdin -hide_banner -i "{}" -ab {} "{}"'.format(inputfile,quality,outfile)).close()),\
               '转码失败: "{}"->"{}" with bitrate {}bit/s'.format(inputfile,outfile,quality)

def call_ffplay(*urls,referer='https://www.bilibili.com',title=None,is_audio=False,repeat=0,
                fullscreen=False,auto_exit=False):
    repeat = int(repeat)+1
    if len(urls) > 1:
        m3u8 = '\n'.join(urls)
        tmpfile = os.path.join(tmpfile_path,f'{time.time()}_{random.randint(100,999)}.m3u8')
        if not os.path.exists(tmpfile_path):
            os.makedirs(tmpfile_path)
        with open(tmpfile,'w+',encoding='utf-8') as f:
            f.write(m3u8)
        logging.info('Make m3u8 file: '+tmpfile)
        source = tmpfile
    else:
        source = urls[0]
    ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.74 Safari/537.36 Edg/79.0.309.43'
    command = 'ffplay.exe -hide_banner -user_agent "{}" -referer "{}"'.format(ua,referer,title,source)
    if title:
        command += ' -window_title "{}"'.format(title)
    if is_audio:
        command += ' -showmode waves'
    if repeat >= 1:
        command += ' -loop '+str(repeat)
    if fullscreen:
        command += ' -fs'
    if auto_exit:
        command += ' -autoexit'
    command += ' "{}"'.format(source)
    #print(command)
    logging.info('Calling FFplay...')
    assert not bool(os.popen(command).close()),'调用ffplay时出现错误'

@atexit.register
def clear_tmpfiles():
    if os.path.exists(tmpfile_path):
        for f in os.listdir(tmpfile_path):
            os.remove(os.path.join(tmpfile_path,f))

def check_ffmpeg():
    return not bool(os.popen('ffmpeg.exe -h').close())

