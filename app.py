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
import database as db
import i18n
import app_logic
import logger_utils
from component import header, main_page, settings_page

# CSS:
# 1. 强制画廊网格
# 2. 隐藏原生 Tab 的导航栏 (.tab-nav { display: none })
custom_css = """
.toolbar-btn { text-align: left !important; margin-bottom: 10px; }
.right-panel { border-left: 1px solid #e5e7eb; padding-left: 20px; }
.tool-sidebar { background-color: #f9fafb; padding: 10px; border-left: 1px solid #e5e7eb; }
#fixed_gallery .grid-wrap { grid-template-columns: repeat(6, 1fr) !important; }

/* 顶部工具栏样式 */
.top-toolbar {
    display: flex;
    align-items: center;
    padding: 8px var(--block-padding);
    border-bottom: 1px solid #e5e7eb;
    background-color: var(--background-fill-primary);
    gap: 10px;
    margin-bottom: 0 !important;
}
.top-toolbar .markdown-text h3 {
    margin-top: 0;
    margin-bottom: 0;
    line-height: 1.5;
}
.toolbar-left { display: flex; align-items: center; gap: 10px; }
.toolbar-right { display: flex; align-items: center; gap: 5px; }

/* =========================================
   ⬇️ 新增：日誌框固定高度與滾動
   ========================================= */
#log_output_box {
    height: 300px !important;  /* 強制固定外框高度 */
    max-height: 300px !important;
    overflow: hidden !important; /* 防止外框出現雙重滾動條 */
}

/* 針對內部的 CodeMirror 編輯器區域 */
#log_output_box .cm-editor {
    height: 100% !important;
}

/* 針對內容滾動區域 */
#log_output_box .cm-scroller {
    overflow-y: auto !important; /* 內容過多時顯示垂直滾動條 */
}

/* =========================================
   ⬇️ 新增：Dark Mode 强制适配样式
   ========================================= */
body.dark {
    /* 1. 重新定义 Gradio 的核心颜色变量 */
    --body-background-fill: #0b0f19;
    --background-fill-primary: #111827;
    --background-fill-secondary: #1f2937;
    --border-color-primary: #374151;
    --block-background-fill: #1f2937;
    --input-background-fill: #374151; /* 输入框背景 */
    
    /* 2. 文字颜色 */
    --body-text-color: #F3F4F6;
    --block-label-text-color: #D1D5DB;
    --input-text-color: #FFFFFF;
}

/* 针对输入框的强制覆盖 (解决你遇到的白色背景问题) */
body.dark input, 
body.dark textarea, 
body.dark select,
body.dark .gr-input {
    background-color: var(--input-background-fill) !important;
    color: var(--input-text-color) !important;
    border-color: var(--border-color-primary) !important;
}

/* 修复侧边栏和工具栏在深色模式下的背景 */
body.dark .tool-sidebar,
body.dark .right-panel {
    background-color: #111827 !important; /* 深色背景 */
    border-color: #374151 !important;     /* 深色边框 */
}
body.dark .top-toolbar {
    border-bottom: 1px solid #374151 !important;
}
"""
# ⬇️ 新增 JS：用于切换深色模式
js_toggle_theme = """
() => {
    document.body.classList.toggle('dark');
}
"""

with gr.Blocks(title=i18n.get("app_title")) as demo:
    gr.HTML(f"<style>{custom_css}</style>")

    # 全局状态
    settings = db.get_all_settings()
    state_api_key = gr.State(value=settings["api_key"])
    state_current_dir_images = gr.State(value=[])

    # 1. 顶部工具栏 (Header)
    btn_nav_home, btn_nav_settings, btn_restart, btn_theme = header.render()

    # 预创建输出历史组件 (供 main_page 使用)
    gallery_output_history = gr.Gallery(label="Outputs", columns=4, height=520, allow_preview=True, interactive=False,
                                        render=False)

    # 2. Tab 容器 (使用 CSS 隐藏了原本的 Tab 按钮)
    # selected="tab_home" 表示默认显示主页
    with gr.Tabs(elem_id="no_header_tabs", selected="tab_home") as main_tabs:
        # ⬇️ i18n 修复: label="Workbench" -> label=i18n.get("tab_home")
        with gr.TabItem(i18n.get("tab_home"), id="tab_home"):
            main_ui = main_page.render(state_api_key, gallery_output_history)

        # ⬇️ i18n 修复: label="Settings" -> label=i18n.get("tab_settings")
        with gr.TabItem(i18n.get("tab_settings"), id="tab_settings"):
            settings_ui = settings_page.render()


    # ================= 页面切换逻辑 =================
    # 点击按钮 -> 更新 Tabs 组件的 selected 属性

    def go_home():
        return gr.Tabs(selected="tab_home")


    def go_settings():
        return gr.Tabs(selected="tab_settings")


    btn_nav_home.click(fn=go_home, inputs=None, outputs=main_tabs)
    btn_nav_settings.click(fn=go_settings, inputs=None, outputs=main_tabs)

    # ================= 业务逻辑绑定 =================

    # ... (其余逻辑与之前完全一致，直接复用即可) ...

    # 主题切换
    btn_theme.click(None, None, None, js=js_toggle_theme)

    # 日志刷新
    log_timer = gr.Timer(1)
    log_timer.tick(logger_utils.get_logs, outputs=main_ui["log_output"])

    # --- 设置页逻辑 ---
    # 保存后自动跳回主页 (更新 outputs=main_tabs)
    settings_ui["btn_save"].click(
        app_logic.save_cfg_wrapper,
        inputs=[settings_ui["api_key"], settings_ui["path"], settings_ui["prefix"], settings_ui["lang"]],
        outputs=[state_api_key, main_tabs, gallery_output_history]  # 这里把 main_tabs 也放进去
    ).then(
        fn=go_home,  # 确保逻辑层也是切回 Home
        inputs=None,
        outputs=main_tabs
    )

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
    # [新增] 綁定打開文件夾按鈕
    main_ui["btn_open_out_dir"].click(
        fn=app_logic.open_output_folder,
        inputs=None,
        outputs=None
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

    # --- 主页: 图片选择与移除 ---
    main_ui["gallery_source"].select(app_logic.select_img, [state_current_dir_images, main_ui["state_selected_images"]],
                                     [main_ui["state_selected_images"], main_ui["gallery_selected"]])
    main_ui["gallery_selected"].select(app_logic.remove_selected_img, [main_ui["state_selected_images"]],
                                       [main_ui["state_selected_images"], main_ui["gallery_selected"]])
    main_ui["btn_clear"].click(lambda: ([], []), None, [main_ui["state_selected_images"], main_ui["gallery_selected"]])

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