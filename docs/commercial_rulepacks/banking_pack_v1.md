# Banking Pack v1.0 — Technical Reference
> **Applies to:** FinLang Engine v0.6.4+  
> **Status:** Commercial  
> **Version:** 1.0.0  
> **Total Rules:** 92  
> **Last tested:** v0.7.2

The Banking Pack provides a deterministic logic layer for normalizing global and UK banking data. It consists of three specialized rule files.

---

## 📂 File Summary

| Rule File | Rules | Purpose |
|:----------|:------|:--------|
| `Banking.ReconcileHeuristics.fin` | 56 | Core transaction type classification & UK Rails |
| `Banking.BankFees.fin` | 26 | Separation of fees, interest, and operational costs |
| `Banking.DuplicateHeuristics.fin` | 10 | Identification of reversals, corrections, and duplicates |
| **Total** | **92** | |

---

## 1. Reconcile Heuristics
**File:** `banking/Banking.ReconcileHeuristics.fin` (56 rules)

Handles the normalization of transaction types, payment rails, and neobank funding flows.

| Section | Logic / Scope | Categories Set | Flags Applied |
|:--------|:--------------|:---------------|:--------------|
| **Neobank / Funding** | Detects Revolut/Wise/Monzo flows. Uses **directional logic** (negative amounts only) to distinguish funding from spending. | `Card Payment`, `Account Topup`, `Bank Transfer` | `Wallet_Funding`, `Bank_TopUp`, `Bank_FX_Exchange`, `Bank_Card` |
| **Universal Banking** | Standard identifiers for D/D, Standing Orders, POS, Mobile Pay (Apple/Google), and ATM withdrawals. | `Direct Debit`, `Standing Order`, `Card Payment`, `ATM` | `Bank_Scheduled`, `Bank_Card`, `Bank_ATM` |
| **UK Standard Codes** | Decodes UK interbank payment rails (BACS, FPS, CHAPS) and legacy codes (BGC, TLR, DPC). | `Bank Transfer`, `Cheque`, `Internal Transfer` | `Bank_BACS`, `Bank_FPS`, `Bank_CHAPS`, `Bank_Giro`, `Bank_Cheque` |
| **Metadata** | Applies sentinel tag to all processed rows. | — | `Pack:Banking_v1.0` |

---

## 2. Bank Fees & Interest
**File:** `banking/Banking.BankFees.fin` (26 rules)

Separates operational finance costs from actual spending.

| Section | Patterns | Categories Set | Flags Applied |
|:--------|:---------|:---------------|:--------------|
| **Maintenance** | Monthly fees, plan fees, service charges. | `Bank Fees` | `Bank_Fee` |
| **Overdraft / Unpaid** | NSF, Returned items, Unpaid DDs, Overdraft usage fees. | `Bank Charges` | `Bank_Overdraft`, `Bank_Unpaid`, `Bank_Returned` |
| **Interest** | Distinguishes paid interest (Income) from charged interest (Expense). | `Interest Income`, `Interest Expense` | `Bank_Interest` |
| **Usage Fees** | Non-Sterling transaction fees, ATM usage fees, Wire fees. | `Bank Fees` | `Bank_ATM_Fee`, `Bank_FX_Fee`, `Bank_Wire_Fee` |
| **RBS/NatWest** | Decodes specific RBS codes: `CHG`, `VRATE`, `CUI`, `DIV`, `N-S TRN FEE`. | `Bank Fees`, `Dividend Income` | `Bank_Fee`, `Bank_Dividend` |

---

## 3. Duplicate & Reversal Detection
**File:** `banking/Banking.DuplicateHeuristics.fin` (10 rules)

Identifies potential dirty data that should be excluded from reconciliation.

| Pattern | Description | Flags Applied |
|:--------|:------------|:--------------|
| `* REV *` | Space-padded reversal detection (avoids false positives like "PREVIEW"). | `Bank_Adjustment`, `Dup_Candidate` |
| `CORRECTION` | Bank-initiated corrections. | `Bank_Adjustment`, `Dup_Candidate` |
| `REFUND` | Merchant refunds and chargebacks. | `Bank_Adjustment`, `Dup_Candidate` |
| `DUPLICATE` | Explicit bank markers for duplicate entries. | `Dup_Candidate` |

---

## 🚩 Flag Reference

The pack applies the following standardized flags to your data:

| Flag | Meaning |
|:-----|:--------|
| `Pack:Banking_v1.0` | **Sentinel:** Indicates this row was processed by the Banking Pack. |
| `Wallet_Funding` | Outbound transfer to a neobank/wallet (Asset Transfer). |
| `Bank_BACS` | Payment via BACS rail. |
| `Bank_FPS` | Payment via Faster Payments Service. |
| `Bank_CHAPS` | Payment via CHAPS (High Value). |
| `Bank_Scheduled` | Recurring item (Direct Debit or Standing Order). |
| `Bank_Card` | POS or Debit Card transaction. |
| `Bank_ATM` | Cash withdrawal. |
| `Bank_Fee` | Operational cost / Service fee. |
| `Bank_Interest` | Interest earned or paid. |
| `Dup_Candidate` | **Warning:** This row is likely a duplicate, reversal, or correction. |

---

## 📦 Installation

The Banking Pack is a commercial add-on. After purchase, you receive three `.fin` files.

**Usage:**
```bash
finlang --input bank.csv --output out.csv \
  --rules my_rules.fin \
  --rules banking/Banking.ReconcileHeuristics.fin \
  --rules banking/Banking.BankFees.fin \
  --rules banking/Banking.DuplicateHeuristics.fin
```

Or combine into a single rules file:
```bash
cat my_rules.fin banking/*.fin > combined.fin
finlang --input bank.csv --output out.csv --rules combined.fin
```

---

## 🔹 Cross-References

- [Rule Packs Reference](../rulepacks.md) — Overview of all packs
- [Rule Language](../rule_language.md) — DSL syntax reference
- [Mapping Guide](../mapping_guide.md) — Field normalization

---

**Purchase:** [finlang.io](https://finlang.io/)

© FinLang Ltd
