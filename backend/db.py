"""PostgreSQL Database Connection Pool

- Manages a shared pool of database connections using Flask.
- Provides four helpers for every route to use:
1. query() - Executes a SELECT, reutnr all rows as a list of dicts
2. query_one() - Executes a SELECT, returns the first row as a dict or None
3. execute() - Executes an INSERT/UPDATE/DELETE, returns any result rows as a list of dicts
4. execute_many() - Executes a batch of INSERT/UPDATE/DELETE with a list of parameter dicts"

The connections are borrowed per request and then returned to the pool automatically."""


from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any


import psycopg2
import psycopg2.extras
import psycopg2.pool
from flask import Flask, g

log = logging.getLogger(__name__)


_pool: psycopg2.pool.ThreadedConnectionPool | None = None


"""Creates the PostgreSQL Connection Pool using DB config values from app.config,
   Called once in app.py during app startup.
   Also registers a teardown handler to return connections to the pool at the end of each request."""
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
        cursor_factory = psycopg2.extras.RealDictCursor,
    )
    
    log.info(
        "PostgreSQL Connection Pool Ready (%d-%d conns) -> %s:%s/%s",
        minconn, maxconn,
        app.config["DB_HOST"], app.config["DB_PORT"], app.config["DB_NAME"],
    )
    
    @app.teardown_appcontext
    def _return_conn(exc: BaseException | None) -> None:
        """Returns borrowed connections to the pool at the end of each request"""
        conn = g.pop("db_conn", None)
        if conn is not None:
            if exc is not None:
                conn.rollback()            #Rollback on Exception
            _pool.putconn(conn)
            
            
"""Returns a connection from the current Flask Application Context.
   This same connection is reused for the lifetime of a single request"""            
def get_conn() -> psycopg2.extensions.connection:
    if "pg_conn" not in g:
        if _pool is None:
            raise RuntimeError("Database Pool is not initialized. Call init_db(app) first.")
        g.pg_conn = _pool.getconn()
        g.pg_conn.autocommit = False
    return g.pg_conn


"""Serves as a Internal Context Manager - used by execute() and execute_many()
   Achieves a cursor, commits on success, and rolls back on any exception."""
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


"""Run a SELECT Statement. Return all rows as list of dicts.
   Returns an empty list if no rows are found."""
def query(sql: str, params: dict | None = None) -> list[dict]:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(sql, params or {})
        return [dict(row) for row in (cur.fetchall() or [])]
    

"""Runs a SELECT Statement. Returns the first row as a dict, 
   or None if no rows are found."""
def query_one(sql: str, params: dict | None = None) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None


"""Runs an INSERT, UPDATE, or DELETE Statement and commit. 
   Returns the affected rows as a list of dicts."""
def execute(sql: str, params: dict | None = None) -> list[dict]:
    with _cursor() as cur:
        cur.execute(sql, params or {})
        if cur.description:
            return [dict(row) for row in (cur.fetchall() or [])]
        return []
    

"""Runs the same INSERT, UPDATE or DELETE Statement with a list of parameter dicts and commit."""
def execute_many(sql: str, param_list: list[dict]) -> None:
    with _cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, param_list)