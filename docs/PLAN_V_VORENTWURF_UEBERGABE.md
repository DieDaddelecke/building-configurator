# V Vorentwurf-Übergabe – Plan für die Umsetzung

> **Umgesetzt am 19.09.2026:** Backend `backend/app/submission` (Übergabe, Dossier, Job `dossier_generate`), Prüfstempel in `backend/app/configuration/review.py`, Nachrichten, Zustände und Zugangslink in `backend/app/inquiry`, Migration 0011; Oberfläche: Übergabe im Schritt Vorentwurf, `/vorgang`, `/zugang`, Fassungen und Nachrichten im Büro. 12 Einheits- und 18 Integrationstests des Backends (Gesamtstand 474), 11 neue Tests der Oberfläche (Gesamtstand 143); im Browser auf AD 65 geprüft (Kapitel 6). Festlegungen in ANNAHMEN VU01–VU16, Betrieb in BETRIEB 14. Offen: Playwright-Szenario, DXF im ArchiCAD des Büros.
>
> **Entwurf vom 19.09.2026** zu Umsetzungsplan 3.10, Spezifikation 4.4, 5.10.1–5.10.7 (gekürzt), 6.3, 6.4, 10.2, 10.3. Entscheidungen des Nutzers in dieser Session: D8 und D10 bleiben wie in HK10 (bestätigt), **ODbL: Quellenangabe in PDF und DXF genügt** (G17; rechtliche Prüfung vor der Beta bleibt offen). Die Festlegungen in Kapitel 8 tragen je eine Empfehlung und gelten mit dem Auftrag „plane V … und setze es um“ als entschieden ([[feedback-plan-dann-umsetzen]]); sie stehen in `docs/ANNAHMEN.md` (Abschnitt V, Präfix `VU`) und sind umkehrbar.

## 1. Ziel und Abgrenzung

**Ziel:** Der Kunde übergibt den fertigen Vorentwurf aus dem Konfigurator an das Büro. Beim Absenden rechnet der Server alles neu und zeigt, was sich seit dem Anzeigen geändert hat; das Büro erhält eine unveränderliche Fassung mit Snapshot, Dossier-PDF und DXF-Lageplan und kann mit dem Kunden Nachrichten tauschen. Damit ist der Regelweg G3 → H2 → H3 → V geschlossen (D14); A bleibt daneben der schnelle Weg ohne Konfiguration.

**In V:**
- Übergabe als **Fassung** (`submission`) desselben Vorgangs (`inquiry`, eine Nummer je Projekt, Plan A 3.4); eine Neuübergabe setzt die vorige Fassung auf `superseded`.
- **Vollständige Neuprüfung beim Absenden** über einen Prüfstempel (3.3), Bestätigung „mit Abweichungen übergeben“ (3.4).
- Einwilligungen je Fassung (3.5), Snapshot Schema 2 (3.6).
- Dossier: **PDF** in Französisch und Deutsch (Projektbeschreibung gekürzt, Lageplan, Regelprüfung mit Zitaten, Kosten) und **DXF-Lageplan** in Lambert-93 und in lokalen Metern (3.7), als Job.
- Zustände des Vorgangs, **Nachrichten** Büro ↔ Kunde, Zurückziehen (3.8).
- **Zugangslink** per Mail und Anforderung eines neuen Links (3.9; schließt AF12 Punkt 1).
- Oberfläche: Übergabe im Schritt Vorentwurf, Kundenseite „Mein Vorgang“ (`/vorgang`), Zugangsseite (`/zugang`), Fassungen und Nachrichten im Anfrage-Detail des Büros.

**Nicht in V:** IFC, XLSX-Mengen, Pläne des Typs mit Stempel, Ansichten und Axonometrie, ZIP-Paket (X4); Webhooks (X5); Kopie einer Fassung als neue Konfiguration durch das Büro (Spez. 5.10.8, KANN); Anhänge an Nachrichten; Mailanhang (AF01 gilt weiter); Endlöschung nach einer Anfrage (D6); Anfrage ohne Grundstück (AF11).

## 2. Ausgangslage

- **A** legt beim Bestätigen des Codes `inquiry` (eine je Projekt, Nummer aus Sequenz, vier freie Zustände, Snapshot Schema 1 aus Grundstück, Regeln, Baurahmen), `customer` (bestätigt) und zwei `consent` an (eindeutig je Projekt und Art, unveränderlich per Trigger). Mails laufen als Jobs in derselben Transaktion. Das Projekt-Cookie gilt 90 Tage ab Anlage und wird nie erneuert; wer es verliert, kommt nicht mehr an sein Projekt (AF12).
- **H2/H3** rechnen bei jedem `GET …/configuration` neu (HP13, HK01). `ConfigurationOut` trägt Typversion (mit `retired`), Versionen von Linie und Optionen, `costs.catalog_version`, `engine_version`, Prüfungen (`fit.reasons`, `evaluation.checks`, `compliance.checks`). `PATCH` lehnt nur **neue** bindende Verstöße ab (HK08); eine gespeicherte Konfiguration kann also nach einem Regel- oder Katalogwechsel bindende Verstöße tragen.
- **G3** bildet eine Prüfsumme über den **Inhalt** von Grundstück und Regeln (`envelope.service.fingerprint`), nicht über Versionsnummern (Gelände kommt ohne neue Revision, Projektkorrekturen ohne neue Regelwerksversion).
- Der Steckbrief (G3) zeigt das Muster für PDFs: HTML mit SVG-Lageplan, WeasyPrint im Worker, Ablage im Objektspeicher, Download über die API. `ezdxf` und WeasyPrint sind im Image.
- Lokale Koordinaten sind Lambert-93 minus `local_origin` (reine Verschiebung, auf Millimeter gerundet). Für Weg E ist der Ursprung ohne geografische Bedeutung (G27).

## 3. Fachliche Festlegungen

### 3.1 Vorgang und Fassungen

- **Vorgang** = `inquiry`: Nummer, Kunde, Status der Bearbeitung im Büro. **Fassung** = `submission`: laufende Nummer 1 … n je Vorgang, Snapshot, Dossier, Einwilligungen. A erzeugt einen Vorgang ohne Fassung; V erzeugt Vorgang und Fassung 1 oder eine weitere Fassung. Genau eine Fassung ist `current` (Index), alle früheren `superseded`.
- Spez. 5.10.1 vermischt beides; die Zuordnung:

| Spez. 5.10.1 | Hier |
|---|---|
| `submitted` | Vorgang `neu` (auch nach jeder Neuübergabe) |
| `in_review` | `in_bearbeitung` |
| `clarification` | `rueckfrage` (neu) |
| `offer_sent` | `beantwortet` |
| `closed` | `geschlossen` |
| `withdrawn` | `zurueckgezogen` (neu) |
| `superseded` | Status der **Fassung** |

- Die Konfiguration bleibt nach der Übergabe änderbar; ans Büro gelangt eine Änderung nur als neue Fassung. Die Fassung selbst ist unveränderlich (kein Schreibpfad auf Snapshot und Einwilligungen). Das Büro sieht die übergebene Fassung (Snapshot, Dossier) und den Hinweis „seit der Übergabe geändert“, wenn die Revision der Konfiguration höher ist.

### 3.2 Absenden

**Voraussetzungen:** Grundstück, Typ und Lage; eine **Linie, sobald der Katalog für den Typ Linien anbietet** (Spez. 5.10.2 Punkt 1 verlangt sie; ohne veröffentlichten Katalog gibt es keine, dann entfiele V ganz). Sonst `409 submission_incomplete` mit `missing`.

**Ablauf** (`POST /projects/{id}/submission`, Flag `submission`), in einer Transaktion mit Sperre auf der Projektzeile:

1. Beide Bestätigungen gesetzt, sonst `400 consent_required`.
2. Vollständige Neuauswertung (derselbe Code wie `GET …/configuration`), Voraussetzungen prüfen.
3. Prüfstempel vergleichen (3.3): weicht er ab, `409 review_changed` mit `changes` und neuem Stempel; die Oberfläche lädt neu, zeigt die Änderung, der Kunde bestätigt erneut. Trägt die aktuelle Fassung schon diesen Stempel, endet der Aufruf hier mit ihr (Doppelklick, unten).
4. Abweichungen (3.4): bindende Verstöße ohne `deviations_acknowledged` → `409 deviations_not_acknowledged` mit den Prüfungen.
5. Kontakt: Ist der Kunde noch nicht bestätigt, braucht der Aufruf den Code aus `POST …/inquiry/contact` (A, unverändert) und prüft ihn wie A (Ablauf, Versuche, Hash). Erst nach Schritt 3 und 4, damit eine Ablehnung wegen geänderter Auswertung keinen Code verbraucht. Ein bestätigter Kunde (Vorgang besteht) braucht keinen Code.
6. Anlegen: Vorgang (falls neu, mit dem Snapshot aus A), vorige Fassung `superseded`, neue Fassung mit Snapshot, zwei Einwilligungen, Vorgang auf `neu`, Projekt `submitted`, Audit, Jobs `dossier_generate`, Mail an das Büro, Mail an den Kunden mit Zugangslink.
7. Antwort `201 {number, sequence, status}`.

**Doppelklick:** Hat die aktuelle Fassung denselben Prüfstempel (er enthält die Revision der Konfiguration), liefert der Aufruf sie zurück, ohne neue Fassung und ohne Mails. Die Sperre auf der Projektzeile ordnet gleichzeitige Aufrufe; der zweite sieht die erste Fassung. Ein `Idempotency-Key`-Kopf (Spez. 6.1) ist damit nicht nötig.

### 3.3 Prüfstempel (Neuprüfung beim Absenden)

`review_stamp` in `ConfigurationOut` (`null` ohne Typ): `v1:` und sechs Teile zu je 12 Hex-Zeichen, `name=hash` durch Punkte getrennt:

| Teil | Inhalt | erkennt |
|---|---|---|
| `site` | Umriss, Kanten mit Klasse und Herkunft, Gelände, Warnungen (Teil der G3-Prüfsumme) | Kantenkorrektur, eingetroffenes Gelände |
| `rules` | Zonen, Inhalt der Regeln und Hinweise, überlagernde Vorgaben, Status (Rest der G3-Prüfsumme) | neuer Planstand, Korrektur des Büros für Zone oder Projekt |
| `catalog` | Typversion und Status, Versionen und Status von Linie und Optionen, Version und Satz des Preiskatalogs | neuer Preiskatalog, zurückgezogene Version |
| `configuration` | Revision der Konfiguration | Änderung in einem anderen Fenster |
| `result` | Inhalt der Auswertung (Prüfungen, Flächen, Nebenbauten, Kosten, Energie, Himmelsrichtung, Zulässigkeit) | alles, was ohne Versionswechsel anders herauskommt (RE2020-Befund, Preiszeile) |
| `engine` | `ENGINE_VERSION` | neues Rechenwerk |

Gehasht wird der **Inhalt**, nie Zeitstempel oder IDs zufälliger Herkunft (wie G3). Listen gehen sortiert in den Hash (als Mengen), damit eine andere Reihenfolge aus einem anderen Prozess (zufällige Hash-Reihenfolge von Mengen in Python) keinen Wechsel vortäuscht. `selection.dropped` steht nur in der Antwort auf `PATCH` und bleibt draußen. Für Weg E entfällt `rules` (leer).

### 3.4 Abweichungen

Eine **Abweichung** ist eine bindende Prüfung mit `fail` in `fit.reasons`, `evaluation.checks` oder `compliance.checks`. `PATCH` speichert keine neuen (D12, HK08), nach einem Regel- oder Katalogwechsel können gespeicherte aber bestehen. Übergabe dann nur mit `deviations_acknowledged = true` („Mit Abweichungen zur Prüfung übergeben“, Spez. 5.10.2 Punkt 6); die Fassung speichert Bestätigung und Anzahl, das Büro sieht sie zuerst. `unknown` und Hinweise hindern nie und stehen im Dossier als offene Prüfpunkte. Die Anfrage an das Büro bleibt immer möglich (Plan 7, D11).

### 3.5 Einwilligungen

Zwei neue Rechtstexte statt einer neuen Version der A-Texte, weil sie mehr umfassen: `notice.design_confirmation` („unverbindliche Vorentwurfsskizze“, Kosten sind eine Schätzung, kein Vertrag, Simulation; Spez. 5.10.2 Punkt 4) und `consent.transmission_design` (Übermittlung von Kontakt und Projekt **einschließlich Konfiguration, Kostenschätzung und Dossier**; Punkt 5). Vorläufig wie AF05, veröffentlicht über `legal-seed`. Jede Fassung speichert ihre zwei Einwilligungen (`consent.submission_id`); die Eindeutigkeit „je Projekt und Art“ gilt nur noch für die Einwilligungen aus A (Teilindex). Der Name des Büros fehlt weiter (HANDOFF 3, Priorität 1).

### 3.6 Snapshot (Schema 2)

Selbsttragendes JSON je Fassung (Spez. 5.10.4): `schema_version = 2`, `number`, `sequence`, `submitted_at`, `locale`, `customer` (Kontakt, Baubeginn, Finanzierung, Lotissement), `consents` (Art, Schlüssel, Version, Zeit), `site` (`SiteOut`), `rules` (`ProjectRulesOut`), `envelope` (`EnvelopeOut`, bei Weg E mit `unavailable`), `configuration` (`ConfigurationOut` samt Auswertung), `catalog` (Kopien der benutzten Katalogstände: Typ mit Kennwerten und Status, Linie und Optionen mit Bezeichnungen, Art, Parametern, Material, Preiskatalog mit Version und Satz), `review_stamp`, `deviations`, `deviations_acknowledged`, `open_points`.

Abweichung von Spez. 5.10.4: Kopien nur der Felder, die Auswertung und Dossier benutzen; veröffentlichte Versionen sind ohnehin unveränderlich (L4), IFC-Pakete und Pläne gibt es nicht (Plan 7). Das Dossier entsteht **nur aus dem Snapshot**, ohne Datenbankabfrage; es ist damit jederzeit gleich wiederherstellbar.

### 3.7 Dossier

| Datei | Inhalt |
|---|---|
| `<Nummer>_F<n>_fr.pdf`, `…_de.pdf` | Kopf mit Nummer, Fassung, Datum und Hinweis „unverbindliche Simulation“ (L7); 1 Zusammenfassung (Typ, Linie, Optionen, Hinweis auf inzwischen zurückgezogene Versionen (Spez. 5.10.2 Punkt 2), Kennzahlen, Kostenkorridor „ca.“ mit „Schätzung, unverbindlich“, Zahl der Abweichungen und offenen Punkte, Bestätigung); 2 Kunde mit Einwilligungen; 3 Lageplan; 4 Standort (Parzellen, Genauigkeit, Kanten mit Herkunft, Gelände, Risiken); 5 Implantation (Lambert-93-Ursprung, Drehung, Abstände je Kante); 6 Regelprüfung mit Messwert, Grenze, Bindung, Seite und Zitat, Abweichungen zuerst; 7 Flächen; 8 Kosten (Posten, Korridor, Katalogstand, Mehrwertsteuersatz; kein Gesamtpreis, L1); 9 Energie; 10 Hinweise L7, Quellen und Lizenzen, Herkunft (Stempel, Rechenstände), Anlagen |
| `<Nummer>_F<n>_L93.dxf` | Lageplan in Lambert-93 (EPSG:2154), Meter; nur für Grundstücke aus dem Kataster |
| `<Nummer>_F<n>_local.dxf` | Derselbe Plan in lokalen Metern; Ursprung als Punkt und Text mit seinen Lambert-93-Koordinaten |

**Lageplan** (SVG im PDF, Ebenen im DXF): Grundstück, Nachbarparzellen und -gebäude, Kanten nach Art (Straße hervorgehoben), bebaubare Fläche weit und eng, Haus (Fassade, Überstand), Terrasse, Carport, Zufahrt, Nordpfeil (Gitternorden, Meridiankonvergenz als Text), Maßstabsleiste. Maßstab: der kleinste aus 1:200, 1:250, 1:500, 1:1000, 1:2000, bei dem das Grundstück samt Rand auf 170 × 120 mm passt (Spez. nennt 1:500). Weg E: kein Nordpfeil, Vermerk „ohne geografischen Bezug“, nur die lokale DXF-Datei.

**DXF-Ebenen** (französisch, weil das Büro in Frankreich arbeitet): `PARCELLE`, `LIMITE_VOIE`, `LIMITE_SEPARATIVE`, `LIMITE_FOND`, `LIMITE_AUTRE`, `VOISINS_PARCELLES`, `VOISINS_BATI`, `ZONE_CONSTRUCTIBLE_LARGE`, `ZONE_CONSTRUCTIBLE_STRICTE`, `MAISON_FACADE`, `MAISON_DEBORD`, `TERRASSE`, `CARPORT`, `ACCES`, `ORIGINE`, `TEXTE`. Einheit Meter (`$INSUNITS = 6`), Format R2010, geschlossene Polylinien.

**Quellenangabe (G17):** PDF und DXF tragen „Cadastre : DGFiP / Etalab (ODbL 1.0) · Voies : IGN BD TOPO (Licence Ouverte 2.0)“, bei Weg E entfällt sie.

**Erzeugung:** Job `dossier_generate` (bis 3 Versuche, 300 s) liest die Fassung, rendert, legt die Dateien unter `dossiers/<Projekt>/<Fassung>/` ab und schreibt Name, Art, Größe und SHA-256 in die Fassung (`dossier_status = ready`). Scheitert der letzte Versuch: `failed` mit Fehlertext, Log `dossier_failed` (Alarm in BETRIEB), im Büro ein Knopf „neu erzeugen“. Der Kunde merkt davon nichts; seine Fassung ist gespeichert (Spez. 5.10.3). Downloads laufen über die API: das Büro lädt alle Dateien, der Kunde die PDFs seiner Fassungen.

### 3.8 Zustände und Nachrichten

- Neue Fassung → `neu` (auch aus `geschlossen` oder `zurueckgezogen`: der Kunde kommt zurück).
- Büro setzt frei jeden Zustand außer `zurueckgezogen` (wie A 3.7, mit Audit).
- **Nachricht des Büros** → `rueckfrage`, wenn der Vorgang `neu` oder `in_bearbeitung` ist; Mail an den Kunden mit Text und Zugangslink.
- **Nachricht des Kunden** → aus `rueckfrage` wird `in_bearbeitung`; Mail an das Büro. Nicht möglich, wenn zurückgezogen (`409 inquiry_withdrawn`).
- **Zurückziehen** durch den Kunden → `zurueckgezogen`, Mail an das Büro; es wird nichts gelöscht (D6).
- Nachrichten: nur Text (1–4000 Zeichen), Verfasser `customer` oder `office` mit Mitarbeiterkennung, keine Anhänge; sie gehören zum Vorgang und gelten auch für Vorgänge aus A.

### 3.9 Zugang für den Kunden

- **Zugangslink** `…/zugang#t=<Token>` (im Fragment, damit er in keinem Serverlog steht): `base64url(Projekt-UUID + Ablauf)` und HMAC-SHA256 mit `secret_key` und Zweck `project_access`; 30 Tage gültig, ohne personenbezogene Daten (Spez. 5.10.7). Er steht in der Kundenmail der Übergabe, in jeder Nachricht des Büros und in der Kundenkopie von A.
- **Einlösen** (`POST /access/redeem`, öffentlich, begrenzt je IP): gültig, nicht abgelaufen, Projekt mit Vorgang → neues Zugangstoken, Cookie wie bei der Projektanlage, Audit. Weil nur der Hash des Tokens gespeichert ist, **ersetzt** das Einlösen das bisherige Cookie: andere Geräte verlieren den Zugang, bis sie den Link ebenfalls öffnen (Kapitel 8, E-V5).
- **Neuen Link anfordern** (`POST /access/request {email}`, öffentlich, begrenzt je IP und Adresse): Für jedes Projekt mit Vorgang und bestätigtem Kunden dieser Adresse geht eine Mail mit Link hinaus. Die Antwort ist immer `202`, damit niemand erfährt, ob eine Adresse bekannt ist.

### 3.10 Mails

Neue Vorlagen (de, fr): `submission_office` (Betreff `Vorentwurf <Nummer> · Fassung <n> · Parzelle <Kennung> · <Typ> / <Linie>`, Korridor, Abweichungen, offene Punkte, Link ins Büro-Portal), `submission_customer` (Nummer, nächste Schritte, Zugangslink), `message_customer`, `message_office`, `withdrawn_office`, `access_link`; `inquiry_customer_copy` (A) bekommt den Zugangslink. Wortwahl ohne Handelsbegriffe (L1). Sprache der Kundenmails aus `customer.locale` (neu, beim Kontakt und bei der Übergabe gesetzt); Büromails wie in A.

### 3.11 Flags, Rechte, Grenzen

- Flag `submission` für `POST …/submission` und den Knopf im Vorentwurf. „Mein Vorgang“ (Lesen, Nachricht, Zurückziehen, PDF) braucht `inquiry` **oder** `submission`, weil auch Vorgänge aus A Nachrichten bekommen. Zugangslink ohne Flag (öffentlich, wie Export und Löschung).
- Büro: `architect`, `rules_admin`, `ops` wie A.
- Rate-Limits: Übergabe 20/h je IP, Nachricht 30/h je IP, Einlösen 20/h je IP, Anfordern 5/h je IP und 3/h je Adresse.
- Export (Spez. 10.2) umfasst Fassungen (Snapshot, Dateinamen) und Nachrichten; Löschung und Aufbewahrung bleiben wie A (`409` nach einer Anfrage, D6).

## 4. Technik

### 4.1 Datenmodell (Migration 0011)

```
submission       id, project_id → project (CASCADE), inquiry_id → inquiry (CASCADE), sequence,
                 status ('current','superseded'), snapshot JSONB, snapshot_schema_version (2),
                 configuration_revision, review_stamp, deviations_acknowledged, deviation_count,
                 open_points, dossier_status ('pending','ready','failed'), dossier_files JSONB,
                 dossier_error, supersedes_id → submission, created_at, created_by, updated_at
                 UNIQUE (inquiry_id, sequence); UNIQUE (inquiry_id) WHERE status = 'current'
inquiry_message  id, inquiry_id → inquiry (CASCADE), author ('customer','office'), body, created_at,
                 created_by
consent          + submission_id → submission (CASCADE, NULL für A); Art + 'design_confirmation',
                 'transmission_design'; UNIQUE (project_id, kind) WHERE submission_id IS NULL;
                 UNIQUE (submission_id, kind) WHERE submission_id IS NOT NULL
inquiry.status   + 'rueckfrage', 'zurueckgezogen'
customer         + locale ('fr','de', Standard 'fr')
```

Abwärtskompatibel (Plan 6.5): nur neue Tabellen, Spalten mit Standardwert, erweiterte Prüfungen; die alte Eindeutigkeit wird zum Teilindex. Ein zurückgerolltes Image liest die neuen Zustände nicht (Anfragenliste scheitert) – in BETRIEB vermerkt.

### 4.2 Aufbau

- `app/configuration/review.py`: Prüfstempel (Teile, Vergleich), Abweichungen, offene Punkte; `ConfigurationOut.review_stamp`. `app/envelope/service.fingerprint_parts` teilt die G3-Prüfsumme in `site` und `rules`.
- Neues Modul `app/submission/`: `models`, `schemas`, `service` (Absenden, Snapshot, Katalogkopie, Fassungen fürs Büro), `api`, `texts` (vorläufige Rechtstexte), `jobs` (`dossier_generate`), `dossier/plan.py` (Geometrie des Lageplans aus dem Snapshot, Maßstab), `dossier/pdf.py` (HTML/SVG, WeasyPrint), `dossier/dxf.py` (`ezdxf`).
- `app/inquiry/`: Nachrichten, Zurückziehen, neue Zustände, Kundenansicht des Vorgangs, `access.py` (Zugangslink: Token, Einlösen, Anfordern), Export.
- Texte der Prüfungen für das PDF: Backend-Übersetzungen `check.*` (flach, `{param}`), erzeugt aus `configurator.check.*` und den zugehörigen Wörterbüchern des Frontends mit `tools/sync-check-texts.cjs`; neue Prüfcodes brauchen beide Stellen (README).

### 4.3 API

| Methode | Pfad | Zweck |
|---|---|---|
| POST | `/projects/{id}/submission` | Übergabe (3.2) |
| GET | `/projects/{id}/inquiry` | erweitert: Fassungen (Nummer, Status, Datum, Abweichungen, PDF-Dateien), Nachrichten, `can_withdraw` |
| POST | `/projects/{id}/inquiry/messages` | Nachricht des Kunden |
| POST | `/projects/{id}/inquiry/withdraw` | Zurückziehen |
| GET | `/projects/{id}/submissions/{n}/files/{name}` | PDF der eigenen Fassung |
| POST | `/access/redeem`, `/access/request` | Zugangslink einlösen, anfordern (öffentlich) |
| GET | `/admin/inquiries` | erweitert: Zahl der Fassungen, Abweichungen und Dossierstand der aktuellen |
| GET | `/admin/projects/{id}/inquiry` | erweitert: Fassungen mit Zusammenfassung aus dem Snapshot, Dateien, „seit der Übergabe geändert“, Nachrichten |
| PATCH | `/admin/projects/{id}/inquiry` | neue Zustände |
| POST | `/admin/projects/{id}/inquiry/messages` | Nachricht des Büros |
| GET | `/admin/projects/{id}/submissions/{n}/files/{name}` | alle Dateien |
| POST | `/admin/projects/{id}/submissions/{n}/dossier` | Dossier neu erzeugen (nur bei `failed`) |

`ConfigurationOut` bekommt `review_stamp`. Neue Problemcodes: `submission_incomplete`, `review_changed`, `deviations_not_acknowledged`, `inquiry_withdrawn`, `access_link_invalid`, `dossier_not_ready`, `file_not_found`.

### 4.4 Frontend

- **Vorentwurf:** Abschnitt „Vorentwurf übergeben“ statt des Verweises (ohne Flag bleibt der Verweis): Abweichungen mit Bestätigung, bei neuem Kunden Kontaktformular (aus A) und Code, sonst nur die zwei Bestätigungen; bei `review_changed` Neuladen und Hinweis, was sich geändert hat; danach Nummer, Fassung und Verweis auf `/vorgang`.
- **`/vorgang`:** Status, Fassungen mit PDF, Nachrichten mit Antwortfeld, Zurückziehen (mit Rückfrage); ohne Vorgang das Formular „Zugangslink anfordern“.
- **`/zugang`:** liest `#t=`, löst ein, leitet auf `/vorgang`; bei ungültigem Link Hinweis und Anforderungsformular.
- **Büro:** Anfrage-Detail mit Fassungen (aktuelle zuerst, Abweichungen hervorgehoben, Typ, Linie, Optionen, Korridor, Dossierstand, Downloads, „neu erzeugen“), Nachrichten mit Eingabe, erweiterten Zuständen; Anfragenliste mit Spalte „Vorentwurf“.

## 5. Arbeitsschritte

1. Migration 0011, Modelle, Rechtstexte (`legal-seed`), Einstellungen.
2. Prüfstempel, `fingerprint_parts`, `review_stamp` in `ConfigurationOut`; Einheitstests.
3. Übergabe (Dienst, API, Mails), Nachrichten, Zurückziehen, Zugangslink, Export, Büro-Endpunkte.
4. Dossier: Plan, PDF, DXF, Job, Downloads; Texte `check.*` übernehmen.
5. Tests (Einheit, Integration), `openapi.json`, Typen.
6. Frontend: Übergabe, `/vorgang`, `/zugang`, Büro; Komponententests.
7. Im Browser am lokalen Stack prüfen (AD 65 mit Linie, Terrasse, Carport; Mailpit; PDF und DXF ansehen).
8. Dokumentation: ANNAHMEN (VU), BETRIEB, README, Umsetzungsplan 3.10 und Kapitel 7, AGENTS.

## 6. Abnahme

Aus Umsetzungsplan 3.10:
- Durchlauf auf AD 65 (Typ, Linie, Terrasse, Carport) erzeugt beide PDFs und beide DXF-Dateien; das DXF liest `ezdxf` zurück, die Ebenen sind da, der Hausumriss liegt in der L93-Datei bei lokal + Ursprung.
- Eine zwischen Anzeigen und Absenden geänderte Regel (Korrektur für das Projekt) wird erkannt: `409 review_changed` mit `rules`; mit dem neuen Stempel geht die Übergabe durch.
- Eine Neuübergabe setzt die vorige Fassung auf `superseded`; es gibt nie zwei aktuelle.
- Das Büro übernimmt den DXF-Lageplan nach beschriebenem Vorgehen lagerichtig in ArchiCAD: Vorgehen in BETRIEB beschrieben; **nur vom Büro prüfbar** (offen).

**Ergebnis der Abnahme (19.09.2026):** alle Punkte durch Tests belegt, dazu der Durchlauf im Browser auf AD 65 (Ligne Demo mit Linie Base, Terrasse und Carport): Kontakt, Code aus Mailpit, Übergabe → Vorgang EMP-2026-000002 Fassung 1, beide PDFs (4 Seiten, Lageplan 1:500) und beide DXF-Dateien in 3,7 s erzeugt, Büro-Mail mit Korridor und Abweichungen, Kundenmail mit Zugangslink; Nachricht des Büros → `rueckfrage` und Mail, Antwort des Kunden → `in_bearbeitung`; Zugangslink eingelöst (neues Cookie) und PDF-Download 200; Regeländerung zwischen Anzeigen und Absenden → `review_changed` mit `rules` und `result`, danach Fassung 2, Fassung 1 `superseded`, Vorgang wieder `neu`. Gemessen: Übergabe 0,8–1,0 s (409 in 0,6 s), Dossier-Job 2,2–3,7 s, Snapshot 17,5 KB; der Prüfstempel kostet 1–2 ms je Abruf (`GET …/configuration` liegt im Container bei rund 0,5 s, aus H2/H3). Die DXF-Dateien sind mit `ezdxf` zurückgelesen (Ebenen, Lambert-93 = lokal + Ursprung), **nicht** in ArchiCAD.

Zusätzlich: Doppelklick erzeugt eine Fassung; Abweichungen verlangen die Bestätigung; ohne Einwilligungen `400`; Vorgang aus A bekommt eine Fassung ohne Code und steht wieder auf `neu`; neuer Kunde braucht den Code, eine Ablehnung wegen geänderter Auswertung verbraucht ihn nicht; Nachrichten ändern die Zustände wie in 3.8; Zurückziehen; Zugangslink: gültig → Cookie gewechselt, gefälscht oder abgelaufen → abgewiesen; Anfordern verrät nicht, ob die Adresse bekannt ist; Export enthält Fassungen und Nachrichten; Rechte und Flags; kein Gesamtpreis im Snapshot (L1); Weg E ohne L93-Datei. Leistung: Übergabe unter 2 s, Dossier-Job unter 30 s (lokal gemessen).

## 7. Risiken

- **Vorläufige Rechtstexte** und fehlender Name des Büros (wie AF05); die Kennzeichnung als Simulation steht auf jeder Seite des PDFs.
- **Mailanbieter (E2) offen**, Sammelpostfach `EMPRISE_OFFICE_EMAIL` noch Platzhalter und auf Unraid nicht verdrahtet (HANDOFF 4.7): lokal über Mailpit.
- **Zugangslink** gilt 30 Tage für jeden, der die Mail hat (Spez. 5.10.7 nimmt das hin); er wechselt das Cookie.
- **ArchiCAD** ist nicht verfügbar; die DXF-Dateien sind mit `ezdxf` geprüft, nicht im Zielprogramm.
- **Texte der Prüfungen doppelt** (Frontend und Backend); das Werkzeug gleicht ab, ein Test der Oberfläche liest die Backend-Übersetzungen und meldet Abweichungen (der Backend-Container sieht das Frontend nicht).

## 8. Festlegungen mit Empfehlung

| Nr. | Frage | Empfehlung (genommen) | Besser, wenn … |
|---|---|---|---|
| E-V1 | Eigene Tabelle je Fassung oder Snapshot der Anfrage überschreiben? | `submission` je Fassung, Vorgang bleibt `inquiry` (3.1) | – (Überschreiben verlöre die gespeicherte Fassung, L4) |
| E-V2 | Zustände: Spez. 5.10.1 wörtlich (englisch, Zustandsautomat) oder A erweitern? | A um `rueckfrage` und `zurueckgezogen` erweitern, frei für das Büro | das Büro einen festen Ablauf mit Fristen will (Plan 8) |
| E-V3 | Konfiguration nach der Übergabe sperren? | Nein; Änderungen erreichen das Büro als neue Fassung | das Büro auf der Live-Konfiguration arbeiten soll |
| E-V4 | Neuprüfung über Versionsnummern oder Inhalt? | Inhalt, in sechs benannten Teilen (3.3) | – (Versionsnummern übersehen Gelände, Projektkorrekturen, Befunde) |
| E-V5 | Zugangslink: Cookie ersetzen oder mehrere Zugangstoken je Projekt? | Ersetzen (kein neues Tabellenmodell) | Kunden oft mehrere Geräte gleichzeitig nutzen – dann Tabelle `project_access` |
| E-V6 | Sprache des Dossiers | beide Sprachen (zwei PDFs, ein Renderer) | das Büro sich auf eine Sprache festlegt |
| E-V7 | Linie Pflicht? | nur, wenn der Katalog Linien für den Typ anbietet (3.2) | – |
| E-V8 | Dossier bei Fehler: Mail an Betrieb und Büro (Spez. 5.10.3)? | Log-Alarm und Anzeige im Büro, keine Mail | ein Mailanbieter feststeht und das Büro Mails wünscht |

## 9. Prüfprotokoll

### 9.1 Befunde beim Entwurf

| Nr. | Befund | Folge |
|---|---|---|
| 1 | Die Eindeutigkeit `consent (project_id, kind)` aus A hätte jede zweite Fassung mit einem Integritätsfehler abgewiesen | Teilindizes je Herkunft (4.1) |
| 2 | Plan A 3.4 sagt „V erweitert dieselbe `inquiry`-Zeile“; wörtlich genommen hätte der Snapshot der Anfrage bei jeder Neuübergabe überschrieben werden müssen – die übergebene Fassung wäre verloren (L4) | Vorgang und Fassung getrennt (3.1, E-V1) |
| 3 | Code vor der Neuprüfung geprüft: Eine Ablehnung wegen geänderter Auswertung hätte den einmaligen Code verbraucht, der Kunde müsste einen neuen anfordern | Code erst nach Stempel und Abweichungen (3.2 Schritt 5) |
| 4 | `selection.dropped` steht nur in der Antwort auf `PATCH`; die Oberfläche übernimmt diese Antwort als Stand. Mit im Hash hätte die erste Übergabe nach einem Typwechsel immer `review_changed` gemeldet | Aus dem Hash genommen (3.3) |
| 5 | Listen aus Mengen haben in Python je Prozess eine andere Reihenfolge (zufälliger Hash-Startwert); bei zwei API-Prozessen hätte derselbe Stand zwei Stempel gehabt | Listen gehen sortiert in den Hash (3.3) |
| 6 | Doppelklick ohne Code (Kunde schon bestätigt) hätte zwei Fassungen und zwei Mailpaare erzeugt; A war nur durch den einmaligen Code geschützt | Gleicher Stempel → bestehende Fassung; Sperre auf der Projektzeile (3.2) |
| 7 | Die Neuübergabe eines geschlossenen oder zurückgezogenen Vorgangs wäre beim Büro unsichtbar geblieben | Jede neue Fassung setzt den Vorgang auf `neu` und schickt die Büromail (3.8) |
| 8 | Weg E hat einen lokalen Ursprung ohne geografische Bedeutung (G27); eine L93-Datei hätte eine falsche Lage vorgetäuscht | Nur die lokale Datei, Vermerk im PDF (3.7) |
| 9 | Nachrichten brauchen einen Rückweg des Kunden; das Cookie gilt 90 Tage ab Anlage und wird nie erneuert (AF12) | Zugangslink mit Anforderung (3.9) |
| 10 | Nachrichten auch zu Vorgängen aus A: mit Flag nur `submission` erreichte ein A-Kunde seine Nachricht nicht | „Mein Vorgang“ mit `inquiry` oder `submission` (3.11) |
| 11 | Ein erneuter Dossier-Job mit demselben Idempotenzschlüssel liefe nicht an (`enqueue` gibt den alten, gescheiterten Job zurück) | Neu erzeugen mit eigenem Schlüssel je Auftrag (3.7) |
| 12 | Die Konfigurationsseite rechnete die Abweichungen nur als Hinweis; ohne eigene Zählung hätte das Büro die Kennzeichnung „zuerst“ (Spez. 5.10.2) nicht in der Liste | `deviation_count` an der Fassung, Spalte in der Liste (4.1, 4.4) |
| 13 | Der Token im Query-String stünde im Zugriffslog von Caddy und im Referer | Token im Fragment, Einlösen per `POST` (3.9) |
| 14 | Der erste Entwurf wollte im Backend testen, dass jeder Prüfcode übersetzt ist; der Backend-Container sieht die Texte des Frontends nicht, und die Prüfcodes stehen verstreut im Rechenwerk | Abgleich als Test der Oberfläche gegen die Backend-Übersetzungen (7) |

### 9.1a Befunde beim Bau

| Nr. | Befund | Folge |
|---|---|---|
| 15 | `fingerprint_parts` gab die vollen 64 Hex-Zeichen der G3-Prüfsumme zurück; der Stempel wurde 200 Zeichen lang und die Übergabe scheiterte an der Schemaprüfung (`422 string_too_long`) | Teile auf 12 Zeichen gekürzt wie die übrigen (3.3); Integrationstest über die Länge und die Namen der Teile |
| 16 | **Im Browser:** Das Dossier zeigte die Standortrisiken als Rohtext von Géorisques („Risque Existant (present)“) ohne die Art des Risikos, weil nur `label` benutzt wurde | `risk.kind.*` und `risk.level.*` zusätzlich aus dem Frontend übernommen (VU12); Einheitstest auf „Schrumpfen und Quellen toniger Böden: mittel“ |
| 17 | **Im Browser:** Die Menge der Terrasse stand als „36,0 m2 × 480 €“ im PDF (Einheit aus der API) | Einheiten `m2`/`m3` werden für die Anzeige zu `m²`/`m³` |
| 18 | Der Abgleichstest der Prüftexte las die Backend-Datei über `new URL(…, import.meta.url)`; Vite macht daraus einen Asset-Import und verweigert Pfade außerhalb des Frontends (`Denied ID`) | Pfad über `process.cwd()` (vitest läuft im Ordner `frontend`) |
| 19 | Beim Abgleich fiel auf, dass `problem.revision_conflict` in den Backend-Übersetzungen doppelt stand (G1 und H2); JSON behält den letzten, deshalb meldete auch das Grundstück „Die Konfiguration wurde geändert“ | Ein neutraler Text für beide Fälle (VU16) |
| 20 | Nach `review_changed` lädt die Oberfläche alle Abfragen des Konfigurators neu (Typen, Optionen, Fläche); im Browser dauerte der Abruf der Konfiguration dabei einmal 4,5 s | Belassen: die Typen können sich mit den Regeln ebenfalls geändert haben. Grenze in 9.3 vermerkt |

### 9.2 Geprüfte Alternativen

- **Übergabe über A (`inquiry/confirm`) erweitern** statt eines eigenen Endpunkts: verworfen; A darf ohne Konfiguration funktionieren (D14), und der Ablauf mit Stempel, Abweichungen und bestätigtem Kunden ohne Code ist ein anderer.
- **Dossier aus der Datenbank neu rechnen** statt aus dem Snapshot: verworfen; das Dossier muss die übergebene Fassung zeigen, nicht den heutigen Stand.
- **Mehrere Zugangstoken je Projekt** (E-V5): verworfen für jetzt; ein Gerätewechsel ist selten, der Link steht in jeder Mail.
- **Prüftexte generisch im PDF** („Code: gemessen, Grenze“): verworfen; das Büro liest das Dossier, die Texte existieren schon im Frontend.
- **PDF nur in der Sprache des Kunden:** verworfen (E-V6); das Büro arbeitet französisch, der Kunde vielleicht deutsch.
- **Ein DXF mit zwei Koordinatensystemen (Block in lokalem System):** verworfen; zwei Dateien sind für CAD-Nutzer eindeutiger.

### 9.3 Grenzen

- **Kein Playwright-Szenario** für den Weg Konfigurator → Übergabe → Vorgang; es fehlt schon für H2 und H3 und bräuchte zusätzlich Katalog-Seed, Rechtstexte und den Code aus Mailpit in der CI (HANDOFF 4.1).
- **DXF nur mit `ezdxf` geprüft**, nicht in ArchiCAD; das Vorgehen steht in BETRIEB 14 und muss das Büro bestätigen.
- Das Dossier ist der gekürzte Umfang aus Plan 3.10: kein IFC, keine Mengen-XLSX, keine gestempelten Pläne, keine Ansichten, kein ZIP (X4); keine Webhooks (X5); keine Anhänge an Nachrichten.
- Der Lageplan im PDF zeichnet die Nachbarschaft ohne Beschriftung und ohne Maßketten; Maße stehen als Tabelle daneben.
- Nach `review_changed` lädt die Oberfläche den ganzen Konfigurator neu (9.1a Nr. 20).
- Die Rechtstexte sind vorläufig, der Name des Büros fehlt; die Kundenmails gehen in der Sprache der Übergabe hinaus, Büromails ebenfalls (wie A).
