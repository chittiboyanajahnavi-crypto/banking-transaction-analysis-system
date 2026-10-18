"""SQLAlchemy engine and schema helpers; importing this module opens no connection."""

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for the application's relational models."""


def make_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Create an engine and enable SQLite foreign keys for local tests."""
    engine = create_engine(database_url, echo=echo, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_schema(engine: Engine) -> None:
    """Create missing tables from the registered model metadata."""
    from . import models  # noqa: F401  Import registers model tables on Base.metadata.

    Base.metadata.create_all(engine)
