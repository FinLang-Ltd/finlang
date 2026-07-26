# verify_html.py
# FinLang — Integrity Verification HTML Report (SOL-111)
# Copyright (C) 2026 FinLang Ltd
#
# This file is part of FinLang, licensed under the GNU Affero General Public
# License v3.0 or later. See <https://www.gnu.org/licenses/agpl-3.0.html>.
#
# Commercial licensing: contact@finlang.co.uk

"""Self-contained HTML report for `--verify` / `--verify-full` (SOL-111).

Design note (SOL-111 §2) — this report differs in kind from the reconcile and
impact reports. Those exist to show FINDINGS: disagreements, changed rows,
orphans. Verification's healthy outcome has none — "58 rows, 0 mismatches".

So the report's job is not to show findings. It is to make the ABSENCE of
findings legible as evidence. A reviewer should close it able to say what was
checked, what was deliberately not checked, by what method, over what data,
with which settings — and to see actual fingerprint pairs rather than a claim
that they matched.

Structure mirrors reconcile_html.py: one entry point, inline CSS, no
JavaScript, no external references, html.escape() on every value that came
from user data.
"""

import html
from datetime import datetime, timezone
try:
    from finlang import __version__
except ImportError:  # pragma: no cover - standalone execution
    __version__ = "0.0.0"

from finlang.tools.verify import (
    VerifyResult,
    IMMUTABLE_FIELDS,
    CATEGORISATION_FIELDS,
)


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------

def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _short_hash(value: str) -> str:
    """Abbreviate a SHA-256 for reading. Full values live in verify_proof.csv.

    A 64-character hash is unreadable in a table and encourages nobody to
    check it. First 8 and last 6 is enough to see that two differ.
    """
    v = (value or "").strip()
    if len(v) <= 18:
        return html.escape(v)
    return html.escape(f"{v[:8]}…{v[-6:]}")


def _describe_dates(params: dict) -> str:
    """One plain-English sentence about how dates were read."""
    date_format = params.get("date_format")
    if date_format:
        return (
            f"Dates were read using the explicit format "
            f"<code>{html.escape(str(date_format))}</code> "
            f"(<code>--date-format</code> supplied)."
        )
    if params.get("dayfirst"):
        return (
            "Ambiguous dates were read <strong>day-first</strong> (DD/MM/YYYY) "
            "because <code>--dayfirst</code> was supplied; unambiguous formats "
            "such as ISO are unaffected."
        )
    return (
        "Ambiguous dates were read <strong>month-first</strong> (MM/DD/YYYY), "
        "the default — no date override was supplied. Unambiguous formats "
        "such as ISO are unaffected."
    )


def _describe_numbers(params: dict) -> str:
    """One plain-English sentence about how amounts were read."""
    decimal = params.get("decimal") or "."
    thousands = params.get("thousands")
    bits = [
        f"Amounts used <code>{html.escape(decimal)}</code> as the decimal separator"
    ]
    if thousands:
        bits.append(
            f"and <code>{html.escape(thousands)}</code> as the thousands separator"
        )
    return " ".join(bits) + "."


def _describe_overrides(params: dict) -> str:
    """Name every override explicitly, or say plainly that there were none.

    Silence is not the same as "defaults applied" — a reviewer needs to see
    the difference stated, not infer it.
    """
    supplied = []
    if params.get("dayfirst"):
        supplied.append("<code>--dayfirst</code>")
    if params.get("date_format"):
        supplied.append("<code>--date-format</code>")
    if (params.get("decimal") or ".") != ".":
        supplied.append("<code>--decimal</code>")
    if params.get("thousands"):
        supplied.append("<code>--thousands</code>")
    if not supplied:
        return "<strong>No locale overrides were supplied</strong> — FinLang's defaults were used throughout."
    return "Locale overrides supplied: " + ", ".join(supplied) + "."


def _split_structural(result: VerifyResult):
    """Separate structural failures from row-level mismatches.

    A row-count mismatch is not a row that failed comparison — it means the
    two files do not even contain the same rows, which is a different (and
    worse) statement. Verify records it as a mismatch entry with csv_row 0;
    counting it as a failed row makes the arithmetic lie: with one matching
    shared row plus one extra output row, "1 of 1 rows did not match" blames
    a row that PASSED, and with zero shared rows the banner goes negative.
    (Caught in Codex review, 26 Jul 2026.)
    """
    structural = []
    row_level = []
    for m in result.mismatch_rows:
        reason = str(m.get("reason", ""))
        if reason.startswith("row count mismatch"):
            structural.append(reason)
        else:
            row_level.append(m)
    return structural, row_level


def _plain_english(result: VerifyResult) -> str:
    """The section that opens the report: what actually ran, in sentences.

    Renders with the same structure whether the run passed or failed — only
    the facts change. A reviewer must never have to infer something from
    what is missing.
    """
    params = result.run_params or {}
    rows = f"{result.rows_checked:,}"
    mode_text = (
        "each immutable field was also compared individually, not just the fingerprint"
        if result.mode == "full"
        else "row fingerprints were compared"
    )

    structural, row_level = _split_structural(result)
    if result.success:
        verdict = (
            f"<strong>All {rows} rows matched.</strong> No immutable field was "
            f"altered, no row was lost, and no data moved between rows."
        )
    elif structural:
        # Structural failure: the files do not contain the same rows. Say
        # that, and report the shared rows' comparison separately and
        # accurately — a matching shared row must not be blamed.
        parts = [
            f"<strong>Structural failure: {html.escape(structural[0])}.</strong> "
            f"The output does not contain the same number of rows as the input — "
            f"a row was lost or added before any field comparison."
        ]
        if row_level:
            parts.append(
                f" Of the {rows} shared rows compared, "
                f"<strong>{len(row_level):,} also did not match</strong> — "
                f"detail in the table below."
            )
        elif result.rows_checked > 0:
            parts.append(
                f" The {rows} shared rows that could be compared all matched."
            )
        verdict = "".join(parts)
    else:
        verdict = (
            f"<strong>{len(row_level):,} of {rows} rows did not match.</strong> "
            f"Their immutable fields differ between input and output — the "
            f"detail is in the table below."
        )

    immutable = ", ".join(f"<strong>{f}</strong>" for f in IMMUTABLE_FIELDS)

    return f"""<section class="plain">
<h2>What happened</h2>
<p>FinLang read <strong>{rows} rows</strong> from
   <code>{html.escape(result.input_file)}</code> and wrote
   <code>{html.escape(result.output_file)}</code>.</p>
<p>{_describe_dates(params)} {_describe_numbers(params)}</p>
<p>{_describe_overrides(params)}</p>
<p>The {immutable} of every row were fingerprinted with SHA-256 before
   processing and again afterwards, then compared — in <code>{html.escape(result.mode)}</code>
   mode, so {mode_text}.</p>
<p class="verdict">{verdict}</p>
</section>"""


def _scope_section() -> str:
    """What was checked and — just as important — what was not."""
    checked = " · ".join(f"<code>{f}</code>" for f in IMMUTABLE_FIELDS)
    not_checked = " · ".join(f"<code>{f}</code>" for f in CATEGORISATION_FIELDS)
    return f"""<section>
<h2>Scope of this check</h2>
<table class="scope">
<tr><th>Compared</th><td>{checked}</td>
    <td class="meta">Immutable — the engine must never change these.</td></tr>
<tr><th>Not compared</th><td>{not_checked}</td>
    <td class="meta">Categorisation output — the engine is meant to change these,
        so they differ by design.</td></tr>
</table>
<p class="meta">Verification shows whether the categorisation layer altered the
underlying data. It does not check whether a rule produced the right category —
that is what <code>--reconcile</code> is for.</p>
</section>"""


def _proof_section(result: VerifyResult) -> str:
    """Actual fingerprint pairs. This is what makes a PASS page worth opening."""
    if not result.proof_sample:
        return ""
    rows_html = []
    for row in result.proof_sample:
        status = row.get("status", "")
        cls = "pass" if status == "PASS" else "fail"
        sub = f"{html.escape(str(row.get('date','')))} · {html.escape(str(row.get('amount','')))}"
        rows_html.append(
            "<tr>"
            f"<td class=\"num\">{row.get('row','')}</td>"
            f"<td>{html.escape(str(row.get('counterparty','')))}"
            f"<br><span class=\"meta\">{sub}</span></td>"
            f"<td class=\"hash\">{_short_hash(row.get('fingerprint_in',''))}</td>"
            f"<td class=\"hash\">{_short_hash(row.get('fingerprint_out',''))}</td>"
            f"<td class=\"{cls}\">{html.escape(status)}</td>"
            "</tr>"
        )
    shown = len(result.proof_sample)
    total = result.rows_checked
    caption = (
        f"first {shown} of {total:,}" if shown < total else f"all {total:,}"
    )
    return f"""<section>
<h2>Fingerprint proof <span class="meta">({caption})</span></h2>
<table>
<tr><th>#</th><th>Counterparty</th><th>Fingerprint in</th>
    <th>Fingerprint out</th><th></th></tr>
{''.join(rows_html)}
</table>
<p class="meta">Hashes abbreviated for reading. Every row's full pair is in
<code>verify_proof.csv</code>.</p>
</section>"""


def _mismatch_section(result: VerifyResult) -> str:
    """Rendered only when there are mismatches — never as an empty table.

    An empty table reads as "nothing ran"; omission plus a PASS banner reads
    as "nothing was wrong", which is the truth.
    """
    if not result.mismatch_rows:
        return ""
    rows_html = []
    for m in result.mismatch_rows:
        diffs = m.get("field_diffs", "") or ""
        rows_html.append(
            "<tr>"
            f"<td class=\"num\">{html.escape(str(m.get('csv_row', '')))}</td>"
            f"<td>{html.escape(str(m.get('reason', '')))}</td>"
            f"<td class=\"diff\">{html.escape(str(diffs))}</td>"
            f"<td class=\"hash\">{_short_hash(m.get('fingerprint_in', ''))}</td>"
            f"<td class=\"hash\">{_short_hash(m.get('fingerprint_out', ''))}</td>"
            "</tr>"
        )
    return f"""<section>
<h2>Mismatches ({len(result.mismatch_rows)})</h2>
<table>
<tr><th>Row</th><th>Reason</th><th>Field difference</th>
    <th>Fingerprint in</th><th>Fingerprint out</th></tr>
{''.join(rows_html)}
</table>
<p class="meta">Full set in <code>verify_mismatches.csv</code>.</p>
</section>"""


_CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
       margin: 0; padding: 2.5rem 2rem; color: #1f2733; background: #fff;
       line-height: 1.5; }
.wrap { max-width: 1100px; margin: 0 auto; }
h1 { font-size: 1.55rem; margin: 0 0 .35rem; font-weight: 700; }
h1 .meta { font-weight: 400; color: #6b7a90; }
h2 { font-size: 1.05rem; margin: 2rem 0 .6rem; font-weight: 700; }
.meta { color: #6b7a90; font-size: .875rem; }
code { font-family: ui-monospace, Consolas, monospace; font-size: .9em;
       background: #f1f4f9; padding: .1em .35em; border-radius: 3px; }
.banner { padding: .8rem 1rem; border-radius: 6px; margin: 1.2rem 0;
          border-left: 4px solid #d34; background: #fdf3f4; }
.banner.pass { border-left-color: #12a377; background: #f0faf6; }
section.plain { background: #f8fafc; border: 1px solid #e3e9f2;
                border-radius: 8px; padding: .4rem 1.25rem 1rem; }
section.plain h2 { margin-top: 1rem; }
section.plain p { margin: .55rem 0; max-width: 70ch; }
p.verdict { margin-top: .9rem; padding-top: .8rem;
            border-top: 1px solid #e3e9f2; }
table { border-collapse: collapse; width: 100%; margin: .5rem 0; font-size: .9rem; }
th { text-align: left; background: #f1f4f9; padding: .5rem .65rem;
     border-bottom: 1px solid #dde4ee; font-weight: 600; }
td { padding: .5rem .65rem; border-bottom: 1px solid #eef1f6;
     vertical-align: top; }
td.num { color: #8a96a8; width: 3rem; }
td.hash, .hash { font-family: ui-monospace, Consolas, monospace;
                 font-size: .84rem; color: #47546b; }
td.hash { color: #47546b; }
td.diff { font-family: ui-monospace, Consolas, monospace; font-size: .84rem; }
td.pass { color: #12a377; font-weight: 600; }
td.fail { color: #d34; font-weight: 600; }
table.scope th { width: 9rem; background: transparent; border-bottom: none;
                 vertical-align: top; }
table.scope td { border-bottom: none; }
footer { margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid #eef1f6;
         color: #8a96a8; font-size: .82rem; }
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def generate_html_report(result: VerifyResult, output_path: str) -> None:
    """Write a self-contained HTML verification report to `output_path`.

    Args:
        result: The `VerifyResult` from `run_verification`.
        output_path: Full filesystem path for the HTML file. The parent
            directory must already exist (the CLI hook creates
            `--verify-output-dir` before calling).

    Side effects:
        Writes one UTF-8 HTML file. No other artefacts, no network access,
        no external asset references.
    """
    timestamp = _utc_timestamp()
    banner_class = "banner pass" if result.success else "banner"
    status_text = "PASS" if result.success else "REVIEW REQUIRED"

    structural, row_level = _split_structural(result)
    if result.success:
        summary = f"{result.rows_checked:,}/{result.rows_checked:,} rows verified · 0 mismatches"
    else:
        verified = max(0, result.rows_checked - len(row_level))
        bits = [f"{verified:,}/{result.rows_checked:,} shared rows verified"]
        if row_level:
            bits.append(f'<span style="color:#d34">{len(row_level):,} mismatches</span>')
        if structural:
            bits.append(f'<span style="color:#d34">{html.escape(structural[0])}</span>')
        summary = " · ".join(bits)

    doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FinLang Integrity Verification — {html.escape(result.output_file)}</title>
<style>{_CSS}</style></head>
<body><div class="wrap">
<h1>FinLang Integrity Verification —
    <span class="meta">{html.escape(result.input_file)} &rarr; {html.escape(result.output_file)}</span></h1>
<div class="meta">{timestamp} · mode <code>{html.escape(result.mode)}</code> ·
    finlang {html.escape(__version__)} · run duration {result.duration_seconds}s</div>
<div class="{banner_class}"><strong>Status: {status_text}</strong> · {summary}</div>
{_plain_english(result)}
{_scope_section()}
{_mismatch_section(result)}
{_proof_section(result)}
<footer>finlang {html.escape(__version__)} · generated by
    <code>--verify-html</code> · full artefacts alongside this file:
    <code>verify_report.json</code>, <code>verify_proof.csv</code>{
        ", <code>verify_mismatches.csv</code>" if result.mismatch_rows else ""}
</footer>
</div></body></html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(doc)
