# FinLang Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
