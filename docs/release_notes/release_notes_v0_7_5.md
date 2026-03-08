# FinLang v0.7.5 Release Notes
*Released: 8 March 2026*

---

## Summary

v0.7.5 is a hardening release focused on rulepack safety and test suite integrity. No engine changes. No breaking changes. Existing rules and workflows are unaffected.

---

## What Changed

### Bundled Rulepack Wildcard Hardening

Unpadded short wildcard tokens in the bundled packs were identified as capable of producing false matches on unrelated counterparty names. Affected patterns have been replaced with space-padded equivalents.

Files updated: `02-transport.fin`, `01-vendors-retail.fin`, `05-financial.fin`, `06-compliance.flags.fin`.

Example: `*TFL*` → `TFL*` — prevents matching counterparties containing "TFL" as a substring (e.g. NETFLIX).

No categories or flags change for correctly-matched transactions. Only false-positive matches are eliminated.

---

## No Engine Changes

The FinLang engine (`finlang_engine.py`) is unchanged. All performance benchmarks from v0.7.4.post1 remain valid.

- Enterprise throughput: ~27K rows/sec (5M × 50 cols)
- Integrity throughput: ~167K rows/sec (FastIO, 20M rows)

---

## Upgrade

```bash
pip install --upgrade finlang
```

No migration required. Existing `.fin` rules, map files, and workflows are fully compatible.

---

## Files Modified

| File | Change |
|------|--------|
| `src/finlang/rulepacks/02-transport.fin` | Wildcard hardening |
| `src/finlang/rulepacks/01-vendors-retail.fin` | Wildcard hardening |
| `src/finlang/rulepacks/05-financial.fin` | Wildcard hardening |
| `src/finlang/rulepacks/06-compliance.flags.fin` | Wildcard hardening |

---

*See [CHANGELOG.md](../../CHANGELOG.md) for full version history.*
