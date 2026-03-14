"""Unit tests for lib/excel_reader.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.excel_reader import _classify_column_type


def test_classify_numeric_columns():
    """Numeric keyword columns detected correctly."""
    assert _classify_column_type("TOTAL_AMT") == "numeric"
    assert _classify_column_type("RISKWEIGHT") == "numeric"
    assert _classify_column_type("CCF") == "numeric"
    assert _classify_column_type("EXPOSURE") == "numeric"


def test_classify_date_columns():
    """Date keyword columns detected correctly."""
    assert _classify_column_type("TDATE") == "date1"
    assert _classify_column_type("VDATE") == "date1"
    assert _classify_column_type("MDATE") == "date1"
    assert _classify_column_type("OS_DATE") == "date2"


def test_classify_string_default():
    """Unknown columns default to string."""
    assert _classify_column_type("CUST_NAME") == "string"
    assert _classify_column_type("ACCT_ID") == "string"
