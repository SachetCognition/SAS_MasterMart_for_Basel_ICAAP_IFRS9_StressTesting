"""
Build notch_cc and notch_bd lookup formats from rating data.

Translated from Code/01.CAR_BASE/F_11_CCP_BONDS_RATING.sas (~180 lines).

Creates dynamic PROC FORMAT lookups used in L_01:
  - notch_cc: Counterparty credit rating → NOTCH (by RM_CUST_ID + CCY_GROUP)
  - notch_bd: Bond rating → NOTCH (by ACCT_ID)
  - Handles multiple rating agencies with priority logic
  - Selects target rating (flag_target=1) based on most conservative rating
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

from lib.lookups import build_notch_bd_lookup, build_notch_cc_lookup

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)

# Rating agency priority (lower = higher priority)
_AGENCY_PRIORITY = {
    "S&P": 1,
    "MOODY": 2,
    "MOODYS": 2,
    "FITCH": 3,
    "OTHER": 99,
}


def _assign_notch(df: pl.DataFrame) -> pl.DataFrame:
    """
    Assign NOTCH integer from rating strings.

    Maps S&P-style ratings to notch values:
      AAA=1, AA+=2, AA=3, AA-=4, A+=5, A=6, A-=7,
      BBB+=8, BBB=9, BBB-=10, BB+=11, BB=12, BB-=13,
      B+=14, B=15, B-=16, CCC+=17, CCC=18, CCC-=19,
      CC=20, C=21, D=22
    """
    rating_to_notch: dict[str, int] = {
        "AAA": 1, "AA+": 2, "AA": 3, "AA-": 4,
        "A+": 5, "A": 6, "A-": 7,
        "BBB+": 8, "BBB": 9, "BBB-": 10,
        "BB+": 11, "BB": 12, "BB-": 13,
        "B+": 14, "B": 15, "B-": 16,
        "CCC+": 17, "CCC": 18, "CCC-": 19,
        "CC": 20, "C": 21, "D": 22,
    }

    if "ECAI_RATING" not in df.columns:
        return df.with_columns(pl.lit(None).cast(pl.Int32).alias("NOTCH"))

    # Create mapping DataFrame for join-based lookup
    map_df = pl.DataFrame({
        "ECAI_RATING": list(rating_to_notch.keys()),
        "NOTCH": list(rating_to_notch.values()),
    })

    # Normalize the rating string
    df = df.with_columns(
        pl.col("ECAI_RATING").cast(pl.Utf8).str.strip_chars().str.to_uppercase().alias("_rating_clean")
    )

    map_df = map_df.with_columns(
        pl.col("ECAI_RATING").str.to_uppercase().alias("_rating_clean")
    )

    result = df.join(
        map_df.select(["_rating_clean", "NOTCH"]),
        on="_rating_clean",
        how="left",
    ).drop("_rating_clean")

    return result


def _select_target_rating(df: pl.DataFrame, group_cols: list[str]) -> pl.DataFrame:
    """
    Select the target rating per group (most conservative = highest NOTCH).

    SAS logic (F_11 lines 131-152):
      1. For each group, if multiple agencies, pick most conservative (highest NOTCH)
      2. If tie, pick by agency priority
      3. Flag selected row as flag_target = 1
    """
    if df.is_empty() or "NOTCH" not in df.columns:
        return df

    valid_group = [c for c in group_cols if c in df.columns]
    if not valid_group:
        return df

    # Add row index for unique identification when joining back
    df = df.with_row_index("_row_idx")

    # Filter out rows with missing NOTCH
    rated = df.filter(pl.col("NOTCH").is_not_null())
    if rated.is_empty():
        return df.with_columns(pl.lit(0).alias("flag_target")).drop("_row_idx")

    # Add agency priority
    if "RATING_AGENCY" in rated.columns:
        rated = rated.with_columns(
            pl.col("RATING_AGENCY").cast(pl.Utf8).str.to_uppercase()
            .replace(_AGENCY_PRIORITY, default=99)
            .cast(pl.Int32)
            .alias("_agency_pri")
        )
    else:
        rated = rated.with_columns(pl.lit(99).alias("_agency_pri"))

    # Sort: most conservative first (highest NOTCH), then by agency priority
    rated = rated.sort(valid_group + ["NOTCH", "_agency_pri"], descending=[False] * len(valid_group) + [True, False])

    # Pick the last per group (highest NOTCH = most conservative)
    target = rated.group_by(valid_group).last()

    # Use _row_idx to mark ONLY the single target row per group
    target_indices = set(target["_row_idx"].to_list())
    result = df.with_columns(
        pl.when(pl.col("_row_idx").is_in(list(target_indices)))
        .then(1)
        .otherwise(0)
        .alias("flag_target")
    ).drop("_row_idx")

    return result


def run(
    config: Config,
    cc_rating: pl.DataFrame,
    bonds_rating: pl.DataFrame,
) -> dict[str, object]:
    """
    Build notch lookup formats from rating data.

    Parameters
    ----------
    config : Config
    cc_rating : pl.DataFrame
        Counterparty credit rating data from e05_xls_rating.
    bonds_rating : pl.DataFrame
        Bond rating data from e05_xls_rating.

    Returns
    -------
    dict[str, object]
        Keys:
          - cc_rate_notch: pl.DataFrame with assigned NOTCH and flag_target
          - bonds_notch: pl.DataFrame with assigned NOTCH and flag_target
          - notch_cc_map: dict mapping RM_CUST_ID+CCY_GROUP → NOTCH
          - notch_bd_map: dict mapping ACCT_ID → NOTCH
    """
    results: dict[str, object] = {}

    # --- Counterparty credit rating processing ---
    if not cc_rating.is_empty():
        cc_df = _assign_notch(cc_rating)
        cc_df = _select_target_rating(cc_df, ["RM_CUST_ID", "CCY_GROUP"])
        results["cc_rate_notch"] = cc_df

        # Build lookup from target ratings
        target_cc = cc_df.filter(pl.col("flag_target") == 1)
        results["notch_cc_map"] = build_notch_cc_lookup(target_cc)
        logger.info("F11: CC rating notch: %d entries, %d target",
                     len(cc_df), len(target_cc))
    else:
        results["cc_rate_notch"] = pl.DataFrame()
        results["notch_cc_map"] = {}

    # --- Bond rating processing ---
    if not bonds_rating.is_empty():
        bd_df = _assign_notch(bonds_rating)
        bd_df = _select_target_rating(bd_df, ["ACCT_ID"])
        results["bonds_notch"] = bd_df

        # Build lookup from target ratings
        target_bd = bd_df.filter(pl.col("flag_target") == 1)
        results["notch_bd_map"] = build_notch_bd_lookup(target_bd)
        logger.info("F11: Bond rating notch: %d entries, %d target",
                     len(bd_df), len(target_bd))
    else:
        results["bonds_notch"] = pl.DataFrame()
        results["notch_bd_map"] = {}

    return results
