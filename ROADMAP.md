# Roadmap

> **Stand:** 04.10.2026; letzte Session: Hausmodell HM0, HM1 und HM3 umgesetzt (Rechenkern `packages/domain`, Rechendienst `engine`, IFC-Import im Büro), nach Thema committet und gepusht. Diese Datei trägt Stand, offene Entscheidungen, offene Arbeitspunkte und den nächsten Schritt; `/handoff` schreibt sie fort. Dauerhaftes steht in [DECISIONS.md](DECISIONS.md), [README.md](README.md) und [deploy/unraid/README.md](deploy/unraid/README.md).

## 1. Stand

- **Git:** `main` gepusht bis `e2a73aa`, seit `30b2196` acht Commits. Zwei stammen aus der Session vom 03.10.2026 und lagen uncommittet: Unraid-Hinweise (`e9ae8ba`) und ROADMAP (`72f6325`). Danach das Hausmodell nach Thema: Build (`02795f4`), Rechenkern und `engine` (`8abc2a0`), Backend (`18b9e6a`), Frontend (`cc3dc0e`), Doku (`b67417c`), zuletzt ein Fix für die CI (`e2a73aa`). Dieses Hand-off ist noch nicht committet.
- **CI:** Lauf 37183088070 auf `e2a73aa`: `domain`, `backend`, `frontend` und `e2e` grün. Im Lauf davor war `backend` rot: Der IFC-Leser scheiterte unter der Speichergrenze schon beim Laden einer Bibliothek, und das galt nicht als Speichergrenze (behoben mit `e2a73aa`, README, Stolperstellen).
  - **`security` bleibt rot** wie schon vor dieser Session (Lauf 37137761473 auf `30b2196`): Trivy meldet HIGH in `pypdf` 6.18.1 (CVE-2026-102998, -102999, -103000; behoben in 6.19.0) und `urllib3` 2.7.0 (CVE-2026-97687, -97689; behoben in 2.8.0), wegen des uv-Caches doppelt. Der Job bricht danach ab; `web` und `engine` sind ungescannt, `engine` noch nie.
- **Hausmodell** ([PLAN_HAUSMODELL](docs/PLAN_HAUSMODELL.md)): HM0, HM1 und HM3 umgesetzt (03./04.10.2026), HM3 auf Anweisung vor HM2. Haustypen kommen als IFC aus Archicad unter `/buero/katalog/hausmodell`: Import im Kindprozess, Entwurf, Prüfung in `engine`, Freigabe. Kunden sehen davon noch nichts (ab HM4). Festlegungen E-HM-1 bis E-HM-47 in DECISIONS 4.11, Ergebnisse in PLAN_HAUSMODELL 10, Anleitung für das Büro in [docs/IFC_IMPORTVERTRAG.md](docs/IFC_IMPORTVERTRAG.md).
- **Bereiche:**
  - Hauskonfigurator: R0, G1–G3, A, H1–H3 und V fachlich vollständig; seit dem 03.10. mit Startseite (Anmeldung, Bereiche) und Parzellenwahl über mehrere Gemeinden.
  - Emprise Analyse: AN0–AN7 unter `/analyse` (ADR-02); AN6 auf Organisationen und Mitglieder zurückgebaut (ADR-07); fremde Büros gesperrt bis E-A5.
  - Refactoring vom 29./30.09.2026 abgeschlossen (ADR-01 bis ADR-10); Kennzahlen in `git show 8ca3238:ROADMAP.md`, Abschnitt 1.
- **G2:** Modell Opus 5.5 (RW28, PU11), `g2-prompt-5` mit Nachsuche, etwa 1,46 $ je Kapitel. GPT-6 Sol mit Flex ist die günstige Alternative (PLAN_G2_VOLLSTAENDIGKEIT 7.7). „Offen“ in der Messung heißt `named_gap` (`rules/domain/reference.py`).
- **Lokal** (Stack `emprise`, Migration 0024, ohne OpenRouter-Schlüssel):
  - Kataster von Treillières, Paris (75101–75120) und 1 265 Gemeinden der Île-de-France: 1 286 Gemeinden, 3,7 Mio. Parzellen, Datenbank 3,2 GB.
  - Demo-Typen mit Preiskatalog, alle Flags für `architect`; Konfigurator auf AD 65 durchspielbar.
  - Regeln nur für die Zone Uh (5). Die Referenzliste „PLU Beyenes UC“ liegt in `emprise`, das Dokument dazu nicht (4.1).
  - Hausmodell: Demo-Katalog v1 veröffentlicht; `demo_house` v1 veröffentlicht und aktuell, `demohaus` v1 verworfen, `probe_1` v1 Entwurf aus Probedatei 1. `ops@emprise.local` hat wieder nur `architect` und `ops`.
- **Unraid** (`root@Tower`, 192.168.1.36), in Betrieb seit 03.10.2026:
  - Release `8ca3238` über `deploy.sh`. Den Code holt der Nutzer selbst per `git pull` in `/mnt/user/appdata/emprise-src` (Deploy-Key). Das nächste Release bringt das Image `engine` und Migration 0024 mit (deploy 9, 10, 24).
  - Authentik 2026.8.2 auf Port 9010; die Anmeldung im Büro funktioniert, mit Passkey als zweitem Faktor. Cloudflare „proxied“ (ADR-11), Nginx Proxy Manager mit Let's Encrypt.
  - Flags `site_selection`, `rules_simulation`, `envelope_simulation` für `architect`. Noch nicht da: Haustypen, Flag `configurator`, `legal-seed`, Mailversand.
  - Kataster Treillières hat der Worker importiert: 8 753 Parzellen, Stand 2026-06-01. Die Befehle für Paris und die Île-de-France sind übergeben; ein Ergebnis hat der Nutzer nicht gemeldet.
  - Der OpenRouter-Schlüssel soll leer bleiben; ob er es ist, hat der Nutzer nicht bestätigt.
- **Tests (lokal, 04.10.2026):** Backend 943 (1 übersprungen: Referenz-IFC des Büros fehlt), Frontend 272, Rechenkern 140, `engine` 13; ruff, mypy, Typprüfung, Lint und Build grün.
- **OpenRouter:** Anzeige zuletzt 4,38 $ von 10 $ (29.09.2026). In dieser Session keine bezahlten Läufe; nach einem Neustart hatten `api` und `worker` kurz den Schlüssel aus `.env`, es lief aber kein Job (README, Stolperstellen). Der Schlüssel stand am 28.09. im Chat und ist zu erneuern (4.3).

## 2. Nächster Schritt

1. **CI grün machen:** `pypdf` ≥ 6.19.0 und `urllib3` ≥ 2.8.0 in `uv.lock`, dazu den uv-Cache aus dem Image (5). Erst danach laufen die Scans von `web` und `engine`; sie können weitere Funde zeigen. Danach auf Unraid ausliefern, weil `pypdf` hochgeladene PDFs liest (4.5).
2. **Unraid fertig einrichten** (4.5): Platzhalterkonto sperren, Importe prüfen, Ersatz für den zweiten Faktor.
3. **Nach Wahl des Nutzers:**
   - Hausmodell weiter (4.8): HM2 (Oberfläche, braucht Referenzgeräte, 3) oder HM4 (Kundenweg); dazu die Eingaben des Büros für HM3.
   - Aufräumen (3, 4.7).
   - Beyenes UC (4.1).

## 3. Offene Entscheidungen des Nutzers

| Priorität | Nr. | Frage | Wo |
|---|---|---|---|
| 1 | E-HM-32, -35, -36, -37 | **Festlegungen des Hausmodells bestätigen:** Raumüberschreibung bei Gleichstand (32); Höhen über ±0,00 = Oberkante Bodenplatte EG, mit dem Büro klären (35); `engine` prüft nur die Hülle der Anfrage (36); Öffnungstyp über die Maße und eigene Standards je Bauteil (37) | DECISIONS 4.11 |
| 1 | – | **Referenzgeräte für HM2:** auf welchen Geräten die Zielwerte P 4.1 gemessen werden | PLAN_HAUSMODELL 6 (HM2) |
| 1 | – | **Haustypen auf Unraid:** echte Typen über H1 anlegen (XLSX, `/buero/katalog`) oder auf das Hausmodell warten? Kunden sehen Haustypen aus IFC erst ab HM4; H1-Typen lohnen sich nur für den Parallelbetrieb (3a). | 4.5, deploy 19 |
| 1 | – | **Regeln Treillières auf Unraid auswerten?** Dafür den Schlüssel in `.env` eintragen. Kosten: 1,5 $ bis 18 $, je nachdem, wie viele Kapitel erkannt werden (5). Nur mit Go je Lauf. | 4.3 |
| 1 | – | **Alte Datenbanken und Volumes löschen?** `emprise_analyse`, `emprise_shared`, `emprise_probe`, `emprise_storage-data`, `emprise_minio-data`. Empfehlung: ja; vorher `pg_dump` und das Beyenes-PDF sichern (4.1). | 4.7 |
| 1 | – | **Referenzliste Beyenes UC prüfen**, dann auf „geprüft“ setzen; kleine Nebengebäude gehören zu E-VA-5. | `/analyse/verwaltung`, PLAN_G2 6, 7.5, 7.7 |
| 1 | – | **Beyenes UC neu auswerten** (etwa 1,46 $)? Empfehlung: nach der Prüfung der Liste. | 4.1 |
| 1 | E2 | Mailanbieter (Empfehlung Scaleway TEM, sonst Brevo) | DECISIONS 3 |
| 1 | – | Sammeladresse (`EMPRISE_OFFICE_EMAIL`) und Name des Büros für die Einwilligungstexte | AF02, AF05, VU08 |
| 2 | – | AN7 Abnahme Nr. 4: bezahlte Auswertung des Scan-Kapitels UC (etwa 1,5 $) freigeben? | PLAN_AN7 6 |
| 2 | – | Befund „Zitat verschluckt eine Vorschrift“: Zitat begrenzen oder Abdeckung? Empfehlung: Abdeckung | PLAN_G2 7.7 |
| 2 (vor Beta) | – | Rechtliche Prüfung: Simulation, vier vorläufige Rechtstexte, ODbL-Quellenangabe; Cloudflare im Datenweg (ADR-11) | Plan 6.9, RW16, AF05, VU08, VU11 |
| 2 | E-A5 | Rechtlicher Rahmen der Analyse; mit E-A6 (Deckel je Organisation) | DECISIONS 4.1 |
| 2 | – | H10–H14 bestätigen; AF11, AF12, G15 | ANNAHMEN |
| 2 | D5, D6 | Betriebsverantwortung; Datenschutzrolle Emprise ↔ Büro; Anfragebearbeitung; Standort des Servers (L8) | DECISIONS 2 |
| 3 | – | Issue bei `clipper2-ts` melden (endlose `union` bei einem Rücklauf)? Das ist eine Veröffentlichung, nur mit Zustimmung | E-HM-27 |
| 3 | – | Bruttopreise auf den Cent vereinheitlichen (B-65)? | 5 |
| 3 | – | `sentry-sdk` und `renovate.json` entfernen oder behalten? | 5 |
| 3 | – | GPT-6 Sol mit Flex statt Opus 5.5? Empfehlung: bei Opus 5.5 bleiben | PLAN_G2 7.7 |
| 3 | E-A1 | Produktname der Analyse | DECISIONS 4.1 |
| 3 | – | Géorisques-Token; D2 (Beta, öffentlich), E1–E12 soweit offen | DECISIONS 2, 3 |
| später | E-VA-5 | Auslegung von Regeln gemeinsam mit dem Nutzer | PLAN_G2 6 |

## 4. Offene Arbeitspunkte

### 4.1 G2-Vollständigkeit (PLAN_G2_VOLLSTAENDIGKEIT)

1. **Befunde aus 7.7:** Ein Zitat verschluckt eine Vorschrift (S. 14, S. 17); Weg nach Entscheidung in 3. Den Widerspruch im Dach (`flat_roof` zugelassen, `flat` fehlt in `allowed_forms`) in `Roof._consistent` als ungültig werten.
2. **Beyenes UC:** Unter `/analyse` ein Projekt anlegen, das PDF erneut hochladen (Kopie im Volume `emprise_storage-data`, 4.7); die Referenzliste findet es über die Prüfsumme. Danach messen und in PLAN_G2 7.5 nachtragen. Weitere Referenzlisten: Zonen von Treillières, andere Gemeinden.
3. **Staffel der Grundflächenzahl** in Schema und Berechnung (E-VA-4, eigener Plan).
4. **Sperre oder Bestätigung** vor bezahlten Neuauswertungen durch `rules_housekeeping` bei neuer `ENGINE_VERSION`.
5. Denkaufwand `xhigh`/`max` an OpenRouter durchreichen; bei Flex `service_tier` und Wiederholung. Später E-VA-1 und E-VA-2.

### 4.2 Emprise Analyse

1. **Echte Unterlagen:** PLUi Erdre et Gesvres (333 Seiten; Budget prüfen), ein PLU einer anderen Gemeinde, ein règlement de lotissement mit Tabelle je Lot, ein echter Scan (E-AN7-5). Dauer und Kosten in `deploy/unraid/README.md` nachtragen.
2. DXF (Lambert-93, 3D-Gabarit) im ArchiCAD des Büros prüfen (E-AN5-3); echte CAD-DXF aus dem Büro.
3. Nutzfläche gegen Handrechnung an drei Grundstücken; Zitat-PDFs in Chrome und Firefox.
4. Vor Daten in Produktion: Export (UP07); Betroffenenrechte mit Organisationen; verwaiste Dateien bei `retention_cleanup` (B-22).
5. Für fremde Büros (nach E-A5): Deckel (E-A6), Bezahlung, AGB, Auftragsverarbeitung, Einladung; Rückweg für API-Schlüssel und Erscheinungsbild in Git `24d3627`.
6. Ende-zu-Ende Analyse bis zum Zusatzdokument; Komponententest `KonturWahl` mit vielen Flächen; Scan-Parzelle als PDF im Browser.
7. Später: E-AN2-4, Vergleichstabelle in Telefonbreite, E-AN3G-3, E-AN5-8, Filter der Projektliste (ADR-02).

### 4.3 G2 und G3 mit Schlüssel

1. **Schlüssel erneuern** (openrouter.ai/keys); lokal und auf Unraid in `.env`.
2. Kapitel von Treillières: erst klären, warum lokal 11 von 12 `chapter_not_detected` sind (5), dann neu auswerten (`rules-extract --pending`; Budget). Danach `setback_street.band`, `max_area` und Abdeckung in `/buero/regeln` prüfen.
3. `envelope-check --commune 44209` über alle Zonen; dann Beta der Flags erwägen. Später mehrbändige Reglements (RW23).

### 4.4 Ende-zu-Ende und Nachprüfung (H1–H3, A, V)

1. Playwright: Kunde bis Vorentwurf (H2, H3, V), Weg E, „Kunde stellt Anfrage“ (A).
2. Im Browser: gesperrter Typ, Mehrzonen, Gelände, H3 mit `annex`/`unsealed_min`, V mit Abweichungen; DXF von V im ArchiCAD prüfen.
3. Tests: `garage_driveway` (HK07) fehlt, `test_moving_the_house_rechecks_the_outbuildings` schwach; `placement.py::facade` prüfen.
4. A: Test zu AF10, Docstring in `platform/tasks.py`; Komponententests `Anfragen.tsx`/`AnfrageDetail.tsx`; Löschung im Browser; Endlöschung nach D6.
5. H1: echte Typen mit Fassadenrollen (Entscheidung in 3); XLSX-Vorlage mit „netto (HT)“ und „Terrasse je m²“; Docstring der Rollen in `catalog/api.py`.
6. Nach Bedarf: Carport in Schnellstellungen, ungeprüfte Regelarten, Preis-Editor, V-Ausbau.

### 4.5 Auslieferung und Betrieb

1. **CI und Image:** `pypdf` und `urllib3` anheben (1), uv-Cache aus dem Image (5); dann `git pull` und `deploy.sh` auf Unraid. `deploy.sh` baut dabei erstmals `engine` und führt Migration 0024 aus; das Hausmodell selbst erst einrichten, wenn das Büro es ausprobieren soll (4.8).
2. **Unraid nacharbeiten:**
   - Das Platzhalterkonto `deine@adresse.fr` wurde versehentlich mit allen Rollen freigeschaltet. Sperren mit `staff-deactivate`; ob das geschehen ist, ist offen.
   - Paris und Île-de-France prüfen: `idf_import.log` in `/mnt/user/appdata/emprise`, 1 265 `succeeded`, kein `failed` (deploy 15).
   - TOTP und Notfallcodes neben dem Passkey einrichten (deploy 3).
   - Prüfen, dass `OPENROUTER_API_KEY` leer ist.
3. **Vor `inquiry`, `configurator`, `submission`:**
   - `legal-seed` ausführen und Haustypen anlegen (Entscheidung in 3), keine `demo_*`-Typen; einen Preiskatalog veröffentlichen.
   - **`EMPRISE_OFFICE_EMAIL` ist auf Unraid noch nicht verdrahtet**; SMTP nach E2.
4. **Vor dem öffentlichen Start:** Client-IP aus `CF-Connecting-IP` übernehmen, Bot-Schutz von Cloudflare prüfen (ADR-11). `emprise-analyse.aslani.work` als Weiterleitung auf `/analyse`, falls der Name schon verteilt ist.
5. Überwachung (Uptime Kuma), Offsite-Sicherung (mit der Île-de-France rund 1 GB je Sicherung), erste Wiederherstellungsübung; Hauptzweig schützen.
6. Verarbeitungsverzeichnis mit Analyse-Projekten und Organisationen.
7. Nach dem öffentlichen Start mit `--all`: Flag-Prüfungen im Code entfernen (ADR-10).

### 4.6 Weitere Punkte

- „Regelwerke“ im Büro mit echten Daten ansehen.
- CNIG-Typliste für überlagernde Vorgaben (BR05, E-G3-2), bevor Gemeinden mit Regeln dazukommen.
- Log `envelope_derive_failed` (Plan G3 6.2).

### 4.7 Aufräumen (nach Freigabe, siehe 3)

- Datenbanken `emprise_analyse`, `emprise_shared`, `emprise_probe` (`DROP DATABASE`, vorher `pg_dump`).
- Volumes `emprise_storage-data` (darin das Beyenes-PDF) und `emprise_minio-data`.
- 240 Projekte mit `created_by = 'envelope-check'` vom 16.09.2026; zwei Projekte der Schlussprüfung vom 30.09.2026 („Smoke Treillières“, Kundenprojekt AD 65 mit `smoke-30-09@example.com`).
- Test-Stack `emprise-g1`.

### 4.8 Hausmodell (PLAN_HAUSMODELL 6)

1. **Eingaben des Büros für HM3:**
   - Referenz-IFC des Demohauses nach dem Importvertrag als `ifc-proben/demohaus_referenz.ifc`; dann läuft der übersprungene Abnahmetest (bis dahin steht ein synthetisches Demohaus aus den Testdaten).
   - Liste der Zonenkategorien des Büros als Aliasse im Katalog (bisher die des Demo-Katalogs, ohne Garage).
   - ±0,00: Oberkante Bodenplatte oder Fertigfußboden (E-HM-35, Warnung `ground_slab_offset`).
2. **HM2 Oberfläche** nach Festlegung der Referenzgeräte (3): 2D, 3D, Preisleiste, Web Worker, Zielwerte P 4.1 messen. Das Frontend bindet dann `@emprise/domain` als Paket ein.
3. **Playwright für HM3:** Upload bis Freigabe; bisher nur von Hand im lokalen Stack geprüft (PLAN_HAUSMODELL 10).
4. **Probedateien des Büros:** Alle Zonen werden erkannt, veröffentlichen lässt sich aber noch keine. Fenster und Haustür brauchen Katalogtypen mit Rollladenkasten (HM6); Probe 1 hat kein Dach, Probe 2 ein Walmdach (HM5).
5. **HM4 bis HM6** nach PLAN_HAUSMODELL 6. Für HM5 fehlt im Vertrag noch das Dach als Kantenprofile (E-HM-25).
6. **Unraid:** Hausmodell nach deploy 24 einrichten (Konto mit `catalog_admin`, Demo-Katalog per CLI), sobald das Büro es ausprobieren soll.

## 5. Befunde, nicht umgesetzt

| Befund | Bewertung |
|---|---|
| Treillières lokal: 11 von 12 Kapiteln des aktiven Planstands `failed: chapter_not_detected` mit leeren Sektoren, nur Uh ausgewertet | nicht untersucht; vor einer bezahlten Auswertung auf Unraid in `/buero/regeln` ansehen (4.3) |
| Backend-Image enthält den uv-Cache (`/root/.cache/uv`, Trivy findet Pakete doppelt), weil `uv sync` im Dockerfile ohne `--no-cache` läuft | Image größer, Funde doppelt; mit 4.5 Nr. 1 beheben |
| Hausmodell: Hochladen und Freigeben nur mit `catalog_admin` (PLAN_HAUSMODELL 3.6), im Katalog H1 bearbeitet auch `architect` | bewusst nach Plan; angleichen, falls Architekten Haustypen hochladen sollen |
| Hausmodell: Eine fehlende Fassadenrolle ist nur eine Warnung (`facade_roles_missing`) | vor HM4 prüfen, ob sie das Veröffentlichen sperren muss; die PLU-Prüfung braucht die Straßenseite |
| Brutto doppelt gerundet (B-65): `costs.py` und `outputs.py` runden Positionen und Summe getrennt, bis 1 Cent | per Test festgehalten; Entscheidung in 3 |
| Gescanntes Reglement im GPU-Weg endet mit `no_chapters` (E-AN7-6) | Funktionserweiterung; `platform/scan.py` wiederverwendbar |
| Eingabe-Hash beim Text-Rückfall (S18) | nur lokale Altdaten; mit `--force` neu auswerten |
| `site/service.py`: `relocate`, `classify_outline` nicht rein | bei nächster Arbeit an G1 |
| `UNCOVERED_WARNING_SHARE` doppelt (`derive.py`, `resolve.py`) | gleicher Wert; zusammen ändern |
| Zyklen `inquiry` ⇄ `submission` (B-01), `rules.jobs` ⇄ `rules.*` (B-72) | beobachten |
| Drei PDF-Renderer (B-05) | zusammenlegen bei nächster Arbeit an einem Renderer |
| `catalog/service.py` rund 1.150 Zeilen | teilen bei nächster Arbeit an H1 (entfällt mit dem Hausmodell) |
| Frontend-Chunks über 500 kB (`kacheln` 1 MB) | weiter teilen bei Bedarf |
| Handgeschriebene Frontend-Typen `Problem`, `ParcelCollection`, `ReviewPart` | ohne Entsprechung in `components["schemas"]` |
| `sentry-sdk`, `renovate.json` vermutlich ungenutzt | Entscheidung in 3 |
| Tabellenliste in `backend/tests/conftest.py` von Hand (REF-014) | aus Metadaten erzeugen, wenn sie stört |

## 6. Hinweise

- Bezahlte Läufe nur nach Freigabe je Lauf; Tests und lokale Stacks ohne `EMPRISE_OPENROUTER_API_KEY`.
- **Unraid:**
  - Der Nutzer führt `git pull`, `deploy.sh` und die CLI-Befehle selbst aus und schickt Ausgaben oder Screenshots.
  - Befehle gelten für den Ordner `/mnt/user/appdata/emprise-src/deploy/unraid`.
  - Platzhalter unverwechselbar schreiben (z. B. `DEINE-ECHTE-ADRESSE`).
- **Lokal ausprobieren:** `http://localhost:8080`, Anmeldung ohne Passwort über den OIDC-Testdienst, Parzelle TREILLIERES AD 65; Mails in Mailpit (`http://localhost:8025`). Hausmodell unter `/buero/katalog/hausmodell`; Hochladen braucht vorübergehend `catalog_admin` (README, Lokal starten).
- **Probedateien des Büros** liegen in `ifc-proben/` und kommen nie in Git (`ifc-proben/.gitignore`).
- Probeläufe in `emprise_probe`: siehe PLAN_G2 und `EMPRISE_RULES_*`; vor dem zweiten Durchlauf `input_hash` leeren.
- Zwischencommits, die einzeln nicht bauen, bei `git bisect` überspringen: `219a285` bis `1c4ba2b` (Refactoring) und `02795f4` bis `cc3dc0e` (Hausmodell nach Thema).

## 7. Startprompt für die neue Session

```
Lies ROADMAP.md und AI_CONTEXT.md. Fasse den Stand in fünf Sätzen zusammen.
Schlage als Erstes die Behebung der roten CI vor (ROADMAP 2.1). Frage mich danach in höchstens
drei Fragen (Empfehlung an erster Stelle), was aus ROADMAP 2 und 3 als Nächstes kommt, darunter
wie es mit dem Hausmodell weitergeht (HM2 oder HM4, PLAN_HAUSMODELL 6). Arbeite das Gewählte ab
(Plan mit Selbstprüfung, dann Umsetzung). Bezahlte Läufe nur nach meiner Freigabe. Committe und
pushe nur auf meine Anweisung.
```
