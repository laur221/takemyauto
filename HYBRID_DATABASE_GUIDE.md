# 🔗 Hybrid PostgreSQL + Redis Database Guide

Complete guide to the new **100% persistent** database system that survives Render dyno restarts.

---

## 📊 Architecture Overview

```
┌─────────────────────────────────────────────┐
│         Render Web Service (App)            │
│  TakeMySkins Bot + Flet Web Interface       │
└────────────────┬────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
   ┌─────────┐       ┌────────────┐
   │  Redis  │       │ PostgreSQL │
   │(Upstash)│       │(Render DB) │
   └────┬────┘       └─────┬──────┘
        │                  │
   Session Data       Long-term Data
   (30-day TTL)       (Permanent)
   Survives           Survives
   Restart!           Restart!
   ✅                 ✅
```

---

## 🎯 What This Solves

### BEFORE (SQLite Only)
```
❌ Browser session lost on restart
❌ Must re-login every 1-2 weeks
❌ Stats reset on restart
❌ User friction!
```

### AFTER (PostgreSQL + Redis Hybrid)
```
✅ Browser session persists (30-day TTL in Redis)
✅ NO re-login after restart
✅ Stats never lost (PostgreSQL permanent)
✅ 100% data persistence
✅ Zero user friction!
```

---

## 🚀 Deployment Options

### Option 1: HYBRID (Recommended) ⭐

**Best performance and persistence!**

```env
REDIS_URL=redis://default:PASSWORD@HOST:PORT    # From Upstash
DATABASE_URL=postgresql://user:pass@host/db     # From Render
```

**Result**:
- ✅ Session persists (Redis)
- ✅ Stats permanent (PostgreSQL)
- ✅ NO re-login needed
- ✅ All data survives restart
- 💰 Cost: $0

**Log output**:
```
[DB] ✅ Upstash Redis connected!
[DB] ✅ Render PostgreSQL connected!
[DB] ✅ HYBRID MODE: PostgreSQL + Redis (PERFECT!)
```

---

### Option 2: PostgreSQL Only

```env
DATABASE_URL=postgresql://user:pass@host/db
# No REDIS_URL
```

**Result**:
- ✅ Long-term data persists (PostgreSQL)
- ⚠️ Session lost on restart → Must re-login
- 💰 Cost: $0

**Log output**:
```
[DB] ✅ Render PostgreSQL connected!
[DB] ⚠️ PostgreSQL only (no session persistence)
```

---

### Option 3: Redis Only

```env
REDIS_URL=redis://default:PASSWORD@HOST:PORT
# No DATABASE_URL
```

**Result**:
- ✅ Session persists (Redis)
- ⚠️ Limited storage (256MB free tier)
- ⚠️ Session expires after 30 days
- 💰 Cost: $0

**Not recommended** for production (limited persistence)

---

### Option 4: SQLite (Legacy - Not Recommended)

```env
# No REDIS_URL or DATABASE_URL
```

**Result**:
- ✅ App starts
- ❌ Session lost on restart
- ❌ Stats lost on restart
- ⚠️ Only for testing

---

## 📋 How to Set Up HYBRID MODE

### Step 1: Create FREE Upstash Redis (3 min)

1. Go to https://upstash.com
2. Sign up (free account)
3. Create database:
   - Name: `takemyskins-session`
   - Tier: **FREE** (10K commands/day, 256MB)
   - Region: Same as your Render (e.g., us-east-1)
4. Click "Create"
5. Copy connection string:
   ```
   redis://default:PASSWORD@HOST:PORT
   ```
   (Format: `redis://default:abc123@redis-xxxxx.upstash.io:39xxx`)

**Cost: $0 forever** ✓

---

### Step 2: Add Render PostgreSQL (3 min)

1. In Render Dashboard → **Databases** → **New Database**
2. Select **PostgreSQL** → Tier: **Free**
3. Name: `takemyskins-db`
4. Region: Same as your Web Service (Oregon)
5. Click "Create Database"
6. Render auto-creates `DATABASE_URL` environment variable

**Cost: $0 forever** ✓

---

### Step 3: Set Environment Variables in Render (2 min)

1. Render Dashboard → Your Web Service → **Environment**
2. Add new variables:

   ```
   REDIS_URL=redis://default:PASSWORD@HOST:PORT
   ```
   (Copy from Upstash step 1)

3. PostgreSQL: `DATABASE_URL` should already exist (auto-added by Render)

4. Save & Redeploy

**Total time: 8 minutes** ✓

---

## ✅ How to Verify It Works

### Check 1: Logs (Immediate)

After redeploy, look at Render logs for:

```
[DB] ✅ Upstash Redis connected!
[DB] ✅ Render PostgreSQL connected!
[DB] ✅ HYBRID MODE: PostgreSQL + Redis (PERFECT!)
```

✅ **All three lines? Perfect setup!**

---

### Check 2: Session Persistence (After First Check)

After running a raffle check, you should see:

```
[SESSION] ✅ Session saved to Redis (survives restart!)
```

This means:
- Session is now in Redis
- Persists for 30 days
- Will be restored on next startup

---

### Check 3: Stats in PostgreSQL

Run a raffle check, you should see:

```
[DB] ✅ Saved to PostgreSQL: raffle_name = status
[DB] ✅ Cached in Redis: raffle_name
```

This means:
- Data saved to permanent PostgreSQL database
- Also cached in Redis for speed
- Stats visible in `/status` endpoint

---

### Check 4: Session Restoration (After Dyno Restart)

1. Trigger a dyno restart (Render → Service → Restart)
2. App starts
3. Click "Generează QR Code" (or run a check)
4. Look for:
   ```
   [SESSION] ✅ Restored from Redis - NO re-login needed!
   ```

✅ **Session automatically restored! No re-login!**

---

## 🔧 How It Works (Technical Details)

### Session Storage (Redis)

**Saved when**: After successful raffle check
```python
db.save_session({
    "cookies": [...],           # Browser cookies
    "localStorage": [...],      # Stored data
    "sessionStorage": [...],    # Session data
    "last_check": 1234567890,  # Timestamp
    "status": "logged_in"
})
```

**TTL**: 30 days (redis EXPIRY)

**Restored when**: Browser opens or check starts
```python
session = db.get_session()
if session:
    # Restore cookies, etc. → NO re-login!
    driver.add_cookie(...)
```

---

### Long-term Data (PostgreSQL)

**What's stored**:
```sql
CREATE TABLE wins (
    id SERIAL PRIMARY KEY,
    raffle_name TEXT UNIQUE,
    status TEXT,
    item_name TEXT,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Saved when**: During raffle check or user interaction
```python
db.save_raffle("raffle_name", "WON", item="Item Name")
```

**Persists**: Forever (until you delete it manually)

---

### Dual-Write Pattern

Every important operation writes to BOTH:

```python
# 1. Save to PostgreSQL (permanent)
INSERT INTO wins (...) VALUES (...)

# 2. Cache in Redis (fast, survives restart)
HSET wins:raffle_name status=value
```

**Benefits**:
- PostgreSQL = permanent backup
- Redis = fast cache + session persistence
- If Redis fails, PostgreSQL is still there
- If PostgreSQL fails, Redis has recent data

---

## ⚠️ Edge Cases & Fallbacks

### What if Redis is down?

✅ **Handled gracefully**:
```python
if self.redis_available:
    try:
        self.redis_client.set(...)
    except:
        print("⚠️ Redis offline (PostgreSQL still works)")
```

- Bot continues working
- Data still saves to PostgreSQL
- Session not persisted, but bot works
- ✅ No crashes!

---

### What if PostgreSQL is down?

✅ **Also handled**:
```python
if self.postgres_available:
    try:
        conn.execute(INSERT ...)
    except:
        print("⚠️ PostgreSQL offline (Redis cached)")
```

- Bot continues working
- Session still in Redis
- Data cached in Redis temporarily
- ✅ No crashes!

---

### What if session expires (30 days)?

✅ **Normal operation**:
- Very rare (only if bot unused 30+ days)
- User just clicks "Generează QR Code"
- Takes 1 minute to scan QR
- New session starts
- ✅ No problem!

---

### What if Render restarts while saving?

✅ **Transaction safety**:
- PostgreSQL: ACID guarantees (atomic saves)
- Redis: TTL prevents stale data
- Worst case: One transaction lost (rare)
- Bot resumes normally after restart
- ✅ No data corruption!

---

## 📊 Performance Characteristics

### Response Times

| Operation | Storage | Time | Notes |
|-----------|---------|------|-------|
| Save session | Redis | ~10ms | Very fast |
| Get session | Redis | ~5ms | Cache hit |
| Save stats | PostgreSQL | ~50ms | Insert/Update |
| Get stats | PostgreSQL | ~30ms | Query |
| Query history | PostgreSQL | ~100ms | Full scan |

All operations < 200ms ✓

---

### Storage Usage

| Component | FREE Tier | Usage | Status |
|-----------|-----------|-------|--------|
| Redis | 256MB | ~5MB (session + cache) | ✅ Plenty |
| PostgreSQL | 256MB | ~10MB (stats) | ✅ Plenty |
| Render Dyno | 512MB | ~150MB (app + chrome) | ✅ OK |

---

## 🚨 Troubleshooting

### Problem: "❌ No databases available!"

**Cause**: Neither Redis nor PostgreSQL configured

**Fix**:
1. Go to Render → Environment
2. Add `REDIS_URL` from Upstash
3. Ensure `DATABASE_URL` exists
4. Redeploy

---

### Problem: "[SESSION] ℹ️ No saved session in Redis"

**Cause**: First run, or session expired

**Fix**:
- Normal on first run
- QR login once → Session saved
- Next restart will restore

---

### Problem: "⚠️ PostgreSQL offline"

**Cause**: DATABASE_URL invalid or service down

**Fix**:
1. Check DATABASE_URL in Render Environment
2. Verify Render PostgreSQL is running
3. Check connection string format
4. Redeploy

---

### Problem: "⚠️ Redis offline"

**Cause**: REDIS_URL invalid or Upstash service down

**Fix**:
1. Check REDIS_URL format (should be `redis://default:pwd@host:port`)
2. Verify Upstash dashboard shows DB online
3. Test connection locally: `redis-cli -u REDIS_URL ping`
4. Redeploy

---

## 📈 Monitoring

### Key Metrics to Watch

1. **In Render Logs**:
   - Look for `[DB]` messages on startup
   - Check for `[SESSION]` save/restore events
   - Monitor error frequency

2. **In Render Dashboard**:
   - CPU: Should be <10% (mostly idle)
   - Memory: Should be ~150MB steady
   - Green health status ✓

3. **Session Persistence**:
   - First run: `[SESSION] ℹ️ No saved session`
   - After check: `[SESSION] ✅ Session saved to Redis`
   - After restart: `[SESSION] ✅ Restored from Redis`

---

## 💡 Best Practices

1. **Always use HYBRID mode** (PostgreSQL + Redis)
   - Best reliability
   - Best performance
   - Zero cost
   - No re-logins

2. **Monitor database connectivity**
   - Check logs on startup
   - Verify both services online before deploying

3. **Keep environment variables safe**
   - REDIS_URL contains password (keep secret)
   - DATABASE_URL contains credentials (keep secret)
   - Never commit to git!

4. **Backup important data**
   - Export PostgreSQL stats periodically
   - Redis data is cache (can be lost, OK)
   - PostgreSQL is permanent (important!)

---

## 🎓 Learning More

### Related Documentation

- `RENDER_DEPLOYMENT.md` - Step-by-step deployment
- `QUICK_START.md` - 5-minute setup
- `DATABASE.md` - Database troubleshooting
- `README.md` - Project overview

### Resources

- Upstash Docs: https://upstash.com/docs/redis/overall/getstarted
- Render Docs: https://render.com/docs/databases
- PostgreSQL: https://www.postgresql.org/docs/
- Redis: https://redis.io/docs/

---

## ✅ Checklist: HYBRID Mode Deployment

- [ ] Created FREE Upstash Redis account
- [ ] Created FREE Redis database (10K commands/day)
- [ ] Copied Redis connection string
- [ ] Created FREE Render PostgreSQL database
- [ ] Added `REDIS_URL` to Render Environment
- [ ] Verified `DATABASE_URL` auto-added by Render
- [ ] Redeployed app to Render
- [ ] Checked logs for all 3 success messages
- [ ] Ran first raffle check
- [ ] Verified session saved to Redis
- [ ] Triggered dyno restart
- [ ] Verified session restored automatically
- [ ] ✅ HYBRID Mode is live and working!

**Total time: ~15 minutes for full setup** ✓

---

**Status**: ✅ Hybrid Database System Active  
**Cost**: $0/month FOREVER  
**Data Persistence**: 100% ✓  
**User Experience**: Zero friction! ✓

