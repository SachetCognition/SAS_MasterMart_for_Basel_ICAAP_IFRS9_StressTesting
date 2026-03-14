"""
Extract non-PBG exposure data from Excel.

Translated from Code/02.RU_NONBANK_EXP/E_01_XLS_RU_NONPBG_EXP.sas.
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
    """
    Import non-PBG (non-Private Banking Group) exposure Excel file.

    Parameters
    ----------
    config : Config

    Returns
    -------
    pl.DataFrame
    """
    xls_dir = Path(config.dir_xls)
    rpt_month = config.rpt_month
    file_path = xls_dir / f"RU_{rpt_month}" / f"NonPBG_Exposure_{rpt_month}.xls"

    logger.info("Importing non-PBG exposure: %s", file_path)
    try:
        df = pl.read_excel(source=file_path, engine="openpyxl")
        # Filter out blank rows
        if "CUST_NAME" in df.columns:
            df = df.filter(pl.col("CUST_NAME").is_not_null())
        logger.info("Imported non-PBG exposure: %d rows", len(df))
        return df
    except FileNotFoundError:
        logger.warning("Non-PBG exposure file not found: %s", file_path)
        return pl.DataFrame()
    except Exception:
        logger.exception("Failed to import non-PBG exposure from %s", file_path)
        return pl.DataFrame()
