import gradio as gr
import i18n
import database as db
import logger_utils
from config import (
    MODEL_SELECTOR_CHOICES,
    MODEL_SELECTOR_DEFAULT,
    AR_SELECTOR_CHOICES,
    AR_SELECTOR_DEFAULT,
    RES_SELECTOR_CHOICES,
    RES_SELECTOR_DEFAULT,
    VALID_IMAGE_EXTENSIONS,
    UPLOAD_DIR
)
import os
import shutil
import platform
import subprocess
from typing import List

# --- Main Page Logic ---

def open_folder_dialog():
    import tkinter as tk
    from tkinter import filedialog
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
    
    saved_paths = []
    for temp_path in files:
        if not temp_path:
            continue
            
        original_name = os.path.basename(temp_path)
        target_path = os.path.join(UPLOAD_DIR, original_name)
        
        try:
            shutil.copy(temp_path, target_path)
            saved_paths.append(target_path)
        except Exception as e:
            logger_utils.log(f"Failed to copy uploaded file: {e}")

    if saved_paths:
        logger_utils.log(f"Uploaded and saved {len(saved_paths)} files.")
        
    return saved_paths

def load_output_gallery():
    save_dir = db.get_setting("save_path")
    if not save_dir or not os.path.exists(save_dir):
        return []
    files = [os.path.join(save_dir, f) for f in os.listdir(save_dir)
             if os.path.splitext(f)[1].lower() in VALID_IMAGE_EXTENSIONS]
    files.sort(key=os.path.getmtime, reverse=True)
    return files

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

# --- UI Rendering ---

def render(state_api_key, gallery_output_history):
    settings = db.get_all_settings()
    initial_prompts = db.get_all_prompt_titles()
    
    history_visible = bool(settings.get("save_path"))

    with gr.Row(equal_height=False):
        with gr.Column(scale=4):
            with gr.Group():
                gr.Markdown(f"#### {i18n.get('home_assets_title')}")
                with gr.Tabs():
                    with gr.TabItem(i18n.get("home_assets_tab_local")):
                        with gr.Row():
                            dir_input = gr.Textbox(value=settings["last_dir"], label=i18n.get("home_assets_label_dirPath"), scale=3)
                            btn_select_dir = gr.Button(i18n.get("home_assets_btn_browse"), scale=0, min_width=50)
                            btn_refresh = gr.Button(i18n.get("home_assets_btn_refresh"), scale=0, min_width=50)
                        size_slider = gr.Slider(2, 6, value=4, step=1, label=i18n.get("home_assets_label_columns"))
                        gallery_source = gr.Gallery(label=i18n.get("home_assets_label_source"), columns=4, height=480, allow_preview=False, object_fit="contain")
                    
                    with gr.TabItem(i18n.get("home_assets_tab_upload")):
                        upload_button = gr.UploadButton(i18n.get("home_assets_btn_upload"), file_types=["image"], file_count="multiple")
                        gallery_upload = gr.Gallery(label="Uploaded", columns=4, height=480, allow_preview=False, object_fit="contain")

                btn_add_to_selected = gr.Button(i18n.get("home_assets_btn_addToSelected"), variant="primary")
                info_box = gr.Markdown(i18n.get("home_assets_info_ready"))
                state_marked_for_add = gr.State(None)

            with gr.Group(visible=history_visible) as history_group:
                with gr.Row():
                    gr.Markdown(f"#### {i18n.get('home_history_title')}")
                    btn_open_out_dir = gr.Button(i18n.get("home_history_btn_open"), scale=0, size="sm")
                gallery_output_history.render()
                with gr.Row():
                    btn_download_hist = gr.DownloadButton(i18n.get("home_history_btn_download"), size="sm", scale=1, interactive=False)
                    btn_delete_hist = gr.Button(i18n.get("home_history_btn_delete"), size="sm", variant="stop", scale=1, interactive=False)
                state_hist_selected_path = gr.State(value=None)

        with gr.Column(scale=6):
            with gr.Group():
                gr.Markdown(f"### {i18n.get('home_control_title')}")
                
                btn_remove_from_selected = gr.Button(i18n.get("home_control_btn_removeFromSelected"), variant="stop")
                gallery_selected = gr.Gallery(label=i18n.get("home_control_gallery_selected_label"), elem_id="fixed_gallery", height=240, columns=6, rows=1, show_label=False, object_fit="contain", allow_preview=False, interactive=False)
                state_selected_images = gr.State(value=[])
                state_marked_for_remove = gr.State(None)

                gr.Markdown(i18n.get("home_control_prompt_title"))
                with gr.Row():
                    prompt_dropdown = gr.Dropdown(choices=initial_prompts, value=i18n.get("home_control_prompt_placeholder"), label=i18n.get("home_control_prompt_label_history"), scale=3, interactive=True)
                    btn_load_prompt = gr.Button(i18n.get("home_control_prompt_btn_load"), scale=1)
                    btn_del_prompt = gr.Button(i18n.get("home_control_prompt_btn_delete"), scale=1, variant="stop")
                prompt_input = gr.Textbox(label="", placeholder=i18n.get("home_control_prompt_input_placeholder"), lines=4, show_label=False)
                with gr.Row():
                    prompt_title_input = gr.Textbox(placeholder=i18n.get("home_control_prompt_save_placeholder"), label=i18n.get("home_control_prompt_save_label"), scale=3, container=False)
                    btn_save_prompt = gr.Button(i18n.get("home_control_prompt_btn_save"), scale=1)

                with gr.Row():
                    model_selector = gr.Dropdown(choices=MODEL_SELECTOR_CHOICES, value=MODEL_SELECTOR_DEFAULT, label=i18n.get("home_control_model_label"), scale=2, allow_custom_value=True)
                    ar_selector = gr.Dropdown(choices=AR_SELECTOR_CHOICES, value=AR_SELECTOR_DEFAULT, label=i18n.get("home_control_ratio_label"), scale=1)
                    res_selector = gr.Dropdown(choices=RES_SELECTOR_CHOICES, value=RES_SELECTOR_DEFAULT, label=i18n.get("home_control_resolution_label"), scale=1)

                with gr.Row():
                    btn_send = gr.Button(i18n.get("home_control_btn_send"), variant="primary", scale=3)
                    btn_retry = gr.Button(i18n.get("home_control_btn_retry"), scale=1)

                with gr.Accordion(i18n.get("home_control_log_label"), open=False):
                    log_output = gr.Code(language="shell", lines=10, interactive=False, elem_id="log_output_box")

            with gr.Group():
                gr.Markdown(f"### {i18n.get('home_preview_title')}")
                result_image = gr.Image(label=i18n.get("home_preview_label_result"), type="pil", interactive=False, height=500)
                btn_download = gr.DownloadButton(label=i18n.get("home_preview_btn_download_placeholder"), interactive=False)

    return {
        "dir_input": dir_input,
        "btn_select_dir": btn_select_dir,
        "btn_refresh": btn_refresh,
        "size_slider": size_slider,
        "gallery_source": gallery_source,
        "info_box": info_box,
        "gallery_selected": gallery_selected,
        "prompt_dropdown": prompt_dropdown,
        "btn_load_prompt": btn_load_prompt,
        "btn_del_prompt": btn_del_prompt,
        "prompt_input": prompt_input,
        "prompt_title_input": prompt_title_input,
        "btn_save_prompt": btn_save_prompt,
        "model_selector": model_selector,
        "ar_selector": ar_selector,
        "res_selector": res_selector,
        "btn_send": btn_send,
        "btn_retry": btn_retry,
        "log_output": log_output,
        "result_image": result_image,
        "btn_download": btn_download,
        "btn_open_out_dir": btn_open_out_dir,
        "btn_download_hist": btn_download_hist,
        "btn_delete_hist": btn_delete_hist,
        "state_hist_selected_path": state_hist_selected_path,
        "state_selected_images": state_selected_images,
        "btn_add_to_selected": btn_add_to_selected,
        "btn_remove_from_selected": btn_remove_from_selected,
        "state_marked_for_add": state_marked_for_add,
        "state_marked_for_remove": state_marked_for_remove,
        "upload_button": upload_button,
        "gallery_upload": gallery_upload,
        "history_group": history_group
    }