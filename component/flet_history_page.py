import flet as ft
import os
import platform
import subprocess
from typing import List, Dict, Any, Optional

import i18n
import database as db
import logger_utils
from config import VALID_IMAGE_EXTENSIONS

class FletHistoryPage(ft.Control):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.state_hist_selected_path: Optional[str] = None
        self.file_downloader = ft.FilePicker(on_result=self.on_file_downloaded)

        self.gallery_output_history = ft.GridView(
            runs_count=6,
            max_extent=150,
            spacing=5,
            run_spacing=5,
            child_aspect_ratio=1.0,
            padding=0,
            controls=[],
        )
        self.btn_open_out_dir = ft.ElevatedButton(
            text=i18n.get("home_history_btn_open"),
            icon=ft.Icons.FOLDER_OPEN,
            on_click=self.open_output_folder_handler,
            style=ft.ButtonStyle(padding=ft.padding.symmetric(horizontal=10, vertical=5))
        )
        self.btn_refresh_history = ft.IconButton(
            icon=ft.Icons.REFRESH,
            on_click=self.refresh_history_handler,
            tooltip="Refresh history"
        )
        self.btn_download_hist = ft.ElevatedButton(
            text=i18n.get("home_history_btn_download"),
            icon=ft.Icons.DOWNLOAD,
            on_click=self.download_selected_file,
            disabled=True,
            expand=1
        )
        self.btn_delete_hist = ft.ElevatedButton(
            text=i18n.get("home_history_btn_delete"),
            icon=ft.Icons.DELETE,
            on_click=self.delete_output_file_handler,
            disabled=True,
            expand=1,
            style=ft.ButtonStyle(bgcolor=ft.Colors.RED_500, color=ft.Colors.WHITE)
        )

        self.page.overlay.append(self.file_downloader)

    def _get_control_name(self):
        return "flethistorypage"

    def build(self):
        return ft.Column(
            controls=[
                ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Markdown(f"## {i18n.get('home_history_title')}"),
                                        self.btn_open_out_dir,
                                        self.btn_refresh_history,
                                    ],
                                    alignment=ft.MainAxisAlignment.START,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                                ),
                                self.gallery_output_history,
                                ft.Row(
                                    controls=[
                                        self.btn_download_hist,
                                        self.btn_delete_hist,
                                    ]
                                )
                            ],
                        ),
                        padding=ft.padding.all(10)
                    )
                )
            ],
            expand=True
        )

    def _update_gallery(self, files: List[str]):
        self.gallery_output_history.controls.clear()
        for path in files:
            self.gallery_output_history.controls.append(
                ft.GestureDetector(
                    content=ft.Image(
                        src=path,
                        fit=ft.ImageFit.CONTAIN,
                        border_radius=ft.border_radius.all(5)
                    ),
                    on_tap=lambda e, p=path: self.on_gallery_image_select(p)
                )
            )
        # Removed self.gallery_output_history.update()
        # The parent control's update() will handle this.

    def load_output_gallery_logic(self) -> List[str]:
        save_dir = db.get_setting("save_path")
        if not save_dir or not os.path.exists(save_dir):
            return []
        files = [os.path.join(save_dir, f) for f in os.listdir(save_dir)
                 if os.path.splitext(f)[1].lower() in VALID_IMAGE_EXTENSIONS]
        files.sort(key=os.path.getmtime, reverse=True)
        return files

    def refresh_history_handler(self, e):
        files = self.load_output_gallery_logic()
        self._update_gallery(files)
        self.state_hist_selected_path = None
        self.btn_download_hist.disabled = True
        self.btn_delete_hist.disabled = True
        self.btn_download_hist.text = i18n.get("home_history_btn_download")
        self.update()

    def open_output_folder_handler(self, e):
        path = db.get_setting("save_path", "outputs")
        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
            except OSError as err:
                self.page.snack_bar = ft.SnackBar(ft.Text(i18n.get("logic_error_createDir", error=err)), open=True)
                self.page.update()
                return
        abs_path = os.path.abspath(path)
        logger_utils.log(f"Attempting to open directory: {abs_path}")
        try:
            system_platform = platform.system()
            if system_platform == "Windows":
                os.startfile(abs_path)
            elif system_platform == "Darwin":
                subprocess.run(["open", abs_path], check=False)
            else:
                subprocess.run(["xdg-open", abs_path], check=False)
        except (OSError, FileNotFoundError) as err:
            err_msg = i18n.get("logic_error_openFolder", error=err)
            logger_utils.log(err_msg)
            self.page.snack_bar = ft.SnackBar(ft.Text(err_msg), open=True)
            self.page.update()

    def on_gallery_image_select(self, file_path: str):
        self.state_hist_selected_path = file_path
        filename = os.path.basename(file_path)
        self.btn_download_hist.text = f"{i18n.get('home_history_btn_download')} ({filename})"
        self.btn_download_hist.disabled = False
        self.btn_delete_hist.disabled = False
        self.update()

    async def download_selected_file(self, e):
        if self.state_hist_selected_path:
            await self.file_downloader.save_file(
                self.state_hist_selected_path,
                file_name=os.path.basename(self.state_hist_selected_path)
            )
    
    def on_file_downloaded(self, e: ft.FilePickerResultEvent):
        if e.path:
            self.page.snack_bar = ft.SnackBar(ft.Text(f"File saved to: {e.path}"), open=True)
        else:
            self.page.snack_bar = ft.SnackBar(ft.Text("Download cancelled."), open=True)
        self.page.update()

    def delete_output_file_handler(self, e):
        if not self.state_hist_selected_path:
            self.page.snack_bar = ft.SnackBar(ft.Text(i18n.get("logic_warn_noImageSelected")), open=True)
            self.page.update()
            return

        if os.path.exists(self.state_hist_selected_path):
            try:
                os.remove(self.state_hist_selected_path)
                logger_utils.log(i18n.get("logic_log_deletedFile", path=self.state_hist_selected_path))
                self.page.snack_bar = ft.SnackBar(ft.Text(i18n.get("logic_info_deleteSuccess")), open=True)
                self.page.update()
            except (OSError, IOError) as err:
                logger_utils.log(i18n.get("logic_error_deleteFailed", error=err))
                self.page.snack_bar = ft.SnackBar(ft.Text(i18n.get("logic_warn_deleteFailed", error=err)), open=True)
                self.page.update()
        
        self.refresh_history_handler(None)

    def load_more_images(self, e):
        # Implement lazy loading if the history gallery can be very large
        pass
