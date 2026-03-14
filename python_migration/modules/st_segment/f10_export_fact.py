"""
Export fact tables for stress testing results.

Translated from Code/05.ST_SEGMENT/F_10_EXPORT_FACT.sas (~30 lines).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(config: Config, st_combined: pl.DataFrame, icaap_combined: pl.DataFrame) -> None:
    """
    Export stressed fact tables to the FACT data layer.

    Parameters
    ----------
    config : Config
    st_combined : pl.DataFrame
        Combined stressed dataset from f08.
    icaap_combined : pl.DataFrame
        ICAAP combined stressed dataset from f09.
    """
    fact_dir = Path(config.dir_fact) if hasattr(config, "dir_fact") else Path("Data/3.FACT")
    fact_dir.mkdir(parents=True, exist_ok=True)
    rpt = config.rpt_month

    if not st_combined.is_empty():
        path = fact_dir / f"st_crm_rwa_fact_{rpt}.parquet"
        st_combined.write_parquet(path)
        logger.info("F10 ST: Exported st_crm_rwa_fact: %d rows -> %s", len(st_combined), path)

    if not icaap_combined.is_empty():
        path = fact_dir / f"st_icaap_fact_{rpt}.parquet"
        icaap_combined.write_parquet(path)
        logger.info("F10 ST: Exported st_icaap_fact: %d rows -> %s", len(icaap_combined), path)
