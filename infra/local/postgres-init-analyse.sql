-- Zweite lokale Datenbank für das Produkt „Emprise Analyse“ (AN0, E-A4: eigene Datenbank je Produkt).
-- Läuft nicht beim Anlegen des Servers, sondern aus `compose.analyse.yaml` gegen die schon laufende
-- Datenbank des Hauptstacks; die Rollen legt `postgres-init.sql` an. Mehrfach ausführbar.
SELECT 'CREATE DATABASE emprise_analyse OWNER migrator'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'emprise_analyse')
\gexec

\connect emprise_analyse

CREATE EXTENSION IF NOT EXISTS postgis;
REVOKE ALL ON DATABASE emprise_analyse FROM PUBLIC;
GRANT CONNECT ON DATABASE emprise_analyse TO app, readonly;
GRANT USAGE ON SCHEMA public TO app, readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public GRANT SELECT ON TABLES TO readonly;
