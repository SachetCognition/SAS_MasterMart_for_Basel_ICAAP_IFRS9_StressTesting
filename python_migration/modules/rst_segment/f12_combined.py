"""
Combine all RST stressed segments.

Translated from Code/04.RST_SEGMENT/F_12_COMBINED.sas.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(config: Config, stressed_segments: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Combine all RST stressed segment datasets into unified dataset."""
    frames: list[pl.DataFrame] = []
    for name, df in stressed_segments.items():
        if not df.is_empty():
            frames.append(df)
            logger.info("F12 RST: Including segment %s: %d rows", name, len(df))

    if not frames:
        logger.warning("F12 RST: No segments to combine")
        return pl.DataFrame()

    combined = pl.concat(frames, how="diagonal")
    combined = combined.with_columns(pl.lit(config.rpt_month).alias("RPT_MONTH"))
    logger.info("F12 RST: Combined RST: %d rows", len(combined))
    return combined
