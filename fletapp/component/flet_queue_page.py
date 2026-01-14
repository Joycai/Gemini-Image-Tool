import flet as ft
import time
from common.job_manager import job_manager, Job
from common import i18n

def queue_page(page: ft.Page):
    
    def format_time(timestamp):
        if not timestamp:
            return "--:--:--"
        return time.strftime("%H:%M:%S", time.localtime(timestamp))

    def get_status_icon(status):
        if status == "queued":
            return ft.Icon(ft.Icons.TIMER, color=ft.Colors.GREY_500)
        elif status == "running":
            return ft.ProgressRing(width=16, height=16, stroke_width=2)
        elif status == "success":
            return ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_500)
        elif status == "error":
            return ft.Icon(ft.Icons.ERROR, color=ft.Colors.RED_500)
        elif status == "cancelled":
            return ft.Icon(ft.Icons.CANCEL, color=ft.Colors.ORANGE_500)
        return ft.Icon(ft.Icons.QUESTION_MARK)

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

        def close_dlg(e):
            page.pop_dialog()

        # Create a more beautiful details view
        dialog = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, color=ft.Colors.BLUE_400),
                ft.Text(f"Job Details", size=20, weight=ft.FontWeight.BOLD)
            ]),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(job.name, size=16, weight=ft.FontWeight.W_500, color=ft.Colors.BLUE_GREY_700),
                    ft.Divider(height=10, thickness=1),
                    
                    ft.Text("Prompt / Content:", weight=ft.FontWeight.BOLD, size=14),
                    ft.Container(
                        content=ft.TextField(
                            value=prompt_text,
                            multiline=True,
                            read_only=True,
                            border=ft.InputBorder.NONE,
                            text_size=13,
                            text_style=ft.TextStyle(font_family="monospace"),
                        ),
                        padding=15,
                        border=ft.border.all(1, ft.Colors.GREY_400),
                        border_radius=10,
                        expand=True,
                    ),
                    
                    ft.Container(height=10),
                    
                    ft.Row([
                        ft.Column([
                            ft.Text("Model Configuration", weight=ft.FontWeight.BOLD, size=14),
                            ft.Text(f"Model: {job.kwargs.get('model_id', 'Default')}", size=13),
                            ft.Text(f"Resolution: {job.kwargs.get('resolution', 'Default')}", size=13),
                            ft.Text(f"Aspect Ratio: {job.kwargs.get('aspect_ratio', 'Default')}", size=13),
                        ], expand=True),
                        ft.Column([
                            ft.Text("Execution Info", weight=ft.FontWeight.BOLD, size=14),
                            ft.Text(f"Status: {job.status.capitalize()}", size=13, color=ft.Colors.BLUE_600 if job.status == "running" else None),
                            ft.Text(f"Created: {format_time(job.created_at)}", size=13),
                            ft.Text(f"Started: {format_time(job.started_at)}", size=13),
                        ], expand=True),
                    ], spacing=20),
                    
                    ft.Column([
                        ft.Divider(height=20),
                        ft.Text("Error Message:", weight=ft.FontWeight.BOLD, size=14, color=ft.Colors.RED_600),
                        ft.Container(
                            content=ft.Text(job.error if job.error else "", color=ft.Colors.RED_700, size=12),
                            padding=10,
                            border=ft.border.all(1, ft.Colors.RED_200),
                            border_radius=5,
                        )
                    ], visible=bool(job.error)),
                    
                ], tight=True, scroll=ft.ScrollMode.AUTO, spacing=10),
                width=600,
                height=500,
            ),
            actions=[
                ft.ElevatedButton("Close", on_click=close_dlg, style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ft.Colors.BLUE_400))
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
            tooltip="Cancel Job",
            on_click=lambda _: job_manager.cancel_job(job.id),
            visible=(job.status == "queued")
        )

        view_btn = ft.IconButton(
            icon=ft.Icons.VISIBILITY_OUTLINED,
            icon_color=ft.Colors.BLUE_400,
            tooltip="View Details",
            on_click=lambda _: show_job_details(job)
        )

        return ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(job.name, expand=True, overflow=ft.TextOverflow.ELLIPSIS, weight=ft.FontWeight.W_500)),
                ft.DataCell(get_status_icon(job.status)),
                ft.DataCell(ft.Text(job.status.capitalize(), color=ft.Colors.BLUE_600 if job.status == "running" else None)),
                ft.DataCell(ft.Text(format_time(job.created_at))),
                ft.DataCell(ft.Text(f"{format_time(job.started_at)}{duration}")),
                ft.DataCell(ft.Row([view_btn, cancel_btn], spacing=0)),
            ]
        )

    job_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Job Name", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Icon", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Status", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Created", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Started/Duration", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Actions", weight=ft.FontWeight.BOLD)),
        ],
        rows=[],
        # Removed hardcoded heading_row_color to fit theme
        divider_thickness=1,
        column_spacing=20,
        # Ensure table expands to fill container
        expand=True,
    )

    def refresh_ui():
        jobs = job_manager.get_all_jobs()
        # Show newest first
        job_table.rows = [create_job_row(j) for j in reversed(jobs)]
        queue_count_text.value = f"Jobs in Queue: {job_manager.get_queue_size()}"
        try:
            page.update()
        except:
            pass

    queue_count_text = ft.Text(f"Jobs in Queue: {job_manager.get_queue_size()}", size=20, weight=ft.FontWeight.BOLD)
    
    # Subscribe to job manager updates
    job_manager.subscribe(refresh_ui)

    # Main layout
    view = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.QUEUE_PLAY_NEXT, size=30, color=ft.Colors.BLUE_400),
                queue_count_text,
                ft.IconButton(ft.Icons.REFRESH, on_click=lambda _: refresh_ui(), tooltip="Refresh List")
            ], alignment=ft.MainAxisAlignment.START),
            ft.Divider(height=20, thickness=1),
            ft.Column([
                ft.Card(
                    content=ft.Container(
                        content=ft.Row([job_table], scroll=ft.ScrollMode.ALWAYS),
                        padding=10,
                    ),
                    elevation=2,
                    expand=True,
                )
            ], scroll=ft.ScrollMode.AUTO, expand=True)
        ], expand=True),
        expand=True,
        padding=20
    )

    # Initial load
    refresh_ui()

    return view
