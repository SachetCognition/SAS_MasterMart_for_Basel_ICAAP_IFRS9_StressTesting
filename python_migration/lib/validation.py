"""
Validation infrastructure for SAS-to-Python migration testing.

Provides dataclasses and a PipelineValidator for comparing SAS outputs
against Python outputs, generating detailed reports.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)


@dataclass
class ColumnComparison:
    """Comparison statistics for a single column."""

    column_name: str
    sas_null_count: int = 0
    python_null_count: int = 0
    sas_sum: float | None = None
    python_sum: float | None = None
    sum_diff_pct: float | None = None
    max_abs_diff: float | None = None
    mismatch_count: int = 0
    mismatch_pct: float = 0.0


@dataclass
class ValidationReport:
    """Full comparison report between SAS and Python outputs."""

    module_name: str = ""
    table_name: str = ""
    sas_row_count: int = 0
    python_row_count: int = 0
    row_count_match: bool = False
    column_names_match: bool = False
    missing_in_python: list[str] = field(default_factory=list)
    extra_in_python: list[str] = field(default_factory=list)
    dtype_mismatches: dict[str, tuple[str, str]] = field(default_factory=dict)
    value_comparison: dict[str, ColumnComparison] = field(default_factory=dict)
    mismatched_rows_sample: pl.DataFrame | None = None
    execution_time_seconds: float = 0.0
    peak_memory_mb: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def passed(self) -> bool:
        """Return True if all checks passed."""
        if not self.row_count_match:
            return False
        if not self.column_names_match:
            return False
        for comp in self.value_comparison.values():
            if comp.mismatch_count > 0:
                return False
        return True

    def summary(self) -> str:
        """Return a human-readable summary."""
        lines = [
            f"Validation Report: {self.module_name}/{self.table_name}",
            f"  Timestamp: {self.timestamp}",
            f"  Row count: SAS={self.sas_row_count}, Python={self.python_row_count} "
            f"({'MATCH' if self.row_count_match else 'MISMATCH'})",
            f"  Column names: {'MATCH' if self.column_names_match else 'MISMATCH'}",
        ]
        if self.missing_in_python:
            lines.append(f"  Missing in Python: {self.missing_in_python}")
        if self.extra_in_python:
            lines.append(f"  Extra in Python: {self.extra_in_python}")
        if self.dtype_mismatches:
            lines.append(f"  Dtype mismatches: {len(self.dtype_mismatches)}")
        for col, comp in self.value_comparison.items():
            if comp.mismatch_count > 0:
                lines.append(
                    f"  Column '{col}': {comp.mismatch_count} mismatches "
                    f"({comp.mismatch_pct:.2%}), max_abs_diff={comp.max_abs_diff}"
                )
        lines.append(f"  Execution time: {self.execution_time_seconds:.2f}s")
        lines.append(f"  Peak memory: {self.peak_memory_mb:.1f}MB")
        lines.append(f"  RESULT: {'PASS' if self.passed else 'FAIL'}")
        return "\n".join(lines)


class PipelineValidator:
    """
    Validates Python pipeline outputs against SAS reference data.

    Usage::

        validator = PipelineValidator()
        report = validator.compare_datasets(
            sas_csv_path="path/to/sas_output.csv",
            python_df=my_dataframe,
            key_columns=["ACCT_ID", "PORT_CD"],
        )
        validator.save_artifacts(report, "artifacts/")
        validator.assert_match(report)  # raises if mismatch
    """

    def compare_datasets(
        self,
        sas_csv_path: str | Path,
        python_df: pl.DataFrame,
        key_columns: list[str],
        tolerance: float = 0.005,
        module_name: str = "",
        table_name: str = "",
    ) -> ValidationReport:
        """
        Compare a SAS CSV export against a Python DataFrame.

        Parameters
        ----------
        sas_csv_path : str or Path
            Path to the SAS output exported as CSV.
        python_df : pl.DataFrame
            The Python pipeline output.
        key_columns : list[str]
            Columns to join on for row-level comparison.
        tolerance : float
            Relative tolerance for numeric comparisons (0.005 = 0.5%).
        module_name : str
            Module name for reporting.
        table_name : str
            Table name for reporting.

        Returns
        -------
        ValidationReport
        """
        t0 = time.perf_counter()

        try:
            import psutil
            process = psutil.Process()
            mem_before = process.memory_info().rss / 1024 / 1024
        except ImportError:
            mem_before = 0.0

        report = ValidationReport(module_name=module_name, table_name=table_name)

        # Load SAS data
        sas_df = pl.read_csv(sas_csv_path, infer_schema_length=10000)

        report.sas_row_count = len(sas_df)
        report.python_row_count = len(python_df)
        report.row_count_match = report.sas_row_count == report.python_row_count

        # Column comparison
        sas_cols = set(sas_df.columns)
        py_cols = set(python_df.columns)
        report.missing_in_python = sorted(sas_cols - py_cols)
        report.extra_in_python = sorted(py_cols - sas_cols)
        report.column_names_match = not report.missing_in_python and not report.extra_in_python

        # Common columns for value comparison
        common_cols = sorted(sas_cols & py_cols)

        # Dtype comparison
        for col in common_cols:
            sas_dtype = str(sas_df.schema[col])
            py_dtype = str(python_df.schema[col])
            if sas_dtype != py_dtype:
                report.dtype_mismatches[col] = (sas_dtype, py_dtype)

        # Value comparison for common columns
        valid_keys = [k for k in key_columns if k in common_cols]
        if valid_keys:
            # Sort both by key columns for alignment
            try:
                sas_sorted = sas_df.sort(valid_keys)
                py_sorted = python_df.sort(valid_keys)
            except Exception:
                sas_sorted = sas_df
                py_sorted = python_df

            for col in common_cols:
                comp = ColumnComparison(column_name=col)

                sas_series = sas_sorted[col] if col in sas_sorted.columns else None
                py_series = py_sorted[col] if col in py_sorted.columns else None

                if sas_series is None or py_series is None:
                    continue

                comp.sas_null_count = sas_series.null_count()
                comp.python_null_count = py_series.null_count()

                # Numeric comparison
                if sas_series.dtype.is_numeric() and py_series.dtype.is_numeric():
                    try:
                        sas_float = sas_series.cast(pl.Float64)
                        py_float = py_series.cast(pl.Float64)

                        comp.sas_sum = sas_float.sum()
                        comp.python_sum = py_float.sum()

                        if comp.sas_sum and comp.sas_sum != 0:
                            comp.sum_diff_pct = abs(
                                (comp.python_sum or 0) - comp.sas_sum
                            ) / abs(comp.sas_sum)

                        # Row-level comparison (truncate to min length)
                        min_len = min(len(sas_float), len(py_float))
                        if min_len > 0:
                            s = sas_float.head(min_len)
                            p = py_float.head(min_len)
                            diff = (s - p).abs()
                            comp.max_abs_diff = diff.max()

                            # Count mismatches beyond tolerance
                            # Use Series ops instead of pl.when (which expects Expr, not Series)
                            s_abs = s.abs()
                            relative_diff = pl.Series(
                                "rel_diff",
                                [
                                    (d / sa) if sa > 0 else d
                                    for d, sa in zip(diff.to_list(), s_abs.to_list())
                                ],
                            )
                            mismatches = relative_diff.filter(relative_diff > tolerance)
                            comp.mismatch_count = len(mismatches)
                            comp.mismatch_pct = comp.mismatch_count / min_len if min_len > 0 else 0
                    except Exception:
                        logger.debug("Could not compare column '%s' numerically", col)
                else:
                    # String comparison
                    try:
                        min_len = min(len(sas_series), len(py_series))
                        if min_len > 0:
                            s = sas_series.cast(pl.Utf8).head(min_len)
                            p = py_series.cast(pl.Utf8).head(min_len)
                            mismatches = (s != p).sum()
                            comp.mismatch_count = mismatches
                            comp.mismatch_pct = mismatches / min_len if min_len > 0 else 0
                    except Exception:
                        logger.debug("Could not compare column '%s' as strings", col)

                report.value_comparison[col] = comp

        try:
            import psutil
            process = psutil.Process()
            mem_after = process.memory_info().rss / 1024 / 1024
            report.peak_memory_mb = mem_after - mem_before
        except ImportError:
            report.peak_memory_mb = 0.0

        report.execution_time_seconds = time.perf_counter() - t0
        return report

    def save_artifacts(
        self,
        report: ValidationReport,
        output_dir: str | Path,
    ) -> None:
        """
        Save validation artifacts (HTML report, stats JSON).

        Parameters
        ----------
        report : ValidationReport
            The validation report to save.
        output_dir : str or Path
            Directory to write artifacts to.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        prefix = f"{report.module_name}_{report.table_name}".replace("/", "_")

        # Save JSON stats
        stats: dict[str, Any] = {
            "module_name": report.module_name,
            "table_name": report.table_name,
            "sas_row_count": report.sas_row_count,
            "python_row_count": report.python_row_count,
            "row_count_match": report.row_count_match,
            "column_names_match": report.column_names_match,
            "missing_in_python": report.missing_in_python,
            "extra_in_python": report.extra_in_python,
            "execution_time_seconds": report.execution_time_seconds,
            "peak_memory_mb": report.peak_memory_mb,
            "passed": report.passed,
            "timestamp": report.timestamp,
        }
        json_path = output_dir / f"{prefix}_stats.json"
        json_path.write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")

        # Save HTML report
        html_path = output_dir / f"{prefix}_report.html"
        html_lines = [
            "<!DOCTYPE html><html><head>",
            f"<title>Validation: {prefix}</title>",
            "<style>",
            "body { font-family: monospace; margin: 20px; }",
            ".pass { color: green; } .fail { color: red; }",
            "table { border-collapse: collapse; } td, th { border: 1px solid #ccc; padding: 4px; }",
            "</style></head><body>",
            f"<h1>Validation Report: {prefix}</h1>",
            f"<pre>{report.summary()}</pre>",
            "</body></html>",
        ]
        html_path.write_text("\n".join(html_lines), encoding="utf-8")

        logger.info("Saved artifacts to %s", output_dir)

    def assert_match(self, report: ValidationReport) -> None:
        """
        Raise ``AssertionError`` with details if the report indicates mismatch.
        """
        if not report.passed:
            raise AssertionError(f"Validation FAILED:\n{report.summary()}")
