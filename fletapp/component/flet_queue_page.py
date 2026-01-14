import flet as ft
import time
import base64
from io import BytesIO
from common.job_manager import job_manager, Job
from common import i18n

def queue_page(page: ft.Page):
    
    def format_time(timestamp):
        if not timestamp:
            return "--:--:--"
        return time.strftime("%H:%M:%S", time.localtime(timestamp))

    def get_status_text(status):
        status_map = {
            "queued": i18n.get("queue_status_queued"),
            "running": i18n.get("queue_status_running"),
            "success": i18n.get("queue_status_success"),
            "error": i18n.get("queue_status_error"),
            "cancelled": i18n.get("queue_status_cancelled")
        }
        return status_map.get(status, status.capitalize())

    def get_status_icon(status):
        if status == "queued":
            return ft.Icon(ft.Icons.TIMER, color=ft.Colors.GREY_500, size=18)
        elif status == "running":
            return ft.ProgressRing(width=14, height=14, stroke_width=2)
        elif status == "success":
            return ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_500, size=18)
        elif status == "error":
            return ft.Icon(ft.Icons.ERROR, color=ft.Colors.RED_500, size=18)
        elif status == "cancelled":
            return ft.Icon(ft.Icons.CANCEL, color=ft.Colors.ORANGE_500, size=18)
        return ft.Icon(ft.Icons.QUESTION_MARK, size=18)

    def show_job_details(job: Job):
        # Extract prompt from kwargs
        prompt = job.kwargs.get("prompt") or job.kwargs.get("prompt_parts")
        
        # Format prompt parts if it's a list (from chat)
        if isinstance(prompt, list):
            formatted_prompt = []
            for part in prompt:
                if isinstance(part, str):
                    formatted_prompt.append(part)
                else:
                    formatted_prompt.append(f"[Image/Object: {type(part).__name__}]")
            prompt_text = "\n".join(formatted_prompt)
        else:
            prompt_text = str(prompt) if prompt else "(No prompt)"

        # Extract images for preview
        images_row = ft.Row(wrap=True, spacing=10)
        
        # 1. Check for image_paths (Single Edit)
        image_paths = job.kwargs.get("image_paths", [])
        for path in image_paths:
            images_row.controls.append(
                ft.Image(src=path, width=80, height=80, fit=ft.BoxFit.COVER, border_radius=5)
            )
            
        # 2. Check for PIL Images in prompt_parts (Chat)
        prompt_parts = job.kwargs.get("prompt_parts", [])
        if isinstance(prompt_parts, list):
            for part in prompt_parts:
                if not isinstance(part, str):
                    try:
                        # Convert PIL Image to base64 for preview
                        buffered = BytesIO()
                        preview_img = part.copy()
                        preview_img.thumbnail((200, 200))
                        preview_img.save(buffered, format="PNG")
                        img_str = base64.b64encode(buffered.getvalue()).decode()
                        images_row.controls.append(
                            ft.Image(src_base64=img_str, width=80, height=80, fit=ft.BoxFit.COVER, border_radius=5)
                        )
                    except:
                        pass

        def close_dlg(e):
            page.pop_dialog()

        # Create a more beautiful details view
        dialog = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, color=ft.Colors.BLUE_400),
                ft.Text(i18n.get("queue_dialog_title"), size=20, weight=ft.FontWeight.BOLD)
            ]),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(job.name, size=16, weight=ft.FontWeight.W_500, color=ft.Colors.BLUE_GREY_700),
                    ft.Divider(height=10, thickness=1),
                    
                    ft.Text(i18n.get("queue_dialog_prompt_label"), weight=ft.FontWeight.BOLD, size=14),
                    ft.Container(
                        content=ft.TextField(
                            value=prompt_text,
                            multiline=True,
                            read_only=True,
                            border=ft.InputBorder.NONE,
                            text_size=13,
                            text_style=ft.TextStyle(font_family="monospace"),
                            expand=True,
                        ),
                        padding=15,
                        border=ft.border.all(1, ft.Colors.GREY_400),
                        border_radius=10,
                        width=600,
                    ),
                    
                    ft.Column([
                        ft.Text(i18n.get("queue_dialog_images_label"), weight=ft.FontWeight.BOLD, size=14),
                        images_row,
                    ], visible=len(images_row.controls) > 0),
                    
                    ft.Container(height=10),
                    
                    ft.Row([
                        ft.Column([
                            ft.Text(i18n.get("queue_dialog_config_title"), weight=ft.FontWeight.BOLD, size=14),
                            ft.Text(f"{i18n.get('home_control_model_label')}: {job.kwargs.get('model_id', 'Default')}", size=13),
                            ft.Text(f"{i18n.get('home_control_resolution_label')}: {job.kwargs.get('resolution', 'Default')}", size=13),
                            ft.Text(f"{i18n.get('home_control_ratio_label')}: {job.kwargs.get('aspect_ratio', 'Default')}", size=13),
                        ], expand=True),
                        ft.Column([
                            ft.Text(i18n.get("queue_dialog_exec_title"), weight=ft.FontWeight.BOLD, size=14),
                            ft.Text(f"{i18n.get('queue_col_status')}: {get_status_text(job.status)}", size=13, color=ft.Colors.BLUE_600 if job.status == "running" else None),
                            ft.Text(f"{i18n.get('queue_col_created')}: {format_time(job.created_at)}", size=13),
                            ft.Text(f"{i18n.get('queue_col_started')}: {format_time(job.started_at)}", size=13),
                        ], expand=True),
                    ], spacing=20),
                    
                    ft.Column([
                        ft.Divider(height=20),
                        ft.Text(i18n.get("queue_dialog_error_label"), weight=ft.FontWeight.BOLD, size=14, color=ft.Colors.RED_600),
                        ft.Container(
                            content=ft.Text(job.error if job.error else "", color=ft.Colors.RED_700, size=12),
                            padding=10,
                            border=ft.border.all(1, ft.Colors.RED_200),
                            border_radius=5,
                            width=600,
                        )
                    ], visible=bool(job.error)),
                    
                ], tight=True, scroll=ft.ScrollMode.AUTO, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                width=600,
                height=500,
            ),
            actions=[
                ft.ElevatedButton(i18n.get("dialog_btn_close"), on_click=close_dlg, style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ft.Colors.BLUE_400))
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=15),
        )
        
        page.show_dialog(dialog)

    def create_job_row(job: Job):
        duration = ""
        if job.started_at and job.finished_at:
            duration = f" ({int(job.finished_at - job.started_at)}s)"
        elif job.started_at:
            duration = f" ({int(time.time() - job.started_at)}s...)"

        cancel_btn = ft.IconButton(
            icon=ft.Icons.CANCEL_OUTLINED,
            icon_color=ft.Colors.RED_400,
            tooltip=i18n.get("queue_btn_cancel_tooltip"),
            on_click=lambda _: job_manager.cancel_job(job.id),
            visible=(job.status == "queued")
        )

        view_btn = ft.IconButton(
            icon=ft.Icons.VISIBILITY_OUTLINED,
            icon_color=ft.Colors.BLUE_400,
            tooltip=i18n.get("queue_btn_view_tooltip"),
            on_click=lambda _: show_job_details(job)
        )

        # Merge Icon and Status text into one cell
        status_cell_content = ft.Row([
            get_status_icon(job.status),
            ft.Text(get_status_text(job.status), color=ft.Colors.BLUE_600 if job.status == "running" else None)
        ], spacing=8, alignment=ft.MainAxisAlignment.START)

        return ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(job.name, overflow=ft.TextOverflow.ELLIPSIS, weight=ft.FontWeight.W_500)),
                ft.DataCell(status_cell_content),
                ft.DataCell(ft.Text(format_time(job.created_at))),
                ft.DataCell(ft.Text(f"{format_time(job.started_at)}{duration}")),
                ft.DataCell(ft.Row([view_btn, cancel_btn], spacing=0)),
            ]
        )

    job_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text(i18n.get("queue_col_name"), weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text(i18n.get("queue_col_status"), weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text(i18n.get("queue_col_created"), weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text(i18n.get("queue_col_started"), weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text(i18n.get("queue_col_actions"), weight=ft.FontWeight.BOLD)),
        ],
        rows=[],
        heading_row_color=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        divider_thickness=1,
        column_spacing=20,
        expand=True,
    )

    def refresh_ui():
        jobs = job_manager.get_all_jobs()
        # Show newest first
        job_table.rows = [create_job_row(j) for j in reversed(jobs)]
        queue_count_text.value = i18n.get("queue_jobs_count", count=job_manager.get_queue_size())
        try:
            page.update()
        except:
            pass

    queue_count_text = ft.Text(i18n.get("queue_jobs_count", count=job_manager.get_queue_size()), size=20, weight=ft.FontWeight.BOLD)
    
    # Subscribe to job manager updates
    job_manager.subscribe(refresh_ui)

    # Main layout
    view = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.QUEUE_PLAY_NEXT, size=30, color=ft.Colors.BLUE_400),
                queue_count_text,
                ft.IconButton(ft.Icons.REFRESH, on_click=lambda _: refresh_ui(), tooltip=i18n.get("home_history_btn_refresh_tooltip"))
            ], alignment=ft.MainAxisAlignment.START),
            ft.Divider(height=20, thickness=1),
            ft.Column([
                ft.Card(
                    content=ft.Container(
                        content=job_table,
                        padding=10,
                    ),
                    elevation=2,
                    expand=True,
                )
            ], expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        ], expand=True),
        expand=True,
        padding=20
    )

    # Initial load
    refresh_ui()

    return view
