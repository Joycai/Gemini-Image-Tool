import flet as ft
from common import database as db, i18n

def prompt_history_page(page: ft.Page, on_prompt_select: callable = None):
    
    def load_history():
        history = db.get_prompt_history()
        history_list.controls.clear()
        for content in history:
            history_list.controls.append(
                ft.ListTile(
                    title=ft.Text(content, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    on_click=lambda e, c=content: select_prompt(c),
                    trailing=ft.IconButton(
                        icon=ft.Icons.COPY,
                        on_click=lambda e, c=content: copy_to_clipboard(c),
                        tooltip=i18n.get("prompt_history_copy_tooltip", "Copy to clipboard")
                    )
                )
            )
        page.update()

    def select_prompt(content):
        if on_prompt_select:
            on_prompt_select(content)
            # Optionally switch to the single edit tab
            # page.pubsub.send_all("switch_tab", 0) 
        else:
            # If no callback, just copy to clipboard as fallback
            page.set_clipboard(content)
            page.show_snack_bar(ft.SnackBar(ft.Text(i18n.get("prompt_history_copied", "Prompt copied to clipboard"))))

    def copy_to_clipboard(content):
        page.set_clipboard(content)
        page.show_snack_bar(ft.SnackBar(ft.Text(i18n.get("prompt_history_copied", "Prompt copied to clipboard"))))

    def clear_history(e):
        # We need a way to clear history in database.py if we want this
        # For now, let's just refresh
        load_history()

    history_list = ft.ListView(expand=True, spacing=10)
    
    view = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.HISTORY, size=30, color=ft.Colors.BLUE_400),
                ft.Text(i18n.get("app_tab_prompt_history", "Prompt History"), size=20, weight=ft.FontWeight.BOLD),
                ft.IconButton(ft.Icons.REFRESH, on_click=lambda _: load_history())
            ], alignment=ft.MainAxisAlignment.START),
            ft.Divider(),
            history_list
        ], expand=True),
        padding=20,
        expand=True
    )

    # Initial load
    load_history()

    return view
