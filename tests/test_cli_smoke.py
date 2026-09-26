# FinLang — Financial Rules DSL
# Copyright (C) 2025 FinLang Ltd
#
# This file is part of FinLang.
#
# FinLang is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, version 3.
#
# FinLang is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with FinLang.  If not, see <https://www.gnu.org/licenses/>.
#
# Commercial licensing is available. Contact FinLang Ltd for terms.
#
# FinLang™ is a trademark of FinLang Ltd.


import json, subprocess, sys, tempfile, os, csv, pathlib
import importlib, warnings

import pandas as pd
import pytest

BIN = "finlang"  # Assumes installed entry point

def run(cmd):
    """Helper to run CLI commands and assert success."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(f"cmd failed: {cmd}\n\nSTDOUT:\n{r.stdout}\n\nSTDERR:\n{r.stderr}")
    return r

def test_cli_runs_on_onecol(tmp_path):
    """Tests a basic run with a valid canonical CSV, rules, and audit."""
    data = tmp_path/"onecol.csv"
    # FIX: Provide all required columns: date, counterparty, and amount.
    data.write_text("date,counterparty,amount\n2025-01-01,TESCO,-10.50\n", encoding="utf-8")
    
    out = tmp_path/"out.csv"
    audit = tmp_path/"audit.json"
    rules = tmp_path/"rules.fin"
    rules.write_text('rule "tesco" { match: - counterparty ~ "*TESCO*" set: - category = "Groceries" }', encoding="utf-8")

    cmd = f'{BIN} --input "{data}" --output "{out}" --rules "{rules}" --include-pack sanity --audit "{audit}" --audit-mode lite'
    run(cmd)

    # Output exists and has the same row count
    rows = list(csv.reader(out.read_text(encoding="utf-8").splitlines()))
    assert len(rows) == 2  # header + 1 row

    # Audit exists and is a JSON list
    audit_obj = json.loads(audit.read_text(encoding="utf-8"))
    assert isinstance(audit_obj, list)

def test_drcr_synthesizes_amount(tmp_path):
    """Tests that 'amount' is correctly synthesized from debit/credit columns."""
    data = tmp_path/"drcr.csv"
    data.write_text("date,counterparty,credit,debit\n2025-01-02,TEST_CREDIT,10.00,\n2025-01-03,TEST_DEBIT,,5.50\n", encoding="utf-8")
    out = tmp_path/"out.csv"
    rules = tmp_path/"rules.fin"
    rules.write_text('rule "all" { match: - counterparty ~ "*" set: - flags += "seen" }', encoding="utf-8")

    cmd = f'{BIN} --input "{data}" --output "{out}" --rules "{rules}" --audit-mode none'
    run(cmd)

    text = out.read_text(encoding="utf-8")
    assert "amount" in text  # synthesized column present

def test_regex_wildcard_no_flags_crash_py313(tmp_path):
    """
    Regression: avoid 'Cannot pass flags that do not match pat.flags' on Python 3.13+
    when evaluating ~ wildcards via pandas string ops.
    """
    data = tmp_path/"crash_repro.csv"
    data.write_text(
        "date,counterparty,amount\n"
        "2025-01-01,M&S MARKS AND SPENCER LONDON,-10.00\n",
        encoding="utf-8"
    )

    rules = tmp_path / "crash.fin"
    # Use multi-line format to ensure robust parsing
    rules.write_text(
        'rule "CrashTest" {\n'
        '    match:\n'
        '        - counterparty ~ "*MARKS*SPENCER*"\n'
        '    set:\n'
        '        - category = "Groceries"\n'
        '}',
        encoding="utf-8"
    )

    out = tmp_path/"out.csv"
    cmd = f'{BIN} --input "{data}" --output "{out}" --rules "{rules}" --audit-mode none'
    run(cmd)

    rows = list(csv.reader(out.read_text(encoding="utf-8").splitlines()))
    header = rows[0]
    assert "category" in header
    cat_idx = header.index("category")
    assert rows[1][cat_idx] == "Groceries"

# ---------------------------------------------------------------------------
# Rules-source hardening (4-Jul sweep, Branch 3): a NAMED rules source that
# cannot be loaded is a fatal validation error (exit 2), never a warn-and-
# continue -- partial categorisation with exit 0 is an audit-integrity bug.
# ---------------------------------------------------------------------------

def _write_min_fixtures(tmp_path):
    data = tmp_path / "in.csv"
    data.write_text("date,amount,counterparty\n2026-01-05,-12.50,ACME TAXI\n", encoding="utf-8")
    rules = tmp_path / "good.fin"
    rules.write_text(
        'rule "taxi" {\n  match:\n    - counterparty ~ "*TAXI*"\n'
        '  set:\n    - category = "Transport"\n}\n', encoding="utf-8")
    return data, rules


def test_missing_named_rules_file_is_fatal(tmp_path):
    data, rules = _write_min_fixtures(tmp_path)
    out = tmp_path / "out.csv"
    r = subprocess.run(
        f'{BIN} --input "{data}" --output "{out}" --rules "{rules}" "{tmp_path / "typo.fin"}" --headless',
        shell=True, capture_output=True, text=True)
    assert r.returncode == 2, (
        f"missing named rules file must be fatal (exit 2), got {r.returncode}; "
        f"partial rules + exit 0 silently omits categorisation.\nstderr: {r.stderr}"
    )
    assert "not found" in (r.stderr + r.stdout).lower()


def test_unknown_include_pack_is_fatal(tmp_path):
    data, rules = _write_min_fixtures(tmp_path)
    out = tmp_path / "out.csv"
    r = subprocess.run(
        f'{BIN} --input "{data}" --output "{out}" --rules "{rules}" --include-pack no_such_pack --headless',
        shell=True, capture_output=True, text=True)
    assert r.returncode == 2, (
        f"unknown --include-pack must be fatal (exit 2), got {r.returncode}.\n"
        f"stderr: {r.stderr}"
    )
    assert "unknown pack" in (r.stderr + r.stdout).lower()


def test_help_renders_for_every_entry_point():
    """--help must render for every console entry point.

    Regression guard (26 Jul 2026): argparse %-formats help strings, so an
    unescaped literal like '%d/%m/%Y' in a help= string raises
    "TypeError: %d format: a real number is required, not dict" and takes
    --help down completely. That shipped through a 200-test daily gate and a
    7/7 full suite untouched, because nothing ran --help.

    Cheap to keep, and it covers the entire flag surface at once: any future
    help string with a stray % fails here instead of in a user's terminal.
    """
    for entry in ("finlang", "finlang-discover", "finlang-suggest"):
        result = subprocess.run(
            [entry, "--help"], capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0, (
            f"{entry} --help exited {result.returncode}:\n{result.stderr}"
        )
        assert "Traceback" not in result.stderr, (
            f"{entry} --help raised:\n{result.stderr}"
        )
        assert "usage:" in result.stdout.lower(), (
            f"{entry} --help produced no usage block:\n{result.stdout[:400]}"
        )


def test_audit_max_env_var_is_validated(tmp_path):
    """FINLANG_AUDIT_MAX must be validated, not crash or silently corrupt.

    Regression guard (Codex review, 26 Jul 2026): `int(os.getenv(...))` at
    module import meant a non-integer value produced a raw ValueError
    traceback during import, and a negative value was accepted -- silently
    disabling audit capping arithmetic. Both are now a clean FATAL exit 2.
    """
    data, rules = _write_min_fixtures(tmp_path)
    out = tmp_path / "out.csv"
    cmd = f'{BIN} --input "{data}" --output "{out}" --rules "{rules}" --audit-mode none --headless'

    for bad in ("abc", "-5"):
        env = dict(os.environ, FINLANG_AUDIT_MAX=bad)
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
        combined = r.stdout + r.stderr
        assert r.returncode == 2, (
            f"FINLANG_AUDIT_MAX={bad!r} must be fatal (exit 2), got "
            f"{r.returncode}.\nstderr: {r.stderr}")
        assert "FINLANG_AUDIT_MAX" in combined, combined
        assert "Traceback" not in r.stderr, (
            f"validation must be a clean FATAL, not a traceback:\n{r.stderr}")

    # A valid override still works end-to-end.
    env = dict(os.environ, FINLANG_AUDIT_MAX="9000")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
    assert r.returncode == 0, (
        f"valid FINLANG_AUDIT_MAX must not fail: exit {r.returncode}\n{r.stderr}")


# ---------------------------------------------------------------------------
# pandas 3 string migration (26 Sep 2026, v0.9.1). Both CSV formula-injection
# guards (_csv_safe_text in run_finlang.py and discover.py) picked their text
# columns with select_dtypes(include="object"). On pandas 3 that emits a
# Pandas4Warning on every run -- which the Workbench prints in its run log,
# user's install path included -- and pandas has deprecated the very behaviour
# that lets "object" still match pandas 3's 'str' columns, so the guard would
# go quiet on a later pandas. Fix: pandas' documented cross-version form,
# include=["object", "string"].
# CI runs this file on pandas 2 (Python 3.10) and pandas 3 (3.11+), so these
# pin both properties on both majors: no warning, and dangerous cells escaped.
# ---------------------------------------------------------------------------

# "reference" is not a canonical field: the engine normalises the canonical
# columns itself (they reach the write step as object), but an extra column
# passes through untouched, so on pandas 3 it arrives at the guard as 'str'
# dtype. Without it this run never touches the pandas 3 path at all.
_DANGER_ROWS = (
    "date,amount,counterparty,memo,reference\n"
    "2026-01-05,-12.50,=HYPERLINK(1) TAXI,@SUM(A1),-REF-001\n"
    "2026-01-06,-8.20,NORMAL VENDOR LTD,+cmd,INV-2\n"
)


# These run the engine exactly as the API/Workbench does: `python -m <module>`.
# That matters: Pandas4Warning is a DeprecationWarning, which Python only
# prints by default when raised from __main__ -- so the `finlang` console
# script stays silent while `-m` (the Workbench's path since 23 Sep 2026)
# shows it. Testing through the console script would miss the real symptom.

def test_clean_run_is_warning_free_and_guards_formulas(tmp_path):
    """A clean categorise run leaves stderr empty (the Workbench shows stderr
    to the user as "Engine output") and still escapes formula-leading cells,
    including in a pass-through column."""
    data, rules = _write_min_fixtures(tmp_path)
    data.write_text(_DANGER_ROWS, encoding="utf-8")
    out = tmp_path / "out.csv"
    r = subprocess.run(
        [sys.executable, "-m", "finlang.cli.run_finlang", "--input", str(data),
         "--output", str(out), "--rules", str(rules), "--audit-mode", "none", "--headless"],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stderr.strip() == "", f"a clean run must leave stderr empty:\n{r.stderr}"
    rows = list(csv.DictReader(out.read_text(encoding="utf-8").splitlines()))
    assert rows[0]["counterparty"] == "'=HYPERLINK(1) TAXI"
    assert rows[0]["memo"] == "'@SUM(A1)"
    assert rows[1]["memo"] == "'+cmd"
    assert rows[0]["reference"] == "'-REF-001"
    assert rows[1]["reference"] == "INV-2"


def test_discover_run_is_warning_free(tmp_path):
    """Discover (the Workbench's Growth loop) runs the same guard over its
    candidate files; a clean run leaves stderr empty too. Its input is
    categorised output, so rows carry an (empty) category column."""
    data = tmp_path / "in.csv"
    data.write_text(
        "date,amount,counterparty,memo,reference,category\n"
        "2026-01-05,-12.50,=HYPERLINK(1) TAXI,@SUM(A1),-REF-001,\n"
        + "2026-01-07,-9.10,NORMAL VENDOR LTD,again,INV-3,\n" * 5,
        encoding="utf-8")
    cand, allc = tmp_path / "cand.csv", tmp_path / "all.csv"
    r = subprocess.run(
        [sys.executable, "-m", "finlang.tools.discover", "--input", str(data),
         "--candidates", str(cand), "--all-candidates", str(allc),
         "--min-count", "1", "--headless"],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stderr.strip() == "", f"a clean discover must leave stderr empty:\n{r.stderr}"
    rows = list(csv.DictReader(allc.read_text(encoding="utf-8").splitlines()))
    names = {row["example_counterparty_name"] for row in rows}
    assert "'=HYPERLINK(1) TAXI" in names, names   # raw example name, escaped


@pytest.mark.parametrize("module", ["finlang.cli.run_finlang", "finlang.tools.discover"])
def test_csv_guard_escapes_every_text_dtype_warning_free(module):
    """Both guards, every text dtype pandas 2 or 3 can hand them: the column
    pandas infers for plain strings (object on 2, 'str' on 3), an explicit
    object column, and the nullable "string" dtype. No warning, all escaped,
    numbers untouched."""
    guard = importlib.import_module(module)._csv_safe_text
    df = pd.DataFrame({
        "inferred": ["=1+1", "ok"],
        "object": pd.Series(["@SUM(A1)", "ok"], dtype=object),
        "string": pd.Series(["+cmd", pd.NA], dtype="string"),
        "amount": [-12.5, 3.0],
    })
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = guard(df)
    assert out["inferred"].tolist() == ["'=1+1", "ok"]
    assert out["object"].tolist() == ["'@SUM(A1)", "ok"]
    assert out["string"].iloc[0] == "'+cmd"
    assert out["amount"].tolist() == [-12.5, 3.0]
