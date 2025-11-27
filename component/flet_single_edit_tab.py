import flet as ft
from flet.core.container import Container
from flet.core.page import Page
import os
from typing import Callable, List
import threading
import time
import shutil

# Custom imports
import database as db
import api_client
import logger_utils
import i18n
from component.flet_gallery_component import local_gallery_component
from config import MODEL_SELECTOR_CHOICES, AR_SELECTOR_CHOICES, RES_SELECTOR_CHOICES, OUTPUT_DIR

# Ensure OUTPUT_DIR exists
os.makedirs(OUTPUT_DIR, exist_ok=True)


def single_edit_tab(page: Page) -> Container:
    selected_images_paths: List[str] = []
    
    # API Task State (local to this tab instance)
    api_task_state = {
        "status": "idle",  # idle, running, success, error
        "result_image_path": None,
        "error_msg": None,
    }

    selected_images_grid = ft.GridView(
        runs_count=5,
        max_extent=100, # Smaller thumbnails for selected images
        spacing=5,
        run_spacing=5,
        child_aspect_ratio=1.0,
        padding=0,
        controls=[],
        expand=True,
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

    # Components for the right-hand side (output/control panel)
    prompt_input = ft.TextField(
        label="Prompt Input",
        multiline=True,
        min_lines=3,
        max_lines=5,
        hint_text="Enter your prompt here...",
        expand=True
    )
    
    log_output_text = ft.Text("Log messages will appear here...", selectable=True)
    api_response_image = ft.Image(
        src="https://via.placeholder.com/300x200?text=API+Response", # Placeholder image
        fit=ft.ImageFit.CONTAIN,
        expand=True
    )

    def _update_log(message: str, append: bool = True):
        if append:
            log_output_text.value += "\n" + message
        else:
            log_output_text.value = message
        page.update()

    # Threading event to stop the log updater thread
    stop_log_updater = threading.Event()

    def _log_updater_thread():
        while not stop_log_updater.is_set():
            current_logs = logger_utils.get_logs()
            if log_output_text.value != current_logs:
                log_output_text.value = current_logs
                page.update()
            time.sleep(1) # Update every 1 second

    # Start the log updater thread
    log_thread = threading.Thread(target=_log_updater_thread, daemon=True)
    log_thread.start()

    # Register a handler to stop the thread when the page disconnects
    def on_page_disconnect(e):
        stop_log_updater.set()
    page.on_disconnect = on_page_disconnect


    def _api_worker(prompt: str, image_paths: List[str], api_key: str, model_id: str, aspect_ratio: str, resolution: str):
        api_task_state["status"] = "running"
        api_task_state["result_image_path"] = None
        api_task_state["error_msg"] = None
        logger_utils.log(i18n.get("logic_log_newTask"))
        logger_utils.log(f"Sending request to Gemini API...")
        
        try:
            generated_image = api_client.call_google_genai(
                prompt=prompt,
                image_paths=image_paths,
                api_key=api_key,
                model_id=model_id,
                aspect_ratio=aspect_ratio,
                resolution=resolution
            )
            
            prefix = db.get_setting("file_prefix", "gemini_gen")
            timestamp = int(time.time())
            filename = f"{prefix}_{timestamp}.png"
            temp_path = os.path.abspath(os.path.join(OUTPUT_DIR, filename))
            generated_image.save(temp_path, format="PNG")
            
            api_task_state["result_image_path"] = temp_path
            api_task_state["status"] = "success"
            
            api_response_image.src = temp_path
            logger_utils.log(i18n.get("logic_log_saveOk", path=temp_path))
            
            # Optionally copy to permanent save path if configured
            permanent_dir = db.get_setting("save_path")
            if permanent_dir:
                try:
                    os.makedirs(permanent_dir, exist_ok=True)
                    permanent_path = os.path.abspath(os.path.join(permanent_dir, filename))
                    shutil.copy(temp_path, permanent_path)
                    logger_utils.log(f"Copied to permanent storage: {permanent_path}")
                except (IOError, OSError) as e:
                    logger_utils.log(f"Failed to copy to permanent storage: {e}")

        except Exception as e:
            error_msg = str(e)
            api_task_state["error_msg"] = error_msg
            api_task_state["status"] = "error"
            logger_utils.log(i18n.get("logic_warn_taskFailed", error_msg=error_msg))
        finally:
            page.update() # Ensure UI updates after task completion/error

    def send_prompt_handler(e):
        if api_task_state["status"] == "running":
            logger_utils.log("An API task is already running. Please wait.")
            return

        api_key = db.get_all_settings().get("api_key")
        if not api_key:
            logger_utils.log(i18n.get("api_error_apiKey"))
            return

        current_prompt = prompt_input.value
        selected_model = model_selector_dropdown.value
        selected_ratio = ratio_dropdown.value
        selected_resolution = resolution_dropdown.value
        
        if not current_prompt and not selected_images_paths:
            logger_utils.log("Please provide a prompt or select images.")
            return

        threading.Thread(
            target=_api_worker,
            args=(
                current_prompt,
                selected_images_paths,
                api_key,
                selected_model,
                selected_ratio,
                selected_resolution
            )
        ).start()
        logger_utils.log(i18n.get("logic_info_taskSubmitted"))


    def download_image_handler(e):
        if api_task_state["status"] == "success" and api_task_state["result_image_path"]:
            # In a real app, you'd use ft.FilePicker to let the user choose a save location.
            # For now, we'll just log the path and simulate a download.
            logger_utils.log(f"Simulating download of: {api_task_state['result_image_path']}")
            # Example of how you might use a FilePicker for saving:
            # page.dialog = ft.FilePicker(on_result=lambda e: print(f"Save path: {e.path}"))
            # page.dialog.save_file(
            #     file_name=os.path.basename(api_task_state['result_image_path']),
            #     allowed_extensions=['png']
            # )
            # page.update()
        else:
            logger_utils.log("No image available to download.")


    ratio_dropdown = ft.Dropdown(
        label="Ratio",
        options=[ft.dropdown.Option(ar) for ar in AR_SELECTOR_CHOICES],
        value=AR_SELECTOR_CHOICES[0],
        expand=1
    )
    resolution_dropdown = ft.Dropdown(
        label="Resolution",
        options=[ft.dropdown.Option(res) for res in RES_SELECTOR_CHOICES],
        value=RES_SELECTOR_CHOICES[0],
        expand=1
    )
    model_selector_dropdown = ft.Dropdown(
        label="Select Model",
        options=[ft.dropdown.Option(model) for model in MODEL_SELECTOR_CHOICES],
        value=MODEL_SELECTOR_CHOICES[0],
        expand=True
    )

    return ft.Container(
        content=ft.Row(
            [
                local_gallery_component(page, 4, on_image_select=add_selected_image),
                ft.VerticalDivider(), # Changed from ft.Divider() for vertical separation
                ft.Column(
                    [
                        ft.Text("Selected Images", size=16, weight=ft.FontWeight.BOLD),
                        selected_images_grid,
                        ft.Divider(),
                        # Ratio and Resolution Dropdowns
                        ft.Row(
                            [
                                ratio_dropdown,
                                resolution_dropdown,
                            ],
                            alignment=ft.MainAxisAlignment.START
                        ),
                        # Prompt Input
                        prompt_input,
                        # Send Button
                        ft.ElevatedButton(
                            text="Send Prompt",
                            icon=ft.Icons.SEND,
                            on_click=send_prompt_handler,
                            expand=True
                        ),
                        ft.Divider(),
                        # Model Selection
                        model_selector_dropdown,
                        ft.Divider(),
                        # Log Display
                        ft.Text("Log Output:", size=14, weight=ft.FontWeight.BOLD),
                        ft.Container(
                            content=ft.Column(
                                [
                                    log_output_text
                                ],
                                scroll=ft.ScrollMode.AUTO,
                                expand=True
                            ),
                            border=ft.border.all(1, ft.Colors.GREY_400),
                            border_radius=5,
                            padding=10,
                            height=150, # Fixed height for log area
                            expand=True
                        ),
                        ft.Divider(),
                        # API Returned Image Preview
                        ft.Text("Response Preview:", size=14, weight=ft.FontWeight.BOLD),
                        ft.Container(
                            content=api_response_image,
                            border=ft.border.all(1, ft.Colors.GREY_400),
                            border_radius=5,
                            padding=5,
                            height=300, # Fixed height for image preview
                            expand=True
                        ),
                        # Download Button
                        ft.ElevatedButton(
                            text="Download Original Image",
                            icon=ft.Icons.DOWNLOAD,
                            on_click=download_image_handler,
                            expand=True
                        )
                    ],
                    expand=6,
                    horizontal_alignment=ft.CrossAxisAlignment.START,
                    scroll=ft.ScrollMode.AUTO # Ensure this column is scrollable if content overflows
                )
            ],
            expand=True
        ),
        expand=True
    )