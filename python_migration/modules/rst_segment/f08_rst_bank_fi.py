"""
RST Bank/FI stress with notch shifts.

Translated from Code/04.RST_SEGMENT/F_08_RST_BANK_FI.sas.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

from lib.lookups import build_pd_format, build_rw_long_format

if TYPE_CHECKING:
    from config.settings import Config
    from modules.rst_segment.f04_parameter import RSTParameters

logger = logging.getLogger(__name__)


def run(
    config: Config,
    bank_fi: pl.DataFrame,
    params: RSTParameters,
    master_scale_pd: pl.DataFrame,
) -> pl.DataFrame:
    """Apply RST stress to Bank/FI segment via notch shifts."""
    if bank_fi.is_empty():
        logger.warning("F08 RST: Empty Bank/FI segment")
        return bank_fi

    df = bank_fi.clone()
    pd_map = build_pd_format(master_scale_pd) if not master_scale_pd.is_empty() else {}
    rw_map = build_rw_long_format(master_scale_pd) if not master_scale_pd.is_empty() else {}
    lgd = 0.45
    crm_col = "APPL_CRM_AMT_HKE" if "APPL_CRM_AMT_HKE" in df.columns else "ORIG_CRM_AMT_HKE"

    for i in range(4):
        suffix = f"ST{i}"
        shift = params.fi_notch_shift[i]

        if "NOTCH" in df.columns:
            df = df.with_columns(
                (pl.col("NOTCH") + shift).clip(1, 22).alias(f"NOTCH_{suffix}")
            )
        else:
            df = df.with_columns(pl.lit(11).alias(f"NOTCH_{suffix}"))

        if pd_map:
            pd_entries = pl.DataFrame(
                {f"NOTCH_{suffix}": list(pd_map.keys()), f"PD_{suffix}": list(pd_map.values())}
            ).with_columns(pl.col(f"NOTCH_{suffix}").cast(pl.Int32))
            df = df.with_columns(pl.col(f"NOTCH_{suffix}").cast(pl.Int32))
            df = df.join(pd_entries, on=f"NOTCH_{suffix}", how="left")
            df = df.with_columns(pl.col(f"PD_{suffix}").fill_null(0.01))
        else:
            df = df.with_columns(pl.lit(0.01).alias(f"PD_{suffix}"))

        if rw_map:
            rw_entries = pl.DataFrame(
                {f"NOTCH_{suffix}": list(rw_map.keys()), f"RW_{suffix}": list(rw_map.values())}
            ).with_columns(pl.col(f"NOTCH_{suffix}").cast(pl.Int32))
            if f"RW_{suffix}" in df.columns:
                df = df.drop(f"RW_{suffix}")
            df = df.join(rw_entries, on=f"NOTCH_{suffix}", how="left")
            df = df.with_columns(pl.col(f"RW_{suffix}").fill_null(100.0))
        else:
            df = df.with_columns(pl.lit(100.0).alias(f"RW_{suffix}"))

        if crm_col in df.columns:
            df = df.with_columns(
                (pl.col(crm_col).fill_null(0) * pl.col(f"RW_{suffix}") / 100.0).alias(f"RWA_{suffix}")
            )
            df = df.with_columns(pl.col(crm_col).fill_null(0).alias(f"EAD_{suffix}"))
            df = df.with_columns(
                (pl.col(f"EAD_{suffix}") * pl.col(f"PD_{suffix}") * lgd).alias(f"EL_{suffix}")
            )

    logger.info("F08 RST: Bank/FI stress: %d rows", len(df))
    return df
