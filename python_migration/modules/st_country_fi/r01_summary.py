"""
Generate ST Country FI summary reports.

Translated from Code/06.ST_COUNTRY_FI/R_01_RESULT.sas (~60 lines).
Reports by GRP_NAM, FLAG_UNRATED, and Vietnam banks.
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


def run(config: Config, stressed_fi: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """
    Generate summary reports for ST Country FI results.

    Reports:
    - By GRP_NAM (counterparty group)
    - By FLAG_UNRATED (rated vs unrated)
    - Vietnam banks subset

    Returns dict of summary DataFrames.
    """
    results: dict[str, pl.DataFrame] = {}

    if stressed_fi.is_empty():
        logger.warning("R01 ST_FI: Empty stressed FI input")
        return results

    output_dir = Path(config.dir_mart) if hasattr(config, "dir_mart") else Path("artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)
    rpt = config.rpt_month

    # Summary by GRP_NAM
    if "GRP_NAM" in stressed_fi.columns:
        agg_exprs: list[pl.Expr] = [pl.len().alias("COUNT")]
        for suffix in ["ST0", "ST1", "ST2"]:
            for metric in ["RWA", "EAD", "EL"]:
                col = f"{metric}_{suffix}"
                if col in stressed_fi.columns:
                    agg_exprs.append(pl.col(col).sum().alias(f"SUM_{col}"))

        by_grp = stressed_fi.group_by("GRP_NAM").agg(agg_exprs).sort("GRP_NAM")
        results["fi_by_grp_nam"] = by_grp

        write_excel_report(
            by_grp,
            output_path=str(output_dir / f"st_fi_by_grp_{rpt}.xlsx"),
            sheet_name="By_Group",
        )

    # Summary by FLAG_UNRATED
    if "FLAG_UNRATED" in stressed_fi.columns:
        agg_exprs = [pl.len().alias("COUNT")]
        for suffix in ["ST0", "ST1", "ST2"]:
            for metric in ["RWA", "EAD", "EL"]:
                col = f"{metric}_{suffix}"
                if col in stressed_fi.columns:
                    agg_exprs.append(pl.col(col).sum().alias(f"SUM_{col}"))

        by_rated = stressed_fi.group_by("FLAG_UNRATED").agg(agg_exprs).sort("FLAG_UNRATED")
        results["fi_by_rated"] = by_rated

    # Grand total
    total_exprs: list[pl.Expr] = [pl.len().alias("COUNT")]
    for suffix in ["ST0", "ST1", "ST2"]:
        for metric in ["RWA", "EAD", "EL"]:
            col = f"{metric}_{suffix}"
            if col in stressed_fi.columns:
                total_exprs.append(pl.col(col).sum().alias(f"TOTAL_{col}"))

    grand_total = stressed_fi.select(total_exprs)
    results["fi_grand_total"] = grand_total

    # HTML summary
    if "fi_by_grp_nam" in results:
        write_summary_html(
            results["fi_by_grp_nam"],
            output_path=str(output_dir / f"st_fi_summary_{rpt}.html"),
        )

    logger.info("R01 ST_FI: Summary reports generated")
    return results
