# FinLang v0.9.2 — A Workbench that looks like the product, and every rules file you name
*Released: 18 November 2026*

---

## Summary

A Workbench release and one CLI fix.

- **The Workbench has a new look.** Light, calm screens, each named for its job and laid out as a few numbered steps. Click any categorised row to see why it landed there, and copy that explanation into a review note.
- **Repeating `--rules` now adds the files together.** Until now, only the last `--rules` counted, and the earlier files were dropped without a warning.

The engine's categorisation logic is unchanged. The daily test suite is unchanged at 204 tests across 10 gates, and the standalone API suite at 43. The standalone Workbench suites grow to 18 UI-contract and 99 end-to-end tests.

---

## What changed for you

### The redesigned Workbench

Run `finlang-ui` as before. The screens are:

| Screen | Was | What it does |
|---|---|---|
| **Categorise** | Run | Three numbered steps: your file, your rules, the checks. Then the results |
| **Rules** | Rules | Write or build rules; the engine reads them back in plain English |
| **Find gaps** | Growth loop | The counterparties no rule claimed, and draft rules for the ones you pick |
| **Test a change** | Impact | What a proposed rules change would move, before you ship it |

On Categorise, **Verify** and **Compare with another system** are switches. The audit trail is a select that defaults to Full, which is what puts the deciding rule on every row. Compare's new *How rows are paired* choice covers row by row (the default), identity check, and key matching.

Results open with a banner and tags. The **rows** ledger shows the rule that set each row's category. Click a row, or press Enter or Space on it, to open **Why this category**:
- every rule that matched, in the order it ran;
- what each one changed;
- which earlier result a later rule replaced;
- a **Copy explanation** button.

With the audit trail off, or past its entry limit on a large file (`FINLANG_AUDIT_MAX`, 5,000 by default), the Workbench can't show which rule decided a category, and says so rather than guessing. With the light audit trail, the drawer lists only the rules that changed something.

Categorise and Test a change show the equivalent command, so those runs can be scripted. Nothing about where the Workbench runs has changed. It is served from `127.0.0.1` on your machine, and its pages make no external requests. The HTTP API's interactive docs at `/docs` are FastAPI's own and load Swagger UI from a CDN, as before.

### Repeated `--rules` adds the files together

```bash
finlang --input bank.csv --output out.csv --rules base.fin --rules banking.fin
```

On v0.9.1 and earlier, this loaded only `banking.fin`: each `--rules` replaced the one before. The earlier files were dropped without a warning, and a missing file in an earlier group wasn't reported. Now:
- every file named loads, in command-line order;
- a missing file in any group is fatal (exit 2).

Order matters because rules run in file order, and when several rules set the category, the last one decides.

Listing several files after one flag (`--rules base.fin banking.fin`) worked before and still does. That form also works on every version, so use it in scripts that may run on an older FinLang. Combining either form with `--include-pack` is unchanged. This is a CLI change only: the HTTP API sends one rules file per request.

The Banking Pack's quick start used the repeated form and ran 1 of its 3 files. The pack's README and `docs/commercial_rulepacks/banking_pack_v1.md` now use the single-flag form.

### Two Workbench fixes from 0.9.1

- **Find gaps:** switching from a carried-over Categorise output to a fresh file failed and did nothing. It now uses the fresh file.
- **Test a change:** the engine-summary table showed nested values as `[object Object]` and pushed the page about 1,700px wide. Nested values are now a collapsible JSON block.

---

## Upgrading

```bash
pip install -U finlang
```

No configuration changes. If a Workbench page looks half-styled after the upgrade, press `Ctrl+F5` once. Your browser kept a file from the older version. From this version on, `/ui` is served with `Cache-Control: no-cache`, so the browser re-checks each load.

---

## Tests

- `tests/test_cli_smoke.py` 11 → 13: repeated `--rules` applies both files in order. A missing named rules file is fatal whether it sits in the first or a later group.
- Standalone Workbench suites: UI-contract 17 → 18, which adds the `/ui` `Cache-Control` header. Playwright end-to-end 10 → 99, driving the redesigned screens in a real browser against a live server and the real CLI.
- Standalone API suite unchanged at 43. Daily gate unchanged at 204 tests / 10 gates.
