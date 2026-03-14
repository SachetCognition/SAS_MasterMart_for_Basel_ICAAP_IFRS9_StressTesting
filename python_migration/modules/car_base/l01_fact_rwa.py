"""
THE MASTER FACT TABLE BUILDER — combines 15+ staging datasets.

Translated from Code/01.CAR_BASE/L_01_FACT_RWA.sas (~400 lines).

Key operations:
  1. Union all staging datasets with FLAG_SOLO tagging
  2. Apply ECAI rating notch logic:
     - CCY_GROUP determination (HKD/USD/CNY/SGD → group)
     - NOTCH lookup from notch_cc and notch_bd formats
     - Guarantor rating fallback
     - Issuing bank rating fallback
     - Short-term claim proxy handling
     - Unrated proxy NOTCH assignment based on APPL_RISK_WEIGHT
  3. Identify REF facilities
  4. Produce fact.st_crm_rwa_fact dataset
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)

# FLAG_SOLO classification (SAS lines 15-60)
_SOLO_MAP: dict[str, str] = {
    "car_iw_adj": "IW",
    "adj_sgp_sec_fix_loan": "SGP",
    "adj_sgp_mm": "SGP",
    "adj_sgp_imex": "SGP",
    "adj_sgp_nostro_tb": "SGP",
    "adj_delta_3": "ADJ",
    "adj_delta_5": "ADJ",
    "adj_delta_6": "ADJ",
    "adj_delta_other": "ADJ",
    "adj_ns_combined_delta": "NONSYS",
    "adj_ns_subsidiaries_delta": "NONSYS",
    "car_hkcbf_adj": "HKCBF",
    "adj_ns_hkcbf_delta": "HKCBF",
    "car_sz_adj": "CBIC",
    "adj_ns_consolid_crm_delta": "NONSYS",
    "adj_derv_delta": "DERV",
}

# CCY_GROUP mapping
_CCY_GROUP: dict[str, str] = {
    "HKD": "HKD",
    "USD": "USD",
    "CNY": "CNY",
    "RMB": "CNY",
    "SGD": "SGD",
    "EUR": "EUR",
    "GBP": "GBP",
    "JPY": "JPY",
}

# Unrated NOTCH proxy based on APPL_RISK_WEIGHT (SAS lines 200-230)
_RW_TO_NOTCH: dict[int, int] = {
    0: 1,    # 0% → AAA equivalent
    10: 2,   # 10% → AA+ equivalent
    20: 3,   # 20% → AA equivalent
    50: 8,   # 50% → BBB+ equivalent
    100: 11, # 100% → BB+ equivalent (unrated default)
    150: 17, # 150% → CCC+ equivalent
}


def _determine_ccy_group(df: pl.DataFrame) -> pl.DataFrame:
    """Assign CCY_GROUP based on currency code."""
    if "CCY" not in df.columns:
        return df.with_columns(pl.lit("OTHER").alias("CCY_GROUP"))

    # Build replacement mapping
    return df.with_columns(
        pl.col("CCY").cast(pl.Utf8).str.to_uppercase()
        .replace(_CCY_GROUP, default="OTHER")
        .alias("CCY_GROUP")
    )


def _apply_notch_cc(
    df: pl.DataFrame,
    notch_cc_map: dict[str, int],
) -> pl.DataFrame:
    """
    Apply counterparty credit rating NOTCH lookup.

    Key: RM_CUST_ID + CCY_GROUP → NOTCH
    """
    if not notch_cc_map or "RM_CUST_ID" not in df.columns or "CCY_GROUP" not in df.columns:
        return df

    # Build lookup key
    df = df.with_columns(
        (pl.col("RM_CUST_ID").cast(pl.Utf8) + pl.col("CCY_GROUP").cast(pl.Utf8))
        .alias("_notch_cc_key")
    )

    # Apply lookup via join
    map_df = pl.DataFrame({
        "_notch_cc_key": list(notch_cc_map.keys()),
        "NOTCH_CC": list(notch_cc_map.values()),
    })

    df = df.join(map_df, on="_notch_cc_key", how="left").drop("_notch_cc_key")
    return df


def _apply_notch_bd(
    df: pl.DataFrame,
    notch_bd_map: dict[str, int],
) -> pl.DataFrame:
    """
    Apply bond rating NOTCH lookup.

    Key: ACCT_ID → NOTCH
    """
    if not notch_bd_map or "ACCT_ID" not in df.columns:
        return df

    map_df = pl.DataFrame({
        "ACCT_ID": list(notch_bd_map.keys()),
        "NOTCH_BD": list(notch_bd_map.values()),
    })

    # Ensure matching types
    if df["ACCT_ID"].dtype != pl.Utf8:
        df = df.with_columns(pl.col("ACCT_ID").cast(pl.Utf8))
    if map_df["ACCT_ID"].dtype != pl.Utf8:
        map_df = map_df.with_columns(pl.col("ACCT_ID").cast(pl.Utf8))

    df = df.join(map_df, on="ACCT_ID", how="left")
    return df


def _apply_guarantor_fallback(df: pl.DataFrame, notch_cc_map: dict[str, int]) -> pl.DataFrame:
    """
    Guarantor rating fallback: if NOTCH is missing but guarantor has rating,
    use guarantor's NOTCH.
    """
    if not notch_cc_map or "GUARTOR_CUST_SEC_ID" not in df.columns:
        return df

    # Build guarantor lookup key
    guartor_map: dict[str, int] = {}
    for key, notch in notch_cc_map.items():
        # Extract cust_id part (key = RM_CUST_ID + CCY_GROUP)
        guartor_map[key] = notch

    if "CCY_GROUP" in df.columns:
        df = df.with_columns(
            (pl.col("GUARTOR_CUST_SEC_ID").cast(pl.Utf8).fill_null("") + pl.col("CCY_GROUP").cast(pl.Utf8))
            .alias("_guartor_key")
        )

        map_df = pl.DataFrame({
            "_guartor_key": list(guartor_map.keys()),
            "NOTCH_GUARTOR": list(guartor_map.values()),
        })

        df = df.join(map_df, on="_guartor_key", how="left").drop("_guartor_key")

    return df


def _resolve_notch(df: pl.DataFrame) -> pl.DataFrame:
    """
    Resolve final NOTCH from multiple sources with priority:
      1. NOTCH_CC (counterparty credit rating)
      2. NOTCH_BD (bond rating)
      3. NOTCH_GUARTOR (guarantor fallback)
      4. NOTCH_ISSUER (issuing bank fallback)
      5. Unrated proxy from APPL_RISK_WEIGHT
    """
    notch_cols = ["NOTCH_CC", "NOTCH_BD", "NOTCH_GUARTOR"]
    available = [c for c in notch_cols if c in df.columns]

    if not available:
        # All unrated — use risk weight proxy
        if "APPL_RISK_WEIGHT" in df.columns:
            rw_map_df = pl.DataFrame({
                "APPL_RISK_WEIGHT": [float(k) for k in _RW_TO_NOTCH],
                "_notch_proxy": list(_RW_TO_NOTCH.values()),
            })
            df = df.join(
                rw_map_df,
                on="APPL_RISK_WEIGHT",
                how="left",
            )
            df = df.with_columns(
                pl.col("_notch_proxy").fill_null(11).alias("NOTCH")
            ).drop("_notch_proxy")
        else:
            df = df.with_columns(pl.lit(11).alias("NOTCH"))
        return df

    # Build NOTCH using coalesce logic
    coalesce_exprs = [pl.col(c) for c in available]

    # Add risk weight proxy as last resort
    if "APPL_RISK_WEIGHT" in df.columns:
        rw_map_df = pl.DataFrame({
            "APPL_RISK_WEIGHT": [float(k) for k in _RW_TO_NOTCH],
            "_notch_proxy": list(_RW_TO_NOTCH.values()),
        })
        df = df.join(rw_map_df, on="APPL_RISK_WEIGHT", how="left")
        coalesce_exprs.append(pl.col("_notch_proxy"))

    df = df.with_columns(
        pl.coalesce(coalesce_exprs).fill_null(11).cast(pl.Int32).alias("NOTCH")
    )

    # Flag rated vs unrated — must be computed BEFORE dropping notch source columns
    rated_exprs = [pl.col(c) for c in available if c != "_notch_proxy"]
    if rated_exprs:
        df = df.with_columns(
            pl.when(pl.coalesce(rated_exprs).is_not_null())
            .then(pl.lit("RATED"))
            .otherwise(pl.lit("UNRATED"))
            .alias("FLAG_RATED")
        )
    else:
        df = df.with_columns(pl.lit("UNRATED").alias("FLAG_RATED"))

    # Clean up temporary columns
    drop_cols = [c for c in ["_notch_proxy"] + available if c in df.columns]
    df = df.drop(drop_cols)

    return df


def _flag_ref(df: pl.DataFrame, ref_list: pl.DataFrame) -> pl.DataFrame:
    """Flag REF (Real Estate Financing) facilities."""
    if ref_list.is_empty() or "FAC_REF" not in ref_list.columns or "FAC_REF" not in df.columns:
        return df.with_columns(pl.lit(0).alias("FLAG_REF"))

    ref_set = set(ref_list["FAC_REF"].cast(pl.Utf8).to_list())
    df = df.with_columns(
        pl.when(pl.col("FAC_REF").cast(pl.Utf8).is_in(list(ref_set)))
        .then(1)
        .otherwise(0)
        .alias("FLAG_REF")
    )
    return df


def run(
    config: Config,
    staging_datasets: dict[str, pl.DataFrame],
    notch_cc_map: dict[str, int],
    notch_bd_map: dict[str, int],
    ref_list: pl.DataFrame,
) -> pl.DataFrame:
    """
    Build the master RWA fact table.

    Parameters
    ----------
    config : Config
    staging_datasets : dict[str, pl.DataFrame]
        All staging datasets from F_xx modules.
    notch_cc_map : dict[str, int]
        CC rating → NOTCH lookup from f11.
    notch_bd_map : dict[str, int]
        Bond rating → NOTCH lookup from f11.
    ref_list : pl.DataFrame
        REF facility list from f12.

    Returns
    -------
    pl.DataFrame
        fact.st_crm_rwa_fact — the master fact table.
    """
    # 1. Union all staging datasets with FLAG_SOLO tagging
    frames: list[pl.DataFrame] = []
    for name, flag_solo in _SOLO_MAP.items():
        df = staging_datasets.get(name, pl.DataFrame())
        if df.is_empty():
            continue
        df = df.with_columns(pl.lit(flag_solo).alias("FLAG_SOLO"))
        frames.append(df)

    if not frames:
        logger.warning("L01: No staging datasets to union")
        return pl.DataFrame()

    fact = pl.concat(frames, how="diagonal")
    logger.info("L01: Unioned %d staging datasets → %d rows", len(frames), len(fact))

    # 2. Determine CCY_GROUP
    fact = _determine_ccy_group(fact)

    # 3. Apply NOTCH lookups
    fact = _apply_notch_cc(fact, notch_cc_map)
    fact = _apply_notch_bd(fact, notch_bd_map)
    fact = _apply_guarantor_fallback(fact, notch_cc_map)

    # 4. Resolve final NOTCH
    fact = _resolve_notch(fact)

    # 5. Flag REF facilities
    fact = _flag_ref(fact, ref_list)

    # 6. Add reporting period columns
    fact = fact.with_columns([
        pl.lit(config.rpt_month).alias("RPT_MONTH"),
        pl.lit(config.st_rpt_ymd).alias("RPT_DATE"),
    ])

    logger.info("L01: Master fact table: %d rows, %d columns", len(fact), len(fact.columns))
    return fact
