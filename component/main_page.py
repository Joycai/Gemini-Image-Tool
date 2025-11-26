import os
import platform
import shutil
import subprocess
from typing import List
import tkinter as tk
from tkinter import filedialog

import gradio as gr

import database as db
import i18n
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


# --- Main Page Logic ---

def open_folder_dialog():
    system_platform = platform.system()
    if system_platform == "Darwin":
        script = 'POSIX path of (choose folder with prompt "Please select a folder to process")'
        try:
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except (subprocess.CalledProcessError, Exception) as e:
            logger_utils.log(f"Failed to open folder dialog: {e}")
            return None
    else:
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            folder_path = filedialog.askdirectory()
            root.destroy()
            return folder_path if folder_path else None
        except Exception as e:
            logger_utils.log(f"Failed to open folder dialog: {e}")
            return None

def load_images_from_dir(dir_path, recursive):
    if not dir_path or not os.path.exists(dir_path):
        return [], i18n.get("logic_error_dirNotFound", path=dir_path)
    db.save_setting("last_dir", dir_path)
    
    image_files = []
    if recursive:
        for root, _, files in os.walk(dir_path):
            for f in files:
                if os.path.splitext(f)[1].lower() in VALID_IMAGE_EXTENSIONS:
                    image_files.append(os.path.join(root, f))
    else:
        image_files = [os.path.join(dir_path, f) for f in os.listdir(dir_path)
                       if os.path.splitext(f)[1].lower() in VALID_IMAGE_EXTENSIONS]
                       
    msg = i18n.get("logic_log_loadDir", path=dir_path, count=len(image_files))
    logger_utils.log(msg)
    return image_files, msg

def handle_upload(files):
    if not files: return []
    saved_paths = []
    for temp_path in files:
        if not temp_path: continue
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

def mark_for_add(evt: gr.SelectData):
    if evt.value and isinstance(evt.value, dict) and 'image' in evt.value and 'path' in evt.value['image']:
        return evt.value['image']['path']
    return None

def mark_for_remove(evt: gr.SelectData):
    if evt.value and isinstance(evt.value, dict) and 'image' in evt.value and 'path' in evt.value['image']:
        return evt.value['image']['path']
    return None

def add_marked_to_selected(marked_path: str, current_selected: List[str]):
    if not marked_path: return current_selected
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

# --- UI Rendering ---

def render(state_api_key):
    settings = db.get_all_settings()
    initial_prompts = db.get_all_prompt_titles()

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
                        with gr.Row():
                            recursive_checkbox = gr.Checkbox(label=i18n.get("home_assets_label_recursive"), value=False)
                            size_slider = gr.Slider(2, 6, value=4, step=1, label=i18n.get("home_assets_label_columns"))
                        gallery_source = gr.Gallery(label=i18n.get("home_assets_label_source"), columns=4, height="auto", allow_preview=False, object_fit="contain")
                    
                    with gr.TabItem(i18n.get("home_assets_tab_upload")):
                        upload_button = gr.UploadButton(i18n.get("home_assets_btn_upload"), file_types=["image"], file_count="multiple")
                        gallery_upload = gr.Gallery(label="Uploaded", columns=4, height="auto", allow_preview=False, object_fit="contain", interactive=True)

                btn_add_to_selected = gr.Button(i18n.get("home_assets_btn_addToSelected"), variant="primary")
                info_box = gr.Markdown(i18n.get("home_assets_info_ready"))
                state_marked_for_add = gr.State(None)

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
                    ar_selector = gr.Dropdown(choices=i18n.get_translated_choices(AR_SELECTOR_CHOICES), value=AR_SELECTOR_DEFAULT, label=i18n.get("home_control_ratio_label"), scale=1)
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
        "recursive_checkbox": recursive_checkbox,
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
        "state_selected_images": state_selected_images,
        "btn_add_to_selected": btn_add_to_selected,
        "btn_remove_from_selected": btn_remove_from_selected,
        "state_marked_for_add": state_marked_for_add,
        "state_marked_for_remove": state_marked_for_remove,
        "upload_button": upload_button,
        "gallery_upload": gallery_upload,
    }
