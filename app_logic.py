from typing import List, Tuple, Optional
import os
import time
import sys
import base64  # ⬇️ 新增
import threading
import tkinter as tk
from tkinter import filedialog
import gradio as gr

# 引入模块
import database as db
import api_client
import logger_utils
import i18n

# --- 全局任务状态管理 ---
TASK_STATE = {
    "status": "idle",
    "timestamp": 0,
    "result_image": None,
    "result_path": None,
    "error_msg": None,
    "ui_updated": True
}


def reset_task_state():
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


# ⬇️ 修改：使用 Base64 嵌入图片数据，实现无视路径的下载
def _generate_download_html(full_path):
    if not full_path or not os.path.exists(full_path):
        return get_disabled_download_html()

    filename = os.path.basename(full_path)

    try:
        # 1. 读取文件二进制数据
        with open(full_path, "rb") as f:
            image_data = f.read()

        # 2. 转为 Base64 字符串
        b64_str = base64.b64encode(image_data).decode('utf-8')

        # 3. 确定 MIME 类型
        ext = os.path.splitext(filename)[1].lower().replace(".", "")
        if ext == "jpg": ext = "jpeg"
        mime_type = f"image/{ext}"

        # 4. 构造 Data URI (这就是把图片变成了巨长的一行字)
        href = f"data:{mime_type};base64,{b64_str}"

        btn_text = i18n.get("btn_download_ready") + f" ({filename})"

        return f"""
        <div style="text-align: center; margin-top: 10px;">
            <a href="{href}" download="{filename}"
               style="display: inline-block; background-color: #2563eb; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: bold; font-family: sans-serif; box-shadow: 0 2px 4px rgba(0,0,0,0.2); cursor: pointer;">
               {btn_text}
            </a>
        </div>
        """
    except Exception as e:
        logger_utils.log(f"❌ HTML 生成失败: {e}")
        return get_disabled_download_html()


# --- 核心：后台任务线程函数 ---
def _background_worker(prompt, img_paths, key, model, ar, res):
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
def start_generation_task(
    prompt: str,
    img_paths: List[str],
    key: str,
    model: str,
    ar: str,
    res: str
) -> None:
    if TASK_STATE["status"] == "running":
        gr.Warning(i18n.get("log_task_running"))
        return

    reset_task_state()

    t = threading.Thread(
        target=_background_worker,
        args=(prompt, img_paths, key, model, ar, res)
    )
    t.start()
    gr.Info(i18n.get("log_task_submitted"))


# --- UI 轮询函数 ---
def poll_task_status():
    # 1. 运行中
    if TASK_STATE["status"] == "running":
        # 返回：圖片不變，下載按鈕不可用且顯示 "生成中..."
        return gr.skip(), gr.DownloadButton(label=i18n.get("log_new_task"), interactive=False), gr.skip()

    # 2. 完成且未更新 UI
    if not TASK_STATE["ui_updated"]:
        if TASK_STATE["status"] == "success":
            TASK_STATE["ui_updated"] = True

            # [修改點] 直接返回文件路徑給 DownloadButton
            # update(value=路徑, label="下載", interactive=True)
            new_btn = gr.DownloadButton(
                label=i18n.get("btn_download_ready") + f" ({os.path.basename(TASK_STATE['result_path'])})",
                value=TASK_STATE["result_path"],
                interactive=True,
                visible=True
            )
            return TASK_STATE["result_image"], new_btn, load_output_gallery()

        elif TASK_STATE["status"] == "error":
            TASK_STATE["ui_updated"] = True
            gr.Warning(i18n.get("log_task_failed", error_msg=TASK_STATE['error_msg']))
            # 錯誤狀態：按鈕變回不可用
            return None, gr.DownloadButton(label=i18n.get("btn_download_placeholder"), interactive=False), gr.skip()

    return gr.skip(), gr.skip(), gr.skip()


# ... (以下函数保持不变) ...
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


# ⬇️ 初始化函数
def init_app_data():
    fresh_settings = db.get_all_settings()
    logger_utils.log("🔄 正在恢复用户会话...")

    # 1. 默认状态
    current_html = get_disabled_download_html()
    restored_image = None

    # 如果有恢復的任務，返回對應的 DownloadButton 更新
    if TASK_STATE["status"] == "success" and TASK_STATE["result_path"]:
        current_download_btn = gr.DownloadButton(
            label=i18n.get("btn_download_ready"),
            value=TASK_STATE["result_path"],
            interactive=True
        )
    else:
        current_download_btn = gr.DownloadButton(label=i18n.get("btn_download_placeholder"), interactive=False)

    return (
        fresh_settings["last_dir"],
        fresh_settings["api_key"],
        current_download_btn,
        restored_image,
        fresh_settings["save_path"],
        fresh_settings["file_prefix"],
        fresh_settings["language"],
        fresh_settings["api_key"]
    )