"""
Centralized PROC FORMAT lookups — translated from across the SAS codebase.

All static and dynamic lookups that were originally defined as SAS PROC FORMAT
value statements are consolidated here.

Static lookups (hardcoded):
  - PORTCD_MAP          (L_02_FACT_ICAAP_FORMAT.sas lines 1-18)
  - BUSUNIT_MAP         (L_02_FACT_ICAAP_FORMAT.sas lines 22-35)
  - PORT_RW_MAP         (S_01_ONBAL_CHECKING.sas lines 1-76)
  - SP_RATE_MAP         (notch -> S&P rating strings)

Dynamic lookups (built at runtime from data):
  - build_notch_cc_lookup()   (F_11_CCP_BONDS_RATING.sas lines 131-152)
  - build_notch_bd_lookup()   (F_11_CCP_BONDS_RATING.sas lines 158-174)
  - build_pd_format()         (M_01_BASE.sas lines 1-20)
  - build_rw_long_format()    (M_01_BASE.sas)
  - build_rw_short_format()   (M_01_BASE.sas)
  - build_cust_elim_format()  (L_01_BASE.sas lines 7-17)
"""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)


# =============================================================================
# STATIC LOOKUPS
# =============================================================================

# ---------------------------------------------------------------------------
# PORTCD_MAP — from L_02_FACT_ICAAP_FORMAT.sas lines 1-18
# Maps portfolio codes to descriptive categories.
# SAS: proc format; value $portcd ...
# ---------------------------------------------------------------------------
PORTCD_MAP: dict[str, str] = {
    "Ia": "01. Sovereign",
    "Ib": "01. Sovereign",
    "Ic": "01. Sovereign",
    "Id": "01. Sovereign",
    "IIa": "02. PSE",
    "IIb": "02. PSE",
    "IIc": "02. PSE",
    "III": "03. MDB",
    "IV": "04. Bank",
    "V": "05. Securities",
    "VI": "06. Corporate",
    "VIIa": "07. CIS",
    "VIIb": "07. CIS",
    "VIIIa": "08. Retail-Other",
    "VIIIb": "08. Retail-Other",
    "IX": "09. RML",
    "X": "10. Past Due",
    "XI": "11. Other",
    "XII": "12. Cash",
}
# Default for any unmapped code
PORTCD_DEFAULT = "99. ###"

# ---------------------------------------------------------------------------
# BUSUNIT_MAP — from L_02_FACT_ICAAP_FORMAT.sas lines 22-35
# Maps business unit codes to descriptive names.
# SAS: proc format; value $busunit ...
# ---------------------------------------------------------------------------
BUSUNIT_MAP: dict[str, str] = {
    "CBG": "1.0 WBG",
    "WBG": "1.0 WBG",
    "WBG-REF": "1.1 WBG-REF",
    "IBG": "2.0 IBG",
    "IBG-SGP": "2.1 IBG-SGP",
    "IBG-SGP/MAS": "2.2 IBG-SGP/MAS",
    "CBIC": "3.0 CBIC",
    "BB": "4.0 BB",
    "CTU": "5.0 CTU",
    "ORR": "6.0 ORR",
    "OFD": "7.0 OFD",
    "RAM": "8.0 RAM",
    "CONSOL ADJ": "9.0 CONSOL ADJ",
}
BUSUNIT_DEFAULT = "99. ###"

# ---------------------------------------------------------------------------
# PORT_RW_MAP — from S_01_ONBAL_CHECKING.sas lines 1-76
# Maps portfolio + risk weight combinations to validation codes.
# SAS: proc format; value $port_rw ...
# ---------------------------------------------------------------------------
PORT_RW_MAP: dict[str, int] = {
    "Ia_0": 1,
    "Ib_0": 2,
    "Ib_10": 3,
    "Ib_20": 4,
    "Ib_50": 5,
    "Ib_100": 6,
    "Ib_150": 7,
    "Ic_0": 8,
    "Ic_20": 9,
    "Ic_50": 10,
    "Ic_100": 11,
    "Ic_150": 12,
    "Id_100": 13,
    "IIa_0": 14,
    "IIa_20": 15,
    "IIa_50": 16,
    "IIa_100": 17,
    "IIb_20": 18,
    "IIb_50": 19,
    "IIb_100": 20,
    "IIb_150": 21,
    "IIc_20": 22,
    "IIc_50": 23,
    "IIc_100": 24,
    "IIc_150": 25,
    "III_0": 26,
    "III_20": 27,
    "III_50": 28,
    "IV_20": 29,
    "IV_50": 30,
    "IV_100": 31,
    "IV_150": 32,
    "V_20": 33,
    "V_50": 34,
    "V_100": 35,
    "V_150": 36,
    "VI_20": 37,
    "VI_50": 38,
    "VI_100": 39,
    "VI_150": 40,
    "VIIa_20": 41,
    "VIIa_50": 42,
    "VIIa_100": 43,
    "VIIa_150": 44,
    "VIIb_100": 45,
    "VIIIa_75": 46,
    "VIIIb_75": 47,
    "IX_35": 48,
    "IX_50": 49,
    "IX_75": 50,
    "IX_100": 51,
    "X_50": 52,
    "X_100": 53,
    "X_150": 54,
    "XI_0": 55,
    "XI_10": 56,
    "XI_20": 57,
    "XI_100": 58,
    "XI_150": 59,
    "XI_250": 60,
    "XI_1250": 61,
    "XII_0": 62,
    "XII_20": 63,
    "XII_100": 64,
    # Off-balance entries
    "B1_0": 65,
    "B2_20": 66,
    "B3_50": 67,
    "B4_100": 68,
    "B5_0": 69,
    "B6_50": 70,
    "B7_100": 71,
}

# ---------------------------------------------------------------------------
# SP_RATE_MAP — Maps notch integers to S&P rating strings
# Used in L_01_FACT_RWA.sas for ECAI rating logic.
# ---------------------------------------------------------------------------
SP_RATE_MAP: dict[int, str] = {
    1: "AAA",
    2: "AA+",
    3: "AA",
    4: "AA-",
    5: "A+",
    6: "A",
    7: "A-",
    8: "BBB+",
    9: "BBB",
    10: "BBB-",
    11: "BB+",
    12: "BB",
    13: "BB-",
    14: "B+",
    15: "B",
    16: "B-",
    17: "CCC+",
    18: "CCC",
    19: "CCC-",
    20: "CC",
    21: "C",
    22: "D",
}


# =============================================================================
# DYNAMIC LOOKUPS (built from data at runtime)
# =============================================================================

def build_notch_cc_lookup(cc_rate_notch_df: pl.DataFrame) -> dict[str, int]:
    """
    Build counterparty credit rating → NOTCH lookup.

    Translated from F_11_CCP_BONDS_RATING.sas lines 131-152::

        data FMT_NOTCH_CC(keep=FMTNAME TYPE START LABEL HLO);
            retain FMTNAME 'notchcc' TYPE 'C';
            set cc_rate_notch;
            where flag_target=1;
            START=cats(RM_CUST_ID, CCY_GROUP);
            LABEL=NOTCH;
        run;

    Parameters
    ----------
    cc_rate_notch_df : pl.DataFrame
        Must have columns: ``flag_target``, ``RM_CUST_ID``, ``CCY_GROUP``, ``NOTCH``.

    Returns
    -------
    dict[str, int]
        ``{"{RM_CUST_ID}{CCY_GROUP}": NOTCH, ...}``
    """
    filtered = cc_rate_notch_df.filter(pl.col("flag_target") == 1)
    result: dict[str, int] = {}
    for row in filtered.iter_rows(named=True):
        key = f"{row['RM_CUST_ID']}{row['CCY_GROUP']}"
        result[key] = int(row["NOTCH"])
    logger.info("build_notch_cc_lookup: %d entries", len(result))
    return result


def build_notch_bd_lookup(bonds_notch_df: pl.DataFrame) -> dict[str, int]:
    """
    Build bond issue rating → NOTCH lookup.

    Translated from F_11_CCP_BONDS_RATING.sas lines 158-174::

        data FMT_NOTCH_BD(keep=FMTNAME TYPE START LABEL HLO);
            retain FMTNAME 'notchbd' TYPE 'C';
            set bonds_notch;
            where flag_target=1;
            START=ACCT_ID;
            LABEL=NOTCH;
        run;

    Parameters
    ----------
    bonds_notch_df : pl.DataFrame
        Must have columns: ``flag_target``, ``ACCT_ID``, ``NOTCH``.

    Returns
    -------
    dict[str, int]
        ``{ACCT_ID: NOTCH, ...}``
    """
    filtered = bonds_notch_df.filter(pl.col("flag_target") == 1)
    result: dict[str, int] = {}
    for row in filtered.iter_rows(named=True):
        result[str(row["ACCT_ID"])] = int(row["NOTCH"])
    logger.info("build_notch_bd_lookup: %d entries", len(result))
    return result


def build_pd_format(xls_master_scale_pd: pl.DataFrame) -> dict[int, float]:
    """
    Build NOTCH → PD_AVG mapping.

    Translated from Code/06.ST_COUNTRY_FI/M_01_BASE.sas lines 1-20.

    Parameters
    ----------
    xls_master_scale_pd : pl.DataFrame
        Must have columns: ``NOTCH``, ``PD_AVG``.

    Returns
    -------
    dict[int, float]
        ``{NOTCH: PD_AVG, ...}``
    """
    result: dict[int, float] = {}
    for row in xls_master_scale_pd.iter_rows(named=True):
        if row.get("NOTCH") is not None and row.get("PD_AVG") is not None:
            result[int(row["NOTCH"])] = float(row["PD_AVG"])
    logger.info("build_pd_format: %d entries", len(result))
    return result


def build_rw_long_format(xls_master_scale_pd: pl.DataFrame) -> dict[int, float]:
    """
    Build NOTCH → rw_long (long-term risk weight) mapping.

    Parameters
    ----------
    xls_master_scale_pd : pl.DataFrame
        Must have columns: ``NOTCH``, ``rw_long``.

    Returns
    -------
    dict[int, float]
    """
    result: dict[int, float] = {}
    for row in xls_master_scale_pd.iter_rows(named=True):
        notch = row.get("NOTCH")
        rw = row.get("rw_long") if row.get("rw_long") is not None else row.get("RW_LONG")
        if notch is not None and rw is not None:
            result[int(notch)] = float(rw)
    logger.info("build_rw_long_format: %d entries", len(result))
    return result


def build_rw_short_format(xls_master_scale_pd: pl.DataFrame) -> dict[int, float]:
    """
    Build NOTCH → rw_short (short-term risk weight) mapping.

    Parameters
    ----------
    xls_master_scale_pd : pl.DataFrame
        Must have columns: ``NOTCH``, ``rw_short``.

    Returns
    -------
    dict[int, float]
    """
    result: dict[int, float] = {}
    for row in xls_master_scale_pd.iter_rows(named=True):
        notch = row.get("NOTCH")
        rw = row.get("rw_short") if row.get("rw_short") is not None else row.get("RW_SHORT")
        if notch is not None and rw is not None:
            result[int(notch)] = float(rw)
    logger.info("build_rw_short_format: %d entries", len(result))
    return result


def build_cust_elim_format(cust_elim_df: pl.DataFrame) -> set[str]:
    """
    Build set of CUST_SEC_IDs for consolidation elimination.

    Translated from Code/06.ST_COUNTRY_FI/L_01_BASE.sas lines 7-17::

        data FMT_CUST_ELIM(keep=FMTNAME TYPE START LABEL HLO);
            retain FMTNAME 'c_elim' TYPE 'C';
            set siw.vi_iacbs_cust_elim_upd_&st_RptMth. end=last;
            START=CUST_SEC_ID;
            LABEL='Y';
            output;
            if last then do;
                START="**OTHER**";
                LABEL='N';
                HLO='O';
                output;
            end;
        run;

    Parameters
    ----------
    cust_elim_df : pl.DataFrame
        Must have column: ``CUST_SEC_ID``.

    Returns
    -------
    set[str]
        Set of CUST_SEC_IDs to eliminate.
    """
    result = set(
        str(v) for v in cust_elim_df.select("CUST_SEC_ID").to_series().to_list()
        if v is not None
    )
    logger.info("build_cust_elim_format: %d entries", len(result))
    return result


# =============================================================================
# HELPER: apply_lookup
# =============================================================================

def apply_lookup(
    df: pl.DataFrame,
    column: str,
    lookup_dict: dict[Any, Any],
    output_column: str | None = None,
    default: Any = None,
) -> pl.DataFrame:
    """
    Apply a dictionary lookup to a polars column.

    Equivalent to SAS ``put(value, $format.)`` — maps each value in *column*
    through *lookup_dict*, writing the result to *output_column*.

    Parameters
    ----------
    df : pl.DataFrame
        Input DataFrame.
    column : str
        Source column name.
    lookup_dict : dict
        Mapping from source values to target values.
    output_column : str, optional
        Name for the result column.  Defaults to *column* (in-place replace).
    default : Any, optional
        Value to use when the source value is not in the lookup.

    Returns
    -------
    pl.DataFrame
    """
    if output_column is None:
        output_column = column

    # Build a polars mapping DataFrame for efficient join-based lookup
    keys = list(lookup_dict.keys())
    values = list(lookup_dict.values())

    if not keys:
        # Empty lookup — just fill with default
        return df.with_columns(pl.lit(default).alias(output_column))

    # Determine types
    lookup_df = pl.DataFrame({
        "_lkp_key": keys,
        "_lkp_val": values,
    })

    # Join approach for large lookups
    # Deduplicate after Utf8 cast to prevent row multiplication when
    # different-typed keys stringify to the same value (e.g. int 1 and str "1").
    lookup_df_cast = lookup_df.with_columns(
        pl.col("_lkp_key").cast(pl.Utf8)
    ).unique(subset=["_lkp_key"])

    result = (
        df.with_columns(pl.col(column).cast(pl.Utf8).alias("_lkp_src"))
        .join(
            lookup_df_cast,
            left_on="_lkp_src",
            right_on="_lkp_key",
            how="left",
        )
        .with_columns(
            pl.when(pl.col("_lkp_val").is_not_null())
            .then(pl.col("_lkp_val"))
            .otherwise(pl.lit(default))
            .alias(output_column)
        )
        .drop(["_lkp_src", "_lkp_val"])
    )

    return result
