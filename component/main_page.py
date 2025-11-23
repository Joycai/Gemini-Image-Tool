import gradio as gr
import i18n
import database as db
import app_logic
import logger_utils
from config import (
    MODEL_SELECTOR_CHOICES,
    MODEL_SELECTOR_DEFAULT,
    AR_SELECTOR_CHOICES,
    AR_SELECTOR_DEFAULT,
    RES_SELECTOR_CHOICES,
    RES_SELECTOR_DEFAULT
)


def render(state_api_key, gallery_output_history):
    settings = db.get_all_settings()
    initial_prompts = db.get_all_prompt_titles()

    with gr.Row(equal_height=False):
        # === 左侧 ===
        with gr.Column(scale=4):
            # --- 区域 1: 图片选择 ---
            with gr.Group():
                gr.Markdown(f"#### {i18n.get('tab_assets')}")
                with gr.Row():
                    dir_input = gr.Textbox(value=settings["last_dir"], label=i18n.get("dir_path"), scale=3)
                    btn_select_dir = gr.Button(i18n.get("btn_select"), scale=0, min_width=50)
                    btn_refresh = gr.Button(i18n.get("btn_refresh"), scale=0, min_width=50)
                size_slider = gr.Slider(2, 6, value=4, step=1, label=i18n.get("label_column"))
                gallery_source = gr.Gallery(label=i18n.get("label_source"), columns=4, height=520, allow_preview=False)
                info_box = gr.Markdown(i18n.get("ready"))

            # --- 区域 2: 输出浏览 ---
            with gr.Group():
                with gr.Row():
                    gr.Markdown(f"#### {i18n.get('header_output_gallery')}")
                    btn_open_out_dir = gr.Button(i18n.get("btn_open_dir"), scale=0, size="sm")
                gallery_output_history.render()
                with gr.Row():
                    btn_download_hist = gr.DownloadButton(i18n.get("btn_down_selected"), size="sm", scale=1, interactive=False)
                    btn_delete_hist = gr.Button(i18n.get("btn_del_selected"), size="sm", variant="stop", scale=1, interactive=False)
                state_hist_selected_path = gr.State(value=None)

        # === 右侧 ===
        with gr.Column(scale=6):
            # --- 区域 3: 编辑和发送 ---
            with gr.Group():
                gr.Markdown(f"### {i18n.get('section_control_panel')}")
                
                # 已选参考图
                with gr.Row():
                    gr.Markdown(i18n.get("selected_imgs"))
                    btn_clear = gr.Button("🗑️", size="sm", scale=0)
                gr.Markdown(i18n.get("tip_remove"))
                gallery_selected = gr.Gallery(label=i18n.get("gallery_selected"), elem_id="fixed_gallery", height=240, columns=6, rows=1, show_label=False, object_fit="cover", allow_preview=False, interactive=False)
                state_selected_images = gr.State(value=[])

                # Prompt
                gr.Markdown(i18n.get("section_prompt"))
                with gr.Row():
                    prompt_dropdown = gr.Dropdown(choices=initial_prompts, value=i18n.get("prompt_placeholder"), label=i18n.get("label_hist_prompt"), scale=3, interactive=True)
                    btn_load_prompt = gr.Button(i18n.get("btn_load"), scale=1)
                    btn_del_prompt = gr.Button(i18n.get("btn_del"), scale=1, variant="stop")
                prompt_input = gr.Textbox(label="", placeholder=i18n.get("ph_prompt"), lines=4, show_label=False)
                with gr.Row():
                    prompt_title_input = gr.Textbox(placeholder=i18n.get("ph_save_title"), label=i18n.get("label_save_title"), scale=3, container=False)
                    btn_save_prompt = gr.Button(i18n.get("btn_save_prompt"), scale=1)

                # 模型、比例、分辨率
                with gr.Row():
                    model_selector = gr.Dropdown(choices=MODEL_SELECTOR_CHOICES, value=MODEL_SELECTOR_DEFAULT, label=i18n.get("label_model"), scale=2, allow_custom_value=True)
                    ar_selector = gr.Dropdown(choices=AR_SELECTOR_CHOICES, value=AR_SELECTOR_DEFAULT, label=i18n.get("label_ratio"), scale=1)
                    res_selector = gr.Dropdown(choices=RES_SELECTOR_CHOICES, value=RES_SELECTOR_DEFAULT, label=i18n.get("label_res"), scale=1)

                # 发送和重试按钮
                with gr.Row():
                    btn_send = gr.Button(i18n.get("btn_send"), variant="primary", scale=3)
                    btn_retry = gr.Button(i18n.get("btn_retry"), scale=1)

                # 日志
                with gr.Accordion(i18n.get("log_label"), open=False):
                    log_output = gr.Code(language="shell", lines=10, interactive=False, elem_id="log_output_box")

            # --- 区域 4: 结果预览 ---
            with gr.Group():
                result_image = gr.Image(label=i18n.get("label_result"), type="pil", interactive=False, height=500)
                btn_download = gr.DownloadButton(label=i18n.get("btn_download_placeholder"), interactive=False)

    return {
        "dir_input": dir_input,
        "btn_select_dir": btn_select_dir,
        "btn_refresh": btn_refresh,
        "size_slider": size_slider,
        "gallery_source": gallery_source,
        "info_box": info_box,
        "btn_clear": btn_clear,
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
        "state_selected_images": state_selected_images
    }