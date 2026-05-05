# FinLang — The Financial Rules Engine

**Deterministic. Auditable. Global.**  
Designed for explainable processing in regulated environments.

[![PyPI version](https://badge.fury.io/py/finlang.svg)](https://badge.fury.io/py/finlang)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/FinLang-Ltd/finlang)
[![Python versions](https://img.shields.io/pypi/pyversions/finlang.svg)](https://pypi.org/project/finlang/)

---

## 🌐 Overview

**FinLang** is a domain-specific language (DSL) and high-performance CLI engine for financial transaction processing.  
It replaces opaque machine-learning categorization with **transparent, deterministic rules** — delivering explainability, auditability, and global compatibility.

> **Built for audit-friendly logic and deterministic processing.**  
> A deterministic alternative where explainability and reproducibility matter.

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

## ⚙️ Key Features (v0.7.7)

| Feature | Description |
|:--|:--|
| **Deterministic DSL** | Human-readable `.fin` rules language — explainable logic, Git-friendly. |
| **High-Performance Engine** | Vectorized core (Pandas + NumPy + PyArrow) — **~217K rows/sec FastIO** validated throughput on the integrity harness. |
| **Dual Backend** | Standard (`Engine: c`) or FastIO (`Engine: pyarrow`) with automatic fallback. |
| **Growth Loop** | Automated Discover → Suggest → Categorize workflow — 97.8% success on addressable patterns. |
| **Global I18n Support** | US/UK/EU/Commonwealth formats, £ € $ ¥ ₹ stripping, localized decimals/dates/delimiters. |
| **Audit Trail System** | Every decision logged (before/after state diffs); stateless for reproducibility. |
| **Exclude Marker** | Boolean `exclude` column — rule-driven, auditable, supports blacklist/whitelist exception patterns. |
| **CR/DR Semantics** | Case-insensitive CR/DR (with or without space), accounting negatives `(123.45)`, trailing minus `123.45-`. v0.7.7 fixes a latent bug on no-space CR/DR formats. |
| **Amount Synthesis** | Auto-computes `amount = abs(credit) – abs(debit)` across 9 edge cases. |
| **Strict Parsing** | Locale-aware normalization with configurable thresholds (`--strict-parse`). |
| **Flag Integrity** | Append-only (`flags +=`) with deterministic deduplication. |
| **Integrity Verification** | Built-in `--verify` and `--verify-full` — SHA-256 fingerprinting of immutable fields with optional artifact output. |

---

## 📦 Installation

**Requirements:** Python 3.10—3.14

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
finlang --input transactions.csv --output baseline.csv \
  --rules my_rules.fin --include-pack retail,transport
```

2️⃣ **Discover Gaps**
```bash
finlang-discover --input baseline.csv \
  --candidates candidates.csv --all-candidates all_candidates.csv \
  --min-count 5
```

3️⃣ **Suggest Rules (Exact Mode Recommended)**
```bash
finlang-suggest --input candidates.csv --output suggested_rules.fin \
  --rules my_rules.fin --emit-match exact
```

4️⃣ **Merge and Re-run**
```bash
cat my_rules.fin suggested_rules.fin > merged.fin
finlang --input transactions.csv --output improved.csv \
  --rules merged.fin --include-pack retail,transport
```

✅ **Expected Result:** 5–10% coverage improvement; zero duplicates in `exact` mode.

---

## 📊 Performance Benchmarks (v0.7.7)

Measured with `--audit-mode none` (max throughput) on Intel i7-12700T, 48GB RAM, Windows 11, Python 3.13.7, PyArrow 21.0.

| Dataset | Test | Time (s) | Rows/sec | Notes |
|:--|:--|:--:|:--:|:--|
| 100K (UK Synthetic) | Growth Loop | 2.54 | **39,370** ✅ | Baseline (121 rules) |
| 100K (after Growth Loop) | Growth Loop | 4.96 | **20,161** ✅ | +6.3× rules → ≈ 2× slower (764 rules) |
| **5M × 50 cols** | Benchmark Harness | **179.27** | **27,900** ✅ | Enterprise validation, 3-run average |
| **20M × 6 cols** | Integrity Test (FastIO) | **~90** | **217,068** ✅ | Engine throughput, full SHA-256 verified |

> **v0.7.7 improvement:** Hot-path bug fix in `_to_number` removed an unnecessary `\b` word boundary that was both producing wrong results on no-space CR/DR formats AND costing measurable runtime. The fix delivered **+30-50% throughput** on the integrity harness vs v0.7.6, taking standard mode to ~180K rows/sec and FastIO to ~217K rows/sec.  
>
> **Cumulative v0.6.4 → v0.7.7:** -14% runtime, +16% throughput on the enterprise harness (5M × 50).  
>
> **Audit Overhead:** Enabling `--audit-mode lite/full` reduces throughput by ≈38% due to diff calculation; provides full decision provenance.  
>
> **Note:** These figures are validated benchmark results from controlled tests. Actual performance varies depending on dataset, ruleset, and audit mode.  
> See [`docs/benchmarks.md`](docs/benchmarks.md) for full details.

---

## 🔐 Cryptographic Integrity Verification (v0.7.7)

SHA-256 fingerprint verification benchmarked on large datasets:

| Rows | Engine (Standard) | Engine (FastIO) | Result |
|:--:|:--:|:--:|:--|
| 5M | **178,903 rows/s** | **198,448 rows/s** | ✅ All fingerprints match |
| 10M | **178,511 rows/s** | **214,136 rows/s** | ✅ All fingerprints match |
| **20M** | **181,566 rows/s** | **217,068 rows/s** | **✅ All fingerprints match** |

> **What this benchmark validated:** Every row's immutable fields (`date`, `amount`, `counterparty`) were verified via SHA-256 hash before and after engine processing. Zero cross-row contamination detected. Zero data corruption detected. **60M rows verified field-by-field across three runs, zero mismatches.**
>
> **Note:** As of v0.7.7, SHA-256 integrity verification is available as a CLI feature via `--verify` (fast fingerprint) and `--verify-full` (fingerprint + field comparison). Use `--verify-output-dir` to save audit artifacts (JSON report + proof CSV). See `docs/cli_reference.md` for details.

---

## 🌍 Internationalization Matrix

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

FinLang's Growth Loop accelerates rule creation through data-driven discovery.

- **Discover** uncategorized counterparties  
- **Suggest** new rules in seconds (1:1 mapping in exact mode)  
- **Merge + Re-run** for incremental coverage gains  
- **Validated Result:** 97.8% success on addressable patterns  
- **ROI:** 8.8 transactions categorized per new rule  

📄 See: [`docs/growth_loop_best_practices.md`](docs/growth_loop_best_practices.md)

---

## 🧾 Known Limitations (v0.7.x)

- ⚠️ `--emit-match fuzzy` (default) filters corporate stopwords (LTD, LLC, PLC, INC, GROUP, COMPANY, CO, SAS, GMBH, CORP) and deduplicates patterns within a batch (v0.7.7). Edge cases with very short counterparty names may still produce broad patterns.  → Use `--emit-match exact` for production workflows.   
- ⚠️ Hyphenated/apostrophe names may affect fuzzy matching (< 1% impact).  
- ⚠️ No support for non-Gregorian calendars or non-Western numerals.

---

## 📘 Documentation

- [`docs/release_notes/v0_7_7.md`](docs/release_notes/release_notes_v0_7_7.md)
- [`docs/release_notes/v0_7_6.md`](docs/release_notes/release_notes_v0_7_6.md)  
- [`docs/runtime_contract.md`](docs/runtime_contract.md)  
- [`docs/cli_reference.md`](docs/cli_reference.md)  
- [`docs/rulepacks.md`](docs/rulepacks.md)  
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
finlang --input bank.csv --output categorized.csv \
  --rules examples/rules.demo.fin \
  --include-pack retail,transport,subs \
  --fastio --audit audit_log.json --audit-mode lite
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

## 📌 Version Summary

| Component | Version | Status |
|:--|:--|:--|
| Core Engine      | v0.7.7   | ✅ Production-Ready  |
| CLI Suite        | v0.7.7   | ✅ Validated (135 tests, 10 gates) |
| Discover/Suggest | v0.7.7   | ✅ 97.8% accuracy    |
| Integrity Test   | v0.7.7   | ✅ 20M rows verified, ~217K rows/sec FastIO |
| Verify           | v0.7.7   | ✅ Built-in `--verify` / `--verify-full` |
| Docs             | v0.7.7   | ✅ Complete          |
| Python Support   | 3.10—3.14 | ✅ Tested            |
