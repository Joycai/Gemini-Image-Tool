import os
from dataclasses import dataclass
from typing import Callable, List, Optional

import flet as ft
from flet import BoxFit, FilePickerFileType, Control

from common import i18n, logger_utils
from common.config import VALID_IMAGE_EXTENSIONS


@dataclass
class PreviewDialogData:
    image_list: List[str] | None = None
    current_index: int = 0


def preview_dialog(
        page: ft.Page,
        data_state: PreviewDialogData,
        on_deleted_callback_fnc: Optional[Callable[[], None]] = None,
        simple_mode: bool = False
):
    # UI elements
    preview_image = ft.Image(
        src=data_state.image_list[data_state.current_index],
        fit=BoxFit.CONTAIN,
    )

    def close_handler():
        page.pop_dialog()

    def go_next():
        if data_state.current_index < len(data_state.image_list) - 1:
            _show_image_at_index(data_state.current_index + 1)

    def go_previous(e):
        if data_state.current_index > 0:
            _show_image_at_index(data_state.current_index - 1)

    def on_delete_handler():
        d_image_path = data_state.image_list[data_state.current_index]
        try:
            if os.path.exists(d_image_path):
                os.remove(d_image_path)
                if data_state.current_index == len(data_state.image_list) - 1:
                    data_state.current_index -= 1
                if data_state.current_index < 0:
                    if on_deleted_callback_fnc:
                        on_deleted_callback_fnc()
                    data_state.image_list.remove(d_image_path)
                    page.pop_dialog()
                    return
                data_state.image_list.remove(d_image_path)
                _show_image_at_index(data_state.current_index)
                if on_deleted_callback_fnc:
                    on_deleted_callback_fnc()
                logger_utils.log(i18n.get("logic_log_deletedFile", path=d_image_path))
        except Exception as e:
            logger_utils.log(f"Error deleting image {d_image_path}: {e}")

    async def on_download_handler():
        try:
            d_image_path = data_state.image_list[data_state.current_index]
            # 'rb' mode is crucial here
            with open(d_image_path, 'rb') as f:
                file_bytes = f.read()
            saved_path = await ft.FilePicker().save_file(
                file_name=os.path.basename(d_image_path),
                allowed_extensions=[ext.strip('.') for ext in VALID_IMAGE_EXTENSIONS],
                src_bytes=file_bytes,
                file_type=FilePickerFileType.IMAGE
            )
        except FileNotFoundError:
            logger_utils.log("File not found.")
        except PermissionError:
            logger_utils.log("Permission denied.")

    prev_button = ft.TextButton(i18n.get("dialog_btn_previous", "Previous"), on_click=go_previous)
    next_button = ft.TextButton(i18n.get("dialog_btn_next", "Next"), on_click=go_next)
    download_button = ft.TextButton(i18n.get("dialog_btn_download", "Download"), on_click=on_download_handler)

    delete_button = ft.TextButton(i18n.get("dialog_btn_delete", "Delete"), on_click=on_delete_handler)

    if on_deleted_callback_fnc is None:
        delete_button.disabled = True

    def _show_image_at_index(index: int):
        data_state.current_index = index
        image_path = data_state.image_list[data_state.current_index]

        # Reset view and update image source
        preview_image.src = image_path

        # Update navigation button visibility
        if prev_button.visible:
            prev_button.disabled = data_state.current_index == 0
            next_button.disabled = data_state.current_index == len(data_state.image_list) - 1
        preview_image.update()

    actions: list[Control]= []
    if not simple_mode:
        actions.append(prev_button)
        actions.append(next_button)
        actions.append(download_button)
        actions.append(delete_button)
    actions.append(ft.TextButton(i18n.get("dialog_btn_close", "Close"), on_click=close_handler))

    return ft.AlertDialog(
        modal=True,
        title=ft.Text(i18n.get("dialog_title_image_preview", "Image Preview")),
        content=ft.InteractiveViewer(
            width=800,
            height=600,
            min_scale=0.1,
            max_scale=16,
            content=preview_image
        ),
        actions=actions,
        actions_alignment=ft.MainAxisAlignment.END,
    )
