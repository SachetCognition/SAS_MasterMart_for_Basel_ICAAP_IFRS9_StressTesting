"""
RST NBMCE stress calculations.

Translated from Code/04.RST_SEGMENT/F_10_RST_NBMCE.sas.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config
    from modules.rst_segment.f04_parameter import RSTParameters

logger = logging.getLogger(__name__)


def run(config: Config, nbmce: pl.DataFrame, params: RSTParameters) -> pl.DataFrame:
    """Apply RST stress to NBMCE segment."""
    if nbmce.is_empty():
        logger.warning("F10 RST: Empty NBMCE segment")
        return nbmce

    df = nbmce.clone()
    crm_col = "APPL_CRM_AMT_HKE" if "APPL_CRM_AMT_HKE" in df.columns else "ORIG_CRM_AMT_HKE"
    rw_col = "APPL_RISK_WEIGHT" if "APPL_RISK_WEIGHT" in df.columns else None

    for i in range(4):
        suffix = f"ST{i}"
        npl_target = params.nbmce_npl_target[i]
        lgd_val = params.nbmce_lgd[i]

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

    logger.info("F10 RST: NBMCE stress: %d rows", len(df))
    return df
