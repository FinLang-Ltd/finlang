# FinLang v0.7.4 Release Notes
*Released: 1 March 2026*

---

## Summary

v0.7.4 is a correctness-focused release that restores the `exclude` feature (broken since v0.6.4 launch), fixes a cache staleness bug in rule chaining, and introduces a comprehensive test suite (81 daily tests across engine contracts, tool validation, and rule acceptance). The engine module has been renamed from `finlang_engine_v0_6_4.py` to `finlang_engine.py`.

No performance regression. Benchmarks re-validated at v0.7.4.post1 show 3–5% improvement across most data shapes, attributed to the cache invalidation fix eliminating redundant evaluation. Integrity test throughput improved ~5% (FastIO: 159K → 167K rows/s at 20M rows). Headline enterprise throughput remains ~27K rows/sec at 5M × 50 columns.

---

## Bug Fixes

### Exclude Feature Restored (Critical)
The `exclude` functionality has been non-operational since the v0.6.4 launch due to a dead `continue` statement that bypassed all exclude logic. This release restores full exclude support with improvements:

- **Intent-based initialisation:** The exclude column appears only when the ruleset references exclude. No exclude rules = no column (clean schema).
- **Boolean coercion:** Handles string `"true"`/`"false"` from CSV input, coerces to proper Python booleans.
- **Second-pass survival:** Exclude values from a previous pass are preserved as proper booleans even when the current ruleset has no exclude rules (growth loop safe).
- **CLI passthrough:** The exclude column now appears in output CSV (was previously filtered out by the CLI layer).

### Cache Invalidation Fix (Critical)
Rules matching on fields modified by earlier rules (e.g., Rule A sets `category = "Vendor"`, Rule B matches `category == "Vendor"`) now correctly see updated values. Previously, stale cached column data could cause later rules to miss matches.

### Audit Improvements
- Post-state snapshots now use defensive `.copy()` to prevent view-mutation issues.
- Exclude diffs serialize as JSON booleans (`true`/`false`) rather than strings (`"True"`/`"False"`), ensuring downstream JSON consumers work correctly.

---

## Exclude Behaviour (Option 2 — Marker Only)

The `exclude` column is a mutable boolean marker. It does **not** freeze rows. Later rules can still modify excluded rows, and a later rule can set `exclude = false` to un-exclude a row. This enables the **Exception Pattern**:

```fin
rule "Blacklist Amazon" {
  match:
    - counterparty ~ "*AMAZON*"
  set:
    - exclude
}

rule "Whitelist high-value Amazon" {
  match:
    - counterparty ~ "*AMAZON*"
    - amount in 5000..999999
  set:
    - exclude = false
    - flags += "Capital_Expenditure"
}
```

The audit trail captures the full chain: `exclude false→true` (blacklist), then `exclude true→false` + flag addition (whitelist).

---

## New Tests

### `test_rule_interactions.py` (22 tests)
Engine state-transition contract tests covering:

1. Cache invalidation (category and flags chains)
2. Exclude basic behaviour (boolean marker, column presence/absence)
3. Second-pass coercion (growth loop round-trip)
4. Exception pattern (blacklist then whitelist)
5. Audit modes (none/lite/full)
6. Boolean serialisation (JSON roundtrip)
7. Exclude does not freeze rows (Option 2 contract)
8. parse_action shortcut
9. Idempotency
10. Edge case: `exclude = false` without prior exclude

### `test_discover_suggest.py` (20 tests)
Discover/suggest tool validation covering:

- Exclude-aware discovery (excluded counterparties filtered)
- Fingerprint dedup (identical descriptions collapsed)
- Rule generation (suggest produces valid `.fin` syntax)
- Dedup safety (suggested rules don't duplicate existing rules)
- End-to-end pipeline (discover → suggest → apply)

### `test_rule_correctness.py` (26 tests)
Golden-path acceptance tests proving `rules.demo.fin` + bundled packs produce expected output on known data:

- Category correctness (7 tests): matched rows get `Review`, unmatched stay empty
- Flag correctness (9 tests): token-level verification of Retail, Transport, Fuel, Subscription flags
- Structural integrity (2 tests): row count preserved, immutable fields (date, amount, counterparty, memo) unchanged
- Comprehensive sweeps (2 tests): full 16-row sweep for categories and flags

### Daily Gate Integration
All three test suites integrated into `quick_check.ps1` (6 gates, 81 tests total). Inherited by `full_test_suite.ps1` and `cleanroom_test.ps1`.

---

## Breaking Changes

### Engine Module Renamed
`finlang_engine_v0_6_4.py` → `finlang_engine.py`. If you import the engine directly (not via the CLI), update your import:

```python
# Before
from finlang.engine.finlang_engine_v0_6_4 import run_audit

# After
from finlang.engine.finlang_engine import run_audit
```

---

## Upgrade

```bash
pip install --upgrade finlang
```

Verify:
```bash
finlang --version
# FinLang 0.7.4
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/finlang/engine/finlang_engine.py` | Renamed + 7 engine fixes |
| `src/finlang/cli/run_finlang.py` | Import paths + exclude passthrough + version bump |
| `src/finlang/__init__.py` | Version bump |
| `pyproject.toml` | Version bump |
| `test_rule_interactions.py` | New (22 engine contract tests) |
| `test_discover_suggest.py` | New (20 discover/suggest tool tests) |
| `test_rule_correctness.py` | New (26 golden-path acceptance tests) |
| `quick_check.ps1` | Rewritten: 6 gates, 81 tests, clean single-line display |
| `full_test_suite.ps1` | New: single-command wrapper for all tiers + contracts |
| `cleanroom_test.ps1` | New: disposable venv PyPI validation (gates 1–4) |

---

© FinLang Ltd
