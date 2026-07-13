"""PostgreSQL connection pool helpers.

query()     — SELECT, returns list of dicts
query_one() — SELECT, returns first row or None
execute()   — INSERT/UPDATE/DELETE, returns RETURNING rows
get_conn()  — raw connection (for multi-statement transactions)
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import psycopg2.pool
from flask import Flask, g

log = logging.getLogger(__name__)

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def init_db(app: Flask) -> None:
    global _pool

    minconn = int(os.getenv("DB_POOL_MIN", 2))
    maxconn = int(os.getenv("DB_POOL_MAX", 10))

    _pool = psycopg2.pool.ThreadedConnectionPool(
        minconn,
        maxconn,
        host=app.config["DB_HOST"],
        port=app.config["DB_PORT"],
        dbname=app.config["DB_NAME"],
        user=app.config["DB_USER"],
        password=app.config["DB_PASSWORD"],
        cursor_factory=psycopg2.extras.RealDictCursor,
    )

    log.info(
        "PostgreSQL pool ready (%d-%d conns) -> %s:%s/%s",
        minconn, maxconn,
        app.config["DB_HOST"], app.config["DB_PORT"], app.config["DB_NAME"],
    )

    @app.teardown_appcontext
    def _return_conn(exc: BaseException | None) -> None:
        conn = g.pop("pg_conn", None)
        if conn is not None:
            if exc is not None:
                conn.rollback()
            _pool.putconn(conn)


def get_conn() -> psycopg2.extensions.connection:
    if "pg_conn" not in g:
        if _pool is None:
            raise RuntimeError("Call init_db(app) before using the database.")
        g.pg_conn = _pool.getconn()
        g.pg_conn.autocommit = False
    return g.pg_conn


@contextmanager
def _cursor():
    conn = get_conn()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def query(sql: str, params: dict | None = None) -> list[dict]:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(sql, params or {})
        return [dict(row) for row in (cur.fetchall() or [])]


def query_one(sql: str, params: dict | None = None) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: dict | None = None) -> list[dict]:
    with _cursor() as cur:
        cur.execute(sql, params or {})
        if cur.description:
            return [dict(row) for row in (cur.fetchall() or [])]
        return []
