# FinLang Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

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
- Deep audit verification confirming deterministic, “machine-grade” operation.

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