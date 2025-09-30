import json, subprocess, sys, tempfile, os, csv, pathlib

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