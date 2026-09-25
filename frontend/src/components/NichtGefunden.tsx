import { useTranslation } from "react-i18next";
import { Link } from "react-router";

/** Fehlerseite beider Produkte (AN0): liegt hier, damit der Analyse-Einstieg nicht `App.tsx` lädt. */
export function NichtGefunden() {
  const { t } = useTranslation();
  return (
    <main className="emp p-10 flex flex-col gap-4">
      <h1 className="f-display text-3xl">{t("error.notFound")}</h1>
      <Link className="link" to="/">
        {t("error.home")}
      </Link>
    </main>
  );
}
