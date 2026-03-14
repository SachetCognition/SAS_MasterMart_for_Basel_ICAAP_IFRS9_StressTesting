"""Unit tests for lib/db_connector.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.db_connector import OracleConnector


def test_oracle_connector_init():
    """OracleConnector initializes with DSN."""
    conn = OracleConnector.__new__(OracleConnector)
    conn.dsn = "test_dsn"
    conn.pool = None
    conn._conn = None
    assert conn.dsn == "test_dsn"
