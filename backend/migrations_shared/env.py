"""Migrationen der gemeinsamen Datenbank beider Produkte (docs/PLAN_G2_VOLLSTAENDIGKEIT.md 3.9).

Eigene Versionstabelle `alembic_version_shared`: Ohne eigene Verbindung liegen die gemeinsamen Tabellen in
der Datenbank der Instanz neben deren Migrationen. Beide Produkte fahren diese Migrationen in ihrem
Migrate-Job; eine Sperre auf Datenbankebene hält zwei gleichzeitige Läufe auseinander. Nur erweiternde
Migrationen: Ein älteres Image verträgt ein neueres Schema.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool, text

import app.platform.shared
import app.rules.reference_models  # noqa: F401  – alle gemeinsamen Modelle laden
from app.config import get_settings
from app.platform.shared import SharedBase, shared_migration_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SharedBase.metadata
VERSION_TABLE = "alembic_version_shared"
LOCK_KEY = 7_311_2026
"""Beliebige, feste Nummer der Sperre (`pg_advisory_lock`) für diese Migrationen."""


def _url() -> str:
    override = config.attributes.get("database_url")
    return str(override) if override else shared_migration_url(get_settings())


def include_object(obj: object, name: str | None, type_: str, reflected: bool, compare_to: object) -> bool:
    # Liegen die Tabellen in der Datenbank einer Instanz, gehören deren Tabellen nicht hierher
    if type_ == "table":
        return name in target_metadata.tables
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object,
        version_table=VERSION_TABLE,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": LOCK_KEY})
        connection.commit()
        try:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                include_object=include_object,
                version_table=VERSION_TABLE,
                transaction_per_migration=True,
            )
            with context.begin_transaction():
                context.run_migrations()
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
            connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
