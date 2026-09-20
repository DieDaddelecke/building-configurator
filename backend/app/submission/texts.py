"""Vorläufiger Wortlaut der zwei Rechtstexte der Übergabe (docs/PLAN_V_VORENTWURF_UEBERGABE.md 3.5).

Wie bei A (AF05, `app/inquiry/texts.py`): einmalig über `python -m app.cli legal-seed` als Version 1
veröffentlicht, damit jede Einwilligung auf eine gespeicherte Version verweist. Der endgültige Wortlaut nach
Rechtsberatung ersetzt sie über `POST /admin/legal-texts`. Der Name des Büros fehlt noch (HANDOFF 3).
"""

from app.platform.i18n import Locale

PROVISIONAL_TEXTS: list[tuple[str, Locale, str, str]] = [
    (
        "notice.design_confirmation",
        "fr",
        "Confirmation : esquisse non contractuelle",
        "Le pré-projet que je transmets est une esquisse établie automatiquement à partir de données "
        "publiques et du catalogue d'Emprise. Les règles d'urbanisme, l'implantation et la fourchette de "
        "coût sont une simulation, sans engagement et non vérifiée par un architecte ; le coût est une "
        "estimation, pas une offre. Seule l'offre écrite de l'agence d'architecture partenaire fait foi. "
        "Cette transmission ne constitue ni une commande ni un contrat.",
    ),
    (
        "notice.design_confirmation",
        "de",
        "Bestätigung: unverbindliche Vorentwurfsskizze",
        "Der Vorentwurf, den ich übergebe, ist eine automatisch aus öffentlichen Daten und dem Katalog "
        "von Emprise erstellte Skizze. Regeln des Bebauungsplans, Lage und Kostenkorridor sind eine "
        "unverbindliche, von keinem Architekten geprüfte Simulation; die Kosten sind eine Schätzung, kein "
        "Angebot. Verbindlich ist allein das schriftliche Angebot des Architekturbüros. Die Übergabe ist "
        "weder Bestellung noch Vertrag.",
    ),
    (
        "consent.transmission_design",
        "fr",
        "Consentement à la transmission du pré-projet",
        "J'accepte que mes coordonnées (nom, e-mail, téléphone le cas échéant) et les données de mon "
        "projet (terrain, simulation du règlement, modèle de maison, gamme, options, implantation, "
        "estimation de coût et dossier en PDF et DXF) soient transmises à l'agence d'architecture "
        "partenaire d'Emprise, seule destinataire, afin qu'elle puisse étudier mon pré-projet et me "
        "contacter. Emprise n'utilise ces données à aucune autre fin.",
    ),
    (
        "consent.transmission_design",
        "de",
        "Einwilligung zur Übermittlung des Vorentwurfs",
        "Ich willige ein, dass meine Kontaktdaten (Name, E-Mail, ggf. Telefon) und die Daten meines "
        "Projekts (Grundstück, Simulation des Regelwerks, Haustyp, Linie, Optionen, Lage, "
        "Kostenschätzung und Dossier als PDF und DXF) an das mit Emprise zusammenarbeitende "
        "Architekturbüro als alleinigen Empfänger übermittelt werden, damit es meinen Vorentwurf prüfen "
        "und mich kontaktieren kann. Emprise verwendet diese Daten zu keinem anderen Zweck.",
    ),
]
