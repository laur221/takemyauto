import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

class DBManager:
    def __init__(self):
        # Preferăm variabilele de mediu (Render le oferă automat)
        # Dacă nu există, folosim fallback-ul local (opțional)
        self.database_url = os.getenv("DATABASE_URL")
        
        if self.database_url:
            self.conn_params = None
        else:
            self.conn_params = {
                "dbname": os.getenv("DB_NAME", "takemyskins"),
                "user": os.getenv("DB_USER", "postgres"),
                "password": os.getenv("DB_PASSWORD", "2910"),
                "host": os.getenv("DB_HOST", "localhost"),
                "port": os.getenv("DB_PORT", "5432")
            }

    def get_conn(self):
        if self.database_url:
            return psycopg2.connect(self.database_url)
        return psycopg2.connect(**self.conn_params)

    def save_raffle(self, name, status, item="None"):
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO wins (raffle_name, status, item_name) 
            VALUES (%s, %s, %s)
            ON CONFLICT (raffle_name) DO UPDATE SET status = EXCLUDED.status;
        """, (name, status, item))
        conn.commit()
        cur.close()
        conn.close()

    def get_stats(self):
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM wins") # Total verificate
        total = cur.fetchone()[0]
        cur.execute("SELECT * FROM wins WHERE status = 'WON' ORDER BY date DESC")
        wins = cur.fetchall()
        cur.close()
        conn.close()
        return total, wins

    def setup_db(self):
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS wins (
                id SERIAL PRIMARY KEY,
                raffle_name TEXT UNIQUE,
                status TEXT,
                item_name TEXT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()