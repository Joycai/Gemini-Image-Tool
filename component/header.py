import gradio as gr
import i18n
import app_logic


def render():
    """
    渲染顶部工具栏
    Returns:
        tuple: (restart_btn, theme_btn)
    """
    with gr.Row(elem_classes="top-toolbar", equal_height=True):
        # 1. 标题
        gr.Markdown(f"### {i18n.get('app_title')}")
        with gr.Row(scale=1):
            # 2. 弹簧/间隔 (占据所有可用空间)
            gr.Column(scale=1)
            # 3. 按钮 (直接作为 top-toolbar 的子元素)
            btn_theme = gr.Button("🎨", size="sm", variant="secondary", scale=0, elem_classes="icon-button")
            btn_restart = gr.Button("🔄", size="sm", variant="secondary", scale=0, elem_classes="icon-button")

    # 绑定重启事件
    btn_restart.click(fn=app_logic.restart_app, inputs=None, outputs=None)

    return btn_restart, btn_theme
