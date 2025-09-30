# 📖 Mapping Guide
*Applies to FinLang v0.6.x*

This guide explains how FinLang maps your raw bank export headers into the canonical column names required by the engine. It also covers customization, troubleshooting, validation, and enterprise practices.

---

## 🔹 Purpose of Mapping

Different banks export different CSV headers. For example:  
- Some use `Payee`, others use `Vendor`, others use `Description`.  
- Some export `Debit`/`Credit` columns, others provide a single `Amount` field.

FinLang uses a JSON mapping file to normalize these variations into canonical fields:  
`date`, `counterparty`, `amount`, `debit`, `credit`, `memo`, `category`, `flags`.

---

## 🔹 The Bundled `bank.map.json`

FinLang ships with a **default `bank.map.json`** that covers a wide range of common English-language headers used by UK, US, and European banks. You can find this file in the distribution and override it with your own via the `--map` flag.

**Core Required Fields (must exist after mapping):**

  - `date`
  - `counterparty`
  - `amount`  
    (this may be present directly, or synthesized from `debit` + `credit`)

Without these three, FinLang will abort with a schema error.

**Optional Canonical Fields (understood if present):**

  - `memo` → free text (notes, transaction type, etc.)
  - `category` → assigned by rules
  - `flags` → append-only tags (`flags += "Retail"`)
  - `status` → can be set/used in rules
  - `exclude` → marks rows to be dropped from further processing

**Excerpt from the bundled `bank.map.json`:**

```json
{
  "date": [
    "date",
    "transaction_date",
    "txn_date",
    "posted_date",
    "value_date"
  ],
  "counterparty": [
    "description",
    "payee",
    "vendor",
    "merchant",
    "narrative",
    "details"
  ],
  "memo": [
    "type",
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

This bundled file ensures that most common exports will "just work" without customization.

📌 Note: If you don’t specify `--map`, FinLang automatically uses the bundled `bank.map.json`. You only need `--map` if you want to override with your own custom file.

---

## 🔹 How to Use and Customize Mappings

There are two primary ways to handle mapping:

### 1. Use the Default (No Action Required)

If your CSV headers are common (e.g., `Date`, `Description`, `Debit`, `Credit`), you don't need to do anything. FinLang will automatically use its bundled `bank.map.json`.

### 2. Build Your Own Custom Map

If you have a bank export with unusual headers, you can provide your own mapping file.

- **Step 1: Create a JSON file** (e.g., `my_custom_map.json`).  
- **Step 2: Add your mappings.** For each canonical field, create a key and provide a list of the header names from your CSV that should map to it.

**Example `my_custom_map.json` for a non-standard export:**

```json
{
  "date": ["TXN_DATE"],
  "counterparty": ["Beneficiary_Name"],
  "memo": ["Transaction_Ref"],
  "amount": {
    "debit": "Outgoing_Amt",
    "credit": "Incoming_Amt"
  }
}
```

- **Step 3: Tell FinLang to use it.** Use the `--map` flag in the command line:

```bash
finlang --input my_bank.csv --output categorized.csv --rules my_rules.fin --map my_custom_map.json
```

This will override the default `bank.map.json` with your custom logic.

---

## 🔹 Advanced Notes

- **Language & Character Support**  
  - FinLang is designed to be language-agnostic. The mapping file and rule files should be saved with **UTF-8 encoding** to support international character sets in your transaction data.  
  - The engine normalizes text for matching by stripping accents (e.g., `CAFÉ` becomes `CAFE`) to ensure robust, accent-insensitive comparisons.

- **Case Insensitivity**  
  The mapping process is case-insensitive. A header of `Description` in your CSV will match the `description` key in your mapping file.

- **Extra Columns**  
  If your input file has **more columns than the canonical model**, they are simply passed through unchanged. FinLang only interprets the canonical fields listed above (required: `date`, `counterparty`, `amount`; optional: `memo`, `category`, `flags`, `status`, `exclude`). All other columns are passed through unchanged. All other fields remain in the output CSV for your reference but are not affected by rules.

- **Limitations**  
  The mapping is a simple header-to-field translation. It does not perform complex data transformations or cell-level manipulations. That is the job of the rule engine.

- **Precedence of Amount vs Debit/Credit**  
  If both `amount` and debit/credit exist, `amount` is always trusted. Debit/credit are fallback only.

- **Amount Synthesis Rule**  
  If no `amount` column exists, FinLang synthesizes it with:  
  ```
  amount = abs(credit) - abs(debit)
  ```

**Examples:**

| Debit | Credit | Synthesized `amount` |
|-------|--------|-----------------------|
| 12.34 |        | `-12.34`              |
|       | 9.99   | `+9.99`               |
| 12.00 | 5.00   | `-7.00` (`5 - 12`)    |
|       |        | `0`                   |

📌 See [`rule_language.md`](rule_language.md) for how rules are applied once data has been mapped into the canonical schema.

---

## 🔹 Troubleshooting

**Issue:** “My CSV fails to load: unknown header `vendor_name`.”  
- ✅ Add `"vendor_name"` under `counterparty` in your map.  
- ✅ Re-run with `--map my.map.json`.

**Issue:** “My amounts look wrong.”  
- ✅ Check whether your file has both debit/credit and amount columns. Remember: `amount` always takes precedence.  
- ✅ Verify the synthesis rule is understood:  
  ```
  amount = abs(credit) - abs(debit)
  ```

**Issue:** “Multiple possible counterparty fields exist.”  
- ✅ Only the first populated column is used. Consider editing your map to set explicit priority.

**Issue:** “Flags or categories disappeared.”  
- ✅ Check you didn’t accidentally overwrite canonical column names in your custom map.  
- ✅ Use `--audit audit.json --audit-mode full` to verify changes.

---

## 🔹 Validating a Map

You can validate your custom map against a CSV to ensure headers match.

**Linux/macOS:**

```bash
finlang --input transactions.csv --map my.map.json --output /dev/null --audit-mode none --headless
```

**Windows PowerShell:**

```powershell
finlang --input transactions.csv --map my.map.json --output NUL --audit-mode none --headless
```

If the map is invalid, FinLang will exit non-zero and explain which headers failed.

---

## 🔹 Enterprise Considerations

- **Shared maps:** Place mapping files in version control alongside rules for team consistency.  
- **Multiple banks:** Maintain separate maps per institution (e.g. `hsbc.map.json`, `barclays.map.json`).  
- **Auditing:** Always validate maps before production runs. Consider using CI/CD validation (see [Rule Language](rule_language.md)).  
- **Portability:** When onboarding new datasets, review `bank.map.json` and extend rather than overwrite to preserve defaults.

---

## 🔹 Cross-References

- [Rule Language](rule_language.md) → how mapped fields are used in rules  
- [CLI Reference](cli_reference.md) → all CLI flags for supplying maps  
- [Workflows](workflows.md) → daily run + growth loop integration  
- [FAQ](faq.md) → common mapping and amount-related questions

---

© FinLang Ltd
