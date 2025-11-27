import sqlite3
import os
import json
from common import logger_utils

# Define the storage directory and database file path
STORAGE_DIR = "storage"
DB_FILE = os.path.join(STORAGE_DIR, "database.sqlite")

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
                 (title TEXT PRIMARY KEY, content TEXT)''')
    # Add default settings if needed
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ("language", "en"))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ("save_path", "outputs"))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ("file_prefix", "gemini_gen"))
    conn.commit()

def ensure_db_exists():
    """
    Ensures the database file and its directory exist.
    If the database file does not exist, it initializes it.
    """
    if not os.path.exists(DB_FILE):
        logger_utils.log(f"Database file not found at {DB_FILE}. Creating a new one.")
        try:
            os.makedirs(STORAGE_DIR, exist_ok=True)
            conn = get_db_connection()
            init_db(conn)
            conn.close()
            logger_utils.log("Database created and initialized successfully.")
        except Exception as e:
            logger_utils.log(f"FATAL: Could not create or initialize the database: {e}")
            raise

# --- Full Data Import/Export ---
def export_all_data():
    """Exports all settings and prompts into a single dictionary."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("SELECT key, value FROM settings")
    settings = [dict(row) for row in c.fetchall()]
    
    c.execute("SELECT title, content FROM prompts")
    prompts = [dict(row) for row in c.fetchall()]
    
    conn.close()
    
    return {"settings": settings, "prompts": prompts}

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
        
        # Insert new settings
        settings_to_insert = [(item.get('key'), item.get('value')) for item in data.get("settings", [])]
        c.executemany("INSERT INTO settings (key, value) VALUES (?, ?)", settings_to_insert)
        
        # Insert new prompts
        prompts_to_insert = [(item.get('title'), item.get('content')) for item in data.get("prompts", [])]
        c.executemany("INSERT INTO prompts (title, content) VALUES (?, ?)", prompts_to_insert)
        
        # Commit transaction
        conn.commit()
        logger_utils.log(f"Successfully imported {len(settings_to_insert)} settings and {len(prompts_to_insert)} prompts.")
        
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
        "language": get_setting("language", "en")
    }

# --- Prompt related ---
def save_prompt(title, content):
    if not title or not content:
        return False
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO prompts (title, content) VALUES (?, ?)", (title, content))
    conn.commit()
    conn.close()
    return True

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
    c.execute("SELECT title FROM prompts ORDER BY title")
    titles = [row[0] for row in c.fetchall()]
    conn.close()
    return titles

def get_all_prompts_for_export():
    """Gets all prompts for export, returns a list of dicts."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT title, content FROM prompts ORDER BY title")
    prompts = [dict(row) for row in c.fetchall()]
    conn.close()
    return prompts

def import_prompts_from_list(prompts_list):
    """Imports prompts from a list of dicts, overwriting duplicates."""
    if not prompts_list:
        return 0
    conn = get_db_connection()
    c = conn.cursor()
    data_to_insert = [(item.get('title'), item.get('content')) for item in prompts_list if item.get('title') and item.get('content')]
    c.executemany("INSERT OR REPLACE INTO prompts (title, content) VALUES (?, ?)", data_to_insert)
    count = len(data_to_insert)
    conn.commit()
    conn.close()
    return count

# --- Initialization ---
ensure_db_exists()
