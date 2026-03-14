"""
Summary report generation for non-bank exposures.

Translated from Code/02.RU_NONBANK_EXP/R_01_SUMMARY.sas.
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


def run(
    config: Config,
    npl_fact: pl.DataFrame,
    npl_ratios: dict[str, float],
) -> None:
    """
    Generate summary reports for non-bank exposure and NPL analysis.

    Parameters
    ----------
    config : Config
    npl_fact : pl.DataFrame
        NPL fact table from l01.
    npl_ratios : dict[str, float]
        NPL ratios by BU from m01.
    """
    if npl_fact.is_empty():
        logger.warning("R01 RU: No data for reporting")
        return

    output_dir = Path(config.dir_mart) if hasattr(config, "dir_mart") else Path("artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)

    # NPL ratio summary
    ratio_df = pl.DataFrame({
        "Business_Unit": list(npl_ratios.keys()),
        "NPL_Ratio": list(npl_ratios.values()),
    })

    write_excel_report(
        ratio_df,
        output_path=str(output_dir / f"npl_ratio_by_bu_{config.rpt_month}.xlsx"),
        sheet_name="NPL_Ratios",
    )

    # Exposure summary by BU and NPL flag
    bu_col = None
    for candidate in ["ICAAP_BUS_UNIT", "BUS_UNIT", "IND_BUS_UNIT"]:
        if candidate in npl_fact.columns:
            bu_col = candidate
            break

    if bu_col:
        exp_col = None
        for candidate in ["APPL_CRM_AMT_HKE", "ORIG_CRM_AMT_HKE", "CUR_BAL_ON_HKE"]:
            if candidate in npl_fact.columns:
                exp_col = candidate
                break

        if exp_col:
            summary = npl_fact.group_by([bu_col, "FLAG_NPL"]).agg([
                pl.len().alias("COUNT"),
                pl.col(exp_col).sum().alias("TOTAL_EXPOSURE"),
            ]).sort([bu_col, "FLAG_NPL"])

            write_excel_report(
                summary,
                output_path=str(output_dir / f"npl_exposure_summary_{config.rpt_month}.xlsx"),
                sheet_name="Exposure_Summary",
            )

    # HTML summary
    write_summary_html(
        ratio_df,
        output_path=str(output_dir / f"npl_ratio_summary_{config.rpt_month}.html"),
    )

    logger.info("R01 RU: Reports generated in %s", output_dir)
