"""
Build NPL fact table.

Translated from Code/02.RU_NONBANK_EXP/L_01_RU_NPL_FACT_TABLE.sas.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(
    config: Config,
    nonpbg_exp: pl.DataFrame,
    pbg_exp: pl.DataFrame,
    npl_data: pl.DataFrame,
) -> pl.DataFrame:
    """
    Build the NPL fact table by combining PBG and non-PBG exposures with NPL flags.

    Parameters
    ----------
    config : Config
    nonpbg_exp : pl.DataFrame
        Transformed non-PBG exposure from f01.
    pbg_exp : pl.DataFrame
        Transformed PBG exposure from f03.
    npl_data : pl.DataFrame
        NPL data from e02.

    Returns
    -------
    pl.DataFrame
        NPL fact table.
    """
    # Union PBG and non-PBG exposures
    frames: list[pl.DataFrame] = []
    if not nonpbg_exp.is_empty():
        frames.append(nonpbg_exp)
    if not pbg_exp.is_empty():
        frames.append(pbg_exp)

    if not frames:
        logger.warning("L01 RU: No exposure data")
        return pl.DataFrame()

    combined = pl.concat(frames, how="diagonal")

    # Join NPL flags
    if not npl_data.is_empty():
        join_key = None
        for candidate in ["ACCT_ID", "CUST_SEC_ID", "RM_CUST_ID"]:
            if candidate in combined.columns and candidate in npl_data.columns:
                join_key = candidate
                break

        if join_key:
            npl_cols = ["FLAG_NPL", "NPL_AMT", "NPL_DATE", "NPL_CATEGORY"]
            available_npl = [c for c in npl_cols if c in npl_data.columns]
            if available_npl:
                npl_subset = npl_data.select([join_key] + available_npl).unique(subset=[join_key])
                combined = combined.join(npl_subset, on=join_key, how="left")

    # Fill missing NPL flags
    if "FLAG_NPL" not in combined.columns:
        combined = combined.with_columns(pl.lit(0).alias("FLAG_NPL"))
    else:
        combined = combined.with_columns(pl.col("FLAG_NPL").fill_null(0))

    # Add reporting period
    combined = combined.with_columns(pl.lit(config.rpt_month).alias("RPT_MONTH"))

    logger.info("L01 RU: NPL fact table: %d rows", len(combined))
    return combined
