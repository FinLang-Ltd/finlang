# 📊 FinLang Benchmarks
> **Applies to:** FinLang v0.7+  
> **Status:** Reference  
> **Last verified:** v0.7.4.post1

This guide presents validated benchmark data for FinLang v0.7.4.post1, tested on a real developer workstation.

---

## ⚙️ Test Environment

- **CPU:** Intel i7‑12700T (12th Gen)  
- **RAM:** 48 GB  
- **OS:** Windows 11 (64‑bit)  
- **Python:** 3.13.7 (64‑bit)  
- **Backend:** FastIO (PyArrow)

> Your absolute numbers may differ based on CPU, storage, and OS. Focus on **shape** (linear scaling) and **relative** performance.

---

## 🧪 Benchmark Harnesses

### 1) Single Ruleset Harness — scaling across Rows × Cols

Evaluates performance for a single static ruleset over a grid of dataset sizes and column widths.

```powershell
python -m benchmarks.bench_finlang_harness `
  --mode full-cli `
  --run-fin "finlang --fastio --audit-mode none --headless" `
  --rules examples/rules.demo.fin `
  --include-pack retail,transport,subs `
  --rows 25000 50000 100000 200000 `
  --cols 5 20 35 50 `
  --runs 3 `
  --final-rows 1000000 5000000 `
  --outdir bench_out_final
```

**Outputs:**
- `bench_surface.png` — 3D runtime surface  
- `bench_heatmap.png` — runtime heatmap  
- `bench_results.csv` — raw timings (median of 3 runs)

---

### 2) Ruleset Comparison Harness — small vs medium vs large rules

Measures runtime impact of ruleset size/complexity.

```powershell
python -m benchmarks.bench_finlang_rulesets `
  --run-fin "finlang --fastio --audit-mode none --headless" `
  --rules-set Small:examples/rules.demo.fin `
  --rules-set Medium:src/finlang/rulepacks/01-vendors-retail.fin `
  --rules-set Large:src/finlang/rulepacks/03-subscriptions.fin `
  --include-pack transport `
  --grid-rows 25000 50000 100000 200000 `
  --grid-cols 5 20 35 50 `
  --repeats 3 `
  --final-rows 1000000 5000000 `
  --outdir bench_out_rulesets
```

**Outputs:**
- `heatmap_Small.png`, `heatmap_Medium.png`, `heatmap_Large.png`
- `results_all.csv`, `finales.csv`

---

### 3) Integrity Test — cryptographic verification at scale

Validates data integrity with SHA-256 fingerprinting. Proves zero data corruption or cross-row contamination.

```powershell
# Default: 5K rows, fingerprint-only (daily use)
python integrity_test.py

# Full validation: field-by-field + fingerprint
python integrity_test.py --full

# Scale testing
python integrity_test.py --rows 20000000 --full
```

**What it proves:**
- Row count preserved (no dropped/duplicated rows)
- Immutable fields unchanged (`date`, `amount`, `counterparty`)
- SHA-256 fingerprint per row validates no cross-row contamination
- Both code paths (standard + PyArrow) produce identical results

---

## 📈 Validated Results (v0.7.4.post1)

### Single Ruleset Performance — Grid

| Rows × Cols | Runtime (s) | Throughput (rows/s) |
|---:|---:|---:|
| 25K × 5  | 0.74 | 33,800 |
| 25K × 20 | 1.00 | 25,000 |
| 25K × 35 | 1.28 | 19,500 |
| 25K × 50 | 1.55 | 16,100 |
| 50K × 5  | 0.84 | 59,500 |
| 50K × 20 | 1.37 | 36,500 |
| 50K × 35 | 1.88 | 26,600 |
| 50K × 50 | 2.41 | 20,700 |
| 100K × 5  | 1.00 | 100,200 |
| 100K × 20 | 2.08 | 48,100 |
| 100K × 35 | 3.19 | 31,400 |
| 100K × 50 | 4.32 | 23,100 |
| 200K × 5  | 1.44 | 139,200 |
| 200K × 20 | 3.90 | 51,300 |
| 200K × 35 | 6.00 | 33,300 |
| 200K × 50 | 8.02 | 24,900 |

### Single Ruleset Performance — Finals

| Rows × Cols | Runtime (s) | Throughput (rows/s) |
|---:|---:|---:|
| 1M × 5 | 4.94 | 202,400 |
| 1M × 20 | 15.83 | 63,200 |
| 1M × 50 | 38.05 | 26,300 |
| 5M × 5 | 22.74 | 219,900 |
| 5M × 20 | 77.12 | 64,800 |
| **5M × 50** | **187.90** | **26,600** |

### Ruleset Comparison (5M × 50)

| Ruleset | Runtime (s) | Throughput (rows/s) |
|---------|-------------|---------------------|
| Small | 176.04 | 28,400 |
| Medium | 180.19 | 27,750 |
| Large | 178.70 | 27,980 |

**Key finding:** <3% variance across rulesets — rule complexity has negligible impact at scale.

> Peak observed on ruleset variants: up to 28,400 rows/sec. Conservative marketing figure remains ~27K to account for real-world variance.

---

## 🔐 Integrity Test Results

Cryptographic verification using SHA-256 fingerprints on every row.

### Performance by Scale

| Rows | Generation | Engine (std) | Engine (fast) | Validation (full) | Total |
|------|------------|--------------|---------------|-------------------|-------|
| 5M | 20s | 39s (128K/s) | 38s (133K/s) | 1.8m | ~5 min |
| 10M | 43s | 1.4m (122K/s) | 1.1m (156K/s) | 3.2m | ~10 min |
| **20M** | **1.2m** | **2.3m (146K/s)** | **2.0m (167K/s)** | **5.9m** | **~18 min** |

### 20M Row Validation — Full Output

```
=== FinLang Data Integrity Test (Python) ===
  Row count: 20,000,000
  Validation mode: Full (field-by-field + fingerprint)
  PyArrow available: Yes
[1/6] Generating 20,000,000 test rows with fingerprints... OK (1.2m)
[2/6] Creating test rules... OK
       Loading input data for validation... OK (20.4s)
[3/6] Running FinLang engine (standard)... OK (2.3m, 146,105 rows/s)
[4/6] Validating integrity (standard, full)... OK (20,000,000 categorized, 5.9m)
[5/6] Running FinLang engine (--fastio)... OK (2.0m, 167,475 rows/s)
[6/6] Validating integrity (--fastio, full)... OK (20,000,000 categorized, 5.9m)
=== Integrity Test PASSED ===
  Rows tested: 20,000,000
  Immutable fields verified: date, amount, counterparty
  Fingerprints validated: 20,000,000 (no cross-row contamination)
  Validation mode: Full (field-by-field + fingerprint)
  Standard mode: PASS (146,105 rows/s)
  FastIO mode:   PASS (167,475 rows/s)
```

### Why Integrity Test Shows Higher Throughput

The integrity test uses a **minimal 6-column schema** (date, amount, counterparty, memo, category, fingerprint) versus the benchmark's **50-column enterprise schema**.

| Test Type | Columns | Throughput (FastIO) |
|-----------|---------|---------------------|
| Integrity test | 6 | 167K rows/s |
| Enterprise benchmark | 50 | 27K rows/s |

This is expected: narrower data = less I/O, less memory pressure, faster processing. Both numbers are valid for their respective use cases.

---

## 📊 Version Comparison

| Benchmark | v0.6.4 | v0.7.2 | v0.7.4.post1 | Cumulative |
|-----------|--------|--------|--------------|------------|
| Single Ruleset (5M×50) | 208.31s | 187.76s | 187.90s | **-10%** |
| Ruleset Comparison (5M×50 avg) | ~200s | ~185s | ~178s | **-11%** |
| Throughput (enterprise) | ~24K rows/s | ~27K rows/s | ~27K rows/s | **+12%** |
| Integrity (FastIO, 20M×6) | — | 159K rows/s | 167K rows/s | **+5%** (vs v0.7.2) |

---

## 🖼️ Visual Results

| Visualization | Description |
|---|---|
| ![Surface](assets/bench_surface.png) | 3D runtime surface (Rows × Cols) |
| ![Heatmap](assets/bench_heatmap.png) | Runtime heatmap (Rows × Cols) |
| ![Small](assets/heatmap_Small.png) | Ruleset comparison — Small |
| ![Medium](assets/heatmap_Medium.png) | Ruleset comparison — Medium |
| ![Large](assets/heatmap_Large.png) | Ruleset comparison — Large |

---

## 🔬 Methodology Notes

- **3 runs per point**, median reported to smooth variance  
- Warm runs (Chrome closed, system idle)
- `--audit-mode none` to measure engine speed (no audit overhead)  
- PyArrow (`--fastio`) enabled for CSV I/O  
- Deterministic data generation, reproducible CLI scripts

---

## 💡 Practical Interpretation

| Scenario | Example Dataset | Expected Runtime |
|---|---|---|
| Personal finance | 25K × 20 | < 1s |
| Small business | 500K × 35 | ~15s |
| Enterprise ledger | 5M × 50 | ~3 min |
| Full year bank data | 20M × 6 | ~18 min (with integrity verification) |

**Rule of thumb:** FinLang scales linearly — doubling rows ≈ doubling runtime; increasing columns raises evaluation cost predictably.

---

## 🧩 Troubleshooting

| Issue | Symptom | Fix |
|---|---|---|
| "PyArrow missing" | `ImportError: No module named pyarrow` | `pip install "finlang[fastio]"` |
| "Encoding error" | Garbled text | Add `--encoding auto` |
| Slow performance | Lower than expected throughput | Ensure `--fastio` is present; close background apps |
| CPU power limits | Runtime > expected | Disable power saving / thermal throttling |

---

## 📚 Related Documentation

- [CLI Reference](cli_reference.md) — Complete command reference
- [Runtime Contract](runtime_contract.md) — Backend selection logic
- [Flags](flags.md) — Full CLI flags and canonical formats  
- [Workflows](workflows.md) — End‑to‑end workflow guide
