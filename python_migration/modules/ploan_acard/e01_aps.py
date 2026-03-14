"""
Import APS (Application Processing System) data.

Translated from Code/08.PLOAN-ACARD/E_01_IMPORT_APS.sas (~40 lines).
Imports Old and New APS application data.
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
    Import APS application data (Old and New formats).

    Returns dict with 'aps_old' and 'aps_new' DataFrames.
    """
    results: dict[str, pl.DataFrame] = {}
    aps_dir = Path(config.dir_aps) if hasattr(config, "dir_aps") else Path("Data/0.INPUT_XLS")

    # Old APS
    old_path = aps_dir / "aps_old.sas7bdat"
    if old_path.exists():
        try:
            df = pl.read_parquet(old_path.with_suffix(".parquet"))
            results["aps_old"] = df
            logger.info("E01 PLOAN: Imported old APS: %d rows", len(df))
        except FileNotFoundError:
            results["aps_old"] = pl.DataFrame()
            logger.warning("E01 PLOAN: Old APS not found: %s", old_path)
    else:
        results["aps_old"] = pl.DataFrame()

    # New APS
    new_path = aps_dir / "aps_new.sas7bdat"
    if new_path.exists():
        try:
            df = pl.read_parquet(new_path.with_suffix(".parquet"))
            results["aps_new"] = df
            logger.info("E01 PLOAN: Imported new APS: %d rows", len(df))
        except FileNotFoundError:
            results["aps_new"] = pl.DataFrame()
            logger.warning("E01 PLOAN: New APS not found: %s", new_path)
    else:
        results["aps_new"] = pl.DataFrame()

    return results
