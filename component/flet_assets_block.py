import flet as ft
import os
import platform
import shutil
import subprocess
from typing import List, Dict, Any, Optional

import i18n
import database as db
import logger_utils
from config import VALID_IMAGE_EXTENSIONS, UPLOAD_DIR

# Flet's FilePicker will handle folder selection
# No need for tkinter or AppleScript directly in the UI component

class FletAssetsBlock(ft.Control): # Changed back to ft.Control
    def __init__(self, page: ft.Page, prefix: str = ""):
        super().__init__()
        self.page = page
        self.prefix = prefix
        self.settings = db.get_all_settings()

        self.dir_input = ft.TextField(
            value=self.settings["last_dir"],
            label=i18n.get("home_assets_label_dirPath"),
            expand=3,
            data=f"{prefix}dir_input"
        )
        self.file_picker = ft.FilePicker(on_result=self.on_folder_selected)
        self.btn_select_dir = ft.ElevatedButton(
            text=i18n.get("home_assets_btn_browse"),
            icon=ft.Icons.FOLDER_OPEN,
            on_click=lambda e: self.file_picker.get_directory_path(),
            data=f"{prefix}btn_select_dir"
        )
        self.btn_refresh = ft.ElevatedButton(
            text=i18n.get("home_assets_btn_refresh"),
            icon=ft.Icons.REFRESH,
            on_click=self.refresh_images,
            data=f"{prefix}btn_refresh"
        )
        self.recursive_checkbox = ft.Checkbox(
            label=i18n.get("home_assets_label_recursive"),
            value=False,
            on_change=self.refresh_images,
            data=f"{prefix}recursive_checkbox"
        )
        self.size_slider = ft.Slider(
            min=2,
            max=6,
            divisions=4,
            value=4,
            label=i18n.get("home_assets_label_columns"),
            on_change=self.update_gallery_columns,
            data=f"{prefix}size_slider"
        )
        self.gallery_source = ft.GridView(
            runs_count=4,
            max_extent=150,
            spacing=5,
            run_spacing=5,
            child_aspect_ratio=1.0,
            padding=0,
            controls=[],
            data=f"{prefix}gallery_source"
        )
        self.upload_button = ft.FilePicker(on_result=self.on_files_uploaded)
        self.btn_upload_files = ft.ElevatedButton(
            text=i18n.get("home_assets_btn_upload"),
            icon=ft.Icons.UPLOAD_FILE,
            on_click=lambda e: self.upload_button.pick_files(allow_multiple=True, allowed_extensions=[ext.lstrip('.') for ext in VALID_IMAGE_EXTENSIONS]),
            data=f"{prefix}upload_button"
        )
        self.gallery_upload = ft.GridView(
            runs_count=4,
            max_extent=150,
            spacing=5,
            run_spacing=5,
            child_aspect_ratio=1.0,
            padding=0,
            controls=[],
            data=f"{prefix}gallery_upload"
        )
        self.info_box = ft.Markdown(
            i18n.get("home_assets_info_ready"),
            data=f"{prefix}info_box"
        )
        self.state_marked_for_add = None

        self.page.overlay.append(self.file_picker)
        self.page.overlay.append(self.upload_button)

    def _get_control_name(self): # Added this method
        return "fletassetsblock"

    def build(self):
        return ft.Column(
            [
                ft.Markdown(f"#### {i18n.get('home_assets_title')}"),
                ft.Tabs(
                    selected_index=0,
                    animation_duration=300,
                    tabs=[
                        ft.Tab(
                            text=i18n.get("home_assets_tab_local"),
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            self.dir_input,
                                            self.btn_select_dir,
                                            self.btn_refresh,
                                        ]
                                    ),
                                    ft.Row(
                                        [
                                            self.recursive_checkbox,
                                            self.size_slider,
                                        ]
                                    ),
                                    self.gallery_source,
                                ]
                            ),
                        ),
                        ft.Tab(
                            text=i18n.get("home_assets_tab_upload"),
                            content=ft.Column(
                                [
                                    self.btn_upload_files,
                                    self.gallery_upload,
                                ]
                            ),
                        ),
                    ],
                    expand=1
                ),
                self.info_box,
            ]
        )

    def on_folder_selected(self, e: ft.FilePickerResultEvent):
        if e.path:
            self.dir_input.value = e.path
            self.dir_input.update()
            self.refresh_images()

    def load_images_from_dir_logic(self, dir_path: str, recursive: bool) -> tuple[List[str], str]:
        if not dir_path or not os.path.exists(dir_path):
            return [], i18n.get("logic_error_dirNotFound", path=dir_path)
        db.save_setting("last_dir", dir_path)

        image_files: List[str] = []
        if recursive:
            for root, _, files in os.walk(dir_path):
                for f in files:
                    if os.path.splitext(f)[1].lower() in VALID_IMAGE_EXTENSIONS:
                        image_files.append(os.path.join(root, f))
        else:
            image_files = [os.path.join(dir_path, f) for f in os.listdir(dir_path)
                           if os.path.splitext(f)[1].lower() in VALID_IMAGE_EXTENSIONS]

        msg: str = i18n.get("logic_log_loadDir", path=dir_path, count=len(image_files))
        logger_utils.log(msg)
        return image_files, msg

    def refresh_images(self, e=None):
        dir_path = self.dir_input.value
        recursive = self.recursive_checkbox.value
        image_paths, msg = self.load_images_from_dir_logic(dir_path, recursive)

        self.gallery_source.controls.clear()
        for path in image_paths:
            self.gallery_source.controls.append(
                ft.Image(
                    src=path,
                    fit=ft.ImageFit.CONTAIN,
                )
            )
        self.info_box.value = msg
        self.update() # Updated to call self.update()

    def update_gallery_columns(self, e):
        self.gallery_source.runs_count = int(e.control.value)
        self.gallery_upload.runs_count = int(e.control.value)
        self.update() # Updated to call self.update()

    def on_files_uploaded(self, e: ft.FilePickerResultEvent):
        if e.files:
            saved_paths: List[str] = []
            for f in e.files:
                target_path: str = os.path.join(UPLOAD_DIR, f.name)
                try:
                    shutil.copy(f.path, target_path)
                    saved_paths.append(target_path)
                except (IOError, OSError) as err:
                    logger_utils.log(f"Failed to copy uploaded file {f.name}: {err}")

            if saved_paths:
                logger_utils.log(f"Uploaded and saved {len(saved_paths)} files.")
                self.gallery_upload.controls.clear()
                for path in saved_paths:
                    self.gallery_upload.controls.append(
                        ft.Image(
                            src=path,
                            fit=ft.ImageFit.CONTAIN,
                        )
                    )
                self.update() # Updated to call self.update()
