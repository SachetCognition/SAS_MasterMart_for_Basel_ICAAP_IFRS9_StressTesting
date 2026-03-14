"""
RST Property Investment/Development transformation.

Translated from Code/04.RST_SEGMENT/F_02_RST_PRTY_INV_DEV.sas.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(config: Config, rst_prty_raw: pl.DataFrame) -> pl.DataFrame:
    """Transform RST Property Investment/Development data."""
    if rst_prty_raw.is_empty():
        logger.warning("F02 RST: Empty PRTY_INV_DEV input")
        return pl.DataFrame()

    df = rst_prty_raw.clone()
    df = df.with_columns([
        pl.lit("RST_PRTY_INV_DEV").alias("FILE_SRC"),
        pl.lit(config.rpt_month).alias("RPT_MONTH"),
    ])

    for col in df.columns:
        if any(kw in col.upper() for kw in ["AMT", "BAL", "EXPOSURE", "LIMIT"]):
            df = df.with_columns(pl.col(col).cast(pl.Float64, strict=False).fill_null(0.0).alias(col))

    logger.info("F02 RST: PRTY_INV_DEV transformed: %d rows", len(df))
    return df
