"""
Calculate stress scenarios for Bank/FI exposures.

Translated from Code/06.ST_COUNTRY_FI/M_01_BASE.sas (~50 lines).
Calculates NOTCH_ST0/ST1/ST2 -> PD -> EL, RWA for each scenario.
ST0=baseline, ST1=NOTCH+3, ST2=max(NOTCH,11).
LGD fixed at 0.45 for all scenarios.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

from lib.lookups import build_pd_format, build_rw_long_format

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)

LGD = 0.45


def run(
    config: Config,
    base_fi: pl.DataFrame,
    master_scale_pd: pl.DataFrame,
) -> pl.DataFrame:
    """
    Calculate stressed EL and RWA for Bank/FI exposures.

    Scenarios:
        ST0: Baseline (NOTCH unchanged)
        ST1: Moderate stress (NOTCH + 3)
        ST2: Severe stress (max(NOTCH, 11))

    Parameters
    ----------
    config : Config
    base_fi : pl.DataFrame
        Output from l01_base.run().
    master_scale_pd : pl.DataFrame
        Master scale PD table for notch->PD/RW lookup.

    Returns
    -------
    pl.DataFrame
        Dataset with ST0/ST1/ST2 columns for PD, RW, EAD, RWA, EL.
    """
    if base_fi.is_empty():
        logger.warning("M01 ST_FI: Empty base FI input")
        return pl.DataFrame()

    df = base_fi.clone()
    pd_map = build_pd_format(master_scale_pd) if not master_scale_pd.is_empty() else {}
    rw_map = build_rw_long_format(master_scale_pd) if not master_scale_pd.is_empty() else {}

    crm_col = "APPL_CRM_AMT_HKE" if "APPL_CRM_AMT_HKE" in df.columns else "ORIG_CRM_AMT_HKE"
    ccf_col = "CCF" if "CCF" in df.columns else None
    port_col = "PORT_CD" if "PORT_CD" in df.columns else None

    # Calculate CCF factor: CCF/100 for off-balance (B1-B9), else 1.0
    if ccf_col and port_col:
        df = df.with_columns(
            pl.when(pl.col(port_col).str.starts_with("B"))
            .then(pl.col(ccf_col).fill_null(100.0) / 100.0)
            .otherwise(pl.lit(1.0))
            .alias("t_CCF")
        )
    else:
        df = df.with_columns(pl.lit(1.0).alias("t_CCF"))

    # Scenario definitions
    scenarios = {
        "ST0": lambda n: n,  # baseline
        "ST1": lambda n: (n + 3).clip(1, 22),  # moderate: +3 notch
        "ST2": lambda n: pl.max_horizontal(n, pl.lit(11)).clip(1, 22),  # severe: floor 11
    }

    for suffix, notch_fn in scenarios.items():
        # Calculate stressed NOTCH
        if "NOTCH" in df.columns:
            if suffix == "ST0":
                df = df.with_columns(pl.col("NOTCH").alias(f"NOTCH_{suffix}"))
            elif suffix == "ST1":
                df = df.with_columns((pl.col("NOTCH") + 3).clip(1, 22).alias(f"NOTCH_{suffix}"))
            elif suffix == "ST2":
                df = df.with_columns(
                    pl.max_horizontal(pl.col("NOTCH"), pl.lit(11)).cast(pl.Int32).clip(1, 22).alias(f"NOTCH_{suffix}")
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

        # EAD = CRM * t_CCF
        if crm_col in df.columns:
            df = df.with_columns(
                (pl.col(crm_col).fill_null(0) * pl.col("t_CCF")).alias(f"EAD_{suffix}")
            )
        else:
            df = df.with_columns(pl.lit(0.0).alias(f"EAD_{suffix}"))

        # RWA = CRM * RW / 100
        if crm_col in df.columns:
            df = df.with_columns(
                (pl.col(crm_col).fill_null(0) * pl.col(f"RW_{suffix}") / 100.0).alias(f"RWA_{suffix}")
            )

        # EL = EAD * PD * LGD
        df = df.with_columns(
            (pl.col(f"EAD_{suffix}") * pl.col(f"PD_{suffix}") * LGD).alias(f"EL_{suffix}")
        )

    logger.info("M01 ST_FI: Calculated stress scenarios: %d rows", len(df))
    return df
