"""
Other segments stress (Sovereign/PSE/MDB, Cash, Past Due, Exceptions).

Translated from Code/05.ST_SEGMENT/F_06_ST_OTHER.sas (~50 lines).

These segments have minimal or no stress — baseline values carried through.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config
    from modules.st_segment.f01_parameter import StressParameters

logger = logging.getLogger(__name__)


def run(
    config: Config,
    segment_df: pl.DataFrame,
    params: StressParameters,
    segment_name: str = "OTHER",
) -> pl.DataFrame:
    """
    Apply stress to non-specialized segments (pass-through with RWA preservation).

    For Sovereign/PSE/MDB, Cash, Past Due, Exceptions:
      ST0 = baseline (original values)
      ST1-ST3 = same as baseline (no stress applied to these segments)

    Parameters
    ----------
    config : Config
    segment_df : pl.DataFrame
    params : StressParameters
    segment_name : str

    Returns
    -------
    pl.DataFrame
    """
    if segment_df.is_empty():
        logger.info("F06 ST: Empty %s segment", segment_name)
        return segment_df

    df = segment_df.clone()
    crm_col = "APPL_CRM_AMT_HKE" if "APPL_CRM_AMT_HKE" in df.columns else "ORIG_CRM_AMT_HKE"
    rw_col = "APPL_RISK_WEIGHT" if "APPL_RISK_WEIGHT" in df.columns else None
    rwa_col = "RISK_WEIGHTED_AMT_HKE" if "RISK_WEIGHTED_AMT_HKE" in df.columns else None

    for i in range(4):
        suffix = f"ST{i}"

        # RW preserved across all scenarios
        if rw_col:
            df = df.with_columns(pl.col(rw_col).fill_null(100.0).alias(f"RW_{suffix}"))
        else:
            df = df.with_columns(pl.lit(100.0).alias(f"RW_{suffix}"))

        # CRM preserved
        if crm_col in df.columns:
            df = df.with_columns(pl.col(crm_col).fill_null(0).alias(f"CRM_{suffix}"))
        else:
            df = df.with_columns(pl.lit(0.0).alias(f"CRM_{suffix}"))

        # RWA preserved from original or recalculated
        if rwa_col and i == 0:
            df = df.with_columns(pl.col(rwa_col).fill_null(0).alias(f"RWA_{suffix}"))
        else:
            df = df.with_columns(
                (pl.col(f"CRM_{suffix}") * pl.col(f"RW_{suffix}") / 100.0).alias(f"RWA_{suffix}")
            )

        # EAD = CRM (no CCF adjustment for these segments)
        df = df.with_columns(pl.col(f"CRM_{suffix}").alias(f"EAD_{suffix}"))

        # EL = 0 for these segments (no default expected)
        df = df.with_columns(pl.lit(0.0).alias(f"EL_{suffix}"))

    logger.info("F06 ST: %s stress (pass-through): %d rows", segment_name, len(df))
    return df
