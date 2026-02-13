# 🚩 FinLang Flags & Canonical Formats
> **Applies to:** FinLang v0.7+
> **Status:** Active
> **Last verified:** v0.7.2

This page defines the **single source of truth** for CLI flags and their **expected input formats**.  
All definitions verified against the v0.6.4 GA codebase (Nov 2025).

---

## 1) Date & Time Flags

| Flag | Canonical Input | Meaning | Notes |
|-----|------------------|--------|------|
| `--since-date` | **ISO 8601** `YYYY-MM-DD` (e.g., `2025-01-01`) | Filter records with `date >= since_date` | Implemented only for `finlang-discover`. |
| `--dayfirst` | *(boolean switch)* | Interpret ambiguous dates as **DD/MM/YYYY** | Use for UK-style `01/12/2025`. Redundant for `DD.MM.YYYY` / `YYYY-MM-DD`. |
| `--date-format` | e.g., `"%d/%m/%Y"` | Explicit parser for custom formats | Overrides ambiguity. Prefer ISO when possible. |

**Locale guidance:** One locale per run. See **[i18n Examples](i18n_examples.md)** for regional recipes.

---

## 2) Number & Locale Flags

| Flag | Canonical Input | Meaning | Notes |
|-----|------------------|--------|------|
| `--decimal` | `.` or `,` | Decimal character | EU often uses `,` (comma). |
| `--thousands` | `,` `.` `'` or space (`' '`) | Thousands separator | Switzerland commonly uses **apostrophe `'`**. |
| `--encoding` | `utf-8-sig` *(default)*, `auto`, `utf-8`, `latin-1`, … | CSV text encoding | `auto` safely detects UTF-8 / Latin-1 in most cases. |
| `--output-encoding` | `utf-8` *(default)* or any valid codec | Output CSV encoding | Use when downstream tools require a specific codec. |

**Shell safety:** Always quote separator characters to prevent shell interpretation:
```bash
--decimal ","   --thousands "."   # EU
--decimal "."   --thousands ","   # UK/US with explicit thousands
--thousands "'"                   # Switzerland (apostrophe)
```
> **Why?** PowerShell treats bare `,` `;` `'` as operators. Quoting works safely in **all** shells (PowerShell, Bash, CMD).
>
> **Bash/Linux users:** Quoting is optional for most separators but recommended for consistency across environments.

**Common pitfalls:**  
- “199,99 → 19999.0” = wrong `--decimal/--thousands` pairing.  
- CR/DR suffixes and trailing minus are normalized automatically.

---

## 3) Strictness & Safety

| Flag | Canonical Input | Meaning | Notes |
|-----|------------------|--------|------|
| `--strict-parse` | *(boolean switch)* | Enforce delimiter/header consistency | Fails early on malformed CSVs. |
| `--fail-threshold` | **fraction `0.0–1.0`** (e.g., `0.05`) | Abort if drop-rate exceeds threshold | Protects against silent data loss. |
| `--headless` | *(boolean switch)* | Suppress non-essential console output | Good for CI. |
| `--timings` | *(boolean switch)* | Report phase timings | Pairs well with `--fastio`. |

---

## 4) Performance

| Flag | Canonical Input | Meaning | Notes |
|-----|------------------|--------|------|
| `--fastio` | *(boolean switch)* | Prefer PyArrow for I/O | 20–40% speed-up on large files (PyArrow ≥ 16). |

---

## 5) Rules, Maps & Auditing (Core CLI)

| Flag | Canonical Input | Meaning | Notes |
|-----|------------------|--------|------|
| `--rules` | Path(s) to `.fin` file(s) | Load user rules | Multiple allowed. |
| `--include-pack` | Comma list (e.g., `retail,sanity`) | Include bundled rule packs | Optional. |
| `--map` | Path to header map JSON | Apply canonical field mapping | Defaults to built-in map if omitted. |
| `--audit` | Output path (`.json`) | Write audit log | Use with `--audit-mode`. |
| `--audit-mode` | `none` \| `lite` \| `full` | Diff verbosity | `lite` default; `full` for validation. |

---

## 6) Discover / Suggest (Growth Loop)

**Discover (`finlang-discover`)**

| Flag | Canonical Input | Meaning |
|-----|------------------|--------|
| `--input` | Path to CSV | Source transactions |
| `--candidates` | Path to CSV | Output shortlisted candidate patterns |
| `--all-candidates` (alias: `--all`) | Path to CSV | Output full candidate set with aggregates |
| `--min-count` | Integer | Minimum frequency to include |
| `--min-amount` | Number | Minimum absolute amount |
| `--top-k` | Integer | Limit top results |
| `--since-date` | **ISO** `YYYY-MM-DD` | Time-bounded discovery |
| `--strict-parse` | switch | Hardened parsing |
| `--fail-threshold` | **fraction `0.0–1.0`** | Guardrail on drops |
| `--fastio` / `--headless` | switches | I/O speed / quiet mode |
| `--encoding` `--decimal` `--thousands` `--dayfirst` `--date-format` | per above | Locale controls |

**Suggest (`finlang-suggest`)**

| Flag | Canonical Input | Meaning |
|-----|------------------|--------|
| `--input` / `--output` | Paths | Read candidates / write rules |
| `--emit-match` | `exact` \| `fuzzy` | **Use `exact` for 1:1 production rules** |
| `--category` | String | Default category for emitted rules |
| `--prefix` | String | Add label prefix |
| `--rules` | Path | De-dupe against existing rules |
| `--append` / `--overwrite` | switches | File write mode |
| `--quote-style` | `"` \| `'` | Quote character used in suggested rules output. |

---

## 7) Environment Variables

| Variable | Component | Meaning |
|---------|-----------|--------|
| `FINLANG_SAFE_TEXT` | CLI | Enables CSV injection protection (prefix unsafe cells) |
| `FINLANG_AUDIT_MODE` | CLI | Default for `--audit-mode` |
| `FINLANG_AUDIT_MAX` | Engine | Cap audit log size |

---

## 8) Canonical Examples

**UK monthly run w/ date filter (ISO):**
```bash
finlang --input bank.csv --output out.csv --rules rules.fin   --dayfirst --strict-parse --encoding auto --fastio
```

**EU (France/Germany) discovery last 90 days (explicit determinism):**
```bash
finlang-discover --input cat.csv --candidates cand.csv --all-candidates all_cand.csv   --since-date 2025-08-01 --decimal "," --thousands "." --dayfirst --encoding auto   --strict-parse --top-k 50
```

**Suggest exact 1:1 rules from candidates:**
```bash
finlang-suggest --input cand.csv --output draft_rules.fin   --emit-match exact --category "Review" --append
```

---

## 🧪 Audit Reference
Cross-verified against **Independent Technical Audit (Nov 9, 2025)**.  
All flags validated in FinLang v0.7.2.

---

## ⚠️ Known Issues (v0.6.4.post2)

- None

---

## Links
- [CLI Reference](cli_reference.md) · [i18n Examples](i18n_examples.md) · [Growth Loop Best Practices](growth_loop_best_practices.md)

© FinLang Ltd
