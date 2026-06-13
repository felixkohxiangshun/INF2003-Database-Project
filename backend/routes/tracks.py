"""Track, Artist and Genre Routes

- Handles searching and browsing tracks, artists, and genres.
- Handles the following and unfollowing of artists.
- All routes are read-only except follow/unfollow which require @auth_required."""
from __future__ import annotations

import logging
from datetime import date

from flask import Blueprint, g, jsonify, request

from backend.db import execute, query, query_one
from backend.middleware.auth_required import auth_required

log = logging.getLogger(__name__)
bp  = Blueprint("tracks", __name__)


# ---------------------------------------------------------------------------
# --------------------------------Helpers------------------------------------
# ---------------------------------------------------------------------------
"""Recursively converts date objects to strings for JSON serialisation."""
def _serialize(obj):
    
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(v) for v in obj]
    if isinstance(obj, date):
        return str(obj)
    return obj


"""Parses and validates limit and offset query parameters.
   Returns (limit, offset) on success, or (None, None) if invalid."""
def _parse_pagination(args) -> tuple[int, int] | tuple[None, None]:
   
    try:
        limit  = min(int(args.get("limit",  20)), 100)
        offset = max(int(args.get("offset",  0)),  0)
        return limit, offset
    except (ValueError, TypeError):
        return None, None


# ---------------------------------------------------------------------------
# ----------------------------------GET /tracks------------------------------
# ---------------------------------------------------------------------------
"""Searches and lists tracks with optional title, artist, album or genre filters."""
@bp.route("/tracks", methods=["GET"])
def list_tracks():
   
    limit, offset = _parse_pagination(request.args)
    if limit is None:
        return jsonify({"error": "limit and offset must be integers"}), 400

    q     = request.args.get("q")     or None
    genre = request.args.get("genre") or None

    rows = query(
        """
        SELECT t.track_id,
               t.title          AS track_title,
               t.duration_sec,
               t.play_count,
               al.album_id,
               al.title         AS album_title,
               ar.artist_id,
               ar.name          AS artist_name,
               g.genre_id,
               g.name           AS genre_name
        FROM   tracks t
        JOIN   albums  al ON al.album_id  = t.album_id
        JOIN   artists ar ON ar.artist_id = al.artist_id
        LEFT JOIN genres g ON g.genre_id  = t.genre_id
        WHERE  (%(search)s IS NULL OR (
                    t.title  ILIKE '%%' || %(search)s || '%%'
                 OR al.title ILIKE '%%' || %(search)s || '%%'
                 OR ar.name  ILIKE '%%' || %(search)s || '%%'
               ))
          AND  (%(genre_name)s IS NULL OR g.name = %(genre_name)s)
        ORDER  BY t.play_count DESC, t.title ASC
        LIMIT  %(limit)s OFFSET %(offset)s
        """,
        {"search": q, "genre_name": genre, "limit": limit, "offset": offset},
    )
    return jsonify(_serialize(rows))


# ---------------------------------------------------------------------------
# ----------------------------------GET /tracks/<id>------------------------------
# ---------------------------------------------------------------------------
"""Returns full details for a single track including album, artist and genre."""
@bp.route("/tracks/<int:track_id>", methods=["GET"])
def get_track(track_id: int):
    
    row = query_one(
        """
        SELECT t.track_id,
               t.title          AS track_title,
               t.duration_sec,
               t.play_count,
               al.album_id,
               al.title         AS album_title,
               al.release_date,
               ar.artist_id,
               ar.name          AS artist_name,
               ar.bio,
               ar.country       AS artist_country,
               g.genre_id,
               g.name           AS genre_name
        FROM   tracks t
        JOIN   albums  al ON al.album_id  = t.album_id
        JOIN   artists ar ON ar.artist_id = al.artist_id
        LEFT JOIN genres g ON g.genre_id  = t.genre_id
        WHERE  t.track_id = %(track_id)s
        """,
        {"track_id": track_id},
    )
    if not row:
        return jsonify({"error": "Track not found"}), 404
    return jsonify(_serialize(row))


# ---------------------------------------------------------------------------
# ----------------------------------GET /artists------------------------------
# ---------------------------------------------------------------------------
"""Lists all artists with optional name search and pagination."""
@bp.route("/artists", methods=["GET"])
def list_artists():

    limit, offset = _parse_pagination(request.args)
    if limit is None:
        return jsonify({"error": "limit and offset must be integers"}), 400

    q = request.args.get("q") or None

    rows = query(
        """
        SELECT ar.artist_id,
               ar.name,
               ar.bio,
               ar.country,
               COUNT(DISTINCT t.track_id) AS track_count
        FROM   artists ar
        LEFT JOIN albums al ON al.artist_id = ar.artist_id
        LEFT JOIN tracks t  ON t.album_id   = al.album_id
        WHERE  (%(q)s IS NULL OR ar.name ILIKE '%%' || %(q)s || '%%')
        GROUP  BY ar.artist_id, ar.name, ar.bio, ar.country
        ORDER  BY track_count DESC, ar.name ASC
        LIMIT  %(limit)s OFFSET %(offset)s
        """,
        {"q": q, "limit": limit, "offset": offset},
    )
    return jsonify(rows)


# ---------------------------------------------------------------------------
# ----------------------------------GET /artists/<id>------------------------------
# ---------------------------------------------------------------------------
"""Returns an artist's profile with all their albums and tracks."""
@bp.route("/artists/<int:artist_id>", methods=["GET"])
def get_artist(artist_id: int):
    """Return an artist with their albums and tracks."""
    artist = query_one(
        "SELECT artist_id, name, bio, country FROM artists WHERE artist_id = %(id)s",
        {"id": artist_id},
    )
    if not artist:
        return jsonify({"error": "Artist not found"}), 404

    albums = query(
        """
        SELECT al.album_id, al.title AS album_title,
               al.release_date,
               COALESCE(json_agg(
                   json_build_object(
                       'track_id',    t.track_id,
                       'title',       t.title,
                       'duration_sec',t.duration_sec,
                       'play_count',  t.play_count
                   ) ORDER BY t.track_id
               ) FILTER (WHERE t.track_id IS NOT NULL), '[]') AS tracks
        FROM  albums al
        LEFT JOIN tracks t ON t.album_id = al.album_id
        WHERE al.artist_id = %(artist_id)s
        GROUP BY al.album_id, al.title, al.release_date
        ORDER BY al.release_date DESC NULLS LAST
        """,
        {"artist_id": artist_id},
    )

    return jsonify(_serialize({**artist, "albums": albums}))


# ---------------------------------------------------------------------------
# --------------------Follow / Unfollow Artist-------------------------------
# ---------------------------------------------------------------------------
"""Returns whether the current user follows the given artist."""
@bp.route("/artists/<int:artist_id>/follow", methods=["GET"])
@auth_required
def follow_status(artist_id: int):

    row = query_one(
        "SELECT 1 FROM user_follows_artist WHERE user_id=%(uid)s AND artist_id=%(aid)s",
        {"uid": g.user_id, "aid": artist_id},
    )
    return jsonify({"following": row is not None})


"""Follows an artist - It is Safe to call multiple times."""
@bp.route("/artists/<int:artist_id>/follow", methods=["POST"])
@auth_required
def follow_artist(artist_id: int):
    """Follow an artist (idempotent)."""
    if not query_one("SELECT 1 FROM artists WHERE artist_id=%(id)s", {"id": artist_id}):
        return jsonify({"error": "Artist not found"}), 404

    rows = execute(
        """
        INSERT INTO user_follows_artist (user_id, artist_id)
        VALUES (%(uid)s, %(aid)s)
        ON CONFLICT (user_id, artist_id) DO NOTHING
        RETURNING user_id, artist_id, followed_at
        """,
        {"uid": g.user_id, "aid": artist_id},
    )

    followed_at = str(rows[0]["followed_at"]) if rows else None
    return jsonify({"following": True, "followed_at": followed_at}), 201


"""Unfollows an artist - It is Safe to call multiple times."""
@bp.route("/artists/<int:artist_id>/follow", methods=["DELETE"])
@auth_required
def unfollow_artist(artist_id: int):
    """Unfollow an artist."""
    execute(
        "DELETE FROM user_follows_artist WHERE user_id=%(uid)s AND artist_id=%(aid)s",
        {"uid": g.user_id, "aid": artist_id},
    )

    return jsonify({"following": False})


# ---------------------------------------------------------------------------
# ----------------------------------GET /genres------------------------------
# ---------------------------------------------------------------------------
"""Returns all genres ordered alphabetically."""
@bp.route("/genres", methods=["GET"])
def list_genres():
    """Return all genre names, ordered alphabetically."""
    rows = query("SELECT genre_id, name FROM genres ORDER BY name ASC")
    return jsonify(rows)