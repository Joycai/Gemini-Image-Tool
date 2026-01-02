import flet as ft
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from common import i18n, database as db
from fletapp.component.flet_single_edit_tab import single_edit_tab
from fletapp.component.flet_settings_page import settings_page
from fletapp.component.flet_history_page import history_page
from fletapp.component.flet_chat_page import chat_page
from fletapp.component.flet_prompt_manager_tab import prompt_manager_tab


def main(page: ft.Page):
    i18n.load_language()

    page.title = i18n.get("app_title")
    page.vertical_alignment = ft.MainAxisAlignment.START

    # --- Theme Loading ---
    saved_theme = db.get_setting("theme_mode", "LIGHT")
    page.theme_mode = ft.ThemeMode.DARK if saved_theme == "DARK" else ft.ThemeMode.LIGHT

    def restart_app():
        """Restarts the current application."""
        page.window_destroy()
        os.execl(sys.executable, sys.executable, *sys.argv)

    def toggle_theme(e):
        new_theme_mode = ft.ThemeMode.DARK if page.theme_mode == ft.ThemeMode.LIGHT else ft.ThemeMode.LIGHT
        page.theme_mode = new_theme_mode
        db.save_setting("theme_mode", "DARK" if new_theme_mode == ft.ThemeMode.DARK else "LIGHT")
        theme_toggle_button.icon = ft.Icons.WB_SUNNY_OUTLINED if page.theme_mode == ft.ThemeMode.DARK else ft.Icons.DARK_MODE_OUTLINED
        page.update()

    theme_toggle_button = ft.IconButton(
        icon=ft.Icons.WB_SUNNY_OUTLINED if page.theme_mode == ft.ThemeMode.DARK else ft.Icons.DARK_MODE_OUTLINED,
        tooltip=i18n.get("header_theme_button_tooltip", "Toggle theme"),
        on_click=toggle_theme
    )

    page.appbar = ft.AppBar(
        title=ft.Text(i18n.get("app_title")),
        center_title=False,
        actions=[theme_toggle_button]
    )

    # --- Component Creation ---
    single_edit_component = single_edit_tab(page)
    # chat_component = chat_page(page)
    # prompt_manager_component = prompt_manager_tab(page)
    
    main_tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        length=3,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(
                            label=i18n.get("app_tab_single_edit", "Single Edit"),
                        ),
                        # ft.Tab(
                        #     label=i18n.get("app_tab_chat"),
                        # ),
                        # ft.Tab(
                        #     label=i18n.get("app_tab_prompt_manager", "Prompt Manager"),
                        # ),
                        ft.Tab(
                            label=i18n.get("app_tab_history"),
                        ),
                        ft.Tab(
                            label=i18n.get("app_tab_settings"),
                        ),
                    ]
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[
                        single_edit_component["view"],
                        # chat_component["view"],
                        # prompt_manager_component["view"],
                        history_page(page),
                        settings_page(page, on_restart=restart_app)
                    ]
                )
            ]
        ),
        expand=1
    )

    page.add(main_tabs)

    # --- Deferred Initialization ---
    single_edit_component["init"]()
    # chat_component["init"]()
    # prompt_manager_component["init"]()

if __name__ == "__main__":
    os.environ["PYTHONUTF8"] = "1"
    ft.run(main)
