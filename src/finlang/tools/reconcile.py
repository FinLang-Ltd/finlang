# reconcile.py
# FinLang — Independent ML Validation Layer (v0.7.8)
# Copyright (C) 2026 FinLang Ltd
#
# This file is part of FinLang, licensed under the GNU Affero General Public
# License v3.0 or later. See <https://www.gnu.org/licenses/agpl-3.0.html>.
#
# Commercial licensing: contact@finlang.co.uk

"""
Independent ML validation layer for FinLang (SOL-040).

Compares FinLang's deterministic output against an external system's
output (typically an ML categorisation model) and produces a full audit
trail of agreements and disagreements with rule attribution.

Phase 1 MVP (v0.7.8):
  - Positional alignment only (row N in FinLang output = row N in ML output)
  - Single reconcile field by default ("category"); custom fields via flag
  - Strict mode only (any mismatch = exit code 3)
  - Output artifacts: reconcile_report.json + reconcile_mismatches.csv
  - Audit linkage via FinLang's audit.json (--audit-mode full required)

Architecture mirrors verify.py: decoupled module, post-engine hook,
NamedTuple result, optional artifact directory, headless mode.
"""

import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import NamedTuple, List, Optional, Dict, Any, Tuple


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class IdentityMismatchError(ValueError):
    """Raised when --reconcile-identity-fields detects positional misalignment.

    Subclasses ValueError so the CLI's existing structural-error path
    (FATAL message + exit 1) handles it without new dispatch machinery.
    Field-level mismatch reporting is suppressed when this is raised —
    a positionally misaligned comparison cannot be trusted.
    """


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

class ReconcileResult(NamedTuple):
    success: bool
    rows_compared: int
    matches: int
    mismatches: int
    mismatch_rows: List[dict]  # List of {row_number, ml_value, finlang_value, ...} dicts
    reconcile_fields: List[str]
    alignment_mode: str  # "positional" for Phase 1
    duration_seconds: float
    finlang_output_file: str
    ml_output_file: str
    # audit_entries_loaded: count of audit entries indexed by row.
    #   0  = audit_path not provided (no audit requested)
    #   -1 = audit_path provided but file missing or unparseable
    #   >0 = number of rule-attributed entries loaded
    audit_entries_loaded: int = 0
    # SOL-104 key-based alignment: orphan rows (present on one side only).
    # Tuples of context dicts (row_number/date/amount/counterparty/memo/
    # category). Always empty in positional mode. Tuple, not list — NamedTuple
    # defaults are class-level, so the default must be immutable.
    orphans_finlang: tuple = ()
    orphans_ml: tuple = ()
    # How the ML side's date convention was decided. Recorded so the artefact
    # states its own assumption: {"mode": inferred|assumed|explicit|
    # not_applicable, "dayfirst": bool, "ambiguous_values": int,
    # "evidence": str|None}. "assumed" means the data could not settle it.
    ml_date_convention: Optional[dict] = None


# ---------------------------------------------------------------------------
# CSV reading helpers
# ---------------------------------------------------------------------------

def _read_csv_rows(path: str) -> List[Dict[str, str]]:
    """Read all rows of a CSV as a list of dicts.

    Auto-detects delimiter via csv.Sniffer (handles comma, semicolon, tab,
    pipe). Reads with utf-8-sig encoding to tolerate BOMs. Preserves column
    names verbatim — case-insensitive matching is the caller's responsibility.

    Args:
        path: Path to CSV file.

    Returns:
        List of dicts, one per row, keys are column names from the header.

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If the file has no header or zero data rows.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV not found: {path}")

    rows: List[Dict[str, str]] = []
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        sample = f.read(8192)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = "excel"
        reader = csv.DictReader(f, dialect=dialect)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header row: {path}")
        for i, row in enumerate(reader):
            # Ragged rows: DictReader puts surplus fields in a list under the
            # None restkey and fills missing fields with None. Either way the
            # row can't be trusted — fail structurally, naming the row.
            if None in row or any(v is None for v in row.values()):
                raise ValueError(
                    f"Malformed CSV row {i + 2} in {path}: field count differs "
                    f"from header (unquoted comma or truncated row?)"
                )
            rows.append({k: (v or "").strip() for k, v in row.items()})
    if not rows:
        raise ValueError(f"CSV has zero data rows: {path}")
    return rows


def _resolve_field(row: Dict[str, str], field: str) -> Optional[str]:
    """Resolve a field name case-insensitively against a row dict.

    Returns the value if any column matches the field name (case-insensitive),
    else None.
    """
    field_lower = field.lower()
    for k, v in row.items():
        if k.lower() == field_lower:
            return v
    return None


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------

def _align_positional(
    finlang_rows: List[Dict[str, str]],
    ml_rows: List[Dict[str, str]],
) -> None:
    """Validate positional alignment of two row lists.

    Phase 1: row counts must match exactly. Mismatch is a hard error
    (caller exits with code 1, not exit code 3 — this is a structural
    problem, not a categorisation disagreement).

    Raises:
        ValueError: If row counts differ.
    """
    if len(finlang_rows) != len(ml_rows):
        raise ValueError(
            f"Row count mismatch: FinLang output has {len(finlang_rows)} rows, "
            f"ML output has {len(ml_rows)} rows. Positional alignment requires "
            f"identical row counts. Use --reconcile-key for key-based alignment "
            f"(Phase 2 feature)."
        )


def _validate_field_presence(
    rows: List[Dict[str, str]],
    fields: List[str],
    source_label: str,
) -> None:
    """Validate that each reconcile field exists (case-insensitively) in rows.

    Phase 1 contract: both FinLang output and ML output must contain every
    requested reconcile field. A missing field on either side is a hard
    error (caller exits with code 1) rather than silently treating every
    row as a mismatch against an empty value.

    Raises:
        ValueError: If any reconcile field is absent from rows[0].keys().
    """
    if not rows:
        return  # Empty CSVs are caught by alignment, not here.
    available_lower = {k.lower() for k in rows[0].keys()}
    missing = [f for f in fields if f.lower() not in available_lower]
    if missing:
        raise ValueError(
            f"Reconcile field(s) not found in {source_label}: {missing}. "
            f"Available columns: {sorted(rows[0].keys())}"
        )


# ---------------------------------------------------------------------------
# Identity guard (SOL-103) — positional alignment verification
# ---------------------------------------------------------------------------

_AMBIGUOUS_DATE_RE = re.compile(r"^\s*(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})\s*$")


def is_ambiguous_date(value: Optional[str]) -> bool:
    """True if a date string could be read as either DD/MM or MM/DD.

    Both leading components <= 12 means the convention cannot be inferred
    from the value alone: '05/01/2026' is 5 January or 1 May depending on
    locale, and nothing in the string says which. ISO (YYYY-MM-DD) and any
    value with a component > 12 are unambiguous and return False.
    """
    m = _AMBIGUOUS_DATE_RE.match(value or "")
    if not m:
        return False
    first, second = int(m.group(1)), int(m.group(2))
    return first <= 12 and second <= 12


def _identity_normalise(
    field: str,
    value: Optional[str],
    dayfirst: bool = False,
    date_format: Optional[str] = None,
) -> str:
    """Normalise one identity-field value for positional comparison.

    Comparison contract (documented in reconciliation.md):
      - amount: normalised via verify.py's `_normalize_amount_string`
        (synced with the engine's `_to_number` — handles CR/DR suffixes,
        parens, currency symbols, trailing zeros: "-10.00" == "-10.0")
      - date: normalised via verify.py's `_normalize_date_string` to ISO
        8601, applying the run's locale flags. The FinLang side is
        engine-written ISO (unaffected), but the ML side comes from an
        external system and may carry local formats — so `dayfirst` /
        `date_format` MUST reach here. Before v0.8.3 they did not, and an
        ambiguous day-first ML date (e.g. '05/01/2026') canonicalised under
        the wrong convention, reporting an identical transaction as two
        orphans with no warning.
      - everything else: whitespace-stripped, case-insensitive

    Reuses verify.py's normalisers rather than forking new copies — one
    source of truth per DOCUMENT_MAP's amount-parsing sync rule.
    """
    from finlang.tools.verify import (
        _normalize_amount_string,
        _normalize_date_string,
        _strip_injection_quote,
    )
    v = (value or "").strip()
    field_lower = field.lower()
    if field_lower == "amount":
        return _normalize_amount_string(v)
    if field_lower == "date":
        return _normalize_date_string(v, dayfirst=dayfirst, date_format=date_format)
    # Unquote the engine's formula-injection prefix before comparing: the
    # FinLang side is engine-written ('+44 TAXI...) while an ML pipeline
    # reads the raw source (+44 TAXI...). Same transaction, must compare
    # equal — applies to both identity-guard and key construction (this
    # function is the shared canonicalisation contract for both).
    return _strip_injection_quote(v).strip().lower()


def _check_identity(
    finlang_rows: List[Dict[str, str]],
    ml_rows: List[Dict[str, str]],
    identity_fields: List[str],
    ml_dayfirst: bool = False,
    ml_date_format: Optional[str] = None,
) -> List[dict]:
    """Compare identity fields positionally; return failure dicts.

    A failure dict names the 1-indexed position, the identity fields
    that differ there, and both sides' raw values for every configured
    identity field (raw, not normalised — the artefact must show what
    the files actually contain).
    """
    failures: List[dict] = []
    for i, (fl_row, ml_row) in enumerate(zip(finlang_rows, ml_rows)):
        differing: List[str] = []
        for field in identity_fields:
            fl_val = _identity_normalise(field, _resolve_field(fl_row, field))
            ml_val = _identity_normalise(field, _resolve_field(ml_row, field),
                                         dayfirst=ml_dayfirst,
                                         date_format=ml_date_format)
            if fl_val != ml_val:
                differing.append(field)
        if not differing:
            continue
        failure = {
            "row_number": i + 1,
            "differing_identity_fields": ",".join(differing),
        }
        for field in identity_fields:
            failure[f"finlang_{field}"] = _resolve_field(fl_row, field) or ""
            failure[f"ml_{field}"] = _resolve_field(ml_row, field) or ""
        failures.append(failure)
    return failures


# JSON identity-failure artefact embeds at most this many row-level
# failures; the CSV always carries the full set. Keeps the JSON readable
# when an entire large file is misaligned.
_IDENTITY_JSON_FAILURE_CAP = 100


def _write_identity_failures(
    failures: List[dict],
    identity_fields: List[str],
    total_rows: int,
    finlang_output: str,
    ml_output: str,
    output_dir: str,
) -> None:
    """Write reconcile_identity_failures.csv (full) + .json (summary)."""
    columns = ["row_number", "differing_identity_fields"]
    for field in identity_fields:
        columns.append(f"finlang_{field}")
        columns.append(f"ml_{field}")

    csv_path = os.path.join(output_dir, "reconcile_identity_failures.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for failure in failures:
            writer.writerow([failure.get(col, "") for col in columns])

    summary: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "finlang_output_file": os.path.basename(finlang_output),
        "ml_output_file": os.path.basename(ml_output),
        "identity_fields": identity_fields,
        "total_rows": total_rows,
        "identity_failures": len(failures),
        "status": "IDENTITY MISMATCH",
        "failures": failures[:_IDENTITY_JSON_FAILURE_CAP],
        "failures_truncated": len(failures) > _IDENTITY_JSON_FAILURE_CAP,
    }
    json_path = os.path.join(output_dir, "reconcile_identity_failures.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


# ---------------------------------------------------------------------------
# Key-based alignment (SOL-104) — --reconcile-key
# ---------------------------------------------------------------------------

def _build_key_index(
    rows: List[Dict[str, str]],
    key_fields: List[str],
    source_label: str,
    dayfirst: bool = False,
    date_format: Optional[str] = None,
) -> Dict[tuple, int]:
    """Build a composite-key → row-index map; fail strict on duplicates.

    Keys are canonicalised via `_identity_normalise` (same contract as the
    identity guard: amounts numerically, dates ISO, text case-insensitive).
    Duplicate keys on either side are a hard error — silent first-match
    would degenerate back into positional behaviour, which defeats the
    purpose of key alignment.

    Raises:
        ValueError: If any composite key appears on more than one row.
    """
    index: Dict[tuple, int] = {}
    duplicates: Dict[tuple, List[int]] = {}
    for i, row in enumerate(rows):
        key = tuple(
            _identity_normalise(f, _resolve_field(row, f),
                                dayfirst=dayfirst, date_format=date_format)
            for f in key_fields
        )
        if key in index or key in duplicates:
            duplicates.setdefault(key, [index[key]] if key in index else [])
            duplicates[key].append(i)
            index.pop(key, None)
        else:
            index[key] = i
    if duplicates:
        examples = []
        for key, idxs in list(duplicates.items())[:5]:
            rows_str = ",".join(str(i + 1) for i in sorted(idxs))
            examples.append(f"{key!r} on rows [{rows_str}]")
        raise ValueError(
            f"Duplicate key(s) in {source_label}: {len(duplicates)} composite "
            f"key value(s) appear on multiple rows — safe alignment cannot "
            f"proceed (first-match would silently degenerate to positional "
            f"behaviour). Examples: {'; '.join(examples)}. Refine "
            f"--reconcile-key to a unique composite (e.g. add date or amount)."
        )
    return index


def _orphan_context(row: Dict[str, str], row_number: int) -> dict:
    """Build the context dict written per orphan row (fixed column set)."""
    return {
        "row_number": row_number,
        "date": _resolve_field(row, "date") or "",
        "amount": _resolve_field(row, "amount") or "",
        "counterparty": _resolve_field(row, "counterparty") or "",
        "memo": _resolve_field(row, "memo") or "",
        "category": _resolve_field(row, "category") or "",
    }


def _validate_ml_date_format(
    ml_rows: List[Dict[str, str]],
    fields: List[str],
    date_format: str,
) -> None:
    """An explicit --reconcile-date-format must actually parse the ML dates.

    Without this, an invalid or mismatched format was recorded as
    mode: "explicit" while the normaliser quietly caught the failure and
    returned the RAW string — so the artefact claimed a format was applied
    when it never was, and a reconciliation could even pass on raw-string
    coincidence. (Codex review, 26 Jul 2026.)

    Raises:
        ValueError: If the format itself is invalid, or any non-empty ML
            date value fails to parse under it. Structural — the caller
            maps this to FATAL exit 1, same as other reconcile input errors.
    """
    import pandas as pd

    date_fields = [f for f in fields if f.lower() == "date"]
    if not date_fields:
        return
    # One vectorised parse over unique values, not a scalar pd.to_datetime
    # per row — the per-call cost (~45 µs) would otherwise double the
    # date-parsing share of a large explicit-format reconciliation.
    first_row: Dict[str, int] = {}
    for i, row in enumerate(ml_rows):
        for f in date_fields:
            v = (_resolve_field(row, f) or "").strip()
            if v and v not in first_row:
                first_row[v] = i
    if not first_row:
        raise ValueError(
            f"--reconcile-date-format {date_format!r} was given, but the ML "
            f"output contains no non-empty date values to apply it to."
        )
    values = list(first_row)
    try:
        parsed = pd.to_datetime(values, format=date_format, errors="coerce")
    except (ValueError, TypeError) as e:
        raise ValueError(
            f"--reconcile-date-format {date_format!r} is not a valid "
            f"date format: {e}"
        )
    # Insertion order = first-appearance order, so the first failing value
    # here is the one at the earliest failing row (matches the old per-row
    # scan's error attribution).
    for v, dt in zip(values, parsed):
        if pd.isna(dt):
            raise ValueError(
                f"--reconcile-date-format {date_format!r} does not parse "
                f"ML output date {v!r} (row {first_row[v] + 1}). The stated "
                f"format must match the ML file's dates — fix the format, or "
                f"omit it to infer from the column."
            )


def _infer_ml_date_convention(
    ml_rows: List[Dict[str, str]],
    fields: List[str],
    headless: bool,
) -> Dict[str, Any]:
    """Infer whether the ML side's dates are day-first, from the column itself.

    FinLang's own output is engine-written ISO, so only the ML side needs
    inferring. The inference is a deterministic function of the whole column,
    not a per-value guess:

      - any value whose FIRST component is > 12  -> day-first   (13/01/2026)
      - any value whose SECOND component is > 12 -> month-first (01/13/2026)
      - both present                             -> mixed formats, unresolvable
      - neither (every value ambiguous, or all ISO) -> cannot infer

    Returns:
        A decision dict recorded verbatim in reconcile_report.json so the
        artefact states its own assumption:
            mode: "inferred" | "assumed" | "not_applicable"
            dayfirst: bool — the convention actually applied to the ML side
            ambiguous_values: int — how many values could be read either way
            evidence: str — the value that settled it, when inferred
        "assumed" means the data could not settle it and month-first was
        applied by default. That case is a stated assumption, not a fact.

    Raises:
        ValueError: If the column contains BOTH day-first-only and
            month-first-only values. That is not a convention, it is two
            conventions in one file, and no single reading is correct.
    """
    date_fields = [f for f in fields if f.lower() == "date"]
    if not date_fields:
        return {"mode": "not_applicable", "dayfirst": False,
                "ambiguous_values": 0, "evidence": None}

    saw_dayfirst = saw_monthfirst = False
    dayfirst_ex = monthfirst_ex = ""
    ambiguous: List[str] = []

    for row in ml_rows:
        for f in date_fields:
            raw = (_resolve_field(row, f) or "").strip()
            m = _AMBIGUOUS_DATE_RE.match(raw)
            if not m:
                continue  # ISO or unparseable — nothing to infer from
            first, second = int(m.group(1)), int(m.group(2))
            if first > 12:
                saw_dayfirst = True
                dayfirst_ex = dayfirst_ex or raw
            elif second > 12:
                saw_monthfirst = True
                monthfirst_ex = monthfirst_ex or raw
            else:
                ambiguous.append(raw)

    if saw_dayfirst and saw_monthfirst:
        raise ValueError(
            f"ML output mixes date conventions: '{dayfirst_ex}' can only be "
            f"day-first, '{monthfirst_ex}' can only be month-first. No single "
            f"reading is correct. Fix the ML export, or pass "
            f"--reconcile-date-format to state one explicitly."
        )
    if saw_dayfirst or saw_monthfirst:
        return {
            "mode": "inferred",
            "dayfirst": saw_dayfirst,
            "ambiguous_values": len(ambiguous),
            "evidence": dayfirst_ex if saw_dayfirst else monthfirst_ex,
        }

    # NOT gated on headless: this is a correctness caveat, not progress
    # chatter. Headless is what CI runs, and CI is exactly where a silently
    # assumed date convention would go unnoticed.
    if ambiguous:
        sample = ", ".join(dict.fromkeys(ambiguous))
        print(
            f"WARNING: every date in the ML output is ambiguous "
            f"(e.g. {sample.split(',')[0].strip()}) — the convention cannot be "
            f"inferred from the data.",
            file=sys.stderr,
        )
        print(
            "         ASSUMING month-first. If the ML system emits day-first "
            "dates, pass --reconcile-date-format \"%d/%m/%Y\" — otherwise "
            "matching rows can be reported as orphans on both sides.",
            file=sys.stderr,
        )
        print(
            "         This assumption is recorded in reconcile_report.json "
            "under ml_date_convention.",
            file=sys.stderr,
        )
    return {
        "mode": "assumed" if ambiguous else "not_applicable",
        "dayfirst": False,
        "ambiguous_values": len(ambiguous),
        "evidence": None,
    }


def _align_by_key(
    finlang_rows: List[Dict[str, str]],
    ml_rows: List[Dict[str, str]],
    key_fields: List[str],
    ml_dayfirst: bool = False,
    ml_date_format: Optional[str] = None,
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[int], List[dict], List[dict]]:
    """Align two row lists by composite key.

    Returns:
        (fl_matched, ml_matched, fl_indices, orphans_finlang, orphans_ml)
        where fl_matched[i] pairs with ml_matched[i], fl_indices[i] is the
        0-based FinLang row index (drives audit linkage + row_number), and
        the orphan lists carry `_orphan_context` dicts. Matched pairs are
        ordered by FinLang row order (deterministic).

    Raises:
        ValueError: On duplicate keys (either side).
    """
    # FinLang's side is engine-written ISO by construction — never reinterpret
    # it. Only the ML side carries an external system's local convention.
    fl_index = _build_key_index(finlang_rows, key_fields, "FinLang output")
    ml_index = _build_key_index(ml_rows, key_fields, "ML output",
                                dayfirst=ml_dayfirst, date_format=ml_date_format)

    fl_matched: List[Dict[str, str]] = []
    ml_matched: List[Dict[str, str]] = []
    fl_indices: List[int] = []
    orphans_finlang: List[dict] = []
    matched_ml_indices: set = set()

    for i, row in enumerate(finlang_rows):
        key = tuple(
            _identity_normalise(f, _resolve_field(row, f))
            for f in key_fields
        )
        ml_i = ml_index.get(key)
        if ml_i is None:
            orphans_finlang.append(_orphan_context(row, i + 1))
        else:
            fl_matched.append(row)
            ml_matched.append(ml_rows[ml_i])
            fl_indices.append(i)
            matched_ml_indices.add(ml_i)

    orphans_ml = [
        _orphan_context(row, i + 1)
        for i, row in enumerate(ml_rows)
        if i not in matched_ml_indices
    ]

    return fl_matched, ml_matched, fl_indices, orphans_finlang, orphans_ml


# ---------------------------------------------------------------------------
# Audit linkage
# ---------------------------------------------------------------------------

def _safe_reason(match: Any) -> str:
    """Extract a defensively-sanitised string reason from match conditions.

    Defensive against degenerate audit-entry shapes — if `match` is not a
    list, or its first element is not already a string, return empty.
    Truncate to 200 chars. Prevents shipping JSON-stringified Python
    representations of unexpected types into mismatch CSVs.
    """
    if not isinstance(match, list) or not match:
        return ""
    first = match[0]
    if not isinstance(first, str):
        return ""
    return first[:200]


def _load_audit_index(audit_path: Optional[str]) -> Tuple[Dict[int, Dict[str, str]], int]:
    """Build a row-index → {rule_name, reason} map from audit.json.

    Audit JSON schema (lite/full mode):
        [
          {"index": 0, "rule": "Energy: Shell", "changes": {...}},
          ...
        ]

    Returns:
        Tuple of (index_dict, status_count).
            status_count == 0  → audit_path not provided
            status_count == -1 → audit_path provided but file missing or
                                 unparseable (caller should warn)
            status_count >  0  → number of indexed entries
    """
    if not audit_path:
        return {}, 0

    if not os.path.exists(audit_path):
        return {}, -1

    try:
        with open(audit_path, "r", encoding="utf-8") as f:
            audit_entries = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}, -1

    if not isinstance(audit_entries, list):
        return {}, -1

    index: Dict[int, Dict[str, str]] = {}
    for entry in audit_entries:
        if not isinstance(entry, dict):
            continue
        idx = entry.get("index")
        if not isinstance(idx, int):
            continue
        rule_name = entry.get("rule", "")
        if not isinstance(rule_name, str):
            rule_name = ""
        index[idx] = {
            "rule_name": rule_name,
            "reason": _safe_reason(entry.get("match")),
        }
    return index, len(index)


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def _compare_rows(
    finlang_rows: List[Dict[str, str]],
    ml_rows: List[Dict[str, str]],
    reconcile_fields: List[str],
    audit_index: Dict[int, Dict[str, str]],
    row_indices: Optional[List[int]] = None,
) -> List[dict]:
    """Compare aligned rows field-by-field on the reconcile fields.

    Args:
        row_indices: Original 0-based FinLang row indices for each aligned
            pair (key mode passes these so row_number and audit linkage
            reference the FinLang file, not the aligned position). None =
            positional mode, where position IS the index.

    Returns a list of mismatch dicts. Each mismatch contains:
        - row_number: 1-indexed FinLang row number (excluding header)
        - date, amount, counterparty: contextual fields if present
        - For each reconcile field: ml_<field>, finlang_<field>
        - finlang_rule_matched: from audit_index if available
        - finlang_audit_reason: from audit_index if available
    """
    mismatches: List[dict] = []
    for pos, (fl_row, ml_row) in enumerate(zip(finlang_rows, ml_rows)):
        i = row_indices[pos] if row_indices is not None else pos
        differing_fields: List[str] = []
        for field in reconcile_fields:
            fl_val = _resolve_field(fl_row, field) or ""
            ml_val = _resolve_field(ml_row, field) or ""
            if fl_val != ml_val:
                differing_fields.append(field)

        if not differing_fields:
            continue

        audit_info = audit_index.get(i, {})
        mismatch = {
            "row_number": i + 1,
            "date": _resolve_field(fl_row, "date") or "",
            "amount": _resolve_field(fl_row, "amount") or "",
            "counterparty": _resolve_field(fl_row, "counterparty") or "",
            "memo": _resolve_field(fl_row, "memo") or "",
            "differing_fields": ",".join(differing_fields),
            "finlang_rule_matched": audit_info.get("rule_name", ""),
            "finlang_audit_reason": audit_info.get("reason", ""),
        }
        for field in reconcile_fields:
            mismatch[f"ml_{field}"] = _resolve_field(ml_row, field) or ""
            mismatch[f"finlang_{field}"] = _resolve_field(fl_row, field) or ""
        mismatches.append(mismatch)

    return mismatches


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_reconciliation(
    finlang_output: str,
    ml_output: str,
    reconcile_fields: Optional[List[str]] = None,
    output_dir: Optional[str] = None,
    audit_path: Optional[str] = None,
    headless: bool = False,
    emit_html: bool = False,
    identity_fields: Optional[List[str]] = None,
    key_fields: Optional[List[str]] = None,
    ml_date_format: Optional[str] = None,
) -> ReconcileResult:
    """Run reconciliation: compare FinLang output against ML output.

    Args:
        finlang_output: Path to FinLang's output CSV (engine result).
        ml_output: Path to ML system's output CSV.
        reconcile_fields: Field names to compare. Defaults to ["category"].
        output_dir: If set, write reconcile_report.json and (if any
            mismatches) reconcile_mismatches.csv into this directory.
        audit_path: Path to FinLang's audit.json. Used to populate rule
            name + reason on mismatches. Optional; absence means mismatches
            ship without audit linkage.
        headless: If True, suppress console output.
        emit_html: If True (and ``output_dir`` is set), additionally
            write a self-contained HTML report to
            ``<output_dir>/reconcile_report.html``. Has no effect when
            ``output_dir`` is None.
        identity_fields: Optional list of fields to identity-check
            positionally BEFORE field comparison (SOL-103 identity
            guard). If row N's identity fields differ between the two
            files, the comparison cannot be trusted: identity-failure
            artefacts are written (when ``output_dir`` is set), normal
            mismatch reporting is suppressed, and IdentityMismatchError
            is raised (CLI exits 1 — structural, not exit 3).
        key_fields: Optional list of fields forming a composite key for
            key-based alignment (SOL-104). Replaces positional alignment
            entirely: rows match by canonicalised key, row counts may
            differ, unmatched rows on either side are reported as
            orphans (exit 3 — review needed). Duplicate keys on either
            side are a hard error (ValueError — CLI exits 1). Mutually
            exclusive with ``identity_fields``.

    Returns:
        ReconcileResult NamedTuple.

    Raises:
        FileNotFoundError: If finlang_output or ml_output is missing.
        ValueError: If row counts differ (positional alignment) or files
            have no header.
        IdentityMismatchError: If ``identity_fields`` is set and any row's
            identity fields are positionally misaligned.
    """
    t0 = time.perf_counter()
    fields = list(reconcile_fields) if reconcile_fields else ["category"]
    if not fields:
        # Defensive: empty fields list reaches here only if caller built one.
        # The CLI rejects --reconcile-fields="" at parse time (exit 2).
        raise ValueError("reconcile_fields must contain at least one field name.")
    if identity_fields and key_fields:
        # Defensive: the CLI rejects this combination at parse time (exit 2).
        raise ValueError(
            "identity_fields and key_fields are mutually exclusive — one is "
            "a positional guard, the other replaces positional alignment."
        )

    finlang_rows = _read_csv_rows(finlang_output)
    ml_rows = _read_csv_rows(ml_output)

    if not key_fields:
        _align_positional(finlang_rows, ml_rows)

    # Field-presence check: each reconcile field must exist on BOTH sides.
    # Missing on either side = exit 1 (structural error), not exit 3.
    _validate_field_presence(finlang_rows, fields, "FinLang output")
    _validate_field_presence(ml_rows, fields, "ML output")

    # Identity guard (SOL-103): verify positional alignment of identity
    # fields BEFORE trusting any field-level comparison. Refuses to
    # produce confident-looking mismatches over misaligned rows.
    if identity_fields:
        _validate_field_presence(finlang_rows, identity_fields, "FinLang output")
        _validate_field_presence(ml_rows, identity_fields, "ML output")
        if ml_date_format:
            _validate_ml_date_format(ml_rows, identity_fields, ml_date_format)
            date_decision = {"mode": "explicit", "dayfirst": False,
                             "ambiguous_values": 0, "evidence": ml_date_format}
        else:
            date_decision = _infer_ml_date_convention(
                ml_rows, identity_fields, headless)
        id_dayfirst = date_decision["dayfirst"]
        identity_failures = _check_identity(
            finlang_rows, ml_rows, identity_fields,
            ml_dayfirst=id_dayfirst, ml_date_format=ml_date_format,
        )
        if identity_failures:
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                _write_identity_failures(
                    identity_failures, identity_fields, len(finlang_rows),
                    finlang_output, ml_output, output_dir,
                )
            if not headless:
                print(
                    f"Identity guard: {len(identity_failures)} of "
                    f"{len(finlang_rows)} rows misaligned on "
                    f"[{','.join(identity_fields)}] — structural failure."
                )
                for failure in identity_failures[:10]:
                    row = failure.get("row_number", "?")
                    differing = failure.get("differing_identity_fields", "?")
                    print(f"   Row {row}: identity differs on [{differing}]")
                if len(identity_failures) > 10:
                    print(f"   ... and {len(identity_failures) - 10} more")
            artefact_note = (
                " See reconcile_identity_failures.csv for the full set."
                if output_dir else ""
            )
            raise IdentityMismatchError(
                f"Identity check failed: {len(identity_failures)} of "
                f"{len(finlang_rows)} rows have misaligned identity fields "
                f"[{','.join(identity_fields)}]. Row order has drifted "
                f"between the two files; field-level mismatch reporting "
                f"suppressed (it cannot be trusted). Use --reconcile-key "
                f"for key-based alignment.{artefact_note}"
            )

    audit_index, audit_count = _load_audit_index(audit_path)
    if audit_count == -1 and not headless:
        print(
            f"WARN: --reconcile audit linkage requested but '{audit_path}' "
            f"could not be loaded. Mismatches will lack rule attribution.",
            file=sys.stderr,
        )

    orphans_finlang: List[dict] = []
    orphans_ml: List[dict] = []
    if key_fields:
        # Key fields must exist on both sides (structural — exit 1).
        _validate_field_presence(finlang_rows, key_fields, "FinLang output")
        _validate_field_presence(ml_rows, key_fields, "ML output")
        # The ML side is an external system's CSV: infer its date convention
        # from the column unless the caller stated one explicitly.
        if ml_date_format:
            _validate_ml_date_format(ml_rows, key_fields, ml_date_format)
            date_decision = {"mode": "explicit", "dayfirst": False,
                             "ambiguous_values": 0, "evidence": ml_date_format}
        else:
            date_decision = _infer_ml_date_convention(ml_rows, key_fields, headless)
        ml_dayfirst = date_decision["dayfirst"]
        (fl_matched, ml_matched, fl_indices,
         orphans_finlang, orphans_ml) = _align_by_key(
            finlang_rows, ml_rows, key_fields,
            ml_dayfirst=ml_dayfirst, ml_date_format=ml_date_format)
        mismatches = _compare_rows(
            fl_matched, ml_matched, fields, audit_index, row_indices=fl_indices)
        rows_compared = len(fl_matched)
        alignment_mode = "key:" + ",".join(key_fields)
    else:
        mismatches = _compare_rows(finlang_rows, ml_rows, fields, audit_index)
        rows_compared = len(finlang_rows)
        alignment_mode = "positional"

    if "date_decision" not in locals():
        date_decision = {"mode": "not_applicable", "dayfirst": False,
                         "ambiguous_values": 0, "evidence": None}

    match_count = rows_compared - len(mismatches)
    duration = time.perf_counter() - t0

    result = ReconcileResult(
        success=(len(mismatches) == 0
                 and not orphans_finlang and not orphans_ml),
        rows_compared=rows_compared,
        matches=match_count,
        mismatches=len(mismatches),
        mismatch_rows=mismatches,
        reconcile_fields=fields,
        alignment_mode=alignment_mode,
        duration_seconds=round(duration, 3),
        finlang_output_file=os.path.basename(finlang_output),
        ml_output_file=os.path.basename(ml_output),
        audit_entries_loaded=audit_count,
        orphans_finlang=tuple(orphans_finlang),
        orphans_ml=tuple(orphans_ml),
        ml_date_convention=date_decision,
    )

    if not headless:
        _print_result(result)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        _write_report_json(result, output_dir)
        if mismatches:
            _write_mismatches_csv(mismatches, fields, output_dir)
        if result.orphans_finlang:
            _write_orphans_csv(
                list(result.orphans_finlang), output_dir,
                "reconcile_orphans_finlang.csv")
        if result.orphans_ml:
            _write_orphans_csv(
                list(result.orphans_ml), output_dir,
                "reconcile_orphans_ml.csv")
        if emit_html:
            # Lazy import keeps reconcile.py decoupled from the HTML module
            # for invocations that don't need it. Same pattern as the CLI's
            # lazy import of reconcile from run_finlang.py.
            from finlang.tools.reconcile_html import generate_html_report
            generate_html_report(
                result, os.path.join(output_dir, "reconcile_report.html")
            )

    return result


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def _print_result(result: ReconcileResult) -> None:
    """Print reconciliation result to console."""
    rows_fmt = f"{result.rows_compared:,}"
    dur_fmt = f"{result.duration_seconds:.1f}s"
    if result.rows_compared > 0:
        match_rate = 100.0 * result.matches / result.rows_compared
    else:
        match_rate = 100.0

    if result.success:
        print(
            f"Reconciliation: {rows_fmt} rows compared, all match "
            f"({result.alignment_mode} alignment, {dur_fmt})"
        )
    else:
        print(
            f"Reconciliation: {result.mismatches} mismatches in {rows_fmt} rows "
            f"(match rate {match_rate:.2f}%)"
        )
        for m in result.mismatch_rows[:10]:
            row = m.get("row_number", "?")
            differing = m.get("differing_fields", "?")
            cp = m.get("counterparty", "")
            print(f"   Row {row}: differs on [{differing}] — {cp}")
        if result.mismatches > 10:
            print(f"   ... and {result.mismatches - 10} more")

    if result.orphans_finlang or result.orphans_ml:
        print(
            f"   Orphans: {len(result.orphans_finlang)} FinLang row(s) "
            f"unmatched in ML output; {len(result.orphans_ml)} ML row(s) "
            f"unmatched in FinLang output"
        )
        for o in list(result.orphans_finlang)[:5]:
            print(
                f"   FinLang row {o.get('row_number', '?')} has no ML match — "
                f"{o.get('counterparty', '')}"
            )
        for o in list(result.orphans_ml)[:5]:
            print(
                f"   ML row {o.get('row_number', '?')} has no FinLang match — "
                f"{o.get('counterparty', '')}"
            )


# ---------------------------------------------------------------------------
# Artifact generation
# ---------------------------------------------------------------------------

def _write_report_json(result: ReconcileResult, output_dir: str) -> None:
    """Write reconcile_report.json."""
    if result.rows_compared > 0:
        match_rate = round(100.0 * result.matches / result.rows_compared, 2)
    else:
        match_rate = 100.0

    report: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "finlang_output_file": result.finlang_output_file,
        "ml_output_file": result.ml_output_file,
        "reconcile_fields": result.reconcile_fields,
        "alignment_mode": result.alignment_mode,
        "total_rows": result.rows_compared,
        "matches": result.matches,
        "mismatches": result.mismatches,
        "match_rate_percent": match_rate,
        "perfect_match": result.success,  # closes 99.998% rounding ambiguity
        "audit_entries_loaded": result.audit_entries_loaded,
        # States how the ML side's date convention was decided, so a reader of
        # this artefact can see whether it was proven by the data ("inferred"),
        # supplied by the operator ("explicit"), or defaulted because every
        # value was ambiguous ("assumed" — a stated assumption, not a fact).
        "ml_date_convention": result.ml_date_convention,
        "orphans_finlang_count": len(result.orphans_finlang),
        "orphans_ml_count": len(result.orphans_ml),
        "duration_seconds": result.duration_seconds,
        "status": "PASS" if result.success else "REVIEW REQUIRED",
    }
    path = os.path.join(output_dir, "reconcile_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


def _write_mismatches_csv(
    mismatches: List[dict],
    reconcile_fields: List[str],
    output_dir: str,
) -> None:
    """Write reconcile_mismatches.csv with one row per disagreement."""
    path = os.path.join(output_dir, "reconcile_mismatches.csv")
    base_columns = [
        "row_number", "date", "amount", "counterparty",
        "differing_fields",
    ]
    field_columns: List[str] = []
    for field in reconcile_fields:
        field_columns.append(f"ml_{field}")
        field_columns.append(f"finlang_{field}")
    audit_columns = ["finlang_rule_matched", "finlang_audit_reason"]
    columns = base_columns + field_columns + audit_columns

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for m in mismatches:
            writer.writerow([m.get(col, "") for col in columns])


def _write_orphans_csv(orphans: List[dict], output_dir: str, filename: str) -> None:
    """Write an orphan-rows CSV (key mode — rows present on one side only).

    `row_number` references the row's position in its OWN file (FinLang
    numbering for reconcile_orphans_finlang.csv, ML numbering for
    reconcile_orphans_ml.csv).
    """
    columns = ["row_number", "date", "amount", "counterparty", "memo", "category"]
    path = os.path.join(output_dir, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for o in orphans:
            writer.writerow([o.get(col, "") for col in columns])
