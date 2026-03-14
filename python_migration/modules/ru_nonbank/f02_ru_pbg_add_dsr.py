"""
Add DSR data to PBG exposure.

Translated from Code/02.RU_NONBANK_EXP/F_02_RU_PBG_ADD_DSR.sas.
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
    pbg_exposure: pl.DataFrame,
    dsr_data: pl.DataFrame,
) -> pl.DataFrame:
    """
    Join DSR data to PBG exposure records.

    Parameters
    ----------
    config : Config
    pbg_exposure : pl.DataFrame
        PBG exposure data from e04.
    dsr_data : pl.DataFrame
        DSR data from e03.

    Returns
    -------
    pl.DataFrame
        PBG exposure enriched with DSR information.
    """
    if pbg_exposure.is_empty():
        logger.warning("F02 RU: Empty PBG exposure input")
        return pl.DataFrame()

    df = pbg_exposure.clone()

    if dsr_data.is_empty():
        logger.info("F02 RU: No DSR data to join")
        return df

    # Join DSR on customer/account key
    join_cols = []
    for candidate in ["CUST_SEC_ID", "RM_CUST_ID", "ACCT_ID"]:
        if candidate in df.columns and candidate in dsr_data.columns:
            join_cols.append(candidate)
            break

    if join_cols:
        dsr_cols = [c for c in dsr_data.columns if c not in join_cols]
        dsr_subset = dsr_data.select(join_cols + dsr_cols).unique(subset=join_cols)
        df = df.join(dsr_subset, on=join_cols, how="left")
        logger.info("F02 RU: Joined DSR to PBG: %d rows", len(df))
    else:
        logger.warning("F02 RU: No common join key between PBG and DSR")

    return df
