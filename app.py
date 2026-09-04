import base64
import datetime
import os
import threading
import time

import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from db_manager import DBManager
from engine import RaffleBot
from webui import INDEX_HTML

db = DBManager()
bot = RaffleBot(db)

# Pre-populate cookies in Redis at startup
_startup_cookies = [
    {"name": "i18n_locale", "value": "en", "domain": ".takemyskins.com", "path": "/", "expires": 1708359327, "httpOnly": False, "secure": True, "sameSite": "Lax"},
    {"name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d", "value": "eyJpdiI6InlOREhmTTR4bWtTeDhxcjUzazlTNHc9PSIsInZhbHVlIjoiZ2dvQmlHRGNsR1ArbHJjeDZmbDFJQys0ZFFhU2Z3TkxVWkhxTytzSHZjYWdidHZ5L0ZPZW1TbXlwMG5SKzdJb1NUVjJqUCtaR2E4YjF6Vk9lWHNmTFFlenJlV1pjS0ZSQWN1TklmL1JmVlpOVUtXQ1JOUVNaRndKd01XeUc1SG1lNmZVclJ4bkFKWk8zWnR0WU5qOUhnN2M5YUtRclZDeVVwYjYvVk9GVlE0eXJ5T2lQVm8wcGh2OG1VcjBZRHVndytaSEVuYmFNLzlGTmZOQzBVdWFCVXhINEl2V3ZUQzI3RFVOWUJwd2xDaz0i", "domain": ".takemyskins.com", "path": "/", "expires": 1708359336, "httpOnly": True, "secure": True, "sameSite": "Lax"},
    {"name": "return_url", "value": "eyJpdiI6InczTlB4MkJWdVBmL1NhUWV0M3dERGc9PSIsInZhbHVlIjoieUlPV1dKanQrN3pGVUFsOU1ZeFVESGtjM3lRb211RWZMa3Z5eWtDdnRNNmJ4dWhYWEROcjdkN3pNMkxVbVRLNTRwckRkYjFYeEVVQjAvclc0Wk1ocVd3aFRCV3duZjNkVjJRdFFpeDlqd0k9IiwibWFjIjoiM2ZhNDNmMTI4OGJkYjlkNDdmNTZiNTU5Y2M0ZDgzM2VkODQ0NzhkNjY4ZjZmNzVlNjQ1YTRjNGUzNjNlZmRjNiIsInRhZyI6IiJ9", "domain": ".takemyskins.com", "path": "/", "expires": 1709415310, "httpOnly": True, "secure": True, "sameSite": "Lax"},
    {"name": "spin_wheel_stat_cookie", "value": "eyJpdiI6IndPcUFnZ3FUYlVYRG5TTnEvWXArcWc9PSIsInZhbHVlIjoiOVEva1dsM1VrRXh3MVgrNFBacUhXQ2ZvNUc0blpTaFFtZmp1YjQrT2FDL1ZmZi85NzF4MGJtdGxldlZNV1N4eUVsY0FVb3ZQRVN5KzdnalB1VG9NQzJBK0o4SVhOQllMZ05Td3JONVVpZGNTZEhLTkVKanQwVEw0bUpxSlpXV3oiLCJtYWMiOiI0MTliMGZlNDAwYmQzYzFmOTdhN2UyMWIwNDU0N2JjMDJiYmI1NGIyMzRiZjRjNWUwNjRlZGUyMDAwY2IwMWViIiwidGFnIjoiIn0%3D", "domain": ".takemyskins.com", "path": "/", "expires": 1708359327, "httpOnly": True, "secure": True, "sameSite": "Lax"},
    {"name": "takemyskins_session", "value": "PwLK8VsL1ya6WliNRmKT1XF0qWwmhbkyjp4otzCb", "domain": ".takemyskins.com", "path": "/", "expires": 1726012409, "httpOnly": True, "secure": True, "sameSite": "Lax"},
    {"name": "XSRF-TOKEN", "value": "eyJpdiI6Iko1aU5JTHhYZ0ErSVgvdDVwSUNFWmc9PSIsInZhbHVlIjoiSkNYcUxlM3hhQnBxRDV5elhsdDFZS3cvejM2R25HQlJYOGFBQXJUSTd6ZEZLaG5pWi9xaWRib0dyMUU3QjFFMCthSkVpK09vUXhOMHJmNkRFaWpHYjhBdklKUDFVWEZRNmI2bmx0V2t0WVhhSGxrWmRDamJYd3NLUitlZ3pRZG8iLCJtYWMiOiI5ODgxMTk0ZGE4NjI1YzExOWUyNGIwMDRiNTA1YWU4YWZmNDRhOWMyYTQyNWNkNDBjMDNjNGMxYjU2YmQ3YmNmIiwidGFnIjoiIn0%3D", "domain": ".takemyskins.com", "path": "/", "expires": 1726012409, "httpOnly": False, "secure": True, "sameSite": "Lax"}
]
db.save_session({"cookies": _startup_cookies, "saved_at": time.time()})

app = FastAPI(title="TakeMySkins Automator", version="2.0.0", docs_url="/docs", redoc_url=None)

# ── shared runtime state ────────────────────────────────────────────────
LOG_LINES = []
LOG_LOCK = threading.Lock()
MAX_LOG = 400

RUNTIME = {"state": "idle"}  # idle | run | ok | err
QR_STATE = {"status": "idle", "image": None, "message": "", "ok": False}
QR_LOCK = threading.Lock()
CHECK_RUNNING = {"flag": False}
QR_RUNNING = {"flag": False}


def _colorize(msg):
    up = str(msg).upper()
    if up.startswith("[JOINED]") or up.startswith("[OK]"):
        return "g"
    if up.startswith("[WARN]") or up.startswith("[WAIT]"):
        return "y"
    if up.startswith("[ERR]") or "EROARE" in up or "ERROR" in up:
        return "r"
    if up.startswith("[AUTH]") or up.startswith("[SESSION]"):
        return "c"
    if up.startswith("[API]") or up.startswith("[SCHEDULER]"):
        return "m"
    return "b"


def bot_log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    with LOG_LOCK:
        LOG_LINES.append({"time": now, "msg": str(msg), "color": _colorize(msg)})
        if len(LOG_LINES) > MAX_LOG:
            del LOG_LINES[: len(LOG_LINES) - MAX_LOG]


def set_runtime(state):
    RUNTIME["state"] = state


def qr_callback(data):
    """Called from engine.get_steam_qr. data = PNG bytes or dict."""
    with QR_LOCK:
        if isinstance(data, dict):
            if data.get("status") == "success":
                QR_STATE.update({"status": "done", "ok": True,
                                 "message": data.get("message", "Sesiune salvata!")})
            else:
                QR_STATE.update({"status": "done", "ok": False,
                                 "message": data.get("error", "Eroare QR")})
        elif data:
            b64 = base64.b64encode(data).decode("ascii")
            QR_STATE.update({"status": "show", "image": b64, "ok": True,
                             "message": "Scaneaza codul QR cu Steam Mobile"})
        else:
            QR_STATE.update({"status": "done", "ok": False,
                             "message": "QR indisponibil"})


def run_check_worker():
    try:
        set_runtime("run")
        bot_log("Pornesc verificarea manuala...")
        result = bot.run_check(is_headless=True, log_func=bot_log)
        bot_log(f"Verificare terminata: {result}")
        set_runtime("ok")
    except Exception as e:
        bot_log(f"Eroare la verificare: {e}")
        set_runtime("err")
    finally:
        CHECK_RUNNING["flag"] = False


def run_qr_worker():
    try:
        bot_log("Se genereaza QR Steam...")
        bot.get_steam_qr(qr_callback)
    except Exception as e:
        bot_log(f"Eroare QR: {e}")
        QR_STATE.update({"status": "done", "ok": False, "message": str(e)})
    finally:
        QR_RUNNING["flag"] = False


# ── UI ─────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def index():
    return INDEX_HTML


# ── API ────────────────────────────────────────────────────────────────
@app.post("/api/check")
def api_check():
    if CHECK_RUNNING["flag"]:
        return JSONResponse({"error": "O verificare ruleaza deja."}, status_code=409)
    CHECK_RUNNING["flag"] = True
    threading.Thread(target=run_check_worker, daemon=True).start()
    return {"ok": True}


@app.post("/api/qr")
def api_qr():
    if QR_RUNNING["flag"]:
        return JSONResponse({"error": "QR-ul se genereaza deja."}, status_code=409)
    QR_RUNNING["flag"] = True
    QR_STATE.update({"status": "show", "image": None, "message": "Se genereaza...", "ok": False})
    threading.Thread(target=run_qr_worker, daemon=True).start()
    return {"ok": True}


@app.get("/api/logs")
def api_logs(after: int = 0):
    with LOG_LOCK:
        lines = LOG_LINES[after:]
        return {"count": len(LOG_LINES), "lines": lines}


@app.get("/api/stats")
def api_stats():
    total, wins = db.get_stats()
    last_run = "-"
    if wins:
        try:
            last_run = str(wins[0][4])[:16]
        except Exception:
            last_run = datetime.datetime.now().strftime("%H:%M")
    elif total > 0:
        last_run = datetime.datetime.now().strftime("%H:%M")

    win_list = []
    for w in wins[:20]:
        win_list.append({
            "item": str(w[3]) if len(w) > 3 else "-",
            "status": str(w[2]) if len(w) > 2 else "-",
            "date": str(w[4])[:16] if len(w) > 4 and w[4] else "-",
        })
    return {"total": total, "wins": win_list, "last_run": last_run}


@app.get("/api/qr")
def api_qr_get():
    with QR_LOCK:
        return dict(QR_STATE)


@app.get("/api/runtime")
def api_runtime():
    return {"state": RUNTIME["state"]}


@app.get("/api/winnings")
def api_winnings():
    try:
        data = bot.get_profile_prizes(log=bot_log)
        if data is None:
            return JSONResponse({"error": "Nu esti logat. Ruleaza login-ul Steam."}, status_code=401)
        return data
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/session")
def api_session():
    user = bot.get_current_user(log=bot_log)
    if user:
        return {"logged_in": True, "nickname": user.get("nickname"),
                "id": user.get("id")}
    return {"logged_in": False}


@app.get("/api/db")
def api_db():
    return {
        "redis": db.redis_available,
        "postgres": db.postgres_available,
        "session_in_redis": db.session_exists(),
    }


# ── health (Render) ────────────────────────────────────────────────────
@app.get("/healthz")
def healthz():
    return "ok"


@app.get("/ping")
def ping():
    return {"status": "alive"}


@app.get("/status")
def status():
    return {"app": "TakeMySkins Automator", "status": "running"}


# ── keep-alive ─────────────────────────────────────────────────────────
def keep_alive_self_ping(target_url, interval_seconds=600):
    while True:
        try:
            response = requests.get(target_url, timeout=10)
            if response.status_code == 200:
                print(f"[KEEP-ALIVE] Self-ping OK: {target_url}")
            else:
                print(f"[KEEP-ALIVE] Unexpected status {response.status_code}")
        except requests.exceptions.Timeout:
            print("[KEEP-ALIVE] Timeout la self-ping (ignorat)")
        except Exception as e:
            print(f"[KEEP-ALIVE] Eroare: {e}")
        time.sleep(interval_seconds)


def delayed_scheduler_start(bot, delay=120, interval_seconds=21600):
    print(f"[SCHEDULER] Waiting {delay}s before first check (RAM optimization)...")
    time.sleep(delay)
    print("[SCHEDULER] Delay done, starting background scheduler now.")
    bot.start_background_scheduler(interval_seconds=interval_seconds, is_headless=True, log_func=bot_log)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8080))

    SELF_PING_INTERVAL = int(os.getenv("SELF_PING_INTERVAL", 600))
    threading.Thread(
        target=keep_alive_self_ping,
        args=(f"http://127.0.0.1:{port}/healthz", SELF_PING_INTERVAL),
        daemon=True,
    ).start()

    SCHEDULER_DELAY = int(os.getenv("SCHEDULER_DELAY", 120))
    SCHEDULER_INTERVAL = int(os.getenv("SCHEDULER_INTERVAL", 21600))
    threading.Thread(
        target=delayed_scheduler_start,
        args=(bot, SCHEDULER_DELAY, SCHEDULER_INTERVAL),
        daemon=True,
    ).start()

    print(f"Web UI starting on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
