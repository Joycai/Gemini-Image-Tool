import gradio as gr
import i18n
import database as db
from config import (
    MODEL_SELECTOR_CHOICES,
    MODEL_SELECTOR_DEFAULT,
    AR_SELECTOR_CHOICES,
    AR_SELECTOR_DEFAULT,
    RES_SELECTOR_CHOICES,
    RES_SELECTOR_DEFAULT
)

def render(state_api_key):
    """
    渲染聊天页面的 UI 组件。
    """
    settings = db.get_all_settings()

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
                
                # 对话历史记录
                chatbot = gr.Chatbot(label=i18n.get("chat_chatbot_label"), height=700, type="messages")
                
                # 多模态输入框
                chat_input = gr.MultimodalTextbox(
                    file_types=["image"],
                    label=i18n.get("chat_input_label"),
                    placeholder=i18n.get("chat_input_placeholder"),
                    show_label=False
                )

                # 控制按钮和参数
                with gr.Row():
                    chat_model_selector = gr.Dropdown(choices=MODEL_SELECTOR_CHOICES, value=MODEL_SELECTOR_DEFAULT, label=i18n.get("home_control_model_label"), scale=2, allow_custom_value=True)
                    chat_ar_selector = gr.Dropdown(choices=i18n.get_translated_choices(AR_SELECTOR_CHOICES), value=AR_SELECTOR_DEFAULT, label=i18n.get("home_control_ratio_label"), scale=1)
                    chat_res_selector = gr.Dropdown(choices=RES_SELECTOR_CHOICES, value=RES_SELECTOR_DEFAULT, label=i18n.get("home_control_resolution_label"), scale=1)
                
                with gr.Row():
                    chat_btn_send = gr.Button(i18n.get("chat_btn_send"), variant="primary", scale=3)
                    chat_btn_clear = gr.Button(i18n.get("chat_btn_clear"), variant="stop", scale=1)

    # 返回所有需要被外部引用的组件
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
