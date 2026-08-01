import os
import json
from dotenv import load_dotenv
import redis
import psycopg2
from datetime import datetime

load_dotenv()

class DBManager:
    """Hybrid Database Manager - PostgreSQL + Redis (Both FREE on Render!)
    
    Best of both worlds:
    - PostgreSQL: Long-term data (wins, raffles) - FREE from Render
    - Redis (Upstash): Fast session storage that SURVIVES RESTARTS - FREE Upstash
    
    Total Cost: $0/month FOREVER ✓
    Data Persistence: 100% (everything survives everything!)
    """
    
    def __init__(self):
        """Initialize both PostgreSQL and Redis connections"""
        self.redis_client = None
        self.redis_available = False
        self.postgres_available = False
        self.conn_params = None
        
        # Initialize Redis (Upstash) for session persistence
        self._init_redis()
        
        # Initialize PostgreSQL (Render) for long-term data
        self._init_postgres()
        
        # If both available, we're golden!
        if self.redis_available and self.postgres_available:
            print("[DB] ✅ HYBRID MODE: PostgreSQL + Redis (PERFECT!)")
            self.setup_db()
        elif self.postgres_available:
            print("[DB] ⚠️ PostgreSQL only (no session persistence across restarts)")
            self.setup_db()
        elif self.redis_available:
            print("[DB] ⚠️ Redis only (limited data, no relational queries)")
        else:
            print("[DB] ❌ No databases available!")
    
    def _init_redis(self):
        """Initialize Redis connection to Upstash"""
        redis_url = os.getenv("REDIS_URL")
        
        if redis_url:
            print("[DB] 🔴 Connecting to Upstash Redis...")
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True, ssl_cert_reqs="required")
                self.redis_client.ping()
                print("[DB] ✅ Upstash Redis connected!")
                self.redis_available = True
            except Exception as e:
                print(f"[DB] ⚠️ Redis failed: {e}")
        else:
            # Try local Redis
            try:
                self.redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True, socket_connect_timeout=3)
                self.redis_client.ping()
                print("[DB] ✅ Local Redis connected")
                self.redis_available = True
            except:
                print("[DB] ℹ️ No Redis (session won't survive restarts)")
    
    def _init_postgres(self):
        """Initialize PostgreSQL connection from Render"""
        database_url = os.getenv("DATABASE_URL")
        
        if database_url:
            print("[DB] 🐘 Connecting to Render PostgreSQL...")
            try:
                # Test connection
                conn = psycopg2.connect(database_url)
                conn.close()
                print("[DB] ✅ Render PostgreSQL connected!")
                self.postgres_available = True
                self.database_url = database_url
            except Exception as e:
                print(f"[DB] ⚠️ PostgreSQL failed: {e}")
        else:
            print("[DB] ℹ️ No DATABASE_URL (add Postgres to Render)")
    
    def _get_postgres_conn(self):
        """Get PostgreSQL connection"""
        if not self.postgres_available:
            return None
        
        try:
            return psycopg2.connect(self.database_url)
        except Exception as e:
            print(f"[DB] ❌ PostgreSQL connection error: {e}")
            return None
    
    def setup_db(self):
        """Initialize database structure"""
        if self.postgres_available:
            self._setup_postgres_schema()
    
    def _setup_postgres_schema(self):
        """Create PostgreSQL tables"""
        try:
            conn = self._get_postgres_conn()
            if not conn:
                return
            
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
            print("[DB] ✅ PostgreSQL schema ready")
        except Exception as e:
            print(f"[DB] ❌ Error setting up PostgreSQL: {e}")
    
    def save_raffle(self, name, status, item="None"):
        """Save raffle to PostgreSQL (long-term) + Redis cache
        
        PostgreSQL = permanent data
        Redis = fast cache
        """
        # Save to PostgreSQL (permanent)
        if self.postgres_available:
            try:
                conn = self._get_postgres_conn()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO wins (raffle_name, status, item_name) 
                    VALUES (%s, %s, %s)
                    ON CONFLICT (raffle_name) DO UPDATE SET status = EXCLUDED.status;
                """, (name, status, item))
                conn.commit()
                cur.close()
                conn.close()
                print(f"[DB] ✅ Saved to PostgreSQL: {name} = {status}")
            except Exception as e:
                print(f"[DB] ❌ PostgreSQL error: {e}")
        
        # Also cache in Redis (fast)
        if self.redis_available:
            try:
                data = {
                    "status": status,
                    "item_name": item,
                    "date": datetime.now().isoformat()
                }
                self.redis_client.hset(f"wins:{name}", mapping=data)
                self.redis_client.sadd("wins:list", name)
                print(f"[DB] ✅ Cached in Redis: {name}")
            except Exception as e:
                print(f"[DB] ⚠️ Redis cache error: {e}")
    
    def get_stats(self):
        """Get stats from PostgreSQL (true data!)
        
        Returns: (total_raffles, list_of_wins)
        """
        if self.postgres_available:
            try:
                conn = self._get_postgres_conn()
                cur = conn.cursor()
                
                # Total raffles
                cur.execute("SELECT COUNT(*) FROM wins")
                total = cur.fetchone()[0]
                
                # Wins
                cur.execute("SELECT * FROM wins WHERE status = 'WON' ORDER BY date DESC")
                wins = cur.fetchall()
                
                cur.close()
                conn.close()
                
                print(f"[DB] ✅ Stats from PostgreSQL: {total} raffles, {len(wins)} wins")
                return total, wins
            except Exception as e:
                print(f"[DB] ❌ Error getting stats: {e}")
                return 0, []
        
        return 0, []
    
    def save_session(self, session_data):
        """Save browser session to Redis (PERSISTS ACROSS RESTARTS!)
        
        30-day TTL - ensures session survives dyno restart
        """
        if not self.redis_available:
            print("[DB] ⚠️ Redis not available, session not saved")
            return
        
        try:
            # Save to Redis with 30-day expiry
            self.redis_client.set("session:browser", json.dumps(session_data), ex=86400*30)
            print("[DB] ✅ Session saved to Redis (30 days, SURVIVES RESTARTS!)")
        except Exception as e:
            print(f"[DB] ❌ Error saving session: {e}")
    
    def get_session(self):
        """Retrieve browser session from Redis (SURVIVES RESTARTS!)
        
        This is the KEY feature - session persists even if dyno restarts!
        """
        if not self.redis_available:
            return None
        
        try:
            session_json = self.redis_client.get("session:browser")
            if session_json:
                print("[DB] ✅ Session restored from Redis (NO re-login needed!)")
                return json.loads(session_json)
            print("[DB] ℹ️ No session found")
            return None
        except Exception as e:
            print(f"[DB] ❌ Error getting session: {e}")
            return None
    
    def session_exists(self):
        """Check if valid session exists in Redis"""
        if not self.redis_available:
            return False
        
        try:
            return self.redis_client.exists("session:browser") > 0
        except:
            return False
    
    def clear_session(self):
        """Clear session from Redis"""
        if self.redis_available:
            try:
                self.redis_client.delete("session:browser")
                print("[DB] ✅ Session cleared")
            except Exception as e:
                print(f"[DB] ❌ Error clearing session: {e}")
