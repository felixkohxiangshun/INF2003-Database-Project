"""Authentication Gaurd Decorator

- Protect routes that need a logged-in user.
- Check for valid session before allowing access to that route.
- Injects g.user_id so that protected routes never need to read session directly."""

from __future__ import annotations

import functools
from flask import g, jsonify, session


"""Decorator that blocks unauthenticated requests with HTTP 401"""
def auth_required(f):
    
    """Inner Wrapper Function that performs the session check on every request."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get("user_id")
        if user_id is None:
            return jsonify({"error": "Authentication required"}), 401
        g.user_id = user_id
        g.username = session.get("username")
        return f(*args, **kwargs)
    return decorated
