# ⚠️ IMPORTANT: How to Start AI Engine

## ✅ CORRECT WAY:

```bash
./start.sh
```

OR

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## ❌ WRONG WAY:

```bash
uvicorn main:app --port 8000  # Missing --host 0.0.0.0
```

---

## Why `--host 0.0.0.0` is Required:

- **Without it:** AI engine only listens on `127.0.0.1` (localhost)
- **Problem:** Docker containers can't reach `127.0.0.1` of the host
- **Result:** Backend gets "Connection refused" errors
- **Solution:** Use `0.0.0.0` to listen on all network interfaces

---

## Quick Test:

```bash
# After starting, verify it's accessible:
curl http://192.168.100.102:8000/health

# Should return: {"status":"ok"}
```

---

See `QUICK_START.md` for full documentation.
