"""
Join NBMCE data with main fact table for RST.

Translated from Code/04.RST_SEGMENT/F_03_JOIN_NBMCE.sas.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config
logger = logging.getLogger(__name__)

def run(config: Config, fact_rwa: pl.DataFrame, rst_nbmce: pl.DataFrame) -> pl.DataFrame:
    """Join NBMCE RST data with master fact table."""
    if fact_rwa.is_empty():
        logger.warning("F03 RST: Empty fact table")
        return pl.DataFrame()
    df = fact_rwa.clone()
    if not rst_nbmce.is_empty():
        join_key = None
        for candidate in ["ACCT_ID", "CUST_SEC_ID"]:
            if candidate in df.columns and candidate in rst_nbmce.columns:
                join_key = candidate
                break
        if join_key:
            nbmce_cols = [c for c in rst_nbmce.columns if c not in df.columns or c == join_key]
            df = df.join(rst_nbmce.select(nbmce_cols).unique(subset=[join_key]), on=join_key, how="left")
    logger.info("F03 RST: Joined NBMCE: %d rows", len(df))
    return df
