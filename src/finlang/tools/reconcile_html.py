# reconcile_html.py
# FinLang — HTML report generator for ML reconciliation (v0.7.8, SOL-040 Branch 3)
# Copyright (C) 2026 FinLang Ltd
#
# This file is part of FinLang, licensed under the GNU Affero General Public
# License v3.0 or later. See <https://www.gnu.org/licenses/agpl-3.0.html>.
#
# Commercial licensing: contact@finlang.co.uk

"""
HTML report generator for FinLang reconciliation (SOL-040 Branch 3).

Renders a self-contained HTML view of a `ReconcileResult` — title +
status banner + mismatch table + footer — using f-string substitution
inline. No JS, no external resources. Opens offline. Mirrors the
mockup at `scratch/mockups/reconcile_html_mockup.html` (visual
contract, approved 5 May 2026).

Phase 1 MVP: renders only fields available on `reconcile.py`'s output
dict (no engine extension). Killer-demo asset for compliance-context
use cases where audit-trail readability matters more than raw JSON.

Two non-negotiable disciplines per the five-AI thinktank review:

1. **Performance:** mismatch rows are built as a list of strings then
   `"".join()`-ed before injection into the outer f-string template.
   Naïve `+=` concatenation in a loop is O(N²) and would hang on a
   100K-row real run with thousands of mismatches; this idiom is O(N).

2. **Security:** every user-provided string from the mismatch dict
   (counterparty, memo, ML/FinLang values, rule name, audit reason)
   passes through `html.escape()` before f-string injection. A bank's
   ML output containing `<script>` in a counterparty field renders as
   `&lt;script&gt;`, never as live HTML. CVE-prevention.
"""

import html
import os
from datetime import datetime, timezone
from typing import Dict, List

from finlang import __version__
from finlang.tools.reconcile import ReconcileResult


# ---------------------------------------------------------------------------
# CSS — kept as a module-level constant for clarity. Inlined into the f-string
# template at render time. Self-contained, no external resources.
# ---------------------------------------------------------------------------

_CSS = (
    "body{font:14px/1.5 system-ui,Segoe UI,sans-serif;max-width:960px;"
    "margin:2rem auto;padding:0 1rem;color:#222}"
    "h1{font-size:1.3rem;margin:0}"
    ".meta{color:#789;font-size:.85em}"
    ".banner{border-left:4px solid #d34;background:#fafafa;"
    "padding:.6rem 1rem;margin:1rem 0;border-radius:3px}"
    ".banner.pass{border-color:#2a8}"
    "table{width:100%;border-collapse:collapse;margin-top:.5rem;font-size:.92em}"
    "th{text-align:left;background:#eef;padding:.45rem .55rem;"
    "border-bottom:2px solid #ccd}"
    "td{padding:.5rem .55rem;border-bottom:1px solid #eee;vertical-align:top}"
    "code{font:12px Consolas,monospace;color:#456}"
    "footer{margin-top:1.5rem;font-size:.78em;color:#789;"
    "border-top:1px solid #eee;padding-top:.5rem}"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_timestamp() -> str:
    """Return current UTC time as ISO 8601 (mirrors `_write_report_json`)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_subline(date: str, amount: str, memo: str) -> str:
    """Build the muted subline under counterparty (amount · date · memo).

    All inputs html-escaped. Memo wrapped in quotes when non-empty so
    free-text values are visually distinguished from amounts/dates.
    """
    parts: List[str] = []
    if amount:
        parts.append(html.escape(amount))
    if date:
        parts.append(html.escape(date))
    if memo:
        parts.append(f'"{html.escape(memo)}"')
    return " · ".join(parts)


def _build_row_html(mismatch: Dict[str, str], reconcile_fields: List[str]) -> str:
    """Build a single `<tr>` for one mismatch row.

    Every user-provided string passes through `html.escape()` before
    injection. Multi-field reconcile renders ML/FinLang values
    comma-joined in a single cell; default single-field case is one
    value per cell.
    """
    row_number = html.escape(str(mismatch.get("row_number", "")))
    counterparty = html.escape(mismatch.get("counterparty", ""))
    subline = _format_subline(
        mismatch.get("date", ""),
        mismatch.get("amount", ""),
        mismatch.get("memo", ""),
    )

    ml_values: List[str] = []
    finlang_values: List[str] = []
    for field in reconcile_fields:
        ml_values.append(html.escape(mismatch.get(f"ml_{field}", "")))
        finlang_values.append(html.escape(mismatch.get(f"finlang_{field}", "")))
    ml_cell = ", ".join(ml_values)
    finlang_cell = ", ".join(finlang_values)

    rule_name = html.escape(mismatch.get("finlang_rule_matched", ""))
    audit_reason = html.escape(mismatch.get("finlang_audit_reason", ""))
    if rule_name and audit_reason:
        rule_cell = f"{rule_name}<br><code>{audit_reason}</code>"
    elif rule_name:
        rule_cell = rule_name
    elif audit_reason:
        rule_cell = f"<code>{audit_reason}</code>"
    else:
        rule_cell = ""

    return (
        f"<tr><td>{row_number}</td>"
        f'<td>{counterparty}<br><span class="meta">{subline}</span></td>'
        f"<td>{ml_cell}</td>"
        f"<td>{finlang_cell}</td>"
        f"<td>{rule_cell}</td></tr>"
    )


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

def generate_html_report(result: ReconcileResult, output_path: str) -> None:
    """Write a self-contained HTML reconciliation report to `output_path`.

    Args:
        result: The `ReconcileResult` NamedTuple from `run_reconciliation`.
        output_path: Full filesystem path to write the HTML file to.
            Parent directory must exist (caller's responsibility — the
            CLI hook creates `--reconcile-output-dir` before this call).

    Side effects:
        Writes one UTF-8 HTML file. Does not write any other artifacts.
    """
    finlang_file = html.escape(result.finlang_output_file)
    ml_file = html.escape(result.ml_output_file)
    fields_str = html.escape(", ".join(result.reconcile_fields))
    alignment = html.escape(result.alignment_mode)
    timestamp = _utc_timestamp()

    if result.success:
        banner_class = "banner pass"
        status_text = "PASS"
    else:
        banner_class = "banner"
        status_text = "REVIEW REQUIRED"

    if result.rows_compared > 0:
        match_rate = round(100.0 * result.matches / result.rows_compared, 2)
    else:
        match_rate = 100.0

    if result.mismatches > 0:
        mismatch_summary = (
            f'<span style="color:#d34">{result.mismatches} mismatches</span>'
        )
    else:
        mismatch_summary = "0 mismatches"

    # Sort mismatches by row_number for positional honesty (per visual
    # contract: row 1 before row 4, no severity-driven reordering).
    sorted_rows = sorted(
        result.mismatch_rows,
        key=lambda r: r.get("row_number", 0),
    )

    # Build rows as list-of-strings then join — O(N) construction, not
    # O(N²) via incremental += concatenation. Discipline holds at
    # 100K-row real-world scale; the 15-row demo doesn't expose it.
    row_html_list = [
        _build_row_html(m, result.reconcile_fields) for m in sorted_rows
    ]
    rows_html = "".join(row_html_list)

    perfect_match_str = "true" if result.success else "false"

    html_content = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>FinLang Reconciliation</title><style>{_CSS}</style></head><body>
<h1>FinLang Reconciliation — <span class="meta">{finlang_file} ↔ {ml_file}</span></h1>
<div class="meta">{timestamp} · {alignment} alignment · field: <code>{fields_str}</code> · finlang {__version__} · audit_entries_loaded={result.audit_entries_loaded}</div>
<div class="{banner_class}"><strong>Status: {status_text}</strong> · {result.matches}/{result.rows_compared} match ({match_rate}%) · {mismatch_summary} · perfect_match=<code>{perfect_match_str}</code></div>
<table>
<thead><tr><th>#</th><th>Counterparty</th><th>ML says</th><th>FinLang says</th><th>Rule matched</th></tr></thead>
<tbody>
{rows_html}
</tbody>
</table>
<footer>FinLang {__version__} · run duration {result.duration_seconds}s · generated by <code>finlang --reconcile-html</code></footer>
</body></html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
