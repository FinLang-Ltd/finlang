# 🛡 Integrity Verification
> **Applies to:** FinLang v0.7.7+
> **Status:** Production
> **Last verified:** v0.8.1

FinLang's `--verify` and `--verify-full` flags produce a SHA-256 fingerprint of every transaction's immutable fields — date, amount, counterparty — before and after engine processing, and emit a JSON report plus optional proof CSV showing whether any immutable field was modified, any row was lost, or cross-row contamination occurred. **It is the integrity primitive**: an evidence artefact that can be presented in an audit, regulatory challenge, or model-risk review to show that the categorisation layer did not silently corrupt the underlying data.

---

## 🎯 Quick Navigation

**I want to…**
- [Understand when verify fits my workflow](#-when-to-use) → Bidirectional When / When NOT
- [See a worked example](#-worked-example-the-clean-run) → Clean run with full artefacts
- [Read the report files](#-output-anatomy) → JSON, proof CSV, mismatches CSV
- [Wire verification into CI/CD](workflows.md#-enterprise-integration--workflows) → Pattern in workflows.md

> **New to FinLang?** Start with [install.md](install.md) and the [Daily Run](workflows.md#-daily-run) workflow. Verification runs on top of an existing FinLang pipeline — it isn't first-touch.

---

## ✅ When to Use

- **CI/CD pipelines processing financial data.** Add `--verify` to the daily run. **Exit code 3 on fingerprint mismatch fails the pipeline before bad data propagates downstream.** Cheap (fast mode is fingerprint-only) and gives a clear pass/fail signal on integrity.
- **Pre-audit evidence preparation.** Run `--verify-full --verify-output-dir audit/` ahead of an audit window. The resulting `verify_proof.csv` shows every row's input fingerprint vs output fingerprint with PASS/FAIL — **the evidence artefact a regulator or internal auditor reads** rather than trusting a verbal claim.
- **Regression gating after engine changes.** Any FinLang upgrade that touches data parsing or normalisation should pass `--verify-full` against a known-good corpus. The Verify gate in `quick_check.ps1` exercises this on every code change.
- **As a paired check with `--reconcile`.** Verify answers "did FinLang corrupt the input data?" Reconcile answers "does FinLang agree with the ML model's categorisation?" Both can run in the same invocation; together they form a complete chain.

## ❌ When NOT to Use

- **Your downstream doesn't care whether immutable fields were touched.** If integrity is not a requirement, the verification overhead is wasted cycles.
- **You changed locale flags between the engine run and a separate verify run.** Verify re-applies the locale flags (`--decimal`, `--thousands`, `--dayfirst`, `--date-format`) to normalise input fingerprints. **If the flags differ, fingerprints will not match** — and the failure won't reflect a real integrity problem.
- **You're trying to verify categorisation fields like `category`, `flags`, or `memo`.** The fingerprint covers immutable fields only by design — the engine modifies categorisation fields, so they will (and should) differ between input and output.
- **You expect verification to detect a rule logic change.** Verify shows whether the engine touched immutable fields. **It does not detect** that a rule produced a different category than the previous run. For categorisation drift, use `--reconcile` against a known-good output.

---

## 🔄 The Verification Flow

```
   ┌─────────────────────┐
   │  Raw transactions   │
   │  (input CSV)        │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  📸 Snapshot A      │   SHA-256 fingerprint of
   │  Immutable fields   │   date + amount + counterparty
   └──────────┬──────────┘   per row
              │
              ▼
   ┌─────────────────────┐
   │  FinLang Engine     │   Applies rules.
   │  Modifies category, │   Immutable fields are NOT touched
   │  flags, memo        │   by design.
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  Output CSV         │
   │  (categorised)      │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  📸 Snapshot B      │   SHA-256 fingerprint of
   │  Immutable fields   │   immutable fields in output
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  --verify           │   A == B  →  PASS (immutable fields intact)
   │  Compare A vs B     │   A != B  →  FAIL (engine corrupted data)
   └──────────┬──────────┘
              │
        ┌─────┴───────┬─────────────┐
        ▼             ▼             ▼
   ┌──────────┐ ┌──────────┐ ┌──────────┐
   │ 📄 JSON  │ │ 📊 proof │ │ 📊 mis-  │
   │ report   │ │ CSV      │ │ matches  │
   │ always   │ │ always   │ │ on FAIL  │
   └──────────┘ └──────────┘ └──────────┘
```

The **snapshot-then-compare pattern** — fingerprint the immutable fields before and after the engine, demand they match — is the load-bearing design. If the engine mutates `date`, `amount`, or `counterparty`, `--verify` is designed to catch it.

---

## 📍 Worked Example: The Clean Run

A FinLang run with full verification and artefact generation:

```bash
finlang \
  --input transactions.csv \
  --rules compliance.fin \
  --output finlang_out.csv \
  --audit audit.json --audit-mode full \
  --verify-full \
  --verify-output-dir verify/
```

### What's Happening

- `--input` and `--rules` — same as a normal FinLang run. The engine applies rules deterministically.
- `--verify-full` — turns on full mode (fingerprint + per-field comparison). Surfaces the specific field that drifted when a fingerprint mismatch is detected, not just "something changed". Slightly heavier than `--verify` (fast mode), still fast.
- `--verify-output-dir verify/` — directory for the verification artefacts. Two files always land there; a third lands on FAIL.

### Console Output (Clean Run)

```
Integrity verified: 15 rows, 0 mismatches (full mode, 0.1s)
```

Exit code: **0**.

### The Proof CSV

`verify/verify_proof.csv` — one row per input row, with the before/after fingerprints and a PASS/FAIL marker.

| date | amount | counterparty | memo | category | flags | _fingerprint_in | _fingerprint_out | _status |
|---|---|---|---|---|---|---|---|---|
| 2026-01-15 | -245000.00 | SHELL TRADING INTERNATIONAL | Q1 Gas Supply | Energy & Commodities | | a4b2c1… | a4b2c1… | PASS |
| 2026-01-16 | -87500.50 | SHELL UK LTD | Fuel card settlement | Energy & Commodities | | 7e3f9d… | 7e3f9d… | PASS |
| … | … | … | … | … | … | … | … | PASS |

Every row PASS, fingerprints identical before vs after the engine ran. **The categorisation columns (`category`, `flags`) are populated by the engine** — those fields are mutable by design — but the immutable fields they were derived from are byte-identical. **That's the evidence**: the engine ran its rules without touching the underlying transaction data.

### What FAIL Looks Like (Conceptual)

If a fingerprint mismatched, the corresponding row in `verify_proof.csv` would show `_status: FAIL` and `verify_mismatches.csv` would name the offending field with old → new values. The console would print one line per mismatch (up to 10) and the run would exit with code **3**. CI/CD treats this as "the engine corrupted the data; do not promote this output downstream."

---

## ⚙️ CLI Usage

| Flag | Argument | What it does |
|------|----------|--------------|
| `--verify` | (boolean) | **Fast mode**: SHA-256 fingerprint comparison on immutable fields (date, amount, counterparty). ~milliseconds for typical data. |
| `--verify-full` | (boolean) | **Full mode**: fingerprint + per-field comparison. Surfaces the specific field that drifted when a fingerprint mismatch is detected. Still fast. |
| `--verify-output-dir` | directory path | Where to write verification artefacts (`verify_report.json`, `verify_proof.csv`, and `verify_mismatches.csv` on failure). Requires `--verify` or `--verify-full`. |

> **⚠️ Fast vs Full mode:** Use `--verify` for CI/CD gating where you only need the yes/no answer. Use `--verify-full` for pre-audit evidence where you need to know *which field* drifted on FAIL. The proof CSV is identical in both modes; only the mismatch detail differs.

> **🌍 Locale flags inherited:** Verification re-applies the locale flags (`--decimal`, `--thousands`, `--dayfirst`, `--date-format`) to normalise input fingerprints. **If you change locale flags between an engine run and a separate verify invocation, fingerprints will not match** — and the failure will look like an integrity problem when it's actually a normalisation drift. Keep flags identical end-to-end.

> **🚧 No standalone mode:** `--verify` runs alongside the engine in the same invocation. There's no flag to verify two pre-existing CSVs without re-running the engine. The engine reads the input, writes the output, and verifies in the same pass.

`--verify` coexists with `--reconcile` — both can run in the same invocation, both produce their own artefacts, exit code 3 if either fails.

---

## 📋 Output Anatomy

When `--verify-output-dir <path>` is set, two artefacts always land in that directory; a third lands on FAIL.

### 📄 `verify_report.json` *(always written)*

Machine-readable summary. Contains:

- `timestamp` — UTC ISO 8601 of the verification run
- `input_file`, `output_file` — basenames of the compared files
- `mode` — `"fast"` or `"full"`
- `rows_checked` — number of rows fingerprinted
- `mismatches` — count of integrity violations
- `duration_seconds`
- `status` — `"PASS"` or `"FAIL"`

### 📊 `verify_proof.csv` *(always written)*

Per-row fingerprint evidence. Columns: `date`, `amount`, `counterparty`, `memo`, `category`, `flags`, `_fingerprint_in`, `_fingerprint_out`, `_status`. **Every row gets a line, PASS or FAIL** — this is the artefact that shows integrity row by row. The CSV stays small even at 5K rows; at 1M rows it's still a single readable file.

### 📊 `verify_mismatches.csv` *(written when mismatches > 0)*

One row per integrity violation. Columns: `csv_row`, `reason` (e.g. "fingerprint mismatch", "field mismatch (amount)", "row count mismatch"), `fingerprint_in`, `fingerprint_out`, `field_diffs` (the specific field that drifted with old → new values). **Read this first when verification fails** — it tells you exactly what was modified.

> **Two-CSV asymmetry note:** Verify produces both `verify_proof.csv` (always — per-row evidence) and `verify_mismatches.csv` (on FAIL — failure detail). This is deliberate: the proof CSV is the always-on evidence artefact for an auditor; the mismatches CSV is the diagnostic for an engineer. Reconcile only produces one mismatches CSV because there is no equivalent "always-on per-row evidence" output for it.

---

## 🚦 Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Engine succeeded AND all post-engine checks passed (verify, reconcile). |
| `1` | Structural error — file not found, permission denied, parse error. |
| `2` | Validation error — e.g. `--verify-output-dir` without `--verify` or `--verify-full`. |
| `3` | Post-engine check failure — verification mismatch and/or reconciliation mismatch. **CI/CD should treat this as "the engine corrupted the data; do not promote this output downstream."** |

Exit code 3 was introduced in v0.7.7 alongside `--verify`. It is FinLang's shared "review-needed" signal: `--verify` and `--reconcile` (v0.7.8) can both run in one invocation — if either fails, the run exits with code 3 — and impact analysis (`--impact-rules`, v0.8.0) uses the same code for behavioural changes (impact runs on its own, being mutually exclusive with verify/reconcile).

---

## 🚧 Limitations

- **Immutable-fields scope.** The fingerprint covers `date`, `amount`, `counterparty`. Categorisation fields (`category`, `flags`, `memo`) are deliberately excluded — the engine modifies those, so they will differ between input and output. If you need to verify that `memo` survived unchanged, the field comparison in `--verify-full` will catch a mutation, but the fingerprint itself does not include it.
- **Row-count mismatch is a hard failure.** If `len(input_rows) != len(output_rows)`, verification fails with a row-count-mismatch reason. Intentional: the engine should not lose or duplicate rows.
- **Locale dependency.** Verification re-applies the locale flags to normalise input fingerprints. Different locale flags between engine and verify produce false negatives. Keep flags identical end-to-end.
- **No tampering protection on the artefacts themselves.** `verify_report.json` and `verify_proof.csv` are plain files. **Cryptographic signing of the artefacts is out of scope** — that's a downstream tooling decision (cosign, sigstore, GPG can sign without changes to FinLang).

---

## ⚡ Performance

Verification is vectorised (SOL-110, July 2026): both CSVs load through a pandas fast path (with automatic fallback to the original reader on unusual CSV structures), and normalisation/fingerprinting run once per *unique* value rather than once per row. On a 500,000-row full-mode measurement, wall-clock dropped from ~570s (scalar implementation) to ~15s on the same hardware — with byte-identical artefacts and field-identical results, held in place by dedicated equivalence tests in the daily gate. Real-world ledgers, where dates and amounts repeat heavily, can see proportionally better times than that deliberately repeat-hostile fixture.

---

## 🛣️ Roadmap (direction, not promises)

- **Verify progress indicator** — for long-running verification on large fixtures. UX polish for live demos where a spinning cursor reads as "hanging".
- **Cryptographic signing of artefacts** — out of scope for FinLang itself; a downstream tooling decision. Can sign `verify_report.json` + `verify_proof.csv` with any standard tool without changes to FinLang.

---

## 📚 Related Documentation

- [reconciliation.md](reconciliation.md) — `--reconcile` ML validation layer (related but distinct independent-challenge primitive)
- [impact.md](impact.md) — `--impact-rules` rule-change impact analysis (comparing two rulepacks, not confirming one run)
- [workflows.md](workflows.md#-enterprise-integration--workflows) — Verification in CI/CD and pre-audit workflow patterns
- [cli_reference.md](cli_reference.md) — full flag table for all CLIs
- [flags.md](flags.md) — canonical input formats for every flag
- [faq.md](faq.md) — common questions about `--verify`, exit codes, and integrity behaviour
- [install.md](install.md) — getting started

*Verify shows the engine didn't corrupt the data. Reconcile gives the categorisation an independent challenge. Audit names the rule behind every decision. The three feed the same evidence chain a regulated workflow expects.*
