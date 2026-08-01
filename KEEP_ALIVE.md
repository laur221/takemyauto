# 🚀 Keep-Alive Guide - Render Free 24/7

## Problema: Render Free (dyno gratuit) - 2 Limitări Critice

### 1️⃣ Spin-Down: App se suspend după 15 min de inactivitate
- ⏸️ Dyno se "oprește" complet (suspendă)
- ⏱️ Prima cerere după asta: **+50 sec delay** (spin-up time) 🐌
- ⚠️ User vede: "Aplicația se încarcă..." timp de 1 minut

### 2️⃣ Scheduler Impact
- Browser checks pornesc ~50 sec mai târziu decât intenționat
- Dacă interval = 6 ore și niciun ping extern → dyno va fi suspendat 50% din timp

Soluția: **Ping-uri periodice cu cron-job.org GRATUIT** previne spin-down

---

## ✅ Metoda 1: Self-Ping (INCORPORAT DEJA)

### Ce se întâmplă?

1. `app.py` pornește un **health server** pe port `PORT + 1` (ex: 8081)
2. Fiecare **5 minute** (optimizat pentru Render), aplicația se **self-ping-uiește** intern
3. Aceasta ține viu procesul și **previne spin-down**
4. Fără ping extern = dyno se suspend → +50 sec delay la următoarea cerere

### ⚡ Optimizare Critică: Timeout-uri pentru Spin-Up

Când dyno se relansează:
- ✅ Aplicația se pornește (~20 sec)
- ✅ Health server se inițiază (~5 sec)  
- ✅ Self-ping asteaptă (timeout 10 sec) ✓

**Important**: Timeout-uri mari pentru a permite spin-up!

---

## ✅ Metoda 2: Cron-Job.org (RECOMANDATĂ PENTRU SIGURANTA MAXIMA)

### Setup (2 minute):

1. **Accesează**: https://cron-job.org/en/

2. **Sign up GRATUIT** (nu-ți cere card credit)

3. **Crează noua Job**:
   - **Title**: `TakeMySkins Keep-Alive`
   - **URL**: `https://your-app.onrender.com/healthz`
   - **Execution time**: `Every 10 minutes` ⭐ CRÍTICO - previne spin-down
   - **Timeout**: `30 seconds` (permite spin-up delay)
   - **Notification**: `On failure`

4. **Save & Activate** ✓

### De ce Cron-Job.org?

✅ **Gratuit** - Fără limite, fără card credit  
✅ **Reliable** - 99.9% uptime  
✅ **Simplu** - O configurare, gata  
✅ **Monitoring** - Email notificări dacă cade  
✅ **Previne spin-down** - Ping la 10 min = dyno rămâne ACTIV 24/7 🚀

---

## ✅ Metoda 3: UptimeRobot (ALTERNATIVA)

Dacă vrei mai mult monitoring:

1. Accesează: https://uptimerobot.com
2. **Ping interval**: 5 minute
3. **URL**: `https://your-app.onrender.com/status`
4. **Alerts**: Email dacă e down

---

## 📊 Diagrama Keep-Alive

```
┌─────────────────────────────────────────────┐
│         TakeMySkins App (Render)            │
│  ┌───────────────────────────────────────┐  │
│  │  Self-Ping Thread (every 10 min)      │  │
│  │  Internal: localhost:8081/healthz ─→ OK  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
         ↑
         │ (every 5 min, HTTP GET)
         │
┌──────────────────────────┐
│   Cron-Job.org           │
│   (External Ping)        │
└──────────────────────────┘
```

---

## 🔧 Environment Variables (Render.com)

Adaugă în Render dashboard:

```env
PORT=8080
HEALTHCHECK_PORT=8081
SCHEDULER_INTERVAL=21600  # 6 ore între verificări raffles
```

---

## ✨ Testare Local

```bash
# Terminal 1: Pornește app
python app.py

# Terminal 2: Testează endpoint-uri
curl http://localhost:8081/healthz
curl http://localhost:8081/ping
curl http://localhost:8081/status
```

---

## 🚨 Troubleshooting

| Problem | Solution |
|---------|----------|
| App cade după 30 min | Self-ping nu rulează - verifyca logs |
| Cron-Job.org nu atacă | Firewall block? Testează URL direct |
| Port 8081 nu răspunde | Dockerfile nu expose portul health |
| Rate limit | Crește interval la 10 minute în cron-job |

---

## 📌 Concluzie

- **Self-ping** = Keep-Alive intern, automat ✓
- **Cron-Job.org** = Backup extern, 100% FREE ✓
- **Combo = Perfect** pentru Render Free 24/7 running ✅

