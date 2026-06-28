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
        for row in reader:
            rows.append({k: (v or "").strip() for k, v in row.items()})
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

def _identity_normalise(field: str, value: Optional[str]) -> str:
    """Normalise one identity-field value for positional comparison.

    Comparison contract (documented in reconciliation.md):
      - amount: normalised via verify.py's `_normalize_amount_string`
        (synced with the engine's `_to_number` — handles CR/DR suffixes,
        parens, currency symbols, trailing zeros: "-10.00" == "-10.0")
      - date: normalised via verify.py's `_normalize_date_string`
        (ISO 8601; both sides of a reconcile are post-engine CSVs, so
        engine defaults apply — no dayfirst/date_format plumbing here)
      - everything else: whitespace-stripped, case-insensitive

    Reuses verify.py's normalisers rather than forking new copies — one
    source of truth per DOCUMENT_MAP's amount-parsing sync rule.
    """
    from finlang.tools.verify import (
        _normalize_amount_string,
        _normalize_date_string,
    )
    v = (value or "").strip()
    field_lower = field.lower()
    if field_lower == "amount":
        return _normalize_amount_string(v)
    if field_lower == "date":
        return _normalize_date_string(v)
    return v.lower()


def _check_identity(
    finlang_rows: List[Dict[str, str]],
    ml_rows: List[Dict[str, str]],
    identity_fields: List[str],
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
            ml_val = _identity_normalise(field, _resolve_field(ml_row, field))
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
) -> List[dict]:
    """Compare aligned rows field-by-field on the reconcile fields.

    Returns a list of mismatch dicts. Each mismatch contains:
        - row_number: 1-indexed row number (excluding header)
        - date, amount, counterparty: contextual fields if present
        - For each reconcile field: ml_<field>, finlang_<field>
        - finlang_rule_matched: from audit_index if available
        - finlang_audit_reason: from audit_index if available
    """
    mismatches: List[dict] = []
    for i, (fl_row, ml_row) in enumerate(zip(finlang_rows, ml_rows)):
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

    finlang_rows = _read_csv_rows(finlang_output)
    ml_rows = _read_csv_rows(ml_output)

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
        identity_failures = _check_identity(finlang_rows, ml_rows, identity_fields)
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

    mismatches = _compare_rows(finlang_rows, ml_rows, fields, audit_index)

    rows_compared = len(finlang_rows)
    match_count = rows_compared - len(mismatches)
    duration = time.perf_counter() - t0

    result = ReconcileResult(
        success=len(mismatches) == 0,
        rows_compared=rows_compared,
        matches=match_count,
        mismatches=len(mismatches),
        mismatch_rows=mismatches,
        reconcile_fields=fields,
        alignment_mode="positional",
        duration_seconds=round(duration, 3),
        finlang_output_file=os.path.basename(finlang_output),
        ml_output_file=os.path.basename(ml_output),
        audit_entries_loaded=audit_count,
    )

    if not headless:
        _print_result(result)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        _write_report_json(result, output_dir)
        if mismatches:
            _write_mismatches_csv(mismatches, fields, output_dir)
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
