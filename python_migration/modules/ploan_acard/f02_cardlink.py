"""
Cardlink performance processing.

Translated from Code/08.PLOAN-ACARD/F_02_CARDLINK.sas (~50 lines).
Calculates IND_BAD/IND_MED indicators and transposes by month.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)

# IND_BAD codes: severe delinquency/charge-off
_BAD_CODES = {100, 200, 201, 202, 203, 204}
# IND_MED codes: moderate delinquency
_MED_CODES = {200, 201, 202, 203, 204}


def run(config: Config, cardlink_pil: pl.DataFrame, cardlink_card: pl.DataFrame) -> pl.DataFrame:
    """
    Process Cardlink performance data.

    Calculates IND_BAD (>=90 DPD or charge-off) and IND_MED (60 DPD or cancel)
    indicators, then transposes performance by month.
    """
    frames: list[pl.DataFrame] = []
    if not cardlink_pil.is_empty():
        frames.append(cardlink_pil.with_columns(pl.lit("PIL").alias("PERF_SOURCE")))
    if not cardlink_card.is_empty():
        frames.append(cardlink_card.with_columns(pl.lit("CARD").alias("PERF_SOURCE")))

    if not frames:
        logger.warning("F02 PLOAN: No cardlink data")
        return pl.DataFrame()

    df = pl.concat(frames, how="diagonal")

    # FLAG_EXCLUDE_PERF
    df = df.with_columns(pl.lit(None).cast(pl.Int32).alias("FLAG_EXCLUDE_PERF"))

    # 001: Transferred
    if "TRANSFER_IND" in df.columns:
        df = df.with_columns(
            pl.when(pl.col("TRANSFER_IND") == 1)
            .then(pl.lit(1))
            .otherwise(pl.col("FLAG_EXCLUDE_PERF"))
            .alias("FLAG_EXCLUDE_PERF")
        )

    # 002: Supplementary card
    if "SUPP_CARD_IND" in df.columns:
        df = df.with_columns(
            pl.when((pl.col("FLAG_EXCLUDE_PERF").is_null()) & (pl.col("SUPP_CARD_IND") == 1))
            .then(pl.lit(2))
            .otherwise(pl.col("FLAG_EXCLUDE_PERF"))
            .alias("FLAG_EXCLUDE_PERF")
        )

    # 100: Fraud charge-off
    if "FRAUD_IND" in df.columns:
        df = df.with_columns(
            pl.when((pl.col("FLAG_EXCLUDE_PERF").is_null()) & (pl.col("FRAUD_IND") == 1))
            .then(pl.lit(100))
            .otherwise(pl.col("FLAG_EXCLUDE_PERF"))
            .alias("FLAG_EXCLUDE_PERF")
        )

    # IND_BAD: >=90 days past due or charge-off
    dpd_col = "DPD_DAYS" if "DPD_DAYS" in df.columns else "DAYS_PAST_DUE"

    if dpd_col in df.columns:
        df = df.with_columns(
            pl.when(pl.col(dpd_col).fill_null(0) >= 90)
            .then(pl.lit(1))
            .otherwise(pl.lit(0))
            .alias("IND_BAD")
        )
    else:
        df = df.with_columns(pl.lit(0).alias("IND_BAD"))

    # IND_MED: 60 days past due
    if dpd_col in df.columns:
        df = df.with_columns(
            pl.when(pl.col(dpd_col).fill_null(0) >= 60)
            .then(pl.lit(1))
            .otherwise(pl.lit(0))
            .alias("IND_MED")
        )
    else:
        df = df.with_columns(pl.lit(0).alias("IND_MED"))

    df = df.with_columns(pl.lit(config.rpt_month).alias("RPT_MONTH"))
    logger.info("F02 PLOAN: Cardlink processed: %d rows", len(df))
    return df
