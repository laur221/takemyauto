import os
from dotenv import load_dotenv
import sqlite3
import psycopg2

load_dotenv()

class DBManager:
    def __init__(self):
        """Initialize database manager with fallback to SQLite.
        
        Priority:
        1. DATABASE_URL (Render PostgreSQL) - Production
        2. Local PostgreSQL (development)
        3. SQLite (Render Free tier) - Fallback
        """
        self.database_url = os.getenv("DATABASE_URL")
        self.use_sqlite = False
        self.sqlite_path = "./data.db"
        
        if not self.database_url:
            # Check if local PostgreSQL is available
            self.conn_params = {
                "dbname": os.getenv("DB_NAME", "takemyskins"),
                "user": os.getenv("DB_USER", "postgres"),
                "password": os.getenv("DB_PASSWORD", "2910"),
                "host": os.getenv("DB_HOST", "localhost"),
                "port": os.getenv("DB_PORT", "5432")
            }
            # Try to connect; if fails, use SQLite
            try:
                test_conn = psycopg2.connect(**self.conn_params)
                test_conn.close()
                print("✓ PostgreSQL disponibil")
            except Exception as e:
                print(f"⚠️ PostgreSQL nu e disponibil: {e}")
                print(f"ℹ️ Treceți la SQLite (data.db)")
                self.use_sqlite = True
        
        if self.use_sqlite:
            print(f"[DB] Using SQLite: {self.sqlite_path}")

    def get_conn(self):
        """Get database connection (PostgreSQL or SQLite)."""
        if self.use_sqlite:
            return sqlite3.connect(self.sqlite_path)
        
        if self.database_url:
            # Render PostgreSQL requires SSL
            url = self.database_url
            if "sslmode=" not in url:
                separator = "&" if "?" in url else "?"
                url = f"{url}{separator}sslmode=require"
            return psycopg2.connect(url)
        
        # Local PostgreSQL
        return psycopg2.connect(**self.conn_params)

    def save_raffle(self, name, status, item="None"):
        """Save raffle entry to database."""
        try:
            if self.use_sqlite:
                conn = self.get_conn()
                cur = conn.cursor()
                cur.execute("""
                    INSERT OR REPLACE INTO wins (raffle_name, status, item_name) 
                    VALUES (?, ?, ?)
                """, (name, status, item))
                conn.commit()
                cur.close()
                conn.close()
            else:
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
        except Exception as e:
            print(f"[DB] Error saving raffle: {e}")

    def get_stats(self):
        """Get raffle statistics from database."""
        try:
            conn = self.get_conn()
            cur = conn.cursor()
            
            if self.use_sqlite:
                cur.execute("SELECT COUNT(*) FROM wins")
                total = cur.fetchone()[0]
                cur.execute("SELECT * FROM wins WHERE status = 'WON' ORDER BY date DESC")
            else:
                cur.execute("SELECT COUNT(*) FROM wins")  # Total verificate
                total = cur.fetchone()[0]
                cur.execute("SELECT * FROM wins WHERE status = 'WON' ORDER BY date DESC")
            
            wins = cur.fetchall()
            cur.close()
            conn.close()
            return total, wins
        except Exception as e:
            print(f"[DB] Error getting stats: {e}")
            return 0, []

    def setup_db(self):
        """Create database schema if not exists."""
        try:
            conn = self.get_conn()
            cur = conn.cursor()
            
            if self.use_sqlite:
                # SQLite schema
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS wins (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        raffle_name TEXT UNIQUE,
                        status TEXT,
                        item_name TEXT,
                        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
            else:
                # PostgreSQL schema
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
            print("[DB] ✓ Database schema initialized")
        except Exception as e:
            print(f"[DB] Error setting up database: {e}")