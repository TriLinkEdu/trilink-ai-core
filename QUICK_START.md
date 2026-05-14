# TriLink AI Engine - Quick Start

## ⚠️ IMPORTANT: Always use `--host 0.0.0.0`

The AI engine MUST listen on all interfaces to be accessible from Docker containers.

---

## 🚀 START AI ENGINE (Recommended):

```bash
cd /home/sadam/Development/trilink/ai-engine
./start.sh
```

---

## 🚀 START AI ENGINE (Manual):

```bash
cd /home/sadam/Development/trilink/ai-engine
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## ❌ WRONG (Don't do this):

```bash
# This only listens on 127.0.0.1 - Docker can't reach it!
uvicorn main:app --port 8000
```

---

## ✅ VERIFY IT'S WORKING:

### 1. Check from host:
```bash
curl http://192.168.100.102:8000/health
```

### 2. Check from Docker:
```bash
docker exec trilink-backend-api-1 wget -qO- http://192.168.100.102:8000/health
```

### 3. Test AI chat:
```bash
curl -X POST "http://192.168.100.102:8000/api/ai/chat" \
  -H "X-API-Key: trilink-dev-shared-secret" \
  -H "Content-Type: application/json" \
  -d '{"student_id":"test","message":"Hello","grade_level":9}'
```

---

## 🔍 TROUBLESHOOTING:

### Problem: "Connection refused" from backend
**Cause:** AI engine listening on 127.0.0.1 only  
**Solution:** Restart with `--host 0.0.0.0`

### Problem: "500 Internal Server Error"
**Cause:** Missing or invalid Groq API key  
**Solution:** Check `.env` has `GROQ_API_KEY=...` (uncommented)

### Problem: "401 Unauthorized"
**Cause:** Missing or wrong API key  
**Solution:** Check `.env` has `INTERNAL_API_KEY=trilink-dev-shared-secret`

---

## 📝 CONFIGURATION:

### Required in `.env`:
```env
INTERNAL_API_KEY=trilink-dev-shared-secret
GROQ_API_KEY=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
POSTGRES_URL=postgresql://trilink:trilink_secret@localhost:5433/trilink
MONGO_URL=mongodb://localhost:27017/trilink
```

---

## 🎯 QUICK CHECK:

```bash
# Is it listening on all interfaces?
ss -tlnp | grep 8000

# Should show: 0.0.0.0:8000 (good)
# NOT: 127.0.0.1:8000 (bad - Docker can't reach)
```

---

## 📱 MOBILE APP FLOW:

```
Mobile App
    ↓ HTTP (JWT)
Backend (Docker:4000)
    ↓ HTTP (API Key)
AI Engine (Host:8000)
    ↓ HTTP
Groq API
```

---

**Remember:** Always use `./start.sh` or `--host 0.0.0.0` ! 🚀
