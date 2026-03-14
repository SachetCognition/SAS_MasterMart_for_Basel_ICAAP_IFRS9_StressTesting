"""
BIS CSRBB Base data preparation.

Translated from Code/07.BIS_BASEL_III_CHECK/F_02_BIS_CSRBB_BASE.sas (~240 lines).
Categorizes ON/OFF/DERV, maps BIS_CQ, BIS_SECTOR_TYP, BIS_RES_MAT_YEAR.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)

_ON_BAL_PORTS = {"Ia", "Ib", "Ic", "Id", "Ie", "II", "IIIa", "IIIb", "IV", "IVa", "V", "VI",
                 "VIIa", "VIIb", "VIIc", "VIIIa", "VIIIb", "VIIIc", "IX", "X", "XIa", "XIb", "XIc"}
_OFF_BAL_PORTS = {"B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B9a", "B9b", "B9c", "B9d"}
_DERV_PORTS = {"B14", "B15", "B16", "B17", "B18"}

_SECTOR_MAP_PORT = {
    "Ia": 1, "Ib": 1, "Ic": 1, "Id": 2, "Ie": 3,
    "II": 1, "IIIa": 1, "IIIb": 1,
    "IV": 4, "IVa": 4, "V": 5,
}


def _classify_exposure_type(port_cd: str) -> str:
    """Classify exposure as ON, OFF, or DERV."""
    if port_cd in _ON_BAL_PORTS:
        return "ON"
    if port_cd in _OFF_BAL_PORTS:
        return "OFF"
    if port_cd in _DERV_PORTS:
        return "DERV"
    return "OTHER"


def _map_bis_cq(ecai_rating: str | None) -> str:
    """Map ECAI rating to BIS Credit Quality (IG/HY/NR)."""
    if not ecai_rating or ecai_rating.strip() == "":
        return "NR"
    rating = ecai_rating.strip().upper()
    ig_ratings = {"AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-"}
    if rating in ig_ratings:
        return "IG"
    return "HY"


def run(config: Config, fact_rwa: pl.DataFrame) -> pl.DataFrame:
    """
    Prepare CSRBB base dataset with BIS classifications.

    Adds: BIS_EXP_TYPE, BIS_CQ, BIS_SECTOR_TYP, BIS_RES_MAT_YEAR
    """
    if fact_rwa.is_empty():
        logger.warning("F02 BIS: Empty fact table")
        return pl.DataFrame()

    df = fact_rwa.clone()
    port_col = "PORT_CD" if "PORT_CD" in df.columns else None

    # BIS_EXP_TYPE classification
    if port_col:
        df = df.with_columns(
            pl.when(pl.col(port_col).is_in(list(_ON_BAL_PORTS))).then(pl.lit("ON"))
            .when(pl.col(port_col).is_in(list(_OFF_BAL_PORTS))).then(pl.lit("OFF"))
            .when(pl.col(port_col).is_in(list(_DERV_PORTS))).then(pl.lit("DERV"))
            .otherwise(pl.lit("OTHER"))
            .alias("BIS_EXP_TYPE")
        )
    else:
        df = df.with_columns(pl.lit("OTHER").alias("BIS_EXP_TYPE"))

    # BIS_CQ: Credit Quality
    ecai_col = "ECAI_RATING" if "ECAI_RATING" in df.columns else None
    if ecai_col:
        ig_ratings = ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-"]
        df = df.with_columns(
            pl.when(pl.col(ecai_col).is_null() | (pl.col(ecai_col).str.strip_chars() == ""))
            .then(pl.lit("NR"))
            .when(pl.col(ecai_col).str.strip_chars().str.to_uppercase().is_in(ig_ratings))
            .then(pl.lit("IG"))
            .otherwise(pl.lit("HY"))
            .alias("BIS_CQ")
        )
    else:
        df = df.with_columns(pl.lit("NR").alias("BIS_CQ"))

    # BIS_SECTOR_TYP
    if port_col:
        sector_conditions = pl.lit(6)  # default: Corporate
        for p, s in _SECTOR_MAP_PORT.items():
            sector_conditions = (
                pl.when(pl.col(port_col) == p).then(pl.lit(s)).otherwise(sector_conditions)
            )
        # Retail
        sector_conditions = (
            pl.when(pl.col(port_col).is_in(["VIIIa", "VIIIb", "VIIIc", "IX"]))
            .then(pl.lit(7))
            .otherwise(sector_conditions)
        )
        df = df.with_columns(sector_conditions.alias("BIS_SECTOR_TYP"))
    else:
        df = df.with_columns(pl.lit(6).alias("BIS_SECTOR_TYP"))

    # BIS_RES_MAT_YEAR: Residual maturity
    mat_col = "FINAL_MAT_DT" if "FINAL_MAT_DT" in df.columns else None
    rpt_col = "RPT_DT" if "RPT_DT" in df.columns else None

    if mat_col and rpt_col:
        df = df.with_columns(
            ((pl.col(mat_col) - pl.col(rpt_col)).dt.total_days() / 365.0)
            .clip(0, None)
            .alias("BIS_RES_MAT_YEAR")
        )
    else:
        df = df.with_columns(pl.lit(1.0).alias("BIS_RES_MAT_YEAR"))

    # Special maturity handling
    fac_col = "FAC_USAGE_CD" if "FAC_USAGE_CD" in df.columns else None
    if fac_col:
        # Nostro: 0 years
        df = df.with_columns(
            pl.when(pl.col(fac_col).str.contains("(?i)nostro"))
            .then(pl.lit(0.0))
            .otherwise(pl.col("BIS_RES_MAT_YEAR"))
            .alias("BIS_RES_MAT_YEAR")
        )

    # Maturity bucket
    df = df.with_columns(
        pl.when(pl.col("BIS_RES_MAT_YEAR") <= 1).then(pl.lit("0-1Y"))
        .when(pl.col("BIS_RES_MAT_YEAR") <= 3).then(pl.lit("1-3Y"))
        .when(pl.col("BIS_RES_MAT_YEAR") <= 5).then(pl.lit("3-5Y"))
        .when(pl.col("BIS_RES_MAT_YEAR") <= 10).then(pl.lit("5-10Y"))
        .otherwise(pl.lit(">10Y"))
        .alias("BIS_MAT_BUCKET")
    )

    logger.info("F02 BIS: CSRBB base: %d rows", len(df))
    return df
