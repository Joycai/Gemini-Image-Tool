import os
import shutil
import sys
import threading
import time
from typing import List, Any

import gradio as gr
from PIL import Image
from google import genai

import api_client
# 引入模块
import database as db
import i18n
import logger_utils
from config import OUTPUT_DIR

# --- 主生成任务状态 ---
TASK_STATE = {
    "status": "idle", "result_image": None, "result_path": None, 
    "error_msg": None, "ui_updated": True
}

# --- 聊天任务状态 ---
CHAT_TASK_STATE = {
    "status": "idle", "response_parts": None, "updated_session": None,
    "error_msg": None, "ui_updated": True
}

def reset_task_state():
    TASK_STATE.update({
        "status": "idle", "result_image": None, "result_path": None, 
        "error_msg": None, "ui_updated": True
    })

def reset_chat_task_state():
    CHAT_TASK_STATE.update({
        "status": "idle", "response_parts": None, "updated_session": None,
        "error_msg": None, "ui_updated": True
    })

# --- 主生成任务 ---
def _background_worker(prompt, img_paths, key, model, ar, res):
    try:
        TASK_STATE.update({"status": "running", "ui_updated": False})
        logger_utils.log(i18n.get("logic_log_newTask"))
        generated_image = api_client.call_google_genai(prompt, img_paths, key, model, ar, res)
        
        prefix = db.get_setting("file_prefix", "gemini_gen")
        timestamp = int(time.time())
        filename = f"{prefix}_{timestamp}.png"
        temp_path = os.path.abspath(os.path.join(OUTPUT_DIR, filename))
        generated_image.save(temp_path, format="PNG")
        logger_utils.log(f"Saved to temp: {temp_path}")

        permanent_dir = db.get_setting("save_path")
        if permanent_dir:
            try:
                os.makedirs(permanent_dir, exist_ok=True)
                permanent_path = os.path.abspath(os.path.join(permanent_dir, filename))
                shutil.copy(temp_path, permanent_path)
                logger_utils.log(i18n.get("logic_log_saveOk", path=permanent_path))
            except Exception as e:
                logger_utils.log(f"Failed to copy to permanent storage: {e}")

        TASK_STATE.update({"result_image": generated_image, "result_path": temp_path, "status": "success"})
    except Exception as e:
        error_msg = str(e)
        logger_utils.log(i18n.get("logic_log_saveFail", err=error_msg))
        TASK_STATE.update({"error_msg": error_msg, "status": "error"})

def start_generation_task(prompt: str, img_paths: List[str], key: str, model: str, ar: str, res: str):
    if TASK_STATE["status"] == "running":
        gr.Warning(i18n.get("logic_warn_taskRunning"))
        return
    reset_task_state()
    t = threading.Thread(target=_background_worker, args=(prompt, img_paths, key, model, ar, res))
    t.start()
    gr.Info(i18n.get("logic_info_taskSubmitted"))

def poll_task_status_callback():
    if TASK_STATE["status"] == "running" or TASK_STATE["ui_updated"]:
        return gr.skip(), gr.skip()

    if TASK_STATE["status"] == "success":
        TASK_STATE["ui_updated"] = True
        new_btn = gr.DownloadButton(
            label=i18n.get("logic_btn_downloadReady", filename=os.path.basename(TASK_STATE['result_path'])),
            value=TASK_STATE["result_path"], interactive=True, visible=True
        )
        return TASK_STATE["result_image"], new_btn
    elif TASK_STATE["status"] == "error":
        TASK_STATE["ui_updated"] = True
        gr.Warning(i18n.get("logic_warn_taskFailed", error_msg=TASK_STATE['error_msg']))
        return None, gr.DownloadButton(label=i18n.get("home_preview_btn_download_placeholder"), interactive=False)
    
    return gr.skip(), gr.skip()

# --- 聊天任务 ---
def _chat_background_worker(genai_client, session_state, chat_input, model, ar, res):
    try:
        CHAT_TASK_STATE.update({"status": "running", "ui_updated": False})
        
        # 解包会话状态
        session_obj = session_state["session_obj"] if session_state else None
        session_id = session_state["id"] if session_state else f"chat_{int(time.time())}"

        prompt_parts: List[Any] = []
        if chat_input.get('files'):
            for file_path in chat_input['files']:
                prompt_parts.append(Image.open(file_path))
        if chat_input.get('text'):
            prompt_parts.append(chat_input['text'])

        updated_chat_obj, response_parts = api_client.call_google_chat(
            genai_client, session_obj, prompt_parts, model, ar, res
        )
        
        # 重新打包会话状态字典
        new_session_state = {"id": session_id, "session_obj": updated_chat_obj}

        CHAT_TASK_STATE.update({
            "status": "success",
            "response_parts": response_parts,
            "updated_session": new_session_state
        })
    except Exception as e:
        error_msg = str(e)
        logger_utils.log(f"❌ Chat failed: {error_msg}")
        CHAT_TASK_STATE.update({"status": "error", "error_msg": error_msg})

def start_chat_task(chat_input, genai_client, session_state, model, ar, res):
    if CHAT_TASK_STATE["status"] == "running":
        gr.Warning(i18n.get("logic_warn_taskRunning"))
        return
    reset_chat_task_state()
    t = threading.Thread(target=_chat_background_worker, args=(genai_client, session_state, chat_input, model, ar, res))
    t.start()

def poll_chat_task_status_callback():
    if CHAT_TASK_STATE["status"] == "running" or CHAT_TASK_STATE["ui_updated"]:
        return gr.skip(), gr.skip(), gr.skip(), gr.skip()

    CHAT_TASK_STATE["ui_updated"] = True
    if CHAT_TASK_STATE["status"] == "success":
        return CHAT_TASK_STATE["response_parts"], CHAT_TASK_STATE["updated_session"], gr.update(interactive=True), gr.update(interactive=True)
    elif CHAT_TASK_STATE["status"] == "error":
        gr.Warning(i18n.get("logic_warn_taskFailed", error_msg=CHAT_TASK_STATE['error_msg']))
        # 返回 None 以触发 handle_bot_response 中的错误处理
        return None, None, gr.update(interactive=True), gr.update(interactive=True)
    
    return gr.skip(), gr.skip(), gr.skip(), gr.skip()

# --- 通用函数 ---
def restart_app():
    logger_utils.log(i18n.get("logic_log_restarting"))
    time.sleep(0.5)
    python = sys.executable
    os.execl(python, python, *sys.argv)

def create_genai_client(api_key):
    if not api_key: return None
    try:
        return genai.Client(api_key=api_key)
    except Exception as e:
        logger_utils.log(f"Failed to create GenAI Client: {e}")
        return None

def init_app_data():
    fresh_settings = db.get_all_settings()
    api_key = fresh_settings["api_key"]
    genai_client = create_genai_client(api_key)
    
    logger_utils.log(i18n.get("logic_log_resumingSession"))
    restored_image = None
    if TASK_STATE["status"] == "success" and TASK_STATE["result_path"]:
        current_download_btn = gr.DownloadButton(
            label=i18n.get("logic_btn_downloadReady_noFilename"),
            value=TASK_STATE["result_path"], interactive=True
        )
    else:
        current_download_btn = gr.DownloadButton(label=i18n.get("home_preview_btn_download_placeholder"), interactive=False)
    
    return (
        fresh_settings["last_dir"], api_key, genai_client, current_download_btn,
        restored_image, fresh_settings["save_path"], fresh_settings["file_prefix"],
        fresh_settings["language"], api_key
    )
