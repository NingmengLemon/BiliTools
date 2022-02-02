import os

def merge_media(audio_file,video_file,output_file): #传入时要带后缀
    assert not bool(os.popen('ffmpeg.exe -nostdin -hide_banner -i "{}" -i "{}" -vcodec copy -acodec copy "{}"'.format(audio_file,video_file,output_file)).close()),\
           '混流失败: "{}"&"{}"->"{}" with vcodec "{}"'.format(video_file,audio_file,output_file,video_encoding)

def convert_audio(inputfile,outfile=None,audio_format='mp3',quality='320k'):#outfile的后缀名由audio_format决定
    if outfile:
        outfile = '{}.{}'.format(outfile,audio_format)
    else:
        path,filename = os.path.split(inputfile)
        outfile = os.path.join(path,os.path.splitext(filename)[0]+'.'+audio_format)
    assert not bool(os.popen('ffmpeg.exe -nostdin -hide_banner -i "{}" -ab {} "{}"'.format(inputfile,quality,outfile)).close()),\
           '转码失败: "{}"->"{}" with bitrate {}bit/s'.format(inputfile,outfile,quality)

def check_ffmpeg():
    return not bool(os.popen('ffmpeg.exe -h').close())
