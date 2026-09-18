/** Erfassungsformulare eines Typstands: Fassadenrollen, Lage von Eingang und Garagentor, RE2020, Grundriss-PDF. */

import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  useSetEnergyAssessment,
  useUploadPlanDocument,
  type EnergyAssessmentOut,
  type PackageVersionOut,
} from "../api/catalog";
import { KatalogFehler, number } from "./bausteine";
import { edgesOf, FACADE_ROLES, suggestRoles, type FacadeRole, type Placement, type Ring, type Roles } from "./geometrie";
import { ROLE_COLORS } from "./Grundriss";

// ---------------------------------------------------------------------------
// Fassadenrollen (Plan H1 3.3): Vorschlag des Systems, Bestätigung durch das Büro (L6)
// ---------------------------------------------------------------------------

interface FassadenrollenProps {
  ring: Ring;
  roles: Roles;
  onChange: (roles: Roles) => void;
  onHighlight: (edge: number | null) => void;
  editable: boolean;
  saving: boolean;
  saved: boolean;
  onSave: () => void;
}

export function Fassadenrollen({ ring, roles, onChange, onHighlight, editable, saving, saved, onSave }: FassadenrollenProps) {
  const { t, i18n } = useTranslation();
  const edges = edgesOf(ring);
  const setRole = (index: number, role: FacadeRole | "") => {
    const next = { ...roles };
    if (role) next[index] = role;
    else delete next[index];
    onChange(next);
  };
  return (
    <section aria-labelledby="typ-rollen" className="flex flex-col gap-3">
      <h3 id="typ-rollen" className="m-0 text-lg font-medium">{t("catalog.type.roles.title")}</h3>
      <p className="m-0 text-sm t-mute max-w-prose">{t("catalog.type.roles.intro")}</p>
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-left border-b bd-strong">
            <th scope="col" className="py-2 pr-3 font-medium">{t("catalog.type.roles.edge")}</th>
            <th scope="col" className="py-2 pr-3 font-medium">{t("catalog.type.roles.length")}</th>
            <th scope="col" className="py-2 font-medium">{t("catalog.type.roles.role")}</th>
          </tr>
        </thead>
        <tbody>
          {edges.map((edge) => (
            <tr key={edge.index} className="border-b bd" onMouseEnter={() => onHighlight(edge.index)} onMouseLeave={() => onHighlight(null)}>
              <th scope="row" className="py-2 pr-3 text-left font-normal f-mono">{edge.index}</th>
              <td className="py-2 pr-3 num">{number(edge.length, i18n.language, 2)} m</td>
              <td className="py-2">
                <select
                  className="field"
                  aria-label={t("catalog.type.roles.forEdge", { index: edge.index })}
                  value={roles[edge.index] ?? ""}
                  disabled={!editable}
                  onFocus={() => onHighlight(edge.index)}
                  onBlur={() => onHighlight(null)}
                  onChange={(e) => setRole(edge.index, e.target.value as FacadeRole | "")}
                  style={roles[edge.index] ? { borderColor: ROLE_COLORS[roles[edge.index]!] } : undefined}
                >
                  <option value="">{t("catalog.type.roles.none")}</option>
                  {FACADE_ROLES.map((role) => (
                    <option key={role} value={role}>
                      {t(`catalog.facadeRole.${role}`)}
                    </option>
                  ))}
                </select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {editable && (
        <div className="flex gap-3 flex-wrap">
          <button type="button" className="btn btn-ghost" onClick={() => onChange(suggestRoles(ring))}>
            {t("catalog.type.roles.suggest")}
          </button>
          <button type="button" className="btn btn-primary" onClick={onSave} disabled={saving}>
            {t("catalog.save")}
          </button>
          {saved && <span role="status" className="self-center text-sm t-mute">{t("catalog.saved")}</span>}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Eingang und Garagentor: je ein Punkt auf einer Umrisskante, Ablage als {edge, position} (ANNAHMEN H10)
// ---------------------------------------------------------------------------

interface PunktProps {
  label: string;
  value: Placement | null;
  edgeCount: number;
  editable: boolean;
  onChange: (value: Placement | null) => void;
}

function Punkt({ label, value, edgeCount, editable, onChange }: PunktProps) {
  const { t } = useTranslation();
  return (
    <fieldset className="border bd p-3 flex flex-col gap-3 m-0">
      <legend className="px-1 text-sm font-medium">{label}</legend>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={value !== null}
          disabled={!editable}
          onChange={(e) => onChange(e.target.checked ? { edge: 0, position: 0.5 } : null)}
        />
        {t("catalog.type.placement.set")}
      </label>
      {value && (
        <div className="grid gap-3 sm:grid-cols-2 text-sm">
          <label className="flex flex-col gap-1">
            {t("catalog.type.placement.edge")}
            <select
              className="field"
              value={value.edge}
              disabled={!editable}
              onChange={(e) => onChange({ ...value, edge: Number(e.target.value) })}
            >
              {Array.from({ length: edgeCount }, (_, i) => (
                <option key={i} value={i}>{i}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            {t("catalog.type.placement.position", { percent: Math.round(value.position * 100) })}
            <input
              type="range"
              min={0}
              max={100}
              step={1}
              value={Math.round(value.position * 100)}
              disabled={!editable}
              onChange={(e) => onChange({ ...value, position: Number(e.target.value) / 100 })}
            />
          </label>
        </div>
      )}
    </fieldset>
  );
}

interface PlatzierungProps {
  edgeCount: number;
  entrance: Placement | null;
  garageDoor: Placement | null;
  onEntrance: (value: Placement | null) => void;
  onGarageDoor: (value: Placement | null) => void;
  editable: boolean;
  saving: boolean;
  saved: boolean;
  onSave: () => void;
}

export function Platzierung({ edgeCount, entrance, garageDoor, onEntrance, onGarageDoor, editable, saving, saved, onSave }: PlatzierungProps) {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="typ-lage" className="flex flex-col gap-3">
      <h3 id="typ-lage" className="m-0 text-lg font-medium">{t("catalog.type.placement.title")}</h3>
      <p className="m-0 text-sm t-mute max-w-prose">{t("catalog.type.placement.intro")}</p>
      <div className="grid gap-4 md:grid-cols-2">
        <Punkt label={t("catalog.type.entrance")} value={entrance} edgeCount={edgeCount} editable={editable} onChange={onEntrance} />
        <Punkt label={t("catalog.type.garageDoor")} value={garageDoor} edgeCount={edgeCount} editable={editable} onChange={onGarageDoor} />
      </div>
      {editable && (
        <div className="flex gap-3">
          <button type="button" className="btn btn-primary" onClick={onSave} disabled={saving}>
            {t("catalog.save")}
          </button>
          {saved && <span role="status" className="self-center text-sm t-mute">{t("catalog.saved")}</span>}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// RE2020 je Typ und Linie (Plan H1 3.8): Freitext-Befund, keine Wärmeschutzberechnung (L7)
// ---------------------------------------------------------------------------

function EnergieFormular({ typeSlug, packageSlug, label, current }: { typeSlug: string; packageSlug: string; label: string; current?: EnergyAssessmentOut }) {
  const { t } = useTranslation();
  const save = useSetEnergyAssessment(typeSlug);
  const [zone, setZone] = useState(current?.climate_zone ?? "");
  const [verdict, setVerdict] = useState(current?.verdict ?? "");
  const [compliant, setCompliant] = useState(current?.compliant ?? true);
  const [surcharge, setSurcharge] = useState(
    current?.compliance_surcharge_cents != null ? String(current.compliance_surcharge_cents / 100) : "",
  );
  const [measures, setMeasures] = useState(current?.measures ?? "");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate({
      packageSlug,
      body: {
        climate_zone: zone.trim(),
        verdict: verdict.trim(),
        compliant,
        compliance_surcharge_cents: surcharge.trim() === "" ? null : Math.round(Number(surcharge.replace(",", ".")) * 100),
        measures: measures.trim() || null,
      },
    });
  };

  return (
    <form onSubmit={submit} className="border bd p-3 grid gap-3 md:grid-cols-2 text-sm" aria-label={t("catalog.type.energy.forLine", { line: label })}>
      <h4 className="m-0 md:col-span-2 font-medium">
        {label} <span className="f-mono t-mute font-normal">{packageSlug}</span>
        {!current && <span className="t-mute font-normal"> · {t("catalog.type.energy.notAssessed")}</span>}
      </h4>
      <label className="flex flex-col gap-1">
        {t("catalog.type.energy.zone")}
        <input className="field f-mono" value={zone} onChange={(e) => setZone(e.target.value)} required />
      </label>
      <label className="flex items-center gap-2 self-end pb-2">
        <input type="checkbox" checked={compliant} onChange={(e) => setCompliant(e.target.checked)} />
        {t("catalog.type.energy.compliant")}
      </label>
      <label className="flex flex-col gap-1 md:col-span-2">
        {t("catalog.type.energy.verdict")}
        <textarea className="field" rows={2} value={verdict} onChange={(e) => setVerdict(e.target.value)} required />
      </label>
      <label className="flex flex-col gap-1">
        {t("catalog.type.energy.surcharge")}
        <input className="field num" inputMode="decimal" value={surcharge} onChange={(e) => setSurcharge(e.target.value)} />
      </label>
      <label className="flex flex-col gap-1">
        {t("catalog.type.energy.measures")}
        <input className="field" value={measures} onChange={(e) => setMeasures(e.target.value)} />
      </label>
      <div className="md:col-span-2 flex items-center gap-3">
        <button type="submit" className="btn btn-primary" disabled={save.isPending}>
          {t("catalog.save")}
        </button>
        {save.isSuccess && <span role="status" className="t-mute">{t("catalog.saved")}</span>}
      </div>
      {save.isError && <div className="md:col-span-2"><KatalogFehler error={save.error} /></div>}
    </form>
  );
}

interface EnergieProps {
  typeSlug: string;
  packages: PackageVersionOut[];
  assessments: EnergyAssessmentOut[];
  language: string;
  editable: boolean;
}

export function Energie({ typeSlug, packages, assessments, language, editable }: EnergieProps) {
  const { t } = useTranslation();
  // eine Zeile je Linie: die neueste Version liefert das Etikett
  const lines = [...new Map(packages.map((p) => [p.slug, p])).values()];
  return (
    <section aria-labelledby="typ-energie" className="flex flex-col gap-3">
      <h3 id="typ-energie" className="m-0 text-lg font-medium">{t("catalog.type.energy.title")}</h3>
      <p className="m-0 text-sm t-mute max-w-prose">{t("catalog.type.energy.intro")}</p>
      {lines.length === 0 && <p className="m-0 text-sm t-mute">{t("catalog.type.energy.noLines")}</p>}
      {lines.map((line) => {
        const current = assessments.find((a) => a.building_type_slug === typeSlug && a.package_slug === line.slug);
        const label = language === "de" ? line.label_de : line.label_fr;
        if (!editable) {
          return (
            <div key={line.slug} className="border bd p-3 text-sm">
              <strong>{label}</strong>{" "}
              {current ? `· ${current.climate_zone} · ${current.verdict}` : `· ${t("catalog.type.energy.notAssessed")}`}
            </div>
          );
        }
        return <EnergieFormular key={line.slug} typeSlug={typeSlug} packageSlug={line.slug} label={label} current={current} />;
      })}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Grundriss-PDF: reiner Upload, keine Auswertung (Plan H1 3.6)
// ---------------------------------------------------------------------------

export function PlanDokument({ slug }: { slug: string }) {
  const { t, i18n } = useTranslation();
  const upload = useUploadPlanDocument(slug);
  const [file, setFile] = useState<File | null>(null);
  return (
    <section aria-labelledby="typ-pdf" className="flex flex-col gap-3">
      <h3 id="typ-pdf" className="m-0 text-lg font-medium">{t("catalog.type.pdf.title")}</h3>
      <p className="m-0 text-sm t-mute max-w-prose">{t("catalog.type.pdf.intro")}</p>
      <div className="flex gap-3 items-end flex-wrap">
        <label className="flex flex-col gap-1 text-sm">
          {t("catalog.type.pdf.file")}
          <input className="field" type="file" accept="application/pdf,.pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        <button type="button" className="btn btn-ghost" disabled={!file || upload.isPending} onClick={() => file && upload.mutate(file)}>
          {t("catalog.type.pdf.upload")}
        </button>
      </div>
      {upload.isSuccess && (
        <p role="status" className="m-0 text-sm t-mute">
          {t("catalog.type.pdf.done", { name: upload.data.filename, size: number(upload.data.size_bytes / 1024, i18n.language, 0) })}
        </p>
      )}
      {upload.isError && <KatalogFehler error={upload.error} />}
    </section>
  );
}
