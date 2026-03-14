"""
BIS CSRBB Part B - Debt securities validation.

Translated from Code/07.BIS_BASEL_III_CHECK/F_03_BIS_CSRBB_PART_B.sas (~80 lines).
GL account-level debt securities validation (CSRBB_B1-B9).
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
    Generate CSRBB Part B validation reports.

    B1-B9: GL account-level debt securities validation reports.
    """
    results: dict[str, pl.DataFrame] = {}

    if csrbb_base.is_empty():
        logger.warning("F04 BIS B: Empty CSRBB base")
        return results

    output_dir = Path(config.dir_mart) if hasattr(config, "dir_mart") else Path("artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)
    rpt = config.rpt_month

    ead_col = "APPL_CRM_AMT_HKE" if "APPL_CRM_AMT_HKE" in csrbb_base.columns else "ORIG_CRM_AMT_HKE"

    # B1: On-balance summary by sector
    has_exp_type = "BIS_EXP_TYPE" in csrbb_base.columns
    on_bal = csrbb_base.filter(pl.col("BIS_EXP_TYPE") == "ON") if has_exp_type else pl.DataFrame()
    if not on_bal.is_empty() and "BIS_SECTOR_TYP" in on_bal.columns:
        b1 = on_bal.group_by("BIS_SECTOR_TYP").agg([
            pl.len().alias("COUNT"),
            pl.col(ead_col).sum().alias("SUM_EAD") if ead_col in on_bal.columns else pl.lit(0).alias("SUM_EAD"),
        ]).sort("BIS_SECTOR_TYP")
        results["CSRBB_B1"] = b1
        write_excel_report(b1, str(output_dir / f"CSRBB_B1_{rpt}.xlsx"), "OnBal_Sector")

    # B2: Off-balance summary by sector
    off_bal = csrbb_base.filter(pl.col("BIS_EXP_TYPE") == "OFF") if has_exp_type else pl.DataFrame()
    if not off_bal.is_empty() and "BIS_SECTOR_TYP" in off_bal.columns:
        b2 = off_bal.group_by("BIS_SECTOR_TYP").agg([
            pl.len().alias("COUNT"),
            pl.col(ead_col).sum().alias("SUM_EAD") if ead_col in off_bal.columns else pl.lit(0).alias("SUM_EAD"),
        ]).sort("BIS_SECTOR_TYP")
        results["CSRBB_B2"] = b2
        write_excel_report(b2, str(output_dir / f"CSRBB_B2_{rpt}.xlsx"), "OffBal_Sector")

    # B3: Derivative summary
    derv = csrbb_base.filter(pl.col("BIS_EXP_TYPE") == "DERV") if has_exp_type else pl.DataFrame()
    if not derv.is_empty():
        b3 = derv.select([
            pl.len().alias("COUNT"),
            pl.col(ead_col).sum().alias("SUM_EAD") if ead_col in derv.columns else pl.lit(0).alias("SUM_EAD"),
        ])
        results["CSRBB_B3"] = b3
        write_excel_report(b3, str(output_dir / f"CSRBB_B3_{rpt}.xlsx"), "Derivative")

    # B4-B9: Additional validation reports by CQ x Maturity
    for exp_type, label in [("ON", "OnBal"), ("OFF", "OffBal"), ("DERV", "Deriv")]:
        subset = csrbb_base.filter(pl.col("BIS_EXP_TYPE") == exp_type) if has_exp_type else pl.DataFrame()
        if subset.is_empty():
            continue

        group_cols = []
        for c in ["BIS_CQ", "BIS_MAT_BUCKET"]:
            if c in subset.columns:
                group_cols.append(c)

        if group_cols:
            aggs: list[pl.Expr] = [pl.len().alias("COUNT")]
            if ead_col in subset.columns:
                aggs.append(pl.col(ead_col).sum().alias("SUM_EAD"))

            report = subset.group_by(group_cols).agg(aggs).sort(group_cols)
            key = f"CSRBB_{label}_CQ_Mat"
            results[key] = report
            write_excel_report(report, str(output_dir / f"CSRBB_{label}_CQ_Mat_{rpt}.xlsx"), key)

    logger.info("F04 BIS B: Generated %d CSRBB Part B reports", len(results))
    return results
