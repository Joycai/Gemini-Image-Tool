from typing import List, Tuple, Optional
import os
import time
import sys
import base64
import threading
import tkinter as tk
from tkinter import filedialog
import gradio as gr
import shutil

# 引入模块
import database as db
import api_client
import logger_utils
import i18n
import platform
import subprocess

from component import main_page
from config import VALID_IMAGE_EXTENSIONS, UPLOAD_DIR, OUTPUT_DIR
# from ticker import ticker_instance # 不再需要在这里导入

# --- 全局任务状态管理 ---
TASK_STATE = {
    "status": "idle",
    "timestamp": 0,
    "result_image": None,
    "result_path": None,
    "error_msg": None,
    "ui_updated": True
}


def reset_task_state():
    TASK_STATE["status"] = "idle"
    TASK_STATE["result_image"] = None
    TASK_STATE["result_path"] = None
    TASK_STATE["error_msg"] = None
    TASK_STATE["ui_updated"] = True


# --- 核心：后台任务线程函数 ---
def _background_worker(prompt, img_paths, key, model, ar, res):
    try:
        TASK_STATE["status"] = "running"
        TASK_STATE["ui_updated"] = False
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

        TASK_STATE["result_image"] = generated_image
        TASK_STATE["result_path"] = temp_path
        TASK_STATE["status"] = "success"

    except Exception as e:
        error_msg = str(e)
        logger_utils.log(i18n.get("logic_log_saveFail", err=error_msg))
        TASK_STATE["error_msg"] = error_msg
        TASK_STATE["status"] = "error"


def start_generation_task(prompt: str, img_paths: List[str], key: str, model: str, ar: str, res: str):
    if TASK_STATE["status"] == "running":
        gr.Warning(i18n.get("logic_warn_taskRunning"))
        return
    reset_task_state()
    t = threading.Thread(target=_background_worker, args=(prompt, img_paths, key, model, ar, res))
    t.start()
    gr.Info(i18n.get("logic_info_taskSubmitted"))


def poll_task_status_callback():
    # 状态1：任务正在运行，不需要更新 UI
    if TASK_STATE["status"] == "running":
        return gr.skip(), gr.skip()

    # 状态2：任务已完成，但 UI 尚未更新
    if not TASK_STATE["ui_updated"]:
        # 状态 2.1：任务成功
        if TASK_STATE["status"] == "success":
            TASK_STATE["ui_updated"] = True
            new_btn = gr.DownloadButton(
                label=i18n.get("logic_btn_downloadReady", filename=os.path.basename(TASK_STATE['result_path'])),
                value=TASK_STATE["result_path"],
                interactive=True,
                visible=True
            )
            return TASK_STATE["result_image"], new_btn
        
        # 状态 2.2：任务失败
        elif TASK_STATE["status"] == "error":
            TASK_STATE["ui_updated"] = True
            gr.Warning(i18n.get("logic_warn_taskFailed", error_msg=TASK_STATE['error_msg']))
            return None, gr.DownloadButton(label=i18n.get("home_preview_btn_download_placeholder"), interactive=False)

    # 状态3：其他情况（例如 idle 且 UI 已更新），不执行任何操作
    return gr.skip(), gr.skip()


def restart_app():
    logger_utils.log(i18n.get("logic_log_restarting"))
    time.sleep(0.5)
    python = sys.executable
    os.execl(python, python, *sys.argv)

def init_app_data():
    fresh_settings = db.get_all_settings()
    logger_utils.log(i18n.get("logic_log_resumingSession"))
    restored_image = None
    if TASK_STATE["status"] == "success" and TASK_STATE["result_path"]:
        current_download_btn = gr.DownloadButton(
            label=i18n.get("logic_btn_downloadReady_noFilename"),
            value=TASK_STATE["result_path"],
            interactive=True
        )
    else:
        current_download_btn = gr.DownloadButton(label=i18n.get("home_preview_btn_download_placeholder"), interactive=False)
    return (
        fresh_settings["last_dir"],
        fresh_settings["api_key"],
        current_download_btn,
        restored_image,
        fresh_settings["save_path"],
        fresh_settings["file_prefix"],
        fresh_settings["language"],
        fresh_settings["api_key"]
    )

# # 移除自动注册
# ticker_instance.register(_poll_task_status_callback)
