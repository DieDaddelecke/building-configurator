"""Vorläufiger Wortlaut der zwei neuen Rechtstexte (docs/PLAN_A_ANFRAGE.md 3.10, 9 Punkt 3).

Wird einmalig über `python -m app.cli legal-seed` veröffentlicht (Version 1), damit die erste Einwilligung
sich auf eine echte, gespeicherte Version beziehen kann. Endgültiger Wortlaut nach Rechtsberatung ersetzt
diese Version über `POST /admin/legal-texts`, ohne Codeänderung hier. Der Name des Architekturbüros ist
noch nicht in den Projektunterlagen benannt; der Text beschreibt es deshalb als Emprise' Simulationspartner
statt einen Namen zu erfinden – bei Bedarf ersetzen, sobald er feststeht.
"""

from app.platform.i18n import Locale

PROVISIONAL_TEXTS: list[tuple[str, Locale, str, str]] = [
    (
        "notice.simulation_confirmation",
        "fr",
        "Confirmation : simulation non contractuelle",
        "Les informations affichées (limites du terrain, règles du plan local d'urbanisme, emprise "
        "constructible) résultent d'une simulation automatique à partir de données publiques. Elles ne "
        "constituent ni une autorisation d'urbanisme, ni un engagement contractuel, ni une vérification par "
        "un architecte. Seuls un certificat d'urbanisme délivré par la mairie ou l'étude du dossier par "
        "l'agence d'architecture partenaire font foi. En cochant cette case, je reconnais avoir pris "
        "connaissance du caractère non contractuel et non vérifié de cette simulation.",
    ),
    (
        "notice.simulation_confirmation",
        "de",
        "Bestätigung: unverbindliche Simulation",
        "Die angezeigten Angaben (Grundstücksgrenzen, Regeln des Bebauungsplans, bebaubare Fläche) stammen "
        "aus einer automatischen Simulation auf Grundlage öffentlicher Daten. Sie sind kein "
        "Baugenehmigungsbescheid, keine vertragliche Zusage und keine Prüfung durch ein Architekturbüro. "
        "Verbindlich ist allein ein Certificat d'urbanisme der Gemeinde oder die Prüfung durch das "
        "Architekturbüro. Mit dem Ankreuzen bestätige ich, dass ich diesen unverbindlichen, ungeprüften "
        "Charakter der Simulation zur Kenntnis genommen habe.",
    ),
    (
        "consent.transmission_office",
        "fr",
        "Consentement à la transmission au bureau d'architecture",
        "J'accepte que mes coordonnées (nom, e-mail, téléphone le cas échéant) et les données de mon projet "
        "(terrain, simulation du règlement, emprise constructible) soient transmises à l'agence "
        "d'architecture partenaire d'Emprise, seule destinataire, afin qu'elle puisse me contacter et "
        "étudier ma demande. Emprise n'utilise ces données à aucune autre fin. Tant qu'aucune demande n'a "
        "été transmise, je peux demander l'export ou la suppression de mes données.",
    ),
    (
        "consent.transmission_office",
        "de",
        "Einwilligung zur Übermittlung an das Architekturbüro",
        "Ich willige ein, dass meine Kontaktdaten (Name, E-Mail, ggf. Telefon) und die Daten meines "
        "Projekts (Grundstück, Simulation des Regelwerks, bebaubare Fläche) an das mit Emprise "
        "zusammenarbeitende Architekturbüro als alleinigen Empfänger übermittelt werden, damit es mich "
        "kontaktieren und meine Anfrage prüfen kann. Emprise verwendet diese Daten zu keinem anderen Zweck. "
        "Solange noch keine Anfrage übermittelt wurde, kann ich Export oder Löschung meiner Daten "
        "verlangen.",
    ),
]
