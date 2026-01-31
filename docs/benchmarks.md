# 📊 FinLang Benchmarks
> **Applies to:** FinLang v0.6+  
> **Status:** Reference  
> **Last verified:** v0.6.4.post1

This guide presents validated benchmark data for FinLang v0.6.4.post1, tested on a real developer workstation, with updated results, corrected flags, and links to related docs.

---

## ⚙️ Test Environment (Workstation Used)

- **CPU:** Intel i7‑12700T (12th Gen)  
- **RAM:** 48 GB  
- **OS:** Windows 11 (64‑bit)  
- **Python:** 3.11 (64‑bit)  
- **I/O:** PyArrow fast I/O enabled (`--fastio`)  

> Your absolute numbers may differ based on CPU, storage, and OS. Focus on **shape** (linear scaling) and **relative** performance.

---

## 🧪 Benchmark Harnesses

Two benchmark harnesses were used for GA validation:

### 1) **Single Ruleset Harness** — scaling across Rows × Cols
Evaluates performance for a single static ruleset over a grid of dataset sizes and column widths.

```bash
python -m benchmarks.bench_finlang_harness   --mode full-cli   --run-fin "finlang --fastio --audit-mode none --headless --strict-parse --encoding auto"   --rules examples/rules.demo.fin   --rows 25000 50000 100000 200000   --cols 5 20 35 50   --runs 3   --final-rows 1000000 5000000   --outdir bench_out_final
```

Outputs include:
- `bench_surface.png` — 3D runtime surface  
- `bench_heatmap.png` — runtime heatmap  
- CSVs with raw timings (median of 3 runs reported)

---

### 2) **Ruleset Comparison Harness** — small vs medium vs large rules
Measures runtime impact of ruleset size/complexity.

```bash
python -m benchmarks.bench_finlang_rulesets   --rules-set examples/rules.small.fin examples/rules.medium.fin examples/rules.large.fin   --outdir bench_out_rulesets
```
> ✅ **Flag correction:** The correct flag is `--rules-set` (not `--ruleset-paths`).

Outputs include:
- `heatmap_Small.png`  
- `heatmap_Medium.png`  
- `heatmap_Large.png`

---

## 🖼️ Visual Results (from latest GA runs)

| Visualization | Description |
|---|---|
| ![Surface](assets/bench_surface.png) | 3D runtime surface (Rows × Cols) |
| ![Heatmap](assets/bench_heatmap.png) | Runtime heatmap (Rows × Cols) |
| ![Small](assets/heatmap_Small.png) | Ruleset comparison — Small |
| ![Medium](assets/heatmap_Medium.png) | Ruleset comparison — Medium |
| ![Large](assets/heatmap_Large.png) | Ruleset comparison — Large |

---

## 📈 Validated Results (v0.6.4.post1)

| Rows × Cols | Runtime (s) | Throughput (rows/s) | Notes |
|---:|---:|---:|---|
| 25 K × 5  | 0.7  | 35,700 | Baseline smoke test |
| 50 K × 20 | 1.5  | 33,300 | Excellent linearity |
| 100 K × 35| 3.6  | 27,700 | Near‑ideal scaling |
| 200 K × 50| 8.6  | 23,200 | Approaches saturation |
| **5 M × 50** | **≈ 208** | **≈ 24,000** | **Enterprise benchmark** |

---

## 🔬 Methodology Notes

- **3 runs per point**, **median** reported to smooth variance  
- First run treated as warm‑up when necessary  
- `--audit-mode none` to measure engine speed (no audit overhead)  
- PyArrow (`--fastio`) enabled for CSV I/O  
- Deterministic data generation, reproducible CLI scripts

---

## 💡 Practical Interpretation

| Scenario | Example Dataset | Expected Runtime |
|---|---|---|
| Personal finance | 25 K × 20 | < 1 s |
| Small business | 500 K × 35 | ~18 s |
| Enterprise ledger | 5 M × 50 | ~208 s |

**Rule of thumb:** FinLang scales linearly — doubling rows ≈ doubling runtime; increasing columns raises evaluation cost predictably.

---

## 🧩 Troubleshooting

| Issue | Symptom | Fix |
|---|---|---|
| “PyArrow missing” | `ImportError: No module named pyarrow` | Reinstall with `[fastio]` extras: `pip install finlang[fastio]` |
| “Encoding error” | Garbled text | Add `--encoding auto` |
| “CSV fails strict parse” | Header / delimiter issues | Use `--strict-parse`; correct headers or delimiters |
| Slow performance | Lower than expected throughput | Ensure `--fastio` is present; close background apps |
| CPU power limits | Runtime > expected | Disable power saving / thermal throttling |

---

## 📚 Related Documentation

- [flags.md](flags.md) — Full CLI flags and canonical formats  
- [i18n_examples.md](i18n_examples.md) — Regional format examples  
- [mapping_guide.md](mapping_guide.md) — Align headers to schema  
- [amount_synthesis.md](amount_synthesis.md) — Debit/credit synthesis logic  
- [rule_language.md](rule_language.md) — How to write/test rules  
- [growth_loop_best_practices.md](growth_loop_best_practices.md) — 3‑step discovery workflow  
- [cli_reference.md](cli_reference.md) — Complete command reference  
- [workflows.md](workflows.md) — End‑to‑end workflow guide
