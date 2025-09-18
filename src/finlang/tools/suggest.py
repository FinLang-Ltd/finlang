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
suggest.py — Generate draft .fin rules from discovery candidates

Usage:
  python suggest.py --input discovery/candidates.csv --output draft_rules.fin \
    [--rules rules.fin] [--category "Review"] [--prefix "SUGGEST"] [--overwrite|--append]

Behavior:
  - Reads candidates.csv produced by discover.py (headers flexible; auto-detected).
  - Emits conservative, review-first draft rules like:

      # SUGGESTED (freq=134, last=2025-08-21, sample_amt=-92.34)
      rule "SUGGEST: TESCO" {
        match:
          - counterparty ~ "*TESCO*"
        set:
          - category = "Review"
      }

  - De-duplicates against existing rules if --rules is provided (skips patterns already present).
  - Appends to output by default; use --overwrite to replace.
"""

import argparse
import csv
import os
import re
import sys
from typing import List, Dict, Optional


# ----------------- CSV Reader (header-flexible) -----------------

def _read_candidates(path: str) -> List[Dict[str, str]]:
    """
    Read a candidates CSV coming from discover.py.

    Logical fields we try to map (case-insensitive):
      - fingerprint: counterparty_fingerprint | fingerprint | vendor_key
      - example name: example_counterparty_name | example | sample_name | counterparty | name
      - count: count | freq | frequency
      - last_seen: last_seen_date | last_seen | last_date | sample_date | date
      - sample_amount: sample_amount | example_amount | sample_amt | amount
    """
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return []

    cols = {c.lower(): c for c in (reader.fieldnames or [])}

    def pick(*names):
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

    missing = [k for k, v in key_cols.items() if v is None and k in ("fingerprint", "example_name", "count")]
    if missing:
        raise SystemExit(
            f"FATAL: Missing required columns in {path}: {missing}. "
            f"Present: {sorted(cols.keys())}"
        )

    out = []
    for r in rows:
        out.append({
            "fingerprint":   (r.get(key_cols["fingerprint"], "") or "").strip(),
            "example_name":  (r.get(key_cols["example_name"], "") or "").strip(),
            "count":         (r.get(key_cols["count"], "") or "").strip(),
            "last_seen":     (r.get(key_cols["last_seen"], "") or "").strip() if key_cols["last_seen"] else "",
            "sample_amount": (r.get(key_cols["sample_amount"], "") or "").strip() if key_cols["sample_amount"] else "",
        })
    return out


# ----------------- Pattern helpers -----------------

def _tokenize_for_pattern(name: str) -> Optional[str]:
    """
    Pick a clean token from the example name to use in a wildcard pattern.
    Strategy:
      - Uppercase, keep alnum and '&'
      - Split on non-alnum
      - Prefer the longest token with >= 3 chars that's not purely digits
    """
    if not name:
        return None
    up = name.upper()
    up = re.sub(r"[^A-Z0-9&]+", " ", up)
    tokens = [t for t in up.split() if len(t) >= 3 and not t.isdigit()]
    if not tokens:
        return None
    tokens.sort(key=len, reverse=True)
    return tokens[0]


def _load_existing_patterns(rules_path: Optional[str]) -> List[str]:
    if not rules_path or not os.path.exists(rules_path):
        return []
    with open(rules_path, "r", encoding="utf-8") as f:
        text = f.read()
    # naive extract of counterparty ~ "PATTERN"
    return re.findall(r'counterparty\s*~\s*"(.*?)"', text, flags=re.IGNORECASE)


def _already_covered(pattern: str, existing: List[str]) -> bool:
    if pattern in existing:
        return True
    # rough containment check to avoid near-duplicates
    for p in existing:
        p_s = p.strip("*")
        pat_s = pattern.strip("*")
        if p_s and (p_s in pattern or pat_s in p):
            return True
    return False


# ----------------- Generation -----------------

def generate_rules(cands: List[Dict[str, str]],
                   prefix: str,
                   default_category: str,
                   existing_rules_file: Optional[str]) -> List[str]:
    existing = _load_existing_patterns(existing_rules_file)
    blocks: List[str] = []
    for c in cands:
        token = _tokenize_for_pattern(c.get("example_name", "")) or _tokenize_for_pattern(c.get("fingerprint", ""))
        if not token:
            continue
        pattern = f"*{token}*"
        if _already_covered(pattern, existing):
            continue

        freq = c.get("count", "")
        last_seen = c.get("last_seen", "")
        samp = c.get("sample_amount", "")

        title = f'{prefix}: {token}'
        meta_bits = []
        if freq:      meta_bits.append(f"freq={freq}")
        if last_seen: meta_bits.append(f"last={last_seen}")
        if samp:      meta_bits.append(f"sample_amt={samp}")
        meta = f"# SUGGESTED ({', '.join(meta_bits)})" if meta_bits else "# SUGGESTED"

        block = [
            meta,
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


# ----------------- CLI -----------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Generate draft .fin rules from discovery candidates")
    ap.add_argument("--input", required=True, help="Path to candidates.csv from discover.py")
    ap.add_argument("--output", required=True, help="Path to write/append draft_rules.fin")
    ap.add_argument("--rules", help="Existing rules.fin to avoid duplicate patterns")
    ap.add_argument("--category", default="Review", help='Default category to set (default: "Review")')
    ap.add_argument("--prefix", default="SUGGEST", help='Rule name prefix (default: "SUGGEST")')
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--append", action="store_true", help="Append to output file (default)")
    mode.add_argument("--overwrite", action="store_true", help="Overwrite output file")
    args = ap.parse_args()

    cands = _read_candidates(args.input)
    if not cands:
        print("No candidates found. Nothing to write.")
        return 0

    blocks = generate_rules(cands, args.prefix, args.category, args.rules)
    if not blocks:
        print("All candidates appear to be covered by existing rules. Nothing to write.")
        return 0

    # choose write mode
    write_mode = "w" if args.overwrite or (not os.path.exists(args.output) and not args.append) else "a"
    with open(args.output, write_mode, encoding="utf-8", newline="") as f:
        if write_mode == "a":
            f.write("\n")
        f.write("\n".join(blocks))

    print(f"✅ Wrote {len(blocks)} draft rule(s) to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())