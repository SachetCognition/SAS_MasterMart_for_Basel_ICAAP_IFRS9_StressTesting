"""
RST summary report generation.

Translated from Code/04.RST_SEGMENT/F_13_RST_SUMMARY.sas.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

from lib.report_writer import write_excel_report, write_summary_html

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(config: Config, rst_combined: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """Generate RST summary reports."""
    results: dict[str, pl.DataFrame] = {}

    if rst_combined.is_empty():
        logger.warning("F13 RST: Empty combined input")
        return results

    output_dir = Path(config.dir_mart) if hasattr(config, "dir_mart") else Path("artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)
    rpt = config.rpt_month

    segment_col = "RST_SEGMENT" if "RST_SEGMENT" in rst_combined.columns else None
    if segment_col:
        agg_exprs: list[pl.Expr] = [pl.len().alias("COUNT")]
        for i in range(4):
            for metric in ["RWA", "EAD", "EL"]:
                col = f"{metric}_ST{i}"
                if col in rst_combined.columns:
                    agg_exprs.append(pl.col(col).sum().alias(f"SUM_{col}"))

        summary = rst_combined.group_by(segment_col).agg(agg_exprs).sort(segment_col)
        results["rst_summary"] = summary

        write_excel_report(
            summary,
            output_path=str(output_dir / f"rst_summary_{rpt}.xlsx"),
            sheet_name="RST_Summary",
        )
        write_summary_html(
            summary,
            output_path=str(output_dir / f"rst_summary_{rpt}.html"),
        )

    logger.info("F13 RST: Summary reports generated")
    return results
