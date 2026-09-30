# AN6 – Mandanten: Organisationen, Budget, Branding, API (Emprise Analyse)

> **Status:** geplant und umgesetzt am 29.09.2026 (Auftrag: „weiter mit AN6 und AN7“, Umfang „Plan und technische Basis“; Festlegungen `docs/ANNAHMEN.md` MA01–MA09) · **Bezug:** [PLAN_ANALYSE.md](PLAN_ANALYSE.md) 4 (AN6), 6 (E-A5, E-A6, E-A7); [PLAN_AN7_SCAN.md](PLAN_AN7_SCAN.md) E-AN7-7 (Scan-Kontingent); [PLAN_AN1_PARZELLE.md](PLAN_AN1_PARZELLE.md) (Projekte am Architektenkonto, `organisation_id` offengehalten); ANNAHMEN A4 (Rollen in `staff_user`), UP05 (Projekte ohne Cookie), PU01 (ein Dokument je Prüfsumme), AU07–AU08 (Bericht) · **Festlegungen:** `docs/ANNAHMEN.md` Abschnitt AN6 (Präfix `MA`)
> **Voraussetzung:** AN0–AN5, AN7. Fachregeln: `BACKEND_SPEZIFIKATION.md` 1.2 (L5 Server maßgeblich, L7 Datenschutz), 6 (Zugang), 10 (Sicherheit).

---

## 1. Zweck und Umfang

Emprise Analyse kennt heute ein einziges Büro: Jeder angemeldete Architekt einer Instanz sieht alle Projekte mit Eigentümer, alle hochgeladenen Unterlagen und die Kosten der Instanz. Für ein Abo fremder Büros (RA3) braucht es Organisationen mit eigenen Projekten, Rechten, Kostengrenzen, eigenem Erscheinungsbild in den Ausgaben und einen Zugang ohne Browser.

**Entscheidung des Nutzers (29.09.2026)** auf die Frage nach dem Umfang: **Plan und technische Basis.**

| Enthalten | Nicht enthalten |
|---|---|
| Organisationen, Mitglieder und Rollen | Bezahlung, Rechnungen, Weiterberechnung |
| Projekte und Dokumente je Organisation | AGB, Auftragsverarbeitungsvertrag, Haftungsausschluss als Rechtstexte |
| Monatsbudget je Organisation mit Scan-Kontingent (E-A6, E-AN7-7) | Selbstregistrierung (Konten legt der Betreiber an) |
| Branding in Bericht-PDF und DXF | Branding der Web-Oberfläche |
| API-Schlüssel je Organisation | eigene Domains je Organisation |

**Fremde Büros erst nach juristischer Prüfung (E-A5).** Die Technik trennt Organisationen vollständig; eine zweite Organisation lässt sich aber erst anlegen, wenn der Betreiber es ausdrücklich freischaltet (3.1). Bis dahin gibt es genau eine: das eigene Büro.

---

## 2. Befund

| Stelle | Stand | Folge für AN6 |
|---|---|---|
| `project.organisation_id` | seit AN1 vorhanden, immer NULL, ohne Fremdschlüssel und Index | Fremdschlüssel, Index, beim Anlegen gesetzt; Bestand wird dem eigenen Büro zugeordnet |
| `auth/context.py::require_project_access`, `require_owned_project` | Architekt **und** Projekt mit Eigentümer genügen – jedes Projekt jedes Architekten | zusätzlich gleiche Organisation; sonst `404` wie bisher |
| `GET /projects` | alle Projekte mit Eigentümer (Docstring: „nach Person und Organisation trennt erst AN6“) | nur die der eigenen Organisation |
| `POST /projects` | öffentlich; ohne Anmeldung entsteht ein Kundenprojekt mit Cookie – auch im Analyse-Produkt | im Analyse-Produkt nur mit Konto oder API-Schlüssel (7.1 Nr. 2) |
| `/admin/projects/{id}/…` (Regeln, Korrekturen, Baurahmen, Grundstück) | nur Rolle geprüft; die Analyse-Oberfläche liest Regeln und Baurahmen darüber (PU08) | Projekte mit Eigentümer: gleiche Organisation; Kundenprojekte des Konfigurators: wie heute (Büro) |
| `/admin/rule-sets/{id}`, `/regulation-files/{id}` | nur Rolle; wer eine Kennung kennt, liest Regelwerk bzw. PDF | nur, wenn ein Projekt der eigenen Organisation das Dokument nutzt, oder Betreiberrolle |
| `/admin/rules/coverage`, `/admin/rules/model`, `/admin/sites/review` | für Architekten lesbar: Abdeckung aller Gemeinden mit Kosten, Monatskosten der Instanz, Prüfliste aller Grundstücke | für Mitglieder fremder Organisationen gesperrt (3.2) |
| `rules/extract.py::month_cost`, `_before_call` | eine Summe je Instanz (`rule_extraction_run.cost_usd`) gegen `EMPRISE_RULES_BUDGET_MONTH_USD` | Lauf bekommt die Organisation; Grenze je Organisation zusätzlich zur Instanzgrenze (3.4) |
| Kapitel und Dokumente | ein Dokument je Prüfsumme für alle Projekte (PU01); ein Kapitel wird einmal ausgewertet | bleibt; Kosten trägt die Organisation, die die Auswertung auslöst (3.3) |
| `rules/ocr.py::request` | keine Grenze | Kontingent erkannter Seiten je Organisation und Monat (3.4) |
| `analysis/report.py` | Kopf ohne Absender, Fußzeile mit Hinweis und Prüfsumme | Logo, Name und Schriftfeld der Organisation (3.5) |
| `plan/dxf.py::render` | Textzeilen `notes` auf Ebene `TEXTE` | zusätzlich Schriftfeld auf eigener Ebene (3.5) |
| Anmeldung | nur Cookies (OIDC-Sitzung, Projekt-Cookie), CSRF per Double-Submit für alle schreibenden `/api/`-Aufrufe | Schlüssel im Kopf `Authorization: Bearer …`; ohne Cookie keine CSRF-Prüfung nötig (3.6) |
| `staff_user.roles` | `architect`, `rules_admin`, `catalog_admin`, `ops` – global | bleiben Rollen des Betreibers; dazu Rolle in der Organisation (`admin`, `member`) |
| Rate-Limits | je IP bzw. Adresse | für Schlüssel je Schlüssel |
| `GET /jobs/{id}` | nur Projekt-Cookie oder `ops` | unverändert; Schlüssel und Architekten fragen den Stand über die Fachendpunkte ab |

---

## 3. Fachliche Festlegungen

### 3.1 Organisation und Mitgliedschaft

- **Organisation:** Name, Anzeigename, Art (`operator` für das Büro, das Emprise betreibt, sonst `customer`), Budgetwerte (3.4), Erscheinungsbild (3.5), `active`. Organisationen werden **nur vom Betreiber** angelegt (`python -m app.cli org-create`); es gibt keine Selbstregistrierung.
- **Sperre für fremde Büros (E-A5):** Solange `EMPRISE_EXTERNAL_ORGANISATIONS` nicht `true` ist, lehnt `org-create` jede Organisation der Art `customer` ab. Tests schalten es ein.
- **Mitgliedschaft:** Ein Konto gehört zu genau einer Organisation (E-AN6-1); Rolle `admin` (Mitglieder, Erscheinungsbild, Schlüssel, Verbrauch) oder `member` (Projekte). Die Tabelle erlaubt später mehrere Organisationen je Konto.
- **Mitglieder hinzufügen:** Ein `admin` trägt eine E-Mail-Adresse ein. Emprise legt das Konto (`staff_user` mit Rolle `architect`) und die Mitgliedschaft an. Das Konto beim Identitätsdienst (Authentik) richtet der Betreiber ein; die erste Anmeldung bindet es wie heute über die bestätigte Adresse (A4). Entfernen beendet die Mitgliedschaft und deaktiviert das Konto; Projekte bleiben bei der Organisation.
- **Rollen des Betreibers** (`ops`, `rules_admin`, `catalog_admin`) gibt es nur für Mitglieder der Organisation der Art `operator`. `staff-add` und die Mitgliederverwaltung prüfen das.
- **Bestand:** Die Migration legt, wenn es Architekten oder Projekte mit Eigentümer gibt, die Organisation „Eigenes Büro“ (Art `operator`) an, ordnet alle Konten als `admin` zu (Betreiberrollen gelten nur dort), setzt `organisation_id` an allen Projekten mit Eigentümer und trägt den Betreiber als Zahler aller bisherigen Läufe und Kapitel ein (7.5 Nr. 8). Das Verhalten für das eigene Büro bleibt damit gleich. Das gilt in beiden Produkten (dieselbe Migration, getrennte Datenbanken); im Konfigurator gibt es keine Projekte mit Eigentümer, dort ändert sich nichts Sichtbares.

### 3.2 Zugriff

**Regel:** Ein Projekt einer Organisation ist nur für Mitglieder derselben Organisation und für deren API-Schlüssel sichtbar. Alles andere antwortet `404 not_found` wie heute ein fremdes Projekt. Die Regel steckt zentral in den Zugriffsregeln (`auth/context.py`), nicht in den Endpunkten: So gilt sie auch für Routen, die später dazukommen.

- **Wirksame Rollen:** Außerhalb der Organisation `operator` wirkt von den Rollen eines Kontos nur `architect`; `ops`, `rules_admin` und `catalog_admin` fallen beim Anmelden weg. Ein Konto ohne Organisation hat keine Rechte.
- **`require_roles`** (alle `/admin/…`-Routen): Trägt der Pfad eine `project_id`, muss das Projekt der Organisation des Kontos gehören; ein Kundenprojekt ohne Organisation (Konfigurator) sieht nur die Organisation `operator`. Ohne `project_id` ist die Route nur für die Organisation `operator` – außer sie ist ausdrücklich für alle Organisationen geöffnet (`organisations=True`).

| Bereich | Regel |
|---|---|
| `/projects/{id}/…` (`project`, `owned_project`) | Projekt-Cookie wie heute **oder** Mitglied bzw. Schlüssel derselben Organisation |
| `/admin/projects/{id}/…` (Regeln, Korrekturen, Baurahmen, Grundstück; im Konfigurator Anfrage, Einreichung) | Rolle wie heute und Projekt derselben Organisation (auch mit Betreiberrolle – kein Durchgriff über die Oberfläche, E-AN6-7). Kundenprojekt ohne Organisation: Organisation `operator` |
| `/regulation-files/{id}` | geöffnet für alle Organisationen; Organisation `operator` jede Datei, sonst nur, wenn ein Projekt der eigenen Organisation das Dokument nutzt (`project_regulation`) |
| `/admin/rule-kinds` | geöffnet für alle Organisationen (nur Formularbeschreibung) |
| alle übrigen `/admin/…` (Abdeckung, Regelwerke und ihre Versionen, KI-Modell, Prüfliste der Grundstücke, Referenzlisten, Flags, Betrieb, Katalog) | nur Organisation `operator`, dort wie heute nach Rolle |
| `GET /projects` | Mitglied oder Schlüssel; nur Projekte der eigenen Organisation |
| `POST /projects` | im Analyse-Produkt nur mit Konto oder Schlüssel; setzt `organisation_id`, `owner_staff_user_id` (bei Schlüsseln leer, dafür `created_by = api_key:<id>`) |

Projekte mit Schlüssel angelegt haben keinen Eigentümer im Sinne einer Person. Die bisherige Bedingung „hat Eigentümer“ wird deshalb zu „gehört einer Organisation“ (`organisation_id IS NOT NULL`).

### 3.3 Dokumente je Organisation

- Ein hochgeladenes Dokument bleibt eines je Prüfsumme für alle (PU01, E-AN6-2): Wer dieselbe Datei hochlädt, besitzt ihren Inhalt ohnehin; eine zweite Auswertung kostete nur Geld. Sichtbar ist ein Dokument aber nur über die Projekte der eigenen Organisation – Liste, Datei, Regelwerk, Abdeckung.
- **Kosten:** Eine Auswertung zahlt die Organisation, die sie auslöst (Zonenwahl, Lotwahl, „Neu auswerten“). Das Kapitel merkt sich diese Organisation (`regulation_chapter.billing_organisation_id`); jeder Lauf trägt sie (`rule_extraction_run.organisation_id`), auch Wiederaufnahmen durch `rules_housekeeping`. Nutzt eine zweite Organisation das fertige Kapitel, entstehen keine Kosten.
- Eine Texterkennung (AN7) zählt bei der Organisation, die sie bestätigt; dieselbe Datei wird nur einmal erkannt (SC01).
- Korrekturen (AN4), Annahmen, Name und Notiz hängen wie bisher am Projekt und sind damit je Organisation getrennt.

### 3.4 Budget und Kontingent

- **Monatsbudget der Auswertung** je Organisation in Dollar (`organisation.budget_month_usd`, Vorgabe aus `EMPRISE_ORG_BUDGET_MONTH_USD`, 20 $). Geprüft wie heute vor jedem Aufruf (`_before_call`): erst die Grenze der Instanz, dann die der Organisation des Kapitels. Überschritten → Kapitel `budget_exceeded` wie heute, mit dem Zusatz, wessen Grenze griff; `rules_housekeeping` nimmt es im nächsten Monat wieder auf. Schon bei der Zonenwahl sagt die API `409 organisation_budget_exceeded`, wenn das Budget verbraucht ist, statt ein Kapitel anzulegen, das sofort stehen bleibt.
- **Scan-Kontingent** je Organisation in erkannten Seiten (`organisation.ocr_pages_month`, Vorgabe `EMPRISE_ORG_OCR_PAGES_MONTH`, 2 000 Seiten ≈ 1,7 Stunden Worker). `POST …/ocr` prüft: offene Seiten ≤ verbleibendes Kontingent, sonst `409 ocr_quota_exceeded` mit verbleibender Zahl. Gezählt wird bei der Bestätigung (Tabelle `usage_record`, Art `ocr_pages`), nicht beim Erkennen: Der Hinweis nennt dieselbe Zahl, die abgezogen wird.
- **Monat:** Kalendermonat in UTC wie `month_cost`.
- **Werte ändern** nur der Betreiber (`org-set-budget`), nicht der `admin` der Organisation: Sie sind Teil des Abos.
- **Anzeige:** Seite „Organisation“, Abschnitt Verbrauch (3.7): Auswertung (Dollar, Budget), erkannte Seiten (Kontingent), letzte sechs Monate.

### 3.5 Branding in PDF und DXF

- **Angaben:** Anzeigename, Anschrift (bis 4 Zeilen), Telefon, E-Mail, Website, Kennung (z. B. „N° d'inscription à l'Ordre des architectes“ oder SIRET), Akzentfarbe, Logo.
- **Logo:** PNG oder JPEG, höchstens 1 MB und 2 000 Pixel; mit Pillow geprüft, auf höchstens 800 Pixel verkleinert und als PNG neu geschrieben (entfernt Metadaten und fremde Inhalte), Ablage `organisations/<id>/logo-<revision>.png`. **Kein SVG** (E-AN6-6): WeasyPrint würde darin verlinkte Ressourcen laden.
- **Akzentfarbe:** Hex-Wert; die API lehnt Farben mit zu wenig Kontrast zu Weiß ab (WCAG 4,5 : 1), weil Überschriften und Linien sie tragen.
- **Bericht-PDF:** Kopf der ersten Seite rechts mit Logo, Anzeigename und Schriftfeld (Anschrift, Kontakt, Kennung); auf jeder Seite der Anzeigename oben rechts; Überschriften und Linien in der Akzentfarbe. Das Schriftfeld steht im Kopf, nicht in der Fußzeile: Die Fußzeile trägt schon Hinweis und Prüfsumme, und ein mehrzeiliger Block dort verkleinerte jede Seite (Umsetzung, ANNAHMEN MA05). Ohne Angaben bleibt der Bericht wie heute. `organisation.branding_revision` geht in die Prüfsumme des Berichts; eine Änderung erzeugt beim nächsten Abruf einen neuen Bericht.
- **DXF:** Schriftfeld als Textzeilen auf der Ebene `CARTOUCHE` unter den bisherigen Hinweisen (Büro, Anschrift, Kennung, Projekt, Datum, Variante). Kein Logo: DXF bettet Bilder nicht ein, sondern verweist auf Dateien.
- Die Web-Oberfläche bleibt „Emprise Analyse“.

### 3.6 API-Schlüssel

- **Anlegen** nur ein `admin` in der Oberfläche: Name, Rechte `read` oder `read, write`, Ablauf (Vorgabe 365 Tage, höchstens 730). Der Schlüssel erscheint **einmal**: `emp_<8 Zeichen Präfix>_<32 Byte Base64url>`. Gespeichert werden Präfix und SHA-256 (wie Sitzungen, `hash_token`), dazu Ersteller, `last_used_at` (höchstens alle 10 Minuten geschrieben), `revoked_at`.
- **Anmelden:** `Authorization: Bearer emp_…`. `get_auth` erkennt den Schlüssel, prüft Ablauf, Widerruf und aktive Organisation und liefert einen `ApiPrincipal` (Organisation, Schlüssel, Rechte). Ein Aufruf mit Schlüssel darf **keine** Cookies mitschicken (sonst `400 api_key_with_cookies`); dann entfällt die CSRF-Prüfung, weil ein Browser einen fremden `Authorization`-Kopf nur nach einer CORS-Freigabe sendet, die es nicht gibt.
- **Reichweite:** die Projektendpunkte des Analyse-Produkts (`/projects…`: anlegen, Liste, Grundstück, Hochladen, Reglement, Zonenwahl, Texterkennung, Analyse, Bericht, DXF, GeoJSON). `read` erlaubt GET, `write` zusätzlich alles andere; Kosten begrenzt das Budget der Organisation. **Nicht** erreichbar: `/admin/…`, Mitglieder, Schlüssel, Organisation.
- **Grenzen:** eigenes Rate-Limit je Schlüssel (`EMPRISE_API_KEY_LIMIT_PER_MINUTE`, 60); höchstens 10 aktive Schlüssel je Organisation.
- **Nachvollziehbarkeit:** Audit bei Anlegen und Widerruf; Aufrufe schreiben `actor = api_key:<id>` in Audit und `created_by`.
- **Beschreibung:** Das OpenAPI-Dokument nennt das Schema `bearerAuth`; eine kurze Anleitung (`docs/API_ANALYSE.md`) zeigt den Ablauf mit `curl` (Projekt anlegen, DXF hochladen, Reglement hochladen, Zone wählen, Analyse und DXF holen).

### 3.7 Oberfläche

- Neue Seite **„Organisation“** (`/organisation`, Link im Kopf) mit vier Abschnitten: **Mitglieder** (Liste, hinzufügen per E-Mail, Rolle, entfernen), **Erscheinungsbild** (Logo, Farbe, Schriftfeld, Vorschau des Berichtskopfs als HTML), **Verbrauch** (Monat und Verlauf), **API-Schlüssel** (anlegen, einmalige Anzeige mit Kopierknopf, Liste mit Präfix, Rechten, letzter Nutzung, widerrufen). `member` sieht nur Verbrauch.
- `GET /session` nennt Organisation (Name, Art) und Rolle; der Kopf zeigt den Namen der Organisation.
- Fehlertexte für `organisation_budget_exceeded` und `ocr_quota_exceeded` in Bebauungsplan und Scan-Hinweis.
- Deutsch und Französisch, Telefonbreite.

### 3.8 Daten, Sicherheit, Datenschutz

- **Trennung** in jeder Zugriffsregel, geprüft durch einen Test, der für **jede** Route des Analyse-Produkts mit Projekt- oder Dokumentbezug einen Aufruf aus einer fremden Organisation macht und `404` (bzw. `403` bei `/admin` ohne Projekt) erwartet.
- **Betreiber** sieht Projekte fremder Organisationen nicht in der Oberfläche (E-AN6-7); Unterstützung nur mit Zustimmung und über die Datenbank, im Verarbeitungsverzeichnis zu beschreiben.
- **Schlüssel** nur als Hash; Präfix zum Wiedererkennen; ein verlorener Schlüssel wird widerrufen, nicht wiederhergestellt.
- **Personenbezogene Daten:** Mitglieder (Name, E-Mail), Schriftfeld (Kontakt des Büros). Keine neuen Empfänger; nichts verlässt die Instanz.
- **Vor fremden Büros offen** (mit E-A5 zu klären, nicht Teil von AN6): Datenauskunft und Export je Organisation (UP07), Löschen einer Organisation am Vertragsende, AVV, Aufbewahrungsfristen.

---

## 4. Architektur

### 4.1 Datenmodell (Migration 0020)

| Tabelle | Inhalt |
|---|---|
| `organisation` | `id`, `name` (eindeutig), `display_name`, `kind` (`operator`/`customer`), `active`, `budget_month_usd`, `ocr_pages_month`, `address_lines text[]`, `phone`, `email`, `website`, `registration`, `accent_color`, `logo_key`, `branding_revision int`, `created_at`, `created_by` |
| `organisation_member` | `organisation_id` FK, `staff_user_id` FK (eindeutig, E-AN6-1), `role` (`admin`/`member`), `created_at`, `created_by` |
| `api_key` | `id`, `organisation_id` FK, `name`, `prefix` (eindeutig), `token_hash` (eindeutig), `scopes text[]`, `expires_at`, `last_used_at`, `revoked_at`, `created_at`, `created_by` |
| `usage_record` | `id`, `organisation_id` FK, `kind` (`ocr_pages`), `quantity`, `reference` (Datei), `created_at`, `created_by` |
| `project` | Fremdschlüssel und Index auf `organisation_id` (`ON DELETE RESTRICT`) |
| `rule_extraction_run` | `organisation_id` NULL (Läufe vor AN6 und des GPU-Wegs) |
| `regulation_chapter` | `billing_organisation_id` NULL |
| `audit_log` | Bedingung `actor_type` um `api_key` erweitert |

Datenmigration nach 3.1 (Bestand). Auswertungskosten bleiben in `rule_extraction_run`; `usage_record` nimmt nur, was dort nicht steht.

### 4.2 Backend

- **`app/platform/organisations.py`:** Modelle, Dienst (anlegen, Mitglieder, Budgetstand `org_month_cost`, `org_ocr_pages`), Branding (Logo prüfen und ablegen, Farbe prüfen). Kern, weil `rules`, `analysis` und `plan` es brauchen.
- **`app/platform/auth/`:** `StaffPrincipal` bekommt `organisation_id`, `organisation_kind`, `org_role`; neuer `ApiPrincipal`; `get_auth` liest den Bearer-Kopf; `api_keys.py` (erzeugen, prüfen); Zugriffsregeln nach 3.2, neue Regeln `org_admin` und `org_member`. `CsrfMiddleware` überspringt Aufrufe mit Bearer-Kopf ohne Cookies.
- **`app/platform/org_api.py`:** `GET/PATCH /organisation`, `PUT/DELETE /organisation/logo`, `GET/POST /organisation/members`, `PATCH/DELETE /organisation/members/{id}`, `GET /organisation/usage`, `GET/POST /organisation/api-keys`, `DELETE /organisation/api-keys/{id}` – nur mit Konto, nie mit Schlüssel.
- **CLI:** `org-create` (mit Sperre nach 3.1), `org-member-add`, `org-set-budget`, `org-list`.
- **`rules`:** Organisation in Job-Nutzlast und `_Calls`; `_before_call` mit Organisationsgrenze; Zonen-/Lotwahl prüft vorab; `ocr.request` prüft und bucht Kontingent; Sichtbarkeit von Dokument, Datei und Regelwerk über `project_regulation` der Organisation.
- **`analysis/report.py`, `plan/dxf.py`:** Branding nach 3.5; `ReportData` bekommt `branding`, die Prüfsumme `branding_revision`.
- **Produkte:** `POST /projects` im Analyse-Produkt ohne anonyme Projekte (Einstellung am Produkt, `products.py`).

### 4.3 Frontend

- `api/organisation.ts` (Hooks), `products/analyse/Organisation.tsx` mit Abschnitten `Mitglieder.tsx`, `Erscheinungsbild.tsx`, `Verbrauch.tsx`, `ApiSchluessel.tsx`; Link im Kopf; Session-Typ mit Organisation.
- Fehlertexte de/fr, Spiegelung der neuen Problemcodes in die Backend-Übersetzungen, wo der Bericht sie braucht (keine).

---

## 5. Arbeitsschritte

1. **Migration 0020 und Modelle**, Datenmigration Bestand; CLI `org-create` (Sperre), `org-member-add`, `org-set-budget`, `org-list`.
2. **Zugriff:** Principal mit Organisation, Regeln nach 3.2, `POST /projects` im Analyse-Produkt, Listen und Dateien. **Trennungstest** über alle Routen (zwei Organisationen, je ein Projekt mit Grundstück, Reglement, Korrektur, Bericht).
3. **Budget und Kontingent:** Organisation in Lauf und Kapitel, Prüfungen, `usage_record`, Verbrauchsabfrage. Tests mit `FakeExtractor` (kein bezahlter Lauf).
4. **Organisation-API und Oberfläche:** Mitglieder, Verbrauch; Seite „Organisation“.
5. **Branding:** Logo, Farbe, Schriftfeld; Bericht und DXF; Prüfsumme; Oberfläche mit Vorschau.
6. **API-Schlüssel:** Erzeugen, Anmelden, Rechte, Rate-Limit, CSRF-Ausnahme, OpenAPI-Schema, Oberfläche, `docs/API_ANALYSE.md`.
7. **Abnahme** (6) und Dokumentation: ANNAHMEN MA01 ff., BETRIEB 15 (Einrichten, CLI, Budget, Schlüssel), PLAN_ANALYSE, README, AGENTS.

Geschätzt 8–10 Arbeitstage; Schritt 2 ist der wichtigste und wird zuerst vollständig getestet.

---

## 6. Abnahme

1. **Vollständiger Prüflauf** Backend und Frontend; Konfigurator unverändert (seine Tests, dazu Büro-Ansicht eines Kundenprojekts im Browser).
2. **Trennung:** Trennungstest grün; im Browser zwei Konten verschiedener Organisationen (Sperre in der lokalen Umgebung aufgehoben) – keines sieht Projekte, Dokumente, Dateien oder Verbrauch des anderen, auch nicht mit kopierter Kennung in der Adresse.
3. **Bestand:** Nach der Migration sieht das eigene Büro alle bisherigen Projekte und Dokumente wie vorher; Bericht, DXF und Regeln unverändert (bis auf das Schriftfeld, sobald Angaben gesetzt sind).
4. **Budget:** Organisationsbudget auf 0,01 $ → Zonenwahl `409 organisation_budget_exceeded`; Instanzbudget unberührt; nach Erhöhung läuft die Auswertung (mit `FakeExtractor`, ohne Kosten). Scan-Kontingent 50 Seiten → Beyenes-Scan (74 Seiten) `409 ocr_quota_exceeded` mit Hinweis.
5. **Branding:** Logo und Schriftfeld im Bericht (de/fr) und im DXF; Wechsel der Farbe erzeugt einen neuen Bericht; SVG, zu großes Bild und Farbe mit zu wenig Kontrast werden abgelehnt.
6. **API:** mit `curl` nach `docs/API_ANALYSE.md`: Projekt anlegen, DXF hochladen, Analyse und DXF holen; `read` darf nicht hochladen (`403`), widerrufener Schlüssel `401`, fremdes Projekt `404`, Schlüssel mit Cookie `400`; Rate-Limit greift.
7. **Oberfläche:** Seite „Organisation“ de/fr, Telefonbreite; `member` sieht nur Verbrauch.

**Ergebnis (29.09.2026, lokaler Analyse-Stack; fremde Organisation „Atelier Sud“ mit aufgehobener Sperre nur lokal):**

| Nr. | Ergebnis |
|---|---|
| 1 | Backend **776 bestanden**, 2 übersprungen (S3) nach allen Änderungen aus 7.5; ruff, Format, mypy sauber, `openapi.json` gleich dem Code. Frontend 36 Dateien, 243 Tests, Typprüfung, Lint, Build (auch im Image). Konfigurator-Stack mit neuem Image: 0020 auf der lokalen Datenbank – „Eigenes Büro“ mit dem vorhandenen Konto und dem einen Projekt mit Eigentümer, 6 Läufe und 12 Kapitel beim Betreiber, 289 Kundenprojekte ohne Organisation; Büro-Ansicht der Anfrage EMP-2026-000002 (Anfrage, Versionen, Nachrichten, Grundstück, Gelände, Risiken, Regeln) lädt vollständig, alle Aufrufe `200`, Rollen `architect, ops` wie vorher |
| 2 | Trennungstest über **alle** Routen mit `{project_id}` grün (fremde Organisation: `403`/`404`), dazu Dateien, Listen und `/admin/…` ohne Projekt. Im Browser: Atelier Sud (als `admin` und als `member`) sieht nur ihr eigenes Projekt, keine Modellwahl, Verbrauch 0,00 $; das eigene Büro sieht seine 6 Projekte, nicht das von Atelier Sud, und bekommt mit kopierter Kennung `404` auf Projekt, Grundstück, Analyse, Bericht und Regeln; umgekehrt Atelier Sud (Sitzung und Schlüssel) auf ein Büroprojekt ebenfalls `404` |
| 3 | Analyse-Datenbank nach 0020: „Eigenes Büro“ mit dem vorhandenen Konto und allen 6 Projekten mit Eigentümer; alle 6 Läufe und 21 Kapitel beim Betreiber (erst nach 7.5 Nr. 8), Verbrauch 1,05 $ wie vor dem Update; ein anonymes Kundenprojekt vom 20.09. bleibt wie vorgesehen ohne Organisation. Liste, Modellwahl und Projektseiten wie vorher. Prüfsumme des Berichts: AN6 fügt nur `branding` hinzu, für das Büro `None`, damit bleibt sie gleich (`report_hash`, Test). Neu erzeugte Berichte zweier Bestandsprojekte hatten trotzdem andere Prüfsummen als die von 01:30 und 08:50 – Ursache sind die noch nicht committeten Änderungen aus AN5/AN7 und beim Scan-Projekt die Texterkennung, die erst nach dem Bericht fertig wurde, nicht AN6. DXF ohne Schriftfeld ohne Ebene `CARTOUCHE` |
| 4 | Mit `FakeExtractor` in Tests, nicht im Browser (die lokale Zonenwahl liefe mit echtem Schlüssel): Budget 0 → Zonenwahl `409 organisation_budget_exceeded`, kein Job; nach Erhöhung läuft die Auswertung, Kosten bei Atelier Sud; halbiertes Budget hält die laufende Auswertung an (`organisation_budget_exceeded` am Kapitel, Wiederaufnahme erst nach Erhöhung), die Grenze der Instanz bleibt unberührt. Kontingent 1 Seite → Texterkennung von 2 Scan-Seiten `409 ocr_quota_exceeded` mit `remaining`; nach Erhöhung gebucht (2 Seiten, im Verbrauch sichtbar). Der Beyenes-Scan wurde nicht erneut hochgeladen (Kosten und Laufzeit ohne neuen Erkenntniswert) |
| 5 | Bericht über den API-Schlüssel in fr und de: Logo, Name in der Akzentfarbe, Adresse, Telefon und Ordre-Nummer oben rechts auf Seite 1, Name im Kopf jeder Seite; DXF-Ebene `CARTOUCHE` mit sechs Zeilen (Name, Adresse, Telefon, Ordre, „Projet : … - local“). Im Browser Logo hochgeladen, SVG abgelehnt, Farbe mit zu wenig Kontrast sperrt das Speichern; zu großes Bild und neuer Bericht nach Farbwechsel (andere Prüfsumme) im Test |
| 6 | curl nach `docs/API_ANALYSE.md` mit Lese- und Schreibschlüssel: Projekt anlegen, Parzelle hochladen, Analyse, DXF und Bericht holen; Leseschlüssel beim Hochladen `403`, nach Widerruf `401`, fremdes Projekt `404`, Schlüssel mit Cookie `400`, `/flags`, `/session` und `/organisation` mit Schlüssel `403 api_key_not_allowed`; Rate-Limit: von 70 schnellen Aufrufen 64 × `200`, 6 × `429`. Änderung am Projekt im Audit-Log als `api_key` (Test) |
| 7 | Seite „Organisation“ deutsch und französisch vollständig übersetzt; 375 px ohne seitliches Scrollen. Als `member`: nur „Verbrauch“, keine Eingaben; `members`, `api-keys` und `PATCH /organisation` `403`, Verbrauch `200`; die Projektliste zeigt das über den Schlüssel angelegte Projekt der Organisation |

---

## 7. Prüfprotokoll

### 7.1 Entwurf (vor dem Bau)

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 1 | Die Analyse-Oberfläche liest Regeln, Korrekturen und Baurahmen über `/admin/projects/{id}/…` (PU08). Eine Trennung nur an `/projects/…` ließe diese Wege offen | Fremde Organisation liest mit kopierter Kennung Regeln und Grundstück | 3.2: dieselbe Regel für `/admin/projects/{id}` bei Projekten mit Eigentümer; Trennungstest über **alle** Routen |
| 2 | `POST /projects` ist öffentlich; im Analyse-Produkt entstehen so Projekte ohne Eigentümer, die über `/admin/projects/{id}` jedem Architekten mit Rolle offenstehen | Lücke neben der Organisationsregel | 3.2: im Analyse-Produkt nur mit Konto oder Schlüssel |
| 3 | Kapitel werden von mehreren Organisationen geteilt; ein Lauf, den `rules_housekeeping` wieder aufnimmt, hat keinen Auslöser | Kosten ohne Organisation, Budget umgangen | 3.3: Kapitel merkt sich die zahlende Organisation (`billing_organisation_id`), Läufe erben sie |
| 4 | Eine zweite Organisation wählt einen weiteren Sektor desselben Kapitels – das Kapitel wird neu ausgewertet (E-AN2-2) | Kosten bei der zweiten, obwohl die erste das Kapitel ausgelöst hat | 3.3: zahlt, wer die Neuauswertung auslöst – gewollt, weil sie seinen Sektor betrifft |
| 5 | `/admin/rules/model` und `/admin/rules/coverage` zeigen Monatskosten und Gemeinden der ganzen Instanz | Verbrauch anderer Büros sichtbar | 3.2: beide nur für den Betreiber; den eigenen Verbrauch zeigt die Seite Organisation (3.7) |
| 6 | Die Bedingung „Projekt hat Eigentümer“ passt nicht zu Projekten aus der API | Schlüssel-Projekte fielen durch alle Regeln | 3.2: Bedingung wird „gehört einer Organisation“ |
| 7 | CSRF: Ein Aufruf mit Schlüssel **und** Sitzungscookie könnte die Prüfung umgehen, wenn nur der Kopf zählte | Angriff über eine fremde Seite mit gesetztem Kopf | 3.6: Schlüssel und Cookies schließen sich aus (`400`); Browser senden fremde `Authorization`-Köpfe nur nach CORS-Freigabe |
| 8 | Ein SVG-Logo lädt in WeasyPrint verlinkte Ressourcen | Anfragen an fremde Server beim Setzen des Berichts | 3.5: nur PNG/JPEG, neu geschrieben |
| 9 | Das Branding ändert den Bericht, aber nicht dessen Prüfsumme | alter Bericht mit altem Logo würde wiederverwendet | 3.5: `branding_revision` in der Prüfsumme |
| 10 | Die Scan-Grenze beim Erkennen zu zählen hieße: Ein Abbruch zählt halb, der Hinweis nennt eine andere Zahl | Verwirrende Abrechnung | 3.4: Buchung bei der Bestätigung mit der Zahl des Hinweises |
| 11 | Betreiberrollen global in `staff_user.roles` – ein fremdes Konto mit `ops` sähe Flags, Referenzlisten, alle Jobs | Rechteausweitung | 3.1: Betreiberrollen nur in der Organisation `operator`, geprüft beim Vergeben |
| 12 | Der Bestand hat nur ein Büro; ohne Datenmigration verlöre das eigene Büro nach dem Einspielen alle Projekte | Ausfall | 3.1: Migration legt „Eigenes Büro“ an und ordnet zu; Abnahme 3 |
| 13 | Der Konfigurator nutzt dieselben Zugriffsregeln für Kundenprojekte des Büros | Änderung könnte das Büro aussperren | 3.2: Kundenprojekte (ohne Organisation) behalten ihre Regel; Abnahme 1 im Browser |

**Zweite Prüfung gegen den Code (29.09.2026, vor dem Bau):**

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 14 | `POST /admin/rule-sets/{id}/versions` steht Architekten offen und ändert die Regeln einer Zone „für alle Projekte in dieser Zone“ – bei geteilten Dokumenten (3.3) auch die fremder Organisationen | Ein Büro verändert die Analyse eines anderen | 3.2: alle `/admin/…` ohne Projekt nur für `operator`; Korrekturen der Kunden bleiben je Projekt (AN4) |
| 15 | Organisationsprüfung je Endpunkt nachzutragen hieße rund 30 Stellen ändern und bei jeder neuen Route daran denken | Vergessene Route = Datenleck | 3.2: zentral in `require_roles` über den Pfadparameter `project_id` und über die wirksamen Rollen; Trennungstest über alle Routen |
| 16 | `/admin/rules/model` zeigt Modell und Monatskosten der Instanz; Kosten je Organisation herauszurechnen lohnt nicht, weil die Seite Organisation den eigenen Verbrauch zeigt | – | 3.2: nur `operator` (statt Kosten zu filtern) |
| 17 | `audit_log.actor_type` erlaubt nur `staff`, `customer`, `system` | Aufrufe mit Schlüssel ließen sich nicht protokollieren | 4.1: Wert `api_key` ergänzen |
| 18 | Die Testhilfe `login_as` legt Konten ohne Organisation an; nach 3.2 hätten sie keine Rechte | Alle Bürotests schlügen fehl | Testhilfe ordnet der Organisation `operator` zu, mit Parameter für eine andere |
| 19 | `require_owned_project` gibt `StaffPrincipal` zurück, die Endpunkte nutzen `staff.actor_id` | Schlüssel passten nicht in die Signatur | gemeinsame Schnittstelle `Principal` (Konto oder Schlüssel) mit `actor_id`, `actor_type`, `organisation_id` |
| 20 | `rules_housekeeping` nimmt `budget_exceeded`-Kapitel nur nach der Instanzgrenze wieder auf | Kapitel einer Organisation mit neuem Monat oder erhöhtem Budget blieben liegen – oder liefen trotz erschöpfter Organisation wieder an | Fehler `organisation_budget_exceeded` getrennt; Wiederaufnahme prüft die Organisation des Kapitels |

### 7.2 Geprüfte Alternativen

| Alternative | Verworfen, weil | Besser, wenn … |
|---|---|---|
| Eine Datenbank oder Instanz je Organisation | vielfacher Betrieb (Stacks, Sicherungen, Migrationen) für wenige Kunden auf Unraid; geteilte Auswertungen unmöglich | Kunden Trennung auf Infrastrukturebene vertraglich verlangen |
| Row-Level Security in PostgreSQL | stärkste Trennung, aber jede Abfrage bräuchte den Mandanten in der Sitzung, Jobs und Wartung laufen organisationsübergreifend; hoher Umbau | viele Organisationen und ein Audit sie fordert – als zweite Schicht nachrüstbar |
| Rollen und Organisation aus Authentik-Gruppen | Rollen liegen bewusst in der Anwendung (A4); Wechsel des Identitätsdienstes bliebe einfach | Selbstregistrierung über Authentik kommt |
| OAuth-Client-Credentials statt API-Schlüssel | mehr Aufwand für Kunden und Betreiber; Authentik müsste Clients je Organisation verwalten | Integrationen großer Kunden das verlangen |
| Dokumente je Organisation getrennt (keine Prüfsummen-Deduplizierung) | Zweitauswertung derselben öffentlichen Unterlage kostet erneut 1–2 $ je Kapitel; der Besitz der Datei belegt ohnehin den Inhalt | Kunden Unterlagen hochladen, deren bloße Existenz vertraulich ist |
| Budget je Konto statt je Organisation | Abo und Rechnung gehören zur Organisation | – |
| SVG-Logos | Sicherheitsrisiko beim Setzen (7.1 Nr. 8) | ein sicherer SVG-Filter vorhanden ist |

### 7.3 Bewusste Grenzen

Keine Bezahlung, keine Rechtstexte, keine Selbstregistrierung, kein Branding der Oberfläche, keine eigene Domain je Organisation, ein Konto gehört zu einer Organisation, kein Löschen und kein Export einer Organisation (vor fremden Büros mit E-A5), kein Durchgriff des Betreibers über die Oberfläche.

### 7.4 Offene Festlegungen (mit Empfehlung)

| Nr. | Frage | Empfehlung |
|---|---|---|
| E-AN6-1 | Mehrere Organisationen je Konto? | Nein, eine (eindeutig in `organisation_member`); die Tabelle erlaubt es später |
| E-AN6-2 | Dokumente über Organisationen teilen? | Ja, nach Prüfsumme; Sichtbarkeit nur über eigene Projekte, Kosten beim Auslöser (3.3) |
| E-AN6-3 | Rollen in der Organisation | `admin` und `member` |
| E-AN6-4 | Vorgaben für Budget und Scan-Kontingent | 20 $ und 2 000 Seiten je Monat, änderbar nur durch den Betreiber |
| E-AN6-5 | Rechte der Schlüssel | `read` und `write`; Kosten begrenzt das Budget |
| E-AN6-6 | Logo-Formate | PNG und JPEG, kein SVG |
| E-AN6-7 | Durchgriff des Betreibers auf fremde Projekte | keiner über die Oberfläche; nur mit Zustimmung über die Datenbank |
| E-AN6-8 | Freischaltung fremder Büros | technisch gesperrt (`EMPRISE_EXTERNAL_ORGANISATIONS`), bis E-A5 geklärt ist |
| E-AN6-9 | Mitglied hinzufügen ohne Selbstregistrierung | `admin` trägt die Adresse ein, der Betreiber richtet das Konto bei Authentik ein; keine Einladungsmail in AN6 |
| E-AN6-10 | Monatsgrenze | Kalendermonat UTC wie bisher |

### 7.5 Beim Bau gefunden

| Nr. | Befund | Folge |
|---|---|---|
| 1 | Öffentliche Routen ohne `get_auth` (`/flags`, `/geocode` …) hätten einen API-Schlüssel stillschweigend übergangen und anonym geantwortet | Die CSRF-Middleware lehnt einen Schlüssel außerhalb von `/api/v1/projects…` ab (`403 api_key_not_allowed`), bevor eine Route läuft (MA03) |
| 2 | Die Projektliste zeigt die Modellwahl über `GET /admin/rules/model` – für fremde Büros jetzt `403`, und die Antwort nennt den Namen der Person, die das Modell gewählt hat | Die Oberfläche zeigt die Modellwahl nur der Organisation `operator`; die Route bleibt dem Betrieb vorbehalten (MA02) |
| 3 | Drei ältere Tests legten im Analyse-Produkt anonym ein Kundenprojekt an, um zu zeigen, dass es nichts sieht; das lehnt `POST /projects` jetzt mit `401` ab | Hilfsfunktion `customer_project` legt das Projekt mit Cookie wie der Konfigurator an |
| 4 | `to_char(…, 'YYYY-MM')` als gebundener Parameter steht in SELECT und GROUP BY als zwei Parameter; PostgreSQL lehnt die Gruppierung ab | Formatangabe als Literal (`MONTH_FORMAT`) |
| 5 | `EmailStr` lehnt reservierte Domains (`.test`, `.local`) ab | Solche Konten nur über `staff-add`; festgehalten in MA07 und README |
| 6 | Ein mehrzeiliges Schriftfeld in der Fußzeile des Berichts verkleinerte jede Seite | Schriftfeld im Kopf der ersten Seite, Name oben rechts auf jeder Seite (3.5 angepasst, MA05) |
| 7 | „Budget erreicht“ mit Zusatz, wessen Grenze griff, hätte Oberfläche und Wiederaufnahme dieselbe Zeichenkette zerlegen lassen | Eigener Fehlercode `organisation_budget_exceeded` am Kapitel (MA04) |
| 8 | **Abnahme 3:** Nach der Migration zeigte der Verbrauch des Betreibers 0 $, obwohl im selben Monat Läufe für 1,05 $ liefen – Läufe und Kapitel vor AN6 hatten keine Organisation | Migration 0020 trägt den Betreiber als Zahler aller bisherigen Läufe und Kapitel ein (MA01); Scan-Seiten vor AN6 werden nicht nachgebucht (keine Buchungen vorhanden) |
