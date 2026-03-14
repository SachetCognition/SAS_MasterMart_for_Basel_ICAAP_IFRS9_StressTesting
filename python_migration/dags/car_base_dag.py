"""
CAR_BASE pipeline DAG orchestrator.

Orchestrates the 5-stage ETL pipeline for core fact table preparation:
PART 1: Extract common (IW, Basel SGP, Parameters)
PART 2: Extract RWA-specific (Error master, Derivatives, Ratings)
PART 3: Formulate & Transform (11 scripts)
PART 4: Load to FACT (RWA, ICAAP format, ICAAP info)
PART 5: Sense Checking (On-balance, Off-balance, Derivatives)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run_pipeline(config: Config, datasets: dict[str, pl.DataFrame]) -> dict[str, pl.DataFrame]:
    """
    Execute the full CAR_BASE pipeline.

    Parameters
    ----------
    config : Config
    datasets : dict[str, pl.DataFrame]
        Pre-loaded datasets from extract layer.

    Returns
    -------
    dict[str, pl.DataFrame]
        All output datasets including fact tables and sense-check results.
    """
    from modules.car_base import (
        e00_xls_err_master,
        e02_xls_nonsystem,
        e04_xls_derivative,
        e05_xls_rating,
        e06_xls_ref_list,
        f00_iw_to_stg,
        f03_derivative,
        f04_iw_adj,
        f05_sgp_xls,
        f06_sgp_nostro,
        f07_adj_delta,
        f08_nonsys_delta,
        f09_hkcbf_adj_n_delta,
        f10_cbic_adj,
        f11_ccp_bonds_rating,
        f12_ref_list_from_bu,
        l01_fact_rwa,
        l02_fact_icaap_format,
        l03_fact_icaap_info,
        s01_onbal_checking,
        s02_offbal_checking,
        s03_derivative_checking,
    )

    results: dict[str, pl.DataFrame] = {}

    # PART 1: Extract common
    logger.info("CAR_BASE DAG: PART 1 - Extract common")
    # IW data assumed pre-loaded in datasets

    # PART 2: Extract RWA-specific
    logger.info("CAR_BASE DAG: PART 2 - Extract RWA-specific")
    xls_err = e00_xls_err_master.run(config)
    xls_nonsys = e02_xls_nonsystem.run(config)
    xls_derv = e04_xls_derivative.run(config)
    xls_rating = e05_xls_rating.run(config)
    xls_ref = e06_xls_ref_list.run(config)

    # PART 3: Formulate & Transform
    logger.info("CAR_BASE DAG: PART 3 - Formulate & Transform")
    stg_iw = f00_iw_to_stg.run(config, datasets)

    # Extract combined CAR DataFrame from per-entity results
    # f00_iw_to_stg returns dict; downstream modules need a single DataFrame
    rpt = config.rpt_month
    car_frames = [
        stg_iw[f"vi_iambs_{e}_car_{rpt}"]
        for e in ["kw", "vc", "cf", "sz"]
        if f"vi_iambs_{e}_car_{rpt}" in stg_iw
        and not stg_iw[f"vi_iambs_{e}_car_{rpt}"].is_empty()
    ]
    car_iw_combined = pl.concat(car_frames, how="diagonal") if car_frames else pl.DataFrame()

    stg_derv = f03_derivative.run(config, xls_derv)
    sgp_imex = datasets.get("sgp_imex", pl.DataFrame())
    err_master_df = xls_err.get("xls_st_manual_master", pl.DataFrame())
    stg_adj = f04_iw_adj.run(
        config, car_iw_combined, sgp_imex, err_master_df,
    )
    stg_sgp = f05_sgp_xls.run(config, datasets)
    stg_nostro = f06_sgp_nostro.run(config, datasets.get("sgp_nostro", pl.DataFrame()))
    stg_adj_delta = f07_adj_delta.run(config, err_master_df)
    stg_ns_delta = f08_nonsys_delta.run(
        config,
        xls_nonsys.get("nonsystem", pl.DataFrame()),
        xls_nonsys.get("ns_hkcbf", pl.DataFrame()),
    )
    stg_hkcbf = f09_hkcbf_adj_n_delta.run(config, stg_adj)
    stg_cbic = f10_cbic_adj.run(config, stg_adj)
    rating_lookups = f11_ccp_bonds_rating.run(
        config,
        xls_rating.get("cc_rating", pl.DataFrame()),
        xls_rating.get("bonds_rating", pl.DataFrame()),
    )
    stg_ref = f12_ref_list_from_bu.run(config, xls_ref, car_iw_adj=stg_adj)

    # Collect all staging datasets
    # Modules returning dict must be flattened so l01_fact_rwa can find
    # individual keys like "adj_sgp_imex", "adj_delta_3", etc.
    staging: dict[str, pl.DataFrame] = {
        "car_iw_adj": stg_adj,
        "adj_derv_delta": stg_derv,
        "car_sz_adj": stg_cbic,
        "ref_list": stg_ref if isinstance(stg_ref, pl.DataFrame) else pl.DataFrame(),
    }
    staging.update(stg_sgp)                # adj_sgp_imex, adj_sgp_mm, ...
    staging["adj_sgp_nostro_tb"] = stg_nostro
    staging.update(stg_adj_delta)          # adj_delta_3, adj_delta_5, ...
    staging.update(stg_ns_delta)           # nonsystem delta keys
    staging.update(stg_hkcbf)              # car_hkcbf_adj, adj_ns_hkcbf_delta
    staging.update(rating_lookups)

    # PART 4: Load to FACT
    logger.info("CAR_BASE DAG: PART 4 - Load to FACT")
    notch_cc_map = rating_lookups.get("notch_cc_map", {})
    notch_bd_map = rating_lookups.get("notch_bd_map", {})
    ref_list_df = stg_ref if isinstance(stg_ref, pl.DataFrame) else pl.DataFrame()
    fact_rwa = l01_fact_rwa.run(config, staging, notch_cc_map, notch_bd_map, ref_list_df)
    fact_icaap = l02_fact_icaap_format.run(config, fact_rwa)
    fact_icaap_info = l03_fact_icaap_info.run(config, fact_icaap)

    results["fact_rwa"] = fact_rwa
    results["fact_icaap"] = fact_icaap
    results["fact_icaap_info"] = fact_icaap_info

    # PART 5: Sense Checking
    logger.info("CAR_BASE DAG: PART 5 - Sense Checking")
    onbal_results = s01_onbal_checking.run(config, fact_rwa)
    offbal_results = s02_offbal_checking.run(config, fact_rwa)
    derv_results = s03_derivative_checking.run(config, fact_rwa)
    results.update(onbal_results)
    results.update(offbal_results)
    results.update(derv_results)

    logger.info("CAR_BASE DAG: Pipeline complete")
    return results
