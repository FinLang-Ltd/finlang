# FinLang v0.7.6 Release Notes
*Released: 9 March 2026*

---

## Summary

v0.7.6 is a rulepack correction release. No engine changes. No breaking changes. Existing rules and workflows are unaffected.

---

## What Changed

### Bundled Rulepack Coverage Correction

Three bundled pack rules introduced in v0.7.5 were found to be over-tightened, causing missed matches on valid transactions. Affected patterns have been reverted to restore v0.7.2 coverage parity.

Files updated: `01-vendors-retail.fin`, `05-financial.fin`, `06-compliance.flags.fin`.

Examples:
- `* FX *` → `*FX*` in `05-financial.fin` and `06-compliance.flags.fin` — space-padding caused missed matches on FX memo variants such as `FX TRANSFER` and `SWIFT FX`
- `ALDI*` → `*ALDI*` in `01-vendors-retail.fin` — prefix-only pattern unnecessarily restricted coverage

No categories or flags change for transactions already correctly matched in v0.7.5. Only previously missed transactions are now correctly categorised.

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
| `src/finlang/rulepacks/01-vendors-retail.fin` | Rulepack coverage correction |
| `src/finlang/rulepacks/05-financial.fin` | Rulepack coverage correction |
| `src/finlang/rulepacks/06-compliance.flags.fin` | Rulepack coverage correction |

---

*See [CHANGELOG.md](../../CHANGELOG.md) for full version history.*
