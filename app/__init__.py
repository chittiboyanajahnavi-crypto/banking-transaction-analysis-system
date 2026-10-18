"""Flask application setup for the Banking Transaction Analysis System."""

from flask import Flask, jsonify

from .config import Config


def create_app(test_config: dict | None = None) -> Flask:
    """Create and configure the application without opening a database connection."""
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    @app.get("/health")
    def health():
        """Report that the Flask process is responding; this does not check MySQL."""
        return jsonify(status="ok"), 200

    return app
