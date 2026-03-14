"""Integration tests for BIS Check pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def test_bis_check_modules_import():
    """Verify all bis_check modules can be imported."""
    from modules.bis_check import (
        f01_bis_gen_info,
    )
    assert hasattr(f01_bis_gen_info, "run")
