"""Migrationen laufen mit der Rolle `migrator` (EMPRISE_MIGRATION_DATABASE_URL), nie mit `app` (Plan 6.6)."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

import app.analysis.models
import app.catalog.models
import app.configuration.models
import app.envelope.models
import app.inquiry.models
import app.platform.models  # alle Modelle laden, damit Alembic sie vergleicht
import app.rules.models
import app.rules.reference_models
import app.site.models
import app.submission.models  # noqa: F401
from app.config import get_settings
from app.platform.db import Base
from app.platform.shared import SharedBase

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    override = config.attributes.get("database_url")
    if override:
        return str(override)
    settings = get_settings()
    return settings.migration_database_url or settings.database_url


SHARED_TABLES = {*SharedBase.metadata.tables, "alembic_version_shared"}
"""Gemeinsame Tabellen (`migrations_shared`); ohne eigene Verbindung liegen sie in derselben Datenbank."""


def include_object(obj: object, name: str | None, type_: str, reflected: bool, compare_to: object) -> bool:
    # PostGIS legt eigene Tabellen an (spatial_ref_sys); sie gehören nicht zu unseren Migrationen
    ignored = {"spatial_ref_sys", *SHARED_TABLES}
    return not (type_ == "table" and reflected and compare_to is None and name in ignored)


def run_migrations_offline() -> None:
    context.configure(
        url=_url(), target_metadata=target_metadata, literal_binds=True, include_object=include_object
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
