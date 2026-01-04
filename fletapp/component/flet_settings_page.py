import json
import os
import platform
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass

import flet as ft
from flet import Container
from flet import Page

from common import database as db, i18n, logger_utils
from common.config import UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR
from fletapp.component.common_component import show_snackbar


@dataclass
class State:
    output_picker: ft.FilePicker | None = None
    export_picker: ft.FilePicker | None = None
    import_picker: ft.FilePicker | None = None
    last_save_path: str | None = None


state = State()


def settings_page(page: Page) -> Container:
    # --- Controls ---
    api_key_input = ft.TextField(
        label=i18n.get("settings_label_apiKey"),
        password=True,
        can_reveal_password=True)
    lang_dropdown = ft.Dropdown(
        label=i18n.get("settings_label_language"),
        options=[
            ft.dropdown.Option(key="en", text=i18n.get("settings_lang_en", "English")),
            ft.dropdown.Option(key="zh", text=i18n.get("settings_lang_zh", "中文")),
        ],
    )
    save_path_input = ft.TextField(label=i18n.get("settings_label_savePath"))
    file_prefix_input = ft.TextField(label=i18n.get("settings_label_prefix"))

    # --- Save Settings Logic ---
    def save_settings_handler(e):
        try:
            db.save_setting("api_key", api_key_input.value or "")
            db.save_setting("save_path", save_path_input.value or "outputs")
            db.save_setting("file_prefix", file_prefix_input.value or "gemini_gen")
            db.save_setting("language", lang_dropdown.value or "en")
            show_snackbar(page, i18n.get("settings_saved_content", "Settings have been saved successfully."))
        except Exception as ex:
            show_snackbar(page, f"{i18n.get('settings_saved_error_content', 'Failed to save settings:')} {ex}",
                          is_error=True)

    # --- Cache Clear Logic ---
    def clear_cache_handler(e):
        try:
            dirs_to_clear = [UPLOAD_DIR, OUTPUT_DIR]
            for d in dirs_to_clear:
                if os.path.exists(d):
                    shutil.rmtree(d)
                os.makedirs(d, exist_ok=True)
            show_snackbar(page, i18n.get("logic_info_cacheCleared", "Cache cleared successfully."))
        except Exception as ex:
            show_snackbar(page, f"Error clearing cache: {ex}", is_error=True)

    def open_temp_folder_handler(e):
        path = TEMP_DIR
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

    # --- Database Clear Logic ---
    confirm_dialog = None

    def close_confirm_dialog(e):
        if confirm_dialog:
            page.pop_dialog()

    def confirm_clear_data(e):
        if confirm_dialog:
            close_confirm_dialog(e)
        try:
            db.clear_all_data()
            show_snackbar(page, i18n.get("settings_clear_success", "All data has been cleared successfully."))
            # Reload settings on the page
            load_initial_settings()
        except Exception as ex:
            show_snackbar(page, i18n.get("settings_clear_error", "Error clearing data: {error}", error=ex),
                          is_error=True)

    def clear_data_handler(e):
        if confirm_dialog:
            page.show_dialog(confirm_dialog)

    confirm_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(i18n.get("settings_clear_confirm_title", "Confirm Clear Data")),
        content=ft.Text(i18n.get("settings_clear_confirm_content",
                                 "Are you sure you want to delete all data? This action cannot be undone.")),
        actions=[
            ft.TextButton(i18n.get("dialog_btn_confirm", "Confirm"),
                          on_click=confirm_clear_data),
            ft.TextButton(i18n.get("dialog_btn_cancel", "Cancel"),
                          on_click=close_confirm_dialog),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    # import confirm dalog
    import_dialog = {}

    def close_import_dialog(e):
        if import_dialog:
            page.pop_dialog()

    import_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(i18n.get("settings_import_success_title", "Import Successful")),
        content=ft.Text(i18n.get("settings_import_success_content",
                                 "Data has been imported. Please restart the application for all changes to take effect.")),
        actions=[ft.TextButton(i18n.get("dialog_btn_ok", "OK"), on_click=close_import_dialog)],
    )

    async def export_btn_handler():
        if state.export_picker is None:
            state.export_picker = ft.FilePicker()
        try:
            all_data = db.export_all_data()
            json_bytes = json.dumps(all_data, ensure_ascii=False).encode('utf-8')
            save_file_path = await state.export_picker.save_file(file_name=f"g_ai_edit_backup_{int(time.time())}.json",
                                                                 allowed_extensions=["json"],
                                                                 src_bytes=json_bytes
                                                                 )
            show_snackbar(page,
                          i18n.get("settings_export_success", "Data successfully exported to {path}",
                                   path=save_file_path))
        except Exception as ex:
            show_snackbar(page, i18n.get("settings_export_error", "Error exporting data: {error}", error=ex),
                          is_error=True)

    async def import_btn_handler():
        if state.import_picker is None:
            state.import_picker = ft.FilePicker()
        files = await state.import_picker.pick_files(allow_multiple=False, allowed_extensions=["json"])
        try:
            with open(files[0].path, "r", encoding="utf-8") as f:
                data_to_import = json.load(f)
            db.import_all_data(data_to_import)
            page.show_dialog(import_dialog)

        except Exception as ex:
            show_snackbar(page, i18n.get("settings_import_error", "Error importing data: {error}", error=ex),
                          is_error=True)

    async def pick_output_directory_btn_handler():
        if state.output_picker is None:
            state.output_picker = ft.FilePicker()
        output_directory = await state.output_picker.get_directory_path()
        if output_directory:
            save_path_input.value = output_directory
            db.save_setting("save_path", output_directory)

    # --- UI Layout ---
    pick_output_directory_btn = ft.Button(
        content=i18n.get("settings_btn_pick_savePath", "Choose..."),
        icon=ft.Icons.FOLDER_OPEN,
        on_click=pick_output_directory_btn_handler
    )
    save_button = ft.Button(content=i18n.get("settings_btn_save"), on_click=save_settings_handler, icon=ft.Icons.SAVE)
    export_button = ft.Button(content=i18n.get("settings_btn_export", "Export All Data"), icon=ft.Icons.UPLOAD,
                              on_click=export_btn_handler)
    import_button = ft.Button(content=i18n.get("settings_btn_import", "Import All Data"), icon=ft.Icons.DOWNLOAD,
                              on_click=import_btn_handler)
    
    clear_cache_button = ft.Button(content=i18n.get("settings_btn_clear_cache", "Clear Cache"),
                                   icon=ft.Icons.CLEANING_SERVICES,
                                   on_click=clear_cache_handler)

    open_temp_button = ft.Button(content=i18n.get("settings_btn_open_temp", "Browse Cache"),
                                 icon=ft.Icons.FOLDER_OPEN,
                                 on_click=open_temp_folder_handler)

    clear_db_button = ft.Button(content=i18n.get("settings_btn_clear_db", "Clear All Data"),
                             icon=ft.Icons.DELETE_FOREVER,
                             on_click=clear_data_handler, color="white", bgcolor="red")

    # --- Initialization Logic ---
    def load_initial_settings():
        settings = db.get_all_settings()
        api_key_input.value = settings.get("api_key", "")
        save_path_input.value = settings.get("save_path", "outputs")
        file_prefix_input.value = settings.get("file_prefix", "gemini_gen")
        lang_dropdown.value = settings.get("language", "en")
        page.update()

    threading.Timer(0.1, load_initial_settings).start()

    return ft.Container(
        content=ft.Column(
            [
                ft.Text(i18n.get("settings_title"), size=24, weight=ft.FontWeight.BOLD),
                lang_dropdown,
                ft.Row(controls=[api_key_input, ft.Container(expand=True)]),
                file_prefix_input,
                ft.Row([save_path_input, pick_output_directory_btn]),
                save_button,
                ft.Divider(),
                ft.Text(i18n.get("settings_data_management_title", "Data Management"), size=18,
                        weight=ft.FontWeight.BOLD),
                ft.Row([import_button, export_button], alignment=ft.MainAxisAlignment.START),
                ft.Divider(),
                ft.Text(i18n.get("settings_app_management_title", "Application Management"), size=18,
                        weight=ft.FontWeight.BOLD),
                ft.Row([open_temp_button, clear_cache_button, clear_db_button])
            ],
            spacing=20,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=ft.padding.all(20),
        expand=True,
    )
