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
from config import VALID_IMAGE_EXTENSIONS

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


# --- 辅助逻辑 ---
def open_folder_dialog():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    folder_path = filedialog.askdirectory()
    root.destroy()
    return folder_path


def load_images_from_dir(dir_path):
    if not dir_path or not os.path.exists(dir_path):
        return [], i18n.get("logic_error_dirNotFound", path=dir_path)
    db.save_setting("last_dir", dir_path)
    image_files = [os.path.join(dir_path, f) for f in os.listdir(dir_path)
                   if os.path.splitext(f)[1].lower() in VALID_IMAGE_EXTENSIONS]
    msg = i18n.get("logic_log_loadDir", path=dir_path, count=len(image_files))
    logger_utils.log(msg)
    return image_files, msg


def handle_upload(files):
    if not files:
        return []
    
    upload_dir = "tmp/upload"
    saved_paths = []
    for temp_path in files:
        if not temp_path:
            continue
            
        original_name = os.path.basename(temp_path)
        target_path = os.path.join(upload_dir, original_name)
        
        try:
            shutil.copy(temp_path, target_path)
            saved_paths.append(target_path)
        except Exception as e:
            logger_utils.log(f"Failed to copy uploaded file: {e}")

    if saved_paths:
        logger_utils.log(f"Uploaded and saved {len(saved_paths)} files.")
        
    return saved_paths


def load_output_gallery():
    save_dir = db.get_setting("save_path", "outputs")
    if not os.path.exists(save_dir):
        return []
    files = [os.path.join(save_dir, f) for f in os.listdir(save_dir)
             if os.path.splitext(f)[1].lower() in VALID_IMAGE_EXTENSIONS]
    files.sort(key=os.path.getmtime, reverse=True)
    return files


def get_disabled_download_html(text_key="home_preview_btn_download_placeholder"):
    text = i18n.get(text_key)
    return f"""
    <div style="text-align: center; margin-top: 10px;">
        <span style="display: inline-block; background-color: #f3f4f6; color: #9ca3af; border: 1px solid #e5e7eb; padding: 10px 20px; border-radius: 8px; font-weight: bold; font-family: sans-serif; cursor: not-allowed; user-select: none;">
        {text}
        </span>
    </div>
    """


def _generate_download_html(full_path):
    if not full_path or not os.path.exists(full_path):
        return get_disabled_download_html()

    filename = os.path.basename(full_path)

    try:
        with open(full_path, "rb") as f:
            image_data = f.read()
        b64_str = base64.b64encode(image_data).decode('utf-8')
        ext = os.path.splitext(filename)[1].lower().replace(".", "")
        if ext == "jpg": ext = "jpeg"
        mime_type = f"image/{ext}"
        href = f"data:{mime_type};base64,{b64_str}"
        btn_text = i18n.get("logic_btn_downloadReady", filename=filename)

        return f"""
        <div style="text-align: center; margin-top: 10px;">
            <a href="{href}" download="{filename}"
               style="display: inline-block; background-color: #2563eb; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: bold; font-family: sans-serif; box-shadow: 0 2px 4px rgba(0,0,0,0.2); cursor: pointer;">
               {btn_text}
            </a>
        </div>
        """
    except Exception as e:
        logger_utils.log(f"❌ HTML 生成失败: {e}")
        return get_disabled_download_html()


def _background_worker(prompt, img_paths, key, model, ar, res):
    try:
        TASK_STATE["status"] = "running"
        TASK_STATE["ui_updated"] = False
        logger_utils.log(i18n.get("logic_log_newTask"))
        generated_image = api_client.call_google_genai(prompt, img_paths, key, model, ar, res)
        save_dir = db.get_setting("save_path", "outputs")
        prefix = db.get_setting("file_prefix", "gemini_gen")
        os.makedirs(save_dir, exist_ok=True)
        timestamp = int(time.time())
        filename = f"{prefix}_{timestamp}.png"
        full_path = os.path.abspath(os.path.join(save_dir, filename))
        generated_image.save(full_path, format="PNG")
        logger_utils.log(i18n.get("logic_log_saveOk", path=filename))
        TASK_STATE["result_image"] = generated_image
        TASK_STATE["result_path"] = full_path
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


def poll_task_status():
    if TASK_STATE["status"] == "running":
        return gr.skip(), gr.DownloadButton(label=i18n.get("logic_log_newTask"), interactive=False), gr.skip()
    if not TASK_STATE["ui_updated"]:
        if TASK_STATE["status"] == "success":
            TASK_STATE["ui_updated"] = True
            new_btn = gr.DownloadButton(
                label=i18n.get("logic_btn_downloadReady", filename=os.path.basename(TASK_STATE['result_path'])),
                value=TASK_STATE["result_path"],
                interactive=True,
                visible=True
            )
            return TASK_STATE["result_image"], new_btn, load_output_gallery()
        elif TASK_STATE["status"] == "error":
            TASK_STATE["ui_updated"] = True
            gr.Warning(i18n.get("logic_warn_taskFailed", error_msg=TASK_STATE['error_msg']))
            return None, gr.DownloadButton(label=i18n.get("home_preview_btn_download_placeholder"), interactive=False), gr.skip()
    return gr.skip(), gr.skip(), gr.skip()


def refresh_prompt_dropdown():
    titles = db.get_all_prompt_titles()
    return gr.Dropdown(choices=titles, value=i18n.get("home_control_prompt_placeholder"))


def load_prompt_to_ui(selected_title):
    if not selected_title or selected_title == i18n.get("home_control_prompt_placeholder"):
        return gr.skip()
    logger_utils.log(i18n.get("logic_log_loadPrompt", title=selected_title))
    content = db.get_prompt_content(selected_title)
    return content


def save_prompt_to_db(title, content):
    if not title or not content:
        gr.Warning(i18n.get("logic_warn_promptEmpty"))
        return gr.skip()
    db.save_prompt(title, content)
    logger_utils.log(i18n.get("logic_log_savePrompt", title=title))
    gr.Info(i18n.get("logic_info_promptSaved", title=title))
    return refresh_prompt_dropdown()


def delete_prompt_from_db(selected_title):
    if not selected_title or selected_title == i18n.get("home_control_prompt_placeholder"):
        return gr.skip()
    db.delete_prompt(selected_title)
    logger_utils.log(i18n.get("logic_log_deletePrompt", title=selected_title))
    gr.Info(i18n.get("logic_info_promptDeleted", title=selected_title))
    return refresh_prompt_dropdown()


def mark_for_add(evt: gr.SelectData):
    if evt.value and isinstance(evt.value, dict) and 'image' in evt.value and 'path' in evt.value['image']:
        return evt.value['image']['path']
    return None

def mark_for_remove(evt: gr.SelectData):
    if evt.value and isinstance(evt.value, dict) and 'image' in evt.value and 'path' in evt.value['image']:
        return evt.value['image']['path']
    return None

def add_marked_to_selected(marked_path: str, current_selected: List[str]):
    if not marked_path:
        return current_selected
    if marked_path not in current_selected:
        new_selected = current_selected + [marked_path]
        if len(new_selected) > 5:
            new_selected = new_selected[-5:]
        logger_utils.log(i18n.get("logic_log_selectImage", name=os.path.basename(marked_path)))
        return new_selected
    return current_selected

def remove_marked_from_selected(marked_path: str, current_selected: List[str]):
    if not marked_path or marked_path not in current_selected:
        return current_selected
    new_list = [item for item in current_selected if item != marked_path]
    logger_utils.log(i18n.get("logic_log_removeImage", name=os.path.basename(marked_path), count=len(new_list)))
    return new_list


def restart_app():
    logger_utils.log(i18n.get("logic_log_restarting"))
    time.sleep(0.5)
    python = sys.executable
    os.execl(python, python, *sys.argv)


def save_cfg_wrapper(key, path, prefix, lang):
    db.save_setting("api_key", key)
    db.save_setting("save_path", path)
    db.save_setting("file_prefix", prefix)
    db.save_setting("language", lang)
    logger_utils.log(i18n.get("logic_info_configSaved"))
    gr.Info(i18n.get("logic_info_configSaved"))
    return key, load_output_gallery()


def open_output_folder():
    path = db.get_setting("save_path", "outputs")
    if not os.path.exists(path):
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as e:
            gr.Warning(i18n.get("logic_error_createDir", error=e))
            return
    abs_path = os.path.abspath(path)
    logger_utils.log(f"嘗試打開目錄: {abs_path}")
    try:
        system_platform = platform.system()
        if system_platform == "Windows":
            os.startfile(abs_path)
        elif system_platform == "Darwin":
            subprocess.run(["open", abs_path])
        else:
            subprocess.run(["xdg-open", abs_path])
    except Exception as e:
        err_msg = i18n.get("logic_error_openFolder", error=e)
        logger_utils.log(err_msg)
        gr.Warning(err_msg)


def on_gallery_select(evt: gr.SelectData, gallery_data):
    if not gallery_data or evt.index is None:
        return gr.update(interactive=False), gr.update(interactive=False), None
    try:
        selected_item = gallery_data[evt.index]
        temp_path = None
        if isinstance(selected_item, (list, tuple)):
            temp_path = selected_item[0]
        elif isinstance(selected_item, str):
            temp_path = selected_item
        elif hasattr(selected_item, "root") and hasattr(selected_item, "name"):
            temp_path = selected_item.path
        else:
            temp_path = selected_item.get("name") or selected_item.get("path")
        if temp_path:
            filename = os.path.basename(temp_path)
            save_dir = db.get_setting("save_path", "outputs")
            real_path = os.path.abspath(os.path.join(save_dir, filename))
            final_path = temp_path
            if os.path.exists(real_path):
                final_path = real_path
            else:
                logger_utils.log(i18n.get("logic_log_originalFileNotFound", path=real_path))
            return (
                gr.DownloadButton(value=final_path, label=i18n.get("home_history_btn_download") + f" ({filename})", interactive=True),
                gr.Button(interactive=True),
                final_path
            )
    except Exception as e:
        logger_utils.log(i18n.get("logic_error_gallerySelect", error=e))
    return gr.update(interactive=False), gr.update(interactive=False), None


def delete_output_file(file_path):
    if not file_path:
        gr.Warning(i18n.get("logic_warn_noImageSelected"))
        return gr.skip(), gr.skip(), gr.skip()
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger_utils.log(i18n.get("logic_log_deletedFile", path=file_path))
            gr.Info(i18n.get("logic_info_deleteSuccess"))
        except Exception as e:
            logger_utils.log(i18n.get("logic_error_deleteFailed", error=e))
            gr.Warning(i18n.get("logic_warn_deleteFailed", error=e))
    new_gallery = load_output_gallery()
    return (
        new_gallery,
        gr.DownloadButton(value=None, label=i18n.get("home_history_btn_download"), interactive=False),
        gr.Button(interactive=False)
    )


def init_app_data():
    fresh_settings = db.get_all_settings()
    logger_utils.log(i18n.get("logic_log_resumingSession"))
    current_html = get_disabled_download_html()
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