"""Unit tests for lib/lookups.py."""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.lookups import BUSUNIT_MAP, PORT_RW_MAP, PORTCD_MAP, apply_lookup


def test_portcd_map_complete():
    """PORTCD_MAP has required entries."""
    assert PORTCD_MAP["Ia"] == "01. Sovereign"
    assert PORTCD_MAP["IV"] == "04. Bank"
    assert PORTCD_MAP["IX"] == "09. RML"


def test_busunit_map():
    """BUSUNIT_MAP has required entries."""
    assert "CBG" in BUSUNIT_MAP
    assert "CBIC" in BUSUNIT_MAP


def test_port_rw_map():
    """PORT_RW_MAP has required entries."""
    assert "Ia_0" in PORT_RW_MAP
    assert PORT_RW_MAP["Ia_0"] == 1


def test_apply_lookup():
    """apply_lookup maps values correctly."""
    df = pl.DataFrame({"PORT_CD": ["Ia", "IV", "UNKNOWN"]})
    result = apply_lookup(df, "PORT_CD", PORTCD_MAP, default="99. ###")
    vals = result["PORT_CD_MAPPED"].to_list()
    assert vals[0] == "01. Sovereign"
    assert vals[1] == "04. Bank"
    assert vals[2] == "99. ###"
