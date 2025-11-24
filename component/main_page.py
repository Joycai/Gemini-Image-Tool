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
    
    # 根据是否配置了永久保存路径，决定是否显示历史记录区域
    history_visible = bool(settings.get("save_path"))

    with gr.Row(equal_height=False):
        # === 左侧 ===
        with gr.Column(scale=4):
            # --- 区域 1: 图片选择 ---
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

            # --- 区域 2: 输出浏览 ---
            with gr.Group(visible=history_visible) as history_group:
                with gr.Row():
                    gr.Markdown(f"#### {i18n.get('home_history_title')}")
                    btn_open_out_dir = gr.Button(i18n.get("home_history_btn_open"), scale=0, size="sm")
                gallery_output_history.render()
                with gr.Row():
                    btn_download_hist = gr.DownloadButton(i18n.get("home_history_btn_download"), size="sm", scale=1, interactive=False)
                    btn_delete_hist = gr.Button(i18n.get("home_history_btn_delete"), size="sm", variant="stop", scale=1, interactive=False)
                state_hist_selected_path = gr.State(value=None)

        # === 右侧 ===
        with gr.Column(scale=6):
            # --- 区域 3: 编辑和发送 ---
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

            # --- 区域 4: 结果预览 ---
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