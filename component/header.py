import gradio as gr
import i18n
import app_logic


def render():
    """
    渲染顶部工具栏
    Returns:
        tuple: (nav_home_btn, nav_settings_btn, restart_btn, theme_btn)
    """
    # 去掉 variant="panel"，改用 CSS 控制样式
    with gr.Row(elem_classes="top-toolbar", equal_height=True):
        # --- 左侧区域：标题 + 导航 ---
        with gr.Row(scale=0, elem_classes="toolbar-left"):
            # 1. 标题 (给个最小宽度防止换行)
            with gr.Column(scale=0, min_width=220):
                gr.Markdown(f"### {i18n.get('app_title')}")

            # 2. 导航按钮 (紧跟标题)
            btn_nav_home = gr.Button("🏠 " + i18n.get("tab_workbench"), size="sm", variant="primary", scale=0)
            btn_nav_settings = gr.Button("⚙️ " + i18n.get("settings_panel"), size="sm", variant="secondary", scale=0)

        # --- 中间弹簧：占据剩余空间 ---
        with gr.Column(scale=1):
            pass

            # --- 右侧区域：系统功能 ---
        with gr.Row(scale=0, elem_classes="toolbar-right"):
            btn_restart = gr.Button(i18n.get("btn_restart"), size="sm", variant="stop", scale=0)
            btn_theme = gr.Button(i18n.get("btn_theme"), size="sm", variant="secondary", scale=0)

    # 绑定重启事件 (逻辑在 header 内部绑定，不暴露给 app.py)
    btn_restart.click(fn=app_logic.restart_app, inputs=None, outputs=None)

    return btn_nav_home, btn_nav_settings, btn_restart, btn_theme