"""Decorator that blocks unauthenticated requests with HTTP 401 and injects g.user_id."""

from __future__ import annotations

import functools
from flask import g, jsonify, session


def auth_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get("user_id")
        if user_id is None:
            return jsonify({"error": "Authentication required"}), 401
        g.user_id = user_id
        return f(*args, **kwargs)
    return decorated