"""
Oracle IW data extraction — translated from Code/0.SIW_IMPORT/E_IMPORT_IW.sas (63 lines).

Extracts ~30 Oracle IW views for 4 entities (KW, CF, SZ, VC) plus static tables,
saving each as Parquet in the SIW data layer directory.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from config.settings import Config
    from lib.db_connector import OracleConnector

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Oracle view definitions organized by category
# Translated from E_IMPORT_IW.sas lines 1-63
# ---------------------------------------------------------------------------

# Views that are extracted per-entity (kw, cf, sz, vc) with date filter
ENTITY_VIEWS: dict[str, list[str]] = {
    # CMV (Current Market Value) — lines 2-6
    "ac_cov": ["vi_iambs_{entity}_ac_cov"],
    # EAD and RWA — lines 8-12
    "car": ["vi_iambs_{entity}_car"],
    # Collateral Information — lines 14-18
    "coll": ["vi_iambs_{entity}_coll"],
    # Collateral with allocation — lines 20-24
    "alc_dtl": ["vi_iambs_{entity}_alc_dtl"],
    # Account exposure — lines 33-37
    "ac_exp": ["vi_iambs_{entity}_ac_exp"],
}

# Views extracted once (not per-entity) with date filter
SINGLE_VIEWS: list[str] = [
    # SZ-specific loans — line 27
    "vi_iamcn_sz_loans",
    # Customer info — line 28
    "vi_sgmfc_cust",
    # Customer monthly (excl. Singapore and CBI China) — line 31
    "vi_iamrm_cust_noid",
    # Rating information — lines 39-42
    "vi_iamop_corp_rating",
    "vi_iamic_cap_excpt",
    "vi_iamic_cap_smry",
    # CVA information — lines 44-48
    "vi_iambs_cva_ac_exp",
    "vi_iambs_cva_grp_exp",
    "vi_iambs_cva_adj",
    "vi_iambs_cva_rtg",
    # ICAAP information — line 51
    "vi_iamic_cap_dtl",
]

# Static tables (no date filter) — lines 57-62
STATIC_TABLES: dict[str, str] = {
    "vi_iacbs_cust_elim_upd": "vi_iacbs_cust_elim_upd",
    "vi_iacic_cap_coll_typ_upd": "vi_iacic_cap_coll_typ_upd",
    "vi_iacic_cap_userparm_upd": "vi_iacic_cap_user_parm_upd",
    "vi_iacic_cap_clsundwn_upd": "vi_iacic_cap_cls_undwn_upd",
    "vi_iambs_cva_result": "vi_iambs_cva_result",
}


def _extract_single_view(
    connector: OracleConnector,
    view_name: str,
    output_path: Path,
    config: Config,
) -> tuple[str, pl.DataFrame]:
    """Extract a single Oracle view and save to Parquet."""
    logger.info("Extracting %s -> %s", view_name, output_path)
    df = connector.extract_table(
        table_name=f"iw.{view_name}",
        date_filter=config.dt_rpt_month,
        batch_size=config.extraction.batch_size,
        output_path=output_path,
    )
    return view_name, df


def import_all_iw_views(
    config: Config,
    connector: OracleConnector,
) -> dict[str, pl.DataFrame]:
    """
    Extract all Oracle IW views for the reporting month.

    Translated from E_IMPORT_IW.sas.  Uses ThreadPoolExecutor to
    parallelize extraction across entities.

    Parameters
    ----------
    config : Config
        Application configuration.
    connector : OracleConnector
        Active Oracle connection manager.

    Returns
    -------
    dict[str, pl.DataFrame]
        ``{output_name: DataFrame, ...}``
    """
    results: dict[str, pl.DataFrame] = {}
    siw_dir = Path(config.dir_siw)
    siw_dir.mkdir(parents=True, exist_ok=True)
    rpt = config.rpt_month
    entities = config.extraction.entities

    tasks: list[tuple[str, str, Path]] = []

    # 1. Per-entity views
    for category, view_templates in ENTITY_VIEWS.items():
        for template in view_templates:
            for entity in entities:
                view_name = template.format(entity=entity)
                output_name = f"{view_name}_{rpt}"
                output_path = siw_dir / f"{output_name}.parquet"
                tasks.append((view_name, output_name, output_path))

    # 2. Single views with date filter
    for view_name in SINGLE_VIEWS:
        output_name = f"{view_name}_{rpt}"
        output_path = siw_dir / f"{output_name}.parquet"
        tasks.append((view_name, output_name, output_path))

    # Execute with thread pool
    max_workers = config.extraction.max_workers
    logger.info(
        "Starting IW extraction: %d views with %d workers",
        len(tasks),
        max_workers,
    )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for view_name, output_name, output_path in tasks:
            future = executor.submit(
                _extract_single_view,
                connector,
                view_name,
                output_path,
                config,
            )
            futures[future] = output_name

        for future in as_completed(futures):
            output_name = futures[future]
            try:
                _, df = future.result()
                results[output_name] = df
            except Exception:
                logger.exception("Failed to extract %s", output_name)

    # 3. Static tables (no date filter)
    for output_key, source_table in STATIC_TABLES.items():
        output_name = f"{output_key}_{rpt}"
        output_path = siw_dir / f"{output_name}.parquet"
        logger.info("Extracting static table %s -> %s", source_table, output_path)
        try:
            df = connector.extract_table(
                table_name=f"iw.{source_table}",
                date_filter=None,
                output_path=output_path,
            )
            results[output_name] = df
        except Exception:
            logger.exception("Failed to extract static table %s", source_table)

    logger.info("IW extraction complete: %d datasets loaded", len(results))
    return results
