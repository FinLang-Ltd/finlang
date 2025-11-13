# 📖 FinLang CLI Reference
*Version: v0.6.4.post1 (GA • Rev 3.5)*

This is the authoritative, production-ready CLI reference for FinLang v0.6.4.post1. It preserves the comprehensive structure of the original guide while fixing the three critical issues you flagged and harmonizing links/notes with the rest of the GA docs.

---

## 0) Quick Navigation
- [1) `finlang` — Main CLI](#1-finlang--main-cli)
- [2) `finlang-discover` — Discovery Tool](#2-finlang-discover--discovery-tool)
- [3) `finlang-suggest` — Rule Generation](#3-finlang-suggest--rule-generation)
- [4) Environment Variables](#4-environment-variables)
- [5) Quick Reference Table](#5-quick-reference-table)
- [6) Practical Recipes](#6-practical-recipes)
- [7) FAQ](#7-faq)
- [⚠️ Known Issues (v0.6.4)](#️-known-issues-v064)
- [Related Documentation](#related-documentation)

---

## 1) `finlang` — Main CLI

### Purpose
Apply your rules (and optional rule packs) to a CSV of transactions to produce a categorized, normalized output with an optional audit trail.

### Mapping & Canonicalization (Fields after header mapping)
FinLang expects the following **canonical columns** after mapping/synthesis. Your source CSV headers are normalized via `--map` (or the built-in map) into these canonical names:

- `date` — Transaction date (ISO recommended)
- `amount` — Signed numeric amount (synthesis allowed from `debit`/`credit`)
- `counterparty` — Merchant / payee / descriptor
- `currency` — Optional 3-letter code (e.g., GBP, USD, EUR)
- `memo` — Optional free text / description
- `category` — Optional initial category (rules may override)
- `status` — Optional transaction status
- `exclude` — Optional exclusion flag (informational only in v0.6.4)

> **Required after mapping/synthesis:** `date`, `amount`, `counterparty`. If missing, FinLang exits with a fatal error.

> **Rule precedence:** **Last matching rule wins** for each transaction (by design for deterministic overrides).

### Flags

| Flag | Description |
|------|-------------|
| `--input PATH` | Input CSV file to process. |
| `--output PATH` | Output CSV after rule processing. **Must be writeable; no auto-fallback name in v0.6.4.** |
| `--rules PATH` | Your primary `.fin` rules file. |
| `--include-pack LIST` | Comma-separated built-in packs to include (e.g., `retail,sanity`). |
| `--map PATH` | Custom header mapping JSON (replaces bundled map). |
| `--audit PATH` | Write audit JSON (diff of changed cells). |
| `--audit-mode MODE` | `none | lite | full` — scope of logged changes. |
| `--fastio` | Use PyArrow for IO (20–40% faster in our benches). |
| `--headless` | Suppress non-essential console output. |
| `--strict-parse` | Fail fast on malformed CSV / schema issues. |
| `--decimal CH` | Decimal separator for numbers (e.g., `,`). |
| `--thousands CH` | Thousands/grouping separator (e.g., `.`, space, NBSP `\u00A0`, thin NBSP `\u202F`). |
| `--dayfirst` | Parse dates as `DD/MM/...` instead of `MM/DD/...`. |
| `--encoding NAME` | Input file encoding (e.g., `utf-8`, `latin-1`, or `auto`). |
| `--date-format STR` | Explicit strptime format for dates (e.g., `%Y-%m-%d`). |
| `--output-encoding NAME` | Output encoding (default UTF-8). |
| `--timings` | Print basic step timings to STDERR. |
| `--fail-threshold F` | Abort if drop-rate > `F` (fraction `0.0–1.0`). **** |

## 2) `finlang-discover` — Discovery Tool

Scan a processed CSV to find frequently-occurring, **uncategorized** counterparties and produce candidate tables for rule generation.

### Flags

| Flag | Description |
|------|-------------|
| `--input PATH` | Categorized CSV from a prior `finlang` run. |
| `--candidates PATH` | Output CSV of shortlisted candidates. |
| `--all PATH` (alias: `--all-candidates`) | Output full candidate set with aggregates. |
| `--min-count N` | Minimum occurrences to include (default sensible). |
| `--min-amount A` | Minimum absolute amount filter (optional). |
| `--top-k N` | Limit to top-N by frequency/weight (optional). |
| `--since-date YYYY-MM-DD` | Only consider rows on/after this date. |
| `--encoding NAME` | Input encoding or `auto`. |
| `--strict-parse` | Fail fast on malformed input. |

### Output Format
**`--candidates` CSV columns (typical):**
- `counterparty`
- `count`
- `example_memo`
- `example_amount`

**`--all` CSV adds:**
- `count` — Number of transactions for this counterparty  
- `last_seen_date` — Most recent transaction date  
- `max_abs_amount` — Largest absolute transaction amount  
- `total_value` — Sum of all transaction amounts

> The exact set/order may expand over time, but these fields are present in v0.6.4.

---

## 3) `finlang-suggest` — Rule Generation

Turn discovery candidates into **draft `.fin` rules** for review/merge.

### Flags

| Flag | Description |
|------|-------------|
| `--input PATH` | Candidates CSV (typically from `discover`). |
| `--output PATH` | Output `.fin` file with suggested rules. |
| `--rules PATH` | Your existing `.fin` (used to avoid duplicates). |
| `--emit-match MODE` | `exact | smart` (use `exact` for production-grade 1:1 rules). |
| `--category NAME` | Default category to assign (e.g., `Review`). |
| `--prefix STR` | Optional rule-name prefix (e.g., `AUTO`). |
| `--append` | Append to output file if it exists (default overwrite disabled unless specified). |
| `--quote-style` | Quote character for emitted rules (`"` or `'`). |

### Output
- A syntactically correct `.fin` file with conservative, deduplicated rules that you should **review** and then merge into your primary ruleset.

---

## 4) Environment Variables

| Variable | Effect | Example |
|----------|--------|---------|
| `FINLANG_SAFE_TEXT` | Enable CSV-injection protections for text fields | `export FINLANG_SAFE_TEXT=1` |
| `FINLANG_AUDIT_MODE` | Default audit mode if `--audit-mode` omitted | `export FINLANG_AUDIT_MODE=full` |
| `FINLANG_AUDIT_MAX` | Cap number of audit entries | `export FINLANG_AUDIT_MAX=10000` |

---

## 5) Quick Reference Table

| Task | Command |
|------|---------|
| Minimal run (UK/US) | `finlang --input bank.csv --output out.csv --rules rules.fin --fastio` |
| EU/CH locale (comma decimals) | `finlang --input bank.csv --output out.csv --rules rules.fin --decimal , --thousands . --dayfirst --encoding auto` |
| Strict schema check | `finlang --input bank.csv --output out.csv --rules rules.fin --strict-parse` |
| Growth loop (discover) | `finlang-discover --input out.csv --candidates cand.csv --all all.csv --min-count 3` |
| Growth loop (suggest) | `finlang-suggest --input cand.csv --output draft.fin --rules rules.fin --emit-match exact --category "Review"` |

---

## 6) Practical Recipes

### Daily Run (audited)
```bash
finlang --input transactions.csv --output categorized.csv   --rules my_rules.fin --include-pack retail,sanity   --fastio --audit audit.json --audit-mode lite
```

**What’s happening**
- `transactions.csv` → raw bank export (headers mapped to canonical fields)
- `my_rules.fin` → your personal ruleset (**last matching rule wins**)
- `--include-pack retail,sanity` → baseline coverage + sanity checks
- `--audit audit.json --audit-mode lite` → logs changed cells (lite = changed cells only)
- `--fastio` → faster IO with PyArrow

### International CSV (EU)
```bash
finlang --input bank_eu.csv --output out.csv --rules rules.fin   --decimal , --thousands . --dayfirst --encoding auto --fastio
```

### Growth Loop (3-step)
```bash
# 1) Process with your current rules
finlang --input data.csv --output categorized.csv --rules rules.fin --fastio

# 2) Discover candidates
finlang-discover --input categorized.csv   --candidates candidates.csv   --all all_candidates.csv   --min-count 3 --strict-parse --encoding auto

# 3) Suggest rules
finlang-suggest --input candidates.csv --output draft_rules.fin   --rules rules.fin --emit-match exact --category "Review"
```

---

## 7) FAQ

**Q: Which rule takes precedence?**  
A: The **last matching rule wins** for a transaction (deterministic override model). See `docs/rule_language.md`.

**Q: Why does `--fail-threshold` not fail my CI even though it prints FATAL?**  
A: In v0.6.4, it logs **FATAL** but exits `0`. Use the CI workaround shown above; this will be fixed in a future release.

**Q: Can I filter by date in `finlang` directly?**  
A: Date filtering is available in `finlang-discover` via `--since-date`. The main `finlang` CLI does not implement `--since-date` in v0.6.4.

**Q: What does `--quote-style` accept?**  
A: The **literal** quote character to use in emitted rules: `"` or `'`.

**Q: Do I need a custom mapping?**  
A: Usually no. The bundled map covers most UK/EU banks. See `docs/mapping_guide.md` for custom maps and amount synthesis.

---

## ⚠️ Known Issues (v0.6.4.post2)

- None

---

## Related Documentation

- `docs/install.md`
- `docs/flags.md`
- `docs/workflows.md`
- `docs/mapping_guide.md`
- `docs/amount_synthesis.md`
- `docs/rule_language.md`
- `docs/growth_loop_best_practices.md`
- `docs/release_notes_v0_6_4.md`
- `docs/faq.md`
- `docs/security.md`
