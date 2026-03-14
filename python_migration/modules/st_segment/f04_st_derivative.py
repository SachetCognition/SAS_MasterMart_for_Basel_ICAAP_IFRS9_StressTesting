"""
Derivative stress with current exposure multiplier.

Translated from Code/05.ST_SEGMENT/F_04_ST_DERIVATIVE.sas (~60 lines).
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
    derivative: pl.DataFrame,
    params: StressParameters,
) -> pl.DataFrame:
    """
    Apply stress to derivative segment via CE multiplier.

    For each scenario ST0-ST3:
      - CUR_EXP_STi = CUR_EXP_AMT_HKE * deriv_ce_multiplier[i]
      - CRM_STi = CUR_EXP_STi + POTENT_EXP_AMT_HKE
      - RWA_STi = CRM_STi * APPL_RISK_WEIGHT / 100

    Parameters
    ----------
    config : Config
    derivative : pl.DataFrame
        Derivative segment from f02_segment.
    params : StressParameters

    Returns
    -------
    pl.DataFrame
        Stressed derivative dataset with ST0-ST3 columns.
    """
    if derivative.is_empty():
        logger.warning("F04 ST: Empty derivative segment")
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

        # CRM = stressed CE + potential exposure
        pot_val = pl.col(pot_exp_col).fill_null(0) if pot_exp_col else pl.lit(0.0)
        df = df.with_columns(
            (pl.col(f"CUR_EXP_{suffix}") + pot_val).alias(f"CRM_{suffix}")
        )

        # RWA
        if rw_col:
            df = df.with_columns(
                (pl.col(f"CRM_{suffix}") * pl.col(rw_col).fill_null(100) / 100.0)
                .alias(f"RWA_{suffix}")
            )
        else:
            df = df.with_columns(pl.col(f"CRM_{suffix}").alias(f"RWA_{suffix}"))

        # EAD = CRM (derivatives are fully on-balance equivalent)
        df = df.with_columns(pl.col(f"CRM_{suffix}").alias(f"EAD_{suffix}"))

    logger.info("F04 ST: Derivative stress: %d rows, 4 scenarios", len(df))
    return df
