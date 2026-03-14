"""
ICAAP combination of stressed datasets.

Translated from Code/05.ST_SEGMENT/F_09_ICAAP_COMBINED.sas (~50 lines).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(config: Config, st_combined: pl.DataFrame) -> pl.DataFrame:
    """
    Produce ICAAP-specific combined stressed dataset.

    Filters and enriches the combined stressed data for ICAAP reporting:
      - Apply IND_ICAAP filter
      - Add ICAAP-specific aggregation columns
      - Calculate capital impact metrics

    Parameters
    ----------
    config : Config
    st_combined : pl.DataFrame
        Combined stressed dataset from f08.

    Returns
    -------
    pl.DataFrame
        ICAAP combined stressed dataset.
    """
    if st_combined.is_empty():
        logger.warning("F09 ST: Empty combined input")
        return st_combined

    df = st_combined.clone()

    # Filter for ICAAP-eligible records
    if "IND_ICAAP" in df.columns:
        df = df.filter(pl.col("IND_ICAAP") == "Y")

    # Calculate incremental RWA (stress - baseline)
    for i in range(1, 4):
        suffix = f"ST{i}"
        if f"RWA_{suffix}" in df.columns and "RWA_ST0" in df.columns:
            df = df.with_columns(
                (pl.col(f"RWA_{suffix}").fill_null(0) - pl.col("RWA_ST0").fill_null(0))
                .alias(f"INCR_RWA_{suffix}")
            )
        if f"EL_{suffix}" in df.columns and "EL_ST0" in df.columns:
            df = df.with_columns(
                (pl.col(f"EL_{suffix}").fill_null(0) - pl.col("EL_ST0").fill_null(0))
                .alias(f"INCR_EL_{suffix}")
            )

    logger.info("F09 ST: ICAAP combined: %d rows", len(df))
    return df
