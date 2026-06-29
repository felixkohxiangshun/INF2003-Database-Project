"""Recommendations Route

- GET /recommend  — personalised track recommendations for the logged-in user.

Strategy (in order of preference):
  1. Collaborative filtering via Neo4j — tracks played by users with similar taste
  2. Artist similarity via Neo4j       — tracks from artists similar to followed ones
  3. Genre affinity via Neo4j          — tracks from genres the user listens to most
  4. SQL fallback                      — top tracks in genres from user's play history
     (used when Neo4j is unavailable or user has no graph data yet)

Each Neo4j result only returns track_id + metadata scores.
Full track details (title, artist, etc.) are fetched from PostgreSQL.
"""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify

from backend.db import query
from backend.graph import neo4j_query
from backend.middleware.auth_required import auth_required

log = logging.getLogger(__name__)
bp  = Blueprint("recommendations", __name__)


def _enrich_tracks(track_ids: list[int], scores: dict[int, float]) -> list[dict]:
    """Fetch full track details from PostgreSQL for a list of track_ids."""
    if not track_ids:
        return []

    rows = query(
        """
        SELECT t.track_id,
               t.title          AS title,
               ar.name          AS artist,
               al.title         AS album,
               g.name           AS genre,
               t.duration_sec,
               t.play_count
        FROM   tracks  t
        JOIN   albums  al ON al.album_id  = t.album_id
        JOIN   artists ar ON ar.artist_id = al.artist_id
        LEFT JOIN genres g ON g.genre_id  = t.genre_id
        WHERE  t.track_id = ANY(%(ids)s)
        """,
        {"ids": track_ids},
    )

    # Attach score and preserve order
    track_map = {r["track_id"]: r for r in rows}
    result = []
    for tid in track_ids:
        if tid in track_map:
            t = dict(track_map[tid])
            t["score"] = scores.get(tid, 0)
            result.append(t)
    return result


def _sql_fallback(user_id: int, limit: int = 10) -> list[dict]:
    """Genre-based SQL fallback when Neo4j has no data for this user."""
    rows = query(
        """
        WITH user_genre_counts AS (
            SELECT t.genre_id, COUNT(*) AS plays
            FROM   play_history ph
            JOIN   tracks t ON t.track_id = ph.track_id
            WHERE  ph.user_id = %(user_id)s
            GROUP  BY t.genre_id
        )
        SELECT t.track_id,
               t.title          AS title,
               ar.name          AS artist,
               al.title         AS album,
               g.name           AS genre,
               t.duration_sec,
               t.play_count,
               ROUND(ugc.plays * 0.7 + t.play_count * 0.3) AS score
        FROM   tracks t
        JOIN   user_genre_counts ugc ON ugc.genre_id = t.genre_id
        JOIN   albums  al ON al.album_id  = t.album_id
        JOIN   artists ar ON ar.artist_id = al.artist_id
        LEFT JOIN genres g ON g.genre_id  = t.genre_id
        WHERE  NOT EXISTS (
            SELECT 1 FROM play_history ph2
            WHERE  ph2.user_id = %(user_id)s AND ph2.track_id = t.track_id
        )
        ORDER  BY score DESC, t.play_count DESC
        LIMIT  %(limit)s
        """,
        {"user_id": user_id, "limit": limit},
    )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /recommend
# ---------------------------------------------------------------------------
@bp.route("/recommend", methods=["GET"])
@auth_required
def recommend():
    user_id = g.user_id
    recommendations = []

    # ── 1. Genre affinity from own listening history (primary) ────────────
    # Works for any single user — recommends unheard tracks from their
    # most-played genres, ranked by that genre's global popularity.
    genre_recs = neo4j_query(
        """
        MATCH (u:User {user_id: $user_id})-[r:LISTENED_TO]->(t:Track)
        WITH u, t.genre AS genre, sum(r.count) AS genre_plays
        ORDER BY genre_plays DESC LIMIT 3
        MATCH (rec:Track {genre: genre})
        WHERE NOT (u)-[:LISTENED_TO]->(rec)
        WITH rec, genre_plays,
             genre_plays * 10 + toFloat(coalesce(rec.play_count, 0)) / 1000.0 AS score
        RETURN rec.track_id AS track_id, round(score) AS score
        ORDER BY score DESC
        LIMIT 10
        """,
        {"user_id": user_id},
    )
    if genre_recs:
        scores = {r["track_id"]: r["score"] for r in genre_recs}
        recommendations = _enrich_tracks(list(scores.keys()), scores)

    # ── 2. Collaborative filtering (top up if genre affinity < 5) ─────────
    # Finds users with overlapping listening history and surfaces their tracks.
    if len(recommendations) < 5:
        collab = neo4j_query(
            """
            MATCH (u:User {user_id: $user_id})-[:LISTENED_TO]->(t:Track)
                  <-[:LISTENED_TO]-(similar:User)-[:LISTENED_TO]->(rec:Track)
            WHERE NOT (u)-[:LISTENED_TO]->(rec) AND u <> similar
            RETURN rec.track_id AS track_id, count(DISTINCT similar) AS score
            ORDER BY score DESC
            LIMIT 10
            """,
            {"user_id": user_id},
        )
        if collab:
            existing_ids = {r["track_id"] for r in recommendations}
            scores = {r["track_id"]: r["score"] for r in collab if r["track_id"] not in existing_ids}
            recommendations += _enrich_tracks(list(scores.keys()), scores)

    # ── 3. Artist similarity (top up if still < 5) ────────────────────────
    # Uses SIMILAR_TO edges between artists who share genres.
    if len(recommendations) < 5:
        artist_recs = neo4j_query(
            """
            MATCH (u:User {user_id: $user_id})-[:FOLLOWS]->(a:Artist)
                  -[:SIMILAR_TO]-(similar:Artist)<-[:PERFORMED_BY]-(rec:Track)
            WHERE NOT (u)-[:LISTENED_TO]->(rec)
            RETURN rec.track_id AS track_id, count(*) AS score
            ORDER BY score DESC
            LIMIT 10
            """,
            {"user_id": user_id},
        )
        if artist_recs:
            existing_ids = {r["track_id"] for r in recommendations}
            scores = {r["track_id"]: r["score"] for r in artist_recs if r["track_id"] not in existing_ids}
            recommendations += _enrich_tracks(list(scores.keys()), scores)

    # ── 4. SQL fallback ────────────────────────────────────────────────────
    if len(recommendations) < 5:
        existing_ids = {r["track_id"] for r in recommendations}
        fallback = _sql_fallback(user_id, limit=10)
        recommendations += [r for r in fallback if r["track_id"] not in existing_ids]

    return jsonify({"recommendations": recommendations[:10]})
