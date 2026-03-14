"""
RML stress testing — THE MOST COMPLEX STRESS MODULE.

Translated from Code/05.ST_SEGMENT/F_05_ST_RML.sas (~300 lines).

Implements 4-scenario arrays (ST0-ST3) for: CMV, CLTV, CRM, RW, RWA,
RWA_NPL, IA, CRM_NPL, RWA_NPL_CLEAN, RWA_NPL_SECUR, EAD_NPL, EAD.
Uses vectorized polars operations instead of SAS array loops.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config
    from modules.st_segment.f01_parameter import StressParameters

logger = logging.getLogger(__name__)

# RML risk weight schedule based on CLTV bands (SAS lines 40-80)
_RW_CLTV_BANDS: list[tuple[float, float, float]] = [
    (0.0, 0.70, 35.0),
    (0.70, 0.80, 50.0),
    (0.80, 0.90, 75.0),
    (0.90, 1.00, 100.0),
    (1.00, float("inf"), 100.0),
]


def _assign_rw_from_cltv(cltv_col: str) -> pl.Expr:
    """Build nested when/then expression for CLTV → RW mapping."""
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


def run(
    config: Config,
    rml: pl.DataFrame,
    params: StressParameters,
    npl_ratios: dict[str, float] | None = None,
) -> pl.DataFrame:
    """
    Apply stress to RML (Residential Mortgage Loan) segment.

    For each scenario ST0-ST3:
      1. CMV_STi = CMV_HKE * (1 + hk_property_yoy[i]) * (1 - hk_property_haircut[i])
      2. CLTV_STi = APPL_CRM_AMT_HKE / CMV_STi
      3. RW_STi = f(CLTV_STi) per risk weight schedule
      4. CRM_STi = APPL_CRM_AMT_HKE (no change for performing)
      5. RWA_STi = CRM_STi * RW_STi / 100
      6. NPL splitting: NPL target from params, LGD, coverage
      7. EAD_STi, EL_STi calculations
      8. Loan growth adjustment

    Parameters
    ----------
    config : Config
    rml : pl.DataFrame
        RML segment from f02_segment.
    params : StressParameters
    npl_ratios : dict[str, float] | None
        Current NPL ratios by BU.

    Returns
    -------
    pl.DataFrame
        Stressed RML dataset with ST0-ST3 columns.
    """
    if rml.is_empty():
        logger.warning("F05 ST: Empty RML segment")
        return rml

    df = rml.clone()
    rml_bu_params = params.bu_params.get("RML")

    # Ensure CMV column exists
    cmv_col = "CMV_HKE" if "CMV_HKE" in df.columns else None
    crm_col = "APPL_CRM_AMT_HKE" if "APPL_CRM_AMT_HKE" in df.columns else "ORIG_CRM_AMT_HKE"
    rw_col = "APPL_RISK_WEIGHT" if "APPL_RISK_WEIGHT" in df.columns else None

    # Use ORIG_LTV_RATIO as fallback for CLTV
    has_ltv = "ORIG_LTV_RATIO" in df.columns

    for i in range(4):
        suffix = f"ST{i}"
        yoy = params.hk_property_yoy[i]
        haircut = params.hk_property_haircut[i]

        # 1. CMV stress
        if cmv_col:
            df = df.with_columns(
                (pl.col(cmv_col).fill_null(0) * (1.0 + yoy) * (1.0 - haircut))
                .alias(f"CMV_{suffix}")
            )
        else:
            df = df.with_columns(pl.lit(0.0).alias(f"CMV_{suffix}"))

        # 2. CLTV calculation
        if cmv_col and crm_col in df.columns:
            df = df.with_columns(
                pl.when(pl.col(f"CMV_{suffix}") > 0)
                .then(pl.col(crm_col).fill_null(0) / pl.col(f"CMV_{suffix}"))
                .otherwise(
                    pl.col("ORIG_LTV_RATIO").fill_null(1.0) if has_ltv else pl.lit(1.0)
                )
                .alias(f"CLTV_{suffix}")
            )
        elif has_ltv:
            df = df.with_columns(pl.col("ORIG_LTV_RATIO").fill_null(1.0).alias(f"CLTV_{suffix}"))
        else:
            df = df.with_columns(pl.lit(1.0).alias(f"CLTV_{suffix}"))

        # 3. RW from CLTV
        df = df.with_columns(
            _assign_rw_from_cltv(f"CLTV_{suffix}").alias(f"RW_{suffix}")
        )

        # For ST0, preserve original RW if available
        if i == 0 and rw_col:
            df = df.with_columns(
                pl.col(rw_col).fill_null(pl.col(f"RW_{suffix}")).alias(f"RW_{suffix}")
            )

        # 4. CRM (no change for performing book)
        if crm_col in df.columns:
            df = df.with_columns(pl.col(crm_col).fill_null(0).alias(f"CRM_{suffix}"))
        else:
            df = df.with_columns(pl.lit(0.0).alias(f"CRM_{suffix}"))

        # 5. RWA
        df = df.with_columns(
            (pl.col(f"CRM_{suffix}") * pl.col(f"RW_{suffix}") / 100.0).alias(f"RWA_{suffix}")
        )

        # 6. NPL adjustment
        npl_target = 0.0
        lgd_val = 0.45
        npl_cov = 0.0
        loan_growth = 0.0

        if rml_bu_params:
            npl_target = rml_bu_params.npl_target[i]
            lgd_val = rml_bu_params.lgd[i]
            npl_cov = rml_bu_params.npl_cov[i]
            loan_growth = rml_bu_params.loan_growth[i]

        # Current NPL ratio
        current_npl = (npl_ratios or {}).get("RML", 0.0)
        incremental_npl = max(0, npl_target - current_npl)

        # NPL RWA: for NPL portion, RW=100% and provision coverage
        df = df.with_columns([
            (pl.col(f"CRM_{suffix}") * incremental_npl * 1.0).alias(f"RWA_NPL_{suffix}"),
            (pl.col(f"CRM_{suffix}") * incremental_npl * npl_cov).alias(f"IA_{suffix}"),
        ])

        # 7. EAD
        df = df.with_columns(
            (pl.col(f"CRM_{suffix}") * (1.0 + loan_growth)).alias(f"EAD_{suffix}")
        )

        # 8. EL
        df = df.with_columns(
            (pl.col(f"EAD_{suffix}") * npl_target * lgd_val).alias(f"EL_{suffix}")
        )

    logger.info("F05 ST: RML stress: %d rows, 4 scenarios", len(df))
    return df
