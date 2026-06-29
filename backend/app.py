"""Flask Application Factory

- Creates and Configure the Flask App
- Load environmen variables from .env
- Register all route blueprints
- Initialize PostgreSQL and Neo4j database connections on startup
- Provides a /health endpointt to check database connectivity
- Handles the global HTTP errors with JSON responses"""

from __future__ import annotations

import logging
import os
from datetime import timedelta
from dotenv import load_dotenv
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

#Loads .env from Project Root Directory
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logging.basicConfig(
    level = logging.DEBUG if os.getenv("FLASK_DEBUG", "0") == "1" else logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)

log = logging.getLogger(__name__)


"""Create and Returns the Configured Flask App Instance
- Load configuration, initialize DB conenction, and register all blueprints."""
def create_app() -> Flask:
    # Create and Configure the Flask Web Application
    app = Flask(__name__)
    
    # Configuration
    app.config.update(
        SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me"),
        SESSION_COOKIE_HTTPONLY = True,
        SESSION_COOKIE_SAMESITE = "Lax",
        PERMANENT_SESSION_LIFETIME = timedelta(days=7),
    
    
        # PostgreSQL Database Setup
        DB_HOST = os.getenv("DB_HOST", "localhost"),
        DB_PORT = int(os.getenv("DB_PORT", 5432)),
        DB_NAME = os.getenv("DB_NAME", "music_streaming"),
        DB_USER = os.getenv("DB_USER", "postgres"),
        DB_PASSWORD = os.getenv("DB_PASSWORD", ""),
    
    
        # Neo4j (Graph Database) Setup
        NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687"),
        NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j"),
        NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", ""),
    ) 
    
    
    # CORS — only needed if frontend is served from a different origin
    CORS(app, supports_credentials=True, origins=["http://localhost:8080", "http://127.0.0.1:8080"])

    # Serve frontend static files
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")

    @app.route("/")
    def index():
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/<path:filename>")
    def static_files(filename):
        return send_from_directory(frontend_dir, filename)

    # Database Connections
    from backend.db              import init_db
    from backend.graph           import init_graph
    from backend.startup_sync    import start_background_sync
    init_db(app)
    init_graph(app)

    # Seed Neo4j in the background — Flask starts serving immediately,
    # sync finishes in ~10-30 s depending on dataset size.
    start_background_sync(app)

    # Register Blueprints
    from backend.routes.auth            import bp as auth_bp
    from backend.routes.tracks          import bp as tracks_bp
    from backend.routes.playlist        import bp as playlists_bp
    from backend.routes.history         import bp as history_bp
    from backend.routes.recommendations import bp as recommendations_bp
    from backend.routes.artists         import bp as artists_graph_bp
    from backend.routes.admin           import bp as admin_bp
    from backend.routes.insights        import bp as insights_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(insights_bp)   # register before tracks so /artists/top-performers matches first
    app.register_blueprint(tracks_bp)
    app.register_blueprint(playlists_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(recommendations_bp)
    app.register_blueprint(artists_graph_bp)
    app.register_blueprint(admin_bp)



    """Checks if PostgreSQL is reachable.
    - Returns status "ok" (200) if up, else 'degraded' (207) if down."""
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
        
        
    # Global Error Handlers
    """Returns a JSON response for 400 Bad Request Errors."""
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad Request", "message": str(e)}), 400

    """Returns a JSON response for 404 Not Found Errors."""
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not Found", "message": str(e)}), 404

    """Returns a JSON response for 405 Method Not Allowed Errors."""
    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method Not Allowed", "message": str(e)}), 405


    """Returns a JSON response for 500 Internal Server Errors."""
    @app.errorhandler(500)
    def internal_server_error(e):
        log.error(f"Internal Server Error: {e}")
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred."}), 500

    log.info("Flask App Created Successfully. Registered Blueprints: auth, tracks, playlists, history, recommendations")
    return app


"""Runs the Flask Development Server if this script is executed directly."""
if __name__ == "__main__":
    create_app().run(
        host = "0.0.0.0",
        port=int(os.getenv("FLASK_PORT", 8080)),
        debug = os.getenv("FLASK_DEBUG", "0") == "1",
    )
