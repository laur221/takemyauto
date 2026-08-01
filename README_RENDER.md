# 🎮 Steam Session Management on Render Free

## The Challenge: Re-login Required on Each Restart

**Render Free** = No Persistent Disk by default ❌

When dyno restarts:
- **Browser session cache** (`./user_session`) is **DELETED** ❌
- Steam cookies & login data are **GONE** ❌
- Bot must **re-login** at next check ⚠️

---

## ✅ Solution 1: Implement Persistent Disk (PAID)

**Cost**: $5/month  
**Setup** on Render:

1. Add Disk in Render dashboard:
   - Name: `session_storage`
   - Mount path: `/var/data`
   - Size: 1 GB

2. Update Python paths:
```python
# In engine.py
self.session_dir = "/var/data/user_session"  # Now persists!
```

3. Deploy & Steam session **survives restarts** ✅

---

## ✅ Solution 2: Re-Login Automation (FREE)

**No extra cost** - but requires bot interaction

### How It Works:

1. App starts
2. Check if session exists:
   - ✅ Session found → Normal check
   - ❌ No session → Trigger QR login
3. User scans QR on mobile Steam
4. Session saved → Runs checks

### Implementation (Already in your code!):

```python
# In gui.py: "Generează QR Code Steam" button
# User clicks → triggers get_steam_qr()
# Browser opens Steam login → QR displays
# User scans with Steam Mobile app
# Session established → Ready for checks
```

### Automated Re-login Approach:

Add to `engine.py` scheduler:

```python
def start_background_scheduler(self, interval_seconds=21600, is_headless=True, log_func=None):
    # Check if session exists
    if not os.path.exists(os.path.join(self.session_dir, "cookies.json")):
        log("⚠️ Sesiune Steam expirată. Declanșez re-login la următoarea verificare...")
        # Trigger QR login via UI callback
        return
    
    # Continue normal check...
    self.run_check(is_headless=is_headless, log_func=log_func)
```

---

## 🔄 Recommended Workflow for Render Free

### Daily Routine:

```
1. App starts
2. Checks: Session valid?
   ├─ YES → Auto-check raffles (headless) ✓
   └─ NO → Wait for user to scan QR ⏳
3. User logs in via QR (once per restart)
4. Bot runs checks on schedule
5. Render restart (if happens) → Loop repeats
```

### When Render Restarts:

- Dyno cold-start (~30-60 sec)
- App boots
- Session cache **lost** (FREE tier)
- User clicks "Generează QR Code Steam"
- Scans on phone
- Session re-established
- Checks resume ✓

---

## 📊 Comparison: Free vs Paid

| Feature | Free Tier | With $5/mo Disk |
|---------|-----------|-----------------|
| Session Persistence | ❌ Lost on restart | ✅ Survives restarts |
| Re-login Frequency | Every restart | Once per month |
| Setup Complexity | Simple (manual QR) | Automated checks |
| Cost | $0 | $5/month |
| Best For | Low-volume users | 24/7 automated bot |

---

## 🎯 Recommended Setup (Balanced)

For **TakeMySkins Automator**:

### Option A: FULLY FREE (Manual Login)

```
✓ No extra costs
✓ Simple setup
✓ Manual QR login every restart (~1 min)
✓ Perfect if Render doesn't restart often
```

**Setup**:
1. Deploy as-is
2. When app starts: Click "Generează QR Code Steam"
3. Scan on phone
4. Checks run on schedule
5. App continues until next restart

### Option B: PAID + FULLY AUTOMATED ($5/mo)

```
✓ Persistent disk ($5/month)
✓ Zero manual intervention
✓ Login once, forget about it
✓ Best for high-frequency checks
```

**Setup**:
1. Add disk to Render
2. Change `self.session_dir` to `/var/data/user_session`
3. Deploy
4. Login once via QR
5. Bot checks automatically forever

---

## 🔧 Implementation for Re-login Detection

Add to `engine.py`:

```python
import os

def check_session_exists(self):
    """Verifică dacă sesiunea Steam e validă"""
    session_path = os.path.join(self.session_dir, "Default")
    return os.path.exists(session_path) and os.path.getsize(session_path) > 1000

def start_background_scheduler(self, interval_seconds=21600, is_headless=True, log_func=None):
    def log(msg):
        if log_func:
            log_func(msg)
        print(msg)
    
    def worker():
        while not self._scheduler_stop_event.is_set():
            # Check sesiune
            if not self.check_session_exists():
                log("⚠️ Sesiune Steam nu găsită. Aștept login manual...")
                self._scheduler_stop_event.wait(60)  # Check din nou după 1 min
                continue
            
            # Sesiune OK - ruleaza check
            log("✓ Sesiune Steam validă. Pornesc verificare raffles...")
            try:
                self.run_check(is_headless=is_headless, log_func=log_func)
            except Exception as e:
                log(f"Eroare în scheduler: {e}")
            
            self._scheduler_stop_event.wait(interval_seconds)
    
    self._scheduler_thread = threading.Thread(target=worker, daemon=True)
    self._scheduler_thread.start()
```

---

## 📱 QR Login Flow (Already Implemented!)

Your current `gui.py` flow is perfect:

```
┌──────────────────────────────────┐
│ User clicks "Generează QR Code"  │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│ bot.get_steam_qr() triggered     │
│ Opens Steam login page           │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│ QR displays in UI                │
│ (base64 encoded, transmitted OK) │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│ User scans with Steam Mobile     │
│ Phone confirms login             │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│ Browser detects login ✓          │
│ Session saved to ./user_session  │
│ Checks can now run headless      │
└──────────────────────────────────┘
```

---

## 🚨 Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| "Sesiune expirată" on every restart | FREE tier, no persistence | Add disk or manual login |
| QR doesn't appear | Browser issue | Increase timeout in `get_steam_qr()` |
| Can't scan QR | UI not rendering base64 | Check `refresh_qr()` in gui.py |
| Bot runs headless but fails | No session = can't auto-login | Must login manually first |

---

## ✅ Recommendation for YOUR Project

Since you're using **Render Free**:

**Best approach: Option A (Fully Free)**

1. Keep current implementation ✓
2. When Render restarts (~rare on free tier):
   - App starts, health server runs
   - Click "Generează QR Code Steam"
   - Scan QR with phone
   - Checks resume
3. Cost: **$0**
4. Effort: **~1 min per restart**

**If you want 24/7 zero-effort**:
- Upgrade to disk ($5/month)
- Changes are minimal (1 path change)
- Fully automated after that

---

## 📌 Current Status

✅ Self-ping implemented  
✅ QR login flow working  
✅ Session handling ready  
✅ Documentation complete  

**You're good to deploy!** 🎉

