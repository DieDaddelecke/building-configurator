# IFC-Importvertrag

> **Stand 04.10.2026 (HM5).** Für das Büro: So wird ein Haustyp in Archicad modelliert und exportiert, damit der Konfigurator ihn einlesen kann. Gilt seit dem IFC-Import (HM3), mit mehreren Geschossen und geneigten Dächern seit HM5. Grundlage: [PLAN_HAUSMODELL.md](PLAN_HAUSMODELL.md) 3.6 und die Probedateien in Kapitel 10. Einzige Ausnahme zur Regel „sechs Dokumente plus Archiv“ (E-HM-17), weil das Büro und nicht der Code der Leser ist.

## 1. Grundsatz

Der Import macht aus einer IFC-Datei einen **Entwurf** des Haustyps. Das Büro prüft den Entwurf, ergänzt, was der Import nicht erkennt, und veröffentlicht ihn erst dann. Nichts geht still verloren: Der Importbericht nennt zu jedem Bauteil und jeder Zone, was gelesen, ignoriert oder nicht erkannt wurde.

Außenwände und Dach sind **Platzhalter**. Ihren Aufbau (Schichten, Dämmung, Deckung) wählt der Kunde im Konfigurator. Aus dem IFC zählt nur ihre Lage und Form.

## 2. Export und Hochladen

- Übersetzer **„03 - Paramétrique (IFC4)“** (IFC4 Design Transfer View), Einheit Meter. Andere Übersetzer erst nach Rücksprache. Gelesen werden IFC2X3, IFC4 und IFC4X3 als `.ifc` (STEP), nicht IFC-ZIP oder ifcXML.
- Eine Datei je Haustyp, höchstens 100 MB. Raumbegrenzungen und Basismengen sind nicht nötig.
- Lage im Projekt beliebig: Der Import bezieht alles auf die Innenkante der Außenwände. Nordrichtung und Gelände werden nicht gelesen; die Lage auf dem Grundstück wählt der Kunde.
- Hochladen im Büro unter Katalog → Hausmodell (Rolle `catalog_admin`). Die **Kennung** des Haustyps besteht aus Kleinbuchstaben, Ziffern und Unterstrich und beginnt mit einem Buchstaben (z. B. `maison_plain_pied_90`); sie muss die sein, unter der der Katalog den Typ mit Preis führt. Jede neue Datei unter derselben Kennung ist eine neue Version; dieselbe Datei noch einmal ergibt keine, solange ihr Entwurf offen ist.

## 3. Geschosse

- Jedes Geschoss mit Wänden oder Zonen zählt als Geschoss, z. B. Erdgeschoss und R+1.
- **Alle Geschosse haben dieselbe Innenkante der Außenwände** (Außenwände genau übereinander, Toleranz 1 mm). Ein kleineres Obergeschoss, Rücksprünge oder Erker nur in einem Geschoss liest der Import nicht.
- Ein Geschoss, das nur das Dach enthält (z. B. „R+1“ auf Höhe der Traufe), ist die **Dachebene** und zählt nicht als Geschoss.
- Bodenplatte im Erdgeschoss als Decke (`FLOOR` oder `BASESLAB`), Oberkante auf der Höhe des Geschosses (±0,00).
- **Unter jedem Obergeschoss eine Geschossdecke** (`FLOOR`), Oberkante auf der Höhe des Geschosses, über mehr als der Hälfte der Fläche innerhalb der Außenwände; ein Treppenloch ist erlaubt. Welchem Geschoss sie in Archicad zugeordnet ist, spielt keine Rolle. Treppen liest der Import nicht.
- Höhe des Erdgeschosses über dem Gelände: Eigenschaft `Emprise.GroundFloorOffset` am Gebäude, sonst Eingabe im Entwurf (Standard 0,20 m).
- Die Fassadenrollen (Straße, Garten, Seiten) setzt das Büro im Entwurf am Erdgeschoss; die Obergeschosse übernehmen sie.

## 4. Außenwände (Platzhalter)

- Einschichtig mit beliebigem Material und beliebiger Dicke modellieren, **gerade** (Bogenwände liest der Import nicht).
- **Die Innenseite ist maßgeblich:** Sie wird die Innenkante der innersten Schicht jedes Wandaufbaus im Konfigurator. Räume bleiben so bei jedem Aufbau gleich groß; die Fassade wandert nach außen.
- Referenzlinie auf der Innenseite (wie in den Probedateien), Wände an den Ecken geschlossen (Toleranz 1 mm).
- `IsExternal` (Archicad: Position „Außen“) bei Außenwänden ein, bei Innenwänden aus. Stimmt es nicht, trennt der Import über die Geometrie und warnt.
- Beim Flachdach mit Attika die Außenwände bis zur Oberkante der Attika hochziehen; der Import liest die Attika als Überstand der Wände über die Dachdecke. Beim geneigten Dach liest er die Höhe der Außenwände nicht; Giebelwände dürfen bis unter das Dach reichen.
- Keine Vorsatzschalen oder getrennten Dämmwände: Sie gehören zum Wandaufbau des Konfigurators.

## 5. Innenwände

- Als Wände mit `IsExternal` aus. Dicke und Lage werden übernommen.
- Räume sind die Flächen zwischen den Wänden eines Geschosses. Wände müssen sich deshalb berühren; eine Lücke verbindet zwei Räume.

## 6. Zonen

- Jeder Raum bekommt eine Zone. Eine offene Wohnküche darf zwei Zonen haben (Séjour und Cuisine); die Aufteilung bestätigt das Büro im Entwurf.
- **Die Zonenkategorie bestimmt den Raumtyp** (z. B. CHAMBRE, SEJOUR/CUISINE, SALLE DE BAIN/WC, ENTREE, GARAGE). Nummern stören nicht („CHAMBRE 1“, „Chambre_02“), ebenso wenig Akzente, Groß- und Kleinschreibung oder die Reihenfolge bei „Cuisine + Séjour“. Neue Kategorien trägt das Büro einmal als Alias im Katalog ein.
- Zonen bis zur Innenseite der Wände zeichnen und nach dem Verschieben von Wänden aktualisieren. Der Import ordnet auch veraltete Zonen richtig zu, weil der Umriss aus den Wänden kommt, warnt dann aber („Zone nicht aktualisiert“).
- Kategorien für Flächenberechnungen (SDP, SHAB, Surface de plancher, Emprise au sol) werden ignoriert. Zonenname und -nummer werden nicht übernommen.
- Bis die Liste des Büros vorliegt, kennt der Demo-Katalog: Séjour, Salon, Salle à manger, Séjour/Cuisine, Pièce de vie · Cuisine · Chambre, Suite parentale · Salle de bain, Salle d’eau, Salle de bain/WC, Salle d’eau/WC, WC · Dégagement, Couloir, Entrée, Hall. Eine Garage kennt er noch nicht.

## 7. Fenster und Türen

- Mit den Fenster- und Türwerkzeugen in die Wand setzen, nicht als Objekte davor.
- Maße kommen aus dem Typ (Breite, Höhe), die Lage aus der Wand.
- **Rollladenkasten:** Die Öffnung in der Wand ist um den Kasten höher als das Fenster (in den Probedateien 0,25 m oben, 0,05 m unten). Der Import liest die Kastenhöhe daraus; kein eigenes Bauteil für den Kasten.
- **Typ aus dem Katalog:** Der Import sucht zu jedem Fenster den Katalogtyp mit gleicher Breite, Höhe, Oberkante und Kastenhöhe, zu jeder Tür den mit gleicher Breite und Höhe (je auf 1 mm). Passt keiner oder passen mehrere, wählt das Büro den Wert im Entwurf. Ein Fenstermaß, das es im Katalog nicht gibt, erst dort anlegen lassen.
- **Haustür:** die Außentür, die in die Zone ENTREE führt; der Import schlägt sie als Eingang vor. Ebenso ein Garagentor (Außentür in die Garage).

## 8. Dach (Platzhalter)

- **Genau ein Dach** über dem obersten Geschoss: `IfcRoof` (ein Körper oder aus Teilen) oder eine Decke vom Typ Dach.
- **Flachdach:** oben und unten waagerecht, über der ganzen Fläche innerhalb der Außenwände. Seine Unterseite ist die Auflagerhöhe (Decke des obersten Geschosses über ±0,00), seine Dicke die Dachdecke; die Außenwände reichen bis zur Oberkante der Attika (Abschnitt 4). Ragt das Dach über die Außenseite der Wände, gilt das als Überstand.
- **Geneigt** mit dem Dachwerkzeug: Pultdach, Satteldach, Walm- und Zeltdach, Krüppelwalmdach, Mansarddach (umlaufend) und Mansarddach mit Giebeln, auch auf L-, T- und U-Grundrissen. Der Import liest die Form aus der **Unterseite** des Dachs:
  - Die Unterseite liegt auf der Innenkante der Außenwände in Auflagerhöhe (Probedatei 2: 3,77 m); alle Traufen liegen gleich hoch.
  - Alle Traufflächen haben dieselbe Neigung (beim Mansarddach die unteren, steilen Abschnitte). Die oberen Abschnitte des Mansarddachs und die Krüppelwalme haben je eine eigene, untereinander gleiche Neigung.
  - An einem Giebel steigt das Dach nicht von der Wand an; Giebel liegen nur an den Enden eines Flügels.
  - Überstand waagerecht ab Außenseite der Wand: an allen Traufen gleich, an den Giebeln (Ortgang) ein eigener, untereinander gleicher Wert.
- Der Konfigurator erzeugt das Dach selbst aus Form, Neigungen, Auflagerhöhe, Überständen und Drehung und vergleicht seine Unterseite auf 1 mm mit der aus dem IFC. Weicht sie ab oder passt keine Form, meldet der Import „Dachform nicht erkannt“ mit dem Grund (z. B. „die Traufen liegen verschieden hoch“); das Dach ist dann **offen im Entwurf**.
- **Dach im Entwurf festlegen:** Unter „Geneigtes Dach festlegen“ wählt das Büro Form, Neigung der Traufflächen, beim Krüppelwalm- und Mansarddach die obere Neigung und die Krüppel- bzw. Knickhöhe, die Drehung, die Auflagerhöhe und die Überstände an Traufe und Ortgang. Die Angabe ersetzt das Dach aus dem IFC, auch ein erkanntes. Ein Flachdach lässt sich so nicht festlegen; es braucht die Dachdecke aus dem IFC.
- **Öffnungen unter einem geneigten Dach:** Die Unterseite fällt von der Innenkante nach außen ab (bei 35° und 0,36 m Wand um 0,25 m). Unter einer Traufe muss jede Öffnung samt Rollladenkasten unter der Dachunterseite an der Außenseite der Wand enden; mit Stürzen auf Auflagerhöhe sperrt der Konfigurator die Dachform. Das Auflager deshalb um diesen Betrag höher legen (Kniestock), gerechnet mit dem dicksten Wandprofil des Katalogs.
- Noch nicht: Gauben, Dachfenster, versetzte Pultdächer, Dächer über Gebäudeteilen verschiedener Höhe.

## 9. Was der Import nicht liest

Möbel, Sanitär- und Küchenobjekte, Treppen, Beschriftungen und Bemaßungen, Schichten und Materialien von Außenwänden und Dach, Proxys, Gelände. Die Bodenplatte dient nur zur Kontrolle (ihre Fläche muss der Innenkontur entsprechen) und für ihre Dicke, ebenso die Geschossdecken (Lage und Dicke).

## 10. Checkliste vor dem Export

- [ ] Geschosse mit Wänden und Zonen, Außenwände aller Geschosse genau übereinander
- [ ] Bodenplatte auf ±0,00, unter jedem Obergeschoss eine Geschossdecke auf seiner Höhe
- [ ] Außenwände gerade und geschlossen, Innenseite ist die gewünschte Innenkante, `IsExternal` richtig gesetzt
- [ ] Innenwände berühren sich; keine Lücke zwischen Räumen
- [ ] Jede Zone mit Kategorie; nach Wandänderungen aktualisiert
- [ ] Fenster und Türen in den Wänden, Maße wie ein Typ im Katalog; Haustür führt in die Entrée
- [ ] Genau ein Dach: flach über der Fläche innerhalb der Außenwände (Außenwände bis Oberkante Attika) oder geneigt mit der Unterseite auf der Innenkante in Auflagerhöhe, gleichen Traufen und gleichen Überständen
- [ ] Unter einem geneigten Dach enden die Öffnungen samt Rollladenkasten unter der Dachunterseite an der Außenseite der Wand
- [ ] Übersetzer „03 - Paramétrique (IFC4)“, Meter, Datei unter 100 MB

## 11. Meldungen

**Fehler** behebt nur eine neue Datei, **offene Punkte** klärt das Büro im Entwurf; beide verhindern das Veröffentlichen. Warnungen und Hinweise hindern nicht. Die vollständige Liste zeigt der Importbericht in der Oberfläche.

| Meldung | Art | Abhilfe |
|---|---|---|
| Datei nicht lesbar, Schema nicht unterstützt, Lesen zu lang oder zu groß | Fehler | neu exportieren (Übersetzer prüfen) |
| Kein Geschoss mit Wänden oder Zonen; Geschoss mit anderem Außenumriss als das Erdgeschoss | Fehler | Geschosszuordnung prüfen; Außenwände übereinander setzen |
| Keine Geschossdecke unter einem Obergeschoss | Fehler | Decke mit Oberkante auf der Höhe des Geschosses modellieren |
| Außenwände umschließen nicht genau eine Fläche; Wand nicht gerade | Fehler | Ecken schließen, Wand gerade modellieren |
| Zone liegt in keinem Raum zwischen den Wänden | Fehler | Zone in einen Raum legen oder Wände schließen |
| Öffnung in keiner Wand oder außerhalb ihrer Wand | Fehler | Fenster oder Tür mit dem Werkzeug in die Wand setzen |
| Keine Bodenplatte; kein Dach oder mehrere Dächer | Fehler | Bodenplatte bzw. genau ein Dach modellieren |
| Zone nicht erkannt, Raum ohne Zone | offen im Entwurf | Raumtyp zuweisen oder Alias im Katalog ergänzen |
| Raum mit Zonen verschiedener Typen | offen im Entwurf | Teilung bestätigen |
| Kein oder mehrere Katalogtypen passen zur Öffnung | offen im Entwurf | Wert wählen oder Typ im Katalog anlegen lassen |
| Kein Eingang erkannt, mehrere Kandidaten für Eingang oder Garagentor | offen im Entwurf | Tür wählen |
| Dachform nicht erkannt (mit Grund) | offen im Entwurf | Dach im Entwurf festlegen oder in Archicad korrigieren (Abschnitt 8) |
| Zone nicht aktualisiert; Werte der Zone widersprechen sich | Warnung | Zone an die Wände anpassen bzw. Kategorie prüfen |
| `IsExternal` widerspricht der Lage | Warnung | Position der Wand korrigieren |
| Bodenplatte neben ±0,00 oder mit anderer Fläche, Geschossdecke neben der Höhe ihres Geschosses; Flachdach deckt die Fläche nicht | Warnung | Platte, Decke bzw. Dach prüfen |
| Noch keine Fassadenrolle gesetzt | Warnung | Straße, Garten und Seiten im Entwurf zuordnen |
| Geschoss nur mit Dach (Dachebene); Dach im Entwurf festgelegt | Hinweis | – |

Offen: Referenz-IFC des Demohauses, Liste der Zonenkategorien des Büros (bis dahin die Aliasse des Demo-Katalogs, Abschnitt 6) und je Dachform eine Probe aus Archicad. Geprüft ist bisher nur das Walmdach der Probedatei 2, die übrigen Formen nur mit nachgebauten Dateien; Abschnitt 8 kann sich mit den ersten Proben noch ändern.
