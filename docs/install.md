# Installation Guide

This guide walks you through installing **FinLang** on Windows, macOS, and Linux — with optional fast CSV I/O and tips for common pitfalls.

---

## Requirements

- **Python**: 3.9 or newer (3.9–3.12 recommended)
- **OS**: Windows, macOS (Intel/Apple Silicon), or Linux
- **RAM**: Scales with your CSV size (as a rough guide, 1–2× file size)

> Tip: Use a **virtual environment** so FinLang and its dependencies stay isolated from your system Python.

---

## Quick Install (recommended)

```bash
pip install finlang
```

Verify:

```bash
finlang --help
```

### Optional: Faster I/O (pyarrow)

For faster CSV reads/writes, install the optional **fast I/O** extra (pulls in `pyarrow`):

```bash
pip install "finlang[fastio]"
```

If `pyarrow` isn’t available for your platform, FinLang still runs — it just uses standard I/O.

---

## Create a Virtual Environment (optional but recommended)

### macOS / Linux (bash/zsh)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install "finlang[fastio]"   # or: pip install finlang
```

### Windows (PowerShell)
```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install "finlang[fastio]"   # or: python -m pip install finlang
```

> If your shell complains about quotes, use: `pip install finlang[fastio]` (no quotes) on PowerShell/CMD.

---

## From Source (editable install)

```bash
git clone https://github.com/your-org/finlang.git
cd finlang
pip install -U pip
pip install -e .           # editable install for development
# optional fast I/O:
pip install ".[fastio]"
```

---

## Minimal Smoke Test

1) Create a tiny CSV (headers can be raw — FinLang will canonicalize columns using its bank map):
```csv
Date,Description,Debit,Credit
2025-01-01,Tesco Superstore,45.20,
2025-01-02,ACME Payroll,,1500.00
```

2) Run FinLang to produce a canonical/processed file:
```bash
finlang --input sample.csv --output categorized.csv --audit audit.json --audit-mode lite
```

You should get `categorized.csv` with canonical columns (`counterparty, amount, date, category, flags, memo`) and an `audit.json` file if changes were made.

---

## Upgrading / Uninstalling

- **Upgrade** to the latest version:
  ```bash
  pip install -U finlang
  ```

- **Uninstall**:
  ```bash
  pip uninstall finlang
  ```

---

## Platform Notes & Troubleshooting

### Windows
- If `pip` isn’t found, try `python -m pip` or `py -m pip`.
- If `finlang` isn’t found after install, ensure your **Scripts** folder is on PATH (e.g., `%USERPROFILE%\AppData\Local\Programs\Python\Python3x\Scripts\`). Activating a venv handles this automatically.
- Unicode output issues? Run `chcp 65001` in CMD to switch to UTF‑8.

### macOS
- On Apple Silicon (M1/M2/M3), use a **universal/arm64** Python (via `python.org` or Homebrew).
- If `pip` points to a different interpreter, prefer `python3 -m pip ...`.

### Linux
- Ensure `venv` is available: on Debian/Ubuntu `sudo apt-get install python3-venv`.
- If you see permission errors, use a venv or `pip install --user ...`.

### `pyarrow` / fast I/O
- If `pip install "finlang[fastio]"` fails on `pyarrow`, try updating pip first:
  ```bash
  pip install -U pip wheel setuptools
  pip install "finlang[fastio]"
  ```
- You can always install base FinLang (`pip install finlang`) and skip fast I/O — FinLang will **fall back** to standard CSV I/O.

### Command not found
- Make sure the environment is activated (you should see `(.venv)` in your prompt) or use full paths: `python -m finlang`.

---

## What’s Next?

- Read the **[CLI Reference](cli_reference.md)** for all flags and switches.
- Check **[Core Workflows](workflows.md)** to run the daily loop and the growth loop.
- Learn the **[Rule Language](rule_language.md)** to write powerful, auditable rules.
