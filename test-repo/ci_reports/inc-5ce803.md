# 🚨 Incident Report: CI/CD Deployment Failure in Test Suite

---

## 📋 Summary

| Field | Value |
|-------|-------|
| **Incident ID** | `inc-5ce803` |
| **Service** | `test-repo` |
| **Environment** | `ci-pipeline` |
| **Generated At** | `2026-04-16T06:43:59.474774+00:00` |
| **Error** | `AttributeError: 'NoneType' object has no attribute 'strip'` |

## 💥 Exact Problem

**File:** `auth.py`

> **Root Cause:** AttributeError: 'NoneType' object has no attribute 'strip'

```python
       1 | # auth.py
       2 | from database import DatabaseManager
       3 | 
       4 | def validate_credentials(user, password):
       5 |     # Intentional bug: if user is None, this will throw an AttributeError
       6 |     normalized_user = user.strip().lower() 
       7 |     
       8 |     # Imagine this hashes the password and checks DB
       9 |     db = DatabaseManager()
      10 |     db.connect()
      11 |     result = db.query(f"SELECT id FROM users WHERE user='{user}' AND pass='{password}'")
      12 |     return True
      13 | 
      14 | def login_user(user, password):
      15 |     if validate_credentials(user, password):
      16 |         return "JWT-TOKEN-123"
      17 |     return None
```

> Lines marked with `>>>` are where execution crashed.

## 🔧 All Possible Fixes

> Ranked **most recommended → least**. Apply Fix 1 unless you have a specific reason not to.

### Fix 1: Guard against `None` before calling `.strip()`

**When to use:** The argument can legitimately arrive as `None` — add an early return or raise.

**Before (broken):**
```python
def validate_credentials(user, password):
    normalized_user = user.strip().lower()  # crashes when user is None
```

**After (fixed):**
```python
def validate_credentials(user, password):
    if user is None:
        return False  # or: raise ValueError('user must not be None')
    normalized_user = user.strip().lower()
```

**Why this works:** `user` is `None` when no account is supplied. Checking first prevents the `AttributeError`.

---

### Fix 2: Coerce `None` to empty string with `or`

**When to use:** An empty string is a safe substitute for `None` here (auth will simply fail).

**Before (broken):**
```python
    normalized_user = user.strip().lower()
```

**After (fixed):**
```python
    normalized_user = (user or "").strip().lower()
```

**Why this works:** `(user or "")` converts `None` → `""` inline, so `.strip().lower()` never crashes.

---

### Fix 3: Validate at the public API boundary (`login_user`)

**When to use:** You want zero invalid inputs ever reaching internal helpers.

**Before (broken):**
```python
def login_user(user, password):
    if validate_credentials(user, password):  # user can be None
        return 'JWT-TOKEN-123'
```

**After (fixed):**
```python
def login_user(user, password):
    if not user or not password:
        raise ValueError('user and password are required')
    if validate_credentials(user, password):
        return 'JWT-TOKEN-123'
```

**Why this works:** Entry-point validation makes the whole module robust — no internal helper ever receives `None`.

---

## 🕸️ Code Graph — Affected Locations

- `incident.json` — confidence `0.95` — _matched incident search terms_
- `ci_reports/inc-398731.md` — confidence `0.95` — _matched incident search terms_
- `ci_reports/inc-a2e4cc.md` — confidence `0.72` — _matched incident search terms_
- `auth.py` — confidence `0.64` — _matched incident search terms_
- `ci_reports/inc-27fbbc.md` — confidence `0.64` — _matched incident search terms_
- `test_auth_raw.py` — confidence `0.52` — _matched Nexus project-scoped code graph, summary overlaps incident terms, blast radius 7, 5 immediate graph links_

## ✅ Immediate Next Steps

1. Apply **Fix 1** from the section above.
2. Add a regression test: `assert login_user(None, 'x') raises ValueError`.
3. Re-run the CI pipeline to confirm the build turns green.
4. If the issue persists, escalate with the full stack trace to the on-call team.
