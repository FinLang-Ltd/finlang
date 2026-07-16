# 📘 Mapping Guide
> **Applies to:** FinLang v0.6+
> **Status:** Stable
> **Last verified:** v0.8.1

---

## 🚀 Quick Start

**Most users don't need custom maps** — the default `bank.map.json` already covers major UK/EU banks.

**Only create a custom map if:**
- Your bank uses non-standard column names
- The default map doesn't recognize your headers

**Simple examples:**
```bash
# Default map (works for most banks)
finlang --input revolut.csv --output out.csv --rules rules.fin

# Custom map (for unusual headers)
finlang --input unusual_bank.csv --output out.csv --rules rules.fin --map custom.map.json
```

---

## 🎯 Overview

FinLang uses **mapping files** to translate the column names in your bank or accounting exports into FinLang's **canonical schema**.

Mapping ensures consistent interpretation of fields such as `date`, `amount`, and `counterparty`, even when your CSV headers differ (e.g., `TransactionDate`, `Value`, `Description`).

---

## 🔹 The Canonical Schema

The **canonical schema** is FinLang's normalized internal field set. After mapping, all data is represented using these standardized field names, regardless of what your original CSV headers were called. This ensures rules work consistently across different bank formats.

### Required Fields

These fields **must exist** after mapping (or be synthesized):

| Field | Purpose | Accepted Input | Notes |
|-------|---------|----------------|-------|
| `date` | Transaction date | `YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY` | Use `--dayfirst` for UK/EU formats. |
| `counterparty` | Payee/vendor/merchant | Any text string | Primary matching field for rules. |
| `amount` | Transaction value | Signed numeric (e.g., `-45.99`, `1234.56`) | Or synthesized from `debit`/`credit`. |

### Optional Fields

These fields are used if present in your input or set by rules:

| Field | Purpose | Accepted Input | Notes |
|-------|---------|----------------|-------|
| `memo` | Free text notes | Any text string | Matchable and settable in rules. |
| `category` | Category assignment | Any text string | Rules commonly assign this. Last rule wins. |
| `flags` | Tags for review/analytics | Any text string | Set via `+=` only. Multiple flags accumulate as space-separated values.<br />Flag values must be single tokens containing no whitespace (e.g., use `Large_Tx` instead of `Large Tx`) |
| `status` | Workflow state tracking | Any text string | e.g., `"Pending"`, `"Reviewed"`. Matchable and settable. |
| `exclude` | Marker for custom filtering | Boolean marker | Set via `exclude` or `exclude = true/false`. Mutable — later rules can override. No automatic row filtering. |

**Examples (rules using optional fields):**

```fin
rule "Mark high-value for review" {
  match:
    - amount in -999999..-1000
  set:
    - flags += "high_value"
    - category = "Review"
}

rule "Flag pending items" {
  match:
    - status == "Pending"
  set:
    - flags += "needs_attention"
}
```

📌 Extra columns not in the canonical list are **passed through unchanged** to the output.

---

## 🔹 Field Match/Set Reference

This table shows which canonical fields can be used in `match:` conditions and `set:` actions:

| Field | Source | Can Match? | Can Set? | Match Operators | Set Operators | Notes |
|-------|--------|------------|----------|-----------------|---------------|-------|
| `date` | Input CSV | ❌ No | ❌ No | — | — | Read-only. Not matchable in current grammar. |
| `amount` | Input CSV | ✅ Yes | ❌ No | `==`, `in` | — | Read-only. Use `in` for ranges (e.g., `amount in -100..-10`). |
| `counterparty` | Input CSV | ✅ Yes | ❌ No | `==`, `~` | — | Read-only. Use `~` for wildcards (e.g., `counterparty ~ "*TESCO*"`). |
| `memo` | Input CSV | ✅ Yes | ✅ Yes | `==`, `~` | `=`, `+=` | Free text field. |
| `category` | Engine | ✅ Yes | ✅ Yes | `==`, `~` | `=`, `+=` | Primary output field. Last matching rule wins. |
| `flags` | Engine | ✅ Yes | ✅ Yes (`+=` only) | `==`, `~` | `+=` only | Append-only. Direct assignment (`=`) not allowed. |
| `status` | Engine | ✅ Yes | ✅ Yes | `==`, `~` | `=`, `+=` | User-defined workflow state. |
| `exclude` | Engine | ❌ No | ✅ Yes | — | `=` | Boolean marker. Mutable — later rules can override. No automatic row filtering. |

**Set operators** (for `set:` actions on settable fields):
- `=` — direct assignment (e.g., `category = "Groceries"`)
- `+=` — append (e.g., `flags += "Review"`; **required** for `flags`, also supported on `category`, `status`, and `memo`)

**Key points:**
- **Read-only fields** (`date`, `amount`, `counterparty`) come from your input data and cannot be modified by rules.
- **Engine fields** (`category`, `flags`, `status`, `exclude`) are managed by the rule engine and persist across rule execution.
- **Matchable if previously set:** Fields like `category`, `flags`, and `status` can only be matched if they exist in the data (either from input or set by an earlier rule).

---

## 🗂️ The Bundled `bank.map.json` (Actual Shape)

FinLang ships with a default mapping file, **`bank.map.json`**, which already covers many common formats (e.g., Barclays, Revolut, Starling, Monzo).  
**Schema note:** The bundled file uses a nested object for `amount` with **`aliases`** (single-column amounts) and **`debit` / `credit`** for two-column exports.

📍 Source path:
```
src/finlang/mapping/bank.map.json
```

**Realistic example (matches the bundled file's structure):**
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
2. Compares them (**case-insensitively**) to these lists.  
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

**Step 1: Identify your CSV headers**
```bash
# View first line of your CSV
head -n 1 bank.csv
# Output: Transaction_Date,EUR_Value,Vendor_Name,Debit,Credit
```

**Step 2: Create your map file (choose one pattern below)**

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

**Step 3: Test with strict parsing**
```bash
finlang --input bank.csv --output out.csv \
  --map my_bank.map.json --rules rules.fin --strict-parse
```

If headers don't match, you'll get a clear, fatal error identifying missing requirements.

---

## 🧭 Mapping vs. Internationalization (I18n)

It's important to understand the difference between the **mapping file** and the **I18n flags**:

| Concept | Purpose | Example |
|---------|---------|---------|
| **Mapping (`--map`)** | Tells FinLang *which column* is the amount | `amount.aliases = ["Value_EUR"]` |
| **I18n Flags (`--decimal`, `--thousands`)** | Tell FinLang *how to read* the numbers in that column | `--decimal ,` parses `1.234,56` correctly |

You must use both to correctly process non-US/UK data.  
See [i18n_examples.md](i18n_examples.md) for regional recipes.

---

## 💰 Amount Synthesis

If no `amount` column exists after mapping, FinLang automatically **synthesizes** one from `debit` and `credit` columns.

This logic—including all edge cases for different bank formats—is detailed in [amount_synthesis.md](amount_synthesis.md).

---

## 🏦 Common Bank Export Formats

**Revolut (UK):**  
- Headers already match canonical schema.  
✅ No custom map needed.

**Barclays (UK):**  
- `"Transaction Date"` → `date`  
- `"Amount"` → `amount`  
✅ Default map works.

**German Banks (Sparkasse, Deutsche Bank):**  
- Often use `"Soll"` (debit) / `"Haben"` (credit)  
- Require custom map + I18n flags:

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

**Swiss Banks (UBS, Credit Suisse):**  
- May use apostrophe as thousands separator:
```bash
finlang --thousands "'" --decimal .
```

See [i18n_examples.md](i18n_examples.md) for complete regional recipes.

---

## 🌏 Non-Latin & International Header Mapping

The mapping layer works with **any Unicode headers** — not just Latin characters. The engine matches header strings exactly as specified in the map file. As long as the file encoding is correct (`--encoding utf-8` or `--encoding auto`), headers in any script are supported.

**Verified examples:**

### 🇯🇵 Japanese
```json
{
  "date": ["日付"],
  "amount": { "aliases": ["金額"] },
  "counterparty": ["取引先"],
  "memo": ["摘要"]
}
```
```bash
finlang --input jp_export.csv --map jp.map.json --encoding utf-8 --rules rules.fin
```

### 🇮🇳 Hindi
```json
{
  "date": ["तारीख"],
  "amount": { "aliases": ["राशि"] },
  "counterparty": ["प्रतिपक्ष"],
  "memo": ["विवरण"]
}
```
```bash
finlang --input india_export.csv --map india.map.json --encoding utf-8 --dayfirst --rules rules.fin
```

### 🇫🇷 French
```json
{
  "date": ["date"],
  "amount": { "aliases": ["montant"] },
  "counterparty": ["contrepartie"],
  "memo": ["libellé"]
}
```
```bash
finlang --input fr_export.csv --map france.map.json --decimal "," --thousands "." --dayfirst --rules rules.fin
```

### 🇮🇹 Italian
```json
{
  "date": ["data"],
  "amount": { "aliases": ["importo"] },
  "counterparty": ["controparte"],
  "memo": ["descrizione"]
}
```
```bash
finlang --input it_export.csv --map italy.map.json --decimal "," --thousands "." --dayfirst --rules rules.fin
```

**Note:** Wildcard matching in `.fin` rules also works with non-Latin characters: `counterparty ~ "*シェル*"` (Japanese) and `counterparty ~ "*बैंक*"` (Hindi) are both valid and tested.

Mapping keys are matched **case-insensitively**, so both `description` and `Description` work equally well.

If your bank uses unusual or non-ASCII header names, ensure the file encoding is declared properly (e.g., `--encoding utf-8` or `--encoding auto`).

---

---

## 🧩 Case Insensitivity

Mapping keys are matched **case-insensitively**, so both `description` and `Description` work equally well.

If your bank uses unusual or non-ASCII header names, ensure the file encoding is declared properly (e.g., `--encoding utf-8` or `--encoding auto`).

---

## 🧰 Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| **"Missing canonical field: amount"** | CSV headers don't match mapping | Create custom map with your amount column name or debit/credit names |
| **"Malformed numeric value"** | Locale mismatch (e.g., `1.234,56`) | Add `--decimal , --thousands .` |
| **"Multiple matches for column"** | Duplicate header aliases | Check for conflicting keys in custom map |
| **Output amounts wrong sign** | Debit/Credit logic unclear | See [amount_synthesis.md](amount_synthesis.md) |
| **Headers not recognized** | Encoding issues | Try `--encoding auto` or `--encoding utf-8-sig` |
| **Case-sensitive matching fails** | Non-ASCII characters | Ensure map file is UTF-8 encoded |

**Debug Tip:** Use `--strict-parse` to fail fast with clear error messages.

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
finlang --input new_bank.csv --output test.csv \
  --map custom.map.json --rules rules.fin --strict-parse
```
5. **Verify output with audit mode**
```bash
finlang --input new_bank.csv --output test.csv \
  --map custom.map.json --rules rules.fin \
  --audit test_audit.json --audit-mode full
```
6. **Check audit log for correct field interpretation**

---

## 🔹 Cross-References

- [flags.md](flags.md) — Master list of all flags and canonical formats  
- [i18n_examples.md](i18n_examples.md) — Regional recipes for parsing data  
- [amount_synthesis.md](amount_synthesis.md) — Detailed logic for debit/credit synthesis  
- [rule_language.md](rule_language.md) — How mapped fields are used in rules  
- [cli_reference.md](cli_reference.md) — All CLI flags for supplying maps  
- [workflows.md](workflows.md) — How mapping fits into daily runs  
- [faq.md](faq.md) — Common mapping and amount-related questions

---

© FinLang Ltd
