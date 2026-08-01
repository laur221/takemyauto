import flet as ft
import threading


def start_gui(bot_logic):
    def main(page: ft.Page):
        page.theme_mode = ft.ThemeMode.DARK
        page.title = "TakeMySkins Automator"
        page.padding = 0
        page.bgcolor = "#111827"
        page.window_min_width = 720
        page.window_min_height = 640

        def icon(name):
            icons_new = getattr(ft, "Icons", None)
            icons_old = getattr(ft, "icons", None)
            return (
                getattr(icons_new, name, None)
                or getattr(icons_old, name, None)
                or name.lower()
            )

        def panel(content, padding=18):
            return ft.Container(
                content=content,
                padding=padding,
                border_radius=8,
                bgcolor="#182033",
                border=ft.Border(
                    top=ft.BorderSide(width=1, color="#26334D"),
                    bottom=ft.BorderSide(width=1, color="#26334D"),
                    left=ft.BorderSide(width=1, color="#26334D"),
                    right=ft.BorderSide(width=1, color="#26334D"),
                ),
            )

        log_area = ft.ListView(
            expand=True,
            spacing=6,
            auto_scroll=True,
            height=310
        )

        qr_image = ft.Image(
            src="",
            width=220,
            height=220,
            visible=False,
            border_radius=8,
            fit="contain"
        )

        login_status = ft.Text(
            "Asteptare login Steam",
            size=13,
            color="#CBD5E1",
            weight="w500",
        )
        runtime_status = ft.Text("Idle", size=13, color="#CBD5E1", weight="w500")
        runtime_dot = ft.Container(width=8, height=8, border_radius=4, bgcolor="#94A3B8")

        def refresh_qr(qr_bytes):
            if qr_bytes:
                try:
                    qr_image.src = qr_bytes
                    qr_image.visible = True
                    login_status.value = "Scaneaza QR-ul cu Steam Mobile"
                    login_status.color = "#22C55E"
                except Exception as e:
                    login_status.value = f"Eroare QR: {str(e)}"
                    login_status.color = "#F87171"
            else:
                login_status.value = "Nu am putut genera QR-ul Steam."
                login_status.color = "#F59E0B"
            btn_qr.disabled = False
            page.update()

        def on_qr_request(e):
            btn_qr.disabled = True
            login_status.value = "Generez QR Steam..."
            login_status.color = "#93C5FD"
            page.update()
            threading.Thread(target=bot_logic.get_steam_qr, args=(refresh_qr,), daemon=True).start()

        btn_qr = ft.ElevatedButton(
            "Genereaza QR",
            icon=icon("QR_CODE_2"),
            on_click=on_qr_request,
            style=ft.ButtonStyle(color="#FFFFFF", bgcolor="#2563EB"),
        )

        def logger(message):
            import datetime
            now = datetime.datetime.now().strftime("%H:%M:%S")
            log_area.controls.append(
                ft.Text(
                    f"[{now}] {message}",
                    size=12,
                    color="#BFDBFE",
                    font_family="Consolas",
                )
            )
            page.update()

        def on_start_click(e):
            btn_start.disabled = True
            progress.visible = True
            runtime_status.value = "Ruleaza verificarea"
            runtime_status.color = "#93C5FD"
            runtime_dot.bgcolor = "#3B82F6"
            logger("Initializare motor de cautare...")
            page.update()

            def worker():
                status = bot_logic.run_check(is_headless=True, log_func=logger)
                btn_start.disabled = False
                progress.visible = False
                runtime_status.value = status
                runtime_status.color = "#CBD5E1"
                runtime_dot.bgcolor = "#94A3B8"
                logger(f"Sesiune terminata: {status}")
                page.update()

            threading.Thread(target=worker, daemon=True).start()

        title = ft.Text("TakeMySkins Automator", size=28, weight="bold", color="#F8FAFC")

        btn_login = ft.ElevatedButton(
            "Login Steam",
            icon=icon("LOGIN"),
            on_click=lambda _: bot_logic.run_check(is_headless=False, log_func=logger),
            style=ft.ButtonStyle(color="#FFFFFF", bgcolor="#334155")
        )

        btn_start = ft.ElevatedButton(
            "Porneste verificarea",
            icon=icon("PLAY_ARROW"),
            on_click=on_start_click,
            style=ft.ButtonStyle(color="#FFFFFF", bgcolor="#15803D")
        )

        progress = ft.ProgressBar(width=float("inf"), visible=False, color="#3B82F6", bgcolor="#1E293B")

        log_container = ft.Container(
            content=log_area,
            border=ft.Border(
                top=ft.BorderSide(width=1, color="#1E3A5F"),
                bottom=ft.BorderSide(width=1, color="#1E3A5F"),
                left=ft.BorderSide(width=1, color="#1E3A5F"),
                right=ft.BorderSide(width=1, color="#1E3A5F"),
            ),
            border_radius=8,
            padding=15,
            bgcolor="#0B1120"
        )

        def show_stats_page():
            try:
                total, wins = bot_logic.db.get_stats()
            except Exception:
                total, wins = 0, []

            total_box = ft.Container(
                content=ft.Column([
                    ft.Text("Rafle verificate", size=12, color="#94A3B8"),
                    ft.Text(str(total), size=30, weight="bold", color="#F8FAFC"),
                ], spacing=2),
                padding=16,
                border_radius=8,
                bgcolor="#0F172A",
                expand=True,
            )

            wins_box = ft.Container(
                content=ft.Column([
                    ft.Text("Castiguri", size=12, color="#94A3B8"),
                    ft.Text(str(len(wins)), size=30, weight="bold", color="#22C55E"),
                ], spacing=2),
                padding=16,
                border_radius=8,
                bgcolor="#0F172A",
                expand=True,
            )

            if wins:
                history = ft.DataTable(
                    heading_row_color="#0F172A",
                    data_row_color="#111827",
                    columns=[
                        ft.DataColumn(ft.Text("Premiu", color="#CBD5E1")),
                        ft.DataColumn(ft.Text("Status", color="#CBD5E1")),
                        ft.DataColumn(ft.Text("Data", color="#CBD5E1")),
                    ],
                    rows=[
                        ft.DataRow(cells=[
                            ft.DataCell(ft.Text(str(w[3]), color="#E2E8F0")),
                            ft.DataCell(ft.Text(str(w[2]), color="#E2E8F0")),
                            ft.DataCell(ft.Text(str(w[4]), color="#E2E8F0")),
                        ]) for w in wins
                    ]
                )
                history_content = ft.Row([history], scroll=ft.ScrollMode.ALWAYS)
            else:
                history_content = ft.Container(
                    content=ft.Column([
                        ft.Icon(icon("INBOX"), color="#64748B", size=32),
                        ft.Text("Nu exista castiguri salvate inca.", color="#CBD5E1", size=14),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    height=120,
                    border_radius=8,
                    bgcolor="#0F172A",
                )

            return ft.Column([
                ft.Row([total_box, wins_box], spacing=12),
                ft.Container(height=8),
                ft.Text("Istoric castiguri", size=16, weight="bold", color="#E2E8F0"),
                history_content,
            ], spacing=10, scroll=ft.ScrollMode.ADAPTIVE)

        stats_container = ft.Container(content=show_stats_page())

        def refresh_stats(e):
            stats_container.content = show_stats_page()
            page.update()

        def make_refresh_button():
            return ft.ElevatedButton(
                "Actualizeaza",
                on_click=refresh_stats,
                style=ft.ButtonStyle(color="#FFFFFF", bgcolor="#334155"),
            )

        page.add(
            ft.Container(
                padding=24,
                content=ft.Column([
                    ft.Row([
                        ft.Column([
                            title,
                            ft.Text(
                                "Dashboard pentru login, verificari si rezultate.",
                                size=14,
                                color="#94A3B8",
                            ),
                        ], spacing=4, expand=True),
                        ft.Container(
                            content=ft.Row([
                                runtime_dot,
                                runtime_status,
                            ], spacing=8),
                            padding=12,
                            border_radius=20,
                            bgcolor="#0F172A",
                        ),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    progress,
                    ft.Row([
                        panel(
                            ft.Column([
                                ft.Text("Login Steam", size=18, weight="bold", color="#F8FAFC"),
                                ft.Text("Genereaza QR sau deschide login manual.", size=13, color="#94A3B8"),
                                ft.Container(height=4),
                                ft.Row([btn_qr, btn_login], spacing=10),
                                qr_image,
                                login_status,
                            ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            padding=18,
                        ),
                        panel(
                            ft.Column([
                                ft.Row([
                                    ft.Column([
                                        ft.Text("Control bot", size=18, weight="bold", color="#F8FAFC"),
                                        ft.Text("Ruleaza o verificare manuala si actualizeaza datele.", size=13, color="#94A3B8"),
                                    ], spacing=4, expand=True),
                                    make_refresh_button(),
                                ]),
                                ft.Row([btn_start], spacing=10),
                                ft.Text(
                                    "Schedulerul ruleaza automat in fundal la intervalul configurat.",
                                    size=12,
                                    color="#64748B",
                                ),
                            ], spacing=14),
                            padding=18,
                        ),
                    ], spacing=16, vertical_alignment=ft.CrossAxisAlignment.START),
                    panel(
                        ft.Column([
                            ft.Row([
                                ft.Text("Statistici si castiguri", size=18, weight="bold", color="#F8FAFC", expand=True),
                                make_refresh_button(),
                            ]),
                            stats_container,
                        ], spacing=12),
                    ),
                    panel(
                        ft.Column([
                            ft.Text("Console log", size=18, weight="bold", color="#F8FAFC"),
                            log_container,
                        ], spacing=12),
                    ),
                ], spacing=16, scroll=ft.ScrollMode.ADAPTIVE),
            )
        )

    return main
