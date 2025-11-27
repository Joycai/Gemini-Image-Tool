import flet as ft
from flet.core.container import Container
from flet.core.page import Page
import threading
import os
import time
from typing import List, Any, Dict
from PIL import Image

from common import database as db, i18n, logger_utils
from geminiapi import api_client
from common.config import MODEL_SELECTOR_CHOICES, AR_SELECTOR_CHOICES, RES_SELECTOR_CHOICES, OUTPUT_DIR
from fletapp.component.flet_image_preview_dialog import ImagePreviewDialog

def chat_page(page: Page) -> Dict[str, Any]:
    # --- State Management ---
    chat_session_state: Dict[str, Any] = {"session_obj": None}
    genai_client = None # Persistent client instance
    api_task_running = threading.Event()
    uploaded_image_paths: List[str] = []

    # --- Reusable Components ---
    image_previewer = ImagePreviewDialog(page)
    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)

    # --- Controls ---
    def open_chat_image_preview(image_path: str):
        image_previewer.open(image_path=image_path, on_download=download_image)

    class Message(ft.Row):
        def __init__(self, role: str, parts: List[Any]):
            super().__init__()
            self.vertical_alignment = ft.CrossAxisAlignment.START
            
            content_controls = []
            for part in parts:
                if isinstance(part, str):
                    content_controls.append(ft.Markdown(part, selectable=True, extension_set="gitHubWeb", code_theme="atom-one-dark"))
                elif isinstance(part, ft.Image):
                    part.border_radius = ft.border_radius.all(10)
                    part.width = 400
                    content_controls.append(
                        ft.GestureDetector(
                            content=part,
                            on_double_tap=lambda e, p=part.src: open_chat_image_preview(p)
                        )
                    )

            bubble_content = ft.Column(content_controls, tight=True, spacing=5)
            
            if role == "user":
                self.alignment = ft.MainAxisAlignment.END
                bubble = ft.Container(
                    content=bubble_content,
                    bgcolor="primaryContainer",
                    padding=10,
                    border_radius=10,
                    margin=ft.margin.only(left=50)
                )
                icon = ft.Icon(name=ft.Icons.PERSON, size=30)
                self.controls = [bubble, icon]
            else: # assistant
                self.alignment = ft.MainAxisAlignment.START
                bubble = ft.Container(
                    content=bubble_content,
                    bgcolor="surfaceVariant",
                    padding=10,
                    border_radius=10,
                    margin=ft.margin.only(right=50)
                )
                icon = ft.Icon(name=ft.Icons.ASSISTANT, size=30)
                self.controls = [icon, bubble]

    chat_history = ft.ListView(expand=True, spacing=20, auto_scroll=True)
    thumbnail_row = ft.Row(wrap=True, spacing=10)
    user_input = ft.TextField(label=i18n.get("chat_input_label"), hint_text=i18n.get("chat_input_placeholder"), expand=True, multiline=True, shift_enter=True)
    send_button = ft.IconButton(icon=ft.Icons.SEND, tooltip=i18n.get("home_control_btn_send"), on_click=lambda e: send_message_handler())
    model_selector = ft.Dropdown(label=i18n.get("home_control_model_label"), options=[ft.dropdown.Option(model) for model in MODEL_SELECTOR_CHOICES], value=MODEL_SELECTOR_CHOICES[0], expand=2)
    ar_selector = ft.Dropdown(label=i18n.get("home_control_ratio_label"), options=[ft.dropdown.Option(key=value, text=text) for text, value in i18n.get_translated_choices(AR_SELECTOR_CHOICES)], value=AR_SELECTOR_CHOICES[0], expand=1)
    res_selector = ft.Dropdown(label=i18n.get("home_control_resolution_label"), options=[ft.dropdown.Option(res) for res in RES_SELECTOR_CHOICES], value=RES_SELECTOR_CHOICES[0], expand=1)
    prompt_dropdown = ft.Dropdown(label=i18n.get("home_control_prompt_label_history"), hint_text=i18n.get("home_control_prompt_placeholder"), options=[], expand=True)
    prompt_title_input = ft.TextField(label=i18n.get("home_control_prompt_save_label"), hint_text=i18n.get("home_control_prompt_save_placeholder"), expand=True)

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
        user_input.value = content
        logger_utils.log(i18n.get("logic_log_loadPrompt", title=selected_title))
        user_input.update()

    def save_prompt_handler(e):
        title = prompt_title_input.value
        content = user_input.value
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

    def update_thumbnail_display():
        thumbnail_row.controls.clear()
        for path in uploaded_image_paths:
            thumbnail_row.controls.append(
                ft.GestureDetector(
                    on_double_tap=lambda e, p=path: remove_uploaded_image(p),
                    content=ft.Image(src=path, width=70, height=70, fit=ft.ImageFit.COVER, border_radius=ft.border_radius.all(5))
                )
            )
        thumbnail_row.update()

    def remove_uploaded_image(path_to_remove: str):
        if path_to_remove in uploaded_image_paths:
            uploaded_image_paths.remove(path_to_remove)
            update_thumbnail_display()

    def on_files_picked(e: ft.FilePickerResultEvent):
        if e.files:
            for f in e.files:
                if f.path not in uploaded_image_paths:
                    uploaded_image_paths.append(f.path)
            update_thumbnail_display()
    
    file_picker.on_result = on_files_picked
    upload_button = ft.IconButton(icon=ft.Icons.UPLOAD_FILE, tooltip="Upload Images", on_click=lambda _: file_picker.pick_files(allow_multiple=True, file_type=ft.FilePickerFileType.IMAGE))

    def clear_chat_handler(e):
        nonlocal genai_client
        chat_history.controls.clear()
        chat_session_state["session_obj"] = None
        genai_client = None
        uploaded_image_paths.clear()
        update_thumbnail_display()
        logger_utils.log("Chat cleared.")
        page.update()

    clear_button = ft.ElevatedButton(text=i18n.get("chat_btn_clear"), on_click=clear_chat_handler, icon=ft.Icons.CLEAR_ALL)

    def _chat_worker(client, prompt_parts: List[Any], model: str, ar: str, res: str):
        try:
            updated_chat_obj, response_parts = api_client.call_google_chat(
                genai_client=client,
                chat_session=chat_session_state.get("session_obj"),
                prompt_parts=prompt_parts,
                model_id=model,
                aspect_ratio=ar,
                resolution=res,
            )
            
            chat_session_state["session_obj"] = updated_chat_obj
            
            if chat_history.controls and isinstance(chat_history.controls[-1], Message):
                last_bubble = chat_history.controls[-1].controls[1]
                if isinstance(last_bubble, ft.Container) and last_bubble.content.controls[0].value == "🤔 Thinking...":
                    chat_history.controls.pop()

            text_parts = [part for part in response_parts if isinstance(part, str)]
            image_parts = [part for part in response_parts if not isinstance(part, str)]

            if text_parts:
                chat_history.controls.append(Message(role="assistant", parts=["\n\n".join(text_parts)]))
                page.update()

            save_dir = db.get_setting("save_path", OUTPUT_DIR)
            if image_parts:
                if not os.path.isdir(save_dir):
                    try: os.makedirs(save_dir, exist_ok=True)
                    except OSError as e: logger_utils.log(f"Could not create save directory: {e}"); save_dir = None
                
                for i, img_part in enumerate(image_parts):
                    if save_dir:
                        try:
                            filepath = os.path.join(save_dir, f"chat_{int(time.time() * 1000)}_{i}.png")
                            img_part.save(filepath)
                            flet_image = ft.Image(src=filepath)
                            chat_history.controls.append(Message(role="assistant", parts=[flet_image]))
                        except Exception as e:
                            chat_history.controls.append(Message(role="assistant", parts=[f"[Error saving image: {e}]"]))
                    else:
                        chat_history.controls.append(Message(role="assistant", parts=["[Image could not be displayed because save path is not set.]"]))
                page.update()
        except Exception as e:
            logger_utils.log(f"Chat API call failed: {e}")
            if chat_history.controls and isinstance(chat_history.controls[-1], Message):
                last_bubble = chat_history.controls[-1].controls[1]
                if isinstance(last_bubble, ft.Container) and last_bubble.content.controls[0].value == "🤔 Thinking...":
                    chat_history.controls.pop()
            chat_history.controls.append(Message(role="assistant", parts=[f"😥 Oops, something went wrong:\n\n{e}"]))
        finally:
            api_task_running.clear()
            user_input.disabled = False
            send_button.disabled = False
            page.update()

    def send_message_handler():
        nonlocal genai_client
        if api_task_running.is_set(): return
        
        prompt_text = user_input.value
        if not prompt_text and not uploaded_image_paths: return

        api_key = db.get_all_settings().get("api_key")
        if not api_key:
            chat_history.controls.append(Message(role="assistant", parts=[i18n.get("api_error_apiKey")])); page.update(); return

        if genai_client is None:
            genai_client = api_client.genai.Client(api_key=api_key)

        api_task_running.set()
        user_input.disabled = True
        send_button.disabled = True
        
        prompt_parts: List[Any] = []
        user_message_parts: List[Any] = []

        for path in uploaded_image_paths:
            prompt_parts.append(Image.open(path))
            user_message_parts.append(ft.Image(src=path, width=150, border_radius=ft.border_radius.all(5)))
        
        if prompt_text:
            prompt_parts.append(prompt_text)
            user_message_parts.append(prompt_text)

        chat_history.controls.append(Message(role="user", parts=user_message_parts))
        chat_history.controls.append(Message(role="assistant", parts=["🤔 Thinking..."]))
        user_input.value = ""
        uploaded_image_paths.clear()
        update_thumbnail_display()
        page.update()

        threading.Thread(target=_chat_worker, args=(genai_client, prompt_parts, model_selector.value, ar_selector.value, res_selector.value)).start()

    user_input.on_submit = lambda e: send_message_handler()

    def download_image(image_path: str):
        def on_save_result(e: ft.FilePickerResultEvent):
            if e.path:
                try:
                    import shutil
                    shutil.copy(image_path, e.path)
                except Exception as ex:
                    logger_utils.log(f"Error saving image: {ex}")
        
        file_picker.on_result = on_save_result
        file_picker.save_file(file_name=os.path.basename(image_path))

    # --- Initialization function to be called after mount ---
    def initialize():
        refresh_prompts_dropdown()

    view = ft.Container(
        content=ft.Column([
            chat_history,
            ft.Row([model_selector, ar_selector, res_selector]),
            ft.Divider(),
            ft.Row([
                prompt_dropdown,
                ft.IconButton(icon=ft.Icons.DOWNLOAD, on_click=load_prompt_handler, tooltip=i18n.get("home_control_prompt_btn_load")),
                ft.IconButton(icon=ft.Icons.DELETE_FOREVER, on_click=delete_prompt_handler, tooltip=i18n.get("home_control_prompt_btn_delete")),
            ]),
            thumbnail_row,
            ft.Row([user_input, upload_button, send_button], vertical_alignment=ft.CrossAxisAlignment.START),
            ft.Row([
                prompt_title_input,
                ft.ElevatedButton(i18n.get("home_control_prompt_btn_save"), icon=ft.Icons.SAVE, on_click=save_prompt_handler),
            ]),
            ft.Row([clear_button])
        ]),
        padding=ft.padding.all(10),
        expand=True,
    )
    
    return {"view": view, "init": initialize}
