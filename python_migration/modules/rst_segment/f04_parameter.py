"""
Load RST stress parameters.

Translated from Code/04.RST_SEGMENT/F_04_PARAMETER.sas.
Reuses the StressParameters dataclass from st_segment but loads RST-specific params.
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
class RSTParameters:
    """RST-specific stress parameters with base/mild/medium/severe scenarios."""
    fi_notch_shift: list[int] = field(default_factory=lambda: [0, 1, 3, 5])
    hk_property_yoy: list[float] = field(default_factory=lambda: [0.0, -0.05, -0.15, -0.30])
    hk_property_haircut: list[float] = field(default_factory=lambda: [0.0, 0.05, 0.10, 0.20])
    cn_property_yoy: list[float] = field(default_factory=lambda: [0.0, -0.05, -0.15, -0.30])
    cn_property_haircut: list[float] = field(default_factory=lambda: [0.0, 0.05, 0.10, 0.20])
    nbmce_npl_target: list[float] = field(default_factory=lambda: [0.0, 0.01, 0.03, 0.05])
    nbmce_lgd: list[float] = field(default_factory=lambda: [0.45, 0.45, 0.45, 0.45])

def run(config: Config, rst_parameter: pl.DataFrame) -> RSTParameters:
    """Parse RST parameters from the RST_Parameter Excel sheet."""
    params = RSTParameters()
    if rst_parameter.is_empty():
        logger.warning("F04 RST: Empty RST parameter input")
        return params
    cols = rst_parameter.columns
    if len(cols) < 5:
        return params
    param_col = cols[0]
    scenario_cols = cols[1:5]
    for row in rst_parameter.iter_rows(named=True):
        param_name = str(row.get(param_col, "")).strip().upper()
        values = [float(row.get(sc, 0) or 0) for sc in scenario_cols]
        if "FI" in param_name and "NOTCH" in param_name:
            params.fi_notch_shift = [int(v) for v in values]
        elif "HK" in param_name and "YOY" in param_name:
            params.hk_property_yoy = values
        elif "HK" in param_name and "HAIRCUT" in param_name:
            params.hk_property_haircut = values
        elif "NBMCE" in param_name and "NPL" in param_name:
            params.nbmce_npl_target = values
        elif "NBMCE" in param_name and "LGD" in param_name:
            params.nbmce_lgd = values
    logger.info("F04 RST: Parsed RST parameters")
    return params
