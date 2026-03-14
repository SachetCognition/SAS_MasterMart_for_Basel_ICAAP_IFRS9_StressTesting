"""
Transform PBG exposure data.

Translated from Code/02.RU_NONBANK_EXP/F_03_RU_PBG_EXP.sas.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(config: Config, pbg_with_dsr: pl.DataFrame) -> pl.DataFrame:
    """
    Final PBG exposure transformation.

    Parameters
    ----------
    config : Config
    pbg_with_dsr : pl.DataFrame
        PBG data enriched with DSR from f02.

    Returns
    -------
    pl.DataFrame
        Transformed PBG exposure ready for fact table.
    """
    if pbg_with_dsr.is_empty():
        logger.warning("F03 RU: Empty PBG input")
        return pl.DataFrame()

    df = pbg_with_dsr.clone()
    df = df.with_columns([
        pl.lit("PBG").alias("FILE_SRC"),
        pl.lit(config.rpt_month).alias("RPT_MONTH"),
    ])

    logger.info("F03 RU: PBG exposure: %d rows", len(df))
    return df
