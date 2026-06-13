"""
nosql/sync.py
=============
Syncs data from PostgreSQL into Neo4j.

Run after sql/seed.py has populated the relational database.

What it syncs:
  1. User nodes          ← users table
  2. Artist nodes        ← artists table
  3. Track nodes         ← tracks + genres tables
  4. PERFORMED_BY edges  ← tracks → albums → artists
  5. LISTENED_TO edges   ← play_history (aggregated per user/track)
  6. FOLLOWS edges       ← user_follows_artist

Usage:
    cd INF2003-Database-Project
    source venv/bin/activate
    python3 nosql/sync.py
"""

import os
import sys
import psycopg2
import psycopg2.extras
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────────
PG_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "dbname":   os.getenv("DB_NAME",     "music_streaming"),
    "user":     os.getenv("DB_USER",     "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

BATCH_SIZE = 500  # rows per Neo4j transaction batch

# ── Helpers ────────────────────────────────────────────────────────────────────

def pg_connect():
    try:
        conn = psycopg2.connect(**PG_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)
        print(f"  [PG]  Connected to '{PG_CONFIG['dbname']}' on {PG_CONFIG['host']}")
        return conn
    except Exception as e:
        print(f"  [ERR] PostgreSQL connection failed: {e}")
        sys.exit(1)

def neo4j_connect():
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        print(f"  [N4J] Connected to Neo4j at {NEO4J_URI}")
        return driver
    except Exception as e:
        print(f"  [ERR] Neo4j connection failed: {e}")
        sys.exit(1)

def batched(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def run_batch(session, query, rows):
    """Run a Cypher query for each batch of rows using UNWIND."""
    total = 0
    for batch in batched(rows, BATCH_SIZE):
        session.run(query, rows=batch)
        total += len(batch)
    return total

# ── Sync functions ─────────────────────────────────────────────────────────────

def sync_users(pg_cur, session):
    print("\n  Syncing Users...")
    pg_cur.execute("SELECT user_id, username FROM users")
    rows = [{"user_id": r["user_id"], "username": r["username"]} for r in pg_cur.fetchall()]
    n = run_batch(session, """
        UNWIND $rows AS row
        MERGE (u:User {user_id: row.user_id})
        SET u.username = row.username
    """, rows)
    print(f"    {n} users synced")


def sync_artists(pg_cur, session):
    print("\n  Syncing Artists...")
    pg_cur.execute("SELECT artist_id, name FROM artists")
    rows = [{"artist_id": r["artist_id"], "name": r["name"]} for r in pg_cur.fetchall()]
    n = run_batch(session, """
        UNWIND $rows AS row
        MERGE (a:Artist {artist_id: row.artist_id})
        SET a.name = row.name
    """, rows)
    print(f"    {n} artists synced")


def sync_tracks(pg_cur, session):
    print("\n  Syncing Tracks...")
    pg_cur.execute("""
        SELECT t.track_id, t.title, g.name AS genre
        FROM tracks t
        LEFT JOIN genres g ON g.genre_id = t.genre_id
    """)
    rows = [{"track_id": r["track_id"], "title": r["title"], "genre": r["genre"]} for r in pg_cur.fetchall()]
    n = run_batch(session, """
        UNWIND $rows AS row
        MERGE (t:Track {track_id: row.track_id})
        SET t.title = row.title,
            t.genre = row.genre
    """, rows)
    print(f"    {n} tracks synced")


def sync_performed_by(pg_cur, session):
    print("\n  Syncing PERFORMED_BY relationships...")
    pg_cur.execute("""
        SELECT t.track_id, ar.artist_id
        FROM tracks t
        JOIN albums al ON al.album_id = t.album_id
        JOIN artists ar ON ar.artist_id = al.artist_id
    """)
    rows = [{"track_id": r["track_id"], "artist_id": r["artist_id"]} for r in pg_cur.fetchall()]
    n = run_batch(session, """
        UNWIND $rows AS row
        MATCH (t:Track {track_id: row.track_id})
        MATCH (a:Artist {artist_id: row.artist_id})
        MERGE (t)-[:PERFORMED_BY]->(a)
    """, rows)
    print(f"    {n} PERFORMED_BY edges synced")


def sync_listened_to(pg_cur, session):
    print("\n  Syncing LISTENED_TO relationships...")
    pg_cur.execute("""
        SELECT user_id, track_id,
               COUNT(*)          AS play_count,
               MAX(played_at)    AS last_played
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
        for r in pg_cur.fetchall()
    ]
    n = run_batch(session, """
        UNWIND $rows AS row
        MATCH (u:User {user_id: row.user_id})
        MATCH (t:Track {track_id: row.track_id})
        MERGE (u)-[r:LISTENED_TO]->(t)
        SET r.count       = row.count,
            r.last_played = row.last_played
    """, rows)
    print(f"    {n} LISTENED_TO edges synced")


def sync_follows(pg_cur, session):
    print("\n  Syncing FOLLOWS relationships...")
    pg_cur.execute("""
        SELECT user_id, artist_id, followed_at
        FROM user_follows_artist
    """)
    rows = [
        {
            "user_id":    r["user_id"],
            "artist_id":  r["artist_id"],
            "followed_at": r["followed_at"].isoformat() if r["followed_at"] else None,
        }
        for r in pg_cur.fetchall()
    ]
    n = run_batch(session, """
        UNWIND $rows AS row
        MATCH (u:User {user_id: row.user_id})
        MATCH (a:Artist {artist_id: row.artist_id})
        MERGE (u)-[r:FOLLOWS]->(a)
        SET r.followed_at = row.followed_at
    """, rows)
    print(f"    {n} FOLLOWS edges synced")


def seed_similar_to(session):
    print("\n  Computing SIMILAR_TO relationships (shared genres)...")
    print("    This may take a few minutes on a large graph...")
    session.run("""
        MATCH (a1:Artist)<-[:PERFORMED_BY]-(t1:Track),
              (a2:Artist)<-[:PERFORMED_BY]-(t2:Track)
        WHERE a1 <> a2
          AND t1.genre = t2.genre
          AND t1.genre IS NOT NULL
        WITH a1, a2, count(DISTINCT t1.genre) AS shared_genres
        WHERE shared_genres > 0
        MERGE (a1)-[r:SIMILAR_TO]-(a2)
        SET r.similarity_score = shared_genres
    """)
    print("    SIMILAR_TO relationships computed")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=== Music Streaming — Neo4j Sync ===\n")

    pg_conn = pg_connect()
    pg_cur  = pg_conn.cursor()
    driver  = neo4j_connect()

    try:
        with driver.session() as session:
            sync_users(pg_cur, session)
            sync_artists(pg_cur, session)
            sync_tracks(pg_cur, session)
            sync_performed_by(pg_cur, session)
            sync_listened_to(pg_cur, session)
            sync_follows(pg_cur, session)
            seed_similar_to(session)

        print("\n  Sync complete. Neo4j graph is ready.")

    except Exception as e:
        import traceback
        print(f"\n  [ERR] Sync failed:")
        traceback.print_exc()
        sys.exit(1)

    finally:
        pg_cur.close()
        pg_conn.close()
        driver.close()


if __name__ == "__main__":
    main()
