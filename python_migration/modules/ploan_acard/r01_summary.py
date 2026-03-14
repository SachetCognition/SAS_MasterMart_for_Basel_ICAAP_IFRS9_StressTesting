"""
P-LOAN/ACARD summary report generation.

Translated from Code/08.PLOAN-ACARD reporting logic.
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


def run(config: Config, accept_df: pl.DataFrame, full_df: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """Generate P-LOAN/ACARD summary reports."""
    results: dict[str, pl.DataFrame] = {}

    output_dir = Path(config.dir_mart) if hasattr(config, "dir_mart") else Path("artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)
    rpt = config.rpt_month

    # Exclusion summary
    if not full_df.is_empty() and "FLAG_ALL_EXCLUDED" in full_df.columns:
        excl_summary = full_df.group_by("FLAG_ALL_EXCLUDED").agg([
            pl.len().alias("COUNT"),
        ]).sort("FLAG_ALL_EXCLUDED")
        results["exclusion_summary"] = excl_summary
        write_excel_report(excl_summary, str(output_dir / f"ploan_exclusion_{rpt}.xlsx"), "Exclusions")

    # Acceptance summary by product
    if not accept_df.is_empty():
        prod_col = "IND_PRODUCT" if "IND_PRODUCT" in accept_df.columns else None
        if prod_col:
            bad_rate_expr = (
                pl.col("IND_1ST_BAD").mean().alias("BAD_RATE")
                if "IND_1ST_BAD" in accept_df.columns
                else pl.lit(0).alias("BAD_RATE")
            )
            prod_summary = accept_df.group_by(prod_col).agg([
                pl.len().alias("COUNT"),
                bad_rate_expr,
            ]).sort(prod_col)
            results["product_summary"] = prod_summary
            write_excel_report(prod_summary, str(output_dir / f"ploan_product_{rpt}.xlsx"), "By_Product")

        # Overall stats
        total_exprs: list[pl.Expr] = [pl.len().alias("TOTAL_COUNT")]
        if "IND_1ST_BAD" in accept_df.columns:
            total_exprs.append(pl.col("IND_1ST_BAD").sum().alias("TOTAL_BAD"))
            total_exprs.append(pl.col("IND_1ST_BAD").mean().alias("BAD_RATE"))
        if "IND_1ST_MED" in accept_df.columns:
            total_exprs.append(pl.col("IND_1ST_MED").sum().alias("TOTAL_MED"))

        grand_total = accept_df.select(total_exprs)
        results["grand_total"] = grand_total

    # HTML summary
    if "exclusion_summary" in results:
        write_summary_html(results["exclusion_summary"], str(output_dir / f"ploan_summary_{rpt}.html"))

    logger.info("R01 PLOAN: Summary reports generated")
    return results
