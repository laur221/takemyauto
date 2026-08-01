# 🎮 TakeMySkins Automator - Raffle Bot 24/7

**Automated raffle participation bot** pentru [takemyskins.com](https://takemyskins.com) - Rulează pe Render Free fără costuri! 🚀

---

## 📋 Caracteristici

✅ **Automatizare Completă**
- Verificare raffles la intervale regulate (6 ore default)
- Înscrierea automată în raffles disponibile
- Tracking câștiguri și premii

✅ **Keep-Alive 24/7** 
- Self-ping intern (10 min) previne Render spin-down
- Cron-job.org integration (gratuit) pentru backup
- Zero downtime pe dyno gratuit

✅ **Autentificare Steam Securizată**
- QR Code login (nu cere parola)
- Sesiune persistentă pe disk persistent (optional)
- Suport pentru manual + automated login

✅ **Web Interface Intuitivă**
- Interfață dark theme cu Flet
- Console logs real-time
- Statistici raffles și câștiguri
- Status monitoring

✅ **Monitoring și Diagnostics**
- Health endpoints: `/healthz`, `/ping`, `/status`
- Render-compatible logging
- Error recovery automat

---

## 🚀 Quick Start

### Local Development

```bash
# 1. Clone & install
git clone https://github.com/laur221/takemyauto.git
cd takemyauto
pip install -r requirements.txt

# 2. Run locally
python app.py

# 3. Access web UI
# Open: http://localhost:8080

# 4. Test health endpoints (new terminal)
curl http://localhost:8081/healthz
curl http://localhost:8081/status
```

### Deploy to Render.com (Free) ⚡

**100% FREE - $0/month - No Credit Card** ✓

**Quick path (5 min)**:
👉 See **`QUICK_START.md`** for copy-paste instructions

**Detailed path**:
👉 See **`RENDER_DEPLOYMENT.md`** for step-by-step

---

## 💰 Cost

**TOTAL: $0/month FOREVER** ✓

- Render Free Tier: $0
- SQLite Database: $0
- Cron-Job.org Keep-Alive: $0
- Steam QR Login: $0

No credit card needed. No hidden fees. No upgrades required.

---

## 📁 Project Structure

```
takemyskinauto/
├── app.py                    # Web server + health endpoints
├── engine.py                 # Bot logic + background scheduler
├── gui.py                    # Flet web interface
├── db_manager.py             # Database management (auto-fallback)
├── requirements.txt          # Python dependencies
│
├── README.md                 # This file
├── DATABASE.md               # Database configuration guide
├── KEEP_ALIVE.md             # Render spin-down prevention guide
├── README_RENDER.md          # Steam session management on Render Free
├── LOCAL_TEST_GUIDE.md       # Local testing procedures
├── DEPLOYMENT_CHECKLIST.md   # Pre/post deployment steps
│
├── Dockerfile                # Container for Render deployment
├── render.yaml               # Render auto-configuration
├── user_session/             # Browser session cache (Steam cookies)
├── downloaded_files/         # Raffle data storage
├── data.db                   # SQLite database (auto-created, Render Free)
└── .git/                     # Version control
```

---

## ⚙️ Architecture

### Components

```
┌──────────────────────────────────────────┐
│         Flet Web UI (Port 8080)          │
│  ├─ QR Steam Login                       │
│  ├─ Manual Check Button                  │
│  ├─ Scheduler Controls                   │
│  └─ Live Console Logs                    │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│    Flask-like HTTP Handler (app.py)      │
│  ├─ /healthz (keep-alive)                │
│  ├─ /ping (cron-job.org)                 │
│  └─ /status (monitoring)                 │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│      RaffleBot Engine (engine.py)        │
│  ├─ run_check() - Single check           │
│  ├─ start_background_scheduler()         │
│  ├─ get_steam_qr() - QR login            │
│  └─ check_wins_internal() - Prize check  │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│    SeleniumBase Driver (Undetected)      │
│  ├─ Chromium headless browser            │
│  ├─ Anti-detection enabled               │
│  └─ RAM-optimized for Render (512MB)     │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│   takemyskins.com (Target Website)       │
│  ├─ Raffle discovery                     │
│  ├─ Automated join                       │
│  └─ Win tracking                         │
└──────────────────────────────────────────┘
```

## ⚙️ Architecture

### Components

```
┌──────────────────────────────────────────┐
│         Flet Web UI (Port 8080)          │
│  ├─ QR Steam Login                       │
│  ├─ Manual Check Button                  │
│  ├─ Scheduler Controls                   │
│  └─ Live Console Logs                    │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│    Flask-like HTTP Handler (app.py)      │
│  ├─ /healthz (keep-alive)                │
│  ├─ /ping (cron-job.org)                 │
│  └─ /status (monitoring)                 │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│      RaffleBot Engine (engine.py)        │
│  ├─ run_check() - Single check           │
│  ├─ start_background_scheduler()         │
│  ├─ get_steam_qr() - QR login            │
│  └─ check_wins_internal() - Prize check  │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│    SeleniumBase Driver (Undetected)      │
│  ├─ Chromium headless browser            │
│  ├─ Anti-detection enabled               │
│  └─ RAM-optimized for Render (512MB)     │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│   takemyskins.com (Target Website)       │
│  ├─ Raffle discovery                     │
│  ├─ Automated join                       │
│  └─ Win tracking                         │
└──────────────────────────────────────────┘
```

### Keep-Alive System (100% FREE)

```
Internal Keep-Alive:
  app.py (self-ping thread) 
    └─> HTTP GET /healthz every 10 min
        └─> Health server responds ✓
            └─> Dyno stays awake

External Keep-Alive (Redundant):
  cron-job.org (external service - GRATIS)
    └─> HTTP GET /healthz every 10 min
        └─> Health server responds ✓
            └─> Double protection against spin-down
```

---

## 🔐 Steam Authentication

### Method: QR Code (FREE & Secure) ✅

```
1. Click "Generează QR Code Steam"
2. QR appears in browser
3. Scan with Steam Mobile app
4. Login confirmed
5. Session saved to disk
6. Bot can run headless
```

**Secure**: No password needed, QR only  
**Free**: No paid options needed  
**Session**: Lasts until dyno restart (rare)  

When dyno restarts (~once per week or less):
- Session lost (free tier limitation)
- Just click QR button again
- Takes 1 minute to re-login
- Bot continues working

**No paid persistent disk needed!** This is acceptable for free tier.

---

## 📊 Key Endpoints

| Endpoint | Purpose | Response |
|----------|---------|----------|
| `GET /healthz` | Basic health check | Plain text: "ok" |
| `GET /ping` | JSON ping (cron-job.org) | `{"status": "alive"}` |
| `GET /status` | Full app status | `{"app": "...", "status": "running"}` |
| `/` | Web UI (port 8080) | Flet app interface |

---

## 🛠️ Configuration

### Environment Variables

```env
# Application
PORT=8080                       # Main web server port
HEALTHCHECK_PORT=8081          # Health server port

# Keep-Alive
SELF_PING_INTERVAL=600         # Internal ping interval (seconds)

# Scheduler
SCHEDULER_INTERVAL=21600       # Check interval (6 hours default)

# Optional: Persistent storage
SESSION_DIR=/var/data/user_session  # If using Render disk
```

### Browser Optimization (for Render 512MB RAM)

In `engine.py`, chromium args are optimized:
```python
chromium_arg="--no-sandbox,--disable-dev-shm-usage,--disable-gpu,--disable-extensions"
```

This prevents OOM errors on Render Free.

---

## 📈 Monitoring & Logs

### Real-time Logs in Web UI

- Console tab shows live logs
- Timestamps for each entry
- Color-coded by type (info/warning/error)

### Render Logs

Check Render dashboard → "Logs" tab for:
```
[KEEP-ALIVE] Self-ping OK: http://127.0.0.1:8081/healthz
Pornesc verificarea automată a raflelor (Background Task)...
[QR] Accesez pagina de login Steam...
[QR] Trimis pe UI: 45234 bytes base64
Se deschide browserul...
Am găsit 12 rafle pe pagină.
```

### External Monitoring (Cron-Job.org)

1. Go to https://cron-job.org/en/
2. Create job pointing to `/status` endpoint
3. Get email alerts if app crashes

---

## 🚨 Troubleshooting

### App stops after 30 minutes
**Problem**: Render Free dyno spins down (no activity for 15+ min)  
**Solution**: 
- Verify self-ping logs (`[KEEP-ALIVE]` every 10 min)
- Enable external cron-job.org monitoring
- See `KEEP_ALIVE.md` for detailed guide

### QR Code doesn't appear
**Problem**: Steam QR not rendered in browser  
**Solution**:
- Increase timeout: Change `time.sleep(5)` → `time.sleep(10)` in engine.py
- Check browser console (F12) for errors
- Verify base64 encoding in logs

### Bot doesn't run scheduled checks
**Problem**: Scheduler starts but no checks execute  
**Solution**:
- Manual Steam login required (QR scan)
- Check session path exists: `./user_session/Default`
- Verify `SCHEDULER_INTERVAL` > 60 seconds
- Check logs for errors

### High memory usage
**Problem**: Chrome takes 300+ MB, Render limit is 512 MB  
**Solution**:
- Increase RAM limit (paid plan) or
- Reduce check frequency (increase `SCHEDULER_INTERVAL`) or
- Use persistent disk to skip re-login overhead

---

## 📖 Full Documentation

- **QUICK_START.md** ⚡ - Deploy in 5 minutes (START HERE!)
- **README.md** - Project overview & architecture (this file)
- **RENDER_DEPLOYMENT.md** - Detailed Render setup & troubleshooting
- **KEEP_ALIVE.md** - Keep-alive strategies (prevent spin-down)
- **README_RENDER.md** - Steam session management on free tier
- **LOCAL_TEST_GUIDE.md** - Local testing procedures
- **DATABASE.md** - Database configuration (SQLite/PostgreSQL)
- **DEPLOYMENT_CHECKLIST.md** - Pre/post deployment verification

---

## 🤝 Contributing

Issues & suggestions welcome!

---

## 📝 License

MIT License - See LICENSE file

---

## ⭐ Key Takeaways

✅ **Free hosting** on Render (no credit card)  
✅ **24/7 uptime** with keep-alive pings  
✅ **Secure login** with Steam QR codes  
✅ **Automated raffles** every 6 hours  
✅ **Web interface** accessible anytime  
✅ **Fully documented** with troubleshooting  

**Ready to deploy?** → See `DEPLOYMENT_CHECKLIST.md` 🚀

---

**Last Updated**: 2026-08-01  
**Version**: 1.0.0  
**Status**: Production Ready ✓

