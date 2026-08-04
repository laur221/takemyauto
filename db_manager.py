import os
import json
import hashlib
import base64
from dotenv import load_dotenv

load_dotenv()

# Try imports (optional dependencies)
try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

try:
    import psycopg2
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False


def _xor_cipher(data_bytes, key):
    """Simple XOR cipher - NOT secure encryption, just obscures the password.
    Real security comes from Redis/Postgres access control + HTTPS.
    """
    key_bytes = key.encode('utf-8')
    return bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(data_bytes))


def _encrypt_password(password, secret_key):
    if not password:
        return ""
    data = password.encode('utf-8')
    encrypted = _xor_cipher(data, secret_key)
    return base64.b64encode(encrypted).decode('utf-8')


def _decrypt_password(encrypted_b64, secret_key):
    if not encrypted_b64:
        return ""
    try:
        encrypted = base64.b64decode(encrypted_b64)
        decrypted = _xor_cipher(encrypted, secret_key)
        return decrypted.decode('utf-8')
    except Exception:
        return ""


class DBManager:
    def __init__(self):
        self.redis_client = None
        self.redis_available = False
        self.postgres_available = False
        self.database_url = None
        self._secret = os.getenv("DB_SECRET", "takemyskins-default-key-2024")

        self._init_redis()
        self._init_postgres()

        if self.postgres_available:
            self.setup_db()

        modes = []
        if self.postgres_available:
            modes.append("PostgreSQL")
        if self.redis_available:
            modes.append("Redis")
        mode_str = " + ".join(modes) if modes else "Memory"
        print(f"[DB] Mode: {mode_str}")

    def _init_redis(self):
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                self.redis_client = redis.from_url(
                    redis_url, decode_responses=True,
                    ssl_cert_reqs="required"
                )
                self.redis_client.ping()
                self.redis_available = True
                print("[DB] Redis connected")
            except Exception as e:
                print(f"[DB] Redis failed: {e}")
        else:
            print("[DB] No REDIS_URL (set in Render env)")

    def _init_postgres(self):
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            try:
                conn = psycopg2.connect(database_url)
                conn.close()
                self.postgres_available = True
                self.database_url = database_url
                print("[DB] PostgreSQL connected")
            except Exception as e:
                print(f"[DB] PostgreSQL failed: {e}")
        else:
            print("[DB] No DATABASE_URL (set in Render env)")

    def _get_conn(self):
        if not self.postgres_available:
            return None
        try:
            return psycopg2.connect(self.database_url)
        except Exception as e:
            print(f"[DB] PG connection error: {e}")
            return None

    def setup_db(self):
        if not self.postgres_available:
            return
        try:
            conn = self._get_conn()
            if not conn:
                return
            cur = conn.cursor()

            # Raffle results
            cur.execute("""
                CREATE TABLE IF NOT EXISTS wins (
                    id SERIAL PRIMARY KEY,
                    raffle_name TEXT UNIQUE,
                    status TEXT,
                    item_name TEXT,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Steam profile (username + encrypted password)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS steam_profile (
                    id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    password_encrypted TEXT NOT NULL,
                    last_login TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            conn.commit()
            cur.close()
            conn.close()
            print("[DB] Schema ready")
        except Exception as e:
            print(f"[DB] Schema error: {e}")

    # ---- Steam Profile ----

    def save_steam_profile(self, username, password):
        """Save or update Steam credentials (password encrypted)."""
        encrypted = _encrypt_password(password, self._secret)
        if self.postgres_available:
            try:
                conn = self._get_conn()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO steam_profile (username, password_encrypted, last_login)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        username = EXCLUDED.username,
                        password_encrypted = EXCLUDED.password_encrypted,
                        last_login = NOW();
                """ , (username, encrypted))
                # Keep only latest profile
                cur.execute("DELETE FROM steam_profile WHERE id != (SELECT id FROM steam_profile ORDER BY last_login DESC LIMIT 1)")
                conn.commit()
                cur.close()
                conn.close()
                return True
            except Exception as e:
                print(f"[DB] Save profile error: {e}")
                return False
        return False
    def get_steam_profile(self):
        """Get saved Steam credentials. Returns (username, password) or (None, None)."""
        if self.postgres_available:
            try:
                conn = self._get_conn()
                cur = conn.cursor()
                cur.execute("SELECT username, password_encrypted FROM steam_profile ORDER BY last_login DESC LIMIT 1")
                row = cur.fetchone()
                cur.close()
                conn.close()
                if row:
                    username, encrypted = row
                    password = _decrypt_password(encrypted, self._secret)
                    return username, password
            except Exception as e:
                print(f"[DB] Get profile error: {e}")
        return None, None

    def has_steam_profile(self):
        """Check if a Steam profile is saved."""
        u, p = self.get_steam_profile()
        return u is not None and p is not None

    # ---- Session (Redis) ----

    def save_session(self, session_data):
        if not self.redis_available:
            print("[DB] No Redis - session not persisted")
            return
        try:
            self.redis_client.set(
                "session:takemyskins",
                json.dumps(session_data),
                ex=86400 * 30
            )
            print("[DB] Session saved to Redis (30d)")
        except Exception as e:
            print(f"[DB] Session save error: {e}")

    def get_session(self):
        if not self.redis_available:
            return None
        try:
            data = self.redis_client.get("session:takemyskins")
            if data:
                print("[DB] Session restored from Redis")
                return json.loads(data)
        except Exception as e:
            print(f"[DB] Session get error: {e}")
        return None

    def session_exists(self):
        if not self.redis_available:
            return False
        try:
            return self.redis_client.exists("session:takemyskins") > 0
        except Exception:
            return False

    def clear_session(self):
        if self.redis_available:
            try:
                self.redis_client.delete("session:takemyskins")
                print("[DB] Session cleared")
            except Exception as e:
                print(f"[DB] Session clear error: {e}")

    # ---- Raffles/Wins ----

    def save_raffle(self, name, status, item="None"):
        if self.postgres_available:
            try:
                conn = self._get_conn()
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
                print(f"[DB] Save raffle error: {e}")

        if self.redis_available:
            try:
                self.redis_client.hset(f"w:{name}", mapping={
                    "status": status, "item": item
                })
            except Exception:
                pass

    def get_stats(self):
        if self.postgres_available:
            try:
                conn = self._get_conn()
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM wins")
                total = cur.fetchone()[0]
                cur.execute("SELECT * FROM wins WHERE status = 'WON' ORDER BY date DESC")
                wins = cur.fetchall()
                cur.close()
                conn.close()
                return total, wins
            except Exception as e:
                print(f"[DB] Stats error: {e}")
        return 0, []
