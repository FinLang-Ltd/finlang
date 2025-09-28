# FinLang CLI Reference

## Install

```bash
pip install "finlang[fastio]"
```

Optional: install `pyarrow` for faster `--fastio`.
Supports Python 3.9+ on Windows, macOS, Linux.


This document provides a full reference of available switches and flags across the FinLang ecosystem, 
including the core CLI, discovery/suggestion helpers, and benchmarking harnesses. It also includes 
example workflows such as the *growth loop* and practical recipes for daily use.

---

## 1. Core CLI (`finlang`)

**Usage:**

```bash
finlang --input <csv> --output <csv> [--rules FILE ...] [--include-pack PACKS] [--map FILE]
        [--audit FILE] [--audit-mode {none|lite|full}] [--fastio] [--timings] [--headless]
```

### Required

- `--input PATH`  
  Source transactions CSV. Can be raw (with bank headers) or canonical.  
- `--output PATH`  
  Destination CSV. If locked, FinLang writes a timestamped fallback.

### Rules & Packs

- `--rules FILE [FILE …]`  
  Load one or more `.fin` rule files (highest precedence).  
- `--include-pack retail,transport,...`  
  Add built-in packs (lower precedence than rules).

### Mapping & Canonicalization

- `--map FILE`  
  Optional header mapping JSON (defaults to bundled `bank.map.json`).  
- Canonical columns: `counterparty, amount, date, category, flags, memo`.  
- Debit/credit synthesis: `amount = credit – debit` if no `amount` column exists.

### Auditing

- `--audit FILE`  
  Write structured audit JSON of rule-driven changes.  
- `--audit-mode {none|lite|full}` (default: *lite*)  
  - **none**: fastest, no audit  
  - **lite**: records changed cells (capped)  
  - **full**: maximum detail (capped)

### Performance & Logging

- `--fastio`  
  Use `pyarrow` for faster CSV IO if available.  
- `--timings`  
  Print stage-by-stage timing breakdown.  
- `--headless`  
  Suppress console chatter (use in scripts/benchmarks).

### Rule Engine Notes

- Match fields: `counterparty, amount, category, flags, status, memo`.  
- Operators: `==`, `~` (wildcards), `in` (for `amount` ranges).  
- Set fields: `category, status, memo, flags, exclude`.  
- **Flags:** only `flags += "..."` (append) is allowed.  
- **Exclude:** defaults to `false`. Rules can set `exclude = true`.

---

## 2. Growth Loop Example

A recommended workflow for bootstrapping coverage:

```bash
# 1. Discover frequent uncategorized counterparties
finlang-discover --input categorized.csv --top-k 20 > suggestions.fin

# 2. Append suggested rules into your main ruleset
type suggestions.fin >> my_rules.fin    # (Windows)
cat suggestions.fin >> my_rules.fin     # (Linux/macOS)

# 3. Apply rules + packs with full audit trail
finlang --input transactions.csv --output categorized.csv \
        --rules my_rules.fin --include-pack retail,sanity --audit-mode full
```
**Growth Loop Diagram**

![FinLang Growth Loop](assets/finlang_growth_loop.png)


---

## 3. Discovery Helper (`finlang-discover`)

**Purpose:** Surface frequently occurring *uncategorized counterparties* so you can draft rules to cover them.

**Usage:**

```bash
finlang-discover --input canonical.csv --candidates out.csv --all out_full.csv
                 [--min-count N] [--min-amount X] [--since-date YYYY-MM-DD] [--top-k K]
```

### Flags

- `--input FILE` (required)  
  Canonical CSV with `counterparty, category, amount, date`.  
- `--candidates FILE` (required)  
  Shortlist output (top counterparties).  
- `--all FILE` (required)  
  Full frequency table.  
- `--min-count N` (default 5)  
  Minimum occurrences to consider.  
- `--min-amount X`  
  Always include counterparties with a single transaction ≥ X.  
- `--since-date YYYY-MM-DD`  
  Filter to recent data.  
- `--top-k K`  
  Limit shortlist length.

**Outputs:** shortlist of suggested counterparties + full table of frequencies.

---

## 4. Suggestion Helper (`suggest.py`)

**Usage:**

```bash
python suggest.py --input candidates.csv --output draft_rules.fin
                  [--rules existing.fin] [--category "Review"]
                  [--prefix "SUGGEST"] [--append|--overwrite]
```

### Flags

- `--input FILE` (required)  
  Shortlist from `discover`.  
- `--output FILE` (required)  
  Draft rules file.  
- `--rules FILE`  
  De-dupe against existing rules.  
- `--category NAME` (default: `"Review"`)  
  Category for draft rules.  
- `--prefix NAME` (default: `"SUGGEST"`)  
  Rule title prefix.  
- `--append` / `--overwrite`  
  Control file writing mode.

**Output:** Draft `.fin` rules like:

```finlang
# SUGGESTED (freq=134, last=2025-08-21, sample_amt=-92.34)
rule "SUGGEST: TESCO" {
  match:
    - counterparty ~ "*TESCO*"
  set:
    - category = "Review"
}
```

---

## 5. Benchmark Harnesses

### A) Single Ruleset

**Usage:**

```bash
python -m benchmarks.bench_finlang_harness --mode full-cli --run-fin "finlang --fastio --audit-mode none" \
  --rules examples/rules.demo.fin --include-pack retail,transport,subs \
  --rows 25000 50000 100000 200000 --cols 5 20 35 50 --runs 3 \
  --final-rows 1000000 5000000 --outdir bench_out
```

**Flags:**

- `--mode {full-cli|io-only}`  
- `--run-fin "CMD"` (the CLI command template)  
- `--rules FILE`  
- `--include-pack PACKS`  
- `--map FILE`  
- `--rows N1 N2 ...`  
- `--cols C1 C2 ...`  
- `--runs K` (repeats per grid point)  
- `--final-rows N ...` (big finale runs)  
- `--cli-parse` (parse CLI stdout timings instead of timer)  
- `--outdir DIR` (results + plots)

**Outputs:** `bench_results.csv`, heatmaps, surfaces, finale plots.

### B) Multi-Ruleset

**Usage:**

```bash
python -m benchmarks.bench_finlang_rulesets --run-fin "finlang --fastio" \
  --rules-set RETAIL:examples/rules.retail.fin --rules-set TRANSPORT:examples/rules.transport.fin \
  --rows 50000 100000 --cols 10 20 --repeats 3 --outdir bench_out
```

- `--rules-set NAME:FILE` (repeatable)  
- Other flags mirror single-ruleset harness.

**Outputs:** comparison heatmaps and lines across rulesets.

---

## 6. Quick Reference Table

| Flag | Applies To | Default | Meaning / Use Case |
|------|------------|---------|--------------------|
| `--input` | finlang, discover | required | Input CSV file |
| `--output` | finlang, suggest | required | Output CSV or rules file |
| `--rules` | finlang, suggest | none | User rules (highest precedence) |
| `--include-pack` | finlang, benchmarks | none | Add built-in packs |
| `--map` | finlang, benchmarks | bundled | Column mapping JSON |
| `--audit` | finlang | none | Audit JSON path |
| `--audit-mode` | finlang | lite | Audit verbosity (none/lite/full) |
| `--fastio` | finlang | off | Use pyarrow IO if installed |
| `--timings` | finlang | off | Show timing breakdown |
| `--headless` | finlang | off | Suppress console output |
| `--min-count` | discover | 5 | Min frequency for candidates |
| `--min-amount` | discover | none | Always include above this |
| `--since-date` | discover | none | Filter recent data |
| `--top-k` | discover | none | Limit shortlist length |
| `--category` | suggest | Review | Default category for drafts |
| `--prefix` | suggest | SUGGEST | Rule title prefix |
| `--append/--overwrite` | suggest | append | File writing mode |
| `--mode` | benchmarks | full-cli | Benchmark mode |
| `--rows/--cols` | benchmarks | none | Grid sizes |
| `--runs` | benchmarks | 1 | Repeats per run |
| `--final-rows` | benchmarks | none | Big finale sizes |
| `--outdir` | benchmarks | bench_out | Results directory |

---

## 7. Practical Recipes

- **Daily run (fast + auditable):**  
  ```bash
  finlang --input in.csv --output out.csv --rules my.fin \
          --include-pack retail,sanity --fastio --audit audit.json --audit-mode lite
  ```

- **Pure throughput benchmark:**  
  ```bash
  python -m benchmarks.bench_finlang_harness --mode full-cli \
    --run-fin "finlang --fastio --audit-mode none --headless" \
    --rows 100000 500000 1000000 --cols 10 50 --runs 3 --outdir bench_out
  ```

- **Coverage growth loop:**  
  ```bash
  finlang-discover --input categorized.csv --top-k 50 > suggestions.fin
  python suggest.py --input suggestions.fin --output draft_rules.fin --rules my_rules.fin --category "Review"
  finlang --input transactions.csv --output categorized.csv --rules my_rules.fin --include-pack retail,sanity --audit-mode full
  ```

---

**Note:** Defaults such as `exclude = false` and `flags +=` (append-only) are enforced to guarantee auditability and prevent silent overrides.


---

## FAQ

**Q: I tried `flags = "X"` and it didn’t work. Why?**  
A: Flags are append-only. Use `flags += "X"` instead. This ensures no accidental overwrites.

**Q: Why is audit mode slowing things down?**  
A: `--audit-mode full` records every change, which adds overhead. Use `lite` for daily use, `none` for benchmarks.

**Q: My amounts look wrong. Why?**  
A: If no `amount` column exists, FinLang synthesizes it from debit/credit. Check your bank map or source headers.

**Q: Which rules take precedence?**  
A: `--rules` always override `--include-pack`. Put your custom rules first.
