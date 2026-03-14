"""
RU Non-Bank Exposure pipeline DAG orchestrator.

Orchestrates non-bank exposure and NPL data processing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run_pipeline(config: Config) -> dict[str, pl.DataFrame]:
    """Execute the full RU Non-Bank pipeline."""
    from modules.ru_nonbank import (
        e01_xls_ru_nonpbg_exp,
        e02_xls_npl,
        e03_xls_dsr,
        e04_pbg_tables,
        f01_ru_nonpbg_exp,
        f02_ru_pbg_add_dsr,
        f03_ru_pbg_exp,
        l01_ru_npl_fact_table,
        m01_npl_ratio_by_bu,
        r01_summary,
    )

    results: dict[str, pl.DataFrame] = {}

    # Extract
    logger.info("RU_NONBANK DAG: Extract")
    nonpbg_raw = e01_xls_ru_nonpbg_exp.run(config)
    npl_raw = e02_xls_npl.run(config)
    dsr_raw = e03_xls_dsr.run(config)
    pbg_tables = e04_pbg_tables.run(config)

    # Transform
    logger.info("RU_NONBANK DAG: Transform")
    nonpbg = f01_ru_nonpbg_exp.run(config, nonpbg_raw)
    pbg_dsr = f02_ru_pbg_add_dsr.run(
        config,
        pbg_tables.get("pbg_exposure", pl.DataFrame()),
        dsr_raw,
    )
    pbg_exp = f03_ru_pbg_exp.run(config, pbg_dsr)

    # Load
    logger.info("RU_NONBANK DAG: Load")
    npl_fact = l01_ru_npl_fact_table.run(config, nonpbg, pbg_exp, npl_raw)
    results["npl_fact"] = npl_fact

    # Model
    npl_ratios = m01_npl_ratio_by_bu.run(config, npl_fact)
    results["npl_ratios_df"] = pl.DataFrame({
        "BU": list(npl_ratios.keys()),
        "NPL_RATIO": list(npl_ratios.values()),
    })

    # Report
    logger.info("RU_NONBANK DAG: Report")
    summary = r01_summary.run(config, npl_fact)
    results.update(summary)

    logger.info("RU_NONBANK DAG: Pipeline complete")
    return results
