import json
import os
import sys

from common import database as db

# 全局变量存储翻译字典
_TRANSLATIONS = {}
CURRENT_LANG = "zh"


def get_resource_path(relative_path):
    """
    获取资源的绝对路径
    兼容开发环境 (Dev) 和 PyInstaller 打包后的环境 (Frozen)
    """
    if hasattr(sys, '_MEIPASS'): # pylint: disable=protected-access
        base_path = sys._MEIPASS # pylint: disable=protected-access
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

def load_language():
    """
    根据数据库设置加载对应的语言文件
    """
    global _TRANSLATIONS # pylint: disable=global-statement
    global CURRENT_LANG # pylint: disable=global-statement

    lang_code = db.get_setting("language", "zh")
    CURRENT_LANG = lang_code

    file_path = get_resource_path(os.path.join("../lang", f"{lang_code}.json"))

    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                _TRANSLATIONS = json.load(f)
        else:
            _TRANSLATIONS = {}
    except (IOError, OSError, json.JSONDecodeError) as e:
        print(f"❌ Failed to load language: {e}")
        _TRANSLATIONS = {}


def get(key, default=None, **kwargs):
    """
    获取翻译文本，支持默认值和格式化参数
    """
    if not _TRANSLATIONS:
        load_language()

    fallback = default if default is not None else key

    text = _TRANSLATIONS.get(key, fallback)

    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError: # 捕获更具体的 KeyError
            return text
    return text

def get_translated_choices(keys):
    """
    获取翻译后的选项列表，用于 gr.Dropdown 的 choices。
    返回一个 (显示文本, 内部值) 的元组列表。
    如果一个 key 没有翻译，显示文本将是 key 本身。
    """
    return [(get(key), key) for key in keys]

# 模块加载时自动初始化一次
load_language()
