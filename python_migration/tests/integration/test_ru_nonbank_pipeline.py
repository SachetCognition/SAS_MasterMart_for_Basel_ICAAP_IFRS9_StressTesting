"""Integration tests for RU Non-Bank pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def test_ru_nonbank_modules_import():
    """Verify all ru_nonbank modules can be imported."""
    from modules.ru_nonbank import (
        m01_npl_ratio_by_bu,
    )
    assert hasattr(m01_npl_ratio_by_bu, "run")
