"""
ST Segment pipeline DAG orchestrator.

Orchestrates stress testing across 8 Basel asset classes.
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
    st_parameter: pl.DataFrame,
    master_scale_pd: pl.DataFrame,
    npl_ratios: dict[str, float] | None = None,
) -> dict[str, pl.DataFrame]:
    """Execute the full ST Segment pipeline."""
    from modules.st_segment import (
        f01_parameter,
        f02_segment,
        f03_st_bank_fi,
        f04_st_derivative,
        f05_st_rml,
        f06_st_other,
        f07_st_nonrml,
        f08_combined,
        f09_icaap_combined,
        f10_export_fact,
        f11_st_summary,
        f12_icaap_summary,
    )

    results: dict[str, pl.DataFrame] = {}

    # Parse parameters
    logger.info("ST_SEGMENT DAG: Parse parameters")
    params = f01_parameter.run(config, st_parameter)

    # Segment
    logger.info("ST_SEGMENT DAG: Segment fact table")
    segments = f02_segment.run(config, fact_rwa)

    # Stress each segment
    logger.info("ST_SEGMENT DAG: Stress segments")
    stressed: dict[str, pl.DataFrame] = {}

    stressed["bank_fi"] = f03_st_bank_fi.run(
        config, segments.get("st_bank_fi", pl.DataFrame()), params, master_scale_pd,
    )
    stressed["derivative"] = f04_st_derivative.run(
        config, segments.get("st_derivative", pl.DataFrame()), params,
    )
    stressed["rml"] = f05_st_rml.run(
        config, segments.get("st_rml", pl.DataFrame()), params, npl_ratios or {},
    )

    # Other segments (sovereign, cash, past_due, exception)
    for seg_name in ["sovereign_pse_mdb", "cash", "past_due", "exception"]:
        stressed[seg_name] = f06_st_other.run(
            config, segments.get(f"st_{seg_name}", pl.DataFrame()), params,
        )

    stressed["non_rml"] = f07_st_nonrml.run(
        config, segments.get("st_non_rml", pl.DataFrame()), params, npl_ratios or {},
    )

    # Combine
    logger.info("ST_SEGMENT DAG: Combine")
    combined = f08_combined.run(config, stressed)
    icaap_combined = f09_icaap_combined.run(config, combined)
    results["st_combined"] = combined
    results["icaap_combined"] = icaap_combined

    # Export
    f10_export_fact.run(config, combined, icaap_combined)

    # Summary reports
    st_summary = f11_st_summary.run(config, combined)
    icaap_summary = f12_icaap_summary.run(config, icaap_combined)
    results.update(st_summary)
    results.update(icaap_summary)

    logger.info("ST_SEGMENT DAG: Pipeline complete")
    return results
