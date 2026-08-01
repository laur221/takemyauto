from seleniumbase import Driver
import time


class RaffleBot:
    def __init__(self, db):
        self.db = db
        self.session_dir = "./user_session"

    # În engine.py, modifică metoda run_check:
    def run_check(self, is_headless=True, log_func=None):
        def log(msg):
            if log_func: log_func(msg)
            print(msg)

        driver = Driver(uc=True, user_data_dir=self.session_dir, headless=is_headless)
        try:
            log("Se deschide browserul...")
            driver.get("https://takemyskins.com/")

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

            return "Gata!"
        except Exception as e:
            log(f"Eroare generală: {str(e)}")
            return "Eroare"
        finally:
            driver.quit()

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

    def get_steam_qr(self, refresh_ui_callback):
        # Deschidem browserul în mod headless pentru a lua QR-ul
        driver = Driver(uc=True, user_data_dir=self.session_dir, headless=True)
        try:
            driver.get("https://store.steampowered.com/login/")
            time.sleep(5)  # Așteptăm să se genereze QR-ul

            # Identificăm elementul QR Code (în 2026 Steam folosește clase specifice)
            # Selectorul pentru containerul QR este de obicei o clasă ce conține "qrcode"
            qr_selector = "div[class*='login_QR_'] canvas, div[class*='qr_code'] img"

            if driver.is_element_visible(qr_selector):
                # Facem screenshot doar la acel element
                driver.save_element_screenshot(qr_selector, "temp_qr.png")
                refresh_ui_callback()  # Anunțăm interfața să arate poza

                # Așteptăm logarea (verificăm dacă URL-ul se schimbă sau apare profilul)
                for _ in range(60):  # Așteptăm max 60 secunde scanarea
                    if "steamcommunity.com/id/" in driver.current_url or driver.is_element_visible(".persona"):
                        print("Logare reușită prin QR!")
                        break
                    time.sleep(2)
            else:
                print("Nu am găsit QR Code-ul pe pagină.")
        finally:
            driver.quit()