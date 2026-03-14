"""Integration tests for ST Country FI pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def test_st_country_fi_modules_import():
    """Verify all st_country_fi modules can be imported."""
    from modules.st_country_fi import l01_base, m01_base, r01_summary
    assert hasattr(l01_base, "run")
    assert hasattr(m01_base, "run")
    assert hasattr(r01_summary, "run")
