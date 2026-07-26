# ⚖️ ML Reconciliation
> **Applies to:** FinLang v0.7.8+
> **Status:** Two alignment modes — positional (default, with optional identity guard via `--reconcile-identity-fields`) and key-based (`--reconcile-key`, with orphan detection). Single-field default; strict mode.
> **Last verified:** v0.8.2

Reconciliation compares FinLang's deterministic categorisation against an external system's output — typically an ML model — and produces a row-by-row report of every mismatch, complete with the rule that fired and the audit reason. **It is not an alternative to ML categorisation. It is an independent challenge layer that bolts onto an existing pipeline through one CLI flag**, producing evidence a compliance review or model-risk-management process can use to identify silent drift in categorisation outputs.

---

## 🎯 Quick Navigation

**I want to…**
- [Understand when reconcile fits my workflow](#-when-to-use) → Bidirectional When / When NOT
- [Walk through a working example](#-worked-example-the-cayman-scenario) → 15-row Cayman demo
- [Try other flag combinations](#-variations) → Minimal, JSON-only, multi-field, verify+reconcile
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
- **Your two CSVs have different row counts and you're in positional mode.** Positional alignment requires identical row counts — a row-count mismatch exits with code 1, not 3 (structural problem, not a categorisation disagreement). Switch to `--reconcile-key date,amount,counterparty`: rows match by content, row counts may differ, and unmatched rows on either side are reported as orphans.
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

Row 4 is the load-bearing line. The ML output silently approved a £250K transfer to an offshore jurisdiction as routine "Treasury Operations". FinLang's rule pack flagged the same row under "Compliance: Offshore Jurisdictions" because the counterparty matched `*CAYMAN*`. **The columns a reviewer may need — `finlang_rule_matched` plus `finlang_audit_reason` — are the deterministic rule-attribution layer FinLang adds alongside the ML output.**

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

**Use case:** the complete evidence chain in one run: verify shows the engine didn't corrupt the data, reconcile gives the categorisation an independent challenge, audit names the rule behind every decision. When a single run produces all three, the artefacts archive together as one auditable bundle. See [verify.md](verify.md) for the verify-side detail.

---

## ⚙️ CLI Usage

| Flag | Argument | What it does |
|------|----------|--------------|
| `--reconcile` | path to ML output CSV | Triggers reconciliation. Requires `--audit` and `--audit-mode full`. |
| `--reconcile-fields` | comma-separated field names | Which fields to compare. Default: `category`. Multi-field works (e.g. `category,flags`). |
| `--reconcile-output-dir` | directory path | Where to write reconciliation artefacts. Required if `--reconcile-html` is set. |
| `--reconcile-html` | (boolean) | Additionally emit a self-contained HTML report. Requires both `--reconcile` and `--reconcile-output-dir`. |
| `--reconcile-identity-fields` | comma-separated field names | Identity guard: verify the named fields match positionally **before** comparing reconcile fields (e.g. `date,amount,counterparty`). Misaligned rows = structural failure (exit 1) with `reconcile_identity_failures.{csv,json}` artefacts; normal mismatch reporting is suppressed. Requires `--reconcile`. Mutually exclusive with `--reconcile-key`. |
| `--reconcile-key` | comma-separated field names | Key-based alignment: match rows by canonicalised composite key (e.g. `date,amount,counterparty`) instead of position. Row counts may differ; unmatched rows are reported as **orphans** (exit 3, `reconcile_orphans_finlang.csv` / `reconcile_orphans_ml.csv`). Duplicate keys on either side = structural failure (exit 1) — no silent first-match. Requires `--reconcile`. Mutually exclusive with `--reconcile-identity-fields`. |
| `--reconcile-date-format` | strftime format (e.g. `%d/%m/%Y`) | States the ML output's date convention explicitly instead of letting reconcile infer it (see *ML date convention* below). Validated against the actual ML dates — an unparseable format is a structural failure (exit 1). Requires an alignment mode (`--reconcile-identity-fields` or `--reconcile-key`); positional field comparison does not parse dates, so the inert combination is rejected (exit 2) rather than silently ignored. |

> **⚠️ Audit-mode requirement:** `--reconcile` rejects with exit code 2 if `--audit` is absent or `--audit-mode` is not `full`. This is a deliberate design point — silent reconciliation without rule attribution is worse than no reconciliation at all.

> **🌍 Locale flags inherited — FinLang side only:** The i18n flags that the engine honours (`--decimal`, `--thousands`, `--dayfirst`, `--date-format`, `--encoding`) describe **your input file**, and reconcile applies them to the FinLang side of the comparison. They are deliberately NOT applied to the ML file: it is a separate system's export and can carry a different date convention entirely (a UK-locale ML system emitting `05/01/2026` against FinLang's ISO `2026-01-05`).

**ML date convention (identity/key alignment).** When `date` is among the alignment fields, reconcile decides how to read the ML side's dates before comparing:

1. **Inferred** — the ML date column is scanned; any value with a component above 12 settles the convention deterministically (e.g. `19/01/2026` can only be day-first). Two values that settle it in *opposite* directions is a structural failure (exit 1) — mixed conventions in one file have no single correct reading.
2. **Explicit** — `--reconcile-date-format` states the convention. The format is validated against every non-empty ML date first; a format that does not parse the data is exit 1, never recorded as applied.
3. **Assumed** — every date in the column is ambiguous (all components ≤ 12), so nothing can settle it. Reconcile proceeds month-first, **warns on stderr**, and records the assumption. If your ML export is day-first, this is the case `--reconcile-date-format '%d/%m/%Y'` exists for.

Whichever path ran, the decision is recorded in `reconcile_report.json` under `ml_date_convention` — the artefact states its own assumption rather than hiding it.

> **⚠️ Critical assumption — row order:** Reconcile compares FinLang row N to ML row N positionally. By itself it does NOT verify that both rows represent the same transaction. If your ML pipeline reorders, batches, or async-processes rows, positional comparison can silently compare unrelated rows and produce nonsense mismatches with confident-looking attribution — or a false-confident perfect match.
>
> Safe ML pipelines: row-by-row sequential, simple pandas, single-threaded processing — these preserve order.
>
> Risky: distributed processing, parallel batching, async/queue-based ML inference, any post-processing that re-sorts.
>
> **Mitigation:** set `--reconcile-identity-fields date,amount,counterparty`. The identity guard checks those fields positionally before any comparison and refuses to report (exit 1, with a row-level failure artefact) when row order has drifted. Or switch to `--reconcile-key` — key-based alignment removes the row-order dependency entirely: rows match by content, so a reordering ML pipeline reconciles cleanly.

**Field canonicalisation contract** (applies to both `--reconcile-identity-fields` comparison and `--reconcile-key` key construction): `amount` values compare numerically after the engine's amount normalisation (`-10.00` matches `-10.0`, CR/DR suffixes and parens handled); `date` values compare after ISO-8601 normalisation; all other fields compare case-insensitively with whitespace trimmed, and *(v0.8.1)* tolerate the CSV formula-injection guard — a leading `'` the engine added at write time (before `=` `+` `-` `@` or tab) is stripped symmetrically on both sides before comparison, so an engine-written FinLang row matches the same transaction in a raw ML file. Raw values — exactly as the files contain them — are what land in the artefacts.

**Choosing a key:** the composite key must be unique per row on both sides. Duplicate keys are a hard error (exit 1) rather than a silent first-match, because first-match alignment quietly degenerates into positional behaviour — the exact failure mode key alignment exists to remove. If `date,amount,counterparty` collides (two identical transactions on the same day), add `memo` or use a transaction-ID column if your data carries one.

> **HTML report in key mode:** orphan detail currently lives in the CLI summary, JSON counts, and the two orphan CSVs. The HTML report renders the field-mismatch table and flips to REVIEW REQUIRED whenever orphans exist; a dedicated orphans section in the HTML is pending visual-contract approval.

`--reconcile` coexists with `--verify` — both can run in the same invocation, both produce their own artefacts, exit code 3 if either fails.

---

## 📋 Output Anatomy

When `--reconcile-output-dir <path>` is set, up to three artefacts land in that directory.

### 📄 `reconcile_report.json` *(always written)*

Machine-readable summary. Contains:

- `timestamp` — UTC ISO 8601 of the reconciliation run
- `finlang_output_file`, `ml_output_file` — basenames of the compared files
- `reconcile_fields` — list of fields compared
- `alignment_mode` — `"positional"` or `"key:<fields>"` (e.g. `"key:date,amount,counterparty"`)
- `orphans_finlang_count`, `orphans_ml_count` — unmatched-row counts (always `0` in positional mode)
- `ml_date_convention` — how the ML side's date convention was decided: `{"mode": "inferred" | "explicit" | "assumed" | "not_applicable", "dayfirst": bool, "ambiguous_values": int, "evidence": ...}`. `evidence` carries the value that settled an inferred convention, or the format string when explicit. `not_applicable` = date was not among the alignment fields (including all positional-mode runs)
- `total_rows`, `matches`, `mismatches`, `match_rate_percent`
- `perfect_match` — boolean (closes any rounding ambiguity around the percent)
- `audit_entries_loaded` — count of audit entries indexed by row. Sentinel: `0` = no audit requested, `-1` = requested but unloadable, `>0` = loaded count
- `duration_seconds`
- `status` — `"PASS"` or `"REVIEW REQUIRED"`

### 📊 `reconcile_mismatches.csv` *(written when mismatches > 0)*

One row per disagreement. Columns: `row_number`, `date`, `amount`, `counterparty`, `differing_fields`, `ml_<field>` and `finlang_<field>` for each reconcile field, `finlang_rule_matched`, `finlang_audit_reason`. **Rows ordered by `row_number`** — positional honesty, no severity-driven reordering.

### 🌐 `reconcile_report.html` *(written when `--reconcile-html` is set)*

Self-contained HTML. Title, status banner (red for REVIEW REQUIRED, green for PASS), mismatch table with rule attribution and audit reason inline, footer with FinLang version and run duration. **No JavaScript, no external resources, opens offline.** Every user-provided string is `html.escape()`-ed before injection — counterparty values containing HTML special characters render as escaped text, never as live HTML.

> **Memo column note:** Memo from the input CSV is carried on the per-row mismatch dict and the HTML report, but **not** in `reconcile_mismatches.csv` (positional-MVP scope). Downstream consumers reading the dict directly get the full context; the CSV stays focused on the reconcile fields and rule attribution.

### 👻 `reconcile_orphans_finlang.csv` / `reconcile_orphans_ml.csv` *(key mode, written when orphans exist)*

One row per unmatched transaction. `reconcile_orphans_finlang.csv` = FinLang rows with no ML counterpart (the ML system dropped or never scored them); `reconcile_orphans_ml.csv` = ML rows FinLang never produced. Columns: `row_number` (position in the row's OWN file), `date`, `amount`, `counterparty`, `memo`, `category`. An unreconciled row is a disagreement by definition — orphans set exit code 3.

### 🛑 `reconcile_identity_failures.csv` / `.json` *(written only on identity-guard failure)*

When `--reconcile-identity-fields` is set and rows misalign, these replace the normal artefacts (which are suppressed — a misaligned comparison cannot be trusted). The CSV carries the full failure set: `row_number`, `differing_identity_fields`, then `finlang_<field>` / `ml_<field>` raw values for every configured identity field. The JSON is a summary (counts, fields, status `IDENTITY MISMATCH`) embedding the first 100 row-level failures (`failures_truncated: true` flags when the CSV holds more).

---

## 🚦 Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Engine succeeded AND all post-engine checks passed (verify, reconcile). |
| `1` | Structural error — file not found, permission denied, parse error, row-count mismatch (positional mode), reconcile/key field absent from one side, missing ML file, **identity-guard failure** (`--reconcile-identity-fields` rows misaligned), **duplicate keys** (`--reconcile-key`, either side). |
| `2` | Validation error — e.g. `--reconcile` without `--audit-mode full`, `--reconcile-html` without `--reconcile-output-dir`, empty `--reconcile-fields`/`--reconcile-identity-fields`/`--reconcile-key`, alignment flags without `--reconcile`, `--reconcile-key` together with `--reconcile-identity-fields`. |
| `3` | Post-engine check failure — verification mismatch, reconciliation mismatch, and/or **orphan rows in key mode** (an unreconciled row is a disagreement by definition). **CI/CD should treat this as "review needed."** Not "the data is broken" (that's exit 1) and not "configuration is wrong" (exit 2). |

---

## 🚧 Limitations

- **Positional mode trusts row order unless told otherwise.** In the default mode, row N must be the same transaction in both files — use `--reconcile-identity-fields` to have FinLang check that assumption, or `--reconcile-key` to drop the assumption entirely (see the row-order callout above).
- **Key mode requires unique composite keys.** Duplicate keys on either side are a hard stop (exit 1) by design. No fuzzy matching, no tolerance, no automatic key inference — the caller declares the key explicitly.
- **HTML orphans section pending.** Key-mode orphan detail lives in CLI/JSON/CSV; the HTML report's dedicated orphans section awaits visual-contract approval.
- **Single reconcile field by default.** Multi-field works (`--reconcile-fields category,flags`) but the killer use case focuses on category drift.
- **Strict mode only.** Any mismatch = exit code 3. No threshold flag yet.
- **No standalone mode.** `--reconcile` runs alongside the FinLang engine. Comparing two pre-existing CSVs without re-running the engine is roadmap territory (`--reconcile-only`).
- **Audit linkage requires `--audit-mode full`.** Lite mode is insufficient — the rule attribution on mismatches needs the full match-condition payload.
- **Amount formatting verbatim.** Amount strings render as the engine emits them (e.g. `-245000.0`); cosmetic normalisation across JSON/CSV/HTML is queued.

---

## ⚡ Scale

Key alignment is an **in-memory hash join** (O(N+M), not pairwise), built for review-slice sizes — comfortably up to the low hundreds of thousands of rows. Both files and the key index live in RAM, so the limit is **your machine's memory, not a fixed row count**: once the two files plus their indexes no longer fit in available RAM, reconcile isn't the tool. On a typical workstation that's around the **low millions of rows** — and it's memory that gives first, not speed, because each row is held as an in-memory object several times its raw size (a ~50 MB CSV can occupy a few hundred MB live, ×2 files plus indexes). Chunked/streaming I/O is deliberately out of scope, and that range isn't yet benchmarked. It's a monthly/quarterly review tool, not a big-data pipeline.

---

## 🛣️ Roadmap (direction, not promises)

Candidates being evaluated:

- **Column mapping** (`--reconcile-map`) — handle ML outputs that name the categorisation field differently (e.g. `classification` instead of `category`).
- **Standalone mode** (`--reconcile-only`) — compare two pre-existing CSV files without re-running the engine. Drops time-to-PoC for a buyer evaluation.
- **Threshold mode** (`--reconcile-threshold N`) — exit 0 if match rate ≥ N%, exit 3 below. Strict-by-default remains the canonical mode.
- **`reconcile_proof.csv`** — full row-by-row comparison (matches and mismatches), not just disagreements.

---

## 📚 Related Documentation

- [verify.md](verify.md) — `--verify` and `--verify-full` integrity verification (related but distinct primitive)
- [impact.md](impact.md) — `--impact-rules`: comparing two **rulepacks** (your rule change) rather than two systems? That's impact analysis, not reconcile.
- [workflows.md](workflows.md#-reconciliation-workflow) — CI/CD integration pattern, three-step workflow, exit-code policy
- [cli_reference.md](cli_reference.md) — full flag table for all CLIs
- [flags.md](flags.md) — canonical input formats for every flag
- [faq.md](faq.md) — common questions about `--reconcile`, exit codes, ML pipeline integration
- [install.md](install.md) — getting started

*FinLang does not replace your ML model. It challenges it. Use it alongside, not instead of.*
