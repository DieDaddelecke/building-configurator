# Plan: Regeldienst für die Massenstudie (RD)

> Stand 25.11.2026. Auftrag des Nutzers (Entscheidungskarte im Projekt „Mass study“, 25.11.2026): Die Massenstudie (`DieDaddelecke/mass-study`) spricht Emprise als Dienst über eine API an und übernimmt PLU-Regeln (Abstände, Prospect H/x, Emprise, Höhen, pleine terre) als Vorschläge mit Zitat in ihre Regeleingabe. Dafür hier zwei Teile: **RD1** eine Prompt-Variante „collectif“ für Mehrfamilienhäuser, **RD2** eine Leseroute „Regeln für Gemeinde + Zone“ mit Service-Token. mass-study selbst ändert sich in diesem Schritt nicht.

## 1. Ausgangslage

- G2 liest Zonenkapitel in drei Läufen (Auswertung, Gegenprüfung, Nachsuche), prüft deterministisch und schreibt je Sektor ein Regelwerk (`rule_set` → `rule_set_version` → `rule`). Der Prompt ist auf **ein neues Einfamilienhaus** zugeschnitten (`rules/domain/extraction.py`, `_PLU_INTRO`); die Nachsuche verwirft Stellen zu Wohnanlagen als `out_of_scope: multi_dwelling`. Für eine Massenstudie im Geschosswohnungsbau sind gerade diese Stellen maßgeblich (Abstände zwischen Gebäuden, Prospect, Bandtiefen, Höhen in Geschossen).
- Zugriff gibt es nur über die OIDC-Sitzung des Büros (mit zweitem Faktor) oder das Kunden-Cookie. Die API-Schlüssel der Organisationen wurden mit ADR-07 entfernt.
- Kosten: Jede Änderung an Prompt oder Schema des Hausprompts erzwingt die Neuauswertung aller Kapitel (RW26, README Stolperstellen). Bezahlte Läufe nur mit Freigabe je Lauf.

## 2. Ziel und Abgrenzung

- **RD1:** Ein Kapitel lässt sich zusätzlich im Umfang `collectif` auswerten. Das Ergebnis steht neben dem des Einfamilienhauses, ersetzt es nicht und ist für Kunden, Konfigurator und Analyse unsichtbar. Die Auswertung `house` bleibt bytegleich (gleicher Prompt, gleiche Prüfsumme, keine Neuauswertung).
- **RD2:** `GET /api/v1/service/rules/communes/{insee}` und `GET /api/v1/service/rules/communes/{insee}/zones/{zone}?scope=collectif|house` mit `Authorization: Bearer <Service-Token>`. Die Route liest nur; sie plant nie eine Auswertung ein (keine Kosten über die API).
- Nicht in diesem Schritt: Auswertung auf Anforderung über die API, Anzeige von `collectif` im Büro (`/buero/regeln`), Fallback auf einen älteren Planstand, Ortsabfrage nach Koordinaten, Prospect zur gegenüberliegenden Straßenseite als Parameter (siehe 6).

## 3. Entwurf RD1: Umfang `collectif`

### 3.1 Domäne (`rules/domain`)

- `kinds.py`: `RuleScope = Literal["house", "collectif"]`, `SCOPES`, `MANDATORY_BY_SCOPE`. Pflichtarten `collectif`: `setback_street`, `setback_side`, `setback_rear`, `setback_between_buildings`, `max_footprint_ratio`, `max_height`, `unsealed_min`. Dach und Fassade werden gelesen, sind aber keine Pflicht; der Abstand zwischen Gebäuden auf derselben Parzelle ist es (mehrere Baukörper).
- `extraction.py`:
  - `_COLLECTIF_INTRO` statt `_PLU_INTRO`: neue Wohngebäude mit mehreren Wohnungen (habitat collectif, immeuble, résidence, opération d'ensemble), allgemeiner Fall. Unterscheidet der Text individuel/collectif, gilt der Wert für collectif; Werte nur für Einfamilienhäuser entfallen. Schwellen nach Wohnungszahl oder Fläche (mixité sociale, Stellplätze ab n Wohnungen) bleiben bedingte Regeln (`text_only`). `building_kind main` = das Wohngebäude.
  - `_COLLECTIF_PARAMS`: Zusatz zu `_PARAMS` mit den Lesarten des Geschosswohnungsbaus: Prospect „L ≥ H/2, minimum 4 m“ → `height_factor` 0.5 und `min_m` 4; Abstand zwischen Gebäuden derselben Parzelle → `setback_between_buildings`; „bande de constructibilité principale“ → `setback_street` mit `band building`; Höhe in Geschossen → `storeys`; Prospect zur gegenüberliegenden Straßenseite → `text_only`.
  - Nachsuche: `gap_task(scope)` und `gap_schema(scope)`. Für `collectif` heißt der Grund statt `multi_dwelling` nun `single_house` („betrifft nur Einfamilienhäuser“); die Texte sprechen vom Wohngebäude statt vom Einfamilienhaus.
  - `system_prompt(kind, scope)`, `prompt_fingerprint(kind, scope)`, `prompt_version(scope)` (`g2-prompt-5+collectif`). Für `house` liefern alle Funktionen genau das Bisherige; ein Test hält die Prüfsumme `a7ad548f037be25e` (PLU) und `dc4e752f99503cef` (Zusatzdokument) fest.
  - `ExtractionRequest.scope`; Zusatzdokumente gibt es nur als `house`.
- `assess.py`: `complete`, `coverage` und `find_gaps` (in `extract.py`) nehmen die Pflichtarten als Parameter, Standard wie bisher.
- Schranken (`BOUNDS`) bleiben gleich, damit `ENGINE_VERSION` nicht steigt. Folge: `sdp_m2` über 5 000 m² oder `on_boundary_max_height_m` über 15 m werden `unknown` (`out_of_bounds`), sichtbar statt still.

### 3.2 Speicherung (Migration 0026)

- `rule_set.scope` (`house` Standard, Prüfung auf die zwei Werte); Eindeutigkeit `(land_use_plan_id, zone_code, scope)` statt `(land_use_plan_id, zone_code)`.
- `rule_extraction_run.scope` (`house` Standard): Kosten und Läufe bleiben je Kapitel sichtbar, Wiederverwendung hängt ohnehin am Eingabe-Hash (der für `collectif` den Umfang enthält).
- Neue Tabelle `regulation_chapter_scope` (`chapter_id`, `scope`, `status`, `input_hash`, `engine_version`, `error`, `updated_at`): Stand der Auswertung je Kapitel und zusätzlichem Umfang. Der Stand `house` bleibt in `regulation_chapter`, damit Import, Housekeeping, Fallback und Kundenweg unverändert bleiben.
- Alle bisherigen Lesepfade auf `rule_set` filtern `scope = 'house'`: Kundenweg und Analyse (`service._rules_for_zones`), Abdeckung im Büro (`office.py`), Referenzlisten (`reference.py`, `reference_store.py`).

### 3.3 Ablauf

- `extract_chapter(..., scope="collectif")` nutzt dieselben drei Läufe, dieselben Schranken und dieselbe Kostenbremse (Monatsbudget). Unterschiede: Stand in `regulation_chapter_scope`, kein Folgeauftrag und kein Freigeben des Fallbacks, Zusatzdokumente → `skipped: scope_not_supported`.
- Ausgelöst wird `collectif` **nur von Hand**: `rules-extract --scope collectif (--chapter ID | --commune INSEE --zone CODE)` synchron in der CLI, Ausgabe mit Kosten. Kein Job, kein Housekeeping, keine Auswertung über die API. Damit kostet `collectif` nur, wenn der Nutzer einen Lauf startet.
- Eine Gemeinde der Massenstudie (z. B. Palaiseau 91477) braucht vorher ihren Planstand: `plu-import --commune 91477` (kostenlos). **Achtung:** Der Import plant die Hausauswertung aller Kapitel ein; ohne Schlüssel im Worker enden sie `not_configured` und bleiben kostenlos. Steht später ein Schlüssel in `.env`, nimmt das Housekeeping sie auf (bezahlt). Deshalb den Schlüssel für einen `collectif`-Lauf nur dem CLI-Aufruf mitgeben (`docker compose exec -e EMPRISE_OPENROUTER_API_KEY=… api python -m app.cli rules-extract …`), nicht in `.env` (Betrieb).

## 4. Entwurf RD2: Leseroute mit Service-Token

### 4.1 Service-Token

- Tabelle `service_token` (`name` eindeutig, `token_hash`, `scopes`, `expires_at`, `revoked_at`, `last_used_at`, `created_by`). Token `emps_<32 Byte urlsafe>`, gespeichert nur als SHA-256 (wie Sitzungen). CLI: `service-token-add NAME [--days N]` (zeigt das Token einmal), `service-token-revoke NAME`, `service-token-list`; Anlegen und Widerrufen im Audit.
- Zugriffsregel `require_service_token("rules:read")` in `platform/auth/context.py`: nur der Kopf `Authorization: Bearer emps_…`; ein Cookie ist dafür weder nötig noch wirksam. Fehler `401 service_token_required` / `401 service_token_invalid`, `403 service_token_scope`. Rate-Limit 120 Aufrufe je Minute und Token (`429`).
- Reichweite: nur die zwei Routen unter `/api/v1/service/rules`. Kein Projekt, keine Kundendaten, keine Kosten. Unterschied zu ADR-07: kein Bearer-Zugang zu Projektrouten und keine Organisationen; ein Token handelt nicht als Person.

### 4.2 Format `emprise-rules/1`

Beschrieben für die Gegenseite in [API_REGELDIENST.md](API_REGELDIENST.md). Die Regeln haben dasselbe Modell wie im Konfigurator (`RuleOut`): Art, Baukörper, Status, Grund, Parameter (Meter, Anteile 0–1, Grad), Seite, Zitat, `quote_verified`, Link auf das PDF des GPU mit `#page=`, Sicherheit, Hinweise. Dazu Planstand, Version (simuliert oder vom Büro geprüft, Modell, Prompt), Status der Zone für diesen Umfang (`ok`, `in_progress`, `not_extracted`, `unavailable`), Hinweise (`text_only`) und offene Textstellen.

### 4.3 Lesen

- Gemeinde → `rules_commune` (aktueller Planstand; 404 `commune_unknown`, wenn nie importiert; bei RNU usw. `status` der Gemeinde mit leerer Zonenliste).
- Zone → Zonen des Planstands in dieser Gemeinde (404 `zone_unknown`), Kapitel über `zone.chapter_code`, Regelwerk `(Planstand, Zone, Umfang)`, aktuelle Version. Kein Rückgriff auf ältere Planstände: Ist der aktuelle nicht ausgewertet, heißt es `not_extracted`.

## 5. Messung (RD1)

- Eine Referenzliste kann einen Umfang tragen (`"scope": "collectif"`, sonst `house`); `reference-check` misst dann die Versionen dieses Umfangs.
- **Bezahlter Lauf nur nach Go des Nutzers.** Vorschlag: Palaiseau, Zone der Testparzelle 0H 0518 (27 Bd Thomas Gobert): `plu-import --commune 91477`, Referenzliste aus dem Originaltext (Entwurf durch Claude, Prüfung durch den Nutzer), dann ein Lauf `collectif` für das Kapitel (geschätzt 1,5–3 $ mit Opus 5.5 je nach Länge). Ergebnis in Abschnitt 8.
- Ohne Lauf getestet: Prompt-Aufbau, Schema, Schranken, Speicherung und Route mit aufgezeichneten Antworten (`FakeExtractor`).

## 6. Risiken und Grenzen

| Risiko | Umgang |
|---|---|
| Hausprompt ändert sich unbemerkt → Neuauswertung aller Kapitel | Test auf die Prüfsummen von 25.11.2026; `collectif`-Texte getrennt |
| Prospect zur gegenüberliegenden Straßenseite (H ≤ L) hat keinen Parameter | als `text_only` mit Zitat; Parameter erst mit eigener Entscheidung (ändert das Ausgabeschema und damit den Hausprompt) |
| Schwellen nach Wohnungszahl | bleiben `text_only`; mass-study zeigt sie als Hinweis |
| Housekeeping wertet importierte Gemeinden der Massenstudie aus, sobald `.env` einen Schlüssel hat | Betrieb: Schlüssel nur am CLI-Aufruf; Folgearbeit: Gemeinden ohne Hausauswertung markieren |
| Cloudflare-Bot-Schutz blockt den Server von mass-study | Betrieb: Regel für `/api/v1/service/` prüfen (ADR-11) |
| Token im Klartext beim Gegenüber | mass-study hält ihn im Server (`apps/server`), nie im Browser; Widerruf per CLI |

## 7. Selbstprüfung

| Frage | Antwort |
|---|---|
| Bleibt die Auswertung `house` unverändert? | Ja: Prompt, Schemata und Eingabe-Hash für `house` sind byte- und wertgleich (Test). `ENGINE_VERSION` bleibt. |
| Kann die API Kosten auslösen? | Nein: Die Route liest nur; `collectif` startet nur über die CLI. |
| Sieht ein Kunde `collectif`-Regeln? | Nein: Alle bisherigen Lesepfade filtern `scope = 'house'` (Test). |
| L2/L6/ADR-01 eingehalten? | Ja: dieselben Schranken und Zitatprüfung; `unknown` statt geraten; die Massenstudie übernimmt nur als Vorschlag. |
| L8? | Ja: Nur öffentliche Planunterlagen gehen an das Modell; die Route gibt keine Projekt- oder Kundendaten aus. |
| Widerspricht das ADR-07? | Nein: ADR-07 entfernte Bearer-Zugang zu Projekten für Organisationen; der Service-Token liest nur öffentliche Regeln und ist eine neue Entscheidung (ADR-12). |
| Genau eine Zugriffsregel je Route? | Ja: `require_service_token`; `test_access_policies.py` führt die Service-Routen eigens auf. |
| Datenbank nur über Alembic? | Ja: Migration 0026, abwärtskompatibel (Standard `house`). |

## 8. Ergebnisse

- Umsetzung RD1 und RD2: 25.11.2026, siehe Git-Log und DECISIONS 4.12.
- Messung: offen, wartet auf Go für den bezahlten Lauf (5).
