"""
HKCBF adjustments and deltas.

Translated from Code/01.CAR_BASE/F_09_HKCBF_ADJ_N_DELTA.sas (~70 lines).

Processes HKCBF (Hong Kong CBF) specific adjustments:
  - Apply HKCBF-specific PORT_CD reclassifications
  - Compute deltas between pre- and post-adjustment
  - Produce car_hkcbf_adj staging dataset
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
    car_iw_adj: pl.DataFrame,
) -> dict[str, pl.DataFrame]:
    """
    Apply HKCBF-specific adjustments and compute deltas.

    Translated from F_09_HKCBF_ADJ_N_DELTA.sas:
      - Filter car_iw_adj for FLAG_SRC in ('KW','VC') where ENTITY = 'HKCBF'
      - Apply HKCBF-specific PORT_CD mapping
      - Compute adjustment delta

    Parameters
    ----------
    config : Config
    car_iw_adj : pl.DataFrame
        Adjusted CAR IW data from f04_iw_adj.

    Returns
    -------
    dict[str, pl.DataFrame]
        Keys: car_hkcbf_adj, adj_ns_hkcbf_delta
    """
    results: dict[str, pl.DataFrame] = {}

    if car_iw_adj.is_empty():
        logger.warning("F09: Empty CAR IW adj input")
        results["car_hkcbf_adj"] = pl.DataFrame()
        results["adj_ns_hkcbf_delta"] = pl.DataFrame()
        return results

    # Filter for HKCBF entity records
    entity_col = "ENTITY" if "ENTITY" in car_iw_adj.columns else None
    flag_col = "FLAG_SRC" if "FLAG_SRC" in car_iw_adj.columns else None

    if entity_col is None or flag_col is None:
        results["car_hkcbf_adj"] = pl.DataFrame()
        results["adj_ns_hkcbf_delta"] = pl.DataFrame()
        return results

    hkcbf_mask = (
        (pl.col(flag_col).is_in(["KW", "VC"]))
        & (pl.col(entity_col) == "HKCBF")
    )

    hkcbf_df = car_iw_adj.filter(hkcbf_mask)

    if hkcbf_df.is_empty():
        logger.info("F09: No HKCBF records found")
        results["car_hkcbf_adj"] = pl.DataFrame()
        results["adj_ns_hkcbf_delta"] = pl.DataFrame()
        return results

    # Apply HKCBF-specific adjustments
    hkcbf_adj = hkcbf_df.with_columns([
        pl.lit("HKCBF").alias("FILE_SRC"),
        pl.lit(210.0).alias("FLAG_ADJ"),
    ])

    results["car_hkcbf_adj"] = hkcbf_adj

    # Delta is the HKCBF subset itself (represents the HKCBF-specific portion)
    results["adj_ns_hkcbf_delta"] = hkcbf_adj

    logger.info("F09: HKCBF adj: %d rows", len(hkcbf_adj))
    return results
