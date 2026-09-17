"""Import an already-logged-in takemyskins.com browser session into the DB,
bypassing the QR/Selenium login flow entirely.

Useful when Steam's anti-automation throttling makes the automated QR login
unreliable - if you're already logged into takemyskins.com in your own
regular browser, export those cookies and import them here instead.

Steps:
  1. Log into takemyskins.com normally, in your own browser.
  2. Export cookies for the takemyskins.com domain as JSON (e.g. with the
     "Cookie-Editor" browser extension: open it on takemyskins.com, then
     Export > Export as JSON) and save to a file, e.g. cookies.json.
  3. Run: python import_session.py cookies.json
"""
import json
import sys

from db_manager import DBManager
from engine import RaffleBot


def main():
    if len(sys.argv) != 2:
        print("Usage: python import_session.py <cookies.json>")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Cookie-Editor exports a list of {name, value, domain, path, ...},
    # already matching the shape engine.py expects from Selenium.
    cookies = raw if isinstance(raw, list) else raw.get("cookies", [])
    if not cookies:
        print("Nu am gasit cookie-uri in fisier.")
        sys.exit(1)

    db = DBManager()
    bot = RaffleBot(db)
    steam_id, nickname = bot._identity_from_cookies(cookies, log=print)
    if not steam_id:
        print("Nu am putut identifica contul din aceste cookie-uri (poate au expirat - reexporta-le).")
        sys.exit(1)

    bot.save_cookies(cookies, log=print, steam_id=steam_id, nickname=nickname)
    print(f"Cont salvat si activat: {nickname or steam_id} ({steam_id})")


if __name__ == "__main__":
    main()
