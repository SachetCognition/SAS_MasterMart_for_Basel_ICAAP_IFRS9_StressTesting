"""
On-balance sheet validation with port_rw format.

Translated from Code/01.CAR_BASE/S_01_ONBAL_CHECKING.sas (~120 lines).

Validates on-balance sheet exposures by checking:
  - PORT_CD + APPL_RISK_WEIGHT combinations against valid set
  - Row counts by PORT_CD
  - Amount totals by PORT_CD
  - Identifies unexpected combinations
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

from lib.lookups import PORT_RW_MAP

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(config: Config, fact_rwa: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """
    Perform on-balance sheet sense checking.

    Translated from S_01_ONBAL_CHECKING.sas:
      - Filter for on-balance items (PORT_CD not starting with 'B')
      - Check PORT_CD + APPL_RISK_WEIGHT against port_rw format
      - Produce summary statistics by PORT_CD
      - Flag unexpected combinations

    Parameters
    ----------
    config : Config
    fact_rwa : pl.DataFrame
        Master fact table from l01/l02/l03.

    Returns
    -------
    dict[str, pl.DataFrame]
        Keys: onbal_summary, onbal_exceptions
    """
    results: dict[str, pl.DataFrame] = {}

    if fact_rwa.is_empty():
        logger.warning("S01: Empty fact_rwa input")
        results["onbal_summary"] = pl.DataFrame()
        results["onbal_exceptions"] = pl.DataFrame()
        return results

    # Filter for on-balance items
    if "PORT_CD" not in fact_rwa.columns:
        results["onbal_summary"] = pl.DataFrame()
        results["onbal_exceptions"] = pl.DataFrame()
        return results

    onbal = fact_rwa.filter(
        ~pl.col("PORT_CD").cast(pl.Utf8).str.starts_with("B")
    )

    if onbal.is_empty():
        logger.info("S01: No on-balance records")
        results["onbal_summary"] = pl.DataFrame()
        results["onbal_exceptions"] = pl.DataFrame()
        return results

    # Build PORT_CD + RW combination key
    rw_col = "APPL_RISK_WEIGHT" if "APPL_RISK_WEIGHT" in onbal.columns else None
    if rw_col:
        onbal = onbal.with_columns(
            (pl.col("PORT_CD").cast(pl.Utf8) + "_" + pl.col(rw_col).cast(pl.Int32).cast(pl.Utf8))
            .alias("PORT_RW_KEY")
        )

        # Check against valid combinations
        valid_keys = set(PORT_RW_MAP.keys())
        onbal = onbal.with_columns(
            pl.col("PORT_RW_KEY").is_in(list(valid_keys)).alias("PORT_RW_VALID")
        )

        # Exceptions: invalid combinations
        exceptions = onbal.filter(~pl.col("PORT_RW_VALID"))
        results["onbal_exceptions"] = exceptions
        if len(exceptions) > 0:
            logger.warning("S01: %d rows with invalid PORT_CD+RW combinations", len(exceptions))

    # Summary by PORT_CD
    agg_cols: list[pl.Expr] = [pl.len().alias("ROW_COUNT")]
    amt_cols = ["CUR_BAL_ON_HKE", "ORIG_CRM_AMT_HKE", "APPL_CRM_AMT_HKE", "RISK_WEIGHTED_AMT_HKE"]
    for col in amt_cols:
        if col in onbal.columns:
            agg_cols.append(pl.col(col).sum().alias(f"SUM_{col}"))

    summary = onbal.group_by("PORT_CD").agg(agg_cols).sort("PORT_CD")
    results["onbal_summary"] = summary

    logger.info("S01: On-balance check: %d PORT_CDs, %d total rows, %d exceptions",
                len(summary), len(onbal), len(results.get("onbal_exceptions", pl.DataFrame())))
    return results
