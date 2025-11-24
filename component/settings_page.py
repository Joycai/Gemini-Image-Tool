import gradio as gr
import i18n
import database as db
import shutil
import os
from config import UPLOAD_DIR, OUTPUT_DIR
import app_logic

def save_cfg_wrapper(key, path, prefix, lang):
    db.save_setting("api_key", key)
    db.save_setting("save_path", path)
    db.save_setting("file_prefix", prefix)
    db.save_setting("language", lang)
    app_logic.logger_utils.log(i18n.get("logic_info_configSaved"))
    gr.Info(i18n.get("logic_info_configSaved"))
    return key, app_logic.load_output_gallery()

def clear_cache():
    """清空 tmp 目录下的 upload 和 output 文件夹"""
    dirs_to_clear = [UPLOAD_DIR, OUTPUT_DIR]
    for d in dirs_to_clear:
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d)
    gr.Info(i18n.get("logic_info_cacheCleared"))

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
            btn_clear_cache = gr.Button(i18n.get("settings_btn_clear_cache"), variant="stop", scale=1)

    return {
        "api_key": setting_api_key_input,
        "path": setting_save_path,
        "prefix": setting_prefix,
        "lang": setting_lang,
        "btn_save": btn_save_settings,
        "btn_clear_cache": btn_clear_cache
    }

def bind_events(settings_ui, state_api_key, gallery_output_history):
    settings_ui["btn_save"].click(
        save_cfg_wrapper,
        inputs=[settings_ui["api_key"], settings_ui["path"], settings_ui["prefix"], settings_ui["lang"]],
        outputs=[state_api_key, gallery_output_history]
    )
    settings_ui["btn_clear_cache"].click(fn=clear_cache)