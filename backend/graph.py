"""Neo4j Graph Database Connection

- Manages a single Neo4j driver instance for the app lifetime.
- Provides query helpers for recommendation routes.
- init_graph(app) must be called once during app startup.
"""

from __future__ import annotations

import logging
import os
from neo4j import GraphDatabase

log = logging.getLogger(__name__)

_driver = None


def init_graph(app):
    """Create the Neo4j driver from app config. Called once in app.py."""
    global _driver
    uri      = app.config.get("NEO4J_URI",      "bolt://localhost:7687")
    user     = app.config.get("NEO4J_USER",     "neo4j")
    password = app.config.get("NEO4J_PASSWORD",  "")

    try:
        _driver = GraphDatabase.driver(uri, auth=(user, password))
        _driver.verify_connectivity()
        log.info("Neo4j connected at %s", uri)
    except Exception as e:
        log.warning("Neo4j connection failed: %s — recommendations will be unavailable", e)
        _driver = None


def get_driver():
    return _driver


def neo4j_query(cypher: str, params: dict = None) -> list[dict]:
    """Run a read Cypher query, return list of dicts."""
    if _driver is None:
        return []
    with _driver.session() as session:
        result = session.run(cypher, params or {})
        return [dict(r) for r in result]
