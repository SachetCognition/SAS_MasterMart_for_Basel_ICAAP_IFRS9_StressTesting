"""
Configuration module — translated from 00. STARTSCRIPT.sas (lines 13-65).

All %let macro variables are represented as fields of the Config dataclass.
Derived date formats are exposed as properties.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class OracleConfig:
    """Oracle connection settings."""

    dsn: str = "iw_connection_string"
    pool_min: int = 2
    pool_max: int = 10
    pool_increment: int = 1


@dataclass
class ExtractionConfig:
    """Parallel extraction settings."""

    batch_size: int = 10000
    max_workers: int = 4
    entities: list[str] = field(default_factory=lambda: ["kw", "cf", "sz", "vc"])


@dataclass
class Config:
    """
    Central configuration translated from SAS %let macro variables.

    Attributes
    ----------
    rpt_month : str
        Reporting month in YYYYMM format (e.g. "201412").
        Corresponds to SAS ``&st_RptMth``.
    dt_rpt_month : date
        End-of-month date for the reporting period.
        Corresponds to SAS ``&dt_RptMth``.
    dt_f_x2s : int
        Excel-to-SAS date offset (21916).
    ind_icaap : str
        ICAAP indicator flag.
    """

    rpt_month: str = "201412"
    dt_f_x2s: int = 21916
    ind_icaap: str = ""

    # ----- path configuration -----
    dir_base: str = ""
    dir_pbg: str = ""
    dir_ccd: str = ""
    dir_aps: str = ""
    dir_cardlink: str = ""
    dir_root: str = ""
    dir_xls: str = ""
    dir_xlssiw: str = ""
    dir_siw: str = ""
    dir_stg: str = ""
    dir_fact: str = ""
    dir_mart: str = ""
    dir_rpt: str = ""

    # ----- sub-configs -----
    oracle: OracleConfig = field(default_factory=OracleConfig)
    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)

    def __post_init__(self) -> None:
        self.auto_rpt_month()

    # ------------------------------------------------------------------
    # Derived date properties (translated from SAS putn / intnx calls)
    # ------------------------------------------------------------------

    @property
    def dt_rpt_month(self) -> date:
        """End-of-month date for the reporting period."""
        year = int(self.rpt_month[:4])
        month = int(self.rpt_month[4:6])
        # Move to first of *next* month, then subtract 1 day
        if month == 12:
            return date(year + 1, 1, 1) - timedelta(days=1)
        return date(year, month + 1, 1) - timedelta(days=1)

    @property
    def st_rpt_ymd(self) -> str:
        """YYYYMMDD string — corresponds to SAS ``&st_RptYMD`` (yymmddn8.)."""
        return self.dt_rpt_month.strftime("%Y%m%d")

    @property
    def st_rpt_ymd6(self) -> str:
        """YYMMDD string — corresponds to SAS ``&st_RptYMD6`` (yymmddn6.)."""
        return self.dt_rpt_month.strftime("%y%m%d")

    @property
    def st_rpt_yymm(self) -> str:
        """YYMM string — corresponds to SAS ``&st_RptYYMM`` (yymmn4.)."""
        return self.dt_rpt_month.strftime("%y%m")

    # ------------------------------------------------------------------
    # Auto reporting month (translated from %Auto_RptMth macro)
    # ------------------------------------------------------------------

    def auto_rpt_month(self) -> None:
        """
        If ``rpt_month`` is blank, default to previous month-end in YYYYMM.

        Translated from ``Code/0.LIBRARY/Macro.sas`` lines 15-23::

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
        if not self.rpt_month or not self.rpt_month.strip():
            today = date.today()
            first_of_month = today.replace(day=1)
            prev_month_end = first_of_month - timedelta(days=1)
            self.rpt_month = prev_month_end.strftime("%Y%m")
            logger.info("rpt_month auto-set to %s", self.rpt_month)

    # ------------------------------------------------------------------
    # Factory classmethod
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: str | Path | None = None) -> Config:
        """
        Load configuration from a YAML file.

        Parameters
        ----------
        path : str or Path, optional
            Path to settings.yaml.  Defaults to ``config/settings.yaml``
            relative to the project root.
        """
        if path is None:
            path = _PROJECT_ROOT / "config" / "settings.yaml"
        path = Path(path)

        with open(path, encoding="utf-8") as fh:
            raw: dict[str, Any] = yaml.safe_load(fh) or {}

        rpt_month: str = str(raw.get("rpt_month", "201412"))
        ind_icaap: str = str(raw.get("ind_icaap", ""))
        dt_f_x2s: int = int(raw.get("dt_f_x2s", 21916))

        paths: dict[str, str] = raw.get("paths", {})
        data_layers: dict[str, str] = raw.get("data_layers", {})

        dir_base = paths.get("base", "")
        dir_root = f"{dir_base}/#SAS.Logic" if dir_base else ""

        def _resolve_layer(template: str) -> str:
            return template.replace("{root}", dir_root)

        oracle_raw: dict[str, Any] = raw.get("oracle", {})
        extraction_raw: dict[str, Any] = raw.get("extraction", {})

        return cls(
            rpt_month=rpt_month,
            dt_f_x2s=dt_f_x2s,
            ind_icaap=ind_icaap,
            dir_base=dir_base,
            dir_pbg=paths.get("pbg", ""),
            dir_ccd=paths.get("ccd", ""),
            dir_aps=paths.get("aps", ""),
            dir_cardlink=paths.get("cardlink", ""),
            dir_root=dir_root,
            dir_xls=_resolve_layer(data_layers.get("input_xls", "")),
            dir_xlssiw=_resolve_layer(data_layers.get("input_xlssiw", "")),
            dir_siw=_resolve_layer(data_layers.get("siw", "")),
            dir_stg=_resolve_layer(data_layers.get("staging", "")),
            dir_fact=_resolve_layer(data_layers.get("fact", "")),
            dir_mart=_resolve_layer(data_layers.get("mart", "")),
            dir_rpt=_resolve_layer(data_layers.get("report", "")),
            oracle=OracleConfig(
                dsn=oracle_raw.get("dsn", "iw_connection_string"),
                pool_min=oracle_raw.get("pool_min", 2),
                pool_max=oracle_raw.get("pool_max", 10),
                pool_increment=oracle_raw.get("pool_increment", 1),
            ),
            extraction=ExtractionConfig(
                batch_size=extraction_raw.get("batch_size", 10000),
                max_workers=extraction_raw.get("max_workers", 4),
                entities=extraction_raw.get("entities", ["kw", "cf", "sz", "vc"]),
            ),
        )
