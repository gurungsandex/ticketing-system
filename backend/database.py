import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Allow overriding the DB location (e.g. tests use a temp file / in-memory).
SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./helpdesk.db")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """Reliability + concurrency hardening for SQLite.

    - WAL lets readers and a writer proceed concurrently instead of blocking
      the whole database, which matters when multiple staff use the dashboard
      while end-user clients submit tickets.
    - busy_timeout makes a connection wait (up to 30s) for a lock instead of
      immediately raising "database is locked".
    - foreign_keys enforces referential integrity.
    """
    # Only apply to SQLite connections (guards against non-SQLite test targets).
    if not hasattr(dbapi_connection, "execute"):
        return
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=30000;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()
    except Exception:
        # Never let pragma tuning prevent a connection from being usable.
        pass


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
