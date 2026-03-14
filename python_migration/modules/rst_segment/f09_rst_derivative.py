"""
RST Derivative stress.

Translated from Code/04.RST_SEGMENT/F_09_RST_DERIVATIVE.sas.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config
    from modules.rst_segment.f04_parameter import RSTParameters

logger = logging.getLogger(__name__)


def run(config: Config, derivative: pl.DataFrame, params: RSTParameters) -> pl.DataFrame:
    """Apply RST stress to derivative segment."""
    if derivative.is_empty():
        logger.warning("F09 RST: Empty derivative segment")
        return derivative

    df = derivative.clone()
    rw_col = "APPL_RISK_WEIGHT" if "APPL_RISK_WEIGHT" in df.columns else None
    crm_col = "APPL_CRM_AMT_HKE" if "APPL_CRM_AMT_HKE" in df.columns else "ORIG_CRM_AMT_HKE"

    for i in range(4):
        suffix = f"ST{i}"
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

        df = df.with_columns(pl.lit(0.0).alias(f"EL_{suffix}"))

    logger.info("F09 RST: Derivative stress: %d rows", len(df))
    return df
