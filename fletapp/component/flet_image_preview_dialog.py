import flet as ft
from typing import Callable

class ImagePreviewDialog:
    def __init__(self, page: ft.Page):
        self.page = page
        
        # --- Constants for Zoom & Pan ---
        self.INITIAL_SCALE = 1.0
        self.ZOOM_FACTOR = 0.1
        self.MAX_ZOOM = 3.0
        self.MIN_ZOOM = 0.5
        self.VIEWPORT_WIDTH = 800
        self.VIEWPORT_HEIGHT = 600

        # --- Internal Controls ---
        self.preview_image = ft.Image(
            fit=ft.ImageFit.CONTAIN,
            scale=self.INITIAL_SCALE,
            left=0,
            top=0,
        )
        self.delete_button = ft.TextButton("Delete")
        self.download_button = ft.TextButton("Download")

        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Image Preview"),
            content=ft.GestureDetector(
                content=ft.Container(
                    width=self.VIEWPORT_WIDTH,
                    height=self.VIEWPORT_HEIGHT,
                    content=ft.Stack(controls=[self.preview_image]),
                    clip_behavior=ft.ClipBehavior.HARD_EDGE,
                    alignment=ft.alignment.center,
                ),
                on_scroll=self._on_scroll_zoom,
                on_pan_update=self._on_pan_update,
                drag_interval=10,
            ),
            actions=[
                self.download_button,
                self.delete_button,
                ft.TextButton("Close", on_click=self.close),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def _on_scroll_zoom(self, e: ft.ScrollEvent):
        current_scale = self.preview_image.scale or self.INITIAL_SCALE
        if e.scroll_delta_y < 0:  # Zoom in
            new_scale = min(self.MAX_ZOOM, current_scale + self.ZOOM_FACTOR)
        else:  # Zoom out
            new_scale = max(self.MIN_ZOOM, current_scale - self.ZOOM_FACTOR)
        
        self.preview_image.scale = new_scale
        self.preview_image.update()

    def _on_pan_update(self, e: ft.DragUpdateEvent):
        self.preview_image.left = (self.preview_image.left or 0) + e.delta_x
        self.preview_image.top = (self.preview_image.top or 0) + e.delta_y
        self.preview_image.update()

    def open(self, image_path: str, on_delete: Callable[[str], None] = None, on_download: Callable[[str], None] = None):
        # Reset image state
        self.preview_image.src = image_path
        self.preview_image.scale = self.INITIAL_SCALE
        self.preview_image.left = 0
        self.preview_image.top = 0

        # Wire up actions
        if on_delete:
            self.delete_button.on_click = lambda _: on_delete(image_path)
            self.delete_button.visible = True
        else:
            self.delete_button.visible = False

        if on_download:
            self.download_button.on_click = lambda _: on_download(image_path)
            self.download_button.visible = True
        else:
            self.download_button.visible = False
        
        self.page.open(self.dialog)

    def close(self, e):
        self.page.close(self.dialog)
