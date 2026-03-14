"""
BIS General Information - CVA processing.

Translated from Code/07.BIS_BASEL_III_CHECK/F_01_BIS_GEN_INFO.sas (~40 lines).
Aggregates CVA exposure (EAD amount + counterparty count).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(config: Config, fact_rwa: pl.DataFrame) -> pl.DataFrame:
    """
    Process CVA exposure for BIS general information.

    Aggregates EAD amounts and counts unique counterparties
    for Credit Valuation Adjustment reporting.
    """
    if fact_rwa.is_empty():
        logger.warning("F01 BIS: Empty fact table")
        return pl.DataFrame()

    df = fact_rwa.clone()

    # Filter for derivative exposures (B14-B18 port codes)
    port_col = "PORT_CD" if "PORT_CD" in df.columns else None
    derv_ports = {"B14", "B15", "B16", "B17", "B18"}

    if port_col:
        df = df.filter(pl.col(port_col).is_in(list(derv_ports)))

    if df.is_empty():
        logger.warning("F01 BIS: No derivative exposures for CVA")
        return pl.DataFrame()

    # Aggregate CVA exposure
    ead_col = "APPL_CRM_AMT_HKE" if "APPL_CRM_AMT_HKE" in df.columns else "ORIG_CRM_AMT_HKE"
    cust_col = "CUST_SEC_ID" if "CUST_SEC_ID" in df.columns else None

    agg_exprs: list[pl.Expr] = []
    if ead_col in df.columns:
        agg_exprs.append(pl.col(ead_col).sum().alias("CVA_EAD_AMT"))
    if cust_col:
        agg_exprs.append(pl.col(cust_col).n_unique().alias("CVA_CPTY_COUNT"))
    agg_exprs.append(pl.len().alias("CVA_EXPOSURE_COUNT"))

    result = df.select(agg_exprs)
    result = result.with_columns(pl.lit(config.rpt_month).alias("RPT_MONTH"))

    cpty_count = result["CVA_CPTY_COUNT"][0] if "CVA_CPTY_COUNT" in result.columns else 0
    logger.info("F01 BIS: CVA processed: %d counterparties", cpty_count)
    return result
