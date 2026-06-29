"""backend/startup_sync.py
========================
Runs the one-time "static" Neo4j seed in a background daemon thread when
Flask starts.  Handles: constraints, User/Artist/Track nodes,
PERFORMED_BY, FOLLOWS, LISTENED_TO (historical), and SIMILAR_TO edges.

After this runs, LISTENED_TO is kept live by the real-time write in
backend/routes/tracks.py (POST /play), so the For You and Graph pages
always reflect the user's current listening history.

Called from backend/app.py:
    from backend.startup_sync import start_background_sync
    start_background_sync(app)
"""

from __future__ import annotations

import logging
import os
import threading

import psycopg2
import psycopg2.extras

log = logging.getLogger(__name__)

BATCH_SIZE = 500


# ── helpers ────────────────────────────────────────────────────────────────────

def _pg_connect():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "music_streaming"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def _run_batch(session, cypher, rows):
    for i in range(0, len(rows), BATCH_SIZE):
        session.run(cypher, rows=rows[i : i + BATCH_SIZE])


# ── sync steps ─────────────────────────────────────────────────────────────────

def _ensure_constraints(session):
    for stmt in [
        "CREATE CONSTRAINT user_id_unique   IF NOT EXISTS FOR (u:User)   REQUIRE u.user_id   IS UNIQUE",
        "CREATE CONSTRAINT track_id_unique  IF NOT EXISTS FOR (t:Track)  REQUIRE t.track_id  IS UNIQUE",
        "CREATE CONSTRAINT artist_id_unique IF NOT EXISTS FOR (a:Artist) REQUIRE a.artist_id IS UNIQUE",
        "CREATE INDEX track_genre_index     IF NOT EXISTS FOR (t:Track)  ON (t.genre)",
    ]:
        session.run(stmt)


def _sync_users(cur, session):
    cur.execute("SELECT user_id, username FROM users")
    rows = [{"user_id": r["user_id"], "username": r["username"]} for r in cur.fetchall()]
    _run_batch(session, """
        UNWIND $rows AS row
        MERGE (u:User {user_id: row.user_id})
        SET u.username = row.username
    """, rows)
    log.info("[sync] users: %d", len(rows))


def _sync_artists(cur, session):
    cur.execute("SELECT artist_id, name FROM artists")
    rows = [{"artist_id": r["artist_id"], "name": r["name"]} for r in cur.fetchall()]
    _run_batch(session, """
        UNWIND $rows AS row
        MERGE (a:Artist {artist_id: row.artist_id})
        SET a.name = row.name
    """, rows)
    log.info("[sync] artists: %d", len(rows))


def _sync_tracks(cur, session):
    cur.execute("""
        SELECT t.track_id, t.title, t.play_count, g.name AS genre
        FROM tracks t
        LEFT JOIN genres g ON g.genre_id = t.genre_id
    """)
    rows = [
        {"track_id": r["track_id"], "title": r["title"],
         "genre": r["genre"], "play_count": r["play_count"]}
        for r in cur.fetchall()
    ]
    _run_batch(session, """
        UNWIND $rows AS row
        MERGE (t:Track {track_id: row.track_id})
        SET t.title      = row.title,
            t.genre      = row.genre,
            t.play_count = row.play_count
    """, rows)
    log.info("[sync] tracks: %d", len(rows))


def _sync_performed_by(cur, session):
    cur.execute("""
        SELECT t.track_id, ar.artist_id
        FROM tracks t
        JOIN albums al  ON al.album_id  = t.album_id
        JOIN artists ar ON ar.artist_id = al.artist_id
    """)
    rows = [{"track_id": r["track_id"], "artist_id": r["artist_id"]} for r in cur.fetchall()]
    _run_batch(session, """
        UNWIND $rows AS row
        MATCH (t:Track  {track_id:  row.track_id})
        MATCH (a:Artist {artist_id: row.artist_id})
        MERGE (t)-[:PERFORMED_BY]->(a)
    """, rows)
    log.info("[sync] PERFORMED_BY: %d", len(rows))


def _sync_listened_to(cur, session):
    cur.execute("""
        SELECT user_id, track_id,
               COUNT(*)       AS play_count,
               MAX(played_at) AS last_played
        FROM play_history
        GROUP BY user_id, track_id
    """)
    rows = [
        {
            "user_id":    r["user_id"],
            "track_id":   r["track_id"],
            "count":      r["play_count"],
            "last_played": r["last_played"].isoformat() if r["last_played"] else None,
        }
        for r in cur.fetchall()
    ]
    if rows:
        _run_batch(session, """
            UNWIND $rows AS row
            MATCH (u:User  {user_id:  row.user_id})
            MATCH (t:Track {track_id: row.track_id})
            MERGE (u)-[r:LISTENED_TO]->(t)
            SET r.count       = row.count,
                r.last_played = row.last_played
        """, rows)
    log.info("[sync] LISTENED_TO: %d", len(rows))


def _sync_follows(cur, session):
    cur.execute("SELECT user_id, artist_id, followed_at FROM user_follows_artist")
    rows = [
        {
            "user_id":    r["user_id"],
            "artist_id":  r["artist_id"],
            "followed_at": r["followed_at"].isoformat() if r["followed_at"] else None,
        }
        for r in cur.fetchall()
    ]
    if rows:
        _run_batch(session, """
            UNWIND $rows AS row
            MATCH (u:User   {user_id:   row.user_id})
            MATCH (a:Artist {artist_id: row.artist_id})
            MERGE (u)-[r:FOLLOWS]->(a)
            SET r.followed_at = row.followed_at
        """, rows)
    log.info("[sync] FOLLOWS: %d", len(rows))


def _seed_similar_to(session):
    session.run("""
        MATCH (a:Artist)<-[:PERFORMED_BY]-(t:Track)
        WHERE t.genre IS NOT NULL
        WITH t.genre AS genre, collect(DISTINCT a) AS artists
        WHERE size(artists) > 1
        UNWIND range(0, size(artists) - 2) AS i
        UNWIND range(i + 1, size(artists) - 1) AS j
        WITH artists[i] AS a1, artists[j] AS a2
        MERGE (a1)-[r:SIMILAR_TO]-(a2)
        SET r.similarity_score = coalesce(r.similarity_score, 0) + 1
    """)
    log.info("[sync] SIMILAR_TO computed")


# ── entry point ────────────────────────────────────────────────────────────────

def _run_sync(driver):
    """Full sync — runs once in a daemon thread at startup."""
    log.info("[sync] Background Neo4j sync starting…")
    pg_conn = None
    try:
        pg_conn = _pg_connect()
        cur = pg_conn.cursor()

        with driver.session() as s:
            _ensure_constraints(s)
            _sync_users(cur, s)
            _sync_artists(cur, s)
            _sync_tracks(cur, s)
            _sync_performed_by(cur, s)
            _sync_listened_to(cur, s)
            _sync_follows(cur, s)
            _seed_similar_to(s)

        log.info("[sync] Background Neo4j sync complete ✓")

    except Exception:
        log.exception("[sync] Background sync failed — graph features may be stale")
    finally:
        if pg_conn:
            pg_conn.close()


def start_background_sync(app):
    """Call this once from create_app() after init_graph().
    Spawns a daemon thread so Flask can start serving immediately."""
    from backend.graph import get_driver

    driver = get_driver()
    if driver is None:
        log.warning("[sync] Neo4j driver not available — skipping background sync")
        return

    t = threading.Thread(target=_run_sync, args=(driver,), daemon=True, name="neo4j-startup-sync")
    t.start()
    log.info("[sync] Background sync thread started (pid-agnostic daemon)")
