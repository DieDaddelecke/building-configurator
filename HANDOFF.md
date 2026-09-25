# Hand-off für die nächste Session

> **Stand:** 25.09.2026 · **Letzte Session:** „Emprise Analyse“ AN2 (Bebauungsplan hochladen) geplant, umgesetzt, im Browser geprüft, committet und gepusht (Eintrag „Emprise Analyse: AN2 …“ oben in [AENDERUNGEN.md](AENDERUNGEN.md)).
> Momentaufnahme, bei jedem `/handoff` neu geschrieben. Dauerhaftes steht nicht hier, sondern in README (Stolperstellen), BETRIEB (Module im Betrieb), ANNAHMEN und Spez. Anhang E.4.

---

## 1. Aktueller Stand

- **Git:** `main` auf https://github.com/DieDaddelecke/building-configurator (privat) gepusht bis `aaa8bf6`: `6241363` AN2, `aaa8bf6` CI e2e ohne fremde Dienste (Arbeit einer parallelen Session, getrennt committet). Uncommittet sind nur die Hand-off-Dokumente dieser Session. **CI-Lauf 36188401453 vollständig grün**, auch e2e (erstmals mit SeaweedFS und ohne fremde Dienste).
- **Hauskonfigurator:** R0 (ohne Auslieferung auf Unraid), G1–G3, A, H1–H3 und V fertig; R2 fachlich vollständig. Durch AN2 geändert: G2 plant einen Folgeauftrag, wenn während einer Auswertung ein Sektor dazukommt (Fehlerbehebung, PU07); sonst gleiches Verhalten, alle bisherigen Tests grün.
- **Emprise Analyse (D18):** AN0, AN1 und **AN2** umgesetzt – règlement écrit als PDF hochladen (Lesen im Job `rules_document_read`, dasselbe PDF = ein Dokument für alle Projekte), Kapitel und Zone wählen, Auswertung mit G2, zweiter Einstieg in `resolve_rules`, Baurahmen auch für Parzellen aus Datei oder Zeichnung, Zitate auf `/api/v1/regulation-files/…#page=`. Festlegungen PU01–PU10; Pläne [PLAN_ANALYSE](docs/PLAN_ANALYSE.md), [PLAN_AN2](docs/PLAN_AN2_PLU.md); Betrieb [BETRIEB 15](docs/BETRIEB.md). **Zusatzdokumente nach AN4 verschoben** (PU09).
- **Tests:** Backend 541 (vorher 526), Frontend 157 (150), dazu ruff, Format, mypy, Typprüfung, Lint und Build grün. Playwright lief lokal nicht; für Konfigurator, V und das Analyse-Produkt gibt es kein Szenario.
- **Lokale Stacks laufen:** Hauskonfigurator http://localhost:8080, „Emprise Analyse“ http://localhost:8180; beide auf Migration **0013**, Objektspeicher SeaweedFS mit `-volume.max=0`. In der Analyse-Datenbank liegt das Testprojekt „Testparzelle Zone Uh“ mit einem Scheinlauf von 0,16 $.
- **G2 ohne Schlüssel** der Claude API weiterhin ohne echte Auswertung (gilt für beide Produkte); H1 fehlen fünf echte Typdateien und die XLSX-Vorlage.
- **Entscheidungen:** D1–D4, D8, D10, D11–D18 entschieden; G17 entschieden. **Spezifikation:** Korrekturen S1–S17 in Anhang E.4 (S3 und S5 gelöst).

## 2. Ergebnisse der letzten Session, die nur im Chat standen

Befunde, Prüflauf und Browserprüfung stehen in [PLAN_AN2](docs/PLAN_AN2_PLU.md) 7.4. Außerdem:

- **Anzeige der PDFs in Chrome ungeprüft:** Die Seiten-CSP gilt nicht mehr für die Planunterlagen (PU06, belegt mit Chromium-Fehler 40328564); geprüft ist nur die Kopfzeile, weil das Browserwerkzeug PDFs herunterlädt.
- **CI:** Der Lauf nach dem Speicherwechsel (`c240195`) war im Job e2e bei `pnpm install --frozen-lockfile` gescheitert; der Lauf nach `aaa8bf6` ist ohne Änderung daran grün – vermutlich ein vorübergehender Fehler.
- **Parallele Session:** Sie hat während dieser Session SeaweedFS committet und gepusht und den e2e-Umbau (`compose.e2e.yaml`) liegen lassen. Beide Dateien verweisen auf eine Festlegung **A28, die in ANNAHMEN fehlt**.

## 3. Offene Entscheidungen des Nutzers

| Priorität | Nr. | Frage | Wo |
|---|---|---|---|
| 1 | – | Konto und Schlüssel der Claude API (vom Nutzer selbst in `.env` und `.env.analyse`); Monatsbudget je Stack (Vorschlag 150 $, lokal 20 $) | BETRIEB 9, 15, RW11 |
| 1 | – | Hostname für Authentik (Vorschlag `auth.aslani.work`); Cloudflare „DNS only“ (empfohlen, L8) oder Proxy | Unraid README 2, A26 |
| 1 | E2 | Mailanbieter (EU-Drittanbieter akzeptiert, z. B. Brevo, Scaleway TEM); dringend, weil A und V Mails brauchen | Spez. 16, BETRIEB 5 |
| 1 | – | Echte Sammeladresse des Büros für `EMPRISE_OFFICE_EMAIL` und **Name des Büros** für die Einwilligungstexte | AF02, AF05, VU08 |
| 2 | E-AN2-5 | **Zusatzdokumente** (lotissement, cahier des charges) wie umgesetzt erst mit AN4 (Regelformular, Übernahme als Projektkorrektur) – bestätigen oder vorziehen | PLAN_AN2 6, PU09 |
| 2 | – | Gescannte PDFs (Parzelle und Reglement) lesen? Nur mit Bilderkennung über die Claude API – Kosten je Aufruf, braucht den Schlüssel. Empfehlung: nach Priorität 1 | UP16, PU03, RW03 |
| 2 | – | Hostname und Authentik-Anwendung für den Analyse-Stack (Vorschlag `analyse.aslani.work`) | BETRIEB 15, PS08 |
| 2 (vor Beta) | – | Rechtliche Prüfung: Simulation (Hinweise, Haftung, Konturen, Weg E), die **vier** vorläufigen Rechtstexte (A und V) und die ODbL-Quellenangabe | Plan 6.9, RW16, AF05, VU08, VU11 |
| 2 | E-A5 | Rechtlicher Rahmen des Analyse-Produkts: Der Hinweis im Fuß genügt, solange nur das eigene Büro arbeitet; **vor AN6 juristisch prüfen** | PLAN_ANALYSE 6 |
| 2 | – | Festlegungen H10–H14 (Format Eingang/Garagentor, links/rechts, Umfang der Katalogoberfläche) bestätigen oder ändern | ANNAHMEN H10–H14 |
| 2 | – | Anfrage ohne Grundstück außerhalb des Einzugsgebiets: eigener Kontaktweg oder Hinweis `site.outside` ändern? | AF11 |
| 2 | – | Antwortvorlage des Büros mit CU-Hinweis nachholen? | AF12, Plan 3.6 |
| 2 | – | Wer schreibt die Hinweistexte L7 (neu auch `notice.rules_upload`, `notice.site_without_cadastre`)? Bis dahin Rückfalltext | G16, G30, BR11, PU05, Plan 8 |
| 2 | – | Datenschutzerklärung: Kartenkacheln direkt vom IGN – Hinweis genügt (Empfehlung) oder Kachel-Proxy? | G15 |
| 2 | D5, D6 | Betriebsverantwortung; Datenschutzrolle Emprise ↔ Büro (bestimmt die Löschung nach einer Anfrage) | Plan 9 |
| 2 | – | Ablauf der Anfragebearbeitung im Büro (Antwortfrist, Vorlagen); Standort des Unraid-Servers (EU, L8) | Plan 8 |
| 3 | – | Gegenprüfung statt zweitem Lauf (RW19) in Plan 3.4 übernehmen? Empfehlung: nach der Messung mit der Referenzmenge | RW19 |
| 3 | E-A1, E-A6 | Endgültiger Produktname statt „Emprise Analyse“ und Kostendeckel der Claude API je Organisation – beides erst vor AN6 | PLAN_ANALYSE 6 |
| 3 | – | Géorisques-Token vor öffentlichem Start | G12 |
| 3 | – | Umsetzungsplan als Ganzes freigeben (dann Plan 7 und Spez. E.4 einarbeiten); D2 (Beta), D7, E1–E12 | Plan 9, Spez. 16 |

## 4. Offene Arbeitspunkte

### 4.1 Emprise Analyse weiterbauen

1. **AN3 – Analyse für den Entwurf** (10–12 T, PLAN_ANALYSE 4): bindende Grundfläche, Vollgeschosse, Nutzflächenspanne (RA1 fertig); Gabarit und Schnitt gehören zu RA2.
2. **Echte Reglements durch den Upload:** das vollständige PLUi Erdre et Gesvres (333 Seiten) und ein PLU einer anderen Gemeinde – Kapitelerkennung, Lesedauer, Vorschläge für Sektoren. Mit Schlüssel Dauer und Kosten eines hochgeladenen Kapitels in BETRIEB 15 eintragen (PLAN_ANALYSE 7 Punkt 7).
3. Zitat-PDFs in Chrome und Firefox öffnen (PU06; `#page=` springt auf die Seite?).
4. **Vor Daten in Produktion:** `GET /projects/{id}/export` fehlt dem Analyse-Produkt (UP07); vor AN6 auch die Betroffenenrechte neu bewerten.
5. Echten Katasterauszug und eine echte CAD-DXF aus dem Büro durch den Upload schicken (PLAN_AN1 8.3).
6. Ende-zu-Ende-Szenario für das Analyse-Produkt (Parzelle, Reglement, Zone, Baurahmen); Komponententest für `KonturWahl` mit vielen Flächen.
7. Später: ungenutzte hochgeladene Dokumente aufräumen (E-AN2-4, BETRIEB 15 – bisher nur per SQL).

### 4.2 Ende-zu-Ende-Tests und Nachprüfung von H2, H3 und V

1. Playwright-Szenarien: „Kunde wählt Typ, verschiebt das Haus, wählt Linie und Optionen, übergibt den Vorentwurf“ (H2, H3, V) und Weg E; für A siehe 4.4. Für V braucht die CI zusätzlich `tests.e2e_seed_types`, `legal-seed` und den Code aus Mailpit.
2. Im Browser ansehen: gesperrter Typ mit echten Regeln, Mehrzonen-Grundstück, Berührung, Höhenprüfung mit Gelände; für H3 ein Grundstück mit wirksamer `annex`- und `unsealed_min`-Regel; für V eine Übergabe **mit** Abweichungen und ein Dossier für Weg E.
3. **DXF im ArchiCAD des Büros prüfen** (BETRIEB 14); bisher nur mit `ezdxf` zurückgelesen.
4. Aufräumen in `backend/app/configuration/domain/placement.py`: unbenutzter Parameter `facade` in `_band_checks`, ungenutzte Hilfen `footprint_polygons`, `all_segments`.
5. Ungenutztes im Frontend: `vatRate` in `configuration/Linien.tsx`, Schlüssel `configurator.options.kind`, `configurator.options.perM2`, `configurator.plan_layers`, `submission.disabled` in `i18n/{de,fr}.json`.
6. Tests ergänzen: Zufahrt zum Garagentor (`garage_driveway`, HK07) hat keinen Test; `test_moving_the_house_rechecks_the_outbuildings` akzeptiert 200 oder 422 und ist damit schwach.

### 4.3 H3 und V weiterentwickeln (nach Bedarf)

- Schnellstellungen des Hauses (H2) kennen den Carport nicht (Plan H3 10.3).
- Nicht geprüft: `spaces_per_m2_sdp`, `setback_between_buildings`, `color_families_allowed`; kein Keller, keine Photovoltaik-Belegung, keine Ausführungen und Mengen (Plan 7, X3).
- Ein Preis-Editor fehlt: Preise kommen nur aus dem XLSX (H05, H14); die Importbeschreibung sollte „netto (HT)“ und „Terrasse je m²“ nennen (siehe 4.5).
- V: Anhänge an Nachrichten, Kopie einer Fassung als neue Konfiguration (Spez. 5.10.8), Webhooks (X5), erweitertes Dossier (X4) – bewusst offen (Plan V 1, 9.3).

### 4.4 Modul A nacharbeiten

1. Test: Projekt mit Anfrage überlebt `retention_cleanup`, Projekt mit unbestätigtem Kontakt nicht (AF10); Docstring in `backend/app/platform/tasks.py` anpassen.
2. Punkte aus AF11 und AF12 nach Entscheidung (Abschnitt 3).
3. E2E-Szenario „Kunde stellt Anfrage“; Komponententests für `Anfragen.tsx`/`AnfrageDetail.tsx`.
4. Löschung eines Projekts im Browser ohne Anfrage prüfen (`DatenschutzAktionen`, Weiterleitung auf `/`, veraltetes Cookie) – die Löschung liegt seit AN1 im Kern.
5. Später: Büro-Funktion für die Endlöschung nach einer Anfrage (nach D6).

### 4.5 H1 abschließen

1. **Fünf Platzhalter-Typen** als echte XLSX/DXF erfassen (Plan H1 Kapitel 12) und hochladen; Linien und Optionen zuerst, **Fassadenrollen zuweisen**. `backend/tests/e2e_seed_types.py` zeigt ein Muster mit Preisen.
2. XLSX-Vorlage zum Herunterladen; darin „Preise netto (HT)“ und „Terrasse je m²“ ergänzen.
3. Docstring von `backend/app/catalog/api.py` nennt die Rollen falsch (`architect` liest nur); laut Code bearbeiten `architect` und `catalog_admin` (H01, H14).
4. Optional: Entwurf direkt bearbeiten statt neue Version; Komponententests für Preise und Typstand; Playwright Katalogpflege; Fehlertexte der Konsistenzprüfung über `code` übersetzen.

### 4.6 G2 und G3 abschließen (sobald ein Schlüssel eingetragen ist)

1. Schlüssel in `.env`, `docker compose up -d`; sofort `docker compose exec api python -m app.cli rules-extract --pending`. Kosten, Dauer, Anteil der Gegenprüfung in BETRIEB 9 eintragen.
2. Wegen `g2-prompt-3` alle Kapitel neu auswerten; prüfen, ob `setback_street.band` gefüllt ist.
3. Referenzmenge der Zonen von Treillières messen (Spez. 11.4).
4. `envelope-check --commune 44209` über alle Zonen wiederholen, Anteil unvollständiger Konturen in BETRIEB 10 festhalten; für H2 den Anteil gesperrter Typen je Zone prüfen; für H3, wie oft `annex`, `unsealed_min` und `facade` wirksam werden.
5. Danach Beta für `rules_simulation`/`envelope_simulation`/`inquiry`/`configurator`/`submission` erwägen.
6. Später: Korrekturformular statt JSON (RW15) – **gehört zu AN4**, zusammen mit den Zusatzdokumenten; OCR (RW03); mehrbändige Reglements (RW23).

### 4.7 Auslieferung und Betrieb

1. Unraid in Betrieb nehmen ([deploy/unraid/README.md](deploy/unraid/README.md) 2–4), danach TLS, Authentik, `staff-add`, Login prüfen.
2. G1–V auf Unraid nach Unraid README 9 und BETRIEB 1 (ausgehender Zugang, `.env` mit `ANTHROPIC_API_KEY`, Migrationen 0007–**0013**, `legal-seed`, Flags). **`EMPRISE_OFFICE_EMAIL` ist in `deploy/unraid/compose.yaml` und `deploy/unraid/.env.example` noch nicht verdrahtet** – ergänzen. `demo_*`-Typen und Demo-Preise nie in Produktion; vor `configurator` und `submission` einen Preiskatalog veröffentlichen (BETRIEB 13, 14).
3. Zweiten Stack ausliefern, sobald gewünscht: `.env.analyse` aus der Vorlage (mit `ANTHROPIC_API_KEY`), eigene Authentik-Anwendung, `./deploy.sh analyse` (BETRIEB 15).
4. Überwachung (Uptime Kuma, Unraid README 7) mit den Log-Alarmen aus BETRIEB 1, auch `dossier_failed`; Offsite-Sicherung; erste Wiederherstellungsübung.
5. SMTP nach E2 eintragen, Testmail; GitHub-Hauptzweig schützen.
6. Verarbeitungsverzeichnis (Plan 4.1 Kriterium 6): Staff-E-Mail, Mailadressen in Jobs (A12), IP-HMAC (A7), Steckbriefe (BR10), Kundenkontakt, Einwilligungen, Snapshots, Konfiguration, Dossierdateien; die Projekte des Analyse-Produkts (Eigentümer, hochgeladene Umrisse); hochgeladene Reglements enthalten keine personenbezogenen Daten (PU01). Die Claude API erhält nur Planunterlagen.
7. Den ungenutzten Band `minio-data` entfernen (`docker volume rm emprise_minio-data`, README).
8. **CI:** Festlegung A28 (e2e ohne fremde Dienste, `compose.e2e.yaml`) in ANNAHMEN nachtragen – beide Dateien verweisen schon darauf.

### 4.8 Weitere Punkte

1. **Spezifikation:** S1–S17 mit Stand in Spez. Anhang E.4; zusammen mit Plan Kapitel 7 einarbeiten, sobald der Plan freigegeben ist (Abschnitt 3).
2. Büro-Oberfläche „Regelwerke“ (G2: „Erneut versuchen“, „Neu auswerten“, „veraltet“) mit echten Daten ansehen; hochgeladene Reglements erscheinen dort nicht (nur je Projekt im Analyse-Produkt).
3. Einwilligung zur Datenweitergabe im Mockup (Spez. Anh. E.2 M10): serverseitig da, das Mockup zeigt sie weiter nicht.
4. Vor Erweiterung des Einzugsgebiets: CNIG-Typliste der überlagernden Vorgaben prüfen (BR05).
5. Log `envelope_derive_failed` (Plan G3 6.2) anlegen oder im Plan streichen.
6. Alten Test-Stack der G1-Session entfernen: `docker compose -p emprise-g1 down -v`.

## 5. Empfohlener nächster Schritt

1. Hand-off-Dokumente dieser Session committen; A28 nachtragen (4.7 Punkt 8).
2. Priorität 1 aus Abschnitt 3 klären (Schlüssel der Claude API, Authentik-Hostname, Mailanbieter, Büro-Postfach und -Name); E-AN2-5 bestätigen.
3. Danach entweder **AN3** (4.1) oder die Auslieferung auf Unraid und G2/G3 mit echtem Schlüssel (4.6, 4.7). Mit Schlüssel lohnt zuerst 4.1 Punkt 2 (echtes Reglement), weil es beide Produkte misst.
4. Bald 4.2 und 4.1 Punkt 6: Playwright-Szenarien.

## 6. Hinweise

- Stolperstellen (lokaler Stack, SeaweedFS, Tests, Browserprüfung mit PDFs und Scheinauswertung) stehen dauerhaft in [README.md](README.md).
- Der Volllauf des Backends dauert rund 7–17 Minuten; `docker compose run -T` benutzen.
- Beim Öffnen eines PDF im Browserwerkzeug ging beim Nutzer ein Speichern-Dialog auf; PDFs dort nicht aufrufen.

## 7. Startprompt für die neue Session

```
Lies HANDOFF.md und den obersten Eintrag in AENDERUNGEN.md. Fasse den Stand in fünf Sätzen zusammen.
Committe die Hand-off-Dokumente der Vorsession und trage A28 nach (HANDOFF 4.7 Punkt 8). Entscheide danach mit mir die
Priorität-1-Punkte und E-AN2-5 aus HANDOFF 3 – höchstens drei Fragen, jede mit Empfehlung an erster Stelle.
Arbeite anschließend AN3 aus HANDOFF 4.1 ab (Modulplan mit Selbstprüfung, dann Umsetzung) oder, wenn
ich das vorziehe, die Auslieferung auf Unraid (4.7). Committe und pushe nur auf meine Anweisung.
```
