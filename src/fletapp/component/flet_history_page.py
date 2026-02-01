import asyncio
import os
import platform
import subprocess

import flet as ft
from flet import Container, BoxFit
from flet import Page

from common import database as db, i18n, logger_utils
from common.config import VALID_IMAGE_EXTENSIONS, OUTPUT_DIR
from common.image_util import get_image_details
from common.prompts import AI_RECOGNIZE_TASKS
from fletapp.component.common_component import show_snackbar
from fletapp.component.flet_image_preview_dialog import PreviewDialogData, preview_dialog
from geminiapi import unified_client


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

    def delete_image(image_path):
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
                load_history_images()
                show_snackbar(page, i18n.get("logic_info_deleteSuccess", "Image Deleted"))
        except Exception as ex:
            show_snackbar(page, f"Error: {ex}", is_error=True)

    def _show_ai_recognize_dialog(image_path: str):
        # Load last prompt from DB
        last_prompt = db.get_setting("last_ai_recognize_prompt", AI_RECOGNIZE_TASKS["recognize"]["prompt"])
        
        prompt_input = ft.TextField(
            label="Custom Task / Prompt",
            value=last_prompt,
            multiline=True,
            min_lines=3,
            max_lines=5,
            expand=True
        )
        
        response_text = ft.Markdown(
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            code_theme=ft.MarkdownCodeTheme.GOOGLE_CODE,
        )
        
        progress_ring = ft.ProgressRing(visible=False)
        
        def on_task_change(e):
            if e.control.value in AI_RECOGNIZE_TASKS:
                prompt_input.value = AI_RECOGNIZE_TASKS[e.control.value]["prompt"]
            prompt_input.update()

        task_dropdown = ft.Dropdown(
            label="Pre-defined Tasks",
            options=[
                *[ft.dropdown.Option(key=k, text=v["name"]) for k, v in AI_RECOGNIZE_TASKS.items()],
                ft.dropdown.Option(key="custom", text="Custom Task"),
            ],
            value="custom"
        )
        task_dropdown.on_change = on_task_change

        async def run_ai_task(e):
            settings = db.get_all_settings()
            model_id = settings.get("recognition_model_id")
            
            if not model_id:
                show_snackbar(page, "Recognition model not configured in settings.", is_error=True)
                return

            # Save prompt to DB
            db.save_setting("last_ai_recognize_prompt", prompt_input.value)
            
            run_button.disabled = True
            progress_ring.visible = True
            response_text.value = "Processing..."
            page.update()

            try:
                # Use unified_client for recognition
                from PIL import Image
                img = await asyncio.to_thread(Image.open, image_path)
                
                result = await asyncio.to_thread(
                    unified_client.chat_completions,
                    model_id=model_id,
                    messages=[],
                    prompt_parts=[img, prompt_input.value]
                )
                
                # Extract text from result parts
                if isinstance(result, tuple) and len(result) == 2:
                    _, parts = result
                    text_result = ""
                    for part in parts:
                        if isinstance(part, str):
                            text_result += part
                    response_text.value = text_result
                else:
                    response_text.value = "Unexpected response format."

            except Exception as ex:
                response_text.value = f"Error: {ex}"
            finally:
                run_button.disabled = False
                progress_ring.visible = False
                page.update()

        run_button = ft.ElevatedButton("Run AI Task", icon=ft.Icons.PLAY_ARROW, on_click=run_ai_task)

        def close_dlg(e):
            page.pop_dialog()

        dlg = ft.AlertDialog(
            title=ft.Text(f"AI Recognize: {os.path.basename(image_path)}"),
            content=ft.Container(
                content=ft.Column([
                    ft.Image(src=image_path, height=200, fit=ft.BoxFit.CONTAIN),
                    task_dropdown,
                    prompt_input,
                    ft.Row([run_button, progress_ring], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Divider(),
                    ft.Column([
                        response_text,
                    ], scroll=ft.ScrollMode.AUTO, height=300)
                ], tight=True, scroll=ft.ScrollMode.AUTO),
                width=600,
            ),
            actions=[
                ft.TextButton("Close", on_click=close_dlg)
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dlg)

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

                # Use a closure to capture the current 'img_path' and 'i' correctly
                def create_context_menu_handler(current_path, current_index):
                    def _show_context_menu(e):
                        def _handle_delete(ev):
                            page.pop_dialog()
                            delete_image(current_path)
                        
                        def _handle_preview(ev):
                            page.pop_dialog()
                            open_preview_dialog(current_index)
                        
                        def _handle_ai_recognize(ev):
                            page.pop_dialog()
                            _show_ai_recognize_dialog(current_path)

                        def close_context_dlg(ev):
                            page.pop_dialog()

                        page.show_dialog(
                            ft.AlertDialog(
                                title=ft.Text(os.path.basename(current_path)),
                                content=ft.Column([
                                    ft.ListTile(
                                        leading=ft.Icon(ft.Icons.AUTO_FIX_HIGH, color=ft.Colors.AMBER_600),
                                        title=ft.Text("AI Recognize"),
                                        on_click=_handle_ai_recognize
                                    ),
                                    ft.ListTile(
                                        leading=ft.Icon(ft.Icons.PREVIEW),
                                        title=ft.Text(i18n.get("dialog_title_image_preview", "Preview")),
                                        on_click=_handle_preview
                                    ),
                                    ft.ListTile(
                                        leading=ft.Icon(ft.Icons.DELETE_OUTLINE, color=ft.Colors.RED_400),
                                        title=ft.Text(i18n.get("dialog_btn_delete", "Delete")),
                                        on_click=_handle_delete
                                    ),
                                ], tight=True),
                                actions=[
                                    ft.TextButton(i18n.get("dialog_btn_close", "Close"), on_click=close_context_dlg)
                                ],
                                actions_alignment=ft.MainAxisAlignment.END,
                            )
                        )
                    return _show_context_menu

                context_menu_handler = create_context_menu_handler(img_path, i)

                history_grid.controls.append(
                    ft.GestureDetector(
                        content=image_with_details,
                        on_double_tap=lambda e, index=i: open_preview_dialog(index),
                        on_secondary_tap=context_menu_handler,
                        on_long_press=context_menu_handler,
                    )
                )
        except Exception as e:
            logger_utils.log(f"Error loading history images: {e}")
            history_grid.controls.append(ft.Text(f"Error: {e}"))

        if page: page.update()

    def on_job_completed(topic: str):
        """Callback for PubSub when a job is completed."""
        load_history_images()

    def open_preview_dialog(current_index: int):
        image_preview_dialog = preview_dialog(
            page,
            PreviewDialogData(
                image_list=image_files,
                current_index=current_index
            ),
            on_deleted_callback_fnc=load_history_images)
        page.show_dialog(image_preview_dialog)

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

    # --- Initialization ---
    page.pubsub.subscribe(on_job_completed)
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
