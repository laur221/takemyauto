import base64
import flet as ft
import threading
import datetime


def start_gui(bot_logic):
    def main(page: ft.Page):
        page.theme_mode = ft.ThemeMode.DARK
        page.title = "TakeMySkins Automator"
        page.padding = 0
        page.bgcolor = "#0A0E17"
        page.scroll = ft.ScrollMode.ADAPTIVE

        # ── state ───────────────────────────────────────────────────────
        log_area = ft.ListView(expand=True, spacing=3, auto_scroll=True, height=240)
        stats_body = ft.Container()

        qr_image = ft.Image(
            src="", width=200, height=200, visible=False,
            border_radius=10, fit="contain",
        )
        qr_status = ft.Text("", size=13, color="#8B949E")
        steam_status = ft.Text("", size=13, color="#8B949E")
        check_status = ft.Text("", size=13, color="#8B949E")

        runtime_dot = ft.Container(width=8, height=8, border_radius=4, bgcolor="#484F58")
        runtime_text = ft.Text("Idle", size=13, color="#8B949E")

        progress = ft.ProgressBar(
            width=float("inf"), visible=False, color="#3B82F6", bgcolor="#161B22"
        )

        def log(msg):
            now = datetime.datetime.now().strftime("%H:%M:%S")
            log_area.controls.append(
                ft.Text(f"[{now}] {msg}", size=12, color="#79C0FF", font_family="Consolas")
            )
            page.update()

        # ── QR ──────────────────────────────────────────────────────────
        def on_qr_bytes(qr_bytes):
            if isinstance(qr_bytes, dict):
                qr_status.value = qr_bytes.get("error", "Eroare QR")
                qr_status.color = "#D29922"
                btn_qr.disabled = False
                page.update()
                return
            if qr_bytes:
                try:
                    b64_str = base64.b64encode(qr_bytes).decode("utf-8")
                    qr_image.src = f"data:image/png;base64,{b64_str}"
                    qr_image.src_base64 = b64_str
                    qr_image.visible = True
                    qr_status.value = "Scaneaza codul QR cu aplicatia Steam Mobile"
                    qr_status.color = "#3FB950"
                except Exception as e:
                    qr_status.value = f"Eroare afisare QR: {e}"
                    qr_status.color = "#F85149"
            else:
                qr_status.value = "QR indisponibil - incearca din nou"
                qr_status.color = "#D29922"
            btn_qr.disabled = False
            page.update()

        def start_qr(e):
            btn_qr.disabled = True
            qr_status.value = "Am apasat QR - pornesc Selenium..."
            qr_status.color = "#58A6FF"
            log("BUTON: QR Steam apasat - pornesc SeleniumBase pentru captura QR")
            page.update()
            threading.Thread(target=bot_logic.get_steam_qr, args=(on_qr_bytes,), daemon=True).start()

        btn_qr = ft.ElevatedButton(
            "Genereaza QR Steam",
            on_click=start_qr,
            style=ft.ButtonStyle(color="#FFFFFF", bgcolor="#3B82F6"),
        )

        # ── steam login in user's browser ───────────────────────────────
        # ✅ FIX: handler asincron cu await
        async def on_steam_click(e):
            steam_status.value = "Deschid Steam Login intr-un tab nou..."
            steam_status.color = "#3FB950"
            log("BUTON: Steam Login apasat - deschidere tab nou")
            await page.launch_url("https://store.steampowered.com/login/")
            page.update()

        steam_btn = ft.ElevatedButton(
            "Deschide Steam Login",
            on_click=on_steam_click,
            style=ft.ButtonStyle(color="#FFFFFF", bgcolor="#1F6FEB"),
        )

        # ✅ FIX: handler asincron cu await
        async def on_tms_click(e):
            log("BUTON: Deschide TakeMySkins apasat")
            await page.launch_url("https://takemyskins.com/")
            page.update()

        tms_btn = ft.ElevatedButton(
            "Deschide TakeMySkins",
            on_click=on_tms_click,
            style=ft.ButtonStyle(color="#FFFFFF", bgcolor="#238636"),
        )

        # ── start check ─────────────────────────────────────────────────
        def do_check(e):
            btn_check.disabled = True
            progress.visible = True
            runtime_dot.bgcolor = "#58A6FF"
            runtime_text.value = "Ruleaza..."
            runtime_text.color = "#58A6FF"
            check_status.value = "Verificare in curs..."
            check_status.color = "#58A6FF"
            log("BUTON: Verificare apasat - pornesc SeleniumBase headless")
            page.update()

            def worker():
                result = bot_logic.run_check(is_headless=True, log_func=log)
                btn_check.disabled = False
                progress.visible = False
                runtime_dot.bgcolor = "#484F58"
                runtime_text.value = "Idle"
                runtime_text.color = "#8B949E"
                log(f"Verificare terminata: {result}")
                refresh_stats()
                page.update()

            threading.Thread(target=worker, daemon=True).start()

        btn_check = ft.ElevatedButton(
            "Ruleaza verificarea",
            on_click=do_check,
            style=ft.ButtonStyle(color="#FFFFFF", bgcolor="#238636"),
        )

        # ── stats ───────────────────────────────────────────────────────
        def build_stats():
            try:
                total, wins = bot_logic.db.get_stats()
            except Exception:
                total, wins = 0, []

            stat_cards = ft.Row([
                _stat_card("Rafle verificate", str(total), "#E6EDF3"),
                _stat_card("Castiguri", str(len(wins)), "#3FB950"),
                _stat_card("Ultima rulare",
                           datetime.datetime.now().strftime("%H:%M") if total > 0 else "-",
                           "#8B949E"),
            ], spacing=12)

            if wins:
                rows = []
                for w in wins:
                    rows.append(ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(w[3])[:35] if w[3] else "-", color="#C9D1D9")),
                        ft.DataCell(ft.Text(str(w[2]) if w[2] else "-", color="#C9D1D9")),
                        ft.DataCell(ft.Text(str(w[4])[:16] if w[4] else "-", color="#8B949E", size=12)),
                    ]))
                history = ft.Column([
                    ft.Text("Istoric", size=14, weight="bold", color="#E6EDF3"),
                    ft.Row([
                        ft.DataTable(
                            columns=[
                                ft.DataColumn(ft.Text("Premiu", color="#E6EDF3")),
                                ft.DataColumn(ft.Text("Status", color="#E6EDF3")),
                                ft.DataColumn(ft.Text("Data", color="#E6EDF3")),
                            ],
                            rows=rows,
                        ),
                    ], scroll=ft.ScrollMode.ALWAYS),
                ], spacing=8)
            else:
                history = ft.Container(
                    content=ft.Text("Niciun castig inca. Vor aparea automat aici.",
                                    size=13, color="#484F58"),
                    padding=ft.Padding(left=0, top=20, right=0, bottom=20),
                )

            return ft.Column([stat_cards, history], spacing=14)

        def _stat_card(label, value, color):
            return ft.Container(
                content=ft.Column([
                    ft.Text(label, size=11, color="#8B949E", weight="w600"),
                    ft.Text(value, size=28, weight="bold", color=color),
                ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding(left=16, top=12, right=16, bottom=12),
                border_radius=8, bgcolor="#161B22", expand=True,
            )

        stats_body.content = build_stats()

        def refresh_stats(e=None):
            stats_body.content = build_stats()
            page.update()

        # ── card builder ─────────────────────────────────────────────────
        def _card(title, sub, body, right=None):
            return ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Column([
                            ft.Text(title, size=16, weight="bold", color="#F0F6FC"),
                            ft.Text(sub, size=13, color="#8B949E"),
                        ], spacing=2, expand=True),
                    ] + ([right] if right else []), vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    body,
                ], spacing=12),
                padding=18, border_radius=10, bgcolor="#131820",
                border=ft.Border(
                    top=ft.BorderSide(width=1, color="#21262D"),
                    bottom=ft.BorderSide(width=1, color="#21262D"),
                    left=ft.BorderSide(width=1, color="#21262D"),
                    right=ft.BorderSide(width=1, color="#21262D"),
                ),
            )

        # ── log terminal ────────────────────────────────────────────────
        log_box = ft.Container(
            content=log_area, padding=12, border_radius=8, bgcolor="#0B0F14",
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
                ft.Text("TakeMySkins Automator", size=24, weight="bold", color="#F0F6FC"),
                ft.Text("Automatizare rafle  .  takemyskins.com", size=13, color="#484F58"),
            ], spacing=2, expand=True),
            ft.Container(
                content=ft.Row([runtime_dot, runtime_text], spacing=8),
                padding=ft.Padding(left=14, top=8, right=14, bottom=8),
                border_radius=16, bgcolor="#161B22",
            ),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

        refresh_btn = ft.IconButton(
            icon="refresh", icon_color="#8B949E", on_click=refresh_stats,
        )

        page.add(
            ft.Container(
                padding=ft.Padding(left=24, top=20, right=24, bottom=20),
                content=ft.Column([
                    header,
                    progress,
                    ft.Row([
                        _card(
                            "Login Steam",
                            "Conecteaza-te prin QR sau deschide Steam in browser.",
                            ft.Column([
                                ft.Row([btn_qr, steam_btn, tms_btn], spacing=10, wrap=True),
                                steam_status,
                                qr_image,
                                qr_status,
                            ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        ),
                        _card(
                            "Verificare rafle",
                            "Ruleaza o verificare manuala si vezi rezultatele.",
                            ft.Column([
                                btn_check,
                                check_status,
                                ft.Text(
                                    "Schedulerul ruleaza automat la fiecare 6 ore.",
                                    size=12, color="#484F58",
                                ),
                            ], spacing=10),
                            right=refresh_btn,
                        ),
                    ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.START),
                    _card(
                        "Statistici si castiguri",
                        "Rezultatele verificarilor si istoricul premiilor.",
                        stats_body,
                        right=refresh_btn,
                    ),
                    _card(
                        "Console log",
                        "Iesirea in timp real a verificarilor.",
                        log_box,
                    ),
                    ft.Text("v1.0  .  Render Free  .  $0/mo",
                            size=11, color="#21262D", text_align=ft.TextAlign.CENTER),
                ], spacing=14, scroll=ft.ScrollMode.ADAPTIVE),
            )
        )

    return main
