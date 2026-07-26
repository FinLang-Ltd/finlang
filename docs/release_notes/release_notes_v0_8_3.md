# FinLang v0.8.3 — Verification you can hand to a human
*Released: 26 July 2026*

---

## Summary

Two changes, one theme: the trust layer now explains itself.

- **`--verify-html` (SOL-111)** — verification gains a readable, self-contained HTML report. It was the only trust-layer feature without one, while being the one aimed most directly at auditors.
- **Reconcile reads the ML file's dates on their own terms** — instead of assuming the external system shares FinLang's date convention, reconcile now infers the convention from the data, accepts an explicit `--reconcile-date-format`, and records whichever decision it made in the artefact.

Plus a round of hardening driven by three external review passes: environment-variable validation, API parity and loud rejection of silently-inert flag combinations, and a `--help` regression guard.

Daily test suite: 187 → 204 tests across the same 10 gates; standalone API suite: 26 → 29.

---

## What changed for you

### `--verify-html`: the integrity report a reviewer can read

`--verify` already wrote machine artefacts (`verify_report.json`, `verify_proof.csv`, `verify_mismatches.csv`). The new report is the human companion:

- **It states the facts up front, in plain English** — rows read, how dates and amounts were parsed, and which locale overrides were supplied (or explicitly that none were). A pass with no findings still reads as evidence, not an empty page.
- **Scope is explicit** — which fields were compared and which were deliberately not, rendered from the same constants the code uses, so the page cannot drift from the check.
- **Proof, not promises** — a fingerprint sample with real before/after hashes from your run.
- **Mismatch detail only when there is any** — and structural failures (like a row-count mismatch) are named as structural, never blamed on rows that passed.
- **Self-contained** — no JavaScript, no external references; can be opened offline and attached to a review as-is.

Usage: add `--verify-html` to a `--verify`/`--verify-full` run with `--verify-output-dir`. Via the API, `verify_html=true` on `/process` returns the rendered report inline as `verify_report_html` — including on a verification failure, where the 422 detail carries it alongside the JSON report.

### Reconcile no longer assumes your ML system's date convention

Reconcile's job is comparing FinLang output against an **external** system's CSV — and external systems emit local date formats. Previously the ML side was canonicalised under FinLang's own defaults: a day-first ML export could silently misalign, in the worst case reporting one identical transaction as two orphans.

Now, when `date` participates in identity or key alignment:

1. **Inferred** — the ML date column is scanned; any value with a component above 12 settles the convention deterministically. Two values settling it in opposite directions is a structural error (exit 1) — mixed conventions have no single correct reading.
2. **Explicit** — `--reconcile-date-format '%d/%m/%Y'` states the convention. The format is validated against every non-empty ML date before it is applied; a format that does not parse the data is a structural error (exit 1), never recorded as applied.
3. **Assumed** — if every date is ambiguous, reconcile proceeds month-first, warns on stderr, and records the assumption.

Whichever path ran, `reconcile_report.json` records it under `ml_date_convention` — the artefact states its own assumption instead of hiding it. The API gains the matching `reconcile_date_format` field on `/reconcile`.

Two deliberate strictness points: passing `--reconcile-date-format` without an alignment mode is a validation error (exit 2), because positional field comparison never parses dates and a silently-ignored flag is worse than an error; and the fix measured ~6% *faster* on the reconcile benchmark, since pandas no longer re-parses values under a mismatched convention.

**Behaviour note:** if your key/identity reconciliations previously "worked" against day-first ML data, alignments can change — the old behaviour was misreading those dates. The artefact now shows exactly which convention was applied.

### Hardening

- **`FINLANG_AUDIT_MAX` is validated at startup** — a non-integer previously crashed import with a raw traceback; a negative was silently accepted. Both are now a clean `FATAL` exit 2. The `run_audit(audit_max=...)` parameter enforces the same non-negative contract for direct in-process callers.
- **`--help` is guarded** — a smoke test renders `--help` for every entry point, so a formatting regression can no longer ship unnoticed.
- **API strictness** — `verify_html` without a verify mode is a 422, not a silent no-op.
- **Docs correction** — the default 5K integrity-harness run performs full field-by-field validation (fast fingerprint-only mode starts above the 100,000-row threshold); `benchmarks.md` previously described it as fingerprint-only.

---

## Upgrade

```
pip install -U finlang
```

New flags are opt-in; existing exit codes are unchanged. The new validation errors only fire on flag combinations that did not exist before this release. If you reconcile day-first ML data by key or identity fields, review `ml_date_convention` in your next `reconcile_report.json` — it now tells you how the dates were read.
