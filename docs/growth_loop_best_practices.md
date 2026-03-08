# 🔁 Growth Loop Best Practices
> **Applies to:** FinLang v0.6.4+  
> **Status:** Recommended  
> **Last verified:** v0.7.5

The **Growth Loop** is FinLang's continuous-improvement cycle:  
**Discover → Suggest → Merge → Audit → Refine.**

---

## 🔁 The Growth Loop Cycle

```
   ┌──────────────────────────────────────────┐
   │                                          │
   │  1. DISCOVER      2. SUGGEST            │
   │  Uncategorized → Draft Rules            │
   │       ↓               ↓                  │
   │  4. ITERATE  ←  3. MERGE & AUDIT        │
   │  Measure      ← Apply + Validate        │
   │                                          │
   └──────────────────────────────────────────┘
```

---

## 1️⃣ Discover

**Input:** `categorized.csv` (output from a previous `finlang` run)  
**Output:** `suggestions.csv` (candidate counterparties for new rules)

Surface recurring uncategorized counterparties:

```bash
finlang-discover --input categorized.csv --candidates suggestions.csv \
  --all-candidates all_candidates.csv \
  --strict-parse --encoding auto --min-count 5 --top-k 50 \
  --since-date 2025-01-01
```

> **Date filter:** `--since-date` expects **ISO `YYYY-MM-DD`** (e.g., `2025-01-01`).  
> Other forms may parse, but **ISO is the only guaranteed format**. See **[flags.md](flags.md)**.

✅ Tips  
- Use `--since-date` to restrict to recent months.  
- Add `--fastio` for PyArrow acceleration.

---

## 2️⃣ Suggest

**Input:** `suggestions.csv` (from Discover) + `my_rules.fin` (your existing rules)  
**Output:** `draft_rules.fin` (new rules to review)

Generate conservative draft rules:

```bash
finlang-suggest --input suggestions.csv --output draft_rules.fin \
  --rules my_rules.fin \
  --emit-match exact --category "Review"
```

> **Flag clarification:**
> - `--rules` — Your existing ruleset; used to **deduplicate** (won't suggest patterns already covered)
> - `--append` / `--overwrite` — Controls what happens to the `--output` file (see below)
> - `--emit-match exact` — Generates precise 1:1 patterns for production safety

### Output File Behavior

| Scenario | Result |
|----------|--------|
| File doesn't exist | Creates new file |
| File exists, no flags | **Appends** (default) |
| File exists + `--append` | Appends (explicit) |
| File exists + `--overwrite` | Overwrites/replaces |

**Example: Accumulating drafts across multiple runs**
```bash
# Run 1: Q1 candidates → creates draft_rules.fin
finlang-suggest --input q1_candidates.csv --output draft_rules.fin \
  --rules my_rules.fin --emit-match exact --category "Review"

# Run 2: Q2 candidates → appends to same file
finlang-suggest --input q2_candidates.csv --output draft_rules.fin \
  --rules my_rules.fin --emit-match exact --category "Review" --append

# Run 3: Fresh start → overwrites with only Q3
finlang-suggest --input q3_candidates.csv --output draft_rules.fin \
  --rules my_rules.fin --emit-match exact --category "Review" --overwrite
```

✅ Tips  
- Always pass `--rules` to avoid suggesting duplicates of patterns you already have.
- Review drafts manually before merging.

### ⚠️ Important: Fuzzy Mode Limitations
The default `--emit-match fuzzy` may generate broad patterns (e.g., `*PLC*`, `*LLC*`). Prefer `exact` in production.

---

## 3️⃣ Merge and Audit

**Input:** `draft_rules.fin` (reviewed) + `my_rules.fin` (existing)  
**Output:** Updated `my_rules.fin`

After reviewing the suggested rules, merge them into your main ruleset:

**Linux/macOS/WSL**
```bash
cat draft_rules.fin >> my_rules.fin
```

**Windows (PowerShell)**
```powershell
Get-Content draft_rules.fin | Add-Content my_rules.fin
```

**Windows (CMD)**
```cmd
type draft_rules.fin >> my_rules.fin
```

Then re-run with full audit to validate:
```bash
finlang --input transactions.csv --output categorized.csv \
  --rules my_rules.fin --include-pack retail,sanity \
  --audit audit.json --audit-mode full --fastio
```

Audit output confirms every rule's effect.  
Re-run `finlang-discover` to measure coverage improvement.

---

## 4️⃣ Iterate and Measure

| Metric | Baseline | After Loop | Change |
|--------|----------|------------|--------|
| Uncategorised % | 41 % | 17 % | -58 % |
| Coverage gain (5 runs) | – | 97.8 % avg | ✅ Sustained |

---

## ⏱️ Time Investment Per Loop

| Phase | First Time | Subsequent Loops |
|-------|------------|------------------|
| Discover | 5 min | 2 min |
| Review suggestions | 15–30 min | 10 min |
| Merge & test | 10 min | 5 min |
| Audit & validate | 5 min | 2 min |
| **Total** | **35–50 min** | **~20 min** |

**ROI:** Each loop typically improves coverage by **5–10%**.

---

## 5️⃣ Team Workflow Tips

- Store rules and maps in Git.  
- Use CI/CD validation (`finlang --headless --audit-mode none`).  
- Enforce code-review before merging pack updates.

---

## 📖 Related Documentation

- [Workflows](workflows.md) — Daily run & enterprise patterns  
- [CLI Reference](cli_reference.md) — All flags & switches  
- [i18n Examples](i18n_examples.md) — Regional settings  
- [Rule Language](rule_language.md) — DSL reference  
- [Flags](flags.md) — Canonical formats

© FinLang Ltd
