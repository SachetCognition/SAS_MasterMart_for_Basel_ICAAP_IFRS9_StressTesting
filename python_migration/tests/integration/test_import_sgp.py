"""Integration tests for extract/import_basel_sgp.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def test_import_sgp_module_loads():
    """Verify import_basel_sgp module can be imported."""
    from extract import import_basel_sgp
    assert hasattr(import_basel_sgp, "import_all_sgp")
