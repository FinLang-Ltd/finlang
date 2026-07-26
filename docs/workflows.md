# 📖 Core Workflows
> **Applies to:** FinLang v0.7+
> **Status:** Stable
> **Last verified:** v0.8.3



## 🎯 Quick Navigation

**I want to…**
- [Run FinLang daily](#-daily-run) → Basic categorization
- [Improve my rules (feedback loop)](#-growth-loop-feedback-workflow) → Iterative coverage improvement
- [Test performance](#-benchmarking) → Validate scaling
- [Deploy to a team](#-enterprise-integration--workflows) → Enterprise setup & CI/CD

---



## ✅ Daily Run

The **Daily Run** applies your personal rules plus optional starter packs to new transaction data.

### First Time? Quick Setup
```bash
# 1) Install FinLang (with fast IO extras)
pip install "finlang[fastio]"

# 2) Create an empty rules file
echo "# My FinLang Rules" > my_rules.fin

# 3) Run your first categorization
finlang --input transactions.csv --output categorized.csv --rules my_rules.fin
```



### Example (Full Production Command)

```bash
finlang --input transactions.csv --output categorized.csv \
  --rules my_rules.fin --include-pack retail,sanity \
  --fastio --audit audit.json --audit-mode lite
```



### What’s Happening

- `transactions.csv` → raw bank export (**FinLang normalizes headers automatically**).
- `my_rules.fin` → your personal ruleset (**highest precedence**).
- `--include-pack retail,sanity` → adds baseline coverage & sanity checks.
- `--audit audit.json --audit-mode lite` → logs changed cells for traceability (lite = only changed cells).
- `--fastio` → speeds up CSV IO with PyArrow.

> **🌍 International users:** If your CSV uses European formats (e.g., `1.234,56` or `DD/MM/YYYY`), add I18n flags:
> ```bash
> finlang --input transactions.csv --output categorized.csv \
>   --rules my_rules.fin --include-pack retail,sanity \
>   --decimal "," --thousands "." --dayfirst --encoding auto --strict-parse
> ```
> See **i18n_examples.md** for regional recipes.

**When to Use**
- Daily or weekly transaction categorization.
- Producing audit trails for compliance or bookkeeping.
- Fast, reliable updates with minimal overhead.

---



## 🔁 Growth Loop (Feedback Workflow)

![Growth Loop Diagram](assets/finlang_growth_loop.png)

FinLang's Growth Loop converts **uncategorized** data into **new rules** using three tools:

- `finlang` → Process transactions
- `finlang-discover` → Find frequent uncategorized patterns
- `finlang-suggest` → Generate conservative draft rules

### Step 1 — Initial Processing

**When to use:** Start of every growth loop cycle, or when processing new transaction data.

Run FinLang as per the Daily Run example above. This produces `categorized.csv`.

### Step 2 — Discover Candidates

**When to use:** After processing, to identify recurring uncategorized counterparties.

Identify frequently-occurring **uncategorized** counterparties and also export full discovery stats.

> **Exclude-aware (v0.7.4):** Rows marked `exclude=True` are skipped by default — they are intentionally out of scope, not categorisation gaps. To include them (e.g., for audit or review), add `--include-excluded`.

```bash
finlang-discover --input categorized.csv \
  --candidates candidates.csv \
  --all-candidates all_candidates.csv \
  --min-count 3 --strict-parse --encoding auto
```

### Step 3 — Suggest Draft Rules

**When to use:** When you have candidates worth converting to rules (typically 5+ occurrences).

Generate draft `.fin` rules from the candidates. For production-grade precision, prefer **exact** matching.

```bash
finlang-suggest --input candidates.csv --output draft_rules.fin \
  --rules my_rules.fin \
  --emit-match exact \
  --category "Review"
```

> ⚠️ **Important:** Always review `draft_rules.fin` before merging. The `"Review"` category is intentional—verify logic then update categories.

### Step 4 — Review & Merge

**When to use:** After reviewing suggested rules for accuracy. Never merge blindly.

```bash
# Linux/macOS
cat draft_rules.fin >> my_rules.fin

# Windows (PowerShell)
Get-Content draft_rules.fin | Add-Content my_rules.fin

# Windows (CMD)
type draft_rules.fin >> my_rules.fin
```

### Step 5 — Re-run with Full Audit

**When to use:** After merging new rules, to validate coverage improvement.

```bash
finlang --input transactions.csv --output categorized.csv \
  --rules my_rules.fin --include-pack retail,sanity \
  --audit audit_full.json --audit-mode full --fastio
```

### 📈 Expected Outcomes

|    Iteration | Uncategorized ↓ | Time/Loop  | Rules Added      |
| -----------: | --------------- | ---------- | ---------------- |
|   First loop | 60% → 40%       | ~45 min    | 15–30            |
|    3–5 loops | 40% → 15%       | ~20 min    | 5–10             |
| Steady state | <5%             | ~10 min/mo | Maintenance only |

*Results vary by dataset complexity and team discipline. Most users see **5–10%** improvement per loop.*

### Track Coverage

**Purpose:** Monitor your categorization progress over iterations. The goal is to reduce uncategorized transactions to <5%.

```bash
# Linux/macOS
finlang-discover --input categorized.csv --candidates temp.csv
grep -c '""' categorized.csv  # Count empty categories (heuristic)
```

```powershell
# Windows PowerShell
finlang-discover --input categorized.csv --candidates temp.csv
(Get-Content categorized.csv | Select-String '""').Count
```

---



## 🧪 Benchmarking

**When to benchmark**
- Validate that FinLang handles your data volume
- Compare ruleset strategies
- Capacity planning prior to rollout
- After major rule changes (regression check)

**When not to benchmark**

- Routine daily ops (adds noise)
- Before understanding your data patterns
- Without a specific performance question

### Single-Ruleset Harness (CLI)
```bash
python -m benchmarks.bench_finlang_harness \
  --mode full-cli \
  --run-fin "finlang --fastio --audit-mode none --headless --strict-parse --encoding auto" \
  --rules examples/rules.demo.fin \
  --rows 25000 50000 100000 200000 \
  --cols 5 20 35 50 \
  --runs 3 \
  --final-rows 1000000 5000000 \
  --outdir bench_out
```

### Performance at a Glance (v0.7.7)
| Rows × Cols | Runtime | Throughput | Context | Suitable For |
|------------:|--------:|-----------:|--------|--------------|
| 5M × 5  | ~18 s  | ~283 K rows/s | SME batch | Small business |
| 5M × 20 | ~72 s  | ~70 K rows/s  | Payment gateway | Mid-market |
| 5M × 50 | ~179 s | ~28 K rows/s  | Enterprise ledger | Enterprise |
| 20M × 6 | ~90 s (FastIO) | ~217 K rows/s | Integrity harness | Engine throughput ceiling |

> **v0.7.7 update:** A hot-path bug fix in `_to_number` (removing an unnecessary `\b` word boundary that was misclassifying no-space CR/DR formats) delivered +30-50% throughput on the integrity harness vs v0.7.6. See **benchmarks.md** for the full version comparison and methodology.

See **benchmarks.md** for detailed data & methodology.

---



## 🏢 Enterprise Integration & Workflows

### Git-Based Review Flow (Recommended)
```bash
# Create feature branch
git checkout -b add-suggested-rules

# Review and edit draft_rules.fin locally
# ... make changes ...

# Merge draft rules into main ruleset
cat draft_rules.fin >> my_rules.fin

# Commit & push
git add my_rules.fin
git commit -m "Add suggested rules for TESCO, AMAZON, UBER"
git push origin add-suggested-rules

# Open a Pull Request for review
```

### CI/CD Validation (GitHub Actions)
Protect your main branch with automated rule testing:

```yaml
name: Validate Rules
on: [pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install FinLang
        run: pip install "finlang[fastio]"
      - name: Validate Rules (strict, headless)
        run: >
          finlang --rules my_rules.fin
                  --input test_data/sample.csv
                  --output /dev/null
                  --headless --strict-parse --audit-mode none
```

> **Windows note:** Use `NUL` instead of `/dev/null` if running steps on Windows runners.

### Integrity Verification
FinLang can verify that immutable fields (date, amount, counterparty) are unchanged between input and output using built-in SHA-256 fingerprinting:

```bash
# Fast verification (fingerprint only, console output)
finlang --input data.csv --output out.csv --rules rules.fin --verify

# Full verification (fingerprint + field comparison)
finlang --input data.csv --output out.csv --rules rules.fin --verify-full

# CI/CD pipeline: verify + save artifacts for audit trail
finlang --input data.csv --output out.csv --rules rules.fin --verify --verify-output-dir ./audit

# v0.8.3: add --verify-html to also render a self-contained plain-English report
finlang --input data.csv --output out.csv --rules rules.fin --verify --verify-output-dir ./audit --verify-html
```

Exit code `3` indicates a verification failure. Artifacts include `verify_report.json`, `verify_proof.csv`, and `verify_mismatches.csv` (on failure only).

See [verify.md](verify.md) for the full feature explainer (when to use it, output anatomy, limitations).

---

## 🔄 Reconciliation Workflow

Where governance expects an independent challenge to a categorisation pipeline — typically an ML model — `--reconcile` produces a row-by-row mismatch report with rule attribution and audit reason. This is the integration pattern.

### Step 1 — Run FinLang against the same raw data the ML pipeline processed

```bash
finlang --input transactions.csv \
        --rules compliance.fin \
        --output finlang_out.csv \
        --audit audit.json --audit-mode full \
        --reconcile ml_categorised.csv \
        --reconcile-identity-fields date,amount,counterparty \
        --reconcile-output-dir audit/ \
        --reconcile-html
```

> **ML date conventions (v0.8.3):** the ML file's dates are read on their own terms — the convention is inferred from the column, or stated with `--reconcile-date-format`, and recorded in `reconcile_report.json` as `ml_date_convention`. See [reconciliation.md](reconciliation.md).

`--audit --audit-mode full` is required so mismatch rows can carry rule name + match condition. `--reconcile-html` is optional but recommended for compliance-context reports. `--reconcile-identity-fields` is recommended in CI: if the ML pipeline ever reorders its output (parallel batching, async writes), the identity guard fails structurally (exit `1`) instead of reporting nonsense mismatches over misaligned rows — exactly the failure mode an unattended pipeline won't catch by eye.

### Step 2 — Read the report

| Artefact | Purpose | Read by |
|---|---|---|
| `audit/reconcile_report.json` | Machine-readable summary (status, match rate, mismatches count, audit_entries_loaded) | CI/CD assertions, dashboards |
| `audit/reconcile_mismatches.csv` | One row per disagreement: counterparty, ML's category, FinLang's category, rule name, audit reason | Auditors, compliance reviewers |
| `audit/reconcile_report.html` | Self-contained HTML view of the above (opens offline, no JS) | Compliance reports, archival, stakeholder review |

Exit code `3` indicates one or more mismatches. CI/CD should treat this as "review needed" — not "the data is broken" (that's exit code 1) and not "configuration is wrong" (exit code 2).

### Step 3 — Decide what to do about the disagreements

`--reconcile` reports disagreements; it does not score them or judge which side is right. A human reads the mismatches CSV and decides.

The CSV column an auditor reads is the one a black-box ML model does not expose: `finlang_rule_matched` plus `finlang_audit_reason`. That column is the load-bearing piece — it's the answer to "why did FinLang reach a different conclusion?", which the regulator's challenger workflow needs.

### CI/CD pattern

```bash
finlang ... --reconcile ml_out.csv --reconcile-output-dir ./audit
EXIT=$?
if [ $EXIT -eq 3 ]; then
  echo "Reconciliation surfaced disagreements. See audit/reconcile_mismatches.csv"
  # Pipeline policy: notify reviewer, do NOT auto-block downstream
fi
```

See [reconciliation.md](reconciliation.md) for the full feature explainer.

---

### ✅ Rollout Checklist
**Phase 1: Pilot (Week 1–2)**
- [ ] Install FinLang in test environment
- [ ] Validate with 3 months historical data
- [ ] Train 2–3 power users
- [ ] Create initial ruleset

**Phase 2: Department (Week 3–4)**
- [ ] Deploy to finance team (10–20 users)
- [ ] Set up Git repository for rules
- [ ] Establish Growth Loop cadence
- [ ] Document standard workflows

**Phase 3: Enterprise (Month 2–3)**
- [ ] CI/CD pipeline integration
- [ ] Audit log storage & retention
- [ ] Multi-team collaboration model
- [ ] SLA definition & monitoring

**Phase 4: Scale (Month 3+)**
- [ ] Automated daily runs
- [ ] Dashboard/metrics reporting
- [ ] Cross-department rule sharing
- [ ] Rule pack marketplace / internal packs

![Adoption Pyramid](assets/finlang_adoption_pyramid.png)

---

## 📚 Related Documentation
- **install.md** — Getting started quickly  
- **flags.md** — All CLI flags & canonical formats  
- **i18n_examples.md** — Regional format recipes  
- **mapping_guide.md** — Align headers to the canonical schema  
- **amount_synthesis.md** — Debit/credit synthesis logic  
- **rule_language.md** — Write and test rules  
- **growth_loop_best_practices.md** — 3-step discovery workflow  
- **cli_reference.md** — Complete command reference  
- **benchmarks.md** — Performance data and methodology  

---

© FinLang Ltd. All rights reserved.
