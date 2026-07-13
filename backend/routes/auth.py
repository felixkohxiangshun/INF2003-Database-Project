"""Authentication routes — register, login, logout, profile, password."""

from __future__ import annotations

import logging

import bcrypt
from flask import Blueprint, g, jsonify, request, session

from backend.db import execute, query, query_one
from backend.middleware.auth_required import auth_required

log = logging.getLogger(__name__)
bp  = Blueprint("auth", __name__, url_prefix="/auth")


def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _verify(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _set_session(user: dict) -> None:
    session.clear()
    session["user_id"]  = user["user_id"]
    session["username"] = user["username"]
    session.permanent   = True


@bp.route("/register", methods=["POST"])
def register():
    body     = request.get_json(silent=True) or {}
    email    = (body.get("email")    or "").strip().lower()
    username = (body.get("username") or "").strip()
    password =  body.get("password") or ""

    if not email or not username or not password:
        return jsonify({"error": "email, username and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    if query_one("SELECT user_id FROM users WHERE email = %(email)s", {"email": email}):
        return jsonify({"error": "Email already registered"}), 409
    if query_one("SELECT user_id FROM users WHERE username = %(username)s", {"username": username}):
        return jsonify({"error": "Username already taken"}), 409

    rows = execute(
        """
        INSERT INTO users (email, username, password_hash)
        VALUES (%(email)s, %(username)s, %(password_hash)s)
        RETURNING user_id, email, username, created_at
        """,
        {"email": email, "username": username, "password_hash": _hash(password)},
    )
    user = rows[0]
    _set_session(user)
    log.info("Registered user_id=%d email=%s", user["user_id"], email)

    return jsonify({
        "user_id":  user["user_id"],
        "username": user["username"],
        "email":    user["email"],
    }), 201


@bp.route("/login", methods=["POST"])
def login():
    body     = request.get_json(silent=True) or {}
    email    = (body.get("email")    or "").strip().lower()
    password =  body.get("password") or ""

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    user = query_one(
        "SELECT user_id, email, username, password_hash, created_at "
        "FROM users WHERE email = %(email)s",
        {"email": email},
    )

    if not user or not _verify(password, user["password_hash"]):
        return jsonify({"error": "Invalid email or password"}), 401

    _set_session(user)
    log.info("Login user_id=%d", user["user_id"])

    return jsonify({
        "user_id":  user["user_id"],
        "username": user["username"],
        "email":    user["email"],
    })


@bp.route("/logout", methods=["POST"])
@auth_required
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


@bp.route("/me", methods=["GET"])
@auth_required
def me():
    user = query_one(
        """
        SELECT u.user_id, u.email, u.username, u.created_at
        FROM   users u
        WHERE  u.user_id = %(user_id)s
        """,
        {"user_id": g.user_id},
    )

    if not user:
        return jsonify({"error": "User not found"}), 404

    user = dict(user)
    if user.get("created_at") is not None:
        user["created_at"] = str(user["created_at"])

    return jsonify(user)


@bp.route("/profile", methods=["GET"])
@auth_required
def profile():
    user = query_one(
        "SELECT user_id, email, username, created_at FROM users WHERE user_id = %(id)s",
        {"id": g.user_id},
    )
    if not user:
        return jsonify({"error": "User not found"}), 404

    user = dict(user)
    if user.get("created_at"):
        user["created_at"] = str(user["created_at"])

    stats = query_one(
        """
        SELECT
            (SELECT COUNT(*)             FROM play_history        WHERE user_id = %(id)s) AS total_plays,
            (SELECT COUNT(DISTINCT track_id) FROM play_history   WHERE user_id = %(id)s) AS unique_tracks,
            (SELECT COUNT(*)             FROM user_follows_artist WHERE user_id = %(id)s) AS artists_followed,
            (SELECT COUNT(*)             FROM playlists           WHERE user_id = %(id)s) AS playlist_count
        """,
        {"id": g.user_id},
    )

    top_genre = query_one(
        """
        SELECT g.name
        FROM   play_history ph
        JOIN   tracks t ON t.track_id = ph.track_id
        JOIN   genres g ON g.genre_id = t.genre_id
        WHERE  ph.user_id = %(id)s
        GROUP  BY g.name
        ORDER  BY COUNT(*) DESC
        LIMIT  1
        """,
        {"id": g.user_id},
    )

    return jsonify({
        **user,
        "total_plays":      stats["total_plays"]      if stats else 0,
        "unique_tracks":    stats["unique_tracks"]     if stats else 0,
        "artists_followed": stats["artists_followed"]  if stats else 0,
        "playlist_count":   stats["playlist_count"]    if stats else 0,
        "top_genre":        top_genre["name"]          if top_genre else None,
    })


@bp.route("/me", methods=["PUT"])
@auth_required
def update_profile():
    body     = request.get_json(silent=True) or {}
    username = body.get("username")
    email    = body.get("email")

    if email:
        email = email.strip().lower()
        if query_one(
            "SELECT user_id FROM users WHERE email = %(email)s AND user_id <> %(uid)s",
            {"email": email, "uid": g.user_id},
        ):
            return jsonify({"error": "Email already in use"}), 409

    if username:
        username = username.strip()
        if query_one(
            "SELECT user_id FROM users WHERE username = %(username)s AND user_id <> %(uid)s",
            {"username": username, "uid": g.user_id},
        ):
            return jsonify({"error": "Username already taken"}), 409

    rows = execute(
        """
        UPDATE users
        SET    email    = COALESCE(%(email)s,    email),
               username = COALESCE(%(username)s, username)
        WHERE  user_id  = %(user_id)s
        RETURNING user_id, email, username, created_at
        """,
        {"email": email, "username": username, "user_id": g.user_id},
    )

    if not rows:
        return jsonify({"error": "User not found"}), 404

    updated = rows[0]

    if "user_id" in session and username:
        session["username"] = updated["username"]

    if username:
        try:
            from backend.graph import get_driver
            driver = get_driver()
            if driver:
                with driver.session() as s:
                    s.run(
                        "MERGE (u:User {user_id: $user_id}) SET u.username = $username",
                        {"user_id": g.user_id, "username": updated["username"]},
                    )
        except Exception:
            log.warning("Neo4j user update failed for user_id=%s", g.user_id)

    updated["created_at"] = str(updated["created_at"])
    return jsonify(updated)


@bp.route("/password", methods=["PUT"])
@auth_required
def change_password():
    body             = request.get_json(silent=True) or {}
    current_password = body.get("current_password") or ""
    new_password     = body.get("new_password")     or ""

    if not current_password or not new_password:
        return jsonify({"error": "current_password and new_password are required"}), 400
    if len(new_password) < 6:
        return jsonify({"error": "New password must be at least 6 characters"}), 400

    user = query_one(
        "SELECT password_hash FROM users WHERE user_id = %(user_id)s",
        {"user_id": g.user_id},
    )
    if not user or not _verify(current_password, user["password_hash"]):
        return jsonify({"error": "Current password is incorrect"}), 401

    rows = execute(
        "UPDATE users SET password_hash = %(hash)s WHERE user_id = %(uid)s RETURNING user_id",
        {"hash": _hash(new_password), "uid": g.user_id},
    )

    if not rows:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"message": "Password updated"})
