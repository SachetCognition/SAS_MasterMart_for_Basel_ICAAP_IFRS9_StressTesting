"""
RST Segment pipeline DAG orchestrator.

Orchestrates Reverse Stress Testing across segments.
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
    rst_parameter: pl.DataFrame,
    master_scale_pd: pl.DataFrame,
    npl_ratios: dict[str, float] | None = None,
) -> dict[str, pl.DataFrame]:
    """Execute the full RST Segment pipeline."""
    from modules.rst_segment import (
        e01_xls_rst_nbmce,
        e02_xls_rst_prty_inv_dev,
        f01_rst_nbmce,
        f02_rst_prty_inv_dev,
        f03_join_nbmce,
        f04_parameter,
        f05_segment,
        f06_rst_rml,
        f07_rst_prop_invdev,
        f08_rst_bank_fi,
        f09_rst_derivative,
        f10_rst_nbmce,
        f11_rst_other,
        f12_combined,
        f13_rst_summary,
    )

    results: dict[str, pl.DataFrame] = {}

    # Extract
    logger.info("RST DAG: Extract")
    nbmce_raw = e01_xls_rst_nbmce.run(config)
    prty_raw = e02_xls_rst_prty_inv_dev.run(config)

    # Transform raw extracts
    nbmce_processed = f01_rst_nbmce.run(config, nbmce_raw)
    results["prty_processed"] = f02_rst_prty_inv_dev.run(config, prty_raw)
    results["nbmce_joined"] = f03_join_nbmce.run(config, nbmce_processed, fact_rwa)

    # Parse parameters
    logger.info("RST DAG: Parse parameters")
    params = f04_parameter.run(config, rst_parameter)

    # Segment
    logger.info("RST DAG: Segment fact table")
    segments = f05_segment.run(config, fact_rwa)

    # Stress each segment
    logger.info("RST DAG: Stress segments")
    stressed: dict[str, pl.DataFrame] = {}

    stressed["rml"] = f06_rst_rml.run(
        config, segments.get("rst_hk_rml", pl.DataFrame()), params,
    )
    stressed["prop_invdev"] = f07_rst_prop_invdev.run(
        config, segments.get("rst_prty_inv", pl.DataFrame()), params,
    )
    stressed["bank_fi"] = f08_rst_bank_fi.run(
        config, segments.get("rst_bank_fi", pl.DataFrame()), params, master_scale_pd,
    )
    stressed["derivative"] = f09_rst_derivative.run(
        config, segments.get("rst_deri", pl.DataFrame()), params,
    )
    stressed["nbmce"] = f10_rst_nbmce.run(
        config, segments.get("rst_nbmce", pl.DataFrame()), params,
    )

    # Other segments
    for seg_name in ["PASTDUE", "OTH"]:
        stressed[seg_name.lower()] = f11_rst_other.run(
            config, segments.get(f"rst_{seg_name.lower()}", pl.DataFrame()), params,
        )

    # Combine
    logger.info("RST DAG: Combine")
    combined = f12_combined.run(config, stressed)
    results["rst_combined"] = combined

    # Summary
    summary = f13_rst_summary.run(config, combined)
    results.update(summary)

    logger.info("RST DAG: Pipeline complete")
    return results
