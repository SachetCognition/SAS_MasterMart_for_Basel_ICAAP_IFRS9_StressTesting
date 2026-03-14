"""
Oracle connection manager — provides OracleConnector class.

Wraps ``oracledb`` with connection pooling, context-manager support,
and a high-level ``extract_table()`` method that returns polars DataFrames.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl

if TYPE_CHECKING:
    from datetime import date

    from config.settings import OracleConfig

logger = logging.getLogger(__name__)


class OracleConnector:
    """
    Oracle database connector with connection pooling.

    Usage::

        with OracleConnector(config.oracle) as db:
            df = db.extract_table("iw.vi_iambs_kw_car", date_filter=config.dt_rpt_month)
    """

    def __init__(self, oracle_config: OracleConfig) -> None:
        self._config = oracle_config
        self._pool: Any = None

    def __enter__(self) -> OracleConnector:
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def connect(self) -> None:
        """Create the connection pool."""
        import oracledb

        self._pool = oracledb.create_pool(
            dsn=self._config.dsn,
            min=self._config.pool_min,
            max=self._config.pool_max,
            increment=self._config.pool_increment,
        )
        logger.info("Oracle connection pool created (dsn=%s)", self._config.dsn)

    def close(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            self._pool.close(force=True)
            self._pool = None
            logger.info("Oracle connection pool closed")

    def get_connection(self) -> Any:
        """Acquire a connection from the pool."""
        if self._pool is None:
            raise RuntimeError("Connection pool is not initialised. Call connect() first.")
        return self._pool.acquire()

    def extract_table(
        self,
        table_name: str,
        date_filter: date | None = None,
        batch_size: int = 10_000,
        output_path: str | Path | None = None,
    ) -> pl.DataFrame:
        """
        Extract a full table/view from Oracle into a polars DataFrame.

        Parameters
        ----------
        table_name : str
            Fully qualified Oracle table or view name.
        date_filter : date, optional
            If provided, filter rows where month-end of ``as_of_dt`` matches.
        batch_size : int
            Cursor array size for fetch performance.
        output_path : str or Path, optional
            If provided, also persist result as Parquet.

        Returns
        -------
        pl.DataFrame
        """
        import pyarrow as pa

        t0 = time.perf_counter()
        conn = self.get_connection()

        try:
            cursor = conn.cursor()
            cursor.arraysize = batch_size

            if date_filter is not None:
                sql = (
                    f"SELECT * FROM {table_name} "  # noqa: S608
                    "WHERE TRUNC(LAST_DAY(CAST(as_of_dt AS DATE))) = :dt"
                )
                cursor.execute(sql, {"dt": date_filter})
            else:
                sql = f"SELECT * FROM {table_name}"  # noqa: S608
                cursor.execute(sql)

            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            cursor.close()
        finally:
            self._pool.release(conn)

        elapsed = time.perf_counter() - t0
        logger.info(
            "Extracted %d rows from %s in %.2fs",
            len(rows),
            table_name,
            elapsed,
        )

        # Build DataFrame via PyArrow for zero-copy efficiency
        if rows:
            arrays = list(zip(*rows))
            arrow_arrays = [pa.array(col) for col in arrays]
            arrow_table = pa.table(dict(zip(columns, arrow_arrays)))
            df = pl.from_arrow(arrow_table)
        else:
            df = pl.DataFrame(schema={col: pl.Utf8 for col in columns})

        # Optionally persist
        if output_path is not None:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            df.write_parquet(output_path)
            logger.info("Persisted to %s", output_path)

        return df
