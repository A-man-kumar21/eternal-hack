"""Alembic environment: uses DATABASE_URL from app config."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from alembic import context  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.models import Base  # noqa: E402

config = context.config
target_metadata = Base.metadata


def run_migrations_online() -> None:
    url = get_settings().DATABASE_URL
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
