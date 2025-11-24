# ================= 🐛 PyCharm Debugger 修复补丁 =================
import asyncio
import sys
import os

if sys.gettrace() is not None:
    _pycharm_run = asyncio.run


    def _fixed_run(main, *, debug=None, loop_factory=None):
        return _pycharm_run(main, debug=debug)


    asyncio.run = _fixed_run
# ==============================================================

import gradio as gr
import database as db
import i18n
import app_logic
import logger_utils
from component import header, main_page, settings_page
from config import get_allowed_paths, UPLOAD_DIR, OUTPUT_DIR

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

with gr.Blocks(title=i18n.get("app_title")) as demo:
    gr.HTML(f"<style>{custom_css}</style>")

    # 全局状态
    settings = db.get_all_settings()
    state_api_key = gr.State(value=settings["api_key"])
    state_current_dir_images = gr.State(value=[])

    # 1. 顶部工具栏 (Header)
    btn_restart, btn_theme = header.render()

    # 预创建输出历史组件 (供 main_page 使用)
    gallery_output_history = gr.Gallery(label="Outputs", columns=4, height=520, allow_preview=True, interactive=False,
                                        object_fit="contain", render=False)

    # 2. Tab 容器
    with gr.Tabs() as main_tabs:
        with gr.TabItem(i18n.get("app_tab_home"), id="tab_home"):
            main_ui = main_page.render(state_api_key, gallery_output_history)

        with gr.TabItem(i18n.get("app_tab_settings"), id="tab_settings"):
            settings_ui = settings_page.render()


    # ================= 业务逻辑绑定 =================

    # 主题切换
    btn_theme.click(None, None, None, js=js_toggle_theme)

    # 日志刷新
    log_timer = gr.Timer(1)
    log_timer.tick(logger_utils.get_logs, outputs=main_ui["log_output"])

    # --- 设置页逻辑 ---
    settings_ui["btn_save"].click(
        app_logic.save_cfg_wrapper,
        inputs=[settings_ui["api_key"], settings_ui["path"], settings_ui["prefix"], settings_ui["lang"]],
        outputs=[state_api_key, gallery_output_history]
    )
    settings_ui["btn_clear_cache"].click(fn=app_logic.clear_cache)


    # --- 主页: Prompt ---
    main_ui["btn_save_prompt"].click(app_logic.save_prompt_to_db,
                                     [main_ui["prompt_title_input"], main_ui["prompt_input"]],
                                     [main_ui["prompt_dropdown"]])
    main_ui["btn_load_prompt"].click(app_logic.load_prompt_to_ui, [main_ui["prompt_dropdown"]],
                                     [main_ui["prompt_input"]])
    main_ui["btn_del_prompt"].click(app_logic.delete_prompt_from_db, [main_ui["prompt_dropdown"]],
                                    [main_ui["prompt_dropdown"]])

    # --- 主页: 左侧素材 ---
    main_ui["btn_select_dir"].click(lambda: app_logic.open_folder_dialog() or gr.skip(), None, main_ui["dir_input"])

    load_inputs = [main_ui["dir_input"]]
    load_outputs = [state_current_dir_images, main_ui["info_box"]]

    main_ui["dir_input"].change(app_logic.load_images_from_dir, load_inputs, load_outputs).then(lambda x: x,
                                                                                                state_current_dir_images,
                                                                                                main_ui[
                                                                                                    "gallery_source"])
    main_ui["btn_refresh"].click(app_logic.load_images_from_dir, load_inputs, load_outputs).then(lambda x: x,
                                                                                                 state_current_dir_images,
                                                                                                 main_ui[
                                                                                                     "gallery_source"])
    
    # 上传逻辑
    main_ui["upload_button"].upload(
        app_logic.handle_upload,
        main_ui["upload_button"],
        main_ui["gallery_upload"]
    )

    # [新增] 历史画廊交互逻辑

    # 1. 选中图片
    gallery_output_history.select(
        fn=app_logic.on_gallery_select,
        inputs=[gallery_output_history],  # 将画廊自身作为输入，获取当前列表
        outputs=[
            main_ui["btn_download_hist"],  # 更新下载按钮
            main_ui["btn_delete_hist"],  # 更新删除按钮
            main_ui["state_hist_selected_path"]  # 更新选中路径状态
        ]
    )

    # 2. 删除图片
    main_ui["btn_delete_hist"].click(
        fn=app_logic.delete_output_file,
        inputs=[main_ui["state_hist_selected_path"]],
        outputs=[
            gallery_output_history,  # 刷新画廊
            main_ui["btn_download_hist"],  # 重置下载按钮
            main_ui["btn_delete_hist"]  # 重置删除按钮
        ]
    )

    main_ui["size_slider"].change(lambda x: gr.Gallery(columns=x), main_ui["size_slider"], main_ui["gallery_source"])

    # --- 主页: 图片选择与移除 (新逻辑) ---
    main_ui["gallery_source"].select(
        app_logic.mark_for_add,
        None,
        main_ui["state_marked_for_add"]
    )
    main_ui["gallery_upload"].select(
        app_logic.mark_for_add,
        None,
        main_ui["state_marked_for_add"]
    )
    main_ui["gallery_selected"].select(
        app_logic.mark_for_remove,
        None,
        main_ui["state_marked_for_remove"]
    )

    main_ui["btn_add_to_selected"].click(
        app_logic.add_marked_to_selected,
        [main_ui["state_marked_for_add"], main_ui["state_selected_images"]],
        main_ui["state_selected_images"]
    ).then(
        lambda x: x,
        main_ui["state_selected_images"],
        main_ui["gallery_selected"]
    )

    main_ui["btn_remove_from_selected"].click(
        app_logic.remove_marked_from_selected,
        [main_ui["state_marked_for_remove"], main_ui["state_selected_images"]],
        main_ui["state_selected_images"]
    ).then(
        lambda x: x,
        main_ui["state_selected_images"],
        main_ui["gallery_selected"]
    )


    # --- 主页: 生成 (异步模式) ---
    gen_inputs = [
        main_ui["prompt_input"],
        main_ui["state_selected_images"],
        state_api_key,
        main_ui["model_selector"],
        main_ui["ar_selector"],
        main_ui["res_selector"]
    ]

    # 1. 点击按钮 -> 仅提交任务 (Start Task)，不等待结果
    main_ui["btn_send"].click(app_logic.start_generation_task, gen_inputs, None)
    main_ui["btn_retry"].click(app_logic.start_generation_task, gen_inputs, None)

    # 2. 状态轮询定时器 (每1秒检查一次)
    # tick 事件会去 app_logic 检查 TASK_STATE，如果完成则更新 UI
    poll_timer = gr.Timer(1)
    poll_timer.tick(
        app_logic.poll_task_status,
        inputs=None,
        outputs=[
            main_ui["result_image"],
            main_ui["btn_download"],  # 這裡對應新的組件
            gallery_output_history
        ]
    )

    # --- 启动加载 ---
    demo.load(
        app_logic.init_app_data,
        inputs=None,
        outputs=[
            main_ui["dir_input"],  # 1
            state_api_key,  # 2
            main_ui["btn_download"],  # 3 [修改點]
            main_ui["result_image"],  # 4
            settings_ui["path"],  # 5
            settings_ui["prefix"],  # 6
            settings_ui["lang"],  # 7
            settings_ui["api_key"]  # 8
        ]
    ).then(
        app_logic.load_images_from_dir,
        inputs=[main_ui["dir_input"]],
        outputs=[state_current_dir_images, main_ui["info_box"]]
    ).then(
        lambda x: x,
        inputs=[state_current_dir_images],
        outputs=[main_ui["gallery_source"]]
    ).then(
        app_logic.load_output_gallery,
        inputs=None,
        outputs=[gallery_output_history]
    )

if __name__ == "__main__":
    import platform
    import sys


    # ================= 🚑 PyInstaller noconsole 修复补丁 =================
    # 当使用 --noconsole 打包时，sys.stdout 和 sys.stderr 是 None
    # 这会导致 uvicorn 日志初始化失败。我们需要给它一个假的流对象。

    class NullWriter:
        def write(self, data): pass

        def flush(self): pass

        def isatty(self): return False  # 这就是 uvicorn 需要的方法

        def fileno(self): return -1


    if sys.stdout is None:
        sys.stdout = NullWriter()
    if sys.stderr is None:
        sys.stderr = NullWriter()
    # =====================================================================

    allowed_paths = get_allowed_paths()
    print(f"✅ Allowed Paths: {len(allowed_paths)}")
    demo.launch(inbrowser=True, server_name="0.0.0.0", server_port=7860, allowed_paths=allowed_paths)