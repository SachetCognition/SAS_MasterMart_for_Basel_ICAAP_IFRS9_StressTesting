"""
Define all PROC FORMAT lookups as Python dicts for ICAAP reporting.

Translated from Code/01.CAR_BASE/L_02_FACT_ICAAP_FORMAT.sas (~80 lines).

Creates portfolio code and business unit mappings used for ICAAP
segmentation and reporting.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

from lib.lookups import BUSUNIT_MAP, PORTCD_MAP, apply_lookup

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(config: Config, fact_rwa: pl.DataFrame) -> pl.DataFrame:
    """
    Apply ICAAP format lookups to the master fact table.

    Translated from L_02_FACT_ICAAP_FORMAT.sas:
      - Map PORT_CD → ICAAP_PORTCD_DESC using portcd format
      - Map ICAAP_BUS_UNIT → ICAAP_BU_DESC using busunit format
      - Add ICAAP segment classification
      - Derive ICAAP_ON_OFF indicator

    Parameters
    ----------
    config : Config
    fact_rwa : pl.DataFrame
        Master fact table from l01_fact_rwa.

    Returns
    -------
    pl.DataFrame
        Enriched fact table with ICAAP format columns.
    """
    if fact_rwa.is_empty():
        logger.warning("L02: Empty fact_rwa input")
        return fact_rwa

    df = fact_rwa.clone()

    # Apply PORT_CD → ICAAP_PORTCD_DESC (use output_column to avoid overwriting PORT_CD)
    if "PORT_CD" in df.columns:
        df = apply_lookup(df, "PORT_CD", PORTCD_MAP, output_column="ICAAP_PORTCD_DESC", default="99. ###")

    # Apply ICAAP_BUS_UNIT → ICAAP_BU_DESC (use output_column to avoid overwriting)
    if "ICAAP_BUS_UNIT" in df.columns:
        df = apply_lookup(df, "ICAAP_BUS_UNIT", BUSUNIT_MAP, output_column="ICAAP_BU_DESC", default="9.0 Other")

    # Derive ICAAP_ON_OFF indicator based on PORT_CD
    if "PORT_CD" in df.columns:
        df = df.with_columns(
            pl.when(pl.col("PORT_CD").cast(pl.Utf8).str.starts_with("B"))
            .then(pl.lit("OFF"))
            .otherwise(pl.lit("ON"))
            .alias("ICAAP_ON_OFF")
        )

    # Derive ICAAP segment from PORT_CD description
    if "ICAAP_PORTCD_DESC" in df.columns:
        df = df.with_columns(
            pl.col("ICAAP_PORTCD_DESC").cast(pl.Utf8).str.slice(0, 2).str.strip_chars().alias("ICAAP_SEGMENT_CD")
        )

    logger.info("L02: Applied ICAAP formats to %d rows", len(df))
    return df
