/**
 * Implantation (Plan H2 4.4, Spez. 8.2): der Lageplan mit den Daten des Konfigurators. Beim Loslassen entscheidet
 * der Server (`PATCH /configuration`); eine Lage mit bindendem Verstoß lehnt er ab (D12).
 * Die Seite gibt `key={revision}` mit: Ein neuer Stand vom Server ersetzt den Entwurf.
 */

import { problemOf, usePatchConfiguration, usePlacementArea, usePresets, type ConfigurationOut } from "../api/configuration";
import type { EnvelopeOut } from "../api/envelope";
import type { SiteOut } from "../api/site";
import { Lageplan, type Lage } from "./Lageplan";
import { Nebenbauten } from "./Nebenbauten";

interface ImplantationProps {
  projectId: string;
  site: SiteOut;
  configuration: ConfigurationOut;
  envelope?: EnvelopeOut | null;
  /** Bezeichnungen von Linien und Optionen für die Texte der Prüfungen (Plan H3 4.4) */
  names?: Record<string, string>;
}

export function Implantation({ projectId, site, configuration, envelope = null, names = {} }: ImplantationProps) {
  const type = configuration.type;
  const patch = usePatchConfiguration(projectId);
  const presets = usePresets(projectId);
  const area = usePlacementArea(projectId, type?.slug, configuration.boundary_options);
  const revision = configuration.revision;

  const place = ({ origin, rotation }: Lage) =>
    patch.mutate({ body: { placement: { origin: { e: origin[0], n: origin[1] }, rotation_deg: rotation } }, revision });

  return (
    <Lageplan
      site={site}
      envelope={envelope}
      haus={{
        name: type?.name ?? "",
        retired: Boolean(type?.retired),
        facts: configuration.fit?.facts ?? null,
        placement: configuration.placement ?? null,
        rotations: configuration.rotations,
        evaluation: configuration.evaluation ?? null,
        boundaryOptions: configuration.boundary_options,
      }}
      area={area.data}
      presets={{ pending: presets.isPending, result: presets.data, load: () => presets.mutateAsync(type?.slug ?? "") }}
      pending={patch.isPending}
      problem={problemOf(patch.error)}
      onPlace={place}
      onBoundary={(options) => patch.mutate({ body: { boundary_options: options }, revision })}
      names={names}
      overlay={(size) => <Nebenbauten outbuildings={configuration.outbuildings} size={size} />}
    />
  );
}
