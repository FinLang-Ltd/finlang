# FinLang v0.9.0 — The Workbench
*Released: September 2026*

---

## Summary

FinLang has a face now.

- **The Workbench** — `finlang-ui` opens a browser interface on your own machine. Pick a CSV, pick your rules, tick what you want checked, and run: every row comes back with the rule that decided it, verification and reconciliation arrive as reports you can hand to a human, and a rule builder reads your rules back in plain English — checked by the same engine that runs them.
- **One install** — `pip install finlang` now includes everything the Workbench and the HTTP API need. No extras required.
- **One API change to note** — a verify mismatch on `/process` is now reported as HTTP 200 with the findings in the body, matching `/reconcile` and `/impact`.

The engine is unchanged in this release. Same input, same rules, same output — whichever surface you use.

---

## What changed for you

### The Workbench: FinLang without the terminal

```
pip install -U finlang
finlang-ui
```

Your browser opens at `http://127.0.0.1:8484/ui/`. Five screens:

- **Run** — choose a transactions CSV and rules (a `.fin` file, a bundled rulepack, or your draft from the Rules screen), set the audit trail, tick **Verify** and/or **Reconcile against a model**, and run. Results arrive in tabs: the rows with their deciding rule, key-results charts drawn from the run's own output, the verify and reconcile HTML reports inline, downloads, and a **run log showing the equivalent `finlang` command** — so anything you click today, you can script tomorrow. A verify or reconcile finding is reported as the product working, not as an error.
- **Rules** — write rules directly or build them step by step. **Check syntax** sends the file to the real engine, and the Workbench reads back what the engine understood, in plain English: *when counterparty contains SHELL, then set category to Energy & Commodities.* The Workbench contains no parser of its own, so "valid here" and "valid in a run" are the same fact.
- **Growth loop** — find what no rule claimed in a run's output, then draft candidate rules for the gaps. Nothing enters your ruleset without you accepting it.
- **Impact** — compare your current rules with a proposed version and see which rows would re-categorise and how much value would move, before the change ships. It writes no output; it is a rehearsal.
- **Home** — the flow at a glance, and which engine version is serving.

**Local by design.** The server is bound to `127.0.0.1` with no override. The page makes no external requests — no CDN, no telemetry, no external fonts or scripts; everything it uses ships inside the package. If you want the HTTP surface on a network, that remains an explicit decision: `finlang-api`.

Full guide: [`docs/workbench.md`](../workbench.md).

### `pip install finlang` is now the whole product

`fastapi`, `uvicorn[standard]` and `python-multipart` moved from the optional `[api]` extra into the base install, so `finlang-ui` and `finlang-api` work from a plain `pip install finlang`. `pip install "finlang[api]"` still works — it simply adds nothing now.

### New API endpoints

- **`GET /rulepacks`** — the bundled rulepacks by short name, from the CLI's own pack map.
- **`POST /rules/validate`** — parse-check a rules file (upload or text) against the real engine. A parse failure comes back as a result (`ok: false` plus the engine's message), not an HTTP error.

### Behaviour change: verify mismatches on `/process`

When `/process` runs with `verify` or `verify_full` and the engine finds a mismatch (exit 3), the API now returns **HTTP 200** with `stats.exit_code = 3`, the categorised output, and the verify report in `verify_report` / `verify_report_html`. Previously it returned **422** with the report inside a structured `detail` object.

Why: a finding is a reported outcome, not a request error — `/reconcile` and `/impact` already worked this way. The old mapping also meant a client running verify and reconcile together hit a dead end at the 422 and never reached the reconciliation. **If your integration branched on a 422 with `detail.error == "verify_failed"`, read `stats.exit_code == 3` on a 200 instead.**

### Fixed: API row counts

`rows_in` / `rows_out` in API responses were counted as raw lines read as UTF-8, so a quoted field containing a line break inflated the count, and semicolon-delimited or non-UTF-8 files could be miscounted. Counts now use the engine's own delimiter detection and encoding handling, including `encoding="auto"`. The categorised data was never affected — only the reported statistics.

### How it was checked

The Workbench went through six rounds of adversarial review before release, with each finding resolved and pinned by a regression test. New standalone suites: 17 UI-contract tests pinning every response field the screens read, and 10 end-to-end tests driving a real browser against a live server and the real CLI, with nothing mocked. Standalone API suite: 29 → 39. Daily gate unchanged at 204 tests across 10 gates.

---

## Upgrade

```
pip install -U finlang
finlang-ui
```

Existing CLI flags, exit codes, rules and artefacts are unchanged. The one change that can affect existing integrations is the `/process` verify-mismatch status code above.
