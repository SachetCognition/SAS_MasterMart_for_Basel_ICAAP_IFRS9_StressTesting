"""
Extract RST NBMCE (Non-Bank Mortgage and Consumer Entities) data from Excel.

Translated from Code/04.RST_SEGMENT/E_01_XLS_RST_NBMCE.sas.
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
    """Import RST NBMCE Excel file."""
    xls_dir = Path(config.dir_xls)
    rpt_month = config.rpt_month
    file_path = xls_dir / f"RST_{rpt_month}" / f"RST_NBMCE_{rpt_month}.xls"

    logger.info("Importing RST NBMCE: %s", file_path)
    try:
        df = pl.read_excel(source=file_path, engine="openpyxl")
        logger.info("Imported RST NBMCE: %d rows", len(df))
        return df
    except FileNotFoundError:
        logger.warning("RST NBMCE file not found: %s", file_path)
        return pl.DataFrame()
    except Exception:
        logger.exception("Failed to import RST NBMCE from %s", file_path)
        return pl.DataFrame()
