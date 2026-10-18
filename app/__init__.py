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
    def overview():
        """Serve the all-time transaction overview."""
        return render_template("overview.html", active_page="overview", include_charts=True), 200

    @app.get("/transactions")
    def transactions_page():
        """Serve the transaction explorer."""
        return render_template("transactions.html", active_page="transactions", include_charts=False), 200

    @app.get("/analysis")
    def analysis_page():
        """Serve the date-filtered analytics workspace."""
        return render_template("analysis.html", active_page="analysis", include_charts=True), 200

    return app
