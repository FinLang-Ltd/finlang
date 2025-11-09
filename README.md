# FinLang — The Financial Rules Engine

**Deterministic. Auditable. Global.**  
Compliant with the **EU AI Act (effective August 2026)**.

[![PyPI version](https://badge.fury.io/py/finlang.svg)](https://badge.fury.io/py/finlang)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/FinLang-Ltd/finlang)
[![Python versions](https://img.shields.io/pypi/pyversions/finlang.svg)](https://pypi.org/project/finlang/)

---

## 🌍 Overview

**FinLang** is a domain-specific language (DSL) and high-performance CLI engine for financial transaction processing.  
It replaces opaque machine-learning categorization with **transparent, deterministic rules** — delivering explainability, auditability, and global compatibility.

> **Built for compliance.**  
> Designed to meet the **EU AI Act** “high-risk AI” obligations — deterministic, explainable, and fully auditable.

---

## 📝 The FinLang DSL

FinLang rules are human-readable, Git-friendly, and designed for precision.  
The engine processes rules top-to-bottom; the last matching rule sets the category, while flags accumulate.

```fin
# Example: Basic categorization and flagging
rule "GROCERIES: Tesco" {
  match:
    - counterparty ~ "*TESCO*"
  set:
    - category = "Groceries"
    - flags += "Supermarket"
}

# Example: Numeric range and exact match
rule "TRAVEL: High Value Flight" {
  match:
    - counterparty == "BRITISH AIRWAYS"
    - amount in -5000.00 .. -500.00
  set:
    - category = "Travel"
    - flags += "HighValue"
}
```

---

## ⚙️ Key Features (v0.6.4)

| Feature | Description |
|:--|:--|
| **Deterministic DSL** | Human-readable `.fin` rules language — explainable logic, Git-friendly. |
| **High-Performance Engine** | Vectorized core (Pandas + NumPy + PyArrow) — 24K+ rows/sec validated throughput. |
| **Growth Loop** | Automated Discover → Suggest → Categorize workflow — 97.8% success on addressable patterns. |
| **Global I18n Support** | US/UK/EU/Commonwealth formats, £ € $ ¥ ₹ stripping, localized decimals/dates/delimiters. |
| **Audit Trail System** | Every decision logged (before/after state diffs); stateless for reproducibility. |
| **CR/DR Semantics** | Case-insensitive CR/DR, accounting negatives `(123.45)`, trailing minus `123.45-`. |
| **Amount Synthesis** | Auto-computes `amount = abs(credit) – abs(debit)` across 9 edge cases. |
| **Strict Parsing** | Locale-aware normalization with configurable thresholds (`--strict-parse`). |
| **Flag Integrity** | Append-only (`flags +=`) with deterministic deduplication. |

---

## 📦 Installation

**Requirements:** Python 3.10 or later

**From PyPI (Recommended):**
```bash
pip install finlang
```

**With Fast I/O (PyArrow):**
```bash
pip install "finlang[fastio]"
```
*(Enables `--fastio` for accelerated CSV I/O.)*

**From Source (Development):**
```bash
git clone https://github.com/FinLang-Ltd/finlang.git
cd finlang
pip install -e .[fastio]
```

---

## 🚀 Quick Start — The 5-Step Growth Loop

1️⃣ **Initial Categorization**
```bash
finlang --input transactions.csv --output baseline.csv   --rules my_rules.fin --include-pack retail,transport
```

2️⃣ **Discover Gaps**
```bash
finlang-discover --input baseline.csv   --candidates candidates.csv --all-candidates all_candidates.csv   --min-count 5
```

3️⃣ **Suggest Rules (Exact Mode Recommended)**
```bash
finlang-suggest --input candidates.csv --output suggested_rules.fin   --rules my_rules.fin --emit-match exact
```

4️⃣ **Merge and Re-run**
```bash
cat my_rules.fin suggested_rules.fin > merged.fin
finlang --input transactions.csv --output improved.csv   --rules merged.fin --include-pack retail,transport
```

✅ **Expected Result:** 5–10% coverage improvement; zero duplicates in `exact` mode.

---

## 📊 Performance Benchmarks (v0.6.4 Validated)

Measured with `--audit-mode none` (max throughput).

| Dataset | Rules | Time (s) | Rows/sec | Notes |
|:--|:--|:--:|:--:|:--|
| 100 K (UK Synthetic) | 121 | 2.54 | **39 370 ✅** | Baseline |
| 100 K (after Growth Loop) | 764 | 4.96 | **20 161 ✅** | +6.3× rules → ≈ 2× slower |
| **5M × 50 cols** | — | 208.31 | **24 003 ✅** | High volume validation |

>  **Audit Overhead:** Enabling `--audit-mode lite/full` **reduces throughput by ≈ 38%** due to diff calculation; provides full decision provenance.  
> See [`docs/benchmarks.md`](docs/benchmarks.md) for details.

---

## 🌐 Internationalization Matrix

| Region | Example Number | Date Order | CLI Flags |
|:--|:--:|:--:|:--|
| 🇺🇸 US / 🇨🇦 Canada | 1,234.56 | MM/DD | (defaults) |
| 🇬🇧 UK / 🇦🇺 Commonwealth | 1,234.56 | DD/MM | `--dayfirst` |
| 🇪🇺 Continental Europe | 1.234,56 | DD/MM | `--decimal "," --thousands "." --dayfirst` |
| 🇨🇭 Switzerland | 1'234.56 | DD/MM | `--thousands "'" --dayfirst` |

**Auto-Detection and Normalization:** BOM-safe UTF-8 encodings, `, ; | \t` delimiters, and automatic currency symbol stripping.

---

## 🧠 The Growth Loop Explained

> **Discover → Suggest → Categorize → Repeat**

FinLang’s Growth Loop accelerates rule creation through data-driven discovery.

- **Discover** uncategorized counterparties  
- **Suggest** new rules in seconds (1:1 mapping in exact mode)  
- **Merge + Re-run** for incremental coverage gains  
- **Validated Result:** 97.8% success on addressable patterns  
- **ROI:** 8.8 transactions categorized per new rule  

📄 See: [`docs/growth_loop_best_practices.md`](docs/growth_loop_best_practices.md)

---

## 🧾 Known Limitations (v0.6.4)

- ⚠️ `--emit-match fuzzy` (default) uses naive tokenization and may produce broad patterns (e.g. `*PLC*`).   
  → Use `--emit-match exact` for production workflows (improvements planned for v0.6.5).  
- ⚠️ Hyphenated/apostrophe names may affect fuzzy matching (< 1% impact).  
- ⚠️ No support for non-Gregorian calendars or non-Western numerals.

---

## 📘 Documentation

- [`docs/release_notes_v0_6_4.md`](docs/release_notes_v0_6_4.md)  
- [`docs/benchmarks.md`](docs/benchmarks.md)  
- [`docs/growth_loop_best_practices.md`](docs/growth_loop_best_practices.md)  
- [`docs/amount_synthesis.md`](docs/amount_synthesis.md)  
- [`docs/i18n_examples.md`](docs/i18n_examples.md)  
- [`docs/stateless_processing.md`](docs/stateless_processing.md)

**Command-line help:**
```bash
finlang --help
finlang-discover --help
finlang-suggest --help
```

---

## 🧩 Example CLI Usage

```bash
finlang --input bank.csv --output categorized.csv   --rules examples/rules.demo.fin   --include-pack retail,transport,subs   --fastio --audit audit_log.json --audit-mode lite
```

---

## 📜 License & Commercial Use

FinLang is open source under the **GNU Affero General Public License (AGPL-3.0)**.  
Commercial licenses and enterprise support are available via **FinLang Ltd**.

📧 info@finlang.io  
🌐 https://finlang.io

------

## Contributing
Contributions are welcome! Before submitting a PR, please review and accept our
[Contributor Licence Agreement (CLA)](docs/legal/CLA.md).

---

## 🏁 Version Summary

| Component | Version | Status |
|:--|:--|:--|
| Core Engine | v0.6.4 | ✅ Production-Ready |
| CLI Suite | v0.6.4 | ✅ Validated |
| Discover/Suggest | v0.6.4 | ✅ 97.8% accuracy |
| Docs | v0.6.4 | ✅ Complete |
| Next Milestone | v0.6.5 | 🚧 Fuzzy tokenizer & audit optimization |
