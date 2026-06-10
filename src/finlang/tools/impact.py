# impact.py
# FinLang — Rule-Change Impact Analysis (SOL-105 Branch 1)
# Copyright (C) 2026 FinLang Ltd
#
# This file is part of FinLang, licensed under the GNU Affero General Public
# License v3.0 or later. See <https://www.gnu.org/licenses/agpl-3.0.html>.
#
# Commercial licensing: contact@finlang.co.uk

"""
Rule-change impact analysis for FinLang (SOL-105).

Runs the same normalised input frame through two rulepacks — baseline
(`--rules`) and candidate (`--impact-rules`) — and reports exactly what
the change does: which rows re-categorise, the indicative amount moved
between categories, which rules gain or lose matches, and row-level
before/after attribution.

Architecture: one frame, two passes, in-process. Both passes share the
same loaded/mapped/normalised frame, so row identity and order are
identical by construction — none of reconcile's alignment machinery is
needed, and determinism is inherited from the engine. Pass isolation is
guaranteed by `run_audit`'s internal `df.copy()` (engine purity verified
against source at build time; regression-tested via the leak-detector
test in test_impact.py).

Diff semantics:
  - Behavioural change  = any difference in (category, flags, status).
    Flags compare by SET equality (space-separated tokens; the engine
    de-duplicates tokens and attaches no semantics to order).
    Behavioural changes drive exit code 3 — review required.
  - Attribution-only    = same outcome, different rule produced it
    (rename, reorder, shadow). Reported prominently, never gating —
    harmless renames must not make CI noisy.

Amount discipline: indicative sums use the engine-normalised amount
column. Float sums are reproducible (same input → same sum, every run)
but are not accounting-grade decimal arithmetic — the disclaimer ships
in the CLI summary itself, not only in docs.

No printing in this module's analysis path — `run_impact` returns data;
the CLI layer prints `format_summary`'s lines.
"""

import time
from collections import Counter
from typing import NamedTuple, List, Dict, Any, Optional

import pandas as pd

from finlang.engine.finlang_engine import run_audit


_ENGINE_COLS = ["counterparty", "amount", "date", "memo",
                "category", "flags", "status", "exclude"]
_UNCATEGORISED = "(uncategorised)"
FLOAT_DISCLAIMER = ("Indicative totals — float arithmetic, "
                    "not accounting-grade.")


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

class ImpactResult(NamedTuple):
    rows_compared: int
    behavioural_changed: int
    attribution_changed: int
    rows_stable: int
    # Aggregates — tuples of plain dicts (immutable defaults; JSON-ready).
    transitions: tuple        # {old_category, new_category, rows, indicative_amount}
    rule_deltas: tuple        # {rule, matches_baseline, matches_candidate, delta, presence}
    flag_deltas: tuple        # {flag, rows_gained, rows_lost}
    status_deltas: tuple      # {status, rows_baseline, rows_candidate, delta}
    changed_rows: tuple       # row-level dicts, sorted by row_number (artefact source)
    input_file: str
    baseline_rules_file: str
    candidate_rules_file: str
    duration_seconds: float


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _tokens(s: str) -> frozenset:
    """Flag string → set of tokens (engine semantics: order carries none)."""
    return frozenset(str(s).split())


def _result_col(df: pd.DataFrame, name: str, n: int) -> pd.Series:
    """Engine-managed column as a clean positional string Series."""
    if name in df.columns:
        return df[name].fillna("").astype(str).reset_index(drop=True)
    return pd.Series([""] * n, dtype=object)


def _last_rule_by_row(audit_log: List[Dict[str, Any]], n: int) -> pd.Series:
    """Per-row attribution: the LAST rule that fired on each row.

    Mirrors reconcile's audit-index semantics (later entries overwrite).
    Rows no rule touched attribute as "".
    """
    rule_by_idx: Dict[int, str] = {}
    for entry in audit_log:
        if isinstance(entry, dict) and isinstance(entry.get("index"), int):
            rule = entry.get("rule", "")
            rule_by_idx[entry["index"]] = rule if isinstance(rule, str) else ""
    if not rule_by_idx:
        return pd.Series([""] * n, dtype=object)
    return (pd.Series(rule_by_idx, dtype=object)
            .reindex(range(n), fill_value=""))


def _rule_match_counts(audit_log: List[Dict[str, Any]]) -> Counter:
    """Rule name → number of rows it fired on (full-mode audit entries)."""
    return Counter(
        entry.get("rule", "")
        for entry in audit_log
        if isinstance(entry, dict) and isinstance(entry.get("index"), int)
    )


def _rule_names(rules: List[Dict[str, Any]]) -> List[str]:
    return [r.get("name", f"<unnamed_{i}>") for i, r in enumerate(rules)]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_impact(
    df: pd.DataFrame,
    baseline_rules: List[Dict[str, Any]],
    candidate_rules: List[Dict[str, Any]],
    input_file: str = "",
    baseline_rules_file: str = "",
    candidate_rules_file: str = "",
) -> ImpactResult:
    """Run impact analysis: one frame, two passes, vectorised diff.

    Args:
        df: The loaded/mapped/normalised input frame (the CLI's frame,
            post-normalisation, pre-engine). Never mutated.
        baseline_rules: Parsed rule dicts from `--rules` (+ packs).
        candidate_rules: Parsed rule dicts from `--impact-rules`.
        input_file / *_rules_file: Basenames for reporting.

    Returns:
        ImpactResult. Caller prints `format_summary(result)` and exits 3
        when `behavioural_changed > 0`, else 0.
    """
    t0 = time.perf_counter()
    n = len(df)
    engine_cols = [c for c in _ENGINE_COLS if c in df.columns]
    base_frame = df[engine_cols].copy()

    # Attribution must stay complete for the per-rule deltas: raise the
    # audit ceiling to worst-case firings (every rule on every row).
    # CLI runs keep the default cap — this is analysis-mode only.
    audit_cap = max(
        n * max(len(baseline_rules), len(candidate_rules), 1), 5000)

    # Two passes. run_audit copies its input internally (verified pure —
    # pass A cannot contaminate pass B; see test_12_pass_isolation).
    df_a, audit_a = run_audit(base_frame, baseline_rules,
                              audit_mode="full", audit_max=audit_cap)
    df_b, audit_b = run_audit(base_frame, candidate_rules,
                              audit_mode="full", audit_max=audit_cap)

    cat_a, cat_b = _result_col(df_a, "category", n), _result_col(df_b, "category", n)
    fl_a, fl_b = _result_col(df_a, "flags", n), _result_col(df_b, "flags", n)
    st_a, st_b = _result_col(df_a, "status", n), _result_col(df_b, "status", n)

    cat_changed = cat_a != cat_b
    status_changed = st_a != st_b
    # Flags: fast path on raw inequality, set-equality only where raw differs.
    flags_changed = fl_a != fl_b
    if flags_changed.any():
        diff_idx = flags_changed[flags_changed].index
        flags_changed.loc[diff_idx] = (
            fl_a.loc[diff_idx].map(_tokens) != fl_b.loc[diff_idx].map(_tokens))

    behavioural = cat_changed | flags_changed | status_changed

    rule_a = _last_rule_by_row(audit_a, n)
    rule_b = _last_rule_by_row(audit_b, n)
    attribution_only = (~behavioural) & (rule_a != rule_b)

    amounts = pd.to_numeric(
        df["amount"], errors="coerce").fillna(0.0).abs().reset_index(drop=True) \
        if "amount" in df.columns else pd.Series([0.0] * n)

    # Transition matrix: category-changed rows, indicative absolute amounts.
    transitions: List[dict] = []
    if cat_changed.any():
        tdf = pd.DataFrame({
            "old_category": cat_a[cat_changed].replace("", _UNCATEGORISED),
            "new_category": cat_b[cat_changed].replace("", _UNCATEGORISED),
            "amount": amounts[cat_changed],
        })
        grouped = (tdf.groupby(["old_category", "new_category"], sort=True)
                   .agg(rows=("amount", "size"),
                        indicative_amount=("amount", "sum"))
                   .reset_index())
        grouped = grouped.sort_values(
            ["indicative_amount", "old_category", "new_category"],
            ascending=[False, True, True])
        for rec in grouped.to_dict("records"):
            rec["rows"] = int(rec["rows"])
            rec["indicative_amount"] = round(float(rec["indicative_amount"]), 2)
            transitions.append(rec)

    # Per-rule match deltas (baseline order first, then candidate-only rules).
    counts_a = _rule_match_counts(audit_a)
    counts_b = _rule_match_counts(audit_b)
    names_a = _rule_names(baseline_rules)
    names_b = _rule_names(candidate_rules)
    ordered = list(dict.fromkeys(names_a + names_b))
    rule_deltas: List[dict] = []
    for name in ordered:
        in_a, in_b = name in names_a, name in names_b
        presence = "present" if (in_a and in_b) else ("removed" if in_a else "new")
        ma, mb = int(counts_a.get(name, 0)), int(counts_b.get(name, 0))
        rule_deltas.append({
            "rule": name, "matches_baseline": ma, "matches_candidate": mb,
            "delta": mb - ma, "presence": presence,
        })

    # Flag deltas: per token, rows gained/lost (set-membership, both sides).
    sets_a, sets_b = fl_a.map(_tokens), fl_b.map(_tokens)
    all_flags = sorted(set().union(*sets_a, *sets_b)) if n else []
    flag_deltas: List[dict] = []
    for tok in all_flags:
        has_a = sets_a.map(lambda s, t=tok: t in s)
        has_b = sets_b.map(lambda s, t=tok: t in s)
        gained, lost = int((~has_a & has_b).sum()), int((has_a & ~has_b).sum())
        if gained or lost:
            flag_deltas.append(
                {"flag": tok, "rows_gained": gained, "rows_lost": lost})

    # Status deltas: per value, row counts both sides.
    vc_a, vc_b = st_a.value_counts(), st_b.value_counts()
    status_deltas: List[dict] = []
    for status in sorted(set(vc_a.index) | set(vc_b.index)):
        if status == "":
            continue
        ra, rb = int(vc_a.get(status, 0)), int(vc_b.get(status, 0))
        if ra != rb:
            status_deltas.append({"status": status, "rows_baseline": ra,
                                  "rows_candidate": rb, "delta": rb - ra})

    # Row-level changed rows (artefact source — written to CSV in Branch 2).
    changed_mask = behavioural | attribution_only
    changed_rows: List[dict] = []
    if changed_mask.any():
        change_class = behavioural.map(
            {True: "behavioural", False: "attribution"})
        ctx = pd.DataFrame({
            "row_number": pd.RangeIndex(1, n + 1),
            "counterparty": _result_col(df, "counterparty", n),
            "amount": _result_col(df, "amount", n),
            "date": _result_col(df, "date", n),
            "memo": _result_col(df, "memo", n),
            "old_category": cat_a, "new_category": cat_b,
            "old_flags": fl_a, "new_flags": fl_b,
            "old_status": st_a, "new_status": st_b,
            "old_rule": rule_a, "new_rule": rule_b,
            "change_class": change_class,
        })
        changed_rows = ctx[changed_mask].to_dict("records")

    behavioural_count = int(behavioural.sum())
    attribution_count = int(attribution_only.sum())

    return ImpactResult(
        rows_compared=n,
        behavioural_changed=behavioural_count,
        attribution_changed=attribution_count,
        rows_stable=n - behavioural_count - attribution_count,
        transitions=tuple(transitions),
        rule_deltas=tuple(rule_deltas),
        flag_deltas=tuple(flag_deltas),
        status_deltas=tuple(status_deltas),
        changed_rows=tuple(changed_rows),
        input_file=input_file,
        baseline_rules_file=baseline_rules_file,
        candidate_rules_file=candidate_rules_file,
        duration_seconds=round(time.perf_counter() - t0, 3),
    )


# ---------------------------------------------------------------------------
# CLI summary (the CLI layer prints these lines)
# ---------------------------------------------------------------------------

def format_summary(result: ImpactResult) -> List[str]:
    """Build the CLI summary lines (mirrors reconcile's summary register)."""
    lines: List[str] = []
    lines.append(
        f"Impact analysis: {result.baseline_rules_file} -> "
        f"{result.candidate_rules_file} on {result.input_file} "
        f"({result.rows_compared:,} rows, {result.duration_seconds:.1f}s)"
    )
    pct_stable = (100.0 * result.rows_stable / result.rows_compared
                  if result.rows_compared else 100.0)
    lines.append(
        f"   {result.behavioural_changed} behavioural change(s), "
        f"{result.attribution_changed} attribution-only, "
        f"{result.rows_stable} stable ({pct_stable:.2f}% stable)"
    )
    for t in list(result.transitions)[:5]:
        lines.append(
            f"   {t['old_category']} -> {t['new_category']}: "
            f"{t['rows']} row(s), indicative amount {t['indicative_amount']:,.2f}"
        )
    if len(result.transitions) > 5:
        lines.append(f"   ... and {len(result.transitions) - 5} more transition(s)")
    added = sum(1 for r in result.rule_deltas if r["presence"] == "new")
    removed = sum(1 for r in result.rule_deltas if r["presence"] == "removed")
    if added or removed:
        lines.append(f"   Rules added: {added}, removed: {removed}")
    lines.append(f"   {FLOAT_DISCLAIMER}")
    if result.behavioural_changed:
        lines.append(
            f"   Result: REVIEW REQUIRED — {result.behavioural_changed} "
            f"row(s) change behaviour (exit 3)"
        )
    else:
        lines.append("   Result: no behavioural changes (exit 0)")
    return lines
