/**
 * Speichern der Hauskonfiguration (HM4): ein `PATCH` nach dem anderen. Was während eines Laufs dazukommt, wartet
 * und geht gesammelt mit der Revision der letzten Antwort; so überholen sich Ausstattung, Lage und Grenzschalter
 * nicht. Ein Haustyp ersetzt alles Wartende, weil der Server Auswahl und Lage dabei zurücksetzt.
 */

import { useRef, useState } from "react";

import { problemOf, type ConfigurationProblem } from "../api/configuration";
import { usePatchHouseConfiguration, type HouseConfigurationPatch } from "../api/hausKonfiguration";

export type Art = "typ" | "auswahl" | "lage";

export interface Fehler {
  art: Art;
  problem: ConfigurationProblem | null;
  /** Haustyp, dessen Wahl abgelehnt wurde. */
  slug: string | null;
}

interface Auftrag {
  body: HouseConfigurationPatch;
  danach: (() => void)[];
}

function artOf(body: HouseConfigurationPatch): Art {
  if (body.template_slug !== undefined) return "typ";
  return body.configuration !== undefined ? "auswahl" : "lage";
}

export interface Speichern {
  /** Ein `PATCH` läuft oder wartet. */
  laeuft: boolean;
  fehler: Fehler | null;
  /** `price_match` der letzten Antwort mit Browserpreis. */
  preisGleich: boolean | null;
  /** Reiht eine Änderung ein; `danach` läuft, sobald sie gespeichert ist. */
  senden: (body: HouseConfigurationPatch, danach?: () => void) => void;
}

/** `onKonflikt` läuft, wenn ein anderer Stand gespeichert wurde; die Seite verwirft dann ihren Entwurf. */
export function useSpeichern(projectId: string, revision: number, onKonflikt: () => void): Speichern {
  const patch = usePatchHouseConfiguration(projectId);
  const zustand = useRef<{ wartend: Auftrag | null; laeuft: boolean; revision: number | null }>({
    wartend: null,
    laeuft: false,
    revision: null,
  });
  const [laeuft, setLaeuft] = useState(false);
  const [fehler, setFehler] = useState<Fehler | null>(null);
  const [preisGleich, setPreisGleich] = useState<boolean | null>(null);

  const abarbeiten = async (geladen: number) => {
    const z = zustand.current;
    z.laeuft = true;
    setLaeuft(true);
    while (z.wartend) {
      const auftrag = z.wartend;
      z.wartend = null;
      try {
        const out = await patch.mutateAsync({ body: auftrag.body, revision: z.revision ?? geladen });
        z.revision = out.revision;
        setFehler(null);
        if (auftrag.body.client_price) setPreisGleich(out.price_match ?? null);
        for (const callback of auftrag.danach) callback();
      } catch (error) {
        const problem = problemOf(error);
        // Nach einem Fehler gilt wieder die Revision der Abfrage (nach einem Konflikt neu geladen)
        z.revision = null;
        setFehler({ art: artOf(auftrag.body), problem, slug: auftrag.body.template_slug ?? null });
        if (problem?.code === "revision_conflict") {
          z.wartend = null;
          onKonflikt();
        }
      }
    }
    z.laeuft = false;
    setLaeuft(false);
  };

  const senden = (body: HouseConfigurationPatch, danach?: () => void) => {
    const z = zustand.current;
    const typ = body.template_slug !== undefined;
    const vorher = typ ? null : z.wartend;
    z.wartend = {
      body: vorher ? { ...vorher.body, ...body } : body,
      danach: [...(vorher?.danach ?? []), ...(danach ? [danach] : [])],
    };
    if (!z.laeuft) void abarbeiten(revision);
  };

  return { laeuft, fehler, preisGleich, senden };
}
