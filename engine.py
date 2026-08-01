from seleniumbase import Driver
import time
import threading
import os


class RaffleBot:
    def __init__(self, db):
        self.db = db
        self.session_dir = "./user_session"
        self._check_lock = threading.Lock()
        self._scheduler_thread = None
        self._scheduler_stop_event = threading.Event()

    # În engine.py, modifică metoda run_check:
    def run_check(self, is_headless=True, log_func=None):
        def log(msg):
            if log_func: log_func(msg)
            print(msg)

        if not self._check_lock.acquire(blocking=False):
            log("O verificare rulează deja. Sar peste execuția paralelă.")
            return "Deja rulează"

        # Optimizări critice pentru Render Free (512MB RAM)
        driver = Driver(
            uc=True, 
            user_data_dir=self.session_dir, 
            headless=is_headless,
            agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            # Dezactivăm chestiile inutile pentru a economisi RAM
            chromium_arg="--no-sandbox,--disable-dev-shm-usage,--disable-gpu,--disable-extensions,--memory-pressure-off"
        )
        try:
            log("Se deschide browserul...")
            driver.get("https://takemyskins.com/")

            # Try to restore session from Redis (survives restart!)
            self.restore_session_from_redis(driver, log)
            time.sleep(3)

            if not is_headless:
                log("Aștept să te loghezi manual...")
                return "Login Manual Deschis"

            time.sleep(5)
            cards = driver.find_elements("css selector", "a._link_ro95i_15")
            log(f"Am găsit {len(cards)} rafle pe pagină.")

            for card in cards:
                if "You're in!" in card.text:
                    log("Sunt deja înscris la o raflă, trec mai departe.")
                    continue

                link = card.get_attribute("href")
                log(f"Încerc să intru în rafla: {link}")
                
                try:
                    # Deschidem rafla într-un tab nou
                    driver.execute_script(f"window.open('{link}', '_blank');")
                    driver.switch_to.window(driver.window_handles[-1])
                    time.sleep(3)
                    
                    # Căutăm butonul de Join
                    # Folosim un selector mai robust bazat pe text și clasele observate
                    join_selectors = [
                        'button:contains("Join")',
                        'button._base_g0vst_1',
                        'button[class*="join"]'
                    ]
                    
                    joined = False
                    for selector in join_selectors:
                        if driver.is_element_visible(selector):
                            driver.click(selector)
                            log(f"Am apăsat pe Join în rafla: {link}")
                            self.db.save_raffle(link, "JOINED")
                            joined = True
                            time.sleep(2)
                            break
                    
                    if not joined:
                        log(f"Nu am găsit butonul de Join pentru {link} (posibil task-uri sau deja înscris)")
                        self.db.save_raffle(link, "JOIN_NOT_FOUND")

                except Exception as e:
                    log(f"Eroare la procesarea raflei {link}: {str(e)}")
                finally:
                    # Închidem tab-ul și ne întoarcem la lista principală
                    if len(driver.window_handles) > 1:
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])

            # După ce terminăm raflele, verificăm și câștigurile
            self.check_wins_internal(driver, log)

            # Salvez sesiunea în Redis (SURVIVES RESTART!)
            try:
                session_data = {
                    "cookies": driver.get_cookies(),
                    "localStorage": driver.execute_script("return Object.keys(localStorage);"),
                    "sessionStorage": driver.execute_script("return Object.keys(sessionStorage);"),
                    "last_check": time.time(),
                    "status": "logged_in"
                }
                self.db.save_session(session_data)
                log("[SESSION] ✅ Session saved to Redis (survives restart!)")
            except Exception as e:
                log(f"[SESSION] ⚠️ Could not save session: {e}")

            return "Gata!"
        except Exception as e:
            log(f"Eroare generală: {str(e)}")
            return "Eroare"
        finally:
            driver.quit()
            self._check_lock.release()

    def start_background_scheduler(self, interval_seconds=21600, is_headless=True, log_func=None):
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            return

        self._scheduler_stop_event.clear()

        def log(msg):
            if log_func:
                log_func(msg)
            print(msg)

        def worker():
            while not self._scheduler_stop_event.is_set():
                log("Pornesc verificarea automată a raflelor (Background Task)...")
                try:
                    self.run_check(is_headless=is_headless, log_func=log_func)
                except Exception as e:
                    log(f"Eroare în scheduler: {e}")
                self._scheduler_stop_event.wait(interval_seconds)

        self._scheduler_thread = threading.Thread(target=worker, daemon=True)
        self._scheduler_thread.start()

    def stop_background_scheduler(self):
        self._scheduler_stop_event.set()

    def check_wins_internal(self, driver, log):
        try:
            log("Verific dacă există câștiguri noi pe profil...")
            driver.get("https://takemyskins.com/profile") # Sau URL-ul specific de premii dacă există
            time.sleep(5)
            
            # Exemplu de logică pentru identificarea premiilor
            # Trebuie adaptat în funcție de HTML-ul real al paginii de profil
            # Presupunem că există elemente cu clasa '_item_name' pentru obiectele câștigate
            prizes = driver.find_elements("css selector", "[class*='prize'], [class*='won']")
            
            if prizes:
                log(f"Am găsit {len(prizes)} posibile premii pe pagină.")
                for prize in prizes:
                    prize_text = prize.text
                    if "Claim" in prize_text or "Won" in prize_text:
                        # Extragem un nume generic sau ID pentru a nu dubla în DB
                        self.db.save_raffle(f"Win_{int(time.time())}", "WON", item=prize_text[:50])
                        log(f"Câștig nou detectat: {prize_text[:30]}")
            else:
                log("Nu am detectat câștiguri noi în această sesiune.")
                
        except Exception as e:
            log(f"Eroare la verificarea câștigurilor: {str(e)}")

    def close_extra_tabs(self, driver):
        while len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
            driver.close()
        driver.switch_to.window(driver.window_handles[0])

    def restore_session_from_redis(self, driver, log):
        """Restore browser session from Redis if available (NO re-login needed!)
        
        Survives dyno restart - persistent across 30 days!
        """
        try:
            session_data = self.db.get_session()
            if session_data:
                # Restore cookies
                if "cookies" in session_data:
                    for cookie in session_data["cookies"]:
                        try:
                            driver.add_cookie(cookie)
                        except:
                            pass  # Some cookies may fail, that's OK
                
                log("[SESSION] ✅ Restored from Redis - NO re-login needed!")
                return True
            else:
                log("[SESSION] ℹ️ No saved session in Redis")
                return False
        except Exception as e:
            log(f"[SESSION] ⚠️ Could not restore session: {e}")
            return False

    def get_steam_qr(self, refresh_ui_callback):
        """Generează QR Code Steam și îl trimite pe web în format base64.
        
        Optimizări:
        - Timeout mare pentru rendering QR
        - PNG encoding optimizat pentru web
        - Eroare graceful dacă QR nu e găsit
        """
        driver = Driver(uc=True, user_data_dir=self.session_dir, headless=True)
        try:
            print("[QR] Accesez pagina de login Steam...")
            driver.get("https://store.steampowered.com/login/")
            time.sleep(7)  # Așteptare mai lungă pentru rendering QR

            # Selectoare alternative pentru QR în 2026
            qr_selectors = [
                "div[class*='login_QR_'] canvas",
                "div[class*='qr_code'] img",
                "img[class*='qrcode']",
                "canvas[class*='qr']",
                "div[class*='QR'] img"
            ]

            qr_found = False
            for selector in qr_selectors:
                try:
                    if driver.is_element_visible(selector):
                        print(f"[QR] QR găsit cu selector: {selector}")
                        driver.save_element_screenshot(selector, "temp_qr.png")
                        
                        # Citim raw bytes - Flet 0.86+ accepts bytes directly in Image.src
                        with open("temp_qr.png", "rb") as f:
                            qr_bytes = f.read()
                        
                        # Transmit pe UI (raw bytes, no base64 needed)
                        refresh_ui_callback(qr_bytes)
                        qr_found = True
                        print(f"[QR] Trimis pe UI: {len(qr_bytes)} bytes raw")
                        break
                except Exception as e:
                    print(f"[QR] Selector eșuat ({selector}): {e}")
                    continue

            if not qr_found:
                print("[QR] Niciun QR Code găsit - posibil deja logat")
                refresh_ui_callback(None)
                return

            # Așteptare logare (max 60 secunde)
            print("[QR] Aștept scanarea QR-ului (60 sec timeout)...")
            for attempt in range(60):
                try:
                    if "steamcommunity.com/id/" in driver.current_url or driver.is_element_visible(".persona"):
                        print("[QR] ✓ Logare reușită prin QR!")
                        break
                except:
                    pass
                time.sleep(1)
                if attempt % 10 == 0:
                    print(f"[QR] Încă aștept... ({attempt}/60)")
                    
        except Exception as e:
            print(f"[QR] Eroare critică: {str(e)}")
            refresh_ui_callback(None)
        finally:
            try:
                driver.quit()
            except:
                pass
            # Cleanup
            try:
                os.remove("temp_qr.png")
            except:
                pass