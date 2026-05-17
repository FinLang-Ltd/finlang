# 🧩 Installation Guide
> **Applies to:** FinLang v0.7+
> **Status:** Active
> **Last verified:** v0.7.9

FinLang can be installed on Windows, macOS, or Linux using `pip`.  
This guide walks through installation, quick testing, and key configuration notes introduced in **v0.6.4.post1 (GA)**.

---

## 🚀 Quick Install

FinLang requires **Python 3.10–3.14**.

```bash
pip install finlang
```

Or with Fast I/O acceleration (recommended for large datasets):
```bash
pip install "finlang[fastio]"
```

Or with the HTTP API wrapper (FastAPI + uvicorn):
```bash
pip install "finlang[api]"
finlang-api    # binds 127.0.0.1:8000 — interactive docs at /docs
```
*(Thin FastAPI wrapper over the CLI. See [api.md](api.md).)*

Verify installation:
```bash
finlang --help
```

📌 **FinLang v0.6.4+** automatically detects common encodings (e.g., `latin-1`) and delimiters (`;`, `,`, `\t`).  
For complete control over regional formats, see the **[i18n Examples](i18n_examples.md)**.

---

## 🧪 Minimal Smoke Test

Create a small test CSV:

```csv
date,amount,description
2025-01-10,19.99,Test transaction
```

Then run:
```bash
finlang --input test.csv --output out.csv --rules rules.fin --audit audit.json
```

FinLang will categorize transactions using your rule file and generate an audit log.

---

### 🌍 Note on Internationalization (I18n)

The above smoke test works for US/UK-style CSVs.  
If your CSV uses European number or date formats, you must add locale flags:

**Example (EU data):**
```bash
finlang --input sample.csv --output out.csv --rules rules.fin \
  --decimal "," --thousands "." --dayfirst
```
For full regional recipes, see **[i18n Examples](i18n_examples.md)**.

---

## ⚙️ Developer (Editable) Install

Clone and install in editable mode for local development:

```bash
git clone https://github.com/finlang-ltd/finlang.git
cd finlang
pip install -e .
```

---

## 💡 Platform Notes & Troubleshooting

### Internationalization & Parsing

- **Problem:** Amounts are wrong (e.g., `199,99` → `19999.0`)  
  **Fix:** Add `--decimal ","` to specify a comma decimal separator.

- **Problem:** Dates parsed incorrectly (e.g., 01/12 → Jan 12 instead of 1 Dec)  
  **Fix:** Add `--dayfirst` to interpret as `DD/MM/YYYY`.

- **Problem:** Garbled text (e.g., `cafÃ©`)  
  **Fix:** File uses non‑UTF‑8 encoding. Add `--encoding auto` to detect automatically.

See **[i18n Examples](i18n_examples.md)** for more.

---

### Windows Users

If you see Unicode errors, set UTF‑8 mode:
```cmd
chcp 65001
```

Then re‑run your FinLang command.

---

### macOS / Linux Users

If `finlang` is not found, check that your Python Scripts directory is on PATH:
```bash
python3 -m pip install --upgrade finlang
```
or run directly:
```bash
python3 -m finlang --help
```

---

## 🔄 Upgrade or Uninstall

```bash
pip install --upgrade finlang
pip uninstall finlang
```

---

## 📘 What’s Next?

- **[Flags](flags.md)** – Canonical formats for all CLI arguments  
- **[i18n Examples](i18n_examples.md)** – Regional command recipes (US, UK, EU)  
- **[Growth Loop Best Practices](growth_loop_best_practices.md)** – Learn `discover` and `suggest` workflows  
- **[CLI Reference](cli_reference.md)** – Detailed flag and command reference  
- **[Rule Language](rule_language.md)** – Write deterministic `.fin` rules  
- **[Workflows](workflows.md)** – Run FinLang day‑to‑day
- **[Verify](verify.md)** – `--verify` / `--verify-full` integrity verification (SHA-256 fingerprinting + field comparison)
- **[Reconciliation](reconciliation.md)** – `--reconcile` ML validation layer with HTML audit report
- **[API](api.md)** – FastAPI wrapper (`pip install finlang[api]`, `finlang-api`)
