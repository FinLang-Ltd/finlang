# discover.py
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


import pandas as pd
# Removed unused Decimal imports as pipeline relies on float64
# from decimal import Decimal, ROUND_HALF_UP
# from dataclasses import dataclass
import re
import unicodedata
import argparse
import sys
import os
from typing import Tuple, Optional, Any, List

# --------------------------------------------------------------------------------------
# Data Hardening Utilities (Synchronized with run_finlang_v0_6_4_rc1a.py)
# --------------------------------------------------------------------------------------

# Compact regex covering C0, DEL, C1, and common problem format chars (ZW*, LS, PS, BOM)
_CONTROL_CHARS_RE = re.compile("[\x00-\x1F\x7F-\x9F\u200B-\u200D\u2028\u2029\uFEFF]")

# Currency/NBSP removal (Required by _to_number)
_CURRENCY_NBSP_RE = re.compile("[£€$¥₹\u00A0\u202F]")

def _strip_controls_series(series: pd.Series) -> pd.Series:
    s = series.fillna("").astype(str)     # ✅ fill first, then cast
    maybe = s.str.contains(_CONTROL_CHARS_RE, regex=True, na=False)
    if not maybe.any():
        return s
    return s.str.replace(_CONTROL_CHARS_RE, "", regex=True)

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

    if winners.count(sep) < int(0.9 * len(winners)):
        raise ValueError(f"Strict parse: mixed delimiters detected (expected '{sep}').")


def _validate_headers(df: pd.DataFrame, *, strict: bool, headless: bool) -> None:
    """Validate DataFrame headers for emptiness and duplicates."""
    cols = list(df.columns)
    # Check for empty or whitespace-only headers
    if any((c is None) or (str(c).strip() == "") for c in cols):
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


def _clean_counterparty(s: pd.Series) -> pd.Series:
    """Normalizes a series of strings to create a fingerprint."""
    # Use the optimized, vectorized control stripping
    s = s.fillna('').astype(str).pipe(_strip_controls_series)
    # Normalize accents and special characters (e.g., CAFÉ -> CAFE)
    s = s.map(lambda x: unicodedata.normalize('NFKD', x).encode('ascii', 'ignore').decode('ascii'))
    # Standard cleaning: uppercase, remove punctuation, collapse whitespace
    s = s.str.upper()
    s = s.str.replace(r'[^A-Z0-9\s]', ' ', regex=True)
    s = s.str.replace(r'\s+', ' ', regex=True).str.strip()
    return s

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

    # Modifying a copy of the DF to avoid side effects, as this function might be reused.
    df_out = df.copy()
    for c in cols_to_fix:
        s = df_out[c].astype(str).fillna("")
        lead = s.str.lstrip(" ")
        # CRITICAL FIX: NA-safe mask to avoid propagating NaNs through bitwise ops
        mask = lead.str.startswith(DANGER, na=False) & ~s.str.startswith("'", na=False)
        if mask.any():
            df_out.loc[mask, c] = "'" + s[mask]
    return df_out

def _read_csv_hardened(
    path: str,
    *,
    encoding: str = "utf-8-sig", # Ensure default is BOM-safe
    fastio: bool = False,
    headless: bool = False,
    strict_parse: bool = False, # Explicitly pass strict configuration
) -> pd.DataFrame:
    """
    Robust CSV loader that warns and skips malformed rows, with engine fallbacks.
    Reads all data as strings to ensure deterministic parsing.
    """
    import warnings
    # Handle potential import variations for pandas errors
    try:
        import pandas.errors as pd_errors
    except ImportError:
        # Mock errors if pandas internals are restricted or for older versions
        class MockParserWarning(Warning): pass
        class MockParserError(Exception): pass
        pd_errors = type("MockErrors", (object,), {"ParserWarning": MockParserWarning, "ParserError": MockParserError})

    # Ensure on_bad_lines="skip" for robustness
    read_kwargs = dict(encoding=encoding, on_bad_lines="skip", dtype=str)
    
    # EU-friendly delimiter detection
    sep = _detect_delimiter(path, encoding=encoding)
    if sep:
        # Always use the detected separator
        read_kwargs["sep"] = sep
        if not headless and sep != ",":
            print(f"-> Detected delimiter '{sep}' (auto)")
        
        # Strict check: Delimiter consistency
        if strict_parse:
            _assert_delimiter_consistency(path, encoding, sep)

    # --- Engine execution loop ---
    engines_to_try = []
    if fastio:
        engines_to_try.append("pyarrow")
    engines_to_try.extend(["c", "python"])

    last_error = None
    for engine in engines_to_try:
        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always", pd_errors.ParserWarning)
                df = pd.read_csv(path, engine=engine, **read_kwargs)
                
                # Strict check: Header validation
                _validate_headers(df, strict=strict_parse, headless=headless)

                bad_lines = [m for m in w if issubclass(m.category, pd_errors.ParserWarning)]
                if bad_lines and not headless:
                    print(f"-> Skipped {len(bad_lines)} malformed row(s) ({engine} engine)")
                
                # --- NEW BLOCK START ---
                if not headless:
                    print(f"   (Engine: {engine})")
                # --- NEW BLOCK END ---

                return df
        except ImportError:
            if engine == "pyarrow":
                continue
        except (pd_errors.ParserError, ValueError) as e:
            # Catch ParserError (e.g. C engine failure) and ValueError (e.g. strict checks)
            last_error = e
            if strict_parse:
                # If strict mode fails (e.g. mixed delimiters), fail fast
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
        # If all engines failed, re-raise the last error
        raise last_error
    
    # Should be unreachable if engines are available, but as a safeguard:
    raise RuntimeError("CSV parsing failed with all available engines.")


def discover_candidates(
    df: pd.DataFrame,
    counterparty_col: str = "counterparty",
    category_col: str = "category",
    amount_col: str = "amount",
    date_col: str = "date",
    min_count: int = 5,
    min_amount: Optional[float] = None,
    since_date: Optional[str] = None,
    top_k: Optional[int] = None,
    include_excluded: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Discover uncategorized counterparty candidates from a canonical DataFrame.
    """
    df = df.copy()
    
    # 1. Isolate uncategorized transactions for analysis.
    # Ensure NA/None handling robustness (v0.6.4)
    uncategorized_mask = df[category_col].isna() | (df[category_col].astype(str).str.strip() == '')

    # v0.7.4: Exclude-aware discovery. Rows with exclude=True are not categorisation
    # gaps — they were intentionally marked out of scope. Skip unless --include-excluded.
    if not include_excluded and "exclude" in df.columns:
        _exc = df["exclude"].fillna("").astype(str).str.strip().str.lower()
        uncategorized_mask &= (~_exc.isin(("true", "1", "yes")))

    work_df = df[uncategorized_mask].copy()

    if since_date:
        since_dt = pd.to_datetime(since_date, errors='coerce')
        if pd.notna(since_dt):
            # Ensure date column is datetime before comparison
            # Assumes dates are already normalized (timezone-naive) by main()
            if not pd.api.types.is_datetime64_any_dtype(work_df[date_col]):
                 work_df[date_col] = pd.to_datetime(work_df[date_col], errors='coerce')
            work_df = work_df[work_df[date_col] >= since_dt].copy()

    # Define empty DF structures for early exit
    cols_all = ['counterparty_fingerprint', 'example_counterparty_name', 'count', 'last_seen_date', 'max_abs_amount', 'total_value']
    cols_cand = ['counterparty_fingerprint', 'example_counterparty_name', 'count', 'sample_amount', 'sample_date']
    empty_cand = pd.DataFrame(columns=cols_cand)
    empty_all = pd.DataFrame(columns=cols_all)

    # Early exit if there are no uncategorized rows to process.
    if work_df.empty:
        return empty_cand, empty_all

    # 2. Create fingerprints and helper columns for aggregation.
    work_df['counterparty_fingerprint'] = _clean_counterparty(work_df[counterparty_col])
    work_df['abs_amount'] = work_df[amount_col].abs()
    work_df = work_df[work_df['counterparty_fingerprint'] != '']

    if work_df.empty:
        return empty_cand, empty_all

    # 3. Build the full frequency table ('all_candidates_df').
    # First, find a deterministic example name for each fingerprint (latest, then largest amount).
    # Use kind='mergesort' for stable sorting
    example_indices = work_df.sort_values(
        by=[date_col, 'abs_amount'], ascending=[False, False], kind='mergesort'
    ).drop_duplicates(subset=['counterparty_fingerprint'], keep='first').index
    example_map = work_df.loc[example_indices].set_index('counterparty_fingerprint')[counterparty_col]
    
    # Then, perform all aggregations.
    all_candidates_df = work_df.groupby('counterparty_fingerprint').agg(
        count=(counterparty_col, 'size'),
        last_seen_date=(date_col, 'max'),
        max_abs_amount=('abs_amount', 'max'),
        total_value=(amount_col, 'sum')
    ).reset_index()
    all_candidates_df['example_counterparty_name'] = all_candidates_df['counterparty_fingerprint'].map(example_map)
    
    # 4. Filter the full table to create the prioritized shortlist ('candidates_df').
    count_mask = (all_candidates_df['count'] >= min_count)
    if min_amount is not None:
        amount_mask = (all_candidates_df['max_abs_amount'] >= min_amount)
        final_filter_mask = count_mask | amount_mask
    else:
        final_filter_mask = count_mask
    candidates_df = all_candidates_df[final_filter_mask].copy()
    
    # Handle case where no candidates meet the filter criteria
    final_candidate_cols = ['counterparty_fingerprint', 'example_counterparty_name', 'count', 'sample_amount', 'sample_date']
    if candidates_df.empty:
        # If no candidates are found, return an empty DF with the correct columns.
        candidates_df = pd.DataFrame(columns=final_candidate_cols)
    else:
        # 5. If candidates were found, enrich them with sample details.
        # Remove inplace=True (Pandas compatibility)
        candidates_df = candidates_df.sort_values(by='count', ascending=False, kind='mergesort')
        if top_k is not None:
            candidates_df = candidates_df.head(top_k)

        # Get sample details (amount/date) for the final candidates.
        # Use kind='mergesort' for stable sorting
        sample_indices = (work_df.sort_values(by=[date_col, 'abs_amount'], ascending=[False, False], kind='mergesort')
                        .drop_duplicates(subset=['counterparty_fingerprint'], keep='first').index)
        sample_details = work_df.loc[sample_indices, ['counterparty_fingerprint', amount_col, date_col]]\
            .rename(columns={amount_col: 'sample_amount', date_col: 'sample_date'})

        candidates_df = candidates_df.merge(sample_details, on='counterparty_fingerprint', how='left')
        candidates_df = candidates_df[final_candidate_cols]
    
    # 6. Final formatting and sorting.
    final_all_cols = ['counterparty_fingerprint', 'example_counterparty_name', 'count', 'last_seen_date', 'max_abs_amount', 'total_value']
    all_candidates_df = all_candidates_df[final_all_cols]
    
    # Format dates for output (assumes datetime objects from normalization)
    if not candidates_df.empty:
        # Ensure conversion handles potential mixed types if normalization was imperfect
        candidates_df['sample_date'] = pd.to_datetime(candidates_df['sample_date'], errors='coerce').dt.strftime('%Y-%m-%d')
    if not all_candidates_df.empty:
        all_candidates_df['last_seen_date'] = pd.to_datetime(all_candidates_df['last_seen_date'], errors='coerce').dt.strftime('%Y-%m-%d')
    
    # Final deterministic sort
    if not candidates_df.empty:
        # Remove inplace=True (Pandas compatibility)
        candidates_df = candidates_df.sort_values(by='count', ascending=False, kind='mergesort')
    
    return candidates_df, all_candidates_df

def _to_number(series: pd.Series, decimal: str, thousands: Optional[str]) -> pd.Series:
    """Optimized number conversion with locale hardening (Synchronized with run_finlang)."""
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
    cr_mask = s_upper.str.contains(r'\b(?:CR|CRED|CREDIT)\b\.?\s*$', regex=True, na=False)
    dr_mask = s_upper.str.contains(r'\b(?:DR|DEB|DEBIT)\b\.?\s*$', regex=True, na=False)

    # Strip CR/DR tokens (case-insensitive)
    # Ensure non-capturing groups (?:...)
    # Strip CR/DR tokens (true case-insensitive; non-capturing groups)
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
                vals = vals.copy()  # defensive copy
                vals.loc[dr_mask] = vals.loc[dr_mask].abs() * -1
            if cr_mask.any():
                vals = vals.copy()  # defensive copy
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


def main(args_list=None):
    """CLI wrapper for the discover_candidates function."""
    parser = argparse.ArgumentParser(
        description="Discover uncategorized transaction candidates from a canonical FinLang CSV.",
        epilog="Example: finlang-discover --input canonical.csv --candidates candidates.csv --all-candidates all_candidates.csv --min-count 5"
    )
    parser.add_argument("--input", required=True,
                        help="Canonical CSV with columns: counterparty, category, amount, date.")
    # Accept both new names and legacy aliases to avoid breaking scripts
    parser.add_argument("--candidates", "--output", dest="candidates", required=True,
                        help="Output path for the prioritized candidates CSV.")
    parser.add_argument("--all-candidates", "--all", dest="all_candidates", required=True,
                        help="Output path for the full 'all candidates' CSV.")
    parser.add_argument("--min-count", type=int, default=5, help="Minimum transaction count to be a candidate.")
    parser.add_argument("--min-amount", type=float, help="Minimum absolute transaction amount to be a candidate.")
    parser.add_argument("--since-date", type=str, help="Only consider transactions since this date (YYYY-MM-DD).")
    parser.add_argument("--top-k", type=int, help="Limit output to the top K most frequent candidates.")
    parser.add_argument("--fastio", action="store_true", help="Use pyarrow engine for fast CSV IO (if installed).")
    parser.add_argument("--headless", action="store_true", help="Suppress console status messages.")
    parser.add_argument("--include-excluded", action="store_true",
                        help="Include exclude=True rows in discovery (default: skip them).")

    # Strict Parsing Flags (RC1 Requirement)
    parser.add_argument("--strict-parse", action="store_true", help="Fail fast on mixed delimiters, bad headers, or excessive drops.")
    parser.add_argument("--fail-threshold", type=float, default=0.01, help="Max allowed fraction of dropped rows after normalization (0 in strict).")

    # Internationalization Flags
    # Updated default and help text to include 'auto'
    parser.add_argument("--encoding", type=str, default="utf-8-sig", help="CSV file encoding (e.g. 'utf-8', 'latin-1', 'auto'). Default: utf-8-sig.")
    parser.add_argument("--decimal", type=str, default=".", help="Decimal separator for numeric fields ('.' or ',').")
    parser.add_argument("--thousands", type=str, default=None, help="Thousands separator for numeric fields (e.g. ',', '.').")
    parser.add_argument("--dayfirst", action="store_true", help="Parse ambiguous dates as DD/MM/YYYY (UK/EU style).")
    parser.add_argument("--date-format", type=str, default=None, help="Explicit strftime format for date parsing.")
    
    # Handle argument parsing flexibility
    try:
        if args_list is not None:
            args = parser.parse_args(args_list)
        elif sys.argv[1:]:
            args = parser.parse_args()
        else:
            parser.print_help()
            return
    except SystemExit:
        return

    def log(msg: str):
        if not args.headless:
            print(msg, flush=True)

    # Validate separators
    if args.decimal and len(args.decimal) != 1:
        print("FATAL: --decimal must be a single character '.' or ','.", file=sys.stderr); sys.exit(2)
    if args.thousands and len(args.thousands) != 1 and args.thousands is not None:
        print("FATAL: --thousands must be a single character (e.g., ',' or '.').", file=sys.stderr); sys.exit(2)
    if args.decimal and args.thousands and args.decimal == args.thousands:
        print("FATAL: --decimal and --thousands cannot be the same.", file=sys.stderr); sys.exit(2)

    if args.fastio:
        try:
            import pyarrow
        except ImportError:
            log("   (Info: --fastio requires 'pyarrow'. Falling back to default IO behavior.)")
            args.fastio = False

    try:
        # 1. Load the data robustly.
        log(f"1. Loading and normalizing {os.path.basename(args.input)}...")
        
        # Handle auto encoding detection
        input_encoding = args.encoding
        if input_encoding.lower() == "auto":
            input_encoding = _auto_pick_encoding(args.input, headless=args.headless)

        # Pass configuration explicitly to _read_csv_hardened
        df = _read_csv_hardened(
            args.input,
            encoding=input_encoding,
            fastio=args.fastio,
            headless=args.headless,
            strict_parse=args.strict_parse
        )

        # Standardize column names (lowercase, strip whitespace).
        df.columns = [str(c).strip().lower() for c in df.columns]

        # 2. Ensure canonical columns exist.
        required_cols = ["counterparty", "category", "amount", "date"]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            print(f"FATAL: Missing required canonical columns: {missing}. Ensure input CSV is correctly formatted.", file=sys.stderr)
            sys.exit(2)

        # 3. Normalize data types using the optimized, shared logic.
        
        # Numeric Normalization (using the synchronized _to_number)
        df["amount"] = _to_number(df["amount"], decimal=args.decimal, thousands=args.thousands)

        # Date Normalization
        if args.date_format:
            df["date"] = pd.to_datetime(df["date"], format=args.date_format, errors="coerce")
        else:
            # Use cache=True for performance
            df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=args.dayfirst, cache=True)

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

        # Drop rows where normalization failed and apply drop-rate guard (RC1 Requirement)
        total_rows = len(df)
        valid_mask = df["amount"].notna() & df["date"].notna()
        dropped_count = total_rows - valid_mask.sum()
        
        if dropped_count and not args.headless:
             log(f"-> Dropped {dropped_count} rows with invalid amount/date.")

        # Apply drop rate guard logic
        # Threshold is 0 if strict_parse is True, otherwise use the specified fail_threshold
        thresh = 0.0 if args.strict_parse else args.fail_threshold
        
        if total_rows > 0 and (dropped_count / total_rows) > thresh:
            msg = f"FATAL: Dropped {dropped_count}/{total_rows} rows during normalization (> {thresh:.2%})."
            if args.strict_parse:
                # In strict mode, any drop is a failure (thresh=0.0)
                msg = f"Strict parse: {msg}"
            print(msg, file=sys.stderr)
            sys.exit(2)

        df = df[valid_mask].copy()

        if df.empty:
            log("No valid transactions found in the input file.")
            # Write empty output files
            pd.DataFrame().to_csv(args.candidates, index=False)
            pd.DataFrame().to_csv(args.all_candidates, index=False)
            return

        # 4. Run the discovery algorithm.
        log("2. Discovering candidates...")
        candidates_df, all_candidates_df = discover_candidates(
            df,
            min_count=args.min_count,
            min_amount=args.min_amount,
            since_date=args.since_date,
            top_k=args.top_k,
            include_excluded=args.include_excluded,
        )

        # 5. Write the output CSVs.
        log("3. Writing outputs...")

        # Apply CSV injection protection before writing (using optimized version)
        # Allow disabling via environment variable for consistency with main CLI
        if str(os.getenv("FINLANG_SAFE_TEXT", "1")).lower() not in ("0", "false", "no"):
            # _csv_safe_text returns a modified copy
            candidates_df = _csv_safe_text(candidates_df)
            all_candidates_df = _csv_safe_text(all_candidates_df)
        elif not args.headless:
            log("-> Skipping CSV injection protection (FINLANG_SAFE_TEXT=0)")


        # Write outputs using utf-8 encoding
        candidates_df.to_csv(args.candidates, index=False, encoding="utf-8")
        all_candidates_df.to_csv(args.all_candidates, index=False, encoding="utf-8")

        log("-" * 20)
        log("OK. Discovery complete.")
        # Use the configured min_count in the summary message
        log(f"   Found {len(candidates_df)} prioritized candidates (>= {args.min_count} txns or >= amount threshold).")
        log(f"   Total unique uncategorized counterparties: {len(all_candidates_df)}.")
        log(f"   Prioritized output: {args.candidates}")
        log(f"   Full output: {args.all_candidates}")

    except FileNotFoundError:
        print(f"FATAL: Input file not found at '{args.input}'", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        # Catch specific errors from strict checks or normalization
        print(f"FATAL: Data processing error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"An unexpected error occurred: {type(e).__name__}: {e}", file=sys.stderr)
        # Optionally print traceback for debugging
        # import traceback; traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    # Ensure compatibility with PYTHONWARNINGS=error policy
    if not sys.warnoptions:
        import warnings
        warnings.simplefilter("default")
    main()