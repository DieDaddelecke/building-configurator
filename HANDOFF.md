# Hand-off für die nächste Session

> **Stand:** 18.09.2026 · **Letzte Session:** H1 Hauskatalog geplant und das Backend umgesetzt (Datenmodell, XLSX/DXF-Import, Katalogpflege-API), gepusht, CI grün. Davor: Stand von G1 Weg E korrigiert (war entgegen dem Vermerk schon gepusht), Modul-Landkarte erläutert, Entscheidung D14 getroffen.
> Diese Datei ist eine Momentaufnahme und wird bei jedem `/handoff` vollständig neu geschrieben. Die Historie steht in [AENDERUNGEN.md](AENDERUNGEN.md).

---

## 1. Aktueller Stand

- **Git:** `main` auf https://github.com/DieDaddelecke/building-configurator (privat), gepusht, CI grün. Letzter Commit `596e075` (H1 Backend, Lauf 35308790615), davor `a37e76d`/`11a6e64` (G1 Weg E, Lauf 35258574782).
- **R0 Plattform (Plan 3.2):** anbieterunabhängiger Teil fertig; noch nicht auf Unraid ausgeliefert. [docs/ANNAHMEN.md](docs/ANNAHMEN.md) A1–A27.
- **G1–G3 (Grundstück, Regelwerk, Baurahmen):** fertig, lokal intern freigeschaltet, gepusht. G1 um Weg E ergänzt (ANNAHMEN G01–G30); G2 ohne Schlüssel der Claude API noch keine echte Auswertung (ANNAHMEN RW01–RW27); G3 über 200 echte Parzellen geprüft (ANNAHMEN BR01–BR15, [docs/PLAN_G3_BAURAHMEN.md](docs/PLAN_G3_BAURAHMEN.md)).
- **H1 Hauskatalog – Backend fertig, Frontend offen:** [docs/PLAN_H1_HAUSKATALOG.md](docs/PLAN_H1_HAUSKATALOG.md), `backend/app/catalog/`. Typen/Linien/Optionen/Preiskatalog als Identität+Version, unveränderlich nach Veröffentlichung (Trigger `forbid_published_modification`, bedingt auf `status='published'`, anders als das unbedingte `rule_no_update`). Erfassung ohne IFC aus XLSX (Blätter „Kennwerte“, „Räume“, „Preise“) und DXF (Layer `EMPRISE_FOOTPRINT_FACADE`/`_PROJECTION`). Nur Büro-Endpunkte unter `/admin/catalog/...`, Rolle `catalog_admin` als Editor (ANNAHMEN H01–H09). 28 neue Tests, alle grün.
- **Wichtig – Modul A übersprungen:** Der Umsetzungsplan sieht die Reihenfolge A → H1 → H2 → H3 → V vor (Kapitel 5); diese Session hat direkt mit H1 begonnen, A (Anfrage) existiert noch nicht. Vor Modul H2 prüfen, ob A nachgeholt werden soll (siehe Abschnitt 6).
- **Lokaler Stack `emprise`:** mit dem H1-Stand dieser Session noch nicht neu gebaut/getestet (nur im CI-Container geprüft); Migration 0007 muss beim nächsten lokalen Start mitlaufen.
- **Umsetzungsplan:** R0, G1, G2, G3, H1 (Backend) beauftragt; D1–D4, D11, D14 entschieden, D12 und D13 offen (Plan 9). **Spezifikation:** unverändert, Korrekturen S1–S14 offen (4.4).

## 2. Ergebnisse der letzten Session, die nur im Chat standen

- **Modul-Landkarte erläutert:** Es gibt kein Modul „G4“; die G-Kette endet bei G3. Nächste Module: A (Anfrage), dann H1–H3 (Konfigurator), V (Übergabe), X2–X5 (Ausbau). Inhalt von Modul A im Detail erklärt (Kontakt, Snapshot, Büro-Prüfung).
- **Gesamtablauf geklärt (→ D14):** Nutzer erinnerte an die ursprünglich geplante Reihenfolge – Kunde konfiguriert sein Haus frei, ohne Büro-Input, die Anfrage entsteht erst danach. Abgeglichen mit Spez. 3.4 (Gesamtablauf): stimmt für den fertigen Konfigurator (G3 → H2 → H3 → V). Modul A direkt nach G3 ist der **zusätzliche** Notausgang für die Zeit, solange H1–H3 noch nicht existieren bzw. für Kunden, die nicht konfigurieren wollen – bleibt laut D14 dauerhaft bestehen, auch mit gültigem Baurahmen.
- **H1-Plan (Kapitel 9) vom Nutzer entschieden:** fünf Platzhalter-Typen statt drei (zwei neu erarbeitet: Carré – ebenerdig, Walmdach; Attique – drei Ebenen mit ausgebautem Dachgeschoss, nah an den Höhengrenzen der Zone; Kennwerte in Plan Kapitel 12); Katalogpflege über `architect`; Grundriss-PDF bleibt intern.
- **Rollenkorrektur während der Umsetzung:** `catalog_admin` existierte bereits seit R0 (ungenutzt) – die eigene Empfehlung „architect reicht“ war ein Rechercheversehen und wurde vor dem Bau der API auf `catalog_admin` als Editor-Rolle korrigiert (H01), ohne erneute Rückfrage.
- **Trigger-Fehler beim Schreiben gefunden:** Der erste Entwurf von `forbid_published_modification` gab bei jedem Aufruf `RETURN NULL` zurück, was auch unveröffentlichte Entwürfe stillschweigend am Schreiben gehindert hätte – vor dem Testen bemerkt und auf `RETURN NEW`/`RETURN OLD` korrigiert.

## 3. Offene Entscheidungen des Nutzers

| Priorität | Nr. | Frage | Wo |
|---|---|---|---|
| 1 | – | Konto und Schlüssel der Claude API (vom Nutzer selbst in `.env`); Monatsbudget (Vorschlag 150 $, lokal 20 $) | BETRIEB 9, RW11 |
| 1 | – | Hostname für Authentik (Vorschlag `auth.aslani.work`); Cloudflare „DNS only“ (empfohlen, L8) oder Proxy | Unraid README 2, A26 |
| 1 | E2 | Mailanbieter: EU-Drittanbieter akzeptiert, welcher konkret (z. B. Brevo, Scaleway TEM) noch offen | Spez. 16, BETRIEB 5 |
| 2 (vor Beta) | – | Rechtliche Prüfung der ungeprüften Simulation: Wortlaut der Hinweise, Haftung, Bezeichnungen der Konturen, Hinweis für Weg E | Plan 6.9, RW16, Plan G3 10 |
| 2 | – | Wer schreibt die Hinweistexte L7? Bis dahin Rückfalltext | G16, G30, BR11, Plan 8 |
| 2 | – | Datenschutzerklärung: Kartenkacheln direkt vom IGN – Hinweis genügt oder eigener Kachel-Proxy? Empfehlung Hinweis | G15 |
| 2 | D8 | Bietet das Büro Honorar oder Bauleistung an? | Plan 9 |
| 2 | D5, D6 | Betriebsverantwortung; Datenschutzrolle Emprise ↔ Büro | Plan 9 |
| 2 | – | Standort des Unraid-Servers bestätigen (EU, L8) | – |
| 3 (vor H2) | D12 | Wie stark schränken simulierte Regeln den Konfigurator ein? Engste Kontur als Grenze, weiteste als Suchraum (Vorschlag) | Plan 9, BR01 |
| 3 (vor H2) | D13 | Wie geht H2 mit einem Grundstück ohne Baurahmen um (Weg E)? Vorschlag: Platzierung ohne Abstandsprüfung | Plan 9, 3.3 |
| 3 | – | Modul A nachholen, bevor H2 begonnen wird, oder bewusst erst später (Abschnitt 6)? | neu, diese Session |
| 3 | – | Gegenprüfung statt zweitem Lauf (RW19) in den Umsetzungsplan 3.4 übernehmen? | RW19, Plan 3.4 |
| 3 | – | ODbL des Katasters vor Modul V klären; Géorisques-Token vor öffentlichem Start | G12, G17 |
| 3 | – | Außerhalb des Einzugsgebiets bis Modul A nur Hinweis – ausreichend? | G18 |
| 3 | – | Umsetzungsplan als Ganzes freigeben; D2 (Beta, öffentlich), D7, D10, E1–E12 | Plan 9, Spez. 16 |
| 3 | – | Große Dokumente zu Sessionbeginn kapitelweise oder vollständig lesen? (seit 13.09. unbeantwortet) | CLAUDE.md Punkt 4 |

## 4. Offene Arbeitspunkte

### 4.1 H1 abschließen

1. Katalogpflege-Oberfläche im Frontend (Büro-Route, kein Kundenschritt): Typ-Import mit Vorschau, Fassadenrollen zuweisen, Preise/RE2020 erfassen, veröffentlichen.
2. Fünf Platzhalter-Typen als echte XLSX/DXF-Dateien erfassen (Kennwerte in Plan H1 Kapitel 12; DXF-Umriss dort nur als Rechteck angenommen, muss noch gezeichnet werden) und über die API hochladen.
3. Linien (Base/Confort/Signature) und Optionen vor den Typen anlegen und veröffentlichen, sonst meldet der Typ-Import `catalog_reference_unknown`.
4. `docs/BETRIEB.md`-Abschnitt für H1 (Migration 0007, keine neuen externen Dienste, neue Python-Abhängigkeiten openpyxl/ezdxf/python-multipart im Image).
5. Lokalen Stack neu bauen und Migration 0007 anwenden, bevor im Browser geprüft wird.

### 4.2 G2 und G3 abschließen (sobald ein Schlüssel eingetragen ist)

1. Schlüssel in `.env`, `docker compose up -d`; sofort `docker compose exec api python -m app.cli rules-extract --pending`. Kosten, Dauer, Anteil der Gegenprüfung in BETRIEB 9 eintragen.
2. Wegen `g2-prompt-3` alle Kapitel neu auswerten; danach prüfen, ob `setback_street.band` gefüllt ist.
3. Referenzmenge der Zonen von Treillières messen (Spez. 11.4).
4. `envelope-check --commune 44209` über alle Zonen wiederholen, Anteil unvollständiger Konturen in BETRIEB 10 festhalten.
5. Danach Beta für `rules_simulation`/`envelope_simulation` erwägen.
6. Später: Korrekturformular aus dem Schema statt JSON (RW15); OCR für Seiten ohne Textschicht (RW03); mehrbändige Reglements (RW23).

### 4.3 Auslieferung und Betrieb

1. Unraid in Betrieb nehmen (README 2–4), danach TLS, Authentik, `staff-add`, Login prüfen.
2. G1–H1 auf Unraid: ausgehender Zugang (`data.geopf.fr`, `cadastre.data.gouv.fr`, `georisques.gouv.fr`, `apicarto.ign.fr`, `www.geoportail-urbanisme.gouv.fr`, `api.anthropic.com`), `.env` mit `ANTHROPIC_API_KEY`, Flags für `architect`; Migration 0007 läuft beim Ausliefern mit; Caddy-Ersetzungen beim nächsten Caddy-Release prüfen (A27).
3. Überwachung (Uptime Kuma), Offsite-Sicherung, erste Wiederherstellungsübung.
4. SMTP nach E2 eintragen, Testmail; GitHub-Hauptzweig schützen.
5. Verarbeitungsverzeichnis (Plan 4.1 Kriterium 6): Staff-E-Mail, Mailadresse in Jobs (A12), IP-HMAC (A7), Steckbriefe im Objektspeicher (BR10); Claude API erhält nur Planunterlagen.
6. Optional: lokal und in CI SeaweedFS statt MinIO (A16, A22).

### 4.4 Nächstes Modul

- **Erst klären:** Modul A nachholen (Abschnitt 3) oder direkt mit **H2** (Zulässigkeit und Implantation) weitermachen? H2 braucht H1 (fertig, Backend) und G3 (fertig); D12 und D13 vorher entscheiden. Spezifikation 5.3.3–5.3.6 vor Code lesen. H2 nutzt `envelope/domain` mit den Höhen der Konfiguration und legt `/buildable?height_m=` an (Plan 7).
- **A (Plan 3.6):** Kontakt, Snapshot, Mail ans Büro, Prüfung der Simulation; offene Punkte darin: Frage „Lotissement?“ (RW16), Büro-Prüfliste auf Projekte mit Anfrage beschränken (G21), `retention_cleanup` erweitern (A11), `DELETE /projects/{id}` gegen Aufbewahrung abwägen (S10). Für Weg E noch nicht entworfen, wie eine Anfrage ohne Simulation aussieht.
- **Vor Erweiterung des Einzugsgebiets:** CNIG-Typliste der überlagernden Vorgaben gegen den Standard prüfen (BR05).

### 4.5 Korrekturen an der Spezifikation (offen)

Unverändert seit 13.09.2026: S1–S14 (siehe vorige Fassungen von HANDOFF.md bzw. AENDERUNGEN.md 14.09.). H1s Abweichungen (ANNAHMEN H01–H09) sind Plan-Ebene, keine neue Spezifikationskorrektur.

### 4.6 Weitere Punkte

1. Einwilligung zur Datenweitergabe fehlt im Mockup (Spez. Anh. E.2 M10).
2. Büro-Oberfläche aus G2 (Knöpfe „Erneut versuchen“, „Neu auswerten“, Status „veraltet“) im Browser ansehen; bisher nur Komponententests.

## 5. Empfohlener nächster Schritt

1. Entscheiden: Modul A nachholen oder direkt H1-Frontend/H2 (Abschnitt 3, 4.4).
2. H1 fertigstellen (4.1): Katalogpflege-Oberfläche, fünf echte Typen, lokal im Browser prüfen.
3. Priorität 1 aus Abschnitt 3 (Claude-API-Schlüssel, Authentik-Hostname, E2-Anbieter) → 4.2/4.3.

## 6. Hinweise und Stolperstellen

- **Modul A übersprungen:** siehe Abschnitt 1 und 4.4 – nicht automatisch annehmen, dass A schon existiert.
- **H1-Trigger `forbid_published_modification`** ist **bedingt** (blockt nur `UPDATE`/`DELETE` bei `status = 'published'`), anders als das unbedingte `forbid_modification` (`rule_no_update`, `audit_log`/`legal_text`). Bei weiteren unveränderlichen Tabellen das richtige Muster wählen.
- **H1-Preiskatalog ist ein Singleton-Entwurf** je Region (`default`), wird beim ersten Typ-Import oder Linie/Option automatisch angelegt und mit `POST /admin/catalog/price-catalog/publish` als Ganzes veröffentlicht.
- **Befehle:** Backend-Prüfungen `docker compose --profile dev run --rm -e TEST_S3=1 backend-dev sh -c "ruff check . && ruff format --check . && mypy app && pytest"` (MinIO und Mailpit müssen laufen). Nach neuen Abhängigkeiten zuerst `uv lock` im Container, dann `docker compose --profile dev build backend-dev` (diese Session: openpyxl, ezdxf, python-multipart neu). Frontend `corepack pnpm …` im Ordner `frontend` **ohne** `MSYS_NO_PATHCONV=1` (das zerbricht den Pfad zu `corepack.js` in Git Bash); die Variable nur bei `docker …`-Befehlen mit Linux-Pfaden setzen.
- **Heredocs im Bash-Werkzeug** zerbrechen an einer ungeraden Zahl von Apostrophen, an Backticks und `$$`. Längere Dateien mit dem Write-Werkzeug schreiben.
- **E2E vor dem Push lokal laufen lassen:** Flags per `flag-set … --all`, dann `corepack pnpm exec playwright test -g Kunde`. H1 hat noch kein E2E-Szenario (reiner Büro-Pfad, kein Kundenschritt) und braucht keins, solange keine Kunden-Oberfläche existiert.
- **G3:** `envelope-check` ist die schnellste Gegenprobe nach Änderungen an G1, G2 oder den Schranken.
- **Weg E:** Details siehe vorige Fassungen; Geometrie ohne geografischen Bezug, nie ohne Prüfung von `site.origin` behandeln.
- **WeasyPrint** braucht Pango und DejaVu im Image; die HarfBuzz-Subset-Warnung ist unkritisch.
- **Unsichtbare Zeichen:** `backend/app/rules/domain/text.py` – beim Neuschreiben mit `git diff` prüfen.
- **Jobarten registrieren:** Wer `enqueue` aufruft, muss `app.registry` importieren. H1 hat keine Hintergrundjobs (Import ist synchron) und braucht keinen Eintrag.
- **FastAPI:** neue **öffentliche** Route in `test_access_policies.py` eintragen; H1s Routen sind alle `/admin/...` mit Rollenprüfung, keine Eintragung nötig (Test prüft ohnehin „genau eine Zugriffsregel je Route“). `openapi.json` neu erzeugen (`python -m app.cli openapi openapi.json`), dann `pnpm api:types`.
- **Docker Desktop** beendet sich gelegentlich; Start `C:\Users\sarah\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe`, dann `docker info` abwarten.
- **Ports lokal:** Web 8080, API 8000, OIDC-Testdienst 8081, MinIO 9000, Mailpit 8025. **Lokaler Login:** `ops@emprise.local`; beim Wechsel Testdienst ↔ Authentik `oidc_subject` auf NULL setzen. Datenbank: `docker exec emprise-db-1 psql -U postgres -d emprise`.
- **Rate-Limits beim Testen:** viele Projekte/Grundstücke von derselben IP → 429; Limits in `.env` hochsetzen.
- **Kosten der Claude API:** Aufrufe mit Schlüssel kosten; Änderungen an Prompt/Ausgabeschema vor dem Eintragen des Schlüssels bündeln.
- **CI:** Security-Job baut Caddy mit `xcaddy`; Netzfehler zu `sum.golang.org` sind kein Codefehler, mit `gh run rerun <id> --failed` wiederholen. `596e075` (H1) lief grün ohne Auffälligkeiten trotz drei neuer Python-Abhängigkeiten.

## 7. Startprompt für die neue Session

```
Lies HANDOFF.md und den Eintrag vom 18.09.2026 in AENDERUNGEN.md. Fasse den Stand in fünf Sätzen zusammen, nenne die Entscheidungen mit Priorität 1 und frag mich ausdrücklich, ob Modul A nachgeholt werden soll, bevor wir mit H2 oder dem H1-Frontend weitermachen.
```
