"""
Segment fact table for RST processing.

Translated from Code/04.RST_SEGMENT/F_05_SEGMENT.sas.
Routes exposures to RST-specific staging tables.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config
logger = logging.getLogger(__name__)

_RST_SEGMENTS = {
    "HK_RML": ["IX"],
    "PRTY_INV": [],
    "BANK_FI": ["IV", "IVa", "V"],
    "DERI": ["B14", "B15", "B16", "B17", "B18"],
    "NBMCE": [],
    "PASTDUE": ["X"],
    "OTH": [],
}

def run(config: Config, fact_rwa: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """Segment the fact table into RST processing groups."""
    results: dict[str, pl.DataFrame] = {}
    if fact_rwa.is_empty():
        for seg in _RST_SEGMENTS:
            results[f"rst_{seg.lower()}"] = pl.DataFrame()
        return results
    port_col = "PORT_CD" if "PORT_CD" in fact_rwa.columns else None
    for seg_name, port_cds in _RST_SEGMENTS.items():
        if port_cds and port_col:
            seg_df = fact_rwa.filter(pl.col(port_col).is_in(port_cds))
        elif seg_name == "PRTY_INV" and "IND_PROPERTY_INV_n_DEV" in fact_rwa.columns:
            seg_df = fact_rwa.filter(pl.col("IND_PROPERTY_INV_n_DEV") == 1)
        elif seg_name == "NBMCE" and "IND_NBMCE_GRP" in fact_rwa.columns:
            seg_df = fact_rwa.filter((pl.col("IND_NBMCE_GRP") == 1))
        elif seg_name == "OTH":
            assigned = set()
            for _, pcs in _RST_SEGMENTS.items():
                assigned.update(pcs)
            if port_col:
                seg_df = fact_rwa.filter(~pl.col(port_col).is_in(list(assigned)))
            else:
                seg_df = fact_rwa
            # Exclude records already assigned to indicator-based segments
            # (PRTY_INV and NBMCE) to prevent double-counting
            if "IND_PROPERTY_INV_n_DEV" in seg_df.columns:
                seg_df = seg_df.filter(pl.col("IND_PROPERTY_INV_n_DEV") != 1)
            if "IND_NBMCE_GRP" in seg_df.columns:
                seg_df = seg_df.filter(pl.col("IND_NBMCE_GRP") != 1)
        else:
            seg_df = pl.DataFrame()
        if not seg_df.is_empty():
            seg_df = seg_df.with_columns(pl.lit(seg_name).alias("RST_SEGMENT"))
        results[f"rst_{seg_name.lower()}"] = seg_df
        logger.info("F05 RST: Segment %s: %d rows", seg_name, len(seg_df))
    return results
