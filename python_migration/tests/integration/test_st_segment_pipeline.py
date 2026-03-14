"""Integration tests for ST Segment pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def test_st_segment_modules_import():
    """Verify all st_segment modules can be imported."""
    from modules.st_segment import (
        f01_parameter,
    )
    assert hasattr(f01_parameter, "run")
