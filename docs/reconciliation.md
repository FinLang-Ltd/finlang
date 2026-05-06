# ⚖️ ML Reconciliation
> **Applies to:** FinLang v0.7.8+
> **Status:** Phase 1 MVP (positional alignment, single-field default, strict mode)
> **Last verified:** v0.7.8

Reconciliation compares FinLang's deterministic categorisation against an external system's output — typically an ML model — and produces a row-by-row report of every mismatch, complete with the rule that fired and the audit reason. **It is not an alternative to ML categorisation. It is an independent challenge layer that bolts onto an existing pipeline through one CLI flag**, producing evidence a compliance review or model-risk-management process can use to identify silent drift in categorisation outputs.

---

## 🎯 Quick Navigation

**I want to…**
- [Understand when reconcile fits my workflow](#-when-to-use) → Bidirectional When / When NOT
- [Walk through a working example](#-worked-example-the-cayman-scenario) → 15-row Cayman demo
- [Read the report artefacts](#-output-anatomy) → JSON, CSV, HTML breakdown
- [Wire reconciliation into CI/CD](workflows.md#-reconciliation-workflow) → Pattern in workflows.md

> **New to FinLang?** Start with [install.md](install.md) and the [Daily Run](workflows.md#-daily-run) workflow. Reconciliation runs on top of a working FinLang pipeline — it isn't first-touch.

---

## ✅ When to Use

- **Validating ML categorisation outputs in regulated workflows.** Run FinLang against the same raw data your ML pipeline processes; reconcile the two outputs row by row. Every disagreement is flagged, the FinLang rule is named, the audit reason is attached. Your ML pipeline keeps running as-is.
- **Surfacing model drift between training cycles.** Reconcile a representative slice each month against a stable rule set. **Mismatch rate trending up is an independent signal** — separate from anything the ML system reports about itself.
- **Pre-audit evidence preparation.** Produce row-level CSV plus a self-contained HTML report for compliance review. Both archive cleanly.
- **Where governance expects an independent challenge to AI outputs.** SR 11-7 / model-risk-management challenger workflows in regulated finance. A deterministic rule engine is one option; `--reconcile` produces the disagreement evidence; the human decides what to do.
- **As a CI/CD gate.** See [workflows.md § Reconciliation Workflow](workflows.md#-reconciliation-workflow) for the integration pattern — the gate exists there, not duplicated here.

## ❌ When NOT to Use

- **Your ML pipeline is the only categorisation system AND no governance expects independent challenge.** Use either FinLang OR the ML model directly; reconciliation adds friction without value.
- **You can't enable `--audit --audit-mode full`.** Reconcile refuses to run without it. The whole point is rule-attributed mismatches; without audit linkage there's no rule names on the disagreements.
- **Your two CSVs have different row counts.** Phase 1 MVP requires identical row counts (positional alignment). Row-count mismatch exits with code 1, not 3 — that's a structural problem, not a categorisation disagreement. Key-based alignment lands in Phase 2.
- **You want a "score" of which side is right.** Reconcile reports disagreements; it does not score them or judge. A human reads the mismatches CSV and decides.

---

## 🔄 The Reconciliation Flow

```
   ┌─────────────────────┐         ┌─────────────────────┐
   │  Raw transactions   │ ←same → │  Same raw data      │
   │  (your bank CSV)    │  data   │                     │
   └──────────┬──────────┘         └──────────┬──────────┘
              │                               │
              ▼                               ▼
   ┌─────────────────────┐         ┌─────────────────────┐
   │  ML Pipeline        │         │  FinLang Engine     │
   │  External output.   │         │  Deterministic.     │
   │  Audit varies.      │         │  Rule + audit.json. │
   └──────────┬──────────┘         └──────────┬──────────┘
              │                               │
              ▼                               ▼
   ┌─────────────────────┐         ┌─────────────────────┐
   │  ml_output.csv      │         │  finlang_out.csv    │
   │                     │         │  + audit.json       │
   └──────────┬──────────┘         └──────────┬──────────┘
              │                               │
              └───────────────┬───────────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │  --reconcile        │
                   │  row-by-row,        │
                   │  field comparison   │
                   └──────────┬──────────┘
                              │
                ┌─────────────┼─────────────┐
                ▼             ▼             ▼
          ┌──────────┐  ┌──────────┐  ┌──────────┐
          │ 📄 JSON  │  │ 📊 CSV   │  │ 🌐 HTML  │
          │ report   │  │ mismatch │  │ report   │
          └──────────┘  └──────────┘  └──────────┘
```

The **two-pipeline pattern** — ML on one side, FinLang on the other, fed the same raw data — is the load-bearing design. Reconciliation is the join.

---

## 📍 Worked Example: The Cayman Scenario

The bundled demo is a 15-row corporate treasury input plus a purpose-built rule pack and two ML-output variants — one **clean** (perfect match) and one with **two deliberate mismatches** (drift). Row 4 is `CAYMAN ISLANDS TRUST` for −£250,000.

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

### What's Happening

- `--input` and `--rules` — same as a normal FinLang run. The engine categorises every row deterministically.
- `--audit audit.json --audit-mode full` — required by `--reconcile`. The audit log carries the rule name and match condition for every row, which is what gets attached to mismatches.
- `--reconcile <ml_output.csv>` — triggers the post-engine comparison phase. The ML CSV is read, aligned row-by-row with FinLang's output, every reconcile field is compared.
- `--reconcile-output-dir audit/` — directory for the report artefacts. Three files land there.
- `--reconcile-html` — additionally emits a self-contained HTML report (compliance-context asset; opens offline, no JavaScript).

### Console Output

```
Reconciliation: 2 mismatches in 15 rows (match rate 86.67%)
   Row 1: differs on [category] — SHELL TRADING INTERNATIONAL
   Row 4: differs on [category] — CAYMAN ISLANDS TRUST
```

Exit code: **3** (post-engine check failed; data is fine but the categorisations disagree).

### The Mismatches CSV

| row_number | counterparty | ml_category | finlang_category | finlang_rule_matched | finlang_audit_reason |
|---|---|---|---|---|---|
| 1 | SHELL TRADING INTERNATIONAL | Utilities | Energy & Commodities | Energy: Shell | counterparty ~ "*SHELL*" |
| 4 | CAYMAN ISLANDS TRUST | Treasury Operations | Compliance: Offshore Jurisdictions | Compliance: Offshore Jurisdictions | counterparty ~ "*CAYMAN*" |

Row 4 is the load-bearing line. The ML output silently approved a £250K transfer to an offshore jurisdiction as routine "Treasury Operations". FinLang's rule pack flagged the same row under "Compliance: Offshore Jurisdictions" because the counterparty matched `*CAYMAN*`. **The column a reviewer needs — `finlang_rule_matched` plus `finlang_audit_reason` — is the deterministic rule-attribution layer FinLang adds alongside the ML output.**

Open `audit/reconcile_report.html` in any browser for the same content rendered as a self-contained compliance-context report.

---

## 🎛️ Variations

The Worked Example above shows the maximalist case — every reconcile flag set, every artefact emitted. Most workflows use a subset. Four common shapes follow.

### Minimal — console only, no artefacts

```bash
finlang \
  --input transactions.csv \
  --rules rules.fin \
  --output finlang_out.csv \
  --audit audit.json --audit-mode full \
  --reconcile ml_output.csv
```

**`--reconcile-output-dir` defaults to none.** With no output directory set, the reconcile module writes nothing to disk — no JSON, no CSV, no HTML. The reconciliation still runs: console output prints up to 10 mismatches plus a summary line, and the exit code is **3** if any disagreement is found.

> **⚠️ The trap to know about:** running `--reconcile <ml.csv>` without `--reconcile-output-dir` is a **deliberate** mode, not a misuse. A new user can hunt for a file that was never written; that file was never going to be written, by design. Use this shape when the exit code is the signal you want and disk artefacts are noise.

**Use case:** CI/CD gates. The pipeline reads exit code 3 as "review needed" and short-circuits the merge. No disk I/O, no artefact cleanup, no archive bloat.

### JSON + CSV — no HTML

```bash
finlang \
  --input transactions.csv \
  --rules rules.fin \
  --output finlang_out.csv \
  --audit audit.json --audit-mode full \
  --reconcile ml_output.csv \
  --reconcile-output-dir audit/
```

Adds `--reconcile-output-dir`; omits `--reconcile-html`. `reconcile_report.json` lands in `audit/` always. `reconcile_mismatches.csv` lands when `mismatches > 0`. No HTML report is emitted.

**Use case:** programmatic consumption. Downstream tooling parses the JSON for monitoring or alerting; compliance teams archive the CSV for the audit trail. Drop the HTML when no human needs the visual report.

### Multi-field — compare more than `category`

```bash
finlang \
  --input transactions.csv \
  --rules rules.fin \
  --output finlang_out.csv \
  --audit audit.json --audit-mode full \
  --reconcile ml_output.csv \
  --reconcile-output-dir audit/ \
  --reconcile-fields category,flags
```

`--reconcile-fields category,flags` compares **both** fields row-by-row. A row is a mismatch if **either** field disagrees. The `differing_fields` column in `reconcile_mismatches.csv` tells you which one(s) drifted on each row.

**Use case:** when categorisation drift on one axis (category) and tag/flag drift on another (flags) both matter. Common in pipelines that emit both a classification AND a compliance flag, where either disagreement is independently actionable.

### Verify + reconcile in one invocation

```bash
finlang \
  --input transactions.csv \
  --rules rules.fin \
  --output finlang_out.csv \
  --audit audit.json --audit-mode full \
  --verify-full --verify-output-dir verify/ \
  --reconcile ml_output.csv \
  --reconcile-output-dir audit/ \
  --reconcile-html
```

Both post-engine checks run independently. Verify writes its artefacts to `verify/`; reconcile writes its own to `audit/`. **Exit code 3 if either fails** — the engine treats this as the union, not the intersection.

**Use case:** the complete evidence chain in one run. Data integrity (verify), categorisation independence (reconcile), per-row reasoning (audit). When a single run produces all three, the artefacts archive together as one auditable bundle. See [verify.md](verify.md) for the verify-side detail.

---

## ⚙️ CLI Usage

| Flag | Argument | What it does |
|------|----------|--------------|
| `--reconcile` | path to ML output CSV | Triggers reconciliation. Requires `--audit` and `--audit-mode full`. |
| `--reconcile-fields` | comma-separated field names | Which fields to compare. Default: `category`. Multi-field works (e.g. `category,flags`). |
| `--reconcile-output-dir` | directory path | Where to write reconciliation artefacts. Required if `--reconcile-html` is set. |
| `--reconcile-html` | (boolean) | Additionally emit a self-contained HTML report. Requires both `--reconcile` and `--reconcile-output-dir`. |

> **⚠️ Audit-mode requirement:** `--reconcile` rejects with exit code 2 if `--audit` is absent or `--audit-mode` is not `full`. This is a deliberate design point — silent reconciliation without rule attribution is worse than no reconciliation at all.

> **🌍 Locale flags inherited:** The same i18n flags that the engine honours (`--decimal`, `--thousands`, `--dayfirst`, `--date-format`, `--encoding`) apply during reconciliation. If your data uses European formats, the reconcile output picks up the same locale handling automatically.

> **🚧 Phase 1 limitation — positional alignment:** FinLang output and ML output must have identical row counts. Row N in one file corresponds to row N in the other. Row-count mismatch exits with code 1 (structural error). Key-based alignment via `--reconcile-key date,amount,counterparty` lands in Phase 2.

`--reconcile` coexists with `--verify` — both can run in the same invocation, both produce their own artefacts, exit code 3 if either fails.

---

## 📋 Output Anatomy

When `--reconcile-output-dir <path>` is set, up to three artefacts land in that directory.

### 📄 `reconcile_report.json` *(always written)*

Machine-readable summary. Contains:

- `timestamp` — UTC ISO 8601 of the reconciliation run
- `finlang_output_file`, `ml_output_file` — basenames of the compared files
- `reconcile_fields` — list of fields compared
- `alignment_mode` — `"positional"` in Phase 1
- `total_rows`, `matches`, `mismatches`, `match_rate_percent`
- `perfect_match` — boolean (closes any rounding ambiguity around the percent)
- `audit_entries_loaded` — count of audit entries indexed by row. Sentinel: `0` = no audit requested, `-1` = requested but unloadable, `>0` = loaded count
- `duration_seconds`
- `status` — `"PASS"` or `"REVIEW REQUIRED"`

### 📊 `reconcile_mismatches.csv` *(written when mismatches > 0)*

One row per disagreement. Columns: `row_number`, `date`, `amount`, `counterparty`, `differing_fields`, `ml_<field>` and `finlang_<field>` for each reconcile field, `finlang_rule_matched`, `finlang_audit_reason`. **Rows ordered by `row_number`** — positional honesty, no severity-driven reordering.

### 🌐 `reconcile_report.html` *(written when `--reconcile-html` is set)*

Self-contained HTML. Title, status banner (red for REVIEW REQUIRED, green for PASS), mismatch table with rule attribution and audit reason inline, footer with FinLang version and run duration. **No JavaScript, no external resources, opens offline.** Every user-provided string is `html.escape()`-ed before injection — counterparty values containing HTML special characters render as escaped text, never as live HTML.

> **Memo column note:** Memo from the input CSV is carried on the per-row mismatch dict and the HTML report, but **not** in `reconcile_mismatches.csv` (Phase 1 scope). Downstream consumers reading the dict directly get the full context; the CSV stays focused on the reconcile fields and rule attribution.

---

## 🚦 Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Engine succeeded AND all post-engine checks passed (verify, reconcile). |
| `1` | Structural error — file not found, permission denied, parse error, row-count mismatch between FinLang and ML output, reconcile field absent from one side, missing ML file. |
| `2` | Validation error — e.g. `--reconcile` without `--audit-mode full`, `--reconcile-html` without `--reconcile-output-dir`, empty `--reconcile-fields`. |
| `3` | Post-engine check failure — verification mismatch and/or reconciliation mismatch. **CI/CD should treat this as "review needed."** Not "the data is broken" (that's exit 1) and not "configuration is wrong" (exit 2). |

---

## 🚧 Limitations (Phase 1 MVP)

- **Positional alignment only.** Identical row counts required. Phase 2 brings key-based alignment.
- **Single reconcile field by default.** Multi-field works (`--reconcile-fields category,flags`) but the killer use case focuses on category drift.
- **Strict mode only.** Any mismatch = exit code 3. No threshold flag in Phase 1.
- **No standalone mode.** `--reconcile` runs alongside the FinLang engine. Comparing two pre-existing CSVs without re-running the engine is Phase 2 territory.
- **Audit linkage requires `--audit-mode full`.** Lite mode is insufficient — the rule attribution on mismatches needs the full match-condition payload.
- **Amount formatting verbatim.** Amount strings render as the engine emits them (e.g. `-245000.0`); cosmetic normalisation across JSON/CSV/HTML is queued for v0.7.9.

---

## 🛣️ Roadmap (direction, not promises)

Phase 2 candidates being evaluated:

- **Key-based alignment** (`--reconcile-key date,amount,counterparty`) — match rows by key fields rather than position. Hash join, O(N) not O(N²). Useful when the two pipelines emit rows in different orders.
- **Column mapping** (`--reconcile-map`) — handle ML outputs that name the categorisation field differently (e.g. `classification` instead of `category`).
- **Standalone mode** (`--reconcile-only`) — compare two pre-existing CSV files without re-running the engine. Drops time-to-PoC for a buyer evaluation.
- **Threshold mode** (`--reconcile-threshold N`) — exit 0 if match rate ≥ N%, exit 3 below. Strict-by-default remains the canonical mode.
- **`reconcile_proof.csv`** — full row-by-row comparison (matches and mismatches), not just disagreements.

---

## 📚 Related Documentation

- [verify.md](verify.md) — `--verify` and `--verify-full` integrity verification (related but distinct primitive)
- [workflows.md](workflows.md#-reconciliation-workflow) — CI/CD integration pattern, three-step workflow, exit-code policy
- [cli_reference.md](cli_reference.md) — full flag table for all CLIs
- [flags.md](flags.md) — canonical input formats for every flag
- [faq.md](faq.md) — common questions about `--reconcile`, exit codes, ML pipeline integration
- [install.md](install.md) — getting started

*FinLang does not replace your ML model. It challenges it. Use it alongside, not instead of.*
