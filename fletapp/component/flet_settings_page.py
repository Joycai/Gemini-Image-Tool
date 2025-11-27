import flet as ft
from flet.core.container import Container
from flet.core.page import Page
import json
import time
import threading

from common import database as db, i18n, logger_utils

def settings_page(page: Page) -> Container:
    # --- Controls ---
    api_key_input = ft.TextField(label=i18n.get("settings_label_apiKey"), password=True, can_reveal_password=True)
    save_path_input = ft.TextField(label=i18n.get("settings_label_savePath"))
    file_prefix_input = ft.TextField(label=i18n.get("settings_label_prefix"))
    lang_dropdown = ft.Dropdown(
        label=i18n.get("settings_label_language"),
        options=[
            ft.dropdown.Option(key="en", text="English"),
            ft.dropdown.Option(key="zh", text="中文"),
        ],
    )

    def show_snackbar(message: str, is_error: bool = False):
        page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.ERROR if is_error else ft.Colors.GREEN_700,
        )
        page.snack_bar.open = True
        page.update()

    def close_dialog(e):
        if page.dialog:
            page.dialog.open = False
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

    # --- Import/Export Logic ---
    def on_export_result(e: ft.FilePickerResultEvent):
        if e.path:
            try:
                all_data = db.export_all_data()
                with open(e.path, "w", encoding="utf-8") as f:
                    json.dump(all_data, f, ensure_ascii=False, indent=4)
                show_snackbar(f"Data successfully exported to {e.path}")
            except Exception as ex:
                show_snackbar(f"Error exporting data: {ex}", is_error=True)

    def on_import_result(e: ft.FilePickerResultEvent):
        if e.files and e.files[0].path:
            filepath = e.files[0].path
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data_to_import = json.load(f)
                db.import_all_data(data_to_import)
                
                # Show a confirmation dialog instructing user to restart
                page.dialog = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Import Successful"),
                    content=ft.Text("Data has been imported. Please restart the application for all changes to take effect."),
                    actions=[ft.TextButton("OK", on_click=close_dialog)],
                )
                page.dialog.open = True
                page.update()
                
            except Exception as ex:
                show_snackbar(f"Error importing data: {ex}", is_error=True)

    export_picker = ft.FilePicker(on_result=on_export_result)
    import_picker = ft.FilePicker(on_result=on_import_result)
    page.overlay.extend([export_picker, import_picker])

    # --- UI Layout ---
    save_button = ft.ElevatedButton(text=i18n.get("settings_btn_save"), on_click=save_settings_handler, icon=ft.Icons.SAVE)
    export_button = ft.ElevatedButton("Export All Data", icon=ft.Icons.UPLOAD, on_click=lambda _: export_picker.save_file(file_name=f"g_ai_edit_backup_{int(time.time())}.json", allowed_extensions=["json"]))
    import_button = ft.ElevatedButton("Import All Data", icon=ft.Icons.DOWNLOAD, on_click=lambda _: import_picker.pick_files(allow_multiple=False, allowed_extensions=["json"]))

    # --- Initialization Logic ---
    def load_initial_settings():
        settings = db.get_all_settings()
        api_key_input.value = settings.get("api_key", "")
        save_path_input.value = settings.get("save_path", "outputs")
        file_prefix_input.value = settings.get("file_prefix", "gemini_gen")
        lang_dropdown.value = settings.get("language", "en")
        page.update()

    # Use a short timer to ensure the page is ready before loading data
    threading.Timer(0.1, load_initial_settings).start()

    return ft.Container(
        content=ft.Column(
            [
                ft.Text(i18n.get("settings_title"), size=24, weight=ft.FontWeight.BOLD),
                api_key_input,
                save_path_input,
                file_prefix_input,
                lang_dropdown,
                save_button,
                ft.Divider(),
                ft.Text("Data Management", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([import_button, export_button], alignment=ft.MainAxisAlignment.START),
            ],
            spacing=20,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=ft.padding.all(20),
        expand=True,
    )
