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


"""
Utilities for loading bundled maps & rulepacks from the installed package.
"""
from importlib import resources
from typing import List

def load_default_map_text() -> str:
    """Return the text of the default bank map (mapping/bank.map.json)."""
    return resources.files("finlang.mapping").joinpath("bank.map.json").read_text(encoding="utf-8")

def load_rulepack_text(filename: str) -> str:
    """Return the text of a rulepack file under finlang.rulepacks/."""
    return resources.files("finlang.rulepacks").joinpath(filename).read_text(encoding="utf-8")

def list_rulepacks() -> List[str]:
    """List available top-level files in finlang.rulepacks (non-recursive)."""
    pkg = resources.files("finlang.rulepacks")
    return sorted([p.name for p in pkg.iterdir() if p.is_file()])