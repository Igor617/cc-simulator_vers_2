from __future__ import annotations

import os
from flask import Flask, send_from_directory


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=os.path.join(os.path.dirname(__file__), "..", "..", "web"),
        static_url_path="/static",
    )

    # Register API routes
    try:
        from .api import register_routes

        register_routes(app)
    except Exception as exc:  # pragma: no cover
        @app.get("/api/health")
        def api_health():
            return {"status": "degraded", "detail": str(exc)}

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    return app


def main() -> None:
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
