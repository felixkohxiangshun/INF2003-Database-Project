"""Authentication Routes

- Handles user registration, login, logout, and profile management.
- All routes are prefixed with /auth
- Protected routes require a valid session via @auth_required middleware
- Passwords are hashed using bcrypt before storing in the database
- Sessions are managed using Flask's built-in session cookie.
"""

from __future__ import annotations

import logging

import bcrypt
from flask import Blueprint, g, jsonify, request, session

from backend.db import execute, query_one
from backend.middleware.auth_required import auth_required

log = logging.getLogger(__name__)
bp  = Blueprint("auth", __name__, url_prefix="/auth")


"""--------------------------Helper Functions---------------------"""


"""Hashes a plain text password using bcrypt"""
def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


"""Verifies a plain text password against a bcrypt hash"""
def _verify(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


"""Store user_id and username into the Flask Session and Keeps It Permanent"""
def _set_session(user: dict) -> None:
    session.clear()
    session["user_id"]  = user["user_id"]
    session["username"] = user["username"]
    session.permanent   = True


# ---------------------------------------------------------------------------
# -----------------------------POST /auth/register---------------------------
# ---------------------------------------------------------------------------
"""Register a new user account, and auto-assign the Free Plan,
   starts a session."""
@bp.route("/register", methods=["POST"])
def register():
    
    body     = request.get_json(silent=True) or {}
    email    = (body.get("email")    or "").strip().lower()
    username = (body.get("username") or "").strip()
    password =  body.get("password") or ""
    country  = (body.get("country")  or "").strip().upper() or None

    # Basic Validation
    if not email or not username or not password:
        return jsonify({"error": "email, username and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if country and len(country) != 2:
        return jsonify({"error": "country must be a 2-letter ISO code"}), 400

    # Duplicate Check
    if query_one("SELECT user_id FROM users WHERE email = %(email)s", {"email": email}):
        return jsonify({"error": "Email already registered"}), 409
    if query_one("SELECT user_id FROM users WHERE username = %(username)s", {"username": username}):
        return jsonify({"error": "Username already taken"}), 409

    # Insert User
    rows = execute(
        """
        INSERT INTO users (email, username, password_hash, country)
        VALUES (%(email)s, %(username)s, %(password_hash)s, %(country)s)
        RETURNING user_id, email, username, country, created_at
        """,
        {
            "email":         email,
            "username":      username,
            "password_hash": _hash(password),
            "country":       country,
        },
    )
    user = rows[0]

    # Auto-Assign Free plan
    execute(
        """
        INSERT INTO subscriptions (user_id, plan_id, start_date, status)
        SELECT %(user_id)s, plan_id, CURRENT_DATE, 'active'
        FROM   plans
        WHERE  name = 'Free'
        """,
        {"user_id": user["user_id"]},
    )

    _set_session(user)
    log.info("Registered user_id=%d email=%s", user["user_id"], email)

    return jsonify({
        "user_id":  user["user_id"],
        "username": user["username"],
        "email":    user["email"],
    }), 201


# ---------------------------------------------------------------------------
# -----------------------------POST /auth/login---------------------------
# ---------------------------------------------------------------------------
""""Authenticates a user by email and password and starts a session."""
@bp.route("/login", methods=["POST"])
def login():

    body     = request.get_json(silent=True) or {}
    email    = (body.get("email")    or "").strip().lower()
    password =  body.get("password") or ""

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    user = query_one(
        "SELECT user_id, email, username, password_hash, country, created_at "
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


# ---------------------------------------------------------------------------
# -----------------------------POST /auth/logout---------------------------
# ---------------------------------------------------------------------------
"""Clears the current session, and logs the user out."""
@bp.route("/logout", methods=["POST"])
@auth_required
def logout():
  
    session.clear()
    return jsonify({"message": "Logged out"})


# ---------------------------------------------------------------------------
# -----------------------------GET /auth/me-------------------------------
# ---------------------------------------------------------------------------
"""Return the current user's profile including active plan details."""
@bp.route("/me", methods=["GET"])
@auth_required
def me():

    user = query_one(
        """
        SELECT u.user_id, u.email, u.username, u.country, u.created_at,
               p.name          AS current_plan,
               p.monthly_price,
               p.skip_limit,
               s.subscription_id,
               s.start_date,
               s.end_date,
               s.status        AS subscription_status
        FROM   users u
        LEFT JOIN subscriptions s ON s.user_id = u.user_id AND s.status = 'active'
        LEFT JOIN plans p         ON p.plan_id  = s.plan_id
        WHERE  u.user_id = %(user_id)s
        """,
        {"user_id": g.user_id},
    )

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Converts the datetime/date objects to ISO strings for JSON Serialisation
    user = dict(user)
    for key in ("created_at", "start_date", "end_date"):
        if user.get(key) is not None:
            user[key] = str(user[key])

    return jsonify(user)


# ---------------------------------------------------------------------------
# -----------------------PUT /auth/me  — update profile----------------------
# ---------------------------------------------------------------------------
"""Updates the current user's username, email, or country."""
@bp.route("/me", methods=["PUT"])
@auth_required
def update_profile():

    body     = request.get_json(silent=True) or {}
    username = body.get("username")
    email    = body.get("email")
    country  = body.get("country")

    if email:
        email = email.strip().lower()
        dup = query_one(
            "SELECT user_id FROM users WHERE email = %(email)s AND user_id <> %(uid)s",
            {"email": email, "uid": g.user_id},
        )
        if dup:
            return jsonify({"error": "Email already in use"}), 409

    if username:
        username = username.strip()
        dup = query_one(
            "SELECT user_id FROM users WHERE username = %(username)s AND user_id <> %(uid)s",
            {"username": username, "uid": g.user_id},
        )
        if dup:
            return jsonify({"error": "Username already taken"}), 409

    rows = execute(
        """
        UPDATE users
        SET    email    = COALESCE(%(email)s,    email),
               username = COALESCE(%(username)s, username),
               country  = COALESCE(%(country)s,  country)
        WHERE  user_id  = %(user_id)s
        RETURNING user_id, email, username, country, created_at
        """,
        {
            "email":    email,
            "username": username,
            "country":  country,
            "user_id":  g.user_id,
        },
    )

    if not rows:
        return jsonify({"error": "User not found"}), 404

    updated = rows[0]

    
    if "user_id" in session and username:
        session["username"] = updated["username"]

    updated["created_at"] = str(updated["created_at"])
    return jsonify(updated)


# ---------------------------------------------------------------------------
# ----------------------------PUT /auth/password-----------------------------
# ---------------------------------------------------------------------------
"""Changes the current user's password after verifying the current one."""
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