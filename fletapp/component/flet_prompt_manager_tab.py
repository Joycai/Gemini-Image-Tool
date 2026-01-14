import flet as ft
from flet import FontWeight, TextThemeStyle

from common import i18n, database as db


def prompt_manager_tab(page: ft.Page):
    def create_prompt_item(prompt_data, on_delete_prompt, on_update_order):
        """
        Creates the controls for a single prompt item wrapped in a Card.
        """
        prompt_title = prompt_data["title"]
        prompt_content = prompt_data["content"]

        # --- Controls for the item ---
        display_title = ft.Text(value=prompt_title, size=16, weight=FontWeight.BOLD)
        display_content = ft.Text(
            value=prompt_content, 
            italic=True, 
            color=ft.Colors.GREY_700,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS
        )

        edit_title_field = ft.TextField(label=i18n.get("home_control_prompt_save_label"), value=prompt_title, expand=True)
        edit_content_field = ft.TextField(
            label=i18n.get("home_control_prompt_input_placeholder"),
            value=prompt_content, 
            multiline=True, 
            min_lines=3, 
            max_lines=10, 
            expand=True
        )

        def move_to_top(e):
            idx = prompt_list.controls.index(card)
            if idx > 0:
                prompt_list.controls.insert(0, prompt_list.controls.pop(idx))
                on_update_order()
                prompt_list.update()

        def move_to_bottom(e):
            idx = prompt_list.controls.index(card)
            if idx < len(prompt_list.controls) - 1:
                prompt_list.controls.append(prompt_list.controls.pop(idx))
                on_update_order()
                prompt_list.update()

        def move_up(e):
            idx = prompt_list.controls.index(card)
            if idx > 0:
                prompt_list.controls.insert(idx - 1, prompt_list.controls.pop(idx))
                on_update_order()
                prompt_list.update()

        def move_down(e):
            idx = prompt_list.controls.index(card)
            if idx < len(prompt_list.controls) - 1:
                prompt_list.controls.insert(idx + 1, prompt_list.controls.pop(idx))
                on_update_order()
                prompt_list.update()

        def show_display_view(e):
            edit_view.visible = False
            display_view.visible = True
            card.update()

        def show_edit_view(e):
            display_view.visible = False
            edit_view.visible = True
            card.update()

        def save_changes(e):
            nonlocal prompt_title, prompt_content
            new_title = edit_title_field.value
            new_content = edit_content_field.value

            if not new_title or not new_content:
                return

            db.update_prompt(prompt_title, new_title, new_content)
            
            # Update the property used for ordering
            card.prompt_title = new_title
            
            page.pubsub.send_all("prompts_updated")

            # Update local state and UI
            prompt_title = new_title
            prompt_content = new_content
            display_title.value = new_title
            display_content.value = new_content

            show_display_view(e)

        def delete_item(e):
            on_delete_prompt(prompt_title, card)

        # Display View using ListTile for a clean card look
        display_view = ft.ListTile(
            leading=ft.Icon(ft.Icons.NOTES, color=ft.Colors.BLUE_400),
            title=display_title,
            subtitle=display_content,
            on_click=show_edit_view,
            trailing=ft.Row(
                [
                    ft.IconButton(
                        icon=ft.Icons.VERTICAL_ALIGN_TOP, 
                        icon_size=20,
                        tooltip=i18n.get("prompt_manager_move_top", "Move to Top"),
                        on_click=move_to_top
                    ),
                    ft.IconButton(
                        icon=ft.Icons.ARROW_UPWARD, 
                        icon_size=20,
                        tooltip=i18n.get("prompt_manager_move_up"),
                        on_click=move_up
                    ),
                    ft.IconButton(
                        icon=ft.Icons.ARROW_DOWNWARD, 
                        icon_size=20,
                        tooltip=i18n.get("prompt_manager_move_down"),
                        on_click=move_down
                    ),
                    ft.IconButton(
                        icon=ft.Icons.VERTICAL_ALIGN_BOTTOM, 
                        icon_size=20,
                        tooltip=i18n.get("prompt_manager_move_bottom", "Move to Bottom"),
                        on_click=move_to_bottom
                    ),
                    ft.IconButton(
                        icon=ft.Icons.EDIT, 
                        icon_size=20,
                        tooltip=i18n.get("prompt_manager_edit"),
                        on_click=show_edit_view
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE, 
                        icon_size=20,
                        icon_color=ft.Colors.RED_400,
                        tooltip=i18n.get("prompt_manager_delete"),
                        on_click=delete_item
                    ),
                ],
                tight=True,
                spacing=0,
            ),
        )

        edit_view = ft.Container(
            padding=15,
            visible=False,
            content=ft.Column([
                edit_title_field,
                edit_content_field,
                ft.Row([
                    ft.ElevatedButton(
                        content=ft.Text(i18n.get("prompt_manager_save")), 
                        icon=ft.Icons.SAVE, 
                        on_click=save_changes,
                        style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ft.Colors.BLUE_600)
                    ),
                    ft.TextButton(
                        i18n.get("prompt_manager_cancel"), 
                        icon=ft.Icons.CANCEL, 
                        on_click=show_display_view
                    ),
                ], alignment=ft.MainAxisAlignment.END)
            ], spacing=10)
        )

        card = ft.Card(
            content=ft.Container(
                content=ft.Column([display_view, edit_view], tight=True),
                padding=ft.padding.symmetric(vertical=5),
            ),
            elevation=2,
        )
        
        # Add a property to the control to easily retrieve the title for ordering
        card.prompt_title = prompt_title
        return card

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
            load_all_prompts()

    def delete_prompt(title_to_delete, item_control):
        db.delete_prompt(title_to_delete)
        page.pubsub.send_all("prompts_updated")
        prompt_list.controls.remove(item_control)
        prompt_list.update()

    def update_prompt_order():
        titles = [item.prompt_title for item in prompt_list.controls]
        db.update_prompt_order(titles)
        page.pubsub.send_all("prompts_updated")

    # --- Main UI Components for the Tab ---
    prompt_list = ft.ListView(expand=True, spacing=5, padding=10)
    
    new_prompt_title_field = ft.TextField(
        label=i18n.get("prompt_manager_new_prompt_title_label", "New Prompt Title"),
        border_radius=10,
    )
    new_prompt_content_field = ft.TextField(
        label=i18n.get("prompt_manager_new_prompt_content_label", "New Prompt Content"), 
        multiline=True, 
        min_lines=3,
        max_lines=5, 
        border_radius=10,
    )
    
    add_prompt_card = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Text(i18n.get("prompt_manager_add_new_title", "Add New Prompt"), weight=ft.FontWeight.BOLD, size=18),
                new_prompt_title_field,
                new_prompt_content_field,
                ft.Row([
                    ft.ElevatedButton(
                        content=ft.Text(i18n.get("prompt_manager_add_button", "Add Prompt")),
                        icon=ft.Icons.ADD,
                        on_click=add_new_prompt,
                        style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ft.Colors.GREEN_700)
                    )
                ], alignment=ft.MainAxisAlignment.END)
            ], spacing=15),
            padding=20,
        )
    )

    view = ft.Column(
        controls=[
            add_prompt_card,
            ft.Divider(height=30, thickness=1),
            ft.Row([
                ft.Icon(ft.Icons.LIST_ALT, color=ft.Colors.BLUE_GREY_400),
                ft.Text(
                    i18n.get("prompt_manager_existing_prompts_title", "Existing Prompts"),
                    theme_style=TextThemeStyle.HEADLINE_SMALL,
                    weight=ft.FontWeight.BOLD
                ),
            ], alignment=ft.MainAxisAlignment.START),
            prompt_list,
        ],
        expand=True,
    )

    def init_view():
        load_all_prompts()

    return {
        "view": view,
        "init": init_view,
    }
