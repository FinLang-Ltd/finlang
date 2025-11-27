import pytest
import yaml
from pathlib import Path

@pytest.fixture(scope="session")
def contract():
    """Loads the canonical field definition."""
    path = Path(__file__).parent / "canonical_fields.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)