import ast
from pathlib import Path
import pytest

def test_cli_passes_all_fields_to_engine(contract):
    """
    Static analysis of run_finlang.py to ensure engine_cols list 
    includes all required fields defined in the contract.
    """
    # Locate run_finlang.py relative to this test file
    repo_root = Path(__file__).parents[2] 
    cli_path = repo_root / "src" / "finlang" / "cli" / "run_finlang.py"
    
    if not cli_path.exists():
        pytest.fail(f"Could not find run_finlang.py at {cli_path}")

    tree = ast.parse(cli_path.read_text(encoding="utf-8"))
    
    # Find the list assignment: engine_cols = [...]
    found_cols = set()
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "engine_cols":
                    # We found the assignment. Look inside the ListComp
                    if isinstance(node.value, ast.ListComp):
                        iterator = node.value.generators[0].iter
                        if isinstance(iterator, ast.List):
                            # Python 3.8+ uses ast.Constant
                            found_cols = {elt.value for elt in iterator.elts if isinstance(elt, ast.Constant)}
                            # Fallback for older python ast if needed
                            if not found_cols:
                                found_cols = {elt.s for elt in iterator.elts if hasattr(elt, 's')}
    
    # Assertions
    required_inputs = set(contract["engine_input"])
    missing = required_inputs - found_cols
    
    assert not missing, f"CLI is failing to pass these fields to Engine: {missing}"