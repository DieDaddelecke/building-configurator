/**
 * Zugangslink aus einer Kundenmail einlösen (V 3.9): `/zugang#t=<Token>`. Der Token steht im Fragment und
 * erreicht den Server nur im Rumpf des `POST`. Danach gilt ein neues Projekt-Cookie, und die Seite wechselt zu
 * `/vorgang`. Das Einlösen wartet auf die Sitzung, weil diese das CSRF-Cookie setzt.
 */

import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { useSession } from "../../api/session";
import { useRedeemAccess } from "../../api/submission";
import { Kopf } from "../../components/Kopf";
import { Kopfzeile } from "../../components/Kopfzeile";
import { ZugangAnfordern } from "../../inquiry/ZugangAnfordern";

function tokenFromHash(hash: string): string | null {
  const value = new URLSearchParams(hash.replace(/^#/, "")).get("t");
  return value && value.length >= 10 ? value : null;
}

export function ZugangSeite() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const session = useSession();
  const redeem = useRedeemAccess();
  const started = useRef(false);
  const token = tokenFromHash(window.location.hash);

  useEffect(() => {
    if (!token || session.isPending || started.current) return;
    started.current = true;
    redeem.mutate(token, { onSuccess: () => navigate("/vorgang", { replace: true }) });
  }, [token, session.isPending, redeem, navigate]);

  const invalid = !token || redeem.isError;
  return (
    <div className="emp">
      <Kopfzeile untertitel={t("tagline")} />
      <main className="max-w-5xl mx-auto px-6 lg:px-10 py-10 anim-seite flex flex-col gap-8">
        <Kopf eyebrow={t("configurator.eyebrow")} titel={t("access.title")}>
          <p role={invalid ? "alert" : "status"}>{invalid ? t("access.invalid") : t("access.redeeming")}</p>
        </Kopf>
        {invalid && <ZugangAnfordern />}
      </main>
    </div>
  );
}
