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


import argparse
import os
import re
import sys
import time
import tempfile
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

TOTAL_TIME_RE = re.compile(r"Total execution time:\s*([0-9.]+)\s*seconds", re.I)

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
    extras = {f"extra_{i}": rng.normal(0, 1, n_rows) for i in range(extras_needed)}
    return pd.DataFrame({**base, **extras})

def ensure_rules_file(rules_path: Path):
    if rules_path and not rules_path.exists():
        rules_path.write_text(
            'rule "EXAMPLE: retail review" {\\n'
            '  match:\\n'
            '    - counterparty ~ "*TESCO*"\\n'
            '  set:\\n'
            '    - category = "Groceries"\\n'
            '    - flags += "auto"\\n'
            '}\\n',
            encoding="utf-8",
        )

def run_cli_and_time(run_fin_cmd: str, input_path: Path, output_path: Path,
                     rules: Path|None, include_pack: str, map_path: Path|None,
                     cli_parse: bool) -> float | None:
    cmd = run_fin_cmd.split() + [
        "--input", str(input_path),
        "--output", str(output_path),
        "--headless",
        "--audit-mode", "none"
    ]
    if rules:
        cmd += ["--rules", str(rules)]
    if include_pack:
        cmd += ["--include-pack", include_pack]
    if map_path and map_path.exists():
        cmd += ["--map", str(map_path)]

    if cli_parse:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            sys.stderr.write(f"[ERROR] CLI failed: {e}\\n")
            return None
        m = TOTAL_TIME_RE.search(result.stdout or "")
        if not m:
            sys.stderr.write("[WARN] Could not parse runtime from CLI output; consider disabling --cli-parse.\\n")
            return None
        try:
            return float(m.group(1))
        except Exception:
            return None
    else:
        t0 = time.perf_counter()
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            sys.stderr.write(f"[ERROR] CLI failed: {e}\\n")
            return None
        return time.perf_counter() - t0

def time_io_roundtrip(df: pd.DataFrame, tmpdir: Path, tag: str) -> float | None:
    path = tmpdir / f"tmp_{tag}.csv"
    try:
        t0 = time.perf_counter()
        df.to_csv(path, index=False)
        pd.read_csv(path)
        return time.perf_counter() - t0
    except Exception as e:
        sys.stderr.write(f"[ERROR] IO roundtrip failed: {e}\\n")
        return None
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass

def avg_or_nan(xs):
    vals = [x for x in xs if x is not None and not (isinstance(x, float) and (x != x))]
    if not vals:
        return float("nan")
    return float(np.mean(vals))

def plot_surface(results_df: pd.DataFrame, out_png: Path):
    rows_sorted = sorted(results_df["rows"].unique())
    cols_sorted = sorted(results_df["cols"].unique())
    Z = results_df.pivot(index="rows", columns="cols", values="runtime_sec").reindex(index=rows_sorted, columns=cols_sorted).values
    X, Y = np.meshgrid(cols_sorted, rows_sorted)

    fig = plt.figure(figsize=(9,6))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(X, Y, Z)
    ax.set_xlabel("Columns"); ax.set_ylabel("Rows"); ax.set_zlabel("Runtime (s)")
    ax.set_title("FinLang runtime vs Rows x Columns")
    plt.tight_layout(); fig.savefig(out_png, dpi=160); plt.close(fig)

def plot_heatmap(results_df: pd.DataFrame, out_png: Path):
    rows_sorted = sorted(results_df["rows"].unique())
    cols_sorted = sorted(results_df["cols"].unique())
    pivot = results_df.pivot(index="rows", columns="cols", values="runtime_sec").reindex(index=rows_sorted, columns=cols_sorted)
    fig = plt.figure(figsize=(8,5)); ax = fig.add_subplot(111)
    im = ax.imshow(pivot.values, aspect="auto")
    ax.set_xticks(range(len(cols_sorted)), cols_sorted)
    ax.set_yticks(range(len(rows_sorted)), rows_sorted)
    ax.set_xlabel("Columns"); ax.set_ylabel("Rows")
    ax.set_title("FinLang runtime (Rows x Columns)")
    for i in range(len(rows_sorted)):
        for j in range(len(cols_sorted)):
            ax.text(j, i, f"{pivot.values[i,j]:.2f}", ha="center", va="center", color="w")
    cbar = fig.colorbar(im); cbar.set_label("Runtime (s)")
    plt.tight_layout(); fig.savefig(out_png, dpi=160); plt.close(fig)

def main():
    ap = argparse.ArgumentParser(description="FinLang performance benchmark (grid + finales)")
    ap.add_argument("--mode", choices=["full-cli","io-only"], default="full-cli")
    ap.add_argument("--run-fin", default="python run_finlang.py")
    ap.add_argument("--rules", default="", help="Path to rules.fin (created if missing)")
    ap.add_argument("--include-pack", default="")
    ap.add_argument("--map", default="")
    ap.add_argument("--rows", type=int, nargs="+", default=[25000, 50000, 100000])
    ap.add_argument("--cols", type=int, nargs="+", default=[5, 20, 35, 50])
    ap.add_argument("--runs", type=int, default=1, help="repetitions per grid point")
    ap.add_argument("--final-rows", type=int, nargs="+", default=[1000000, 5000000])
    ap.add_argument("--cli-parse", action="store_true", help="parse CLI stdout for 'Total execution time'")
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    rules_path = Path(args.rules) if args.rules else None
    if rules_path:
        ensure_rules_file(rules_path)
    map_path = Path(args.map) if args.map else None

    print(f"[CONFIG] mode={args.mode} rows={args.rows} cols={args.cols} runs={args.runs}")
    print(f"[CONFIG] run_fin='{args.run_fin}' rules='{rules_path}' include_pack='{args.include_pack}' map='{map_path}'")

    records = []
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)

        # Grid
        for r in args.rows:
            for c in args.cols:
                run_times = []
                for k in range(args.runs):
                    tag = f"{r}r_{c}c_rep{k+1}"
                    df = make_df(r, c, seed=42+k)
                    if args.mode == "io-only":
                        dt = time_io_roundtrip(df, tmpdir, tag)
                    else:
                        in_path = tmpdir / f"input_{tag}.csv"
                        out_path = tmpdir / f"output_{tag}.csv"
                        df.to_csv(in_path, index=False)
                        dt = run_cli_and_time(args.run_fin, in_path, out_path, rules_path,
                                              args.include_pack, map_path, args.cli_parse)
                        try:
                            in_path.unlink(missing_ok=True); out_path.unlink(missing_ok=True)
                        except Exception: pass
                    run_times.append(dt)
                avg = avg_or_nan(run_times)
                records.append({"rows": r, "cols": c, "runs": args.runs, "runtime_sec": avg})
                print(f"[GRID] rows={r:>7}, cols={c:>3} -> avg {avg:.3f}s over {args.runs} run(s)")

        results_df = pd.DataFrame(records)
        results_csv = outdir / "bench_results.csv"
        results_df.to_csv(results_csv, index=False)
        print(f"[WRITE] {results_csv}")

        # Plots
        try:
            plot_heatmap(results_df, outdir / "bench_heatmap.png")
            plot_surface(results_df, outdir / "bench_surface.png")
            print(f"[WRITE] {outdir / 'bench_heatmap.png'}")
            print(f"[WRITE] {outdir / 'bench_surface.png'}")
        except Exception as e:
            print(f"[WARN] plot failed: {e}")

        # Finales
        finales = []
        for fr in args.final_rows:
            for c in (5, 20, 50):
                tag = f"FINAL_{fr}r_{c}c"
                df = make_df(fr, c, seed=99)
                if args.mode == "io-only":
                    dt = time_io_roundtrip(df, tmpdir, tag)
                else:
                    in_path = tmpdir / f"input_{tag}.csv"
                    out_path = tmpdir / f"output_{tag}.csv"
                    df.to_csv(in_path, index=False)
                    dt = run_cli_and_time(args.run_fin, in_path, out_path, rules_path,
                                          args.include_pack, map_path, args.cli_parse)
                    try:
                        in_path.unlink(missing_ok=True); out_path.unlink(missing_ok=True)
                    except Exception: pass
                finales.append({"rows": fr, "cols": c, "runtime_sec": (dt if dt is not None else float('nan'))})
                print(f"[FINAL] rows={fr:>9}, cols={c:>3} -> {finales[-1]['runtime_sec']:.2f}s")

        pd.DataFrame(finales).to_csv(outdir / "bench_big.csv", index=False)
        print(f"[WRITE] {outdir / 'bench_big.csv'}")

if __name__ == "__main__":
    main()