# run_finlang.py
# FinLang — Financial Rules DSL
# Copyright (C) 2026 FinLang Ltd
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
# Removed unused unicodedata and Decimal imports
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
# from dataclasses import dataclass
from importlib import resources

# --------------------------------------------------------------------------------------
# Data Input/Hygiene Utilities (Synchronized with discover.py)
# --------------------------------------------------------------------------------------

def _auto_pick_encoding(path: str, headless: bool = False) -> str:
    """Detect encoding with sensible fallbacks."""
    # utf-8-sig handles BOM correctly and is the safest default if detection fails.
    default = "utf-8-sig"
    # Try common encodings in order of preference
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with open(path, "r", encoding=enc, errors="strict") as f:
                f.read(4096) # Read a chunk to verify
            if not headless:
                print(f"-> Auto-detected encoding: {enc}")
            return enc
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
             # If file not found, we can't detect, return default before main raises error
            return default
        except Exception:
            # Other file access error, fall back to default
            return default
    if not headless:
        print(f"-> Encoding auto-detection failed. Falling back to {default}.")
    return default


def _detect_delimiter(path: str, encoding: str = "utf-8-sig", sample_bytes: int = 65536) -> Optional[str]:
    """Heuristic delimiter detector for CSVs (EU-friendly)."""
    try:
        # Use errors="ignore" during detection phase to handle potential mixed encodings in sample
        with open(path, "r", encoding=encoding, errors="ignore") as f:
            sample = f.read(sample_bytes)
    except Exception:
        return None
    # Look at the first ~50 non-empty lines
    lines = [ln for ln in sample.splitlines() if ln.strip()][:50]
    if not lines:
        return None
    sample_text = "\n".join(lines)
    counts = {
        ";": sample_text.count(";"),
        ",": sample_text.count(","),
        "\t": sample_text.count("\t"),
        "|": sample_text.count("|"),
    }
    semi, comma, tab, pipe = counts[";"], counts[","], counts["\t"], counts["|"]
    if semi >= int(comma * 1.2) and semi > 0:
        return ";"
    if tab > max(semi, comma, pipe) and tab > 0:
        return "\t"
    if pipe > max(semi, comma, tab) and pipe > 0:
        return "|"
    if comma >= max(semi, tab, pipe) and comma > 0:
        return ","
    if semi > 0:
        return ";"
    return None

# --------------------------------------------------------------------------------------
# Version + Engine import (hardened)
# --------------------------------------------------------------------------------------
try:
    from finlang import __version__
except ImportError:
    __version__ = "0.8.1"  # fallback for standalone script execution

# Optional: keep the env var override if you ever need it for CI builds,
# otherwise just use the raw version.
if os.getenv("FINLANG_CLI_BUILD_TAG"):
    __version__ = f"{__version__}+{os.getenv('FINLANG_CLI_BUILD_TAG')}"

# Prefer packaged engine; then editable (relative) module; else fail fast (no silent mock)
try:
    from finlang.engine.finlang_engine import run_audit  # packaged install
except ImportError:
    try:
        # Editable dev path when running as "python -m finlang.cli.run_finlang"
        from ..engine.finlang_engine import run_audit
    except (ImportError, ValueError):
        print(
            "FATAL: FinLang engine not found. Ensure either the packaged engine "
            "(finlang.engine.finlang_engine) or a local engine file "
            "(src/finlang/engine/finlang_engine.py) is importable.",
            file=sys.stderr,
        )
        sys.exit(2)

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


def _read_pack_text(pack_name: str) -> Optional[str]:
    """Read a packaged rulepack by short name, with a local dev-folder fallback.

    Returns None when the pack is unknown or unreadable — a NAMED source
    that cannot be loaded is fatal upstream (4-Jul sweep: warn-and-continue
    produced partial categorisation with exit 0).
    """
    fname = PACK_MAP.get(pack_name.lower())
    if not fname:
        print(f"FATAL: Unknown pack '{pack_name}'. Known: {', '.join(sorted(PACK_MAP))}", file=sys.stderr)
        return None

    # Package-first (BOM-safe read)
    try:
        return resources.files("finlang.rulepacks").joinpath(fname).read_text(encoding="utf-8-sig")
    except Exception:
        # Local fallback (BOM-safe read)
        p = _LOCAL_RULEPACKS / fname
        if p.exists():
            return p.read_text(encoding="utf-8-sig")
        print(f"FATAL: Pack '{pack_name}' ({fname}) could not be read from the package or dev folder.", file=sys.stderr)
        return None


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
def _combine_rules(rules_files: List[str], pack_list: List[str]) -> Optional[Path]:
    """Combine named rules files + packs into one temp .fin.

    Returns None on any fatal condition. Every NAMED source must load —
    warn-and-continue on a missing file produced partial categorisation
    with exit 0 (4-Jul sweep), which an audit-positioned engine must not do.
    The sentinel is None, not Path(): Path() is Path('.') — truthy and
    .exists() — which made the callers' failure guards dead code.
    """
    parts: List[str] = []

    # 1) Personal rules first (highest precedence)
    for rf in (rules_files or []):
        p = Path(rf)
        if not p.exists():
            print(f"FATAL: Rules file not found: {p}", file=sys.stderr)
            return None
        try:
            # Ensure BOM-safe reading
            parts.append(f"# --- BEGIN {p.name} ---\n{p.read_text(encoding='utf-8-sig')}\n# --- END ---")
        except Exception as e:
            print(f"FATAL: Error reading rules file {p}: {e}", file=sys.stderr)
            return None

    # 2) Packs (lower precedence)
    for name in pack_list:
        txt = _read_pack_text(name)
        if txt is None:
            return None  # _read_pack_text printed the FATAL
        if txt:
            parts.append(f"# --- BEGIN PACK {name} ---\n{txt}\n# --- END PACK ---")

    if not parts:
        print("FATAL: No rules provided or found. Use --rules and/or --include-pack.", file=sys.stderr)
        return None

    try:
        # Write combined rules using standard utf-8
        tmp = tempfile.NamedTemporaryFile("w", delete=False, suffix=".fin", encoding="utf-8")
        tmp.write("\n\n".join(parts))
        tmp.flush()
        tmp.close()
        return Path(tmp.name)
    except Exception as e:
        print(f"FATAL: Could not create temporary rules file: {e}", file=sys.stderr)
        return None


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
        # Ensure BOM-safe reading
        content = Path(path).read_text(encoding="utf-8-sig")
    except (FileNotFoundError, IsADirectoryError):
        print(f"FATAL: Rules file issue at '{path}'", file=sys.stderr)
        return []
    except Exception as e:
        print(f"FATAL: Error parsing rules file '{path}': {e}", file=sys.stderr)
        return []

    rules: List[Dict[str, Any]] = []
    # Regex supports double quotes, single quotes, or unquoted names
    rule_pattern = re.compile(r"rule\s+(?:\"([^\"]*)\"|'([^']*)'|(\S+))\s*\{(.*?)\}",
                              re.DOTALL | re.IGNORECASE)

    for match in rule_pattern.finditer(content):
        # Find the captured name (group 1, 2, or 3)
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
_CONTROL_CHARS_RE = re.compile("[\x00-\x1F\x7F-\x9F\u200B-\u200D\u2028\u2029\uFEFF]")

# Currency/NBSP removal
_CURRENCY_NBSP_RE = re.compile("[£€$¥₹\u00A0\u202F]")


def _strip_controls_series(series: pd.Series) -> pd.Series:
    s = series.fillna("").astype(str)     # ✅ fill first, then cast
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
    # Ensure non-capturing groups (?:...) for compatibility/performance
    s_upper = s.str.upper()
    # No \b before token — handles no-space variants like 200DR (v0.7.6 fix)
    cr_mask = s_upper.str.contains(r'(?:CR|CRED|CREDIT)\.?\s*$', regex=True, na=False)
    dr_mask = s_upper.str.contains(r'(?:DR|DEB|DEBIT)\.?\s*$', regex=True, na=False)

    # Strip CR/DR tokens (case-insensitive)
    # Ensure non-capturing groups (?:...)
    s = s.str.replace(r'(?i)\s*(?:CR|CRED|CREDIT)\.?\s*$', '', regex=True)
    s = s.str.replace(r'(?i)\s*(?:DR|DEB|DEBIT)\.?\s*$', '', regex=True)

    # --- Fast path: default locale and already clean numeric strings ---
    if (decimal == "." or decimal is None) and not thousands:
        # Updated regex to include optional scientific notation: ^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$
        maybe_clean = s.str.match(r"^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$", na=False)
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
        # Check if s is potentially a view of the original series
        if not trail_mask.any(): # Simplified check based on previous operations
            s = s.copy()
        s.loc[mask_accounting] = "-" + s.loc[mask_accounting].str.slice(1, -1).str.strip()

    # Thousands removal
    if thousands:
        s = s.str.replace(thousands, "", regex=False)

    # Remove currency symbols and NBSPs (Optimized Regex)
    s = s.str.replace(_CURRENCY_NBSP_RE, "", regex=True)

    # Decimal swap (Handles localized scientific notation conversion)
    if decimal and decimal != ".":
        s = s.str.replace(decimal, ".", regex=False)

    # pd.to_numeric handles standard scientific notation (e.g. 1.23E+5)
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
    # Ensure BOM-safe reading
    with open(path, "r", encoding="utf-8-sig") as f:
        raw = json.load(f)

    mapping: dict[str, Any] = {}
    # (RC1a Patch): Normalize the entire map structure (keys and values) to lowercase and strip whitespace.
    for canon, aliases in raw.items():
        canon_l = str(canon).strip().lower()
        if isinstance(aliases, dict):
            norm: dict[str, Any] = {}
            for k, v in aliases.items():
                k_l = str(k).strip().lower()
                if isinstance(v, list):
                    # Ensure list items (aliases) are normalized
                    norm[k_l] = [str(a).strip().lower() for a in v if str(a).strip()]
                else:
                    # Ensure values (explicit names for debit/credit) are also normalized
                    norm[k_l] = str(v).strip().lower()
            mapping[canon_l] = norm
        elif isinstance(aliases, str):
            mapping[canon_l] = [aliases.strip().lower()]
        elif isinstance(aliases, list):
            mapping[canon_l] = [str(a).strip().lower() for a in aliases if str(a).strip()]
    return mapping


def apply_header_map(df: pd.DataFrame, mapping: dict, *, headless: bool) -> pd.DataFrame:
    """
    Normalize DataFrame headers using the mapping file.
    Handles standard aliases and specialized debit/credit normalization for synthesis.
    (RC1a Watertightness Patch: Enhanced debit/credit alias support)
    """
    df.columns = [str(c).strip().lower() for c in df.columns]
    used: dict[str, str] = {}
    rename_dict: dict[str, str] = {}
    current_columns = set(df.columns)

    # Helper to manage renaming and tracking usage
    def map_alias(canon, alias):
        if alias in current_columns:
            rename_dict[alias] = canon
            used[canon] = alias
            current_columns.remove(alias)
            current_columns.add(canon)
            return True
        return False

    # Phase 1: Standard aliases (including 'amount' aliases)
    for canon, spec in mapping.items():
        # Check if the canonical name already exists
        if canon in current_columns:
            continue
            
        cand_list: List[str] = []
        if isinstance(spec, str):
            cand_list = [spec]
        elif isinstance(spec, list):
            cand_list = spec
        elif isinstance(spec, dict) and canon == "amount":
            # Handle 'amount' aliases specifically
            aliases = spec.get("aliases", [])
            if isinstance(aliases, str): aliases = [aliases]
            if isinstance(aliases, list): cand_list = aliases

        for alias in cand_list:
            if map_alias(canon, alias):
                break

    # Phase 2: Debit/Credit specific handling (Surgical Patch)
    # This relies on the 'amount' specification in the map to find and normalize debit/credit columns.
    amt_spec = mapping.get("amount")
    if isinstance(amt_spec, dict):
        for leg in ("debit", "credit"):
            # If the canonical leg name already exists, skip.
            if leg in current_columns:
                continue

            # Check configuration (normalized by load_header_map)
            explicit_name = amt_spec.get(leg)
            leg_aliases = amt_spec.get(f"{leg}_aliases", [])

            # 1. Check if the exact name specified in the map exists in the CSV and map it
            if isinstance(explicit_name, str) and map_alias(leg, explicit_name):
                 continue 

            # 2. If exact name didn't match or wasn't specified, check aliases.
            if isinstance(leg_aliases, str): leg_aliases = [leg_aliases]
            
            if isinstance(leg_aliases, list):
                for alias in leg_aliases:
                    if map_alias(leg, alias):
                        break

    # Apply renames in a single batch operation
    if rename_dict:
        # Remove inplace=True (Pandas compatibility regression fix)
        df = df.rename(columns=rename_dict)

    if not headless and used:
        # Sort for deterministic output
        picks = ", ".join([f"{canon}<-{alias}" for canon, alias in sorted(used.items())])
        print(f"-> Normalized headers via map ({picks})")
    return df


# --------------------------------------------------------------------------------------
# Canonical normalization
# --------------------------------------------------------------------------------------

REQUIRED_CANON = frozenset(["counterparty", "amount", "date"])


def _normalize_canonical(
    df: pd.DataFrame,
    *,
    headless: bool,
    dayfirst: bool,
    date_format: str | None,
    strict_parse: bool,      # Explicitly pass strict configuration
    fail_threshold: float,   # Explicitly pass threshold
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

    # Ensure deterministic, timezone-naive dates (RC1 Regression Fix)
    dtype = df["date"].dtype
    try:
        from pandas import DatetimeTZDtype  # pandas >=1.0
        is_tzaware = isinstance(dtype, DatetimeTZDtype) or (getattr(dtype, "tz", None) is not None)
    except Exception:
        # very old pandas fallback
        is_tzaware = getattr(dtype, "tz", None) is not None

    if is_tzaware:
        df["date"] = df["date"].dt.tz_localize(None)

    # Ensure string cols are clean (optimized sanitizer with fast skip)
    for col in ("counterparty", "memo", "category"):
        if col in df.columns:
            df[col] = _strip_controls_series(df[col]).str.strip()
        else:
            # Ensure required 'counterparty' exists (checked earlier), initialize optional cols
            if col != "counterparty":
                df[col] = ""

    if "flags" not in df.columns:
        df["flags"] = ""

    # Coerce amount to numeric if needed before validity check
    # This assumes _to_number was already called if locale required it, 
    # or native parsing handled it. This is a final safety coercion.
    if not pd.api.types.is_numeric_dtype(df["amount"]):
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    # Validity check and Drop-Rate Guard (RC1 Requirement)
    bad_date = df["date"].isna()
    bad_amt = df["amount"].isna()
    invalid_mask = bad_date | bad_amt
    
    # reset_index: downstream audit attribution treats row identity as
    # positional; a gapped label index after drops shifted impact/reconcile
    # rule attribution for every row past the gap (4-Jul sweep F1).
    df_out = df[~invalid_mask].copy().reset_index(drop=True)

    total = len(df)
    dropped = int(invalid_mask.sum())

    if dropped and not headless:
        print(f"-> Dropped {dropped} row(s) with invalid date/amount")

    # Apply drop rate guard logic
    # Threshold is 0 if strict_parse is True, otherwise use the specified fail_threshold
    thresh = 0.0 if strict_parse else fail_threshold
    
    if total > 0 and (dropped / total) > thresh:
        msg = f"FATAL: Dropped {dropped}/{total} rows during normalization (> {thresh:.2%})."
        if strict_parse:
            # In strict mode, any drop is a failure (thresh=0.0)
            msg = f"Strict parse: {msg}"
        print(msg, file=sys.stderr)
        # Raise SystemExit to ensure non-zero exit code for validation failure
        raise SystemExit(2)

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
        # Ensure NA safety during string operations
        s = obj[c].astype(str).fillna("")
        lead = s.str.lstrip(" ")
        
        # Identify rows that are dangerous (using na=False for safety)
        is_dangerous = lead.str.startswith(DANGER, na=False)
        
        # Identify rows that are already safe (quoted)
        is_safe = s.str.startswith("'", na=False)

        # Needs fix if any row is dangerous AND not safe
        if (is_dangerous & ~is_safe).any():
            cols_to_fix.append(c)

    # Modifying a copy of the DF to maintain function purity
    df_out = df.copy()
    for c in cols_to_fix:
        s = df_out[c].astype(str).fillna("")
        lead = s.str.lstrip(" ")
        # CRITICAL FIX: NA-safe mask
        mask = lead.str.startswith(DANGER, na=False) & ~s.str.startswith("'", na=False)
        if mask.any():
            df_out.loc[mask, c] = "'" + s[mask]
    return df_out


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
        # _csv_safe_text returns a modified copy
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
       # ... (inside PermissionError handling)
        try:
            df.to_csv(fb, index=False, encoding=encoding)
        except Exception as e:
             print(f"FATAL: Failed to write to fallback {fb}: {e}", file=sys.stderr)
             raise
        return fb
    except Exception as e:
        print(f"FATAL: Failed to write CSV to {path}: {e}", file=sys.stderr)
        raise

def safe_write_json(obj, path: str, verbose: bool) -> str:
    _ensure_parent_dir(path)
    try:
        
        # Write JSON using standard utf-8
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False, default=str)
        return path
    except PermissionError:
        fb = _timestamped(path)
        if verbose:
            print(f"X Cannot write to {path} — file is open in another program.")
            print(f"   -> Saving to fallback: {fb}")
        # ... (inside PermissionError handling)
        try:
            with open(fb, "w", encoding="utf-8") as f:
                json.dump(obj, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
             print(f"FATAL: Failed to write JSON to fallback {fb}: {e}", file=sys.stderr)
             raise
        return fb
    except Exception as e:
        print(f"FATAL: Failed to write JSON to {path}: {e}", file=sys.stderr)
        raise

# --------------------------------------------------------------------------------------
# Strict Parsing Utilities (Synchronized with discover.py)
# --------------------------------------------------------------------------------------

def _assert_delimiter_consistency(path: str, encoding: str, sep: str, sample_bytes: int = 131072) -> None:
    """Verify that the detected delimiter is dominant across a representative sample."""
    try:
        # Use errors="ignore" for robustness during consistency check
        with open(path, "r", encoding=encoding, errors="ignore") as f:
            sample = f.read(sample_bytes)
    except Exception:
        return
    lines = [ln for ln in sample.splitlines() if ln.strip()][:200]
    if not lines:
        return
    seps = [",", ";", "\t", "|"]
    winners = []
    for ln in lines:
        counts = [(s, ln.count(s)) for s in seps]
        # Ensure max returns a valid result even if counts are zero
        winner = max(counts, key=lambda x: x[1])
        if winner[1] > 0:
            winners.append(winner[0])

    if not winners:
        return

    # 90% consensus threshold
    if winners.count(sep) < int(0.9 * len(winners)):
        raise ValueError(f"Strict parse: mixed delimiters detected (expected '{sep}').")

def _validate_headers(df: pd.DataFrame, *, strict: bool, headless: bool) -> None:
    """Validate DataFrame headers for emptiness and duplicates."""
    cols = list(df.columns)
    # Check for empty or whitespace-only headers
    if any(c is None or str(c).strip() == "" for c in cols):
        if strict:
            raise ValueError("Strict parse: empty/missing header detected.")
        elif not headless:
            print("WARN: empty/missing header detected.", flush=True)
    
    # Check for duplicate headers
    # Use a manual count to handle potential non-string headers correctly
    counts: dict[str, int] = {}
    for c in cols:
        s = str(c)
        counts[s] = counts.get(s, 0) + 1
        
    dups = {c for c, count in counts.items() if count > 1}
    if dups:
        if strict:
            raise ValueError(f"Strict parse: duplicate headers: {sorted(dups)}")
        elif not headless:
            print(f"WARN: duplicate headers: {sorted(dups)}", flush=True)

# --------------------------------------------------------------------------------------
# Hardened CSV reader with fast path
# --------------------------------------------------------------------------------------
def _read_csv_hardened(
    path: str,
    *,
    encoding: str = "utf-8-sig", # Ensure default is BOM-safe
    fastio: bool = False,
    decimal: str | None = None,
    thousands: str | None = None,
    headless: bool = False,
    strict_parse: bool = False, # Explicitly pass strict configuration
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
    # Ensure on_bad_lines="skip" for robustness
    base_kwargs = dict(encoding=encoding, on_bad_lines="skip")

    # EU-friendly delimiter detection (Required for strict checks)
    sep = _detect_delimiter(path, encoding=encoding)
    if sep:
        base_kwargs["sep"] = sep
        if not headless and sep != ",":
             print(f"-> Detected delimiter '{sep}' (auto)")
        
        # Strict check: Delimiter consistency
        if strict_parse:
            _assert_delimiter_consistency(path, encoding, sep)

    # --- Fast path: Native parsing (Arrow/C) when locale is standard ---
    if is_standard_locale:
        engines = []
        if fastio:
            engines.append("pyarrow")
        engines.append("c")
        
        for engine in engines:
            try:
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always", pd_errors.ParserWarning)
                    # Attempt native parse (numbers/dates inferred)
                    df = pd.read_csv(path, engine=engine, **base_kwargs)
                
                # Strict check: Header validation
                _validate_headers(df, strict=strict_parse, headless=headless)

                bad_lines = [m for m in w if issubclass(m.category, pd_errors.ParserWarning)]
                
                # 1. Warn about bad lines (if any)
                if bad_lines and not headless:
                    print(f"-> Skipped {len(bad_lines)} malformed row(s) (Native Parse - {engine} engine)")
                
                # 2. Print the Engine (Always, unless headless) -> DEDENTED to line up with 'if' above
                if not headless:
                    print(f"   (Engine: {engine})")

                # 3. Return successfully (Just once!)
                return df
            except ImportError:
                if engine == "pyarrow":
                    continue
            except (ValueError, pd_errors.ParserError) as e:
                # Catch strict check failures or parser errors
                if strict_parse:
                    raise e
                if not headless:
                    print(f"   (Info: Native parse failed ({type(e).__name__} with {engine} engine); falling back to hardened reading)")
                break # Fallback to hardened path
            except Exception as e:
                if not headless:
                    print(f"   (Info: Unexpected error during native parse ({type(e).__name__} with {engine} engine); falling back)")
                break

    # --- Hardened path: Force string read (locale-safe) ---
    hardened_kwargs = base_kwargs.copy()
    hardened_kwargs["dtype"] = str
    # Do not pass decimal/thousands args when dtype=str, as they affect native parsing behavior which we bypass here.

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
                
                # Strict check: Header validation
                _validate_headers(df, strict=strict_parse, headless=headless)

                bad_lines = [m for m in w if issubclass(m.category, pd_errors.ParserWarning)]
                if bad_lines and not headless:
                    print(f"-> Skipped {len(bad_lines)} malformed row(s) (Hardened Parse - {engine} engine)")
                return df
        except ImportError:
            if engine == "pyarrow":
                continue
        except (ValueError, pd_errors.ParserError) as e:
            # Catch strict check failures or parser errors
            last_error = e
            if strict_parse:
                raise e
            if not headless and engine != "python":
                print(f"   (Info: {engine} engine failed ({type(e).__name__}); trying next engine...)")
            continue
        except Exception as e:
            last_error = e
            if not headless and engine != "python":
                 print(f"   (Info: Unexpected error with {engine} engine ({type(e).__name__}); trying next engine...)")
            continue

    if last_error:
        raise last_error
    raise RuntimeError("CSV parsing failed with all available engines.")


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------
def main(args_list=None):
    ap = argparse.ArgumentParser(description=f"FinLang — High-Performance Financial Rules Engine ({__version__})")

    ap.add_argument("--version", action="version", version=f"FinLang {__version__}",
                    help="Show program's version number and exit.")
    ap.add_argument("--rules", nargs="+", help="One or more .fin files (your rules). May be combined with --include-pack.")
    ap.add_argument("--include-pack", default="", help="Comma-separated starter packs to include (e.g. retail,transport,subs)")
    ap.add_argument("--input", required=True, help="Path to input CSV file")
    ap.add_argument("--output", help="Path to output CSV file. Required except in impact mode (--impact-rules), which writes no categorised output.")
    ap.add_argument("--map", dest="map_path", help="Optional header mapping JSON. If omitted, default packaged map is used when available.")
    ap.add_argument("--audit", help="Optional path to write audit.json")
    ap.add_argument("--audit-mode", choices=["none", "lite", "full"],
                    default=os.environ.get("FINLANG_AUDIT_MODE", "lite"),
                    help="Audit verbosity (overrides FINLANG_AUDIT_MODE).")
    ap.add_argument("--headless", action="store_true", help="Suppress console status messages")
    ap.add_argument("--fastio", action="store_true", help="Use pyarrow engine for fast CSV IO")
    ap.add_argument("--timings", action="store_true", help="Print per-stage timing breakdown")
    

    # Internationalization and Strictness (RC1 Requirements)
    ap.add_argument("--strict-parse", action="store_true", help="Fail fast on mixed delimiters, bad headers, or excessive drops.")
    ap.add_argument("--fail-threshold", type=float, default=0.01, help="Max allowed fraction of dropped rows after normalization (0 in strict).")
    # Updated default and help text to include 'auto'
    ap.add_argument("--encoding", default="utf-8-sig", help="Input file encoding (e.g. 'utf-8', 'latin-1', 'auto'). Default: utf-8-sig.")
    ap.add_argument("--decimal", default=".", help="Decimal separator for numeric fields (e.g., '.').")
    ap.add_argument("--thousands", default=None, help="Thousands separator for numeric fields (e.g., ',').")
    ap.add_argument("--dayfirst", action="store_true", help="Parse ambiguous dates as DD/MM/YYYY (UK/EU style).")
    ap.add_argument("--date-format", default=None, help="Explicit strftime format for date parsing.")
    ap.add_argument("--output-encoding", default="utf-8", help="Encoding for output CSV (e.g., 'utf-8', 'utf-8-sig').")

    # Verification flags (v0.7.6) — post-engine integrity check
    ap.add_argument("--verify", action="store_true", help="Fast SHA-256 integrity verification after engine run.")
    ap.add_argument("--verify-full", action="store_true", help="Full integrity verification (fingerprint + field comparison).")
    ap.add_argument("--verify-output-dir", default=None, help="Directory for verification artifacts (JSON report + proof CSV). Requires --verify or --verify-full.")

    # Reconciliation flags (v0.7.8, SOL-040) — independent ML validation layer
    ap.add_argument("--reconcile", default=None, help="Path to ML output CSV to reconcile against. Requires --audit and --audit-mode full.")
    ap.add_argument("--reconcile-fields", default="category", help="Comma-separated fields to compare. Default: category.")
    ap.add_argument("--reconcile-output-dir", default=None, help="Directory for reconciliation artifacts (JSON report + mismatches CSV).")
    ap.add_argument("--reconcile-html", action="store_true", help="Additionally emit a self-contained HTML report (reconcile_report.html). Requires --reconcile and --reconcile-output-dir.")
    ap.add_argument("--reconcile-identity-fields", default=None, help="Comma-separated fields to identity-check positionally before comparison (e.g. date,amount,counterparty). Misaligned rows = structural failure (exit 1), mismatch reporting suppressed. Requires --reconcile.")
    ap.add_argument("--reconcile-key", default=None, help="Comma-separated fields forming a composite key for key-based alignment (e.g. date,amount,counterparty). Replaces positional alignment: rows match by key, row counts may differ, unmatched rows are reported as orphans (exit 3). Duplicate keys = exit 1. Requires --reconcile; mutually exclusive with --reconcile-identity-fields.")

    # Impact analysis flags (SOL-105) — rule-change impact analysis
    ap.add_argument("--impact-rules", default=None, help="Path to a candidate .fin rulepack. Activates impact analysis: the input runs through both --rules (baseline) and this candidate; behavioural differences are reported with indicative amounts. Writes no categorised output. Exit 3 on behavioural change. Requires --impact-output-dir; mutually exclusive with --reconcile and --verify.")
    ap.add_argument("--impact-output-dir", default=None, help="Directory for impact-analysis artefacts. Required in impact mode; created if absent.")
    ap.add_argument("--impact-html", action="store_true", help="Additionally emit a self-contained HTML impact report (impact_report.html). Requires --impact-rules (and --impact-output-dir).")

    ap.epilog = (
    "Environment Variables:\n"
    "  FINLANG_SAFE_TEXT=0   Disable CSV injection protection (for benchmarking)\n"
    "  FINLANG_AUDIT_MODE    Default audit mode (none|lite|full)\n"
    )

    # Parse
    try:
        if args_list is not None:
            args = ap.parse_args(args_list)
        elif sys.argv[1:]:
            args = ap.parse_args()
        # Global state variables (GLOBAL_STRICT_PARSE, etc.) are removed entirely.
        # Configuration is passed explicitly via arguments.
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

    # Validate --verify-output-dir requires --verify or --verify-full
    if args.verify_output_dir and not (args.verify or args.verify_full):
        print("FATAL: --verify-output-dir requires --verify or --verify-full.", file=sys.stderr); sys.exit(2)

    # Validate --reconcile requires --audit and --audit-mode full (SOL-040 design point)
    if args.reconcile:
        if not args.audit:
            print("FATAL: --reconcile requires --audit for mismatch reasoning.", file=sys.stderr); sys.exit(2)
        if args.audit_mode != "full":
            print("FATAL: --reconcile requires --audit-mode full for mismatch reasoning.", file=sys.stderr); sys.exit(2)
        # Reject empty/whitespace-only --reconcile-fields at parse time
        _reconcile_fields_parsed = [s.strip() for s in args.reconcile_fields.split(",") if s.strip()]
        if not _reconcile_fields_parsed:
            print("FATAL: --reconcile-fields cannot be empty (got '%s')." % args.reconcile_fields, file=sys.stderr); sys.exit(2)
    if args.reconcile_output_dir and not args.reconcile:
        print("FATAL: --reconcile-output-dir requires --reconcile.", file=sys.stderr); sys.exit(2)
    # Identity guard (SOL-103): requires --reconcile; non-empty field list
    if args.reconcile_identity_fields is not None:
        if not args.reconcile:
            print("FATAL: --reconcile-identity-fields requires --reconcile.", file=sys.stderr); sys.exit(2)
        _identity_fields_parsed = [s.strip() for s in args.reconcile_identity_fields.split(",") if s.strip()]
        if not _identity_fields_parsed:
            print("FATAL: --reconcile-identity-fields cannot be empty (got '%s')." % args.reconcile_identity_fields, file=sys.stderr); sys.exit(2)
    # Key-based alignment (SOL-104): requires --reconcile; non-empty field
    # list; mutually exclusive with the positional identity guard
    if args.reconcile_key is not None:
        if not args.reconcile:
            print("FATAL: --reconcile-key requires --reconcile.", file=sys.stderr); sys.exit(2)
        if args.reconcile_identity_fields is not None:
            print("FATAL: --reconcile-key and --reconcile-identity-fields are mutually exclusive — one replaces positional alignment, the other guards it.", file=sys.stderr); sys.exit(2)
        _key_fields_parsed = [s.strip() for s in args.reconcile_key.split(",") if s.strip()]
        if not _key_fields_parsed:
            print("FATAL: --reconcile-key cannot be empty (got '%s')." % args.reconcile_key, file=sys.stderr); sys.exit(2)
    # Impact analysis (SOL-105): analysis run, mutually exclusive with the
    # post-engine checks; writes no categorised output (--output not needed)
    if args.impact_rules:
        if args.reconcile:
            print("FATAL: --impact-rules and --reconcile are mutually exclusive — impact compares two rulepacks; reconcile compares against an external system.", file=sys.stderr); sys.exit(2)
        if args.verify or args.verify_full:
            print("FATAL: --impact-rules and --verify/--verify-full are mutually exclusive — impact expects differences by design.", file=sys.stderr); sys.exit(2)
        if not args.impact_output_dir:
            print("FATAL: --impact-rules requires --impact-output-dir.", file=sys.stderr); sys.exit(2)
    if args.impact_output_dir and not args.impact_rules:
        print("FATAL: --impact-output-dir requires --impact-rules.", file=sys.stderr); sys.exit(2)
    if args.impact_html and not args.impact_rules:
        print("FATAL: --impact-html requires --impact-rules (and --impact-output-dir).", file=sys.stderr); sys.exit(2)
    if not args.output and not args.impact_rules:
        print("FATAL: --output is required (impact mode is the only mode that writes no categorised output).", file=sys.stderr); sys.exit(2)
    # --reconcile-html requires BOTH --reconcile AND --reconcile-output-dir
    # (Branch 3 thinktank-mandated dual-flag validation: no place to write
    # the HTML without an output dir; no reconciliation to render without
    # --reconcile.)
    if args.reconcile_html:
        if not args.reconcile:
            print("FATAL: --reconcile-html requires --reconcile.", file=sys.stderr); sys.exit(2)
        if not args.reconcile_output_dir:
            print("FATAL: --reconcile-html requires --reconcile-output-dir.", file=sys.stderr); sys.exit(2)

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
    impact_combined_path = None
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
        
        # Handle auto encoding detection
        input_encoding = args.encoding
        if input_encoding.lower() == "auto":
            input_encoding = _auto_pick_encoding(args.input, headless=args.headless)

        try:
            # Pass configuration explicitly to _read_csv_hardened
            df = _read_csv_hardened(
                args.input,
                encoding=input_encoding,
                fastio=args.fastio,
                decimal=args.decimal,
                thousands=args.thousands,
                headless=args.headless,
                strict_parse=args.strict_parse,
            )
        except FileNotFoundError:
            print(f"FATAL: Input CSV file not found at '{args.input}'", file=sys.stderr)
            sys.exit(1)
        except ValueError as e:
            # Catch specific errors from strict checks
            print(f"FATAL: Failed to read CSV '{args.input}': {e}", file=sys.stderr)
            sys.exit(2)
        except Exception as e:
            print(f"FATAL: Failed to read CSV '{args.input}': {type(e).__name__}: {e}", file=sys.stderr)
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
            # (RC1a Patch): Ensure default map loading uses the robust, normalizing loader logic.
            try:
                map_text = _load_default_bank_map_text()
                if map_text and map_text.strip():
                     # Use a temporary file to utilize the normalization logic in load_header_map
                     # Use utf-8-sig for writing the temp file to match load_header_map expectation
                     tmpf_path = None
                     try:
                         with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8-sig") as tmpf:
                            tmpf.write(map_text)
                            tmpf_path = tmpf.name
                         header_map = load_header_map(tmpf_path)
                     finally:
                        # Ensure cleanup of temp file
                        if tmpf_path and os.path.exists(tmpf_path):
                             os.remove(tmpf_path)
                else:
                     header_map = {}
                     
                if not args.headless and header_map:
                    print("-> Loaded default mapping: bank.map.json")
            except Exception as e:
                if not args.headless:
                    print(f"(Warning) Failed to load or normalize default mapping: {e}. Continuing.")
                header_map = {}

        if header_map:
            # apply_header_map returns the modified dataframe and handles normalization
            df = apply_header_map(df, header_map, headless=args.headless)

        # Ensure lowercased headers for downstream logic (redundant if apply_header_map called, but safe)
        df.columns = [str(c).strip().lower() for c in df.columns]

        # Debit/credit synthesis or amount conversion (if not handled by native parse)
        
        # (RC1a Patch): Since apply_header_map normalizes aliases to 'debit' and 'credit', 
        # we check for these canonical names directly.
        have_debit = "debit" in df.columns
        have_credit = "credit" in df.columns

        # Synthesis logic
        if "amount" not in df.columns and (have_debit or have_credit):
            # If amount is missing but debit/credit exist, synthesize it.
            # We must use _to_number here as the data might be strings if read via hardened path.
            # Use canonical names 'debit'/'credit' and .get() for safety if only one exists.
            # ✅  Fixed — index-aligned zero Series fallback
            debit_series  = _to_number(
                df["debit"] if "debit" in df.columns else pd.Series(0, index=df.index),
                decimal=args.decimal, thousands=args.thousands
            )
            credit_series = _to_number(
                df["credit"] if "credit" in df.columns else pd.Series(0, index=df.index),
                decimal=args.decimal, thousands=args.thousands
            )
            
            # Calculate amount: Credit - Debit (using absolute values for safety)
            df["amount"] = credit_series.fillna(0).abs() - debit_series.fillna(0).abs()
            if not args.headless:
                # Logging here confirms synthesis occurred; specific column picks logged in apply_header_map
                print("-> Synthesized 'amount' from debit/credit columns (credit - debit, abs-safe)")
        
        elif "amount" in df.columns and not pd.api.types.is_numeric_dtype(df["amount"]):
            # If amount exists but is not numeric (hardened path), convert it.
            df["amount"] = _to_number(df["amount"], decimal=args.decimal, thousands=args.thousands)
        # If amount exists and is numeric (native path), it's already handled.

        # 4) Canonical normalization
        # Pass configuration explicitly to _normalize_canonical
        df = _normalize_canonical(
            df,
            headless=args.headless,
            dayfirst=args.dayfirst,
            date_format=args.date_format,
            strict_parse=args.strict_parse,
            fail_threshold=args.fail_threshold
        )
        
        # Check if normalization failed fatally or dropped all rows.
        if df.empty:
            # If the returned DF does not have the required columns, it indicates a fatal error (missing columns or drop rate exceeded).
            # The specific error message was already printed in _normalize_canonical.
            if not REQUIRED_CANON.issubset(df.columns):
                 sys.exit(2)
            
            # Columns exist, but 0 rows (e.g. input file was empty or all data invalid but format OK)
            log("-> DataFrame is empty after normalization. Proceeding with 0 transactions.")
            # Proceed to engine/write steps with 0 rows.

        t_norm = time.perf_counter()

        # 4b) Impact analysis mode (SOL-105): one frame, two passes,
        # vectorised diff. Replaces the normal engine+write flow — an
        # analysis run, not a production run (no categorised output).
        if args.impact_rules:
            log("3. Impact analysis: parsing candidate rulepack...")
            impact_combined_path = _combine_rules([args.impact_rules], [])
            if not impact_combined_path or not impact_combined_path.exists():
                sys.exit(2)
            candidate_rules = parse_fin_rules(str(impact_combined_path))
            if not candidate_rules:
                print("FATAL: No valid rules found in --impact-rules file.", file=sys.stderr)
                sys.exit(2)
            os.makedirs(args.impact_output_dir, exist_ok=True)

            from finlang.tools.impact import run_impact, format_summary
            log(f"4. Applying baseline ({len(rules)} rule(s)) and candidate "
                f"({len(candidate_rules)} rule(s)) to {len(df)} transaction(s)...")
            impact_result = run_impact(
                df, rules, candidate_rules,
                input_file=os.path.basename(args.input),
                baseline_rules_file=", ".join(
                    os.path.basename(p) for p in (args.rules or [])) or "(packs)",
                candidate_rules_file=os.path.basename(args.impact_rules),
                output_dir=args.impact_output_dir,
                # Hash the rule text each pass actually consumed (the
                # combined files) — ties the report to the reviewed text.
                baseline_hash_source=str(combined_rules_path),
                candidate_hash_source=str(impact_combined_path),
                emit_html=args.impact_html,
            )
            # The summary IS the deliverable of an impact run — printed
            # regardless of --headless (which suppresses status chatter).
            for line in format_summary(impact_result):
                print(line, flush=True)
            sys.exit(3 if impact_result.behavioural_changed else 0)

        # 5) Engine
        if not df.empty:
            log(f"3. Applying {len(rules)} rule(s) to {len(df)} transaction(s)...")
            # Prepare DF for engine (select relevant columns)
            engine_cols = [c for c in ["counterparty", "amount", "date", "memo", "category", "flags", "status", "exclude"] if c in df.columns]
            engine_df = df[engine_cols].copy()
            
            # Execute engine
            proc_engine_df, audit_log = run_audit(engine_df, rules, audit_mode=args.audit_mode)

            # Assign results back to original df (efficient update)
            for col in ("category", "flags", "status", "memo", "exclude"):
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

        # --- Post-engine validation phases (v0.7.6 verify, v0.7.8 reconcile) ---
        # Per SOL-040 spec: verify and reconcile are orthogonal and report
        # independently. Both run regardless of which (if any) fails. Exit
        # code 3 if either fails.
        post_engine_failure = False

        if args.verify or args.verify_full:
            from finlang.tools.verify import run_verification

            verify_mode = "full" if args.verify_full else "fast"
            verify_result = run_verification(
                input_path=args.input,
                output_path=out_path,
                mode=verify_mode,
                output_dir=args.verify_output_dir,
                headless=args.headless,
                decimal=args.decimal,
                thousands=args.thousands,
                dayfirst=args.dayfirst,
                date_format=args.date_format,
            )
            if not verify_result.success:
                post_engine_failure = True

        if args.reconcile:
            from finlang.tools.reconcile import run_reconciliation

            reconcile_fields = [s.strip() for s in args.reconcile_fields.split(",") if s.strip()]
            identity_fields = None
            if args.reconcile_identity_fields is not None:
                identity_fields = [
                    s.strip() for s in args.reconcile_identity_fields.split(",") if s.strip()
                ]
            key_fields = None
            if args.reconcile_key is not None:
                key_fields = [
                    s.strip() for s in args.reconcile_key.split(",") if s.strip()
                ]
            try:
                reconcile_result = run_reconciliation(
                    finlang_output=out_path,
                    ml_output=args.reconcile,
                    reconcile_fields=reconcile_fields,
                    output_dir=args.reconcile_output_dir,
                    audit_path=args.audit,
                    headless=args.headless,
                    emit_html=args.reconcile_html,
                    identity_fields=identity_fields,
                    key_fields=key_fields,
                )
            except FileNotFoundError as e:
                print(f"FATAL: {e}", file=sys.stderr)
                sys.exit(1)
            except ValueError as e:
                # Row count mismatch and similar structural problems
                print(f"FATAL: {e}", file=sys.stderr)
                sys.exit(1)
            if not reconcile_result.success:
                post_engine_failure = True

        if post_engine_failure:
            sys.exit(3)  # Distinct exit code for post-engine check failure

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
        # Optionally print traceback for debugging
        # import traceback; traceback.print_exc(file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            if combined_rules_path and combined_rules_path.exists():
                combined_rules_path.unlink()
        except Exception as e:
            if 'args' in locals() and not args.headless:
                print(f"(Warning) Could not delete temporary file {combined_rules_path}: {e}", file=sys.stderr)
        try:
            if impact_combined_path and impact_combined_path.exists():
                impact_combined_path.unlink()
        except Exception as e:
            if 'args' in locals() and not args.headless:
                print(f"(Warning) Could not delete temporary file {impact_combined_path}: {e}", file=sys.stderr)


if __name__ == "__main__":
    # Ensure compatibility with PYTHONWARNINGS=error policy
    if not sys.warnoptions:
        import warnings
        warnings.simplefilter("default")
    main()