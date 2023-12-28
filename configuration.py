import os
from biliapis import bilicodes, requester, login
import logging
import colorama
import sys
from PIL import Image

# 这个文件叫 configuration 是因为主程序里已经有 config 这个变量了

development_mode = True

work_dir = os.getcwd()
user_name = os.getlogin()
version = "2.0.0_Dev17"

if sys.platform.startswith("win"):
    platform = "win"
    inner_data_path = os.path.join(os.environ["USERPROFILE"], ".bilitools")
    inner_data_path_legacy = os.path.join(os.environ["USERPROFILE"], "BiliTools")
elif sys.platform.startswith("linux"):
    platform = "linux"
    inner_data_path = os.path.join(os.environ["HOME"], ".bilitools")
    inner_data_path_legacy = os.path.join(os.environ["HOME"], "BiliTools")
else:
    raise AssertionError("Unknown platform...")
# if os.path.exists(inner_data_path_legacy) and not os.path.exists(inner_data_path):
#     os.rename(inner_data_path_legacy, inner_data_path)
requester.inner_data_path = inner_data_path
login.ref_token_path = inner_data_path

if not os.path.exists(inner_data_path):
    os.mkdir(inner_data_path)
config_path = os.path.join(inner_data_path, "config.json")
logging_path = os.path.join("./", "last_run.log")

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
    logging.DEBUG:      colorama.Fore.BLUE + "{}" + colorama.Fore.RESET,
    logging.INFO:       colorama.Fore.GREEN + "{}" + colorama.Fore.RESET,
    logging.WARNING:    colorama.Fore.YELLOW + "{}" + colorama.Fore.RESET,
    logging.ERROR:      colorama.Fore.RED + "{}" + colorama.Fore.RESET,
    logging.CRITICAL:   colorama.Fore.LIGHTRED_EX + "{}" + colorama.Fore.RESET,
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

if __name__ == "__main__":
    print("--- Logging Test ---")
    logging.debug("你是一个一个一个")
    logging.info("我是一个一个一个")
    logging.warning("他是一个一个一个")
    logging.error("Aughhhhhh")
    logging.critical("waaaaaaaaaaaagh")
