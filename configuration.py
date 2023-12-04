import os
from biliapis import bilicodes

work_dir = os.getcwd()
user_name = os.getlogin()
version = "2.0.0_Dev16-fix"
inner_data_path = "C:\\Users\\{}\\BiliTools\\".format(user_name)

default_config = {
    "version": version,
    "topmost": False,
    "alpha": 1.0,  # 0.0 - 1.0
    "filter_emoji": False,
    "show_tips": False,
    "download": {
        "video": {
            "quality": None,
            "audio_convert": "mp3",
            "allow_flac": False,
            "subtitle": True,
            "allow_ai_subtitle": False,
            "subtitle_lang_regulation": [
                "zh-CN",
                "zh-Hans",
                "zh-Hant",
                "zh-HK",
                "zh-TW",
                "en-US",
                "en-GB",
                "ja",
                "ja-JP",
            ],
            "danmaku": False,
            "convert_danmaku": True,
            "danmaku_filter": {
                "keyword": [],
                "regex": [],
                "user": [],  # 用户uid的hash, crc32
                "filter_level": 0,  # 0-10
            },
        },
        "audio": {"convert": "mp3", "lyrics": False},
        "manga": {
            "save_while_viewing": False,
            "auto_save_path": os.path.join(inner_data_path, "MangaAutoSave"),
        },
        "max_thread_num": 2,
        "progress_backup_path": os.path.join(inner_data_path, "progress_backup.json"),
    },
    "play": {
        "video_quality": bilicodes.stream_flv_video_quality_["720P"],
        "audio_quality": bilicodes.stream_audio_quality_["320K"],
        "repeat": 0,
        "fullscreen": False,
        "auto_exit": False,
    },
    "proxy": {
        "enabled": False,
        "use_system_proxy": False,
        "host": "127.0.0.1",
        "port": 7890,
    },
}
