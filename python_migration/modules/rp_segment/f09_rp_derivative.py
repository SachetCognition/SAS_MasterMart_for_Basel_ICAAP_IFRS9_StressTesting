"""
RP Derivative stress.

Translated from Code/90.RP_SEGMENT/F_09_RP_DERIVATIVE.sas.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config
    from modules.rp_segment.f04_parameter import RPParameters

logger = logging.getLogger(__name__)


def run(config: Config, derivative: pl.DataFrame, params: RPParameters) -> pl.DataFrame:
    """Apply RP stress to derivative segment with CE multiplier."""
    if derivative.is_empty():
        logger.warning("F09 RP: Empty derivative segment")
        return derivative

    df = derivative.clone()
    cur_exp_col = "CUR_EXP_AMT_HKE" if "CUR_EXP_AMT_HKE" in df.columns else None
    pot_exp_col = "POTENT_EXP_AMT_HKE" if "POTENT_EXP_AMT_HKE" in df.columns else None
    rw_col = "APPL_RISK_WEIGHT" if "APPL_RISK_WEIGHT" in df.columns else None

    for i in range(4):
        suffix = f"ST{i}"
        multiplier = params.deriv_ce_multiplier[i]

        # Stressed current exposure
        if cur_exp_col:
            df = df.with_columns(
                (pl.col(cur_exp_col).fill_null(0) * multiplier).alias(f"CUR_EXP_{suffix}")
            )
        else:
            df = df.with_columns(pl.lit(0.0).alias(f"CUR_EXP_{suffix}"))

        # CRM = CUR_EXP + POTENT_EXP
        pot_val = pl.col(pot_exp_col).fill_null(0) if pot_exp_col else pl.lit(0.0)
        df = df.with_columns((pl.col(f"CUR_EXP_{suffix}") + pot_val).alias(f"CRM_{suffix}"))

        # RW
        if rw_col:
            df = df.with_columns(pl.col(rw_col).fill_null(100.0).alias(f"RW_{suffix}"))
        else:
            df = df.with_columns(pl.lit(100.0).alias(f"RW_{suffix}"))

        # RWA, EAD, EL
        df = df.with_columns(
            (pl.col(f"CRM_{suffix}") * pl.col(f"RW_{suffix}") / 100.0).alias(f"RWA_{suffix}")
        )
        df = df.with_columns(pl.col(f"CRM_{suffix}").alias(f"EAD_{suffix}"))
        df = df.with_columns(pl.lit(0.0).alias(f"EL_{suffix}"))

    logger.info("F09 RP: Derivative stress: %d rows", len(df))
    return df
