# impact_html.py
# FinLang — HTML report generator for rule-change impact analysis (SOL-105 Branch 3)
# Copyright (C) 2026 FinLang Ltd
#
# This file is part of FinLang, licensed under the GNU Affero General Public
# License v3.0 or later. See <https://www.gnu.org/licenses/agpl-3.0.html>.
#
# Commercial licensing: contact@finlang.co.uk

"""
HTML report generator for FinLang impact analysis (SOL-105 Branch 3).

Renders a self-contained HTML view of an ``ImpactResult`` — title + status
banner + headline cards + transition matrix + per-rule deltas +
attribution-only section + capped row-level table + footer. No JS, no
external resources, opens offline, prints to PDF. Mirrors the approved
mockup at ``scratch/mockups/impact_html_mockup.html``.

Two non-negotiable disciplines, carried verbatim from ``reconcile_html.py``:

1. **Performance:** table rows are built as a list of strings then
   ``"".join()``-ed — O(N), never ``+=`` in a loop.
2. **Security:** every user-provided string (counterparty, category, rule
   name, flags, memo, amounts) passes through ``html.escape()`` before
   injection. A rulepack that produces ``<script>`` in a category renders
   as inert text, never live HTML.

Banner is **AMBER** ("REVIEW REQUIRED") when behavioural changes exist,
**GREEN** ("NO BEHAVIOURAL CHANGE") otherwise — deliberately distinct from
reconcile's red/green pass/fail, because a rule change producing changes is
*expected*, not an error.

Row-level table caps at the first 50 rows (``_ROW_CAP``) — a visual-contract
decision (28 June 2026, down from the spec's 1,000: 1,000 is a wall to scroll
in a change-approval meeting). The full row-by-row set is always in
``impact_changes.csv``; the HTML stays an executive view.
"""

import html
from collections import OrderedDict
from datetime import datetime, timezone

from finlang import __version__
from finlang.tools.impact import ImpactResult, FLOAT_DISCLAIMER


# Row-level table cap — visual contract; full set always in impact_changes.csv.
_ROW_CAP = 50

_CSS = """
body{font:14px/1.5 system-ui,Segoe UI,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#222}
h1{font-size:1.3rem;margin:0}
h2{font-size:1.05rem;margin:1.4rem 0 .2rem}
.meta{color:#789;font-size:.85em}
.banner{border-left:4px solid #d90;background:#fdf6e3;padding:.6rem 1rem;margin:1rem 0;border-radius:3px}
.banner.pass{border-color:#2a8;background:#fafafa}
.cards{display:flex;gap:.6rem;flex-wrap:wrap;margin:.8rem 0}
.card{flex:1 1 150px;border:1px solid #e3e3e0;border-radius:6px;padding:.55rem .7rem;background:#fbfbfa}
.card .num{font-size:1.25rem;font-weight:700}
.card .lbl{color:#789;font-size:.78em}
table{width:100%;border-collapse:collapse;margin-top:.5rem;font-size:.92em}
th{text-align:left;background:#eef;padding:.45rem .55rem;border-bottom:2px solid #ccd}
td{padding:.5rem .55rem;border-bottom:1px solid #eee;vertical-align:top}
code{font:12px Consolas,monospace;color:#456}
.note{color:#789;font-size:.85em;margin:.2rem 0 0}
.attr{background:#f4f7fb;border-left:4px solid #79b;padding:.5rem 1rem;margin:1rem 0;border-radius:3px}
footer{margin-top:1.5rem;font-size:.78em;color:#789;border-top:1px solid #eee;padding-top:.5rem}
""".strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _esc(value) -> str:
    """html.escape() any value, coercing to str first."""
    return html.escape(str(value))


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _short_hash(h: str) -> str:
    """Truncated hash for display (full value goes in the title attribute)."""
    return f"{h[:6]}…{h[-4:]}" if h else "—"


def _transition_rows(transitions) -> str:
    parts = []
    for t in transitions:
        parts.append(
            f"<tr><td>{_esc(t.get('old_category', ''))}</td>"
            f"<td>{_esc(t.get('new_category', ''))}</td>"
            f"<td>{int(t.get('rows', 0))}</td>"
            f"<td>{float(t.get('indicative_amount', 0.0)):,.2f}</td></tr>"
        )
    return "".join(parts)


def _rule_delta_rows(rule_deltas) -> str:
    parts = []
    for r in rule_deltas:
        presence = r.get("presence", "present")
        ma = "—" if presence == "new" else str(int(r.get("matches_baseline", 0)))
        mb = "—" if presence == "removed" else str(int(r.get("matches_candidate", 0)))
        delta = int(r.get("delta", 0))
        delta_disp = f"+{delta}" if delta > 0 else str(delta)
        parts.append(
            f"<tr><td>{_esc(r.get('rule', ''))}</td><td>{ma}</td>"
            f"<td>{mb}</td><td>{delta_disp}</td><td>{_esc(presence)}</td></tr>"
        )
    return "".join(parts)


def _attribution_section(changed_rows, attribution_changed: int) -> str:
    """Aggregate attribution-only rows by (old_rule -> new_rule). Empty when
    there are none (section omitted entirely)."""
    if attribution_changed <= 0:
        return ""
    agg = OrderedDict()
    for row in changed_rows:
        if row.get("change_class") != "attribution":
            continue
        key = (row.get("old_rule", ""), row.get("new_rule", ""))
        agg[key] = agg.get(key, 0) + 1
    body = "".join(
        f"<tr><td>{_esc(old)}</td><td>{_esc(new)}</td><td>{n}</td></tr>"
        for (old, new), n in agg.items()
    )
    return (
        f"<h2>Attribution-only changes ({attribution_changed})</h2>"
        f'<div class="attr">Same outcome, different rule produced it — renames, '
        f"reorders, shadowing rules. Reported for completeness; these do "
        f"<strong>not</strong> set exit code 3 and are not counted in the "
        f"behavioural numbers above.</div>"
        f"<table><thead><tr><th>Was attributed to</th><th>Now attributed to</th>"
        f"<th>Rows</th></tr></thead><tbody>{body}</tbody></table>"
    )


def _subline(amount, date) -> str:
    parts = []
    if amount:
        parts.append(_esc(amount))
    if date:
        parts.append(_esc(date))
    return " · ".join(parts)


def _row_level_rows(changed_rows) -> str:
    """Build the capped row-level table body (first _ROW_CAP rows)."""
    parts = []
    for row in changed_rows[:_ROW_CAP]:
        old_cat = _esc(row.get("old_category", "") or "(uncategorised)")
        new_cat = _esc(row.get("new_category", "") or "(uncategorised)")
        old_rule = _esc(row.get("old_rule", "") or "—")
        new_rule = _esc(row.get("new_rule", "") or "—")
        parts.append(
            f"<tr><td>{_esc(row.get('row_number', ''))}</td>"
            f'<td>{_esc(row.get("counterparty", ""))}<br>'
            f'<span class="meta">{_subline(row.get("amount", ""), row.get("date", ""))}</span></td>'
            f"<td>{old_cat} → {new_cat}</td>"
            f"<td>{old_rule} → {new_rule}</td>"
            f"<td>{_esc(row.get('change_class', ''))}</td></tr>"
        )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

def generate_html_report(result: ImpactResult, output_path: str) -> None:
    """Write a self-contained HTML impact report to ``output_path``.

    Args:
        result: The ``ImpactResult`` from ``run_impact``.
        output_path: Full filesystem path to write the HTML file to. Parent
            directory must exist (the CLI hook creates ``--impact-output-dir``
            before this call).

    Side effects:
        Writes one UTF-8 HTML file. No other artifacts.
    """
    timestamp = _utc_timestamp()
    baseline_file = _esc(result.baseline_rules_file)
    candidate_file = _esc(result.candidate_rules_file)
    input_file = _esc(result.input_file)

    behavioural = result.behavioural_changed
    if behavioural > 0:
        banner_class = "banner"
        banner_text = f"REVIEW REQUIRED — {behavioural} rows change behaviour"
    else:
        banner_class = "banner pass"
        banner_text = "NO BEHAVIOURAL CHANGE"

    pct_stable = (100.0 * result.rows_stable / result.rows_compared
                  if result.rows_compared else 100.0)
    indicative_total = sum(
        float(t.get("indicative_amount", 0.0)) for t in result.transitions
    )
    rules_added = sum(1 for r in result.rule_deltas if r.get("presence") == "new")
    rules_removed = sum(1 for r in result.rule_deltas if r.get("presence") == "removed")

    transition_html = (_transition_rows(result.transitions)
                       or '<tr><td colspan="4" class="meta">No category transitions.</td></tr>')
    rule_delta_html = (_rule_delta_rows(result.rule_deltas)
                       or '<tr><td colspan="5" class="meta">No rule deltas.</td></tr>')
    attribution_html = _attribution_section(result.changed_rows, result.attribution_changed)

    total_changed = result.behavioural_changed + result.attribution_changed
    if result.changed_rows:
        shown = min(total_changed, _ROW_CAP)
        cap_note = (f"Showing the first <strong>{shown}</strong> of {total_changed} "
                    f"changed rows (by row number) — the complete row-by-row set is "
                    f"always in <code>impact_changes.csv</code> (sortable/filterable).")
        row_level_table = (
            f'<h2>Row-level changes</h2><p class="note">{cap_note}</p>'
            f"<table><thead><tr><th>#</th><th>Counterparty</th>"
            f"<th>Category (old → new)</th><th>Rule (old → new)</th>"
            f"<th>Class</th></tr></thead><tbody>"
            f"{_row_level_rows(result.changed_rows)}</tbody></table>"
        )
    else:
        row_level_table = ""

    html_content = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>FinLang Impact Analysis</title><style>{_CSS}</style></head><body>
<h1>FinLang Impact Analysis — <span class="meta">{baseline_file} → {candidate_file}</span></h1>
<div class="meta">{timestamp} · input {input_file} ({result.rows_compared:,} rows) · finlang {__version__} · baseline sha256 <code title="{_esc(result.baseline_rules_sha256)}">{_short_hash(result.baseline_rules_sha256)}</code> · candidate sha256 <code title="{_esc(result.candidate_rules_sha256)}">{_short_hash(result.candidate_rules_sha256)}</code><br>{_esc(FLOAT_DISCLAIMER)}</div>
<div class="{banner_class}"><strong>{banner_text}</strong> · {result.attribution_changed} attribution-only · {result.rows_stable} stable ({pct_stable:.2f}%)</div>
<div class="cards">
<div class="card"><div class="num">{behavioural}</div><div class="lbl">rows changed</div></div>
<div class="card"><div class="num">{pct_stable:.2f}%</div><div class="lbl">stable</div></div>
<div class="card"><div class="num">{indicative_total:,.2f}</div><div class="lbl">indicative amount moved</div></div>
<div class="card"><div class="num">{rules_added}</div><div class="lbl">rules added</div></div>
<div class="card"><div class="num">{rules_removed}</div><div class="lbl">rules removed</div></div>
</div>
<h2>Category transitions</h2>
<table><thead><tr><th>From</th><th>To</th><th>Rows</th><th>Indicative amount</th></tr></thead><tbody>
{transition_html}
</tbody></table>
<h2>Per-rule match deltas</h2>
<table><thead><tr><th>Rule</th><th>Baseline</th><th>Candidate</th><th>Δ</th><th>Presence</th></tr></thead><tbody>
{rule_delta_html}
</tbody></table>
{attribution_html}
{row_level_table}
<footer>FinLang {__version__} · run duration {result.duration_seconds}s · generated by <code>finlang --impact-html</code></footer>
</body></html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
