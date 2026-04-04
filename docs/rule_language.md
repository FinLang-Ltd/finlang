# 📖 Rule Language Reference
> **Applies to:** FinLang v0.6+  
> **Status:** Stable  
> **Last verified:** v0.7.7

> **Note:** This DSL is stable. All v0.6.x and v0.7.x releases maintain backward compatibility.  
> Breaking changes (if any) will be clearly documented in release notes.

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

## 🔹 Field Match/Set Reference

This table shows which fields can be used in `match:` conditions and `set:` actions:

| Field | Source | Can Match? | Can Set? | Match Operators | Set Operators | Notes |
|-------|--------|------------|----------|-----------------|---------------|-------|
| `date` | Input CSV | ❌ No | ❌ No | — | — | Read-only. Not matchable in current grammar. |
| `amount` | Input CSV | ✅ Yes | ❌ No | `==`, `in` | — | Read-only. Use `in` for ranges (e.g., `amount in -100..-10`). |
| `counterparty` | Input CSV | ✅ Yes | ❌ No | `==`, `~` | — | Read-only. Use `~` for wildcards (e.g., `counterparty ~ "*TESCO*"`). |
| `memo` | Input CSV | ✅ Yes | ✅ Yes | `==`, `~` | `=`, `+=` | Free text field. |
| `category` | Engine | ✅ Yes | ✅ Yes | `==`, `~` | `=`, `+=` | Primary output field. Last matching rule wins. |
| `flags` | Engine | ✅ Yes | ✅ Yes (`+=` only) | `==`, `~` | `+=` only | Append-only. Direct assignment (`=`) not allowed. Flag values must be single tokens (no whitespace); use underscores or camelCase (e.g. `Large_Tx`, `LargeTx`). |
| `status` | Engine | ✅ Yes | ✅ Yes | `==`, `~` | `=`, `+=` | User-defined workflow state. |
| `exclude` | Engine | ❌ No | ✅ Yes | — | `=` | Boolean marker. Set via `exclude` or `exclude = true/false`. Mutable — later rules can override. No automatic row filtering. |

**Set operators** (for `set:` actions on settable fields):
- `=` — direct assignment (e.g., `category = "Groceries"`)
- `+=` — append (e.g., `flags += "Review"`; **required** for `flags`, also supported on `category`, `status`, and `memo`)

**Key points:**
- **Read-only fields** (`date`, `amount`, `counterparty`) come from your input data and cannot be modified by rules.
- **Engine fields** (`category`, `flags`, `status`, `exclude`) are managed by the rule engine.
- **`currency` is not supported** in any match or set operation.

---

## 🔹 When Do Engine Fields Exist?

Fields like `category`, `flags`, and `status` are **not part of the default bank mapping**. They only exist in your data if:

1. **Present in your input CSV** — Some exports include a `category` column.
2. **Created by a previous FinLang run** — When you process a file, FinLang adds these columns to the output.
3. **Set by an earlier rule in the same run** — Rules execute top-to-bottom; later rules can match fields set by earlier rules.

**Practical implications:**

| Scenario | Can you match `category`? |
|----------|---------------------------|
| First run on raw bank export | ❌ No (column doesn't exist yet) |
| Re-processing FinLang output | ✅ Yes (column exists from previous run) |
| Later rule in same file | ✅ Yes (if earlier rule set it) |

**Example: Chained rules in the same file**
```fin
# Rule 1: Sets category
rule "Retail: Tesco" {
  match:
    - counterparty ~ "*TESCO*"
  set:
    - category = "Groceries"
}

# Rule 2: Matches category set by Rule 1
rule "Flag all groceries" {
  match:
    - category == "Groceries"
  set:
    - flags += "food_expense"
}
```

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

## 🔹 Match Operators

Conditions check fields against values. **All conditions must match** (AND logic).

> **Important:** If you need OR logic, write separate rules.

### The `==` Operator (Exact Match)

Case-insensitive exact match for text fields, numeric equality for `amount`.

```fin
match:
  - counterparty == "TESCO STORES LTD"    # Must match exactly
  - amount == -45.99                       # Numeric equality
```

### The `~` Operator (Wildcard Match)

The `~` operator enables **wildcard matching** using `*` as a glob pattern. All matches are **case-insensitive**.

| Pattern | Behavior | Example Matches |
|---------|----------|-----------------|
| `~ "Tesco"` | **Exact match** (same as `==`) | `"Tesco"` only |
| `~ "Tesco*"` | Prefix match | `"Tesco"`, `"Tesco Store 123"` |
| `~ "*Tesco"` | Suffix match | `"Tesco"`, `"Big Tesco"` |
| `~ "*Tesco*"` | Contains/substring | `"Tesco"`, `"Big Tesco Store"` |
| `~ "A*B*C"` | Complex pattern | `"ABC"`, `"A123B456C"` |

> ⚠️ **Important:** Without wildcards, `~` behaves exactly like `==`. If you want substring matching, use `~ "*TESCO*"` not `~ "TESCO"`.

### The `in` Operator (Numeric Range)

For the `amount` field only. Matches values within an inclusive range.

```fin
match:
  - amount in -100..-10      # Debits between £10 and £100
  - amount in 50..500        # Credits between £50 and £500
```

### AND Logic (Multiple Conditions)

All conditions in a `match:` block must be true:

```fin
match:
  - counterparty ~ "*UBER*"
  - amount in -100..0
# Both must be true for the rule to fire
```

### OR Logic (Separate Rules)

For OR logic, write separate rules:

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

Bank descriptions vary. The same merchant might appear as:
- `"TESCO STORES 1234 LONDON"`
- `"TESCO EXPRESS EDINBURGH"`
- `"TESCO.COM ONLINE"`

**Example:**
❌ **Too specific:** `counterparty == "TESCO STORES 1234 LONDON"`  
✅ **Better:** `counterparty ~ "*TESCO*"`  
✅ **Even better:** `counterparty ~ "TESCO*"` (anchored prefix)

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
1. **Rule 1 casts a wide net** — captures all Amazon transactions.  
2. **Rule 2 refines specific cases** — recognizes subscriptions.  
3. **Flags accumulate** — multiple flags build up as space-separated values.  
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
    - amount in -999999..-1000
  set:
    - flags += "high_value"
    - category = "Review"
}
```

---

## 🔹 Exclude (Boolean Marker)

The `exclude` field is a **mutable boolean marker** that flags rows for downstream filtering. It does not freeze rows or prevent further rule processing — later rules can still modify excluded rows.

### Basic Syntax

```fin
# Shorthand (sets exclude = true)
rule "Exclude internal transfers" {
  match:
    - counterparty ~ "*INTERNAL*"
  set:
    - exclude
}

# Explicit true/false
rule "Exclude Amazon" {
  match:
    - counterparty ~ "*AMAZON*"
  set:
    - exclude = true
}
```

### Exception Pattern (Blacklist then Whitelist)

Because exclude is mutable, later rules can reverse it. This enables blacklist/whitelist patterns:

```fin
rule "Blacklist Amazon" {
  match:
    - counterparty ~ "*AMAZON*"
  set:
    - exclude
}

rule "Whitelist high-value Amazon" {
  match:
    - counterparty ~ "*AMAZON*"
    - amount in 5000..999999
  set:
    - exclude = false
    - flags += "Capital_Expenditure"
}
```

**Result:** All Amazon transactions are excluded *except* those over £5,000, which are un-excluded and flagged for capital expenditure review. The audit trail captures the full chain.

### Behaviour Notes

- **Column appears only when needed.** If no rule in your ruleset references `exclude`, the column is omitted from output (clean schema).
- **Growth loop safe.** Exclude values from a previous pass survive as proper booleans in subsequent passes.
- **Audit tracked.** Exclude changes appear in the audit log as boolean diffs (`false` → `true` or `true` → `false`).
- **No automatic row dropping.** FinLang marks rows; your downstream pipeline decides what to do with them.

---

## ⚡ Performance Characteristics

- **Ruleset-invariant** → Rule complexity has minimal performance impact  
  *Example:* 10 rules vs 1000 rules ≈ 5% runtime difference
- **Deterministic** → Same inputs → same outputs, guaranteed
- **Linear scaling** → Performance scales predictably with dataset size  
  *Example:* 100K rows ≈ 2.5 s, 5 M rows ≈ 188 s (~27 K rows/sec)

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
|---------|---------|----------|
| `flags = "value"` | Overwrites all flags | Use `flags += "value"` |
| `flags += "Large Tx"` | Whitespace splits into two flags | Use `flags += "Large_Tx"` or `flags += "LargeTx"` |
| `~ "TESCO"` without wildcards | Exact match, not contains | Use `~ "*TESCO*"` for substring |
| Missing quotes | Syntax error | Always quote strings: `"value"` |
| Wrong operator | No match | Use `~` for wildcards, `==` for exact |
| Order matters | Wrong rule wins | Put specific rules after broad rules |
| No audit testing | Silent errors | Use `--audit-mode full` during validation |

---

## 📘 Quick Reference

| Keyword | Description |
|---------|-------------|
| `match` | Conditions (all must be true) |
| `set` | Assignments (category, flags, memo, etc.) |
| `flags +=` | Append mode (non-destructive) |
| `in` | Numeric range (amount only) |
| `~` | Wildcard operator (use `*` for patterns) |
| `==` | Exact match |
| `#` | Comment line |

---

## 🔹 Cross-References

- [mapping_guide.md](mapping_guide.md) — Canonical schema and field reference
- [flags.md](flags.md) — All CLI flags and canonical formats
- [i18n_examples.md](i18n_examples.md) — Regional format recipes
- [workflows.md](workflows.md) — Daily run and growth loop patterns
- [benchmarks.md](benchmarks.md) — Performance data

---

© FinLang Ltd
