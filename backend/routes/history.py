"""History & Stats Routes

- GET /history          — current user's recent play history
- GET /stats            — top tracks and genres across all users (Charts page)
"""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from backend.db import query, query_one
from backend.middleware.auth_required import auth_required

log = logging.getLogger(__name__)
bp  = Blueprint("history", __name__)


# ---------------------------------------------------------------------------
# GET /history  — current user's recent play history
# ---------------------------------------------------------------------------
@bp.route("/history", methods=["GET"])
@auth_required
def get_history():
    try:
        limit  = min(int(request.args.get("limit",  50)), 200)
        offset = max(int(request.args.get("offset",  0)),   0)
    except (ValueError, TypeError):
        return jsonify({"error": "limit and offset must be integers"}), 400

    rows = query(
        """
        SELECT ph.history_id,
               ph.played_at,
               t.track_id,
               t.title          AS track_title,
               t.duration_sec,
               t.play_count,
               ar.name          AS artist_name,
               al.title         AS album_title,
               g.name           AS genre_name
        FROM   play_history ph
        JOIN   tracks  t  ON t.track_id   = ph.track_id
        JOIN   albums  al ON al.album_id  = t.album_id
        JOIN   artists ar ON ar.artist_id = al.artist_id
        LEFT JOIN genres g ON g.genre_id  = t.genre_id
        WHERE  ph.user_id = %(user_id)s
        ORDER  BY ph.played_at DESC
        LIMIT  %(limit)s OFFSET %(offset)s
        """,
        {"user_id": g.user_id, "limit": limit, "offset": offset},
    )

    # Serialise datetimes
    result = []
    for r in rows:
        r = dict(r)
        r["played_at"] = str(r["played_at"])
        result.append(r)

    return jsonify(result)


# ---------------------------------------------------------------------------
# GET /stats  — Charts page: top tracks + top genres from play_history
# ---------------------------------------------------------------------------
@bp.route("/stats", methods=["GET"])
def get_stats():

    top_tracks = query(
        """
        SELECT t.track_id,
               t.title          AS title,
               ar.name          AS artist,
               t.play_count
        FROM   tracks  t
        JOIN   albums  al ON al.album_id  = t.album_id
        JOIN   artists ar ON ar.artist_id = al.artist_id
        ORDER  BY t.play_count DESC
        LIMIT  8
        """
    )

    top_genres = query(
        """
        SELECT g.name,
               SUM(t.play_count) AS play_count
        FROM   genres  g
        JOIN   tracks  t ON t.genre_id = g.genre_id
        GROUP  BY g.genre_id, g.name
        ORDER  BY play_count DESC
        LIMIT  10
        """
    )

    return jsonify({
        "top_tracks": top_tracks,
        "top_genres": top_genres,
    })
