"""Unit tests for lib/datasets.py."""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.datasets import add_field_suffix


def test_add_field_suffix_basic():
    """add_field_suffix renames non-key columns with suffix."""
    df = pl.DataFrame({
        "KEY1": [1, 2],
        "KEY2": ["a", "b"],
        "VAL1": [10, 20],
        "VAL2": [30, 40],
    })
    result = add_field_suffix(df, "_ST0", key_fields=["KEY1", "KEY2"])
    assert "KEY1" in result.columns
    assert "KEY2" in result.columns
    assert "VAL1_ST0" in result.columns
    assert "VAL2_ST0" in result.columns
    assert "VAL1" not in result.columns


def test_add_field_suffix_empty_keys():
    """All columns renamed when no keys specified."""
    df = pl.DataFrame({"A": [1], "B": [2]})
    result = add_field_suffix(df, "_X", key_fields=[])
    assert "A_X" in result.columns
    assert "B_X" in result.columns
