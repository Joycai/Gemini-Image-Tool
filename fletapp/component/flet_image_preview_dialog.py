import flet as ft
from typing import Callable, List, Optional
from common import i18n

class ImagePreviewDialog:
    def __init__(self, page: ft.Page):
        self.page = page
        
        # --- Callbacks ---
        self.on_delete: Optional[Callable[[str], None]] = None
        self.on_download: Optional[Callable[[str], None]] = None
        
        # --- Image List ---
        self.image_list: List[str] = []
        self.current_index: int = 0

        # --- Constants for Zoom & Pan ---
        self.INITIAL_SCALE = 1.0
        self.ZOOM_FACTOR = 0.1
        self.MAX_ZOOM = 3.0
        self.MIN_ZOOM = 0.5
        self.VIEWPORT_WIDTH = 800
        self.VIEWPORT_HEIGHT = 600

        # --- Internal Controls ---
        self.preview_image = ft.Image(
            width=self.VIEWPORT_WIDTH,
            height=self.VIEWPORT_HEIGHT,
            fit=ft.ImageFit.CONTAIN, 
            scale=self.INITIAL_SCALE,
            left=0,
            top=0,
        )
        self.prev_button = ft.TextButton(i18n.get("dialog_btn_previous", "Previous"), on_click=self._go_previous)
        self.next_button = ft.TextButton(i18n.get("dialog_btn_next", "Next"), on_click=self._go_next)
        self.download_button = ft.TextButton(i18n.get("dialog_btn_download", "Download"))
        self.delete_button = ft.TextButton(i18n.get("dialog_btn_delete", "Delete"))

        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(i18n.get("dialog_title_image_preview", "Image Preview")),
            content=ft.GestureDetector(
                content=ft.Container(
                    width=self.VIEWPORT_WIDTH,
                    height=self.VIEWPORT_HEIGHT,
                    content=ft.Stack(controls=[self.preview_image]),
                    clip_behavior=ft.ClipBehavior.HARD_EDGE,
                ),
                on_scroll=self._on_scroll_zoom,
                on_pan_update=self._on_pan_update,
                drag_interval=10,
            ),
            actions=[
                self.prev_button,
                self.next_button,
                self.download_button,
                self.delete_button,
                ft.TextButton(i18n.get("dialog_btn_close", "Close"), on_click=self.close),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def _on_scroll_zoom(self, e: ft.ScrollEvent):
        current_scale = self.preview_image.scale or self.INITIAL_SCALE
        if e.scroll_delta_y < 0:
            new_scale = min(self.MAX_ZOOM, current_scale + self.ZOOM_FACTOR)
        else:
            new_scale = max(self.MIN_ZOOM, current_scale - self.ZOOM_FACTOR)
        self.preview_image.scale = new_scale
        self.preview_image.update()

    def _on_pan_update(self, e: ft.DragUpdateEvent):
        self.preview_image.left = (self.preview_image.left or 0) + e.delta_x
        self.preview_image.top = (self.preview_image.top or 0) + e.delta_y
        self.preview_image.update()

    def _go_previous(self, e):
        if self.current_index > 0:
            self._show_image_at_index(self.current_index - 1)
            self.dialog.update()

    def _go_next(self, e):
        if self.current_index < len(self.image_list) - 1:
            self._show_image_at_index(self.current_index + 1)
            self.dialog.update()

    def _show_image_at_index(self, index: int):
        self.current_index = index
        image_path = self.image_list[self.current_index]

        # Reset view and update image source
        self.preview_image.src = image_path
        self.preview_image.scale = self.INITIAL_SCALE
        self.preview_image.left = 0
        self.preview_image.top = 0

        # Update button callbacks
        if self.on_download:
            self.download_button.on_click = lambda _, p=image_path: self.on_download(p)
        if self.on_delete:
            self.delete_button.on_click = lambda _, p=image_path: self.on_delete(p)

        # Update navigation button visibility
        if self.prev_button.visible:
            self.prev_button.disabled = self.current_index == 0
            self.next_button.disabled = self.current_index == len(self.image_list) - 1
        
    def open(self, 
             image_path: Optional[str] = None, 
             image_list: Optional[List[str]] = None, 
             current_index: int = 0, 
             on_delete: Optional[Callable[[str], None]] = None, 
             on_download: Optional[Callable[[str], None]] = None):
        
        if image_path:
            self.image_list = [image_path]
            current_index = 0
            self.prev_button.visible = False
            self.next_button.visible = False
        elif image_list:
            self.image_list = image_list
            self.prev_button.visible = True
            self.next_button.visible = True
        else:
            raise ValueError("Either image_path or image_list must be provided.")

        self.on_delete = on_delete
        self.on_download = on_download

        self.delete_button.visible = on_delete is not None
        self.download_button.visible = on_download is not None

        self._show_image_at_index(current_index)
        self.page.open(self.dialog)

    def close(self, e):
        self.page.close(self.dialog)
