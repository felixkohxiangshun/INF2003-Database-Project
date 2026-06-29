"""Insights Routes — Complex / Nested Query Endpoints

Exposes the advanced SQL queries from sql/queries/nested_queries.sql
as callable API endpoints, demonstrating window functions, relational
division, correlated sub-queries, and CTE patterns.

Endpoints
---------
GET /insights/top-by-genre
    Top 5 most-played tracks per genre this month.
    Uses CTE + ROW_NUMBER() window function (nested_queries.sql #1).

GET /artists/<id>/related
    Artists followed by users who also follow the given artist —
    collaborative filtering seed (nested_queries.sql #3).

GET /playlists/<id>/completionists
    Users who have listened to every track in a playlist —
    relational division via double NOT EXISTS (nested_queries.sql #6).

GET /artists/top-performers
    Artists whose average track play_count beats their genre average —
    nested aggregate with HAVING (nested_queries.sql #7).
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from backend.db import query, query_one
from backend.middleware.auth_required import auth_required

log = logging.getLogger(__name__)
bp  = Blueprint("insights", __name__)


# ---------------------------------------------------------------------------
# GET /insights/top-by-genre
# nested_queries.sql #1 — CTE + ROW_NUMBER() window function
# ---------------------------------------------------------------------------

@bp.route("/insights/top-by-genre", methods=["GET"])
def top_by_genre():
    """Return the top 5 most-played tracks per genre for the current calendar month.
    Uses a CTE and ROW_NUMBER() window function partitioned by genre."""
    rows = query(
        """
        WITH monthly_track_plays AS (
            SELECT
                g.genre_id,
                g.name          AS genre_name,
                t.track_id,
                t.title         AS track_title,
                ar.name         AS artist_name,
                COUNT(ph.history_id) AS plays_this_month
            FROM   play_history ph
            JOIN   tracks  t  ON t.track_id   = ph.track_id
            JOIN   albums  al ON al.album_id  = t.album_id
            JOIN   artists ar ON ar.artist_id = al.artist_id
            LEFT JOIN genres g ON g.genre_id  = t.genre_id
            WHERE  ph.played_at >= date_trunc('month', CURRENT_DATE)
              AND  ph.played_at <  date_trunc('month', CURRENT_DATE) + INTERVAL '1 month'
            GROUP  BY g.genre_id, g.name, t.track_id, t.title, ar.name
        ), ranked AS (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY genre_id
                       ORDER BY plays_this_month DESC, track_title ASC
                   ) AS genre_rank
            FROM   monthly_track_plays
        )
        SELECT genre_name, genre_rank, track_id, track_title,
               artist_name, plays_this_month
        FROM   ranked
        WHERE  genre_rank <= 5
        ORDER  BY genre_name, genre_rank
        """
    )
    # Group rows into { genre_name: [tracks] } for easier frontend consumption
    genres: dict = {}
    for r in rows:
        g = r["genre_name"] or "Unknown"
        genres.setdefault(g, []).append({
            "rank":         r["genre_rank"],
            "track_id":     r["track_id"],
            "title":        r["track_title"],
            "artist":       r["artist_name"],
            "plays":        r["plays_this_month"],
        })
    return jsonify({"genres": genres})


# ---------------------------------------------------------------------------
# GET /artists/<id>/related
# nested_queries.sql #3 — collaborative filtering via shared followers
# ---------------------------------------------------------------------------

@bp.route("/artists/<int:artist_id>/related", methods=["GET"])
def related_artists(artist_id: int):
    """Artists followed by users who also follow the given artist.
    Surfaces artists frequently co-followed with the seed artist, ordered
    by the number of shared followers. Uses a three-way self-join on
    user_follows_artist."""
    if not query_one("SELECT 1 FROM artists WHERE artist_id = %(id)s", {"id": artist_id}):
        return jsonify({"error": "Artist not found"}), 404

    rows = query(
        """
        SELECT
            other_artist.artist_id,
            other_artist.name          AS artist_name,
            COUNT(DISTINCT sf.user_id) AS shared_follower_count
        FROM   user_follows_artist seed_follow
        JOIN   user_follows_artist sf
               ON sf.user_id = seed_follow.user_id
        JOIN   artists other_artist
               ON other_artist.artist_id = sf.artist_id
        WHERE  seed_follow.artist_id = %(artist_id)s
          AND  sf.artist_id <> %(artist_id)s
        GROUP  BY other_artist.artist_id, other_artist.name
        ORDER  BY shared_follower_count DESC, artist_name ASC
        LIMIT  10
        """,
        {"artist_id": artist_id},
    )
    return jsonify({"artist_id": artist_id, "related": rows})


# ---------------------------------------------------------------------------
# GET /playlists/<id>/completionists
# nested_queries.sql #6 — relational division (double NOT EXISTS)
# ---------------------------------------------------------------------------

@bp.route("/playlists/<int:playlist_id>/completionists", methods=["GET"])
def playlist_completionists(playlist_id: int):
    """Return users who have listened to every track in the given playlist.
    Implements relational division via the double NOT EXISTS pattern — the
    SQL equivalent of 'for all x, P(x)' which has no direct operator in SQL."""
    pl = query_one(
        "SELECT playlist_id, name FROM playlists WHERE playlist_id = %(pid)s AND is_public = TRUE",
        {"pid": playlist_id},
    )
    if not pl:
        return jsonify({"error": "Playlist not found or not public"}), 404

    rows = query(
        """
        SELECT u.user_id, u.username
        FROM   users u
        WHERE  NOT EXISTS (
            SELECT 1
            FROM   playlist_tracks pt
            WHERE  pt.playlist_id = %(playlist_id)s
              AND  NOT EXISTS (
                  SELECT 1
                  FROM   play_history ph
                  WHERE  ph.user_id  = u.user_id
                    AND  ph.track_id = pt.track_id
              )
        )
        ORDER  BY u.username ASC
        """,
        {"playlist_id": playlist_id},
    )
    return jsonify({
        "playlist_id":   playlist_id,
        "playlist_name": pl["name"],
        "completionists": rows,
    })


# ---------------------------------------------------------------------------
# GET /artists/top-performers
# nested_queries.sql #7 — nested aggregate with HAVING
# ---------------------------------------------------------------------------

@bp.route("/artists/top-performers", methods=["GET"])
def top_performing_artists():
    """Artists whose average track play_count exceeds the average for their genre.
    Uses a correlated sub-query inside HAVING to compare each artist's average
    against the overall genre average — a nested aggregate pattern."""
    rows = query(
        """
        SELECT
            ar.artist_id,
            ar.name                  AS artist_name,
            g.name                   AS genre_name,
            ROUND(AVG(t.play_count)) AS artist_avg_plays,
            COUNT(t.track_id)        AS track_count
        FROM   artists ar
        JOIN   albums al ON al.artist_id = ar.artist_id
        JOIN   tracks  t ON t.album_id   = al.album_id
        LEFT JOIN genres g ON g.genre_id = t.genre_id
        GROUP  BY ar.artist_id, ar.name, g.genre_id, g.name
        HAVING AVG(t.play_count) > (
            SELECT AVG(t2.play_count)
            FROM   tracks t2
            WHERE  t2.genre_id IS NOT DISTINCT FROM g.genre_id
        )
        ORDER  BY artist_avg_plays DESC
        """
    )
    return jsonify({"artists": rows})
