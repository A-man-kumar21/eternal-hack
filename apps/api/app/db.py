"""Database engine/session wiring."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        url = get_settings().DATABASE_URL
        connect_args = {}
        if url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        _engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), class_=Session, expire_on_commit=False)
    return _SessionLocal


def reset_engine() -> None:
    """Test/seed helper: drop cached engine so env changes take effect."""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None


def wipe_database(engine) -> None:
    """Dev/reset only: empty every application table, restoring pristine demo state.

    ``documents.current_version_id`` <-> ``document_versions.document_id`` form a
    foreign-key cycle, so a plain ``metadata.drop_all()`` fails on Postgres
    ("cannot drop table ... because other objects depend on it"). Emptying the
    tables instead of dropping them also keeps the schema and the
    ``alembic_version`` row intact, so a later ``alembic upgrade head`` is a
    harmless no-op:

    - Postgres: ``TRUNCATE ... RESTART IDENTITY CASCADE`` (sequences restart at 1).
    - Other DBs (SQLite in tests): plain ``DELETE``s — SQLite does not enforce
      FKs by default, so table order does not matter; ``sqlite_sequence`` is
      cleared too when present.
    """
    from .models import Base  # local import: models imports config, not db

    # Idempotent: recreate any table a previously failed reset may have dropped.
    Base.metadata.create_all(engine, checkfirst=True)

    if engine.dialect.name == "postgresql":
        table_list = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {table_list} RESTART IDENTITY CASCADE"))
    else:
        with engine.begin() as conn:
            for table in Base.metadata.sorted_tables:
                conn.execute(text(f'DELETE FROM "{table.name}"'))
            seq = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'")
            ).first()
            if seq:
                conn.execute(text("DELETE FROM sqlite_sequence"))
