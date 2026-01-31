import flet as ft
from datetime import datetime, timedelta
from common import database as db, i18n

def dashboard_page(page: ft.Page):
    
    # --- State ---
    fee_config = {
        "model_id": None,
        "input_price": 0.0,
        "output_price": 0.0,
        "is_unified": True
    }

    def load_usage_data(e=None):
        start_date = start_date_picker.value.strftime("%Y-%m-%d 00:00:00") if start_date_picker.value else None
        end_date = end_date_picker.value.strftime("%Y-%m-%d 23:59:59") if end_date_picker.value else None
        
        summary = db.get_token_usage_summary(start_date, end_date)
        usage_table.rows.clear()
        
        total_input = 0
        total_output = 0
        total_all = 0
        total_requests = 0
        
        model_options = []
        
        for item in summary:
            model_id = item['model_id']
            input_tokens = item['total_input']
            output_tokens = item['total_output']
            all_tokens = item['total_all']
            requests = item['request_count']
            
            total_input += input_tokens
            total_output += output_tokens
            total_all += all_tokens
            total_requests += requests
            
            model_options.append(ft.dropdown.Option(model_id))
            
            usage_table.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(model_id, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(f"{input_tokens:,}")),
                        ft.DataCell(ft.Text(f"{output_tokens:,}")),
                        ft.DataCell(ft.Text(f"{all_tokens:,}")),
                        ft.DataCell(ft.Text(str(requests))),
                        ft.DataCell(
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_color=ft.Colors.RED_400,
                                tooltip=f"Reset {model_id}",
                                on_click=lambda _, m=model_id: reset_model_usage(m)
                            )
                        ),
                    ]
                )
            )
        
        # Update summary cards
        input_card.value = f"{total_input:,}"
        output_card.value = f"{total_output:,}"
        total_card.value = f"{total_all:,}"
        request_card.value = str(total_requests)
        
        # Update calculator dropdown
        calc_model_dropdown.options = model_options
        
        page.update()

    def reset_model_usage(model_id):
        def confirm_reset(e):
            db.clear_token_usage(model_id)
            page.pop_dialog()
            load_usage_data()
            
        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Confirm Reset"),
                content=ft.Text(f"Are you sure you want to clear all usage data for {model_id}?"),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda _: page.pop_dialog()),
                    ft.TextButton("Reset", on_click=confirm_reset),
                ]
            )
        )

    def calculate_fee(e=None):
        model_id = calc_model_dropdown.value
        if not model_id:
            return
            
        summary = db.get_token_usage_summary()
        model_data = next((item for item in summary if item['model_id'] == model_id), None)
        
        if not model_data:
            calc_result.value = "No data for this model."
            page.update()
            return
            
        try:
            in_price = float(input_price_field.value or 0)
            out_price = float(output_price_field.value or 0) if not unified_checkbox.value else in_price
            
            # Price is per million tokens
            fee = (model_data['total_input'] * in_price / 1_000_000) + \
                  (model_data['total_output'] * out_price / 1_000_000)
            
            calc_result.value = f"Estimated Total Fee: ${fee:.4f} USD"
        except ValueError:
            calc_result.value = "Invalid price input."
        
        page.update()

    # --- UI Components ---
    
    # Date Range Pickers
    start_date_picker = ft.DatePicker(
        on_change=load_usage_data,
        first_date=datetime(2024, 1, 1),
        last_date=datetime(2030, 12, 31),
    )
    end_date_picker = ft.DatePicker(
        on_change=load_usage_data,
        first_date=datetime(2024, 1, 1),
        last_date=datetime(2030, 12, 31),
    )

    input_card = ft.Text("0", size=30, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400)
    output_card = ft.Text("0", size=30, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
    total_card = ft.Text("0", size=30, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE_400)
    request_card = ft.Text("0", size=30, weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE_400)

    def create_stat_card(title, control, icon):
        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.ListTile(
                        leading=ft.Icon(icon, size=30),
                        title=ft.Text(title, size=14, color=ft.Colors.BLUE_GREY_400),
                        subtitle=control,
                    )
                ]),
                padding=10,
                width=200,
            )
        )

    usage_table = ft.DataTable(
        columns=[
            ft.DataColumn(label=ft.Text("Model ID", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(label=ft.Text("Input Tokens", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(label=ft.Text("Output Tokens", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(label=ft.Text("Total Tokens", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(label=ft.Text("Requests", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(label=ft.Text("Actions", weight=ft.FontWeight.BOLD)),
        ],
        rows=[]
    )

    # Calculator Components
    calc_model_dropdown = ft.Dropdown(label="Select Model", width=300)
    calc_model_dropdown.on_change = calculate_fee
    
    unified_checkbox = ft.Checkbox(label="Unified Price (Input = Output)", value=True, 
                                   on_change=lambda e: (setattr(output_price_field, 'visible', not e.control.value), 
                                                        setattr(input_price_field, 'label', "Price per 1M Tokens" if e.control.value else "Input Price per 1M"),
                                                        calculate_fee(),
                                                        page.update()))
    input_price_field = ft.TextField(label="Price per 1M Tokens", value="0", width=200, on_change=calculate_fee, suffix=ft.Text("USD"))
    output_price_field = ft.TextField(label="Output Price per 1M", value="0", width=200, visible=False, on_change=calculate_fee, suffix=ft.Text("USD"))
    calc_result = ft.Text("Estimated Total Fee: $0.0000 USD", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700)

    # Sub-tabs content
    usage_breakdown_content = ft.Column([
        ft.Text("Usage by Model", size=18, weight=ft.FontWeight.BOLD),
        ft.Column([usage_table], scroll=ft.ScrollMode.AUTO, expand=True)
    ], expand=True, spacing=10)

    fee_calculator_content = ft.Container(
        content=ft.Column([
            ft.Text("Cost Estimator", size=18, weight=ft.FontWeight.BOLD),
            ft.Row([calc_model_dropdown, unified_checkbox]),
            ft.Row([input_price_field, output_price_field]),
            ft.Container(height=10),
            calc_result,
            ft.Text("Note: Prices are usually quoted per 1 million tokens in USD.", size=12, italic=True)
        ], spacing=15),
        padding=20
    )

    # Dashboard Tabs using TabBar/TabBarView for compatibility
    dashboard_tabs = ft.Tabs(
        selected_index=0,
        length=2,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="Usage Breakdown"),
                        ft.Tab(label="Fee Calculator"),
                    ]
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[
                        usage_breakdown_content,
                        fee_calculator_content,
                    ]
                )
            ]
        ),
        expand=True
    )

    view = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.DASHBOARD, size=30, color=ft.Colors.BLUE_400),
                ft.Text("Usage Dashboard", size=24, weight=ft.FontWeight.BOLD),
                ft.VerticalDivider(),
                ft.TextButton("Start Date", icon=ft.Icons.CALENDAR_MONTH, on_click=lambda _: page.show_dialog(start_date_picker)),
                ft.TextButton("End Date", icon=ft.Icons.CALENDAR_MONTH, on_click=lambda _: page.show_dialog(end_date_picker)),
                ft.IconButton(ft.Icons.CLOSE, tooltip="Clear Date Filter", on_click=lambda _: (setattr(start_date_picker, 'value', None), setattr(end_date_picker, 'value', None), load_usage_data())),
                ft.IconButton(ft.Icons.REFRESH, on_click=load_usage_data)
            ]),
            ft.Divider(),
            ft.Row([
                create_stat_card("Total Input Tokens", input_card, ft.Icons.ARROW_UPWARD),
                create_stat_card("Total Output Tokens", output_card, ft.Icons.ARROW_DOWNWARD),
                create_stat_card("Total Tokens Used", total_card, ft.Icons.FUNCTIONS),
                create_stat_card("Total Requests", request_card, ft.Icons.HUB),
            ], wrap=True, spacing=20),
            ft.Divider(),
            dashboard_tabs
        ], expand=True, spacing=20),
        padding=20,
        expand=True
    )

    # Initial load
    load_usage_data()

    return view
