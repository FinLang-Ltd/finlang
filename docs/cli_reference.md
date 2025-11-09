# 📖 FinLang CLI Reference
*Applies to FinLang v0.6.4.post1 (GA Rev 3.1)*

## 🎯 About This Document

This is the **complete command-line reference** for all FinLang tools.

**Use this when:**
- You need flag syntax and defaults
- You're writing scripts or CI/CD pipelines
- You want to understand all available options

**For quick start guides, see:**
- [Install Guide](install.md) — Getting started
- [i18n Examples](i18n_examples.md) — Regional settings
- [Workflows](workflows.md) — Common patterns

---

## 1) Core CLI — `finlang`

**Simple Example:**
```bash
# Basic categorization with rules
finlang --input bank.csv --output categorized.csv --rules my_rules.fin
```

**Usage (Full):**
```bash
finlang --input <csv> --output <csv> [--rules FILE ...] [--include-pack PACKS] [--map FILE]
        [--audit FILE] [--audit-mode {none|lite|full}] [--strict-parse] [--fail-threshold F]
        [--decimal .|,] [--thousands ','|'.'|' '|'\''] [--dayfirst] [--date-format FMT]
        [--encoding CODEC|auto] [--output-encoding CODEC]
        [--fastio] [--timings] [--headless]
```

### Required
- `--input PATH` — Source CSV (raw bank export or canonical)
- `--output PATH` — Destination CSV (timestamped fallback if locked)

### Rules & Packs
- `--rules FILE [FILE …]` — One or more `.fin` files (highest precedence)
- `--include-pack retail,transport,...` — Bundled packs (lower precedence)

### Mapping & Canonicalization
- `--map FILE` — Optional header‑map JSON (defaults to bundled `bank.map.json`)
- Canonical columns: `counterparty, amount, date, category, flags, memo`
- Amount synthesis when needed:
  ```
  amount = abs(credit) - abs(debit)
  ```

### Auditing
- `--audit FILE` — Write audit JSON of rule‑driven changes
- `--audit-mode {none|lite|full}` (default: **lite**)
  - **none** — fastest, no audit
  - **lite** — changed cells only (capped)
  - **full** — before/after state diffs (capped)

### Internationalization & Encoding
- `--decimal` / `--thousands` — Numeric punctuation
- `--dayfirst` or `--date-format` — Date parsing strategy
- `--encoding` — Input codec (**default `utf-8-sig`**; `auto` recommended for safety)
- `--output-encoding` — Output CSV codec (default `utf-8`)

### Strictness & Execution
- `--strict-parse` — Enforce delimiter/header consistency; fail early
- `--fail-threshold F` — **Fraction `0.0–1.0`** (e.g., `0.05`)
- `--fastio` — Prefer PyArrow I/O (20–40% faster on large files)
- `--timings` — Print phase timings
- `--headless` — Suppress non-essential console output

---

## 2) Discovery Helper — `finlang-discover`

**Purpose:** Surface frequently occurring **uncategorized counterparties** to draft rules for.

**Usage:**
```bash
finlang-discover --input canonical.csv --candidates out.csv [--all out_full.csv]   [--min-count N] [--min-amount X] [--since-date YYYY-MM-DD] [--top-k K]   [--strict-parse] [--fail-threshold F]   [--encoding CODEC|auto] [--decimal .|,] [--thousands ','|'.'|' '|'\'']   [--dayfirst] [--date-format FMT] [--fastio] [--headless]
```

**Output Format (`--candidates`):**
```csv
counterparty_fingerprint,example_counterparty_name,count,sample_amount,sample_date
TESCO,TESCO STORES 1234,134,-92.34,2025-08-21
```
Use this as input to `finlang-suggest` to generate draft rules.

> ℹ️ **Note:** The **full table** specified via `--all` contains additional aggregates:
> `sum_amount, first_date, last_date`.

---

## 3) Suggestion Helper — `finlang-suggest`

**Purpose:** Generate conservative **draft `.fin` rules** from a candidates CSV.

**Usage:**
```bash
finlang-suggest --input candidates.csv --output draft_rules.fin   [--emit-match {exact|fuzzy}] [--category "Review"] [--prefix "SUGGEST"]   [--rules existing.fin] [--append|--overwrite] [--quote-style {always|minimal}]
```

**Key Flags**
- `--emit-match` — **Use `exact` for 1:1 production rules**; `fuzzy` may be broader.
- `--category` *(default "Review")* — Draft category label
- `--prefix` *(default "SUGGEST")* — Rule title prefix
- `--rules` — De‑dupe against existing rules
- `--append` / `--overwrite` — File write mode
- `--quote-style` — CSV/FIN quoting (`always|minimal`)

**Example Output**
```fin
# SUGGESTED (freq=134, last=2025-08-21, sample_amt=-92.34)
rule "SUGGEST: TESCO STORES 1234" {
  match:
    - counterparty == "TESCO STORES 1234"
  set:
    - category = "Review"
}
```

⚠️ **Important:** Always review draft rules manually before merging into production.  
The `"Review"` category is intentional—verify each rule’s logic before deployment.

---

## 4) Environment Variables

| Variable | Effect | Example |
|----------|--------|---------|
| `FINLANG_SAFE_TEXT` | Enable CSV injection protection | `export FINLANG_SAFE_TEXT=1` |
| `FINLANG_AUDIT_MODE` | Default audit mode | `export FINLANG_AUDIT_MODE=full` |
| `FINLANG_AUDIT_MAX` | Cap audit log entries | `export FINLANG_AUDIT_MAX=10000` |

**Usage Examples:**
```bash
# Linux/macOS
export FINLANG_AUDIT_MODE=full
finlang --input data.csv ...

# Windows PowerShell
$env:FINLANG_AUDIT_MODE="full"
finlang --input data.csv ...
```

---

## 5) Quick Reference Table

> 🧭 This table lists the most common operational flags.  
> For full canonical details (all flags, data types, and defaults), see [flags.md](flags.md).

| Flag | Applies To | Default | Meaning / Use Case | See Also |
|------|-------------|----------|--------------------|-----------|
| `--input` | finlang, discover | required | Input CSV | - |
| `--output` | finlang, suggest | required | Output file | - |
| `--rules` | finlang, suggest | none | User rules (highest precedence) | [rule_language.md](rule_language.md) |
| `--include-pack` | finlang, benchmarks | none | Add built‑in packs | [workflows.md](workflows.md) |
| `--map` | finlang, benchmarks | bundled | Column mapping | [mapping_guide.md](mapping_guide.md) |
| `--audit` | finlang | none | Write audit JSON | [release_notes_v0_6_4.md](release_notes_v0_6_4.md) |
| `--audit-mode` | finlang | lite | Audit verbosity | [release_notes_v0_6_4.md](release_notes_v0_6_4.md) |
| `--strict-parse` | finlang, discover | off | Hardened CSV parsing | [flags.md](flags.md) |
| `--fail-threshold` | finlang, discover | none | Fraction `0.0–1.0` drop‑rate ceiling | [flags.md](flags.md) |
| `--decimal` / `--thousands` | finlang, discover | . / , | Numeric punctuation | [i18n_examples.md](i18n_examples.md) |
| `--dayfirst` / `--date-format` | finlang, discover | off / none | Date parsing strategy | [i18n_examples.md](i18n_examples.md) |
| `--encoding` | finlang, discover | utf-8-sig | Input codec (`auto` recommended) | [flags.md](flags.md) |
| `--output-encoding` | finlang | utf-8 | Output codec | - |
| `--emit-match` / `--quote-style` | suggest | fuzzy / minimal | Rule emission style | [growth_loop_best_practices.md](growth_loop_best_practices.md) |
| `--category` / `--prefix` | suggest | Review / SUGGEST | Rule metadata | - |
| `--append` / `--overwrite` | suggest | append | Write mode | - |
| `--fastio` | finlang, discover | off | Arrow I/O acceleration | - |
| `--timings` / `--headless` | finlang, discover | off | Diagnostics / quiet mode | - |

---

## 6) Practical Recipes

**Daily Run (Auditable + Fast)**
```bash
finlang --input in.csv --output out.csv --rules my.fin   --include-pack retail,sanity --fastio   --audit audit.json --audit-mode lite
```

**Growth Loop (Rev 3.1)**
```bash
# 1) Discover candidates (CSV)
finlang-discover --input categorized.csv --candidates candidates.csv --top-k 50

# 2) Generate draft rules
finlang-suggest --input candidates.csv --output draft_rules.fin   --emit-match exact --category "Review" --append

# 3) Apply rules + packs with full audit
finlang --input transactions.csv --output categorized.csv   --rules draft_rules.fin --include-pack retail,sanity   --audit audit.json --audit-mode full
```

**Enterprise CI/CD (Headless + Strict)**
```bash
finlang --input daily_export.csv --output categorized.csv   --rules production_rules.fin   --include-pack retail,transport,subs   --strict-parse --fail-threshold 0.02   --encoding auto --fastio   --headless --audit ci_audit.json --audit-mode lite

if [ $? -ne 0 ]; then
  echo "Categorization failed - check logs"
  exit 1
fi
```

---

## FAQ

**Q: I tried `flags = "X"` and it didn’t work. Why?**  
A: Flags are append‑only. Use `flags += "X"`.

**Q: Why did audit mode slow my job?**  
A: `full` mode records before/after diffs. Use `lite` (default) for speed.

**Q: My amounts are wrong (199,99 → 19999.0).**  
A: Your file uses a comma decimal. Add `--decimal , --thousands .` or see [i18n_examples.md](i18n_examples.md).

**Q: Mixed US/EU formats in one file?**  
A: Not supported. FinLang enforces one locale per run for determinism. Split your file or normalize formats first.

**Q: Which rules take precedence?**  
A: Load order then file order — user `--rules` first, then packs; within a file, top to bottom.

---

© FinLang Ltd — v0.6.4.post1 (GA Rev 3.1)
