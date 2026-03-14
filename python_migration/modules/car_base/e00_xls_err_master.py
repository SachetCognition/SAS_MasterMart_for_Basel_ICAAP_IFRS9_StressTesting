"""
Import 6 Excel sheets from ST_Manual_Master.xls.

Translated from Code/01.CAR_BASE/E_00_XLS_ERR_MASTER.sas (40 lines).

Sheets imported:
  - Manual_Adj         -> xls_st_manual_master
  - ST_Parameter       -> xls_st_parameter
  - CBIC_Bank_Mapping  -> xls_cbic_bank_cust_id
  - ST_Parameter_ICAAP -> xls_st_parm_icaap
  - RST_Parameter      -> xls_rst_parm
  - RP_Parameter       -> xls_rp_parm
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(config: Config) -> dict[str, pl.DataFrame]:
    """
    Import all sheets from ST_Manual_Master.xls.

    Delegates to ``extract.import_parameters.import_manual_master()``.

    Parameters
    ----------
    config : Config
        Application configuration.

    Returns
    -------
    dict[str, pl.DataFrame]
    """
    from extract.import_parameters import import_manual_master

    results = import_manual_master(config)
    logger.info("E00: Imported %d sheets from ST_Manual_Master.xls", len(results))
    return results
