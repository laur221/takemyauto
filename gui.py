import base64
import flet as ft
import threading
import datetime


# ── Design tokens (Flet 0.86 compatible) ────────────────────────────────

BG_BASE      = "#0A0E17"   # fundal principal
BG_CARD      = "#131929"   # carduri
BG_ELEVATED  = "#1A2240"   # elemente ridicate
BG_TERMINAL  = "#090D14"   # consola log

BORDER       = "#1E2D4A"   # borduri
BORDER_FOCUS = "#2D4A7A"   # borduri active

TEXT_PRIMARY   = "#F1F5F9"
TEXT_SECONDARY = "#94A3B8"
TEXT_MUTED     = "#64748B"

ACCENT_BLUE   = "#3B82F6"
ACCENT_GREEN  = "#22C55E"
ACCENT_AMBER  = "#F59E0B"
ACCENT_RED    = "#EF4444"
ACCENT_INDIGO = "#6366F1"

STATUS_IDLE    = "#64748B"
STATUS_RUNNING = "#3B82F6"
STATUS_SUCCESS = "#22C55E"
STATUS_ERROR   = "#EF4444"

RADIUS = 10


# ── helpers ─────────────────────────────────────────────────────────────

def _icon(name):
    """Safe icon lookup for Flet 0.86."""
    ns = getattr(ft, "icons", None) or getattr(ft, "Icons", None)
    if ns:
        val = getattr(ns, name, None)
        if val:
            return val
    return name.lower()


def _build_card(content, padding=20):
    return ft.Container(
        content=content,
        padding=padding,
        border_radius=RADIUS,
        bgcolor=BG_CARD,
        border=ft.Border(
            top=ft.BorderSide(width=1, color=BORDER),
            bottom=ft.BorderSide(width=1, color=BORDER),
            left=ft.BorderSide(width=1, color=BORDER),
            right=ft.BorderSide(width=1, color=BORDER),
        ),
    )


def _section_header(title, subtitle=""):
    return ft.Column([
        ft.Text(title, size=17, weight="bold", color=TEXT_PRIMARY),
        ft.Text(subtitle, size=13, color=TEXT_SECONDARY),
    ], spacing=2)


def _status_badge(color, text):
    return ft.Row([
        ft.Container(width=8, height=8, border_radius=4, bgcolor=color),
        ft.Text(text, size=13, color=TEXT_SECONDARY, weight="w500"),
    ], spacing=8)


def _compact_stat(label, value, accent=TEXT_PRIMARY):
    return ft.Container(
        content=ft.Column([
            ft.Text(label, size=11, color=TEXT_MUTED, weight="w600"),
            ft.Text(str(value), size=26, weight="bold", color=accent),
        ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding(left=16, top=12, right=16, bottom=12),
        border_radius=RADIUS,
        bgcolor=BG_ELEVATED,
    )


# ── main ────────────────────────────────────────────────────────────────

def start_gui(bot_logic):
    def main(page: ft.Page):
        page.theme_mode = ft.ThemeMode.DARK
        page.title = "TakeMySkins Automator"
        page.padding   = 0
        page.bgcolor   = BG_BASE
        page.window_min_width  = 780
        page.window_min_height = 720

        # ── state ───────────────────────────────────────────────────────

        log_area = ft.ListView(expand=True, spacing=4, auto_scroll=True, height=280)

        qr_image = ft.Image(
            src="", width=210, height=210, visible=False, border_radius=8, fit="contain"
        )

        login_status = ft.Text("Asteapta login", size=13, color=TEXT_SECONDARY)
        runtime_status_text = ft.Text("Idle", size=13, color=TEXT_SECONDARY)
        runtime_dot = ft.Container(width=8, height=8, border_radius=4, bgcolor=STATUS_IDLE)

        # ── log helpers ─────────────────────────────────────────────────

        def log(msg):
            now = datetime.datetime.now().strftime("%H:%M:%S")
            log_area.controls.append(
                ft.Text(f"[{now}] {msg}", size=12, color="#93B4E8", font_family="Consolas")
            )
            page.update()

        # ── QR callback ─────────────────────────────────────────────────

        def on_qr_bytes(qr_bytes):
            if isinstance(qr_bytes, dict):
                login_status.value = qr_bytes.get("error", "Eroare QR")
                login_status.color = ACCENT_AMBER
                qr_image.visible = False
                btn_qr.disabled = False
                page.update()
                return
            if qr_bytes:
                try:
                    qr_image.src = None
                    qr_image.src_base64 = base64.b64encode(qr_bytes).decode()
                    qr_image.visible = True
                    login_status.value = "Scaneaza QR cu Steam Mobile"
                    login_status.color = ACCENT_GREEN
                except Exception as e:
                    login_status.value = f"Eroare: {e}"
                    login_status.color = ACCENT_RED
            else:
                qr_image.visible = False
                login_status.value = "QR indisponibil"
                login_status.color = ACCENT_AMBER
            btn_qr.disabled = False
            page.update()

        def on_qr_click(e):
            btn_qr.disabled = True
            login_status.value = "Se genereaza QR-ul..."
            login_status.color = ACCENT_BLUE
            page.update()
            threading.Thread(target=bot_logic.get_steam_qr, args=(on_qr_bytes,), daemon=True).start()

        btn_qr = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(_icon("QR_CODE_2"), size=18, color="#FFFFFF"),
                ft.Text("Genereaza QR", size=14, color="#FFFFFF", weight="w600"),
            ], spacing=8),
            on_click=on_qr_click,
            style=ft.ButtonStyle(bgcolor=ACCENT_BLUE, shape=ft.RoundedRectangleBorder(radius=8)),
        )

        # ── start check ─────────────────────────────────────────────────

        progress = ft.ProgressBar(width=float("inf"), visible=False, color=ACCENT_BLUE, bgcolor=BG_ELEVATED)

        def on_start(e):
            btn_start.disabled = True
            progress.visible = True
            runtime_dot.bgcolor = STATUS_RUNNING
            runtime_status_text.value = "Ruleaza..."
            runtime_status_text.color = ACCENT_BLUE
            log("Pornesc verificarea automata...")
            page.update()

            def worker():
                result = bot_logic.run_check(is_headless=True, log_func=log)
                btn_start.disabled = False
                progress.visible = False
                runtime_dot.bgcolor = STATUS_IDLE
                runtime_status_text.value = "Idle"
                runtime_status_text.color = TEXT_SECONDARY
                log(f"Verificare terminata: {result}")
                page.update()

            threading.Thread(target=worker, daemon=True).start()

        btn_start = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(_icon("PLAY_ARROW"), size=18, color="#FFFFFF"),
                ft.Text("Ruleaza verificarea", size=14, color="#FFFFFF", weight="w600"),
            ], spacing=8),
            on_click=on_start,
            style=ft.ButtonStyle(bgcolor=ACCENT_GREEN, shape=ft.RoundedRectangleBorder(radius=8)),
        )

        btn_manual = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(_icon("LOGIN"), size=18, color="#FFFFFF"),
                ft.Text("Login manual", size=14, color="#FFFFFF", weight="w600"),
            ], spacing=8),
            on_click=lambda _: bot_logic.run_check(is_headless=False, log_func=log),
            style=ft.ButtonStyle(bgcolor="#334155", shape=ft.RoundedRectangleBorder(radius=8)),
        )

        # ── stats panel ─────────────────────────────────────────────────

        stats_container = ft.Container()

        def build_stats():
            try:
                total, wins = bot_logic.db.get_stats()
            except Exception:
                total, wins = 0, []

            if wins:
                table = ft.DataTable(
                    heading_row_color=BG_ELEVATED,
                    data_row_color=BG_CARD,
                    heading_text_style=ft.TextStyle(size=12, color=TEXT_SECONDARY, weight="w600"),
                    data_text_style=ft.TextStyle(size=13, color=TEXT_PRIMARY),
                    columns=[
                        ft.DataColumn(ft.Text("Premiu")),
                        ft.DataColumn(ft.Text("Status")),
                        ft.DataColumn(ft.Text("Data")),
                    ],
                    rows=[
                        ft.DataRow(cells=[
                            ft.DataCell(ft.Text(str(w[3])[:40])),
                            ft.DataCell(ft.Row([
                                ft.Container(width=6, height=6, border_radius=3,
                                             bgcolor=ACCENT_GREEN if str(w[2]) == "WON" else ACCENT_BLUE),
                                ft.Text(str(w[2]), size=12),
                            ], spacing=6)),
                            ft.DataCell(ft.Text(str(w[4])[:16], size=11, color=TEXT_MUTED)),
                        ]) for w in wins
                    ],
                )
                history = ft.Column([table], scroll=ft.ScrollMode.ALWAYS)
            else:
                history = ft.Container(
                    content=ft.Column([
                        ft.Text("🎁", size=28),
                        ft.Text("Niciun castig inca.", size=14, color=TEXT_MUTED),
                        ft.Text("Ele vor aparea aici automat.", size=12, color=TEXT_MUTED),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                    padding=30,
                    border_radius=RADIUS,
                    bgcolor=BG_ELEVATED,
                    alignment=ft.alignment.center,
                )

            return ft.Column([
                ft.Row([
                    _compact_stat("Rafle verificate", total),
                    _compact_stat("Castiguri", len(wins), ACCENT_GREEN),
                    _compact_stat("Ultima verificare", 
                                  datetime.datetime.now().strftime("%d.%m") if total > 0 else "-"),
                ], spacing=10),
                ft.Text("Istoric castiguri", size=14, weight="bold", color=TEXT_PRIMARY),
                history,
            ], spacing=12)

        stats_container.content = build_stats()

        def refresh_stats(e=None):
            stats_container.content = build_stats()
            page.update()

        btn_refresh = ft.IconButton(
            icon=_icon("REFRESH"),
            icon_color=TEXT_SECONDARY,
            on_click=refresh_stats,
        )

        # ── layout ──────────────────────────────────────────────────────

        # Top header bar
        header = ft.Row([
            ft.Column([
                ft.Text("TakeMySkins Automator", size=24, weight="bold", color=TEXT_PRIMARY),
                ft.Text("Dashboard pentru monitorizare automata a raflelor",
                        size=13, color=TEXT_MUTED),
            ], spacing=2, expand=True),
            ft.Container(
                content=_status_badge(runtime_dot.bgcolor, runtime_status_text.value),
                padding=ft.Padding(left=14, top=8, right=18, bottom=8),
                border_radius=20,
                bgcolor=BG_ELEVATED,
            ),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # Left column: auth + QR
        auth_card = _build_card(
            ft.Column([
                _section_header("Autentificare Steam",
                                "Conecteaza-te prin QR sau login manual pentru a participa la rafle."),
                ft.Container(height=4),
                ft.Row([btn_qr, btn_manual], spacing=10),
                ft.Container(
                    content=ft.Column([qr_image, login_status], spacing=10,
                                     horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    visible=True,
                ),
            ], spacing=14),
        )

        # Right column: control + scheduler info
        control_card = _build_card(
            ft.Column([
                ft.Row([
                    _section_header("Verificare rafle", "Ruleaza o verificare manuala acum."),
                    btn_refresh,
                ], vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Row([btn_start], spacing=10),
                ft.Container(height=4),
                ft.Text("Schedulerul ruleaza automat la fiecare 6 ore in fundal.",
                        size=12, color=TEXT_MUTED),
            ], spacing=14),
        )

        # Stats section
        stats_card = _build_card(
            ft.Column([
                ft.Row([
                    _section_header("Statistici si castiguri", ""),
                    btn_refresh,
                ], vertical_alignment=ft.CrossAxisAlignment.START),
                stats_container,
            ], spacing=14),
        )

        # Terminal log
        log_terminal = ft.Container(
            content=log_area,
            border=ft.Border(
                top=ft.BorderSide(width=1, color="#0F2A4A"),
                bottom=ft.BorderSide(width=1, color="#0F2A4A"),
                left=ft.BorderSide(width=1, color="#0F2A4A"),
                right=ft.BorderSide(width=1, color="#0F2A4A"),
            ),
            border_radius=RADIUS,
            padding=14,
            bgcolor=BG_TERMINAL,
        )

        log_card = _build_card(
            ft.Column([
                _section_header("Console log", "Iesire in timp real a verificarilor."),
                log_terminal,
            ], spacing=12),
        )

        # Footer
        footer = ft.Text("TakeMySkins Automator  v1.0  ·  Render Free Tier",
                         size=11, color=TEXT_MUTED, text_align=ft.TextAlign.CENTER)

        # ── compose ─────────────────────────────────────────────────────

        page.add(
            ft.Container(
                padding=ft.Padding(left=24, top=20, right=24, bottom=20),
                content=ft.Column([
                    header,
                    progress,
                    ft.Row([auth_card, control_card], spacing=14,
                           vertical_alignment=ft.CrossAxisAlignment.START),
                    stats_card,
                    log_card,
                    footer,
                ], spacing=14, scroll=ft.ScrollMode.ADAPTIVE),
            )
        )

    return main
