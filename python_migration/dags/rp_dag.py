"""
RP Segment pipeline DAG orchestrator.

Orchestrates Regulatory Purpose stress testing across segments.
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
    rp_parameter: pl.DataFrame,
    master_scale_pd: pl.DataFrame,
    npl_ratios: dict[str, float] | None = None,
) -> dict[str, pl.DataFrame]:
    """Execute the full RP Segment pipeline."""
    from modules.rp_segment import (
        f04_parameter,
        f05_segment,
        f06_rp_rml,
        f07_rp_prop_invdev,
        f08_rp_bank_fi,
        f09_rp_derivative,
        f10_rp_nbmce,
        f11_rp_other,
        f12_combined,
        f13_rp_summary,
    )

    results: dict[str, pl.DataFrame] = {}

    # Parse parameters
    logger.info("RP DAG: Parse parameters")
    params = f04_parameter.run(config, rp_parameter)

    # Segment
    logger.info("RP DAG: Segment fact table")
    segments = f05_segment.run(config, fact_rwa)

    # Stress each segment
    logger.info("RP DAG: Stress segments")
    stressed: dict[str, pl.DataFrame] = {}

    stressed["rml"] = f06_rp_rml.run(
        config, segments.get("HK_RML", pl.DataFrame()), params,
    )
    stressed["prop_invdev"] = f07_rp_prop_invdev.run(
        config, segments.get("PRTY_INV", pl.DataFrame()), params,
    )
    stressed["bank_fi"] = f08_rp_bank_fi.run(
        config, segments.get("BANK_FI", pl.DataFrame()), params, master_scale_pd,
    )
    stressed["derivative"] = f09_rp_derivative.run(
        config, segments.get("DERI", pl.DataFrame()), params,
    )
    stressed["nbmce"] = f10_rp_nbmce.run(
        config, segments.get("NBMCE", pl.DataFrame()), params,
    )

    # Other segments
    for seg_name in ["PASTDUE", "OTH"]:
        stressed[seg_name.lower()] = f11_rp_other.run(
            config, segments.get(seg_name, pl.DataFrame()), params,
        )

    # Combine
    logger.info("RP DAG: Combine")
    combined = f12_combined.run(config, stressed)
    results["rp_combined"] = combined

    # Summary
    summary = f13_rp_summary.run(config, combined)
    results.update(summary)

    logger.info("RP DAG: Pipeline complete")
    return results
