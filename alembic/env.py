"""Alembic environment — uses the app's settings and models."""

from logging.config import fileConfig

from alembic import context

from app.core.config import settings
from app.core.models import Base

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    return settings.database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_url().startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection")
    if connectable is None:
        from app.core.database import engine as connectable  # noqa: N811

    with connectable.connect() as connection:
        if connection.dialect.name == "sqlite":
            # Batch migrations recreate tables (copy + DROP + rename). With FK enforcement
            # on, dropping a parent table would CASCADE-delete child rows. PRAGMA is a
            # no-op inside a transaction, so set it before Alembic begins one.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
            compare_type=True,
        )
        try:
            with context.begin_transaction():
                context.run_migrations()
        finally:
            if connection.dialect.name == "sqlite":
                if connection.in_transaction():
                    connection.commit()
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
