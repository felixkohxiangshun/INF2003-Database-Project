"""Track, Artist and Genre Routes

- Handles searching and browsing tracks, artists, and genres.
- Handles the following and unfollowing of artists.
- All routes are read-only except follow/unfollow which require @auth_required."""
from __future__ import annotations

import logging
from flask import Blueprint, g, jsonify, request

from backend.db import execute, query, query_one
from backend.middleware.auth_required import auth_required
from backend.utils import serialize as _serialize

log = logging.getLogger(__name__)
bp  = Blueprint("tracks", __name__)


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
    
    from flask import session as flask_session
    user_id = flask_session.get("user_id")

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
               g.genre_id,
               g.name           AS genre_name,
               COALESCE(uph.user_plays, 0) AS user_plays
        FROM   tracks t
        JOIN   albums  al ON al.album_id  = t.album_id
        JOIN   artists ar ON ar.artist_id = al.artist_id
        LEFT JOIN genres g ON g.genre_id  = t.genre_id
        LEFT JOIN (
            SELECT track_id, COUNT(*) AS user_plays
            FROM   play_history
            WHERE  user_id = %(user_id)s
            GROUP  BY track_id
        ) uph ON uph.track_id = t.track_id
        WHERE  t.track_id = %(track_id)s
        """,
        {"track_id": track_id, "user_id": user_id},
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
               COUNT(DISTINCT t.track_id) AS track_count
        FROM   artists ar
        LEFT JOIN albums al ON al.artist_id = ar.artist_id
        LEFT JOIN tracks t  ON t.album_id   = al.album_id
        WHERE  (%(q)s IS NULL OR ar.name ILIKE '%%' || %(q)s || '%%')
        GROUP  BY ar.artist_id, ar.name, ar.bio
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
        "SELECT artist_id, name, bio FROM artists WHERE artist_id = %(id)s",
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
    artist = query_one(
        "SELECT artist_id, name FROM artists WHERE artist_id=%(id)s",
        {"id": artist_id},
    )
    if not artist:
        return jsonify({"error": "Artist not found"}), 404
    user = query_one(
        "SELECT username FROM users WHERE user_id = %(id)s",
        {"id": g.user_id},
    )

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
    if followed_at is None:
        existing = query_one(
            """
            SELECT followed_at
            FROM   user_follows_artist
            WHERE  user_id = %(uid)s AND artist_id = %(aid)s
            """,
            {"uid": g.user_id, "aid": artist_id},
        )
        followed_at = str(existing["followed_at"]) if existing else None

    # Real-time Neo4j write
    try:
        from backend.graph import get_driver
        driver = get_driver()
        if driver:
            with driver.session() as s:
                s.run(
                    """
                    MERGE (u:User   {user_id:   $user_id})
                    SET   u.username = $username
                    MERGE (a:Artist {artist_id: $artist_id})
                    SET   a.name = $artist_name
                    MERGE (u)-[r:FOLLOWS]->(a)
                    SET   r.followed_at = $followed_at
                    """,
                    {
                        "user_id":     g.user_id,
                        "username":    user["username"] if user else getattr(g, "username", None),
                        "artist_id":   artist_id,
                        "artist_name": artist["name"],
                        "followed_at": followed_at,
                    },
                )
    except Exception:
        log.warning("Neo4j follow write failed user=%s artist=%s", g.user_id, artist_id)

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

    # Real-time Neo4j write
    try:
        from backend.graph import get_driver
        driver = get_driver()
        if driver:
            with driver.session() as s:
                s.run(
                    """
                    MATCH (u:User   {user_id:   $user_id})-[r:FOLLOWS]->
                          (a:Artist {artist_id: $artist_id})
                    DELETE r
                    """,
                    {"user_id": g.user_id, "artist_id": artist_id},
                )
    except Exception:
        log.warning("Neo4j unfollow write failed user=%s artist=%s", g.user_id, artist_id)

    return jsonify({"following": False})


# ---------------------------------------------------------------------------
# ----------------------------------POST /play-------------------------------
# ---------------------------------------------------------------------------
"""Logs a track play for the current user. Trigger increments tracks.play_count.
   Returns the updated play_count."""
@bp.route("/play", methods=["POST"])
@auth_required
def log_play():
    body     = request.get_json(silent=True) or {}
    track_id = body.get("track_id")

    if not track_id:
        return jsonify({"error": "track_id is required"}), 400
    try:
        track_id = int(track_id)
    except (ValueError, TypeError):
        return jsonify({"error": "track_id must be an integer"}), 400

    track = query_one(
        """
        SELECT t.track_id, t.title, g.name AS genre
        FROM   tracks t
        LEFT JOIN genres g ON g.genre_id = t.genre_id
        WHERE  t.track_id = %(id)s
        """,
        {"id": track_id},
    )
    if not track:
        return jsonify({"error": "Track not found"}), 404

    # Insert play — trigger fires AFTER this, incrementing play_count
    execute(
        "INSERT INTO play_history (user_id, track_id) VALUES (%(user_id)s, %(track_id)s)",
        {"user_id": g.user_id, "track_id": track_id},
    )

    # Read play_count in a separate query — trigger has now fired so count is accurate
    row = query_one(
        """
        SELECT t.play_count,
               t.title,
               g.name AS genre,
               u.username
        FROM   tracks t
        JOIN   users u ON u.user_id = %(user_id)s
        LEFT JOIN genres g ON g.genre_id = t.genre_id
        WHERE  t.track_id = %(track_id)s
        """,
        {"track_id": track_id, "user_id": g.user_id},
    )
    play_count = row["play_count"] if row else None

    # Real-time Neo4j write: keep LISTENED_TO edge in sync without running sync.py
    try:
        from backend.graph import get_driver
        driver = get_driver()
        if driver:
            with driver.session() as s:
                s.run(
                    """
                    MERGE (u:User  {user_id:  $user_id})
                    SET   u.username = $username
                    MERGE (t:Track {track_id: $track_id})
                    SET   t.title = $title,
                          t.genre = $genre,
                          t.play_count = $play_count
                    MERGE (u)-[r:LISTENED_TO]->(t)
                    ON CREATE SET r.count = 1,             r.last_played = datetime()
                    ON MATCH  SET r.count = r.count + 1,  r.last_played = datetime()
                    """,
                    {
                        "user_id":    g.user_id,
                        "username":   row["username"] if row else getattr(g, "username", None),
                        "track_id":   track_id,
                        "title":      row["title"] if row else track["title"],
                        "genre":      row["genre"] if row else track["genre"],
                        "play_count": play_count,
                    },
                )
    except Exception:
        log.warning("Neo4j real-time write failed for user=%s track=%s", g.user_id, track_id)

    return jsonify({"ok": True, "play_count": play_count})


# ---------------------------------------------------------------------------
# ----------------------------------GET /genres------------------------------
# ---------------------------------------------------------------------------
"""Returns all genres ordered alphabetically."""
@bp.route("/genres", methods=["GET"])
def list_genres():
    """Return all genre names, ordered alphabetically."""
    rows = query("SELECT genre_id, name FROM genres ORDER BY name ASC")
    return jsonify(rows)
