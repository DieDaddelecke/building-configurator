# Testdaten Modul G2

Aufgezeichnet am 14.09.2026 von den öffentlichen Diensten (docs/ANNAHMEN.md RW01–RW18).

| Datei | Quelle | Inhalt |
|---|---|---|
| `municipality-44209.json` | `apicarto.ign.fr/api/gpu/municipality?insee=44209` | Gemeindegrenze Treillières, `is_rnu: false` |
| `zone-urba-44209.json` | `apicarto.ign.fr/api/gpu/zone-urba` (POST) mit einem Rechteck um 8 rue des Chênes (−1,601/47,2795 bis −1,593/47,284) | 7 Zonen: 5 des PLUi Erdre et Gesvres (`DU_244400503`: N, Uh, A, Uec, Ue), 2 des Nachbarplans Nantes Métropole (`DU_244400404`: Ad, UMe) |
| `prescription-surf-44209.json`, `prescription-lin-44209.json`, `info-surf-44209.json` | gleiche Endpunkte `prescription-surf`, `prescription-lin`, `info-surf` | Ausschnitt; große Geometrien weggelassen, Koordinaten auf 6 Stellen gerundet |
| `document-911b23511c396d7211def55c6bf40bd4.json` | `www.geoportail-urbanisme.gouv.fr/api/document/<id>/details` und `/files`, zusammengeführt | Dokumentangaben und Dateiliste des PLUi |
| `reglement-pages.json` | Textschicht (pypdf) von `244400503_reglement_20260304.pdf` | Originalseiten 1–3 (Inhaltsverzeichnis) und 92–112 (Kapitel Zone Uh) |
| `beyenes-uc-pages.json` | Textschicht (pypdf) des règlement écrit „PLU Beyenes“ (Modification n°1), hochgeladen in Emprise Analyse, aufgezeichnet am 28.09.2026 | Seiten 5–8 (Dispositions générales) und 9–20 (Kapitel Zone UC); Grundlage der Tests zur Abdeckung der Textstellen und der Referenzliste `app/rules/reference_seed/beyenes_uc.json` (PLAN_G2_VOLLSTAENDIGKEIT) |

Die Planunterlage selbst (6,8 MB, eingebettete Schriften) liegt nicht im Repository; `tests/rules_support.py` setzt aus der Textschicht ein schlichtes PDF. Die aufgezeichnete Modellantwort `uh_output()` dort ist von Hand am Text geprüft: Bauband 5–20 m (S. 97), seitlich auf der Grenze oder mindestens 3 m (S. 98), Grundfläche 25 % (S. 99), Traufe 7 m und First 10 m (S. 100); Dach, Fassade und unversiegelte Fläche nennt das Kapitel nicht als Zahl.

Das Testgrundstück AD 65 der G1-Fixture liegt in Zone Uh.
