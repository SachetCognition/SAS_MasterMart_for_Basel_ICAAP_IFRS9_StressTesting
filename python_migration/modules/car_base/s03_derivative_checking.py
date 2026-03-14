"""
Derivative validation.

Translated from Code/01.CAR_BASE/S_03_DERIVATIVE_CHECKING.sas (~60 lines).

Validates derivative exposures by checking:
  - PORT_CD in B-prefix derivative codes
  - Current and potential exposure amounts
  - CRM amounts consistency
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)

# Valid derivative PORT_CDs
_DERV_PORT_CDS = {"B14", "B15", "B16", "B17", "B18"}


def run(config: Config, fact_rwa: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """
    Perform derivative sense checking.

    Parameters
    ----------
    config : Config
    fact_rwa : pl.DataFrame
        Master fact table.

    Returns
    -------
    dict[str, pl.DataFrame]
        Keys: derv_summary, derv_exceptions
    """
    results: dict[str, pl.DataFrame] = {}

    if fact_rwa.is_empty() or "PORT_CD" not in fact_rwa.columns:
        results["derv_summary"] = pl.DataFrame()
        results["derv_exceptions"] = pl.DataFrame()
        return results

    # Filter for derivative items
    derv = fact_rwa.filter(pl.col("PORT_CD").cast(pl.Utf8).is_in(list(_DERV_PORT_CDS)))

    if derv.is_empty():
        logger.info("S03: No derivative records")
        results["derv_summary"] = pl.DataFrame()
        results["derv_exceptions"] = pl.DataFrame()
        return results

    # Check: CUR_EXP_AMT_HKE + POTENT_EXP_AMT_HKE should ≈ ORIG_CRM_AMT_HKE
    exceptions = pl.DataFrame()
    exp_cols = ["CUR_EXP_AMT_HKE", "POTENT_EXP_AMT_HKE", "ORIG_CRM_AMT_HKE"]
    if all(c in derv.columns for c in exp_cols):
        derv_check = derv.with_columns(
            (
                pl.col("CUR_EXP_AMT_HKE").fill_null(0)
                + pl.col("POTENT_EXP_AMT_HKE").fill_null(0)
                - pl.col("ORIG_CRM_AMT_HKE").fill_null(0)
            ).abs().alias("_crm_diff")
        )
        # Flag rows where difference > 1 (tolerance for rounding)
        exceptions = derv_check.filter(pl.col("_crm_diff") > 1.0)
        if len(exceptions) > 0:
            logger.warning("S03: %d derivative rows with CRM mismatch", len(exceptions))
        exceptions = exceptions.drop("_crm_diff")

    results["derv_exceptions"] = exceptions

    # Summary by PORT_CD
    agg_cols: list[pl.Expr] = [pl.len().alias("ROW_COUNT")]
    amt_cols = [
        "CUR_BAL_OFF_HKE", "CUR_EXP_AMT_HKE", "POTENT_EXP_AMT_HKE",
        "ORIG_CRM_AMT_HKE", "APPL_CRM_AMT_HKE", "RISK_WEIGHTED_AMT_HKE",
    ]
    for col in amt_cols:
        if col in derv.columns:
            agg_cols.append(pl.col(col).sum().alias(f"SUM_{col}"))

    summary = derv.group_by("PORT_CD").agg(agg_cols).sort("PORT_CD")
    results["derv_summary"] = summary

    logger.info("S03: Derivative check: %d PORT_CDs, %d total rows, %d exceptions",
                len(summary), len(derv), len(exceptions))
    return results
