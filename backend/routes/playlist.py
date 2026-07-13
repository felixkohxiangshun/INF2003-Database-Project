"""Playlist routes — CRUD for playlists and their tracks."""

from __future__ import annotations

import logging
from flask import Blueprint, g, jsonify, request
import psycopg2.errors

from backend.db import execute, get_conn, query, query_one
from backend.middleware.auth_required import auth_required
from backend.utils import serialize as _serialize

log = logging.getLogger(__name__)
bp  = Blueprint("playlists", __name__)


def _owned_or_404(playlist_id: int, user_id: int):
    return query_one(
        "SELECT playlist_id, user_id, name, is_public FROM playlists "
        "WHERE playlist_id = %(pid)s AND user_id = %(uid)s",
        {"pid": playlist_id, "uid": user_id},
    )


def session_user_id() -> int:
    from flask import session as flask_session
    return flask_session.get("user_id", -1)


@bp.route("/playlists", methods=["GET"])
def list_public_playlists():
    try:
        limit  = min(int(request.args.get("limit",  20)), 100)
        offset = max(int(request.args.get("offset",  0)),  0)
    except (ValueError, TypeError):
        return jsonify({"error": "limit and offset must be integers"}), 400

    rows = query(
        """
        SELECT   p.playlist_id,
                 p.name,
                 p.created_at,
                 u.user_id          AS owner_id,
                 u.username         AS owner_username,
                 COUNT(pt.track_id) AS track_count
        FROM     playlists p
        JOIN     users u  ON u.user_id   = p.user_id
        LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.playlist_id
        WHERE    p.is_public = TRUE
        GROUP BY p.playlist_id, p.name, p.created_at, u.user_id, u.username
        ORDER BY p.created_at DESC
        LIMIT    %(limit)s OFFSET %(offset)s
        """,
        {"limit": limit, "offset": offset},
    )
    return jsonify(_serialize(rows))


@bp.route("/playlists/mine", methods=["GET"])
@auth_required
def my_playlists():
    rows = query(
        """
        SELECT   p.playlist_id,
                 p.user_id,
                 p.name,
                 p.is_public,
                 p.created_at,
                 COUNT(pt.track_id) AS track_count
        FROM     playlists p
        LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.playlist_id
        WHERE    p.user_id = %(uid)s
        GROUP BY p.playlist_id, p.user_id, p.name, p.is_public, p.created_at
        ORDER BY p.created_at DESC
        """,
        {"uid": g.user_id},
    )
    return jsonify(_serialize(rows))


@bp.route("/playlists", methods=["POST"])
@auth_required
def create_playlist():
    body      = request.get_json(silent=True) or {}
    name      = (body.get("name") or "").strip()
    is_public = body.get("is_public")

    if not name:
        return jsonify({"error": "name is required"}), 400

    rows = execute(
        """
        INSERT INTO playlists (user_id, name, is_public)
        VALUES (%(uid)s, %(name)s, COALESCE(%(is_public)s, TRUE))
        RETURNING playlist_id, user_id, name, is_public, created_at
        """,
        {"uid": g.user_id, "name": name, "is_public": is_public},
    )
    return jsonify(_serialize(rows[0])), 201


@bp.route("/playlists/<int:playlist_id>", methods=["GET"])
def get_playlist(playlist_id: int):
    requesting_user = session_user_id()

    rows = query(
        """
        SELECT p.playlist_id,
               p.name             AS playlist_name,
               p.is_public,
               p.created_at,
               u.username         AS owner_username,
               u.user_id          AS owner_id,
               pt.position,
               t.track_id,
               t.title            AS track_title,
               t.duration_sec,
               t.play_count,
               ar.name            AS artist_name,
               al.title           AS album_title,
               g.name             AS genre_name
        FROM   playlists p
        JOIN   users u    ON u.user_id    = p.user_id
        LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.playlist_id
        LEFT JOIN tracks t  ON t.track_id  = pt.track_id
        LEFT JOIN albums al ON al.album_id = t.album_id
        LEFT JOIN artists ar ON ar.artist_id = al.artist_id
        LEFT JOIN genres  g  ON g.genre_id  = t.genre_id
        WHERE  p.playlist_id = %(pid)s
          AND  (p.is_public = TRUE OR p.user_id = %(uid)s)
        ORDER BY pt.position ASC NULLS LAST
        """,
        {"pid": playlist_id, "uid": requesting_user},
    )

    if not rows:
        return jsonify({"error": "Playlist not found or access denied"}), 404

    first = rows[0]
    playlist_meta = {
        "playlist_id":    first["playlist_id"],
        "playlist_name":  first["playlist_name"],
        "is_public":      first["is_public"],
        "created_at":     str(first["created_at"]),
        "owner_id":       first["owner_id"],
        "owner_username": first["owner_username"],
    }
    tracks = [
        {
            "position":     r["position"],
            "track_id":     r["track_id"],
            "track_title":  r["track_title"],
            "duration_sec": r["duration_sec"],
            "play_count":   r["play_count"],
            "artist_name":  r["artist_name"],
            "album_title":  r["album_title"],
            "genre_name":   r["genre_name"],
        }
        for r in rows if r["track_id"] is not None
    ]
    return jsonify({**playlist_meta, "tracks": tracks})


@bp.route("/playlists/<int:playlist_id>", methods=["PUT"])
@auth_required
def update_playlist(playlist_id: int):
    if not _owned_or_404(playlist_id, g.user_id):
        return jsonify({"error": "Playlist not found or not yours"}), 404

    body      = request.get_json(silent=True) or {}
    name      = body.get("name")
    is_public = body.get("is_public")

    if name is not None:
        name = name.strip()
        if not name:
            return jsonify({"error": "name cannot be empty"}), 400

    rows = execute(
        """
        UPDATE playlists
        SET    name      = COALESCE(%(name)s, name),
               is_public = COALESCE(%(is_public)s, is_public)
        WHERE  playlist_id = %(pid)s AND user_id = %(uid)s
        RETURNING playlist_id, user_id, name, is_public, created_at
        """,
        {"name": name, "is_public": is_public, "pid": playlist_id, "uid": g.user_id},
    )
    return jsonify(_serialize(rows[0]))


@bp.route("/playlists/<int:playlist_id>", methods=["DELETE"])
@auth_required
def delete_playlist(playlist_id: int):
    if not _owned_or_404(playlist_id, g.user_id):
        return jsonify({"error": "Playlist not found or not yours"}), 404

    execute(
        "DELETE FROM playlists WHERE playlist_id=%(pid)s AND user_id=%(uid)s",
        {"pid": playlist_id, "uid": g.user_id},
    )
    return jsonify({"message": "Playlist deleted"})


@bp.route("/playlists/<int:playlist_id>/tracks", methods=["POST"])
@auth_required
def add_track(playlist_id: int):
    if not _owned_or_404(playlist_id, g.user_id):
        return jsonify({"error": "Playlist not found or not yours"}), 404

    body     = request.get_json(silent=True) or {}
    track_id = body.get("track_id")
    position = body.get("position")

    if not track_id:
        return jsonify({"error": "track_id is required"}), 400
    try:
        track_id = int(track_id)
    except (ValueError, TypeError):
        return jsonify({"error": "track_id must be an integer"}), 400

    if position is not None:
        try:
            position = int(position)
            if position < 1:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({"error": "position must be a positive integer"}), 400

    if not query_one("SELECT 1 FROM tracks WHERE track_id=%(id)s", {"id": track_id}):
        return jsonify({"error": "Track not found"}), 404

    if query_one(
        "SELECT 1 FROM playlist_tracks WHERE playlist_id=%(pid)s AND track_id=%(tid)s",
        {"pid": playlist_id, "tid": track_id},
    ):
        return jsonify({"error": "Track already in playlist"}), 409

    try:
        if position is None:
            rows = execute(
                """
                INSERT INTO playlist_tracks (playlist_id, track_id, position)
                SELECT %(pid)s, %(tid)s, COALESCE(MAX(position), 0) + 1
                FROM   playlist_tracks
                WHERE  playlist_id = %(pid)s
                RETURNING playlist_id, track_id, position
                """,
                {"pid": playlist_id, "tid": track_id},
            )
        else:
            execute(
                """
                UPDATE playlist_tracks
                SET    position = position + 1
                WHERE  playlist_id = %(pid)s AND position >= %(pos)s
                """,
                {"pid": playlist_id, "pos": position},
            )
            rows = execute(
                """
                INSERT INTO playlist_tracks (playlist_id, track_id, position)
                VALUES (%(pid)s, %(tid)s, %(pos)s)
                RETURNING playlist_id, track_id, position
                """,
                {"pid": playlist_id, "tid": track_id, "pos": position},
            )
    except psycopg2.errors.RaiseException:
        return jsonify({"error": "Track already in playlist"}), 409

    return jsonify(rows[0]), 201


# Two-phase ROW_NUMBER() reorder in one transaction; the +100000 offset avoids
# unique constraint collisions during the intermediate update.
@bp.route("/playlists/<int:playlist_id>/tracks/<int:track_id>/position", methods=["PUT"])
@auth_required
def move_track(playlist_id: int, track_id: int):
    if not _owned_or_404(playlist_id, g.user_id):
        return jsonify({"error": "Playlist not found or not yours"}), 404

    body = request.get_json(silent=True) or {}
    new_position = body.get("position")
    if new_position is None:
        return jsonify({"error": "position is required"}), 400
    try:
        new_position = int(new_position)
        if new_position < 1:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "position must be a positive integer"}), 400

    if not query_one(
        "SELECT 1 FROM playlist_tracks WHERE playlist_id=%(pid)s AND track_id=%(tid)s",
        {"pid": playlist_id, "tid": track_id},
    ):
        return jsonify({"error": "Track not in playlist"}), 404

    params = {"playlist_id": playlist_id, "track_id": track_id, "new_position": new_position}
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH current_rows AS (
                SELECT playlist_id, track_id, position
                FROM   playlist_tracks
                WHERE  playlist_id = %(playlist_id)s
            ), target AS (
                SELECT track_id, position AS old_position
                FROM   current_rows
                WHERE  track_id = %(track_id)s
            ), reordered AS (
                SELECT cr.track_id,
                       ROW_NUMBER() OVER (
                           ORDER BY
                               CASE
                                   WHEN cr.track_id = %(track_id)s
                                       THEN %(new_position)s
                                   WHEN cr.position >= %(new_position)s
                                    AND cr.position <  (SELECT old_position FROM target)
                                       THEN cr.position + 1
                                   WHEN cr.position <= %(new_position)s
                                    AND cr.position >  (SELECT old_position FROM target)
                                       THEN cr.position - 1
                                   ELSE cr.position
                               END,
                               cr.position
                       ) AS new_pos
                FROM current_rows cr
            )
            UPDATE playlist_tracks pt
            SET    position = r.new_pos + 100000
            FROM   reordered r
            WHERE  pt.playlist_id = %(playlist_id)s
              AND  pt.track_id    = r.track_id
            """,
            params,
        )
        cur.execute(
            """
            UPDATE playlist_tracks
            SET    position = position - 100000
            WHERE  playlist_id = %(playlist_id)s
              AND  position > 100000
            RETURNING playlist_id, track_id, position
            """,
            params,
        )
        rows = [dict(r) for r in (cur.fetchall() or [])]
    conn.commit()

    return jsonify({"tracks": sorted(rows, key=lambda r: r["position"])})


@bp.route("/playlists/<int:playlist_id>/tracks/<int:track_id>", methods=["DELETE"])
@auth_required
def remove_track(playlist_id: int, track_id: int):
    if not _owned_or_404(playlist_id, g.user_id):
        return jsonify({"error": "Playlist not found or not yours"}), 404

    rows = execute(
        """
        WITH removed AS (
            DELETE FROM playlist_tracks
            WHERE  playlist_id = %(pid)s AND track_id = %(tid)s
            RETURNING playlist_id, position
        ), shifted AS (
            UPDATE playlist_tracks pt
            SET    position = pt.position - 1
            FROM   removed r
            WHERE  pt.playlist_id = r.playlist_id AND pt.position > r.position
            RETURNING pt.playlist_id
        )
        SELECT * FROM removed
        """,
        {"pid": playlist_id, "tid": track_id},
    )

    if not rows:
        return jsonify({"error": "Track not in playlist"}), 404

    return jsonify({"message": "Track removed"})
