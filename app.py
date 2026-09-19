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

# Check existing session at startup (don't overwrite with hardcoded cookies)
if db.pinned_account:
    if db.session_exists():
        print(f'[STARTUP] Pinned account {db.pinned_account} found in Redis - will use it')
    else:
        print(f'[STARTUP] Pinned account {db.pinned_account} has no session in Redis - QR/import required')
elif db.session_exists():
    print('[STARTUP] Session found in Redis - will use saved cookies')
else:
    print('[STARTUP] No session in Redis - QR login required')

app = FastAPI(title="TakeMySkins Automator", version="2.0.0", docs_url="/docs", redoc_url=None)

# ── shared runtime state ────────────────────────────────────────────────
LOG_LINES = []
LOG_LOCK = threading.Lock()
MAX_LOG = 400

RUNTIME = {"state": "idle"}  # idle | run | ok | err
QR_STATE = {"status": "idle", "image": None, "message": "", "ok": False}
QR_LOCK = threading.Lock()
QR_DONE_AT = {"time": 0}
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
            QR_DONE_AT["time"] = time.time()
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
            QR_DONE_AT["time"] = time.time()
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
        bot.get_steam_qr(qr_callback, log_func=bot_log)
    except Exception as e:
        bot_log(f"Eroare QR: {e}")
        with QR_LOCK:
            QR_DONE_AT["time"] = time.time()
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
    with QR_LOCK:
        QR_STATE.update({"status": "show", "image": None, "message": "Se genereaza...", "ok": False})
    threading.Thread(target=run_qr_worker, daemon=True).start()
    return {"ok": True}


@app.post("/api/qr/regenerate")
def api_qr_regenerate():
    """Cancel any in-progress QR attempt (e.g. Steam Guard popup closed by
    mistake) and start a fresh one."""
    bot.request_qr_cancel()
    for _ in range(50):  # up to 5s for the old attempt to unwind
        if not QR_RUNNING["flag"]:
            break
        time.sleep(0.1)
    QR_RUNNING["flag"] = True
    with QR_LOCK:
        QR_STATE.update({"status": "show", "image": None, "message": "Se regenereaza...", "ok": False})
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
        if QR_STATE["status"] == "done" and time.time() - QR_DONE_AT["time"] > 15:
            QR_STATE.update({"status": "idle", "image": None, "message": "", "ok": False})
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


@app.get("/api/accounts")
def api_accounts():
    return {"accounts": bot.list_accounts(), "pinned": db.pinned_account}


@app.post("/api/accounts/switch")
def api_accounts_switch(req: dict):
    steam_id = req.get("steam_id")
    if not steam_id:
        return JSONResponse({"error": "steam_id necesar"}, status_code=400)
    if db.pinned_account and steam_id != db.pinned_account:
        return JSONResponse(
            {"error": f"Server fixat pe {db.pinned_account} (ACTIVE_STEAM_ID). Schimba env-ul ca sa schimbi contul."},
            status_code=403,
        )
    ok = bot.switch_account(steam_id, log=bot_log)
    if not ok:
        return JSONResponse({"error": "Cont necunoscut"}, status_code=404)
    return {"ok": True}


@app.get("/api/ip")
def api_ip():
    try:
        r = requests.get("https://api.ipify.org?format=json", timeout=5)
        return {"ip": r.json().get("ip", "-")}
    except Exception:
        return {"ip": "-"}


@app.get("/api/db")
def api_db():
    return {
        "redis": db.redis_available,
        "postgres": db.postgres_available,
        "session_in_redis": db.session_exists(),
        "pinned": db.pinned_account,
        "active": db.get_active_steam_id(),
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

    SELF_PING_INTERVAL = int(os.getenv("SELF_PING_INTERVAL", 300))
    # IMPORTANT: ping-ul trebuie sa iasa prin URL-ul PUBLIC (prin proxy-ul
    # Render), altfel routerul nu vede trafic inbound si serviciul intra
    # in sleep dupa ~15 min (cold start 50s+). Ping-ul catre 127.0.0.1
    # ramane in container si NU previne spin-down-ul.
    # RENDER_EXTERNAL_URL e injectat automat de Render, fara config manual.
    public_base = (
        os.getenv("RENDER_EXTERNAL_URL")
        or os.getenv("PUBLIC_URL")
        or f"http://127.0.0.1:{port}"
    ).rstrip("/")
    self_ping_url = f"{public_base}/healthz"
    print(f"[KEEP-ALIVE] Self-ping target: {self_ping_url} la fiecare {SELF_PING_INTERVAL}s")
    threading.Thread(
        target=keep_alive_self_ping,
        args=(self_ping_url, SELF_PING_INTERVAL),
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
