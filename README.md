# FinLang

**Deterministic Financial Rules Engine • 23,800+ Rows/Second • Audit-First**

[![PyPI version](https://badge.fury.io/py/finlang.svg)](https://badge.fury.io/py/finlang)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/FinLang-Ltd/finlang)
[![Python versions](https://img.shields.io/pypi/pyversions/finlang.svg)](https://pypi.org/project/finlang/)


---

## 🚀 Performance (v0.6.1)

**Test Rig:** Intel i7-12700T • 48 GB RAM • Windows • Python 3.11 • `--fastio` (PyArrow)  
**Methodology:** Wall-clock timings via `benchmarks/bench_finlang_harness.py` (3 runs; **median** reported)

### Production-Scale Performance

| Dataset        | Processing Time | Throughput        | Use Case                 |
|----------------|-----------------|-------------------|--------------------------|
| **5M × 50 cols** | **~210.3 s**   | **~23,800 rows/s** | Enterprise batch processing |
| 5M × 20 cols   | ~95.1 s         | ~52,600 rows/s    | Transaction monitoring   |
| 5M × 5 cols    | ~35.2 s         | ~142,800 rows/s   | Real-time screening      |

> 🔍 *Variability ±5–10% at scale due to system noise*

### Scalability Profile (50 Columns)

| Scale    | Runtime | Throughput      | Business Context   |
|----------|---------|-----------------|--------------------|
| 100K × 50 | ~5.0 s | 20,000 rows/s   | Hourly processing  |
| 1M × 50  | ~41.8 s | 23,900 rows/s   | Daily batches      |
| **5M × 50** | **~210.3 s** | **23,800 rows/s** | Monthly compliance |

## 🏢 Enterprise Ready
- **ICO Registered • Trademarks Filed • Professional Indemnity Insurance**
- **Deterministic Compliance** for regulated financial environments
- **Self-Hosted Deployment** - no data egress, full control


---

## 💡 Key Architectural Advantages

### 🎯 Predictable Performance
- **Linear scaling** with row count → accurate capacity planning  
- **Width-aware optimization** → engine projects to minimal column set  
- **Ruleset-invariant** → business logic complexity has minimal impact  

### 🔒 Deterministic & Auditable
- **Same inputs → same outputs** → reproducible, explainable results  
- **Append-only flagging (`+=`)** → prevents accidental overwrites  
- **Audit JSON log** → full trail of applied rule changes  

---

## 🛠️ Quickstart

1. **Install FinLang with the `fastio` option:**
   ```bash
   pip install "finlang[fastio]"
   ```

2. **Create your rules file (e.g., `my_rules.fin`):**
   ```fin
   rule "Groceries: TESCO" {
     match:
       - counterparty ~ "*TESCO*"
     set:
       - category = "Groceries"
       - flags += "Retail"
   }
   ```

3. **Run FinLang on your transactions CSV:**
   ```bash
   finlang --rules my_rules.fin --include-pack retail,sanity            --input transactions.csv --output categorized.csv --fastio
   ```

> 💡 **Pro Tip:** Start with `--audit-mode full` during development, switch to `none` for production throughput.


---

## 🔄 Growth Loop

FinLang supports an iterative discovery → suggestion cycle:

```bash
finlang-discover --input categorized.csv --top-k 20 > suggestions.fin
type suggestions.fin >> my_rules.fin
finlang --input transactions.csv --output categorized.csv         --rules my_rules.fin --include-pack retail,sanity --audit-mode full
```

- **`discover.py`** → mines uncategorized counterparties  
- **`suggest.py`** → generates conservative draft rules (deduplicated)

---

## 🧪 Reproduce Benchmarks

Full benchmarking suite (grid + finales):

```bash
python -m benchmarks.bench_finlang_harness   --mode full-cli   --run-fin "finlang --fastio --audit-mode none"   --rules examples/rules.demo.fin   --include-pack retail,transport,subs   --rows 25000 50000 100000 200000   --cols 5 20 35 50   --runs 3   --final-rows 1000000 5000000   --outdir bench_out
```

---

## 📖 Documentation

- [Manifesto](docs/manifesto.md)  
- [Grammar](docs/grammar.md)  
- [Benchmarks](docs/benchmarks.md) *(optional)*  
- [Privacy Policy](docs/privacy.md)  
- [Terms of Use](docs/terms.md)  

---

## 📦 Licensing

- **Community Edition** — AGPL-3.0 (open-source)  
- **Pro / Enterprise** — commercial license (FinLang Ltd)  

Contact: **[info@finlang.io](mailto:info@finlang.io)**  
Commercial handled via **Lemon Squeezy**

---

## 🏢 Project

- **Company:** FinLang Ltd (UK)  
- **Maintainer:** Angus McNab (founder)  
- **Trademark:** FinLang™  