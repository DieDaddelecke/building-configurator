#!/bin/sh
# Wird nur beim ersten Start mit leerem Datenverzeichnis ausgeführt.
# Rollen wie in Betrieb vorgesehen (Plan 6.6): migrator besitzt das Schema, app nur Datenzugriff.
set -eu

psql -v ON_ERROR_STOP=1 --username postgres \
  -v migrator_pw="$MIGRATOR_DB_PASSWORD" -v app_pw="$APP_DB_PASSWORD" -v readonly_pw="$READONLY_DB_PASSWORD" <<'SQL'
CREATE ROLE migrator LOGIN PASSWORD :'migrator_pw';
CREATE ROLE app LOGIN PASSWORD :'app_pw';
CREATE ROLE readonly LOGIN PASSWORD :'readonly_pw';
CREATE DATABASE emprise OWNER migrator;
\connect emprise
CREATE EXTENSION IF NOT EXISTS postgis;
REVOKE ALL ON DATABASE emprise FROM PUBLIC;
GRANT CONNECT ON DATABASE emprise TO app, readonly;
GRANT USAGE ON SCHEMA public TO app, readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public GRANT SELECT ON TABLES TO readonly;
SQL
