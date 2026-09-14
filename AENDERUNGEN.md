# Änderungsprotokoll

Neueste Einträge zuerst. Ein Eintrag je Session, geschrieben von `/handoff`. Der aktuelle Stand steht in [HANDOFF.md](HANDOFF.md).

---

## 13.09.2026 – Prüfung Spezifikation, Umsetzungsplan, Session-Übergabe

**Neu**
- `UMSETZUNGSPLAN.md` – Module P, G1–G3, A, H1–H3, V, X1–X5; Releases R0–R2; technische Umsetzung je Modul; IT-Infrastruktur; 20 Abweichungen von der Spezifikation; Entscheidungen D1–D10; Prüfprotokoll mit 20 behobenen Logikfehlern und 15 Alternativen. Status: Vorschlag.
- `HANDOFF.md` – Momentaufnahme für die nächste Session.
- `AENDERUNGEN.md` – dieses Protokoll.
- `.claude/skills/handoff/SKILL.md` – Befehl `/handoff`.

**Geändert**
- `AGENTS.md` – Stand um Umsetzungsplan ergänzt; Dokumententabelle um `UMSETZUNGSPLAN.md`, `HANDOFF.md`, `AENDERUNGEN.md`.
- `CLAUDE.md` – Ablauf zu Beginn jeder Session und Verweis auf `/handoff`.

**Ohne Dateiänderung**
- Rückmeldung zur Spezifikation: Umfang, Reihenfolge, 12 Logikfehler, Effizienzvorschläge. Offene Punkte stehen in `HANDOFF.md` 4.1.
- Funktionsprüfung des Mockups im Browser: Durchlauf Ligne/Confort/Lärche/Terrasse ergibt „ca. 384.000 – 418.000 €“, Schnellstellung straßennah 5/18/4/4 m, Begrenzung und Formularprüfung funktionieren.
- Erklärung, wie Kataster- und Bebauungspläne in Grundstück, Regelwerk, bebaubare Fläche und Oberfläche übergehen.

**Unverändert:** `BACKEND_SPEZIFIKATION.md`, `Hauskonfigurator.jsx`, `emprise.html`, `Dokumentation.html`, `tools/build-mockup.cjs`.

**Memory:** Erste Einträge angelegt (Sprache und Schwerpunkte des Nutzers, Selbstprüfung von Dokumenten, schrittweise produktive Umsetzung).

**Hand-off:** Am Sessionende erstmals ausgeführt, von Hand nach `SKILL.md`. `HANDOFF.md` ergänzt um die offene Frage, ob große Dokumente zu Sessionbeginn vollständig gelesen werden sollen, und um den ausstehenden Test von `/handoff`. Memory geprüft, keine Änderung nötig.

---

## Bis 13.09.2026 – frühere Sessions

Aus Dateiständen und `AGENTS.md` rekonstruiert, ohne Einzelheiten:
- Klickbares Mockup `Hauskonfigurator.jsx` mit Build-Skript `tools/build-mockup.cjs` und erzeugter Seite `emprise.html`; als Artefakt veröffentlicht.
- Fachdokumentation `Dokumentation.html`; als Artefakt veröffentlicht.
- `BACKEND_SPEZIFIKATION.md` mit Prüfprotokoll (Anhang E).
- `AGENTS.md` und `CLAUDE.md` angelegt.
