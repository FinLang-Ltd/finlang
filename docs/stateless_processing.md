# ⚙️ Stateless Processing & Determinism
> **Applies to:** FinLang v0.6+  
> **Status:** Core Concept  
> **Last verified:** v0.7.2
> 
FinLang’s architecture is **stateless**, **deterministic**, and **idempotent**, ensuring that the same inputs always produce the same outputs — with no hidden state or telemetry.

---

## 🎯 Why Stateless Matters

**For Auditability:**

- Every decision is auditable and reproducible
- No hidden state means no unexplainable behavior
- Same inputs always produce same outputs

**For Operations:**
- Parallel processing safe (no shared state)
- Easy testing (deterministic outputs)
- CI/CD friendly (no databases or config drift)

**For Privacy:**
- All processing is local
- No telemetry, cloud calls, or data leaving your machine

---

## 🔹 Design Principles

| Principle | Purpose |
|-----------|----------|
| Determinism | Identical inputs → identical outputs. |
| Idempotence | Re-running a ruleset never duplicates changes. |
| Transparency | Audit trail (`audit.json`) captures every mutation. |
| Privacy | All processing is local; no telemetry or cloud calls. |

---

## 🔹 Execution Flow

1. Read input CSV (via `_read_csv_hardened`)  
2. Apply header map → canonical fields  
3. Normalize numbers & dates (locale-aware)  
4. Execute rules in order  
5. Generate audit log (if enabled)  
6. Write output → deterministic CSV (ordered columns)

---

## 🔒 Reproducibility Guarantee

Run the same command twice:

**Linux/macOS/WSL**
```bash
# Run 1
finlang --input data.csv --output out1.csv --rules rules.fin
# Run 2
finlang --input data.csv --output out2.csv --rules rules.fin
# Files are byte-for-byte identical
diff out1.csv out2.csv
# (no output = identical)
```

**Windows (PowerShell)**
```powershell
finlang --input data.csv --output out1.csv --rules rules.fin
finlang --input data.csv --output out2.csv --rules rules.fin
Compare-Object (Get-Content out1.csv) (Get-Content out2.csv)
# (no output = identical)
```

**Hash verification**

**Linux/macOS/WSL**
```bash
sha256sum out1.csv out2.csv
# Hashes should match
```

**Windows (PowerShell)**
```powershell
Get-FileHash out1.csv, out2.csv -Algorithm SHA256
# Both hashes will match
```

This guarantee enables:
- ✅ Regression testing
- ✅ Regulatory validation
- ✅ Distributed processing

---

## 📋 Real-World Example: Audit Trail

```bash
# Initial categorization
finlang --input transactions.csv --output baseline.csv   --rules rules.fin --audit baseline_audit.json --audit-mode full

# Later: Re-run with same rules
finlang --input transactions.csv --output rerun.csv   --rules rules.fin --audit rerun_audit.json --audit-mode full

# Audit files are identical (proves determinism)
# Linux/macOS/WSL:
diff baseline_audit.json rerun_audit.json
# Windows (PowerShell):
Compare-Object (Get-Content baseline_audit.json) (Get-Content rerun_audit.json)
```

---

## 📖 Related Documentation

- [Compliance Pack](legal/compliance_pack.md) – Governance overview  
- [Privacy Policy](legal/privacy.md) – Data handling & rights  
- [Terms](legal/terms.md) – Licensing & legal terms  
- [Rule Language](rule_language.md) – DSL reference  
- [Benchmarks](benchmarks.md) – Performance data

© FinLang Ltd
