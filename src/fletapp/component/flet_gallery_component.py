import os
import json
import asyncio
from dataclasses import dataclass, field
from typing import Union, Callable, List, Set, Dict

import flet as ft
from flet import Container, BoxFit, Alignment, Page

from common import database as db, i18n
from common.config import VALID_IMAGE_EXTENSIONS
from common.prompts import AI_RECOGNIZE_TASKS
from fletapp.component.common_component import show_snackbar
from fletapp.component.flet_image_preview_dialog import PreviewDialogData, preview_dialog
from geminiapi import api_client


@dataclass
class State:
    file_picker: ft.FilePicker | None = None
    current_directory: str | None = None
    selected_paths: Set[str] = field(default_factory=set)
    expanded_paths: Set[str] = field(default_factory=set)
    row_count: int = 2


state = State()


def local_gallery_component(page: Page, expand: Union[None, bool, int],
                            on_image_select: Callable[[str], None] = None) -> Container:
    
    # --- UI Controls ---
    selected_directory_text = ft.Text(
        value=i18n.get("home_assets_info_ready", "Ready."),
        size=12,
        italic=True,
        color=ft.Colors.BLUE_GREY_400,
        overflow=ft.TextOverflow.ELLIPSIS,
        expand=True,
    )

    image_gallery = ft.GridView(
        runs_count=state.row_count,
        spacing=10,
        run_spacing=10,
        child_aspect_ratio=0.87,
        padding=0,
        controls=[],
        expand=True
    )

    directory_tree_column = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, height=250)

    # --- Functions ---

    def save_gallery_state():
        """Persists the current gallery state to the database."""
        db.save_setting("gallery_row_count", str(state.row_count))
        db.save_setting("gallery_selected_paths", json.dumps(list(state.selected_paths)))
        db.save_setting("gallery_expanded_paths", json.dumps(list(state.expanded_paths)))

    def open_image_preview(e, image_path):
        page.show_dialog(preview_dialog(page, PreviewDialogData(
            image_list=[image_path],
            current_index=0,
        ), None, True))

    def update_grid_layout(e: ft.Event[ft.Slider]):
        columns = int(e.control.value)
        state.row_count = columns
        image_gallery.runs_count = columns
        save_gallery_state()
        image_gallery.update()

    zoom_slider = ft.Slider(
        min=1,
        max=5,
        divisions=4,
        value=state.row_count,
        label="{value}",
        on_change=update_grid_layout,
        height=30,
    )

    def delete_image(image_path):
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
                load_images_from_selected_directories()
                show_snackbar(page, i18n.get("logic_info_deleteSuccess", "Image Deleted"))
        except Exception as ex:
            show_snackbar(page, f"Error: {ex}", is_error=True)

    def _show_ai_recognize_dialog(image_path: str):
        # Load last prompt from DB
        last_prompt = db.get_setting("last_ai_recognize_prompt", AI_RECOGNIZE_TASKS["recognize"]["prompt"])
        
        prompt_input = ft.TextField(
            label="Custom Task / Prompt",
            value=last_prompt,
            multiline=True,
            min_lines=3,
            max_lines=5,
            expand=True
        )
        
        response_text = ft.Markdown(
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            code_theme=ft.MarkdownCodeTheme.GOOGLE_CODE,
        )
        
        progress_ring = ft.ProgressRing(visible=False)
        
        def on_task_change(e):
            if e.control.value in AI_RECOGNIZE_TASKS:
                prompt_input.value = AI_RECOGNIZE_TASKS[e.control.value]["prompt"]
            prompt_input.update()

        task_dropdown = ft.Dropdown(
            label="Pre-defined Tasks",
            options=[
                *[ft.dropdown.Option(key=k, text=v["name"]) for k, v in AI_RECOGNIZE_TASKS.items()],
                ft.dropdown.Option(key="custom", text="Custom Task"),
            ],
            value="custom"
        )
        task_dropdown.on_change = on_task_change

        async def run_ai_task(e):
            settings = db.get_all_settings()
            api_key = settings.get("api_key")
            model_id = settings.get("refine_model_id", "gemini-2.0-flash")
            
            if not api_key:
                show_snackbar(page, i18n.get("api_error_apiKey"), is_error=True)
                return

            # Save prompt to DB
            db.save_setting("last_ai_recognize_prompt", prompt_input.value)
            
            run_button.disabled = True
            progress_ring.visible = True
            response_text.value = "Processing..."
            page.update()

            try:
                result = await asyncio.to_thread(
                    api_client.ai_recognize_image,
                    image_path=image_path,
                    prompt=prompt_input.value,
                    api_key=api_key,
                    model_id=model_id
                )
                response_text.value = result
            except Exception as ex:
                response_text.value = f"Error: {ex}"
            finally:
                run_button.disabled = False
                progress_ring.visible = False
                page.update()

        run_button = ft.ElevatedButton("Run AI Task", icon=ft.Icons.PLAY_ARROW, on_click=run_ai_task)

        def close_dlg(e):
            page.pop_dialog()

        dlg = ft.AlertDialog(
            title=ft.Text(f"AI Recognize: {os.path.basename(image_path)}"),
            content=ft.Container(
                content=ft.Column([
                    ft.Image(src=image_path, height=200, fit=ft.BoxFit.CONTAIN),
                    task_dropdown,
                    prompt_input,
                    ft.Row([run_button, progress_ring], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Divider(),
                    ft.Column([
                        response_text,
                    ], scroll=ft.ScrollMode.AUTO, height=300)
                ], tight=True, scroll=ft.ScrollMode.AUTO),
                width=600,
            ),
            actions=[
                ft.TextButton("Close", on_click=close_dlg)
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dlg)

    def load_images_from_selected_directories():
        image_gallery.controls.clear()
        
        all_image_paths = []
        for directory_path in state.selected_paths:
            if os.path.isdir(directory_path):
                try:
                    for filename in os.listdir(directory_path):
                        file_path = os.path.join(directory_path, filename)
                        if os.path.isfile(file_path):
                            _, ext = os.path.splitext(filename)
                            if ext.lower() in VALID_IMAGE_EXTENSIONS:
                                all_image_paths.append(file_path)
                except (PermissionError, OSError):
                    continue

        for path in all_image_paths:
            def _on_tap(e, p=path):
                if on_image_select:
                    on_image_select(p)

            # Use a closure to capture the current 'path' value correctly
            def create_context_menu_handler(current_path):
                def _show_context_menu(e):
                    def _handle_delete(ev):
                        page.pop_dialog()
                        delete_image(current_path)
                    
                    def _handle_preview(ev):
                        page.pop_dialog()
                        open_image_preview(None, current_path)
                    
                    def _handle_ai_recognize(ev):
                        page.pop_dialog()
                        _show_ai_recognize_dialog(current_path)

                    def close_context_dlg(ev):
                        page.pop_dialog()

                    page.show_dialog(
                        ft.AlertDialog(
                            title=ft.Text(os.path.basename(current_path)),
                            content=ft.Column([
                                ft.ListTile(
                                    leading=ft.Icon(ft.Icons.AUTO_FIX_HIGH, color=ft.Colors.AMBER_600),
                                    title=ft.Text("AI Recognize"),
                                    on_click=_handle_ai_recognize
                                ),
                                ft.ListTile(
                                    leading=ft.Icon(ft.Icons.PREVIEW),
                                    title=ft.Text(i18n.get("dialog_title_image_preview", "Preview")),
                                    on_click=_handle_preview
                                ),
                                ft.ListTile(
                                    leading=ft.Icon(ft.Icons.DELETE_OUTLINE, color=ft.Colors.RED_400),
                                    title=ft.Text(i18n.get("dialog_btn_delete", "Delete")),
                                    on_click=_handle_delete
                                ),
                            ], tight=True),
                            actions=[
                                ft.TextButton(i18n.get("dialog_btn_close", "Close"), on_click=close_context_dlg)
                            ],
                            actions_alignment=ft.MainAxisAlignment.END,
                        )
                    )
                return _show_context_menu

            context_menu_handler = create_context_menu_handler(path)

            image_gallery.controls.append(
                ft.GestureDetector(
                    content=ft.Container(
                        width=150,
                        height=150,
                        border_radius=ft.border_radius.all(5),
                        content=ft.Image(
                            src=path,
                            fit=BoxFit.CONTAIN,
                            tooltip=os.path.basename(path)
                        ),
                        alignment=Alignment.CENTER,
                    ),
                    on_double_tap=lambda e, p=path: open_image_preview(e, p),
                    on_tap=_on_tap,
                    on_secondary_tap=context_menu_handler,
                    on_long_press=context_menu_handler,
                )
            )
        try:
            image_gallery.update()
        except:
            pass

    def toggle_directory_selection(e: ft.Event[ft.Checkbox]):
        path = e.control.data
        if e.control.value:
            state.selected_paths.add(path)
        else:
            state.selected_paths.discard(path)
        save_gallery_state()
        load_images_from_selected_directories()

    def toggle_directory_expand(e: ft.Event[ft.IconButton]):
        path = e.control.data
        if path in state.expanded_paths:
            state.expanded_paths.discard(path)
        else:
            state.expanded_paths.add(path)
        save_gallery_state()
        refresh_directory_tree()

    def build_directory_tree(root_path: str, current_level: int = 0) -> List[ft.Control]:
        controls = []
        try:
            subdirs = [d for d in os.listdir(root_path) if os.path.isdir(os.path.join(root_path, d))]
            subdirs.sort()

            for subdir in subdirs:
                full_path = os.path.join(root_path, subdir)
                is_expanded = full_path in state.expanded_paths
                
                has_children = False
                try:
                    has_children = any(os.path.isdir(os.path.join(full_path, d)) for d in os.listdir(full_path))
                except:
                    pass

                controls.append(
                    ft.Row(
                        controls=[
                            ft.Container(width=current_level * 15),
                            ft.IconButton(
                                icon=ft.Icons.KEYBOARD_ARROW_DOWN if is_expanded else ft.Icons.KEYBOARD_ARROW_RIGHT,
                                icon_size=14,
                                visual_density=ft.VisualDensity.COMPACT,
                                on_click=toggle_directory_expand,
                                data=full_path,
                                visible=has_children
                            ),
                            ft.Checkbox(
                                value=full_path in state.selected_paths,
                                on_change=toggle_directory_selection,
                                data=full_path,
                                visual_density=ft.VisualDensity.COMPACT,
                            ),
                            ft.Icon(ft.Icons.FOLDER_OPEN if is_expanded else ft.Icons.FOLDER, size=14, color=ft.Colors.AMBER_400),
                            ft.Text(subdir, size=12, overflow=ft.TextOverflow.ELLIPSIS),
                        ],
                        spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    )
                )

                if is_expanded:
                    controls.extend(build_directory_tree(full_path, current_level + 1))
        except (PermissionError, OSError):
            pass
            
        return controls

    def refresh_directory_tree():
        if state.current_directory and os.path.isdir(state.current_directory):
            directory_tree_column.controls = [
                ft.Row([
                    ft.Checkbox(
                        value=state.current_directory in state.selected_paths,
                        on_change=toggle_directory_selection,
                        data=state.current_directory,
                        visual_density=ft.VisualDensity.COMPACT,
                    ),
                    ft.Icon(ft.Icons.HOME, size=16, color=ft.Colors.BLUE_400),
                    ft.Text(os.path.basename(state.current_directory) or state.current_directory, weight=ft.FontWeight.BOLD, size=13)
                ], spacing=0),
                *build_directory_tree(state.current_directory)
            ]
        
        try:
            directory_tree_column.update()
        except:
            pass

    async def open_directory_picker(e: ft.Event[ft.Button]):
        if not state.file_picker:
            state.file_picker = ft.FilePicker()
        pick_directory = await state.file_picker.get_directory_path(initial_directory=state.current_directory)
        if pick_directory:
            db.save_setting("last_dir", pick_directory)
            state.current_directory = pick_directory
            selected_directory_text.value = state.current_directory
            state.selected_paths = {pick_directory}
            state.expanded_paths = set()
            save_gallery_state()
            refresh_directory_tree()
            load_images_from_selected_directories()
            selected_directory_text.update()

    def refresh_all(e):
        refresh_directory_tree()
        load_images_from_selected_directories()

    # --- Initialization ---
    def delayed_initialize():
        # Load row count
        saved_row_count = db.get_setting("gallery_row_count", "2")
        state.row_count = int(saved_row_count)
        image_gallery.runs_count = state.row_count
        zoom_slider.value = state.row_count

        # Load directory
        last_dir = db.get_setting("last_dir")
        if last_dir and os.path.isdir(last_dir):
            selected_directory_text.value = last_dir
            state.current_directory = last_dir
            
            # Load selected and expanded paths
            try:
                sel_paths = json.loads(db.get_setting("gallery_selected_paths", "[]"))
                state.selected_paths = set(sel_paths) if sel_paths else {last_dir}
                
                exp_paths = json.loads(db.get_setting("gallery_expanded_paths", "[]"))
                state.expanded_paths = set(exp_paths)
            except:
                state.selected_paths = {last_dir}
                state.expanded_paths = set()

            refresh_directory_tree()
            load_images_from_selected_directories()
        else:
            selected_directory_text.value = "No directory selected."

    delayed_initialize()

    # Expansion Tile for the tree to save space
    tree_expansion_tile = ft.ExpansionTile(
        title=ft.Text(i18n.get("home_assets_label_dir_structure", "Folders"), size=13, weight=ft.FontWeight.BOLD),
        leading=ft.Icon(ft.Icons.ACCOUNT_TREE_OUTLINED, size=20, color=ft.Colors.BLUE_400),
        controls=[
            ft.Container(
                content=directory_tree_column,
                padding=ft.padding.only(left=5, right=5, bottom=10),
            )
        ],
        maintain_state=True,
    )

    return ft.Container(
        content=ft.Column(
            [
                # Compact Header
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.FOLDER_OPEN, size=20, color=ft.Colors.BLUE_GREY_400),
                        selected_directory_text,
                        ft.IconButton(
                            icon=ft.Icons.EDIT_NOTE,
                            on_click=open_directory_picker,
                            tooltip=i18n.get("home_assets_btn_browse_tooltip"),
                            icon_size=20,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.REFRESH,
                            on_click=refresh_all,
                            tooltip=i18n.get("home_history_btn_refresh_tooltip"),
                            icon_size=20,
                        )
                    ],
                    spacing=5,
                ),
                
                # Collapsible Tree
                tree_expansion_tile,
                
                # Zoom Control
                ft.Row([
                    ft.Icon(ft.Icons.GRID_VIEW, size=16, color=ft.Colors.BLUE_GREY_300),
                    ft.Container(content=zoom_slider, expand=True)
                ], spacing=10),
                
                ft.Divider(height=1),
                
                # Gallery
                ft.Column(
                    controls=[image_gallery],
                    expand=True,
                    scroll=ft.ScrollMode.AUTO
                )
            ],
            expand=True,
            spacing=10,
        ),
        padding=ft.padding.all(10),
        expand=expand,
    )
