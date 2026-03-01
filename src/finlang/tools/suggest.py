# suggest.py
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


# suggest.py — Generate draft .fin rules from discovery candidates
#
# v0.6.4-rc1a Final v3:
#   - (RC1a Semantic Fix): Corrected exact mode to match example_name (not fingerprint).
#   - (Optimization): Optimized exact de-duplication using a pre-computed set (O(1) lookup).
#   - (Robustness): Added re.DOTALL to pattern extraction regexes.

import argparse
import csv
import os
import re
import sys
# Import Set for type hinting the optimized de-duplication structure.
from typing import Dict, List, Optional, Tuple, Set

# ---------------------------------------------------------------------
# Header mapping / CSV read (BOM-safe, case-insensitive)
# ---------------------------------------------------------------------

def _read_candidates(path: str) -> List[Dict[str, str]]:
    """
    Read a candidates CSV coming from discover.py.
    """
    try:
        # Ensure BOM-safe reading
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fieldnames = reader.fieldnames or []
    except FileNotFoundError:
        raise SystemExit(f"FATAL: Input file not found at {path}")
    except Exception as e:
        raise SystemExit(f"FATAL: Error reading CSV {path}: {e}")

    if not rows:
        return []

    # Normalize column names to lowercase
    cols = {c.lower(): c for c in fieldnames}

    def pick(*names: str) -> Optional[str]:
        for n in names:
            if n in cols:
                return cols[n]
        return None

    key_cols = {
        "fingerprint":   pick("counterparty_fingerprint", "fingerprint", "vendor_key"),
        "example_name":  pick("example_counterparty_name", "example", "sample_name", "counterparty", "name"),
        "count":         pick("count", "freq", "frequency"),
        "last_seen":     pick("last_seen_date", "last_seen", "last_date", "sample_date", "date"),
        "sample_amount": pick("sample_amount", "example_amount", "sample_amt", "amount"),
    }

    # Minimal required inputs: Fingerprint (for grouping context) and Example Name (for matching/titles).
    if key_cols.get("fingerprint") is None or key_cols.get("example_name") is None:
         raise SystemExit(
            f"FATAL: Missing required 'fingerprint' or 'example_name' columns (or aliases) in {path}. "
            f"Present: {sorted(cols.keys())}"
        )

    out: List[Dict[str, str]] = []
    for r in rows:
        # Safely access data using the original column names identified in key_cols
        out.append({
            "fingerprint":   (r.get(key_cols["fingerprint"]) or "").strip(),
            "example_name":  (r.get(key_cols["example_name"]) or "").strip(),
            # Handle potential absence of optional columns gracefully
            "count":         (r.get(key_cols["count"]) or "").strip() if key_cols.get("count") else "",
            "last_seen":     (r.get(key_cols["last_seen"]) or "").strip() if key_cols.get("last_seen") else "",
            "sample_amount": (r.get(key_cols["sample_amount"]) or "").strip() if key_cols.get("sample_amount") else "",
        })
    return out

# ---------------------------------------------------------------------
# Pattern helpers (Used for fuzzy patterns and exact titles)
# ---------------------------------------------------------------------

# Keep A-Z, 0-9 and '&' (For Fuzzy Tokenization)
_ALNUM_AMP = re.compile(r"[^A-Z0-9&]+")
# (RC1a Polish): Check for at least one alphanumeric character
_HAS_ALNUM = re.compile(r"[A-Z0-9]")

# Title sanitizer for exact mode titles (Allows more characters for readability)
# Allow A-Z, 0-9, &, _, space, hyphen, apostrophe.
_TITLE_SAFE_RE = re.compile(r"[^A-Z0-9&_ '-]+")


def _tokenize_for_pattern(name: str) -> Optional[str]:
    """
    (Fuzzy Mode Only) Pick a clean token from the name for a wildcard pattern.
    Prefers the longest token with >= 3 chars. (Naive implementation for RC1).
    """
    if not name:
        return None
    up = name.upper()
    up = _ALNUM_AMP.sub(" ", up)
    
    # (RC1a Patch): Added _HAS_ALNUM.search(t) to reject symbol-only tokens (e.g., "&&&")
    tokens = [t for t in up.split() if len(t) >= 3 and not t.isdigit() and _HAS_ALNUM.search(t)]
    
    if not tokens:
        return None
    # Deterministic sorting: primary key length (desc), secondary key alphabetical (asc)
    tokens.sort(key=lambda x: (-len(x), x))
    return tokens[0]

def _sanitize_title(name: str) -> str:
    """(Exact Mode Only) Create a safe, readable title slug."""
    if not name:
        return "CANDIDATE"
    # Simple normalization: uppercase, replace unsafe chars with space.
    title = _TITLE_SAFE_RE.sub(' ', name.upper())
    # Collapse multiple spaces into one, strip, and cap length.
    title = re.sub(r'\s+', ' ', title).strip()[:64]
    return title or "CANDIDATE"


def _escape_quotes(s: str, quote_char: str = '"') -> str:
    """Escape the specific quote character used for enclosing the string."""
    return s.replace(quote_char, f'\\{quote_char}')

# ---------------------------------------------------------------------
# Existing rules de-dupe (supports fuzzy and exact styles)
# ---------------------------------------------------------------------

# Regression Fix (RC1): Ensure regexes support both single (') and double (") quotes.
# (Robustness v3): Added re.DOTALL for resilience against multiline formatting.
_FUZZY_RE = re.compile(r'counterparty\s*~\s*[\'"](.*?)[\'"]', re.IGNORECASE | re.DOTALL)
_EXACT_RE = re.compile(r'counterparty\s*==\s*[\'"](.*?)[\'"]', re.IGNORECASE | re.DOTALL)

def _load_existing_patterns(rules_path: Optional[str]) -> Tuple[List[str], List[str]]:
    if not rules_path or not os.path.exists(rules_path):
        return [], []
    try:
        # Ensure BOM-safe reading
        with open(rules_path, "r", encoding="utf-8-sig") as f:
            text = f.read()
    except Exception as e:
        print(f"Warning: Could not read existing rules file {rules_path}: {e}", file=sys.stderr)
        return [], []
        
    # Extract patterns using the updated regexes
    return (
        _FUZZY_RE.findall(text),
        _EXACT_RE.findall(text),
    )

def _already_covered_fuzzy(pattern: str, existing_fuzzy: List[str]) -> bool:
    """Check if the proposed fuzzy pattern is already covered."""
    if pattern in existing_fuzzy:
        return True
    # Rough containment check to avoid near-duplicates
    p_core = pattern.strip("*")
    if not p_core:
        return False
    for p in existing_fuzzy:
        core = p.strip("*")
        if core and (core in pattern or p_core in p):
            return True
    return False

# (Optimization v3): Updated signature to accept pre-computed exact_set.
def _already_covered_exact(name: str, existing_exact_set: Set[str], existing_fuzzy: List[str]) -> bool:
    """Check if the proposed exact name is already covered by exact or fuzzy rules."""
    # (RC1a Semantic Fix & Optimization): Case-insensitive check using the pre-computed set.
    name_lower = name.lower()
    if name_lower in existing_exact_set:
        return True
    
    # Also consider if existing fuzzy patterns already cover this exact name.
    # This is a heuristic check for de-duplication purposes.
    for fuzzy_pattern in existing_fuzzy:
        # Basic wildcard simulation: if the core of the fuzzy pattern is in the name.
        core = fuzzy_pattern.strip("*").lower()
        if core and core in name_lower:
            # Heuristic match: assume existing fuzzy rule covers this specific example.
            return True
    return False

# ---------------------------------------------------------------------
# Rule generation
# ---------------------------------------------------------------------

def _build_meta(count: str, last_seen: str, sample_amount: str) -> str:
    bits = []
    if count:       bits.append(f"freq={count}")
    if last_seen:   bits.append(f"last={last_seen}")
    if sample_amount: bits.append(f"sample_amt={sample_amount}")
    return f"# SUGGESTED ({', '.join(bits)})" if bits else "# SUGGESTED"

def generate_rules(
    cands: List[Dict[str, str]],
    prefix: str,
    default_category: str,
    existing_rules_file: Optional[str],
    emit_match: str = "fuzzy",  # "fuzzy" | "exact"
    quote_char: str = '"', # Default to double quotes for output
) -> List[str]:
    exist_fuzzy, exist_exact = _load_existing_patterns(existing_rules_file)
    
    # (Optimization v3): Create a case-insensitive set for fast O(1) exact match lookups.
    exist_exact_set = {e.lower() for e in exist_exact}
    
    blocks: List[str] = []

    for c in cands:
        # (RC1a Robustness): Enforce non-empty fingerprint and example name.
        fp = c.get("fingerprint", "")
        example = c.get("example_name", "")
        
        if not fp or not example:
            # Skip candidates missing essential data.
            continue

        count   = c.get("count", "")
        last    = c.get("last_seen", "")
        samp    = c.get("sample_amount", "")

        meta  = _build_meta(count, last, samp)
        category_escaped = _escape_quotes(default_category, quote_char)
        
        # Prepare example comment (no escaping needed for comments)
        example_comment = example

        if emit_match == "exact":
            # (RC1a Semantic Fix): Use the example_name for matching and the title.

            # Check coverage against the actual example name
            if _already_covered_exact(example, exist_exact_set, exist_fuzzy):
                continue
            
            # Generate a safe title slug from the example name
            title_slug = _sanitize_title(example)
            title_escaped = _escape_quotes(f'{prefix}: {title_slug}', quote_char)
            
            # Use the raw example name for the exact match condition
            exact_name_escaped = _escape_quotes(example, quote_char)

            block = [
                meta,
                f'# Example: {example_comment}',
                f'# Fingerprint: {fp}', # Add fingerprint for context
                f'rule {quote_char}{title_escaped}{quote_char} ' + "{",
                "  match:",
                # Match the raw example name, as the engine matches against the raw counterparty field.
                f'    - counterparty == {quote_char}{exact_name_escaped}{quote_char}',
                "  set:",
                f'    - category = {quote_char}{category_escaped}{quote_char}',
                "}",
                ""
            ]
        else:  # fuzzy (default)
            # Fuzzy mode retains existing tokenization logic.
            
            # Try tokenizing the example name first, then the fingerprint if the example fails.
            token = _tokenize_for_pattern(example) or _tokenize_for_pattern(fp)

            if not token:
                # Skip if no suitable token (>=3 chars) is found (Safety Guard for RC1).
                continue

            pattern = f'*{token}*'
            if _already_covered_fuzzy(pattern, exist_fuzzy):
                continue
            
            # Use the token for the title (naive heuristic for RC1)
            title_escaped = _escape_quotes(f'{prefix}: {token}', quote_char)
            pattern_escaped = _escape_quotes(pattern, quote_char)

            block = [
                meta,
                f"# Example: {example_comment}",
                f'# Fingerprint: {fp}', # Add fingerprint for context
                f'rule {quote_char}{title_escaped}{quote_char} ' + "{",
                "  match:",
                f'    - counterparty ~ {quote_char}{pattern_escaped}{quote_char}',
                "  set:",
                f'    - category = {quote_char}{category_escaped}{quote_char}',
                "}",
                ""
            ]

        blocks.append("\n".join(block))

    return blocks

# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Generate draft .fin rules from discovery candidates")
    ap.add_argument("--input", required=True, help="Path to candidates.csv from discover.py")
    ap.add_argument("--output", required=True, help="Path to write/append draft_rules.fin")
    ap.add_argument("--rules", help="Existing rules.fin to avoid duplicate patterns")
    ap.add_argument("--category", default="Review", help='Default category to set (default: "Review")')
    ap.add_argument("--prefix", default="SUGGEST", help='Rule name prefix (default: "SUGGEST")')
    ap.add_argument("--emit-match", choices=["fuzzy", "exact"], default="fuzzy",
                    help='Matching style: "fuzzy" (counterparty ~ "*TOKEN*") or '
                         '"exact" (counterparty == "NAME"). Default: fuzzy.')
    ap.add_argument("--quote-style", choices=['"', "'"], default='"',
                    help='Preferred quote style for output rules (default: double quotes ").')

    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--append", action="store_true", help="Append to output file (default behavior if file exists)")
    mode.add_argument("--overwrite", action="store_true", help="Overwrite output file")
    
    # Handle CLI invocation robustly
    try:
        if len(sys.argv) == 1:
            ap.print_help(sys.stderr)
            return 1
        args = ap.parse_args()
    except SystemExit:
        # Argparse handles --help/errors internally
        return 0 if '--help' in sys.argv else 1

    try:
        cands = _read_candidates(args.input)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 1

    if not cands:
        print("No candidates found in input file. Nothing to write.")
        return 0
    
    # (RC1a Robustness): Calculate metrics before generation for accurate reporting
    total_cands = len(cands)
    valid_cands_count = len([c for c in cands if c.get("fingerprint", "") and c.get("example_name", "")])
    skipped_count = total_cands - valid_cands_count

    blocks = generate_rules(
        cands=cands,
        prefix=args.prefix,
        default_category=args.category,
        existing_rules_file=args.rules,
        emit_match=args.emit_match,
        quote_char=args.quote_style,
    )

    if skipped_count > 0:
        print(f"Note: Skipped {skipped_count} row(s) missing fingerprints or example names.")

    if not blocks:
        if valid_cands_count == 0:
             print("No valid candidates found after filtering. Nothing to write.")
        else:
            print("All valid candidates appear to be covered by existing rules or were skipped. Nothing new to write.")
        return 0

    # Determine write mode
    if args.overwrite:
        write_mode = "w"
    elif args.append or os.path.exists(args.output):
        write_mode = "a"
    else:
        write_mode = "w"

    try:
        # Write output using standard utf-8
        with open(args.output, write_mode, encoding="utf-8", newline="") as f:
            # Add a newline separator if appending to a non-empty file
            if write_mode == "a":
                try:
                    # Attempt to check if the file is non-empty before appending separator
                    if os.path.getsize(args.output) > 0:
                         f.write("\n\n# --- Appended by suggest.py ---\n\n")
                except OSError:
                    pass # Handle potential race conditions gracefully
                
            f.write("\n".join(blocks))
    except Exception as e:
        print(f"FATAL: Failed to write to output file {args.output}: {e}", file=sys.stderr)
        return 1

    print(f"✅ {'Appended' if write_mode == 'a' else 'Wrote'} {len(blocks)} draft rule(s) to {args.output}")
    return 0

if __name__ == "__main__":
    # Ensure compatibility with PYTHONWARNINGS=error policy
    if not sys.warnoptions:
        import warnings
        warnings.simplefilter("default")
    sys.exit(main())