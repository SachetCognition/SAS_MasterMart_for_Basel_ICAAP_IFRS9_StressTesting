"""
Extract DSR (Debt Service Ratio) data from Excel.

Translated from Code/02.RU_NONBANK_EXP/E_03_XLS_DSR.sas.
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
    """Import DSR Excel file."""
    xls_dir = Path(config.dir_xls)
    rpt_month = config.rpt_month
    file_path = xls_dir / f"RU_{rpt_month}" / f"DSR_{rpt_month}.xls"

    logger.info("Importing DSR data: %s", file_path)
    try:
        df = pl.read_excel(source=file_path, engine="openpyxl")
        logger.info("Imported DSR: %d rows", len(df))
        return df
    except FileNotFoundError:
        logger.warning("DSR file not found: %s", file_path)
        return pl.DataFrame()
    except Exception:
        logger.exception("Failed to import DSR from %s", file_path)
        return pl.DataFrame()
