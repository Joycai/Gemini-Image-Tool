import gradio as gr
import i18n

def render():
    """
    渲染顶部工具栏
    Returns:
        gr.Button: theme_btn
    """
    with gr.Row(elem_classes="top-toolbar", equal_height=True):
        # 1. 标题
        gr.Markdown(f"### {i18n.get('app_title')}")
        with gr.Row(scale=1):
            # 2. 弹簧/间隔 (占据所有可用空间)
            gr.Column(scale=1)
            # 3. 按钮 (直接作为 top-toolbar 的子元素)
            btn_theme = gr.Button("🎨", size="sm", variant="secondary", scale=0, elem_classes="icon-button")

    return btn_theme
