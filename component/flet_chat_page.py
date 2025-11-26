import flet as ft
import os
import time
from typing import List, Dict, Tuple, Optional, Any
from PIL import Image # For handling image parts

import i18n
import database as db
import logger_utils
from config import (
    MODEL_SELECTOR_CHOICES,
    MODEL_SELECTOR_DEFAULT,
    AR_SELECTOR_CHOICES,
    AR_SELECTOR_DEFAULT,
    RES_SELECTOR_CHOICES,
    RES_SELECTOR_DEFAULT,
    VALID_IMAGE_EXTENSIONS # Added for file picker allowed_extensions
)
from component.flet_assets_block import FletAssetsBlock # Import the FletAssetsBlock

# Define type aliases
ChatHistory = List[Dict[str, Any]]
SessionState = Optional[Dict[str, Any]]

class FletChatPage(ft.Control): # Changed from ft.UserControl to ft.Control
    def __init__(self, page: ft.Page): # Added page as an argument
        super().__init__()
        self.page = page # Store page reference
        self.settings: Dict[str, Any] = db.get_all_settings()

        # State variables
        self.state_chat_session: SessionState = None
        self.state_response_parts: Optional[List[Any]] = None
        self.state_updated_session: SessionState = None
        self.state_chat_input_buffer: Dict[str, Any] = {"text": "", "files": []}

        # UI Components
        self.assets_block = FletAssetsBlock(page=self.page, prefix="chat_") # Pass page to FletAssetsBlock

        self.chatbot_listview = ft.ListView(
            expand=True,
            spacing=10,
            auto_scroll=True,
            controls=[]
        )

        self.chat_input_field = ft.TextField(
            hint_text=i18n.get("chat_input_placeholder"),
            multiline=True,
            min_lines=1,
            max_lines=5,
            expand=True,
            on_submit=self.on_chat_input_submit # This will trigger the send logic
        )
        self.chat_file_picker = ft.FilePicker(on_result=self.on_chat_files_picked)
        self.chat_attach_button = ft.IconButton(
            icon=ft.Icons.ATTACH_FILE, # Changed ft.icons.ATTACH_FILE to ft.Icons.ATTACH_FILE
            tooltip="Attach files",
            on_click=lambda e: self.chat_file_picker.pick_files(allow_multiple=True, allowed_extensions=[ext.lstrip('.') for ext in VALID_IMAGE_EXTENSIONS])
        )
        self.chat_send_button = ft.IconButton(
            icon=ft.Icons.SEND, # Changed ft.icons.SEND to ft.Icons.SEND
            tooltip="Send message",
            on_click=self.on_chat_input_submit
        )

        self.chat_model_selector = ft.Dropdown(
            options=[ft.dropdown.Option(choice) for choice in MODEL_SELECTOR_CHOICES],
            value=MODEL_SELECTOR_DEFAULT,
            label=i18n.get("home_control_model_label"),
            expand=2,
            # allow_other_options=True # This property is not directly available in ft.Dropdown
        )
        self.chat_ar_selector = ft.Dropdown(
            options=[ft.dropdown.Option(text=text, key=key) for text, key in i18n.get_translated_choices(AR_SELECTOR_CHOICES)],
            value=AR_SELECTOR_DEFAULT,
            label=i18n.get("home_control_ratio_label"),
            expand=1
        )
        self.chat_res_selector = ft.Dropdown(
            options=[ft.dropdown.Option(choice) for choice in RES_SELECTOR_CHOICES],
            value=RES_SELECTOR_DEFAULT,
            label=i18n.get("home_control_resolution_label"),
            expand=1
        )

        self.chat_btn_clear = ft.ElevatedButton(
            text=i18n.get("chat_btn_clear"),
            style=ft.ButtonStyle(bgcolor=ft.Colors.RED_500, color=ft.Colors.WHITE), # stop # Changed ft.colors.RED_500 to ft.Colors.RED_500
            on_click=self.clear_chat_handler
        )

        # Register file picker with the page in __init__
        self.page.overlay.append(self.chat_file_picker)
        # No need to call self.page.update() here, it will be called by the main app

    def _get_control_name(self): # Added this method
        return "fletchatpage"

    def build(self): # build method now returns the root control
        return ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        self.assets_block,
                        # No direct "add to chat input" button, selection from gallery will add to input
                    ],
                    expand=4
                ),
                ft.Column(
                    controls=[
                        ft.Card(
                            content=ft.Container(
                                # Removed padding from ft.Column directly
                                content=ft.Column(
                                    controls=[
                                        ft.Markdown(f"### {i18n.get('chat_title')}"),
                                        self.chatbot_listview,
                                        ft.Row(
                                            controls=[
                                                self.chat_attach_button,
                                                self.chat_input_field,
                                                self.chat_send_button,
                                            ]
                                        ),
                                        ft.Row(
                                            controls=[
                                                self.chat_model_selector,
                                                self.chat_ar_selector,
                                                self.chat_res_selector,
                                            ]
                                        ),
                                        self.chat_btn_clear,
                                    ],
                                    # padding=10 # Removed this line
                                ),
                                padding=ft.padding.all(10) # Padding applied to the Container wrapping the Column
                            )
                        )
                    ],
                    expand=6
                )
            ],
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.START
        )

    # --- Logic functions (adapted from chat_page.py) ---

    def add_message_to_chatbot(self, role: str, content: Any):
        if role == "user":
            avatar_color = ft.Colors.BLUE_GREY_500 # Changed ft.colors.BLUE_GREY_500 to ft.Colors.BLUE_GREY_500
            alignment = ft.MainAxisAlignment.END
        else: # assistant
            avatar_color = ft.Colors.GREEN_500 # Changed ft.colors.GREEN_500 to ft.Colors.GREEN_500
            alignment = ft.MainAxisAlignment.START

        message_content = []
        if isinstance(content, str):
            message_content.append(ft.Text(content, selectable=True))
        elif isinstance(content, Image.Image): # PIL Image
            # Save image to a temporary file to display in Flet
            # Ensure TEMP_DIR exists, or use a more robust temporary file solution
            temp_dir = os.path.join(ft.app_dir, "temp_chat_images")
            os.makedirs(temp_dir, exist_ok=True)
            temp_img_path = os.path.join(temp_dir, f"chat_img_{int(time.time() * 1000)}.png")
            content.save(temp_img_path)
            message_content.append(ft.Image(src=temp_img_path, width=200, height=200, fit=ft.ImageFit.CONTAIN))
        elif isinstance(content, dict) and 'path' in content: # Gradio Image dict
            message_content.append(ft.Image(src=content['path'], width=200, height=200, fit=ft.ImageFit.CONTAIN))
        else: # Fallback for unexpected content
            message_content.append(ft.Text(str(content)))


        self.chatbot_listview.controls.append(
            ft.Row(
                [
                    ft.Container(
                        content=ft.Column(message_content),
                        padding=10,
                        border_radius=10,
                        bgcolor=ft.Colors.BLUE_GREY_100 if role == "user" else ft.Colors.GREEN_100, # Changed ft.colors.BLUE_GREY_100 and ft.colors.GREEN_100
                        width=self.chatbot_listview.width * 0.7 if self.chatbot_listview.width else None # Limit width, handle None
                    )
                ],
                alignment=alignment
            )
        )
        self.chatbot_listview.update()

    def on_chat_files_picked(self, e: ft.FilePickerResultEvent):
        if e.files:
            for f in e.files:
                if f.path not in self.state_chat_input_buffer["files"]:
                    self.state_chat_input_buffer["files"].append(f.path)
                    # Optionally, show a preview or list of attached files
            self.page.snack_bar = ft.SnackBar(ft.Text(f"Attached {len(e.files)} files."), open=True)
            self.page.update()

    def on_chat_input_submit(self, e):
        user_text = self.chat_input_field.value
        user_files = self.state_chat_input_buffer["files"]

        if not user_text and not user_files:
            return

        # Prepare chat input buffer
        self.state_chat_input_buffer["text"] = user_text
        # Files are already in buffer

        # Display user message
        if user_files:
            for file_path in user_files:
                self.add_message_to_chatbot("user", {"path": file_path})
        if user_text:
            self.add_message_to_chatbot("user", user_text)

        # Display thinking message
        self.add_message_to_chatbot("assistant", "🤔 Thinking...")

        # Clear input field and buffer
        self.chat_input_field.value = ""
        self.state_chat_input_buffer["files"] = []
        self.chat_input_field.update()

        # Disable input while thinking (optional, can be done in main app logic)
        self.chat_input_field.disabled = True
        self.chat_attach_button.disabled = True
        self.chat_send_button.disabled = True
        self.update()

        # Trigger the actual chat task (will be handled by main app logic / ticker)
        # For now, just a placeholder
        print("Chat input submitted, triggering chat task...")
        # The main app will poll for state_chat_input_buffer and start the task

    def handle_bot_response_update_ui(self, response_parts: Optional[List[Any]], session_state_from_task: SessionState):
        """
        This function will be called by the main app's ticker/polling mechanism
        to update the UI with the bot's response.
        """
        # Remove thinking message
        if self.chatbot_listview.controls and isinstance(self.chatbot_listview.controls[-1], ft.Row):
            # Check if the last message is the "thinking..." message
            # This check needs to be more robust, as controls[0] might not be a Text control
            if (self.chatbot_listview.controls[-1].controls and
                isinstance(self.chatbot_listview.controls[-1].controls[0], ft.Container) and
                self.chatbot_listview.controls[-1].controls[0].content and
                isinstance(self.chatbot_listview.controls[-1].controls[0].content, ft.Column) and
                self.chatbot_listview.controls[-1].controls[0].content.controls and
                isinstance(self.chatbot_listview.controls[-1].controls[0].content.controls[0], ft.Text) and
                self.chatbot_listview.controls[-1].controls[0].content.controls[0].value == "🤔 Thinking..."):
                self.chatbot_listview.controls.pop()

        if response_parts is None or session_state_from_task is None:
            self.add_message_to_chatbot("assistant", "😥 Oops, something went wrong.")
            return

        self.state_chat_session = session_state_from_task

        save_dir: str = db.get_setting("save_path")
        if not save_dir:
            self.page.snack_bar = ft.SnackBar(ft.Text("Save path is not set. Images will not be saved."), open=True)
            self.page.update()

        text_parts: List[str] = [part for part in response_parts if isinstance(part, str)]
        image_parts: List[Image.Image] = [part for part in response_parts if not isinstance(part, str)]

        if text_parts:
            combined_text: str = "\n".join(text_parts)
            self.add_message_to_chatbot("assistant", combined_text)

        for img_part in image_parts:
            if save_dir:
                try:
                    os.makedirs(save_dir, exist_ok=True)
                    timestamp: int = int(time.time() * 1000)
                    filename: str = f"{session_state_from_task['id']}_{timestamp}.png"
                    filepath: str = os.path.join(save_dir, filename)
                    img_part.save(filepath)
                    self.add_message_to_chatbot("assistant", {"path": filepath})
                except (IOError, OSError) as e:
                    error_msg: str = f"Failed to save image: {e}"
                    self.page.snack_bar = ft.SnackBar(ft.Text(error_msg), open=True)
                    self.page.update()
                    self.add_message_to_chatbot("assistant", error_msg)
            else:
                self.add_message_to_chatbot("assistant", img_part)

        # Re-enable input
        self.chat_input_field.disabled = False
        self.chat_attach_button.disabled = False
        self.chat_send_button.disabled = False
        self.update()


    def clear_chat_handler(self, e):
        self.chatbot_listview.controls.clear()
        self.state_chat_session = None
        self.state_chat_input_buffer = {"text": "", "files": []}
        self.chat_input_field.value = ""
        self.chat_input_field.disabled = False
        self.chat_attach_button.disabled = False
        self.chat_send_button.disabled = False
        self.update()
