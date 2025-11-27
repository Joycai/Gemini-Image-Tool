# pylint: disable=no-member
import sys
import os

import gradio as gr

# 导入回调函数和 Ticker 实例
from gapp.app_logic import (
    poll_task_status_callback,
    start_generation_task,
    init_app_data,
    create_genai_client,
    start_chat_task,
    poll_chat_task_status_callback,
    restart_app
)
from common import logger_utils as app_logic_logger, database as db, i18n
from common.logger_utils import get_logs
from gapp.ticker import ticker_instance

from gapp.component import history_page, chat_page, main_page, assets_block, settings_page, header
from common.config import get_allowed_paths, UPLOAD_DIR, OUTPUT_DIR

# ⬇️ 新增 JS：用于切换深色模式
with open("assets/script.js", "r", encoding="utf-8") as f:
    js_toggle_theme = f.read()

with open("assets/style.css", "r", encoding="utf-8") as f:
    custom_css = f.read()

# 创建临时目录
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# 显式注册回调，确保顺序正确
ticker_instance.register(poll_task_status_callback)
ticker_instance.register(poll_chat_task_status_callback)
ticker_instance.register(get_logs)

# --- 顶层辅助函数 ---
def save_and_update_client(key, path, prefix, lang):
    db.save_setting("api_key", key)
    db.save_setting("save_path", path)
    db.save_setting("file_prefix", prefix)
    db.save_setting("language", lang)
    app_logic_logger.log(i18n.get("logic_info_configSaved"))
    gr.Info(i18n.get("logic_info_configSaved"))
    
    new_client = create_genai_client(key)
    # 同时更新历史记录页面
    return key, new_client, history_page.load_output_gallery()


with gr.Blocks(title=i18n.get("app_title")) as app:
    gr.HTML(f"<style>{custom_css}</style>")

    # 全局状态
    settings = db.get_all_settings()
    state_api_key = gr.State(value=settings["api_key"])
    state_main_dir_images = gr.State(value=[])
    state_chat_dir_images = gr.State(value=[])
    state_genai_client = gr.State(value=None)
    state_chat_session = gr.State(value=None)
    # 用于轮询的聊天状态
    state_response_parts = gr.State()
    state_updated_session = gr.State()
    # 用于在异步任务间传递用户输入的缓冲区
    state_chat_input_buffer = gr.State()


    # 1. 顶部工具栏 (Header)
    btn_theme = header.render()

    # 2. Tab 容器
    with gr.Tabs() as main_tabs:
        with gr.TabItem(i18n.get("app_tab_home"), id="tab_home"):
            main_ui = main_page.render()
        
        with gr.TabItem(i18n.get("app_tab_chat"), id="tab_chat"):
            chat_ui = chat_page.render()

        with gr.TabItem(i18n.get("app_tab_history"), id="tab_history"):
            history_ui = history_page.render()

        with gr.TabItem(i18n.get("app_tab_settings"), id="tab_settings"):
            settings_ui = settings_page.render()


    # ================= 业务逻辑绑定 =================

    # 主题切换
    btn_theme.click(None, None, None, js=js_toggle_theme)

    # --- 设置页逻辑 ---
    settings_ui["btn_save"].click(
        save_and_update_client,
        inputs=[settings_ui["api_key"], settings_ui["path"], settings_ui["prefix"], settings_ui["lang"]],
        outputs=[state_api_key, state_genai_client, history_ui["gallery_output_history"]]
    )
    settings_ui["btn_clear_cache"].click(fn=settings_page.clear_cache)
    settings_ui["btn_restart"].click(fn=restart_app, inputs=None, outputs=None)
    settings_ui["btn_export_prompts"].click(
        fn=settings_page.export_prompts_logic,
        inputs=None,
        outputs=[settings_ui["exported_file"]]
    )
    settings_ui["btn_import_prompts"].upload(
        fn=settings_page.import_prompts_logic,
        inputs=[settings_ui["btn_import_prompts"]],
        outputs=[main_ui["prompt_dropdown"]]
    )


    # --- 主页: Prompt ---
    main_ui["btn_save_prompt"].click(main_page.save_prompt_to_db,
                                     [main_ui["prompt_title_input"], main_ui["prompt_input"]],
                                     [main_ui["prompt_dropdown"]])
    main_ui["btn_load_prompt"].click(main_page.load_prompt_to_ui, [main_ui["prompt_dropdown"]],
                                     [main_ui["prompt_input"]])
    main_ui["btn_del_prompt"].click(main_page.delete_prompt_from_db, [main_ui["prompt_dropdown"]],
                                    [main_ui["prompt_dropdown"]])

    # --- 主页: 左侧素材 ---
    main_ui["main_btn_select_dir"].click(lambda: assets_block.open_folder_dialog() or gr.skip(), None, main_ui["main_dir_input"])

    main_load_inputs = [main_ui["main_dir_input"], main_ui["main_recursive_checkbox"]]
    main_load_outputs = [state_main_dir_images, main_ui["main_info_box"]]

    main_ui["main_dir_input"].change(assets_block.load_images_from_dir, main_load_inputs, main_load_outputs).then(lambda x: x,
                                                                                                                  state_main_dir_images,
                                                                                                                  main_ui["main_gallery_source"])
    main_ui["main_btn_refresh"].click(assets_block.load_images_from_dir, main_load_inputs, main_load_outputs).then(lambda x: x,
                                                                                                                   state_main_dir_images,
                                                                                                                   main_ui["main_gallery_source"])
    main_ui["main_recursive_checkbox"].change(assets_block.load_images_from_dir, main_load_inputs, main_load_outputs).then(lambda x: x,
                                                                                                                           state_main_dir_images,
                                                                                                                           main_ui["main_gallery_source"])
    
    main_ui["main_upload_button"].upload(assets_block.handle_upload, main_ui["main_upload_button"], main_ui["main_gallery_upload"])
    main_ui["main_size_slider"].change(lambda x: gr.Gallery(columns=x), main_ui["main_size_slider"], main_ui["main_gallery_source"])

    # --- 聊天页: 左侧素材 ---
    chat_ui["chat_btn_select_dir"].click(lambda: assets_block.open_folder_dialog() or gr.skip(), None, chat_ui["chat_dir_input"])

    chat_load_inputs = [chat_ui["chat_dir_input"], chat_ui["chat_recursive_checkbox"]]
    chat_load_outputs = [state_chat_dir_images, chat_ui["chat_info_box"]]

    chat_ui["chat_dir_input"].change(assets_block.load_images_from_dir, chat_load_inputs, chat_load_outputs).then(lambda x: x,
                                                                                                                  state_chat_dir_images,
                                                                                                                  chat_ui["chat_gallery_source"])
    chat_ui["chat_btn_refresh"].click(assets_block.load_images_from_dir, chat_load_inputs, chat_load_outputs).then(lambda x: x,
                                                                                                                   state_chat_dir_images,
                                                                                                                   chat_ui["chat_gallery_source"])
    chat_ui["chat_recursive_checkbox"].change(assets_block.load_images_from_dir, chat_load_inputs, chat_load_outputs).then(lambda x: x,
                                                                                                                           state_chat_dir_images,
                                                                                                                           chat_ui["chat_gallery_source"])
    
    chat_ui["chat_upload_button"].upload(assets_block.handle_upload, chat_ui["chat_upload_button"], chat_ui["chat_gallery_upload"])
    chat_ui["chat_size_slider"].change(lambda x: gr.Gallery(columns=x), chat_ui["chat_size_slider"], chat_ui["chat_gallery_source"])


    # --- 历史记录页 ---
    history_ui["btn_open_out_dir"].click(fn=history_page.open_output_folder)
    history_ui["btn_refresh_history"].click(fn=history_page.load_output_gallery, outputs=history_ui["gallery_output_history"])
    history_ui["gallery_output_history"].select(
        history_page.on_gallery_select,
        inputs=[history_ui["gallery_output_history"]],
        outputs=[
            history_ui["btn_download_hist"],
            history_ui["btn_delete_hist"],
            history_ui["state_hist_selected_path"]
        ]
    )
    history_ui["btn_delete_hist"].click(
        history_page.delete_output_file,
        inputs=[history_ui["state_hist_selected_path"]],
        outputs=[
            history_ui["gallery_output_history"],
            history_ui["btn_download_hist"],
            history_ui["btn_delete_hist"]
        ]
    )

    # --- 图片选择与移除 ---
    main_ui["main_gallery_source"].select(main_page.mark_for_add, None, main_ui["main_state_marked_for_add"])
    main_ui["main_gallery_upload"].select(main_page.mark_for_add, None, main_ui["main_state_marked_for_add"])
    main_ui["gallery_selected"].select(main_page.mark_for_remove, None, main_ui["state_marked_for_remove"])
    chat_ui["chat_gallery_source"].select(chat_page.add_image_to_chat_input, inputs=[chat_ui["chat_input"]], outputs=[chat_ui["chat_input"]])
    chat_ui["chat_gallery_upload"].select(chat_page.add_image_to_chat_input, inputs=[chat_ui["chat_input"]], outputs=[chat_ui["chat_input"]])


    main_ui["btn_add_to_selected"].click(
        main_page.add_marked_to_selected,
        [main_ui["main_state_marked_for_add"], main_ui["state_selected_images"]],
        main_ui["state_selected_images"]
    ).then(
        lambda x: x,
        main_ui["state_selected_images"],
        main_ui["gallery_selected"]
    )

    main_ui["btn_remove_from_selected"].click(
        main_page.remove_marked_from_selected,
        [main_ui["state_marked_for_remove"], main_ui["state_selected_images"]],
        main_ui["state_selected_images"]
    ).then(
        lambda x: x,
        main_ui["state_selected_images"],
        main_ui["gallery_selected"]
    ).then(lambda : gr.Gallery(selected_index=None), outputs=[main_ui["gallery_selected"]])


    # --- 主页: 生成 (异步模式) ---
    gen_inputs = [
        main_ui["prompt_input"],
        main_ui["state_selected_images"],
        state_api_key,
        main_ui["model_selector"],
        main_ui["ar_selector"],
        main_ui["res_selector"]
    ]
    main_ui["btn_send"].click(start_generation_task, gen_inputs, None)
    main_ui["btn_retry"].click(start_generation_task, gen_inputs, None)

    # --- 聊天页: 对话逻辑 (异步模式) ---
    chat_ui["chat_input"].submit(
        chat_page.prepare_chat_display,
        inputs=[chat_ui["chat_input"], chat_ui["chatbot"]],
        outputs=[chat_ui["chatbot"], chat_ui["chat_input"], chat_ui["chat_input"], chat_ui["chat_btn_clear"], state_chat_input_buffer]
    ).then(
        start_chat_task,
        inputs=[
            state_chat_input_buffer,
            state_genai_client,
            state_chat_session,
            chat_ui["chat_model_selector"],
            chat_ui["chat_ar_selector"],
            chat_ui["chat_res_selector"]
        ],
        outputs=None
    )
    
    state_response_parts.change(
        chat_page.handle_bot_response,
        inputs=[state_response_parts, state_updated_session, chat_ui["chatbot"]],
        outputs=[chat_ui["chatbot"], state_chat_session]
    )

    chat_ui["chat_btn_clear"].click(
        chat_page.clear_chat,
        inputs=None,
        outputs=[chat_ui["chatbot"], state_chat_session]
    )


    # --- 全局定时器 ---
    poll_timer = gr.Timer(1)
    poll_timer.tick(
        ticker_instance.tick,
        inputs=None,
        outputs=[
            main_ui["result_image"],
            main_ui["btn_download"],
            state_response_parts,
            state_updated_session,
            chat_ui["chat_input"],
            chat_ui["chat_btn_clear"],
            main_ui["log_output"]
        ]
    )

    # --- 主页: 结果触发历史刷新 ---
    main_ui["result_image"].change(
        fn=history_page.load_output_gallery,
        inputs=None,
        outputs=[history_ui["gallery_output_history"]]
    )


    # --- 启动加载 ---
    app.load(
        init_app_data,
        inputs=None,
        outputs=[
            main_ui["main_dir_input"],
            state_api_key,
            state_genai_client,
            main_ui["btn_download"],
            main_ui["result_image"],
            settings_ui["path"],
            settings_ui["prefix"],
            settings_ui["lang"],
            settings_ui["api_key"]
        ]
    ).then(
        assets_block.load_images_from_dir,
        inputs=[main_ui["main_dir_input"], main_ui["main_recursive_checkbox"]],
        outputs=[state_main_dir_images, main_ui["main_info_box"]]
    ).then(
        lambda x: x,
        inputs=[state_main_dir_images],
        outputs=[main_ui["main_gallery_source"]]
    ).then(
        history_page.load_output_gallery,
        inputs=None,
        outputs=[history_ui["gallery_output_history"]]
    )

if __name__ == "__main__":
    # ================= 🚑 PyInstaller noconsole 修复补丁 =================
    # 当使用 --noconsole 打包时，sys.stdout 和 sys.stderr 是 None
    # 这会导致 uvicorn 日志初始化失败。我们需要给它一个假的流对象。

    class NullWriter:
        def write(self, data): pass

        def flush(self): pass

        def isatty(self): return False

        def fileno(self): return -1


    if sys.stdout is None:
        sys.stdout = NullWriter()
    if sys.stderr is None:
        sys.stderr = NullWriter()
    # =====================================================================

    allowed_paths = get_allowed_paths()
    print(f"✅ Allowed Paths: {len(allowed_paths)}")
    app.launch(inbrowser=True, server_name="0.0.0.0", server_port=7860, allowed_paths=allowed_paths)
