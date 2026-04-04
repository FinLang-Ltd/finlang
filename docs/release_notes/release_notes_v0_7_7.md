# FinLang v0.7.7 Release Notes
*Released: 4 April 2026*

---

## Summary

v0.7.7 adds built-in integrity verification (`--verify`), fixes a CR/DR parsing bug, and improves fuzzy rule suggestion quality. 118 automated tests across 9 quality gates. No breaking changes.

---

## What Changed

### New: Integrity Verification (`--verify`)

Post-engine SHA-256 fingerprint verification, available as a CLI feature.

- `--verify` — fast mode: fingerprint comparison on immutable fields (date, amount, counterparty)
- `--verify-full` — full mode: fingerprint + field-by-field comparison
- `--verify-output-dir <path>` — generates audit artifacts: `verify_report.json`, `verify_proof.csv`, and `verify_mismatches.csv` (on failure)
- Exit code 3 on verification failure (distinct from 0/1/2)
- Respects all i18n flags (`--decimal`, `--thousands`, `--dayfirst`, `--date-format`)

New module: `src/finlang/tools/verify.py` (~230 lines, fully decoupled from engine).

### Fixed: CR/DR No-Space Parsing

Amount values like `200DR` and `100CR` (no space before the suffix) were incorrectly parsed — `200DR` was treated as positive instead of negative. The `\b` word boundary in the detection regex prevented matching when the suffix was directly adjacent to digits.

Fixed in both `run_finlang.py` and `discover.py`. Spaced variants (`200 DR`, `100 CR`) were already working correctly.

### Improved: Fuzzy Suggest Quality

- Stopword filter added to fuzzy tokenizer: LTD, LLC, PLC, INC, GROUP, COMPANY, CO, SAS, GMBH, CORP. Prevents over-matching patterns like `*GROUP*` when the meaningful token is `*SMITH*`.
- Intra-batch dedup: duplicate fuzzy patterns within a single suggest run are now suppressed.
- Fallback preserved: if stopword removal leaves no tokens, the original tokens are used.

### Maintenance

- `finlang_engine.py` version comment updated to v0.7.6
- Stale filename references in sync comments corrected (`discover_v0_6_4_rc1.py` → `discover.py`, `run_finlang_v0_6_4_rc1a.py` → `run_finlang.py`)
- "Last verified" stamps updated across 9 documentation files
- `integrity_testv2.py` docstring clarification (`.2f` fingerprint contract)

---

## Test Suite

| Metric | v0.7.6 | v0.7.7 |
|--------|--------|--------|
| Automated tests | 89 | 118 |
| Quality gates | 8 | 9 |
| New gate | — | Verify (8 tests) |
| New tests | — | 15 `_to_number` contracts, 2 suggest fuzzy, 8 verify, 4 CR/DR regression |

All 118 tests pass across 9 gates. Full test suite (7 gates including golden masters, adversarial, integrity, contracts) passes.

---

## No Performance Changes

The FinLang engine (`finlang_engine.py`) has no logic changes in this release. All performance benchmarks from v0.7.4.post1 remain valid.

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
| `src/finlang/cli/run_finlang.py` | CR/DR regex fix, `--verify` integration, sync comment |
| `src/finlang/tools/discover.py` | CR/DR regex fix, sync comment |
| `src/finlang/tools/suggest.py` | Stopword filter, intra-batch dedup |
| `src/finlang/tools/verify.py` | **New file** — integrity verification module |
| `src/finlang/engine/finlang_engine.py` | Version comment only |
| `docs/cli_reference.md` | `--verify` flags documented |
| `docs/flags.md` | `--verify` flags added |
| `docs/workflows.md` | Verification workflow section |
| `docs/faq.md` | Exit code 3, verify FAQ |

---

*See [CHANGELOG.md](../../CHANGELOG.md) for full version history.*
