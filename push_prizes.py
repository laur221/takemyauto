"""Trimite lista de prize (active + istoric) catre KV-ul Worker-ului.

Ruleaza pe PC-ul local (acolo unde API-ul TMS nu blocheaza inventarul).
Programabil prin Windows Task Scheduler (ex: o data pe zi).
"""
import json
import sys
from pathlib import Path

import requests

BASE = Path(r"D:\github\takemyskinauto")
sys.path.insert(0, str(BASE))

WORKER_URL = "https://takemyauto.pinzaru-laurentiu.workers.dev"
API_BASE = "https://api.takemyskins.com"


def main():
    from engine import RaffleBot
    from db_manager import DBManager

    bot = RaffleBot(DBManager())
    s = bot._ensure_session()
    bot._set_csrf(s, log=lambda m: None)

    user = s.get(f"{API_BASE}/profile/user", timeout=20).json().get("user")
    if not user:
        print("[!] Sesiune expirata local. Refa login QR.")
        return
    uid = user["id"]
    print(f"[i] Utilizator: {user['nickname']} ({uid})")

    def norm(entry):
        item = entry.get("item") or {}
        return {
            "name": item.get("steam_market_hash_name") or item.get("skin_name") or "-",
            "price": item.get("price") or 0,
            "image": item.get("steam_image") or "",
            "exterior": item.get("steam_short_exterior") or "",
            "time_finished": entry.get("time_finished") or "",
            "url": entry.get("url") or "",
        }

    active, history = [], []
    for game in ("csgo", "dota2", "rust"):
        for tab, bucket in (("items", active), ("items_history", history)):
            try:
                r = s.get(
                    f"{API_BASE}/profile/get_profile_{tab}/{uid}",
                    params={"game": game, "limit": 64, "page": 1},
                    timeout=20,
                )
                if not r.ok:
                    continue
                for e in r.json().get("items") or []:
                    p = norm(e)
                    if p["name"] != "-":
                        bucket.append(p)
            except Exception as e:
                print(f"[!] {tab}/{game}: {e}")

    payload = {"active": active, "history": history}
    r = requests.post(f"{WORKER_URL}/admin/session-cache", json=payload, timeout=30)
    print(f"[OK] Cache trimis: {len(active)} active, {len(history)} istoric -> {r.status_code}")


if __name__ == "__main__":
    main()
