import os
import platform
import subprocess

import gradio as gr

import database as db
import i18n
import logger_utils
from config import VALID_IMAGE_EXTENSIONS


# --- History Page Logic ---

def load_output_gallery():
    save_dir = db.get_setting("save_path")
    if not save_dir or not os.path.exists(save_dir):
        return []
    files = [os.path.join(save_dir, f) for f in os.listdir(save_dir)
             if os.path.splitext(f)[1].lower() in VALID_IMAGE_EXTENSIONS]
    files.sort(key=os.path.getmtime, reverse=True)
    return files

def open_output_folder():
    path = db.get_setting("save_path", "outputs")
    if not os.path.exists(path):
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            gr.Warning(i18n.get("logic_error_createDir", error=e))
            return
    abs_path = os.path.abspath(path)
    logger_utils.log(f"Attempting to open directory: {abs_path}")
    try:
        system_platform = platform.system()
        if system_platform == "Windows":
            os.startfile(abs_path)
        elif system_platform == "Darwin":
            subprocess.run(["open", abs_path], check=False)
        else:
            subprocess.run(["xdg-open", abs_path], check=False)
    except (OSError, FileNotFoundError) as e:
        err_msg = i18n.get("logic_error_openFolder", error=e)
        logger_utils.log(err_msg)
        gr.Warning(err_msg)

def on_gallery_select(evt: gr.SelectData, gallery_data):
    if not gallery_data or evt.index is None:
        return gr.update(interactive=False), gr.update(interactive=False), None
    try:
        selected_item = gallery_data[evt.index]
        temp_path = selected_item[0] if isinstance(selected_item, (list, tuple)) else selected_item
        
        if temp_path:
            filename = os.path.basename(temp_path)
            save_dir = db.get_setting("save_path", "outputs")
            real_path = os.path.abspath(os.path.join(save_dir, filename))
            final_path = real_path if os.path.exists(real_path) else temp_path
            
            return (
                gr.DownloadButton(value=final_path, label=f"{i18n.get('home_history_btn_download')} ({filename})", interactive=True),
                gr.Button(interactive=True),
                final_path
            )
    except (IndexError, KeyError) as e:
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
        except (OSError, IOError) as e:
            logger_utils.log(i18n.get("logic_error_deleteFailed", error=e))
            gr.Warning(i18n.get("logic_warn_deleteFailed", error=e))
    
    new_gallery = load_output_gallery()
    return (
        new_gallery,
        gr.DownloadButton(value=None, label=i18n.get("home_history_btn_download"), interactive=False),
        gr.Button(interactive=False)
    )

# --- UI Rendering ---

def render():
    with gr.Group():
        with gr.Row():
            gr.Markdown(f"## {i18n.get('home_history_title')}")
            btn_open_out_dir = gr.Button(i18n.get("home_history_btn_open"), scale=0, size="sm")
            btn_refresh_history = gr.Button("🔄", scale=0, size="sm")

        gallery_output_history = gr.Gallery(
            label="Outputs", columns=6, height="auto", allow_preview=True,
            interactive=False, object_fit="contain"
        )
        with gr.Row():
            btn_download_hist = gr.DownloadButton(i18n.get("home_history_btn_download"), size="sm", scale=1, interactive=False)
            btn_delete_hist = gr.Button(i18n.get("home_history_btn_delete"), size="sm", variant="stop", scale=1, interactive=False)
        
        state_hist_selected_path = gr.State(value=None)

    return {
        "gallery_output_history": gallery_output_history,
        "btn_open_out_dir": btn_open_out_dir,
        "btn_refresh_history": btn_refresh_history,
        "btn_download_hist": btn_download_hist,
        "btn_delete_hist": btn_delete_hist,
        "state_hist_selected_path": state_hist_selected_path
    }
