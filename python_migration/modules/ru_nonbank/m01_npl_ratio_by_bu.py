"""
Calculate NPL ratios by business unit.

Translated from Code/02.RU_NONBANK_EXP/M_01_NPL_RATIO_BY_BU.sas.

Generates macro variables (npl_bu_RML, npl_bu_WBG, etc.) used downstream
by stress testing. In Python, returns a dict of BU → NPL ratio.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)

# Business units for NPL ratio calculation
_BU_LIST = ["RML", "WBG", "IBG", "CBIC", "BB", "CTU", "ORR", "OFD"]


def run(config: Config, npl_fact: pl.DataFrame) -> dict[str, float]:
    """
    Calculate NPL ratio by business unit.

    NPL ratio = sum(NPL_AMT) / sum(TOTAL_EXPOSURE) for each BU.

    Parameters
    ----------
    config : Config
    npl_fact : pl.DataFrame
        NPL fact table from l01.

    Returns
    -------
    dict[str, float]
        Business unit → NPL ratio mapping (e.g., {"RML": 0.012, "WBG": 0.005}).
    """
    npl_ratios: dict[str, float] = {}

    if npl_fact.is_empty():
        logger.warning("M01 RU: Empty NPL fact table")
        return {bu: 0.0 for bu in _BU_LIST}

    # Determine BU column
    bu_col = None
    for candidate in ["ICAAP_BUS_UNIT", "BUS_UNIT", "IND_BUS_UNIT"]:
        if candidate in npl_fact.columns:
            bu_col = candidate
            break

    if bu_col is None:
        logger.warning("M01 RU: No business unit column found")
        return {bu: 0.0 for bu in _BU_LIST}

    # Determine amount columns
    npl_amt_col = "NPL_AMT" if "NPL_AMT" in npl_fact.columns else None
    exp_col = None
    for candidate in ["APPL_CRM_AMT_HKE", "ORIG_CRM_AMT_HKE", "CUR_BAL_ON_HKE", "TOTAL_EXPOSURE"]:
        if candidate in npl_fact.columns:
            exp_col = candidate
            break

    if exp_col is None:
        logger.warning("M01 RU: No exposure amount column found")
        return {bu: 0.0 for bu in _BU_LIST}

    # Calculate NPL ratio per BU
    for bu in _BU_LIST:
        bu_data = npl_fact.filter(pl.col(bu_col).cast(pl.Utf8).str.to_uppercase() == bu)

        if bu_data.is_empty():
            npl_ratios[bu] = 0.0
            continue

        total_exp = bu_data[exp_col].sum()
        if total_exp is None or total_exp == 0:
            npl_ratios[bu] = 0.0
            continue

        if npl_amt_col:
            npl_amt = bu_data[npl_amt_col].sum()
            npl_ratios[bu] = float(npl_amt or 0) / float(total_exp)
        else:
            # Use FLAG_NPL to identify NPL records
            npl_exp = bu_data.filter(pl.col("FLAG_NPL") == 1)[exp_col].sum()
            npl_ratios[bu] = float(npl_exp or 0) / float(total_exp)

    for bu, ratio in npl_ratios.items():
        logger.info("M01 RU: NPL ratio %s = %.6f", bu, ratio)

    return npl_ratios
