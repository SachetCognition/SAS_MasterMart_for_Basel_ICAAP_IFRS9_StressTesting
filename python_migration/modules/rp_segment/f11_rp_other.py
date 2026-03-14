"""
RP Other segments stress (pass-through).

Translated from Code/90.RP_SEGMENT/F_11_RP_OTHER.sas.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config
    from modules.rp_segment.f04_parameter import RPParameters

logger = logging.getLogger(__name__)


def run(config: Config, other: pl.DataFrame, params: RPParameters) -> pl.DataFrame:
    """Apply RP stress to other segments (pass-through with RWA preservation)."""
    if other.is_empty():
        return other

    df = other.clone()
    crm_col = "APPL_CRM_AMT_HKE" if "APPL_CRM_AMT_HKE" in df.columns else "ORIG_CRM_AMT_HKE"
    rw_col = "APPL_RISK_WEIGHT" if "APPL_RISK_WEIGHT" in df.columns else None
    rwa_col = "RISK_WEIGHTED_AMT_HKE" if "RISK_WEIGHTED_AMT_HKE" in df.columns else None

    for i in range(4):
        suffix = f"ST{i}"
        if rw_col:
            df = df.with_columns(pl.col(rw_col).fill_null(100.0).alias(f"RW_{suffix}"))
        else:
            df = df.with_columns(pl.lit(100.0).alias(f"RW_{suffix}"))

        if crm_col in df.columns:
            df = df.with_columns(pl.col(crm_col).fill_null(0).alias(f"CRM_{suffix}"))
        else:
            df = df.with_columns(pl.lit(0.0).alias(f"CRM_{suffix}"))

        if rwa_col and i == 0:
            df = df.with_columns(pl.col(rwa_col).fill_null(0).alias(f"RWA_{suffix}"))
        else:
            df = df.with_columns(
                (pl.col(f"CRM_{suffix}") * pl.col(f"RW_{suffix}") / 100.0).alias(f"RWA_{suffix}")
            )

        df = df.with_columns(pl.col(f"CRM_{suffix}").alias(f"EAD_{suffix}"))
        df = df.with_columns(pl.lit(0.0).alias(f"EL_{suffix}"))

    logger.info("F11 RP: Other stress: %d rows", len(df))
    return df
