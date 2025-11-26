import flet as ft
import json
import os
import shutil
import time
from typing import List, Dict, Any, Optional

import i18n
import database as db
import logger_utils
from config import UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR

# Assuming main_page.refresh_prompt_dropdown will be called from FletMainPage instance
# For now, we'll just log or use a placeholder.

class FletSettingsPage(ft.Control): # Changed from ft.UserControl to ft.Control
    def __init__(self, page: ft.Page): # Added page as an argument
        super().__init__()
        self.page = page # Store page reference
        self.settings: Dict[str, Any] = db.get_all_settings()

        # UI Components
        self.api_key_input = ft.TextField(
            label=i18n.get("settings_label_apiKey"),
            value=self.settings["api_key"],
            password=True,
            can_reveal_password=True,
            expand=2
        )
        self.save_path_input = ft.TextField(
            label=i18n.get("settings_label_savePath"),
            value=self.settings["save_path"],
            expand=True
        )
        self.file_prefix_input = ft.TextField(
            label=i18n.get("settings_label_prefix"),
            value=self.settings["file_prefix"],
            expand=True
        )
        self.language_dropdown = ft.Dropdown(
            options=[
                ft.dropdown.Option(text="中文", key="zh"), # Changed to explicitly use text=
                ft.dropdown.Option(text="English", key="en") # Changed to explicitly use text=
            ],
            value=self.settings["language"],
            label=i18n.get("settings_label_language"),
            expand=True
        )
        self.btn_save_settings = ft.ElevatedButton(
            text=i18n.get("settings_btn_save"),
            on_click=self.save_settings_handler,
            expand=1
        )
        self.btn_export_prompts = ft.ElevatedButton(
            text=i18n.get("settings_btn_export_prompts"),
            on_click=self.export_prompts_handler,
            expand=True
        )
        self.file_picker_export = ft.FilePicker(on_result=self.on_export_file_result)
        self.file_picker_import = ft.FilePicker(on_result=self.on_import_file_result)
        self.btn_import_prompts = ft.ElevatedButton(
            text=i18n.get("settings_btn_import_prompts"),
            on_click=lambda e: self.file_picker_import.pick_files(allow_multiple=False, allowed_extensions=["json"]),
            expand=True
        )
        self.exported_file_text = ft.Text(
            value="",
            visible=False # Initially hidden
        )
        self.btn_clear_cache = ft.ElevatedButton(
            text=i18n.get("settings_btn_clear_cache"),
            on_click=self.clear_cache_handler,
            expand=1,
            style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_GREY_500, color=ft.Colors.WHITE)
        )
        self.btn_restart = ft.ElevatedButton(
            text="🔄 Restart",
            on_click=self.restart_app_handler,
            expand=1,
            style=ft.ButtonStyle(bgcolor=ft.Colors.RED_500, color=ft.Colors.WHITE)
        )

        # Register file pickers with the page in __init__
        self.page.overlay.append(self.file_picker_export)
        self.page.overlay.append(self.file_picker_import)
        # No need to call self.page.update() here, it will be called by the main app

    def _get_control_name(self): # Added this method
        return "fletsettingspage"

    def build(self): # build method now returns the root control
        return ft.Column(
            controls=[
                ft.Card(
                    content=ft.Container(
                        # Removed padding from ft.Column directly
                        content=ft.Column(
                            controls=[
                                ft.Markdown(f"## {i18n.get('settings_title')}"),
                                ft.Row(
                                    controls=[self.api_key_input]
                                ),
                                ft.Row(
                                    controls=[self.save_path_input, self.file_prefix_input]
                                ),
                                ft.Row(
                                    controls=[self.language_dropdown]
                                ),
                                ft.Row(
                                    controls=[self.btn_save_settings]
                                ),
                                ft.ExpansionTile(
                                    title=ft.Text(i18n.get("settings_label_prompt_management")),
                                    initially_expanded=True,
                                    controls=[
                                        ft.Row(
                                            controls=[
                                                self.btn_export_prompts,
                                                self.btn_import_prompts,
                                            ]
                                        ),
                                        self.exported_file_text, # Display exported file path
                                    ]
                                ),
                                ft.Row(
                                    controls=[
                                        self.btn_clear_cache,
                                        self.btn_restart,
                                    ]
                                ),
                            ],
                            # padding=10 # Removed this line
                        ),
                        padding=ft.padding.all(10) # Padding applied to the Container wrapping the Column
                    )
                )
            ],
            expand=True
        )

    # --- Logic functions (adapted from settings_page.py) ---

    def save_settings_handler(self, e):
        db.save_setting("api_key", self.api_key_input.value)
        db.save_setting("save_path", self.save_path_input.value)
        db.save_setting("file_prefix", self.file_prefix_input.value)
        db.save_setting("language", self.language_dropdown.value)
        logger_utils.log(i18n.get("logic_info_configSaved"))
        self.page.snack_bar = ft.SnackBar(ft.Text(i18n.get("logic_info_configSaved")), open=True)
        self.page.update()
        # Need to trigger app restart or client re-initialization in main app logic

    def clear_cache_handler(self, e):
        dirs_to_clear = [UPLOAD_DIR, OUTPUT_DIR]
        for d in dirs_to_clear:
            if os.path.exists(d):
                shutil.rmtree(d)
            os.makedirs(d)
        self.page.snack_bar = ft.SnackBar(ft.Text(i18n.get("logic_info_cacheCleared")), open=True)
        self.page.update()

    async def export_prompts_handler(self, e):
        try:
            prompts = db.get_all_prompts_for_export()
            timestamp = int(time.time())
            filename = f"prompts_export_{timestamp}.json"
            filepath = os.path.join(TEMP_DIR, filename)

            os.makedirs(TEMP_DIR, exist_ok=True) # Ensure TEMP_DIR exists

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(prompts, f, ensure_ascii=False, indent=4)

            logger_utils.log(i18n.get("logic_info_prompts_exported", count=len(prompts)))
            self.page.snack_bar = ft.SnackBar(ft.Text(i18n.get("logic_info_prompts_exported", count=len(prompts))), open=True)
            self.page.update()

            # Use FilePicker to offer download
            await self.file_picker_export.save_file(
                file_name=filename,
                allowed_extensions=["json"],
                file_path=filepath # Provide initial path
            )
            self.exported_file_text.value = f"Exported to: {filepath}"
            self.exported_file_text.visible = True
            self.exported_file_text.update()

        except (IOError, OSError, json.JSONDecodeError) as err:
            error_msg = i18n.get("logic_error_prompts_export_failed", error=str(err))
            logger_utils.log(error_msg)
            self.page.snack_bar = ft.SnackBar(ft.Text(error_msg), open=True)
            self.page.update()
            self.exported_file_text.visible = False
            self.exported_file_text.update()

    def on_export_file_result(self, e: ft.FilePickerResultEvent):
        # This callback is triggered after save_file dialog is closed
        if e.path:
            self.page.snack_bar = ft.SnackBar(ft.Text(f"Prompts saved to: {e.path}"), open=True)
            self.page.update()
        else:
            self.page.snack_bar = ft.SnackBar(ft.Text("Export cancelled."), open=True)
            self.page.update()

    def on_import_file_result(self, e: ft.FilePickerResultEvent):
        if not e.files:
            self.page.snack_bar = ft.SnackBar(ft.Text("No file selected for import."), open=True)
            self.page.update()
            return

        file_to_import = e.files[0].path
        try:
            with open(file_to_import, 'r', encoding='utf-8') as f:
                prompts_to_import = json.load(f)

            count = db.import_prompts_from_list(prompts_to_import)

            self.page.snack_bar = ft.SnackBar(ft.Text(i18n.get("logic_info_prompts_imported", count=count)), open=True)
            self.page.update()
            logger_utils.log(i18n.get("logic_info_prompts_imported", count=count))
            # Need to trigger refresh of prompt dropdown in FletMainPage
            # This will require a way to communicate between pages or a global state manager
            # For now, we'll just log.
        except (IOError, OSError, json.JSONDecodeError) as err:
            error_msg = i18n.get("logic_error_prompts_import_failed", error=str(err))
            logger_utils.log(error_msg)
            self.page.snack_bar = ft.SnackBar(ft.Text(error_msg), open=True)
            self.page.update()

    def restart_app_handler(self, e):
        # This will require a mechanism to restart the Flet app,
        # which is typically handled outside the Flet app itself (e.g., by a wrapper script).
        # For now, we'll just log and inform the user.
        logger_utils.log("Application restart requested.")
        self.page.snack_bar = ft.SnackBar(ft.Text("Application restart requested. Please close and reopen the app."), open=True)
        self.page.update()
        # In a real scenario, you might call sys.exit(0) or os.execv to restart.
