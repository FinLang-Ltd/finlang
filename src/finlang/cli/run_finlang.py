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
# Removed unused unicodedata import
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from importlib import resources

# --------------------------------------------------------------------------------------
# Version / Engine import
# --------------------------------------------------------------------------------------
try:
    from finlang import __version__ as _pkg_version
except ImportError:
    _pkg_version = "0.6.2"  # fallback if package isn't importable

CLI_BUILD_TAG = os.getenv("FINLANG_CLI_BUILD_TAG", "optimized-final")
__version__ = f"{_pkg_version}+cli-{CLI_BUILD_TAG}"

try:
    from finlang.engine.finlang_engine_v0_5_2 import run_audit
except ImportError:
    # Minimal mock for environments where engine isn't importable
    def run_audit(df, rules, audit_mode="lite"):
        proc_df = df.copy()
        if "category" not in proc_df.columns:
            proc_df["category"] = ""
        if "flags" not in proc_df.columns:
            proc_df["flags"] = ""
        return proc_df, []


# --------------------------------------------------------------------------------------
# Starter packs and Resource Helpers
# --------------------------------------------------------------------------------------
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

try:
    _THIS_DIR = Path(__file__).resolve().parent           # .../src/finlang/cli
    _PKG_ROOT = _THIS_DIR.parent                          # .../src/finlang
    _LOCAL_RULEPACKS = _PKG_ROOT / "rulepacks"
except NameError:
    _THIS_DIR = Path(".").resolve()
    _PKG_ROOT = _THIS_DIR
    _LOCAL_RULEPACKS = _PKG_ROOT / "rulepacks"


def _read_pack_text(pack_name: str) -> str:
    """Read a packaged rulepack by short name, with a local dev-folder fallback."""
    fname = PACK_MAP.get(pack_name.lower())
    if not fname:
        print(f"Unknown pack '{pack_name}'. Known: {', '.join(sorted(PACK_MAP))}", file=sys.stderr)
        return ""

    # Package-first
    try:
        return resources.files("finlang.rulepacks").joinpath(fname).read_text(encoding="utf-8")
    except Exception:
        # Local fallback
        p = _LOCAL_RULEPACKS / fname
        if p.exists():
            return p.read_text(encoding="utf-8")
        return ""  # be permissive in CLI; earlier stage will catch missing rules


def _load_default_bank_map_text() -> str:
    """Load default bank.map.json from package, with robust dev-folder fallback."""
    fname = "bank.map.json"
    # Try packaged resource first (BOM-safe)
    try:
        return resources.files("finlang.mapping").joinpath(fname).read_text(encoding="utf-8-sig")
    except Exception:
        pass

    # Fallbacks
    here = _THIS_DIR
    candidates = [
        here / "mapping" / fname,
        here.parent / "mapping" / fname,
        here.parent / "finlang" / "mapping" / fname,
    ]
    for p in candidates:
        if p.exists():
            return p.read_text(encoding="utf-8-sig")
    return "{}"


# --------------------------------------------------------------------------------------
# Rules concatenation & parsing
# --------------------------------------------------------------------------------------
def _combine_rules(rules_files: List[str], pack_list: List[str]) -> Path:
    parts: List[str] = []

    # 1) Personal rules first (highest precedence)
    for rf in (rules_files or []):
        p = Path(rf)
        if not p.exists():
            print(f"Rules file not found: {p}", file=sys.stderr)
            continue
        try:
            parts.append(f"# --- BEGIN {p.name} ---\n{p.read_text(encoding='utf-8-sig')}\n# --- END ---")
        except Exception as e:
            print(f"Error reading rules file {p}: {e}", file=sys.stderr)

    # 2) Packs (lower precedence)
    for name in pack_list:
        txt = _read_pack_text(name)
        if txt:
            parts.append(f"# --- BEGIN PACK {name} ---\n{txt}\n# --- END PACK ---")

    if not parts:
        print("FATAL: No rules provided or found. Use --rules and/or --include-pack.", file=sys.stderr)
        return Path()

    try:
        tmp = tempfile.NamedTemporaryFile("w", delete=False, suffix=".fin", encoding="utf-8")
        tmp.write("\n\n".join(parts))
        tmp.flush()
        tmp.close()
        return Path(tmp.name)
    except Exception as e:
        print(f"FATAL: Could not create temporary rules file: {e}", file=sys.stderr)
        return Path()


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
            if i + 1 < len(line) and line[i:i + 2] == '//':
                return line[:i].rstrip()
        i += 1
    return line


def parse_fin_rules(path: str) -> List[Dict[str, Any]]:
    try:
        content = Path(path).read_text(encoding="utf-8-sig")
    except (FileNotFoundError, IsADirectoryError):
        print(f"FATAL: Rules file issue at '{path}'", file=sys.stderr)
        return []
    except Exception as e:
        print(f"FATAL: Error parsing rules file '{path}': {e}", file=sys.stderr)
        return []

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


# --------------------------------------------------------------------------------------
# Data hardening (optimized)
# --------------------------------------------------------------------------------------

# Compact regex covering C0, DEL, C1, and common problem format chars (ZW*, LS, PS, BOM)
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1F\x7F-\x9F\u200B-\u200D\u2028\u2029\uFEFF]")

# Currency/NBSP removal
_CURRENCY_NBSP_RE = re.compile(r"[£€$¥₹\u00A0\u202F]")


def _strip_controls_series(series: pd.Series) -> pd.Series:
    """Vectorized control-char stripping with fast skip for clean columns."""
    # Ensure string type and treat nulls as empty strings
    s = series.astype(str).fillna("")
    # Fast skip when no control chars (Guarded Apply)
    # Use na=False to ensure boolean output for .any()
    maybe = s.str.contains(_CONTROL_CHARS_RE, regex=True, na=False)
    if not maybe.any():
        return s
    return s.str.replace(_CONTROL_CHARS_RE, "", regex=True)


def _to_number(series: pd.Series, decimal: str, thousands: Optional[str]) -> pd.Series:
    """Optimized number conversion with locale hardening (Synchronized)."""
    # Already numeric -> done
    if pd.api.types.is_numeric_dtype(series.dtype):
        return pd.to_numeric(series, errors="coerce")

    s = series.astype(str).str.strip()

    # --- Sign normalization (always) ---
    # Unicode minus (U+2212) -> '-'
    s = s.str.replace('\u2212', '-', regex=False)

    # Trailing minus: '123,45-' -> '-123,45'
    trail_mask = s.str.endswith('-', na=False)
    if trail_mask.any():
        s = s.copy()
        s.loc[trail_mask] = '-' + s.loc[trail_mask].str[:-1]

    # Capture CR/DR indicators (case-insensitive) before stripping
    s_upper = s.str.upper()
    cr_mask = s_upper.str.contains(r'\b(?:CR|CRED|CREDIT)\b\.?\s*$', regex=True, na=False)
    dr_mask = s_upper.str.contains(r'\b(?:DR|DEB|DEBIT)\b\.?\s*$', regex=True, na=False)

    # Strip CR/DR tokens (case-insensitive)
    s = s.str.replace(r'\s*(CR|CRED|CREDIT)\.?\s*$', '', regex=True, case=False)
    s = s.str.replace(r'\s*(DR|DEB|DEBIT)\.?\s*$', '', regex=True, case=False)

    # --- Fast path: default locale and already clean numeric strings ---
    if (decimal == "." or decimal is None) and not thousands:
        maybe_clean = s.str.match(r"^[+-]?\d+(\.\d+)?$", na=False)
        if maybe_clean.all():
            vals = pd.to_numeric(s, errors="coerce")
            # Apply CR/DR semantics: DR => negative, CR => positive
            if dr_mask.any():
                vals = vals.copy()
                vals.loc[dr_mask] = vals.loc[dr_mask].abs() * -1
            if cr_mask.any():
                vals = vals.copy()
                vals.loc[cr_mask] = vals.loc[cr_mask].abs()
            return vals

    # --- Full canonicalization tail (baseline parity) ---
    # Accounting negatives: (123.45) -> -123.45
    mask_accounting = s.str.startswith("(", na=False) & s.str.endswith(")", na=False)
    if mask_accounting.any():
        # Copy only if we didn't already copy for trailing minus
        if not trail_mask.any():
            s = s.copy()
        s.loc[mask_accounting] = "-" + s.loc[mask_accounting].str.slice(1, -1).str.strip()

    # Thousands removal
    if thousands:
        s = s.str.replace(thousands, "", regex=False)

    # Remove currency symbols and NBSPs (Optimized Regex)
    s = s.str.replace(_CURRENCY_NBSP_RE, "", regex=True)

    # Decimal swap
    if decimal and decimal != ".":
        s = s.str.replace(decimal, ".", regex=False)

    vals = pd.to_numeric(s, errors="coerce")
    # Apply CR/DR semantics: DR => negative, CR => positive
    if dr_mask.any():
        vals = vals.copy()  # Ensure copy before modification
        vals.loc[dr_mask] = vals.loc[dr_mask].abs() * -1
    if cr_mask.any():
        vals = vals.copy()  # Ensure copy before modification
        vals.loc[cr_mask] = vals.loc[cr_mask].abs()
    return vals


def load_header_map(path: str) -> dict:
    with open(path, "r", encoding="utf-8-sig") as f:
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
    rename_dict: dict[str, str] = {}
    current_columns = set(df.columns)

    for canon, spec in mapping.items():
        if canon in current_columns:
            continue
        cand_list: List[str] = []
        if isinstance(spec, str):
            cand_list = [spec]
        elif isinstance(spec, list):
            cand_list = spec
        elif isinstance(spec, dict) and canon == "amount":
            aliases = spec.get("aliases", [])
            if isinstance(aliases, str):
                aliases = [aliases]
            cand_list = aliases

        for alias in cand_list:
            if alias in current_columns:
                rename_dict[alias] = canon
                used[canon] = alias
                current_columns.remove(alias)
                current_columns.add(canon)
                break

    # Apply renames in a single batch operation
    if rename_dict:
        df.rename(columns=rename_dict, inplace=True)

    if not headless and used:
        picks = ", ".join([f"{canon}<-{alias}" for canon, alias in used.items()])
        print(f"-> Normalized headers via map ({picks})")
    return df


# --------------------------------------------------------------------------------------
# Canonical normalization
# --------------------------------------------------------------------------------------

REQUIRED_CANON = frozenset(["counterparty", "amount", "date"])


def _normalize_canonical(
    df: pd.DataFrame, *, headless: bool, dayfirst: bool, date_format: str | None
) -> pd.DataFrame:
    """Convert to canonical types and ensure required columns exist."""
    
    # Check required columns before making a copy
    missing = REQUIRED_CANON - set(df.columns)
    if missing:
        print(f"FATAL: Missing required columns after mapping: {sorted(list(missing))}.", file=sys.stderr)
        print("       Provide a mapping JSON via --map or preprocess your CSV first.", file=sys.stderr)
        return pd.DataFrame() # Return empty DF to signal fatal error

    df = df.copy()

    # Date → datetime (skip if already datetime from fast path)
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        if date_format:
            df["date"] = pd.to_datetime(df["date"], format=date_format, errors="coerce")
        else:
            # Use cache=True for speedup
            df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=dayfirst, cache=True)

    # Ensure string cols are clean (optimized sanitizer with fast skip)
    for col in ("counterparty", "memo", "category"):
        if col in df.columns:
            df[col] = _strip_controls_series(df[col]).str.strip()
        else:
            if col != "counterparty":
                df[col] = ""

    if "flags" not in df.columns:
        df["flags"] = ""

    # Coerce amount to numeric if needed before validity check
    if not pd.api.types.is_numeric_dtype(df["amount"]):
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    bad_date = df["date"].isna()
    bad_amt = df["amount"].isna()
    dropped = int((bad_date | bad_amt).sum())
    if dropped and not headless:
        print(f"-> Dropped {dropped} row(s) with invalid date/amount")

    df_out = df[~(bad_date | bad_amt)].copy()
    return df_out


# --------------------------------------------------------------------------------------
# Safe write helpers
# --------------------------------------------------------------------------------------

def _csv_safe_text(df: pd.DataFrame) -> pd.DataFrame:
    """Optimized and NA-Safe: Escapes cells that could be interpreted as formulas."""
    DANGER = ("=", "+", "-", "@", "\t")
    obj = df.select_dtypes(include="object")
    if obj.empty:
        return df

    # Column-level pre-checks (Guarded Apply) to avoid scanning everything
    cols_to_fix: List[str] = []
    for c in obj.columns:
        s = obj[c].astype(str)
        lead = s.str.lstrip(" ")
        
        # Identify rows that are dangerous (using na=False for safety)
        is_dangerous = lead.str.startswith(DANGER, na=False)
        
        # Identify rows that are already safe (quoted)
        is_safe = s.str.startswith("'", na=False)

        # Needs fix if any row is dangerous AND not safe
        if (is_dangerous & ~is_safe).any():
            cols_to_fix.append(c)

    # In this CLI context, modifying in place just before write is acceptable for performance.
    for c in cols_to_fix:
        s = df[c].astype(str)
        lead = s.str.lstrip(" ")
        # CRITICAL FIX: NA-safe mask to avoid propagating NaNs through bitwise ops
        mask = lead.str.startswith(DANGER, na=False) & ~s.str.startswith("'", na=False)
        if mask.any():
            df.loc[mask, c] = "'" + s[mask]
    return df


def _timestamped(path: str) -> str:
    base, ext = os.path.splitext(path)
    return f"{base}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}{ext}"


def _ensure_parent_dir(path: str):
    parent = os.path.dirname(path)
    if parent and parent != "." and parent != os.path.sep:
        os.makedirs(parent, exist_ok=True)

"""
Note:
  Set environment variable FINLANG_SAFE_TEXT=0 to skip spreadsheet formula
  injection protection during CSV output. Useful for benchmarks or CI runs.
"""

def safe_write_csv(df: pd.DataFrame, path: str, verbose: bool, encoding: str) -> str:
    _ensure_parent_dir(path)

    # Allow disabling safe text via env (benchmarks)
    if str(os.getenv("FINLANG_SAFE_TEXT", "1")).lower() not in ("0", "false", "no"):
        # _csv_safe_text modifies df in place
        df = _csv_safe_text(df)
    elif verbose:
        print("-> Skipping CSV injection protection (FINLANG_SAFE_TEXT=0)")

    try:
        df.to_csv(path, index=False, encoding=encoding)
        return path
    except PermissionError:
        fb = _timestamped(path)
        if verbose:
            print(f"X Cannot write to {path} — file is open in another program.")
            print(f"   -> Saving to fallback: {fb}")
        try:
            df.to_csv(fb, index=False, encoding=encoding)
        except Exception as e:
             print(f"FATAL: Failed to write to fallback {fb}: {e}", file=sys.stderr)
        return fb
    except Exception as e:
        print(f"FATAL: Failed to write CSV to {path}: {e}", file=sys.stderr)
        return path


def safe_write_json(obj, path: str, verbose: bool) -> str:
    _ensure_parent_dir(path)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False, default=str)
        return path
    except PermissionError:
        fb = _timestamped(path)
        if verbose:
            print(f"X Cannot write to {path} — file is open in another program.")
            print(f"   -> Saving to fallback: {fb}")
        try:
            with open(fb, "w", encoding="utf-8") as f:
                json.dump(obj, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
             print(f"FATAL: Failed to write JSON to fallback {fb}: {e}", file=sys.stderr)
        return fb
    except Exception as e:
        print(f"FATAL: Failed to write JSON to {path}: {e}", file=sys.stderr)
        return path


# --------------------------------------------------------------------------------------
# Hardened CSV reader with fast path
# --------------------------------------------------------------------------------------
def _read_csv_hardened(
    path: str,
    *,
    encoding: str = "utf-8",
    fastio: bool = False,
    decimal: str | None = None,
    thousands: str | None = None,
    headless: bool = False,
) -> pd.DataFrame:
    """
    Robust CSV loader. Tries native parsing (fast path) first, then falls back
    to a string-only hardened path (locale-safe, injection-safe).
    """
    import warnings
    try:
        import pandas.errors as pd_errors
    except ImportError:
        # Mock errors if pandas internals are restricted
        class MockParserWarning(Warning): pass
        class MockParserError(Exception): pass
        pd_errors = type("MockErrors", (object,), {"ParserWarning": MockParserWarning, "ParserError": MockParserError})

    is_standard_locale = (decimal in (".", None)) and (thousands is None)
    base_kwargs = dict(encoding=encoding, on_bad_lines="warn")

    # Fast path: let Arrow/C parse numbers and dates when safe
    if is_standard_locale:
        engines = []
        if fastio:
            engines.append("pyarrow")
        engines.append("c")
        for engine in engines:
            try:
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always", pd_errors.ParserWarning)
                    df = pd.read_csv(path, engine=engine, **base_kwargs)
                    bad_lines = [m for m in w if issubclass(m.category, pd_errors.ParserWarning)]
                    if bad_lines and not headless:
                        print(f"-> Skipped {len(bad_lines)} malformed row(s) (Native Parse - {engine} engine)")
                    return df
            except ImportError:
                if engine == "pyarrow":
                    continue
            except Exception as e:
                if not headless:
                    print(f"   (Info: Native parse failed ({type(e).__name__} with {engine} engine); falling back to hardened reading)")
                break

    # Hardened path: force strings; we will coerce types later
    hardened_kwargs = base_kwargs.copy()
    hardened_kwargs["dtype"] = str
    if decimal and decimal != ".":
        hardened_kwargs["decimal"] = decimal
    if thousands:
        hardened_kwargs["thousands"] = thousands

    engines_to_try = []
    if fastio:
        engines_to_try.append("pyarrow")
    engines_to_try.extend(["c", "python"])

    last_error = None
    for engine in engines_to_try:
        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always", pd_errors.ParserWarning)
                df = pd.read_csv(path, engine=engine, **hardened_kwargs)
                bad_lines = [m for m in w if issubclass(m.category, pd_errors.ParserWarning)]
                if bad_lines and not headless:
                    print(f"-> Skipped {len(bad_lines)} malformed row(s) (Hardened Parse - {engine} engine)")
                return df
        except ImportError:
            if engine == "pyarrow":
                continue
        except Exception as e:
            last_error = e
            if not headless and engine != "python":
                print(f"   (Info: {engine} engine failed ({type(e).__name__}); trying next engine...)")
            continue

    if last_error:
        raise last_error
    raise RuntimeError("CSV parsing failed with all available engines.")


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------
def main(args_list=None):
    ap = argparse.ArgumentParser(description="FinLang Mk6 CLI (optimized)")

    ap.add_argument("--version", action="version", version=f"FinLang {__version__}",
                    help="Show program's version number and exit.")
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
    ap.epilog = (
    "Environment Variables:\n"
    "  FINLANG_SAFE_TEXT=0   Disable CSV injection protection (for benchmarking)\n"
    "  FINLANG_AUDIT_MODE    Default audit mode (none|lite|full)\n"
)

    # Internationalization
    ap.add_argument("--encoding", default="utf-8", help="Input CSV file encoding (e.g., 'utf-8', 'latin-1').")
    ap.add_argument("--decimal", default=".", help="Decimal separator for numeric fields (e.g., '.').")
    ap.add_argument("--thousands", default=None, help="Thousands separator for numeric fields (e.g., ',').")
    ap.add_argument("--dayfirst", action="store_true", help="Parse ambiguous dates as DD/MM/YYYY (UK/EU style).")
    ap.add_argument("--date-format", default=None, help="Explicit strftime format for date parsing.")
    ap.add_argument("--output-encoding", default="utf-8", help="Encoding for output CSV (e.g., 'utf-8', 'utf-8-sig').")

    # Parse
    try:
        if args_list is not None:
            args = ap.parse_args(args_list)
        elif sys.argv[1:]:
            args = ap.parse_args()
        else:
            # If run without arguments
            ap.print_help()
            sys.exit(0)
    except SystemExit as e:
        # ArgumentParser calls sys.exit() on error or --help/--version. Propagate it.
        if e.code is not None:
            sys.exit(e.code)
        return

    # Validate separators (Exit codes reinstated for CLI behavior)
    if args.decimal is not None and len(args.decimal) != 1:
        print("FATAL: --decimal must be a single character '.' or ','.", file=sys.stderr); sys.exit(2)
    if args.thousands is not None and len(args.thousands) != 1:
        print("FATAL: --thousands must be a single character (e.g., ',' or '.').", file=sys.stderr); sys.exit(2)
    if args.decimal and args.thousands and args.decimal == args.thousands:
        print("FATAL: --decimal and --thousands cannot be the same.", file=sys.stderr); sys.exit(2)

    # Check pyarrow if fastio is requested
    if args.fastio:
        try:
            import pyarrow  # noqa: F401
        except ImportError:
            if not args.headless:
                print("   (Info: --fastio requires 'pyarrow'. Falling back to default IO behavior.)")
            args.fastio = False

    def log(msg: str):
        if not args.headless:
            print(msg, flush=True)

    t0 = time.perf_counter()
    combined_rules_path = None
    # Initialize timing markers
    t_rules, t_read, t_norm, t_engine, t_write = t0, t0, t0, t0, t0


    try:
        # 1) Rules
        log("1. Parsing rules file(s)...")
        pack_list = [s.strip() for s in args.include_pack.split(",") if s.strip()] if args.include_pack else []
        rules_files = args.rules or []

        combined_rules_path = _combine_rules(rules_files, pack_list)
        if not combined_rules_path or not combined_rules_path.exists():
            sys.exit(2) # Exit if rule combination failed fatally

        rules = parse_fin_rules(str(combined_rules_path))
        if not rules:
            # Ensure user knows if file was >0 bytes but contained no valid rules
            if combined_rules_path.stat().st_size > 0:
                 print("FATAL: No valid rules found in provided file(s)/packs.", file=sys.stderr)
            sys.exit(2)

        if not args.headless:
            names = [r.get("name", "<unnamed>") for r in rules]
            preview = ", ".join(names[:10]) + (f", ... (+{len(names)-10})" if len(names) > 10 else "")
            print(f"-> Parsed {len(rules)} rule(s): {preview}")
        t_rules = time.perf_counter()

        # 2) Read CSV
        log(f"2. Loading {os.path.basename(args.input)}...")
        try:
            df = _read_csv_hardened(
                args.input,
                encoding=args.encoding,
                fastio=args.fastio,
                decimal=args.decimal,
                thousands=args.thousands,
                headless=args.headless,
            )
        except FileNotFoundError:
            print(f"FATAL: Input CSV file not found at '{args.input}'", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"FATAL: Failed to read CSV '{args.input}': {e}", file=sys.stderr)
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
                map_text = _load_default_bank_map_text()
                header_map = json.loads(map_text) if map_text and map_text.strip() else {}
                if not args.headless and header_map:
                    print("-> Loaded default mapping: bank.map.json")
            except Exception as e:
                if not args.headless:
                    print(f"(Warning) Failed to load default mapping: {e}. Continuing.")
                header_map = {}

        if header_map:
            df = apply_header_map(df, header_map, headless=args.headless)

        # Ensure lowercased headers for downstream logic
        df.columns = [str(c).strip().lower() for c in df.columns]

        # Debit/credit synthesis or amount conversion
        amt_map = header_map.get("amount", {}) if header_map else {}
        debit_name = amt_map.get("debit")
        if isinstance(debit_name, str): debit_name = debit_name.strip().lower()
        credit_name = amt_map.get("credit")
        if isinstance(credit_name, str): credit_name = credit_name.strip().lower()

        have_debit = bool(debit_name and debit_name in df.columns)
        have_credit = bool(credit_name and credit_name in df.columns)

        if "amount" not in df.columns and (have_debit or have_credit):
            debit_series  = _to_number(df.get(debit_name, "0"), decimal=args.decimal, thousands=args.thousands)
            credit_series = _to_number(df.get(credit_name, "0"), decimal=args.decimal, thousands=args.thousands)
            df["amount"] = credit_series.fillna(0).abs() - debit_series.fillna(0).abs()
            if not args.headless:
                print("-> Synthesized 'amount' from debit/credit columns (credit - debit, abs-safe)")
        elif "amount" in df.columns:
            df["amount"] = _to_number(df["amount"], decimal=args.decimal, thousands=args.thousands)

        # 4) Canonical normalization
        df = _normalize_canonical(df, headless=args.headless, dayfirst=args.dayfirst, date_format=args.date_format)
        
        # Check if normalization failed fatally or dropped all rows.
        if df.empty:
            if not REQUIRED_CANON.issubset(df.columns):
                 # Fatal error (missing required columns, error already printed in _normalize_canonical)
                 sys.exit(2)
            # Columns exist, but 0 rows (all data invalid)
            log("-> DataFrame is empty after normalization. Proceeding with 0 transactions.")
            # Proceed to engine/write steps with 0 rows.

        t_norm = time.perf_counter()

        # 5) Engine
        if not df.empty:
            log(f"3. Applying {len(rules)} rule(s) to {len(df)} transaction(s)...")
            engine_cols = [c for c in ["counterparty", "amount", "date", "memo", "category", "flags"] if c in df.columns]
            engine_df = df[engine_cols].copy()
            proc_engine_df, audit_log = run_audit(engine_df, rules, audit_mode=args.audit_mode)

            # Assign back to original df (no full copy)
            for col in ("category", "flags"):
                if col in proc_engine_df.columns:
                    df[col] = proc_engine_df[col]
        else:
            log("3. Skipping engine (0 transactions).")
            audit_log = []
            
        t_engine = time.perf_counter()

        # 6) Writes
        log(f"4. Writing {len(df)} rows to {os.path.basename(args.output)}...")
        out_path = safe_write_csv(df, args.output, verbose=not args.headless, encoding=args.output_encoding)

        audit_path = None
        if args.audit and args.audit_mode != "none":
            log(f"5. Writing {len(audit_log)} audit entries to {os.path.basename(args.audit)}...")
            audit_path = safe_write_json(audit_log, args.audit, verbose=not args.headless)
        t_write = time.perf_counter()

        # 7) Timing
        elapsed = time.perf_counter() - t0
        log("-" * 20)
        log("OK. Processing complete.")
        if out_path != args.output:
            log(f"   Output written to fallback: {out_path}")
        if audit_path and audit_path != args.audit:
            log(f"   Audit written to fallback:  {audit_path}")
        log(f"   Total execution time: {elapsed:.4f} seconds")

        if args.timings and not args.headless:
            # Use max(0, ...) to ensure non-negative timings
            print("   Breakdown (s):")
            print(f"     parse rules : {max(0, t_rules - t0):8.4f}")
            print(f"     read csv    : {max(0, t_read - t_rules):8.4f}")
            print(f"     normalize   : {max(0, t_norm - t_read):8.4f}")
            print(f"     engine      : {max(0, t_engine - t_norm):8.4f}")
            print(f"     write       : {max(0, t_write - t_engine):8.4f}")

    except SystemExit as e:
        # Handle controlled exits
        if e.code != 0:
             # Avoid redundant messages if the error was already printed
             pass
        # Ensure the process exits with the correct code
        if e.code is not None:
            sys.exit(e.code)
            
    except Exception as e:
        # Catch unexpected errors during execution
        print(f"An unexpected error occurred during processing: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            if combined_rules_path and combined_rules_path.exists():
                combined_rules_path.unlink()
        except Exception as e:
            if 'args' in locals() and not args.headless:
                print(f"(Warning) Could not delete temporary file {combined_rules_path}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()