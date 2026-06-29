# FinLang Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.8.0] - 2026-06-29

### Added
- **`--reconcile-identity-fields <field[,field...]>` (SOL-103)** — identity guard for `--reconcile`. Verifies the named fields line up row-for-row between FinLang's output and the ML output *before* comparison. On misalignment the run stops with exit 1 and writes `reconcile_identity_failures.{csv,json}` naming the first divergent rows — catching silent row-shift before it produces misleading mismatch counts. Positional reconcile (v0.7.8 behaviour) is unchanged when the flag is omitted.
- **`--reconcile-key <field[,field...]>` (SOL-104)** — key-based reconciliation alignment. Matches rows by a canonicalised composite key (hash join, O(N+M)) instead of by position, so external systems can reorder, drop, or add rows. Rows present on only one side are reported as orphans: `reconcile_orphans_finlang.csv` (FinLang rows with no ML match) and `reconcile_orphans_ml.csv` (ML rows with no FinLang match); orphans set exit 3 (review-needed). Duplicate keys on either side stop the run with exit 1 (strict — an ambiguous key can't be reconciled). Mutually exclusive with `--reconcile-identity-fields`.
- **Rule-change impact analysis (SOL-105)** — `--impact-rules <candidate.fin>` runs the same input through the baseline rulepack (`--rules`) and a candidate rulepack and reports what the change does: rows re-categorised (behavioural change → exit 3), rules renamed with the same outcome (attribution-only → reported, never gates), and an indicative amount moved per category transition. `--impact-output-dir` writes `impact_report.json` (schema `impact/1`, including baseline + candidate rule-text SHA-256s) and `impact_changes.csv`; `--impact-html` adds a self-contained HTML report. Impact is an analysis run — it writes no categorised output.
- **New modules:** `src/finlang/tools/impact.py` (impact engine, decoupled from the FinLang engine) and `src/finlang/tools/impact_html.py` (HTML report generator, `html.escape()` on every user-provided string). `src/finlang/tools/reconcile_html.py` gained orphan sections.
- **HTTP API parity (SOL-041 wrapper extended):** `POST /reconcile` exposes `reconcile_identity_fields` + `reconcile_key` and surfaces `orphans_finlang_csv` / `orphans_ml_csv` in the response; new **`POST /impact`** endpoint (baseline `rules` vs candidate `impact_rules`, `impact_html`, `?format=html`) mirrors `/reconcile`. `test_api.py`: 17 → 24 standalone tests.
- **New documentation:** `docs/impact.md` (feature explainer); `docs/reconciliation.md` expanded for identity-guard, key alignment, and orphan artefacts; `docs/api.md` + `docs/api_reference.md` updated for the new params and `/impact`.

### Changed
- **Reconcile JSON report schema** gained `alignment_mode` (`positional` | `key:<fields>`) plus `orphans_finlang_count` / `orphans_ml_count` (additive — positional-mode reports are unchanged apart from the new `alignment_mode: positional` line). This schema change is the reason for the minor version bump (0.7.x → 0.8.0).
- **Engine `run_audit` gained an additive `audit_max` parameter** (used by impact's two-pass diff). The default code path is **output-identical** to v0.7.9 — existing categorisation, audit, verify, and reconcile output is unchanged.
- **Alignment API endpoints (`/reconcile`, `/impact`)** map engine exit 1 to HTTP 422 (an overloaded structural / client-data condition, mapped by its dominant meaning) with a structured discriminator body (`error` enum + `exit_code` + `message` + `stderr`); exit 3 → HTTP 200 (review-needed is the expected outcome, not an error).
- **Daily test gate:** 137 → 168 tests, 10 gates unchanged. Gate 10 now runs `test_reconcile.py` + `test_impact.py` (50 tests). Standalone API gate: 17 → 24.

### Fixed
- (none — additive feature release)

---

## [0.7.9] - 2026-05-18

### Added
- **`[api]` optional extras group** — `pip install finlang[api]` installs `fastapi`, `uvicorn`, `python-multipart`. Core install (`pip install finlang`) unchanged; users who don't install `[api]` are unaffected.
- **`finlang-api` console script** — runs the FastAPI app via uvicorn for local development and demo. Single-process by default; production deployments run behind a reverse proxy (nginx, Caddy) with TLS termination.
- **New module: `src/finlang/api/main.py`** — thin FastAPI wrapper over the published FinLang CLI entry points. Subprocess dispatch only; never imports engine internals.
- **Endpoints:** `GET /` (landing), `GET /health` (liveness + version), `POST /process` (categorise), `POST /discover` (find uncategorised counterparties), `POST /suggest` (generate draft `.fin` rules), `POST /reconcile` (ML reconciliation with optional HTML report).
- **`/reconcile` exit-code semantics:** exit code 3 (mismatches found) maps to HTTP 200 with mismatches in the response body. Mismatches are an expected review outcome of reconciliation, not an error. Only ops errors (exit 1 → 500) and validation errors (exit 2 → 422) map to error HTTP statuses on this endpoint.
- **`/reconcile?format=html` query param** — returns the HTML report directly with `Content-Type: text/html`, bypassing JSON wrapping. Convenient for human inspection (browsers, Swagger UI, curl piped to file); requires `reconcile_html=true`. Default `format=json` returns the full `ReconcileResponse` (existing behaviour, no breaking change). Closes the UX gap where viewing the HTML report from a JSON response required manual field extraction + backslash-escape cleanup.
- **Optional API-key authentication** — set `FINLANG_API_KEY` env var to enable `X-API-Key` header gating on all non-health endpoints. Auth is opt-in (disabled when env var unset). `/health` is always public.
- **Configurable limits** — `FINLANG_API_TIMEOUT` (default 300s subprocess timeout), `FINLANG_API_MAX_UPLOAD` (default 100 MiB upload cap), `FINLANG_API_HOST` / `FINLANG_API_PORT` / `FINLANG_API_LOG_LEVEL` for the `finlang-api` script.
- **API test suite: `test-suite/test_api.py`** — 17 tests covering health, root, `/process`, `/discover`, `/suggest`, `/reconcile` (perfect-match, mismatches, HTML emission, `format=html` direct-response, `format=html` validation), auth gating, and a CLI/API reconcile parity contract test. Standalone gate, **not** part of daily `quick_check.ps1` (137 tests / 10 gates unchanged); run via `python -m pytest test_api.py -v` from `test-suite/` with `pip install -e ../prod[api]` + `pip install httpx` in the test venv.
- **New documentation:** `docs/api.md` (user-facing workflow doc — when to use, request flow, worked example, configuration, exit-code mapping, limitations) and `docs/api_reference.md` (full endpoint reference with form-field tables, response schemas, curl recipes, deployment notes).
- **README + cli_reference.md** cross-linked to the new API docs.

### Changed
- Engine and CLI surfaces unchanged. SOL-041 is a curated wrapper — new CLI flags need explicit endpoint parameters, not auto-forwarded.

---

## [0.7.8] - 2026-05-15

### Added
- `--reconcile <ml_output.csv>` — independent ML validation layer. Compares FinLang's deterministic output against an external (typically ML) categorisation, producing a row-by-row mismatch report with rule attribution and audit reason. Requires `--audit` and `--audit-mode full`.
- `--reconcile-fields <field[,field...]>` — comma-separated fields to compare. Default: `category`.
- `--reconcile-output-dir <path>` — directory for reconciliation artifacts (`reconcile_report.json`, `reconcile_mismatches.csv`).
- `--reconcile-html` — additionally emit a self-contained HTML report (`reconcile_report.html`). Requires both `--reconcile` and `--reconcile-output-dir`. No JS, no external resources, opens offline.
- `memo` field surfaced on per-row mismatch dict (downstream presentation surfaces — HTML report, future audit viewer).
- New module: `src/finlang/tools/reconcile.py` — reconciliation engine, decoupled from the FinLang engine.
- New module: `src/finlang/tools/reconcile_html.py` — HTML report generator with `html.escape()` on every user-provided string.
- Exit code 3 on reconciliation mismatch (consistent with `--verify`).
- New documentation: `docs/reconciliation.md` (full feature explainer) and `docs/verify.md` (backfilled v0.7.7 explainer).

### Changed
- Daily test gate: 9 → 10 gates, 118 → 137 tests. New Gate 10 runs `test_reconcile.py` (19 tests).
- Post-engine validation phase refactored: `--verify` and `--reconcile` coexist via a `post_engine_failure` flag; both run independently and each reports its own artifacts. Exit code 3 set if either fails.

### Fixed
- (none — pure additive feature release)

---

## [0.7.7] - 2026-04-04

### Added
- `--verify` and `--verify-full` CLI flags — SHA-256 integrity verification with optional artifact output (`--verify-output-dir`)
- Exit code 3 for verification failure
- Stopword filter in fuzzy suggest mode (LTD, LLC, PLC, INC, GROUP, COMPANY, CO, SAS, GMBH, CORP)
- Intra-batch dedup in fuzzy suggest mode

### Fixed
- CR/DR no-space regex bug (`200DR` now correctly parsed as negative)
- Stale filename references in sync comments

## [0.7.6] - 2026-03-09

### Fixed
- Bundled rulepacks: reverted over-tightened `* FX *` patterns to `*FX*` in `05-financial.fin` and `06-compliance.flags.fin` — space-padding caused missed matches on FX memo variants
- Bundled rulepacks: reverted `ALDI*` to `*ALDI*` in `01-vendors-retail.fin` restoring 0.7.2 coverage parity

## [0.7.5] - 2026-03-08

### Fixed
- Bundled rulepacks — wildcard hardening across `02-transport.fin`, `01-vendors-retail.fin`, `05-financial.fin`, `06-compliance.flags.fin`. Unpadded short tokens replaced with space-padded equivalents to prevent false matches on counterparty names.

## [0.7.4.post1] - 2026-03-02

### Fixed
- discover.py: string "False" from CSV round-trip incorrectly filtered as excluded (silent data drop)
- suggest.py: Unicode emoji crashed on Windows cp1252 console encoding

## [0.7.4] - 2026-03-01

### Fixed
- **Critical:** Restored `exclude` functionality (broken since v0.6.4 launch — dead `continue` statement bypassed all exclude logic).
- **Critical:** Fixed cache staleness in rule chaining — rules matching on fields modified by earlier rules now correctly see updated values.
- **Engine:** Added defensive `.copy()` on post-state audit snapshots to prevent view-mutation issues.
- **Engine:** Audit diffs for `exclude` now serialize as JSON booleans (`true`/`false`), not strings (`"True"`/`"False"`).
- **CLI:** Added `exclude` to engine column selection and write-back loop so the column appears in output CSV.

### Added
- **Engine:** Intent-based exclude initialisation — column appears only when ruleset references exclude; absent otherwise (clean schema).
- **Engine:** Second-pass coercion — exclude column from a previous pass survives as proper booleans regardless of current ruleset.
- **Testing:** `test_rule_interactions.py` — 12 tests, 55 assertions covering cache invalidation, exclude semantics, exception pattern (blacklist/whitelist), audit modes, boolean serialisation, idempotency, and Option 2 contract (exclude does not freeze rows).
- **Testing:** Rule interaction tests integrated into `quick_check.ps1` daily gate (now 4 stages, 68 total assertions).

### Changed
- **Engine:** Renamed `finlang_engine_v0_6_4.py` → `finlang_engine.py` (imports updated across CLI, tests, and documentation).

## [0.7.3] - 2026-02-25

### Fixed
- Rule parser now strictly rejects whitespace in `flags +=` values to prevent silent token splitting. Use underscores or camelCase (e.g. `Large_Tx` or `LargeTx`).

## [0.7.2] - 2026-01-31
### Fixed
- **Critical:** Resolved a regex escaping incompatibility that could trigger crashes when the PyArrow backend was active (or installed). All internal patterns are now RE2-compatible across all backends.
- **Resilience:** Hardened `finlang-discover` against backend variability; improved graceful fallback behavior when optional dependencies are unavailable.

### Added
- **Transparency:** Added explicit engine reporting `(Engine: ...)` to `finlang-discover`, aligning runtime visibility with the main CLI.
- **Documentation:** Introduced `docs/runtime_contract.md`, establishing the authoritative runtime, backend, and IO behavior contract.

### Changed
- **Branding:** Refined CLI help text and version descriptors for a production-quality release.
- **Housekeeping:** Updated copyright headers to 2026 across the codebase.

## [0.7.1] - 2026-01-27
### Fixed
- **Engine:** Resolved a critical `RuntimeError` on Python 3.13+ and Pandas 3.0 where passing regex flags conflicted with pre-compiled patterns during fuzzy matching (`~`).

### Changed
- **Architecture:** Hardened the regex engine to use stateless string patterns with inline modifiers (`(?s)`), ensuring strict compatibility with modern Pandas versions.
- **CI:** Updated test matrix to officially support Python 3.13 and Python 3.14.

## [0.7.0] - 2025-12-30
### Added
- **Banking Pack v1.0:** First stable release of the Open Core rulepacks.
- **Rule Hardening:** Added split logic for M&S, Apple, BA, and Cash/ATM to ensure strict engine compatibility.
- **Engine:** Introduced strict validation for bundled rulepacks.

### Fixed
- **Rules:** Fixed "AND Trap" logic where multi-line matches were silently failing (Rules affected: 10/43).
- **CLI:** Eliminated silent write-back loss for status and memo fields.
- **Docs:** Clarified AND vs OR semantics in `08-examples.fin`.

## 📈 Internal/Engineering
**Status:** Added Tier 1 Contract Tests to enforce CLI/Engine schema parity.

## [v0.6.4.post4] — 2025-11-26 — Improvement
**Status:** Patch Release

### Added
- **Mapping:** Added "Started Date" and "Completed Date" to the default `bank.map.json` to support **Revolut** exports out-of-the-box.

## [v0.6.4.post3] — 2025-11-25 — Hotfix
**Status:** Critical Patch

### Fixed
- **CLI Integration:** Fixed a bug where `status` fields were not passed to the engine, and updates to `status` and `memo` were discarded before output. Both fields are now fully matchable and settable.

## [v0.6.4.post2] — 2025-11-14 — GA (Final Polish)
**Status:** Production-ready (Fully Validated)

### Fixed
- **CI/CD Hardening:** Fixed CLI exit code behavior to ensure pipeline reliability.
  - `--fail-threshold` violations now correctly exit with code `2` (Validation Error).
  - Output file write failures (e.g., read-only fs) now correctly exit with code `1` (Runtime Error).
- **Documentation:** Removed "Known Issues" section; all identified exit-code bugs are resolved.

## [v0.6.4] — 2025-11-09 — GA (Machine-Grade)


### 🚀 Highlights
- **GA Docs Suite (audited & approved):**
  - `cli_reference.md` (GA Rev 3.1) — complete CLI for `finlang`, `finlang-discover`, `finlang-suggest`, env vars, cross-platform examples.
  - `rule_language.md` (Rev 2) — stable DSL spec, stacked rules, determinism, best practices.
  - `flags.md` (Rev 2) — canonical inputs for all flags (incl. `--fail-threshold` as **fraction 0.0–1.0**).
  - `i18n_examples.md` (Rev 2) — regional recipes (FR/DE, UK, CH apostrophe, explicit `--dayfirst` for determinism).
  - `mapping_guide.md` (Rev 3.4) — **correct nested `amount` mapping** (`aliases` / `debit` / `credit`), case-insensitive matching, custom map **replaces** default, `exclude` = informational only in v0.6.4.
  - `growth_loop_best_practices.md` (Rev 2) — discover → **suggest** (`--emit-match exact`) → review/merge.
  - `workflows.md` (GA Rev 3.2) — Daily Run, Growth Loop, benchmarking, enterprise rollout; Windows/Linux/macOS parity.
  - `benchmarks.md` (GA Rev 3.1) — validated: **≈24k rows/s @ 5M×50**; audit overhead characterized (~38%).
  - `stateless_processing.md` (Rev 2), `amount_synthesis.md` (Rev 2), `release_notes_v0_6_4.md` (Rev 2), `install.md` (Rev 2), `faq.md`, `security.md`, `compliance_pack.md`.
  - Add CONTRIBUTING.md and CLA.md
### ✨ Engine / CLI
- Locale controls: `--decimal`, `--thousands`, `--dayfirst`; `--encoding utf-8-sig` (default) with `--encoding auto` available.
- Strictness: `--strict-parse`, `--fail-threshold` (**fraction**, e.g. `0.02`).
- Audit: `--audit`, `--audit-mode` (`none|lite|full`); CSV injection mitigations.
- Discovery & Suggestion workflow standardized:
  - `finlang-discover --candidates ... [--all/--all-candidates ...]`
  - `finlang-suggest --emit-match exact` recommended.

### 📈 Performance
- Linear scaling validated; ~24,003 rows/sec on 5M×50.
- Audit diff overhead characterized (~38%) with sustained throughput.

### 🗂 Mapping
- Default `bank.map.json` path documented; custom `--map` **replaces** default.
- `amount` mapping supports **single-column aliases** or **debit/credit synthesis**.
- `exclude` field: usable as a boolean marker in rules; **no automatic row dropping** in v0.6.4.

### 🧾 Legal & Governance
- **CLA v1.0** added (dual-licensing enablement; contributor retains copyright).
- `terms.md`, `privacy.md`, `compliance_pack.md` aligned under Scottish law.


## [0.6.4.post1] – 2025-11-03
**Status:** Production-ready (RC1 certified)

### Added
- Restored before/after **diff auditing** in both `lite` and `full` modes.
  - `lite`: logs one entry per **changed row** → `{index, rule, changes{old,new}}`.
  - `full`: adds rule context (`match[]`, `set[]`) plus per-row `changes`.
- Deep audit verification confirming deterministic, "machine-grade" operation.

### Improved
- **Internationalisation (I18n)**: locale-aware numeric parsing, CR/DR semantics,
  encoding/delimiter auto-detection, strict date handling.
- **Engine Hardening**: strict parsing (`--strict-parse`), fail-threshold guards,
  control-character stripping, and CSV formula-injection protection.
- **Performance**: validated 24k–39k rows/sec throughput with linear scaling.

### Fixed
- Regression in `run_audit()` (introduced during I18n refactor) that omitted
  before/after diffs.

  ### Known Issues
- `--fail-threshold`: Logs a **FATAL** error when the drop-rate is exceeded,  
  but returns exit code `0` in v0.6.4.  
  Planned fix: v0.7 will exit with code `1` when threshold is breached.

---

## [0.6.3] – 2025-09-30
### Added
- New `--emit-match exact` mode in `finlang-suggest` for 1:1 rule generation.
- De-duplication now checks both fuzzy (`~`) and exact (`==`) patterns.

---

## [0.5.2] – 2025-06-15
### Initial public release
- Core deterministic engine.
- `finlang`, `finlang-discover`, and `finlang-suggest` CLIs introduced.
- Basic auditing and rule application framework.
