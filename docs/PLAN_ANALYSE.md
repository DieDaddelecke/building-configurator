# Emprise Analyse – eigenständige Web-App aus G1–G3

> **Status:** geplant am 20.09.2026 · **AN0 und AN1 umgesetzt am 20./21.09.2026** (Festlegungen `docs/ANNAHMEN.md` PS01–PS09 und UP01–UP16, Plan [PLAN_AN1_PARZELLE.md](PLAN_AN1_PARZELLE.md), Betrieb [BETRIEB.md](BETRIEB.md) 15); AN2–AN6 offen · **Arbeitstitel:** „Emprise Analyse“
> **Bezug:** `UMSETZUNGSPLAN.md` 2.1, 3.2–3.5 (Zuschnitt von P, G1, G2, G3), `docs/PLAN_G3_BAURAHMEN.md` (Ableitung), `docs/ANNAHMEN.md` G01–G30, RW01–RW27, BR01–BR15 (Stand von G1–G3), `BACKEND_SPEZIFIKATION.md` 5.1–5.3, 5.9 (Fachregeln)
> **Verhältnis zum Umsetzungsplan:** Dieses Dokument beschreibt ein **zweites Produkt** neben dem Hauskonfigurator, nicht ein weiteres Modul von R1/R2. Es ändert nichts an G1–G3, A, H1–H3 oder V; wo es den Kern berührt, steht das in Kapitel 4 (AN0, AN1, AN2).

---

## 1. Kontext

G1–G3 beantworten heute für einen **Bauinteressenten** die Frage „was darf ich hier bauen?“ und münden in Konfigurator und Anfrage. Dieselbe Kette – Parzelle, PLU-Auswertung, Baurahmen – ist für den **Architekten** der Beginn jedes Entwurfs, nur mit anderen Anforderungen: Maßzahlen für den Entwurf (Höhe, Abstand je Grenze, bebaubare Fläche, Nutzfläche), Nachvollziehbarkeit bis zum Zitat, Korrekturmöglichkeit und Ausgabe ins CAD.

Ergebnis: ein zweites, eigenständiges Produkt aus demselben Repository mit demselben Kern. Der Hauskonfigurator bleibt unverändert lauffähig.

**Entscheidungen des Nutzers vom 20.09.2026:**

| Frage | Entscheidung | Folge |
|---|---|---|
| Zielgruppe | Zuerst nur das eigene Büro; später Abo für fremde Büros mit eigenem Branding und API | AN6 als eigene Ausbaustufe; in AN1 wird nur die nullable Spalte `organisation_id` offengehalten, sonst nichts vorgebaut |
| Codebasis | Ein Repo, zwei Produkte aus gemeinsamem Kern | AN0 |
| Gebiet und Datenbeschaffung | **Kein Vorausdenken von Gebieten.** Der Nutzer lädt Parzelle und PLU selbst hoch: „das Produkt ist die Analyse, die Kunden liefern das Material“ | Kehrt die Beschaffungsseite um: Upload ist der Pflichtweg (AN1, AN2); Kataster und GPU bleiben als Komfortweg vorhanden, aber ohne Vorabimport |

---

## 2. Befund: was vorhanden ist, was fehlt

**Der Schnitt ist sauber.** `site/`, `rules/` und `envelope/` importieren ausschließlich aus `platform/`, `integrations/` und untereinander. Kein Fremdschlüssel aus `catalog`, `configuration`, `inquiry` oder `submission` zeigt auf eine G-Tabelle; die Richtung ist umgekehrt (`configuration/domain` rechnet mit `envelope/domain`). Die Migrationen 0002–0006 sind ein zusammenhängender Block.

| Anforderung des Architekten | Stand heute | Lücke |
|---|---|---|
| Höchste Höhe (First, Traufe, Attika, Geschosse) mit Bezug | in `envelope` je Zone mit Zitat | kein Höhenschnitt, keine Angabe in m NGF (BR09), keine angezeigte Umrechnung Geschosse → Meter (BR06 wirkt nur intern) |
| Abstand je Grundstücksgrenze, auch „nicht notwendig“ | `edges[].setbacks` mit `lenient`/`strict`, `allow_on_boundary`, `height_factor`, Zitat | Aussage ist auf den Kunden zugeschnitten; keine höhenabhängige Kurve `d(h)`, keine Fachdarstellung |
| Höchste bebaubare Fläche | zwei Konturen und `footprint_max_m2` je Teilfläche | der **bindende** Wert (Minimum aus beidem) wird nicht gebildet und nicht benannt |
| Höchste Nutzfläche (surface de plancher) | **fehlt vollständig** | neu, AN3 |
| Grafische Ableitung auf der Parzelle | SVG-Lageplan `frontend/src/envelope/BaurahmenPlan.tsx` in lokalen Metern, 1 Einheit = 1 m, Norden oben | kein Schnitt, kein gestufter Hüllkörper, keine Kartendarstellung |
| Eigene Parzelle einbringen | Weg E (freies Zeichnen mit Bemaßung) | kein Datei-Upload; Weg E legt **keine `site_edge` an** (G26–G30) → ohne Kanten kein Abstand und kein Baurahmen |
| Eigenes PLU einbringen | `rules/plan_import.py` holt das règlement nur vom GPU | kein Upload; `rules/service.py::resolve_rules` startet zwingend bei Gemeinde-INSEE → `rules_commune` → `land_use_plan` → Zonen per Geometrie |
| Regeln korrigieren | `project_rule_override` und Büro-Formular vorhanden | Parameter nur als roher JSON-Text (RW15 offen) – für ein Architektenwerkzeug untragbar |
| Ausgabe ins CAD | DXF-Schreiber mit Ebenen `ZONE_CONSTRUCTIBLE_LARGE`/`_STRICTE` vorhanden | liegt in `submission/dossier/` (Modul V), das im Analyse-Produkt nicht mitläuft |
| Projekte verwalten | anonymes Projekt-Cookie; `require_project_access` erlaubt **nur** den Cookie | der Architekt braucht benannte Projekte am eigenen Konto; `retention_cleanup` würde sie nach 90 Tagen löschen (A11) |

Nicht gebraucht und darum nicht enthalten: `catalog` (H1), `configuration` (H2/H3), `inquiry` (A), `submission` (V).

---

## 3. Architektur: ein Repo, zwei Produkte

```
Kern (beide Produkte)   platform/  integrations/  site/  rules/  envelope/  plan/ (neu)
Produkt „konfigurator“  + catalog/  configuration/  inquiry/  submission/
Produkt „analyse“       + intake/ (Upload Parzelle und PLU)  + analysis/ (Nutzfläche, Gabarit, Schnitt)
```

- **Backend-Profil:** neue Einstellung `EMPRISE_PRODUCT ∈ {configurator, analyse}` in `backend/app/config.py`, Standard `configurator` (bestehendes Verhalten unverändert). Neue Datei `backend/app/products.py` hält je Produkt die Liste der Router und der Job-Module; `main.py` und `registry.py` lesen daraus statt aus festen Importlisten. Nötig, weil im Analyse-Produkt sonst die periodischen Jobs `cadastre_import` und `plu_import` mitliefen.
- **`backend/openapi.json` bleibt eine Datei** und entsteht weiter aus dem **vollen** Profil. Sonst bricht der CI-Schritt `pnpm run api:types && git diff --exit-code`, und `frontend/src/api/schema.d.ts` wäre doppelt zu pflegen. Das Profil wirkt nur zur Laufzeit.
- **Grenze absichern:** neuer Test `backend/tests/unit/test_module_boundaries.py` prüft über den AST, dass `platform`, `integrations`, `site`, `rules`, `envelope` und `plan` nie `app.catalog`, `app.configuration`, `app.inquiry` oder `app.submission` importieren. Heute erfüllt; der Test hält es dauerhaft.
- **Frontend:** ein Paket, zwei Vite-Einstiege (`index.html`, `analyse.html` über `build.rollupOptions.input`). Gemeinsam bleiben `src/api`, `src/components/plan`, `src/components/karte`, `src/site`, `src/rules`, `src/envelope`, `src/i18n`; neu `src/products/analyse/` mit eigenem Router, eigenen Farbtokens und eigenem Rahmen. Ein Abhängigkeitsstand, ein Testlauf, eine Typerzeugung.
- **Migrationen:** ein linearer Strang bleibt. Die Analyse-Datenbank trägt die Tabellen aus 0007–0011 ungenutzt mit; das kostet nichts und vermeidet zwei auseinanderlaufende Stränge.
- **Auslieferung:** zweiter Stack `deploy/unraid/compose.analyse.yaml` mit eigener Datenbank, eigenem Objektspeicher-Präfix, eigenem Hostnamen und eigener Authentik-Anwendung; `deploy/unraid/deploy.sh` erhält einen Stack-Parameter. Getrennte Datenbanken, weil Berufsdaten des Büros und Kundendaten des Konfigurators nichts miteinander zu tun haben.
- **Regelwerke teilen** (später, nach Auslöser): ausgewertete `rule_set_version` per `rules-export`/`rules-import` zwischen den Produkten austauschen, damit eine bezahlte Auswertung nur einmal anfällt. Erst umsetzen, wenn die Kosten es rechtfertigen.

---

## 4. Module

Jedes Modul ist ein senkrechter Schnitt (Tabellen, Fachlogik, API, Oberfläche, Tests, Betriebsanleitung) und für sich lauffähig – wie in Plan 3.

### AN0 – Produktschnitt (4–6 T) · **umgesetzt am 20.09.2026**

`EMPRISE_PRODUCT`, `products.py`, Grenz-Test, zweiter Vite-Einstieg, zweiter Compose-Stack, Abschnitt in `docs/BETRIEB.md`.

**Verschiebung ohne Verhaltensänderung:** `backend/app/submission/dossier/plan.py` und `dxf.py` nach `backend/app/plan/`, weil beide Produkte sie brauchen. `submission` importiert danach von dort; Tests unverändert grün.

*Abnahme:* Beide Produkte laufen lokal nebeneinander; die Analyse-Anwendung liefert unter `/api/v1` keine Katalog-, Anfrage- oder Übergabe-Route; alle bestehenden Tests grün.

*Ergebnis:* erfüllt. Analyse-Profil 41 Routen gegen 79 im Konfigurator, keine davon aus Katalog, Konfiguration, Anfrage oder Übergabe; vier statt sechs periodische Aufgaben; `http://localhost:8180` zeigt „Emprise Analyse“, `:8080` unverändert den Konfigurator. Backend 479 Tests (vorher 474), Frontend 145 (vorher 143), ruff, Format, mypy, Typprüfung, Lint und Build grün; `openapi.json` unverändert. Zwei Abweichungen vom Plan sind in `docs/ANNAHMEN.md` festgehalten: periodische Aufgaben statt ganzer Job-Module je Produkt (PS03, siehe 8.1 Nr. 9) und `app/plan/geometry.py` statt `app/plan/plan.py` mit `from_snapshot` weiterhin in Modul V (PS04).

### AN1 – Parzelle ohne Kataster (6–8 T) · **umgesetzt am 20.09.2026** ([Plan](PLAN_AN1_PARZELLE.md))

- `site.origin` um `upload` erweitern (Migration). **Für `manual_sketch` und `upload` werden `site_edge`-Zeilen angelegt** – ohne sie rechnet `derive_envelope` keinen einzigen Abstand. Einordnung der Kantenart von Hand über den vorhandenen Architekten-Endpunkt `PATCH /projects/{id}/site/edges/{seq}`.
- Datei-Upload der Parzelle: **DXF** (`ezdxf` ist bereits Abhängigkeit; geschlossene Polylinie auf wählbarer Ebene), **GeoJSON** (Lambert-93 oder WGS84) und – nachgetragen am 21.09.2026 – **vektorielles PDF** (Katasterauszug, Plan des Geometers; PLAN_AN1 8). Mehrere Konturen → Auswahl. Prüfungen wie bei Weg E: keine Selbstüberschneidung, plausible Fläche und Kantenlänge.
- Freies Zeichnen mit Bemaßung (`frontend/src/site/FreiesZeichnen.tsx`, `backend/app/site/domain/manual.py`) bleibt der zweite Weg.
- **Projekte gehören dem Architekten:** Spalten `project.owner_staff_user_id` und `project.organisation_id` (nullable, eine Standard-Organisation). `require_project_access` in `backend/app/platform/auth/context.py` so erweitern, dass ein Staff-Principal mit Rolle `architect` auf Projekte seiner Organisation zugreift – sonst sind sämtliche G1–G3-Kundenendpunkte für ihn gesperrt. `retention_cleanup` in `backend/app/platform/tasks.py` überspringt Projekte mit Eigentümer.
- Kataster-Klick und Adresssuche bleiben nutzbar, wo eine Gemeinde importiert ist; kein Vorabimport.

*Ergebnis:* umgesetzt wie beschrieben, Einzelheiten und Abweichungen in [PLAN_AN1_PARZELLE.md](PLAN_AN1_PARZELLE.md) und ANNAHMEN UP01–UP10. Zwei Abweichungen: Die **Auskunft** (`GET …/export`) bleibt in Modul A, nur die **Löschung** wandert in den Kern (UP07); ein **Upload mit erkanntem Koordinatensystem** behält seine echte Lage (`site.georeferenced`), Gelände und Risiken bleiben trotzdem bis AN5 aus (UP04).

### AN2 – PLU selbst hochladen (8–10 T)

- règlement écrit als PDF hochladen → Objektspeicher, SHA-256, `source_file` mit `origin = upload`.
- `rules/plan_import.py` auftrennen: der Teil ab „PDF liegt vor“ (Seitentexte über `rules/pdf.py`, Kapitelerkennung über `rules/domain/chapters.py`) wird für Uploads wiederverwendet; der GPU-Teil davor bleibt dem Konfigurator.
- **Zonenzuordnung von Hand:** Der Architekt wählt Kapitel oder Zonencode aus der erkannten Liste oder gibt einen Seitenbereich an. Das ersetzt die Zonengeometrie aus dem GPU.
- **Eingriff in `rules/service.py`:** `resolve_rules` startet heute zwingend bei Gemeinde-INSEE → `rules_commune` → `land_use_plan` → Zonen per `ST_Intersection`. Für hochgeladene Dokumente braucht es einen zweiten Einstieg: Projekt → gewähltes Dokument und Kapitel → Regeln, Teilfläche = ganzes Grundstück. Die gemeinsame Ausgabe (`RulesResult`) bleibt gleich, damit `envelope_rules` und alle Anzeigen unverändert funktionieren (BR15). **Das ist der größte verdeckte Aufwand des Vorhabens.**
- Auswertung über den vorhandenen Job `rules_extract` – unverändert inklusive Schranken, Zitatprüfung, zweitem Lauf und Kostenzählung. Ausgewertet wird nur das gewählte Zonenkapitel und die allgemeinen Bestimmungen, nicht das ganze Dokument.
- **Zusatzdokumente:** règlement de lotissement und cahier des charges als zweites Dokument derselben Art, dessen Regeln die PLU-Regeln überlagern. Heute nur ein Hinweistext, für Architekten aber ein echter Bedarf.
- Kein extrahierbarer Text (Scan) → klare Meldung; OCR bleibt Ausbaustufe (RW03).

### AN3 – Analyse für den Entwurf (10–12 T)

| Ergebnis | Herleitung |
|---|---|
| **Bindende höchste Grundfläche** | `min(Fläche der Kontur, ratio × Fläche der Teilfläche)` je Auslegung, mit Angabe, welcher der beiden Werte bindet |
| **Vollgeschosse** | aus `max_height.storeys` (`R+1+C`), sonst aus First- oder Traufhöhe geteilt durch die Geschosshöhe; Annahme sichtbar |
| **Höchste Nutzfläche (SDP)** | als **Spanne**, nicht als Einzelwert: Grundfläche × Geschosse × Faktoren. Alle Parameter (Geschosshöhe, Außenwandabzug, anrechenbarer Anteil des Dachgeschosses) sind offengelegt und änderbar; Vorgabewerte in `docs/ANNAHMEN.md`. Die Abzüge nach R.111-22, die das Werkzeug **nicht** rechnet (Treppenräume, Stellplätze, Lichthöhe unter 1,80 m), werden ausdrücklich benannt – ehrlich statt scheingenau |
| **Gabarit (Höhenstufen)** | Konturen bei `h = 0, 3, 6, … H_max`. `_boundary` in `envelope/domain/setbacks.py` rechnet bereits `max(min_m, factor × h)`; es genügt, dieselbe Ableitung je Höhenstufe mit fixiertem `Heights` aufzurufen. Ergebnis: gestufter Hüllkörper – 2D als Höhenlinien im Lageplan, 3D als DXF |
| **Schnitt** | Schnittlinie quer über das Grundstück: Gelände, höchste Traufe und First, Abstandsdreiecke – SVG mit den Bausteinen aus `frontend/src/components/plan/` |
| **Abstandsaussage je Grenze** | im Klartext: „auf der Grenze zulässig“ / „mindestens 3 m“ / „H/2, mindestens 3 m – bei 7 m Höhe also 3,50 m“, jeweils mit Zitat und Seite |

Die Ableitung bleibt in `envelope/domain` rein und deterministisch; das Neue kommt als `analysis/domain` dazu und nutzt `derive_envelope` als Baustein.

### AN4 – Korrigieren und begründen (6–8 T)

- **Regelformular statt JSON** (RW15): Formular aus den Pydantic-Regelarten in `rules/domain/kinds.py` erzeugt – eine Quelle für Schema, API, Modellausgabe und Formular.
- Wert je Projekt übersteuern mit Pflichtbegründung, Herkunft `architect`; der Baurahmen zeigt die Herkunft an jedem Wert (vorhanden, L3).
- Regeln ergänzen, die das Modell nicht gefunden hat.
- Zwei Stände nebeneinander vergleichen (vor und nach Korrektur, zwei Auswertungsläufe).

### AN5 – Ausgabe und Projektakte (8–10 T)

- **Bericht-PDF** für die Projektakte: alle Werte mit Zitat und Seite, Lageplan, Schnitt, Gabarit, Annahmen und Grenzen, Dokumentstände und Datum. Erweitert `envelope/sheet.py` (WeasyPrint, vorhanden).
- **DXF:** Umriss, Kanten nach Art, beide Konturen, Bauband, Bauverbotsflächen, Höhenstufen als 3D – lokal und, bei Georeferenz, in Lambert-93. Erweitert `app/plan/dxf.py` aus AN0.
- **GeoJSON-Export.**
- **Projektliste** mit Benennung, Notiz und Archiv am Architektenkonto.
- **Georeferenzierung** eines gezeichneten oder hochgeladenen Grundstücks (Punkt aus der Adresssuche und Drehwinkel). Erst damit sind Gelände, Risiken und die Lambert-93-DXF möglich.

### AN6 – Abo, Mandanten, Branding, API (später, eigener Auslöser)

Tabelle `organisation`; Projekte, Dokumente und Rechte je Organisation; Branding (Logo, Farben, Schriftfeld in PDF und DXF); API mit Token je Organisation; Kontingente und Weiterberechnung der Claude-Kosten (Zählung je Lauf existiert); AGB, Haftungsausschluss, Auftragsverarbeitung. **Jetzt schon offengehalten, ohne Mehrkosten:** die nullable Spalte `organisation_id` aus AN1, Ausgaben ausschließlich über `app/plan/` und die API, Farben nur als Tokens.

---

## 5. Reihenfolge

| Release | Module | Nutzen | Größe |
|---|---|---|---|
| **RA1** | AN0, AN1, AN2, AN3 (bindende Grundfläche, Geschosse, Nutzfläche) | Grundstück zeichnen oder hochladen, PLU hochladen, Baurahmen mit Höhen, Abständen, Flächen und Nutzfläche – im eigenen Büro produktiv nutzbar | 28–36 T (6–7 PW) |
| **RA2** | AN3 vollständig (Gabarit, Schnitt), AN4, AN5 | Entwurfsbegleitung: Hüllkörper, Schnitt, eigene Korrekturen, Bericht und CAD-Ausgabe | 24–30 T (5–6 PW) |
| **RA3** | AN6 | Abo für fremde Büros | nach Auslöser |

Größen in Personentagen für eine Person mit Claude Code, ohne Inhaltsarbeit, Rechtstexte und Gestaltung.

---

## 6. Offene Entscheidungen (mit Empfehlung)

| Nr. | Frage | Empfehlung |
|---|---|---|
| E-A1 | Produktname und Marke | Arbeitstitel „Emprise Analyse“ verwenden, endgültigen Namen vor der ersten Nutzung außerhalb des Büros festlegen |
| E-A2 | Dateiformate der Parzelle in RA1 | DXF, GeoJSON und freies Zeichnen. **Kein DWG** (proprietär, bräuchte einen zusätzlichen Konverter). **Entschieden 21.09.2026 (Nutzer): auch PDF** – vektorielle Pläne mit Maßstab aus dem Text oder von Hand, umgesetzt in AN1 (PLAN_AN1 8, UP13–UP16); Scans bleiben offen |
| E-A3 | Mehrzonen-Grundstück beim Upload | In RA1 eine Zone je Grundstück. Zonengrenze einzeichnen erst in AN5 – ohne GPU-Geometrie gibt es keine automatische Verschneidung |
| E-A4 | Datenhaltung | Eigene Datenbank je Produkt. Ausgewertete Regelwerke erst dann teilen, wenn die Auswertungskosten es rechtfertigen |
| E-A5 | Rechtlicher Rahmen | Solange nur das eigene Büro nutzt, genügt ein Hinweis „Analyse auf Grundlage der eingereichten Unterlagen, keine Rechtsauskunft; maßgeblich ist das Certificat d'urbanisme“. **Vor AN6 juristische Prüfung** (Haftung gegenüber fremden Büros, AGB, Auftragsverarbeitung, Urheberrecht an hochgeladenen Plänen) |
| E-A6 | Claude-Budget | Deckel je Organisation und Monat, bevor Dritte hochladen dürfen; die Mechanik (Kostenzählung je Lauf, Monatsbudget) ist vorhanden |

---

## 7. Prüfung und Abnahme

1. **Bestandsschutz:** voller Prüflauf nach AN0 (Backend 474 Tests, Frontend 143, ruff, Format, mypy, Typprüfung, Lint, Build) – der Hauskonfigurator verhält sich unverändert.
2. **Grenz-Test:** `test_module_boundaries.py` schlägt fehl, sobald der Kern ein Produktmodul importiert.
3. **Zwei Stacks lokal:** `docker compose -p emprise up -d` und `docker compose -p emprise-analyse up -d` parallel; `GET /api/v1/openapi.json` des Analyse-Profils enthält keine `catalog`-, `inquiry`- oder `submission`-Route.
4. **Ende zu Ende im Browser:** anmelden → Grundstück zeichnen **und** als DXF hochladen → Kantenarten setzen → règlement als PDF hochladen → Zone wählen → Auswertung abwarten → Baurahmen mit Höhen, Abständen je Grenze, bindender Grundfläche und Nutzflächenspanne → Wert korrigieren → Bericht-PDF und DXF herunterladen. Deutsch und Französisch, auch in Telefonbreite.
5. **Fachliche Gegenprobe:** dieselbe Parzelle einmal über den Kataster- und GPU-Weg (Treillières, Zone Uh, aufgezeichnete Antwort) und einmal über den Upload-Weg; beide Baurahmen müssen bis auf Rundung übereinstimmen. Aussagekräftigster Test des neuen Einstiegs in `resolve_rules`.
6. **Nutzfläche gegen Handrechnung:** drei reale Grundstücke des Büros, Spanne gegen die von Hand ermittelte SDP; Abweichungen führen zu benannten Annahmen, nicht zu stillen Korrekturen.
7. **Leistung:** Ableitung weiter p95 unter 300 ms (heute Median 75 ms, BR07); Auswertung eines hochgeladenen Kapitels mit Dauer und Kosten gemessen und in `docs/BETRIEB.md` eingetragen.
8. **Robustheitslauf** `envelope-check` bleibt gültig und wird um den Upload-Weg erweitert.

---

## 8. Prüfprotokoll

### 8.1 Gefundene Fehler und Lücken

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 1 | „G3 bleibt unverändert nutzbar“ war falsch: `resolve_rules` startet zwingend bei Gemeinde-INSEE und Zonengeometrie aus dem GPU | Ohne zweiten Einstieg liefert der Upload-Weg gar keine Regeln | AN2, als größter verdeckter Aufwand benannt |
| 2 | Weg E legt keine `site_edge` an (G26–G30) | Ohne Kanten rechnet `derive_envelope` keinen Abstand – der Baurahmen wäre leer | AN1 |
| 3 | `require_project_access` erlaubt ausschließlich den Projekt-Cookie | Der angemeldete Architekt käme an keinen einzigen G1–G3-Endpunkt | AN1 |
| 4 | `retention_cleanup` löscht Projekte nach 90 Tagen ohne Aktivität (A11) | Architektenprojekte wären nach drei Monaten weg | AN1 |
| 5 | Zwei Produktprofile ergäben zwei verschiedene OpenAPI-Dateien | CI-Schritt `api:types && git diff --exit-code` bricht, `schema.d.ts` doppelt zu pflegen | AN0: `openapi.json` weiter aus dem vollen Profil |
| 6 | Der DXF-Schreiber liegt in `submission/` (Modul V), das im Analyse-Produkt fehlt | Keine CAD-Ausgabe möglich | AN0: Verschiebung nach `app/plan/` |
| 7 | `registry.py` importiert alle Job-Module fest | Im Analyse-Produkt liefen `cadastre_import` und `plu_import` periodisch ins Leere | AN0: Job-Module je Produkt |
| 8 | „Höchste Nutzfläche“ als eine Zahl | Wäre scheingenau und im Streitfall eine Zusage | AN3: Spanne, offengelegte Parameter, benannte nicht gerechnete Abzüge |

Beim Bau von AN0 dazugekommen:

| Nr. | Befund | Folge | Behoben in |
|---|---|---|---|
| 9 | Nr. 7 („Job-Module je Produkt“) ist zu grob: `site/jobs.py` enthält `cadastre_import` **und** `site_enrich`, `rules/jobs.py` enthält `plu_import` **und** `rules_extract`. Ohne das Modul fehlten dem Analyse-Produkt Jobs, die es braucht | Der Schnitt läuft nicht zwischen Dateien, sondern zwischen periodischen Aufgaben | AN0: `products.py` führt die periodischen Aufgaben je Produkt, die Jobarten bleiben registriert (PS03) |
| 10 | `DELETE /projects/{id}` (Löschung) und `GET /projects/{id}/export` (Auskunft) liegen in Modul A; das Analyse-Produkt hat sie damit nicht | Ein Produkt mit Projekten ohne Löschung wäre nicht brauchbar | AN1: die Löschung liegt im Kern, Modul A hängt seine Sperre ein; die **Auskunft bleibt in A**, weil ihr Inhalt allein aus A stammt – vor AN6 neu zu bewerten (UP07) |
| 11 | Zwei Einstiege in einem Web-Image: `try_files … /index.html` hätte im Analyse-Stack die Seite des Konfigurators geliefert, auch mit gesetztem `SPA_INDEX` (Caddy liefert für `/` den Verzeichnisindex) | Falsche Oberfläche im zweiten Produkt | AN0: `file_server { index {$SPA_INDEX} }` zusätzlich zu `try_files` (PS06) |
| 12 | Ein Rückrollen hätte beide Stacks getroffen, weil `deploy.sh` die Images auf `:current` umhängt | Der Konfigurator wäre beim nächsten `up` still mit zurückgerollt | AN0: eigenes Kennzeichen `current-analyse` je Stack (PS08) |

### 8.2 Geprüfte Alternativen

| Alternative | Verworfen, weil | Besser, wenn … |
|---|---|---|
| Eigenes Repository (Fork) | Die wertvollste und komplexeste Logik (Regelauswertung, Baurahmen) wäre doppelt zu pflegen; die Analyse-Erweiterungen nützen auch H2 | die beiden Produkte fachlich auseinanderlaufen – dann später trennen, die Grenze aus AN0 macht das möglich |
| Nur ein neuer Bereich unter `/buero` | Keine eigenständige App, keine eigene Marke, keine getrennte Auslieferung; das Abo-Ziel wäre verbaut | das Werkzeug dauerhaft nur intern bliebe |
| Kataster- und GPU-Weg als Pflicht behalten | Widerspricht der Entscheidung: Gebiete vorauszudenken kostet Import und Auswertung für Gemeinden, die nie genutzt werden | das Werkzeug auf ein festes Einzugsgebiet begrenzt bliebe |
| Zwei Migrationsstränge, getrennte Schemata | Zwei auseinanderlaufende Stränge sind dauerhaft teurer als ein paar ungenutzte Tabellen | die Analyse-Datenbank später eigenständig werden soll |
| Mandantenfähigkeit sofort vollständig bauen | Kosten ohne Nutzen, solange nur ein Büro arbeitet | ein zweites Büro konkret bevorsteht |
| Baurahmen auf der MapLibre-Karte statt im SVG | Braucht eine Rücktransformation lokal → WGS84, die es im Frontend nicht gibt; für hochgeladene Parzellen ohne Georeferenz ohnehin sinnlos | nach AN5 (Georeferenzierung) als Zusatzansicht |

### 8.3 Bewusste Grenzen

Kein DWG, kein OCR gescannter PLU, keine 3D-Modellierung des Entwurfs, keine IFC-Ausgabe, keine Prüfung gegen Vorschriften außerhalb der eingereichten Unterlagen (servitudes d'utilité publique nur, soweit hochgeladen), keine Rechtsauskunft. Der Baurahmen bleibt, was er heute ist: eine nachvollziehbare Ableitung mit Zitat an jedem Wert – mit dem Unterschied, dass im Analyse-Produkt ein Fachmann die Eingangsdaten liefert und jeden Wert korrigieren kann.
