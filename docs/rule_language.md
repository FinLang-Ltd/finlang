# 📖 Rule Language Reference

FinLang uses a simple, declarative DSL (`.fin` files) to define categorization logic. Rules match transactions by conditions, then apply actions to set categories, flags, and other fields.

---

## 🔹 Rule Structure

A rule has:
- A **name** (quoted string).
- A **block** with two sections: `match:` and `set:`.

```fin
rule "GROCERIES: Tesco" {
  match:
    - counterparty ~ "*TESCO*"
  set:
    - category = "Groceries"
    - flags += "auto"
}
```

---

## 🔹 Match Conditions

Conditions check fields against values. Multiple conditions combine with **AND**.

### Supported Operators
- `==` → exact match  
- `~` → wildcard match (`*` for substring, prefix, suffix)  
- `in` → numeric range (amount only)

### Examples
```fin
# Exact text match
counterparty == "AMAZON EU"

# Wildcard: contains "UBER"
counterparty ~ "*UBER*"

# Wildcard: starts with "NETFLIX"
counterparty ~ "NETFLIX*"

# Numeric range: amount between -20 and -5
amount in -20..-5
```

---

## 🔹 Fields Available

You can match on:
- `counterparty` → normalized payee/vendor name
- `amount` → numeric transaction amount
- `category` → current category (useful for refinement rules)
- `flags` → existing flags
- `status` → optional workflow status field
- `memo` → notes or free-text descriptions

---

## 🔹 Set Actions

Actions define what happens when a rule matches.

- `category = "..."` → overwrite category
- `memo = "..."` → overwrite memo
- `status = "..."` → overwrite status
- `exclude = true/false` → mark row for exclusion
- `flags += "..."` → **append** a flag (safe default)

⚠️ `flags = "..."` (overwrite) is **not allowed** — this prevents accidental loss of existing flags. Always use `+=`.

---

## 🔹 Amount Field Logic

The `amount` field is critical for many rules. FinLang uses a clear, deterministic process to resolve the final transaction amount.

**Resolution Order:**

1. **If an `amount` column exists:** It is always trusted as the primary source.  
2. **If `amount` is missing:** FinLang automatically *synthesizes* it from `debit` and `credit` columns using the following abs-safe formula:
   ```
   amount = abs(credit) - abs(debit)
   ```
   - **Debit-only:** results in `-abs(debit)`  
   - **Credit-only:** results in `+abs(credit)`  
   - **Both empty:** results in `0`

This logic ensures that even if a bank export has inconsistent debit/credit signs, the resulting `amount` is always calculated correctly.

**Examples:**

| Debit | Credit | Resulting `amount` |
| :---: | :----: | :-----------------: |
| 12.34 |        | `-12.34`            |
|       | 9.99   | `+9.99`             |
| 12.00 | 5.00   | `-7.00` (`5 - 12`)  |

---

## 🔹 Best Practices

✅ **Specific first, general later**  
Rules are applied in order of precedence:  
1. Your personal rules (`my_rules.fin`).  
2. Then included packs (`--include-pack`).  
Later rules can override earlier ones.

✅ **Use audit mode**  
Always review `audit.json` in **full audit mode** when testing new rules. It shows exactly which cells changed.

✅ **Prefer wildcards for robustness**  
Instead of exact strings (`"TESCO 1234"`), use patterns (`*TESCO*`) to catch statement variations.

✅ **Use flags for metadata**  
Flags (`recurring`, `subscription`, `fx`) allow multiple labels without overriding categories.

✅ **Keep rules atomic**  
One rule = one clear intent. Easier to debug and audit.

---

## 🔹 Advanced Example: Rule Stacking & Refinement

Rules are applied in order, allowing you to create layers of logic. A common pattern is to set a general category first, then use a more specific rule to refine it.

Because later rules can override earlier ones, you can even match on a category set by a previous rule.

```fin
# --- Rule 1: General Vendor (runs first) ---
# Broadly categorizes all Amazon transactions as "Shopping".
rule "VENDOR: Amazon" {
  match:
    - counterparty ~ "*AMAZON*"
  set:
    - category = "Shopping"
}

# --- Rule 2: Specific Refinement (runs after Rule 1) ---
# Catches Amazon Prime subscriptions by matching on the category
# set by the previous rule AND the transaction amount.
rule "SUBSCRIPTION: Amazon Prime" {
  match:
    - category == "Shopping"
    - counterparty ~ "*AMAZON*PRIME*"
  set:
    - category = "Subscriptions"
    - flags += "Subscription"
    - flags += "Recurring"
}
```

### Demonstration of Stacked Processing

**Input Transaction:**

| counterparty       | amount | category | flags |
|--------------------|:------:|:--------:|:-----:|
| AMAZON PRIME UK    | -10.99 |          |       |

**After Rule 1 (“VENDOR: Amazon”):**

| counterparty       | amount |    category    | flags |
|--------------------|:------:|:--------------:|:-----:|
| AMAZON PRIME UK    | -10.99 | **Shopping**   |       |

**After Rule 2 (“SUBSCRIPTION: Amazon Prime”):**

| counterparty       | amount |    category     |            flags             |
|--------------------|:------:|:---------------:|:----------------------------:|
| AMAZON PRIME UK    | -10.99 | **Subscriptions** | **Subscription, Recurring** |

The specific rule refines the general one — a common and powerful pattern.

---

## 🔹 Example Rule Pack

```fin
rule "SUBSCRIPTION: Netflix" {
  match:
    - counterparty ~ "NETFLIX*"
  set:
    - category = "Entertainment"
    - flags += "subscription"
}

rule "TRANSPORT: Uber Rides" {
  match:
    - counterparty ~ "*UBER*"
    - amount in -100..0
  set:
    - category = "Transport"
    - flags += "auto"
}
```

---

## 🔹 Catch-Alls & Flagging

Rules don’t just assign categories — they can also be used as *safety nets* to highlight transactions that need manual review. These patterns are especially useful for enterprise teams to surface edge cases.

```fin
# --- CATCH-ALLS & FLAGGING ---

# Flags any uncategorized debit larger than £500
rule "Flag: Large Unidentified Debit" {
  match:
    - amount in -500..-0.01
    - category == ""
  set:
    - flags += "Review: Large Unidentified"
}

# Flags small Square payments that may indicate duplicates
rule "Flag: Potential Duplicate" {
  match:
    - counterparty ~ "*SQ *"
    - amount in -20..-0.01
  set:
    - flags += "Review: Potential Duplicate"
}
```

These catch-all rules act as guardrails, ensuring no high-value or suspicious-looking transaction is silently ignored.

---

## 🔹 Quick Reference

- **Operators:** `==`, `~`, `in`  
- **Set fields:** `category`, `memo`, `status`, `exclude`, `flags +=`  
- **Rule precedence:** personal rules → packs  
- **Audit mode:** always use for testing

---

## ⚡ Performance Characteristics

- **Ruleset-invariant** → Rule complexity has minimal performance impact  
- **Deterministic** → Same inputs → same outputs, guaranteed  
- **Linear scaling** → Performance scales predictably with data size (see `benchmarks.md` for detailed plots)  

---

## 🏢 Enterprise Rule Management

- **Version control** → Store `rules.fin` in Git for full audit trails  
- **Testing framework** → Validate rules against sample data pre-deployment  
- **Change management** → Review and approve modifications before merging into production rulesets  

---

## 🔄 CI/CD Integration Examples

FinLang rules can be validated and regression-tested in automated pipelines. These examples show how to integrate across different operating systems.

### **Linux / macOS (bash/zsh)**

```bash
# Validate rules syntax before deployment (output discarded)
finlang --rules my_rules.fin --input sample.csv --output /dev/null --audit-mode none --headless

# Apply rules on sample data for regression testing
finlang --rules my_rules.fin --input sample.csv --output sample_out.csv --audit-mode lite --headless
```

### **Windows PowerShell**

```powershell
# Validate rules syntax before deployment (output discarded)
finlang --rules my_rules.fin --input sample.csv --output NUL --audit-mode none --headless

# Apply rules on sample data for regression testing
finlang --rules my_rules.fin --input sample.csv --output sample_out.csv --audit-mode lite --headless
```

### **Windows CMD**

```cmd
:: Validate rules syntax before deployment (output discarded)
finlang --rules my_rules.fin --input sample.csv --output NUL --audit-mode none --headless

:: Apply rules on sample data for regression testing
finlang --rules my_rules.fin --input sample.csv --output sample_out.csv --audit-mode lite --headless
```

These commands enable CI/CD systems to:  
- Fail builds if rule syntax is invalid.  
- Detect regressions by comparing `sample_out.csv` to a committed expected version.  

---

📌 See [`workflows.md`](workflows.md) for how rules integrate into the Growth Loop and daily workflows.
