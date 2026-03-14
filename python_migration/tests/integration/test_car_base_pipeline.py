"""Integration tests for CAR_BASE pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def test_car_base_modules_import():
    """Verify all car_base modules can be imported."""
    from modules.car_base import (
        l01_fact_rwa,
    )
    assert hasattr(l01_fact_rwa, "run")
