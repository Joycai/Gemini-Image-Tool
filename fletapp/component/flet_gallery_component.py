import os
from dataclasses import dataclass, field
from typing import Union, Callable, List, Set, Dict

import flet as ft
from flet import Container, BoxFit, Alignment, Page

from common import database as db, i18n
from common.config import VALID_IMAGE_EXTENSIONS
from fletapp.component.flet_image_preview_dialog import PreviewDialogData, preview_dialog


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
    selected_directory_field = ft.TextField(
        label=i18n.get("home_assets_label_dirPath", "Directory Path"),
        read_only=True,
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

    directory_tree_column = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, height=200, visible=False)

    # --- Functions ---

    def open_image_preview(e, image_path):
        page.show_dialog(preview_dialog(page, PreviewDialogData(
            image_list=[image_path],
            current_index=0,
        ), None, True))

    def update_grid_layout(e: ft.Event[ft.Slider]):
        columns = int(e.control.value)
        state.row_count = columns
        image_gallery.runs_count = columns
        image_gallery.update()

    zoom_slider = ft.Slider(
        min=1,
        max=5,
        divisions=4,
        value=state.row_count,
        label="{value}",
        on_change=update_grid_layout,
        width=200,
    )

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
                    on_tap=_on_tap
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
        load_images_from_selected_directories()

    def toggle_directory_expand(e: ft.Event[ft.IconButton]):
        path = e.control.data
        if path in state.expanded_paths:
            state.expanded_paths.discard(path)
        else:
            state.expanded_paths.add(path)
        refresh_directory_tree()

    def build_directory_tree(root_path: str, current_level: int = 0) -> List[ft.Control]:
        controls = []
        try:
            # Get subdirectories
            subdirs = [d for d in os.listdir(root_path) if os.path.isdir(os.path.join(root_path, d))]
            subdirs.sort()

            for subdir in subdirs:
                full_path = os.path.join(root_path, subdir)
                is_expanded = full_path in state.expanded_paths
                
                # Check if it has subdirectories for the expand icon
                has_children = False
                try:
                    has_children = any(os.path.isdir(os.path.join(full_path, d)) for d in os.listdir(full_path))
                except:
                    pass

                # Directory Row
                controls.append(
                    ft.Row(
                        controls=[
                            ft.Container(width=current_level * 20), # Indentation
                            ft.IconButton(
                                icon=ft.Icons.KEYBOARD_ARROW_DOWN if is_expanded else ft.Icons.KEYBOARD_ARROW_RIGHT,
                                icon_size=16,
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
                            ft.Icon(ft.Icons.FOLDER_OPEN if is_expanded else ft.Icons.FOLDER, size=16, color=ft.Colors.AMBER_400),
                            ft.Text(subdir, size=13, overflow=ft.TextOverflow.ELLIPSIS),
                        ],
                        spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    )
                )

                # Recursive children
                if is_expanded:
                    controls.extend(build_directory_tree(full_path, current_level + 1))
        except (PermissionError, OSError):
            pass
            
        return controls

    def refresh_directory_tree():
        if state.current_directory and os.path.isdir(state.current_directory):
            directory_tree_column.controls = [
                # Root directory entry
                ft.Row([
                    ft.Checkbox(
                        value=state.current_directory in state.selected_paths,
                        on_change=toggle_directory_selection,
                        data=state.current_directory,
                        visual_density=ft.VisualDensity.COMPACT,
                    ),
                    ft.Icon(ft.Icons.HOME, size=16, color=ft.Colors.BLUE_400),
                    ft.Text(os.path.basename(state.current_directory) or state.current_directory, weight=ft.FontWeight.BOLD)
                ], spacing=0),
                # Subdirectories
                *build_directory_tree(state.current_directory)
            ]
            directory_tree_column.visible = True
        else:
            directory_tree_column.visible = False
        
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
            selected_directory_field.value = state.current_directory
            state.selected_paths = {pick_directory} # Select root by default
            state.expanded_paths = set()
            refresh_directory_tree()
            load_images_from_selected_directories()
            selected_directory_field.update()

    def refresh_all(e):
        refresh_directory_tree()
        load_images_from_selected_directories()

    # --- Initialization ---
    def delayed_initialize():
        last_dir = db.get_setting("last_dir")
        if last_dir and os.path.isdir(last_dir):
            selected_directory_field.value = last_dir
            state.current_directory = last_dir
            state.selected_paths = {last_dir}
            refresh_directory_tree()
            load_images_from_selected_directories()
        else:
            selected_directory_field.value = "No directory selected."

    delayed_initialize()

    return ft.Container(
        content=ft.Column(
            [
                ft.Column(
                    controls=[
                        selected_directory_field,
                        ft.Row(
                            controls=[
                                ft.Button(
                                    content=i18n.get("home_assets_btn_browse", "Browse"),
                                    icon=ft.Icons.FOLDER_OPEN,
                                    on_click=open_directory_picker,
                                    tooltip=i18n.get("home_assets_btn_browse_tooltip", "Browse a Directory"),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.REFRESH,
                                    on_click=refresh_all,
                                    tooltip=i18n.get("home_assets_btn_refresh_tooltip", "Refresh the Gallery"),
                                )
                            ],
                            expand=True
                        ),
                        ft.Text(i18n.get("home_assets_label_dir_structure", "Directory Structure:"), size=12, weight=ft.FontWeight.BOLD),
                        ft.Container(
                            content=directory_tree_column,
                            border=ft.border.all(1, ft.Colors.GREY_300),
                            border_radius=5,
                            padding=5,
                        ),
                        ft.Row([ft.Text(i18n.get("home_history_zoom", "Column Num:")),
                                zoom_slider]),
                    ]
                ),
                ft.Column(
                    controls=[image_gallery],
                    expand=True,
                    scroll=ft.ScrollMode.AUTO
                )
            ],
            expand=True,
        ),
        padding=ft.padding.all(10),
        expand=expand,
    )
