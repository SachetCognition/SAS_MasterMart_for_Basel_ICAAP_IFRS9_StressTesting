"""
Non-RML stress testing.

Translated from Code/05.ST_SEGMENT/F_07_ST_NONRML.sas (~200 lines).

Uses %genSTTable macro pattern called for 9 business units.
In Python, implement as a function called in a loop.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config
    from modules.st_segment.f01_parameter import StressParameters

logger = logging.getLogger(__name__)

# Business units processed for Non-RML stress
_BU_LIST = ["WBG", "WBG_REF", "IBG", "IBG_SGP", "IBG_SGP_MAS", "CBIC", "BB", "CTU", "ORR"]


def _stress_bu(
    df: pl.DataFrame,
    bu_name: str,
    params: StressParameters,
    npl_ratios: dict[str, float],
    scenario_idx: int,
) -> pl.DataFrame:
    """Apply stress for a single BU and scenario."""
    suffix = f"ST{scenario_idx}"

    # Get BU-specific parameters
    # Map compound BU names to parameter BU names
    param_bu = bu_name.split("_")[0] if "_" in bu_name else bu_name
    bu_params = params.bu_params.get(param_bu)

    npl_target = bu_params.npl_target[scenario_idx] if bu_params else 0.0
    lgd_val = bu_params.lgd[scenario_idx] if bu_params else 0.45
    npl_cov = bu_params.npl_cov[scenario_idx] if bu_params else 0.0
    loan_growth = bu_params.loan_growth[scenario_idx] if bu_params else 0.0

    current_npl = npl_ratios.get(param_bu, 0.0)
    incremental_npl = max(0, npl_target - current_npl)

    crm_col = "APPL_CRM_AMT_HKE" if "APPL_CRM_AMT_HKE" in df.columns else "ORIG_CRM_AMT_HKE"
    rw_col = "APPL_RISK_WEIGHT" if "APPL_RISK_WEIGHT" in df.columns else None

    # CRM preserved
    if crm_col in df.columns:
        df = df.with_columns(pl.col(crm_col).fill_null(0).alias(f"CRM_{suffix}"))
    else:
        df = df.with_columns(pl.lit(0.0).alias(f"CRM_{suffix}"))

    # RW preserved
    if rw_col:
        df = df.with_columns(pl.col(rw_col).fill_null(100.0).alias(f"RW_{suffix}"))
    else:
        df = df.with_columns(pl.lit(100.0).alias(f"RW_{suffix}"))

    # RWA = CRM * RW / 100
    df = df.with_columns(
        (pl.col(f"CRM_{suffix}") * pl.col(f"RW_{suffix}") / 100.0).alias(f"RWA_{suffix}")
    )

    # NPL RWA
    df = df.with_columns(
        (pl.col(f"CRM_{suffix}") * incremental_npl).alias(f"RWA_NPL_{suffix}")
    )

    # Impairment allowance
    df = df.with_columns(
        (pl.col(f"CRM_{suffix}") * incremental_npl * npl_cov).alias(f"IA_{suffix}")
    )

    # EAD with loan growth
    df = df.with_columns(
        (pl.col(f"CRM_{suffix}") * (1.0 + loan_growth)).alias(f"EAD_{suffix}")
    )

    # EL = EAD * NPL_target * LGD
    df = df.with_columns(
        (pl.col(f"EAD_{suffix}") * npl_target * lgd_val).alias(f"EL_{suffix}")
    )

    return df


def run(
    config: Config,
    nonrml: pl.DataFrame,
    params: StressParameters,
    npl_ratios: dict[str, float] | None = None,
) -> pl.DataFrame:
    """
    Apply stress to Non-RML segment by business unit.

    Parameters
    ----------
    config : Config
    nonrml : pl.DataFrame
        Non-RML segment from f02_segment.
    params : StressParameters
    npl_ratios : dict[str, float] | None
        NPL ratios by BU.

    Returns
    -------
    pl.DataFrame
        Stressed Non-RML dataset.
    """
    if nonrml.is_empty():
        logger.warning("F07 ST: Empty Non-RML segment")
        return nonrml

    npl_ratios = npl_ratios or {}
    bu_col = None
    for candidate in ["ICAAP_BUS_UNIT_ADJ", "ICAAP_BUS_UNIT", "BUS_UNIT"]:
        if candidate in nonrml.columns:
            bu_col = candidate
            break

    frames: list[pl.DataFrame] = []

    for bu in _BU_LIST:
        if bu_col:
            bu_df = nonrml.filter(pl.col(bu_col).cast(pl.Utf8).str.to_uppercase() == bu.upper())
        else:
            bu_df = nonrml if bu == _BU_LIST[0] else pl.DataFrame()

        if bu_df.is_empty():
            continue

        # Apply all 4 scenarios
        for i in range(4):
            bu_df = _stress_bu(bu_df, bu, params, npl_ratios, i)

        frames.append(bu_df)

    # Handle records not matching any BU
    if bu_col:
        bu_upper = [b.upper() for b in _BU_LIST]
        unmatched = nonrml.filter(~pl.col(bu_col).cast(pl.Utf8).str.to_uppercase().is_in(bu_upper))
        if not unmatched.is_empty():
            for i in range(4):
                unmatched = _stress_bu(unmatched, "OTHER", params, npl_ratios, i)
            frames.append(unmatched)

    if not frames:
        return nonrml

    result = pl.concat(frames, how="diagonal")
    logger.info("F07 ST: Non-RML stress: %d rows across %d BUs", len(result), len(frames))
    return result
