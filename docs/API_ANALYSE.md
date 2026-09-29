# API von „Emprise Analyse“ mit API-Schlüssel

Anleitung für Büros, die Emprise Analyse aus eigenen Programmen oder einer CAD-Anbindung aufrufen (AN6, [PLAN_AN6_MANDANTEN.md](PLAN_AN6_MANDANTEN.md) 3.6). Die vollständige Beschreibung aller Endpunkte steht im OpenAPI-Dokument unter `/api/v1/openapi.json` (Schema `bearerAuth`).

## Schlüssel und Rechte

- Anlegen auf der Seite **Organisation → API-Schlüssel** (nur Rolle „Verwaltung“). Der Schlüssel `emp_<Präfix>_<Geheimnis>` erscheint **einmal**; gespeichert wird nur eine Prüfsumme. Verloren → widerrufen und neu anlegen.
- Aufruf mit dem Kopf `Authorization: Bearer emp_…`, **ohne Cookies** (sonst `400 api_key_with_cookies`).
- Reichweite: nur `/api/v1/projects…` – Projekte anlegen und auflisten, Parzelle, Reglement, Zonenwahl, Texterkennung, Analyse, Bericht, DXF, GeoJSON. Alles andere antwortet `403 api_key_not_allowed`.
- Rechte: `read` erlaubt GET, `read, write` auch alles andere (`403 api_key_read_only`). Ein Schlüssel handelt wie ein Architekt der Organisation: Er sieht ihre Projekte und nur diese; fremde Projekte antworten `404`.
- Grenzen: 60 Aufrufe je Minute und Schlüssel (`429`), höchstens 10 aktive Schlüssel, Gültigkeit bis 730 Tage. Kosten der Auswertung zählen zum Monatsbudget der Organisation (`409 organisation_budget_exceeded`), erkannte Seiten zum Scan-Kontingent (`409 ocr_quota_exceeded` mit `remaining`, `pages`, `limit`).
- Fehler kommen als Problem nach RFC 9457 mit `code` (`application/problem+json`).

## Ablauf mit curl

```bash
export EMPRISE=https://analyse.example.fr
export KEY=emp_ab12cd34_…
auth=(-H "Authorization: Bearer $KEY")

# 1. Projekt anlegen
PROJECT=$(curl -s "${auth[@]}" -X POST "$EMPRISE/api/v1/projects" | jq -r .id)

# 2. Parzelle als DXF, GeoJSON oder vektorielles PDF hochladen (eine geschlossene Kontur)
curl -s "${auth[@]}" -F file=@parzelle.dxf -F address_label="12 rue des Lilas, Nantes" \
  "$EMPRISE/api/v1/projects/$PROJECT/site/upload" | jq .site.area_m2

# 3. règlement écrit hochladen; gelesen wird im Hintergrund (202)
DOC=$(curl -s "${auth[@]}" -F file=@reglement.pdf -F du_type=PLU \
  "$EMPRISE/api/v1/projects/$PROJECT/regulations" | jq -r .document.id)

# 4. Warten, bis das Dokument gelesen ist (status "active"; "scan" = erst Texterkennung starten)
curl -s "${auth[@]}" "$EMPRISE/api/v1/projects/$PROJECT/regulations" | jq '.[0].document | {status, chapters: [.chapters[].code]}'

# 5. Zone wählen: plant die Auswertung (kostenpflichtig, einmal je Kapitel)
curl -s "${auth[@]}" -X PUT -H "Content-Type: application/json" \
  -d '{"zone_code": "Uh", "chapter_code": "Uh"}' \
  "$EMPRISE/api/v1/projects/$PROJECT/regulations/$DOC/zone"

# 6. Warten, bis das Kapitel ausgewertet ist (status "succeeded"), dann Analyse und Ausgabe
curl -s "${auth[@]}" "$EMPRISE/api/v1/projects/$PROJECT/analysis" | jq .
curl -s "${auth[@]}" -o lageplan.dxf "$EMPRISE/api/v1/projects/$PROJECT/analysis/export/dxf?variant=local"

# 7. Bericht als PDF: anfordern, bis "ready", dann laden
curl -s "${auth[@]}" -X POST -H "Content-Type: application/json" -d '{"locale": "fr"}' \
  "$EMPRISE/api/v1/projects/$PROJECT/analysis/report" | jq .status
curl -s "${auth[@]}" -o rapport.pdf "$EMPRISE/api/v1/projects/$PROJECT/analysis/report?locale=fr"
```

Gescannte Reglements: Steht das Dokument auf `scan` oder nennt es Seiten ohne Text, startet `POST …/regulations/$DOC/ocr` die Texterkennung (zählt zum Kontingent); danach wie ab Schritt 4.

Abfragen in Schritt 4, 6 und 7 höchstens alle paar Sekunden; das Rate-Limit gilt je Schlüssel.
