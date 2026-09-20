/** Neuen Zugangslink per E-Mail anfordern (V 3.9). Die Antwort ist immer gleich, ob die Adresse bekannt ist. */

import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useRequestAccess } from "../api/submission";
import { Fehler } from "./AnfrageFormular";

export function ZugangAnfordern() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const request = useRequestAccess();
  return (
    <section aria-labelledby="zugang-anfordern" className="flex flex-col gap-3 max-w-xl">
      <h2 id="zugang-anfordern" className="eyebrow m-0">
        {t("access.requestTitle")}
      </h2>
      <p className="text-sm t-mute m-0">{t("access.requestIntro")}</p>
      {request.isSuccess ? (
        <p className="m-0" role="status">
          {t("access.sent")}
        </p>
      ) : (
        <form
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            request.mutate(email);
          }}
        >
          <label className="flex flex-col gap-1">
            {t("access.email")}
            <input type="email" className="field" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          {request.isError && <Fehler error={request.error} />}
          <button type="submit" className="btn btn-primary self-start" disabled={request.isPending}>
            {t("access.send")}
          </button>
        </form>
      )}
    </section>
  );
}
