import flet as ft
from flet.core.container import Container
from flet.core.page import Page
import os # Import os for basename

from component.flet_gallery_component import local_gallery_component


def single_edit_tab(page: Page) -> Container:
    selected_images_paths = []
    
    selected_images_grid = ft.GridView(
        runs_count=5,
        max_extent=100, # Smaller thumbnails for selected images
        spacing=5,
        run_spacing=5,
        child_aspect_ratio=1.0,
        padding=0,
        controls=[],
        expand=True
    )

    def remove_selected_image(e, image_path):
        if image_path in selected_images_paths:
            selected_images_paths.remove(image_path)
            # Rebuild controls to reflect removal
            selected_images_grid.controls.clear()
            for path in selected_images_paths:
                selected_images_grid.controls.append(
                    ft.GestureDetector(
                        content=ft.Container(
                            width=100,
                            height=100,
                            border_radius=ft.border_radius.all(5),
                            content=ft.Image(
                                src=path,
                                fit=ft.ImageFit.CONTAIN,
                                tooltip=os.path.basename(path)
                            ),
                            alignment=ft.alignment.center,
                        ),
                        on_tap=lambda ev, p=path: remove_selected_image(ev, p)
                    )
                )
            selected_images_grid.update()

    def add_selected_image(image_path: str):
        if image_path not in selected_images_paths:
            selected_images_paths.append(image_path)
            selected_images_grid.controls.append(
                ft.GestureDetector(
                    content=ft.Container(
                        width=100,
                        height=100,
                        border_radius=ft.border_radius.all(5),
                        content=ft.Image(
                            src=image_path,
                            fit=ft.ImageFit.CONTAIN,
                            tooltip=os.path.basename(image_path)
                        ),
                        alignment=ft.alignment.center,
                    ),
                    on_tap=lambda e, p=image_path: remove_selected_image(e, p)
                )
            )
            selected_images_grid.update()
        # else:
            # Optionally, provide feedback that the image is already selected
            # print(f"Image {image_path} is already selected.")


    return ft.Container(
        content=ft.Row(
            [
                local_gallery_component(page, 4, on_image_select=add_selected_image),
                ft.VerticalDivider(), # Changed from ft.Divider() for vertical separation
                ft.Column(
                    [
                        ft.Text("Selected Images", size=16, weight=ft.FontWeight.BOLD),
                        selected_images_grid,
                        # 展示一个输入框和一个发送按钮，用于输入prompt和发送，還有圖片比例和分辨率
                        ft.Row(
                            [
                                # 選擇比例
                                ft.Dropdown("ratio"),
                                # 選擇分辨率
                                ft.Dropdown("resolution"),
                                ft.Text("Prompt Input"),
                                ft.Text("Send")
                            ]
                        ),
                        # 選擇處理模型
                        ft.Dropdown("Select Model"),
                        # 展示日志，包括发送了什么，用什么参数
                        ft.Text("LogOutput"),
                        # api返回的圖片預覽
                        ft.Text("ResponsePreview"),
                        # 按鈕，點擊後下載原始尺寸的圖片
                        ft.Text("download Origin Image")
                    ],
                    expand=6
                )
            ],
            expand=True
        ),
        expand=True
    )
