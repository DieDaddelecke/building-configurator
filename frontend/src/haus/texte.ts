/** Texte des Hausmodells in den Sprachen der Oberfläche (D7): Deutsch, sonst Französisch (führend). */

export interface Text {
  fr: string;
  de: string;
}

export const label = (text: Text, language: string) => (language === "de" ? text.de : text.fr);

/** Winkel mit höchstens einer Nachkommastelle, z. B. „35°“ oder „37,5°“ (Neigung und Drehung des Dachs). */
export const grad = (value: number, language: string) =>
  `${new Intl.NumberFormat(language === "de" ? "de-DE" : "fr-FR", { maximumFractionDigits: 1 }).format(value)}°`;
