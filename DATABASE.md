# 🗄️ Database Configuration

## Overview

TakeMySkins Automator supports **3 database backends** with automatic fallback:

```
1. Render PostgreSQL (DATABASE_URL) → Production
2. Local PostgreSQL → Development  
3. SQLite (data.db) → Fallback (Render Free)
```

---

## 🚀 Render Free (SQLite)

**Default for Render Free tier** - No setup required ✓

### What Happens:
1. App tries to connect to PostgreSQL
2. Connection fails (no DB service on Free tier)
3. Falls back to SQLite automatically
4. Creates `data.db` in app directory

### Pros:
✅ Zero cost  
✅ Zero setup  
✅ Automatic fallback  
✅ Data persists per dyno  

### Cons:
⚠️ Data lost on dyno restart (unless using persistent disk)  
⚠️ No multi-process support  

**Perfect for**: Testing, small-scale use

---

## 📊 Production (Render PostgreSQL)

### Setup on Render.com:

1. **Create PostgreSQL database**:
   - Render Dashboard → Create → PostgreSQL
   - Choose paid tier ($15/month minimum)

2. **Render auto-sets `DATABASE_URL`**:
   ```
   DATABASE_URL=postgresql://user:pass@host:5432/dbname
   ```

3. **App automatically detects and uses it** ✓

### Example Environment:
```env
DATABASE_URL=postgresql://user123:secretpass@dpg-xyz.render.com:5432/takemyskins_db
```

### Pros:
✅ Data persists forever  
✅ Production-grade reliability  
✅ Multi-instance support  
✅ Automatic backups  

### Cons:
⚠️ $15/month cost  

**Perfect for**: Production deployments

---

## 💻 Local Development (PostgreSQL)

### Setup:

```bash
# 1. Install PostgreSQL locally
# https://www.postgresql.org/download/

# 2. Start PostgreSQL service
# Windows: Services → PostgreSQL
# Mac: brew services start postgresql
# Linux: sudo systemctl start postgresql

# 3. Create database
psql -U postgres
CREATE DATABASE takemyskins;
\q

# 4. Set environment variables (.env)
DB_HOST=localhost
DB_USER=postgres
DB_PASSWORD=your_password
DB_NAME=takemyskins
DB_PORT=5432

# 5. Run app
python app.py
```

### Pros:
✅ Full control  
✅ Testing with real PostgreSQL  
✅ Data persists  

### Cons:
⚠️ Requires local installation  
⚠️ Only for development  

**Perfect for**: Development & testing

---

## 🔄 Fallback Logic

### Connection Attempt Order:

```
┌─────────────────────────────┐
│ Check DATABASE_URL (env)    │
│ (Render PostgreSQL)         │
└────────────┬────────────────┘
             │ If set → Use it
             │
             ▼
┌─────────────────────────────┐
│ Try Local PostgreSQL        │
│ (localhost:5432)            │
└────────────┬────────────────┘
             │ If connects → Use it
             │
             ▼
┌─────────────────────────────┐
│ Fall back to SQLite         │
│ (data.db)                   │
└─────────────────────────────┘
```

### Log Output:

```
# PostgreSQL available:
✓ PostgreSQL disponibil
[DB] Using PostgreSQL

# PostgreSQL unavailable (falls back):
⚠️ PostgreSQL nu e disponibil: Connection refused
ℹ️ Treceți la SQLite (data.db)
[DB] Using SQLite: ./data.db
```

---

## 📋 Database Schema

### Table: `wins`

| Column | Type | Purpose |
|--------|------|---------|
| id | PRIMARY KEY | Auto-increment ID |
| raffle_name | TEXT UNIQUE | Raffle identifier |
| status | TEXT | "JOINED", "WON", "JOIN_NOT_FOUND" |
| item_name | TEXT | Prize name (if won) |
| date | TIMESTAMP | Entry timestamp |

### SQL Versions:

**PostgreSQL**:
```sql
CREATE TABLE IF NOT EXISTS wins (
    id SERIAL PRIMARY KEY,
    raffle_name TEXT UNIQUE,
    status TEXT,
    item_name TEXT,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**SQLite**:
```sql
CREATE TABLE IF NOT EXISTS wins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raffle_name TEXT UNIQUE,
    status TEXT,
    item_name TEXT,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🔒 Security

### Environment Variables (.env)

```env
# Local PostgreSQL
DB_HOST=localhost
DB_USER=postgres
DB_PASSWORD=your_secure_password
DB_NAME=takemyskins
DB_PORT=5432

# .env is in .gitignore - never commit!
```

### Render.com

- `DATABASE_URL` is automatically set by Render
- Never hardcode credentials
- Use Render's environment variable system

---

## 🐛 Troubleshooting

### SQLite Issues

**Problem**: `data.db` grows too large  
**Solution**: 
```bash
# Delete old database (re-creates on restart)
rm data.db
# App will create new data.db with fresh schema
```

**Problem**: Permissions denied on data.db  
**Solution**:
```bash
chmod 644 data.db
python app.py  # Try again
```

### PostgreSQL Issues

**Problem**: "Connection refused" on localhost  
**Solution**:
```bash
# Check if PostgreSQL is running
psql -U postgres  # If fails, start the service

# Windows: Services → PostgreSQL → Start
# Mac: brew services start postgresql
# Linux: sudo systemctl start postgresql
```

**Problem**: Wrong password in .env  
**Solution**:
```bash
# Reset PostgreSQL password
psql -U postgres
ALTER USER postgres WITH PASSWORD 'new_password';
\q

# Update .env
DB_PASSWORD=new_password
```

**Problem**: Database "takemyskins" doesn't exist  
**Solution**:
```bash
psql -U postgres
CREATE DATABASE takemyskins;
\q
python app.py  # App will create schema
```

### Render PostgreSQL Issues

**Problem**: "DATABASE_URL not set" warning  
**Solution**:
- Check Render dashboard → Environment
- PostgreSQL must be created first
- Restart app after adding database

**Problem**: Too many connections  
**Solution**:
- Increase connection pool (if using one)
- Reduce check frequency in `SCHEDULER_INTERVAL`
- Close connections properly (already done in code)

---

## 📊 Data Persistence

### On Render Free (SQLite):

| Scenario | Data Persists? |
|----------|---|
| Browser refresh | ✅ Yes |
| App restart | ✅ Yes (same dyno) |
| Render dyno restart | ❌ No (unless persistent disk) |
| Scheduler runs | ✅ Yes |

**Solution**: Use `persistent disk` ($5/month) to save data across restarts

### On Render Paid (PostgreSQL):

| Scenario | Data Persists? |
|----------|---|
| Browser refresh | ✅ Yes |
| App restart | ✅ Yes |
| Render dyno restart | ✅ Yes |
| Scheduler runs | ✅ Yes |
| Auto-backups | ✅ Yes (daily) |

**Perfect for**: Production environments

---

## 🚀 Migration: SQLite → PostgreSQL

If you start with SQLite and want to upgrade to PostgreSQL:

```bash
# 1. Export SQLite data
sqlite3 data.db ".dump wins" > wins_backup.sql

# 2. Create PostgreSQL database on Render
# (Render dashboard)

# 3. Import data (manual or automated)
psql $DATABASE_URL < wins_backup.sql

# 4. Restart app
# App detects DATABASE_URL and uses PostgreSQL
```

---

## ✅ Configuration Checklist

**For Render Free**:
- [ ] No DATABASE_URL needed
- [ ] App falls back to SQLite automatically
- [ ] `data.db` created on first run
- [ ] Stats display in web UI

**For Render Production**:
- [ ] PostgreSQL database created on Render
- [ ] DATABASE_URL auto-set by Render
- [ ] App uses PostgreSQL automatically
- [ ] Data persists across restarts

**For Local Development**:
- [ ] PostgreSQL installed locally
- [ ] `.env` file configured
- [ ] Database "takemyskins" exists
- [ ] App connects successfully

---

## 📚 Related Files

- `db_manager.py` - Database connection logic
- `.env` - Local configuration (git-ignored)
- `.gitignore` - Excludes `data.db`
- `README.md` - Project overview

---

**Database Status**: ✅ Auto-detecting, fallback-enabled, production-ready

