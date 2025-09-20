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


from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from importlib import resources

# Engine import (package layout only; installed or editable install)
from finlang.engine.finlang_engine_v0_5_2 import run_audit

# ---- Starter packs short names ------------------------------------------------

PACK_MAP = {
    "retail": "01-vendors-retail.fin",
    "transport": "02-transport.fin",
    "subs": "03-subscriptions.fin",
    "subscriptions": "03-subscriptions.fin",
    "travel": "04-travel.fin",
    "financial": "05-financial.fin",
    "compliance": "06-compliance.flags.fin",
    "sanity": "07-sanity.fin",
    "examples": "08-examples.fin",
}

# Paths for local fallbacks (src/finlang/*)
_THIS_DIR = Path(__file__).resolve().parent           # .../src/finlang/cli
_PKG_ROOT = _THIS_DIR.parent                          # .../src/finlang
_LOCAL_RULEPACKS = _PKG_ROOT / "rulepacks"


# ---- Resource helpers: package-first, then dev-folder fallback ---------------

def _read_pack_text(pack_name: str) -> str:
    """Read a packaged rulepack by short name, with a local dev-folder fallback."""
    fname = PACK_MAP.get(pack_name.lower())
    if not fname:
        raise SystemExit(f"Unknown pack '{pack_name}'. Known: {', '.join(sorted(PACK_MAP))}")

    # Package-first
    try:
        return resources.files("finlang.rulepacks").joinpath(fname).read_text(encoding="utf-8")
    except Exception:
        # Local fallback (dev-folder runs without installation)
        p = _LOCAL_RULEPACKS / fname
        if p.exists():
            return p.read_text(encoding="utf-8")
        raise SystemExit(f"Could not find rulepack '{fname}' in package or at '{p}'.")


def _load_default_bank_map_text() -> str:
    """Load default bank.map.json from package, with robust dev-folder fallback."""
    fname = "bank.map.json"
    # Try packaged resource first
    try:
        return resources.files("finlang.mapping").joinpath(fname).read_text(encoding="utf-8")
    except Exception:
        pass

    # Fallback: running from repo with multiple possible layouts
    here = Path(__file__).resolve().parent
    candidates = [
        here / "mapping" / fname,                   # ./mapping/bank.map.json
        here.parent / "mapping" / fname,            # ../mapping/bank.map.json
        here.parent / "finlang" / "mapping" / fname,# ../finlang/mapping/bank.map.json
    ]
    for p in candidates:
        if p.exists():
            return p.read_text(encoding="utf-8")
    raise SystemExit("Could not find default bank.map.json (provide --map explicitly).")


# ---- Rules concatenation & parsing -------------------------------------------

def _combine_rules(rules_files: List[str], pack_list: List[str]) -> Path:
    parts: List[str] = []

    # 1) Personal rules first (highest precedence)
    for rf in (rules_files or []):
        p = Path(rf)
        if not p.exists():
            raise SystemExit(f"Rules file not found: {p}")
        parts.append(f"# --- BEGIN {p.name} ---\n{p.read_text(encoding='utf-8')}\n# --- END ---")

    # 2) Then packs (lower precedence)
    for name in pack_list:
        txt = _read_pack_text(name)
        parts.append(f"# --- BEGIN PACK {name} ---\n{txt}\n# --- END PACK ---")

    if not parts:
        raise SystemExit("No rules provided. Use --rules and/or --include-pack.")

    tmp = tempfile.NamedTemporaryFile("w", delete=False, suffix=".fin", encoding="utf-8")
    tmp.write("\n\n".join(parts))
    tmp.flush()
    tmp.close()
    return Path(tmp.name)


def _strip_inline_comment(line: str) -> str:
    in_quote: Optional[str] = None
    i = 0
    while i < len(line):
        ch = line[i]
        if ch in ('"', "'"):
            if in_quote == ch:
                in_quote = None
            elif in_quote is None:
                in_quote = ch
        elif in_quote is None:
            if ch == '#':
                return line[:i].rstrip()
            if i + 1 < len(line) and line[i:i+2] == '//':
                return line[:i].rstrip()
        i += 1
    return line


def parse_fin_rules(path: str) -> List[Dict[str, Any]]:
    try:
        content = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"FATAL: Rules file not found at '{path}'", file=sys.stderr)
        sys.exit(1)

    rules: List[Dict[str, Any]] = []
    rule_pattern = re.compile(r"rule\s+(?:\"([^\"]*)\"|'([^']*)'|(\S+))\s*\{(.*?)\}",
                              re.DOTALL | re.IGNORECASE)

    for match in rule_pattern.finditer(content):
        name = next(g for g in match.groups()[:3] if g is not None)
        block = match.group(4)
        rule: Dict[str, Any] = {"name": name, "match": [], "set": []}
        section: Optional[str] = None
        for raw in block.splitlines():
            line = _strip_inline_comment(raw).strip()
            if not line:
                continue
            low = line.lower()
            if low.startswith("match:"):
                section = "match"; continue
            if low.startswith("set:"):
                section = "set"; continue
            if section:
                if line.startswith("-"):
                    line = line[1:].strip()
                rule[section].append(line)
        rules.append(rule)
    return rules


# ---- Header mapping (hybrid amount support) ----------------------------------

def load_header_map(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    mapping: dict[str, Any] = {}
    for canon, aliases in raw.items():
        canon_l = str(canon).strip().lower()
        if isinstance(aliases, dict):
            norm: dict[str, Any] = {}
            for k, v in aliases.items():
                k_l = str(k).strip().lower()
                if isinstance(v, list):
                    norm[k_l] = [str(a).strip().lower() for a in v if str(a).strip()]
                else:
                    norm[k_l] = str(v).strip().lower()
            mapping[canon_l] = norm
        elif isinstance(aliases, str):
            mapping[canon_l] = [aliases.strip().lower()]
        elif isinstance(aliases, list):
            mapping[canon_l] = [str(a).strip().lower() for a in aliases if str(a).strip()]
    return mapping


def apply_header_map(df: pd.DataFrame, mapping: dict, *, headless: bool) -> pd.DataFrame:
    df.columns = [str(c).strip().lower() for c in df.columns]
    used: dict[str, str] = {}

    for canon, spec in mapping.items():
        # Special-case: amount aliases (hybrid dict form)
        if canon == "amount" and isinstance(spec, dict):
            aliases = spec.get("aliases")
            if aliases and "amount" not in df.columns:
                for alias in (aliases if isinstance(aliases, list) else [aliases]):
                    if alias in df.columns:
                        df.rename(columns={alias: "amount"}, inplace=True)
                        used["amount"] = alias
                        break
            continue

        if canon in df.columns:
            continue

        cand_list: List[str] = []
        if isinstance(spec, str):
            cand_list = [spec]
        elif isinstance(spec, list):
            cand_list = spec

        for alias in cand_list:
            if alias in df.columns:
                df.rename(columns={alias: canon}, inplace=True)
                used[canon] = alias
                break

    if not headless and used:
        picks = ", ".join([f"{canon}←{alias}" for canon, alias in used.items()])
        print(f"→ Normalized headers via map ({picks})")
    return df


# ---- Normalize canonical schema ----------------------------------------------

REQUIRED_CANON = ("counterparty", "amount", "date")

def _normalize_canonical(df: pd.DataFrame, *, headless: bool) -> pd.DataFrame:
    """
    Convert columns to canonical types and ensure required columns exist.
    Minimal but safe: amount numeric, date datetime, text fields str.
    """
    df = df.copy()

    # Enforce required columns
    missing = [c for c in REQUIRED_CANON if c not in df.columns]
    if missing:
        print(f"FATAL: Missing required columns after mapping: {missing}.", file=sys.stderr)
        print("       Provide a mapping JSON via --map or preprocess your CSV first.", file=sys.stderr)
        sys.exit(2)

    # Amount -> numeric
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    # Date -> datetime (coerce; keep original string if you want to debug in audit)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Counterparty/memo/category to strings
    for col in ("counterparty", "memo", "category"):
        if col in df.columns:
            df[col] = df[col].astype(str).fillna("").str.strip()
        else:
            if col != "counterparty":  # counterparty required already
                df[col] = ""

    # Flags column optional; keep as string or empty
    if "flags" not in df.columns:
        df["flags"] = ""

    # Drop rows with NaT date or NaN amount (engine expects valid)
    bad_date = df["date"].isna()
    bad_amt = df["amount"].isna()
    dropped = int((bad_date | bad_amt).sum())
    if dropped and not headless:
        print(f"→ Dropped {dropped} row(s) with invalid date/amount")

    df = df[~(bad_date | bad_amt)].copy()
    return df


# ---- Safe write helpers -------------------------------------------------------

def _timestamped(path: str) -> str:
    base, ext = os.path.splitext(path)
    return f"{base}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}{ext}"

def _ensure_parent_dir(path: str):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

def safe_write_csv(df: pd.DataFrame, path: str, verbose: bool) -> str:
    _ensure_parent_dir(path)
    try:
        df.to_csv(path, index=False)
        return path
    except PermissionError:
        fb = _timestamped(path)
        if verbose:
            print(f"❌ Cannot write to {path} — file is open in another program.")
            print(f"   ➜ Saving to fallback: {fb}")
        df.to_csv(fb, index=False)
        return fb

def safe_write_json(obj, path: str, verbose: bool) -> str:
    _ensure_parent_dir(path)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False, default=str)
        return path
    except PermissionError:
        fb = _timestamped(path)
        if verbose:
            print(f"❌ Cannot write to {path} — file is open in another program.")
            print(f"   ➜ Saving to fallback: {fb}")
        with open(fb, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False, default=str)
        return fb


# ---- Main --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="FinLang Mk6 CLI")
    ap.add_argument("--rules", nargs="+", help="One or more .fin files (your rules). May be combined with --include-pack.")
    ap.add_argument("--include-pack", default="", help="Comma-separated starter packs to include (e.g. retail,transport,subs)")
    ap.add_argument("--input", required=True, help="Path to input CSV file")
    ap.add_argument("--output", required=True, help="Path to output CSV file")
    ap.add_argument("--map", dest="map_path", help="Optional header mapping JSON. If omitted, default packaged map is used when available.")
    ap.add_argument("--audit", help="Optional path to write audit.json")
    ap.add_argument("--audit-mode", choices=["none", "lite", "full"],
                    default=os.environ.get("FINLANG_AUDIT_MODE", "lite"),
                    help="Audit verbosity (overrides FINLANG_AUDIT_MODE).")
    ap.add_argument("--headless", action="store_true", help="Suppress console status messages")
    ap.add_argument("--fastio", action="store_true", help="Use pyarrow engine for fast CSV IO")
    ap.add_argument("--timings", action="store_true", help="Print per-stage timing breakdown")
    args = ap.parse_args()

    def log(msg: str):
        if not args.headless:
            print(msg, flush=True)

    t0 = time.perf_counter()

    # 1) Rules
    log("1. Parsing rules file(s)...")
    pack_list = [s.strip() for s in args.include_pack.split(",") if s.strip()] if args.include_pack else []
    rules_files = args.rules or []
    combined_rules_path = _combine_rules(rules_files, pack_list)

    try:
        rules = parse_fin_rules(str(combined_rules_path))
        if not rules:
            print("FATAL: No rules found in provided file(s)/packs.", file=sys.stderr)
            sys.exit(2)
        if not args.headless:
            names = [r.get("name", "<unnamed>") for r in rules]
            preview = ", ".join(names[:10]) + (f", ... (+{len(names)-10})" if len(names) > 10 else "")
            print(f"→ Parsed {len(rules)} rule(s): {preview}")
        t_rules = time.perf_counter()

        # 2) Read CSV
        log(f"2. Loading {os.path.basename(args.input)}...")
        read_kwargs: Dict[str, Any] = {}
        if args.fastio:
            try:
                import pyarrow  # noqa: F401
                read_kwargs["engine"] = "pyarrow"
            except ImportError:
                log("   (Warning: --fastio requires 'pyarrow'. Falling back to default engine.)")
        try:
            df = pd.read_csv(args.input, **read_kwargs)
        except FileNotFoundError:
            print(f"FATAL: Input CSV file not found at '{args.input}'", file=sys.stderr)
            sys.exit(1)
        t_read = time.perf_counter()

        # 3) Header mapping (map file or default)
        header_map: Optional[dict] = None
        if getattr(args, "map_path", None):
            try:
                header_map = load_header_map(args.map_path)
            except FileNotFoundError:
                print(f"(Warning) Mapping file not found: {args.map_path}. Continuing without it.", file=sys.stderr)
            except Exception as e:
                print(f"(Warning) Failed to load mapping file '{args.map_path}': {e}. Continuing.", file=sys.stderr)
        else:
            try:
                header_map = json.loads(_load_default_bank_map_text())
                if not args.headless:
                    print(f"→ Loaded default mapping: bank.map.json")
            except Exception as e:
                print(f"(Warning) Could not load default mapping file: {e}", file=sys.stderr)
                header_map = {}

        if header_map:
            df = apply_header_map(df, header_map, headless=args.headless)
            # Hybrid debit/credit synthesis if amount still missing
            amt_map = header_map.get("amount")
            if isinstance(amt_map, dict):
                df.columns = [str(c).strip().lower() for c in df.columns]
                have_amount = "amount" in df.columns
                debit_name = amt_map.get("debit")
                credit_name = amt_map.get("credit")
                have_debit = bool(debit_name and debit_name in df.columns)
                have_credit = bool(credit_name and credit_name in df.columns)
                if (have_debit or have_credit) and not have_amount:
                    debit_series = pd.to_numeric(df.get(debit_name, 0), errors="coerce").fillna(0)
                    credit_series = pd.to_numeric(df.get(credit_name, 0), errors="coerce").fillna(0)
                    df["amount"] = credit_series - debit_series
                    if not args.headless:
                        if have_debit and have_credit:
                            print("→ Synthesized 'amount' from debit/credit columns")
                        elif have_debit:
                            print("→ Synthesized 'amount' from debit only (amount = -debit)")
                        elif have_credit:
                            print("→ Synthesized 'amount' from credit only (amount = credit)")
                elif (have_debit or have_credit) and have_amount and not args.headless:
                    print("→ Amount column already present; skipping debit/credit synthesis")

        # 4) Canonical normalization
        df = _normalize_canonical(df, headless=args.headless)
        t_norm = time.perf_counter()

        # 5) Engine
        log(f"3. Applying {len(rules)} rule(s) to {len(df)} transaction(s)...")
        processed_df, audit_log = run_audit(df, rules, audit_mode=args.audit_mode)
        t_engine = time.perf_counter()

        # 6) Writes
        log(f"4. Writing {len(processed_df)} rows to {os.path.basename(args.output)}...")
        out_path = safe_write_csv(processed_df, args.output, verbose=not args.headless)

        audit_path = None
        if args.audit and args.audit_mode != "none":
            log(f"5. Writing {len(audit_log)} audit entries to {os.path.basename(args.audit)}...")
            audit_path = safe_write_json(audit_log, args.audit, verbose=not args.headless)
        t_write = time.perf_counter()

        # 7) Timing
        elapsed = time.perf_counter() - t0
        log("-" * 20)
        log("✅ Processing complete.")
        if out_path != args.output:
            log(f"   Output written to fallback: {out_path}")
        if audit_path and audit_path != args.audit:
            log(f"   Audit written to fallback:  {audit_path}")
        log(f"   Total execution time: {elapsed:.4f} seconds")

        if args.timings and not args.headless:
            print("   Breakdown (s):")
            print(f"     parse rules : {t_rules - t0:8.4f}")
            print(f"     read csv    : {t_read - t_rules:8.4f}")
            print(f"     normalize   : {t_norm - t_read:8.4f}")
            print(f"     engine      : {t_engine - t_norm:8.4f}")
            print(f"     write       : {t_write - t_engine:8.4f}")

    finally:
        try:
            if 'combined_rules_path' in locals() and combined_rules_path.exists():
                combined_rules_path.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    main()