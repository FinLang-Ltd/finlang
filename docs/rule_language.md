# 📖 Rule Language Reference
*Applies to FinLang v0.6.x (Stable since v0.6.0) — Rev 2.1*

> **Note:** This DSL is stable. All v0.6.x releases maintain backward compatibility.  
> Breaking changes (if any) will only occur in v0.7.0+.

---

## 🎯 Quick Start

**Simplest possible rule:**
```fin
rule "Groceries" {
  match:
    - counterparty ~ "*TESCO*"
  set:
    - category = "Groceries"
}
```

**What this does:**
- Finds any transaction with "TESCO" in the counterparty name
- Sets its category to "Groceries"

That's it! Everything else builds on this pattern.

---

## 🔹 Rule Structure

A FinLang `.fin` file is a deterministic set of rules, each with two blocks:
- `match:` → defines which transactions the rule applies to
- `set:` → defines what to change when the rule applies

```fin
rule "Transport: Uber" {
  match:
    - counterparty ~ "*UBER*"
  set:
    - category = "Transport"
    - flags += "reviewed"
}
```

---

## 🔹 Match Conditions

Conditions check fields against values. **All conditions must match** (AND logic).

> **Important:** If you need OR logic, write separate rules.

### Supported Operators
- `==` : Exact match
- `~` : Wildcard match (`*pattern*`)
- `in` : Range or list inclusion

**Example (AND logic):**
```fin
match:
  - counterparty ~ "*UBER*"
  - amount in -100..0
# Both must be true
```

**For OR logic, use separate rules:**
```fin
rule "Transport: Uber" {
  match:
    - counterparty ~ "*UBER*"
  set:
    - category = "Transport"
}

rule "Transport: Lyft" {
  match:
    - counterparty ~ "*LYFT*"
  set:
    - category = "Transport"
}
```

---

## 🔹 Amount Field Logic

FinLang automatically synthesizes the `amount` field if your export provides `debit` and `credit` separately:
```
amount = abs(credit) - abs(debit)
```

⚠️ **Locale Matters:** If your bank uses comma decimals (e.g., `12,34`), use the `--decimal ,` flag or amounts may parse incorrectly.  
See [i18n_examples.md](i18n_examples.md).

---

## 🔹 Best Practices

**Prefer wildcards for robustness**

**Example:**
❌ **Too specific:** `counterparty == "TESCO STORE 1234 LONDON"`  
✅ **Better:** `counterparty ~ "*TESCO*"`  
✅ **Even better:** `counterparty ~ "TESCO*"`

---

## 🔹 Advanced Examples (Stacked Rules)

```fin
# 1. Broad catch
rule "Amazon (generic)" {
  match:
    - counterparty ~ "*AMZN*"
  set:
    - category = "Shopping"
}

# 2. Narrow refinement
rule "Amazon Prime" {
  match:
    - counterparty ~ "*AMZNPRIME*"
  set:
    - category = "Subscriptions"
    - flags += "prime"
}
```

### Why This Pattern Works
1. **Rule 1 casts a wide net** – captures all Amazon transactions.  
2. **Rule 2 refines specific cases** – recognizes subscriptions.  
3. **Flags accumulate** – helps track multiple attributes.  
4. **Later rules overwrite** earlier category values deterministically.

Use case: Start broad, refine as you learn patterns in your data.

---

## 🔹 Catch-Alls & Flagging

**When to use catch-all rules:**
- ✅ Flagging high-value uncategorized transactions
- ✅ Identifying potential duplicates
- ✅ Highlighting unusual patterns
- ✅ Creating safety nets for compliance

**When NOT to use:**
- ❌ As a substitute for proper categorization
- ❌ For every small transaction (adds noise)

**Example:**
```fin
rule "Review: Uncategorised > £1000" {
  match:
    - category == ""
    - amount <= -1000
  set:
    - flags += "high_value"
    - category = "Review"
}
```

---

## ⚡ Performance Characteristics

- **Ruleset-invariant** → Rule complexity has minimal performance impact  
  *Example:* 10 rules vs 1000 rules ≈ 5% runtime difference
- **Deterministic** → Same inputs → same outputs, guaranteed
- **Linear scaling** → Performance scales predictably with dataset size  
  *Example:* 100K rows ≈ 2.5 s, 5 M rows ≈ 208 s (~24 K rows/sec)

See [benchmarks.md](benchmarks.md) for details.

---

## 🧪 CI/CD Integration

You can safely validate and regression-test rulesets in pipelines.

**Example (PowerShell):**
```powershell
finlang --rules production.fin --input test.csv --output test_out.csv --strict-parse
Compare-Object (Get-Content test_out.csv) (Get-Content expected_out.csv)
```

### Exit Code Validation
All examples return `0` on success, non-zero on failure.

**Example CI/CD script (bash):**
```bash
#!/bin/bash
set -e

# Validate syntax
finlang --rules production.fin --input test.csv --output /dev/null --headless

# Regression test
finlang --rules production.fin --input test.csv --output test_out.csv --headless

# Compare to golden file
diff test_out.csv expected_out.csv
echo "✅ All tests passed"
```

---

## ⚠️ Common Mistakes

| Mistake | Problem | Solution |
|----------|----------|----------|
| `flags = "value"` | Overwrites all flags | Use `flags += "value"` |
| Missing quotes | Syntax error | Always quote strings: `"value"` |
| Wrong operator | No match | Use `~` for wildcards, `==` for exact |
| Order matters | Wrong rule wins | Put specific rules first |
| No audit testing | Silent errors | Use `--audit-mode full` during validation |

---

## 📘 Quick Reference

| Keyword | Description |
|----------|-------------|
| `match` | Conditions (all must be true) |
| `set` | Assignments (category, flags, notes, etc.) |
| `flags +=` | Append mode (non-destructive) |
| `in` | Range test or list inclusion |
| `~` | Wildcard operator |
| `==` | Exact match |
| `#` | Comment line |

---

© FinLang Ltd — v0.6.x DSL Reference (Rev 2.1)
