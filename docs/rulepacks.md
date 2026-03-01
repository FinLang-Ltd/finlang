# 📦 Rule Packs Reference
> **Applies to:** FinLang v0.6+  
> **Status:** Stable  
> **Last verified:** v0.7.4

Rule packs are pre-built `.fin` files that provide baseline categorization logic. They save you from writing common rules from scratch.

---

## 🚀 Quick Start

Include packs using the `--include-pack` flag:

```bash
# Single pack
finlang --input bank.csv --output out.csv --rules my_rules.fin --include-pack retail

# Multiple packs (comma-separated)
finlang --input bank.csv --output out.csv --rules my_rules.fin --include-pack retail,sanity,transport
```

---

## 🔹 How Packs Work

1. **Your rules take precedence** — Personal rules in `--rules` are applied first (highest priority).
2. **Packs provide baseline coverage** — They catch common patterns you haven't written rules for yet.
3. **Last rule wins** — If multiple rules match, the last one in execution order sets the category.
4. **Flags accumulate** — All matching rules contribute flags (space-separated).

**Execution order:**
```
Your rules (--rules) → Pack 1 → Pack 2 → Pack 3 ...
```

> 💡 **Tip:** Packs set `category = "Review"` by default. This is intentional — review the matches, then update your personal rules with the correct categories.

---

## 🔹 Bundled Packs (Free)

These packs ship with FinLang and are available immediately:

| Pack Name | Alias | Rules | Description |
|-----------|-------|-------|-------------|
| `retail` | — | ~10 | UK grocery & retail chains (Tesco, Sainsbury's, Lidl, Aldi, etc.) |
| `transport` | — | ~6 | Transport & fuel (Uber, TfL, Trainline, Shell, BP) |
| `subscriptions` | `subs` | ~8 | Streaming & software (Spotify, Netflix, Amazon Prime, Adobe) |
| `travel` | — | ~8 | Airlines & accommodation (Airbnb, Booking.com, Ryanair, BA) |
| `financial` | — | ~10 | Bank fees, interest, ATM, FX charges |
| `compliance` | — | ~5 | Flags for large transactions, FX, potential duplicates |
| `sanity` | — | ~3 | Data quality checks (empty counterparty, zero amount, refund keywords) |
| `examples` | — | ~4 | Tutorial rules demonstrating operators and patterns |

### Pack Details

#### `retail` — UK Grocery & Retail
Matches major UK supermarkets and retail chains.

**Patterns:** `*TESCO*`, `*SAINSBURY*`, `*LIDL*`, `*ALDI*`, `*ASDA*`, `*MARKS*SPENCER*`, `*M&S*`, `*CO*OP*`, `*ICELAND*`

**Sets:** `category = "Review"`, `flags += "Retail"`

---

#### `transport` — Transport & Fuel
Matches ride-sharing, public transport, and fuel stations.

**Patterns:** `*UBER*`, `*TRAINLINE*`, `*TFL*`, `*SHELL*`, `*BP*`, `*NATIONAL*RAIL*`

**Sets:** `category = "Review"`, `flags += "Transport"` or `flags += "Fuel"`

---

#### `subscriptions` (alias: `subs`) — Streaming & Software
Matches common subscription services.

**Patterns:** `*SPOTIFY*`, `*NETFLIX*`, `*AMAZON*PRIME*`, `*YOUTUBE*PREMIUM*`, `*APPLE.COM/BILL*`, `*MICROSOFT*`, `*ADOBE*`

**Sets:** `category = "Review"`, `flags += "Subscription"`

---

#### `travel` — Airlines & Accommodation
Matches travel booking platforms and airlines.

**Patterns:** `*AIRBNB*`, `*BOOKING*COM*`, `*EASYJET*`, `*RYANAIR*`, `*BRITISH*AIRWAYS*`, `*HOTELS*COM*`, `*EXPEDIA*`

**Sets:** `category = "Review"`, `flags += "Travel"`

---

#### `financial` — Bank Fees & Interest
Matches bank operational charges.

**Patterns:** `*BANK*CHARGE*`, `*INTEREST*`, `*FX*FEE*`, `*CASH*WITHDRAWAL*`, `*ATM*`, `*OVERDRAFT*`

**Sets:** `category = "Review"`, `flags += "BankFee"` / `"Interest"` / `"FX"` / `"Cash"`

---

#### `compliance` — Compliance Flags
Non-destructive flagging for audit/compliance workflows.

**Logic:**
- Large transactions (≥ £500 debit or credit) → `flags += "LargeTxn"`
- Non-sterling indicators → `flags += "FX"`
- Duplicate markers in memo → `flags += "PotentialDuplicate"`

**Sets:** Flags only (does not change category).

---

#### `sanity` — Data Quality Checks
Catches data issues that need manual review.

**Logic:**
- Empty counterparty → `flags += "EmptyCounterparty"`
- Zero amount → `flags += "ZeroAmount"`
- Memo contains "REFUND" → `flags += "RefundCheck"`

**Sets:** `category = "Review"`, plus relevant flag.

---

#### `examples` — Tutorial & Learning
Demonstrates FinLang operators and syntax. Not for production use.

**Covers:** Equality (`==`), wildcards (`~`), amount ranges (`in`), flag appending (`+=`).

---

## 🔹 Commercial Packs

For complex use cases, FinLang Ltd offers commercial rule packs with deeper coverage.

### Banking Pack v1.0 (£49)
**92 rules** for UK banking data normalization.

| File | Rules | Purpose |
|------|-------|---------|
| `Banking.ReconcileHeuristics.fin` | 56 | Transaction type classification, UK payment rails (BACS, FPS, CHAPS) |
| `Banking.BankFees.fin` | 26 | Fee separation, interest classification, RBS/NatWest codes |
| `Banking.DuplicateHeuristics.fin` | 10 | Reversal, correction, and duplicate detection |

**Key features:**
- Neobank detection (Revolut, Wise, Monzo)
- UK payment rail decoding (BACS, FPS, CHAPS, BGC)
- Directional logic (distinguishes funding from spending)
- Sentinel tagging (`Pack:Banking_v1.0`)

See [Commercial Rulepacks - Banking Pack (Banking Pack v1.0)](commercial_rulepacks/banking_pack_v1.md) for full details.

**Purchase:** [finlang.io](https://finlang.io)

---

## 🔹 Using Commercial Packs

Commercial packs are standalone `.fin` files. Include them via `--rules`:

```bash
# Your rules + commercial pack
finlang --input bank.csv --output out.csv \
  --rules my_rules.fin \
  --rules banking/Banking.ReconcileHeuristics.fin \
  --rules banking/Banking.BankFees.fin \
  --include-pack sanity
```

Or concatenate into a single file:

```bash
cat my_rules.fin banking/*.fin > combined_rules.fin
finlang --input bank.csv --output out.csv --rules combined_rules.fin
```

---

## 🔹 Best Practices

1. **Start with `retail,sanity`** — Good baseline for personal finance.
2. **Review before trusting** — Packs set `category = "Review"` intentionally.
3. **Graduate rules to your personal file** — Once verified, copy rules to `my_rules.fin` with correct categories.
4. **Don't over-include** — Only add packs relevant to your data.

**Recommended combinations:**

| Use Case | Packs |
|----------|-------|
| Personal finance (UK) | `retail,transport,subs,sanity` |
| Business expenses | `retail,transport,travel,financial,sanity` |
| Compliance/audit | `financial,compliance,sanity` |
| Learning FinLang | `examples` |

---

## 🔹 Creating Your Own Packs

Any `.fin` file can be a pack. To create a reusable pack:

1. Write rules following [Rule Language](rule_language.md) syntax.
2. Use descriptive rule names with a prefix (e.g., `"MyPack: Vendor Name"`).
3. Consider adding a sentinel flag: `flags += "Pack:MyPack_v1.0"`.
4. Test thoroughly before sharing.

**Example custom pack structure:**
```fin
# MyCompany Vendor Pack v1.0

rule "MyPack: Preferred Supplier A" {
  match:
    - counterparty ~ "*SUPPLIER A*"
  set:
    - category = "Approved Vendors"
    - flags += "Pack:MyCompany_v1.0"
}
```

---

## 🔹 Cross-References

- [CLI Reference](cli_reference.md) — `--include-pack` flag details
- [Rule Language](rule_language.md) — Writing custom rules
- [Workflows](workflows.md) — Using packs in daily runs
- [Growth Loop Best Practices](growth_loop_best_practices.md) — Iterating on coverage

---

© FinLang Ltd
