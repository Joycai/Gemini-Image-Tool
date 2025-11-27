import flet as ft
from PIL.ImageOps import expand

import i18n
import database as db
import flet_app_logic # Import the new app logic module
import logger_utils # For initial log setup
import sys # Import the sys module
import os # Import the os module
from component.flet_single_edit_tab import single_edit_tab


# Removed custom component imports:
# from component.flet_single_image_editor_page import FletSingleImageEditorPage
# from component.flet_main_page import FletMainPage
# from component.flet_chat_page import FletChatPage
# from component.flet_history_page import FletHistoryPage
# from component.flet_settings_page import FletSettingsPage

def main(page: ft.Page):
    # Removed: flet_app_logic.set_flet_page_ref(page)

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

    # --- End Single Image Editor Page Controls and Handlers ---

    # Main content area with Tabs
    main_tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
            ft.Tab(
                text="单图编辑", # Changed tab text
                content=single_edit_tab(page),
            ),
            ft.Tab(
                text=i18n.get("app_tab_chat"),
                content=ft.Text("Chat Page Content")
            ),
            ft.Tab(
                text=i18n.get("app_tab_history"),
                content=ft.Text("History Page Content")
            ),
            ft.Tab(
                text=i18n.get("app_tab_settings"),
                content=ft.Text("Settings Page Content")
            ),
        ],
        expand=1
    )

    page.add(main_tabs)

    # Removed: Initial App Data Load
    # Removed: Apply initial data to UI components
    # Removed: Update all components after initial data load
    # Removed: Start periodic UI updates
    # Removed: Connect FletMainPage and FletChatPage to app_logic functions


if __name__ == "__main__":
    # Ensure necessary directories exist (assuming flet_app_logic still defines these)
    # These lines are commented out as flet_app_logic is not fully integrated yet.
    # os.makedirs(flet_app_logic.UPLOAD_DIR, exist_ok=True)
    # os.makedirs(flet_app_logic.OUTPUT_DIR, exist_ok=True)
    # os.makedirs(flet_app
    ft.app(target=main)