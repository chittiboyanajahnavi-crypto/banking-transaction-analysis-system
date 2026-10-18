"""Environment-backed settings for the Flask application."""

import os


class Config:
    """Default configuration; debug mode is off unless explicitly enabled."""

    ENVIRONMENT = os.environ.get("APP_ENV", "development")
    DEBUG = os.environ.get("APP_DEBUG", "0").strip().lower() in {"1", "true", "yes"}
    TESTING = False
