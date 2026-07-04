# verify.py
# FinLang — Post-Engine Integrity Verification (v0.7.7)
# Copyright (C) 2026 FinLang Ltd
#
# This file is part of FinLang, licensed under the GNU Affero General Public
# License v3.0 or later. See <https://www.gnu.org/licenses/agpl-3.0.html>.
#
# Commercial licensing: contact@finlang.co.uk

"""
Post-engine integrity verification for FinLang.

Computes SHA-256 fingerprints on immutable fields (date, amount, counterparty)
and compares input vs output to prove no data corruption occurred.

Two modes:
  - fast: fingerprint comparison only
  - full: fingerprint + field-by-field comparison

Completely decoupled from the engine — reads finished input/output CSVs.
"""

import csv
import hashlib
import json
import os
import re
import time
from datetime import datetime
from typing import NamedTuple, List, Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

class VerifyResult(NamedTuple):
    success: bool
    rows_checked: int
    mismatches: int
    mismatch_rows: List[dict]  # List of {row, reason, ...} dicts
    mode: str
    duration_seconds: float
    input_file: str
    output_file: str


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

# Currency symbols and NBSP regex — mirrors _CURRENCY_NBSP_RE in run_finlang.py
_CURRENCY_NBSP_RE = re.compile("[£€$¥₹\u00A0\u202F]")

# CR/DR detection — mirrors run_finlang.py (v0.7.6 no-\b fix)
_CR_RE = re.compile(r"(?:CR|CRED|CREDIT)\.?\s*$", re.IGNORECASE)
_DR_RE = re.compile(r"(?:DR|DEB|DEBIT)\.?\s*$", re.IGNORECASE)

# CR/DR stripping — mirrors run_finlang.py
_CR_STRIP_RE = re.compile(r"(?i)\s*(?:CR|CRED|CREDIT)\.?\s*$")
_DR_STRIP_RE = re.compile(r"(?i)\s*(?:DR|DEB|DEBIT)\.?\s*$")


def _normalize_amount_string(amount: str, decimal: str = ".", thousands: Optional[str] = None) -> str:
    """Normalize a raw amount string to .2f, mirroring engine _to_number logic.

    Handles: Unicode minus, trailing minus, CR/DR suffixes, accounting parens,
    currency symbol stripping, thousands removal, decimal swap.
    This ensures input fingerprints match output fingerprints even when the
    input contains bank-format amounts like £123.45, 200CR, (50.00), etc.
    """
    s = amount.strip()
    if not s:
        return s

    # Unicode minus → ASCII minus
    s = s.replace("\u2212", "-")

    # Trailing minus: 123.45- → -123.45
    if s.endswith("-"):
        s = "-" + s[:-1]

    # Detect CR/DR before stripping
    s_upper = s.upper()
    is_cr = bool(_CR_RE.search(s_upper))
    is_dr = bool(_DR_RE.search(s_upper))

    # Strip CR/DR tokens
    s = _CR_STRIP_RE.sub("", s)
    s = _DR_STRIP_RE.sub("", s)

    # Accounting parens: (123.45) → -123.45
    s = s.strip()
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1].strip()

    # Thousands removal
    if thousands:
        s = s.replace(thousands, "")

    # Currency symbol and NBSP stripping
    s = _CURRENCY_NBSP_RE.sub("", s)

    # Decimal swap
    if decimal and decimal != ".":
        s = s.replace(decimal, ".")

    # Convert to float, apply CR/DR semantics, format to .2f
    try:
        val = float(s)
        if is_dr:
            val = -abs(val)
        elif is_cr:
            val = abs(val)
        return f"{val:.2f}"
    except (ValueError, TypeError):
        return amount.strip()


# Mirrors run_finlang._csv_safe_text's danger set. That write-time guard
# prefixes ' to any text cell whose lstripped value starts with one of these,
# so engine-written CSVs can legitimately differ from raw source values.
_SAFE_TEXT_DANGER = ("=", "+", "-", "@", "\t")


def _strip_injection_quote(value: str) -> str:
    """Undo the engine's formula-injection quote for comparison purposes.

    Exact inverse of the _csv_safe_text transform: strip one leading '
    when the remainder is danger-leading. Applied symmetrically to both
    sides of every comparison, so it is safe whether or not the guard was
    active when the file was written (FINLANG_SAFE_TEXT).
    """
    if value.startswith("'") and value[1:].lstrip(" ").startswith(_SAFE_TEXT_DANGER):
        return value[1:]
    return value


def _amount_2dp(value: str) -> str:
    """Format an amount to .2f for comparison; non-numeric values pass through.

    Blank or unparseable amounts (possible when the drop-rate guard removed
    a row and alignment shifted) must compare as strings, not crash float().
    """
    try:
        return f"{float(value):.2f}"
    except (ValueError, TypeError):
        return value.strip()


def _normalize_date_string(date: str, dayfirst: bool = False,
                           date_format: Optional[str] = None) -> str:
    """Normalize a date string to ISO 8601 (YYYY-MM-DD), mirroring engine logic.

    The engine uses pd.to_datetime with dayfirst/date_format, then writes
    ISO format via to_csv. We replicate that here so input fingerprints
    match output fingerprints even when input has DD/MM/YYYY or other formats.
    """
    s = date.strip()
    if not s:
        return s
    try:
        if date_format:
            dt = pd.to_datetime(s, format=date_format, errors="coerce")
        else:
            dt = pd.to_datetime(s, errors="coerce", dayfirst=dayfirst)
        if pd.isna(dt):
            return s  # Unparseable — return as-is
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return s


def _normalize_field(field: str, value: str, decimal: str = ".",
                     thousands: Optional[str] = None, dayfirst: bool = False,
                     date_format: Optional[str] = None) -> str:
    """Normalize a field value for comparison, applying type-appropriate logic."""
    if field == "amount":
        return _normalize_amount_string(value, decimal, thousands)
    elif field == "date":
        return _normalize_date_string(value, dayfirst, date_format)
    return value


def _fingerprint(date: str, amount: str, counterparty: str) -> str:
    """SHA-256 fingerprint of immutable fields (first 16 hex chars).

    Expects pre-normalised values (standard locale, ISO date).
    Amount is formatted to .2f to tolerate pandas trailing-zero differences.
    """
    normalized_amount = _amount_2dp(amount)
    composite = f"{date}|{normalized_amount}|{counterparty}"
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()[:16]


def _read_immutable_fields(path: str) -> List[dict]:
    """Read date, amount, counterparty (+ memo, category, flags for context) from a CSV."""
    rows = []
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        # Auto-detect delimiter (handles semicolons, tabs, pipes, etc.)
        sample = f.read(8192)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = "excel"  # Fall back to comma-delimited
        reader = csv.DictReader(f, dialect=dialect)
        fieldnames_lower = {fn.lower(): fn for fn in (reader.fieldnames or [])}

        # Map to canonical lowercase keys
        date_col = fieldnames_lower.get("date", "")
        amount_col = fieldnames_lower.get("amount", "")
        cp_col = fieldnames_lower.get("counterparty", "")
        memo_col = fieldnames_lower.get("memo", "")
        cat_col = fieldnames_lower.get("category", "")
        flags_col = fieldnames_lower.get("flags", "")

        for i, row in enumerate(reader):
            # (x or "") guards against None values from short (ragged) rows —
            # DictReader fills missing fields with restval None.
            rows.append({
                "csv_row": i + 2,  # 1-indexed, header = row 1
                "date": (row.get(date_col) or "").strip(),
                "amount": (row.get(amount_col) or "").strip(),
                # Unquote symmetrically (input AND output pass through this
                # reader) so the engine's injection guard doesn't read as a
                # fingerprint mismatch on legitimate data.
                "counterparty": _strip_injection_quote(
                    (row.get(cp_col) or "").strip()).strip(),
                "memo": (row.get(memo_col) or "").strip(),
                "category": (row.get(cat_col) or "").strip(),
                "flags": (row.get(flags_col) or "").strip(),
            })
    return rows


def run_verification(
    input_path: str,
    output_path: str,
    mode: str = "fast",
    output_dir: Optional[str] = None,
    headless: bool = False,
    decimal: str = ".",
    thousands: Optional[str] = None,
    dayfirst: bool = False,
    date_format: Optional[str] = None,
) -> VerifyResult:
    """Run integrity verification on input vs output CSVs.

    Args:
        input_path: Path to original input CSV.
        output_path: Path to engine output CSV.
        mode: "fast" (fingerprint only) or "full" (fingerprint + field comparison).
        output_dir: If set, write verification artifacts here.
        headless: If True, suppress console output.
        decimal: Decimal separator used by the engine (for amount normalisation).
        thousands: Thousands separator used by the engine (for amount normalisation).
        dayfirst: Parse ambiguous dates as DD/MM (matches engine --dayfirst flag).
        date_format: Explicit strftime format for date parsing (matches engine --date-format).

    Returns:
        VerifyResult namedtuple.
    """
    t0 = time.perf_counter()

    input_rows = _read_immutable_fields(input_path)
    output_rows = _read_immutable_fields(output_path)

    # Pre-normalise input rows: the engine normalises amounts (via _to_number)
    # and dates (via pd.to_datetime) before writing output. We must apply the
    # same transformations to the raw input so fingerprints match.
    # Output rows are already in standard format (decimal '.', ISO dates).
    for row in input_rows:
        row["amount"] = _normalize_amount_string(row["amount"], decimal, thousands)
        row["date"] = _normalize_date_string(row["date"], dayfirst, date_format)

    row_count = min(len(input_rows), len(output_rows))
    mismatches: List[dict] = []

    for i in range(row_count):
        inp = input_rows[i]
        out = output_rows[i]

        fp_in = _fingerprint(inp["date"], inp["amount"], inp["counterparty"])
        fp_out = _fingerprint(out["date"], out["amount"], out["counterparty"])

        inp["_fingerprint"] = fp_in
        out["_fingerprint"] = fp_out

        if fp_in != fp_out:
            mismatch = {
                "csv_row": out["csv_row"],
                "reason": "fingerprint mismatch",
                "fingerprint_in": fp_in,
                "fingerprint_out": fp_out,
            }
            if mode == "full":
                # Add field-level detail (input already pre-normalised, output in standard format)
                field_diffs = []
                for field in ("date", "amount", "counterparty"):
                    # For amount, normalise to .2f for comparison (pandas trailing zeros);
                    # _amount_2dp passes non-numeric values through rather than crashing.
                    v_in = _amount_2dp(inp[field]) if field == "amount" else inp[field]
                    v_out = _amount_2dp(out[field]) if field == "amount" else out[field]
                    if v_in != v_out:
                        field_diffs.append(f"{field}: '{inp[field]}' → '{out[field]}'")
                mismatch["field_diffs"] = "; ".join(field_diffs) if field_diffs else "hash differs (fields appear equal)"
            mismatches.append(mismatch)
        elif mode == "full":
            # Even if fingerprints match, verify fields individually
            for field in ("date", "amount", "counterparty"):
                v_in = _amount_2dp(inp[field]) if field == "amount" else inp[field]
                v_out = _amount_2dp(out[field]) if field == "amount" else out[field]
                if v_in != v_out:
                    mismatches.append({
                        "csv_row": out["csv_row"],
                        "reason": f"field mismatch ({field})",
                        "fingerprint_in": fp_in,
                        "fingerprint_out": fp_out,
                        "field_diffs": f"{field}: '{inp[field]}' → '{out[field]}'",
                    })
                    break  # One mismatch per row is enough

    # Row count mismatch
    if len(input_rows) != len(output_rows):
        mismatches.append({
            "csv_row": 0,
            "reason": f"row count mismatch: input={len(input_rows)}, output={len(output_rows)}",
            "fingerprint_in": "",
            "fingerprint_out": "",
        })

    duration = time.perf_counter() - t0
    success = len(mismatches) == 0

    result = VerifyResult(
        success=success,
        rows_checked=row_count,
        mismatches=len(mismatches),
        mismatch_rows=mismatches,
        mode=mode,
        duration_seconds=round(duration, 3),
        input_file=os.path.basename(input_path),
        output_file=os.path.basename(output_path),
    )

    # Console output
    if not headless:
        _print_result(result)

    # Artifacts
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        _write_report_json(result, output_dir)
        _write_proof_csv(input_rows, output_rows, row_count, output_dir)
        if mismatches:
            _write_mismatches_csv(mismatches, output_dir)

    return result


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def _print_result(result: VerifyResult) -> None:
    """Print verification result to console."""
    mode_label = "fast" if result.mode == "fast" else "full"
    rows_fmt = f"{result.rows_checked:,}"
    dur_fmt = f"{result.duration_seconds:.1f}s"

    if result.success:
        print(f"Integrity verified: {rows_fmt} rows, 0 mismatches ({mode_label} mode, {dur_fmt})")
    else:
        print(f"Integrity failure: {result.mismatches} mismatches detected in {rows_fmt} rows")
        # Show up to 10 mismatch details
        for m in result.mismatch_rows[:10]:
            row = m.get("csv_row", "?")
            reason = m.get("reason", "unknown")
            print(f"   Row {row}: {reason}")
        if result.mismatches > 10:
            print(f"   ... and {result.mismatches - 10} more")


# ---------------------------------------------------------------------------
# Artifact generation
# ---------------------------------------------------------------------------

def _write_report_json(result: VerifyResult, output_dir: str) -> None:
    """Write verify_report.json."""
    from datetime import datetime, timezone
    report = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input_file": result.input_file,
        "output_file": result.output_file,
        "mode": result.mode,
        "rows_checked": result.rows_checked,
        "mismatches": result.mismatches,
        "duration_seconds": result.duration_seconds,
        "status": "PASS" if result.success else "FAIL",
    }
    path = os.path.join(output_dir, "verify_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


def _write_proof_csv(input_rows, output_rows, row_count, output_dir: str) -> None:
    """Write verify_proof.csv with per-row fingerprint comparison."""
    path = os.path.join(output_dir, "verify_proof.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "date", "amount", "counterparty", "memo", "category", "flags",
            "_fingerprint_in", "_fingerprint_out", "_status",
        ])
        for i in range(row_count):
            out = output_rows[i]
            inp = input_rows[i]
            fp_in = inp.get("_fingerprint", "")
            fp_out = out.get("_fingerprint", "")
            status = "PASS" if fp_in == fp_out else "FAIL"
            writer.writerow([
                out["date"], out["amount"], out["counterparty"],
                out["memo"], out["category"], out["flags"],
                fp_in, fp_out, status,
            ])


def _write_mismatches_csv(mismatches: List[dict], output_dir: str) -> None:
    """Write verify_mismatches.csv with failure details."""
    path = os.path.join(output_dir, "verify_mismatches.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["csv_row", "reason", "fingerprint_in", "fingerprint_out", "field_diffs"])
        for m in mismatches:
            writer.writerow([
                m.get("csv_row", ""),
                m.get("reason", ""),
                m.get("fingerprint_in", ""),
                m.get("fingerprint_out", ""),
                m.get("field_diffs", ""),
            ])
