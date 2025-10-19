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
import unicodedata
import argparse
import sys
from typing import Tuple, Optional, Any

def _strip_control_chars(s: str) -> str:
    """Removes invisible Unicode control characters from a string."""
    if not isinstance(s, str):
        return s
    return "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")

def _clean_counterparty(s: pd.Series) -> pd.Series:
    """Normalizes a series of strings to create a fingerprint."""
    s = s.fillna('').astype(str).apply(_strip_control_chars)
    # Normalize accents and special characters (e.g., CAFÉ -> CAFE)
    s = s.map(lambda x: unicodedata.normalize('NFKD', x).encode('ascii', 'ignore').decode('ascii'))
    # Standard cleaning: uppercase, remove punctuation, collapse whitespace
    s = s.str.upper()
    s = s.str.replace(r'[^A-Z0-9\s]', ' ', regex=True)
    s = s.str.replace(r'\s+', ' ', regex=True).str.strip()
    return s

def _csv_safe_text(df: pd.DataFrame) -> pd.DataFrame:
    """Escapes cells that could be interpreted as formulas in spreadsheet software."""
    DANGER = ("=", "+", "-", "@", "\t")
    obj_cols = [c for c in df.columns if df[c].dtype == "object"]
    for c in obj_cols:
        s = df[c].astype(str)
        lead = s.str.lstrip(" ")  # preserve leading tabs as a danger signal
        mask = lead.str.startswith(DANGER) & ~s.str.startswith("'")
        if mask.any():
            df.loc[mask, c] = "'" + s[mask]
    return df

def _read_csv_hardened(
    path: str, *, encoding: str = "utf-8", fastio: bool = False
) -> pd.DataFrame:
    """
    Robust CSV loader that warns and skips malformed rows, with engine fallbacks.
    Reads all data as strings to ensure deterministic parsing.
    """
    import warnings
    import pandas.errors as pd_errors

    read_kwargs = dict(encoding=encoding, on_bad_lines="warn", dtype=str)

    # Try fast path first if requested
    if fastio:
        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always", pd_errors.ParserWarning)
                df = pd.read_csv(path, engine="pyarrow", **read_kwargs)
                bad_lines = [m for m in w if issubclass(m.category, pd_errors.ParserWarning)]
                if bad_lines:
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
            if bad_lines:
                print(f"-> Skipped {len(bad_lines)} malformed row(s) (extra columns or bad structure)")
            return df
    except pd.errors.ParserError:
        # Final fallback: Python engine
        print("   (Info: C-engine parse failed; falling back to slower Python engine)")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", pd_errors.ParserWarning)
            df = pd.read_csv(path, engine="python", **read_kwargs)
            bad_lines = [m for m in w if issubclass(m.category, pd_errors.ParserWarning)]
            if bad_lines:
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

def main():
    """CLI wrapper for the discover_candidates function."""
    parser = argparse.ArgumentParser(
        description="Discover uncategorized transaction candidates from a canonical FinLang CSV.",
        epilog="Example: finlang-discover --input canonical.csv --candidates candidates.csv --all-candidates all_candidates.csv --min-count 5"
    )
    # --- FIX: Add missing --input argument ---
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

    # Internationalization Flags
    parser.add_argument("--encoding", type=str, default="utf-8", help="CSV file encoding (e.g. 'utf-8', 'latin-1').")
    parser.add_argument("--decimal", type=str, default=".", help="Decimal separator for numeric fields ('.' or ',').")
    parser.add_argument("--thousands", type=str, default=None, help="Thousands separator for numeric fields (e.g. ',', '.').")
    parser.add_argument("--dayfirst", action="store_true", help="Parse ambiguous dates as DD/MM/YYYY (UK/EU style).")
    parser.add_argument("--date-format", type=str, default=None, help="Explicit strftime format for date parsing, e.g. '%%d/%%m/%%Y'.")
    parser.add_argument("--output-encoding", default="utf-8", help="Encoding for output CSV (e.g. 'utf-8', 'utf-8-sig').")

    args = parser.parse_args()

    # Final validation of separator arguments
    if args.decimal is not None and len(args.decimal) != 1:
        print("FATAL: --decimal must be a single character '.' or ','.", file=sys.stderr); sys.exit(2)
    if args.thousands is not None and len(args.thousands) != 1:
        print("FATAL: --thousands must be a single character (e.g., ',' or '.').", file=sys.stderr); sys.exit(2)
    if args.decimal and args.thousands and args.decimal == args.thousands:
        print("FATAL: --decimal and --thousands cannot be the same.", file=sys.stderr); sys.exit(2)

    try:
        print(f"1. Loading canonical transactions from '{args.input}'...")
        df = _read_csv_hardened(args.input, encoding=args.encoding, fastio=args.fastio)
    except FileNotFoundError:
        print(f"FATAL: Input file not found at '{args.input}'", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"FATAL: Could not read input file. Error: {e}", file=sys.stderr)
        sys.exit(1)

    if df.empty:
        print("FATAL: Input file is empty or contains no valid data.", file=sys.stderr)
        sys.exit(1)
        
    required_cols = {"counterparty", "category", "amount", "date"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        print(f"FATAL: Input file is missing required canonical columns: {', '.join(missing_cols)}", file=sys.stderr)
        print(f"       Please process the raw file with 'run_finlang.py' first.", file=sys.stderr)
        sys.exit(1)

    # Convert core columns to their expected types using locale settings
    if args.date_format:
        df["date"] = pd.to_datetime(df["date"], format=args.date_format, errors="coerce")
    else:
        df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=args.dayfirst)
    
    s_amount = df["amount"].str.strip()
    if args.thousands:
        s_amount = s_amount.str.replace(args.thousands, "", regex=False)
    if args.decimal != ".":
        s_amount = s_amount.str.replace(args.decimal, ".", regex=False)
    df["amount"] = pd.to_numeric(s_amount, errors="coerce")


    # Drop rows with invalid core data before discovery to ensure clean analysis
    bad_rows = df["date"].isna() | df["amount"].isna()
    if bad_rows.any():
        print(f"-> Skipping {int(bad_rows.sum())} row(s) with invalid date/amount.")
        df = df[~bad_rows].copy()

    print("2. Discovering rule candidates...")
    candidates_df, all_candidates_df = discover_candidates(
        df,
        min_count=args.min_count,
        min_amount=args.min_amount,
        since_date=args.since_date,
        top_k=args.top_k
    )

    print(f"3. Writing outputs...")
    try:
        # Sanitize text fields before writing to prevent formula injection
        candidates_df = _csv_safe_text(candidates_df)
        all_candidates_df = _csv_safe_text(all_candidates_df)
        
        candidates_df.to_csv(args.candidates, index=False, encoding=args.output_encoding)
        all_candidates_df.to_csv(args.all_candidates, index=False, encoding=args.output_encoding)
    except Exception as e:
        print(f"FATAL: Could not write output files. Error: {e}", file=sys.stderr)
        sys.exit(1)

    print("-" * 20)
    print("✅ Discovery complete.")
    print(f"   -> Prioritized shortlist: '{args.candidates}' ({len(candidates_df)} rows)")
    print(f"   -> Full frequency table:  '{args.all_candidates}' ({len(all_candidates_df)} rows)")


if __name__ == "__main__":
    main()

