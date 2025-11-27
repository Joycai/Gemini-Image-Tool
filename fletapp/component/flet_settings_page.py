import flet as ft
from flet.core.container import Container
from flet.core.page import Page

from common import database as db, i18n

def settings_page(page: Page) -> Container:
    # --- Controls ---
    api_key_input = ft.TextField(
        label=i18n.get("settings_label_apiKey"),
        password=True,
        can_reveal_password=True,
    )
    save_path_input = ft.TextField(
        label=i18n.get("settings_label_savePath"),
    )
    file_prefix_input = ft.TextField(
        label=i18n.get("settings_label_prefix"),
    )
    lang_dropdown = ft.Dropdown(
        label=i18n.get("settings_label_language"),
        options=[
            ft.dropdown.Option(key="zh", text="中文"),
            ft.dropdown.Option(key="en", text="English"),
        ],
    )

    def save_settings_handler(e):
        try:
            db.save_setting("api_key", api_key_input.value)
            db.save_setting("save_path", save_path_input.value)
            db.save_setting("file_prefix", file_prefix_input.value)
            db.save_setting("language", lang_dropdown.value)
            
            # Show a confirmation dialog
            page.dialog = ft.AlertDialog(
                title=ft.Text(i18n.get("settings_saved_title", "Success")),
                content=ft.Text(i18n.get("settings_saved_content", "Settings have been saved successfully.")),
                actions=[ft.TextButton("OK", on_click=lambda _: close_dialog(e))],
            )
            page.dialog.open = True
            page.update()
        except Exception as ex:
            # Show an error dialog
            page.dialog = ft.AlertDialog(
                title=ft.Text(i18n.get("settings_saved_error_title", "Error")),
                content=ft.Text(f"{i18n.get('settings_saved_error_content', 'Failed to save settings:')} {ex}"),
                actions=[ft.TextButton("OK", on_click=lambda _: close_dialog(e))],
            )
            page.dialog.open = True
            page.update()

    def close_dialog(e):
        page.dialog.open = False
        page.update()

    save_button = ft.ElevatedButton(
        text=i18n.get("settings_btn_save"),
        on_click=save_settings_handler,
        icon=ft.Icons.SAVE
    )

    # --- Initialization Logic ---
    def load_initial_settings():
        settings = db.get_all_settings()
        api_key_input.value = settings.get("api_key", "")
        save_path_input.value = settings.get("save_path", "")
        file_prefix_input.value = settings.get("file_prefix", "")
        lang_dropdown.value = settings.get("language", "en")
        page.update()

    # Use a short timer to ensure the page is ready before loading data
    import threading
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
            ],
            spacing=20,
            # Make the column scrollable if content overflows
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=ft.padding.all(20),
        expand=True,
    )
