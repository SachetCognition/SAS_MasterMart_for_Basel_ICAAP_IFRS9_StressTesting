"""
Load RP stress parameters.

Translated from Code/90.RP_SEGMENT/F_04_PARAMETER.sas (~40 lines).
Loads 8 segments x 4 severities (base, mild, medium, severe).
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
class RPSegmentParams:
    """Per-segment stress parameters for RP."""
    segment: str = ""
    npl_target: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    lgd: list[float] = field(default_factory=lambda: [0.45, 0.45, 0.45, 0.45])
    npl_cov: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    loan_growth: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])


@dataclass
class RPParameters:
    """RP stress parameters across all segments."""
    fi_notch_shift: list[int] = field(default_factory=lambda: [0, 1, 3, 5])
    hk_property_yoy: list[float] = field(default_factory=lambda: [0.0, -0.05, -0.15, -0.30])
    hk_property_haircut: list[float] = field(default_factory=lambda: [0.0, 0.05, 0.10, 0.20])
    cn_property_yoy: list[float] = field(default_factory=lambda: [0.0, -0.05, -0.15, -0.30])
    cn_property_haircut: list[float] = field(default_factory=lambda: [0.0, 0.05, 0.10, 0.20])
    deriv_ce_multiplier: list[float] = field(default_factory=lambda: [1.0, 1.1, 1.3, 1.5])
    segment_params: dict[str, RPSegmentParams] = field(default_factory=dict)


def run(config: Config, rp_parameter: pl.DataFrame) -> RPParameters:
    """Parse RP parameters from the RP_Parameter Excel sheet."""
    params = RPParameters()

    if rp_parameter.is_empty():
        logger.warning("F04 RP: Empty RP parameter input, using defaults")
        return params

    cols = rp_parameter.columns
    if len(cols) < 5:
        logger.warning("F04 RP: Insufficient columns in RP parameter sheet")
        return params

    param_col = cols[0]
    scenario_cols = cols[1:5]

    current_segment: str | None = None

    for row in rp_parameter.iter_rows(named=True):
        param_name = str(row.get(param_col, "")).strip()
        if not param_name:
            continue

        values = [float(row.get(sc, 0) or 0) for sc in scenario_cols]
        upper = param_name.upper()

        # Global parameters
        if "FI" in upper and "NOTCH" in upper:
            params.fi_notch_shift = [int(v) for v in values]
        elif "HK" in upper and "YOY" in upper:
            params.hk_property_yoy = values
        elif "HK" in upper and "HAIRCUT" in upper:
            params.hk_property_haircut = values
        elif "CN" in upper and "YOY" in upper:
            params.cn_property_yoy = values
        elif "CN" in upper and "HAIRCUT" in upper:
            params.cn_property_haircut = values
        elif "DERIV" in upper and "MULTI" in upper:
            params.deriv_ce_multiplier = values
        # Segment-specific parameters
        elif "SEGMENT" in upper or "BU" in upper:
            current_segment = param_name
            if current_segment not in params.segment_params:
                params.segment_params[current_segment] = RPSegmentParams(segment=current_segment)
        elif current_segment:
            seg = params.segment_params[current_segment]
            if "NPL" in upper and "TARGET" in upper:
                seg.npl_target = values
            elif "LGD" in upper:
                seg.lgd = values
            elif "NPL" in upper and "COV" in upper:
                seg.npl_cov = values
            elif "LOAN" in upper and "GROWTH" in upper:
                seg.loan_growth = values

    logger.info("F04 RP: Parsed parameters for %d segments", len(params.segment_params))
    return params
