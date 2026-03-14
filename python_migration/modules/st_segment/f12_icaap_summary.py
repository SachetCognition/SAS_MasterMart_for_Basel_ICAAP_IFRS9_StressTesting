"""
ICAAP summary report generation.

Translated from Code/05.ST_SEGMENT/F_12_ICAAP_SUMMARY.sas (~60 lines).
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


def run(config: Config, icaap_combined: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """
    Generate ICAAP summary reports.

    Parameters
    ----------
    config : Config
    icaap_combined : pl.DataFrame
        ICAAP combined from f09.

    Returns
    -------
    dict[str, pl.DataFrame]
        Summary DataFrames.
    """
    results: dict[str, pl.DataFrame] = {}

    if icaap_combined.is_empty():
        logger.warning("F12 ST: Empty ICAAP combined input")
        return results

    output_dir = Path(config.dir_mart) if hasattr(config, "dir_mart") else Path("artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)
    rpt = config.rpt_month

    # Summary by ICAAP segment and BU
    bu_col = None
    for candidate in ["ICAAP_BUS_UNIT_ADJ", "ICAAP_BUS_UNIT"]:
        if candidate in icaap_combined.columns:
            bu_col = candidate
            break

    seg_col = "ICAAP_PORTCD_DESC" if "ICAAP_PORTCD_DESC" in icaap_combined.columns else "ST_SEGMENT"

    if bu_col and seg_col in icaap_combined.columns:
        agg_exprs: list[pl.Expr] = [pl.len().alias("COUNT")]
        for i in range(4):
            for metric in ["RWA", "EAD", "EL"]:
                col = f"{metric}_ST{i}"
                if col in icaap_combined.columns:
                    agg_exprs.append(pl.col(col).sum().alias(f"SUM_{col}"))
            incr_col = f"INCR_RWA_ST{i}"
            if incr_col in icaap_combined.columns:
                agg_exprs.append(pl.col(incr_col).sum().alias(f"SUM_{incr_col}"))

        summary = icaap_combined.group_by([bu_col, seg_col]).agg(agg_exprs).sort([bu_col, seg_col])
        results["icaap_summary"] = summary

        write_excel_report(
            summary,
            output_path=str(output_dir / f"icaap_summary_{rpt}.xlsx"),
            sheet_name="ICAAP_Summary",
        )

        write_summary_html(
            summary,
            output_path=str(output_dir / f"icaap_summary_{rpt}.html"),
        )

    logger.info("F12 ST: ICAAP summary reports generated")
    return results
