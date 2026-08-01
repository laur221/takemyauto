# 🚀 Render.com Deployment Guide (100% FREE)

Complete step-by-step guide for deploying **TakeMySkins Automator** to Render.com **Free Tier** - **ZERO COST** ✓

---

## ✅ Pre-Deployment Checklist

- [ ] GitHub account with repo pushed
- [ ] Render.com free account created (no credit card!)
- [ ] Local testing complete (see `LOCAL_TEST_GUIDE.md`)
- [ ] All code committed and pushed

**Important**: You can deploy and run **100% FREE forever** on Render Free Tier!

---

## 🎯 Deployment Steps

### Step 1: Create Render Account

1. Go to https://render.com
2. Sign up (free, no credit card)
3. Confirm email

---

### Step 2: Connect GitHub Repository

1. In Render Dashboard → **Settings** → **GitHub**
2. Click **"Connect GitHub"**
3. Authorize Render to access your repos
4. Select `takemyauto` repository

---

### Step 3: Create Web Service

1. Render Dashboard → **New +** → **Web Service**
2. Select **GitHub repository**: `laur221/takemyauto`
3. Fill in details:

| Field | Value |
|-------|-------|
| Name | `takemyskins-automator` |
| Environment | `Docker` |
| Region | `Oregon` (recommended) |
| Branch | `master` |
| Build Command | (auto-detected from Dockerfile) |
| Start Command | (auto-detected from Dockerfile) |
| Instance Type | **`Free`** ⭐ (IMPORTANT!) |

4. Click **"Create Web Service"**

**Important**: Select **Free** tier - no paid options needed!

---

### Step 4: Setup Redis + PostgreSQL (OPTIONAL but Recommended for 100% Persistence!)

#### 4A: Add FREE Upstash Redis (Session Persistence)

**Why?** Session survives dyno restart → No re-login needed!

1. Go to https://upstash.com (FREE tier available)
2. Sign up → Create Redis Database (FREE)
3. Get connection string: `redis://default:password@host:port`
4. Keep it handy

#### 4B: Add FREE Render PostgreSQL

**Why?** Long-term data storage (wins, stats) that never resets!

1. In Render Dashboard → **Databases** → **New Database**
2. Select PostgreSQL → FREE tier
3. Name: `takemyskins-db`
4. Region: Same as Web Service (Oregon)
5. Render auto-creates `DATABASE_URL` environment variable ✓

**Cost**: Both FREE forever!

---

### Step 5: Configure Environment Variables

In Render Dashboard → Your Service → **Environment**:

```env
PORT=8080
HEALTHCHECK_PORT=8081
SELF_PING_INTERVAL=600
SCHEDULER_INTERVAL=21600
PYTHONUNBUFFERED=1
REDIS_URL=redis://default:PASSWORD@HOST:PORT  # From Upstash
DATABASE_URL=                                    # Auto-set by Render PostgreSQL
```

**Why each variable**:
- `PORT` - Main web server (required by Render)
- `HEALTHCHECK_PORT` - Keep-alive health checks
- `SELF_PING_INTERVAL` - Self-ping frequency (10 min default)
- `SCHEDULER_INTERVAL` - Raffle checks (6 hours default)
- `PYTHONUNBUFFERED` - Real-time logging in Render
- `REDIS_URL` - Upstash connection (session survives restarts!) 🔴
- `DATABASE_URL` - Render PostgreSQL (auto-set) 🐘

**Hybrid Database Mode** ✅:
- `REDIS_URL` + `DATABASE_URL` → Perfect! Full persistence
- `DATABASE_URL` only → PostgreSQL (no session persistence)
- Neither → SQLite fallback (works but data resets on restart)

---

### Step 6: Deploy

**Option A: Automatic Deploy** (Recommended)

When you push to GitHub:
```bash
git add -A
git commit -m "Deploy to Render with Redis + PostgreSQL"
git push origin master
```

Render detects changes and auto-deploys (~2-3 min)

**Option B: Manual Deploy**

In Render Dashboard → Service → **Manual Deploy** button

---

## ⏳ Deployment Process

### Expected Timeline

| Stage | Time | Status |
|-------|------|--------|
| Build image | 2-3 min | Building... |
| Install dependencies | 2-3 min | Installing... |
| Start service | 30 sec | Starting... |
| Health check | 10 sec | Running ✓ |
| **Total** | **5-6 min** | **Deployed** |

### Monitor Deployment

In Render Dashboard → Service → **Logs**:

```
#10 Installing collected packages: ...
#10 Successfully installed ...
#11 COPY app.py engine.py gui.py db_manager.py .
#12 RUN mkdir -p user_session downloaded_files
==> Deploying...
[DB] Using SQLite: ./data.db          ← Good! Database ready
[DB] ✓ Database schema initialized     ← Schema created
Health server pornit pe portul 8081     ← Keep-alive server started
```

---

## ✅ Post-Deployment Verification

### 1. Check Logs

In Render Dashboard → **Logs**:

Look for:
```
Health server pornit pe portul 8081 (/healthz).
[KEEP-ALIVE] Self-ping OK: http://127.0.0.1:8081/healthz
```

### 2. Test Web Interface

```bash
# Replace with your Render URL
curl https://YOUR_SERVICE_NAME.onrender.com
```

Expected: HTML response with Flet app

### 3. Test Health Endpoints

```bash
# Health check
curl https://YOUR_SERVICE_NAME.onrender.com:8081/healthz
# Expected: "ok"

# Status check
curl https://YOUR_SERVICE_NAME.onrender.com:8081/status
# Expected: {"app": "TakeMySkins Automator", "status": "running"}
```

### 4. Access Web UI

1. Open: `https://YOUR_SERVICE_NAME.onrender.com`
2. Should see Flet web interface
3. Dark theme with buttons visible

---

## 🔄 Keep-Alive Setup (Critical!)

### What Render Does

- Free dyno spins down after **15 min inactivity**
- Next request: **+50 second delay** (spin-up time)

### Solution: External Monitoring

1. Go to https://cron-job.org/en/
2. Create new job:
   - **Title**: `TakeMySkins Keep-Alive`
   - **URL**: `https://YOUR_SERVICE.onrender.com/healthz`
   - **Schedule**: `Every 10 minutes`
   - **Timeout**: `30 seconds`

3. Save & Activate

**Result**: Dyno never spins down! 24/7 running ✓

---

## 🎮 Steam Login Setup

### First Run: Manual QR Login (FREE)

1. Open web UI: `https://YOUR_SERVICE.onrender.com`
2. Click **"Generează QR Code Steam"**
3. QR Code appears (takes ~10 sec)
4. Scan with Steam Mobile app
5. Login confirmed ✓

Browser session stored in container.

### Session Persistence (IMPORTANT - With FREE Redis!)

**Old approach (SQLite only)**: Session lost on restart → Must re-login

**NEW approach (WITH REDIS)**: Session persists! No re-login needed!

#### If you add FREE Upstash Redis:
- Session stored in Redis (30-day TTL)
- Survives dyno restart automatically
- **Zero re-logins needed!** ✓
- **Cost: $0**

#### If no Redis (PostgreSQL only or SQLite):
- Session lost on restart
- Must QR login again (takes 1 minute) ✓

**Recommendation**: Add Upstash Redis (3 clicks) → Never re-login again!

---

**Setup reminder**:
1. Create FREE Upstash Redis
2. Add `REDIS_URL` to environment variables in Render
3. Redeploy
4. Done! Sessions now persist! ✓

---

## 📊 Database Setup

### HYBRID MODE (Recommended): PostgreSQL + Redis ✅ **100% PERSISTENCE!**

**You get the best of both:**

| Database | Purpose | Cost | Data Survives Restart? |
|----------|---------|------|------------------------|
| **PostgreSQL (Render)** | Long-term stats, wins, raffles | **$0** | ✅ YES - permanent |
| **Redis (Upstash)** | Session storage (fast) | **$0** | ✅ YES - 30 days |
| **Result** | Both available = PERFECT! | **$0** | ✅ EVERYTHING persists |

**Setup Steps**:
1. Create FREE Upstash Redis → Get connection string
2. Create FREE Render PostgreSQL → Auto-configured
3. Add `REDIS_URL` + `DATABASE_URL` environment variables
4. Done! Both auto-detected and used by `db_manager.py`

**What this means**:
- Browser session saved in Redis → Survives dyno restart
- Stats/wins saved in PostgreSQL → Never lost
- No data loss! No re-logins!
- **Cost: $0 forever** ✓

---

### Single Database Options

#### Option A: PostgreSQL Only (No Session Persistence)
```
✓ Long-term data persists
✗ Session lost on restart → Must re-login
❌ Not recommended
```

#### Option B: Render Free: SQLite (No Persistence)
```
✓ App starts immediately
✗ Database resets on restart
✗ Stats lost, session lost
❌ Old approach (replaced)
```

**Recommendation: Use HYBRID MODE (PostgreSQL + Redis) for best results!**

---

### Verify Hybrid Setup Works

In Render Dashboard → Logs:

```
[DB] 🔴 Connecting to Upstash Redis...
[DB] ✅ Upstash Redis connected!
[DB] 🐘 Connecting to Render PostgreSQL...
[DB] ✅ Render PostgreSQL connected!
[DB] ✅ HYBRID MODE: PostgreSQL + Redis (PERFECT!)
```

If you see this → Everything works perfectly! ✓

---

## 🚨 Troubleshooting

### App crashes on startup

**Log output**:
```
psycopg2.OperationalError: connection refused
[DB] Using SQLite: ./data.db
[DB] ✓ Database schema initialized
```

✅ This is normal! App is falling back to SQLite.

If it crashes:
- Check logs for error message
- Verify all files copied (COPY in Dockerfile)
- Check Python syntax errors

### Web interface won't load (404)

**Problem**: URL is wrong

**Fix**:
```bash
# Get correct URL from Render dashboard
# Should be: https://takemyskins-automator.onrender.com
# NOT: https://onrender.com/takemyskins...
```

### Health endpoints don't respond

**Problem**: Port 8081 might be blocked

**Check logs**:
```
Health server pornit pe portul 8081
```

If missing:
- App crashed before health server started
- Check early logs for errors
- Verify app.py starts without errors

### QR Code doesn't appear

**Problem**: Browser session issues

**Fix**:
1. Refresh browser (F5)
2. Clear browser cache
3. Try in incognito mode
4. Check logs for `[QR]` messages

### Bot doesn't run scheduled checks

**Reasons**:
1. Steam session not logged in (need QR login first)
2. Check interval too short (set to at least 60 sec)
3. App restarted (scheduler is in-memory)

**Fix**:
1. Click "Generează QR Code" and login
2. Wait for scheduler to trigger
3. Check logs for "Pornesc verificarea..."

---

## 📈 Monitoring

### Render Dashboard

Check these regularly:

1. **Health**: Green checkmark = running
2. **Logs**: Should see `[KEEP-ALIVE]` pings
3. **Metrics**: CPU should be low (app idle most of time)
4. **Memory**: Should be 100-200 MB (steady)

### External Monitoring (Cron-Job.org)

Set up alerts:
1. Go to cron-job.org → Your Job
2. Enable **Email Notifications** → On Failure
3. Get email if app crashes

---

## 🔄 Redeployment

### Automatic (Recommended)

Every git push redeploys:
```bash
git add -A
git commit -m "Bug fix or feature"
git push origin master
# Render auto-deploys in 2-3 min
```

### Manual

In Render Dashboard → Service → **Manual Deploy**

---

## 💰 Total Cost Breakdown

### HYBRID MODE (Recommended):

| Component | Cost |
|-----------|------|
| Render Free Web Service | **$0** ✓ |
| PostgreSQL Database (Render) | **$0** ✓ |
| Upstash Redis (10K commands/day) | **$0** ✓ |
| Cron-Job.org Keep-Alive | **$0** ✓ |
| Steam Login (QR) | **$0** ✓ |
| GitHub (free repo) | **$0** ✓ |
| **TOTAL MONTHLY COST** | **$0** ✓ |

### What You Get:
✅ Session persists across restarts (no re-logins!)  
✅ All stats saved permanently  
✅ 100% data persistence  
✅ 24/7 running bot  
✅ **ZERO COST** forever  

**Yes, you can run this bot 100% FREE forever with full persistence!** 🎉

---

### Legacy: SQLite Only (Not Recommended)

| Component | Cost |
|-----------|------|
| Render Free Web Service | **$0** ✓ |
| SQLite Database (in-memory) | **$0** ✓ |
| Cron-Job.org Keep-Alive | **$0** ✓ |
| **TOTAL MONTHLY COST** | **$0** ✓ |

⚠️ **Limitation**: Data resets on dyno restart  
⚠️ **Use only if you can't set up Redis**

---

## 🎉 Success Indicators

### With HYBRID MODE (PostgreSQL + Redis):

✅ Service showing **"Live"** in dashboard  
✅ Logs show `[DB] ✅ HYBRID MODE: PostgreSQL + Redis (PERFECT!)`  
✅ Web UI loads at `https://YOUR_SERVICE.onrender.com`  
✅ Health endpoint responds: `/healthz` → "ok"  
✅ Keep-alive pings every 10 min: `[KEEP-ALIVE]` in logs  
✅ Scheduler running: "Pornesc verificarea..." logs  
✅ **Session saved to Redis (30 days, SURVIVES RESTARTS!)**  

### With PostgreSQL Only:

✅ Service running  
✅ Logs show `[DB] ✅ Render PostgreSQL connected!`  
✅ Web UI works  
⚠️ Session lost on restart (must re-login)

---

## 📚 Next Steps

1. ✅ Deploy to Render (this guide)
2. ✅ Test web interface
3. ✅ Setup cron-job.org keep-alive
4. ✅ QR login to Steam
5. ✅ Let bot run 24/7!

---

## 📞 Support Resources

- `README.md` - Project overview
- `DATABASE.md` - Database troubleshooting
- `KEEP_ALIVE.md` - Keep-alive strategies
- `README_RENDER.md` - Render-specific issues
- `DEPLOYMENT_CHECKLIST.md` - General deployment
- Render Docs: https://render.com/docs/

---

**Status**: ✅ Ready for Render.com Free Tier  
**Last Updated**: 2026-08-01  
**Cost**: $0/month  

