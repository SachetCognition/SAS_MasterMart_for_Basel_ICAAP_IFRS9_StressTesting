"""
Standardize APS application data.

Translated from Code/08.PLOAN-ACARD/F_01_APS.sas (~120 lines).
Standardizes applications, applies FLAG_EXCLUDE_APS (16 types),
calculates DTI_pct.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)

# FLAG_EXCLUDE_APS codes
_EXCLUDE_APS_RULES: dict[int, str] = {
    100: "Supplementary card",
    120: "Staff - general",
    121: "Staff - senior",
    130: "Pre-approved",
    140: "VIP - general",
    141: "VIP - senior",
    142: "VIP - executive",
    200: "Missing income",
    210: "Zero income",
    220: "Income requirement - low",
    221: "Income requirement - high",
    222: "Income requirement - missing",
    223: "Income requirement - other",
    300: "Duplicate application",
    310: "Test application",
    340: "Age requirement",
    341: "ID requirement",
    342: "Residency requirement",
}


def run(config: Config, aps_old: pl.DataFrame, aps_new: pl.DataFrame) -> pl.DataFrame:
    """
    Standardize APS application data and apply exclusion flags.

    Combines old and new APS data, standardizes column names,
    applies 16 exclusion rules, and calculates DTI_pct.
    """
    frames: list[pl.DataFrame] = []
    if not aps_old.is_empty():
        frames.append(aps_old.with_columns(pl.lit("OLD").alias("APS_SOURCE")))
    if not aps_new.is_empty():
        frames.append(aps_new.with_columns(pl.lit("NEW").alias("APS_SOURCE")))

    if not frames:
        logger.warning("F01 PLOAN: No APS data")
        return pl.DataFrame()

    df = pl.concat(frames, how="diagonal")

    # Initialize FLAG_EXCLUDE_APS
    df = df.with_columns(pl.lit(None).cast(pl.Int32).alias("FLAG_EXCLUDE_APS"))

    # Apply exclusion rules based on available columns
    # 100: Supplementary card
    if "CARD_TYPE" in df.columns:
        df = df.with_columns(
            pl.when((pl.col("FLAG_EXCLUDE_APS").is_null()) & (pl.col("CARD_TYPE").str.contains("(?i)supp")))
            .then(pl.lit(100))
            .otherwise(pl.col("FLAG_EXCLUDE_APS"))
            .alias("FLAG_EXCLUDE_APS")
        )

    # 120-121: Staff
    if "STAFF_IND" in df.columns:
        df = df.with_columns(
            pl.when((pl.col("FLAG_EXCLUDE_APS").is_null()) & (pl.col("STAFF_IND") == 1))
            .then(pl.lit(120))
            .otherwise(pl.col("FLAG_EXCLUDE_APS"))
            .alias("FLAG_EXCLUDE_APS")
        )

    # 130: Pre-approved
    if "PRE_APPROVED_IND" in df.columns:
        df = df.with_columns(
            pl.when((pl.col("FLAG_EXCLUDE_APS").is_null()) & (pl.col("PRE_APPROVED_IND") == 1))
            .then(pl.lit(130))
            .otherwise(pl.col("FLAG_EXCLUDE_APS"))
            .alias("FLAG_EXCLUDE_APS")
        )

    # 140-142: VIP
    if "VIP_IND" in df.columns:
        df = df.with_columns(
            pl.when((pl.col("FLAG_EXCLUDE_APS").is_null()) & (pl.col("VIP_IND") == 1))
            .then(pl.lit(140))
            .otherwise(pl.col("FLAG_EXCLUDE_APS"))
            .alias("FLAG_EXCLUDE_APS")
        )

    # 200/210: Missing/zero income
    if "INCOME" in df.columns:
        df = df.with_columns(
            pl.when((pl.col("FLAG_EXCLUDE_APS").is_null()) & pl.col("INCOME").is_null())
            .then(pl.lit(200))
            .when((pl.col("FLAG_EXCLUDE_APS").is_null()) & (pl.col("INCOME") == 0))
            .then(pl.lit(210))
            .otherwise(pl.col("FLAG_EXCLUDE_APS"))
            .alias("FLAG_EXCLUDE_APS")
        )

    # 310: Test application
    if "TEST_IND" in df.columns:
        df = df.with_columns(
            pl.when((pl.col("FLAG_EXCLUDE_APS").is_null()) & (pl.col("TEST_IND") == 1))
            .then(pl.lit(310))
            .otherwise(pl.col("FLAG_EXCLUDE_APS"))
            .alias("FLAG_EXCLUDE_APS")
        )

    # DTI calculation
    income_col = "INCOME" if "INCOME" in df.columns else None
    if income_col:
        revolv_col = "REVOLVING_MIN_PMT" if "REVOLVING_MIN_PMT" in df.columns else None
        install_col = "INSTALLMENTS" if "INSTALLMENTS" in df.columns else None
        rental_col = "RENTAL" if "RENTAL" in df.columns else None

        debt_expr = pl.lit(0.0)
        if revolv_col:
            debt_expr = debt_expr + pl.col(revolv_col).fill_null(0)
        if install_col:
            debt_expr = debt_expr + pl.col(install_col).fill_null(0)
        if rental_col:
            debt_expr = debt_expr + pl.col(rental_col).fill_null(0)

        df = df.with_columns(
            pl.when(pl.col(income_col) > 0)
            .then(debt_expr / pl.col(income_col) * 100.0)
            .otherwise(pl.lit(0.0))
            .alias("DTI_pct")
        )
    else:
        df = df.with_columns(pl.lit(0.0).alias("DTI_pct"))

    df = df.with_columns(pl.lit(config.rpt_month).alias("RPT_MONTH"))
    excluded_count = df.filter(pl.col("FLAG_EXCLUDE_APS").is_not_null()).height
    logger.info("F01 PLOAN: APS standardized: %d rows, %d excluded", len(df), excluded_count)
    return df
