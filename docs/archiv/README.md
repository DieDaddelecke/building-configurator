# Archiv

Frühere Dokumente, **unverändert** am 30.09.2026 hierher verschoben (DECISIONS ADR-08). Sie sind historisch und gelten nur, soweit [DECISIONS.md](../../DECISIONS.md) auf sie verweist. Hier nichts ändern; Neues gehört in die sechs Dokumente im Wurzelordner.

**Verweise:** Der Code nennt Kapitel und IDs dieser Dateien („Spez. 5.3.1“, „Plan H3 3.8“, `docs/PLAN_AN5_AUSGABE.md` 3.6, „ANNAHMEN PU12“, „BETRIEB 15“). Die Dateinamen sind gleich geblieben, nur der Ordner ist jetzt `docs/archiv/`. Relative Links innerhalb der Dateien zeigen noch auf die alten Orte (Wurzelordner bzw. `docs/`).

| Datei | Früher | Inhalt |
|---|---|---|
| [BACKEND_SPEZIFIKATION.md](BACKEND_SPEZIFIKATION.md) | Wurzel | Spezifikation des Backends: Leitplanken, Glossar, Datenmodell, Abläufe, API, Tests, E1–E12, Prüfprotokoll mit S1–S17. Beschreibt teils Veraltetes (Celery, Redis, MinIO, Claude API) |
| [UMSETZUNGSPLAN.md](UMSETZUNGSPLAN.md) | Wurzel | Module, Releases, Technik, Infrastruktur, Abweichungen (Kapitel 7), D1–D18 |
| `PLAN_<Modul>.md` | `docs/` | Modulpläne G2-Vollständigkeit, G3, H1, H2, H3, A, V, Analyse und AN1–AN7 mit Festlegungen, Entscheidungen E-…, Prüfprotokollen |
| [ANNAHMEN.md](ANNAHMEN.md) | `docs/` | Festlegungen je Modul mit IDs (A, G, RW, BR, H, AF, HP, HK, VU, PS, UP, PU, EA, KR, VA, AU, SC, MA) |
| [BETRIEB.md](BETRIEB.md) | `docs/` | Betriebsanleitung; aktueller Inhalt jetzt in [deploy/unraid/README.md](../../deploy/unraid/README.md) Teil B (Abschnitt n hier = dort: 1 → 10, 2 → 5, 3 → 11, 4 → 12, 5 → 13, 6 → 6, 7 → 14, 8 → 15 … 16 → 23) |
| [API_ANALYSE.md](API_ANALYSE.md) | `docs/` | Anleitung zur API mit Schlüsseln für fremde Büros; seit ADR-07 ohne Gegenstück im Code |
| [HANDOFF.md](HANDOFF.md) | Wurzel | letzter Hand-off vom 29.09.2026; abgelöst durch [ROADMAP.md](../../ROADMAP.md) |
| [AENDERUNGEN.md](AENDERUNGEN.md) | Wurzel | Änderungsprotokoll je Session bis 29.09.2026; seitdem ist das Git-Log das Protokoll |
| [INFRA_ANBIETER.md](INFRA_ANBIETER.md) | `infra/README.md` | Anforderungen an einen späteren verwalteten Anbieter (Plan 6.4); gilt wieder, wenn D3 neu entschieden wird |
| `REFACTORING_*.md` | Wurzel | Analyse, Plan, Zielarchitektur und Risiken des Refactorings vom 29./30.09.2026 (Befunde B-…, Risiken R-…, Schritte S1–S26) |
| `mockup/` | Wurzel, `tools/` | Mockup vom 13.09.2026 (siehe unten) |

## Mockup

`Hauskonfigurator.jsx` war das Mockup als einzelne React-Datei, `emprise.html` die daraus erzeugte Seite, `Dokumentation.html` ihre Beschreibung. Das Frontend in `frontend/` hat es ersetzt; es wird nicht mehr gepflegt. Veröffentlicht als Artefakte: Mockup https://claude.ai/code/artifact/32deba67-7935-49f5-90af-181e05a23aee, Dokumentation https://claude.ai/code/artifact/73ba0a48-1197-4d7c-8c8a-8ad1e6fe1576. Der ursprüngliche Auftrag lag außerhalb des Projekts (`C:\Users\sarah\Downloads\mockup-prompt.md`).

- **Neu erzeugen:** `build-mockup.cjs` liest `Hauskonfigurator.jsx` aus dem Ordner über sich und schreibt `emprise.html` dorthin. Am einfachsten Skript und JSX in einen leeren Ordner `x/tools/` bzw. `x/` kopieren, dort `npm install --no-save esbuild` und `node tools/build-mockup.cjs`.
- **Im Browser prüfen** (`file:///…`): Bedienung und Auslesen per `find` und `javascript_tool`; Typkarten sind keine `<button>`, sondern Elemente mit `role=button`; die Kontaktprüfung meldet Fehler erst beim Klick auf „Vorentwurf zur Prüfung übergeben“.
