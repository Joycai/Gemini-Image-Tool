import json
import os
import shutil
import time

import gradio as gr

from common import logger_utils, database as db, i18n
from gapp.component import main_page
from common.config import UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR


def clear_cache():
    """清空 tmp 目录下的 upload 和 output 文件夹"""
    dirs_to_clear = [UPLOAD_DIR, OUTPUT_DIR]
    for d in dirs_to_clear:
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d)
    gr.Info(i18n.get("logic_info_cacheCleared"))

def export_prompts_logic():
    """导出所有 prompts 到一个 JSON 文件"""
    try:
        prompts = db.get_all_prompts_for_export()
        timestamp = int(time.time())
        filename = f"prompts_export_{timestamp}.json"
        filepath = os.path.join(TEMP_DIR, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(prompts, f, ensure_ascii=False, indent=4)
        
        gr.Info(i18n.get("logic_info_prompts_exported", count=len(prompts)))
        return gr.File(value=filepath, visible=True)
    except (IOError, OSError, json.JSONDecodeError) as e:
        error_msg = i18n.get("logic_error_prompts_export_failed", error=str(e))
        logger_utils.log(error_msg)
        gr.Error(error_msg)
        return gr.File(visible=False)

def import_prompts_logic(file):
    """从 JSON 文件导入 prompts"""
    if file is None:
        return gr.skip()
    try:
        with open(file.name, 'r', encoding='utf-8') as f:
            prompts_to_import = json.load(f)
        
        count = db.import_prompts_from_list(prompts_to_import)
        
        gr.Info(i18n.get("logic_info_prompts_imported", count=count))
        return main_page.refresh_prompt_dropdown()
    except (IOError, OSError, json.JSONDecodeError) as e:
        error_msg = i18n.get("logic_error_prompts_import_failed", error=str(e))
        logger_utils.log(error_msg)
        gr.Error(error_msg)
        return gr.skip()

def render():
    settings = db.get_all_settings()
    with gr.Group():
        gr.Markdown(f"## {i18n.get('settings_title')}")

        with gr.Row():
            setting_api_key_input = gr.Textbox(label=i18n.get("settings_label_apiKey"), value=settings["api_key"], type="password",
                                               scale=2)

        with gr.Row():
            setting_save_path = gr.Textbox(label=i18n.get("settings_label_savePath"), value=settings["save_path"])
            setting_prefix = gr.Textbox(label=i18n.get("settings_label_prefix"), value=settings["file_prefix"])

        with gr.Row():
            setting_lang = gr.Dropdown(choices=[("中文", "zh"), ("English", "en")], value=settings["language"],
                                       label=i18n.get("settings_label_language"), interactive=True)

        with gr.Row():
            btn_save_settings = gr.Button(i18n.get("settings_btn_save"), variant="primary", scale=1)
        
        with gr.Accordion(label=i18n.get("settings_label_prompt_management"), open=True):
            with gr.Row():
                btn_export_prompts = gr.Button(i18n.get("settings_btn_export_prompts"))
                btn_import_prompts = gr.UploadButton(i18n.get("settings_btn_import_prompts"), file_types=['.json'])
            
            exported_file = gr.File(label="Exported Prompts", visible=False)

        with gr.Row():
            btn_clear_cache = gr.Button(i18n.get("settings_btn_clear_cache"), variant="secondary", scale=1)
            btn_restart = gr.Button("🔄 Restart", variant="stop", scale=1)


    return {
        "api_key": setting_api_key_input,
        "path": setting_save_path,
        "prefix": setting_prefix,
        "lang": setting_lang,
        "btn_save": btn_save_settings,
        "btn_clear_cache": btn_clear_cache,
        "btn_restart": btn_restart,
        "btn_export_prompts": btn_export_prompts,
        "btn_import_prompts": btn_import_prompts,
        "exported_file": exported_file
    }
