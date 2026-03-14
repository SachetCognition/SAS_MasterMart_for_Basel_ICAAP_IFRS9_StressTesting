"""
Bank/FI stress with notch shifts.

Translated from Code/05.ST_SEGMENT/F_03_ST_BANK_FI.sas (~80 lines).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

from lib.lookups import build_pd_format, build_rw_long_format, build_rw_short_format

if TYPE_CHECKING:
    from config.settings import Config
    from modules.st_segment.f01_parameter import StressParameters

logger = logging.getLogger(__name__)


def run(
    config: Config,
    bank_fi: pl.DataFrame,
    params: StressParameters,
    master_scale_pd: pl.DataFrame,
) -> pl.DataFrame:
    """
    Apply stress to Bank/FI segment via notch shifts.

    For each scenario ST0-ST3:
      - NOTCH_STi = NOTCH + fi_notch_shift[i]
      - PD_STi = pd_format(NOTCH_STi)
      - RW_STi = rw_format(NOTCH_STi)
      - RWA_STi = CRM * RW_STi / 100
      - EL_STi = EAD * PD_STi * LGD (LGD=0.45)

    Parameters
    ----------
    config : Config
    bank_fi : pl.DataFrame
        Bank/FI segment from f02_segment.
    params : StressParameters
    master_scale_pd : pl.DataFrame
        Master scale for PD/RW lookup.

    Returns
    -------
    pl.DataFrame
        Stressed Bank/FI dataset with ST0-ST3 columns.
    """
    if bank_fi.is_empty():
        logger.warning("F03 ST: Empty Bank/FI segment")
        return bank_fi

    df = bank_fi.clone()

    # Build lookup dicts
    has_pd = not master_scale_pd.is_empty()
    pd_map = build_pd_format(master_scale_pd) if has_pd else {}
    rw_long_map = build_rw_long_format(master_scale_pd) if has_pd else {}
    _ = build_rw_short_format(master_scale_pd) if has_pd else {}  # reserved for short-term

    lgd = 0.45

    # Determine CRM and EAD columns
    crm_col = "APPL_CRM_AMT_HKE" if "APPL_CRM_AMT_HKE" in df.columns else "ORIG_CRM_AMT_HKE"

    # CCF logic: for off-balance (PORT_CD starts with B), use CCF/100, else 1.0
    if "CCF" in df.columns and "PORT_CD" in df.columns:
        df = df.with_columns(
            pl.when(pl.col("PORT_CD").cast(pl.Utf8).str.starts_with("B"))
            .then(pl.col("CCF").fill_null(100.0) / 100.0)
            .otherwise(1.0)
            .alias("t_CCF")
        )
    else:
        df = df.with_columns(pl.lit(1.0).alias("t_CCF"))

    # Apply 4 scenarios
    for i in range(4):
        suffix = f"ST{i}"
        shift = params.fi_notch_shift[i]

        # NOTCH_STi = NOTCH + shift, clamped to [1, 22]
        if "NOTCH" in df.columns:
            df = df.with_columns(
                (pl.col("NOTCH") + shift).clip(1, 22).alias(f"NOTCH_{suffix}")
            )
        else:
            df = df.with_columns(pl.lit(11).alias(f"NOTCH_{suffix}"))

        # PD_STi via lookup
        if pd_map:
            pd_map_df = pl.DataFrame({
                f"NOTCH_{suffix}": list(pd_map.keys()),
                f"PD_{suffix}": list(pd_map.values()),
            }).with_columns(pl.col(f"NOTCH_{suffix}").cast(pl.Int32))

            df = df.with_columns(pl.col(f"NOTCH_{suffix}").cast(pl.Int32))
            df = df.join(pd_map_df, on=f"NOTCH_{suffix}", how="left")
            df = df.with_columns(pl.col(f"PD_{suffix}").fill_null(0.01))
        else:
            df = df.with_columns(pl.lit(0.01).alias(f"PD_{suffix}"))

        # RW_STi via lookup (use long-term by default)
        if rw_long_map:
            rw_map_df = pl.DataFrame({
                f"NOTCH_{suffix}": list(rw_long_map.keys()),
                f"RW_{suffix}": list(rw_long_map.values()),
            }).with_columns(pl.col(f"NOTCH_{suffix}").cast(pl.Int32))

            # Drop existing RW column if present from previous join
            if f"RW_{suffix}" in df.columns:
                df = df.drop(f"RW_{suffix}")
            df = df.join(rw_map_df, on=f"NOTCH_{suffix}", how="left")
            df = df.with_columns(pl.col(f"RW_{suffix}").fill_null(100.0))
        else:
            df = df.with_columns(pl.lit(100.0).alias(f"RW_{suffix}"))

        # RWA_STi = CRM * RW / 100
        if crm_col in df.columns:
            df = df.with_columns(
                (pl.col(crm_col).fill_null(0) * pl.col(f"RW_{suffix}") / 100.0)
                .alias(f"RWA_{suffix}")
            )

        # EAD_STi = CRM * t_CCF
        if crm_col in df.columns:
            df = df.with_columns(
                (pl.col(crm_col).fill_null(0) * pl.col("t_CCF"))
                .alias(f"EAD_{suffix}")
            )

        # EL_STi = EAD * PD * LGD
        df = df.with_columns(
            (pl.col(f"EAD_{suffix}") * pl.col(f"PD_{suffix}") * lgd)
            .alias(f"EL_{suffix}")
        )

    logger.info("F03 ST: Bank/FI stress: %d rows, 4 scenarios", len(df))
    return df
