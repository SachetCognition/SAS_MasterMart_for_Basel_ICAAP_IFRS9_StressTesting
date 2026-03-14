"""
Extract NPL (Non-Performing Loan) data from Excel.

Translated from Code/02.RU_NONBANK_EXP/E_02_XLS_NPL.sas.
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
    """Import NPL Excel file."""
    xls_dir = Path(config.dir_xls)
    rpt_month = config.rpt_month
    file_path = xls_dir / f"RU_{rpt_month}" / f"NPL_{rpt_month}.xls"

    logger.info("Importing NPL data: %s", file_path)
    try:
        df = pl.read_excel(source=file_path, engine="openpyxl")
        if "ACCT_ID" in df.columns:
            df = df.filter(pl.col("ACCT_ID").is_not_null())
        logger.info("Imported NPL: %d rows", len(df))
        return df
    except FileNotFoundError:
        logger.warning("NPL file not found: %s", file_path)
        return pl.DataFrame()
    except Exception:
        logger.exception("Failed to import NPL from %s", file_path)
        return pl.DataFrame()
