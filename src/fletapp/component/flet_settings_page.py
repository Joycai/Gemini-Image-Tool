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
    # --- Google GenAI Controls ---
    google_paid_key_input = ft.TextField(
        label=i18n.get("settings_label_apiKey", "Paid API Key"),
        password=True,
        can_reveal_password=True,
        expand=True)
    
    google_free_key_input = ft.TextField(
        label=i18n.get("settings_label_refineApiKey", "Free API Key"),
        password=True,
        can_reveal_password=True,
        expand=True)
    
    google_use_paid_checkbox = ft.Checkbox(
        label=i18n.get("settings_label_usePaidForAll", "Same as paid key (Use paid key for all models)"),
        value=False
    )

    # --- OpenAI Controls ---
    openai_api_key_input = ft.TextField(
        label="OpenAI API Key",
        password=True,
        can_reveal_password=True,
        expand=True)
    
    openai_base_url_input = ft.TextField(
        label="OpenAI Base URL",
        value="https://api.openai.com/v1")

    # --- Model Config Area ---
    refine_model_dropdown = ft.Dropdown(
        label=i18n.get("settings_label_refineModel", "Refine Agent Model"),
        options=[],
        expand=True
    )
    
    recognition_model_dropdown = ft.Dropdown(
        label=i18n.get("settings_label_recognitionModel", "Image Recognition Model"),
        options=[],
        expand=True
    )

    # --- General Controls ---
    lang_dropdown = ft.Dropdown(
        label=i18n.get("settings_label_language"),
        options=[
            ft.dropdown.Option(key="en", text=i18n.get("settings_lang_en", "English")),
            ft.dropdown.Option(key="zh", text=i18n.get("settings_lang_zh", "中文")),
        ],
    )
    save_path_input = ft.TextField(label=i18n.get("settings_label_savePath"), expand=True)
    file_prefix_input = ft.TextField(label=i18n.get("settings_label_prefix"))
    
    max_history_input = ft.TextField(
        label=i18n.get("settings_label_max_history", "Max Prompt History"),
        value="20",
        keyboard_type=ft.KeyboardType.NUMBER
    )

    # --- Model Management Dialog ---
    def open_model_manager(e):
        model_list_view = ft.ListView(expand=True, spacing=10, height=400)
        
        # Input fields for adding/editing
        model_id_input = ft.TextField(label="Model ID", expand=True)
        model_series_dropdown = ft.Dropdown(
            label="Series",
            options=[
                ft.dropdown.Option("google-genai"),
                ft.dropdown.Option("openai")
            ],
            value="google-genai",
            width=150
        )
        
        tag_image_cb = ft.Checkbox(label="Image", value=False)
        tag_chat_cb = ft.Checkbox(label="Chat", value=True)
        is_paid_cb = ft.Checkbox(label="Paid Model", value=False)
        model_display_input = ft.TextField(label="Display Name", expand=True)
        
        # Track if we are editing
        editing_mode = {"active": False, "original_id": None, "original_series": None}

        def update_model_list():
            models = db.get_all_models()
            model_list_view.controls.clear()
            for model in models:
                icons = []
                if "Chat" in model["tags"]: icons.append(ft.Icon(ft.Icons.CHAT, size=16))
                if "Image" in model["tags"]: icons.append(ft.Icon(ft.Icons.IMAGE, size=16))
                
                paid_badge = ft.Container(
                    content=ft.Text("PAID", size=10, color="white", weight="bold"),
                    bgcolor="orange",
                    padding=ft.padding.symmetric(horizontal=4, vertical=2),
                    border_radius=4,
                    visible=model["is_paid"] == 1
                )
                
                model_list_view.controls.append(
                    ft.Row([
                        ft.Row(icons, spacing=4),
                        ft.Column([
                            ft.Row([ft.Text(model["display_name"], weight=ft.FontWeight.BOLD), paid_badge]),
                            ft.Text(f"{model['id']} ({model['series']})", size=12, color=ft.Colors.GREY_500),
                        ], expand=True, spacing=0),
                        ft.IconButton(
                            icon=ft.Icons.EDIT_OUTLINED,
                            icon_color=ft.Colors.BLUE_400,
                            on_click=lambda e, m=model: start_edit_model(m)
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_color=ft.Colors.RED_400,
                            on_click=lambda e, m=model["id"], s=model["series"]: remove_model(m, s)
                        )
                    ])
                )
            try:
                model_list_view.update()
            except:
                pass

        def start_edit_model(model):
            editing_mode["active"] = True
            editing_mode["original_id"] = model["id"]
            editing_mode["original_series"] = model["series"]
            
            model_id_input.value = model["id"]
            model_series_dropdown.value = model["series"]
            model_display_input.value = model["display_name"]
            tag_chat_cb.value = "Chat" in model["tags"]
            tag_image_cb.value = "Image" in model["tags"]
            is_paid_cb.value = model["is_paid"] == 1
            
            # Disable ID and Series during edit as they are Primary Keys
            model_id_input.disabled = True
            model_series_dropdown.disabled = True
            
            submit_btn.text = "Update Model"
            submit_btn.icon = ft.Icons.SAVE
            cancel_btn.visible = True
            
            model_id_input.update()
            model_series_dropdown.update()
            model_display_input.update()
            tag_chat_cb.update()
            tag_image_cb.update()
            is_paid_cb.update()
            submit_btn.update()
            cancel_btn.update()

        def reset_form(e=None):
            editing_mode["active"] = False
            editing_mode["original_id"] = None
            editing_mode["original_series"] = None
            
            model_id_input.value = ""
            model_id_input.disabled = False
            model_series_dropdown.value = "google-genai"
            model_series_dropdown.disabled = False
            model_display_input.value = ""
            tag_chat_cb.value = True
            tag_image_cb.value = False
            is_paid_cb.value = False
            
            submit_btn.text = "Add Model"
            submit_btn.icon = ft.Icons.ADD
            cancel_btn.visible = False
            
            model_id_input.update()
            model_series_dropdown.update()
            model_display_input.update()
            tag_chat_cb.update()
            tag_image_cb.update()
            is_paid_cb.update()
            submit_btn.update()
            cancel_btn.update()

        def submit_model(e):
            if model_id_input.value and model_display_input.value:
                tags = []
                if tag_chat_cb.value: tags.append("Chat")
                if tag_image_cb.value: tags.append("Image")
                
                db.save_model(
                    model_id_input.value,
                    model_series_dropdown.value,
                    ",".join(tags),
                    model_display_input.value,
                    1 if is_paid_cb.value else 0
                )
                
                reset_form()
                update_model_list()
                page.pubsub.send_all("models_updated")

        def remove_model(model_id, series):
            db.delete_model(model_id, series)
            update_model_list()
            page.pubsub.send_all("models_updated")

        submit_btn = ft.ElevatedButton("Add Model", icon=ft.Icons.ADD, on_click=submit_model, width=180)
        cancel_btn = ft.TextButton("Cancel Edit", on_click=reset_form, visible=False)

        update_model_list()

        dlg = ft.AlertDialog(
            title=ft.Text("Manage AI Models"),
            content=ft.Container(
                content=ft.Column([
                    ft.Row([model_id_input, model_display_input]),
                    ft.Row([model_series_dropdown, tag_chat_cb, tag_image_cb, is_paid_cb]),
                    ft.Row([submit_btn, cancel_btn], alignment=ft.MainAxisAlignment.START),
                    ft.Divider(),
                    model_list_view
                ], tight=True, spacing=10),
                width=700,
            ),
            actions=[
                ft.TextButton("Close", on_click=lambda _: page.pop_dialog()),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dlg)

    manage_models_btn = ft.ElevatedButton(
        "Manage All Models",
        icon=ft.Icons.SETTINGS_SUGGEST,
        on_click=open_model_manager
    )

    # --- Save Settings Logic ---
    def save_settings_handler(e):
        try:
            db.save_setting("api_key", google_paid_key_input.value or "")
            db.save_setting("refine_api_key", google_free_key_input.value or "")
            db.save_setting("google_use_paid_for_all", "1" if google_use_paid_checkbox.value else "0")
            
            db.save_setting("openai_api_key", openai_api_key_input.value or "")
            db.save_setting("openai_base_url", openai_base_url_input.value or "https://api.openai.com/v1")
            
            db.save_setting("refine_model_id", refine_model_dropdown.value or "")
            db.save_setting("recognition_model_id", recognition_model_dropdown.value or "")
            
            db.save_setting("save_path", save_path_input.value or "outputs")
            db.save_setting("file_prefix", file_prefix_input.value or "gemini_gen")
            db.save_setting("language", lang_dropdown.value or "en")
            db.save_setting("max_history_len", max_history_input.value or "20")
            
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

    async def pick_output_directory_btn_handler(e):
        if state.output_picker is None:
            state.output_picker = ft.FilePicker()
            page.overlay.append(state.output_picker)
            page.update()
        output_directory = await state.output_picker.get_directory_path()
        if output_directory:
            save_path_input.value = output_directory
            db.save_setting("save_path", output_directory)
            save_path_input.update()

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
        google_paid_key_input.value = settings.get("google_paid_api_key", "")
        google_free_key_input.value = settings.get("google_free_api_key", "")
        google_use_paid_checkbox.value = settings.get("google_use_paid_for_all", False)
        
        openai_api_key_input.value = settings.get("openai_api_key", "")
        openai_base_url_input.value = settings.get("openai_base_url", "https://api.openai.com/v1")
        
        # Load all chat models for dropdowns
        chat_models = db.get_models_by_tag("Chat")
        options = [ft.dropdown.Option(key=m["id"], text=f"{m['display_name']} ({m['series']})") for m in chat_models]
        
        refine_model_dropdown.options = options
        refine_model_dropdown.value = settings.get("refine_model_id", "")
        
        recognition_model_dropdown.options = options
        recognition_model_dropdown.value = settings.get("recognition_model_id", "")
        
        save_path_input.value = settings.get("save_path", "outputs")
        file_prefix_input.value = settings.get("file_prefix", "gemini_gen")
        lang_dropdown.value = settings.get("language", "en")
        max_history_input.value = settings.get("max_history_len", "20")
        page.update()

    def on_models_updated(topic: str):
        load_initial_settings()

    page.pubsub.subscribe(on_models_updated)
    threading.Timer(0.1, load_initial_settings).start()

    return ft.Container(
        content=ft.Column(
            [
                ft.Text(i18n.get("settings_title"), size=24, weight=ft.FontWeight.BOLD),
                lang_dropdown,
                ft.Divider(),
                
                # Google GenAI Section
                ft.Text("Google GenAI Config", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([google_paid_key_input]),
                ft.Row([google_free_key_input]),
                google_use_paid_checkbox,
                ft.Divider(),
                
                # OpenAI Section
                ft.Text("OpenAI API Config", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([openai_api_key_input]),
                openai_base_url_input,
                ft.Divider(),
                
                # Model Config Area
                ft.Text("Model Config Area", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([refine_model_dropdown]),
                ft.Row([recognition_model_dropdown]),
                manage_models_btn,
                ft.Divider(),
                
                # Output Settings
                ft.Text("Output Settings", size=18, weight=ft.FontWeight.BOLD),
                file_prefix_input,
                ft.Row([save_path_input, pick_output_directory_btn]),
                max_history_input,
                ft.Divider(),
                
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
