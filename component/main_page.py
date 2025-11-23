import gradio as gr
import i18n
import database as db
import app_logic
import logger_utils


def render(state_api_key, gallery_output_history):
    settings = db.get_all_settings()
    initial_prompts = db.get_all_prompt_titles()

    with gr.Row(equal_height=False):
        # === 左侧 ===
        with gr.Column(scale=4):
            gr.Markdown(f"#### {i18n.get('tab_assets')}")
            with gr.Row():
                dir_input = gr.Textbox(value=settings["last_dir"], label=i18n.get("dir_path"), scale=3)
                btn_select_dir = gr.Button(i18n.get("btn_select"), scale=0, min_width=50)
                btn_refresh = gr.Button(i18n.get("btn_refresh"), scale=0, min_width=50)

            # ⬇️ i18n 修复: label="Column" -> label=i18n.get("label_column")
            size_slider = gr.Slider(2, 6, value=4, step=1, label=i18n.get("label_column"))

            # ⬇️ i18n 修复: label="Source" -> label=i18n.get("label_source")
            gallery_source = gr.Gallery(label=i18n.get("label_source"), columns=4, height=520, allow_preview=False)

            info_box = gr.Markdown(i18n.get("ready"))

            gr.Markdown(f"#### {i18n.get('header_output_gallery', '📤 历史输出')}")
            gallery_output_history.render()

            # === 右侧 ===
        with gr.Column(scale=6, elem_classes="right-panel"):
            state_selected_images = gr.State(value=[])
            with gr.Group():
                with gr.Row():
                    gr.Markdown(i18n.get("selected_imgs"))
                    btn_clear = gr.Button("🗑️", size="sm", scale=0)
                gr.Markdown(i18n.get("tip_remove"))
                gallery_selected = gr.Gallery(label=i18n.get("gallery_selected"), elem_id="fixed_gallery",
                                              height=240, columns=6, rows=1, show_label=False, object_fit="cover",
                                              allow_preview=False, interactive=False)

            gr.Markdown(i18n.get("section_prompt"))
            with gr.Group():
                with gr.Row():
                    prompt_dropdown = gr.Dropdown(choices=initial_prompts, value="---",
                                                  label=i18n.get("label_hist_prompt"), scale=3, interactive=True)
                    btn_load_prompt = gr.Button(i18n.get("btn_load"), scale=1)
                    btn_del_prompt = gr.Button(i18n.get("btn_del"), scale=1, variant="stop")
                prompt_input = gr.Textbox(label="", placeholder=i18n.get("ph_prompt"), lines=4, show_label=False)
                with gr.Row():
                    prompt_title_input = gr.Textbox(placeholder=i18n.get("ph_save_title"),
                                                    label=i18n.get("label_save_title"), scale=3, container=False)
                    btn_save_prompt = gr.Button(i18n.get("btn_save_prompt"), scale=1)

            with gr.Row():
                model_selector = gr.Dropdown(["gemini-2.5-flash-image", "gemini-3-pro-image-preview"],
                                             value="gemini-3-pro-image-preview", label=i18n.get("label_model"),
                                             scale=2, allow_custom_value=True)
                ar_selector = gr.Dropdown(["1:1", "3:4", "4:3", "16:9"], value="1:1", label=i18n.get("label_ratio"),
                                          scale=1)
                res_selector = gr.Dropdown(["1K", "2K", "4K"], value="2K", label=i18n.get("label_res"), scale=1)

            with gr.Row():
                btn_send = gr.Button(i18n.get("btn_send"), variant="primary", scale=3)
                btn_retry = gr.Button(i18n.get("btn_retry"), scale=1)

            log_output = gr.Code(language="shell", label=i18n.get("log_label"), lines=10, interactive=False)
            result_image = gr.Image(label=i18n.get("label_result"), type="pil", interactive=False, height=500)
            download_html = gr.HTML(value=app_logic.get_disabled_download_html(), visible=True)

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
        "download_html": download_html,
        "state_selected_images": state_selected_images
    }