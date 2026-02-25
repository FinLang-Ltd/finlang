# FinLang v0.7.3 Release Notes
**Date:** 2026-02-25
**Tag:** `Correctness & Hardening`

## Overview
This patch release closes the only silent failure condition in the FinLang parser. It adds parse-time validation to reject whitespace in `flags +=` values, preventing silent token splitting that could corrupt flag semantics in audit trails and downstream processing.

## 🚀 Key Changes

### 1. Flags Whitespace Validation
The `flags` field stores space-separated tokens internally. Previously, a rule like `flags += "Large Tx"` would silently split into two separate flags (`Large` and `Tx`) instead of one flag (`Large Tx`), producing incorrect output with no error.
* **Fix:** The parser now rejects any `flags +=` value containing whitespace at parse time, before data is loaded.
* **Impact:** Rules with whitespace in flag values will now fail immediately with a clear error message and remediation guidance. All existing rulepacks and user rules using single-token flags (the documented convention) are unaffected.

### 2. Documentation Updates
The flags field invariant ("flag values must be single tokens containing no whitespace") is now explicitly documented in `rule_language.md` and `mapping_guide.md`.

## 🛠 Upgrade Instructions
No breaking changes for valid rules. Upgrade via standard mechanisms:

```bash
pip install --upgrade finlang
# or for local dev
git pull && pip install -e .
```

Rules containing whitespace in flag values (e.g. `flags += "Large Tx"`) will now fail at parse time. Replace with underscores or camelCase: `flags += "Large_Tx"` or `flags += "LargeTx"`.
