# 📊 FinLang Benchmarks
> **Applies to:** FinLang v0.7+  
> **Status:** Reference  
> **Last verified:** v0.7.2

This guide presents validated benchmark data for FinLang v0.7.2, tested on a real developer workstation.

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

## 📈 Validated Results (v0.7.2)

### Single Ruleset Performance — Grid

| Rows × Cols | Runtime (s) | Throughput (rows/s) |
|---:|---:|---:|
| 25K × 5  | 0.70 | 35,700 |
| 25K × 20 | 1.00 | 25,000 |
| 25K × 35 | 1.26 | 19,800 |
| 25K × 50 | 1.58 | 15,800 |
| 50K × 5  | 0.83 | 60,200 |
| 50K × 20 | 1.37 | 36,500 |
| 50K × 35 | 1.89 | 26,500 |
| 50K × 50 | 2.40 | 20,800 |
| 100K × 5  | 1.02 | 98,000 |
| 100K × 20 | 2.08 | 48,100 |
| 100K × 35 | 3.27 | 30,600 |
| 100K × 50 | 4.39 | 22,800 |
| 200K × 5  | 1.46 | 137,000 |
| 200K × 20 | 3.68 | 54,300 |
| 200K × 35 | 5.92 | 33,800 |
| 200K × 50 | 8.29 | 24,100 |

### Single Ruleset Performance — Finals

| Rows × Cols | Runtime (s) | Throughput (rows/s) |
|---:|---:|---:|
| 1M × 5 | 5.05 | 198,000 |
| 1M × 20 | 16.52 | 60,500 |
| 1M × 50 | 38.47 | 26,000 |
| 5M × 5 | 23.06 | 216,800 |
| 5M × 20 | 89.45 | 55,900 |
| **5M × 50** | **187.76** | **26,600** | 

### Ruleset Comparison (5M × 50)

| Ruleset | Runtime (s) | Throughput (rows/s) |
|---------|-------------|---------------------|
| Small | 185.18 | 27,000 |
| Medium | 185.99 | 26,900 |
| Large | 184.66 | 27,100 |

**Key finding:** <1% variance across rulesets — rule complexity has negligible impact at scale.

---

## 📊 v0.7.2 vs v0.6.4 Comparison

| Benchmark | v0.6.4 | v0.7.2 | Improvement |
|-----------|--------|--------|-------------|
| Single Ruleset (5M×50) | 208.31s | 187.76s | **-10%** |
| Ruleset Comparison (5M×50 avg) | ~200s | ~185s | **-8%** |
| Throughput | ~24K rows/s | ~27K rows/s | **+12%** |

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
