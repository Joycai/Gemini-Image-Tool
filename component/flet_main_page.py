import flet as ft
from typing import List, Dict, Any, Optional
import os # Added for os.path.basename

import i18n
import database as db
import logger_utils
from config import (
    MODEL_SELECTOR_CHOICES,
    MODEL_SELECTOR_DEFAULT,
    AR_SELECTOR_CHOICES,
    AR_SELECTOR_DEFAULT,
    RES_SELECTOR_CHOICES,
    RES_SELECTOR_DEFAULT,
)
from component.flet_assets_block import FletAssetsBlock # Import the FletAssetsBlock

class FletMainPage(ft.Control): # Base class is ft.Control
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.settings: Dict[str, Any] = db.get_all_settings()
        self.initial_prompts: List[str] = db.get_all_prompt_titles()

        self.state_selected_images: List[str] = []
        self.state_marked_for_add: Optional[str] = None
        self.state_marked_for_remove: Optional[str] = None

        self.assets_block = FletAssetsBlock(page=self.page, prefix="main_")

        self.gallery_selected = ft.GridView(
            runs_count=6,
            max_extent=100,
            spacing=5,
            run_spacing=5,
            child_aspect_ratio=1.0,
            padding=0,
            controls=[],
        )
        self.btn_add_to_selected = ft.ElevatedButton(
            text=i18n.get("home_assets_btn_addToSelected"),
            style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_500, color=ft.Colors.WHITE),
            on_click=self.add_marked_to_selected_handler
        )
        self.btn_remove_from_selected = ft.ElevatedButton(
            text=i18n.get("home_control_btn_removeFromSelected"),
            style=ft.ButtonStyle(bgcolor=ft.Colors.RED_500, color=ft.Colors.WHITE),
            on_click=self.remove_marked_from_selected_handler
        )

        self.prompt_dropdown = ft.Dropdown(
            options=[ft.dropdown.Option(title) for title in self.initial_prompts],
            value=i18n.get("home_control_prompt_placeholder"),
            label=i18n.get("home_control_prompt_label_history"),
            expand=3,
            on_change=self.load_prompt_to_ui_handler
        )
        self.btn_load_prompt = ft.ElevatedButton(
            text=i18n.get("home_control_prompt_btn_load"),
            expand=1,
            on_click=self.load_prompt_to_ui_handler
        )
        self.btn_del_prompt = ft.ElevatedButton(
            text=i18n.get("home_control_prompt_btn_delete"),
            expand=1,
            style=ft.ButtonStyle(bgcolor=ft.Colors.RED_500, color=ft.Colors.WHITE),
            on_click=self.delete_prompt_from_db_handler
        )
        self.prompt_input = ft.TextField(
            label="",
            hint_text=i18n.get("home_control_prompt_input_placeholder"),
            multiline=True,
            min_lines=4,
            max_lines=4,
        )
        self.prompt_title_input = ft.TextField(
            hint_text=i18n.get("home_control_prompt_save_placeholder"),
            label=i18n.get("home_control_prompt_save_label"),
            expand=3,
            border_radius=0
        )
        self.btn_save_prompt = ft.ElevatedButton(
            text=i18n.get("home_control_prompt_btn_save"),
            expand=1,
            on_click=self.save_prompt_to_db_handler
        )

        self.model_selector = ft.Dropdown(
            options=[ft.dropdown.Option(choice) for choice in MODEL_SELECTOR_CHOICES],
            value=MODEL_SELECTOR_DEFAULT,
            label=i18n.get("home_control_model_label"),
            expand=2,
        )
        self.ar_selector = ft.Dropdown(
            options=[ft.dropdown.Option(text=text, key=key) for text, key in i18n.get_translated_choices(AR_SELECTOR_CHOICES)],
            value=AR_SELECTOR_DEFAULT,
            label=i18n.get("home_control_ratio_label"),
            expand=1
        )
        self.res_selector = ft.Dropdown(
            options=[ft.dropdown.Option(choice) for choice in RES_SELECTOR_CHOICES],
            value=RES_SELECTOR_DEFAULT,
            label=i18n.get("home_control_resolution_label"),
            expand=1
        )

        self.btn_send = ft.ElevatedButton(
            text=i18n.get("home_control_btn_send"),
            style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_500, color=ft.Colors.WHITE),
            expand=3,
        )
        self.btn_retry = ft.ElevatedButton(
            text=i18n.get("home_control_btn_retry"),
            expand=1,
        )

        self.log_output = ft.TextField(
            label=i18n.get("home_control_log_label"),
            multiline=True,
            read_only=True,
            min_lines=10,
            max_lines=10,
            border_radius=0,
            value=""
        )

        self.result_image = ft.Image(
            src="",
            fit=ft.ImageFit.CONTAIN,
            height=500,
        )
        self.btn_download = ft.ElevatedButton(
            text=i18n.get("home_preview_btn_download_placeholder"),
            disabled=True,
        )
        self.file_downloader = ft.FilePicker(on_result=self.on_file_downloaded)

        self.page.overlay.append(self.file_downloader)

    def _get_control_name(self): # Added this method
        return "fletmainpage"

    def build(self):
        return ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        self.assets_block,
                        self.btn_add_to_selected,
                    ],
                    expand=4
                ),
                ft.Column(
                    controls=[
                        ft.Card(
                            content=ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Markdown(f"### {i18n.get('home_control_title')}"),
                                        self.btn_remove_from_selected,
                                        ft.Container(
                                            content=self.gallery_selected,
                                            alignment=ft.alignment.center,
                                            padding=ft.padding.only(top=5),
                                        ),
                                        ft.Markdown(i18n.get("home_control_prompt_title")),
                                        ft.Row(
                                            controls=[
                                                self.prompt_dropdown,
                                                self.btn_load_prompt,
                                                self.btn_del_prompt,
                                            ]
                                        ),
                                        self.prompt_input,
                                        ft.Row(
                                            controls=[
                                                self.prompt_title_input,
                                                self.btn_save_prompt,
                                            ]
                                        ),
                                        ft.Row(
                                            controls=[
                                                self.model_selector,
                                                self.ar_selector,
                                                self.res_selector,
                                            ]
                                        ),
                                        ft.Row(
                                            controls=[
                                                self.btn_send,
                                                self.btn_retry,
                                            ]
                                        ),
                                        ft.ExpansionTile(
                                            title=ft.Text(i18n.get("home_control_log_label")),
                                            controls=[
                                                self.log_output,
                                            ]
                                        ),
                                    ],
                                ),
                                padding=ft.padding.all(10)
                            )
                        ),
                        ft.Card(
                            content=ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Markdown(f"### {i18n.get('home_preview_title')}"),
                                        ft.Text(i18n.get("home_preview_label_result")),
                                        self.result_image,
                                        self.btn_download,
                                    ],
                                ),
                                padding=ft.padding.all(10)
                            )
                        )
                    ],
                    expand=6
                )
            ],
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.START
        )

    def _update_selected_gallery(self):
        self.gallery_selected.controls.clear()
        for path in self.state_selected_images:
            self.gallery_selected.controls.append(
                ft.Image(
                    src=path,
                    fit=ft.ImageFit.CONTAIN,
                )
            )
        self.gallery_selected.update()

    def mark_for_add_handler(self, image_path: str):
        self.state_marked_for_add = image_path

    def mark_for_remove_handler(self, image_path: str):
        self.state_marked_for_remove = image_path

    def add_marked_to_selected_handler(self, e):
        if not self.state_marked_for_add:
            return

        if self.state_marked_for_add not in self.state_selected_images:
            self.state_selected_images.append(self.state_marked_for_add)
            if len(self.state_selected_images) > 5:
                self.state_selected_images = self.state_selected_images[-5:]
            logger_utils.log(i18n.get("logic_log_selectImage", name=os.path.basename(self.state_marked_for_add)))
            self._update_selected_gallery()
        self.state_marked_for_add = None
        self.update()

    def remove_marked_from_selected_handler(self, e):
        if not self.state_marked_for_remove or self.state_marked_for_remove not in self.state_selected_images:
            return

        self.state_selected_images = [item for item in self.state_selected_images if item != self.state_marked_for_remove]
        logger_utils.log(i18n.get("logic_log_removeImage", name=os.path.basename(self.state_marked_for_remove), count=len(self.state_selected_images)))
        self._update_selected_gallery()
        self.state_marked_for_remove = None
        self.update()

    def refresh_prompt_dropdown(self):
        titles = db.get_all_prompt_titles()
        self.prompt_dropdown.options = [ft.dropdown.Option(title) for title in titles]
        self.prompt_dropdown.update()

    def load_prompt_to_ui_handler(self, e):
        selected_title = self.prompt_dropdown.value
        if not selected_title or selected_title == i18n.get("home_control_prompt_placeholder"):
            return

        logger_utils.log(i18n.get("logic_log_loadPrompt", title=selected_title))
        content = db.get_prompt_content(selected_title)
        self.prompt_input.value = content
        self.prompt_input.update()

    def save_prompt_to_db_handler(self, e):
        title = self.prompt_title_input.value
        content = self.prompt_input.value
        if not title or not content:
            self.page.snack_bar = ft.SnackBar(ft.Text(i18n.get("logic_warn_promptEmpty")), open=True)
            self.page.update()
            return

        db.save_prompt(title, content)
        logger_utils.log(i18n.get("logic_log_savePrompt", title=title))
        self.page.snack_bar = ft.SnackBar(ft.Text(i18n.get("logic_info_promptSaved", title=title)), open=True)
        self.page.update()
        self.refresh_prompt_dropdown()
        self.prompt_title_input.value = ""
        self.prompt_title_input.update()

    def delete_prompt_from_db_handler(self, e):
        selected_title = self.prompt_dropdown.value
        if not selected_title or selected_title == i18n.get("home_control_prompt_placeholder"):
            return

        db.delete_prompt(selected_title)
        logger_utils.log(i18n.get("logic_log_deletePrompt", title=selected_title))
        self.page.snack_bar = ft.SnackBar(ft.Text(i18n.get("logic_info_promptDeleted", title=selected_title)), open=True)
        self.page.update()
        self.refresh_prompt_dropdown()
        self.prompt_dropdown.value = i18n.get("home_control_prompt_placeholder")
        self.prompt_dropdown.update()
        self.prompt_input.value = ""
        self.prompt_input.update()

    async def download_image(self, e):
        if self.result_image.src:
            await self.file_downloader.save_file(
                self.result_image.src,
                file_name=os.path.basename(self.result_image.src)
            )
    
    def on_file_downloaded(self, e: ft.FilePickerResultEvent):
        if e.path:
            self.page.snack_bar = ft.SnackBar(ft.Text(f"File saved to: {e.path}"), open=True)
        else:
            self.page.snack_bar = ft.SnackBar(ft.Text("Download cancelled."), open=True)
        self.page.update()
