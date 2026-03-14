"""
REF list processing from business units.

Translated from Code/01.CAR_BASE/F_12_REF_LIST_FROM_BU.sas (~50 lines).

Processes the REF (Real Estate Financing) facility list:
  - Join REF list with BU (business unit) mapping
  - Create FLAG_REF indicator for REF facilities
  - Produce ref_list staging dataset used in L_01 for REF identification
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(
    config: Config,
    ref_list: pl.DataFrame,
    car_iw_adj: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """
    Process REF list and create FLAG_REF mapping.

    Translated from F_12_REF_LIST_FROM_BU.sas:
      - Read REF_List from e06_xls_ref_list
      - Extract unique FAC_REF values
      - Create a lookup set for REF facility identification
      - Optionally enrich with business unit information

    Parameters
    ----------
    config : Config
    ref_list : pl.DataFrame
        REF facility list from e06_xls_ref_list.
    car_iw_adj : pl.DataFrame | None
        Adjusted CAR data (optional, for enrichment).

    Returns
    -------
    pl.DataFrame
        REF list with FLAG_REF = 1 for all entries.
    """
    if ref_list.is_empty():
        logger.warning("F12: Empty REF list input")
        return pl.DataFrame()

    result = ref_list.clone()

    # Add FLAG_REF indicator
    result = result.with_columns(pl.lit(1).alias("FLAG_REF"))

    # Extract unique FAC_REF values for lookup
    if "FAC_REF" in result.columns:
        result = result.unique(subset=["FAC_REF"])

        # If car_iw_adj provided, enrich with BU info
        if car_iw_adj is not None and not car_iw_adj.is_empty():
            bu_cols = ["FAC_REF", "ICAAP_BUS_UNIT", "ICAAP_TEAM_CD"]
            available_bu = [c for c in bu_cols if c in car_iw_adj.columns]

            if "FAC_REF" in available_bu and len(available_bu) > 1:
                bu_info = car_iw_adj.select(available_bu).unique(subset=["FAC_REF"])
                result = result.join(bu_info, on="FAC_REF", how="left")

    logger.info("F12: REF list: %d unique facilities", len(result))
    return result
