import os
import sqlite3
import json

from common import logger_utils
from common.config import DB_FILE, STORAGE_DIR


def get_db_connection():
    """Establishes a connection to the database."""
    return sqlite3.connect(DB_FILE)

def init_db(conn):
    """Initializes the database table structure."""
    logger_utils.log("Initializing new database schema.")
    c = conn.cursor()
    # 1. Settings table
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)''')
    # 2. Prompt table
    c.execute('''CREATE TABLE IF NOT EXISTS prompts
                 (title TEXT PRIMARY KEY, content TEXT, order_id INTEGER)''')
    # 3. Prompt History table
    c.execute('''CREATE TABLE IF NOT EXISTS prompt_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    # 4. Refine Tasks table
    c.execute('''CREATE TABLE IF NOT EXISTS refine_tasks
                 (id TEXT PRIMARY KEY, name TEXT, name_zh TEXT, system_instruction TEXT, order_id INTEGER)''')
    
    # Add default settings if needed
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ("language", "en"))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ("save_path", "outputs"))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ("file_prefix", "gemini_gen"))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ("max_history_len", "20"))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ("refine_model_id", "gemini-3-flash-preview"))
    
    # Add default refine tasks
    default_tasks = [
        ("cosplay_photo", "Cosplay Photo", "Cosplay 照片", 
         "You are a professional prompt engineer for the nanoBananaPro image generation system. Your task is to take a simple user idea and expand it into a highly detailed, structured, and artistic prompt for generating a realistic Cosplay photograph.\n\nOutput Format (STRICTLY FOLLOW THIS MARKDOWN STRUCTURE):\n**任务:**\n[Describe the core task]\n\n**模特设定:**\n+ [Detail 1]\n...\n\n**服装描述:**\n+ [Detail 1]\n...\n\n**场景和动作和镜头:**\n+ [Detail 1]\n...\n\n**镜头和光照:**\n+ [Detail 1]\n...\n\n**输出要求:**\n+ [Detail 1]\n...\n\nOutput ONLY the refined prompt text in the specified Markdown format.", 0),
        ("artistic_illustration", "Artistic Illustration", "艺术插画", 
         "You are a professional prompt engineer for the nanoBananaPro image generation system. Your task is to take a simple user idea and expand it into a detailed prompt for a high-quality artistic illustration. Focus on art style, brushwork, color palette, and composition.\n\nOutput Format:\n**Style:** [Style Name]\n**Subject:** [Detailed Subject Description]\n**Composition:** [Camera angle, framing]\n**Colors & Lighting:** [Palette and light source]\n**Details:** [Specific artistic elements]\n\nOutput ONLY the refined prompt text in Markdown format.", 1),
        ("product_photography", "Product Photography", "产品摄影", 
         "You are a professional prompt engineer for the nanoBananaPro image generation system. Your task is to expand a user idea into a professional product photography prompt. Focus on studio lighting, background textures, macro details, and commercial aesthetic.\n\nOutput Format:\n**Product:** [Detailed Product Description]\n**Setting:** [Background and environment]\n**Lighting:** [Studio light setup, shadows]\n**Camera:** [Lens, depth of field]\n\nOutput ONLY the refined prompt text in Markdown format.", 2),
        ("swap_clothes", "Swap Clothes", "更换服装", 
         "You are a professional prompt engineer for the nanoBananaPro image generation system. Your task is to create a precise prompt for a 'clothes swapping' operation. The user will provide two reference images: Image 1 (the target outfit) and Image 2 (the model/subject).\n\nOutput Format:\n**任务描述:**\n将{参考图2}中模特穿着的服装更换为{参考图1}的套装（包含所有配件和鞋子），不要保留任何图2模特穿着的服装和配件。\n\n**服装细节 (来自图1):**\n+ [Detailed description of style]\n+ [Detailed list of components]\n\n**保持一致 (来自图2):**\n+ 模特的动作和姿势与图2完全一致。\n+ 模特的部特征和表情与图2完全一致。\n+ 背景环境与图2保持一致。\n\n**生成要求:**\n+ 确保更换后的服装自然贴合模特的身体，层次结构正确。\n+ 发型可以根据需要进行微调以完美搭配头饰。\n\nOutput ONLY the refined prompt text in Markdown format.", 3)
    ]
    c.executemany("INSERT OR IGNORE INTO refine_tasks (id, name, name_zh, system_instruction, order_id) VALUES (?, ?, ?, ?, ?)", default_tasks)
    
    conn.commit()

def migrate_db(conn):
    """Migrates the database schema to the latest version."""
    c = conn.cursor()
    
    # Check for order_id in prompts
    c.execute("PRAGMA table_info(prompts)")
    columns = [row[1] for row in c.fetchall()]
    if "order_id" not in columns:
        logger_utils.log("Migrating database: Adding 'order_id' to prompts table.")
        c.execute("ALTER TABLE prompts ADD COLUMN order_id INTEGER")
        c.execute("SELECT title FROM prompts")
        titles = [row[0] for row in c.fetchall()]
        for i, title in enumerate(titles):
            c.execute("UPDATE prompts SET order_id = ? WHERE title = ?", (i, title))
        conn.commit()

    # Check for prompt_history table
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prompt_history'")
    if not c.fetchone():
        logger_utils.log("Migrating database: Creating prompt_history table.")
        c.execute('''CREATE TABLE prompt_history
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()

    # Check for refine_tasks table
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='refine_tasks'")
    if not c.fetchone():
        logger_utils.log("Migrating database: Creating refine_tasks table.")
        c.execute('''CREATE TABLE refine_tasks
                     (id TEXT PRIMARY KEY, name TEXT, name_zh TEXT, system_instruction TEXT, order_id INTEGER)''')
        conn.commit()
        # Re-run init to add defaults
        init_db(conn)
    else:
        # Check if swap_clothes exists
        c.execute("SELECT id FROM refine_tasks WHERE id='swap_clothes'")
        if not c.fetchone():
            logger_utils.log("Migrating database: Adding 'swap_clothes' task.")
            init_db(conn)

    # Check for max_history_len setting
    c.execute("SELECT value FROM settings WHERE key='max_history_len'")
    if not c.fetchone():
        c.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ("max_history_len", "20"))
        conn.commit()

    # Check for refine settings
    c.execute("SELECT value FROM settings WHERE key='refine_model_id'")
    if not c.fetchone():
        c.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ("refine_model_id", "gemini-3-flash-preview"))
        conn.commit()


def ensure_db_exists():
    """
    Ensures the database file and its directory exist.
    If the database file does not exist, it initializes it.
    Also handles database migrations.
    """
    db_needs_init = not os.path.exists(DB_FILE)

    try:
        # Use os.makedirs to create the full path, including intermediate directories
        os.makedirs(STORAGE_DIR, exist_ok=True)
        conn = get_db_connection()

        if db_needs_init:
            logger_utils.log(f"Database file not found at {DB_FILE}. Creating a new one.")
            init_db(conn)
            logger_utils.log("Database created and initialized successfully.")
        else:
            # Database exists, check for migrations
            migrate_db(conn)

        conn.close()
    except Exception as e:
        logger_utils.log(f"FATAL: Could not create, initialize, or migrate the database: {e}")
        raise


# --- Full Data Import/Export ---
def export_all_data():
    """Exports all settings and prompts into a single dictionary."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT key, value FROM settings")
    settings = [dict(row) for row in c.fetchall()]

    c.execute("SELECT title, content, order_id FROM prompts ORDER BY order_id")
    prompts = [dict(row) for row in c.fetchall()]

    c.execute("SELECT id, name, name_zh, system_instruction, order_id FROM refine_tasks ORDER BY order_id")
    refine_tasks = [dict(row) for row in c.fetchall()]

    conn.close()

    return {"settings": settings, "prompts": prompts, "refine_tasks": refine_tasks}

def import_all_data(data: dict):
    """Wipes and imports all settings and prompts from a dictionary."""
    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Start transaction
        c.execute("BEGIN TRANSACTION")

        # Wipe existing data
        c.execute("DELETE FROM settings")
        c.execute("DELETE FROM prompts")
        c.execute("DELETE FROM refine_tasks")

        # Insert new settings
        settings_to_insert = [(item.get('key'), item.get('value')) for item in data.get("settings", [])]
        c.executemany("INSERT INTO settings (key, value) VALUES (?, ?)", settings_to_insert)

        # Insert new prompts
        prompts_to_insert = []
        for i, item in enumerate(data.get("prompts", [])):
            order_id = item.get('order_id', i)
            prompts_to_insert.append((item.get('title'), item.get('content'), order_id))
        c.executemany("INSERT INTO prompts (title, content, order_id) VALUES (?, ?, ?)", prompts_to_insert)

        # Insert new refine tasks
        refine_tasks_to_insert = []
        for i, item in enumerate(data.get("refine_tasks", [])):
            order_id = item.get('order_id', i)
            refine_tasks_to_insert.append((item.get('id'), item.get('name'), item.get('name_zh'), item.get('system_instruction'), order_id))
        c.executemany("INSERT INTO refine_tasks (id, name, name_zh, system_instruction, order_id) VALUES (?, ?, ?, ?, ?)", refine_tasks_to_insert)

        # Commit transaction
        conn.commit()
        logger_utils.log(f"Successfully imported data.")

    except Exception as e:
        conn.rollback()
        logger_utils.log(f"Data import failed: {e}")
        raise
    finally:
        conn.close()

def clear_all_data():
    """Wipes all data from the database and re-initializes it."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("BEGIN TRANSACTION")
        c.execute("DELETE FROM settings")
        c.execute("DELETE FROM prompts")
        c.execute("DELETE FROM prompt_history")
        c.execute("DELETE FROM refine_tasks")
        conn.commit()
        # After clearing, re-initialize with default values
        init_db(conn)
        logger_utils.log("Successfully cleared all data from the database.")
    except Exception as e:
        conn.rollback()
        logger_utils.log(f"Data clearing failed: {e}")
        raise
    finally:
        conn.close()

# --- Settings related ---
def get_setting(key, default=""):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else default

def save_setting(key, value):
    conn = get_db_connection()
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
        "language": get_setting("language", "en"),
        "max_history_len": get_setting("max_history_len", "20"),
        "last_prompt": get_setting("last_prompt", ""),
        "refine_api_key": get_setting("refine_api_key", ""),
        "refine_model_id": get_setting("refine_model_id", "gemini-3-flash-preview")
    }

# --- Prompt related ---
def save_prompt(title, content):
    if not title or not content:
        return False
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT MAX(order_id) FROM prompts")
    max_order = c.fetchone()[0]
    new_order = (max_order or 0) + 1
    c.execute("INSERT OR REPLACE INTO prompts (title, content, order_id) VALUES (?, ?, ?)", (title, content, new_order))
    conn.commit()
    conn.close()
    return True

def update_prompt(old_title, new_title, new_content):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE prompts SET title = ?, content = ? WHERE title = ?", (new_title, new_content, old_title))
    conn.commit()
    conn.close()

def update_prompt_order(titles):
    conn = get_db_connection()
    c = conn.cursor()
    for i, title in enumerate(titles):
        c.execute("UPDATE prompts SET order_id = ? WHERE title = ?", (i, title))
    conn.commit()
    conn.close()

def delete_prompt(title):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM prompts WHERE title=?", (title,))
    conn.commit()
    conn.close()

def get_prompt_content(title):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT content FROM prompts WHERE title=?", (title,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else ""

def get_all_prompt_titles():
    """Gets all Prompt titles for dropdowns."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT title FROM prompts ORDER BY order_id")
    titles = [row[0] for row in c.fetchall()]
    conn.close()
    return titles

def get_all_prompts():
    """Gets all prompts, returns a list of dicts."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT title, content, order_id FROM prompts ORDER BY order_id")
    prompts = [dict(row) for row in c.fetchall()]
    conn.close()
    return prompts

# --- Refine Task related ---
def get_all_refine_tasks():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, name, name_zh, system_instruction, order_id FROM refine_tasks ORDER BY order_id")
    tasks = [dict(row) for row in c.fetchall()]
    conn.close()
    return tasks

def get_refine_task(task_id):
    """Gets a specific refine task by ID."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, name, name_zh, system_instruction, order_id FROM refine_tasks WHERE id=?", (task_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def save_refine_task(task_id, name, name_zh, system_instruction):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT MAX(order_id) FROM refine_tasks")
    max_order = c.fetchone()[0]
    new_order = (max_order or 0) + 1
    c.execute("INSERT OR REPLACE INTO refine_tasks (id, name, name_zh, system_instruction, order_id) VALUES (?, ?, ?, ?, ?)", 
              (task_id, name, name_zh, system_instruction, new_order))
    conn.commit()
    conn.close()

def update_refine_task(task_id, name, name_zh, system_instruction):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE refine_tasks SET name = ?, name_zh = ?, system_instruction = ? WHERE id = ?", 
              (name, name_zh, system_instruction, task_id))
    conn.commit()
    conn.close()

def delete_refine_task(task_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM refine_tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()

def update_refine_task_order(ids):
    conn = get_db_connection()
    c = conn.cursor()
    for i, task_id in enumerate(ids):
        c.execute("UPDATE refine_tasks SET order_id = ? WHERE id = ?", (i, task_id))
    conn.commit()
    conn.close()

# --- Prompt History related ---
def add_prompt_history(content):
    if not content:
        return
    conn = get_db_connection()
    c = conn.cursor()
    
    # Insert new history
    c.execute("INSERT INTO prompt_history (content) VALUES (?)", (content,))
    
    # Get limit
    c.execute("SELECT value FROM settings WHERE key='max_history_len'")
    limit = int(c.fetchone()[0] or 20)
    
    # Delete old history exceeding limit
    c.execute("DELETE FROM prompt_history WHERE id NOT IN (SELECT id FROM prompt_history ORDER BY timestamp DESC LIMIT ?)", (limit,))
    
    conn.commit()
    conn.close()

def get_prompt_history():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT content FROM prompt_history ORDER BY timestamp DESC")
    history = [row[0] for row in c.fetchall()]
    conn.close()
    return history

# --- Initialization ---
ensure_db_exists()
