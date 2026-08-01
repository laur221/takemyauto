import base64
import flet as ft
import threading
import datetime


# ── Start GUI ───────────────────────────────────────────────────────────

def start_gui(bot_logic):
    def main(page: ft.Page):
        page.theme_mode = ft.ThemeMode.DARK
        page.title = "TakeMySkins Automator"
        page.padding = 20
        page.bgcolor = "#0D1117"
        page.scroll = ft.ScrollMode.ADAPTIVE

        # ── state ───────────────────────────────────────────────────────

        log_area = ft.ListView(expand=True, spacing=4, auto_scroll=True, height=260)

        qr_image = ft.Image(
            src="", width=200, height=200, visible=False, border_radius=10, fit="contain"
        )

        login_status = ft.Text("", size=13, color="#8B9BB4")
        runtime_status = ft.Text("Idle", size=13, color="#8B9BB4")

        progress = ft.ProgressBar(width=float("inf"), visible=False, color="#3B82F6", bgcolor="#161B22")

        stats_container = ft.Container()

        # ── helpers ─────────────────────────────────────────────────────

        def log(msg):
            now = datetime.datetime.now().strftime("%H:%M:%S")
            log_area.controls.append(
                ft.Text(f"[{now}] {msg}", size=12, color="#79C0FF", font_family="Consolas")
            )
            page.update()

        # ── QR callback ─────────────────────────────────────────────────

        def on_qr_bytes(qr_bytes):
            if isinstance(qr_bytes, dict):
                login_status.value = qr_bytes.get("error", "Eroare QR")
                login_status.color = "#F59E0B"
                btn_qr.disabled = False
                page.update()
                return
            if qr_bytes:
                try:
                    qr_image.src = None
                    qr_image.src_base64 = base64.b64encode(qr_bytes).decode("ascii")
                    qr_image.visible = True
                    login_status.value = "Scaneaza QR cu Steam Mobile"
                    login_status.color = "#22C55E"
                except Exception as e:
                    login_status.value = f"Eroare QR: {e}"
                    login_status.color = "#F87171"
            else:
                login_status.value = "QR indisponibil"
                login_status.color = "#F59E0B"
            btn_qr.disabled = False
            page.update()

        def on_qr_click(e):
            btn_qr.disabled = True
            login_status.value = "Se genereaza QR..."
            login_status.color = "#3B82F6"
            page.update()
            threading.Thread(target=bot_logic.get_steam_qr, args=(on_qr_bytes,), daemon=True).start()

        # ── buttons ─────────────────────────────────────────────────────

        btn_qr = ft.ElevatedButton(
            "Genereaza QR",
            on_click=on_qr_click,
            style=ft.ButtonStyle(color="#FFFFFF", bgcolor="#3B82F6"),
        )

        btn_login = ft.ElevatedButton(
            "Login manual",
            on_click=lambda _: bot_logic.run_check(is_headless=False, log_func=log),
            style=ft.ButtonStyle(color="#FFFFFF", bgcolor="#30363D"),
        )

        btn_start = ft.ElevatedButton(
            "Ruleaza verificarea",
            on_click=None,  # set below
            style=ft.ButtonStyle(color="#FFFFFF", bgcolor="#238636"),
        )

        def on_start(e):
            btn_start.disabled = True
            progress.visible = True
            runtime_status.value = "Ruleaza..."
            runtime_status.color = "#3B82F6"
            log("Pornesc verificarea automata...")
            page.update()

            def worker():
                result = bot_logic.run_check(is_headless=True, log_func=log)
                btn_start.disabled = False
                progress.visible = False
                runtime_status.value = "Idle"
                runtime_status.color = "#8B9BB4"
                log(f"Verificare terminata: {result}")
                refresh_stats()
                page.update()

            threading.Thread(target=worker, daemon=True).start()

        btn_start.on_click = on_start

        # ── stats ───────────────────────────────────────────────────────

        def build_stats():
            try:
                total, wins = bot_logic.db.get_stats()
            except Exception:
                total, wins = 0, []

            cards = ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Text("Rafle verificate", size=12, color="#8B9BB4"),
                        ft.Text(str(total), size=32, weight="bold", color="#E6EDF3"),
                    ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=16, border_radius=8, bgcolor="#161B22", expand=True,
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text("Castiguri", size=12, color="#8B9BB4"),
                        ft.Text(str(len(wins)), size=32, weight="bold", color="#22C55E"),
                    ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=16, border_radius=8, bgcolor="#161B22", expand=True,
                ),
            ], spacing=12)

            if wins:
                table = ft.DataTable(
                    columns=[
                        ft.DataColumn(ft.Text("Premiu", color="#E6EDF3")),
                        ft.DataColumn(ft.Text("Status", color="#E6EDF3")),
                        ft.DataColumn(ft.Text("Data", color="#E6EDF3")),
                    ],
                    rows=[
                        ft.DataRow(cells=[
                            ft.DataCell(ft.Text(str(w[3])[:40], color="#C9D1D9")),
                            ft.DataCell(ft.Text(str(w[2]), color="#C9D1D9")),
                            ft.DataCell(ft.Text(str(w[4])[:16], color="#8B9BB4")),
                        ]) for w in wins
                    ],
                )
                history = ft.Row([table], scroll=ft.ScrollMode.ALWAYS)
            else:
                history = ft.Container(
                    content=ft.Column([
                        ft.Text("Niciun castig inca.", size=14, color="#8B9BB4"),
                        ft.Text("Vor aparea automat aici dupa verificari.", size=12, color="#484F58"),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                    padding=30, border_radius=8, bgcolor="#161B22",
                )

            return ft.Column([cards, ft.Text("Istoric castiguri", size=15, weight="bold", color="#E6EDF3"), history], spacing=12)

        stats_container.content = build_stats()

        def refresh_stats(e=None):
            stats_container.content = build_stats()
            page.update()

        # ── card builder ─────────────────────────────────────────────────

        def card(title_text, subtitle_text, body, extra=None):
            header_row = ft.Row([
                ft.Column([
                    ft.Text(title_text, size=16, weight="bold", color="#E6EDF3"),
                    ft.Text(subtitle_text, size=13, color="#8B9BB4"),
                ], spacing=2, expand=True),
            ] + ([extra] if extra else []), vertical_alignment=ft.CrossAxisAlignment.CENTER)

            return ft.Container(
                content=ft.Column([header_row, body], spacing=14),
                padding=18,
                border_radius=10,
                bgcolor="#131820",
                border=ft.Border(
                    top=ft.BorderSide(width=1, color="#21262D"),
                    bottom=ft.BorderSide(width=1, color="#21262D"),
                    left=ft.BorderSide(width=1, color="#21262D"),
                    right=ft.BorderSide(width=1, color="#21262D"),
                ),
            )

        # ── log terminal ────────────────────────────────────────────────

        log_terminal = ft.Container(
            content=log_area,
            padding=12,
            border_radius=8,
            bgcolor="#0B0F14",
            border=ft.Border(
                top=ft.BorderSide(width=1, color="#1A3A5C"),
                bottom=ft.BorderSide(width=1, color="#1A3A5C"),
                left=ft.BorderSide(width=1, color="#1A3A5C"),
                right=ft.BorderSide(width=1, color="#1A3A5C"),
            ),
        )

        # ── layout ──────────────────────────────────────────────────────

        header = ft.Row([
            ft.Column([
                ft.Text("TakeMySkins Automator", size=26, weight="bold", color="#F0F6FC"),
                ft.Text("Dashboard automat de rafle", size=14, color="#8B9BB4"),
            ], spacing=2, expand=True),
            ft.Container(
                content=ft.Row([
                    ft.Container(width=8, height=8, border_radius=4, bgcolor="#3B82F6"),
                    runtime_status,
                ], spacing=8),
                padding=ft.Padding(left=14, top=8, right=14, bottom=8),
                border_radius=16,
                bgcolor="#161B22",
            ),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

        page.add(
            ft.Column([
                header,
                progress,
                ft.Row([
                    card(
                        "Autentificare Steam",
                        "Conecteaza-te prin QR pentru a participa la rafle.",
                        ft.Column([
                            ft.Row([btn_qr, btn_login], spacing=10),
                            qr_image,
                            login_status,
                        ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    ),
                    card(
                        "Control verificari",
                        "Ruleaza o verificare manuala sau actualizeaza statisticile.",
                        ft.Column([
                            btn_start,
                            ft.Text("Schedulerul ruleaza la fiecare 6 ore in fundal.",
                                    size=12, color="#484F58"),
                        ], spacing=10),
                        extra=ft.IconButton(
                            icon=ft.icons.REFRESH if hasattr(ft, "icons") else "refresh",
                            icon_color="#8B9BB4",
                            on_click=refresh_stats,
                        ),
                    ),
                ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.START),
                card(
                    "Statistici si castiguri",
                    "Rezultatele verificarilor automate si istoricul premiilor.",
                    stats_container,
                ),
                card(
                    "Console log",
                    "Iesire in timp real a verificarilor si erorilor.",
                    log_terminal,
                ),
                ft.Text("TakeMySkins Automator  v1.0  .  Render Free Tier",
                        size=11, color="#30363D", text_align=ft.TextAlign.CENTER),
            ], spacing=14, scroll=ft.ScrollMode.ADAPTIVE),
        )

    return main
