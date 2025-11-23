# ================= 🐛 PyCharm Debugger 修复补丁 =================
import asyncio
import sys

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
import i18n


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
    msg = i18n.get("log_load_dir", path=dir_path, count=len(image_files))
    logger_utils.log(msg)
    return image_files, msg


# ⬇️ 新增：加载输出目录的图片 (用于左侧下方 Output Gallery)
def load_output_gallery():
    save_dir = db.get_setting("save_path", "outputs")
    if not os.path.exists(save_dir):
        return []

    # 获取所有图片并按修改时间倒序排列（最新的在最前）
    valid_exts = {'.png', '.jpg', '.jpeg', '.webp'}
    files = [os.path.join(save_dir, f) for f in os.listdir(save_dir)
             if os.path.splitext(f)[1].lower() in valid_exts]
    files.sort(key=os.path.getmtime, reverse=True)
    return files


# 生成禁用状态的下载按钮 HTML
def get_disabled_download_html():
    text = i18n.get("btn_download_placeholder")
    return f"""
    <div style="text-align: center; margin-top: 10px;">
        <span style="
            display: inline-block;
            background-color: #f3f4f6;
            color: #9ca3af;
            border: 1px solid #e5e7eb;
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: bold;
            font-family: sans-serif;
            cursor: not-allowed;
            user-select: none;
        ">
        {text}
        </span>
    </div>
    """


def handle_generation_and_save(prompt, img_paths, key, model, ar, res):
    logger_utils.log(i18n.get("log_new_task"))

    # 1. 调用 API
    try:
        generated_image = api_client.call_google_genai(prompt, img_paths, key, model, ar, res)
    except Exception as e:
        # 失败时保持按钮灰色
        return None, get_disabled_download_html()

    # 2. 保存文件
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

    # 3. 生成激活状态的 HTML 链接
    if full_path and os.path.exists(full_path):
        safe_path = full_path.replace("\\", "/")
        filename = os.path.basename(full_path)
        btn_text = i18n.get("btn_download_ready") + f" ({filename})"

        html_content = f"""
        <div style="text-align: center; margin-top: 10px;">
            <a href="/file={safe_path}" download="{filename}" target="_blank" 
               style="display: inline-block; background-color: #2563eb; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: bold; font-family: sans-serif; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
               {btn_text}
            </a>
        </div>
        """
        return generated_image, html_content
    else:
        return generated_image, get_disabled_download_html()


# --- Prompt 管理逻辑 (保持不变) ---
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


def restart_app():
    """
    重启当前 Python 进程
    注意：这会导致前端网页连接断开，用户需要手动刷新浏览器
    """
    logger_utils.log(i18n.get("log_restarting"))
    # 稍微延迟一点点，让日志有机会写入
    time.sleep(0.5)

    # 获取当前 Python解释器路径 和 脚本路径参数
    python = sys.executable
    # 使用 execl 替换当前进程
    os.execl(python, python, *sys.argv)
    

# ⬇️ 页面加载初始化 (修改版)
def init_app_data():
    fresh_settings = db.get_all_settings()
    logger_utils.log("🔄 正在恢复用户会话...")
    # 返回的内容顺序必须与下面 demo.load 的 outputs 一一对应
    return (
        fresh_settings["last_dir"],       # 1. 目录路径
        fresh_settings["api_key"],        # 2. State API Key
        get_disabled_download_html(),     # 3. 下载按钮状态
        fresh_settings["save_path"],      # 4. 设置: 自动保存路径 (修复不同步的关键!)
        fresh_settings["file_prefix"],    # 5. 设置: 文件前缀
        fresh_settings["language"],       # 6. 设置: 语言
        fresh_settings["api_key"]         # 7. 设置: API Key 输入框
    )


# --- UI 构建 ---
custom_css = """
.toolbar-btn { text-align: left !important; margin-bottom: 10px; }
.right-panel { border-left: 1px solid #e5e7eb; padding-left: 20px; }
.tool-sidebar { background-color: #f9fafb; padding: 10px; border-left: 1px solid #e5e7eb; }
#fixed_gallery .grid-wrap { grid-template-columns: repeat(6, 1fr) !important; }
"""
js_toggle_theme = "() => { document.body.classList.toggle('dark'); }"

with gr.Blocks(title=i18n.get("app_title")) as demo:
    gr.HTML(f"<style>{custom_css}</style>")

    settings = db.get_all_settings()
    initial_prompts = db.get_all_prompt_titles()

    state_api_key = gr.State(value=settings["api_key"])
    state_current_dir_images = gr.State(value=[])
    state_selected_images = gr.State(value=[])

    # 1. 顶部工具栏
    with gr.Row(elem_classes="top-toolbar", variant="panel"):
        gr.Markdown(f"### {i18n.get('app_title')}")
        with gr.Column(scale=1): pass

        # ⬇️ 新增：重启按钮 (红色警告色 variant="stop" 或 灰色 secondary 均可)
        btn_restart = gr.Button(i18n.get("btn_restart"), size="sm", variant="stop", scale=0)

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
        with gr.Row():
            setting_lang = gr.Dropdown(choices=[("中文", "zh"), ("English", "en")], value=settings["language"],
                                       label=i18n.get("label_language"), interactive=True)

    # 3. 主区域
    with gr.Row(equal_height=False):
        # === 左侧：资源与历史 (40%) ===
        with gr.Column(scale=4):
            # A. 本地素材库
            gr.Markdown(f"#### {i18n.get('tab_assets')}")
            with gr.Row():
                dir_input = gr.Textbox(value=settings["last_dir"], label=i18n.get("dir_path"), scale=3)
                btn_select_dir = gr.Button(i18n.get("btn_select"), scale=0, min_width=50)
                btn_refresh = gr.Button(i18n.get("btn_refresh"), scale=0, min_width=50)
            size_slider = gr.Slider(2, 6, value=4, step=1, label="Column")
            gallery_source = gr.Gallery(label="Source", columns=4, height=520, allow_preview=False)  # 高度略减，腾位置给下方

            info_box = gr.Markdown(i18n.get("ready"))

            # B. ⬇️ 新增：输出历史浏览器
            gr.Markdown(f"#### {i18n.get('header_output_gallery', '📤 历史输出')}")
            # 这里的 allow_preview=True，因为用户可能想看大图
            gallery_output_history = gr.Gallery(label="Outputs", columns=4, height=520, allow_preview=True,
                                                interactive=False)

        # === 右侧：工作台 (60%) ===
        with gr.Column(scale=6, elem_classes="right-panel"):
            with gr.Group():
                with gr.Row():
                    gr.Markdown(i18n.get("selected_imgs"))
                    btn_clear = gr.Button("🗑️", size="sm", scale=0)
                gr.Markdown(i18n.get("tip_remove"))
                gallery_selected = gr.Gallery(label=i18n.get("gallery_selected"), elem_id="fixed_gallery", height=240,
                                              columns=6, rows=1, show_label=False, object_fit="cover",
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
                                             value="gemini-3-pro-image-preview", label=i18n.get("label_model"), scale=2,
                                             allow_custom_value=True)
                ar_selector = gr.Dropdown(["1:1", "3:4", "4:3", "16:9"], value="1:1", label=i18n.get("label_ratio"),
                                          scale=1)
                res_selector = gr.Dropdown(["1K", "2K", "4K"], value="2K", label=i18n.get("label_res"), scale=1)

            with gr.Row():
                btn_send = gr.Button(i18n.get("btn_send"), variant="primary", scale=3)
                btn_retry = gr.Button(i18n.get("btn_retry"), scale=1)

            # ⬇️ 新增：Log 区域 (移到中间)
            # lines=10 固定高度，max_lines 也设为 10 确保不自动撑开
            log_output = gr.Code(language="shell", label=i18n.get("log_label"), lines=10, interactive=False)

            # ⬇️ 修改：结果预览与下载
            result_image = gr.Image(label=i18n.get("label_result"), type="pil", interactive=False, height=500)

            # ⬇️ 修改：常驻 HTML，初始显示禁用状态
            download_html = gr.HTML(value=get_disabled_download_html(), visible=True)

    # 这里的 Log Timer 逻辑需要保留，但 Code 组件已经移到了上面
    log_timer = gr.Timer(1)

    # ================= 事件绑定 =================

    btn_theme.click(None, None, None, js=js_toggle_theme)
    log_timer.tick(logger_utils.get_logs, outputs=log_output)
    btn_settings_top.click(lambda: gr.Accordion(visible=True), None, settings_panel)
    # ⬇️ 绑定重启事件
    btn_restart.click(fn=restart_app, inputs=None, outputs=None)

    # 保存配置事件：保存后不仅更新 state，还要刷新左下角的输出浏览器(因为路径可能变了)
    def save_cfg_wrapper(key, path, prefix, lang):
        db.save_setting("api_key", key)
        db.save_setting("save_path", path)
        db.save_setting("file_prefix", prefix)
        db.save_setting("language", lang)
        logger_utils.log(i18n.get("info_conf_saved"))
        gr.Info(i18n.get("info_conf_saved"))
        # 返回: key, 隐藏面板, 刷新后的输出列表
        return key, gr.Accordion(visible=False), load_output_gallery()


    btn_save_settings.click(
        save_cfg_wrapper,
        [setting_api_key_input, setting_save_path, setting_prefix, setting_lang],
        [state_api_key, settings_panel, gallery_output_history]  # 更新 gallery_output_history
    )

    # Prompt 事件
    btn_save_prompt.click(save_prompt_to_db, [prompt_title_input, prompt_input], [prompt_dropdown])
    btn_load_prompt.click(load_prompt_to_ui, [prompt_dropdown], [prompt_input])
    btn_del_prompt.click(delete_prompt_from_db, [prompt_dropdown], [prompt_dropdown])

    # 左上素材库事件
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

    # 生成事件：
    # 成功后：1.显示图片 2.更新下载按钮HTML 3.自动刷新左下角的输出浏览器
    gen_inputs = [prompt_input, state_selected_images, state_api_key, model_selector, ar_selector, res_selector]
    gen_outputs = [result_image, download_html]

    btn_send.click(handle_generation_and_save, gen_inputs, gen_outputs).then(load_output_gallery, None,
                                                                             gallery_output_history)
    btn_retry.click(handle_generation_and_save, gen_inputs, gen_outputs).then(load_output_gallery, None,
                                                                              gallery_output_history)

    # 启动加载链：
    # Init Data -> Load Source Images -> Refresh Source Gallery -> Load Output History
    demo.load(
        init_app_data,
        inputs=None,
        outputs=[
            dir_input,  # 1
            state_api_key,  # 2
            download_html,  # 3
            setting_save_path,  # 4 (新增)
            setting_prefix,  # 5 (新增)
            setting_lang,  # 6 (新增)
            setting_api_key_input  # 7 (新增)
        ]
    ).then(
        load_images_from_dir,
        inputs=[dir_input],
        outputs=[state_current_dir_images, info_box]
    ).then(
        lambda x: x,
        inputs=[state_current_dir_images],
        outputs=[gallery_source]
    ).then(
        load_output_gallery,
        inputs=None,
        outputs=[gallery_output_history]
    )

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