# ================= 🐛 PyCharm Debugger 修复补丁 =================
import asyncio
import sys

# 仅在 Debug 模式下应用修复
if sys.gettrace() is not None:
    _pycharm_run = asyncio.run


    def _fixed_run(main, *, debug=None, loop_factory=None):
        return _pycharm_run(main, debug=debug)


    asyncio.run = _fixed_run
# ==============================================================

import gradio as gr
import os
import time
import tkinter as tk
from tkinter import filedialog
from PIL import Image

# 引入模块
import database as db
import api_client
import logger_utils
import i18n  # ⬇️ 新增 i18n 模块


# --- 辅助逻辑 ---
def open_folder_dialog():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    folder_path = filedialog.askdirectory()
    root.destroy()
    return folder_path


def load_images_from_dir(dir_path):
    if not dir_path or not os.path.exists(dir_path):
        return [], i18n.get("dir_path") + " Not Found"
    db.save_setting("last_dir", dir_path)
    valid_exts = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
    image_files = [os.path.join(dir_path, f) for f in os.listdir(dir_path)
                   if os.path.splitext(f)[1].lower() in valid_exts]

    # 使用 i18n
    msg = i18n.get("log_load_dir", path=dir_path, count=len(image_files))
    logger_utils.log(msg)
    return image_files, msg


def handle_generation_and_save(prompt, img_paths, key, model, ar, res):
    logger_utils.log(i18n.get("log_new_task"))

    # 注意：api_client 内部的日志建议也改造成接受 i18n，或者在 api_client 里 import i18n
    # 这里为了简化，我们在 api_client 外部做部分日志，内部保持原样或后续再改
    try:
        generated_image = api_client.call_google_genai(prompt, img_paths, key, model, ar, res)
    except Exception as e:
        # api_client 抛出的 Error 已经在内部处理过，这里直接展示
        return None, gr.HTML(visible=False)

    save_dir = db.get_setting("save_path", "outputs")
    prefix = db.get_setting("file_prefix", "gemini_gen")
    full_path = None
    try:
        os.makedirs(save_dir, exist_ok=True)
        timestamp = int(time.time())
        filename = f"{prefix}_{timestamp}.png"
        full_path = os.path.abspath(os.path.join(save_dir, filename))
        generated_image.save(full_path, format="PNG")

        logger_utils.log(i18n.get("log_save_ok", path=filename))
        gr.Info(i18n.get("info_save_ok", name=filename))
    except Exception as e:
        logger_utils.log(i18n.get("log_save_fail", err=str(e)))
        gr.Warning(i18n.get("warn_save_fail", err=str(e)))

    if full_path and os.path.exists(full_path):
        # 构建下载 HTML
        safe_path = full_path.replace("\\", "/")
        filename = os.path.basename(full_path)
        btn_text = i18n.get("btn_download_html") + f" ({filename})"

        html_content = f"""
        <div style="text-align: center; margin-top: 10px;">
            <a href="/file={safe_path}" download="{filename}" target="_blank" 
               style="display: inline-block; background-color: #2563eb; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: bold; font-family: sans-serif; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
               {btn_text}
            </a>
        </div>
        """
        return generated_image, gr.HTML(value=html_content, visible=True)
    else:
        return generated_image, gr.HTML(visible=False)


# --- Prompt 管理逻辑 ---
def refresh_prompt_dropdown():
    titles = db.get_all_prompt_titles()
    return gr.Dropdown(choices=titles, value="---")


def load_prompt_to_ui(selected_title):
    if not selected_title or selected_title == "---":
        return gr.skip()
    logger_utils.log(i18n.get("log_load_prompt", title=selected_title))
    content = db.get_prompt_content(selected_title)
    return content


def save_prompt_to_db(title, content):
    if not title or not content:
        gr.Warning(i18n.get("warn_prompt_empty"))
        return gr.skip()
    db.save_prompt(title, content)
    logger_utils.log(i18n.get("log_save_prompt", title=title))
    gr.Info(i18n.get("info_prompt_saved", title=title))
    return refresh_prompt_dropdown()


def delete_prompt_from_db(selected_title):
    if not selected_title or selected_title == "---":
        return gr.skip()
    db.delete_prompt(selected_title)
    logger_utils.log(i18n.get("log_del_prompt", title=selected_title))
    gr.Info(i18n.get("info_prompt_del", title=selected_title))
    return refresh_prompt_dropdown()


def select_img(evt: gr.SelectData, all_imgs, current):
    path = all_imgs[evt.index] if isinstance(all_imgs, list) else all_imgs[evt.index].name
    new_list = current + [path]
    if len(new_list) > 5: new_list = new_list[-5:]
    logger_utils.log(i18n.get("log_select_img", name=os.path.basename(path)))
    return new_list, new_list


def remove_selected_img(evt: gr.SelectData, current_list):
    if not current_list or evt.index is None:
        return current_list, current_list
    if evt.index >= len(current_list):
        return current_list, current_list
    removed_item = current_list[evt.index]
    removed_name = os.path.basename(removed_item)
    new_list = [path for i, path in enumerate(current_list) if i != evt.index]
    logger_utils.log(i18n.get("log_remove_img", name=removed_name, count=len(new_list)))
    return new_list, new_list


# --- UI 构建 ---

# CSS: 强制画廊网格布局
custom_css = """
.toolbar-btn { text-align: left !important; margin-bottom: 10px; }
.right-panel { border-left: 1px solid #e5e7eb; padding-left: 20px; }
.tool-sidebar { background-color: #f9fafb; padding: 10px; border-left: 1px solid #e5e7eb; }
#fixed_gallery .grid-wrap { grid-template-columns: repeat(6, 1fr) !important; }
"""

# ⬇️ JavaScript: 用于切换深色模式
# Gradio 网页通常通过 body 的 class="dark" 来控制主题
js_toggle_theme = """
() => {
    document.body.classList.toggle('dark');
}
"""

with gr.Blocks(title=i18n.get("app_title")) as demo:
    gr.HTML(f"<style>{custom_css}</style>")

    # 初始化数据
    settings = db.get_all_settings()
    initial_prompts = db.get_all_prompt_titles()

    state_api_key = gr.State(value=settings["api_key"])
    state_current_dir_images = gr.State(value=[])
    state_selected_images = gr.State(value=[])

    # 1. 顶部工具栏
    with gr.Row(elem_classes="top-toolbar", variant="panel"):
        gr.Markdown(f"### {i18n.get('app_title')}")
        with gr.Column(scale=1): pass

        # ⬇️ 新增：深色模式切换按钮 (绑定 JS)
        btn_theme = gr.Button(i18n.get("btn_theme"), size="sm", variant="secondary", scale=0)

        btn_settings_top = gr.Button(i18n.get("btn_settings"), size="sm", variant="secondary", scale=0)

    # 2. 设置面板
    with gr.Accordion(i18n.get("settings_panel"), open=False, visible=False) as settings_panel:
        with gr.Row():
            setting_api_key_input = gr.Textbox(label=i18n.get("label_apikey"), value=settings["api_key"],
                                               type="password", scale=2)
            btn_save_settings = gr.Button(i18n.get("btn_save_conf"), variant="primary", scale=0)
        with gr.Row():
            setting_save_path = gr.Textbox(label=i18n.get("label_save_path"), value=settings["save_path"])
            setting_prefix = gr.Textbox(label=i18n.get("label_prefix"), value=settings["file_prefix"])

        # ⬇️ 新增：语言选择
        with gr.Row():
            # 值为 code, 显示为 Label。 Gradio Dropdown 可以直接传 values list
            setting_lang = gr.Dropdown(
                choices=[("中文", "zh"), ("English", "en")],
                value=settings["language"],
                label=i18n.get("label_language"),
                interactive=True
            )

    # 3. 主区域
    with gr.Row(equal_height=False):
        # 左侧：浏览
        with gr.Column(scale=4):
            gr.Markdown(f"#### {i18n.get('tab_assets')}")
            with gr.Row():
                dir_input = gr.Textbox(value=settings["last_dir"], label=i18n.get("dir_path"), scale=3)
                btn_select_dir = gr.Button(i18n.get("btn_select"), scale=0, min_width=50)
                btn_refresh = gr.Button(i18n.get("btn_refresh"), scale=0, min_width=50)
            size_slider = gr.Slider(2, 6, value=4, step=1, label="Column")
            gallery_source = gr.Gallery(label="Source", columns=4, height=500, allow_preview=False)
            info_box = gr.Markdown(i18n.get("ready"))

        # 右侧：工作台
        with gr.Column(scale=6, elem_classes="right-panel"):
            with gr.Group():
                with gr.Row():
                    gr.Markdown(i18n.get("selected_imgs"))
                    btn_clear = gr.Button("🗑️", size="sm", scale=0)

                gr.Markdown(i18n.get("tip_remove"))
                gallery_selected = gr.Gallery(
                    label=i18n.get("gallery_selected"),
                    elem_id="fixed_gallery",
                    height=240,
                    columns=6,
                    rows=1,
                    show_label=False,
                    object_fit="cover",
                    allow_preview=False,
                    interactive=False
                )

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
                                             value="gemini-3-pro-image-preview", label=i18n.get("label_model"), scale=2,
                                             allow_custom_value=True)
                ar_selector = gr.Dropdown(["1:1", "3:4", "4:3", "16:9"], value="1:1", label=i18n.get("label_ratio"),
                                          scale=1)
                res_selector = gr.Dropdown(["1K", "2K", "4K"], value="2K", label=i18n.get("label_res"), scale=1)

            with gr.Row():
                btn_send = gr.Button(i18n.get("btn_send"), variant="primary", scale=3)
                btn_retry = gr.Button(i18n.get("btn_retry"), scale=1)

            result_image = gr.Image(label=i18n.get("label_result"), type="pil", interactive=False, height=500)
            download_html = gr.HTML(visible=False)

    # Log 显示区域
    with gr.Accordion(i18n.get("log_title"), open=True):
        log_output = gr.Code(language="shell", label=i18n.get("log_label"), lines=10, interactive=False)
        log_timer = gr.Timer(1)

    # ================= 事件绑定 =================

    # ⬇️ 深色模式切换 (直接执行 JS)
    btn_theme.click(None, None, None, js=js_toggle_theme)

    log_timer.tick(logger_utils.get_logs, outputs=log_output)
    btn_settings_top.click(lambda: gr.Accordion(visible=True), None, settings_panel)


    def save_cfg_wrapper(key, path, prefix, lang):
        db.save_setting("api_key", key)
        db.save_setting("save_path", path)
        db.save_setting("file_prefix", prefix)
        db.save_setting("language", lang)

        logger_utils.log(i18n.get("info_conf_saved"))
        gr.Info(i18n.get("info_conf_saved"))
        # 注意：语言修改需要重启 App 才能完全应用到 UI Label
        return key, gr.Accordion(visible=False)


    btn_save_settings.click(
        save_cfg_wrapper,
        [setting_api_key_input, setting_save_path, setting_prefix, setting_lang],
        [state_api_key, settings_panel]
    )

    # 其他事件保持逻辑不变，仅复用
    btn_save_prompt.click(save_prompt_to_db, [prompt_title_input, prompt_input], [prompt_dropdown])
    btn_load_prompt.click(load_prompt_to_ui, [prompt_dropdown], [prompt_input])
    btn_del_prompt.click(delete_prompt_from_db, [prompt_dropdown], [prompt_dropdown])

    btn_select_dir.click(lambda: open_folder_dialog() or gr.skip(), None, dir_input)
    load_inputs = [dir_input]
    load_outputs = [state_current_dir_images, info_box]
    dir_input.change(load_images_from_dir, load_inputs, load_outputs).then(lambda x: x, state_current_dir_images,
                                                                           gallery_source)
    btn_refresh.click(load_images_from_dir, load_inputs, load_outputs).then(lambda x: x, state_current_dir_images,
                                                                            gallery_source)
    size_slider.change(lambda x: gr.Gallery(columns=x), size_slider, gallery_source)

    gallery_source.select(select_img, [state_current_dir_images, state_selected_images],
                          [state_selected_images, gallery_selected])
    gallery_selected.select(remove_selected_img, [state_selected_images], [state_selected_images, gallery_selected])
    btn_clear.click(lambda: ([], []), None, [state_selected_images, gallery_selected])

    gen_inputs = [prompt_input, state_selected_images, state_api_key, model_selector, ar_selector, res_selector]
    gen_outputs = [result_image, download_html]
    btn_send.click(handle_generation_and_save, gen_inputs, gen_outputs)
    btn_retry.click(handle_generation_and_save, gen_inputs, gen_outputs)

    demo.load(load_images_from_dir, dir_input, [state_current_dir_images, info_box]).then(lambda x: x,
                                                                                          state_current_dir_images,
                                                                                          gallery_source)

if __name__ == "__main__":
    import platform

    allowed_paths = []
    if platform.system() == "Windows":
        for char in range(ord('A'), ord('Z') + 1):
            allowed_paths.append(f"{chr(char)}:\\")
        nas_paths = ["\\\\DS720plus\\home", "\\\\192.168.1.1\\share"]
        allowed_paths.extend(nas_paths)
    else:
        allowed_paths = ["/", "/mnt", "/media", "/home"]

    print(f"✅ Allowed Paths: {len(allowed_paths)}")
    demo.launch(inbrowser=True, server_name="0.0.0.0", server_port=7860, allowed_paths=allowed_paths)