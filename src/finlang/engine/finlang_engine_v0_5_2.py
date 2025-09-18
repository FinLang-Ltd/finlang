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


import os
import re
import pandas as pd
from typing import List, Dict, Any, Tuple

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
    low, high = float(parts[0]), float(parts[1])
    if low > high:
        raise ValueError("Range low > high")
    return low, high

def _looks_number(s: str) -> bool:
    try:
        float(s); return True
    except Exception:
        return False

def _wildcard_to_regex(pattern: str) -> re.Pattern:
    escaped = re.escape(pattern).replace(r"\*", ".*")
    return re.compile(escaped, re.IGNORECASE | re.DOTALL)

def parse_condition(condition: str) -> Tuple[str, str, Any]:
    m = CONDITION_PATTERN.match(condition)
    if not m:
        raise ValueError(f"Invalid syntax: '{condition}'")
    field = m.group("field").strip().lower()
    op    = m.group("op")
    raw   = m.group("value").strip()
    if field not in CANON_FIELDS_MATCH:
        raise KeyError(f"Unknown field '{field}'")
    if op == "in":
        low, high = _parse_range(_unescape_quoted(raw))
        return field, op, (low, high)
    return field, op, _unescape_quoted(raw)

def _get_lower_col(df: pd.DataFrame, col: str, cache: Dict[str, pd.Series]) -> pd.Series:
    ckey = f"{col}_lower"
    if ckey not in cache:
        cache[ckey] = df[col].astype(str).str.lower()
    return cache[ckey]

def _get_str_col(df: pd.DataFrame, col: str, cache: Dict[str, pd.Series]) -> pd.Series:
    ckey = f"{col}_str"
    if ckey not in cache:
        cache[ckey] = df[col].astype(str)
    return cache[ckey]

def get_condition_mask(condition: str, df: pd.DataFrame, cache: Dict[str, pd.Series]) -> pd.Series:
    try:
        field, op, value = parse_condition(condition)
        if field not in df.columns:
            raise KeyError(f"Missing column '{field}' in DataFrame")
        col = field

        if op == "==":
            if field == "amount":
                if not isinstance(value, (int, float)) and not _looks_number(value):
                    raise TypeError(f"'amount ==' needs numeric, got '{value}'")
                return df[col] == float(value)
            lower = _get_lower_col(df, col, cache)
            return lower == str(value).lower()

        if op == "~":
            raw = str(value)
            lower = _get_lower_col(df, col, cache)
            val = raw.lower()

            # FAST PATHS (avoid regex):
            star_count = raw.count('*')
            if star_count == 0:
                return lower.str.contains(val, regex=False)
            if star_count == 1:
                if raw.endswith('*') and not raw.startswith('*'):
                    # prefix match
                    return lower.str.startswith(val[:-1])
                if raw.startswith('*') and not raw.endswith('*'):
                    # suffix match
                    return lower.str.endswith(val[1:])
            if star_count == 2 and raw.startswith('*') and raw.endswith('*'):
                # substring match
                return lower.str.contains(val.strip('*'), regex=False)

            # Fallback to regex for complex wildcard patterns
            s = _get_str_col(df, col, cache)
            return s.str.contains(_wildcard_to_regex(raw), na=False)

        if op == "in":
            if field != "amount":
                raise TypeError("'in' is only valid for 'amount'")
            low, high = value
            return df[col].between(low, high)

    except Exception as e:
        print(f"⚠️ Warning: Skipping invalid condition '{condition}'. Reason: {e}")
        return pd.Series(False, index=df.index)

    return pd.Series(False, index=df.index)

def apply_vectorized_actions(df: pd.DataFrame, actions: List[str], mask: pd.Series) -> pd.DataFrame:
    for action in actions:
        try:
            if "+=" in action:
                field, val = action.split("+=", 1)
                field, val = field.strip().lower(), _unescape_quoted(val.strip())
                if field != "flags":
                    raise KeyError("'+=' only valid for 'flags'")
                def add_flag(current_flags):
                    current = "" if pd.isna(current_flags) else str(current_flags)
                    parts = [p.strip() for p in current.split(",") if p.strip()]
                    if val not in parts:
                        parts.append(val)
                    return ", ".join(parts)
                df.loc[mask, field] = df.loc[mask, field].apply(add_flag)
            elif "=" in action:
                field, val = action.split("=", 1)
                field, val = field.strip().lower(), _unescape_quoted(val.strip())
                
                # --- PATCH START ---
                # Disallow assignment to 'flags', forcing the use of '+='
                if field == "flags":
                    raise ValueError("'flags' can only be modified with '+=', not '='. This prevents accidental overwrites.")
                # --- PATCH END ---

                if field not in CANON_FIELDS_SET:
                    raise KeyError(f"Unknown set field '{field}'")
                if field == "exclude":
                    df.loc[mask, field] = (str(val).strip().lower() == "true")
                else:
                    df.loc[mask, field] = val
            else:
                raise ValueError("Action must contain '=' or '+='")
        except Exception as e:
            print(f"⚠️ Warning: Skipping invalid action '{action}'. Reason: {e}")
    return df

def run_audit(
    df: pd.DataFrame,
    rules: List[Dict[str, Any]],
    audit_mode: str | None = None,
    audit_row_cap: int | None = None,
) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    mode = (audit_mode or os.getenv("FINLANG_AUDIT_MODE", "full")).lower()
    cap  = int(os.getenv("FINLANG_AUDIT_MAX", "100000")) if audit_row_cap is None else int(audit_row_cap)

    audit_log: List[Dict[str, Any]] = []
    df = df.copy()

    for col in TEXT_COLS:
        if col not in df.columns:
            df[col] = pd.Series(dtype="object")
        else:
            df[col] = df[col].astype("object")
    if "exclude" not in df.columns:
        df["exclude"] = False
    else:
        s = df.get("exclude")
        if s is None:
            df["exclude"] = False
        else:
            df["exclude"] = s.astype("boolean", copy=False).fillna(False).astype(bool)

    cache: Dict[str, pd.Series] = {}

    for rule in rules:
        matches = rule.get("match") or []
        if not matches:
            continue

        mask = pd.Series(True, index=df.index)
        for cond in matches:
            mask &= get_condition_mask(cond, df, cache)
        if not mask.any():
            continue

        original_rows = df.loc[mask].copy()
        df = apply_vectorized_actions(df, rule.get("set", []), mask)

        if mode == "none":
            continue

        touched_cols: set[str] = set()
        for a in rule.get("set", []):
            f = None
            if "+=" in a:
                f = a.split("+=", 1)[0].strip().lower()
            elif "=" in a:
                f = a.split("=", 1)[0].strip().lower()
            if f in CANON_FIELDS_SET:
                touched_cols.add(f)
        if not touched_cols:
            continue

        updated_rows = df.loc[mask, list(touched_cols)]
        changes_added = 0
        row_changes: Dict[int, Dict[str, Dict[str, Any]]] = {}

        for col in touched_cols:
            orig = original_rows[col].astype(str)
            new  = updated_rows[col].astype(str)
            changed = orig != new
            if not changed.any():
                continue

            for idx in changed[changed].index:
                if changes_added >= cap:
                    break
                entry = row_changes.get(idx)
                if entry is None:
                    entry = {}
                    row_changes[idx] = entry
                entry[col] = {"old": original_rows.at[idx, col], "new": df.at[idx, col]}
                changes_added += 1
            if changes_added >= cap:
                break

        if row_changes:
            for idx, changes in row_changes.items():
                audit_log.append({"row": int(idx) + 2, "rule": rule.get("name", "<unnamed>"), "changes": changes})
            if changes_added >= cap:
                audit_log.append({
                    "rule": rule.get("name", "<unnamed>"),
                    "truncated": True,
                    "note": f"Audit detail capped at {cap} cell changes. Set FINLANG_AUDIT_MAX or use FINLANG_AUDIT_MODE=lite/none."
                })

    return df, audit_log
