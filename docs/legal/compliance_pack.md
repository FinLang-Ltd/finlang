# 📑 FinLang Compliance Pack Summary
*Version: v0.9.2 — November 2026*

This Compliance Pack provides a consolidated overview of **FinLang Ltd**’s legal, compliance, and governance framework. It is intended for customers, partners, and potential acquirers as a due diligence reference.

---

## 🔹 Company Details
- **Entity:** FinLang Ltd, registered in Scotland, company number SC860894  
- **Location:** Auchterarder, Scotland, United Kingdom  
- **ICO Registration Number:** ZB998843  
- **Trademark:** FinLang®, registered (UKIPO UK00004268386, classes 9 and 42), owned by FinLang Ltd  

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
  - privacy.md (UK GDPR privacy policy: legal bases, rights, retention, transfers; no transaction data collected, self-hosted)  
  - terms.md (Commercial Licence Terms v2, 20 Nov 2026: plans, no kill switch, rulepack licence, confidentiality, UK GDPR Article 28 processor schedule, liability, Scots law)

---

## 🔹 Product Assurance & Validation
- **Deterministic engine** — no machine learning, no randomness, no network calls in the engine; every output row attributable to a named rule via the audit trail.
- **Trust layer** — `--verify` (SHA-256 output integrity), `--reconcile` (independent row-by-row comparison against an external/ML system, with orphan detection), `--impact` (pre-change blast-radius analysis of rulepack edits).
- **Test discipline** — 204-test daily suite across 10 gates; 7-gate full pre-release suite (golden-master matrix, adversarial edge cases, data-integrity run, AST contract tests); 43-test standalone HTTP API suite; standalone Workbench suites (18 UI-contract tests and 99 end-to-end tests in a real browser); post-publish cleanroom validation from PyPI.
- **Reproducibility** — the same input and rules can be re-run to produce the same categorised output, with a run-reproducible audit artefact (v0.8.1).
- **Release governance** — versioned changelog and per-release notes; checklist-gated publishing.

---

## 🔹 Privacy & Data Protection
- **No customer transaction data collected** – FinLang is self-hosted and processes data entirely on the customer’s infrastructure.  
- **No telemetry** – software does not “phone home.”
- **Optional HTTP API is self-hosted** – deployed on the customer’s own infrastructure; the same no-collection posture applies.  
- **Minimal data stored:** name, email, licence type (commercial customers only).  
- **Payments handled by Lemon Squeezy** (merchant of record; FinLang Ltd never sees card details).  
- **Data Retention:**  
  - Inquiries – 3 years  
  - Payment records – 7 years  
  - Licence information – while the licence lasts + 2 years; perpetual rulepack licences 6 years after purchase  
  - Data sent for support or services – deleted or returned when the work ends  

---

## 🔹 Licence & Legal Structure
- **Dual licensing:** AGPLv3 (open source) and the FinLang Commercial Licence Terms (terms.md, v2).  
- **Commercial plans:** Team (one legal entity, internal use), Enterprise Group (whole group, internal use), Enterprise Platform (adds client-facing use, priced by band of client organisations). No seat counts.  
- **Commercial licence:**  
  - Annual, Team auto-renews; fees non-refundable; price changes only at renewal with 30 days' notice  
  - Every release during the term included, major versions too  
  - No kill switch: on expiry, use continues under AGPLv3  
  - Support: Team by email, 48-hour response target; Enterprise as agreed in the order  
  - 90-day conformity remedy: if it doesn't work as documented and can't be fixed, the order is refunded  
  - Liability capped for both parties at the greater of fees paid in the last 12 months and £1,000  
  - Mutual confidentiality; customer purchase-order terms don't apply  
  - Governing law: Scotland; Scottish courts  
- **Commercial rulepacks:** perpetual licence for the buying entity, and its group while it holds an Enterprise plan (terms clause 9).  
- **Enterprise Platform:** may distribute FinLang to client organisations; copies already delivered stay licensed after expiry; 90-day wind-down for hosted use.  
- **Acquisitions:** if a customer is acquired or sells a business, cover continues until the end of the period paid for; customer orders continue on the same terms if FinLang Ltd is acquired.  
- **Data:** FinLang Ltd acts as processor only for data a customer chooses to send for support (terms clause 10.4 and Schedule 1). Customers are asked not to send payment card or special category data.  
- **Business customers only;** force majeure, severability and survival clauses included.  

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
