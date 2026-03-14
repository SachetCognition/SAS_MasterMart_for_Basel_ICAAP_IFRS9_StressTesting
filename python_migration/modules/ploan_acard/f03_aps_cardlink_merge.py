"""
Merge APS applications with Cardlink performance.

Translated from Code/08.PLOAN-ACARD/F_03_FACT_TABLE.sas (~40 lines).
Merges standardized applications with performance data,
calculates IND_1ST_BAD and IND_1ST_MED.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(config: Config, aps_std: pl.DataFrame, cardlink_perf: pl.DataFrame) -> pl.DataFrame:
    """
    Merge APS applications with Cardlink performance data.

    Joins on ACCT_ID or APPLICATION_ID, calculates first-bad/first-med indicators.
    """
    if aps_std.is_empty():
        logger.warning("F03 PLOAN: No APS data for merge")
        return pl.DataFrame()

    df = aps_std.clone()

    if not cardlink_perf.is_empty():
        # Determine join key
        join_key = None
        for candidate in ["ACCT_ID", "APPLICATION_ID", "APP_ID"]:
            if candidate in df.columns and candidate in cardlink_perf.columns:
                join_key = candidate
                break

        if join_key:
            # Aggregate performance by account: first bad/med occurrence
            perf_agg_exprs: list[pl.Expr] = []
            if "IND_BAD" in cardlink_perf.columns:
                perf_agg_exprs.append(pl.col("IND_BAD").max().alias("IND_1ST_BAD"))
            if "IND_MED" in cardlink_perf.columns:
                perf_agg_exprs.append(pl.col("IND_MED").max().alias("IND_1ST_MED"))
            if "FLAG_EXCLUDE_PERF" in cardlink_perf.columns:
                perf_agg_exprs.append(pl.col("FLAG_EXCLUDE_PERF").min().alias("FLAG_EXCLUDE_PERF_AGG"))

            if perf_agg_exprs:
                perf_summary = cardlink_perf.group_by(join_key).agg(perf_agg_exprs)
                df = df.join(perf_summary, on=join_key, how="left")
            else:
                df = df.join(
                    cardlink_perf.select([join_key]).unique(),
                    on=join_key,
                    how="left",
                )
        else:
            logger.warning("F03 PLOAN: No common join key between APS and Cardlink")

    # Fill missing indicators
    if "IND_1ST_BAD" not in df.columns:
        df = df.with_columns(pl.lit(0).alias("IND_1ST_BAD"))
    else:
        df = df.with_columns(pl.col("IND_1ST_BAD").fill_null(0))

    if "IND_1ST_MED" not in df.columns:
        df = df.with_columns(pl.lit(0).alias("IND_1ST_MED"))
    else:
        df = df.with_columns(pl.col("IND_1ST_MED").fill_null(0))

    logger.info("F03 PLOAN: Merged APS+Cardlink: %d rows", len(df))
    return df
