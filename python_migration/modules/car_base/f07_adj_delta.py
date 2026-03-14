"""
Delta adjustments using error adjustment system.

Translated from Code/01.CAR_BASE/F_07_ADJ_DELTA.sas (~173 lines).

In SAS, F_07 calls %ErrAdj(tbl=KW_VC, mode=I) which generates include files
(EA3_1, EA5_1, EA6_1, EA999).  Each DATA step then %includes one of these
files to create new delta adjustment records with hardcoded metadata.

Delta groups:
  - adj_delta_3   (FLAG_ADJ=3.1):  from EA3_1
  - adj_delta_5   (FLAG_ADJ=5.1):  Credit Card from EA5_1
  - adj_delta_6   (FLAG_ADJ=6.1):  MPA deduction from EA6_1
  - adj_delta_other:                Other adjustments from EA999
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

import polars as pl

from lib.macros import error_adjustment

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapping from SAS adj_no identifiers to delta group metadata.
#
# SAS: %ErrAdj(err_tbl=..., tbl=KW_VC, mode=I) generates one include file
# per distinct adj_no.  Each DATA step in F_07 references a specific file
# and adds hardcoded column assignments (ENTITY, APPL_CD, etc.) taken from
# the original SAS source (lines 7-49).
# ---------------------------------------------------------------------------
_DELTA_GROUPS: list[dict[str, Any]] = [
    {
        "adj_nos": ["3_1", "3.1"],
        "name": "adj_delta_3",
        "flag_adj": 3.1,
        "desc": "NY/LA reclass from EA3_1",
        "metadata": {},
    },
    {
        "adj_nos": ["5_1", "5.1"],
        "name": "adj_delta_5",
        "flag_adj": 5.1,
        "desc": "Credit Card from EA5_1",
        "metadata": {
            "ENTITY": "CNCBI",
            "APPL_CD": "CREDIT CARD",
            "ORIG_PORT_CD": "VIIIa",
            "PORT_CD": "VIIIa",
            "PROD_SYS_CD": "MANUAL ADJ",
        },
    },
    {
        "adj_nos": ["6_1", "6.1"],
        "name": "adj_delta_6",
        "flag_adj": 6.1,
        "desc": "MPA deduction from EA6_1",
        "metadata": {
            "ENTITY": "CNCBI",
            "APPL_CD": "ALS",
            "PROD_SYS_CD": "MANUAL ADJ",
        },
    },
    {
        "adj_nos": ["999", "999.0"],
        "name": "adj_delta_other",
        "flag_adj": None,
        "desc": "Other adjustments from EA999",
        "metadata": {
            "ENTITY": "CNCBI",
            "PROD_SYS_CD": "MANUAL ADJ",
        },
    },
]


def _parse_detail_assignments(details: list[str]) -> dict[str, Any]:
    """
    Parse SAS assignment statements from error adjustment detail lines.

    In SAS, each detail line from the error master is written to an include
    file and executed inside a DATA step.  For mode=I (Insert), these are
    simple assignments that populate column values for a new observation::

        PORT_CD='IV'; APPL_CRM_AMT_HKE=12345;

    All detail lines for one adj_no accumulate into a single record
    (matching SAS DATA step behavior where included lines populate one
    observation before the implicit OUTPUT).
    """
    record: dict[str, Any] = {}
    for detail in details:
        if not detail or not detail.strip():
            continue
        for stmt in detail.strip().split(";"):
            stmt = stmt.strip()
            if not stmt:
                continue
            m = re.match(r"(\w+)\s*=\s*(.+)", stmt)
            if m:
                col = m.group(1).strip()
                val = m.group(2).strip().strip("'\"")
                try:
                    num_val = float(val)
                    record[col] = int(num_val) if num_val == int(num_val) else num_val
                except ValueError:
                    record[col] = val
    return record


def run(
    config: Config,
    err_master: pl.DataFrame,
) -> dict[str, pl.DataFrame]:
    """
    Generate delta adjustment records from the error master table.

    Translated from F_07_ADJ_DELTA.sas::

        %ErrAdj(err_tbl=siw.XLS_ST_MANUAL_MASTER,tbl=KW_VC,mode=I);

        data stg.adj_delta_3;
            %include EA3_1 /source2;
            FLAG_ADJ=3.1;
            if APPL_CRM_AMT_HKE = . then delete;
        run;
        ...  (similar for adj_delta_5, adj_delta_6, adj_delta_other)

    Parameters
    ----------
    config : Config
    err_master : pl.DataFrame
        Error/manual adjustment master table (``XLS_ST_MANUAL_MASTER``).

    Returns
    -------
    dict[str, pl.DataFrame]
        Delta datasets: adj_delta_3, adj_delta_5, adj_delta_6, adj_delta_other
    """
    results: dict[str, pl.DataFrame] = {}

    # SAS: %ErrAdj(err_tbl=..., tbl=KW_VC, mode=I)
    all_adjustments: dict[str, list[str]] = {}
    if not err_master.is_empty():
        required_cols = {"IW_Table", "Mode", "adj_no", "eff_from", "eff_to", "Detail"}
        if required_cols.issubset(set(err_master.columns)):
            all_adjustments = error_adjustment(
                err_tbl=err_master,
                tbl="KW_VC",
                mode="I",
                dt_rpt_month=config.dt_rpt_month,
            )

    for group_info in _DELTA_GROUPS:
        name: str = group_info["name"]

        # Find matching adjustment details for this group
        details: list[str] = []
        for adj_no_variant in group_info["adj_nos"]:
            if adj_no_variant in all_adjustments:
                details = all_adjustments[adj_no_variant]
                break

        if details:
            record = _parse_detail_assignments(details)
            # Apply hardcoded metadata from SAS DATA step
            record.update(group_info["metadata"])
            if group_info["flag_adj"] is not None:
                record["FLAG_ADJ"] = group_info["flag_adj"]
            # SAS: if APPL_CRM_AMT_HKE = . then delete
            if record.get("APPL_CRM_AMT_HKE") is not None:
                results[name] = pl.DataFrame([record])
            else:
                results[name] = pl.DataFrame()
        else:
            results[name] = pl.DataFrame()

        logger.info("F07: %s (%s): %d rows",
                     name, group_info["desc"], len(results[name]))

    return results
