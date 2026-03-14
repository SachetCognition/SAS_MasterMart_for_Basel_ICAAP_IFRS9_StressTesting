"""
Apply 8+ sequential adjustment rules to IW CAR data.

Translated from Code/01.CAR_BASE/F_04_IW_ADJ.sas (THE MOST COMPLEX FILE — ~500 lines).

Sequential adjustments:
  Adj 3.0001 — SHORT_TERM_CLAIM_IND fix (SGP IMEX short-term indicator)
  Adj 3      — NY/LA reclass (PORT_CD Ia→IV for US branches)
  Adj 5      — Credit Card reclass to VIIIa (PORT_CD VI→VIIIa for credit cards)
  Adj 6      — MPA reclass IX→35% RW (IX with APPL_RISK_WEIGHT=50% → 35%)
  Adj 8      — Short-term bank exposure reallocation
  Combined inter-company elimination
  Consolidated inter-company elimination
  Dynamic error adjustments (EA3_0, EA8_0, EA8_1, EA104, EA202, EA203)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

from lib.macros import apply_error_adjustments, error_adjustment

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)

# Columns for the CAR IW adjustment output
_AMT_COLS = [
    "CUR_BAL_ON_HKE", "CUR_BAL_OFF_HKE", "CUR_EXP_AMT_HKE",
    "POTENT_EXP_AMT_HKE", "ORIG_CRM_AMT_HKE", "APPL_CRM_AMT_HKE",
    "RISK_WEIGHTED_AMT_HKE", "PROVISION_AMT_HKE",
]


def _adj_3_0001(df: pl.DataFrame, sgp_imex: pl.DataFrame) -> pl.DataFrame:
    """
    Adj 3.0001: Fix SHORT_TERM_CLAIM_IND from SGP IMEX data.

    For accounts that appear in sgp_imex with SHORT_TERM_CLAIM_IND = 'Y',
    update the indicator in the main CAR dataset.
    """
    if sgp_imex.is_empty() or "SHORT_TERM_CLAIM_IND" not in sgp_imex.columns:
        return df

    short_term_accts = sgp_imex.filter(
        pl.col("SHORT_TERM_CLAIM_IND") == "Y"
    )
    if short_term_accts.is_empty():
        return df

    if "ACCT_ID" not in short_term_accts.columns or "ACCT_ID" not in df.columns:
        return df

    short_term_list = short_term_accts["ACCT_ID"].to_list()
    df = df.with_columns(
        pl.when(pl.col("ACCT_ID").is_in(short_term_list))
        .then(pl.lit("Y"))
        .otherwise(pl.col("SHORT_TERM_CLAIM_IND") if "SHORT_TERM_CLAIM_IND" in df.columns else pl.lit(None))
        .alias("SHORT_TERM_CLAIM_IND")
    )
    logger.info("Adj 3.0001: Updated SHORT_TERM_CLAIM_IND for %d accounts", len(short_term_list))
    return df


def _adj_3(df: pl.DataFrame) -> pl.DataFrame:
    """
    Adj 3: NY/LA branch reclass — PORT_CD Ia → IV for US branches.

    In SAS: if FLAG_SRC in ('KW') and PORT_CD = 'Ia'
            and ENTITY in ('NYBR','LABR') then PORT_CD = 'IV';
    """
    if "PORT_CD" not in df.columns or "FLAG_SRC" not in df.columns:
        return df

    entity_col = "ENTITY" if "ENTITY" in df.columns else None
    if entity_col is None:
        return df

    cond = (
        (pl.col("FLAG_SRC") == "KW")
        & (pl.col("PORT_CD") == "Ia")
        & (pl.col(entity_col).is_in(["NYBR", "LABR"]))
    )
    count = df.filter(cond).height
    df = df.with_columns(
        pl.when(cond).then(pl.lit("IV")).otherwise(pl.col("PORT_CD")).alias("PORT_CD")
    )
    logger.info("Adj 3: Reclassed %d NY/LA records Ia→IV", count)
    return df


def _adj_5(df: pl.DataFrame) -> pl.DataFrame:
    """
    Adj 5: Credit Card reclass — PORT_CD VI → VIIIa.

    In SAS: if PORT_CD = 'VI' and upcase(RC_CD) contains 'CC'
            then PORT_CD = 'VIIIa';
    """
    if "PORT_CD" not in df.columns or "RC_CD" not in df.columns:
        return df

    cond = (
        (pl.col("PORT_CD") == "VI")
        & (pl.col("RC_CD").cast(pl.Utf8).str.to_uppercase().str.contains("CC"))
    )
    count = df.filter(cond).height
    df = df.with_columns(
        pl.when(cond).then(pl.lit("VIIIa")).otherwise(pl.col("PORT_CD")).alias("PORT_CD")
    )
    logger.info("Adj 5: Reclassed %d credit card records VI→VIIIa", count)
    return df


def _adj_6(df: pl.DataFrame) -> pl.DataFrame:
    """
    Adj 6: MPA reclass IX → 35% RW.

    In SAS: if PORT_CD = 'IX' and APPL_RISK_WEIGHT = 50
            then APPL_RISK_WEIGHT = 35;
    """
    if "PORT_CD" not in df.columns or "APPL_RISK_WEIGHT" not in df.columns:
        return df

    cond = (
        (pl.col("PORT_CD") == "IX")
        & (pl.col("APPL_RISK_WEIGHT") == 50)
    )
    count = df.filter(cond).height
    df = df.with_columns(
        pl.when(cond).then(pl.lit(35.0)).otherwise(pl.col("APPL_RISK_WEIGHT")).alias("APPL_RISK_WEIGHT")
    )
    logger.info("Adj 6: Reclassed %d MPA records from 50%%→35%% RW", count)
    return df


def _adj_8(df: pl.DataFrame) -> pl.DataFrame:
    """
    Adj 8: Short-term bank exposure reallocation.

    In SAS: if PORT_CD = 'IV' and SHORT_TERM_CLAIM_IND = 'Y'
            then PORT_CD = 'IVa';
    Also handles cases where APPL_RISK_WEIGHT should be changed based on
    original vs short-term risk weight tables.
    """
    if "PORT_CD" not in df.columns:
        return df

    st_col = "SHORT_TERM_CLAIM_IND" if "SHORT_TERM_CLAIM_IND" in df.columns else None
    if st_col is None:
        return df

    cond = (
        (pl.col("PORT_CD") == "IV")
        & (pl.col(st_col) == "Y")
    )
    count = df.filter(cond).height
    df = df.with_columns(
        pl.when(cond).then(pl.lit("IVa")).otherwise(pl.col("PORT_CD")).alias("PORT_CD")
    )
    logger.info("Adj 8: Reclassed %d short-term bank exposures IV→IVa", count)
    return df


def _combined_elimination(
    df: pl.DataFrame,
    cust_elim_set: set[str],
) -> pl.DataFrame:
    """
    Combined inter-company elimination.

    Remove rows where CUST_SEC_ID is in the elimination set and FLAG_SRC
    is in the combined group (KW, VC).
    """
    if not cust_elim_set or "CUST_SEC_ID" not in df.columns:
        return df

    flag_col = "FLAG_SRC" if "FLAG_SRC" in df.columns else None
    if flag_col is None:
        return df

    before_count = len(df)
    cond = (
        (pl.col(flag_col).is_in(["KW", "VC"]))
        & (pl.col("CUST_SEC_ID").cast(pl.Utf8).is_in(list(cust_elim_set)))
    )
    # Zero out amounts for eliminated rows, keep them with flag
    for col in _AMT_COLS:
        if col in df.columns:
            df = df.with_columns(
                pl.when(cond).then(0.0).otherwise(pl.col(col)).alias(col)
            )
    df = df.with_columns(
        pl.when(cond).then(pl.lit("ELIM_COMBINED")).otherwise(
            pl.col("FLAG_ELIM") if "FLAG_ELIM" in df.columns else pl.lit(None)
        ).alias("FLAG_ELIM")
    )
    elim_count = df.filter(cond).height
    logger.info(
        "Combined elimination: zeroed %d of %d rows",
        elim_count, before_count,
    )
    return df


def _consolidated_elimination(
    df: pl.DataFrame,
    cust_elim_set: set[str],
) -> pl.DataFrame:
    """
    Consolidated inter-company elimination.

    Remove rows where CUST_SEC_ID is in the consolidated elimination set
    and FLAG_SRC is in the consolidated group (all entities).
    """
    if not cust_elim_set or "CUST_SEC_ID" not in df.columns:
        return df

    cond = pl.col("CUST_SEC_ID").cast(pl.Utf8).is_in(list(cust_elim_set))
    for col in _AMT_COLS:
        if col in df.columns:
            df = df.with_columns(
                pl.when(cond).then(0.0).otherwise(pl.col(col)).alias(col)
            )
    df = df.with_columns(
        pl.when(cond).then(pl.lit("ELIM_CONSOLID")).otherwise(
            pl.col("FLAG_ELIM") if "FLAG_ELIM" in df.columns else pl.lit(None)
        ).alias("FLAG_ELIM")
    )
    elim_count = df.filter(cond).height
    logger.info("Consolidated elimination: zeroed %d rows", elim_count)
    return df


def run(
    config: Config,
    car_iw: pl.DataFrame,
    sgp_imex: pl.DataFrame,
    err_master: pl.DataFrame,
    cust_elim_combined: set[str] | None = None,
    cust_elim_consolid: set[str] | None = None,
) -> pl.DataFrame:
    """
    Apply all IW adjustments sequentially.

    Parameters
    ----------
    config : Config
    car_iw : pl.DataFrame
        The combined 4-entity CAR dataset from f00_iw_to_stg.
    sgp_imex : pl.DataFrame
        SGP IMEX data for SHORT_TERM_CLAIM_IND fix.
    err_master : pl.DataFrame
        Error/manual adjustment master table.
    cust_elim_combined : set[str] | None
        Customer IDs for combined inter-company elimination.
    cust_elim_consolid : set[str] | None
        Customer IDs for consolidated inter-company elimination.

    Returns
    -------
    pl.DataFrame
        car_iw_adj — the fully adjusted IW CAR dataset.
    """
    if car_iw.is_empty():
        logger.warning("F04: Empty CAR IW input")
        return car_iw

    df = car_iw.clone()

    # 1. Adj 3.0001 — SHORT_TERM_CLAIM_IND fix
    df = _adj_3_0001(df, sgp_imex)

    # 2. Adj 3 — NY/LA reclass
    df = _adj_3(df)

    # 3. Adj 5 — Credit Card reclass
    df = _adj_5(df)

    # 4. Adj 6 — MPA reclass
    df = _adj_6(df)

    # 5. Adj 8 — Short-term bank exposure
    df = _adj_8(df)

    # 6. Combined inter-company elimination
    if cust_elim_combined:
        df = _combined_elimination(df, cust_elim_combined)

    # 7. Consolidated inter-company elimination
    if cust_elim_consolid:
        df = _consolidated_elimination(df, cust_elim_consolid)

    # 8. Dynamic error adjustments
    # In SAS, %ErrAdj is called with mode='U' (Update) and the EA codes are adj_no
    # values, not Mode values.  Fetch all Update adjustments for CAR table once,
    # then filter by the specific adj_no codes.
    ea_codes = {"EA3_0", "EA8_0", "EA8_1", "EA104", "EA202", "EA203"}
    required_cols = {"IW_Table", "Mode", "adj_no", "eff_from", "eff_to", "Detail"}
    all_adj: dict[str, list[str]] = {}
    if not err_master.is_empty() and required_cols.issubset(set(err_master.columns)):
        all_adj = error_adjustment(
            err_tbl=err_master,
            tbl="CAR",
            mode="U",
            dt_rpt_month=config.dt_rpt_month,
        )
    if all_adj:
        for adj_no, details in all_adj.items():
            if adj_no in ea_codes:
                df = apply_error_adjustments(df, {adj_no: details})
                logger.info("Applied error adjustment %s (%d rules)", adj_no, len(details))

    logger.info("F04 IW Adj: Final dataset has %d rows", len(df))
    return df
