# 🔁 Growth Loop Best Practices
*Applies to FinLang v0.6.4.post1 (Rev 2)*

The **Growth Loop** is FinLang’s continuous-improvement cycle:  
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

Surface recurring uncategorized counterparties:

```bash
finlang-discover --input categorized.csv --candidates suggestions.csv   --strict-parse --encoding auto --min-count 5 --top-k 50   --since-date 2025-01-01
```

> **Date filter:** `--since-date` expects **ISO `YYYY-MM-DD`** (e.g., `2025-01-01`).  
> Other forms may parse, but **ISO is the only guaranteed format**. See **[flags.md](flags.md)**.

✅ Tips  
- Use `--since-date` to restrict to recent months.  
- Add `--fastio` for PyArrow acceleration.

---

## 2️⃣ Suggest

Generate conservative draft rules:

```bash
finlang-suggest --input suggestions.csv --output draft_rules.fin   --emit-match exact --category "Review" --append
```

✅ Tips  
- `--emit-match exact` generates precise 1:1 patterns for production safety.  
- Review drafts manually before merging.

## ⚠️ Important: Fuzzy Mode Limitations
The default `--emit-match fuzzy` may generate broad patterns (e.g., `*PLC*`, `*LLC*`). Prefer `exact` in production.

---

## 3️⃣ Merge and Audit

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

Then run:
```bash
finlang --input transactions.csv --output categorized.csv   --rules my_rules.fin --include-pack retail,sanity   --audit audit.json --audit-mode full --fastio
```

Audit output confirms every rule’s effect.  
Re-run `finlang-discover` to measure coverage improvement.

---

## 4️⃣ Iterate and Measure

| Metric | Baseline | After Loop | Change |
|--------|-----------|------------|--------|
| Uncategorised % | 41 %  | 17 %  | -58 % |
| Coverage gain (5 runs) | –  | 97.8 % avg | ✅ Sustained |

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

- [Workflows](workflows.md) – Daily run & enterprise patterns  
- [CLI Reference](cli_reference.md) – All flags & switches  
- [i18n Examples](i18n_examples.md) – Regional settings  
- [Rule Language](rule_language.md) – DSL reference  
- [Flags](flags.md) – Canonical formats

© FinLang Ltd
