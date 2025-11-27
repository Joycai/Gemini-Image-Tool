import flet as ft
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from common import i18n
from fletapp.component.flet_single_edit_tab import single_edit_tab
from fletapp.component.flet_settings_page import settings_page


def main(page: ft.Page):
    # i18n is automatically initialized when the module is imported.
    # We may need to explicitly reload it if the language changes in the settings page.
    i18n.load_language()

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

    # Main content area with Tabs
    main_tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
            ft.Tab(
                text=i18n.get("app_tab_single_edit", "Single Edit"),
                content=single_edit_tab(page)
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
                content=settings_page(page) # Replaced placeholder
            ),
        ],
        expand=1
    )

    page.add(main_tabs)


if __name__ == "__main__":
    ft.app(target=main)