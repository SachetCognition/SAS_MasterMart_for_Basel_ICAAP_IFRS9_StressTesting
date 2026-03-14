"""
Parameter imports — translated from Code/0.SIW_IMPORT/E_IMPORT_PARAMETERS.sas (28 lines)
and Code/01.CAR_BASE/E_00_XLS_ERR_MASTER.sas (40 lines).

Imports:
  - PD stress parameters from PD_ST.xls
  - Master scale PD from Master_Scale.xls
  - 6 sheets from ST_Manual_Master.xls
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)

# ST_Manual_Master.xls sheet definitions — from E_00_XLS_ERR_MASTER.sas
MANUAL_MASTER_SHEETS: dict[str, str] = {
    "xls_st_manual_master": "Manual_Adj",
    "xls_st_parameter": "ST_Parameter",
    "xls_cbic_bank_cust_id": "CBIC_Bank_Mapping",
    "xls_st_parm_icaap": "ST_Parameter_ICAAP",
    "xls_rst_parm": "RST_Parameter",
    "xls_rp_parm": "RP_Parameter",
}


def import_parameters(config: Config) -> dict[str, pl.DataFrame]:
    """
    Import all parameter Excel files.

    Translated from E_IMPORT_PARAMETERS.sas::

        PROC IMPORT OUT=XLS_PD DATAFILE="&dir_xlssiw.\\PD_ST.xls"
            DBMS=XLS REPLACE; GETNAMES=YES; SHEET="PD"; RUN;
        data siw.xls_param_PD;
            set XLS_PD;
            if trim(left(Rating)) eq "" then delete;
        run;

        PROC IMPORT OUT=siw.XLS_MASTER_SCALE_PD
            DATAFILE="&dir_xlssiw.\\Master_Scale.xls"
            DBMS=XLS REPLACE; GETNAMES=YES; SHEET="PD"; RUN;

    Parameters
    ----------
    config : Config
        Application configuration.

    Returns
    -------
    dict[str, pl.DataFrame]
    """
    results: dict[str, pl.DataFrame] = {}
    xlssiw_dir = Path(config.dir_xlssiw)

    # 1. PD Stress parameters
    pd_path = xlssiw_dir / "PD_ST.xls"
    try:
        xls_pd = pl.read_excel(source=pd_path, sheet_name="PD", engine="openpyxl")
        # Filter: delete rows where Rating is blank
        if "Rating" in xls_pd.columns:
            xls_pd = xls_pd.filter(
                pl.col("Rating").is_not_null()
                & (pl.col("Rating").cast(pl.Utf8).str.strip_chars() != "")
            )
        results["xls_param_pd"] = xls_pd
        logger.info("Imported PD parameters: %d rows", len(xls_pd))
    except FileNotFoundError:
        logger.warning("PD_ST.xls not found at %s", pd_path)
        results["xls_param_pd"] = pl.DataFrame()
    except Exception:
        logger.exception("Failed to import PD_ST.xls")
        results["xls_param_pd"] = pl.DataFrame()

    # 2. Master Scale PD
    ms_path = xlssiw_dir / "Master_Scale.xls"
    try:
        xls_ms = pl.read_excel(source=ms_path, sheet_name="PD", engine="openpyxl")
        results["xls_master_scale_pd"] = xls_ms
        logger.info("Imported Master Scale PD: %d rows", len(xls_ms))
    except FileNotFoundError:
        logger.warning("Master_Scale.xls not found at %s", ms_path)
        results["xls_master_scale_pd"] = pl.DataFrame()
    except Exception:
        logger.exception("Failed to import Master_Scale.xls")
        results["xls_master_scale_pd"] = pl.DataFrame()

    return results


def import_manual_master(config: Config) -> dict[str, pl.DataFrame]:
    """
    Import all 6 sheets from ST_Manual_Master.xls.

    Translated from E_00_XLS_ERR_MASTER.sas (lines 1-40)::

        PROC IMPORT OUT=siw.XLS_ST_MANUAL_MASTER_&st_rptmth.
            DATAFILE="&dir_xls.\\ST_Manual_Master.xls"
            DBMS=XLS REPLACE; SHEET="Manual_Adj"; run;
        ...

    Parameters
    ----------
    config : Config
        Application configuration.

    Returns
    -------
    dict[str, pl.DataFrame]
        Keys: xls_st_manual_master, xls_st_parameter, xls_cbic_bank_cust_id,
              xls_st_parm_icaap, xls_rst_parm, xls_rp_parm
    """
    from lib.excel_reader import import_multi_sheet

    xls_dir = Path(config.dir_xls)
    master_path = xls_dir / "ST_Manual_Master.xls"

    sheet_configs = {
        name: {"sheet": sheet_name}
        for name, sheet_name in MANUAL_MASTER_SHEETS.items()
    }

    results = import_multi_sheet(master_path, sheet_configs)
    logger.info("Imported Manual Master: %d sheets", len(results))
    return results
