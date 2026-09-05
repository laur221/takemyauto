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

    # ── API methods ──────────────────────────────────────────────────────

    def fetch_root(self, log=None):
        session = self._ensure_session(log)
        return self._set_csrf(session, log)

    def list_active_giveaways_from_html(self, log=None):
        """
        Folosește Playwright headless browser pentru a scrape rafle și a intra în ele.
        API-ul TakeMySkins e blocat pentru bots, deci folosim browser real.
        """
        try:
            from playwright.sync_api import sync_playwright
            import json
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                
                # Încarcă cookies din Redis (Upstash)
                cookies = self.load_cookies(log)
                if cookies:
                    context.add_cookies(cookies)
                    if log:
                        log(f"[PW] Cookies incarcate din Redis ({len(cookies)} cookies)")
                
                page = context.new_page()
                page.goto("https://takemyskins.com/", wait_until="networkidle", timeout=30000)
                
                # Așteaptă ca raflele să se încarce (Vue.js e lent)
                page.wait_for_timeout(5000)
                
                # Extrage raflele
                giveaways = page.evaluate("""() => {
                    const links = Array.from(document.querySelectorAll('a[href*="/giveaway"]'));
                    return links.map(l => ({
                        url: l.href,
                        segment: l.href.split('/').pop(),
                        isJoined: l.textContent.includes("You're in")
                    }));
                }""")
                
                if log:
                    log(f"[PW] Gasite {len(giveaways)} rafle pe site")
                
                # Convertește în format compatibil
                result_giveaways = []
                for g in giveaways:
                    result_giveaways.append({
                        "id": g['segment'],
                        "custom_url_segment": g['segment'],
                        "name": f"Raffle {g['segment'][:8]}",
                        "joined": g['isJoined'],
                        "is_joined": g['isJoined']
                    })
                
                browser.close()
                return {"giveaways": result_giveaways, "total": {"active_total": len(result_giveaways)}}
                
        except Exception as e:
            if log:
                log(f"[PW] Eroare Playwright: {e}")
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
        """
        Intră în raflă folosind Playwright (API-ul e blocat).
        Completează automat condițiile și apasă Join.
        """
        try:
            from playwright.sync_api import sync_playwright
            import json
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                
                # Încarcă cookies din Redis (Upstash)
                cookies = self.load_cookies(log)
                if cookies:
                    context.add_cookies(cookies)
                    if log:
                        log(f"[PW] Cookies incarcate din Redis pentru join ({len(cookies)} cookies)")
                
                page = context.new_page()
                page.goto(f"https://takemyskins.com/giveaways/{ref}", wait_until="networkidle", timeout=30000)
                
                # Așteptă ca Vue.js să se încarce
                page.wait_for_timeout(5000)
                
                # Verifică dacă deja înscris
                is_joined = page.evaluate("""() => {
                    return document.body.innerText.includes("You're in");
                }""")
                
                if is_joined:
                    browser.close()
                    return {"status": "success", "message": "Already joined"}
                
                # Completează condițiile (click pe check pentru fiecare task)
                try:
                    check_buttons = page.locator('button:has-text("Check"), button:has-text("Verify")').all()
                    for btn in check_buttons:
                        try:
                            if btn.is_visible(timeout=1000):
                                btn.click()
                                page.wait_for_timeout(500)
                        except:
                            pass
                    page.wait_for_timeout(2000)
                except:
                    pass
                
                # Click pe butonul de join
                try:
                    join_btn = page.locator('button:has-text("Join"), button:has-text("Enter"), button:has-text("Participate")').first
                    if join_btn.is_visible(timeout=5000):
                        join_btn.click()
                        page.wait_for_timeout(2000)
                        browser.close()
                        return {"status": "success"}
                    else:
                        browser.close()
                        return {"status": "error", "error_message": "Join button not found"}
                except Exception as e:
                    browser.close()
                    return {"status": "error", "error_message": str(e)}
                    
        except Exception as e:
            # Fallback la API vechi dacă Playwright eșuează
            if log:
                log(f"[PW] Eroare Playwright join, fallback la API: {e}")
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

    def check_and_join_giveaway_pw(self, segment, log=None):
        """
        Join raffle - robust flow:
        1. Navigate to giveaway page
        2. Wait for Vue to load precondition items
        3. Check if already joined ("You're in!")
        4. Find non-completed condition items
        5. For each pending item, click its action button ("Share"/"Link") and close popup
        6. Verify "You're in!" appears
        """
        try:
            from playwright.sync_api import sync_playwright
            
            if log:
                log(f"[DEBUG] Starting join flow for {segment}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
                )
                context = browser.new_context()
                
                cookies = self.load_cookies(log)
                if cookies:
                    context.add_cookies(cookies)
                    if log:
                        log(f"[DEBUG] Loaded {len(cookies)} cookies into Playwright context")
                
                page = context.new_page()
                if log:
                    log(f"[DEBUG] Navigating to {segment}")
                
                page.goto(f"https://takemyskins.com/giveaways/{segment}", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)
                
                curr_url = page.url
                curr_title = page.title()
                body_sample = page.evaluate("""() => (document.body ? document.body.innerText : '').slice(0, 300)""")
                
                if log:
                    log(f"[DEBUG] Page state -> URL: {curr_url} | Title: {curr_title} | Text: {body_sample[:100]}")
                
                # Wait for Vue.js app to mount preconditions section
                if log:
                    log(f"[DEBUG] Waiting for Vue preconditions section...")
                
                try:
                    page.wait_for_function(
                        "() => document.body && (document.body.innerText.includes('Share the raffle') || document.body.innerText.includes('Link your Discord') || document.body.innerText.includes(\"You're in\") || document.body.innerText.includes('preconditions'))",
                        timeout=15000
                    )
                    if log:
                        log(f"[DEBUG] Preconditions section loaded successfully")
                except Exception as e:
                    body_fail = page.evaluate("""() => (document.body ? document.body.innerText : '').replace(/\\n+/g, ' ').slice(0, 300)""")
                    if log:
                        log(f"[DEBUG] Timeout waiting for preconditions. Current text: {body_fail}")
                
                page.wait_for_timeout(2000)
                
                # Check if already joined
                is_joined = page.evaluate("""() => document.body.innerText.includes("You're in")""")
                if is_joined:
                    if log:
                        log(f"[DEBUG] Already joined: {segment}")
                        log(f"[PW] Already joined: {segment}")
                    browser.close()
                    return {"status": "success", "already_joined": True}
                
                # Loop through pending condition cards (up to 10 attempts for Share + Check pairs)
                for attempt in range(10):
                    # Find first pending condition card
                    pending_info = page.evaluate("""() => {
                        const cards = Array.from(document.querySelectorAll('div')).filter(d => {
                            const hasAction = d.querySelector('div[class*="action"], p[class*="action"], [class*="action"]');
                            const t = d.innerText || '';
                            return hasAction && t.length < 150 && (t.includes('Share the raffle') || t.includes('Link your Discord') || t.includes('Link and confirm'));
                        });
                        
                        const pending = cards.filter(c => !c.innerText.includes('DONE'));
                        if (pending.length === 0) {
                            return { allDone: true, count: cards.length };
                        }
                        
                        const first = pending[0];
                        const actionEl = first.querySelector('div[class*="action"], p[class*="action"], [class*="action"]');
                        const actionText = actionEl ? actionEl.innerText.trim() : '';
                        return {
                            allDone: false,
                            title: first.innerText.replace(/\\n+/g, ' ').slice(0, 60),
                            actionText: actionText,
                            pendingCount: pending.length,
                            totalCount: cards.length
                        };
                    }""")
                    
                    if log:
                        log(f"[DEBUG] Status attempt {attempt+1}: {pending_info}")
                    
                    if pending_info.get('allDone'):
                        if log:
                            log(f"[DEBUG] All condition cards are DONE!")
                        break
                    
                    cond_title = pending_info.get('title', 'Condition')
                    action_text = pending_info.get('actionText', '')
                    
                    if log:
                        log(f"[DEBUG] Processing pending condition: {cond_title}")
                        log(f"[PW] Processing {cond_title[:30]}...")
                    
                    # Click the action button on the first non-DONE card
                    try:
                        is_check = "check" in action_text.lower()
                        if not is_check:
                            try:
                                with context.expect_page(timeout=3000) as new_page_info:
                                    page.evaluate("""() => {
                                        const cards = Array.from(document.querySelectorAll('div')).filter(d => {
                                            const hasAction = d.querySelector('div[class*="action"], p[class*="action"], [class*="action"]');
                                            const t = d.innerText || '';
                                            return hasAction && t.length < 150 && (t.includes('Share the raffle') || t.includes('Link your Discord') || t.includes('Link and confirm'));
                                        });
                                        const firstPending = cards.find(c => !c.innerText.includes('DONE'));
                                        if (firstPending) {
                                            const btn = firstPending.querySelector('div[class*="action"], p[class*="action"], [class*="action"]') || firstPending;
                                            btn.click();
                                        }
                                    }""")
                                popup_page = new_page_info.value
                                if popup_page:
                                    popup_url = getattr(popup_page, 'url', '')
                                    if log:
                                        log(f"[DEBUG] Opened popup: {popup_url[:50]}")
                                    page.wait_for_timeout(1000)
                                    popup_page.close()
                                    if log:
                                        log(f"[DEBUG] Closed popup tab")
                            except Exception:
                                if log:
                                    log(f"[DEBUG] Clicked Share/Link action")
                        else:
                            # Inline "Check" button click
                            page.evaluate("""() => {
                                const cards = Array.from(document.querySelectorAll('div')).filter(d => {
                                    const hasAction = d.querySelector('div[class*="action"], p[class*="action"], [class*="action"]');
                                    const t = d.innerText || '';
                                    return hasAction && t.length < 150 && (t.includes('Share the raffle') || t.includes('Link your Discord') || t.includes('Link and confirm'));
                                });
                                const firstPending = cards.find(c => !c.innerText.includes('DONE'));
                                if (firstPending) {
                                    const btn = firstPending.querySelector('div[class*="action"], p[class*="action"], [class*="action"]') || firstPending;
                                    btn.click();
                                }
                            }""")
                            if log:
                                log(f"[DEBUG] Clicked inline Check button")
                    except Exception as popup_err:
                        if log:
                            log(f"[DEBUG] Click error: {str(popup_err)[:60]}")
                    
                    page.wait_for_timeout(1500)
                
                # Final check after conditions
                page.wait_for_timeout(3000)
                is_joined_final = page.evaluate("""() => document.body.innerText.includes("You're in")""")
                
                if log:
                    log(f"[DEBUG] Final check result: {'JOINED!' if is_joined_final else 'NOT JOINED'}")
                
                browser.close()
                
                if is_joined_final:
                    if log:
                        log(f"[OK] JOINED: {segment}")
                    return {"status": "success", "joined": True}
                else:
                    if log:
                        log(f"[WARN] Conditions completed but not joined: {segment}")
                    return {"status": "success", "joined": False}
                    
        except Exception as e:
            if log:
                log(f"[DEBUG] EXCEPTION in check_and_join_giveaway_pw: {str(e)[:150]}")
                log(f"[PW] Error: {segment}: {e}")
            return {"status": "error", "message": str(e)}


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
                    
                    # Folosește DOAR Playwright pentru a verifica și intra în raflă
                    res = self.check_and_join_giveaway_pw(segment, log)
                    status = res.get("status")
                    
                    if status == "success":
                        if res.get("already_joined"):
                            already_joined += 1
                            log(f"[OK] Deja inscris (PW): {name}")
                        elif res.get("joined"):
                            joined_count += 1
                            self.db.save_raffle(str(gid), "JOINED", item=name)
                            log(f"[JOINED] INTRAT in {name}!")
                        else:
                            log(f"[INFO] Join initiat: {name}")
                    else:
                        msg = res.get("message") or "unknown error"
                        log(f"[SKIP] {name}: {msg}")
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
            headless=True,
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
            
            # Inchide cookie consent banner daca apare
            try:
                cookie_buttons = driver.find_elements("xpath", "//button[contains(text(), 'I Agree') or contains(text(), 'Accept') or contains(text(), 'OK')]")
                for btn in cookie_buttons:
                    try:
                        if btn.is_displayed():
                            btn.click()
                            print("[QR] Cookie banner inchis")
                            time.sleep(1)
                            break
                    except:
                        pass
            except:
                pass

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
                                        # Crop poza la QR doar (elimina spatiul din jurul QR-ului)
                                        from PIL import Image
                                        from io import BytesIO
                                        img = Image.open(BytesIO(shot))
                                        # Crop la 80% din centru pentru a elimina spatiul
                                        w, h = img.size
                                        margin_x = int(w * 0.1)
                                        margin_y = int(h * 0.1)
                                        img_crop = img.crop((margin_x, margin_y, w - margin_x, h - margin_y))
                                        bio = BytesIO()
                                        img_crop.save(bio, format='PNG')
                                        qr_bytes = bio.getvalue()
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
