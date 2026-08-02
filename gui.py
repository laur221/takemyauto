import base64
import flet as ft
import threading
import datetime
import traceback


def start_gui(bot_logic):
    def main(page: ft.Page):
        # ── Setări generale ──────────────────────────────────────────────
        page.title = "TakeMySkins Automator"
        page.theme_mode = ft.ThemeMode.DARK
        page.bgcolor = "#0A0E17"
        page.padding = 10
        page.scroll = ft.ScrollMode.ADAPTIVE

        # ── Elemente UI (definite aici pentru a fi accesibile peste tot) ──
        log_area = ft.ListView(expand=True, spacing=2, auto_scroll=True, height=180)
        status_text = ft.Text("", size=13, color="#8B949E")
        qr_image = ft.Image(src="", width=180, height=180, visible=False, fit="contain")
        qr_status = ft.Text("", size=13, color="#8B949E")
        progress = ft.ProgressBar(width=float("inf"), visible=False, color="#3B82F6")
        runtime_dot = ft.Container(width=8, height=8, border_radius=4, bgcolor="#484F58")
        runtime_text = ft.Text("Idle", size=13, color="#8B949E")

        # ── Funcții de log și update ────────────────────────────────────
        def log(msg):
            now = datetime.datetime.now().strftime("%H:%M:%S")
            log_area.controls.append(ft.Text(f"[{now}] {msg}", size=11, color="#79C0FF"))
            page.update()

        def update_status(msg, color="#58A6FF"):
            status_text.value = msg
            status_text.color = color
            page.update()

        # ── QR ──────────────────────────────────────────────────────────
        def on_qr_bytes(data):
            if isinstance(data, dict):
                qr_status.value = data.get("error", "Eroare QR")
                qr_status.color = "#D29922"
                page.update()
                return
            if data:
                try:
                    b64 = base64.b64encode(data).decode("utf-8")
                    qr_image.src = f"data:image/png;base64,{b64}"
                    qr_image.visible = True
                    qr_status.value = "Scanează codul QR cu Steam Mobile"
                    qr_status.color = "#3FB950"
                except Exception as e:
                    qr_status.value = f"Eroare: {e}"
                    qr_status.color = "#F85149"
            else:
                qr_status.value = "QR indisponibil - încearcă din nou"
                qr_status.color = "#D29922"
            page.update()

        def start_qr(e):
            qr_status.value = "Se generează QR..."
            qr_status.color = "#58A6FF"
            page.update()
            threading.Thread(target=bot_logic.get_steam_qr, args=(on_qr_bytes,), daemon=True).start()

        btn_qr = ft.ElevatedButton("Generează QR Steam", on_click=start_qr,
                                   style=ft.ButtonStyle(bgcolor="#3B82F6", color="white"))

        # ── Butoane Steam ──────────────────────────────────────────────
        async def open_steam(e):
            await page.launch_url("https://store.steampowered.com/login/")
            update_status("✅ Tab Steam deschis", "#3FB950")

        async def open_tms(e):
            await page.launch_url("https://takemyskins.com/")
            update_status("✅ Tab TakeMySkins deschis", "#3FB950")

        btn_steam = ft.ElevatedButton("Deschide Steam Login", on_click=open_steam,
                                      style=ft.ButtonStyle(bgcolor="#1F6FEB", color="white"))
        btn_tms = ft.ElevatedButton("Deschide TakeMySkins", on_click=open_tms,
                                    style=ft.ButtonStyle(bgcolor="#238636", color="white"))

        # ── Verificare manuală ──────────────────────────────────────────
        def run_check(e):
            progress.visible = True
            runtime_dot.bgcolor = "#58A6FF"
            runtime_text.value = "Rulează..."
            page.update()

            def worker():
                try:
                    result = bot_logic.run_check(is_headless=True, log_func=log)
                    update_status(f"✅ Verificare terminată: {result}", "#3FB950")
                except Exception as ex:
                    update_status(f"❌ Eroare: {ex}", "#F85149")
                    log(traceback.format_exc())
                finally:
                    progress.visible = False
                    runtime_dot.bgcolor = "#484F58"
                    runtime_text.value = "Idle"
                    page.update()

            threading.Thread(target=worker, daemon=True).start()

        btn_check = ft.ElevatedButton("Rulează verificarea", on_click=run_check,
                                      style=ft.ButtonStyle(bgcolor="#238636", color="white"))

        # ── Statistici (safe) ──────────────────────────────────────────
        def build_stats():
            try:
                total, wins = bot_logic.db.get_stats()
            except Exception as e:
                return ft.Text(f"⚠️ Nu s-au putut încărca statisticile: {e}",
                               color="#F85149", size=13)

            cards = ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Text("Rafle verificate", size=11, color="#8B949E"),
                        ft.Text(str(total), size=24, weight="bold", color="#E6EDF3"),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=10, bgcolor="#161B22", border_radius=8, expand=True,
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text("Castiguri", size=11, color="#8B949E"),
import base64
import flet as ft
import threading
import datetime
import traceback


def start_gui(bot_logic):
    def main(page: ft.Page):
        # ── Setări generale ──────────────────────────────────────────────
        page.title = "TakeMySkins Automator"
        page.theme_mode = ft.ThemeMode.DARK
        page.bgcolor = "#0A0E17"
        page.padding = 10
        page.scroll = ft.ScrollMode.ADAPTIVE

        # ── Elemente UI ──────────────────────────────────────────────────
        log_area = ft.ListView(expand=True, spacing=2, auto_scroll=True, height=180)
        status_text = ft.Text("", size=13, color="#8B949E")
        qr_image = ft.Image(src="", width=180, height=180, visible=False, fit="contain")
        qr_status = ft.Text("", size=13, color="#8B949E")
        progress = ft.ProgressBar(width=float("inf"), visible=False, color="#3B82F6")
        runtime_dot = ft.Container(width=8, height=8, border_radius=4, bgcolor="#484F58")
        runtime_text = ft.Text("Idle", size=13, color="#8B949E")

        # ── Funcții de log și update ────────────────────────────────────
        def log(msg):
            now = datetime.datetime.now().strftime("%H:%M:%S")
            log_area.controls.append(ft.Text(f"[{now}] {msg}", size=11, color="#79C0FF"))
            page.update()

        def update_status(msg, color="#58A6FF"):
            status_text.value = msg
            status_text.color = color
            page.update()

        # ── QR ──────────────────────────────────────────────────────────
        def on_qr_bytes(data):
            if isinstance(data, dict):
                qr_status.value = data.get("error", "Eroare QR")
                qr_status.color = "#D29922"
                page.update()
                return
            if data:
                try:
                    b64 = base64.b64encode(data).decode("utf-8")
                    qr_image.src = f"data:image/png;base64,{b64}"
                    qr_image.visible = True
                    qr_status.value = "Scanează codul QR cu Steam Mobile"
                    qr_status.color = "#3FB950"
                except Exception as e:
                    qr_status.value = f"Eroare: {e}"
                    qr_status.color = "#F85149"
            else:
                qr_status.value = "QR indisponibil - încearcă din nou"
                qr_status.color = "#D29922"
            page.update()

        def start_qr(e):
            qr_status.value = "Se generează QR..."
            qr_status.color = "#58A6FF"
            page.update()
            threading.Thread(target=bot_logic.get_steam_qr, args=(on_qr_bytes,), daemon=True).start()

        btn_qr = ft.ElevatedButton("Generează QR Steam", on_click=start_qr,
                                   style=ft.ButtonStyle(bgcolor="#3B82F6", color="white"))

        # ── Butoane Steam ──────────────────────────────────────────────
        async def open_steam(e):
            await page.launch_url("https://store.steampowered.com/login/")
            update_status("✅ Tab Steam deschis", "#3FB950")

        async def open_tms(e):
            await page.launch_url("https://takemyskins.com/")
            update_status("✅ Tab TakeMySkins deschis", "#3FB950")

        btn_steam = ft.ElevatedButton("Deschide Steam Login", on_click=open_steam,
                                      style=ft.ButtonStyle(bgcolor="#1F6FEB", color="white"))
        btn_tms = ft.ElevatedButton("Deschide TakeMySkins", on_click=open_tms,
                                    style=ft.ButtonStyle(bgcolor="#238636", color="white"))

        # ── Verificare manuală ──────────────────────────────────────────
        def run_check(e):
            progress.visible = True
            runtime_dot.bgcolor = "#58A6FF"
            runtime_text.value = "Rulează..."
            page.update()

            def worker():
                try:
                    result = bot_logic.run_check(is_headless=True, log_func=log)
                    update_status(f"✅ Verificare terminată: {result}", "#3FB950")
                except Exception as ex:
                    update_status(f"❌ Eroare: {ex}", "#F85149")
                    log(traceback.format_exc())
                finally:
                    progress.visible = False
                    runtime_dot.bgcolor = "#484F58"
                    runtime_text.value = "Idle"
                    page.update()

            threading.Thread(target=worker, daemon=True).start()

        btn_check = ft.ElevatedButton("Rulează verificarea", on_click=run_check,
                                      style=ft.ButtonStyle(bgcolor="#238636", color="white"))

        # ── Statistici (safe) ──────────────────────────────────────────
        def build_stats():
            try:
                total, wins = bot_logic.db.get_stats()
            except Exception as e:
                return ft.Text(f"⚠️ Nu s-au putut încărca statisticile: {e}",
                               color="#F85149", size=13)

            cards = ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Text("Rafle verificate", size=11, color="#8B949E"),
                        ft.Text(str(total), size=24, weight="bold", color="#E6EDF3"),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=10, bgcolor="#161B22", border_radius=8, expand=True,
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text("Castiguri", size=11, color="#8B949E"),
                        ft.Text(str(len(wins)), size=24, weight="bold", color="#3FB950"),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=10, bgcolor="#161B22", border_radius=8, expand=True,
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text("Ultima rulare", size=11, color="#8B949E"),
                        ft.Text(datetime.datetime.now().strftime("%H:%M") if total > 0 else "-",
                                size=24, weight="bold", color="#8B949E"),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=10, bgcolor="#161B22", border_radius=8, expand=True,
                ),
            ], spacing=10)

            if wins:
                rows = []
                for w in wins[:20]:
                    rows.append(ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(w[3])[:30] if w[3] else "-", size=12)),
                        ft.DataCell(ft.Text(str(w[2]) if w[2] else "-", size=12)),
                        ft.DataCell(ft.Text(str(w[4])[:16] if w[4] else "-", size=11, color="#8B949E")),
                    ]))
                history = ft.Column([
                    ft.Text("Istoric", size=13, weight="bold", color="#E6EDF3"),
                    ft.DataTable(
                        columns=[
                            ft.DataColumn(ft.Text("Premiu", color="#8B949E")),
                            ft.DataColumn(ft.Text("Status", color="#8B949E")),
                            ft.DataColumn(ft.Text("Data", color="#8B949E")),
                        ],
                        rows=rows,
                        column_spacing=20,
                        horizontal_lines=ft.BorderSide(1, "#21262D"),
                    ),
                ], spacing=6)
                return ft.Column([cards, history], spacing=16)
            else:
                return ft.Column([
                    cards,
                    ft.Text("Niciun câștig încă. Ele vor apărea automat aici.",
                            size=12, color="#484F58", italic=True),
                ], spacing=16)

        stats_area = ft.Container(content=build_stats())

        def refresh_stats(e=None):
            stats_area.content = build_stats()
            page.update()

        # ── Card generic ──────────────────────────────────────────────
        def card(title, subtitle, body, right=None):
            return ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Column([
                            ft.Text(title, size=15, weight="bold", color="#F0F6FC"),
                            ft.Text(subtitle, size=12, color="#8B949E"),
                        ], spacing=1, expand=True),
                        right if right else ft.Container(),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    body,
                ], spacing=10),
                padding=14, border_radius=10, bgcolor="#131820",
                border=ft.Border(
                    top=ft.BorderSide(1, "#21262D"),
                    bottom=ft.BorderSide(1, "#21262D"),
                    left=ft.BorderSide(1, "#21262D"),
                    right=ft.BorderSide(1, "#21262D"),
                ),
            )

        # ── Layout principal ──────────────────────────────────────────
        log_box = ft.Container(
            content=log_area,
            padding=8,
            bgcolor="#0B0F14",
            border_radius=6,
            height=200,
            border=ft.Border.all(1, "#1A3A5C"),
        )

        header = ft.Row([
            ft.Text("TakeMySkins Automator", size=20, weight="bold", color="#F0F6FC"),
            ft.Container(
                content=ft.Row([runtime_dot, runtime_text], spacing=6),
                padding=ft.Padding(left=10, top=4, right=10, bottom=4),
                bgcolor="#161B22", border_radius=20,
            ),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        # ----- IconButton-uri corectate (folosesc ft.icons.REFRESH) -----
        refresh_btn = ft.IconButton(
            icon=ft.icons.REFRESH,
            on_click=refresh_stats,
            icon_color="#8B949E"
        )

        page.add(
            ft.Container(
                padding=ft.Padding(left=10, top=10, right=10, bottom=10),
                content=ft.Column([
                    header,
                    progress,
                    ft.Row([
                        card(
                            "🔐 Login Steam",
                            "Conectează-te prin QR sau deschide manual",
                            ft.Column([
                                ft.Row([btn_qr, btn_steam, btn_tms], wrap=True, spacing=8),
                                qr_image,
                                qr_status,
                            ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        ),
                        card(
                            "🚀 Verificare",
                            "Rulează manual sau așteaptă programarea",
                            ft.Column([
                                btn_check,
                                status_text,
                                ft.Text("Scheduler: la fiecare 6 ore", size=11, color="#484F58"),
                            ], spacing=6),
                            right=refresh_btn,  # <--- butonul corectat
                        ),
                    ], spacing=10, wrap=True),
                    card(
                        "📊 Statistici",
                        "Rezultatele și istoricul",
                        stats_area,
                        right=refresh_btn,  # <--- butonul corectat
                    ),
                    card(
                        "📋 Log",
                        "Ieșirea în timp real",
                        log_box,
                    ),
                    ft.Text("v1.0 · Render Free", size=10, color="#21262D", text_align=ft.TextAlign.CENTER),
                ], spacing=12, scroll=ft.ScrollMode.ADAPTIVE),
            )
        )

    return mai Statistici",
                        "Rezultatele și istoricul",
                        stats_area,
                        right=ft.IconButton(icon="refresh", on_click=refresh_stats, icon_color="#8B949E"),
                    ),
                    card(
                        "📋 Log",
                        "Ieșirea în timp real",
                        log_box,
                    ),
                    ft.Text("v1.0 · Render Free", size=10, color="#21262D", text_align=ft.TextAlign.CENTER),
                ], spacing=12, scroll=ft.ScrollMode.ADAPTIVE),
            )
        )

    return main
