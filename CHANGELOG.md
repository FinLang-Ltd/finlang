# FinLang Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

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