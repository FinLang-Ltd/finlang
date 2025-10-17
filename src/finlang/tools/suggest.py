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


"""
suggest.py — Generate draft .fin rules from discovery candidates.

This tool reads a candidates CSV file produced by discover.py and generates
conservative, review-ready .fin rule blocks. It is designed to accelerate
the rule-writing process by providing a safe starting point.

Usage:
  python suggest.py --input candidates.csv --output draft_rules.fin \\
    [--rules existing.fin] [--category "Review"] [--prefix "SUGGEST"]

Behavior:
  - Reads a candidates CSV (headers are auto-detected).
  - Generates rules based on the exact 'fingerprint' of a counterparty.
  - Skips generating rules for fingerprints already covered in an
    optional existing rules file.
  - Emits review-ready rules with metadata in comments.
"""

import argparse
import csv
import os
import re
import sys
from typing import List, Dict, Optional, Any

# ---- Constants for flexible header detection ----
CANDIDATE_FINGERPRINT_HEADERS = {"counterparty_fingerprint", "fingerprint"}
CANDIDATE_EXAMPLE_HEADERS = {"example_counterparty_name", "example"}
CANDIDATE_COUNT_HEADERS = {"count", "frequency"}
CANDIDATE_DATE_HEADERS = {"sample_date", "last_seen_date"}
CANDIDATE_AMOUNT_HEADERS = {"sample_amount", "sample_value"}


def _read_candidates(path: str) -> List[Dict[str, Any]]:
    """
    Safely reads a discovery candidates CSV into a list of dictionaries.
    Handles potential file errors and normalizes headers.
    """
    # This function is wrapped in a try/except block in main().
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        # Normalize headers to lowercase for robust matching
        fieldnames = [h.lower().strip() for h in reader.fieldnames] if reader.fieldnames else []
        reader.fieldnames = fieldnames
        return list(reader)


def generate_rules(
    candidates: List[Dict[str, Any]],
    prefix: str,
    category: str,
    existing_rules_path: Optional[str] = None
) -> List[str]:
    """
    Build conservative, review-first rule blocks from discovered candidates.

    This function creates rule blocks that match on the exact counterparty
    'fingerprint', ensuring no unintended side effects. It will skip any
    candidates that appear to be covered by rules in the existing rules file.

    Args:
        candidates: A list of candidate dictionaries from the input CSV.
        prefix: A string to prepend to the generated rule names.
        category: The default category to assign in the 'set' block.
        existing_rules_path: Optional path to a .fin file to check for duplicates.

    Returns:
        A list of strings, where each string is a complete .fin rule block.
    """
    # 1. Read existing rules to find patterns that are already covered.
    existing_patterns = set()
    if existing_rules_path:
        try:
            with open(existing_rules_path, "r", encoding="utf-8-sig") as f:
                content = f.read()
            # A simple regex to find `fingerprint == "..."` patterns.
            # This prevents generating obvious duplicates.
            existing_patterns.update(re.findall(r'fingerprint\s*==\s*"([^"]+)"', content))
        except FileNotFoundError:
            print(f"WARNING: Existing rules file not found at '{existing_rules_path}'. Continuing without it.", file=sys.stderr)
        except OSError as e:
            print(f"WARNING: Could not read existing rules file '{existing_rules_path}': {e}. Continuing without it.", file=sys.stderr)


    # 2. Helper to find the correct header for a given field type from the CSV.
    def _find_key(row: Dict[str, Any], headers: set) -> Optional[str]:
        """Finds the first matching key from a set of possible headers."""
        return next((k for k in row.keys() if k in headers), None)

    # 3. Generate rule blocks for new, uncovered candidates.
    rule_blocks = []
    if not candidates:
        return []

    # Auto-detect headers from the first candidate row for efficiency.
    first_row = candidates[0]
    fingerprint_key = _find_key(first_row, CANDIDATE_FINGERPRINT_HEADERS)
    example_key = _find_key(first_row, CANDIDATE_EXAMPLE_HEADERS)
    count_key = _find_key(first_row, CANDIDATE_COUNT_HEADERS)
    date_key = _find_key(first_row, CANDIDATE_DATE_HEADERS)
    amount_key = _find_key(first_row, CANDIDATE_AMOUNT_HEADERS)

    if not fingerprint_key:
        print("FATAL: Could not find a 'counterparty_fingerprint' or 'fingerprint' column in candidates file.", file=sys.stderr)
        sys.exit(1)

    for cand in candidates:
        fingerprint = cand.get(fingerprint_key, "")
        if not fingerprint or fingerprint in existing_patterns:
            continue

        # Gather metadata for the comment block.
        example = cand.get(example_key, "N/A")
        count = cand.get(count_key, "N/A")
        date = cand.get(date_key, "N/A")
        amount = cand.get(amount_key, "N/A")

        # Sanitize the fingerprint to create a valid and readable rule name.
        rule_name_suffix = re.sub(r'[^A-Z0-9_]+', '_', fingerprint).strip('_')
        rule_name = f"{prefix}: {rule_name_suffix}"
        
        block = f"""
# SUGGESTED (freq={count}, last={date}, sample_amt={amount})
# Example: {example}
rule "{rule_name}" {{
  match:
    - fingerprint == "{fingerprint}"
  set:
    category = "{category}"
}}"""
        rule_blocks.append(block)

    return rule_blocks


def main():
    """CLI wrapper to generate draft rules."""
    ap = argparse.ArgumentParser(
        description="Generate draft .fin rules from discovery candidates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Example:
  python suggest.py --input candidates.csv --output draft_rules.fin --rules existing.fin
"""
    )
    ap.add_argument("--input", required=True, help="Path to candidates.csv from discover.py")
    ap.add_argument("--output", required=True, help="Path to write/append draft_rules.fin")
    ap.add_argument("--rules", help="Existing rules.fin to avoid duplicate patterns")
    ap.add_argument("--category", default="Review", help='Default category to set (default: "Review")')
    ap.add_argument("--prefix", default="SUGGEST", help='Rule name prefix (default: "SUGGEST")')
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--append", action="store_true", help="Append to output file (default)")
    mode.add_argument("--overwrite", action="store_true", help="Overwrite output file")
    args = ap.parse_args()

    print(f"1. Reading candidates from '{args.input}'...")
    try:
        cands = _read_candidates(args.input)
    except FileNotFoundError:
        print(f"FATAL: Input candidates file not found at '{args.input}'", file=sys.stderr)
        sys.exit(1)
    except (OSError, csv.Error) as e:
        print(f"FATAL: Could not read candidates file '{args.input}'. Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not cands:
        print("-> No candidates found. Nothing to write.")
        sys.exit(0)

    print(f"2. Generating rules (checking against '{args.rules}' if provided)...")
    blocks = generate_rules(cands, args.prefix, args.category, args.rules)
    if not blocks:
        print("-> All candidates appear to be covered by existing rules. Nothing to write.")
        sys.exit(0)

    # Choose write mode: default to append unless overwriting or file doesn't exist.
    write_mode = "w" if args.overwrite or not os.path.exists(args.output) else "a"
    
    print(f"3. Writing {len(blocks)} new rule(s) to '{args.output}' (mode: {write_mode})...")
    try:
        with open(args.output, write_mode, encoding="utf-8", newline="") as f:
            if write_mode == 'a' and f.tell() > 0:
                # Add spacing if appending to a non-empty file.
                f.write("\n\n")
            f.write("\n\n".join(blocks))
            f.write("\n") # Ensure final newline for clean formatting.
    except IOError as e:
        print(f"FATAL: Could not write to output file '{args.output}'. Error: {e}", file=sys.stderr)
        sys.exit(1)

    print("-" * 20)
    print("✅ Suggestion complete.")


if __name__ == "__main__":
    main()

