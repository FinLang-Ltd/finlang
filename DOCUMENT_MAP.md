# FinLang Document Map
*Last updated: 8 March 2026 | v0.7.5*

This document is the authoritative map of the FinLang codebase, documentation, testing infrastructure, and demo environment. It exists to ensure that changes to the system update the correct files, tests, and documentation consistently. This document should be updated whenever new files, tests, or major documentation are introduced.

### Version Sync Rule
Version numbers must remain consistent across these five files on every release:
`__init__.py`, `pyproject.toml`, `run_finlang.py` (fallback), `canonical_fields.yaml`, `CHANGELOG.md`

---

## System Architecture Overview

FinLang consists of five major components:

1. **Engine** — Rule parsing and deterministic execution (`finlang_engine.py`)
2. **CLI Interface** — Argument parsing, data hardening, and orchestration (`run_finlang.py`)
3. **Tools** — Discovery and rule generation (`discover.py`, `suggest.py`)
4. **Documentation & Rulepacks** — DSL specification, bundled categorisation packs, and user guides
5. **Validation Infrastructure** — 81-test daily suite + rulepack linter, integrity verification, cleanroom PyPI validation, golden master baselines

---

## Source Repo (`finlang`)

### Core Source Files

| File | Contains | Update When |
|------|----------|-------------|
| `src/finlang/__init__.py` | `__version__` string | Version bump |
| `pyproject.toml` | Package version, dependencies, entry points | Version bump, new dependency, new CLI entry point |
| `src/finlang/cli/run_finlang.py` | Main CLI: argparse flags, data hardening (`_to_number`, `_CURRENCY_NBSP_RE`), header mapping, engine orchestration, fallback `__version__` | New/changed CLI flags, new amount formats, mapping logic changes, version bump |
| `src/finlang/engine/finlang_engine.py` | Rule parser, condition/action evaluator, `CANON_FIELDS_MATCH`/`CANON_FIELDS_SET`, `TEXT_COLS`, wildcard/range matching | New operators, new matchable/settable fields, rule syntax changes |
| `src/finlang/tools/discover.py` | Discovery tool: argparse, `_to_number` (synced copy), candidate extraction, exclude-aware filtering | New discover flags, changes to amount parsing, exclude logic changes |
| `src/finlang/tools/suggest.py` | Rule generator: fuzzy/exact modes, dedup, quote styles, append/overwrite | New suggest flags, output format changes |
| `src/finlang/mapping/bank.map.json` | Default header mapping (date, counterparty, memo, amount with aliases + debit/credit) | New bank format support |
| `src/finlang/rulepacks/*.fin` | 8 bundled packs: retail, transport, subs, travel, financial, compliance, sanity, examples | Pack content changes, new packs added |
| `src/finlang/utils/resources.py` | Package resource loading helpers | Structural changes to pack/map loading |
| `tests/contracts/canonical_fields.yaml` | Version string, engine input/output field lists for AST contract tests | Version bump, new canonical fields |

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
| `docs/release_notes/release_notes_v0_7_4.md` | v0.7.4 release: what changed, files modified, test counts | Only for that release (new releases get new files) |
| `docs/release_notes/release_notes_v0_7_5.md` | v0.7.5 release: rulepack linter, wildcard hardening, test suite fixes | Only for that release (new releases get new files) |

### Legal (`docs/legal/`)

| File | Contains | Update When |
|------|----------|-------------|
| `docs/legal/compliance_pack.md` | Company details, doc suite summary, privacy/data, licence structure, insurance | Company changes, new legal docs, version in header |
| `docs/legal/privacy.md` | GDPR/ICO privacy policy | Policy changes (rare) |
| `docs/legal/terms.md` | EULA / Terms of Use, dual licence, liability, jurisdiction | Terms changes (rare) |

### Benchmarks (`benchmarks/`)

| File | Contains | Update When |
|------|----------|-------------|
| `benchmarks/bench_finlang_harness.py` | Single-ruleset grid benchmark harness | Benchmark methodology changes |
| `benchmarks/bench_finlang_rulesets.py` | Multi-ruleset comparison harness | Benchmark methodology changes |
| `docs/assets/bench_heatmap*.png` | Heatmap visualisations | Re-benchmarked |

---

## Test Suite Repo (`finlang-test_suite`)

### Process Documents

| File | Contains | Update When |
|------|----------|-------------|
| `TEST_SUITE.md` | Test counts, gate counts, script descriptions, fixture details, expected timings, troubleshooting | New tests added, scripts renamed/added, timing changes, gate changes |
| `RELEASE_CHECKLIST.md` | Step-by-step release process, version bump locations, test commands, quick reference table | New release steps, new version bump locations, test process changes |

### Test Runners

| File | Contains | Update When |
|------|----------|-------------|
| `quick_check.ps1` | Daily gate runner (7 gates, 81 tests + rulepack linter), single-line-per-gate display | New daily gates, test count changes |
| `full_test_suite.ps1` | All tiers runner (daily + pre-release + contracts) | New tiers, gate changes |
| `cleanroom_test.ps1` | Disposable venv PyPI validation (gates 1-4) | New cleanroom gates, install process changes |
| `run_cleanroom.cmd` | Double-click launcher for cleanroom | Rarely |
| `finlang_showcase.ps1` | Proof-of-life: disposable venv + tests + demo in one recording | New test gates, demo changes |
| `run_showcase.cmd` | Double-click launcher for showcase | Rarely |

### Test Scripts

| File | Tests | Contains | Update When |
|------|-------|----------|-------------|
| `rulepack_linter.py` | Static | Static wildcard safety analyser: detects HIGH/WARN risk patterns in `.fin` files without running the engine. Gate 7 in `quick_check.ps1` (bundled packs) and `full_test_suite.ps1` (commercial pack). | Pack content changes, new packs, KNOWN_SAFE_TOKENS changes |
| `smoke_test.ps1` | 13 CLI | Format, pack, i18n smoke tests | New CLI flags, new packs |
| `paranoia_lite.ps1` | (part of gate 2) | Flag, threshold, typo checks | New edge cases |
| `pyarrow_smoke.ps1` | (part of gate 3) | PyArrow/regex fix validation | PyArrow-related changes |
| `test_rule_interactions.py` | 22 engine | Cache invalidation, exclude lifecycle, flag accumulation, audit modes, idempotency | Engine state-transition changes |
| `test_discover_suggest.py` | 20 tool | Discover/suggest pipeline, exclude-aware discovery, fuzzy/exact modes | Discover/suggest behaviour changes |
| `test_rule_correctness.py` | 26 acceptance | Golden-path: categories, flags, structural integrity on known data | Pack content changes, engine output changes |
| `run_test_matrix.ps1` | 6 golden masters | SHA256 baselines for US/UK/EU/debit/pipe/CR-DR formats | New regional formats, output changes |
| `adversarial_tests.ps1` | 8 edge cases | Mixed delimiters, duplicate headers, CR/DR, pipe delimiter, scientific notation | New edge case support |
| `integrity_testv2.py` | Scale integrity | SHA-256 fingerprinting at 5K-20M rows | Changes to data hardening or amount normalisation |

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

The demo script lives in the **test suite root** (`finlang-test_suite/finlang_demo_v4.ps1`).
Demo data files live in the **demo subfolder** (`finlang-test_suite/demo/`).

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

---

## Strategic / Planning Documents

| File | Contains | Update When |
|------|----------|-------------|
| `ROADMAP_verify.md` | `finlang --verify` design spec (future feature) | When verify feature is built |
| `demo_video_pack.md` | Video recording plan and script notes | Before recording demo video |
| `showcase_narration_script.md` | Voiceover lines mapped to every spacebar press in showcase | Before recording showcase video |
| `finlang_consolidated_roadmap_draft.md` | v0.7.5+ roadmap items (decimal pipeline, streaming audit, GUI builder, SOL-001) | Roadmap review sessions |
| `finlang_solution_outlines.md` | Solution outlines for enterprise use cases | New vertical/use case work |
| `finlang_vertical_analysis.md` | Vertical expansion analysis (procurement, healthcare, insurance) + arbitrary column matching spec | When vertical strategy changes or engine modification is built |

---

## Common Change Scenarios → Files to Touch

| Scenario | Files to Update |
|----------|----------------|
| **New CLI flag** | `run_finlang.py` (argparse), `cli_reference.md`, `flags.md`, `--help` auto-updates, smoke tests if testable |
| **New discover/suggest flag** | `discover.py` or `suggest.py` (argparse), `cli_reference.md`, `flags.md`, `test_discover_suggest.py` if testable |
| **New canonical field** | `finlang_engine.py` (CANON_FIELDS), `mapping_guide.md` (field table), `rule_language.md` (field reference), `canonical_fields.yaml`, `test_rule_interactions.py` |
| **New rule operator** | `finlang_engine.py` (parser + evaluator), `rule_language.md`, possibly `test_rule_interactions.py` |
| **Version bump** | `__init__.py`, `pyproject.toml`, `run_finlang.py` fallback, `canonical_fields.yaml`, `CHANGELOG.md`, release notes, doc `Last verified:` headers, `compliance_pack.md` header |
| **New test added** | Test script, `TEST_SUITE.md` (counts, descriptions), `quick_check.ps1` or `full_test_suite.ps1` (if new gate), `RELEASE_CHECKLIST.md` (counts) |
| **Pack content change** | Rulepack `.fin` file, `rulepacks.md`, `test_rule_correctness.py` (tightly coupled), golden baselines (regenerate), re-run `rulepack_linter.py` to verify clean |
| **Rulepack wildcard change** | `rulepack_linter.py` (re-run to verify clean — exit 0 required before commit), `KNOWN_SAFE_TOKENS` if new safe token needed |
| **Amount parsing change** | `run_finlang.py` (`_to_number`), `discover.py` (`_to_number` synced copy), `amount_synthesis.md`, `i18n_examples.md`, adversarial tests, integrity test |
| **Benchmark re-run** | `benchmarks.md`, heatmap PNGs, `workflows.md` (throughput table) |
| **New demo step** | `finlang_demo_v4.ps1`, possibly new CSV/map files in demo folder |
| **New regional format** | Test CSV, `run_test_matrix.ps1` (new case), golden baselines, `i18n_examples.md`, possibly `mapping_guide.md` |

---

## Sync Rules

1. **`_to_number` exists in two places** — `run_finlang.py` and `discover.py`. Changes must be synced manually.
2. **`--help` is auto-generated** from argparse. No separate help file to maintain. Verify against docs on release.
3. **Golden baselines** must be regenerated (`WriteGolden`) after any change that affects CSV output format.
4. **Pack changes break `test_rule_correctness.py`** by design — it's tightly coupled to pack content.
5. **Legal docs have own versioning** — don't bump during routine releases unless content actually changes.
6. **Benchmark docs only update when re-benchmarked** — don't update version headers unless data is re-validated.

---

© FinLang Ltd
