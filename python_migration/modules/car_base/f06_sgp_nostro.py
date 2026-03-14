"""
Singapore Nostro processing.

Translated from Code/01.CAR_BASE/F_06_SGP_NOSTRO.sas (~60 lines).

Processes SGP Nostro data into staging format with PORT_CD assignment
and HKE amount calculation for nostro/vostro accounts.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(
    config: Config,
    sgp_nostro: pl.DataFrame,
) -> pl.DataFrame:
    """
    Process SGP Nostro data into staging format.

    Translated from F_06_SGP_NOSTRO.sas:
      - Assign PORT_CD = 'IV' (bank exposure)
      - Set APPL_RISK_WEIGHT = 20 (standard bank RW)
      - Calculate RISK_WEIGHTED_AMT_HKE
      - Tag with FILE_SRC = 'SGP-Nostro'

    Parameters
    ----------
    config : Config
    sgp_nostro : pl.DataFrame
        Raw SGP Nostro data from import_basel_sgp.

    Returns
    -------
    pl.DataFrame
        adj_sgp_nostro_tb staging dataset.
    """
    if sgp_nostro.is_empty():
        logger.warning("F06: Empty SGP Nostro input")
        return pl.DataFrame()

    df = sgp_nostro.clone()

    # Add standard identifiers
    df = df.with_columns([
        pl.lit("SGP-Nostro").alias("FILE_SRC"),
        pl.lit("KW").alias("FLAG_SRC"),
        pl.lit("SGBR").alias("ENTITY"),
        pl.lit("IV").alias("PORT_CD"),
        pl.lit(20.0).alias("APPL_RISK_WEIGHT"),
        pl.lit(104.0).alias("FLAG_ADJ"),
        pl.lit(config.rpt_month).alias("RPT_MONTH"),
    ])

    # Standardize amount columns
    if "AMT_HKE" in df.columns:
        df = df.rename({"AMT_HKE": "CUR_BAL_ON_HKE"})
    elif "AMOUNT" in df.columns:
        df = df.rename({"AMOUNT": "CUR_BAL_ON_HKE"})

    # Set CRM = balance for nostro (fully on-balance)
    if "CUR_BAL_ON_HKE" in df.columns:
        df = df.with_columns([
            pl.col("CUR_BAL_ON_HKE").alias("ORIG_CRM_AMT_HKE"),
            pl.col("CUR_BAL_ON_HKE").alias("APPL_CRM_AMT_HKE"),
            (pl.col("CUR_BAL_ON_HKE") * 20.0 / 100.0).alias("RISK_WEIGHTED_AMT_HKE"),
        ])

    # Zero out off-balance columns
    df = df.with_columns([
        pl.lit(0.0).alias("CUR_BAL_OFF_HKE"),
        pl.lit(0.0).alias("CUR_EXP_AMT_HKE"),
        pl.lit(0.0).alias("POTENT_EXP_AMT_HKE"),
        pl.lit(0.0).alias("PROVISION_AMT_HKE"),
    ])

    logger.info("F06: SGP Nostro staging: %d rows", len(df))
    return df
