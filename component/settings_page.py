import gradio as gr
import i18n
import database as db


def render():
    settings = db.get_all_settings()

    # 渲染 UI
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


    # ⬇️ 关键修改：必须返回字典，不能只返回变量名
    return {
        "api_key": setting_api_key_input,
        "path": setting_save_path,
        "prefix": setting_prefix,
        "lang": setting_lang,
        "btn_save": btn_save_settings,
        "btn_clear_cache": btn_clear_cache
    }