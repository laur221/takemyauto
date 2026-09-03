import json
import os
import threading
import time

import requests

API_BASE = "https://api.takemyskins.com"
FRONTEND_VERSION = "23.07.2026_7dade"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = os.path.join(BASE_DIR, "user_session", "tms_cookies.json")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class RaffleBot:
    def __init__(self, db):
        self.db = db
        self.session_dir = os.path.join(BASE_DIR, "user_session")
        self._http = None
        self._csrf_token = None
        self._check_lock = threading.Lock()
        self._scheduler_thread = None
        self._scheduler_stop_event = threading.Event()
        self._user_id = None
        self._profile_cache = None

    # ── helpers ──────────────────────────────────────────────────────────

    def _session_file(self):
        return os.path.join(self.session_dir, "tms_cookies.json")

    def save_cookies(self, cookie_list, log=None):
        self._http = None
        self._csrf_token = None
        os.makedirs(self.session_dir, exist_ok=True)
        payload = {
            "cookies": cookie_list,
            "saved_at": time.time(),
        }
        with open(self._session_file(), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        if log:
            log("[SESSION] Cookies salvate local")
        self.db.save_session(payload)

    def load_cookies(self, log=None):
        data = None
        try:
            if os.path.exists(self._session_file()):
                with open(self._session_file(), "r", encoding="utf-8") as f:
                    data = json.load(f)
        except Exception:
            data = None
        if not data:
            data = self.db.get_session()
        if not data:
            if log:
                log("[SESSION] Nu exista cookies salvate")
            return None
        return data.get("cookies") or []

    def _build_http(self, log=None):
        session = requests.Session()
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "X-Frontend-Version": FRONTEND_VERSION,
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://takemyskins.com",
            "Referer": "https://takemyskins.com/",
        })
        cookies = self.load_cookies(log)
        if cookies:
            for c in cookies:
                try:
                    if not c.get("name") or c.get("value") is None:
                        continue
                    session.cookies.set(
                        c["name"],
                        c["value"],
                        domain=c.get("domain") or "takemyskins.com",
                        path=c.get("path") or "/",
                        secure=bool(c.get("secure")),
                    )
                except Exception:
                    continue
        return session

    def _set_csrf(self, session, log=None):
        try:
            r = session.get(
                f"{API_BASE}/root",
                headers={"Accept": "application/json, text/plain, */*"},
                timeout=20,
            )
            data = r.json()
            token = data.get("token")
            if token:
                self._csrf_token = token
                session.headers["X-CSRF-Token"] = token
                if log:
                    log("[AUTH] CSRF token obtinut din /root")
            return data
        except Exception as e:
            if log:
                log(f"[AUTH] Nu am putut lua CSRF din /root: {e}")
            return {}

    def _ensure_session(self, log=None):
        if self._http is None:
            self._http = self._build_http(log)
        return self._http

    # ── API methods ──────────────────────────────────────────────────────

    def fetch_root(self, log=None):
        session = self._ensure_session(log)
        return self._set_csrf(session, log)

    def list_active_giveaways_from_html(self, log=None):
        """Parsează pagina principală și extrage raflele direct din HTML"""
        import re
        session = self._ensure_session(log)
        try:
            r = session.get("https://takemyskins.com/", timeout=20)
            r.raise_for_status()
            html = r.text
            
            # Caută toate link-urile către giveaways: /giveaways/{segment}
            pattern = r'href="(/giveaways/([a-f0-9]+))"[^>]*>(.*?)</a>'
            matches = re.findall(pattern, html, re.DOTALL)
            
            giveaways = []
            for url, segment, content in matches:
                # Verifică dacă e deja înscris (conține "You're in")
                joined = "You're in" in content or "You&#x27;re in" in content
                
                # Extrage numele (aproximativ, poate fi îmbunătățit)
                name_match = re.search(r'Raffle #(\d+)', content)
                name = f"Raffle #{name_match.group(1)}" if name_match else f"Raffle {segment[:8]}"
                
                giveaways.append({
                    "id": segment,  # Folosim segment ca ID
                    "custom_url_segment": segment,
                    "name": name,
                    "joined": joined,
                    "is_joined": joined
                })
            
            if log:
                log(f"[HTML] Găsite {len(giveaways)} rafle pe pagina principală")
            
            return {"giveaways": giveaways, "total": {"active_total": len(giveaways)}}
        except Exception as e:
            if log:
                log(f"[HTML] Eroare la parsarea HTML: {e}")
            return {"giveaways": [], "total": {"active_total": 0}}

    def list_active_giveaways(self, log=None, page=1, per_page=50):
        session = self._ensure_session(log)
        params = {"page": page, "per_page": per_page}
        r = session.get(
            f"{API_BASE}/giveaway/active_giveaways",
            params=params,
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    def show_giveaway(self, segment, log=None):
        session = self._ensure_session(log)
        r = session.get(f"{API_BASE}/giveaway/show/{segment}", timeout=20)
        r.raise_for_status()
        return r.json()

    def join_giveaway(self, ref, log=None):
        session = self._ensure_session(log)
        r = session.post(
            f"{API_BASE}/giveaway/join_giveaway/{ref}",
            json={},
            timeout=20,
        )
        try:
            return r.json()
        except Exception as e:
            try:
                error_text = r.text[:200]
            except Exception:
                error_text = f"Failed to parse response (status {r.status_code})"
            return {"status": "error", "error_message": error_text}

    def check_reward_conditions(self, condition, ga_id, log=None):
        session = self._ensure_session(log)
        r = session.post(
            f"{API_BASE}/giveaway/check_reward_conditions",
            json={"condition": condition, "ga_id": ga_id},
            timeout=20,
        )
        try:
            return r.json()
        except Exception:
            return {"status": "error", "error_message": r.text[:200]}

    def get_conditions(self, id_or_code, log=None):
        session = self._ensure_session(log)
        r = session.post(
            f"{API_BASE}/giveaway/get_conditions",
            json={"id_or_code": id_or_code},
            timeout=20,
        )
        try:
            # Verifică dacă răspunsul e HTML (sesiune expirată)
            content_type = r.headers.get('content-type', '')
            if 'text/html' in content_type or r.text.strip().startswith('<!DOCTYPE'):
                if log:
                    log("[AUTH] Sesiune expirata - cookies invalide. Re-logheaza-te din UI.")
                return {"status": "error", "error_message": "session_expired"}
            return r.json()
        except Exception:
            return {"status": "error", "error_message": r.text[:200]}

    # ── profile / prizes ────────────────────────────────────────────────

    def get_current_user(self, log=None):
        """Fetch the logged-in user profile (None if not authenticated).
        Retries once with a fresh session so cookies loaded later (Redis) are picked up."""
        for attempt in range(2):
            try:
                session = self._ensure_session(log)
                self._set_csrf(session, log)
                r = session.get(f"{API_BASE}/profile/user", timeout=20)
                data = r.json()
                user = data.get("user")
                if user:
                    self._user_id = user.get("id")
                    self._profile_cache = user
                    return user
                if attempt == 0:
                    self._http = None
                    self._csrf_token = None
            except Exception as e:
                if attempt == 0:
                    self._http = None
                    self._csrf_token = None
                if log:
                    log(f"[API] get_current_user: {e}")
        return None

    def _normalize_prize(self, entry):
        item = entry.get("item") or {}
        return {
            "name": item.get("steam_market_hash_name") or item.get("skin_name") or "-",
            "price": item.get("price") or 0,
            "image": item.get("steam_image") or "",
            "rarity": item.get("rarity") or "",
            "exterior": item.get("steam_short_exterior") or "",
            "weapon": item.get("weapon_name") or "",
            "time_finished": entry.get("time_finished") or "",
            "url": entry.get("url") or "",
            "game": entry.get("game") or "",
            "inventory_state": entry.get("inventory_state"),
        }

    def get_profile_prizes(self, log=None):
        """Won prizes from both profile tabs (active = not taken, history = taken)
        aggregated over all games, plus the participation count."""
        def log_m(msg):
            if log:
                log(msg)

        user = self.get_current_user(log)
        if not user:
            return None
        uid = user.get("id") or self._user_id
        if not uid:
            return None

        active_items, history_items = [], []
        session = self._ensure_session(log)

        for game in ["csgo", "dota2", "rust"]:
            for tab, bucket in (("items", active_items), ("items_history", history_items)):
                try:
                    r = session.get(
                        f"{API_BASE}/profile/get_profile_{tab}/{uid}",
                        params={"game": game},
                        timeout=20,
                    )
                    if r.status_code != 200:
                        continue
                    data = r.json()
                    for entry in data.get("items") or []:
                        prize = self._normalize_prize(entry)
                        if prize["name"] != "-":
                            bucket.append(prize)
                except Exception as e:
                    log_m(f"[API] get_profile_{tab} ({game}): {e}")

        # authoritative profile stats (same endpoint the site's profile page uses)
        stats = {}
        try:
            r = session.get(
                f"{API_BASE}/profile/get_profile_general_information/{uid}",
                params={"game": "csgo"},
                timeout=20,
            )
            info = r.json().get("info") or {}
            stats = info.get("stats") or {}
        except Exception as e:
            log_m(f"[API] general information: {e}")

        active_cost = round(sum(p["price"] for p in active_items), 2)
        history_cost = round(sum(p["price"] for p in history_items), 2)
        item_total = len(active_items) + len(history_items)
        return {
            "active": active_items,
            "history": history_items,
            "active_count": len(active_items),
            "active_cost": active_cost,
            "history_count": len(history_items),
            "won_count": int(stats.get("giveaway_count") or item_total or 0),
            "won_cost": float(stats.get("total_ga_value") or 0) or round(active_cost + history_cost, 2),
            "participated": int(stats.get("user_giveaway_count") or 0),
            "nickname": user.get("nickname"),
        }

    # ── main methods ─────────────────────────────────────────────────────

    def run_check(self, is_headless=True, log_func=None):
        def log(msg):
            if log_func:
                log_func(msg)
            print(msg)

        if not self._check_lock.acquire(blocking=False):
            log("O verificare ruleaza deja. Sar peste executia paralela.")
            return "Deja ruleaza"

        try:
            session = self._ensure_session(log)
            root = self._set_csrf(session, log)
            if not root:
                log("[API] Eroare la init /root. Verifica reteaua.")
                return "Eroare"

            log("[HTML] Se listeaza raflele active de pe site...")
            data = self.list_active_giveaways_from_html(log)
            giveaways = data.get("giveaways") or []
            total_info = data.get("total") or {}
            total = total_info.get("active_total") if isinstance(total_info, dict) else total_info
            log(f"[HTML] {len(giveaways)} rafle gasite pe pagina ({total} active).")

            joined_count = 0
            skipped_conditions = 0
            already_joined = 0

            for g in giveaways:
                try:
                    gid = g.get("id")
                    segment = g.get("custom_url_segment") or gid
                    name = g.get("name") or f"raffle-{gid}"
                    joined = bool(g.get("joined") or g.get("is_joined"))

                    if joined:
                        already_joined += 1
                        log(f"[OK] Deja inscris: {name} (#{gid})")
                        continue

                    log(f"-> Verific {name} (#{segment})...")
                    cond_data = self.get_conditions(segment, log)
                    
                    # Skip rafle care returnează eroare (șterse/închise)
                    if cond_data.get("status") == "error":
                        error_msg = cond_data.get("error_message", "unknown")
                        log(f"[SKIP] {name}: {error_msg}")
                        continue
                    
                    cond_inner = cond_data.get("data") or cond_data

                    if cond_inner.get("is_joined"):
                        already_joined += 1
                        log(f"[OK] Deja inscris (detail): {name}")
                        continue

                    conditions = cond_inner.get("conditions") or {}
                    if conditions:
                        pending = [
                            code for code, c in conditions.items()
                            if code != "join" and not c.get("verified")
                        ]
                        if pending:
                            log(f"  -> Verific conditiile: {', '.join(pending)}")
                            for code in pending:
                                try:
                                    check = self.check_reward_conditions(code, gid, log)
                                    if check.get("verified"):
                                        log(f"    [OK] {code} verificat")
                                    else:
                                        log(f"    [WARN] {code}: {check.get('error_message') or 'failed'}")
                                except Exception as e:
                                    log(f"    [ERR] check {code}: {e}")
                            conditions = self.get_conditions(segment, log)
                            cond_inner = conditions.get("data") or conditions
                            still_pending = [
                                code for code, c in (cond_inner.get("conditions") or {}).items()
                                if code != "join" and not c.get("verified")
                            ]
                            if still_pending:
                                skipped_conditions += 1
                                log(f"[WAIT] {name}: conditii ramase: {', '.join(still_pending)}")
                                continue

                    res = self.join_giveaway(gid, log)
                    status = res.get("status")
                    if status == "success":
                        joined_count += 1
                        self.db.save_raffle(str(gid), "JOINED", item=name)
                        log(f"[JOINED] INTRAT in {name}!")
                    else:
                        msg = res.get("error_message") or "unknown"
                        log(f"[WARN] {name}: {status} ({msg})")
                        if "need_auth" in str(msg).lower():
                            log("[AUTH] Nu esti logat. Ruleaza login-ul Steam din UI.")
                except Exception as e:
                    log(f"Eroare la procesarea raflei: {e}")

            log(f"[API] Gata: {joined_count} noi, {already_joined} deja, "
                f"{skipped_conditions} cu conditii.")
            return "Gata!"
        except Exception as e:
            log(f"Eroare generala: {e}")
            return "Eroare"
        finally:
            self._check_lock.release()

    # ── scheduler ────────────────────────────────────────────────────────

    def start_background_scheduler(self, interval_seconds=21600, is_headless=True, log_func=None):
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            return

        self._scheduler_stop_event.clear()

        def log(msg):
            if log_func:
                log_func(msg)
            print(msg)

        def worker():
            log(f"[SCHEDULER] Background scheduler started (interval: {interval_seconds}s)")
            while not self._scheduler_stop_event.is_set():
                cookies = self.load_cookies(log)
                if not cookies:
                    log("[SCHEDULER] Nu exista sesiune. Astept login Steam inainte de verificari.")
                    self._scheduler_stop_event.wait(interval_seconds)
                    continue

                log("Pornesc verificarea automata a raflelor (Background Task)...")
                try:
                    self.run_check(is_headless=is_headless, log_func=log_func)
                except Exception as e:
                    log(f"Eroare in scheduler: {e}")
                self._scheduler_stop_event.wait(interval_seconds)

        self._scheduler_thread = threading.Thread(target=worker, daemon=True)
        self._scheduler_thread.start()

    def stop_background_scheduler(self):
        self._scheduler_stop_event.set()

    # ── steam QR login (browser, one-time) ───────────────────────────────

    def get_steam_qr(self, refresh_ui_callback):
        """One-time Steam login via QR. Retries if Chrome becomes unresponsive.
        After successful login the takemyskins session cookies are saved."""
        if not self._check_lock.acquire(blocking=False):
            print("[QR] Browserul este ocupat. Incearca din nou in cateva minute.")
            refresh_ui_callback({"error": "Browserul este ocupat cu o alta verificare."})
            return

        try:
            last_err = None
            for attempt in range(1, 4):
                try:
                    self._steam_qr_attempt(refresh_ui_callback)
                    return
                except Exception as e:
                    last_err = str(e)
                    unstable = "Timed out receiving message from renderer" in last_err
                    if not unstable or attempt >= 3:
                        break
                    print(f"[QR] Chrome instabil (incercarea {attempt}). Reincerc peste 5s...")
                    time.sleep(5)
            refresh_ui_callback({"error": last_err or "Eroare QR necunoscuta"})
        finally:
            self._check_lock.release()

    def _steam_qr_attempt(self, refresh_ui_callback):
        """Single attempt of the QR login flow. Raises on failure."""
        from seleniumbase import Driver

        os.makedirs(self.session_dir, exist_ok=True)
        driver = Driver(
            uc=True,
            user_data_dir=self.session_dir,
            headless=False,
            agent=USER_AGENT,
            chromium_arg="--no-sandbox,--disable-dev-shm-usage,--disable-gpu,"
                         "--disable-extensions,--no-first-run,--mute-audio,"
                         "--window-position=-32000,-32000,--window-size=1280,800",
        )
        try:
            driver.set_page_load_timeout(30)
            driver.get("https://store.steampowered.com/login/")
            print("[QR] Pagina Steam incarcata, astept QR...")
            time.sleep(6)

            qr_bytes = None
            qr_selectors = [
                "img[src*='blob:']",
                "div[style*='--qr-bright-color']",
                "div[class*='qr'] img",
                "canvas",
            ]
            for attempt in range(5):
                for sel in qr_selectors:
                    try:
                        elems = driver.find_elements("css selector", sel)
                        for el in elems:
                            if el.is_displayed():
                                size = el.size or {}
                                if size.get("width", 0) >= 120:
                                    shot = el.screenshot_as_png
                                    if shot and len(shot) > 1000:
                                        qr_bytes = shot
                                        break
                        if qr_bytes:
                            break
                    except Exception:
                        continue
                if qr_bytes:
                    break
                time.sleep(2)

            if not qr_bytes:
                raise RuntimeError("Steam nu a afisat QR-ul (pagina s-ar putea sa ceara user/pass).")

            refresh_ui_callback(qr_bytes)
            print("[QR] QR trimis pe UI. Astept scanarea...")

            scanned = False
            scan_timeout = int(os.getenv("STEAM_QR_TIMEOUT", "180"))
            for _ in range(scan_timeout):
                try:
                    cookies = driver.get_cookies()
                    names = {c.get("name") for c in cookies}
                    if "steamLoginSecure" in names:
                        scanned = True
                        break
                except Exception:
                    pass
                time.sleep(1)

            if not scanned:
                raise RuntimeError("Timpul a expirat. QR-ul Steam nu a fost scanat.")

            print("[QR] Steam autentificat! Completez login-ul la TakeMySkins...")
            driver.get(f"{API_BASE}/login/steam")

            cookies = None
            for _ in range(30):
                try:
                    current = driver.get_cookies()
                    names = {c.get("name") for c in current}
                    if "takemyskins_session" in names:
                        cookies = current
                        break
                except Exception:
                    pass
                time.sleep(1)

            if not cookies:
                raise RuntimeError("Login Steam OK, dar TakeMySkins nu a setat sesiunea. "
                                   "Incearca din nou sau logheaza-te manual in browser.")

            self.save_cookies(cookies)
            refresh_ui_callback({"status": "success", "message": "Sesiune TakeMySkins salvata!"})
            print("[QR] [OK] Sesiune TakeMySkins salvata!")
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
