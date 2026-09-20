/**
 * Schritt Vorentwurf (Plan H3 4.4): Alle Angaben auf einem Blatt – Lageplan mit Nebenbauten, Auswahl, Flächen,
 * Himmelsrichtung, Energie und Prüfungen. Eine unverbindliche Simulation (D11, L7). Darunter die Übergabe an
 * das Büro (Modul V); ohne Flag `submission` bleibt der Verweis auf die Anfrage der Grundstücksseite (A).
 */

import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import type { ConfigurationOut, OptionsOut } from "../api/configuration";
import type { SiteOut } from "../api/site";
import { Nordpfeil } from "../components/plan/Masskette";
import { Planblatt } from "../components/plan/Planblatt";
import { PlanSvg, boundsOf, polygonPath, ringPath, toSvg, type LocalPoint } from "../components/plan/PlanSvg";
import { formatNumber } from "../site/geo";
import { EnergieHinweis } from "./Linien";
import { Nebenbauten } from "./Nebenbauten";
import { Uebergabe } from "./Uebergabe";
import { checkText, compassKey, localLabel, sortChecks, STATUS_TONE } from "./format";

export type DesignStep = "type" | "placement" | "package" | "options";

const rings = (value: unknown) => (value ?? []) as unknown as LocalPoint[][];

function Abschnitt({ titel, onGehe, schritt, children }: { titel: string; onGehe?: (step: DesignStep) => void; schritt?: DesignStep; children: React.ReactNode }) {
  const { t } = useTranslation();
  return (
    <div className="grid grid-cols-12 gap-4 py-4 border-t bd">
      <div className="col-span-12 sm:col-span-3 eyebrow pt-0.5">{titel}</div>
      <div className="col-span-10 sm:col-span-7 text-sm t-ink flex flex-col gap-1">{children}</div>
      <div className="col-span-2 text-right">
        {onGehe && schritt && (
          <button type="button" className="link text-sm" onClick={() => onGehe(schritt)}>
            {t("configurator.design.change")}
          </button>
        )}
      </div>
    </div>
  );
}

interface VorentwurfProps {
  site: SiteOut;
  configuration: ConfigurationOut;
  options: OptionsOut | null;
  onGehe: (step: DesignStep) => void;
  /** Flag `submission`: Übergabe an das Büro (V) statt des Verweises auf die Grundstücksseite. */
  submissionEnabled?: boolean;
}

export function Vorentwurf({ site, configuration, options, onGehe, submissionEnabled = false }: VorentwurfProps) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const selection = configuration.selection;
  const areas = configuration.areas;
  const evaluation = configuration.evaluation;
  const names: Record<string, string> = {};
  for (const item of [...(options?.packages ?? []), ...(options?.options ?? [])]) names[item.slug] = localLabel(item, lng);

  const outline = rings(site.outline_local);
  const bounds = boundsOf(outline.flat());
  const size = Math.max(bounds.maxE - bounds.minE, bounds.maxN - bounds.minN, 10);
  const rand = Math.max(6, size * 0.18);
  const [northX, northY] = toSvg([bounds.maxE + rand * 0.55, bounds.maxN + rand * 0.35]);
  const facade = rings([evaluation?.facade_local])[0] ?? null;
  const projection = rings([evaluation?.projection_local])[0] ?? null;
  const checks = sortChecks(configuration.compliance?.checks ?? []);
  const orientation = configuration.orientation;
  const chosenOptions = [...(selection?.option_slugs ?? []), ...(selection?.included_slugs ?? []).filter((s) => !selection?.option_slugs.includes(s))];
  const areaRows: [string, number | undefined][] = [
    ["site", areas?.site_m2],
    ["house", areas?.house_m2],
    ["carport", areas && areas.carport_m2 > 0 ? areas.carport_m2 : undefined],
    ["terrace", areas && areas.terrace_m2 > 0 ? areas.terrace_m2 : undefined],
    ["driveway", areas && areas.driveway_m2 > 0 ? areas.driveway_m2 : undefined],
    ["paths", areas?.paths_m2],
    ["emprise", areas?.emprise_m2],
    ["sealed", areas?.sealed_m2],
    ["unsealed", areas?.unsealed_m2],
  ];

  return (
    <div className="flex flex-col gap-8" data-testid="vorentwurf">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        <div className="lg:col-span-5">
          <Planblatt
            inhalt={t("configurator.design.plan")}
            schriftfeld={[{ label: t("sheet.parcel"), wert: site.parcels.map((p) => `${p.section} ${Number(p.number)}`).join(" + ") || "–" }]}
          >
            <PlanSvg bounds={bounds} rand={rand} label={t("configurator.design.planLabel")}>
              <path d={polygonPath(outline)} fillRule="evenodd" style={{ fill: "var(--sheet)", fillOpacity: 0.9, stroke: "var(--ink)", strokeWidth: size / 400 }} />
              <Nebenbauten outbuildings={configuration.outbuildings} size={size} />
              {projection && <path d={ringPath(projection)} style={{ fill: "var(--accent)", fillOpacity: 0.04, stroke: "var(--faint)", strokeWidth: size / 400, strokeDasharray: `${size / 120} ${size / 160}` }} />}
              {facade && <path d={ringPath(facade)} style={{ fill: "var(--accent-tint)", stroke: "var(--ink)", strokeWidth: size / 220 }} />}
              <g transform={`translate(${northX} ${northY}) scale(${size / 45})`}>
                <Nordpfeil x={0} y={0} />
              </g>
            </PlanSvg>
          </Planblatt>
        </div>
        <div className="lg:col-span-7 border-b bd">
          <Abschnitt titel={t("configurator.design.site")}>
            <span>{site.parcels.map((p) => `${p.section} ${Number(p.number)}`).join(" + ") || "–"}</span>
            {areas && <span className="t-mute num">{formatNumber(areas.site_m2, lng, 0)} m²</span>}
          </Abschnitt>
          <Abschnitt titel={t("configurator.design.type")} onGehe={onGehe} schritt="type">
            <span>{configuration.type?.name}</span>
            {configuration.fit && (
              <span className="t-mute">
                {formatNumber(configuration.fit.facts.footprint_m2, lng, 0)} m² · {formatNumber(configuration.fit.facts.living_area_m2, lng, 0)} m² · {configuration.fit.facts.rooms_text}
              </span>
            )}
          </Abschnitt>
          <Abschnitt titel={t("configurator.design.package")} onGehe={onGehe} schritt="package">
            <span>{selection?.package_slug ? (names[selection.package_slug] ?? selection.package_slug) : t("configurator.design.noPackage")}</span>
          </Abschnitt>
          <Abschnitt titel={t("configurator.design.options")} onGehe={onGehe} schritt="options">
            {chosenOptions.length === 0 && <span className="t-mute">{t("configurator.design.noOptions")}</span>}
            {chosenOptions.map((slug) => (
              <span key={slug}>
                {names[slug] ?? slug}
                {selection?.included_slugs.includes(slug) && <span className="t-mute"> · {t("configurator.options.included")}</span>}
              </span>
            ))}
          </Abschnitt>
          <Abschnitt titel={t("configurator.design.placement")} onGehe={onGehe} schritt="placement">
            {orientation &&
              (["garden", "street"] as const).flatMap((role) =>
                orientation.facades[role] != null
                  ? [
                      <span key={role}>
                        {t(`configurator.design.facade.${role}`)}: {t(`configurator.compass.${compassKey(orientation.facades[role]!)}`)} ({formatNumber(orientation.facades[role]!, lng, 0)}°)
                      </span>,
                    ]
                  : [],
              )}
            {orientation && <span className="text-xs t-mute">{t("configurator.design.convergenceNote", { deg: formatNumber(orientation.convergence_deg, lng, 1) })}</span>}
          </Abschnitt>
        </div>
      </div>

      {configuration.energy && configuration.selection?.package_slug && <EnergieHinweis energy={configuration.energy} />}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <section aria-labelledby="vorentwurf-flaechen">
          <h3 id="vorentwurf-flaechen" className="eyebrow pb-2">{t("configurator.design.areas")}</h3>
          <table className="w-full text-sm border-collapse" data-testid="flaechen">
            <tbody>
              {areaRows
                .filter(([, value]) => value != null)
                .map(([key, value]) => (
                  <tr key={key} className="border-t bd">
                    <th scope="row" className="py-1 pr-3 text-left font-normal">{t(`configurator.design.area.${key}`)}</th>
                    <td className="py-1 text-right num">{formatNumber(value!, lng, 1)} m²</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </section>
        <section aria-labelledby="vorentwurf-pruefungen">
          <h3 id="vorentwurf-pruefungen" className="eyebrow pb-2">{t("configurator.design.checks")}</h3>
          {checks.length === 0 ? (
            <p className="text-sm t-mute m-0">{t("configurator.design.noChecks")}</p>
          ) : (
            <ul className="m-0 pl-5 text-sm flex flex-col gap-1" data-testid="vorentwurf-pruefungen">
              {checks.map((check, index) => (
                <li key={`${check.code}-${check.zone_code ?? ""}-${index}`} className={STATUS_TONE[check.status]}>
                  {checkText(check, t, lng, names)} <span className="t-faint">· {t(`configurator.status.${check.status}`)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {submissionEnabled ? (
        <Uebergabe projectId={site.project_id} configuration={configuration} names={names} />
      ) : (
        <p className="bg-tint t-ink px-4 py-3 text-sm m-0 max-w-prose">
          {t("configurator.design.next")}{" "}
          <Link className="link" to="/grundstueck">{t("configurator.design.request")}</Link>
        </p>
      )}
    </div>
  );
}
