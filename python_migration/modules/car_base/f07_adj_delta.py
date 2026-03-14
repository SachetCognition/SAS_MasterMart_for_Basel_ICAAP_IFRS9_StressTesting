"""
Delta adjustments using error adjustment system.

Translated from Code/01.CAR_BASE/F_07_ADJ_DELTA.sas (~80 lines).

Computes delta (difference) between IW system values and adjusted values,
producing adjustment records for on-balance, off-balance, and derivative items.
Groups: Adj 3 (NY/LA), Adj 5 (CC), Adj 6 (MPA), Other adjustments.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)

_AMT_COLS = [
    "CUR_BAL_ON_HKE", "CUR_BAL_OFF_HKE", "CUR_EXP_AMT_HKE",
    "POTENT_EXP_AMT_HKE", "ORIG_CRM_AMT_HKE", "APPL_CRM_AMT_HKE",
    "RISK_WEIGHTED_AMT_HKE", "PROVISION_AMT_HKE",
]

# Adjustment groups and their FLAG_ADJ codes
_ADJ_GROUPS = {
    "adj_delta_3": {"flag_adj": 3.0, "desc": "NY/LA reclass Ia→IV"},
    "adj_delta_5": {"flag_adj": 5.0, "desc": "Credit Card VI→VIIIa"},
    "adj_delta_6": {"flag_adj": 6.0, "desc": "MPA IX 50%→35%"},
    "adj_delta_other": {"flag_adj": 9.0, "desc": "Other adjustments"},
}


def _compute_delta(
    before: pl.DataFrame,
    after: pl.DataFrame,
    flag_adj: float,
    group_cols: list[str],
) -> pl.DataFrame:
    """
    Compute the delta (after - before) for amount columns.

    Aggregates both before and after by group_cols, then computes differences.
    """
    valid_group = [c for c in group_cols if c in before.columns and c in after.columns]
    if not valid_group:
        return pl.DataFrame()

    valid_amts = [c for c in _AMT_COLS if c in before.columns and c in after.columns]
    if not valid_amts:
        return pl.DataFrame()

    # Aggregate before
    before_agg = before.group_by(valid_group).agg([
        pl.col(c).sum().alias(f"{c}_before") for c in valid_amts
    ])

    # Aggregate after
    after_agg = after.group_by(valid_group).agg([
        pl.col(c).sum().alias(f"{c}_after") for c in valid_amts
    ])

    # Join and compute deltas
    merged = before_agg.join(after_agg, on=valid_group, how="outer", suffix="_r")

    delta_exprs: list[pl.Expr] = []
    for c in valid_amts:
        delta_exprs.append(
            (pl.col(f"{c}_after").fill_null(0) - pl.col(f"{c}_before").fill_null(0)).alias(c)
        )

    result = merged.select(valid_group + delta_exprs)

    # Filter: keep only rows where at least one delta is non-zero
    any_nonzero = pl.lit(False)
    for c in valid_amts:
        any_nonzero = any_nonzero | (pl.col(c).abs() > 0.01)
    result = result.filter(any_nonzero)

    # Add metadata
    result = result.with_columns([
        pl.lit(flag_adj).alias("FLAG_ADJ"),
        pl.lit("DELTA").alias("FILE_SRC"),
    ])

    return result


def run(
    config: Config,
    car_iw_before: pl.DataFrame,
    car_iw_after: pl.DataFrame,
) -> dict[str, pl.DataFrame]:
    """
    Compute delta adjustments between before and after IW adjustment.

    Parameters
    ----------
    config : Config
    car_iw_before : pl.DataFrame
        CAR IW data before adjustments.
    car_iw_after : pl.DataFrame
        CAR IW data after adjustments (from f04_iw_adj).

    Returns
    -------
    dict[str, pl.DataFrame]
        Delta datasets: adj_delta_3, adj_delta_5, adj_delta_6, adj_delta_other
    """
    results: dict[str, pl.DataFrame] = {}
    group_cols = ["PORT_CD", "FLAG_SRC", "ENTITY"]

    for name, info in _ADJ_GROUPS.items():
        delta = _compute_delta(
            car_iw_before, car_iw_after,
            flag_adj=info["flag_adj"],
            group_cols=group_cols,
        )
        results[name] = delta
        logger.info("F07: %s (%s): %d delta rows", name, info["desc"], len(delta))

    return results
