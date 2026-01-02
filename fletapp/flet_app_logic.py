import asyncio  # Import asyncio for sleep
import os
import shutil
import sys
import threading
import time
from typing import List, Optional, Any

import flet as ft
from PIL import Image
from google import genai

from common import logger_utils, database as db, i18n
from common.config import OUTPUT_DIR
# 引入模块
from geminiapi import api_client

# --- 主生成任务状态 ---
TASK_STATE = {
    "status": "idle", "result_image": None, "result_path": None,
    "error_msg": None, "ui_updated": True, "download_btn_props": None
}

# --- 聊天任务状态 ---
CHAT_TASK_STATE = {
    "status": "idle", "response_parts": None, "updated_session": None,
    "error_msg": None, "ui_updated": True, "chat_input_disabled": False,
    "chat_attach_btn_disabled": False, "chat_send_btn_disabled": False
}

# --- Flet Page References (to allow background threads and periodic updates to interact with UI) ---
_FLET_PAGE_REF: Optional[ft.Page] = None
_MAIN_PAGE_REF: Optional[Any] = None  # Will hold FletMainPage instance
_CHAT_PAGE_REF: Optional[Any] = None  # Will hold FletChatPage instance


def set_flet_page_ref(page: ft.Page):
    global _FLET_PAGE_REF  # pylint: disable=global-statement
    _FLET_PAGE_REF = page


def set_main_page_ref(main_page_instance: Any):
    global _MAIN_PAGE_REF  # pylint: disable=global-statement
    _MAIN_PAGE_REF = main_page_instance


def set_chat_page_ref(chat_page_instance: Any):
    global _CHAT_PAGE_REF  # pylint: disable=global-statement
    _CHAT_PAGE_REF = chat_page_instance


def reset_task_state():
    TASK_STATE.update({
        "status": "idle", "result_image": None, "result_path": None,
        "error_msg": None, "ui_updated": True, "download_btn_props": None
    })


def reset_chat_task_state():
    CHAT_TASK_STATE.update({
        "status": "idle", "response_parts": None, "updated_session": None,
        "error_msg": None, "ui_updated": True, "chat_input_disabled": False,
        "chat_attach_btn_disabled": False, "chat_send_btn_disabled": False
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
        os.makedirs(OUTPUT_DIR, exist_ok=True)  # Ensure OUTPUT_DIR exists
        generated_image.save(temp_path, format="PNG")
        logger_utils.log(f"Saved to temp: {temp_path}")

        permanent_dir = db.get_setting("save_path")
        if permanent_dir:
            try:
                os.makedirs(permanent_dir, exist_ok=True)
                permanent_path = os.path.abspath(os.path.join(permanent_dir, filename))
                shutil.copy(temp_path, permanent_path)
                logger_utils.log(i18n.get("logic_log_saveOk", path=permanent_path))
            except (IOError, OSError) as e:
                logger_utils.log(f"Failed to copy to permanent storage: {e}")

        TASK_STATE.update({
            "result_image": generated_image,
            "result_path": temp_path,
            "status": "success",
            "download_btn_props": {
                "label": i18n.get("logic_btn_downloadReady", filename=os.path.basename(temp_path)),
                "value": temp_path,
                "interactive": True
            }
        })
    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = str(e)
        logger_utils.log(i18n.get("logic_log_saveFail", err=error_msg))
        TASK_STATE.update({
            "error_msg": error_msg,
            "status": "error",
            "download_btn_props": {
                "label": i18n.get("home_preview_btn_download_placeholder"),
                "value": None,
                "interactive": False
            }
        })
    finally:
        TASK_STATE["ui_updated"] = False  # Mark for UI update


def start_generation_task(prompt: str, img_paths: List[str], key: str, model: str, ar: str, res: str):
    if TASK_STATE["status"] == "running":
        if _FLET_PAGE_REF:
            _FLET_PAGE_REF.snack_bar = ft.SnackBar(ft.Text(i18n.get("logic_warn_taskRunning")), open=True)
            _FLET_PAGE_REF.update()
        return
    reset_task_state()
    t = threading.Thread(target=_background_worker, args=(prompt, img_paths, key, model, ar, res))
    t.start()
    if _FLET_PAGE_REF:
        _FLET_PAGE_REF.snack_bar = ft.SnackBar(ft.Text(i18n.get("logic_info_taskSubmitted")), open=True)
        _FLET_PAGE_REF.update()


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
    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = str(e)
        logger_utils.log(f"❌ Chat failed: {error_msg}")
        CHAT_TASK_STATE.update({"status": "error", "error_msg": error_msg})
    finally:
        CHAT_TASK_STATE["ui_updated"] = False  # Mark for UI update


def start_chat_task(chat_input, genai_client, session_state, model, ar, res):
    if CHAT_TASK_STATE["status"] == "running":
        if _FLET_PAGE_REF:
            _FLET_PAGE_REF.snack_bar = ft.SnackBar(ft.Text(i18n.get("logic_warn_taskRunning")), open=True)
            _FLET_PAGE_REF.update()
        return
    reset_chat_task_state()
    t = threading.Thread(target=_chat_background_worker, args=(genai_client, session_state, chat_input, model, ar, res))
    t.start()


# --- Flet UI Update Polling ---
async def poll_flet_ui_updates(interval: float = 0.5):
    while True:
        if _FLET_PAGE_REF is None:
            await asyncio.sleep(interval)
            continue

        # Update Main Page (Generation Task)
        if not TASK_STATE["ui_updated"]:
            if TASK_STATE["status"] == "success":
                if _MAIN_PAGE_REF:
                    _MAIN_PAGE_REF.result_image.src = TASK_STATE["result_path"]
                    _MAIN_PAGE_REF.btn_download.text = TASK_STATE["download_btn_props"]["label"]
                    _MAIN_PAGE_REF.btn_download.disabled = not TASK_STATE["download_btn_props"]["interactive"]
                    _MAIN_PAGE_REF.update()  # Update the parent custom control
                    # Trigger history page refresh
                    if _FLET_PAGE_REF.controls and isinstance(_FLET_PAGE_REF.controls[0], ft.Tabs):
                        history_tab_content = _FLET_PAGE_REF.controls[0].tabs[
                            2].content  # Assuming history is the 3rd tab
                        if history_tab_content and hasattr(history_tab_content, 'refresh_history_handler'):
                            # Call the handler directly, it will update its own controls
                            history_tab_content.refresh_history_handler(None)
                TASK_STATE["ui_updated"] = True
            elif TASK_STATE["status"] == "error":
                if _FLET_PAGE_REF:
                    _FLET_PAGE_REF.snack_bar = ft.SnackBar(ft.Text(
                        i18n.get("logic_warn_taskFailed", error_msg=TASK_STATE['error_msg'])), open=True)
                    _FLET_PAGE_REF.update()
                if _MAIN_PAGE_REF:
                    _MAIN_PAGE_REF.btn_download.text = TASK_STATE["download_btn_props"]["label"]
                    _MAIN_PAGE_REF.btn_download.disabled = not TASK_STATE["download_btn_props"]["interactive"]
                    _MAIN_PAGE_REF.update()  # Update the parent custom control
                TASK_STATE["ui_updated"] = True

        # Update Chat Page (Chat Task)
        if not CHAT_TASK_STATE["ui_updated"]:
            if CHAT_TASK_STATE["status"] == "success":
                if _CHAT_PAGE_REF:
                    _CHAT_PAGE_REF.handle_bot_response_update_ui(
                        CHAT_TASK_STATE["response_parts"],
                        CHAT_TASK_STATE["updated_session"]
                    )
                CHAT_TASK_STATE["ui_updated"] = True
            elif CHAT_TASK_STATE["status"] == "error":
                if _FLET_PAGE_REF:
                    _FLET_PAGE_REF.snack_bar = ft.SnackBar(ft.Text(
                        i18n.get("logic_warn_taskFailed", error_msg=CHAT_TASK_STATE['error_msg'])), open=True)
                    _FLET_PAGE_REF.update()
                if _CHAT_PAGE_REF:
                    _CHAT_PAGE_REF.handle_bot_response_update_ui(None, None)  # Trigger error handling in UI
                CHAT_TASK_STATE["ui_updated"] = True

            # Always re-enable chat input after task completion (success or error)
            if CHAT_TASK_STATE["status"] != "running" and _CHAT_PAGE_REF:
                _CHAT_PAGE_REF.chat_input_field.disabled = False
                _CHAT_PAGE_REF.chat_attach_button.disabled = False
                _CHAT_PAGE_REF.chat_send_button.disabled = False
                _CHAT_PAGE_REF.update()  # Update the parent custom control

        # Update Log Output
        if _MAIN_PAGE_REF:
            logs = logger_utils.get_logs()
            if _MAIN_PAGE_REF.log_output.value != logs:  # Only update if logs have changed
                _MAIN_PAGE_REF.log_output.value = logs
                _MAIN_PAGE_REF.update()  # Update the parent custom control

        await asyncio.sleep(interval)


# --- 通用函数 ---
def restart_app():
    logger_utils.log(i18n.get("logic_log_restarting"))
    time.sleep(0.5)
    python = sys.executable
    os.execl(python, python, *sys.argv)


def create_genai_client(api_key):
    if not api_key:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger_utils.log(f"Failed to create GenAI Client: {e}")
        return None


def init_app_data():
    fresh_settings = db.get_all_settings()
    api_key = fresh_settings["api_key"]
    genai_client = create_genai_client(api_key)

    logger_utils.log(i18n.get("logic_log_resumingSession"))

    # Initial download button state
    current_download_btn_props = {
        "label": i18n.get("home_preview_btn_download_placeholder"),
        "value": None,
        "interactive": False
    }
    if TASK_STATE["status"] == "success" and TASK_STATE["result_path"]:
        current_download_btn_props = {
            "label": i18n.get("logic_btn_downloadReady_noFilename"),
            "value": TASK_STATE["result_path"],
            "interactive": True
        }

    return (
        fresh_settings["last_dir"], api_key, genai_client, current_download_btn_props,
        None,  # restored_image (Flet doesn't need this directly in init)
        fresh_settings["save_path"], fresh_settings["file_prefix"],
        fresh_settings["language"], api_key
    )
