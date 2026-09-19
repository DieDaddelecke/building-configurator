/**
 * Implantation (Plan H2 4.4, Spez. 8.2): Das Haus lässt sich auf dem Lageplan ziehen und drehen. Beim Ziehen
 * prüft der Browser lokal gegen die Fläche zulässiger Ursprünge; beim Loslassen entscheidet der Server
 * (`PATCH /configuration`) und liefert alle Prüfungen je Kante. Tastatur: Pfeile verschieben, R dreht.
 * Die Seite gibt `key={revision}` mit: Ein neuer Stand vom Server ersetzt den Entwurf.
 */

import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  problemOf,
  usePatchConfiguration,
  usePlacementArea,
  usePresets,
  type CheckOut,
  type ConfigurationOut,
  type PresetName,
} from "../api/configuration";
import type { EnvelopeOut } from "../api/envelope";
import type { SiteOut } from "../api/site";
import { Nordpfeil, strich, txt } from "../components/plan/Masskette";
import { Planblatt } from "../components/plan/Planblatt";
import { PlanSvg, boundsOf, polygonPath, ringPath, toSvg, type LocalPoint } from "../components/plan/PlanSvg";
import { EDGE_COLORS, formatNumber, midpoint } from "../site/geo";
import { checkText, edgeName, requiredText, sortChecks, STATUS_TONE } from "./format";
import { GRID_M, centroid, dragTo, nearestInside, originKeepingCentre, placeRing, type Pt, type Ring } from "./geometry";

const PRESETS: readonly PresetName[] = ["street_near", "set_back", "garden_max"];
const COMMIT_DELAY_MS = 350;

const rings = (value: unknown) => (value ?? []) as unknown as Ring[];
const sameAngle = (a: number, b: number) => Math.abs(((a - b + 540) % 360) - 180) < 0.1;

interface Draft {
  origin: Pt;
  rotation: number;
}

interface ImplantationProps {
  projectId: string;
  site: SiteOut;
  configuration: ConfigurationOut;
  envelope?: EnvelopeOut | null;
}

export function Implantation({ projectId, site, configuration, envelope = null }: ImplantationProps) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const type = configuration.type;
  const facts = configuration.fit?.facts;
  const saved = configuration.placement;
  const savedOrigin: Pt | null = saved ? [saved.origin.e, saved.origin.n] : null;

  const [draft, setDraft] = useState<Draft | null>(null);
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const [focused, setFocused] = useState(false);
  const patch = usePatchConfiguration(projectId);
  const presets = usePresets(projectId);
  const area = usePlacementArea(projectId, type?.slug, configuration.boundary_options);
  const drag = useRef<{ grab: Pt } | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latest = useRef<Draft | null>(null);

  const origin = draft?.origin ?? savedOrigin;
  const rotation = draft?.rotation ?? saved?.rotation_deg ?? configuration.rotations[0] ?? 0;

  useEffect(() => () => void (timer.current && clearTimeout(timer.current)), []);

  const areaRings = (angle: number): Ring[] => {
    const entry = area.data?.rotations.find((r) => sameAngle(r.rotation_deg, angle));
    return entry ? rings(entry.rings_local) : [];
  };

  const commit = (next: Draft) => {
    patch.mutate({
      body: { placement: { origin: { e: next.origin[0], n: next.origin[1] }, rotation_deg: next.rotation } },
      revision: configuration.revision,
    });
  };

  const scheduleCommit = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      if (latest.current) commit(latest.current);
    }, COMMIT_DELAY_MS);
  };

  const localPoint = (event: PointerEvent<SVGGElement>): Pt | null => {
    const svg = event.currentTarget.ownerSVGElement;
    const matrix = svg?.getScreenCTM?.();
    if (!svg || !matrix || typeof svg.createSVGPoint !== "function") return null;
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const local = point.matrixTransform(matrix.inverse());
    return [local.x, -local.y];
  };

  const onPointerDown = (event: PointerEvent<SVGGElement>) => {
    const pointer = localPoint(event);
    if (!pointer || !origin) return;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    drag.current = { grab: [pointer[0] - origin[0], pointer[1] - origin[1]] };
  };

  const onPointerMove = (event: PointerEvent<SVGGElement>) => {
    const pointer = localPoint(event);
    if (!drag.current || !pointer || !origin) return;
    const target: Pt = [pointer[0] - drag.current.grab[0], pointer[1] - drag.current.grab[1]];
    const next = dragTo(target, origin, areaRings(rotation));
    latest.current = { origin: next, rotation };
    setDraft({ origin: next, rotation });
  };

  const onPointerUp = () => {
    if (!drag.current) return;
    drag.current = null;
    if (latest.current) commit(latest.current);
  };

  const rotate = () => {
    const list = configuration.rotations;
    if (list.length < 2 || !origin || !facts) return;
    const centre = centroid(rings([facts.facade_local])[0]!);
    const start = Math.max(0, list.findIndex((r) => sameAngle(r, rotation)));
    for (let step = 1; step <= list.length; step++) {
      const next = list[(start + step) % list.length]!;
      const spot = nearestInside(originKeepingCentre(centre, origin, rotation, next), areaRings(next));
      if (spot) {
        commit({ origin: spot, rotation: next });
        return;
      }
    }
  };

  const onKeyDown = (event: KeyboardEvent<SVGGElement>) => {
    if (!origin) return;
    if (event.key === "r" || event.key === "R") {
      event.preventDefault();
      rotate();
      return;
    }
    const step = event.shiftKey ? 1 : GRID_M;
    const delta: Record<string, Pt> = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, step], ArrowDown: [0, -step] };
    const move = delta[event.key];
    if (!move) return;
    event.preventDefault();
    const next = dragTo([origin[0] + move[0], origin[1] + move[1]], origin, areaRings(rotation));
    setDraft({ origin: next, rotation });
    latest.current = { origin: next, rotation };
    scheduleCommit();
  };

  const applyPreset = async (name: PresetName) => {
    if (!type) return;
    const result = await presets.mutateAsync(type.slug);
    const found = result.presets[name];
    if (found) commit({ origin: [found.origin.e, found.origin.n], rotation: found.rotation_deg });
  };

  const toggleBoundary = (seq: number, on: boolean) => {
    const options = { ...configuration.boundary_options, [String(seq)]: on };
    for (const key of Object.keys(options)) if (!options[key]) delete options[key];
    patch.mutate({ body: { boundary_options: options }, revision: configuration.revision });
  };

  const outline = rings(site.outline_local);
  const bounds = boundsOf(outline.flat() as unknown as LocalPoint[]);
  const size = Math.max(bounds.maxE - bounds.minE, bounds.maxN - bounds.minN, 10);
  const rand = Math.max(6, size * 0.18);
  const label = size / 45;
  const [northX, northY] = toSvg([bounds.maxE + rand * 0.55, bounds.maxN + rand * 0.35]);
  const evaluation = configuration.evaluation;

  const house = useMemo(() => {
    if (!facts || !origin) return null;
    const facade = placeRing(rings([facts.facade_local])[0]!, origin, rotation);
    const projection = placeRing(rings([facts.projection_local])[0]!, origin, rotation);
    const points = facade.slice(0, -1);
    const street = Object.entries(facts.facade_roles)
      .filter(([, role]) => role === "street")
      .map(([index]) => Number(index))
      .filter((index) => index < points.length)
      .map((index) => [points[index]!, points[(index + 1) % points.length]!] as const);
    return { facade, projection, street };
  }, [facts, origin, rotation]);

  const problem = problemOf(patch.error);
  const refusedChecks = (problem?.checks ?? problem?.reasons ?? []).filter((c) => c.status === "fail");
  const sorted = sortChecks(evaluation?.checks ?? []);
  const failing = sorted.filter((c) => c.status === "fail" && c.binding);
  const boundaryEdges = evaluation?.edges.filter((e) => e.on_boundary_allowed) ?? [];
  const noArea = area.isSuccess && !area.data.rotations.some((r) => r.area_m2 > 0);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
      <div className="lg:col-span-4 flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <div className="eyebrow">{t("configurator.placement.presets")}</div>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((name) => (
              <button
                key={name}
                type="button"
                className="chip"
                disabled={presets.isPending || patch.isPending}
                onClick={() => void applyPreset(name)}
              >
                {t(`configurator.placement.preset.${name}`)}
              </button>
            ))}
          </div>
          {presets.isSuccess && PRESETS.every((name) => presets.data.presets[name] == null) && (
            <p className="text-sm t-warn m-0">{t("configurator.placement.noPreset")}</p>
          )}
          <div className="flex flex-wrap items-center gap-3 mt-2">
            <button type="button" className="btn btn-ghost" onClick={rotate} disabled={configuration.rotations.length < 2 || patch.isPending}>
              {t("configurator.placement.rotate")}
            </button>
            <span className="text-sm t-mute">
              {t("configurator.placement.rotation", {
                index: Math.max(0, configuration.rotations.findIndex((r) => sameAngle(r, rotation))) + 1,
                count: configuration.rotations.length,
              })}
            </span>
          </div>
        </div>

        {boundaryEdges.length > 0 && (
          <fieldset className="flex flex-col gap-2 border-0 p-0 m-0">
            <legend className="eyebrow p-0">{t("configurator.placement.boundary")}</legend>
            <p className="text-xs t-mute m-0">{t("configurator.placement.boundaryHint")}</p>
            {boundaryEdges.map((edge) => (
              <label key={edge.seq} className="flex items-center gap-2 text-sm t-ink">
                <input
                  type="checkbox"
                  checked={Boolean(configuration.boundary_options[String(edge.seq)])}
                  disabled={patch.isPending}
                  onChange={(event) => toggleBoundary(edge.seq, event.target.checked)}
                />
                {t("configurator.placement.boundaryEdge", { edge: edgeName(edge.kind, edge.seq, t) })}
              </label>
            ))}
          </fieldset>
        )}

        <div role="status" aria-live="polite" className={`px-4 py-3 text-sm ${failing.length ? "bg-alert t-ink" : "bg-sheet border bd t-mute"}`}>
          {patch.isPending && t("configurator.placement.saving")}
          {!patch.isPending && problem?.code === "revision_conflict" && t("configurator.placement.conflict")}
          {!patch.isPending && problem && problem.code !== "revision_conflict" && (
            <>
              <span className="t-alert font-medium">{t("configurator.placement.refused")}</span>
              {refusedChecks.length > 0 && (
                <ul className="m-0 mt-1 pl-5 flex flex-col gap-1">
                  {refusedChecks.map((check, index) => (
                    <li key={`${check.code}-${index}`}>{checkText(check, t, lng)}</li>
                  ))}
                </ul>
              )}
            </>
          )}
          {!patch.isPending && !problem && (failing.length
            ? t("configurator.placement.violated")
            : evaluation
              ? t("configurator.placement.valid")
              : t("configurator.placement.noPreset"))}
          {!patch.isPending && !problem && failing.length > 0 && (
            <ul className="m-0 mt-1 pl-5 flex flex-col gap-1">
              {failing.map((check, index) => (
                <li key={`${check.code}-${index}`}>{checkText(check, t, lng)}</li>
              ))}
            </ul>
          )}
        </div>
        {noArea && <p className="text-sm t-warn m-0">{t("configurator.check.no_valid_position")}</p>}
        {type?.retired && <p className="text-sm t-warn m-0">{t("configurator.placement.retired")}</p>}

        {evaluation && evaluation.edges.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse" data-testid="abstaende">
              <caption className="eyebrow text-left pb-2">{t("configurator.placement.distances")}</caption>
              <thead>
                <tr className="text-left border-b bd-strong">
                  <th scope="col" className="py-1 pr-3 font-medium">{t("configurator.placement.column.edge")}</th>
                  <th scope="col" className="py-1 pr-3 font-medium">{t("configurator.placement.column.measured")}</th>
                  <th scope="col" className="py-1 font-medium">{t("configurator.placement.column.required")}</th>
                </tr>
              </thead>
              <tbody>
                {evaluation.edges.map((edge) => (
                  <tr
                    key={edge.seq}
                    className="border-b bd"
                    onMouseEnter={() => setHighlighted(edge.seq)}
                    onMouseLeave={() => setHighlighted(null)}
                  >
                    <th scope="row" className="py-1 pr-3 font-normal text-left">{edgeName(edge.kind, edge.seq, t)}</th>
                    <td className={`py-1 pr-3 num ${edge.status === "fail" ? "t-alert" : "t-ink"}`}>{formatNumber(edge.measured_m, lng, 2)} m</td>
                    <td className="py-1 num t-mute">{requiredText(edge, t, lng)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {evaluation && (
          <details className="text-sm">
            <summary className="cursor-pointer eyebrow t-accent">{t("configurator.placement.checks")}</summary>
            <ul className="m-0 mt-2 pl-5 flex flex-col gap-1" data-testid="pruefungen">
              {sorted.map((check: CheckOut, index) => (
                <li key={`${check.code}-${check.edge_seq ?? ""}-${index}`} className={STATUS_TONE[check.status]}>
                  {checkText(check, t, lng)} <span className="t-faint">· {t(`configurator.status.${check.status}`)}</span>
                </li>
              ))}
            </ul>
          </details>
        )}
        <p className="text-xs t-faint m-0">{t("configurator.placement.keyboard")}</p>
      </div>

      <div className="lg:col-span-8">
        <Planblatt
          inhalt={t("configurator.placement.plan")}
          schriftfeld={[
            { label: t("sheet.parcel"), wert: site.parcels.map((p) => `${p.section} ${Number(p.number)}`).join(" + ") || "–" },
            { label: t("configurator.types.fact.footprint"), wert: facts ? `${formatNumber(facts.footprint_m2, lng, 0)} m²` : "–" },
          ]}
        >
          <PlanSvg bounds={bounds} rand={rand} label={t("configurator.placement.planLabel")}>
            <path d={polygonPath(outline as unknown as LocalPoint[][])} fillRule="evenodd" style={{ fill: "var(--sheet)", fillOpacity: 0.9, stroke: "var(--ink)", strokeWidth: size / 400 }} />
            {envelope?.contours.lenient && (
              <path
                d={polygonPath(rings(envelope.contours.lenient.rings_local) as unknown as LocalPoint[][])}
                fillRule="evenodd"
                aria-hidden="true"
                style={strich("var(--accent)", size / 300, { fill: "var(--accent)", fillOpacity: 0.06, strokeDasharray: `${size / 70} ${size / 110}` })}
              />
            )}
            {site.edges.map((edge) => {
              const coords = edge.coords_local as unknown as LocalPoint[];
              if (coords.length < 2) return null;
              const measure = evaluation?.edges.find((e) => e.seq === edge.seq);
              const [mx, my] = toSvg(midpoint(coords));
              const active = highlighted === edge.seq;
              return (
                <g key={edge.seq}>
                  <path
                    d={coords.map((p, i) => `${i ? "L" : "M"}${toSvg(p)[0].toFixed(3)} ${toSvg(p)[1].toFixed(3)}`).join("")}
                    style={strich(EDGE_COLORS[edge.kind], ((active ? 2.2 : 1) * size) / 140, { strokeLinecap: "round" })}
                  />
                  {measure && (
                    <text
                      x={mx}
                      y={my - label * 0.4}
                      textAnchor="middle"
                      style={txt(measure.status === "fail" ? "var(--alert)" : "var(--mute)", label * 0.95, { fontWeight: measure.status === "fail" ? 600 : 400 })}
                    >
                      {formatNumber(measure.measured_m, lng, 2)}
                    </text>
                  )}
                </g>
              );
            })}
            {house && (
              <g
                data-testid="haus"
                tabIndex={0}
                role="button"
                aria-label={type?.name}
                style={{ cursor: "grab", touchAction: "none", outline: "none" }}
                onFocus={() => setFocused(true)}
                onBlur={() => setFocused(false)}
                onPointerDown={onPointerDown}
                onPointerMove={onPointerMove}
                onPointerUp={onPointerUp}
                onPointerCancel={onPointerUp}
                onKeyDown={onKeyDown}
              >
                <path d={ringPath(house.projection as unknown as LocalPoint[])} style={strich("var(--faint)", size / 400, { strokeDasharray: `${size / 120} ${size / 160}`, fill: "var(--accent)", fillOpacity: 0.04 })} />
                <path
                  d={ringPath(house.facade as unknown as LocalPoint[])}
                  style={{ fill: failing.length ? "var(--alert-tint)" : "var(--accent-tint)", stroke: failing.length ? "var(--alert)" : focused ? "var(--accent)" : "var(--ink)", strokeWidth: focused ? size / 120 : size / 220 }}
                />
                {house.street.map(([a, b], index) => {
                  const [x1, y1] = toSvg(a);
                  const [x2, y2] = toSvg(b);
                  return <line key={index} x1={x1} y1={y1} x2={x2} y2={y2} style={{ stroke: "var(--accent)", strokeWidth: size / 110 }} />;
                })}
              </g>
            )}
            <g transform={`translate(${northX} ${northY}) scale(${size / 45})`}>
              <Nordpfeil x={0} y={0} />
            </g>
          </PlanSvg>
        </Planblatt>
      </div>
    </div>
  );
}
