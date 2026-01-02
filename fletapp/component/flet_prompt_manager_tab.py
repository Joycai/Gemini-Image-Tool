import flet as ft
from flet import FontWeight, TextThemeStyle

from common import i18n, database as db


def prompt_manager_tab(page: ft.Page):
    def create_prompt_item(prompt_data, on_delete_prompt, on_update_order):
        """
        Creates the controls for a single prompt item.
        This is a functional approach, not a class-based one.
        """
        prompt_title = prompt_data["title"]
        prompt_content = prompt_data["content"]

        # --- Controls for the item ---
        display_title = ft.Text(value=prompt_title, size=16, weight=FontWeight.BOLD)
        display_content = ft.Text(value=prompt_content, italic=True)

        edit_title_field = ft.TextField(value=prompt_title, expand=True)
        edit_content_field = ft.TextField(value=prompt_content, multiline=True, min_lines=3, max_lines=5, expand=True)

        def move_up(e):
            idx = prompt_list.controls.index(item_column)
            if idx > 0:
                prompt_list.controls.insert(idx - 1, prompt_list.controls.pop(idx))
                on_update_order()

        def move_down(e):
            idx = prompt_list.controls.index(item_column)
            if idx < len(prompt_list.controls) - 1:
                prompt_list.controls.insert(idx + 1, prompt_list.controls.pop(idx))
                on_update_order()

        def show_display_view(e):
            edit_view.visible = False
            display_view.visible = True
            item_column.update()

        def show_edit_view(e):
            display_view.visible = False
            edit_view.visible = True
            item_column.update()

        def save_changes(e):
            nonlocal prompt_title, prompt_content
            new_title = edit_title_field.value
            new_content = edit_content_field.value

            db.update_prompt(prompt_title, new_title, new_content)
            page.pubsub.send_all("prompts_updated")

            # Update local state and UI
            prompt_title = new_title
            prompt_content = new_content
            display_title.value = new_title
            display_content.value = new_content

            show_display_view(e)

        def delete_item(e):
            on_delete_prompt(prompt_title, item_column)

        display_view = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Column([display_title, display_content], expand=True),
                ft.Row(
                    spacing=0,
                    controls=[
                        ft.IconButton(ft.Icons.ARROW_UPWARD, on_click=move_up,
                                      tooltip=i18n.get("prompt_manager_move_up")),
                        ft.IconButton(ft.Icons.ARROW_DOWNWARD, on_click=move_down,
                                      tooltip=i18n.get("prompt_manager_move_down")),
                        ft.IconButton(ft.Icons.EDIT, on_click=show_edit_view, tooltip=i18n.get("prompt_manager_edit")),
                        ft.IconButton(ft.Icons.DELETE, on_click=delete_item, tooltip=i18n.get("prompt_manager_delete")),
                    ],
                ),
            ],
        )

        edit_view = ft.Container(
            padding=10,
            bgcolor="surfaceVariant",
            visible=False,
            content=ft.Column([
                edit_title_field,
                edit_content_field,
                ft.Row([
                    ft.Button(content=i18n.get("prompt_manager_save"), icon=ft.Icons.SAVE, on_click=save_changes),
                    ft.TextButton(i18n.get("prompt_manager_cancel"), icon=ft.Icons.CANCEL, on_click=show_display_view),
                ])
            ])
        )

        item_column = ft.Column(controls=[display_view, edit_view])
        # Add a property to the control to easily retrieve the title for ordering
        item_column.prompt_title = prompt_title
        return item_column

    def load_all_prompts():
        prompts = db.get_all_prompts()
        prompt_list.controls.clear()
        for p in prompts:
            prompt_list.controls.append(
                create_prompt_item(
                    prompt_data=p,
                    on_delete_prompt=delete_prompt,
                    on_update_order=update_prompt_order,
                )
            )
        prompt_list.update()

    def add_new_prompt(e):
        title = new_prompt_title_field.value
        content = new_prompt_content_field.value
        if title and content:
            db.save_prompt(title, content)
            page.pubsub.send_all("prompts_updated")
            new_prompt_title_field.value = ""
            new_prompt_content_field.value = ""
            new_prompt_title_field.update()
            new_prompt_content_field.update()
            load_all_prompts()  # Reload the whole list

    def delete_prompt(title_to_delete, item_control):
        db.delete_prompt(title_to_delete)
        page.pubsub.send_all("prompts_updated")
        prompt_list.controls.remove(item_control)
        prompt_list.update()

    def update_prompt_order():
        # Retrieve the title from the custom property we added
        titles = [item.prompt_title for item in prompt_list.controls]
        db.update_prompt_order(titles)
        page.pubsub.send_all("prompts_updated")
        # No need to update UI here, it's already visually changed

    # --- Main UI Components for the Tab ---
    prompt_list = ft.ListView(expand=True, spacing=10)
    new_prompt_title_field = ft.TextField(label=i18n.get("prompt_manager_new_prompt_title_label", "New Prompt Title"),
                                          expand=True)
    new_prompt_content_field = ft.TextField(
        label=i18n.get("prompt_manager_new_prompt_content_label", "New Prompt Content"), multiline=True, min_lines=3,
        max_lines=5, expand=True)
    add_prompt_button = ft.Button(
        content=i18n.get("prompt_manager_add_button", "Add Prompt"),
        icon=ft.Icons.ADD,
        on_click=add_new_prompt,
    )

    view = ft.Column(
        controls=[
            ft.Text(
                i18n.get("prompt_manager_add_new_title", "Add New Prompt"),
                theme_style=TextThemeStyle.HEADLINE_SMALL),
            new_prompt_title_field,
            new_prompt_content_field,
            ft.Row([add_prompt_button], alignment=ft.MainAxisAlignment.END),
            ft.Divider(),
            ft.Text(
                i18n.get("prompt_manager_existing_prompts_title", "Existing Prompts"),
                theme_style=TextThemeStyle.HEADLINE_SMALL),
            prompt_list,
        ],
        expand=True,
        scroll=ft.ScrollMode.AUTO
    )

    def init_view():
        load_all_prompts()

    return {
        "view": view,
        "init": init_view,
    }
