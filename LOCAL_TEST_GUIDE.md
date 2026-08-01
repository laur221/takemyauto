# 🧪 Local Testing Guide

## Pre-requisites

```bash
# Python 3.10+
python --version  # Should show 3.10+

# Git
git --version
```

---

## Setup (First Time)

```bash
# 1. Clone repository
git clone https://github.com/laur221/takemyauto.git
cd takemyauto

# 2. Create virtual environment (recommended)
python -m venv venv

# On Windows:
venv\Scripts\activate

# On Mac/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify installation
python -c "from seleniumbase import Driver; print('✓ SeleniumBase installed')"
python -c "import flet; print('✓ Flet installed')"
```

---

## Run Application

### Terminal 1: Start App

```bash
cd takemyskinauto
python app.py
```

Expected output:
```
Health server pornit pe portul 8081 (/healthz).
[KEEP-ALIVE] Self-ping OK: http://127.0.0.1:8081/healthz
Flet app started on: http://localhost:8080
```

### Terminal 2: Test Health Endpoints

```bash
# Basic health check
curl http://localhost:8081/healthz
# Expected: "ok"

# JSON ping
curl http://localhost:8081/ping
# Expected: {"status": "alive"}

# Full status
curl http://localhost:8081/status
# Expected: {"app": "TakeMySkins Automator", "status": "running"}
```

### Browser: Access Web UI

```
Open: http://localhost:8080
```

Expected:
- Title: "TAKEMYSKINS BOT"
- Buttons: "Login Steam", "Pornire Automatizare", "Refresh Stats"
- QR Code section visible
- Console logs area

---

## Feature Testing Checklist

### 1. ✅ Health Server (Endpoints)

```bash
# Terminal 2
curl http://localhost:8081/healthz

# Expected:
# 200 OK
# "ok"
```

### 2. ✅ Self-Ping (Keep-Alive)

Check Terminal 1 logs every 10 minutes:
```
[KEEP-ALIVE] Self-ping OK: http://127.0.0.1:8081/healthz
```

**What to look for**:
- Message appears every 10 minutes exactly
- Status code 200
- No connection errors

### 3. ✅ Web UI (Flet Interface)

Open http://localhost:8080

**Check**:
- [ ] Page loads (dark theme)
- [ ] Title "TAKEMYSKINS BOT" visible
- [ ] 3 main buttons present
- [ ] Console log area scrollable
- [ ] Stats section shows table

### 4. ✅ QR Code Generation

Click "Generează QR Code Steam" button:

**Expected**:
1. Button disables (gray out)
2. Message: "Inițiez cerere QR..."
3. Browser window opens (Steam login page)
4. QR Code appears in web UI (250x250 px)
5. Message: "Scanează codul cu aplicația Steam Mobile"

**Troubleshooting**:
- If QR doesn't appear: Check Chrome is installed
- If browser doesn't open: Verify ChromeDriver works
- Increase timeout if slow: Edit engine.py line 178, change `time.sleep(5)` → `time.sleep(10)`

### 5. ✅ Background Scheduler (Optional - Long Test)

This normally runs checks every 6 hours. To test:

**Option A: Manual Check**

Click "Pornire Automatizare" → Starts manual check immediately

Expected:
- Button disables
- Console shows:
  ```
  Se deschide browserul...
  Am găsit X rafle pe pagină.
  Sunt deja înscris la o raflă...
  Am apăsat pe Join...
  ```
- Stats update after completion

**Option B: Auto-Scheduler (Requires Steam Login)**

1. Click "Generează QR Code Steam"
2. Scan QR with Steam Mobile
3. Wait for login confirmation
4. Scheduler starts automatically
5. Next check will run in 6 hours (or set SCHEDULER_INTERVAL env var to test faster)

**Test faster**:
```bash
# Set to 2 minutes for testing
export SCHEDULER_INTERVAL=120
python app.py
```

---

## Performance Monitoring

### RAM Usage

Monitor Chrome memory usage:

```bash
# Option 1: Task Manager (Windows)
# Ctrl+Shift+Esc → Look for "chrome" processes

# Option 2: System Monitor (Linux/Mac)
# top -p $(pgrep -f "chrome")
```

Expected for Render Free (512MB total):
- Idle: 100-150 MB
- During check: 250-350 MB
- Peak: Should not exceed 400 MB

### CPU Usage

Normal:
- Idle: 0-2%
- During check: 30-50%
- Self-ping: < 1%

---

## Log Analysis

### Console Logs (in web UI)

**Format**: `[HH:MM:SS] Message`

**Color coding**:
- 🔵 Blue: Info messages
- 🟠 Orange: Warnings
- 🔴 Red: Errors

### System Output (Terminal)

**Expected messages**:
```
Health server pornit pe portul 8081
[KEEP-ALIVE] Self-ping OK: ...
Pornesc verificarea automată...
Se deschide browserul...
Am găsit N rafle pe pagină.
```

**Error patterns** to watch for:
```
Timeout at host:port          → Network issue
Failed to locate element      → Page changed
Out of memory                 → RAM full (Render 512MB limit)
Cannot find Chrome driver     → Installation issue
```

---

## Debugging

### Enable Verbose Logging

Edit `app.py`, add before `ft.app()`:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Chrome Driver Version

```bash
python -c "from seleniumbase import Driver; d = Driver(); print(d.__dict__)"
```

### Test Database Connection (if using PostgreSQL)

```bash
python -c "from db_manager import DBManager; db = DBManager(); db.setup_db(); print('✓ DB OK')"
```

### Test Individual Components

```python
# Test engine
from engine import RaffleBot
from db_manager import DBManager

db = DBManager()
bot = RaffleBot(db)
status = bot.run_check(is_headless=True)
print(f"Check result: {status}")
```

---

## Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| App won't start | Dependencies missing | `pip install -r requirements.txt` |
| Port already in use | Another app on 8080/8081 | Change PORT env var |
| Chrome not found | Not installed | `pip install seleniumbase` then retry |
| QR doesn't appear | Steam page changed | Increase timeout in engine.py |
| "Timeout" errors | Network issue | Check internet connection |
| High memory | Long-running checks | Reduce check frequency |

---

## Performance Baseline (Local)

On a decent machine (i5, 8GB RAM):

| Operation | Time | RAM |
|-----------|------|-----|
| App startup | 3-5 sec | 50 MB |
| Health server startup | 1 sec | +5 MB |
| Browser open | 8-10 sec | +150 MB |
| QR Code display | 3 sec | +20 MB |
| Single raffle check | 15-20 sec | 250 MB peak |
| Full scan (12 raffles) | 120-180 sec | 300 MB peak |

---

## Test Checklist Before Deployment

- [ ] App starts without errors
- [ ] Health endpoints respond (curl tests)
- [ ] Web UI loads in browser
- [ ] QR Code button works
- [ ] Self-ping logs appear every 10 min
- [ ] Manual check completes successfully
- [ ] Stats update after checks
- [ ] No memory leaks (RAM stable)
- [ ] No Python errors in console

---

## Deployment Readiness

Once all above pass:

```bash
# Commit changes
git add -A
git commit -m "Final testing complete - ready for Render deployment"

# Push to GitHub
git push origin main

# Then deploy to Render.com (see DEPLOYMENT_CHECKLIST.md)
```

---

## Support Resources

- `README.md` - Project overview
- `KEEP_ALIVE.md` - Keep-alive strategies
- `README_RENDER.md` - Steam session on Render
- `DEPLOYMENT_CHECKLIST.md` - Production deployment

---

**Happy testing!** 🧪 If issues persist, check logs and error messages carefully.

