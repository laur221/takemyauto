from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import threading
import os
import tempfile


class RaffleBot:
    def __init__(self, db):
        self.db = db
        self.session_dir = "./user_session"
        self._check_lock = threading.Lock()
        self._scheduler_thread = None
        self._scheduler_stop_event = threading.Event()

    # ── helpers ──────────────────────────────────────────────────────────

    def _is_logged_in(self, driver, log):
        """Detect if user is authenticated on takemyskins.com.
        
        Checks multiple signals in priority order:
        1. Profile/avatar element visible
        2. No "login" button on the page
        3. Cookie presence for Steam/takemyskins session
        Returns True if logged in, False otherwise.
        """
        try:
            # Signal 1: profile avatar / username element
            for sel in [
                "img[alt*='avatar']", "img[class*='avatar']",
                "[class*='user']", "[class*='profile']",
                "a[href*='profile']", "[data-testid*='user']",
            ]:
                try:
                    if driver.is_element_visible(sel):
                        return True
                except Exception:
                    continue

            # Signal 2: cookies that indicate a Steam session
            cookies = driver.get_cookies()
            steam_cookies = [c for c in cookies if "steam" in c.get("domain", "").lower()
                             or "steam" in c.get("name", "").lower()]
            if steam_cookies:
                return True

            # Signal 3: no login/sign-in link visible
            login_indicators = [
                "Login", "Sign in", "Log in", "Sign-in", "Log-in"
            ]
            page_text = driver.execute_script("return document.body.innerText || '';")
            has_login_link = any(indicator.lower() in page_text.lower() for indicator in login_indicators)
            if not has_login_link:
                return True
        except Exception as e:
            log(f"[AUTH] Login detection error: {e}")

        return False

    def _find_join_button(self, driver, log):
        """Find and click the Join button using robust strategies.
        
        Strategy order:
        1. XPath text match (works regardless of CSS class names)
        2. Button text content via JavaScript
        3. Common CSS patterns (fallback)
        """
        strategies = [
            # Strategy 1: XPath by visible text (most resilient)
            ("xpath", "//button[contains(translate(text(), 'JOIN', 'join'), 'join')]"),
            ("xpath", "//button[contains(translate(., 'JOIN', 'join'), 'join')]"),
            ("xpath", "//a[contains(translate(text(), 'JOIN', 'join'), 'join')]"),
            ("xpath", "//*[contains(translate(text(), 'JOIN', 'join'), 'join') and (self::button or self::a)]"),
            # Strategy 2: CSS with common join patterns
            ("css", "button[class*='join']"),
            ("css", "a[class*='join']"),
            ("css", "[data-action*='join']"),
            ("css", "[data-testid*='join']"),
            # Strategy 3: Broad button matches (last resort)
            ("css", "button._base_g0vst_1"),
        ]

        for strategy_type, selector in strategies:
            try:
                if strategy_type == "xpath":
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)

                for el in elements:
                    if not el.is_displayed():
                        continue
                    text = (el.text or "").strip().lower()
                    if "join" in text or "enter" in text or "participate" in text:
                        try:
                            el.click()
                            log(f"✅ Join button clicked via {strategy_type}: '{selector}'")
                            return True
                        except Exception:
                            # Retry with JS click
                            try:
                                driver.execute_script("arguments[0].click();", el)
                                log(f"✅ Join button JS-clicked via {strategy_type}: '{selector}'")
                                return True
                            except Exception:
                                continue
            except Exception:
                continue

        # Last resort: JavaScript-based button search
        try:
            result = driver.execute_script("""
                const buttons = document.querySelectorAll('button, a, [role="button"]');
                for (const btn of buttons) {
                    const text = (btn.textContent || '').trim().toLowerCase();
                    if (text.includes('join') || text.includes('enter')) {
                        if (btn.offsetParent !== null) {
                            btn.click();
                            return 'clicked';
                        }
                    }
                }
                return 'not_found';
            """)
            if result == "clicked":
                log("✅ Join button clicked via JavaScript fallback")
                return True
        except Exception as e:
            log(f"JS fallback error: {e}")

        return False

    # ── main methods ─────────────────────────────────────────────────────

    def run_check(self, is_headless=True, log_func=None):
        def log(msg):
            if log_func:
                log_func(msg)
            print(msg)

        if not self._check_lock.acquire(blocking=False):
            log("O verificare ruleaza deja. Sar peste executia paralela.")
            return "Deja ruleaza"

        driver = Driver(
            uc=True,
            user_data_dir=self.session_dir,
            headless=is_headless,
            agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            chromium_arg="--no-sandbox,--disable-dev-shm-usage,--disable-gpu,"
                         "--disable-extensions,--memory-pressure-off"
        )
        try:
            log("Se deschide browserul...")

            # Step 1: Navigate to the domain FIRST (required by WebDriver for cookie injection)
            driver.get("https://takemyskins.com/")
            time.sleep(2)

            # Step 2: Restore session from Redis (cookies need domain to be loaded)
            restored = self.restore_session_from_redis(driver, log)
            if restored:
                # Refresh so cookies take effect
                driver.get("https://takemyskins.com/")
                time.sleep(3)

            # Step 3: Check login state
            logged_in = self._is_logged_in(driver, log)
            log(f"[AUTH] Login status: {'LOGGED IN' if logged_in else 'NOT LOGGED IN'}")

            if not is_headless:
                log("Astept sa te loghezi manual...")
                return "Login Manual Deschis"

            if not logged_in:
                log("[AUTH] ⚠️ NOT LOGGED IN - raffle check will likely fail.")
                log("[AUTH] Please use the QR login button in the web UI first.")
                # Still try, but log warning

            # Step 4: Find raffle cards using generic selectors (not auto-generated CSS classes)
            time.sleep(3)
            card_selectors = [
                "a[href*='/raffle/']",
                "a[href*='/giveaway/']",
                "[class*='raffle'] a",
                "[class*='card'] a[href]",
                "a[class*='_link']",          # CSS module fallback
                "a[href*='takemyskins.com']",  # any internal link
            ]

            cards = []
            for sel in card_selectors:
                found = driver.find_elements("css selector", sel)
                if found:
                    cards = found
                    break

            # Filter to likely raffle cards (have link + look like raffle entries)
            raffle_cards = []
            seen_hrefs = set()
            for c in cards:
                href = c.get_attribute("href") or ""
                if not href or href in seen_hrefs:
                    continue
                if any(kw in href.lower() for kw in ["raffle", "giveaway", "competition"]):
                    seen_hrefs.add(href)
                    raffle_cards.append(c)

            if not raffle_cards:
                # Broader fallback: take any linked card that looks substantial
                for c in cards:
                    href = c.get_attribute("href") or ""
                    if href and href not in seen_hrefs and href.startswith("http"):
                        seen_hrefs.add(href)
                        raffle_cards.append(c)

            log(f"Am gasit {len(raffle_cards)} rafle pe pagina.")

            # Step 5: Process each raffle
            for card in raffle_cards:
                try:
                    card_text = (card.text or "").lower()
                    if "you're in" in card_text or "entered" in card_text:
                        log("Sunt deja inscris la o rafla, trec mai departe.")
                        continue
                except Exception:
                    pass

                link = card.get_attribute("href")
                if not link:
                    continue

                log(f"Incerc sa intru in rafla: {link}")

                try:
                    driver.execute_script(f"window.open('{link}', '_blank');")
                    driver.switch_to.window(driver.window_handles[-1])
                    time.sleep(3)

                    joined = self._find_join_button(driver, log)

                    if joined:
                        self.db.save_raffle(link, "JOINED")
                        time.sleep(2)
                    else:
                        log(f"Nu am gasit butonul de Join pentru {link} "
                            f"(posibil task-uri sau deja inscris)")
                        self.db.save_raffle(link, "JOIN_NOT_FOUND")

                except Exception as e:
                    log(f"Eroare la procesarea raflei {link}: {str(e)}")
                finally:
                    if len(driver.window_handles) > 1:
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])

            # Step 6: Check wins
            self.check_wins_internal(driver, log)

            # Step 7: Save session to Redis
            try:
                session_data = {
                    "cookies": driver.get_cookies(),
                    "last_check": time.time(),
                    "status": "logged_in" if logged_in else "unknown",
                }
                self.db.save_session(session_data)
                log("[SESSION] ✅ Session saved to Redis (survives restart!)")
            except Exception as e:
                log(f"[SESSION] ⚠️ Could not save session: {e}")

            return "Gata!"
        except Exception as e:
            log(f"Eroare generala: {str(e)}")
            return "Eroare"
        finally:
            try:
                driver.quit()
            except Exception:
                pass
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
            log("[SCHEDULER] Background scheduler started "
                f"(interval: {interval_seconds} seconds)")
            while not self._scheduler_stop_event.is_set():
                local_session_exists = os.path.exists(os.path.join(self.session_dir, "Default"))
                if not self.db.session_exists() and not local_session_exists:
                    log("[SCHEDULER] Nu exista sesiune salvata. Astept login Steam inainte de verificari automate.")
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

    # ── wins ─────────────────────────────────────────────────────────────

    def check_wins_internal(self, driver, log):
        try:
            log("Verific daca exista castiguri noi pe profil...")
            driver.get("https://takemyskins.com/profile")
            time.sleep(5)

            prizes = driver.find_elements("css selector",
                                          "[class*='prize'], [class*='won'], [class*='win']")

            if prizes:
                log(f"Am gasit {len(prizes)} posibile premii pe pagina.")
                for prize in prizes:
                    prize_text = prize.text
                    if not prize_text:
                        continue
                    prize_lower = prize_text.lower()
                    if any(kw in prize_lower for kw in ["claim", "won", "win", "prize"]):
                        self.db.save_raffle(
                            f"Win_{int(time.time())}", "WON",
                            item=prize_text[:50]
                        )
                        log(f"Castig nou detectat: {prize_text[:30]}")
            else:
                log("Nu am detectat castiguri noi in aceasta sesiune.")

        except Exception as e:
            log(f"Eroare la verificarea castigurilor: {str(e)}")

    def close_extra_tabs(self, driver):
        while len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
            driver.close()
        driver.switch_to.window(driver.window_handles[0])

    # ── session ──────────────────────────────────────────────────────────

    def restore_session_from_redis(self, driver, log):
        """Restore browser session from Redis.
        
        IMPORTANT: Must be called AFTER driver.get() so the domain is loaded.
        After adding cookies, the caller should refresh the page.
        """
        try:
            session_data = self.db.get_session()
            if not session_data:
                log("[SESSION] ℹ️ No saved session in Redis")
                return False

            if "cookies" in session_data:
                for cookie in session_data["cookies"]:
                    try:
                        # Validate cookie before adding
                        if "name" not in cookie or "value" not in cookie:
                            continue
                        driver.add_cookie(cookie)
                    except Exception:
                        pass  # Some cookies may fail on domain mismatch

            log("[SESSION] ✅ Restored from Redis - NO re-login needed!")
            return True
        except Exception as e:
            log(f"[SESSION] ⚠️ Could not restore session: {e}")
            return False

    # ── steam QR ─────────────────────────────────────────────────────────

    def get_steam_qr(self, refresh_ui_callback):
        """Generate Steam QR code and push raw PNG bytes to the UI callback.
        
        Uses undetected-chromedriver mode to bypass Steam protections.
        """
        if not self._check_lock.acquire(blocking=False):
            print("[QR] Browserul este ocupat cu o alta verificare. Incearca din nou in cateva minute.")
            refresh_ui_callback(None)
            return

        os.makedirs(self.session_dir, exist_ok=True)
        temp_qr_path = os.path.join(tempfile.gettempdir(), f"steam_qr_{int(time.time())}.png")
        driver = None
        try:
            driver = Driver(
                uc=True,
                user_data_dir=self.session_dir,
                headless=True,
                no_sandbox=True,
                disable_gpu=True,
                chromium_arg="--no-sandbox,--disable-dev-shm-usage,--disable-gpu,"
                             "--disable-extensions,--memory-pressure-off",
            )
            print("[QR] Accesez pagina de login Steam...")
            driver.get("https://store.steampowered.com/login/")
            time.sleep(7)

            qr_selectors = [
                "div[class*='login_QR_'] canvas",
                "div[class*='qr_code'] img",
                "img[class*='qrcode']",
                "canvas[class*='qr']",
                "div[class*='QR'] img",
                "div[class*='qrcode'] canvas",
                "img[src*='qr']",
                "canvas",
            ]

            qr_found = False
            for selector in qr_selectors:
                try:
                    if driver.is_element_visible(selector):
                        print(f"[QR] QR gasit cu selector: {selector}")
                        driver.save_element_screenshot(selector, temp_qr_path)

                        with open(temp_qr_path, "rb") as f:
                            qr_bytes = f.read()

                        refresh_ui_callback(qr_bytes)
                        qr_found = True
                        print(f"[QR] Trimis pe UI: {len(qr_bytes)} bytes raw")
                        break
                except Exception as e:
                    print(f"[QR] Selector esuat ({selector}): {e}")
                    continue

            if not qr_found:
                print("[QR] Niciun QR Code gasit - posibil deja logat")
                refresh_ui_callback(None)
                return

            print("[QR] Astept scanarea QR-ului (60 sec timeout)...")
            for attempt in range(60):
                try:
                    url = driver.current_url or ""
                    if ("steamcommunity.com/id/" in url
                            or "steamcommunity.com/profiles/" in url
                            or driver.is_element_visible(".persona")):
                        print("[QR] ✓ Logare reusita prin QR!")
                        break
                except Exception:
                    pass
                time.sleep(1)
                if attempt % 10 == 0:
                    print(f"[QR] Inca astept... ({attempt}/60)")

        except Exception as e:
            print(f"[QR] Eroare critica: {str(e)}")
            refresh_ui_callback(None)
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
            try:
                os.remove(temp_qr_path)
            except Exception:
                pass
            self._check_lock.release()
