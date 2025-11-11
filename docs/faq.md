# ❓ FinLang FAQ
*Applies to FinLang v0.6.4.post1 (GA Rev 3)*

---

## 🚀 Quick Answers (Most Common Questions)

**Q: Do I need a custom map?**  
A: Probably not. The default map covers most UK/EU banks.

**Q: My amounts look wrong (199,99 → 19999.0)**  
A: Add `--decimal , --thousands .` to your command. See [i18n_examples.md](i18n_examples.md).

**Q: How do I start?**  
A: `pip install finlang[fastio]` then `finlang --input bank.csv --output out.csv --rules rules.fin`

**Q: Where's the full documentation?**  
A: Start with [install.md](install.md) then [workflows.md](workflows.md).

---

## 💡 General

**Q: How does FinLang decide which rule wins?**  
A: Rules are evaluated **top‑to‑bottom**. When multiple rules match, **the last matching rule wins** for assignable fields such as `category` and `memo`.  
`flags` are always **append‑only**, so multiple rules can add tags.

**Q: Are rules case‑sensitive?**  
A: No. Field names and string comparisons are **case‑insensitive**, except when explicitly quoted regex patterns are used.

**Q: What happens if a rule has a syntax error?**  
A: The parser will exit immediately with an error message identifying the rule and line number. Use `--strict-parse` during development to catch errors early.

**Q: Does FinLang modify my input file?**  
A: No. The input CSV is read in a streaming fashion and never overwritten. Output is written to a new file specified by `--output`.

---

## 🧭 Data & Mapping

**Q: My file has both `amount` and `debit`/`credit` columns. Which does FinLang use?**  
A: If an `amount` column exists after mapping, it takes precedence. Otherwise, FinLang synthesizes one from `debit` and `credit`.  
➡️ See [amount_synthesis.md](amount_synthesis.md) and [mapping_guide.md](mapping_guide.md) for complete details.

**Q: My CSV headers don’t match the expected names. What should I do?**  
A: Use a **custom mapping file** (`--map`) to tell FinLang which column corresponds to `date`, `amount`, and `counterparty`. See the [Mapping Guide](mapping_guide.md) for examples.

**Q: Are mappings case‑sensitive?**  
A: No. Mapping keys and CSV headers are matched case‑insensitively.

**Q: What encodings are supported?**  
A: FinLang defaults to `utf‑8‑sig`. If your file contains special characters, use `--encoding auto` to automatically detect the correct one.

**Q: What does `exclude` do?**  
A: In v0.6.4 it’s **informational only**. You can set it in rules as a marker (e.g., `exclude = true`), but FinLang does not skip or drop rows yet. Future releases may make it functional.

---

## 🌍 I18n & Strictness

**Q: My amounts are wrong (e.g., `199,99` becomes `19999.0`).**  
A: This is a **locale mismatch**. Your file uses a comma as a decimal. Add `--decimal , --thousands .` to parse it correctly.  
➡️ See [i18n_examples.md](i18n_examples.md).

**Q: My dates are wrong (Jan 12 vs Dec 1).**  
A: Your file likely uses `DD/MM/YYYY`. Add the flag `--dayfirst` to interpret day‑first formats correctly.

**Q: My CSV fails to load or text looks garbled.**  
A: The file probably isn’t UTF‑8 encoded. Use `--encoding auto` to let FinLang detect it automatically.

**Q: I got a “Strict parse” error. What does it mean?**  
A: You ran with `--strict-parse`, which enforces consistency and fails fast on malformed input (e.g., irregular headers or mixed delimiters). Clean your CSV or run without that flag for lenient mode.

---

## 🧩 Rules & Logic

**Q: How do I mark transactions for manual review?**  
A: Use `flags` or `status` in your rule set:  
```fin
rule "Review large withdrawals" {
  match:
    - amount <= -1000
  set:
    - flags += "review"
    - status = "pending"
}
```

**Q: Can I use OR logic in rules?**  
A: Not within a single rule. Each rule’s `match:` block uses **AND** logic across its conditions. To implement OR logic, write separate rules.

**Q: How can I ignore small transactions?**  
A: Either filter them out later using a spreadsheet or mark them with a flag:  
```fin
rule "Ignore micro‑transactions" {
  match:
    - abs(amount) < 1.00
  set:
    - flags += "ignore"
}
```

**Q: How can I test my rule set safely?**  
A: Use the `--headless` flag with `--audit audit.json --audit-mode full`. This writes the audit log without generating output files, ideal for CI/CD testing.

---

## 🧠 Workflows & Automation

**Q: What is the recommended daily workflow?**  
A: FinLang’s **Growth Loop** follows a three‑step process:  
1. `finlang-discover` — scans your data and identifies new counterparties  
2. `finlang-suggest` — generates draft rules from those discoveries  
3. `finlang` — applies updated rules to produce categorized output  

For details and cross‑platform merge commands, see [growth_loop_best_practices.md](growth_loop_best_practices.md).

**Q: How can I merge new rules safely?**  
A: Always review suggested rules before merging.  
```bash
# Linux/macOS/WSL
cat draft_rules.fin >> my_rules.fin

# Windows PowerShell
Get-Content draft_rules.fin | Add-Content my_rules.fin

# Windows CMD
type draft_rules.fin >> my_rules.fin
```

**Q: What is the recommended audit practice?**  
A: Use `--audit <file> --audit-mode lite` for normal runs, or `full` when debugging. The audit file records every transformation for reproducibility and compliance.

**Q: Can I automate FinLang in CI/CD?**  
A: Yes. FinLang supports headless operation. Example:  
```bash
finlang --input daily.csv --output categorized.csv   --rules production.fin --headless   --strict-parse --fail-threshold 0.02   --encoding auto --audit ci_audit.json --audit-mode lite
```

---

## ⚡ Performance

**Q: How fast is FinLang?**  
A: Approximately 24 K rows/sec on commodity hardware (5 M rows × 50 cols ≈ 208 seconds). See [benchmarks.md](benchmarks.md) for detailed data.

**Q: How can I speed it up?**  
A: 
- Use `--fastio` (20‑40 % faster with PyArrow)  
- Disable audit mode for production runs  
- Use `--audit-mode lite` instead of `full`

**Q: Does it work with very large files (10 M + rows)?**  
A: Yes. FinLang processes data in a streaming fashion and scales linearly.

---

## ⚠️ Troubleshooting

**Q: “Missing canonical field: amount” error**  
A: Your CSV headers don’t map to the canonical schema. Create a custom map or verify your input file.  
```
FATAL: Missing required columns after mapping: ['amount'].
       Provide a mapping JSON via --map or preprocess your CSV first.
```

**Q: "No such file or directory" error**  
A: Check your file paths. Use absolute paths or ensure you're in the correct directory. Example:  
```bash
# Relative path (must be in correct directory)
finlang --input bank.csv --output out.csv --rules rules.fin

# Absolute path (works from anywhere)
finlang --input C:\Users\You\Documents\bank.csv --output C:\Users\You\Documents\out.csv --rules rules.fin
```

**Q: Output amounts have the wrong sign.**  
A: Your file might use reversed debit/credit logic. Adjust your custom map or check [amount_synthesis.md](amount_synthesis.md).

**Q: I get “Malformed numeric value” errors.**  
A: Locale mismatch — use the correct `--decimal` and `--thousands` flags.

**Q: FinLang seems slow on large files.**  
A: Performance scales linearly. Expect ~24 K rows/s on commodity hardware with full audit mode. Disable `--audit` for faster runs.

**Q: Does `--fail-threshold` fail my CI run automatically?**  
A: Not in v0.6.4. The flag correctly detects and logs a **FATAL** error when the drop-rate threshold is exceeded, but it returns **exit code 0** instead of non-zero.

**Workaround for CI/CD:**
```bash
# Linux/macOS
finlang --input data.csv --output out.csv --rules rules.fin \
  --fail-threshold 0.05 2>&1 | tee run.log

if grep -q "FATAL: Dropped" run.log; then
  echo "Drop threshold exceeded"
  exit 1
fi
```
```powershell
# Windows PowerShell
finlang --input data.csv --output out.csv --rules rules.fin `
  --fail-threshold 0.05 2>&1 | Tee-Object -FilePath run.log

if (Select-String -Path run.log -Pattern "FATAL: Dropped") {
  Write-Host "Drop threshold exceeded"
  exit 1
}
```

This will be fixed in v0.7.

---

## 📚 Related Documentation

- [flags.md](flags.md) – All CLI flags and canonical formats  
- [i18n_examples.md](i18n_examples.md) – Regional format examples  
- [mapping_guide.md](mapping_guide.md) – How to align headers to schema  
- [amount_synthesis.md](amount_synthesis.md) – Logic for debit/credit synthesis  
- [rule_language.md](rule_language.md) – How to write and test rules  
- [growth_loop_best_practices.md](growth_loop_best_practices.md) – 3‑step discovery workflow  
- [cli_reference.md](cli_reference.md) – Complete command reference

---

© FinLang Ltd — v0.6.4.post1 (GA Rev 3)
