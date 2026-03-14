"""
APS and PIL data extraction — translated from Code/0.SIW_IMPORT/E_IMPORT_APS_PIL.sas (5 lines).

Imports credit card performance data (PIL, CARD) and application data
from SAS libraries into the SIW layer.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config

logger = logging.getLogger(__name__)


def import_aps_pil(config: Config) -> dict[str, pl.DataFrame]:
    """
    Import APS and PIL data files.

    Translated from E_IMPORT_APS_PIL.sas::

        data siw.pil_&st_RptMth.;       set crdk.pil&st_RptYMD6.;  run;
        data siw.card_&st_RptMth.;       set crdk.card&st_RptYMD6.; run;
        data siw.app_combine;            set aps.app_combine;        run;

    In the Python migration, these source datasets are expected as Parquet
    files in the configured directories, rather than SAS library files.

    Parameters
    ----------
    config : Config
        Application configuration.

    Returns
    -------
    dict[str, pl.DataFrame]
        Keys: ``pil``, ``card``, ``app_combine``
    """
    results: dict[str, pl.DataFrame] = {}
    rpt_ymd6 = config.st_rpt_ymd6

    # PIL data — from CardLink data mart
    pil_path = Path(config.dir_cardlink) / f"pil{rpt_ymd6}.parquet"
    try:
        results["pil"] = pl.read_parquet(pil_path)
        logger.info("Imported PIL: %d rows from %s", len(results["pil"]), pil_path)
    except FileNotFoundError:
        logger.warning("PIL file not found: %s", pil_path)
        results["pil"] = pl.DataFrame()
    except Exception:
        logger.exception("Failed to import PIL from %s", pil_path)
        results["pil"] = pl.DataFrame()

    # CARD data — from CardLink data mart
    card_path = Path(config.dir_cardlink) / f"card{rpt_ymd6}.parquet"
    try:
        results["card"] = pl.read_parquet(card_path)
        logger.info("Imported CARD: %d rows from %s", len(results["card"]), card_path)
    except FileNotFoundError:
        logger.warning("CARD file not found: %s", card_path)
        results["card"] = pl.DataFrame()
    except Exception:
        logger.exception("Failed to import CARD from %s", card_path)
        results["card"] = pl.DataFrame()

    # Application data — from APS data mart
    app_path = Path(config.dir_aps) / "app_combine.parquet"
    try:
        results["app_combine"] = pl.read_parquet(app_path)
        logger.info("Imported app_combine: %d rows from %s", len(results["app_combine"]), app_path)
    except FileNotFoundError:
        logger.warning("app_combine not found: %s", app_path)
        results["app_combine"] = pl.DataFrame()
    except Exception:
        logger.exception("Failed to import app_combine from %s", app_path)
        results["app_combine"] = pl.DataFrame()

    return results
