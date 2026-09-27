# FinLang v0.9.1 — A clean run log, and a guard that covers every column
*Released: 27 September 2026*

---

## Summary

A patch release for the Workbench and the CSV formula-injection guard.

- **The Workbench's "Engine output" is clean again.** On pandas 3, which a fresh `pip install finlang` now resolves, every Workbench run showed a pandas deprecation warning that included the full path to your Python installation. It's gone.
- **The formula-injection guard covers every text column type**, on pandas 2 and pandas 3. One column type was previously missed on pandas 2. This is a deliberate, small output change (below).

The engine's categorisation logic is unchanged. Daily test suite unchanged at 204 tests across 10 gates; standalone API suite 42 → 43; four new cross-version tests run in CI on both pandas majors.

---

## What changed for you

### The run log no longer shows your install path

Since 0.9.0 the Workbench server runs the engine as `python -m finlang.cli.run_finlang`, so it can only ever run the FinLang it was installed with. A side effect: Python prints deprecation warnings raised by the program it runs directly, and on pandas 3 the guard below raised one on every run. The Workbench shows the engine's stderr as "Engine output", so the warning, with the path to your Python installation (on Windows that usually includes your username), appeared on every run.

Nothing was sent anywhere; it was displayed locally. But it looked like a fault, and a screenshot of the run log would have shared the path. The `finlang` command itself never showed it.

### The CSV formula-injection guard covers every text column

When FinLang writes a CSV, cells that start with `=`, `+`, `-`, `@` or a tab get a leading `'`, so a spreadsheet opens them as text rather than as a formula. The guard found its columns with `select_dtypes(include="object")`:

- On **pandas 3** that raised the warning above. pandas has also deprecated the behaviour that let `"object"` still match pandas 3's text columns, so the guard would have gone quiet on a later pandas.
- On **pandas 2** it never matched columns of pandas' nullable `string` type, so formula-leading cells in those columns went out unescaped.

Both guards (`finlang` and `finlang-discover`, which powers the Workbench's Growth loop) now use pandas' documented cross-version form, `include=["object", "string"]`.

**Output change:** formula-leading cells in nullable-`string` columns are now escaped like every other text column. Standard CSV input produces no such columns, and the golden-master fixtures are unchanged, so most users will see no difference in their output files.

---

## Upgrading

```bash
pip install -U finlang
```

No configuration changes. `FINLANG_SAFE_TEXT=0` still disables the guard for benchmark runs, as before.

---

## Tests

- `tests/test_cli_smoke.py`: four cross-version tests. A categorise run and a discover run, both through `python -m` (the Workbench's own path), must leave stderr empty and escape formula-leading cells, including a pass-through column and discover's example names. Both guards are also checked directly against inferred, `object` and nullable-`string` columns, with warnings treated as errors. CI runs this file on pandas 2 (Python 3.10) and pandas 3 (Python 3.11+).
- Standalone API suite 42 → 43: a clean `/process` and `/discover` return an empty "Engine output".
- Full pre-release suite 7/7; standalone API + Workbench suites 70/70.
