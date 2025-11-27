# 📘 Mapping Guide
*Applies to FinLang v0.6.4.post1 (GA Rev 3.4 — Final Clarified)*

---

## 🚀 Quick Start

**Most users don’t need custom maps** — the default `bank.map.json` already covers major UK/EU banks.

**Only create a custom map if:**
- Your bank uses non-standard column names
- The default map doesn’t recognize your headers

**Simple examples:**
```bash
# Default map (works for most banks)
finlang --input revolut.csv --output out.csv --rules rules.fin

# Custom map (for unusual headers)
finlang --input unusual_bank.csv --output out.csv --rules rules.fin --map custom.map.json
```

---

## 🎯 Overview

FinLang uses **mapping files** to translate the column names in your bank or accounting exports into FinLang’s **canonical schema**.

Mapping ensures consistent interpretation of fields such as `date`, `amount`, and `counterparty`, even when your CSV headers differ (e.g., `TransactionDate`, `Value`, `Description`).

---

## 🔹 The Canonical Schema

**Required fields (must exist after mapping or synthesis):**
- `date` — transaction date (ISO recommended in output)
- `counterparty` — payee/vendor/description
- `amount` — signed numeric; **or** `debit`/`credit` from which `amount` is synthesized

**Optional fields (used if present):**

| Field | Purpose / Effect | Typical Source | Notes |
|------|-------------------|----------------|-------|
| `memo` | Free text notes shown verbatim in output | “Notes”, “Reference”, “Type” | Interpreted; matchable and settable. |
| `category` | Display/category field set by rules | (rarely present in input) | Rules commonly assign/overwrite this |
| `flags` | Append‑only tags for review/analytics | (rare) | **Use** `flags += "Retail"`; non‑destructive |
| `status` | State you can set/test in rules | (rare) | E.g., `status = "reconciled"` then filter later |
| `exclude` | Usable in rules as a custom boolean marker. **Informational only** in v0.6.4; FinLang does not skip rows automatically. | (n/a) | Future releases may add native exclusion behavior |

**Examples (rules using optional fields):**
```fin
rule "Mark high‑value for review" {
  match:
    - amount in -999999..-1000
  set:
    - flags += "high_value"
    - category = "Review"
}
```

📌 Extra columns not in the canonical list are **passed through unchanged** to the output.

---

## 🗂️ The Bundled `bank.map.json` (Actual Shape)

FinLang ships with a default mapping file, **`bank.map.json`**, which already covers many common formats (e.g., Barclays, Revolut, Starling, Monzo).  
**Schema note:** The bundled file uses a nested object for `amount` with **`aliases`** (single-column amounts) and **`debit` / `credit`** for two-column exports.

📍 Source path:
```
src/finlang/mapping/bank.map.json
```

**Realistic example (matches the bundled file’s structure):**
```json
{
  "date": [
    "date",
    "Date",
    "transaction_date",
    "txn_date",
    "posted_date",
    "post_date",
    "value_date",
    "booking_date",
    "timestamp",
    "transaction date",
    "posted date",
    "value date",
    "booking date",
    "Completed Date",
    "Started Date"
  ],
  "counterparty": [
    "description",
    "Description",
    "payee",
    "vendor",
    "merchant",
    "narrative",
    "details"
  ],
  "memo": [
    "type",
    "Type",
    "notes",
    "note",
    "memo"
  ],
  "amount": {
    "aliases": ["amount", "value", "transaction_amount", "amt"],
    "debit": "debit",
    "credit": "credit"
  }
}
```

**How it works:**
1. FinLang reads your CSV headers.  
2. Compares them (**case‑insensitively**) to these lists.  
3. Maps matched columns to canonical names.  
4. For `amount`:
   - If a header matches any in `amount.aliases` → that column is the **amount**.
   - Else, if both `debit` and `credit` headers are present → FinLang **synthesizes** `amount`.
   - Else → FinLang errors (missing required columns).

---

## ⚙️ Using Custom Maps

Provide your own JSON mapping file with the `--map` flag:

```bash
finlang --input bank.csv --output out.csv --rules my_rules.fin --map my_bank.map.json
```

📌 **Important:** Providing a custom map **replaces** the default bundled map entirely.  
It does **not merge** — only the specified mappings will be used.

📌 **Tip:** Run with `--strict-parse` to validate header alignment early.

---

## 📝 Creating a Custom Map

**Step 1: Identify your CSV headers**
```bash
# View first line of your CSV
head -n 1 bank.csv
# Output: Transaction_Date,EUR_Value,Vendor_Name,Debit,Credit
```

**Step 2: Create your map file (choose one pattern below)**

**(A) Single amount column**
```json
{
  "date": ["Transaction_Date"],
  "counterparty": ["Vendor_Name"],
  "amount": {
    "aliases": ["EUR_Value"]
  }
}
```

**(B) Separate debit / credit columns**
```json
{
  "date": ["Transaction_Date"],
  "counterparty": ["Vendor_Name"],
  "amount": {
    "debit": "Debit",
    "credit": "Credit"
  }
}
```

**Step 3: Test with strict parsing**
```bash
finlang --input bank.csv --output out.csv   --map my_bank.map.json --rules rules.fin --strict-parse
```

If headers don’t match, you’ll get a clear, fatal error identifying missing requirements.

---

## 🧭 Mapping vs. Internationalization (I18n)

It’s important to understand the difference between the **mapping file** and the **I18n flags**:

| Concept | Purpose | Example |
|----------|----------|----------|
| **Mapping (`--map`)** | Tells FinLang *which column* is the amount | `amount.aliases = ["Value_EUR"]` |
| **I18n Flags (`--decimal`, `--thousands`)** | Tell FinLang *how to read* the numbers in that column | `--decimal ,` parses `1.234,56` correctly |

You must use both to correctly process non‑US/UK data.  
See [i18n_examples.md](i18n_examples.md) for regional recipes.

---

## 💰 Amount Synthesis

If no `amount` column exists after mapping, FinLang automatically **synthesizes** one from `debit` and `credit` columns.

This logic—including all edge cases for different bank formats—is detailed in [amount_synthesis.md](amount_synthesis.md).

---

## 🏦 Common Bank Export Formats

**Revolut (UK):**  
- Headers already match canonical schema.  
✅ No custom map needed.

**Barclays (UK):**  
- `"Transaction Date"` → `date`  
- `"Amount"` → `amount`  
✅ Default map works.

**German Banks (Sparkasse, Deutsche Bank):**  
- Often use `"Soll"` (debit) / `"Haben"` (credit)  
- Require custom map + I18n flags:

```json
{
  "amount": {
    "debit": "Soll",
    "credit": "Haben"
  }
}
```
```bash
finlang --map german_bank.map.json --decimal , --thousands .
```

**Swiss Banks (UBS, Credit Suisse):**  
- May use apostrophe as thousands separator:
```bash
finlang --thousands "'" --decimal .
```

See [i18n_examples.md](i18n_examples.md) for complete regional recipes.

---

## 🧩 Case Insensitivity

Mapping keys are matched **case‑insensitively**, so both `description` and `Description` work equally well.

If your bank uses unusual or non‑ASCII header names, ensure the file encoding is declared properly (e.g., `--encoding utf‑8` or `--encoding auto`).

---

## 🧰 Troubleshooting

| Symptom | Cause | Fix |
|----------|--------|-----|
| **“Missing canonical field: amount”** | CSV headers don’t match mapping | Create custom map with your amount column name or debit/credit names |
| **“Malformed numeric value”** | Locale mismatch (e.g., `1.234,56`) | Add `--decimal , --thousands .` |
| **“Multiple matches for column”** | Duplicate header aliases | Check for conflicting keys in custom map |
| **Output amounts wrong sign** | Debit/Credit logic unclear | See [amount_synthesis.md](amount_synthesis.md) |
| **Headers not recognized** | Encoding issues | Try `--encoding auto` or `--encoding utf‑8‑sig` |
| **Case‑sensitive matching fails** | Non‑ASCII characters | Ensure map file is UTF‑8 encoded |

**Debug Tip:** Use `--strict-parse` to fail fast with clear error messages.

---

## ✅ Validation Workflow

**Recommended process for new bank formats:**

1. **Test with default map first**
```bash
finlang --input new_bank.csv --output test.csv --rules rules.fin --strict-parse
```
2. **If it fails, check the error message**
```
FATAL: Missing required columns after mapping: ['amount'].
       Provide a mapping JSON via --map or preprocess your CSV first.
```
3. **Create minimal custom map**
```json
{
  "amount": {
    "aliases": ["EUR_Value"]
  }
}
```
4. **Test again with custom map**
```bash
finlang --input new_bank.csv --output test.csv   --map custom.map.json --rules rules.fin --strict-parse
```
5. **Verify output with audit mode**
```bash
finlang --input new_bank.csv --output test.csv   --map custom.map.json --rules rules.fin   --audit test_audit.json --audit-mode full
```
6. **Check audit log for correct field interpretation**

---

## 🔹 Cross‑References

- [flags.md](flags.md) – Master list of all flags and canonical formats  
- [i18n_examples.md](i18n_examples.md) – Regional recipes for parsing data  
- [amount_synthesis.md](amount_synthesis.md) – Detailed logic for debit/credit synthesis  
- [rule_language.md](rule_language.md) – How mapped fields are used in rules  
- [cli_reference.md](cli_reference.md) – All CLI flags for supplying maps  
- [workflows.md](workflows.md) – How mapping fits into daily runs  
- [faq.md](faq.md) – Common mapping and amount‑related questions

---

© FinLang Ltd — v0.6.4.post1 (GA Rev 3.4 — Final Clarified)
