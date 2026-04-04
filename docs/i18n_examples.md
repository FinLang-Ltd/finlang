# 🌍 Internationalization Examples
> **Applies to:** FinLang v0.6+  
> **Status:** Reference  
> **Last verified:** v0.7.7

FinLang supports locale-specific date and number formats for global datasets.

---

## 🔹 Common CLI Flags

| Flag | Purpose |
|------|----------|
| `--encoding auto` | Detect UTF-8 vs Latin-1 automatically. |
| `--decimal ,` | Sets decimal char (e.g., ','). **Fixes "199,99" → 199.99.** |
| `--thousands .` | Defines thousands separator (e.g., '.') for EU formats. |
| `--dayfirst` | Interpret DD/MM/YYYY where dates are ambiguous. |
| `--date-format "%d/%m/%Y"` | Manually specify format if needed. |

---

## 🔹 Regional Examples

### 🇺🇸 United States
```bash
# (No flags needed; this is the default)
```
**Why:** US exports use `MM/DD/YYYY` and `.` decimal with `,` thousands — FinLang’s default assumptions. Day-first is not used.

---

### 🇬🇧 United Kingdom
```bash
finlang --dayfirst
```
**Why:** UK uses `DD/MM/YYYY` with the same punctuation as US. `--dayfirst` disambiguates dates like `01/12/2025` (1 Dec).

---

### 🇫🇷 France / 🇩🇪 Germany
```bash
finlang --decimal "," --thousands "." --dayfirst --encoding auto
```
**Why:** EU exports commonly use `,` decimal, `.` thousands, and `DD.MM.YYYY` or ISO `YYYY-MM-DD`. The parser often infers day‑first from dots, but adding `--dayfirst` is **explicit and deterministic** across files.

---

### 🇨🇭 Switzerland
```bash
finlang --decimal "." --thousands "'" --dayfirst
```
**Why:** Swiss formats frequently use **apostrophe `'`** as thousands (e.g., `1'234.56`) and **DD.MM.YYYY** for dates. Explicit `--dayfirst` ensures consistent behaviour across banks.

---

### 🇮🇹 Italy
```bash
finlang --decimal "," --thousands "." --dayfirst --encoding auto --map italian_bank.map.json
```
**Why:** Italian exports use the same EU number formatting as France/Germany (`,` decimal, `.` thousands, semicolon delimiter). Column headers are in Italian — use a custom map to resolve them.

**Example map (`italian_bank.map.json`):**
```json
{
  "date": ["data"],
  "amount": { "aliases": ["importo"] },
  "counterparty": ["controparte"],
  "memo": ["descrizione"]
}
```

---

### 🇯🇵 Japan
```bash
finlang --encoding utf-8 --map japanese_bank.map.json
```
**Why:** Japanese exports typically use UTF-8 encoding, `YYYY-MM-DD` dates, `.` decimal (no special flags needed), and `¥` currency symbols. The `¥` symbol is stripped automatically by the parser. Column headers are in Japanese — use a custom map.

**Example map (`japanese_bank.map.json`):**
```json
{
  "date": ["日付"],
  "amount": { "aliases": ["金額"] },
  "counterparty": ["取引先"],
  "memo": ["摘要"]
}
```

**Note:** Japanese wildcard matching works in `.fin` rules: `counterparty ~ "*シェル*"` matches counterparties containing シェル (Shell).

---

### 🇮🇳 India
```bash
finlang --dayfirst --encoding utf-8 --map indian_bank.map.json
```
**Why:** Indian exports typically use `DD/MM/YYYY` dates and `₹` currency symbols. The `₹` symbol is stripped automatically. Column headers may be in Hindi or English — use a custom map for Hindi headers.

**Example map (`indian_bank.map.json`):**
```json
{
  "date": ["तारीख"],
  "amount": { "aliases": ["राशि"] },
  "counterparty": ["प्रतिपक्ष"],
  "memo": ["विवरण"]
}
```

**Note:** Hindi wildcard matching works in `.fin` rules: `counterparty ~ "*बैंक*"` matches counterparties containing बैंक (Bank).

**⚠️ Known limitation:** Indian **lakhs notation** (e.g., `1,25,000` instead of `125,000`) is not currently supported. The non-standard thousands grouping causes parsing errors. Amounts without lakhs formatting work correctly. This is tracked for a future release.

---

## 🔹 Supported Currency Symbols

The parser automatically strips the following currency symbols from amount fields:

| Symbol | Currency | Region |
|--------|----------|--------|
| `£` | Pound Sterling | UK |
| `€` | Euro | EU |
| `$` | Dollar | US / multiple |
| `¥` | Yen | Japan |
| `₹` | Rupee | India |

No CLI flag is needed — currency stripping is automatic. Non-breaking spaces (`\u00A0`, `\u202F`) commonly found in EU-formatted amounts are also stripped.

---

## 🧪 Quick Test Your Settings

Create a `test.csv` with the following content:
```csv
date,amount
01/12/2025,"1.234,56"
```

Then run:
```bash
finlang --input test.csv --output test_out.csv   --decimal "," --thousands "." --dayfirst   --rules empty.fin --headless
```
**Expected:** Amount parses to `1234.56`, date is **1 December 2025**.

---

## ⚠️ Mixed Formats in One File

**Problem:** File contains both US and EU formatted numbers.

**Solution:** Standardize before import, or split into separate runs:
```bash
# Process US format rows
finlang --decimal "." --thousands "," --input us_subset.csv ...

# Process EU format rows
finlang --decimal "," --thousands "." --dayfirst --input eu_subset.csv ...
```
FinLang processes with **one locale per run** to ensure determinism.

---

## 🔧 Troubleshooting

| Symptom | Example | Likely Fix |
|----------|---------|------------|
| Amounts 10× too large | 1,234.56 → 123456 | Swap `--decimal` and `--thousands`. Always quote values. |
| Dates wrong by 11 months | 01/12 → Dec 1 instead of 1 Jan | Add `--dayfirst`. |
| Garbled accents | café → cafÃ© | Use `--encoding utf-8` or `auto`. |
| Negative amounts positive | -50 shows as 50 | Check CR/DR columns with `--audit-mode full`. |

---

## 📖 Related Documentation

- [CLI Reference](cli_reference.md) – Complete flag listing  
- [FAQ](faq.md) – Common questions  
- [Benchmarks](benchmarks.md) – Performance data  
- [Workflows](workflows.md) – Integration patterns

© FinLang Ltd
