"""
Combine all RP stressed segments.

Translated from Code/90.RP_SEGMENT/F_12_COMBINED.sas.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(config: Config, stressed_segments: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Combine all RP stressed segment datasets into unified dataset."""
    frames: list[pl.DataFrame] = []
    for name, df in stressed_segments.items():
        if not df.is_empty():
            frames.append(df)
            logger.info("F12 RP: Including segment %s: %d rows", name, len(df))

    if not frames:
        logger.warning("F12 RP: No segments to combine")
        return pl.DataFrame()

    combined = pl.concat(frames, how="diagonal")
    combined = combined.with_columns(pl.lit(config.rpt_month).alias("RPT_MONTH"))
    logger.info("F12 RP: Combined RP: %d rows", len(combined))
    return combined
