import os
import platform
import shutil
import subprocess
from typing import List, Dict, Any, Optional
import tkinter as tk
from tkinter import filedialog

import gradio as gr

from common import logger_utils, database as db, i18n
from common.config import VALID_IMAGE_EXTENSIONS, UPLOAD_DIR


def open_folder_dialog() -> Optional[str]:
    """
    Opens a native folder selection dialog.
    Uses AppleScript on macOS to avoid threading issues with tkinter.
    Uses tkinter on other systems.
    """
    system_platform = platform.system()
    if system_platform == "Darwin":
        script = 'POSIX path of (choose folder with prompt "Please select a folder to process")'
        try:
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, check=False)
            return result.stdout.strip()
        except (subprocess.CalledProcessError, OSError) as e:
            logger_utils.log(f"Failed to open folder dialog using AppleScript: {e}")
            return None
    else:
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            folder_path = filedialog.askdirectory()
            root.destroy()
            return folder_path if folder_path else None
        except (tk.TclError, RuntimeError) as e:
            logger_utils.log(f"Failed to open folder dialog using tkinter: {e}")
            return None

def load_images_from_dir(dir_path: str, recursive: bool) -> tuple[List[str], str]:
    if not dir_path or not os.path.exists(dir_path):
        return [], i18n.get("logic_error_dirNotFound", path=dir_path)
    db.save_setting("last_dir", dir_path)
    
    image_files: List[str] = []
    if recursive:
        for root, _, files in os.walk(dir_path):
            for f in files:
                if os.path.splitext(f)[1].lower() in VALID_IMAGE_EXTENSIONS:
                    image_files.append(os.path.join(root, f))
    else:
        image_files = [os.path.join(dir_path, f) for f in os.listdir(dir_path)
                       if os.path.splitext(f)[1].lower() in VALID_IMAGE_EXTENSIONS]
                       
    msg: str = i18n.get("logic_log_loadDir", path=dir_path, count=len(image_files))
    logger_utils.log(msg)
    return image_files, msg

def handle_upload(files: List[str]) -> List[str]:
    if not files:
        return []
    saved_paths: List[str] = []
    for temp_path in files:
        if not temp_path:
            continue
        original_name: str = os.path.basename(temp_path)
        target_path: str = os.path.join(UPLOAD_DIR, original_name)
        try:
            shutil.copy(temp_path, target_path)
            saved_paths.append(target_path)
        except (IOError, OSError) as e:
            logger_utils.log(f"Failed to copy uploaded file: {e}")
    if saved_paths:
        logger_utils.log(f"Uploaded and saved {len(saved_paths)} files.")
    return saved_paths

def render_assets_block(prefix: str = "") -> Dict[str, gr.Component]:
    """
    渲染素材库 UI 块。
    prefix: 用于区分不同素材库组件的唯一前缀 (例如 "main_" 或 "chat_")
    """
    settings: Dict[str, Any] = db.get_all_settings()

    with gr.Group():
        gr.Markdown(f"#### {i18n.get('home_assets_title')}")
        with gr.Tabs():
            with gr.TabItem(i18n.get("home_assets_tab_local")):
                with gr.Row():
                    dir_input = gr.Textbox(value=settings["last_dir"], label=i18n.get("home_assets_label_dirPath"), scale=3, elem_id=f"{prefix}dir_input")
                    btn_select_dir = gr.Button(i18n.get("home_assets_btn_browse"), scale=0, min_width=50, elem_id=f"{prefix}btn_select_dir")
                    btn_refresh = gr.Button(i18n.get("home_assets_btn_refresh"), scale=0, min_width=50, elem_id=f"{prefix}btn_refresh")
                with gr.Row():
                    recursive_checkbox = gr.Checkbox(label=i18n.get("home_assets_label_recursive"), value=False, elem_id=f"{prefix}recursive_checkbox")
                    size_slider = gr.Slider(2, 6, value=4, step=1, label=i18n.get("home_assets_label_columns"), elem_id=f"{prefix}size_slider")
                gallery_source = gr.Gallery(label=i18n.get("home_assets_label_source"), columns=4, height="auto", allow_preview=False, object_fit="contain", elem_id=f"{prefix}gallery_source")
            
            with gr.TabItem(i18n.get("home_assets_tab_upload")):
                upload_button = gr.UploadButton(i18n.get("home_assets_btn_upload"), file_types=["image"], file_count="multiple", elem_id=f"{prefix}upload_button")
                gallery_upload = gr.Gallery(label="Uploaded", columns=4, height="auto", allow_preview=False, object_fit="contain", interactive=True, elem_id=f"{prefix}gallery_upload")

        info_box = gr.Markdown(i18n.get("home_assets_info_ready"), elem_id=f"{prefix}info_box")
        state_marked_for_add = gr.State(None) # 移除 elem_id

    return {
        f"{prefix}dir_input": dir_input,
        f"{prefix}btn_select_dir": btn_select_dir,
        f"{prefix}btn_refresh": btn_refresh,
        f"{prefix}recursive_checkbox": recursive_checkbox,
        f"{prefix}size_slider": size_slider,
        f"{prefix}gallery_source": gallery_source,
        f"{prefix}upload_button": upload_button,
        f"{prefix}gallery_upload": gallery_upload,
        f"{prefix}info_box": info_box,
        f"{prefix}state_marked_for_add": state_marked_for_add,
    }
