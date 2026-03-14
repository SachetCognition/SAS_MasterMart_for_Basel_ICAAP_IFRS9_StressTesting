"""
Parse semi-structured derivative data with positional columns.

Translated from Code/01.CAR_BASE/F_03_DERIVATIVE.sas (88 lines).

Key operations:
  - Forward-fill port codes (PORTCD_COMBINED, PORTCD_CONSOLID)
  - Parse portfolio codes from column A/J (B-prefix handling)
  - Handle B18 special case
  - Multiply amounts by 1000
  - Produce both Combined (OVERSEA) and Consolidated (CBIC) derivative deltas
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def _parse_port_code(port_str: str) -> tuple[str, str]:
    """
    Parse a portfolio code string into (PORT_CD, EXP_REF).

    If string does NOT start with 'B', prefix with 'B' and derive EXP_REF
    from the 3rd character (a=1 YEAR, b=5 YEARS, c=OVER 5YR).
    If string starts with 'B', PORT_CD is first 3 chars, EXP_REF is remainder.
    """
    if not port_str or not port_str.strip():
        return "", ""

    port_str = port_str.strip()
    if port_str[0] != "B":
        port_cd = f"B{port_str[:2]}"
        exp_ref = ""
        if len(port_str) >= 3:
            suffix = port_str[2]
            if suffix == "a":
                exp_ref = "1 YEAR"
            elif suffix == "b":
                exp_ref = "5 YEARS"
            elif suffix == "c":
                exp_ref = "OVER 5YR"
        return port_cd, exp_ref
    else:
        port_cd = port_str[:3]
        exp_ref = port_str[4:] if len(port_str) > 4 else ""
        return port_cd, exp_ref


def _parse_amount(val: str | None) -> float:
    """Parse a comma-formatted string to float, multiply by 1000."""
    if val is None:
        return 0.0
    try:
        return float(str(val).replace(",", "")) * 1000
    except (ValueError, TypeError):
        return 0.0


def run(config: Config, x_deriv_df: pl.DataFrame) -> pl.DataFrame:
    """
    Process derivative data into delta adjustments.

    Translated from F_03_DERIVATIVE.sas.

    Parameters
    ----------
    config : Config
    x_deriv_df : pl.DataFrame
        Raw derivative Excel data (stg.x_deriv).

    Returns
    -------
    pl.DataFrame
        adj_derv_delta with columns: FLAG_ADJ, PORT_CD, EXP_REF, ENTITY,
        FILE_SRC, CUST_NAME, CUR_BAL_OFF_HKE, CUR_EXP_AMT_HKE,
        POTENT_EXP_AMT_HKE, ORIG_CRM_AMT_HKE, APPL_CRM_AMT_HKE,
        RISK_WEIGHTED_AMT_HKE, FAC_TYP
    """
    if x_deriv_df.is_empty():
        logger.warning("F03: Empty derivative input")
        return pl.DataFrame()

    # Skip first 9 rows (SAS: firstobs=10 means start from row 10)
    if len(x_deriv_df) <= 9:
        logger.warning("F03: Derivative data has fewer than 10 rows")
        return pl.DataFrame()

    data = x_deriv_df.slice(9)
    cols = data.columns

    # Map positional columns: A=col[0], B=col[1], ..., O=col[14]
    col_map = {chr(65 + i): cols[i] for i in range(min(len(cols), 15))}

    records: list[dict[str, object]] = []
    portcd_combined = ""
    portcd_consolid = ""

    for row in data.iter_rows(named=True):
        a_val = str(row.get(col_map.get("A", ""), "") or "").strip()
        j_val = str(row.get(col_map.get("J", ""), "") or "").strip()

        # Forward-fill port codes (SAS retain logic)
        if a_val:
            portcd_combined = a_val
        else:
            a_val = portcd_combined
        if j_val:
            portcd_consolid = j_val
        else:
            j_val = portcd_consolid

        # --- Combined (OVERSEA) record ---
        b_val = str(row.get(col_map.get("B", ""), "") or "").strip()
        if b_val:
            port_cd, exp_ref = _parse_port_code(a_val)
            c_amt = _parse_amount(row.get(col_map.get("C", ""), None))
            d_amt = _parse_amount(row.get(col_map.get("D", ""), None))
            e_amt = _parse_amount(row.get(col_map.get("E", ""), None))
            f_amt = _parse_amount(row.get(col_map.get("F", ""), None))
            g_val = str(row.get(col_map.get("G", ""), "") or "").strip()

            if exp_ref == "5 YEAR":
                exp_ref = "5 YEARS"

            rec: dict[str, object] = {
                "FLAG_ADJ": 300.1,
                "ENTITY": "OVERSEA",
                "FILE_SRC": "COMBINED-DERV",
                "PORT_CD": port_cd,
                "EXP_REF": exp_ref,
                "CUST_NAME": b_val,
                "FAC_TYP": g_val,
            }

            # B18 special case
            if port_cd == "B18":
                rec["CUR_BAL_OFF_HKE"] = d_amt
                rec["CUR_EXP_AMT_HKE"] = 0.0
                rec["POTENT_EXP_AMT_HKE"] = 0.0
                rec["ORIG_CRM_AMT_HKE"] = e_amt
                rec["APPL_CRM_AMT_HKE"] = e_amt
                rec["RISK_WEIGHTED_AMT_HKE"] = f_amt
            else:
                rec["CUR_BAL_OFF_HKE"] = c_amt
                rec["CUR_EXP_AMT_HKE"] = d_amt
                rec["POTENT_EXP_AMT_HKE"] = e_amt
                rec["ORIG_CRM_AMT_HKE"] = d_amt + e_amt
                rec["APPL_CRM_AMT_HKE"] = d_amt + e_amt
                rec["RISK_WEIGHTED_AMT_HKE"] = f_amt

            records.append(rec)

        # --- Consolidated (CBIC) record ---
        k_val = str(row.get(col_map.get("K", ""), "") or "").strip()
        if k_val:
            port_cd, exp_ref = _parse_port_code(j_val)
            l_amt = _parse_amount(row.get(col_map.get("L", ""), None))
            m_amt = _parse_amount(row.get(col_map.get("M", ""), None))
            n_amt = _parse_amount(row.get(col_map.get("N", ""), None))
            o_amt = _parse_amount(row.get(col_map.get("O", ""), None))

            if exp_ref == "5 YEAR":
                exp_ref = "5 YEARS"

            rec2: dict[str, object] = {
                "FLAG_ADJ": 300.2,
                "ENTITY": "CBIC",
                "FILE_SRC": "CONSOLID-DERV",
                "PORT_CD": port_cd,
                "EXP_REF": exp_ref,
                "CUST_NAME": k_val,
                "FAC_TYP": "",
            }

            if port_cd == "B18":
                rec2["CUR_BAL_OFF_HKE"] = m_amt
                rec2["CUR_EXP_AMT_HKE"] = 0.0
                rec2["POTENT_EXP_AMT_HKE"] = 0.0
                rec2["ORIG_CRM_AMT_HKE"] = n_amt
                rec2["APPL_CRM_AMT_HKE"] = n_amt
                rec2["RISK_WEIGHTED_AMT_HKE"] = o_amt
            else:
                rec2["CUR_BAL_OFF_HKE"] = l_amt
                rec2["CUR_EXP_AMT_HKE"] = m_amt
                rec2["POTENT_EXP_AMT_HKE"] = n_amt
                rec2["ORIG_CRM_AMT_HKE"] = m_amt + n_amt
                rec2["APPL_CRM_AMT_HKE"] = m_amt + n_amt
                rec2["RISK_WEIGHTED_AMT_HKE"] = o_amt

            records.append(rec2)

    if not records:
        logger.warning("F03: No derivative records produced")
        return pl.DataFrame()

    result = pl.DataFrame(records)
    result = result.sort(["FILE_SRC", "PORT_CD", "EXP_REF"])

    logger.info("F03: Produced %d derivative delta records", len(result))
    return result
