# FinLang v0.7.1 Release Notes

**Build Date:** January 2026
**Theme:** Modern Runtime Hardening

This release focuses on future-proofing the FinLang engine for Python 3.13+ and Pandas 3.0 environments. It eliminates stateful regex compilation in favor of stateless string patterns.

### 🛡️ Core Engine
* **Fix:** Resolved a Python 3.13+/Pandas 3.0 regex flag conflict in `~` wildcard matching.
* **Change:** Wildcard matching now uses string regex patterns (no precompiled `re.Pattern`) and relies on Pandas string methods with `case=False`.

### ⚙️ Configuration & CI
* **Python Support:** Officially verified for **Python 3.13** and **Python 3.14**.
* **CI Matrix:** Updated testing infrastructure to validate against the full spectrum (Python 3.10–3.14).

### 📦 Upgrading
```bash
pip install finlang --upgrade