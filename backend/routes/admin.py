"""Admin CRUD Routes

Provides full Create / Update / Delete access for the catalogue:
  Artists, Albums, Tracks, Genres.

All routes require an authenticated session (@auth_required).
In a production system these would be gated to admin-role users;
for the INF2003 demo any logged-in user can access them.

Endpoints
---------
GET    /admin/genres               list all genres
POST   /admin/genres               create genre
POST   /admin/artists              create artist
PUT    /admin/artists/<id>         update artist name / bio
DELETE /admin/artists/<id>         delete artist (+ Neo4j node)
POST   /admin/albums               create album
PUT    /admin/albums/<id>          update album title / release_date
DELETE /admin/albums/<id>          delete album
POST   /admin/tracks               create track
PUT    /admin/tracks/<id>          update track metadata
DELETE /admin/tracks/<id>          delete track (+ Neo4j node)
GET    /admin/audit-log            recent rows from audit_log
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from backend.db import execute, query, query_one
from backend.middleware.auth_required import auth_required
from backend.utils import serialize

log = logging.getLogger(__name__)
bp  = Blueprint("admin", __name__, url_prefix="/admin")


# ---------------------------------------------------------------------------
# Genres
# ---------------------------------------------------------------------------

@bp.route("/genres", methods=["GET"])
@auth_required
def list_genres():
    rows = query("SELECT genre_id, name FROM genres ORDER BY name ASC")
    return jsonify(rows)


@bp.route("/genres", methods=["POST"])
@auth_required
def create_genre():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    rows = execute(
        """
        INSERT INTO genres (name)
        VALUES (%(name)s)
        ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
        RETURNING genre_id, name
        """,
        {"name": name},
    )
    return jsonify(rows[0]), 201


# ---------------------------------------------------------------------------
# Artists
# ---------------------------------------------------------------------------

@bp.route("/artists", methods=["POST"])
@auth_required
def create_artist():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    bio  = (body.get("bio")  or "").strip() or None

    if not name:
        return jsonify({"error": "name is required"}), 400

    rows = execute(
        """
        INSERT INTO artists (name, bio)
        VALUES (%(name)s, %(bio)s)
        RETURNING artist_id, name, bio
        """,
        {"name": name, "bio": bio},
    )
    artist = rows[0]

    # Mirror into Neo4j
    _neo4j_merge_artist(artist["artist_id"], artist["name"])

    return jsonify(artist), 201


@bp.route("/artists/<int:artist_id>", methods=["PUT"])
@auth_required
def update_artist(artist_id: int):
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip() or None
    bio  = body.get("bio")

    if bio is not None:
        bio = bio.strip() or None

    rows = execute(
        """
        UPDATE artists
        SET name = COALESCE(%(name)s, name),
            bio  = COALESCE(%(bio)s,  bio)
        WHERE artist_id = %(id)s
        RETURNING artist_id, name, bio
        """,
        {"name": name, "bio": bio, "id": artist_id},
    )
    if not rows:
        return jsonify({"error": "Artist not found"}), 404

    # Keep Neo4j name in sync
    _neo4j_merge_artist(rows[0]["artist_id"], rows[0]["name"])
    return jsonify(rows[0])


@bp.route("/artists/<int:artist_id>", methods=["DELETE"])
@auth_required
def delete_artist(artist_id: int):
    if not query_one("SELECT 1 FROM artists WHERE artist_id = %(id)s", {"id": artist_id}):
        return jsonify({"error": "Artist not found"}), 404

    execute("DELETE FROM artists WHERE artist_id = %(id)s", {"id": artist_id})

    # Remove Artist node and all its edges from Neo4j
    try:
        from backend.graph import get_driver
        driver = get_driver()
        if driver:
            with driver.session() as s:
                s.run(
                    "MATCH (a:Artist {artist_id: $id}) DETACH DELETE a",
                    {"id": artist_id},
                )
    except Exception:
        log.warning("Neo4j artist delete failed for artist_id=%s", artist_id)

    return jsonify({"message": "Artist deleted"})


# ---------------------------------------------------------------------------
# Albums
# ---------------------------------------------------------------------------

@bp.route("/albums", methods=["POST"])
@auth_required
def create_album():
    body         = request.get_json(silent=True) or {}
    artist_id    = body.get("artist_id")
    title        = (body.get("title") or "").strip()
    release_date = body.get("release_date") or None

    if not artist_id or not title:
        return jsonify({"error": "artist_id and title are required"}), 400

    if not query_one("SELECT 1 FROM artists WHERE artist_id = %(id)s", {"id": artist_id}):
        return jsonify({"error": "Artist not found"}), 404

    rows = execute(
        """
        INSERT INTO albums (artist_id, title, release_date)
        VALUES (%(artist_id)s, %(title)s, %(release_date)s)
        RETURNING album_id, artist_id, title, release_date
        """,
        {"artist_id": artist_id, "title": title, "release_date": release_date},
    )
    return jsonify(serialize(rows[0])), 201


@bp.route("/albums/<int:album_id>", methods=["PUT"])
@auth_required
def update_album(album_id: int):
    body         = request.get_json(silent=True) or {}
    title        = (body.get("title") or "").strip() or None
    release_date = body.get("release_date")

    rows = execute(
        """
        UPDATE albums
        SET title        = COALESCE(%(title)s, title),
            release_date = COALESCE(%(release_date)s, release_date)
        WHERE album_id = %(id)s
        RETURNING album_id, artist_id, title, release_date
        """,
        {"title": title, "release_date": release_date, "id": album_id},
    )
    if not rows:
        return jsonify({"error": "Album not found"}), 404
    return jsonify(serialize(rows[0]))


@bp.route("/albums/<int:album_id>", methods=["DELETE"])
@auth_required
def delete_album(album_id: int):
    if not query_one("SELECT 1 FROM albums WHERE album_id = %(id)s", {"id": album_id}):
        return jsonify({"error": "Album not found"}), 404

    # Fetch track IDs before cascading delete so we can clean Neo4j
    tracks = query(
        "SELECT track_id FROM tracks WHERE album_id = %(id)s", {"id": album_id}
    )
    execute("DELETE FROM albums WHERE album_id = %(id)s", {"id": album_id})

    for t in tracks:
        _neo4j_delete_track(t["track_id"])

    return jsonify({"message": "Album deleted"})


# ---------------------------------------------------------------------------
# Tracks
# ---------------------------------------------------------------------------

@bp.route("/tracks", methods=["POST"])
@auth_required
def create_track():
    body         = request.get_json(silent=True) or {}
    album_id     = body.get("album_id")
    genre_id     = body.get("genre_id")
    title        = (body.get("title") or "").strip()
    duration_sec = body.get("duration_sec")

    if not album_id or not title or not duration_sec:
        return jsonify({"error": "album_id, title and duration_sec are required"}), 400

    try:
        album_id     = int(album_id)
        duration_sec = int(duration_sec)
        if album_id <= 0 or duration_sec <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "album_id and duration_sec must be positive integers"}), 400

    if genre_id in ("", None):
        genre_id = None
    else:
        try:
            genre_id = int(genre_id)
        except (ValueError, TypeError):
            return jsonify({"error": "genre_id must be an integer"}), 400

    if not query_one("SELECT 1 FROM albums WHERE album_id = %(id)s", {"id": album_id}):
        return jsonify({"error": "Album not found"}), 404
    if genre_id and not query_one("SELECT 1 FROM genres WHERE genre_id = %(id)s", {"id": genre_id}):
        return jsonify({"error": "Genre not found"}), 404

    rows = execute(
        """
        INSERT INTO tracks (album_id, genre_id, title, duration_sec)
        VALUES (%(album_id)s, %(genre_id)s, %(title)s, %(duration_sec)s)
        RETURNING track_id, album_id, genre_id, title, duration_sec, play_count
        """,
        {
            "album_id": album_id, "genre_id": genre_id,
            "title": title, "duration_sec": duration_sec,
        },
    )
    track = rows[0]

    # Sync new track into Neo4j
    _neo4j_sync_track(track["track_id"], track["title"], album_id)

    return jsonify(track), 201


@bp.route("/tracks/<int:track_id>", methods=["PUT"])
@auth_required
def update_track(track_id: int):
    body         = request.get_json(silent=True) or {}
    title        = (body.get("title") or "").strip() or None
    duration_sec = body.get("duration_sec")
    genre_id     = body.get("genre_id")

    if duration_sec is not None:
        try:
            duration_sec = int(duration_sec)
            if duration_sec <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({"error": "duration_sec must be a positive integer"}), 400

    update_genre = "genre_id" in body
    if update_genre:
        if genre_id in ("", None):
            genre_id = None
        else:
            try:
                genre_id = int(genre_id)
            except (ValueError, TypeError):
                return jsonify({"error": "genre_id must be an integer"}), 400
    if genre_id and not query_one("SELECT 1 FROM genres WHERE genre_id = %(id)s", {"id": genre_id}):
        return jsonify({"error": "Genre not found"}), 404

    rows = execute(
        """
        UPDATE tracks
        SET title        = COALESCE(%(title)s,        title),
            duration_sec = COALESCE(%(duration_sec)s, duration_sec),
            genre_id     = CASE
                               WHEN %(update_genre)s THEN %(genre_id)s
                               ELSE genre_id
                           END
        WHERE track_id = %(id)s
        RETURNING track_id, album_id, genre_id, title, duration_sec, play_count
        """,
        {
            "title": title, "duration_sec": duration_sec,
            "genre_id": genre_id, "update_genre": update_genre,
            "id": track_id,
        },
    )
    if not rows:
        return jsonify({"error": "Track not found"}), 404

    track = rows[0]
    graph_row = query_one(
        """
        SELECT t.track_id, t.title, t.play_count, g.name AS genre
        FROM   tracks t
        LEFT JOIN genres g ON g.genre_id = t.genre_id
        WHERE  t.track_id = %(id)s
        """,
        {"id": track_id},
    )

    # Update title, genre, and play_count in Neo4j
    try:
        from backend.graph import get_driver
        driver = get_driver()
        if driver and graph_row:
            with driver.session() as s:
                s.run(
                    """
                    MATCH (t:Track {track_id: $id})
                    SET   t.title = $title,
                          t.genre = $genre,
                          t.play_count = $play_count
                    """,
                    {
                        "id":         track_id,
                        "title":      graph_row["title"],
                        "genre":      graph_row["genre"],
                        "play_count": graph_row["play_count"],
                    },
                )
    except Exception:
        log.warning("Neo4j track update failed for track_id=%s", track_id)

    return jsonify(track)


@bp.route("/tracks/<int:track_id>", methods=["DELETE"])
@auth_required
def delete_track(track_id: int):
    if not query_one("SELECT 1 FROM tracks WHERE track_id = %(id)s", {"id": track_id}):
        return jsonify({"error": "Track not found"}), 404

    execute("DELETE FROM tracks WHERE track_id = %(id)s", {"id": track_id})
    _neo4j_delete_track(track_id)

    return jsonify({"message": "Track deleted"})


# ---------------------------------------------------------------------------
# Audit log viewer
# ---------------------------------------------------------------------------

@bp.route("/audit-log", methods=["GET"])
@auth_required
def audit_log():
    try:
        limit  = min(int(request.args.get("limit",  50)), 200)
        offset = max(int(request.args.get("offset",  0)),   0)
    except (ValueError, TypeError):
        return jsonify({"error": "limit and offset must be integers"}), 400

    rows = query(
        """
        SELECT log_id, table_name, record_id, changed_at,
               changed_by, field_name, old_value, new_value
        FROM   audit_log
        ORDER  BY changed_at DESC
        LIMIT  %(limit)s OFFSET %(offset)s
        """,
        {"limit": limit, "offset": offset},
    )
    return jsonify(serialize(rows))


# ---------------------------------------------------------------------------
# Neo4j helpers
# ---------------------------------------------------------------------------

def _neo4j_merge_artist(artist_id: int, name: str):
    try:
        from backend.graph import get_driver
        driver = get_driver()
        if driver:
            with driver.session() as s:
                s.run(
                    "MERGE (a:Artist {artist_id: $id}) SET a.name = $name",
                    {"id": artist_id, "name": name},
                )
    except Exception:
        log.warning("Neo4j artist merge failed for artist_id=%s", artist_id)


def _neo4j_delete_track(track_id: int):
    try:
        from backend.graph import get_driver
        driver = get_driver()
        if driver:
            with driver.session() as s:
                s.run(
                    "MATCH (t:Track {track_id: $id}) DETACH DELETE t",
                    {"id": track_id},
                )
    except Exception:
        log.warning("Neo4j track delete failed for track_id=%s", track_id)


def _neo4j_sync_track(track_id: int, title: str, album_id: int):
    """Create Track node and PERFORMED_BY edge in Neo4j for a newly inserted track."""
    try:
        from backend.graph import get_driver
        from backend.db import query_one as db_query_one
        driver = get_driver()
        if not driver:
            return

        artist_row = db_query_one(
            """
            SELECT ar.artist_id, ar.name, g.name AS genre
            FROM   albums  al
            JOIN   artists ar ON ar.artist_id = al.artist_id
            LEFT JOIN tracks t  ON t.album_id  = al.album_id AND t.track_id = %(tid)s
            LEFT JOIN genres g  ON g.genre_id  = t.genre_id
            WHERE  al.album_id = %(aid)s
            LIMIT 1
            """,
            {"tid": track_id, "aid": album_id},
        )
        with driver.session() as s:
            s.run(
                """
                MERGE (t:Track {track_id: $track_id})
                SET t.title = $title,
                    t.genre = $genre,
                    t.play_count = 0
                """,
                {"track_id": track_id, "title": title,
                 "genre": artist_row["genre"] if artist_row else None},
            )
            if artist_row:
                s.run(
                    """
                    MERGE (a:Artist {artist_id: $artist_id})
                    SET a.name = $name
                    MERGE (t:Track {track_id: $track_id})
                    MERGE (t)-[:PERFORMED_BY]->(a)
                    """,
                    {
                        "artist_id": artist_row["artist_id"],
                        "name":      artist_row["name"],
                        "track_id":  track_id,
                    },
                )
    except Exception:
        log.warning("Neo4j track sync failed for track_id=%s", track_id)
