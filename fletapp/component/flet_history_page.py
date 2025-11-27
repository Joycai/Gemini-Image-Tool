import flet as ft
from flet.core.container import Container
from flet.core.page import Page
import os
import subprocess
import platform
import threading

from common import database as db, i18n, logger_utils
from common.config import VALID_IMAGE_EXTENSIONS, OUTPUT_DIR
from fletapp.component.flet_image_preview_dialog import ImagePreviewDialog

def history_page(page: Page) -> Container:
    # --- Controls ---
    history_grid = ft.GridView(
        expand=True,
        runs_count=5,
        max_extent=150,
        child_aspect_ratio=1.0,
        spacing=10,
        run_spacing=10,
    )

    # --- Reusable Components ---
    image_preview_dialog = ImagePreviewDialog(page)
    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)

    # --- Functions ---
    def load_history_images():
        history_grid.controls.clear()
        save_dir = db.get_setting("save_path", OUTPUT_DIR)
        
        if not os.path.isdir(save_dir):
            history_grid.controls.append(ft.Text(i18n.get("history_no_dir_found", "Output directory not found.")))
            if page: page.update()
            return

        try:
            files = [os.path.join(save_dir, f) for f in os.listdir(save_dir)
                     if os.path.splitext(f)[1].lower() in VALID_IMAGE_EXTENSIONS]
            files.sort(key=os.path.getmtime, reverse=True)

            if not files:
                history_grid.controls.append(ft.Text(i18n.get("history_no_images_found", "No images found in the output directory.")))
            
            for img_path in files:
                history_grid.controls.append(
                    ft.GestureDetector(
                        content=ft.Container(
                            content=ft.Image(src=img_path, fit=ft.ImageFit.CONTAIN, tooltip=os.path.basename(img_path)),
                            border_radius=ft.border_radius.all(5)
                        ),
                        on_double_tap=lambda e, path=img_path: open_preview_dialog(path)
                    )
                )
        except Exception as e:
            logger_utils.log(f"Error loading history images: {e}")
            history_grid.controls.append(ft.Text(f"Error: {e}"))
        
        if page: page.update()

    def open_preview_dialog(image_path: str):
        image_preview_dialog.open(
            image_path=image_path,
            on_delete=delete_image,
            on_download=download_image
        )

    def delete_image(image_path: str):
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
                logger_utils.log(i18n.get("logic_log_deletedFile", path=image_path))
            image_preview_dialog.close(None)
            load_history_images() # Refresh the grid
        except Exception as e:
            logger_utils.log(f"Error deleting image {image_path}: {e}")

    def download_image(image_path: str):
        def on_save_result(e: ft.FilePickerResultEvent):
            if e.path:
                try:
                    import shutil
                    shutil.copy(image_path, e.path)
                    logger_utils.log(f"Image saved to: {e.path}")
                except Exception as ex:
                    logger_utils.log(f"Error saving image: {ex}")
        
        file_picker.on_result = on_save_result
        file_picker.save_file(
            file_name=os.path.basename(image_path),
            allowed_extensions=[ext.strip('.') for ext in VALID_IMAGE_EXTENSIONS]
        )

    def open_output_folder_handler(e):
        path = db.get_setting("save_path", OUTPUT_DIR)
        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
            except OSError as ex:
                logger_utils.log(f"Error creating directory: {ex}")
                return
        
        try:
            system_platform = platform.system()
            if system_platform == "Windows":
                os.startfile(os.path.abspath(path))
            elif system_platform == "Darwin":
                subprocess.run(["open", os.path.abspath(path)], check=False)
            else:
                subprocess.run(["xdg-open", os.path.abspath(path)], check=False)
        except Exception as ex:
            logger_utils.log(f"Error opening folder: {ex}")

    # --- Initialization using threading.Timer ---
    def delayed_initialize():
        load_history_images()

    threading.Timer(0.1, delayed_initialize).start()

    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(i18n.get("home_history_title"), size=24, weight=ft.FontWeight.BOLD),
                    ]
                ),
                ft.Row(
                    [
                        ft.IconButton(icon=ft.Icons.FOLDER_OPEN, on_click=open_output_folder_handler,
                                      tooltip=i18n.get("home_history_btn_open")),
                        ft.IconButton(icon=ft.Icons.REFRESH, on_click=lambda e: load_history_images(),
                                      tooltip=i18n.get("home_history_btn_refresh", "Refresh")),
                    ]
                ),
                history_grid,
            ]
        ),
        padding=ft.padding.all(10),
        expand=True,
    )
