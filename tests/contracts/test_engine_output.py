import ast
from pathlib import Path
import pytest

def test_cli_writes_back_all_fields(contract):
    """
    Static analysis of run_finlang.py to ensure the write-back loop 
    ('for col in (...)') includes all mutable fields.
    """
    repo_root = Path(__file__).parents[2]
    cli_path = repo_root / "src" / "finlang" / "cli" / "run_finlang.py"
    
    tree = ast.parse(cli_path.read_text(encoding="utf-8"))
    
    found_writeback_cols = set()
    
    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            # looking for: for col in ("category", "flags", ...)
            if isinstance(node.iter, ast.Tuple):
                # We found a loop over a tuple. 
                cols = {elt.value for elt in node.iter.elts if isinstance(elt, ast.Constant)}
                if not cols:
                     cols = {elt.s for elt in node.iter.elts if hasattr(elt, 's')}
                
                # Heuristic: if it has 'category' and 'flags', it's our loop
                if "category" in cols and "flags" in cols:
                    found_writeback_cols = cols
                    break
    
    required_outputs = set(contract["engine_output"])
    missing = required_outputs - found_writeback_cols
    
    assert not missing, f"CLI is discarding updates to these fields: {missing}"