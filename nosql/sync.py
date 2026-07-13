"""
Syncs data from PostgreSQL into Neo4j. Run after sql/seed.py has populated
the relational database.

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
        SELECT t.track_id, t.title, t.play_count, g.name AS genre
        FROM tracks t
        LEFT JOIN genres g ON g.genre_id = t.genre_id
    """)
    rows = [{"track_id": r["track_id"], "title": r["title"], "genre": r["genre"], "play_count": r["play_count"]} for r in pg_cur.fetchall()]
    n = run_batch(session, """
        UNWIND $rows AS row
        MERGE (t:Track {track_id: row.track_id})
        SET t.title      = row.title,
            t.genre      = row.genre,
            t.play_count = row.play_count
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


def ensure_constraints(session):
    """Constraints create backing indexes automatically, so every
    MERGE lookup below is O(log n) instead of a full graph scan."""
    print("\n  Ensuring Neo4j constraints and indexes...")
    stmts = [
        "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE",
        "CREATE CONSTRAINT track_id_unique IF NOT EXISTS FOR (t:Track) REQUIRE t.track_id IS UNIQUE",
        "CREATE CONSTRAINT artist_id_unique IF NOT EXISTS FOR (a:Artist) REQUIRE a.artist_id IS UNIQUE",
        "CREATE INDEX track_genre_index IF NOT EXISTS FOR (t:Track) ON (t.genre)",
    ]
    for s in stmts:
        session.run(s)
    print("    Constraints and indexes ready")


def seed_similar_to(session):
    """Build SIMILAR_TO edges between artists who share genres.

    Grouping by genre first and pairing only within each group avoids
    the O(tracks^2) cartesian join of matching all track pairs and
    filtering by genre afterward.
    """
    print("\n  Computing SIMILAR_TO relationships (shared genres)...")
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
    print("    SIMILAR_TO relationships computed")


def main():
    print("=== Music Streaming — Neo4j Sync ===\n")

    pg_conn = pg_connect()
    pg_cur  = pg_conn.cursor()
    driver  = neo4j_connect()

    try:
        with driver.session() as session:
            ensure_constraints(session)
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
