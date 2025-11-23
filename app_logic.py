import os
import time
import sys
import threading  # ⬇️ 新增
import tkinter as tk
from tkinter import filedialog
import gradio as gr

# 引入模块
import database as db
import api_client
import logger_utils
import i18n

# --- 全局任务状态管理 ---
# 这是一个简单的内存数据库，用来记录当前正在跑的任务
# 即使页面刷新，只要 Python 进程没挂，这个状态就在
TASK_STATE = {
    "status": "idle",  # idle, running, success, error
    "timestamp": 0,
    "result_image": None,  # 存储 PIL Image 对象
    "result_path": None,  # 存储文件路径
    "error_msg": None,
    "ui_updated": True  # 标记 UI 是否已经获取了最新结果
}


def reset_task_state():
    """重置任务状态"""
    TASK_STATE["status"] = "idle"
    TASK_STATE["result_image"] = None
    TASK_STATE["result_path"] = None
    TASK_STATE["error_msg"] = None
    TASK_STATE["ui_updated"] = True


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


def load_output_gallery():
    save_dir = db.get_setting("save_path", "outputs")
    if not os.path.exists(save_dir):
        return []
    valid_exts = {'.png', '.jpg', '.jpeg', '.webp'}
    files = [os.path.join(save_dir, f) for f in os.listdir(save_dir)
             if os.path.splitext(f)[1].lower() in valid_exts]
    files.sort(key=os.path.getmtime, reverse=True)
    return files


def get_disabled_download_html(text_key="btn_download_placeholder"):
    text = i18n.get(text_key)
    return f"""
    <div style="text-align: center; margin-top: 10px;">
        <span style="display: inline-block; background-color: #f3f4f6; color: #9ca3af; border: 1px solid #e5e7eb; padding: 10px 20px; border-radius: 8px; font-weight: bold; font-family: sans-serif; cursor: not-allowed; user-select: none;">
        {text}
        </span>
    </div>
    """


# --- 核心：后台任务线程函数 ---
def _background_worker(prompt, img_paths, key, model, ar, res):
    """这是在后台线程中运行的真实逻辑"""
    try:
        TASK_STATE["status"] = "running"
        TASK_STATE["ui_updated"] = False

        logger_utils.log(i18n.get("log_new_task"))

        # 1. API 调用
        generated_image = api_client.call_google_genai(prompt, img_paths, key, model, ar, res)

        # 2. 保存文件
        save_dir = db.get_setting("save_path", "outputs")
        prefix = db.get_setting("file_prefix", "gemini_gen")

        os.makedirs(save_dir, exist_ok=True)
        timestamp = int(time.time())
        filename = f"{prefix}_{timestamp}.png"
        full_path = os.path.abspath(os.path.join(save_dir, filename))

        generated_image.save(full_path, format="PNG")
        logger_utils.log(i18n.get("log_save_ok", path=filename))

        # 3. 更新成功状态
        TASK_STATE["result_image"] = generated_image
        TASK_STATE["result_path"] = full_path
        TASK_STATE["status"] = "success"

    except Exception as e:
        error_msg = str(e)
        logger_utils.log(i18n.get("log_save_fail", err=error_msg))
        TASK_STATE["error_msg"] = error_msg
        TASK_STATE["status"] = "error"


# --- 供 UI 调用的入口 ---

def start_generation_task(prompt, img_paths, key, model, ar, res):
    """
    UI 点击按钮时调用此函数。
    它不再阻塞等待结果，而是启动线程后立即返回。
    """
    if TASK_STATE["status"] == "running":

        gr.Warning(i18n.get("log_task_running"))
        return

    # 重置状态
    reset_task_state()

    # 启动后台线程
    t = threading.Thread(
        target=_background_worker,
        args=(prompt, img_paths, key, model, ar, res)
    )
    t.start()
    gr.Info(i18n.get("log_task_submitted"))


# --- UI 轮询函数 (Timer 每秒调用) ---
def poll_task_status():
    """
    检查当前任务状态，并返回 UI 更新
    返回: (Image, HTML, Gallery)
    """
    # 1. 如果正在运行
    if TASK_STATE["status"] == "running":
        # 返回禁用状态的下载按钮，文字改为 "处理中..."
        return gr.skip(), get_disabled_download_html("log_new_task"), gr.skip()

    # 2. 如果已经处理完，且 UI 还没更新过 (避免重复刷新导致闪烁)
    if not TASK_STATE["ui_updated"]:

        if TASK_STATE["status"] == "success":
            # 标记已更新
            TASK_STATE["ui_updated"] = True

            # 构建下载链接
            full_path = TASK_STATE["result_path"]
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
            # 成功：更新图片、显示下载按钮、刷新历史画廊
            return TASK_STATE["result_image"], html_content, load_output_gallery()

        elif TASK_STATE["status"] == "error":
            TASK_STATE["ui_updated"] = True
            # gr.Warning(f"任务失败: {TASK_STATE['error_msg']}")
            gr.Warning(i18n.get("log_task_failed"),error_msg={TASK_STATE['error_msg']})

            return None, get_disabled_download_html(), gr.skip()

    # 3. 其他情况 (Idle 或 UI已更新)，保持现状
    return gr.skip(), gr.skip(), gr.skip()


# ... (其余 Prompt 相关、Init 相关逻辑保持不变，直接复制原来的即可) ...
# 为了确保完整性，以下是保留的原有逻辑：

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
    logger_utils.log(i18n.get("log_restarting"))
    time.sleep(0.5)
    python = sys.executable
    os.execl(python, python, *sys.argv)


def save_cfg_wrapper(key, path, prefix, lang):
    db.save_setting("api_key", key)
    db.save_setting("save_path", path)
    db.save_setting("file_prefix", prefix)
    db.save_setting("language", lang)
    logger_utils.log(i18n.get("info_conf_saved"))
    gr.Info(i18n.get("info_conf_saved"))
    return key, load_output_gallery()


def init_app_data():
    fresh_settings = db.get_all_settings()
    logger_utils.log("🔄 正在恢复用户会话...")

    # 1. 默认状态
    current_html = get_disabled_download_html()
    restored_image = None  # 默认不显示图片

    # 2. 检查是否有“断网期间跑完”的任务
    # 如果任务状态是 Success，说明图已经生成好了，直接恢复显示！
    if TASK_STATE["status"] == "success" and TASK_STATE["result_path"] and TASK_STATE["result_image"]:
        logger_utils.log("♻️ 检测到后台已完成的任务，正在恢复显示...")

        # 恢复图片
        restored_image = TASK_STATE["result_image"]

        # 恢复下载按钮
        full_path = TASK_STATE["result_path"]
        filename = os.path.basename(full_path)
        safe_path = full_path.replace("\\", "/")
        btn_text = i18n.get("btn_download_ready") + f" ({filename})"
        current_html = f"""
                <div style="text-align: center; margin-top: 10px;">
                    <a href="/file={safe_path}" download="{filename}" target="_blank" 
                       style="display: inline-block; background-color: #2563eb; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: bold; font-family: sans-serif; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                       {btn_text}
                    </a>
                </div>
                """

    # 返回数据顺序必须与 app.py 的 outputs 一致
    return (
        fresh_settings["last_dir"],
        fresh_settings["api_key"],
        current_html,  # 恢复的下载按钮
        restored_image,  # ⬇️ 新增：恢复的图片 (对应 result_image)
        fresh_settings["save_path"],
        fresh_settings["file_prefix"],
        fresh_settings["language"],
        fresh_settings["api_key"]
    )