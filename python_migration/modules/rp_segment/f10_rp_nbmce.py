"""
RP NBMCE stress calculations.

Translated from Code/90.RP_SEGMENT/F_10_RP_NBMCE.sas.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config
    from modules.rp_segment.f04_parameter import RPParameters

logger = logging.getLogger(__name__)


def run(config: Config, nbmce: pl.DataFrame, params: RPParameters) -> pl.DataFrame:
    """Apply RP stress to NBMCE segment."""
    if nbmce.is_empty():
        logger.warning("F10 RP: Empty NBMCE segment")
        return nbmce

    df = nbmce.clone()
    crm_col = "APPL_CRM_AMT_HKE" if "APPL_CRM_AMT_HKE" in df.columns else "ORIG_CRM_AMT_HKE"
    rw_col = "APPL_RISK_WEIGHT" if "APPL_RISK_WEIGHT" in df.columns else None

    # Get NBMCE segment params if available
    seg_params = params.segment_params.get("NBMCE", None)

    for i in range(4):
        suffix = f"ST{i}"
        npl_target = seg_params.npl_target[i] if seg_params else 0.0
        lgd_val = seg_params.lgd[i] if seg_params else 0.45

        if rw_col:
            df = df.with_columns(pl.col(rw_col).fill_null(100.0).alias(f"RW_{suffix}"))
        else:
            df = df.with_columns(pl.lit(100.0).alias(f"RW_{suffix}"))

        if crm_col in df.columns:
            df = df.with_columns(pl.col(crm_col).fill_null(0).alias(f"CRM_{suffix}"))
            df = df.with_columns(
                (pl.col(f"CRM_{suffix}") * pl.col(f"RW_{suffix}") / 100.0).alias(f"RWA_{suffix}")
            )
            df = df.with_columns(pl.col(f"CRM_{suffix}").alias(f"EAD_{suffix}"))
            df = df.with_columns(
                (pl.col(f"EAD_{suffix}") * npl_target * lgd_val).alias(f"EL_{suffix}")
            )

    logger.info("F10 RP: NBMCE stress: %d rows", len(df))
    return df
