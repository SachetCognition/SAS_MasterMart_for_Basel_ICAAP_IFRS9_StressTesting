"""
CBIC (China) adjustments.

Translated from Code/01.CAR_BASE/F_10_CBIC_ADJ.sas (~100 lines).

Processes CBIC-specific adjustments:
  - Filter SZ entity data
  - Apply CBIC customer ID mapping
  - Apply CBIC-specific PORT_CD and risk weight adjustments
  - Produce car_sz_adj staging dataset
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(
    config: Config,
    car_iw_adj: pl.DataFrame,
    cbic_bank_mapping: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """
    Apply CBIC-specific adjustments.

    Translated from F_10_CBIC_ADJ.sas:
      - Filter for FLAG_SRC = 'SZ' or 'CF' (China entities)
      - Apply CBIC bank customer ID mapping
      - Reclassify PORT_CD for CBIC-specific rules
      - Tag with FILE_SRC = 'CBIC'

    Parameters
    ----------
    config : Config
    car_iw_adj : pl.DataFrame
        Adjusted CAR IW data from f04_iw_adj.
    cbic_bank_mapping : pl.DataFrame | None
        CBIC bank customer mapping from E_00.

    Returns
    -------
    pl.DataFrame
        car_sz_adj staging dataset.
    """
    if car_iw_adj.is_empty():
        logger.warning("F10: Empty CAR IW adj input")
        return pl.DataFrame()

    flag_col = "FLAG_SRC" if "FLAG_SRC" in car_iw_adj.columns else None
    if flag_col is None:
        return pl.DataFrame()

    # Filter for China entities (SZ = Shenzhen, CF = CITIC Finance)
    cbic_mask = pl.col(flag_col).is_in(["SZ", "CF"])
    cbic_df = car_iw_adj.filter(cbic_mask)

    if cbic_df.is_empty():
        logger.info("F10: No CBIC records found")
        return pl.DataFrame()

    # Apply CBIC bank customer ID mapping
    if cbic_bank_mapping is not None and not cbic_bank_mapping.is_empty():
        if "CUST_NAME" in cbic_bank_mapping.columns and "ISSUE_BANK_CUST_SEC_ID" in cbic_bank_mapping.columns:
            mapping_dict: dict[str, str] = {}
            for row in cbic_bank_mapping.iter_rows(named=True):
                name = str(row.get("CUST_NAME", "")).strip()
                sec_id = str(row.get("ISSUE_BANK_CUST_SEC_ID", ""))
                if name:
                    mapping_dict[name] = sec_id

            if mapping_dict and "CUST_NAME" in cbic_df.columns:
                cbic_df = cbic_df.with_columns(
                    pl.col("CUST_NAME").cast(pl.Utf8).replace(mapping_dict, default=None)
                    .alias("CBIC_BANK_CUST_SEC_ID")
                )

    # Tag with CBIC identifiers
    cbic_df = cbic_df.with_columns([
        pl.lit("CBIC").alias("FILE_SRC"),
        pl.lit(220.0).alias("FLAG_ADJ"),
    ])

    # Apply CBIC-specific PORT_CD adjustments
    # In SAS: if PORT_CD = 'IX' and FLAG_SRC = 'SZ' then PORT_CD = 'VI'
    # (China RML treated as corporate for consolidation)
    if "PORT_CD" in cbic_df.columns:
        cbic_df = cbic_df.with_columns(
            pl.when(
                (pl.col("PORT_CD") == "IX") & (pl.col(flag_col) == "SZ")
            )
            .then(pl.lit("VI"))
            .otherwise(pl.col("PORT_CD"))
            .alias("PORT_CD")
        )

    logger.info("F10: CBIC adj: %d rows", len(cbic_df))
    return cbic_df
