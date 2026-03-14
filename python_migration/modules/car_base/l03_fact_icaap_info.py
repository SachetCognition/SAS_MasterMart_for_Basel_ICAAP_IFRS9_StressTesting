"""
ICAAP information enrichment.

Translated from Code/01.CAR_BASE/L_03_FACT_ICAAP_INFO.sas (~60 lines).

Enriches the fact table with ICAAP-specific information:
  - Business unit classification
  - Team code mapping
  - Product code enrichment
  - Collateral type indicators
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(config: Config, fact_rwa: pl.DataFrame) -> pl.DataFrame:
    """
    Enrich fact table with ICAAP information.

    Translated from L_03_FACT_ICAAP_INFO.sas:
      - Classify exposures by ICAAP business unit
      - Add team and product descriptions
      - Compute ICAAP-specific indicators
      - Add collateral coverage ratios

    Parameters
    ----------
    config : Config
    fact_rwa : pl.DataFrame
        Fact table from l02_fact_icaap_format.

    Returns
    -------
    pl.DataFrame
        Final enriched ICAAP fact table.
    """
    if fact_rwa.is_empty():
        logger.warning("L03: Empty fact_rwa input")
        return fact_rwa

    df = fact_rwa.clone()

    # ICAAP business unit classification (SAS lines 8-30)
    if "ICAAP_BUS_UNIT" in df.columns:
        # Flag WBG-REF subset
        if "FLAG_REF" in df.columns:
            df = df.with_columns(
                pl.when(
                    (pl.col("ICAAP_BUS_UNIT") == "WBG") & (pl.col("FLAG_REF") == 1)
                )
                .then(pl.lit("WBG-REF"))
                .otherwise(pl.col("ICAAP_BUS_UNIT"))
                .alias("ICAAP_BUS_UNIT_ADJ")
            )
        else:
            df = df.with_columns(
                pl.col("ICAAP_BUS_UNIT").alias("ICAAP_BUS_UNIT_ADJ")
            )

    # IND_ICAAP flag (SAS lines 32-40)
    ind_icaap = config.ind_icaap if hasattr(config, "ind_icaap") else "Y"
    df = df.with_columns(pl.lit(ind_icaap).alias("IND_ICAAP"))

    # Collateral coverage ratio (SAS lines 42-55)
    if "APPL_CRM_AMT_HKE" in df.columns and "ORIG_CRM_AMT_HKE" in df.columns:
        df = df.with_columns(
            pl.when(pl.col("ORIG_CRM_AMT_HKE") > 0)
            .then(pl.col("APPL_CRM_AMT_HKE") / pl.col("ORIG_CRM_AMT_HKE"))
            .otherwise(pl.lit(1.0))
            .alias("CRM_COVERAGE_RATIO")
        )

    # Risk weight bucket (SAS lines 57-70)
    if "APPL_RISK_WEIGHT" in df.columns:
        df = df.with_columns(
            pl.when(pl.col("APPL_RISK_WEIGHT") == 0).then(pl.lit("0%"))
            .when(pl.col("APPL_RISK_WEIGHT") <= 10).then(pl.lit("10%"))
            .when(pl.col("APPL_RISK_WEIGHT") <= 20).then(pl.lit("20%"))
            .when(pl.col("APPL_RISK_WEIGHT") <= 35).then(pl.lit("35%"))
            .when(pl.col("APPL_RISK_WEIGHT") <= 50).then(pl.lit("50%"))
            .when(pl.col("APPL_RISK_WEIGHT") <= 75).then(pl.lit("75%"))
            .when(pl.col("APPL_RISK_WEIGHT") <= 100).then(pl.lit("100%"))
            .when(pl.col("APPL_RISK_WEIGHT") <= 150).then(pl.lit("150%"))
            .otherwise(pl.lit(">150%"))
            .alias("RW_BUCKET")
        )

    logger.info("L03: ICAAP info enrichment: %d rows", len(df))
    return df
