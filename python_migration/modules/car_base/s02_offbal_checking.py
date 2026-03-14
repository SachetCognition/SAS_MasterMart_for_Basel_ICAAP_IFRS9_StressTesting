"""
Off-balance sheet validation.

Translated from Code/01.CAR_BASE/S_02_OFFBAL_CHECKING.sas (~80 lines).

Validates off-balance sheet exposures by checking:
  - PORT_CD starts with 'B' (off-balance indicator)
  - CCF values are within expected ranges
  - Amount totals by PORT_CD
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(config: Config, fact_rwa: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """
    Perform off-balance sheet sense checking.

    Translated from S_02_OFFBAL_CHECKING.sas:
      - Filter for off-balance items (PORT_CD starting with 'B')
      - Validate CCF values
      - Produce summary statistics by PORT_CD
      - Flag unusual CCF or amount patterns

    Parameters
    ----------
    config : Config
    fact_rwa : pl.DataFrame
        Master fact table.

    Returns
    -------
    dict[str, pl.DataFrame]
        Keys: offbal_summary, offbal_exceptions
    """
    results: dict[str, pl.DataFrame] = {}

    if fact_rwa.is_empty() or "PORT_CD" not in fact_rwa.columns:
        results["offbal_summary"] = pl.DataFrame()
        results["offbal_exceptions"] = pl.DataFrame()
        return results

    # Filter for off-balance items
    offbal = fact_rwa.filter(
        pl.col("PORT_CD").cast(pl.Utf8).str.starts_with("B")
    )

    if offbal.is_empty():
        logger.info("S02: No off-balance records")
        results["offbal_summary"] = pl.DataFrame()
        results["offbal_exceptions"] = pl.DataFrame()
        return results

    # Check CCF values
    exceptions = pl.DataFrame()
    if "CCF" in offbal.columns:
        # CCF should be between 0 and 100
        ccf_exceptions = offbal.filter(
            (pl.col("CCF") < 0) | (pl.col("CCF") > 100)
        )
        if len(ccf_exceptions) > 0:
            logger.warning("S02: %d rows with CCF outside 0-100 range", len(ccf_exceptions))
        exceptions = ccf_exceptions

    results["offbal_exceptions"] = exceptions

    # Summary by PORT_CD
    agg_cols: list[pl.Expr] = [pl.len().alias("ROW_COUNT")]
    amt_cols = [
        "CUR_BAL_OFF_HKE", "CUR_EXP_AMT_HKE", "POTENT_EXP_AMT_HKE",
        "ORIG_CRM_AMT_HKE", "APPL_CRM_AMT_HKE", "RISK_WEIGHTED_AMT_HKE",
    ]
    for col in amt_cols:
        if col in offbal.columns:
            agg_cols.append(pl.col(col).sum().alias(f"SUM_{col}"))

    summary = offbal.group_by("PORT_CD").agg(agg_cols).sort("PORT_CD")
    results["offbal_summary"] = summary

    logger.info("S02: Off-balance check: %d PORT_CDs, %d total rows, %d exceptions",
                len(summary), len(offbal), len(exceptions))
    return results
