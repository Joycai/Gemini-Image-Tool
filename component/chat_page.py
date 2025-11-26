import gradio as gr
import i18n
import database as db
import api_client
import os
import time
import random
import string
from PIL import Image
from typing import List, Dict, Tuple, Optional, Any
from google import genai

from config import (
    MODEL_SELECTOR_CHOICES,
    MODEL_SELECTOR_DEFAULT,
    AR_SELECTOR_CHOICES,
    AR_SELECTOR_DEFAULT,
    RES_SELECTOR_CHOICES,
    RES_SELECTOR_DEFAULT
)

# 定义 Chatbot 历史记录的类型别名，以增加可读性
ChatHistory = List[Dict[str, Any]]
# 定义会话状态的类型别名
SessionState = Optional[Dict[str, Any]]

def handle_chat_submission(
    chat_input: Dict[str, Any], 
    chat_history: ChatHistory, 
    genai_client: Optional[genai.Client], 
    session_state: SessionState, 
    model: str, 
    ar: str, 
    res: str
) -> Tuple[ChatHistory, SessionState, None]:
    """
    处理聊天提交的核心逻辑。

    Args:
        chat_input: 来自 gr.MultimodalTextbox 的输入。
        chat_history: 当前的聊天历史记录。
        genai_client: Google GenAI 的客户端实例。
        session_state: 当前的会话状态字典。
        model: 使用的模型 ID。
        ar: 图像宽高比。
        res: 图像分辨率。

    Returns:
        一个元组，包含更新后的聊天历史、会话状态和用于清空输入框的 None。
    """
    if not chat_input or (not chat_input.get('text') and not chat_input.get('files')):
        return chat_history, session_state, None

    # --- 会话管理 ---
    session_id: str
    chat_obj: Optional[genai.Chat]
    if session_state is None:
        session_id = f"chat_{int(time.time())}"
        chat_obj = None
        gr.Info("✨ New chat session started.")
    else:
        session_id = session_state["id"]
        chat_obj = session_state["session_obj"]

    # --- 格式化用户输入 (拆分为多条消息) ---
    if chat_input.get('files'):
        for file_path in chat_input['files']:
            chat_history.append({
                "role": "user",
                "content": gr.Image(value=file_path, show_label=False, interactive=False)
            })
    if chat_input.get('text'):
        chat_history.append({
            "role": "user", 
            "content": chat_input['text']
        })

    # --- 格式化 API 输入 ---
    prompt_parts: List[Any] = []
    if chat_input.get('files'):
        for file_path in chat_input['files']:
            prompt_parts.append(Image.open(file_path))
    if chat_input.get('text'):
        prompt_parts.append(chat_input['text'])

    # 调用 API
    updated_chat_obj, response_parts = api_client.call_google_chat(
        genai_client, chat_obj, prompt_parts, model, ar, res
    )

    # 更新会话状态字典
    updated_session_state: SessionState = {"id": session_id, "session_obj": updated_chat_obj}

    # --- 处理 API 返回 (拆分为多条消息) ---
    save_dir: str = db.get_setting("save_path")
    if not save_dir:
        gr.Warning("Save path is not set. Images will not be saved.")

    text_parts: List[str] = [part for part in response_parts if isinstance(part, str)]
    image_parts: List[Image.Image] = [part for part in response_parts if not isinstance(part, str)]

    if text_parts:
        combined_text: str = "\n".join(text_parts)
        chat_history.append({"role": "assistant", "content": combined_text})

    for img_part in image_parts:
        if save_dir:
            try:
                os.makedirs(save_dir, exist_ok=True)
                timestamp: int = int(time.time() * 1000)
                filename: str = f"{session_id}_{timestamp}.png"
                filepath: str = os.path.join(save_dir, filename)
                img_part.save(filepath)
                chat_history.append({
                    "role": "assistant",
                    "content": gr.Image(value=filepath, show_label=False, interactive=False)
                })
            except Exception as e:
                error_msg: str = f"Failed to save image: {e}"
                gr.Warning(error_msg)
                chat_history.append({"role": "assistant", "content": error_msg})
        else:
            chat_history.append({
                "role": "assistant",
                "content": gr.Image(value=img_part, show_label=False, interactive=False)
            })

    return chat_history, updated_session_state, None

def clear_chat() -> Tuple[List, None]:
    """清空聊天记录和会话状态"""
    return [], None

def render(state_api_key: gr.State) -> Dict[str, gr.Component]:
    """
    渲染聊天页面的 UI 组件。
    """
    settings: Dict[str, Any] = db.get_all_settings()

    with gr.Row(equal_height=False):
        # --- 左侧：素材库 ---
        with gr.Column(scale=4):
            with gr.Group():
                gr.Markdown(f"#### {i18n.get('home_assets_title')}")
                with gr.Tabs():
                    with gr.TabItem(i18n.get("home_assets_tab_local")):
                        with gr.Row():
                            chat_dir_input = gr.Textbox(value=settings["last_dir"], label=i18n.get("home_assets_label_dirPath"), scale=3)
                            chat_btn_select_dir = gr.Button(i18n.get("home_assets_btn_browse"), scale=0, min_width=50)
                            chat_btn_refresh = gr.Button(i18n.get("home_assets_btn_refresh"), scale=0, min_width=50)
                        with gr.Row():
                            chat_recursive_checkbox = gr.Checkbox(label=i18n.get("home_assets_label_recursive"), value=False)
                            chat_size_slider = gr.Slider(2, 6, value=4, step=1, label=i18n.get("home_assets_label_columns"))
                        chat_gallery_source = gr.Gallery(label=i18n.get("home_assets_label_source"), columns=4, height=600, allow_preview=False, object_fit="contain")
                    
                    with gr.TabItem(i18n.get("home_assets_tab_upload")):
                        chat_upload_button = gr.UploadButton(i18n.get("home_assets_btn_upload"), file_types=["image"], file_count="multiple")
                        chat_gallery_upload = gr.Gallery(label="Uploaded", columns=4, height=600, allow_preview=False, object_fit="contain", interactive=True)

                chat_info_box = gr.Markdown(i18n.get("home_assets_info_ready"))
                state_chat_marked_for_add = gr.State(None)

        # --- 右侧：聊天界面 ---
        with gr.Column(scale=6):
            with gr.Group():
                gr.Markdown(f"### {i18n.get('chat_title')}")
                
                chatbot = gr.Chatbot(label=i18n.get("chat_chatbot_label"), height=700, type="messages")
                
                chat_input = gr.MultimodalTextbox(
                    file_types=["image"],
                    label=i18n.get("chat_input_label"),
                    placeholder=i18n.get("chat_input_placeholder"),
                    show_label=False
                )

                with gr.Row():
                    chat_model_selector = gr.Dropdown(choices=MODEL_SELECTOR_CHOICES, value=MODEL_SELECTOR_DEFAULT, label=i18n.get("home_control_model_label"), scale=2, allow_custom_value=True)
                    chat_ar_selector = gr.Dropdown(choices=i18n.get_translated_choices(AR_SELECTOR_CHOICES), value=AR_SELECTOR_DEFAULT, label=i18n.get("home_control_ratio_label"), scale=1)
                    chat_res_selector = gr.Dropdown(choices=RES_SELECTOR_CHOICES, value=RES_SELECTOR_DEFAULT, label=i18n.get("home_control_resolution_label"), scale=1)
                
                with gr.Row():
                    chat_btn_send = gr.Button(i18n.get("chat_btn_send"), variant="primary", scale=3)
                    chat_btn_clear = gr.Button(i18n.get("chat_btn_clear"), variant="stop", scale=1)

    return {
        "chat_dir_input": chat_dir_input,
        "chat_btn_select_dir": chat_btn_select_dir,
        "chat_btn_refresh": chat_btn_refresh,
        "chat_recursive_checkbox": chat_recursive_checkbox,
        "chat_size_slider": chat_size_slider,
        "chat_gallery_source": chat_gallery_source,
        "chat_upload_button": chat_upload_button,
        "chat_gallery_upload": chat_gallery_upload,
        "chat_info_box": chat_info_box,
        "state_chat_marked_for_add": state_chat_marked_for_add,
        "chatbot": chatbot,
        "chat_input": chat_input,
        "chat_model_selector": chat_model_selector,
        "chat_ar_selector": chat_ar_selector,
        "chat_res_selector": chat_res_selector,
        "chat_btn_send": chat_btn_send,
        "chat_btn_clear": chat_btn_clear
    }
