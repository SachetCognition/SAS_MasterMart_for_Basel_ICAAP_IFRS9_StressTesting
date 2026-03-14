"""
Combine all stressed segments into unified dataset.

Translated from Code/05.ST_SEGMENT/F_08_COMBINED.sas (~40 lines).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def run(config: Config, stressed_segments: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """
    Combine all stressed segment datasets into one unified dataset.

    Parameters
    ----------
    config : Config
    stressed_segments : dict[str, pl.DataFrame]
        All stressed segments from f03-f07.

    Returns
    -------
    pl.DataFrame
        Combined stressed dataset.
    """
    frames: list[pl.DataFrame] = []
    for name, df in stressed_segments.items():
        if not df.is_empty():
            frames.append(df)
            logger.info("F08 ST: Including segment %s: %d rows", name, len(df))

    if not frames:
        logger.warning("F08 ST: No segments to combine")
        return pl.DataFrame()

    combined = pl.concat(frames, how="diagonal")
    combined = combined.with_columns(pl.lit(config.rpt_month).alias("RPT_MONTH"))

    logger.info("F08 ST: Combined stressed dataset: %d rows", len(combined))
    return combined
