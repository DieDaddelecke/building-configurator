#!/bin/sh
# Gemeinsame Datenbank beider Produkte (compose.shared.yaml). Wird nur beim ersten Start mit leerem
# Datenverzeichnis ausgeführt. Rollen wie in den Produkten (Plan 6.6), aber eigene Passwörter.
set -eu

psql -v ON_ERROR_STOP=1 --username postgres \
  -v migrator_pw="$MIGRATOR_DB_PASSWORD" -v app_pw="$APP_DB_PASSWORD" -v readonly_pw="$READONLY_DB_PASSWORD" <<'SQL'
CREATE ROLE migrator LOGIN PASSWORD :'migrator_pw';
CREATE ROLE app LOGIN PASSWORD :'app_pw';
CREATE ROLE readonly LOGIN PASSWORD :'readonly_pw';
CREATE DATABASE emprise_shared OWNER migrator;
\connect emprise_shared
REVOKE ALL ON DATABASE emprise_shared FROM PUBLIC;
GRANT CONNECT ON DATABASE emprise_shared TO app, readonly;
GRANT USAGE ON SCHEMA public TO app, readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public GRANT SELECT ON TABLES TO readonly;
SQL
