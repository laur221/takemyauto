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

### 3. Wait for Deploy (2 min)

Logs show:
```
[DB] ✓ Database schema initialized
Health server pornit pe portul 8081
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
- ✅ Saves wins to SQLite
- ✅ Tracks everything

---

## 📱 What About Re-Login?

If Render restarts (rare, ~1x per week):
1. Open web UI
2. Click QR button
3. Scan again (1 min)
4. Done! Bot continues

**That's it!** No paid alternatives needed.

---

## 💰 Cost?

**$0/month FOREVER** ✓

No hidden fees. No credit card. Zero upgrades needed.

```
Render Free:        $0
Database (SQLite):  $0
Keep-Alive (Free):  $0
Steam Login (Free): $0
─────────────────────
TOTAL:              $0
```

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

