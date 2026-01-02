import json
import threading
import time
from dataclasses import dataclass
from typing import Callable

import flet as ft
from flet import Container
from flet import Page

from common import database as db, i18n


@dataclass
class State:
    output_picker: ft.FilePicker | None = None
    export_picker: ft.FilePicker | None = None
    import_picker: ft.FilePicker | None = None
    last_save_path: str | None = None


state = State()


def settings_page(page: Page, on_restart: Callable[[], None]) -> Container:
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

    def show_snackbar(message: str, is_error: bool = False):
        page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.ERROR if is_error else ft.Colors.GREEN_700,
        )
        page.snack_bar.open = True
        page.update()

    # --- Save Settings Logic ---
    def save_settings_handler(e):
        try:
            db.save_setting("api_key", api_key_input.value or "")
            db.save_setting("save_path", save_path_input.value or "outputs")
            db.save_setting("file_prefix", file_prefix_input.value or "gemini_gen")
            db.save_setting("language", lang_dropdown.value or "en")
            show_snackbar(i18n.get("settings_saved_content", "Settings have been saved successfully."))
        except Exception as ex:
            show_snackbar(f"{i18n.get('settings_saved_error_content', 'Failed to save settings:')} {ex}", is_error=True)

    # --- Database Clear Logic ---
    confirm_dialog = None

    def close_confirm_dialog(e):
        if confirm_dialog:
            page.close(confirm_dialog)

    def confirm_clear_data(e):
        if confirm_dialog:
            close_confirm_dialog(e)
        try:
            db.clear_all_data()
            show_snackbar(i18n.get("settings_clear_success", "All data has been cleared successfully."))
            # Reload settings on the page
            load_initial_settings()
        except Exception as ex:
            show_snackbar(i18n.get("settings_clear_error", "Error clearing data: {error}", error=ex), is_error=True)

    def clear_data_handler(e):
        if confirm_dialog:
            page.open(confirm_dialog)

    confirm_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(i18n.get("settings_clear_confirm_title", "Confirm Clear Data")),
        content=ft.Text(i18n.get("settings_clear_confirm_content",
                                 "Are you sure you want to delete all data? This action cannot be undone.")),
        actions=[
            ft.TextButton(i18n.get("dialog_btn_confirm", "Confirm"), on_click=confirm_clear_data,
                          style=ft.ButtonStyle(color="red")),
            ft.TextButton(i18n.get("dialog_btn_cancel", "Cancel"), on_click=close_confirm_dialog),
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
            show_snackbar(
                i18n.get("settings_export_success", "Data successfully exported to {path}", path=save_file_path))
        except Exception as ex:
            show_snackbar(i18n.get("settings_export_error", "Error exporting data: {error}", error=ex), is_error=True)

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
            show_snackbar(i18n.get("settings_import_error", "Error importing data: {error}", error=ex), is_error=True)

    async def pick_output_directory_btn_handler():
        if state.output_picker is None:
            state.output_picker = ft.FilePicker()
        output_directory = await state.output_picker.get_directory_path()
        if output_directory:
            save_path_input.value = output_directory
            db.save_setting("save_path", output_directory)

    # --- UI Layout ---
    pick_output_directory_btn = ft.Button(
        content=i18n.get("settings_btn_pick_directory", "Choose..."),
        icon=ft.Icons.FOLDER_OPEN,
        on_click=pick_output_directory_btn_handler
    )
    save_button = ft.Button(content=i18n.get("settings_btn_save"), on_click=save_settings_handler, icon=ft.Icons.SAVE)
    export_button = ft.Button(content=i18n.get("settings_btn_export", "Export All Data"), icon=ft.Icons.UPLOAD,
                              on_click=export_btn_handler)
    import_button = ft.Button(content=i18n.get("settings_btn_import", "Import All Data"), icon=ft.Icons.DOWNLOAD,
                              on_click=import_btn_handler)
    clear_button = ft.Button(content=i18n.get("settings_btn_clear", "Clear All Data"), icon=ft.Icons.DELETE_FOREVER,
                             on_click=clear_data_handler, color="white", bgcolor="red")
    restart_button = ft.Button(content=i18n.get("settings_btn_restart", "Restart Application"),
                               icon=ft.Icons.RESTART_ALT, on_click=lambda _: on_restart(), color="white", bgcolor="red")

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
                ft.Row([import_button, export_button, clear_button], alignment=ft.MainAxisAlignment.START),
                ft.Divider(),
                ft.Text(i18n.get("settings_app_management_title", "Application Management"), size=18,
                        weight=ft.FontWeight.BOLD),
                restart_button,
            ],
            spacing=20,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=ft.padding.all(20),
        expand=True,
    )
