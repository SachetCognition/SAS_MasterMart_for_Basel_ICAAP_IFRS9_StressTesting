"""
Parse stress parameters from Excel into StressParameters dataclass.

Translated from Code/05.ST_SEGMENT/F_01_PARAMETER.sas (~120 lines).

Replaces all the `call symput` logic with a structured dataclass containing
base/mild/medium/severe values for each stress parameter.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


@dataclass
class BUStressParams:
    """Stress parameters for a single business unit."""

    npl_target: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    lgd: list[float] = field(default_factory=lambda: [0.45, 0.45, 0.45, 0.45])
    npl_cov: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    loan_growth: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])


@dataclass
class StressParameters:
    """
    Complete stress testing parameter set.

    4 scenarios: [base, mild, medium, severe] indexed as ST0-ST3.
    """

    # FI notch shifts (4 scenarios)
    fi_notch_shift: list[int] = field(default_factory=lambda: [0, 1, 3, 5])

    # HK property parameters
    hk_property_yoy: list[float] = field(default_factory=lambda: [0.0, -0.05, -0.15, -0.30])
    hk_property_haircut: list[float] = field(default_factory=lambda: [0.0, 0.05, 0.10, 0.20])

    # CN property parameters
    cn_property_yoy: list[float] = field(default_factory=lambda: [0.0, -0.05, -0.15, -0.30])
    cn_property_haircut: list[float] = field(default_factory=lambda: [0.0, 0.05, 0.10, 0.20])

    # Derivative current exposure multiplier
    deriv_ce_multiplier: list[float] = field(default_factory=lambda: [1.0, 1.1, 1.2, 1.5])

    # Per-BU parameters
    bu_params: dict[str, BUStressParams] = field(default_factory=dict)


def _parse_st_parameter(st_param_df: pl.DataFrame) -> StressParameters:
    """
    Parse ST_Parameter sheet into StressParameters.

    The ST_Parameter sheet has rows for each parameter and columns for
    base/mild/medium/severe scenarios.
    """
    params = StressParameters()

    if st_param_df.is_empty():
        return params

    cols = st_param_df.columns

    # Try to identify scenario columns (typically columns 2-5)
    scenario_cols: list[str] = []
    for col in cols[1:5]:
        scenario_cols.append(col)

    if len(scenario_cols) < 4:
        logger.warning("F01 ST: Expected 4 scenario columns, got %d", len(scenario_cols))
        return params

    param_col = cols[0]

    for row in st_param_df.iter_rows(named=True):
        param_name = str(row.get(param_col, "")).strip().upper()
        values = [float(row.get(sc, 0) or 0) for sc in scenario_cols]

        if "FI" in param_name and "NOTCH" in param_name:
            params.fi_notch_shift = [int(v) for v in values]
        elif "HK" in param_name and "YOY" in param_name:
            params.hk_property_yoy = values
        elif "HK" in param_name and "HAIRCUT" in param_name:
            params.hk_property_haircut = values
        elif "CN" in param_name and "YOY" in param_name:
            params.cn_property_yoy = values
        elif "CN" in param_name and "HAIRCUT" in param_name:
            params.cn_property_haircut = values
        elif "DERIV" in param_name and ("CE" in param_name or "MULTIPLIER" in param_name):
            params.deriv_ce_multiplier = values

    return params


def _parse_bu_params(
    st_param_df: pl.DataFrame,
    bu_list: list[str],
) -> dict[str, BUStressParams]:
    """Parse per-business-unit stress parameters."""
    bu_params: dict[str, BUStressParams] = {}

    if st_param_df.is_empty():
        return bu_params

    cols = st_param_df.columns
    if len(cols) < 5:
        return bu_params

    param_col = cols[0]
    scenario_cols = cols[1:5]

    for row in st_param_df.iter_rows(named=True):
        param_name = str(row.get(param_col, "")).strip().upper()
        values = [float(row.get(sc, 0) or 0) for sc in scenario_cols]

        for bu in bu_list:
            if bu.upper() in param_name:
                if bu not in bu_params:
                    bu_params[bu] = BUStressParams()

                if "NPL" in param_name and "COV" in param_name:
                    bu_params[bu].npl_cov = values
                elif "NPL" in param_name:
                    bu_params[bu].npl_target = values
                elif "LGD" in param_name:
                    bu_params[bu].lgd = values
                elif "LOAN" in param_name and "GROWTH" in param_name:
                    bu_params[bu].loan_growth = values

    return bu_params


def run(
    config: Config,
    st_parameter: pl.DataFrame,
) -> StressParameters:
    """
    Parse stress parameters from the ST_Parameter Excel sheet.

    Parameters
    ----------
    config : Config
    st_parameter : pl.DataFrame
        ST_Parameter sheet from ST_Manual_Master.xls.

    Returns
    -------
    StressParameters
    """
    params = _parse_st_parameter(st_parameter)

    bu_list = ["RML", "WBG", "IBG", "CBIC", "BB", "CTU", "ORR"]
    params.bu_params = _parse_bu_params(st_parameter, bu_list)

    logger.info("F01 ST: Parsed stress parameters: FI notch shifts=%s, HK YOY=%s",
                params.fi_notch_shift, params.hk_property_yoy)
    return params
