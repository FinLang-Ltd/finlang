# FinLang — Financial Rules DSL
# Copyright (C) 2025 FinLang Ltd
#
# This file is part of FinLang.
#
# FinLang is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, version 3.
#
# FinLang is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with FinLang.  If not, see <https://www.gnu.org/licenses/>.
#
# Commercial licensing is available. Contact FinLang Ltd for terms.
#
# FinLang™ is a trademark of FinLang Ltd.


import argparse, os, sys, time, subprocess
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib.pyplot as plt

def make_df(n_rows: int, n_cols: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    base = {
        "counterparty": rng.choice(["TESCO","AMAZON","UBER","STARBUCKS","MCDONALDS","VODAFONE"], n_rows),
        "amount": rng.normal(0, 100, n_rows),
        "date": pd.date_range("2025-01-01", periods=n_rows, freq="T").astype(str),
        "category": [""] * n_rows,
        "flags": [""] * n_rows,
    }
    extras_needed = max(0, n_cols - 5)
    extras = {f"extra_{i}": rng.normal(0,1,n_rows) for i in range(extras_needed)}
    return pd.DataFrame({**base, **extras})

def time_full_cli(df, outdir: Path, tag: str, run_fin_cmd: str, rules_path: Path,
                  include_pack: str, map_path: Path|None) -> float:
    in_path = outdir / f"input_{tag}.csv"; out_path = outdir / f"output_{tag}.csv"
    df.to_csv(in_path, index=False)
    cmd = run_fin_cmd.split() + ["--input", str(in_path), "--output", str(out_path), "--headless", "--audit-mode", "none"]
    if rules_path: cmd += ["--rules", str(rules_path)]
    if include_pack: cmd += ["--include-pack", include_pack]
    if map_path and map_path.exists(): cmd += ["--map", str(map_path)]
    t0 = time.perf_counter()
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] CLI failed for tag={tag}: {e}", file=sys.stderr); return float("nan")
    dt = time.perf_counter() - t0
    try:
        in_path.unlink(missing_ok=True); out_path.unlink(missing_ok=True)
    except Exception: pass
    return dt

def plot_heatmap(df: pd.DataFrame, title: str, out_png: Path):
    rows_sorted = sorted(df["rows"].unique()); cols_sorted = sorted(df["cols"].unique())
    pivot = df.pivot(index="rows", columns="cols", values="runtime_sec").reindex(index=rows_sorted, columns=cols_sorted)
    fig = plt.figure(figsize=(8,5)); ax = fig.add_subplot(111); im = ax.imshow(pivot.values, aspect="auto")
    ax.set_xticks(range(len(cols_sorted)), cols_sorted); ax.set_yticks(range(len(rows_sorted)), rows_sorted)
    ax.set_xlabel("Columns"); ax.set_ylabel("Rows"); ax.set_title(title)
    for i in range(len(rows_sorted)):
        for j in range(len(cols_sorted)):
            ax.text(j, i, f"{pivot.values[i,j]:.2f}", ha="center", va="center", color="w")
    cbar = fig.colorbar(im); cbar.set_label("Runtime (s)"); plt.tight_layout(); fig.savefig(out_png, dpi=160); plt.close(fig)

def plot_compare_lines(all_df: pd.DataFrame, fixed: str, value: int, out_png: Path):
    other = "cols" if fixed=="rows" else "rows"
    fig = plt.figure(figsize=(8,5)); ax = fig.add_subplot(111)
    subset = all_df[all_df[fixed]==value]
    for name, g in subset.groupby("ruleset"):
        g_sorted = g.sort_values(other)
        ax.plot(g_sorted[other], g_sorted["runtime_sec"], marker="o", label=name)
    ax.set_xlabel(other.capitalize()); ax.set_ylabel("Runtime (s)")
    ax.set_title(f"Runtime vs {other} @ {fixed}={value}"); ax.legend(); ax.grid(True); plt.tight_layout(); fig.savefig(out_png, dpi=160); plt.close(fig)

def main():
    ap = argparse.ArgumentParser(description="Multi-ruleset FinLang benchmark")
    ap.add_argument("--run-fin", default="python run_finlang.py")
    ap.add_argument("--rules-set", action="append", required=True, help="Name:/path/to/file.fin (repeatable)")
    ap.add_argument("--include-pack", default=""); ap.add_argument("--map", default="")
    ap.add_argument("--grid-rows", type=int, nargs="+", default=[25000, 50000, 100000])
    ap.add_argument("--grid-cols", type=int, nargs="+", default=[5, 20, 35, 50])
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--final-rows", type=int, nargs="+", default=[1000000, 5000000])
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    map_path = Path(args.map) if args.map else None
    rulesets = []
    for item in args.rules_set:
        name, path = item.split(":",1); rulesets.append((name.strip(), Path(path)))

    records = []
    for name, rules_path in rulesets:
        print(f"[RULESET] {name} -> {rules_path}")
        for r in args.grid_rows:
            for c in args.grid_cols:
                for rep in range(args.repeats):
                    tag = f"{name}_{r}r_{c}c_rep{rep+1}"
                    df = make_df(r, c, seed=42+rep)
                    dt = time_full_cli(df, outdir, tag, args.run_fin, rules_path, args.include_pack, map_path)
                    records.append({"ruleset": name, "rows": r, "cols": c, "repeat": rep+1, "runtime_sec": dt})
                    print(f"[GRID] {name:>8} rows={r:>7}, cols={c:>3}, rep={rep+1} -> {dt:.3f}s")

    all_df = pd.DataFrame(records); (outdir / "results_all.csv").write_text(all_df.to_csv(index=False))

    # per-ruleset heatmaps
    for name, _ in rulesets:
        df = all_df[all_df["ruleset"]==name].groupby(["rows","cols"], as_index=False)["runtime_sec"].mean()
        plot_heatmap(df, f"Runtime heatmap — {name}", outdir / f"heatmap_{name}.png")

    # comparisons
    avg = all_df.groupby(["ruleset","rows","cols"], as_index=False)["runtime_sec"].mean()
    for r in args.grid_rows:
        plot_compare_lines(avg, "rows", r, outdir / f"compare_rows_{r}.png")
    for c in args.grid_cols:
        plot_compare_lines(avg, "cols", c, outdir / f"compare_cols_{c}.png")

    # finales
    big = []
    for name, rules_path in rulesets:
        for fr in args.final_rows:
            for c in (5,20,50):
                tag = f"FINAL_{name}_{fr}r_{c}c"
                df = make_df(fr, c, seed=99)
                dt = time_full_cli(df, outdir, tag, args.run_fin, rules_path, args.include_pack, map_path)
                big.append({"ruleset": name, "rows": fr, "cols": c, "runtime_sec": dt})
                print(f"[FINAL] {name:>8} rows={fr:>9}, cols={c:>3} -> {dt:.2f}s")
    big_df = pd.DataFrame(big); (outdir / "finales.csv").write_text(big_df.to_csv(index=False))

if __name__ == "__main__":
    main()