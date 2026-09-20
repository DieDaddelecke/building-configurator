# Hand-off für die nächste Session

> **Stand:** 19.09.2026 · **Letzte Session:** H3 (Konfiguration und Kosten) geplant, umgesetzt und im Browser geprüft; noch nichts committet (Eintrag „H3“ oben in [AENDERUNGEN.md](AENDERUNGEN.md)).
> Momentaufnahme, bei jedem `/handoff` neu geschrieben. Dauerhaftes steht nicht hier, sondern in README (Stolperstellen), BETRIEB (Module im Betrieb), ANNAHMEN und Spez. Anhang E.4.

---

## 1. Aktueller Stand

- **Git:** `main` auf https://github.com/DieDaddelecke/building-configurator (privat) steht auf `a5fc5e3`, CI-Lauf 35431041895 grün. **Uncommittet im Arbeitsbaum:** H3 (Code, Tests, Dokumente) und die Änderungen an HANDOFF/AENDERUNGEN der Vorsession.
- **R0 Plattform:** anbieterunabhängiger Teil fertig; Unraid vorbereitet, nicht ausgeliefert (ANNAHMEN A1–A27).
- **G1–G3, A, H1, H2:** fertig und lokal intern freigeschaltet; G2 ohne Schlüssel der Claude API noch keine echte Auswertung. Offen bei H1: fünf echte Typdateien, XLSX-Vorlage.
- **H3 Konfiguration und Kosten:** fertig (ANNAHMEN HK01–HK17, [PLAN_H3](docs/PLAN_H3_KONFIGURATION_KOSTEN.md), BETRIEB 13): Linie und Optionen mit Ausschlüssen, Terrasse (je m²) und Carport (einstellig, zweistellig) automatisch gesetzt, Flächen, Regelprüfung, RE2020-Status, Kostenkorridor brutto mit „ca.“, Himmelsrichtung mit Meridiankonvergenz; Migration 0010, `ENGINE_VERSION h3-1.0.0`. Route `/konfigurator` mit den Schritten Haustyp, Implantation, Linie, Optionen, Vorentwurf und Kostenleiste; Katalogpflege mit Art, Maßen und Material.
- **Hauskonfigurator (R2):** H1–H3 da; **V (Übergabe) fehlt**. Der Vorentwurf sendet nichts ab, er verweist auf die Anfrage der Grundstücksseite.
- **Tests:** Backend 444, Frontend 132, ruff, mypy, Typprüfung, Lint, Build grün. Playwright lief lokal nicht.
- **Lokaler Stack `emprise`:** Migration 0010, Flags für `architect`. Demo: `demo_*`-Typen (v2), Linien `base`/`confort`, Optionen `terrasse`, `carport_1`, `carport_2`, `pv`, `holz_sued`, veröffentlichter Preiskatalog v1 (erfundene Preise), RE2020-Befund `demo_ligne`/`base`; dazu die H1-Testtypen `ligne`, `plateau`, eine Anfrage `EMP-2026-000001`.
- **Entscheidungen:** D1–D4, D11, D12, D13, D14 entschieden; D8 und D10 nach Empfehlung genommen, **nicht bestätigt**. **Spezifikation:** Korrekturen S1–S17 offen (Anhang E.4); sie wird kapitelweise gelesen.

## 2. Ergebnisse der letzten Session, die nur im Chat standen

- **Auslegung des Ablaufs:** Der Nutzer stellte den Ablauf im Startprompt vor (Stand, gezielte Fragen, dann Plan und Umsetzung in einem) und beantwortete die Fragen; was er nicht gefragt bekam (D8, D10), gilt als nach Empfehlung entschieden (Memory `feedback-plan-dann-umsetzen`).
- **Preise:** Das Büro trägt Preise **netto (HT)** ein; angezeigt wird brutto mit `vat_rate_default` des Katalogs (20 %). Wer brutto einträgt, bekommt 20 % zu viel (BETRIEB 13, HK10). Die Terrasse wird je m² berechnet, alle anderen Optionen fest.
- **Auffälligkeiten im Browser (behoben, in Plan H3 10.1a):** Carport hinter dem Haus mit Zufahrt durch das Haus; Carport überlappt Terrasse. Folge: Der zweistellige Carport ist auf AD 65 neben einem mittig stehenden Haus gesperrt (`no_valid_position`), bis das Haus zur Seite rückt.
- **Messwerte:** siehe Plan H3 Kapitel 6 (Auswertung 13–79 ms lokal).
- **Zone Uh von AD 65** hat weder Nebengebäuderegel noch Regel zum unversiegelten Anteil: im Browser sind `carport_setback_relaxed` und `unsealed_min_unknown` zu sehen, ein Nebenbauverstoß mit echten Regeln nur in den Tests.

## 3. Offene Entscheidungen des Nutzers

| Priorität | Nr. | Frage | Wo |
|---|---|---|---|
| 1 | – | Konto und Schlüssel der Claude API (vom Nutzer selbst in `.env`); Monatsbudget (Vorschlag 150 $, lokal 20 $) | BETRIEB 9, RW11 |
| 1 | – | Hostname für Authentik (Vorschlag `auth.aslani.work`); Cloudflare „DNS only“ (empfohlen, L8) oder Proxy | Unraid README 2, A26 |
| 1 | E2 | Mailanbieter (EU-Drittanbieter akzeptiert, z. B. Brevo, Scaleway TEM); dringend, weil Modul A Mails braucht | Spez. 16, BETRIEB 5 |
| 1 | – | Echte Sammeladresse des Büros für `EMPRISE_OFFICE_EMAIL` und **Name des Büros** für den Einwilligungstext | AF02, AF05 |
| 2 | D8, D10 | Nach Empfehlung genommen (HK10): Honorar oder Bauleistung (nur Wortlaut der Spanne); Mehrwertsteuer (netto speichern, brutto anzeigen): bestätigen oder ändern | Plan 9, ANNAHMEN HK10 |
| 2 | – | Festlegungen H10–H14 (Format Eingang/Garagentor, links/rechts, Umfang der Katalogoberfläche) bestätigen oder ändern | ANNAHMEN H10–H14 |
| 2 (vor Beta) | – | Rechtliche Prüfung: Simulation (Hinweise, Haftung, Konturen, Weg E) und die zwei vorläufigen Einwilligungstexte | Plan 6.9, RW16, AF05 |
| 2 | – | Anfrage ohne Grundstück außerhalb des Einzugsgebiets: eigener Kontaktweg oder Hinweis `site.outside` ändern? | AF11 |
| 2 | – | Zugangslink in der Kundenmail (signiert) und Antwortvorlage des Büros mit CU-Hinweis nachholen? | AF12, Plan 3.6 |
| 2 | – | Wer schreibt die Hinweistexte L7? Bis dahin Rückfalltext | G16, G30, BR11, Plan 8 |
| 2 | – | Datenschutzerklärung: Kartenkacheln direkt vom IGN – Hinweis genügt (Empfehlung) oder Kachel-Proxy? | G15 |
| 2 | D5, D6 | Betriebsverantwortung; Datenschutzrolle Emprise ↔ Büro (bestimmt die Löschung nach einer Anfrage) | Plan 9 |
| 2 | – | Ablauf der Anfragebearbeitung im Büro (Antwortfrist, Vorlagen); Standort des Unraid-Servers (EU, L8) | Plan 8 |
| 3 | – | Gegenprüfung statt zweitem Lauf (RW19) in Plan 3.4 übernehmen? Empfehlung: nach der Messung mit der Referenzmenge | RW19 |
| 3 | – | ODbL des Katasters vor Modul V klären; Géorisques-Token vor öffentlichem Start | G12, G17 |
| 3 | – | Umsetzungsplan als Ganzes freigeben (dann Plan 7 und Spez. E.4 einarbeiten); D2 (Beta), D7, E1–E12 | Plan 9, Spez. 16 |

## 4. Offene Arbeitspunkte

### 4.1 Nachprüfung von H2 und H3, Ende-zu-Ende-Tests

1. Playwright-Szenarien: „Kunde wählt Typ, verschiebt das Haus, wählt Linie und Optionen“ (H2, H3), Weg E (fehlt seit 17.09.); für A siehe 4.4.
2. Im Browser ansehen: gesperrter Typ mit echten Regeln, Mehrzonen-Grundstück, Berührung, Höhenprüfung mit Gelände (`site_enrich`); für H3 zusätzlich ein Grundstück mit wirksamer `annex`- und `unsealed_min`-Regel, Ziehen des Hauses mit gewählter Terrasse und Carport (`selection_blocked` im Plan sichtbar?), Kostenleiste und Optionen auf dem Telefon, Katalogpflege-Formulare (nur Komponententests).
3. Aufräumen in `backend/app/configuration/domain/placement.py`: unbenutzter Parameter `facade` in `_band_checks`, ungenutzte Hilfen `footprint_polygons`, `all_segments`.
4. H3 aufräumen: `vatRate` in `frontend/src/configuration/Linien.tsx` (`EnergieHinweis`) ist ungenutzt; ungenutzte Schlüssel `configurator.options.kind`, `configurator.options.perM2`, `configurator.plan_layers` in `i18n/{de,fr}.json`.
5. H3-Tests ergänzen: Zufahrt zum Garagentor (`garage_driveway`, HK07) hat keinen Test; `test_moving_the_house_rechecks_the_outbuildings` akzeptiert 200 oder 422 und ist damit schwach.

### 4.2 H3 weiterentwickeln (nach Bedarf)

- Schnellstellungen des Hauses (H2) kennen den Carport nicht: Eine Lage, die den zweistelligen Carport zulässt, wird nicht vorgeschlagen (Plan H3 10.3).
- Nicht geprüft: `spaces_per_m2_sdp` (Hinweis `parking_not_checked`), `setback_between_buildings`, `color_families_allowed`; kein Keller, keine Photovoltaik-Belegung, keine Ausführungen und Mengen (Plan 7, X3).
- Ein Preis-Editor fehlt: Preise (auch je m² der Terrasse) kommen nur aus dem XLSX (H05, H14); die Importbeschreibung sollte „netto (HT)“ und „Terrasse je m²“ nennen (siehe 4.5).

### 4.3 V – Vorentwurf-Übergabe

Umsetzungsplan 3.10, Spez. 5.10: Anfrage um Konfiguration und Auswertung im Snapshot erweitern (die Antwort trägt schon `selection` mit Versionen, `costs.catalog_version`, `engine_version`), vollständige Neuprüfung beim Absenden (neuer Preiskatalog, neue Regeln), Dossier-PDF, Lageplan als DXF (Lambert-93 und lokale Meter), Zustände, Nachrichten. D14: A bleibt daneben Notausgang. Zuerst `docs/PLAN_V_….md` schreiben und selbst prüfen.

### 4.4 Modul A nacharbeiten

1. Test: Projekt mit Anfrage überlebt `retention_cleanup`, Projekt mit unbestätigtem Kontakt nicht (AF10); Docstring in `backend/app/platform/tasks.py` anpassen.
2. Punkte aus AF11/AF12 nach Entscheidung (Abschnitt 3).
3. E2E-Szenario „Kunde stellt Anfrage“; Komponententests für `Anfragen.tsx`/`AnfrageDetail.tsx` (bisher nur `AnfrageFormular`).
4. Löschung eines Projekts im Browser ohne Anfrage prüfen (`DatenschutzAktionen`, danach Weiterleitung auf `/`, veraltetes Cookie).
5. Später: Büro-Funktion für die Endlöschung nach einer Anfrage (nach D6), Nachrichten an den Kunden (mit V).

### 4.5 H1 abschließen

1. **Fünf Platzhalter-Typen** als echte XLSX/DXF erfassen (Plan H1 Kapitel 12; DXF-Umriss dort nur als Rechteck angenommen) und hochladen; Linien und Optionen zuerst (sonst `catalog_reference_unknown`); **Fassadenrollen zuweisen** (sonst richtet sich H2 nach Modellnorden, `facade_roles_missing`, und H3 kann keine Terrasse setzen). Ein Generator fehlt; `backend/tests/e2e_seed_types.py` zeigt ein Muster mit Preisen.
2. XLSX-Vorlage zum Herunterladen (Endpunkt oder Datei); bisher nur die Beschreibung im Importformular; darin „Preise netto (HT)“ und „Terrasse je m²“ ergänzen.
3. Docstring von `backend/app/catalog/api.py` nennt die Rollen falsch (`architect` liest nur); laut Code bearbeiten `architect` und `catalog_admin` (H01, H14).
4. Optional: Entwurf direkt bearbeiten statt neue Version; Komponententests für Preise und Typstand; Playwright Katalogpflege; Fehlertexte der Konsistenzprüfung über `code` übersetzen statt des deutschen `detail`.

### 4.6 G2 und G3 abschließen (sobald ein Schlüssel eingetragen ist)

1. Schlüssel in `.env`, `docker compose up -d`; sofort `docker compose exec api python -m app.cli rules-extract --pending`. Kosten, Dauer, Anteil der Gegenprüfung in BETRIEB 9 eintragen.
2. Wegen `g2-prompt-3` alle Kapitel neu auswerten; prüfen, ob `setback_street.band` gefüllt ist.
3. Referenzmenge der Zonen von Treillières messen (Spez. 11.4).
4. `envelope-check --commune 44209` über alle Zonen wiederholen, Anteil unvollständiger Konturen in BETRIEB 10 festhalten; für H2 den Anteil gesperrter Typen je Zone stichprobenartig prüfen; für H3 prüfen, wie oft `annex`, `unsealed_min` und `facade` wirksam werden.
5. Danach Beta für `rules_simulation`/`envelope_simulation`/`inquiry`/`configurator` erwägen.
6. Später: Korrekturformular statt JSON (RW15); OCR (RW03); mehrbändige Reglements (RW23).

### 4.7 Auslieferung und Betrieb

1. Unraid in Betrieb nehmen ([deploy/unraid/README.md](deploy/unraid/README.md) 2–4), danach TLS, Authentik, `staff-add` (auch für die Katalogpflege), Login prüfen.
2. G1–H3 auf Unraid nach Unraid README 9 und BETRIEB 1 (ausgehender Zugang, `.env` mit `ANTHROPIC_API_KEY`, Migrationen 0007–0010, `legal-seed`, Flags). **`EMPRISE_OFFICE_EMAIL` ist in `deploy/unraid/compose.yaml` und `.env.example` noch nicht verdrahtet** – ergänzen, sonst gehen Büro-Mails an den Platzhalter. `demo_*`-Typen und die Demo-Preise nie in Produktion; vor dem Freischalten von H3 einen Preiskatalog veröffentlichen (BETRIEB 13).
3. Überwachung (Uptime Kuma, Unraid README 7) mit den Log-Alarmen aus BETRIEB 1; Offsite-Sicherung; erste Wiederherstellungsübung.
4. SMTP nach E2 eintragen, Testmail; GitHub-Hauptzweig schützen.
5. Verarbeitungsverzeichnis (Plan 4.1 Kriterium 6): Staff-E-Mail, Mailadressen in Jobs (A12), IP-HMAC (A7), Steckbriefe (BR10), Kundenkontakt, Einwilligungen, Snapshot (A), Konfiguration am Projekt (H2, H3: Linie, Optionen); die Claude API erhält nur Planunterlagen.
6. Optional: lokal und in CI SeaweedFS statt MinIO (A16, A22).

### 4.8 Korrekturen an der Spezifikation

S1–S17 mit Stand in Spez. Anhang E.4; zusammen mit Plan Kapitel 7 (jetzt auch Cache, Ausführungen) einarbeiten, sobald der Plan freigegeben ist (Abschnitt 3).

### 4.9 Weitere Punkte

1. Büro-Oberfläche „Regelwerke“ (G2: „Erneut versuchen“, „Neu auswerten“, „veraltet“) mit echten Daten ansehen.
2. Einwilligung zur Datenweitergabe im Mockup (Spez. Anh. E.2 M10): serverseitig da, das Mockup zeigt sie weiter nicht.
3. Vor Erweiterung des Einzugsgebiets: CNIG-Typliste der überlagernden Vorgaben prüfen (BR05).
4. Log `envelope_derive_failed` (Plan G3 6.2) anlegen oder im Plan streichen; bisher gibt es keinen Alarm für G3.
5. Alten Test-Stack der G1-Session entfernen: `docker compose -p emprise-g1 down -v` (Container `emprise-g1-db-1`, Volume `emprise-g1_db-data`).

## 5. Empfohlener nächster Schritt

1. **Committen** (auf Anweisung, direkt auf `main`): erst H3 (Code, Tests, Dokumente), getrennt davon HANDOFF und AENDERUNGEN; vor dem Push die CI-Prüfungen lokal wie in README „Prüfen“. Danach CI-Lauf prüfen (`gh run list`; bei Netzfehlern zu `sum.golang.org` `gh run rerun <id> --failed`).
2. Priorität 1 aus Abschnitt 3 klären (Schlüssel der Claude API, Authentik-Hostname, Mailanbieter, Büro-Postfach und -Name), dann 4.6/4.7.
3. **V planen und umsetzen** (4.3); erst dann ist der Hauskonfigurator vollständig. Parallel H1 abschließen (4.5), sonst gibt es keine echten Typen und Preise für die Beta.

## 6. Hinweise

- Stolperstellen (Werkzeuge, lokaler Stack, Tests, Browserprüfung) stehen dauerhaft in [README.md](README.md); neue dort eintragen.
- Modulübersicht für Betrieb und Freischalten: [docs/BETRIEB.md](docs/BETRIEB.md) Abschnitt 1, für H3 Abschnitt 13.
- Der Volllauf des Backends dauert 4–11 Minuten (README, Stolperstellen: `docker compose run -T`).

## 7. Startprompt für die neue Session

```
Lies HANDOFF.md und den Eintrag vom 19.09.2026 „H3“ in AENDERUNGEN.md. Fasse den Stand in fünf Sätzen zusammen und nenne die Entscheidungen mit Priorität 1. Frag mich, ob D8 und D10 (HK10: netto speichern, brutto anzeigen; Wortlaut der Spanne) so bleiben sollen. Danach plane V (Vorentwurf-Übergabe, Umsetzungsplan 3.10) mit Selbstprüfung und setze es um. Die H3-Änderungen und die Dokumente der beiden Vorsessions sind noch nicht committet; committe und pushe nur auf meine Anweisung.
```
