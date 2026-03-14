"""
Combine 4-entity IW data into staging with FLAG_SRC, create CMV account-level aggregation.

Translated from Code/01.CAR_BASE/F_00_IW_TO_STG.sas (300 lines).

Key operations:
  1. Union 4-entity ac_cov datasets with FLAG_SRC tagging
  2. Aggregate CMV at account level (vi_cmv_aclevel)
  3. Union allocation detail datasets with collateral type indicators
  4. Aggregate allocation details by ACCT_ID
  5. Sort and join ICAAP info to CAR tables
  6. Build CBIC customer ID format from XLS mapping
  7. Join guarantor information from collateral tables
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)

ENTITIES = ["kw", "vc", "cf", "sz"]
ENTITY_FLAGS = {"kw": "KW", "vc": "VC", "cf": "CF", "sz": "SZ"}

# ICAAP join key columns
ICAAP_JOIN_KEYS = [
    "ENTITY", "APPL_CD", "ACCT_ID", "ORIG_PORT_CD", "PORT_CD",
    "COLL_ACCT_ID", "COLL_REC_NBR", "COLL_CHG_PRI_NBR",
]

# ICAAP columns to bring in from cap_dtl
ICAAP_KEEP_COLS = [
    "ICAAP_BUS_UNIT", "ICAAP_CCF_TENOR", "ICAAP_COLL_TYP",
    "ICAAP_COLL_TYP_DESC", "ICAAP_CNTR_TYP", "ICAAP_CNTR_TYP_DESC",
    "ICAAP_CUST_SEC_ID", "ICAAP_PROD_CD", "ICAAP_RC_TEAM_CD",
    "ICAAP_TEAM_CD", "ICAAP_TEAM_DESC",
    "BAL_OGL_ACCT", "OGL_PROD_CD", "ALCO_PROD_CD",
    "ON_OFF_IND", "RC_CD", "ELIM_LVL", "SEC_CD",
]


def _union_entities(
    datasets: dict[str, pl.DataFrame],
    view_prefix: str,
    rpt_month: str,
    drop_cols: list[str] | None = None,
) -> pl.DataFrame:
    """Union 4-entity datasets with FLAG_SRC tagging."""
    frames: list[pl.DataFrame] = []
    for entity in ENTITIES:
        key = f"vi_iambs_{entity}_{view_prefix}_{rpt_month}"
        if key in datasets:
            df = datasets[key]
            if drop_cols:
                existing_drops = [c for c in drop_cols if c in df.columns]
                if existing_drops:
                    df = df.drop(existing_drops)
            df = df.with_columns(pl.lit(ENTITY_FLAGS[entity]).alias("FLAG_SRC"))
            frames.append(df)
    if not frames:
        return pl.DataFrame()
    return pl.concat(frames, how="diagonal")


def run(
    config: Config,
    datasets: dict[str, pl.DataFrame],
) -> dict[str, pl.DataFrame]:
    """
    Execute the IW-to-staging transformation.

    Parameters
    ----------
    config : Config
    datasets : dict[str, pl.DataFrame]
        All extracted IW datasets keyed by name.

    Returns
    -------
    dict[str, pl.DataFrame]
        Staging datasets.
    """
    results: dict[str, pl.DataFrame] = {}
    rpt = config.rpt_month

    # -------------------------------------------------------------------------
    # 1. Union ac_cov (CMV) datasets — lines 3-26
    # -------------------------------------------------------------------------
    ac_cov = _union_entities(datasets, "ac_cov", rpt)
    results[f"vi_iambs_ac_cov_{rpt}"] = ac_cov

    # -------------------------------------------------------------------------
    # 2. CMV account-level aggregation — lines 28-40
    # -------------------------------------------------------------------------
    if not ac_cov.is_empty() and "ACCT_ID" in ac_cov.columns:
        cmv_aclevel = ac_cov.group_by("ACCT_ID").agg([
            pl.col("POS_AMT_HKE").sum().alias("POS_AMT_HKE"),
            pl.col("ALLOCATED_CMV_HKE").sum().alias("ALLOCATED_CMV_HKE"),
            pl.col("RESIDUAL_CMV_HKE").sum().alias("RESIDUAL_CMV_HKE"),
            pl.col("UNCOVER_AMT_HKE").sum().alias("UNCOVER_AMT_HKE"),
            (pl.col("ALLOCATED_CMV_HKE").sum() + pl.col("RESIDUAL_CMV_HKE").sum()).alias("CMV_HKE"),
        ])
        results[f"vi_cmv_aclevel_{rpt}"] = cmv_aclevel
    else:
        results[f"vi_cmv_aclevel_{rpt}"] = pl.DataFrame()

    # -------------------------------------------------------------------------
    # 3. Union allocation detail datasets with collateral indicators — lines 44-92
    # -------------------------------------------------------------------------
    alc_dtl = _union_entities(
        datasets, "alc_dtl", rpt,
        drop_cols=["COLL_REC_NBR", "COLL_CHG_PRI_NBR"],
    )
    if not alc_dtl.is_empty() and "COLL_TYP" in alc_dtl.columns:
        alc_dtl = alc_dtl.with_columns([
            pl.when(pl.col("COLL_TYP") == "TD").then(1).otherwise(None).alias("IND_COLL_TD"),
            pl.when(pl.col("COLL_TYP") == "DP").then(1).otherwise(None).alias("IND_COLL_DP"),
            pl.when(pl.col("COLL_TYP").is_in(["PY", "P004"])).then(1).otherwise(None).alias("IND_COLL_PY"),
            pl.when(pl.col("COLL_TYP") == "G1").then(1).otherwise(None).alias("IND_COLL_G1"),
            pl.when(pl.col("COLL_TYP") == "LC").then(1).otherwise(None).alias("IND_COLL_LC"),
        ])
        results[f"vi_iambs_alc_dtl_{rpt}"] = alc_dtl

        # Aggregate allocation details by ACCT_ID
        coll_types = ["TD", "DP", "PY", "G1", "LC"]
        agg_exprs: list[pl.Expr] = []

        for ctype in ["ALL"] + coll_types:
            if ctype == "ALL":
                alloc_expr = pl.col("ALLOCATED_CMV_HKE").sum().clip(lower_bound=0).alias("ALLOCATED_CMV_HKE_ALL")
                resid_expr = pl.col("RESIDUAL_CMV_HKE").sum().clip(lower_bound=0).alias("RESIDUAL_CMV_HKE_ALL")
            else:
                ind_col = f"IND_COLL_{ctype}"
                alloc_expr = (
                    (pl.col("ALLOCATED_CMV_HKE") * pl.col(ind_col).fill_null(0))
                    .sum().clip(lower_bound=0)
                    .alias(f"ALLOCATED_CMV_HKE_{ctype}")
                )
                resid_expr = (
                    (pl.col("RESIDUAL_CMV_HKE") * pl.col(ind_col).fill_null(0))
                    .sum().clip(lower_bound=0)
                    .alias(f"RESIDUAL_CMV_HKE_{ctype}")
                )
            agg_exprs.extend([alloc_expr, resid_expr])

        alc_dtl_sum = alc_dtl.group_by("ACCT_ID").agg(agg_exprs)

        # Add combined CMV columns
        for ctype in ["ALL"] + coll_types:
            alc_dtl_sum = alc_dtl_sum.with_columns(
                (pl.col(f"ALLOCATED_CMV_HKE_{ctype}") + pl.col(f"RESIDUAL_CMV_HKE_{ctype}"))
                .alias(f"CMV_HKE_{ctype}")
            )

        results[f"vi_iambs_alc_dtl_sum_{rpt}"] = alc_dtl_sum
    else:
        results[f"vi_iambs_alc_dtl_{rpt}"] = pl.DataFrame()
        results[f"vi_iambs_alc_dtl_sum_{rpt}"] = pl.DataFrame()

    # -------------------------------------------------------------------------
    # 4. Join ICAAP info to CAR tables — lines 94-158
    # -------------------------------------------------------------------------
    icaap_key = f"vi_iamic_cap_dtl_{rpt}"
    icaap_df = datasets.get(icaap_key, pl.DataFrame())

    if not icaap_df.is_empty():
        # Deduplicate ICAAP data by join keys
        valid_keys = [k for k in ICAAP_JOIN_KEYS if k in icaap_df.columns]
        if valid_keys:
            icaap_dedup = icaap_df.unique(subset=valid_keys)
        else:
            icaap_dedup = icaap_df

        for entity in ENTITIES:
            car_key = f"vi_iambs_{entity}_car_{rpt}"
            if car_key in datasets:
                car_df = datasets[car_key]
                join_keys = [k for k in ICAAP_JOIN_KEYS if k in car_df.columns and k in icaap_dedup.columns]
                keep_cols = [k for k in ICAAP_KEEP_COLS if k in icaap_dedup.columns]

                if join_keys and keep_cols:
                    icaap_subset = icaap_dedup.select(join_keys + keep_cols)
                    joined = car_df.join(icaap_subset, on=join_keys, how="left")
                    joined = joined.with_columns(
                        pl.when(pl.col(keep_cols[0]).is_not_null())
                        .then(1)
                        .otherwise(None)
                        .alias("FLAG_ICAAP")
                    )
                    results[car_key] = joined
                else:
                    results[car_key] = car_df
            else:
                logger.debug("CAR dataset not found: %s", car_key)

    # -------------------------------------------------------------------------
    # 5. Build CBIC customer ID format — lines 160-175
    # -------------------------------------------------------------------------
    cbic_key = "xls_cbic_bank_cust_id"
    cbic_df = datasets.get(cbic_key, pl.DataFrame())
    cbic_id_map: dict[str, str] = {}
    if not cbic_df.is_empty():
        if "CUST_NAME" in cbic_df.columns and "ISSUE_BANK_CUST_SEC_ID" in cbic_df.columns:
            for row in cbic_df.iter_rows(named=True):
                name = str(row.get("CUST_NAME", "")).strip()
                sec_id = str(row.get("ISSUE_BANK_CUST_SEC_ID", ""))
                if name:
                    cbic_id_map[name] = sec_id
    results["_cbic_id_map"] = pl.DataFrame({"key": list(cbic_id_map.keys()), "value": list(cbic_id_map.values())})

    # -------------------------------------------------------------------------
    # 6. Join guarantor info from collateral tables — lines 178-206
    # -------------------------------------------------------------------------
    for entity in ENTITIES:
        car_key = f"vi_iambs_{entity}_car_{rpt}"
        coll_key = f"vi_iambs_{entity}_coll_{rpt}"

        car_df = results.get(car_key, datasets.get(car_key, pl.DataFrame()))
        coll_df = datasets.get(coll_key, pl.DataFrame())

        if car_df.is_empty() or coll_df.is_empty():
            continue

        # For SZ entity, apply CBIC customer ID mapping
        if entity == "sz" and cbic_id_map and "CUST_NAME" in car_df.columns:
            car_df = car_df.with_columns(
                pl.col("CUST_NAME").cast(pl.Utf8).replace(cbic_id_map, default=None)
                .alias("ISSUE_BANK_CUST_SEC_ID")
            )

        # Extract distinct guarantor info from collateral
        guartor_cols = ["ACCT_ID", "REC_NBR", "CHG_PRI_NBR", "FAC_REF",
                        "GUARTOR_CUST_SEC_ID", "GUARTOR_NAME_1", "GUARTOR_NAME_2"]
        available_cols = [c for c in guartor_cols if c in coll_df.columns]

        if len(available_cols) >= 4:  # Need at least join keys
            guartor_df = coll_df.select(available_cols).unique()

            # Build guarantor name
            if "GUARTOR_NAME_1" in guartor_df.columns:
                name_parts = [pl.col("GUARTOR_NAME_1").cast(pl.Utf8).fill_null("")]
                if "GUARTOR_NAME_2" in guartor_df.columns:
                    name_parts.append(pl.lit(" "))
                    name_parts.append(pl.col("GUARTOR_NAME_2").cast(pl.Utf8).fill_null(""))
                guartor_df = guartor_df.with_columns(
                    pl.concat_str(name_parts).str.strip_chars().alias("GUARTOR_NAME")
                )

            # Join on collateral keys
            join_map = {
                "COLL_ACCT_ID": "ACCT_ID",
                "COLL_REC_NBR": "REC_NBR",
                "COLL_CHG_PRI_NBR": "CHG_PRI_NBR",
                "FAC_REF": "FAC_REF",
            }
            left_keys = [k for k in join_map if k in car_df.columns]
            right_keys = [join_map[k] for k in left_keys]

            if left_keys:
                keep_from_guartor = ["GUARTOR_CUST_SEC_ID", "GUARTOR_NAME"]
                keep_from_guartor = [c for c in keep_from_guartor if c in guartor_df.columns]
                if keep_from_guartor:
                    guartor_subset = guartor_df.select(right_keys + keep_from_guartor).unique()
                    car_df = car_df.join(
                        guartor_subset,
                        left_on=left_keys,
                        right_on=right_keys,
                        how="left",
                    )

        results[car_key] = car_df

    logger.info("F00 IW-to-STG: produced %d staging datasets", len(results))
    return results
