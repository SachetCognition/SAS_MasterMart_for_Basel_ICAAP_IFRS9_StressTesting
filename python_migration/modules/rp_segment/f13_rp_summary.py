"""
RP summary report generation.

Translated from Code/90.RP_SEGMENT reporting logic.
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


def run(config: Config, rp_combined: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """Generate RP summary reports."""
    results: dict[str, pl.DataFrame] = {}

    if rp_combined.is_empty():
        logger.warning("F13 RP: Empty combined input")
        return results

    output_dir = Path(config.dir_mart) if hasattr(config, "dir_mart") else Path("artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)
    rpt = config.rpt_month

    segment_col = "RP_SEGMENT" if "RP_SEGMENT" in rp_combined.columns else "ST_SEGMENT"
    if segment_col in rp_combined.columns:
        agg_exprs: list[pl.Expr] = [pl.len().alias("COUNT")]
        for i in range(4):
            for metric in ["RWA", "EAD", "EL"]:
                col = f"{metric}_ST{i}"
                if col in rp_combined.columns:
                    agg_exprs.append(pl.col(col).sum().alias(f"SUM_{col}"))

        summary = rp_combined.group_by(segment_col).agg(agg_exprs).sort(segment_col)
        results["rp_summary"] = summary

        write_excel_report(
            summary,
            output_path=str(output_dir / f"rp_summary_{rpt}.xlsx"),
            sheet_name="RP_Summary",
        )
        write_summary_html(
            summary,
            output_path=str(output_dir / f"rp_summary_{rpt}.html"),
        )

    # Per-segment detail reports
    if segment_col in rp_combined.columns:
        for seg in rp_combined[segment_col].unique().to_list():
            if seg is None:
                continue
            seg_df = rp_combined.filter(pl.col(segment_col) == seg)
            seg_key = f"rp_{str(seg).lower()}"
            output_path = output_dir / f"rp_{str(seg).lower()}_{rpt}.xlsx"
            write_excel_report(seg_df, str(output_path), str(seg))
            results[seg_key] = seg_df

    logger.info("F13 RP: Summary reports generated")
    return results
