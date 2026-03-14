"""
Import derivative Excel data.

Translated from Code/01.CAR_BASE/E_04_XLS_DERIVATIVE.sas (10 lines).
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
    Import derivative summary Excel file.

    Translated from::

        %off_Derv_Import(Summary of Car adj for Derivatives_&st_RptYMD..xls,
                         stg.x_deriv_&st_Rptmth.);

    Parameters
    ----------
    config : Config

    Returns
    -------
    pl.DataFrame
    """
    xls_dir = Path(config.dir_xls)
    rpt_ymd = config.st_rpt_ymd
    rpt_month = config.rpt_month
    fmd_dir = xls_dir / f"FMD_{rpt_month}"

    file_name = f"Summary of Car adj for Derivatives_{rpt_ymd}.xls"
    file_path = fmd_dir / file_name

    logger.info("Importing derivative data: %s", file_path)

    try:
        # GETNAMES=NO — read raw without column names
        df = pl.read_excel(source=file_path, engine="openpyxl")
        logger.info("Imported derivative data: %d rows, %d columns", len(df), len(df.columns))
        return df
    except FileNotFoundError:
        logger.warning("Derivative file not found: %s", file_path)
        return pl.DataFrame()
    except Exception:
        logger.exception("Failed to import derivative file: %s", file_path)
        return pl.DataFrame()
