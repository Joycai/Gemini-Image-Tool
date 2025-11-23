import json
import os
import sys
import database as db

# 全局变量存储翻译字典
_TRANSLATIONS = {}
CURRENT_LANG = "zh"


# ⬇️ 新增：获取资源绝对路径的通用函数
def get_resource_path(relative_path):
    """
    获取资源的绝对路径
    兼容开发环境 (Dev) 和 PyInstaller 打包后的环境 (Frozen)
    """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后的临时目录
        base_path = sys._MEIPASS
    else:
        # 开发环境：当前文件所在目录的上一级（即项目根目录）
        # 假设 i18n.py 在根目录，如果不是，请调整这里的逻辑
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

def load_language():
    """
    根据数据库设置加载对应的语言文件
    """
    global _TRANSLATIONS, CURRENT_LANG

    # 1. 从数据库获取语言设置，默认为中文
    lang_code = db.get_setting("language", "zh")
    CURRENT_LANG = lang_code

    # 2. 确定文件路径
    # ⬇️ 修改点：使用新的路径获取函数
    # 之前是: file_path = os.path.join(base_dir, "lang", f"{lang_code}.json")
    file_path = get_resource_path(os.path.join("lang", f"{lang_code}.json"))

    # 3. 加载 JSON
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                _TRANSLATIONS = json.load(f)
        else:
            # print(f"⚠️ 语言文件不存在: {file_path}, 回退到空字典")
            _TRANSLATIONS = {}
    except Exception as e:
        print(f"❌ 加载语言失败: {e}")
        _TRANSLATIONS = {}


# ⬇️ 修复点：修改函数签名，增加 default 参数
def get(key, default=None, **kwargs):
    """
    获取翻译文本，支持默认值和格式化参数
    用法:
      1. i18n.get("key")
      2. i18n.get("key", "默认值")
      3. i18n.get("key", name="User")
    """
    # 如果字典为空（还没初始化），尝试加载
    if not _TRANSLATIONS:
        load_language()

    # 逻辑：
    # 1. 如果传了 default，没找到 key 就返回 default
    # 2. 如果没传 default，没找到 key 就返回 key 本身
    fallback = default if default is not None else key

    text = _TRANSLATIONS.get(key, fallback)

    if kwargs:
        try:
            return text.format(**kwargs)
        except:
            return text
    return text


# 模块加载时自动初始化一次
load_language()