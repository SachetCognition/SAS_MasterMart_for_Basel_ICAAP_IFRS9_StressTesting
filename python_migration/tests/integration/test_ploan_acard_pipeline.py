"""Integration tests for PLOAN ACARD pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def test_ploan_acard_modules_import():
    """Verify all ploan_acard modules can be imported."""
    from modules.ploan_acard import (
        f01_aps,
        l01_fact,
    )
    assert hasattr(f01_aps, "run")
    assert hasattr(l01_fact, "run")
