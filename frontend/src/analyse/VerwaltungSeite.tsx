import { useSession } from "../api/session";
import { darfVerwalten, Verwaltung } from "../verwaltung/Verwaltung";

/** Gemeinsame Verwaltung im Rahmen des Analyse-Produkts (PLAN_G2_VOLLSTAENDIGKEIT 3.9). */
export function VerwaltungSeite() {
  const roles = useSession().data?.staff?.roles;
  return <Verwaltung darf={darfVerwalten(roles)} />;
}
