"""
RP Bank/FI stress with notch shifts.

Translated from Code/90.RP_SEGMENT/F_08_RP_BANK_FI.sas (~80 lines).
LGD fixed at 0.45 for all stress scenarios.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

from lib.lookups import build_pd_format, build_rw_long_format

if TYPE_CHECKING:
    from config.settings import Config
    from modules.rp_segment.f04_parameter import RPParameters

logger = logging.getLogger(__name__)

LGD = 0.45


def run(
    config: Config,
    bank_fi: pl.DataFrame,
    params: RPParameters,
    master_scale_pd: pl.DataFrame,
) -> pl.DataFrame:
    """Apply RP stress to Bank/FI segment via notch shifts."""
    if bank_fi.is_empty():
        logger.warning("F08 RP: Empty Bank/FI segment")
        return bank_fi

    df = bank_fi.clone()
    pd_map = build_pd_format(master_scale_pd) if not master_scale_pd.is_empty() else {}
    rw_map = build_rw_long_format(master_scale_pd) if not master_scale_pd.is_empty() else {}
    crm_col = "APPL_CRM_AMT_HKE" if "APPL_CRM_AMT_HKE" in df.columns else "ORIG_CRM_AMT_HKE"
    ccf_col = "CCF" if "CCF" in df.columns else None
    port_col = "PORT_CD" if "PORT_CD" in df.columns else None

    # t_CCF: CCF/100 for off-balance (B ports), else 1.0
    if ccf_col and port_col:
        df = df.with_columns(
            pl.when(pl.col(port_col).str.starts_with("B"))
            .then(pl.col(ccf_col).fill_null(100.0) / 100.0)
            .otherwise(pl.lit(1.0))
            .alias("t_CCF")
        )
    else:
        df = df.with_columns(pl.lit(1.0).alias("t_CCF"))

    for i in range(4):
        suffix = f"ST{i}"
        shift = params.fi_notch_shift[i]

        # Stressed NOTCH
        if "NOTCH" in df.columns:
            df = df.with_columns(
                (pl.col("NOTCH") + shift).clip(1, 22).alias(f"NOTCH_{suffix}")
            )
        else:
            df = df.with_columns(pl.lit(11).alias(f"NOTCH_{suffix}"))

        # PD lookup
        if pd_map:
            pd_entries = pl.DataFrame(
                {f"NOTCH_{suffix}": list(pd_map.keys()), f"PD_{suffix}": list(pd_map.values())}
            ).with_columns(pl.col(f"NOTCH_{suffix}").cast(pl.Int32))
            df = df.with_columns(pl.col(f"NOTCH_{suffix}").cast(pl.Int32))
            df = df.join(pd_entries, on=f"NOTCH_{suffix}", how="left")
            df = df.with_columns(pl.col(f"PD_{suffix}").fill_null(0.01))
        else:
            df = df.with_columns(pl.lit(0.01).alias(f"PD_{suffix}"))

        # RW lookup
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

        # EAD, RWA, EL
        if crm_col in df.columns:
            df = df.with_columns(
                (pl.col(crm_col).fill_null(0) * pl.col("t_CCF")).alias(f"EAD_{suffix}")
            )
            df = df.with_columns(
                (pl.col(crm_col).fill_null(0) * pl.col(f"RW_{suffix}") / 100.0).alias(f"RWA_{suffix}")
            )
            df = df.with_columns(
                (pl.col(f"EAD_{suffix}") * pl.col(f"PD_{suffix}") * LGD).alias(f"EL_{suffix}")
            )

    logger.info("F08 RP: Bank/FI stress: %d rows", len(df))
    return df
