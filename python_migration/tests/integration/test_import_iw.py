"""Integration tests for extract/import_iw.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def test_import_iw_module_loads():
    """Verify import_iw module can be imported."""
    from extract import import_iw
    assert hasattr(import_iw, "import_all_iw_views")
