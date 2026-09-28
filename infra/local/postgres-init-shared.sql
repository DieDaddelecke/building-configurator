-- Gemeinsame lokale Datenbank beider Produkte (PLAN_G2_VOLLSTAENDIGKEIT 3.9): KI-Modell und Referenzlisten.
-- Lokal im Datenbankserver des Hauptstacks; auf Unraid ein eigener Stack (deploy/unraid/compose.shared.yaml).
-- Läuft aus `compose.yaml` (db-init-shared) gegen die schon laufende Datenbank; die Rollen legt
-- `postgres-init.sql` an. Mehrfach ausführbar.
SELECT 'CREATE DATABASE emprise_shared OWNER migrator'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'emprise_shared')
\gexec

\connect emprise_shared

REVOKE ALL ON DATABASE emprise_shared FROM PUBLIC;
GRANT CONNECT ON DATABASE emprise_shared TO app, readonly;
GRANT USAGE ON SCHEMA public TO app, readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public GRANT SELECT ON TABLES TO readonly;
