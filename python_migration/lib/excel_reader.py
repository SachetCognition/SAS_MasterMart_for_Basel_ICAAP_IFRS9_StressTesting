"""
Excel import utilities — translated from E_IMPORT_BASEL_SGP.sas and related files.

Provides:
  - import_excel_sheet()    — general-purpose Excel import
  - import_sgp_excel()      — complex SGP import with dynamic column typing
  - import_multi_sheet()    — multi-sheet import (e.g. ST_Manual_Master.xls)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keywords used for dynamic numeric column detection in SGP imports
# Translated from E_IMPORT_BASEL_SGP.sas lines 20-33 (%tx macro)
# ---------------------------------------------------------------------------
_NUMERIC_KEYWORDS = frozenset({
    "AMT", "RISKWEIGHT", "CCF", "ACCUREDINT", "RATE", "EXPOSURE",
    "DAYS", "ACC_INT", "AMOUNT", "MTMPL", "UPLHKE", "EXPSOURE", "TOTALHKD",
})

# Date type 1 columns (Excel datevalue - need offset subtraction)
_DATE_TYPE1_KEYWORDS = frozenset({
    "TDATE", "VDATE", "MDATE", "RVDATE", "RPT_DATE",
    "STARTDATE", "ENDDATE", "VALUEDATE", "MAT_DATE",
    "MONTHSAFTERVALUEDATE", "DUE_DATE",
})

# Date type 2 columns (ISO format dates)
_DATE_TYPE2_KEYWORDS = frozenset({"OS_DATE"})

# Type-specific row filters
_TYPE_FILTERS: dict[str, str] = {
    "IMEX": "CURR",
    "Loan": "CURRENCY",
    "MM": "CCY",
    "FX": "CC",
    "Nostro": "Nature",
}


def import_excel_sheet(
    path: str | Path,
    sheet: str | int = 0,
    header_row: int = 0,
    **kwargs: Any,
) -> pl.DataFrame:
    """
    Import a single Excel sheet into a polars DataFrame.

    Wraps ``polars.read_excel`` with sensible defaults.

    Parameters
    ----------
    path : str or Path
        Path to the Excel file.
    sheet : str or int
        Sheet name or 0-based index.
    header_row : int
        Row index (0-based) to use as column headers.

    Returns
    -------
    pl.DataFrame
    """
    path = Path(path)
    logger.info("Importing Excel: %s [sheet=%s, header_row=%d]", path, sheet, header_row)

    df = pl.read_excel(
        source=path,
        sheet_name=sheet if isinstance(sheet, str) else sheet,
        engine="openpyxl",
        **kwargs,
    )

    # If header_row > 0, we need to skip rows and use the specified row as header
    if header_row > 0:
        new_columns = [str(v) for v in df.row(header_row - 1)]
        df = df.slice(header_row).rename(dict(zip(df.columns, new_columns)))

    logger.info("  -> %d rows, %d columns", len(df), len(df.columns))
    return df


def import_sgp_excel(
    path: str | Path,
    type_name: str,
    name_row: int,
    sheet: str | None = None,
    dt_f_x2s: int = 21916,
) -> pl.DataFrame:
    """
    Import a Singapore Basel return Excel file with dynamic column typing.

    Translated from E_IMPORT_BASEL_SGP.sas — the ``%tx`` and ``%SGPImport``
    macros (lines 1-98).

    The logic:
    1. Read the raw Excel (GETNAMES=NO, DATAROW=namerow)
    2. Read column names from the first data row
    3. Classify each column as numeric, date-type-1, date-type-2, or string
       based on keyword matching
    4. Apply type conversions
    5. Apply type-specific row filter (e.g. IMEX: not missing CURR)

    Parameters
    ----------
    path : str or Path
        Path to the Excel file.
    type_name : str
        Type identifier: "IMEX", "MM", "Loan", "FX", or "Nostro".
    name_row : int
        Row number (1-based) containing column names.
    sheet : str, optional
        Sheet name.  If ``None``, uses the first sheet.
    dt_f_x2s : int
        Excel-to-SAS date offset for type-1 date conversion.

    Returns
    -------
    pl.DataFrame
    """
    path = Path(path)
    logger.info("SGP Import: %s [type=%s, namerow=%d]", path, type_name, name_row)

    # Step 1: Read raw data without headers
    read_kwargs: dict[str, Any] = {"engine": "openpyxl"}
    if sheet is not None:
        read_kwargs["sheet_name"] = sheet

    raw_df = pl.read_excel(source=path, **read_kwargs)

    if len(raw_df) < name_row:
        logger.warning("File has fewer rows than name_row=%d", name_row)
        return pl.DataFrame()

    # Step 2: Extract column names from the name row (1-based → 0-based index)
    name_row_data = raw_df.row(name_row - 1)
    raw_col_names = [str(v) if v is not None else "" for v in name_row_data]

    # Clean column names: remove spaces, digits, special chars for classification
    def _clean_name(name: str) -> str:
        return re.sub(r"[ 0-9/(%)&.]", "", name).strip()

    cleaned_names = [_clean_name(n) for n in raw_col_names]

    # Step 3: Get data rows (after the name row)
    data_df = raw_df.slice(name_row)

    # Rename columns to the cleaned text names
    final_names: list[str] = []
    seen: dict[str, int] = {}
    for cn in cleaned_names:
        if not cn:
            cn = f"_EMPTY_{len(final_names)}"
        if cn in seen:
            seen[cn] += 1
            cn = f"{cn}_{seen[cn]}"
        else:
            seen[cn] = 0
        final_names.append(cn)

    rename_map = dict(zip(data_df.columns, final_names))
    data_df = data_df.rename(rename_map)

    # Step 4: Classify and convert columns
    result_exprs: list[pl.Expr] = []
    keep_cols: list[str] = []

    for i, (orig_name, txt_name) in enumerate(zip(raw_col_names, final_names)):
        if not _clean_name(orig_name):
            continue

        upper_txt = txt_name.upper()

        # Check numeric keywords
        is_numeric = any(kw in upper_txt for kw in _NUMERIC_KEYWORDS)

        # Check date keywords
        is_date1 = upper_txt in _DATE_TYPE1_KEYWORDS
        is_date2 = upper_txt in _DATE_TYPE2_KEYWORDS

        if is_numeric:
            # Convert to float (comma32. format in SAS)
            result_exprs.append(
                pl.col(txt_name).cast(pl.Utf8).str.replace_all(",", "").cast(pl.Float64, strict=False).alias(txt_name)
            )
        elif is_date1:
            # Excel datevalue minus offset → SAS date → Python date
            result_exprs.append(
                (pl.col(txt_name).cast(pl.Float64, strict=False) - dt_f_x2s).alias(txt_name)
            )
        elif is_date2:
            # Parse as YYYYMMDD date string
            result_exprs.append(
                pl.col(txt_name).cast(pl.Utf8).alias(txt_name)
            )
        else:
            # Keep as string
            result_exprs.append(pl.col(txt_name).cast(pl.Utf8).alias(txt_name))

        keep_cols.append(txt_name)

    if result_exprs:
        data_df = data_df.select(result_exprs)

    # Step 5: Apply type-specific row filter
    filter_col = _TYPE_FILTERS.get(type_name)
    if filter_col and filter_col in data_df.columns:
        data_df = data_df.filter(pl.col(filter_col).is_not_null() & (pl.col(filter_col) != ""))

    # Special handling for IMEX: derive SHORT_TERM_CLAIM_IND
    if type_name == "IMEX" and "CARItemCode" in data_df.columns:
        data_df = data_df.with_columns(
            pl.when(
                pl.col("CARItemCode").cast(pl.Utf8).str.strip_chars().str.reverse().str.slice(0, 1) == "Y"
            )
            .then(pl.lit("Y"))
            .otherwise(pl.lit(""))
            .alias("SHORT_TERM_CLAIM_IND")
        )

    logger.info("  -> %d rows, %d columns after conversion", len(data_df), len(data_df.columns))
    return data_df


def import_multi_sheet(
    path: str | Path,
    sheet_configs: dict[str, dict[str, Any]],
) -> dict[str, pl.DataFrame]:
    """
    Import multiple sheets from a single Excel file.

    Used for ST_Manual_Master.xls which has 6 sheets:
      - Manual_Adj, ST_Parameter, CBIC_Bank_Mapping,
        ST_Parameter_ICAAP, RST_Parameter, RP_Parameter

    Translated from E_00_XLS_ERR_MASTER.sas (lines 1-40).

    Parameters
    ----------
    path : str or Path
        Path to the Excel file.
    sheet_configs : dict[str, dict]
        ``{output_name: {"sheet": sheet_name, ...kwargs}}``

    Returns
    -------
    dict[str, pl.DataFrame]
        ``{output_name: DataFrame, ...}``
    """
    path = Path(path)
    results: dict[str, pl.DataFrame] = {}

    for output_name, config in sheet_configs.items():
        sheet_name = config.pop("sheet", output_name)
        logger.info("Importing sheet '%s' from %s -> %s", sheet_name, path, output_name)

        try:
            df = pl.read_excel(
                source=path,
                sheet_name=sheet_name,
                engine="openpyxl",
                **config,
            )
            results[output_name] = df
            logger.info("  -> %d rows, %d columns", len(df), len(df.columns))
        except Exception:
            logger.exception("Failed to import sheet '%s' from %s", sheet_name, path)
            results[output_name] = pl.DataFrame()

    return results
