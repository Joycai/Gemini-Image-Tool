import os
import asyncio
import time
from typing import List, Any, Dict

import flet as ft
from PIL import Image
from flet import Page, BoxFit, MarkdownExtensionSet, MarkdownCodeTheme

from common import database as db, i18n, logger_utils
from common.config import MODEL_SELECTOR_CHOICES, AR_SELECTOR_CHOICES, RES_SELECTOR_CHOICES, OUTPUT_DIR
from common.job_manager import job_manager, Job
from common.text_encoder import text_encoder
from fletapp.component.common_component import show_snackbar
from fletapp.component.flet_image_preview_dialog import preview_dialog, PreviewDialogData
from geminiapi import api_client


def chat_page(page: Page) -> Dict[str, Any]:
    # --- State Management ---
    chat_session_state: Dict[str, Any] = {"session_obj": None}
    genai_client = None  # Persistent client instance
    uploaded_image_paths: List[str] = []

    # --- Controls ---
    def open_chat_image_preview(image_path: str):
        image_preview_dialog = preview_dialog(
            page,
            PreviewDialogData(
                image_list=[image_path],
                current_index=0
            ),
            on_deleted_callback_fnc=None)
        page.show_dialog(image_preview_dialog)

    class Message(ft.Row):
        def __init__(self, role: str, parts: List[Any]):
            super().__init__()
            self.vertical_alignment = ft.CrossAxisAlignment.START

            content_controls = []
            for part in parts:
                if isinstance(part, str):
                    content_controls.append(
                        ft.Markdown(part, selectable=True, extension_set=MarkdownExtensionSet.GITHUB_WEB,
                                    code_theme=MarkdownCodeTheme.GOOGLE_CODE))
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
                icon = ft.Icon(ft.Icons.PERSON, size=30)
                self.controls = [bubble, icon]
            else:  # assistant
                self.alignment = ft.MainAxisAlignment.START
                bubble = ft.Container(
                    content=bubble_content,
                    bgcolor="surfaceVariant",
                    padding=10,
                    border_radius=10,
                    margin=ft.margin.only(right=50)
                )
                icon = ft.Icon(ft.Icons.ASSISTANT, size=30)
                self.controls = [icon, bubble]

    chat_history = ft.ListView(expand=True, spacing=20, auto_scroll=True)
    thumbnail_row = ft.Row(wrap=True, spacing=10)
    user_input = ft.TextField(label=i18n.get("chat_input_label"), hint_text=i18n.get("chat_input_placeholder"),
                              expand=True, multiline=True, shift_enter=True)
    
    progress_ring = ft.ProgressRing(width=16, height=16, stroke_width=2, visible=False)
    send_button = ft.IconButton(icon=ft.Icons.SEND, tooltip=i18n.get("home_control_btn_send"),
                                on_click=lambda e: asyncio.create_task(send_message_handler()))
    
    model_selector = ft.Dropdown(label=i18n.get("home_control_model_label"),
                                 options=[ft.dropdown.Option(model) for model in MODEL_SELECTOR_CHOICES],
                                 value=MODEL_SELECTOR_CHOICES[0], expand=2)
    ar_selector = ft.Dropdown(label=i18n.get("home_control_ratio_label"),
                              options=[ft.dropdown.Option(key=value, text=text) for text, value in
                                       i18n.get_translated_choices(AR_SELECTOR_CHOICES)], value=AR_SELECTOR_CHOICES[0],
                              expand=1)
    res_selector = ft.Dropdown(label=i18n.get("home_control_resolution_label"),
                               options=[ft.dropdown.Option(res) for res in RES_SELECTOR_CHOICES],
                               value=RES_SELECTOR_CHOICES[0], expand=1)
    prompt_dropdown = ft.Dropdown(label=i18n.get("home_control_prompt_label_history"),
                                  hint_text=i18n.get("home_control_prompt_placeholder"), options=[], expand=True)
    prompt_title_input = ft.TextField(label=i18n.get("home_control_prompt_save_label"),
                                      hint_text=i18n.get("home_control_prompt_save_placeholder"), expand=True)

    # --- Functions ---

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
        user_input.value = content
        logger_utils.log(i18n.get("logic_log_loadPrompt", title=selected_title))
        user_input.update()

    def save_prompt_handler(e):
        title = prompt_title_input.value
        content = user_input.value
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

    def update_thumbnail_display():
        thumbnail_row.controls.clear()
        for path in uploaded_image_paths:
            thumbnail_row.controls.append(
                ft.GestureDetector(
                    on_double_tap=lambda e, p=path: remove_uploaded_image(p),
                    content=ft.Image(src=path, width=70, height=70, fit=BoxFit.COVER,
                                     border_radius=ft.border_radius.all(5))
                )
            )
        thumbnail_row.update()

    def remove_uploaded_image(path_to_remove: str):
        if path_to_remove in uploaded_image_paths:
            uploaded_image_paths.remove(path_to_remove)
            update_thumbnail_display()

    async def upload_image_handler(e):
        file_picker = ft.FilePicker()
        files = await file_picker.pick_files(allow_multiple=True, file_type=ft.FilePickerFileType.IMAGE)
        if files:
            for f in files:
                if f.path not in uploaded_image_paths:
                    uploaded_image_paths.append(f.path)
            update_thumbnail_display()

    upload_button = ft.IconButton(icon=ft.Icons.UPLOAD_FILE,
                                  on_click=upload_image_handler,
                                  tooltip=i18n.get("chat_btn_pick_images_tooltip", "select Images"))

    def clear_chat_handler(e):
        nonlocal genai_client
        chat_history.controls.clear()
        chat_session_state["session_obj"] = None
        genai_client = None
        uploaded_image_paths.clear()
        update_thumbnail_display()
        logger_utils.log("Chat cleared.")
        page.update()

    clear_button = ft.Button(content=i18n.get("chat_btn_clear"), on_click=clear_chat_handler, icon=ft.Icons.CLEAR_ALL)

    async def handle_api_success(result):
        if result:
            updated_chat_obj, response_parts = result
            chat_session_state["session_obj"] = updated_chat_obj

            # Remove "Thinking" message
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
                    try:
                        os.makedirs(save_dir, exist_ok=True)
                    except OSError as e:
                        logger_utils.log(f"Could not create save directory: {e}")
                        save_dir = None

                for i, img_part in enumerate(image_parts):
                    if save_dir:
                        try:
                            filepath = os.path.join(save_dir, f"chat_{int(time.time() * 1000)}_{i}.png")
                            # Save image in thread
                            await asyncio.to_thread(img_part.save, filepath)
                            flet_image = ft.Image(src=filepath)
                            chat_history.controls.append(Message(role="assistant", parts=[flet_image]))
                        except Exception as e:
                            chat_history.controls.append(
                                Message(role="assistant", parts=[f"[Error saving image: {e}]"]))
                    else:
                        chat_history.controls.append(Message(role="assistant", parts=[
                            "[Image could not be displayed because save path is not set.]"]))
                page.update()

    async def handle_api_error(error_msg):
        logger_utils.log(f"Chat API call failed: {error_msg}")
        if chat_history.controls and isinstance(chat_history.controls[-1], Message):
            last_bubble = chat_history.controls[-1].controls[1]
            if isinstance(last_bubble, ft.Container) and last_bubble.content.controls[0].value == "🤔 Thinking...":
                chat_history.controls.pop()
        chat_history.controls.append(Message(role="assistant", parts=[f"😥 Oops, something went wrong:\n\n{error_msg}"]))
        page.update()

    async def handle_api_finally():
        user_input.disabled = False
        send_button.disabled = False
        progress_ring.visible = False
        page.update()

    async def send_message_handler():
        nonlocal genai_client

        prompt_text = text_encoder(user_input.value)
        if not prompt_text and not uploaded_image_paths: return

        api_key = db.get_all_settings().get("api_key")
        if not api_key:
            chat_history.controls.append(Message(role="assistant", parts=[i18n.get("api_error_apiKey")]))
            page.update()
            return

        if genai_client is None:
            genai_client = api_client.genai.Client(api_key=api_key)

        user_input.disabled = True
        send_button.disabled = True
        progress_ring.visible = True

        prompt_parts: List[Any] = []
        user_message_parts: List[Any] = []

        for path in uploaded_image_paths:
            # Open images in thread pool
            img = await asyncio.to_thread(Image.open, path)
            prompt_parts.append(img)
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

        # Create and add job to queue
        job = Job(
            id=f"chat_{int(time.time() * 1000)}",
            name=f"Chat: {prompt_text[:20]}..." if prompt_text else "Chat (Image only)",
            task_func=api_client.call_google_chat,
            kwargs={
                "genai_client": genai_client,
                "chat_session": chat_session_state.get("session_obj"),
                "prompt_parts": prompt_parts,
                "model_id": model_selector.value,
                "aspect_ratio": ar_selector.value,
                "resolution": res_selector.value,
            },
            on_success=handle_api_success,
            on_error=handle_api_error,
            on_finally=handle_api_finally
        )
        await job_manager.add_job(job)

    user_input.on_submit = lambda e: asyncio.create_task(send_message_handler())

    # --- Initialization function to be called after mount ---
    def initialize():
        page.pubsub.subscribe(on_prompts_update)
        refresh_prompts_dropdown()

    view = ft.Container(
        content=ft.Column([
            chat_history,
            ft.Divider(),
            ft.Row([model_selector, ar_selector, res_selector, ft.Container(expand=True)]),
            ft.Divider(),
            ft.Row([
                ft.Row([
                    prompt_dropdown,
                    ft.IconButton(icon=ft.Icons.DOWNLOAD, on_click=load_prompt_handler,
                                  tooltip=i18n.get("home_control_prompt_btn_load")),
                    ft.IconButton(icon=ft.Icons.DELETE_FOREVER, on_click=delete_prompt_handler,
                                  tooltip=i18n.get("home_control_prompt_btn_delete"))
                ], expand=4),
                ft.Row([
                    prompt_title_input,
                    ft.Button(content=i18n.get("home_control_prompt_btn_save"), icon=ft.Icons.SAVE,
                              on_click=save_prompt_handler)
                ], expand=2),
            ]),
            thumbnail_row,
            ft.Row([user_input, upload_button, ft.Stack([send_button, ft.Container(progress_ring, margin=ft.margin.only(left=12, top=12))])], vertical_alignment=ft.CrossAxisAlignment.START),
            ft.Row([clear_button])
        ]),
        padding=ft.padding.all(10),
        expand=True,
    )

    return {"view": view, "init": initialize}
