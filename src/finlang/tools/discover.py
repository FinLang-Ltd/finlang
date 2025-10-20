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


import pandas as pd
import re
import unicodedata
import argparse
import sys
import os
from typing import Tuple, Optional, Any, List

# --------------------------------------------------------------------------------------
# Data Hardening Utilities (Synchronized with run_finlang_locale_v2_1.py)
# --------------------------------------------------------------------------------------

# Compact regex covering C0, DEL, C1, and common problem format chars (ZW*, LS, PS, BOM)
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1F\x7F-\x9F\u200B-\u200D\u2028\u2029\uFEFF]")

# Currency/NBSP removal (Required by _to_number)
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

# Removed the slow _strip_control_chars function.

def _detect_delimiter(path: str, encoding: str = "utf-8", sample_bytes: int = 65536) -> Optional[str]:
    """Heuristic delimiter detector for CSVs (EU-friendly)."""
    try:
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
        s = obj[c].astype(str)
        lead = s.str.lstrip(" ")
        
        # Identify rows that are dangerous (using na=False for safety)
        is_dangerous = lead.str.startswith(DANGER, na=False)
        
        # Identify rows that are already safe (quoted)
        is_safe = s.str.startswith("'", na=False)

        # Needs fix if any row is dangerous AND not safe
        if (is_dangerous & ~is_safe).any():
            cols_to_fix.append(c)

    # Modifying in place is acceptable here as the DF is not reused after write.
    for c in cols_to_fix:
        s = df[c].astype(str)
        lead = s.str.lstrip(" ")
        # CRITICAL FIX: NA-safe mask to avoid propagating NaNs through bitwise ops
        mask = lead.str.startswith(DANGER, na=False) & ~s.str.startswith("'", na=False)
        if mask.any():
            df.loc[mask, c] = "'" + s[mask]
    return df

def _read_csv_hardened(
    path: str, *, encoding: str = "utf-8", fastio: bool = False, headless: bool = False
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

    read_kwargs = dict(encoding=encoding, on_bad_lines="warn", dtype=str)
    # EU-friendly delimiter detection
    sep = _detect_delimiter(path, encoding=encoding)
    if sep and sep != ",":
        if not headless:
            print(f"-> Detected delimiter '{sep}' (auto)")
        read_kwargs["sep"] = sep

    # Try fast path first if requested
    if fastio:
        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always", pd_errors.ParserWarning)
                df = pd.read_csv(path, engine="pyarrow", **read_kwargs)
                bad_lines = [m for m in w if issubclass(m.category, pd_errors.ParserWarning)]
                if bad_lines and not headless:
                    print(f"-> Skipped {len(bad_lines)} malformed row(s) (extra columns or bad structure)")
                return df
        except Exception:
            pass  # fall through

    # Default engine (C parser) with graceful ParserWarning handling
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", pd_errors.ParserWarning)
            df = pd.read_csv(path, **read_kwargs)
            bad_lines = [m for m in w if issubclass(m.category, pd_errors.ParserWarning)]
            if bad_lines and not headless:
                print(f"-> Skipped {len(bad_lines)} malformed row(s) (extra columns or bad structure)")
            return df
    except pd_errors.ParserError:
        # Final fallback: Python engine
        if not headless:
            print("   (Info: C-engine parse failed; falling back to slower Python engine)")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", pd_errors.ParserWarning)
            df = pd.read_csv(path, engine="python", **read_kwargs)
            bad_lines = [m for m in w if issubclass(m.category, pd_errors.ParserWarning)]
            if bad_lines and not headless:
                print(f"-> Skipped {len(bad_lines)} malformed row(s) (extra columns or bad structure)")
            return df

def discover_candidates(
    df: pd.DataFrame,
    counterparty_col: str = "counterparty",
    category_col: str = "category",
    amount_col: str = "amount",
    date_col: str = "date",
    min_count: int = 5,
    min_amount: Optional[float] = None,
    since_date: Optional[str] = None,
    top_k: Optional[int] = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Discover uncategorized counterparty candidates from a canonical DataFrame.
    """
    df = df.copy()
    
    # 1. Isolate uncategorized transactions for analysis.
    uncategorized_mask = df[category_col].isna() | (df[category_col].astype(str).str.strip() == '')
    work_df = df[uncategorized_mask].copy()

    if since_date:
        since_dt = pd.to_datetime(since_date, errors='coerce')
        if pd.notna(since_dt):
            # Ensure date column is datetime before comparison
            if not pd.api.types.is_datetime64_any_dtype(work_df[date_col]):
                 work_df[date_col] = pd.to_datetime(work_df[date_col], errors='coerce')
            work_df = work_df[work_df[date_col] >= since_dt].copy()

    # Early exit if there are no uncategorized rows to process.
    if work_df.empty:
        cols_all = ['counterparty_fingerprint', 'example_counterparty_name', 'count', 'last_seen_date', 'max_abs_amount', 'total_value']
        cols_cand = ['counterparty_fingerprint', 'example_counterparty_name', 'count', 'sample_amount', 'sample_date']
        return pd.DataFrame(columns=cols_cand), pd.DataFrame(columns=cols_all)

    # 2. Create fingerprints and helper columns for aggregation.
    work_df['counterparty_fingerprint'] = _clean_counterparty(work_df[counterparty_col])
    work_df['abs_amount'] = work_df[amount_col].abs()
    work_df = work_df[work_df['counterparty_fingerprint'] != '']

    if work_df.empty:
        cols_all = ['counterparty_fingerprint', 'example_counterparty_name', 'count', 'last_seen_date', 'max_abs_amount', 'total_value']
        cols_cand = ['counterparty_fingerprint', 'example_counterparty_name', 'count', 'sample_amount', 'sample_date']
        return pd.DataFrame(columns=cols_cand), pd.DataFrame(columns=cols_all)

    # 3. Build the full frequency table ('all_candidates_df').
    # First, find a deterministic example name for each fingerprint (latest, then largest amount).
    example_indices = work_df.sort_values(
        by=[date_col, 'abs_amount'], ascending=[False, False]
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
        candidates_df.sort_values(by='count', ascending=False, inplace=True)
        if top_k is not None:
            candidates_df = candidates_df.head(top_k)

        # Get sample details (amount/date) for the final candidates.
        sample_indices = (work_df.sort_values(by=[date_col, 'abs_amount'], ascending=[False, False])
                        .drop_duplicates(subset=['counterparty_fingerprint'], keep='first').index)
        sample_details = work_df.loc[sample_indices, ['counterparty_fingerprint', amount_col, date_col]]\
            .rename(columns={amount_col: 'sample_amount', date_col: 'sample_date'})

        candidates_df = candidates_df.merge(sample_details, on='counterparty_fingerprint', how='left')
        candidates_df = candidates_df[final_candidate_cols]
    
    # 6. Final formatting and sorting.
    final_all_cols = ['counterparty_fingerprint', 'example_counterparty_name', 'count', 'last_seen_date', 'max_abs_amount', 'total_value']
    all_candidates_df = all_candidates_df[final_all_cols]
    
    if not candidates_df.empty:
        candidates_df['sample_date'] = pd.to_datetime(candidates_df['sample_date']).dt.strftime('%Y-%m-%d')
    if not all_candidates_df.empty:
        all_candidates_df['last_seen_date'] = pd.to_datetime(all_candidates_df['last_seen_date']).dt.strftime('%Y-%m-%d')
    
    if not candidates_df.empty:
        candidates_df.sort_values(by='count', ascending=False, inplace=True, kind='mergesort')
    
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
    s_upper = s.str.upper()
    cr_mask = s_upper.str.contains(r'\b(CR|CRED|CREDIT)\b\.?\s*$', regex=True, na=False)
    dr_mask = s_upper.str.contains(r'\b(DR|DEB|DEBIT)\b\.?\s*$', regex=True, na=False)

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
                vals.loc[dr_mask] = vals.loc[dr_mask].abs() * -1
            if cr_mask.any():
                vals.loc[cr_mask] = vals.loc[cr_mask].abs()
            return vals

    # --- Full canonicalization tail (baseline parity) ---
    # Accounting negatives: (123.45) -> -123.45
    mask_accounting = s.str.startswith("(", na=False) & s.str.endswith(")", na=False)
    if mask_accounting.any():
        s = s.copy()
        # Ensure s is a copy if modifications are made in multiple branches
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
        vals = vals.copy() # Ensure copy before modification
        vals.loc[dr_mask] = vals.loc[dr_mask].abs() * -1
    if cr_mask.any():
        vals = vals.copy() # Ensure copy before modification
        vals.loc[cr_mask] = vals.loc[cr_mask].abs()
    return vals


# --------------------------------------------------------------------------------------
# CLI Entrypoint
# --------------------------------------------------------------------------------------

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

    # Internationalization Flags
    parser.add_argument("--encoding", type=str, default="utf-8", help="CSV file encoding (e.g. 'utf-8', 'latin-1').")
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
        df = _read_csv_hardened(args.input, encoding=args.encoding, fastio=args.fastio, headless=args.headless)

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
            df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=args.dayfirst, cache=True)

        # Drop rows where normalization failed (invalid amounts or dates).
        valid_mask = df["amount"].notna() & df["date"].notna()
        if not valid_mask.all():
             dropped_count = len(df) - valid_mask.sum()
             log(f"-> Dropped {dropped_count} rows with invalid amount/date.")
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
            top_k=args.top_k
        )

        # 5. Write the output CSVs.
        log("3. Writing outputs...")

        # Apply CSV injection protection before writing (using optimized version)
        # Allow disabling via environment variable for consistency with main CLI
        if str(os.getenv("FINLANG_SAFE_TEXT", "1")).lower() not in ("0", "false", "no"):
            candidates_df = _csv_safe_text(candidates_df)
            all_candidates_df = _csv_safe_text(all_candidates_df)
        elif not args.headless:
            log("-> Skipping CSV injection protection (FINLANG_SAFE_TEXT=0)")


        candidates_df.to_csv(args.candidates, index=False, encoding="utf-8")
        all_candidates_df.to_csv(args.all_candidates, index=False, encoding="utf-8")

        log("-" * 20)
        log("OK. Discovery complete.")
        log(f"   Found {len(candidates_df)} prioritized candidates (>= {args.min_count} txns).")
        log(f"   Total unique uncategorized counterparties: {len(all_candidates_df)}.")
        log(f"   Prioritized output: {args.candidates}")
        log(f"   Full output: {args.all_candidates}")

    except FileNotFoundError:
        print(f"FATAL: Input file not found at '{args.input}'", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()