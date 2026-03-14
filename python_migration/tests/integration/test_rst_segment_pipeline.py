"""Integration tests for RST Segment pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def test_rst_segment_modules_import():
    """Verify all rst_segment modules can be imported."""
    from modules.rst_segment import (
        f04_parameter,
    )
    assert hasattr(f04_parameter, "run")
