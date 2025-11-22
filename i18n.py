import json
import os
import database as db

# 全局变量存储翻译字典
_TRANSLATIONS = {}
CURRENT_LANG = "zh"


def load_language():
    """
    根据数据库设置加载对应的语言文件
    """
    global _TRANSLATIONS, CURRENT_LANG

    # 1. 从数据库获取语言设置，默认为中文
    lang_code = db.get_setting("language", "zh")
    CURRENT_LANG = lang_code

    # 2. 确定文件路径
    # 假设 lang 目录在当前文件同级
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "lang", f"{lang_code}.json")

    # 3. 加载 JSON
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                _TRANSLATIONS = json.load(f)
        else:
            print(f"⚠️ 语言文件不存在: {file_path}, 回退到空字典")
            _TRANSLATIONS = {}
    except Exception as e:
        print(f"❌ 加载语言失败: {e}")
        _TRANSLATIONS = {}


def get(key, **kwargs):
    """
    获取翻译文本，支持格式化参数
    用法: i18n.get("welcome_msg", name="User")
    """
    # 如果字典为空（还没初始化），尝试加载
    if not _TRANSLATIONS:
        load_language()

    text = _TRANSLATIONS.get(key, key)  # 如果找不到key，直接返回key本身

    if kwargs:
        try:
            return text.format(**kwargs)
        except:
            return text
    return text


# 模块加载时自动初始化一次
load_language()