/**
 * Lage des Hauses (HM4): der gemeinsame Lageplan mit den Daten des Hausmodells, dazu Terrasse, Carport und Zufahrt,
 * wie der Server sie gesetzt hat (Ergänzung 7, HM5). Eine Lage mit Verstoß wird
 * gespeichert und als Abweichung ausgewiesen (E-HM-6); gibt es eine zulässige Lage in der Nähe, lässt sie sich
 * übernehmen (Ergänzung 9). Gespeichert wird über die Seite, damit alle Änderungen nacheinander laufen.
 * Die Seite gibt `key={revision}` mit: Ein neuer Stand vom Server ersetzt den Entwurf des Plans.
 */

import { useTranslation } from "react-i18next";

import type { ConfigurationProblem } from "../api/configuration";
import type { EnvelopeOut } from "../api/envelope";
import { useHousePlacementArea, useHousePresets, type HouseConfigurationOut } from "../api/hausKonfiguration";
import type { SiteOut } from "../api/site";
import { Lageplan, type Lage } from "../configuration/Lageplan";
import { Nebenbauten } from "../configuration/Nebenbauten";
import { label } from "./texte";

interface HausLageProps {
  projectId: string;
  site: SiteOut;
  current: HouseConfigurationOut;
  envelope: EnvelopeOut | null;
  pending: boolean;
  /** Ablehnung der letzten Lage oder Grenzschalter (z. B. eine Drehung außer den vier zur Straße). */
  problem: ConfigurationProblem | null;
  onPlace: (lage: Lage) => void;
  onBoundary: (options: Record<string, boolean>) => void;
  names: Record<string, string>;
}

export function HausLage({ projectId, site, current, envelope, pending, problem, onPlace, onBoundary, names }: HausLageProps) {
  const { t, i18n } = useTranslation();
  const area = useHousePlacementArea(projectId, current);
  const presets = useHousePresets(projectId);
  const suggestion = current.suggestion;

  return (
    <Lageplan
      site={site}
      envelope={envelope}
      haus={{
        name: current.template ? label(current.template.name, i18n.language) : "",
        // Den Hinweis auf eine zurückgezogene Version zeigt die Seite oben
        retired: false,
        facts: current.facts ?? null,
        placement: current.placement ?? null,
        rotations: current.rotations,
        evaluation: current.evaluation ?? null,
        boundaryOptions: current.boundary_options,
      }}
      area={area.data}
      presets={{ pending: presets.isPending, result: presets.data, load: () => presets.mutateAsync() }}
      pending={pending}
      problem={problem}
      onPlace={onPlace}
      onBoundary={onBoundary}
      names={names}
      overlay={(size) => <Nebenbauten outbuildings={current.outbuildings} size={size} />}
      meldung={
        suggestion && !pending ? (
          <span className="flex flex-col gap-2 mt-2">
            <span>{t("houseConfigurator.suggestion.text")}</span>
            <button
              type="button"
              className="btn btn-ghost self-start"
              data-testid="vorschlag"
              onClick={() => onPlace({ origin: [suggestion.origin.e, suggestion.origin.n], rotation: suggestion.rotation_deg })}
            >
              {t("houseConfigurator.suggestion.apply")}
            </button>
          </span>
        ) : null
      }
    />
  );
}
