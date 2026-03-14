"""
Pytest configuration and shared fixtures for the SAS-to-Python migration test suite.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure python_migration is on the path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def sample_config():
    """Return a Config instance with test defaults."""
    from config.settings import Config

    return Config(
        rpt_month="201412",
        ind_icaap="Y",
    )


@pytest.fixture
def tmp_artifacts(tmp_path):
    """Return a temporary directory for test artifacts."""
    d = tmp_path / "artifacts"
    d.mkdir()
    return d
