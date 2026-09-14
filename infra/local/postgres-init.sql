-- Lokale Datenbank wie in staging/production: getrennte Rollen (Plan 6.6).
-- Beim verwalteten Anbieter legt der Proof of Concept dieselben Rollen an (infra/README.md).
CREATE ROLE migrator LOGIN PASSWORD 'migrator';
CREATE ROLE app LOGIN PASSWORD 'app';
CREATE ROLE readonly LOGIN PASSWORD 'readonly';

CREATE DATABASE emprise OWNER migrator;
\connect emprise

CREATE EXTENSION IF NOT EXISTS postgis;
REVOKE ALL ON DATABASE emprise FROM PUBLIC;
GRANT CONNECT ON DATABASE emprise TO app, readonly;
GRANT USAGE ON SCHEMA public TO app, readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public GRANT SELECT ON TABLES TO readonly;
