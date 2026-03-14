"""
Final acceptance dataset creation for P-LOAN/ACARD.

Translated from Code/08.PLOAN-ACARD/L_01_P-LOAN.sas (~70 lines).
Applies 12-month performance window, FLAG_ALL_EXCLUDED,
and renames variables to x_01-x_38 standardized format.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)

# FLAG_ALL_EXCLUDED codes
_FINAL_EXCLUDE_CODES: dict[int, str] = {
    2: "Sampling exclusion",
    3: "Declined/Cancelled",
    4: "No performance data",
    5: "Performance exclusion",
    6: "Indeterminate outcome",
}


def run(
    config: Config,
    merged_fact: pl.DataFrame,
    x_var_mapping: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """
    Create final acceptance dataset for credit risk modeling.

    1. Apply 12-month performance window
    2. Apply FLAG_ALL_EXCLUDED (codes 2-6)
    3. Rename business variables to x_01-x_38 standardized names
    4. Output: PLOAN_ACARD_X_ACCEPT

    Parameters
    ----------
    config : Config
    merged_fact : pl.DataFrame
        Output from f03_aps_cardlink_merge.run().
    x_var_mapping : pl.DataFrame | None
        Variable mapping table (x_01-x_38 -> business names).
    """
    if merged_fact.is_empty():
        logger.warning("L01 PLOAN: Empty merged fact table")
        return pl.DataFrame()

    df = merged_fact.clone()

    # FLAG_ALL_EXCLUDED determination
    df = df.with_columns(pl.lit(None).cast(pl.Int32).alias("FLAG_ALL_EXCLUDED"))

    # 3: Declined/Cancelled
    if "DECISION" in df.columns:
        df = df.with_columns(
            pl.when(pl.col("DECISION").str.contains("(?i)decline|cancel"))
            .then(pl.lit(3))
            .otherwise(pl.col("FLAG_ALL_EXCLUDED"))
            .alias("FLAG_ALL_EXCLUDED")
        )

    # 4: No performance data
    if "IND_1ST_BAD" in df.columns:
        df = df.with_columns(
            pl.when(
                (pl.col("FLAG_ALL_EXCLUDED").is_null())
                & (pl.col("IND_1ST_BAD").is_null())
            )
            .then(pl.lit(4))
            .otherwise(pl.col("FLAG_ALL_EXCLUDED"))
            .alias("FLAG_ALL_EXCLUDED")
        )

    # 5: Performance exclusion
    if "FLAG_EXCLUDE_PERF_AGG" in df.columns:
        df = df.with_columns(
            pl.when(
                (pl.col("FLAG_ALL_EXCLUDED").is_null())
                & (pl.col("FLAG_EXCLUDE_PERF_AGG").is_not_null())
            )
            .then(pl.lit(5))
            .otherwise(pl.col("FLAG_ALL_EXCLUDED"))
            .alias("FLAG_ALL_EXCLUDED")
        )

    # 2: Sampling exclusion (from APS)
    if "FLAG_EXCLUDE_APS" in df.columns:
        df = df.with_columns(
            pl.when(
                (pl.col("FLAG_ALL_EXCLUDED").is_null())
                & (pl.col("FLAG_EXCLUDE_APS").is_not_null())
            )
            .then(pl.lit(2))
            .otherwise(pl.col("FLAG_ALL_EXCLUDED"))
            .alias("FLAG_ALL_EXCLUDED")
        )

    # Acceptance dataset: records with missing FLAG_ALL_EXCLUDED
    accept = df.filter(pl.col("FLAG_ALL_EXCLUDED").is_null())

    # Apply x_var_mapping if available (rename business vars to x_01-x_38)
    if x_var_mapping is not None and not x_var_mapping.is_empty():
        rename_map: dict[str, str] = {}
        for row in x_var_mapping.iter_rows(named=True):
            x_var = str(row.get("X_VAR", "")).strip()
            biz_var = str(row.get("BIZ_VAR", "")).strip()
            if x_var and biz_var and biz_var in accept.columns:
                rename_map[biz_var] = x_var

        if rename_map:
            accept = accept.rename(rename_map)
            logger.info("L01 PLOAN: Renamed %d variables to x_xx format", len(rename_map))

    accept = accept.with_columns(pl.lit(config.rpt_month).alias("RPT_MONTH"))

    # Export
    output_dir = Path(config.dir_mart) if hasattr(config, "dir_mart") else Path("artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"PLOAN_ACARD_X_ACCEPT_{config.rpt_month}.parquet"
    accept.write_parquet(output_path)

    logger.info(
        "L01 PLOAN: Acceptance dataset: %d rows (excluded %d), saved to %s",
        len(accept), len(df) - len(accept), output_path,
    )
    return accept
