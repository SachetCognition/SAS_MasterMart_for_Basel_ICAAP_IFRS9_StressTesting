"""
ICAAP pipeline DAG orchestrator.

Orchestrates ST Country FI and BIS Check modules.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run_pipeline(
    config: Config,
    fact_rwa: pl.DataFrame,
    master_scale_pd: pl.DataFrame,
    cust_elim: pl.DataFrame | None = None,
) -> dict[str, pl.DataFrame]:
    """Execute ICAAP-related pipelines (ST Country FI + BIS Check)."""
    from modules.bis_check import (
        f01_bis_gen_info,
        f02_bis_csrbb_base,
        f03_bis_csrbb_part_a,
        f04_bis_csrbb_part_b,
    )
    from modules.st_country_fi import l01_base, m01_base, r01_summary

    results: dict[str, pl.DataFrame] = {}

    # ── ST Country FI ──
    logger.info("ICAAP DAG: ST Country FI - Base")
    fi_base = l01_base.run(config, fact_rwa, cust_elim)
    fi_stressed = m01_base.run(config, fi_base, master_scale_pd)
    fi_summary = r01_summary.run(config, fi_stressed)
    results["fi_base"] = fi_base
    results["fi_stressed"] = fi_stressed
    results.update(fi_summary)

    # ── BIS Check ──
    logger.info("ICAAP DAG: BIS Check")
    bis_gen = f01_bis_gen_info.run(config, fact_rwa)
    bis_base = f02_bis_csrbb_base.run(config, fact_rwa)
    bis_part_a = f03_bis_csrbb_part_a.run(config, bis_base)
    bis_part_b = f04_bis_csrbb_part_b.run(config, bis_base)
    results["bis_gen_info"] = bis_gen
    results["bis_csrbb_base"] = bis_base
    results.update(bis_part_a)
    results.update(bis_part_b)

    logger.info("ICAAP DAG: Pipeline complete")
    return results
