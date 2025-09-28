# 📖 FAQ (Frequently Asked Questions)
*Applies to FinLang v0.6.x*

This document answers common questions about FinLang’s features, behavior, and best practices.

---

## 🔹 General

**Q: Which rules take precedence?**  
A: Rules are applied in the order they are loaded:  
1. Personal `.fin` files (`--rules`) are loaded first.  
2. Included packs (`--include-pack`) are appended afterward.  

Within each file, rules run **top-to-bottom**. For `category`, `memo`, and `exclude`, **the last matching rule wins** — regardless of whether it came from a personal file or a pack. Flags always accumulate (`+=` only).  

👉 If you want a personal rule to “win,” make it more specific than the pack rule, or place your overrides after broader ones if they’re in the same file.

**Example:**

```fin
# personal_rules.fin
rule "Amazon Personal" {
  match:
    - counterparty ~ "*AMAZON*"
  set:
    - category = "My Amazon Purchases"
}

# retail.fin (pack)
rule "Retail: Amazon General" {
  match:
    - counterparty ~ "*AMAZON*"
  set:
    - category = "Shopping"
}
```

**Input Transaction:**  
| counterparty | amount | category |  
|--------------|--------|----------|  
| AMAZON UK    | -25.00 |          |  

**Result:**  
`category = "Shopping"` (pack rule runs later, overrides).

---

## 🔹 Data & Mapping

**Q: My CSV headers don’t match the examples. What should I do?**  
A: FinLang ships with a bundled `bank.map.json`, used automatically if you don’t specify `--map`. If your headers differ, edit or supply a custom map so they align with canonical fields (`counterparty`, `amount`, `debit`, `credit`, etc.). See [Mapping Guide](mapping_guide.md).

**Q: My file has both `amount` and `debit/credit`. Which is used?**  
A: `amount` always takes precedence. `debit`/`credit` are only used if `amount` is missing.

**Precedence Example:**  

| Debit | Credit | Amount column present? | Final `amount` used |  
|-------|--------|-------------------------|---------------------|  
| 12.34 |        | Yes                     | value from `Amount` |  
|       | 9.99   | Yes                     | value from `Amount` |  
| 12.00 | 5.00   | No                      | -7.00 (5 - 12)      |  

---

## 🔹 Rule Language & Engine Behavior

**Q: I tried `flags = "X"` and it didn’t work. Why?**  
A: Flags are append-only. Use `flags += "X"`. Overwriting (`flags = "..."`) is disallowed to preserve history.

**Q: How does the amount/debit/credit synthesis work?**  
A: If no `amount` column exists, FinLang synthesizes it with:  

```
amount = abs(credit) - abs(debit)
```

- Debit-only → `-abs(debit)`  
- Credit-only → `+abs(credit)`  
- Both empty → `0`

**Q: Can I chain rules or have one rule match on the output of another?**  
A: Yes. Later rules can match on `category` or `flags` set by earlier rules (“rule stacking”). See [Rule Language Reference](rule_language.md).

**Example:**

```fin
rule "Amazon General" {
  match:
    - counterparty ~ "*AMAZON*"
  set:
    - category = "Shopping"
}

rule "Amazon Prime" {
  match:
    - category == "Shopping"
    - counterparty ~ "*PRIME*"
  set:
    - category = "Subscriptions"
    - flags += "Recurring"
}
```

**Input Transaction:**  
| counterparty    | amount | category |  
|-----------------|--------|----------|  
| AMAZON PRIME UK | -10.99 |          |  

**Result:**  
`category = "Subscriptions"` with `flags = "Recurring"`.

**Q: What is the default for the `exclude` field?**  
A: `false`. Set `exclude = true` in a rule to mark rows for exclusion.

**Q: Can a rule match on multiple fields at once?**  
A: Yes. Multiple conditions in a `match:` block are combined with **AND**.

---

## 🔹 Workflows & Tools

**Q: Why do the discovery and suggestion tools sometimes miss things?**  
A: They’re conservative by design. `finlang-suggest` de-duplicates against your existing rules to avoid redundant suggestions.

**Q: How do I safely append new rules to my main file?**  
A: Always back up first:

- **macOS/Linux (bash/zsh):**
  ```bash
  cp my_rules.fin{,.bak} && cat draft_rules.fin >> my_rules.fin
  ```

- **Windows (PowerShell):**
  ```powershell
  Copy-Item my_rules.fin -Destination my_rules.bak
  Get-Content draft_rules.fin | Add-Content my_rules.fin
  ```

- **Windows (CMD):**
  ```cmd
  copy my_rules.fin my_rules.bak && type draft_rules.fin >> my_rules.fin
  ```

---

## 🔹 Rules & Logic Gotchas

**Q: What happens if two rules both match?**  
A: The last one wins for category/memo/exclude; flags always accumulate.

**Q: Why can’t I delete flags with a rule?**  
A: FinLang is append-only for auditability. You can clear flags manually in the CSV if needed.

---

## 🔹 Performance & Scale

**Q: How many rows can FinLang handle?**  
A: Millions. Benchmarks show:  
- 5M × 50 cols → ~210s (~23,800 rows/s, enterprise baseline)  
- 5M × 20 cols → ~95s (~52,600 rows/s, lighter case)  

Throughput scales with column count. See [benchmarks.md](benchmarks.md).

**Q: Memory usage seems high — is that normal?**  
A: Yes. FinLang projects only required columns but processes them in vectorized form. Drop unused columns upstream or split wide files if memory is tight.

**Q: Why is running with `--audit-mode` slower?**  
A: Because it tracks changes. Audit modes:  
- `none` → no audit, fastest.  
- `lite` → records changed cells only (default).  
- `full` → records before/after snapshots of all evaluated cells.  

---

## 🔹 Audit & Compliance

**Q: Can I export the audit log?**  
A: Yes, with `--audit audit.json`. It records all changes per rule.

**Q: Why does my audit log look empty?**  
A: You ran with `--audit-mode none`. Use `lite` (default) or `full`.

---

## 🔹 User Experience

**Q: Do I need to learn regex?**  
A: No. Use simple wildcards (`*TESCO*`), though regex is supported for advanced cases.

**Q: Can I edit rules in Excel instead of a text editor?**  
A: Yes. `.fin` files are plain text. Ensure spaces (not tabs) for indentation.

---

© FinLang Ltd
