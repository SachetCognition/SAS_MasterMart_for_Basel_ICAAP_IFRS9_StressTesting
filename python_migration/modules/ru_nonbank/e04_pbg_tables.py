"""
Extract PBG (Private Banking Group) tables.

Translated from Code/02.RU_NONBANK_EXP/E_04_PBG_TABLES.sas.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(config: Config) -> dict[str, pl.DataFrame]:
    """
    Import PBG exposure and related tables.

    Parameters
    ----------
    config : Config

    Returns
    -------
    dict[str, pl.DataFrame]
        Keys: pbg_exposure, pbg_collateral, pbg_customer
    """
    results: dict[str, pl.DataFrame] = {}
    pbg_dir = Path(config.dir_pbg) if hasattr(config, "dir_pbg") else None

    if pbg_dir is None or not pbg_dir.exists():
        logger.warning("E04: PBG directory not found")
        return {
            "pbg_exposure": pl.DataFrame(),
            "pbg_collateral": pl.DataFrame(),
            "pbg_customer": pl.DataFrame(),
        }

    rpt_month = config.rpt_month

    # PBG exposure
    for name, pattern in [
        ("pbg_exposure", f"pbg_exposure_{rpt_month}"),
        ("pbg_collateral", f"pbg_collateral_{rpt_month}"),
        ("pbg_customer", f"pbg_customer_{rpt_month}"),
    ]:
        # Try parquet first, then SAS dataset
        parquet_path = pbg_dir / f"{pattern}.parquet"
        if parquet_path.exists():
            results[name] = pl.read_parquet(parquet_path)
            logger.info("Imported %s from parquet: %d rows", name, len(results[name]))
        else:
            logger.warning("PBG file not found: %s", parquet_path)
            results[name] = pl.DataFrame()

    return results
