"""
BIS CSRBB Part A - Standard dimensional reports.

Translated from Code/07.BIS_BASEL_III_CHECK/F_03_BIS_CSRBB_PART_A.sas (~100 lines).
Generates CSRBB_A1-A3 reports: CQ x Sector x Maturity, Risk Weight, Currency.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

from lib.report_writer import write_excel_report

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(config: Config, csrbb_base: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """
    Generate CSRBB Part A dimensional reports.

    A1: CQ x Sector x Maturity breakdown
    A2: Risk Weight distribution
    A3: Currency breakdown
    """
    results: dict[str, pl.DataFrame] = {}

    if csrbb_base.is_empty():
        logger.warning("F03 BIS A: Empty CSRBB base")
        return results

    output_dir = Path(config.dir_mart) if hasattr(config, "dir_mart") else Path("artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)
    rpt = config.rpt_month

    ead_col = "APPL_CRM_AMT_HKE" if "APPL_CRM_AMT_HKE" in csrbb_base.columns else "ORIG_CRM_AMT_HKE"
    rwa_col = "RISK_WEIGHTED_AMT_HKE" if "RISK_WEIGHTED_AMT_HKE" in csrbb_base.columns else None

    # A1: CQ x Sector x Maturity
    group_cols_a1 = []
    for c in ["BIS_CQ", "BIS_SECTOR_TYP", "BIS_MAT_BUCKET"]:
        if c in csrbb_base.columns:
            group_cols_a1.append(c)

    if group_cols_a1:
        agg_a1: list[pl.Expr] = [pl.len().alias("COUNT")]
        if ead_col in csrbb_base.columns:
            agg_a1.append(pl.col(ead_col).sum().alias("SUM_EAD"))
        if rwa_col and rwa_col in csrbb_base.columns:
            agg_a1.append(pl.col(rwa_col).sum().alias("SUM_RWA"))

        a1 = csrbb_base.group_by(group_cols_a1).agg(agg_a1).sort(group_cols_a1)
        results["CSRBB_A1"] = a1
        write_excel_report(a1, str(output_dir / f"CSRBB_A1_{rpt}.xlsx"), "CQ_Sector_Mat")

    # A2: Risk Weight distribution
    rw_col = "APPL_RISK_WEIGHT" if "APPL_RISK_WEIGHT" in csrbb_base.columns else None
    if rw_col:
        csrbb_rw = csrbb_base.with_columns(
            pl.when(pl.col(rw_col) == 0).then(pl.lit("0%"))
            .when(pl.col(rw_col) <= 20).then(pl.lit("20%"))
            .when(pl.col(rw_col) <= 50).then(pl.lit("50%"))
            .when(pl.col(rw_col) <= 100).then(pl.lit("100%"))
            .when(pl.col(rw_col) <= 150).then(pl.lit("150%"))
            .otherwise(pl.lit(">150%"))
            .alias("RW_BUCKET")
        )
        agg_a2: list[pl.Expr] = [pl.len().alias("COUNT")]
        if ead_col in csrbb_rw.columns:
            agg_a2.append(pl.col(ead_col).sum().alias("SUM_EAD"))
        if rwa_col in csrbb_rw.columns:
            agg_a2.append(pl.col(rwa_col).sum().alias("SUM_RWA"))

        a2 = csrbb_rw.group_by("RW_BUCKET").agg(agg_a2).sort("RW_BUCKET")
        results["CSRBB_A2"] = a2
        write_excel_report(a2, str(output_dir / f"CSRBB_A2_{rpt}.xlsx"), "RiskWeight")

    # A3: Currency breakdown
    ccy_col = "CCY_CD" if "CCY_CD" in csrbb_base.columns else None
    if ccy_col:
        agg_a3: list[pl.Expr] = [pl.len().alias("COUNT")]
        if ead_col in csrbb_base.columns:
            agg_a3.append(pl.col(ead_col).sum().alias("SUM_EAD"))
        if rwa_col and rwa_col in csrbb_base.columns:
            agg_a3.append(pl.col(rwa_col).sum().alias("SUM_RWA"))

        a3 = csrbb_base.group_by(ccy_col).agg(agg_a3).sort(ccy_col)
        results["CSRBB_A3"] = a3
        write_excel_report(a3, str(output_dir / f"CSRBB_A3_{rpt}.xlsx"), "Currency")

    logger.info("F03 BIS A: Generated %d CSRBB Part A reports", len(results))
    return results
