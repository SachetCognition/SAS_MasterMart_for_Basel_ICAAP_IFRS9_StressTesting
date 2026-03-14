"""Unit tests for lib/validation.py."""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.validation import PipelineValidator


def test_pipeline_validator_identical():
    """Identical DataFrames produce matching report."""
    df = pl.DataFrame({"KEY": [1, 2, 3], "VAL": [10.0, 20.0, 30.0]})
    validator = PipelineValidator()
    # Save to CSV to simulate SAS output
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        df.write_csv(f.name)
        report = validator.compare_datasets(f.name, df, key_columns=["KEY"])

    assert report.row_count_match
    assert report.column_names_match
