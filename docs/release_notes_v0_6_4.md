# 🧾 FinLang v0.6.4.post1 – GA Release Notes
*Released November 2025 (Rev 2)*

This release marks the **General Availability (GA)** milestone of FinLang — the deterministic, auditable financial rules engine.  
It completes the v0.6.x cycle with hardened I/O, full internationalization (I18n), and industrial-grade validation.

---

## 🔹 Highlights

| Category | Description |
|-----------|--------------|
| **I18n & Locale Control** | Added full regional parsing flags: `--decimal`, `--thousands`, `--dayfirst`, `--date-format`, and `--encoding auto`. |
| **Strictness & Validation** | New `--strict-parse` and `--fail-threshold` ensure schema and delimiter integrity with drop-rate protection. |
| **Audit & Performance** | **Full audit tracking (state diffs) introduced with characterized overhead (≈38% throughput reduction).** Sustained throughput **≈ 24 k rows/s @ 5 M × 50 cols**. |
| **Discover & Suggest Enhancements** | Added `--emit-match {fuzzy,exact}` for **safer, 1:1 rule generation** and `--quote-style` for formatting. |
| **CLI Improvements** | Auto-encoding detection, safe text guard (`FINLANG_SAFE_TEXT`), and refined Fast I/O mode. |
| **Documentation** | Full rewrite of install, CLI, and FAQ; new guides for growth loop, amount synthesis, I18n, and deterministic design. |

---

## 🔹 Changelog Summary

### Added
- `--strict-parse`, `--fail-threshold`, `--encoding`, `--decimal`, `--thousands`, `--dayfirst`, `--date-format`, `--output-encoding`
- `FINLANG_SAFE_TEXT`, `FINLANG_AUDIT_MODE`, `FINLANG_AUDIT_MAX` env vars

### Improved
- Hardened `_read_csv_hardened()` with delimiter auto-detection
- CR/DR localization in `_to_number`
- Audit vectorization and capped logging

### Fixed
- Rare encoding fallback bug (Latin-1 detection)
- Audit JSON schema validation mismatch
- Windows UTF-8 console output (via `chcp 65001` guidance)

---

### ⚠️ Known Issues
- **None.**
All exit code behaviors regarding `--fail-threshold` and I/O write failures were resolved in **v0.6.4.post2**. This release is fully validated for interactive and CI/CD use.


---

## 🔄 Upgrading from v0.6.3 or Earlier

### Breaking Changes
**None.** v0.6.4 is fully backward compatible.

### New Recommended Flags
```bash
# Old (still works)
finlang --input data.csv --output out.csv --rules rules.fin

# New (recommended - adds validation)
finlang --input data.csv --output out.csv --rules rules.fin   --strict-parse --encoding auto --fastio
```

### 📊 Audit Mode Changes
v0.6.4 improves audit output to show **actual changes** (before/after state):

**Old format (v0.6.3):**
```json
{"index": 1, "rule": "Transport: Uber"}
```

**New format (v0.6.4):**
```json
{
  "index": 1,
  "rule": "Transport: Uber",
  "changes": {
    "category": {"old": null, "new": "Transport"}
  }
}
```

**Migration:** Regenerate golden test files if using audit-based validation.

---

## 🔹 Compatibility

- **Python:** 3.10 – 3.12  
- **OS:** Windows 11, macOS (M-series & Intel), Linux  
- **Dependency:** PyArrow ≥ 16.0 (optional)

---

## 📖 Related Documentation

- [CLI Reference](cli_reference.md) – Complete flag listing  
- [FAQ](faq.md) – Common questions  
- [Benchmarks](benchmarks.md) – Performance data  
- [Workflows](workflows.md) – Integration patterns  
- [i18n Examples](i18n_examples.md) – Regional settings  
- [Stateless Processing](stateless_processing.md) – Architecture

© FinLang Ltd
