"""
Generate stress testing summary reports using PROC TABULATE equivalent.

Translated from Code/05.ST_SEGMENT/F_11_ST_SUMMARY.sas (~80 lines).
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


def run(config: Config, st_combined: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """
    Generate stress testing summary reports.

    Parameters
    ----------
    config : Config
    st_combined : pl.DataFrame
        Combined stressed dataset from f08.

    Returns
    -------
    dict[str, pl.DataFrame]
        Summary DataFrames for reporting.
    """
    results: dict[str, pl.DataFrame] = {}

    if st_combined.is_empty():
        logger.warning("F11 ST: Empty combined input")
        return results

    output_dir = Path(config.dir_mart) if hasattr(config, "dir_mart") else Path("artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)
    rpt = config.rpt_month

    # Summary by segment
    segment_col = "ST_SEGMENT" if "ST_SEGMENT" in st_combined.columns else None
    if segment_col:
        agg_exprs: list[pl.Expr] = [pl.len().alias("COUNT")]
        for i in range(4):
            for metric in ["RWA", "EAD", "EL"]:
                col = f"{metric}_ST{i}"
                if col in st_combined.columns:
                    agg_exprs.append(pl.col(col).sum().alias(f"SUM_{col}"))

        summary_by_segment = st_combined.group_by(segment_col).agg(agg_exprs).sort(segment_col)
        results["st_summary_by_segment"] = summary_by_segment

        write_excel_report(
            summary_by_segment,
            output_path=str(output_dir / f"st_summary_by_segment_{rpt}.xlsx"),
            sheet_name="By_Segment",
        )

    # Summary by BU
    bu_col = None
    for candidate in ["ICAAP_BUS_UNIT_ADJ", "ICAAP_BUS_UNIT"]:
        if candidate in st_combined.columns:
            bu_col = candidate
            break

    if bu_col:
        agg_exprs = [pl.len().alias("COUNT")]
        for i in range(4):
            for metric in ["RWA", "EAD", "EL"]:
                col = f"{metric}_ST{i}"
                if col in st_combined.columns:
                    agg_exprs.append(pl.col(col).sum().alias(f"SUM_{col}"))

        summary_by_bu = st_combined.group_by(bu_col).agg(agg_exprs).sort(bu_col)
        results["st_summary_by_bu"] = summary_by_bu

        write_excel_report(
            summary_by_bu,
            output_path=str(output_dir / f"st_summary_by_bu_{rpt}.xlsx"),
            sheet_name="By_BU",
        )

    # Grand total
    total_exprs: list[pl.Expr] = [pl.len().alias("COUNT")]
    for i in range(4):
        for metric in ["RWA", "EAD", "EL"]:
            col = f"{metric}_ST{i}"
            if col in st_combined.columns:
                total_exprs.append(pl.col(col).sum().alias(f"TOTAL_{col}"))

    grand_total = st_combined.select(total_exprs)
    results["st_grand_total"] = grand_total

    # HTML summary
    if "st_summary_by_segment" in results:
        write_summary_html(
            results["st_summary_by_segment"],
            output_path=str(output_dir / f"st_summary_{rpt}.html"),
        )

    logger.info("F11 ST: Summary reports generated in %s", output_dir)
    return results
