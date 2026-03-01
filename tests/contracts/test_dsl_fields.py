import sys
from pathlib import Path
import pytest

# Add src to sys.path to allow import of the engine module
repo_root = Path(__file__).parents[2]
sys.path.insert(0, str(repo_root / "src"))

from finlang.engine.finlang_engine import CANON_FIELDS_MATCH, CANON_FIELDS_SET

def test_engine_match_fields_align_with_contract(contract):
    expected = set(contract["matchable"])
    actual = CANON_FIELDS_MATCH
    
    # Check for drift
    missing = expected - actual
    extra = actual - expected
    
    assert not missing, f"Contract requires matching on {missing}, but Engine lacks it."
    assert not extra, f"Engine supports matching {extra}, but Contract (and likely Docs) don't list it."

def test_engine_set_fields_align_with_contract(contract):
    expected = set(contract["settable"])
    actual = CANON_FIELDS_SET
    
    missing = expected - actual
    extra = actual - expected
    
    assert not missing, f"Contract requires setting {missing}, but Engine lacks it."
    assert not extra, f"Engine supports setting {extra}, but Contract (and likely Docs) don't list it."