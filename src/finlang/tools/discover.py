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
from typing import Tuple, Optional

def _clean_counterparty(s: pd.Series) -> pd.Series:
    """Normalizes a series of strings to create a fingerprint."""
    # Ensure series is string type and handle NaNs
    s = s.fillna('').astype(str)
    # Strip accents (e.g., CAFÉ -> CAFE)
    s = s.map(lambda x: unicodedata.normalize('NFKD', x).encode('ascii', 'ignore').decode('ascii'))
    # Standard cleaning: uppercase, remove punctuation, collapse whitespace
    s = s.str.upper()
    s = s.str.replace(r'[^A-Z0-9\s]', ' ', regex=True)
    s = s.str.replace(r'\s+', ' ', regex=True).str.strip()
    return s

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
    # Robustly convert core columns to their expected types
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce')

    # Filter for uncategorized rows
    uncategorized_mask = df[category_col].isna() | (df[category_col].astype(str).str.strip() == '')
    work_df = df[uncategorized_mask].copy()

    # Apply date filter if provided
    if since_date:
        since_dt = pd.to_datetime(since_date, errors='coerce')
        if pd.notna(since_dt):
            work_df = work_df[work_df[date_col] >= since_dt].copy()

    # Early exit if no data to process
    if work_df.empty:
        cols_all = ['counterparty_fingerprint', 'example_counterparty_name', 'count', 'last_seen_date', 'max_abs_amount', 'total_value']
        cols_cand = ['counterparty_fingerprint', 'example_counterparty_name', 'count', 'sample_amount', 'sample_date']
        return pd.DataFrame(columns=cols_cand), pd.DataFrame(columns=cols_all)

    # Create fingerprint and helper column
    work_df['counterparty_fingerprint'] = _clean_counterparty(work_df[counterparty_col])
    work_df['abs_amount'] = work_df[amount_col].abs()
    work_df = work_df[work_df['counterparty_fingerprint'] != '']

    # Find the deterministic example row for each group
    example_indices = work_df.sort_values(
        by=[date_col, 'abs_amount'], ascending=[False, False]
    ).drop_duplicates(subset=['counterparty_fingerprint'], keep='first').index

    example_map = work_df.loc[example_indices].set_index('counterparty_fingerprint')[counterparty_col]
    
    # Perform all aggregations in one vectorized step
    all_candidates_df = work_df.groupby('counterparty_fingerprint').agg(
        count=(counterparty_col, 'size'),
        last_seen_date=(date_col, 'max'),
        max_abs_amount=('abs_amount', 'max'),
        total_value=(amount_col, 'sum')
    ).reset_index()
    
    all_candidates_df['example_counterparty_name'] = all_candidates_df['counterparty_fingerprint'].map(example_map)
    
    # Filter for the prioritized candidates list
    count_mask = (all_candidates_df['count'] >= min_count)
    if min_amount is not None:
        amount_mask = (all_candidates_df['max_abs_amount'] >= min_amount)
        final_filter_mask = count_mask | amount_mask
    else:
        final_filter_mask = count_mask

    candidates_df = all_candidates_df[final_filter_mask].copy()
    
    candidates_df.sort_values(by='count', ascending=False, inplace=True)
    if top_k is not None:
        candidates_df = candidates_df.head(top_k)

    # Get sample details for the final candidates
    sample_details = work_df.loc[
        work_df.sort_values(by=[date_col, 'abs_amount'], ascending=[False, False])
        .drop_duplicates(subset=['counterparty_fingerprint'], keep='first')
        .index
    ]
    sample_details = sample_details[['counterparty_fingerprint', amount_col, date_col]]\
        .rename(columns={amount_col: 'sample_amount', date_col: 'sample_date'})

    candidates_df = candidates_df.merge(sample_details, on='counterparty_fingerprint', how='left')
    
    # Final formatting
    final_candidate_cols = ['counterparty_fingerprint', 'example_counterparty_name', 'count', 'sample_amount', 'sample_date']
    final_all_cols = ['counterparty_fingerprint', 'example_counterparty_name', 'count', 'last_seen_date', 'max_abs_amount', 'total_value']
    
    candidates_df = candidates_df[final_candidate_cols]
    all_candidates_df = all_candidates_df[final_all_cols]
    
    candidates_df['sample_date'] = pd.to_datetime(candidates_df['sample_date']).dt.strftime('%Y-%m-%d')
    all_candidates_df['last_seen_date'] = pd.to_datetime(all_candidates_df['last_seen_date']).dt.strftime('%Y-%m-%d')
    
    # Ensure final sort order is preserved after merge
    candidates_df.sort_values(by='count', ascending=False, inplace=True, kind='mergesort')
    
    return candidates_df, all_candidates_df

def main():
    """CLI wrapper for the discover_candidates function."""
    parser = argparse.ArgumentParser(
        description="Discover uncategorized transaction candidates from a canonical FinLang CSV.",
        epilog="Example: python discover.py --input canonical.csv --candidates candidates.csv --all all_candidates.csv --min-count 5"
    )
    parser.add_argument("--input", required=True, help="Path to the input canonical CSV file.")
    parser.add_argument("--candidates", required=True, help="Output path for the prioritized candidates CSV.")
    parser.add_argument("--all", required=True, help="Output path for the full 'all candidates' CSV.")
    parser.add_argument("--min-count", type=int, default=5, help="Minimum transaction count to be a candidate.")
    parser.add_argument("--min-amount", type=float, help="Minimum absolute transaction amount to be a candidate.")
    parser.add_argument("--since-date", type=str, help="Only consider transactions since this date (YYYY-MM-DD).")
    parser.add_argument("--top-k", type=int, help="Limit output to the top K most frequent candidates.")
    args = parser.parse_args()

    try:
        print(f"1. Loading canonical transactions from '{args.input}'...")
        df = pd.read_csv(args.input)
    except FileNotFoundError:
        print(f"FATAL: Input file not found at '{args.input}'", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"FATAL: Could not read input file. Error: {e}", file=sys.stderr)
        sys.exit(1)
        
    # Verify required columns exist
    required_cols = {"counterparty", "category", "amount", "date"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        print(f"FATAL: Input file is missing required canonical columns: {', '.join(missing_cols)}", file=sys.stderr)
        print(f"       Please process the raw file with 'run_finlang.py' first.", file=sys.stderr)
        sys.exit(1)

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
        candidates_df.to_csv(args.candidates, index=False)
        all_candidates_df.to_csv(args.all, index=False)
    except Exception as e:
        print(f"FATAL: Could not write output files. Error: {e}", file=sys.stderr)
        sys.exit(1)

    print("-" * 20)
    print("✅ Discovery complete.")
    print(f"   -> Prioritized shortlist: '{args.candidates}' ({len(candidates_df)} rows)")
    print(f"   -> Full frequency table:  '{args.all}' ({len(all_candidates_df)} rows)")


if __name__ == "__main__":
    main()