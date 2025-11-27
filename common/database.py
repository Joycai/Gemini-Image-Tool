import sqlite3

from common import logger_utils

DB_FILE = "../app_data.db"

def init_db():
    """初始化数据库表结构"""
    logger_utils.log("Initializing DB")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 1. 配置表
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)''')
    # 2. Prompt 表 (新增)
    c.execute('''CREATE TABLE IF NOT EXISTS prompts
                 (title TEXT PRIMARY KEY, content TEXT)''')
    conn.commit()
    conn.close()

# --- Settings 相关 ---
def get_setting(key, default=""):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else default

def save_setting(key, value):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_all_settings():
    return {
        "api_key": get_setting("api_key", ""),
        "last_dir": get_setting("last_dir", ""),
        "save_path": get_setting("save_path", "outputs"),
        "file_prefix": get_setting("file_prefix", "gemini_gen"),
        "language": get_setting("language", "zh") # ⬇️ 新增语言设置
    }

# --- Prompt 相关 (新增) ---
def save_prompt(title, content):
    if not title or not content:
        return False
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO prompts (title, content) VALUES (?, ?)", (title, content))
    conn.commit()
    conn.close()
    return True

def delete_prompt(title):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM prompts WHERE title=?", (title,))
    conn.commit()
    conn.close()

def get_prompt_content(title):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT content FROM prompts WHERE title=?", (title,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else ""

def get_all_prompt_titles():
    """获取所有 Prompt 标题列表，用于下拉框"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT title FROM prompts ORDER BY title")
    titles = [row[0] for row in c.fetchall()]
    conn.close()
    return ["---"] + titles # 添加默认空选项

def get_all_prompts_for_export():
    """获取所有 prompts 用于导出，返回字典列表"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT title, content FROM prompts ORDER BY title")
    prompts = [dict(row) for row in c.fetchall()]
    conn.close()
    return prompts

def import_prompts_from_list(prompts_list):
    """从字典列表导入 prompts，重复的标题将被覆盖"""
    if not prompts_list:
        return 0
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 将字典列表转换为元组列表
    data_to_insert = [(item.get('title'), item.get('content')) for item in prompts_list if item.get('title') and item.get('content')]
    c.executemany("INSERT OR REPLACE INTO prompts (title, content) VALUES (?, ?)", data_to_insert)
    count = len(data_to_insert)
    conn.commit()
    conn.close()
    return count

# 初始化
init_db()
