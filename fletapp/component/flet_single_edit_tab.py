import os
import shutil
import threading
import time
from typing import List, Dict, Any

import flet as ft
from flet.core.page import Page
from flet.core.types import MainAxisAlignment
from PIL import Image

# Custom imports
from common import database as db, logger_utils, i18n
from common.config import MODEL_SELECTOR_CHOICES, AR_SELECTOR_CHOICES, RES_SELECTOR_CHOICES, OUTPUT_DIR
from common.text_encoder import text_encoder
from fletapp.component.flet_gallery_component import local_gallery_component
from geminiapi import api_client

# Ensure OUTPUT_DIR exists
os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_image_details(image_path: str) -> str:
    """
    Gets the closest aspect ratio and resolution for an image.
    """
    try:
        with Image.open(image_path) as img:
            width, height = img.size
    except Exception as e:
        logger_utils.log(f"Error opening image {image_path}: {e}")
        return "Unknown"

    # Resolution
    max_dim = max(width, height)
    if max_dim <= 1024:
        res_text = "1K"
    elif max_dim <= 2048:
        res_text = "2K"
    else:
        res_text = "4K"

    # Aspect Ratio
    if height == 0:
        return f"{res_text} / ?"

    image_ar = width / height

    best_ar_choice = ""
    min_diff = float('inf')

    for ar_choice in AR_SELECTOR_CHOICES:
        if ar_choice == "ar_none":
            continue

        try:
            ar_parts = ar_choice.split(':')
            ar_value = int(ar_parts[0]) / int(ar_parts[1])

            diff = abs(image_ar - ar_value)

            if diff < min_diff:
                min_diff = diff
                best_ar_choice = ar_choice
        except (ValueError, ZeroDivisionError):
            continue

    return f"{res_text} / {best_ar_choice}"


def single_edit_tab(page: Page) -> Dict[str, Any]:
    selected_images_paths: List[str] = []

    api_task_state = {
        "status": "idle",
        "result_image_path": None,
        "error_msg": None,
    }

    # --- Prompt Management Controls ---
    prompt_dropdown = ft.Dropdown(
        label=i18n.get("home_control_prompt_label_history"),
        hint_text=i18n.get("home_control_prompt_placeholder"),
        options=[],
        expand=True
    )
    prompt_title_input = ft.TextField(
        label=i18n.get("home_control_prompt_save_label"),
        hint_text=i18n.get("home_control_prompt_save_placeholder"),
        expand=True
    )

    # --- Main UI Controls ---
    selected_images_grid = ft.GridView(runs_count=5, max_extent=120, spacing=5, run_spacing=5, child_aspect_ratio=0.8,
                                       padding=0, controls=[], expand=True)
    prompt_input = ft.TextField(label=i18n.get("home_control_prompt_input_placeholder"), multiline=True, min_lines=3,
                                max_lines=5, hint_text=i18n.get("home_control_prompt_input_placeholder"), expand=4)
    log_output_text = ft.Text(i18n.get("log_initial_message", "Log messages will appear here..."), selectable=True,
                              expand=True)
    api_response_image = ft.Image(src="https://via.placeholder.com/300x200?text=API+Response", fit=ft.ImageFit.CONTAIN,
                                  expand=True)
    ratio_dropdown = ft.Dropdown(label=i18n.get("home_control_ratio_label"),
                                 options=[ft.dropdown.Option(key=value, text=text) for text, value in
                                          i18n.get_translated_choices(AR_SELECTOR_CHOICES)],
                                 value=AR_SELECTOR_CHOICES[0], expand=1)
    resolution_dropdown = ft.Dropdown(label=i18n.get("home_control_resolution_label"),
                                      options=[ft.dropdown.Option(res) for res in RES_SELECTOR_CHOICES],
                                      value=RES_SELECTOR_CHOICES[0], expand=1)
    model_selector_dropdown = ft.Dropdown(label=i18n.get("home_control_model_label"),
                                          options=[ft.dropdown.Option(model) for model in MODEL_SELECTOR_CHOICES],
                                          value=MODEL_SELECTOR_CHOICES[0], expand=2)

    # --- Functions ---
    def show_snackbar(message: str, is_error: bool = False):
        page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.ERROR if is_error else ft.Colors.GREEN_700,
        )
        page.snack_bar.open = True
        page.update()

    def refresh_prompts_dropdown():
        titles = db.get_all_prompt_titles()
        prompt_dropdown.options = [ft.dropdown.Option(title) for title in titles]
        prompt_dropdown.update()

    def load_prompt_handler(e):
        selected_title = prompt_dropdown.value
        if not selected_title:
            show_snackbar(i18n.get("logic_warn_promptNotSelected", "Please select a prompt to load."), is_error=True)
            return
        content = db.get_prompt_content(selected_title)
        prompt_input.value = content
        logger_utils.log(i18n.get("logic_log_loadPrompt", title=selected_title))
        prompt_input.update()

    def save_prompt_handler(e):
        title = prompt_title_input.value
        content = prompt_input.value
        if not title or not content:
            show_snackbar(i18n.get("logic_warn_promptEmpty"), is_error=True)
            return
        db.save_prompt(title, content)
        logger_utils.log(i18n.get("logic_log_savePrompt", title=title))
        show_snackbar(i18n.get("logic_info_promptSaved", title=title))
        prompt_title_input.value = ""
        prompt_title_input.update()
        refresh_prompts_dropdown()

    def delete_prompt_handler(e):
        selected_title = prompt_dropdown.value
        if not selected_title:
            show_snackbar(i18n.get("logic_warn_promptNotSelected", "Please select a prompt to delete."), is_error=True)
            return
        db.delete_prompt(selected_title)
        logger_utils.log(i18n.get("logic_log_deletePrompt", title=selected_title))
        show_snackbar(i18n.get("logic_info_promptDeleted", title=selected_title))
        prompt_dropdown.value = None
        refresh_prompts_dropdown()

    # --- Other Functions (Image selection, API calls, etc.) ---
    def remove_selected_image(e, image_path):
        if image_path in selected_images_paths:
            selected_images_paths.remove(image_path)
            update_selected_images_display()

    def add_selected_image(image_path: str):
        if image_path not in selected_images_paths:
            selected_images_paths.append(image_path)
            update_selected_images_display()

    def update_selected_images_display():
        selected_images_grid.controls.clear()
        for path in selected_images_paths:
            details_text = get_image_details(path)

            thumbnail = ft.Container(
                width=100,
                height=100,
                border_radius=ft.border_radius.all(5),
                content=ft.Image(
                    src=path,
                    fit=ft.ImageFit.CONTAIN,
                    tooltip=os.path.basename(path)
                ),
                alignment=ft.alignment.center
            )

            details_label = ft.Text(
                value=details_text,
                size=10,
                text_align=ft.TextAlign.CENTER,
                width=100
            )

            image_with_details = ft.Column(
                controls=[
                    thumbnail,
                    details_label,
                ],
                spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            )

            selected_images_grid.controls.append(
                ft.GestureDetector(
                    content=image_with_details,
                    on_tap=lambda ev, p=path: remove_selected_image(ev, p)
                )
            )
        selected_images_grid.update()

    stop_log_updater = threading.Event()

    def _log_updater_thread():
        while not stop_log_updater.is_set():
            current_logs = logger_utils.get_logs()
            if log_output_text.value != current_logs:
                log_output_text.value = current_logs
                page.update()
            time.sleep(1)

    log_thread = threading.Thread(target=_log_updater_thread, daemon=True)
    log_thread.start()
    page.on_disconnect = lambda e: stop_log_updater.set()

    def _api_worker(prompt, image_paths, api_key, model_id, aspect_ratio, resolution):
        api_task_state["status"] = "running"
        logger_utils.log(i18n.get("logic_log_newTask"))
        try:
            generated_image = api_client.call_google_genai(prompt=prompt, image_paths=image_paths, api_key=api_key,
                                                           model_id=model_id, aspect_ratio=aspect_ratio,
                                                           resolution=resolution)
            prefix = db.get_setting("file_prefix", "gemini_gen")
            filename = f"{prefix}_{int(time.time())}.png"
            temp_path = os.path.abspath(os.path.join(OUTPUT_DIR, filename))
            generated_image.save(temp_path, format="PNG")
            api_task_state.update({"result_image_path": temp_path, "status": "success"})
            api_response_image.src = temp_path
            logger_utils.log(i18n.get("logic_log_saveOk", path=temp_path))
            permanent_dir = db.get_setting("save_path")
            if permanent_dir:
                try:
                    os.makedirs(permanent_dir, exist_ok=True)
                    shutil.copy(temp_path, os.path.abspath(os.path.join(permanent_dir, filename)))
                except (IOError, OSError) as e:
                    logger_utils.log(f"Failed to copy to permanent storage: {e}")
        except Exception as e:
            api_task_state.update({"error_msg": str(e), "status": "error"})
            logger_utils.log(i18n.get("logic_warn_taskFailed", error_msg=str(e)))
        finally:
            page.update()

    def send_prompt_handler(e):
        if api_task_state["status"] == "running":
            show_snackbar(i18n.get("logic_warn_taskRunning"), is_error=True)
            return
        api_key = db.get_all_settings().get("api_key")
        if not api_key:
            show_snackbar(i18n.get("api_error_apiKey"), is_error=True)
            return
        if not prompt_input.value and not selected_images_paths:
            show_snackbar(i18n.get("logic_warn_promptEmpty"), is_error=True)
            return
        threading.Thread(target=_api_worker, args=(text_encoder(prompt_input.value), selected_images_paths, api_key,
                                                   model_selector_dropdown.value, ratio_dropdown.value,
                                                   resolution_dropdown.value)).start()
        show_snackbar(i18n.get("logic_info_taskSubmitted"))

    file_picker = ft.FilePicker(on_result=lambda e: on_file_save_result(e))
    page.overlay.append(file_picker)

    def on_file_save_result(e: ft.FilePickerResultEvent):
        if e.path and api_task_state["result_image_path"]:
            try:
                shutil.copy(api_task_state["result_image_path"], e.path)
                logger_utils.log(f"Image saved to: {e.path}")
            except Exception as ex:
                logger_utils.log(f"Error saving image: {ex}")

    def download_image_handler(e):
        if api_task_state["status"] == "success" and api_task_state["result_image_path"]:
            file_picker.save_file(file_name=os.path.basename(api_task_state['result_image_path']),
                                  allowed_extensions=['png', 'jpg', 'jpeg', 'webp'])
        else:
            show_snackbar(i18n.get("logic_warn_noImageToDownload", "No image available to download."), is_error=True)

    # --- Initialization function to be called after mount ---
    def initialize():
        refresh_prompts_dropdown()

    # --- Layout ---
    view = ft.Container(
        content=ft.Row([
            local_gallery_component(page, 4, on_image_select=add_selected_image),
            ft.VerticalDivider(),
            ft.Column(
                [
                    ft.Text(i18n.get("home_control_gallery_selected_label"), size=16, weight=ft.FontWeight.BOLD),
                    selected_images_grid,
                    ft.Divider(),
                    ft.Row([model_selector_dropdown, ratio_dropdown, resolution_dropdown]),
                    ft.Divider(),
                    ft.Row([
                        prompt_dropdown,
                        ft.IconButton(icon=ft.Icons.DOWNLOAD, on_click=load_prompt_handler,
                                      tooltip=i18n.get("home_control_prompt_btn_load")),
                        ft.IconButton(icon=ft.Icons.DELETE_FOREVER, on_click=delete_prompt_handler,
                                      tooltip=i18n.get("home_control_prompt_btn_delete")),
                    ]),

                    ft.Row(
                        controls=[
                            prompt_input,
                            ft.Column([
                                prompt_title_input,
                                ft.ElevatedButton(i18n.get("home_control_prompt_btn_save"), icon=ft.Icons.SAVE,
                                                  on_click=save_prompt_handler),
                            ],expand=1),
                        ]
                    ),
                    ft.ElevatedButton(text=i18n.get("home_control_btn_send"), icon=ft.Icons.SEND,
                                      on_click=send_prompt_handler, expand=True),
                    ft.Divider(),
                    ft.Text(i18n.get("home_control_log_label"), size=14, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        content=ft.Column(
                            [log_output_text],
                            scroll=ft.ScrollMode.AUTO,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            expand=1
                        ),
                        border=ft.border.all(1, ft.Colors.GREY_400),
                        border_radius=5,
                        padding=10,
                        height=150,
                        expand=True,
                    ),
                    ft.Divider(),
                    ft.Column(
                        alignment=MainAxisAlignment.CENTER,
                        controls=[
                            ft.Text(i18n.get("home_preview_title"), size=14, weight=ft.FontWeight.BOLD),
                            ft.Container(content=api_response_image, border=ft.border.all(1, ft.Colors.GREY_400),
                                         border_radius=5, padding=5, height=300, expand=1),
                            ft.ElevatedButton(text=i18n.get("home_preview_btn_download_placeholder"),
                                              icon=ft.Icons.DOWNLOAD, on_click=download_image_handler, expand=True)
                        ],
                        expand=1
                    )
                ], expand=6, scroll=ft.ScrollMode.AUTO)
        ], expand=True),
        expand=True,
    )

    return {"view": view, "init": initialize}
