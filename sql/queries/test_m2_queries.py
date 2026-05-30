"""
test_m2_queries.py
==================
Standalone test script for M2's SQL queries.
Tests all queries in: crud_users.sql, crud_tracks.sql,
                      crud_playlists.sql, nested_queries.sql, analysis.sql

Usage:
    cd INF2003-Database-Project
    source venv/bin/activate
    python3 sql/queries/test_m2_queries.py

Requires a running PostgreSQL instance with schema.sql + triggers.sql applied.
Reads credentials from .env in the project root.
All test data is inserted and cleaned up within a single transaction — your DB
is left unchanged after the script runs.
"""

import os
import sys
import traceback
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# ── Load .env ──────────────────────────────────────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 5432)),
    "dbname":   os.getenv("DB_NAME", "music_streaming"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

# ── Helpers ────────────────────────────────────────────────────────────────────
PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"

results = []

def run(cur, label, sql, params=None):
    """Execute a query and record pass/fail."""
    try:
        cur.execute(sql, params or {})
        rows = cur.fetchall() if cur.description else []
        print(f"  {PASS} {label} — {len(rows)} row(s) returned")
        results.append((label, True, None))
        return rows
    except Exception as e:
        print(f"  {FAIL} {label}")
        print(f"         {e}")
        results.append((label, False, str(e)))
        return []

def run_noreturn(cur, label, sql, params=None):
    """Execute a DML statement that may not return rows."""
    try:
        cur.execute(sql, params or {})
        # Some statements use RETURNING — fetchall is safe either way
        rows = cur.fetchall() if cur.description else []
        print(f"  {PASS} {label}")
        results.append((label, True, None))
        return rows
    except Exception as e:
        print(f"  {FAIL} {label}")
        print(f"         {e}")
        results.append((label, False, str(e)))
        return []

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{INFO} Connecting to PostgreSQL at {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}...")
    try:
        conn = psycopg2.connect(**DB_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)
    except Exception as e:
        print(f"{FAIL} Could not connect: {e}")
        sys.exit(1)

    print(f"{INFO} Connected. Running all M2 query tests inside a ROLLBACK transaction.\n")

    conn.autocommit = False
    cur = conn.cursor()

    try:
        # ── Seed test data ─────────────────────────────────────────────────────
        print("=" * 60)
        print("SEEDING TEST DATA")
        print("=" * 60)

        # Plans (may already exist — upsert by name)
        cur.execute("""
            INSERT INTO plans (name, monthly_price, skip_limit)
            VALUES ('Free', 0.00, 6), ('Premium', 9.99, -1)
            ON CONFLICT (name) DO UPDATE SET monthly_price = EXCLUDED.monthly_price
            RETURNING plan_id, name
        """)
        plans = {r['name']: r['plan_id'] for r in cur.fetchall()}
        free_plan_id    = plans.get('Free')
        premium_plan_id = plans.get('Premium')

        # Genre
        cur.execute("""
            INSERT INTO genres (name) VALUES ('Pop')
            ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
            RETURNING genre_id
        """)
        genre_id = cur.fetchone()['genre_id']

        # Artist
        cur.execute("""
            INSERT INTO artists (name, bio, country)
            VALUES ('Test Artist', 'Test bio', 'SG')
            RETURNING artist_id
        """)
        artist_id = cur.fetchone()['artist_id']

        # Artist 2 (for follow/recommendation tests)
        cur.execute("""
            INSERT INTO artists (name, bio, country)
            VALUES ('Another Artist', 'Another bio', 'US')
            RETURNING artist_id
        """)
        artist_id_2 = cur.fetchone()['artist_id']

        # Album
        cur.execute("""
            INSERT INTO albums (artist_id, title, release_date)
            VALUES (%(artist_id)s, 'Test Album', '2024-01-01')
            RETURNING album_id
        """, {'artist_id': artist_id})
        album_id = cur.fetchone()['album_id']

        # Tracks (3 tracks)
        track_ids = []
        for i in range(3):
            cur.execute("""
                INSERT INTO tracks (album_id, genre_id, title, duration_sec)
                VALUES (%(album_id)s, %(genre_id)s, %(title)s, 180)
                RETURNING track_id
            """, {'album_id': album_id, 'genre_id': genre_id, 'title': f'Test Track {i+1}'})
            track_ids.append(cur.fetchone()['track_id'])

        # Users (2 users)
        cur.execute("""
            INSERT INTO users (email, username, password_hash, country)
            VALUES ('testuser1@test.com', 'testuser1', 'hashedpw1', 'SG')
            RETURNING user_id
        """)
        user_id_1 = cur.fetchone()['user_id']

        cur.execute("""
            INSERT INTO users (email, username, password_hash, country)
            VALUES ('testuser2@test.com', 'testuser2', 'hashedpw2', 'US')
            RETURNING user_id
        """)
        user_id_2 = cur.fetchone()['user_id']

        # Subscription for user 1 (Free)
        cur.execute("""
            INSERT INTO subscriptions (user_id, plan_id, start_date, status)
            VALUES (%(user_id)s, %(plan_id)s, CURRENT_DATE, 'active')
            RETURNING subscription_id
        """, {'user_id': user_id_1, 'plan_id': free_plan_id})
        sub_id = cur.fetchone()['subscription_id']

        # Play history — user 1 plays all 3 tracks multiple times
        for track_id in track_ids:
            for _ in range(8):
                cur.execute("""
                    INSERT INTO play_history (user_id, track_id)
                    VALUES (%(user_id)s, %(track_id)s)
                """, {'user_id': user_id_1, 'track_id': track_id})

        # Playlist
        cur.execute("""
            INSERT INTO playlists (user_id, name, is_public)
            VALUES (%(user_id)s, 'Test Playlist', TRUE)
            RETURNING playlist_id
        """, {'user_id': user_id_1})
        playlist_id = cur.fetchone()['playlist_id']

        # Add track 1 to playlist at position 1
        cur.execute("""
            INSERT INTO playlist_tracks (playlist_id, track_id, position)
            VALUES (%(playlist_id)s, %(track_id)s, 1)
        """, {'playlist_id': playlist_id, 'track_id': track_ids[0]})

        # Follow artist
        cur.execute("""
            INSERT INTO user_follows_artist (user_id, artist_id)
            VALUES (%(user_id)s, %(artist_id)s)
        """, {'user_id': user_id_1, 'artist_id': artist_id})

        print(f"  {INFO} Seed data created (user_id={user_id_1}, artist_id={artist_id}, playlist_id={playlist_id})\n")

        # ── crud_users.sql ─────────────────────────────────────────────────────
        print("=" * 60)
        print("crud_users.sql")
        print("=" * 60)

        run(cur, "1. CREATE USER (RETURNING)",
            """
            INSERT INTO users (email, username, password_hash, country)
            VALUES (%(email)s, %(username)s, %(password_hash)s, %(country)s)
            RETURNING user_id, email, username, country, created_at
            """,
            {'email': 'newuser@test.com', 'username': 'newuser', 'password_hash': 'hash', 'country': 'SG'})

        run(cur, "2. READ USER BY ID WITH ACTIVE PLAN",
            """
            SELECT u.user_id, u.email, u.username, u.country, u.created_at,
                   p.name AS current_plan, p.monthly_price, p.skip_limit,
                   s.subscription_id, s.start_date, s.end_date, s.status
            FROM users u
            LEFT JOIN subscriptions s ON s.user_id = u.user_id AND s.status = 'active'
            LEFT JOIN plans p ON p.plan_id = s.plan_id
            WHERE u.user_id = %(user_id)s
            """,
            {'user_id': user_id_1})

        run(cur, "3. READ USER BY EMAIL",
            "SELECT user_id, email, username, password_hash, country, created_at FROM users WHERE email = %(email)s",
            {'email': 'testuser1@test.com'})

        run(cur, "4. UPDATE USER PROFILE",
            """
            UPDATE users
            SET email    = COALESCE(%(email)s, email),
                username = COALESCE(%(username)s, username),
                country  = COALESCE(%(country)s, country)
            WHERE user_id = %(user_id)s
            RETURNING user_id, email, username, country, created_at
            """,
            {'email': None, 'username': 'updateduser1', 'country': None, 'user_id': user_id_1})

        run(cur, "5. UPDATE PASSWORD HASH",
            "UPDATE users SET password_hash = %(password_hash)s WHERE user_id = %(user_id)s RETURNING user_id, email, username",
            {'password_hash': 'newhash', 'user_id': user_id_1})

        run(cur, "7. CHANGE SUBSCRIPTION PLAN (Premium)",
            """
            INSERT INTO subscriptions (user_id, plan_id, start_date, status)
            SELECT %(user_id)s, p.plan_id, CURRENT_DATE, 'active'
            FROM plans p WHERE p.name = %(plan_name)s
            RETURNING subscription_id, user_id, plan_id, start_date, end_date, status
            """,
            {'user_id': user_id_1, 'plan_name': 'Premium'})

        run(cur, "8. CANCEL ACTIVE SUBSCRIPTION",
            """
            UPDATE subscriptions
            SET status = 'cancelled', end_date = CURRENT_DATE
            WHERE user_id = %(user_id)s AND status = 'active'
            RETURNING subscription_id, user_id, plan_id, start_date, end_date, status
            """,
            {'user_id': user_id_1})

        run(cur, "9. USER LISTENING SUMMARY",
            """
            SELECT u.user_id, u.username,
                   COUNT(ph.history_id) AS total_plays,
                   COUNT(DISTINCT ph.track_id) AS unique_tracks_played,
                   MAX(ph.played_at) AS last_played_at
            FROM users u
            LEFT JOIN play_history ph ON ph.user_id = u.user_id
            WHERE u.user_id = %(user_id)s
            GROUP BY u.user_id, u.username
            """,
            {'user_id': user_id_1})

        run(cur, "6. DELETE USER",
            "DELETE FROM users WHERE user_id = %(user_id)s RETURNING user_id, email, username",
            {'user_id': user_id_2})

        # ── crud_tracks.sql ────────────────────────────────────────────────────
        print()
        print("=" * 60)
        print("crud_tracks.sql")
        print("=" * 60)

        run(cur, "1. SEARCH TRACKS (by title)",
            """
            SELECT t.track_id, t.title AS track_title, t.duration_sec, t.play_count,
                   al.album_id, al.title AS album_title,
                   ar.artist_id, ar.name AS artist_name,
                   g.genre_id, g.name AS genre_name
            FROM tracks t
            JOIN albums al ON al.album_id = t.album_id
            JOIN artists ar ON ar.artist_id = al.artist_id
            LEFT JOIN genres g ON g.genre_id = t.genre_id
            WHERE (%(search)s IS NULL OR (
                    t.title ILIKE '%%' || %(search)s || '%%'
                 OR al.title ILIKE '%%' || %(search)s || '%%'
                 OR ar.name  ILIKE '%%' || %(search)s || '%%'
            ))
              AND (%(genre_name)s IS NULL OR g.name = %(genre_name)s)
            ORDER BY t.play_count DESC, t.title ASC
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            {'search': 'Test', 'genre_name': None, 'limit': 10, 'offset': 0})

        run(cur, "1b. SEARCH TRACKS (no filter / NULL search)",
            """
            SELECT t.track_id, t.title AS track_title, t.duration_sec, t.play_count,
                   al.album_id, al.title AS album_title,
                   ar.artist_id, ar.name AS artist_name,
                   g.genre_id, g.name AS genre_name
            FROM tracks t
            JOIN albums al ON al.album_id = t.album_id
            JOIN artists ar ON ar.artist_id = al.artist_id
            LEFT JOIN genres g ON g.genre_id = t.genre_id
            WHERE (%(search)s IS NULL OR (
                    t.title ILIKE '%%' || %(search)s || '%%'
                 OR al.title ILIKE '%%' || %(search)s || '%%'
                 OR ar.name  ILIKE '%%' || %(search)s || '%%'
            ))
              AND (%(genre_name)s IS NULL OR g.name = %(genre_name)s)
            ORDER BY t.play_count DESC, t.title ASC
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            {'search': None, 'genre_name': None, 'limit': 10, 'offset': 0})

        run(cur, "2. GET TRACK DETAILS BY ID",
            """
            SELECT t.track_id, t.title AS track_title, t.duration_sec, t.play_count,
                   al.album_id, al.title AS album_title, al.release_date,
                   ar.artist_id, ar.name AS artist_name, ar.bio, ar.country AS artist_country,
                   g.genre_id, g.name AS genre_name
            FROM tracks t
            JOIN albums al ON al.album_id = t.album_id
            JOIN artists ar ON ar.artist_id = al.artist_id
            LEFT JOIN genres g ON g.genre_id = t.genre_id
            WHERE t.track_id = %(track_id)s
            """,
            {'track_id': track_ids[0]})

        run(cur, "3. CREATE ARTIST",
            "INSERT INTO artists (name, bio, country) VALUES (%(name)s, %(bio)s, %(country)s) RETURNING artist_id, name, bio, country",
            {'name': 'New Artist', 'bio': 'Some bio', 'country': 'US'})

        run(cur, "4. CREATE ALBUM",
            "INSERT INTO albums (artist_id, title, release_date) VALUES (%(artist_id)s, %(title)s, %(release_date)s) RETURNING album_id, artist_id, title, release_date",
            {'artist_id': artist_id, 'title': 'New Album', 'release_date': '2025-01-01'})

        run(cur, "5. CREATE TRACK",
            "INSERT INTO tracks (album_id, genre_id, title, duration_sec) VALUES (%(album_id)s, %(genre_id)s, %(title)s, %(duration_sec)s) RETURNING track_id, album_id, genre_id, title, duration_sec, play_count",
            {'album_id': album_id, 'genre_id': genre_id, 'title': 'Brand New Track', 'duration_sec': 200})

        run(cur, "6. CREATE GENRE IF MISSING",
            "INSERT INTO genres (name) VALUES (%(name)s) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING genre_id, name",
            {'name': 'Rock'})

        run(cur, "7. UPDATE TRACK METADATA",
            """
            UPDATE tracks
            SET album_id     = COALESCE(%(album_id)s, album_id),
                genre_id     = COALESCE(%(genre_id)s, genre_id),
                title        = COALESCE(%(title)s, title),
                duration_sec = COALESCE(%(duration_sec)s, duration_sec)
            WHERE track_id = %(track_id)s
            RETURNING track_id, album_id, genre_id, title, duration_sec, play_count
            """,
            {'album_id': None, 'genre_id': None, 'title': 'Updated Track Title', 'duration_sec': None, 'track_id': track_ids[2]})

        run(cur, "9. LOG A TRACK PLAY (CTE + trigger)",
            """
            WITH inserted_play AS (
                INSERT INTO play_history (user_id, track_id)
                VALUES (%(user_id)s, %(track_id)s)
                RETURNING history_id, user_id, track_id, played_at
            )
            SELECT ip.history_id, ip.user_id, ip.track_id, ip.played_at, t.play_count
            FROM inserted_play ip
            JOIN tracks t ON t.track_id = ip.track_id
            """,
            {'user_id': user_id_1, 'track_id': track_ids[0]})

        run(cur, "10. FOLLOW ARTIST",
            "INSERT INTO user_follows_artist (user_id, artist_id) VALUES (%(user_id)s, %(artist_id)s) ON CONFLICT (user_id, artist_id) DO NOTHING RETURNING user_id, artist_id, followed_at",
            {'user_id': user_id_1, 'artist_id': artist_id_2})

        run(cur, "11. UNFOLLOW ARTIST",
            "DELETE FROM user_follows_artist WHERE user_id = %(user_id)s AND artist_id = %(artist_id)s RETURNING user_id, artist_id",
            {'user_id': user_id_1, 'artist_id': artist_id_2})

        run(cur, "8. DELETE TRACK",
            "DELETE FROM tracks WHERE track_id = %(track_id)s RETURNING track_id, title",
            {'track_id': track_ids[2]})

        # ── crud_playlists.sql ─────────────────────────────────────────────────
        print()
        print("=" * 60)
        print("crud_playlists.sql")
        print("=" * 60)

        run(cur, "1. CREATE PLAYLIST",
            "INSERT INTO playlists (user_id, name, is_public) VALUES (%(user_id)s, %(name)s, COALESCE(%(is_public)s, TRUE)) RETURNING playlist_id, user_id, name, is_public, created_at",
            {'user_id': user_id_1, 'name': 'My New Playlist', 'is_public': None})

        run(cur, "2. LIST PLAYLISTS OWNED BY USER",
            """
            SELECT p.playlist_id, p.user_id, p.name, p.is_public, p.created_at,
                   COUNT(pt.track_id) AS track_count
            FROM playlists p
            LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.playlist_id
            WHERE p.user_id = %(user_id)s
            GROUP BY p.playlist_id, p.user_id, p.name, p.is_public, p.created_at
            ORDER BY p.created_at DESC
            """,
            {'user_id': user_id_1})

        run(cur, "3. LIST PUBLIC PLAYLISTS",
            """
            SELECT p.playlist_id, p.name, p.created_at,
                   u.user_id AS owner_id, u.username AS owner_username,
                   COUNT(pt.track_id) AS track_count
            FROM playlists p
            JOIN users u ON u.user_id = p.user_id
            LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.playlist_id
            WHERE p.is_public = TRUE
            GROUP BY p.playlist_id, p.name, p.created_at, u.user_id, u.username
            ORDER BY p.created_at DESC
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            {'limit': 10, 'offset': 0})

        run(cur, "4. GET PLAYLIST DETAILS WITH TRACKS",
            """
            SELECT p.playlist_id, p.name AS playlist_name, p.is_public, p.created_at,
                   u.username AS owner_username, pt.position,
                   t.track_id, t.title AS track_title, t.duration_sec, t.play_count,
                   ar.name AS artist_name, al.title AS album_title, g.name AS genre_name
            FROM playlists p
            JOIN users u ON u.user_id = p.user_id
            LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.playlist_id
            LEFT JOIN tracks t ON t.track_id = pt.track_id
            LEFT JOIN albums al ON al.album_id = t.album_id
            LEFT JOIN artists ar ON ar.artist_id = al.artist_id
            LEFT JOIN genres g ON g.genre_id = t.genre_id
            WHERE p.playlist_id = %(playlist_id)s
              AND (p.is_public = TRUE OR p.user_id = %(requesting_user_id)s)
            ORDER BY pt.position ASC NULLS LAST
            """,
            {'playlist_id': playlist_id, 'requesting_user_id': user_id_1})

        run(cur, "5. UPDATE PLAYLIST NAME / VISIBILITY",
            """
            UPDATE playlists
            SET name = COALESCE(%(name)s, name), is_public = COALESCE(%(is_public)s, is_public)
            WHERE playlist_id = %(playlist_id)s AND user_id = %(user_id)s
            RETURNING playlist_id, user_id, name, is_public, created_at
            """,
            {'name': 'Renamed Playlist', 'is_public': None, 'playlist_id': playlist_id, 'user_id': user_id_1})

        run(cur, "7. APPEND TRACK TO END OF PLAYLIST",
            """
            INSERT INTO playlist_tracks (playlist_id, track_id, position)
            SELECT %(playlist_id)s, %(track_id)s, COALESCE(MAX(position), 0) + 1
            FROM playlist_tracks
            WHERE playlist_id = %(playlist_id)s
            ON CONFLICT (playlist_id, track_id) DO NOTHING
            RETURNING playlist_id, track_id, position
            """,
            {'playlist_id': playlist_id, 'track_id': track_ids[1]})

        run(cur, "8a. INSERT TRACK AT POSITION — shift existing up",
            """
            UPDATE playlist_tracks
            SET position = position + 100000
            WHERE playlist_id = %(playlist_id)s AND position >= %(position)s
            """,
            {'playlist_id': playlist_id, 'position': 1})

        run(cur, "8b. INSERT TRACK AT POSITION — insert",
            """
            INSERT INTO playlist_tracks (playlist_id, track_id, position)
            VALUES (%(playlist_id)s, %(track_id)s, %(position)s)
            RETURNING playlist_id, track_id, position
            """,
            {'playlist_id': playlist_id, 'track_id': track_ids[0], 'position': 1})

        run(cur, "8c. INSERT TRACK AT POSITION — normalize positions",
            """
            UPDATE playlist_tracks
            SET position = position - 99999
            WHERE playlist_id = %(playlist_id)s AND position >= 100000
            """,
            {'playlist_id': playlist_id})

        run(cur, "9. REMOVE TRACK AND COMPACT POSITIONS",
            """
            WITH removed AS (
                DELETE FROM playlist_tracks
                WHERE playlist_id = %(playlist_id)s AND track_id = %(track_id)s
                RETURNING playlist_id, position
            ), shifted AS (
                UPDATE playlist_tracks pt
                SET position = pt.position - 1
                FROM removed r
                WHERE pt.playlist_id = r.playlist_id AND pt.position > r.position
                RETURNING pt.playlist_id, pt.track_id, pt.position
            )
            SELECT * FROM removed
            """,
            {'playlist_id': playlist_id, 'track_id': track_ids[1]})

        run(cur, "6. DELETE PLAYLIST",
            "DELETE FROM playlists WHERE playlist_id = %(playlist_id)s AND user_id = %(user_id)s RETURNING playlist_id, name",
            {'playlist_id': playlist_id, 'user_id': user_id_1})

        # ── nested_queries.sql ─────────────────────────────────────────────────
        print()
        print("=" * 60)
        print("nested_queries.sql")
        print("=" * 60)

        run(cur, "1. TOP 5 MOST-PLAYED TRACKS PER GENRE THIS MONTH",
            """
            WITH monthly_track_plays AS (
                SELECT g.genre_id, g.name AS genre_name, t.track_id, t.title AS track_title,
                       ar.name AS artist_name, COUNT(ph.history_id) AS plays_this_month
                FROM play_history ph
                JOIN tracks t ON t.track_id = ph.track_id
                JOIN albums al ON al.album_id = t.album_id
                JOIN artists ar ON ar.artist_id = al.artist_id
                LEFT JOIN genres g ON g.genre_id = t.genre_id
                WHERE ph.played_at >= date_trunc('month', CURRENT_DATE)
                  AND ph.played_at <  date_trunc('month', CURRENT_DATE) + INTERVAL '1 month'
                GROUP BY g.genre_id, g.name, t.track_id, t.title, ar.name
            ), ranked AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY genre_id ORDER BY plays_this_month DESC, track_title ASC) AS genre_rank
                FROM monthly_track_plays
            )
            SELECT genre_name, genre_rank, track_id, track_title, artist_name, plays_this_month
            FROM ranked WHERE genre_rank <= 5
            ORDER BY genre_name, genre_rank
            """)

        run(cur, "2. FREE PLAN USERS WHO PLAYED MORE THAN 20 TRACKS TODAY",
            """
            SELECT u.user_id, u.username, u.email, COUNT(ph.history_id) AS plays_today
            FROM users u
            JOIN play_history ph ON ph.user_id = u.user_id
            WHERE u.user_id IN (
                SELECT s.user_id FROM subscriptions s
                JOIN plans p ON p.plan_id = s.plan_id
                WHERE s.status = 'active' AND p.name = 'Free'
            )
              AND ph.played_at >= CURRENT_DATE
              AND ph.played_at <  CURRENT_DATE + INTERVAL '1 day'
            GROUP BY u.user_id, u.username, u.email
            HAVING COUNT(ph.history_id) > 20
            ORDER BY plays_today DESC
            """)

        run(cur, "3. ARTISTS FOLLOWED BY USERS WHO ALSO FOLLOW A GIVEN ARTIST",
            """
            SELECT other_artist.artist_id, other_artist.name AS recommended_artist,
                   COUNT(DISTINCT similar_user.user_id) AS shared_follower_count
            FROM user_follows_artist seed_follow
            JOIN user_follows_artist similar_user ON similar_user.user_id = seed_follow.user_id
            JOIN artists other_artist ON other_artist.artist_id = similar_user.artist_id
            WHERE seed_follow.artist_id = %(artist_id)s
              AND similar_user.artist_id <> %(artist_id)s
            GROUP BY other_artist.artist_id, other_artist.name
            ORDER BY shared_follower_count DESC, recommended_artist ASC
            LIMIT 10
            """,
            {'artist_id': artist_id})

        run(cur, "4. PLAYLISTS CONTAINING A TRACK, ORDERED BY OWNER POPULARITY",
            """
            WITH owner_popularity AS (
                SELECT u.user_id,
                       COUNT(DISTINCT ufa.artist_id) AS followed_artists,
                       COUNT(DISTINCT ph.history_id) AS total_plays,
                       COUNT(DISTINCT ufa.artist_id) + COUNT(DISTINCT ph.history_id) AS popularity_score
                FROM users u
                LEFT JOIN user_follows_artist ufa ON ufa.user_id = u.user_id
                LEFT JOIN play_history ph ON ph.user_id = u.user_id
                GROUP BY u.user_id
            )
            SELECT p.playlist_id, p.name AS playlist_name, p.is_public,
                   u.user_id AS owner_id, u.username AS owner_username,
                   op.followed_artists, op.total_plays, op.popularity_score
            FROM playlist_tracks pt
            JOIN playlists p ON p.playlist_id = pt.playlist_id
            JOIN users u ON u.user_id = p.user_id
            JOIN owner_popularity op ON op.user_id = u.user_id
            WHERE pt.track_id = %(track_id)s AND p.is_public = TRUE
            ORDER BY op.popularity_score DESC, p.created_at DESC
            """,
            {'track_id': track_ids[0]})

        run(cur, "5. PERSONALIZED RECOMMENDATION (SQL baseline)",
            """
            WITH user_genre_counts AS (
                SELECT t.genre_id, COUNT(*) AS user_genre_plays
                FROM play_history ph
                JOIN tracks t ON t.track_id = ph.track_id
                WHERE ph.user_id = %(user_id)s
                GROUP BY t.genre_id
            ), candidate_tracks AS (
                SELECT t.track_id, t.title AS track_title, ar.name AS artist_name,
                       g.name AS genre_name, t.play_count, ugc.user_genre_plays,
                       (ugc.user_genre_plays * 0.7 + t.play_count * 0.3) AS recommendation_score
                FROM tracks t
                JOIN user_genre_counts ugc ON ugc.genre_id = t.genre_id
                JOIN albums al ON al.album_id = t.album_id
                JOIN artists ar ON ar.artist_id = al.artist_id
                LEFT JOIN genres g ON g.genre_id = t.genre_id
                WHERE NOT EXISTS (
                    SELECT 1 FROM play_history ph2
                    WHERE ph2.user_id = %(user_id)s AND ph2.track_id = t.track_id
                )
            )
            SELECT * FROM candidate_tracks
            ORDER BY recommendation_score DESC, play_count DESC
            LIMIT 10
            """,
            {'user_id': user_id_1})

        run(cur, "6. USERS WHO LISTENED TO ALL TRACKS IN A PLAYLIST (relational division)",
            """
            SELECT u.user_id, u.username
            FROM users u
            WHERE NOT EXISTS (
                SELECT 1 FROM playlist_tracks pt
                WHERE pt.playlist_id = %(playlist_id)s
                  AND NOT EXISTS (
                      SELECT 1 FROM play_history ph
                      WHERE ph.user_id = u.user_id AND ph.track_id = pt.track_id
                  )
            )
            """,
            {'playlist_id': playlist_id})

        run(cur, "7. ARTISTS WITH ABOVE-AVERAGE TRACK POPULARITY IN THEIR GENRE",
            """
            SELECT ar.artist_id, ar.name AS artist_name, g.name AS genre_name,
                   AVG(t.play_count) AS artist_avg_play_count
            FROM artists ar
            JOIN albums al ON al.artist_id = ar.artist_id
            JOIN tracks t ON t.album_id = al.album_id
            LEFT JOIN genres g ON g.genre_id = t.genre_id
            GROUP BY ar.artist_id, ar.name, g.genre_id, g.name
            HAVING AVG(t.play_count) > (
                SELECT AVG(t2.play_count) FROM tracks t2
                WHERE t2.genre_id IS NOT DISTINCT FROM g.genre_id
            )
            ORDER BY artist_avg_play_count DESC
            """)

        # ── analysis.sql ───────────────────────────────────────────────────────
        print()
        print("=" * 60)
        print("analysis.sql")
        print("=" * 60)

        run(cur, "1. EXPLAIN — play_history lookup by user",
            "EXPLAIN SELECT * FROM play_history WHERE user_id = 1 ORDER BY played_at DESC LIMIT 20")

        run(cur, "2. EXPLAIN — play_history lookup by played_at",
            "EXPLAIN SELECT COUNT(*) FROM play_history WHERE played_at >= date_trunc('month', CURRENT_DATE)")

        run(cur, "3. EXPLAIN — track search with joins",
            """
            EXPLAIN
            SELECT t.track_id, t.title, ar.name AS artist_name, g.name AS genre_name
            FROM tracks t
            JOIN albums al ON al.album_id = t.album_id
            JOIN artists ar ON ar.artist_id = al.artist_id
            LEFT JOIN genres g ON g.genre_id = t.genre_id
            WHERE t.title ILIKE '%love%'
            ORDER BY t.play_count DESC
            LIMIT 20
            """)

        run(cur, "5. CONSISTENCY CHECK — play_count vs history count",
            """
            SELECT t.track_id, t.title, t.play_count AS stored_play_count,
                   COUNT(ph.history_id) AS actual_play_count
            FROM tracks t
            LEFT JOIN play_history ph ON ph.track_id = t.track_id
            GROUP BY t.track_id, t.title, t.play_count
            HAVING t.play_count <> COUNT(ph.history_id)
            """)

    except Exception:
        print(f"\n{FAIL} Unexpected error during test run:")
        traceback.print_exc()

    finally:
        # ── Always rollback — DB is left untouched ─────────────────────────────
        conn.rollback()
        cur.close()
        conn.close()
        print(f"\n{INFO} Transaction rolled back — database is unchanged.\n")

    # ── Summary ────────────────────────────────────────────────────────────────
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = [r for r in results if r[1]]
    failed = [r for r in results if not r[1]]
    print(f"  {PASS} {len(passed)} passed")
    if failed:
        print(f"  {FAIL} {len(failed)} failed:")
        for label, _, err in failed:
            print(f"       • {label}: {err}")
    else:
        print(f"\n  All queries passed. M2's files are safe to merge.")
    print()


if __name__ == "__main__":
    main()
