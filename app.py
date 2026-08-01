import os
import flet as ft
import time
import threading
import requests
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from db_manager import DBManager
from engine import RaffleBot
from gui import start_gui

# Initialize components
db = DBManager()
db.setup_db()
bot = RaffleBot(db)
main_func = start_gui(bot)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        elif self.path == "/ping":
            body = b'{"status": "alive"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        elif self.path == "/status":
            body = b'{"app": "TakeMySkins Automator", "status": "running"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return


def start_internal_health_server(port):
    server = ThreadingHTTPServer(("127.0.0.1", port), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Health server pornit pe 127.0.0.1:{port} (/healthz) - internal only.")


def keep_alive_self_ping(target_url, interval_seconds=600):
    while True:
        try:
            response = requests.get(target_url, timeout=10)
            if response.status_code == 200:
                print(f"[KEEP-ALIVE] Self-ping OK: {target_url}")
            else:
                print(f"[KEEP-ALIVE] Unexpected status {response.status_code}")
        except requests.exceptions.Timeout:
            print(f"[KEEP-ALIVE] Timeout la self-ping (ignorat)")
        except Exception as e:
            print(f"[KEEP-ALIVE] Eroare: {e}")
        time.sleep(interval_seconds)


def delayed_scheduler_start(bot, delay=120, interval_seconds=21600):
    """Start scheduler after delay so Flet initializes first (avoids OOM on 512MB)."""
    print(f"[SCHEDULER] Waiting {delay}s before first check (RAM optimization)...")
    time.sleep(delay)
    print(f"[SCHEDULER] Delay done, starting background scheduler now.")
    bot.start_background_scheduler(interval_seconds=interval_seconds, is_headless=True)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))

    health_port = int(os.getenv("HEALTHCHECK_PORT", str(port + 1)))
    start_internal_health_server(health_port)
    self_ping_url = f"http://127.0.0.1:{health_port}/healthz"

    SELF_PING_INTERVAL = int(os.getenv("SELF_PING_INTERVAL", 600))
    threading.Thread(target=keep_alive_self_ping, args=(self_ping_url, SELF_PING_INTERVAL), daemon=True).start()

    # Delay scheduler: Flet + SeleniumBase at once = OOM on 512MB Render Free
    SCHEDULER_DELAY = int(os.getenv("SCHEDULER_DELAY", 120))
    threading.Thread(
        target=delayed_scheduler_start,
        args=(bot, SCHEDULER_DELAY, 21600),
        daemon=True,
    ).start()

    # Flet on 0.0.0.0:PORT
    print(f"Flet web UI starting on 0.0.0.0:{port}")
    ft.app(target=main_func, view=ft.AppView.WEB_BROWSER, port=port)
