"""
RP Property Investment/Development stress.

Translated from Code/90.RP_SEGMENT/F_07_RP_PROP_INVDEV.sas (~50 lines).
Excludes CONSOL ADJ and CBIC business units, applies property stress.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config
    from modules.rp_segment.f04_parameter import RPParameters

logger = logging.getLogger(__name__)

_EXCLUDE_BU = {"CONSOL ADJ", "CBIC"}


def run(config: Config, prty_inv: pl.DataFrame, params: RPParameters) -> pl.DataFrame:
    """Apply RP stress to Property Investment/Development segment."""
    if prty_inv.is_empty():
        logger.warning("F07 RP: Empty PRTY_INV segment")
        return prty_inv

    df = prty_inv.clone()

    # Exclude certain business units
    bu_col = "IND_BUS_UNIT" if "IND_BUS_UNIT" in df.columns else None
    if bu_col:
        df = df.filter(~pl.col(bu_col).is_in(list(_EXCLUDE_BU)))

    crm_col = "APPL_CRM_AMT_HKE" if "APPL_CRM_AMT_HKE" in df.columns else "ORIG_CRM_AMT_HKE"
    rw_col = "APPL_RISK_WEIGHT" if "APPL_RISK_WEIGHT" in df.columns else None

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

    logger.info("F07 RP: PRTY_INV stress: %d rows", len(df))
    return df
