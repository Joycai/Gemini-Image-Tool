import os
import platform
import subprocess

import flet as ft
from flet import Container, BoxFit
from flet import Page

from common import database as db, i18n, logger_utils
from common.config import VALID_IMAGE_EXTENSIONS, OUTPUT_DIR
from common.image_util import get_image_details
from fletapp.component.flet_image_preview_dialog import PreviewDialogData, preview_dialog


def history_page(page: Page) -> Container:
    # --- Data ---
    image_files = []

    # --- Controls ---
    history_grid = ft.GridView(
        expand=True,
        runs_count=5,
        child_aspect_ratio=0.87,
        spacing=10,
        run_spacing=10,
    )

    # --- Reusable Components ---
    # image_preview_dialog = ImagePreviewDialog(page)

    # --- Functions ---
    def update_grid_layout(e):
        columns = int(e.control.value)
        history_grid.runs_count = columns
        if page: page.update()

    zoom_slider = ft.Slider(
        min=1,
        max=10,
        divisions=9,
        value=5,
        label="{value}",
        on_change=update_grid_layout,
        width=200,
    )

    def load_history_images():
        nonlocal image_files
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
            image_files = files

            if not image_files:
                history_grid.controls.append(
                    ft.Text(i18n.get("history_no_images_found", "No images found in the output directory.")))

            for i, img_path in enumerate(image_files):
                details_text = get_image_details(img_path)

                thumbnail = ft.Container(
                    content=ft.Image(src=img_path, fit=BoxFit.CONTAIN, tooltip=os.path.basename(img_path)),
                    border_radius=ft.border_radius.all(5),
                    expand=True
                )

                details_label = ft.Text(
                    value=details_text,
                    size=10,
                    text_align=ft.TextAlign.CENTER,
                )

                image_with_details = ft.Column(
                    controls=[
                        thumbnail,
                        details_label,
                    ],
                    spacing=2,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    expand=True,
                )

                history_grid.controls.append(
                    ft.GestureDetector(
                        content=image_with_details,
                        on_double_tap=lambda e, index=i: open_preview_dialog(index)
                    )
                )
        except Exception as e:
            logger_utils.log(f"Error loading history images: {e}")
            history_grid.controls.append(ft.Text(f"Error: {e}"))

        if page: page.update()

    def open_preview_dialog(current_index: int):
        image_preview_dialog = preview_dialog(
            page,
            PreviewDialogData(
                image_list=image_files,
                current_index=current_index
            ),
            on_deleted_callback_fnc=load_history_images)
        page.show_dialog(image_preview_dialog)
        # image_preview_dialog.open(
        #     image_list=image_files,
        #     current_index=current_index,
        #     on_delete=delete_image,
        #     on_download=download_image_handler
        # )

    # def delete_image(image_path: str):
    #     try:
    #         if os.path.exists(image_path):
    #             os.remove(image_path)
    #             logger_utils.log(i18n.get("logic_log_deletedFile", path=image_path))
    #         image_preview_dialog.close(None)
    #         load_history_images()  # Refresh the grid
    #     except Exception as e:
    #         logger_utils.log(f"Error deleting image {image_path}: {e}")

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
    load_history_images()

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
                                      tooltip=i18n.get("home_history_btn_refresh_tooltip", "Refresh")),
                        ft.Text(i18n.get("home_history_zoom", "Column Num:")),
                        zoom_slider,
                    ]
                ),
                history_grid,
            ]
        ),
        padding=ft.padding.all(10),
        expand=True,
    )
