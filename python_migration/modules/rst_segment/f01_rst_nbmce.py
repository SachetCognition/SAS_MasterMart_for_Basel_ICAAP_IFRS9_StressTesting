"""
RST NBMCE transformation.

Translated from Code/04.RST_SEGMENT/F_01_RST_NBMCE.sas.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(config: Config, rst_nbmce_raw: pl.DataFrame) -> pl.DataFrame:
    """Transform RST NBMCE data into staging format."""
    if rst_nbmce_raw.is_empty():
        logger.warning("F01 RST: Empty NBMCE input")
        return pl.DataFrame()

    df = rst_nbmce_raw.clone()
    df = df.with_columns([
        pl.lit("RST_NBMCE").alias("FILE_SRC"),
        pl.lit(config.rpt_month).alias("RPT_MONTH"),
    ])

    # Ensure amount columns are numeric
    for col in df.columns:
        if any(kw in col.upper() for kw in ["AMT", "BAL", "EXPOSURE", "LIMIT"]):
            df = df.with_columns(pl.col(col).cast(pl.Float64, strict=False).fill_null(0.0).alias(col))

    logger.info("F01 RST: NBMCE transformed: %d rows", len(df))
    return df
