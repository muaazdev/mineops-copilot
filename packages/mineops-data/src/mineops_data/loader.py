"""Bulk-load generated CSVs into Postgres with ``COPY`` (psycopg 3), in one transaction."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import psycopg
from psycopg import sql

from mineops_data.generator import TABLE_COLUMNS

log = logging.getLogger(__name__)

# Truncated together (CASCADE-free: the list covers every FK edge inside ops).
OPS_TABLES = (*TABLE_COLUMNS, "work_order_drafts")
_CHUNK = 1 << 16


def load(conninfo: str, src: Path) -> dict[str, int]:
    """Truncate-and-reload every ops table from ``src``. All-or-nothing."""
    missing = [t for t in TABLE_COLUMNS if not (src / f"{t}.csv").is_file()]
    if missing:
        raise FileNotFoundError(f"missing CSVs in {src}: {', '.join(missing)}")

    counts: dict[str, int] = {}
    with psycopg.connect(conninfo) as conn, conn.transaction():
        truncate = sql.SQL("TRUNCATE {}").format(
            sql.SQL(", ").join(sql.Identifier("ops", t) for t in OPS_TABLES)
        )
        conn.execute(truncate)
        for table, expected_cols in TABLE_COLUMNS.items():
            path = src / f"{table}.csv"
            with path.open(encoding="utf-8", newline="") as fh:
                header = next(csv.reader(fh))
            if tuple(header) != expected_cols:
                raise ValueError(f"{path.name}: header {header} != {list(expected_cols)}")
            stmt = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv, HEADER true)").format(
                sql.Identifier("ops", table),
                sql.SQL(", ").join(map(sql.Identifier, header)),
            )
            with conn.cursor() as cur:
                with cur.copy(stmt) as copy, path.open("rb") as fh:
                    while chunk := fh.read(_CHUNK):
                        copy.write(chunk)
                counts[table] = cur.rowcount
            log.info("loaded table", extra={"table": table, "rows": counts[table]})
    return counts
