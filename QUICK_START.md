# ⚡ Quick Start - 100% FREE Bot

Deploy bot to Render Free in **5 minutes** with **zero cost**. ✓

---

## 🚀 Deploy Now (Copy-Paste)

### 1. GitHub Setup (1 min)

```bash
# Already done - repo is at:
# https://github.com/laur221/takemyauto
```

### 2. Render Deploy (2 min)

1. Go to: https://render.com
2. Sign up (free, no credit card)
3. Dashboard → **New +** → **Web Service**
4. Connect GitHub → Select `takemyauto` repo
5. Settings:
   - Name: `takemyskins-automator`
   - Environment: `Docker`
   - Region: `Oregon`
   - Instance: **Free**
6. Click **"Create Web Service"**

### 2.5 Add Database (OPTIONAL - Recommended for Full Persistence!)

**For ZERO data loss on restart:**

1. **Upstash Redis** (Session persistence):
   - Go to: https://upstash.com
   - Sign up (free)
   - Create Redis DB (FREE tier)
   - Copy connection string: `redis://default:PASSWORD@HOST:PORT`

2. **Render PostgreSQL** (Long-term data):
   - In Render Dashboard → **Databases** → **New**
   - Select PostgreSQL (FREE tier)
   - Done! Auto-configured ✓

3. Set Environment Variables in Render:
   - Go to Service → **Environment**
   - Add: `REDIS_URL=redis://default:PASSWORD@HOST:PORT`
   - PostgreSQL: Auto-added as `DATABASE_URL` ✓

### 3. Wait for Deploy (2 min)

Logs show:
```
[DB] ✅ Upstash Redis connected!
[DB] ✅ Render PostgreSQL connected!
[DB] ✅ HYBRID MODE: PostgreSQL + Redis (PERFECT!)
```

App is LIVE! ✓

---

## 🎮 First Login (2 min)

1. Click Render dashboard link: `takemyskins-automator.onrender.com`
2. Click **"Generează QR Code Steam"**
3. QR appears
4. Scan with Steam Mobile app
5. Done! ✓

Bot now runs checks every 6 hours automatically.

---

## 🔧 Setup Keep-Alive (1 min - Optional but Recommended)

Prevent spin-down (dyno sleep):

1. Go to: https://cron-job.org/en/
2. Sign up free
3. Create job:
   - **URL**: `https://takemyskins-automator.onrender.com/healthz`
   - **Schedule**: Every 10 minutes
4. Save

Done! Your bot stays active 24/7.

---

## ✅ You're Done!

**Total time**: ~10 minutes  
**Total cost**: **$0** ✓  
**Setup needed**: Never again  

Bot now:
- ✅ Checks raffles every 6 hours
- ✅ Runs 24/7 on Render Free
- ✅ Saves wins (PostgreSQL + Redis)
- ✅ Session persists across restarts (with Redis)
- ✅ Tracks everything permanently

---

## 📱 Session Persistence

**With Upstash Redis (Recommended):**
- Session saved automatically
- Survives Render restart → NO re-login needed! ✓
- Cost: $0

**Without Redis:**
- If Render restarts (rare, ~1x per week):
  1. Open web UI
  2. Click QR button
  3. Scan again (1 min)
  4. Done! Bot continues

**Tip**: Add Redis (step 2.5) to avoid re-logins forever!

---

## 💰 Cost?

**$0/month FOREVER** ✓

No hidden fees. No credit card. Zero upgrades needed.

```
Render Free Web Service:      $0
PostgreSQL Database (Render): $0
Upstash Redis (10K/day):      $0
Keep-Alive (cron-job.org):    $0
Steam Login (Free QR):        $0
─────────────────────────────────
TOTAL:                        $0
```

**EVERYTHING is FREE!**

---

## 📞 Issues?

- **Bot not running**: Check logs in Render dashboard
- **QR doesn't appear**: Refresh browser (F5)
- **Keep-alive not working**: Setup cron-job.org (step above)
- **Session lost**: Login via QR again (1 min)

See full docs for more:
- `README.md` - Full overview
- `RENDER_DEPLOYMENT.md` - Detailed setup
- `KEEP_ALIVE.md` - Advanced keep-alive

---

## 🎉 That's It!

Your free 24/7 TakeMySkins bot is ready!

Enjoy! 🚀

