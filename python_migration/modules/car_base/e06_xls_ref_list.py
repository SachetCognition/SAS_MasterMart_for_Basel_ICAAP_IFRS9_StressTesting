"""
Import REF (Real Estate Financing) reference lists.

Translated from Code/01.CAR_BASE/E_06_XLS_REF_LIST.sas (12 lines).
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
    Import the REF facility reference list.

    Translated from::

        PROC IMPORT OUT=stg.REF_List_&st_Rptmth.
            DATAFILE="&dir_xls.\\WBG_&st_Rptmth.\\REF_List_&st_Rptmth..xls"
            DBMS=xls REPLACE; RUN;

        data stg.REF_List_&st_Rptmth.;
            set stg.REF_List_&st_Rptmth.;
            where not missing(FAC_REF);
        run;

    Returns
    -------
    pl.DataFrame
    """
    xls_dir = Path(config.dir_xls)
    rpt_month = config.rpt_month
    wbg_dir = xls_dir / f"WBG_{rpt_month}"
    file_path = wbg_dir / f"REF_List_{rpt_month}.xls"

    logger.info("Importing REF list: %s", file_path)

    try:
        df = pl.read_excel(source=file_path, engine="openpyxl")
        # Filter: keep only rows where FAC_REF is not missing
        if "FAC_REF" in df.columns:
            df = df.filter(
                pl.col("FAC_REF").is_not_null()
                & (pl.col("FAC_REF").cast(pl.Utf8).str.strip_chars() != "")
            )
        logger.info("Imported REF list: %d rows", len(df))
        return df
    except FileNotFoundError:
        logger.warning("REF list file not found: %s", file_path)
        return pl.DataFrame()
    except Exception:
        logger.exception("Failed to import REF list from %s", file_path)
        return pl.DataFrame()
