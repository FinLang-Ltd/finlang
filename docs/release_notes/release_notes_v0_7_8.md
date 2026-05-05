# FinLang v0.7.8 Release Notes
*Released: 15 May 2026 (target)*

---

## Summary

FinLang v0.7.8 introduces `--reconcile` — a deterministic challenge layer that compares external categorisation output, including ML-generated output, against rule-attributed FinLang results, producing a row-by-row mismatch report with audit context. When an ML model silently approves a £250K offshore transfer, this is the artefact that shows the disagreement.

137 automated tests across 10 quality gates. Engine byte-identical to v0.7.7. No breaking changes.

---

## What Changed

### New: ML Reconciliation (`--reconcile`)

Independent validation layer that compares FinLang's deterministic output against an external system's CSV output (typically an ML model's). Every disagreement is flagged, the matching rule is named, and the audit reason is attached.

- `--reconcile <ml_output.csv>` — path to the external output to reconcile against. Requires `--audit` and `--audit-mode full` so mismatch rows can carry rule attribution.
- `--reconcile-fields <field[,field...]>` — comma-separated fields to compare. Default: `category`.
- `--reconcile-output-dir <path>` — directory for reconciliation artifacts (`reconcile_report.json`, `reconcile_mismatches.csv`).
- Exit code 3 on any mismatch (consistent with `--verify`); exit code 1 on structural errors (row count mismatch, missing field, missing ML file).
- Coexists with `--verify` — both can run in the same invocation, both report independently.

New module: `src/finlang/tools/reconcile.py` (~470 lines, fully decoupled from the engine).

### New: HTML Reconciliation Report (`--reconcile-html`)

Self-contained HTML report alongside the JSON+CSV artifacts. One file, no JS, no external resources, opens offline. Rule name and audit reason rendered inline against each mismatch. All user-provided strings escaped.

- `--reconcile-html` — boolean flag. Requires both `--reconcile` and `--reconcile-output-dir`. Writes `reconcile_report.html` to the output directory.
- Compliance-context asset: opens in any browser, archives cleanly, no runtime dependencies.

New module: `src/finlang/tools/reconcile_html.py` (~210 lines).

### Design constraints honoured

- **Zero engine changes.** `finlang_engine.py` byte-identical to v0.7.7. Reconciliation is a post-engine comparison phase.
- **Audit-grounded.** Every mismatch carries the rule that fired (from `audit.json`). Without `--audit-mode full`, `--reconcile` refuses to run.
- **Strict by default.** Any mismatch = exit code 3. Compliance officers want binaries, not percentages. Threshold mode is Phase 2.
- **Positional alignment.** Phase 1 MVP requires identical row counts between FinLang output and ML output. Key-based alignment is Phase 2.

---

## Test Suite

| Metric | v0.7.7 | v0.7.8 |
|--------|--------|--------|
| Automated tests | 118 | 137 |
| Quality gates (daily) | 9 | 10 |
| New gate | — | Reconcile (19 tests) |
| New tests | — | 12 reconcile happy/edge + 3 validation rejection + 1 verify+reconcile coexistence + 1 memo enrichment + 2 HTML render/escape/dual-flag |

All 137 tests pass across 10 gates. Full test suite (7 gates including golden masters, adversarial, integrity, contracts) passes. Cleanroom PyPI validation (4 gates) passes against the published wheel.

---

## No Engine Changes

The FinLang engine (`finlang_engine.py`) is byte-identical to v0.7.7. Reconciliation is implemented as a post-engine comparison phase, exactly like `--verify`. All performance characteristics from v0.7.7 remain valid.

- Enterprise throughput: ~27,900 rows/sec (5M × 50 cols, locked benchmark)
- Integrity throughput: ~217K rows/sec (FastIO, 20M rows, locked benchmark)
- Reconciliation overhead: ~25–100s wall-clock for the 19-test suite (subprocess-dominated, varies with cache state); per-run reconcile-only overhead measured in milliseconds for typical demo data

---

## Upgrade

```bash
pip install --upgrade finlang
```

No migration required. Existing `.fin` rules, map files, and workflows are fully compatible. Reconciliation is purely additive — invocations that don't use `--reconcile` behave identically to v0.7.7.

---

## Worked Example

Run reconciliation against the bundled corporate treasury demo and an ML output containing a deliberate offshore-jurisdiction mismatch:

```bash
finlang \
  --input transactions.csv \
  --rules compliance.fin \
  --output finlang_out.csv \
  --audit audit.json --audit-mode full \
  --reconcile ml_output.csv \
  --reconcile-output-dir audit/ \
  --reconcile-html
```

Output:

```
=== Reconciliation Complete ===
   Rows compared:    15
   Matches:          13 (86.67%)
   Mismatches:        2

   Status: REVIEW REQUIRED

   Report:        audit/reconcile_report.json
   Mismatches:    audit/reconcile_mismatches.csv
   HTML report:   audit/reconcile_report.html
```

Exit code: 3.

The mismatches CSV carries the row number, counterparty, ML's category, FinLang's category, the rule name that fired, and the audit reason — the column an auditor reads. See [reconciliation.md](../reconciliation.md) for the full feature explainer.

---

## Limitations (Phase 1 MVP)

- **Positional alignment only.** FinLang output and ML output must have identical row counts; row N in one file corresponds to row N in the other. Key-based alignment (`--reconcile-key date,amount,counterparty`) is Phase 2.
- **Single reconcile field by default.** `--reconcile-fields category` is the canonical use. Multi-field works (`--reconcile-fields category,flags`) but the killer demo focuses on category drift.
- **Strict mode only.** Any mismatch = exit 3. Threshold mode (`--reconcile-threshold 95`) is Phase 2.
- **No standalone mode yet.** `--reconcile` runs alongside the engine. Comparing two pre-existing CSV files without re-running the engine (`--reconcile-only`) is Phase 2.
- **Amount formatting consistency.** Amount strings in `reconcile_report.json`, `reconcile_mismatches.csv`, and `reconcile_report.html` reflect the engine's pandas output verbatim (e.g. `-245000.0` rather than `−£245,000.00`). Consistency normalisation across all three artefacts is queued for v0.7.9.

---

## Files Modified

| File | Change |
|------|--------|
| `src/finlang/cli/run_finlang.py` | `--reconcile`, `--reconcile-fields`, `--reconcile-output-dir`, `--reconcile-html` argparse + validation + post-engine hook |
| `src/finlang/tools/reconcile.py` | **New file** — independent ML validation module |
| `src/finlang/tools/reconcile_html.py` | **New file** — HTML report generator |
| `src/finlang/engine/finlang_engine.py` | No change |
| `docs/cli_reference.md` | Reconcile flags documented; cross-links to reconciliation.md and verify.md |
| `docs/flags.md` | Reconcile flag entries added |
| `docs/workflows.md` | New "Reconciliation Workflow" section; verify cross-link |
| `docs/faq.md` | Reconcile + verify FAQ entries |
| `docs/reconciliation.md` | **New file** — full feature explainer |
| `docs/verify.md` | **New file** — backfilled feature explainer for v0.7.7's `--verify` |
| `README.md` | Headline feature line; documentation links |
| `CHANGELOG.md` | v0.7.8 entry |

---

*See [CHANGELOG.md](../../CHANGELOG.md) for full version history.*
*See [reconciliation.md](../reconciliation.md) and [verify.md](../verify.md) for feature-level documentation.*
