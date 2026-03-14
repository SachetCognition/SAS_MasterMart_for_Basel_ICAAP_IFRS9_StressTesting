"""
Segment the master fact table into 8 Basel asset classes.

Translated from Code/05.ST_SEGMENT/F_02_SEGMENT.sas (~100 lines).

Segments: Sovereign/PSE/MDB, Cash, PastDue, Bank/FI, RML, Derivative,
Non-RML, Exceptions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)

# Segment routing based on ICAAP_PORTCD_DESC prefix (SAS lines 10-50)
_SEGMENT_RULES: list[tuple[str, list[str]]] = [
    ("SOVEREIGN_PSE_MDB", ["01.", "02.", "03."]),
    ("CASH", ["12."]),
    ("PAST_DUE", ["10."]),
    ("BANK_FI", ["04.", "05."]),
    ("RML", ["09."]),
    ("DERIVATIVE", []),  # derivatives handled via PORT_CD B14-B18, not ICAAP_PORTCD_DESC prefix
    ("NON_RML", ["06.", "07.", "08."]),
    ("EXCEPTION", ["11.", "99."]),
]

# PORT_CD-based segment mapping for off-balance
_OFFBAL_SEGMENTS: dict[str, str] = {
    "B14": "DERIVATIVE", "B15": "DERIVATIVE", "B16": "DERIVATIVE",
    "B17": "DERIVATIVE", "B18": "DERIVATIVE",
}


def run(config: Config, fact_rwa: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """
    Segment the master fact table into Basel asset classes.

    Parameters
    ----------
    config : Config
    fact_rwa : pl.DataFrame
        Master fact table from L_01/L_02/L_03.

    Returns
    -------
    dict[str, pl.DataFrame]
        Segmented datasets keyed by segment name.
    """
    results: dict[str, pl.DataFrame] = {}

    if fact_rwa.is_empty():
        logger.warning("F02 ST: Empty fact table")
        for seg_name, _ in _SEGMENT_RULES:
            results[f"st_{seg_name.lower()}"] = pl.DataFrame()
        return results

    # First, assign segment based on ICAAP_PORTCD_DESC
    if "ICAAP_PORTCD_DESC" in fact_rwa.columns:
        segment_expr = pl.lit("EXCEPTION")
        for seg_name, prefixes in reversed(_SEGMENT_RULES):
            for prefix in prefixes:
                segment_expr = (
                    pl.when(pl.col("ICAAP_PORTCD_DESC").cast(pl.Utf8).str.starts_with(prefix))
                    .then(pl.lit(seg_name))
                    .otherwise(segment_expr)
                )
        # Off-balance derivative PORT_CDs (B14-B18) don't appear in PORTCD_MAP
        # and get default "99. ###" — override to DERIVATIVE via PORT_CD check
        if "PORT_CD" in fact_rwa.columns:
            segment_expr = (
                pl.when(pl.col("PORT_CD").cast(pl.Utf8).is_in(list(_OFFBAL_SEGMENTS.keys())))
                .then(pl.lit("DERIVATIVE"))
                .otherwise(segment_expr)
            )
        fact_rwa = fact_rwa.with_columns(segment_expr.alias("ST_SEGMENT"))
    elif "PORT_CD" in fact_rwa.columns:
        # Fallback: use PORT_CD directly
        fact_rwa = fact_rwa.with_columns(
            pl.when(pl.col("PORT_CD").is_in(["Ia", "Ib", "Ic", "Id"]))
            .then(pl.lit("SOVEREIGN_PSE_MDB"))
            .when(pl.col("PORT_CD") == "XII")
            .then(pl.lit("CASH"))
            .when(pl.col("PORT_CD") == "X")
            .then(pl.lit("PAST_DUE"))
            .when(pl.col("PORT_CD").is_in(["IV", "IVa", "V"]))
            .then(pl.lit("BANK_FI"))
            .when(pl.col("PORT_CD") == "IX")
            .then(pl.lit("RML"))
            .when(pl.col("PORT_CD").cast(pl.Utf8).str.starts_with("B"))
            .then(
                pl.col("PORT_CD").cast(pl.Utf8).replace(_OFFBAL_SEGMENTS, default="NON_RML")
            )
            .when(pl.col("PORT_CD").is_in(["VI", "VIIIa", "VIIIb"]))
            .then(pl.lit("NON_RML"))
            .otherwise(pl.lit("EXCEPTION"))
            .alias("ST_SEGMENT")
        )
    else:
        fact_rwa = fact_rwa.with_columns(pl.lit("EXCEPTION").alias("ST_SEGMENT"))

    # Split into segment DataFrames
    for seg_name, _ in _SEGMENT_RULES:
        seg_df = fact_rwa.filter(pl.col("ST_SEGMENT") == seg_name)
        results[f"st_{seg_name.lower()}"] = seg_df
        logger.info("F02 ST: Segment %s: %d rows", seg_name, len(seg_df))

    # Also return the full segmented dataset
    results["st_all_segmented"] = fact_rwa

    return results
