import os
import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RESOURCES_DIR = os.path.join(BASE_DIR, "resources")
LOGO_PATH = os.path.join(RESOURCES_DIR, "logo.png")
SUPPORT_LIST_FILE = os.path.join(RESOURCES_DIR, "supported_m3u8_list.txt")

DEFAULT_MAX_WORKERS = 8
DEFAULT_LOG_UPDATE_FREQ = 5

DEFAULT_WINDOW_X = 800
DEFAULT_WINDOW_Y = 400
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 1000

def resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)