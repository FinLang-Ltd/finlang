# 📖 FinLang CLI Reference

> **Applies to:** FinLang v0.7+  
> **Status:** Active  
> **Last verified:** v0.8.3

## 0) Quick Navigation
- [1) `finlang` — Main CLI](#1-finlang--main-cli)
- [2) `finlang-discover` — Discovery Tool](#2-finlang-discover--discovery-tool)
- [3) `finlang-suggest` — Rule Generation](#3-finlang-suggest--rule-generation)
- [Rule Packs Quick Reference](#rule-packs-quick-reference)
- [4) Environment Variables](#4-environment-variables)
- [5) Quick Reference Table](#5-quick-reference-table)
- [6) Practical Recipes](#6-practical-recipes)
- [7) FAQ](#7-faq)
- [⚠️ Known Issues (Active)](#️-known-issues-active)
- [Related Documentation](#related-documentation)

---

## 1) `finlang` — Main CLI

### Purpose
Apply your rules (and optional rule packs) to a CSV of transactions to produce a categorized, normalized output with an optional audit trail.

### Mapping & Canonicalization (Fields after header mapping)
FinLang expects the following **canonical columns** after mapping/synthesis. Your source CSV headers are normalized via `--map` (or the built-in map) into these canonical names:

- `date` — Transaction date (ISO recommended)
- `amount` — Signed numeric amount (synthesized from debit/credit if needed)
- `counterparty` — Merchant / payee / descriptor
- `memo` — Optional free text / description
- `category` — Optional existing category (rules may override)
- `status` — Optional: workflow / transaction state
- `flags` — Internal list field (append-only via `flags +=`)
- `exclude` — Boolean marker for downstream filtering (rule-driven, mutable, auditable; rows are flagged, not dropped)

> **Required after mapping/synthesis:** `date`, `amount`, `counterparty`. If missing, FinLang exits with a fatal error.

> **Rule precedence:** **Last matching rule wins** for each transaction (by design for deterministic overrides).

### Flags

| Flag                     | Description                                                  |
| ------------------------ | ------------------------------------------------------------ |
| `--input PATH`           | Input CSV file to process.                                   |
| `--output PATH`          | Output CSV after rule processing. (Must be writeable).       |
| `--rules PATH`           | Your primary `.fin` rules file.                              |
| `--include-pack LIST`    | Comma-separated built-in packs to include (e.g., `retail,sanity`). See [Rule Packs](#rule-packs-quick-reference). |
| `--map PATH`             | Custom header mapping JSON (replaces bundled map; no merge). |
| `--audit PATH`           | Write audit JSON (diff of changed cells).                    |
| `--audit-mode MODE`      | Verbosity: `none` (fastest), `lite` (default — logs changed fields only), or `full` (includes match conditions and set actions). |
| `--fastio`               | Use PyArrow for IO (20–40% faster).                          |
| `--headless`             | Suppress non-essential console output.                       |
| `--strict-parse`         | Fail fast on malformed CSV / schema issues.                  |
| `--decimal CH`           | Decimal separator for numbers (e.g., `,`).                   |
| `--thousands CH`         | Thousands/grouping separator (e.g., `.`, space, NBSP `\u00A0`, thin NBSP `\u202F`). |
| `--dayfirst`             | Parse dates as `DD/MM/...` instead of `MM/DD/...`.           |
| `--encoding NAME`        | Input file encoding (e.g., `utf-8`, `latin-1`, or `auto`).   |
| `--date-format STR`      | Explicit strptime format for dates (e.g., `%Y-%m-%d`).       |
| `--output-encoding NAME` | Output encoding (default UTF-8).                             |
| `--timings`              | Print basic step timings to STDERR.                          |
| `--fail-threshold F`     | Abort if drop-rate > `F` (fraction `0.0–1.0`).               |
| `--verify`               | Fast SHA-256 integrity verification after engine run. See [verify.md](verify.md). |
| `--verify-full`          | Full verification (fingerprint + field-by-field comparison). See [verify.md](verify.md). |
| `--verify-output-dir DIR`| Write verification artifacts (JSON report + proof CSV) to DIR. |
| `--reconcile PATH`       | Path to ML output CSV. Compares FinLang's deterministic output against an external (typically ML) categorisation; produces a row-by-row mismatch report with rule attribution. Requires `--audit` and `--audit-mode full`. See [reconciliation.md](reconciliation.md). |
| `--reconcile-fields LIST`| Comma-separated fields to compare. Default: `category`. |
| `--verify-html`          | Additionally emit a self-contained HTML integrity report (`verify_report.html`). Requires `--verify` or `--verify-full` AND `--verify-output-dir`. See [verify.md](verify.md). |
| `--reconcile-output-dir DIR` | Directory for reconciliation artefacts (`reconcile_report.json`, `reconcile_mismatches.csv`). Required when `--reconcile-html` is set. |
| `--reconcile-html`       | Additionally emit a self-contained HTML report (`reconcile_report.html`). Requires `--reconcile` AND `--reconcile-output-dir`. See [reconciliation.md](reconciliation.md). |
| `--reconcile-identity-fields LIST` | Identity guard: comma-separated fields verified positionally BEFORE comparison (e.g. `date,amount,counterparty`). Misaligned rows = exit 1 with `reconcile_identity_failures.{csv,json}`; mismatch reporting suppressed. Requires `--reconcile`. Mutually exclusive with `--reconcile-key`. See [reconciliation.md](reconciliation.md). |
| `--reconcile-key LIST` | Key-based alignment: comma-separated fields forming a composite key (e.g. `date,amount,counterparty`). Replaces positional alignment — row counts may differ; unmatched rows reported as orphans (exit 3, `reconcile_orphans_*.csv`); duplicate keys = exit 1. Requires `--reconcile`. Mutually exclusive with `--reconcile-identity-fields`. See [reconciliation.md](reconciliation.md). |
| `--reconcile-date-format FMT` | Explicit strftime format for the ML output's dates (e.g. `%d/%m/%Y`) — the ML file is another system's export and can use a different convention from `--input`. Omitted: reconcile infers the convention from the ML date column. Validated against the actual data (unparseable format = exit 1); requires an alignment mode (`--reconcile-identity-fields` or `--reconcile-key`), since positional field comparison does not parse dates (exit 2 otherwise). Decision recorded in `reconcile_report.json` as `ml_date_convention`. See [reconciliation.md](reconciliation.md). |
| `--impact-rules PATH`    | Impact analysis: run the input through both `--rules` (baseline) and this candidate `.fin` pack; report rows re-categorised, indicative amount moved per transition, per-rule match deltas. Exit 3 on behavioural change (CI-gateable). Writes no categorised output (`--output` not required in this mode). Requires `--impact-output-dir`; mutually exclusive with `--reconcile` and `--verify`. |
| `--impact-output-dir DIR`| Directory for impact artefacts (`impact_report.json` — versioned schema with rulepack SHA-256 hashes; `impact_changes.csv` — row-level before/after). Required in impact mode; created if absent. |
| `--impact-html`          | Additionally emit a self-contained `impact_report.html` (amber REVIEW REQUIRED / green NO BEHAVIOURAL CHANGE banner, transition matrix, per-rule deltas, attribution section, row-level table capped at 50). Requires `--impact-rules` (and `--impact-output-dir`). See [impact.md](impact.md). |

## 2) `finlang-discover` — Discovery Tool

Scan a processed CSV to find frequently-occurring, **uncategorized** counterparties and produce candidate tables for rule generation.

### Flags

| Flag                                     | Description                                        |
| ---------------------------------------- | -------------------------------------------------- |
| `--input PATH`                           | Categorized CSV from a prior `finlang` run.        |
| `--candidates PATH`                      | Output CSV of shortlisted candidates.              |
| `--all PATH` (alias: `--all-candidates`) | Output full candidate set with aggregates.         |
| `--min-count N`                          | Minimum occurrences to include (default sensible). |
| `--min-amount A`                         | Minimum absolute amount filter (optional).         |
| `--top-k N`                              | Limit to top-N by frequency/weight (optional).     |
| `--since-date YYYY-MM-DD`                | Only consider rows on/after this date.             |
| `--include-excluded`                     | Include `exclude=True` rows in discovery (default: skip them). |
| `--encoding NAME`                        | Input encoding or `auto`.                          |
| `--strict-parse`                         | Fail fast on malformed input.                      |

### Output Format
**`--candidates` CSV columns:**
- `counterparty_fingerprint` — Normalized counterparty key
- `example_counterparty_name` — Original counterparty text (for reference)
- `count` — Number of occurrences
- `sample_amount` — Example transaction amount
- `sample_date` — Example transaction date

**`--all-candidates` CSV columns:**
- `counterparty_fingerprint` — Normalized counterparty key
- `example_counterparty_name` — Original counterparty text
- `count` — Number of transactions for this counterparty  
- `last_seen_date` — Most recent transaction date  
- `max_abs_amount` — Largest absolute transaction amount  
- `total_value` — Sum of all transaction amounts

> **Note:** `finlang-discover` also supports standard locale flags (`--decimal`, `--thousands`, `--dayfirst`, `--date-format`) and performance flags (`--fastio`, `--headless`, `--fail-threshold`). See Main CLI for details.

> **Exclude-aware (v0.7.4):** By default, rows with `exclude=True` are skipped during discovery — they are intentionally out of scope, not categorisation gaps. Use `--include-excluded` to surface them (e.g., for review workflows).

---

## 3) `finlang-suggest` — Rule Generation

Turn discovery candidates into **draft `.fin` rules** for review/merge.

### Flags

| Flag                | Description                                                  |
| ------------------- | ------------------------------------------------------------ |
| `--input PATH`      | Candidates CSV (typically from `discover`).                  |
| `--output PATH`     | Output `.fin` file with suggested rules.                     |
| `--rules PATH`      | Your existing `.fin` (used to avoid duplicates).             |
| `--emit-match MODE` | `exact` or `fuzzy` (default). Use `exact` for production-grade 1:1 rules. |
| `--category NAME`   | Default category to assign (e.g., `Review`).                 |
| `--prefix STR`      | Optional rule-name prefix (e.g., `AUTO`).                    |
| `--append`          | Append to output file if it exists.                          |
| `--overwrite`       | Overwrite output file (mutually exclusive with `--append`).  |
| `--quote-style`     | Quote character for emitted rules (`"` or `'`).              |

### Output
- A syntactically correct `.fin` file with conservative, deduplicated rules that you should **review** and then merge into your primary ruleset.

---

## Rule Packs Quick Reference

Bundled packs provide baseline categorization. Use with `--include-pack`:

| Pack | Alias | Description |
|------|-------|-------------|
| `retail` | — | UK grocery & retail (Tesco, Sainsbury's, Lidl, etc.) |
| `transport` | — | Transport & fuel (Uber, TfL, Shell, BP) |
| `subscriptions` | `subs` | Streaming & software (Spotify, Netflix, Adobe) |
| `travel` | — | Airlines & hotels (Airbnb, Ryanair, BA) |
| `financial` | — | Bank fees, interest, ATM, FX |
| `compliance` | — | Flags for large transactions, FX, duplicates |
| `sanity` | — | Data quality checks (empty fields, zero amounts) |
| `examples` | — | Tutorial rules (not for production) |

**Common combinations:**
```bash
# Personal finance
--include-pack retail,transport,subs,sanity

# Business expenses  
--include-pack retail,transport,travel,financial,sanity
```

> 📘 See [rulepacks.md](rulepacks.md) for detailed pack contents and commercial packs.

> **Stability note:** Pack IDs (`retail`, `transport`, `subs`, etc.) are stable and won't change. The underlying filenames (e.g., `01-vendors-retail.fin`) are internal and may be renamed in future versions.

---

## 4) Environment Variables

| Variable             | Effect                                           | Example                          |
| -------------------- | ------------------------------------------------ | -------------------------------- |
| `FINLANG_SAFE_TEXT`  | Enable CSV-injection protections for text fields | `export FINLANG_SAFE_TEXT=1`     |
| `FINLANG_AUDIT_MODE` | Default audit mode if `--audit-mode` omitted     | `export FINLANG_AUDIT_MODE=full` |
| `FINLANG_AUDIT_MAX`  | Cap number of audit entries                      | `export FINLANG_AUDIT_MAX=10000` |

---

## 5) Quick Reference Table

| Task                          | Command                                                      |
| ----------------------------- | ------------------------------------------------------------ |
| Minimal run (UK/US)           | `finlang --input bank.csv --output out.csv --rules rules.fin --fastio` |
| EU/CH locale (comma decimals) | `finlang --input bank.csv --output out.csv --rules rules.fin --decimal "," --thousands "." --dayfirst --encoding auto` |
| Strict schema check           | `finlang --input bank.csv --output out.csv --rules rules.fin --strict-parse` |
| Growth loop (discover)        | `finlang-discover --input out.csv --candidates cand.csv --all all.csv --min-count 3` |
| Growth loop (suggest)         | `finlang-suggest --input cand.csv --output draft.fin --rules rules.fin --emit-match exact --category "Review"` |

---

## 6) Practical Recipes

### Daily Run (audited)
```bash
finlang --input transactions.csv --output categorized.csv \
  --rules my_rules.fin --include-pack retail,sanity \
  --fastio --audit audit.json --audit-mode lite
```

**What's happening**

* `transactions.csv` → raw bank export (headers mapped to canonical fields)
* `my_rules.fin` → your personal ruleset (**last matching rule wins**)
* `--include-pack retail,sanity` → baseline coverage + sanity checks
* `--audit audit.json --audit-mode lite` → logs changed cells (lite = changed cells only)
* `--fastio` → faster IO with PyArrow

### International CSV (EU)

```bash
finlang --input bank_eu.csv --output out.csv --rules rules.fin \
  --decimal "," --thousands "." --dayfirst --encoding auto --fastio
```

### Growth Loop (3-step)

```bash
# 1) Process with your current rules
finlang --input data.csv --output categorized.csv --rules rules.fin --fastio

# 2) Discover candidates
finlang-discover --input categorized.csv \
  --candidates candidates.csv \
  --all-candidates all_candidates.csv \
  --min-count 3 --strict-parse --encoding auto

# 3) Suggest rules
finlang-suggest --input candidates.csv --output draft_rules.fin \
  --rules rules.fin --emit-match exact --category "Review"
```

### CI Validation with Fail Threshold

Use `--fail-threshold` to abort processing if too many rows are dropped during normalization:

```bash
# Fail if more than 5% of rows are dropped
finlang --input data.csv --output clean.csv --rules rules.fin \
  --fail-threshold 0.05

# Exit code: 0 = success, 2 = threshold exceeded
echo "Exit code: $?"
```

> **Note:** When `--strict-parse` is enabled, the threshold is forced to `0.0` (any dropped row is fatal).

This is useful in CI/CD pipelines to catch data quality issues early.

---

## 7) FAQ

**Q: Which rule takes precedence?**
A: The **last matching rule wins** for a transaction (deterministic override model). See `docs/rule_language.md`.

**Q: What exit codes does FinLang return?**
A: `0` = success, `1` = runtime error (e.g., file not found, unexpected exception during rule execution, invalid rule syntax, row-count mismatch on `--reconcile`, missing reconcile field), `2` = configuration/validation failure (e.g., `--fail-threshold` exceeded, `--strict-parse` error, missing required columns, invalid `--decimal`/`--thousands` values, no valid rules found, `--reconcile` without `--audit-mode full`, `--reconcile-html` without `--reconcile-output-dir`), `3` = post-engine check failure (`--verify` or `--verify-full` detected data mismatch, OR `--reconcile` detected categorisation disagreement).

**Q: Can I filter by date in `finlang` directly?**
A: Date filtering is available in `finlang-discover` via `--since-date`. The main `finlang` CLI does not currently implement `--since-date`.

**Q: What does `--quote-style` accept?**
A: The **literal** quote character to use in emitted rules: `"` or `'`.

**Q: Do I need a custom mapping?**
A: Usually no. The bundled map covers most UK/EU banks. See `docs/mapping_guide.md` for custom maps and amount synthesis.

---

## ⚠️ Known Issues (Active)

* None

---

## Related Documentation

* `docs/install.md`
* `docs/flags.md`
* `docs/workflows.md`
* `docs/mapping_guide.md`
* `docs/amount_synthesis.md`
* `docs/rule_language.md`
* `docs/rulepacks.md`
* `docs/growth_loop_best_practices.md`
* `docs/faq.md`
* `docs/api.md` — HTTP API wrapper over these CLI entry points (`pip install finlang[api]`)
* `docs/api_reference.md` — full API endpoint reference
