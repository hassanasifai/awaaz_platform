"""Alembic environment for the Awaaz schema.

We expose the synchronous engine here (Alembic's helpers are synchronous);
runtime SQLAlchemy is async via ``awaaz_api.persistence.db``.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Pull DSN from env so we never hardcode credentials.
db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
if not db_url:
    raise RuntimeError(
        "DATABASE_URL_SYNC (preferred) or DATABASE_URL must be set for Alembic"
    )
# Alembic wants the sync driver — convert ``+asyncpg`` if found.
if "+asyncpg" in db_url:
    db_url = db_url.replace("+asyncpg", "+psycopg")
config.set_main_option("sqlalchemy.url", db_url)


# We deliberately do NOT bind a SQLAlchemy MetaData here — every migration is
# explicit raw SQL or ``op.execute(...)``.  This keeps schema authoritative in
# migrations rather than in models, which is what we want for a multi-tenant
# DB whose RLS policies don't map cleanly onto declarative metadata.
target_metadata = None


def run_migrations_offline() -> None:
    """Generate SQL without a DB connection."""

    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Disable RLS for the migration session — DDL must not be filtered.
        connection.execute(__import__("sqlalchemy").text("SET row_security = off"))
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
