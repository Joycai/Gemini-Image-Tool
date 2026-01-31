import flet as ft
from common import i18n, database as db

def refine_manager_tab(page: ft.Page):
    def create_task_item(task_data, on_delete, on_update_order):
        task_id = task_data["id"]
        name = task_data["name"]
        name_zh = task_data["name_zh"]
        instruction = task_data["system_instruction"]

        display_name = ft.Text(value=f"{name} / {name_zh}", size=16, weight=ft.FontWeight.BOLD)
        display_instruction = ft.Text(
            value=instruction, 
            italic=True, 
            color=ft.Colors.GREY_700,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS
        )

        edit_name = ft.TextField(label=i18n.get("refine_manager_label_name_en", "Name (EN)"), value=name, expand=True)
        edit_name_zh = ft.TextField(label=i18n.get("refine_manager_label_name_zh", "Name (ZH)"), value=name_zh, expand=True)
        edit_instruction = ft.TextField(
            label=i18n.get("refine_manager_label_instruction", "System Instruction"),
            value=instruction, 
            multiline=True, 
            min_lines=5, 
            max_lines=15, 
            expand=True
        )

        def show_display_view(e):
            edit_view.visible = False
            display_view.visible = True
            card.update()

        def show_edit_view(e):
            display_view.visible = False
            edit_view.visible = True
            card.update()

        def save_changes(e):
            nonlocal name, name_zh, instruction
            new_name = edit_name.value
            new_name_zh = edit_name_zh.value
            new_instruction = edit_instruction.value

            if not new_name or not new_instruction:
                return

            db.update_refine_task(task_id, new_name, new_name_zh, new_instruction)
            
            name, name_zh, instruction = new_name, new_name_zh, new_instruction
            display_name.value = f"{name} / {name_zh}"
            display_instruction.value = instruction
            
            show_display_view(e)
            page.pubsub.send_all("refine_tasks_updated")

        def move_up(e):
            idx = task_list.controls.index(card)
            if idx > 0:
                task_list.controls.insert(idx - 1, task_list.controls.pop(idx))
                update_order()

        def move_down(e):
            idx = task_list.controls.index(card)
            if idx < len(task_list.controls) - 1:
                task_list.controls.insert(idx + 1, task_list.controls.pop(idx))
                update_order()

        display_view = ft.ListTile(
            leading=ft.Icon(ft.Icons.AUTO_FIX_HIGH, color=ft.Colors.AMBER_600),
            title=display_name,
            subtitle=display_instruction,
            on_click=show_edit_view,
            trailing=ft.Row([
                ft.IconButton(ft.Icons.ARROW_UPWARD, icon_size=20, on_click=move_up, tooltip=i18n.get("prompt_manager_move_up")),
                ft.IconButton(ft.Icons.ARROW_DOWNWARD, icon_size=20, on_click=move_down, tooltip=i18n.get("prompt_manager_move_down")),
                ft.IconButton(ft.Icons.EDIT, icon_size=20, on_click=show_edit_view, tooltip=i18n.get("prompt_manager_edit")),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=20, icon_color=ft.Colors.RED_400, on_click=lambda _: on_delete(task_id, card), tooltip=i18n.get("prompt_manager_delete")),
            ], tight=True)
        )

        edit_view = ft.Container(
            padding=15,
            visible=False,
            content=ft.Column([
                ft.Row([edit_name, edit_name_zh]),
                edit_instruction,
                ft.Row([
                    ft.ElevatedButton(i18n.get("prompt_manager_save"), icon=ft.Icons.SAVE, on_click=save_changes),
                    ft.TextButton(i18n.get("prompt_manager_cancel"), icon=ft.Icons.CANCEL, on_click=show_display_view),
                ], alignment=ft.MainAxisAlignment.END)
            ])
        )

        card = ft.Card(content=ft.Column([display_view, edit_view], tight=True))
        card.task_id = task_id
        return card

    def load_tasks():
        tasks = db.get_all_refine_tasks()
        task_list.controls.clear()
        for t in tasks:
            task_list.controls.append(create_task_item(t, delete_task, update_order))
        
        try:
            if task_list.page:
                task_list.update()
        except:
            pass

    def add_task(e):
        name = new_name_field.value
        name_zh = new_name_zh_field.value
        instruction = new_instruction_field.value
        if name and instruction:
            task_id = name.lower().replace(" ", "_")
            db.save_refine_task(task_id, name, name_zh, instruction)
            new_name_field.value = ""
            new_name_zh_field.value = ""
            new_instruction_field.value = ""
            load_tasks()
            page.pubsub.send_all("refine_tasks_updated")

    def delete_task(task_id, control):
        db.delete_refine_task(task_id)
        task_list.controls.remove(control)
        task_list.update()
        page.pubsub.send_all("refine_tasks_updated")

    def update_order():
        ids = [c.task_id for c in task_list.controls]
        db.update_refine_task_order(ids)
        page.pubsub.send_all("refine_tasks_updated")

    task_list = ft.ListView(expand=True, spacing=10)
    new_name_field = ft.TextField(label=i18n.get("refine_manager_label_name_en", "Name (EN)"), expand=True)
    new_name_zh_field = ft.TextField(label=i18n.get("refine_manager_label_name_zh", "Name (ZH)"), expand=True)
    new_instruction_field = ft.TextField(label=i18n.get("refine_manager_label_instruction", "System Instruction"), multiline=True, min_lines=3, expand=True)

    view = ft.Column([
        ft.Card(ft.Container(padding=20, content=ft.Column([
            ft.Text(i18n.get("refine_manager_add_title", "Add New Refine Task"), size=18, weight=ft.FontWeight.BOLD),
            ft.Row([new_name_field, new_name_zh_field]),
            new_instruction_field,
            ft.ElevatedButton(i18n.get("refine_manager_btn_add", "Add Task"), icon=ft.Icons.ADD, on_click=add_task)
        ]))),
        ft.Divider(),
        ft.Text(i18n.get("refine_manager_existing_title", "Existing Refine Tasks"), size=18, weight=ft.FontWeight.BOLD),
        task_list
    ], expand=True, scroll=ft.ScrollMode.AUTO)

    load_tasks()
    return view
