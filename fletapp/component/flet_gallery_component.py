import os
from dataclasses import dataclass
from typing import Union, Callable
import threading
import flet as ft
from flet import Container, BoxFit, Alignment
from flet import Page

# Import common modules
from common.config import VALID_IMAGE_EXTENSIONS
from common import database as db

@dataclass
class State:
    file_picker: ft.FilePicker | None = None
    current_directory: str | None = None
    include_subdirectories: bool = False


state = State()

def local_gallery_component(page: Page, expand: Union[None,bool,int], on_image_select: Callable[[str], None] = None) -> Container:
    # --- Single Image Editor Page Controls and Handlers ---
    selected_directory = ft.TextField(
        label="Selected Directory",
        read_only=True
    )

    # Image preview dialog components - defined once
    image_preview_image = ft.Image(
        src="",
        fit=BoxFit.CONTAIN
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
        page.show_dialog(image_preview_dialog)  # Correct way to open dialog

    def close_image_preview(e):
        page.pop_dialog()  # Correct way to close dialog

    image_gallery = ft.GridView(
        runs_count=5,  # 每行显示5张图片
        max_extent=150,  # 每张图片的最大宽度
        spacing=10,
        run_spacing=10,
        child_aspect_ratio=1.0,
        padding=0,
        controls=[],
        expand=True
    )

    def load_images_from_directory(directory_path: str, include_subdirectories: bool):
        image_gallery.controls.clear()
        if not os.path.isdir(directory_path):
            image_gallery.controls.append(ft.Text("Invalid directory."))
            if page: page.update()
            return

        image_paths = []
        if include_subdirectories:
            for root, _, files in os.walk(directory_path):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    if os.path.isfile(file_path):
                        _, ext = os.path.splitext(filename)
                        if ext.lower() in VALID_IMAGE_EXTENSIONS:
                            image_paths.append(file_path)
        else:
            for filename in os.listdir(directory_path):
                file_path = os.path.join(directory_path, filename)
                if os.path.isfile(file_path):
                    _, ext = os.path.splitext(filename)
                    if ext.lower() in VALID_IMAGE_EXTENSIONS:
                        image_paths.append(file_path)
        
        for path in image_paths:
            def _on_tap(e, p=path):
                if on_image_select:
                    on_image_select(p)

            image_gallery.controls.append(
                ft.GestureDetector(
                    content=ft.Container(
                        width=150,
                        height=150,
                        border_radius=ft.border_radius.all(5),
                        content=ft.Image(
                            src=path,
                            fit=BoxFit.CONTAIN,
                            tooltip=os.path.basename(path)
                        ),
                        alignment=Alignment.CENTER,
                    ),
                    on_double_tap=lambda e, p=path: open_image_preview(e, p),
                    on_tap=_on_tap
                )
            )
        if page: page.update()

    async def open_directory_picker(e: ft.Event[ft.Button]):
        if not state.file_picker:
            state.file_picker = ft.FilePicker()
        pick_directory = await state.file_picker.get_directory_path(initial_directory=state.current_directory)
        if pick_directory and pick_directory != state.file_picker:
            db.save_setting("last_dir", pick_directory)
            state.current_directory = pick_directory
            selected_directory.value = state.current_directory
            refresh_directory(e)

    def include_subdirectories_changed(e: ft.Event[ft.Checkbox]):
        if e.control.value is not None:
            state.include_subdirectories=e.control.value
        refresh_directory(e)

    # Checkbox to include subdirectories
    include_subdirectories_checkbox = ft.Checkbox(
        label="Include Subdirectories",
        value=False,
        on_change=include_subdirectories_changed
    )

    def refresh_directory(e):
        if state.current_directory and os.path.isdir(state.current_directory):
            load_images_from_directory(state.current_directory, state.include_subdirectories)

    # --- Initialization Logic using threading.Timer ---
    def delayed_initialize():
        last_dir = db.get_setting("last_dir")
        if last_dir and os.path.isdir(last_dir):
            selected_directory.value = last_dir
            state.current_directory = last_dir
            refresh_directory(None)
        else:
            selected_directory.value = "No directory selected."
        # Safely update the page now
        if page: page.update()

    delayed_initialize()

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
                                ft.Row(
                                    controls=[
                                        ft.Button(
                                            content="Open Directory",
                                            icon=ft.Icons.FOLDER_OPEN,
                                            on_click=open_directory_picker,
                                            tooltip="Open Directory"
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.REFRESH,
                                            on_click=refresh_directory,
                                            tooltip="Refresh Directory"
                                        )
                                    ]
                                ),
                                include_subdirectories_checkbox
                            ],
                            expand=4
                        )
                    ]
                ),
                ft.Column(
                    controls=[image_gallery],
                    expand=True,
                    scroll=ft.ScrollMode.AUTO
                )
            ],
            expand=True,
        ),
        padding=ft.padding.all(10),
        expand=expand,
    )