import flet as ft
import threading


def start_gui(bot_logic):
    def main(page: ft.Page):
        page.theme_mode = ft.ThemeMode.DARK
        page.title = "TakeMySkins Automator"
        page.padding = 25
        page.bgcolor = "#1a1c2e"

        # Zona de Log-uri
        log_area = ft.ListView(
            expand=True,
            spacing=5,
            auto_scroll=True,
            height=350
        )

        # Elementul care va afisa QR Code-ul
        qr_image = ft.Image(
            src="",
            width=250,
            height=250,
            visible=False,
            border_radius=15,
            fit="contain"
        )

        login_status = ft.Text("Asteptare solicitare login...", size=12)

        def refresh_qr(qr_bytes):
            if qr_bytes:
                try:
                    qr_image.src = qr_bytes
                    qr_image.visible = True
                    login_status.value = "✓ Scaneaza QR-ul cu aplicatia Steam Mobile"
                    login_status.color = "green400"
                except Exception as e:
                    login_status.value = f"Eroare QR: {str(e)}"
                    login_status.color = "red400"
            else:
                login_status.value = "⚠ Nu am putut genera QR-ul Steam."
                login_status.color = "orange400"
            btn_qr.disabled = False
            page.update()

        def on_qr_request(e):
            btn_qr.disabled = True
            login_status.value = "Initiez cerere QR..."
            page.update()
            threading.Thread(target=bot_logic.get_steam_qr, args=(refresh_qr,), daemon=True).start()

        btn_qr = ft.ElevatedButton("Genereaza QR Code Steam", on_click=on_qr_request)

        page.add(
            ft.Column([
                ft.Text("Login Securizat", size=20, weight="bold"),
                btn_qr,
                qr_image,
                login_status
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )

        def logger(message):
            import datetime
            now = datetime.datetime.now().strftime("%H:%M:%S")
            log_area.controls.append(
                ft.Text(f"[{now}] {message}", size=12, color="blue200", font_family="Consolas")
            )
            page.update()

        def on_start_click(e):
            btn_start.disabled = True
            progress.visible = True
            logger("Initializare motor de cautare...")
            page.update()

            def worker():
                status = bot_logic.run_check(is_headless=True, log_func=logger)
                btn_start.disabled = False
                progress.visible = False
                logger(f"Sesiune terminata: {status}")
                page.update()

            threading.Thread(target=worker, daemon=True).start()

        title = ft.Text("TAKEMYSKINS BOT", size=28, weight="bold", color="blue400")

        btn_login = ft.ElevatedButton(
            "Login Steam",
            icon="login",
            on_click=lambda _: bot_logic.run_check(is_headless=False, log_func=logger),
            style=ft.ButtonStyle(color="white", bgcolor="#2d325a")
        )

        btn_start = ft.ElevatedButton(
            "Pornire Automatizare",
            icon="play_arrow",
            on_click=on_start_click,
            style=ft.ButtonStyle(color="white", bgcolor="#1e3a8a")
        )

        progress = ft.ProgressBar(width=float("inf"), visible=False, color="blue400")

        log_container = ft.Container(
            content=log_area,
            border=ft.border.only(
                top=ft.BorderSide(1, "blue900"),
                bottom=ft.BorderSide(1, "blue900"),
                left=ft.BorderSide(1, "blue900"),
                right=ft.BorderSide(1, "blue900"),
            ),
            border_radius=15,
            padding=15,
            bgcolor="#0f111a"
        )

        def show_stats_page():
            try:
                total, wins = bot_logic.db.get_stats()
            except Exception:
                total, wins = 0, []

            table = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("Premiu")),
                    ft.DataColumn(ft.Text("Status")),
                    ft.DataColumn(ft.Text("Data")),
                ],
                rows=[
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(w[3]))),
                        ft.DataCell(ft.Text(str(w[2]))),
                        ft.DataCell(ft.Text(str(w[4]))),
                    ]) for w in wins
                ]
            )

            return ft.Column([
                ft.Text(f"Total Verificate: {total}", size=20, weight="bold"),
                ft.Divider(),
                ft.Text("Istoric Castiguri:", size=18, weight="bold", color="green400"),
                ft.Container(content=table, height=200, scroll=ft.ScrollMode.ALWAYS)
            ], scroll=ft.ScrollMode.ADAPTIVE)

        stats_container = ft.Container(content=show_stats_page())

        def refresh_stats(e):
            stats_container.content = show_stats_page()
            page.update()

        btn_refresh = ft.IconButton(icon="refresh", on_click=refresh_stats)

        page.add(
            ft.Column([
                title,
                ft.Text("Sistem automat de inscriere rafle", size=14, color="grey400"),
                ft.Divider(height=20, color="blue900"),
                ft.Row([btn_login, btn_start, btn_refresh], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
                ft.Divider(height=10, color="transparent"),
                progress,
                ft.Text("Statistici si Castiguri:", size=16, weight="bold", color="green200"),
                stats_container,
                ft.Divider(height=10, color="transparent"),
                ft.Text("Console Log:", size=16, weight="bold", color="blue200"),
                log_container,
                ft.Text("© 2024 Raffle Bot System", size=10, color="grey700", text_align=ft.TextAlign.CENTER)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, scroll=ft.ScrollMode.ADAPTIVE)
        )

    return main
