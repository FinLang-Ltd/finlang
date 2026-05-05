# Integrity Verification
> **Applies to:** FinLang v0.7.7+
> **Status:** Production
> **Last verified:** v0.7.8

---

## 1. What it does

FinLang's `--verify` and `--verify-full` flags produce a SHA-256 fingerprint of every transaction's immutable fields — date, amount, counterparty — before and after engine processing, and emit a JSON report plus optional proof CSV showing whether any immutable field was modified, any row was lost, or cross-row contamination occurred. It is the integrity primitive: an evidence artefact that can be presented in an audit, regulatory challenge, or model-risk review to show that the categorisation layer did not silently corrupt the underlying data.

---

## 2. When to use it

**CI/CD pipelines processing financial data.** Add `--verify` to the daily run. Exit code 3 on a fingerprint mismatch fails the pipeline before bad data propagates downstream. Cheap (fast mode is fingerprint-only) and gives a definitive yes/no on integrity.

**Pre-audit evidence preparation.** Run `--verify-full --verify-output-dir audit/` ahead of an audit window. The resulting `verify_proof.csv` shows every row's input fingerprint vs output fingerprint with PASS/FAIL — the evidence artefact a regulator or internal auditor reads to confirm integrity rather than trusting a verbal claim.

**Regression gating after engine changes.** Any FinLang upgrade that touches data parsing or normalisation should pass `--verify-full` against a known-good corpus. Locally, `quick_check.ps1`'s Verify gate exercises this on every code change.

**As a paired check with `--reconcile`.** Verify answers "did FinLang corrupt the input data?" Reconcile answers "does FinLang agree with the ML model's categorisation?" Both can run in the same invocation. Together they form a complete chain: data integrity (`--verify`) → categorisation independence (`--reconcile`) → per-row reasoning (`--audit`).

---

## 3. Worked example — full integrity check with artifacts

A clean run of FinLang against demo data, with full verification and artifact generation:

```bash
finlang \
  --input transactions.csv \
  --rules compliance.fin \
  --output finlang_out.csv \
  --audit audit.json --audit-mode full \
  --verify-full \
  --verify-output-dir verify/
```

Console output on a clean run:

```
Integrity verified: 15 rows, 0 mismatches (full mode, 0.1s)
```

Exit code: 0.

Three artefacts land in `verify/`:

- `verify_report.json` — machine-readable summary (timestamp, mode, rows checked, mismatches, status).
- `verify_proof.csv` — per-row fingerprint comparison: every row's `_fingerprint_in`, `_fingerprint_out`, and `_status` (PASS/FAIL).
- `verify_mismatches.csv` — written **only on failure**. One row per integrity violation with the offending field and the before/after values.

Open `verify_proof.csv`:

| date | amount | counterparty | memo | category | flags | _fingerprint_in | _fingerprint_out | _status |
|---|---|---|---|---|---|---|---|---|
| 2026-01-15 | -245000.00 | SHELL TRADING INTERNATIONAL | Q1 Gas Supply | Energy & Commodities | | a4b2c1... | a4b2c1... | PASS |
| 2026-01-16 | -87500.50 | SHELL UK LTD | Fuel card settlement | Energy & Commodities | | 7e3f9d... | 7e3f9d... | PASS |
| ... | ... | ... | ... | ... | ... | ... | ... | PASS |

Every row PASS, fingerprints identical before vs after the engine ran. The categorisation columns (`category`, `flags`) populated by the engine are present, but the immutable fields they depend on are byte-identical. That's the evidence: FinLang ran its rules without touching the underlying transaction data.

If a fingerprint mismatched, the row would show FAIL and a corresponding entry in `verify_mismatches.csv` would name the offending field with its before/after value.

---

## 4. CLI usage

| Flag | Argument | What it does |
|------|----------|--------------|
| `--verify` | (boolean) | Fast mode: SHA-256 fingerprint comparison on immutable fields (date, amount, counterparty). Lightweight, ~milliseconds for typical data. |
| `--verify-full` | (boolean) | Full mode: fingerprint comparison + field-by-field comparison. Surfaces the specific field and old/new values when a fingerprint mismatch is detected. Slightly heavier; still fast. |
| `--verify-output-dir` | directory path | Where to write verification artifacts (`verify_report.json`, `verify_proof.csv`, and `verify_mismatches.csv` on failure). Requires `--verify` or `--verify-full`. |

`--verify` and `--verify-full` are mutually compatible with all i18n flags: `--decimal`, `--thousands`, `--dayfirst`, `--date-format`, `--encoding`. Verification re-applies the same locale handling so input fingerprints match output fingerprints across regional formats.

`--verify` coexists with `--reconcile`. Both can run in the same invocation; both produce their own artifacts; exit code 3 if either fails.

---

## 5. Output anatomy

### `verify_report.json` (always written when `--verify-output-dir` set)

Machine-readable summary. Contains:

- `timestamp` — UTC ISO 8601 of the verification run
- `input_file`, `output_file` — basenames of the compared files
- `mode` — `"fast"` or `"full"`
- `rows_checked` — number of rows fingerprinted
- `mismatches` — count of integrity violations
- `duration_seconds`
- `status` — `"PASS"` or `"FAIL"`

### `verify_proof.csv` (always written when `--verify-output-dir` set)

Per-row fingerprint evidence. Columns: `date`, `amount`, `counterparty`, `memo`, `category`, `flags`, `_fingerprint_in`, `_fingerprint_out`, `_status`. Every row gets a line, PASS or FAIL — this is the artefact that shows integrity row by row.

### `verify_mismatches.csv` (written when mismatches > 0)

One row per integrity violation. Columns: `csv_row`, `reason` (e.g. "fingerprint mismatch", "field mismatch (amount)"), `fingerprint_in`, `fingerprint_out`, `field_diffs` (the specific field that drifted with old → new values). Read this first when verification fails — it tells you exactly what was modified.

---

## 6. Exit codes

| Code | Meaning |
|------|---------|
| `0` | Engine succeeded AND all post-engine checks passed (verify, reconcile). |
| `1` | Structural error (file not found, permission denied, parse error). |
| `2` | Validation/parsing error (e.g. `--verify-output-dir` without `--verify` or `--verify-full`). |
| `3` | Post-engine check failure — verification mismatch and/or reconciliation mismatch. CI/CD should treat this as "the engine corrupted the data; do not promote this output downstream." |

Exit code 3 was introduced in v0.7.7 alongside `--verify`. It is now shared with `--reconcile` (v0.7.8): if either fails in the same invocation, the run exits with code 3.

---

## 7. Limitations

- **Immutable-fields scope.** The fingerprint covers `date`, `amount`, `counterparty`. Categorisation fields (`category`, `flags`, `memo`) are deliberately excluded — those are what the engine modifies, so they are expected to differ between input and output. If you need to verify that `memo` survived the engine unchanged, the field comparison in `--verify-full` will catch a mutation, but the fingerprint itself does not include it.
- **Row-count mismatch is a hard failure.** If `len(input_rows) != len(output_rows)`, verification fails with a row-count-mismatch reason. This is intentional: the engine should not lose or duplicate rows.
- **Locale dependency.** Verification re-applies the locale flags (`--decimal`, `--thousands`, `--dayfirst`, `--date-format`) to normalise input fingerprints. If you change the locale flags between an engine run and a later verification, fingerprints will not match.
- **No tampering protection on the artefacts themselves.** `verify_report.json` and `verify_proof.csv` are plain files. Cryptographic signing of the artefacts is not in scope — that would be a downstream tooling decision.
- **Performance characterisation pending re-validation.** Vectorisation work (queued as SOL-039) may improve the verify path's throughput; current performance is acceptable for typical data sizes (sub-second for 5K rows; a few seconds at 1M rows).

---

## 8. Roadmap (direction, not promises)

- **Verify vectorisation (SOL-039)** — confirm the current vectorisation path is being used; the observed performance ceiling suggests a scalar fallback in some paths. Removes a visible perf wart; makes demos snappier.
- **Verify progress indicator** — for long-running verification on large fixtures. UX polish for live demos where a spinning cursor reads as "hanging".
- **Cryptographic signing of artefacts** — out of scope for FinLang itself; a downstream tooling decision. Can sign `verify_report.json` + `verify_proof.csv` with any standard tool (cosign, sigstore, GPG) without changes to FinLang.

---

## See also

- [reconciliation.md](reconciliation.md) — `--reconcile` ML validation layer (the related but distinct independent-challenge primitive)
- [cli_reference.md](cli_reference.md) — full flag table for all CLIs
- [flags.md](flags.md) — canonical input formats for every flag
- [workflows.md](workflows.md) — verification in CI/CD and pre-audit workflow patterns
- [faq.md](faq.md) — common questions about `--verify`, exit codes, and integrity behaviour

*The framing line:* Verify shows the engine didn't corrupt the data. Reconcile gives the categorisation an independent challenge. Audit names the rule behind every decision. The three feed the same evidence chain a regulated workflow expects.
