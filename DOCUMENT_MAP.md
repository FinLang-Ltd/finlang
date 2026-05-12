# FinLang Document Map
*Last updated: 12 May 2026 | v0.7.9-target (Unreleased) | SOL-041 FastAPI wrapper: new `src/finlang/api/` package (main.py + __init__.py), `[api]` optional extras group + `finlang-api` console script in pyproject.toml, new docs `docs/api.md` + `docs/api_reference.md`, standalone 15-test gate `test-suite/test_api.py`. Daily quick_check 137/10 unchanged (standalone gate decision). Builds on v0.7.8 SOL-040 reconcile (shipped 9 May 2026).*

This document is the authoritative map of the FinLang codebase, documentation, testing infrastructure, and demo environment. It exists to ensure that changes to the system update the correct files, tests, and documentation consistently. This document should be updated whenever new files, tests, or major documentation are introduced.

**Post-consolidation note (27 April 2026):** FinLang lives in a single-tree workspace at `{workspace}\` with subfolders `prod\` (this repo, the tracked codebase), `test-suite\` (external validation + release gate), `commercial\` (rulepacks, partitioned), `scratch\` (disposable), `strategy-backlog\` (BACKLOG/ROADMAP/SOL specs). This document describes files in `prod\` and `..\..\test-suite\` from the perspective of `prod\`. Workspace-level docs live at `{workspace}\` — see the "Top-Level Workspace Documents" section below. For the full layout see `..\..\PROJECT_FOLDER_STRUCTURE.md`.

**Persistence model for `prod\CLAUDE.md` (1 May 2026 update):** the working contract lives at `prod\CLAUDE.md`, **gitignored** (same pattern as `RELEASE_CHECKLIST.md`). It sits in `prod\` for path coherence and is read by every CC session, but does not ship in public git history; recovery relies on external workspace backup. The Path A/B/C branch model from Process Lock 280426 (28 April 2026) doesn't mechanically apply here — there are no commits to gate — but the editing discipline still does: Angus's trivial edits go directly; CC-authored or substantive rewrites get diff-reviewed before save. The pre-consolidation canonical-source-mirror pattern remains retired; the file lives once, in `prod\`, gitignored.

### Version Sync Rule
Version numbers must remain consistent across these **five** files on every release. Four are tracked, one is gitignored — the gitignored one is the easy one to forget because it won't surface in `git status` or any pre-commit check:

- `__init__.py` — tracked
- `pyproject.toml` — tracked
- `run_finlang.py` (fallback `__version__`) — tracked
- `canonical_fields.yaml` — tracked
- `prod/CLAUDE.md` (header canary line) — **gitignored** since 1 May 2026; check explicitly on every release

`CHANGELOG.md` also gets a new entry every release but doesn't carry the version string in the same way.

---

## System Architecture Overview

FinLang consists of five major components:

1. **Engine** — Rule parsing and deterministic execution (`finlang_engine.py`)
2. **CLI Interface** — Argument parsing, data hardening, and orchestration (`run_finlang.py`)
3. **Tools** — Discovery, rule generation, integrity verification, and ML reconciliation (`discover.py`, `suggest.py`, `verify.py`, `reconcile.py`)
4. **Documentation & Rulepacks** — DSL specification, bundled categorisation packs, and user guides
5. **Validation Infrastructure** — 137-test daily suite (10 gates) + rulepack linter, integrity verification, cleanroom PyPI validation, golden master baselines, ML reconciliation (JSON+CSV+HTML)

---

## Source Repo (`finlang`) — lives at `{workspace}\prod\`

### Core Source Files

| File | Contains | Update When |
|------|----------|-------------|
| `src/finlang/__init__.py` | `__version__` string | Version bump |
| `pyproject.toml` | Package version, dependencies, entry points | Version bump, new dependency, new CLI entry point |
| `src/finlang/cli/run_finlang.py` | Main CLI: argparse flags, data hardening (`_to_number`, `_CURRENCY_NBSP_RE`), header mapping, engine orchestration, fallback `__version__` | New/changed CLI flags, new amount formats, mapping logic changes, version bump |
| `src/finlang/engine/finlang_engine.py` | Rule parser, condition/action evaluator, `CANON_FIELDS_MATCH`/`CANON_FIELDS_SET`, `TEXT_COLS`, wildcard/range matching | New operators, new matchable/settable fields, rule syntax changes |
| `src/finlang/tools/discover.py` | Discovery tool: argparse, `_to_number` (synced copy), candidate extraction, exclude-aware filtering | New discover flags, changes to amount parsing, exclude logic changes |
| `src/finlang/tools/suggest.py` | Rule generator: fuzzy/exact modes, dedup, quote styles, append/overwrite | New suggest flags, output format changes |
| `src/finlang/tools/verify.py` | Post-engine integrity verification: SHA-256 fingerprinting, fast/full modes, artifact generation | Verification logic changes, new verification modes |
| `src/finlang/tools/reconcile.py` | Independent ML validation layer (SOL-040, v0.7.8): positional alignment, field comparison, audit linkage from `audit.json`, JSON+CSV artifact generation, optional HTML report dispatch (when `emit_html=True` and `output_dir` set). Decoupled from engine — post-engine hook called from `run_finlang.py`. | New reconcile flags, alignment modes (key-based), report schema changes, audit-extraction logic changes |
| `src/finlang/tools/reconcile_html.py` | HTML report generator for reconciliation (SOL-040 Branch 3, v0.7.8): self-contained HTML view of a `ReconcileResult` — title + status banner + mismatch table + footer. F-string templating with inline CSS, `html.escape()` on every user-provided string (XSS-safe), join-pattern row construction (O(N) not O(N²)). Renders only fields the `reconcile.py` output dict exposes — no engine extension. Lazy-imported by `reconcile.py` when `emit_html=True`. | Visual contract changes (mockup at `..\..\scratch\mockups\reconcile_html_mockup.html`), CSS theme updates, new fields added to `ReconcileResult` mismatch dict |
| `src/finlang/api/__init__.py` | API package init (SOL-041): re-exports `app` and `run` from `main.py` so consumers can `from finlang.api import app, run` without reaching into the module. | New top-level API exports |
| `src/finlang/api/main.py` | FastAPI wrapper around the FinLang CLI (SOL-041): thin REST surface (`GET /`, `GET /health`, `POST /process`, `POST /discover`, `POST /suggest`, `POST /reconcile`) over the published CLI entry points via subprocess. Never imports engine internals. `/reconcile` exit-code semantics: whitelist `{0, 3}` → HTTP 200 (mismatches are an expected review outcome), `1` → 500, `2` → 422. Optional API-key auth via `FINLANG_API_KEY` env var + `X-API-Key` header. Curated, not auto-forwarding — new CLI flags need explicit `Form()` parameters. | New endpoints, new form-field parameters, subprocess dispatch logic changes, auth or limit configuration changes, new response models |
| `src/finlang/mapping/bank.map.json` | Default header mapping (date, counterparty, memo, amount with aliases + debit/credit) | New bank format support |
| `src/finlang/rulepacks/*.fin` | 8 bundled packs: retail, transport, subs, travel, financial, compliance, sanity, examples | Pack content changes, new packs added |
| `src/finlang/utils/resources.py` | Package resource loading helpers | Structural changes to pack/map loading |
| `tests/contracts/canonical_fields.yaml` | Version string, engine input/output field lists for AST contract tests | Version bump, new canonical fields |

### Internal Process Files (in `prod\`, mixed visibility)

These files live in `prod\` because they reference prod-side files extensively. Two are **gitignored** maintainer tooling that doesn't ship to GitHub or PyPI (`RELEASE_CHECKLIST.md`, `CLAUDE.md`); one is **tracked** and ships as part of the published repo (`DOCUMENT_MAP.md` — it's the file map for the public codebase).

| File | Contains | Visibility | Update When |
|------|----------|-----------|-------------|
| `RELEASE_CHECKLIST.md` | **Operational v0.7.x content** (March 2026 vintage, restored 28 April 2026 from `..\..\scratch\internal_snapshots\v0.7.7\` during Process Lock 280426 sidetrack — replaces the earlier post-consolidation placeholder). 11-step release process: Version Bump → Documentation → Local Dev → Run Tests → Commit & Tag → Build → Lemon Squeezy → Publish PyPI → Clean Room → GitHub Release → Announce. **Targeted updates deferred to separate Path B task post-Process-Lock**: paths reflecting single-tree (no `dev/`), current dates, Path C alignment language (Process Lock 280426 — manual `twine upload` permitted only after checklist completion + cleanroom validation, until release gate is built). The pre-consolidation copy remains archived at `..\..\scratch\archive\RELEASE_CHECKLIST-pre-consolidation-20260427.md`. | **Gitignored** — internal-only (per Rule 6 of folder-structure-package single-tree variant) | When the deferred Path B targeted updates land; or when release steps materially change |
| `CLAUDE.md` | **Working contract** for Claude Code — gitignored as of 1 May 2026 (same pattern as `RELEASE_CHECKLIST.md`). Workflow doctrine (Process Lock 280426 — Path A/B/C model with key phrase + trigger test), critical safety rules, mandatory first step, Rule 4 (test files), scope/language/git discipline, header canary line (`Tests: N (G gates)`), current focus. | **Gitignored** — internal-only; recovery via external workspace backup (no git history) | Every release (header canary line — manual check, not surfaced by `git status`), behaviour rule changes, current focus shift, workflow-doctrine changes |
| `DOCUMENT_MAP.md` | This file — authoritative map of every file, version sync rules, change scenarios | **Tracked** — ships with repo | New files, new change scenarios, structural changes |

### Documentation (`docs/`)

| File | Contains | Update When |
|------|----------|-------------|
| `README.md` | Overview, quick start, version badge, feature summary | Version bump, new headline features, quick start changes |
| `CHANGELOG.md` | Version-by-version change log | Every release |
| `docs/install.md` | Installation instructions, platform notes, upgrade/uninstall | New dependencies, platform issues, install process changes |
| `docs/cli_reference.md` | Flag tables for all 3 CLIs, recipes, FAQ, pack reference, exit codes | Any flag added/removed/changed, new CLI tool, pack changes |
| `docs/flags.md` | Canonical flag formats, version references, env vars, examples | Any flag added/removed/changed, version bump |
| `docs/rule_language.md` | DSL spec: match/set syntax, operators (`==`, `~`, `in`, `+=`), field reference, CI/CD examples | New operators, new matchable/settable fields, syntax changes |
| `docs/mapping_guide.md` | Map file format, canonical schema, field match/set reference table, bank format examples | New canonical fields, mapping logic changes, new bank formats |
| `docs/amount_synthesis.md` | Debit/credit synthesis logic, edge cases (CR/DR, parentheses, locale) | Changes to `_to_number`, new amount formats supported |
| `docs/i18n_examples.md` | Regional command recipes (US, UK, EU, Swiss), troubleshooting table | New locale support, new flags, new regional formats |
| `docs/workflows.md` | Daily run, growth loop, enterprise integration, CI/CD, rollout checklist, benchmarking | New workflow patterns, new tools, performance changes |
| `docs/growth_loop_best_practices.md` | Discover→Suggest→Merge cycle, time estimates, team tips | Changes to discover/suggest behaviour |
| `docs/benchmarks.md` | Performance data, harness commands, throughput tables, heatmaps | Re-benchmarked (new version, hardware, or significant perf change) |
| `docs/faq.md` | User Q&A: precedence, amounts, encoding, exit codes, performance | New common questions, behaviour changes, fixed bugs |
| `docs/rulepacks.md` | Pack descriptions, pattern lists, commercial pack details (Banking v1.1) | Pack content changes, new packs, pricing changes |
| `docs/api.md` | User-facing HTTP API doc (SOL-041): when-to-use / when-NOT-to-use, request flow diagram, worked example with curl + JSON response, endpoints overview, auth + configuration (env vars), HTTP-status ↔ exit-code mapping, limitations, roadmap, related docs. Voice register matches `workflows.md` / `reconciliation.md`. | New endpoints, new form-field parameters surfaced to users, changes to auth/configuration env vars, exit-code mapping changes |
| `docs/api_reference.md` | Full API reference (SOL-041): form-field tables per endpoint, response schemas (Pydantic shape), HTTP status code mapping, curl recipes for each endpoint, deployment notes (reverse-proxy/TLS caveat), determinism contract section. The technical-reference companion to `docs/api.md`. | New endpoints, form-field changes, response shape changes, new env vars, deployment-pattern documentation |
| `docs/release_notes/release_notes_v0_7_4.md` | v0.7.4 release: what changed, files modified, test counts | Only for that release (new releases get new files) |
| `docs/release_notes/release_notes_v0_7_5.md` | v0.7.5 release: rulepack linter, wildcard hardening, test suite fixes | Only for that release (new releases get new files) |
| `docs/release_notes/release_notes_v0_7_6.md` | v0.7.6 release: rulepack patch, linter fix, cleanroom seal | Only for that release (new releases get new files) |
| `docs/release_notes/release_notes_v0_7_7.md` | v0.7.7 release: `--verify`, CR/DR regex fix, suggest improvements | Only for that release (new releases get new files) |

### Legal (`docs/legal/`)

| File | Contains | Update When |
|------|----------|-------------|
| `docs/legal/compliance_pack.md` | Company details, doc suite summary, privacy/data, licence structure, insurance | Company changes, new legal docs, version in header |
| `docs/legal/privacy.md` | GDPR/ICO privacy policy | Policy changes (rare) |
| `docs/legal/terms.md` | EULA / Terms of Use, dual licence, liability, jurisdiction | Terms changes (rare) |

### Examples (`examples/`)

These files exist in the public repository but do **not** ship in the pip-installed wheel (`MANIFEST.in` only includes `src/finlang/mapping` and `src/finlang/rulepacks`). Doc readers on GitHub can click through; users running locally need to clone the repo or download a release tarball.

| File | Contains | Update When |
|------|----------|-------------|
| `examples/rules.demo.fin` | Pre-existing demo rule file referenced from various docs | When demo rule patterns change |
| `examples/reconcile/demo_reconcile_input.csv` | 15-row corporate treasury input for the SOL-040 reconcile worked example. Mirrors `..\..\test-suite\demo\demo_reconcile_input.csv` (Branch 2 test fixture). | SOL-040 demo data changes |
| `examples/reconcile/demo_reconcile_rules.fin` | Purpose-built minimal ruleset (10 rules incl. "Compliance: Offshore Jurisdictions") for the reconcile worked example. Mirrors test-suite/demo/. | SOL-040 demo ruleset changes |
| `examples/reconcile/demo_reconcile_ml_clean.csv` | Happy-path ML output mirroring FinLang's categories. Mirrors test-suite/demo/. | SOL-040 demo data changes |
| `examples/reconcile/demo_reconcile_ml_mismatches.csv` | Drift-path ML output with deliberate mismatches (SHELL→Utilities, CAYMAN→Treasury Operations). Mirrors test-suite/demo/. | SOL-040 demo data changes |

### Benchmarks (`benchmarks/`)

| File | Contains | Update When |
|------|----------|-------------|
| `benchmarks/bench_finlang_harness.py` | Single-ruleset grid benchmark harness | Benchmark methodology changes |
| `benchmarks/bench_finlang_rulesets.py` | Multi-ruleset comparison harness | Benchmark methodology changes |
| `docs/assets/bench_heatmap*.png` | Heatmap visualisations | Re-benchmarked |

**Benchmark output note:** Harness *scripts* live in `prod\benchmarks\` (tracked, shipped). Benchmark *output* (generated CSVs, run-specific PNGs) goes to `..\..\scratch\benchmarks\v##\`, never into `prod\` or `dev\`. See `..\..\PROJECT_FOLDER_STRUCTURE.md`.

### Tests in prod (`tests/`)

| File | Contains | Update When |
|------|----------|-------------|
| `tests/test_cli_smoke.py` | CLI subprocess smoke tests — runs `finlang` as installed entry point | CLI entry point changes, packaging changes |
| `tests/contracts/conftest.py` | Session-scoped fixture loading `canonical_fields.yaml` | Contract test infrastructure changes |
| `tests/contracts/test_dsl_fields.py` | AST analysis of `CANON_FIELDS_MATCH`/`CANON_FIELDS_SET` against YAML contract | Engine field set changes |
| `tests/contracts/test_engine_input.py` | AST analysis of `engine_cols` list in `run_finlang.py` against `engine_input` contract | CLI engine input contract changes |
| `tests/contracts/test_engine_output.py` | AST analysis of write-back loop in `run_finlang.py` against `engine_output` contract | CLI engine output contract changes |
| `tests/data/drcr.csv` | 2-row debit/credit synthesis test fixture | Synthesis logic changes |
| `tests/data/onecol.csv` | 2-row missing-required-field test fixture | Required field changes |

**Note:** `prod/tests/` only contains the small ship-with-the-repo tests (CLI smoke + AST contracts). The bulk of FinLang's testing lives in `..\..\test-suite\` (sibling folder, internal tooling). See the External Test Suite section below.

---

## Test Suite Repo (`test-suite`) — lives at `{workspace}\test-suite\`

The bulk of FinLang's tests live here as internal validation tooling (not shipped with the PyPI package). `prod\tests\` only contains the small ship-with-the-repo tests (`test_cli_smoke.py` and `tests/contracts/*.py`).

### Process Documents

| File | Contains | Update When |
|------|----------|-------------|
| `TEST_SUITE.md` | Test counts, gate counts, script descriptions, fixture details, expected timings, troubleshooting | New tests added, scripts renamed/added, timing changes, gate changes |

### Test Runners

| File | Contains | Update When |
|------|----------|-------------|
| `quick_check.ps1` | Daily gate runner (10 gates, 137 tests + rulepack linter), single-line-per-gate display. Wall-clock ~100–140s typical post-Gate-10 (varies with cache state, Reconcile gate range ~25–100s observed). | New daily gates, test count changes |
| `full_test_suite.ps1` | All tiers runner (daily + pre-release + contracts) | New tiers, gate changes |
| `cleanroom_test.ps1` | Disposable venv PyPI validation (gates 1-4) | New cleanroom gates, install process changes, **test count strings in header (always)** |
| `run_cleanroom.cmd` | Double-click launcher for cleanroom | Rarely |
| `finlang_showcase.ps1` | Proof-of-life: disposable venv + tests + demo in one recording | New test gates, demo changes, **test count strings in banner + final summary (always)** |
| `finlang_showcase_public.ps1` | Path-masked showcase variant for public recording | New test gates, demo changes, **test count strings in banner + final summary (always)** |
| `run_showcase.cmd` | Double-click launcher for showcase (PyPI install — default; validates published wheel) | Rarely |
| `run_showcase_public.cmd` | Double-click launcher for public showcase (PyPI install + path-masked recording mode) | Rarely |
| `run_showcase_local.cmd` | Double-click launcher for showcase against `{workspace}\prod` local source — pre-release rehearsal mode (NOT a PyPI validation; use only when v0.7.x+1 not yet published). Phase 3 version guard skips if installed FinLang < 0.7.8. | Rarely |

### Test Scripts

| File | Tests | Contains | Update When |
|------|-------|----------|-------------|
| `rulepack_linter.py` | Static (Gate 9) | Static wildcard safety analyser: detects HIGH/WARN risk patterns in `.fin` files without running the engine. Gate 9 in `quick_check.ps1` (bundled packs) and `full_test_suite.ps1` (commercial pack). | Pack content changes, new packs, KNOWN_SAFE_TOKENS changes |
| `smoke_test.ps1` | 13 CLI | Format, pack, i18n smoke tests | New CLI flags, new packs |
| `paranoia_lite.ps1` | (part of gate 2) | Flag, threshold, typo checks | New edge cases |
| `pyarrow_smoke.ps1` | (part of gate 3) | PyArrow/regex fix validation | PyArrow-related changes |
| `test_rule_interactions.py` | 22 engine | Cache invalidation, exclude lifecycle, flag accumulation, audit modes, idempotency | Engine state-transition changes |
| `test_discover_suggest.py` | 22 tool | Discover/suggest pipeline, exclude-aware discovery, fuzzy/exact modes, stopword filter, intra-batch dedup | Discover/suggest behaviour changes |
| `test_rule_correctness.py` | 45 acceptance | Golden-path: categories, flags, structural integrity on known data; _to_number contracts; --dayfirst | Pack content changes, engine output changes |
| `test_custom_map.py` | 8 map pipeline | Custom --map flag: foreign header resolution, debit/credit synthesis, non-ASCII headers, memo mapping, error paths (malformed/partial map), multi-row throughput | Mapping logic changes, new map error paths, canonical schema changes |
| `test_verify.py` | 8 verify | Integrity verification: --verify (fast), --verify-full, --verify-output-dir, tampered output detection | Verification logic or CLI integration changes |
| `test_reconcile.py` | 19 reconcile (Gate 10) | `--reconcile` ML validation: 12 happy/edge tests + 3 validation rejection tests + 1 verify+reconcile coexistence regression + 1 memo-enrichment dict assertion + 1 HTML render+escape end-to-end + 1 dual-flag validation. Subprocess-based plus 2 module-level direct-API tests (tampered coexistence, memo dict). Wall-clock ~25–100s. | Reconcile logic changes, CLI argparse changes, new validation rules, new exit-code paths, mismatch dict shape changes, HTML report format changes |
| `test_api.py` | 15 API (standalone gate — NOT part of `quick_check.ps1`'s 137/10) | SOL-041 FastAPI wrapper integration tests via `fastapi.testclient.TestClient`: health, root, `/process` (rules + include_pack + verify + validation), `/discover` (default `return_all=False` path), `/suggest`, `/reconcile` (perfect match, mismatches → 200, HTML emission), CLI/API reconcile parity contract, auth gating. Run via `python -m pytest test_api.py -v` from `test-suite/` with `pip install -e ../prod[api]` + `pip install httpx` in `.venv-quickcheck`. Wall-clock ~22s. | New API endpoints, form-field changes, response-shape changes, auth behaviour changes, exit-code mapping changes |
| `run_test_matrix.ps1` | 6 golden masters | SHA256 baselines for US/UK/EU/debit/pipe/CR-DR formats | New regional formats, output changes |
| `adversarial_tests.ps1` | 8 edge cases | Mixed delimiters, duplicate headers, CR/DR, pipe delimiter, scientific notation | New edge case support |
| `integrity_testv2.py` | Scale integrity | SHA-256 fingerprinting at 5K-20M rows | Changes to data hardening or amount normalisation |
| `validate_sandbox_port.py` | Port validation | Targeted validation for sandbox-to-production ports — proves specific changes landed correctly, independent of full suite | Port procedure changes |

### Test Support Files

| File | Purpose | Update When |
|------|---------|-------------|
| `rules.demo.fin` | Shared rules for smoke/matrix tests | When test expectations change |
| `bank.map.json` | Standard header mapping for tests | When mapping logic changes |
| `test_eu_map.json` | German header mapping (datum, beschreibung, betrag) | When EU test fixtures change |
| `test_us.csv`, `test_uk.csv`, `test_eu.csv` | Regional baseline CSVs | When test matrix changes |
| `eu_cr_dr.csv` | CR/DR suffix test data | When CR/DR handling changes |
| `debit_only.csv` | Debit/credit synthesis test | When synthesis logic changes |
| `pipe_quotes.csv` | Pipe delimiter edge case | When delimiter handling changes |
| `cp1252_weird.csv` | Windows-1252 encoding edge case | When encoding handling changes |
| `demo_corporate_transactions.csv` | Copy of demo CSV (used by some tests) | When demo data changes |
| `demo_corporate_transactions.fin` | Copy of demo rules (used by some tests) | When demo rules change |
| `golden/*.sha256` | SHA256 baselines for matrix verification | After any engine output change (regenerate via `WriteGolden`) |

### Generated / Transient (do not commit, do not track)

| Path | Contents | Notes |
|------|----------|-------|
| `_archive/` | Deprecated/archived scripts (incl. `finlang_demo_v3.ps1`) | Reference only |
| `_screenshot proofs/` | Integrity test proof screenshots (JPGs) | Evidence only, not functional |
| `gen/` | Adversarial test fixtures/outputs | Overwritten each run |
| `test_out/` | Matrix test CSV/JSON outputs | Overwritten each run |

---

## Demo Files

The demo script lives in the **test suite root** (`test-suite/finlang_demo_v4.ps1`).
Demo data files live in the **demo subfolder** (`test-suite/demo/`).

### Demo Script (test suite root)

| File | Purpose | Update When |
|------|---------|-------------|
| `finlang_demo_v4.ps1` | Live demo script (9 steps, spacebar-driven) | Demo flow changes, new demo features |

### Demo Data (`./demo`)

| File | Purpose | Update When |
|------|---------|-------------|
| `demo_corporate_transactions.csv` | 58 corporate treasury transactions | Demo data changes (rare) |
| `demo_corporate_transactions.fin` | 37 rules (energy, banking, fleet, tech, professional services) | Demo rule changes |
| `demo_uk_transactions.csv` | 8 UK format transactions (DD/MM/YYYY) | i18n demo changes |
| `demo_us_transactions.csv` | 8 US format transactions (MM/DD/YYYY) | i18n demo changes |
| `demo_eu_transactions.csv` | 8 EU format transactions (semicolons, comma decimals, € symbols) | i18n demo changes |
| `demo_eu_transactions_de.csv` | 8 German header transactions (datum, betrag, beschreibung, vermerk) | i18n demo changes |
| `demo_de.map.json` | German → canonical mapping | When German demo data changes |
| `demo_reconcile_input.csv` | 15 corporate treasury transactions including the spec's killer CAYMAN ISLANDS TRUST row. Paired with `demo_reconcile_rules.fin` for the SOL-040 reconcile demo. | SOL-040 demo data changes |
| `demo_reconcile_rules.fin` | Purpose-built minimal ruleset (10 rules) for the reconcile demo. Includes "Compliance: Offshore Jurisdictions" listed first for narration prominence. NOT a fork of `demo_corporate_transactions.fin`. | SOL-040 demo ruleset changes |
| `demo_reconcile_ml_clean.csv` | Happy-path ML output: 15 rows, categories mirror FinLang's output exactly. Used to demonstrate exit 0 / status PASS. | SOL-040 demo data changes |
| `demo_reconcile_ml_mismatches.csv` | Drift-path ML output: 15 rows with 2 deliberate mismatches — SHELL TRADING (ML "Utilities" vs FinLang "Energy & Commodities") and the killer CAYMAN ISLANDS TRUST (ML "Treasury Operations" vs FinLang "Compliance: Offshore Jurisdictions"). Demonstrates exit 3 / status REVIEW REQUIRED. | SOL-040 demo data changes |

---

## Top-Level Workspace Documents — live at `{workspace}\`

These sit one level above `prod\` and span multiple subdirectories. They are workspace governance, not part of the published repo.

| File | Purpose | Update When |
|------|---------|-------------|
| `..\..\CLAUDE.md` | Top-level project orientation — visitor map, single-tree workspace model summary (post-consolidation 27 April 2026, post-Process-Lock 28 April 2026), where to find what | Project structure changes, new top-level files |
| `..\..\PROJECT_FOLDER_STRUCTURE.md` | Single-tree folder pattern (post-consolidation 27 April 2026), operational rules, two-CLAUDE.md single-tree variant, solo-maintainer trunk workflow as reasoned deviation (Process Lock 280426, 28 April 2026 — single `origin` remote with augmented pre-push hook blocking non-`main`/non-tag pushes; Layer 4 retracted with conditional reinstatement triggers; release gate as target state) | Structure changes, new operational rules, deviation status changes |
| `..\strategy-backlog\BACKLOG.md` | Tactical project backlog (Now / Next / Later / Done). Canonical source for in-flight work. | When items move between horizons, are shipped, or new items land |
| `..\strategy-backlog\ROADMAP.md` | Living strategic roadmap. Quarterly horizons + exit calibration. | On strategic shifts, portfolio rebalances |
| `..\strategy-backlog\SANDBOX_PARKING_LOT_ARCHIVED.md` | **Archived** 21 April 2026. Historical engineering backlog from v0.7.7 cycle. Not maintained — see BACKLOG.md for current work. | Never (archived) |
| `..\..\scratch\archive\RELEASE_PREFLIGHT_SPEC-pre-consolidation-20260427.md` | Pre-consolidation release-preflight spec (archived 27 April — content described retired infrastructure). Active release-gate spec lives at `angus-os/engineering/DRAFT-release-gate-package-v1.md`. | Reference only — superseded |
| `..\..\ANGUS_OS_CANDIDATES.md` | Curated list of FinLang process & discipline files that are candidates for lifting into angus-os. Filtered, not a complete inventory. | When angus-os scaffolding evolves, when new top-level discipline files are added |
| `..\..\ANGUS_OS_ENGINEERING_CANDIDATES.md` | Curated list of FinLang engineering patterns (source layout, test contracts, CI templates, workspace patterns) that are candidates for lifting into angus-os. Filtered, not a complete code inventory. | When angus-os scaffolding evolves, when new transferable patterns emerge |

---

## Strategic / Planning Documents

> **Note on date-versioned files:** Some planning docs use a date-appended naming pattern (`<filename>_<DDMMYY>.md`). The most recent dated copy is always the active version. Older copies are historical reference, not actively maintained. Current versions are tracked in the **Current Versions** table below.

> **Note on accessibility:** Strategic docs live in `..\strategy-backlog\` (workspace-readable) since the 21 April 2026 reorganisation. Historical Drive-hosted versions exist for some items but are no longer the canonical source. **No Drive-only files remain.** The demo-video narration script (`..\test-suite\showcase_narration_script.md`) is on disk but is a historical artifact from the pre-v0.7.7 recording — no longer maintained, no longer count-swept.

### Current Versions
| Pattern | Current Version | Last Updated |
|---------|-----------------|--------------|
| Living roadmap | `..\strategy-backlog\ROADMAP.md` | 21 Apr 2026 |
| Frozen roadmap snapshot | `..\strategy-backlog\ROADMAP-detailed-110426.md` | 11 Apr 2026 |
| Solution outlines (archived) | `..\strategy-backlog\archive\SOLUTIONS_ARCHIVED_040426.md` | 4 Apr 2026 (archived; SOL-040 + future SOL-041 are standalone specs in `..\strategy-backlog\`) |
| Engineering parking lot (archived) | `..\strategy-backlog\SANDBOX_PARKING_LOT_ARCHIVED.md` | 21 Apr 2026 (archived; current work in BACKLOG.md) |

### File Catalog
| File | Contains | Update When |
|------|----------|-------------|
| `..\strategy-backlog\BACKLOG.md` | Tactical Now / Next / Later / Done items | Items ship, new items land, horizons shift |
| `..\strategy-backlog\ROADMAP.md` | Living strategic narrative | Strategic shifts, portfolio rebalances |
| `..\strategy-backlog\ROADMAP-detailed-110426.md` | Frozen 11 Apr 2026 detailed snapshot | Never (frozen) |
| `..\strategy-backlog\archive\SOLUTIONS_ARCHIVED_040426.md` | SOL-001 through SOL-039 historical specs | Never (archived) |
| `..\strategy-backlog\SANDBOX_PARKING_LOT_ARCHIVED.md` | v0.7.7 parking-lot items with mapping to current BACKLOG | Never (archived) |
| `..\strategy-backlog\SOL-040_reconcile_specification.md` | `--reconcile` feature spec (think tank reviewed) | Spec changes, post-implementation review |
| `..\strategy-backlog\finlang-post-acquisition-roadmap.md` | Post-acquisition product/platform roadmap | Strategic discussions about post-exit phase |
| `..\strategy-backlog\archive\roadmap_timeline_050426.mermaid` | Pre-16-April visual roadmap timeline (archived) | Never (archived) |
| `..\strategy-backlog\finlang_vertical_analysis.md` | Vertical expansion analysis (procurement, healthcare, insurance) + arbitrary column matching spec | When vertical strategy changes or engine modification is built |
| `..\strategy-backlog\FinLang_Pricing.html` | Pricing model artefact | When pricing model is revised |
| `..\strategy-backlog\PitchDeck-April 2026.pptm` | April 2026 pitch deck | When deck is revised for new audience or strategic reframe |
| `..\test-suite\showcase_narration_script.md` | Voiceover lines mapped to every spacebar press in the pre-v0.7.7 showcase recording. **Historical artifact** — demo is recorded, script reflects that prior state. No longer count-swept, no longer maintained. | Never (historical) |

*(Note: `SANDBOX_PORT_PROCEDURE.md` and `demo_video_pack.md` were referenced in earlier versions of this catalog. Sandbox port is moot post-consolidation; demo_video_pack was Drive-historical. Both removed from the catalog.)*

---

## Common Change Scenarios → Files to Touch

| Scenario | Files to Update |
|----------|----------------|
| **New CLI flag** | `run_finlang.py` (argparse), `cli_reference.md`, `flags.md`, `--help` auto-updates, smoke tests if testable |
| **New discover/suggest flag** | `discover.py` or `suggest.py` (argparse), `cli_reference.md`, `flags.md`, `test_discover_suggest.py` if testable |
| **New canonical field** | `finlang_engine.py` (CANON_FIELDS), `mapping_guide.md` (field table), `rule_language.md` (field reference), `canonical_fields.yaml`, `test_rule_interactions.py` |
| **New rule operator** | `finlang_engine.py` (parser + evaluator), `rule_language.md`, possibly `test_rule_interactions.py` |
| **Version bump** | `__init__.py`, `pyproject.toml`, `run_finlang.py` fallback, `canonical_fields.yaml`, `prod/CLAUDE.md` (header canary — **gitignored** since 1 May 2026; check manually because `git status` won't surface it), `CHANGELOG.md`, release notes, doc `Last verified:` headers, `compliance_pack.md` header |
| **New test added** | Test script (in `..\..\test-suite\` for behavioural, `tests\contracts\` for AST), `TEST_SUITE.md` (counts, descriptions), `quick_check.ps1` and `full_test_suite.ps1` (counts always; orchestration only if new gate — gate addition needs explicit human approval per `prod\CLAUDE.md` Rule 4), `cleanroom_test.ps1` (counts in header — always; rename to `cleanroom_pypi.ps1` is planned as Phase 3 follow-on), `finlang_showcase.ps1` and `finlang_showcase_public.ps1` (counts in banner + final summary — always), `RELEASE_CHECKLIST.md` (counts in quick reference table — gitignored), `DOCUMENT_MAP.md` (test scripts table), `README.md` (if test counts mentioned), `prod/CLAUDE.md` (header canary line — **gitignored** since 1 May 2026; check manually, `git status` won't surface it). (`showcase_narration_script.md` is no longer count-swept — historical artifact from pre-v0.7.7 demo recording.) |
| **Pack content change** | Rulepack `.fin` file, `rulepacks.md`, `test_rule_correctness.py` (tightly coupled), golden baselines (regenerate), re-run `rulepack_linter.py` to verify clean |
| **Rulepack wildcard change** | `rulepack_linter.py` (re-run to verify clean — exit 0 required before commit), `KNOWN_SAFE_TOKENS` if new safe token needed |
| **Amount parsing change** | `run_finlang.py` (`_to_number`), `discover.py` (`_to_number` synced copy), `verify.py` (`_normalize_amount_string` synced copy), `amount_synthesis.md`, `i18n_examples.md`, adversarial tests, integrity test |
| **Benchmark re-run** | `benchmarks.md`, heatmap PNGs, `workflows.md` (throughput table). Output goes to `..\..\scratch\benchmarks\v##\`, never into `prod\` or `dev\`. |
| **New demo step** | `finlang_demo_v4.ps1`, possibly new CSV/map files in demo folder |
| **New regional format** | Test CSV, `run_test_matrix.ps1` (new case), golden baselines, `i18n_examples.md`, possibly `mapping_guide.md` |
| **Working contract change** (CC behaviour rules, current focus, etc) | `prod\CLAUDE.md` (**gitignored** since 1 May 2026 — no commits to gate, but the editing discipline from `prod\CLAUDE.md` § "Workflow doctrine" still applies: Angus-driven typo/clarification edits go directly; CC-authored or substantive rewrites get diff-reviewed before save) |

---

## Sync Rules

1. **`_to_number` exists in two places** — `run_finlang.py` and `discover.py`. Changes must be synced manually.
2. **`--help` is auto-generated** from argparse. No separate help file to maintain. Verify against docs on release.
3. **Golden baselines** must be regenerated (`WriteGolden`) after any change that affects CSV output format.
4. **Pack changes break `test_rule_correctness.py`** by design — it's tightly coupled to pack content.
5. **Legal docs have own versioning** — don't bump during routine releases unless content actually changes.
6. **Benchmark docs only update when re-benchmarked** — don't update version headers unless data is re-validated.
7. **`_normalize_amount_string` in `verify.py` mirrors `_to_number` logic** — keep synced on amount parsing changes.
8. **Count sweep is unconditional** for `cleanroom_test.ps1`, `finlang_showcase.ps1`, and `finlang_showcase_public.ps1` — these were the most-missed files during the v0.7.7 release. The old "if count strings hardcoded" qualifier was the loophole that caused them to be missed. They always have hardcoded counts.
9. **`prod\CLAUDE.md` is gitignored** (1 May 2026) — same pattern as `RELEASE_CHECKLIST.md`. The working contract lives in `prod\` for path coherence and is read by every CC session, but does not ship in public git history. Recovery relies on external workspace backup. The Path A/B/C branch model from Process Lock 280426 doesn't mechanically apply (no commits to gate), but the editing discipline does: Angus-driven trivial edits go directly; CC-authored or substantive rewrites get diff-reviewed before save. The pre-consolidation canonical-source-mirror pattern remains retired.
10. **Internal process files in `prod\` are gitignored**, not committed. Currently applies to `RELEASE_CHECKLIST.md` and `prod\CLAUDE.md` (and any future maintainer-only tooling). They live in `prod\` for path coherence but don't ship. The `prod\.gitignore` lists each filename explicitly.
11. **Internal process file snapshots live in `..\..\scratch\internal_snapshots\v##\`** — one folder per release, containing `RELEASE_CHECKLIST.md` (and any other gitignored maintainer-only tooling) as of that release. Written as part of release Phase 8 of `release-promotion-package.md`. Not tracked by git (scratch is disposable) but preserved via external workspace backup for version archaeology. Recovery mechanism for the gitignored-internal-tooling pattern (Rule 6 corollary in folder-structure-package).
12. **`reconcile.py` ↔ `run_finlang.py` argparse coupling** (SOL-040, v0.7.8) — the four reconcile flags (`--reconcile`, `--reconcile-fields`, `--reconcile-output-dir`, `--reconcile-html`) are declared in `run_finlang.py` argparse and consumed by `run_reconciliation()` in `reconcile.py`. New reconcile flags require coordinated edits in both files: argparse declaration + validation block + post-engine hook call in `run_finlang.py`; signature parameter in `run_reconciliation()` and downstream comparison/report logic in `reconcile.py`. The post-engine hook also coexists with `--verify` via the `post_engine_failure` flag pattern — both report independently per spec §3 line 201; do not regress to immediate `sys.exit(3)` on either side. `--reconcile-html` requires both `--reconcile` and `--reconcile-output-dir` (Branch 3 thinktank-mandated dual validation); when set, `reconcile.py` lazy-imports `reconcile_html.generate_html_report()` and writes `reconcile_report.html` alongside the JSON+CSV artefacts.
13. **`examples/reconcile/` mirrors `..\..\test-suite\demo\` reconcile fixtures** (SOL-040, v0.7.8) — four files exist in both locations as parallel sets: `demo_reconcile_input.csv`, `demo_reconcile_rules.fin`, `demo_reconcile_ml_clean.csv`, `demo_reconcile_ml_mismatches.csv`. Different purposes: `examples/reconcile/` is doc-facing (referenced from `docs/reconciliation.md` worked example, GitHub-readable, in the public repo); `test-suite/demo/` is test-fixture-facing (consumed by `test_reconcile.py` if added in future, locked per Rule 4 "modifying existing truth-fixture contents requires explicit approval"). On any change to one set, sync the other manually or surface deliberate divergence. Test fixtures are locked under Rule 4; doc-facing examples are not — but they describe the same scenario in v0.7.8.

---

## Historical: 12 April 2026 dev/prod restructure

> **This section documents the 12 April 2026 dev/prod restructure, which was retired in the 27 April 2026 single-env consolidation. Preserved as historical reference. For the current model see post-consolidation notes above and `..\PROJECT_FOLDER_STRUCTURE.md`.**
>
> *Section cleaned 27 April 2026 — previously contained corruption artifacts from a search-and-replace operation during post-consolidation sanitization. Restored to original pre-consolidation terms (Phase 12, dev_CLAUDE.md, etc.) inside this clearly-marked historical context.*

This document was updated as part of the dev/prod workspace restructure. Key changes from the 11 April version:

- Header date updated, v0.7.7 baseline reaffirmed
- Restructure context note added below title
- **`dev_CLAUDE.md` persistence model documented** — canonical source at `prod\dev_CLAUDE.md` (gitignored), restored to `dev\CLAUDE.md` by Phase 12.5a `Move-Item` rename after robocopy refresh
- **`dev_CLAUDE.md` and `RELEASE_CHECKLIST.md` flagged as gitignored throughout** — both were internal maintainer tooling, lived in `prod\` for path coherence but never shipped. Sync Rule 10 covered the general principle.
- Version Sync Rule expanded to 5 files (added `dev_CLAUDE.md` header canary, with gitignored-on-disk note)
- New "Internal Process Files" subsection under Source Repo for `RELEASE_CHECKLIST.md`, `dev_CLAUDE.md`, and `DOCUMENT_MAP.md` with explicit visibility column
- "Source Repo" and "Test Suite Repo" headers annotated with new absolute paths
- Test Runners section: `cleanroom_test.ps1`, `finlang_showcase.ps1` counts marked as unconditional; `finlang_showcase_public.ps1` and `run_showcase_public.cmd` added
- Test Scripts section: `test_custom_map.py`, `test_verify.py`, `validate_sandbox_port.py` added (were present in 11 April scan but missing from that version of this doc)
- Release notes section: v0.7.6 and v0.7.7 entries added
- Benchmark output note added (scripts ship, output goes to scratch)
- New "Top-Level Workspace Documents" section for files at `{workspace}\` (above prod), referencing the renamed `ANGUS_OS_*_CANDIDATES.md` files
- New "Sandbox-only mirror" subsection clarifying `dev\CLAUDE.md` was mirror, not source (subsection itself retired in 27 April consolidation)
- Strategic / Planning Documents section: accessibility note added (was Drive-only at the time; strategic docs migrated into `strategy-backlog\` on 21 April 2026); `showcase_narration_script.md` flagged as human-managed
- "New test added" row rewritten: removed the "if count strings hardcoded" qualifier; added `finlang_showcase_public.ps1`, `README.md`, `dev_CLAUDE.md` (with gitignored note); added note that gate addition requires explicit human approval per Rule 4
- "Version bump" row updated to include `dev_CLAUDE.md` header canary with gitignored note
- New "Sandbox contract change" row pointing all edits at `prod\dev_CLAUDE.md` (gitignored)
- Sync Rule 8 added (unconditional count sweep)
- Sync Rule 9 added (mirror file sourced from gitignored canonical in prod)
- Sync Rule 10 added (internal process files gitignored, robocopy is filesystem-level)
- **Sync Rule 11 added** (13 April 2026): internal process file snapshots live in `scratch\internal_snapshots\v##\`, written by Phase 12 step 12.0a. Closes the recoverability gap identified by the thinktank review of the gitignore decision.

> **Post-consolidation status (27 April 2026):** Phase 12, robocopy refresh, dev/prod folder split, `dev_CLAUDE.md` mirror pattern, and Sync Rules 9-10 (in their pre-consolidation form) are all retired. Sync Rule 11 partially survives — internal-snapshot-on-release pattern continues for `RELEASE_CHECKLIST.md` only. See current Sync Rules 9-11 in the "Sync Rules" section above for post-consolidation form.

---

© FinLang Ltd
