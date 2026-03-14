"""
Dataset utilities — translated from Code/0.LIBRARY/Datasets.sas (lines 6-45).

Provides Python equivalents of SAS macros:
  - %addFieldSuffix -> add_field_suffix()
"""

from __future__ import annotations

import logging

import polars as pl

logger = logging.getLogger(__name__)


def add_field_suffix(
    df: pl.DataFrame,
    suffix: str,
    key_fields: list[str],
    sort: bool = False,
) -> pl.DataFrame:
    """
    Rename all columns NOT in *key_fields* by appending *suffix*.

    Translated from ``Code/0.LIBRARY/Datasets.sas`` lines 6-45::

        %macro addFieldSuffix(inlibds, outlibds, suffix, keyfields, view=N, sort=N);
            %local __keyfield_;
            %let __key_=%sysfunc(compbl(&keyfields.));
            %let __keyfield_=%sysfunc(tranwrd("&__key_.",%str( ),%str(%",%")));
            proc contents data=&inlibds. out=__t_field_(keep=name type format) noprint; run;
            filename c_file temp;
            data _null_;
                file c_file;
                set __t_field_(where=(name not in (&__keyfield_)));
                if _n_=1 then put "rename";
                newname=cat(trim(name),"&suffix.");
                put name "=" newname;
            run;
            ...
        %mend;

    Parameters
    ----------
    df : pl.DataFrame
        Input DataFrame.
    suffix : str
        Suffix to append (e.g. ``"_KW"``).
    key_fields : list[str]
        Column names that should *not* be renamed.
    sort : bool
        If ``True``, sort the result by *key_fields*.

    Returns
    -------
    pl.DataFrame
        DataFrame with non-key columns renamed.
    """
    key_set = set(key_fields)
    rename_map = {
        col: f"{col}{suffix}"
        for col in df.columns
        if col not in key_set
    }

    result = df.rename(rename_map)

    if sort and key_fields:
        result = result.sort(key_fields)

    logger.debug(
        "add_field_suffix: renamed %d columns with suffix '%s'",
        len(rename_map),
        suffix,
    )
    return result
