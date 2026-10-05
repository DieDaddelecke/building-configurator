/**
 * Entwurf eines Haustyps (docs/PLAN_HAUSMODELL.md 3.6 Nr. 5, E-HM-11, E-HM-13, E-HM-37): Was der Import
 * vorschlägt, bestätigt oder ergänzt das Büro. Ohne Angabe gilt der Vorschlag; gespeichert werden nur die
 * Angaben, Entwurf und Bericht bildet der Server daraus neu.
 */

import type { TFunction } from "i18next";
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type {
  FacadeRole,
  HouseCatalogChoicesOut,
  HouseDraftDecisions,
  HouseImportReport,
  HouseTemplate,
  HouseText,
} from "../../api/haus";
import { number } from "../../katalog/bausteine";
import { label } from "../texte";
import { areaOf } from "./Vorschau";

export const IGNORE = "ignore";
const FACADE_ROLES: FacadeRole[] = ["street", "garden", "side_left", "side_right"];

function withKey<T>(record: Record<string, T>, key: string, value: T | undefined): Record<string, T> {
  const next = { ...record };
  if (value === undefined) delete next[key];
  else next[key] = value;
  return next;
}

/** Name in beiden Sprachen oder keiner (D7). */
export const nameIncomplete = (decisions: HouseDraftDecisions) =>
  decisions.name !== null && (decisions.name.fr.trim() === "" || decisions.name.de.trim() === "");

interface SectionProps {
  id: string;
  title: string;
  intro?: string;
  children: ReactNode;
}

function Abschnitt({ id, title, intro, children }: SectionProps) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3">
      <h4 id={id} className="m-0 text-lg font-medium">
        {title}
      </h4>
      {intro && <p className="m-0 text-sm t-mute max-w-prose">{intro}</p>}
      {children}
    </section>
  );
}

interface EntwurfProps {
  template: HouseTemplate | null;
  report: HouseImportReport;
  catalog: HouseCatalogChoicesOut;
  /** Gespeicherte Angaben: Ihre Zeilen bleiben stehen, auch wenn der Bericht den Punkt nicht mehr nennt. */
  saved: HouseDraftDecisions;
  draft: HouseDraftDecisions;
  onChange: (draft: HouseDraftDecisions) => void;
  editable: boolean;
  onHighlight: (ids: string[]) => void;
}

export function Entwurf(props: EntwurfProps) {
  return (
    <div className="flex flex-col gap-8">
      <Allgemein {...props} />
      <Zonen {...props} />
      <Raeume {...props} />
      {props.template && <Fassade {...props} template={props.template} />}
      {props.template && <Tueren {...props} template={props.template} />}
      {props.template && <Dach {...props} template={props.template} />}
      <Standards {...props} />
      <Oeffnungen {...props} />
    </div>
  );
}

function RoomTypeSelect({
  value,
  catalog,
  empty,
  disabled,
  onChange,
  labelText,
}: {
  value: string | undefined;
  catalog: HouseCatalogChoicesOut;
  empty: string;
  disabled: boolean;
  onChange: (value: string | undefined) => void;
  labelText: string;
}) {
  const { t, i18n } = useTranslation();
  return (
    <select
      className="field"
      aria-label={labelText}
      value={value ?? ""}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value === "" ? undefined : e.target.value)}
    >
      <option value="">{empty}</option>
      {catalog.room_types.map((type) => (
        <option key={type.id} value={type.id}>
          {label(type.name, i18n.language)}
        </option>
      ))}
      <option value={IGNORE}>{t("house.draft.ignore")}</option>
    </select>
  );
}

function Allgemein({ template, draft, onChange, editable }: EntwurfProps) {
  const { t, i18n } = useTranslation();
  const name = draft.name ?? { fr: "", de: "" };
  const setName = (next: HouseText) =>
    onChange({ ...draft, name: next.fr === "" && next.de === "" ? null : next });
  return (
    <Abschnitt id="entwurf-allgemein" title={t("house.draft.general")}>
      <div className="grid gap-4 md:grid-cols-3 items-start">
        <label className="flex flex-col gap-1 text-sm">
          {t("house.draft.nameFr")}
          <input
            className="field"
            value={name.fr}
            placeholder={template?.name.fr}
            disabled={!editable}
            maxLength={500}
            onChange={(e) => setName({ ...name, fr: e.target.value })}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("house.draft.nameDe")}
          <input
            className="field"
            value={name.de}
            placeholder={template?.name.de}
            disabled={!editable}
            maxLength={500}
            onChange={(e) => setName({ ...name, de: e.target.value })}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("house.draft.groundFloorOffset")}
          <input
            className="field num"
            type="number"
            step="0.01"
            min={-5}
            max={5}
            value={draft.ground_floor_offset ?? ""}
            placeholder={template ? number(template.ground_floor_offset, i18n.language, 2) : undefined}
            disabled={!editable}
            onChange={(e) =>
              onChange({ ...draft, ground_floor_offset: e.target.value === "" ? null : Number(e.target.value) })
            }
          />
          <span className="text-xs t-mute">{t("house.draft.groundFloorOffsetHint")}</span>
        </label>
      </div>
      {nameIncomplete(draft) && <p className="m-0 text-sm t-alert">{t("house.draft.nameIncomplete")}</p>}
    </Abschnitt>
  );
}

function Zonen({ report, catalog, draft, onChange, editable, onHighlight }: EntwurfProps) {
  const { t, i18n } = useTranslation();
  if (report.zones.length === 0) return null;
  const roomName = (id: string | null) => {
    const type = catalog.room_types.find((r) => r.id === id);
    return type ? label(type.name, i18n.language) : (id ?? "–");
  };
  return (
    <Abschnitt id="entwurf-zonen" title={t("house.draft.zones")} intro={t("house.draft.zonesIntro")}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="text-left border-b bd-strong">
              <th scope="col" className="py-2 pr-3 font-medium">{t("house.draft.zoneValues")}</th>
              <th scope="col" className="py-2 pr-3 font-medium">{t("house.draft.zoneResult")}</th>
              <th scope="col" className="py-2 pr-3 font-medium text-right">{t("house.draft.zoneShare")}</th>
              <th scope="col" className="py-2 font-medium">{t("house.draft.decision")}</th>
            </tr>
          </thead>
          <tbody>
            {report.zones.map((zone) => (
              <tr
                key={zone.ifc_guid}
                className="border-b bd align-top"
                data-testid={`zone-${zone.ifc_guid}`}
                onMouseEnter={() => onHighlight(zone.room_id ? [zone.room_id] : [])}
                onMouseLeave={() => onHighlight([])}
              >
                <td className="py-2 pr-3">
                  <ul className="m-0 p-0 list-none">
                    {zone.values.map((value, i) => (
                      <li key={i}>
                        <span className="t-mute">{t(`house.source.${value.kind}`)}:</span>{" "}
                        <span className={value.raw === zone.raw ? "font-medium" : undefined}>{value.raw}</span>
                      </li>
                    ))}
                  </ul>
                  <span className="f-mono text-xs t-mute">{zone.ifc_guid}</span>
                </td>
                <td className="py-2 pr-3">
                  {zone.result === "room" ? roomName(zone.room_type_id) : t(`house.zoneResult.${zone.result}`)}
                  {zone.source && <div className="text-xs t-mute">{t(`house.source.${zone.source}`)}</div>}
                </td>
                <td className="py-2 pr-3 text-right num">
                  {zone.share !== null ? `${number(zone.share * 100, i18n.language, 0)} %` : "–"}
                </td>
                <td className="py-2">
                  <RoomTypeSelect
                    value={draft.zone_types[zone.ifc_guid]}
                    catalog={catalog}
                    empty={t("house.draft.recognition")}
                    disabled={!editable}
                    labelText={t("house.draft.zoneDecision", { guid: zone.ifc_guid })}
                    onChange={(value) => onChange({ ...draft, zone_types: withKey(draft.zone_types, zone.ifc_guid, value) })}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Abschnitt>
  );
}

function Raeume({ template, report, catalog, saved, draft, onChange, editable, onHighlight }: EntwurfProps) {
  const { t, i18n } = useTranslation();
  const ids = (codes: string[]) =>
    report.findings.filter((f) => codes.includes(f.code) && f.element_id).map((f) => f.element_id as string);
  const withoutZone = [
    ...new Set([
      ...ids(["room_without_zone", "room_ignored"]),
      ...Object.keys(saved.room_types),
      ...Object.keys(draft.room_types),
    ]),
  ];
  const splits = [...new Set([...ids(["room_split_unconfirmed"]), ...saved.confirmed_splits, ...draft.confirmed_splits])];
  if (withoutZone.length === 0 && splits.length === 0) return null;
  const area = (id: string) => {
    const finding = report.findings.find((f) => f.element_id === id && typeof f.params.area === "number");
    if (finding) return finding.params.area as number;
    const room = template?.rooms.find((r) => r.id === id);
    return room ? areaOf(room.polygon) : null;
  };
  return (
    <Abschnitt id="entwurf-raeume" title={t("house.draft.rooms")} intro={t("house.draft.roomsIntro")}>
      <ul className="m-0 p-0 list-none flex flex-col gap-2">
        {withoutZone.map((id) => {
          const size = area(id);
          return (
            <li
              key={id}
              className="flex gap-3 items-center flex-wrap"
              onMouseEnter={() => onHighlight([id])}
              onMouseLeave={() => onHighlight([])}
            >
              <span className="text-sm">
                {t("house.draft.roomWithoutZone")}
                {size !== null && <span className="num"> · {number(size, i18n.language, 2)} m²</span>}
              </span>
              <span className="f-mono text-xs t-mute">{id}</span>
              <RoomTypeSelect
                value={draft.room_types[id]}
                catalog={catalog}
                empty={t("house.draft.open")}
                disabled={!editable}
                labelText={t("house.draft.roomDecision", { id })}
                onChange={(value) => onChange({ ...draft, room_types: withKey(draft.room_types, id, value) })}
              />
            </li>
          );
        })}
        {splits.map((id) => (
          <li key={id} className="flex gap-3 items-center flex-wrap">
            <label className="flex gap-2 items-center text-sm">
              <input
                type="checkbox"
                checked={draft.confirmed_splits.includes(id)}
                disabled={!editable}
                onChange={(e) =>
                  onChange({
                    ...draft,
                    confirmed_splits: e.target.checked
                      ? [...draft.confirmed_splits, id]
                      : draft.confirmed_splits.filter((s) => s !== id),
                  })
                }
              />
              {t("house.draft.confirmSplit")}
            </label>
            <span className="f-mono text-xs t-mute">{id}</span>
          </li>
        ))}
      </ul>
    </Abschnitt>
  );
}

function Fassade({ draft, onChange, editable, onHighlight, template }: EntwurfProps & { template: HouseTemplate }) {
  const { t } = useTranslation();
  const segments = template.envelope.flatMap((loop) => loop.segments);
  return (
    <Abschnitt id="entwurf-fassade" title={t("house.draft.facadeRoles")} intro={t("house.draft.facadeRolesIntro")}>
      <ul className="m-0 p-0 list-none grid gap-2 md:grid-cols-2">
        {segments.map((segment, i) => (
          <li
            key={segment.id}
            className="flex gap-3 items-center"
            onMouseEnter={() => onHighlight([segment.id])}
            onMouseLeave={() => onHighlight([])}
          >
            <span className="f-mono text-sm w-24">
              {t("house.draft.segment")} {i}
            </span>
            <select
              className="field"
              aria-label={t("house.draft.segmentRole", { index: i })}
              value={draft.facade_roles[segment.id] ?? ""}
              disabled={!editable}
              onFocus={() => onHighlight([segment.id])}
              onBlur={() => onHighlight([])}
              onChange={(e) =>
                onChange({
                  ...draft,
                  facade_roles: withKey(
                    draft.facade_roles,
                    segment.id,
                    e.target.value === "" ? undefined : (e.target.value as FacadeRole),
                  ),
                })
              }
            >
              <option value="">{t("house.draft.noRole")}</option>
              {FACADE_ROLES.map((role) => (
                <option key={role} value={role}>
                  {t(`catalog.facadeRole.${role}`)}
                </option>
              ))}
            </select>
          </li>
        ))}
      </ul>
    </Abschnitt>
  );
}

const AUTO = "auto";
const NONE = "none";

function Tueren({ report, saved, draft, onChange, editable, template }: EntwurfProps & { template: HouseTemplate }) {
  const { t, i18n } = useTranslation();
  const segments = template.envelope.flatMap((loop) => loop.segments.map((s) => s.id));
  const doors = template.openings.filter((o) => o.kind === "door" && o.host_kind === "envelope_segment");
  const widths = new Map(report.openings.map((o) => [o.element_id, o.width]));
  const doorLabel = (id: string) => {
    const width = widths.get(id);
    const host = doors.find((door) => door.id === id)?.host_id;
    return [
      host !== undefined ? `${t("house.draft.segment")} ${segments.indexOf(host)}` : null,
      width ? `${number(width, i18n.language, 2)} m` : null,
      id.slice(-6),
    ]
      .filter(Boolean)
      .join(" · ");
  };
  const field = (key: "entrance" | "garage_door") => {
    const choice = draft[key];
    const value = choice === null ? AUTO : (choice.opening_id ?? NONE);
    // Der Entwurf zeigt den Vorschlag nur, solange auch gespeichert nichts gewählt ist
    const proposed =
      saved[key] === null ? (key === "entrance" ? template.entrance_opening_id : template.garage_door_opening_id) : null;
    return (
      <label className="flex flex-col gap-1 text-sm">
        {t(`house.draft.${key === "entrance" ? "entrance" : "garageDoor"}`)}
        <select
          className="field"
          value={value}
          disabled={!editable}
          onChange={(e) => {
            const next = e.target.value;
            onChange({ ...draft, [key]: next === AUTO ? null : { opening_id: next === NONE ? null : next } });
          }}
        >
          <option value={AUTO}>
            {t("house.draft.proposal")}
            {proposed ? `: ${doorLabel(proposed)}` : ""}
          </option>
          <option value={NONE}>{t("house.draft.none")}</option>
          {doors.map((door) => (
            <option key={door.id} value={door.id}>
              {doorLabel(door.id)}
            </option>
          ))}
        </select>
      </label>
    );
  };
  return (
    <Abschnitt id="entwurf-tueren" title={t("house.draft.doors")} intro={t("house.draft.doorsIntro")}>
      <div className="grid gap-4 md:grid-cols-2">
        {field("entrance")}
        {field("garage_door")}
      </div>
    </Abschnitt>
  );
}

type RoofPlacement = HouseTemplate["roof"];
type RoofForm = RoofPlacement["design"]["form"];
type PitchedForm = Exclude<RoofForm, "flat">;

const ROOF_FORMS: readonly PitchedForm[] = ["mono_pitch", "gable", "hip", "half_hip", "mansard", "mansard_gable"];
const ROTATIONS = [0, 90, 180, 270] as const;
const TWO_PART = new Set<RoofForm>(["half_hip", "mansard", "mansard_gable"]);

/** Startwerte beim Wechsel der Form, bis das Büro sie ändert; die Neigung bleibt, wenn es schon eine gibt. */
const START: Record<PitchedForm, { pitch: number; upper: number | null; breakHeight: number | null }> = {
  mono_pitch: { pitch: 15, upper: null, breakHeight: null },
  gable: { pitch: 35, upper: null, breakHeight: null },
  hip: { pitch: 30, upper: null, breakHeight: null },
  half_hip: { pitch: 40, upper: 60, breakHeight: 2 },
  mansard: { pitch: 70, upper: 25, breakHeight: 2.2 },
  mansard_gable: { pitch: 70, upper: 25, breakHeight: 2.2 },
};

/** Das Dach des Entwurfs in einer Zeile: Form, Neigungen, Auflager, Überstände, Drehung. */
export function roofSummary(roof: RoofPlacement, t: TFunction, lng: string): string {
  const design = roof.design;
  const form = t(`configurator.types.roof.${design.form}`, { defaultValue: design.form });
  if (design.form === "flat") {
    return t("house.draft.roofSummaryFlat", { form, parapet: number(roof.parapet_height, lng, 2), bearing: number(roof.bearing_height, lng, 2) });
  }
  const pitches = [design.pitch_deg, design.upper_pitch_deg]
    .filter((p): p is number => p !== null)
    .map((p) => `${number(p, lng, 1)}°`);
  return t("house.draft.roofSummary", {
    form,
    pitches: pitches.join(" / "),
    bearing: number(roof.bearing_height, lng, 2),
    eave: number(roof.eave_overhang, lng, 2),
    verge: number(roof.verge_overhang, lng, 2),
    rotation: design.rotation,
  });
}

/** Zahl mit eigenem Text während der Eingabe: Ein leeres Feld oder ein halber Wert ändert die Angabe nicht;
 * Schranken prüft der Server beim Speichern. */
function ZahlFeld({ label: text, value, step, disabled, onValue }: { label: string; value: number | null; step: string; disabled: boolean; onValue: (next: number) => void }) {
  const [entwurf, setEntwurf] = useState<string | null>(null);
  return (
    <label className="flex flex-col gap-1 text-sm">
      {text}
      <input
        className="field num"
        type="number"
        step={step}
        value={entwurf ?? value ?? ""}
        disabled={disabled}
        onChange={(e) => {
          setEntwurf(e.target.value);
          const next = Number(e.target.value);
          if (e.target.value !== "" && Number.isFinite(next)) onValue(next);
        }}
        onBlur={() => setEntwurf(null)}
      />
    </label>
  );
}

/**
 * Dach (E-HM-65): Der Import erkennt die Form aus der Dachgeometrie des IFC. Erkennt er sie nicht oder will das
 * Büro ein anderes geneigtes Dach, legt es Form und Maße hier fest; ein Flachdach braucht die Dachdecke aus dem IFC.
 */
function Dach({ draft, onChange, editable, template }: EntwurfProps & { template: HouseTemplate }) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const roof = draft.roof;
  const set = (next: RoofPlacement | null) => onChange({ ...draft, roof: next });
  const start = (): RoofPlacement => {
    if (template.roof.design.form !== "flat") return template.roof;
    return {
      bearing_height: template.roof.bearing_height,
      parapet_height: 0,
      eave_overhang: 0.5,
      verge_overhang: 0.3,
      design: { form: "gable", pitch_deg: START.gable.pitch, upper_pitch_deg: null, break_height: null, rotation: 0 },
    };
  };
  const withForm = (current: RoofPlacement, form: PitchedForm): RoofPlacement => {
    const two = TWO_PART.has(form);
    const design = current.design;
    return {
      ...current,
      design: {
        form,
        pitch_deg: design.pitch_deg ?? START[form].pitch,
        upper_pitch_deg: two ? (design.upper_pitch_deg ?? START[form].upper) : null,
        break_height: two ? (design.break_height ?? START[form].breakHeight) : null,
        rotation: design.rotation,
      },
    };
  };
  // Leere oder ungültige Eingaben ändern nichts; Schranken prüft der Server beim Speichern
  const field = (key: string, value: number | null, apply: (next: number) => RoofPlacement, step: string) => (
    <ZahlFeld label={t(`house.draft.${key}`)} value={value} step={step} disabled={!editable} onValue={(next) => set(apply(next))} />
  );
  return (
    <Abschnitt id="entwurf-dach" title={t("house.draft.roof")} intro={t("house.draft.roofIntro")}>
      <p className="m-0 text-sm" data-testid="dach-entwurf">
        {t("house.draft.roofCurrent")}: {roofSummary(template.roof, t, lng)}
      </p>
      <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
        <label className="flex gap-2 items-center">
          <input type="radio" name="dach" checked={roof === null} disabled={!editable} onChange={() => set(null)} />
          {t("house.draft.roofFromIfc")}
        </label>
        <label className="flex gap-2 items-center">
          <input type="radio" name="dach" checked={roof !== null} disabled={!editable} onChange={() => set(roof ?? start())} />
          {t("house.draft.roofSet")}
        </label>
      </div>
      {roof !== null && (
        <div className="grid gap-4 md:grid-cols-3 items-start">
          <label className="flex flex-col gap-1 text-sm">
            {t("house.draft.roofForm")}
            <select
              className="field"
              value={roof.design.form}
              disabled={!editable}
              onChange={(e) => set(withForm(roof, e.target.value as PitchedForm))}
            >
              {ROOF_FORMS.map((form) => (
                <option key={form} value={form}>
                  {t(`configurator.types.roof.${form}`)}
                </option>
              ))}
            </select>
          </label>
          {field("roofPitch", roof.design.pitch_deg, (next) => ({ ...roof, design: { ...roof.design, pitch_deg: next } }), "0.5")}
          <label className="flex flex-col gap-1 text-sm">
            {t("house.draft.roofRotation")}
            <select
              className="field"
              value={roof.design.rotation}
              disabled={!editable}
              onChange={(e) =>
                set({ ...roof, design: { ...roof.design, rotation: Number(e.target.value) as RoofPlacement["design"]["rotation"] } })
              }
            >
              {ROTATIONS.map((rotation) => (
                <option key={rotation} value={rotation}>
                  {rotation}°
                </option>
              ))}
            </select>
          </label>
          {TWO_PART.has(roof.design.form) && (
            <>
              {field(
                "roofUpperPitch",
                roof.design.upper_pitch_deg,
                (next) => ({ ...roof, design: { ...roof.design, upper_pitch_deg: next } }),
                "0.5",
              )}
              {field(
                roof.design.form === "half_hip" ? "roofHipHeight" : "roofBreakHeight",
                roof.design.break_height,
                (next) => ({ ...roof, design: { ...roof.design, break_height: next } }),
                "0.01",
              )}
            </>
          )}
          {field("roofBearing", roof.bearing_height, (next) => ({ ...roof, bearing_height: next }), "0.01")}
          {field("roofEave", roof.eave_overhang, (next) => ({ ...roof, eave_overhang: next }), "0.01")}
          {field("roofVerge", roof.verge_overhang, (next) => ({ ...roof, verge_overhang: next }), "0.01")}
        </div>
      )}
    </Abschnitt>
  );
}

function Standards({ template, catalog, saved, draft, onChange, editable }: EntwurfProps) {
  const { t, i18n } = useTranslation();
  if (catalog.slots.length === 0) return null;
  return (
    <Abschnitt id="entwurf-standards" title={t("house.draft.defaults")} intro={t("house.draft.defaultsIntro")}>
      <div className="grid gap-4 md:grid-cols-2">
        {catalog.slots.map((slot) => {
          const proposed =
            saved.defaults[slot.id] === undefined
              ? slot.values.find((v) => v.id === template?.defaults[slot.id])
              : undefined;
          return (
            <label key={slot.id} className="flex flex-col gap-1 text-sm">
              {label(slot.name, i18n.language)}
              <select
                className="field"
                value={draft.defaults[slot.id] ?? ""}
                disabled={!editable}
                onChange={(e) =>
                  onChange({
                    ...draft,
                    defaults: withKey(draft.defaults, slot.id, e.target.value === "" ? undefined : e.target.value),
                  })
                }
              >
                <option value="">
                  {t("house.draft.proposal")}
                  {proposed ? `: ${label(proposed.name, i18n.language)}` : ""}
                </option>
                {slot.values.map((value) => (
                  <option key={value.id} value={value.id}>
                    {label(value.name, i18n.language)}
                  </option>
                ))}
              </select>
            </label>
          );
        })}
      </div>
    </Abschnitt>
  );
}

const PAIR = "::";

function Oeffnungen({ report, catalog, saved, draft, onChange, editable, onHighlight }: EntwurfProps) {
  const { t, i18n } = useTranslation();
  if (report.openings.length === 0) return null;
  const valueName = (slotId: string | null, valueId: string | null) => {
    const slot = catalog.slots.find((s) => s.id === slotId);
    const value = slot?.values.find((v) => v.id === valueId);
    return slot && value ? `${label(slot.name, i18n.language)}: ${label(value.name, i18n.language)}` : null;
  };
  const open = new Set(
    report.findings
      .filter((f) => f.code === "opening_type_unmatched" || f.code === "opening_type_ambiguous")
      .map((f) => f.element_id),
  );
  const m = (value: number | null) => (value === null ? "–" : number(value, i18n.language, 2));
  return (
    <Abschnitt id="entwurf-oeffnungen" title={t("house.draft.openings")} intro={t("house.draft.openingsIntro")}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="text-left border-b bd-strong">
              <th scope="col" className="py-2 pr-3 font-medium">{t("house.draft.opening")}</th>
              <th scope="col" className="py-2 pr-3 font-medium">{t("house.draft.size")}</th>
              <th scope="col" className="py-2 pr-3 font-medium">{t("house.draft.type")}</th>
              <th scope="col" className="py-2 font-medium">{t("house.draft.decision")}</th>
            </tr>
          </thead>
          <tbody>
            {report.openings.map((opening) => {
              const chosen = draft.element_defaults[opening.element_id];
              const [chosenSlot, chosenValue] = chosen ? (Object.entries(chosen)[0] ?? []) : [];
              const needed =
                open.has(opening.element_id) ||
                saved.element_defaults[opening.element_id] !== undefined ||
                chosen !== undefined;
              return (
                <tr
                  key={opening.element_id}
                  className="border-b bd align-top"
                  data-testid={`oeffnung-zeile-${opening.element_id}`}
                  onMouseEnter={() => onHighlight([opening.element_id])}
                  onMouseLeave={() => onHighlight([])}
                >
                  <td className="py-2 pr-3">
                    {t(`house.draft.kind.${opening.kind}`)}
                    <div className="f-mono text-xs t-mute">{opening.element_id}</div>
                  </td>
                  <td className="py-2 pr-3 num">
                    {m(opening.width)} × {m(opening.height)} m
                    <div className="text-xs t-mute">
                      {t("house.draft.head")} {m(opening.head_height)} m
                      {opening.shutter_box_height > 0 && ` · ${t("house.draft.shutterBox")} ${m(opening.shutter_box_height)} m`}
                    </div>
                  </td>
                  <td className="py-2 pr-3">
                    {valueName(opening.slot_id, opening.option_value_id) ?? (
                      <span className="t-warn">{t("house.draft.noType")}</span>
                    )}
                    {opening.source && <div className="text-xs t-mute">{t(`house.draft.typeSource.${opening.source}`)}</div>}
                  </td>
                  <td className="py-2">
                    {needed && (
                      <select
                        className="field"
                        aria-label={t("house.draft.openingDecision", { id: opening.element_id })}
                        value={chosenSlot && chosenValue ? `${chosenSlot}${PAIR}${chosenValue}` : ""}
                        disabled={!editable}
                        onChange={(e) => {
                          const [slotId, valueId] = e.target.value.split(PAIR);
                          onChange({
                            ...draft,
                            element_defaults: withKey(
                              draft.element_defaults,
                              opening.element_id,
                              slotId && valueId ? { [slotId]: valueId } : undefined,
                            ),
                          });
                        }}
                      >
                        <option value="">{t("house.draft.open")}</option>
                        {catalog.slots.map((slot) => (
                          <optgroup key={slot.id} label={label(slot.name, i18n.language)}>
                            {slot.values.map((value) => (
                              <option key={value.id} value={`${slot.id}${PAIR}${value.id}`}>
                                {label(value.name, i18n.language)}
                              </option>
                            ))}
                          </optgroup>
                        ))}
                      </select>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Abschnitt>
  );
}
