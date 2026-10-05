import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import de from "./de.json";
import fr from "./fr.json";

// Französisch führt (Entscheidung D7); Deutsch zusätzlich. Die Wahl bleibt im Browser gespeichert.
export const LANGUAGES = ["fr", "de"] as const;
export type Language = (typeof LANGUAGES)[number];

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: { fr: { translation: fr }, de: { translation: de } },
    fallbackLng: "fr",
    supportedLngs: LANGUAGES,
    nonExplicitSupportedLngs: true,
    load: "languageOnly",
    interpolation: { escapeValue: false },
    detection: {
      order: ["localStorage", "navigator"],
      lookupLocalStorage: "emprise.sprache",
      caches: ["localStorage"],
      // Nur die Sprache, ohne Region: Code vergleicht `i18n.language` mit "de" (Zahlen, Bezeichnungen); mit
      // "de-DE" aus dem Browser griffe das sonst nicht
      convertDetectedLanguage: (lng: string) => lng.slice(0, 2),
    },
  });

i18n.on("languageChanged", (lng) => {
  document.documentElement.lang = lng;
});

export function currentLanguage(): Language {
  const lng = (i18n.resolvedLanguage ?? "fr").slice(0, 2);
  return (LANGUAGES as readonly string[]).includes(lng) ? (lng as Language) : "fr";
}

export default i18n;
