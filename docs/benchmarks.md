# 📖 Benchmarks Guide
*Applies to FinLang v0.6.x*

FinLang includes a benchmarking harness to validate performance across dataset sizes, column widths, and ruleset complexities.  
This guide shows how to run benchmarks, interpret results, and use them for enterprise capacity planning.

---

## 🔹 Test Environment

- **CPU:** Intel i7-12700T (12th Gen)  
- **RAM:** 48 GB  
- **OS:** Windows 11 (64-bit)  
- **Python:** 3.11  
- **I/O:** PyArrow fast I/O enabled (`--fastio`)  

---

## 🔹 Harnesses

- **`bench_finlang_rulesets.py`** → tests ruleset-invariance (ruleset size vs performance).  
- **`bench_finlang_harness.py`** → full end-to-end benchmark (rows × cols grid, finale runs).  

Run from project root:

```powershell
python -m benchmarks.bench_finlang_harness `
  --mode full-cli `
  --run-fin "finlang --fastio --audit-mode none" `
  --rules examples/rules.demo.fin `
  --include-pack retail,transport,subs `
  --rows 25000,50000,100000,200000 `
  --cols 5,20,35,50 `
  --runs 3 `
  --final-rows 1000000,5000000 `
  --outdir bench_out_final
```

This runs a grid of dataset scales and concludes with finale tests (1M and 5M rows).

---

## 🔹 Official Results (v0.6.1)

### Grid Benchmarks (median of 3 runs)

| Rows   | Cols | Median Runtime (s) | Median Throughput (rows/s) |
|--------|------|---------------------|-----------------------------|
| 25,000 | 50   | 1.7                 | 14,806                      |
| 50,000 | 50   | 2.7                 | 18,442                      |
| 100,000| 50   | 5.0                 | 20,078                      |
| 200,000| 50   | 8.7                 | 22,944                      |

📈 Throughput increases as column count decreases (full grid in `bench_results.csv`).

### Finale Benchmarks

| Rows      | Cols | Runtime (s) | Throughput (rows/s) |
|-----------|------|-------------|----------------------|
| 1,000,000 | 50   | 41.8        | 23,900               |
| 5,000,000 | 50   | 210.3       | **23,800**           |
| 5,000,000 | 20   | 116.1       | 43,072               |
| 5,000,000 | 5    | 37.0        | 135,214              |

👉 **Canonical Headline:** 23,800 rows/s @ 5M × 50 cols.

---

## 🔹 Visualizations

### Runtime Surface (Rows × Cols)
![Surface](assets/bench_surface.png)

### Runtime Heatmap (Rows × Cols)
![Heatmap](assets/bench_heatmap.png)

### Ruleset Comparison Heatmaps
- Small ruleset  
![Small](assets/heatmap_Small.png)

- Medium ruleset  
![Medium](assets/heatmap_Medium.png)

- Large ruleset  
![Large](assets/heatmap_Large.png)

---

## 🔹 Findings

### Test 1: Performance vs Data Scale
- **Predictable scaling** → runtime grows linearly with rows.  
- **Column width adds cost** → more columns = more evaluation overhead.  
- **Robust throughput** → >20k rows/s sustained at enterprise scale.

### Test 2: Performance vs Rule Complexity
- **Ruleset-invariant** → small, medium, and large rulesets show negligible differences in throughput.  
- Confirms FinLang’s architectural advantage: rule complexity does not materially impact performance.

---

## 🔹 Troubleshooting

- **“Command not found”** → use `python -m benchmarks...` or check PATH.  
- **Low throughput** → ensure `--fastio` is enabled; otherwise falls back to slower CSV I/O.  
- **Audit overhead** → use `--audit-mode none` for benchmarking (fastest mode).  
- **Variance across runs** → close background apps, run ≥3 iterations, use median.

---

## 🔹 Enterprise Integration

- **Regression Testing** → Add benchmark stage in CI/CD; fail builds if throughput drops >10%.  
- **Capacity Planning** → Rows/s throughput × SLA gives max dataset size supportable.  
- **Compliance Evidence** → Benchmarks prove deterministic scaling; include reports in audit trail.

---

## 🔹 Cross-References

- [CLI Reference](cli_reference.md) → flags like `--fastio` and `--audit-mode`.  
- [Rule Language](rule_language.md) → rulesets used in tests.  
- [Workflows](workflows.md) → daily run & growth loop integration.  
- [README](README.md) → headline benchmark highlights.

---

© FinLang Ltd
