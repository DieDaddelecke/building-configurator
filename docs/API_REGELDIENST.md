# Regeldienst: PLU-Regeln für andere Dienste

Anleitung für Dienste, die die Regeln von Emprise lesen, zuerst die Massenstudie (`DieDaddelecke/mass-study`). Entwurf und Entscheidungen: [PLAN_REGELDIENST.md](PLAN_REGELDIENST.md), DECISIONS ADR-12 und 4.12. Die vollständige Beschreibung steht im OpenAPI-Dokument (`/api/v1/openapi.json`, Tag `rules-service`).

## Zugang

- Token anlegen (Betrieb, einmal je Dienst): `python -m app.cli service-token-add mass-study [--days 365]`. Das Token `emps_…` erscheint nur dann; gespeichert wird eine Prüfsumme. Verloren → `service-token-revoke mass-study` und neu anlegen. Stand: `service-token-list`.
- Aufruf mit `Authorization: Bearer emps_…`. Cookies sind weder nötig noch wirksam.
- Das Token gehört in den Server des Gegenübers (bei mass-study `apps/server`, Umgebungsvariable), nie in den Browser.
- Reichweite: nur die zwei Routen unten, nur lesend. Keine Projekte, keine Kundendaten. Die Routen starten **nie** eine Auswertung und kosten nichts.
- Grenze: 120 Aufrufe je Minute und Token (`429` mit `Retry-After`).
- Fehler als Problem nach RFC 9457 (`application/problem+json`) mit `code`:

| Status | `code` | Bedeutung |
|---|---|---|
| 401 | `service_token_required` | Kopf fehlt |
| 401 | `service_token_invalid` | unbekannt, abgelaufen oder widerrufen |
| 403 | `service_token_scope` | Token ohne Recht `rules:read` |
| 404 | `commune_unknown` | für die Gemeinde ist kein Planstand importiert |
| 404 | `commune_without_plan` | Gemeinde ohne auswertbaren Planstand (Feld `commune_status`) |
| 404 | `commune_zone_unknown` | Zone gibt es im aktuellen Planstand der Gemeinde nicht |
| 422 | `validation_error` | INSEE-Code oder `scope` ungültig |

## Routen

### `GET /api/v1/service/rules/communes/{insee}`

Planstand der Gemeinde und ihre Zonen mit dem Stand je Umfang. Zonencodes sind die des Géoportail de l'Urbanisme (`libelle` der `zone-urba`), z. B. `UA`, `UCa`.

```json
{
  "format": "emprise-rules/1",
  "commune_insee": "44209",
  "status": "ok",
  "reason": null,
  "plan": {"id": "…", "origin": "gpu", "title": "PLUi …", "du_type": "PLUi", "gpu_doc_id": "…",
           "gpu_update_date": "2026-03-04", "regulation_url": "https://…/reglement.pdf"},
  "zones": [
    {"code": "Uh", "label": "Zone urbaine …", "chapter_code": "Uh",
     "states": [
       {"scope": "house", "status": "simulated", "reason": null, "updated_at": "…"},
       {"scope": "collectif", "status": "not_extracted", "reason": null, "updated_at": null}
     ]}
  ]
}
```

`status` der Gemeinde: `ok` oder ein Grund ohne Regeln (`rnu`, `no_document`, `no_regulation`, `multiple_regulations`, `no_chapters`, `failed`); dann ist `zones` leer.

### `GET /api/v1/service/rules/communes/{insee}/zones/{zone}?scope=collectif`

Regeln der Zone in einem Umfang. `scope`: `collectif` (Standard; Wohngebäude mit mehreren Wohnungen) oder `house` (ein Einfamilienhaus, wie im Konfigurator).

```json
{
  "format": "emprise-rules/1",
  "simulation": true,
  "commune_insee": "44209",
  "scope": "collectif",
  "zone": {"code": "Uh", "label": "…", "chapter_code": "Uh"},
  "status": "simulated",
  "reason": null,
  "plan": {"…": "wie oben"},
  "version": {"id": "…", "version": 1, "status": "simulated", "origin": "extraction",
              "model": "anthropic/claude-opus-5.5", "prompt_version": "g2-prompt-5+collectif",
              "engine_version": "g2-1.2.0", "created_at": "…",
              "coverage": {"effective": 9, "unknown": 2, "mandatory_unknown": 1}},
  "rules": [
    {"kind": "setback_side", "building_kind": "main", "status": "effective", "reason": null,
     "params": {"min_m": 4.0, "height_factor": 0.5, "height_basis": "eave", "allow_on_boundary": false,
                "measured_from": "facade"},
     "page": 34, "quote": "… à une distance au moins égale à la moitié de la hauteur … avec un minimum de 4 m.",
     "quote_verified": true, "source_url": "https://…/reglement.pdf#page=34", "confidence": 0.9,
     "notes": null, "origin": "extraction", "source_document_id": "…", "search_note": null,
     "from_scan": false}
  ],
  "hints": [{"kind": "text_only", "status": "text_only", "params": {"summary": "…"}, "…": "…"}],
  "open_passages": [{"page": 36, "text": "…", "reason": null}],
  "notices": ["notice.rules_simulation", "notice.rules_lotissement", "notice.rules_feed_suggestion"]
}
```

**Stand der Zone (`status`)**

| Wert | Bedeutung | Regeln |
|---|---|---|
| `simulated` | automatisch ausgewertet, nicht vom Büro geprüft | ja |
| `office_reviewed` | vom Büro geprüft | ja |
| `in_progress` | Auswertung läuft | nein |
| `not_extracted` | für diesen Umfang noch nicht ausgewertet; kommt nicht von selbst (bezahlt, nur auf Auftrag im Betrieb) | nein |
| `unavailable` | mit `reason`, z. B. `chapter_not_found` (Zone ohne Kapitel), `refusal`, `not_configured` | nein |

**Regeln.** Eine Regel je `kind` und `building_kind` (`main` Hauptgebäude, `annex` Nebengebäude, `pool`, `any` ohne Unterscheidung).

- `status`: `effective` (Wert, Zitat und Zahlen geprüft), `not_regulated` (ausdrücklich nicht geregelt), `unknown` (offen; `reason` sagt warum, z. B. `missing`, `runs_disagree`, `quote_unverified`, `not_found_after_search`, `out_of_bounds`). Nur `effective` begrenzt; `unknown` ist ein Hinweis, nie ein Standardwert.
- Einheiten: Meter, Anteile 0–1 (40 % = 0.4), Winkel in Grad.
- `page` ist die Seite im PDF von `source_url` (dort mit `#page=`), `quote` wörtlich aus dem Dokument.
- Wichtige Arten für eine Massenstudie und ihre Parameter:

| `kind` | Parameter |
|---|---|
| `setback_street` | `mode` (`min`, `fixed`, `range`, `alignment`), `min_m`, `max_m`, `band` (`building`: ganzer Baukörper im Band, `facade`: nur die Straßenfassade), `measured_from` |
| `setback_side`, `setback_rear` | `min_m`, `height_factor` (Prospect: 0.5 für H/2), `height_basis` (`eave`, `ridge`, `facade_point`), `allow_on_boundary`, `on_boundary_max_height_m`, `measured_from`. Abstand = max(`min_m`, `height_factor` × H). Optional `blind_min_m`, `blind_height_factor`: Abstand vor einer Fassade ohne Ansichten („sans vues“); dann gelten `min_m`/`height_factor` für die Fassade mit Ansichten |
| `setback_between_buildings` | `min_m`, `height_factor` (Gebäude auf derselben Parzelle); optional `height_basis` (`eave`, `ridge`, `facade_point`), `blind_min_m`, `blind_height_factor`, wenn keine der beiden Fassaden Ansichten hat |
| `max_footprint_ratio` | `ratio` (Emprise au sol), `counts_overhangs`, `terrace_counts_above_m` |
| `max_height` | `eave_m`, `ridge_m`, `parapet_m`, `storeys` (Text, z. B. `R+3+C`), `reference`, `measured_at` |
| `unsealed_min` | `ratio` (espaces libres), `full_soil_ratio` (pleine terre), `counting` |
| `max_area` | `sdp_m2`, `footprint_m2` |
| `parking` | `spaces_per_dwelling`, `spaces_per_m2_sdp` |

Die Beschreibung aller Arten liefert auch `GET /api/v1/admin/rule-kinds` (Büro).

**Hinweise (`hints`)**: Vorschriften ohne Parameter, Zusammenfassung auf Französisch in `params.summary`, mit Zitat. Dazu gehören bedingte Werte (Staffeln, Schwellen nach Wohnungszahl, Sozialwohnungsquote) und der Prospect zur gegenüberliegenden Straßenseite (Höhe ≤ Abstand zur Gegenseite).

**Offene Stellen (`open_passages`)**: Textstellen mit Vorschriftscharakter, denen keine Regel zugeordnet ist; der Architekt prüft sie selbst.

## Übernahme in der Massenstudie (Empfehlung)

- Jede `effective`-Regel als Vorschlag mit Zitat und Link anzeigen; übernehmen bestätigt der Architekt (L6). `unknown` und `hints` als Hinweis, nie als Grenze.
- `version.id` mit der Übernahme speichern: Eine neue Auswertung hat eine neue Version.
- `not_extracted`: dem Nutzer sagen, dass die Zone für Wohnungsbau noch nicht gelesen ist (Auftrag an den Betrieb, Kosten).
- Den Stand der Gemeinde (`communes/{insee}`) vor den Regeln abfragen, statt Zonen zu raten.
