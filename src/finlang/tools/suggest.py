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


# FinLang — Financial Rules DSL
# suggest.py — Generate draft .fin rules from discovery candidates
#
# v0.6.2 stable: engine-compatible, deterministic, and comment-rich.
# - Default: emits fuzzy rules (counterparty ~ "*TOKEN*")
# - Optional: --emit-match exact  -> emits exact rules (counterparty == "NAME")
# - BOM-safe CSV reader, flexible header mapping, tidy output, de-dupe.
#
# Usage:
#   python -m finlang.tools.suggest --input candidates.csv --output draft_rules.fin \
#     [--rules existing_rules.fin] [--category "Review"] [--prefix "SUGGEST"] \
#     [--emit-match fuzzy|exact] [--overwrite|--append]

import argparse
import csv
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------
# Header mapping / CSV read (BOM-safe, case-insensitive)
# ---------------------------------------------------------------------

def _read_candidates(path: str) -> List[Dict[str, str]]:
    """
    Read a candidates CSV coming from discover.py.

    Logical fields we try to map (case-insensitive):
      - fingerprint: counterparty_fingerprint | fingerprint | vendor_key
      - example_name: example_counterparty_name | example | sample_name | counterparty | name
      - count: count | freq | frequency
      - last_seen: last_seen_date | last_seen | last_date | sample_date | date
      - sample_amount: sample_amount | example_amount | sample_amt | amount
    """
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    if not rows:
        return []

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

    # Minimal required inputs to propose a rule
    missing = [k for k in ("example_name", "fingerprint", "count") if key_cols.get(k) is None]
    if missing:
        raise SystemExit(
            f"FATAL: Missing required columns in {path}: {missing}. "
            f"Present: {sorted(cols.keys())}"
        )

    out: List[Dict[str, str]] = []
    for r in rows:
        out.append({
            "fingerprint":   (r.get(key_cols["fingerprint"], "") or "").strip(),
            "example_name":  (r.get(key_cols["example_name"], "") or "").strip(),
            "count":         (r.get(key_cols["count"], "") or "").strip(),
            "last_seen":     (r.get(key_cols["last_seen"], "") or "").strip() if key_cols["last_seen"] else "",
            "sample_amount": (r.get(key_cols["sample_amount"], "") or "").strip() if key_cols["sample_amount"] else "",
        })
    return out

# ---------------------------------------------------------------------
# Pattern helpers (stable tokenization; avoid over-broad patterns)
# ---------------------------------------------------------------------

_ALNUM_AMP = re.compile(r"[^A-Z0-9&]+")

def _tokenize_for_pattern(name: str) -> Optional[str]:
    """
    Pick a clean token from the example name to use in a wildcard pattern.
      - Uppercase, keep A–Z, 0–9 and '&'
      - Split on non-alnum
      - Prefer the longest token with >= 3 chars and not purely digits
    """
    if not name:
        return None
    up = name.upper()
    up = _ALNUM_AMP.sub(" ", up)
    tokens = [t for t in up.split() if len(t) >= 3 and not t.isdigit()]
    if not tokens:
        return None
    tokens.sort(key=len, reverse=True)
    return tokens[0]

def _escape_quotes(s: str) -> str:
    return s.replace('"', '\\"')

# ---------------------------------------------------------------------
# Existing rules de-dupe (supports fuzzy and exact styles)
# ---------------------------------------------------------------------

_FUZZY_RE = re.compile(r'counterparty\s*~\s*"(.*?)"', re.IGNORECASE)
_EXACT_RE = re.compile(r'counterparty\s*==\s*"(.*?)"', re.IGNORECASE)
# Accept legacy/broken patterns to avoid duplicates if present in user rules
_FINGERPRINT_RE = re.compile(r'fingerprint\s*==\s*"(.*?)"', re.IGNORECASE)

def _load_existing_patterns(rules_path: Optional[str]) -> Tuple[List[str], List[str], List[str]]:
    if not rules_path or not os.path.exists(rules_path):
        return [], [], []
    with open(rules_path, "r", encoding="utf-8") as f:
        text = f.read()
    return (
        _FUZZY_RE.findall(text),
        _EXACT_RE.findall(text),
        _FINGERPRINT_RE.findall(text),
    )

def _already_covered_fuzzy(pattern: str, existing_fuzzy: List[str]) -> bool:
    if pattern in existing_fuzzy:
        return True
    # rough containment to avoid near-duplicates
    p_core = pattern.strip("*")
    if not p_core:
        return False
    for p in existing_fuzzy:
        core = p.strip("*")
        if core and (core in pattern or p_core in p):
            return True
    return False

def _already_covered_exact(name: str, existing_exact: List[str], existing_fuzzy: List[str]) -> bool:
    if name in existing_exact:
        return True
    # also consider fuzzy patterns that already cover this exact name
    return _already_covered_fuzzy(f"*{name}*", existing_fuzzy)

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
) -> List[str]:
    exist_fuzzy, exist_exact, exist_fingerprint = _load_existing_patterns(existing_rules_file)
    blocks: List[str] = []

    for c in cands:
        example = c.get("example_name", "") or c.get("fingerprint", "")
        fp      = c.get("fingerprint", "")
        count   = c.get("count", "")
        last    = c.get("last_seen", "")
        samp    = c.get("sample_amount", "")

        token = _tokenize_for_pattern(example) or _tokenize_for_pattern(fp)
        if not token:
            continue

        meta  = _build_meta(count, last, samp)
        title = f'{prefix}: {token}'
        example_escaped = _escape_quotes(example or fp or token)

        if emit_match == "exact":
            exact_name = _escape_quotes((fp or example).upper())
            if _already_covered_exact(exact_name, exist_exact, exist_fuzzy) or exact_name in exist_fingerprint:
                continue
            block = [
                meta,
                f'rule "{title}" ' + "{",
                "  match:",
                f'    - counterparty == "{exact_name}"',
                "  set:",
                f'    - category = "{default_category}"',
                "}",
                ""
            ]
        else:  # fuzzy (default)
            pattern = f'*{_escape_quotes(token)}*'
            if _already_covered_fuzzy(pattern, exist_fuzzy):
                continue
            block = [
                meta,
                f"# Example: {example_escaped}",
                f'rule "{title}" ' + "{",
                "  match:",
                f'    - counterparty ~ "{pattern}"',
                "  set:",
                f'    - category = "{default_category}"',
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
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--append", action="store_true", help="Append to output file (default)")
    mode.add_argument("--overwrite", action="store_true", help="Overwrite output file")
    args = ap.parse_args()

    cands = _read_candidates(args.input)
    if not cands:
        print("No candidates found. Nothing to write.")
        return 0

    blocks = generate_rules(
        cands=cands,
        prefix=args.prefix,
        default_category=args.category,
        existing_rules_file=args.rules,
        emit_match=args.emit_match,
    )

    if not blocks:
        print("All candidates appear to be covered by existing rules. Nothing to write.")
        return 0

    write_mode = "w" if args.overwrite or (not os.path.exists(args.output) and not args.append) else "a"
    with open(args.output, write_mode, encoding="utf-8", newline="") as f:
        if write_mode == "a":
            f.write("\n")
        f.write("\n".join(blocks))

    print(f"✅ Wrote {len(blocks)} draft rule(s) to {args.output}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
