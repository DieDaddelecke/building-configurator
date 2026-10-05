/** Texte des Hausmodells in den Sprachen der Oberfläche (D7): Deutsch, sonst Französisch (führend). */

export interface Text {
  fr: string;
  de: string;
}

export const label = (text: Text, language: string) => (language === "de" ? text.de : text.fr);
