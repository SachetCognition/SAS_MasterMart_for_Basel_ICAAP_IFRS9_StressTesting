"""
Singapore Excel data transformation.

Translated from Code/01.CAR_BASE/F_05_SGP_XLS.sas (~120 lines).

Processes SGP Basel return data (IMEX, MM, Loan, FX) into staging format:
  - Standardize column names
  - Apply PORT_CD mapping from SGP type
  - Calculate HKE amounts from CCY amounts
  - Flag on/off balance items
  - Produce adj_sgp_sec_fix_loan, adj_sgp_mm, adj_sgp_imex datasets
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)

# SGP type to PORT_CD mapping (SAS lines 8-25)
_SGP_PORT_MAPPING: dict[str, dict[str, str]] = {
    "IMEX": {
        "default": "IV",
        "short_term": "IVa",
    },
    "MM": {
        "default": "IV",
    },
    "Loan": {
        "default": "IV",
    },
    "FX": {
        "default": "B17",
    },
}


def _standardize_sgp(
    df: pl.DataFrame,
    sgp_type: str,
    rpt_month: str,
) -> pl.DataFrame:
    """
    Standardize SGP data into CAR-compatible format.

    Maps SGP columns to standard CAR column names and applies
    type-specific business rules.
    """
    if df.is_empty():
        return pl.DataFrame()

    result = df.clone()

    # Add standard identifiers
    result = result.with_columns([
        pl.lit(f"SGP-{sgp_type}").alias("FILE_SRC"),
        pl.lit("KW").alias("FLAG_SRC"),
        pl.lit("SGBR").alias("ENTITY"),
        pl.lit(rpt_month).alias("RPT_MONTH"),
    ])

    # Map PORT_CD based on type
    port_info = _SGP_PORT_MAPPING.get(sgp_type, {"default": "IV"})
    default_port = port_info["default"]

    if sgp_type == "IMEX" and "SHORT_TERM_CLAIM_IND" in result.columns:
        result = result.with_columns(
            pl.when(pl.col("SHORT_TERM_CLAIM_IND") == "Y")
            .then(pl.lit(port_info.get("short_term", default_port)))
            .otherwise(pl.lit(default_port))
            .alias("PORT_CD")
        )
    else:
        result = result.with_columns(pl.lit(default_port).alias("PORT_CD"))

    # Standardize amount columns
    amt_mappings = {
        "AMT_HKE": "CUR_BAL_ON_HKE",
        "AMOUNT_HKE": "CUR_BAL_ON_HKE",
        "RISKWEIGHT": "APPL_RISK_WEIGHT",
        "RISK_WEIGHT": "APPL_RISK_WEIGHT",
        "CCF": "CCF",
        "EXPOSURE_HKE": "ORIG_CRM_AMT_HKE",
        "EXPOSURE": "ORIG_CRM_AMT_HKE",
    }

    for src_col, tgt_col in amt_mappings.items():
        if src_col in result.columns and tgt_col not in result.columns:
            result = result.rename({src_col: tgt_col})

    # Calculate RISK_WEIGHTED_AMT_HKE if not present
    if "RISK_WEIGHTED_AMT_HKE" not in result.columns:
        crm_col = "APPL_CRM_AMT_HKE" if "APPL_CRM_AMT_HKE" in result.columns else "ORIG_CRM_AMT_HKE"
        rw_col = "APPL_RISK_WEIGHT"
        if crm_col in result.columns and rw_col in result.columns:
            result = result.with_columns(
                (pl.col(crm_col) * pl.col(rw_col) / 100.0).alias("RISK_WEIGHTED_AMT_HKE")
            )

    # Ensure APPL_CRM_AMT_HKE exists
    if "APPL_CRM_AMT_HKE" not in result.columns and "ORIG_CRM_AMT_HKE" in result.columns:
        result = result.with_columns(
            pl.col("ORIG_CRM_AMT_HKE").alias("APPL_CRM_AMT_HKE")
        )

    # Flag adjustment number based on type
    flag_adj_map = {
        "IMEX": 100.0,
        "MM": 101.0,
        "Loan": 102.0,
        "FX": 103.0,
    }
    result = result.with_columns(
        pl.lit(flag_adj_map.get(sgp_type, 100.0)).alias("FLAG_ADJ")
    )

    return result


def run(
    config: Config,
    sgp_datasets: dict[str, pl.DataFrame],
) -> dict[str, pl.DataFrame]:
    """
    Process all SGP Excel datasets into staging format.

    Parameters
    ----------
    config : Config
    sgp_datasets : dict[str, pl.DataFrame]
        Keys: ``sgp_imex``, ``sgp_mm``, ``sgp_loan``, ``sgp_fx``

    Returns
    -------
    dict[str, pl.DataFrame]
        Staging datasets: adj_sgp_imex, adj_sgp_mm, adj_sgp_sec_fix_loan, adj_sgp_fx
    """
    results: dict[str, pl.DataFrame] = {}
    rpt = config.rpt_month

    type_output_map = {
        "sgp_imex": ("IMEX", "adj_sgp_imex"),
        "sgp_mm": ("MM", "adj_sgp_mm"),
        "sgp_loan": ("Loan", "adj_sgp_sec_fix_loan"),
        "sgp_fx": ("FX", "adj_sgp_fx"),
    }

    for input_key, (sgp_type, output_key) in type_output_map.items():
        raw_df = sgp_datasets.get(input_key, pl.DataFrame())
        if raw_df.is_empty():
            logger.warning("F05: No data for %s", input_key)
            results[output_key] = pl.DataFrame()
            continue

        processed = _standardize_sgp(raw_df, sgp_type, rpt)
        results[output_key] = processed
        logger.info("F05: %s -> %s: %d rows", input_key, output_key, len(processed))

    return results
