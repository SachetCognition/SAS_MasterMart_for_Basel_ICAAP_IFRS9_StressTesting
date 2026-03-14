"""
Shared macros — translated from Code/0.LIBRARY/Macro.sas (all 51 lines).

Provides Python equivalents of SAS macros:
  - %ORA_Extract  -> ora_extract()
  - %Auto_RptMth  -> auto_rpt_month()
  - %ErrAdj       -> error_adjustment()
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl

if TYPE_CHECKING:
    import oracledb

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# %ORA_Extract  (Macro.sas lines 1-13)
# ---------------------------------------------------------------------------

def ora_extract(
    connection: oracledb.Connection,
    input_table: str,
    output_path: str | Path,
    date_filter: date | None = None,
    replace: bool = False,
    batch_size: int = 10_000,
) -> pl.DataFrame:
    """
    Extract data from an Oracle IW view, optionally filtering by month-end date.

    Translated from::

        %macro ORA_Extract(input=, output=, date=, ind=);
            %if NOT %sysfunc(exist(&output.)) or &ind.=REPLACE %then %do;
                %if &date. ne %then %let dt=&date.;
                %else %let dt=&dt_RptMth.;
                data &output.;
                    set &input.;
                    where intnx("MONTH", datepart(as_of_dt), 0, "END") = &dt.;
                run;
            %end;
            %else %put [Info: The file of &output. is already exist, please check!];
        %mend;

    Parameters
    ----------
    connection : oracledb.Connection
        Active Oracle database connection.
    input_table : str
        Fully-qualified Oracle view/table name.
    output_path : str or Path
        Destination Parquet file path.
    date_filter : date, optional
        Month-end date for the ``as_of_dt`` filter.  When ``None`` the
        query is issued *without* a date filter (used for static tables).
    replace : bool
        If ``False`` and the output file already exists, skip extraction.
    batch_size : int
        ``cursor.arraysize`` for performance (default 10 000).

    Returns
    -------
    pl.DataFrame
    """
    import pyarrow as pa

    output_path = Path(output_path)

    # Idempotency: skip if file exists and replace is not requested
    if output_path.exists() and not replace:
        logger.info("Output already exists, skipping: %s", output_path)
        return pl.read_parquet(output_path)

    cursor = connection.cursor()
    cursor.arraysize = batch_size

    if date_filter is not None:
        # SAS: where intnx("MONTH", datepart(as_of_dt), 0, "END") = &dt.
        # In Oracle SQL we match the last day of the as_of_dt month
        sql = (
            f"SELECT * FROM {input_table} "  # noqa: S608
            "WHERE TRUNC(LAST_DAY(CAST(as_of_dt AS DATE))) = :dt"
        )
        cursor.execute(sql, {"dt": date_filter})
    else:
        sql = f"SELECT * FROM {input_table}"  # noqa: S608
        cursor.execute(sql)

    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    cursor.close()

    logger.info(
        "Extracted %d rows from %s", len(rows), input_table,
    )

    # Zero-copy conversion via PyArrow
    if rows:
        arrays = list(zip(*rows))
        arrow_arrays = [pa.array(col) for col in arrays]
        arrow_table = pa.table(dict(zip(columns, arrow_arrays)))
        df = pl.from_arrow(arrow_table)
    else:
        df = pl.DataFrame(schema={col: pl.Utf8 for col in columns})

    # Persist as Parquet
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(output_path)
    logger.info("Wrote %s (%d rows)", output_path, len(df))

    return df


# ---------------------------------------------------------------------------
# %Auto_RptMth  (Macro.sas lines 15-23)
# ---------------------------------------------------------------------------

def auto_rpt_month(rpt_month: str = "") -> str:
    """
    Return YYYYMM string for the reporting month.

    If *rpt_month* is blank / empty, defaults to the previous calendar
    month end — matching the SAS macro ``%Auto_RptMth``.

    Translated from::

        %Macro Auto_RptMth();
            %if &st_RptMth. =  %then %do;
                data _null_;
                    a=intnx("MONTH", date(), -1, "END");
                    b=put(a,yymmn6.);
                    call symput("st_RptMth", b);
                run;
            %end;
        %mend;
    """
    if rpt_month and rpt_month.strip():
        return rpt_month.strip()

    today = date.today()
    first_of_month = today.replace(day=1)
    prev_month_end = first_of_month - timedelta(days=1)
    return prev_month_end.strftime("%Y%m")


# ---------------------------------------------------------------------------
# %ErrAdj  (Macro.sas lines 25-50)
# ---------------------------------------------------------------------------

def error_adjustment(
    err_tbl: pl.DataFrame,
    tbl: str,
    mode: str,
    dt_rpt_month: date,
) -> dict[str, list[str]]:
    """
    Generate error-adjustment instructions from the manual master table.

    In SAS this macro dynamically writes code to temp files and ``%include``s
    them.  In Python we return a dictionary keyed by ``adj_no`` whose values
    are lists of ``Detail`` strings.  The caller applies these as conditional
    column updates.

    Translated from::

        %macro ErrAdj(err_tbl=,tbl=,mode=);
            proc sort data=&err_tbl. out=adj_no_key(keep=adj_no) nodupkey;
                where IW_Table = "&tbl." and Mode = "&mode.";
                by adj_no;
            run;
            proc sql noprint;
                select count(1) into :cnt from adj_no_key;
            quit;
            %do i=1 %to &cnt.;
                data _null_;
                    set adj_no_key(firstobs=&i. obs=&i.);
                    call symput("adjno",adj_no);
                run;
                filename EA&adjno. temp;
                data _null_;
                    file EA&adjno. lrecl=65535;
                    set &err_tbl.;
                    if eff_from <= &dt_RptMth. <= eff_to;
                    if IW_Table = "&tbl.";
                    if Mode     = "&mode.";
                    if Adj_No   = "&adjno.";
                    put Detail;
                run;
            %end;
        %mend;

    Parameters
    ----------
    err_tbl : pl.DataFrame
        The manual-master error table (``siw.XLS_ST_MANUAL_MASTER``).
        Expected columns: ``IW_Table``, ``Mode``, ``adj_no``,
        ``eff_from``, ``eff_to``, ``Detail``.
    tbl : str
        Value to match against ``IW_Table`` (e.g. ``"KW_VC"``).
    mode : str
        Value to match against ``Mode`` (e.g. ``"U"`` or ``"I"``).
    dt_rpt_month : date
        The reporting month-end date used for effective-date filtering.

    Returns
    -------
    dict[str, list[str]]
        ``{adj_no: [detail_line, ...]}``
    """
    # Filter by IW_Table, Mode, and effective date range
    filtered = err_tbl.filter(
        (pl.col("IW_Table") == tbl)
        & (pl.col("Mode") == mode)
        & (pl.col("eff_from") <= dt_rpt_month)
        & (pl.col("eff_to") >= dt_rpt_month)
    )

    if filtered.is_empty():
        return {}

    result: dict[str, list[str]] = {}
    adj_nos = filtered.select("adj_no").unique().sort("adj_no")

    for row in adj_nos.iter_rows():
        adj_no = str(row[0])
        details = (
            filtered.filter(pl.col("adj_no") == row[0])
            .select("Detail")
            .to_series()
            .to_list()
        )
        result[adj_no] = [str(d) for d in details if d is not None]

    logger.info(
        "ErrAdj(tbl=%s, mode=%s): found %d adjustment groups",
        tbl,
        mode,
        len(result),
    )
    return result


def apply_error_adjustments(
    df: pl.DataFrame,
    adjustments: dict[str, list[str]],
    context: dict[str, Any] | None = None,
) -> pl.DataFrame:
    """
    Apply error adjustment detail lines to a DataFrame.

    Each ``Detail`` string from the SAS error table is a SAS statement
    (e.g. ``if ACCT_ID='xxx' then APPL_RISK_WEIGHT=20;``).  This function
    parses simple assignment patterns and applies them as conditional
    updates on *df*.

    Parameters
    ----------
    df : pl.DataFrame
        The working dataset to modify.
    adjustments : dict[str, list[str]]
        Output of :func:`error_adjustment`.
    context : dict, optional
        Additional variables available during evaluation.

    Returns
    -------
    pl.DataFrame
        The modified DataFrame.
    """
    import re

    for adj_no, details in adjustments.items():
        for detail in details:
            detail = detail.strip().rstrip(";")
            if not detail:
                continue

            # Parse simple "if <cond> then <var>=<val>" patterns
            match = re.match(
                r"if\s+(.+?)\s+then\s+(\w+)\s*=\s*(.+)",
                detail,
                re.IGNORECASE,
            )
            if match:
                condition_str = match.group(1).strip()
                target_col = match.group(2).strip()
                value_str = match.group(3).strip().strip("'\"")

                # Build polars filter expression from simple conditions
                filter_expr = _parse_condition(condition_str)
                if filter_expr is not None:
                    try:
                        value: Any
                        try:
                            value = float(value_str)
                            if value == int(value):
                                value = int(value)
                        except ValueError:
                            value = value_str

                        df = df.with_columns(
                            pl.when(filter_expr)
                            .then(pl.lit(value))
                            .otherwise(pl.col(target_col))
                            .alias(target_col)
                        )
                        logger.debug(
                            "Applied adj %s: %s", adj_no, detail,
                        )
                    except Exception:
                        logger.warning(
                            "Could not apply adj %s detail: %s",
                            adj_no,
                            detail,
                        )
                else:
                    logger.warning(
                        "Could not parse condition in adj %s: %s",
                        adj_no,
                        detail,
                    )
            else:
                logger.warning(
                    "Unrecognised detail format in adj %s: %s",
                    adj_no,
                    detail,
                )

    return df


def _parse_condition(condition_str: str) -> pl.Expr | None:
    """
    Parse a simple SAS-style condition into a polars expression.

    Handles:
      - ``FIELD = 'value'``
      - ``FIELD = numeric``
      - ``FIELD in ('a','b')``
      - compound conditions joined with ``and``
    """
    import re

    parts = re.split(r"\s+and\s+", condition_str, flags=re.IGNORECASE)
    expr: pl.Expr | None = None

    for part in parts:
        part = part.strip()

        # field = 'value' or field = number
        m_eq = re.match(r"(\w+)\s*=\s*['\"]?([^'\"]+?)['\"]?\s*$", part)
        if m_eq:
            col_name = m_eq.group(1)
            val = m_eq.group(2).strip()
            try:
                val_num = float(val)
                sub = pl.col(col_name) == val_num
            except ValueError:
                sub = pl.col(col_name) == val

            expr = sub if expr is None else expr & sub
            continue

        # field in ('a','b','c')
        m_in = re.match(r"(\w+)\s+in\s*\((.+)\)", part, re.IGNORECASE)
        if m_in:
            col_name = m_in.group(1)
            vals_raw = m_in.group(2)
            vals = [v.strip().strip("'\"") for v in vals_raw.split(",")]
            sub = pl.col(col_name).is_in(vals)
            expr = sub if expr is None else expr & sub
            continue

        # If we can't parse, give up
        return None

    return expr
