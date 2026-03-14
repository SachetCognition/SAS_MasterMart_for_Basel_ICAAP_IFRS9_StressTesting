"""
RST RML stress calculations.

Translated from Code/04.RST_SEGMENT/F_06_RST_RML.sas.
Similar to ST RML but uses RST-specific parameters.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config
    from modules.rst_segment.f04_parameter import RSTParameters

logger = logging.getLogger(__name__)

_RW_CLTV_BANDS: list[tuple[float, float, float]] = [
    (0.0, 0.70, 35.0),
    (0.70, 0.80, 50.0),
    (0.80, 0.90, 75.0),
    (0.90, 1.00, 100.0),
    (1.00, float("inf"), 100.0),
]


def _assign_rw_from_cltv(cltv_col: str) -> pl.Expr:
    """Assign risk weight based on CLTV bands."""
    expr = pl.lit(100.0)
    for lower, upper, rw in reversed(_RW_CLTV_BANDS):
        if upper == float("inf"):
            expr = pl.when(pl.col(cltv_col) >= lower).then(pl.lit(rw)).otherwise(expr)
        else:
            expr = (
                pl.when((pl.col(cltv_col) >= lower) & (pl.col(cltv_col) < upper))
                .then(pl.lit(rw))
                .otherwise(expr)
            )
    return expr


def run(config: Config, rml: pl.DataFrame, params: RSTParameters) -> pl.DataFrame:
    """Apply RST stress to RML segment."""
    if rml.is_empty():
        logger.warning("F06 RST: Empty RML segment")
        return rml

    df = rml.clone()
    cmv_col = "CMV_HKE" if "CMV_HKE" in df.columns else None
    crm_col = "APPL_CRM_AMT_HKE" if "APPL_CRM_AMT_HKE" in df.columns else "ORIG_CRM_AMT_HKE"

    for i in range(4):
        suffix = f"ST{i}"
        yoy = params.hk_property_yoy[i]
        haircut = params.hk_property_haircut[i]

        if cmv_col:
            df = df.with_columns(
                (pl.col(cmv_col).fill_null(0) * (1.0 + yoy) * (1.0 - haircut)).alias(f"CMV_{suffix}")
            )
        else:
            df = df.with_columns(pl.lit(0.0).alias(f"CMV_{suffix}"))

        if cmv_col and crm_col in df.columns:
            df = df.with_columns(
                pl.when(pl.col(f"CMV_{suffix}") > 0)
                .then(pl.col(crm_col).fill_null(0) / pl.col(f"CMV_{suffix}"))
                .otherwise(pl.lit(1.0))
                .alias(f"CLTV_{suffix}")
            )
        else:
            df = df.with_columns(pl.lit(1.0).alias(f"CLTV_{suffix}"))

        df = df.with_columns(_assign_rw_from_cltv(f"CLTV_{suffix}").alias(f"RW_{suffix}"))

        if crm_col in df.columns:
            df = df.with_columns(pl.col(crm_col).fill_null(0).alias(f"CRM_{suffix}"))
            df = df.with_columns(
                (pl.col(f"CRM_{suffix}") * pl.col(f"RW_{suffix}") / 100.0).alias(f"RWA_{suffix}")
            )
            df = df.with_columns(pl.col(f"CRM_{suffix}").alias(f"EAD_{suffix}"))

        df = df.with_columns(pl.lit(0.0).alias(f"EL_{suffix}"))

    logger.info("F06 RST: RML stress: %d rows", len(df))
    return df
