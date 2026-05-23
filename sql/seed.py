"""
INF2003 Music Streaming App — Database Seed Script
Author  : M1 (Database Architect)

Loads the Spotify Tracks Dataset from Kaggle into PostgreSQL.

Dataset : https://www.kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset
File    : data/dataset.csv   (~114 k tracks)

Usage:
    python sql/seed.py

Prerequisites:
    pip install psycopg2-binary pandas python-dotenv
    Download dataset.csv and place in data/
"""

import os
import sys
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------------------
# Database connection — reads from .env
# ------------------------------------------------------------------
DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     os.getenv("DB_PORT",     "5432"),
    "dbname":   os.getenv("DB_NAME",     "music_streaming"),
    "user":     os.getenv("DB_USER",     "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "dataset.csv")


def connect():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        print(f"Connected to '{DB_CONFIG['dbname']}' on {DB_CONFIG['host']}")
        return conn
    except psycopg2.OperationalError as e:
        print(f"[ERROR] Could not connect to database:\n{e}")
        sys.exit(1)


def load_csv():
    if not os.path.exists(DATA_PATH):
        print(f"[ERROR] Dataset not found at {DATA_PATH}")
        print("Download from: https://www.kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset")
        sys.exit(1)

    print(f"Loading CSV from {DATA_PATH} …")
    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=["artists", "album_name", "track_name", "track_genre"])
    df = df.drop_duplicates(subset=["track_id"])
    print(f"  {len(df):,} rows after deduplication")
    return df


# ------------------------------------------------------------------
# Seed helpers
# ------------------------------------------------------------------

def seed_plans(cur):
    """Insert the three subscription tiers."""
    plans = [
        ("Free",       0.00,  6),
        ("Premium",    9.90, -1),
        ("Student",    4.90, -1),
    ]
    execute_values(cur,
        "INSERT INTO plans (name, monthly_price, skip_limit) VALUES %s ON CONFLICT (name) DO NOTHING",
        plans
    )
    print("  Plans seeded")


def seed_genres(cur, df):
    """Insert unique genres from the dataset."""
    genres = [(g,) for g in df["track_genre"].dropna().unique()]
    execute_values(cur,
        "INSERT INTO genres (name) VALUES %s ON CONFLICT (name) DO NOTHING",
        genres
    )
    print(f"  {len(genres)} genres seeded")


def seed_artists(cur, df):
    """
    The dataset stores artists as a semicolon-separated string.
    We take the first listed artist per track to keep it simple.
    """
    # Extract first artist from strings like "Artist1;Artist2"
    all_artists = df["artists"].str.split(";").str[0].str.strip().dropna().unique()
    artist_rows = [(a,) for a in all_artists]
    execute_values(cur,
        "INSERT INTO artists (name) VALUES %s ON CONFLICT DO NOTHING",
        artist_rows
    )
    print(f"  {len(artist_rows)} artists seeded")


def seed_albums_and_tracks(cur, df):
    """
    Build albums and tracks in one pass.
    Albums are identified by (artist_name, album_name).
    """
    # Fetch lookup maps from DB
    cur.execute("SELECT name, artist_id FROM artists")
    artist_map = {row[0]: row[1] for row in cur.fetchall()}

    cur.execute("SELECT name, genre_id FROM genres")
    genre_map = {row[0]: row[1] for row in cur.fetchall()}

    # Deduplicate albums
    df["first_artist"] = df["artists"].str.split(";").str[0].str.strip()
    albums_df = df[["first_artist", "album_name"]].drop_duplicates()

    album_rows = []
    for _, row in albums_df.iterrows():
        artist_id = artist_map.get(row["first_artist"])
        if artist_id:
            album_rows.append((artist_id, row["album_name"]))

    execute_values(cur,
        "INSERT INTO albums (artist_id, title) VALUES %s ON CONFLICT DO NOTHING",
        album_rows
    )
    print(f"  {len(album_rows)} albums seeded")

    # Fetch album map: (artist_id, title) -> album_id
    cur.execute("SELECT artist_id, title, album_id FROM albums")
    album_map = {(row[0], row[1]): row[2] for row in cur.fetchall()}

    # Build track rows
    track_rows = []
    for _, row in df.iterrows():
        artist_id = artist_map.get(row["first_artist"])
        album_id  = album_map.get((artist_id, row["album_name"]))
        genre_id  = genre_map.get(row["track_genre"])
        duration  = max(1, int(row.get("duration_ms", 180000) / 1000))

        if album_id:
            track_rows.append((album_id, genre_id, row["track_name"], duration))

    execute_values(cur,
        "INSERT INTO tracks (album_id, genre_id, title, duration_sec) VALUES %s ON CONFLICT DO NOTHING",
        track_rows
    )
    print(f"  {len(track_rows)} tracks seeded")


def seed_demo_users(cur):
    """
    Insert a small set of demo users so M4 can test auth immediately.
    Passwords are bcrypt hashes of 'password123' — replace in production.
    """
    demo_hash = "$2b$12$demohashdemohashdemohasXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
    users = [
        ("alice@example.com",  "alice",   "SG", demo_hash),
        ("bob@example.com",    "bob",     "SG", demo_hash),
        ("carol@example.com",  "carol",   "MY", demo_hash),
    ]
    execute_values(cur,
        "INSERT INTO users (email, username, country, password_hash) VALUES %s ON CONFLICT (email) DO NOTHING",
        users
    )

    # Give each demo user an active Free subscription
    cur.execute("SELECT user_id FROM users WHERE email = ANY(%s)",
                (["alice@example.com", "bob@example.com", "carol@example.com"],))
    user_ids = [row[0] for row in cur.fetchall()]

    cur.execute("SELECT plan_id FROM plans WHERE name = 'Free'")
    free_plan_id = cur.fetchone()[0]

    for uid in user_ids:
        cur.execute("""
            INSERT INTO subscriptions (user_id, plan_id, status)
            VALUES (%s, %s, 'active')
            ON CONFLICT DO NOTHING
        """, (uid, free_plan_id))

    print(f"  {len(users)} demo users seeded (password: password123)")


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    print("=== Music Streaming DB — Seed Script ===\n")

    conn = connect()
    cur  = conn.cursor()

    try:
        df = load_csv()

        print("\nSeeding reference data …")
        seed_plans(cur)
        seed_genres(cur, df)
        seed_artists(cur, df)
        seed_albums_and_tracks(cur, df)
        seed_demo_users(cur)

        conn.commit()
        print("\n✓ Seed complete. Database is ready.")

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Seed failed, transaction rolled back:\n{e}")
        raise

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
