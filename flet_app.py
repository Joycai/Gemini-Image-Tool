import flet as ft
import i18n
import database as db
import flet_app_logic # Import the new app logic module
import logger_utils # For initial log setup
import sys # Import the sys module
import os # Import the os module

from component.flet_main_page import FletMainPage
from component.flet_chat_page import FletChatPage
from component.flet_history_page import FletHistoryPage
from component.flet_settings_page import FletSettingsPage

def main(page: ft.Page):
    # Set page reference in app_logic for UI updates from background threads
    flet_app_logic.set_flet_page_ref(page)

    page.title = i18n.get("app_title")
    page.vertical_alignment = ft.MainAxisAlignment.START

    # Header equivalent
    page.appbar = ft.AppBar(
        title=ft.Text(i18n.get("app_title")),
        center_title=False,
        actions=[
            ft.IconButton(
                icon=ft.Icons.COLOR_LENS,
                tooltip=i18n.get("header_theme_button_tooltip", "Toggle theme"),
                on_click=lambda e: print("Theme button clicked") # Placeholder for theme toggle logic
            )
        ]
    )

    # Instantiate page components, passing the page object
    main_page_instance = FletMainPage(page=page)
    chat_page_instance = FletChatPage(page=page)
    history_page_instance = FletHistoryPage(page=page)
    settings_page_instance = FletSettingsPage(page=page)

    # Set page component references in app_logic
    flet_app_logic.set_main_page_ref(main_page_instance)
    flet_app_logic.set_chat_page_ref(chat_page_instance)
    # History and Settings pages don't directly receive updates from background tasks in app_logic,
    # but they might trigger actions that app_logic handles.

    # Main content area with Tabs
    main_tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
            ft.Tab(
                text=i18n.get("app_tab_home"),
                content=main_page_instance
            ),
            ft.Tab(
                text=i18n.get("app_tab_chat"),
                content=chat_page_instance
            ),
            ft.Tab(
                text=i18n.get("app_tab_history"),
                content=history_page_instance
            ),
            ft.Tab(
                text=i18n.get("app_tab_settings"),
                content=settings_page_instance
            ),
        ],
        expand=1
    )

    page.add(main_tabs)

    # --- Initial App Data Load ---
    (
        initial_main_dir, initial_api_key, initial_genai_client,
        initial_download_btn_props, _, initial_save_path,
        initial_file_prefix, initial_language, _
    ) = flet_app_logic.init_app_data()

    # Apply initial data to UI components
    main_page_instance.assets_block.dir_input.value = initial_main_dir
    main_page_instance.btn_download.text = initial_download_btn_props["label"]
    main_page_instance.btn_download.disabled = not initial_download_btn_props["interactive"]
    # main_page_instance.result_image.src = ... (if there was a restored image, it would be set here)

    settings_page_instance.api_key_input.value = initial_api_key
    settings_page_instance.save_path_input.value = initial_save_path
    settings_page_instance.file_prefix_input.value = initial_file_prefix
    settings_page_instance.language_dropdown.value = initial_language

    # Update all components after initial data load
    main_page_instance.update()
    chat_page_instance.update()
    history_page_instance.update()
    settings_page_instance.update()

    # Start periodic UI updates using page.run_task
    page.run_task(flet_app_logic.poll_flet_ui_updates) # Changed to page.run_task

    # Initial load for assets and history
    main_page_instance.assets_block.refresh_images()
    history_page_instance.refresh_history_handler(None) # Pass None as event argument

    # --- Connect FletMainPage and FletChatPage to app_logic functions ---
    main_page_instance.btn_send.on_click = lambda e: flet_app_logic.start_generation_task(
        main_page_instance.prompt_input.value,
        main_page_instance.state_selected_images,
        settings_page_instance.api_key_input.value, # Use current API key from settings
        main_page_instance.model_selector.value,
        main_page_instance.ar_selector.value,
        main_page_instance.res_selector.value
    )
    main_page_instance.btn_retry.on_click = main_page_instance.btn_send.on_click # Retry uses same logic

    chat_page_instance.chat_send_button.on_click = lambda e: flet_app_logic.start_chat_task(
        chat_page_instance.state_chat_input_buffer,
        initial_genai_client, # Use the initially created client, or update dynamically
        chat_page_instance.state_chat_session,
        chat_page_instance.chat_model_selector.value,
        chat_page_instance.chat_ar_selector.value,
        chat_page_instance.chat_res_selector.value
    )
    chat_page_instance.chat_input_field.on_submit = chat_page_instance.chat_send_button.on_click

    # Connect settings save to update client
    settings_page_instance.btn_save_settings.on_click = lambda e: (
        settings_page_instance.save_settings_handler(e),
        # Update genai_client after settings are saved
        flet_app_logic.create_genai_client(settings_page_instance.api_key_input.value)
    )
    settings_page_instance.btn_restart.on_click = lambda e: flet_app_logic.restart_app()


if __name__ == "__main__":
    # ================= 🚑 PyInstaller noconsole 修复补丁 =================
    # 当使用 --noconsole 打包时，sys.stdout 和 sys.stderr 是 None
    # 这会导致 uvicorn 日志初始化失败。我们需要给它一个假的流对象。
    class NullWriter:
        def write(self, data): pass
        def flush(self): pass
        def isatty(self): return False
        def fileno(self): return -1

    if sys.stdout is None:
        sys.stdout = NullWriter()
    if sys.stderr is None:
        sys.stderr = NullWriter()
    # =====================================================================

    # Ensure necessary directories exist
    os.makedirs(flet_app_logic.UPLOAD_DIR, exist_ok=True)
    os.makedirs(flet_app_logic.OUTPUT_DIR, exist_ok=True)
    os.makedirs(flet_app_logic.TEMP_DIR, exist_ok=True) # Ensure TEMP_DIR exists for exports

    ft.app(target=main)
