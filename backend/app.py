"""Flask application factory."""

from __future__ import annotations

import logging
import os
from datetime import timedelta
from dotenv import load_dotenv
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logging.basicConfig(
    level = logging.DEBUG if os.getenv("FLASK_DEBUG", "0") == "1" else logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)

log = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)

    app.config.update(
        SECRET_KEY                 = os.getenv("SECRET_KEY", "dev-secret-change-me"),
        SESSION_COOKIE_HTTPONLY    = True,
        SESSION_COOKIE_SAMESITE    = "Lax",
        PERMANENT_SESSION_LIFETIME = timedelta(days=7),
        DB_HOST     = os.getenv("DB_HOST",     "localhost"),
        DB_PORT     = int(os.getenv("DB_PORT", 5432)),
        DB_NAME     = os.getenv("DB_NAME",     "music_streaming"),
        DB_USER     = os.getenv("DB_USER",     "postgres"),
        DB_PASSWORD = os.getenv("DB_PASSWORD", ""),
        NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687"),
        NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j"),
        NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", ""),
    )

    CORS(app, supports_credentials=True, origins=["http://localhost:8080", "http://127.0.0.1:8080"])

    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")

    @app.route("/")
    def index():
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/<path:filename>")
    def static_files(filename):
        return send_from_directory(frontend_dir, filename)

    from backend.db              import init_db
    from backend.graph           import init_graph
    from backend.startup_sync    import start_background_sync
    init_db(app)
    init_graph(app)
    start_background_sync(app)

    from backend.routes.auth            import bp as auth_bp
    from backend.routes.tracks          import bp as tracks_bp
    from backend.routes.playlist        import bp as playlists_bp
    from backend.routes.history         import bp as history_bp
    from backend.routes.recommendations import bp as recommendations_bp
    from backend.routes.artists         import bp as artists_graph_bp
    from backend.routes.admin           import bp as admin_bp
    from backend.routes.insights        import bp as insights_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(insights_bp)   # must register before tracks_bp so /artists/top-performers matches first
    app.register_blueprint(tracks_bp)
    app.register_blueprint(playlists_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(recommendations_bp)
    app.register_blueprint(artists_graph_bp)
    app.register_blueprint(admin_bp)



    @app.route("/health")
    def health_check():
        from backend.db import query_one
        from backend.graph import get_driver

        pg_ok  = False
        neo_ok = False

        try:
            query_one("SELECT 1")
            pg_ok = True
        except Exception as e:
            log.error("PostgreSQL health check failed: %s", e)

        try:
            driver = get_driver()
            if driver:
                driver.verify_connectivity()
                neo_ok = True
        except Exception as e:
            log.error("Neo4j health check failed: %s", e)

        status = "ok" if (pg_ok and neo_ok) else "degraded"
        code   = 200 if status == "ok" else 207

        return jsonify({
            "status":     status,
            "postgresql": "up" if pg_ok  else "down",
            "neo4j":      "up" if neo_ok else "down",
        }), code
        
        
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad Request", "message": str(e)}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not Found", "message": str(e)}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method Not Allowed", "message": str(e)}), 405

    @app.errorhandler(500)
    def internal_server_error(e):
        log.error("Internal server error: %s", e)
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred."}), 500

    return app


if __name__ == "__main__":
    create_app().run(
        host = "0.0.0.0",
        port=int(os.getenv("FLASK_PORT", 8080)),
        debug = os.getenv("FLASK_DEBUG", "0") == "1",
    )
