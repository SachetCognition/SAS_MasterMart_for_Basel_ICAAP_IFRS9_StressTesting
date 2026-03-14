"""
Report generation utilities — replaces SAS PROC TABULATE, ODS HTML, and PROC EXPORT.

Provides:
  - write_tabulate_report()  — pivot-table style report to Excel
  - write_summary_html()     — HTML table output
  - write_excel_report()     — direct Excel output
"""

from __future__ import annotations

import logging
from pathlib import Path

import polars as pl

logger = logging.getLogger(__name__)


def write_tabulate_report(
    df: pl.DataFrame,
    class_cols: list[str],
    var_cols: list[str],
    format_maps: dict[str, dict[str, str]] | None = None,
    output_path: str | Path = "report.xlsx",
    title: str = "Report",
    sheet_name: str = "Sheet1",
) -> Path:
    """
    Create a pivot-table style report — replaces SAS PROC TABULATE.

    Groups data by *class_cols*, aggregates *var_cols* (sum), and writes
    the result to an Excel file with formatting.

    Parameters
    ----------
    df : pl.DataFrame
        Input data.
    class_cols : list[str]
        Columns to group by (equivalent to ``CLASS`` statement).
    var_cols : list[str]
        Numeric columns to aggregate (equivalent to ``VAR`` statement).
    format_maps : dict, optional
        ``{column: {value: label}}`` for formatting class column values.
    output_path : str or Path
        Destination Excel file path.
    title : str
        Report title written to the first row.
    sheet_name : str
        Excel sheet name.

    Returns
    -------
    Path
        The output file path.
    """
    import xlsxwriter

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Apply format maps if provided
    working_df = df.clone()
    if format_maps:
        for col, mapping in format_maps.items():
            if col in working_df.columns:
                working_df = working_df.with_columns(
                    pl.col(col).cast(pl.Utf8).replace(mapping).alias(col)
                )

    # Group and aggregate
    agg_exprs = [pl.col(c).sum().alias(c) for c in var_cols if c in working_df.columns]
    valid_class = [c for c in class_cols if c in working_df.columns]

    if valid_class and agg_exprs:
        summary = working_df.group_by(valid_class).agg(agg_exprs).sort(valid_class)
    else:
        summary = working_df.select([c for c in var_cols if c in working_df.columns])

    # Write to Excel with xlsxwriter
    workbook = xlsxwriter.Workbook(str(output_path))
    worksheet = workbook.add_worksheet(sheet_name)

    # Title format
    title_fmt = workbook.add_format({"bold": True, "font_size": 14})
    header_fmt = workbook.add_format({"bold": True, "bg_color": "#4472C4", "font_color": "white"})
    number_fmt = workbook.add_format({"num_format": "#,##0.00"})

    # Write title
    worksheet.write(0, 0, title, title_fmt)

    # Write headers
    all_cols = summary.columns
    for col_idx, col_name in enumerate(all_cols):
        worksheet.write(2, col_idx, col_name, header_fmt)

    # Write data
    for row_idx, row in enumerate(summary.iter_rows()):
        for col_idx, value in enumerate(row):
            if isinstance(value, (int, float)):
                worksheet.write_number(row_idx + 3, col_idx, value, number_fmt)
            else:
                worksheet.write(row_idx + 3, col_idx, str(value) if value is not None else "")

    # Auto-fit column widths (approximate)
    for col_idx, col_name in enumerate(all_cols):
        max_len = max(len(str(col_name)), 12)
        worksheet.set_column(col_idx, col_idx, max_len + 2)

    workbook.close()
    logger.info("Wrote tabulate report: %s (%d rows)", output_path, len(summary))
    return output_path


def write_summary_html(
    df: pl.DataFrame,
    output_path: str | Path,
    title: str = "Summary Report",
    class_cols: list[str] | None = None,
    var_cols: list[str] | None = None,
) -> Path:
    """
    Generate an HTML table report — replaces SAS ODS HTML.

    Parameters
    ----------
    df : pl.DataFrame
        Input data.
    output_path : str or Path
        Destination HTML file path.
    title : str
        HTML page title.
    class_cols : list[str], optional
        If provided, group by these columns first.
    var_cols : list[str], optional
        If provided with class_cols, aggregate these columns.

    Returns
    -------
    Path
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Optionally aggregate
    if class_cols and var_cols:
        agg_exprs = [pl.col(c).sum().alias(c) for c in var_cols if c in df.columns]
        valid_class = [c for c in class_cols if c in df.columns]
        if valid_class and agg_exprs:
            display_df = df.group_by(valid_class).agg(agg_exprs).sort(valid_class)
        else:
            display_df = df
    else:
        display_df = df

    # Build HTML
    html_parts = [
        "<!DOCTYPE html>",
        "<html><head>",
        f"<title>{title}</title>",
        "<style>",
        "body { font-family: Arial, sans-serif; margin: 20px; }",
        "table { border-collapse: collapse; width: 100%; }",
        "th { background-color: #4472C4; color: white; padding: 8px; text-align: left; }",
        "td { border: 1px solid #ddd; padding: 6px; }",
        "tr:nth-child(even) { background-color: #f2f2f2; }",
        ".numeric { text-align: right; }",
        "</style>",
        "</head><body>",
        f"<h1>{title}</h1>",
        f"<p>Rows: {len(display_df)} | Columns: {len(display_df.columns)}</p>",
        "<table>",
        "<thead><tr>",
    ]

    # Header row
    for col in display_df.columns:
        html_parts.append(f"<th>{col}</th>")
    html_parts.append("</tr></thead><tbody>")

    # Data rows
    for row in display_df.iter_rows():
        html_parts.append("<tr>")
        for value in row:
            css_class = ' class="numeric"' if isinstance(value, (int, float)) else ""
            if isinstance(value, float):
                html_parts.append(f"<td{css_class}>{value:,.2f}</td>")
            elif value is None:
                html_parts.append(f"<td{css_class}></td>")
            else:
                html_parts.append(f"<td{css_class}>{value}</td>")
        html_parts.append("</tr>")

    html_parts.extend(["</tbody></table>", "</body></html>"])

    output_path.write_text("\n".join(html_parts), encoding="utf-8")
    logger.info("Wrote HTML report: %s (%d rows)", output_path, len(display_df))
    return output_path


def write_excel_report(
    df: pl.DataFrame,
    output_path: str | Path,
    sheet_name: str = "Sheet1",
) -> Path:
    """
    Write a DataFrame directly to Excel — replaces SAS PROC EXPORT.

    Parameters
    ----------
    df : pl.DataFrame
        Data to export.
    output_path : str or Path
        Destination Excel file.
    sheet_name : str
        Sheet name.

    Returns
    -------
    Path
    """
    import xlsxwriter

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    workbook = xlsxwriter.Workbook(str(output_path))
    worksheet = workbook.add_worksheet(sheet_name)

    header_fmt = workbook.add_format({"bold": True, "bg_color": "#4472C4", "font_color": "white"})
    number_fmt = workbook.add_format({"num_format": "#,##0.00"})

    # Headers
    for col_idx, col_name in enumerate(df.columns):
        worksheet.write(0, col_idx, col_name, header_fmt)

    # Data
    for row_idx, row in enumerate(df.iter_rows()):
        for col_idx, value in enumerate(row):
            if isinstance(value, (int, float)):
                worksheet.write_number(row_idx + 1, col_idx, value, number_fmt)
            elif value is None:
                worksheet.write(row_idx + 1, col_idx, "")
            else:
                worksheet.write(row_idx + 1, col_idx, str(value))

    # Auto-fit
    for col_idx, col_name in enumerate(df.columns):
        worksheet.set_column(col_idx, col_idx, max(len(col_name), 10) + 2)

    workbook.close()
    logger.info("Wrote Excel report: %s (%d rows)", output_path, len(df))
    return output_path
