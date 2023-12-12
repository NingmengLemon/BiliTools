import os
from biliapis import bilicodes, requester, login
import logging
import colorama
import sys
from PIL import Image

# import winreg

development_mode = True

work_dir = os.getcwd()
user_name = os.getlogin()
version = "2.0.0_Dev17"
inner_data_path = "C:\\Users\\{}\\BiliTools\\".format(user_name)
config_path = os.path.join(inner_data_path, "config.json")
logging_path = os.path.join(inner_data_path, "last_run.log")

# def get_desktop():
#     key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Shell Folders')
#     return winreg.QueryValueEx(key,"Desktop")[0]

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
        "batch_sleep": 0.2,
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


# 日志设置
LOGLEVEL_COLOR_DICT = {
    logging.DEBUG: colorama.Fore.BLUE + "{}" + colorama.Fore.RESET,
    logging.INFO: colorama.Fore.GREEN + "{}" + colorama.Fore.RESET,
    logging.WARNING: colorama.Fore.YELLOW + "{}" + colorama.Fore.RESET,
    logging.ERROR: colorama.Fore.RED + "{}" + colorama.Fore.RESET,
    logging.CRITICAL: colorama.Fore.LIGHTRED_EX + "{}" + colorama.Fore.RESET,
}


def colored_filter(record: logging.LogRecord) -> bool:
    if development_mode:
        record.levelname = LOGLEVEL_COLOR_DICT[record.levelno].format(record.levelname)
    return True


basic_logging_config = {
    "format": "%(asctime)s - %(levelname)s - %(message)s",
    "datefmt": "%Y-%m-%d %H:%M:%S",
    "level": logging.INFO,
}

if development_mode or "-debug" in sys.argv:
    basic_logging_config["level"] = logging.DEBUG

if not development_mode:
    basic_logging_config["filename"] = logging_path
    basic_logging_config["filemode"] = "w+"

logging.getLogger("PIL").setLevel(logging.WARNING)
logger = logging.getLogger()
logger.addFilter(colored_filter)
logging.basicConfig(**basic_logging_config)

requester.inner_data_path = inner_data_path
login.ref_token_path = inner_data_path

if __name__ == "__main__":
    print("--- Logging Test ---")
    logging.debug("你是一个一个一个")
    logging.info("我是一个一个一个")
    logging.warning("他是一个一个一个")
    logging.error("Aughhhhhh")
    logging.critical("waaaaaaaaaaaagh")
