"""
Import Cardlink monthly performance data.

Translated from Code/08.PLOAN-ACARD/E_02_IMPORT_CARDLINK.sas (~30 lines).
Imports PIL and CARD monthly performance datasets.
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
    Import Cardlink performance data (PIL and CARD).

    Returns dict with 'cardlink_pil' and 'cardlink_card' DataFrames.
    """
    results: dict[str, pl.DataFrame] = {}
    ccd_dir = Path(config.dir_ccd) if hasattr(config, "dir_ccd") else Path("Data/0.INPUT_XLS")

    for dataset_name in ["cardlink_pil", "cardlink_card"]:
        parquet_path = ccd_dir / f"{dataset_name}.parquet"
        try:
            if parquet_path.exists():
                df = pl.read_parquet(parquet_path)
            else:
                df = pl.DataFrame()
                logger.warning("E02 PLOAN: %s not found: %s", dataset_name, parquet_path)
            results[dataset_name] = df
            if not df.is_empty():
                logger.info("E02 PLOAN: Imported %s: %d rows", dataset_name, len(df))
        except Exception:
            logger.exception("E02 PLOAN: Failed to import %s", dataset_name)
            results[dataset_name] = pl.DataFrame()

    return results
