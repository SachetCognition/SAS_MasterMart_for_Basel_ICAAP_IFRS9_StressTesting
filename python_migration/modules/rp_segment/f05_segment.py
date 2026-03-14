"""
Segment fact table for RP processing.

Translated from Code/90.RP_SEGMENT/F_05_SEGMENT.sas (~30 lines).
Routes exposures to 7 staging tables:
HK_RML, PRTY_INV, BANK_FI, DERI, NBMCE, PASTDUE, OTH.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)

_RP_SEGMENTS: dict[str, list[str]] = {
    "HK_RML": ["IX"],
    "PRTY_INV": [],
    "BANK_FI": ["IV", "IVa", "V"],
    "DERI": ["B14", "B15", "B16", "B17", "B18"],
    "NBMCE": [],
    "PASTDUE": ["X"],
    "OTH": [],
}


def run(config: Config, fact_rwa: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """
    Segment the fact table into RP processing groups.

    Returns dict mapping segment name -> DataFrame.
    """
    results: dict[str, pl.DataFrame] = {}

    if fact_rwa.is_empty():
        for seg in _RP_SEGMENTS:
            results[f"rp_{seg.lower()}"] = pl.DataFrame()
        return results

    port_col = "PORT_CD" if "PORT_CD" in fact_rwa.columns else None

    for seg_name, port_cds in _RP_SEGMENTS.items():
        if seg_name == "OTH":
            continue

        if port_cds and port_col:
            mask = fact_rwa[port_col].is_in(port_cds)
            # Special: HK_RML excludes CBIC
            if seg_name == "HK_RML" and "FILE_SRC" in fact_rwa.columns:
                mask = mask & (fact_rwa["FILE_SRC"] != "CBIC")
            seg_df = fact_rwa.filter(mask)
        elif seg_name == "PRTY_INV" and "IND_PROPERTY_INV_n_DEV" in fact_rwa.columns:
            seg_df = fact_rwa.filter(pl.col("IND_PROPERTY_INV_n_DEV") == 1)
        elif seg_name == "NBMCE" and "IND_NBMCE_GRP" in fact_rwa.columns:
            nbmce_mask = pl.col("IND_NBMCE_GRP") == 1
            if "IND_AFS" in fact_rwa.columns:
                nbmce_mask = nbmce_mask & (pl.col("IND_AFS") != 1)
            seg_df = fact_rwa.filter(nbmce_mask)
        else:
            seg_df = pl.DataFrame()

        seg_df = seg_df.with_columns(pl.lit(seg_name).alias("RP_SEGMENT"))
        results[f"rp_{seg_name.lower()}"] = seg_df
        logger.info("F05 RP: Segment %s: %d rows", seg_name, len(seg_df))

    # OTH: everything not assigned to other segments
    all_assigned = set()
    for seg_name, port_cds in _RP_SEGMENTS.items():
        if seg_name != "OTH":
            all_assigned.update(port_cds)

    if port_col:
        oth_mask = ~fact_rwa[port_col].is_in(list(all_assigned))
        if "IND_PROPERTY_INV_n_DEV" in fact_rwa.columns:
            oth_mask = oth_mask & (fact_rwa["IND_PROPERTY_INV_n_DEV"] != 1)
        if "IND_NBMCE_GRP" in fact_rwa.columns:
            oth_mask = oth_mask & (fact_rwa["IND_NBMCE_GRP"] != 1)
        # Add back CBIC records with PORT_CD='IX' that were excluded from HK_RML
        # but also excluded from OTH because 'IX' is in all_assigned.
        if "FILE_SRC" in fact_rwa.columns:
            cbic_ix_mask = (fact_rwa[port_col] == "IX") & (fact_rwa["FILE_SRC"] == "CBIC")
            oth_mask = oth_mask | cbic_ix_mask
        oth_df = fact_rwa.filter(oth_mask)
    else:
        oth_df = pl.DataFrame()

    oth_df = oth_df.with_columns(pl.lit("OTH").alias("RP_SEGMENT")) if not oth_df.is_empty() else oth_df
    results["rp_oth"] = oth_df
    logger.info("F05 RP: Segment OTH: %d rows", len(oth_df))

    return results
