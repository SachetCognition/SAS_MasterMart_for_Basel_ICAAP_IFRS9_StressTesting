"""Integration tests for RP Segment pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def test_rp_segment_modules_import():
    """Verify all rp_segment modules can be imported."""
    from modules.rp_segment import (
        f04_parameter,
        f05_segment,
    )
    assert hasattr(f04_parameter, "run")
    assert hasattr(f05_segment, "run")
