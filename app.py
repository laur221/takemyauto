import os
import flet as ft
from db_manager import DBManager
from engine import RaffleBot
from gui import start_gui

# Inițializăm componentele
db = DBManager()
db.setup_db()
bot = RaffleBot(db)
app_func = start_gui(bot)

if __name__ == "__main__":
    # Rulare locală sau pe server (Flet detectează portul din variabila de mediu PORT pe Render)
    port = int(os.getenv("PORT", 8080))
    ft.app(target=app_func, view=ft.AppView.WEB_BROWSER, port=port)