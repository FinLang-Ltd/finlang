# 💰 Amount Synthesis Logic
> **Applies to:** FinLang v0.6.4+
> **Status:** Stable
> **Last verified:** v0.7.2

FinLang guarantees deterministic numeric resolution even with inconsistent bank exports.

---

## 🎯 Why Amount Synthesis Matters

Many banks export **separate debit/credit columns** instead of a single signed amount.
FinLang automatically synthesizes a canonical `amount` field using deterministic logic,
eliminating manual preprocessing and ensuring consistent handling across institutions.

---

## 🔹 Resolution Order

1️⃣ Use `amount` column if present.  
2️⃣ Else synthesize from `debit` and `credit`:

```
amount = abs(credit) - abs(debit)
```

- Debit-only → `-abs(debit)`  
- Credit-only → `+abs(credit)`  
- Both empty → `0`

---

## 🔹 Examples

| Debit | Credit | Result |
|:----:|:----:|:----:|
| 45.20 |  | -45.20 |
|  | 1500.00 | +1500.00 |
| 12.00 | 5.00 | -7.00 |
|  |  | 0 |

---

## 🔹 Edge Cases & Internationalization

| Issue | Cause | Resolution |
|:---|:---|:---|
| “199.99 → 19999.0” | Decimal comma locale | Use `--decimal , --thousands .` |
| `(199,99)` or `199,99-` | Accounting/trailing minus | Handled automatically by parser. |
| `199,99 DR` or `199,99 CR` | CR/DR suffixes | Handled automatically by parser. |

---

## ✅ Verification

Use audit mode to confirm synthesis is correct:
```bash
finlang --audit amounts_check.json --audit-mode full ...
```
Review the `changes` field to see synthesized amounts.

---

## 🔧 Best Practices

- Validate using `--audit-mode full` before production.  
- Always prefer numeric fields over textual amounts.  
- Use consistent decimal symbols across imports.

---

## 📖 Related Documentation

- [Mapping Guide](mapping_guide.md) – Canonical fields  
- [Rule Language](rule_language.md) – Using `amount` in rules  
- [i18n Examples](i18n_examples.md) – Regional parsing

© FinLang Ltd
