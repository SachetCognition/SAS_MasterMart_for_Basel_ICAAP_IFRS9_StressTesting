"""
Import non-system adjustment Excel files.

Translated from Code/01.CAR_BASE/E_02_XLS_NONSYSTEM.sas (62 lines).

Imports OGL outstanding for Basel (nonsystem) and HKCBF Non_Sys files
with dynamic column typing via the %tx macro equivalent.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)

# Columns that remain as strings (not converted to numeric)
_STRING_COLUMNS = frozenset({"PORT_CD", "ITEM", "NATUREOFITEM"})


def _transform_nonsystem(raw_df: pl.DataFrame) -> pl.DataFrame:
    """
    Apply the %tx macro transformation logic for non-system data.

    Translated from E_02_XLS_NONSYSTEM.sas lines 1-50:
    - Read column names from first data row
    - Classify: if name in (PORT_CD, ITEM, NATUREOFITEM) -> string, else numeric
    - Clean column names (remove spaces, special chars)
    - Filter: keep rows where ITEM is not missing
    """
    if len(raw_df) < 2:
        return pl.DataFrame()

    # First row contains column names
    name_row = raw_df.row(0)
    raw_names = [str(v) if v is not None else "" for v in name_row]

    # Clean names: remove spaces, +, -, ', /, (, ), %, &, ., CR/LF
    def _clean(name: str) -> str:
        cleaned = re.sub(r"[ +\-'/(%)&.\r\n]", "", name).upper()
        return cleaned.strip()

    cleaned_names = [_clean(n) for n in raw_names]

    # Data starts from row 2 (index 1, since first row is names)
    data_df = raw_df.slice(1)

    # Rename columns
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

    # Apply type conversions
    exprs: list[pl.Expr] = []
    for col_name in data_df.columns:
        if col_name.startswith("_EMPTY_"):
            continue
        if col_name in _STRING_COLUMNS:
            exprs.append(pl.col(col_name).cast(pl.Utf8).alias(col_name))
        else:
            # Numeric: parse comma-formatted numbers
            exprs.append(
                pl.col(col_name)
                .cast(pl.Utf8)
                .str.replace_all(",", "")
                .cast(pl.Float64, strict=False)
                .alias(col_name)
            )

    if exprs:
        data_df = data_df.select(exprs)

    # Filter: keep rows where ITEM is not missing
    if "ITEM" in data_df.columns:
        data_df = data_df.filter(
            pl.col("ITEM").is_not_null() & (pl.col("ITEM").cast(pl.Utf8).str.strip_chars() != "")
        )

    return data_df


def run(config: Config) -> dict[str, pl.DataFrame]:
    """
    Import non-system adjustment Excel files.

    Translated from E_02_XLS_NONSYSTEM.sas::

        %nonsysImport(OGL outstanding for Basel_&st_RptYMD._RMG.xls, nonsystem);
        %nonsysImport(HKCBF Non_Sys_&st_RptYMD..xls, ns_hkcbf);

    Parameters
    ----------
    config : Config
        Application configuration.

    Returns
    -------
    dict[str, pl.DataFrame]
        Keys: ``nonsystem``, ``ns_hkcbf``
    """
    results: dict[str, pl.DataFrame] = {}
    xls_dir = Path(config.dir_xls)
    rpt_ymd = config.st_rpt_ymd
    rpt_month = config.rpt_month
    fmd_dir = xls_dir / f"FMD_{rpt_month}"

    imports = [
        (f"OGL outstanding for Basel_{rpt_ymd}_RMG.xls", "nonsystem"),
        (f"HKCBF Non_Sys_{rpt_ymd}.xls", "ns_hkcbf"),
    ]

    for file_name, output_name in imports:
        file_path = fmd_dir / file_name
        logger.info("Importing non-system: %s -> %s", file_path, output_name)

        try:
            raw_df = pl.read_excel(
                source=file_path,
                sheet_name="NonSys_Summary",
                engine="openpyxl",
            )
            # DATAROW=5 means skip first 4 rows (0-based: slice from row 4)
            if len(raw_df) > 4:
                raw_df = raw_df.slice(3)  # Adjust for 0-based indexing after header
            df = _transform_nonsystem(raw_df)
            results[output_name] = df
            logger.info("  -> %s: %d rows", output_name, len(df))
        except FileNotFoundError:
            logger.warning("File not found: %s", file_path)
            results[output_name] = pl.DataFrame()
        except Exception:
            logger.exception("Failed to import %s", file_path)
            results[output_name] = pl.DataFrame()

    return results
