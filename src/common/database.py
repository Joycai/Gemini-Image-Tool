import os
import sqlite3
import json
from typing import List, Any, Optional, Dict

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
    # 5. Token Usage table
    c.execute('''CREATE TABLE IF NOT EXISTS token_usage
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  model_id TEXT, 
                  input_tokens INTEGER, 
                  output_tokens INTEGER, 
                  total_tokens INTEGER, 
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    # 6. Models table
    c.execute('''CREATE TABLE IF NOT EXISTS models
                 (id TEXT, series TEXT, tags TEXT, display_name TEXT, is_paid INTEGER DEFAULT 0, order_id INTEGER,
                  PRIMARY KEY (id, series))''')
    
    # 7. Model Prices table
    c.execute('''CREATE TABLE IF NOT EXISTS model_prices
                 (model_id TEXT PRIMARY KEY, input_price REAL, output_price REAL)''')
    
    # Add default settings
    default_settings = [
        ("language", "en"),
        ("save_path", "outputs"),
        ("file_prefix", "gemini_gen"),
        ("max_history_len", "20"),
        ("refine_model_id", "gemini-1.5-flash"),
        ("recognition_model_id", "gemini-1.5-flash"),
        ("google_use_paid_for_all", "0"),
        ("openai_base_url", "https://api.openai.com/v1")
    ]
    c.executemany("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", default_settings)
    
    # Add default models
    default_models = [
        ("gemini-2.0-flash-exp", "google-genai", "Image,Chat", "Gemini 2.0 Flash Exp", 0, 0),
        ("gemini-1.5-flash", "google-genai", "Chat", "Gemini 1.5 Flash", 0, 1),
        ("gemini-1.5-pro", "google-genai", "Chat", "Gemini 1.5 Pro", 1, 2),
        ("imagen-3", "google-genai", "Image", "Imagen 3", 1, 3),
        ("gpt-4o", "openai", "Chat", "GPT-4o", 1, 4),
        ("gpt-4o-mini", "openai", "Chat", "GPT-4o Mini", 0, 5),
        ("dall-e-3", "openai", "Image", "DALL-E 3", 1, 6)
    ]
    c.executemany("INSERT OR IGNORE INTO models (id, series, tags, display_name, is_paid, order_id) VALUES (?, ?, ?, ?, ?, ?)", default_models)

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
    
    # 1. Check for order_id in prompts
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

    # 2. Check for prompt_history table
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prompt_history'")
    if not c.fetchone():
        logger_utils.log("Migrating database: Creating prompt_history table.")
        c.execute('''CREATE TABLE prompt_history
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()

    # 3. Check for refine_tasks table
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='refine_tasks'")
    if not c.fetchone():
        logger_utils.log("Migrating database: Creating refine_tasks table.")
        c.execute('''CREATE TABLE refine_tasks
                     (id TEXT PRIMARY KEY, name TEXT, name_zh TEXT, system_instruction TEXT, order_id INTEGER)''')
        conn.commit()
        init_db(conn)

    # 4. Check for token_usage table
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='token_usage'")
    if not c.fetchone():
        logger_utils.log("Migrating database: Creating token_usage table.")
        c.execute('''CREATE TABLE token_usage
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      model_id TEXT, 
                      input_tokens INTEGER, 
                      output_tokens INTEGER, 
                      total_tokens INTEGER, 
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()

    # 5. Check for models table and its schema
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='models'")
    if not c.fetchone():
        logger_utils.log("Migrating database: Creating models table.")
        c.execute('''CREATE TABLE models
                     (id TEXT, series TEXT, tags TEXT, display_name TEXT, is_paid INTEGER DEFAULT 0, order_id INTEGER,
                      PRIMARY KEY (id, series))''')
        conn.commit()
        init_db(conn)
    else:
        c.execute("PRAGMA table_info(models)")
        cols = {row[1]: row for row in c.fetchall()}
        
        needs_recreate = False
        if "type" in cols:
            needs_recreate = True
        if "tags" not in cols:
            needs_recreate = True
        if "is_paid" not in cols:
            needs_recreate = True

        if needs_recreate:
            logger_utils.log("Migrating database: Updating models table schema (type -> tags, adding is_paid).")
            c.execute("CREATE TABLE models_new (id TEXT, series TEXT, tags TEXT, display_name TEXT, is_paid INTEGER DEFAULT 0, order_id INTEGER, PRIMARY KEY (id, series))")
            
            c.execute("SELECT * FROM models")
            old_rows = c.fetchall()
            for row in old_rows:
                m_id, m_series, m_type, m_display, m_order = row
                m_tag = m_type.capitalize() if m_type else "Chat"
                m_paid = 1 if "pro" in m_id.lower() or "dall-e" in m_id.lower() or "gpt-4" in m_id.lower() else 0
                c.execute("INSERT INTO models_new (id, series, tags, display_name, is_paid, order_id) VALUES (?, ?, ?, ?, ?, ?)",
                          (m_id, m_series, m_tag, m_display, m_paid, m_order))
            
            c.execute("DROP TABLE models")
            c.execute("ALTER TABLE models_new RENAME TO models")
            conn.commit()

    # 6. Check for model_prices table
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='model_prices'")
    if not c.fetchone():
        logger_utils.log("Migrating database: Creating model_prices table.")
        c.execute('''CREATE TABLE model_prices
                     (model_id TEXT PRIMARY KEY, input_price REAL, output_price REAL)''')
        conn.commit()

    # 7. Check for new settings
    new_defaults = [
        ("recognition_model_id", "gemini-1.5-flash"),
        ("google_use_paid_for_all", "0"),
        ("openai_base_url", "https://api.openai.com/v1")
    ]
    for key, val in new_defaults:
        c.execute("SELECT value FROM settings WHERE key=?", (key,))
        if not c.fetchone():
            c.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, val))
    
    conn.commit()


def ensure_db_exists():
    """
    Ensures the database file and its directory exist.
    If the database file does not exist, it initializes it.
    Also handles database migrations.
    """
    db_needs_init = not os.path.exists(DB_FILE)

    try:
        os.makedirs(STORAGE_DIR, exist_ok=True)
        conn = get_db_connection()

        if db_needs_init:
            logger_utils.log(f"Database file not found at {DB_FILE}. Creating a new one.")
            init_db(conn)
        else:
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

    c.execute("SELECT id, series, tags, display_name, is_paid, order_id FROM models ORDER BY order_id")
    models = [dict(row) for row in c.fetchall()]

    c.execute("SELECT model_id, input_price, output_price FROM model_prices")
    model_prices = [dict(row) for row in c.fetchall()]

    conn.close()

    return {
        "settings": settings, 
        "prompts": prompts, 
        "refine_tasks": refine_tasks, 
        "models": models,
        "model_prices": model_prices
    }

def import_all_data(data: dict):
    """Wipes and imports all settings and prompts from a dictionary."""
    conn = get_db_connection()
    c = conn.cursor()

    try:
        c.execute("BEGIN TRANSACTION")
        c.execute("DELETE FROM settings")
        c.execute("DELETE FROM prompts")
        c.execute("DELETE FROM refine_tasks")
        c.execute("DELETE FROM models")
        c.execute("DELETE FROM model_prices")

        settings_to_insert = [(item.get('key'), item.get('value')) for item in data.get("settings", [])]
        c.executemany("INSERT INTO settings (key, value) VALUES (?, ?)", settings_to_insert)

        prompts_to_insert = []
        for i, item in enumerate(data.get("prompts", [])):
            order_id = item.get('order_id', i)
            prompts_to_insert.append((item.get('title'), item.get('content'), order_id))
        c.executemany("INSERT INTO prompts (title, content, order_id) VALUES (?, ?, ?)", prompts_to_insert)

        refine_tasks_to_insert = []
        for i, item in enumerate(data.get("refine_tasks", [])):
            order_id = item.get('order_id', i)
            refine_tasks_to_insert.append((item.get('id'), item.get('name'), item.get('name_zh'), item.get('system_instruction'), order_id))
        c.executemany("INSERT INTO refine_tasks (id, name, name_zh, system_instruction, order_id) VALUES (?, ?, ?, ?, ?)", refine_tasks_to_insert)

        models_to_insert = []
        for i, item in enumerate(data.get("models", [])):
            order_id = item.get('order_id', i)
            models_to_insert.append((item.get('id'), item.get('series'), item.get('tags'), item.get('display_name'), item.get('is_paid', 0), order_id))
        c.executemany("INSERT INTO models (id, series, tags, display_name, is_paid, order_id) VALUES (?, ?, ?, ?, ?, ?)", models_to_insert)

        prices_to_insert = [(item.get('model_id'), item.get('input_price'), item.get('output_price')) for item in data.get("model_prices", [])]
        c.executemany("INSERT INTO model_prices (model_id, input_price, output_price) VALUES (?, ?, ?)", prices_to_insert)

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
        c.execute("DELETE FROM token_usage")
        c.execute("DELETE FROM models")
        c.execute("DELETE FROM model_prices")
        conn.commit()
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
        "google_paid_api_key": get_setting("api_key", ""),
        "google_free_api_key": get_setting("refine_api_key", ""),
        "google_use_paid_for_all": get_setting("google_use_paid_for_all", "0") == "1",
        "openai_api_key": get_setting("openai_api_key", ""),
        "openai_base_url": get_setting("openai_base_url", "https://api.openai.com/v1"),
        "refine_model_id": get_setting("refine_model_id", "gemini-1.5-flash"),
        "recognition_model_id": get_setting("recognition_model_id", "gemini-1.5-flash"),
        "language": get_setting("language", "en"),
        "save_path": get_setting("save_path", "outputs"),
        "file_prefix": get_setting("file_prefix", "gemini_gen"),
        "max_history_len": get_setting("max_history_len", "20"),
        "last_dir": get_setting("last_dir", ""),
        "last_prompt": get_setting("last_prompt", ""),
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

# --- Model related ---
def get_all_models():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, series, tags, display_name, is_paid, order_id FROM models ORDER BY order_id")
    models = [dict(row) for row in c.fetchall()]
    conn.close()
    return models

def get_models_by_tag(tag):
    """Filters models by a specific tag (e.g., 'Image' or 'Chat')."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, series, tags, display_name, is_paid, order_id FROM models WHERE tags LIKE ? ORDER BY order_id", (f'%{tag}%',))
    models = [dict(row) for row in c.fetchall()]
    conn.close()
    return models

def get_model(model_id, series=None):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if series:
        c.execute("SELECT id, series, tags, display_name, is_paid, order_id FROM models WHERE id=? AND series=?", (model_id, series))
    else:
        c.execute("SELECT id, series, tags, display_name, is_paid, order_id FROM models WHERE id=?", (model_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def save_model(model_id, series, tags, display_name, is_paid=0):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT MAX(order_id) FROM models")
    max_order = c.fetchone()[0]
    new_order = (max_order or 0) + 1
    c.execute("INSERT OR REPLACE INTO models (id, series, tags, display_name, is_paid, order_id) VALUES (?, ?, ?, ?, ?, ?)", 
              (model_id, series, tags, display_name, is_paid, new_order))
    conn.commit()
    conn.close()

def delete_model(model_id, series):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM models WHERE id=? AND series=?", (model_id, series))
    conn.commit()
    conn.close()

def update_model_order(ids_series: List[tuple]):
    """Updates the order of models based on a list of (id, series) tuples."""
    conn = get_db_connection()
    c = conn.cursor()
    for i, (m_id, m_series) in enumerate(ids_series):
        c.execute("UPDATE models SET order_id = ? WHERE id = ? AND series = ?", (i, m_id, m_series))
    conn.commit()
    conn.close()

# --- Model Price related ---
def save_model_price(model_id, input_price, output_price):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO model_prices (model_id, input_price, output_price) VALUES (?, ?, ?)",
              (model_id, input_price, output_price))
    conn.commit()
    conn.close()

def get_model_price(model_id):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT input_price, output_price FROM model_prices WHERE model_id=?", (model_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {"input_price": 0.0, "output_price": 0.0}

def get_all_model_prices():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM model_prices")
    prices = {row['model_id']: {"input": row['input_price'], "output": row['output_price']} for row in c.fetchall()}
    conn.close()
    return prices

# --- Prompt History related ---
def add_prompt_history(content):
    if not content:
        return
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO prompt_history (content) VALUES (?)", (content,))
    c.execute("SELECT value FROM settings WHERE key='max_history_len'")
    limit = int(c.fetchone()[0] or 20)
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

# --- Token Usage related ---
def add_token_usage(model_id, input_tokens, output_tokens):
    conn = get_db_connection()
    c = conn.cursor()
    total_tokens = input_tokens + output_tokens
    c.execute("INSERT INTO token_usage (model_id, input_tokens, output_tokens, total_tokens) VALUES (?, ?, ?, ?)",
              (model_id, input_tokens, output_tokens, total_tokens))
    conn.commit()
    conn.close()

def get_token_usage_summary(start_date=None, end_date=None):
    """Gets total token usage grouped by model, optionally filtered by date range."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    query = '''SELECT model_id, 
                        SUM(input_tokens) as total_input, 
                        SUM(output_tokens) as total_output, 
                        SUM(total_tokens) as total_all,
                        COUNT(*) as request_count
                 FROM token_usage'''
    
    params = []
    if start_date and end_date:
        query += " WHERE timestamp BETWEEN ? AND ?"
        params = [start_date, end_date]
    elif start_date:
        query += " WHERE timestamp >= ?"
        params = [start_date]
    elif end_date:
        query += " WHERE timestamp <= ?"
        params = [end_date]
        
    query += " GROUP BY model_id"
    
    c.execute(query, params)
    summary = [dict(row) for row in c.fetchall()]
    conn.close()
    return summary

def clear_token_usage(model_id=None, before_date=None):
    """Clears token usage data, optionally for a specific model or before a date."""
    conn = get_db_connection()
    c = conn.cursor()
    
    query = "DELETE FROM token_usage WHERE 1=1"
    params = []
    
    if model_id:
        query += " AND model_id=?"
        params.append(model_id)
        # Also delete price config if model is cleared
        c.execute("DELETE FROM model_prices WHERE model_id=?", (model_id,))
        
    if before_date:
        query += " AND timestamp < ?"
        params.append(before_date)
        
    c.execute(query, params)
    conn.commit()
    conn.close()

def get_recent_token_usage(limit=50):
    """Gets the most recent token usage entries."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM token_usage ORDER BY timestamp DESC LIMIT ?", (limit,))
    recent = [dict(row) for row in c.fetchall()]
    conn.close()
    return recent

# --- Initialization ---
ensure_db_exists()
