import flet as ft


def show_snackbar(page: ft.Page, message: str, is_error: bool = False, ):
    page.show_dialog(ft.SnackBar(
        content=ft.Text(message),
        bgcolor=ft.Colors.ERROR if is_error else ft.Colors.GREEN_700,
    ))
