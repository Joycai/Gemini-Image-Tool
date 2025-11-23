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
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "lang", f"{lang_code}.json")

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