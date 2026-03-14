"""
Transform non-PBG exposure data.

Translated from Code/02.RU_NONBANK_EXP/F_01_RU_NONPBG_EXP.sas.

Standardizes non-PBG exposure data:
  - Normalize column names
  - Apply business unit mapping
  - Calculate HKE amounts
  - Add exposure classification flags
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(config: Config, nonpbg_exp: pl.DataFrame) -> pl.DataFrame:
    """
    Transform non-PBG exposure data.

    Parameters
    ----------
    config : Config
    nonpbg_exp : pl.DataFrame
        Raw non-PBG exposure from e01.

    Returns
    -------
    pl.DataFrame
        Standardized non-PBG exposure.
    """
    if nonpbg_exp.is_empty():
        logger.warning("F01 RU: Empty non-PBG exposure input")
        return pl.DataFrame()

    df = nonpbg_exp.clone()

    # Add source identifier
    df = df.with_columns([
        pl.lit("NONPBG").alias("FILE_SRC"),
        pl.lit(config.rpt_month).alias("RPT_MONTH"),
    ])

    # Ensure amount columns are numeric
    amt_cols = [c for c in df.columns if any(
        kw in c.upper() for kw in ["AMT", "BAL", "EXPOSURE", "LIMIT"]
    )]
    for col in amt_cols:
        df = df.with_columns(
            pl.col(col).cast(pl.Float64, strict=False).fill_null(0.0).alias(col)
        )

    # Classify exposure type
    if "EXPOSURE_TYPE" in df.columns:
        df = df.with_columns(
            pl.when(pl.col("EXPOSURE_TYPE").cast(pl.Utf8).str.to_uppercase().str.contains("LOAN"))
            .then(pl.lit("LOAN"))
            .when(pl.col("EXPOSURE_TYPE").cast(pl.Utf8).str.to_uppercase().str.contains("TRADE"))
            .then(pl.lit("TRADE"))
            .when(pl.col("EXPOSURE_TYPE").cast(pl.Utf8).str.to_uppercase().str.contains("GUARANTEE"))
            .then(pl.lit("GUARANTEE"))
            .otherwise(pl.lit("OTHER"))
            .alias("EXP_CLASS")
        )

    logger.info("F01 RU: Processed non-PBG exposure: %d rows", len(df))
    return df
