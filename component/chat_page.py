import os
import time
from typing import List, Dict, Tuple, Optional, Any

import gradio as gr
from PIL import Image

import database as db
import i18n
# import api_client # 移除未使用的导入
from config import (
    MODEL_SELECTOR_CHOICES,
    MODEL_SELECTOR_DEFAULT,
    AR_SELECTOR_CHOICES,
    AR_SELECTOR_DEFAULT,
    RES_SELECTOR_CHOICES,
    RES_SELECTOR_DEFAULT
)
from component import assets_block


# 定义类型别名
ChatHistory = List[Dict[str, Any]]
SessionState = Optional[Dict[str, Any]]

def add_image_to_chat_input(
    evt: gr.SelectData,
    current_input: Dict[str, Any]
) -> Dict[str, Any]:
    """
    将从画廊选择的图片添加到多模态输入框中。
    """
    if not evt.value:
        return current_input

    selected_path = evt.value['image']['path']
    
    if current_input is None:
        current_input = {"text": "", "files": []}
    
    if selected_path not in current_input["files"]:
        current_input["files"].append(selected_path)
        
    return current_input

def prepare_chat_display(chat_input: Dict[str, Any], chat_history: ChatHistory) -> Tuple[ChatHistory, None, gr.update, gr.update, Dict[str, Any]]:
    """
    立即响应用户输入，更新聊天记录，禁用输入，并缓冲原始输入。
    """
    if not chat_input or (not chat_input.get('text') and not chat_input.get('files')):
        return chat_history, None, gr.update(), gr.update(), chat_input

    if chat_input.get('files'):
        for file_path in chat_input['files']:
            chat_history.append({"role": "user", "content": gr.Image(value=file_path, show_label=False, interactive=False)})
    if chat_input.get('text'):
        chat_history.append({"role": "user", "content": chat_input['text']})
    
    chat_history.append({"role": "assistant", "content": "🤔 Thinking..."})

    return chat_history, None, gr.update(interactive=False), gr.update(interactive=False), chat_input

def handle_bot_response(
    response_parts: Optional[List[Any]], 
    session_state_from_task: SessionState, 
    chat_history: ChatHistory
) -> Tuple[ChatHistory, SessionState]:
    """
    处理来自后台任务的机器人响应。
    """
    if chat_history and chat_history[-1]["content"] == "🤔 Thinking...":
        chat_history.pop()

    if response_parts is None or session_state_from_task is None:
        chat_history.append({"role": "assistant", "content": "😥 Oops, something went wrong."})
        return chat_history, None

    session_id: str = session_state_from_task["id"]
    
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
                chat_history.append({"role": "assistant", "content": gr.Image(value=filepath, show_label=False, interactive=False)})
            except (IOError, OSError) as e:
                error_msg: str = f"Failed to save image: {e}"
                gr.Warning(error_msg)
                chat_history.append({"role": "assistant", "content": error_msg})
        else:
            chat_history.append({"role": "assistant", "content": gr.Image(value=img_part, show_label=False, interactive=False)})

    return chat_history, session_state_from_task

def clear_chat() -> Tuple[List, None]:
    """清空聊天记录和会话状态"""
    return [], None

def render() -> Dict[str, gr.Component]:
    """
    渲染聊天页面的 UI 组件。
    """
    settings: Dict[str, Any] = db.get_all_settings()

    with gr.Row(equal_height=False):
        with gr.Column(scale=4):
            # 渲染素材库块
            assets_ui = assets_block.render_assets_block(prefix="chat_")
            state_chat_marked_for_add = gr.State(None)

        with gr.Column(scale=6):
            with gr.Group():
                gr.Markdown(f"### {i18n.get('chat_title')}")
                
                chatbot = gr.Chatbot(label=i18n.get("chat_chatbot_label"), height=700, type="messages")
                
                chat_input = gr.MultimodalTextbox(
                    file_types=["image"],
                    label=i18n.get("chat_input_label"),
                    placeholder=i18n.get("chat_input_placeholder"),
                    show_label=False,
                    submit_btn=True
                )

                with gr.Row():
                    chat_model_selector = gr.Dropdown(choices=MODEL_SELECTOR_CHOICES, value=MODEL_SELECTOR_DEFAULT, label=i18n.get("home_control_model_label"), scale=2, allow_custom_value=True)
                    chat_ar_selector = gr.Dropdown(choices=i18n.get_translated_choices(AR_SELECTOR_CHOICES), value=AR_SELECTOR_DEFAULT, label=i18n.get("home_control_ratio_label"), scale=1)
                    chat_res_selector = gr.Dropdown(choices=RES_SELECTOR_CHOICES, value=RES_SELECTOR_DEFAULT, label=i18n.get("home_control_resolution_label"), scale=1)
                
                with gr.Row():
                    chat_btn_clear = gr.Button(i18n.get("chat_btn_clear"), variant="stop", scale=1)

    return {
        **assets_ui,
        "state_chat_marked_for_add": state_chat_marked_for_add,
        "chatbot": chatbot,
        "chat_input": chat_input,
        "chat_model_selector": chat_model_selector,
        "chat_ar_selector": chat_ar_selector,
        "chat_res_selector": chat_res_selector,
        "chat_btn_clear": chat_btn_clear
    }
