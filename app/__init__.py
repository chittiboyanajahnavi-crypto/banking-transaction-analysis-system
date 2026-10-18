"""Flask application setup for the Banking Transaction Analysis System."""

from flask import Flask, jsonify, render_template

from .api import api
from .config import Config
from .database import make_engine


def create_app(test_config: dict | None = None) -> Flask:
    """Create and configure the application without opening a database connection."""
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    database_url = app.config.get("DATABASE_URL")
    app.extensions["database_engine"] = make_engine(database_url) if database_url else None

    app.register_blueprint(api)

    @app.get("/health")
    def health():
        """Report that the Flask process is responding; this does not check MySQL."""
        return jsonify(status="ok"), 200

    @app.get("/")
    def dashboard():
        """Serve the dashboard shell; data is loaded by its read-only API client."""
        return render_template("dashboard.html"), 200

    return app
