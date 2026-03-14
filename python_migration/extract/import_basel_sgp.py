"""
Singapore Basel returns extraction — translated from Code/0.SIW_IMPORT/E_IMPORT_BASEL_SGP.sas (98 lines).

Imports 5 SGP Excel types: IMEX, MM, Loan, FX, Nostro using the
dynamic column typing logic from the %tx and %SGPImport macros.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)

# SGP import configurations — translated from lines 94-98:
# %SGPImport(IMEX,5);
# %SGPImport(MM,12);
# %SGPImport(Loan,4,Sheet1);
# %SGPImport(FX,6,Data);
# %SGPImport(Nostro,5,Sheet1);
SGP_CONFIGS: list[dict[str, str | int | None]] = [
    {"type_name": "IMEX", "name_row": 5, "sheet": None},
    {"type_name": "MM", "name_row": 12, "sheet": None},
    {"type_name": "Loan", "name_row": 4, "sheet": "Sheet1"},
    {"type_name": "FX", "name_row": 6, "sheet": "Data"},
    {"type_name": "Nostro", "name_row": 5, "sheet": "Sheet1"},
]


def import_all_sgp(config: Config) -> dict[str, pl.DataFrame]:
    """
    Import all Singapore Basel return Excel files.

    Translated from E_IMPORT_BASEL_SGP.sas::

        %SGPImport(IMEX,5);            /* Trade Bills */
        %SGPImport(MM,12);             /* Money Market */
        %SGPImport(Loan,4,Sheet1);     /* Loans and Advances */
        %SGPImport(FX,6,Data);         /* Off Bal. derivatives */
        %SGPImport(Nostro,5,Sheet1);   /* Nostro */

    Parameters
    ----------
    config : Config
        Application configuration with paths.

    Returns
    -------
    dict[str, pl.DataFrame]
        ``{type_name: DataFrame, ...}``
    """
    from lib.excel_reader import import_sgp_excel

    results: dict[str, pl.DataFrame] = {}
    xlssiw_dir = Path(config.dir_xlssiw)

    for sgp_config in SGP_CONFIGS:
        type_name = str(sgp_config["type_name"])
        name_row = int(sgp_config["name_row"])  # type: ignore[arg-type]
        sheet = sgp_config.get("sheet")

        # File path pattern: SG_{type}_OS_{YYYYMMDD}_Return.xls
        file_name = f"SG_{type_name}_OS_{config.st_rpt_ymd}_Return.xls"
        file_path = xlssiw_dir / file_name

        logger.info("SGP Import: %s from %s", type_name, file_path)

        try:
            df = import_sgp_excel(
                path=file_path,
                type_name=type_name,
                name_row=name_row,
                sheet=str(sheet) if sheet else None,
                dt_f_x2s=config.dt_f_x2s,
            )
            results[type_name] = df
            logger.info("  -> %s: %d rows, %d columns", type_name, len(df), len(df.columns))
        except FileNotFoundError:
            logger.warning("SGP file not found: %s", file_path)
            results[type_name] = pl.DataFrame()
        except Exception:
            logger.exception("Failed to import SGP %s from %s", type_name, file_path)
            results[type_name] = pl.DataFrame()

    return results
