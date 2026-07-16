# 📑 FinLang Compliance Pack Summary
*Version: v0.8.1 — July 2026*

This Compliance Pack provides a consolidated overview of **FinLang Ltd**’s legal, compliance, and governance framework. It is intended for customers, partners, and potential acquirers as a due diligence reference.

---

## 🔹 Company Details
- **Entity:** FinLang Ltd  
- **Location:** Auchterarder, Scotland, United Kingdom  
- **ICO Registration Number:** ZB998843  
- **Trademark:** “FinLang” filed (UKIPO)  

---

## 🔹 Documentation Suite
- **Technical Documentation:**  
  - README.md (overview, quickstart)  
  - install.md (multi-platform installation)  
  - workflows.md (daily run, growth loop, enterprise integration)  
  - cli_reference.md (full CLI flags & usage)  
  - rule_language.md (DSL specification)  
  - mapping_guide.md (canonical field mapping)  
  - faq.md (user Q&A, performance, precedence)
  - verify.md (SHA-256 output-integrity verification)
  - reconciliation.md (row-by-row comparison against an external/ML system — positional, identity-guard, and key-based alignment with orphan detection)
  - impact.md (rule-change impact analysis — behavioural vs attribution-only, CI-gateable)
  - api.md + api_reference.md (self-hosted HTTP API over the same CLI engine)
  - rulepacks.md · flags.md · amount_synthesis.md · i18n_examples.md · stateless_processing.md · growth_loop_best_practices.md
  - release_notes/ (per-release notes, v0.6.4 → current)  
  - benchmarks.md + PDF (official v0.7.7 performance results — ~180K rows/sec standard, ~217K rows/sec FastIO on the 20M-row integrity harness)

- **Legal Documentation:**  
  - privacy.md (GDPR/ICO aligned privacy policy, no data collection, self-hosted)  
  - terms.md (Terms of Use / End User Licence Agreement, dual licence clarity, IP protection, renewals, refunds, liability, Scotland jurisdiction)

---

## 🔹 Product Assurance & Validation
- **Deterministic engine** — no machine learning, no randomness, no network calls in the engine; every output row attributable to a named rule via the audit trail.
- **Trust layer** — `--verify` (SHA-256 output integrity), `--reconcile` (independent row-by-row comparison against an external/ML system, with orphan detection), `--impact` (pre-change blast-radius analysis of rulepack edits).
- **Test discipline** — 182-test daily suite across 10 gates; 7-gate full pre-release suite (golden-master matrix, adversarial edge cases, data-integrity run, AST contract tests); 26-test standalone HTTP API suite; post-publish cleanroom validation from PyPI.
- **Reproducibility** — the same input and rules can be re-run to produce the same categorised output, with a run-reproducible audit artefact (v0.8.1).
- **Release governance** — versioned changelog and per-release notes; checklist-gated publishing.

---

## 🔹 Privacy & Data Protection
- **No customer transaction data collected** – FinLang is self-hosted and processes data entirely on the customer’s infrastructure.  
- **No telemetry** – software does not “phone home.”
- **Optional HTTP API is self-hosted** – deployed on the customer’s own infrastructure; the same no-collection posture applies.  
- **Minimal data stored:** name, email, licence type (commercial customers only).  
- **Payments handled by Lemon Squeezy** (PCI DSS compliant processor).  
- **Data Retention:**  
  - Inquiries – 3 years  
  - Payment records – 7 years  
  - Licence information – term + 2 years  

---

## 🔹 Licence & Legal Structure
- **Dual licensing:** AGPLv3 (open source) and Commercial Licence (terms.md).  
- **Commercial licence:**  
  - Annual subscription, auto-renewal, non-refundable  
  - Updates & upgrades clause (minor updates included, major versions optional)  
  - Support SLAs tiered (Solo, Team/Business, Enterprise)  
  - Liability capped at fees paid in last 12 months  
  - Governing law: Scotland, UK courts jurisdiction  
- **Assignment clause:** Active licences transfer automatically upon acquisition.  
- **Force majeure & survival clauses** included.  

---

## 🔹 Insurance & Risk Management
- **Business insurance:** Active (UK policy, covers professional liability).  
- **Risk controls:** No hosted customer data → minimal data breach liability.  
- **Legal carve-outs:** Standard exclusions (fraud, negligence causing death/personal injury).  

---

## 🔹 Strategic Compliance Advantages
- **Self-hosted = privacy moat** – clear differentiator vs. cloud-first competitors.  
- **Enterprise readiness** – GDPR alignment, liability caps, SLA clarity.  
- **Acquisition-grade docs** – machine-grade consistency across technical and legal documentation.  

---

---
**See also:** [Privacy Policy](privacy.md) · [Terms of Use](terms.md) · [Benchmarks](../benchmarks.md)

© FinLang Ltd
