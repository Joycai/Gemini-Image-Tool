import os
from typing import Union, Callable

import flet as ft
from flet.core.container import Container
from flet.core.page import Page

# Import VALID_IMAGE_EXTENSIONS from config.py
from common.config import VALID_IMAGE_EXTENSIONS

def local_gallery_component(page: Page, expand: Union[None,bool,int], on_image_select: Callable[[str], None] = None) -> Container:
    # --- Single Image Editor Page Controls and Handlers ---
    selected_directory = ft.TextField(
        label="Selected Directory",
        read_only=True
    )

    # Image preview dialog components - defined once
    image_preview_image = ft.Image(
        src="",
        fit=ft.ImageFit.CONTAIN
    )
    image_preview_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Image Preview"),
        content=ft.Container(
            content=image_preview_image,
            width=800,  # Adjust as needed
            height=600,  # Adjust as needed
        ),
        actions=[
            ft.TextButton("Close", on_click=lambda e: close_image_preview(e)),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def open_image_preview(e, image_path):
        image_preview_image.src = image_path
        page.open(image_preview_dialog)  # Correct way to open dialog

    def close_image_preview(e):
        page.close(image_preview_dialog)  # Correct way to close dialog

    image_gallery = ft.GridView(
        runs_count=5,  # 每行显示5张图片
        max_extent=150,  # 每张图片的最大宽度
        spacing=10,
        run_spacing=10,
        child_aspect_ratio=1.0,
        padding=0,
        controls=[],
        expand=True,
        height=700
    )

    def load_images_from_directory(directory_path: str, include_subdirectories: bool):
        image_gallery.controls.clear()
        if not os.path.isdir(directory_path):
            image_gallery.controls.append(ft.Text("Invalid directory."))
            image_gallery.update()
            return

        if include_subdirectories:
            for root, _, files in os.walk(directory_path):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    if os.path.isfile(file_path):
                        _, ext = os.path.splitext(filename)
                        if ext.lower() in VALID_IMAGE_EXTENSIONS:
                            # Define on_tap handler
                            def _on_tap(e, path=file_path):
                                if on_image_select:
                                    on_image_select(path)

                            image_gallery.controls.append(
                                ft.GestureDetector(
                                    content=ft.Container(
                                        width=150,
                                        height=150,
                                        border_radius=ft.border_radius.all(5),
                                        content=ft.Image(
                                            src=file_path,
                                            fit=ft.ImageFit.CONTAIN,
                                            tooltip=filename
                                        ),
                                        alignment=ft.alignment.center,
                                    ),
                                    on_double_tap=lambda e, path=file_path: open_image_preview(e, path),
                                    on_tap=_on_tap # Add on_tap event
                                )
                            )
        else:
            for filename in os.listdir(directory_path):
                file_path = os.path.join(directory_path, filename)
                if os.path.isfile(file_path):
                    _, ext = os.path.splitext(filename)
                    if ext.lower() in VALID_IMAGE_EXTENSIONS:
                        # Define on_tap handler
                        def _on_tap(e, path=file_path):
                            if on_image_select:
                                on_image_select(path)

                        image_gallery.controls.append(
                            ft.GestureDetector(
                                content=ft.Container(
                                    width=150,
                                    height=150,
                                    border_radius=ft.border_radius.all(5),
                                    content=ft.Image(
                                        src=file_path,
                                        fit=ft.ImageFit.CONTAIN,
                                        tooltip=filename
                                    ),
                                    alignment=ft.alignment.center,
                                ),
                                on_double_tap=lambda e, path=file_path: open_image_preview(e, path),
                                on_tap=_on_tap # Add on_tap event
                            )
                        )
        image_gallery.update()

    def on_directory_picked(e: ft.FilePickerResultEvent):
        if e.path:
            selected_directory.value = e.path
            selected_directory.update()
            load_images_from_directory(e.path, include_subdirectories_checkbox.value)
        else:
            selected_directory.value = "No directory selected."
            selected_directory.update()
            image_gallery.controls.clear()
            image_gallery.update()

    file_picker = ft.FilePicker(on_result=on_directory_picked)
    page.overlay.append(file_picker)

    def open_directory_picker(e):
        file_picker.get_directory_path()

    def include_subdirectories_changed(e):
        if selected_directory.value:
            load_images_from_directory(selected_directory.value, include_subdirectories_checkbox.value)

    # Checkbox to include subdirectories
    include_subdirectories_checkbox = ft.Checkbox(
        label="Include Subdirectories",
        value=False,
        on_change=include_subdirectories_changed
    )

    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    controls=[
                        ft.Column(
                            controls=[selected_directory],
                            expand=6
                        ),
                        ft.Column(
                            controls=[
                                ft.ElevatedButton(
                                    text="Open Directory",
                                    icon=ft.Icons.FOLDER_OPEN,
                                    on_click=open_directory_picker
                                ),
                                include_subdirectories_checkbox
                            ],
                            expand=4
                        )
                    ]
                ),
                image_gallery,
            ],
            scroll=ft.ScrollMode.AUTO
        ),
        padding=ft.padding.all(10),
        expand=expand
    )