# FinLang v0.8.0 — Impact Analysis & Reconcile v2
*Released: 29 June 2026*

---

## Summary

Two new capabilities, both about confidence before a decision.

**Impact analysis** shows you what a rule change does *before* you ship it — which transactions move, how much money shifts, and whether a change is real behaviour or just a rule rename.

**Reconcile v2** makes the ML-challenge comparison hold up when the two sides don't line up row-for-row — match by content instead of position, and see the rows that exist on only one side instead of a wall of misleading mismatches.

Same deterministic engine. Same audit trail. The default categorisation output is unchanged.

---

## What's New

### See a rule change before it ships — `--impact-rules` (SOL-105)

Changing a categorisation rule is nerve-wracking because you can't easily see what *else* moves. Impact analysis removes that blind spot. It runs the same input through your current rulepack (`--rules`) and a candidate rulepack (`--impact-rules`), then tells you exactly what the change does:

- **Behavioural change** — a transaction lands in a different category. Surfaced, and sets exit 3 (review-needed).
- **Attribution-only** — the same outcome, just matched by a renamed rule. Reported, but never gates.
- **Indicative amount moved** — per category transition, so you can see the size of the change, not just the count.

```bash
finlang --input transactions.csv --rules current.fin --impact-rules candidate.fin \
        --impact-output-dir impact_out --impact-html --headless
```

`--impact-output-dir` writes `impact_report.json` (schema `impact/1`, including SHA-256 hashes of both rulepacks' text) and `impact_changes.csv`; `--impact-html` adds a self-contained HTML report you can open offline. Impact is an analysis run — it writes no categorised output, so it can't accidentally overwrite a real run.

### Reconcile that survives messy data — `--reconcile-key` (SOL-104)

v0.7.8 reconcile compared row N against row N. That's correct only when both systems emit rows in the same order — and real ML pipelines reorder, drop, and add rows. When they do, positional comparison reports mismatches that aren't real.

Key alignment matches rows by a canonicalised composite key (e.g. `date,amount,counterparty`) instead of by position:

```bash
finlang --input txns.csv --rules rules.fin --reconcile ml_output.csv \
        --reconcile-key date,amount,counterparty \
        --audit audit.json --audit-mode full \
        --reconcile-output-dir recon_out --headless
```

Rows that exist on only one side become **orphans**, surfaced rather than silently mismatched:

- `reconcile_orphans_finlang.csv` — FinLang categorised a row the ML output never mentioned
- `reconcile_orphans_ml.csv` — the ML output has a row FinLang never saw

Orphans set exit 3 (review-needed). Duplicate keys on either side stop the run with exit 1 — an ambiguous key can't be reconciled honestly, so FinLang refuses to guess.

### Catch silent row-shift — `--reconcile-identity-fields` (SOL-103)

For workflows that *are* positional, the identity guard checks the rows genuinely line up before comparing — so a one-row offset can't masquerade as a wall of mismatches:

```bash
finlang ... --reconcile ml_output.csv --reconcile-identity-fields date,amount,counterparty ...
```

If the named fields don't match position-for-position, the run stops with exit 1 and writes `reconcile_identity_failures.{csv,json}` naming the first divergent rows.

### The API keeps pace — `/reconcile` params + new `/impact`

Three surfaces, one engine — and v0.8.0 keeps that promise. Every new capability is reachable over HTTP, not just the CLI:

- `POST /reconcile` now accepts `reconcile_identity_fields` and `reconcile_key`, and surfaces `orphans_finlang_csv` / `orphans_ml_csv` in the response.
- **New `POST /impact`** endpoint — baseline `rules` vs candidate `impact_rules`, with `impact_html` and `?format=html` for the report directly.
- The alignment endpoints map engine exit 3 → HTTP 200 (finding differences is the expected outcome) and exit 1 → HTTP 422 with a structured discriminator body (`error`, `exit_code`, `message`, `stderr`).

Standalone API tests grew from 17 to 24.

---

## Why This Matters

v0.7.9 framed FinLang as an **ML-challenger** — an HTTP service your pipeline can POST to and get a rule-attributed answer back, row by row. v0.8.0 makes that real against pipelines as they actually behave.

Positional-only reconcile was fragile: the moment an ML system reordered its output, the comparison broke. Key alignment plus orphan surfacing means you can challenge a model's output even when the two systems don't emit rows in the same order — and you find out about the rows that don't exist on both sides, which is often where the interesting disagreements hide.

Impact analysis closes the loop on the other side. When a reconcile run flags a disagreement and you reach for a rule change to fix it, you can now see exactly what that change does to *everything else* first. Change with your eyes open, not on a hunch.

---

## What Hasn't Changed

- **Determinism.** No ML, no randomness, no network calls in the engine. Same input, same rules, same output — every time.
- **The default engine output.** `run_audit` gained an additive `audit_max` parameter (used internally by impact's two-pass diff). The default code path is **output-identical** to v0.7.9 — existing categorisation, audit, `--verify`, and `--reconcile` output is unchanged.
- **Positional reconcile.** The v0.7.8 positional comparison is still the default; the new alignment modes are opt-in via their flags.
- **The CLI surface.** Every flag from prior releases still works exactly as before. The new flags are additive.
- **Daily test gate.** Still 10 gates in `quick_check.ps1` — now 168 tests, with Gate 10 running reconcile + impact (50 tests). The API tests remain a separate standalone gate (24 tests).

---

## Performance

The categorisation hot path is unchanged, so engine throughput carries over from v0.7.9 (~217K rows/sec FastIO on the integrity harness; a confirmation run backs the no-regression claim for this release). Two notes on the new features:

- **Impact** runs the engine twice by design (baseline + candidate), so an impact run is roughly two categorisation passes over the same input.
- **Reconcile key alignment** is an in-memory hash join, O(N+M) in the row counts. The practical ceiling is machine RAM — both sides are held in memory to align them — which is comfortable into the low millions of rows.

---

## What This Completes

The reconcile hardening teased in the v0.7.9 notes — "safer row identity checks and key-based alignment for workflows where external systems may reorder outputs" — is exactly what shipped here, as `--reconcile-identity-fields` and `--reconcile-key`.

---

## How to Upgrade

CLI only:

```bash
pip install --upgrade finlang
```

CLI + HTTP API:

```bash
pip install --upgrade "finlang[api]"
```

With Fast I/O acceleration (recommended for large datasets):

```bash
pip install --upgrade "finlang[fastio]"
# Combine: pip install --upgrade "finlang[fastio,api]"
```

Verify:

```bash
finlang --version    # FinLang 0.8.0
```

---

## Migration Notes

**No migration required.** This release is additive:

- Existing `.fin` rules — unchanged.
- Existing CLI invocations — produce output identical to v0.7.9 on the default path.
- Positional `--reconcile` — still the default; the new alignment modes are opt-in.
- **Reconcile JSON consumers:** the report gained `alignment_mode` (`positional` | `key:<fields>`) and `orphans_finlang_count` / `orphans_ml_count`. These are additive — positional reports are unchanged apart from the new `alignment_mode: positional` line — but a strict schema validator should be told about the new keys.

---

## Acknowledgements

The API exit-code contract for the alignment endpoints (exit 1 → HTTP 422, with a structured discriminator body and the overloading documented honestly rather than papered over) was settled through a multi-model review pass. Both HTML reports — impact and reconcile orphans — were mockup-reviewed before implementation.

---

*See [CHANGELOG.md](../../CHANGELOG.md) for the full version history.*
*See [impact.md](../impact.md) for the impact-analysis feature explainer.*
*See [reconciliation.md](../reconciliation.md) for reconcile, including the v0.8.0 identity-guard and key-alignment modes.*
*See [api.md](../api.md) and [api_reference.md](../api_reference.md) for the HTTP surface.*
