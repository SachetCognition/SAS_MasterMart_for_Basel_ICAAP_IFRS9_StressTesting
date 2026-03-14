"""Unit tests for lib/macros.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.macros import auto_rpt_month


def test_auto_rpt_month_format():
    """auto_rpt_month returns YYYYMM string."""
    result = auto_rpt_month()
    assert len(result) == 6
    assert result.isdigit()
    int_year = int(result[:4])
    int_month = int(result[4:])
    assert 2000 <= int_year <= 2099
    assert 1 <= int_month <= 12
