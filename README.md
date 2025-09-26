# finlang

## Performance (v0.6.1)

**Rig:** Intel i7-12700T • 48 GB RAM • Windows • Python 3.13 • `--fastio` (pyarrow)  
**Method:** wall-clock timings via `benchmarks/bench_finlang_harness.py` (3 runs; headline = **median**).

### Headline (production scale)
- **5M × 50 cols → ~210.3 s (median)**  ≈ **23.8k rows/s**
- **5M × 20 cols → ~95 s**  ≈ **52k rows/s**
- **5M × 5 cols → ~35 s**  ≈ **140k rows/s**

> Variability: expect ±5–10% at 5M due to disk/AV/thermal noise.

### Scalability (rows-linear @ 50 cols)
| Rows × Cols | Runtime (s) | Rows/s |
|---:|---:|---:|
| 100k × 50 | ~5.0 | ~20k |
| 200k × 50 | ~8.7 | ~23k |
| 1M × 50 | ~41.8 | ~24k |
| 5M × 50 | **~210.3** | **~23.8k** |

**What to expect**
- **Depth ≈ linear**: runtime grows proportionally with rows.
- **Width cost is predictable**: more columns increase time (DataFrame width + audit); engine evaluates a **slim projection** to contain this.
- **Deterministic**: append-only `flags +=`, reproducible results.

**Reproduce**
```bash
python -m benchmarks.bench_finlang_harness \
  --mode full-cli \
  --run-fin "finlang --fastio --audit-mode none" \
  --rules examples/rules.demo.fin \
  --include-pack retail,transport,subs \
  --rows 25000 50000 100000 200000 \
  --cols 5 20 35 50 \
  --runs 3 \
  --final-rows 1000000 5000000 \
  --outdir bench_out
