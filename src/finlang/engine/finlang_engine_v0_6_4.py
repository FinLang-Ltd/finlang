# finlang_engine_v0_6_4_rc1.py
# FinLang — Financial Rules DSL (v0.6.4-rc1)
# Strict-aware engine build
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


import os
import re
import pandas as pd
from typing import List, Dict, Any, Tuple
import math # Required for isnan/isinf check (RC1a Polish)

CANON_FIELDS_MATCH = {"counterparty", "amount", "category", "flags", "status", "memo"}
CANON_FIELDS_SET   = {"category", "status", "memo", "flags", "exclude"}
TEXT_COLS = ["category", "flags", "status", "memo"]

CONDITION_PATTERN = re.compile(
    r"""
    ^\s*
    (?P<field>\w+)
    \s+
    (?P<op>==|~|in)
    \s+
    (?P<value>
        "(?:\\.|[^"\\])*"
        |
        '(?:\\.|[^'\\])*'
        |
        -?\d+(?:\.\d+)?\s*\.\.\s*-?\d+(?:\.\d+)?
        |
        \S+
    )
    \s*$
    """, re.VERBOSE,
)

ACTION_PATTERN = re.compile(
    r"""
    ^\s*
    (?P<field>\w+)
    \s*
    (?P<op>=\s*|\+=)
    \s*
    (?P<value>
        "(?:\\.|[^"\\])*"
        |
        '(?:\\.|[^'\\])*'
        |
        \S+
    )
    \s*$
    """, re.VERBOSE | re.IGNORECASE,
)

def _unescape_quoted(s: str) -> str:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        q = s[0]
        inner = s[1:-1]
        inner = inner.replace('\\\\', '\\')
        if q == '"':
            inner = inner.replace('\\"', '"')
        else:
            inner = inner.replace("\\'", "'")
        return inner
    return s

def _parse_range(value: str) -> Tuple[float, float]:
    parts = re.split(r"\s*\.\.\s*", value.strip())
    if len(parts) != 2:
        raise ValueError("Range must be 'low..high'")
    try:
        # We rely on float() conversion as the baseline; NaN/Inf checks happen during mask application if needed
        low, high = float(parts[0]), float(parts[1])
    except ValueError:
        raise ValueError(f"Invalid numeric range values in '{value}'")
        
    if low > high:
        raise ValueError("Range low > high")
    return low, high

def _looks_number(s: str) -> bool:
    """Check if a string can be safely converted to a float (excluding NaN/Inf)."""
    try:
        f = float(s)
        # (RC1a Polish): Exclude NaN (f != f) and Inf for practical financial comparisons
        return (f == f) and (f != float('inf')) and (f != float('-inf'))
    except Exception:
        return False

def _wildcard_to_regex(pattern: str) -> re.Pattern:
    escaped = re.escape(pattern).replace(r"\*", ".*")
    # Anchor the regex for full match semantics
    return re.compile(f"^{escaped}$", re.IGNORECASE | re.DOTALL)

def parse_condition(condition: str) -> Tuple[str, str, Any]:
    """Parse a single condition into (field, operator, value).
    Allowed operators: '==', '~' (wildcard), 'in' (numeric range 'low..high' on 'amount')."""
    m = CONDITION_PATTERN.match(condition)
    if not m:
        raise ValueError(f"Invalid syntax: '{condition}'. Allowed operators are ==, ~, in.")
    field = m.group("field").strip().lower()
    op    = m.group("op")
    raw   = m.group("value").strip()
    if field not in CANON_FIELDS_MATCH:
        raise KeyError(f"Unknown field '{field}'")
    if op == "in":
        if field != "amount":
             raise ValueError(f"Operator 'in' (range) is only valid for 'amount', not '{field}'")
        low, high = _parse_range(_unescape_quoted(raw))
        return field, op, (low, high)
    return field, op, _unescape_quoted(raw)

def parse_action(action: str) -> Tuple[str, str, Any]:
    """Parse a single action into (field, operator, value)."""
    # Handle the 'exclude' keyword shortcut
    if action.strip().lower() == "exclude":
        return "exclude", "=", True

    m = ACTION_PATTERN.match(action)
    if not m:
        raise ValueError(f"Invalid action syntax: '{action}'. Expected format: field = value or field += value.")

    field = m.group("field").strip().lower()
    op = m.group("op").strip()
    raw_value = m.group("value").strip()

    if field not in CANON_FIELDS_SET:
        raise KeyError(f"Cannot set unknown field '{field}'")

    # Enforce append-only for flags (v0.6.4 requirement)
    if field == "flags" and op == "=":
         raise ValueError(f"Use '+=' to append flags; direct assignment '=' is disallowed for field 'flags'.")

    if op == "+=" and field not in TEXT_COLS:
        raise TypeError(f"Operator '+=' (append) is only valid for text fields, not '{field}'.")

    return field, op, _unescape_quoted(raw_value)


def _get_lower_col(df: pd.DataFrame, col: str, cache: Dict[str, pd.Series]) -> pd.Series:
    """Helper to get a cached, lowered, string version of a column."""
    ckey = f"{col}_lower"
    if ckey not in cache:
        # Ensure NA/None are handled (v0.6.4 requirement)
        cache[ckey] = df[col].fillna("").astype(str).str.lower()
    return cache[ckey]

def _get_str_col(df: pd.DataFrame, col: str, cache: Dict[str, pd.Series]) -> pd.Series:
    """Helper to get a cached, string version of a column."""
    ckey = f"{col}_str"
    if ckey not in cache:
        # Ensure NA/None are handled (v0.6.4 requirement)
        cache[ckey] = df[col].fillna("").astype(str)
    return cache[ckey]

def get_condition_mask(condition: str, df: pd.DataFrame, cache: Dict[str, pd.Series]) -> pd.Series:
    """Calculate the boolean mask for a single condition."""
    try:
        field, op, value = parse_condition(condition)
        if field not in df.columns:
            # Strict schema check (optional via environment variable)
            if os.getenv("FINLANG_STRICT_SCHEMA", "0") == "1":
                 raise KeyError(f"Strict schema: Missing column '{field}' in DataFrame")
            # If column is missing and not strict, it's a non-match
            return pd.Series(False, index=df.index)
            
        col = field

        if op == "==":
            if field == "amount":
                # (RC1a Polish): Validate input robustness (NaN/Inf)
                if not isinstance(value, (int, float)) and not _looks_number(value):
                    # _looks_number ensures non-NaN/Inf
                    raise TypeError(f"'amount ==' needs numeric (non-NaN/Inf), got '{value}'")
                
                fv = float(value)
                # (RC1a Polish): Redundant safety check for NaN (though _looks_number handles it)
                if math.isnan(fv):
                    raise TypeError("'amount == NaN' is not a valid condition")

                return df[col] == fv
            
            # Case-insensitive exact match for text fields
            lower = _get_lower_col(df, col, cache)
            return lower == str(value).lower()

        if op == "~":
            # Wildcard match (case-insensitive)
            raw = str(value)
            lower = _get_lower_col(df, col, cache)
            val = raw.lower()

            # FAST PATHS (avoid regex):
            star_count = raw.count('*')
            if star_count == 0:
                # Exact match if no wildcard
                return lower == val
            if star_count == 1:
                if raw.endswith('*') and not raw.startswith('*'):
                    # prefix match: "ABC*"
                    return lower.str.startswith(val[:-1])
                if raw.startswith('*') and not raw.endswith('*'):
                    # suffix match: "*ABC"
                    return lower.str.endswith(val[1:])
            if star_count == 2 and raw.startswith('*') and raw.endswith('*') and len(val) > 2:
                # substring match: "*ABC*"
                # Check if the core substring contains '*' itself before using non-regex contains
                if '*' not in val[1:-1]:
                    return lower.str.contains(val[1:-1], regex=False)

            # Fallback to regex for complex wildcard patterns (e.g. "A*B*C")
            # We use the string representation for regex matching
            s = _get_str_col(df, col, cache)
            regex = _wildcard_to_regex(raw)
            # Use match() for anchored regex comparison
            return s.str.match(regex, na=False)

        if op == "in" and field == "amount":
            low, high = value
            # (RC1a Polish): Check range boundaries for NaN/Inf.
            if math.isnan(low) or math.isnan(high) or math.isinf(low) or math.isinf(high):
                 raise TypeError(f"'amount in' range boundaries cannot be NaN or Inf, got {low}..{high}")
            return df[col].between(low, high)

        # Should be unreachable due to parse_condition validation
        raise ValueError(f"Internal Error: Unsupported operation '{op}' for field '{field}'")

    except (ValueError, TypeError, KeyError) as e:
        # Wrap specific errors in RuntimeError for clear provenance
        raise RuntimeError(f"Error processing condition '{condition}': {e}") from e


# Define audit limit globally
AUDIT_MAX = int(os.getenv("FINLANG_AUDIT_MAX", 5000))

def run_audit(df_in: pd.DataFrame, rules: List[Dict[str, Any]], audit_mode: str = "lite") -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """Execute the ruleset against the DataFrame and return the processed DataFrame and audit log."""
    df = df_in.copy()
    audit_log = []
    
    # Preamble: Ensure text columns exist, are string type, and handle NaN/None (v0.6.4 requirement)
    for col in TEXT_COLS:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)
        elif col in CANON_FIELDS_SET:
            # Initialize settable columns if missing (required for +=)
            df[col] = ""

    # Initialize cache for optimized column access
    cache: Dict[str, pd.Series] = {}
    
    audit_count = 0
    audit_capped = False

    for rule_idx, rule in enumerate(rules):
        rule_name = rule.get("name", f"<unnamed_{rule_idx}>")
        matches = rule.get("match", [])
        actions = rule.get("set", [])

        # Skip empty rules
        if not matches or not actions:
            continue

        try:
            # 1. Calculate mask
            mask = pd.Series(True, index=df.index)
            conditions_parsed = []
            for condition in matches:
                mask &= get_condition_mask(condition, df, cache)
                conditions_parsed.append(condition) # Store for audit log
            
            if not mask.any():
                continue

            # 2. Capture BEFORE state for audit (NEW)
            matched_indices = df.index[mask]
            
            # Determine which fields might change
            mutable_fields = {"category", "flags", "memo", "status", "exclude"}
            fields_to_watch = [f for f in mutable_fields if f in df.columns]
            
            # Snapshot before state
            if audit_mode != "none" and fields_to_watch:
                pre_state = df.loc[mask, fields_to_watch].copy()
            else:
                pre_state = None

            # 3. Apply actions (Vectorized)
            # Parse actions first
            actions_parsed = []
            parsed_actions_list = []
            for action in actions:
                field, op, val = parse_action(action)
                parsed_actions_list.append((field, op, val))
                actions_parsed.append(action) # Store original string for audit log

            # Apply parsed actions
            for field, op, val in parsed_actions_list:
                if field == "exclude":
                     # Handle exclusion logic if implemented
                     # Placeholder for future implementation (e.g. removing rows)
                     continue

                if op == "=":
                    df.loc[mask, field] = val
                elif op == "+=":
                    # Vectorized append (v0.6.4 optimization)
                    current = df.loc[mask, field] # Already guaranteed str and filled by preamble
                    
                    # Add spacer only if current is not empty
                    spacer = current.str.len().gt(0).map({True: ' ', False: ''})
                    merged = (current + spacer + str(val)).str.strip()
                    
                    # (RC1a Polish): De-duplicate flags while preserving order
                    if field == "flags":
                        # Keep unique, order-preserving tokens using dict.fromkeys (Python 3.7+)
                        df.loc[mask, field] = merged.str.split().map(lambda xs: " ".join(dict.fromkeys(xs)))
                    else:
                        # Standard append for category/memo/status
                        df.loc[mask, field] = merged

            # 4. Log audit with DIFF TRACKING (NEW)
            if audit_mode != "none" and not audit_capped:
                num_matched = len(matched_indices)
                
                if audit_count + num_matched > AUDIT_MAX:
                    num_to_log = AUDIT_MAX - audit_count
                    indices_to_log = matched_indices[:num_to_log]
                    audit_capped = True
                else:
                    indices_to_log = matched_indices
                
                # Capture AFTER state
                post_state = df.loc[mask, fields_to_watch] if fields_to_watch else None
                
                for idx in indices_to_log:
                    # Ensure index is native int for JSON serialization
                    entry = {
                        "index": int(idx),
                        "rule": rule_name,
                    }
                    
                    # Compute diffs (NEW)
                    if pre_state is not None and post_state is not None:
                        diffs = {}
                        for col in fields_to_watch:
                            old_val = pre_state.at[idx, col]
                            new_val = post_state.at[idx, col]
                            
                            # Convert empty strings to None for cleaner JSON
                            old_clean = None if old_val == "" else old_val
                            new_clean = None if new_val == "" else new_val
                            
                            # Only log if actually changed
                            if old_val != new_val:
                                diffs[col] = {
                                    "old": old_clean,
                                    "new": new_clean
                                }
                        
                        # LITE mode: only log if something changed
                        if audit_mode == "lite":
                            if diffs:  # Only add entry if there were changes
                                entry["changes"] = diffs
                                audit_log.append(entry)
                                # Don't increment audit_count here, do it after the if/else
                            # If no diffs in lite mode, skip this entry entirely
                            else:
                                continue  # Skip to next index
                        else:  # FULL mode
                            entry["match"] = conditions_parsed
                            entry["set"] = actions_parsed
                            entry["changes"] = diffs  # Include even if empty
                            audit_log.append(entry)
                    else:
                        # Fallback if no fields to watch (shouldn't happen normally)
                        if audit_mode == "full":
                            entry["match"] = conditions_parsed
                            entry["set"] = actions_parsed
                        audit_log.append(entry)
                    
                    # Increment count only if we actually added an entry
                    if audit_mode == "lite":
                        # Count was already handled in the if diffs block above
                        pass
                    else:
                        pass  # Will be counted below
                
                # Update audit count based on what was actually logged
                if audit_mode == "lite":
                    # Count only entries with changes
                    audit_count = len(audit_log)
                else:
                    # Count all matched indices
                    audit_count += len(indices_to_log)


        except RuntimeError as e:
            # Catch runtime errors from condition/action processing and associate with the rule
            raise RuntimeError(f"Error executing rule '{rule_name}': {e}") from e
        except Exception as e:
            # Catch unexpected errors (like parsing errors if CLI didn't catch them)
             raise RuntimeError(f"Unexpected error during rule '{rule_name}': {type(e).__name__}: {e}") from e

    if audit_capped and audit_mode != "none":
        audit_log.append({"message": f"Audit log capped at {AUDIT_MAX} entries."})

    return df, audit_log