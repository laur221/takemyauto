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
        self._qr_cancel_event = threading.Event()

    def request_qr_cancel(self):
        self._qr_cancel_event.set()

    @staticmethod
    def _wd_call(fn, timeout=15):
        """Run a WebDriver command with a hard timeout. Native Selenium
        commands (e.g. .click(), .current_url) have no built-in timeout and
        can hang forever if Chrome becomes unresponsive - unlike page loads,
        which respect set_page_load_timeout."""
        box = {}

        def target():
            try:
                box["value"] = fn()
            except Exception as e:
                box["error"] = e

        t = threading.Thread(target=target, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            raise RuntimeError(f"Comanda browser nu a raspuns in {timeout}s (posibil inghetat)")
        if "error" in box:
            raise box["error"]
        return box.get("value")

    # ── helpers ──────────────────────────────────────────────────────────

    def _session_file(self):
        return os.path.join(self.session_dir, "tms_cookies.json")

    def _identity_from_cookies(self, cookie_list, log=None):
        """Fetch the SteamID64 + nickname for a given cookie jar via the
        takemyskins profile API. Cookies saved after login are
        takemyskins.com-only (Selenium only captures the current domain's
        jar), so there's no Steam cookie to read the SteamID from directly -
        but /profile/user returns it as user.steam_id."""
        session = requests.Session()
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "X-Frontend-Version": FRONTEND_VERSION,
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://takemyskins.com",
            "Referer": "https://takemyskins.com/",
        })
        for c in cookie_list or []:
            try:
                if not c.get("name") or c.get("value") is None:
                    continue
                session.cookies.set(
                    c["name"], c["value"],
                    domain=c.get("domain") or "takemyskins.com",
                    path=c.get("path") or "/",
                )
            except Exception:
                continue
        for attempt in range(3):
            try:
                r = session.get(f"{API_BASE}/root", timeout=20)
                token = r.json().get("token")
                if token:
                    session.headers["X-CSRF-Token"] = token
                r2 = session.get(f"{API_BASE}/profile/user", timeout=20)
                user = r2.json().get("user")
                if user and user.get("steam_id"):
                    return str(user["steam_id"]), user.get("nickname")
                if log:
                    log(f"[AUTH] Identificare cont: raspuns fara user (incercarea {attempt + 1}/3)")
            except Exception as e:
                if log:
                    log(f"[AUTH] Nu am putut identifica contul (incercarea {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(3)
        return None, None

    def save_cookies(self, cookie_list, log=None, steam_id=None, nickname=None):
        self._http = None
        self._csrf_token = None
        os.makedirs(self.session_dir, exist_ok=True)
        if not steam_id:
            steam_id, nickname = self._identity_from_cookies(cookie_list, log)
        steam_id = steam_id or "default"
        payload = {
            "cookies": cookie_list,
            "saved_at": time.time(),
            "steam_id": steam_id,
        }
        with open(self._session_file(), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        if log:
            log(f"[SESSION] Cookies salvate local (cont {nickname or steam_id})")
        self.db.save_session(steam_id, payload, nickname=nickname)
        return steam_id

    def load_cookies(self, log=None):
        data = None
        active_id = self.db.get_active_steam_id()
        data = self.db.get_session(active_id)
        if not data:
            try:
                if os.path.exists(self._session_file()):
                    with open(self._session_file(), "r", encoding="utf-8") as f:
                        local = json.load(f)
                    if not active_id or local.get("steam_id") == active_id:
                        data = local
            except Exception:
                data = None
        if not data:
            # One-time migration from the old single-account key.
            legacy = self.db.get_legacy_session()
            if legacy:
                steam_id, nickname = self._identity_from_cookies(legacy.get("cookies"), log)
                steam_id = steam_id or "default"
                self.db.save_session(steam_id, legacy, nickname=nickname)
                self.db.delete_legacy_session()
                data = legacy
                if log:
                    log(f"[SESSION] Migrat contul existent la noul format ({nickname or steam_id})")
        if not data:
            if log:
                log("[SESSION] Nu exista cookies salvate")
            return None
        raw_cookies = data.get("cookies") or []
        # Fix expired cookies by setting expiry 5 years into the future
        future_expiry = time.time() + 86400 * 365 * 5
        clean_cookies = []
        for c in raw_cookies:
            if isinstance(c, dict):
                c_copy = dict(c)
                c_copy["expires"] = future_expiry
                clean_cookies.append(c_copy)
        return clean_cookies

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
        # Always rebuild session to load fresh cookies from Redis
        self._http = self._build_http(log)
        return self._http

    def list_accounts(self):
        return self.db.list_accounts()

    def switch_account(self, steam_id, log=None):
        ok = self.db.set_active_account(steam_id)
        if ok:
            self._http = None
            self._csrf_token = None
            self._user_id = None
            self._profile_cache = None
            if log:
                log(f"[SESSION] Cont activ schimbat: {steam_id}")
        return ok

    # ── API methods ──────────────────────────────────────────────────────

    def fetch_root(self, log=None):
        session = self._ensure_session(log)
        return self._set_csrf(session, log)

    @staticmethod
    def _pw_cookies(cookie_list):
        """Convert stored cookies (Selenium / Cookie-Editor export shape) to
        the strict shape Playwright's add_cookies() accepts.

        Cookie-Editor exports sameSite as "no_restriction"/"unspecified"/etc.,
        which Playwright rejects (it only accepts Strict|Lax|None). Unknown
        values are dropped so the browser applies its default instead.
        """
        out = []
        for c in cookie_list or []:
            try:
                name = c.get("name")
                value = c.get("value")
                if not name or value is None:
                    continue
                pw = {
                    "name": name,
                    "value": value,
                    "domain": (c.get("domain") or "takemyskins.com").lstrip(".").split(":")[0],
                    "path": c.get("path") or "/",
                }
                exp = c.get("expires") or c.get("expiry") or c.get("expirationDate")
                if exp:
                    try:
                        pw["expires"] = float(exp)
                    except (TypeError, ValueError):
                        pass
                if c.get("httpOnly") is not None:
                    pw["httpOnly"] = bool(c.get("httpOnly"))
                secure = bool(c.get("secure"))
                same = (c.get("sameSite") or "").strip().lower()
                if same == "strict":
                    pw["sameSite"] = "Strict"
                elif same == "lax":
                    pw["sameSite"] = "Lax"
                elif same in ("none", "no_restriction"):
                    pw["sameSite"] = "None"
                    secure = True  # SameSite=None requires Secure
                # else: omit sameSite entirely (browser default)
                pw["secure"] = secure
                out.append(pw)
            except Exception:
                continue
        return out

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

    # NOTE: Playwright-based joining was removed - the site renders the
    # giveaway page logged-out for automated browsers, but the plain API
    # flow (show -> GET checks -> POST join by numeric id) works reliably.



    def check_reward_conditions(self, condition, ga_id, log=None):
        # Real site contract (from its own JS bundle): GET with query params.
        session = self._ensure_session(log)
        r = session.get(
            f"{API_BASE}/giveaway/check_reward_conditions",
            params={"condition": condition, "ga_id": ga_id},
            timeout=20,
        )
        try:
            return r.json()
        except Exception:
            return {"status": "error", "error_message": r.text[:200]}

    def get_conditions(self, id_or_code, log=None):
        # Real site contract: GET with query param.
        session = self._ensure_session(log)
        r = session.get(
            f"{API_BASE}/giveaway/get_conditions",
            params={"id_or_code": id_or_code},
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

    def join_giveaway(self, ga_id, log=None):
        """Join a giveaway by its NUMERIC id (the URL segment 500s).
        Returns the parsed JSON (contains 'member' on success)."""
        session = self._ensure_session(log)
        r = session.post(
            f"{API_BASE}/giveaway/join_giveaway/{ga_id}",
            json={},
            timeout=20,
        )
        try:
            return r.json()
        except Exception:
            try:
                error_text = r.text[:200]
            except Exception:
                error_text = f"Failed to parse response (status {r.status_code})"
            return {"status": "error", "error_message": error_text}

    def check_and_join_giveaway(self, segment, log=None):
        """API-only join flow (no browser needed):
        show -> verify each condition -> join by numeric id -> confirm."""
        def lg(m):
            if log:
                log(m)
        try:
            show = self.show_giveaway(segment, log)
        except Exception as e:
            return {"status": "error", "message": f"show failed: {e}"}
        g = (show.get("giveaway") if isinstance(show, dict) else None) or {}
        ga_id = g.get("id")
        name = g.get("name") or segment
        if g.get("is_joined"):
            lg(f"[OK] Deja inscris (API): {name}")
            return {"status": "success", "already_joined": True}
        if not ga_id:
            return {"status": "error", "message": "show fara id numeric"}
        for cond, info in ((g.get("conditions") or {}).items()):
            try:
                res = self.check_reward_conditions(cond, ga_id, log)
                ok = res.get("verified") or res.get("completed") or res.get("status") == "success"
                lg(f"[COND] {cond}: {'OK' if ok else res}")
            except Exception as e:
                lg(f"[COND] {cond}: eroare {e}")
        res = self.join_giveaway(ga_id, log)
        if isinstance(res, dict) and (res.get("member") or res.get("status") == "success"):
            lg(f"[OK] JOINED: {name} (id {ga_id})")
            return {"status": "success", "joined": True, "ga_id": ga_id}
        msg = (res.get("error_message") if isinstance(res, dict) else None) or str(res)[:150]
        return {"status": "error", "message": msg}

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

    # ── raffle type classification ──────────────────────────────────────
    # takemyskins always runs exactly 3 active giveaways: 1-day, 3-day, 7-day.
    # type: 1 = daily, 2 = every 3 days, 3 = weekly.
    _DURATION_DAYS_TO_TYPE = {1: 1, 3: 2, 7: 3}

    def _fetch_raffle_types(self, log=None):
        """segment -> type (1/2/3), derived from time_end - time_created."""
        try:
            data = self.list_active_giveaways(log)
        except Exception as e:
            if log:
                log(f"[API] Nu am putut clasifica raflele: {e}")
            return {}
        type_map = {}
        for g in data.get("giveaways") or []:
            segment = g.get("custom_url_segment")
            dur_days = round(((g.get("time_end") or 0) - (g.get("time_created") or 0)) / 86400)
            rtype = self._DURATION_DAYS_TO_TYPE.get(dur_days)
            if segment and rtype:
                type_map[segment] = rtype
        return type_map

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

            # Pre-check: sesiunea contului pin-uit mai e valida?
            # Daca nu, oprim aici cu mesaj clar in loc de "0 rafle" / "NOT JOINED".
            user = self.get_current_user(log)
            if not user:
                log("[AUTH] Sesiune expirata sau invalida pentru acest cont. "
                    "Reexporta cookie-urile din browser si reimporta-le.")
                return "Neautentificat"

            log("[API] Se listeaza raflele active...")
            try:
                data = self.list_active_giveaways(log)
            except Exception as e:
                log(f"[API] Eroare la listarea raflelor: {e}")
                return "Eroare"
            giveaways = data.get("giveaways") or []
            log(f"[API] {len(giveaways)} rafle active gasite.")

            type_map = {}
            for g in giveaways:
                segment = g.get("custom_url_segment")
                dur_days = round(((g.get("time_end") or 0) - (g.get("time_created") or 0)) / 86400)
                rtype = self._DURATION_DAYS_TO_TYPE.get(dur_days)
                if segment and rtype:
                    type_map[segment] = rtype

            joined_count = 0
            already_joined = 0

            for g in giveaways:
                try:
                    gid = g.get("id")
                    segment = g.get("custom_url_segment") or gid
                    name = g.get("name") or f"raffle-{gid}"
                    joined = bool(g.get("joined") or g.get("is_joined"))

                    if joined:
                        already_joined += 1
                        log(f"[OK] Deja inscris: {name}")
                        continue

                    log(f"-> Verific {name}...")

                    res = self.check_and_join_giveaway(segment, log)
                    status = res.get("status")

                    if status == "success":
                        if res.get("already_joined"):
                            already_joined += 1
                        elif res.get("joined"):
                            joined_count += 1
                            rtype = type_map.get(segment)
                            self.db.save_raffle(str(gid), "JOINED", item=name, rtype=rtype)
                            log(f"[JOINED] INTRAT in {name}! (tip {rtype or '?'})")
                    else:
                        msg = res.get("message") or "unknown error"
                        log(f"[SKIP] {name}: {msg}")
                except Exception as e:
                    log(f"Eroare la procesarea raflei: {e}")

            log(f"[API] Gata: {joined_count} noi, {already_joined} deja.")
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

    def get_steam_qr(self, refresh_ui_callback, log_func=None):
        """One-time Steam login via QR. Retries if Chrome becomes unresponsive.
        After successful login the takemyskins session cookies are saved."""
        _log = log_func or (lambda m: print(m))
        self._qr_cancel_event.clear()
        if not self._check_lock.acquire(blocking=False):
            _log("[QR] Lock ocupat, astept verificarea curenta...")
            refresh_ui_callback({"status": "waiting", "error": "Astept sa se termine verificarea curenta..."})
            if not self._check_lock.acquire(timeout=120):
                _log("[ERR] Timeout asteptare lock QR.")
                refresh_ui_callback({"error": "Verificarea dureaza prea mult. Incearca din nou."})
                return

        try:
            last_err = None
            for attempt in range(1, 4):
                try:
                    self._steam_qr_attempt(refresh_ui_callback, _log)
                    return
                except Exception as e:
                    last_err = str(e)
                    unstable = ("Timed out receiving message from renderer" in last_err
                                or "nu a raspuns in" in last_err)
                    if not unstable or attempt >= 3:
                        break
                    _log(f"[WARN] Chrome instabil (incercarea {attempt}/3). Reincerc...")
                    time.sleep(5)
            _log(f"[ERR] QR login esuat: {last_err}")
            refresh_ui_callback({"error": last_err or "Eroare QR necunoscuta"})
        finally:
            self._check_lock.release()

    # Steam cookies that carry the logged-in identity - cleared before every
    # QR attempt so a persistent (trusted) browser profile doesn't silently
    # reuse whichever account was scanned last.
    _STEAM_LOGIN_COOKIE_NAMES = {"steamLoginSecure", "steamRememberLogin", "sessionid"}

    def _steam_qr_attempt(self, refresh_ui_callback, _log=None):
        """Single attempt of the QR login flow. Raises on failure.
        Reuses the persistent Chrome profile (Steam treats it as a trusted
        device, which avoids an extra verification step during the OpenID
        authorize handshake) but scrubs prior Steam login cookies first, so
        each attempt still forces a fresh QR login instead of silently
        reusing whichever account was scanned last."""
        from seleniumbase import Driver

        if not _log:
            _log = lambda m: print(m)

        os.makedirs(self.session_dir, exist_ok=True)
        _log("[AUTH] Pornesc browser pentru Steam QR login...")
        driver = Driver(
            uc=True,
            user_data_dir=self.session_dir,
            headless=True,
            agent=USER_AGENT,
            chromium_arg="--no-sandbox,--disable-dev-shm-usage,--disable-gpu,"
                         "--disable-extensions,--no-first-run,--mute-audio,"
                         "--window-position=-32000,-32000,--window-size=1280,800,"
                         "--disable-features=SameSiteByDefaultCookies,"
                         "CookiesWithoutSameSiteMustBeSecure,"
                         "ThirdPartyCookieDeprecation",
        )
        try:
            driver.set_page_load_timeout(30)

            try:
                all_cookies = driver.execute_cdp_cmd('Network.getAllCookies', {}).get('cookies', [])
                cleared = 0
                for c in all_cookies:
                    if c.get('name') in self._STEAM_LOGIN_COOKIE_NAMES and 'steam' in (c.get('domain') or ''):
                        driver.execute_cdp_cmd('Network.deleteCookies', {
                            'name': c['name'], 'domain': c.get('domain'), 'path': c.get('path', '/'),
                        })
                        cleared += 1
                if cleared:
                    _log(f"[AUTH] Sters {cleared} cookie-uri Steam vechi din profilul persistent")
            except Exception as e:
                _log(f"[WARN] Nu am putut curata cookie-urile Steam vechi: {e}")

            # Pre-visit steamcommunity.com to establish first-party cookie context
            # so cross-domain settoken calls can set cookies there
            try:
                driver.get("https://steamcommunity.com/")
                time.sleep(2)
                _log("[AUTH] steamcommunity.com primed for cookies")
            except Exception:
                pass

            driver.get("https://store.steampowered.com/login/")
            _log("[AUTH] Pagina Steam incarcata, astept QR...")
            time.sleep(6)

            try:
                result = driver.execute_script("""
                    var all = document.querySelectorAll('div.Focusable, button, a.btn_medium, [role="button"]');
                    for (var i = 0; i < all.length; i++) {
                        var t = (all[i].innerText || '').trim();
                        if (t === 'Accept All' || t === 'Got It' || t === 'I Agree' || t === 'OK') {
                            all[i].click();
                            return 'clicked: ' + t;
                        }
                    }
                    for (var j = 0; j < all.length; j++) {
                        var t2 = (all[j].innerText || '').trim().toLowerCase();
                        if (t2.includes('accept all') || t2.includes('accept cookies')) {
                            all[j].click();
                            return 'clicked: ' + t2;
                        }
                    }
                    return 'no banner';
                """)
                if result and result != 'no banner':
                    _log(f"[AUTH] Cookie consent: {result}")
                time.sleep(2)
            except Exception:
                pass

            qr_bytes = None
            for attempt in range(5):
                try:
                    driver.execute_script("""
                        document.querySelectorAll('div.Focusable, button, [role="button"]').forEach(function(el) {
                            var t = (el.innerText || '').trim();
                            if (t === 'Accept All' || t === 'Got It') { el.click(); }
                        });
                        document.querySelectorAll('div').forEach(function(e) {
                            var s = getComputedStyle(e);
                            if ((s.position === 'fixed' || s.position === 'sticky') && e.offsetHeight > 50) {
                                var cls = (e.className || '').toString().toLowerCase();
                                var id = (e.id || '').toLowerCase();
                                if (!cls.includes('qr') && !id.includes('qr') && !cls.includes('login') && !cls.includes('newlogindialog')) {
                                    e.remove();
                                }
                            }
                        });
                    """)
                except Exception:
                    pass

                try:
                    qr_b64 = driver.execute_script("""
                        var img = document.querySelector('img[src*="blob:"]');
                        if (!img || !img.naturalWidth) return null;
                        var scale = 10;
                        var pad = 4;
                        var qw = img.naturalWidth * scale;
                        var qh = img.naturalHeight * scale;
                        var canvas = document.createElement('canvas');
                        canvas.width = qw + pad * 2 * scale;
                        canvas.height = qh + pad * 2 * scale;
                        var ctx = canvas.getContext('2d');
                        ctx.fillStyle = '#ffffff';
                        ctx.fillRect(0, 0, canvas.width, canvas.height);
                        ctx.imageSmoothingEnabled = false;
                        ctx.drawImage(img, pad * scale, pad * scale, qw, qh);
                        return canvas.toDataURL('image/png').split(',')[1];
                    """)
                    if qr_b64 and len(qr_b64) > 100:
                        import base64 as b64mod
                        qr_bytes = b64mod.b64decode(qr_b64)
                        _log(f"[AUTH] QR extras via JS canvas (incercarea {attempt+1})")
                        break
                except Exception:
                    pass

                if not qr_bytes:
                    for sel in ["img[src*='blob:']", "div[style*='--qr-bright-color']", "canvas"]:
                        try:
                            elems = driver.find_elements("css selector", sel)
                            for el in elems:
                                if el.is_displayed():
                                    size = el.size or {}
                                    if size.get("width", 0) >= 100:
                                        shot = el.screenshot_as_png
                                        if shot and len(shot) > 500:
                                            qr_bytes = shot
                                            _log(f"[AUTH] QR extras via screenshot (incercarea {attempt+1})")
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
            _log("[AUTH] QR trimis pe UI. Scaneaza cu Steam Mobile!")

            scanned = False
            scan_timeout = int(os.getenv("STEAM_QR_TIMEOUT", "180"))
            login_url = driver.current_url
            _log(f"[AUTH] Astept scanarea ({scan_timeout}s timeout)...")
            for tick in range(scan_timeout):
                if self._qr_cancel_event.is_set():
                    raise RuntimeError("QR anulat - se genereaza unul nou.")
                try:
                    cur_url = driver.current_url
                    if cur_url != login_url and "/login" not in cur_url:
                        _log(f"[AUTH] Pagina s-a schimbat: {cur_url[:80]}")
                        scanned = True
                        break

                    cookies = driver.get_cookies()
                    names = {c.get("name") for c in cookies}
                    steam_auth_cookies = {"steamLoginSecure", "steamRememberLogin",
                                          "steamMachineAuth"}
                    found = names & steam_auth_cookies
                    if found:
                        _log(f"[OK] Cookie Steam detectat: {found}")
                        scanned = True
                        break

                    page_changed = driver.execute_script("""
                        var el = document.querySelector('[class*="avatarHolder"], [class*="profileLink"], [class*="UserAvatar"]');
                        if (el) return 'avatar_found';
                        var qr = document.querySelector('img[src*="blob:"]');
                        if (!qr) return 'qr_gone';
                        return null;
                    """)
                    if page_changed:
                        _log(f"[AUTH] Pagina s-a schimbat dupa scan: {page_changed}")
                        scanned = True
                        break

                    if tick > 0 and tick % 30 == 0:
                        _log(f"[WAIT] Inca astept scanarea... ({tick}s / {scan_timeout}s)")
                except Exception as e:
                    if tick % 30 == 0:
                        _log(f"[WARN] Eroare la verificare scan: {e}")
                time.sleep(1)

            if not scanned:
                _log("[ERR] Timeout - QR-ul nu a fost scanat in timp util.")
                raise RuntimeError("Timpul a expirat. QR-ul Steam nu a fost scanat.")

            _log("[AUTH] Steam detectat! Astept finalizarea transferului de sesiune...")
            time.sleep(12)

            # Use CDP to get ALL cookies from all domains (including cross-domain settoken results)
            all_cookies_data = {}
            try:
                cdp_result = driver.execute_cdp_cmd('Network.getAllCookies', {})
                for c in cdp_result.get('cookies', []):
                    if c.get('name') == 'steamLoginSecure':
                        domain = c.get('domain', '')
                        all_cookies_data[domain] = c.get('value', '')
                        _log(f"[AUTH] steamLoginSecure pe {domain}")
            except Exception as e:
                _log(f"[WARN] CDP getAllCookies eroare: {e}")
                store_cookies = driver.get_cookies()
                for c in store_cookies:
                    if c.get("name") == "steamLoginSecure":
                        all_cookies_data[c.get("domain", "store.steampowered.com")] = c["value"]

            if not all_cookies_data:
                raise RuntimeError("steamLoginSecure cookie disparut dupa scan.")

            has_community = any("steamcommunity" in d for d in all_cookies_data)
            _log(f"[AUTH] Community cookie: {'DA' if has_community else 'NU'}")

            if not has_community:
                _log("[AUTH] Incerc setare manuala cookie pe steamcommunity.com via CDP...")
                store_val = next(iter(all_cookies_data.values()))
                try:
                    driver.execute_cdp_cmd('Network.setCookie', {
                        'name': 'steamLoginSecure',
                        'value': store_val,
                        'domain': 'steamcommunity.com',
                        'path': '/',
                        'secure': True,
                        'httpOnly': True,
                        'sameSite': 'None',
                    })
                    _log("[AUTH] Cookie setat via CDP pe steamcommunity.com")
                except Exception as e:
                    _log(f"[WARN] CDP setCookie eroare: {e}")

            _log("[AUTH] Navighez la TakeMySkins login...")
            try:
                driver.set_page_load_timeout(60)
                driver.get(f"{API_BASE}/login/steam")
            except Exception as e:
                # The redirect chain (takemyskins -> steamcommunity openid ->
                # back) can outlast the page-load timeout even when the
                # browser is still fine - poll current_url below instead of
                # failing the whole attempt.
                _log(f"[WARN] Navigare lenta, continui cu polling: {e}")
            finally:
                driver.set_page_load_timeout(30)
            time.sleep(8)
            cur_url = driver.current_url
            _log(f"[AUTH] URL dupa redirect: {cur_url[:80]}")

            openid_clicked = False
            for openid_wait in range(90):
                if self._qr_cancel_event.is_set():
                    raise RuntimeError("QR anulat - se genereaza unul nou.")
                cur_url = self._wd_call(lambda: driver.current_url)
                if "steamcommunity.com/openid" in cur_url:
                    if not openid_clicked:
                        try:
                            page_text = self._wd_call(
                                lambda: driver.execute_script("return document.body.innerText || ''"))
                            has_signin = "Sign In" in page_text
                            has_loginform = "loginform" in cur_url or "Sign in" in page_text
                            _log(f"[AUTH] OpenID: signin_btn={has_signin}, loginform={has_loginform}")
                        except Exception:
                            pass
                        try:
                            # A native Selenium click dispatches a real,
                            # trusted mouse event; a JS-triggered .click()
                            # (execute_script) reported success here but the
                            # form never actually submitted - Steam's page
                            # likely ignores untrusted synthetic clicks.
                            # Every WebDriver call here is timeout-guarded:
                            # a frozen renderer can hang a native command
                            # forever otherwise, wedging _check_lock for good.
                            def _try_click():
                                for sel in ('#imageLogin',
                                            'input[type="submit"][value="Sign In"]',
                                            'input[name="action_sign_in"]'):
                                    try:
                                        el = driver.find_element("css selector", sel)
                                        if el.is_displayed():
                                            el.click()
                                            return f"clicked: {sel}"
                                    except Exception:
                                        continue
                                try:
                                    form = driver.find_element("css selector", 'form[action*="openid"]')
                                    submit_btn = form.find_element("css selector", 'input[type="submit"]')
                                    submit_btn.click()
                                    return "form-submit"
                                except Exception:
                                    return None

                            clicked = self._wd_call(_try_click)
                            if clicked:
                                _log(f"[AUTH] OpenID confirm: {clicked}")
                                openid_clicked = True
                                time.sleep(8)
                                continue
                            else:
                                _log("[WARN] OpenID: nu am gasit buton Sign In")
                        except Exception as e:
                            _log(f"[WARN] OpenID click eroare: {e}")
                elif "takemyskins" in cur_url:
                    _log(f"[OK] Redirectionat la TakeMySkins: {cur_url[:80]}")
                    break
                if openid_wait > 0 and openid_wait % 20 == 0:
                    _log(f"[WAIT] OpenID flow... URL: {cur_url[:80]}")
                time.sleep(1)

            cookies = None
            for wait_tick in range(30):
                try:
                    current = self._wd_call(lambda: driver.get_cookies())
                    names = {c.get("name") for c in current}
                    if "takemyskins_session" in names:
                        cookies = current
                        _log("[OK] Cookie TakeMySkins detectat!")
                        break
                except Exception:
                    pass
                if wait_tick > 0 and wait_tick % 10 == 0:
                    cur = self._wd_call(lambda: driver.current_url)
                    _log(f"[WAIT] Astept sesiune TakeMySkins... URL: {cur[:80]}")
                time.sleep(1)

            if not cookies:
                cur = driver.current_url
                _log(f"[ERR] TakeMySkins nu a setat sesiunea. URL final: {cur[:100]}")
                raise RuntimeError("Login Steam OK, dar TakeMySkins nu a setat sesiunea. "
                                   "Incearca din nou sau logheaza-te manual in browser.")

            # Save under a placeholder key first so get_current_user() - the
            # same proven, retrying call the dashboard already polls - can
            # load these exact cookies through the normal session-building
            # path, then re-key once we know the real SteamID.
            self.save_cookies(cookies, log=_log, steam_id="pending")
            user = self.get_current_user(log=_log)
            steam_id = str(user["steam_id"]) if user and user.get("steam_id") else None
            nickname = user.get("nickname") if user else None
            if steam_id:
                self.save_cookies(cookies, log=_log, steam_id=steam_id, nickname=nickname)
                self.db.clear_session("pending")
            else:
                steam_id = "pending"
                _log("[WARN] Nu am putut identifica contul dupa login; sesiunea a ramas sub cheia temporara.")
            label = nickname or steam_id
            refresh_ui_callback({"status": "success", "message": f"Sesiune salvata pentru {label}!"})
            _log(f"[OK] Sesiune TakeMySkins salvata cu succes ({label})!")
        finally:
            if driver:
                try:
                    # quit() can hang just as badly as any other WebDriver
                    # command if Chrome is frozen - run it on a daemon thread
                    # so a stuck browser can't wedge this attempt forever.
                    self._wd_call(driver.quit, timeout=10)
                except Exception:
                    pass
