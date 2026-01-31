import flet as ft
from datetime import datetime, timedelta
from common import database as db, i18n

def dashboard_page(page: ft.Page):
    
    def get_date_range_text():
        if not start_date_picker.value and not end_date_picker.value:
            return i18n.get("dashboard_range_all", "All Time")
        
        start = start_date_picker.value.strftime("%Y-%m-%d") if start_date_picker.value else "..."
        end = end_date_picker.value.strftime("%Y-%m-%d") if end_date_picker.value else "..."
        return f"{start} ~ {end}"

    def load_usage_data(e=None):
        start_date = start_date_picker.value.strftime("%Y-%m-%d 00:00:00") if start_date_picker.value else None
        end_date = end_date_picker.value.strftime("%Y-%m-%d 23:59:59") if end_date_picker.value else None
        
        summary = db.get_token_usage_summary(start_date, end_date)
        prices = db.get_all_model_prices()
        
        usage_table.rows.clear()
        
        total_input = 0
        total_output = 0
        total_all = 0
        total_requests = 0
        total_fee = 0.0
        
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
            
            # Calculate fee for this model
            model_price = prices.get(model_id, {"input": 0.0, "output": 0.0})
            fee = (input_tokens * model_price["input"] / 1_000_000) + \
                  (output_tokens * model_price["output"] / 1_000_000)
            total_fee += fee
            
            model_options.append(ft.dropdown.Option(model_id))
            
            usage_table.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(model_id, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(f"{input_tokens:,}")),
                        ft.DataCell(ft.Text(f"{output_tokens:,}")),
                        ft.DataCell(ft.Text(f"${fee:.4f}")),
                        ft.DataCell(ft.Text(str(requests))),
                        ft.DataCell(
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_color=ft.Colors.RED_400,
                                tooltip=f"{i18n.get('dashboard_reset_tooltip', 'Reset')} {model_id}",
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
        fee_card.value = f"${total_fee:.2f}"
        
        # Update range text
        range_text.value = f"{i18n.get('dashboard_label_range', 'Range')}: {get_date_range_text()}"
        
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
                title=ft.Text(i18n.get("dashboard_reset_confirm_title", "Confirm Reset")),
                content=ft.Text(i18n.get("dashboard_reset_confirm_content", "Are you sure you want to clear all usage data for {model}?").format(model=model_id)),
                actions=[
                    ft.TextButton(i18n.get("dialog_btn_cancel", "Cancel"), on_click=lambda _: page.pop_dialog()),
                    ft.TextButton(i18n.get("dashboard_btn_reset", "Reset"), on_click=confirm_reset),
                ]
            )
        )

    def clear_old_data(e):
        def confirm_clear(ev):
            # First day of this month
            first_day = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            db.clear_token_usage(before_date=first_day.strftime("%Y-%m-%d %H:%M:%S"))
            page.pop_dialog()
            load_usage_data()

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(i18n.get("dashboard_clear_old_title", "Clear Old Data")),
                content=ft.Text(i18n.get("dashboard_clear_old_content", "This will delete all usage data before the current month. Continue?")),
                actions=[
                    ft.TextButton(i18n.get("dialog_btn_cancel", "Cancel"), on_click=lambda _: page.pop_dialog()),
                    ft.TextButton(i18n.get("dashboard_btn_clear", "Clear"), on_click=confirm_clear),
                ]
            )
        )

    def apply_quick_filter(days):
        if days == 0: # This month
            start_date_picker.value = datetime.now().replace(day=1)
        else:
            start_date_picker.value = datetime.now() - timedelta(days=days)
        end_date_picker.value = datetime.now()
        load_usage_data()

    def calculate_fee(e=None):
        model_id = calc_model_dropdown.value
        if not model_id:
            return
            
        summary = db.get_token_usage_summary()
        model_data = next((item for item in summary if item['model_id'] == model_id), None)
        
        if not model_data:
            calc_result.value = i18n.get("dashboard_calc_no_data", "No data for this model.")
            page.update()
            return
            
        try:
            in_price = float(input_price_field.value or 0)
            out_price = float(output_price_field.value or 0) if not unified_checkbox.value else in_price
            
            # Save price to DB
            db.save_model_price(model_id, in_price, out_price)
            
            # Price is per million tokens
            fee = (model_data['total_input'] * in_price / 1_000_000) + \
                  (model_data['total_output'] * out_price / 1_000_000)
            
            calc_result.value = f"{i18n.get('dashboard_calc_total_fee', 'Estimated Total Fee')}: ${fee:.4f} USD"
            load_usage_data() # Refresh table to show updated fees
        except ValueError:
            calc_result.value = i18n.get("dashboard_calc_invalid_input", "Invalid price input.")
        
        page.update()

    def on_calc_model_change(e):
        model_id = e.control.value
        price = db.get_model_price(model_id)
        input_price_field.value = str(price["input_price"])
        output_price_field.value = str(price["output_price"])
        unified_checkbox.value = price["input_price"] == price["output_price"]
        output_price_field.visible = not unified_checkbox.value
        calculate_fee()

    # --- UI Components ---
    
    start_date_picker = ft.DatePicker(on_change=load_usage_data, first_date=datetime(2024, 1, 1), last_date=datetime(2030, 12, 31))
    end_date_picker = ft.DatePicker(on_change=load_usage_data, first_date=datetime(2024, 1, 1), last_date=datetime(2030, 12, 31))

    input_card = ft.Text("0", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400)
    output_card = ft.Text("0", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
    total_card = ft.Text("0", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE_400)
    request_card = ft.Text("0", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE_400)
    fee_card = ft.Text("$0.00", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_700)

    range_text = ft.Text("", size=14, italic=True, color=ft.Colors.BLUE_GREY_400)

    def create_stat_card(title, control, icon):
        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.ListTile(
                        leading=ft.Icon(icon, size=24),
                        title=ft.Text(title, size=12, color=ft.Colors.BLUE_GREY_400),
                        subtitle=control,
                    )
                ]),
                padding=5,
                width=180,
            )
        )

    usage_table = ft.DataTable(
        columns=[
            ft.DataColumn(label=ft.Text(i18n.get("dashboard_col_model", "Model ID"), weight=ft.FontWeight.BOLD)),
            ft.DataColumn(label=ft.Text(i18n.get("dashboard_col_input", "Input"), weight=ft.FontWeight.BOLD)),
            ft.DataColumn(label=ft.Text(i18n.get("dashboard_col_output", "Output"), weight=ft.FontWeight.BOLD)),
            ft.DataColumn(label=ft.Text(i18n.get("dashboard_col_fee", "Est. Fee"), weight=ft.FontWeight.BOLD)),
            ft.DataColumn(label=ft.Text(i18n.get("dashboard_col_requests", "Reqs"), weight=ft.FontWeight.BOLD)),
            ft.DataColumn(label=ft.Text(i18n.get("dashboard_col_actions", "Actions"), weight=ft.FontWeight.BOLD)),
        ],
        rows=[]
    )

    calc_model_dropdown = ft.Dropdown(label=i18n.get("dashboard_calc_select_model", "Select Model"), width=300)
    calc_model_dropdown.on_change = on_calc_model_change

    unified_checkbox = ft.Checkbox(label=i18n.get("dashboard_calc_unified_price", "Unified Price"), value=True, 
                                   on_change=lambda e: (setattr(output_price_field, 'visible', not e.control.value), 
                                                        setattr(input_price_field, 'label', i18n.get("dashboard_calc_price_per_1m", "Price per 1M") if e.control.value else i18n.get("dashboard_calc_input_price", "Input Price")),
                                                        calculate_fee(),
                                                        page.update()))
    input_price_field = ft.TextField(label=i18n.get("dashboard_calc_price_per_1m", "Price per 1M"), value="0", width=200, on_change=calculate_fee, suffix=ft.Text("USD"))
    output_price_field = ft.TextField(label=i18n.get("dashboard_calc_output_price", "Output Price"), value="0", width=200, visible=False, on_change=calculate_fee, suffix=ft.Text("USD"))
    calc_result = ft.Text(f"{i18n.get('dashboard_calc_total_fee', 'Estimated Total Fee')}: $0.0000 USD", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700)

    view = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.DASHBOARD, size=30, color=ft.Colors.BLUE_400),
                ft.Text(i18n.get("dashboard_title", "Usage Dashboard"), size=24, weight=ft.FontWeight.BOLD),
                ft.VerticalDivider(),
                ft.TextButton(i18n.get("dashboard_filter_this_month", "This Month"), on_click=lambda _: apply_quick_filter(0)),
                ft.TextButton(i18n.get("dashboard_filter_3m", "3 Months"), on_click=lambda _: apply_quick_filter(90)),
                ft.TextButton(i18n.get("dashboard_filter_1y", "1 Year"), on_click=lambda _: apply_quick_filter(365)),
                ft.VerticalDivider(),
                ft.IconButton(ft.Icons.CALENDAR_MONTH, tooltip=i18n.get("dashboard_btn_start_date"), on_click=lambda _: page.show_dialog(start_date_picker)),
                ft.IconButton(ft.Icons.CALENDAR_MONTH, tooltip=i18n.get("dashboard_btn_end_date"), on_click=lambda _: page.show_dialog(end_date_picker)),
                ft.IconButton(ft.Icons.CLOSE, tooltip=i18n.get("dashboard_clear_filter_tooltip"), on_click=lambda _: (setattr(start_date_picker, 'value', None), setattr(end_date_picker, 'value', None), load_usage_data())),
                ft.IconButton(ft.Icons.REFRESH, on_click=load_usage_data, tooltip=i18n.get("home_history_btn_refresh_tooltip")),
                ft.IconButton(ft.Icons.AUTO_DELETE, icon_color=ft.Colors.RED_400, tooltip=i18n.get("dashboard_clear_old_tooltip", "Clear data before this month"), on_click=clear_old_data)
            ]),
            range_text,
            ft.Divider(),
            ft.Row([
                create_stat_card(i18n.get("dashboard_stat_input"), input_card, ft.Icons.ARROW_UPWARD),
                create_stat_card(i18n.get("dashboard_stat_output"), output_card, ft.Icons.ARROW_DOWNWARD),
                create_stat_card(i18n.get("dashboard_stat_total"), total_card, ft.Icons.FUNCTIONS),
                create_stat_card(i18n.get("dashboard_stat_requests"), request_card, ft.Icons.HUB),
                create_stat_card(i18n.get("dashboard_stat_fee", "Total Estimated Fee"), fee_card, ft.Icons.ATTACH_MONEY),
            ], wrap=True, spacing=10),
            ft.Divider(),
            ft.Tabs(
                selected_index=0,
                length=2,
                content=ft.Column(
                    expand=True,
                    controls=[
                        ft.TabBar(tabs=[ft.Tab(label=i18n.get("dashboard_tab_usage")), ft.Tab(label=i18n.get("dashboard_tab_calculator"))]),
                        ft.TabBarView(expand=True, controls=[
                            ft.Column([ft.Text(i18n.get("dashboard_usage_by_model"), size=18, weight=ft.FontWeight.BOLD), ft.Column([usage_table], scroll=ft.ScrollMode.AUTO, expand=True)], expand=True),
                            ft.Container(content=ft.Column([
                                ft.Text(i18n.get("dashboard_cost_estimator"), size=18, weight=ft.FontWeight.BOLD),
                                ft.Row([calc_model_dropdown, unified_checkbox]),
                                ft.Row([input_price_field, output_price_field]),
                                ft.Container(height=10),
                                calc_result,
                                ft.Text(i18n.get("dashboard_calc_note"), size=12, italic=True)
                            ], spacing=15), padding=20)
                        ])
                    ]
                ),
                expand=True
            )
        ], expand=True, spacing=10),
        padding=20,
        expand=True
    )

    load_usage_data()
    return view
