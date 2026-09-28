# G2 – Vollständige Regelauswertung (Nachsuche, Abdeckung, Referenzlisten)

> **Status:** geplant und umgesetzt am 28.09.2026: A, D1, B1–B3, Probelauf E (Ergebnis in 7.5), C und D2; auf Unraid noch nicht ausgeliefert (gemeinsamer Stack einrichten, `deploy/unraid/README.md` 10) · **Bezug:** [PLAN_AN2_PLU.md](PLAN_AN2_PLU.md) 9 (Modellvergleich), `BACKEND_SPEZIFIKATION.md` 5.2.3–5.2.4, UMSETZUNGSPLAN 3.4 (G2) · **Festlegungen:** `docs/ANNAHMEN.md` Abschnitt „G2 – Vollständigkeit“ (Präfix `VA`)
> **Voraussetzung:** G2 mit Gegenprüfung (RW19), Zitatprüfung mit Auslassungen (RW24), AN4 (Regelformular, Korrektur mit Status und Begründung, KR01–KR02), Modellwahl (PU11), Text statt PDF (PU12).

---

## 1. Zweck und Umfang

Der Modellvergleich am Kapitel UC von „PLU Beyenes“ (PLAN_AN2_PLU 9) zeigt: Jedes Modell übersieht Vorschriften, und keins meldet, was. Der Nutzer will ein Produkt, das **alle** Regeln erkennt, nicht möglichst viele (28.09.2026). Ziel: Jede Vorschrift des Kapitels ist am Ende einer Regel zugeordnet, belegt nicht geregelt oder für den Architekten **sichtbar offen, mit Grund** – keine stillen Lücken, messbar an Referenzlisten.

**Enthalten:**
- **Anweisung nachschärfen:** Auslassungen in Zitaten erlauben (die Prüfung kann sie, RW24), bedingte und gestaffelte Werte nie auf eine Zahl verkürzen.
- **Rückfall beim Funktionsaufruf:** Modelle ohne erzwungenen Funktionsaufruf (Opus 5.5) laufen mit `tool_choice: auto`.
- **Abdeckung der Textstellen:** jede Stelle mit Vorschriftscharakter wird einer Regel zugeordnet oder als offen gezählt und angezeigt.
- **Nachsuche:** automatischer dritter Aufruf nach Auswertung und Gegenprüfung, gezielt für die Lücken, mit Alternativbezeichnungen und Zusatzseiten aus dem ganzen Dokument; Funde durchlaufen Schranken und Gegenprüfung.
- **Gemeinsame Verwaltung für beide Produkte:** eigene Datenbank für programmweite Daten; die Wahl des KI-Modells zieht dorthin.
- **Referenzlisten:** Soll-Listen je Dokument und Zone, von Hand pflegbar in der Verwaltung, nicht an ein Büro gebunden; Messung jeder Auswertung daran. Erste Liste: Beyenes UC.

**Nicht enthalten:** gestaffelte Grundflächenzahl im Regelschema (eigener Punkt; bis dahin `text_only`, E-VA-4); Denkaufwand `xhigh`/`max` durchreichen; Alternativbezeichnungen in der Verwaltung pflegen (E-VA-2); Nachsuche für Zusatzdokumente (E-VA-1).

## 2. Befund

| Baustein | Stand | Folge |
|---|---|---|
| Anweisung (`rules/domain/extraction.py`) | „If a matter is not addressed at all, omit the rule“; „No paraphrase, no ellipsis“ | „steht nicht drin“ und „übersehen“ sind nicht zu unterscheiden; zusammengesetzte Zitate scheitern (Kimi, DeepSeek: Höhe, Dach, Fassade), obwohl `_quote_similarity` Auslassungen prüft |
| `complete()` (`assess.py`) | ergänzt fehlende Pflichtarten als `unknown/missing` | keine Suche, kein Hinweis, wo gesucht wurde |
| Regelarten (`kinds.py`) | 15 Arten, `MaxFootprintRatio.ratio` nur ein Wert | Staffel → Pauschalwert 0,9 (Opus 5, Kimi); Vorschriften außerhalb der Arten (Höhengrenze auf der Grenze, Bauverbot am Wasserlauf) fallen still weg |
| Seitenauswahl (`chapters._general_pages`) | Kapitel + höchstens 40 allgemeine Seiten nach Stichwörtern | Verweise auf Lexique, Annexes, andere Abschnitte bleiben unverfolgt |
| Funktionsaufruf (`openrouter.py`) | `tool_choice` erzwingt die Funktion | Opus 5.5 lehnt ab (400 bei allen Anbietern), die Modellliste zeigt das nicht; wählbar im Dialog, scheitert aber |
| Modellwahl (`model_choice.py`, PU11) | `app_setting` je Instanz, Dialog auf der Startseite der Analyse | eine Einstellung je Datenbank, nicht für beide Produkte |
| Maßstab | Referenzmenge offen (RW18) | „alle“ ist nicht prüfbar |

## 3. Fachliche Festlegungen

### 3.1 Anweisung
- **Zitate:** Nicht zusammenhängende Sätze derselben Stelle dürfen mit „…“ verbunden werden; Abschnitte in Reihenfolge, höchstens 600 Zeichen auseinander, jede Zahl in einem Abschnitt von mindestens acht Zeichen (so prüft `_quote_similarity`, RW24).
- **Keine Pauschalwerte:** Hängt ein Wert von einer Bedingung ab (Grundstücksgröße, Lage auf dem Grundstück, Staffel; Unterschiede nach Baukörper bildet `building_kind` ab), wird er nicht auf eine Zahl verkürzt: `text_only` mit Zusammenfassung. Ohne Nachsuche bleibt die Regelart dann `missing` (sicher), mit Nachsuche wird sie `not_expressible` (3.7).
- `PROMPT_VERSION` → `g2-prompt-5`; die Prüfsumme (`prompt_fingerprint`) ändert sich, die Kapitel werden bei der nächsten Auswertung neu ausgewertet.

### 3.2 Rückfall beim Funktionsaufruf
Antwortet OpenRouter mit 400 und einer Meldung, die `tool_choice` nennt, wiederholt `OpenRouterExtractor.extract` den Aufruf **einmal** mit `tool_choice: "auto"` und dem Satz „Return your result only by calling the tool <name>.“ am Ende des Systemprompts. Ruft das Modell die Funktion dann nicht auf, bleibt der bestehende Fehler `no_text`. Kosten des abgelehnten Aufrufs: keine (sofortige Ablehnung). Der Rückfall hängt nicht am Modellnamen, sondern an der Meldung – so gilt er auch für künftige Modelle.

### 3.3 Abdeckung der Textstellen (`rules/domain/passages.py`, rein)
- **Stellen:** Die Kapitelseiten (Textschicht aus `source_page`) werden in Sätze und Aufzählungspunkte zerlegt (Satzende vor Großbuchstaben, Zeilen mit „-“, „•“, „13.1 -“, Artikelüberschriften als Grenze). Stellen unter 25 Zeichen (Beschriftungen von Skizzen, Kopfzeilen) zählen nicht.
- **Vorschriftscharakter:** eine Zahl mit Einheit (m, m², %, °, place, arbre, logement) oder ein Normwort (doit, doivent, interdit, autorisé, admis, au moins, au maximum, minimum, ne peut, ne doit, sont soumis, est limité). Kopfzeilen mit Seitenzahl ohne Einheit fallen damit heraus.
- **Zugeordnet:** Eine Stelle ist zugeordnet, wenn Zitate von Regeln (jeder Status, auch `unknown` mit Zitat) mindestens die Hälfte ihrer Zeichen in der Vergleichsform (`normalize`) überdecken; die Lage der Zitate im Seitentext kommt aus `partial_match` wie bei der Zitatprüfung.
- **Ergebnis:** gesamt, zugeordnet, außerhalb des Umfangs (nach der Nachsuche), offen; offene Stellen mit Seite und Text (höchstens 500 Zeichen je Stelle). An die Nachsuche gehen höchstens 60 offene Stellen, solche mit Zahl zuerst.
- Allgemeine Seiten liefern keine Stellen (sie gelten für alle Zonen); für sie gilt die Suche nach Begriffen (3.4).

### 3.4 Alternativbezeichnungen und Zusatzseiten (`rules/domain/lexicon.py`)
- **Begriffe je Regelart und Baukörper**, französisch, mit üblichen Artikeln alter PLU (Art. 6–13) und den Abschnitten modernisierter PLU („Volumétrie et implantation des constructions“, „Qualité urbaine, architecturale, environnementale et paysagère“, „Traitement environnemental et paysager des espaces non bâtis“, „Stationnement“). Beispiele: Grundfläche – emprise au sol, CES, coefficient d'emprise, surface bâtie; unversiegelt – espaces libres, pleine terre, non imperméabilisé, coefficient de biotope, CBS, surface éco-aménageable; Seitenabstand – limites séparatives, retrait, prospect, H/2, L = H/2; Zaun – clôture, haie, mur de clôture, portail; Nebengebäude – annexe, abri de jardin, garage, carport; Pool – piscine, bassin.
- **Suche** in der Vergleichsform ohne Akzente über die Textschicht des **ganzen** Dokuments (alle `source_page` der Datei): Begriffe der Lücken und Verweise im Kapitel („article X des dispositions générales“, „titre I“, „lexique“, „annexe n°“, „voir … page“). Seiten außerhalb der schon gesendeten werden **Zusatzseiten**, nach Anzahl der Treffer, höchstens `rules_gap_extra_pages_max` (Vorgabe 15).
- Die Begriffsliste gehört zur Prüfsumme der Eingabe (über `prompt_fingerprint`): Eine Ergänzung wertet neu aus.

### 3.5 Lücken (deterministisch, nach der Gegenprüfung)
1. Jede Pflichtart des Hauptgebäudes ohne `effective`, `not_regulated` oder zugeordneten Hinweis.
2. Jede weitere Art und jeder Baukörper (`annex`, `pool`), deren Begriffe im Kapitel oder auf den allgemeinen Seiten vorkommen, ohne Regel dazu (Zaun, Stellplätze, Bepflanzung, Abstand zwischen Gebäuden, Nebengebäude, Pool).
3. Jede Regel `unknown` mit Zitat (`quote_unverified`, `runs_disagree`, `value_not_in_quote`, `ambiguous`, `sector_mismatch`) – mit bisherigem Befund (Grund, Zitat, Werte), damit das Modell ihn berichtigen kann.
4. Die offenen Textstellen (3.3).

Ohne Lücken entfällt die Nachsuche.

### 3.6 Nachsuche (Lauf 3)
- **Anfrage:** dieselben Dokumente wie Lauf 1 (PDF oder Text) und als drittes Dokument die Zusatzseiten (`extra.pdf`, `document: "extra"`). Aufgabe `GAP_TASK`: je Lücke Art, Baukörper, Sektor, Alternativbezeichnungen, bisheriger Befund; je Textstelle Seite und Text. Das Modell soll unter allen Bezeichnungen, in den allgemeinen Bestimmungen, im Lexique und auf den Zusatzseiten suchen, Verweisen folgen und nichts aus Allgemeinwissen ergänzen.
- **Antwort `GAP_SCHEMA`:** je Lücke `found` (Regel im Format von Lauf 1, Zitat mit Auslassungen erlaubt), `not_expressible` (Zitat und Zusammenfassung: die Vorschrift gibt es, das Schema kann sie nicht abbilden), `absent` (geprüfte Stellen und Begriffe); je Textstelle `assigned` (Regel), `text_only` (Hinweis) oder `out_of_scope` (Begründung: öffentliche Einrichtungen, Gewerbe, Landwirtschaft, Bestand, Sonderfall).
- **Bewertung:** Funde laufen durch `assess_rule` (`DocumentPages.extra` für die Seitenzuordnung) und durch die Gegenprüfung `_verify` (nur die neuen Funde, eigene Nummern ab Lauf-1-Anzahl + 1, eigener Teil `verify:<Prüfsumme>`).
- **Zusammenführen (`fill_gaps`):** Ein bestätigter Fund für einen **Lückenschlüssel** ersetzt die offene Regel. Ein Fund für einen Schlüssel, der keine Lücke war (aus einer Textstelle), geht mit der vorhandenen Regel durch `collapse`: gleiche Werte → eine Regel, andere Werte → `ambiguous` (zwei Aussagen im Dokument; der Architekt entscheidet). Funde, die Schranken oder Gegenprüfung nicht bestehen, ändern nichts; die Lücke bleibt mit ihrem Grund.
- **Aufrufe:** Teil `gaps:<Prüfsumme der Lückenliste>`, `run_no` 3, über `_Calls.run` (Budget, Zeitbudget, Wiederverwendung, `max_tokens` → Lücken halbieren wie `_verify`). Höchstens eine Nachsuche je Auswertung. Eine Neubewertung ohne Aufruf (neue `ENGINE_VERSION`) ruft die Nachsuche nur, wenn sich die Lückenliste geändert hat.
- **Einstellungen:** `rules_gap_search` (Vorgabe an), `rules_gap_extra_pages_max` (15); beide gehören zu `input_hash`.
- **Umfang:** nur `document_kind == "plu"` (E-VA-1).

### 3.7 Ergebnis
- **Neue Gründe für `unknown`** (wirken nicht in der Simulation, D11): `not_found_after_search` (Detail: gesuchte Begriffe und die vom Modell genannten Stellen, gekürzt) und `not_expressible` (Detail: Seite; der Hinweis steht als `text_only` daneben).
- **Nicht gefundene Pflichtangaben** bleiben offen; der Architekt bestätigt sie über die Korrektur je Projekt (AN4, Status `not_regulated`, Begründung Pflicht) – Entscheidung des Nutzers 28.09.2026.
- **Speichern:** `rule_set_version.coverage` erhält `passages_total`, `passages_assigned`, `passages_out_of_scope`, `passages_open`, `gap_search` (`none` | `done` | `skipped`); neue JSONB-Spalten `open_passages` und `out_of_scope_passages` (Seite, Text, bei letzteren Begründung) – Migration 0017 in beiden Instanzen.

### 3.8 Oberfläche
- **Analyse-Projektseite und Büro-Regelwerk:** Zeile „Abdeckung: 46 von 48 Vorschriften zugeordnet, 2 offen“; aufklappbar die offenen Stellen und die als „betrifft kein Einfamilienhaus“ eingestuften, je mit Seite (Link `#page=`).
- **Regel mit `not_found_after_search`:** gesuchte Begriffe und die Schaltfläche „als nicht geregelt bestätigen“ – öffnet das AN4-Formular mit Status `not_regulated` (Begründung vom Architekten).
- Texte de/fr für die neuen Gründe.

### 3.9 Gemeinsame Verwaltung für beide Produkte
- **Datenbank `emprise_shared`** auf demselben Postgres (die Analyse nutzt schon den `db` des Hauptstacks). Verbindung `EMPRISE_SHARED_DATABASE_URL` / `EMPRISE_SHARED_MIGRATION_DATABASE_URL`; beide Stacks zeigen auf dieselbe Datenbank. Angelegt per Init-Schritt wie `db-init-analyse`.
- **Eigene Alembic-Umgebung** `backend/migrations_shared/` mit eigener Versionstabelle und Advisory-Lock (beide Migrate-Jobs können gleichzeitig laufen). Nur erweiternde Migrationen: Ein älteres Image verträgt ein neueres Schema; ist die Datenbank einer Instanz voraus, meldet der Migrate-Job das und bricht nicht ab.
- **Tabellen:** `shared_setting` (key, value JSONB, updated_at, updated_by), `shared_audit` (Zeitpunkt, Konto, Instanz, Aktion, Objekt, vorher/nachher), Referenzlisten (3.10). Konten liegen je Instanz: `updated_by` speichert Kennung und Anzeigenamen ohne Fremdschlüssel.
- **KI-Modell:** `model_choice` liest und schreibt `shared_setting`; eine vorhandene Zeile in `app_setting` wird übernommen, solange `shared_setting` leer ist; `app_setting` entfällt in einer späteren Migration. Endpunkte bleiben `/admin/rules/model(s)`. Die Wahl gilt damit für Konfigurator und Analyse; ohne Eintrag gilt die Umgebung des jeweiligen Stacks.
- **Verwaltungsbereich:** gemeinsame Komponenten `frontend/src/verwaltung/`, eingehängt im Konfigurator unter `/verwaltung` (eigenes Layout, Link im Büro für `ops` und `rules_admin`) und in der Analyse unter `/verwaltung` (Link im Kopf). Seiten „KI-Modell“ (die heutige `ModellWahl`; die Startseite der Analyse zeigt nur noch das Modell) und „Referenzlisten“. Lesen und Schreiben: `ops`, `rules_admin`.
- **Betrieb:** Sicherung und Wiederherstellung umfassen `emprise_shared` (`deploy/unraid/compose.yaml` Dienst `backup`, BETRIEB).

### 3.10 Referenzlisten und Messung
- **Tabellen:** `reference_list` (id, `document_sha256`, Dokumenttitel, Seitenzahl, Zone bzw. Sektor, Status `draft`/`checked`, Notiz, Zeitstempel, Bearbeiter); `reference_entry` (Art, Baukörper, erwarteter Status `effective`/`not_regulated`/`text_only`/`graphic_reference`, Parameter geprüft mit `validate_params`, Seite, Zitat, Notiz).
- **Messung (`rules/domain/reference.py`, rein)** gegen die aktuelle Regelwerksversion **dieser** Instanz (zugeordnet über `document_sha256` und Sektor): je Eintrag `hit` (Status und Werte gleich, `params_equal`), `wrong_value` (wirksam mit anderen Werten), `named_gap` (Regel `unknown` mit Grund – sichtbar), `silent_gap` (keine Regel, kein Hinweis und keine offene Stelle dazu). Hinweise (`text_only`) werden über die Überdeckung der Zitate auf derselben Seite zugeordnet. Dazu `extra`: wirksame Regeln ohne Eintrag (Liste unvollständig oder Fehlfund). Kennzahlen: Trefferquote; `wrong_value` und `silent_gap` sollen 0 sein.
- **API** (beide Backends): Listen anlegen, lesen, ändern, löschen; Einträge anlegen, ändern, löschen; „aus Auswertung übernehmen“ (Entwurf aus der aktuellen Version); Messung (sonst „hier nicht ausgewertet“); Export und Import als JSON.
- **Oberfläche:** Liste (Dokument, Zone, Status, Einträge, letzte Messung) und Detail (Einträge im AN4-Regelformular aus `GET /admin/rule-kinds`, übernehmen, „geprüft“, Export, Import, Messung).
- **Beyenes UC:** Entwurf aus dem Originaltext (S. 9–20) und den bisherigen Läufen, mit Staffel der Grundfläche (Hinweis), Bauverbot am Wasserlauf, Höhengrenze auf der Grenze; Datei `backend/app/rules/reference_seed/beyenes_uc.json`, geladen über Import bzw. CLI `reference-import`. Der Nutzer prüft sie und setzt sie auf „geprüft“.

## 4. Arbeitsschritte

| Schritt | Inhalt | Abhängig von |
|---|---|---|
| A | Anweisung (3.1), Rückfall `tool_choice` (3.2), Tests | – |
| D1 | Referenzliste Beyenes UC als Datei, Messfunktion `reference.py`, CLI `reference-check` gegen eine Datenbank (ohne Verwaltung) | A |
| B1 | `passages.py`, `lexicon.py` mit Einheitstests am Seitentext von Beyenes (Fixture) | – |
| B2 | Lücken, `GAP_TASK`/`GAP_SCHEMA`/`parse_gaps`, drittes Dokument, Lauf 3, `fill_gaps`, Gründe; Integrationstests mit Fake-Extractor | B1 |
| B3 | Migration 0017, API, Oberfläche, Texte | B2 |
| E | Probelauf in `emprise_probe` (Opus 5.5 PDF ohne und mit Nachsuche), Messung gegen D1 – **kostenpflichtig, nur nach Freigabe** | A, B2, D1 |
| C | gemeinsame Datenbank, Migrationen, Modellwahl umziehen, Verwaltungsbereich | – |
| D2 | Referenzlisten in `emprise_shared`, API, Verwaltung, Import der Datei aus D1 | C, D1 |

Nach jedem Schritt: Prüfbefehle aus dem README, Dokumente (ANNAHMEN `VA`, BETRIEB, README-Stolperstellen) nachziehen.

## 5. Abnahme

1. Ein Zitat mit „…“ über zwei Sätze derselben Stelle wird belegt; ein Pauschalwert aus einer Staffel entsteht nicht mehr (Fake-Antwort mit `text_only`).
2. Opus 5.5 wertet über den Rückfall aus (Fake-Client: 400 → zweiter Aufruf mit `auto`).
3. Lücke → Fund → wirksam; Lücke → `absent` → `not_found_after_search` mit Begriffen; offene Stelle → `out_of_scope` mit Begründung; Fund gegen wirksame Regel mit anderem Wert → `ambiguous`.
4. Abdeckung und offene Stellen stehen an der Version und in der Oberfläche beider Produkte.
5. Die Modellwahl in einer Instanz gilt in der anderen; Referenzliste anlegen, messen, exportieren, importieren.
6. **Probelauf Beyenes UC:** `wrong_value` = 0 und `silent_gap` = 0; Trefferquote und Kosten mit und ohne Nachsuche im Prüfprotokoll.

## 6. Offene Festlegungen (mit Empfehlung)

| Nr. | Frage | Empfehlung |
|---|---|---|
| E-VA-1 | Nachsuche auch für Zusatzdokumente (AN3)? | Später: Sie haben keine Pflichtarten; zuerst am PLU messen |
| E-VA-2 | Alternativbezeichnungen in der Verwaltung pflegen? | Später: zunächst im Code, versioniert über die Prüfsumme; Pflege in der Verwaltung, wenn Referenzlisten Lücken durch unbekannte Begriffe zeigen |
| E-VA-3 | Zweite Nachsuche, wenn die erste neue Lücken erzeugt? | Nein: höchstens eine je Auswertung (Kosten, Dauer); verbleibende Lücken sind benannt |
| E-VA-4 | Staffel der Grundflächenzahl | eigener Plan (Schema und Berechnung); bis dahin Hinweis und `not_expressible` |

## 7. Prüfprotokoll

### 7.1 Entwurf (vor dem Bau)

| # | Befund | Behoben durch |
|---|---|---|
| 1 | `collapse` wertet eine offene Regel aus Lauf 1 und einen Fund der Nachsuche mit gleichem Schlüssel als Widerspruch (`ambiguous`) | `fill_gaps`: Ein Fund für einen Lückenschlüssel ersetzt die offene Regel; nur Funde für Nicht-Lücken gehen durch `collapse` (3.6) |
| 2 | Kopfzeilen („dossier approbation 14“) und Beschriftungen von Skizzen („3 m voie publique“) würden als offene Stellen gezählt | Einheit Pflicht bei Zahlen, Mindestlänge 25 Zeichen; Skizzenreste stuft die Nachsuche als `out_of_scope` ein (3.3) |
| 3 | Nummern der Gegenprüfung: neue Funde dürfen nicht mit Nummern aus Lauf 1 zusammenfallen (`sources`) | Nummern ab Anzahl Lauf 1 + 1 (3.6) |
| 4 | Ohne Nachsuche (Phase A allein) hätte ein Hinweis auf eine Staffel keinen Bezug zur Regelart | Die Art bleibt dann `missing` (sicher); `not_expressible` erst mit der Nachsuche (3.1) |
| 5 | Neubewertung ohne Aufruf (RW26) könnte durch eine geänderte Lückenliste einen Aufruf auslösen | ausdrücklich zugelassen und dokumentiert (3.6); Budget und Zeitbudget gelten |
| 6 | Zwei Migrate-Jobs auf derselben gemeinsamen Datenbank | Advisory-Lock, nur erweiternde Migrationen, „voraus“ ist kein Fehler (3.9) |
| 7 | Konten liegen je Instanz; ein Fremdschlüssel auf `account` in `emprise_shared` ist unmöglich | Kennung und Anzeigename ohne Fremdschlüssel; Audit in `shared_audit` (3.9) |
| 8 | Messung: „nicht ermittelt“ ist sichtbar, eine fehlende nicht-Pflicht-Regel nicht – beides als Lücke zu zählen verwischt das Ziel | `named_gap` gegen `silent_gap` getrennt; Abnahme verlangt `silent_gap` = 0 (3.10) |

### 7.2 Geprüfte Alternativen

| Alternative | Warum nicht |
|---|---|
| Zweiter Lauf der Auswertung mit anderem Modell und Vereinigung der Ergebnisse | findet mehr, sagt aber nicht, was fehlt; doppelte Kosten; Entscheidung des Nutzers: dasselbe Modell |
| Nachsuche je Regelart als eigener Aufruf | 10–15 Aufrufe je Kapitel; eine gebündelte Nachsuche mit Lückenliste reicht |
| Nicht gefundene Pflichtangaben automatisch „nicht geregelt“ | eine übersehene Regel wirkte als „keine Grenze“ (Entscheidung des Nutzers: offen lassen) |
| Referenzlisten als Testdateien im Repository | nicht von Hand in der Anwendung erweiterbar (Wunsch des Nutzers) |
| Referenzlisten je Instanz mit Export/Import | Nutzer wünscht eine gemeinsame Verwaltung für beide Produkte |

### 7.3 Bewusste Grenzen
- Ein Sprachmodell kann 100 % nicht zusichern; verbleibende Lücken sind benannt und sichtbar.
- Vorschriften nur in Tabellen oder Skizzen ohne Textschicht erfasst die Abdeckung nicht (gescannte Seiten → AN7).
- Die Messung ist so gut wie die Referenzlisten; deshalb Status „geprüft“ und Pflege von Hand.

### 7.4 Beim Bau gefunden

| # | Befund | Folge |
|---|---|---|
| 1 | „building type“ als Beispiel einer Bedingung in der Anweisung hätte Regeln für Nebengebäude und Pools in Hinweise gedrängt, obwohl `building_kind` sie abbildet | Beispiel ersetzt durch „position on the plot“ (VA01) |
| 2 | Die Höhengrenze an der hinteren Grenze (Beyenes S. 14) lässt sich nicht mit dem Abstand von S. 12 zu einer Regel verbinden: Jede Zahl muss im Zitat stehen, das Zitat auf einer Seite oder über einen Seitenwechsel | Referenzliste erwartet sie als eigenen Hinweis; eine eigene Regelart „Höhe an der Grenze“ wäre ein weiterer Punkt |
| 3 | Ein Fund aus einer offenen Textstelle, der die Schranken nicht besteht, hätte eine geprüfte wirksame Regel über `collapse` zu `ambiguous` gemacht | Nur bestätigte Funde werden mit vorhandenen Regeln verglichen (VA06), Test `test_unconfirmed_finding_leaves_an_effective_rule_alone` |
| 4 | `rules_housekeeping` wertet Kapitel mit älterer Version der Schranken neu aus; mit geänderter Anweisung passen gespeicherte Antworten nicht mehr – eine erhöhte Version hätte alle Kapitel beider Instanzen von selbst und kostenpflichtig neu ausgewertet (lokal 4 Kapitel, etwa 4 $) | Version der Schranken bleibt `g2-1.2.0` (Bewertung vorhandener Antworten unverändert); Neuauswertung nur auf Anstoß (VA08, BETRIEB 9). Eine Sperre in `housekeeping` für kostenpflichtige Neuauswertungen wäre ein eigener Punkt |
| 5 | Bestehende Tests zählen Aufrufe und Kosten; mit der Nachsuche als Vorgabe käme ein dritter Aufruf hinzu | Tests schalten die Nachsuche über `EMPRISE_RULES_GAP_SEARCH=false` ab (`tests/conftest.py`); `FakeExtractor` beantwortet eine Nachsuche ohne eigene Antwort leer; eigene Tests (`test_rules_gaps.py`) schalten sie an |
| 6 | Beyenes UC hat 143 Stellen mit Vorschriftscharakter, die meisten zu Netzen, Gewerbe oder Fahrradstellplätzen | Die Nachsuche stuft sie ein (`out_of_scope` mit Grund); Kosten und Anteil misst der Probelauf (E) |

**Prüflauf (A, D1, B):** Backend 688 Tests mit `TEST_S3=1` (vorher 660; neu Rückfall beim Funktionsaufruf, Zitat mit Auslassung, Referenzliste und Messung, Textstellen und Alternativbezeichnungen, Nachsuche als Einheit und gegen PostGIS), ruff, Format und mypy grün, Migration 0017; Frontend 205 Tests (vorher 203; Abdeckung, Bestätigung „nicht geregelt“, ältere Version ohne Zählung), Lint, Typprüfung und Build grün; `openapi.json` und `schema.d.ts` neu erzeugt. Messung der bisherigen Läufe an der Referenzliste Beyenes UC (ohne Aufruf, Kopie `emprise_probe`):

| Version | Modell | richtig | falsch | offen (sichtbar) | fehlt still |
|---|---|---|---|---|---|
| 1 | Opus 5, PDF | 13 | 1 | 3 | 8 |
| 2 | Opus 5, Text | 11 | 1 | 5 | 8 |
| 3 | DeepSeek V4 Flash, Text | 7 | 0 | 11 | 7 |
| 4 | Kimi K3, Text | 11 | 1 | 4 | 9 |
| 5 | DeepSeek V4 Pro, Text | 10 | 0 | 6 | 9 |
| 6 | Opus 5.5, PDF | 15 | 0 | 3 | 7 |

Still fehlen vor allem Hinweise ohne passende Regelart (Wärmepumpe 4 m, Höhengrenze 3 m, Dachüberstände, Einfriedung zur Straße) – das Ziel der Nachsuche.

| # | Befund | Folge |
|---|---|---|
| 7 | Im Probelauf fehlte nur noch Art. UC 11.1 (zeitgenössische Architektur darf von Dach- und Fassadenregeln abweichen) still: Die Stelle enthält nur „peuvent“ und „dérogé“ und galt nicht als Vorschrift | Normwörter um Erlaubnis und Abweichung ergänzt (`peut`, `peuvent`, `derog`, `exig`; VA04) |
| 8 | Die Staffel der Grundfläche stand zweimal als Hinweis (aus Auswertung und Nachsuche, anderer Zitatbeginn) | Neue Hinweise der Nachsuche entfallen, wenn ein Hinweis auf derselben Seite dieselbe Stelle belegt (`quotes_overlap`; VA06) |
| 9 | Die Messung zählte Regelarten, die nur als Hinweis sichtbar sind, als „fehlt still“; der CLI-Befehl gab offene und verworfene Stellen der Version nicht weiter | Regelart ohne Regel, aber als Hinweis sichtbar → `named_gap` (`hint`); `reference-check` übergibt die Stellen und nennt die Abdeckung |
| 10 | Der Test-Container `backend-dev` erbt aus `compose.yaml` die Adresse der gemeinsamen Datenbank; Tests hätten in die echte gemeinsame Datenbank geschrieben | `tests/conftest.py` entfernt `EMPRISE_SHARED_*`; die gemeinsamen Tabellen liegen in der Testdatenbank (eigene Migrationen dort) |
| 11 | Liegen die gemeinsamen Tabellen in der Datenbank einer Instanz, hätte `alembic check` der Instanz sie als „zu löschen“ gemeldet (und umgekehrt) | `include_object` beider Umgebungen blendet die Tabellen der anderen aus; beide Prüfungen laufen als Test |
| 12 | Auf Unraid sind die Stacks vollständig getrennt (je eigener Datenbank-Container und eigenes internes Netz) | Eigener Stack `emprise-shared` mit eigenem Netz (Entscheidung des Nutzers); `deploy.sh shared` vor den Produkten, `deploy.sh` bricht ohne das Netz mit Hinweis ab |
| 13 | Die Modellwahl gilt jetzt für beide Produkte; eine frühere Wahl einer Instanz (PU11) läge verwaist in `app_setting` | `shared-migrate` übernimmt sie einmal; hat die gemeinsame Datenbank schon eine Wahl, gilt diese und die der Instanz entfällt (Test); der Anzeigename kommt aus dem Konto der Instanz mit |
| 14 | Das Laufzeit-Image enthielt `alembic_shared.ini` und `migrations_shared` nicht; der Migrate-Job brach lokal ab. Die Tests merkten es nicht, weil `backend-dev` den Quellordner einbindet | `backend/Dockerfile` kopiert beide; Stolperstelle im README |
| 15 | Die Verwaltung hängt in beiden Produkten als Splat-Route (`/verwaltung/*`); relative Links lösten sich von der vollen Adresse aus auf: „KI-Modell“ blieb auf jeder Unterseite markiert, „Alle Referenzlisten“ führte auf `/verwaltung` | feste Pfade (`verwaltung/pfade.ts`), Test auf `aria-current` und Ziel des Zurück-Links |

**Prüflauf (C, D2):** siehe 7.6.

### 7.5 Probelauf (E)

Beyenes UC in der Kopie `emprise_probe`, Opus 5.5 mit PDF, Anweisung `g2-prompt-5`, erst ohne, dann mit Nachsuche (Antworten des ersten Durchlaufs wiederverwendet; nur im Probelauf ließ die Prüfsumme die Einstellungen der Nachsuche weg). Gemessen an der Referenzliste (25 Einträge), nach den Befunden 8 und 9:

| | ohne Nachsuche (Version 7) | mit Nachsuche (Version 8) |
|---|---|---|
| richtig | 11 | **21** |
| falsch | 0 | **0** |
| offen, sichtbar | 13 (9 davon nur als offene Stelle) | 3 (kleine Nebengebäude: „nicht abbildbar“ bzw. Hinweis) |
| fehlt still | 1 | 1 (Art. 11.1, behoben durch Befund 7) |
| Stellen zugeordnet / offen / nicht einschlägig | 15 / 128 / 0 von 143 | 41 / 14 / 88 von 143 |
| Hinweise | 2 | 32 (24 über die Liste hinaus: Dachfenster, Solarpaneele, Portale, Stellplatzflächen, Rampen …) |
| Kosten | 0,59 $ (Auswertung und Gegenprüfung) | + 0,87 $ (Nachsuche 0,64 $, Gegenprüfung der 31 Funde 0,24 $) |
| Dauer | 1 min 51 s | + 3 min 25 s |

- **Ohne Nachsuche** liefert die neue Anweisung weniger wirksame Regeln als der Lauf mit `g2-prompt-4` (Version 6: 15 richtig): Dach, Zaun und unversiegelte Fläche scheiterten an der Gegenprüfung (`runs_disagree`). Die Nachsuche holt sie mit Zitat und Gegenprüfung zurück.
- **Mit Nachsuche** sind alle Pflichtangaben richtig; die Grundfläche steht als „nicht abbildbar“ mit der ganzen Staffel als Hinweis; die Sonderregel kleiner Nebengebäude (unter 12 m², unter 2,5 m) als „nicht abbildbar“ mit Hinweis – vertretbar, weil an eine Bedingung geknüpft. 14 Stellen bleiben für den Architekten offen.
- **Kosten** je Kapitel rund 1,46 $ statt der geschätzten 1,00–1,30 $: Die Antwort der Nachsuche ist lang (19 600 Ausgabe-Token mit Denkphase), weil sie jede der 120 übergebenen Stellen einstuft.
- **Abnahme** (5 Nr. 6): `wrong_value` = 0 erreicht; `silent_gap` = 1, der Rest ist mit Befund 7 behoben (Nachweis im nächsten bezahlten Lauf).

### 7.6 Prüflauf (C, D2)

Backend 697 Tests mit `TEST_S3=1` (vorher 688; neu gemeinsame Einstellung und Umzug der Modellwahl durch `shared-migrate`, `alembic check` der gemeinsamen Umgebung, Referenzlisten anlegen, aus der Auswertung übernehmen, messen, exportieren und importieren), ruff, Format und mypy grün; Frontend 210 Tests (vorher 205; Verwaltung mit Rechten, KI-Modell mit Bearbeiter, Referenzlisten, Messung je Eintrag, Eintragsformular, Verweis aus der Analyse-Startseite, Reiter und Zurück-Link nach Befund 15), Lint, Typprüfung und Build grün; `openapi.json` und `schema.d.ts` neu erzeugt.

**Von Hand (lokal):** Beide Stacks neu gebaut; `shared-migrate` legte `emprise_shared` an und übernahm die Modellwahl der Analyse (Opus 5.5), die damit auch im Konfigurator gilt. `reference-import beyenes_uc.json` spielte 25 Einträge als Entwurf ein. `/verwaltung` zeigt in beiden Produkten dasselbe Modell mit Bearbeiter und dieselbe Liste; die Analyse misst sie an ihrer Auswertung (Version 1 mit Opus 5, vor der Nachsuche: 13 von 25 richtig, 1 falsch – die pauschale Grundfläche –, 3 sichtbar offen, 8 still fehlend), der Konfigurator meldet „hier nicht ausgewertet“.
