/**
 * Büro: Ausstattungslinien und Optionen, unabhängig von einzelnen Typen (Plan H1 5 Schritt 4). Ausschlüsse
 * (`excludes`) und „enthalten in Linie“ gelten in der Konfiguration (H3); dazu Art und Maße einer Option
 * (Terrasse, Carport) und das Material für die Regelprüfung (Plan H3 3.2). Eine Änderung erzeugt immer eine
 * neue Version (L4); veröffentlichte Stände bleiben unverändert.
 */

import { useState, type FormEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useOutletContext } from "react-router";

import {
  useCreateModuleVersion,
  useCreatePackageVersion,
  useModules,
  usePackages,
  usePublishModule,
  usePublishPackage,
  type ModuleVersionOut,
  type PackageVersionOut,
} from "../../../api/catalog";
import type { components } from "../../../api/schema";
import { canEditCatalog, KatalogFehler, Statusmarke } from "../../../katalog/bausteine";

type Staff = components["schemas"]["StaffInfo"];

const SLUG_PATTERN = "^[a-z][a-z0-9_]{1,59}$";
const lines = (text: string) => text.split("\n").map((line) => line.trim()).filter(Boolean);

/** Materialklassen der Regeln (Spez. 4.1); dieselbe Liste kennt das Backend. */
const MATERIALS = ["render", "wood", "brick", "stone", "concrete", "metal", "glass", "slate", "clay_tile", "zinc", "composite", "vegetation", "other"] as const;
type OptionKind = ModuleVersionOut["kind"];
const KINDS: readonly OptionKind[] = ["plain", "terrace", "carport"];

type Regulatory = { facade_material: string; roof_material: string };
const regulatoryOf = (source?: Record<string, string>): Regulatory => ({
  facade_material: source?.facade_material ?? "",
  roof_material: source?.roof_material ?? "",
});
const regulatoryBody = (value: Regulatory): Record<string, string> =>
  Object.fromEntries(Object.entries(value).filter(([, material]) => material !== ""));

/** Material von Fassade und Dach für die Regelprüfung; ohne Angabe bleibt die Prüfung „nicht prüfbar“. */
function MaterialAuswahl({ value, onChange }: { value: Regulatory; onChange: (next: Regulatory) => void }) {
  const { t } = useTranslation();
  const select = (key: keyof Regulatory, label: string) => (
    <label className="flex flex-col gap-1">
      {label}
      <select className="field" value={value[key]} onChange={(e) => onChange({ ...value, [key]: e.target.value })}>
        <option value="">{t("catalog.lo.noMaterial")}</option>
        {MATERIALS.map((material) => (
          <option key={material} value={material}>
            {t(`configurator.material.${material}`)}
          </option>
        ))}
      </select>
    </label>
  );
  return (
    <>
      {select("facade_material", t("catalog.lo.facadeMaterial"))}
      {select("roof_material", t("catalog.lo.roofMaterial"))}
      <span className="text-xs t-mute md:col-span-2">{t("catalog.lo.materialHint")}</span>
    </>
  );
}

/** Auswahl mehrerer Slugs als Kontrollkästchen; leere Auswahl ist zulässig. */
function Auswahl({ legend, options, selected, onChange }: { legend: string; options: string[]; selected: string[]; onChange: (next: string[]) => void }) {
  const { t } = useTranslation();
  return (
    <fieldset className="border bd p-3 m-0 flex flex-col gap-2 text-sm">
      <legend className="px-1">{legend}</legend>
      {options.length === 0 && <span className="t-mute">{t("catalog.lo.noOptions")}</span>}
      <div className="flex gap-x-4 gap-y-1 flex-wrap">
        {options.map((slug) => (
          <label key={slug} className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={selected.includes(slug)}
              onChange={(e) => onChange(e.target.checked ? [...selected, slug] : selected.filter((s) => s !== slug))}
            />
            <span className="f-mono">{slug}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

interface LinienFormularProps {
  optionSlugs: string[];
  initial?: PackageVersionOut;
  onDone?: () => void;
}

function LinienFormular({ optionSlugs, initial, onDone }: LinienFormularProps) {
  const { t } = useTranslation();
  const create = useCreatePackageVersion();
  const [slug, setSlug] = useState(initial?.slug ?? "");
  const [labelDe, setLabelDe] = useState(initial?.label_de ?? "");
  const [labelFr, setLabelFr] = useState(initial?.label_fr ?? "");
  const [scope, setScope] = useState((initial?.scope ?? []).join("\n"));
  const [included, setIncluded] = useState(initial?.included_option_slugs ?? []);
  const [regulatory, setRegulatory] = useState(regulatoryOf(initial?.regulatory));

  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(
      {
        slug,
        body: {
          label_de: labelDe,
          label_fr: labelFr,
          scope: lines(scope),
          included_option_slugs: included,
          regulatory: regulatoryBody(regulatory),
        },
      },
      {
        onSuccess: () => {
          if (!initial) {
            setSlug("");
            setLabelDe("");
            setLabelFr("");
            setScope("");
            setIncluded([]);
            setRegulatory(regulatoryOf());
          }
          onDone?.();
        },
      },
    );
  };

  return (
    <form onSubmit={submit} className="grid gap-3 md:grid-cols-2 text-sm">
      <label className="flex flex-col gap-1">
        {t("catalog.lo.slug")}
        <input className="field f-mono" value={slug} onChange={(e) => setSlug(e.target.value)} pattern={SLUG_PATTERN} readOnly={Boolean(initial)} required />
      </label>
      <span className="hidden md:block" />
      <label className="flex flex-col gap-1">
        {t("catalog.lo.labelDe")}
        <input className="field" value={labelDe} onChange={(e) => setLabelDe(e.target.value)} required />
      </label>
      <label className="flex flex-col gap-1">
        {t("catalog.lo.labelFr")}
        <input className="field" value={labelFr} onChange={(e) => setLabelFr(e.target.value)} required />
      </label>
      <label className="flex flex-col gap-1 md:col-span-2">
        {t("catalog.lo.scope")}
        <textarea className="field" rows={4} value={scope} onChange={(e) => setScope(e.target.value)} />
        <span className="text-xs t-mute">{t("catalog.lo.scopeHint")}</span>
      </label>
      <div className="md:col-span-2">
        <Auswahl legend={t("catalog.lo.included")} options={optionSlugs} selected={included} onChange={setIncluded} />
      </div>
      <MaterialAuswahl value={regulatory} onChange={setRegulatory} />
      <div className="md:col-span-2 flex items-center gap-3">
        <button type="submit" className="btn btn-primary" disabled={create.isPending}>
          {initial ? t("catalog.lo.newVersion") : t("catalog.lo.createLine")}
        </button>
        {create.isSuccess && <span role="status" className="t-mute">{t("catalog.lo.draftCreated", { version: create.data.version })}</span>}
      </div>
      {create.isError && <div className="md:col-span-2"><KatalogFehler error={create.error} /></div>}
    </form>
  );
}

function OptionFormular({ optionSlugs, initial, onDone }: { optionSlugs: string[]; initial?: ModuleVersionOut; onDone?: () => void }) {
  const { t } = useTranslation();
  const create = useCreateModuleVersion();
  const [slug, setSlug] = useState(initial?.slug ?? "");
  const [labelDe, setLabelDe] = useState(initial?.label_de ?? "");
  const [labelFr, setLabelFr] = useState(initial?.label_fr ?? "");
  const [excludes, setExcludes] = useState(initial?.excludes_slugs ?? []);
  const [kind, setKind] = useState<OptionKind>(initial?.kind ?? "plain");
  const [regulatory, setRegulatory] = useState(regulatoryOf(initial?.regulatory));
  const [dims, setDims] = useState<Record<string, string>>(
    Object.fromEntries(Object.entries(initial?.params ?? {}).map(([key, value]) => [key, String(value)])),
  );
  const dim = (key: string, fallback: string) => dims[key] ?? fallback;

  const params = (): Record<string, number> => {
    if (kind === "terrace") {
      return {
        depth_m: Number(dim("depth_m", "3")),
        height_above_terrain_m: Number(dim("height_above_terrain_m", "0.3")),
        sealing_factor: Number(dim("sealing_factor", "1")),
      };
    }
    if (kind === "carport") {
      const spaces = Number(dim("spaces", "1"));
      return {
        spaces,
        width_m: Number(dim("width_m", String(3 * spaces))),
        depth_m: Number(dim("depth_m", "5")),
        height_m: Number(dim("height_m", "2.7")),
      };
    }
    return {};
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(
      {
        slug,
        body: {
          label_de: labelDe,
          label_fr: labelFr,
          excludes_slugs: excludes,
          kind,
          params: params(),
          regulatory: regulatoryBody(regulatory),
        },
      },
      {
        onSuccess: () => {
          if (!initial) {
            setSlug("");
            setLabelDe("");
            setLabelFr("");
            setExcludes([]);
            setKind("plain");
            setDims({});
            setRegulatory(regulatoryOf());
          }
          onDone?.();
        },
      },
    );
  };

  return (
    <form onSubmit={submit} className="grid gap-3 md:grid-cols-2 text-sm">
      <label className="flex flex-col gap-1">
        {t("catalog.lo.slug")}
        <input className="field f-mono" value={slug} onChange={(e) => setSlug(e.target.value)} pattern={SLUG_PATTERN} readOnly={Boolean(initial)} required />
      </label>
      <span className="hidden md:block" />
      <label className="flex flex-col gap-1">
        {t("catalog.lo.labelDe")}
        <input className="field" value={labelDe} onChange={(e) => setLabelDe(e.target.value)} required />
      </label>
      <label className="flex flex-col gap-1">
        {t("catalog.lo.labelFr")}
        <input className="field" value={labelFr} onChange={(e) => setLabelFr(e.target.value)} required />
      </label>
      <label className="flex flex-col gap-1">
        {t("catalog.lo.kind")}
        <select className="field" value={kind} onChange={(e) => setKind(e.target.value as OptionKind)}>
          {KINDS.map((option) => (
            <option key={option} value={option}>
              {t(`catalog.lo.kinds.${option}`)}
            </option>
          ))}
        </select>
      </label>
      <span className="hidden md:block" />
      {kind === "terrace" && (
        <>
          <label className="flex flex-col gap-1">
            {t("catalog.lo.depth")}
            <input className="field" type="number" step="0.1" min="0.5" max="6" value={dim("depth_m", "3")} onChange={(e) => setDims({ ...dims, depth_m: e.target.value })} />
          </label>
          <label className="flex flex-col gap-1">
            {t("catalog.lo.heightAboveTerrain")}
            <input className="field" type="number" step="0.05" min="0" max="3" value={dim("height_above_terrain_m", "0.3")} onChange={(e) => setDims({ ...dims, height_above_terrain_m: e.target.value })} />
          </label>
          <label className="flex flex-col gap-1">
            {t("catalog.lo.sealingFactor")}
            <input className="field" type="number" step="0.05" min="0" max="1" value={dim("sealing_factor", "1")} onChange={(e) => setDims({ ...dims, sealing_factor: e.target.value })} />
          </label>
          <span className="text-xs t-mute self-end">{t("catalog.lo.terraceHint")}</span>
        </>
      )}
      {kind === "carport" && (
        <>
          <label className="flex flex-col gap-1">
            {t("catalog.lo.spaces")}
            <select className="field" value={dim("spaces", "1")} onChange={(e) => setDims({ ...dims, spaces: e.target.value })}>
              <option value="1">1</option>
              <option value="2">2</option>
            </select>
          </label>
          <label className="flex flex-col gap-1">
            {t("catalog.lo.width")}
            <input className="field" type="number" step="0.1" min="2" max="12" value={dim("width_m", String(3 * Number(dim("spaces", "1"))))} onChange={(e) => setDims({ ...dims, width_m: e.target.value })} />
          </label>
          <label className="flex flex-col gap-1">
            {t("catalog.lo.depth")}
            <input className="field" type="number" step="0.1" min="2" max="10" value={dim("depth_m", "5")} onChange={(e) => setDims({ ...dims, depth_m: e.target.value })} />
          </label>
          <label className="flex flex-col gap-1">
            {t("catalog.lo.height")}
            <input className="field" type="number" step="0.1" min="2" max="4" value={dim("height_m", "2.7")} onChange={(e) => setDims({ ...dims, height_m: e.target.value })} />
          </label>
          <span className="text-xs t-mute md:col-span-2">{t("catalog.lo.carportHint")}</span>
        </>
      )}
      <MaterialAuswahl value={regulatory} onChange={setRegulatory} />
      <div className="md:col-span-2">
        <Auswahl legend={t("catalog.lo.excludes")} options={optionSlugs.filter((s) => s !== slug)} selected={excludes} onChange={setExcludes} />
      </div>
      <div className="md:col-span-2 flex items-center gap-3">
        <button type="submit" className="btn btn-primary" disabled={create.isPending}>
          {initial ? t("catalog.lo.newVersion") : t("catalog.lo.createOption")}
        </button>
        {create.isSuccess && <span role="status" className="t-mute">{t("catalog.lo.draftCreated", { version: create.data.version })}</span>}
      </div>
      {create.isError && <div className="md:col-span-2"><KatalogFehler error={create.error} /></div>}
    </form>
  );
}

/** Alle Versionen eines Slugs, neueste zuerst, mit Veröffentlichen für Entwürfe und Neuer-Stand-Formular. */
function Gruppe<T extends { slug: string; version: number; status: PackageVersionOut["status"]; label_de: string; label_fr: string }>({
  versions,
  editable,
  detail,
  publish,
  publishing,
  form,
}: {
  versions: T[];
  editable: boolean;
  detail: (version: T) => string;
  publish: (version: T) => void;
  publishing: boolean;
  form: (latest: T, close: () => void) => ReactNode;
}) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const latest = versions[0]!;
  const label = (v: T) => (i18n.language === "de" ? v.label_de : v.label_fr);
  return (
    <li className="karte p-4 flex flex-col gap-3" data-testid={`eintrag-${latest.slug}`}>
      <div className="flex items-baseline gap-3 flex-wrap">
        <h4 className="m-0 text-base font-medium">{label(latest)}</h4>
        <span className="f-mono text-sm t-mute">{latest.slug}</span>
      </div>
      <ul className="m-0 p-0 list-none flex flex-col gap-2">
        {versions.map((version) => (
          <li key={version.version} className="flex items-baseline gap-3 flex-wrap text-sm">
            <span className="f-mono">v{version.version}</span>
            <Statusmarke status={version.status} />
            <span className="t-mute">{detail(version)}</span>
            {editable && version.status === "draft" && (
              <button
                type="button"
                className="btn btn-ghost"
                disabled={publishing}
                onClick={() => {
                  if (window.confirm(t("catalog.lo.publishConfirm", { name: label(version), version: version.version }))) publish(version);
                }}
              >
                {t("catalog.lo.publish")}
              </button>
            )}
          </li>
        ))}
      </ul>
      {editable && (
        <div>
          <button type="button" className="link text-sm" aria-expanded={open} onClick={() => setOpen(!open)}>
            {t("catalog.lo.editAsNew")}
          </button>
          {open && <div className="mt-3">{form(latest, () => setOpen(false))}</div>}
        </div>
      )}
    </li>
  );
}

function groupBySlug<T extends { slug: string }>(versions: T[]): T[][] {
  const groups = new Map<string, T[]>();
  for (const version of versions) groups.set(version.slug, [...(groups.get(version.slug) ?? []), version]);
  return [...groups.values()];
}

export function KatalogLinienOptionen() {
  const { t } = useTranslation();
  const staff = useOutletContext<Staff>();
  const packages = usePackages();
  const modules = useModules();
  const publishPackage = usePublishPackage();
  const publishModule = usePublishModule();
  const editable = canEditCatalog(staff);
  const optionSlugs = [...new Set((modules.data ?? []).map((m) => m.slug))];

  return (
    <div className="flex flex-col gap-10">
      <p className="m-0 text-sm t-mute max-w-prose">{t("catalog.lo.intro")}</p>

      <section aria-labelledby="katalog-linien" className="flex flex-col gap-4">
        <h3 id="katalog-linien" className="m-0 text-lg font-medium">{t("catalog.lo.linesTitle")}</h3>
        {packages.isPending && <p className="t-mute">{t("loading")}</p>}
        {packages.isError && <KatalogFehler error={packages.error} />}
        {packages.data && packages.data.length === 0 && <p className="t-mute">{t("catalog.lo.noLines")}</p>}
        <ul className="m-0 p-0 list-none flex flex-col gap-4">
          {groupBySlug(packages.data ?? []).map((versions) => (
            <Gruppe
              key={versions[0]!.slug}
              versions={versions}
              editable={editable}
              detail={(v) => [v.scope.join(" · "), v.included_option_slugs.length ? `${t("catalog.lo.includedShort")}: ${v.included_option_slugs.join(", ")}` : ""].filter(Boolean).join(" — ")}
              publish={(v) => publishPackage.mutate({ slug: v.slug, version: v.version })}
              publishing={publishPackage.isPending}
              form={(latest, close) => <LinienFormular key={latest.id} optionSlugs={optionSlugs} initial={latest} onDone={close} />}
            />
          ))}
        </ul>
        {publishPackage.isError && <KatalogFehler error={publishPackage.error} />}
        {editable && modules.isSuccess && (
          <details className="karte p-4">
            <summary className="cursor-pointer font-medium">{t("catalog.lo.createLine")}</summary>
            <div className="mt-3"><LinienFormular optionSlugs={optionSlugs} /></div>
          </details>
        )}
      </section>

      <section aria-labelledby="katalog-optionen" className="flex flex-col gap-4">
        <h3 id="katalog-optionen" className="m-0 text-lg font-medium">{t("catalog.lo.optionsTitle")}</h3>
        {modules.isPending && <p className="t-mute">{t("loading")}</p>}
        {modules.isError && <KatalogFehler error={modules.error} />}
        {modules.data && modules.data.length === 0 && <p className="t-mute">{t("catalog.lo.noOptions")}</p>}
        <ul className="m-0 p-0 list-none flex flex-col gap-4">
          {groupBySlug(modules.data ?? []).map((versions) => (
            <Gruppe
              key={versions[0]!.slug}
              versions={versions}
              editable={editable}
              detail={(v) =>
                [
                  v.kind !== "plain"
                    ? `${t(`catalog.lo.kindShort.${v.kind}`)} ${Object.entries(v.params)
                        .map(([key, value]) => `${key} ${String(value)}`)
                        .join(", ")}`
                    : "",
                  v.excludes_slugs.length ? `${t("catalog.lo.excludesShort")}: ${v.excludes_slugs.join(", ")}` : "",
                ]
                  .filter(Boolean)
                  .join(" — ")
              }
              publish={(v) => publishModule.mutate({ slug: v.slug, version: v.version })}
              publishing={publishModule.isPending}
              form={(latest, close) => <OptionFormular key={latest.id} optionSlugs={optionSlugs} initial={latest} onDone={close} />}
            />
          ))}
        </ul>
        {publishModule.isError && <KatalogFehler error={publishModule.error} />}
        {editable && (
          <details className="karte p-4">
            <summary className="cursor-pointer font-medium">{t("catalog.lo.createOption")}</summary>
            <div className="mt-3"><OptionFormular optionSlugs={optionSlugs} /></div>
          </details>
        )}
      </section>
    </div>
  );
}
