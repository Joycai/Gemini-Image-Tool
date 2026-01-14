import asyncio
import os
import shutil
import time
from dataclasses import dataclass
from typing import List, Dict, Any

import flet as ft
# Custom imports
from common import database as db, logger_utils, i18n
from common.config import MODEL_SELECTOR_CHOICES, AR_SELECTOR_CHOICES, RES_SELECTOR_CHOICES, OUTPUT_DIR, VALID_IMAGE_EXTENSIONS
from common.image_util import get_image_details
from common.job_manager import job_manager, Job
from common.text_encoder import text_encoder
from flet import MainAxisAlignment
from flet import Page, BoxFit, Alignment, FilePickerFileType
from fletapp.component.common_component import show_snackbar
from fletapp.component.flet_gallery_component import local_gallery_component
from geminiapi import api_client

# Ensure OUTPUT_DIR exists
os.makedirs(OUTPUT_DIR, exist_ok=True)


@dataclass
class State:
    selected_images_paths: List[str] | None = None
    file_picker: ft.FilePicker | None = None
    last_save_path: str | None = None


state = State()


def single_edit_tab(page: Page) -> Dict[str, Any]:
    if state.selected_images_paths is None:
        state.selected_images_paths = []

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
        width=300,
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
    api_response_image = ft.Image(src="https://via.placeholder.com/300x200?text=API+Response", fit=BoxFit.CONTAIN,
                                  expand=True)

    progress_bar = ft.ProgressBar(width=400, color="blue", visible=False)
    
    send_button = ft.ElevatedButton(
        content=ft.Text(i18n.get("home_control_btn_send")), 
        icon=ft.Icons.SEND,
        on_click=lambda e: asyncio.create_task(send_prompt_handler(e, disable_ui=True)), 
        expand=True
    )
    
    queue_button = ft.ElevatedButton(
        content=ft.Text(i18n.get("home_control_btn_queue")), 
        icon=ft.Icons.QUEUE,
        on_click=lambda e: asyncio.create_task(send_prompt_handler(e, disable_ui=False)), 
        expand=True,
        style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ft.Colors.BLUE_GREY_700)
    )

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

    def refresh_prompts_dropdown():
        titles = db.get_all_prompt_titles()
        prompt_dropdown.options = [ft.dropdown.Option(title) for title in titles]
        prompt_dropdown.update()

    def on_prompts_update(topic: str):
        refresh_prompts_dropdown()

    def load_prompt_handler(e):
        selected_title = prompt_dropdown.value
        if not selected_title:
            show_snackbar(page, i18n.get("logic_warn_promptNotSelected", "Please select a prompt to load."),
                          is_error=True)
            return
        content = db.get_prompt_content(selected_title)
        prompt_input.value = content
        logger_utils.log(i18n.get("logic_log_loadPrompt", title=selected_title))
        prompt_input.update()

    def save_prompt_handler(e):
        title = prompt_title_input.value
        content = prompt_input.value
        if not title or not content:
            show_snackbar(page, i18n.get("logic_warn_promptEmpty"), is_error=True)
            return
        db.save_prompt(title, content)
        page.pubsub.send_all("prompts_updated")
        logger_utils.log(i18n.get("logic_log_savePrompt", title=title))
        show_snackbar(page, i18n.get("logic_info_promptSaved", title=title))
        prompt_title_input.value = ""
        prompt_title_input.update()

    def delete_prompt_handler(e):
        selected_title = prompt_dropdown.value
        if not selected_title:
            show_snackbar(page, i18n.get("logic_warn_promptNotSelected", "Please select a prompt to delete."),
                          is_error=True)
            return
        db.delete_prompt(selected_title)
        page.pubsub.send_all("prompts_updated")
        logger_utils.log(i18n.get("logic_log_deletePrompt", title=selected_title))
        show_snackbar(page, i18n.get("logic_info_promptDeleted", title=selected_title))
        prompt_dropdown.value = None

    # --- Other Functions (Image selection, API calls, etc.) ---
    def remove_selected_image(e, image_path):
        if image_path in state.selected_images_paths:
            state.selected_images_paths.remove(image_path)
            update_selected_images_display()

    def add_selected_image(image_path: str):
        if image_path not in state.selected_images_paths:
            state.selected_images_paths.append(image_path)
            update_selected_images_display()

    def update_selected_images_display():
        selected_images_grid.controls.clear()
        for path in state.selected_images_paths:
            details_text = get_image_details(path)

            thumbnail = ft.Container(
                width=100,
                height=100,
                border_radius=ft.border_radius.all(5),
                content=ft.Image(
                    src=path,
                    fit=BoxFit.CONTAIN,
                    tooltip=os.path.basename(path)
                ),
                alignment=Alignment.CENTER
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

    def on_log_update(new_logs: str):
        log_output_text.value = new_logs
        page.update()

    async def handle_api_start(disable_ui: bool):
        api_task_state["status"] = "running"
        progress_bar.visible = True
        if disable_ui:
            send_button.disabled = True
            queue_button.disabled = True
        page.update()
        logger_utils.log(i18n.get("logic_log_newTask"))

    async def handle_api_success(generated_image):
        if generated_image:
            prefix = db.get_setting("file_prefix", "gemini_gen")
            filename = f"{prefix}_{int(time.time())}.png"
            temp_path = os.path.abspath(os.path.join(OUTPUT_DIR, filename))

            # Save image in thread to avoid blocking
            await asyncio.to_thread(generated_image.save, temp_path, format="PNG")

            api_task_state.update({"result_image_path": temp_path, "status": "success"})
            api_response_image.src = temp_path
            logger_utils.log(i18n.get("logic_log_saveOk", path=temp_path))

            permanent_dir = db.get_setting("save_path")
            if permanent_dir:
                try:
                    os.makedirs(permanent_dir, exist_ok=True)
                    await asyncio.to_thread(shutil.copy, temp_path,
                                            os.path.abspath(os.path.join(permanent_dir, filename)))
                except (IOError, OSError) as e:
                    logger_utils.log(f"Failed to copy to permanent storage: {e}")
            page.update()
        else:
            api_task_state.update({"status": "error", "error_msg": "No image returned"})

    async def handle_api_error(error_msg):
        api_task_state.update({"error_msg": str(error_msg), "status": "error"})
        logger_utils.log(i18n.get("logic_warn_taskFailed", error_msg=str(error_msg)))
        page.update()

    async def handle_api_finally():
        progress_bar.visible = False
        send_button.disabled = False
        queue_button.disabled = False
        page.update()

    async def send_prompt_handler(e, disable_ui: bool = True):
        api_key = db.get_all_settings().get("api_key")
        if not api_key:
            show_snackbar(page, i18n.get("api_error_apiKey"), is_error=True)
            return
        if not prompt_input.value and not state.selected_images_paths:
            show_snackbar(page, i18n.get("logic_warn_promptEmpty"), is_error=True)
            return

        job = Job(
            id=f"single_edit_{int(time.time() * 1000)}",
            task_func=api_client.call_google_genai,
            kwargs={
                "prompt": text_encoder(prompt_input.value),
                "image_paths": state.selected_images_paths.copy(), # Copy to avoid mutation
                "api_key": api_key,
                "model_id": model_selector_dropdown.value,
                "aspect_ratio": ratio_dropdown.value,
                "resolution": resolution_dropdown.value
            },
            on_start=lambda: handle_api_start(disable_ui),
            on_success=handle_api_success,
            on_error=handle_api_error,
            on_finally=handle_api_finally
        )
        await job_manager.add_job(job)
        show_snackbar(page, i18n.get("logic_info_taskSubmitted"))

    async def download_image_handler(e):
        if api_task_state["status"] == "success" and api_task_state["result_image_path"]:
            if state.file_picker is None:
                state.file_picker = ft.FilePicker()
            temp_file_path = api_task_state["result_image_path"]
            with open(temp_file_path, 'rb') as f:
                file_bytes = f.read()
            saved_path = await state.file_picker.save_file(file_name=os.path.basename(temp_file_path),
                                              allowed_extensions=[ext.strip('.') for ext in VALID_IMAGE_EXTENSIONS],
                                              src_bytes=file_bytes,
                                              file_type=FilePickerFileType.IMAGE)
            show_snackbar(page, saved_path,
                          is_error=False)
        else:
            show_snackbar(page, i18n.get("logic_warn_noImageToDownload", "No image available to download."),
                          is_error=True)

    # --- Initialization function to be called after mount ---
    def initialize():
        page.pubsub.subscribe(on_prompts_update)
        logger_utils.subscribe(on_log_update)
        refresh_prompts_dropdown()
        if state.file_picker is None:
            state.file_picker = ft.FilePicker()

    # Clean up on close
    def on_close():
        logger_utils.unsubscribe(on_log_update)

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
                        ft.Container(expand=True)
                    ]),

                    ft.Row(
                        controls=[
                            prompt_input,
                            ft.Column([
                                prompt_title_input,
                                ft.Button(content=i18n.get("home_control_prompt_btn_save"), icon=ft.Icons.SAVE,
                                          on_click=save_prompt_handler),
                            ], expand=1),
                        ]
                    ),
                    progress_bar,
                    ft.Row([send_button, queue_button], spacing=10),
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
                            ft.Button(content=i18n.get("home_preview_btn_download_placeholder"),
                                      icon=ft.Icons.DOWNLOAD, on_click=download_image_handler, expand=True)
                        ],
                        expand=1
                    )
                ], expand=6, scroll=ft.ScrollMode.AUTO)
        ],
            expand=True),
        expand=True,
    )

    return {"view": view, "init": initialize}
