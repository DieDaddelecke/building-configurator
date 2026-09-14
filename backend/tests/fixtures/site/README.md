# Testdaten Modul G1

Aufgezeichnet am 14.09.2026 von den öffentlichen Diensten (docs/ANNAHMEN.md G01–G21).

| Datei | Quelle | Inhalt |
|---|---|---|
| `cadastre-44209-parcelles.json.gz`, `-batiments.json.gz`, `-communes.json.gz` | Etalab-Kataster, Stand 2026-06-01, Gemeinde Treillières (44209), Lizenz ODbL | Parzellen und Gebäude im Umkreis von rund 135 m um 8 rue des Chênes (103 Parzellen, 128 Gebäude), vollständige Gemeindegrenze |
| `bdtopo-44209-troncons.json.gz` | Géoplateforme WFS `BDTOPO_V3:troncon_de_route`, Ausschnitt 352450–352980 / 6696700–6697200 (Lambert-93) | 92 Straßenachsen |
| `geocode_search.json` | `data.geopf.fr/geocodage/search?q=8 rue des Ecoles Treillières` | Adressvorschläge |
| `altimetry.json` | `data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json` | drei Höhen |
| `georisques_report.json`, `georisques_rga.json` | `georisques.gouv.fr/api/v1/resultats_rapport_risque`, `/rga` für 8 rue des Chênes | Risikobericht, Tonböden |

Erwartete Kantenarten der Testfälle (`tests/integration/test_site.py`) sind an einem Lageplan der Daten geprüft: AD 42 liegt an einer Kreuzung der Lotissement-Straßen (Straßenparzelle AD 71), AD 65 ist ein Reihengrundstück mit Straße im Nordnordosten.

Neu aufzeichnen: Katasterdateien mit einem Ausschnitt aus `https://cadastre.data.gouv.fr/data/etalab-cadastre/<stand>/geojson/communes/44/44209/`; bei neuem Stand ändern sich Anzahlen und gegebenenfalls Erwartungen der Tests.
