"""
Extract RST Property Investment/Development data from Excel.

Translated from Code/04.RST_SEGMENT/E_02_XLS_RST_PRTY_INV_DEV.sas.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(config: Config) -> pl.DataFrame:
    """Import RST Property Investment/Development Excel file."""
    xls_dir = Path(config.dir_xls)
    rpt_month = config.rpt_month
    file_path = xls_dir / f"RST_{rpt_month}" / f"RST_PRTY_INV_DEV_{rpt_month}.xls"

    logger.info("Importing RST PRTY_INV_DEV: %s", file_path)
    try:
        df = pl.read_excel(source=file_path, engine="openpyxl")
        logger.info("Imported RST PRTY_INV_DEV: %d rows", len(df))
        return df
    except FileNotFoundError:
        logger.warning("RST PRTY_INV_DEV file not found: %s", file_path)
        return pl.DataFrame()
    except Exception:
        logger.exception("Failed to import RST PRTY_INV_DEV from %s", file_path)
        return pl.DataFrame()
