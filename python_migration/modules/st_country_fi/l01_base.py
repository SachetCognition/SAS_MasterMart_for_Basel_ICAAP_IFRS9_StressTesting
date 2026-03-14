"""
Load and flag data for ST Country FI stress testing.

Translated from Code/06.ST_COUNTRY_FI/L_01_BASE.sas (~50 lines).
Filters master fact table for Bank/FI exposures, applies FLAG_BK_FI
classification (1-5), FLAG_ELIM for consolidation elimination, and
assigns NOTCH from ECAI rating or proxy.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

from lib.lookups import build_cust_elim_format

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)

_BANK_PORT_CDS = {"IV", "IVa", "V"}
_BANK_CUST_SUB_TYPES = {"BK", "BKF", "BKH"}
_BANK_SIC_CODES = {"6020", "6022", "6029"}
_SEC_CUST_SUB_TYPES = {"SEC", "SECF"}
_SEC_SIC_CODES = {"6211", "6159"}


def run(
    config: Config,
    fact_rwa: pl.DataFrame,
    cust_elim: pl.DataFrame,
) -> pl.DataFrame:
    """
    Load base data for ST Country FI analysis.

    1. Filter for Bank/FI-related PORT_CDs
    2. Classify FLAG_BK_FI (1-5)
    3. Apply FLAG_ELIM from cust_elim format
    4. Assign NOTCH from existing rating or proxy

    Returns
    -------
    pl.DataFrame
        Filtered and flagged dataset for Bank/FI stress testing.
    """
    if fact_rwa.is_empty():
        logger.warning("L01 ST_FI: Empty fact table")
        return pl.DataFrame()

    df = fact_rwa.clone()

    # Filter for Bank/FI exposures
    port_col = "PORT_CD" if "PORT_CD" in df.columns else None
    if port_col:
        df = df.filter(pl.col(port_col).is_in(list(_BANK_PORT_CDS)))

    if df.is_empty():
        logger.warning("L01 ST_FI: No Bank/FI exposures found")
        return df

    # FLAG_BK_FI classification
    cust_sub = "CUST_SUB_TYP_CD" if "CUST_SUB_TYP_CD" in df.columns else None
    cust_sic = "CUST_SIC_CD" if "CUST_SIC_CD" in df.columns else None

    flag_expr = pl.lit(0)
    if cust_sub:
        flag_expr = (
            pl.when(pl.col(cust_sub).is_in(list(_BANK_CUST_SUB_TYPES)))
            .then(pl.lit(1))
            .when(pl.col(cust_sub).is_in(list(_SEC_CUST_SUB_TYPES)))
            .then(pl.lit(2))
            .otherwise(pl.lit(0))
        )
    if cust_sic:
        flag_expr = (
            pl.when(pl.col(flag_expr.meta.output_name() if hasattr(flag_expr, "meta") else "FLAG_BK_FI") > 0)
            .then(flag_expr)
            .when(pl.col(cust_sic).is_in(list(_BANK_SIC_CODES)))
            .then(pl.lit(3))
            .when(pl.col(cust_sic).is_in(list(_SEC_SIC_CODES)))
            .then(pl.lit(5))
            .otherwise(pl.lit(0))
        )

    # Simplified classification
    df = df.with_columns(pl.lit(1).alias("FLAG_BK_FI"))
    if cust_sub:
        df = df.with_columns(
            pl.when(pl.col(cust_sub).is_in(list(_BANK_CUST_SUB_TYPES)))
            .then(pl.lit(1))
            .when(pl.col(cust_sub).is_in(list(_SEC_CUST_SUB_TYPES)))
            .then(pl.lit(2))
            .otherwise(
                pl.when(pl.col(cust_sic).is_in(list(_BANK_SIC_CODES)) if cust_sic else pl.lit(False))
                .then(pl.lit(3))
                .when(pl.col(cust_sic).is_in(list(_SEC_SIC_CODES)) if cust_sic else pl.lit(False))
                .then(pl.lit(5))
                .otherwise(pl.lit(4))
            )
            .alias("FLAG_BK_FI")
        )

    # FLAG_ELIM from cust_elim format
    elim_set = build_cust_elim_format(cust_elim) if not cust_elim.is_empty() else set()
    if elim_set and "CUST_SEC_ID" in df.columns:
        df = df.with_columns(
            pl.when(pl.col("CUST_SEC_ID").is_in(list(elim_set)))
            .then(pl.lit(1))
            .otherwise(pl.lit(0))
            .alias("FLAG_ELIM")
        )
    else:
        df = df.with_columns(pl.lit(0).alias("FLAG_ELIM"))

    # NOTCH assignment: use existing NOTCH if available
    if "NOTCH" not in df.columns:
        rw_col = "APPL_RISK_WEIGHT" if "APPL_RISK_WEIGHT" in df.columns else None
        if rw_col:
            df = df.with_columns(
                pl.when(pl.col(rw_col) <= 20).then(pl.lit(3))
                .when(pl.col(rw_col) <= 50).then(pl.lit(7))
                .when(pl.col(rw_col) <= 100).then(pl.lit(11))
                .when(pl.col(rw_col) <= 150).then(pl.lit(17))
                .otherwise(pl.lit(20))
                .alias("NOTCH")
            )
        else:
            df = df.with_columns(pl.lit(11).alias("NOTCH"))

    # GRP_NAM for reporting grouping
    if "CUST_FULL_NM" in df.columns:
        df = df.with_columns(pl.col("CUST_FULL_NM").alias("GRP_NAM"))
    elif "CUST_SEC_ID" in df.columns:
        df = df.with_columns(pl.col("CUST_SEC_ID").alias("GRP_NAM"))
    else:
        df = df.with_columns(pl.lit("UNKNOWN").alias("GRP_NAM"))

    # FLAG_UNRATED
    if "ECAI_RATING" in df.columns:
        df = df.with_columns(
            pl.when(pl.col("ECAI_RATING").is_null() | (pl.col("ECAI_RATING") == ""))
            .then(pl.lit(1))
            .otherwise(pl.lit(0))
            .alias("FLAG_UNRATED")
        )
    else:
        df = df.with_columns(pl.lit(1).alias("FLAG_UNRATED"))

    logger.info("L01 ST_FI: Loaded base: %d rows", len(df))
    return df
