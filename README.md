# FinLang — The Financial Rules Engine

**Deterministic. Auditable. Global.**  
Built for **EU AI Act compliance**. Ready for **August 2026**.

[![PyPI version](https://badge.fury.io/py/finlang.svg)](https://badge.fury.io/py/finlang)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/FinLang-Ltd/finlang)
[![Python versions](https://img.shields.io/pypi/pyversions/finlang.svg)](https://pypi.org/project/finlang/)

---

## 🌍 Overview

**FinLang** is a domain-specific language and CLI engine for financial transaction processing.  
It replaces opaque machine-learning categorization with **transparent, deterministic rules** — delivering explainability, auditability, and global compatibility.

> **Built for compliance.**  
> Designed to meet the **EU AI Act** “high-risk AI” obligations — deterministic, explainable, and fully auditable.

---

## ⚙️ Key Features (v0.6.4 RC1 Final)

| Feature | Description |
|:--|:--|
| **Deterministic DSL** | Human-readable `.fin` rules language — explainable logic, Git-friendly. |
| **High-Performance Engine** | Vectorized core (Pandas + NumPy + PyArrow) — 24 K rows/sec + validated throughput. |
| **Growth Loop** | Automated Discover → Suggest → Categorize workflow — 97.8 % success rate on addressable patterns. |
| **Global I18n Support** | US/UK/EU/Commonwealth formats, £ € $ ¥ ₹ stripping, localized decimals/dates/delimiters. |
| **Audit Trail System** | Every decision logged; deterministic, stateless processing for reproducibility. |
| **CR/DR Semantics** | Case-insensitive (`CR`, `cr`, `Cr`, `DR`, `dr`), accounting negatives `(123.45)`, trailing minus `123.45-`. |
| **Amount Synthesis** | Auto-computes `amount = abs(credit) – abs(debit)`. Comprehensively tested for debit-only, credit-only, both columns, zero/empty values, and CR/DR suffixes. |
| **Strict Parsing** | Locale-aware normalization with fail thresholds (`--strict-parse`, `--fail-threshold 0.01`). |
| **Flag Integrity** | `flags += [...]` enforced; duplicates deduplicated deterministically (RC1a polish). |

---

## 🚀 Quick Start (5-Step Growth Loop)

### 1️⃣ Initial Categorization
```bash
finlang --input transactions.csv --output baseline.csv   --rules my_rules.fin --include-pack retail,transport
```

### 2️⃣ Discover Gaps
```bash
finlang-discover   --input baseline.csv   --candidates candidates.csv   --all-candidates all_candidates.csv   --min-count 5
```

### 3️⃣ Suggest Rules (Exact Mode Recommended)
```bash
finlang-suggest   --input candidates.csv   --output suggested_rules.fin   --rules my_rules.fin   --emit-match exact
```

### 4️⃣ Merge and Re-run
```bash
cat my_rules.fin suggested_rules.fin > merged.fin
finlang --input transactions.csv --output improved.csv   --rules merged.fin --include-pack retail,transport
```

### ✅ Expected Result
+ 5 – 10 % coverage improvement typical on real datasets  
Zero duplicates when using `--emit-match exact`.

---

## 📊 Performance Benchmarks (v0.6.4 RC1 Validated)

| Dataset | Rules | Time (s) | Rows/sec | Notes |
|:--:|:--:|:--:|:--:|:--|
| 100 K (UK Synthetic) | 121 | 2.54 | **39,370 ✅** | Baseline |
| 100 K (After Growth Loop) | 764 | 4.96 | **20,161 ✅** | +6.3× rules → 2× slower |
| 5 M × 50 cols | — | 201 | **24,849 ✅** | Exceeds claim by 4.4 % |

Performance degrades **linearly** with rule count; no cliff at scale.

---

## 🌐 Internationalization Matrix

| Region | Example Number | Date Order | CLI Flags |
|:--|:--:|:--:|:--|
| 🇺🇸 US / 🇨🇦 Canada | 1,234.56 | MM/DD | (defaults) |
| 🇬🇧 UK / 🇦🇺 Commonwealth | 1,234.56 | DD/MM | `--dayfirst` |
| 🇪🇺 Continental Europe | 1.234,56 | DD/MM | `--decimal "," --thousands "." --dayfirst` |
| 🇨🇭 Switzerland | 1'234.56 | DD/MM | `--thousands "'" --dayfirst` |

**Encodings:** UTF-8 (BOM-safe), CP1252, Latin-1 auto-detect  
**Delimiters:** `,`, `;`, `|`, `	` (auto)  
**Currencies:** £ € $ ¥ ₹ + non-breaking spaces automatically stripped

---

## 🧠 The Growth Loop

> **Discover → Suggest → Categorize → Repeat**

FinLang’s **Growth Loop** accelerates rule creation through data-driven discovery.

- **Discover** uncategorized counterparties automatically  
- **Suggest** new rules in seconds (1:1 mapping in `exact` mode)  
- **Merge + Re-run** for incremental coverage gains  
- **Validated Result:** 97.8 % success rate on addressable patterns  
- **ROI:** 8.8 transactions per new rule  

📄 See: [`docs/growth_loop_best_practices.md`](./docs/growth_loop_best_practices.md)

---

## 🧾 Known Limitations (v0.6.4 RC1)

- ⚠️ `--emit-match fuzzy` may produce duplicate patterns (`*GROUP*`, `*LLC*`, etc.).  
  Use `--emit-match exact` for production.  
  Fix planned v0.6.5 (stopword filter + dedup).
- ⚠️ Hyphenated/apostrophe names < 1 % impact in fuzzy mode.  
  Exact mode unaffected.
- ⚠️ No support for non-Gregorian calendars or non-Western numerals.

---

## 📘 Documentation

Full technical docs are included under `docs/`:
- [`release_notes_v0_6_4.md`](./docs/release_notes_v0_6_4.md)
- [`benchmarks.md`](./docs/benchmarks.md)
- [`growth_loop_best_practices.md`](./docs/growth_loop_best_practices.md)
- [`amount_synthesis.md`](./docs/amount_synthesis.md)
- [`i18n_examples.md`](./docs/i18n_examples.md)
- [`stateless_processing.md`](./docs/stateless_processing.md)

---

## 📦 Installation

**From PyPI (once published):**
```bash
pip install finlang
```

**From source:**
```bash
git clone https://github.com/finlang/finlang.git
cd finlang
pip install -e .
```

---

## 🧩 Example CLI Usage

```bash
finlang --input bank.csv --output categorized.csv   --rules examples/rules.demo.fin   --include-pack retail,transport,subs   --fastio --audit-mode lite
```

---

## 📜 License & Commercial Use

Open-source under **AGPL-3.0**.  
Commercial licenses available via **FinLang Ltd**.

📧 info@finlang.io  
🌐 [https://finlang.io](https://finlang.io)

---

## 🏁 Version Summary

| Component | Version | Status |
|:--|:--|:--|
| Core Engine | v0.6.4 (RC1a) | ✅ Production-Ready |
| CLI Suite | RC1 Final | ✅ Validated |
| Discover/Suggest | RC1 Final | ✅ 97.8 % accuracy |
| Docs | RC1 Final | ✅ Complete |
| Next Milestone | v0.6.5 | 🚧 Tokenizer improvements |
