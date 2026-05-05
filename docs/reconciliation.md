# Reconciliation
> **Applies to:** FinLang v0.7.8+
> **Status:** Phase 1 MVP (positional alignment, single-field default, strict mode)
> **Last verified:** v0.7.8

---

## 1. What it does

Reconciliation compares FinLang's deterministic categorisation against an external system's output — typically an ML model — and produces a row-by-row report of every mismatch, complete with the rule that fired and the audit reason. It is not an alternative to ML categorisation. It is an independent challenge layer that bolts onto an existing pipeline through one CLI flag, producing evidence a compliance review or model-risk-management process can use to identify silent drift in categorisation outputs.

---

## 2. When to use it

**Validating ML categorisation outputs in regulated workflows.** Run FinLang against the same raw data your ML pipeline processes. Reconcile the two outputs row by row. Every disagreement is flagged, the FinLang rule is named, and the audit reason is attached. The institution keeps its ML pipeline as-is.

**Surfacing model drift between training cycles.** Run reconciliation on a representative slice each month. Mismatch rate trending up against a stable rule set is a signal — independent of any metric the ML system reports about itself.

**Pre-audit evidence preparation.** Before a regulator or internal audit asks "why did the model categorise this transaction as X?", run reconciliation and have the answer in a row-level CSV plus a self-contained HTML report. Both artefacts archive cleanly and reference the rule name and match condition that drove FinLang's answer.

**SR 11-7 / model-risk-management challenger workflows.** Where governance expects an independent challenge to ML outputs, a deterministic rule engine is one option. FinLang's `--reconcile` produces the disagreement evidence; what to do about it remains a human decision.

---

## 3. Worked example — the Cayman scenario

The bundled demo data ([`examples/reconcile/`](../examples/reconcile/) in the FinLang repository) includes a 15-row corporate treasury input ([`demo_reconcile_input.csv`](../examples/reconcile/demo_reconcile_input.csv)), a purpose-built rule pack ([`demo_reconcile_rules.fin`](../examples/reconcile/demo_reconcile_rules.fin)), and two ML-output variants — one perfect-match clean path ([`demo_reconcile_ml_clean.csv`](../examples/reconcile/demo_reconcile_ml_clean.csv)) and one with two deliberate mismatches drift path ([`demo_reconcile_ml_mismatches.csv`](../examples/reconcile/demo_reconcile_ml_mismatches.csv)). Row 4 is `CAYMAN ISLANDS TRUST` for −£250,000.

The demo data lives in the public repository, not in the pip-installed wheel. Clone the repository or download a release tarball to follow this example locally.

Run the drift path with full reconciliation:

```bash
finlang \
  --input examples/reconcile/demo_reconcile_input.csv \
  --rules examples/reconcile/demo_reconcile_rules.fin \
  --output finlang_out.csv \
  --audit audit.json --audit-mode full \
  --reconcile examples/reconcile/demo_reconcile_ml_mismatches.csv \
  --reconcile-output-dir audit/ \
  --reconcile-html
```

Console output:

```
Reconciliation: 2 mismatches in 15 rows (match rate 86.67%)
   Row 1: differs on [category] — SHELL TRADING INTERNATIONAL
   Row 4: differs on [category] — CAYMAN ISLANDS TRUST
```

Exit code: 3.

Open `audit/reconcile_mismatches.csv`:

| row_number | counterparty | ml_category | finlang_category | finlang_rule_matched | finlang_audit_reason |
|---|---|---|---|---|---|
| 1 | SHELL TRADING INTERNATIONAL | Utilities | Energy & Commodities | Energy: Shell | counterparty ~ "*SHELL*" |
| 4 | CAYMAN ISLANDS TRUST | Treasury Operations | Compliance: Offshore Jurisdictions | Compliance: Offshore Jurisdictions | counterparty ~ "*CAYMAN*" |

Row 4 is the killer. The ML output silently approved a £250K transfer to an offshore jurisdiction as routine "Treasury Operations". FinLang's rule pack flagged the same row under "Compliance: Offshore Jurisdictions" because the counterparty matched `*CAYMAN*`. The CSV column an auditor reads is the one the ML model cannot produce: `finlang_rule_matched` plus `finlang_audit_reason`.

Open `audit/reconcile_report.html` in any browser for the same content rendered as a self-contained compliance-context report — opens offline, no JavaScript, no external resources, archives as a single file.

---

## 4. CLI usage

| Flag | Argument | What it does |
|------|----------|--------------|
| `--reconcile` | path to ML output CSV | Triggers reconciliation. Requires `--audit` and `--audit-mode full`. |
| `--reconcile-fields` | comma-separated field names | Which fields to compare. Default: `category`. Multi-field works (e.g. `category,flags`). |
| `--reconcile-output-dir` | directory path | Where to write reconciliation artifacts. Required if `--reconcile-html` is set. |
| `--reconcile-html` | (boolean) | Additionally emit a self-contained HTML report. Requires both `--reconcile` and `--reconcile-output-dir`. |

`--reconcile` coexists with `--verify`. Both can run in the same invocation; both report independently. If either fails, the run exits with code 3.

---

## 5. Output anatomy

When `--reconcile-output-dir <path>` is set, three artefacts can land in that directory:

### `reconcile_report.json` (always written)

Machine-readable summary. Contains:

- `timestamp` — UTC ISO 8601 of the reconciliation run
- `finlang_output_file`, `ml_output_file` — basenames of the compared files
- `reconcile_fields` — list of fields compared
- `alignment_mode` — `"positional"` in Phase 1
- `total_rows`, `matches`, `mismatches`, `match_rate_percent`
- `perfect_match` — boolean (closes any rounding ambiguity in `match_rate_percent`)
- `audit_entries_loaded` — count of audit entries indexed by row (sentinel: `0` = no audit requested, `-1` = requested but unloadable, `>0` = loaded count)
- `duration_seconds`
- `status` — `"PASS"` or `"REVIEW REQUIRED"`

### `reconcile_mismatches.csv` (written when mismatches > 0)

One row per disagreement. Columns: `row_number`, `date`, `amount`, `counterparty`, `differing_fields`, `ml_<field>` and `finlang_<field>` for each reconcile field, `finlang_rule_matched`, `finlang_audit_reason`. Rows ordered by `row_number` (positional honesty — no severity-driven reordering).

### `reconcile_report.html` (written when `--reconcile-html` is set)

Self-contained HTML. Title, status banner (red for REVIEW REQUIRED, green for PASS), mismatch table with rule attribution and audit reason inline, footer with FinLang version and run duration. No JavaScript, no external resources, opens offline. Every user-provided string is `html.escape()`-ed before injection — counterparty values containing HTML special characters render as escaped text, not as live HTML.

---

## 6. Exit codes

| Code | Meaning |
|------|---------|
| `0` | Engine succeeded AND all post-engine checks passed (verify, reconcile). |
| `1` | Structural error (file not found, permission denied, parse error, row-count mismatch between FinLang and ML output, reconcile field absent from one side, missing ML file). |
| `2` | Validation/parsing error (e.g. `--reconcile` without `--audit-mode full`, `--reconcile-html` without `--reconcile-output-dir`, empty `--reconcile-fields`). |
| `3` | Post-engine check failure — verification mismatch and/or reconciliation mismatch. CI/CD should treat this as "the data is fine but the categorisations disagree; review needed." |

---

## 7. Limitations (Phase 1 MVP)

- **Positional alignment only.** FinLang output and ML output must have identical row counts; row N in one file corresponds to row N in the other. Row-count mismatch exits with code 1, not code 3 — this is a structural problem, not a categorisation disagreement.
- **Single reconcile field by default.** Multi-field comparison works (`--reconcile-fields category,flags`) but the killer use case focuses on category drift.
- **Strict mode only.** Any mismatch results in exit code 3. There is no threshold flag in Phase 1.
- **No standalone mode.** `--reconcile` runs alongside the FinLang engine. Comparing two pre-existing CSV files without re-running the engine is Phase 2 territory.
- **Audit linkage requires full mode.** `--reconcile` refuses to run without `--audit --audit-mode full`. This is a deliberate design point: silent reconciliation without rule attribution is worse than no reconciliation at all.
- **Amount formatting.** Amount strings render verbatim from the engine's output (e.g. `-245000.0` rather than `−£245,000.00`). Consistency normalisation across the JSON, CSV, and HTML artefacts is queued for v0.7.9.

---

## 8. Roadmap (direction, not promises)

Phase 2 candidates being evaluated:

- **Key-based alignment** (`--reconcile-key date,amount,counterparty`) — match rows by key fields rather than position. Hash join, O(N) not O(N²). Useful when the two pipelines emit rows in different orders.
- **Column mapping** (`--reconcile-map`) — handle ML outputs that name the categorisation field differently (e.g. `classification` instead of `category`).
- **Standalone mode** (`--reconcile-only`) — compare two pre-existing CSV files without re-running the engine. Drops time-to-PoC for a buyer evaluation.
- **Threshold mode** (`--reconcile-threshold N`) — exit 0 if match rate ≥ N%, exit 3 below. Strict-by-default remains the canonical mode.
- **`reconcile_proof.csv`** — full row-by-row comparison (matches and mismatches), not just disagreements.

---

## See also

- [verify.md](verify.md) — `--verify` and `--verify-full` integrity verification (the related but distinct integrity primitive)
- [cli_reference.md](cli_reference.md) — full flag table for all CLIs
- [flags.md](flags.md) — canonical input formats for every flag
- [workflows.md](workflows.md) — end-to-end workflow patterns including reconciliation as part of CI/CD or audit prep
- [faq.md](faq.md) — common questions about `--reconcile`, exit codes, and ML pipeline integration

*The framing line:* FinLang does not replace your ML model. It validates it. Use it alongside, not instead of.
