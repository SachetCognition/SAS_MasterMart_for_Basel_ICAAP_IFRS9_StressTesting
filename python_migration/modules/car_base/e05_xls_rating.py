"""
Import CCY and bonds rating data.

Translated from Code/01.CAR_BASE/E_05_XLS_RATING.sas (13 lines).
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
    Import bond and counterparty rating Excel files.

    Translated from::

        PROC IMPORT OUT=stg.bonds_rating_&st_Rptmth.
            DATAFILE="&dir_xls.\\RIORM_&st_Rptmth.\\Bond_Rating_&st_Rptmth..xls"
            DBMS=xls REPLACE; RUN;

        PROC IMPORT OUT=stg.cc_rating_&st_Rptmth.
            DATAFILE="&dir_xls.\\RIORM_&st_Rptmth.\\Counterparty_Risk_Rating_&st_Rptmth..xls"
            DBMS=xls REPLACE; RUN;

    Returns
    -------
    dict[str, pl.DataFrame]
        Keys: ``bonds_rating``, ``cc_rating``
    """
    results: dict[str, pl.DataFrame] = {}
    xls_dir = Path(config.dir_xls)
    rpt_month = config.rpt_month
    riorm_dir = xls_dir / f"RIORM_{rpt_month}"

    # Bond ratings
    bonds_path = riorm_dir / f"Bond_Rating_{rpt_month}.xls"
    try:
        results["bonds_rating"] = pl.read_excel(source=bonds_path, engine="openpyxl")
        logger.info("Imported bonds_rating: %d rows", len(results["bonds_rating"]))
    except FileNotFoundError:
        logger.warning("Bond rating file not found: %s", bonds_path)
        results["bonds_rating"] = pl.DataFrame()
    except Exception:
        logger.exception("Failed to import bond rating from %s", bonds_path)
        results["bonds_rating"] = pl.DataFrame()

    # Counterparty credit ratings
    cc_path = riorm_dir / f"Counterparty_Risk_Rating_{rpt_month}.xls"
    try:
        results["cc_rating"] = pl.read_excel(source=cc_path, engine="openpyxl")
        logger.info("Imported cc_rating: %d rows", len(results["cc_rating"]))
    except FileNotFoundError:
        logger.warning("CC rating file not found: %s", cc_path)
        results["cc_rating"] = pl.DataFrame()
    except Exception:
        logger.exception("Failed to import CC rating from %s", cc_path)
        results["cc_rating"] = pl.DataFrame()

    return results
