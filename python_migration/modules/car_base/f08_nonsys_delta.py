"""
Non-system delta calculations.

Translated from Code/01.CAR_BASE/F_08_NONSYS_DELTA.sas (~90 lines).

Processes non-system (manual) adjustment data into delta records for:
  - Combined non-system adjustments (adj_ns_combined_delta)
  - Subsidiary-level adjustments (adj_ns_subsidiaries_delta)
  - Consolidated CRM adjustments (adj_ns_consolid_crm_delta)
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


def _process_nonsystem(
    df: pl.DataFrame,
    flag_adj: float,
    file_src: str,
) -> pl.DataFrame:
    """
    Convert non-system Excel data into delta adjustment records.

    The non-system Excel contains portfolio-level adjustments with
    amount columns that represent the delta (adjustment amount).
    """
    if df.is_empty():
        return pl.DataFrame()

    result = df.clone()

    # Add metadata columns
    result = result.with_columns([
        pl.lit(flag_adj).alias("FLAG_ADJ"),
        pl.lit(file_src).alias("FILE_SRC"),
    ])

    # Ensure amount columns are numeric
    for col in _AMT_COLS:
        if col in result.columns:
            result = result.with_columns(
                pl.col(col).cast(pl.Float64, strict=False).fill_null(0.0).alias(col)
            )

    # Map ITEM column to standard column names if present
    if "ITEM" in result.columns and "PORT_CD" in result.columns:
        # Keep only rows with valid PORT_CD
        result = result.filter(
            pl.col("PORT_CD").is_not_null()
            & (pl.col("PORT_CD").cast(pl.Utf8).str.strip_chars() != "")
        )

    return result


def run(
    config: Config,
    nonsystem: pl.DataFrame,
    ns_hkcbf: pl.DataFrame,
) -> dict[str, pl.DataFrame]:
    """
    Process non-system adjustment files into delta records.

    Parameters
    ----------
    config : Config
    nonsystem : pl.DataFrame
        OGL outstanding for Basel (main non-system adjustments).
    ns_hkcbf : pl.DataFrame
        HKCBF non-system adjustments.

    Returns
    -------
    dict[str, pl.DataFrame]
        Keys: adj_ns_combined_delta, adj_ns_subsidiaries_delta, adj_ns_consolid_crm_delta
    """
    results: dict[str, pl.DataFrame] = {}

    # 1. Combined non-system delta (FLAG_ADJ = 200)
    combined = _process_nonsystem(nonsystem, flag_adj=200.0, file_src="NONSYS-COMBINED")

    # Split by NATUREOFITEM if present
    if not combined.is_empty() and "NATUREOFITEM" in combined.columns:
        # Combined = rows where NATUREOFITEM contains 'Combined' or 'Overseas'
        combined_mask = (
            pl.col("NATUREOFITEM").cast(pl.Utf8).str.to_uppercase().str.contains("COMBINED")
            | pl.col("NATUREOFITEM").cast(pl.Utf8).str.to_uppercase().str.contains("OVERSEA")
        )
        results["adj_ns_combined_delta"] = combined.filter(combined_mask)

        # Subsidiaries = rows where NATUREOFITEM contains 'Subsidiary' or 'CBIC'
        sub_mask = (
            pl.col("NATUREOFITEM").cast(pl.Utf8).str.to_uppercase().str.contains("SUBSIDIAR")
            | pl.col("NATUREOFITEM").cast(pl.Utf8).str.to_uppercase().str.contains("CBIC")
        )
        results["adj_ns_subsidiaries_delta"] = combined.filter(sub_mask)

        # Consolidated CRM = rows where NATUREOFITEM contains 'Consolid' or 'CRM'
        consolid_mask = (
            pl.col("NATUREOFITEM").cast(pl.Utf8).str.to_uppercase().str.contains("CONSOLID")
            | pl.col("NATUREOFITEM").cast(pl.Utf8).str.to_uppercase().str.contains("CRM")
        )
        results["adj_ns_consolid_crm_delta"] = combined.filter(consolid_mask)
    else:
        results["adj_ns_combined_delta"] = combined
        results["adj_ns_subsidiaries_delta"] = pl.DataFrame()
        results["adj_ns_consolid_crm_delta"] = pl.DataFrame()

    # 2. HKCBF non-system delta (FLAG_ADJ = 201)
    hkcbf_delta = _process_nonsystem(ns_hkcbf, flag_adj=201.0, file_src="NONSYS-HKCBF")
    results["adj_ns_hkcbf_delta"] = hkcbf_delta

    for name, df in results.items():
        logger.info("F08: %s: %d rows", name, len(df))

    return results
